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
 * Free Software Foundation, Inc., 51 Franklin Street, Suite 500,
 * Boston, MA 02110-1335, USA.
 */
/**
 * SECTION:element-stbthistogramcorrect
 *
 * Applies a histogram correction to the input image.
 *
 * <refsect2>
 * <title>Example launch line</title>
 * |[
 * gst-launch -v v4l2src ! videoconvert \
 *     ! histogramcorrect red-correction="23 22" \
 *                  green-correction="0" \
 *                  blue-correction="0" \
 *     ! videoconvert ! autoimagesink
 * ]|
 * </refsect2>
 */

#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include <gst/gst.h>
#include <gst/video/video.h>
#include <gst/video/gstvideofilter.h>

#include <stdio.h>

#include "stbthistogramcorrect.h"

GST_DEBUG_CATEGORY_STATIC (stbt_histogram_correct_debug_category);
#define GST_CAT_DEFAULT stbt_histogram_correct_debug_category

#define STBT_HISTOGRAM_CORRECT_LATENCY (40*GST_MSECOND)

/* prototypes */


static void stbt_histogram_correct_set_property (GObject * object,
    guint property_id, const GValue * value, GParamSpec * pspec);
static void stbt_histogram_correct_get_property (GObject * object,
    guint property_id, GValue * value, GParamSpec * pspec);
static gboolean stbt_histogram_correct_query (GstBaseTransform * trans,
    GstPadDirection direction, GstQuery * query);

static GstFlowReturn stbt_histogram_correct_transform_frame_ip (
    GstVideoFilter * filter, GstVideoFrame * frame);

enum
{
  PROP_0,
  PROP_RED_CORRECTION,
  PROP_GREEN_CORRECTION,
  PROP_BLUE_CORRECTION,
};

/* pad templates */

#define VIDEO_SRC_CAPS \
    "video/x-raw, format=(string)BGR"

#define VIDEO_SINK_CAPS \
    "video/x-raw, format=(string)BGR"

/* Property defaults - No correction */

#define DEFAULT_CORRECTION \
    "0"

/* class initialization */

G_DEFINE_TYPE_WITH_CODE (StbtHistogramCorrect, stbt_histogram_correct,
    GST_TYPE_VIDEO_FILTER,
    GST_DEBUG_CATEGORY_INIT (stbt_histogram_correct_debug_category, "stbthistogramcorrect",
        0, "debug category for histogramcorrect element"));

static void
stbt_histogram_correct_class_init (StbtHistogramCorrectClass * klass)
{
  GObjectClass *gobject_class = G_OBJECT_CLASS (klass);
  GstBaseTransformClass *base_transform_class =
      GST_BASE_TRANSFORM_CLASS (klass);
  GstVideoFilterClass *video_filter_class = GST_VIDEO_FILTER_CLASS (klass);

  /* Setting up pads and setting metadata should be moved to
     base_class_init if you intend to subclass this class. */
  gst_element_class_add_pad_template (GST_ELEMENT_CLASS (klass),
      gst_pad_template_new ("src", GST_PAD_SRC, GST_PAD_ALWAYS,
          gst_caps_from_string (VIDEO_SRC_CAPS)));
  gst_element_class_add_pad_template (GST_ELEMENT_CLASS (klass),
      gst_pad_template_new ("sink", GST_PAD_SINK, GST_PAD_ALWAYS,
          gst_caps_from_string (VIDEO_SINK_CAPS)));

  gst_element_class_set_static_metadata (GST_ELEMENT_CLASS (klass),
      "Histogram Correct", "Generic",
      "Modifies the colours according to the properties",
      "William Manley <will@williammanley.net>");

  gobject_class->set_property = stbt_histogram_correct_set_property;
  gobject_class->get_property = stbt_histogram_correct_get_property;
  base_transform_class->query = GST_DEBUG_FUNCPTR (stbt_histogram_correct_query);
  video_filter_class->transform_frame_ip =
      GST_DEBUG_FUNCPTR (stbt_histogram_correct_transform_frame_ip);

  g_object_class_install_property (gobject_class, PROP_RED_CORRECTION,
      g_param_spec_string ("red-correction", "Red Correction",
          "Correction offsets for Red channel.  256 values between -255 and "
          "255 whitespace separated.",
          DEFAULT_CORRECTION, G_PARAM_READWRITE | G_PARAM_CONSTRUCT | G_PARAM_STATIC_STRINGS));
  g_object_class_install_property (gobject_class, PROP_GREEN_CORRECTION,
      g_param_spec_string ("green-correction", "Green Correction",
          "Correction offsets for Green channel.  256 values between -255 and "
          "255 whitespace separated.",
          DEFAULT_CORRECTION, G_PARAM_READWRITE | G_PARAM_CONSTRUCT | G_PARAM_STATIC_STRINGS));
  g_object_class_install_property (gobject_class, PROP_BLUE_CORRECTION,
      g_param_spec_string ("blue-correction", "Blue Correction",
          "Correction offsets for Blue channel.  256 values between -255 and "
          "255 whitespace separated.",
          DEFAULT_CORRECTION, G_PARAM_READWRITE | G_PARAM_CONSTRUCT | G_PARAM_STATIC_STRINGS));
}

static void
stbt_histogram_correct_init (StbtHistogramCorrect * StbtHistogramCorrect)
{
}

static const char* colours[] = {"RED", "GREEN", "BLUE"};

static void
stbt_histogram_correct_set_property (GObject * object, guint property_id,
    const GValue * value, GParamSpec * pspec)
{
  StbtHistogramCorrect *histogramcorrect = STBT_HISTOGRAM_CORRECT (object);
  int colour = -1;

  GST_DEBUG_OBJECT (histogramcorrect, "set_property");
  switch (property_id) {
    case PROP_RED_CORRECTION:
      colour = colour == -1 ? RED : colour;
    case PROP_GREEN_CORRECTION:
      colour = colour == -1 ? GREEN : colour;
    case PROP_BLUE_CORRECTION:
      colour = colour == -1 ? BLUE : colour;

      gchar **elem;
      int n = 0;
      gchar **elems = g_strsplit_set(g_value_get_string (value), " \t\r\n,",
                                     256);

      for (elem = elems; *elem != NULL; elem++) {
        gint64 correction = g_ascii_strtoll(*elem, NULL, 10);
        if (correction > 255 - n) {
          g_warning("Attempt to correct %s=%i by %i: Correction out of range", colours[colour], n, (int) correction);
          correction = 255 - n;
        }
        if (correction < -n) {
          g_warning("Attempt to correct %s=%i by %i: Correction out of range", colours[colour], n, (int) correction);
          correction = -n;
        }
        histogramcorrect->map[colour][n] = correction + n;
        n++;
      }
      g_strfreev(elems);
      for (;n < 256; n++) {
        histogramcorrect->map[colour][n] = n;
      }
      break;
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, property_id, pspec);
      return;
  }
}

static void
stbt_histogram_correct_get_property (GObject * object, guint property_id,
    GValue * value, GParamSpec * pspec)
{
  StbtHistogramCorrect *histogramcorrect = STBT_HISTOGRAM_CORRECT (object);
  int i, colour = -1;
  char strings[256][5] = {{0}};
  char *stringsv[257] = {0};

  GST_DEBUG_OBJECT (histogramcorrect, "get_property");

  switch (property_id) {
    case PROP_RED_CORRECTION:
      colour = colour == -1 ? RED : colour;
    case PROP_GREEN_CORRECTION:
      colour = colour == -1 ? GREEN : colour;
    case PROP_BLUE_CORRECTION:
      colour = colour == -1 ? BLUE : colour;

      for (i = 0; i < 256; ++i) {
        snprintf(strings[i], sizeof(strings[i]), "%i",
                 (int)histogramcorrect->map[colour][i] - i);
        stringsv[i] = strings[i];
      }
      g_value_take_string(value, g_strjoinv(" ", stringsv));
      break;
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, property_id, pspec);
      return;
  }
}

static gboolean
stbt_histogram_correct_query (GstBaseTransform * trans, GstPadDirection direction,
    GstQuery * query)
{
  gboolean result = GST_BASE_TRANSFORM_CLASS (stbt_histogram_correct_parent_class)
      ->query (trans, direction, query);

  if (result && GST_QUERY_TYPE (query) == GST_QUERY_LATENCY) {
    GstClockTime min, max;
    gboolean live;

    gst_query_parse_latency (query, &live, &min, &max);

    min += STBT_HISTOGRAM_CORRECT_LATENCY;
    max += STBT_HISTOGRAM_CORRECT_LATENCY;

    gst_query_set_latency (query, live, min, max);
  }

  return result;
}

/* transform */
static GstFlowReturn
stbt_histogram_correct_transform_frame_ip (GstVideoFilter * filter,
    GstVideoFrame * frame)
{
  StbtHistogramCorrect *histogramcorrect = STBT_HISTOGRAM_CORRECT (filter);
  int i, len;
  unsigned char *data;

  GST_DEBUG_OBJECT (histogramcorrect, "transform_frame");

  data = frame->data[0];
  len = frame->info.height * frame->info.width * 3;

  for (i = 0; i < len; i += 3) {
    data[i + BLUE] = histogramcorrect->map[BLUE][data[i + BLUE]];
    data[i + GREEN] = histogramcorrect->map[GREEN][data[i + GREEN]];
    data[i + RED] = histogramcorrect->map[RED][data[i + RED]];
  }

  return GST_FLOW_OK;
}
