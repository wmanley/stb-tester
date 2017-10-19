from os.path import dirname

import cv2
import numpy

VIDEO = ('image/png', lambda: [(
    open('%s/chessboard-720p-40px-border-white.png' % dirname(__file__))
    .read(), 60e9)])


class NoChessboardError(Exception):
    pass


def calculate_calibration_params(frame):
    """
    Given an image of a chessboard (as generated by VIDEO) calculates the
    camera parameters to flatten the image.  Returns a dictionary of string to
    float with the keys:

    * fx, fy, cx, cy - The parameters of the camera matrix
    * k1, k2, p1, p2, k3 - The distortion parameters
    * ihm11, ihm12, ihm13, ihm21, ihm22, ihm23, ihm31, ihm32, ihm33 - The
      inverse homography projection matrix.

    If a chessboard cannot be found in frame this raises `NoChessboardError`.
    """
    ideal, corners = _find_chessboard(frame)
    resolution = (frame.shape[1], frame.shape[0])

    out = {}

    # Calculate distortion:
    ideal_3d = numpy.array([[[x, y, 0]] for x, y in ideal],
                           dtype=numpy.float32)
    _, cameraMatrix, distCoeffs, _, _ = cv2.calibrateCamera(
        [ideal_3d], [corners], resolution)

    out.update({
        'fx': cameraMatrix[0, 0],
        'fy': cameraMatrix[1, 1],
        'cx': cameraMatrix[0, 2],
        'cy': cameraMatrix[1, 2],

        'k1': distCoeffs[0, 0],
        'k2': distCoeffs[0, 1],
        'p1': distCoeffs[0, 2],
        'p2': distCoeffs[0, 3],
        'k3': distCoeffs[0, 4],
    })

    # Calculate perspective:
    undistorted_corners = cv2.undistortPoints(corners, cameraMatrix, distCoeffs)
    ideal_2d = numpy.array([[[x, y]] for x, y in ideal],
                           dtype=numpy.float32)
    mat, _ = cv2.findHomography(undistorted_corners, ideal_2d)
    ihm = numpy.linalg.inv(mat)

    for col in range(3):
        for row in range(3):
            out['ihm%i%i' % (col + 1, row + 1)] = ihm[row][col]

    return out


def find_corrected_corners(params, frame):
    """
    Used for validating the geometric calibration.  Given a set of camera
    parameters and an image of a chessboard this will return two lists, one of
    where the corners should be found and one where the corners were found
    (both after flattening has taken place).

    These lists of points can be compared to measure the effectiveness of the
    calibration.

    If a chessboard cannot be found in frame this raises `NoChessboardError`.
    """
    ideal, corners = _find_chessboard(frame)
    return ideal, _apply_geometric_correction(params, corners)


def _find_chessboard(input_image):
    success, corners = cv2.findChessboardCorners(
        input_image, (29, 15), flags=cv2.CALIB_CB_ADAPTIVE_THRESH)

    if not success:
        raise NoChessboardError()

    # Refine the corner measurements (not sure why this isn't built into
    # findChessboardCorners?
    grey_image = cv2.cvtColor(input_image, cv2.COLOR_BGR2GRAY)

    cv2.cornerSubPix(grey_image, corners, (5, 5), (-1, -1),
                     (cv2.TERM_CRITERIA_COUNT, 100, 0.1))

    # Chessboard could have been recognised either way up.  Match it.
    if corners[0][0][0] < corners[1][0][0]:
        ideal = numpy.array(
            [[x * 40 - 0.5, y * 40 - 0.5]
             for y in range(2, 17) for x in range(2, 31)],
            dtype=numpy.float32)
    else:
        ideal = numpy.array(
            [[x * 40 - 0.5, y * 40 - 0.5]
             for y in range(16, 1, -1) for x in range(30, 1, -1)],
            dtype=numpy.float32)

    return ideal, corners


def _apply_geometric_correction(params, points):
    # Undistort
    camera_matrix = numpy.array([[params['fx'], 0, params['cx']],
                                 [0, params['fy'], params['cy']],
                                 [0, 0, 1]])
    dist_coeffs = numpy.array(
        [params['k1'], params['k2'], params['p1'], params['p2'], params['k3']])
    points = cv2.undistortPoints(points, camera_matrix, dist_coeffs)

    # Apply perspective transformation:
    mat = numpy.array([[params['ihm11'], params['ihm21'], params['ihm31']],
                       [params['ihm12'], params['ihm22'], params['ihm32']],
                       [params['ihm13'], params['ihm23'], params['ihm33']]])
    return cv2.perspectiveTransform(points, numpy.linalg.inv(mat))[:, 0, :]