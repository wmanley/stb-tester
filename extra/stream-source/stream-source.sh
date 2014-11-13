#!/bin/bash
#
# This is a simple means of streaming a GStreamer pipeline out to a web-browser
# using [RTMP] and  [FlowPlayer] flash.  Build the Docker container and run
# with:
#
#     make docker-build-stream-source
#     docker run -P stbtester/stream-source videotestsrc
#
# And visit http://localhost/ to view the video.
#
# To stream your currently configured source_pipeline run:
#
#     docker run --privileged -P stbtester/stream-source \
#         $(stbt config global.source_pipeline)
#
# [RTMP]: http://en.wikipedia.org/wiki/Real_Time_Messaging_Protocol
# [FlowPlayer]: http://flash.flowplayer.org/


CRTMPSERVER_CONFIG="$(dirname $0)/crtmpserver.lua"

crtmpserver --daemon "$CRTMPSERVER_CONFIG" || exit 1
gst-launch-1.0 "$@" ! fakesink num-buffers=1

# Low latency options chosen from http://x264dev.multimedia.cx/archives/249
low_latency_x264_opts="tune=zerolatency sliced-threads=true vbv-buf-capacity=0 rc-lookahead=0 key-int-max=30"

x264_encode="x264enc $low_latency_x264_opts b-adapt=false bframes=0 \
                  speed-preset=superfast"

vaapi_encode="vaapiencode_h264 keyframe-period=30 max-bframes=0 cpb-length=1 \
              ! h264parse config-interval=1"


( cd $(dirname $0) && python -m SimpleHTTPServer 80 ) &

ifconfig

exec gst-launch-1.0 "$@" ! videoconvert ! videoscale ! videorate \
        ! video/x-raw,format=I420,framerate=24/1,width=640,height=360 \
        ! $x264_encode \
        ! mpegtsmux ! tcpclientsink host=0.0.0.0 port=4953
