"""着色器源码。

所有颜色都在与 scripts/style/look.py 相同的空间里计算：数值即显示用的 sRGB 值，但允许超过 1（高光），
不做线性化。这样显卡版的调色可以逐式对应 look.grade_past / grade_present，两边看起来一致。
渲染缓冲里存的是预乘 alpha 的颜色。
"""

HEADER = "#version 430\n"

# 噪声函数库：材质和后期都会用到。整数哈希（PCG）在大坐标下仍然均匀，不像 sin 哈希那样出现条纹。
NOISE = r"""
uint pcg(uint v) {
    uint s = v * 747796405u + 2891336453u;
    uint w = ((s >> ((s >> 28u) + 4u)) ^ s) * 277803737u;
    return (w >> 22u) ^ w;
}
uvec3 pcg3(uvec3 v) {
    v = v * 1664525u + 1013904223u;
    v.x += v.y * v.z; v.y += v.z * v.x; v.z += v.x * v.y;
    v ^= v >> 16u;
    v.x += v.y * v.z; v.y += v.z * v.x; v.z += v.x * v.y;
    return v;
}
float rnd(ivec2 p, int s) { return float(pcg3(uvec3(ivec3(p, s))).x) * (1.0 / 4294967295.0); }
float rnd3(ivec3 p) { return float(pcg3(uvec3(p)).x) * (1.0 / 4294967295.0); }
// 值噪声，0–1
float vnoise(vec2 p, int s) {
    vec2 i = floor(p); vec2 f = fract(p);
    vec2 u = f * f * (3.0 - 2.0 * f);
    ivec2 q = ivec2(i);
    float a = rnd(q, s), b = rnd(q + ivec2(1, 0), s), c = rnd(q + ivec2(0, 1), s), d = rnd(q + ivec2(1, 1), s);
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}
// 梯度噪声，约 -0.7–0.7
float gnoise(vec2 p, int s) {
    vec2 i = floor(p); vec2 f = fract(p);
    vec2 u = f * f * f * (f * (f * 6.0 - 15.0) + 10.0);
    ivec2 q = ivec2(i);
    float r00 = rnd(q, s) * 6.2831853, r10 = rnd(q + ivec2(1, 0), s) * 6.2831853;
    float r01 = rnd(q + ivec2(0, 1), s) * 6.2831853, r11 = rnd(q + ivec2(1, 1), s) * 6.2831853;
    float a = dot(vec2(cos(r00), sin(r00)), f);
    float b = dot(vec2(cos(r10), sin(r10)), f - vec2(1, 0));
    float c = dot(vec2(cos(r01), sin(r01)), f - vec2(0, 1));
    float d = dot(vec2(cos(r11), sin(r11)), f - vec2(1, 1));
    return mix(mix(a, b, u.x), mix(c, d, u.x), u.y);
}
// 分形噪声，带抗锯齿：fw 为采样点每像素跨过的噪声坐标长度，过细的倍频逐渐淡出，
// 运动中不会闪烁。返回值约 0–1。
float fbm(vec2 p, int oct, float fw, int s) {
    float sum = 0.0, amp = 0.5, norm = 0.0, f = 1.0;
    for (int i = 0; i < oct; i++) {
        float fade = 1.0 - smoothstep(0.25, 0.6, fw * f);
        sum += amp * fade * vnoise(p * f, s + i * 17);
        sum += amp * (1.0 - fade) * 0.5;
        norm += amp;
        f *= 2.03; amp *= 0.55;
    }
    return sum / norm;
}
"""

# ---------------------------------------------------------------------------
# 平面
# ---------------------------------------------------------------------------

PLANE_VS = HEADER + r"""
uniform mat4 u_vp;
uniform mat4 u_view;
uniform mat4 u_model;      // 单位方形（-0.5–0.5）到世界坐标，已含尺寸
uniform vec2 u_size;
uniform vec4 u_uvrect;     // 纹理子区域 (u0, v0, u1, v1)，v 向下
in vec2 in_pos;
out vec2 v_uv;
out vec2 v_uv01;
out vec3 v_wpos;
out vec2 v_local;
out float v_depth;
void main() {
    vec4 w = u_model * vec4(in_pos, 0.0, 1.0);
    v_wpos = w.xyz;
    v_local = in_pos * u_size;
    v_uv01 = vec2(in_pos.x + 0.5, 0.5 - in_pos.y);
    v_uv = mix(u_uvrect.xy, u_uvrect.zw, v_uv01);
    v_depth = -(u_view * w).z;
    gl_Position = u_vp * w;
}
"""

PLANE_FS_PRE = HEADER + r"""
in vec2 v_uv;
in vec2 v_uv01;
in vec3 v_wpos;
in vec2 v_local;
in float v_depth;
out vec4 frag;
uniform sampler2D u_tex;
uniform int u_texmode;          // 0：预乘 RGBA；1：单通道覆盖率
uniform sampler2D u_vec;        // 矢量模式：画面分辨率下的字形覆盖率
uniform int u_vector;
uniform sampler2D u_mask;       // 挖洞遮罩：1 保留，0 挖掉
uniform int u_hasmask;
uniform vec3 u_color;
uniform float u_opacity;
uniform float u_time;
uniform int u_frame;
uniform vec3 u_eye;
uniform vec3 u_normal;
uniform vec2 u_size;
uniform vec2 u_res;
uniform float u_seed;
uniform float u_dof_k;          // 景深：模糊半径（像素）= u_dof_k * |1/深度 - 1/对焦距离|
uniform float u_focus_inv;
float g_blur;                   // 本像素的景深模糊半径（像素），材质可用来淡出细节
float g_mask;                   // 本像素的遮罩值
""" + NOISE + "\n#line 1\n"

PLANE_FS_MAIN = r"""
void main() {
    g_blur = u_dof_k * abs(1.0 / max(v_depth, 1e-4) - u_focus_inv);
    float lb = log2(max(g_blur, 1.0));
    vec4 base;
    if (u_vector == 1) {
        float c = texelFetch(u_vec, ivec2(int(gl_FragCoord.x), int(u_res.y - gl_FragCoord.y)), 0).r;
        base = vec4(u_color * c, c);
    } else if (u_texmode == 1) {
        float c = texture(u_tex, v_uv, lb).r;
        base = vec4(u_color * c, c);
    } else {
        vec4 t = texture(u_tex, v_uv, lb);
        base = vec4(t.rgb * u_color, t.a);
    }
    g_mask = 1.0;
    if (u_hasmask == 1) g_mask = texture(u_mask, v_uv01, lb).r;
    vec4 c = material(base);
    frag = c * (g_mask * u_opacity);
}
"""

MAT_FLAT = r"""
vec4 material(vec4 base) { return base; }
"""

# 纸：纸纹在平面自身的坐标里生成（单位为世界长度），随平面移动、近看仍有细节。
# 细纹和纤维调制明暗，大块污渍偏黄；画在纸上的字（覆盖率纹理）在纸纹凸起处掉墨，像印刷或书写；
# 挖洞的边缘泛出焦黄。
MAT_PAPER = r"""
uniform float paper_amount;     // 纸纹强度
uniform float paper_scale;      // 纸纹尺度（世界单位）
uniform vec3 paper_tint;        // 污渍颜色（乘在底色上）
uniform float paper_stain;      // 污渍强度
uniform float paper_ink;        // 墨色斑驳程度（只作用于覆盖率纹理，即字）
uniform float paper_edge;       // 挖洞边缘的焦黄程度
vec4 material(vec4 base) {
    vec2 p = v_local / paper_scale + vec2(u_seed * 37.13, u_seed * 11.71);
    float fw = length(fwidth(p));
    float fine = fbm(p * 6.0, 5, fw * 6.0, 3) - 0.5;
    vec2 q = vec2(p.x * 0.8 + p.y * 0.25, p.y * 9.0);              // 沿一个方向拉长的纤维
    float fiber = fbm(q * 2.0, 3, length(fwidth(q)) * 2.0, 11) - 0.5;
    float blot = fbm(p * 0.05, 4, fw * 0.05, 23);
    float stain = smoothstep(0.48, 0.8, blot) * paper_stain;
    float k = 1.0 + paper_amount * (fine * 0.22 + fiber * 0.14 - (blot - 0.5) * 0.10);
    vec3 rgb = base.rgb * k * mix(vec3(1.0), paper_tint, stain);
    float a = base.a;
    if (u_texmode == 1 || u_vector == 1) {
        float dry = smoothstep(0.05, 0.3, fine + fiber * 0.8 + 0.12);
        float keep = 1.0 - paper_ink * 0.55 * dry * (0.6 + 0.4 * blot);
        rgb *= keep; a *= keep;
    }
    if (u_hasmask == 1 && paper_edge > 0.0) {
        float soft = textureLod(u_mask, v_uv01, 4.0).r;
        float rim = clamp((1.0 - soft) * 1.6, 0.0, 1.0);
        rgb = mix(rgb, rgb * vec3(0.62, 0.42, 0.22), rim * paper_edge * a);
    }
    return vec4(rgb, a);
}
"""

# ---------------------------------------------------------------------------
# 粒子：实例化绘制，属性放在着色器存储缓冲里，按 u_order 给出的顺序取，排序不必搬动数据
# ---------------------------------------------------------------------------

PART_VS = HEADER + r"""
layout(std430, binding = 0) readonly buffer B0 { float b_pos[]; };
layout(std430, binding = 1) readonly buffer B1 { float b_size[]; };
layout(std430, binding = 2) readonly buffer B2 { float b_rot[]; };
layout(std430, binding = 3) readonly buffer B3 { float b_col[]; };
layout(std430, binding = 4) readonly buffer B4 { float b_uv[]; };
layout(std430, binding = 5) readonly buffer B5 { float b_back[]; };
layout(std430, binding = 6) readonly buffer B6 { int b_order[]; };
uniform mat4 u_vp;
uniform vec3 u_right;
uniform vec3 u_up;
uniform int u_sorted;
uniform int u_oriented;         // 0：始终面向镜头，绕视线转 rot[0]；1：按 (yaw, pitch, roll) 定向
uniform int u_hasback;
in vec2 in_corner;
out vec2 v_uv;
out vec4 v_col;
out vec4 v_back;
mat3 euler(vec3 r) {
    float cy = cos(r.x), sy = sin(r.x), cp = cos(r.y), sp = sin(r.y), cr = cos(r.z), sr = sin(r.z);
    mat3 Ry = mat3(cy, 0, -sy, 0, 1, 0, sy, 0, cy);
    mat3 Rx = mat3(1, 0, 0, 0, cp, sp, 0, -sp, cp);
    mat3 Rz = mat3(cr, sr, 0, -sr, cr, 0, 0, 0, 1);
    return Ry * Rx * Rz;
}
void main() {
    int i = u_sorted == 1 ? b_order[gl_InstanceID] : gl_InstanceID;
    vec3 p = vec3(b_pos[3 * i], b_pos[3 * i + 1], b_pos[3 * i + 2]);
    vec2 c = in_corner * vec2(b_size[2 * i], b_size[2 * i + 1]);
    vec3 r = vec3(b_rot[3 * i], b_rot[3 * i + 1], b_rot[3 * i + 2]);
    vec3 w;
    if (u_oriented == 0) {
        float ca = cos(r.x), sa = sin(r.x);
        vec2 q = vec2(ca * c.x - sa * c.y, sa * c.x + ca * c.y);
        w = p + u_right * q.x + u_up * q.y;
    } else {
        w = p + euler(r) * vec3(c, 0.0);
    }
    vec4 uv = vec4(b_uv[4 * i], b_uv[4 * i + 1], b_uv[4 * i + 2], b_uv[4 * i + 3]);
    v_uv = mix(uv.xy, uv.zw, vec2(in_corner.x + 0.5, 0.5 - in_corner.y));
    v_col = vec4(b_col[4 * i], b_col[4 * i + 1], b_col[4 * i + 2], b_col[4 * i + 3]);
    v_back = u_hasback == 1 ? vec4(b_back[4 * i], b_back[4 * i + 1], b_back[4 * i + 2], b_back[4 * i + 3]) : v_col;
    gl_Position = u_vp * vec4(w, 1.0);
}
"""

PART_FS = HEADER + r"""
in vec2 v_uv;
in vec4 v_col;
in vec4 v_back;
out vec4 frag;
uniform sampler2D u_atlas;
uniform int u_texmode;
uniform float u_opacity;
void main() {
    vec4 c = gl_FrontFacing ? v_col : v_back;
    float a = c.a * u_opacity;
    if (u_texmode == 1) {
        float cov = texture(u_atlas, v_uv).r;
        frag = vec4(c.rgb * a * cov, a * cov);
    } else {
        vec4 t = texture(u_atlas, v_uv);
        frag = vec4(t.rgb * c.rgb * a, t.a * a);
    }
}
"""

# ---------------------------------------------------------------------------
# 画面层（Overlay）：四个角直接给出渲染缓冲里的像素坐标
# ---------------------------------------------------------------------------

OVL_VS = HEADER + r"""
uniform vec2 u_corners[4];      // 像素坐标，y 向下；顺序：左上、右上、左下、右下
uniform vec2 u_res;
out vec2 v_uv;
void main() {
    int k = gl_VertexID;
    vec2 p = u_corners[k];
    v_uv = vec2(float(k & 1), float(k >> 1));
    gl_Position = vec4(p.x / u_res.x * 2.0 - 1.0, 1.0 - p.y / u_res.y * 2.0, 0.0, 1.0);
}
"""

OVL_FS = HEADER + r"""
in vec2 v_uv;
out vec4 frag;
uniform sampler2D u_tex;
uniform int u_texmode;
uniform vec3 u_color;
uniform float u_opacity;
void main() {
    vec4 base;
    if (u_texmode == 1) { float c = texture(u_tex, v_uv).r; base = vec4(u_color * c, c); }
    else { vec4 t = texture(u_tex, v_uv); base = vec4(t.rgb * u_color, t.a); }
    frag = base * u_opacity;
}
"""

# ---------------------------------------------------------------------------
# 后期
# ---------------------------------------------------------------------------

FS_VS = HEADER + r"""
in vec2 in_pos;
out vec2 v_uv;
void main() { v_uv = in_pos * 0.5 + 0.5; gl_Position = vec4(in_pos, 0.0, 1.0); }
"""

ACCUM_FS = HEADER + r"""
uniform sampler2D u_src;
uniform float u_w;
out vec4 frag;
void main() { frag = texelFetch(u_src, ivec2(gl_FragCoord.xy), 0) * u_w; }
"""

# 超采样缩小：ss×ss 的方框平均（与 numpy 参考实现中 reshape 后求平均相同）
DOWN_FS = HEADER + r"""
uniform sampler2D u_src;
uniform int u_ss;
out vec4 frag;
void main() {
    ivec2 o = ivec2(gl_FragCoord.xy) * u_ss;
    vec4 s = vec4(0.0);
    for (int j = 0; j < u_ss; j++) for (int i = 0; i < u_ss; i++) s += texelFetch(u_src, o + ivec2(i, j), 0);
    frag = s / float(u_ss * u_ss);
}
"""

# 取高光并缩小 u_f 倍：mode 0 为过去的光晕（三通道平均减阈值），mode 1 为今天的泛光（逐通道减阈值）
HIPASS_FS = HEADER + r"""
uniform sampler2D u_src;
uniform int u_f;
uniform int u_mode;
uniform float u_thr;
uniform float u_exposure;
uniform vec2 u_offset;          // 片门抖动的像素偏移（只用于过去）
out vec4 frag;
void main() {
    ivec2 o = ivec2(gl_FragCoord.xy) * u_f;
    ivec2 sz = textureSize(u_src, 0);
    vec4 s = vec4(0.0);
    for (int j = 0; j < u_f; j++) for (int i = 0; i < u_f; i++) {
        ivec2 q = clamp(o + ivec2(i, j) + ivec2(u_offset), ivec2(0), sz - 1);
        vec3 c = max(texelFetch(u_src, q, 0).rgb * u_exposure, 0.0);
        if (u_mode == 0) s.r += max((c.r + c.g + c.b) / 3.0 - u_thr, 0.0);
        else s.rgb += max(c - u_thr, 0.0);
    }
    frag = s / float(u_f * u_f);
}
"""

BLUR_FS = HEADER + r"""
uniform sampler2D u_src;
uniform ivec2 u_dir;
uniform float u_sigma;
out vec4 frag;
void main() {
    ivec2 p = ivec2(gl_FragCoord.xy);
    ivec2 sz = textureSize(u_src, 0);
    int r = int(ceil(u_sigma * 3.0));
    float inv = -0.5 / (u_sigma * u_sigma);
    vec4 acc = vec4(0.0);
    float ws = 0.0;
    for (int k = -r; k <= r; k++) {
        float w = exp(float(k * k) * inv);
        acc += texelFetch(u_src, clamp(p + u_dir * k, ivec2(0), sz - 1), 0) * w;
        ws += w;
    }
    frag = acc / ws;
}
"""

# 每帧的颗粒：两路独立的标准正态噪声，以帧号为种子，所以每帧不同、同一帧重复渲染结果相同
NOISE_FS = HEADER + NOISE + r"""
uniform int u_seed;
out vec4 frag;
void main() {
    uvec3 h = pcg3(uvec3(uint(gl_FragCoord.x), uint(gl_FragCoord.y), uint(u_seed) * 2654435761u + 977u));
    float u1 = (float(h.x) + 1.0) / 4294967296.0;
    float u2 = float(h.y) / 4294967296.0;
    float u3 = (float(h.z) + 1.0) / 4294967296.0;
    float u4 = float(pcg(h.x ^ h.z)) / 4294967296.0;
    float n1 = sqrt(-2.0 * log(u1)) * cos(6.2831853 * u2);
    float n2 = sqrt(-2.0 * log(u3)) * cos(6.2831853 * u4);
    frag = vec4(n1, n2, 0.0, 1.0);
}
"""

COMPOSITE_FS = HEADER + NOISE + r"""
in vec2 v_uv;
out vec4 frag;
uniform sampler2D t_past, t_halo, t_present, t_b6, t_b30, t_raw, t_ovl, t_noise, t_noiseblur;
uniform int has_past, has_present, has_raw, has_ovl;
uniform vec2 u_out;
uniform int u_seed;
uniform float u_scale;          // 输出高度 / 1080，像素尺度参数按它换算
// 过去
uniform float p_exposure, p_halation, p_shoulder, p_lift, p_gain, p_sat, p_vignette, p_grain;
uniform vec3 p_warmth, p_halo_col;
uniform vec2 p_weave;
uniform int n_scratch;
uniform vec4 u_scratch[8];      // x（像素）, 宽度（像素）, 强度, 摆动相位
uniform vec4 u_scratch_y[8];    // y0, y1（0–1，自下而上）, 摆动幅度（像素）, 摆动频率
uniform int n_dust;
uniform vec4 u_dust[32];        // x, y（像素）, 半径（像素）, 强度（正为亮斑，负为暗斑）
// 今天
uniform float q_exposure, q_bloom, q_shoulder, q_black;
// 最终
uniform float f_fade;
uniform vec3 f_fade_col;
void main() {
    vec2 uv = vec2(v_uv.x, 1.0 - v_uv.y);           // 读回时第 0 行就是画面顶部
    vec2 px = uv * u_out;
    vec3 col = vec3(0.0);
    if (has_past == 1) {
        vec2 puv = uv + p_weave / u_out;
        // 以下各步与 look.grade_past 逐式对应
        vec3 x = max(texture(t_past, puv).rgb * p_exposure, 0.0);
        x += texture(t_halo, puv).r * p_halo_col * p_halation;
        x = x / (1.0 + p_shoulder * x);
        x = p_lift + x * p_gain;
        x *= p_warmth;
        float lum = (x.r + x.g + x.b) / 3.0;
        x = lum + (x - lum) * p_sat;
        vec2 d = (uv - 0.5) * 2.0;
        float r2 = dot(d, d);
        x *= 1.08 - p_vignette * pow(r2, 1.4);
        ivec2 ip = ivec2(px);
        float g = texelFetch(t_noise, ip, 0).r + texelFetch(t_noiseblur, ip, 0).g * 1.6;
        x += g * p_grain * (0.4 + lum);
        for (int i = 0; i < n_scratch; i++) {
            vec4 s = u_scratch[i];
            vec4 sy = u_scratch_y[i];
            float yy = uv.y;
            float vmask = smoothstep(sy.x - 0.02, sy.x + 0.02, yy) * (1.0 - smoothstep(sy.y - 0.02, sy.y + 0.02, yy));
            float xs = s.x + sy.z * sin(yy * sy.w + s.w);
            float cov = clamp(s.y * 0.5 + 0.5 - abs(px.x - xs), 0.0, 1.0);
            x = mix(x, vec3(1.0), 0.3 * s.z * cov * vmask);
        }
        for (int i = 0; i < n_dust; i++) {
            vec4 dd = u_dust[i];
            float r = length(px - dd.xy) / max(dd.z, 0.5);
            float a = (1.0 - smoothstep(0.6, 1.0, r)) * abs(dd.w);
            x = mix(x, dd.w > 0.0 ? vec3(0.95, 0.92, 0.85) : vec3(0.03, 0.025, 0.02), a);
        }
        col = clamp(x, 0.0, 1.0);
    }
    if (has_present == 1) {
        // 与 look.grade_present 对应；present 层有透明处时按预乘 alpha 叠在过去之上，
        // 泛光既作用于本层也溢到下面的过去层上
        vec4 P = texture(t_present, uv);
        P.rgb *= q_exposure;
        vec3 B = (texture(t_b6, uv).rgb * 0.6 + texture(t_b30, uv).rgb * 0.4) * q_bloom;
        vec3 x = max(P.rgb, 0.0) + B;
        vec3 T = P.a * q_black + (1.0 - q_black) * x / (1.0 + q_shoulder * x);
        col = clamp(col * (1.0 - P.a) + T, 0.0, 1.0);
    }
    if (has_raw == 1) {
        vec4 R = texture(t_raw, uv);
        col = col * (1.0 - R.a) + R.rgb;
    }
    if (has_ovl == 1) {
        vec4 O = texture(t_ovl, uv);
        col = col * (1.0 - O.a) + O.rgb;
    }
    col = mix(col, f_fade_col, f_fade);
    // 1 个量化级的三角分布抖动，避免今天的纯黑渐变在 8 位输出里出现色带
    ivec2 ip2 = ivec2(px);
    float dz = rnd(ip2, u_seed * 7 + 1) - rnd(ip2, u_seed * 7 + 2);
    col += dz / 255.0;
    frag = vec4(clamp(col, 0.0, 1.0), 1.0);
}
"""
