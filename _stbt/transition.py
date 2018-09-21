# coding: utf-8

"""Detection & frame-accurate measurement of animations and transitions.

For example a selection that moves from one menu item to another or loading a
new screen such as a Guide and waiting for it to populate fully.

Because we want these measurements to be frame-accurate, we don't do expensive
image processing, relying instead on diffs between successive frames.

Copyright 2017-2018 Stb-tester.com Ltd.
License: LGPL v2.1 or (at your option) any later version (see
https://github.com/stb-tester/stb-tester/blob/master/LICENSE for details).
"""

import time

import cv2
import enum
import numpy

from .core import load_image
from .logging import debug
from .types import Region


def press_and_wait(
        key, region=Region.ALL, mask=None, timeout_secs=10, stable_secs=1,
        _dut=None):

    """Press a key, then wait for the screen to change, then wait for it to stop
    changing.

    This should be used instead of ``press`` where possible.  Unlike ``press``,
    this function waits for and measures the effect of pressing the key.  This
    makes your test-scripts more robust and helps with performance measurements.

    Typically ``press_and_wait`` is used with `assert` to ensure that the
    device-under-test reacted to your keypress at all.  Example:

        assert press_and_wait('KEY_DOWN')

    will fail the test if no change is detected after pressing 'KEY_DOWN', or if
    the screen doesn't stop changing within `timeout_secs`.

    ``press_and_wait`` and transparency
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    ``press_and_wait`` waits for a lack of motion to determine when an animation
    has completed.  If your UI features a transparent background with video
    playing or picture-in-picture these areas should be ignored using the mask
    or region arguments.

    Example

    You have an opaque menu that appears on top of live TV on the right hand
    side:

    .. image:: supertv.jpg

    The motion from live TV is not relevant for navigating the menu so you
    specify a region that corresponds to the menu on the left.  This is the
    leftmost 400 pixels:

        MENU_REGION = stbt.Region(0, 0, 400, 720)
        assert press_and_wait('KEY_DOWN', region=MENU_REGION)

    The dogs programme can continue in the background and won't affect your
    measurements.

    ``press_and_wait`` and performance measurements
    ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

    ``press_and_wait`` can be used to measure the responsiveness of your UI and
    the duration of your animations.

    Example: Measuring EPG load time

    You want to press OK to open the Guide and measure how long it takes to
    populate:

        transition = press_and_wait('KEY_OK', timeout_secs=20, stable_secs=5)
        assert transition, "Guide didn't finish loading within 20s"

        print "Loading the guide took {duration} seconds".format(
            duration=transition.duration)

    `assert transition` will cause the test to fail if the device-under-test
    ignores the OK keypress, or if the EPG is still changing after the 20s
    timeout.  This ensures that the test is valid.

    We specify `stable_secs=5` here because there may be some time where the
    EPG is still loading and lacks motion, but still isn't fully loaded.  The
    1s default may not be long enough for an EPG to load it's data from the
    network for example.

    At the end of the test we print the time the EPG took to load.
    Alternatively you could log this time to a monitoring/logging system for
    live measurements of EPG performance - but this is outside the scope of this
    example.

    :param str key: The name of the key to press (passed to `stbt.press`).

    :param stbt.Region region: Only look at the specified region of the video
        frame.

    :param str mask: The filename of a black & white image that specifies which
        part of the video frame to look at. White pixels select the area to
        analyse; black pixels select the area to ignore. You can't specify
        ``region`` and ``mask`` at the same time.

    :param timeout_secs: A timeout in seconds. This function will return a
        falsey value if the transition didn't complete within this number of
        seconds from the key-press.
    :type timeout_secs: int or float

    :param stable_secs: A duration in seconds. The screen must stay unchanged
        (within the specified region or mask) for this long, for the transition
        to be considered "complete".

    :returns:
        An object that will evaluate to true if the transition completed, false
        otherwise. It has the following attributes:

        * **frame** (`stbt.Frame`) – If successful, the first video frame when
          the transition completed; if timed out, the last frame seen.
        * **status** (`TransitionStatus`) – Either ``START_TIMEOUT``,
          ``STABLE_TIMEOUT``, or ``COMPLETE``. If it's ``COMPLETE``, the whole
          object will evaluate as true.
        * **press_time** (*float*) – When the key-press completed.
        * **animation_start_time** (*float*) – When animation started after the
          key-press (or ``None`` if timed out).
        * **end_time** (*float*) – When animation completed (or ``None`` if
          timed out).
        * **duration** (*float*) – Time from ``press_time`` to ``end_time`` (or
          ``None`` if timed out).
        * **animation_duration** (*float*) – Time from ``animation_start_time``
          to ``end_time`` (or ``None`` if timed out).

        All times are measured in seconds since 1970-01-01T00:00Z; the
        timestamps can be compared with system time (the output of
        ``time.time()``).
    """

    t = _Transition(region, mask, timeout_secs, stable_secs, _dut)
    result = t.press_and_wait(key)
    debug("press_and_wait(%r) -> %s" % (key, result))
    return result


def wait_for_transition_to_end(
        initial_frame=None, region=Region.ALL, mask=None, timeout_secs=10,
        stable_secs=1, _dut=None):

    """Wait for the screen to stop changing.

    In most cases you should use `press_and_wait` to measure a complete
    transition, but if you need to measure several points during a single
    transition you can use `wait_for_transition_to_end` as the last
    measurement. For example::

        stbt.press("KEY_OK")  # Launch my app
        press_time = time.time()
        m = stbt.wait_for_match("my-app-home-screen.png")
        time_to_first_frame = m.time - press_time
        end = wait_for_transition_to_end(m.frame)
        time_to_fully_populated = end.end_time - press_time

    :param stbt.Frame initial_frame: The frame of video when the transition
        started. If `None`, we'll pull a new frame from the device under test.

    :param region: See `press_and_wait`.
    :param mask: See `press_and_wait`.
    :param timeout_secs: See `press_and_wait`.
    :param stable_secs: See `press_and_wait`.

    :returns: See `press_and_wait`.
    """
    t = _Transition(region, mask, timeout_secs, stable_secs, _dut)
    result = t.wait_for_transition_to_end(initial_frame)
    debug("wait_for_transition_to_end() -> %s" % (result,))
    return result


class _Transition(object):
    def __init__(self, region=Region.ALL, mask=None, timeout_secs=10,
                 stable_secs=1, dut=None):

        if dut is None:
            import stbt
            self.dut = stbt
        else:
            self.dut = dut

        if region is not Region.ALL and mask is not None:
            raise ValueError(
                "You can't specify region and mask at the same time")

        self.region = region
        self.mask_image = None
        if isinstance(mask, numpy.ndarray):
            self.mask_image = mask
        elif mask:
            self.mask_image = load_image(mask)

        self.timeout_secs = timeout_secs
        self.stable_secs = stable_secs

        self.frames = self.dut.frames()
        self.diff = strict_diff
        self.expiry_time = None

    def press_and_wait(self, key):
        original_frame = next(self.frames)
        self.dut.press(key)
        press_time = time.time()
        debug("transition: %.3f: Pressed %s" % (press_time, key))
        self.expiry_time = press_time + self.timeout_secs

        # Wait for animation to start
        for f in self.frames:
            if f.time < press_time:
                # Discard frame to work around latency in video-capture pipeline
                continue
            if self.diff(original_frame, f, self.region, self.mask_image):
                _debug("Animation started", f)
                animation_start_time = f.time
                break
            _debug("No change", f)
            if f.time >= self.expiry_time:
                _debug(
                    "Transition didn't start within %s seconds of pressing %s",
                    f, self.timeout_secs, key)
                return _TransitionResult(
                    f, TransitionStatus.START_TIMEOUT,
                    press_time, None, None)

        end_result = self.wait_for_transition_to_end(f)  # pylint:disable=undefined-loop-variable
        return _TransitionResult(
            end_result.frame, end_result.status,
            press_time, animation_start_time, end_result.end_time)

    def wait_for_transition_to_end(self, initial_frame):
        if initial_frame is None:
            initial_frame = next(self.frames)
        if self.expiry_time is None:
            self.expiry_time = initial_frame.time + self.timeout_secs

        f = first_stable_frame = initial_frame
        while True:
            prev = f
            f = next(self.frames)
            if self.diff(prev, f, self.region, self.mask_image):
                _debug("Animation in progress", f)
                first_stable_frame = f
            else:
                _debug("No change since previous frame", f)
            if f.time - first_stable_frame.time >= self.stable_secs:
                _debug("Transition complete (stable for %ss since %.3f).",
                       first_stable_frame, self.stable_secs,
                       first_stable_frame.time)
                return _TransitionResult(
                    first_stable_frame, TransitionStatus.COMPLETE,
                    None, initial_frame.time, first_stable_frame.time)
            if f.time >= self.expiry_time:
                _debug("Transition didn't end within %s seconds",
                       f, self.timeout_secs)
                return _TransitionResult(
                    f, TransitionStatus.STABLE_TIMEOUT,
                    None, initial_frame.time, None)


def _debug(s, f, *args):
    debug(("transition: %.3f: " + s) % ((f.time,) + args))


def strict_diff(f1, f2, region, mask_image):
    if region is not None:
        full_frame = Region(0, 0, f1.shape[1], f1.shape[0])
        region = Region.intersect(full_frame, region)
        f1 = f1[region.y:region.bottom, region.x:region.right]
        f2 = f2[region.y:region.bottom, region.x:region.right]

    absdiff = cv2.absdiff(f1, f2)
    if mask_image is not None:
        absdiff = cv2.bitwise_and(absdiff, mask_image, absdiff)

    return absdiff.any()


class _TransitionResult(object):
    def __init__(
            self, frame, status, press_time, animation_start_time, end_time):
        self.frame = frame
        self.status = status
        self.press_time = press_time
        self.animation_start_time = animation_start_time
        self.end_time = end_time

    def __repr__(self):
        return (
            "_TransitionResult(frame=<Frame>, status=%s, press_time=%s, "
            "animation_start_time=%s, end_time=%s)" % (
                self.status,
                self.press_time,
                self.animation_start_time,
                self.end_time))

    def __str__(self):
        # Also lists the properties -- it's useful to see them in the logs.
        return (
            "_TransitionResult(frame=<Frame>, status=%s, press_time=%s, "
            "animation_start_time=%s, end_time=%s, duration=%s, "
            "animation_duration=%s)" % (
                self.status,
                self.press_time,
                self.animation_start_time,
                self.end_time,
                self.duration,
                self.animation_duration))

    def __nonzero__(self):
        return self.status == TransitionStatus.COMPLETE

    @property
    def duration(self):
        if self.end_time is None or self.press_time is None:
            return None
        return self.end_time - self.press_time

    @property
    def animation_duration(self):
        if self.end_time is None or self.animation_start_time is None:
            return None
        return self.end_time - self.animation_start_time


class TransitionStatus(enum.Enum):
    START_TIMEOUT = 0
    STABLE_TIMEOUT = 1
    COMPLETE = 2
