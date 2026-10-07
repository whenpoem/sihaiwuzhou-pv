"""《四海五洲》PV 主歌二（E 段）：L19–L22，102.05–116.0 秒（帧 6123–6959）。

这一段是全片第三层"夜与水下"。画面从间奏一留下的一个暖色光点开始：光点是一盏马灯的火苗，灯光渐渐照亮一扇旧木门，
门上的粉笔字随灯光显出（L19）；镜头沿着字移到门搭扣和挂锁上，"空"字落进锁片的锁孔，锁孔里透出另一边的冷青色光，
镜头推进锁孔、穿过去，另一边是水下：一口钟缓缓下沉，钟声化成一圈圈褪色的红字向外扩散（L20）；钟沉出画面后，
系在钟上的细绳被看不见的风筝拉直，从下往上染红（L21），一个"手"字张开，白色的"風"从指缝间穿过；镜头沿风筝线
加速上升，穿出水面，一层层过去的东西从上方压下来、向下掠过，越往上年代越近，最后冲破最上面一层，画面成为冷白（L22）。

镜头分两段：门这一侧用 CAM_A（门面在 z = door.ZD），穿过锁孔之后用 CAM_B（水下与上升，主平面在 z = 0）。两段在
T_SWITCH 交接：交接前，水下世界整体平移到门后（平移量 B_OFFSET 使两个镜头在交接时刻看到完全相同的画面），
所以从锁孔里看到的就是交接后的水下；交接时门和孔道都已在镜头身后，画面连续。

python scene.py preview | sheet 输出.png 秒,秒,... [--size 640x360] | still 秒 输出.png
"""
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import common  # noqa: E402,F401
import look  # noqa: E402
import plan  # noqa: E402
from plan import T, BAR  # noqa: E402
import handoff  # noqa: E402
from flatcam import FlatCam, cached, ease, ramp, run  # noqa: E402
from engine import FrameSpec, Particles, Plane, Tex, TextPlane  # noqa: E402

import mats_e  # noqa: E402,F401
import door as DR  # noqa: E402
import lamp as LP  # noqa: E402

T0, T1 = handoff.T_POINT, handoff.T_TODAY          # 102.05, 116.0
FOV = 30.0
K = 1.0 / (2.0 * math.tan(math.radians(FOV / 2)))
WARM = np.array(look.C["warm"])
GRADE = handoff.GRADE_PAST

# ---------------------------------------------------------------- 门这一侧的布局（米）

FLAME = np.array([-0.30, 0.125, DR.ZD + 0.085])    # 火苗：马灯挂在门框左边石墙的钉子上，离墙面约 8.5 厘米
KEYHOLE = np.array([0.2150, -0.1701])              # 锁片上锁孔圆孔部分的圆心
L19 = plan._CHARS[18]

# ---------------------------------------------------------------- 镜头

T_SWITCH = 106.55                                   # 穿过锁孔、换到水下镜头的时刻
H0 = 0.75


def _flame_center(H):
    """让火苗（深度 FLAME[2]）落在交接光点的画面位置上时，镜头画面中心的 y。"""
    d = H * K
    return FLAME[1] - (0.5 - handoff.POINT_SCREEN[1]) * H * (d - FLAME[2]) / d


CAM_A = FlatCam([
    (T0, FLAME[0], _flame_center(H0), H0),          # 火苗正好在交接光点的位置
    (102.55, FLAME[0] + 0.010, _flame_center(0.725) - 0.004, 0.725),
    (103.25, -0.175, 0.060, 0.575),                 # "還留着晚燈"竖着写在门框立柱上
    (103.85, -0.050, 0.008, 0.450),
    (104.45, 0.055, -0.078, 0.340),                 # "鎖控著"：镜头落到锁上
    (104.95, 0.100, -0.100, 0.300),
    (105.45, 0.175, -0.128, 0.235),                 # "鎖孔的"
    (105.80, 0.211, -0.140, 0.168),                 # "空"写在锁片上方，字和锁孔同在画面里
    (106.00, KEYHOLE[0], -0.160, 0.100),            # "空"落向锁孔，镜头推近锁孔
    (106.15, KEYHOLE[0], -0.1675, 0.052),
    (106.32, KEYHOLE[0], KEYHOLE[1], 0.024),
    (T_SWITCH, KEYHOLE[0], KEYHOLE[1], 0.0085),     # 眼睛已在孔道出口之后
], fov=FOV, near=0.0006, far=400.0)

HB = 3.0                                            # 水下镜头的画面高（米）
B_START = np.array([0.0, -1.05])                    # 交接时水下镜头的画面中心（水面在 y = 0）
_EA = np.array([KEYHOLE[0], KEYHOLE[1], 0.0085 * K])
B_OFFSET = _EA - np.array([B_START[0], B_START[1], HB * K])   # 水下世界在门这一侧的平移量


def camera(t):
    if t < T_SWITCH:
        return CAM_A(t)
    return CAM_B(t)


# ---------------------------------------------------------------- 灯

def flame_k(t):
    """火苗的亮度：交接时是一个小光点，随后在约半秒里长成完整的火苗；之后带一点煤油灯特有的缓慢摇曳。"""
    grow = float(ease(ramp(t, 102.08, 102.55)))
    flick = 1.0 + 0.035 * math.sin(t * 7.1) + 0.022 * math.sin(t * 13.7 + 1.3) + 0.012 * math.sin(t * 29.0 + 0.4)
    return grow, flick


def light_k(t):
    """照到门上的灯光：火苗长成之后，眼睛渐渐适应，门面在约一秒里被照亮。"""
    grow, flick = flame_k(t)
    return float(ease(ramp(t, 102.15, 103.05))) * flick


def lamp_uniforms(t):
    k = light_k(t)
    glow = key_glow(t)
    return {"L_pos": tuple(FLAME), "L_col": tuple(np.array([1.0, 0.70, 0.40]) * 2.3 * k), "L_r0": 0.42,
            "L_amb": (0.030, 0.037, 0.055), "K_glow": (KEYHOLE[0], KEYHOLE[1], 0.010, glow),
            "K_col": (0.30, 0.95, 1.05)}


def key_glow(t):
    """锁孔透出的冷青色光："孔"字时开始隐约可见，"空"落进去之后变亮。"""
    return 0.25 * float(ease(ramp(t, L19[9], L19[11]))) + 1.6 * float(ease(ramp(t, L19[11] + 0.45, L19[11] + 0.75)))


def lamp_tex():
    def make():
        L = LP.lamp_layers()
        rgb, base, hfrac, aspect = LP.flame_sprite()
        h = rgb.shape[0]
        fade = np.clip(np.linspace(-0.4, 1.6, h), 0, 1)[:, None, None] ** 1.5          # 火苗顶端（照片里被裁掉）渐隐
        return dict(base=Tex(L[..., :4]), glass=Tex(L[..., 4]), rim=Tex(L[..., 5]),
                    flame=Tex(np.clip(rgb * fade, 0, None)), flame_meta=(base, hfrac, aspect),
                    dot=Tex(handoff._soft_dot(256, 2.2)), core=Tex(handoff._soft_dot(128, 3.0)))
    return cached("lamp_tex", make)


def lamp_items(t, H):
    tx = lamp_tex()
    grow, flick = flame_k(t)
    k = grow * flick
    (cx, cy), (w, h) = LP.crop_geometry()
    c = (FLAME[0] + cx, FLAME[1] + cy, FLAME[2])
    items = []
    lit = 0.06 + 0.94 * k
    # 挂灯的铁丝和墙上的钉子：灯帽顶的挂环用一段铁丝挂在钉子上，钉帽被下面的灯光照亮下沿
    hx, hy = LP.px_to_local(*LP.HANG_PX)
    ring = np.array([FLAME[0] + hx, FLAME[1] + hy])
    nail = ring + np.array([0.0, 0.028])
    wire = cached("lamp_wire", lambda: Tex(np.dstack([np.full((64, 8, 3), 0.05, np.float32),
                                                      np.ones((64, 8), np.float32)])))
    op = min(1.0, grow * 2.5)
    items.append(Plane(wire, center=((ring + nail) / 2).tolist() + [FLAME[2] - 0.004], size=(0.0016, 0.030),
                       color=(0.5 + 2.0 * lit,) * 3, group="past", opacity=op, stack="lamp"))
    items.append(Plane(tx["dot"], center=(nail[0], nail[1], DR.ZD + 0.004), size=(0.010, 0.010),
                       color=(0.05, 0.045, 0.04), group="past", opacity=op))
    items.append(Plane(tx["dot"], center=(nail[0], nail[1] - 0.0015, DR.ZD + 0.0045), size=(0.006, 0.004),
                       blend="add", color=tuple(np.array([1.0, 0.65, 0.35]) * 0.5 * k), group="past"))
    items.append(Plane(tx["base"], center=c, size=(w, h), color=(lit * 0.95,) * 3, group="past", stack="lamp",
                       opacity=op))                                   # 灯身随火光亮起才显出来
    items.append(Plane(tx["rim"], center=c, size=(w, h), blend="add", color=tuple(np.array([1.0, 0.62, 0.30]) * 0.35 * k),
                       group="past", stack="lamp"))
    items.append(Plane(tx["glass"], center=c, size=(w, h), blend="add",
                       color=tuple(np.array([1.0, 0.80, 0.55]) * 1.25 * k), group="past", stack="lamp"))
    # 火苗：底部在灯芯上，摇曳时轻轻左右摆、上下伸缩
    (bu, bv), hfrac, aspect = tx["flame_meta"]
    fh = 0.034 * (0.35 + 0.65 * grow) * (1.0 + 0.05 * math.sin(t * 9.3) + 0.03 * math.sin(t * 17.0))
    sh = fh / hfrac
    sw = sh * aspect
    sway = 2.5 * math.sin(t * 3.1) + 1.5 * math.sin(t * 7.7)
    fc = (FLAME[0] + (0.5 - bu) * sw, FLAME[1] - 0.012 + (bv - 0.5) * sh, FLAME[2] + 0.002)
    items.append(Plane(tx["flame"], center=fc, size=(sw, sh), rot=(0, 0, sway), blend="add",
                       color=(1.5 * k, 1.35 * k, 1.2 * k), group="past", stack="lamp"))
    # 玻璃罩里的光晕与屋外的大光晕
    items.append(Plane(tx["dot"], center=(FLAME[0], FLAME[1] + 0.005, FLAME[2] + 0.003), size=(0.13, 0.17), blend="add",
                       color=tuple(np.array([1.0, 0.75, 0.45]) * 0.55 * k), group="past", stack="lamp"))
    items.append(Plane(tx["dot"], center=(FLAME[0], FLAME[1], FLAME[2] + 0.004), size=(0.9, 0.9), blend="add",
                       color=tuple(np.array([1.0, 0.70, 0.40]) * 0.07 * k), group="past", stack="lamp"))
    # 交接的光点：与 handoff.point_items 相同的两层，钉在火苗上，随火苗长成而淡出
    kp = 1.0 - float(ease(ramp(t, 102.08, 102.50)))
    if kp > 0.001:
        Hs = H * (CAM_A.K * H - FLAME[2]) / (CAM_A.K * H)
        pc = np.array(handoff.POINT_COLOR)
        items.append(Plane(tx["dot"], center=tuple(FLAME + [0, 0, 0.006]), size=(handoff.POINT_HALO * Hs,) * 2, blend="add",
                           color=tuple(pc * 0.55 * kp), group="past"))
        items.append(Plane(tx["core"], center=tuple(FLAME + [0, 0, 0.007]), size=(handoff.POINT_CORE * Hs * 2.2,) * 2,
                           blend="add", color=tuple(np.array([1.0, 0.93, 0.80]) * 2.2 * kp), group="past"))
    return items


# ---------------------------------------------------------------- 门

def door_tex():
    def make():
        wrgb, wb, ws = DR.canvas("wide")
        mrgb, mb, ms = DR.canvas("mid")
        ma = DR.mid_alpha()
        hrgba, hb, hc, hs = DR.hasp_patch()
        erg, poly = DR.escutcheon()
        esize, eworld, _ = DR.esc_geometry()
        geo = lambda s: (((s["x"][0] + s["x"][1]) / 2, (s["y"][0] + s["y"][1]) / 2), (s["x"][1] - s["x"][0], s["y"][1] - s["y"][0]))
        wc, wsz = geo(ws)
        mc, msz = geo(ms)
        from scipy.ndimage import gaussian_filter
        elum = erg[..., :3] @ common.LUMA
        eb = np.clip((elum - gaussian_filter(elum, 4)) * 2 + 0.5, 0, 1)
        return dict(
            wide=Tex(wrgb), wide_b=Tex(wb), wide_geo=(wc, wsz), wide_mask=DR.keyhole_path(wc, wsz),
            mid=Tex(np.dstack([mrgb, ma])), mid_b=Tex(mb), mid_geo=(mc, msz), mid_mask=DR.keyhole_path(mc, msz),
            hasp=Tex(hrgba), hasp_b=Tex(hb), hasp_geo=(hc, hs),
            esc=Tex(erg), esc_b=Tex(eb), esc_geo=(DR.ESC_C, esize),
            dark=Tex(np.zeros((4, 4, 4), np.float32) + [0, 0, 0, 1]),
            tunnel=[DR.keyhole_path(KEYHOLE, (0.06, 0.06)) for _ in range(1)])
    return cached("door_tex", make)


def door_items(t, U):
    tx = door_tex()
    z = DR.ZD
    items = []
    for key, bk, bump_k in (("wide", "wide_b", 0.7), ("mid", "mid_b", 0.7), ("hasp", "hasp_b", 0.45)):
        c, s = tx[key + "_geo"]
        u = dict(U, bump=tx[bk], has_bump=1.0, bump_k=bump_k)
        items.append(Plane(tx[key], center=(c[0], c[1], z), size=s, group="past", material="e_lit", uniforms=u,
                           mask=tx.get(key + "_mask"), stack="door"))
    items += chalk_items(t, U)
    # 锁片：略高出门面，带一圈很淡的影子
    c, s = tx["esc_geo"]
    items.append(Plane(tx["esc"], center=(c[0], c[1], z + 0.0015), size=s, group="past", material="e_lit",
                       uniforms=dict(U, bump=tx["esc_b"], has_bump=1.0, bump_k=1.2), stack="esc"))
    items += tunnel_items(t)
    return items


def tunnel_items(t):
    """锁孔的孔道：门厚约 3.5 厘米，孔道是一叠挖了锁孔形洞的薄片，越深越被另一边的青光照亮。"""
    if t < 105.5:
        return []
    tx = door_tex()
    path = tx["tunnel"][0]
    items = []
    n = 36
    glow = min(key_glow(t), 1.6) / 1.6
    for i in range(n):
        f = (i + 1) / n
        z = DR.ZD - 0.001 - 0.034 * f
        items.append(Plane(None, center=(KEYHOLE[0], KEYHOLE[1], z), size=(0.06, 0.06), color=(1, 1, 1), group="past",
                           material="e_tunnel", uniforms={"depth01": f, "tun_cold": tuple(np.array([0.10, 0.36, 0.42]) * (0.4 + 0.6 * glow))},
                           mask=path))
    return items


# ---------------------------------------------------------------- 粉笔字

COL1 = dict(x=-0.098, y0=0.262, step=0.062, h=0.058)       # 還留着晚燈：竖着写在灯右边的门框立柱上，像门联
ROW2 = dict(y=-0.106, step=0.050, h=0.046)                  # 鎖控著　鎖孔的空：搭扣下面一行，"空"在锁片正上方


def chalk_layout():
    text = look.trad(look.lyric(19)).replace("　", "")
    pos = []
    for i in range(5):
        pos.append((COL1["x"], COL1["y0"] - i * COL1["step"], COL1["h"]))
    xs = [KEYHOLE[0] - ROW2["step"] * k for k in (7, 6, 5, 3, 2, 1, 0)]
    for x in xs:
        pos.append((x, ROW2["y"], ROW2["h"]))
    return text, pos


def kong_fall(t):
    """"空"落进锁孔：在"空"的元音起点写出，停约 0.1 秒，随后落向锁孔、越落越小（落进深处），最后穿进锁孔。
    返回 (中心 x, y, 字高缩放, 下落进度)。"""
    tc = L19[11]
    u = ramp(t, tc + 0.10, tc + 0.40)
    s = u * u * (3 - 2 * u)
    x0, y0 = KEYHOLE[0], ROW2["y"]
    y = y0 + (KEYHOLE[1] - y0) * (u ** 1.6)
    scale = 1.0 - 0.86 * s
    return x0, y, scale, s


def chalk_items(t, U):
    text, pos = chalk_layout()
    items = []
    for i, (ch, (x, y, h)) in enumerate(zip(text, pos)):
        tc = L19[i]
        if t < tc - 0.03:
            continue
        rev = ramp(t, tc - 0.03, tc + 0.20)
        u = dict(U, reveal=rev, chalk_k=0.75)
        if i == 11:                                  # "空"
            x, y, sc, s = kong_fall(t)
            fade = 1.0 - ramp(t, tc + 0.48, tc + 0.62)
            if fade <= 0.0:
                continue
            # 落到锁孔口以后画在孔道里（锁片之后），只从锁孔里看得见，随后被另一边的光吞没
            deep = s > 0.86
            z = DR.ZD - 0.004 if deep else DR.ZD + 0.004
            items.append(TextPlane(ch, kind="serif", weight=800, height=h * sc, color=tuple(WARM * (1.0 + 0.8 * s)),
                                   center=(x, y, z), group="past", material="e_chalk",
                                   uniforms=dict(u, chalk_k=0.75 * (1 - s)), opacity=fade))
            continue
        items.append(TextPlane(ch, kind="serif", weight=800, height=h, color=tuple(WARM), center=(x, y, DR.ZD),
                               group="past", material="e_chalk", uniforms=u, stack="door"))
    return items


def darkness(t):
    """开头的黑暗：与交接帧的底色相同，火苗长成、眼睛适应之后淡去（画在门之前、灯之后）。"""
    a = 1.0 - float(ease(ramp(t, 102.10, 102.80)))
    if a <= 0.001:
        return []
    return [Plane(None, center=(FLAME[0], FLAME[1], DR.ZD + 0.03), size=(8.0, 6.0), color=(0.010, 0.012, 0.018),
                  opacity=a, group="past")]


# ---------------------------------------------------------------- 水下

import uw as UW  # noqa: E402
import water as WT  # noqa: E402
import l21 as L21M  # noqa: E402
import l22 as L22M  # noqa: E402
import strata as ST  # noqa: E402

# 上升：从 RISE_T0 静止开始，速度按时间的平方增长，第三下底鼓（"前"，113.62）时穿出水面；之后继续加速，
# 115.55 鼓恢复连续演奏时加速度明显加大，直到 115.97 冲破最上面一层。速度连续、单调增加，加速度也连续。
RISE_T0, RISE_Y0 = 111.60, -2.20
T_SURF = WT.KICK3
_C1 = -RISE_Y0 * 3.0 / (T_SURF - RISE_T0) ** 3          # 第一段 v = c1 (t - t0)²，正好在 T_SURF 升到水面
_V1 = _C1 * (T_SURF - RISE_T0) ** 2
_A1 = 2 * _C1 * (T_SURF - RISE_T0)
T_DRUM = BAR(68, 1.5)                                    # 115.55
_B2 = (10.5 - _V1 - _A1 * (T_DRUM - T_SURF)) / (T_DRUM - T_SURF) ** 2
_V2 = 10.5
_A2 = _A1 + 2 * _B2 * (T_DRUM - T_SURF)
_C3 = 66.0


def rise_v(t):
    """上升速度（米/秒）。"""
    if t <= RISE_T0:
        return 0.0
    if t <= T_SURF:
        return _C1 * (t - RISE_T0) ** 2
    if t <= T_DRUM:
        s = t - T_SURF
        return _V1 + _A1 * s + _B2 * s * s
    s = t - T_DRUM
    return _V2 + _A2 * s + _C3 * s * s


def rise_y(t):
    """上升途中镜头画面中心的高度（解析积分）。"""
    if t <= RISE_T0:
        return RISE_Y0
    if t <= T_SURF:
        return RISE_Y0 + _C1 * (t - RISE_T0) ** 3 / 3
    y1 = 0.0
    if t <= T_DRUM:
        s = t - T_SURF
        return y1 + _V1 * s + _A1 * s * s / 2 + _B2 * s ** 3 / 3
    s2 = T_DRUM - T_SURF
    y2 = y1 + _V1 * s2 + _A1 * s2 * s2 / 2 + _B2 * s2 ** 3 / 3
    s = t - T_DRUM
    return y2 + _V2 * s + _A2 * s * s / 2 + _C3 * s ** 3 / 3


def rise_h(t):
    """最后约半秒镜头同时略微推近，冲向最上面一层。"""
    return HB * (1.0 - 0.14 * float(ease(ramp(t, 115.45, 115.97))))


def rise_samples():
    ts = np.arange(RISE_T0 + 0.04, T1 + 0.0001, 0.04)
    return [(float(t), rise_y(float(t)), rise_h(float(t))) for t in ts]

CAM_B = FlatCam([
    (T_SWITCH, B_START[0], B_START[1], HB),
    (107.60, -0.02, -1.22, HB),
    (108.40, 0.05, -1.52, HB),                      # 跟着钟缓缓下沉
    (109.00, 0.12, -2.02, HB),                      # "多沉重"：钟加速沉出画面，镜头跟下去一段
    (109.50, 0.30, -2.18, HB),                      # 停住
    (110.30, 0.43, -2.20, HB),                      # 风筝线绷直后，镜头对准它
    (RISE_T0, WT.LINE_X, RISE_Y0, HB),
] + [(t, WT.LINE_X, y, h) for t, y, h in rise_samples()], fov=FOV, near=0.01, far=600)


def configure_final():
    """最后一层旧纸在 z = -40，下沿落在远处的水面上，被夜空、水面和层带挡住，只在层带扫过之后露出来。按上升的镜头
    算出两处位置："換了人間"那一列（115.25 秒时列顶在画面上沿下方 5%，此后随纸慢慢下移，到 115.90 秒列底仍在画面
    内），以及撕口的中心（115.97 秒时在画面正中，也就是风筝线指着的地方）。"""
    z = L22M.FINAL["z"]

    def world(t, sx, sy):
        (wx, wy), _ = CAM_B.screen_to_world(t, sx, sy, z=z)
        return wx, wy
    tx, ty = world(115.25, L22M.TEXT_SX, 0.05)
    L22M.configure_final(0.0, (tx, ty), world(L22M.T_BURST, 0.5, 0.5))


configure_final()


def world_b(t, bx, by, bH, off=(0.0, 0.0, 0.0)):
    cam = (bx, by, bH)
    U = dict(UW.UW_DEFAULTS, w_off=tuple(float(v) for v in off))
    items = []
    items += WT.back_items(t, cam, U)
    items += WT.surface_items(t, cam, U)
    items += WT.ray_items(t, cam, U)
    items += WT.mote_items(t, cam, U)
    items += WT.bell_items(t, U)
    items += WT.ring_items(t, U)
    items += WT.l20_items(t, U)
    items += WT.rope_items(t, cam, U)
    items += L21M.bead_items(t, cam, U)                      # 线上的旧字一直排到最上面
    if by < 0.0:
        items += L21M.l21_items(t, U) + L21M.hand_items(t, U) + L21M.wind_items(t, U)
    items += L22M.splash_items(t, cam, U)
    items += L22M.sky_items(t, cam, U)
    items += ST.band_items(t, cam)
    items += ST.flake_items(t, cam)
    items += L22M.final_items(t, cam, U)
    return items


def shift(items, off):
    for it in items:
        if isinstance(it, Particles):
            it.pos = np.ascontiguousarray(it.pos + np.asarray(off, np.float32))
        else:
            it.center = it.center + np.asarray(off, float)
    return items


# ---------------------------------------------------------------- 组装

def frame(t):
    if t < T0 + 2.5 / 60:
        return handoff.point_frame(t)
    if t >= 115.97:
        return handoff.white_frame(t, handoff.COLD_WHITE)
    cam, H = camera(t)
    items = []
    if t < T_SWITCH:
        U = lamp_uniforms(t)
        items += door_items(t, U)
        items += lamp_items(t, H)
        items += darkness(t)
        if t > 105.0:
            ex = np.array(cam.eye) - B_OFFSET
            items += shift(world_b(t, ex[0], ex[1], ex[2] / K, B_OFFSET), B_OFFSET)
    else:
        items += world_b(t, *CAM_B.state(t)[:3])
        items += L22M.lyric_items(t, CAM_B)
        items += L22M.lens_items(t, CAM_B)
    return FrameSpec(cam, items, grade=grade(t))


def grade(t):
    """过去的标准调色；最后约 0.15 秒随冲破的冷光去掉暖色、淡到冷白，与 handoff.white_frame 接上。"""
    if t < 115.70:
        return GRADE
    u = float(ease(ramp(t, 115.70, 115.965)))
    g = {k: dict(v) for k, v in GRADE.items()}
    w0 = np.array([1.06, 0.97, 0.80])
    g["past"]["warmth"] = tuple(w0 * (1 - u) + np.ones(3) * u)
    g["past"]["grain"] = 0.028 * (1 - 0.7 * u)
    f = float(ease(ramp(t, 115.86, 115.965)))
    g["final"] = {"fade": f, "fade_color": handoff.COLD_WHITE}
    return g


def subframes(t):
    """正式渲染每帧的子帧数：平常 2 个；上升段按每帧画面上的位移估计，使相邻两个子帧之间的位移不超过约 8 像素
    （180 度快门下一帧的运动模糊长度是帧间位移的一半；近处的碎片比主平面快约 1.25 倍）。最多 16 个。"""
    if t < RISE_T0 or t >= 115.97:
        return 2
    px = rise_v(t) / rise_h(t) * 1080 / 60 * 0.5 * 1.25
    return int(min(16, max(2, math.ceil(px / 8.0))))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "report":
        CAM_A.report(T0, T_SWITCH)
        CAM_B.report(T_SWITCH, T1)
        ts = np.arange(RISE_T0, T1, 1 / 60)
        n = np.array([subframes(t) for t in ts])
        for k in sorted(set(n)):
            sel = ts[n == k]
            print(f"子帧 {k:2d}：{sel.min():.2f}–{sel.max():.2f} s，{len(sel)} 帧")
    elif len(sys.argv) > 1 and sys.argv[1] == "final":
        run(frame, "主歌二", T0, T1, common.OUT, subframes=subframes)      # 正式渲染按 subframes(t) 取子帧数
    else:
        run(frame, "主歌二", T0, T1, common.OUT)                           # still 只接受整数子帧数，取缺省的 2
