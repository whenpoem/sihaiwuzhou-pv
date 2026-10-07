"""片头的老照片：旧纸上一叠背面朝上的照片，随鼓点一张张翻过来，时间从六十年代走到新世纪。

照片取自 Wikimedia Commons 的公开授权照片（见 assets/images/credits_seg_a1.json），按年代做成当年冲印的样子：
六十年代是带花边的黑白小照片，七十年代是白边黑白照，八十年代是褪色的白边彩照，九十年代是无边的光面彩照，
新世纪是数码冲印。背面是相纸的背面，不写字：早年的相纸发黄，八十年代以后的相纸背面有斜向的水印线。

翻照片像翻书页：右边是背面朝上的一叠，左边是翻过来、正面朝上的一摞，两者之间有一条竖直的"书脊"，每张照片
绕它转半圈，落在左边那摞上，落下的一刻正好是一下鼓点。结尾（seg_h/ending.py）的纸面上，这摞照片还在原处。
"""
import math
import sys
import zlib
from pathlib import Path

import numpy as np
from PIL import Image, ImageFilter

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "style"))
sys.path.insert(0, str(HERE.parent / "film"))
import look  # noqa: E402
from flatcam import cached  # noqa: E402
from engine import Plane, Tex  # noqa: E402

ROOT = HERE.parents[1]
IMG = ROOT / "assets" / "images"
CACHE = ROOT / "data" / "cache" / "seg_a1"
VERSION = 3

HINGE_X = -12.4                 # "书脊"的位置
PILE = (-18.1, 0.1)             # 翻过来的那摞照片的中心
GAP = 0.30                      # 照片边缘离书脊的距离
FLIP = 0.30                     # 翻一张所用的时间（秒），落下的一刻是鼓点

# 各年代照片的样式：(宽, 高)（世界单位，1 单位约 1.3 厘米）、边框、颜色处理
ERA = {
    1960: dict(size=(5.6, 5.6), border=0.075, deckle=True, tone="sepia"),
    1970: dict(size=(7.0, 5.0), border=0.06, deckle=False, tone="bw"),
    1980: dict(size=(8.4, 6.0), border=0.05, deckle=False, tone="faded"),
    1990: dict(size=(11.0, 7.4), border=0.0, deckle=False, tone="gloss", stamp=True),
    2000: dict(size=(11.0, 7.4), border=0.0, deckle=False, tone="digital"),
}

# (文件名, 年代, 背面的字, 是否竖放)。文件名为空时用占位图
PHOTOS = [
    ("1965-5_1965年_北京市果品公司_销售香蕉.jpg", 1960, "", False),
    ("1965-6_1965年_北京灯泡厂_高压水银灯泡.jpg", 1960, "", False),
    ("Pekín_barrios_1978_01.jpg", 1970, "", False),
    ("Pekín_barrios_1978_06.jpg", 1970, "", False),
    ("Pekín_calles_1978_02.jpg", 1970, "", False),
    ("Shanghai_Bund_1987_1_.jpg", 1980, "", False),
    ("Shanghai_street_in_the_1980_s.jpg", 1980, "", False),
    ("Traffic_circle_with_pedestrian_overcrossing_China_1987.jpg", 1980, "", False),
    ("Guangzhou_trolleybuses_from_behind_150_and_another_1991_.jpg", 1990, "", False),
    ("Peking_5_.jpg", 1990, "", False),
    ("Peking_6_.jpg", 1990, "", False),
    ("Shanghai_Gasse-20150516-RM-114217.jpg", 2000, "", False),
    ("Shanghai_Lujiazui_night_skyline_2017_-_Flickr.jpg", 2000, "", False),
]
# 每张落下的鼓点（秒）：开始每两拍一张，越往后越密
LAND = [7.33, 8.19, 9.05, 9.69, 10.34, 10.76, 11.19, 11.62, 12.05, 12.48, 12.90, 13.33, 13.76]


def _rng(key):
    return np.random.default_rng(zlib.crc32(key.encode("utf-8")))


def _placeholder(i, era):
    rng = _rng(f"ph{i}")
    h, w = 600, 900
    a = np.ones((h, w, 3), np.float32) * rng.uniform(0.3, 0.6, 3)
    return a


def _front(i):
    """第 i 张照片的正面（带边框，按年代调色），float32 RGBA，A 为花边形状。"""
    fn, era, _, portrait = PHOTOS[i]
    st = ERA[era]
    W, H = st["size"]
    if portrait:
        W, H = H, W
    px = 900
    ph = int(px * H / W)
    if fn and (IMG / fn).exists():
        im = Image.open(IMG / fn).convert("RGB")
        # 按照片的宽高比居中裁切
        r = W / H
        iw, ih = im.size
        if iw / ih > r:
            nw = int(ih * r)
            im = im.crop(((iw - nw) // 2, 0, (iw - nw) // 2 + nw, ih))
        else:
            nh = int(iw / r)
            im = im.crop((0, (ih - nh) // 2, iw, (ih - nh) // 2 + nh))
        a = np.asarray(im.resize((px, ph), Image.LANCZOS), np.float32) / 255
    else:
        a = _placeholder(i, era)
        a = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).resize((px, ph)), np.float32) / 255
    rng = _rng(f"front{i}")
    lum = a @ np.array([0.30, 0.59, 0.11], np.float32)
    tone = st["tone"]
    if tone == "sepia":
        g = np.clip((lum - 0.03) / 0.92, 0, 1) ** 1.05
        a = g[..., None] * np.array([1.0, 0.93, 0.80]) + (1 - g[..., None]) * np.array([0.06, 0.05, 0.04])
    elif tone == "bw":
        g = np.clip((lum - 0.02) / 0.95, 0, 1)
        a = g[..., None] * np.array([0.98, 0.97, 0.94]) + (1 - g[..., None]) * np.array([0.05, 0.05, 0.05])
    elif tone == "faded":
        # 八十年代的彩照：黑位抬起、青色褪去偏品红黄，饱和度低
        m = a.mean(2, keepdims=True)
        a = m + (a - m) * 0.62
        a = 0.10 + a * 0.84
        a = a * np.array([1.06, 0.96, 0.84])
    elif tone == "gloss":
        m = a.mean(2, keepdims=True)
        a = m + (a - m) * 0.90
        a = 0.03 + a * 0.95
        a = a * np.array([1.04, 0.99, 0.92])
    else:
        a = 0.01 + a * 0.98
    a = np.clip(a, 0, 1).astype(np.float32)
    # 颗粒：越早的照片越粗
    gr = {"sepia": 0.05, "bw": 0.04, "faded": 0.03, "gloss": 0.015, "digital": 0.006}[tone]
    from scipy.ndimage import gaussian_filter
    n = gaussian_filter(rng.normal(0, 1, a.shape[:2]).astype(np.float32), 0.8)
    a = np.clip(a + gr * n[..., None], 0, 1)
    # 边框
    b = st["border"]
    alpha = np.ones(a.shape[:2], np.float32)
    if b > 0:
        bw = int(px * b * min(1.0, H / W) * 0.9)
        paper = np.array([0.95, 0.93, 0.87]) if tone != "faded" else np.array([0.96, 0.95, 0.91])
        out = np.ones((ph + 2 * bw, px + 2 * bw, 3), np.float32) * paper
        out[bw:bw + ph, bw:bw + px] = a
        a = out
        alpha = np.ones(a.shape[:2], np.float32)
        if st["deckle"]:
            # 花边：边缘一圈小波浪
            hh, ww = alpha.shape
            yy, xx = np.mgrid[0:hh, 0:ww]
            d = np.minimum(np.minimum(xx, ww - 1 - xx), np.minimum(yy, hh - 1 - yy)).astype(np.float32)
            along = np.where(np.minimum(xx, ww - 1 - xx) < np.minimum(yy, hh - 1 - yy), yy, xx).astype(np.float32)
            wave = (np.abs(((along / (bw * 0.55)) % 2.0) - 1.0)) * bw * 0.32
            alpha = np.clip((d - wave) / 1.5, 0, 1)
    # 旧照片的边角磨损与泛黄
    hh, ww = alpha.shape
    yy, xx = np.mgrid[0:hh, 0:ww] / np.array([hh, ww])[:, None, None]
    edge = np.minimum(np.minimum(xx, 1 - xx), np.minimum(yy, 1 - yy))
    age = {"sepia": 0.10, "bw": 0.07, "faded": 0.05, "gloss": 0.02, "digital": 0.0}[tone]
    a = a * (1 - age * np.exp(-edge / 0.05))[..., None] * np.array([1.0, 0.98, 0.93]) ** (age * 10)
    return np.dstack([np.clip(a, 0, 1), alpha]).astype(np.float32)


def _date_stamp(a, back):
    """九十年代傻瓜相机在照片右下角印的橙色日期。"""
    import skia
    hh, ww = a.shape[:2]
    yr = back.split()[-1] if back else "95.08"
    yy_, mm = yr.split(".")[:2]
    txt = f"'{yy_[-2:]}  {int(mm)}  {int(_rng(back).integers(1, 28))}"
    s = look.surface(ww, hh)
    c = s.getCanvas()
    f = look.font("sans", 700, hh * 0.055)
    f.setScaleX(0.85)
    c.drawString(txt, ww * 0.70, hh * 0.92, f, look.white_paint())
    m = look.to_np(s)[..., 3]
    from scipy.ndimage import gaussian_filter
    glow = gaussian_filter(m, 2.5)
    col = np.array([1.0, 0.55, 0.12], np.float32)
    a = a * (1 - m[..., None] * 0.8) + col * m[..., None] * 0.95 + col * glow[..., None] * 0.35
    return np.clip(a, 0, 1)


def _back(i):
    """第 i 张照片的背面：相纸背面的颜色，钢笔字或冲印编号。"""
    import skia
    fn, era, txt, portrait = PHOTOS[i]
    W, H = ERA[era]["size"]
    if portrait:
        W, H = H, W
    px = 900
    ph = int(px * H / W)
    col = {1960: (0.93, 0.90, 0.82), 1970: (0.94, 0.92, 0.86), 1980: (0.96, 0.95, 0.92),
           1990: (0.97, 0.97, 0.96), 2000: (0.98, 0.98, 0.98)}[era]
    rng = _rng(f"back{i}")
    from scipy.ndimage import gaussian_filter
    n = gaussian_filter(rng.normal(0, 1, (ph, px)).astype(np.float32), 6)
    a = np.ones((ph, px, 3), np.float32) * np.array(col) * (1 + 0.03 * n[..., None])
    s = look.surface(px, ph)
    c = s.getCanvas()
    if era >= 1980:
        # 八十年代以后的相纸背面有斜向的水印线
        p = skia.Paint(AntiAlias=True, Color=skia.Color4f(1, 1, 1, 0.25), StrokeWidth=2)
        for k in range(-8, 16):
            c.drawLine(k * px * 0.12, 0, k * px * 0.12 + ph * 0.5, ph, p)
        m = look.to_np(s)[..., 3]
        a = a * (1 - m[..., None] * 0.35)
    return np.dstack([np.clip(a, 0, 1), np.ones((ph, px), np.float32)]).astype(np.float32)


def textures(i):
    def make():
        f = CACHE / f"photo_{i}_v{VERSION}_{zlib.crc32(PHOTOS[i][0].encode()):08x}.npz"
        if f.exists():
            d = np.load(f)
            fr, bk = d["front"].astype(np.float32), d["back"].astype(np.float32)
        else:
            fr, bk = _front(i), _back(i)
            CACHE.mkdir(parents=True, exist_ok=True)
            np.savez_compressed(f, front=fr.astype(np.float16), back=bk.astype(np.float16))
        return Tex(fr), Tex(bk), fr.shape[1] / fr.shape[0]
    return cached(f"a1_photo_{i}", make)


def dims(i):
    _, era, _, portrait = PHOTOS[i]
    W, H = ERA[era]["size"]
    st = ERA[era]
    if st["border"] > 0:
        e = 2 * st["border"] * min(W, H) * 0.9
        W, H = W + e, H + e
    return (H, W) if portrait else (W, H)


def poses():
    """每张照片在右边那叠里的位置与转角、在左边那摞里的位置与转角。"""
    def make():
        out = []
        for i in range(len(PHOTOS)):
            rng = _rng(f"pose{i}")
            W, H = dims(i)
            sx = HINGE_X + GAP + W / 2 + rng.normal(0, 0.15)
            sy = PILE[1] + rng.normal(0, 0.25)
            px = HINGE_X - GAP - W / 2 + rng.normal(0, 0.35)
            py = PILE[1] + rng.normal(0, 0.45)
            out.append(((sx, sy, float(rng.normal(0, 3.0))), (px, py, float(rng.normal(0, 5.0)))))
        return out
    return cached("a1_poses", make)


def _shadow(center, size, rot, z, k):
    """照片在纸上的软影子（乘在纸上）。"""
    w, h = size
    return Plane(cached("a1_shadow", _shadow_tex), center=(center[0] + 0.12, center[1] - 0.18, z),
                 size=(w * 1.06, h * 1.07), rot=(0, 0, rot), blend="multiply", opacity=k, group="past")


def _shadow_tex():
    from scipy.ndimage import gaussian_filter
    a = np.zeros((128, 128), np.float32)
    a[14:114, 14:114] = 1
    a = gaussian_filter(a, 4)
    v = 1 - 0.55 * a
    return Tex(np.dstack([v, v, v, np.ones_like(v)]).astype(np.float32))


def flip_state(i, t):
    """0 还在右边那叠里，1 已经落到左边；之间是翻转的进度（0–1）。"""
    t1 = LAND[i]
    u = (t - (t1 - FLIP)) / FLIP
    return float(np.clip(u, 0, 1))


def _photo_planes(i, center, roll, phi, z):
    """一张照片：正面和背面两块平面背靠背，只画此刻朝向镜头的一面。phi 为绕书脊翻过的角度：0 背面朝上
    （在右边那叠里），180 正面朝上（在左边那摞里）。正面的法线为 (sin φ, 0, −cos φ)，引擎的 yaw 取 180 − φ；
    背面的法线相反，yaw 取 −φ。两者的贴图横轴都随照片一起转，所以照片是一个刚体。"""
    fr, bk, _ = textures(i)
    w, h = dims(i)
    if phi > 90.0:
        return [Plane(fr, center=(center[0], center[1], z), size=(w, h), rot=(180.0 - phi, 0, roll), group="past")]
    return [Plane(bk, center=(center[0], center[1], z), size=(w, h), rot=(-phi, 0, roll), group="past")]


def items(t):
    """t 时刻纸上的照片：右边那叠、正在翻的一张、左边那摞。"""
    P = poses()
    out = []
    n = len(PHOTOS)
    zstep = 0.006
    # 左边那摞：已经落下的照片，后落下的在上面
    for i in range(n):
        if flip_state(i, t) >= 1.0:
            (px, py, pr) = P[i][1]
            z = 0.004 + zstep * i
            if i == max(j for j in range(n) if flip_state(j, t) >= 1.0):
                out.append(_shadow((px, py), dims(i), pr, z - 0.001, 0.45))
            out += _photo_planes(i, (px, py), pr, 180.0, z)
    # 右边那叠：还没翻的照片，最先要翻的在最上面
    for i in range(n - 1, -1, -1):
        if flip_state(i, t) > 0.0:
            continue
        (sx, sy, sr) = P[i][0]
        z = 0.004 + zstep * (n - i)
        if i == min(j for j in range(n) if flip_state(j, t) <= 0.0):
            out.append(_shadow((sx, sy), dims(i), sr, z - 0.001, 0.45))
        out += _photo_planes(i, (sx, sy), sr, 0.0, z)
    # 正在翻的一张：绕书脊转半圈，中心离书脊的距离、纵向位置和转角从右边那叠过渡到左边那摞
    for i in range(n):
        u = flip_state(i, t)
        if not 0.0 < u < 1.0:
            continue
        e = u * u * (3 - 2 * u)
        phi = 180.0 * e
        (sx, sy, sr), (px, py, pr) = P[i]
        w, h = dims(i)
        r = (sx - HINGE_X) + ((HINGE_X - px) - (sx - HINGE_X)) * e
        a = math.radians(phi)
        cx = HINGE_X + r * math.cos(a)
        cz = 0.05 + r * math.sin(a)
        cy = sy + (py - sy) * e
        roll = sr + (pr - sr) * e
        out.append(_shadow((cx + cz * 0.15, cy - cz * 0.12), (max(w * abs(math.cos(a)), 0.6) + 0.4, h), roll, 0.0035,
                           0.5 * (1 - 0.4 * math.sin(a))))
        out += _photo_planes(i, (cx, cy), roll, phi, cz)
    return out


def pile_items(at_end=True):
    """结尾用：全部翻完以后的那摞照片。"""
    return items(1e9)
