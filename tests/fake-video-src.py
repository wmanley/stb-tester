#!/usr/bin/python -u

import sys
from gi.repository import Gst, GLib, Gio
import dbus
import gst_utils
import threading
import argparse

Gst.init([])

USE_SHMSRC = True
DEFAULT_URI = 'file:///home/william-manley/.cache/stbt/camera-video-cache/chessboard.mp4'

def main(argv):
    parser = argparse.ArgumentParser()
    parser.add_argument("--overlay", default=None, help="SVG overlay to apply to videos")
    parser.add_argument("socket", help="shmsrc socket")

    args = parser.parse_args(argv[1:])

    frame_bytes = 1280*720*3

    next_video = [DEFAULT_URI]

    def about_to_finish(playbin):
        playbin.set_property('uri', next_video[0])
        next_video[0] = DEFAULT_URI
        playbin.set_state(Gst.State.PLAYING)

    if args.overlay is None:
        overlay = 'identity'
    else:
        overlay = 'video/x-raw,format=BGRA ! rsvgoverlay location=%s' % args.overlay

    if USE_SHMSRC:
        pipeline_desc = ("""\
            playbin name=pb audio-sink=fakesink uri=%s flags=0x00000791 \
            video-sink="videoconvert ! %s ! videoconvert \
                ! video/x-raw,width=1280,height=720,format=RGB ! identity ! \
                shmsink wait-for-connection=true shm-size=%i max-lateness=-1 qos=false \
                        socket-path=%s blocksize=%i sync=true buffer-time=100000000" """ %
                        (DEFAULT_URI, overlay, frame_bytes*1000, args.socket,
                         frame_bytes))
    else:
        pipeline_desc = ("""
            playbin name=pb audio-sink=fakesink uri=%s flags=0x00000791 \
            video-sink="videoconvert ! timeoverlay ! xvimagesink sync=true" """
            % DEFAULT_URI)

    playbin = Gst.parse_launch(pipeline_desc)

    playbin.connect("about-to-finish", about_to_finish)

    runner = gst_utils.PipelineRunner(playbin)
    gst_thread = threading.Thread(target=runner.run)
    gst_thread.daemon = True
    gst_thread.start()

    playbin.get_state(0)

    def set_uri(uri):
        print "=== Setting URI to", uri
        if uri == 'stop':
            next_video[0] = DEFAULT_URI
        else:
            next_video[0] = uri
        playbin.seek(1.0,
            Gst.Format.TIME, Gst.SeekFlags.FLUSH | Gst.SeekFlags.KEY_UNIT,
            Gst.SeekType.END, 0, Gst.SeekType.NONE, 0)

    while True:
        uri = sys.stdin.readline()
        if uri == '':
            break
        elif len(uri.strip()) > 0:
            set_uri(uri.strip())


if __name__ == '__main__':
    sys.exit(main(sys.argv))
