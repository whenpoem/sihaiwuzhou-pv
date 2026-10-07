"""L06→L07：长矛脱手下落，经过一缕近云时变成锈刀；镜头跟着刀穿过一片近云，白光过后刀落到草席上、滑进枕头底下。

骑士从云塔顶往右走下时，长矛从 47.15 秒开始往下压，47.70 秒（"蕎"之前一拍）脱手；脱手后骑士加速往右远去，
长矛按重力加速下落、略向左飘，矛身继续顺时针转、矛尖朝下。47.98 秒它从一缕近云后面经过，被云挡住的那一刻
换成刀：刀的重心、速度和方向都接在长矛上，从云后出来时已经是一把生锈的刀，落向画面右侧三分之一处。

48.15 秒起镜头穿过一片近云：近云的上沿从画面下边升起，0.15 秒铺满画面，全白停 0.14 秒，天空在这片白里换成
屋里；48.44–48.74 秒白光散开，露出受光的枕套，刀离席面只剩一点高度，48.60 秒落到草席上（影子收拢到刀下）。
随后刀向左滑，到"藏"（49.33 秒）停在枕头底下，只露出刀柄和护手。

换刀用的那缕近云取自云堤照片的云体内部，放在 z = 20；镜头穿过的近云锁定在画面上，放在镜头与场景之间。
"""
import math

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

import bed as B
import sky as S
import yard as Y
from common import K, Z_SKY, cached, ease, ramp, smooth
from engine import Plane, Tex
from plan import T

T_DROP = S.T_DROP
T_SWAP = 47.98
G = 24.0                                       # 下落的加速度（世界单位/秒²）


def _com0():
    """脱手瞬间长矛重心的位置与长矛的方向（度，原图里矛从握手处指向矛尖为 64°）。"""
    hand, ang = S.lance_state_at_drop()
    body, lance, hpx, tip = S.knight_tex()
    d = np.array([tip[0] - hpx[0], hpx[1] - tip[1]]) / S.PX_PER_U       # 握手处到矛尖（世界单位，y 向上）
    a = math.radians(ang)
    R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    com = hand + R @ (d * 0.42)
    return com, ang, hand


def fall_state(t):
    """下落物的重心与转角（度，相对原图朝向）。"""
    com0, a0, _ = _com0()
    u = max(t - T_DROP, 0.0)
    vx, tau = -3.0, 0.30                         # 脱手时被马带着，随后略向左飘，落向画面中间
    x = com0[0] + vx * tau * (1 - math.exp(-u / tau)) - 1.0 * u
    y = com0[1] - 0.5 * G * u * u
    return np.array([x, y]), u


def lance_items(t):
    """脱手后、变成刀之前的长矛。"""
    if not (T_DROP <= t < T_SWAP):
        return []
    com0, a0, hand0 = _com0()
    c, u = fall_state(t)
    ang = lance_ang(t)
    body, lance, hpx, tip = S.knight_tex()
    h, w = lance.data.shape[:2]
    W, H = w / S.PX_PER_U, h / S.PX_PER_U
    # 平面中心相对重心的偏移：先算相对握手处，再减去重心相对握手处
    d = np.array([tip[0] - hpx[0], hpx[1] - tip[1]]) / S.PX_PER_U
    off_hand = np.array([(w / 2 - hpx[0]) / S.PX_PER_U, (hpx[1] - h / 2) / S.PX_PER_U])
    off = off_hand - d * 0.42
    a = math.radians(ang)
    R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
    pc = c + R @ off
    return [Plane(lance, center=(pc[0], pc[1], Z_SKY + 0.40), size=(W, H), rot=(0, 0, ang), group="past")]


def lance_ang(t):
    """下落中长矛相对原图的转角：脱手后继续顺时针转，矛尖越来越朝下。"""
    com0, a0, _ = _com0()
    u = max(t - T_DROP, 0.0)
    return a0 - 75.0 * (1 - math.exp(-u / 0.40))


# 刀的方向：贴图里刀尖朝右（0°）。换成刀时接上长矛的方向（长矛在原图里从握手处指向矛尖为 64°），
# 落到席子上时转到 B.KNIFE_ANG − 360°
A_SWAP = 64.0 + lance_ang(T_SWAP)
A_LAND = B.KNIFE_ANG - 360.0
LAND = np.array([25.0, 1.5])


SKY_END = np.array([20.6, 3.4])                   # 在天上的最后位置（T_SWITCH，已被近云挡住）：画面右侧三分之一处


def knife_pose(t):
    """(重心, 转角, 离席面的高度, 缩放)。在天上时从换刀处按三次埃尔米特曲线落向 SKY_END，起点速度接着长矛的
    下落速度；白光过后已在屋里，刀离席面只剩一点高度，48.60 秒落到席子上，随后向左滑进枕头底下。"""
    if t < S.T_SWITCH:
        cs, _ = fall_state(T_SWAP)
        us = T_SWAP - T_DROP
        vs = np.array([-3.0 * math.exp(-us / 0.30) - 1.0, -G * us])
        ve = np.array([-1.0, -16.0])
        D = S.T_SWITCH - T_SWAP
        u = ramp(t, T_SWAP, S.T_SWITCH)
        h00, h10, h01, h11 = 2 * u ** 3 - 3 * u ** 2 + 1, u ** 3 - 2 * u ** 2 + u, -2 * u ** 3 + 3 * u ** 2, u ** 3 - u ** 2
        c = h00 * cs + h10 * D * vs + h01 * SKY_END + h11 * D * ve
        ang = A_SWAP + (A_LAND - A_SWAP) * 0.8 * float(ease(u))
        return c, ang, 3.0, 1.1
    if t < T_LAND_():
        u = ramp(t, S.T_SWITCH, T_LAND_())
        c = LAND + np.array([0.5, 0.25]) * (1 - u)
        ang = A_LAND + 9.0 * (1 - u) ** 2
        hgt = 0.8 * (1 - u ** 2)
        return c, ang, hgt, 1.0 + 0.03 * hgt
    u = ramp(t, T_LAND_(), B.T_HIDE)
    e = 1 - (1 - u) ** 2.6
    c = LAND + (np.array(B.KNIFE_REST) - LAND) * e
    ang = A_LAND + 1.5 * math.sin(u * math.pi) * (1 - u)
    return c, ang, 0.0, 1.0


def T_LAND_():
    return B.T_LAND


def knife_items(t, light):
    if t < T_SWAP:
        return []
    c, ang, hgt, sc = knife_pose(t)
    spark = math.exp(-((t - T(7, -1) - 0.02) / 0.05) ** 2)
    wd = np.array(light["win_dir"])
    room = 1.0 if t >= S.T_SWITCH else 0.0          # 白光过后已经在屋里：光由正午的天光换成屋里的光
    shadow = (wd * hgt * 0.9 + np.array([0.10, -0.10]), 0.34 * (1 - 0.6 * min(hgt / 3.0, 1)) * room)
    return B.knife_plane(t, light, c, ang, height=hgt, spark=spark, scale=sc, shadow=shadow, in_sky=1 - room)


# ---------------------------------------------------------------- 近云

WISPS = [  # (z, 在 t 时刻挡住画面上哪一点（以 z = 0 计，None 表示下落物所在处）, t, 世界宽度, 不透明度, 取云的哪一块)
    (20.0, None, T_SWAP - 0.01, 4.6, 1.0, 0),
]
WISP_SRC = [(2450, 550, 900, 600), (1400, 1350, 1100, 600), (300, 1300, 1200, 650)]   # 云照片里云体内部的区域（像素）


def wisp_tex(k):
    """近云：从云堤照片的云体内部取一块，四周按带噪声的椭圆淡出，边缘先乘一个矩形窗，平面的边不会露出来。"""
    def make():
        a = Y.cloud_rgba()
        x0, y0, w, h = WISP_SRC[k]
        crop = a[y0:y0 + h, x0:x0 + w].copy()
        yy, xx = np.mgrid[0:h, 0:w]
        r = np.hypot((xx - w / 2) / (w / 2), (yy - h / 2) / (h / 2)) / 0.92
        rng = np.random.default_rng(31 + k)
        nz = gaussian_filter(rng.normal(0, 1, (h, w)), 22)
        nz = nz / nz.std()
        fall = np.clip((1.0 - r + 0.16 * nz) / 0.45, 0, 1) ** 1.4
        win = np.clip(np.minimum(xx, w - 1 - xx) / (0.10 * w), 0, 1) * np.clip(np.minimum(yy, h - 1 - yy) / (0.10 * h), 0, 1)
        crop[..., 3] = crop[..., 3] * fall * win
        # 离镜头很近，在焦点之外：模糊，并且被正午的光照透，比云堤更亮
        crop[..., :3] = gaussian_filter(crop[..., :3], (7, 7, 0)) * 0.98 + 0.04
        crop[..., 3] = gaussian_filter(crop[..., 3], 5)
        return Tex(crop)
    return cached(("wisp", k), make)


def wisp_items(t, cam):
    """cam 为 FlatCam：按"在 t 时刻挡住画面上哪一点"反算近云的世界位置（沿视线放到 z 处）。"""
    items = []
    for k, (z, target, tk, wsz, op, src) in enumerate(WISPS):
        if abs(t - tk) > 0.42:
            continue
        if target is None:
            c, _ = fall_state(tk)
            target = (c[0], c[1])
        x, y, H, _ = cam.state(tk)
        d = H * K
        s = (d - z) / d
        wx = x + (target[0] - x) * s
        wy = y + (target[1] - y) * s
        tex = wisp_tex(src)
        h, w = tex.data.shape[:2]
        a = op * (1 - smooth(abs(t - tk), 0.24, 0.42))
        items.append(Plane(tex, center=(wx, wy, z), size=(wsz, wsz * h / w), group="past", opacity=a))
    return items


# ---------------------------------------------------------------- 穿过近云：白光里从天空换到屋里

T_IN0, T_IN1 = 48.15, 48.30                       # 近云的上沿从画面下边升到上边之外
T_OUT0, T_OUT1 = 48.44, 48.74                     # 白光散开，露出枕套的白布
WHITE = (1.30, 1.25, 1.12)                        # 近云内部的白：调色后与受光的枕套是同一种白


def near_cloud_tex():
    """镜头穿过的那片近云：上沿是积云团块的形状，往下是匀净的白，内部只留很淡的明暗。"""
    def make():
        from PIL import Image
        from scipy.ndimage import gaussian_filter1d
        h, w = 900, 1200
        rng = np.random.default_rng(83)
        u = np.linspace(0, 1, w)
        # 上沿：几个大的团块叠上细的鼓包
        top = np.full(w, 0.16)
        for _ in range(7):
            c, r = rng.uniform(0, 1), rng.uniform(0.07, 0.16)
            top = np.minimum(top, 0.16 + 0.05 - 0.08 * np.sqrt(np.clip(1 - ((u - c) / r) ** 2, 0, 1)))
        top += 0.012 * gaussian_filter1d(rng.normal(0, 1, w), 6)
        v = np.linspace(0, 1, h)[:, None]
        nz = gaussian_filter(rng.normal(0, 1, (h, w)), 10)
        nz = nz / nz.std()
        alpha = np.clip((v - top[None, :] + 0.006 * nz) / 0.035, 0, 1)
        a = Y.cloud_rgba()
        crop = a[400:1300, 2300:3500, :3]
        det = np.asarray(Image.fromarray((np.clip(crop / 1.6, 0, 1) * 255).astype(np.uint8)).resize((w, h), Image.LANCZOS),
                         np.float32).mean(2) / 255
        det = gaussian_filter(det, 4)
        det = (det - det.mean()) / (det.std() + 1e-6)
        # 上沿附近的团块有明暗，往里很快变成匀净的白
        k = np.exp(-np.clip(v - top[None, :], 0, None) / 0.10)
        shade = 1.0 + det * (0.10 * k + 0.02)
        col = np.dstack([shade] * 3) * np.array(WHITE)
        return Tex(np.dstack([col, alpha]).astype(np.float32))
    return cached("nearcloud", make)


def whiteout_items(t, cam):
    """镜头跟着刀穿过一片近云：近云的上沿从画面下边升起、铺满画面（0.15 秒），全白停 0.14 秒，
    这期间天空换成屋里；随后白光散开，留下的就是枕套的白布。近云锁定在画面上，放在镜头与场景之间。"""
    if t < T_IN0 or t > T_OUT1:
        return []
    x, y, H, _ = cam.state(t)
    d = H * K
    z = 0.55 * d
    (cx, cy), Hs = cam.screen_to_world(t, 0.5, 0.5, z=z)
    u = smooth(t, T_IN0, T_IN1)
    top_sy = 1.05 - 1.30 * u                          # 近云上沿在画面上的位置（0 为上边，1 为下边）
    tex = near_cloud_tex()
    th = 0.16                                          # 贴图里上沿约在 16% 高处
    PH = 2.6 * Hs                                      # 平面高：上沿以下要盖住整幅画面
    PW = 1.9 * Hs * 16 / 9
    plane_top = (0.5 - top_sy) * Hs + th * PH           # 平面上边相对画面中心的世界 y
    pcy = cy + plane_top - PH / 2
    a = 1.0 - smooth(t, T_OUT0, T_OUT1)
    return [Plane(tex, center=(cx, pcy, z), size=(PW, PH), group="past", opacity=a)]
