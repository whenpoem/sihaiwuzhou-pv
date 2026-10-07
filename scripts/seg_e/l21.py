"""L21：染红的风筝线、线上的旧字、张开的"手"字和穿过指缝的白色"風"字。

风筝线绷直以后，"染"字（第二下底鼓）时红色从画面底部顺着线往上爬，线上随之显出一颗颗极小的红字
"全國山河一片紅"（构思第八章 L21），线在每个字处断开，像穿过一串珠子。"手"字压在线上，竖画就是手掌和手腕，
三道横像手指：出现时略握着线，唱到"染"时红色顺着竖画往手心里渗，"不紅"时退回去；随后手指张开，"的風"的
"風"字拆成几缕白色的笔画从左边吹来，穿过两道指缝，在右边拼成"風"，始终是白色。
"""
import math

import numpy as np

import common  # noqa: F401
import look
from flatcam import cached, ease, ramp
from engine import Particles, Plane, TextPlane

import strokes as SK
from water import (LINE_X, L21, KICK2, RED, WARM, dye_front, rope_shape)

BEAD_TEXT = "全國山河一片紅"
BEAD_H, BEAD_PITCH, BEAD_GAP = 0.105, 0.142, 0.36
HAND_H = 1.05
HAND_Y = -2.33


def _hand_span():
    return HAND_Y - HAND_H * 0.62, HAND_Y + HAND_H * 0.62


def bead_positions(y0, y1):
    """线上旧字的位置：每句七个字等距排开，句与句之间空一段；避开"手"字所在的那一段。返回 [(y, 字)]。"""
    period = BEAD_PITCH * len(BEAD_TEXT) + BEAD_GAP
    out = []
    k0 = int(math.floor((y0 + 50.0) / period)) - 1
    k1 = int(math.ceil((y1 + 50.0) / period)) + 1
    hy0, hy1 = _hand_span()
    for k in range(k0, k1 + 1):
        base = -50.0 + k * period
        for j in range(len(BEAD_TEXT)):
            y = base + j * BEAD_PITCH
            ch = BEAD_TEXT[len(BEAD_TEXT) - 1 - j]            # 竖排从上往下读
            if y0 <= y <= y1 and not (hy0 < y < hy1):
                out.append((y, ch))
    return out


def bead_gaps(t, ys):
    """细线在旧字处断开（像穿过一颗颗珠子），只在染红的那一段。返回每个采样点的不透明度系数。"""
    front = dye_front(t)
    if front < -50:
        return np.ones_like(ys)
    period = BEAD_PITCH * len(BEAD_TEXT) + BEAD_GAP
    rel = (ys + 50.0) % period
    j = np.round(rel / BEAD_PITCH)
    on = (j < len(BEAD_TEXT)) & (np.abs(rel - j * BEAD_PITCH) < BEAD_H * 0.42)
    hy0, hy1 = _hand_span()
    on &= ~((ys > hy0) & (ys < hy1))
    on &= ys < front - 0.05
    return np.where(on, 0.0, 1.0)


def bead_items(t, cam, U):
    front = dye_front(t)
    if front < -50:
        return []
    x, y, H = cam
    y0, y1 = y - 0.62 * H, min(y + 0.62 * H, front)
    if y1 <= y0:
        return []
    bp = bead_positions(y0, y1)
    if not bp:
        return []
    from engine import glyph_atlas
    atlas = cached("bead_atlas", lambda: glyph_atlas(BEAD_TEXT, "fang", 400, 128))
    ys = np.array([b[0] for b in bp], np.float32)
    xs = rope_shape(t, ys)
    a = np.clip((front - ys) / 0.20, 0, 1)
    if y < 0:
        a = a * np.clip(1.0 - ys / 0.05, 0.0, 1.0)
    pos = np.c_[xs, ys, np.full(len(ys), 0.03)].astype(np.float32)
    cols = np.c_[np.tile(RED * 1.30, (len(ys), 1)), a].astype(np.float32)
    uv = atlas.uv("".join(b[1] for b in bp))
    return [Particles(atlas, pos, np.full(len(ys), BEAD_H * 1.12, np.float32), None, cols, uv, blend="over",
                      group="past")]


# ---------------------------------------------------------------- 手

def hand_geometry():
    """"手"字四笔的贴图与位置：撇和两道横是手指，竖钩是手掌和手腕，竖画正好压在风筝线上。
    返回 (笔画列表 [(Tex, em 外接框, 类型)], 字框中心, 竖画中线的 em x)。"""
    def make():
        st = SK.strokes(look.trad("手"), "serif", 800)
        vert = max(st, key=lambda s: s[1][3] - s[1][1])
        others = sorted([s for s in st if s is not vert], key=lambda s: s[1][1])      # 从上到下
        vx = vert[1][2] - 0.075
        center = (LINE_X - (vx - 0.5) * HAND_H, HAND_Y)
        return [(vert[0], vert[1], "palm")] + [(s[0], s[1], f"finger{i}") for i, s in enumerate(others)], center, vx
    return cached("hand_geo", make)


def hand_open(t):
    return float(ease(ramp(t, L21[8] + 0.04, L21[9] + 0.10)))


FINGER_ROT = (20.0, 8.0, -12.0)                   # 张开时三根"手指"各自转过的角度（度，逆时针为正）
FINGER_DY = (0.10, 0.02, -0.09)                  # 张开时上下拉开的距离（em）


def hand_items(t, U):
    t_on = L21[5]
    if t < t_on - 0.04:
        return []
    st, center, vx = hand_geometry()
    a = float(ease(ramp(t, t_on - 0.04, t_on + 0.14)))
    op = hand_open(t)
    grip = 1.0 - float(ease(ramp(t, t_on, t_on + 0.35)))       # 出现时略握紧，随即放松
    glow = 1.0 + 0.7 * math.exp(-max(t - t_on, 0) / 0.3)
    # 红色顺着竖画往手心里渗，"不紅"时退回去
    stain = float(ease(ramp(t, L21[7] - 0.1, L21[7] + 0.08))) * (1.0 - float(ease(ramp(t, L21[8], L21[9] + 0.15))))
    items = []
    for tex, (x0, y0, x1, y1), kind in st:
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        w, h = (x1 - x0) * HAND_H, (y1 - y0) * HAND_H
        pos = SK.em_to_world(cx, cy, center, HAND_H)
        ang = 0.0
        if kind.startswith("finger"):
            i = int(kind[-1])
            ang = FINGER_ROT[i] * op - (3.0, 1.5, -1.5)[i] * grip
            piv = SK.em_to_world(vx, cy, center, HAND_H)
            r = pos - piv
            c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
            pos = piv + np.array([c * r[0] - s * r[1], s * r[0] + c * r[1]]) + np.array([0.0, FINGER_DY[i] * op * HAND_H])
        col = WARM * glow
        if kind == "palm" and stain > 0.001:
            col = col * (1 - 0.40 * stain) + RED * 1.3 * 0.40 * stain
        items.append(Plane(tex, center=(pos[0], pos[1], 0.30), size=(w, h), rot=(0, 0, ang), color=tuple(col),
                           group="past", material="uw_text", uniforms=dict(U, txt_fog=0.10), opacity=a))
    return items


def finger_gaps(t):
    """两道指缝的中心（世界坐标），在竖画右侧。"""
    st, center, vx = hand_geometry()
    ys = []
    for tex, (x0, y0, x1, y1), kind in st:
        if kind.startswith("finger"):
            i = int(kind[-1])
            ys.append((y0 + y1) / 2 - FINGER_DY[i] * hand_open(t))
    ys.sort()
    return [SK.em_to_world(vx + 0.22, (ys[0] + ys[1]) / 2, center, HAND_H),
            SK.em_to_world(vx + 0.22, (ys[1] + ys[2]) / 2, center, HAND_H)]


WIND_C = (LINE_X + 1.02, -1.28 - 5 * 0.28)
WIND_H = 0.27


def wind_items(t, U):
    """"的風"的"風"：每一笔先是一缕细细的白色风线，从左边吹来、穿过两道指缝，到了右边才收成"風"的一笔；
    风线的头亮、尾巴渐淡。全程是白色。"""
    tc = L21[11]
    t_go = tc - 0.32
    if t < t_go - 0.02:
        return []
    from engine import dot_atlas
    st = SK.strokes(look.trad("風"), "serif", 700)
    gaps = finger_gaps(t)
    white = np.array([1.0, 1.04, 1.14]) * 1.08
    atlas = cached("wind_dot", lambda: dot_atlas(32, 0.5))
    items = []
    pts, cols = [], []
    for i, (tex, (x0, y0, x1, y1)) in enumerate([(q[0], q[1]) for q in st]):
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        end = SK.em_to_world(cx, cy, WIND_C, WIND_H)
        g = gaps[i % 2] + np.array([0.0, 0.025 * ((i * 5) % 3 - 1)])
        start = np.array([LINE_X - 1.9 - 0.15 * (i % 3), g[1] - 1.0 - 0.08 * ((i * 7) % 5)])   # 从左下方吹来，不压住左边那列字
        ctrl = 2 * g - 0.5 * (start + end)                      # 二次曲线在中点正好穿过指缝
        d0 = t_go + 0.03 * i
        u = ramp(t, d0, d0 + 0.42)
        if u <= 0:
            continue
        sh = u * u * (3 - 2 * u)

        def at(v):
            v = np.clip(v, 0, 1)[:, None]
            return (1 - v) ** 2 * start + 2 * (1 - v) * v * ctrl + v * v * end
        # 风线：从头往后 0.3 的一段，头亮尾淡；到达之后很快收进笔画里
        tail = np.linspace(sh, max(sh - 0.30, 0.0), 180)
        fade = (1.0 - np.linspace(0, 1, 180)) ** 1.4 * (1.0 - ramp(t, d0 + 0.40, d0 + 0.52))
        line = at(tail)
        tg = np.gradient(line, axis=0)
        nrm = np.c_[-tg[:, 1], tg[:, 0]] / np.maximum(np.hypot(tg[:, 0], tg[:, 1]), 1e-6)[:, None]
        for off, k in ((0.0, 1.0), (0.022, 0.55), (-0.018, 0.45)):   # 一缕风是几根并行的细线
            pts.append(line + nrm * off * (0.4 + 0.6 * np.linspace(0, 1, 180))[:, None])
            cols.append(fade * k * 0.75)
        # 笔画在后半程从风线的头里显出、长到原大
        k = ramp(sh, 0.55, 1.0)
        if k > 0:
            hp = at(np.array([sh]))[0]
            w, h = (x1 - x0) * WIND_H, (y1 - y0) * WIND_H
            sc = 0.5 + 0.5 * k
            items.append(Plane(tex, center=(hp[0], hp[1], 0.36), size=(w * sc, h * sc), color=tuple(white),
                               group="past", opacity=k))
    if pts:
        P = np.concatenate(pts)
        A = np.concatenate(cols)
        n = len(P)
        pos = np.c_[P, np.full(n, 0.37)].astype(np.float32)
        col = np.c_[np.tile(white, (n, 1)) * A[:, None], A].astype(np.float32)
        items.append(Particles(atlas, pos, np.full(n, 0.016, np.float32), None, col, blend="add", group="past"))
    return items


# ---------------------------------------------------------------- L21 的歌词

def l21_layout():
    """左边一列"風箏線染紅"，右边一列"心染不紅"，"的"在右列下方，"風"由飞来的笔画拼成。"""
    text = look.trad(look.lyric(21)).replace("　", "")
    out = []
    for i in range(5):
        out.append((i, text[i], LINE_X - 0.98, -1.30 - i * 0.30, 0.25))
    for j, i in enumerate(range(6, 11)):
        out.append((i, text[i], LINE_X + 1.02, -1.28 - j * 0.28, 0.25))
    return out


def l21_items(t, U):
    if t < L21[0] - 0.05 or t > 113.6:
        return []
    items = []
    fade = 1.0 - float(ease(ramp(t, 112.95, 113.45)))
    for i, ch, x, y, h in l21_layout():
        tc = L21[i]
        if t < tc - 0.03:
            continue
        a = float(ease(ramp(t, tc - 0.03, tc + 0.16))) * fade
        glow = 1.0 + 0.6 * math.exp(-max(t - tc, 0) / 0.25)
        if i == 3 and t >= KICK2:                        # "染"与第二下底鼓同时
            glow += 0.6 * math.exp(-(t - KICK2) / 0.4)
        items.append(TextPlane(ch, kind="serif", weight=700, height=h, color=tuple(WARM * glow), center=(x, y, 0.35),
                               group="past", material="uw_text", uniforms=dict(U, txt_fog=0.10), opacity=a))
    return items


def items(t, cam, U):
    return bead_items(t, cam, U) + l21_items(t, U) + hand_items(t, U) + wind_items(t, U)
