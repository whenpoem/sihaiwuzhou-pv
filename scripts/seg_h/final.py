"""L40 与结尾：回到今天，最后一句，残影，寂静里的一粒尘埃。

阳光暗下去以后，背景回到今天：一座夜里的城市，完全在焦外，只剩一个个圆形的灯光光斑。光斑由陆家嘴夜景照片
（Larry Qian，CC0，Wikimedia Commons，与副歌二的城市是同一张）算出：取照片里亮的灯光，按镜头的焦外成像做
圆盘卷积，再整体压得很暗、偏冷。最后一句是今天的白色细宋体简体，正对观众，在画面正中；镜头在这里第一次完全
停住。字的下面，前面出现过的全部旧字同时淡淡浮现，像屏幕上烧下的残影：褪色红，不透明度 15%–25%，各用当年
的字体（标语用黑体美术字，诗词用仿宋，横幅用宋体），有横排也有竖排，铺满整个画面。

结尾。音乐在第 113 小节首拍戛然而止，画面在那一帧停住，此后一切都不再动，只有淡出：白字先淡去，红色残影多停
两秒再淡去，城市的光斑随之暗下去。最后剩下一束冷白的细光，和片头一样从左上斜照下来，光里漂着一粒尘埃
（凑近看是一个极小的宋体字"尘"），然后全黑。
"""
import math

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

from common import IMG, T, cached, disk_cached, look, smooth, RED, facing_rot
from engine import Overlay, Particles, Plane, Tex, dot_atlas

T_L40 = T(40, 0)
T_CUT = 11549 / 60                 # 音乐骤停（第 113 小节首拍 192.478）之后的第一帧，画面停在这一帧
T_WHITE_OUT = (193.0, 194.4)
T_GHOST_OUT = (196.3, 197.6)
T_CITY_OUT = (195.7, 197.6)
T_BEAM_IN = (196.4, 197.5)
T_BEAM_OUT = (198.5, 199.45)
T_DIM = 188.45


# ---------------------------------------------------------------- 城市的焦外光斑

def _bokeh_city():
    """城市灯光的焦外光斑：在照片里找出亮的灯（局部最亮的点），每盏灯画成同样大小的一个圆形光斑（同一支镜头、
    同样远的灯，光斑一样大），颜色取照片里灯的颜色、去掉大半饱和度；再加一层极淡的天光。"""
    from scipy.ndimage import maximum_filter
    import skia
    src = Image.open(IMG / "Shanghai_Lujiazui_night_skyline_2017_-_Flickr.jpg").convert("RGB")
    W0, H0 = src.size                                   # 3840×2560
    h = int(W0 * 9 / 16)
    y0 = int((H0 - h) * 0.75)
    a = np.asarray(src.crop((0, y0, W0, y0 + h)).resize((960, 540), Image.LANCZOS), np.float32) / 255
    lum = a.mean(2)
    sm = gaussian_filter(lum, 1.0)
    peak = (sm == maximum_filter(sm, 15)) & (sm > 0.45)
    ys, xs = np.nonzero(peak)
    v = sm[ys, xs]
    order = np.argsort(-v)[:95]
    ys, xs, v = ys[order], xs[order], v[order]
    rng = np.random.default_rng(40)
    W, H = 1920, 1080
    acc = np.zeros((H, W, 3), np.float32)
    yy, xx = np.mgrid[-48:49, -48:49]
    for y, x, lv in zip(ys, xs, v):
        c = a[max(y - 2, 0):y + 3, max(x - 2, 0):x + 3].reshape(-1, 3).mean(0)
        c = c.mean() + (c - c.mean()) * 0.4
        if rng.random() < 0.35:                                  # 一部分是暖色的路灯
            c = c.mean() * np.array([1.25, 0.85, 0.50])
        R = 40.0 * rng.uniform(0.9, 1.1)
        d = np.hypot(xx, yy)
        disc = np.clip(R + 0.5 - d, 0, 1) * (0.85 + 0.3 * np.clip((d - R * 0.75) / (R * 0.25), 0, 1))
        disc *= 0.35 + 0.65 * rng.random() ** 2
        k = (lv - 0.4) ** 1.5 * 1.6
        X, Y = int(x * 2), int(y * 2)
        y0_, y1_ = max(Y - 48, 0), min(Y + 49, H)
        x0_, x1_ = max(X - 48, 0), min(X + 49, W)
        acc[y0_:y1_, x0_:x1_] += disc[y0_ - Y + 48:y1_ - Y + 48, x0_ - X + 48:x1_ - X + 48, None] * c * k
    acc = gaussian_filter(acc, (1.2, 1.2, 0))
    base = gaussian_filter(np.asarray(Image.fromarray((a * 255).astype(np.uint8)).resize((W, H)), np.float32) / 255,
                           (50, 50, 0)) * 0.05
    img = acc + base
    img *= np.array([0.82, 0.90, 1.06])
    yy2 = np.linspace(0, 1, H)[:, None, None]
    img *= 1.0 - 0.6 * np.exp(-((yy2 - 0.52) / 0.08) ** 2)          # 白字所在的一条压暗
    return np.clip(img * 0.42, 0, 4).astype(np.float16)


def city_tex():
    return cached("city_bokeh", lambda: Tex(disk_cached("city_bokeh", _bokeh_city, "v5").astype(np.float32)))


# ---------------------------------------------------------------- 残影

GHOSTS = [
    # (文字, 字体, 字重, 字号, x, y, 竖排, 不透明度)；x、y 为第一个字左上角的像素位置。画面中部 480–650 一条
    # 留给白字，只有两侧的竖排穿过它
    ("四海翻騰雲水怒　五洲震盪風雷激", "sans", 900, 104, 70, 60, False, 0.22),
    ("抓革命", "sans", 900, 118, 40, 230, True, 0.20),
    ("促生產", "sans", 900, 118, 1770, 230, True, 0.20),
    ("團結　緊張　嚴肅　活潑", "sans", 850, 58, 240, 215, False, 0.17),
    ("備戰　備荒　為人民", "sans", 850, 50, 1000, 220, False, 0.17),
    ("寂寞嫦娥舒廣袖", "fang", 400, 40, 230, 320, False, 0.15),
    ("不管風吹浪打　勝似閒庭信步", "fang", 400, 38, 600, 322, False, 0.15),
    ("東方紅　太陽升", "serif", 900, 54, 1200, 312, False, 0.17),
    ("好像早晨八九點鐘的太陽", "fang", 400, 40, 230, 410, False, 0.16),
    ("希望寄託在你們身上", "fang", 400, 40, 1180, 410, False, 0.16),
    ("一萬年太久　只爭朝夕", "sans", 900, 50, 1660, 230, True, 0.18),
    ("中蘇友誼萬歲", "serif", 900, 66, 220, 680, False, 0.19),
    ("形勢大好　不是小好", "sans", 850, 46, 700, 690, False, 0.17),
    ("大海航行靠舵手", "serif", 900, 62, 1160, 682, False, 0.19),
    ("待到山花爛漫時　她在叢中笑", "fang", 400, 42, 230, 790, False, 0.17),
    ("一唱雄雞天下白", "fang", 400, 42, 880, 790, False, 0.16),
    ("長夜難明赤縣天", "fang", 400, 42, 1260, 790, False, 0.16),
    ("引無數英雄競折腰", "fang", 400, 42, 560, 862, False, 0.16),
    ("換了人間", "serif", 900, 84, 1250, 846, False, 0.19),
    ("全國山河一片紅", "sans", 900, 60, 130, 620, True, 0.18),
    ("千萬不要忘記階級鬥爭", "sans", 900, 96, 300, 930, False, 0.21),
    ("世界是你們的，也是我們的，但是歸根結底是你們的", "fang", 400, 34, 330, 1040, False, 0.16),
    ("永遠忠於", "fang", 400, 48, 1380, 1012, False, 0.18),
]


def _ghosts():
    """全部旧字的残影（RGBA，1920×1080）：褪色红，各自的不透明度，轻微的模糊和错位，像屏幕上烧下的影子。"""
    import skia
    W, H = 1920, 1080
    alpha = np.zeros((H, W), np.float32)
    for text, kind, wt, size, x, y, vert, op in GHOSTS:
        s = skia.Surface(W, H)
        c = s.getCanvas()
        f = look.font(kind, wt, size, scale_x=0.94 if kind == "sans" else 1.0)
        p = skia.Paint(Color=skia.ColorWHITE, AntiAlias=True)
        if vert:
            yy = y + size * 0.88
            for ch in text:
                if ch != "　":
                    c.drawString(ch, x + (size - f.measureText(ch)) / 2, yy, f, p)
                yy += size * 1.05
        else:
            c.drawString(text, x, y + size * 0.88, f, p)
            if text == "永遠忠於":                  # 宾语留空：一段空横线
                x1 = x + f.measureText(text) + size * 0.3
                c.drawRect(skia.Rect(x1, y + size * 0.86, x1 + size * 3.2, y + size * 0.86 + 3), p)
        m = s.makeImageSnapshot().toarray()[..., 3].astype(np.float32) / 255
        alpha = alpha + m * op * (1 - alpha)
    soft = gaussian_filter(alpha, 1.2)
    alpha = np.maximum(soft, 0.85 * alpha)
    rgb = np.broadcast_to(np.array(RED * 1.15, np.float32), (H, W, 3))
    return np.dstack([rgb, alpha]).astype(np.float32)


def ghost_tex():
    return cached("ghosts", lambda: Tex(disk_cached("ghosts", _ghosts, "v2")))


# ---------------------------------------------------------------- 结尾的一束光

def _beam():
    W, H = 1920, 1080
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    # 光束轴线：从画面上缘偏左斜向右下（与片头相同的方向）
    p0 = np.array([560.0, -80.0])
    d = np.array([0.62, 0.78])
    d /= np.linalg.norm(d)
    v = np.stack([xx - p0[0], yy - p0[1]], -1)
    along = v @ d
    perp = v[..., 0] * (-d[1]) + v[..., 1] * d[0]
    w = 12.0 + 0.03 * along
    a = np.exp(-(perp / w) ** 2) * np.clip(along / 200.0, 0, 1) * np.exp(-np.clip(along, 0, None) / 1100.0)
    a += 0.18 * np.exp(-(perp / (w * 4.0)) ** 2) * np.exp(-np.clip(along, 0, None) / 800.0) * np.clip(along / 300, 0, 1)
    return np.clip(a, 0, 1).astype(np.float32)


def beam_tex():
    return cached("end_beam", lambda: Tex(disk_cached("end_beam", _beam, "v2")))


# ---------------------------------------------------------------- 组装

def screen_plane(tex, eye, basis, D, color=(1, 1, 1), opacity=1.0, blend="over", group="present", scale=1.0,
                 bias=0.0):
    """一张铺满画面、锁定在镜头前深度 D 处的平面。"""
    right, up, fwd = basis
    F = D * 0.53590
    c = eye + fwd * D
    return Plane(tex, center=tuple(c), size=(F * 16 / 9 * scale, F * scale), rot=facing_rot(basis), color=color,
                 opacity=opacity, blend=blend, group=group, bias=bias)


def white_line(t):
    """最后一句：白色细宋体简体，正对观众，在画面正中。"""
    text = look.lyric(40)
    ons = [T(40, i) for i in range(len([c for c in text if c != "　"]))]
    out_a = 1.0 - float(smooth(t, *T_WHITE_OUT))
    if t < ons[0] - 0.05 or out_a <= 0:
        return []
    size, weight = 66, 250
    f = look.font("serif", weight, size)
    adv = [f.measureText(ch) for ch in text]
    x = 960.0 - sum(adv) / 2
    out, k = [], 0
    for ch, a in zip(text, adv):
        if ch != "　":
            tc = ons[k]
            k += 1
            if t >= tc - 0.02:
                op = float(smooth(t, tc - 0.02, tc + 0.16)) * out_a
                out.append(Overlay(ch, xy=(x, 563 + size * 0.38), anchor="left-baseline", size=size, weight=weight,
                                   color=(1, 1, 1), group="present", opacity=op))
        x += a
    return out


def items(t, eye, basis):
    """L40 与结尾的元素（今天的一层，present 组）。t 为真实时刻；画面在 T_CUT 停住以后，只有淡出在变。"""
    if t < T_DIM:
        return []
    tm = min(t, T_CUT)                                   # 停住之后，所有运动都停在这一帧
    els = []
    city_a = float(smooth(t, T_DIM + 0.1, T_DIM + 0.8)) * (1.0 - float(smooth(t, *T_CITY_OUT)))
    if city_a > 0:
        breathe = 1.0 + 0.04 * math.sin(tm * 0.9) + 0.025 * math.sin(tm * 2.3 + 1.0)    # 远处灯光极轻的明暗
        els.append(screen_plane(city_tex(), eye, basis, 400.0, color=(breathe,) * 3, opacity=city_a, scale=1.04,
                                bias=300.0))
    g_a = float(smooth(t, T_L40 + 0.25, T_L40 + 1.6)) * (1.0 - float(smooth(t, *T_GHOST_OUT)))
    if g_a > 0:
        els.append(screen_plane(ghost_tex(), eye, basis, 300.0, opacity=g_a, bias=200.0))
    els += white_line(t)
    b_a = float(smooth(t, *T_BEAM_IN)) * (1.0 - float(smooth(t, *T_BEAM_OUT)))
    if b_a > 0:
        els.append(screen_plane(beam_tex(), eye, basis, 200.0, color=(0.55, 0.62, 0.72), opacity=b_a, blend="add",
                                bias=100.0))
        els += mote_items(t, eye, basis, b_a)
    return els


def mote_items(t, eye, basis, a):
    """光里漂着的灰尘，其中一粒近在焦点上，是一个极小的宋体字"尘"。"""
    right, up, fwd = basis
    rng = np.random.default_rng(1999)
    n = 26
    u = rng.uniform(0.1, 0.9, n)
    p0 = np.array([560.0, -80.0])
    d = np.array([0.62, 0.78]) / np.linalg.norm([0.62, 0.78])
    along = 200 + u * 900
    perp = rng.normal(0, 14, n)
    sx = p0[0] + d[0] * along - d[1] * perp
    sy = p0[1] + d[1] * along + d[0] * perp
    tt = t - T_BEAM_IN[0]
    sx += 6 * np.sin(tt * rng.uniform(0.2, 0.5, n) + rng.uniform(0, 6, n))
    sy += 8 * tt * rng.uniform(0.3, 1.0, n) + 5 * np.sin(tt * rng.uniform(0.2, 0.5, n))
    D = 200.0
    F = D * 0.5359
    X = (sx / 1080 - 960 / 1080) * F
    Y = (0.5 - sy / 1080) * F
    P = eye[None] + right[None] * X[:, None] + up[None] * Y[:, None] + fwd[None] * D
    size = rng.uniform(1.5, 4.0, n) / 1080 * F
    tw = 0.5 + 0.5 * np.sin(tt * rng.uniform(1.0, 3.0, n) + rng.uniform(0, 6, n))
    col = np.c_[np.ones((n, 3)) * (0.7 + 0.6 * tw[:, None]) * np.array([0.85, 0.92, 1.0]), np.full(n, a)]
    dot = cached("end_dot", lambda: dot_atlas(64, 0.5))
    els = [Particles(dot, P.astype(np.float32), size.astype(np.float32), None, col.astype(np.float32), blend="add",
                     group="present", bias=50.0)]
    # 那一粒：在光里慢慢往下漂
    mx = 1010 + 10 * math.sin(tt * 0.35)
    my = 470 + 14 * tt
    els.append(Overlay("尘", xy=(mx, my), anchor="center-middle", size=22, weight=300, color=(0.95, 0.97, 1.0),
                       group="present", opacity=a * (0.75 + 0.25 * math.sin(tt * 1.3))))
    return els
