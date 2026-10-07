"""L19 的旧木门：门框立柱、门扇、门搭扣和挂锁、黄铜锁片，以及门框左边的石墙。

门搭扣和挂锁取自 Estormiz 拍摄的"Padlock Valimokatu Oulu 20250307 03"（Wikimedia Commons，CC0，
assets/images/Padlock_Valimokatu_Oulu_20250307_03.jpg）：一根锈蚀的铁搭扣横跨风化的立柱和门扇的接缝，一把旧挂锁
穿过锁鼻挂在搭扣末端。照片里是左上方的阳光，影子落向右下，正好与挂在左上方的马灯一致，所以照片原样使用，只把门扇
上褪色的红漆去掉颜色，和其余木板统一成灰褐色。照片之外的木板取自 Poly Haven 的"Wood planks"（Amal Kumar，CC0），
转成竖向的门板；门框左边的墙取自 Poly Haven 的"Rock wall 10"（Amal Kumar，CC0）。锁片取自库珀－休伊特博物馆藏
十九世纪初的黄铜锁片（"Keyhole Escutcheon, early 19th century"，公有领域），白底上抠出，锁孔的形状从照片里
直接取出来，既用作锁片和门板上挖的洞，也用作镜头穿过锁孔时的孔道。

坐标（米）：门面在 z = ZD，门框立柱与门扇的接缝在 x = 0，搭扣中线在 y = 0。贴图分三档分辨率：大范围的门与墙
（每米 900 像素）、中间一块（每米 3840 像素，即木板贴图的原始分辨率）、搭扣照片本身（每米约 9100 像素），三档
在边缘羽化后依次叠在同一个平面上。所有贴图都是光照之前的反照率，亮度由材质按马灯的位置实时计算。
"""
import numpy as np
from scipy.ndimage import gaussian_filter, binary_fill_holes, label

from common import CACHE, LUMA, IMG, disk_cache, load_rgb, save_png, OUT, smooth01

ZD = 0.06                                   # 门面所在的深度：留出锁孔孔道的厚度，镜头才能穿过去
PLANKS = "Wood_planks_diff_8k_Amal_Kumar_via_Poly_Haven_.png"
ROCK = "Rock_wall_10_diff_8k_Amal_Kumar_via_Poly_Haven_.png"
HASP = "Padlock_Valimokatu_Oulu_20250307_03.jpg"
ESC = "Keyhole_Escutcheon_early_19th_century_CH_18136249_.jpg"

HASP_PPM = 9100.0                           # 搭扣照片每米的像素数（搭扣长约 30 厘米）
HASP_ORIGIN = (1975.0, 1280.0)              # 照片里立柱与门扇的接缝、搭扣中线 → 世界 (0, 0)
POST_X = (-0.205, 0.0)                      # 门框立柱的左右边
WALL_X = -0.215                             # 墙在这条线以左
WIDE = dict(x=(-1.4, 1.2), y=(-0.9, 1.1), ppm=900.0)
MID = dict(x=(-0.50, 0.46), y=(-0.40, 0.56), ppm=3840.0)
ESC_C = (0.215, -0.178)                     # 锁片中心
ESC_H = 0.070                               # 锁片高度
PADLOCK = (0.0505, -0.021)                  # 挂锁中心（由照片像素换算）
VERSION = 5


# ---------------------------------------------------------------- 颜色

def _stylize(rgb, sat=0.3, tint=(1.0, 0.93, 0.82), gain=1.0):
    """统一成灰褐色的旧木：降低饱和度，乘上一点暖色。"""
    lum = rgb @ LUMA
    out = lum[..., None] + (rgb - lum[..., None]) * sat
    return np.clip(out * np.array(tint, np.float32) * gain, 0, 1).astype(np.float32)


def _match(rgb, mean, std, ref_mask=None):
    """把亮度的均值和标准差调到给定值。"""
    lum = rgb @ LUMA
    sel = lum if ref_mask is None else lum[ref_mask]
    m, s = float(sel.mean()), float(sel.std()) + 1e-6
    new = (lum - m) / s * std + mean
    return np.clip(rgb * (new / np.maximum(lum, 1e-4))[..., None], 0, 1)


# ---------------------------------------------------------------- 贴图采样

_TEX = {}


def _tex(name, rot=False):
    key = (name, rot)
    if key not in _TEX:
        a = load_rgb(name)
        if rot:
            a = np.ascontiguousarray(np.rot90(a))
        _TEX[key] = a
    return _TEX[key]


def _sample(tex, X, Y, tile, ox=0.0, oy=0.0):
    """按世界坐标在平铺贴图上取样（双线性，四边循环）。tile 为一块贴图对应的世界长度。"""
    import cv2
    h, w = tex.shape[:2]
    mx = (((X - ox) / tile) % 1.0 * w).astype(np.float32)
    my = (((oy - Y) / tile) % 1.0 * h).astype(np.float32)
    return cv2.remap(tex, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)


def _grid(spec):
    (x0, x1), (y0, y1), ppm = spec["x"], spec["y"], spec["ppm"]
    w, h = int(round((x1 - x0) * ppm)), int(round((y1 - y0) * ppm))
    X = (x0 + (np.arange(w) + 0.5) / ppm)[None, :].astype(np.float32) * np.ones((h, 1), np.float32)
    Y = (y1 - (np.arange(h) + 0.5) / ppm)[:, None].astype(np.float32) * np.ones((1, w), np.float32)
    return X, Y


# ---------------------------------------------------------------- 门、立柱、墙

POST_STATS = (0.30, 0.085)                  # 立柱亮度的均值与标准差
LEAF_STATS = (0.27, 0.070)                  # 门板


def _hipass_boost(rgb, k, s):
    """放大木纹的高频起伏，让平整的木板显得更风化。"""
    lum = rgb @ LUMA
    d = lum - gaussian_filter(lum, s)
    return np.clip(rgb * (1 + (k - 1) * d / np.maximum(lum, 0.05))[..., None], 0, 1)


def _grime(X, Y):
    """整扇门共用的一层污渍：低频的明暗起伏，把不同来源的木板统一起来。"""
    def n(f, seed):
        rng = np.random.default_rng(seed)
        g = rng.normal(0, 1, (64, 64)).astype(np.float32)
        g = gaussian_filter(g, 2.0, mode="wrap")
        g /= g.std() + 1e-6
        import cv2
        u = ((X * f) % 1.0 * 64).astype(np.float32)
        v = ((Y * f) % 1.0 * 64).astype(np.float32)
        return cv2.remap(g, u, v, cv2.INTER_CUBIC, borderMode=cv2.BORDER_WRAP)
    return 1.0 + 0.10 * n(0.9, 11) + 0.06 * n(3.1, 12)


def _base(X, Y):
    """门扇（竖向木板）、门框立柱（一整块宽木）和石墙的反照率。"""
    planks = _tex(PLANKS, rot=True)
    # 木板贴图（旋转后）的接缝在第 524、961、1426、1816 … 列：门扇按每米一块贴图、让接缝落在 x = 0；
    # 立柱按每两米一块贴图、取第 1426–1816 列那一块宽 0.203 米的木板，正好占满立柱
    leaf = _sample(planks, X, Y, 1.0, ox=-524 / 3840, oy=0.62)
    post = _sample(planks, X, Y, 2.0, ox=-0.205 - 2 * 1426 / 3840, oy=1.31)
    rock = _sample(_tex(ROCK), X, Y, 1.6, ox=0.3, oy=0.2)
    leaf = _match(_stylize(leaf, 0.30, (1.0, 0.93, 0.83)), *LEAF_STATS)
    post = _match(_stylize(_hipass_boost(post, 2.2, 6.0), 0.18, (0.98, 0.95, 0.90)), *POST_STATS)
    rock = _stylize(rock, 0.15, (0.92, 0.94, 0.96), 0.62)
    is_wall = (X < WALL_X).astype(np.float32)
    is_post = ((X >= WALL_X) & (X < 0.0)).astype(np.float32)
    rgb = rock * is_wall[..., None] + post * is_post[..., None] + leaf * (1 - is_wall - is_post)[..., None]
    # 接缝：墙与立柱之间、立柱与门扇之间各一道暗缝
    for x, wd in ((WALL_X + 0.004, 0.006), (0.001, 0.0035)):
        seam = np.exp(-((X - x) / wd) ** 2)
        rgb *= (1 - 0.85 * seam)[..., None]
    # 门扇和立柱的下半部常年受潮，颜色深一些
    damp = smooth01(-Y, 0.2, 0.9)
    rgb *= ((1 - 0.25 * damp) * _grime(X, Y))[..., None]
    return np.clip(rgb, 0, 1).astype(np.float32)


def _hasp_photo():
    """搭扣照片：去掉门扇红漆的颜色，立柱和门扇两部分的亮度分别与两侧的木板统一。
    返回 (rgb, alpha)；alpha 是边缘羽化的不规则形状。"""
    import cv2
    im = load_rgb(HASP)
    h, w = im.shape[:2]
    lum = im @ LUMA
    red = np.clip((im[..., 0] - im[..., 1]) - 0.12, 0, 1)              # 红漆处
    rm = gaussian_filter(smooth01(red, 0.0, 0.12), 3)[..., None]
    rgb = _stylize(im, 0.30, (1.0, 0.93, 0.83)) * (1 - rm) + _stylize(im, 0.10, (1.0, 0.93, 0.83)) * rm
    rust = smooth01((im[..., 0] - im[..., 2]), 0.18, 0.35) * smooth01(-lum, -0.55, -0.25)
    rgb = rgb * (1 - rust[..., None]) + _stylize(im, 0.55, (1.0, 0.92, 0.80)) * rust[..., None]
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    left = xx < HASP_ORIGIN[0]
    clean_l = left & ((yy < 850) | (yy > 1900))                        # 统计时避开铁件
    clean_r = ~left & ((yy < 280) | (yy > 1950)) & (xx > 2300)
    out = rgb.copy()
    out[left] = _match(rgb, *POST_STATS, ref_mask=clean_l)[left]
    out[~left] = _match(rgb, *LEAF_STATS, ref_mask=clean_r)[~left]
    sm = gaussian_filter(left.astype(np.float32), 6)[..., None]          # 两部分之间平滑过渡
    rgb = out * 1.0
    X = (xx - HASP_ORIGIN[0]) / HASP_PPM
    Y = -(yy - HASP_ORIGIN[1]) / HASP_PPM
    rgb = np.clip(rgb * _grime(X, Y)[..., None], 0, 1)
    rng = np.random.default_rng(5)
    n = gaussian_filter(rng.normal(0, 1, (h // 8 + 1, w // 8 + 1)), 6)
    n = cv2.resize((n / (n.std() + 1e-6)).astype(np.float32), (w, h), interpolation=cv2.INTER_LINEAR)
    d = np.minimum.reduce([xx, w - 1 - xx, yy, h - 1 - yy]) + n * 90
    alpha = smooth01(d, 40, 520)
    return rgb.astype(np.float32), alpha.astype(np.float32)


def _paste_hasp(rgb, X, Y):
    """把搭扣照片按世界坐标贴到画布上（羽化边缘）。"""
    import cv2
    hrgb, ha = _hasp_photo()
    mx = (X * HASP_PPM + HASP_ORIGIN[0]).astype(np.float32)
    my = (-Y * HASP_PPM + HASP_ORIGIN[1]).astype(np.float32)
    src = np.dstack([hrgb, ha])
    if HASP_PPM > 2 * (X.shape[1] / (X[0, -1] - X[0, 0])):           # 画布分辨率低时先缩小照片，避免锯齿
        k = HASP_PPM / (X.shape[1] / (X[0, -1] - X[0, 0]))
        src = cv2.resize(src, (int(src.shape[1] / k), int(src.shape[0] / k)), interpolation=cv2.INTER_AREA)
        mx, my = mx / k, my / k
    s = cv2.remap(src, mx, my, cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    a = s[..., 3:4]
    return rgb * (1 - a) + s[..., :3] * a


def _bump(rgb, ppm):
    """由亮度的高频部分近似出高度：木纹的沟、钉孔和搭扣的边缘在灯光下有明暗。"""
    lum = rgb @ LUMA
    s = max(ppm / 900.0, 1.0)
    hgt = lum - gaussian_filter(lum, 3.0 * s)
    hgt = gaussian_filter(hgt, 0.6 * s)
    return np.clip(hgt * 2.0 + 0.5, 0, 1).astype(np.float32)


def canvas(which):
    """门面贴图：which 取 "wide"（大范围）或 "mid"（中间一块）。返回 (rgb uint8, 高度 uint8, spec)。"""
    spec = WIDE if which == "wide" else MID

    def make():
        X, Y = _grid(spec)
        rgb = _base(X, Y)
        rgb = _paste_hasp(rgb, X, Y)
        b = _bump(rgb, spec["ppm"])
        out = np.dstack([rgb, b])
        return (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)
    a = disk_cache(f"door_{which}", make, VERSION)
    return a[..., :3], a[..., 3], spec


def mid_alpha():
    """中间一块贴图的羽化 alpha：叠在大范围贴图上，边缘看不出分辨率的差别。"""
    def make():
        X, Y = _grid(MID)
        (x0, x1), (y0, y1) = MID["x"], MID["y"]
        d = np.minimum.reduce([X - x0, x1 - X, Y - y0, y1 - Y])
        return (smooth01(d, 0.0, 0.06) * 255).astype(np.uint8)
    return disk_cache("door_mid_alpha", make, VERSION)


def hasp_patch():
    """搭扣照片本身（每米 9100 像素），叠在中间一块之上，近看锁时更清楚。返回 (rgba uint8, 高度 uint8, 中心, 尺寸)。"""
    def make():
        rgb, a = _hasp_photo()
        b = _bump(rgb, HASP_PPM)
        out = np.dstack([rgb, a, b])
        return (np.clip(out, 0, 1) * 255 + 0.5).astype(np.uint8)
    a = disk_cache("door_hasp", make, VERSION)
    h, w = a.shape[:2]
    cx = (w / 2 - HASP_ORIGIN[0]) / HASP_PPM
    cy = -(h / 2 - HASP_ORIGIN[1]) / HASP_PPM
    return a[..., :4], a[..., 4], (cx, cy), (w / HASP_PPM, h / HASP_PPM)


# ---------------------------------------------------------------- 锁片与锁孔

def escutcheon():
    """黄铜锁片（RGBA float32，直通 alpha，锁孔处透明）与锁孔轮廓。
    返回 (rgba, 锁孔多边形 (N, 2)，坐标为锁片贴图的 0–1 坐标（u 向右、v 向下）)。"""
    def make():
        import cv2
        im = load_rgb(ESC)
        h, w = im.shape[:2]
        # 黄铜偏黄（红通道明显高于蓝通道），背景和它投下的影子都是中性灰：按这一点分开
        warm = gaussian_filter(im[..., 0] - im[..., 2], 1.5)
        fg = warm > 0.10
        lab, n = label(fg)
        sizes = np.bincount(lab.ravel())
        sizes[0] = 0
        plate = binary_fill_holes(lab == sizes.argmax())
        ys, xs = np.nonzero(plate)
        y0, y1, x0, x1 = ys.min() - 40, ys.max() + 40, xs.min() - 40, xs.max() + 40
        im, warm = im[y0:y1, x0:x1], warm[y0:y1, x0:x1]
        plate = plate[y0:y1, x0:x1]
        dist = 1.0 - np.clip(warm / 0.10, 0, 1) * 0.2
        # 锁孔：锁片内部、颜色接近背景的最大连通区域；两个螺丝孔也是背景色，单独补成暗色的螺丝头
        from scipy.ndimage import binary_opening, binary_closing
        inner = plate & (gaussian_filter(warm, 3.0) < 0.15)
        inner = binary_closing(binary_opening(inner, iterations=2), iterations=3)
        lab, n = label(inner)
        sizes = np.bincount(lab.ravel())
        sizes[0] = 0
        hole = lab == sizes.argmax()
        screws = inner & ~hole
        a = gaussian_filter(plate.astype(np.float32), 1.0)
        a = np.where(hole, 0.0, a)
        a = gaussian_filter(np.where(hole, 0.0, a), 0.7)
        rgb = im.copy()
        sc = gaussian_filter(screws.astype(np.float32), 2.0)
        rgb = rgb * (1 - sc[..., None]) + np.array([0.10, 0.08, 0.05]) * sc[..., None]
        # 黄铜略去一点饱和度，和旧木门统一
        lum = rgb @ LUMA
        rgb = lum[..., None] + (rgb - lum[..., None]) * 0.75
        cs, _ = cv2.findContours(hole.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
        c = max(cs, key=len)[:, 0, :].astype(np.float32)
        hh, ww = a.shape
        poly = np.c_[c[:, 0] / ww, c[:, 1] / hh]
        return np.dstack([rgb, a]).astype(np.float32), poly
    p = CACHE / f"esc_v{VERSION}.npz"
    if p.exists():
        z = np.load(p)
        return z["rgba"], z["poly"]
    rgba, poly = make()
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez(p, rgba=rgba, poly=poly)
    return rgba, poly


def esc_geometry():
    """锁片平面的尺寸（米），以及锁孔在世界坐标里的多边形与圆心。"""
    rgba, poly = escutcheon()
    h, w = rgba.shape[:2]
    # 锁片本体高 ESC_H；贴图四周各多出 40 像素
    ys = np.nonzero(rgba[..., 3].max(1) > 0.5)[0]
    ppm = (ys.max() - ys.min()) / ESC_H
    size = (w / ppm, h / ppm)
    wx = ESC_C[0] + (poly[:, 0] - 0.5) * size[0]
    wy = ESC_C[1] - (poly[:, 1] - 0.5) * size[1]
    world = np.c_[wx, wy]
    # 锁孔上部圆孔的圆心：取孔的上三分之一的形心
    top = world[:, 1] > world[:, 1].max() - (world[:, 1].max() - world[:, 1].min()) * 0.38
    circ = world[top].mean(0)
    return size, world, circ


def keyhole_path(center, size, smooth=True):
    """锁孔在某个平面上的 skia 路径（平面的 0–1 坐标，u 向右、v 向下）；center、size 为该平面的中心与尺寸。"""
    import skia
    _, world, _ = esc_geometry()
    u = (world[:, 0] - center[0]) / size[0] + 0.5
    v = 0.5 - (world[:, 1] - center[1]) / size[1]
    p = skia.Path()
    step = 3 if smooth else 1
    pts = list(zip(u[::step], v[::step]))
    p.moveTo(*map(float, pts[0]))
    for q in pts[1:]:
        p.lineTo(*map(float, q))
    p.close()
    return p


if __name__ == "__main__":
    for which in ("wide", "mid"):
        rgb, b, spec = canvas(which)
        print(which, rgb.shape)
        k = max(1, rgb.shape[1] // 1600)
        save_png(rgb[::k, ::k] / 255.0, OUT / "assets" / f"door_{which}.png")
        save_png(b[::k, ::k] / 255.0, OUT / "assets" / f"door_{which}_bump.png")
    rgba, poly = escutcheon()
    print("esc", rgba.shape, len(poly))
    save_png(rgba[::3, ::3], OUT / "assets" / "door_esc.png")
    size, world, circ = esc_geometry()
    print("esc size", size, "keyhole circle", circ, "keyhole bbox", world.min(0), world.max(0))
