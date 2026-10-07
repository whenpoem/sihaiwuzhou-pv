"""L15 地上那块单车形状的干地：轮廓按飞鸽自行车的侧面照片描出。

照片（assets/images/Left_side_of_Flying_Pigeon.jpg，齐健摄，CC BY 2.0）里车身、轮胎、挡泥板、链罩、车筐都是黑色，
对灰色路面取暗部阈值就能得到它们的轮廓；镀铬的车把、车铃、后货架和车座在阈值里缺失或混进背景，按照片上量出的
位置补画。背景里的树、面包车和左边另一辆车用一个包住单车的多边形排除。辐条是很细的亮线，单车在地上躺了很久，
辐条下面也留着一道道细细的干痕，所以按照片上的轮心和半径补画成细线。

单车平躺在地上留下的干地，从正上方看就是它的侧影。结果是 0–1 的覆盖率（1 为干），宽 2400 像素，
对应车身全长约 1.86 米（照片里车长约 3420 像素）。
"""
import numpy as np
import skia
from PIL import Image
from scipy import ndimage

from common import IMG, disk_cached

PHOTO = IMG / "Left_side_of_Flying_Pigeon.jpg"
TH = 3556 / 1200            # 缩略图坐标 → 原图坐标

# 照片上量出的部件位置（缩略图坐标 1200×800，乘 TH 得原图坐标）。暗部阈值只在这些部件附近保留，
# 车架三角里、车轮里透出的面包车和树因此被排除。
TUBES = [((440, 238), (772, 240)),       # 上管
         ((395, 322), (612, 563)),       # 下管
         ((772, 240), (617, 560)),       # 立管
         ((617, 565), (940, 517)),       # 后下叉
         ((776, 246), (940, 517)),       # 后上叉
         ((392, 236), (378, 334)),       # 车头管
         ((372, 330), (206, 545)),       # 前叉
         ((612, 566), (522, 600))]       # 曲柄
BASKET = [(196, 98), (488, 200), (452, 300), (420, 335), (352, 348), (205, 262), (192, 150)]
GUARD = [(536, 522), (612, 478), (760, 478), (945, 488), (955, 566), (760, 594), (640, 628), (552, 612)]
PEDAL = [(492, 580), (552, 580), (552, 622), (492, 622)]
FENDER_REAR = [(700, 470), (720, 360), (820, 300), (940, 282), (1060, 300), (1150, 380), (1172, 480),
               (1120, 470), (1100, 400), (1010, 330), (940, 318), (860, 330), (760, 400), (735, 480)]
FENDER_FRONT = [(292, 332), (340, 340), (372, 420), (370, 545), (340, 548), (338, 430), (318, 365)]
# 轮胎：在原图上对暗部拟合的椭圆（中心、两轴全长、转角），见 _wheels
WHEELS = [((602.8, 1610.4), (860.5, 1273.5), 22.3), ((2766.3, 1536.0), (1236.2, 1283.1), 25.4)]


def _poly_mask(shape, pts, scale=1.0):
    h, w = shape
    arr = np.zeros((h, w), np.uint8)
    s = skia.Surface.MakeRasterDirect(skia.ImageInfo.MakeA8(w, h), arr)
    c = s.getCanvas()
    p = skia.Path()
    p.moveTo(pts[0][0] * scale, pts[0][1] * scale)
    for x, y in pts[1:]:
        p.lineTo(x * scale, y * scale)
    p.close()
    c.drawPath(p, skia.Paint(AntiAlias=True, Color=skia.ColorWHITE))
    del c, s
    return arr.astype(np.float32) / 255


def _allowed(shape):
    """暗部阈值的保留区：车架各管、车筐、链罩、脚蹬、两块挡泥板和两条轮胎附近。"""
    import cv2
    h, w = shape
    m = np.zeros((h, w), np.uint8)
    for a, b in TUBES:
        cv2.line(m, (int(a[0] * TH), int(a[1] * TH)), (int(b[0] * TH), int(b[1] * TH)), 255, 80)
    for poly in (BASKET, GUARD, PEDAL, FENDER_REAR, FENDER_FRONT):
        cv2.fillPoly(m, [np.round(np.array(poly) * TH).astype(np.int32)], 255)
    for (cx, cy), (ax, ay), ang in WHEELS:
        cv2.ellipse(m, (int(cx), int(cy)), (int(ax / 2), int(ay / 2)), ang, 0, 360, 255, 150)
    return m.astype(np.float32) / 255


def _strokes(shape):
    """补画照片阈值里缺失的镀铬部件：车把、车铃、刹车拉杆、车座、座杆、后货架、支架，以及辐条。"""
    h, w = shape
    arr = np.zeros((h, w), np.uint8)
    s = skia.Surface.MakeRasterDirect(skia.ImageInfo.MakeA8(w, h), arr)
    c = s.getCanvas()

    def line(pts, width, alpha=1.0):
        p = skia.Path()
        p.moveTo(*pts[0])
        for q in pts[1:]:
            p.lineTo(*q)
        c.drawPath(p, skia.Paint(AntiAlias=True, Color=skia.Color4f(1, 1, 1, alpha), Style=skia.Paint.kStroke_Style,
                                 StrokeWidth=width, StrokeCap=skia.Paint.kRound_Cap,
                                 StrokeJoin=skia.Paint.kRound_Join))

    def fill(pts):
        p = skia.Path()
        p.moveTo(*pts[0])
        for q in pts[1:]:
            p.lineTo(*q)
        p.close()
        c.drawPath(p, skia.Paint(AntiAlias=True, Color=skia.ColorWHITE))

    # 车把：从车铃下的夹子向右下弯到黑色握把
    line([(975, 228), (1060, 262), (1200, 345), (1330, 400), (1450, 455), (1550, 488), (1640, 462), (1700, 432)], 30)
    line([(1700, 430), (1828, 445)], 46)                                  # 握把
    line([(985, 222), (1000, 150), (1040, 105)], 22)                       # 车把弯上车铃
    c.drawCircle(1062, 162, 58, skia.Paint(AntiAlias=True, Color=skia.ColorWHITE))   # 车铃
    line([(1300, 440), (1450, 480), (1620, 540), (1785, 600)], 11)         # 刹车拉杆
    line([(1235, 380), (1250, 620)], 30)                                   # 车把立管
    # 车座与座杆
    fill([(2070, 405), (2300, 402), (2540, 430), (2525, 470), (2420, 520), (2300, 545), (2120, 500), (2075, 460)])
    line([(2310, 545), (2285, 720)], 34)
    # 后货架：上沿、平台、两根撑杆
    line([(2290, 745), (2420, 765), (2560, 775), (3110, 790), (3120, 812), (2560, 830)], 26)
    line([(2560, 798), (3110, 805)], 18)
    line([(2985, 830), (2955, 1200)], 18)
    line([(2600, 830), (2700, 1150)], 12)
    # 支架
    line([(2840, 1560), (2860, 2280)], 20)
    # 轮胎：拟合椭圆上补一圈，照片里轮胎顶上反光的一段在阈值里会断开
    for (hx, hy), (ax, ay), ang in WHEELS:
        th = np.radians(ang)
        q = np.linspace(0, 2 * np.pi, 241)
        ex, ey = 0.5 * ax * 1.02 * np.cos(q), 0.5 * ay * 1.02 * np.sin(q)
        line(list(zip(hx + ex * np.cos(th) - ey * np.sin(th), hy + ex * np.sin(th) + ey * np.cos(th))), 52)
    # 辐条：每个轮子 36 根，交叉编法，用细线；外端落在拟合椭圆略向内收的轮辋上
    for (hx, hy), (ax, ay), ang in WHEELS:
        th = np.radians(ang)
        for k in range(36):
            a0 = k * np.pi / 18
            a1 = a0 + (0.42 if k % 2 else -0.42)
            ex, ey = 0.5 * ax * 0.9 * np.cos(a1), 0.5 * ay * 0.9 * np.sin(a1)
            p1 = (hx + ex * np.cos(th) - ey * np.sin(th), hy + ex * np.sin(th) + ey * np.cos(th))
            p0 = (hx + 45 * np.cos(a0), hy + 45 * np.sin(a0))
            line([p0, p1], 7, 0.75)
        c.drawCircle(hx, hy, 60, skia.Paint(AntiAlias=True, Color=skia.ColorWHITE))
    del c, s
    return arr.astype(np.float32) / 255


def dry_mask():
    """干地覆盖率 (H, 2400)，第 0 行是车顶一侧。"""
    def make():
        im = Image.open(PHOTO).convert("RGB")
        a = np.asarray(im, np.float32) / 255
        lum = a.mean(2)
        keep = _allowed(lum.shape)
        # 暗部：黑色车身与轮胎。阈值附近软过渡，再做一次闭运算补上细小的断口
        dark = np.clip((0.19 - lum) / 0.06, 0, 1) * keep
        dark = ndimage.grey_closing(dark, size=(7, 7))
        lab, n = ndimage.label(dark > 0.5)
        sizes = ndimage.sum(dark > 0.5, lab, range(1, n + 1))
        small = np.isin(lab, np.flatnonzero(sizes < 1500) + 1)
        dark[small] = 0
        m = np.maximum(dark, _strokes(lum.shape))
        # 车筐是铁丝网：网眼里也会被雨打湿，保留阈值得到的网格即可；整体边缘略微羽化，像水慢慢浸进干地的边
        m = ndimage.gaussian_filter(m, 1.6)
        ys, xs = np.nonzero(m > 0.05)
        y0, y1, x0, x1 = ys.min() - 40, ys.max() + 40, xs.min() - 40, xs.max() + 40
        m = m[y0:y1, x0:x1]
        w = 2400
        h = int(round(m.shape[0] * w / m.shape[1]))
        out = np.asarray(Image.fromarray((np.clip(m, 0, 1) * 255).astype(np.uint8)).resize((w, h), Image.LANCZOS),
                         np.float32) / 255
        return out.astype(np.float32)
    return disk_cached("bike_dry_v3", make)


LENGTH = 1.86                    # 干地轮廓的世界长度（米）


def size():
    m = dry_mask()
    return LENGTH, LENGTH * m.shape[0] / m.shape[1]


if __name__ == "__main__":
    import sys
    m = dry_mask()
    out = sys.argv[1] if len(sys.argv) > 1 else "bike_dry.png"
    Image.fromarray((m * 255).astype(np.uint8)).save(out)
    print(m.shape, out)
