"""L38–L39：冲出最后一层以后的正午阳光、阳光里的尘埃，以及尘埃拼成"永遠愛她"。

阳光。镜头冲出城市那一层，正对着太阳：画面在"浮"字时过曝成一片暖金色，速度骤然放慢。太阳在一片树冠后面，
树冠用一张从树下仰拍的照片（Baoothersks，CC BY 4.0，Wikimedia Commons）做底：去掉右缘的路灯，叶子按亮度
映射到琥珀与暗褐，天空的空隙按日光金提到高于 1 的亮度；整张图按镜头的焦外成像做圆盘卷积，叶缝里的天光因此
变成一个个圆形的光斑，太阳本身是一团过曝的光。太阳射出的光束（空气里的灰尘把光散射出来）由天空的空隙沿着
指向太阳的方向做径向累积得到，加在树冠前面。树冠在很远处（z = −300），镜头前进时它几乎不变大，像真的天空。
冲出来的头两秒镜头正对太阳，随后视线缓缓压低，太阳移到画面左上角，画面中部留给尘埃和字。

尘埃。旋风里的一切变成阳光里漂浮的尘埃：几千粒很小的灰尘，加上四百来片从前面各段的字上掉下来的碎片
（褪色红的旧字碎片、墨褐和暖白的歌词碎片）。镜头对焦在前方 6 个单位处，离焦平面越远的东西越虚：按薄透镜算
弥散圆直径 A·|D − Df| / Df，碎片小于弥散圆时画成圆形光斑（总亮度不变，所以越虚越淡），接近焦平面时才看出
是一片片有形状的碎片。灰尘的亮度按前向散射计算：越接近太阳的方向越亮，所以逆光里的灰尘闪闪发亮。

一颗尘埃。"当一颗"时，其中一片暗红的碎片从焦外飘进焦平面，停在画面右上方；"躁"时它不安地抖动、乱转，
"郁"时忽然停住，"尘"时转过一个角度、迎着太阳闪一下。这片碎片就是"永"字上面那一点。

拼字（L39）。"又"时碎片从四处聚向焦平面，"脏"时拼成一团：两处是乱涂的线团，两处是翻过来露出黑色背面、
挤成一块的方块（涂黑的脏话）。"拼"时它们散开、在四个字的位置周围打转，"永遠愛她"四个字在各自的元音起点
依次拼成，每个字由几十片碎片拼合，碎片之间留着细缝，颜色各不相同；那颗尘埃在"永"时落成上面的一点。
四个字下面随后闪过一行褪色红的旧句式"永遠忠於"，后面是一段空着的横线。

碎片的形状：把"永遠愛她"四个字（思源宋体粗字重，繁体）的字形按连通区域拆开，大的区域再用沃罗诺伊分区切成
几十块，块与块之间腐蚀出 2 像素的缝；小的区域（点、短撇）保持完整。填充用的碎片从其他旧字和歌词的字形上
同样切下。
"""
import math

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, map_coordinates

from common import CACHE, IMG, T, cached, disk_cached, key_of, look, smooth, smoother, RED, YELLOW, WARM, INK, SUN, \
    rot_axes, euler_from_matrix, facing_rot
from engine import Particles, Plane, Tex, TextPlane, Overlay
from engine.text import Atlas

T_SUN = T(38, 0)
T_DANG, T_YI, T_KE = T(38, 5), T(38, 6), T(38, 7)
T_ZAO, T_YU, T_CHEN = T(38, 8), T(38, 9), T(38, 11)
L39 = [T(39, i) for i in range(13)]       # 又 從 髒 話 中 拼 湊 一 段 永 遠 愛 她
T_YOU, T_ZANG, T_PIN = L39[0], L39[2], L39[5]
T_HOME = L39[9:13]
T_DIM = 188.45                             # 阳光开始暗下去

K = 1.866
DF = 6.0                                   # 焦距（镜头到焦平面的距离）
APERTURE = 0.40
EM = 0.80                                  # "永遠愛她"的字号（焦平面上的世界长度，约 270 像素）
PITCH = 1.10                               # 字距（em）
MOSAIC_C = (0.0, 0.42)                     # 四个字的中心（画面比例：x 相对中心，y 从上往下）
CANOPY_Z = -300.0
CANOPY_W = 900.0
SUN_UV = (0.57, 0.48)

TEXT = look.trad("永远爱她")
FILLER_SRC = [("sans", 900, look.trad("鬥爭萬歲紅忠於")), ("serif", 800, look.trad("陽光被單猫刀腰夜")),
              ("fang", 400, look.trad("風雷激怒雲水"))]


# ---------------------------------------------------------------- 树冠与光束

def _disc_kernel(r):
    n = int(math.ceil(r)) * 2 + 3
    yy, xx = np.mgrid[0:n, 0:n] - (n - 1) / 2
    d = np.hypot(xx, yy)
    k = np.clip(r + 0.5 - d, 0, 1)
    k *= 1.0 + 0.35 * np.clip((d - r * 0.7) / (r * 0.3), 0, 1)       # 光斑边缘略亮（真实镜头的焦外光斑）
    return k / k.sum()


def _canopy():
    """树冠贴图（HDR，2560×1440）。"""
    from scipy.signal import fftconvolve
    src = Image.open(IMG / "Ánh_dương_chiếu_xuyên_qua_những_kẽ_lá.jpg").convert("RGB")
    W0, H0 = src.size
    x1 = int(W0 * 0.94)                    # 去掉右缘的路灯
    h = int(x1 * 9 / 16)
    y0 = int((H0 - h) * 0.3)
    a = np.asarray(src.crop((0, y0, x1, y0 + h)).resize((2560, 1440), Image.LANCZOS), np.float32) / 255
    H, W = a.shape[:2]
    lum = a @ np.array([0.3, 0.55, 0.15], np.float32)
    sat = a.max(2) - a.min(2)
    sky = np.clip((lum - 0.6) / 0.3, 0, 1) * np.clip(1 - (sat - 0.1) / 0.25, 0, 1)
    yy, xx = np.mgrid[0:H, 0:W]
    su, sv = SUN_UV[0] * W, SUN_UV[1] * H
    r = np.hypot(xx - su, yy - sv) / H
    # 叶子：按亮度映射到暗褐—琥珀—金黄，保留一点原来的色相起伏；离太阳越近越透亮
    stops = np.array([[0.015, 0.009, 0.005], [0.07, 0.035, 0.012], [0.26, 0.14, 0.045], [0.62, 0.40, 0.14]])
    xs = np.array([0.0, 0.3, 0.6, 0.85])
    leaf = np.stack([np.interp(lum, xs, stops[:, c]) for c in range(3)], 2)
    leaf *= (1.0 + 0.25 * (a[..., 1:2] - lum[..., None]))
    leaf *= 1.0 + 1.0 * np.exp(-(r / 0.10) ** 2)[..., None]
    skyc = np.array(SUN) * (1.2 + 2.6 * np.exp(-(r / 0.13) ** 2))[..., None]
    img = leaf * (1 - sky[..., None]) + skyc * sky[..., None]
    # 焦外：圆盘卷积（叶缝里的天光变成圆形光斑）
    k = _disc_kernel(26.0)
    img = np.stack([fftconvolve(img[..., c], k, mode="same") for c in range(3)], 2)
    img = gaussian_filter(img, (1.5, 1.5, 0))
    # 太阳：过曝的一团光与一圈很宽的辉光
    img += np.array([1.0, 0.92, 0.75]) * (8.0 * np.exp(-(r / 0.025) ** 2) + 1.0 * np.exp(-(r / 0.07) ** 2)
                                           + 0.18 * np.exp(-r / 0.25))[..., None]
    return np.clip(img, 0, 60).astype(np.float16)


def _rays():
    """光束：天空的空隙沿指向太阳的方向径向累积（1280×720，单通道 0–1）。"""
    src = Image.open(IMG / "Ánh_dương_chiếu_xuyên_qua_những_kẽ_lá.jpg").convert("RGB")
    W0, H0 = src.size
    x1 = int(W0 * 0.94)
    h = int(x1 * 9 / 16)
    y0 = int((H0 - h) * 0.3)
    a = np.asarray(src.crop((0, y0, x1, y0 + h)).resize((1280, 720), Image.LANCZOS), np.float32) / 255
    lum = a @ np.array([0.3, 0.55, 0.15], np.float32)
    sat = a.max(2) - a.min(2)
    sky = np.clip((lum - 0.6) / 0.3, 0, 1) * np.clip(1 - (sat - 0.1) / 0.25, 0, 1)
    sky = gaussian_filter(sky, 1.5)
    H, W = sky.shape
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    su, sv = SUN_UV[0] * W, SUN_UV[1] * H
    acc = np.zeros_like(sky)
    wsum = 0.0
    n = 72
    for k in range(n):
        f = k / n * 0.92
        w = 0.965 ** k
        acc += w * map_coordinates(sky, [yy + (sv - yy) * f, xx + (su - xx) * f], order=1, mode="nearest")
        wsum += w
    acc /= wsum
    r = np.hypot(xx - su, yy - sv) / H
    acc *= np.exp(-r / 0.55)
    acc = np.clip((acc - 0.05) / 0.5, 0, 1) ** 1.3
    return gaussian_filter(acc, 2.0).astype(np.float32)


def canopy_tex():
    def make():
        img = disk_cached("canopy", _canopy, "v3")
        rays = disk_cached("rays", _rays, "v1")
        return Tex(img.astype(np.float32)), Tex(np.ascontiguousarray(rays)), rays
    return cached("canopy_tex", make)


def canopy_center():
    """树冠平面的中心：让 SUN_UV 落在镜头轴线的正下方（世界的 (0, 0)）。"""
    w, h = CANOPY_W, CANOPY_W * 9 / 16
    return (-(SUN_UV[0] - 0.5) * w, (SUN_UV[1] - 0.5) * h)


def sun_light(t):
    """阳光的亮度：第五层碎开后从远处亮起来，冲出时最亮；视线从太阳移开以后，眼睛渐渐适应，四周的树叶
    看上去暗下来（降到 0.62）；L40 前阳光暗下去。"""
    up = float(smooth(t, T(37, 4), T_SUN))
    adapt = 1.0 - 0.38 * float(smooth(t, T_SUN + 1.0, T_SUN + 3.6))
    down = 1.0 - float(smooth(t, T_DIM, T_DIM + 0.85))
    return (0.12 + 0.88 * up ** 1.5) * adapt * down


def background(t, roll_ref):
    """树冠与光束。roll_ref：树冠在世界里的转角（度），取镜头停住时的滚转角，所以停住后树冠是正的。"""
    k = sun_light(t)
    if k <= 0.002:
        return []
    tex, rays, _ = canopy_tex()
    cx, cy = canopy_center()
    r = math.radians(roll_ref)                 # 贴图的上方对准镜头停住时画面的上方
    c, s = math.cos(r), math.sin(r)
    wx, wy = cx * c - cy * s, cx * s + cy * c
    size = (CANOPY_W, CANOPY_W * 9 / 16)
    flick = 1.0 + 0.08 * math.sin(t * 1.7) + 0.05 * math.sin(t * 4.3 + 1.0)    # 树叶在风里动，光束时强时弱
    return [Plane(tex, center=(wx, wy, CANOPY_Z), size=size, rot=(0, 0, roll_ref), color=(k,) * 3,
                  group="past", bias=500.0),
            Plane(rays, center=(wx, wy, CANOPY_Z + 2.0), size=size, rot=(0, 0, roll_ref), blend="add",
                  color=tuple(np.array(SUN) * 0.32 * k * flick), group="past", bias=480.0)]


# ---------------------------------------------------------------- 碎片

def _cut(mask, n_target, rng, gap=2.0, small=0.05):
    """把字形遮罩切成碎片：返回 [(子遮罩, (y0, x0))]。小的连通区域保持完整，大的按沃罗诺伊分区切开。"""
    from scipy import ndimage
    from scipy.spatial import cKDTree
    lab, n = ndimage.label(mask > 0.5)
    total = (mask > 0.5).sum()
    out = []
    for k in range(1, n + 1):
        comp = lab == k
        area = comp.sum()
        if area < 40:
            continue
        ys, xs = np.nonzero(comp)
        if area < total * small:
            cells = [comp]
        else:
            m = max(2, int(round(n_target * area / total)))
            idx = rng.choice(len(ys), m, replace=False)
            sites = np.c_[ys[idx], xs[idx]].astype(float)
            # 两轮劳埃德松弛，碎片大小更均匀
            for _ in range(2):
                _, li = cKDTree(sites).query(np.c_[ys, xs])
                for j in range(m):
                    sel = li == j
                    if sel.any():
                        sites[j] = [ys[sel].mean(), xs[sel].mean()]
            jit = rng.normal(0, 2.5, (len(ys), 2))
            _, li = cKDTree(sites).query(np.c_[ys + jit[:, 0], xs + jit[:, 1]])
            cells = []
            for j in range(m):
                c = np.zeros_like(comp)
                c[ys[li == j], xs[li == j]] = True
                cells.append(c)
        for c in cells:
            if c.sum() < 12:
                continue
            er = ndimage.binary_erosion(c, iterations=int(gap)) if len(cells) > 1 else c
            if er.sum() < 8:
                continue
            sl = ndimage.find_objects(er.astype(int))[0]
            out.append((mask[sl] * er[sl], (sl[0].start, sl[1].start)))
    return out


def _glyph_mask(ch, kind, weight, px):
    import skia
    n = int(px * 1.25)
    s = skia.Surface(n, n)
    c = s.getCanvas()
    f = look.font(kind, weight, px)
    b = skia.Rect()
    f.measureText(ch, bounds=b)
    # 按表意字框排：字身 1 em 居中
    x = (n - f.measureText(ch)) / 2
    y = n / 2 + px * (0.88 - 0.5)
    c.drawString(ch, x, y, f, skia.Paint(Color=skia.ColorWHITE, AntiAlias=True))
    return s.makeImageSnapshot().toarray()[..., 3].astype(np.float32) / 255, n


CELL = 96


def _pieces():
    """碎片数据：图集（RGBA uint8）、uv、世界尺寸（em）、在字里的位置（em，相对字心，y 向下）、所属的字
    （0–3，填充碎片为 -1）、颜色类别（0 红、1 墨褐、2 暖白）、是否为"永"上面那一点。"""
    rng = np.random.default_rng(3939)
    px = 420
    items = []                              # (子遮罩, 字序, 中心 em (x, y), 尺寸 em (w, h))
    dot = None
    for ci, ch in enumerate(TEXT):
        m, n = _glyph_mask(ch, "serif", 900, px)
        cuts = _cut(m, 26, rng, gap=1.0, small=0.12)
        for sub, (y0, x0) in cuts:
            h, w = sub.shape
            cx = (x0 + w / 2 - n / 2) / px
            cy = (y0 + h / 2 - n / 2) / px
            items.append((sub, ci, (cx, cy), (w / px, h / px)))
        if ci == 0:
            # "永"上面那一点：最靠上的那块
            ks = [k for k, it in enumerate(items) if it[1] == 0]
            dot = min(ks, key=lambda k: items[k][2][1])
    n_mosaic = len(items)
    # 填充碎片
    fill = []
    for kind, wt, chars in FILLER_SRC:
        for ch in chars:
            m, n = _glyph_mask(ch, kind, wt, px)
            for sub, (y0, x0) in _cut(m, 22, rng, small=0.0):
                h, w = sub.shape
                fill.append((sub, -1, (0.0, 0.0), (w / px, h / px), kind))
    rng.shuffle(fill)
    items += [f[:4] for f in fill[:260]]
    fill_kind = [f[4] for f in fill[:260]]
    N = len(items)
    cols = int(math.ceil(math.sqrt(N)))
    rows = int(math.ceil(N / cols))
    atlas = np.zeros((rows * CELL, cols * CELL, 4), np.float32)
    rects = np.zeros((N, 4), np.float32)
    size = np.zeros((N, 2), np.float32)
    home = np.zeros((N, 2), np.float32)
    char = np.zeros(N, np.int32)
    for k, (sub, ci, c, wh) in enumerate(items):
        h, w = sub.shape
        sc = (CELL - 6) / max(h, w)
        nh, nw = max(2, int(h * sc)), max(2, int(w * sc))
        a = np.asarray(Image.fromarray((sub * 255).astype(np.uint8)).resize((nw, nh), Image.LANCZOS), np.float32) / 255
        # 纸片的质感：中间是印刷的颜色，边上一圈暗的毛边，让浅色碎片在亮的背景上也看得出形状
        from scipy.ndimage import binary_erosion
        inner = binary_erosion(a > 0.5, iterations=2)
        rim = (a > 0.5) & ~inner
        tone = 0.92 + 0.08 * gaussian_filter(rng.normal(0, 1, a.shape), 1.0)
        rgb = np.dstack([tone] * 3)
        rgb[rim] *= 0.45
        r, cc = divmod(k, cols)
        y0, x0 = r * CELL + 3, cc * CELL + 3
        atlas[y0:y0 + nh, x0:x0 + nw, :3] = rgb
        atlas[y0:y0 + nh, x0:x0 + nw, 3] = a
        rects[k] = ((x0 + 0.5) / atlas.shape[1], (y0 + 0.5) / atlas.shape[0],
                    (x0 + nw - 0.5) / atlas.shape[1], (y0 + nh - 0.5) / atlas.shape[0])
        size[k] = (nw / sc / px, nh / sc / px)
        home[k] = c
        char[k] = ci
    # 颜色：红（旧字）、墨褐与暖白（歌词）
    colc = rng.choice(3, N, p=[0.42, 0.33, 0.25])
    for j, kind in enumerate(fill_kind):
        k = n_mosaic + j
        colc[k] = 0 if kind in ("sans", "fang") else rng.choice([1, 2])
    colc[dot] = 0
    rgba = np.clip(atlas, 0, 1)
    rgba[..., :3] *= rgba[..., 3:4]                       # 预乘，缩小图里边缘不发白
    return {"atlas": (rgba * 255 + 0.5).astype(np.uint8), "rects": rects, "size": size, "home": home,
            "char": char, "col": colc, "dot": np.int32(dot), "n_mosaic": np.int32(n_mosaic)}


def pieces():
    def make():
        f = CACHE / "pieces_v4.npz"
        if f.exists():
            z = np.load(f)
            d = {k: z[k] for k in z.files}
        else:
            d = _pieces()
            np.savez_compressed(f, **d)
        n = len(d["rects"])
        at = Atlas(d["atlas"], {k: tuple(d["rects"][k]) for k in range(n)}, list(range(n)))
        at.tex = Tex(d["atlas"], premultiplied=True)          # 图集已经预乘过
        d["atlas_obj"] = at
        return d
    return cached("pieces", make)


PIECE_COL = np.array([RED * 1.15, np.array([0.50, 0.33, 0.21]), WARM * 1.05], np.float32)
PIECE_BACK = np.array([0.06, 0.05, 0.045], np.float32)


# ---------------------------------------------------------------- 尘埃与碎片的运动

N_DUST = 5200


def dust_layout(cam_rest):
    """灰尘：在镜头停住时的视锥里撒点（每粒灰尘一个世界坐标），另有一批撒在冲出来时经过的路上。"""
    def make():
        rng = np.random.default_rng(3838)
        eye, right, up, fwd = cam_rest
        n1 = int(N_DUST * 0.82)
        D = 0.8 + 70.0 * rng.random(n1) ** 1.6
        sx = rng.uniform(-0.62, 0.62, n1) * 16 / 9 * 0.268 * 2
        sy = rng.uniform(-0.6, 0.6, n1) * 0.268 * 2
        P1 = eye[None] + fwd[None] * D[:, None] + right[None] * (sx * D)[:, None] + up[None] * (sy * D)[:, None]
        n2 = N_DUST - n1
        z = rng.uniform(eye[2] + 1.0, 42.0, n2)
        rr = np.sqrt(rng.random(n2)) * (2.5 + 0.35 * (z - eye[2]))
        ph = rng.uniform(0, 2 * np.pi, n2)
        P2 = np.c_[rr * np.cos(ph), rr * np.sin(ph), z]
        P = np.r_[P1, P2].astype(np.float32)
        size = rng.lognormal(np.log(0.010), 0.5, N_DUST).clip(0.004, 0.04).astype(np.float32)
        ph3 = rng.uniform(0, 2 * np.pi, (N_DUST, 3)).astype(np.float32)
        fr = rng.uniform(0.15, 0.5, (N_DUST, 3)).astype(np.float32)
        tint = rng.choice(4, N_DUST, p=[0.70, 0.12, 0.10, 0.08])
        return P, size, ph3, fr, tint
    return cached("sun_dust", make)


DUST_TINT = np.array([[1.0, 0.92, 0.78], RED * 1.3, YELLOW * 1.2, [1.0, 0.95, 0.88]], np.float32)


def drift(P0, ph, fr, t, amp=0.25):
    """缓慢的漂浮：三个方向各一个慢正弦，再加一点上升（热空气）。"""
    tt = t - T_SUN
    return P0 + np.c_[amp * np.sin(fr[:, 0] * tt + ph[:, 0]), amp * np.sin(fr[:, 1] * tt + ph[:, 1]),
                      amp * 0.7 * np.sin(fr[:, 2] * tt + ph[:, 2])].astype(np.float32)


def scatter_light(P, eye, sun_dir, t):
    """前向散射：粒子越接近太阳的方向越亮；再乘上一层缓慢移动的光束起伏（叶缝里漏下的光柱）。"""
    v = P - eye[None]
    d = np.linalg.norm(v, axis=1) + 1e-6
    cosang = (v @ sun_dir) / d
    ang = np.arccos(np.clip(cosang, -1, 1))
    mie = 0.35 + 2.4 * np.exp(-(ang / 0.22) ** 2) + 0.6 * np.exp(-(ang / 0.6) ** 2)
    shaft = 0.75 + 0.45 * np.sin(P[:, 0] * 0.9 + P[:, 1] * 0.6 + t * 0.4) * np.sin(P[:, 1] * 1.3 - t * 0.3)
    return mie * shaft


def bokeh_atlas():
    def make():
        n = 64
        yy, xx = np.mgrid[0:n, 0:n] - (n - 1) / 2
        d = np.hypot(xx, yy) / (n / 2 - 1.5)
        a = np.clip((1.0 - d) * (n / 2) * 0.35, 0, 1)
        a *= 0.8 + 0.3 * np.clip((d - 0.6) / 0.4, 0, 1)            # 边缘略亮
        a = np.clip(a, 0, 1).astype(np.float32)
        return Atlas(a, {"b": (0, 0, 1, 1)}, ["b"])
    return cached("bokeh_atlas", make)


def _project(P, eye, right, up, fwd):
    v = P - eye[None]
    D = v @ fwd
    return v @ right, v @ up, D


def bokeh_particles(P, size, col, eye, basis, alpha=None, min_px=1.0):
    """把一组粒子按薄透镜画成焦外光斑（加亮）：直径 sqrt(s² + c²)，亮度乘 (s / 直径)²（总光量不变）。"""
    right, up, fwd = basis
    x, y, D = _project(P, eye, right, up, fwd)
    ok = (D > 0.25) & (np.abs(x) < D * 0.60 + 0.5) & (np.abs(y) < D * 0.34 + 0.5)
    coc = APERTURE * np.abs(D - DF) / DF
    eff = np.sqrt(size ** 2 + coc ** 2)
    px = eff / (D * 0.536) * 1080
    ok &= px > min_px
    if not ok.any():
        return []
    k = (size / eff) ** 2
    a = np.clip(k * 1.0, 0.012, 1.0)
    c = col * (k / a)[:, None]
    if alpha is not None:
        a = a * alpha
    c, a, P2, e2 = c[ok], a[ok], P[ok], eff[ok]
    return [Particles(bokeh_atlas(), P2.astype(np.float32), e2.astype(np.float32), None,
                      np.c_[c * a[:, None], a].astype(np.float32), blend="add", group="past", bias=-5.0)]


# ---------------------------------------------------------------- 碎片的状态

def piece_layout(cam_rest):
    """每片碎片在尘埃里的世界位置、翻滚，以及"脏话"阶段的目标（画面比例坐标与转角）。"""
    def make():
        d = pieces()
        n = len(d["rects"])
        rng = np.random.default_rng(4040)
        eye, right, up, fwd = cam_rest
        D = np.where(rng.random(n) < 0.45, rng.uniform(1.3, 3.3, n), rng.uniform(12.0, 34.0, n))
        sx = rng.uniform(-0.55, 0.55, n) * 16 / 9 * 0.536
        sy = rng.uniform(-0.45, 0.45, n) * 0.536
        P = eye[None] + fwd[None] * D[:, None] + right[None] * (sx * D)[:, None] + up[None] * (sy * D)[:, None]
        ph = rng.uniform(0, 2 * np.pi, (n, 3))
        fr = rng.uniform(0.15, 0.45, (n, 3))
        a0 = rng.uniform(-np.pi, np.pi, (n, 3))
        spin = rng.normal(0, 0.8, (n, 3))
        # "脏话"：四个字位上，0、3 号是乱涂的线团，1、2 号是翻过来的黑方块
        slot = rng.integers(0, 4, n)
        tgt = np.zeros((n, 2))
        trot = np.zeros((n, 3))
        for s in range(4):
            m = np.flatnonzero(slot == s)
            cx = (s - 1.5) * PITCH
            if s in (1, 2):
                g = int(math.ceil(math.sqrt(len(m))))
                gx, gy = np.meshgrid(np.linspace(-0.40, 0.40, g), np.linspace(-0.40, 0.40, g))
                pts = np.c_[gx.ravel(), gy.ravel()][:len(m)] + rng.normal(0, 0.04, (len(m), 2))
                tgt[m] = pts + [cx, 0.0]
                trot[m] = np.c_[rng.normal(0, 0.1, len(m)), np.pi + rng.normal(0, 0.1, len(m)),
                                rng.uniform(-np.pi, np.pi, len(m))]
            else:
                # 乱涂：来回的折线，一笔笔把字涂掉，再绕两个圈
                pts = []
                k = 7
                for j in range(k + 1):
                    yj = -0.40 + 0.80 * j / k + rng.normal(0, 0.03)
                    pts.append((-0.42 + rng.normal(0, 0.04), yj) if j % 2 == 0 else (0.42 + rng.normal(0, 0.04), yj))
                for a in np.linspace(0, 4 * np.pi, 14):
                    pts.append((0.30 * math.cos(a) + 0.05 * math.sin(3 * a), 0.25 * math.sin(a) + 0.06 * math.cos(2 * a)))
                pts = np.array(pts)
                seg = np.hypot(*np.diff(pts, axis=0).T)
                cum = np.r_[0, np.cumsum(seg)]
                u = np.sort(rng.random(len(m))) * cum[-1]
                j = np.clip(np.searchsorted(cum, u) - 1, 0, len(seg) - 1)
                f = (u - cum[j]) / np.maximum(seg[j], 1e-6)
                p = pts[j] + (pts[j + 1] - pts[j]) * f[:, None]
                d = pts[j + 1] - pts[j]
                ang = np.arctan2(d[:, 1], d[:, 0])
                tgt[m[np.argsort(rng.random(len(m)))]] = p + [cx, 0.0] + rng.normal(0, 0.012, (len(m), 2))
                trot[m] = np.c_[rng.normal(0, 0.25, len(m)), rng.normal(0, 0.25, len(m)), -ang]
        return {"P": P.astype(np.float32), "ph": ph, "fr": fr, "a0": a0, "spin": spin, "tgt": tgt, "trot": trot,
                "delay": rng.uniform(0.0, 0.18, n), "orb": rng.uniform(0.25, 0.55, n),
                "orb_w": rng.uniform(2.0, 4.0, n) * rng.choice([-1, 1], n), "orb_ph": rng.uniform(0, 2 * np.pi, n),
                "away": rng.normal(0, 1, (n, 3))}
    return cached("piece_layout", make)


def cam_point(eye, basis, X, Y, D):
    """镜头坐标（画面右、上，单位为该深度上的世界长度；D 为深度）→ 世界坐标。X、Y、D 为数组。"""
    right, up, fwd = basis
    return eye[None] + right[None] * X[:, None] + up[None] * Y[:, None] + fwd[None] * D[:, None]


def screen_xy(sx, sy, D):
    """画面比例坐标（x 相对中心、向右为正，单位为画面高；y 从上往下 0–1）→ 深度 D 处的镜头坐标。"""
    F = D * 0.5359
    return sx * F, (0.5 - sy) * F


def mosaic_home(d):
    """每片碎片在拼好的字里的镜头坐标（焦平面上）。"""
    home = d["home"]
    ci = d["char"]
    X = ((ci - 1.5) * PITCH + home[:, 0]) * EM + MOSAIC_C[0] * DF * 0.5359
    Y = (0.5 - MOSAIC_C[1]) * DF * 0.5359 - home[:, 1] * EM
    return X, Y


def mote_track(t):
    """那一颗尘埃（"永"上面的一点）的镜头坐标 (X, Y, D) 与转角（三个，弧度）、亮度倍数。"""
    # 起点：画面右上方、焦外更近处；"当一颗"时飘进焦平面
    sx0, sy0, D0 = 0.30, 0.30, 3.0
    sx1, sy1 = 0.22, 0.36
    u = float(smoother((t - (T_DANG - 0.15)) / (T_KE + 0.15 - (T_DANG - 0.15))))
    D = D0 + (DF - D0) * u
    sx = sx0 + (sx1 - sx0) * u + 0.01 * math.sin(t * 0.7)
    sy = sy0 + (sy1 - sy0) * u + 0.008 * math.sin(t * 0.9 + 1.0)
    rot = np.array([0.3 * math.sin(t * 0.5), 0.4 * math.sin(t * 0.37 + 1), 0.25 * t])
    glint = 1.0
    if t >= T_ZAO:
        # "躁"：不安地抖动乱转；"郁"：忽然停住
        z = math.exp(-(t - T_ZAO) / 0.06) if t >= T_YU else 1.0
        if t < T_YU + 0.3:
            k = (1.0 if t < T_YU else z)
            sx += k * 0.012 * (math.sin(t * 61.0) + 0.6 * math.sin(t * 97.0 + 2))
            sy += k * 0.010 * (math.sin(t * 73.0 + 1) + 0.5 * math.sin(t * 131.0))
            rot += k * np.array([0.5 * math.sin(t * 43), 0.5 * math.sin(t * 57 + 1), 0.6 * math.sin(t * 29)])
        if t >= T_YU:
            tf = min(t, T_YU + 0.3)
            rot = np.array([0.3 * math.sin(tf * 0.5), 0.4 * math.sin(tf * 0.37 + 1), 0.25 * tf])
            # 停住以后极慢地漂
            sx += 0.004 * math.sin((t - T_YU) * 0.6)
    if t >= T_CHEN - 0.05:
        # "尘"：转过一个角度迎着太阳，闪一下
        g = math.exp(-((t - T_CHEN - 0.08) / 0.12) ** 2)
        rot = rot + np.array([0.0, 0.9 * float(smooth(t, T_CHEN - 0.05, T_CHEN + 0.25)), 0.0])
        glint += 2.5 * g
    X, Y = screen_xy(sx, sy, D)
    return X, Y, D, rot, glint


def piece_items(t, eye, basis, roll_basis):
    """碎片：尘埃阶段画成焦外光斑或焦内的碎片，拼字阶段飞到目标。返回 (粒子列表, 是否已开始拼字)。"""
    d = pieces()
    L = piece_layout(roll_basis)
    n = len(d["rects"])
    right, up, fwd = basis
    nm = int(d["n_mosaic"])
    dot = int(d["dot"])
    # 尘埃阶段的位置（世界）→ 镜头坐标
    Pw = drift(L["P"], L["ph"], L["fr"], t, amp=0.18)
    v = Pw - eye[None]
    X0, Y0, D0 = v @ right, v @ up, v @ fwd
    tt = t - T_SUN
    rot0 = L["a0"] + L["spin"] * tt
    # "脏话"阶段的目标（焦平面上的镜头坐标）
    scale = EM
    XB = L["tgt"][:, 0] * scale + MOSAIC_C[0] * DF * 0.5359
    YB = (0.5 - MOSAIC_C[1]) * DF * 0.5359 - L["tgt"][:, 1] * scale
    XH, YH = mosaic_home(d)
    # 权重
    tA = T_YOU + 0.05 + L["delay"]
    wB = smoother((t - tA) / (T_ZANG - tA))
    wC = np.full(n, float(smoother((t - T_PIN) / 0.35)))
    is_m = d["char"] >= 0
    t_home = np.where(is_m, np.take(T_HOME, np.clip(d["char"], 0, 3)), 0.0)
    wD = np.where(is_m, smoother((t - (t_home - 0.32 - 0.1 * L["delay"])) / (0.32 + 0.1 * L["delay"])), 0.0)
    wE = np.where(~is_m, smoother((t - 186.62 - L["delay"]) / 0.55), 0.0)
    # 打转：围着各自的字位绕圈
    cslot = np.where(is_m, d["char"], np.arange(n) % 4)
    ang = L["orb_ph"] + L["orb_w"] * (t - T_PIN)
    XC = ((cslot - 1.5) * PITCH) * EM + L["orb"] * EM * np.cos(ang) + MOSAIC_C[0] * DF * 0.5359
    YC = (0.5 - MOSAIC_C[1]) * DF * 0.5359 + L["orb"] * EM * 0.8 * np.sin(ang)
    # 散开回到尘埃里（填充碎片）
    near_ = L["away"][:, 2] < 0
    DE = np.where(near_, 1.6 + 0.6 * np.abs(L["away"][:, 2]), 18.0 + 8.0 * np.abs(L["away"][:, 2]))
    # 飞近镜头的那一半从字的两侧散开，不挡住正在拼的字
    side = np.sign(L["away"][:, 0]) + (L["away"][:, 0] == 0)
    XE = np.where(near_, (side * (0.55 + 0.25 * np.abs(L["away"][:, 1])) * 0.9525 / 2 * 1.0), 
                  XC / DF + L["away"][:, 0] * 0.35) * DE
    YE = (np.where(near_, L["away"][:, 1] * 0.18, YC / DF + L["away"][:, 1] * 0.25)) * DE
    # 依次混合
    X = X0 + (XB - X0) * wB
    Y = Y0 + (YB - Y0) * wB
    D = D0 + (DF - D0) * wB
    X = X + (XC - X) * wC
    Y = Y + (YC - Y) * wC
    X = X + (XH - X) * wD + (XE - X) * wE
    Y = Y + (YH - Y) * wD + (YE - Y) * wE
    D = D + (DF - D) * wD + (DE - D) * wE
    # 转角：从开始移动那一刻的翻滚角度出发，逐段混合到目标（避免角度回绕造成跳变）
    r_start = L["a0"] + L["spin"] * np.clip(tA - T_SUN, 0, None)[:, None]
    r_start = (r_start + np.pi) % (2 * np.pi) - np.pi
    rot = np.where((wB > 0)[:, None], r_start, rot0)
    rot = rot + (L["trot"] - rot) * wB[:, None]
    swirl = np.c_[0.5 * np.sin(ang * 0.7), 0.6 * np.sin(ang * 0.5 + 1.0), ang * 0.3]
    rot = rot + (swirl - rot) * wC[:, None]
    rot = rot * (1 - wD)[:, None]
    # 那一颗尘埃
    mX, mY, mD, mrot, glint = mote_track(t)
    if t < T_HOME[0] - 0.4:
        X[dot], Y[dot], D[dot] = mX, mY, mD
        rot[dot] = mrot
    else:
        w = float(smoother((t - (T_HOME[0] - 0.4)) / 0.4))
        X[dot] = mX + (XH[dot] - mX) * w
        Y[dot] = mY + (YH[dot] - mY) * w
        D[dot] = mD + (DF - mD) * w
        rot[dot] = mrot * (1 - w)
    # 世界坐标与朝向
    P = cam_point(eye, basis, X, Y, D)
    Rc = np.stack([right, up, -fwd], 1)                                      # 列：右、上、朝镜头
    Rl = rot_axes(rot[:, 1], rot[:, 0], rot[:, 2])
    R = np.einsum("ij,njk->nik", Rc.astype(np.float32), Rl)
    eul = euler_from_matrix(R)
    size = d["size"] * EM
    col = PIECE_COL[d["col"]]
    # 亮度：逆光里的纸片，正对镜头时被天空照亮一些，翻到侧面时边缘发亮
    nz = np.abs(Rl[:, 2, 2])
    light = sun_light(t)
    lit = (0.55 + 0.45 * nz) * (0.75 + 0.25 * light)
    lit[dot] *= glint
    # 远离焦平面时画成光斑，靠近时画成碎片
    coc = APERTURE * np.abs(D - DF) / DF
    s_eff = np.maximum(size[:, 0], size[:, 1])
    sharp = np.clip(1.0 - (coc / np.maximum(s_eff, 1e-4) - 0.2) / 0.3, 0, 1)
    vis = (D > 0.3)
    fade_far = np.clip(1.0 - (D - 30.0) / 10.0, 0, 1) * (1.0 - float(smooth(t, T_DIM + 0.05, T_DIM + 0.6)))
    out = []
    si = np.flatnonzero(vis & (sharp > 0.01))
    if len(si):
        a = (sharp * fade_far)[si]
        # 逆光：纸片的轮廓被身后的阳光勾出一圈亮边
        rim = np.array(SUN) * 0.8 * (0.4 + 0.6 * light)
        out.append(Particles(d["atlas_obj"], (P[si] - fwd[None] * 0.004).astype(np.float32),
                             (size[si] * 1.10 + 0.012).astype(np.float32), eul[si],
                             color=np.c_[np.broadcast_to(rim * a[:, None] ** 0 * 1.0, (len(si), 3)) * a[:, None],
                                         a * 0.0].astype(np.float32),
                             back=np.c_[np.broadcast_to(rim, (len(si), 3)) * a[:, None], a * 0.0].astype(np.float32),
                             uv=d["rects"][si], blend="add", group="past", bias=-7.5))
        c = col[si] * lit[si, None]
        back = np.broadcast_to(PIECE_BACK, (len(si), 3)) * (0.8 + 0.4 * lit[si, None])
        out.append(Particles(d["atlas_obj"], P[si].astype(np.float32), size[si].astype(np.float32), eul[si],
                             color=np.c_[c, a].astype(np.float32), back=np.c_[back, a].astype(np.float32),
                             uv=d["rects"][si], group="past", bias=-8.0))
    bi = np.flatnonzero(vis & (sharp < 0.99))
    if len(bi):
        scat = scatter_light(P[bi], eye, sun_dir(eye), t) * light
        c = col[bi] * (0.5 + 0.5 * scat[:, None])
        out += bokeh_particles(P[bi], s_eff[bi] * 0.8, c, eye, basis, alpha=(1 - sharp[bi]) * fade_far[bi])
    return out


def sun_dir(eye):
    """太阳的方向（从镜头看过去）：指向树冠平面上的太阳，也就是世界的 (0, 0, CANOPY_Z)。"""
    v = np.array([0.0, 0.0, CANOPY_Z], np.float32) - eye
    return (v / np.linalg.norm(v)).astype(np.float32)


def dust_items(t, eye, basis, cam_rest):
    P0, size, ph, fr, tint = dust_layout(cam_rest)
    P = drift(P0, ph, fr, t)
    light = sun_light(t)
    if light <= 0.003:
        return []
    scat = scatter_light(P, eye, sun_dir(eye), t) * light
    col = DUST_TINT[tint] * (scat * 1.3)[:, None]
    return bokeh_particles(P, size, col, eye, basis, min_px=0.9)


# ---------------------------------------------------------------- 歌词与旧句式

def loyalty_items(t, eye, basis):
    """四个字下面闪过的旧句式"永遠忠於"，后面是一段空着的横线：褪色红的仿宋，像印在纸上，闪两下就没了。"""
    t0 = T_HOME[3] + 0.06
    if t < t0 or t > t0 + 0.75:
        return []
    u = t - t0
    a = (0.9 * math.exp(-((u - 0.10) / 0.09) ** 2) + 0.75 * math.exp(-((u - 0.40) / 0.14) ** 2))
    if a < 0.01:
        return []
    h = EM * 0.30
    Y = (0.5 - MOSAIC_C[1]) * DF * 0.5359 - EM * 0.95
    X0 = -EM * 1.10
    P = cam_point(eye, basis, np.array([X0]), np.array([Y]), np.array([DF - 0.01]))[0]
    rot = facing_rot(basis)
    items = [TextPlane(look.trad("永远忠于"), kind="fang", weight=400, height=h, color=tuple(RED * 1.25),
                       center=tuple(P), rot=rot, align="left", tracking=0.18, opacity=a, group="past")]
    # 空白横线
    Pl = cam_point(eye, basis, np.array([X0 + h * 4 * 1.18 + EM * 0.55]), np.array([Y - h * 0.45]),
                   np.array([DF - 0.01]))[0]
    items.append(Plane(None, center=tuple(Pl), size=(EM * 1.0, h * 0.06), rot=rot, color=tuple(RED * 1.25),
                       opacity=a, group="past"))
    return items
