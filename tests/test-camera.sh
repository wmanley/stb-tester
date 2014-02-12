# Run with ./run-tests.sh

stb_tester_logo_src_1080p="\
    videotestsrc pattern=solid-color \
    ! video/x-raw,width=1280,height=720 \
    ! rsvgoverlay location=$testdir/stb-tester-350px.svg x=465 y=210 \
    ! videoscale \
    ! video/x-raw,width=1920,height=1080 \
    ! videoconvert "

###
### stbtwatchplane tests
###

create_stb_tester_logo_template() {
    # Can't just use rsvgdec as it doesn't seem to respect the white background
    # colour in the svg
    gst-launch-1.0 videotestsrc pattern=solid-color \
                 ! video/x-raw,width=349,height=301 \
                 ! rsvgoverlay location="$testdir/stb-tester-350px.svg" \
                 ! videoconvert ! video/x-raw,format=RGB ! pngenc snapshot = true \
                 ! filesink location="stb-tester-350px.png"
}

test_that_stbtwatchplane_scales_by_default() {
    sed -e "s#source_pipeline =.*#source_pipeline = ${stb_tester_logo_src_1080p} ! stbtwatchplane#" \
        -e "s#control = test#control = none#" \
        "$testdir/stbt.conf" > stbt.conf &&

    create_stb_tester_logo_template &&
    echo 'wait_for_match("stb-tester-350px.png")' >test.py &&
    STBT_CONFIG_FILE="$scratchdir/stbt.conf" stbt-run -v test.py
}

# Properties to be passed to stbtwatchplane to flatten capture-logo.png.
# capture-logo.png was taken with a Logitech C920 webcam.
wp_matricies='
    camera-matrix="1491.1536435672558    0.0             929.63729425798135
                      0.0             1490.0565740887305 569.55885903330557
                      0.0                0.0               1.0"

    distortion-coefficients="0.12152211775145583 -0.28102519335279752
        0.00020128754517049412 3.738779032027093e-05 0.08124443207970744"

    homography-matrix="1337.9978689558545       -1.2281763921416602   636.39368178649374
                        -18.912787775602091   1237.5658408092195      398.39453388539317
                          0.10401610284561842   -0.080103205719775208   1.0"'
wp_props="$(echo "$wp_matricies" | tr '\n' ' ')"

test_that_stbtwatchplane_flattens_pictures_of_TVs() {
    sed -e "s#source_pipeline =.*#source_pipeline = uridecodebin uri=file://$testdir/capture-logo.png ! videoconvert ! imagefreeze ! stbtwatchplane $wp_props#" \
        -e "s#control = test#control = none#" \
        "$testdir/stbt.conf" > stbt.conf &&
    create_stb_tester_logo_template &&
    echo 'wait_for_match("stb-tester-350px.png",
                         match_parameters=MatchParameters(confirm_threshold=0.3))' >test.py &&
    STBT_CONFIG_FILE="$scratchdir/stbt.conf" stbt-run -v test.py
}

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

###
### stbt camera validate tests
###

run_validation() {
    color="$1"
    extra=${2:-identity}
    stbt-run \
        --source-pipeline="filesrc location=$testdir/$1.png ! pngdec ! videoconvert ! $extra ! video/x-raw,width=1280,height=720 ! imagefreeze" \
        --control=none \
        $srcdir/extra/camera/stbt-camera-validate.py --tv-driver=assume "$1"
}

test_that_validation_passes_on_pristine_input() {
    run_validation letters-bw "" || fail "Validation failed on pristine input"
}
test_that_validation_fails_if_letters_are_offset() {
    run_validation letters-bw "videobox top=-2 left=-2 ! \
                       videobox autocrop=true" \
        && fail "Validation succeeded on invalid input"
    return 0
}
test_that_validation_fails_if_letters_are_scaled_down() {
    run_validation letters-bw "videoscale ! video/x-raw,width=1278,height=718 ! \
                       videobox autocrop=true" \
        && fail "Validation succeeded on invalid input"
    return 0
}
test_that_validation_fails_if_letters_are_scaled_up() {
    run_validation letters-bw "videoscale ! video/x-raw,width=1282,height=722 ! \
                       videobox autocrop=true" \
        && fail "Validation succeeded on invalid input"
    return 0
}
test_that_validation_fails_with_vignetting() {
    run_validation letters-bw \
        "rsvgoverlay location=$testdir/vignette-overlay.svg" \
        && fail "Validation succeeded on invalid input"
    return 0
}

# Test manual driver

test_that_validation_video_served_over_http_is_correct() {
    # We test a lot of functionality in this test.  Arguably it should be split
    # down.  We test that:
    #
    # * HTTP URLs are provided.
    # * Videos can be played from those URLs.
    # * The videos are what stbt camera validate was expecting and thus that
    #   the videos have been generated on demand successfully.
    # * The validation code is hooked up to the drivers.
    # * The manual driver responds to user input (pressing <ENTER>).
    #
    # The setup looks like:
    #
    #  |-----------------|          video         |----------------------|
    #  | fakevideosrc.py | --- gst-shm-socket --> | stbt camera validate |
    #  |-----------------|                        |----------------------|
    #          ^ stdin                               ^ stdin        | stderr
    #          |                                     |         instructions
    #          |                            stbt_validate_input     |
    #          |                                     |              V
    #          |                                  |----------------------|
    #    uri_playlist ----------------------------|      this test       |
    #                                             |----------------------|
    #
    # The test listens for instructions from stbt camera validate's stderr and
    # instructs fakevideosrc.py to display URIs before telling stbt camera
    # validate to proceed by pressing enter on it's stdin
    start_fake_video_src

    mkfifo stbt_validate_input
    while cat stbt_validate_input; do true; done | \
        stbt run \
            --source-pipeline="$fake_video_src_source" \
            --control=none \
        $srcdir/extra/camera/stbt-camera-validate.py --driver=manual 2>&1 | (\
        while read line; do
            if [[ "$line" =~ 'http://' ]]; then
                fake_video_src_show "$(echo "$line" | grep -Eo 'http://\S*')"
            fi
            if [[ "$line" =~ 'Press <ENTER>' ]]; then
                sleep 1
                echo >stbt_validate_input
            fi
        done
    )

    stop_fake_video_src
}