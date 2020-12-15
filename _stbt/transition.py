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
from __future__ import unicode_literals
from __future__ import print_function
from __future__ import division
from __future__ import absolute_import
from builtins import *  # pylint:disable=redefined-builtin,unused-wildcard-import,wildcard-import,wrong-import-order

import enum

import cv2
import numpy

from .diff import FrameDiffer, MotionDiff, MotionResult
from .imgutils import (
    crop,
    load_mask,
    pixel_bounding_box,
    preload_mask,
    _validate_region)
from .logging import ddebug, debug, draw_on
from .types import Region


def press_and_wait(
        key, region=Region.ALL, mask=None, timeout_secs=10, stable_secs=1,
        min_size=None, _dut=None):

    """Press a key, then wait for the screen to change, then wait for it to stop
    changing.

    This can be used to wait for a menu selection to finish moving before
    attempting to OCR at the selection's new position; or to measure the
    duration of animations; or to measure how long it takes for a screen (such
    as an EPG) to finish populating.

    :param str key: The name of the key to press (passed to `stbt.press`).

    :param stbt.Region region: Only look at the specified region of the video
        frame.

    :param mask:
        A black & white image that specifies which part of the video frame to
        look at. White pixels select the area to analyse; black pixels select
        the area to ignore.

        This can be a string (a filename that will be resolved as per
        `load_image`) or a single-channel image in OpenCV format.

        If you specify ``region``, the mask must be the same size as the
        region. Otherwise the mask must be the same size as the frame.
    :type mask: str or `numpy.ndarray`

    :param timeout_secs: A timeout in seconds. This function will return a
        falsey value if the transition didn't complete within this number of
        seconds from the key-press.
    :type timeout_secs: int or float

    :param stable_secs: A duration in seconds. The screen must stay unchanged
        (within the specified region or mask) for this long, for the transition
        to be considered "complete".
    :type timeout_secs: int or float

    :param min_size: A tuple of ``(width, height)``, in pixels, for differences
        to be considered as "motion". Use this to ignore small differences,
        such as the blinking text cursor in a search box.
    :type min_size: Tuple[int, int]

    :returns:
        An object that will evaluate to true if the transition completed, false
        otherwise. It has the following attributes:

        * **key** (*str*) – The name of the key that was pressed.
        * **frame** (`stbt.Frame`) – If successful, the first video frame when
          the transition completed; if timed out, the last frame seen.
        * **status** (`stbt.TransitionStatus`) – Either ``START_TIMEOUT``,
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

    Changed in v32: Use the same difference-detection algorithm as
    `wait_for_motion`; ``region`` and ``mask`` can both be specified at the
    same time.
    """
    if _dut is None:
        import stbt_core
        _dut = stbt_core

    t = _Transition(region, mask, timeout_secs, stable_secs, min_size, _dut)
    press_result = _dut.press(key)
    debug("transition: %.3f: Pressed %s" % (press_result.end_time, key))
    result = t.wait(press_result)
    debug("press_and_wait(%r) -> %s" % (key, result))
    return result


press_and_wait.differ = MotionDiff


def wait_for_transition_to_end(
        initial_frame=None, region=Region.ALL, mask=None, timeout_secs=10,
        stable_secs=1, min_size=None, _dut=None):

    """Wait for the screen to stop changing.

    In most cases you should use `press_and_wait` to measure a complete
    transition, but if you need to measure several points during a single
    transition you can use `wait_for_transition_to_end` as the last
    measurement. For example::

        keypress = stbt.press("KEY_OK")  # Launch my app
        m = stbt.wait_for_match("my-app-home-screen.png")
        time_to_first_frame = m.time - keypress.start_time
        end = wait_for_transition_to_end(m.frame)
        time_to_fully_populated = end.end_time - keypress.start_time

    :param stbt.Frame initial_frame: The frame of video when the transition
        started. If `None`, we'll pull a new frame from the device under test.

    :param region: See `press_and_wait`.
    :param mask: See `press_and_wait`.
    :param timeout_secs: See `press_and_wait`.
    :param stable_secs: See `press_and_wait`.

    :returns: See `press_and_wait`.
    """
    if _dut is None:
        import stbt_core
        _dut = stbt_core

    t = _Transition(region, mask, timeout_secs, stable_secs, min_size, _dut)
    result = t.wait_for_transition_to_end(initial_frame)
    debug("wait_for_transition_to_end() -> %s" % (result,))
    return result


class _Transition(object):
    def __init__(self, region, mask, timeout_secs, stable_secs, min_size, dut):
        self.region = region
        self.mask = preload_mask(mask)

        self.timeout_secs = timeout_secs
        self.stable_secs = stable_secs
        self.min_size = min_size
        self.dut = dut

        self.frames = self.dut.frames()
        self.expiry_time = None

    def wait(self, press_result):
        self.expiry_time = press_result.end_time + self.timeout_secs

        differ = press_and_wait.differ(initial_frame=press_result.frame_before,
                                       region=self.region, mask=self.mask,
                                       min_size=self.min_size)
        # Wait for animation to start
        for f in self.frames:
            if f.time < press_result.end_time:
                # Discard frame to work around latency in video-capture pipeline
                continue
            motion_result = differ.diff(f)
            draw_on(f, motion_result, label="transition")
            if motion_result:
                _debug("Animation started", f)
                animation_start_time = f.time
                break
            _debug("No change", f)
            if f.time >= self.expiry_time:
                _debug(
                    "Transition didn't start within %s seconds of pressing %s",
                    f, self.timeout_secs, press_result.key)
                return _TransitionResult(
                    press_result.key, f, TransitionStatus.START_TIMEOUT,
                    press_result.end_time, None, None)

        end_result = self.wait_for_transition_to_end(f)  # pylint:disable=undefined-loop-variable
        return _TransitionResult(
            press_result.key, end_result.frame, end_result.status,
            press_result.end_time, animation_start_time, end_result.end_time)

    def wait_for_transition_to_end(self, initial_frame):
        if initial_frame is None:
            initial_frame = next(self.frames)
        if self.expiry_time is None:
            self.expiry_time = initial_frame.time + self.timeout_secs

        first_stable_frame = initial_frame
        differ = press_and_wait.differ(initial_frame=initial_frame,
                                       region=self.region, mask=self.mask,
                                       min_size=self.min_size)
        while True:
            f = next(self.frames)
            motion_result = differ.diff(f)
            draw_on(f, motion_result, label="transition")
            if motion_result:
                _debug("Animation in progress", f)
                first_stable_frame = f
            else:
                _debug("No change since previous frame", f)
            if f.time - first_stable_frame.time >= self.stable_secs:
                _debug("Transition complete (stable for %ss since %.3f).",
                       first_stable_frame, self.stable_secs,
                       first_stable_frame.time)
                return _TransitionResult(
                    None, first_stable_frame, TransitionStatus.COMPLETE,
                    None, initial_frame.time, first_stable_frame.time)
            if f.time >= self.expiry_time:
                _debug("Transition didn't end within %s seconds",
                       f, self.timeout_secs)
                return _TransitionResult(
                    None, f, TransitionStatus.STABLE_TIMEOUT,
                    None, initial_frame.time, None)


def _debug(s, f, *args):
    debug(("transition: %.3f: " + s) % ((getattr(f, "time", 0),) + args))


def _ddebug(s, f, *args):
    ddebug(("transition: %.3f: " + s) % ((getattr(f, "time", 0),) + args))


class StrictDiff(FrameDiffer):
    """The original `press_and_wait` algorithm."""

    def __init__(self, initial_frame, region=Region.ALL, mask=None,
                 min_size=None):
        self.prev_frame = initial_frame
        self.region = _validate_region(self.prev_frame, region)
        self.min_size = min_size

        if mask is not None:
            mask = load_mask(mask, shape=(
                self.region.height, self.region.width, 3))
        self.mask = mask

    def diff(self, frame):
        absdiff = cv2.absdiff(crop(self.prev_frame, self.region),
                              crop(frame, self.region))
        if self.mask is not None:
            absdiff = cv2.bitwise_and(absdiff, self.mask, absdiff)

        diffs_found = False
        out_region = None
        maxdiff = numpy.max(absdiff)
        if maxdiff > 20:
            diffs_found = True
            big_diffs = absdiff > 20
            out_region = pixel_bounding_box(big_diffs)
            _ddebug("found %s diffs above 20 (max %s) in %r", frame,
                    numpy.count_nonzero(big_diffs), maxdiff, out_region)
        elif maxdiff > 0:
            small_diffs = absdiff > 5
            small_diffs_count = numpy.count_nonzero(small_diffs)
            if small_diffs_count > 50:
                diffs_found = True
                out_region = pixel_bounding_box(small_diffs)
                _ddebug("found %s diffs <= %s in %r", frame, small_diffs_count,
                        maxdiff, out_region)
            else:
                _ddebug("only found %s diffs <= %s", frame, small_diffs_count,
                        maxdiff)

        if diffs_found:
            # Undo crop:
            out_region = out_region.translate(self.region)

        motion = diffs_found and (
            self.min_size is None or
            (out_region.width >= self.min_size[0] and
             out_region.height >= self.min_size[1]))

        if motion:
            # Only update the reference frame if we found differences. This
            # makes the algorithm more sensitive to slow motion.
            self.prev_frame = frame

        result = MotionResult(getattr(frame, "time", None), motion,
                              out_region, frame)
        return result


class _TransitionResult(object):
    def __init__(self, key, frame, status, press_time, animation_start_time,
                 end_time):
        self.key = key
        self.frame = frame
        self.status = status
        self.press_time = press_time
        self.animation_start_time = animation_start_time
        self.end_time = end_time

    def __repr__(self):
        return (
            "_TransitionResult(key=%r, frame=<Frame>, status=%s, "
            "press_time=%s, animation_start_time=%s, end_time=%s)" % (
                self.key,
                self.status,
                self.press_time,
                self.animation_start_time,
                self.end_time))

    def __str__(self):
        # Also lists the properties -- it's useful to see them in the logs.
        return (
            "_TransitionResult(key=%r, frame=<Frame>, status=%s, "
            "press_time=%s, animation_start_time=%s, end_time=%s, duration=%s, "
            "animation_duration=%s)" % (
                self.key,
                self.status,
                self.press_time,
                self.animation_start_time,
                self.end_time,
                self.duration,
                self.animation_duration))

    def __bool__(self):
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

    #: The transition didn't start (nothing moved).
    START_TIMEOUT = 0

    #: The transition didn't end (movement didn't stop).
    STABLE_TIMEOUT = 1

    #: The transition started and then stopped.
    COMPLETE = 2
