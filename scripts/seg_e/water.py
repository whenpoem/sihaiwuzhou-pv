"""穿过锁孔以后的世界（L20–L22）：水下、沉钟、字环、风筝线、"手"字，以及上升途中一层层压下来的过去。

所有函数都在水下世界自己的坐标里给出元素（水面 y = 0，主平面 z = 0）；scene.py 在门这一侧把它们整体平移到门后。
每个函数的参数 cam 是 (x, y, H)：水下镜头的画面中心与画面高。
"""
import math

import numpy as np

import common  # noqa: F401
import look
import plan
from plan import T, BAR
from flatcam import cached, ease, ramp
from engine import Particles, Plane, Tex, TextPlane, dot_atlas

import uw as UW

FOV = 30.0
K = 1.0 / (2.0 * math.tan(math.radians(FOV / 2)))
WARM = np.array(look.C["warm"])
RED = np.array(look.C["red"])
L20 = plan._CHARS[19]
L21 = plan._CHARS[20]
L22 = plan._CHARS[21]
KICK1 = BAR(63)                                   # 106.76：钟声
KICK2 = BAR(65)                                   # 110.19："染"
KICK3 = BAR(67)                                   # 113.62："前"

# ---------------------------------------------------------------- 钟

BELL_X = 0.45
BELL_H = 1.55


def bell_y(t):
    """钟心的高度：缓缓下沉；"多"字前后开始加速，"沉重"时沉出画面下方。"""
    y = -1.12 - 0.16 * (t - 106.0)
    u = max(t - 108.30, 0.0)
    return y - 0.5 * 5.2 * u * u * (1.0 - 0.25 * min(u, 1.2))


def bell_roll(t):
    """下沉时轻轻摆动；钟声那一下震一震。"""
    r = 1.6 * math.sin(0.9 * (t - 106.0)) + 0.6 * math.sin(2.1 * t)
    u = t - KICK1
    if u > 0:
        r += 2.2 * math.exp(-u / 0.35) * math.sin(2 * math.pi * 3.2 * u)
    return r


def bell_items(t, U):
    if t > 110.0:
        return []
    tex = cached("bell_tex", lambda: Tex(UW.bell_rgba()))
    size, crown, lip = UW.bell_geometry(BELL_H)
    y = bell_y(t)
    u = dict(U, obj_top=y + BELL_H / 2, obj_bot=y - BELL_H / 2, caust_k=1.6, obj_gain=1.9, obj_vis=22.0)
    return [Plane(tex, center=(BELL_X, y, 0.0), size=size, rot=(0, 0, bell_roll(t)), group="past", material="uw_obj",
                  uniforms=u)]


def bell_crown(t):
    size, crown, lip = UW.bell_geometry(BELL_H)
    a = math.radians(bell_roll(t))
    return np.array([BELL_X - math.sin(a) * crown[1], bell_y(t) + math.cos(a) * crown[1]])


# ---------------------------------------------------------------- 水体、水面、光柱、悬浮颗粒

def back_items(t, cam, U):
    """镜头在水下时是水体，穿出水面以后是夜色（越往上越亮，透出最上面的冷白光）。"""
    x, y, H = cam
    d = H * K
    z = -40.0
    s = H * (d - z) / d
    mat = "uw_back" if y < 0.0 else "e_air"
    return [Plane(None, center=(x, y, z), size=(s * 1.9, s * 1.1), group="past", material=mat, uniforms=U,
                  bias=200.0)]


def surface_items(t, cam, U):
    x, y, H = cam
    return [Plane(None, center=(x, 0.0, -19.0), size=(80.0, 52.0), rot=(0, 90, 0), group="past", material="uw_surface",
                  uniforms=dict(U, surf_k=1.0), bias=60.0)]


RAYS = [(-5.2, -15.0, 4.0, 0.15), (-2.4, -11.0, 3.2, 0.62), (0.6, -13.5, 3.8, 0.33), (2.9, -9.0, 2.8, 0.81),
        (5.4, -12.0, 3.6, 0.47), (-0.9, -6.5, 2.2, 0.27), (1.9, -5.0, 1.9, 0.91), (-3.6, -4.2, 2.0, 0.71)]


def ray_items(t, cam, U):
    x, y, H = cam
    if y > 0.0:
        return []
    items = []
    deep = 1.0 if y < -0.3 else max(0.0, (-y) / 0.3)
    for rx, rz, w, seed in RAYS:
        L = 11.0
        tilt = 9.0
        cx = rx - math.sin(math.radians(tilt)) * L / 2
        items.append(Plane(None, center=(cx, -L / 2 + 0.05, rz), size=(w, L), rot=(0, 0, -tilt), blend="add",
                           group="past", material="uw_rays",
                           uniforms=dict(U, ray_k=1.05 * deep, ray_n=2.0 + w * 0.6, ray_seed=seed)))
    return items


N_MOTES = 2600


def mote_items(t, cam, U):
    """水里悬浮的细小颗粒：分布在镜头前后的一大片空间里，各自缓慢漂移；近的大而虚、远的小而淡。"""
    def make():
        rng = np.random.default_rng(31)
        n = N_MOTES
        p = np.c_[rng.uniform(-9, 9, n), rng.uniform(-14, 0.2, n), rng.uniform(-14, 3.6, n)].astype(np.float32)
        ph = rng.uniform(0, 2 * np.pi, (n, 3)).astype(np.float32)
        sz = rng.lognormal(np.log(0.016), 0.35, n).astype(np.float32)
        br = rng.uniform(0.25, 1.0, n).astype(np.float32)
        return p, ph, sz, br, dot_atlas(64, 0.0)
    p, ph, sz, br, atlas = cached("motes", make)
    x, y, H = cam
    if y > 0.0:
        return []
    drift = np.c_[0.10 * np.sin(0.21 * t + ph[:, 0]), 0.05 * np.sin(0.17 * t + ph[:, 1]) + 0.012 * t,
                  0.06 * np.sin(0.13 * t + ph[:, 2])].astype(np.float32)
    pos = p + drift
    pos[:, 1] = np.where(pos[:, 1] > 0.0, pos[:, 1] - 14.2, pos[:, 1])
    d = H * K
    dz = d - pos[:, 2]
    near = np.clip((pos[:, 2] - 1.0) / 2.5, 0, 1)                    # 越靠近镜头越大越虚
    size = sz * (1.0 + 3.5 * near)
    depth = np.exp(np.minimum(pos[:, 1], 0.0) / 7.0)
    a = br * depth * (0.55 - 0.40 * near) * np.clip(dz / 1.0, 0, 1)
    vis = (np.abs(pos[:, 0] - x) < dz * 0.55 * H / d * 1.9 + 0.2) & (np.abs(pos[:, 1] - y) < dz * 0.55 * H / d + 0.2) & (dz > 0.3)
    if not vis.any():
        return []
    col = np.c_[0.55 * a, 0.95 * a, 1.0 * a, a][vis].astype(np.float32)
    return [Particles(atlas, pos[vis], size[vis], None, col, blend="add", group="past")]


# ---------------------------------------------------------------- 钟声的字环

RING_TEXT = "好像早晨八九點鐘的太陽"
RINGS = [(KICK1, 1.0), (KICK1 + 0.24, 0.75), (KICK1 + 0.52, 0.5)]


def ring_items(t, U):
    """钟声化成一圈圈向外扩散的旧字：每一圈是"好像早晨八九點鐘的太陽"排成的圆，两遍首尾相接；
    圈越扩越大、字越来越虚、越来越淡，声音发闷，扩散也越来越慢。"""
    if t < KICK1 or t > KICK1 + 4.0:
        return []
    atlas = cached("ring_atlas", lambda: UW.ring_atlas(RING_TEXT))
    nlev = 5
    pos, sizes, rots, uvs, cols = [], [], [], [], []
    for t0, amp in RINGS:
        age = t - t0
        if age <= 0 or age > 3.6:
            continue
        cx, cy = BELL_X, bell_y(t0) - 0.05
        r = 0.88 + 3.7 * (1.0 - math.exp(-age / 1.15))
        a = amp * (1.0 - math.exp(-age / 0.07)) * math.exp(-age / 0.95)
        if a < 0.01:
            continue
        lev = min(age / 0.55, nlev - 1.001)
        li = int(lev)
        f = lev - li
        chars = RING_TEXT * 2
        n = len(chars)
        h = 0.21 + 0.12 * min(age, 2.0)
        for k, ch in enumerate(chars):
            ang = 2 * math.pi * k / n + 0.35 + 0.10 * age + 0.9 * (t0 - KICK1)
            wob = 1.0 + 0.025 * math.sin(3 * ang + 2.0 * age)
            px, py = cx + math.cos(ang) * r * wob, cy + math.sin(ang) * r * wob
            for lv, w in ((li, 1 - f), (li + 1, f)):
                if w <= 0.01:
                    continue
                pos.append((px, py, -0.05))
                sizes.append(h * 1.25)
                rots.append(ang - math.pi / 2)
                uvs.append(atlas.rects[f"{ch}{lv}"])
                cols.append((*(RED * 1.25), a * w))
    if not pos:
        return []
    return [Particles(atlas, np.array(pos, np.float32), np.array(sizes, np.float32), np.array(rots, np.float32),
                      np.array(cols, np.float32), np.array(uvs, np.float32), blend="over", group="past")]


# ---------------------------------------------------------------- L20 的歌词

def l20_layout():
    """L20 的十一个字：前五个竖排在钟的左边，后六个竖排在钟的右边（"又該有"在上，"多沉重"在下）。
    返回 [(字, x, y, 字高)]，y 为出现时的位置。"""
    text = look.trad(look.lyric(20)).replace("　", "")
    out = []
    for i in range(5):
        out.append((text[i], BELL_X - 1.30, -0.42 - i * 0.275, 0.235))
    for j, i in enumerate(range(5, 8)):
        out.append((text[i], BELL_X + 1.32, -0.80 - j * 0.275, 0.235))
    for j, i in enumerate(range(8, 11)):
        out.append((text[i], BELL_X + 1.32, -1.80 - j * 0.29, 0.25))
    return out


def l20_items(t, U):
    if t > 110.0:
        return []
    items = []
    fade = 1.0 - float(ease(ramp(t, 109.45, 109.95)))
    for i, (ch, x, y, h) in enumerate(l20_layout()):
        tc = L20[i]
        if t < tc - 0.03:
            continue
        a = float(ease(ramp(t, tc - 0.03, tc + 0.16))) * fade
        age = t - tc
        heavy = i >= 8
        # 字像沉在水里的东西一样慢慢往下沉；"多沉重"三个字沉得更快，落定时略一顿
        wake = 0.32 * max(t - 108.3, 0.0) ** 1.4                  # 钟加速下沉时带动周围的水，字也被带着往下走
        # "多沉重"三个字一起往下沉（按"多"出现的时刻算），彼此间距不变
        ah = max(t - L20[8], 0.0)
        sink = (0.10 * age if not heavy else 0.24 * (1 - math.exp(-ah / 0.45)) + 0.05 * ah) + wake
        glow = 1.0 + 0.6 * math.exp(-max(age, 0) / 0.25)
        if i == 3:                                       # "晨"与钟声同时，亮一下
            glow += 0.8 * math.exp(-max(t - KICK1, 0) / 0.4) if t >= KICK1 else 0.0
        items.append(TextPlane(ch, kind="serif", weight=700, height=h, color=tuple(WARM * glow), center=(x, y - sink, 0.35),
                               group="past", material="uw_text", uniforms=dict(U, txt_fog=0.12), opacity=a))
    return items


# ---------------------------------------------------------------- 风筝线（系在钟上的细绳）

def rope_shape(t, ys):
    """细绳在高度 ys 处的横向位置与"松弛程度"。L20 里钟往下沉，绳子在钟上方松松地飘；"風箏線"时被上方看不见的
    风筝拉直，带一点像拨过的弦那样的余振，随后一直绷直。"""
    cr = bell_crown(min(t, 109.3))
    taut = float(ease(ramp(t, L21[0] - 0.05, L21[2] + 0.05)))
    s = np.maximum(ys - cr[1], 0.0)
    slack = (1.0 - taut) * 0.16 * np.sin(1.9 * s - 1.3 * t) * np.clip(s / 0.8, 0, 1) \
        + (1.0 - taut) * 0.07 * np.sin(4.3 * s + 2.1 * t + 1.0) * np.clip(s / 0.5, 0, 1)
    ring = 0.0
    u = t - (L21[2] + 0.05)
    if u > 0:
        ring = 0.035 * math.exp(-u / 0.30) * np.sin(2 * math.pi * 4.0 * u) * np.sin(np.pi * np.clip((ys - cr[1]) / 6.0, 0, 1))
    x_taut = LINE_X
    x_bell = cr[0]
    base = x_bell + (x_taut - x_bell) * taut
    return base + slack + ring


LINE_X = BELL_X                                    # 风筝线绷直后的位置


def dye_front(t):
    """染红的前沿高度：从画面底部开始，"染"字（底鼓）起往上爬，"紅"字时爬出画面顶端，之后一直在镜头前方。"""
    if t < KICK2 - 0.02:
        return -99.0
    u = t - (KICK2 - 0.02)
    return -4.1 + 3.6 * (1 - math.exp(-u / 0.30)) + 2.4 * u + 1.2 * u * u


def rope_items(t, cam, U, beads=True):
    x, y, H = cam
    d = H * K
    y0, y1 = y - 0.62 * H, y + 0.62 * H
    cr = bell_crown(min(t, 109.3))
    if t < 109.3:
        y0 = max(y0, cr[1])
    if y1 <= y0:
        return []
    n = int((y1 - y0) / H * 1400) + 20
    ys = np.linspace(y0, y1, n).astype(np.float32)
    xs = rope_shape(t, ys)
    atlas = cached("rope_dot", lambda: dot_atlas(32, 0.7))
    front = dye_front(t)
    red = np.clip((front - ys) / 0.25, 0, 1)                         # 前沿以下是红的，前沿处有一小段渐变
    wet = np.exp(-np.abs(ys - front) / 0.12) * (front > -50)
    white = np.array([0.70, 0.86, 0.92])
    depth = np.exp(np.minimum(ys, 0.0) / 7.0)[:, None]
    base = white[None, :] * (0.55 + 0.45 * depth)
    rc = (RED * 1.25)[None, :]
    col = base * (1 - red[:, None]) + rc * red[:, None] + wet[:, None] * np.array([0.25, 0.05, 0.03])
    above = np.clip(1.0 - ys / 0.05, 0.25, 1.0) if cam[1] < 0 else np.ones_like(ys)   # 从水下看不到水面以上的部分
    import l21
    a = np.ones(n, np.float32) * above * l21.bead_gaps(t, ys)
    w = H / 1080 * 3.6
    pos = np.c_[xs, ys, np.full(n, 0.02)].astype(np.float32)
    cols = np.c_[col, a].astype(np.float32)
    items = [Particles(atlas, pos, np.full(n, w, np.float32), None, cols, blend="over", group="past")]
    return items
