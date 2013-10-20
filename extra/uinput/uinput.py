#!/usr/bin/python

import os
from time import sleep
from fcntl import ioctl
import ctypes
import linux_uinput
import linux_input
from linux_input import *
import string
import sys
from textwrap import dedent
import SocketServer

_libc = ctypes.CDLL('libc.so.6', use_errno=True)
_libc.gettimeofday.argtypes = [
    ctypes.POINTER(linux_input.timeval), ctypes.c_void_p]


def gettimeofday():
    tv = linux_uinput.timeval()
    if _libc.gettimeofday(tv, 0) < 0:
        raise RuntimeError("gettimeofday failed")
    return tv

_keymapping = dict(
    [(x, "KEY_%s" % x)
     for x in string.ascii_uppercase + '0123456789'] +
    [(' ', "KEY_SPACE")]
)

normal_keys = \
    ["KEY_%s" % x for x in string.ascii_uppercase + '0123456789']

class UInput:
    """Usage:
    
    >>> UInput().write("This is a test")
    """
    def __init__(self, keys=linux_uinput.key.keys()):
        self.fd = os.open("/dev/uinput", os.O_NONBLOCK | os.O_WRONLY)
        ioctl(self.fd, linux_uinput.UI_SET_EVBIT, linux_input.EV_KEY)
        ioctl(self.fd, linux_uinput.UI_SET_EVBIT, linux_input.EV_SYN)

        s = linux_uinput.uinput_user_dev(
            "uinput-sample",
            linux_input.input_id(linux_input.BUS_USB, 0x1234, 0xfedc, 1))
        for k in keys:
            ioctl(self.fd, linux_uinput.UI_SET_KEYBIT, linux_input.key[k])

        os.write(self.fd, s)
        ioctl(self.fd, linux_uinput.UI_DEV_CREATE)

    def __del__(self):
        ioctl(self.fd, linux_uinput.UI_DEV_DESTROY)
        os.close(self.fd)

    def tap_key(self, key):
        keycode = linux_input.key[key]
        e = linux_input.input_event(
            time=gettimeofday(), type=linux_input.EV_KEY, code=keycode,
            value=1)
        if os.write(self.fd, e) != ctypes.sizeof(e):
            raise RuntimeError("Failed to press key")
        e.value = 0
        if os.write(self.fd, e) != ctypes.sizeof(e):
            raise RuntimeError("Failed to release key")
        e = linux_input.input_event(
            time=gettimeofday(), type=linux_input.EV_SYN,
            code=linux_input.SYN_REPORT, value=0)
        if os.write(self.fd, e) != ctypes.sizeof(e):
            raise RuntimeError("Failed to synchronise")

    def set_key(self, key, value):
        keycode = linux_input.key[key]
        e = linux_input.input_event(
            time=gettimeofday(), type=linux_input.EV_KEY, code=keycode,
            value=value)
        if os.write(self.fd, e) != ctypes.sizeof(e):
            raise RuntimeError("Failed to " + ['release', 'press'][value] + " key")
        e = linux_input.input_event(
            time=gettimeofday(), type=linux_input.EV_SYN,
            code=linux_input.SYN_REPORT, value=0)
        if os.write(self.fd, e) != ctypes.sizeof(e):
            raise RuntimeError("Failed to synchronise")

    def write(self, passage):
        for letter in passage:
            self.press_key(_keymapping[letter])


class LIRCTCPHandler(SocketServer.StreamRequestHandler):
    def handle(self):
        sys.stderr.write("INFO: Received connection\n")
        while 1:
            line = self.rfile.readline()
            if line == '':
                # EOF
                break
            cmd = line.strip()
            if cmd == '':
                continue
            directive, remote, code = (cmd.split() + [None]*2)[0:3]
            if directive in ['SEND_ONCE', 'SEND_START', 'SEND_STOP']:
                if code in linux_input.key.keys():
                    if directive == 'SEND_ONCE':
                        self.server.uinput.tap_key(code)
                        sys.stderr.write("INFO: Pressed %s\n" % code)
                    elif directive == 'SEND_START':
                        self.server.uinput.set_key(code, 1)
                        sys.stderr.write("INFO: Pressing %s\n" % code)
                    elif directive == 'SEND_STOP':
                        self.server.uinput.set_key(code, 0)
                        sys.stderr.write("INFO: Releasing %s\n" % code)
                    self.wfile.write("BEGIN\n%s\nSUCCESS\nEND\n" % cmd)
                else:
                    sys.stderr.write("WARNING: Unknown key code \"%s\"\n" % code)
                    self.wfile.write(dedent(
                        '''\
                        BEGIN
                        %s
                        ERROR
                        DATA
                        1
                        Unknown key code %s
                        END
                        ''') % (cmd, code))
            else:
                sys.stderr.write("WARNING: Ignoring unknown command \"%s\"\n" % cmd)
        sys.stderr.write("INFO: Connection closed\n")


def main(argv):
    if len(argv) == 2 and argv[1] == '-l':
        for k in linux_input.key.keys():
            sys.stdout.write("%s\n" % k)
        return 0
    elif len(argv) > 1:
        sys.stdout.write(
            "%s: Simulates key presses with the linux uinput mechanism\n" % argv[0] +
            "\n" +
            "Options:\n" +
            "    -l  Print all known keys\n"
        )
        return 1
    else:
        server = SocketServer.TCPServer(("0.0.0.0", 8765), LIRCTCPHandler)
        server.allow_reuse_address = True
        server.uinput = UInput()
        sys.stderr.write("Listening for connections on 0.0.0.0:8765\n")
        server.serve_forever()
        return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv))
