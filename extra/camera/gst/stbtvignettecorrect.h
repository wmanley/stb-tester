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

#ifndef _STBT_VIGNETTE_CORRECT_H_
#define _STBT_VIGNETTE_CORRECT_H_

#include <gst/video/video.h>
#include <gst/video/gstvideofilter.h>

G_BEGIN_DECLS
#define STBT_TYPE_VIGNETTE_CORRECT   (stbt_vignette_correct_get_type())
#define STBT_VIGNETTE_CORRECT(obj)   (G_TYPE_CHECK_INSTANCE_CAST((obj),STBT_TYPE_VIGNETTE_CORRECT,StbtVignetteCorrect))
#define STBT_VIGNETTE_CORRECT_CLASS(klass)   (G_TYPE_CHECK_CLASS_CAST((klass),STBT_TYPE_VIGNETTE_CORRECT,StbtVignetteCorrectClass))
#define STBT_IS_VIGNETTE_CORRECT(obj)   (G_TYPE_CHECK_INSTANCE_TYPE((obj),STBT_TYPE_VIGNETTE_CORRECT))
#define STBT_IS_VIGNETTE_CORRECT_CLASS(obj)   (G_TYPE_CHECK_CLASS_TYPE((klass),STBT_TYPE_VIGNETTE_CORRECT))
typedef struct _StbtVignetteCorrect StbtVignetteCorrect;
typedef struct _StbtVignetteCorrectClass StbtVignetteCorrectClass;

enum {
  IMAGE_BLACK,
  IMAGE_WHITE,
};

struct _StbtVignetteCorrect
{
  GstVideoFilter base_vignettecorrect;

  GMutex mutex;

  gchar *reference_image_name[2];
  size_t coefficient_count;

  /* Take this number away from the pixel value to make it black */
  unsigned char *offsets;

  /* coefficients by which each pixel value must be multiplied as a fixed point
     with the decimal point at bit 8. */
  unsigned short *coefficients;
};

struct _StbtVignetteCorrectClass
{
  GstVideoFilterClass base_vignettecorrect_class;
};

GType stbt_vignette_correct_get_type (void);

G_END_DECLS
#endif
