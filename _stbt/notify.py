import os
import socket
from contextlib import contextmanager

from .utils import named_temporary_directory


def sd_notify(text):
    try:
        sockname = os.environ.get('NOTIFY_SOCKET', None)
        if sockname and sockname[0] in ['/', '@'] and sockname[1:]:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
            try:
                sock.sendto(text, sockname)
            finally:
                sock.close()
    except StandardError:
        pass


def _read_msgs(sock, timeout=None):
    sock.settimeout(timeout)
    data, _ = sock.recvfrom(65536)
    if data != '':
        for line in data.split('\n'):
            r = line.split('=', 1)
            if len(r) == 2:
                yield tuple(r)


class _SDListener(object):
    def __init__(self, sock, socket_path):
        self.socket_path = socket_path
        self.sock = sock
        self._msgs = []

    def read_msg(self, timeout=None):
        if len(self._msgs) == 0:
            self._msgs = list(_read_msgs(self.sock, timeout))

        return self._msgs.pop(0)


@contextmanager
def sd_listen(overwrite_environment=True, dir_=None):
    serversocket = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    with named_temporary_directory(dir=dir_,
                                   prefix="stbt-virtual-stb-notify") as temp:
        oldsocket = os.environ.get('NOTIFY_SOCKET')
        try:
            serversocket.bind(temp + '/notify')
            if overwrite_environment:
                os.environ['NOTIFY_SOCKET'] = temp + '/notify'
            yield _SDListener(serversocket, temp + '/notify')
        finally:
            serversocket.close()
            if overwrite_environment:
                if oldsocket is not None:
                    os.environ['NOTIFY_SOCKET'] = oldsocket
                else:
                    del os.environ['NOTIFY_SOCKET']


def test_notification():
    with sd_listen() as listener:
        sd_notify("READY=1\n")
        assert listener.read_msg() == ("READY", "1")
        sd_notify("READY=1\nX_DISPLAY=:23\n")
        sd_notify("X_COWS=Great")
        assert listener.read_msg() == ("READY", "1")
        assert listener.read_msg() == ("X_DISPLAY", ":23")
        assert listener.read_msg() == ("X_COWS", "Great")
