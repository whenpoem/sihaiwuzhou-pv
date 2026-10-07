"""L05 后半：最右一张布烧起来，飘起的灰片聚成"灰的味道"，随后随镜头上升、散进天空。

烧的进度 burn_p(t) 是布上烧到的先后（cloth.burn_tex，0–1）随时间推进的位置，按三个字的元音起点排定：
"發酵成"三个字在布的上部被烤出来时（烤字在烧穿的前沿之前 0.36–0.50 处显出），分别正好是三个字的时刻；
烧穿从"成"之后开始，越烧越快，最后在右边夹子上留一条焦布。

灰片从烧穿的前沿上掉下来：出生时刻在烧穿的时间里均匀分布，出生位置取当时前沿上的随机一点。按出生先后，
灰片依次分给"灰""的""味""道"四个字（每字 1150 片），飞到字形里的目标点：先被热气往上托、打着旋，再收拢到
目标点，字的元音起点前后聚齐；其余的灰片只往上飘、慢慢变淡。刚掉下来的灰片边缘还红着，0.3 秒内冷成灰黑色。
灰片在空中翻转，用宽度随转角缩放来表现。字聚成后随镜头一起上升（停在画面上同一个位置），44.5 秒起一片片
脱离，往右上方散开，到 45.6 秒散尽。
"""
import math

import numpy as np
from scipy.interpolate import PchipInterpolator
from scipy.ndimage import gaussian_filter

import cloth as C
from common import L, Z_SHEET, cached
from engine import Atlas, Particles
from plan import T

BURN_KEYS = [(42.30, -0.32), (T(5, 5), -0.21), (T(5, 6), -0.05), (T(5, 7), 0.02), (43.15, 0.22), (43.40, 0.40),
             (43.60, 0.50), (43.90, 0.60), (44.30, 0.68), (46.0, 0.70)]
_BP = PchipInterpolator([k[0] for k in BURN_KEYS], [k[1] for k in BURN_KEYS])
T_BURN0 = 42.87                     # 烧穿开始（burn_p 过 0）
T_BURN1 = 44.25


def burn_p(t):
    if t < BURN_KEYS[0][0]:
        return -0.5 if t < 42.0 else -0.32 - 0.2 * (BURN_KEYS[0][0] - t)
    return float(_BP(min(t, BURN_KEYS[-1][0])))


ASH_TEXT = "灰的味道"
ASH_T = [T(5, 8), T(5, 9), T(5, 10), T(5, 11)]
ASH_H = 1.25                        # 字高（世界单位，z = 24 那一层）
ASH_X = [2.55, 3.90, 5.25, 6.60]    # 四个字的中心 x
ASH_Y = 4.72                        # 字的中心 y（镜头开始上升之前）
PER_CHAR = 1150
N_FREE = 1800
T_RISE = 43.45                      # 镜头开始上升：此后字随镜头升起
T_SCATTER = 44.45


def atlas():
    """灰片图集：4×4 格，每格一片不规则、卷边的灰片，中间深、卷起的边缘浅（白色，按粒子颜色着色）。"""
    def make():
        cell, n = 64, 4
        rng = np.random.default_rng(5)
        out = np.zeros((cell * n, cell * n, 4), np.float32)
        yy, xx = np.mgrid[0:cell, 0:cell] / (cell - 1) * 2 - 1
        ang = np.arctan2(yy, xx)
        rr = np.hypot(xx, yy)
        rects = {}
        for k in range(n * n):
            # 半径随角度起伏的多边形，再加细碎的缺口
            m = 0.55 + 0.25 * rng.uniform(0.3, 1.0)
            prof = np.ones_like(ang) * m
            for f in range(2, 7):
                prof += rng.normal(0, 0.10 / f ** 0.6) * np.cos(f * ang + rng.uniform(0, 6.28))
            sx, sy = rng.uniform(0.55, 1.0), rng.uniform(0.75, 1.0)
            r2 = np.hypot(xx / sx, yy / sy)
            nz = gaussian_filter(rng.normal(0, 1, rr.shape), 1.5)
            a = np.clip((prof - r2 + 0.06 * nz) / 0.08, 0, 1)
            edge = np.clip(1 - (prof - r2) / 0.22, 0, 1) * a
            shade = 0.55 + 0.25 * nz / (np.abs(nz).max() + 1e-6)
            v = np.clip(shade * (1 - edge) + 1.25 * edge, 0, 1.4)
            i, j = k // n, k % n
            out[i * cell:(i + 1) * cell, j * cell:(j + 1) * cell] = np.dstack([v, v, v, a])
            rects[k] = (j / n, i / n, (j + 1) / n, (i + 1) / n)
        return Atlas(out, rects, list(range(n * n)))
    return cached("ash_atlas", make)


def _glyph_points(ch, n, rng):
    g = L.glyph_mask(ch, "serif", 700, 256, pad=0.04)
    ys, xs = np.nonzero(g > 0.5)
    idx = rng.choice(len(ys), n, replace=len(ys) < n)
    # 字形方格的 0–1 坐标 → 相对字心的世界坐标（字高 ASH_H）
    px = (xs[idx] + rng.uniform(0, 1, n)) / 256 - 0.5
    py = 0.5 - (ys[idx] + rng.uniform(0, 1, n)) / 256
    return np.c_[px, py] * ASH_H / (1 - 2 * 0.04)


def flakes():
    """预先排好每片灰的全部参数。"""
    def make():
        rng = np.random.default_rng(77)
        n_char = PER_CHAR * len(ASH_TEXT)
        N = n_char + N_FREE
        tb = np.sort(rng.uniform(T_BURN0, T_BURN1, N))
        # 出生位置：当时烧穿前沿上的随机一点（在布的 0–1 坐标里拒绝采样）
        x0, ytop, w, h = C.sheet_geom(C.N - 1)
        cand_u = rng.uniform(0, 1, 60000)
        cand_v = rng.uniform(0, 1, 60000)
        cand_d = C.burn_d(cand_u, cand_v)
        origin = np.zeros((N, 2))
        for i in range(N):
            p = burn_p(tb[i])
            ok = np.flatnonzero(np.abs(cand_d - p) < 0.012)
            j = ok[rng.integers(len(ok))] if len(ok) else rng.integers(len(cand_d))
            origin[i] = (x0 + cand_u[j] * w, ytop - cand_v[j] * h)
        # 按出生先后分给四个字
        char = np.full(N, -1)
        target = np.zeros((N, 2))
        arrive = np.zeros(N)
        counts = [0] * len(ASH_TEXT)
        pts = [_glyph_points(ch, PER_CHAR, rng) for ch in ASH_TEXT]
        free_mask = rng.uniform(0, 1, N) < N_FREE / N * 0.6       # 一部分灰片从一开始就只往上飘
        for i in range(N):
            if free_mask[i]:
                continue
            for c in range(len(ASH_TEXT)):
                if counts[c] < PER_CHAR and ASH_T[c] + 0.35 >= tb[i] + 0.25:
                    char[i] = c
                    target[i] = np.array([ASH_X[c], ASH_Y]) + pts[c][counts[c]]
                    arrive[i] = max(tb[i] + 0.28 + rng.uniform(0, 0.18), ASH_T[c] - 0.12 + rng.uniform(0, 0.28))
                    counts[c] += 1
                    break
        P = dict(tb=tb, origin=origin, char=char, target=target, arrive=arrive,
                 size=rng.lognormal(np.log(0.050), 0.30, N).clip(0.024, 0.10),
                 aspect=rng.uniform(0.55, 1.0, N),
                 spin0=rng.uniform(0, 6.28, N), spin_w=rng.uniform(2.0, 7.0, N) * rng.choice([-1, 1], N),
                 tumble_w=rng.uniform(1.5, 5.0, N),
                 sw_a=rng.uniform(0.10, 0.35, N), sw_w=rng.uniform(2.0, 5.0, N), sw_p=rng.uniform(0, 6.28, N),
                 rise=rng.uniform(1.4, 2.6, N), wind=rng.uniform(0.3, 1.1, N), life=rng.uniform(1.0, 2.0, N),
                 tone=rng.uniform(0.035, 0.11, N), uvk=rng.integers(0, 16, N),
                 scat=T_SCATTER + rng.uniform(0, 0.75, N) + 0.10 * np.maximum(char, 0),
                 jit=rng.uniform(0, 6.28, (N, 2)))
        return P
    return cached("flakes", make)


def lift(t, cam_y):
    """字随镜头上升的量：镜头开始上升后，字的 y 跟着镜头中心一起往上。"""
    return cam_y(t) - cam_y(T_RISE) if t > T_RISE else 0.0


def items(t, cam_y):
    if t < T_BURN0 or t > 45.8:
        return []
    P = flakes()
    tb = P["tb"]
    on = tb <= t
    if not on.any():
        return []
    idx = np.flatnonzero(on)
    a = t - tb[idx]
    o = P["origin"][idx]
    ch = P["char"][idx]
    tg = P["target"][idx]
    ar = P["arrive"][idx]
    sw = P["sw_a"][idx][:, None] * np.c_[np.sin(P["sw_w"][idx] * a + P["sw_p"][idx]),
                                          0.6 * np.cos(P["sw_w"][idx] * 0.8 * a + P["sw_p"][idx] * 1.3)]
    ly = lift(t, cam_y)
    # 只往上飘的灰片：热气托着上升，被风带向右边
    free = o + np.c_[P["wind"][idx] * a, P["rise"][idx] * a - 0.15 * a * a] + sw * np.minimum(a / 0.4, 1)[:, None]
    pos = free.copy()
    alpha = np.clip(1 - a / P["life"][idx], 0, 1) ** 0.7
    # 分给字的灰片：从出生到聚齐，先跟着热气走，再收拢到目标点
    c = ch >= 0
    if c.any():
        s = np.clip((t - tb[idx][c]) / np.maximum(ar[c] - tb[idx][c], 1e-3), 0, 1)
        e = s * s * (3 - 2 * s)
        e2 = e ** 1.6
        tgt = tg[c] + np.array([0.0, ly])
        # 到了以后在原处轻轻扑动
        jit = 0.012 * np.c_[np.sin(3.1 * t + P["jit"][idx][c, 0]), np.cos(2.7 * t + P["jit"][idx][c, 1])]
        path = free[c] * (1 - e2)[:, None] + (tgt + jit) * e2[:, None]
        # 散开：44.45 秒起一片片脱离，往右上方飘走
        sc = P["scat"][idx][c]
        u = np.clip(t - sc, 0, None)
        drift = np.c_[0.9 * u + 0.6 * u * u, 1.2 * u + 0.9 * u * u] + sw[c] * np.minimum(u / 0.3, 1)[:, None]
        pos[c] = path + drift
        alpha[c] = np.clip(1 - u / 0.9, 0, 1)
    keep = alpha > 0.01
    if not keep.any():
        return []
    idx, a, pos, alpha = idx[keep], a[keep], pos[keep], alpha[keep]
    n = len(idx)
    # 翻转：宽度随转角缩放
    tum = np.abs(np.cos(P["tumble_w"][idx] * (t - tb[idx]) + P["spin0"][idx]))
    size = P["size"][idx]
    sz = np.c_[size * (0.25 + 0.75 * tum), size * P["aspect"][idx]]
    rot = P["spin0"][idx] + P["spin_w"][idx] * 0.15 * (t - tb[idx])
    # 颜色：刚掉下来时边缘还红着，随后冷成灰黑
    heat = np.exp(-a / 0.12)
    tone = P["tone"][idx]
    col = np.c_[tone + 2.2 * heat, tone * 0.92 + 0.75 * heat, tone * 0.85 + 0.18 * heat, alpha]
    xyz = np.c_[pos, np.full(n, Z_SHEET + 0.05)]
    at = atlas()
    return [Particles(at, xyz, sz.astype(np.float32), rot.astype(np.float32), col.astype(np.float32),
                      at.index_uv(P["uvk"][idx]), blend="over", group="past", stack="ash")]
