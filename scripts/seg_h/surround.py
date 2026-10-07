"""翻板场脚下的地面、照明灯的定义、空气里的灰尘，以及 L33 漆面上的灰。

场地铺在一座夜里的旧体育场中央，四周依次是踩实的土地（场地边缘一圈白灰线）和六条道的煤渣跑道（暗红褐色，
白灰画的分道线）；跑道外的看台、灯塔、光束和夜空在 stadium.py。四角的照明灯是聚光灯，近端左角的灯坏了，光主要
从远端两角斜照过来，几个光池在场地上交叠，光池之间和场地四周暗下去；空气里有几千粒灰尘（"停得住"时停在半空），
镜头贴近 L33 的巨字时，漆面上还有一层灰。

地面的底色用 Poly Haven 的泥土贴图（Charlotte Baglioni，CC0，经 Wikimedia Commons）平铺后调色，跑道在同一张
贴图上着色、画线；光照另存一张照度图，在着色器里相乘，闪电时整体加亮。

坐标与 field.py 相同：场地中心为原点，x 向右、y 向画面上方，地面在 z = 0。
"""
import math

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, zoom

from common import IMG, cached, disk_cached, smooth, T
from engine import Particles, Plane, Tex, register_material, dot_atlas

GW, GH = 820.0, 520.0          # 地面贴图覆盖的范围（世界单位）
PPU = 5.0                      # 每单位的像素数
FIELD_HW, FIELD_HH = 180.0, 75.0
MARGIN = 9.0                   # 场地到跑道内沿的土地
TRACK_W = 20.0                 # 跑道宽
LANES = 6

register_material("h_ground", """
uniform sampler2D lightmap;
uniform float flash;
uniform vec3 flash_col;
uniform float bright;
vec4 material(vec4 base) {
    vec3 L = texture(lightmap, v_uv01).rgb * bright + flash * flash_col;
    return vec4(base.rgb * L, base.a);
}
""", defaults={"flash": 0.0, "flash_col": (0.7, 0.8, 1.0), "bright": 1.0})

# 照明灯：四角灯架顶上的聚光灯组（位置、颜色、相对强度、照向的地点）。远端两角最亮，近端右角较弱，
# 近端左角的灯坏了，只剩很弱的散光；几个光池在场地上互相交叠，光池之间和场地四周暗下去。
LIGHT_POS = [(-236.0, 124.0, 82.0), (236.0, 124.0, 82.0), (-236.0, -124.0, 82.0), (236.0, -124.0, 82.0)]
LIGHT_COL = [(1.0, 0.90, 0.76), (1.0, 0.92, 0.80), (0.9, 0.80, 0.66), (1.0, 0.84, 0.66)]
LIGHT_POW = [1.0, 0.85, 0.08, 0.55]
LIGHT_AIM = [(-45.0, 14.0, 0.0), (70.0, 6.0, 0.0), (-110.0, -50.0, 0.0), (100.0, -44.0, 0.0)]
AMBIENT = (0.035, 0.032, 0.036)


def lights():
    """场地四角的照明灯（cards.Lights）。翻板、地面和灰尘都按它照亮。"""
    import cards as CD
    return cached("h_lights", lambda: CD.Lights(LIGHT_POS, LIGHT_COL, LIGHT_POW, LIGHT_AIM, cone=(0.86, 0.975),
                                                spill=0.10, ambient=AMBIENT, spec=0.5, shininess=36.0))


def _dirt(px_w, px_h, scale, seed):
    """把泥土贴图按 scale（每张贴图覆盖的世界单位）平铺到 px_w × px_h，返回 0–1 的 RGB。"""
    src = np.asarray(Image.open(IMG / "Dirt_diff_8k_Charlotte_Baglioni_via_Poly_Haven_.png").convert("RGB"),
                     np.float32) / 255.0
    n = int(scale * PPU)
    tile = np.asarray(Image.fromarray((src * 255).astype(np.uint8)).resize((n, n), Image.LANCZOS), np.float32) / 255
    rng = np.random.default_rng(seed)
    out = np.zeros((px_h, px_w, 3), np.float32)
    for y0 in range(0, px_h, n):
        for x0 in range(0, px_w, n):
            t = np.rot90(tile, rng.integers(4))
            h, w = min(n, px_h - y0), min(n, px_w - x0)
            out[y0:y0 + h, x0:x0 + w] = t[:h, :w]
    # 平铺的接缝用大尺度的明暗起伏盖住
    lo = gaussian_filter(rng.normal(0, 1, (px_h // 16 + 2, px_w // 16 + 2)), 3.0)
    lo = zoom(lo / (lo.std() + 1e-6), 16, order=1)[:px_h, :px_w]
    return out * (1.0 + 0.10 * lo[..., None])


def _albedo():
    W, H = int(GW * PPU), int(GH * PPU)
    yy, xx = np.mgrid[0:H, 0:W]
    X = (xx + 0.5) / PPU - GW / 2
    Y = GH / 2 - (yy + 0.5) / PPU
    dirt = _dirt(W, H, 60.0, 5)
    lum = dirt.mean(2, keepdims=True)
    rng = np.random.default_rng(9)
    # 土地：褪色的灰褐
    earth = lum * np.array([1.05, 0.92, 0.78]) * 0.95 + (dirt - lum) * 0.5
    # 场地底下：被板子遮着、踩得更实，颜色更暗
    ax, ay = np.abs(X), np.abs(Y)
    in_field = (ax < FIELD_HW + 0.6) & (ay < FIELD_HH + 0.6)
    # 跑道：内沿为圆角矩形
    ix, iy = FIELD_HW + MARGIN, FIELD_HH + MARGIN
    rc = 26.0
    qx, qy = np.clip(ax - (ix - rc), 0, None), np.clip(ay - (iy - rc), 0, None)
    d_in = np.where((ax > ix - rc) & (ay > iy - rc), np.hypot(qx, qy) - rc, np.maximum(ax - ix, ay - iy))
    track = (d_in > 0) & (d_in < TRACK_W)
    cinder = lum * np.array([0.78, 0.48, 0.36]) * 0.9 + (dirt - lum) * 0.35
    cinder *= 1.0 + 0.08 * gaussian_filter(rng.normal(0, 1, (H, W)), 0.7)[..., None]
    alb = np.where(track[..., None], cinder, earth)
    # 分道线与场地边线：白灰画的，断断续续、被踩模糊
    wear0 = gaussian_filter(rng.normal(0, 1, (H, W)), 9.0)
    wear0 = np.clip(0.55 + 0.35 * wear0 / (wear0.std() + 1e-6), 0.1, 0.9)
    grit = np.clip(0.8 + 0.5 * gaussian_filter(rng.normal(0, 1, (H, W)), 0.8), 0, 1)

    def chalk(d, width):
        a = np.clip(1.0 - np.abs(d) / width, 0, 1)
        return a * wear0 * grit
    lines = np.zeros((H, W), np.float32)
    for k in range(LANES + 1):
        lines = np.maximum(lines, chalk(d_in - k * TRACK_W / LANES, 0.28))
    d_field = np.maximum(ax - (FIELD_HW + 3.5), ay - (FIELD_HH + 3.5))
    d_field = np.where((ax > FIELD_HW + 3.5) & (ay > FIELD_HH + 3.5),
                       np.hypot(ax - FIELD_HW - 3.5, ay - FIELD_HH - 3.5), d_field)
    lines = np.maximum(lines, chalk(d_field, 0.45))
    alb = alb * (1 - 0.85 * lines[..., None]) + np.array([0.86, 0.84, 0.78]) * 0.85 * lines[..., None]
    # 看台：跑道外沿以外是水泥台阶（一级 1.6 单位：踏面亮、立面暗），中间留出入口
    d_out = d_in - TRACK_W
    stand = d_out > 3.0
    curb = (d_out > 0) & (d_out <= 3.0)
    step = np.mod(d_out - 3.0, 1.6) / 1.6
    tread = np.where(step < 0.62, 1.0, 0.55)
    conc = lum * np.array([0.92, 0.90, 0.86]) * 0.9 * tread[..., None]
    conc *= 1.0 + 0.12 * gaussian_filter(rng.normal(0, 1, (H, W)), (1.0, 1.0))[..., None]
    alb = np.where(stand[..., None], conc, alb)
    alb = np.where(curb[..., None], lum * np.array([1.0, 0.97, 0.9]) * 1.15, alb)
    # 场地下面压暗
    alb = np.where(in_field[..., None], alb * 0.85, alb)
    return np.clip(alb, 0, 1).astype(np.float32)


DOORS = []                    # 看台入口透出的光（三维看台上没有画入口，不用）


def _lightmap():
    """地面的照度（RGB）：四角照明灯的光池 + 看台入口透出的暖光。"""
    W, H = int(GW * PPU / 4), int(GH * PPU / 4)
    yy, xx = np.mgrid[0:H, 0:W]
    X = (xx + 0.5) / (PPU / 4) - GW / 2
    Y = GH / 2 - (yy + 0.5) / (PPU / 4)
    P = np.stack([X.ravel(), Y.ravel(), np.zeros(X.size)], 1).astype(np.float32)
    out = np.concatenate([lights().irradiance(P[i:i + 200000]) for i in range(0, len(P), 200000)])
    out = out.reshape(H, W, 3).astype(np.float32)
    # 看台入口：门洞里的暖光照亮门前一片扇形
    iy = FIELD_HH + MARGIN + TRACK_W + 3.0
    for x0, s in DOORS:
        dx, dy = X - x0, (Y - s * (iy + 6.0)) * -s
        r = np.hypot(dx, dy)
        fan = np.clip(dy / (r + 1e-6), 0, 1) ** 2 * np.exp(-r / 22.0) * (dy > -1.0)
        core = np.exp(-((dx / 3.5) ** 2 + ((dy + 2.0) / 2.0) ** 2))
        out += np.array([1.0, 0.72, 0.42]) * (0.55 * fan + 1.6 * core)[..., None]
    return gaussian_filter(out, (1.5, 1.5, 0)).astype(np.float32)


def ground_tex():
    def make():
        alb = disk_cached("ground_albedo", _albedo, "v3")
        lm = disk_cached("ground_light", _lightmap, "v7")
        return Tex(alb), Tex(lm)
    return cached("ground_tex", make)


def ground(t, flash=0.0, bright=1.0):
    alb, lm = ground_tex()
    return [Plane(alb, center=(0.0, 0.0, 0.0), size=(GW, GH), group="past", material="h_ground",
                  uniforms={"lightmap": lm, "flash": flash, "bright": bright}, bias=5.0e4)]


# ---------------------------------------------------------------- 空气里的灰尘

N_DUST = 7000


def dust_layout():
    def make():
        rng = np.random.default_rng(77)
        n = N_DUST
        # 灰尘分布在场地上方一个扁的空间里，越低越密
        x = rng.uniform(-200, 200, n)
        y = rng.uniform(-95, 95, n)
        z = 1.5 + rng.exponential(13.0, n).clip(0, 70)
        size = rng.lognormal(np.log(0.05), 0.4, n).clip(0.02, 0.16)
        ph = rng.uniform(0, 2 * np.pi, (n, 3))
        fr = rng.uniform(0.15, 0.45, (n, 3))
        b = rng.uniform(0.25, 1.0, n)
        return np.c_[x, y, z], size, ph, fr, b
    return cached("h_dust", make)


def dust_time(t):
    """灰尘的时间：平时与 t 相同；"停得住"时在 0.2 秒里慢下来、停在半空，镜头升起时再缓缓动起来。
    做法是对速度系数 s(t) 积分：s 平时为 1，"停"之前降到 0，167.5 秒后在 0.8 秒里回到 1。"""
    import field as FD

    def make():
        ts = np.arange(150.0, 200.0, 0.002)
        s = 1.0 - smooth(ts, FD.T_STOP - 0.2, FD.T_STOP) + smooth(ts, 167.5, 168.3)
        tau = np.cumsum(s) * 0.002 + 150.0
        return ts, tau
    ts, tau = cached("h_dust_tau", make)
    return float(np.interp(t, ts, tau))


def dust_items(t, cam, light_fn, aperture=0.5):
    """空气里的灰尘。cam 为当前镜头（裁掉视锥以外的灰尘）；light_fn(P) 给出每粒灰尘处的光强。
    镜头对焦在目标点上：离焦平面越远的灰尘越虚，画成更大、更淡的光斑（薄透镜的弥散圆，总亮度不变）。"""
    P0, size, ph, fr, b = dust_layout()
    tau = dust_time(t)
    drift = np.c_[0.35 * np.sin(fr[:, 0] * tau + ph[:, 0]),
                  0.30 * np.sin(fr[:, 1] * tau + ph[:, 1]),
                  0.20 * np.sin(fr[:, 2] * tau + ph[:, 2]) - 0.05 * (tau - 160.0)]
    P = P0 + drift
    eye = np.asarray(cam.eye, np.float64)
    r, u, f = (np.asarray(v, np.float64) for v in cam.basis())
    v = P - eye[None]
    D = v @ f
    keep = (D > 1.0) & (np.abs(v @ r) < D * 0.50 + 2) & (np.abs(v @ u) < D * 0.29 + 2)
    df = float(eye[2] / -f[2]) if f[2] < -0.05 else float(np.linalg.norm(np.asarray(cam.target) - eye))   # 对焦在地面上
    coc = aperture * np.abs(D - df) / df
    eff = np.sqrt(size ** 2 + coc ** 2)
    px = eff / (np.maximum(D, 1e-3) * 0.536) * 1080.0       # 画面上的直径（像素）
    keep &= (px > 1.2) & (px < 160)
    P, eff, b, sz = P[keep], eff[keep], b[keep], size[keep]
    if len(P) == 0:
        return []
    lit = light_fn(P) * b * np.clip((sz / eff) ** 2, 0.03, 1.0) * 1.6
    col = np.c_[lit[:, None] * np.array([1.0, 0.88, 0.70]), np.ones(len(P))].astype(np.float32)
    dot = cached("h_dot", lambda: dot_atlas(64, 0.55))
    return [Particles(dot, P.astype(np.float32), eff.astype(np.float32), None, col, blend="add", group="past",
                      bias=-1.5e4)]


# ---------------------------------------------------------------- L33：漆面上的灰与刷痕

GRIME_C = (-133.0, -39.0)
GRIME_S = (150.0, 90.0)


def _grime():
    """L33 镜头贴近时盖在板面上的一层灰与刷痕（正片叠底）：泥土贴图的细节做灰，加上沿横向的长刷痕和几道
    鞋底蹭出的暗痕。只在板拼成一整片地面时用，涟漪荡过之前淡出。"""
    ppu = 14
    W, H = int(GRIME_S[0] * ppu), int(GRIME_S[1] * ppu)
    rng = np.random.default_rng(41)
    d = _dirt(W, H, 22.0, 13).mean(2)
    d = (d - gaussian_filter(d, 30)) / (d.std() + 1e-6)
    # 刷痕：一片一片的刷子来回刷过，每片方向略有不同、深浅不一
    streak = np.zeros((H, W))
    for k in range(5):
        sk = gaussian_filter(rng.normal(0, 1, (H, W)), (1.5, rng.uniform(25.0, 60.0)))
        sk /= sk.std() + 1e-6
        patch = gaussian_filter(rng.normal(0, 1, (H // 8 + 2, W // 8 + 2)), 6.0)
        patch = zoom(patch / (patch.std() + 1e-6), 8, order=1)[:H, :W]
        streak += sk * np.clip(patch - 0.3, 0, None)
    streak /= streak.std() + 1e-6
    blot = gaussian_filter(rng.normal(0, 1, (H, W)), 60.0)
    blot /= blot.std() + 1e-6
    v = 0.86 + 0.11 * np.clip(d, -2.5, 2.5) + 0.035 * streak + 0.08 * blot
    yy, xx = np.mgrid[0:H, 0:W]
    for _ in range(14):                                  # 鞋底蹭出的弧形暗痕
        cx, cy, r = rng.uniform(0, W), rng.uniform(0, H), rng.uniform(40, 160)
        a0 = rng.uniform(0, 2 * np.pi)
        rr = np.hypot(xx - cx, yy - cy)
        ang = np.arctan2(yy - cy, xx - cx)
        arc = np.exp(-((rr - r) / rng.uniform(2.0, 5.0)) ** 2) * (np.cos(ang - a0) > 0.6)
        v -= 0.10 * arc * rng.uniform(0.4, 1.0)
    v = np.clip(v, 0.55, 1.05).astype(np.float32)
    # 浮灰：一层发白的灰，一片片、一道道，暗处的地面上看得出来
    film = gaussian_filter(rng.normal(0, 1, (H, W)), 20.0)
    film = np.clip(film / (film.std() + 1e-6) - 0.2, 0, None) * 0.5
    film += np.clip(d - 1.2, 0, None) * 0.35
    for _ in range(40):                                   # 鞋印般的浅色斑块
        cx, cy = rng.uniform(0, W), rng.uniform(0, H)
        rx, ry = rng.uniform(6, 14), rng.uniform(14, 30)
        film += 0.5 * np.exp(-(((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2)) * rng.uniform(0.2, 1.0)
    film = np.clip(film, 0, 1).astype(np.float32)
    return np.dstack([v, v, v, film])


def grime_items(t):
    import field as FD
    k = 1.0 - float(smooth(t, FD.T_SHIVER - 0.05, FD.T_SHIVER + 0.35))
    if k <= 0:
        return []
    def make():
        g = disk_cached("grime", _grime, "v3")
        return Tex(np.ascontiguousarray(g[..., :3])), Tex(np.ascontiguousarray(g[..., 3]))
    mul, film = cached("h_grime", make)
    return [Plane(mul, center=(GRIME_C[0], GRIME_C[1], 0.66), size=GRIME_S, blend="multiply", opacity=k,
                  group="past", stack="grime", bias=-1.0e4),
            Plane(film, center=(GRIME_C[0], GRIME_C[1], 0.661), size=GRIME_S, color=(0.42, 0.39, 0.35),
                  opacity=0.16 * k, group="past", stack="grime", bias=-1.0e4)]
