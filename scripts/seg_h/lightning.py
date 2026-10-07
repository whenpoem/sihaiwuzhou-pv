"""L36"风雷"：远处天上的两道闪电。

闪电画在看台外远处的夜空里（夜空远景前面一点），是细的、带分叉的折线：主干从云底往下，用中点位移法一层层
细分出曲折，沿途随机长出几条更细的分叉。每道闪电只亮两帧，0.07 秒后同一条通道再闪一下（回击）。闪电的
主要作用是照明：闪的那一刻，一道冷白的平行光从闪电的方向照过来，整片场地、看台和漆面上的高光跟着一亮，
云层也被照亮。"风"在左边远处，"雷"在右边远处。镜头那时是从斜上方往下看、看不到天，闪电本身不在画面里，
画面上只看到这两次冷光和漆面上的一闪；镜头看得到天时，闪电本身也会出现在天上。
"""
import math

import numpy as np
from scipy.ndimage import gaussian_filter

from common import T, cached, disk_cached
from engine import Plane, Tex

COLD = np.array([0.74, 0.85, 1.05], np.float32)
# (时刻, 天上的位置 x, 高度 z, 宽, 高, 种子)：闪电贴图的平面立在 y = 550，正对南方
BOLTS = [(T(36, 4), -420.0, 170.0, 150.0, 230.0, 11), (T(36, 5), 380.0, 160.0, 140.0, 210.0, 23)]
BOLT_Y = 320.0
FRAME = 1 / 60


def _bolt(seed):
    """一道闪电的贴图（单通道，512×768）：细的主干与分叉，外面一圈很窄的辉光。"""
    import skia
    rng = np.random.default_rng(seed)
    W, H = 512, 768

    def path(p0, p1, rough, depth):
        pts = [np.array(p0, float), np.array(p1, float)]
        for _ in range(depth):
            out = [pts[0]]
            for a, b in zip(pts[:-1], pts[1:]):
                m = (a + b) / 2
                d = b - a
                n = np.array([-d[1], d[0]]) / (np.linalg.norm(d) + 1e-6)
                m = m + n * rng.normal(0, rough * np.linalg.norm(d))
                out += [m, b]
            pts = out
        return pts

    s = skia.Surface(W, H)
    c = s.getCanvas()
    c.clear(skia.Color4f(0, 0, 0, 1))
    main = path((W * 0.5 + rng.normal(0, 30), 0), (W * 0.5 + rng.normal(0, 80), H * 0.97), 0.22, 7)

    def stroke(pts, width, alpha):
        p = skia.Path()
        p.moveTo(*pts[0])
        for q in pts[1:]:
            p.lineTo(*q)
        c.drawPath(p, skia.Paint(Color=skia.Color4f(1, 1, 1, alpha), AntiAlias=True, Style=skia.Paint.kStroke_Style,
                                 StrokeWidth=width, StrokeJoin=skia.Paint.kRound_Join))
    stroke(main, 2.6, 1.0)
    for _ in range(rng.integers(4, 7)):
        i = rng.integers(len(main) // 8, len(main) * 3 // 4)
        a = main[i]
        ang = math.atan2(main[min(i + 8, len(main) - 1)][1] - a[1], main[min(i + 8, len(main) - 1)][0] - a[0])
        ang += rng.choice([-1, 1]) * rng.uniform(0.4, 1.0)
        L = rng.uniform(80, 220)
        b = a + L * np.array([math.cos(ang), math.sin(ang)])
        br = path(a, b, 0.25, 5)
        stroke(br, 1.3, 0.75)
        if rng.random() < 0.5:
            j = len(br) // 2
            ang2 = ang + rng.choice([-1, 1]) * rng.uniform(0.3, 0.8)
            stroke(path(br[j], br[j] + rng.uniform(40, 90) * np.array([math.cos(ang2), math.sin(ang2)]), 0.25, 4),
                   0.9, 0.55)
    a = s.makeImageSnapshot().toarray()[..., 0].astype(np.float32) / 255
    return np.clip(a + gaussian_filter(a, 4) * 1.5 + gaussian_filter(a, 18) * 0.8, 0, 3).astype(np.float32)


def bolt_tex(i):
    def make():
        a = disk_cached(f"bolt{i}", lambda: _bolt(BOLTS[i][5]), "v3")
        return Tex(np.dstack([a, a, a, np.ones_like(a)]))
    return cached(f"bolt{i}", make)


def level(t, i):
    """第 i 道闪电的亮度：亮两帧，0.07 秒后回击再亮一帧，余光很快消失。"""
    t0 = BOLTS[i][0] - 0.02
    u = t - t0
    if u < 0 or u > 0.25:
        return 0.0
    k = 1.0 if u < 2 * FRAME else 0.0
    k += 0.7 if 0.07 <= u < 0.07 + FRAME else 0.0
    k += 0.25 * math.exp(-u / 0.05)
    return min(k, 1.2)


def items(t):
    out = []
    for i, (tc, x, z, w, h, _) in enumerate(BOLTS):
        k = level(t, i)
        if k <= 0.3:
            continue
        out.append(Plane(bolt_tex(i), center=(x, BOLT_Y, z), size=(w, h), rot=(0.0, 90.0, 0.0), blend="add",
                         color=tuple(COLD * 2.2 * k), group="past", bias=9.5e4))
    return out


def sky_flash(t):
    return max(level(t, 0), level(t, 1))


def field_light(t):
    """闪电的冷光：(给翻板的平行光 [(方向, 颜色)]，地面加亮的程度，给看台和灯塔材质的参数 dict 或 None)。"""
    lights, g, flash = [], 0.0, None
    for i, (tc, x, z, w, h, _) in enumerate(BOLTS):
        k = level(t, i)
        if k <= 0.005:
            continue
        d = np.array([x, BOLT_Y, z], np.float32)
        d /= np.linalg.norm(d)
        lights.append((tuple(d), tuple(COLD * 2.2 * k)))
        g += 1.1 * k
        flash = {"flash": float(k), "flash_dir": tuple(float(v) for v in d), "flash_col": tuple(float(v) for v in COLD * 2.0)}
    return lights, g, flash
