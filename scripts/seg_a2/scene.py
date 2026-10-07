"""主歌一前半（L01–L04，27.0–40.1167 秒）。

python scene.py preview | sheet 输出.png 秒,秒,... | still 秒 输出.png
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
from plan import T, BAR  # noqa: E402
import handoff as HO  # noqa: E402
from flatcam import FlatCam, cached, ease, ramp, run  # noqa: E402
from engine import FrameSpec  # noqa: E402

import ink as IK  # noqa: E402
import strokes as ST  # noqa: E402

T0, T1 = 27.0, 2406 / 60 + 1 / 120        # 渲染到第 2406 帧为止（含）
ROOT = HERE.parents[1]
OUT = ROOT / "renders" / "seg_a2"

# ---------------------------------------------------------------- L01 的排布

L01 = look.trad(look.lyric(1))            # 守着漸漸消失在　街道的吵
EM1 = 1.5                                 # 字高
LINE_Y = 0.45                             # 这一行字框中心的高度（纸面坐标）
PPE_KOU = 2048                            # "吵"的墨迹贴图分辨率：镜头要推进它的"口"


def l01_chars():
    """[(字, 字框中心 (x, y), 转角, 开始时刻, 书写时长, 字序)]。"""
    def make():
        out = []
        k = 0
        adv = [0.55 if ch == "　" else 1.0 for ch in L01]          # 乐句间隔写成半个字宽
        left = -sum(adv) * EM1 / 2
        xs = left + (np.cumsum(adv) - np.array(adv) / 2) * EM1
        onsets = [T(1, i) for i in range(11)]
        for i, ch in enumerate(L01):
            if ch == "　":
                continue
            x = float(xs[i])
            dy, rot, sc = IK.jitter(f"L01{i}{ch}")
            if ch == "吵":
                dy, rot = 0.0, 0.0                  # 镜头要扎进它的"口"，保持端正
            t0 = onsets[k] - 0.03
            nxt = onsets[k + 1] if k + 1 < len(onsets) else onsets[k] + 0.5
            dur = float(np.clip(0.9 * (nxt - onsets[k]), 0.22, 0.42))
            out.append((ch, (x, LINE_Y + dy * EM1), rot, t0, dur, k))
            k += 1
        return out
    return cached("l01", make)


def kou_counter():
    """"吵"左边"口"的字怀（em）：在墨迹贴图的有向距离上取不与边界相连、位于左半边的空白连通区域。
    返回 (中心 (ex, ey), 宽, 高)，em 坐标 y 向下。"""
    def make():
        from scipy import ndimage
        d = ST.ink_tex_data("吵", 1024).astype(np.float32)
        sdf = (d[..., 0] - 2.0) / 10.0
        lab, n = ndimage.label(sdf < 0)
        border = set(np.unique(np.r_[lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
        best, area = None, 0
        for j in range(1, n + 1):
            if j in border:
                continue
            ys, xs = np.nonzero(lab == j)
            if xs.mean() < lab.shape[1] / 2 and len(xs) > area:
                best, area = (ys, xs), len(xs)
        ys, xs = best
        ppe = 1024
        ex0, ex1 = ST.BOX[0] + xs.min() / ppe, ST.BOX[0] + (xs.max() + 1) / ppe
        ey0, ey1 = ST.BOX[1] + ys.min() / ppe, ST.BOX[1] + (ys.max() + 1) / ppe
        # 中心取空白区域的形心：手写的"口"是个略歪的四边形，形心比外接矩形的中心更像视觉上的中心
        cx, cy = ST.BOX[0] + (xs.mean() + 0.5) / ppe, ST.BOX[1] + (ys.mean() + 0.5) / ppe
        return (cx, cy), ex1 - ex0, ey1 - ey0
    return cached("kou", make)


def kou_world():
    """"口"字怀的世界坐标：(中心 (x, y), 宽, 高)。"""
    ch, c, rot, t0, dur, k = next(e for e in l01_chars() if e[0] == "吵")
    (ex, ey), w, h = kou_counter()
    return IK.em_to_world(c, EM1, rot, ex, ey), w * EM1, h * EM1


def kou_edges():
    """字怀四条内边的直线（世界坐标）：对空白区域每一行（列）的最左、最右（最上、最下）像素拟合直线，
    只用中间 70% 的部分，避开圆转的内角。返回 {"left"/"right": (斜率 a, 截距 b) 表示 x = a·y + b，
    "top"/"bottom": (a, b) 表示 y = a·x + b}，以及字怀的像素坐标与世界坐标的换算。"""
    def make():
        from scipy import ndimage
        ppe = 1024
        d = ST.ink_tex_data("吵", ppe).astype(np.float32)
        sdf = (d[..., 0] - 2.0) / 10.0
        lab, n = ndimage.label(sdf < 0)
        border = set(np.unique(np.r_[lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
        cand = [j for j in range(1, n + 1) if j not in border]
        j = max(cand, key=lambda j: (lab == j).sum() if np.nonzero(lab == j)[1].mean() < lab.shape[1] / 2 else 0)
        m = lab == j
        ys, xs = np.nonzero(m)
        ch, c, rot, t0, dur, k = next(e for e in l01_chars() if e[0] == "吵")
        to_w = lambda px, py: IK.em_to_world(c, EM1, rot, ST.BOX[0] + px / ppe, ST.BOX[1] + py / ppe)
        out = {}
        y0, y1 = ys.min(), ys.max()
        rows = np.arange(int(y0 + 0.15 * (y1 - y0)), int(y1 - 0.15 * (y1 - y0)))
        L = np.array([[xs[ys == r].min(), r] for r in rows], float)
        R = np.array([[xs[ys == r].max() + 1, r] for r in rows], float)
        x0, x1 = xs.min(), xs.max()
        cols = np.arange(int(x0 + 0.15 * (x1 - x0)), int(x1 - 0.15 * (x1 - x0)))
        Tp = np.array([[cc, ys[xs == cc].min()] for cc in cols], float)
        Bt = np.array([[cc, ys[xs == cc].max() + 1] for cc in cols], float)
        for name, pts, vert in (("left", L, True), ("right", R, True), ("top", Tp, False), ("bottom", Bt, False)):
            W = np.array([to_w(px, py) for px, py in pts])
            if vert:
                a, b = np.polyfit(W[:, 1], W[:, 0], 1)
            else:
                a, b = np.polyfit(W[:, 0], W[:, 1], 1)
            out[name] = (float(a), float(b))
        return out
    return cached("kou_edges", make)


def roll_land():
    return cached("roll_land", floor_roll)


def floor_roll():
    """让"口"的右边那一竖（转过来以后是方框的下边，猫走在它上面）在画面上水平所需的滚转角（度）。"""
    a, b = kou_edges()["right"]
    # 直线 x = a·y + b 沿纸面向上的方向为 (a, 1)；画面向右的方向 (cos r, sin r) 要与它一致
    return math.degrees(math.atan2(1.0, a))


def box_axes(roll=None):
    """方框里的画面坐标轴：u 为画面向右、v 为画面向上的世界单位向量，原点在字怀中心。"""
    r = math.radians(roll_land() if roll is None else roll)
    return np.array([math.cos(r), math.sin(r)]), np.array([-math.sin(r), math.cos(r)])


def box_to_world(u, v):
    K, kw, kh = kou_world()
    eu, ev = box_axes()
    return K + eu * u + ev * v


def box_floor():
    """方框下边（"口"右边一竖的内边线）在 v 方向上的位置（世界单位，负数）。"""
    K, kw, kh = kou_world()
    a, b = kou_edges()["right"]
    # 直线 x = a·y + b 到中心的距离
    return -abs(K[0] - (a * K[1] + b)) / math.sqrt(1 + a * a)


# ---------------------------------------------------------------- 镜头

T_DIVE0 = 30.52           # 开始扎向"口"（"吵"写到最后几笔时）
T_LAND = BAR(19)          # 31.334 底鼓：落进方框


def _cam_keys():
    """27.0–T_LAND 的镜头：前段几乎不动，"街道的"写出时慢慢靠近行尾，"吵"写完后扎进"口"的字怀，
    推进中绕视线转 90 度。高度按对数变化率积分得到，变化率先平稳增大、在扎进去的一段保持近似恒定、
    落定前 0.22 秒减到零，所以画面放大的速度均匀，最后稳稳停在底鼓上。"""
    K, kw, kh = kou_world()
    H0 = HO.PAPER_CAM[2]
    H_land = h_land()                    # 字怀的短边占画面高度的 84%，四条笔画露在画面四边
    ts = np.arange(T0, T_LAND + 1e-9, 1 / 120)
    # 对数高度的变化率（每秒），形状固定，再整体缩放到正好落在 H_land
    def rate(t):
        r = 0.02
        r += 0.30 * float(ease(ramp(t, 29.2, 30.1)))          # "街道的"写出时慢慢靠近行尾
        r += 4.6 * float(ease(ramp(t, T_DIVE0, T_DIVE0 + 0.16)))   # 扎进去：很快达到恒定的推进速度
        r *= 1.0 - float(ease(ramp(t, T_LAND - 0.24, T_LAND)))      # 落定前 0.24 秒减速，停在底鼓上
        return r
    rr = np.array([rate(t) for t in ts])
    cum = np.r_[0, np.cumsum((rr[1:] + rr[:-1]) / 2 * np.diff(ts))]
    cum *= math.log(H0 / H_land) / cum[-1]
    Hs = H0 * np.exp(-cum)
    # 滚转：随推进的进度（对数高度）转过 90 度，从扎进去开始
    prog = cum / cum[-1]
    p0 = np.interp(T_DIVE0, ts, prog)
    roll = roll_land() * ease(np.clip((prog - p0) / (1 - p0), 0, 1))
    # "口"在画面上的位置：起初在画面右侧（行尾），推进时逐渐移到画面中心
    c0 = np.array([HO.PAPER_CAM[0], HO.PAPER_CAM[1]])
    s0 = (K - c0) / H0
    g = 1.0 - ease(np.clip((prog - 0.10) / 0.80, 0, 1)) ** 0.8
    keys = []
    for t, H, r, gg in zip(ts[::2], Hs[::2], roll[::2], g[::2]):
        a = math.radians(r)
        R = np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])
        c = K - R @ (s0 * gg * H)
        keys.append((float(t), float(c[0]), float(c[1]), float(H), float(r)))
    return keys


def h_land():
    K, kw, kh = kou_world()
    return kw / 0.84


# 落定以后的镜头：(时刻, u, v, 画面高)，u、v 为画面中心相对字怀中心的偏移（方框坐标，以落定时的画面高为单位），
# 画面高也以落定时为单位。滚转保持落定时的角度。
POST_KEYS = [
    (33.80, 0.22, -0.10, 0.84),      # L02：慢慢靠近右下的内角，猫在那里拐过角
    (34.95, "tv", 0.0, 1.89),        # L03：后退，整台电视入画（"tv" 表示画面中心在电视机中心）
    (37.55, "tv", 0.0, 1.81),        # 天气预报时极慢地推近
    (38.45, "tv", 0.0, 2.16),        # L04：照片从亮点展开，略微后退让整张照片入画
    (40.10, "tv", 0.0, 2.08),
]


def camera():
    def make():
        keys = _cam_keys()
        t_last, x, y, H, r = keys[-1]
        HL = h_land()
        g = tv_geom()
        for t, u, v, hm in POST_KEYS:
            c = box_to_world(g["du"], g["dv"]) if u == "tv" else box_to_world(u * HL, v * HL)
            keys.append((t, float(c[0]), float(c[1]), hm * HL, r))
        t_last, x, y, H, r = keys[-1]
        keys.append((T1 + 0.5, x, y, H, r))
        return FlatCam(keys, fov=30.0)
    return cached("cam", make)


# ---------------------------------------------------------------- L02：方框里的字

L02 = look.trad(look.lyric(2))            # 像消失在　角落裏　的貓


def l02_chars():
    """方框里的两行钢笔字：上一行"像消失在"靠左上，下一行"角落裏　的貓"立在方框的下边上、靠右，
    末字"貓"离右下内角还有猫走几步的距离。返回 [(字, 世界坐标中心, 转角, 开始时刻, 时长, 字序)]。"""
    def make():
        HL = h_land()
        em = 0.15 * HL
        fl = box_floor()
        a, b = L02.split("　", 1)
        line2 = b                                         # 角落裏　的貓
        on = [T(2, i) for i in range(9)]
        out = []
        k = 0
        r = roll_land()
        # 第一行
        u = -0.50 * HL
        for ch in a:
            dy, rot, sc = IK.jitter(f"L02{k}{ch}")
            c = box_to_world(u + em / 2, 0.12 * HL + dy * em)
            out.append((ch, c, r + rot, on[k] - 0.03, 0.30, k, em * sc))
            u += em
            k += 1
        # 第二行：右端（"貓"的右缘）在 u = 0.52·HL
        adv = [0.55 if ch == "　" else 1.0 for ch in line2]
        u = 0.52 * HL - sum(adv) * em
        for ch, ad in zip(line2, adv):
            if ch != "　":
                dy, rot, sc = IK.jitter(f"L02{k}{ch}")
                if ch == "貓":
                    rot, sc = 0.0, 1.0                    # 要化成猫，摆正
                v = fl + 0.012 * HL + em * 0.5
                c = box_to_world(u + em / 2, v + dy * em * 0.5)
                nxt = on[k + 1] if k + 1 < 9 else on[k] + 0.29
                out.append((ch, c, r + rot, on[k] - 0.03, float(np.clip(0.9 * (nxt - on[k]), 0.2, 0.38)), k, em * sc))
                k += 1
            u += ad * em
        return out
    return cached("l02", make)


def l02_items(t):
    if t < T(2) - 0.1 or t > 34.6:
        return []
    items = []
    for ch, c, rot, t0, dur, k, em in l02_chars():
        if t < t0 - 0.01:
            continue
        if ch == "貓":
            continue                                       # "貓"字由 cat 部分处理（写出后化成猫）
        items.append(IK.char_plane(ch, c, em, t0, dur, rot=rot, ppe=512, bleed=em * 0.012))
    return items


# ---------------------------------------------------------------- L02 末尾：猫

CAT_FPS = 12.0
CROUCH = 7                        # cat.FRAMES 里伏低的那一格（图版第 8 格）
# 起身、行走、冲刺的画面顺序（cat.FRAMES 的序号）：图版第 7、6 格倒过来是从伏低到站起，接着走 4 格，
# 最后用第 7、8 格的伏低前冲一蹿进墙角
SEQ = [6, 5, 0, 1, 2, 3, 6, 7]
DES = (0.0, 1.0, 2.0, 3.0, 4.0, 5.0, 6.0)    # 豸部的 7 笔（strokes_of("貓") 的序号）


def mao_char():
    return next(e for e in l02_chars() if e[0] == "貓")


def cat_timeline():
    """猫的时间表（秒）：写完"貓"、"豸"的墨开始流成伏着的猫、伏着的猫成形、开始起身、完全没入墙角。
    "貓"字左边的"豸"本是表示走兽的部首：右边的"苗"先淡去，"豸"的墨顺着纸流开，收拢成一只伏着的猫，
    猫随即起身，迈步接上 Muybridge 的步态。"""
    ch, c, rot, t0, dur, k, em = mao_char()
    t_m = t0 + dur + 0.02
    t_f0 = t_m + 0.05
    t_f1 = t_f0 + 0.24
    t_c = t_f1 + 0.08
    t_e = t_c + len(SEQ) / CAT_FPS
    return t_m, t_f0, t_f1, t_c, t_e


def cat_geom():
    """猫的尺寸与路线（方框坐标，世界单位）：猫高（含竖起的尾巴，与 L02 的字号相当）、伏着时的位置 u、
    墙（右边那一竖的内边线）的 u、脚底的 v。"""
    def make():
        HL = h_land()
        unit = 0.17 * HL
        ch, c, rot, t0, dur, k, em = mao_char()
        eu, ev = box_axes()
        K = kou_world()[0]
        u_mao = float((np.asarray(c) - K) @ eu)
        a, b = kou_edges()["top"]
        v_f = box_floor() + 0.004 * HL
        us = np.linspace(0, 0.3, 3001)
        P = K[None, :] + us[:, None] * eu[None, :] + v_f * ev[None, :]
        d = P[:, 1] - (a * P[:, 0] + b)
        u_wall = float(us[np.argmin(np.abs(d))])
        return dict(unit=unit, u0=u_mao + 0.10 * unit, u_wall=u_wall, v_f=v_f)
    return cached("cat_geom", make)


def cat_tex(i):
    def make():
        import cat as CT
        from engine import Tex
        fr, unit = CT.ink_frames()
        return [Tex(f, premultiplied=True) for f in fr]
    return cached("cat_tex", make)[i]


def cat_plane_geom(pos):
    """猫贴图平面的中心（世界坐标）与尺寸：pos 为躯干形心沿 u 的位置。"""
    import cat as CT
    g = cat_geom()
    unit = g["unit"]
    eu, ev = box_axes()
    K = kou_world()[0]
    W, Hh = CT.BOX_W * unit, CT.BOX_H * unit
    cc = K + eu * pos + ev * (g["v_f"] + Hh / 2 - 0.08 * unit)
    return cc, W, Hh


def mao_part_tex(part):
    """"貓"字拆成的两个部件："豸"（左边 7 笔）和"苗"。"""
    def make():
        from engine import Tex
        keep = set(int(i) for i in DES)
        out = {}
        for name, kp in (("zhi", keep), ("miao", set(range(40)) - keep)):
            out[name] = Tex(ST.part_tex_data("貓", 512, kp, name).astype(np.float32), premultiplied=True)
        return out
    return cached("mao_parts", make)[part]


def flow_tex():
    """伏着的猫的墨迹贴图，书写时间通道换成"墨从豸的笔画流到这里的时刻"：在猫贴图的网格上，以豸的墨迹为源
    求距离，按猫身上最远处归一，再加一点低频起伏，墨的前沿因此不是规整的圆。"""
    def make():
        import cat as CT
        from engine import Tex
        from scipy.ndimage import distance_transform_edt, map_coordinates, gaussian_filter
        fr, _ = CT.ink_frames()
        cat0 = fr[CROUCH].copy()
        H, W = cat0.shape[:2]
        g = cat_geom()
        unit = g["unit"]
        ch, c, rot, t0, dur, k, em = mao_char()
        eu, ev = box_axes()
        K = kou_world()[0]
        ys, xs = np.mgrid[0:H, 0:W].astype(np.float32)
        u = (xs / W - 0.5) * CT.BOX_W * unit
        v = (1.0 - ys / H) * CT.BOX_H * unit - 0.08 * unit
        wx = K[0] + eu[0] * (g["u0"] + u) + ev[0] * (g["v_f"] + v)
        wy = K[1] + eu[1] * (g["u0"] + u) + ev[1] * (g["v_f"] + v)
        r = math.radians(rot)
        dx, dy = wx - c[0], wy - c[1]
        ex = (dx * math.cos(r) + dy * math.sin(r)) / em + 0.5
        ey = -(-dx * math.sin(r) + dy * math.cos(r)) / em - 0.38
        ppe = 512
        zd = ST.part_tex_data("貓", ppe, set(int(i) for i in DES), "zhi").astype(np.float32)
        px = (ex - ST.BOX[0]) * ppe
        py = (ey - ST.BOX[1]) * ppe
        src = map_coordinates(zd[..., 0], [py, px], order=1, mode="constant", cval=0.0) > 2.0
        catm = cat0[..., 0] > 2.0
        d = distance_transform_edt(~src)
        rng = np.random.default_rng(8)
        wob = gaussian_filter(rng.normal(0, 1, (H, W)).astype(np.float32), 18)
        wob = wob / (np.abs(wob).max() + 1e-6)
        dmax = max(float(d[catm].max()), 1.0)
        T = np.clip(d / dmax, 0, 1) ** 0.85
        T = np.clip(T + 0.10 * wob * (T > 0.02), 0, 1)
        cat0[..., 1] = T
        return Tex(cat0, premultiplied=True)
    return cached("flow_tex", make)


def cat_pos(t):
    """躯干形心沿 u 的位置：伏着时不动；起身两格里向前挪一点；走 4 格，每秒 2 个猫高；最后一蹿匀加速，
    在 t_e 时尾巴也过了墙的内边线。"""
    g = cat_geom()
    t_m, t_f0, t_f1, t_c, t_e = cat_timeline()
    unit = g["unit"]
    u0 = g["u0"]
    if t <= t_c:
        return u0
    t_w = t_c + 2 / CAT_FPS
    v_walk = 2.0 * unit
    if t <= t_w:
        return u0 + 0.6 * v_walk * (t - t_c)
    u_w = u0 + 0.6 * v_walk * (t_w - t_c)
    t_r = t_c + 6 / CAT_FPS
    if t <= t_r:
        return u_w + v_walk * (t - t_w)
    u_r = u_w + v_walk * (t_r - t_w)
    u_end = g["u_wall"] + 1.05 * unit
    T_ = t_e - t_r
    acc = max(2 * ((u_end - u_r) - v_walk * T_) / (T_ * T_), 0.0)
    tt = t - t_r
    return min(u_r + v_walk * tt + 0.5 * acc * tt * tt, u_end)


def _cat_uniforms(t_ink, dur, unit, gain=1.0, wipe=(0.0, 0.0)):
    return {"ink_t0": float(t_ink), "ink_dur": float(dur), "ink_age": 0.0, "ink_em": float(unit),
            "ink_bleed": float(unit * 0.012), "fibers": IK.fiber_tex(), "fib_tile": IK.FIB_TILE,
            "ink_gain": float(gain), "ink_wipe": tuple(map(float, wipe))}


def cat_items(t):
    from engine import Plane
    t_m, t_f0, t_f1, t_c, t_e = cat_timeline()
    ch, c, rot, t0, dur, k, em = mao_char()
    if t < t0 - 0.01 or t > t_e + 0.02:
        return []
    bleed = em * 0.012
    if t < t_m:
        return [IK.char_plane("貓", c, em, t0, dur, rot=rot, ppe=512, bleed=bleed)]
    items = []
    # "苗"先淡去：墨色变浅、变褐，随即褪尽
    a_m = float(ease(ramp(t, t_m, t_m + 0.20)))
    if a_m < 0.999:
        p = IK.char_plane("貓", c, em, t0, dur, rot=rot, ppe=512, bleed=bleed, age=0.55 * a_m, gain=1.0 - a_m)
        p.tex = mao_part_tex("miao")
        items.append(p)
    # "豸"的墨流成伏着的猫：豸本身随墨流走而变淡
    g_z = 1.0 - float(ease(ramp(t, t_f0 + 0.06, t_f1 + 0.04)))
    if g_z > 0.001:
        p = IK.char_plane("貓", c, em, t0, dur, rot=rot, ppe=512, bleed=bleed, gain=g_z)
        p.tex = mao_part_tex("zhi")
        items.append(p)
    g = cat_geom()
    unit = g["unit"]
    r = roll_land()
    if t < t_c:
        cc, W, Hh = cat_plane_geom(cat_pos(t))
        items.append(Plane(flow_tex(), center=(cc[0], cc[1], 0.0032), size=(W, Hh), rot=(0, 0, r), blend="multiply",
                           material="a2_ink", uniforms=_cat_uniforms(t_f0, t_f1 - t_f0, unit), group="past",
                           stack="paper"))
        return items
    n = min(int((t - t_c) * CAT_FPS), len(SEQ) - 1)       # 每秒 12 张
    t_frame = t_c + n / CAT_FPS
    pos = cat_pos(t_frame)
    cc, W, Hh = cat_plane_geom(pos)
    wipe = (float((g["u_wall"] - (pos - W / 2)) / W), 2.0)   # 墙的内边线以外不画：猫从那里没进墙角
    items.append(Plane(cat_tex(SEQ[n]), center=(cc[0], cc[1], 0.0032), size=(W, Hh), rot=(0, 0, r),
                       blend="multiply", material="a2_ink", uniforms=_cat_uniforms(t_f0, 0.001, unit, wipe=wipe),
                       group="past", stack="paper"))
    return items


# ---------------------------------------------------------------- L03：显像管电视

GW = 0.32                                # 屏幕玻璃的宽（世界单位）
# 方框变成屏幕的头一段，屏幕是一个比字怀大、四边都压在"口"的墨迹笔画里的圆角矩形（半宽、半高，方框坐标）。
# 数值由"吵"的墨迹量出：字怀内边最远处约 0.195、0.106，笔画外边最近处约 0.247、0.162，取两者之间。
SCR_HALF = (0.215, 0.134)
SCR_RAD = 0.022


def tv_geom():
    def make():
        import tv as TV
        gx, gy, gw, gh = TV.glass_rect()            # 以外壳正面宽为 1，y 向下
        FW = GW / gw
        tex_h = FW * (TV.TV_H * (1 + TV.TV_BASE)) / TV.TV_W
        GH = gh * FW
        # 外壳贴图中心相对玻璃中心（方框坐标，v 向上）
        du = (0.5 - gx) * FW
        dv = -((tex_h / FW) / 2 - gy) * FW
        k = tex_h / FW                                 # 外壳贴图的高宽比
        return dict(FW=FW, tex_h=tex_h, GW=GW, GH=GH, du=du, dv=dv,
                    rv_c=(gx, gy / k), rv_h=(gw / 2, gh / 2 / k),
                    rad=TV.GLASS_R / TV.TV_W * FW, bulge=TV.GLASS_BULGE / TV.TV_W * FW)
    return cached("tv_geom", make)


T_GLASS0, T_GLASS1 = 34.10, 34.24        # 猫没入墙角以后，方框里的纸变成玻璃
T_ON0, T_ON1 = 34.14, 34.27              # 显像管预热，"重"字出现时画面亮起
T_BODY0, T_BODY1 = 34.16, 34.62          # 外壳从玻璃边缘向外长出，盖住"口"的笔画
T_SHR0, T_SHR1 = 34.42, 34.66            # 外壳盖过屏幕的边以后，屏幕在外壳下面收到玻璃的大小
T_INK0, T_INK1 = 34.58, 34.90            # 外壳盖好以后，露在外壳外面的那点墨迹笔画淡去
ROLL1 = (T(3, 0) + 0.02, T(3, 1) + 0.12)       # "重播"：画面翻滚
ROLL2 = (T(3, 2), T(3, 3) - 0.02)              # "頻繁"：再翻一次（与底鼓同时）
SNOW = (T(3, 4) - 0.01, T(3, 6) + 0.05)        # "失靈"：雪花
T_OFF = T(4, 1) + 0.03                         # "猜"之后关机
T_LINE, T_DOT = T_OFF + 0.05, T_OFF + 0.13     # 收成一条线、收成一个点
T_PHOTO0, T_PHOTO1 = T_DOT + 0.12, BAR(23)     # 亮点停一下，展开成照片，在第 23 小节首拍的底鼓上展开完


def roll_offset(t):
    """场不同步时画面的翻滚量（以画面高为单位，向上滚为正）：每次先加速、再减速锁定。"""
    off = 0.0
    for (a, b), n in ((ROLL1, 1.0), (ROLL2, 2.0)):
        u = ramp(t, a, b)
        off += n * float(u * u * (3 - 2 * u))
    return off


def crt_state(t):
    """当前显像管的各项参数。"""
    g = tv_geom()
    K, kw, kh = kou_world()
    # 屏幕形状：先是边缘压在墨迹笔画里的圆角矩形，外壳盖住以后在外壳下面收成玻璃的圆角枕形。
    # 画面（光栅）始终按玻璃的大小排布，屏幕比玻璃大的部分是没有光栅的深色玻璃
    m = float(ease(ramp(t, T_SHR0, T_SHR1)))
    w = 2 * SCR_HALF[0] + (g["GW"] - 2 * SCR_HALF[0]) * m
    h = 2 * SCR_HALF[1] + (g["GH"] - 2 * SCR_HALF[1]) * m
    rad = SCR_RAD + (g["rad"] - SCR_RAD) * m
    st = dict(w=w, h=h, rad=rad, bulge=g["bulge"] * m)
    st["glass"] = float(ease(ramp(t, T_GLASS0, T_GLASS1)))
    on = float(ease(ramp(t, T_ON0, T_ON1)))
    st["on"] = on
    r0 = roll_offset(t)
    st["roll"] = (r0, roll_offset(t - 1 / 60), roll_offset(t - 2 / 60))
    # 雪花与串台的旧字：信号断续
    sn = ramp(t, SNOW[0], SNOW[0] + 0.05) * (1 - ramp(t, SNOW[1], SNOW[1] + 0.12))
    st["snow"] = 0.95 * sn + 0.08 * ramp(t, SNOW[1], SNOW[1] + 0.12) * (1 - ramp(t, SNOW[1] + 0.12, SNOW[1] + 0.6))
    st["signal"] = 1.0 - 0.75 * sn
    st["subk"] = 1.0 - 0.15 * sn
    bursts = [(SNOW[0] + 0.05, 0.15), (SNOW[0] + 0.26, 0.17), (SNOW[0] + 0.47, 0.13), (SNOW[0] + 0.63, 0.08)]
    gh = 0.0
    for c0, d in bursts:
        gh = max(gh, float(np.clip(1 - abs(t - c0 - d / 2) / (d / 2), 0, 1)) ** 0.35)
    st["ghost"] = gh * sn
    st["hjit"] = 0.12 * sn + 0.25 * (ramp(t, ROLL2[0], ROLL2[0] + 0.05) * (1 - ramp(t, ROLL2[1], ROLL2[1] + 0.2)))
    # 关机：先竖直压成线（亮度守恒），再水平收成点，点慢慢熄灭
    vs = 1.0 - float(ramp(t, T_OFF, T_LINE)) ** 1.5 * 0.995
    hs = 1.0 - float(ease(ramp(t, T_LINE, T_DOT))) * 0.993
    st["squash"] = (vs, hs)
    off = t >= T_OFF
    st["dot"] = 0.0
    if t >= T_DOT - 0.02:
        st["dot"] = 1.2 * math.exp(-max(t - T_DOT, 0) / 0.25)
    if t >= T_DOT:
        st["on"] = 0.0
    return st


def subtitle_state(t):
    """字幕贴图：L03 按字出现，"我猜"接在后面单独一行。"""
    import tv as TV
    if t >= T(4, 0) - 0.01:
        n = 1 if t < T(4, 1) - 0.01 else 2
        return TV.subtitle_tex_text("我猜"[:n], f"wc{n}")
    n = sum(1 for i in range(11) if t >= T(3, i) - 0.01)
    if t >= T(4, 0) - 0.2:
        n = 11
    return TV.subtitle_tex(n)


def tv_items(t):
    if t < T_GLASS0 or t > T_PHOTO1 + 0.6:
        return []
    import tv as TV
    from engine import Plane, Tex
    g = tv_geom()
    st = crt_state(t)
    K = kou_world()[0]
    eu, ev = box_axes()
    r = roll_land()
    items = []
    # 外壳在纸上的影子（台灯在左上方，影子落在右下）
    body_k = float(ease(ramp(t, T_GLASS0, T_BODY1)))
    tv_fade = 1.0 - float(ease(ramp(t, T_PHOTO1 + 0.1, T_PHOTO1 + 0.45)))     # 照片盖住以后撤掉
    cb = K + eu * g["du"] + ev * g["dv"]
    if body_k > 0:
        sh = cached("tv_shadow", lambda: Tex(_soft_rect(0.08)))
        sc = cb + eu * 0.010 - ev * 0.014
        items.append(Plane(sh, center=(sc[0], sc[1], 0.0034), size=(g["FW"] * 1.06, g["tex_h"] * 1.08), rot=(0, 0, r),
                           blend="multiply", opacity=0.55 * body_k * tv_fade, color=(0.55, 0.50, 0.45), group="past",
                           stack="paper"))
    # 屏幕
    CW, CH = 0.48, 0.32
    uni = {"cloud": TV.cloud_tex(), "subs": subtitle_state(t), "oldtxt": TV.oldtext_tex(), "crt_aspect": CW / CH,
           "crt_half": (st["w"] / 2 / CW, st["h"] / 2 / CH), "crt_rad": st["rad"] / CH, "crt_bulge": st["bulge"] / CH,
           "crt_pic": (g["GW"] / 2 / CW, g["GH"] / 2 / CH),
           "crt_on": st["on"], "crt_roll": st["roll"], "crt_snow": st["snow"], "crt_ghost": st["ghost"],
           "crt_signal": st["signal"], "crt_squash": st["squash"], "crt_dot": st["dot"],
           "cloud_off": (0.004 * (t - 34.0), -0.002 * (t - 34.0)), "cloud_zoom": 1.0 + 0.01 * (t - 34.0),
           "glass_k": 0.6 + 0.4 * body_k, "crt_hjit": st["hjit"], "crt_lines": 240.0,
           "crt_subk": st["subk"]}
    items.append(Plane(None, center=(K[0], K[1], 0.0036), size=(CW, CH), rot=(0, 0, r), material="a2_crt",
                       uniforms=uni, opacity=st["glass"] * tv_fade, group="past", stack="paper"))
    # 外壳：从屏幕边缘向外显出（墨的笔画换成了外壳）
    if body_k > 0:
        tex = cached("tv_body", lambda: Tex(TV.tv_rgba()))
        items.append(Plane(tex, center=(cb[0], cb[1], 0.0038), size=(g["FW"], g["tex_h"]), rot=(0, 0, r),
                           material="a2_reveal", uniforms={"rv_p": body_reveal(t), "rv_c": g["rv_c"], "rv_h": g["rv_h"]},
                           color=(0.88, 0.86, 0.83), opacity=tv_fade, group="past", stack="paper"))
    return items


def body_reveal(t):
    """外壳揭开的范围（到玻璃边缘的盒距离，以玻璃的半宽、半高为单位）。先在玻璃出现的同时很快长到屏幕的边
    （横向约 0.34），屏幕比玻璃大的那一圈因此一直被外壳的黑色橡胶圈和面板盖着；再慢慢向外盖过"口"的笔画。"""
    gw = tv_geom()["GW"] / 2
    edge = SCR_HALF[0] / gw - 1.0 + 0.03
    return edge * float(ease(ramp(t, T_GLASS0, T_GLASS1 - 0.02))) + 0.95 * float(ease(ramp(t, T_GLASS1 - 0.02, T_BODY1)))


def _soft_rect(blur):
    n = 256
    yy, xx = np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1
    d = np.maximum(np.abs(xx) - (1 - blur * 2), 0) ** 2 + np.maximum(np.abs(yy) - (1 - blur * 2), 0) ** 2
    a = np.exp(-d / (blur * blur * 0.8))
    a = a * (np.abs(xx) < 1) * (np.abs(yy) < 1)
    return np.dstack([np.zeros((n, n, 3)), a]).astype(np.float32)


# ---------------------------------------------------------------- L04：花边照片

P_H = 0.40                                # 照片高（世界单位）
T_FLIP0, T_FLIP1 = 39.03, 39.37           # "她"：照片翻到背面
T_GLOW0 = T(4, 8) + 0.035                 # "笑"刚写完，光从字的笔画里透出来
T_BURN0, T_WHITE = 40.025, 40.09          # 光漫到画面边上以后整幅过曝；40.09 起交给 handoff.white_frame（第 2405 帧已是整帧暖白）


def photo_tex(side):
    import photo as PH
    from engine import Tex
    return cached(f"photo_{side}", lambda: Tex(PH.front() if side == "front" else PH.back()))


def photo_state(t):
    """照片的大小（0–1）、翻面角度（0 正面朝上，π 背面朝上）和显影程度。"""
    s = float(ramp(t, T_PHOTO0, T_PHOTO1))
    grow = 1 - (1 - s) ** 3
    th = math.pi * float(ease(ramp(t, T_FLIP0, T_FLIP1)))
    dev = float(ease(ramp(t, T_PHOTO0, T_PHOTO1 + 0.35)))
    return grow, th, dev


def photo_text():
    """照片上的钢笔字：正面下方白边上"沒人記得"，背面"她的笑"。返回 [(面, 字, 照片坐标中心 (x, y)，字高, 开始时刻, 时长)]，
    照片坐标以照片高为 1、原点在照片中心、y 向上。"""
    import photo as PH
    out = []
    a = look.trad(look.lyric(4)).split("　")
    first, second = a[0], a[1]                   # 我猜沒人記得 / 她的笑
    em = 0.105
    x = -PH.ASPECT / 2 + 0.07
    y = -0.5 + PH.BOTTOM * 0.48
    on = [T(4, i) for i in range(9)]
    for i, ch in enumerate(first):
        if i < 2:
            continue                             # "我猜"是关机前的最后一行字幕
        dy, rot, sc = IK.jitter(f"L04{i}{ch}")
        t0 = max(on[i] - 0.03, T_PHOTO1 - 0.08 + 0.10 * (i - 2))
        out.append(("front", ch, (x + em / 2, y + dy * em * 0.6), em * sc, t0, 0.24, rot))
        x += em * 1.02
    em2 = 0.24
    x = -em2 * 1.5
    for j, ch in enumerate(second):
        i = 6 + j
        dy, rot, sc = IK.jitter(f"L04b{i}{ch}")
        t0 = max(on[i] - (0.05 if ch == "笑" else 0.03), T_FLIP1 - 0.10)
        dur = (0.26, 0.22, 0.10)[j]                  # "笑"一笔带过，写完以后白光才从字里漫开
        out.append(("back", ch, (x + em2 / 2, 0.02 + dy * em2 * 0.4), em2 * sc, t0, dur, rot))
        x += em2 * 1.0
    return out


def photo_items(t):
    if t < T_PHOTO0:
        return []
    from engine import Plane
    import photo as PH
    grow, th, dev = photo_state(t)
    eu, ev = box_axes()
    g_tv = tv_geom()
    K0 = kou_world()[0]
    K = K0 + (eu * g_tv["du"] + ev * g_tv["dv"]) * float(ease(grow))     # 从亮点处展开，移到电视机的位置上
    r = roll_land()
    ph = P_H * max(grow, 0.002)
    pw = ph * PH.ASPECT
    cx = math.cos(th)
    items = []
    # 纸上的影子
    sh = cached("photo_shadow", lambda: __import__("engine").Tex(_soft_rect(0.05)))
    sc = K + eu * 0.008 - ev * 0.012
    items.append(Plane(sh, center=(sc[0], sc[1], 0.0040), size=(pw * max(abs(cx), 0.02) * 1.05, ph * 1.06),
                       rot=(0, 0, r), blend="multiply", opacity=0.45 * min(grow * 2, 1), color=(0.5, 0.46, 0.42),
                       group="past", stack="paper"))
    side = "front" if cx >= 0 else "back"
    # 翻面时的受光：台灯在左上方，正面先略微转向灯、再背过去变暗；背面转过来时由暗变亮
    light = 0.80 + 0.20 * math.cos(th - 0.5) if side == "front" else 0.80 + 0.20 * math.cos(th - math.pi + 0.5)
    light *= 0.70 + 0.30 * abs(cx) ** 0.5
    # 显影：刚从亮点里长出来时是一片过曝的白，随即显出影像
    expo = 1.0 + 0.9 * (1 - dev)
    col = tuple(np.array([0.95, 0.93, 0.90]) * light * expo)
    w_now = pw * max(abs(cx), 0.0015)
    items.append(Plane(photo_tex(side), center=(K[0], K[1], 0.0042), size=(w_now, ph), rot=(0, 0, r), color=col,
                       group="past", stack="paper"))
    # 纸的厚度：照片侧过来时露出的一条边
    edge = abs(math.sin(th)) * 0.0022
    if edge > 0.0002 and 0.05 < th < math.pi - 0.05:
        sgn = 1.0 if cx >= 0 else -1.0
        ec = K + eu * (sgn * w_now / 2 + sgn * edge / 2)
        items.append(Plane(None, center=(ec[0], ec[1], 0.0043), size=(edge, ph * 0.995), rot=(0, 0, r),
                           color=(0.78, 0.76, 0.70), group="past", stack="paper"))
    # 钢笔字
    for face, ch, (px, py), em, t0, dur, rot in photo_text():
        if face != side or t < t0 - 0.01:
            continue
        u = px * P_H * grow * cx if face == "front" else -px * P_H * grow * cx
        v = py * P_H * grow
        c = K + eu * u + ev * v
        items.append(IK.char_plane(ch, c, em * P_H * grow, t0, dur, rot=r + rot, ppe=512, z=0.0044,
                                   bleed=em * P_H * 0.010, sx=abs(cx), stack="paper"))
        if ch == "笑" and t >= T_GLOW0:
            items += xiao_glow(t, c, em * P_H, r + rot)
    return items


def xiao_glow_tex():
    """"笑"的光：字形覆盖率在 3 em 见方的画布中央，按两种半径模糊后相加，近处贴着笔画、远处是一团晕。"""
    def make():
        from engine import Tex
        from scipy.ndimage import gaussian_filter
        ppe = 256
        d = ST.ink_tex_data("笑", 512).astype(np.float32)[::2, ::2]
        cov = np.clip(((d[..., 0] - 2.0) / 10.0) * 512 + 0.5, 0, 1)
        n = 3 * ppe
        canvas = np.zeros((n, n), np.float32)
        h, w = cov.shape
        y0, x0 = (n - h) // 2, (n - w) // 2
        canvas[y0:y0 + h, x0:x0 + w] = cov
        g = gaussian_filter(canvas, 0.03 * ppe) * 1.2 + gaussian_filter(canvas, 0.14 * ppe) * 2.2
        g = g / g.max()
        return Tex(np.clip(g, 0, 1))
    return cached("xiao_glow", make)


def xiao_glow(t, c, em, rot):
    """白光从"笑"字向外漫开：先是贴着刚写下的笔画透出的光（薄相纸被背后的强光照透，笔画处的墨挡不住光的
    边缘），随即一圈暖白的光从字的位置向外扩大，在第 2405 帧之前漫过整幅画面。"""
    from engine import Plane
    u = ramp(t, T_GLOW0, T_WHITE - 0.015)
    k = float(u ** 1.25)
    items = []
    tex = xiao_glow_tex()
    sz = 3 * em * (1.0 + 1.5 * k)
    items.append(Plane(tex, center=(c[0], c[1], 0.0046), size=(sz, sz), rot=(0, 0, rot), blend="add",
                       color=tuple(np.array([1.0, 0.92, 0.78]) * (0.25 + 2.6 * k)), group="past", stack="paper"))
    disc = cached("glow_disc", lambda: __import__("engine").Tex(_soft_disc()))
    R = em * (0.8 + 16.0 * k ** 1.5)
    items.append(Plane(disc, center=(c[0], c[1], 0.0047), size=(2 * R, 2 * R), blend="add",
                       color=tuple(np.array([1.0, 0.95, 0.85]) * (0.35 + 2.2 * k)), group="past", stack="paper"))
    return items


def _soft_disc(n=512):
    yy, xx = np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1
    r = np.hypot(xx, yy)
    a = np.clip(1 - r, 0, 1) ** 1.6
    return a.astype(np.float32)


# ---------------------------------------------------------------- 画面

def dust_alpha(t):
    """唱到"漸漸消失"时纸上的灰尘一粒粒淡去：每粒的消失时刻按它在行上的位置从左往右推进，带一点随机。"""
    pos, size, land = HO.dust_layout()
    def make():
        rng = np.random.default_rng(5)
        x = pos[:, 0]
        u = (x - x.min()) / (x.max() - x.min())
        return T(1, 2) + 0.05 + u * (T(1, 6) - T(1, 2)) + rng.normal(0, 0.18, len(x))
    tg = cached("dust_t", make)
    return np.clip(1.0 - (t - tg) / 0.22, 0.0, 1.0)


def l01_items(t):
    if t > T_BODY1 + 0.1:
        return []
    items = []
    chars = l01_chars()
    starts = [e[3] for e in chars]
    for ch, c, rot, t0, dur, k in chars:
        if t < t0 - 0.01:
            continue
        # 每写出一个新字，前面的字就褪一分；"吵"写出后其余的字在半秒内褪尽
        n_after = sum(float(ease(ramp(t, s, s + 0.35))) for s in starts[k + 1:])
        if ch == "吵":
            age = 0.0
            gain = 1.0 - float(ease(ramp(t, T_INK0, T_INK1)))   # 外壳盖过笔画以后，"吵"的墨迹才隐去
        else:
            age = min(1.0, 0.13 * n_after + float(ease(ramp(t, starts[-1] + 0.1, starts[-1] + 0.7))))
            gain = 1.0
        if age >= 0.999 or gain <= 0.001:
            continue
        ppe = PPE_KOU if ch == "吵" else 512
        items.append(IK.char_plane(ch, c, EM1, t0, dur, age=age, rot=rot, ppe=ppe, gain=gain))
    return items


def l02_fade(t):
    """方框里的字在方框变成屏幕时隐去（被玻璃盖住）。"""
    return 1.0 - float(ease(ramp(t, T_GLASS0, T_GLASS1)))


def subframes(t):
    """正式渲染的子帧数：静处 2 个；扎进"口"的高速推进里按推进速度增加到 8 个，做出运动模糊。"""
    if T_DIVE0 - 0.1 < t < T_LAND + 0.05:
        cam = camera()
        dt = 1 / 60
        z = abs(math.log(cam.state(t + dt / 2)[2] / cam.state(t - dt / 2)[2])) / dt
        return int(min(8, 2 + round(z * 1.4)))
    return 2


def grade(t):
    g = {"past": dict(HO.GRADE_PAST["past"])}
    if t > T_BURN0:
        u = ramp(t, T_BURN0, T_WHITE - 0.012)
        g["past"]["exposure"] = 1.0 + 5.0 * u ** 1.6
        g["past"]["halation"] = 1.2 + 2.5 * u
        g["final"] = {"fade": float(u ** 2.0), "fade_color": HO.WARM_WHITE}
    return g


def frame(t):
    if t >= T_WHITE:
        return HO.white_frame(t, HO.WARM_WHITE)
    cam, H = camera()(t)
    items = HO.paper_items(t) + HO.dust_items(t, dust_alpha(t)) + l01_items(t)
    if t < T_GLASS1 + 0.05:
        for it in l02_items(t):
            it.uniforms["ink_gain"] = it.uniforms.get("ink_gain", 1.0) * l02_fade(t)
            items.append(it)
    items += cat_items(t) + tv_items(t) + photo_items(t)
    return FrameSpec(cam, items, grade=grade(t))


if __name__ == "__main__":
    # 正式渲染按 subframes(t) 取子帧数；still 只接受整数，取 2
    mode = sys.argv[1] if len(sys.argv) > 1 else "preview"
    run(frame, "A2_主歌一前半", T0, T1, OUT, subframes=subframes if mode == "final" else 2)
