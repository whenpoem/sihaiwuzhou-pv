"""间奏一：报纸字栏铺成的海（侧视）。

海由十几层正对镜头的长条组成，前后排开：最近的一层在船身前面掠过，最远的几层挤在地平线上。每一层是一栏栏
竖排的仿宋字栏（那个年代报纸常见的版式，栏与栏之间有细栏线），每栏的上沿高低不同，连起来就是浪：浪沿着栏的
序号传播，每栏随浪整体升降，栏里的字跟着栏一起动。镜头横移时，近的层掠过得快，远的层慢（视差）；高速时
着色器在快门时间内沿横向多次采样，得到平滑的运动模糊。

纸面是新闻纸的米灰色，油墨略有洇开和深浅，标题处用粗宋体大字，偶尔有网点印的图片块；不出现任何真实报头。
字栏本身微微发光（被落日余晖透过的薄纸），间奏后半天色变暗，字栏一栏栏熄灭。
"""
import math

import numpy as np
import skia
from scipy import ndimage

from common import cached, disk_cached, look, hash01
from engine import Plane, Tex, register_material

STRIP_W, STRIP_H = 256, 2048        # 每种字栏贴图的尺寸（像素）
N_STRIPS = 8
LINES = 5                           # 每栏 5 行竖排字

# 字栏里的文字：那个年代公开的诗词与口号（本片旧字表里的原文），按栏打乱
CORPUS = look.trad("".join([
    "大海航行靠舵手萬物生長靠太陽雨露滋潤禾苗壯",
    "四海翻騰雲水怒五洲震盪風雷激",
    "一萬年太久只爭朝夕",
    "抓革命促生產",
    "備戰備荒為人民",
    "團結緊張嚴肅活潑",
    "全國山河一片紅",
    "形勢大好不是小好",
    "東方紅太陽升",
    "不管風吹浪打勝似閒庭信步",
    "長夜難明赤縣天一唱雄雞天下白",
    "待到山花爛漫時她在叢中笑",
    "世界是你們的也是我們的但是歸根結底是你們的",
    "你們青年人朝氣蓬勃正在興旺時期好像早晨八九點鐘的太陽希望寄託在你們身上",
    "換了人間",
    "千萬不要忘記階級鬥爭",
]))


def strips():
    """N_STRIPS 种字栏，横排在一张 (STRIP_H, N_STRIPS*STRIP_W) 的灰度图里：1 为纸，0 为墨。"""
    def make():
        rng = np.random.default_rng(29)
        W, H = N_STRIPS * STRIP_W, STRIP_H
        surf = look.surface(W, H)
        c = surf.getCanvas()
        c.clear(skia.Color4f(1, 1, 1, 1))
        ink = skia.Paint(AntiAlias=True, Color=skia.Color4f(0, 0, 0, 1))
        body = look.font("fang", 400, 40)
        head = look.font("serif", 900, 112)
        sub = look.font("sans", 800, 64)
        rule = skia.Paint(AntiAlias=True, Color=skia.Color4f(0, 0, 0, 1), StrokeWidth=2.0)
        pitch_x = (STRIP_W - 16) / LINES
        for s in range(N_STRIPS):
            x0 = s * STRIP_W
            c.drawLine(x0 + 4, 0, x0 + 4, H, rule)
            c.drawLine(x0 + STRIP_W - 4, 0, x0 + STRIP_W - 4, H, rule)
            y = 10.0
            k = int(rng.integers(len(CORPUS)))
            while y < H - 40:
                r = rng.uniform()
                if r < 0.12 and y < H - 300:
                    # 标题：两三个粗宋体大字竖排，居中
                    n = int(rng.integers(2, 4))
                    for i in range(n):
                        ch = CORPUS[(k + i) % len(CORPUS)]
                        adv = head.measureText(ch)
                        c.drawString(ch, x0 + (STRIP_W - adv) / 2, y + 100 + i * 118, head, ink)
                    k += n
                    y += n * 118 + 30
                    c.drawLine(x0 + 14, y - 12, x0 + STRIP_W - 14, y - 12, rule)
                elif r < 0.18 and y < H - 380:
                    # 网点印的图片块：一块由大小不一的圆点组成的灰色区域（不画具体内容）
                    hgt = rng.uniform(200, 330)
                    yy, xx = np.mgrid[0:int(hgt):9, 0:STRIP_W - 30:9]
                    tone = 0.25 + 0.6 * (0.5 + 0.5 * np.sin(yy / hgt * 3.0 + rng.uniform(0, 6))) * \
                        (0.6 + 0.4 * np.cos(xx / 60.0 + rng.uniform(0, 6)))
                    for (py, px), tv in zip(zip(yy.ravel(), xx.ravel()), tone.ravel()):
                        c.drawCircle(x0 + 15 + px + 4.5, y + py + 4.5, 4.6 * math.sqrt(tv), ink)
                    y += hgt + 24
                elif r < 0.24:
                    # 小标题：一行黑体
                    ch = CORPUS[k % len(CORPUS)]
                    for i in range(2):
                        c.drawString(CORPUS[(k + i) % len(CORPUS)], x0 + 30 + i * 100, y + 60, sub, ink)
                    k += 2
                    y += 86
                else:
                    # 正文：5 行竖排仿宋，一段 6–16 字
                    n = int(rng.integers(6, 16))
                    for li in range(LINES):
                        xx = x0 + STRIP_W - 8 - (li + 1) * pitch_x + (pitch_x - 40) / 2
                        for i in range(n):
                            ch = CORPUS[(k + li * 7 + i) % len(CORPUS)]
                            c.drawString(ch, xx, y + 38 + i * 44, body, ink)
                    k += n * LINES
                    y += n * 44 + 18
        img = look.to_np(surf)[..., 0]
        # 油墨洇开一点、深浅不匀
        img = ndimage.gaussian_filter(img, 0.6)
        blot = ndimage.gaussian_filter(rng.normal(0, 1, img.shape), 20) * 4
        img = np.clip(1 - (1 - img) * (0.82 + 0.18 * np.tanh(blot)), 0, 1)
        return img.astype(np.float32)
    return disk_cached("sea_strips_v1", make)


def strips_tex():
    return cached("sea_strips_tex", lambda: Tex(strips(), repeat=True))


SEA_GLSL = """
uniform sampler2D strip;
uniform float y_w;             // 这一层的水面基准高度
uniform float cw;              // 每栏宽（世界单位）
uniform float amp;             // 浪高
uniform float text_k;          // 每世界单位对应字栏贴图的多少（竖直）
uniform float blur_dx;         // 快门时间里镜头横移的距离（世界单位）
uniform float lit;             // 字栏的整体亮度（被余晖照亮、透光）
uniform float off_t0;          // 字栏开始熄灭的时刻
uniform float off_span;        // 全部熄灭用的时间
uniform vec3 fog_col;
uniform float fog;             // 这一层融进天色的程度
uniform vec3 paper;
uniform vec3 inkc;
uniform float wave_t;          // 浪的时间
uniform float rise;            // 涨潮：水面整体抬起的量（之前在画面下面）
uniform float x_shift;         // 本子帧镜头相对帧中心时刻镜头的横向位移：减去它，各子帧画出的都是帧中心时刻的海
uniform float t_c;             // 帧中心时刻
uniform float lseed;

float col_top(float j) {
    float a = sin(j * 0.17 - wave_t * 1.9 + lseed * 6.0) * 0.60
            + sin(j * 0.061 + wave_t * 0.7 + lseed * 2.0) * 0.45
            + sin(j * 0.71 - wave_t * 4.3 + lseed) * 0.16
            + (rnd(ivec2(int(j), 7), int(lseed * 100.0)) - 0.5) * 0.22;
    return y_w + rise + amp * a;
}

vec4 sample_at(float x, float y) {
    float j = floor(x / cw);
    float u = x / cw - j;
    if (u < 0.035 || u > 0.965) return vec4(0.0);       // 栏与栏之间的细缝
    float top = col_top(j);
    float dd = top - y;
    if (dd < 0.0) return vec4(0.0);
    float h = rnd(ivec2(int(j), 11), 3);
    float sidx = floor(h * 8.0);
    float voff = rnd(ivec2(int(j), 13), 5);
    vec2 uv = vec2((sidx + u) / 8.0, voff + dd * text_k);
    vec2 g = vec2(1.0 / (8.0 * cw), text_k);
    float p = textureGrad(strip, uv, vec2(dFdx(x) * g.x, dFdx(y) * g.y), vec2(dFdy(x) * g.x, dFdy(y) * g.y)).r;
    vec3 c = mix(inkc, paper, p);
    c *= 0.80 + 0.35 * rnd(ivec2(int(j), 17), 9);
    // 逆着天光：栏面大体在阴影里，上沿附近被余晖照亮、透出暖色，越往下越暗（像浪谷与水深）
    float band = exp(-dd / (amp * 0.7 + 0.025));
    float deep = exp(-dd / (amp * 3.0 + 0.12));
    float tj = off_t0 + off_span * rnd(ivec2(int(j), 19), 2);
    float on = 1.0 - smoothstep(tj, tj + 0.35, t_c);
    float glowk = lit * on;
    vec3 col = c * ((0.07 + 0.30 * deep) * (0.25 + 0.75 * on) * lit + 0.95 * band * glowk);
    col += vec3(1.0, 0.80, 0.55) * max(glowk, 0.55 * on * step(0.01, lit)) * smoothstep(0.012, 0.0, dd) * 1.1;      // 上沿迎着天光的亮边
    float side = smoothstep(0.035, 0.12, u) * smoothstep(0.965, 0.88, u);
    col *= 0.70 + 0.30 * side;
    return vec4(col, 1.0);
}

vec4 material(vec4 base) {
    float x = v_wpos.x - x_shift, y = v_wpos.y;
    vec4 acc = vec4(0.0);
    int n = blur_dx > 0.002 ? 9 : 1;
    for (int i = 0; i < 9; i++) {
        if (i >= n) break;
        float s = n == 1 ? 0.0 : (float(i) / float(n - 1) - 0.5);
        acc += sample_at(x + s * blur_dx, y);
    }
    acc /= float(n);
    acc.rgb = mix(acc.rgb, fog_col * acc.a, fog);
    return acc;
}
"""
register_material("d_sea", SEA_GLSL, defaults={
    "y_w": 0.0, "cw": 0.22, "amp": 0.06, "text_k": 0.5, "blur_dx": 0.0, "lit": 1.0, "off_t0": 1e4, "off_span": 3.0,
    "fog_col": (0.5, 0.45, 0.4), "fog": 0.0, "paper": (0.86, 0.82, 0.72), "inkc": (0.10, 0.09, 0.085),
    "wave_t": 0.0, "rise": 0.0, "lseed": 0.0, "x_shift": 0.0, "t_c": 0.0})


# ---------------------------------------------------------------- 天空：黄昏的照片，风格化，再一点点暗成夜

TAN_D = 0.043                       # 假想的镜头俯角：地平线在画面中线以上约 0.08 个画面高
SKY_PHOTO = "Sunset_sky_water.jpg"  # CC0，地平线在照片高度的 49.7%
SKY_HORIZON = 0.497


def sky_rgba():
    """黄昏天空：取照片地平线以上的部分，降低粉紫的饱和度，云偏琥珀、高处偏靛青；地平线附近往下延续一段光带
    （会被字栏的海盖住）。返回浮点 RGB。"""
    def make():
        from PIL import Image
        from common import IMG
        im = Image.open(IMG / SKY_PHOTO).convert("RGB")
        a = np.asarray(im, np.float32) / 255
        h, w = a.shape[:2]
        hz = int(h * SKY_HORIZON) - 34              # 地平线上远处的城市轮廓（现代建筑与摩天轮）一并裁掉
        sky = ndimage.gaussian_filter(a[:hz], (1.4, 1.4, 0))      # 去掉照片天空里的 JPEG 噪声，颗粒交给调色
        lum = sky.mean(2, keepdims=True)
        sat = sky - lum
        sky = lum + sat * 0.45
        yy = np.linspace(0, 1, hz)[:, None, None]
        warmc = np.array([1.06, 0.86, 0.62])
        cool = np.array([0.62, 0.72, 0.98])
        tint = cool * (1 - yy ** 2.2) + warmc * yy ** 2.2
        sky = sky * tint * 0.95
        # 地平线以下延伸一段：最后一行模糊后渐暗
        ext = np.repeat(ndimage.gaussian_filter(sky[-6:].mean(0), (8, 0))[None], hz // 3, axis=0)
        ext = ext * np.linspace(1.0, 0.6, hz // 3)[:, None, None]
        out = np.concatenate([sky, ext], 0)
        return np.clip(out, 0, 1.5).astype(np.float32)
    return disk_cached("sea_sky_v3", make)


def sky_tex():
    return cached("sea_sky_tex", lambda: Tex(sky_rgba()))


SKY_Z = -6000.0


def sky_item(cam, t, k=1.0, night=0.0):
    """天空贴在无穷远处：位置随镜头走，地平线对准水面的地平线（画面中线以上 TAN_D·K 个画面高）。"""
    img = sky_rgba()
    h, w = img.shape[:2]
    top_frac = 0.75                              # 照片里地平线以上的部分占全图高度的比例（见 sky_rgba）
    x, y, H, _ = cam.state(t)
    D = H * cam.K
    s = (D - SKY_Z) / D
    Hs = H * s
    hy = y + TAN_D * cam.K * Hs                  # 地平线
    ww = Hs * 16 / 9 * 1.08
    hh = ww * h / w
    if hh * top_frac < Hs * (0.5 + TAN_D * cam.K) * 1.05:
        hh = Hs * (0.5 + TAN_D * cam.K) * 1.05 / top_frac
        ww = hh * w / h
    cy = hy + hh * (top_frac - 0.5)
    col = np.array([1.0, 1.0, 1.0]) * (1 - night) + np.array([0.30, 0.38, 0.62]) * night
    return Plane(sky_tex(), center=(x, cy, SKY_Z), size=(ww, hh), color=tuple(col * k), group="past")


# ---------------------------------------------------------------- 海的各层

# (z, 栏宽, 浪高, 水面相对抬高)：最近的两层在船身前面，其余在后面一直排到地平线
LAYERS = [(2.4, 0.40, 0.22, 0.0), (1.5, 0.34, 0.19, 0.0), (0.85, 0.30, 0.16, 0.17), (0.28, 0.25, 0.12, 0.06),
          (-0.35, 0.22, 0.09, 0.0)] +          [(z, 0.22, 0.08, 0.0) for z in (-1.3, -2.8, -5.0, -8.5, -14.0, -23.0, -37.0, -60.0, -96.0, -155.0, -250.0,
                                          -400.0, -650.0)]
HORIZON_GLOW = np.array([1.0, 0.70, 0.42])
NIGHT_SEA = np.array([0.10, 0.12, 0.18])


def layer_y(y_w, z, base):
    """一层的水面高度：按假想俯角，越远的层水面越高，远处收进地平线。"""
    return y_w - z * TAN_D + base


def sea_items(cam, t, y_w, blur_dx=0.0, rise=0.0, lit=1.0, glow=None, night=0.0, off_t0=1e4, off_span=3.0,
              bow=None, min_z=-1e9, x_shift=0.0, t_c=None):
    """海的各层。rise 为水面相对正常位置抬起的量（以画面高为单位，负数表示还在画面下面），lit 为字栏亮度，
    night 为入夜程度。运动模糊全部在着色器里做：blur_dx 为快门时间内镜头横移的距离；x_shift 为本子帧镜头相对
    帧中心时刻的位移，减去它以后，同一帧的各个子帧画出同一幅海，模糊量不随子帧数变化。"""
    t_c = t if t_c is None else t_c
    x, y, H, _ = cam.state(t)
    D = H * cam.K
    out = []
    glow = HORIZON_GLOW if glow is None else glow
    fogc = glow * (1 - night) + NIGHT_SEA * night
    for i, (z, cw, amp, base) in enumerate(LAYERS):
        if z < min_z:
            continue
        s = (D - z) / D
        Hs = H * s
        rz = rise * Hs                              # 涨潮：每一层都从画面下沿以下升上来（按画面高度计）
        yl = layer_y(y_w, z, base) + rz
        bottom = y - Hs * 0.55
        top = yl + amp * 1.6 + 0.02
        if top < bottom:
            continue
        hgt = top - bottom
        wid = Hs * 16 / 9 * 1.06 + abs(blur_dx) * 2
        dist = D - z
        fog = 1.0 - math.exp(-max(dist - 4.0, 0.0) / 70.0)
        uni = {"strip": strips_tex(), "y_w": layer_y(y_w, z, base), "cw": cw, "amp": amp,
               "text_k": (STRIP_W / cw) / STRIP_H, "blur_dx": blur_dx, "lit": lit * (0.30 if z > 0.5 else (0.45 if z > 0 else 1.0)),
               "off_t0": off_t0 - 0.02 * i,
               "off_span": off_span, "fog_col": tuple(fogc * lit), "fog": fog * 0.85, "wave_t": t_c,
               "rise": rz, "lseed": hash01(i, 5), "x_shift": x_shift, "t_c": t_c}
        out.append(Plane(None, center=(x, (top + bottom) / 2, z), size=(wid, hgt), group="past", material="d_sea",
                         uniforms=uni))
    return out


# ---------------------------------------------------------------- 船、水花与桅灯

SAIL_SCALE = 1.0 / 680


def junk_items(pos, t, billow=0.0, tilt=0.0, k_light=1.0, opacity=1.0, night=0.0, scale=1.0, main_bias=None):
    """整条船：pos 为船（照片 BBOX 中心）的世界坐标 (x, y, z)；tilt 为前后颠簸的转角（度）；billow 为帆被风鼓起
    的程度（主帆以主桅为轴横向撑开一点，与 L18 的画法一致）。"""
    import sail as SL
    tx = SL.textures()
    x0, y0, x1, y1 = SL.BBOX
    k = SAIL_SCALE * scale
    W, H = (x1 - x0) * k, (y1 - y0) * k
    out = []
    col = np.array([1.0, 1.0, 1.0]) * k_light * (1 - night) + np.array([0.20, 0.22, 0.30]) * night * k_light
    mast_dx = ((SL.PW - 805.0) - (x0 + x1) / 2) * k
    a = math.radians(tilt)
    for key in ("hull", "fore", "mizzen", "main"):
        if key == "main":
            sx = 1.0 + 0.07 * billow
            mx0, mx1 = SL.MAIN_X
            u0, u1 = (mx0 - x0) / (x1 - x0), (mx1 - x0) / (x1 - x0)
            cx = ((mx0 + mx1) / 2 - (x0 + x1) / 2) * k
            cx = mast_dx + (cx - mast_dx) * sx
            off = np.array([cx * math.cos(a), cx * math.sin(a)])
            out.append(Plane(tx[key], center=(pos[0] + off[0], pos[1] + off[1], pos[2]), size=((mx1 - mx0) * k * sx, H),
                             uv=(u0, 0, u1, 1), rot=(0, 0, tilt), color=tuple(col * (1 + 0.25 * billow)),
                             opacity=opacity, group="past", stack="junk" if main_bias is None else "junk_main",
                             bias=0.0 if main_bias is None else main_bias))
        else:
            out.append(Plane(tx[key], center=tuple(pos), size=(W, H), rot=(0, 0, tilt), color=tuple(col),
                             opacity=opacity, group="past", stack="junk"))
    return out


def photo_to_world(px, py, pos, tilt=0.0):
    """照片像素 → 船上那一点的世界坐标（考虑颠簸转角）。"""
    import sail as SL
    x0, y0, x1, y1 = SL.BBOX
    dx = (px - (x0 + x1) / 2) * SAIL_SCALE
    dy = -(py - (y0 + y1) / 2) * SAIL_SCALE
    a = math.radians(tilt)
    return np.array([pos[0] + dx * math.cos(a) - dy * math.sin(a), pos[1] + dx * math.sin(a) + dy * math.cos(a), pos[2]])


SPRAY_Z = 0.95                    # 水花画在这个深度：在船身前面那几层浪的前面，否则会被浪挡住


def spray_items(t, bow_fn, speed_fn, t_start, k=1.0, night=0.0, cam_vx=0.0, cam_state=None, cam_K=1.866):
    """船头激起的水花：与 L15 雨点相同的"丶"形水滴，从船头吃水处沿抛物线抛起、再落回海里。
    bow_fn(t) 给出 t 时刻船头的世界坐标，speed_fn(t) 给出船速，cam_vx 为镜头的横向速度（用来让水滴顺着它在
    画面上的运动方向）。"""
    if k <= 0.001:
        return []
    import rain as RN
    rng = np.random.default_rng(41)
    n = 85
    period = 0.6
    ph = rng.uniform(0, 1, n)
    vx_r = rng.uniform(-0.6, 0.9, n)            # 相对船的横向速度：一半向前抛出，一半落在船舷边
    vy0 = rng.uniform(1.1, 2.2, n)
    vz = rng.uniform(0.05, 0.5, n)
    size = rng.uniform(0.016, 0.032, n)
    age = ((t - t_start) / period + ph) % 1.0 * period
    tb = t - age
    ok = tb >= t_start
    if not ok.any():
        return []
    idx = np.flatnonzero(ok)
    pos, ang, alpha = [], [], []
    for i in idx:
        b = bow_fn(tb[i])
        vb = speed_fn(tb[i])
        st = min(vb / 4.5, 1.0)
        if st < 0.08:
            continue
        vy = vy0[i] * (0.45 + 0.55 * st)
        a_ = age[i]
        y = b[1] + vy * a_ - 4.9 * a_ * a_
        if y < b[1] - 0.04:                     # 落回海面以后不再画
            continue
        x = b[0] + (vb + vx_r[i] * st) * a_
        pos.append((x, y, b[2] + vz[i] * a_ + 0.05))
        # 画面上的运动方向：相对镜头的速度
        dvx = vb + vx_r[i] * st - cam_vx
        dvy = vy - 9.8 * a_
        ang.append(math.atan2(dvy, dvx) - math.pi / 2)
        alpha.append(st * min(1.0, a_ / 0.03))
    if not pos:
        return []
    pos, ang, alpha = np.array(pos), np.array(ang), np.array(alpha) * k
    m = len(pos)
    sz = size[:m] if m <= len(size) else np.resize(size, m)
    if cam_state is not None:
        # 把水滴从船的深度挪到 SPRAY_Z，并按透视缩放位置和大小，使它在画面上仍落在船头
        cx, cy, H, _ = cam_state
        D = H * cam_K
        f = (D - SPRAY_Z) / (D - pos[:, 2])
        pos = np.c_[cx + (pos[:, 0] - cx) * f, cy + (pos[:, 1] - cy) * f, np.full(m, SPRAY_Z)]
        sz = sz * f
    c = np.array([1.0, 0.93, 0.82]) * (1 - night) + np.array([0.25, 0.27, 0.33]) * night
    col = np.c_[np.tile(c, (m, 1)) * alpha[:, None], alpha * 0.95]
    atlas = RN.rain_atlas()
    uv = atlas.index_uv(np.zeros(m, int))
    return [Particles_(atlas, pos, np.c_[sz, sz * 1.6], ang, col, uv)]


def Particles_(atlas, pos, size, rot, col, uv):
    from engine import Particles
    return Particles(atlas, pos, size, rot, col, uv=uv, blend="over", group="past")
