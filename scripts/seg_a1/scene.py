"""前奏（A1，0.0–27.0 秒，帧 0–1619）：旧纸上的老照片随鼓点一张张翻开，从六十年代翻到新世纪，再横移到纸上
印着的片名与署名；片名化成灰尘，落在纸上，接主歌一。

全段和主歌一用同一张旧纸、同一盏台灯（handoff.paper_items），镜头一直俯视纸面（平面镜头 FlatCam）。
0–7.3 秒鼓还没进来：台灯慢慢亮起，暖光在纸上铺开，纸的左侧是一叠背面朝上的照片，最上面那张背面用钢笔写着
年月和地点，镜头极慢地推近。7.3 秒鼓声进来，照片开始一张张翻过来（album.py），每一张落下的一刻是一下鼓点，
开始每两拍一张，越往后越密。最后一张翻过以后，镜头沿纸面横移到纸中央，片名"四海五洲"一个字一个字印在纸上
（墨褐色宋体，像旧书的扉页），下面印上一行褪色红的旧字和三行署名。24.5 秒起的四下底鼓上，片名的四个字
依次褪去，字迹化成灰尘飘在灯光里，27.0 秒前落定在纸面上，此后的画面就是 handoff.paper_frame。

    python scene.py preview | sheet 输出.png 秒,秒,... [--size 640x360] | still 秒 输出.png
"""
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "style"))
sys.path.insert(0, str(HERE.parent / "film"))
import look  # noqa: E402
import plan  # noqa: E402
from plan import BAR  # noqa: E402
from flatcam import FlatCam, cached, ease, ramp, run  # noqa: E402
import handoff as HO  # noqa: E402
from engine import FrameSpec, Particles, TextPlane, dot_atlas  # noqa: E402
import album as AL  # noqa: E402

T0, T1 = 0.0, HO.T_PAPER
T_END = 26.95                       # 此后为交接画面

CAM = FlatCam([
    (0.0, -12.2, 0.30, 15.0),
    (7.2, -12.4, 0.25, 13.4),
    (13.8, -13.4, 0.20, 12.6),
    (16.5, -0.4, 0.15, 14.2),
    (24.3, 0.0, 0.05, 12.7),
    (26.5, *HO.PAPER_CAM),
    (27.5, *HO.PAPER_CAM),
], fov=30.0)

# 台灯：先暗，0.6 秒起亮起来，灯丝刚通电时闪一下
def lamp(t):
    u = ramp(t, 0.6, 4.8)
    flick = 0.0
    if 0.6 < t < 1.1:
        flick = 0.10 * math.sin((t - 0.6) * 40.0) * (1.1 - t) / 0.5
    return float(np.clip(0.03 + 0.97 * ease(u) ** 1.4 + flick * u, 0.0, 1.0))


# ---------------------------------------------------------------- 片名、旧字与署名

TITLE = "四海五洲"
EM_T = 2.3
PITCH_T = 1.32                       # 字距（em）
Y_T = 1.75
T_TITLE = [15.91, 16.33, 16.55, 16.87]           # 四个字依次印上，落在鼓点上
RED = "四海翻騰雲水怒　五洲震盪風雷激"
EM_R, Y_R, T_RED = 0.52, Y_T - 1.95, 17.19
CREDITS = [("原唱", "星尘"), ("词曲", "TOPKINGCREAM"), ("PV", "leaderone、opus")]
EM_C, Y_C0, DY_C = 0.42, Y_R - 1.25, 0.70
T_CRED = [17.62, 18.48, 19.33]
BREAKS = [24.48, 24.69, 24.90, 25.12]            # 四个字依次褪去
T_FADE_REST = (24.40, 25.30)                     # 旧字和署名褪去
INK = tuple(float(x) for x in look.C["ink"])


def press(t, t0):
    """印上去的那一下：0.06 秒里墨色到位，字略微从大缩回原大。"""
    u = ramp(t, t0, t0 + 0.06)
    s = 1.0 + 0.05 * (1.0 - ease(ramp(t, t0, t0 + 0.14)))
    return u, s


def title_x(k):
    return (k - 1.5) * EM_T * PITCH_T


def text_items(t):
    out = []
    for k, ch in enumerate(TITLE):
        a, s = press(t, T_TITLE[k])
        a *= 1.0 - ease(ramp(t, BREAKS[k], BREAKS[k] + 0.40))
        if a > 0.002:
            out.append(TextPlane(ch, kind="serif", weight=520, height=EM_T * s, color=INK,
                                 center=(title_x(k), Y_T, 0.003), opacity=0.92 * a, blend="multiply",
                                 group="past", valign="middle"))
    rest = 1.0 - ease(ramp(t, *T_FADE_REST))
    a, s = press(t, T_RED)
    if a * rest > 0.002:
        out.append(TextPlane(RED, kind="fang", height=EM_R * s, color=tuple(look.C["red"] * 1.05),
                             center=(0.0, Y_R, 0.003), opacity=0.75 * a * rest, blend="multiply", group="past",
                             valign="middle", tracking=0.10))
    for j, (role, name) in enumerate(CREDITS):
        a, s = press(t, T_CRED[j])
        if a * rest <= 0.002:
            continue
        y = Y_C0 - j * DY_C
        out.append(TextPlane(role, kind="serif", weight=400, height=EM_C, color=INK, center=(-0.35, y, 0.003),
                             opacity=0.62 * a * rest, blend="multiply", group="past", align="right", valign="middle"))
        out.append(TextPlane(name, kind="serif", weight=400, height=EM_C, color=INK, center=(0.35, y, 0.003),
                             opacity=0.85 * a * rest, blend="multiply", group="past", align="left", valign="middle"))
    return out


# ---------------------------------------------------------------- 片名化成灰尘

def dust_plan():
    """每粒灰尘从片名的哪一笔飘起、何时飘起、飘到多高；落点与落定时刻用 handoff.dust_layout 的。"""
    def make():
        from engine import glyph_path
        import skia
        pos, size, land = HO.dust_layout()
        n = len(pos)
        rng = np.random.default_rng(1964)
        # 在四个字的笔画里均匀取点：把字形栅格化后在墨迹像素里随机抽
        pts = []
        for k, ch in enumerate(TITLE):
            px = 128
            s = look.surface(px, px)
            c = s.getCanvas()
            f = look.font("serif", 520, px * 0.88)
            b = skia.Rect()
            f.measureText(ch, bounds=b)
            c.drawString(ch, (px - b.width()) / 2 - b.left(), (px - b.height()) / 2 - b.top(), f, look.white_paint())
            m = look.to_np(s)[..., 3]
            ys, xs = np.nonzero(m > 0.5)
            pts.append((xs, ys, px))
        src = np.zeros((n, 2))
        t0 = np.zeros(n)
        for i in range(n):
            k = i % 4
            xs, ys, px = pts[k]
            j = rng.integers(len(xs))
            src[i] = (title_x(k) + (xs[j] / px - 0.5) * EM_T * 0.95, Y_T - (ys[j] / px - 0.5) * EM_T * 0.95)
            t0[i] = BREAKS[k] + rng.uniform(0.0, 0.35)
        hz = rng.uniform(0.8, 2.6, n)
        ph = rng.uniform(0, 2 * np.pi, (n, 2))
        return src, t0, hz, ph
    return cached("a1_dust_plan", make)


def floating_dust(t):
    """飘在灯光里、还没落定的灰尘：从字迹里升起，飘一会儿，再按 handoff 的落点和时刻落到纸上。"""
    pos, size, land = HO.dust_layout()
    src, t0, hz, ph = dust_plan()
    on = (t >= t0) & (t < land)
    if not on.any():
        return []
    i = np.nonzero(on)[0]
    u = (t - t0[i]) / np.maximum(land[i] - t0[i], 1e-3)
    up = np.sin(np.pi * np.clip(u, 0, 1)) ** 0.8
    e = u * u * (3 - 2 * u)
    x = src[i, 0] + (pos[i, 0] - src[i, 0]) * e + 0.25 * np.sin(t * 1.7 + ph[i, 0]) * up
    y = src[i, 1] + (pos[i, 1] - src[i, 1]) * e + 0.20 * np.sin(t * 1.3 + ph[i, 1]) * up
    z = 0.004 + hz[i] * up
    P = np.c_[x, y, z]
    # 飘起时被灯照亮，越高越亮
    glow = 0.55 + 0.45 * up
    col = np.c_[np.outer(glow, [1.35, 1.22, 1.0]), np.full(len(i), 0.9)]
    dot = cached("a1_dot", lambda: dot_atlas(64, 0.3))
    p = Particles(dot, P, size[i] * (1.0 + 0.6 * up), None, col, blend="add", group="past")
    p.bias = -1000.0
    return [p]


# ---------------------------------------------------------------- 组装

def frame(t):
    if t >= T_END:
        return HO.paper_frame(t)
    cam, _ = CAM(t)
    paper, light = HO.paper_items(t)
    light.stack, light.bias = None, -500.0           # 灯光乘在纸和照片上，照片也被台灯照亮
    items = [paper] + AL.items(t) + text_items(t) + [light] + floating_dust(t)
    dust = HO.dust_items(t)
    for d in dust:
        d.bias = -1000.0
    items += dust
    g = {k: dict(v) for k, v in HO.GRADE_PAST.items()}
    g["final"] = {"fade": 1.0 - lamp(t), "fade_color": (0.0, 0.0, 0.0)}
    return FrameSpec(cam, items, grade=g)


def subframes(t):
    """翻照片和横移时多取几个子帧。"""
    if 7.0 <= t < 16.8:
        return 4
    return 2


SUBFRAMES = subframes

if __name__ == "__main__":
    run(frame, "前奏", T0, T1, plan.ROOT / "renders" / "seg_a1", subframes=subframes)
