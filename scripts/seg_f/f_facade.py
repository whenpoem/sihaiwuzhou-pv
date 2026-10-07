"""L24 的圆柱楼 LED 立面：样张 C 的做法做成动态。

照片里圆柱形高楼的 LED 立面（样张 C 的四个角）向上盖过楼顶，向下延伸到楼身中部，整面是屏幕。屏幕的画面在"立面
坐标"(u, t) 里定义：u 是绕圆柱的横向位置（0–1），t 是自上而下的高度（0–1）。从照片像素到立面坐标的换算与样张 C
完全相同：先用四个角的透视变换得到四边形里的位置，再按圆柱的弧度把横向位置换成圆柱上的角度，两侧因此压窄、压暗；
仰视时水平的一圈在中间显得更低，同一画面高度上中间对应的灯条更靠下。这一换算在着色器里逐像素按解析式求
（单精度，灯条连续），材质 f_led_facade 按立面坐标画出屏幕：横向一条条 LED 灯条，灯条之间是暗缝；竖排繁体两列的烧屏残影
"抓革命　促生產"在亮处显出偏红的暗印，暗处是极淡的红印；刷新亮带由上往下扫过，亮带后面刚刷新的部分被照亮，
随后慢慢暗回去，残影始终都在。
"""
import cv2
import numpy as np

import f_city as CT
from f_common import RED, cached, disk_cached
import look
from engine import Tex, register_material

TW, TH = 440, 1200                       # 立面画面的分辨率（与立面在照片里的宽高比一致）
BOX = (2556, 1214, 2864, 1962)           # 立面平面覆盖的照片像素范围
PHI0 = np.radians(38)

# 屏幕信号故障（L25 的三个"来"）：画面按横向的块错位、闪烁，偶尔有一条撕开的扫描线；块的划分和位移每秒更新
# 二十次。g_amt 为故障强度（0–1），g_static 为暗色的雪花噪点（"乌云"），flash 为砸下那一下的整屏闪白。
GLITCH = """
uniform sampler2D glyph;         // 屏幕上显示的字（覆盖率）
uniform vec4 glyph_rect;         // 字在屏幕坐标里的范围 (u0, t0, u1, t1)
uniform float glyph_k;           // 字的亮度
uniform float g_amt;
uniform float g_static;
uniform float flash;
uniform float g_seed;
float g_shift(float tt, float amt) {
    if (amt <= 0.001) return 0.0;
    int q = int(floor(u_time * 20.0));
    int sd = int(g_seed * 1000.0);
    float bh = 0.025 + 0.06 * rnd(ivec2(q, 3), sd);
    float b = floor((tt + rnd(ivec2(q, 5), sd + 9) * 0.1) / bh);
    float r1 = rnd(ivec2(int(b), q), sd + 1);
    float r2 = rnd(ivec2(int(b), q), sd + 2);
    float sh = (r1 - 0.5) * 0.30 * amt * step(1.0 - 0.5 * amt, r2);
    float tear = step(abs(tt - rnd(ivec2(q, 8), sd + 4)), 0.012 * amt) * (rnd(ivec2(q, 9), sd + 5) - 0.5) * 0.9 * amt;
    return sh + tear;
}
vec3 g_content(float u, float tt) {
    float sh = g_shift(tt, g_amt);
    vec2 q = vec2((u + sh - glyph_rect.x) / (glyph_rect.z - glyph_rect.x), (tt - glyph_rect.y) / (glyph_rect.w - glyph_rect.y));
    float c = 0.0;
    if (q.x > 0.0 && q.x < 1.0 && q.y > 0.0 && q.y < 1.0) c = texture(glyph, q).r;
    // 冷青色的错位副本：故障时字的右边多出一道偏移的淡影（不用红色，红色只属于旧字）
    vec2 q2 = q + vec2(0.035 * g_amt, 0.0);
    float c2 = 0.0;
    if (q2.x > 0.0 && q2.x < 1.0 && q2.y > 0.0 && q2.y < 1.0) c2 = texture(glyph, q2).r;
    int fq = int(floor(u_time * 30.0));
    float flick = 1.0 - g_amt * 0.55 * rnd(ivec2(fq, 1), int(g_seed * 1000.0) + 7);
    vec3 col = vec3(1.0, 1.02, 1.05) * c * glyph_k * flick + vec3(0.35, 0.75, 1.0) * c2 * (1.0 - c) * glyph_k * 0.45 * g_amt;
    float sn = rnd(ivec2(int(u * 220.0), int(tt * 80.0) * 7 + fq), int(g_seed * 1000.0) + 3);
    col += vec3(0.20, 0.22, 0.26) * g_static * sn * sn;
    col += vec3(0.85, 0.9, 1.0) * flash;
    return col;
}
"""

register_material("f_led_facade", GLITCH + """
uniform vec3 hm0;                // 照片像素 → 立面四边形 (s, t) 的透视变换矩阵（按行）
uniform vec3 hm1;
uniform vec3 hm2;
uniform float phi0;              // 屏幕两侧边缘在圆柱上的角度
uniform sampler2D ghost;         // 烧屏残影的覆盖率（立面坐标）
uniform float band;              // 刷新亮带的位置（t），小于 0 表示没有
uniform float base_lit;          // 屏幕底亮（灯条平时的亮度）
uniform float fresh;             // 亮带扫过后被照亮的强度
uniform float ghost_k;
uniform vec3 red;
uniform float power;             // 通电程度：0 全暗，1 正常
vec4 material(vec4 b) {
    // 立面坐标逐像素用解析式求（与样张 C 的 facade_layer() 逐式对应）：世界坐标换成照片像素，经透视变换得到
    // 四边形里的位置 (s, t)，横向位置换成圆柱上的角度，仰视时中间的灯条略靠下。全程单精度，灯条不会断成折线
    vec3 P = vec3((v_wpos.x + 19.2) * 100.0, (12.8 - v_wpos.y) * 100.0, 1.0);
    float w = dot(hm2, P);
    float s = dot(hm0, P) / w;
    float tt = dot(hm1, P) / w;
    float phi = asin(clamp((2.0 * s - 1.0) * sin(phi0), -1.0, 1.0));
    tt += 0.008 * (cos(phi) - cos(phi0)) / (1.0 - cos(phi0));
    float fs = fwidth(s), ft = fwidth(tt);
    float inside = smoothstep(-fs, fs, s) * smoothstep(1.0 + fs, 1.0 - fs, s)
                 * smoothstep(-ft, ft, tt) * smoothstep(1.0 + ft, 1.0 - ft, tt);
    if (inside < 0.002) return vec4(0.0);
    float u = clamp((phi / phi0 + 1.0) * 0.5, 0.0, 1.0);
    tt = clamp(tt, 0.0, 1.0);
    vec4 m = vec4(u, tt, 0.5 + 0.5 * clamp((cos(phi) - 0.6) / 0.4, 0.0, 1.0), inside);
    float us = u + g_shift(tt, g_amt) * 0.5;
    float g = texture(ghost, vec2(us, tt)).r * ghost_k;
    float lit = base_lit;
    if (band >= 0.0) {
        float d = band - tt;                                     // 亮带上方已经刷新过的部分
        lit += fresh * exp(-max(d, 0.0) * 2.3) * step(0.0, d);
    }
    vec3 field = vec3(0.74, 0.80, 0.90) * lit;
    float gh = g * 0.62;
    vec3 col = 0.02 + field * (1.0 - gh) + field * red * 0.9 * gh + red * 0.10 * g;
    if (band >= 0.0) {
        float e = (tt - band) * 80.0;
        col += vec3(0.92, 0.96, 1.0) * (exp(-e * e * 2.2) * 2.2 + exp(-e * e * 0.06) * 0.35);
    }
    col += g_content(u, tt);
    // LED 灯条：横向一条条亮线，条与条之间是暗缝；远处一条不到两个像素时按平均亮度画，不闪烁
    float sy = tt * 80.0;
    float fw = fwidth(sy);
    float stripe = smoothstep(0.30 + fw, 0.30 - fw, abs(fract(sy) - 0.5) - 0.03);
    stripe = mix(stripe, 0.62, smoothstep(0.35, 0.8, fw));
    col *= (0.18 + 0.82 * stripe) * power;
    col *= m.b;
    return vec4(col * m.a, m.a);
}
""", defaults={"band": -1.0, "base_lit": 0.35, "fresh": 0.65, "ghost_k": 1.0,
               "red": tuple(float(v) for v in RED), "power": 1.0, "glyph_rect": (0, 0, 0, 0), "glyph_k": 0.0,
               "g_amt": 0.0, "g_static": 0.0, "flash": 0.0, "g_seed": 0.3})

# 平的楼面临时变成屏幕（L25 另外两栋楼）：没有残影，平时全暗透明，只在显示字、雪花和闪白时亮起。
register_material("f_led_face", GLITCH + """
uniform float stripes;           // 灯条条数
uniform float screen_a;          // 屏幕通电时整面的不透明度：盖住楼面原来的窗灯
uniform float power;
vec4 material(vec4 b) {
    float u = v_uv01.x, tt = v_uv01.y;
    vec3 col = g_content(u, tt);
    float sy = tt * stripes;
    float fw = fwidth(sy);
    float stripe = smoothstep(0.30 + fw, 0.30 - fw, abs(fract(sy) - 0.5) - 0.03);
    stripe = mix(stripe, 0.62, smoothstep(0.35, 0.8, fw));
    col *= (0.10 + 0.90 * stripe) * power;
    float edge = smoothstep(0.0, 0.03, u) * smoothstep(1.0, 0.97, u);
    float a = max(clamp(dot(col, vec3(0.4)) * 3.0, 0.0, 1.0), screen_a) * edge;
    return vec4(col * edge + vec3(0.012, 0.014, 0.02) * screen_a * edge, a);
}
""", defaults={"stripes": 70.0, "power": 1.0, "screen_a": 0.0, "glyph_rect": (0, 0, 0, 0), "glyph_k": 0.0, "g_amt": 0.0,
               "g_static": 0.0, "flash": 0.0, "g_seed": 0.5})


def homography():
    """照片像素 → 立面四边形 (s, t) 的透视变换（样张 C 的四个角）。"""
    return cv2.getPerspectiveTransform(CT.AURORA, np.float32([[0, 0], [1, 0], [1, 1], [0, 1]])).astype(np.float64)


def ghost_tex():
    """"抓革命　促生產"：思源黑体最粗字重，竖排两列（右列先读），笔画边缘略散开。取自样张 C。"""
    def make():
        from scipy.ndimage import gaussian_filter
        import skia
        f = look.font("sans", 900, 196, scale_x=0.95)
        items = []
        for col_i, word in enumerate([look.trad("抓革命"), look.trad("促生产")]):
            cx = TW * (0.76 if col_i == 0 else 0.24)
            for k, ch in enumerate(word):
                b = skia.Rect()
                f.measureText(ch, bounds=b)
                items.append((ch, f, cx - b.width() / 2 - b.left(), TH / 2 + (k - 1) * 330 - b.top() - b.height() / 2, None))
        g = look.text_layer(items, TW, TH)
        return Tex(gaussian_filter(g, 2.0).astype(np.float32))
    return cached("facade_ghost", make)


def plane_geometry():
    """立面平面在世界里的中心与尺寸（照片所在的 z = 0 平面上）。"""
    x0, y0, x1, y1 = BOX
    a, b = CT.px_to_world(x0, y0), CT.px_to_world(x1, y1)
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), (b[0] - a[0], a[1] - b[1])


_EMPTY = None


def empty_tex():
    global _EMPTY
    if _EMPTY is None:
        _EMPTY = Tex(np.zeros((4, 4, 4), np.float32), premultiplied=True)
    return _EMPTY


def items(t, z=0.003, band=-1.0, base_lit=0.35, fresh=0.65, power=1.0, ghost_k=1.0, glitch=None, group="present"):
    """圆柱楼立面的平面。glitch 为 dict(glyph=Tex, rect=(u0, t0, u1, t1), k=亮度, amt=故障强度, static=雪花, flash=闪白)。"""
    from engine import Plane
    c, s = plane_geometry()
    M = homography()
    uni = {"hm0": tuple(M[0]), "hm1": tuple(M[1]), "hm2": tuple(M[2]), "phi0": float(PHI0), "ghost": ghost_tex(),
           "band": band, "base_lit": base_lit, "fresh": fresh, "power": power, "ghost_k": ghost_k, "glyph": empty_tex()}
    if glitch:
        uni.update(glyph=glitch["glyph"], glyph_rect=glitch["rect"], glyph_k=glitch.get("k", 1.3),
                   g_amt=glitch.get("amt", 0.0), g_static=glitch.get("static", 0.0), flash=glitch.get("flash", 0.0),
                   g_seed=glitch.get("seed", 0.3))
    return [Plane(None, center=(c[0], c[1], z), size=s, color=(1, 1, 1), material="f_led_facade", uniforms=uni,
                  group=group)]


# 另外两栋临时变成屏幕的楼面（原图像素矩形）
FACES = {"left": (2265, 1345, 2452, 2050), "right": (2905, 1370, 3215, 2000)}


def face_items(name, glyph, rect, k=1.3, amt=0.0, static=0.0, flash=0.0, power=1.0, seed=0.5, z=0.004, screen_a=0.0):
    from engine import Plane
    x0, y0, x1, y1 = FACES[name]
    a, b = CT.px_to_world(x0, y0), CT.px_to_world(x1, y1)
    stripes = (y1 - y0) / (BOX[3] - BOX[1]) * 80.0 * 1.05
    uni = {"glyph": glyph, "glyph_rect": rect, "glyph_k": k, "g_amt": amt, "g_static": static, "flash": flash,
           "power": power, "g_seed": seed, "stripes": stripes, "screen_a": screen_a}
    return [Plane(None, center=((a[0] + b[0]) / 2, (a[1] + b[1]) / 2, z), size=(b[0] - a[0], a[1] - b[1]),
                  color=(1, 1, 1), material="f_led_face", uniforms=uni, group="present")]


def face_aspect(name):
    """楼面屏幕的宽高比（宽 / 高）。圆柱楼取立面画面的宽高比。"""
    if name == "aurora":
        return TW / TH
    x0, y0, x1, y1 = FACES[name]
    return (x1 - x0) / (y1 - y0)


def glyph_tex(ch="来", weight=300):
    """屏幕上显示的单字（覆盖率，方形贴图，字框居中）。"""
    def make():
        return Tex(look.glyph_mask(ch, "serif", weight, px=512, pad=0.04))
    return cached(f"face_glyph_{ch}_{weight}", make)
