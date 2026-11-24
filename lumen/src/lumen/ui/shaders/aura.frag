#version 440
layout(location = 0) in vec2 qt_TexCoord0;
layout(location = 0) out vec4 fragColor;

layout(std140, binding = 0) uniform buf {
    mat4 qt_Matrix;
    float qt_Opacity;
    float time;        // giay, tang lien tuc
    vec2  boxSize;     // kich thuoc item (px)
    float radius;      // ban kinh bo goc cua the/hang ben trong
    float inset;       // do day vien aura (px)
} ubuf;

// nhieu gia-ngau-nhien re, du cho lua
float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

float noise(vec2 p) {
    vec2 i = floor(p), f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    return mix(mix(hash(i), hash(i + vec2(1, 0)), f.x),
               mix(hash(i + vec2(0, 1)), hash(i + vec2(1, 1)), f.x), f.y);
}

// nhieu nhieu tang -> ngon lua co ca net to lan net nho
float fbm(vec2 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 4; ++i) { v += a * noise(p); p *= 2.0; a *= 0.5; }
    return v;
}

// khoang cach co dau toi mot hinh chu nhat bo goc
float roundedBox(vec2 p, vec2 b, float r) {
    vec2 q = abs(p) - b + r;
    return length(max(q, 0.0)) + min(max(q.x, q.y), 0.0) - r;
}

void main() {
    vec2 px = (qt_TexCoord0 - 0.5) * ubuf.boxSize;
    vec2 inner = ubuf.boxSize * 0.5 - vec2(ubuf.inset);
    float d = roundedBox(px, inner, ubuf.radius);

    // lua boc quanh vien: chi ve BEN NGOAI hinh trong
    float band = smoothstep(ubuf.inset, 0.0, d) * step(0.0, d);

    // ngon lua troi len tren + nhap nhay theo thoi gian
    vec2 flow = vec2(px.x * 0.035, px.y * 0.020 - ubuf.time * 1.6);
    float turb = fbm(flow * 3.0) * 0.65 + fbm(flow * 7.0) * 0.35;
    float flicker = 0.75 + 0.25 * sin(ubuf.time * 7.3 + px.x * 0.05);

    float intensity = band * turb * flicker;
    intensity = clamp(intensity * 2.2, 0.0, 1.0);

    // loi vang -> ria cam -> tan ra
    vec3 hot  = vec3(1.00, 0.85, 0.35);
    vec3 warm = vec3(1.00, 0.42, 0.08);
    vec3 col  = mix(warm, hot, pow(intensity, 2.0));

    fragColor = vec4(col, 1.0) * intensity * ubuf.qt_Opacity;
}
