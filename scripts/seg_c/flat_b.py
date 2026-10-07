"""副歌一平面版的后半：L12–L14（65.0–75.4 秒），由 flat.py 导入。

前半的长卷停在墙前握花的手上。这里接着往下做：花心的"她"展开成向日葵（"讓她變朵"），花离开手、越过墙头，
飞向墙后远处水池里的北京展览馆，落在塔尖的五角星上（"飛往克里姆林宮的花"）；随后从塔尖跳下，坠落画成物理课本
里的频闪图，"律"字时落水（L13）；镜头越过墙头推向水面、穿过水面进入水下，水下的"中蘇友誼萬歲"横幅在"摔"时
裂开、"碎"时碎成四十块，和"摔碎進溝裡"一起沉进立面脚下的裂沟（L14），画面沉进深水的黑暗里交给下一段。

空间仍然全部是正对镜头的平面，只用 z 区分远近。展览馆在墙后 z = HZ = -26 的一层，按 S_H = 0.45 缩放，水面在
WY = -2；它比墙远得多，所以镜头上升、推进时它移动得慢（多层视差）。镜头要从墙前到展览馆前，必须越过墙头：
这一段的镜头用眼睛位置 (x, y, ze) 描述，ze 可以小于 0（已经越过 z = 0 的墙面）。只要镜头高度 y 始终大于
0.268·ze（竖直视角 30 度时墙头恰好在画面下沿以下的条件），墙在越过之前就已经移出画面下沿，看不到穿模。

水面的画法：镜头在水面以上时，水面以下是一块不透明的倒影（展览馆倒影、夜空、细纹和月光碎光）；镜头在水面
以下时，水面以上换成从水下看到的水面下侧，水面以下透出被淹没的立面、横幅、光柱和悬浮颗粒，整体调色转冷。
"""
import math
import sys
from pathlib import Path

import numpy as np
from scipy.interpolate import PchipInterpolator

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "style"))
sys.path.insert(0, str(HERE.parent / "film"))
import look  # noqa: E402
import plan  # noqa: E402
from plan import T, BAR  # noqa: E402
from engine import Cam, Particles, Plane, Tex, TextPlane, register_material  # noqa: E402
from flatcam import cached, ease, ramp  # noqa: E402

import flower as FL  # noqa: E402

FOV = 30.0
K = 1.0 / (2.0 * math.tan(math.radians(FOV / 2)))

# 与 flat.py 相同的两个量：墙前握花的手的位置与花的缩放
FLOWER_C = np.array([21.0, -7.0])
FL_K = 4.6

# ---------------------------------------------------------------- 展览馆与水面

S_H = 0.45                         # 建筑坐标（spire.py，底边到星顶 80）到长卷坐标的缩放
HX, HZ = 27.0, -26.0               # 建筑对称轴的 x，立面所在的 z
WY = -2.0                          # 水面高度
HY0 = WY - 26.0 * S_H              # 建筑坐标原点（底边中点）的 y：建筑下沉 26，水面以上露出塔楼和尖塔
SEABED_Y = WY - 13.0 * S_H         # 水底
Z_WATER = HZ + 0.5                 # 水面这块平面在立面前面一点
Z_FRONT = HZ + 0.4                 # 塔前的花、残影和字


def hb(bx, by):
    """建筑坐标 → 长卷坐标 (x, y)。"""
    return np.array([HX + bx * S_H, HY0 + by * S_H])


STAR_TOP = hb(0.0, 80.0)
SZ_LAND = 2.3                                          # 花落到星上时的大小（合成贴图的边长）
PERCH = np.array([HX, STAR_TOP[1] + 0.62 * SZ_LAND * 0.5, Z_FRONT - 0.05])

# ---------------------------------------------------------------- 时刻

T_LET = T(12, 0)                   # 讓
T_BLOOM0, T_BLOOM1 = T(12, 1), T(12, 3)
T_FLY, T_LAND = T(12, 4), T(12, -1)
T_JUMP = T(13, 0)                  # 跳
T_SPLASH = BAR(42)                 # 第 42 小节首拍，与"律"几乎同时
V0 = 2.2                           # 起跳时向上的初速度
FALL_DROP = PERCH[1] - WY
_TS = T_SPLASH - T_JUMP
G_FALL = 2 * (FALL_DROP + V0 * _TS) / _TS ** 2
T_CRACK = T(14, 6)                 # 摔
T_SHATTER = T(14, 7)               # 碎
T_END = 4524 / 60                  # 75.4：交给下一段（深水里的暗）

# ---------------------------------------------------------------- 镜头：(时刻, x, y, ze)
# ze 是眼睛的 z；在 z = 0 平面上画面高为 ze / K。插值在 log(ze + 40) 上做，推向远处的展览馆时画面放大的速度均匀。

CAM_KEYS = [
    (65.00, 20.20, -9.00, 9.8 * K),
    (65.40, 20.22, -9.05, 9.7 * K),
    (65.90, 20.32, -8.55, 18.4),
    (66.26, 20.70, -6.70, 19.0),       # 飛：花离开手，镜头开始随花上升
    (67.20, 23.60, 8.80, 13.0),        # 越过墙头：墙已在画面下沿以下，远处的塔楼和尖塔入画
    (68.18, 25.70, 19.10, 3.9),        # 花落在五角星上：星在画面上三分之一处
    (68.60, 25.90, 18.70, 5.6),        # 跳
    (69.70, 26.50, 12.60, 19.5),       # 一边下坠一边后退，坠落的全程进入一幅构图
    (70.40, 26.85, 10.00, 24.4),
    (70.85, 27.00, 7.00, 21.0),        # 落水：看清水花和水面上扩开的字环
    (71.30, 27.10, 4.00, 11.5),        # 推向水花，同时保持在墙头以上
    (71.70, 27.10, 1.60, 3.0),
    (71.88, 27.08, 0.60, -1.0),        # 越过墙面
    (72.35, 27.05, -4.10, -3.0),       # 下降穿过水面
    (73.50, 26.95, -4.50, -3.4),       # 水下：横幅和"沒能抱成一起"
    (74.40, 26.90, -6.40, -3.2),       # 随碎块下沉
    (75.40, 26.90, -9.60, -2.9),
]


def _curves():
    k = np.array(CAM_KEYS)
    return (PchipInterpolator(k[:, 0], k[:, 1]), PchipInterpolator(k[:, 0], k[:, 2]),
            PchipInterpolator(k[:, 0], np.log(k[:, 3] + 40.0)))


def cam_state(t):
    fx, fy, fz = cached("b_cam", _curves)
    tt = min(max(t, CAM_KEYS[0][0]), CAM_KEYS[-1][0])
    return float(fx(tt)), float(fy(tt)), float(np.exp(fz(tt)) - 40.0)


def camera(t):
    x, y, ze = cam_state(t)
    return Cam(eye=(x, y, ze), target=(x, y, ze - 10.0), fov=FOV, near=0.05, far=600.0), ze / K


def H_at(t, z):
    """z 处一个画面高对应的世界长度。"""
    return (cam_state(t)[2] - z) / K


def submerged(t):
    """镜头没入水面的程度：0 在水上，1 在水下，穿过水面的一小段里过渡。"""
    y = cam_state(t)[1]
    return float(ease((WY + 0.25 - y) / 0.5))


# ---------------------------------------------------------------- 材质

register_material("water_flat", """
uniform float wy;
uniform float sub;
uniform sampler2D refl;
uniform vec4 refl_rect;
uniform vec3 sky_hor;
uniform vec3 sky_zen;
uniform vec3 under_col;
vec4 material(vec4 base) {
    vec2 p = v_wpos.xy;
    float t = u_time;
    float wave = 0.035 * sin(p.x * 1.3 + t * 1.7) + 0.02 * sin(p.x * 3.1 - t * 2.3);
    float d = wy + wave - p.y;
    // 水面以上（镜头在水上时）：倒影
    float dd = max(d, 0.0);
    float k = 0.25 + 0.75 * clamp(dd / 7.0, 0.0, 1.0);
    float r1 = vnoise(vec2(p.x * 0.55 + t * 0.10, dd * 2.6 - t * 0.35), 11) - 0.5;
    float r2 = vnoise(vec2(p.x * 1.8 - t * 0.22, dd * 8.0 + t * 0.8), 12) - 0.5;
    vec2 q = vec2(p.x + (r1 * 0.45 + r2 * 0.15) * k, wy + dd * 1.04 + r2 * 0.12 * k);
    vec2 uv = (q - refl_rect.xy) / (refl_rect.zw - refl_rect.xy);
    uv.y = 1.0 - uv.y;
    vec4 R = vec4(0.0);
    if (uv.x > 0.0 && uv.x < 1.0 && uv.y > 0.0 && uv.y < 1.0)
        R = textureLod(refl, uv, 0.8 + dd * 0.35);
    vec3 sky = mix(sky_hor, sky_zen, clamp(dd / 9.0, 0.0, 1.0));
    vec3 c = sky * (1.0 - R.a) + R.rgb;
    float fres = 0.55 + 0.35 * exp(-dd * 0.35);
    c *= fres;
    float glint = smoothstep(0.30, 0.48, r2 + 0.15 * r1) * (0.4 + 0.6 * clamp(1.0 - dd / 10.0, 0.0, 1.0));
    c += vec3(0.30, 0.34, 0.40) * glint * 0.22;
    c += vec3(0.35, 0.40, 0.45) * exp(-dd * dd * 120.0) * step(0.0, d);
    float a_up = smoothstep(-0.015, 0.015, d);
    vec4 above = vec4(c * a_up, a_up);
    // 水面以上（镜头在水下时）：水面下侧，暗青色，细碎的亮纹
    float hh = max(-d, 0.0);
    float n1 = vnoise(vec2(p.x * 1.2 + t * 0.3, hh * 3.0 - t * 0.5), 21);
    float n2 = vnoise(vec2(p.x * 2.7 - t * 0.4, hh * 6.0 + t * 0.6), 22);
    float net = pow(1.0 - abs(n1 - 0.5) * 2.0, 6.0) * 0.6 + pow(1.0 - abs(n2 - 0.5) * 2.0, 8.0) * 0.4;
    vec3 uc = under_col * (0.85 + 0.6 * exp(-hh * 0.6)) + vec3(0.30, 0.45, 0.45) * net * (0.35 + 0.65 * exp(-hh * 0.5));
    uc += vec3(0.5, 0.6, 0.6) * exp(-hh * hh * 60.0);
    float a_dn = smoothstep(-0.015, 0.015, -d);
    vec4 below = vec4(uc * a_dn, a_dn);
    return mix(above, below, sub);
}
""", defaults={"wy": WY, "sub": 0.0, "refl_rect": (0, 0, 1, 1), "sky_hor": (0.11, 0.13, 0.17),
               "sky_zen": (0.035, 0.045, 0.065), "under_col": (0.07, 0.15, 0.16)})

register_material("uw_flat", """
uniform float wy;
uniform vec3 fog_top;
uniform vec3 fog_deep;
uniform float vis;
uniform float tint_k;
vec4 material(vec4 base) {
    float d = max(wy - v_wpos.y, 0.0);
    vec3 fog = mix(fog_top, fog_deep, clamp(d / 8.0, 0.0, 1.0));
    vec3 lit = base.rgb * mix(vec3(1.0), vec3(0.55, 0.88, 0.92), tint_k) * (0.35 + 0.65 * exp(-d * 0.16));
    float f = 1.0 - exp(-v_depth / vis);
    return vec4(mix(lit, fog * base.a, f), base.a);
}
""", defaults={"wy": WY, "fog_top": (0.09, 0.19, 0.20), "fog_deep": (0.012, 0.035, 0.042), "vis": 28.0, "tint_k": 1.0})

register_material("uw_ray", """
uniform float phase;
vec4 material(vec4 base) {
    float s = 0.55 + 0.45 * sin(u_time * 0.9 + phase + v_uv01.y * 2.0);
    float n = vnoise(vec2(v_uv01.x * 3.0 + u_time * 0.15, v_uv01.y * 1.5 - u_time * 0.1), 31);
    return base * s * (0.6 + 0.8 * n);
}
""", defaults={"phase": 0.0})

register_material("uw_bg", """
uniform float wy;
uniform vec3 fog_top;
uniform vec3 fog_deep;
vec4 material(vec4 base) {
    float d = max(wy - v_wpos.y, 0.0);
    vec3 c = mix(fog_top, fog_deep, clamp(d / 8.0, 0.0, 1.0));
    c *= 1.0 - 0.75 * clamp((d - 8.0) / 10.0, 0.0, 1.0);
    float n = vnoise(vec2(v_wpos.x * 0.12 + u_time * 0.04, v_wpos.y * 0.2), 41);
    return vec4(c * (0.85 + 0.3 * n), 1.0);
}
""", defaults={"wy": WY, "fog_top": (0.09, 0.19, 0.20), "fog_deep": (0.012, 0.035, 0.042)})

UW = {"wy": WY, "fog_top": (0.09, 0.19, 0.20), "fog_deep": (0.012, 0.035, 0.042), "vis": 28.0, "tint_k": 1.0}


def warm(k=1.15):
    return tuple(np.array(look.C["warm"]) * k)


# ---------------------------------------------------------------- 展览馆

TOWER_REGION = (-8.0, 26.0, 8.5, 50.0)       # 塔楼段：镜头贴近时按每单位 120 像素重画


def hall_tex():
    def make():
        import spire as SP
        from scipy.ndimage import maximum_filter, minimum_filter
        crack = SP.banner_cracks(40, 0)
        c = np.zeros(crack["lines"].shape + (4,), np.float32)
        c[..., 0], c[..., 1], c[..., 3] = maximum_filter(crack["lines"], 9), minimum_filter(crack["time"], 9), 1.0
        night = SP.building_rgba("night", cut_top=True)
        return dict(SP=SP, building=Tex(night), top=Tex(SP.spire_top_rgba("night")),
                    tower=Tex(SP.building_region_rgba(TOWER_REGION, 120, "night")),
                    albedo=Tex(SP.building_rgba("albedo", cut_top=False)),
                    star=Tex(SP.star_rgba("all")), glow=Tex(SP.star_rgba("glow")), banner=Tex(SP.banner_rgba("night")),
                    crack=Tex(c, premultiplied=True), shards=SP.banner_shards(40, 0, "night"),
                    refl=Tex(_reflection(SP), premultiplied=True))
    return cached("b_hall", make)


REFL_BOX = (-16.0, 26.0, 16.0, 82.0)          # 倒影贴图覆盖的建筑坐标范围（水面以上）


def _reflection(SP):
    """倒影用的贴图：水面以上的建筑（含尖塔和五角星的红光），每单位 16 像素，预乘 alpha。"""
    import cv2
    full = SP.building_rgba("night", cut_top=False)
    bx0 = SP.BUILDING["center"][0] - SP.BUILDING["size"][0] / 2
    ppu = full.shape[1] / SP.BUILDING["size"][0]
    x0, y0, x1, y1 = REFL_BOX
    c0, c1 = int((x0 - bx0) * ppu), int((x1 - bx0) * ppu)
    r0, r1 = int((80.0 - min(y1, 80.0)) * ppu), int((80.0 - y0) * ppu)
    crop = full[r0:r1, c0:c1].astype(np.float32)
    pm = np.dstack([crop[..., :3] * crop[..., 3:4], crop[..., 3:4]])
    w, h = int((x1 - x0) * 16), int((min(y1, 80.0) - y0) * 16)
    pm = cv2.resize(pm, (w, h), interpolation=cv2.INTER_AREA)
    pad = int((y1 - 80.0) * 16)
    pm = np.vstack([np.zeros((pad, w, 4), np.float32), pm])
    # 五角星的红光
    yy, xx = np.mgrid[0:pm.shape[0], 0:w].astype(np.float32)
    sx, sy = (0.0 - x0) * 16, (y1 - SP.STAR["center"][1]) * 16
    g = np.exp(-((xx - sx) ** 2 + (yy - sy) ** 2) / (2 * (2.2 * 16) ** 2))
    pm[..., 0] += g * 1.6
    pm[..., 1] += g * 0.35
    pm[..., 2] += g * 0.12
    pm[..., 3] = np.maximum(pm[..., 3], np.clip(g * 1.6, 0, 1))
    return pm


def hall(t):
    if t < 65.9:
        return []
    tx = hall_tex()
    SP = tx["SP"]
    sub = submerged(t)
    items = []
    bw, bh = SP.BUILDING["size"]
    bcx = SP.BUILDING["center"][0]
    # 水上部分：整座建筑（塔尖另画高分辨率贴图），水面这块平面会盖住水面以下的部分
    if sub < 1.0:
        wl = 26.0
        v_wl = (80.0 - wl) / 80.0
        c = hb(bcx, (80.0 + wl) / 2)
        items.append(Plane(tx["building"], center=(*c, HZ), size=(bw * S_H, (80.0 - wl) * S_H), uv=(0, 0, 1, v_wl),
                           group="past", stack="hall"))
        x0, y0, x1, y1 = TOWER_REGION
        items.append(Plane(tx["tower"], center=(*hb((x0 + x1) / 2, (y0 + y1) / 2), HZ),
                           size=((x1 - x0) * S_H, (y1 - y0) * S_H), group="past", stack="hall"))
        for key, d in (("top", SP.SPIRE_TOP), ("star", SP.STAR)):
            items.append(Plane(tx[key], center=(*hb(*d["center"]), HZ), size=tuple(np.array(d["size"]) * S_H),
                               group="past", stack="hall"))
        pulse = 1.0 + 0.08 * math.sin(t * 3.1)
        items.append(Plane(tx["glow"], center=(*hb(*SP.STAR_GLOW["center"]), HZ + 0.01),
                           size=tuple(np.array(SP.STAR_GLOW["size"]) * S_H), blend="add", color=(pulse,) * 3,
                           group="past", stack="hall"))
    # 水下部分：反照率贴图，按水深染色、按距离融进水色
    if sub > 0.0:
        vis0 = 13.0 - 26.0 + 26.0                                  # 建筑坐标里的水底高度：水面 26 往下 13
        vis0 = 26.0 - 13.0
        wl = 26.0
        c = hb(bcx, (wl + vis0) / 2)
        items.append(Plane(tx["albedo"], center=(*c, HZ), size=(bw * S_H, (wl - vis0) * S_H),
                           uv=(0, (80.0 - wl) / 80.0, 1, (80.0 - vis0) / 80.0), color=(0.85, 0.92, 0.95),
                           group="past", material="uw_flat", uniforms=dict(UW, vis=55.0, tint_k=0.8),
                           stack="hall_uw"))
    items += banner(t, sub)
    return items


def banner(t, sub):
    """塔基的横幅：在水面下 0.75–3.45（建筑坐标）。镜头在水上时被水面盖住；在水下时"摔"裂开、"碎"碎开下沉。"""
    if sub <= 0.0 or t < 71.5:
        return []
    tx = hall_tex()
    SP = tx["SP"]
    bc, bs = SP.BANNER["center"], SP.BANNER["size"]
    c = hb(*bc)
    if t < T_SHATTER - 0.05:
        p = ramp(t, T_CRACK - 0.03, T_CRACK + 0.35)
        return [Plane(tx["banner"], center=(*c, HZ + 0.02), size=(bs[0] * S_H, bs[1] * S_H), color=(1.0, 0.95, 0.92),
                      material="banner_crack", uniforms={"crack": tx["crack"], "progress": p}, group="past",
                      stack="hall_uw")]
    items = []
    mo = cached("b_shard_mo", lambda: _shard_motion(tx["shards"], SP))
    t_go = T_SHATTER - 0.05
    for sh, m in zip(tx["shards"], mo):
        td = t_go + 0.22 * sh["t0"]
        dt = max(t - td, 0.0)
        out = (1 - math.exp(-dt / 0.35)) * m["spread"]
        sink = m["sink"] * (1.0 * dt + 2.3 * dt * dt)
        cx, cy = hb(*sh["center"])
        x = cx + m["dir"][0] * out
        y = cy + m["dir"][1] * out * 0.5 - sink
        z = HZ + 0.03 + m["dz"] * (1 - math.exp(-dt / 0.6))
        rot = (18.0 * m["tumble"] * dt, 55.0 * m["tumble"] * dt, 40.0 * m["spin"] * dt)
        items.append(Plane(sh["rgba"], center=(x, y, z), size=(sh["size"][0] * S_H, sh["size"][1] * S_H), rot=rot,
                           color=(1.0, 0.95, 0.92), group="past", material="uw_flat",
                           uniforms=dict(UW, tint_k=0.25, vis=70.0)))
    return items


def _shard_motion(shards, SP):
    rng = np.random.default_rng(5)
    ox, oy = SP._CRACK_ORIGIN
    W, H = SP.BANNER["size"]
    out = []
    for sh in shards:
        cu, cv = sh["centroid"]
        d = np.array([(cu - ox) * W, -(cv - oy) * H])
        d = d / (np.linalg.norm(d) + 1e-6)
        out.append(dict(dir=d * S_H, sink=rng.uniform(0.85, 1.35), dz=rng.uniform(0.3, 2.2), spin=rng.uniform(-1, 1),
                        tumble=rng.uniform(-1, 1), spread=rng.uniform(0.8, 2.2)))
    return out


# ---------------------------------------------------------------- 水面与水下

def water(t):
    if t < 65.9:
        return []
    tx = hall_tex()
    x0, y0, x1, y1 = REFL_BOX
    a, b = hb(x0, y0), hb(x1, y1)
    sub = submerged(t)
    uni = {"wy": WY, "sub": sub, "refl": tx["refl"], "refl_rect": (a[0], a[1], b[0], b[1])}
    items = [Plane(None, center=(HX, WY, Z_WATER), size=(260.0, 160.0), color=(1, 1, 1), material="water_flat",
                   uniforms=uni, group="past")]
    if sub > 0.0:
        items.append(Plane(None, center=(HX, WY - 40.0, HZ - 0.6), size=(260.0, 80.0), material="uw_bg", uniforms=UW,
                           group="past"))
        items += rays(t, sub) + snow(t, sub) + seabed(t) + caustics(t, sub) + sinking_flower(t, sub)
    return items


def ray_tex():
    def make():
        n = 256
        yy, xx = np.mgrid[0:n * 2, 0:n] / np.array([n * 2 - 1, n - 1])[:, None, None]
        a = np.exp(-((xx - 0.5) / 0.16) ** 2) * (1 - yy) ** 1.6 * np.clip(yy * 12, 0, 1)
        return np.dstack([np.ones_like(a)] * 3 + [a]).astype(np.float32)
    return cached("b_ray", make)


def rays(t, sub):
    """月光透过水面的光柱：上端在水面，斜着向下，缓慢摆动、明暗起伏。"""
    rng = np.random.default_rng(9)
    items = []
    for i in range(9):
        x = HX - 16 + i * 4.0 + rng.uniform(-1.2, 1.2)
        w = rng.uniform(1.2, 2.6)
        L = rng.uniform(9, 15)
        ang = -14.0 + 2.5 * math.sin(t * 0.35 + i)
        cx = x + math.sin(math.radians(-ang)) * L / 2
        cy = WY - math.cos(math.radians(ang)) * L / 2
        items.append(Plane(ray_tex(), center=(cx, cy, HZ + 2.0 + 0.3 * i), size=(w, L), rot=(0, 0, ang), blend="add",
                           color=tuple(np.array([0.30, 0.48, 0.48]) * 0.55 * sub), material="uw_ray",
                           uniforms={"phase": float(i * 1.7)}, group="past"))
    return items


def snow(t, sub):
    """水中悬浮的细小颗粒，缓慢漂移，近处的大而虚。"""
    def make():
        rng = np.random.default_rng(13)
        n = 1400
        return rng.uniform([-14, -16, 0], [14, 2, 1], (n, 3)), rng.uniform(0.02, 0.07, n), rng.uniform(0, 6.28, n)
    p0, sz, ph = cached("b_snow", make)
    x, y, ze = cam_state(t)
    P = p0.copy()
    P[:, 0] = HX + ((p0[:, 0] + 0.08 * t + 14) % 28) - 14
    P[:, 1] = WY + ((p0[:, 1] - 0.05 * t + 16) % 18) - 16 + 0.05 * np.sin(t * 0.7 + ph)
    P[:, 2] = HZ + 1.0 + p0[:, 2] * 18.0
    a = 0.35 * sub * np.clip((WY - P[:, 1]) / 1.5, 0, 1)
    col = np.c_[np.full(len(P), 0.55), np.full(len(P), 0.75), np.full(len(P), 0.72), np.ones(len(P))] * a[:, None]
    dot = cached("dot", lambda: __import__("props").dot())
    return [Particles(dot, P, sz * (1 + p0[:, 2] * 1.5), None, col, blend="add", group="past")]


register_material("uw_caustic", """
uniform float wy;
vec4 material(vec4 base) {
    vec2 p = v_wpos.xy;
    float d = max(wy - p.y, 0.0);
    float t = u_time;
    float n1 = vnoise(vec2(p.x * 0.9 + t * 0.25, p.y * 0.9 - t * 0.18), 51);
    float n2 = vnoise(vec2(p.x * 1.6 - t * 0.3, p.y * 1.4 + t * 0.22), 52);
    float net = pow(1.0 - abs(n1 - 0.5) * 2.0, 7.0) + 0.7 * pow(1.0 - abs(n2 - 0.5) * 2.0, 9.0);
    float k = exp(-d * 0.22) * smoothstep(0.0, 0.6, d);
    return vec4(base.rgb * net * k, 0.0);
}
""", defaults={"wy": WY})


def caustics(t, sub):
    """水面晃动的光在被淹没的立面和水底上投下的亮纹（加法叠加）。"""
    return [Plane(None, center=(HX, WY - 9.0, HZ + 0.06), size=(40.0, 18.0), color=(0.10 * sub, 0.17 * sub, 0.17 * sub),
                  blend="add", material="uw_caustic", uniforms={"wy": WY}, group="past"),
            Plane(None, center=(HX, SEABED_Y - 2.0, HZ + 4.05), size=(48.0, 5.0),
                  color=(0.08 * sub, 0.13 * sub, 0.13 * sub), blend="add", material="uw_caustic", uniforms={"wy": WY},
                  group="past")]


def sinking_flower(t, sub):
    """落水的向日葵在水下慢慢下沉、翻转，冒出几串气泡，最后沉进裂沟。"""
    if t < T_SPLASH + 0.3:
        return []
    u = t - T_SPLASH - 0.3
    x = flower_pos(T_SPLASH)[0] + 4.6 * (1 - math.exp(-u / 0.9)) + 0.25 * math.sin(u * 1.1)
    y = WY - 0.8 - 0.95 * u - 0.12 * u * u
    tex = cached("b_head", lambda: Tex(FL.flower_tex()))
    items = [Plane(tex, center=(x, y, HZ + 1.6), size=(SZ_LAND * 0.95,) * 2, rot=(0, 0, -150 - 35 * u),
                   color=(0.70, 0.68, 0.64), group="past", material="uw_flat", uniforms=dict(UW, tint_k=0.6))]
    rng = np.random.default_rng(77)
    n = 40
    birth = rng.uniform(0, 3.0, n)
    age = u - birth
    ok = (age > 0) & (age < 2.2)
    if ok.any():
        bx = x + rng.normal(0, 0.25, n) + 0.08 * np.sin(age * 6 + birth)
        by = y + 0.3 + age * rng.uniform(1.2, 2.2, n)
        ok &= by < WY - 0.1
        P = np.c_[bx, by, np.full(n, HZ + 1.65)][ok]
        a = 0.5 * sub
        col = np.c_[np.full(n, 0.6), np.full(n, 0.8), np.full(n, 0.8), np.ones(n)][ok] * a
        dot = cached("dot", lambda: __import__("props").dot())
        items.append(Particles(dot, P, rng.uniform(0.04, 0.10, n)[ok], None, col, blend="add", group="past"))
    return items


GAP_X = (HX - 4.2, HX + 3.8)            # 裂沟在水底的开口（左右两岸的 x）


def seabed_tex():
    """水底的侧面：岩层与泥沙，开口处向下裂开；开口的两岸是不规则的折线，越往下越窄。"""
    def make():
        import backdrop as BD
        import cv2
        rock = BD.crack_wall_texture()
        W, H = 2048, 1024                       # 覆盖宽 48、高 24
        tile = cv2.resize(np.tile(rock, (1, 3, 1)), (W, int(W / 3 * 1.0)), interpolation=cv2.INTER_AREA)[:H]
        if tile.shape[0] < H:
            tile = np.vstack([tile, tile[: H - tile.shape[0]]])
        ppu = W / 48.0
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        wx = HX - 24.0 + xx / ppu
        depth = yy / ppu
        rng = np.random.default_rng(4)
        jag = np.cumsum(rng.normal(0, 0.25, H)) * 0.12
        jag2 = np.cumsum(rng.normal(0, 0.25, H)) * 0.12
        narrow = np.clip(1 - depth / 16.0, 0.12, 1) ** 0.8
        mid = (GAP_X[0] + GAP_X[1]) / 2 + 0.3 * np.sin(depth * 0.6)
        half = (GAP_X[1] - GAP_X[0]) / 2 * narrow
        left = mid - half + jag[:, None] * 0 + jag[yy.astype(int)]
        right = mid + half + jag2[yy.astype(int)]
        inside = (wx > left) & (wx < right)
        edge = np.minimum(np.abs(wx - left), np.abs(wx - right))
        a = np.where(inside, 0.0, 1.0) * np.clip(depth / 0.05, 0, 1)
        top = 0.25 * np.sin(wx * 0.9) + 0.18 * np.sin(wx * 2.3 + 1)
        a *= (depth > (0.15 + top * 0.3)).astype(np.float32)
        shade = (0.55 + 0.45 * np.exp(-depth / 2.5)) * (1 - 0.5 * np.exp(-edge / 0.25) * (~inside))
        col = tile * shade[..., None] * np.array([0.6, 0.85, 0.85]) * 2.0
        col *= np.exp(-depth / 9.0)[..., None]
        col += np.array([0.20, 0.28, 0.27]) * np.exp(-np.maximum(depth - top * 0.3 - 0.15, 0) / 0.35)[..., None] * (~inside)[..., None]
        return np.dstack([col, a]).astype(np.float32)
    return cached("b_seabed", make)


def gap_tex():
    def make():
        h, w = 512, 256
        yy, xx = np.mgrid[0:h, 0:w] / np.array([h - 1, w - 1])[:, None, None]
        a = np.clip(yy * 24.0 / 2.5, 0, 1) * np.exp(-((xx - 0.5) / 0.42) ** 6)
        return np.dstack([np.zeros_like(a)] * 3 + [a]).astype(np.float32)
    return cached("b_gap", make)


def seabed(t):
    tex = seabed_tex()
    gap = Plane(gap_tex(), center=((GAP_X[0] + GAP_X[1]) / 2, SEABED_Y - 12.0, HZ - 0.3), size=(12.0, 24.0),
                color=(0.004, 0.010, 0.013), group="past")
    items = [Plane(tex, center=(HX, SEABED_Y - 12.0, HZ + 4.0), size=(48.0, 24.0), color=(1, 1, 1), group="past",
                   material="uw_flat", uniforms=dict(UW, tint_k=0.3, vis=60.0)), gap]
    return items


# ---------------------------------------------------------------- 花：展开、起飞、落在星上、坠落

def flower_light(t):
    base = np.array([0.74, 0.72, 0.70]) + np.array([1.0, 0.52, 0.2]) * 0.10
    p = flower_pos(t)
    near = math.exp(-np.hypot(p[0] - PERCH[0], p[1] - PERCH[1]) / 3.5) if t > T_FLY else 0.0
    return base + np.array([1.0, 0.25, 0.12]) * 0.45 * near


def bloom_u(t):
    return float(1 - (1 - ramp(t, T_BLOOM0, T_BLOOM1)) ** 3)


def flight(t):
    """起飞到落在星上：(位置, 合成贴图边长)。位置沿一条向上拱起的弧线，起落都缓。"""
    s = ramp(t, T_FLY, T_LAND)
    s = s ** 3 * (10 - 15 * s + 6 * s * s)
    p0 = np.array([FLOWER_C[0], FLOWER_C[1], 0.42])
    p = p0 * (1 - s) + PERCH * s
    p[1] += 3.2 * math.sin(math.pi * s) * (1 - 0.3 * s)
    # 先竖直升过墙头，再向远处飞去：z 在花高过墙头之后才开始减小
    p[2] = 0.42 + (PERCH[2] - 0.42) * float(ease(ramp(p[1], 0.8, PERCH[1] - 3.0)))
    size = FL_K * (1 - s) + SZ_LAND * s
    return p, size


def flower_pos(t):
    if t < T_FLY:
        return np.array([FLOWER_C[0], FLOWER_C[1], 0.42])
    if t < T_LAND:
        return flight(t)[0]
    if t < T_JUMP:
        return PERCH.copy()
    tau = min(t, T_SPLASH + 0.6) - T_JUMP
    y = PERCH[1] + V0 * tau - 0.5 * G_FALL * tau * tau
    return np.array([PERCH[0] + 2.4 * (1 - math.exp(-tau / 0.5)), y, PERCH[2]])


def flower_size(t):
    if t < T_FLY:
        return FL_K
    if t < T_LAND:
        return flight(t)[1]
    return SZ_LAND


def flower_spin(t):
    if t < T_FLY:
        return 0.0
    if t < T_LAND:
        s = ramp(t, T_FLY, T_LAND)
        return 25.0 * math.sin(math.pi * s) * (1 - s)
    if t < T_JUMP:
        return 0.0
    return -140.0 * (t - T_JUMP) ** 1.4


def head_items(t):
    """飞行和坠落中的花：一整张合成贴图。"""
    if t < T_FLY or t > T_SPLASH + 0.15:
        return []
    tex = cached("b_head", lambda: Tex(FL.flower_tex()))
    p, s = flower_pos(t), flower_size(t)
    glow = 1.0 + (0.6 * math.exp(-(t - T_LAND) / 0.4) if t >= T_LAND else 0.0)
    return [Plane(tex, center=tuple(p), size=(s, s), rot=(0, 0, flower_spin(t)), color=tuple(flower_light(t) * glow),
                  group="past")]


def stem_items(t):
    """花飞走以后，扌仍握着那根空茎。"""
    if t < T_FLY or t > 68.0:
        return []
    g = FL.stem_geometry()
    c = np.array([FLOWER_C[0], FLOWER_C[1]]) + np.array(g["center"]) * FL_K
    tex = cached("b_stem", lambda: Tex(FL.stem_tex()))
    col = np.array([0.74, 0.72, 0.70]) * 1.05
    return [Plane(tex, center=(c[0], c[1], 0.42 + g["z"] * FL_K), size=tuple(np.array(g["size"]) * FL_K),
                  color=tuple(col), group="past", stack="flower")]


GHOST_T = [BAR(41, b) for b in (1, 2, 3, 4)]


def strobe(t):
    """频闪：坠落中每一拍留下一个残影，残影间距按自由落体逐拍拉大，像物理课本里的频闪照片。"""
    if t < GHOST_T[0] or t > 72.0:
        return []
    tex = cached("b_head", lambda: Tex(FL.flower_tex()))
    items = []
    fade_all = 1.0 - ramp(t, 71.0, 71.8)
    for tk in GHOST_T:
        if t < tk:
            continue
        p = flower_pos(tk)
        a = 0.62 * math.exp(-(t - tk) / 3.0) * fade_all
        flash = 0.5 * math.exp(-(t - tk) / 0.12)
        items.append(Plane(tex, center=(p[0], p[1], p[2] - 0.01), size=(SZ_LAND, SZ_LAND), rot=(0, 0, flower_spin(tk)),
                           color=tuple(flower_light(tk) * (0.85 + flash)), opacity=a, group="past"))
    return items


# ---------------------------------------------------------------- 落水

def ring_tex():
    """水面上扩开的一圈波纹（细的亮环，平躺在水面上，按斜看压扁）。"""
    def make():
        n = 512
        yy, xx = np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1
        r = np.hypot(xx, yy)
        a = np.exp(-((r - 0.92) / 0.025) ** 2) + 0.35 * np.exp(-((r - 0.84) / 0.04) ** 2)
        return np.dstack([np.ones_like(a)] * 3 + [np.clip(a, 0, 1)]).astype(np.float32)
    return cached("b_ringtex", make)


def _jet_tex():
    n = 256
    yy, xx = np.mgrid[0:n * 2, 0:n] / np.array([n * 2 - 1, n - 1])[:, None, None]
    a = np.exp(-((xx - 0.5) / 0.22) ** 2) * np.clip(yy * 6, 0, 1) * (0.5 + 0.5 * yy)
    return np.dstack([np.ones_like(a)] * 3 + [a]).astype(np.float32)


def splash(t):
    """落水：一圈冠状的水花溅起再落回，水面中心随后冒起一股水柱；波纹和红色旧字的字环在水面上扩开。"""
    if t < T_SPLASH - 0.02 or t > 73.5 or submerged(t) >= 1.0:
        return []
    u = t - T_SPLASH
    items = []
    x0 = flower_pos(T_SPLASH)[0]
    zc = Z_WATER + 0.15
    dot = cached("dot", lambda: __import__("props").dot())
    soft = cached("soft", lambda: __import__("props").soft_dot(256))
    if u >= 0:
        # 落水那一下的白光
        f = math.exp(-u / 0.09)
        if f > 0.01:
            items.append(Plane(soft, center=(x0, WY + 0.15, zc), size=(3.2, 1.6), blend="add",
                               color=(0.9 * f, 0.95 * f, 1.0 * f), group="past"))
        # 冠状水花：水珠沿速度方向拉长
        rng = np.random.default_rng(42)
        n = 260
        ang = math.pi / 2 + rng.normal(0, 0.55, n)
        sp = rng.uniform(4.0, 12.5, n) * (1 - 0.35 * np.abs(np.cos(ang)))
        vx, vy = np.cos(ang) * sp * 0.7, np.sin(ang) * sp
        g = 15.0
        px = x0 + rng.normal(0, 0.18, n) + vx * u
        py = WY + 0.05 + vy * u - 0.5 * g * u * u
        alive = py > WY - 0.05
        if alive.any():
            vyy = vy - g * u
            spd = np.hypot(vx, vyy)
            rot = np.arctan2(vyy, vx) - math.pi / 2
            P = np.c_[px, py, np.full(n, zc)][alive]
            a = np.clip(1.15 - u / 1.2, 0, 1)
            w = rng.uniform(0.07, 0.19, n)
            sz = np.c_[w, w * (1 + np.clip(spd * 0.06, 0, 1.8))][alive]
            col = np.c_[np.full(n, 0.85), np.full(n, 0.92), np.full(n, 0.98), np.ones(n)][alive] * a * 0.9
            items.append(Particles(dot, P, sz, rot[alive], col, blend="add", group="past"))
        # 水雾
        m = 50
        mx = x0 + rng.normal(0, 0.6, m) * (1 + 1.5 * u)
        my = WY + 0.2 + np.abs(rng.normal(0, 0.5, m)) * (1 + u) + 0.6 * u
        ma = 0.10 * math.exp(-u / 0.8)
        items.append(Particles(dot, np.c_[mx, my, np.full(m, zc - 0.01)], rng.uniform(0.6, 1.4, m) * (1 + u), None,
                               np.c_[np.full(m, 0.7), np.full(m, 0.8), np.full(m, 0.85), np.ones(m)] * ma,
                               blend="add", group="past"))
        # 水柱：落水后约 0.15 秒从中心冒起，升到 2.2 再落回
        uj = u - 0.15
        if 0 < uj < 0.9:
            hgt = max(3.2 * math.sin(math.pi * uj / 0.9), 0.0)
            if hgt > 0.05:
                items.append(Plane(cached("b_jet", _jet_tex), center=(x0, WY + hgt / 2, zc + 0.01), size=(0.45, hgt),
                                   blend="add", color=(0.85, 0.95, 1.0), group="past"))
        # 波纹：几道亮环平躺在水面上扩开
        for j in range(4):
            uu = u - j * 0.16
            if uu <= 0:
                continue
            r = 0.5 + 3.4 * uu ** 0.65
            op = 0.55 * math.exp(-uu / 1.4)
            items.append(Plane(ring_tex(), center=(x0, WY + 0.01, Z_WATER + 0.05), size=(2 * r, 2 * r), rot=(0, -84, 0),
                               blend="add", color=(0.5 * op, 0.58 * op, 0.65 * op), group="past", stack="b_ring"))
    # 同心字环：红色仿宋的旧字排成的圆环在水面上扩开
    ring = cached("b_ring", lambda: look.trad("不管風吹浪打　勝似閒庭信步　"))
    for j in range(2):
        uu = u - 0.1 - j * 0.3
        if uu <= 0:
            continue
        r = 0.9 + 3.6 * uu ** 0.7
        op = 0.95 * math.exp(-uu / 2.4) * (1 - 0.3 * j)
        n_ch = max(10, int(2 * math.pi * r / 0.85))
        for i in range(n_ch):
            ch = ring[i % len(ring)]
            if ch == "　":
                continue
            a = 2 * math.pi * i / n_ch + 0.4 * j + 0.15 * uu
            c = (x0 + r * math.cos(a), WY + 0.03, Z_WATER + 0.06 + r * math.sin(a))
            items.append(TextPlane(ch, kind="fang", height=0.72, color=tuple(look.C["red"] * 1.45), center=c,
                                   rot=(-math.degrees(a) - 90, -90, 0), group="past", opacity=op, stack="b_ring"))
    return items


# ---------------------------------------------------------------- 歌词

def lyric_l12(t):
    """讓她變朵：以花心的"她"为中心，花瓣展开时把两边的字推开；起飞后"飛往"写在花离开的位置；
    "克里姆林宮的花"竖排在花的左侧、随花一起飞，落定后停在尖塔左边。"""
    items = []
    if T_LET - 0.1 <= t <= T_FLY + 0.6:
        text = look.trad(look.lyric(12).replace("　", ""))
        on = plan._CHARS[11]
        u = bloom_u(t)
        G, h = 1.15, 0.95
        gap = G + (2.75 - G) * u
        op = 1.0 - float(ease(ramp(t, T_FLY - 0.17, T_FLY + 0.02)))
        for ch, tc, dx in zip(text[:4], on[:4], (-gap, None, gap, gap + G)):
            if dx is None or t < tc - 0.02 or op <= 0:
                continue
            items.append(TextPlane(ch, kind="serif", weight=700, height=h, color=warm(), group="past",
                                   center=(FLOWER_C[0] + dx, FLOWER_C[1], 0.42),
                                   opacity=op * float(ease((t - tc + 0.02) / 0.1))))
        op2 = 1.0 - float(ease(ramp(t, T_FLY + 0.35, T_FLY + 0.6)))
        for ch, tc, dx in zip(text[4:6], on[4:6], (2.1, 2.1 + G)):
            if t >= tc - 0.02:
                items.append(TextPlane(ch, kind="serif", weight=700, height=h, color=warm(), group="past",
                                       center=(FLOWER_C[0] + dx, FLOWER_C[1] + 0.5, 0.42),
                                       opacity=op2 * float(ease((t - tc + 0.02) / 0.1))))
    t6 = T(12, 6)
    if t6 - 0.1 <= t <= 69.4:
        text = look.trad(look.lyric(12).split("　")[2])
        on = plan._CHARS[11][-len(text):]
        op = 1.0 - float(ease(ramp(t, 68.9, 69.4)))
        for i, (ch, tc) in enumerate(zip(text, on)):
            if t < tc - 0.02:
                continue
            tl = min(t - 0.05 * i, T_LAND) if t < T_LAND + 0.5 else T_LAND
            p, s = flower_pos(tl), flower_size(tl)
            hmin = 75.0 / 1080.0 * H_at(t, p[2])
            h = min(max(0.62 * s, hmin, 1.25), 1.6)
            c = (p[0] - 0.55 * s - 0.75 * h, p[1] + 0.35 * s - (i + 0.5) * h * 1.06, p[2] + 0.01)
            items.append(TextPlane(ch, kind="serif", weight=700, height=h, color=warm(), group="past", center=c,
                                   opacity=op * float(ease((t - tc + 0.02) / 0.12))))
    return items


def lyric_l13(t):
    items = []
    if T_JUMP - 0.1 <= t <= 71.4:
        text = look.trad(look.lyric(13).split("　")[0])
        on = plan._CHARS[12][:len(text)]
        op = 1.0 - float(ease(ramp(t, 70.9, 71.4)))
        h = 1.9
        for i, (ch, tc) in enumerate(zip(text, on)):
            if t < tc - 0.02:
                continue
            items.append(TextPlane(ch, kind="serif", weight=700, height=h, color=warm(), group="past",
                                   center=(HX + 5.4, STAR_TOP[1] + 0.6 - (i + 0.5) * h * 1.06, Z_FRONT),
                                   opacity=op * float(ease((t - tc + 0.02) / 0.1))))
        # "在自然規律"：每个字立在唱出那一刻花所在的高度
        text2 = look.trad(look.lyric(13).split("　")[1])
        on2 = plan._CHARS[12][len(text):]
        prev_y = None
        for ch, tc in zip(text2, on2):
            if tc > T_SPLASH + 0.05 or t < tc - 0.02:
                continue
            y = max(flower_pos(tc)[1], WY + 1.3)
            if prev_y is not None:
                y = min(y, prev_y - 2.4)
            prev_y = y
            items.append(TextPlane(ch, kind="serif", weight=700, height=2.2, color=warm(), group="past",
                                   center=(HX - 2.7, y, Z_FRONT), opacity=op * float(ease((t - tc + 0.02) / 0.1))))
    # "的作用下"浮在水面上，随水波轻轻起伏，水里有它们的倒影
    text3 = look.trad(look.lyric(13).split("　")[1])
    on3 = plan._CHARS[12][-len(text3):]
    if 70.9 <= t <= 72.3:
        op = 1.0 - float(ease(ramp(t, 71.95, 72.25)))
        k = 0
        x0 = flower_pos(T_SPLASH)[0]
        for ch, tc in zip(text3, on3):
            if tc <= T_SPLASH + 0.05:
                continue
            if t >= tc - 0.02:
                bob = 0.06 * math.sin(t * 4.0 + k * 1.3)
                a = op * float(ease((t - tc + 0.02) / 0.12))
                c = (x0 + 1.3 + 1.45 * k, WY + 0.62 + bob, Z_WATER + 0.12)
                items.append(TextPlane(ch, kind="serif", weight=700, height=1.25, color=warm(), group="past", center=c,
                                       opacity=a))
            k += 1
    return items


def lyric_l14(t):
    items = []
    if t < T(14, 0) - 0.05:
        return items
    text = look.trad(look.lyric(14).split("　")[0])
    on = plan._CHARS[13][:len(text)]
    z = -18.0
    h, g = 0.82, 0.98
    base_x = HX - 0.3 - g * (len(text) - 1) / 2
    y0 = -6.15 + 0.06 * math.sin(t * 1.6)
    fade = 1.0 - float(ease(ramp(t, T_CRACK + 0.05, T_SHATTER + 0.2)))
    col = (1.05, 1.02, 0.92)
    k_bao = text.index("抱")
    for i, (ch, tc) in enumerate(zip(text, on)):
        if t < tc - 0.02:
            continue
        op = float(ease((t - tc + 0.02) / 0.15)) * fade
        sep_all = float(ease((t - on[k_bao] - 0.15) / 1.8)) * 0.35 if t > on[k_bao] else 0.0
        shift = -sep_all if i < k_bao else (sep_all if i > k_bao else 0.0)
        c = np.array([base_x + i * g + shift, y0 + 0.03 * math.sin(t * 1.3 + i), z])
        if i == k_bao:
            sep = float(ease((t - tc - 0.1) / 1.8)) * 0.42
            items.append(TextPlane("扌", kind="serif", weight=700, height=h, color=col, group="past", opacity=op,
                                   center=tuple(c + [-0.17 - sep, 0.05 * sep, 0]), rot=(0, 0, 7 * sep),
                                   material="uw_flat", uniforms=dict(UW, tint_k=0.25, vis=60.0)))
            items.append(TextPlane("包", kind="serif", weight=700, height=h, color=col, group="past", opacity=op,
                                   center=tuple(c + [0.14 + sep, -0.07 * sep, 0]), rot=(0, 0, -6 * sep),
                                   material="uw_flat", uniforms=dict(UW, tint_k=0.25, vis=60.0)))
            continue
        items.append(TextPlane(ch, kind="serif", weight=700, height=h, color=col, group="past", opacity=op, center=tuple(c),
                               material="uw_flat", uniforms=dict(UW, tint_k=0.25, vis=60.0)))
    # "摔碎進溝裡"：从横幅裂开处出现，"碎"以后随碎块沉进裂沟（在水底那一层之后，只在开口里看得到）
    text2 = look.trad(look.lyric(14).split("　")[1])
    on2 = plan._CHARS[13][len(text):]
    mid = (GAP_X[0] + GAP_X[1]) / 2
    by = hb(0, 26.0 - 2.1)[1]                       # 横幅中线
    for i, (ch, tc) in enumerate(zip(text2, on2)):
        if t < tc - 0.02:
            continue
        dt = max(t - max(tc, T_SHATTER), 0.0)
        sink = 0.9 * dt + 2.1 * dt * dt
        narrow = 1.0 - 0.2 * min(dt / 1.2, 1.0)
        cx = mid + (i - 2) * 1.25 * narrow
        c = (cx, by - 1.35 - sink - 0.12 * i * min(dt, 1.0), HZ + 1.2)
        items.append(TextPlane(ch, kind="serif", weight=700, height=0.92, color=col, group="past",
                               center=c, rot=(0, 0, (i - 2) * 6.0 * min(dt, 1.0)),
                               opacity=float(ease((t - tc + 0.02) / 0.12)),
                               material="uw_flat", uniforms=dict(UW, tint_k=0.25, vis=60.0)))
    return items


# ---------------------------------------------------------------- 调色

def grade(t, base):
    """水下时调色转冷：去掉过去调色里的暖黄，降低光晕。"""
    sub = submerged(t)
    if sub <= 0:
        return base
    g = {k: dict(v) for k, v in base.items()}
    p = g.setdefault("past", {})
    w0 = np.array([1.06, 0.97, 0.80])
    w1 = np.array([0.95, 1.0, 0.97])
    p["warmth"] = tuple(w0 * (1 - sub) + w1 * sub)
    p["halation"] = p.get("halation", 1.2) * (1 - 0.5 * sub)
    if t > 74.95:
        g["final"] = {"fade": float(ease(ramp(t, 74.95, T_END - 1 / 60))), "fade_color": (0.006, 0.014, 0.020)}
    return g


SCENES = [hall, water, head_items, stem_items, strobe, splash, lyric_l12, lyric_l13, lyric_l14]
