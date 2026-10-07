"""L15–L16 的雨夜砖地（俯视）：湿透的砖地、路灯、闪电、由"丶"和短竖组成的雨，以及单车留下的干地。

砖地照片（Brick floor，Rob Tuytel / Poly Haven，CC0）平铺成地面，每块贴图对应 2.4 米见方。由照片求出两张辅助图：
砖缝（积水的地方）和砖面高度（砖面微微拱起，边缘圆钝）。地面材质 d_wetground 用它们算湿砖的明暗、积水的反光和
雨点涟漪。镜头从正上方往下看，雨点从镜头附近落向地面，在画面上沿径向朝中心汇聚，越近越大越快。
"""
import math

import numpy as np
from PIL import Image
from scipy import ndimage

import mats_d  # noqa: F401
from common import IMG, cached, disk_cached, hash01
from engine import Particles, Plane, Tex, glyph_atlas

TILE = 2.4                                   # 砖地贴图每块的世界尺寸（米）
GROUND_C = np.array([0.6, -0.3])             # 地面平面的中心
GROUND_SIZE = (16.0, 10.0)
LAMP = np.array([-1.25, 0.95, 3.4])            # 路灯：在画面左上方外面，高 3.8 米
LAMP_COL = np.array([1.15, 0.90, 0.62]) * 1.0  # 钠灯一类的暖光
AMB = np.array([0.060, 0.085, 0.150])        # 夜空的冷色环境光（低云反射的城市灯光）
SKY = np.array([0.050, 0.064, 0.095])        # 反射里的夜空：低云


def brick_tex():
    def make():
        im = Image.open(IMG / "Brick_floor_diff_8k_Rob_Tuytel_via_Poly_Haven_.png").convert("RGB")
        return Tex(np.asarray(im), repeat=True)
    return cached("brick_tex", make)


def brick_aux():
    """R：砖缝与坑洼（会积水），G：砖面高度（0–1，砖面中间高、边缘圆钝），B：未用。2048 见方，可平铺。"""
    def make():
        im = Image.open(IMG / "Brick_floor_diff_8k_Rob_Tuytel_via_Poly_Haven_.png").convert("RGB")
        a = np.asarray(im.resize((2048, 2048), Image.LANCZOS), np.float32) / 255
        L = a.mean(2)
        g = lambda x, s: ndimage.gaussian_filter(x, s, mode="wrap")
        m = g(L, 2.7)
        sd = np.sqrt(np.maximum(g(L * L, 2.7) - m * m, 0))
        dark = np.clip((g(L, 16) - g(L, 1.6) - 0.04) / 0.06, 0, 1)
        rough = np.clip((sd - 0.035) / 0.04, 0, 1)
        j = g(np.maximum(dark, rough), 2.1)
        j = np.clip((j - 0.25) / 0.4, 0, 1)
        height = g(1.0 - j, 6.0)
        height = (height - height.min()) / (height.max() - height.min() + 1e-6)
        out = np.zeros((2048, 2048, 4), np.uint8)
        out[..., 0] = (j * 255).astype(np.uint8)
        out[..., 1] = (height * 255).astype(np.uint8)
        out[..., 3] = 255
        return out
    return cached("brick_aux_tex", lambda: Tex(disk_cached("brick_aux_v1", make), repeat=True, premultiplied=True))


def reflect_dir(p, eye):
    """镜头经过水面上 p 点（z = 0）反射出去的方向：视线关于水平面镜像。一个光源若正好在这个方向上，
    它的倒影就落在 p 点。"""
    v = np.array([p[0] - eye[0], p[1] - eye[1], eye[2]], float)
    return tuple(v / np.linalg.norm(v))


def ground_items(t, flash=0.0, dry=None, pool=None, rain_k=1.0, opacity=1.0, lamp_k=1.0, impacts=(), moon=None):
    """砖地。dry 为 dict(rect=(x0, y0, x1, y1), rot=弧度, tex=Tex, t0=, t1=)；pool 为 (中心 x, 中心 y, 半径, 边缘不规则程度)。"""
    W, H = GROUND_SIZE
    uni = {"aux": brick_aux(), "lamp_pos": tuple(LAMP), "lamp_col": tuple(LAMP_COL * lamp_k), "amb": tuple(AMB),
           "sky": tuple(SKY), "flash": float(flash), "rain_k": float(rain_k)}
    if dry is not None:
        x0, y0, x1, y1 = dry["rect"]
        uni.update({"bikemask": dry["tex"], "dry_on": 1.0, "wet_t0": dry["t0"], "wet_t1": dry["t1"], "bike_rot": dry["rot"],
                    "bike_rect": (x0 - GROUND_C[0], y0 - GROUND_C[1], x1 - GROUND_C[0], y1 - GROUND_C[1])})
    else:
        uni.update({"bikemask": dummy_mask(), "dry_on": 0.0})
    if moon is not None:
        uni["moon_dir"] = tuple(moon)
    for i, im in enumerate(impacts[:3]):
        uni[f"imp{i}"] = tuple(float(v) for v in im)
    if pool is not None:
        uni.update({"pool_c": (pool[0], pool[1]), "pool_r": pool[2], "pool_irr": pool[3] if len(pool) > 3 else 0.0})
    return [Plane(brick_tex(), center=(*GROUND_C, 0.0), size=(W, H), uv=(0, 0, W / TILE, H / TILE), group="past",
                  material="d_wetground", uniforms=uni, opacity=opacity, stack="ground", bias=50.0)]


def dummy_mask():
    return cached("dummy_mask", lambda: Tex(np.zeros((4, 4), np.float32)))


# ---------------------------------------------------------------- 闪电

def flash_level(t, strikes):
    """闪电的亮度：strikes 为 [(时刻, 峰值)]，每次回击在 1 帧内升到峰值，随后约 0.05 秒衰减；主闪之后的天空余光更慢。"""
    v = 0.0
    for ts, k in strikes:
        if t >= ts - 0.004:
            u = max(t - ts, 0.0)
            v += k * (math.exp(-u / 0.045) * 0.85 + 0.15 * math.exp(-u / 0.25))
    return v


# ---------------------------------------------------------------- 雨

N_RAIN = 3200
RAIN_V = 7.5                       # 雨点下落速度（米/秒）
WIND = np.array([0.9, -0.35])      # 风把雨吹斜：每秒水平漂移（米）


def rain_atlas():
    return cached("rain_atlas", lambda: glyph_atlas("丶丨", kind="serif", weight=700, cell=96))


def rain_layout(box):
    """雨点的固定参数：水平位置、起始相位、字形（丶或丨）、粗细。box 为 (x0, y0, x1, y1)。"""
    def make():
        rng = np.random.default_rng(15)
        x0, y0, x1, y1 = box
        n = N_RAIN
        return dict(x=rng.uniform(x0, x1, n), y=rng.uniform(y0, y1, n), ph=rng.uniform(0, 1, n),
                    kind=(rng.uniform(0, 1, n) < 0.28).astype(int), w=rng.uniform(0.7, 1.3, n),
                    b=rng.uniform(0.5, 1.0, n))
    return cached(("rain_layout",) + tuple(box), make)


def rain_items(t, cam_state, ztop, flash=0.0, box=(-3.6, -2.8, 4.6, 2.6), k=1.0, lamp_k=1.0):
    """雨：每个雨点从高 ztop 处落到地面，循环往复。按画面上的运动方向转向、按 1/120 秒的位移拉长，
    远看是一道道朝画面中心汇聚的雨丝；"丶"形的雨点短而圆，"丨"形的拉成细长的雨丝。"""
    if k <= 0.001:
        return []
    L = rain_layout(box)
    cx, cy, H, _ = cam_state
    D = H * 1.8660254
    period = ztop / RAIN_V
    ph = (t / period + L["ph"]) % 1.0
    z = ztop * (1.0 - ph)
    tt = ph * period
    x = L["x"] + WIND[0] * tt
    y = L["y"] + WIND[1] * tt
    depth = np.maximum(D - z, 0.05)
    dt = 1.0 / 120.0
    dx = WIND[0] * dt - (x - cx) * RAIN_V * dt / depth
    dy = WIND[1] * dt - (y - cy) * RAIN_V * dt / depth
    ln = np.hypot(dx, dy)
    ang = np.arctan2(dy, dx) - np.pi / 2
    is_dot = L["kind"] == 1
    thick = np.where(is_dot, 0.010, 0.0026) * L["w"]
    cell_w = np.where(is_dot, thick / 0.45, thick / 0.085)
    length = np.where(is_dot, np.maximum(thick * 2.4, ln * 0.8), np.maximum(0.05, ln * 2.2 + 0.03))
    size = np.c_[cell_w, np.where(is_dot, length / 0.75, length / 0.9)]
    # 亮度：被路灯照到的雨丝亮，离镜头太近的雨点放大成虚影，压暗，不挡住地上的字
    dl = np.sqrt((x - LAMP[0]) ** 2 + (y - LAMP[1]) ** 2 + (z - LAMP[2]) ** 2)
    lit = 0.18 + 6.0 / (dl * dl + 0.5) * lamp_k
    near = np.clip((depth - 0.35) / 1.2, 0, 1)
    a = (lit * 0.30 + flash * 0.7) * L["b"] * near * k
    col = np.c_[a * 1.0, a * 0.93, a * 0.85, a]
    atlas = rain_atlas()
    uv = atlas.index_uv(np.where(is_dot, 0, 1))
    pos = np.c_[x, y, z]
    return [Particles(atlas, pos, size, ang, col, uv=uv, blend="add", group="past")]
