"""L20–L22 的水下：水体、从下面看到的水面、斜射的光柱、悬浮颗粒、沉钟与钟声的字环。

水下的一切都按"水深"和"离镜头的距离"上色：同一个雾色函数被背景、水面、钟和光柱共用，远处融进同一片青色；往上看
最亮（光从水面透下来），平视是青色，往下看接近墨绿；镜头越深整体越暗。水面是一块真正水平的平面（y = 0），从下面看
它是一面闪动的镜子，按透视一直延伸到远处的雾里，所以画面上方有一片向远处收拢的"天花板"，空间的纵深由此而来。光柱是
几块竖长的平面，放在不同深度，镜头移动时快慢不同；悬浮颗粒同样分布在镜头前后，近的大而虚、远的小而淡。

钟取自大都会艺术博物馆藏的青铜钟（"Bell MET LC-52 26-3"，CC0，assets/images/Bell_MET_LC-52_26-3.jpg）：灰色背景
上抠出，按水下的光重新上色——去掉大部分饱和度、偏青、降低对比，上半部被透下的光照亮，钟面上有缓慢游动的焦散亮纹。

坐标（米）：水面在 y = 0。门这一侧（镜头穿过锁孔之前）整个水下世界平移 w_off 放到门后，材质里先减去 w_off 再按
水深计算，所以平移前后颜色完全一致。
"""
import math

import numpy as np
from scipy.ndimage import gaussian_filter, binary_fill_holes, label

from common import CACHE, LUMA, disk_cache, load_rgb, save_png, OUT
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import register_material  # noqa: E402

VERSION = 1
BELL_PHOTO = "Bell_MET_LC-52_26-3.jpg"

UW_COMMON = """
uniform vec3 w_off;
uniform vec3 uw_top;
uniform vec3 uw_mid;
uniform vec3 uw_deep;
uniform vec3 uw_light;
uniform float uw_vis;
uniform float uw_atten;

vec3 uw_dir(vec3 d, float ey) {
    vec3 c = mix(uw_deep, uw_mid, smoothstep(-0.30, 0.02, d.y));
    c = mix(c, uw_top, smoothstep(0.0, 0.30, d.y));
    return c * exp(min(ey, 0.0) / uw_atten);
}
vec3 uw_fog(vec3 col, vec3 p, vec3 e) {
    vec3 d = p - e;
    float dist = length(d);
    float f = 1.0 - exp(-dist / uw_vis);
    return mix(col, uw_dir(d / max(dist, 1e-4), e.y), f);
}
// 焦散：水面的波纹把光聚成一张缓慢游动的亮网。两层脊状噪声相乘，网线细而亮
float caustic(vec2 p, float t) {
    vec2 q = p + vec2(0.35 * sin(0.4 * t + p.y * 0.7), 0.35 * cos(0.33 * t + p.x * 0.6));
    float a = 1.0 - abs(gnoise(q * 1.1 + vec2(0.21 * t, 0.13 * t), 51) * 1.6);
    float b = 1.0 - abs(gnoise(q * 1.7 - vec2(0.17 * t, -0.19 * t), 52) * 1.6);
    return pow(clamp(a, 0.0, 1.0), 7.0) * 0.7 + pow(clamp(a * b, 0.0, 1.0), 5.0) * 0.9;
}
"""

UW_DEFAULTS = {"w_off": (0.0, 0.0, 0.0), "uw_top": (0.16, 0.46, 0.48), "uw_mid": (0.045, 0.19, 0.215),
               "uw_deep": (0.010, 0.050, 0.062), "uw_light": (0.75, 1.45, 1.45), "uw_vis": 9.0, "uw_atten": 7.0}

# 水体：一块始终在镜头前方远处的大平面，颜色只取决于视线方向和镜头深度，加一层极淡的明暗起伏
register_material("uw_back", UW_COMMON + """
vec4 material(vec4 base) {
    vec3 p = v_wpos - w_off, e = u_eye - w_off;
    vec3 d = normalize(p - e);
    vec3 c = uw_dir(d, e.y);
    float n = vnoise(p.xy * 0.08 + vec2(0.02 * u_time, 0.0), 61) * 0.6 + vnoise(p.xy * 0.25 - vec2(0.0, 0.03 * u_time), 62) * 0.4;
    c *= 0.86 + 0.28 * n;
    return vec4(c, 1.0);
}
""", UW_DEFAULTS)

# 水面：从下面看是一面闪动的镜子（全反射映出下面的深水），波纹把光聚成亮网，近处亮、远处融进雾里；
# 从上面看是夜里的水面：按菲涅耳反射映出夜空（越近水平线反射越强），波纹的法线把月光反射成一条碎光带，
# 在月亮正下方从水平线一直铺到近处
register_material("uw_surface", UW_COMMON + """
uniform vec3 night_col;
uniform float surf_k;
uniform vec3 moon_dir;
uniform vec3 sky_refl;
vec4 material(vec4 base) {
    vec3 p = v_wpos - w_off, e = u_eye - w_off;
    float t = u_time;
    vec2 q = p.xz;
    vec2 w = vec2(gnoise(q * 0.7 + vec2(0.25 * t, 0.1 * t), 71), gnoise(q * 0.7 - vec2(0.12 * t, 0.2 * t), 72));
    float c1 = caustic(q * 1.1 + w * 0.8, t * 1.3);
    float c2 = caustic(q * 2.7 - w * 0.5, t * 1.7);
    vec3 col;
    if (e.y < 0.0) {
        float dist = length(p - e);
        col = mix(uw_mid, uw_top, 0.55) * (0.85 + 0.5 * w.x) + uw_top * (1.3 * c1 + 0.7 * c2);
        col *= surf_k;
        col = uw_fog(col, p, e);
    } else {
        vec3 V = normalize(p - e);
        vec2 fine = vec2(gnoise(q * 4.3 + vec2(0.9 * t, -0.6 * t), 75), gnoise(q * 4.3 - vec2(0.5 * t, 0.8 * t), 76));
        vec3 n = normalize(vec3(w.x * 0.22 + fine.x * 0.10, 1.0, w.y * 0.22 + fine.y * 0.10));
        vec3 R = reflect(V, n);
        float cosv = max(-V.y, 0.0);
        float fres = 0.02 + 0.98 * pow(1.0 - cosv, 5.0);
        col = night_col + sky_refl * fres * (0.75 + 0.5 * w.y);
        float mr = max(dot(R, moon_dir), 0.0);
        col += vec3(1.0, 0.94, 0.82) * (pow(mr, 1400.0) * 2.6 + pow(mr, 90.0) * 0.12) * (0.4 + 0.6 * fres);
        float g = pow(max(c2, 0.0), 2.0) * 0.6 + pow(max(c1, 0.0), 3.0) * 0.4;
        col += sky_refl * g * 0.25;
    }
    return vec4(col, 1.0);
}
""", dict(UW_DEFAULTS, night_col=(0.010, 0.016, 0.026), surf_k=1.0, moon_dir=(-0.186, 0.068, -0.980),
                     sky_refl=(0.075, 0.105, 0.19)))

# 光柱：竖长平面上沿光的方向排着几道细光，横向位置随时间缓慢摇动，亮度缓慢起伏；上端最亮，往下变暗，两侧淡出
register_material("uw_rays", UW_COMMON + """
uniform float ray_k;
uniform float ray_n;
uniform float ray_seed;
vec4 material(vec4 base) {
    vec3 p = v_wpos - w_off;
    float u = v_uv01.x, v = v_uv01.y;
    float t = u_time;
    float x = u * ray_n + 0.35 * sin(0.21 * t + v * 2.0 + ray_seed * 6.0) + 0.2 * sin(0.37 * t + ray_seed * 3.0);
    float n = fbm(vec2(x, 0.04 * t + ray_seed * 9.0), 3, 0.0, int(ray_seed * 97.0));
    float rays = smoothstep(0.48, 0.80, n);
    rays *= 0.5 + 0.9 * vnoise(vec2(x * 4.0, 0.1 * t), int(ray_seed * 31.0) + 3);
    float flick = 0.75 + 0.25 * sin(0.6 * t + ray_seed * 11.0) * sin(0.23 * t + ray_seed * 5.0);
    float fade = smoothstep(0.0, 0.05, v) * exp(-v * 2.6) * smoothstep(0.0, 0.25, u) * smoothstep(1.0, 0.75, u);
    vec3 c = uw_top * rays * fade * flick * ray_k;
    return vec4(c, 0.0);
}
""", dict(UW_DEFAULTS, ray_k=1.0, ray_n=3.0, ray_seed=0.3))

# 水下的物体（钟）：去掉大部分饱和度、偏青、降低对比；上半部被透下的光照亮，表面有游动的焦散；按距离融进水色
register_material("uw_obj", UW_COMMON + """
uniform float obj_top;
uniform float obj_bot;
uniform float caust_k;
uniform float obj_gain;
uniform float obj_vis;
vec4 material(vec4 base) {
    if (base.a <= 0.0) return base;
    vec3 p = v_wpos - w_off, e = u_eye - w_off;
    vec3 c = base.rgb / base.a;
    float lum = dot(c, vec3(0.30, 0.59, 0.11));
    c = mix(vec3(lum), c, 0.35);
    c = mix(vec3(0.20), c, 0.85);
    float v = clamp((p.y - obj_bot) / max(obj_top - obj_bot, 1e-3), 0.0, 1.0);
    vec3 L = uw_light * exp(min(p.y, 0.0) / uw_atten) * (0.28 + 1.05 * v * v);
    float ca = caustic(p.xy * 2.2, u_time * 1.2);
    L *= 1.0 + caust_k * ca * (0.35 + 0.65 * v);
    // 顶光在轮廓上沿留下一道亮边：上方是透明处的像素就是受光的边
    float above = textureLod(u_tex, v_uv + vec2(0.0, -0.012), 1.5).a;
    float rim = clamp(base.a - above, 0.0, 1.0);
    vec3 col = c * L * obj_gain + uw_top * rim * 1.0;
    vec3 d = p - e;
    float f = 1.0 - exp(-length(d) / obj_vis);
    col = mix(col, uw_dir(normalize(d), e.y), f);
    return vec4(col * base.a, base.a);
}
""", dict(UW_DEFAULTS, obj_top=0.0, obj_bot=-1.0, caust_k=1.2, obj_gain=1.0, obj_vis=20.0))

# 水下的歌词：暖白，近处几乎不受水色影响，只按距离略微融进水色，并带一点水面透下的光的明暗起伏
register_material("uw_text", UW_COMMON + """
uniform float txt_fog;
vec4 material(vec4 base) {
    if (base.a <= 0.0) return base;
    vec3 p = v_wpos - w_off, e = u_eye - w_off;
    vec3 c = base.rgb / base.a;
    float ca = caustic(p.xy * 2.2, u_time * 1.2);
    c *= 0.92 + 0.18 * ca;
    vec3 f = uw_fog(c, p, e);
    c = mix(c, f, txt_fog);
    return vec4(c * base.a, base.a);
}
""", dict(UW_DEFAULTS, txt_fog=0.15))


# ---------------------------------------------------------------- 钟

def bell_rgba():
    """钟（RGBA，直通 alpha）：灰色背景上按与背景色的距离抠出。返回 (rgba, 钟顶挂环在贴图里的 (u, v), 钟口 v)。"""
    def make():
        im = load_rgb(BELL_PHOTO)
        h, w = im.shape[:2]
        bg = np.median(np.r_[im[:120, :120].reshape(-1, 3), im[:120, -120:].reshape(-1, 3)], 0)
        dist = np.linalg.norm(gaussian_filter(im, (1.2, 1.2, 0)) - bg, axis=2)
        fg = dist > 0.10
        lab, n = label(fg)
        sizes = np.bincount(lab.ravel())
        sizes[0] = 0
        m = binary_fill_holes(lab == sizes.argmax())
        # 挂钮的几个孔是镂空的，单独按背景色挖出来
        holes = (dist < 0.06) & m
        lab2, n2 = label(holes)
        for j in range(1, n2 + 1):
            ys, xs = np.nonzero(lab2 == j)
            if len(ys) > 300 and ys.mean() < h * 0.3:
                m[lab2 == j] = False
        a = np.clip(gaussian_filter(m.astype(np.float32), 1.0) * 1.1, 0, 1)
        ys, xs = np.nonzero(a > 0.5)
        y0, y1, x0, x1 = max(ys.min() - 20, 0), min(ys.max() + 20, h), max(xs.min() - 20, 0), min(xs.max() + 20, w)
        out = np.dstack([im, a])[y0:y1, x0:x1]
        return out.astype(np.float32)
    if "bell" not in _MEM:                                  # 读盘只做一次，之后从内存取
        _MEM["bell"] = disk_cache("bell", make, VERSION)
    return _MEM["bell"]


_MEM = {}


def bell_geometry(height):
    """钟贴图平面的尺寸（宽, 高），以及挂环顶点、钟口相对贴图中心的位置（米）。"""
    key = ("geo", height)
    if key not in _MEM:
        _MEM[key] = _bell_geometry(height)
    return _MEM[key]


def _bell_geometry(height):
    a = bell_rgba()
    h, w = a.shape[:2]
    ys = np.nonzero(a[..., 3].max(1) > 0.5)[0]
    top, bot = ys.min(), ys.max()
    ppm = (bot - top) / height
    size = (w / ppm, h / ppm)
    crown = (0.0, (h / 2 - top) / ppm)
    lip = (h / 2 - bot) / ppm
    return size, crown, lip


# ---------------------------------------------------------------- 字环用的模糊字形图集

def ring_atlas(text, levels=(0.0, 2.5, 5.0, 9.0, 14.0), cell=192):
    """字环的旧字：仿宋，按若干档模糊程度各画一份，拼成一张图集。返回 (Atlas, {字: [各档 uv]})。"""
    import look
    from engine import Atlas
    chars = list(dict.fromkeys(text))
    n = len(chars) * len(levels)
    cols = int(math.ceil(math.sqrt(n)))
    rows = int(math.ceil(n / cols))
    arr = np.zeros((rows * cell, cols * cell), np.float32)
    rects, keys = {}, []
    k = 0
    for li, s in enumerate(levels):
        for ch in chars:
            g = look.glyph_mask(ch, kind="fang", weight=400, px=cell, pad=0.22)
            if s > 0:
                g = gaussian_filter(g, s) * (1.0 + s * 0.04)
            r, c = divmod(k, cols)
            arr[r * cell:(r + 1) * cell, c * cell:(c + 1) * cell] = np.clip(g, 0, 1)
            key = f"{ch}{li}"
            rects[key] = (c * cell / arr.shape[1], r * cell / arr.shape[0], (c + 1) * cell / arr.shape[1], (r + 1) * cell / arr.shape[0])
            keys.append(key)
            k += 1
    return Atlas(arr, rects, keys)


if __name__ == "__main__":
    a = bell_rgba()
    print(a.shape, bell_geometry(1.6))
    save_png(a[::2, ::2], OUT / "assets" / "bell.png")
