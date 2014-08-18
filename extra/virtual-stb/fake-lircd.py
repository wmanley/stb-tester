#!/usr/bin/python

import os
import re
import socket
import subprocess
import threading
from contextlib import contextmanager


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
        yield t
    finally:
        s.close()

with fake_lircd() as t:
    t.join()
