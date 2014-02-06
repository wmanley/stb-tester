import os
import sys
from gi.repository import GLib, Gio
from time import sleep

FORMAT = 'mp4'

def _gen_video_cache_dir():
    cache_root = (os.environ.get("XDG_CACHE_HOME", None) or
                  os.environ.get("HOME") + '/.cache')
    return cache_root + '/stbt/camera-video-cache'


def _generate_video_if_not_exists(video, video_generator, format_):
    from os.path import isfile
    filename = "%s/%s.%s" % (_gen_video_cache_dir(), video, format_)
    if not isfile(filename):
        import gst_utils
        import tempfile
        sys.stderr.write(
            "Creating test video '%s'.  This only has to happen once but may "
            "take some time...\n" % filename)

        # Create the video atomically to avoid serving invalid mp4s
        tf = tempfile.NamedTemporaryFile(prefix=filename, delete=False)
        video_generator[video](tf.name, container=format_)
        os.rename(tf.name, filename)

        sys.stderr.write("Test video generation complete.\n")
    return filename


def _mkdir_p(dirname):
    """Python 3.2 has an optional argument to os.makedirs called exist_ok.  To
    support older versions of python we can't use this and need to catch
    exceptions"""
    try:
        os.makedirs(dirname)
    except OSError as exc:
        import errno
        if exc.errno == errno.EEXIST and os.path.isdir(dirname):
            pass
        else:
            raise


def _get_external_ip():
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.connect(("192.0.2.0", 80))
    return s.getsockname()[0]


class _HTTPVideoServer(object):
    def __init__(self, video_generators):
        from textwrap import dedent
        from tempfile import NamedTemporaryFile
        from subprocess import CalledProcessError, check_output, STDOUT
        from random import randint
        self.lighttpd_pid = None
        self.video_generators = dict(video_generators)
        video_cache_dir = _gen_video_cache_dir()
        _mkdir_p(video_cache_dir)
        lighttpd_config_file = NamedTemporaryFile(
            prefix='stbt-camera-lighttpd-', suffix='.conf', delete=False)
        pidfile = NamedTemporaryFile(
            prefix="stbt-camera-lighttpd-", suffix=".pidfile")
        # FIXME: This is an awful way to start listening on a random port and
        # not a great way of tracking the sub-process.
        port = None
        while port is None:
            try:
                lighttpd_config_file.seek(0)
                lighttpd_config_file.truncate(0)
                try_port = randint(10000, 30000)
                lighttpd_config_file.write(dedent("""\
                    # This file is generated automatically by stb-tester.
                    # DO NOT EDIT.
                    server.document-root = "%s"

                    server.port = %i

                    server.pid-file            = "%s"

                    mimetype.assign = (
                      ".png" => "image/png",
                      ".mp4" => "video/mp4",
                      ".ts" => "video/MP2T"
                    )""") % (video_cache_dir, try_port, pidfile.name))
                lighttpd_config_file.flush()
                check_output(['lighttpd', '-f', lighttpd_config_file.name],
                             close_fds=True, stderr=STDOUT)
                port = try_port
            except CalledProcessError as e:
                if e.output.find('Address already in use') != -1:
                    pass
                else:
                    sys.stderr.write("lighttpd failed to start: %s\n" %
                                     e.output)
                    raise
        # lighttpd writes its pidfile out after forking rather than before
        # casuing a race.  TODO: Use socket passing to clean all this up.
        while os.fstat(pidfile.fileno()).st_size == 0:
            sleep(0.1)
        self.lighttpd_pid = int(pidfile.read())
        self.base_url = "http://%s:%i/" % (_get_external_ip(), port)

    def __del__(self):
        from signal import SIGTERM
        from os import kill
        if self.lighttpd_pid:
            kill(self.lighttpd_pid, SIGTERM)

    def get_url(self, video, format_=FORMAT):
        _generate_video_if_not_exists(video, self.video_generators, format_)
        return "%s%s.%s" % (self.base_url, video, format_)


class _AssumeTvDriver(object):
    def show(self, filename):
        sys.stderr.write("Assuming video %s is playing\n")

    def stop(self):
        sys.stderr.write("Assuming videos are no longer playing\n")


class _ManualTvDriver(object):
    def __init__(self, video_server):
        self.video_server = video_server

    def show(self, video):
        url = self.video_server.get_url(video)
        sys.stderr.write(
            "Please show %s video.  This can be found at %s\n" % (video, url) +
            "\n" +
            "Press <ENTER> when video is showing\n")
        sys.stdin.readline()
        sys.stderr.write("Thank you\n")

    def stop(self):
        sys.stderr.write("Please return TV back to original state\n")


def add_argparse_argument(argparser):
    from stbt import get_config
    argparser.add_argument(
        "--tv-driver",
        help="Determines how to display videos on TV.\n\n"
             "    manual - Prompt the user then wait for confirmation.\n"
             "    assume - Assume the video is already playing (useful for "
             "scripting when passing a single test to be run).\n"
             default=get_config("camera", "tv_driver", "manual"))


def create_from_args(args, video_generator):
    desc = args.tv_driver
    video_server = _HTTPVideoServer(video_generator)
    if desc == 'assume':
        return _AssumeTvDriver()
    elif desc == 'manual':
        return _ManualTvDriver(video_server)
    else:
        raise RuntimeError("Unknown video driver requested: %s" % desc)
