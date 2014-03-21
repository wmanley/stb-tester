#!/usr/bin/python -u
# Encoding: utf-8

import argparse
import sys
from itertools import count
import tv_driver
from os.path import abspath, dirname

try:
    import stbt
except ImportError:
    sys.path.insert(0, dirname(abspath(__file__)) + '/../..')
    import stbt

videos = {}

###
### setup
###

uvcvideosrc = ('uvch264src device=%(v4l2_device)s name=src auto-start=true '
               'rate-control=vbr initial-bitrate=5000000 '
               'peak-bitrate=10000000 average-bitrate=5000000 '
               'v4l2src0::extra-controls="ctrls, %(v4l2_ctls)s" src.vidsrc ! '
               'video/x-h264,width=1920 ! h264parse')
v4l2videosrc = 'v4l2src device=%(v4l2_device)s extra-controls=%(v4l2_ctls)s'


def list_cameras():
    from gi.repository import GUdev  # pylint: disable=E0611
    client = GUdev.Client.new(['video4linux/usb_device'])
    devices = client.query_by_subsystem('video4linux')
    for d in devices:
        # Prefer to refer to a device by path.  This means that you are
        # referring to a particular USB port and is stable across reboots.
        dev_files = d.get_device_file_symlinks()
        path_dev_files = [x for x in dev_files if 'by-path' in x]
        dev_file = (path_dev_files + [d.get_device_file])[0]

        name = (d.get_property('ID_VENDOR_ENC').decode('string-escape') + ' ' +
                d.get_property('ID_MODEL_ENC').decode('string-escape'))

        if d.get_property('ID_USB_DRIVER') == 'uvcvideo':
            source_pipeline = uvcvideosrc
        else:
            source_pipeline = v4l2videosrc

        yield (name, dev_file, source_pipeline)


def setup(source_pipeline):
    if (source_pipeline == ''
            or stbt.get_config('global', 'v4l2_device', '') == ''):
        # Select a new camera TODO: Make this interactive
        sys.stderr.write(
            'No camera configured in stbt.conf please add parameters '
            '"v4l2_device" and "source_pipeline" to section [global] of '
            'stbt.conf.\n\n')
        cameras = list(list_cameras())
        if len(cameras) == 0:
            sys.stderr.write("No Cameras Detected\n\n")
        else:
            sys.stderr.write("Detected cameras:\n\n")
        for n, (name, dev_file, source_pipeline) in zip(count(1), cameras):
            sys.stderr.write(
                "    %i. %s\n"
                "\n"
                "        v4l2_device = %s\n"
                "        source_pipeline = %s\n\n"
                % (n, name, dev_file, source_pipeline))
        return False
    return True

###
### main
###

defaults = {
    'v4l2_ctls': (
        'brightness=128,contrast=128,saturation=128,'
        'white_balance_temperature_auto=0,white_balance_temperature=6500,'
        'gain=60,backlight_compensation=0,exposure_auto=1,'
        'exposure_absolute=152,focus_auto=0,focus_absolute=0,'
        'power_line_frequency=1'),
    # Notes on the source pipeline:
    # * We insert queues between the elements as they can each consume a fair
    #   amount of CPU time and the queues will allow them to be run on
    #   different CPUs.
    # * The queues are kept small to reduce the amount of slack (and thus the
    #   maximum latency) of the pipeline.
    # * We have an unbounded queue2 before the decodebin.  We don't want to
    #   drop encoded packets as this will cause significant image artifacts in
    #   the decoded buffers.  We make the assumption that we have enough
    #   horse-power to decode the incoming stream and any delays will be
    #   transient otherwise the queue2 could start filling up causing unbounded
    #   latency and memory usage!
}


def parse_args(argv):
    parser = stbt.argparser()
    tv_driver.add_argparse_argument(parser)
    parser.add_argument(
        '--noninteractive', action="store_false", dest="interactive",
        help="Don't prompt, assume default answer to all questions")
    return parser.parse_args(argv[1:])


def main(argv):
    args = parse_args(argv)

    if not setup(args.source_pipeline):
        return 1

    for k, v in defaults.iteritems():
        stbt._set_config('global', k, v)

    # Need to re-parse arguments as the settings above may have affected the
    # values we get out.
    args = parse_args(argv)

    transformation_pipeline = (
        'tee name=raw_undistorted '
        'raw_undistorted. ! queue leaky=upstream ! videoconvert ! '
        '    textoverlay text="Capture from camera" ! %s '
        'raw_undistorted. ! queue leaky=upstream max-size-buffers=1 ! %s' %
        (args.sink_pipeline,
         stbt.get_config('global', 'transformation_pipeline')))

    sink_pipeline = ('textoverlay text="After correction" ! ' +
                     args.sink_pipeline)

    stbt.init_run(args.source_pipeline, sink_pipeline, 'none', False,
                  False, transformation_pipeline)

    tv = tv_driver.create_from_args(args, videos)

    if args.interactive:
        raw_input("Calibration complete.  Press <ENTER> to exit")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
