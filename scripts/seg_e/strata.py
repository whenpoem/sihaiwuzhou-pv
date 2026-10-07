"""L22 上升途中一层层压下来的"过去"：每条层带都是前面某一段画面撕下来的一条。

间奏二向下坠落时穿过的是同一批层（renders/layers/*.png，由 scripts/seg_g/make_layers.py 从各段渲染），上升段让观众
认出这些正是前面看过的画面，两次穿越前后呼应。层带按高度排出年代：越往上年代越近——
报纸字栏的海与暴雨（间奏一、L15，第二层）、标语墙（L10，第二层）、逆光的被单（L05，第一层）、旧纸与电视（L01–L03，
第一层）。

每条层带比画面宽，任何时候都看不到端头。贴图取那幅画面里最有代表性的一条横带，按原来的比例贴上，不拉伸；上下边缘
是撕开的纸边，在材质 e_strip 里按平面自身的坐标算出：边缘起伏、露出一圈宽窄不一的白色纸芯、伸出半透明的纤维毛边，
白边内侧是纸被撕起时的一道浅影。每条带子在身后投下一片柔和的影子。

层带分四个深度（远、中、近、最近），远的一层彼此首尾相叠、连成一片，所以近处带子之间的空隙里总能看到更远的带子以
较慢的速度移动，不会露出平涂的底色。越往上带子越窄、越密（"萬重"，115.29 秒最密）。四层的上沿按镜头算好，在
115.25 秒前后依次扫过画面上部，露出最远处最后一层旧纸上的"換了人間"，此后到撕开之前它都不被遮挡。

层画面的文件还没有时（被单要等 B 段完成）用占位贴图，文件出现后自动换成真实画面。
"""
import math

import numpy as np
from scipy.ndimage import gaussian_filter

import common
import look
from flatcam import cached
from engine import Atlas, Particles, Plane, Tex, register_material

from water import LINE_X, K

LAYER_DIR = common.ROOT / "renders" / "layers"
ASPECT = 16 / 9
H_MAX = 3.0                                  # 上升段镜头的画面高（最后半秒略小）
DU = 0.72                                    # 每条带子取原画面宽度的 72%，横向取样位置各不相同
D_MAX = H_MAX * K

# 各层画面：(文件, 最认得出的几处横带的竖直中心)。旧纸由 paper_layer.py 渲染到本段缓存
SOURCES = {
    "newspaper": (LAYER_DIR / "newspaper.png", (0.30, 0.47, 0.80)),   # 间奏一：红帆"大海航行靠舵手"、船身、字块
    "rain": (LAYER_DIR / "rain.png", (0.18, 0.55, 0.84)),             # L15：三个"拜"、单车的干轮廓、"誰的單車"
    "wall": (LAYER_DIR / "wall.png", (0.45, 0.57, 0.72, 0.93)),       # L10：墙皮污渍、墙上的歌词、红漆标语
    "sheets": (LAYER_DIR / "sheets.png", (0.30, 0.50, 0.70)),         # L05：逆光的被单
    "tv": (LAYER_DIR / "tv.png", (0.40, 0.52, 0.62)),                 # L03：电视里的"形勢大好　不是小好"
    "paper": (common.CACHE / "layer_paper.png", (0.25, 0.45, 0.62)),  # 前奏与 L01 交接处的旧纸
}
# 高度 → 年代（世界 y 的分界，越往上越近）
ERAS = [(0.0, ("newspaper", "rain")), (4.6, ("wall",)), (6.4, ("sheets",)), (8.0, ("tv", "tv", "paper"))]


# ---------------------------------------------------------------- 材质

register_material("e_strip", """
uniform float s_h;          // 带子本身的高度（世界单位，不含毛边的留白）
uniform float s_e;          // 这一深度上一个画面高对应的世界长度：撕边的细节按画面比例取
uniform float s_seed;
uniform float band_k;
uniform vec3 band_tint;
// 撕边的起伏：大的波浪 + 中等的豁口 + 细的锯齿；豁口用折返的噪声，形成尖的缺口
float edge_n(float xs, float s, int k) {
    float big = vnoise(vec2(xs * 1.3 + s, 1.0 + s), k);
    float mid = abs(vnoise(vec2(xs * 6.0 - s, 2.0), k + 1) - 0.5) * 2.0;
    float fine = vnoise(vec2(xs * 31.0 + s * 3.0, 3.0), k + 2);
    float notch = smoothstep(0.80, 0.97, vnoise(vec2(xs * 2.4 + s * 5.0, 4.0), k + 3));
    return big * 0.55 + mid * 0.28 + fine * 0.10 + notch * 0.9;
}
vec4 material(vec4 base) {
    vec2 q = v_local;
    float xs = q.x / s_e;
    float top = 0.5 * s_h - s_e * (0.004 + 0.045 * edge_n(xs, s_seed, 11));
    float bot = -0.5 * s_h + s_e * (0.004 + 0.045 * edge_n(xs, s_seed + 5.3, 21));
    float dt = top - q.y, db = q.y - bot;
    float d = min(dt, db);                       // 大于 0 在纸内
    bool is_top = dt < db;
    float side = is_top ? 0.0 : 9.0;
    float aa = fwidth(d) * 1.2 + 1e-6;
    // 纤维毛边：稀疏、长短不一的细纤维，多数很短，偶尔有一根长的，方向略斜
    float lane = floor(xs * 700.0);
    float r1 = rnd(ivec2(int(lane), int(side) + int(s_seed * 13.0)), 51);
    float r2 = rnd(ivec2(int(lane), int(side) + 7), 52);
    float lx = fract(xs * 700.0) - 0.5 + (d / s_e) * 700.0 * 0.0012 * (r2 - 0.5) * 40.0;
    float thin = 1.0 - smoothstep(0.08, 0.30, abs(lx));
    float flen = s_e * (0.002 + 0.010 * r1 * r1 + 0.020 * step(0.97, r1));
    float hair = thin * step(0.55, r1) * (1.0 - smoothstep(0.0, flen, -d)) * step(d, 0.0) * 0.8;
    float body = smoothstep(-aa, aa, d);
    float alpha = max(body, hair);
    // 白色纸芯：上沿多半露出、下沿少，宽窄沿边缘变化很大，长段几乎没有，偶尔撕出一片斜的宽白边
    float wv = vnoise(vec2(xs * 1.7 + side + s_seed * 2.0, 8.0), 41);
    float wcore = s_e * (is_top ? 1.0 : 0.45) * (0.0008 + 0.028 * pow(smoothstep(0.35, 0.95, wv), 1.5));
    float inband = (1.0 - smoothstep(wcore * 0.5, wcore + aa, d)) * body;
    float tx = vnoise(q / s_e * 1100.0, 42) * 0.6 + vnoise(q / s_e * 260.0, 43) * 0.4;
    vec3 white = vec3(0.94, 0.91, 0.85) * (0.78 + 0.30 * tx);
    // 纸被撕起时翘起：纸芯内侧一道很窄的浅影，只在纸芯宽的地方明显
    float lift = exp(-max(d - wcore, 0.0) / (s_e * 0.004)) * (1.0 - inband) * smoothstep(0.002, 0.012, wcore / s_e);
    vec3 col = base.rgb * band_tint * band_k * (1.0 - 0.22 * lift);
    vec3 paper = white * band_tint * min(band_k * 1.08, 1.25);
    col = mix(col, paper, max(inband, hair * (1.0 - body)));
    return vec4(col * alpha, alpha);
}
""", {"s_h": 1.0, "s_e": 1.0, "s_seed": 0.0, "band_k": 1.0, "band_tint": (1.0, 1.0, 1.0)})


# ---------------------------------------------------------------- 贴图

def _placeholder(name):
    """层画面还没有时的占位：被单用逆光的白布纹，其余用旧纸色加一行层名。"""
    rng = np.random.default_rng(abs(hash(name)) % 997)
    h, w = 1080, 1920
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    if name == "sheets":
        weave = 0.5 + 0.25 * np.sin(xx * 1.9) * np.sin(yy * 1.9 + 0.5)
        folds = gaussian_filter(rng.normal(0, 1, w), 60)
        folds = (folds - folds.min()) / (folds.max() - folds.min())
        shade = 0.72 + 0.40 * folds[None, :] + 0.08 * gaussian_filter(rng.normal(0, 1, (h, w)), 8)
        return np.clip(np.array([1.0, 0.93, 0.78]) * (shade * (0.9 + 0.1 * weave))[..., None], 0, 1).astype(np.float32)
    return (np.array(look.C["paper"]) * np.ones((h, w, 3)) * 0.8).astype(np.float32)


def layer_tex(name):
    """层画面的贴图（RGB uint8）。文件不存在时用占位；文件之后出现（例如 B 段完成后），下一次启动自动用上。"""
    def make():
        f = SOURCES[name][0]
        if f.exists():
            from PIL import Image
            return Tex(np.asarray(Image.open(f).convert("RGB")))
        return Tex(_placeholder(name))
    return cached(("strata_tex", name), make)


def available(name):
    return SOURCES[name][0].exists()


# ---------------------------------------------------------------- 排布

def hs(z, H=H_MAX):
    """深度 z 处一个画面高对应的世界长度。"""
    d = H * K
    return H * (d - z) / d


# 四个深度：(z, 底端高度, 顶端高度, 带高（画面高的比例，底部→顶部）, 带距（同上，负数表示相叠）, 首个带子的种子)
TIERS = [
    dict(z=-14.0, y0=2.00, y1=8.95, h=(0.50, 0.26), gap=(-0.08, -0.05), seed=1),
    dict(z=-6.0, y0=2.40, y1=9.15, h=(0.40, 0.18), gap=(0.12, 0.04), seed=2),
    dict(z=-2.2, y0=2.90, y1=9.25, h=(0.32, 0.13), gap=(0.20, 0.05), seed=3),
    dict(z=-0.6, y0=3.60, y1=9.30, h=(0.22, 0.09), gap=(0.50, 0.12), seed=4),
]


def era(y, rng):
    names = ERAS[0][1]
    for y0, ns in ERAS:
        if y >= y0 + rng.normal(0, 0.25):
            names = ns
    return names[int(rng.integers(0, len(names)))]


def layout():
    """所有层带：dict(y 中心, 高, z, 画面, 竖直取样中心, 横向取样起点, 倾角, 种子)。"""
    def make():
        out = []
        last = {}
        for ti, T in enumerate(TIERS):
            rng = np.random.default_rng(100 + T["seed"])
            S = hs(T["z"])
            y = T["y0"]
            while True:
                f = np.clip((y - T["y0"]) / (T["y1"] - T["y0"]), 0, 1)
                hf = T["h"][0] + (T["h"][1] - T["h"][0]) * f ** 0.8
                h = hf * S * rng.uniform(0.85, 1.15)
                if y + h > T["y1"]:
                    h = T["y1"] - y
                    if h < 0.04 * S:
                        break
                name = era(y + h / 2, rng)
                anchors = SOURCES[name][1]
                choices = [a for a in range(len(anchors)) if a != last.get(name)] or [0]
                ai = choices[int(rng.integers(0, len(choices)))]
                last[name] = ai
                vc = anchors[ai] + rng.normal(0, 0.02)
                out.append(dict(y=y + h / 2, h=h, z=T["z"] + rng.uniform(-0.06, 0.06) * S, name=name,
                                vc=float(vc), u0=float(rng.uniform(0.0, 1.0 - DU)),
                                tilt=float(rng.normal(0, 0.7)), seed=float(rng.uniform(0, 50)), tier=ti))
                gf = T["gap"][0] + (T["gap"][1] - T["gap"][0]) * f
                y += h + gf * S * rng.uniform(0.6, 1.4)
                if y >= T["y1"]:
                    break
        out.sort(key=lambda b: b["z"])
        return out
    return cached("strata_layout", make)


def band_light(y):
    """层被上方透下的冷白光照亮的程度：越高越亮、越冷。层画面本身已经带过一次过去的调色，这里略压一点，
    免得再经过一次调色后过亮过暖。"""
    f = float(np.clip((y - 2.0) / 9.0, 0, 1))
    k = 0.72 + 0.30 * f ** 1.4
    tint = np.array([1.0, 0.97, 0.93]) * (1 - f ** 2) + np.array([0.93, 0.98, 1.06]) * f ** 2
    return k, tint


def _shadow_tex():
    n = 128
    yy = np.linspace(-1, 1, n)[:, None] * np.ones((1, 8))
    v = 1.0 - 0.7 * np.exp(-(yy / 0.45) ** 2)
    return np.dstack([v, v, v, np.ones_like(v)]).astype(np.float32)


def band_items(t, cam):
    x, y, H = cam
    if y < 0.0:
        return []
    d = H * K
    items = []
    shadow = cached("strata_shadow", lambda: Tex(_shadow_tex()))
    for b in layout():
        z = b["z"]
        if d - z <= 0.3:
            continue
        S = hs(z, H)
        if abs(b["y"] - y) > 0.5 * S + b["h"]:
            continue
        S_max = hs(z)
        W = 1.32 * ASPECT * S_max                     # 比画面宽，任何时候看不到端头
        pad = 0.05 * S_max
        hp = b["h"] + 2 * pad
        du = DU
        dv = du * ASPECT * hp / W                     # 按原画面的比例取样，不拉伸
        v0 = float(np.clip(b["vc"] - dv / 2, 0.0, 1.0 - dv))
        k, tint = band_light(b["y"])
        items.append(Plane(shadow, center=(LINE_X, b["y"] - 0.30 * b["h"], z - 0.02), size=(W, b["h"] * 1.25),
                           rot=(0, 0, b["tilt"]), blend="multiply", group="past", opacity=0.65))
        items.append(Plane(layer_tex(b["name"]), center=(LINE_X, b["y"], z), size=(W, hp),
                           uv=(b["u0"], v0, b["u0"] + du, v0 + dv), rot=(0, 0, b["tilt"]), group="past",
                           material="e_strip",
                           uniforms=dict(s_h=b["h"], s_e=S_max, s_seed=b["seed"], band_k=k, band_tint=tuple(tint))))
    return items


# ---------------------------------------------------------------- 纸屑

N_FLAKES = 1000
TEXT_COLUMN = (0.70, 0.92)          # "換了人間"所在的画面横向范围：纸屑避开这一列


def flake_atlas():
    """纸屑图集：8×8 个不规则的撕纸小片，每片从某一幅层画面上剪下，带白色纸边。"""
    def make():
        import cv2
        from PIL import Image
        cell, n = 96, 8
        out = np.zeros((cell * n, cell * n, 4), np.float32)
        rng = np.random.default_rng(7)
        srcs = []
        for name in ("paper", "newspaper", "paper", "tv"):     # 多数是浅色的纸，少数是深色的画面碎片
            f = SOURCES[name][0]
            img = np.asarray(Image.open(f).convert("RGB").resize((960, 540)), np.float32) / 255 if f.exists() \
                else _placeholder(name)[::2, ::2]
            srcs.append(img)
        rects = {}
        keys = []
        for i in range(n * n):
            src = srcs[i % len(srcs)]
            y0, x0 = rng.integers(0, src.shape[0] - cell), rng.integers(0, src.shape[1] - cell)
            patch = src[y0:y0 + cell, x0:x0 + cell]
            m = int(rng.integers(5, 9))
            ang = np.sort(rng.uniform(0, 2 * np.pi, m))
            rad = rng.uniform(0.22, 0.46, m) * cell
            pts = np.c_[cell / 2 + np.cos(ang) * rad, cell / 2 + np.sin(ang) * rad * rng.uniform(0.4, 1.0)]
            mask = np.zeros((cell, cell), np.uint8)
            cv2.fillPoly(mask, [pts.astype(np.int32)], 1)
            a = gaussian_filter(mask.astype(np.float32), 0.8)
            edge = np.clip(a * (1 - gaussian_filter(mask.astype(np.float32), 2.5)) * 4, 0, 1)
            rgb = patch * (1 - edge[..., None]) + np.array([0.93, 0.90, 0.84]) * edge[..., None]
            r, c = divmod(i, n)
            out[r * cell:(r + 1) * cell, c * cell:(c + 1) * cell] = np.dstack([rgb, a])
            key = f"f{i}"
            rects[key] = (c / n, r / n, (c + 1) / n, (r + 1) / n)
            keys.append(key)
        return Atlas(out, rects, keys)
    return cached("flake_atlas", make)


def flake_items(t, cam):
    """近处被气流卷着往下飞的纸屑：越往上越多，115.55 秒鼓回来以后更密。它们只在镜头近处，速度最快，运动模糊
    最明显，用来让人感到上升在加速；避开"換了人間"那一列。"""
    x, y, H = cam
    if y < 1.0:
        return []

    def make():
        rng = np.random.default_rng(55)
        n = N_FLAKES
        yy = 1.0 + 22.0 * rng.random(n) ** 0.5                   # 越往上越密，鼓回来以后（y > 13）最密
        z = rng.uniform(0.3, 2.6, n)
        S = hs(z)
        sx = rng.uniform(0.02, 0.98, n)
        sx = np.where((sx > TEXT_COLUMN[0]) & (sx < TEXT_COLUMN[1]), sx - 0.25, sx)
        xx = LINE_X + (sx - 0.5) * ASPECT * S
        size = rng.lognormal(np.log(0.040), 0.40, n) * S
        spin = rng.normal(0, 3.0, n)
        ph = rng.uniform(0, 2 * np.pi, n)
        idx = rng.integers(0, 64, n)
        return yy, z, xx, size, spin, ph, idx
    yy, z, xx, size, spin, ph, idx = cached("flakes", make)
    atlas = flake_atlas()
    d = H * K
    S = H * (d - z) / d
    vis = np.abs(yy - y) < 0.55 * S + size
    if not vis.any():
        return []
    fall = 0.25 * np.sin(1.3 * t + ph)                           # 纸屑自己也在飘
    pos = np.c_[xx + 0.05 * np.sin(2.1 * t + ph) * S, yy + fall, z][vis].astype(np.float32)
    k, tint = band_light(y)
    col = np.c_[np.tile(tint * (k + 0.25), (vis.sum(), 1)), np.ones(vis.sum())].astype(np.float32)
    rot = (spin * t + ph)[vis].astype(np.float32)
    return [Particles(atlas, pos, size[vis].astype(np.float32), rot, col, atlas.index_uv(idx[vis]), blend="over",
                      group="past")]
