import errno
import os
import sys
import tempfile
from contextlib import contextmanager
from shutil import rmtree


def mkdir_p(d):
    """Python 3.2 has an optional argument to os.makedirs called exist_ok.  To
    support older versions of python we can't use this and need to catch
    exceptions"""
    try:
        os.makedirs(d)
    except OSError, e:
        if e.errno == errno.EEXIST and os.path.isdir(d) \
                and os.access(d, os.R_OK | os.W_OK):
            return
        else:
            raise


@contextmanager
def named_temporary_directory(
        suffix='', prefix='tmp', dir=None):  # pylint: disable=W0622
    dirname = tempfile.mkdtemp(suffix, prefix, dir)
    try:
        yield dirname
    finally:
        rmtree(dirname)


@contextmanager
def hide_stderr():
    """Context manager that hides stderr output."""
    fd = sys.__stderr__.fileno()
    saved_fd = os.dup(fd)
    sys.__stderr__.flush()
    null_stream = open(os.devnull, 'w', 0)
    os.dup2(null_stream.fileno(), fd)
    try:
        yield
    finally:
        sys.__stderr__.flush()
        os.dup2(saved_fd, sys.__stderr__.fileno())
        os.close(saved_fd)
        null_stream.close()
