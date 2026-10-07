"""L29 的雨窗：雨打在镜头前的玻璃上，水珠一颗颗挂住，大的水珠顺着玻璃往下流，身后拖出一道水痕；随后玻璃起雾，
雾上浮现单车的轮廓，又被雾气盖住。

水珠是一颗颗小透镜：边缘因折射发暗，靠上的一侧有一点高光，靠下的一侧聚起一弯亮光（透过来的城市灯光被
倒着聚焦）。往下流的水珠走走停停（玻璃上的水珠先被附着力挂住，积够重量才滑下，碰到别的水珠又停一下），
身后留下一道窄窄的湿痕，湿痕慢慢断成一串小水珠。

雾是一层冷灰色的凝结水汽，在着色器里用分形噪声画出浓淡，从玻璃四边往中间长。单车的轮廓取副歌一后半
（D 段，scripts/seg_d/bike.py）按飞鸽自行车照片描出的侧影（缓存 data/cache/seg_d/bike_dry_v3.npy，只读）；
雾上被抹开的地方就是这个侧影，透出后面城市的灯光，像有人用手指在起雾的玻璃上画了一辆单车。
"""
import math

import cv2
import numpy as np

from f_common import ROOT, cached
from engine import Tex, register_material

register_material("f_fog", """
uniform float fog_k;             // 雾的浓度
uniform sampler2D bike;          // 单车轮廓（覆盖率）
uniform vec4 bike_rect;          // 轮廓在玻璃上的范围（0–1 坐标，u0, v0, u1, v1）
uniform float bike_k;            // 轮廓被抹开的程度
uniform float bike_sweep;        // 抹开的进度（从前轮到后轮，0–1）
vec4 material(vec4 b) {
    vec2 p = v_local;
    float fw = length(fwidth(p * 6.0));
    float n = fbm(p * 6.0, 5, fw, 3);
    float n2 = fbm(p * 22.0 + 7.0, 3, fw * 3.6, 9);
    // 从四边往中间长：边缘先起雾
    vec2 e = abs(v_uv01 - 0.5) * 2.0;
    float edge = max(e.x, e.y);
    float grow = smoothstep(1.0 - fog_k * 1.35, 1.25 - fog_k * 1.35, edge + (n - 0.5) * 0.5);
    float a = fog_k * grow * (0.55 + 0.45 * n) * (0.85 + 0.3 * n2);
    vec2 q = (v_uv01 - bike_rect.xy) / (bike_rect.zw - bike_rect.xy);
    if (q.x > 0.0 && q.x < 1.0 && q.y > 0.0 && q.y < 1.0) {
        float m = texture(bike, q).r;
        float sw = smoothstep(q.x, q.x + 0.08, bike_sweep);          // 从前轮（左）画到后轮（右）
        a *= 1.0 - m * bike_k * sw * (0.85 + 0.15 * n2);
    }
    vec3 col = vec3(0.30, 0.33, 0.38) * (0.8 + 0.4 * n) + vec3(0.12, 0.13, 0.15) * (1.0 - v_uv01.y);
    return vec4(col * a, a);
}
""", defaults={"fog_k": 0.0, "bike_rect": (0, 0, 1, 1), "bike_k": 0.0, "bike_sweep": 1.0})


def drop_tex():
    """一颗水珠（预乘发光 RGBA）：暗的折射边、左上的高光、下方的一弯亮光。"""
    def make():
        n = 128
        yy, xx = np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1
        r = np.hypot(xx, yy)
        inside = np.clip((1 - r) * n * 0.25, 0, 1)
        rim = np.exp(-((r - 0.86) / 0.12) ** 2) * inside
        hi = np.exp(-(((xx + 0.32) ** 2 + (yy + 0.38) ** 2) / 0.018))
        cres = np.exp(-((r - 0.62) / 0.12) ** 2) * np.clip(yy * 1.6, 0, 1) * inside
        body = inside * 0.18
        rgb = (hi * 2.2 + cres * 0.9 + body * 0.35)[..., None] * np.array([0.92, 0.97, 1.05])
        a = np.clip(rim * 0.65 + body + hi * 0.6 + cres * 0.3, 0, 1)
        return Tex(np.dstack([rgb, a]).astype(np.float32), premultiplied=True)
    return cached("drop_tex", make)


def trail_tex():
    """水痕：竖向的一道湿痕，两侧略亮，越往上（越早）越淡、越断续。"""
    def make():
        h, w = 512, 32
        yy, xx = np.mgrid[0:h, 0:w] / np.array([h - 1, w - 1])[:, None, None]
        side = np.exp(-((np.abs(xx - 0.5) - 0.32) / 0.08) ** 2)
        rng = np.random.default_rng(5)
        breaks = np.clip(cv2.GaussianBlur(rng.random((h, 1)).astype(np.float32), (0, 0), 6) * 3 - 0.9, 0, 1)
        fade = yy ** 0.7
        a = (side * 0.5 + 0.12 * np.exp(-((xx - 0.5) / 0.3) ** 2)) * (0.35 + 0.65 * fade) * (0.4 + 0.6 * breaks)
        rgb = side[..., None] * np.array([0.5, 0.55, 0.62]) * fade[..., None]
        return Tex(np.dstack([rgb, np.clip(a, 0, 1)]).astype(np.float32), premultiplied=True)
    return cached("trail_tex", make)


def bike_mask():
    """D 段按飞鸽自行车照片描出的单车侧影（只读取它的缓存），缩小到 1200 像素宽，边缘略散开。"""
    def make():
        p = ROOT / "data" / "cache" / "seg_d" / "bike_dry_v3.npy"
        m = np.load(p).astype(np.float32)
        h = int(m.shape[0] * 1200 / m.shape[1])
        m = cv2.resize(m, (1200, h), interpolation=cv2.INTER_AREA)
        m = np.clip(cv2.GaussianBlur(m, (0, 0), 1.2) * 1.3, 0, 1)
        return Tex(m)
    return cached("bike_mask", make)


def bike_aspect():
    p = ROOT / "data" / "cache" / "seg_d" / "bike_dry_v3.npy"
    m = np.load(p, mmap_mode="r")
    return m.shape[1] / m.shape[0]


def beads(n=1500, seed=29):
    """挂在玻璃上的水珠：位置（玻璃的 0–1 坐标）、大小（世界单位）、出现的时刻。"""
    def make():
        rng = np.random.default_rng(seed)
        pos = rng.uniform(0, 1, (n, 2))
        size = np.clip(rng.lognormal(np.log(0.015), 0.55, n), 0.004, 0.06)
        t0 = 137.12 + rng.exponential(0.55, n)
        return pos, size, t0
    return cached(f"beads_{seed}", make)


def runners(n=34, seed=7):
    """往下流的大水珠：起点、开始流的时刻、平均速度、大小。"""
    def make():
        rng = np.random.default_rng(seed)
        x = rng.uniform(0.03, 0.97, n)
        y = rng.uniform(0.02, 0.55, n)
        t0 = rng.uniform(137.3, 140.2, n)
        v = rng.uniform(0.18, 0.45, n)
        sz = rng.uniform(0.016, 0.030, n)
        ph = rng.uniform(0, 6.28, n)
        return x, y, t0, v, sz, ph
    return cached(f"runners_{seed}", make)


def run_y(t, t0, v, ph):
    """走走停停地往下流：速度 v·(1 + 0.95·sin(6u + φ)) 始终不小于 0.05v，停的时候几乎不动。返回已流下的距离（玻璃高度）。"""
    u = max(t - t0, 0.0)
    return v * (u - 0.95 / 6.0 * (math.cos(u * 6.0 + ph) - math.cos(ph)))
