"""L06 的白云骑士：从古斯塔夫·多雷 1863 年为《堂吉诃德》画的版画里抠出骑马持矛的骑士（公有领域，
Commons："Gustave Doré - Dom Quixote - Parte 1 - Cap 2 - 1.jpg"）。

原图里骑士朝左，背后是房子、树和地上的杂物，线条与背景的线条连在一起，不能按颜色抠。做法分三步：先手工
沿骑士和马的外轮廓描一个多边形（坐标是 1920 宽缩略图上的像素，留出几个像素的余量）；再从多边形边界往里
沿着白纸做泛洪填充，把轮廓线外侧残留的白纸去掉，填充只走离边界 22 像素以内的地方，并且先把墨线加粗两像素
堵住缺口，免得漏进马身上大片的白纸；最后把长矛单独取出来，成为可以转动、脱手的另一张贴图。整张图左右翻转，
骑士朝右，沿云顶从左往右走。

调色按正午逆光：太阳在骑士身后的右上方，骑士几乎是剪影，白纸处压成暖褐色，墨线更深，轮廓朝太阳的一侧镶
一道窄的奶油色亮边。版画的线条保留，所以近看仍是木口版画的排线。
"""
import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

from common import IMG, cached, disk, save_png

PHOTO = "Gustave_Doré_-_Dom_Quixote_-_Parte_1_-_Cap_2_-_1.jpg"

# 骑士与马的外轮廓（原图坐标，顺时针，自头盔顶起）
BODY = [
    (1086, 158), (1112, 156), (1124, 170), (1124, 196), (1114, 210), (1114, 234), (1126, 244), (1126, 272), (1120, 284),
    (1128, 300), (1134, 330), (1132, 360), (1122, 384),
    (1135, 392), (1165, 382), (1205, 388), (1240, 398),
    (1262, 404), (1295, 418), (1322, 445), (1342, 480), (1350, 520), (1344, 548), (1325, 530), (1300, 495), (1270, 470),
    (1250, 462),
    (1248, 500), (1244, 535), (1236, 560), (1226, 585), (1228, 612), (1218, 620), (1200, 612), (1204, 590), (1212, 560),
    (1210, 530),
    (1192, 520), (1178, 540), (1170, 565), (1158, 590), (1150, 610), (1138, 632),
    (1112, 640), (1104, 628), (1118, 612), (1130, 590), (1140, 560), (1145, 535),
    (1120, 520), (1100, 515), (1090, 525),
    (1088, 600), (1078, 604),
    (1068, 583), (1052, 580),
    (1035, 585), (1010, 588), (985, 590), (960, 585), (950, 575), (945, 545), (940, 510),
    (935, 470), (925, 440),
    (906, 408), (892, 398),
    (872, 396), (855, 382), (850, 365), (858, 345), (866, 330), (872, 300), (876, 268), (880, 252), (890, 262), (900, 275),
    (915, 290), (935, 300), (955, 320), (970, 340), (985, 350),
    (995, 280), (985, 262), (978, 240), (985, 228), (1000, 232), (1012, 246), (1030, 252), (1055, 248), (1076, 240),
    (1080, 225), (1078, 200), (1080, 178),
]
LANCE = ((880.0, 26.0), (990.0, 255.0))          # 长矛：矛尖与握手处
LANCE_W = 7.0
BOX = (840, 20, 1360, 650)                        # 裁切范围


def _gray():
    return np.asarray(Image.open(IMG / PHOTO).convert("L"), np.float32) / 255


def _poly_mask(pts, shape):
    im = Image.new("L", (shape[1], shape[0]), 0)
    ImageDraw.Draw(im).polygon([tuple(p) for p in pts], fill=255)
    return np.asarray(im, np.float32) / 255


def _lance_mask(shape, w=LANCE_W, extend=0.0):
    (x0, y0), (x1, y1) = LANCE
    d = np.array([x1 - x0, y1 - y0])
    L = np.hypot(*d)
    u = d / L
    nrm = np.array([-u[1], u[0]])
    p0 = np.array([x0, y0]) - u * 4
    p1 = np.array([x1, y1]) + u * extend
    q = [p0 + nrm * w / 2, p1 + nrm * w / 2, p1 - nrm * w / 2, p0 - nrm * w / 2]
    return _poly_mask(q, shape)


def masks():
    """(身体遮罩, 长矛遮罩)，原图尺寸，0–1。"""
    def make():
        g = _gray()
        ink = g < 0.55
        poly = _poly_mask(BODY, g.shape) > 0.5
        # 从多边形边界往里沿白纸泛洪：墨线先加粗两像素堵住缺口；只去掉离边界 22 像素以内的白纸
        wall = ndimage.binary_dilation(ink, iterations=2)
        free = poly & ~wall
        edge = poly & ~ndimage.binary_erosion(poly, iterations=1)
        lab, n = ndimage.label(free)
        touch = np.unique(lab[edge & free])
        touch = touch[touch > 0]
        dist = ndimage.distance_transform_edt(poly)
        outside = np.isin(lab, touch) & (dist < 22)
        body = poly & ~outside
        # 加粗墨线后被去掉的白纸边，再把紧贴的墨线补回来
        body = ndimage.binary_closing(body, iterations=2) & poly
        body = ndimage.binary_fill_holes(body)
        lance = _lance_mask(g.shape) > 0.5
        body &= ~lance
        bm = ndimage.gaussian_filter(body.astype(np.float32), 0.7)
        lm = ndimage.gaussian_filter(lance.astype(np.float32), 0.6)
        return np.stack([bm, lm])
    return disk("knight_masks", make, BODY, LANCE, "m2")


SUN2D = np.array([0.45, -0.89])                   # 翻转后图像里太阳的方向（x 向右、y 向下）：右上方


def _style(g, a):
    """把版画按正午逆光调色：白纸压成暖褐，墨线更深，朝太阳的轮廓镶一道亮边。g 为灰度，a 为遮罩（都已翻转）。
    返回直通 alpha 的 RGBA（亮边处超过 1）。"""
    ink = np.clip((0.70 - g) / 0.45, 0, 1)
    paper = np.array([0.33, 0.26, 0.20])
    line = np.array([0.085, 0.060, 0.045])
    col = paper * (1 - ink[..., None]) + line * ink[..., None]
    # 离轮廓的距离与轮廓的朝向：亮边只在朝太阳的一侧，宽约三个像素
    inside = a > 0.5
    d = ndimage.distance_transform_edt(inside)
    ga = ndimage.gaussian_filter(a, 2.0)
    gy, gx = np.gradient(ga)
    nrm = -np.stack([gx, gy], -1)
    nrm /= np.linalg.norm(nrm, axis=-1, keepdims=True) + 1e-6
    facing = np.clip(nrm @ SUN2D, 0, 1)
    facing = ndimage.gaussian_filter(facing, 2.0)
    rim = np.exp(-d / 2.6) * facing
    wrap = np.exp(-d / 9.0) * 0.30                  # 逆光在轮廓四周漫过来的一点天光
    col = col * (1 + wrap[..., None]) + np.array([1.75, 1.45, 1.00]) * (rim * (1 - 0.5 * ink))[..., None]
    return np.dstack([col, a]).astype(np.float32)


def textures():
    """(骑士 RGBA, 长矛 RGBA, 握手处在贴图里的像素位置, 矛尖的像素位置)，都已左右翻转、裁到 BOX。"""
    def make():
        g = _gray()
        m = masks()
        x0, y0, x1, y1 = BOX
        gg = g[y0:y1, x0:x1][:, ::-1]
        mb = m[0][y0:y1, x0:x1][:, ::-1].copy()
        # 马胸下面那道裁切线是直的：最下面 26 像素逐渐淡出，看起来是前腿隐进了云气里，而不是被截断
        rows = np.arange(mb.shape[0]) + y0
        fade = np.clip((592 - rows) / 26.0, 0, 1)[:, None]
        cols = np.arange(mb.shape[1])
        front = ((cols > 250) & (cols < 450))[None, :]          # 只淡出前腿那一段（翻转后的坐标）
        mb = np.where(front, mb * fade, mb)
        body = _style(gg, mb)
        lance = _style(gg, m[1][y0:y1, x0:x1][:, ::-1])
        return np.stack([body, lance])
    arr = disk("knight_tex", make, BODY, LANCE, BOX, "t2")
    x0, y0, x1, y1 = BOX
    w = x1 - x0
    (lx0, ly0), (lx1, ly1) = LANCE
    tip = (w - (lx0 - x0), ly0 - y0)
    hand = (w - (lx1 - x0), ly1 - y0)
    return arr[0], arr[1], hand, tip


def check():
    g = _gray()
    m = masks()
    x0, y0, x1, y1 = BOX
    rgb = np.dstack([g, g, g])[y0:y1, x0:x1]
    bg = np.array([0.55, 0.35, 0.45])
    a = np.clip(m[0] + m[1], 0, 1)[y0:y1, x0:x1, None]
    out = bg * (1 - a) + rgb * a
    big = np.asarray(Image.fromarray((out * 255).astype(np.uint8)).resize(((x1 - x0) * 2, (y1 - y0) * 2), Image.LANCZOS))
    save_png(big / 255.0, "knight_cut.png")


if __name__ == "__main__":
    check()
