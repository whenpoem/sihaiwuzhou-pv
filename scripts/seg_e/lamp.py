"""L19 的晚灯：一盏点着的马灯（防风煤油灯），抠自真实照片，灯芯另用一张真实火焰照片重新点亮。

灯取自 বাক্যবাগীশ 拍摄的"Kerosene lamp (Hurricane lamp)"（Wikimedia Commons，CC BY-SA 4.0，
assets/images/Kerosene_lamp_Hurricane_lamp_20200521190149.jpg）：夜里点着的马灯挂在一扇旧门前，正面平视，玻璃罩
被火光照成一片过曝的白，两侧的立管和上面的灯帽被照出暖色的边，提梁垂在灯下。照片的背景是门，所以要把灯抠出来：
灯帽和立管是深色的金属，背景也暗，单靠亮度分不开，这里先按照片手工勾出灯体的轮廓（灯帽、两根立管、玻璃罩），
再交给 GrabCut 在轮廓附近细化；细细的提梁另用"比周围亮的细线"检测出来。

照片里玻璃罩整片过曝，看不见火苗。做法是把玻璃罩的亮度压下来，保留玻璃上的污迹和反光，再在灯芯的位置叠一张
真实的火焰照片（Arivumathi 拍摄的"kerosene lamp flame"，CC0，assets/images/_kerosene_lamp_flame.jpg，黑底上
一束煤油灯火苗），火苗按加法叠加、随时间轻轻摇曳，玻璃罩的亮度跟着火苗一起起伏。

输出都是 0–1 的 float32 数组，第 0 行是图像顶部，缓存在 data/cache/seg_e/lamp_*。坐标：像素在照片原图
（3024 × 4032）里量取，PPU 为每米的像素数（玻璃罩高 1490 像素，按实物约 13 厘米）。
"""
import numpy as np
from scipy.ndimage import gaussian_filter, binary_dilation, binary_erosion, label

from common import CACHE, LUMA, disk_cache, load_rgb, save_png, OUT

PHOTO = "Kerosene_lamp_Hurricane_lamp_20200521190149.jpg"
FLAME_PHOTO = "_kerosene_lamp_flame.jpg"
CROP = (600, 640, 2560, 3520)            # 灯在原图里的范围 (x0, y0, x1, y1)：灯帽顶到提梁最低点
PPU = 11500.0                            # 每米像素数
FLAME_PX = (1505, 2760)                  # 灯芯（火苗底部）在原图里的位置
GLOBE = (1000, 1640, 2010, 3130)         # 玻璃罩的范围
HANG_PX = (1545, 690)                    # 灯帽顶的挂环位置
VERSION = 3

# 灯体各部分的轮廓（原图像素）。立管与玻璃罩之间的空隙里露出的是照片的背景，要挖掉，所以分部件勾画再合并。
CAP = [(1200, 712), (1500, 700), (1830, 712), (1885, 760), (1905, 830), (1925, 990), (1945, 1060),
       (1990, 1130), (2050, 1205), (2140, 1215), (2185, 1180), (2240, 1220), (2265, 1330), (2250, 1420),
       (2150, 1440), (2060, 1540), (1960, 1600), (1860, 1615), (1860, 1735), (1170, 1735), (1165, 1610),
       (1040, 1565), (960, 1500), (880, 1430), (780, 1430), (700, 1390), (690, 1260), (750, 1200), (830, 1215),
       (900, 1240), (990, 1200), (1060, 1180), (1110, 1120), (1170, 1060), (1190, 1040), (1190, 880),
       (1150, 830), (1115, 780)]
TUBE_L = [(845, 1420), (900, 1385), (968, 1420), (968, 2950), (1005, 3000), (995, 3065), (900, 3065),
          (860, 3010), (845, 2950)]
TUBE_R = [(1998, 1400), (2060, 1370), (2128, 1400), (2128, 2960), (2145, 3005), (2100, 3025), (2000, 3015),
          (1985, 2960), (1998, 2900)]
GLASS = [(1170, 1730), (1860, 1730), (1885, 1900), (1940, 2200), (1955, 2500), (1935, 2800), (1880, 3000),
         (1800, 3100), (1600, 3152), (1400, 3152), (1200, 3100), (1080, 3010), (1012, 2800), (1000, 2500),
         (1030, 2200), (1090, 2000), (1120, 1850)]
# 提梁经过的路线（左耳 → 灯下最低点 → 右耳）
BAIL = [(765, 1400), (746, 1520), (742, 2200), (746, 2850), (834, 3063), (996, 3196), (1264, 3330),
        (1569, 3406), (1700, 3430), (1760, 3445), (1817, 3410), (2027, 3254), (2294, 3044), (2400, 2834),
        (2409, 2509), (2380, 2223), (2314, 1936), (2240, 1700), (2215, 1500), (2215, 1420)]


def _poly_mask(shape, pts, ox=0, oy=0):
    import cv2
    m = np.zeros(shape, np.uint8)
    cv2.fillPoly(m, [np.array([(x - ox, y - oy) for x, y in pts], np.int32)], 1)
    return m


def _polyline_mask(shape, pts, width, ox=0, oy=0, smooth=True):
    """沿一串点画线；smooth 时先用样条把折线拉成平滑曲线。"""
    import cv2
    from scipy.interpolate import splprep, splev
    p = np.array(pts, float)
    if smooth and len(p) > 3:
        tck, _ = splprep([p[:, 0], p[:, 1]], s=len(p) * 40.0)
        u = np.linspace(0, 1, 600)
        x, y = splev(u, tck)
        p = np.c_[x, y]
    m = np.zeros(shape, np.uint8)
    cv2.polylines(m, [np.round(p - [ox, oy]).astype(np.int32)], False, 1, width, cv2.LINE_AA)
    return m


def _cutout():
    """返回裁剪后的 RGBA（直通 alpha）。"""
    import cv2
    im = load_rgb(PHOTO)
    x0, y0, x1, y1 = CROP
    im = im[y0:y1, x0:x1]
    h, w = im.shape[:2]
    lum = im @ LUMA
    cap = _poly_mask((h, w), CAP, x0, y0).astype(np.float32)
    parts = np.maximum.reduce([_poly_mask((h, w), p, x0, y0) for p in (TUBE_L, TUBE_R, GLASS)]).astype(np.float32)
    # 灯帽上半部分是深色金属压在较亮的背景上：在轮廓附近按亮度细分（背景约 0.07–0.09，灯帽约 0.03–0.04）
    yy = np.arange(h)[:, None] + y0
    soft_cap = gaussian_filter(binary_dilation(cap > 0.5, iterations=12).astype(np.float32), 3)
    # 背景是偏青的门（绿通道高于红通道，或者更亮），灯帽是红绿相等的深蓝灰
    gr = gaussian_filter(im[..., 1] - im[..., 0], 2.5)
    bg = np.maximum(np.clip((gr - 0.004) / 0.010, 0, 1), np.clip((gaussian_filter(lum, 2.5) - 0.075) / 0.02, 0, 1))
    dark = 1.0 - bg
    upper = np.clip((1500 - yy) / 60.0, 0, 1)
    core = gaussian_filter(binary_erosion(cap > 0.5, iterations=16).astype(np.float32), 2)
    cap_a = np.maximum(core, soft_cap * dark) * upper + cap * (1 - upper)
    body = np.clip(np.maximum(cap_a, gaussian_filter(parts, 1.5)), 0, 1)
    # 提梁：沿路线画一根 7 像素的暗铁丝，照片里被火光照亮的那几段（比周围亮的细线）原样保留
    k = 15
    opened = cv2.morphologyEx(lum, cv2.MORPH_OPEN, np.ones((k, k), np.uint8))
    ridge = np.clip((lum - opened - 0.03) * 8.0, 0, 1)
    band = gaussian_filter(_polyline_mask((h, w), BAIL, 26, x0, y0).astype(np.float32), 3)
    lit = np.clip(ridge * band, 0, 1)
    line = gaussian_filter(_polyline_mask((h, w), BAIL, 7, x0, y0).astype(np.float32), 1.2)
    wire_a = np.clip(np.maximum(line * 0.9, lit), 0, 1) * (1 - body)
    wire_rgb = np.where(lit[..., None] > 0.05, im, np.array([0.035, 0.03, 0.03], np.float32))
    a = np.clip(body + wire_a, 0, 1)
    rgb = (im * body[..., None] + wire_rgb * wire_a[..., None]) / np.maximum(a, 1e-4)[..., None]
    return np.dstack([rgb, a]).astype(np.float32)


def lamp_layers():
    """灯的三层贴图（与 CROP 同尺寸）：
    0–3 base：不发光的部分（灯帽、立管、提梁），RGBA；颜色是照片里被火光照亮的样子，画时按火光强弱整体调亮暗；
    4 glass：玻璃罩（覆盖率），亮度压到原来的一半左右，保留污迹，按加法叠加、随火苗起伏；
    5 rim：金属上被火光照亮的暖色边（覆盖率），随火苗起伏。"""
    def make():
        rgba = _cutout()
        im, a = rgba[..., :3], rgba[..., 3]
        x0, y0, x1, y1 = CROP
        h, w = a.shape
        lum = im @ LUMA
        gx0, gy0, gx1, gy1 = GLOBE
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        # 玻璃罩区域：椭圆形，略收在罩子里面；罩内亮度高的像素算作"发光的玻璃"
        cx, cy = (gx0 + gx1) / 2 - x0, (gy0 + gy1) / 2 - y0 + 60
        rx, ry = (gx1 - gx0) / 2 * 0.98, (gy1 - gy0) / 2 * 1.0
        ell = np.clip((1.0 - np.hypot((xx - cx) / rx, (yy - cy) / ry)) * 18, 0, 1)
        glow = ell * np.clip((lum - 0.35) / 0.5, 0, 1)
        glow = gaussian_filter(glow, 2.0)
        # 过曝的白里没有细节：把亮度压缩，过曝处换成从罩子边缘向中心渐亮的暖色，让后加的火苗看得见
        detail = np.clip(lum - gaussian_filter(lum, 18), -0.2, 0.2)
        d = np.hypot((xx - (FLAME_PX[0] - x0)) / (rx * 1.15), (yy - (FLAME_PX[1] - y0 - 280)) / (ry * 1.0))
        core = np.exp(-d ** 2 * 1.6)
        glass = np.clip((0.30 + 0.55 * core) * glow + detail * 1.5 * glow, 0, 1.2)
        # 不发光的部分：去掉玻璃罩的发光，金属保持照片里的颜色
        base_rgb = im * (1 - glow[..., None] * 0.92)
        base_a = a * (1 - glow * 0.85)
        # 金属上的暖色亮边：灯体内、玻璃罩外、亮度较高的地方
        warm = (im[..., 0] - im[..., 2]) > 0.08
        rim = np.clip((lum - 0.18) / 0.5, 0, 1) * warm * a * (1 - glow)
        out = np.dstack([base_rgb, base_a, glass, rim]).astype(np.float32)
        return out
    return disk_cache("lamp_layers", make, VERSION)


def flame_sprite():
    """火苗（RGB，黑底，加法叠加）：取照片里的火苗，裁到火苗外接框，底部的蓝色焰心保留。
    返回 (rgb, 火苗底部在贴图里的相对位置 (u, v), 火苗高度占贴图高度的比例)。"""
    def make():
        im = load_rgb(FLAME_PHOTO)
        lum = im @ LUMA
        ys, xs = np.nonzero(lum > 0.22)
        cy0, cy1 = ys.min(), ys.max()
        cx = int(np.median(xs))
        hh = cy1 - cy0
        pad = int(hh * 0.25)
        y0, y1 = max(cy0 - pad, 0), min(cy1 + pad, im.shape[0])
        half = int(hh * 0.45)
        x0, x1 = max(cx - half, 0), min(cx + half, im.shape[1])
        f = im[y0:y1, x0:x1]
        f = np.clip(f - 0.03, 0, None)                # 黑底压到 0，加法叠加时不发灰
        # 四周羽化，防止裁切边露出来
        h, w = f.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w] / np.array([h - 1, w - 1])[:, None, None]
        edge = np.clip(np.minimum.reduce([xx, 1 - xx, yy, 1 - yy]) * 8, 0, 1)
        f = f * edge[..., None]
        meta = np.array([(cx - x0) / w, (cy1 - y0) / h, hh / h, w / h], np.float32)
        return np.concatenate([f.reshape(-1), meta]).astype(np.float32), f.shape
    p = CACHE / f"flame_v{VERSION}.npz"
    if p.exists():
        z = np.load(p)
        return z["rgb"], tuple(z["meta"][:2]), float(z["meta"][2]), float(z["meta"][3])
    flat, shape = make()
    rgb = flat[:-4].reshape(shape)
    meta = flat[-4:]
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez(p, rgb=rgb, meta=meta)
    return rgb, tuple(meta[:2]), float(meta[2]), float(meta[3])


def px_to_local(px, py):
    """原图像素 → 以火苗为原点的米制坐标（y 向上）。"""
    return ((px - FLAME_PX[0]) / PPU, -(py - FLAME_PX[1]) / PPU)


def crop_geometry():
    """灯贴图平面的中心（相对火苗，米）与尺寸（米）。"""
    x0, y0, x1, y1 = CROP
    return px_to_local((x0 + x1) / 2, (y0 + y1) / 2), ((x1 - x0) / PPU, (y1 - y0) / PPU)


if __name__ == "__main__":
    L = lamp_layers()
    print(L.shape)
    save_png(L[..., :4], OUT / "assets" / "lamp_01_base.png", gain=2.0)
    save_png(L[..., 4], OUT / "assets" / "lamp_02_glass.png")
    save_png(L[..., 5], OUT / "assets" / "lamp_03_rim.png")
    rgb, base, hfrac, aspect = flame_sprite()
    print(rgb.shape, base, hfrac, aspect)
    save_png(rgb, OUT / "assets" / "lamp_04_flame.png")
