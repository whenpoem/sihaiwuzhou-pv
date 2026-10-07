"""D 段：副歌一后半 L15–L18 与间奏一（75.4–102.05 秒，帧 4524–6122）。

画面从上一段沉进深水的黑暗开始。L15 一道闪电照亮雨夜里湿透的砖地（俯视），雨由"丶"和短竖组成，三个"拜"
像印章一样砸在湿地上；地上有一块单车形状的干地，雨点一点点把它打湿。L16 地上一汪圆形积水里，雨点激起的同心
涟漪变成纬线，积水升起成一个由字带组成的地球。L17 地球裂成拼图，铺在桌上拼到一半。L18 拼好的部分折成缺一面
的立方体，缺口里升起红帆。间奏一红帆在报纸字栏铺成的海上疾驰，随后夜色降下，只剩桅顶的一点灯光，落到交接
光点的位置。

镜头用平面镜头 FlatCam（画面中心 x、y 与画面高 H），素材都正对镜头；俯视的地面、桌面和侧视的海都画在正对
镜头的平面上，轴测的立方体用平面仿射变换画出。L15–L18 是一个连续的俯视空间：雨夜砖地上的圆形积水、L17 的拼图
和 L18 的盒子同在 PZ.CENTER，镜头从左往右移到这里后只做推拉。间奏一开头字栏的海从画面下方涨上来、淹过桌子，
镜头随之由俯视换成侧视的海面（这一下发生在帆被风鼓满的一拍，画面主体始终是同一面红帆）。

各部分的素材在同目录的模块里：rain（砖地、雨、闪电）、bike（单车干地的轮廓）、globe（着色器里的球）、
puzzle（拼图块与木桌）、cube（轴测的盒子）、sail（红帆船的照片抠图）、sea（字栏的海、天空、水花）、
mats_d（各材质的着色器）。帧 6120 起（102.0 秒）画面为 handoff.point_frame。

    python scene.py preview | sheet 输出.png 秒,秒,... [--size 640x360] | still 秒 输出.png
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import common as C  # noqa: E402
from common import cached, ease, ramp, warm, chars, onsets  # noqa: E402
import handoff  # noqa: E402
from flatcam import FlatCam, run  # noqa: E402
from plan import T, BAR, BEAT_LEN  # noqa: E402
from engine import FrameSpec, Particles, Plane, Tex, TextPlane, GRADE_DEFAULTS  # noqa: E402

import mats_d  # noqa: E402,F401
import rain as RN  # noqa: E402
import bike as BK  # noqa: E402
import globe as GL  # noqa: E402
import puzzle as PZ  # noqa: E402
import cube as CB  # noqa: E402
import sail as SL  # noqa: E402
import sea as SEA  # noqa: E402

T0, T1 = handoff.T_DEEP, handoff.T_POINT          # 75.4–102.05：渲染帧 4524–6122
GRADE = handoff.GRADE_PAST

# ---------------------------------------------------------------- L15 的布局（世界坐标，米；地面在 z = 0）

T_FLASH = T(15, 0)                                  # "暴"：闪电
STRIKES = [(T(15, 0), 0.75), (T(15, 0) + 0.07, 0.5), (T(15, 0) + 0.15, 0.3), (T(15, 1), 0.55), (T(15, 1) + 0.06, 0.2)]
BIKE_C = np.array([-0.55, -0.40])
BIKE_ROT = math.radians(-5.0)
POOL = (float(PZ.CENTER[0]), float(PZ.CENTER[1]), 0.40)   # 圆形积水：中心与半径（L17 的拼图、L18 的盒子都在这里）
WET_T0, WET_T1 = T(15, 9) - 0.10, T(15, -1) + 0.30  # "沒"前后开始打湿干地，"來"唱完时轮廓消失

L15 = chars(15)
L15_T = onsets(15)
# 每个字落地的位置、字高、转角（度）
L15_POS = [((-2.42, 0.66), 0.34, 3), ((-2.02, 0.62), 0.34, -2),
           ((0.05, 0.62), 0.52, 5), ((0.72, 0.70), 0.52, -4), ((1.40, 0.58), 0.52, 6)]
_x0 = -1.45
L15_POS += [((_x0 + 0.31 * i, -1.20 + 0.012 * math.sin(i * 1.7)), 0.27, (i % 3 - 1) * 2.0) for i in range(7)]

# ---------------------------------------------------------------- 镜头

# ---------------------------------------------------------------- 间奏一的船速与镜头

T_SAIL = BAR(53)                                    # 89.62：间奏一第一拍，起航
RISE_END = 0.02                                     # 主帆升满时帆底高出盒口的量（米）
# 89.6 时船（照片 BBOX 中心）的位置与吃水线，由 L18 的帆的位置算出：盒口在盒底中心上方 S3·cos(33°)，
# 主桅（翻转后照片 x≈1115）对准盒口，帆底（照片 y≈965）高出盒口 RISE_END，照片每 680 像素为 1 米
_TOP_Y = float(PZ.CENTER[1]) + 3 * PZ.P * math.cos(math.radians(33.0))
BOAT0 = np.array([float(PZ.CENTER[0]) + (900 - 1115) / 680, _TOP_Y + RISE_END + (965 - 765) / 680])
Y_W = _TOP_Y + RISE_END + (965 - 1228) / 680
STEPS = [(BAR(53), 1.6), (BAR(54), 1.5), (BAR(55), 1.4), (BAR(56), 1.1)]     # 每个小节首拍加一档速度
T_SLOW = BAR(57)                                    # 96.48：开始减速、升高


def boat_speed(t):
    v = 0.0
    for ts, dv in STEPS:
        u = min(max((t - ts) / 0.75, 0.0), 1.0)
        v += dv * u * u * (3 - 2 * u)
    if t > T_SLOW:
        u = min((t - T_SLOW) / 4.2, 1.0)
        v *= 1.0 - 0.88 * (u * u * (3 - 2 * u))
    return v


def _boat_x_table():
    ts = np.arange(T_SAIL - 0.02, 102.2, 1 / 240)
    vs = np.array([boat_speed(x) for x in ts])
    xs = np.concatenate([[0.0], np.cumsum((vs[1:] + vs[:-1]) / 2 * np.diff(ts))])
    return ts, xs


def boat_dx(t):
    ts, xs = cached("boat_x", _boat_x_table)
    if t <= ts[0]:
        return 0.0
    return float(np.interp(t, ts, xs))


def boat_z(t):
    """间奏后半船驶向远方：深度从 0 退到约 -160。"""
    u = ramp(t, T_SLOW + 0.3, 101.7)
    return -160.0 * (u * u * (3 - 2 * u)) ** 1.25


def _cam_x_table():
    """镜头的横移：前半与船同速；后半镜头的速度逐渐减到零，船自己往前、往远处驶去。"""
    ts = np.arange(T_SAIL - 0.02, 102.2, 1 / 240)
    w = np.array([float(ease(ramp(x, T_SLOW - 0.3, 100.6))) for x in ts])
    vs = np.array([boat_speed(x) for x in ts]) * (1.0 - w)
    xs = np.concatenate([[0.0], np.cumsum((vs[1:] + vs[:-1]) / 2 * np.diff(ts))])
    return ts, xs


def cam_sea(t):
    """(x, y, H)：前半与船并行（船在画面偏左），后半减速、升高、拉远。"""
    ts, xs = cached("cam_x", _cam_x_table)
    x = BOAT0[0] + 0.416 + (float(np.interp(t, ts, xs)) if t > ts[0] else 0.0)
    up = float(ease(ramp(t, T_SLOW, 101.2)))
    y = BOAT0[1] - 0.272 + 2.5 * up
    H = 2.38 + 0.9 * up
    return x, y, H


_keys = [
    (75.40, -0.32, 0.00, 3.20),
    (77.20, -0.36, -0.14, 2.95),
    (78.95, POOL[0] - 0.30, -0.45, 2.45),           # 单车的干地湿透时，镜头已经移向圆形积水
    (79.75, POOL[0] - 0.06, -0.48, 2.10),
    (82.05, POOL[0], -0.48, 2.04),
    (83.05, POOL[0] - 0.5 * PZ.P, -0.50, 1.50),     # L17：推近拼图上的三行字
    (85.55, POOL[0] - 0.5 * PZ.P, -0.50, 1.46),
    (87.14, POOL[0] + 0.02, -0.22, 1.95),           # L18：盒子折起、视角转到轴测
    (88.70, POOL[0] + 0.08, 0.04, 2.35),            # 帆升起
    (89.60, *cam_sea(89.60)),
]
_keys += [(tt, *cam_sea(tt)) for tt in np.arange(89.85, 102.1, 0.2)]
CAM = FlatCam(_keys, far=20000.0, shakes=[(L15_T[2], 0.012, 9.0, 0.09), (L15_T[3], 0.014, 9.0, 0.09), (L15_T[4], 0.018, 9.0, 0.10)])


# ---------------------------------------------------------------- 地上的字：从镜头附近落到湿地上

def fall_z(t, tc, z0, dur):
    """字在 tc 时刻落地：之前 dur 秒从高 z0 处加速落下（z ∝ 1 - u²）。返回高度，未出现时返回 None。"""
    if t < tc - dur:
        return None
    u = min((t - (tc - dur)) / dur, 1.0)
    return z0 * (1.0 - u * u)


def ring_tex():
    def make():
        n = 512
        yy, xx = np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1
        r = np.hypot(xx, yy)
        a = np.exp(-((r - 0.86) / 0.05) ** 2) + 0.35 * np.exp(-((r - 0.70) / 0.06) ** 2)
        a[r > 1] = 0
        return np.dstack([np.ones((n, n, 3), np.float32), a.astype(np.float32)])
    return cached("ring_tex", lambda: Tex(make()))


def soft_disc():
    def make():
        n = 256
        yy, xx = np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1
        r = np.hypot(xx, yy)
        return np.clip(1.0 - r, 0, 1) ** 1.2
    return cached("soft_disc", lambda: Tex(make().astype(np.float32)))


def crown(t, tc, p, r0, n, seed, strength=1.0):
    """落地溅起的水花：一圈"丶"形水珠向外、向上飞出，再落回地面。"""
    u = t - tc
    if u < 0 or u > 0.55:
        return []
    rng = np.random.default_rng(seed)
    a = rng.uniform(0, 2 * np.pi, n)
    v = rng.uniform(0.6, 1.6, n) * strength
    vz = rng.uniform(1.0, 2.6, n) * strength
    life = rng.uniform(0.25, 0.5, n)
    tt = np.minimum(u, life)
    rad = r0 + v * tt
    z = np.maximum(vz * tt - 4.9 * tt * tt, 0.0) + 0.01
    alive = u < life
    if not alive.any():
        return []
    pos = np.c_[p[0] + rad * np.cos(a), p[1] + rad * np.sin(a), z][alive]
    ang = a[alive] - np.pi / 2
    s = rng.uniform(0.010, 0.026, n)[alive] * strength
    lit = 0.5 + 0.9 * rng.uniform(0, 1, n)[alive]
    col = np.tile([1.0, 0.92, 0.80, 0.9], (alive.sum(), 1)) * (np.clip(1 - u / life[alive], 0, 1) * lit)[:, None]
    atlas = RN.rain_atlas()
    return [Particles(atlas, pos, np.c_[s, s * 1.5], ang, col, uv=atlas.index_uv(np.zeros(alive.sum(), int)),
                      blend="add", group="past")]


def l15_text(t):
    items = []
    for i, (ch, tc, (p, h, rot)) in enumerate(zip(L15, L15_T, L15_POS)):
        heavy = 2 <= i <= 4
        z0, dur = (2.2, 0.20) if heavy else ((1.6, 0.13) if i < 2 else (1.2, 0.16))
        z = fall_z(t, tc, z0, dur)
        if z is None:
            continue
        flash = RN.flash_level(t, STRIKES)
        k = 1.12 + 0.25 * flash
        if heavy and t >= tc:
            k += 0.5 * math.exp(-(t - tc) / 0.12)
        a = 1.0 if z < 0.9 * z0 else float(ease((z0 - z) / (0.1 * z0)))
        a *= 1.0 - float(ease(ramp(t, 78.45 + 0.02 * i, 78.95 + 0.02 * i)))      # 镜头移向积水时，雨水漫过地上的字
        if a <= 0.0:
            continue
        sq = 1.0
        if heavy and t >= tc:                         # 落地的一下：像盖印一样一压一弹
            u = t - tc
            sq = 1.0 + 0.10 * math.exp(-u / 0.05) * math.cos(u * 40.0)
            # 字四周的积水被一下压开：一圈暗的湿印，随后水又漫回来
            ring = math.exp(-u / 0.45) * min(u / 0.03, 1.0)
            items.append(Plane(soft_disc(), center=(p[0], p[1], 0.0015), size=(h * 2.4, h * 2.4), color=(0.0, 0.0, 0.0),
                               opacity=0.55 * ring * a, group="past"))
        items.append(TextPlane(ch, kind="serif", weight=800 if heavy else 700, height=h * sq, color=warm(k),
                               center=(p[0], p[1], z + 0.004), rot=(0, 0, rot), group="past", opacity=a))
        # 倒影：落下途中，湿地里映出的字与字本身相向而行，落地时合在一起
        if z > 0.005:
            items.append(TextPlane(ch, kind="serif", weight=800 if heavy else 700, height=h, color=warm(0.5 * k),
                                   center=(p[0], p[1], -z), rot=(0, 0, rot), group="past", opacity=0.45 * a,
                                   bias=-(z + 0.5)))
        if t >= tc:
            u = t - tc
            if heavy:
                items += crown(t, tc, p, h * 0.42, 200, 100 + i, 2.0)
                items += crown(t, tc, p, h * 0.30, 90, 150 + i, 1.2)
            else:
                items += crown(t, tc, p, h * 0.35, 14, 100 + i, 0.5)
    return items


# ---------------------------------------------------------------- L16：积水升起成地球

L16 = chars(16)
L16_T = onsets(16)
T_DROP = L16_T[0]                                   # "她"：一滴大雨落在积水正中
T_FREEZE = L16_T[1] + 0.06                          # "善"：波纹定住
G_R = POOL[2]                                       # 球的半径等于积水的半径
G_ZUP = 1.62                                        # 升起后的球心高度
T_TILT0, T_TILT1 = L16_T[3] - 0.15, L16_T[5] - 0.05 # 极轴从朝向镜头倒向画面上方
GLOBE_XY1 = np.array([POOL[0], POOL[1]])            # 球就在积水正上方升起
# "她善變的"竖排在球的左边，"和我無關"竖排在球的右边，都落在湿地上；球在中间转
L16_POS = [((POOL[0] - 1.15, POOL[1] + 0.45 - 0.31 * i), 0.27, 0) for i in range(4)]
L16_OUT = [((POOL[0] + 1.15, POOL[1] + 0.45 - 0.31 * i), 0.27, 0) for i in range(4)]


def globe_state(t):
    """(球心, 倾角 0–1, 自转角, 水量)。"""
    u_rise = float(ease(ramp(t, L16_T[1] - 0.05, L16_T[3])))          # "善"到"的"：从水里升到半球再升离水面
    zc = -G_R * 0.98 + (G_R * 0.35 + G_R * 0.98) * u_rise
    u_up = float(ease(ramp(t, L16_T[3] - 0.1, L16_T[5] + 0.2)))
    zc += (G_ZUP - G_R * 0.35) * u_up
    xy = np.array(POOL[:2]) + (GLOBE_XY1 - np.array(POOL[:2])) * u_up
    tilt = float(ease(ramp(t, T_TILT0, T_TILT1)))
    spin = -0.30 * (t - L16_T[1]) - 0.9
    level = 1.0 - float(ease(ramp(t, L16_T[2], L16_T[4])))
    return np.array([xy[0], xy[1], zc]), tilt, spin, level


def globe_locks(t, spin_at):
    """赤道带上定住的歌词"世界大概都"：每个字在自己的元音起点定在带上，排成一行。"""
    out = []
    t0 = L16_T[4]
    if t < t0 - 0.02:
        return out
    c0 = GL.lock_cell(GL.EQ, spin_at(t0)) - 1
    for k in range(5):
        tc = L16_T[4 + k]
        if t >= tc - 0.02:
            boost = 1.25 + 0.6 * math.exp(-(t - tc) / 0.25)
            out.append((GL.EQ, c0 + k, L16[4 + k], round(boost, 2)))
    return out


def l16_scene(t):
    items = []
    c, tilt, spin, level = globe_state(t)
    md, ld = moon(t)
    puddle = dict(pc=tuple(POOL[:2]), pr=POOL[2], irr=pool_irr(t), lamp_pos=tuple(RN.LAMP), lamp_col=tuple(RN.LAMP_COL),
                  lamp_rdir=ld, sky=tuple(RN.SKY), flash=float(RN.flash_level(t, STRIKES)), moon_dir=md,
                  drop_t=T_DROP, freeze_t=T_FREEZE, rings=float(ease(ramp(t, T_DROP + 0.1, T_FREEZE))), level=level)
    if level > 0.001:
        items.append(Plane(None, center=(POOL[0], POOL[1], 0.001), size=(2 * POOL[2] * 1.2 + 0.05,) * 2, group="past",
                           material="d_puddle", uniforms=puddle, stack="ground"))
    if t < T_DROP - 0.3:
        return items
    if t >= T_DROP:
        items += crown(t, T_DROP, POOL[:2], 0.03, 40, 300, 1.1)
    if L16_T[1] - 0.06 <= t < PZ.T_BURST + 0.06:
        locks = globe_locks(t, lambda tt: globe_state(tt)[2])
        u_glow = 1.0
        items.append(GL.globe_plane(c, G_R, tilt, spin, min(t, PZ.T_BURST), locks=locks, water=0.0 if c[2] < G_R else -100.0,
                                    opacity=1.0 - ramp(t, PZ.T_BURST, PZ.T_BURST + 0.06),
                                    reveal=float(ease(ramp(t, L16_T[1] - 0.06, L16_T[2]))), glow=u_glow,
                                    crack=float(ease(ramp(t, L16_T[-2] - 0.15, PZ.T_BURST - 0.02))),
                                    lamp=RN.LAMP, lamp_col=tuple(RN.LAMP_COL * 0.35)))
    # "她善變的"：落在积水上方的湿地上；"和我無關"：落在球外面，一动不动
    for chs, ts, pos in ((L16[:4], L16_T[:4], L16_POS), (L16[-4:], L16_T[-4:], L16_OUT)):
        for ch, tc, (p, h, rot) in zip(chs, ts, pos):
            z = fall_z(t, tc, 1.2, 0.15)
            if z is None:
                continue
            items.append(TextPlane(ch, kind="serif", weight=700, height=h, color=warm(1.12), center=(p[0], p[1], z + 0.004),
                                   rot=(0, 0, rot), group="past"))
            if z > 0.005:
                items.append(TextPlane(ch, kind="serif", weight=700, height=h, color=warm(0.5), center=(p[0], p[1], -z),
                                       rot=(0, 0, rot), group="past", opacity=0.4, bias=-(z + 0.5)))
            if t >= tc:
                items += crown(t, tc, p, h * 0.35, 14, 400 + int(tc * 10), 0.5)
    return items


# ---------------------------------------------------------------- L17：地球裂成拼图，铺在桌上

T_BURST = PZ.T_BURST
T_CRACK0 = L16_T[-2] - 0.15                         # "無"前后：球面上显出拼图的切口


def l17_scene(t):
    if t < T_BURST or t >= T_FOLD:
        return []
    gc, _, _, _ = globe_state(T_BURST)
    table_op = float(ease(ramp(t, T_BURST + 0.04, T_BURST + 0.22)))
    return PZ.items(t, gc, G_R, table_op=table_op)


# ---------------------------------------------------------------- L18：折成缺一面的立方体，缺口里升起红帆

L18 = chars(18)
L18_T = onsets(18)
T_FOLD = L18_T[0] - 0.06                            # 由逐块的拼图换成按面画的盒子
FOLD = {"W": (L18_T[0], L18_T[1] + 0.33), "N": (L18_T[1], L18_T[2] + 0.37), "E": (L18_T[2], L18_T[3] + 0.41),
        "S": (L18_T[4] - 0.33, L18_T[5])}          # 四壁依次折起，最后一面在"面"字落下的一拍合上
EL_ISO, PHI_ISO = 33.0, 36.0
T_MAN = L18_T[-1]                                   # "滿"：帆被风鼓满
SAIL_SCALE = 1.0 / 680                              # 照片像素 → 米：主帆高约 1 米


def fold_state(t):
    th = {}
    for n, (a, b) in FOLD.items():
        u = ramp(t, a, b)
        e = u * u * (3 - 2 * u)
        if u >= 1.0:                                # 合上时轻轻一顿
            e = 1.0 - 0.02 * math.exp(-(t - b) / 0.05) * math.sin((t - b) * 70)
        th[n] = e * math.pi / 2
    v = float(ease(ramp(t, L18_T[0], L18_T[5] - 0.1)))
    el = 90.0 + (EL_ISO - 90.0) * v
    phi = PHI_ISO * v
    return th, el, phi


def billow(t):
    """主帆被风鼓起的程度："滿"字时一下鼓满，随后回落到 0.6 并保持。L18 与航行段用同一条曲线，换视角前后一致。"""
    up = float(ease(ramp(t, T_MAN - 0.04, T_MAN + 0.12)))
    return up * (1.0 - 0.4 * float(ease(ramp(t, T_MAN + 0.12, T_MAN + 0.6))))


def sail_rise(t):
    """主帆从盒口升起的高度（米，帆底相对盒口）：从"希"开始，"帆"时升满。"""
    u = float(ease(ramp(t, L18_T[6] - 0.1, L18_T[9] + 0.15)))
    return -1.05 + (1.05 + RISE_END) * u


def junk_planes(proj, t, full=0.0, billow=0.0):
    """红帆船：rise 之前只有主帆和主桅（从盒口升起），full 为船身与前后两帆显现的程度。
    返回 (盒子里的元素, 盒子外的元素)。"""
    tx = SL.textures()
    x0, y0, x1, y1 = SL.BBOX
    k = SAIL_SCALE
    top = proj.pt((0.0, 0.0, CB.S3))
    rise = sail_rise(t)
    # 主帆底边（照片 y≈965）对齐到盒口上方 rise 处；主桅（翻转后照片 x≈1115）对齐到盒口中心
    ax, ay = SL.PW - 805.0, 965.0
    def place(px, py):
        return np.array([top[0] + (px - ax) * k, top[1] + rise + (ay - py) * k])
    c = place((x0 + x1) / 2, (y0 + y1) / 2)
    W, H = (x1 - x0) * k, (y1 - y0) * k
    sx = 1.0 + 0.07 * billow
    inside, outside = [], []
    # 主帆与主桅：在盒口以下的部分裁掉（盒子前壁会挡住开口以下的那一段）
    # 盒口菱形左右两个角的高度：帆在这条线以下的部分在盒子里面，裁掉
    h3 = CB.S3 / 2
    cs = [proj.pt((sx_, sy_, CB.S3)) for sx_ in (-h3, h3) for sy_ in (-h3, h3)]
    cs.sort(key=lambda q: q[0])
    clip_y = max(cs[0][1], cs[-1][1])
    v_bottom = min(1.0, max(0.0, (c[1] + H / 2 - clip_y) / H))
    if v_bottom > 0.001:
        hh = H * v_bottom
        cy = c[1] + H / 2 - hh / 2
        lit = 1.0 + 0.25 * billow
        for key, op in (("main", 1.0), ("hull", 1.0 - full)):
            if op <= 0.001:
                continue
            if key == "hull":
                # 只取主桅那一条
                m0, m1 = SL.PW - 852, SL.PW - 760
                u0, u1 = (m0 - x0) / (x1 - x0), (m1 - x0) / (x1 - x0)
                pc = place((m0 + m1) / 2, 0)[0]
                vb = min(v_bottom, (972 - y0) / (y1 - y0))           # 只要甲板以上的桅杆，不带甲板上的棚架
                hm = H * vb
                cym = c[1] + H / 2 - hm / 2
                inside.append(Plane(tx["hull"], center=(pc, cym, 0.0), size=((m1 - m0) * k, hm),
                                    uv=(u0, 0, u1, vb), color=(lit,) * 3, opacity=op, group="past"))
            else:
                mx0, mx1 = SL.MAIN_X
                u0, u1 = (mx0 - x0) / (x1 - x0), (mx1 - x0) / (x1 - x0)
                pc = place((mx0 + mx1) / 2, 0)[0]
                pivot = top[0]
                pc = pivot + (pc - pivot) * sx
                inside.append(Plane(tx["main"], center=(pc, cy, 0.0), size=((mx1 - mx0) * k * sx, hh),
                                    uv=(u0, 0, u1, v_bottom), color=(lit,) * 3, group="past"))
    if full > 0.001:
        for key in ("hull", "fore", "mizzen"):
            outside.append(Plane(tx[key], center=(c[0], c[1], 0.0), size=(W, H), opacity=full, group="past"))
    return inside, outside


LYRIC_SX = 0.835                                    # 歌词竖列在画面上的横向位置（比例）


def l18_text(t, org):
    items = []
    # "總算差了一面"：盒子下方一行；"希望風帆裝飾的"竖排在帆的右边，"滿"大一号
    for i, (ch, tc) in enumerate(zip(L18[:6], L18_T[:6])):
        if t < tc - 0.02:
            continue
        a = float(ease((t - tc + 0.02) / 0.12)) * (1.0 - float(ease(ramp(t, L18_T[6] - 0.2, L18_T[7]))))
        if a <= 0.0:
            continue
        sc = 1.0 + 0.15 * (1 - a)
        p = (org[0] - 0.55 + 0.22 * i, org[1] - 0.50)
        items.append(TextPlane(ch, kind="serif", weight=700, height=0.19 * sc, color=warm(1.1), center=(*p, 0.05),
                               group="past", opacity=a))
    # "希望風帆裝飾的滿"：竖排锁在画面上船的右边（航行时镜头横移，歌词不随海面移动），画在海和帆的前面
    out_k = 1.0 - float(ease(ramp(t, 90.9, 91.5)))
    for i, (ch, tc) in enumerate(zip(L18[6:], L18_T[6:])):
        if t < tc - 0.02 or out_k <= 0.0:
            continue
        a = float(ease((t - tc + 0.02) / 0.12)) * out_k
        big = ch == L18[-1]
        hf = (0.30 if big else 0.19) / 2.38             # 字高（画面高的比例）
        sy = 0.135 + 0.092 * i + (0.025 if big else 0.0)
        (x, y), Hs = CAM.screen_to_world(t, LYRIC_SX, sy, z=0.05)
        flare = 0.6 * math.exp(-(t - tc) / 0.3) if big and t >= tc else 0.0
        items.append(TextPlane(ch, kind="serif", weight=800 if big else 700, height=hf * Hs * (1 + 0.12 * (1 - a)),
                               color=warm(1.1 + flare), center=(x, y, 0.05), group="past", opacity=a, bias=-200.0))
    return items


def l18_scene(t, sea_k=0.0):
    if t < T_FOLD:
        return []
    th, el, phi = fold_state(t)
    org = PZ.CENTER
    proj = CB.Proj(el, phi, org)
    inside, _ = junk_planes(proj, t, full=0.0, billow=billow(t)) if L18_T[6] - 0.15 <= t else ([], [])
    tide = t >= T_TIDE0
    if tide:
        # 字栏的海涨上来时，主帆和主桅画在海的前面，盒子和桌子画在海的后面（被海一点点淹没）
        for it in inside:
            it.stack, it.bias = "mainsail", -100.0
    items, _ = CB.box_items(t, th, el, phi, org, inside=[] if tide else inside)
    if tide:
        for it in items:
            it.bias = 1000.0
        items += inside
    return items


# ---------------------------------------------------------------- 间奏一：报纸字栏的海

T_TIDE0 = T_MAN - 0.38                              # 89.22：字栏的海从画面下方涨上来，淹过桌子和盒子
T_FULL = T_SAIL - 0.06                              # 89.56：涨满，整幅画面只剩字栏和主帆
R_FULL = 0.70                                       # 涨满时水面比正常高出的量（画面高）
T_RECEDE = T_SAIL + BEAT_LEN                        # 89.62 起俯视的桌面不再画；一拍之内退回正常的海面，露出天空和船
T_NIGHT0, T_NIGHT1 = 96.9, 101.2                    # 天色暗下去
T_OFF0, T_OFF_SPAN = 97.2, 3.2                      # 字栏一栏栏熄灭
T_END = 102.0                                       # 起画面为交接的光点


def cam_vx(t):
    d = 1 / 240
    return (CAM.state(t + d)[0] - CAM.state(t - d)[0]) / (2 * d)


def boat_pose(t):
    """船（照片 BBOX 中心）的世界坐标与颠簸角。"""
    z = boat_z(t)
    sp = boat_speed(t)
    k = min(sp / 5.0, 1.0)
    w = float(ease(ramp(t, T_SAIL, T_SAIL + 1.2)))
    heave = w * ((0.010 + 0.012 * k) * math.sin(2 * math.pi * 1.25 * t) + 0.006 * math.sin(2 * math.pi * 2.1 * t + 1.0))
    tilt = w * (0.6 + 1.4 * k) * math.sin(2 * math.pi * 0.85 * t + 0.4)
    y = SEA.layer_y(Y_W, z, 0.0) + (BOAT0[1] - Y_W) + heave
    return np.array([BOAT0[0] + boat_dx(t), y, z]), tilt


class _MastCam:
    """把交接光点画在桅顶：point_items 按 POINT_SCREEN 取位置，这里把它换成桅顶此刻在画面上的位置，
    最后一秒逐渐移到 POINT_SCREEN（那时船身已经隐进夜色，只剩这一点灯）。"""

    def __init__(self, t):
        self.t = t

    def screen_to_world(self, t, sx, sy, z=0.0):
        pos, tilt = boat_pose(t)
        m = SEA.photo_to_world(*SL.MAST_TOP, pos, tilt)
        x, y, H, _ = CAM.state(t)
        D = H * CAM.K
        d = D - m[2]
        msx = 0.5 + (m[0] - x) / d * CAM.K / (16 / 9)
        msy = 0.5 - (m[1] - y) / d * CAM.K
        u = float(ease(ramp(t, 100.9, T_END - 0.05)))
        tx, ty = msx + (sx - msx) * u, msy + (sy - msy) * u
        return CAM.screen_to_world(t, tx, ty, z)


def sea_rise(t):
    """水面相对正常位置的高度（画面高）：从画面下方涨上来，涨满后停住；换成侧视后一拍之内退回正常位置。"""
    if t < T_SAIL:
        u = ramp(t, T_TIDE0, T_FULL)
        return -1.15 + (R_FULL + 1.15) * (1 - (1 - u) ** 2)
    u = ramp(t, T_SAIL, T_RECEDE)
    return R_FULL * (1.0 - u * u * (3 - 2 * u))


def backing(t, rise):
    """涨潮时最远几层字栏之间的缝隙后面是一块与远处海色相近的底，缝里不露出桌面。"""
    (cx, cy), Hs = CAM.screen_to_world(t, 0.5, 0.5, z=-700.0)
    top_frac = 0.5 - SEA.TAN_D * CAM.K - rise           # 最远一层的上沿在画面上的位置（从上往下）
    top = cy + (0.5 - top_frac) * Hs
    bottom = cy - 0.6 * Hs
    if top <= bottom:
        return []
    col = cached("backing_col", lambda: tuple(float(v) for v in np.clip(SEA.sky_rgba()[-40:].mean((0, 1)), 0, 1) * 0.55))
    return [Plane(None, center=(cx, (top + bottom) / 2, -700.0), size=(Hs * 2.0, top - bottom), color=col,
                  group="past")]


def sea_scene(t):
    if t < T_TIDE0:
        return []
    items = []
    rise = sea_rise(t)
    night = float(ease(ramp(t, T_NIGHT0, T_NIGHT1)))
    if t >= T_SAIL:
        items.append(SEA.sky_item(CAM, t, k=1.0 - 0.94 * night, night=night))
    if t < T_RECEDE:
        items += backing(t, rise)
    # 运动模糊：着色器里取帧中心时刻镜头的位置，模糊宽度为四分之一帧的横移
    t_c = round(t * 60.0) / 60.0
    blur = cam_vx(t_c) * 0.25 / 60.0
    x_shift = CAM.state(t)[0] - CAM.state(t_c)[0]
    lit = 1.0 - 0.55 * night
    items += SEA.sea_items(CAM, t, Y_W, blur_dx=blur, rise=rise, lit=lit, night=night, off_t0=T_OFF0,
                           off_span=T_OFF_SPAN, x_shift=x_shift, t_c=t_c)
    if t >= T_SAIL:
        pos, tilt = boat_pose(t)
        fade = 1.0 - float(ease(ramp(t, 100.2, 101.4)))           # 船身隐进夜色
        items += SEA.junk_items(pos, t, billow=billow(t), tilt=tilt, k_light=1.0 - 0.6 * night, opacity=fade,
                                night=night, main_bias=-100.0)
        bow = lambda tt: SEA.photo_to_world(*SL.BOW, *boat_pose(tt))
        items += SEA.spray_items(t, bow, boat_speed, T_SAIL + 0.3, k=(1.0 - night) * fade, cam_vx=cam_vx(t),
                                 cam_state=CAM.state(t), cam_K=CAM.K)
    # 最后一秒：除了桅灯，一切都沉进夜色，与交接画面的底色一致
    dk = float(ease(ramp(t, 100.9, 101.75)))
    if dk > 0.0:
        (cx, cy), Hs = CAM.screen_to_world(t, 0.5, 0.5, z=0.5)
        items.append(Plane(None, center=(cx, cy, 0.5), size=(Hs * 2.2, Hs * 1.3), color=(0.010, 0.012, 0.018),
                           opacity=dk, group="past", bias=-1000.0))
    # 桅灯：起航后一直亮着，夜色越深越显眼，最后落到交接光点的位置
    if t >= T_SAIL:
        k = (0.35 + 0.65 * float(ease(ramp(t, T_NIGHT0, T_END - 0.3)))) * float(ease(ramp(t, T_RECEDE, T_RECEDE + 0.6)))
        for it in handoff.point_items(_MastCam(t), t, k=k, z=boat_z(t) + 0.02):
            it.bias = -2000.0
            items.append(it)
    return items


# ---------------------------------------------------------------- 组装

MOON_AT = np.array([0.12, -0.11])                   # 月亮的倒影落在圆形积水里的位置（相对积水中心）
LAMP_AT = np.array([-0.15, 0.13])                   # 路灯的倒影：积水靠路灯的一侧


def moon(t):
    """月亮与路灯在圆形积水里的倒影方向：每帧按镜头位置算，倒影因此始终落在积水里固定的位置上。
    返回 (月亮方向, 路灯倒影方向)。"""
    eye, _ = CAM(t)
    e = np.asarray(eye.eye, float)
    return RN.reflect_dir(np.array(POOL[:2]) + MOON_AT, e), RN.reflect_dir(np.array(POOL[:2]) + LAMP_AT, e)


def pool_irr(t):
    """积水边缘的不规则程度：雨夜里是一汪不规则的水，大雨点落下、波纹定住时收成正圆（之后是地球的轮廓）。"""
    return 1.0 - float(ease(ramp(t, T_DROP, T_FREEZE)))


def bike_tex():
    return cached("bike_tex", lambda: Tex(BK.dry_mask()))


def l15_scene(t):
    if t > PZ.T_BURST + 0.25:
        return []
    gone = 1.0 - float(ease(ramp(t, PZ.T_BURST, PZ.T_BURST + 0.2)))     # 碎块飞起遮住画面时，雨夜的地面隐去
    flash = RN.flash_level(t, STRIKES)
    st = CAM.state(t)
    # 闪电过后眼睛一时不适应，路灯照着的地面先暗一些，约半秒后看清
    adapt = 0.55 + 0.45 * float(ease(ramp(t, T_FLASH + 0.05, T_FLASH + 0.7)))
    bw, bh = BK.size()
    dry = dict(rect=(BIKE_C[0] - bw / 2, BIKE_C[1] - bh / 2, BIKE_C[0] + bw / 2, BIKE_C[1] + bh / 2), rot=BIKE_ROT,
               tex=bike_tex(), t0=WET_T0, t1=WET_T1)
    imps = [(L15_POS[i][0][0], L15_POS[i][0][1], L15_T[i], 1.0) for i in (2, 3, 4)]
    pool = (*POOL, pool_irr(t)) if globe_state(t)[3] > 0.001 or t < T_DROP else None
    items = RN.ground_items(t, flash=flash, dry=dry, pool=pool, lamp_k=adapt, impacts=imps, opacity=gone, moon=moon(t)[0])
    items += RN.rain_items(t, st, ztop=st[2] * 1.866 - 0.2, flash=flash, lamp_k=adapt, k=gone)
    items += l15_text(t)
    its16 = l16_scene(t)
    if gone < 1.0:
        for it in its16:
            it.opacity *= gone
    items += its16
    return items


def frame(t):
    if t < T_FLASH - 0.004:
        return handoff.dark_frame(t, handoff.DEEP)
    if t >= T_END - 1e-6:
        return handoff.point_frame(t)
    cam, H = CAM(t)
    items = l15_scene(t) + l17_scene(t) + (l18_scene(t) if t < T_SAIL else []) + sea_scene(t)
    if t >= T_FOLD:
        items += l18_text(t, PZ.CENTER)
    return FrameSpec(cam, items, grade=grade(t))


def grade(t):
    """航行段的天空明亮、平整，颗粒比夜里显眼得多，这一段把颗粒强度降到 0.6 倍；入夜后回到标准值，
    交接时刻（102.0 秒）与 handoff.GRADE_PAST 完全一致。"""
    if t < T_TIDE0 or t > 101.5:
        return GRADE
    if t < T_SAIL:
        k = 1.0 - 0.4 * float(ease(ramp(t, T_TIDE0, T_SAIL)))
    else:
        k = 0.6 + 0.4 * float(ease(ramp(t, 99.0, 101.5)))
    g = {grp: dict(v) for grp, v in GRADE.items()}
    g["past"]["grain"] = GRADE_DEFAULTS["past"]["grain"] * k
    return g


if __name__ == "__main__":
    run(frame, "D段", T0, T1, C.RENDERS)
