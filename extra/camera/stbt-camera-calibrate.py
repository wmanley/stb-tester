#!/usr/bin/python -u
# Encoding: utf-8

import argparse
from collections import namedtuple
from contextlib import contextmanager
import cv2
import math
import numpy
import pprint
import sys
from itertools import count, izip
import time
import tv_driver
import string
import subprocess
import gst_utils
from gi.repository import Gst
from gi.repository import GObject, GLib, Gst
from os.path import abspath, dirname

try:
    import stbt
except ImportError:
    sys.path.insert(0, dirname(abspath(__file__)) + '/../..')
    import stbt

###
### Geometric calibration
###

geometric_videos = [
    ('chessboard', lambda filename, *args, **kwargs: gst_utils.png2mp4(
        '%s/chessboard-720p-40px-border-white.png' % dirname(__file__),
        filename, *args, **kwargs))]

arrows = list(u'→↗↑↖←↙↓↘')
def off_to_arrow(off):
    u"""
    >>> print off_to_arrow((1, 1))
    ↗
    >>> print off_to_arrow((-1, 0))
    ←
    """
    if numpy.linalg.norm(off) > 0.5:
        angle = math.atan2(off[1], off[0])
        return arrows[int(angle/2/math.pi*len(arrows)+len(arrows)+0.5)
                      % len(arrows)]
    else:
        return u'O'


# ANSI colour codes for printing progress.
OKGREEN = '\033[92m'
WARNING = '\033[93m'
FAIL = '\033[91m'
ENDC = '\033[0m'
BOLD = '\033[1m'


def rate(r):
    """How good is the match on a scale of 0-2?"""
    if r < 0.5:
        return 2
    elif r < 5:
        return 1
    else:
        return 0

def print_error_map(outstream, ideal_points, measured_points):
    oldx = 0.0
    outstream.write(
        BOLD + "Geometric Calibration Report:\n" + ENDC +
        "\n"
        "    Legend:\n"
        "        " + OKGREEN + "O" + ENDC + " - Pixel perfect\n"
        "        " + WARNING + "↗" + ENDC + " - Off by up-to 5 pixels\n"
        "        " + FAIL + "↗" + ENDC + " - Off by more than 5 pixels\n"
        "\n")
    for ideal, measured in sorted(zip(ideal_points, measured_points),
                                  key=lambda a: (-a[0][1], a[0][0])):
        if ideal[0] < oldx:
            outstream.write('\n')
        off = ideal - measured
        outstream.write(
            (u"%s%s" % ([FAIL, WARNING, OKGREEN][rate(numpy.linalg.norm(off))],
                        off_to_arrow(off)))
            .encode('utf-8'))
        oldx = ideal[0]
    outstream.write("\n" + ENDC)


def validate_transformation(measured_points, ideal_points, transformation):
    """Use the created homography matrix on the measurements to see how well
    they map"""
    print_error_map(
        sys.stderr, ideal_points,
        [z[0] for z in transformation(measured_points)])


def build_remapping(reverse_transformation_fn, res):
    a = numpy.zeros((res[1], res[0], 2), dtype=numpy.float32)
    for x in range(0, res[0]):
        for y in range(0, res[1]):
            a[y][x][0] = x
            a[y][x][1] = y
    return reverse_transformation_fn(a)


ReversibleTransformation = namedtuple(
    'ReversibleTransformation', 'do reverse describe')


def calculate_distortion(ideal, measured_points, resolution):
    ideal_3d = numpy.array([[[x, y, 0]] for x, y in ideal],
                           dtype=numpy.float32)
    retval, cameraMatrix, distCoeffs, rvecs, tvecs = cv2.calibrateCamera(
        [ideal_3d], [measured_points], resolution)

    def undistort(points):
        return cv2.undistortPoints(points, cameraMatrix, distCoeffs)
    def distort(points):
        origshape = points.shape
        points = points.reshape((-1, 2))
        points_3d = numpy.zeros((len(points), 3))
        points_3d[:,0:2] = points
        return cv2.projectPoints(points_3d, (0,0,0), (0,0,0),
                                 cameraMatrix, distCoeffs)[0]
    def describe():
        return [
            ('camera-matrix',
             ' '.join([ ' '.join([repr(v) for v in l]) for l in cameraMatrix ])),
            ('distortion-coefficients',
             ' '.join([ repr(x) for x in distCoeffs[0]]))]
    return ReversibleTransformation(undistort, distort, describe)


def calculate_perspective_transformation(ideal, measured_points):
    ideal_2d = numpy.array([[[x, y]] for x, y in ideal],
                           dtype=numpy.float32)
    mat, _ = cv2.findHomography(measured_points, ideal_2d)
    def transform_perspective(points):
        return cv2.perspectiveTransform(points, mat)
    def untransform_perspective(points):
        return cv2.perspectiveTransform(points, numpy.linalg.inv(mat))
    def describe():
        return [('homography-matrix',
                 ' '.join([ ' '.join([repr(x) for x in l]) for l in mat]))]
    return ReversibleTransformation(
        transform_perspective, untransform_perspective, describe)


def _find_chessboard(appsink, timeout=10):
    sys.stderr.write("Searching for chessboard\n")
    success = False
    endtime = time.time() + timeout
    while not success and time.time() < endtime:
        input_image = stbt.gst_to_opencv(appsink.emit("pull-sample"))
        success, corners = cv2.findChessboardCorners(
            input_image, (29, 15), flags=cv2.cv.CV_CALIB_CB_ADAPTIVE_THRESH)

    if success:
        # Refine the corner measurements (not sure why this isn't built into
        # findChessboardCorners?
        grey_image = cv2.cvtColor(input_image, cv2.COLOR_BGR2GRAY)
        cv2.cornerSubPix(grey_image, corners, (5, 5), (-1, -1),
                         (cv2.TERM_CRITERIA_COUNT, 100, 0.1));

        # Chessboard could have been recognised either way up.  Match it.
        if corners[0][0][0] < corners[1][0][0]:
            ideal = numpy.array(
                [[x*40 - 0.5, y*40 - 0.5]
                 for y in range(2, 17) for x in range(2, 31)],
                dtype=numpy.float32)
        else:
            ideal = numpy.array(
                [[x*40 - 0.5, y*40 - 0.5]
                 for y in range(16, 1, -1) for x in range(30, 1, -1)],
                dtype=numpy.float32)

        return ideal, corners
    else:
        raise RuntimeError("Couldn't find Chessboard")


def geometric_calibration(tv, interactive=True):
    if interactive:
        raw_input("Please line up camera and press <ENTER> when ready")
    tv.show('chessboard')

    sys.stdout.write("Performing Geometric Calibration\n")

    undistorted_appsink = \
        stbt._display.source_pipeline.get_by_name('undistorted_appsink')
    ideal, corners = _find_chessboard(undistorted_appsink)

    undistort = calculate_distortion(ideal, corners, (1920, 1080))
    unperspect = calculate_perspective_transformation(
        ideal, undistort.do(corners))

    watchplane = stbt._display.source_pipeline.get_by_name(
        'geometric_correction')
    watchplane_params = undistort.describe() + unperspect.describe()
    for key, value in watchplane_params:
        watchplane.set_property(key, value)

    validate_transformation(
        corners, ideal, lambda points: unperspect.do(undistort.do(points)))

    stbt._set_config('global', 'watchplane_params',
                     ' '.join('%s="%s"' % v for v in watchplane_params))

###
### Colour Measurement
###

def generate_colours_video():
    import random
    template_svg = open(dirname(__file__) + '/colours.svg', 'r').read()
    for n in range(0, 10*60*8):
        svg = template_svg.replace(
            '#c0ffee', '#%06x' % random.randint(0, 256**3))
        yield (svg, 1.0/8*Gst.SECOND)

colour_measurement_videos = [
    ('colours', lambda filename, *args, **kwargs: gst_utils.generate_svg_video(
                    filename, generate_colours_video(), *args, **kwargs))]


def analyse_colours_video(number=None):
    """RGB!"""
    errors_in_a_row=0
    n=0
    while number is None or n < number:
        colour_hex = ''
        n = n + 1
        frame = stbt.get_frame()
        colour_hex = stbt.ocr(frame, stbt.Region(360, 60, 560, 110),
                              stbt.OcrMode.SINGLE_LINE)
        colour_hex = colour_hex.replace('O', '0').replace('l', '1')

        if (len(colour_hex) >= 7 and colour_hex[0] == '#' and
                all(c in string.hexdigits for c in colour_hex[1:7])):
            desired = numpy.array((
                int(colour_hex[1:3], 16),
                int(colour_hex[3:5], 16),
                int(colour_hex[5:7], 16)))
            colour = cv2.mean(frame[240:480,520:760])
            colour = (colour[2], colour[1], colour[0])
            yield (n, desired, colour)
            errors_in_a_row = 0
        else:
            errors_in_a_row += 1
            if errors_in_a_row > 50:
                raise RuntimeError(
                    "Failed to find hexidecimal colour description")


def avg_colour(colours):
    n = len(colours)
    return (
        sum([c[0] for c in colours])/n,
        sum([c[1] for c in colours])/n,
        sum([c[2] for c in colours])/n)


example_v4l2_ctl_output = """\
                     brightness (int)    : min=-64 max=64 step=1 default=15 value=15
                       contrast (int)    : min=0 max=95 step=1 default=30 value=30
"""

def v4l2_ctls(device, data=None):
    """
    >>> pprint.pprint(dict(v4l2_ctls(None, example_v4l2_ctl_output)))
    {'brightness': {'default': '15',
                    'max': '64',
                    'min': '-64',
                    'step': '1',
                    'value': '15'},
     'contrast': {'default': '30',
                  'max': '95',
                  'min': '0',
                  'step': '1',
                  'value': '30'}}
    """
    if data == None:
        data = subprocess.check_output(['v4l2-ctl', '-d', device, '-l'])
    for line in data.split('\n'):
        vals = line.strip().split()
        if vals == []:
            continue
        yield (vals[0], dict([v.split('=', 2) for v in vals[3:]]) )


def pop_with_progress(iterator, total, width=20, stream=sys.stderr):
    stream.write('\n')
    for n, v in izip(range(0, total), iterator):
        progress = (n * width) // total
        stream.write(
            '[%s] %8d / %d\r' % (
                '#' * progress + ' ' * (width - progress), n, total))
        yield v
    n += 1
    stream.write('\r' + ' ' * (total + 28) + '\r')


COLOUR_SAMPLES = 50


def fit_fn(ideals, measureds):
    """
    >>> f = fit_fn([120 , 240, 150, 18, 200], [0, 0, 0, 0, 0])
    >>> print f(0), f(56)
    [0, 0, 0, 0, 0]
    """
    from scipy.optimize import curve_fit
    from scipy.interpolate import interp1d
    POINTS = 5
    xs = [n * 255.0 / (POINTS + 1) for n in range(0, POINTS + 2)]
    def fn(x, ys):
        return interp1d(xs, numpy.array([0] + ys + [0]))(x)

    ys, _ = curve_fit(lambda x, *args: fn(x, list(args)), ideals, measureds,
                   [0.0] * POINTS)
    return interp1d(xs, numpy.array([0] + ys.tolist() + [0]))


@contextmanager
def colour_graph():
    try:
        from matplotlib import pyplot
        from scipy.optimize import curve_fit
        from scipy.interpolate import interp1d
    except ImportError:
        sys.stderr.write("Install matplotlib and scipy for graphical "
                         "assistance with colour calibration\n")
        yield lambda: None
        return

    from matplotlib import pyplot
    sys.stderr.write('Analysing colours...\n')
    pyplot.ion()

    comparison = []
    ideals = [[], [], []]
    deltas = [[], [], []]

    pyplot.figure()

    def update():
        pyplot.cla()
        pyplot.axis([0, 255, -128, 128])
        pyplot.ylabel("Error (higher means too bright)")
        pyplot.xlabel("Ideal colour")
        pyplot.grid()

        delta = [0, 0, 0]
        for n, ideal, measured in pop_with_progress(analyse_colours_video(), 50):
            pyplot.draw()
            for c in [0, 1, 2]:
                ideals[c].append(ideal[c])
                delta[c] = measured[c] - ideal[c]
                deltas[c].append(delta[c])
            pyplot.plot([ideal[0]], [delta[0]], 'rx',
                        [ideal[1]], [delta[1]], 'gx',
                        [ideal[2]], [delta[2]], 'bx')

        fits = [fit_fn(ideals[n], deltas[n]) for n in [0, 1, 2]]
        pyplot.plot(range(0, 256), [fits[0](x) for x in range(0, 256)], 'r-',
                    range(0, 256), [fits[1](x) for x in range(0, 256)], 'g-',
                    range(0, 256), [fits[2](x) for x in range(0, 256)], 'b-')
        pyplot.draw()

    yield update
    pyplot.close()


def _can_show_graphs():
    try:
        from matplotlib import pyplot
        from scipy.optimize import curve_fit
        from scipy.interpolate import interp1d
        return True
    except ImportError:
        sys.stderr.write("Install matplotlib and scipy for graphical "
                         "assistance with colour calibration\n")
        return False


def adjust_levels(tv):
    show_graphs = _can_show_graphs()
    tv.show("colours")
    happy = "no"
    device = stbt.get_config('global', 'v4l2_device')
    with colour_graph() as update_graph:
        while not happy.startswith('y'):
            update_graph()

            # Allow adjustment
            subprocess.check_call(['v4l2-ctl', '-d', device, '-L'])
            cmd = raw_input("Happy? [Y/n/set] ").strip().lower()
            if cmd.startswith('set'):
                _, var, val = cmd.split()
                subprocess.check_call(
                    ['v4l2-ctl', '-d', device, "-c", "%s=%s" % (var, val)])
            if cmd.startswith('y') or cmd == '':
                break

    stbt._set_config('global', 'v4l2_ctls', ','.join(
        ["%s=%s" % (c, a['value']) for c, a in dict(v4l2_ctls(device)).items()]))


###
### Uniform Illumination
###

FRAME_AVERAGE_COUNT=16

def generate_blank_video(colour, filename, *args, **kwargs):
    pixel = bytearray((colour[2], colour[1], colour[0]))
    return gst_utils.generate_svg_video(
        filename, [(pixel*1280*720, 60 * Gst.SECOND)],
        caps='video/x-raw,format=BGR,width=1280,height=720', *args, **kwargs)

illumination_videos = [
    ('blank-white', lambda *args, **kwargs:
        generate_blank_video((0xff, 0xff, 0xff), *args, **kwargs)),
    ('blank-black', lambda *args, **kwargs:
        generate_blank_video((0x0, 0x0, 0x0), *args, **kwargs)),
]

def _create_reference_png(filename):
    # Throw away some frames to let everything settle
    zip(range(0, 50), stbt.frames())

    average = None
    for n, frame in izip(range(0, FRAME_AVERAGE_COUNT), stbt.frames()):
        if average is None:
            average = numpy.zeros(shape=frame[0].shape, dtype=numpy.uint16)
        average += frame[0]
    average /= n+1
    cv2.imwrite(filename, numpy.array(average, dtype=numpy.uint8))


def calibrate_illumination(tv):
    img_dir = stbt._xdg_config_dir() + '/stbt/'

    props = {
        'white-reference-image': '%s/vignetting-reference-white.png' % img_dir,
        'black-reference-image': '%s/vignetting-reference-black.png' % img_dir,
    }

    tv.show("blank-white")
    _create_reference_png(props['white-reference-image'])
    tv.show("blank-black")
    _create_reference_png(props['black-reference-image'])

    vignettecorrect = stbt._display.source_pipeline.get_by_name(
        'illumination_correction')
    for k, v in reversed(props.items()):
        vignettecorrect.set_property(k, v)
    stbt._set_config(
        'global', 'vignettecorrect_params',
        ' '.join(["%s=%s" % (k, v) for k, v in props.items()]))


###
### Colours
###

BIN_SIZE=16

ColourRGB = namedtuple('ColourRGB', 'r g b')

CENTRE = 0
LOWER = 1
UPPER = 2
COUNT = 3


def histogram(data, bucket_size, length):
    buckets = [[0, 0, 0, 0]] * (length//bucket_size + 1)
    for n in range(0, length//bucket_size + 1):
        buckets[n] = [(n+0.5) * bucket_size, n * bucket_size, (n+1) * bucket_size, 0]
    for x in data:
        buckets[int(x//bucket_size)][3] += 1
    return buckets


def cumulate(data):
    x=0
    for y in data:
        x+=y[3]
        yield y[0:3] + [x]


def plot_histogram(data, style):
    hist = list(cumulate(histogram(data, BIN_SIZE, 256)))
    total = hist[-1][COUNT]
    pylab.plot([x[0] for x in hist], [x[3]/total for x in hist], style)

def plot_difference(a, b, style):
    hista = list(cumulate(histogram(a, BIN_SIZE, 256)))
    histb = list(cumulate(histogram(b, BIN_SIZE, 256)))
    pylab.plot([x[0] for x in hista], [a_[3] - b_[3] for a_, b_ in zip(hista, histb)], style)


def percentile_to_val(cumhist, percentile):
    assert percentile >=0 and percentile <= 1.0
    ch = [x[3] for x in cumhist]
    v = cumhist[-1][COUNT] * percentile
    p = bisect_left(ch, v)

    if p == 0:
        left = [-cumhist[0][UPPER]/2, -cumhist[0][UPPER], 0, 0]
    else:
        left = cumhist[p - 1]

    if p == len(cumhist):
        right = [cumhist[-1][UPPER], cumhist[-1][UPPER],
                 cumhist[-1][UPPER] + BIN_SIZE, cumhist[-1][COUNT]]
    else:
        right = cumhist[p]

    if right[COUNT] == left[COUNT]:
        binpct = 0.5
    else:
        binpct = (v - left[COUNT]) / (right[COUNT] - left[COUNT])
    return (left[UPPER] +
            binpct * (right[UPPER] - left[UPPER]))


def val_to_percentile(cumhist, val):
    n = int(val//BIN_SIZE)
    right = cumhist[n]
    if n > 0:
        left = cumhist[n - 1]
    else:
        left = [-cumhist[0][UPPER]/2, -cumhist[0][UPPER], 0, 0]
    assert(val >= right[LOWER] and val < right[UPPER])
    val_pct = (float(val) - right[LOWER]) / (right[UPPER] - right[LOWER])
    v = left[COUNT] + val_pct * (right[COUNT] - left[COUNT])
    pct = v/cumhist[-1][COUNT]
    assert pct >= 0 and pct <= 1.0
    return pct


def correct(cumhista, cumhistb, val):
    percentile = val_to_percentile(cumhista, val)
    return percentile_to_val(cumhistb, percentile)



def test_histogram_correction_identity():
    from nose.tools import eq_
    cumhist = list(cumulate(histogram(range(0,256), BIN_SIZE, 256)))
    for percentile in [x/256 for x in range(0,256)]:
        val = percentile_to_val(cumhist, percentile)
        eq_(val, percentile*256)
        eq_(percentile, val_to_percentile(cumhist, val))
    for val in range(0,256):
        percentile = val_to_percentile(cumhist, val)
        eq_(val/256, percentile)
        eq_(val, percentile_to_val(cumhist, percentile))


def frange(start, stop, step=1.0):
    n=0
    if step > 0:
        while start + n*step < stop:
            yield start + n*step
            n += 1
    else:
        raise NotImplementedError()


def test_histogram_correction_requiring_mapping():
    from nose.tools import eq_
    cumhist1 = list(cumulate(histogram(frange(0, 256, 1/3), BIN_SIZE, 256)))
    cumhist2 = list(cumulate(histogram(frange(128, 256, 1/4), BIN_SIZE, 256)))
    for val1, val2 in zip(frange(0, 256), frange(128, 256, 0.5)):
        eq_(val1, correct(cumhist2, cumhist1, val2))


def test_histogram_correction_non_linear():
    from nose.tools import eq_
    cumhist1 = list(cumulate(histogram(frange(0, 256, 1/3), BIN_SIZE, 256)))

    data = list(frange(0, 64, 0.5)) + list(frange(192, 256, 0.5))
    cumhist2 = list(cumulate(histogram(data, BIN_SIZE, 256)))
    for val1, val2 in zip(frange(0, 128), frange(0, 64, 0.5)):
        eq_(val1, correct(cumhist2, cumhist1, val2))
    for val1, val2 in zip(frange(128, 256), frange(192, 256, 0.5)):
        eq_(val1, correct(cumhist2, cumhist1, val2))


def main_calib_colours(argv):
    tv.show('colours')
    data = analyse_colours_video(50)

    IDEAL = 0
    MEASURED = 1
    CORRECTED = 2
    RED = 0
    GREEN = 1
    BLUE = 2

    hists = [[[None], [None], [None]], [[None], [None], [None]]]
    for is_ideal in [IDEAL, MEASURED]:
        for colour in [RED, GREEN, BLUE]:
            hists[is_ideal][colour] = list(cumulate(histogram(
                [x[is_ideal+1][colour] for x in data], BIN_SIZE, 256)))

    pylab.xlabel('Value')
    pylab.ylabel('Frequency')

    for c in [RED, GREEN, BLUE]:
        pylab.plot(range(0, 256, BIN_SIZE), [hists[MEASURED][c][x//BIN_SIZE][3] for x in range(0,256, BIN_SIZE)], '%s.' % 'rgb'[c])
        pylab.plot(range(0, 256, BIN_SIZE), [hists[IDEAL][c][x//BIN_SIZE][3] for x in range(0,256, BIN_SIZE)], '%s.' % 'rgb'[c])
        pylab.plot(range(0, 256), [x - correct(hists[MEASURED][c], hists[IDEAL][c], x) for x in range(0,256)], '%s-' % 'rgb'[c])

    pylab.axis([0, 256, -128, 128])
    pylab.show()

    if args.print_corrections:
        for x in range(0, 256):
            args.print_corrections.write(
                "%i\t%i\t%i\t%i\n" % (x,
                correct(hists[MEASURED][RED], hists[IDEAL][RED], x) - x,
                correct(hists[MEASURED][GREEN], hists[IDEAL][GREEN], x) - x,
                correct(hists[MEASURED][BLUE], hists[IDEAL][BLUE], x) - x))
    if args.print_corrected:
        for n, i, m in data:
            c = (correct(hists[MEASURED][RED], hists[IDEAL][RED], m[RED]),
                 correct(hists[MEASURED][GREEN], hists[IDEAL][GREEN], m[GREEN]),
                 correct(hists[MEASURED][BLUE], hists[IDEAL][BLUE], m[BLUE]))
            args.print_corrected.write("\t".join([repr(x) for x in (n,) + i + m + c]) + "\n")


def calibrate_colours(tv):
    pass

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
    from gi.repository import GUdev
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
            camera_pipeline = uvcvideosrc
        else:
            camera_pipeline = v4l2videosrc

        yield (name, dev_file, camera_pipeline)


def setup():
    if (stbt.get_config('global', 'camera_pipeline', '') == ''
            or stbt.get_config('global', 'v4l2_device', '') == ''):
        # Select a new camera TODO: Make this interactive
        sys.stderr.write(
            'No camera configured in stbt.conf please add parameters '
            '"v4l2_device" and "camera_pipeline" to section [global] of '
            'stbt.conf.\n\n')
        cameras = list(list_cameras())
        if len(cameras) == 0:
            sys.stderr.write("No Cameras Detected\n\n")
        else:
            sys.stderr.write("Detected cameras:\n\n")
        for n, (name, dev_file, camera_pipeline) in zip(count(1), cameras):
            sys.stderr.write(
                "    %i. %s\n"
                "\n"
                "        v4l2_device = %s\n"
                "        camera_pipeline = %s\n\n"
                % (n, name, dev_file, camera_pipeline))
        return False
    return True

###
### main
###

defaults = {
    'histogram_correction': '',
    'vignettecorrect_params': '',
    'v4l2_ctls':
        'brightness=128,contrast=128,saturation=128,'
        'white_balance_temperature_auto=0,gain=40,'
        'white_balance_temperature=6500,backlight_compensation=0,'
        'exposure_auto=1,exposure_absolute=152,focus_auto=0,focus_absolute=0,'
        'power_line_frequency=1',
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
    'source_pipeline':
        '%(camera_pipeline)s ! queue2 max-size-buffers=0 max-size-bytes=0 '
        'max-size-time=0 ! decodebin ! videoconvert ! tee name="raw_undistorted" ! '
        'queue leaky=upstream name="geometric" max-size-buffers=2 ! videoconvert ! stbtwatchplane '
        'name=geometric_correction qos=false %(watchplane_params)s '
        '! queue name="vignetting" max-size-buffers=2 ! stbtvignettecorrect name=illumination_correction %(vignettecorrect_params)s '
        '! queue name="histogram" max-size-buffers=2 ! stbthistogramcorrect %(histogram_correction)s',
}

def main(argv):
    # FIXME: This has side-effects on disk so calling stbt camera calibrate
    # *will actually affect* your stbt.conf!
    for k, v in defaults.iteritems():
        stbt._set_config('global', k, v)

    # Need to do this before we set up the argparser as it will affect the
    # default values it reports.
    if '--skip-geometric' not in argv:
        stbt._set_config('global', 'watchplane_params', '')

    parser = stbt.argparser()
    tv_driver.add_argparse_argument(parser)
    parser.add_argument(
        '--noninteractive', action="store_false", dest="interactive",
        help="Don't prompt, assume default answer to all questions")
    parser.add_argument(
        '--skip-geometric', action="store_true",
        help="Don't perform geometric calibration")
    args = parser.parse_args(argv[1:])

    if not setup():
        return 1

    source_pipeline = args.source_pipeline + (
        ' ! identity name=output '
        'raw_undistorted. ! queue leaky=upstream ! textoverlay text="Capture from camera" ! '
            '%s '
        'raw_undistorted. ! videoconvert ! appsink drop=true sync=false '
            'qos=false max-buffers=1 caps="video/x-raw,format=BGR" '
            'name=undistorted_appsink '
        'output. ! identity') % args.sink_pipeline
    sink_pipeline = ('textoverlay text="After correction" ! ' +
                     args.sink_pipeline)

    stbt.init_run(source_pipeline, sink_pipeline, 'none', False,
                  False)

    tv = tv_driver.create_from_args(args, dict(geometric_videos +
                                               colour_measurement_videos +
                                               illumination_videos))

    if not args.skip_geometric:
        geometric_calibration(tv, interactive=args.interactive)
    if args.interactive:
        adjust_levels(tv)
    calibrate_illumination(tv)
    calibrate_colours(tv)

    if args.interactive:
        raw_input("Calibration complete.  Press <ENTER> to exit")
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
