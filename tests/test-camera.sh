# Run with ./run-tests.sh

###
### Fake Video Source - test infrastructure.
###

fake_video_src_source="\
    shmsrc do-timestamp=true is-live=true blocksize=2764800 \
    socket-path=gst-shm-socket ! \
    video/x-raw,format=BGR,width=1280,height=720,framerate=25/1 ! queue ! \
    videoconvert"

start_fake_video_src() {
    if [ -n "$FAKE_VIDEO_SRC_PID" ]; then
        echo "Restarting Fake video src"
        stop_fake_video_src
    else
        echo "Starting Fake video src"
    fi

    mkfifo uri_playlist
    while cat uri_playlist; do true; done | \
        "$testdir/fake-video-src.py" "$PWD/gst-shm-socket" &
    FAKE_VIDEO_SRC_PID=$!

    sed --in-place "s#^\s*camera_pipeline.*#camera_pipeline = shmsrc \
        do-timestamp=true is-live=true blocksize=2764800 \
        socket-path=$PWD/gst-shm-socket ! video/x-raw,format=BGR,width=1280,height=720,framerate=25/1 ! \
        videoconvert ! rsvgoverlay location=$1  ! videoscale ! videoconvert ! \
        video/x-raw,format=BGR,width=1920,height=1080#" config/stbt/stbt.conf
#    sed --in-place "s#source_pipeline.*#source_pipeline = shmsrc \
#        do-timestamp=true is-live=true blocksize=2764800 \
#        socket-path=$PWD/gst-shm-socket ! video/x-raw,format=BGR,width=1280,height=720,framerate=25/1 ! \
#        videoconvert #" config/stbt/stbt.conf
    if ! grep -q 'tv_driver =' config/stbt/stbt.conf; then
        printf "[camera]\ntv_driver = fake:uri_playlist\n" >>config/stbt/stbt.conf
    fi
}

fake_video_src_show() {
    echo "$1" >uri_playlist
}

stop_fake_video_src() {
    kill "$FAKE_VIDEO_SRC_PID"
    unset FAKE_VIDEO_SRC_PID
    rm uri_playlist gst-shm-socket
}
