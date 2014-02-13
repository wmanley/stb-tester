import os
import sys
from gi.repository import GLib, Gio
from time import sleep
from os.path import abspath, dirname, exists

if exists(dirname(abspath(__file__)) + '/../../stbt.py'):
    sys.path.insert(0, dirname(abspath(__file__)) + '/../..')

from stbt import get_config


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
    def __init__(self, video_generators, video_format):
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
        self.video_format = video_format

    def __del__(self):
        from signal import SIGTERM
        from os import kill
        if self.lighttpd_pid:
            kill(self.lighttpd_pid, SIGTERM)

    def get_url(self, video):
        _generate_video_if_not_exists(video, self.video_generators,
                                      self.video_format)
        return "%s%s.%s" % (self.base_url, video, self.video_format)


class _DleynaDriver(object):
    def __init__(self, friendly_name, video_server):
        self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        self.manager = Gio.DBusProxy.new_sync(
            self.bus, Gio.DBusProxyFlags.NONE, None,
            'com.intel.dleyna-renderer', '/com/intel/dLeynaRenderer',
            'com.intel.dLeynaRenderer.Manager', None)
        self.friendly_name = friendly_name
        self.video_server = video_server

    def get_renderer_by_friendly_name(self, target_friendly_name):
        renderer_paths = self.manager.GetRenderers()
        friendly_names = []
        for renderer_path in renderer_paths:
            renderer = Gio.DBusProxy.new_sync(
                self.bus, Gio.DBusProxyFlags.NONE, None,
                'com.intel.dleyna-renderer', renderer_path,
                'com.intel.dLeynaRenderer.RendererDevice', None)
            friendly_name = \
                renderer.get_cached_property('FriendlyName').get_string()
            if friendly_name == target_friendly_name:
                return Gio.DBusProxy.new_sync(
                    self.bus, Gio.DBusProxyFlags.NONE, None,
                    'com.intel.dleyna-renderer', renderer_path,
                    'org.mpris.MediaPlayer2.Player', None)
            friendly_names.append(friendly_name)
        raise RuntimeError(
            "Cannot find TV with friendly name '%s'.  Options are:\n\n    %s\n"
            % (target_friendly_name, '\n    '.join(friendly_names)))

    def play_uri(self, uri):
        success = False
        # Dleyna is very buggy, need to do this in a loop until it succeeds!
        while not success:
            try:
                player = self.get_renderer_by_friendly_name(self.friendly_name)
                player.Stop()
                player.call_sync(
                    'OpenUri', GLib.Variant('(s)', (uri,)), 0, -1, None)
                player.Play()
                success = True
            except GLib.GError as exception:
                sys.stderr.write("WARNING: DLNA failed: %s\n" % str(exception))
                sleep(1)
                pass

    def show(self, video):
        uri = self.video_server.get_url(video)
        # My Panasonic Viera TV is buggy.  It forgets the 16:9 overscan setting
        # when entering DLNA mode so play twice so second-time round it will
        # already be in DLNA mode:
        self.play_uri(uri)
        sleep(1)
        self.play_uri(uri)

    def stop(self):
        player = self.get_renderer_by_friendly_name(self.friendly_name)
        # Dleyna is very buggy, need to do this in a loop until it succeeds!
        success = False
        while not success:
            try:
                player.Stop()
                success = True
            except Exception:
                sleep(1)


class _AssumeTvDriver(object):
    def show(self, filename):
        sys.stderr.write("Assuming video %s is playing\n")

    def stop(self):
        sys.stderr.write("Assuming videos are no longer playing\n")


class _FakeTvDriver(object):
    """TV driver intended to be paired up with fake-video-src.py from the test
    directory"""
    def __init__(self, control_pipe, video_server):
        self.control_pipe = open(control_pipe, 'w')
        self.video_server = video_server

    def show(self, video):
        uri = self.video_server.get_url(video)
        self.control_pipe.write("%s\n" % uri)
        self.control_pipe.flush()
        # TODO: Add back-channel from stbt-camera-calibrate to find out when
        # the video actually changes.
        sleep(1)

    def stop(self):
        self.control_pipe.write("stop\n")
        self.control_pipe.flush()


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
    argparser.add_argument(
        "--tv-driver",
        help="Determines how to display videos on TV.\n\n"
             "    manual - Prompt the user then wait for confirmation.\n"
             "    assume - Assume the video is already playing (useful for "
             "scripting when passing a single test to be run).\n"
             "    dlna:[Friendly name] - Use DLNA.\n"
             "    fake:pipe_name - Used for testing",
             default=get_config("camera", "tv_driver", "manual"))


def create_from_args(args, video_generator):
    desc = args.tv_driver
    video_server = _HTTPVideoServer(
        video_generator,
        video_format=get_config('camera', 'video_format'))
    if desc == 'assume':
        return _AssumeTvDriver()
    elif desc.startswith('dlna:'):
        return _DleynaDriver(desc[5:], video_server)
    elif desc.startswith('fake:'):
        return _FakeTvDriver(desc[5:], video_server)
    elif desc == 'manual':
        return _ManualTvDriver(video_server)
    else:
        raise RuntimeError("Unknown video driver requested: %s" % desc)
