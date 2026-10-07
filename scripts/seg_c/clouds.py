"""副歌一 L11 的三团乌云：三个"来"（62.17、62.62、63.03 秒）各砸下一团写满"來"字的乌云。

观众第一眼要先认出这是云，再认出云上写满了"來"字。所以每团乌云分成两层：底下是一张用体积渲染烘焙出来的
云体贴图，轮廓柔软、边缘羽化，月光照到的团块顶部是冷白，团块之间的缝和云底压暗，云底前沿有一道窄的
暖橙（铁水映上来的光）；上面是一层"來"字粒子，亮部的字大而清楚，暗部的字小、颜色只比云体略亮，溶在
云里。每团正中再放一个大的"來"，它就是这一拍唱出的歌词，暖白色，与 L10 的歌词同色。

一、推荐用法

cloud_items() 一次给出一团乌云在场景里的全部元素，按绘制顺序排列，直接放进 frame(t) 的元素列表即可：

    import clouds as CL
    t_hit = (62.17, 62.62, 63.03)
    for i in range(3):
        if t < t_hit[i] - 0.3:
            continue
        y = 6.0 * (1 - T.ease("in_cubic", T.ramp(t, t_hit[i] - 0.25, t_hit[i])))     # 落下的位移，协调者决定
        items += CL.cloud_items(i, t - t_hit[i], origin=云底中心 + (0, y, 0), face=cam.eye,
                                strength=(1.0, 1.1, 1.3)[i])

cloud_items(i, t_rel=None, origin=(0, 0, 0), scale=1.0, face=None, group="past", stack=None, big=True,
big_alpha=None, strength=1.0, splash=1.0, glow=0.28, body_opacity=1.0) 的参数如下。i 是第几团（0、1、2），
也可以直接给一个 Cloud。t_rel 是相对这一团落地瞬间的秒数，None 表示静止、不形变。origin 是云底中心的
世界坐标。face 是镜头位置：给出时云体平面和大"來"转向镜头，不给时取烘焙时的朝向（正面朝前下方仰起
BAKE_ELEV = 28°）。big_alpha 缺省时大"來"按 big_alpha_at(t_rel) 在落地前 0.06 秒出现、落地瞬间亮一下；
需要自己控制时给 0–1 的数值。返回的元素依次是：云体平面（Plane）、"來"字与碎云（一组 Particles，图集为
lai_atlas()）、大"來"的淡光（Plane，add 混合）、大"來"（TextPlane，思源宋体 700）。它们共用一个 stack 键，
作为一个整体与其他元素排序，组内按上面的顺序绘制。

二、坐标、尺寸与预设

乌云的局部坐标系以云底中心为原点，x 向右，y 向上，z 朝向观众，单位为世界单位。云体在三维里是一团
积雨云的形状，宽 width、高 height、厚约 0.42·width；烘焙时把它沿视线投影到一张平面上，平面的坐标记为
(u, v, w)：u 向右，v 沿平面向上，w 是平面法线，朝向镜头。字和碎云都贴在这张平面前面一点（w 为宽度的
0.8%–1.8%），所以无论平面转向哪里，字都落在云体上。CLOUDS 是三团的预设，preset(i) 直接取用：

    第一团：宽 8.5、高 5.2、4 个主团块，中间一座高塔；
    第二团：宽 10、高 5.6、5 个主团块，高塔偏右；
    第三团：宽 12.5、高 6.4、7 个主团块、heavy = 1.3，最大最重，颜色最深。

大"來"的字高为云宽的 BIG_FRAC = 36%，放在云体正中偏上；它所在的区域不放小字。
三团在预览里的摆放见 assets_preview.py 的 cloud_layout()：云底在墙头上方 3–5 单位，左右并排，前后略错开。
按这个高度，wall_pose(18.5, 22, 5, pitch=20, dy=1) 的机位正好把三团放在画面上部；
wall_pose(17.5, 19, 8, pitch=6) 时乌云只露出画面上沿，若要在"乌云"二字时就让乌云入画，云底要再低 2–3 单位。

三、云体怎样烘焙

云的形状是一个有符号距离场：底部一个压扁的椭球决定云底的宽度，上面沿 x 排开几个主团块，每个主团块的
上半部再长出几层小鼓包，两侧有几小团碎云，最后在 y = 0 处切平作为云底。距离场加上四层平铺的三维噪声
推动表面，形成翻滚的团块，云底附近噪声减弱，底部保持平；表面外再加一层很淡的絮。密度从表面向内在宽度的
2.6% 之内由 0 升到 1，所以轮廓是软的。

光照分三部分。月光从左上方照来（MOON_DIR），在粗网格上从每个点朝月亮方向累积密度，得到透光率，只有
团块的上部明显受光，越往下越弱（乌云厚而暗）；天光从正上方来，强度很低；月亮在云后时轮廓透出一点冷光
（BACK_DIR）。铁水的暖橙只给云底前沿宽度 4.5% 以内的一窄条，沿 x 断续起伏，往后很快淡去。然后从镜头
一侧沿视线逐步合成（视线仰角 BAKE_ELEV），得到云体的颜色和不透明度，再放大两倍、给边缘加一点絮状的
起伏。颜色常数（MOON_C、SKY_C、BACK_C、FIRE_C、DARK_C）是调色之前的数值，过去层的调色会再提亮、
加暖；按现在的数值，云体暗部比 backdrop.py 的夜空暗一档，团块顶部接近冷白。

四、"來"字与碎云

"來"字按云体贴图来放：在轮廓以内随机取点，月光照到的地方字大（约宽度的 4%–6%）、颜色是明亮的冷白、
完全不透明；暗处的字小（约 2%–3.5%），颜色只比云体略亮，不透明度 0.3–0.6，溶在云里；离轮廓越远字越大。
字与字按尺寸从大到小依次落点，彼此不重叠，转角在 ±10° 左右，暗处略大。字形七成用思源黑体 900，其余用
思源宋体 900 和思源黑体 700。lai_atlas() 是一张 3×3 格的图集：前三格是三种"來"字（字身白色、外面一圈
很淡的暗影，亮字在亮云上也分得开），第七格是柔边圆团，最后两格是絮状碎片；第四到第六格是带明暗的云团，
现在没有用到。

碎云沿轮廓边缘取点，云底和两侧多一些，颜色取自里面一点的云体，静止时完全透明，砸下时才出现。

五、砸下的形变

impact_uvw() 与 impact() 给出形变后的粒子，cloud_items() 内部已经调用，一般不必直接使用。形变按相对落地
瞬间的时间 t 计算。落地前 0.3 秒内，云竖向最多拉长 10%，表现下落的速度。落地后云体以云底为基准竖向压扁
（SQUASH = 22%）、横向摊开（压扁量的 45%），按时间常数 0.20 秒、周期 0.55 秒的衰减振荡回弹；云体平面、
字和大"來"一起变形。同时轮廓附近的字和碎云沿二维外法线飞出，云底附近的往两侧和下方飞，少数飞得特别远；
位移按时间常数 0.28 秒减速，尺度为宽度的 16%（字再乘 1.15，碎云乘 1.5）。碎云在 0.05 秒内出现、边飞边散开变大，
0.25–1.3 秒间淡去；飞出的字缓缓下沉，在 0.15–1.25 秒间最多淡去 70%。strength 乘在压扁和拉长上，
splash 乘在飞溅上；squash_at(t) 单独给出压扁量，可用来同步镜头的震动。

六、其他接口

lai_cloud(seed, width, height, lobes, depth, heavy) 生成任意一团乌云，返回 Cloud：dict 部分是字和碎云粒子的
pos、size、rot、color、uv（缺省朝向下的局部坐标，配 lai_atlas() 可直接交给 Particles）；Cloud.body 是云体贴图
（0–1 浮点 RGBA，直通 alpha，第 0 行是图像顶部）；Cloud.meta 记录 kind（0 字、3 碎云）、uvw、splash、spin、
rest_alpha、body_box（贴图覆盖的平面坐标范围 u0, v0, u1, v1）、base_v、top_v、big（大字的 u、v 与字高）和 elev。
for_glyph_atlas(cloud) 只取字形粒子，供改配 engine.glyph_atlas("來") 时使用，这时没有云体，不推荐。
结果缓存在 data/cache/seg_c/：粒子数据为 clouds_v{VERSION}_{参数摘要}.npz，云体贴图为同名的 _body.png；
光照常数并入了参数摘要，改动后自动重算。第一次生成每团约 20–30 秒。

运行 assets_preview.py clouds 生成三张预览：三团并排的正面、wall_pose 仰角下的一张、第三团砸下的六个时刻。

范围与局限：云体是一张烘焙好的平面，镜头绕着乌云转过 30° 以上时，看到的仍是烘焙时的那一面；云体的光照
在烘焙时就确定了，场景里月亮的方向若与 MOON_DIR 相差很大，要改常数后重新烘焙。
"""
import hashlib
import json
import math
import sys
from pathlib import Path

import cv2
import numpy as np
from scipy.ndimage import distance_transform_edt, gaussian_filter, map_coordinates

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "scripts", ROOT / "scripts" / "style"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import look  # noqa: E402

CACHE = ROOT / "data" / "cache" / "seg_c"
VERSION = 18
CHAR = look.trad("来")                     # "來"

# 三团乌云的预设：第三团最大、最重
CLOUDS = (
    dict(seed=41, width=8.5, height=5.2, lobes=4, heavy=0.9),
    dict(seed=44, width=10.0, height=5.6, lobes=5, heavy=1.0),
    dict(seed=37, width=12.5, height=6.4, lobes=7, heavy=1.3),
)


def _unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v)


MOON_DIR = _unit([-0.45, 0.88, 0.05])       # 月光：左上方，只照亮团块的顶部，正面和缝里暗
FIRE_DIR = _unit([0.10, -0.40, 0.91])       # 铁水的光：前下方，几乎水平地照在云底的前沿

# 字的颜色（调色之前的数值）
GLYPH_LIT = np.array([0.80, 0.86, 1.00])        # 亮部的字（明亮的冷白）
BIG_COLOR = tuple(float(x) for x in look.C["warm"] * 1.15)     # 正中的大"來"：与 L10 的歌词同色
BIG_FRAC = 0.36                                  # 大"來"的字高占云宽的比例


# ---------------------------------------------------------------------------
# 图集：三种"來"字、三种云团（备用）、一种柔边圆团、两种絮状碎片
# ---------------------------------------------------------------------------

CELL = 256
ATLAS_KEYS = ("sans900", "serif900", "sans700", "puff0", "puff1", "puff2", "fill", "wisp0", "wisp1")
GLYPH_CELLS, PUFF_CELLS, FILL_CELL, WISP_CELLS = (0, 1, 2), (3, 4, 5), 6, (7, 8)
KIND_GLYPH, KIND_PUFF, KIND_FILL, KIND_WISP, KIND_GLOW = 0, 1, 2, 3, 4
_atlas = {}


def _noise(h, w, scale, octaves=3, seed=0):
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, tot, s = 1.0, 0.0, float(scale)
    for _ in range(octaves):
        g = rng.random((max(2, int(h / s) + 2), max(2, int(w / s) + 2))).astype(np.float32)
        out += cv2.resize(g, (w, h), interpolation=cv2.INTER_CUBIC) * amp
        tot += amp
        amp *= 0.5
        s /= 2
    out /= tot
    lo, hi = np.percentile(out, 1), np.percentile(out, 99)
    return np.clip((out - lo) / (hi - lo + 1e-6), 0, 1)


def _smooth(e0, e1, x):
    t = np.clip((np.asarray(x, np.float32) - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def _glyph_cells():
    """三种"來"字：字身白色（乘粒子颜色），外面一圈很淡的柔和暗影，帮助亮字从亮的云团上分出来。"""
    import skia
    from engine.text import EM_BOTTOM, EM_TOP, make_font
    out = []
    em = CELL / (1 + 2 * 0.12)
    for kind, wt in (("sans", 900), ("serif", 900), ("sans", 700)):
        cov = np.zeros((CELL, CELL), np.uint8)
        s = skia.Surface.MakeRasterDirect(skia.ImageInfo.MakeA8(CELL, CELL), cov)
        c = s.getCanvas()
        f = make_font(kind, wt, em)
        adv = f.measureText(CHAR)
        c.drawString(CHAR, (CELL - adv) / 2, CELL / 2 - (EM_TOP + EM_BOTTOM) / 2 * em, f,
                     skia.Paint(AntiAlias=True, Color=skia.ColorWHITE))
        del c, s
        g = cov.astype(np.float32) / 255
        halo = np.clip(gaussian_filter(g, 0.035 * em) * 1.6, 0, 1) * 0.30
        a = g + (1 - g) * halo
        rgb = np.where(a > 1e-4, g / np.maximum(a, 1e-4), 0)
        out.append(np.dstack([rgb, rgb, rgb, a]))
    return out


def _puff_cell(seed):
    """一个云团：边缘起伏、柔和羽化；内部按球面的法线从左上方打光，上亮下暗，带一点斑驳。"""
    rng = np.random.default_rng(seed)
    n = CELL
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    x = (xx + 0.5) / n * 2 - 1
    y = (yy + 0.5) / n * 2 - 1
    ang = np.arctan2(-y, x)
    R = 0.74 + sum(rng.uniform(0.02, 0.06) / k * np.cos(k * ang + rng.uniform(0, 6.28)) for k in range(3, 9))
    R = R + 0.06 * np.clip(np.sin(ang), 0, 1)                      # 上半部略鼓
    rr = np.hypot(x, y) / R
    edge = rr + 0.10 * (_noise(n, n, 22, 3, seed) - 0.5)
    a = _smooth(1.0, 0.50, edge) ** 1.3
    nx, ny = x / R, -y / R
    nz = np.sqrt(np.clip(1 - nx ** 2 - ny ** 2, 0, 1))
    L = _unit([-0.35, 0.85, 0.40])
    shade = 0.50 + 0.50 * np.clip(nx * L[0] + ny * L[1] + nz * L[2], 0, 1)
    shade = shade * (0.86 + 0.28 * _noise(n, n, 30, 3, seed + 1))
    a = a * (0.80 + 0.20 * _noise(n, n, 18, 2, seed + 2))
    return np.dstack([shade, shade, shade, a])


def _fill_cell():
    n = CELL
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    r = np.hypot((xx + 0.5) / n * 2 - 1, (yy + 0.5) / n * 2 - 1)
    a = np.exp(-(r ** 2) * 3.2) * _smooth(1.0, 0.85, r)
    one = np.ones_like(a)
    return np.dstack([one, one, one, a])


def _wisp_cell(seed):
    """絮状碎片：横向拉长、边缘破碎、半透明。"""
    n = CELL
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    x = (xx + 0.5) / n * 2 - 1
    y = (yy + 0.5) / n * 2 - 1
    e = np.hypot(x, y * 2.8)
    nz = _noise(n, n, 26, 4, seed)
    streak = cv2.resize(np.random.default_rng(seed + 3).random((n // 4, 6)).astype(np.float32), (n, n),
                        interpolation=cv2.INTER_CUBIC)
    a = _smooth(1.0, 0.15, e + 0.35 * (nz - 0.5)) * (0.55 + 0.45 * streak) * 0.85
    shade = 0.80 + 0.20 * np.clip(-y * 2, -1, 1)
    return np.dstack([shade, shade, shade, a])


def lai_atlas():
    """乌云用的图集（engine.Atlas），3×3 格，条目名见 ATLAS_KEYS：前三格是"來"字（思源黑体 900、思源宋体 900、
    思源黑体 700），接着三格带明暗的云团（备用）、一格柔边圆团、两格絮状碎片。贴图为 RGBA，乘粒子颜色。"""
    if "a" in _atlas:
        return _atlas["a"]
    from engine import Atlas
    cells = _glyph_cells() + [_puff_cell(11), _puff_cell(23), _puff_cell(37), _fill_cell(),
                              _wisp_cell(5), _wisp_cell(9)]
    W = H = 3 * CELL
    data = np.zeros((H, W, 4), np.float32)
    rects = {}
    for i, (k, c) in enumerate(zip(ATLAS_KEYS, cells)):
        cx, cy = (i % 3) * CELL, (i // 3) * CELL
        data[cy:cy + CELL, cx:cx + CELL] = c
        rects[k] = (cx / W, cy / H, (cx + CELL) / W, (cy + CELL) / H)
    _atlas["a"] = Atlas(np.clip(data, 0, 1), rects, list(ATLAS_KEYS))
    return _atlas["a"]


def _uv(cell):
    cell = np.asarray(cell, int)
    cx, cy = cell % 3, cell // 3
    return np.stack([cx / 3, cy / 3, (cx + 1) / 3, (cy + 1) / 3], -1).astype(np.float32)


# ---------------------------------------------------------------------------
# 形状：球体并集
# ---------------------------------------------------------------------------

def _smin(a, b, k):
    h = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b * (1 - h) + a * h - k * h * (1 - h)


def _hemi(rng, up=0.35, front=0.45):
    v = rng.normal(size=3)
    v[1] = abs(v[1]) + up
    v[2] = v[2] * 0.7 + front
    return v / np.linalg.norm(v)


class _Shape:
    """乌云的有符号距离场（世界单位，负值在云内）：底部一个压扁的椭球，上面沿 x 排开几个主团块，
    中间偏一侧的最高；每个主团块的上半部再长三到五个次级鼓包，鼓包上偶尔再长更小的鼓包；
    前后各一个低团块增加厚度，两侧几小团碎云。并集用小半径的平滑最小值连接，最后在 y = 0 切平作为云底。"""

    def __init__(self, seed, width, height, lobes, depth):
        rng = np.random.default_rng(seed)
        W, H, D = width, height, depth
        sph = [((0.0, 0.10 * H, 0.0), (0.47 * W, 0.20 * H, 0.36 * D))]
        xs = np.linspace(-0.34, 0.34, lobes) * W + rng.uniform(-0.04, 0.04, lobes) * W
        peak = rng.uniform(-0.12, 0.18) * W
        for x in xs:
            mid = math.exp(-((x - peak) / (0.36 * W)) ** 2)
            r = W * rng.uniform(0.12, 0.17) * (0.78 + 0.45 * mid)
            top = (0.36 + 0.64 * mid ** 1.5 * rng.uniform(0.82, 1.0)) * H
            y = max(top - r, 0.5 * r)
            z = rng.uniform(-0.12, 0.12) * D
            c0 = np.array([x, y, z])
            sph.append((tuple(c0), (r, r * rng.uniform(0.92, 1.05), r * rng.uniform(0.80, 0.95))))
            for _ in range(rng.integers(3, 6)):
                rr = r * rng.uniform(0.36, 0.55)
                c1 = c0 + _hemi(rng) * r * rng.uniform(0.70, 0.86)
                if c1[1] + rr > 1.06 * H:
                    continue
                sph.append((tuple(c1), (rr, rr, rr)))
                for _ in range(rng.integers(0, 3)):
                    r3 = rr * rng.uniform(0.38, 0.55)
                    c2 = c1 + _hemi(rng, 0.2, 0.6) * rr * 0.82
                    if c2[1] + r3 < 1.08 * H:
                        sph.append((tuple(c2), (r3, r3, r3)))
        for sgn in (-1, 1):
            r = W * rng.uniform(0.12, 0.16)
            sph.append(((rng.uniform(-0.25, 0.25) * W, 0.55 * r, sgn * 0.22 * D), (r, r * 0.85, r)))
        for _ in range(rng.integers(2, 5)):
            side = rng.choice([-1, 1])
            r = W * rng.uniform(0.035, 0.065)
            sph.append(((side * W * rng.uniform(0.44, 0.56), H * rng.uniform(0.12, 0.55),
                         rng.uniform(-0.1, 0.25) * D), (r * 1.3, r, r)))
        self.sph = [(np.array(c, float), np.array(r, float)) for c, r in sph]
        self.k = 0.03 * W
        nf = 10
        dirs = rng.normal(size=(nf, 3))
        dirs /= np.linalg.norm(dirs, axis=1, keepdims=True)
        freq = rng.uniform(1.5, 4.0, nf) * (10.0 / W)
        self.kv = dirs * freq[:, None]
        self.ph = rng.uniform(0, 2 * np.pi, nf)
        self.amp = 0.004 * W * (freq.mean() / freq)

    def __call__(self, p):
        d = None
        for c, r in self.sph:
            q = (p - c) / r
            di = (np.linalg.norm(q, axis=-1) - 1) * r.min()
            d = di if d is None else _smin(d, di, self.k)
        d = d + (np.sin(p @ self.kv.T + self.ph) * self.amp).sum(-1)
        return np.maximum(d, -p[..., 1])

    def normal(self, p, h=0.03):
        g = np.stack([(self(p + e) - self(p - e)) / (2 * h) for e in np.eye(3) * h], -1)
        return g / np.maximum(np.linalg.norm(g, axis=-1, keepdims=True), 1e-6)


def _poisson(P, size, factor, order=None):
    """按 order（缺省为尺寸从大到小）依次落点：与已放置的点距离小于 factor·(两者尺寸之和)/2 的点舍弃。
    factor 可以是标量或逐点数组。返回保留下来的下标。"""
    factor = np.broadcast_to(np.asarray(factor, float), size.shape)
    order = np.argsort(-size) if order is None else order
    cell = float(size.max() * factor.max() + 1e-6)
    grid, acc = {}, []
    for i in order:
        p = P[i]
        key = (int(p[0] // cell), int(p[1] // cell), int(p[2] // cell))
        ok = True
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for j in grid.get((key[0] + dx, key[1] + dy, key[2] + dz), ()):
                        lim = factor[i] * (size[i] + size[j]) * 0.5
                        v = P[j] - p
                        if v[0] * v[0] + v[1] * v[1] + v[2] * v[2] < lim * lim:
                            ok = False
                            break
                    if not ok:
                        break
                if not ok:
                    break
            if not ok:
                break
        if ok:
            grid.setdefault(key, []).append(i)
            acc.append(i)
    return np.array(acc, int)


# ---------------------------------------------------------------------------
# 云体：体积渲染烘焙成一张贴图
# ---------------------------------------------------------------------------

BAKE_ELEV = 28.0                # 烘焙时的视线仰角（度）：镜头在前下方仰看乌云
LIGHT_SOFT = 0.90               # 光线在云内的衰减比视线弱，模拟多次散射，明暗过渡更柔和
MOON_C = np.array([1.00, 1.12, 1.42])        # 月光（偏冷）
SKY_C = np.array([0.010, 0.012, 0.017])      # 天光（自上方）
BACK_C = np.array([0.26, 0.30, 0.40])        # 月亮在云后时的透光轮廓
FIRE_C = np.array([0.0, 0.0, 0.0])              # 原为铁水映上来的暖橙；平面版里墙上已没有铁水，这道暖光去掉
DARK_C = np.array([0.006, 0.007, 0.010])     # 云内最暗处
BACK_DIR = _unit([-0.30, 0.55, -0.78])       # 云后的月亮方向


def _plane_basis(elev_deg=BAKE_ELEV):
    a = math.radians(elev_deg)
    ex = np.array([1.0, 0.0, 0.0])
    ey = np.array([0.0, math.cos(a), math.sin(a)])
    n = np.array([0.0, -math.sin(a), math.cos(a)])            # 朝向镜头（前下方）
    return ex, ey, n


def _fbm3(shape, scales, weights, seed):
    """三维平滑噪声（均值约 0）：每一层是随机格点的三次插值，scales 为特征尺寸（体素）。"""
    from scipy.ndimage import zoom
    rng = np.random.default_rng(seed)
    out = np.zeros(shape, np.float32)
    for s, w in zip(scales, weights):
        g = rng.random(tuple(int(math.ceil(n / s)) + 3 for n in shape)).astype(np.float32)
        up = zoom(g, s, order=3, prefilter=False)
        out += w * (up[:shape[0], :shape[1], :shape[2]] - 0.5)
    return out


def _march(rho_c, lo, cvox, dirv, steps, step):
    """在粗网格上从每个体素沿 dirv 方向累积密度，返回光学厚度（以完整密度下的长度计，世界单位）。"""
    nx, ny, nz = rho_c.shape
    ix, iy, iz = np.meshgrid(np.arange(nx), np.arange(ny), np.arange(nz), indexing="ij")
    base = np.stack([ix, iy, iz]).reshape(3, -1).astype(np.float32)
    acc = np.zeros(base.shape[1], np.float32)
    dv = (np.asarray(dirv) * step / cvox).astype(np.float32)[:, None]
    for k in range(1, steps + 1):
        acc += map_coordinates(rho_c, base + dv * k, order=1, mode="constant", cval=0.0)
    return (acc * step).reshape(rho_c.shape)


def _noise_tile(seed, n=64, sigma=2.2):
    """周期的三维平滑噪声（n³，0–1），按 mode="wrap" 采样可以无缝平铺；特征尺寸约 4 格。"""
    rng = np.random.default_rng(seed)
    t = gaussian_filter(rng.random((n, n, n)).astype(np.float32), sigma, mode="wrap")
    lo_, hi_ = np.percentile(t, 1), np.percentile(t, 99)
    return np.clip((t - lo_) / (hi_ - lo_), 0, 1).astype(np.float32)


class _Density:
    """云的密度场：粗网格上的距离场加四层平铺噪声推动表面（云底附近减弱，底部保持平），
    再在表面外加一层很淡的絮。density(P) 可以在任意点上求值。"""

    def __init__(self, shp, W, H, D, seed, lo, hi, cvox):
        self.W, self.H, self.lo, self.cvox = W, H, lo, cvox
        cs = tuple(int(math.ceil((hi[k] - lo[k]) / cvox)) + 1 for k in range(3))
        gx, gy, gz = (lo[k] + np.arange(cs[k]) * cvox for k in range(3))
        G = np.stack(np.meshgrid(gx, gy, gz, indexing="ij"), -1).reshape(-1, 3)
        self.cs, self.G = cs, G
        self.dc = np.concatenate([shp(G[i:i + 200000]) for i in range(0, len(G), 200000)]).reshape(cs).astype(np.float32)
        self.oct = [(0.13 * W, 0.55), (0.065 * W, 0.30), (0.032 * W, 0.18), (0.016 * W, 0.10)]
        self.tiles = [_noise_tile(seed * 7 + k) for k in range(len(self.oct))]
        self.wtile = _noise_tile(seed * 7 + 11)

    def __call__(self, P):
        W, H = self.W, self.H
        P = np.asarray(P, np.float32)
        d = map_coordinates(self.dc, ((P - self.lo) / self.cvox).T, order=1, mode="nearest")
        nz = np.zeros(len(P), np.float32)
        for (s, a), t in zip(self.oct, self.tiles):
            nz += a * (map_coordinates(t, (P / s * 4.0).T, order=1, mode="grid-wrap") - 0.5)
        calm = _smooth(0.02 * H, 0.18 * H, P[:, 1])
        dn = d + 0.085 * W * nz * (0.42 + 0.58 * calm)
        rho = _smooth(0.006 * W, -0.020 * W, dn)
        wn = map_coordinates(self.wtile, (P / (0.05 * W) * 4.0).T, order=1, mode="grid-wrap")
        rho = np.maximum(rho, 0.14 * _smooth(0.05 * W, 0.0, dn) * _smooth(0.45, 0.75, wn))
        return rho.astype(np.float32)


def _bake(shp, W, H, D, heavy, seed):
    """体积渲染一团乌云，返回 (rgba 贴图, 渲染分辨率下的辅助图 dict, 平面坐标范围)。"""
    vox = W / 420                               # 渲染像素（贴图再放大 2 倍）
    cvox = W / 140                              # 光照网格
    lo = np.array([-0.72 * W, -0.04 * H, -0.66 * D])
    hi = np.array([0.72 * W, 1.16 * H, 0.66 * D])
    den = _Density(shp, W, H, D, seed, lo, hi, cvox)
    rho_c = den(den.G).reshape(den.cs)
    ext = 0.012 * W                          # 完整密度下光学厚度为 1 的长度
    step = 0.022 * W

    def trans(dirv, steps):
        tau = _march(rho_c, lo, cvox, dirv, steps, step) / ext * LIGHT_SOFT
        return (np.exp(-tau) * 0.75 + np.exp(-tau * 0.25) * 0.25).astype(np.float32)
    T_moon = trans(MOON_DIR, 26)
    T_sky = trans(np.array([0.0, 1.0, 0.0]), 22)
    T_back = trans(BACK_DIR, 26)
    # 云底前沿：每个 x 上，离地 0.04H 处云体最靠前的 z；暖橙只给前沿 0.07W 以内
    jy = int(round((0.04 * H - lo[1]) / cvox))
    col_ = rho_c[:, jy, :] > 0.5
    zgrid = lo[2] + np.arange(den.cs[2]) * cvox
    zf_x = np.where(col_.any(1), zgrid[den.cs[2] - 1 - np.argmax(col_[:, ::-1], axis=1)], lo[2] - 1.0)
    zf_x = gaussian_filter(zf_x, 1.0)
    xgrid = lo[0] + np.arange(den.cs[0]) * cvox
    # 沿视线合成
    ex, ey, n = _plane_basis()
    corners = np.array([[x, y, z] for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
    U, V, Wn = corners @ ex, corners @ ey, corners @ n
    us = np.arange(U.min(), U.max(), vox)
    vs = np.arange(V.max(), V.min(), -vox)                  # 第 0 行是图像顶部
    dstep = 0.9 * vox
    ws = np.arange(Wn.max(), Wn.min(), -dstep)              # 从镜头一侧往里
    UU, VV = np.meshgrid(us, vs)
    base = (UU[..., None] * ex + VV[..., None] * ey).reshape(-1, 3).astype(np.float32)
    # 每条视线进出云的范围（用粗网格的距离场估计），只在这段里采样
    T = np.ones(base.shape[0], np.float32)
    C = np.zeros((base.shape[0], 3), np.float32)
    Mo = np.zeros(base.shape[0], np.float32)
    n32 = n.astype(np.float32)
    lo32 = lo.astype(np.float32)
    active = np.ones(base.shape[0], bool)
    for w in ws:
        idx = np.nonzero(active)[0]
        if len(idx) == 0:
            break
        P = base[idx] + w * n32
        dco = map_coordinates(den.dc, ((P - lo32) / cvox).T, order=1, mode="constant", cval=1e3)
        near = dco < 0.12 * W
        if not near.any():
            continue
        idx, P = idx[near], P[near]
        r = den(P)
        hit = r > 1e-4
        if not hit.any():
            continue
        idx, P, r = idx[hit], P[hit], r[hit]
        ci = ((P - lo32) / cvox).T
        tm = map_coordinates(T_moon, ci, order=1, mode="nearest")
        ts = map_coordinates(T_sky, ci, order=1, mode="nearest")
        tb = map_coordinates(T_back, ci, order=1, mode="nearest")
        low = 1 - _smooth(0.0, 0.055 * H, P[:, 1])
        dz = P[:, 2] - np.interp(P[:, 0], xgrid, zf_x)
        brk = map_coordinates(den.wtile, (np.c_[P[:, 0], np.zeros(len(P)), P[:, 0] * 0.3] / (0.09 * W) * 4.0).T,
                              order=1, mode="grid-wrap")                       # 沿 x 断续起伏
        lip = (_smooth(-0.045 * W, -0.004 * W, dz) * (0.35 + 0.9 * brk)
               + 0.15 * _smooth(-0.25 * W, -0.04 * W, dz))
        # 乌云厚而暗：月光只在团块的上部明显，越往下越弱
        upper = 0.18 + 0.82 * _smooth(0.40 * H, 0.88 * H, P[:, 1])
        thin = 0.45 + 0.55 * _smooth(0.15, 0.6, r)                     # 很稀的絮反光弱，不在轮廓外形成一圈亮边
        L = (DARK_C + MOON_C * (tm * upper / heavy ** 0.3)[:, None] + SKY_C * ts[:, None]
             + BACK_C * (0.45 * tb * upper)[:, None]) * thin[:, None] + FIRE_C * (low ** 1.5 * lip)[:, None]
        a = 1 - np.exp(-r * dstep / ext)
        Ti = T[idx]
        C[idx] += (Ti * a)[:, None] * L
        Mo[idx] += Ti * a * tm * upper
        T[idx] = Ti * (1 - a)
        done = idx[T[idx] < 0.004]
        active[done] = False
    shp2 = UU.shape
    A = (1 - T).reshape(shp2)
    C = C.reshape(shp2 + (3,))
    col = C / np.maximum(A, 1e-4)[..., None]
    moon_img = Mo.reshape(shp2) / np.maximum(A, 1e-4)
    aux = dict(A=A, col=col, moon=moon_img, us=us, vs=vs, vox=vox)
    # 贴图：放大 2 倍，加二维细节（边缘的絮、明暗的斑驳）
    k = 2
    h0, w0 = A.shape
    Ab = cv2.resize(A, (w0 * k, h0 * k), interpolation=cv2.INTER_CUBIC)
    Cb = cv2.resize(C, (w0 * k, h0 * k), interpolation=cv2.INTER_CUBIC)
    nz2 = _noise(h0 * k, w0 * k, 22, 4, seed + 11)
    edge = np.clip(4 * Ab * (1 - Ab), 0, 1)
    Ab2 = np.clip(Ab + 0.22 * (nz2 - 0.5) * edge, 0, 1)
    col_b = Cb / np.maximum(Ab, 1e-4)[..., None]
    col_b = col_b * (0.94 + 0.12 * _noise(h0 * k, w0 * k, 30, 3, seed + 12))[..., None]
    tex = np.dstack([np.clip(col_b, 0, 4), Ab2]).astype(np.float32)
    tex[Ab2 < 1e-3, :3] = 0
    ext_uv = (us[0] - vox / 2, vs[-1] - vox / 2, us[-1] + vox / 2, vs[0] + vox / 2)     # u0, v0, u1, v1
    return tex, aux, ext_uv


# ---------------------------------------------------------------------------
# 一团乌云：云体贴图 + "來"字粒子 + 砸下时飞出的碎云
# ---------------------------------------------------------------------------

class Cloud(dict):
    """lai_cloud() 的返回值。dict 部分是"來"字和碎云粒子的 pos、size、rot、color、uv，坐标在乌云的局部坐标系、
    云体平面取缺省朝向（仰角 BAKE_ELEV）时的位置，配 lai_atlas() 可以直接交给 engine.Particles；
    属性 body 是云体贴图（RGBA）；meta 记录平面坐标与形变数据，见模块说明。"""
    meta = None
    body = None


def _light_key():
    """光照与云体参数的摘要，并入缓存键：这些常数改动后缓存自动重算。"""
    vals = [LIGHT_SOFT, BAKE_ELEV, BIG_FRAC] + [float(x) for v in (MOON_C, SKY_C, BACK_C, FIRE_C, DARK_C, MOON_DIR,
                                                               FIRE_DIR, BACK_DIR, GLYPH_LIT) for x in v]
    return hashlib.md5(json.dumps([round(v, 5) for v in vals]).encode()).hexdigest()[:8]


def _cache_key(params):
    return hashlib.md5(json.dumps(params, sort_keys=True).encode()).hexdigest()[:12]


def lai_cloud(seed, width=10.0, height=None, lobes=5, depth=None, heavy=1.0):
    """一团写满"來"字的乌云（正中的大"來"由 cloud_items() 加上）。结果缓存在 data/cache/seg_c/。"""
    from PIL import Image
    height = height or 0.5 * width
    depth = depth or 0.42 * width
    params = dict(v=VERSION, seed=seed, width=width, height=height, lobes=lobes, depth=depth, heavy=heavy,
                  elev=BAKE_ELEV, light=_light_key())
    key = _cache_key(params)
    f = CACHE / f"clouds_v{VERSION}_{key}.npz"
    fb = CACHE / f"clouds_v{VERSION}_{key}_body.png"
    if not (f.exists() and fb.exists()):
        _build(seed, width, height, lobes, depth, heavy, f, fb)
    z = np.load(f)
    cl = Cloud(pos=z["pos"], size=z["size"], rot=z["rot"], color=z["color"], uv=z["uv"])
    cl.meta = {k[5:]: z[k] for k in z.files if k.startswith("meta_")}
    cl.meta.update(width=width, height=height, depth_extent=depth)
    cl.body = np.asarray(Image.open(fb), np.float32) / 255
    return cl


def _build(seed, W, H, lobes, D, heavy, f, fb):
    from PIL import Image
    look.low_priority()
    rng = np.random.default_rng(seed + 1000)
    shp = _Shape(seed, W, H, lobes, D)
    tex, aux, (u0, v0, u1, v1) = _bake(shp, W, H, D, heavy, seed)
    A, col, moon, us, vs, vox = aux["A"], aux["col"], aux["moon"], aux["us"], aux["vs"], aux["vox"]
    h0, w0 = A.shape
    inside = A > 0.55
    dist = distance_transform_edt(inside) * vox
    # 云底（轮廓最低处）与正中的位置
    rows = np.nonzero(inside.any(1))[0]
    base_v = float(vs[rows.max()])
    top_v = float(vs[rows.min()])
    cols = np.nonzero(inside.any(0))[0]
    wsum = A * inside
    uc = float((wsum.sum(0) * us).sum() / wsum.sum())
    big_h = BIG_FRAC * W
    big_v = base_v + 0.60 * (top_v - base_v)
    big_v = min(big_v, top_v - 0.60 * big_h)
    big_v = max(big_v, base_v + 0.62 * big_h)
    # 一、"來"字：轮廓里面，月光照到的地方字大而亮，暗处字小、溶进云体
    m = 16000
    jj = rng.integers(0, w0, m * 6)
    ii = rng.integers(0, h0, m * 6)
    ok = (A[ii, jj] > 0.85) & (dist[ii, jj] > 0.010 * W)
    ii, jj = ii[ok][:m], jj[ok][:m]
    gu = us[jj] + rng.uniform(-0.5, 0.5, len(jj)) * vox
    gv = vs[ii] + rng.uniform(-0.5, 0.5, len(ii)) * vox
    lit = _smooth(0.12, 0.45, moon[ii, jj])
    q = np.clip(dist[ii, jj] / (0.16 * W), 0, 1)
    size = W * (0.020 + 0.016 * q + 0.024 * lit) * rng.uniform(0.80, 1.15, len(ii)) * heavy ** 0.15
    # 大"來"所在的区域不放小字
    inbig = (np.abs(gu - uc) < 0.48 * big_h) & (np.abs(gv - big_v) < 0.50 * big_h)
    keep = ~inbig
    gu, gv, ii, jj, lit, q, size = gu[keep], gv[keep], ii[keep], jj[keep], lit[keep], q[keep], size[keep]
    P2 = np.c_[gu, gv, np.zeros_like(gu)]
    idx = _poisson(P2, size, 0.84 - 0.02 * lit, order=np.argsort(-(size * (1 + lit))))
    gu, gv, ii, jj, lit, q, size = gu[idx], gv[idx], ii[idx], jj[idx], lit[idx], q[idx], size[idx]
    ng = len(gu)
    body_c = col[ii, jj]
    dark_g = body_c * 1.6 + np.array([0.034, 0.039, 0.054])     # 暗部的字：比云体略亮的灰蓝，溶在云里
    col_g = dark_g + (GLYPH_LIT * (0.78 + 0.32 * lit)[:, None] - dark_g) * lit[:, None]
    col_g = col_g * rng.uniform(0.95, 1.04, ng)[:, None]
    a_g = (0.50 + 0.50 * _smooth(0.06, 0.35, moon[ii, jj])) * np.where(lit > 0.5, 1.0, rng.uniform(0.6, 1.0, len(ii)))
    rot_g = rng.normal(0, 0.10, ng) + rng.normal(0, 0.22, ng) * (1 - lit)
    pick = rng.random(ng)
    cell_g = np.where(pick < 0.70, 0, np.where(pick < 0.90, 1, 2))
    w_g = 0.012 * W + 0.004 * W * lit + rng.uniform(0, 0.002 * W, ng)
    # 外法线（二维）：A 模糊后的负梯度
    Ab = gaussian_filter(A, 3.0)
    gy_, gx_ = np.gradient(Ab)
    nu, nv = -gx_, gy_                               # 图像 y 向下，平面 v 向上
    nn = np.hypot(nu, nv) + 1e-6
    nu, nv = nu / nn, nv / nn
    edge_g = np.clip(1 - dist[ii, jj] / (0.07 * W), 0, 1) ** 1.5
    # 二、碎云：轮廓边缘一圈，云底和两侧多；静止时不显示，砸下时飞出
    band = (A > 0.25) & (A < 0.70)
    bi, bj = np.nonzero(band)
    sel = rng.permutation(len(bi))[:6000]
    bi, bj = bi[sel], bj[sel]
    bu, bv = us[bj], vs[bi]
    lowp = 1 - np.clip((bv - base_v) / (top_v - base_v), 0, 1)
    prob = 0.25 + 0.75 * np.clip(lowp ** 2 + (np.abs(bu - uc) / (0.5 * W)) ** 2, 0, 1)
    k2 = rng.random(len(bi)) < prob
    bi, bj, bu, bv = bi[k2], bj[k2], bu[k2], bv[k2]
    sw = rng.uniform(0.08, 0.17, len(bi)) * W
    idx = _poisson(np.c_[bu, bv, np.zeros_like(bu)], sw, 0.55, order=rng.permutation(len(bu)))[:int(90 * W / 10)]
    bi, bj, bu, bv, sw = bi[idx], bj[idx], bu[idx], bv[idx], sw[idx]
    nw = len(bi)
    ii2 = np.clip(bi + np.round(nv[bi, bj] * 6).astype(int), 0, h0 - 1)      # 往里挪几个像素取云体颜色
    jj2 = np.clip(bj - np.round(nu[bi, bj] * 6).astype(int), 0, w0 - 1)
    col_w = np.maximum(col[ii2, jj2] * 1.2, np.array([0.055, 0.062, 0.082]))   # 碎云要从夜空里分得出来
    a_w = rng.uniform(0.40, 0.62, nw)
    rot_w = rng.normal(0, 0.35, nw)
    cell_w = np.where(rng.random(nw) < 0.6, FILL_CELL, rng.choice(WISP_CELLS, nw))
    w_w = np.full(nw, 0.008 * W)
    # 合并（平面坐标 u, v, w：u 向右，v 沿平面向上，w 朝向镜头）
    uvw = np.r_[np.c_[bu, bv, w_w], np.c_[gu, gv, w_g]]
    kind = np.r_[np.full(nw, KIND_WISP), np.full(ng, KIND_GLYPH)]
    size_all = np.r_[sw, size]
    rot_all = np.r_[rot_w, rot_g]
    color = np.c_[np.r_[col_w, col_g], np.r_[a_w, a_g]]
    uv = _uv(np.r_[cell_w, cell_g])
    # 飞溅方向：二维外法线，云底的碎云多往两侧和下方，另带一点朝向镜头的分量
    su = np.r_[nu[bi, bj], nu[ii, jj]]
    sv = np.r_[nv[bi, bj], nv[ii, jj]]
    lowall = 1 - np.clip((uvw[:, 1] - base_v) / (top_v - base_v), 0, 1)
    side = np.sign(uvw[:, 0] - uc + 1e-6)
    su = su * (1 - 0.6 * lowall ** 2) + side * 0.9 * lowall ** 2
    sv = sv * (1 - 0.6 * lowall ** 2) - 0.15 * lowall ** 2
    sn = np.hypot(su, sv) + 1e-6
    sdir = np.c_[su / sn, sv / sn, rng.uniform(0.0, 0.4, len(su))]
    u_r = rng.random(len(su))
    edge_all = np.r_[np.ones(nw), edge_g]
    smag = edge_all * (0.35 + 1.5 * u_r ** 3) * (0.6 + 0.8 * lowall)
    spin = rng.normal(0, 1.6, len(su)) * edge_all * (kind == KIND_GLYPH)
    order = np.argsort(uvw[:, 2], kind="stable")          # 按 w 从后往前，绘制时不必再排序
    uvw, kind, size_all, rot_all, color, uv = uvw[order], kind[order], size_all[order], rot_all[order], color[order], uv[order]
    sdir, smag, spin = sdir[order], smag[order], spin[order]
    ex, ey, n = _plane_basis()
    R0 = np.stack([ex, ey, n], 1)
    pos = uvw @ R0.T
    meta = dict(kind=kind.astype(np.int8), uvw=uvw.astype(np.float32), splash=(sdir * smag[:, None]).astype(np.float32),
                spin=spin.astype(np.float32), rest_alpha=color[:, 3].astype(np.float32),
                body_box=np.array([u0, v0, u1, v1], np.float32), base_v=np.float32(base_v),
                top_v=np.float32(top_v), big=np.array([uc, big_v, big_h], np.float32),
                elev=np.float32(BAKE_ELEV))
    color[kind == KIND_WISP, 3] = 0.0                      # 碎云静止时不显示
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(f, pos=pos.astype(np.float32), size=size_all.astype(np.float32),
                        rot=rot_all.astype(np.float32), color=color.astype(np.float32), uv=uv,
                        **{"meta_" + k: v for k, v in meta.items()})
    Image.fromarray((np.clip(tex, 0, 1) * 255 + 0.5).astype(np.uint8), "RGBA").save(fb)


def preset(i):
    """第 i 团（0、1、2）乌云：按 CLOUDS[i] 的参数生成的 Cloud。"""
    return lai_cloud(**CLOUDS[i])


def for_glyph_atlas(cloud):
    """只取"來"字粒子的 pos、size、rot、color，用于改配 engine.glyph_atlas("來", ...) 的场合（没有云体，不推荐）。"""
    k = cloud.meta["kind"] == KIND_GLYPH
    return dict(pos=cloud["pos"][k], size=cloud["size"][k], rot=cloud["rot"][k], color=cloud["color"][k])


# ---------------------------------------------------------------------------
# 砸下的形变
# ---------------------------------------------------------------------------

SQUASH = 0.22           # 落地瞬间云体竖向压扁的幅度
SQUASH_TAU = 0.20       # 压扁衰减的时间常数（秒）
SQUASH_PERIOD = 0.55    # 回弹振荡的周期（秒）
SPREAD = 0.45           # 压扁时横向摊开的比例（相对压扁量）
SPLASH_DIST = 0.16      # 飞溅位移的尺度（宽度的比例）
SPLASH_TAU = 0.28       # 飞溅减速的时间常数（秒）
STRETCH = 0.10          # 落地前竖向拉长的幅度


def squash_at(t, strength=1.0):
    """t 秒时（相对落地瞬间）的压扁量：正值为压扁，负值为拉长（落地前与回弹）。t 为 None 时为 0。"""
    if t is None:
        return 0.0
    if t < 0:
        return -STRETCH * strength * float(np.clip(1 + t / 0.30, 0, 1)) ** 2
    return SQUASH * strength * math.exp(-t / SQUASH_TAU) * math.cos(2 * math.pi * t / SQUASH_PERIOD)


def _squash_uv(u, v, base_v, sq):
    return u * (1 + SPREAD * sq), base_v + (v - base_v) * (1 - sq)


def impact_uvw(cloud, t, strength=1.0, splash=1.0):
    """形变后的平面坐标：返回 (uvw (N,3), size, rot, color, body_center_uv, body_size_uv, sq)。"""
    m = cloud.meta
    W = m["width"]
    uvw = m["uvw"].astype(np.float64).copy()
    size = cloud["size"].astype(np.float64).copy()
    rot = cloud["rot"].astype(np.float64).copy()
    col = cloud["color"].copy()
    kind = m["kind"]
    base_v = float(m["base_v"])
    u0, v0, u1, v1 = [float(x) for x in m["body_box"]]
    sq = squash_at(t, strength)
    uvw[:, 0], uvw[:, 1] = _squash_uv(uvw[:, 0], uvw[:, 1], base_v, sq)
    bu0, bv0 = _squash_uv(u0, v0, base_v, sq)
    bu1, bv1 = _squash_uv(u1, v1, base_v, sq)
    if t is not None and t >= 0:
        go = 1 - math.exp(-t / SPLASH_TAU)
        mult = np.where(kind == KIND_WISP, 1.5, 1.15)[:, None]
        uvw += m["splash"] * mult * (SPLASH_DIST * W * splash * go)
        far = np.clip(np.linalg.norm(m["splash"][:, :2], axis=1) * splash, 0, 1.5) / 1.5
        uvw[:, 1] -= 0.04 * W * far * float(np.clip((t - 0.2) / 1.0, 0, 1)) ** 1.5
        rot += m["spin"] * go * splash
        wisp = kind == KIND_WISP
        appear = float(_smooth(0.0, 0.05, t))
        fade_w = 1 - float(_smooth(0.25, 1.30, t))
        col[wisp, 3] = m["rest_alpha"][wisp] * appear * fade_w * min(1.0, splash)
        size[wisp] *= 1 + 2.0 * go
        fade_g = float(np.clip((t - 0.15) / 1.1, 0, 1))
        g = ~wisp
        col[g, 3] *= 1 - 0.7 * far[g] * fade_g
        size[g] *= 1 - 0.25 * far[g] * fade_g
    return (uvw, size, rot, col, np.array([(bu0 + bu1) / 2, (bv0 + bv1) / 2]), (bu1 - bu0, bv1 - bv0), sq)


def impact(cloud, t, strength=1.0, splash=1.0):
    """乌云砸下时粒子的形变，返回 dict(pos, size, rot, color, uv)，坐标为缺省朝向下的局部坐标；
    另附 body_center（云体平面中心，局部坐标）、body_size 和 squash。t 为相对落地瞬间的秒数。"""
    uvw, size, rot, col, bc, bs, sq = impact_uvw(cloud, t, strength, splash)
    ex, ey, n = _plane_basis(float(cloud.meta["elev"]))
    R0 = np.stack([ex, ey, n], 1)
    return dict(pos=(uvw @ R0.T).astype(np.float32), size=size.astype(np.float32), rot=rot.astype(np.float32),
                color=col, uv=cloud["uv"], body_center=R0 @ np.array([bc[0], bc[1], 0.0]), body_size=bs, squash=sq)


# ---------------------------------------------------------------------------
# 组合：一团乌云在场景里的全部元素
# ---------------------------------------------------------------------------

def _euler(M):
    p = math.asin(float(np.clip(-M[1, 2], -1, 1)))
    if abs(math.cos(p)) > 1e-6:
        r = math.atan2(M[1, 0], M[1, 1])
        y = math.atan2(M[0, 2], M[2, 2])
    else:
        r, y = 0.0, math.atan2(-M[2, 0], M[0, 0])
    return (math.degrees(y), math.degrees(p), math.degrees(r))


_glow = {}


def _glow_tex():
    """大"來"周围的淡光：字形的高斯模糊，覆盖与大字字框同中心、边长 1.6 倍字高的方形。"""
    if "g" in _glow:
        return _glow["g"]
    import skia
    from engine.text import EM_BOTTOM, EM_TOP, make_font
    n = 512
    em = n / 1.6
    cov = np.zeros((n, n), np.uint8)
    s = skia.Surface.MakeRasterDirect(skia.ImageInfo.MakeA8(n, n), cov)
    c = s.getCanvas()
    f = make_font("serif", 700, em)
    adv = f.measureText(CHAR)
    c.drawString(CHAR, (n - adv) / 2, n / 2 - (EM_TOP + EM_BOTTOM) / 2 * em, f,
                 skia.Paint(AntiAlias=True, Color=skia.ColorWHITE))
    del c, s
    g = gaussian_filter(cov.astype(np.float32) / 255, 0.06 * em)
    _glow["g"] = np.clip(g / g.max(), 0, 1).astype(np.float32)
    return _glow["g"]


def big_alpha_at(t):
    """正中大"來"的不透明度与亮度倍数：落地前 0.06 秒开始出现，落地瞬间亮一下再回到 1。"""
    if t is None:
        return 1.0, 1.0
    a = float(_smooth(-0.06, 0.03, t))
    flash = 1.0 + 0.40 * math.exp(-max(t, 0.0) / 0.12) if t >= 0 else 1.0
    return a, flash


_body_tex = {}


def cloud_items(i, t_rel=None, origin=(0.0, 0.0, 0.0), scale=1.0, face=None, group="past", stack=None,
                big=True, big_alpha=None, strength=1.0, splash=1.0, glow=0.28, body_opacity=1.0):
    """第 i 团乌云（或直接给一个 Cloud）的全部引擎元素，按绘制顺序排列：云体平面、"來"字与碎云粒子、
    大"來"的淡光、大"來"。t_rel 为相对这一团落地瞬间的秒数（None 表示静止、不形变）；origin 为云底中心的
    世界坐标；face 为镜头位置，给出时云体平面和大字转向镜头，否则取烘焙时的仰角 BAKE_ELEV；big_alpha 缺省
    按 big_alpha_at(t_rel) 自动出现。"""
    from engine import Particles, Plane, Tex, TextPlane
    cl = preset(i) if isinstance(i, (int, np.integer)) else i
    m = cl.meta
    W = m["width"]
    o = np.asarray(origin, float)
    uvw, size, rot, col, bc, bs, sq = impact_uvw(cl, t_rel, strength, splash)
    if face is None:
        ex, ey, n = _plane_basis(float(m["elev"]))
    else:
        c0 = o + np.array([0.0, 0.45 * m["height"], 0.0]) * scale
        n = np.asarray(face, float) - c0
        n /= np.linalg.norm(n)
        ex = np.cross([0.0, 1.0, 0.0], n)
        ex /= np.linalg.norm(ex)
        ey = np.cross(n, ex)
    R = np.stack([ex, ey, n], 1)
    rot3 = _euler(R)
    key = stack or f"lai_cloud_{id(cl)}"
    k = id(cl.body)
    if k not in _body_tex:
        _body_tex[k] = Tex(cl.body)
    items = [Plane(_body_tex[k], center=o + R @ np.array([bc[0], bc[1], 0.0]) * scale,
                   size=(bs[0] * scale, bs[1] * scale), rot=rot3, opacity=body_opacity, group=group, stack=key)]
    vis = col[:, 3] > 0.003
    items.append(Particles(lai_atlas(), o + (uvw[vis] @ R.T) * scale, size[vis] * scale, rot[vis], col[vis],
                           cl["uv"][vis], group=group, stack=key, sort=False))
    if big:
        a, flash = big_alpha_at(t_rel)
        if big_alpha is not None:
            a = big_alpha
        if a > 0:
            ub, vb, hb = [float(x) for x in m["big"]]
            ub, vb = _squash_uv(ub, vb, float(m["base_v"]), sq)
            sx, sy = 1 + SPREAD * sq, 1 - sq
            c = o + R @ np.array([ub, vb, 0.03 * W]) * scale
            h = hb * scale
            if glow > 0:
                g = glow * a * flash
                items.append(Plane(_glow_tex(), center=c, size=(1.6 * h * sx, 1.6 * h * sy), rot=rot3,
                                   color=tuple(float(x) * g for x in BIG_COLOR), blend="add", group=group, stack=key))
            items.append(TextPlane(CHAR, kind="serif", weight=700, height=h * sy, scale_x=sx / sy,
                                   color=tuple(float(x) * flash for x in BIG_COLOR), center=c, rot=rot3, opacity=a,
                                   group=group, stack=key))
    return items
