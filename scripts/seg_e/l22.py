"""L22：沿风筝线上升，穿出水面，一层层过去的画面从上方压下来、向下掠过，最后冲破最上面一层。

第三下底鼓（113.62 秒）时镜头随风筝线穿出水面：水花溅起，镜头上挂着的一层水往下流走，水面上映着月亮的碎光，上方是
云中的月亮。随即一条条层带从上方压下来，每条都是前面某一段画面撕下来的一条，越往上年代越近（层带的做法见 strata.py）。
"萬"（115.29 秒）时层最密；随后四个深度的层带依次扫过画面上部，露出最远处的最后一层：一大张旧纸，纸面与前奏和主歌一
交接处的旧纸相同，上面竖印着褪色红的旧字"換了人間"（构思第八章 L22），放在右边一列歌词之外。它离得远，移动得慢，
从 115.25 秒到撕开之前完整可读约 0.65 秒；近处只有被气流卷着飞过的纸屑，速度仍在增加。115.80 秒起纸从风筝线指着的
地方撕开，冷白的光涌出来，115.97 秒成为冷白（handoff.white_frame）。

歌词"回到從前""那樣　風情萬"竖排在风筝线两旁，跟着镜头一起上升（锁定在画面上），所以在一切向下掠过的画面里
始终读得清——唱的是回到从前，镜头却在离开从前。
"""
import math

import numpy as np
from scipy.ndimage import gaussian_filter

import common  # noqa: F401
import look
import plan
from flatcam import cached, ease, ramp
from engine import Particles, Plane, Tex, TextPlane, dot_atlas, register_material

from water import LINE_X, L22, KICK3, WARM, RED, K, FOV

T_DRUM = plan.BAR(68, 1.5)
T_BURST = 115.97
TOP_Y = 19.6                                     # 冲破时镜头的大致高度


# ---------------------------------------------------------------- 材质

register_material("e_air", """
uniform vec3 w_off;
uniform float sky_up;
vec4 material(vec4 base) {
    vec3 p = v_wpos - w_off, e = u_eye - w_off;
    vec3 d = normalize(p - e);
    float h = clamp(e.y / 19.5, 0.0, 1.0);
    vec3 night = vec3(0.012, 0.018, 0.030);
    vec3 cold = vec3(0.80, 0.86, 0.95);
    float k = pow(h, 2.2) * sky_up;
    vec3 c = mix(night, cold * 0.55, k) * (1.0 + 0.6 * smoothstep(-0.2, 0.3, d.y) * (0.3 + k));
    float n = vnoise(p.xy * 0.12, 81) * 0.5 + vnoise(p.xy * 0.4, 82) * 0.5;
    c *= 0.88 + 0.24 * n;
    return vec4(c, 1.0);
}
""", {"w_off": (0.0, 0.0, 0.0), "sky_up": 1.0})

SKY_PHOTO = "Moon_in_clouds_over_Kolleröd.jpg"


def sky_tex():
    """夜空：W.carter 拍摄的云中的月亮（CC0）。压暗、偏夜蓝，上下两端淡出。"""
    def make():
        from common import load_rgb
        im = load_rgb(SKY_PHOTO, maxdim=2400)
        lum = im @ common.LUMA
        rgb = lum[..., None] + (im - lum[..., None]) * 0.55
        rgb = rgb * np.array([0.66, 0.74, 0.98]) * 0.85
        h, w = rgb.shape[:2]
        v = np.linspace(0, 1, h)[:, None]
        uu = np.linspace(0, 1, w)[None, :]
        a = np.clip(v / 0.25, 0, 1) * np.clip((1 - v) / 0.18, 0, 1) * np.clip(uu / 0.12, 0, 1) * np.clip((1 - uu) / 0.12, 0, 1)
        return np.dstack([rgb, a]).astype(np.float32)
    return cached("sky_tex", lambda: Tex(common.disk_cache("night_sky", make, 3)))


MOON_UV = (0.330, 0.355)                   # 月亮在夜空照片里的位置
MOON_SCREEN = (0.30, 0.37)                 # 刚出水（113.70 秒）时月亮在画面上的位置


def sky_geometry():
    """夜空照片平面的中心与尺寸：z = -16，宽为这一深度画面宽的 1.7 倍，月亮在 113.70 秒落在 MOON_SCREEN。"""
    z = -16.0
    d = 3.0 * K
    S = 3.0 * (d - z) / d
    w = 16 / 9 * S * 1.7
    h = w * 2160 / 3840
    y_cam = 0.25
    mx = LINE_X + (MOON_SCREEN[0] - 0.5) * 16 / 9 * S
    my = y_cam + (0.5 - MOON_SCREEN[1]) * S
    return (mx - (MOON_UV[0] - 0.5) * w, my - (0.5 - MOON_UV[1]) * h, z), (w, h)


def sky_items(t, cam, U):
    x, y, H = cam
    if y <= 0.0 or y > 9.0:                    # 镜头还在水下时看不到水面以上
        return []
    c, size = sky_geometry()
    return [Plane(sky_tex(), center=c, size=size, group="past", bias=90.0)]


FINAL = {"z": -40.0, "bottom": 5.0, "text": (10.0, 20.0), "burst": (0.45, 19.0)}   # 由 scene.configure_final 按镜头算出
TEXT_H = 0.14                              # "換了人間"每个字的高度（画面高的比例）
TEXT_SX = 0.80                             # 竖排的一列放在画面横向 0.80 处：右边一列歌词之外


def configure_final(bottom, text_xy, burst_xy):
    FINAL["bottom"], FINAL["text"], FINAL["burst"] = bottom, text_xy, burst_xy


def final_items(t, cam, U):
    """最后一层：远处一大张旧纸（纸面与 handoff.paper_items 相同：同一张旧纸照片和纤维材质，纤维按距离放大），
    竖印着"換了人間"。
    它的下沿始终藏在层带后面；冷白的光越来越近，纸被照得越来越亮、越来越冷；115.80 秒起从风筝线指着的地方撕开。"""
    import handoff
    x, y, H = cam
    if t < 114.3:
        return []
    z = FINAL["z"]
    d = H * K
    S = H * (d - z) / d
    S_max = 3.0 * (3.0 * K - z) / (3.0 * K)
    fw = 16 / 9 * S_max
    bottom = FINAL["bottom"]
    glow = float(ease(ramp(t, 115.25, T_BURST)))
    burst = float(ease(ramp(t, 115.80, T_BURST)))
    cached("handoff_paper_material", handoff._paper_material)
    col = np.array(handoff.PAPER_COLOR) * (0.80 + 0.40 * glow) * (np.array([1.0, 0.98, 0.95]) * (1 - glow)
                                                                    + np.array([0.94, 0.99, 1.06]) * glow)
    k = S_max / handoff.PAPER_CAM[2]                            # 与前奏的纸相比，这一层远了多少倍：纤维按比例放大
    uni = dict(handoff.PAPER_UNI, fib_tile=handoff.PAPER_UNI["fib_tile"] * k, fibers=handoff.paper_fibers())
    W = fw * 1.4
    size = (W, W / 1.6)                                         # 旧纸照片的宽高比
    center = (LINE_X, bottom + size[1] / 2)
    items = [Plane(handoff.paper_photo(), center=(*center, z), size=size, color=tuple(col), material="handoff_paper",
                   uniforms=uni, group="past", stack="final", bias=150.0)]      # 排在夜空和水面之后画（最远）
    tx, ty = FINAL["text"]
    txt = look.trad("換了人間")
    items.append(TextPlane(txt, kind="fang", weight=400, height=TEXT_H * S_max, vertical=True, valign="top",
                           color=tuple(RED * (1.15 + 0.25 * glow)), center=(tx, ty, z), group="past", stack="final",
                           material="handoff_paper", uniforms=uni))
    if burst > 0:
        bx, by = FINAL["burst"]
        items[0].mask = tear_path(burst, center, size, (bx, by), S)
        items[1].mask = tear_path(burst, None, None, (bx, by), S, text=items[1])
        items += burst_items(t, burst, (bx, by, z - 0.05), S)
    return items


def tear_path(b, center, size, p, Hs, text=None):
    """纸从风筝线指着的地方撕开：一个边缘参差的洞，从一个小口迅速扩大到盖过整个画面。
    返回 skia 路径（平面的 0–1 坐标，路径内部是洞）。text 为文字平面时按它的栅格范围换算，纸上的字和纸一起被撕开。"""
    import skia
    if text is not None:
        c, sz = text.box_geometry()
        center, size = (c[0], c[1]), sz
    rng = np.random.default_rng(41)
    n = 160
    ang = np.linspace(0, 2 * np.pi, n, endpoint=False)
    lobes = gaussian_filter(rng.normal(0, 1, n), 9, mode="wrap")
    lobes = lobes / (np.abs(lobes).max() + 1e-6)
    fib = gaussian_filter(rng.normal(0, 1, n), 0.8, mode="wrap")
    jag = 1.0 + 0.28 * lobes + 0.05 * fib / (np.abs(fib).max() + 1e-6)
    for k in rng.choice(n, 3, replace=False):                     # 三道撕得更长的裂口
        jag += 0.55 * np.exp(-(((np.arange(n) - k + n / 2) % n - n / 2) / 2.2) ** 2)
    r = Hs * (0.02 + 1.25 * b ** 1.8)
    xs = p[0] + np.cos(ang) * r * jag * 1.15
    ys = p[1] + np.sin(ang) * r * jag
    u = (xs - center[0]) / size[0] + 0.5
    v = 0.5 - (ys - center[1]) / size[1]
    path = skia.Path()
    path.moveTo(float(u[0]), float(v[0]))
    for uu, vv in zip(u[1:], v[1:]):
        path.lineTo(float(uu), float(vv))
    path.close()
    return path


def burst_items(t, b, c, Hs):
    """洞后面是冷白的光；洞口一圈被背光照透的纸边发亮。"""
    dot = cached("burst_dot", lambda: Tex(_soft(256, 1.2)))
    white = np.array([0.95, 0.97, 1.0])
    s = Hs * (0.04 + 2.6 * b ** 1.8)
    core = cached("burst_core", lambda: Tex(_soft(256, 0.35)))
    return [Plane(core, center=c, size=(s * 1.5, s * 1.5), color=tuple(white * 1.4), group="past"),
            Plane(dot, center=(c[0], c[1], c[2] + 0.1), size=(s * 1.9, s * 1.9), blend="add",
                  color=tuple(white * (0.8 * b)), group="past")]


def _soft(n, p):
    yy, xx = np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1
    a = np.clip(1 - np.hypot(xx, yy), 0, 1) ** p
    return np.dstack([np.ones((n, n, 3), np.float32), a.astype(np.float32)])


# ---------------------------------------------------------------- 穿出水面时的水花

N_SPLASH = 420


def splash_items(t, cam, U):
    """第三下底鼓时镜头随风筝线穿出水面：线带起一串水珠，水面上溅起一圈水花又落回去。"""
    u = t - KICK3
    if u < -0.02 or u > 1.3:
        return []

    def make():
        rng = np.random.default_rng(13)
        n = N_SPLASH
        ang = rng.uniform(0.35, np.pi - 0.35, n)
        sp = rng.lognormal(np.log(2.6), 0.40, n)
        v = np.c_[np.cos(ang) * sp * 0.9, np.sin(ang) * sp * 1.25]
        x0 = rng.normal(0, 0.06, n)
        z = rng.uniform(-0.6, 0.6, n)
        size = rng.lognormal(np.log(0.028), 0.45, n)
        delay = rng.uniform(0, 0.08, n)
        return v, x0, z, size, delay, dot_atlas(64, 0.75)
    v, x0, z, size, delay, atlas = cached("splash2", make)
    tt = np.maximum(u - delay, 0.0)
    px = LINE_X + x0 + v[:, 0] * tt
    py = 0.01 + v[:, 1] * tt - 0.5 * 9.8 * tt * tt
    alive = (u - delay > 0) & (py > -0.02)
    if not alive.any():
        return []
    a = np.clip(1.0 - tt / 1.1, 0, 1) * 0.85                      # 被月光照亮的水珠
    col = np.c_[0.85 * a, 0.92 * a, 1.0 * a, a][alive].astype(np.float32)
    pos = np.c_[px, py, z][alive].astype(np.float32)
    return [Particles(atlas, pos, size[alive], None, col, blend="over", group="past")]


# ---------------------------------------------------------------- L22 的歌词（锁定在画面上）

def lyric_items(t, cam_fn):
    """"回到從前"竖排在线的左边，"那樣　風情萬"在右边；字随镜头上升，出现时从下方略微追上来再停稳。
    暗底上是暖白，115.05–115.30 秒露出亮的旧纸时渐变成墨褐。
    "重"（115.98）落在冲破成冷白的那一刻，由下一段接着写出。"""
    text = look.trad(look.lyric(22)).replace("　", "")
    items = []
    for i, ch in enumerate(text[:-1]):
        tc = L22[i]
        if t < tc - 0.03:
            continue
        if i < 4:
            sx, sy = 0.385, 0.25 + i * 0.105
        else:
            j = i - 4
            sx, sy = 0.630, 0.30 + j * 0.105 + (0.06 if j >= 2 else 0.0)
        a = float(ease(ramp(t, tc - 0.03, tc + 0.12)))
        rise = 0.035 * (1.0 - float(ease(ramp(t, tc - 0.03, tc + 0.30))))
        z = 3.2
        (wx, wy), Hs = cam_fn.screen_to_world(t, sx, sy + rise, z=z)
        h = 0.088 * Hs
        glow = 1.0 + 0.5 * math.exp(-max(t - tc, 0) / 0.25)
        # 层带扫过、露出亮的旧纸以后，歌词按"亮底上用墨褐"由暖白渐变成墨褐，身后的暗影随之淡去
        lt = float(ease(ramp(t, 115.05, 115.30)))
        col = WARM * glow * (1 - lt) + np.array(look.C["ink"]) * lt
        items.append(TextPlane(ch, kind="serif", weight=700, height=h, color=tuple(col), center=(wx, wy, z),
                               group="past", opacity=a))
        # 暗处：字后一团很淡的暗影，压住身后掠过的亮层，保证读得清
        sh = cached("lyric_shadow", lambda: Tex(np.dstack([np.zeros((128, 128, 3), np.float32), _soft(128, 1.4)[..., 3]])))
        if lt < 0.999:
            items.append(Plane(sh, center=(wx, wy, z - 0.01), size=(h * 2.7, h * 2.7), group="past",
                               opacity=0.78 * a * (1 - lt)))
    return items


# ---------------------------------------------------------------- 穿出水面时镜头上的水膜

def _film_tex():
    """镜头上的一层水：青色、半透明，上沿是一道被水面反光照亮的弯月形亮边，边缘起伏不平。"""
    w, h = 1024, 512
    rng = np.random.default_rng(23)
    n1 = gaussian_filter(rng.normal(0, 1, w), 70, mode="wrap")
    n2 = gaussian_filter(rng.normal(0, 1, w), 18, mode="wrap")
    edge = 0.10 + 0.045 * n1 / (np.abs(n1).max() + 1e-6) + 0.012 * n2 / (np.abs(n2).max() + 1e-6)
    yy = np.linspace(0, 1, h)[:, None]
    d = (yy - edge[None, :]) * h
    body = np.clip(d / 10.0, 0, 1) * (0.75 + 0.25 * yy)
    rim = np.exp(-(d / 3.5) ** 2)
    a = np.clip(body * 0.5 + rim * 0.55, 0, 1)
    col = np.array([0.10, 0.36, 0.40]) * body[..., None] * 0.5 + np.array([0.70, 0.92, 1.0]) * rim[..., None] * 0.55
    col = col / np.maximum(a, 1e-3)[..., None]
    return np.dstack([np.clip(col, 0, 2), a]).astype(np.float32)


def lens_items(t, cam_fn):
    """第三下底鼓时镜头穿出水面：镜头上还挂着一层水，水膜在约 0.35 秒里从上往下流走，上沿是一道亮边。"""
    u = t - KICK3
    if u < 0.0 or u > 0.40:
        return []
    tex = cached("lens_film", lambda: Tex(_film_tex()))
    x, y, H, _ = cam_fn.state(t)
    d = H * K
    z = d - 0.6
    s = (d - z) / d
    fh, fw = H * s, H * s * 16 / 9
    drop = (u / 0.36) ** 1.7                                # 水膜下沿以重力加速度流走
    top = 0.5 * fh - drop * 1.25 * fh                       # 水膜上沿在画面上的位置
    ph = fh * 1.1
    return [Plane(tex, center=(x, y + top - ph / 2 + 0.10 * ph, z), size=(fw * 1.05, ph), group="past",
                  opacity=1.0 - 0.3 * drop)]
