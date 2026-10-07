"""H 段的歌词：放进画面里，一次只出一个乐句。

桥段（L33–L36）的歌词是今天的白色细宋体简体，是一个今天的人的声音，浮在巨大的红字前面。每个乐句放在那一刻
构图的空处（SPOTS 里的画面位置），字高按 1080p 下 60–80 像素。字浮在场地上方：乐句开始时，取那个画面位置
沿视线往场地走一段距离的一点作为它在空间里的位置，之后镜头移动时，这一点在画面上会移动，字跟着它移动其中
的四分之一，所以字和场地之间有一点视差，又不会随镜头大幅升降而变得太小或飞出画面。乐句的字在各自的元音起点
出现，下一个乐句开始时淡去。白字画在今天的画面层上，纯白、边缘锐利。

"为我吹一遍"跨过"吹"：风起以后，这一句被风卷起，跟着旋风转着放大、散开。

L37 的"快"就是砸碎各层的那五块字板（storm.py），这里只放"動物永不停下來"：暖白粗宋体，在画面中部偏下，避开正中
那团光，随镜头一路向前，越来越大，不停下来。L38、L39 的歌词是繁体暖白色，悬在阳光里的焦平面上，放在树叶背光的
暗处："當一顆""躁鬱的塵埃"在那颗尘埃旁边，"又從髒話中""拼湊一段"在拼字的下方；L39 的最后一个乐句就是碎片拼成的
"永遠愛她"。L40 在 final.py。
"""
import math

import numpy as np

from common import T, cached, smooth, look, WARM, INK, facing_rot
from engine import Overlay, TextPlane

# (行, 乐句序号) → (画面位置 sx, sy（0–1，左上角为原点；横排为乐句中心，竖排为第一个字的中心）, 竖排, 字高像素)
SPOTS = {
    (33, 0): (0.30, 0.26, False, 66),           # 漆面上方的空处
    (33, 1): (0.80, 0.20, True, 68),            # 竖排，贴着右上方"記"字的一笔
    (33, 2): (0.30, 0.70, False, 66),
    (34, 0): (0.66, 0.74, False, 64),           # 近处空着的漆面上方
    (34, 1): (0.50, 0.14, False, 66),           # 场地上方、看台前的暗处
    (35, 0): (0.50, 0.17, False, 66),           # 两座灯塔之间的夜空
    (35, 1): ("band", 0.0, False, 70),          # 贴在横穿全联的黑带上，随场地移动
    (36, 0): (0.50, 0.12, False, 64),
    (36, 1): ("band", 0.0, False, 76),          # 仍在黑带上，"吹"时被风卷走
}
PARALLAX = 0.25
DEPTH = 0.55                  # 字在空间里的位置：沿视线走到地面距离的这一比例处
WHITE = (1.0, 1.0, 1.0)


def phrases(n, trad=False):
    """第 n 行按全角空格分成的乐句：[(乐句文字, 第一个字的字序)]。"""
    text = look.trad(look.lyric(n)) if trad else look.lyric(n)
    out, k = [], 0
    for part in text.split("　"):
        out.append((part, k))
        k += len(part)
    return out


def _ray_point(cam, sx, sy, frac):
    eye = np.asarray(cam.eye, float)
    r, u, f = (np.asarray(v, float) for v in cam.basis())
    th = math.tan(math.radians(cam.fov / 2))
    d = f + r * (sx - 0.5) * 2 * th * 16 / 9 + u * (0.5 - sy) * 2 * th
    d /= np.linalg.norm(d)
    s = -eye[2] / d[2] if d[2] < -1e-3 else 600.0
    return eye + d * s * frac


def _project(cam, P):
    eye = np.asarray(cam.eye, float)
    r, u, f = (np.asarray(v, float) for v in cam.basis())
    th = math.tan(math.radians(cam.fov / 2))
    v = P - eye
    z = max(v @ f, 1e-3)
    return np.array([0.5 + (v @ r) / z / (2 * th * 16 / 9), 0.5 - (v @ u) / z / (2 * th)])


def bridge_items(t, cam_fn):
    out = []
    cam = None
    for n in (33, 34, 35, 36):
        ph = phrases(n)
        for ki, (text, k0) in enumerate(ph):
            t0 = T(n, k0)
            if ki + 1 < len(ph):
                t_out = T(n, ph[ki + 1][1]) - 0.25
            elif n < 36:
                t_out = T(n + 1, 0) - 0.25
            else:
                t_out = 178.0
            if t < t0 - 0.05 or t > t_out + 0.2:
                continue
            if cam is None:
                cam = cam_fn(t)
            sx, sy, vert, px = SPOTS[(n, ki)]
            if sx == "band":
                # 贴在黑带上：黑带中线（场地中心，板面高度）在画面上的位置
                c = _project(cam, np.array([0.0, 0.0, 0.62]))
                cx, cy = c[0] * 1920, c[1] * 1080
            else:
                W = cached(f"lyw:{n}:{ki}", lambda: _ray_point(cam_fn(t0), sx, sy, DEPTH))
                s0 = cached(f"lys:{n}:{ki}", lambda: _project(cam_fn(t0), W))
                d = (_project(cam, W) - s0) * PARALLAX
                d = np.clip(d, -0.12, 0.12)
                cx, cy = (sx + d[0]) * 1920, (sy + d[1]) * 1080
            fade = 1.0 - float(smooth(t, t_out, t_out + 0.2))
            rot, scale = 0.0, 1.0
            if n == 36 and ki == 1 and t > 177.50:
                # 被风卷起：跟着旋风转着放大
                w = t - 177.50
                rot = -140.0 * w * w - 30.0 * w
                scale = 1.0 + 2.5 * w * w
            fnt = look.font("serif", 260, px)
            adv = [fnt.measureText(ch) for ch in text]
            ca, sa = math.cos(math.radians(-rot)), math.sin(math.radians(-rot))
            x = -sum(adv) / 2
            for i, (ch, a) in enumerate(zip(text, adv)):
                tc = T(n, k0 + i)
                if vert:
                    ox, oy = 0.0, i * 1.08 * px
                else:
                    ox, oy = x + a / 2, 0.0
                    x += a
                if t < tc - 0.02:
                    continue
                ox, oy = ox * scale, oy * scale
                px_, py_ = cx + ox * ca - oy * sa, cy + ox * sa + oy * ca
                op = float(smooth(t, tc - 0.02, tc + 0.14)) * fade
                out.append(Overlay(ch, xy=(px_, py_), anchor="center-middle", size=px, weight=260, kind="serif",
                                   color=WHITE, group="present", opacity=op, rot=rot, scale=scale))
    return out


def l37_items(t):
    """"動物永不停下來"：画面正中，暖白粗宋体，逐字出现，整行一直缓缓变大（随镜头向前）。"""
    text = look.trad("动物永不停下来")
    ons = [T(37, 5 + i) for i in range(7)]
    t_sun = T(38, 0)
    if t < ons[0] - 0.05 or t > t_sun + 0.1:
        return []
    fade = 1.0 - float(smooth(t, t_sun - 0.15, t_sun + 0.05))
    grow = 1.0 + 0.16 * float(smooth(t, ons[0], t_sun)) + 0.05 * (t - ons[0])
    size, weight = 104, 800
    f = look.font("serif", weight, size)
    adv = [f.measureText(ch) for ch in text]
    x = 960.0 - sum(adv) * grow / 2
    out = []
    for ch, a, tc in zip(text, adv, ons):
        if t >= tc - 0.02:
            u = t - tc
            op = float(smooth(u, -0.02, 0.05)) * fade
            sc = grow * (1.0 + 0.25 * math.exp(-max(u, 0.0) / 0.06))
            out.append(Overlay(ch, xy=(x + a * grow / 2, 790), anchor="center-middle", size=size, weight=weight,
                               color=tuple(WARM * 1.2), group="past", opacity=op, scale=sc))
        x += a * grow
    return out


# ---------------------------------------------------------------- L38、L39：阳光里的焦平面

SUN_SPOTS = {
    (38, 0): (0.30, 0.74, False, 70),           # 左下方树叶的暗处
    (38, 1): (0.58, 0.30, False, 70),           # 那颗尘埃的左上方
    (38, 2): (0.85, 0.30, True, 70),            # 竖排在那颗尘埃右边
    (39, 0): (0.50, 0.70, False, 72),           # 拼字的下方
    (39, 1): (0.50, 0.70, False, 72),
}


def sun_items(t, eye, basis, df):
    """L38、L39 的乐句：悬在焦平面上（深度 df），正对镜头。位置在乐句开始时按镜头确定。"""
    out = []
    r, u, f = basis
    for n in (38, 39):
        ph = phrases(n, trad=True)
        for ki, (text, k0) in enumerate(ph):
            if (n, ki) not in SUN_SPOTS:
                continue
            t0 = T(n, k0)
            t_out = (T(n, ph[ki + 1][1]) - 0.05) if ki + 1 < len(ph) else T(n + 1, 0) - 0.05
            if n == 39 and ki == 1:
                t_out = T(39, 9) - 0.1
            if t < t0 - 0.05 or t > t_out + 0.35:
                continue
            fade = 1.0 - float(smooth(t, t_out, t_out + 0.35))
            sx, sy, vert, px = SUN_SPOTS[(n, ki)]
            F = df * 0.53590
            h = px / 1080.0 * F
            fnt = look.font("serif", 700, 1000)
            adv = [fnt.measureText(ch) / 1000 for ch in text]
            A = eye + f * df + r * ((sx - 0.5) * F * 16 / 9) + u * ((0.5 - sy) * F)
            rot = facing_rot(basis)
            x = -sum(adv) / 2
            for i, (ch, a) in enumerate(zip(text, adv)):
                tc = T(n, k0 + i)
                if t >= tc - 0.03:
                    op = float(smooth(t, tc - 0.03, tc + 0.16)) * fade
                    if vert:
                        P = A - u * (i * 1.08 * h)
                    else:
                        P = A + r * ((x + a / 2) * h)
                    rise = (1.0 - float(smooth(t, tc - 0.03, tc + 0.5))) * h * 0.08
                    out.append(TextPlane(ch, kind="serif", weight=700, height=h, color=tuple(WARM * 1.12),
                                         center=tuple(P + u * rise), rot=rot, group="past", opacity=op, bias=-9.0))
                x += a
    return out
