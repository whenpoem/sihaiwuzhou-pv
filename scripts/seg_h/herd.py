"""旋风与兽群："吹"之后一直裹着镜头的那股旋风，以及"动物永不停下来"时成群奔涌、冲向阳光的板与字。

旋风是一条绕着镜头前进方向的隧道：几千块板和字分布在离镜头轴 1.5–11 单位的圆柱面附近，绕轴旋转，并以比
镜头更快的速度迎面而来。离得远时它们挤在画面中心附近、很小；越近越大，同时向画面四周散开，旋转着从镜头
两侧掠过，掠过之后回到远处（相对深度循环），所以几千块就能填满整段路程。每一层碎开以前，层后面的部分
看不见，所以只画镜头与下一层之间的那一段。板的颜色取翻板场的三种漆色，亮度随翻滚的朝向变化，并带上前方
那一层的光色（锁孔的青、报纸海的暮光、标语墙的灰蓝、被单的暖白、城市的冷光）。

"动物永不停下来"时（第五层碎开以后），隧道里的东西不再迎面而来，而是从镜头身后追上来、超过镜头，分成十几群
沿螺旋线一路奔向远处中心的那团光，每群有自己的起伏；那团光越来越大、越来越亮，"浮"字时整幅画面过曝。
"""
import math

import numpy as np

from common import T, cached, smooth, look, RED, YELLOW, WARM, rot_axes
from engine import Particles, Plane, Tex, glyph_atlas
import cards as CD
import field as FD
import storm as ST

N_CARD, N_GLYPH = 1700, 450
D_MAX = 95.0
T_HERD = ST.KUAI[4] + 0.06                      # 第五层碎开：旋风变成兽群
T_SUN = T(38, 0)
K = 1.866
# 前方那一层的光色（旋风里的板带上这种颜色）
LAYER_TINT = [(0.55, 0.75, 0.85), (1.0, 0.72, 0.48), (0.68, 0.74, 0.85), (1.05, 0.95, 0.80), (0.62, 0.70, 0.95)]
HERD_TINT = (1.05, 0.82, 0.55)

OLD_CHARS = look.trad("千万不要忘记阶级斗争团结紧张严肃活泼四海翻腾云水怒五洲震荡风雷激一万年太久只争朝夕"
                      "抓革命促生产形势大好不是小好东方红太阳升备战备荒为人民全国山河一片红换了人间")
LYRIC_CHARS = look.trad("街道的吵角落里的猫天气预报她的笑阳光和衬布白云骑士锈迹的刀谁的腰迷失的深夜褪色的口号"
                        "先别松开她的手克里姆林宫的花跳进池底吧摔碎进沟里单车没回来善变的世界拼完一半希望风帆"
                        "锁孔的空浸没的晨钟风筝线染红回到从前")


def layout():
    def make():
        rng = np.random.default_rng(3737)
        n = N_CARD + N_GLYPH
        f = {}
        f["r"] = 1.5 + rng.gamma(2.2, 2.0, n).clip(0, 9.5)
        f["phi0"] = rng.uniform(0, 2 * np.pi, n)
        f["w"] = rng.uniform(1.6, 3.2, n) * (4.0 / (f["r"] + 2.0))      # 靠轴越近转得越快
        f["d0"] = rng.uniform(0, D_MAX, n)
        f["v"] = rng.uniform(140.0, 230.0, n)                              # 相对镜头迎面而来的速度
        f["spin"] = rng.normal(0, 6.0, (n, 3))
        f["a0"] = rng.uniform(0, 2 * np.pi, (n, 3))
        f["flock"] = rng.integers(0, 7, n)
        f["fo"] = rng.normal(0, 1, (n, 3))
        f["col"] = rng.choice(3, n, p=[0.25, 0.5, 0.25])
        f["var"] = rng.integers(0, CD.N_VAR, n)
        f["size"] = rng.uniform(0.85, 1.15, n)
        g = rng.random(N_GLYPH) < 0.6
        f["g_old"] = g
        f["g_char"] = np.where(g, rng.integers(0, len(OLD_CHARS), N_GLYPH), rng.integers(0, len(LYRIC_CHARS), N_GLYPH))
        return f
    return cached("vortex_layout", make)


def atlases():
    def make():
        old = glyph_atlas(OLD_CHARS, kind="sans", weight=850, cell=96)
        lyr = glyph_atlas(LYRIC_CHARS, kind="serif", weight=700, cell=96)
        return old, lyr
    return cached("vortex_atlas", make)


def _next_layer(t):
    """镜头前方还没碎开的那一层的序号；全部碎开后为 5。"""
    for i in range(5):
        if t < ST.KUAI[i] + 0.04:
            return i
    return 5


def tint_at(t):
    i = _next_layer(t)
    if i >= 5:
        k = float(smooth(t, T_HERD, T_HERD + 0.6))
        return np.array(LAYER_TINT[4]) * (1 - k) + np.array(HERD_TINT) * k
    return np.array(LAYER_TINT[i])


def items(t, cam_state_fn):
    """旋风（177.6 起）与兽群（第五层碎开后到冲进阳光）。"""
    if t < 177.62 or t > T_SUN + 0.25:
        return []
    f = layout()
    x0, y0, H, roll = cam_state_fn(t)
    zc = H * K
    n = N_CARD + N_GLYPH
    # 起势：旋风在"吹"之后 0.3 秒里卷起来；冲进阳光的一刻散成光里的尘埃（由 sun.py 接着画）
    grow = float(smooth(t, 177.62, 178.05))
    end = 1.0 - float(smooth(t, T_SUN - 0.05, T_SUN + 0.2))
    herd = float(smooth(t, T_HERD - 0.05, T_HERD + 0.45))
    tt = t - 177.6
    # 相对深度：旋风里迎面而来（d 减小）；兽群里从身后追上来、奔向远处（d 增大）
    v_eff = f["v"] * (1.0 - 2.1 * herd)
    # 用积分后的位移：兽群开始以后速度翻转，位移 = v·(t_h − t0) + v_h·(t − t_h)
    th = T_HERD - 177.6
    disp = np.where(tt < th, f["v"] * tt, f["v"] * th - f["v"] * 1.1 * (tt - th) * smooth(t, T_HERD, T_HERD + 0.45))
    d = np.mod(f["d0"] - disp, D_MAX) + 0.3
    # 兽群：按群聚拢，每群绕轴的角度和半径各自起伏
    phi = f["phi0"] + f["w"] * tt
    r = f["r"].copy()
    if herd > 0:
        fl = f["flock"]
        fphi = fl * (2 * np.pi / 7) + 1.2 * tt + 0.45 * np.sin(tt * 2.3 + fl)
        frad = 3.6 + 1.8 * np.sin(tt * 3.1 + fl * 1.7 + d * 0.08) + 0.05 * d
        phi = phi * (1 - herd) + (fphi + 0.09 * f["fo"][:, 0] + d * 0.045) * herd
        r = r * (1 - herd) + (frad + 0.45 * f["fo"][:, 1]) * herd
    # 只画镜头与下一层之间的部分
    i = _next_layer(t)
    if i < 5:
        lim = zc - ST.LAYER_Z[i] - 0.5
        vis = d < lim
    else:
        vis = d < D_MAX
    vis &= d > 0.35
    # 画面中心留给前方的层（兽群时留给远处那团光）：只画离画面中心 0.5 个半画面高以外的东西；
    # 贴着镜头、大到超过画面三分之一的板淡掉，不把画面糊满
    srad = r / (d * 0.268)
    psize = f["size"] / (d * 0.536)
    vis &= srad > 0.55
    wx = x0 + r * np.cos(phi)
    wy = y0 + r * np.sin(phi)
    wz = zc - d
    ang = (f["a0"] + f["spin"] * tt).astype(np.float32)
    # 亮度：翻滚时朝向变化，正对镜头时最亮；远处略暗（空气）
    tint = tint_at(t)
    alpha = grow * end * np.clip((D_MAX - d) / 15.0, 0, 1) * smooth(srad, 0.55, 0.9) *         (1.0 - smooth(psize, 0.22, 0.45))
    out = []
    sel_c = np.flatnonzero(vis[:N_CARD])
    if len(sel_c):
        R = rot_axes(ang[sel_c, 0], ang[sel_c, 1], ang[sel_c, 2])
        nz = np.abs(R[:, 2, 2])
        b = (0.30 + 0.70 * nz ** 0.7) * (0.55 + 0.45 * np.exp(-d[sel_c] / 60.0))
        pal = FD.PALETTE[f["col"][sel_c]]
        light = 0.55 + 0.45 * tint[None]
        col = pal * b[:, None] * light * 1.3
        under = FD.PALETTE[(f["col"][sel_c] + 1) % 3] * b[:, None] * light * 1.15
        a = alpha[sel_c]
        at = CD.atlas()
        out.append(Particles(at, np.c_[wx[sel_c], wy[sel_c], wz[sel_c]].astype(np.float32),
                             (f["size"][sel_c] * (0.97 - 0.3 * herd)).astype(np.float32), ang[sel_c],
                             color=np.c_[col, a].astype(np.float32), back=np.c_[under, a].astype(np.float32),
                             uv=at.index_uv(f["var"][sel_c]), group="past", bias=-20.0))
    gi = np.flatnonzero(vis[N_CARD:])
    if len(gi):
        old, lyr = atlases()
        j = N_CARD + gi
        go = f["g_old"][gi]
        for atl, m, chars, colr in ((old, go, OLD_CHARS, None), (lyr, ~go, LYRIC_CHARS, WARM)):
            if not m.any():
                continue
            jj = j[m]
            ch = f["g_char"][gi[m]]
            if colr is None:
                base = np.where((ch % 3 == 0)[:, None], YELLOW[None] * 1.05, RED[None] * 1.15)
            else:
                base = np.broadcast_to(np.array(colr) * 1.1, (len(jj), 3))
            b = 0.55 + 0.45 * np.exp(-d[jj] / 60.0)
            col = base * b[:, None] * (0.6 + 0.4 * tint[None]) * (0.75 if colr is not None else 1.0)
            # 字始终大致朝着镜头，只带一点翻转，远看认得出是字
            a3 = ang[jj] * np.array([0.25, 0.25, 1.0], np.float32)
            out.append(Particles(atl, np.c_[wx[jj], wy[jj], wz[jj]].astype(np.float32),
                                 (f["size"][jj] * 1.3).astype(np.float32), a3,
                                 color=np.c_[col, alpha[jj]].astype(np.float32), uv=atl.index_uv(ch),
                                 group="past", bias=-20.0))
    out += glow_items(t, cam_state_fn)
    return out


def _soft(n, p):
    yy, xx = np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1
    a = np.clip(1 - np.hypot(xx, yy), 0, 1) ** p
    return np.dstack([np.ones((n, n, 3), np.float32), a.astype(np.float32)])


def glow_items(t, cam_state_fn):
    """远处中心的那团光（正午的太阳，镜头冲向它）：第五层碎开后出现在画面中心，越来越大、越来越亮。
    背后是远处的树冠（sun.background），先很暗，随太阳一起亮起来。"""
    if t < ST.KUAI[4] - 0.02:
        return []
    x0, y0, H, roll = cam_state_fn(t)
    tex = cached("herd_glow", lambda: Tex(_soft(512, 1.4)))
    core = cached("herd_core", lambda: Tex(_soft(256, 3.0)))
    k = float(smooth(t, ST.KUAI[4] - 0.02, ST.KUAI[4] + 0.4))
    ramp = float(smooth(t, T_HERD, T_SUN)) ** 1.6
    items = [Plane(tex, center=(x0, y0, -1.0), size=(44.0, 44.0), blend="add",
                   color=tuple(np.array([1.0, 0.70, 0.40]) * (0.25 + 1.6 * ramp) * k), group="past", bias=150.0),
             Plane(core, center=(x0, y0, -0.5), size=(12.0, 12.0), blend="add",
                   color=tuple(np.array([1.2, 1.0, 0.8]) * (0.6 + 3.5 * ramp) * k), group="past", bias=140.0)]
    return items
