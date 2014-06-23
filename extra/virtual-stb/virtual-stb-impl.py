#!/usr/bin/env python

import argparse
import os
import re
import socket
import stat
import subprocess
import sys
import threading
import time
from contextlib import contextmanager

import jinja2
from enum import Enum

from _stbt import notify, utils


def parse_proc_net_unix():
    with open('/proc/net/unix', 'r') as f:
        headings = f.readline().split()
        for line in f:
            yield dict(zip(headings, line.split()))


class XStatus(Enum):
    SUCCESS = 0
    FAILURE = 1
    CONFLICT = 2


def await_xorg_startup(xorg, display_no):
    while True:
        if xorg.poll() is not None:
            return XStatus.FAILURE

        inode = [sock for sock in parse_proc_net_unix()
                 if sock.get('Path', '') == '@/tmp/.X11-unix/X%i' % display_no]
        if len(inode) == 1:
            for linkname in os.listdir('/proc/%i/fd' % xorg.pid):
                abslinkname = '/proc/%i/fd/%s' % (xorg.pid, linkname)
                if os.stat(abslinkname)[stat.ST_INO] == int(inode[0]['Inode']):
                    return XStatus.SUCCESS
            return XStatus.CONFLICT
        time.sleep(0.1)


def dumb_await_xorg_startup(xorg, display_no):
    """Inside a Docker container on an Ubuntu host with apparmor, /proc/<pid>/fd
    doesn't report the inode numbers associated with the process's open
    sockets. This means we can't cross-reference with /proc/net/unix to work
    out if the /tmp/.X11-unix/X* belongs to this X server or not. However since
    we spawned a container just to run 'virtual-stb' we can assume that there
    will be no conflicts -- ours will be the only X server running.
    """
    while True:
        if xorg.poll() is not None:
            return XStatus.FAILURE

        if os.path.exists('/tmp/.X11-unix/X%i' % display_no):
            return XStatus.SUCCESS

        time.sleep(0.1)


@contextmanager
def start_x(width, height, in_container=False):
    with open(os.path.dirname(__file__) + '/xorg.conf.jinja2') as f:
        xorg_conf_template = jinja2.Template(f.read())
    display_no = 10
    while display_no < 100:
        # pylint: disable=W0212
        with utils.named_temporary_directory(prefix='stbt-xorg-') as tmp, \
                open('/dev/null', 'r') as dev_null, \
                open('%s/xorg.output' % tmp, 'w') as xorg_output:

            with open('%s/xorg.conf' % tmp, 'w') as xorg_conf:
                xorg_conf.write(xorg_conf_template.render(
                    width=width, height=height))

            xorg = subprocess.Popen(
                ['Xorg', '-noreset', '+extension', 'GLX', '+extension', 'RANDR',
                 '+extension', 'RENDER', '-config', 'xorg.conf', '-logfile',
                 './xorg.log', ':%i' % display_no],
                stdin=dev_null, stdout=xorg_output, stderr=subprocess.STDOUT,
                close_fds=True, cwd=tmp)
            try:
                if in_container:
                    s = dumb_await_xorg_startup(xorg, display_no)
                else:
                    s = await_xorg_startup(xorg, display_no)
                if s is XStatus.SUCCESS:
                    subprocess.Popen(
                        ['ratpoison', '-d', ':%i' % display_no], close_fds=True,
                        stdin=dev_null, stdout=xorg_output)
                    yield ":%i" % display_no
                    break
                elif s is XStatus.CONFLICT:
                    display_no += 1
                    continue
                elif s is XStatus.FAILURE:
                    raise RuntimeError("Failed to start X")
            finally:
                if xorg.poll() is None:
                    xorg.terminate()
                    xorg.wait()


def load_mapping(filename):
    with open(filename, 'r') as mapfile:
        for line in mapfile:
            s = line.strip().split()
            if len(s) == 2 and not s[0].startswith('#'):
                yield s


def _xdg_config_dir():
    return os.environ.get('XDG_CONFIG_HOME', '%s/.config' % os.environ['HOME'])


@contextmanager
def fake_lircd():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 8765))
    s.listen(5)

    mapping = dict(
        load_mapping(os.path.dirname(__file__) + '/key-mapping.conf'))
    try:
        user_mapping = dict(
            load_mapping(_xdg_config_dir() + '/stbt/key-mapping.conf'))
        mapping = dict(mapping.items() + user_mapping.items())
    except IOError:
        pass

    def listen():
        while True:
            try:
                control, _ = s.accept()
            except socket.error:
                return
            for cmd in control.makefile():
                m = re.match(r'SEND_ONCE (?P<ctrl>\w+) (?P<key>\w+)', cmd)

                if m:
                    key = m.group('key')
                    if key in mapping:
                        key = mapping[key]

                    exit_status = subprocess.call(['xdotool', 'key', key])
                else:
                    exit_status = 1
                control.sendall('BEGIN\n%s%s\nEND\n' % (
                    cmd, 'SUCCESS' if exit_status == 0 else 'ERROR'))

    t = threading.Thread(target=listen)
    t.daemon = True
    t.start()
    try:
        yield
    finally:
        s.close()


@contextmanager
def noop_context():
    yield


def main(argv):
    parser = argparse.ArgumentParser(
        description="Configure stb-tester to use a local program as "
                    "input/output")
    parser.add_argument('--in-container', action='store_true')
    parser.add_argument('--with-lirc', action='store_true')
    parser.add_argument('command', nargs=1)
    parser.add_argument('args', nargs=argparse.REMAINDER)
    args = parser.parse_args(argv[1:])

    with start_x(1280, 720, args.in_container) as display:
        os.environ['DISPLAY'] = display
        with fake_lircd() if args.with_lirc else noop_context():
            if args.with_lirc:
                notify.sd_notify('X_LIRC_SOCKET=%s:8765' %
                                 socket.gethostbyname(socket.gethostname()))
                notify.sd_notify('X_LIRC_REMOTE_NAME=vstb')

            child = subprocess.Popen(args.command + args.args)
            notify.sd_notify('X_DISPLAY=%s' % display)
            notify.sd_notify('READY=1')

            try:
                return child.wait()
            finally:
                if child.poll() is None:
                    child.terminate()

if __name__ == '__main__':
    sys.exit(main(sys.argv))
