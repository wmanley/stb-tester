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
 * SECTION:element-stbtvignettecorrect
 *
 * Applies a vignette correction to the input image.
 *
 * <refsect2>
 * <title>Example launch line</title>
 * |[
 * gst-launch -v v4l2src ! videoconvert \
 *     ! vignettecorrect reference-image="reference.png"
 *     ! videoconvert ! autoimagesink
 * ]|
 * </refsect2>
 */

#ifdef HAVE_CONFIG_H
#include "config.h"
#endif

#include <gst/gst.h>
#include <gst/app/gstappsink.h>

#include <stdio.h>

#include "stbtvignettecorrect.h"
#include "stbtvignettecorrect_orc.h"

GST_DEBUG_CATEGORY_STATIC (stbt_vignette_correct_debug_category);
#define GST_CAT_DEFAULT stbt_vignette_correct_debug_category

#define STBT_VIGNETTE_CORRECT_LATENCY (40*GST_MSECOND)

/* prototypes */

static void stbt_vignette_correct_finalize (GObject * object);

static void stbt_vignette_correct_set_property (GObject * object,
    guint property_id, const GValue * value, GParamSpec * pspec);
static void stbt_vignette_correct_get_property (GObject * object,
    guint property_id, GValue * value, GParamSpec * pspec);
static gboolean stbt_vignette_correct_query (GstBaseTransform * trans,
    GstPadDirection direction, GstQuery * query);

static GstFlowReturn stbt_vignette_correct_transform_frame (
    GstVideoFilter * filter, GstVideoFrame * frame, GstVideoFrame * out_frame);

enum
{
  PROP_0,
  PROP_BLACK_REFERENCE_IMAGE,
  PROP_WHITE_REFERENCE_IMAGE,
};

/* pad templates */

#define VIDEO_SRC_CAPS \
    "video/x-raw, format=(string)BGR"

#define VIDEO_SINK_CAPS \
    "video/x-raw, format=(string)BGR"

/* Property defaults - No correction */

#define DEFAULT_REFERENCE_IMAGE ""

/* class initialization */

G_DEFINE_TYPE_WITH_CODE (StbtVignetteCorrect, stbt_vignette_correct,
    GST_TYPE_VIDEO_FILTER,
    GST_DEBUG_CATEGORY_INIT (stbt_vignette_correct_debug_category,
      "stbtvignettecorrect", 0, "debug category for vignettecorrect element"));

static void
stbt_vignette_correct_class_init (StbtVignetteCorrectClass * klass)
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
      "Vignette Correct", "Generic",
      "Fixes differences in brightness across an image",
      "William Manley <will@williammanley.net>");

  gobject_class->finalize = stbt_vignette_correct_finalize;
  gobject_class->set_property = stbt_vignette_correct_set_property;
  gobject_class->get_property = stbt_vignette_correct_get_property;
  base_transform_class->query = GST_DEBUG_FUNCPTR (stbt_vignette_correct_query);
  video_filter_class->transform_frame =
      GST_DEBUG_FUNCPTR (stbt_vignette_correct_transform_frame);

  g_object_class_install_property (gobject_class, PROP_BLACK_REFERENCE_IMAGE,
      g_param_spec_string ("black-reference-image", "Black Reference Image",
          "Image taken of plain black to use as a reference",
          DEFAULT_REFERENCE_IMAGE, G_PARAM_READWRITE | G_PARAM_CONSTRUCT
          | G_PARAM_STATIC_STRINGS));
  g_object_class_install_property (gobject_class, PROP_WHITE_REFERENCE_IMAGE,
      g_param_spec_string ("white-reference-image", "White Reference Image",
          "Image taken of plain white to use as a reference",
          DEFAULT_REFERENCE_IMAGE, G_PARAM_READWRITE | G_PARAM_CONSTRUCT
          | G_PARAM_STATIC_STRINGS));
}

static void
stbt_vignette_correct_init (StbtVignetteCorrect * vignettecorrect)
{
  g_mutex_init(&vignettecorrect->mutex);
}

static void
stbt_vignette_correct_finalize (GObject * object)
{
  StbtVignetteCorrect * vignettecorrect = STBT_VIGNETTE_CORRECT (object);
  g_mutex_clear(&vignettecorrect->mutex);
  G_OBJECT_CLASS (stbt_vignette_correct_parent_class)->finalize (object);
}

static GstSample*
stbt_vignette_correct_load_png (const gchar *filename, const GstCaps *caps)
{
  GstElement *src, *sink;
  GstSample *out;
  GstElement *pipeline = gst_parse_launch (
    "filesrc name=src ! pngdec ! videoconvert ! appsink name=sink", NULL);

  g_return_val_if_fail (pipeline, NULL);

  src = gst_bin_get_by_name(GST_BIN(pipeline), "src");
  sink = gst_bin_get_by_name(GST_BIN(pipeline), "sink");

  g_return_val_if_fail (src && sink, NULL);
  g_object_set(src, "location", filename, NULL);
  g_object_set(sink, "caps", caps, NULL);

  gst_element_set_state(GST_ELEMENT(pipeline), GST_STATE_PLAYING);

  /* FIXME: deal with error conditions like missing file, etc. */
  out = gst_app_sink_pull_preroll(GST_APP_SINK (sink));

  gst_element_set_state(GST_ELEMENT(pipeline), GST_STATE_NULL);

  g_object_unref(G_OBJECT(src));
  g_object_unref(G_OBJECT(sink));
  g_object_unref(G_OBJECT(pipeline));

  return out;
}

inline static guint8
max3(guint8 a, guint8 b, guint8 c)
{
  if (a > b)
    return a > c ? a : c;
  else
    return b > c ? b : c;
}

inline static guint8
min3(guint8 a, guint8 b, guint8 c)
{
  if (a < b)
    return a < c ? a : c;
  else
    return b < c ? b : c;
}

static GstStaticCaps mycaps = GST_STATIC_CAPS ("video/x-raw,format=BGR");

#define SWAP(a, b) { typeof(a) _swap_tmp = a; a = b; b = _swap_tmp; }

static void
stbt_vignette_correct_update_coefficients(StbtVignetteCorrect *vignettecorrect,
    const gchar* filename_black, const gchar* filename_white)
{
  GstSample *image[2] = {NULL, NULL};
  gchar *reference_image_name[2] = {NULL, NULL};
  gboolean success[2] = {FALSE, FALSE};
  GstMapInfo map[2] = {{0}};
  size_t idx, count = 1280*720*3;
  unsigned short *coefficients = NULL;
  unsigned char *offsets = NULL;

  reference_image_name[IMAGE_WHITE] = g_strdup(filename_white);
  reference_image_name[IMAGE_BLACK] = g_strdup(filename_black);

  if (filename_black && filename_black[0] != '\0') {
    image[IMAGE_BLACK] = stbt_vignette_correct_load_png(filename_black,
        gst_static_caps_get(&mycaps));

    if (image[IMAGE_BLACK]) {
      success[IMAGE_BLACK] = gst_buffer_map(gst_sample_get_buffer(
        image[IMAGE_BLACK]), &map[IMAGE_BLACK], GST_LOCK_FLAG_READ);
      g_return_if_fail (success[IMAGE_BLACK]);
    }
  }

  if (filename_white && filename_white[0] != '\0') {
    image[IMAGE_WHITE] = stbt_vignette_correct_load_png(filename_white,
        gst_static_caps_get(&mycaps));
    if (image[IMAGE_WHITE]) {
      success[IMAGE_WHITE] = gst_buffer_map(gst_sample_get_buffer(
        image[IMAGE_WHITE]), &map[IMAGE_WHITE], GST_LOCK_FLAG_READ);
      g_return_if_fail (success[IMAGE_WHITE]);
    }
  }

  if (success[IMAGE_WHITE])
    count = map[IMAGE_WHITE].size;
  if (success[IMAGE_BLACK])
    count = map[IMAGE_BLACK].size;
  if (success[IMAGE_WHITE] && success[IMAGE_BLACK]
      && map[IMAGE_WHITE].size != map[IMAGE_BLACK].size) {
    GST_ELEMENT_ERROR(vignettecorrect, RESOURCE, FAILED, NULL,
      ("Reference image sizes don't match"));
    goto error;
  }

  coefficients = g_malloc(count * sizeof(unsigned short));
  offsets = g_malloc(count * sizeof(unsigned char));
  for (idx = 0; idx < count; idx += 3) {
    guint8 white_point = success[IMAGE_WHITE] ? max3(map[IMAGE_WHITE].data[idx + 0],
      map[IMAGE_WHITE].data[idx + 1], map[IMAGE_WHITE].data[idx + 2]) : 255;
    guint8 black_point = success[IMAGE_BLACK] ? min3(map[IMAGE_BLACK].data[idx + 0],
      map[IMAGE_BLACK].data[idx + 1], map[IMAGE_BLACK].data[idx + 2]) : 0;
    short diff = (short) white_point - (short) black_point;

    offsets[idx] = black_point;
    offsets[idx+1] = black_point;
    offsets[idx+2] = black_point;
    if (diff <= 0) {
      coefficients[idx] = 255<<8;
      coefficients[idx+1] = 255<<8;
      coefficients[idx+2] = 255<<8;
    } else {
      coefficients[idx] = ((unsigned short)255<<8)/diff;
      coefficients[idx+1] = ((unsigned short)255<<8)/diff;
      coefficients[idx+2] = ((unsigned short)255<<8)/diff;
    }
/*    if (filename_black && filename_black[0] && filename_white && filename_white[0])
      printf("%i, %i => (%f %f %f)\n", (int)black_point, (int) white_point, (float)coefficients[idx] / 256.0, (float)coefficients[idx+1] / 256.0, (float)coefficients[idx+2] / 256.0);*/
  }
  if (success[IMAGE_BLACK]) {
    gst_buffer_unmap (gst_sample_get_buffer(image[IMAGE_BLACK]), &map[IMAGE_BLACK]);
    gst_sample_unref (image[IMAGE_BLACK]);
  }
  if (success[IMAGE_WHITE]) {
    gst_buffer_unmap (gst_sample_get_buffer(image[IMAGE_WHITE]), &map[IMAGE_WHITE]);
    gst_sample_unref (image[IMAGE_WHITE]);
  }
error:
  /* Want to be doing as little as possible with the mutex locked so use SWAP
   */
  g_mutex_lock (&vignettecorrect->mutex);
  SWAP(vignettecorrect->reference_image_name[IMAGE_WHITE],
    reference_image_name[IMAGE_WHITE]);
  SWAP(vignettecorrect->reference_image_name[IMAGE_BLACK],
    reference_image_name[IMAGE_BLACK]);
  SWAP(vignettecorrect->coefficient_count, count);
  SWAP(vignettecorrect->coefficients, coefficients);
  SWAP(vignettecorrect->offsets, offsets);
  g_mutex_unlock (&vignettecorrect->mutex);

  g_free (reference_image_name[IMAGE_WHITE]);
  g_free (reference_image_name[IMAGE_BLACK]);
  g_free (coefficients);
  g_free (offsets);
}

static void
stbt_vignette_correct_set_property (GObject * object, guint property_id,
    const GValue * value, GParamSpec * pspec)
{
  StbtVignetteCorrect *vignettecorrect = STBT_VIGNETTE_CORRECT (object);

  GST_DEBUG_OBJECT (vignettecorrect, "set_property");
  switch (property_id) {
    case PROP_BLACK_REFERENCE_IMAGE:
      stbt_vignette_correct_update_coefficients (vignettecorrect,
          g_strdup(g_value_get_string (value)), vignettecorrect->reference_image_name[IMAGE_WHITE]);
      break;
    case PROP_WHITE_REFERENCE_IMAGE:
      stbt_vignette_correct_update_coefficients (vignettecorrect,
          vignettecorrect->reference_image_name[IMAGE_BLACK], g_strdup(g_value_get_string (value)));
      break;
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, property_id, pspec);
      return;
  }
}

static void
stbt_vignette_correct_get_property (GObject * object, guint property_id,
    GValue * value, GParamSpec * pspec)
{
  StbtVignetteCorrect *vignettecorrect = STBT_VIGNETTE_CORRECT (object);

  GST_DEBUG_OBJECT (vignettecorrect, "get_property");

  switch (property_id) {
    case PROP_BLACK_REFERENCE_IMAGE:
      if (vignettecorrect->reference_image_name[IMAGE_BLACK])
        g_value_set_string(value, "");
      else
        g_value_set_string(value, vignettecorrect->reference_image_name[IMAGE_BLACK]);
      break;
    case PROP_WHITE_REFERENCE_IMAGE:
      if (vignettecorrect->reference_image_name[IMAGE_WHITE])
        g_value_set_string(value, "");
      else
        g_value_set_string(value, vignettecorrect->reference_image_name[IMAGE_WHITE]);
      break;
    default:
      G_OBJECT_WARN_INVALID_PROPERTY_ID (object, property_id, pspec);
      return;
  }
}

static gboolean
stbt_vignette_correct_query (GstBaseTransform * trans, GstPadDirection direction,
    GstQuery * query)
{
  gboolean result = GST_BASE_TRANSFORM_CLASS (stbt_vignette_correct_parent_class)
      ->query (trans, direction, query);

  if (result && GST_QUERY_TYPE (query) == GST_QUERY_LATENCY) {
    GstClockTime min, max;
    gboolean live;

    gst_query_parse_latency (query, &live, &min, &max);

    min += STBT_VIGNETTE_CORRECT_LATENCY;
    max += STBT_VIGNETTE_CORRECT_LATENCY;

    gst_query_set_latency (query, live, min, max);
  }

  return result;
}

inline guint8 clamp(unsigned x)
{
  if (x<255)
    return x;
  else
    return 255;
}

inline unsigned char subusb(unsigned char a, unsigned char b)
{
  return a > b ? a - b : 0;
}

inline unsigned char convususwb(unsigned short a)
{
  return a < 255 ? a : 255;
}

inline unsigned short mulhuw(unsigned short a, unsigned short b)
{
  return (a*b) >> 8;
}

/* transform */
static GstFlowReturn
stbt_vignette_correct_transform_frame (GstVideoFilter * filter,
    GstVideoFrame * in_frame, GstVideoFrame * out_frame)
{
  StbtVignetteCorrect *vignettecorrect = STBT_VIGNETTE_CORRECT (filter);
  int len;

  GST_DEBUG_OBJECT (vignettecorrect, "transform_frame");

  g_mutex_lock (&vignettecorrect->mutex);

  if (vignettecorrect->coefficients == NULL)
    goto done;
  len = in_frame->info.height * in_frame->info.width * 3;
  if (vignettecorrect->coefficient_count != len) {
    GST_ELEMENT_ERROR(vignettecorrect, STREAM, WRONG_TYPE, NULL,
        ("Wrong size"));
    goto error;
  }

  /* Defined in stbtvignettecorrect.orc for speed */
  stbt_vignettecorrect_apply(out_frame->data[0], in_frame->data[0], vignettecorrect->offsets,
      vignettecorrect->coefficients, vignettecorrect->coefficient_count);

  g_mutex_unlock (&vignettecorrect->mutex);

done:
  return GST_FLOW_OK;
error:
  return GST_FLOW_ERROR;
}
