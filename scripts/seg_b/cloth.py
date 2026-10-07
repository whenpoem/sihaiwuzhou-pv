"""L05 的被单：逆光的布料材质、印在布上的歌词、背面透出的反向红字、最右一张的焦黄与烧穿。

做法沿用样张三：正午的太阳在被单后上方，布被照透，正面印着墨褐色的粗宋体，
背面是旧标语布上左右反向的红字"東方紅　太陽升"，只在逆光时透出来。样张三是一张静图，这里改成显卡材质，
让布在风里动起来。动的方式是改变布面的起伏，而不是移动整张平面：

一、布面起伏。布面相对平面的高度由三部分叠加：五组竖向的褶（从夹子处垂下，越往下越深，随时间缓慢漂移）、
被风鼓起的一个大弧面、下摆被风推开的摆幅。由高度的偏导数得到法线。

二、透光。逆光下布的亮度主要来自透过布的阳光：背面法线与太阳方向的夹角决定布背面接到多少光，布的厚度决定
透过多少（按 exp(−厚度) 衰减）。厚度在褶壁处增大（视线斜穿布面），在下摆和两侧的折边处加倍，经纬纱的粗细
不匀让它有细小的起伏，被风绷紧时布变薄。正面只接到一点天光。

三、风。每张布有一个被风吹开的时刻 t_gust，就是它那个字的元音起点。风到之前布松松地垂着，褶深而密，印字
被褶挤得断断续续、看不清，布背面斜对着高处的太阳，透光弱；风到时下摆被推开、布面鼓起绷平，背面转向太阳，
布一下子被照透，字随之清楚地显出来。之后风不停，布维持鼓起的样子轻轻起伏。

四、烧。最右一张从右下角开始发黄、焦黑、烧穿，烧到的先后由 burnmap 给出（0–1），进度 burn_p 由场景推进；
烧穿的边上是一圈暗红的余烬。
"""
import math

import numpy as np
import skia
from scipy.ndimage import gaussian_filter

from common import L, Z_SHEET, cached, disk, ease, ramp
from engine import Plane, Tex, register_material

CLOTH_GLSL = r"""
uniform vec4 sh_box;        // 布在平面局部坐标里的范围：x0, ytop, w, h（世界单位，y 向上）
uniform float sh_seed;
uniform float t_gust;       // 被风吹开的时刻
uniform float slack;        // 风到之前布松垂的程度（褶的深浅）
uniform float swing_k;      // 下摆被推开的幅度
uniform float creases;      // 叠放留下的折痕
uniform sampler2D glyph;    // 歌词字形（覆盖率）
uniform vec4 gbox;          // 字在布上的中心 u、v 与宽、高（布的 0–1 坐标，v 向下）
uniform float ink_k;
uniform sampler2D backp;    // 背面红字（覆盖率，布的 0–1 坐标，已左右翻转）
uniform float back_k;
uniform sampler2D burnmap;  // 烧到的先后
uniform float burn_p;       // 烧的进度，< -0.5 表示这张不烧
uniform sampler2D heatw;    // 烤出来的字（覆盖率，布的 0–1 坐标）
uniform vec3 sun_col;
uniform vec3 amb_col;
uniform vec3 sun_dir;       // 指向太阳

const float PI = 3.14159265;

float gustenv(float t) {
    float u = t - t_gust;
    float rise = smoothstep(-0.10, 0.24, u);
    float settle = 0.68 + 0.32 * exp(-max(u - 0.24, 0.0) / 0.5);
    return rise * settle;
}

// 布面高度（世界单位，朝镜头为正）。P = (X, Y)：X 自左缘向右，Y 自绳子向下。
// 返回 (总高度, 只含褶的高度)：后者用来估计褶把印字挤拢的程度。
vec2 hfield(vec2 P, float t, float g, float W, float Hh, float s) {
    float yv = clamp(P.y / Hh, 0.0, 1.0);
    float pin = 0.30 + 0.70 * smoothstep(0.0, 0.55, yv);
    float amp = mix(slack, 0.45, g);
    float drift = t * (0.06 + 0.55 * g);
    // 竖向的长褶：横向频率高、竖向频率低的梯度噪声，缓慢漂移；风里横向跑动
    vec2 q = vec2(P.x * 2.1 + s * 7.0 + drift, P.y * 0.42 + s * 3.0 - t * 0.04);
    float h = 0.120 * gnoise(q, 3);
    h += 0.060 * gnoise(q * vec2(2.1, 1.6) + vec2(4.1, 1.3) + vec2(drift * 0.7, 0.0), 5);
    h += 0.028 * gnoise(q * vec2(4.4, 3.0) - vec2(2.3, 0.7) + vec2(drift * 1.6, 0.0), 7);
    h += 0.006 * gnoise(q * vec2(9.0, 6.2) + vec2(9.7, 3.1), 11);
    h *= amp * pin;
    // 两只夹子各斜出几道垂褶，向中下方收拢
    float dr = 0.0;
    for (int j = 0; j < 2; j++) {
        float xp = (j == 0 ? 0.10 : 0.90) * W;
        vec2 d = vec2(P.x - xp, P.y + 0.05);
        float r = length(d);
        dr += sin(atan(d.x, d.y) * 8.0 + s * 3.0 + float(j) * 1.7) * exp(-r / (0.28 * Hh)) * smoothstep(0.02, 0.3, r);
    }
    h += 0.032 * dr * (1.0 - 0.55 * g);
    // 叠放留下的折痕：竖向一道在正中，横向两道在三分处
    float cr = exp(-pow((P.x - 0.5 * W) / 0.010, 2.0)) * 0.7
             + exp(-pow((P.y - 0.34 * Hh) / 0.010, 2.0)) * 0.5
             + exp(-pow((P.y - 0.67 * Hh) / 0.010, 2.0)) * 0.5;
    h += creases * 0.0022 * cr * (1.0 - 0.4 * g);
    float folds = h;
    // 风把布鼓起、把下摆推远（推开的方向背离镜头，布的背面因此转向高处的太阳）
    h += -0.55 * g * sin(PI * P.x / W) * pow(yv, 1.3);
    h += -swing_k * (0.08 + g) * 0.36 * Hh * yv * yv;
    return vec2(h, folds);
}

vec4 material(vec4 base) {
    float x0 = sh_box.x, ytop = sh_box.y, W = sh_box.z, Hh = sh_box.w;
    float X = v_local.x - x0;
    float Y = ytop - v_local.y;
    float s = sh_seed * 6.2831853;
    float t = u_time;
    float yv = clamp(Y / Hh, 0.0, 1.0);

    // 风沿绳子从左往右吹来：布的左边先到；风到之后不停，强弱缓缓变化
    float g = gustenv(t - (X / W) * 0.10);
    g *= 1.0 + 0.14 * sin(1.9 * t + s) + 0.08 * sin(4.3 * t + 2.0 * s);
    g = clamp(g, 0.0, 1.2);

    float e = 0.006;
    vec2 P0 = vec2(X, Y);
    vec2 h0 = hfield(P0, t, g, W, Hh, s);
    vec2 h1 = hfield(P0 + vec2(e, 0.0), t, g, W, Hh, s);
    vec2 h2 = hfield(P0 + vec2(0.0, e), t, g, W, Hh, s);
    float hx = (h1.x - h0.x) / e, hy = (h2.x - h0.x) / e;
    float fx = (h1.y - h0.y) / e;
    vec3 n = normalize(vec3(-hx, hy, 1.0));     // 平面里 y 向上，dz/dy = −dz/dY

    // 褶把布在水平方向挤拢：印字在投影上的位置偏移约为 ½·h·∂h/∂x（单一正弦时精确）
    float pleat = 0.5 * h0.y * fx;
    // 下摆被推远后在画面上抬起：投影里的 Y 对应布上更靠下的位置
    float lift = 0.035 * g + 0.008;
    float Yc = Y / (1.0 - lift * yv);
    float vc = Yc / Hh;

    // 轮廓：上沿在两只夹子之间略往下垂，夹子外的两角稍稍耷拉；下摆和两侧随风起伏
    float u01 = X / W;
    float mid = sin(PI * clamp((u01 - 0.10) / 0.80, 0.0, 1.0));
    float outer = pow(max(max(0.10 - u01, u01 - 0.90), 0.0) / 0.10, 2.0);
    float top = (0.018 * mid * (1.0 - 0.5 * g) + 0.035 * outer) * Hh;
    float bot = Hh * (1.0 - lift) + 0.010 * Hh * sin(5.3 * u01 + 1.7 * t + s) * (0.4 + g)
              + 0.006 * Hh * sin(13.0 * u01 - 2.9 * t);
    float side = 0.012 * W * (0.3 + g) * yv * yv;
    float xl = side * sin(1.6 * t + s) + 0.025 * W * g * yv;
    float xr = W - side * sin(1.4 * t + 2.0 * s + 1.0) - 0.025 * W * g * yv;
    float fw = max(length(fwidth(v_local)), 1e-5);
    float dIn = min(min(Y - top, bot - Y), min(X - xl, xr - X));
    float alpha = clamp(dIn / fw + 0.5, 0.0, 1.0);
    if (alpha <= 0.0) return vec4(0.0);

    // 厚度：褶壁（视线斜穿）、折边、纱线不匀；绷紧时变薄
    vec2 P = vec2(X + pleat, Yc);
    float fwp = length(fwidth(P));
    float weft = fbm(vec2(P.x * 1.6, P.y * 95.0) + s, 3, fwp * 95.0, 5) - 0.5;
    float warp = fbm(vec2(P.x * 95.0, P.y * 1.6) - s, 3, fwp * 95.0, 9) - 0.5;
    float cloud = fbm(P * 6.0 + s * 3.0, 4, fwp * 6.0, 13) - 0.5;
    float pt = 0.010;                           // 平纹的经纬交错（放大到看得见的尺度）
    float fade = 1.0 - smoothstep(0.25, 0.7, fwp / pt);
    float plain = sin(P.x / pt * 6.2831853) * sin(P.y / pt * 6.2831853) * fade;
    float edge = min(min(Y - top, bot - Y), min(X - xl, xr - X));
    float hem = smoothstep(0.050, 0.030, edge);
    float tau = 1.0 * (1.0 + 1.4 * hx * hx + 0.9 * hem) * (1.0 + 0.16 * weft + 0.16 * warp + 0.10 * cloud + 0.05 * plain)
              * (1.0 - 0.25 * clamp(g, 0.0, 1.0));
    float T = exp(-tau);

    // 太阳很高：竖直垂着的布背面只被斜照，透过来的光少；风把下摆推开、背面转向太阳时，布一下子被照透。
    // 用 E 的 1.4 次方加大这一差别（布的透光对入射角很敏感，斜照时大部分光被纱线表面散射掉）
    float E = pow(max(dot(-n, sun_dir), 0.0), 1.4);
    vec3 trans = sun_col * (E * 0.95 + 0.03) * T * vec3(1.0, 0.92, 0.76);
    vec3 albedo = vec3(0.90, 0.85, 0.74);
    vec3 front = amb_col * albedo * (0.6 + 0.4 * clamp(n.y * 2.0 + 0.5, 0.0, 1.0)) * (1.0 + 0.06 * cloud);

    // 背面的红字：隔着布看发虚发浅，只挡住透过来的光
    float bk = textureLod(backp, vec2(P.x / W, vc), 2.0).r * back_k;
    trans *= mix(vec3(1.0), vec3(0.82, 0.36, 0.25), bk * 0.80);

    // 正面的印字：染料渗进布纹；正面看去只比布深一些，逆光下挡住透过来的光，显得很深
    vec2 uvg = vec2((P.x / W - gbox.x) / gbox.z + 0.5, (vc - gbox.y) / gbox.w + 0.5);
    float ink = 0.0;
    if (uvg.x > -0.05 && uvg.x < 1.05 && uvg.y > -0.05 && uvg.y < 1.05) {
        float sharp = texture(glyph, uvg).r;
        float soft = textureLod(glyph, uvg, 2.0).r;
        ink = max(sharp, soft * 0.45) * (0.90 + 0.35 * (weft + warp) + 0.15 * cloud);
        ink = clamp(ink, 0.0, 1.0) * ink_k;
    }
    vec3 inkf = albedo * vec3(0.78, 0.68, 0.58);
    vec3 col = mix(front + trans, amb_col * inkf + trans * vec3(0.16, 0.10, 0.07), ink * 0.94);

    // 烧：发黄 → 焦褐 → 焦黑 → 烧穿，边上一圈暗红余烬
    if (burn_p > -0.5) {
        float d = texture(burnmap, vec2(X / W, vc)).r;
        float yel = smoothstep(burn_p + 0.62, burn_p + 0.20, d);
        float brn = smoothstep(burn_p + 0.16, burn_p + 0.03, d);
        float chr = smoothstep(burn_p + 0.035, burn_p + 0.006, d);
        // 布上原先看不见的字被烤出来：先于布本身变成焦褐色（米汤、牛奶写的字受热变褐，是同一个道理）
        float hw = texture(heatw, vec2(P.x / W, vc)).r * smoothstep(burn_p + 0.50, burn_p + 0.36, d);
        col = mix(col, col * vec3(1.0, 0.76, 0.42), yel * 0.85);
        col = mix(col, col * vec3(0.26, 0.13, 0.05) + amb_col * 0.05, hw * 0.93);
        col = mix(col, col * vec3(0.48, 0.26, 0.11), brn * 0.85);
        col = mix(col, vec3(0.03, 0.022, 0.018), chr);
        float fl = 0.6 + 0.4 * vnoise(vec2(X * 26.0, Yc * 26.0) + vec2(0.0, -t * 7.0), 41);
        float ember = exp(-pow((d - burn_p) / 0.010, 2.0)) * fl;
        col += vec3(1.5, 0.34, 0.06) * ember;
        alpha *= smoothstep(burn_p - 0.001, burn_p + 0.004, d);
    }
    return vec4(col * alpha, alpha);
}
"""

register_material("sheet_b", CLOTH_GLSL, defaults={
    "sh_box": (0.0, 0.0, 1.0, 1.0), "sh_seed": 0.3, "t_gust": 1e6, "slack": 1.0, "swing_k": 1.0, "creases": 1.0,
    "gbox": (0.5, 0.47, 0.8, 0.45), "ink_k": 1.0, "back_k": 1.0, "burn_p": -1.0,
    "sun_col": (3.0, 2.75, 2.3), "amb_col": (0.32, 0.30, 0.28), "sun_dir": (0.301, 0.933, -0.201)})


# ---------------------------------------------------------------- 排布

TEXT = L.trad(L.lyric(5).split("　")[0])          # 陽光和襯布
SW, GAP = 2.9, 0.46                                # 每张布宽、间隔（世界单位，与样张三的像素比例相同）
N = len(TEXT)
X0 = -(N * SW + (N - 1) * GAP) / 2                 # 第一张左缘
ROPE_Y0 = 2.62                                     # 绳子在一排中间的高度
SAG = 0.006                                        # 绳子下垂：两根杆子在一排之外，中间最低


def rope_y(x):
    """晾衣绳的高度：两根杆子在一排之外（x = ±15），绳子在中间垂得最低。"""
    return ROPE_Y0 + SAG * (np.asarray(x, float) ** 2) - SAG * 0.0


HEIGHTS = [5.2, 4.95, 5.3, 5.05, 5.2]


def sheet_geom(k):
    """第 k 张布：(左缘 x, 上沿 y, 宽, 高)。"""
    x0 = X0 + k * (SW + GAP)
    return x0, float(rope_y(x0 + SW / 2)), SW, HEIGHTS[k]


# ---------------------------------------------------------------- 贴图

def blank_tex():
    return cached("blank", lambda: Tex(np.zeros((4, 4), np.float32)))


def glyph_tex(ch, px=512):
    """字形覆盖率：粗宋体（思源宋体 800），放在正方形中央。"""
    def make():
        return L.glyph_mask(ch, "serif", 800, px, pad=0.03)
    return cached(("glyph", ch), lambda: Tex(make()))


def banner():
    """整条标语"東方紅　太陽升"按正常方向排好再左右翻转（从正面透过布看到的是反字）。横向覆盖整排布，
    返回 (覆盖率, 横向范围 x0, x1, 纵向范围 y0, y1)（世界单位）。"""
    def make():
        w, h = 4096, 900
        s = L.surface(w, h)
        c = s.getCanvas()
        f = L.font("serif", 900, 560, scale_x=0.92)
        text = L.trad("东方红　太阳升")
        tw = L.line_width(text, f)
        c.drawString(text, (w - tw) / 2, 690, f, L.white_paint())
        m = L.to_np(s)[..., 3]
        # 旧漆印：边缘有刷痕、墨不匀
        rng = np.random.default_rng(11)
        nz = gaussian_filter(rng.normal(0, 1, (h, w)).astype(np.float32), 3)
        m = np.clip(m * (0.82 + 0.25 * nz / nz.std()), 0, 1)
        return m[:, ::-1].copy()
    m = cached("banner", make)
    span = N * SW + (N - 1) * GAP + 1.0
    return m, (X0 - 0.5, X0 - 0.5 + span), (-2.6, 2.6 * 2 * 900 / 4096 * span / 5.2 - 2.6)


def back_tex(k):
    """第 k 张布背面透出的红字：每张布是标语布上剪下的不同一块，所以各自错开一点。"""
    def make():
        m, (bx0, bx1), _ = banner()
        x0, ytop, w, h = sheet_geom(k)
        rng = np.random.default_rng(100 + k)
        dx, dy = rng.uniform(-0.55, 0.55), rng.uniform(-0.35, 0.25)
        n = 256
        u = np.linspace(0, 1, n)
        v = np.linspace(0, 1, int(n * h / w))
        X = x0 + u * w - dx
        Y = ytop - v * h + dy                        # 世界 y
        mh, mw = m.shape
        span = bx1 - bx0
        cy = 0.15                                    # 标语条的中线高度（世界 y）
        bh = span * mh / mw                          # 标语条的世界高度
        col = ((X - bx0) / span * mw).astype(int)
        row = ((cy + bh / 2 - Y) / bh * mh).astype(int)
        cc = np.clip(col, 0, mw - 1)[None, :]
        rr = np.clip(row, 0, mh - 1)[:, None]
        out = m[rr, cc] * ((row >= 0) & (row < mh))[:, None] * ((col >= 0) & (col < mw))[None, :]
        return gaussian_filter(out.astype(np.float32), 1.0)
    return cached(("back", k), lambda: Tex(make()))


def burn_tex():
    """最右一张烧到的先后（0–1）：从左上角开始，向右、向下推进，边缘参差；右边那只夹子附近最后烧到，
    烧到最后还剩一小片焦布挂在夹子上。"""
    def make():
        w, h = SW, HEIGHTS[-1]
        nu = 384
        nv = int(nu * h / w)
        rng = np.random.default_rng(23)
        v, u = np.mgrid[0:nv, 0:nu] / np.array([nv - 1, nu - 1])[:, None, None]
        nz = gaussian_filter(rng.normal(0, 1, u.shape), 10) + 0.45 * gaussian_filter(rng.normal(0, 1, u.shape), 3)
        nz = nz / nz.std()
        r = np.hypot(u * w, v * h * 0.85)
        d = r / np.hypot(w, h * 0.85)
        d = d + 0.30 * np.exp(-(((u - 0.90) / 0.10) ** 2 + (v / 0.10) ** 2))      # 右边夹子附近
        d = d + nz * 0.045
        d = (d - d.min()) / (d.max() - d.min())
        return d.astype(np.float32)
    return cached("burn", lambda: Tex(disk("burnmap", make, "b3")))


HEAT_TEXT = L.trad(L.lyric(5).split("　")[1])     # 發酵成
HEAT_POS = [(0.19, 0.17), (0.50, 0.17), (0.81, 0.17)]   # 三个字在布上的中心（0–1，v 向下）
HEAT_SIZE = 0.84                                  # 字高（世界单位）


def heat_tex():
    """"發酵成"在最右一张布上部排成一行（布的 0–1 坐标的覆盖率）。"""
    def make():
        w, h = SW, HEIGHTS[-1]
        nu = 512
        nv = int(nu * h / w)
        out = np.zeros((nv, nu), np.float32)
        px = int(HEAT_SIZE / w * nu)
        for ch, (cu, cv) in zip(HEAT_TEXT, HEAT_POS):
            g = L.glyph_mask(ch, "serif", 800, px, pad=0.02)
            x0, y0 = int(cu * nu - px / 2), int(cv * nv - px / 2)
            out[y0:y0 + px, x0:x0 + px] = np.maximum(out[y0:y0 + px, x0:x0 + px], g)
        return out
    return cached("heat", lambda: Tex(make()))


def burn_d(u, v):
    """在 CPU 上查烧到的先后（灰片的出发点、烤字显出的时刻都按它排）。"""
    d = burn_tex().data
    d = d.astype(np.float32) / (255.0 if d.dtype == np.uint8 else 1.0)
    nv, nu = d.shape
    return d[np.clip((np.asarray(v) * (nv - 1)).astype(int), 0, nv - 1), np.clip((np.asarray(u) * (nu - 1)).astype(int), 0, nu - 1)]


# ---------------------------------------------------------------- 元素

def sheet_items(t, light, gust_times, burn_p=-1.0, opacity=1.0):
    """五张被单。light 为 (sun_col, amb_col)；gust_times 为每张被风吹开的时刻；burn_p 为最右一张的烧的进度。"""
    items = []
    sun, amb = light
    for k, ch in enumerate(TEXT):
        x0, ytop, w, h = sheet_geom(k)
        mx, mt, mb = 0.35, 0.25, 0.45
        pw, ph = w + 2 * mx, h + mt + mb
        # 布的上沿顺着绳子的斜度：整张平面绕上沿中点转一个小角度（只在画面内转动，不斜看）
        xm = x0 + w / 2
        ang = math.atan(2 * SAG * xm)
        off = np.array([0.0, mt - ph / 2])
        R = np.array([[math.cos(ang), -math.sin(ang)], [math.sin(ang), math.cos(ang)]])
        cx, cy = np.array([xm, ytop]) + R @ off
        uni = {"sh_box": (-pw / 2 + mx, ph / 2 - mt, w, h), "sh_seed": (k * 0.6180339 + 0.21) % 1.0,
               "t_gust": gust_times[k], "glyph": glyph_tex(ch),
               "gbox": (0.5, 0.57 if k == N - 1 else 0.47, 0.80 * 1.0, 0.80 * w / h),
               "heatw": heat_tex() if k == N - 1 else blank_tex(),
               "backp": back_tex(k), "sun_col": tuple(sun), "amb_col": tuple(amb),
               "burnmap": burn_tex(), "burn_p": burn_p if k == N - 1 else -1.0, "seed": (k * 0.37) % 1.0}
        items.append(Plane(None, center=(cx, cy, Z_SHEET), size=(pw, ph), rot=(0, 0, math.degrees(ang)),
                           material="sheet_b", uniforms=uni, group="past", opacity=opacity, stack=f"sheet{k}"))
    return items


# ---------------------------------------------------------------- 晾衣绳与夹子

ROPE_GLSL = r"""
uniform float rope_y0;
uniform float rope_sag;
uniform float rope_r;
uniform vec3 rope_rim;
vec4 material(vec4 base) {
    float x = v_wpos.x, y = v_wpos.y;
    float yr = rope_y0 + rope_sag * x * x;
    float d = (y - yr) / sqrt(1.0 + pow(2.0 * rope_sag * x, 2.0));
    float fw = max(length(fwidth(v_wpos.xy)), 1e-5);
    float a = clamp((rope_r - abs(d)) / fw + 0.5, 0.0, 1.0);
    if (a <= 0.0) return vec4(0.0);
    // 三股绞成的麻绳：斜向的股纹；逆光下是深色，上沿被太阳镶一道亮边
    float q = d / rope_r;
    float strand = 0.5 + 0.5 * sin((x * 0.9 + d * 1.6) / (rope_r * 1.3) * 3.14159);
    float fade = 1.0 - smoothstep(0.15, 0.5, fw / rope_r);
    vec3 col = vec3(0.16, 0.12, 0.09) * (0.75 + 0.5 * mix(0.5, strand, fade)) * (0.8 + 0.25 * (1.0 - abs(q)));
    col += rope_rim * smoothstep(0.35, 0.95, q) * (0.6 + 0.4 * mix(0.5, strand, fade));
    return vec4(col * a, a);
}
"""
register_material("rope_b", ROPE_GLSL, defaults={"rope_y0": ROPE_Y0, "rope_sag": SAG, "rope_r": 0.024,
                                                 "rope_rim": (1.1, 0.95, 0.7)})


def rope_items(t):
    return [Plane(None, center=(0.0, ROPE_Y0 + 0.8, Z_SHEET + 0.01), size=(34.0, 2.2), material="rope_b",
                  group="past", stack="rope")]


PEG_H = 0.24                                       # 夹子高（世界单位，比真实比例略大，远看也认得出）


def peg_tex():
    """木夹子的抠图（Commons：Clothespin-2459e.jpg，Loadmaster，CC BY-SA 3.0）：白底上的木头和弹簧按饱和度与
    明暗抠出，转成竖直、夹口朝下，按逆光压暗，朝上的一侧镶亮边。"""
    def make():
        from PIL import Image
        from common import IMG
        im = Image.open(IMG / "Clothespin-2459e.jpg").convert("RGB")
        a = np.asarray(im, np.float32) / 255
        sat = a[..., 0] - a[..., 2]
        dark = 1 - a.mean(2)
        m = np.clip((sat - 0.05) / 0.06, 0, 1) + np.clip((dark - 0.25) / 0.15, 0, 1)
        m = gaussian_filter(np.clip(m, 0, 1), 1.0)
        rgba = np.dstack([a, m])
        pim = Image.fromarray((rgba * 255).astype(np.uint8), "RGBA").rotate(57, expand=True, resample=Image.BICUBIC)
        r = np.asarray(pim, np.float32) / 255
        ys, xs = np.nonzero(r[..., 3] > 0.3)
        r = r[ys.min() - 4:ys.max() + 5, xs.min() - 4:xs.max() + 5]
        # 缩到高 256
        h, w = r.shape[:2]
        pim = Image.fromarray((r * 255).astype(np.uint8), "RGBA").resize((max(8, int(w * 256 / h)), 256), Image.LANCZOS)
        r = np.asarray(pim, np.float32) / 255
        col, al = r[..., :3], r[..., 3]
        lu = col.mean(2, keepdims=True)
        wood = col * 0.42 * np.array([1.0, 0.86, 0.68])
        top = np.clip(1 - np.arange(r.shape[0]) / (r.shape[0] * 0.35), 0, 1)[:, None, None]
        edge = np.clip(al - gaussian_filter(al, 2.0), 0, 1)[..., None]
        wood = wood + edge * np.array([1.6, 1.3, 0.9]) * (0.4 + top)
        return np.dstack([wood, al]).astype(np.float32)
    return cached("peg", lambda: Tex(make()))


def peg_items(t):
    tex = peg_tex()
    h, w = tex.data.shape[:2]
    pw = PEG_H * w / h
    items = []
    for k in range(N):
        x0, ytop, w_, h_ = sheet_geom(k)
        for side in (0.10, 0.90):
            x = x0 + w_ * side
            y = float(rope_y(x))
            items.append(Plane(tex, center=(x, y - PEG_H * 0.18, Z_SHEET + 0.02), size=(pw, PEG_H), group="past",
                               stack="rope"))
    return items
