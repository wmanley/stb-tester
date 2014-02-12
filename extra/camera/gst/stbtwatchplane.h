/* stb-tester
 * Copyright (C) 2014 stb-tester.com Ltd. <will@williammanley.net>
 *
 * This library is free software; you can redistribute it and/or
 * modify it under the terms of the GNU Library General Public
 * License as published by the Free Software Foundation; either
 * version 2 of the License, or (at your option) any later version.
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 * Library General Public License for more details.
 *
 * You should have received a copy of the GNU Library General Public
 * License along with this library; if not, write to the
 * Free Software Foundation, Inc., 51 Franklin St, Fifth Floor,
 * Boston, MA 02110-1301, USA.
 */

#ifndef _STBT_WATCH_PLANE_H_
#define _STBT_WATCH_PLANE_H_

#include <gst/video/video.h>
#include <gst/video/gstvideofilter.h>

G_BEGIN_DECLS
#define STBT_TYPE_WATCH_PLANE   (stbt_watch_plane_get_type())
#define STBT_WATCH_PLANE(obj)   (G_TYPE_CHECK_INSTANCE_CAST((obj),STBT_TYPE_WATCH_PLANE,StbtWatchPlane))
#define STBT_WATCH_PLANE_CLASS(klass)   (G_TYPE_CHECK_CLASS_CAST((klass),STBT_TYPE_WATCH_PLANE,StbtWatchPlaneClass))
#define STBT_IS_WATCH_PLANE(obj)   (G_TYPE_CHECK_INSTANCE_TYPE((obj),STBT_TYPE_WATCH_PLANE))
#define STBT_IS_WATCH_PLANE_CLASS(obj)   (G_TYPE_CHECK_CLASS_TYPE((klass),STBT_TYPE_WATCH_PLANE))
typedef struct _StbtWatchPlane StbtWatchPlane;
typedef struct _StbtWatchPlaneClass StbtWatchPlaneClass;
typedef struct CvMat CvMat;

struct _StbtWatchPlane
{
  GstVideoFilter base_watchplane;

  GMutex props_mutex;

  /* Properties that describe the transformation.  See the OpenCV documentation
   * for more information.  These are used to create remapping below: */
  float camera_matrix[3][3];
  float distortion_coefficients[5];
  float homography_matrix[3][3];

  gboolean needs_regen;

  /* A 1280x720 array of (int16, int16) and a 1280x720 array of uint16 for use
   * by cvRemap.  Generated based on above properties.  We need two matricies
   * so cvRemap can use the faster fixed-point maths rather than floating
   * point.  See convertMaps for more information. */
  CvMat *remapping_int;
  CvMat *remapping_interpolation;
};

struct _StbtWatchPlaneClass
{
  GstVideoFilterClass base_watchplane_class;
};

GType stbt_watch_plane_get_type (void);

G_END_DECLS
#endif
