"""副歌一的平面长卷版：所有素材摆在同一个正对观众的平面上，镜头只平移和推拉，像展开一幅长卷。

三维飞行的版本里，墙、展览馆、乌云和向日葵这些平面素材一被斜着看就露出纸片感，镜头在三十多个关键位置之间
一停一顿，花飞向尖塔、越过墙头那几段又急又快。这一版改成纯平面：镜头始终正对画面，只沿长卷平移和推拉，
相邻的构图挨着摆，每次移动距离短，推拉幅度控制在两倍以内；每幅构图停够一句歌词，再用一到两秒平稳地移到
下一幅。长卷从上往下是：桌面（L08–L09）→ 铁水字坠落 → 标语墙（L10）→ 墙头砸下的乌云（L11）→ 墙前握花的手。

坐标：x 沿标语墙自左缘量起，y 向上，墙头 y = 0；单位与三维版相同（墙宽 38、高 15，桌面 9.86 × 4.40）。
z 只用来分前后：夜空在 z = -80、剪影在 z = -30，镜头平移时它们移动得慢一些（多层平面的视差），但都正对观众，
不产生透视变形；平面全部正对镜头，排序按 z 精确无误。镜头竖直视角 30 度，画面高度 H（世界单位）决定镜头离
平面的距离 H / (2 tan 15°)。

本文件先做 L08 末尾到 L11（53.0–65.3 秒），用来确认方向。
python flat.py preview | final [--from 秒 --to 秒]
"""
import math
import sys
from pathlib import Path

import numpy as np
from scipy.interpolate import PchipInterpolator

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "style"))
sys.path.insert(0, str(HERE.parent / "film"))
import look  # noqa: E402
import plan  # noqa: E402
from plan import T, BAR  # noqa: E402
from engine import Cam, Film, FrameSpec, Particles, Plane, Tex, TextPlane  # noqa: E402

import desk as D  # noqa: E402
import mats  # noqa: E402,F401
import wall as WL  # noqa: E402
import flower as FL  # noqa: E402
import clouds as CL  # noqa: E402
import backdrop as BD  # noqa: E402
import flat_b as FB  # noqa: E402

T0, T1 = 51.0, FB.T_END
FOV = 30.0
K = 1.0 / (2.0 * math.tan(math.radians(FOV / 2)))
GRADE = {"past": {"halation": 1.2, "lift": 0.03, "gain": 1.25, "vignette": 0.38, "weave": 0.5, "scratch": 0.5}}


def ease(u):
    u = np.clip(u, 0.0, 1.0)
    return u * u * (3 - 2 * u)


def ramp(t, a, b):
    return float(np.clip((t - a) / (b - a), 0.0, 1.0))


_C = {}


def cached(key, fn):
    if key not in _C:
        _C[key] = fn()
    return _C[key]


def warm(k=1.15):
    return tuple(np.array(look.C["warm"]) * k)


# ---------------------------------------------------------------- 长卷上的位置

DESK_C = np.array([5.0, 6.0])           # 桌面中心；L08 那行刻字在 y ≈ 6.5
WALL_C = np.array([19.0, -7.5])         # 标语墙中心（墙宽 38、高 15，墙头 y = 0）
BULB = np.array([5.4, 8.15])            # 灯丝"未來"的中心：灯泡吊在 L08 那行字的上方
L09 = plan._CHARS[8]                    # 未 來 被 熔 斷 在 迷 失 的 深 夜 裡
T_FLICK, T_MELT, T_BREAK = L09[2], L09[3], L09[4]
TEXT_RIGHT = [(6.75, 8.15), (7.22, 8.15), (7.69, 8.15)]   # "被熔斷"：接在灯泡右边，与灯丝同一行
COL_X = 7.69                            # "在迷失的深夜裡"从"斷"字下方竖着往下写
FLOWER_C = np.array([21.0, -7.0])        # 墙前握花的手：花心的位置，在 L10 那行字下方 2 个单位
FL_K = 4.6                               # 花的整体缩放：花心"她"字高 0.97，扌在花心下方 4 个单位
SLAMS = [T(11, 2), T(11, 3), T(11, 4)]   # 三个"来"
CLOUD_ORG = [np.array([10.5, 0.2]), np.array([20.5, 0.9]), np.array([30.0, -0.3])]  # 云底中心：砸在墙头上，压住墙的上沿
APPEAR_T = T(11, 5)                      # "先"：手和茎顶的"她"出现

# ---------------------------------------------------------------- 镜头：(时刻, 中心 x, 中心 y, 画面高 H)
# 每个通道用单调三次插值：关键位置之间速度连续、不过冲，只有方向反转或停住的地方才减到零；H 在对数空间插值，
# 推拉的视觉速度均匀。

CAM_KEYS = [
    (51.00, 5.30, 7.45, 4.45),     # 黑暗中拉亮吊灯：灯泡在画面上方，L08 的刻字在灯下逐个显出
    (53.60, 5.50, 7.42, 4.50),
    (55.45, 5.85, 7.35, 4.6),      # L09："未來"是灯丝，灯泡、"被熔斷"和 L08 那行字同在一幅构图里
    (56.30, 5.90, 7.30, 4.7),      # 灯丝烧断、灯灭，镜头停住
    (58.30, 10.20, 1.40, 11.2),    # 墙出现时它的左端始终在画面外     # 黑暗里慢慢往下，月光显出夜色和墙头；"在迷失的深夜裡"竖着写下来
    (59.70, 12.80, -2.70, 13.8),   # L10："像"之后，墙和歌词
    (61.30, 19.70, -3.20, 15.5),   # 一幅宽构图里沿墙缓缓右移，整行歌词写完时全在画面里
    (62.05, 20.50, -1.50, 18.0),   # "乌云"：稍稍后退，露出墙头上方的夜空，下方留出握花的手的位置
    (63.05, 20.60, -1.55, 18.0),   # 三个"来"，乌云砸在墙头上
    (65.00, 20.20, -9.00, 9.8),    # 推近墙前握花的手：歌词那一行在画面上方三分之一处，扌和茎在下方
    (65.40, 20.22, -9.05, 9.7),
]


def _cam_curves():
    k = np.array(CAM_KEYS)
    return (PchipInterpolator(k[:, 0], k[:, 1]), PchipInterpolator(k[:, 0], k[:, 2]),
            PchipInterpolator(k[:, 0], np.log(k[:, 3])))


def camera(t):
    if t >= 65.0:                            # L12 以后镜头要越过墙头推向远处的展览馆，改用 flat_b 的镜头
        return FB.camera(t)
    fx, fy, fh = cached("cam", _cam_curves)
    tt = min(max(t, CAM_KEYS[0][0]), CAM_KEYS[-1][0])
    x, y, H = float(fx(tt)), float(fy(tt)), float(np.exp(fh(tt)))
    for i, ts in enumerate(SLAMS):           # 乌云砸下时画面短促地上下一震，第三下最重
        u = t - ts
        if 0 <= u < 0.6:
            y += H * (0.010 + 0.005 * i) * math.exp(-u / 0.15) * math.sin(2 * math.pi * 8.5 * u)
    d = H * K
    return Cam(eye=(x, y, d), target=(x, y, 0.0), fov=FOV, near=0.05, far=400.0), H


# ---------------------------------------------------------------- 夜空与远景剪影（后面两层）

SKY_Z, BAND_Z = -80.0, -30.0
SKY_H = 120.0                            # 全景整幅高度对应的世界单位
MOON_P = np.array([-9.4, 19.1])          # 月亮在夜空层上的位置：L10、L11 的画面里出现在墙头左上方


def sky(t):
    def make():
        pano = BD.sky_panorama()
        h, w = pano.shape[:2]
        ppu = h / SKY_H
        mx, my = (-10.0 + 135.0) / 270.0 * w, (80.0 - 30.0) / 90.0 * h     # 全景里月光照亮的那片云（偏航 -10°、仰角 30°）
        c = MOON_P + np.array([(w / 2 - mx) / ppu, (my - h / 2) / ppu])
        moon, halo = BD.moon_textures()
        band = BD.silhouette_band("near")
        return dict(pano=Tex(pano), size=(w / ppu, SKY_H), center=c, moon=Tex(moon), halo=Tex(halo), band=Tex(band),
                    band_aspect=band.shape[1] / band.shape[0])
    s = cached("sky", make)
    items = [Plane(s["pano"], center=(*s["center"], SKY_Z), size=s["size"], group="past")]
    items.append(Plane(s["halo"], center=(*MOON_P, SKY_Z + 0.5), size=(21.0, 21.0), blend="add", group="past"))
    items.append(Plane(s["moon"], center=(*MOON_P, SKY_Z + 0.6), size=(3.5, 3.5), group="past"))
    bh = 17.0
    items.append(Plane(s["band"], center=(18.0, -1.7, BAND_Z), size=(bh * s["band_aspect"] * 1.22, bh), group="past"))
    return items


# ---------------------------------------------------------------- 桌面（L08–L09）

def desk_tex():
    def make():
        a, x, g = D.build()
        return Tex(a, premultiplied=True), Tex(x, premultiplied=True), Tex(g, premultiplied=True)
    return cached("desk", make)


T_ON = plan._CHARS[7][0]               # "嚴"：拉亮吊灯


def fil_b(t):
    """灯丝的亮度（同时决定色温）：拉亮时钨丝在十分之一秒里由暗红烧到正常；平常为 1；"被"时电压不稳、闪几下；
    "熔"时一路发白；"斷"时闪一下烧断，随即冷却。"""
    if t < T_ON:
        return 0.0
    if t < T_ON + 0.35:
        u = (t - T_ON) / 0.35
        b = min((t - T_ON) / 0.11, 1.0) ** 1.5
        return b * (1.0 - 0.18 * math.exp(-((u - 0.55) / 0.12) ** 2))     # 刚通电时的一下暗闪
    if t < T_FLICK:
        return 1.0 + 0.012 * math.sin(t * 2 * math.pi * 7.0)
    if t < T_MELT:
        dips = [(0.025, 0.030), (0.075, 0.020), (0.115, 0.040), (0.165, 0.016)]
        d = max(math.exp(-((t - T_FLICK - c) / w) ** 2) for c, w in dips)
        return 1.0 - 0.78 * d
    if t < T_BREAK:
        u = ramp(t, T_MELT, T_MELT + 0.18)
        return 1.0 + 1.7 * float(ease(u)) + 0.10 * math.sin(t * 2 * math.pi * 23.0) * u
    if t < T_BREAK + 0.035:
        return 4.2
    return 2.4 * math.exp(-(t - T_BREAK - 0.035) / 0.11)


def room_k(t):
    """屋里的灯光：跟着灯丝走，烧断的一刻随闪光一起熄灭。"""
    if t < T_BREAK + 0.035:
        return fil_b(t)
    return 4.2 * math.exp(-(t - T_BREAK - 0.035) / 0.025)


def adapt(t):
    """灯灭以后眼睛慢慢适应黑暗：0 为全黑，1 为看清月夜。"""
    return float(ease(ramp(t, T_BREAK + 0.45, T_BREAK + 1.6)))


def desk(t):
    if t > 59.0:
        return []
    alb, aux, glow = desk_tex()
    W, H = D.SIZE
    k = room_k(t)
    warm_l = np.array([0.96, 0.87, 0.74]) * max(k, 1.0)
    # t_base 推到很远：桌上不再灌铁水、不再烧穿，只留 L08 的刻字，亮度全由灯光决定
    uni = {"aux": aux, "glowmap": glow, "t_base": 1000.0, "night": float(1.0 - min(k, 1.0)), "glow_fill": 0.0,
           "glow_burn": 0.0, "carve_t0": D.CARVE_T0, "carve_span": D.CARVE_SPAN,
           "day_light": tuple(warm_l), "night_light": (0.022, 0.026, 0.038)}
    gone = 1.0 - ramp(t, T_BREAK + 0.1, T_BREAK + 0.5)             # 灯灭后桌面完全隐进黑暗，不在夜空前留下边
    if gone <= 0:
        return []
    return [Plane(alb, center=(*DESK_C, 0.0), size=(W, H), group="past", material="desk_c", uniforms=uni, stack="desk",
                  opacity=gone)]


def l08_old(t):
    """L08 的旧字"引無數英雄競折腰"：唱到"腰"时，L08 那行刻字下方的木纹里隐约显出一行褪色的红漆字。"""
    a = float(ease(ramp(t, plan._CHARS[7][-1] - 0.1, plan._CHARS[7][-1] + 0.6))) * (1 - float(ease(ramp(t, 55.6, 56.3))))
    if a <= 0:
        return []
    return [TextPlane(look.trad("引無數英雄競折腰"), kind="fang", height=0.26, color=(0.55, 0.20, 0.15),
                      group="past", center=(DESK_C[0], DESK_C[1] + 0.06, 0.001), tracking=0.35, opacity=0.55 * a,
                      stack="desk")]


def lamp_pool(t):
    """灯光在桌上照出的一圈：灯泡正下方最亮，往外压暗；灯灭后这一圈也随之消失（正片叠底）。"""
    k = min(room_k(t), 1.0)
    if k <= 0.003 or t > 59.0:
        return []

    def make():
        n = 512
        yy, xx = np.mgrid[0:n, 0:n] / (n - 1)
        # 灯下一圈椭圆的光：横向半径约 2.6、纵向约 1.5，往外很快暗到几乎全黑，桌子的边缘因此藏进黑暗
        r = np.sqrt(((xx - 0.5) * 16 / 3.5) ** 2 + ((yy - 0.5) * 12 / 1.15) ** 2)
        v = 0.015 + 0.985 * np.exp(-r ** 2 * 1.4)
        return np.dstack([v, v * 0.96, v * 0.91, np.ones_like(v)]).astype(np.float32)
    tex = cached("pool4", make)
    dx = sway(t)[0] * 1.6
    return [Plane(tex, center=(5.3 + dx, DESK_C[1] + 0.5, 0.004), size=(16.0, 12.0), blend="multiply",
                  opacity=k, group="past")]


def room(t):
    """屋里灯照不到的地方是黑的：桌面上方和四周压成黑色，往下渐渐过渡到屋外的夜空（放在夜空之前、桌面之后）。"""
    if t > 60.0:
        return []

    def make():
        n = 256
        y = np.linspace(1, 0, n)[:, None] * np.ones((1, 8))
        a = np.clip((y * 12.0 - 2.0) / 2.6, 0, 1)            # 平面高 12、下沿在 y = 0：y = 2 处开始变黑，4.6 处全黑
        return np.dstack([np.zeros_like(a)] * 3 + [a]).astype(np.float32)
    tex = cached("room", make)
    return [Plane(tex, center=(10.0, 6.0, -0.5), size=(80.0, 12.0), group="past"),
            Plane(None, center=(10.0, 22.0, -0.5), size=(80.0, 20.0), color=(0, 0, 0), group="past")]


def blackout(t):
    """烧断的一刻眼前一黑，随后月光把夜色一点点显出来（在桌面、墙和夜空之前，灯泡和字之后）。"""
    if t < T_BREAK + 0.03 or t > T_BREAK + 1.7:
        return []
    return [Plane(None, center=(10.0, 0.0, 0.05), size=(120.0, 80.0), color=(0, 0, 0), opacity=1.0 - adapt(t),
                  group="past")]


def filament_color(b):
    """灯丝的颜色由温度决定：烧得越亮越白，冷却时由橙变成暗红。"""
    if b >= 1.0:
        w = min((b - 1.0) / 2.2, 1.0)
        c = np.array([1.0, 0.80, 0.52]) * (1 - w) + np.array([1.0, 0.96, 0.88]) * w
    else:
        c = np.array([0.55, 0.07, 0.015]) * (1 - b) + np.array([1.0, 0.62, 0.28]) * b
    return c * b


def gaussian(a, s):
    from scipy.ndimage import gaussian_filter
    return np.clip(gaussian_filter(a, s) * 1.6, 0, 1)


def bulb_tex():
    import bulb as BL

    def make():
        L = BL.filament_layers()
        sk = BL.socket()
        return dict(glass=Tex(BL.glass()), fil=[Tex(np.dstack([l, l, l, l])) for l in L],
                    sock=Tex(sk[..., :4]), lit=Tex(np.dstack([sk[..., 4]] * 4)), cord=Tex(BL.cord(), repeat=True),
                    after=Tex(np.dstack([gaussian(L[0] + L[1], 7)] * 4)))
    return cached("bulb_tex", make)


def bulb_items(t):
    return swayed(_bulb_items(t), t)


def _bulb_items(t):
    import bulb as BL
    if t > 59.0:
        return []
    tx = bulb_tex()
    b, k = fil_b(t), room_k(t)
    on = t < T_BREAK + 0.035
    moon = 0.10 * adapt(t)
    items = []
    # 花线与胶木灯头
    neck_y = BULB[1] + (BL.ANCHOR_PX[1] - BL.NECK_Y) / BL.PPU
    sx = BULB[0] + (1608 - BL.ANCHOR_PX[0]) / BL.PPU
    sw, sh = 1040 / BL.PPU, 560 / BL.PPU
    sock_c = (sx, neck_y + sh / 2 - 0.05, 0.10)
    lit_dim = max(min(k, 1.6), 0.0) * 0.8 + moon * 0.6
    items.append(Plane(tx["cord"], center=(sx, sock_c[1] + sh / 2 + 7.5, 0.09), size=(200 / BL.PPU, 15.0),
                       uv=(0, 0, 1, 15.0 * BL.PPU / 1600), color=(0.4 + lit_dim * 0.5,) * 3, group="past"))
    items.append(Plane(tx["sock"], center=sock_c, size=(sw, sh), color=(0.4 + lit_dim,) * 3, group="past"))
    items.append(Plane(tx["lit"], center=(sock_c[0], sock_c[1], 0.101), size=(sw, sh), blend="add",
                       color=tuple(np.array([1.0, 0.7, 0.4]) * 0.8 * min(k, 3.0)), group="past"))
    # 玻璃：按加法叠加，被灯丝照亮；灯灭后只剩月光在玻璃边上的一点冷光
    gc, gs = BL.crop_geometry(BULB)
    if on:
        gk = 0.30 + 0.75 * min(b, 3.0)
        gcol = (gk, gk, gk)
    else:
        e = math.exp(-(t - T_BREAK - 0.035) / 0.12)
        gcol = tuple(np.array([1.0, 0.85, 0.7]) * 0.9 * e + np.array([0.55, 0.65, 0.85]) * moon)
    items.append(Plane(tx["glass"], center=(*gc, 0.11), size=gs, blend="add", color=gcol, group="past"))
    # 屋里的光晕
    halo = cached("soft", lambda: __import__("props").soft_dot(256))
    items.append(Plane(halo, center=(BULB[0], BULB[1] - 0.1, 0.105), size=(5.0, 5.0), blend="add",
                       color=tuple(np.array([1.0, 0.75, 0.45]) * 0.11 * min(k, 4.0)), group="past"))
    # 灯丝：两个字挂在引线上，连接丝从中点烧断；烧断后两个字和两半连接丝各自垂下，带一点晃动
    fc, fs = BL.filament_box(BULB)
    bp = np.array(BL.bridge_point(BULB))
    col = filament_color(b)
    if b > 1.0:                                   # 高温时亮度增长放缓，发白时仍认得出两个字
        col = col / b * (1.0 + 0.5 * (b - 1.0))
    boosts = [0.5 * math.exp(-(t - L09[0]) / 0.3) if t >= L09[0] else 0.0,
              0.5 * math.exp(-(t - L09[1]) / 0.3) if t >= L09[1] else 0.0]
    du = max(t - T_BREAK - 0.035, 0.0)
    sag = 0.0 if on else (1 - math.exp(-du / 0.12)) * (1 + 0.25 * math.exp(-du / 0.25) * math.cos(du * 30))

    def pivot_plane(tex, pivot, ang, color, z):
        r = np.array(fc) - pivot
        c, s_ = math.cos(math.radians(ang)), math.sin(math.radians(ang))
        cc = pivot + np.array([c * r[0] - s_ * r[1], s_ * r[0] + c * r[1]])
        return Plane(tex, center=(*cc, z), size=fs, rot=(0, 0, ang), blend="add", color=tuple(color), group="past")
    wa = np.array(BL.px_to_world(1300, 1920, BULB))          # "未"左上角挂在引线上
    wb = np.array(BL.px_to_world(1972, 1920, BULB))          # "來"右上角挂在引线上
    gain = 2.4
    items.append(pivot_plane(tx["fil"][0], wa, -5.0 * sag, col * gain * (1 + boosts[0]), 0.12))
    items.append(pivot_plane(tx["fil"][1], wb, 4.0 * sag, col * gain * (1 + boosts[1]), 0.12))
    bl = np.array(BL.px_to_world(1636 - 200, 2056, BULB))
    br = np.array(BL.px_to_world(1636 + 200, 2056, BULB))
    hot = 1.0 + (3.0 * ramp(t, T_MELT, T_BREAK) if T_MELT <= t < T_BREAK + 0.035 else 0.0)   # 连接丝中点最先烧白
    items.append(pivot_plane(tx["fil"][2], bl, -38.0 * sag, col * gain * hot, 0.12))
    items.append(pivot_plane(tx["fil"][3], br, 38.0 * sag, col * gain * hot, 0.12))
    metal = np.array([0.42, 0.36, 0.30]) * min(max(b, 0.0), 1.5) * 0.6 + moon * 0.4
    items.append(Plane(tx["fil"][4], center=(*fc, 0.115), size=fs, color=tuple(metal), group="past"))
    items.append(Plane(tx["fil"][5], center=(*fc, 0.118), size=fs, blend="add", color=tuple(col * 0.10), group="past"))
    # 火星：烧断处溅出几粒，落下熄灭
    if not on and du < 0.6:
        rng = np.random.default_rng(3)
        n = 26
        v = np.c_[rng.normal(0, 0.55, n), rng.normal(0.25, 0.45, n)]
        life = rng.uniform(0.18, 0.5, n)
        tt = np.minimum(du, life)
        pos = np.c_[bp[0] + v[:, 0] * tt, bp[1] + v[:, 1] * tt - 1.6 * tt ** 2, np.full(n, 0.125)]
        a = np.clip(1 - du / life, 0, 1)
        cols = np.c_[2.6 * a, 1.5 * a, 0.6 * a, a]
        siz = np.c_[np.full(n, 0.010), 0.010 + np.minimum(np.hypot(*v.T) * 0.02, 0.03)]
        dot = cached("dot", lambda: __import__("props").dot())
        items.append(Particles(dot, pos, siz, None, cols, blend="add", group="past"))
    return items


SWAY_PIVOT_Y = BULB[1] + 16.0


def sway(t):
    """拉亮吊灯时灯泡的摆动：(水平位移, 转角度数)。花线长约 16，摆动周期约 2 秒，四秒内衰减到看不出。"""
    if t < T_ON:
        return 0.0, 0.0
    u = t - T_ON
    dx = 0.13 * math.exp(-u / 1.3) * math.sin(2 * math.pi * u / 2.0 + 0.4)
    return dx, math.degrees(dx / 16.0)


def swayed(items, t):
    dx, ang = sway(t)
    if abs(dx) < 1e-4:
        return items
    c, s_ = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    for it in items:
        if not isinstance(it, Plane):
            continue
        x, y, z = it.center
        rx, ry = x - BULB[0], y - SWAY_PIVOT_Y
        it.center = np.array([BULB[0] + c * rx - s_ * ry, SWAY_PIVOT_Y + s_ * rx + c * ry, z])
        r = tuple(it.rot) if it.rot is not None else (0.0, 0.0, 0.0)
        it.rot = (r[0], r[1], r[2] + ang)
    return items


def afterimage(t):
    """视觉余像：烧断前那一下最亮的灯丝在眼睛里留下反色的影子，停在视线里同一个位置，慢慢淡去。"""
    import bulb as BL
    if not (T_BREAK + 0.05 <= t <= T_BREAK + 2.4):
        return []
    tx = bulb_tex()
    cam0, H0 = camera(T_BREAK)
    cam, H = camera(t)
    fc, fs = BL.filament_box(BULB)
    off = (np.array(fc) - np.array(cam0.target[:2])) / H0
    u = t - T_BREAK
    drift = np.array([0.010 * u, -0.014 * u])                 # 眼睛不由自主地移动，余像跟着轻轻飘
    c = np.array(cam.target[:2]) + (off + drift) * H
    a = float(ease(ramp(u, 0.05, 0.25))) * math.exp(-max(u - 0.25, 0) / 0.8)
    return [Plane(tx["after"], center=(*c, 0.3), size=(fs[0] * H / H0, fs[1] * H / H0), blend="add",
                  color=tuple(np.array([0.32, 0.66, 0.74]) * 0.75 * a), group="past")]


def l09_text(t):
    """"被熔斷"写在灯泡右边，被灯光照着，灯灭时一起暗下去；"在迷失的深夜裡"是月光的冷白色，从"斷"下方竖着往下写，
    越往下字越大；旧字"長夜難明赤縣天"在左边的夜色里若隐若现。"""
    if t > 60.0:
        return []
    items = []
    k = room_k(t)
    for (x, y), ch, tc in zip(TEXT_RIGHT, "被熔斷", L09[2:5]):
        if t < tc - 0.02:
            continue
        lit = min(k, 2.5)
        if ch == "斷" and t >= T_BREAK:
            lit = 4.2 * math.exp(-(t - T_BREAK) / 0.14)        # 只被烧断的那一下闪光照亮
        items.append(TextPlane(ch, kind="serif", weight=700, height=0.40, color=warm(0.30 * min(lit, 1.0) + 0.45 * lit),
                               group="past", center=(x, y, 0.12), opacity=float(ease((t - tc + 0.02) / 0.08))))
    halves = look.lyric(9).split("　")
    text = look.trad(halves[0])[-1] + look.trad(halves[1])          # 在 + 迷失的深夜裡
    on = L09[5:]
    y = TEXT_RIGHT[2][1] - 0.30
    sizes = [0.42, 0.48, 0.55, 0.62, 0.70, 0.78, 0.86]
    cold = np.array([0.80, 0.88, 1.0])
    for ch, tc, h in zip(text, on, sizes):
        y -= h / 2 + 0.06
        if t >= tc - 0.02:
            a = float(ease((t - tc + 0.02) / 0.22))
            items.append(TextPlane(ch, kind="serif", weight=600, height=h, color=tuple(cold * (0.55 + 0.35 * adapt(t))),
                                   group="past", center=(COL_X, y - 0.06 * (1 - a), 0.15), opacity=a))
        y -= h / 2 + 0.06
    old = look.trad("長夜難明赤縣天")
    a = float(ease(ramp(t, 57.0, 57.9))) * (1 - float(ease(ramp(t, 59.2, 59.9))))
    if a > 0:
        items.append(TextPlane(old, kind="fang", height=0.62, color=(0.62, 0.24, 0.20), group="past", vertical=True,
                               valign="top", center=(4.4, 6.6, 0.06), opacity=0.32 * a))
    return items


# ---------------------------------------------------------------- 标语墙（L10）

def wall_tex():
    def make():
        a, x1, x2, wm = WL.build()
        return Tex(a), Tex(x1, premultiplied=True), Tex(x2, premultiplied=True), Tex(wm, premultiplied=True)
    return cached("wall", make)


def lyric10_layout():
    def make():
        text = look.trad(look.lyric(10))
        f = look.font("serif", 600, 1000)
        out, x = [], WL.LYRIC["x"]
        s = WL.LYRIC["size"]
        for ch in text:
            w = f.measureText(ch) / 1000 * s
            if ch != "　":
                out.append((ch, x, w))
            x += w
        return out
    return cached("l10", make)


def wall(t):
    if t < 56.8:
        return []
    alb, aux1, aux2, wm = wall_tex()
    lead = -1.0 + (WL.LEAD_FINAL + 1.0) * float(1 - (1 - ramp(t, BAR(36), BAR(36) + 0.66)) ** 2.2)
    # 墙上不再有铁水流下（t_base 推到很远，铁水永远不到），也就没有铁水的暖光
    uni = {"aux1": aux1, "aux2": aux2, "warmmap": wm, "t_base": 1000.0, "lead_x": lead,
           "bleed_p": float(ease(ramp(t, T(10, -1), T(10, -1) + 1.1))), "warm_k": 0.0, "wall_w": WL.WALL_W}
    items = [Plane(alb, center=(*WALL_C, 0.0), size=(WL.WALL_W, WL.WALL_H), group="past", material="wall_c",
                   uniforms=uni, stack="wall")]
    base_y = -WL.LYRIC["baseline"]
    # 唱到 L11 时，墙上的旧歌词先退到墙里，镜头推向握花的手时完全隐去，不与新的一行争位置
    dim = 1.0 - 0.6 * float(ease(ramp(t, 61.6, 62.4)))
    gone = 1.0 - float(ease(ramp(t, 63.4, 64.2)))
    for (ch, x, w), tc in zip(lyric10_layout(), plan._CHARS[9]):
        if t < tc - 0.02:
            continue
        p = ramp(t, tc - 0.02, tc + 0.14)
        flare = 0.6 * math.exp(-max(t - tc, 0) / 0.25)
        items.append(TextPlane(ch, kind="serif", weight=600, height=WL.LYRIC["size"], color=warm(1.15 * dim),
                               center=(x, base_y, 0.01), align="left", valign="baseline", group="past", opacity=gone,
                               material="reveal_lr", uniforms={"progress": p, "flare": flare}, stack="wall"))
    return items


# ---------------------------------------------------------------- 乌云（L11 的三个"来"）

def clouds(t):
    if t < SLAMS[0] - 0.4:
        return []
    items = []
    for i, (th, org) in enumerate(zip(SLAMS, CLOUD_ORG)):
        if t < th - 0.32:
            continue
        u = ramp(t, th - 0.32, th)
        o = np.array([org[0], org[1] + 5.5 * (1 - u ** 3), 0.3])        # 从上方加速落下，"来"字落地的一拍正好砸到墙头
        its = CL.cloud_items(i, t - th, origin=o, face=o + np.array([0.0, 0.0, 1000.0]), strength=(1.0, 1.1, 1.3)[i])
        fade = 1.0 - float(ease(ramp(t, 65.3 + 0.1 * i, 66.3 + 0.1 * i)))         # 花起飞时乌云散开
        if fade <= 0:
            continue
        for it in its:
            it.opacity *= fade
        items += its
    return items


# ---------------------------------------------------------------- 墙前握花的手（L11 后半）

def flower_light(p):
    return np.array([0.74, 0.72, 0.70]) + np.array([1.0, 0.52, 0.2]) * 0.10


HAND_K = 1.35                            # "扌"相对花的模块里的原始大小再放大，绕握持点缩放，握持关系不变


def hand_planes(o, shadow):
    """握着茎的"扌"：和歌词同样的暖白色，带毛笔的颗粒和飞白，与墙上褪色的红漆标语分得开。"""
    hg = FL.hand_geometry()
    grip = np.asarray(hg["grip"])
    c = grip + (np.asarray(hg["center"]) - grip) * HAND_K
    size = (hg["size"][0] * HAND_K * FL_K, hg["size"][1] * HAND_K * FL_K)

    def make():
        a = FL.hand_tex()[..., 3]
        h, w = a.shape
        rng = np.random.default_rng(8)
        from scipy.ndimage import gaussian_filter
        streak = gaussian_filter(rng.normal(0, 1, (h, w)), (0.6, 14))           # 横向的飞白
        streak = streak / (streak.std() + 1e-6)
        a2 = a * np.clip(1.0 - 0.35 * np.clip(streak - 1.0, 0, 3), 0, 1)
        col = np.ones((h, w, 3), np.float32)
        col *= (0.92 + 0.08 * gaussian_filter(rng.normal(0, 1, (h, w)), 1.0))[..., None]
        return Tex(np.dstack([col, a2]).astype(np.float32))
    tex = cached("hand_warm", make)
    items = []
    if shadow > 0:
        items.append(Plane(FL.grip_shadow_tex(), center=(o[0] + c[0] * FL_K, o[1] + c[1] * FL_K, o[2] + (hg["z"] - 0.002) * FL_K),
                           size=size, opacity=shadow, color=(0.6, 0.6, 0.6), group="past", stack="flower"))
    items.append(Plane(tex, center=(o[0] + c[0] * FL_K, o[1] + c[1] * FL_K, o[2] + hg["z"] * FL_K), size=size,
                       color=warm(1.0), group="past", stack="flower"))
    return items


def flower(t):
    if t < APPEAR_T - 0.35 or t > 68.0:
        return []
    fade = float(ease(ramp(t, APPEAR_T - 0.35, APPEAR_T + 0.05)))
    rise = 0.5 * (1 - float(ease(ramp(t, APPEAR_T - 0.35, APPEAR_T + 0.4))))      # 从下面轻轻升到位
    o = np.array([FLOWER_C[0], FLOWER_C[1] - rise, 0.4])
    glow = 1.12 + 0.5 * math.exp(-max(t - APPEAR_T, 0.0) / 0.3)
    for tc in (plan._CHARS[10][-3], plan._CHARS[11][1]):        # 唱到"她"时，花心的字亮一下
        if t >= tc - 0.02:
            glow += 0.55 * math.exp(-(t - tc + 0.02) / 0.35)
    items = []
    if t < FB.T_FLY:                                             # 起飞以后花头由 flat_b 画，扌握着空茎留在原处
        items += FL.bloom_items(FB.bloom_u(t), origin=o, scale=FL_K, light=flower_light, center_color=(glow,) * 3)
    shadow = 1.0 - ramp(t, FB.T_FLY, FB.T_FLY + 0.15)
    items += hand_planes(o, shadow)
    for it in items:
        it.opacity *= fade
    # "先別鬆開她的手"：与花心的"她"排成一行
    text = look.trad(look.lyric(11).split("　")[1])
    on = plan._CHARS[10][-len(text):]
    k = text.index("她")
    hgt, gap = 0.95, 1.15
    leave = 1.0 - float(ease(ramp(t, FB.T_LET - 0.25, FB.T_LET - 0.03)))     # 在"讓"出现之前让出位置
    for i, (ch, tc) in enumerate(zip(text, on)):
        if i == k or t < tc - 0.02 or leave <= 0:
            continue
        items.append(TextPlane(ch, kind="serif", weight=700, height=hgt, color=warm(), group="past",
                               center=(o[0] + (i - k) * gap, o[1], 0.42),
                               opacity=leave * float(ease((t - tc + 0.02) / 0.1))))
    return items


# ---------------------------------------------------------------- 组装

def focus(t):
    """握花的手出现后，四周的墙面渐渐压暗，视线集中到手和花上（正片叠底的径向渐变）。"""
    k = float(ease(ramp(t, APPEAR_T - 0.3, APPEAR_T + 0.9))) * (1.0 - float(ease(ramp(t, 65.7, 66.5))))
    if k <= 0:
        return []

    W, H = 80.0, 50.0                   # 平面要比任何时刻的画面都大，边缘处的压暗与平面外一致，看不出边

    def make():
        n = 640
        yy, xx = np.mgrid[0:n, 0:n] / (n - 1)
        dx, dy = (xx - 0.5) * W, (yy - 0.5) * H
        r = np.sqrt(dx ** 2 + (dy / 0.8) ** 2)          # 世界单位：手和花周围 4.5 单位以内不压暗，到 12 单位处压到 0.42
        v = 1.0 - 0.58 * np.clip((r - 4.5) / 7.5, 0, 1) ** 1.3
        return np.dstack([v, v, v, np.ones_like(v)]).astype(np.float32)
    tex = cached("focus", make)
    return [Plane(tex, center=(FLOWER_C[0] - 0.8, FLOWER_C[1] - 2.0, 0.02), size=(W, H), blend="multiply",
                  opacity=k, group="past")]


SCENES = [sky, room, desk, l08_old, lamp_pool, wall, blackout, bulb_items, l09_text, clouds, focus, flower, afterimage] + FB.SCENES


def frame(t):
    cam, _ = camera(t)
    items = []
    for sc in SCENES:
        items += sc(t)
    g = FB.grade(t, GRADE)
    if t < T_ON + 0.05:                      # 51.0 秒从上一段的全暗接过来，灯亮之前只有极暗的屋子
        g = dict(g)
        g["final"] = {"fade": 1.0 - 0.25 * float(ease(ramp(t, 51.02, T_ON))), "fade_color": (0.012, 0.012, 0.016)}
        if t >= T_ON:
            g["final"] = {"fade": 0.75 * (1.0 - ramp(t, T_ON, T_ON + 0.05)), "fade_color": (0.012, 0.012, 0.016)}
    return FrameSpec(cam, items, grade=g)


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "preview"
    args = sys.argv[2:]
    t0 = float(args[args.index("--from") + 1]) if "--from" in args else T0
    t1 = float(args[args.index("--to") + 1]) if "--to" in args else T1
    out_dir = plan.ROOT / "renders" / "seg_c"
    out_dir.mkdir(parents=True, exist_ok=True)
    if mode == "preview":
        film = Film(frame, fps=30, size=(1920, 1080), ss=1)
        out = out_dir / "平面版_预览.mp4"
        film.preview(t0, t1, str(out))
    else:
        film = Film(frame, fps=60, size=(1920, 1080), ss=2)
        out = out_dir / "平面版_试做.mp4"
        film.render(t0, t1, str(out), subframes=2)
    print(out)


if __name__ == "__main__":
    main()
