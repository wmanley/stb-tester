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

#ifndef _STBT_HISTOGRAM_CORRECT_H_
#define _STBT_HISTOGRAM_CORRECT_H_

#include <gst/video/video.h>
#include <gst/video/gstvideofilter.h>

G_BEGIN_DECLS
#define STBT_TYPE_HISTOGRAM_CORRECT   (stbt_histogram_correct_get_type())
#define STBT_HISTOGRAM_CORRECT(obj)   (G_TYPE_CHECK_INSTANCE_CAST((obj),STBT_TYPE_HISTOGRAM_CORRECT,StbtHistogramCorrect))
#define STBT_HISTOGRAM_CORRECT_CLASS(klass)   (G_TYPE_CHECK_CLASS_CAST((klass),STBT_TYPE_HISTOGRAM_CORRECT,StbtHistogramCorrectClass))
#define STBT_IS_HISTOGRAM_CORRECT(obj)   (G_TYPE_CHECK_INSTANCE_TYPE((obj),STBT_TYPE_HISTOGRAM_CORRECT))
#define STBT_IS_HISTOGRAM_CORRECT_CLASS(obj)   (G_TYPE_CHECK_CLASS_TYPE((klass),STBT_TYPE_HISTOGRAM_CORRECT))
typedef struct _StbtHistogramCorrect StbtHistogramCorrect;
typedef struct _StbtHistogramCorrectClass StbtHistogramCorrectClass;

enum Colours
{
  BLUE,
  GREEN,
  RED
/*  RED,
  GREEN,
  BLUE,*/
};

struct _StbtHistogramCorrect
{
  GstVideoFilter base_histogramcorrect;

  /* Maps input colours to output colours.  For an input (b, g, r) the output
     will be (map[BLUE][b], map[GREEN][g], map[RED][r]). */
  unsigned char map[3][256];
};

struct _StbtHistogramCorrectClass
{
  GstVideoFilterClass base_histogramcorrect_class;
};

GType stbt_histogram_correct_get_type (void);

G_END_DECLS
#endif
