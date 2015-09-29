precision mediump float;

/*
 * The point in the output video that we need to provide a colour for.  Ranges
 * between (0.0, 0.0) to (1.0, 1.0) corresponding to (0, 0), (1280, 720):
 */
varying vec2 v_texcoord;

/*
 * The input video frame
 */
uniform sampler2D tex;

/*
 * Variables describing the camera matrix:
 *
 * [ fx   0   cx ]
 * [ 0    fy  cy ]
 * [ 0    0    1 ]
 */
uniform float fx; // = 1.0;
uniform float fy; // = 1.0;
uniform float cx; // = 0.0;
uniform float cy; // = 0.0;

/*
 * The distortion coefficients further describing the camera:
 *
 * [ k1, k2, p1, p2, k3 ]
 */
uniform float k1; // = 0.0;
uniform float k2; // = 0.0;
uniform float p1; // = 0.0;
uniform float p2; // = 0.0;
uniform float k3; // = 0.0;

/*
 * The inverse homography matrix describing the location of the TV in the image.
 *
 * Unfortunately the GStreamer glshader element's GLSL parser doesn't seem to
 * parse matricies correctly so I have to write it out explicitly here.
 */
uniform float ihm11; // = 1.5;
uniform float ihm12; // = 0.0;
uniform float ihm13; // = 0.0;
uniform float ihm21; // = 0.0;
uniform float ihm22; // = 1.5;
uniform float ihm23; // = 0.0;
uniform float ihm31; // = 0.25;
uniform float ihm32; // = 0.25;
uniform float ihm33; // = 1.0;
mat3 inv_homography_matrix = mat3(
    ihm11, ihm12, ihm13,
    ihm21, ihm22, ihm23,
    ihm31, ihm32, ihm33);

vec2 world_to_camera(vec3 v)
{
    mat3 camera_matrix = mat3(
        fx, 0.0, 0.0,
        0.0, fy, 0.0,
        cx,  cy, 1.0);

    vec3 o = camera_matrix * v;
    return vec2(o[0], o[1]);
}

vec2 perspective_transform(vec2 src, mat3 m)
{
    vec3 v =  m * vec3(src, 1.0);

    float w = v[2];
    if( w != 0. ) {
        v /= w;
        return vec2(v[0], v[1]);
    } else
        return vec2(0.0, 0.0);
}

vec2 apply_camera_distortion(vec2 src)
{
    float r2 = src.x * src.x + src.y * src.y;
    float r4 = r2 * r2;
    float r6 = r2 * r2 * r2;

    float radial_factor = 1.0 + k1 * r2 + k2 * r4 + k3 * r6;

    return vec2(
        src.x * radial_factor
        + 2.0 * p1 * src.x * src.y
        + p2 * (r2 + 2.0 * src.x * src.x),
        src.y * radial_factor
        + 2.0 * p2 * src.x * src.y
        + p1 * (r2 + 2.0 * src.y * src.y));
}

/*
 * Transform a pixel location in the output 1280x720 image into a pixel location
 * in the input 1920x1080 image.
 */
vec2 transform_coordinates(vec2 in_coord)
{
    in_coord = perspective_transform(in_coord, inv_homography_matrix);

    vec2 distorted = apply_camera_distortion(in_coord);
    return world_to_camera(vec3(distorted, 1.0));
}

void main()
{
    vec2 in_coord = vec2(v_texcoord[0] * 1280.0, v_texcoord[1] * 720.0);
    vec2 out_coord = transform_coordinates(in_coord);
    gl_FragColor = texture2D(tex, vec2(
        (out_coord[0] / 1920.0),
        (out_coord[1] / 1080.0)));
    return;
}

