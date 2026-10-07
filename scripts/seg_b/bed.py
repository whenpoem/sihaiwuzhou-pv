"""L07：草席上的荞麦枕头、枕头底下的锈刀，窗格形状的午后阳光滑过枕面、变暗、转成黄昏的蓝。

画面是俯看的一张床：七十年代夏天的床上铺草席，白布枕头在中间偏左，"蕎麥枕頭下"印在枕头上方的席子上，刀从
右边滑进枕头底下，刀身藏在枕下，只露出护手、一截生锈的刀身和鹿角刀柄；"藏着把"和"鏽跡的刀"印在刀柄的上下两侧。
歌词按正片叠底印在席子上，所以和席子一起被阳光照亮、一起暗下去。

三样东西都用 Commons 上的真实照片：
枕头取 Itrytohelp32 拍的白枕头（Average White Pillow，CC BY-SA 4.0），按颜色把枕头从地毯上抠出来，保留照片里
真实的轮廓、枕角和皱褶的明暗，调成洗旧的棉布色。枕套上印着褪色的红字"備戰　備荒　為人民"（七十年代的枕套、
毛巾常印口号），字跟着照片的明暗起伏；右下角绣一朵花，花样取自 Kritzolina 拍的绣花枕套（CC BY-SA 4.0），
褪色后只剩靛蓝和灰绿（红色留给旧字）。
草席取 Srithern 拍的草席（Reed mat，CC BY-SA 3.0）中间没有花边的部分，镜像平铺，调成草黄色。
刀是奥克兰战争纪念博物馆藏品照片 Knife (AM 1962.54-2)（CC BY 4.0）：鹿角柄、锈蚀的护手和刀首，刀身满是锈斑。

光：窗格形状的光斑由三个材质共用的 GLSL 函数算出，是一个带窗棂的平行四边形，半影有一定宽度。光斑从左往右
滑过，亮度和颜色随时间由午后的暖黄变成橙色、变暗，环境光由暖灰转成黄昏的蓝；枕头和刀高出席面，光斑在它们
上面沿光线方向错开一点。刀在光斑最后掠过时闪一下：钢面在光斑里出现一道很亮的镜面高光。

云变成枕套：镜头跟着刀穿过一片近云，近云的白铺满画面（fall.whiteout_items），屋里的东西在这片白里一次换上
（48.37 秒）。白光散开时，留下的就是受光的枕套的白布；同时焦点由虚到实（scene.frame 里给镜头加景深，
窗格光斑的半影随景深一起变宽），布纹和枕套上的红字随之清楚起来。材质里保留了按云的亮度"显出"的系数 D，
现在阈值取得足够低，D 处处为 1。
"""
import math

import numpy as np
from PIL import Image
from scipy import ndimage
from scipy.ndimage import gaussian_filter

import yard as Y
from common import IMG, INK, L, Z_SKY, cached, disk, ease, lum, photo, ramp, smooth
from engine import Plane, Tex, TextPlane, register_material
from plan import T

# ---------------------------------------------------------------- 布局（z = 0 平面，世界单位）

BED_C = (15.5, 1.5)
BED_SIZE = (46.0, 32.0)
PILLOW_C = (14.6, 1.7)
PILLOW_W = 12.6                                   # 高按照片的宽高比
KNIFE_LEN = 8.0
KNIFE_REST = (23.0, 0.75)                         # 刀停下时的中心：刀身大半在枕头底下，护手和一截刀身露在枕头右边
KNIFE_ANG = 182.5                                 # 刀停下时的方向（度）：刀尖朝左
T_LAND, T_HIDE = 48.60, T(7, 5)                   # 刀落到席子上；"藏"：刀停在枕头底下

# ---------------------------------------------------------------- 共用的光

LIGHT_GLSL = r"""
uniform vec4 win;           // 光斑中心 x、y，宽、高（世界单位）
uniform float win_shear;    // 平行四边形的斜度
uniform vec3 win_col;       // 光斑的颜色和强度
uniform vec3 amb;           // 环境光
uniform vec2 win_dir;       // 光线在床面上的水平方向（从窗到床），用于高处的错位
uniform sampler2D cloudlum; // 云的亮度（显出用）
uniform vec4 cloud_rect;    // 云照片的世界范围：x0、y 顶、宽、高
uniform float dis_thr;      // 显出的阈值，从 1.3 降到 −0.4
uniform float cloud_mix;    // 过渡期间布面明暗里混入云的明暗的程度

float winmask(vec2 p) {
    vec2 q = p - win.xy;
    q.x -= win_shear * q.y;
    vec2 hw = win.zw * 0.5;
    // 半影约 0.3；焦点虚的时候（g_blur 为景深模糊的像素半径）光斑的边一起变虚
    float soft = 0.30 + g_blur * length(fwidth(p)) * 0.8;
    float fx = smoothstep(hw.x + soft, hw.x - soft, abs(q.x));
    float fy = smoothstep(hw.y + soft, hw.y - soft, abs(q.y));
    float bw = 0.15;            // 窗棂宽的一半
    float s2 = min(soft * 0.55, 0.15 + g_blur * length(fwidth(p)) * 0.8);
    float mx = smoothstep(bw - s2, bw + s2, abs(q.x));
    float my1 = smoothstep(bw - s2, bw + s2, abs(q.y - hw.y / 3.0));
    float my2 = smoothstep(bw - s2, bw + s2, abs(q.y + hw.y / 3.0));
    return fx * fy * mx * my1 * my2;
}

// 高度为 h 处的照度：光斑沿光线方向错开
vec3 lightat(vec2 p, float h, float nl) {
    float m = winmask(p - win_dir * h * 0.9);
    float near = exp(-pow(length((p - win.xy) / (win.zw * 1.1)), 2.0));    // 光斑在屋里漫开的一点亮
    return amb + win_col * (m * nl + 0.10 * near);
}

float cloudshade(vec2 p) {
    vec2 uv = vec2((p.x - cloud_rect.x) / cloud_rect.z, (cloud_rect.y - p.y) / cloud_rect.w);
    return texture(cloudlum, uv).r;
}

float reveal(vec2 p, float bonus) {
    float nz = fbm(p * 0.35, 3, 0.0, 61);
    float key = 0.80 * cloudshade(p) + 0.20 * nz + bonus;
    return smoothstep(dis_thr - 0.30, dis_thr, key);
}

// 枕头只从云亮的地方长出来：亮部先变成布，暗部晚一些，但都比席子早
float reveal_pillow(vec2 p) {
    float key = 0.55 + 0.45 * cloudshade(p) + 0.10 * fbm(p * 0.35, 3, 0.0, 61) + 0.30;
    return smoothstep(dis_thr - 0.30, dis_thr, key);
}
"""

MAT_GLSL = LIGHT_GLSL + r"""
vec4 material(vec4 base) {
    vec2 p = v_wpos.xy;
    float D = reveal(p, 0.0);
    if (D <= 0.0) return vec4(0.0);
    vec3 alb = base.rgb / max(base.a, 1e-4);
    // 草席铺得不完全平：低频的起伏让光斑的亮度有一点变化
    float und = gnoise(p * vec2(0.20, 0.55), 5);
    float nl = 1.0 + 0.10 * und;
    float cm = cloud_mix * (1.0 - D * 0.7);
    alb *= mix(1.0, 0.55 + 0.65 * cloudshade(p), cm);
    vec3 col = alb * lightat(p, 0.0, nl);
    return vec4(col * D, D);
}
"""

PILLOW_GLSL = LIGHT_GLSL + r"""
uniform sampler2D hmap;     // 枕头的高度（R）
uniform float p_height;     // 枕头最高处离席面的高度
vec4 material(vec4 base) {
    vec2 p = v_wpos.xy;
    if (base.a <= 0.0) return vec4(0.0);
    float D = reveal_pillow(p);
    if (D <= 0.0) return vec4(0.0);
    vec2 px = 1.0 / vec2(textureSize(hmap, 0));
    float hm = texture(hmap, v_uv).r;
    float hx = texture(hmap, v_uv + vec2(px.x, 0.0)).r - texture(hmap, v_uv - vec2(px.x, 0.0)).r;
    float hy = texture(hmap, v_uv - vec2(0.0, px.y)).r - texture(hmap, v_uv + vec2(0.0, px.y)).r;
    vec2 scale = u_size * px * 2.0;
    vec3 n = normalize(vec3(-hx * p_height / scale.x, -hy * p_height / scale.y, 1.0));
    float h = hm * p_height;
    // 荞麦壳撑出的细碎起伏
    float fw = length(fwidth(p));
    float g1 = gnoise(p * 6.0, 71), g2 = gnoise(p * 6.0 + vec2(0.15, 0.0), 71), g3 = gnoise(p * 6.0 + vec2(0.0, 0.15), 71);
    float lump = (1.0 - smoothstep(0.03, 0.08, fw)) * 0.8;
    n = normalize(n + vec3(-(g2 - g1), -(g3 - g1), 0.0) * 0.30 * lump * hm);
    vec3 Lw = normalize(vec3(win_dir * 0.9, 1.0));
    float nl = clamp(dot(n, Lw), 0.0, 1.0) * 1.10;
    float cm = cloud_mix * (1.0 - D * 0.7);
    vec3 alb = base.rgb / base.a;
    alb *= mix(1.0, 0.80 + 0.35 * cloudshade(p), cm);
    // 鼓起的枕面：边上朝外倾的地方接到的天光少，暗一些
    float ao = 0.62 + 0.38 * smoothstep(0.0, 0.55, hm);
    vec3 col = alb * (0.70 + 0.30 * n.z) * ao * lightat(p, h, nl);
    float a = base.a * D;
    return vec4(col * a, a);
}
"""

KNIFE_GLSL = LIGHT_GLSL + r"""
uniform sampler2D steel;    // 钢面（刀身）的遮罩
uniform float k_height;     // 刀离席面的高度
uniform float spark;        // 闪一下的强度
uniform float in_sky;       // 1：还在天上，按正午的天光照；0：落到屋里，按屋里的光照
vec4 material(vec4 base) {
    vec2 p = v_wpos.xy;
    if (base.a <= 0.0) return vec4(0.0);
    vec3 alb = base.rgb / base.a;
    float st = texture(steel, v_uv).r;
    vec3 room = lightat(p, k_height, 1.0);
    vec3 sky = vec3(0.95, 0.90, 0.80);
    vec3 li = mix(room, sky, in_sky);
    float m = winmask(p - win_dir * k_height * 0.9);
    // 钢面的镜面高光：只在光斑里，沿刀身方向的一条窄带
    float ridge = exp(-pow((v_uv.y - 0.40) / 0.10, 2.0));
    vec3 spec = vec3(1.0, 0.86, 0.62) * st * m * ridge * (0.25 + spark * 8.0) * length(win_col) * (1.0 - in_sky);
    vec3 col = alb * li + spec;
    return vec4(col * base.a, base.a);
}
"""

register_material("mat_b", MAT_GLSL)
register_material("pillow_b", PILLOW_GLSL, defaults={"p_height": 1.6})
register_material("knife_b", KNIFE_GLSL, defaults={"k_height": 0.0, "spark": 0.0, "in_sky": 0.0})


# ---------------------------------------------------------------- 光随时间

WIN_KEYS = [  # (t, 中心 x, 中心 y, 强度, 暖→橙 0–1)
    (48.37, 11.0, 3.4, 1.60, 0.00),
    (49.05, 12.8, 3.1, 1.55, 0.00),
    (49.60, 14.9, 2.7, 1.45, 0.12),
    (50.15, 17.9, 2.1, 1.10, 0.45),
    (50.55, 21.0, 1.5, 0.72, 0.80),
    (50.84, 24.4, 1.1, 0.42, 1.00),
    (50.93, 25.2, 1.0, 0.04, 1.00),
]


def light_state(t):
    k = np.array(WIN_KEYS)
    tt = min(max(t, k[0, 0]), k[-1, 0])
    x, y, s, warm = [float(np.interp(tt, k[:, 0], k[:, i])) for i in range(1, 5)]
    col = np.array([1.0, 0.84, 0.60]) * (1 - warm) + np.array([1.0, 0.50, 0.24]) * warm
    # 环境光：午后的暖灰 → 黄昏的蓝 → 暗
    d = smooth(t, 49.7, 50.62)
    amb = np.array([0.62, 0.57, 0.50]) * (1 - d) + np.array([0.14, 0.17, 0.27]) * d
    amb = amb * (1 - 0.85 * smooth(t, 50.60, 50.93))
    return dict(win=(x, y, 8.2, 5.6), win_shear=0.36, win_col=tuple(col * s), amb=tuple(amb), win_dir=(0.42, -0.10))


def reveal_uniforms(t):
    """屋里的东西在白光里一次换上，不再按云的亮度逐块显出：阈值取得足够低，D 处处为 1。"""
    thr = -2.0
    cm = 0.0
    cx, cy, W, H = Y.cloud_geom()
    return {"cloudlum": cloud_lum_tex(), "cloud_rect": (cx - W / 2, cy + H / 2, W, H), "dis_thr": thr, "cloud_mix": cm}


T_SWITCH = 48.37                                  # 画面全白的一刻（与 sky.T_SWITCH 相同）


def revealed(t):
    """已经换到屋里（之后不再画天空和云）。"""
    return t >= T_SWITCH


def cloud_lum_tex():
    def make():
        a = Y.cloud_rgba()
        lu = lum(a[..., :3]) * a[..., 3]
        lu = lu / max(np.percentile(lu, 99.5), 1e-3)
        small = np.asarray(Image.fromarray((np.clip(lu, 0, 1) * 255).astype(np.uint8)).resize((1024, 560), Image.LANCZOS))
        return gaussian_filter(small.astype(np.float32) / 255, 1.5)
    return cached("cloudlum", lambda: Tex(make()))


# ---------------------------------------------------------------- 草席

MAT_PHOTO = "Reed_mat.jpg"
MAT_CROP = (30, 215, 1180, 1010)                   # 中间没有花边的部分
MAT_UPP = 0.0125                                    # 每像素的世界长度：一根草约 0.09，枕头宽 12.6（约 60 厘米）


def mat_tex():
    def make():
        im = photo(MAT_PHOTO)
        x0, y0, x1, y1 = MAT_CROP
        c = im[y0:y1, x0:x1]
        lu = lum(c)
        # 去掉照片里的偏色和光照不匀：只保留细节（高通），再铺上草黄色
        low = gaussian_filter(lu, 40)
        det = lu / np.maximum(low, 1e-3)
        straw = np.array([0.80, 0.66, 0.42])
        col = straw * np.clip(det, 0.55, 1.45)[..., None] ** 1.3
        # 草与草之间偏绿、偏旧的一点变化
        g = np.clip((c[..., 1] - c[..., 0]) * 3.0, -0.3, 0.3)
        col = col * (1 + np.stack([-0.10 * g, 0.05 * g, -0.10 * g], -1))
        # 镜像平铺成 2 × 2
        top = np.concatenate([col, col[:, ::-1]], 1)
        full = np.concatenate([top, top[::-1]], 0)
        return full.astype(np.float32)
    return cached("mattex", lambda: Tex(disk("mat", make, MAT_PHOTO, MAT_CROP, "m1"), repeat=True))


def bed_items(t, light):
    if t < T_SWITCH:
        return []
    tex = mat_tex()
    h, w = tex.data.shape[:2]
    uni = dict(light)
    uni.update(reveal_uniforms(t))
    tw, th = w * MAT_UPP, h * MAT_UPP
    W, H = BED_SIZE
    return [Plane(tex, center=(*BED_C, Z_SKY + 0.5), size=(W, H), uv=(0, 0, W / tw, H / th), material="mat_b",
                  uniforms=uni, group="past", stack="bed")]


# ---------------------------------------------------------------- 枕头

PILLOW_PHOTO = "Average_White_Pillow.jpg"


def _pillow_cut():
    """照片里的枕头：(RGB, alpha)，裁到枕头的范围，宽 1500 像素。"""
    ph = photo(PILLOW_PHOTO)
    sat = ph.max(2) - ph.min(2)
    lu = lum(ph)
    m = (sat < 0.10) & (lu > 0.33)
    m = ndimage.binary_opening(m, iterations=3)
    lab, n = ndimage.label(m)
    sizes = ndimage.sum(m, lab, range(1, n + 1))
    m = lab == (np.argmax(sizes) + 1)
    m = ndimage.binary_closing(m, iterations=6)
    m = ndimage.binary_fill_holes(m)
    # 边缘的阴影把轮廓啃得参差不齐：把轮廓抹圆再取一半，得到照片里枕头本来平滑的边
    m = gaussian_filter(m.astype(np.float32), 40) > 0.5
    ys, xs = np.nonzero(m)
    y0, y1, x0, x1 = ys.min() - 20, ys.max() + 21, xs.min() - 20, xs.max() + 21
    rgb = ph[y0:y1, x0:x1]
    a = gaussian_filter(m[y0:y1, x0:x1].astype(np.float32), 2.0)
    s = 1500 / rgb.shape[1]
    size = (1500, int(rgb.shape[0] * s))
    rgb = np.asarray(Image.fromarray((rgb * 255).astype(np.uint8)).resize(size, Image.LANCZOS), np.float32) / 255
    a = np.asarray(Image.fromarray((a * 255).astype(np.uint8)).resize(size, Image.LANCZOS), np.float32) / 255
    return rgb, a


def _print_layer(nx, ny, shade):
    """枕套上的红字（覆盖率）：沿一条平缓的弧排开，字随枕面的明暗起伏轻微错位。"""
    import skia
    s = L.surface(nx, ny)
    c = s.getCanvas()
    text = L.trad("备战　备荒　为人民")
    f = L.font("serif", 900, ny * 0.125, scale_x=0.90)
    tw = L.line_width(text, f)
    x = (nx - tw) / 2
    for ch in text:
        w = f.measureText(ch)
        if ch != "　":
            cx = x + w / 2
            k = (cx - nx / 2) / (nx / 2)
            y = ny * 0.36 + (k ** 2) * ny * 0.04
            c.save()
            c.translate(cx, y)
            c.rotate(k * 5.0)
            c.drawString(ch, -w / 2, 0, f, L.white_paint())
            c.restore()
        x += w
    m = L.to_np(s)[..., 3]
    # 字印在鼓起的布面上：沿明暗的梯度错开几个像素
    gy, gx = np.gradient(gaussian_filter(shade, 12))
    yy, xx = np.mgrid[0:ny, 0:nx].astype(np.float32)
    m = ndimage.map_coordinates(m, [yy - gy * 900, xx - gx * 900], order=1)
    # 洗旧：印墨斑驳、边缘起毛
    rng = np.random.default_rng(9)
    nz = gaussian_filter(rng.normal(0, 1, (ny, nx)), 1.6)
    nz2 = gaussian_filter(rng.normal(0, 1, (ny, nx)), 16.0)
    m = np.clip(m * (0.72 + 0.20 * nz / nz.std() + 0.20 * nz2 / nz2.std()), 0, 1)
    return np.maximum(m * 0.92, gaussian_filter(m, 1.2) * 0.45)


def _embroidery(size_px):
    """绣花：取照片中央那朵花，保留针脚的明暗，颜色褪成靛蓝、灰绿。返回 RGBA。"""
    im = photo("Embroidered_pillowcase_02.jpg")
    crop = im[290:1160, 580:1430]
    lu = lum(crop)
    sat = crop.max(2) - crop.min(2)
    m = np.clip((sat - 0.16) / 0.08, 0, 1)
    m = ndimage.binary_closing(m > 0.5, iterations=3)
    m = ndimage.binary_fill_holes(m)
    lab, n = ndimage.label(m)
    sizes = ndimage.sum(m, lab, range(1, n + 1))
    m = gaussian_filter((lab == (np.argmax(sizes) + 1)).astype(np.float32), 1.5)
    red = crop[..., 0] - crop[..., 2]
    # 红色只属于旧字：花瓣改成洗褪了的靛蓝，叶子是灰绿
    col = np.where((red > 0.12)[..., None], np.array([0.40, 0.46, 0.60]), np.array([0.52, 0.56, 0.46]))
    col = col * (0.62 + 0.62 * lu[..., None])
    rgba = np.dstack([col, m * 0.70]).astype(np.float32)
    pim = Image.fromarray((np.clip(rgba, 0, 1) * 255).astype(np.uint8), "RGBA").resize((size_px, size_px), Image.LANCZOS)
    return np.asarray(pim, np.float32) / 255


def pillow_textures():
    """(枕头 RGBA 贴图, 高度贴图, 高宽比)。"""
    def make():
        rgb, a = _pillow_cut()
        ny, nx = a.shape
        lu = lum(rgb)
        # 照片的明暗：闪光灯让中间偏亮，保留一半，皱褶的细节全部保留
        low = gaussian_filter(lu, 60)
        det = lu / np.maximum(low, 1e-3)
        lowc = low / np.percentile(low[a > 0.5], 90)
        shade = np.clip(det, 0.6, 1.3) * (0.70 + 0.30 * np.clip(lowc, 0.5, 1.1))
        rng = np.random.default_rng(4)
        cotton = np.array([0.94, 0.91, 0.84])
        stain = gaussian_filter(rng.normal(0, 1, (ny, nx)), 70)
        stain = np.clip((stain / stain.std() - 0.3) * 0.6, 0, 1)
        base = cotton * (1 - stain[..., None] * 0.16 * np.array([0.2, 0.5, 1.0]))
        pm = _print_layer(nx, ny, shade)
        red = np.array([0.71, 0.255, 0.18])
        base = base * (1 - pm[..., None] * 0.80) + red * pm[..., None] * 0.80
        es = int(ny * 0.26)
        emb = _embroidery(es)
        ex, ey = int(nx * 0.72), int(ny * 0.62)
        ea = emb[..., 3:4]
        base[ey:ey + es, ex:ex + es] = base[ey:ey + es, ex:ex + es] * (1 - ea) + emb[..., :3] * ea
        col = base * shade[..., None]
        d = ndimage.distance_transform_edt(a > 0.5)
        hgt = np.clip(d / (0.22 * ny), 0, 1) ** 0.6
        hgt = gaussian_filter(hgt, 6)
        rgba = np.dstack([col, a]).astype(np.float32)
        hm = np.dstack([hgt, np.zeros_like(hgt), np.full_like(hgt, 1.5), np.ones_like(hgt)]).astype(np.float32)
        return np.stack([rgba, hm])
    arr = disk("pillow_tex", make, PILLOW_PHOTO, "p5")
    asp = arr.shape[1] / arr.shape[2]
    return cached("pillow_texs", lambda: (Tex(arr[0]), Tex(arr[1], premultiplied=True), asp))


def pillow_size():
    _, _, asp = pillow_textures()
    return PILLOW_W, PILLOW_W * asp


def pillow_items(t, light):
    if t < T_SWITCH:
        return []
    rgba, hm, asp = pillow_textures()
    uni = dict(light)
    uni.update(reveal_uniforms(t))
    uni["hmap"] = hm
    items = []
    k = 1.0
    if k > 0:
        # 枕头压在席子上的影子：贴着轮廓最深，往外很快变淡，顺着光线方向错开一点
        pw, ph = pillow_size()
        items.append(Plane(pillow_shadow_tex(), center=(PILLOW_C[0] + 0.25, PILLOW_C[1] - 0.18, Z_SKY + 0.5),
                           size=(pw * 1.16, ph * 1.16), blend="multiply", opacity=0.75 * k, group="past", stack="bed"))
    items.append(Plane(rgba, center=(*PILLOW_C, Z_SKY + 0.5), size=pillow_size(), material="pillow_b", uniforms=uni,
                       group="past", stack="bed"))
    return items


def pillow_shadow_tex():
    def make():
        rgba, hm, asp = pillow_textures()
        a = rgba.data[..., 3].astype(np.float32)
        a = a / 255.0 if rgba.data.dtype == np.uint8 else a
        a = a[::2, ::2]
        h, w = a.shape
        pad = int(w * 0.08)
        big = np.zeros((h + 2 * pad, w + 2 * pad), np.float32)
        big[pad:pad + h, pad:pad + w] = a
        sh = 0.65 * gaussian_filter(big, 6) + 0.35 * gaussian_filter(big, 22)
        return np.dstack([np.zeros_like(sh)] * 3 + [np.clip(sh, 0, 1)]).astype(np.float32)
    return cached("pillow_shadow", lambda: Tex(make()))


# ---------------------------------------------------------------- 刀

KNIFE_PHOTO = "Knife_AM_1962_54-2_.jpg"


def knife_textures():
    """(刀 RGBA，钢面遮罩，宽高比)。照片里刀横放、刀尖朝右，背景是白纸；裁到刀的范围。"""
    def make():
        k = photo(KNIFE_PHOTO)
        bg = np.median(k[:60, :60].reshape(-1, 3), 0)
        d = np.abs(k - bg).max(2)
        lu = lum(k)
        # 白纸上的投影是偏暖的浅灰（亮度 0.7 以上、饱和度 0.1 以下）：刀本身要么更暗，要么颜色更饱和
        sat = k.max(2) - k.min(2)
        m = (lu < 0.60) | (sat > 0.15)
        m = ndimage.binary_opening(m, iterations=2)
        lab, n = ndimage.label(m)
        sizes = ndimage.sum(m, lab, range(1, n + 1))
        m = lab == (np.argmax(sizes) + 1)
        m = ndimage.binary_closing(m, iterations=9)
        m = ndimage.binary_closing(m, structure=np.ones((1, 121), bool))      # 刀身上沿的反光不算缺口
        m = ndimage.binary_fill_holes(m)
        # 护手下面被围住的一小块投影：刀柄一侧浅灰、不饱和的像素去掉
        ys_, xs_ = np.nonzero(m)
        xcut = xs_.min() + 0.55 * (xs_.max() - xs_.min())
        paper = (lu > 0.68) & (sat < 0.09) & (np.arange(k.shape[1])[None, :] < xcut)
        core = ndimage.binary_erosion(m, iterations=22)                     # 刀柄里面的浅色鹿角纹不动
        m &= ~(paper & ~core)
        m = ndimage.binary_fill_holes(m)
        m = ndimage.binary_opening(m, iterations=6)
        lab, n = ndimage.label(m)
        sizes = ndimage.sum(m, lab, range(1, n + 1))
        m = lab == (np.argmax(sizes) + 1)
        m = ndimage.binary_erosion(m, iterations=2)
        ys, xs = np.nonzero(m)
        y0, y1, x0, x1 = ys.min() - 8, ys.max() + 9, xs.min() - 8, xs.max() + 9
        crop = k[y0:y1, x0:x1]
        a = gaussian_filter(m[y0:y1, x0:x1].astype(np.float32), 1.2)
        sat = crop.max(2) - crop.min(2)
        lu = lum(crop)
        xx = np.arange(crop.shape[1])[None, :] / crop.shape[1]
        steel = np.clip((0.12 - sat) / 0.06, 0, 1) * np.clip((lu - 0.30) / 0.2, 0, 1) * (xx > 0.55)
        steel = gaussian_filter(steel, 2.0)
        h, w = crop.shape[:2]
        sc = 1600 / w
        rgba = np.dstack([crop * 0.95, a]).astype(np.float32)
        rim = Image.fromarray((np.clip(rgba, 0, 1) * 255).astype(np.uint8), "RGBA").resize((1600, int(h * sc)), Image.LANCZOS)
        sim = Image.fromarray((np.clip(steel, 0, 1) * 255).astype(np.uint8)).resize((1600, int(h * sc)), Image.LANCZOS)
        out = np.zeros((int(h * sc), 1600, 5), np.float32)
        out[..., :4] = np.asarray(rim, np.float32) / 255
        out[..., 4] = np.asarray(sim, np.float32) / 255
        return out
    arr = disk("knife_tex", make, KNIFE_PHOTO, "k6")
    return cached("knife_texs", lambda: (Tex(arr[..., :4].copy()), Tex(arr[..., 4].copy()), arr.shape[1] / arr.shape[0]))


def knife_plane(t, light, center, ang, height=0.0, spark=0.0, scale=1.0, shadow=None, in_sky=0.0, z=None):
    rgba, steel, asp = knife_textures()
    uni = dict(light)
    uni.update(reveal_uniforms(t))
    uni.update({"steel": steel, "k_height": height, "spark": spark, "in_sky": in_sky})
    z = Z_SKY + 0.5 if z is None else z
    items = []
    size = (KNIFE_LEN * scale, KNIFE_LEN * scale / asp)
    if shadow is not None:
        off, a = shadow
        items.append(Plane(rgba, center=(center[0] + off[0], center[1] + off[1], z), size=size, rot=(0, 0, ang),
                           color=(0.0, 0.0, 0.0), opacity=a, group="past", stack="bed"))
    items.append(Plane(rgba, center=(center[0], center[1], z), size=size, rot=(0, 0, ang), material="knife_b",
                       uniforms=uni, group="past", stack="bed"))
    return items


# ---------------------------------------------------------------- 字

L07 = L.trad(L.lyric(7))                          # 蕎麥枕頭下　藏着把　鏽跡的刀
TEXT_H = 1.45


def text_layout():
    """(字, x, y, 时刻)：第一句在枕头上方一行，后两句在刀柄的上下两侧。"""
    parts = L07.split("　")
    out = []
    k = 0
    pw, ph = pillow_size()
    x0, y0 = PILLOW_C[0] - 2 * 1.62 - 0.4, PILLOW_C[1] + ph / 2 + 1.25
    for i, ch in enumerate(parts[0]):
        out.append((ch, x0 + i * 1.62, y0, T(7, k)))
        k += 1
    for i, ch in enumerate(parts[1]):
        out.append((ch, 22.6 + i * 1.58, 3.55, T(7, k)))
        k += 1
    for i, ch in enumerate(parts[2]):
        out.append((ch, 21.4 + i * 1.58, -1.05, T(7, k)))
        k += 1
    return out


def text_items(t):
    if t < T(7, 0) - 0.05:
        return []
    items = []
    for ch, x, y, tc in text_layout():
        if t < tc - 0.03:
            continue
        # 最后一个"刀"唱出时屋里只剩最后一点光，字要在一两帧里印出来
        a = float(ease((t - tc + 0.03) / (0.06 if tc == T(7, -1) else 0.18)))
        items.append(TextPlane(ch, kind="serif", weight=700, height=TEXT_H, color=INK, center=(x, y, Z_SKY + 0.5),
                               blend="multiply", opacity=a * 0.92, group="past", stack="bed"))
    return items
