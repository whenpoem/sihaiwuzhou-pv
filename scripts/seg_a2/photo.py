"""L04 的花边老照片：正面是一张七十年代的街景，背面是钢笔字和透出来的红色印刷字。

照片取自 Hans-Peter Bärtschi 1977 年在汉口车站路拍的街景（Wikimedia Commons，CC BY-SA 4.0）。处理成当年
国内照相馆冲印的黑白小照片的样子：银盐相纸的影调（暗部偏冷、亮部略带奶黄）、轻微的银镜反应（暗部边缘泛出一点
金属灰）、颗粒，四周留白边，白边外缘用花边剪刀剪成连续的小圆齿（俗称"花边"）。下方的白边留得宽一些，用来
写钢笔字。画面中央偏左原本走着的一个人被挖掉，只剩一片人形的空白相纸，形状取自这个人本身的轮廓（用 YOLO
的人像分割求出）。

背面是相纸的纸背：比正面更暖的米白色，纸纹明显，透出一点正面影像的影子（薄相纸逆光时能看到）。背面上有
红色印刷的旧字"待到山花爛漫時　她在叢中笑"，像相纸厂印在纸背上的字样，钢笔字"她的笑"写在它上面。

贴图都是 float32 RGBA（直通 alpha），第 0 行为顶部，缓存在 data/cache/seg_a2/。
"""
import sys
from pathlib import Path

import numpy as np
import skia
from PIL import Image
from scipy import ndimage

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "style"))
import look  # noqa: E402

SRC = ROOT / "assets" / "images" / "Chezhan_Road_Hankou_1977_SIK_03-060008-Print_.jpg"
CACHE = ROOT / "data" / "cache" / "seg_a2"
VERSION = 2

# 照片整体（含白边）的尺寸，单位为照片高度的比例：宽高比 1.42；四边白边宽 0.045，下边 0.16
ASPECT = 1.42
BORDER = 0.045
BOTTOM = 0.165
RES = 1400                          # 照片高度方向的像素数


def _cache(name, fn):
    p = CACHE / f"photo_v{VERSION}_{name}.npy"
    if p.exists():
        return np.load(p).astype(np.float32)
    a = fn().astype(np.float32)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.save(p, a.astype(np.float16))
    return a


def deckle_mask(w, h, period_px=26.0, depth_px=7.0, seed=3):
    """花边剪刀剪出的外缘：沿四边连续的小圆齿。返回 (h, w) 覆盖率。"""
    s = skia.Surface.MakeRasterN32Premul(w, h)
    c = s.getCanvas()
    c.clear(skia.Color4f(0, 0, 0, 0))
    rng = np.random.default_rng(seed)
    path = skia.Path()
    m = depth_px + 2

    def edge(p0, p1, first):
        p0, p1 = np.array(p0, float), np.array(p1, float)
        d = p1 - p0
        L = np.hypot(*d)
        n = max(int(round(L / period_px)), 1)
        t = d / L
        nrm = np.array([t[1], -t[0]])                      # 指向外侧
        for k in range(n):
            a = p0 + d * (k / n)
            b = p0 + d * ((k + 1) / n)
            mid = (a + b) / 2 + nrm * depth_px * (0.85 + 0.3 * rng.uniform())
            if first and k == 0:
                path.moveTo(*a)
            path.quadTo(*mid, *b)

    corners = [(m, m), (w - m, m), (w - m, h - m), (m, h - m)]
    for i in range(4):
        edge(corners[i], corners[(i + 1) % 4], i == 0)
    path.close()
    c.drawPath(path, skia.Paint(AntiAlias=True, Color=skia.Color4f(1, 1, 1, 1)))
    arr = s.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType, alphaType=skia.kPremul_AlphaType)
    return arr[..., 3].astype(np.float32) / 255.0


def size_px():
    h = RES
    w = int(round(RES * ASPECT))
    return w, h


def image_rect():
    """影像区（不含白边）在整张照片里的像素范围 (x0, y0, x1, y1)。"""
    w, h = size_px()
    b = int(BORDER * h)
    return b, b, w - b, h - int(BOTTOM * h)


CROP_X0, CROP_Y0, CROP_W = 470, 566, 1220       # 原图里取用的范围（1920 宽的版本），高度按影像区的宽高比
PERSON = 2                                       # YOLO 分割结果里那位背对镜头走远的女子
YOLO = ROOT / "assets" / "models" / "yolo26s-seg.pt"     # Ultralytics YOLO26 分割模型
PAPER_WHITE = np.array([0.93, 0.91, 0.85], np.float32)      # 相纸白（未曝光处）


def person_mask():
    """原图里那位女子的轮廓（与原图同尺寸的 0–1 数组）。用 YOLO 的人像分割求出后缓存。"""
    def make():
        from ultralytics import YOLO as Y
        res = Y(str(YOLO)).predict(str(SRC), imgsz=1920, conf=0.25, classes=[0], retina_masks=True, verbose=False)[0]
        boxes = res.boxes.xyxy.cpu().numpy()
        masks = res.masks.data.cpu().numpy()
        # 按位置挑出这位女子（她的外接框约为 x 1077–1169、y 918–1188），不依赖检测的排序
        k = int(np.argmin([abs((b[0] + b[2]) / 2 - 1123) + abs((b[1] + b[3]) / 2 - 1053) for b in boxes]))
        return masks[k].astype(np.float32)
    return _cache("person", make)


def _tone(lum):
    """银盐相纸的影调：S 形曲线，黑位抬起、白位压低一点（褪色），暗部偏冷、亮部偏奶黄。"""
    x = np.clip(lum, 0, 1)
    x = x * x * (3 - 2 * x) * 0.55 + x * 0.45
    x = 0.07 + 0.86 * x
    shadow = np.array([0.050, 0.050, 0.052], np.float32)
    high = np.array([0.95, 0.925, 0.86], np.float32)
    return shadow + (high - shadow) * x[..., None]


def front():
    """照片正面（RGBA，直通 alpha）。"""
    def make():
        rng = np.random.default_rng(1977)
        im = np.asarray(Image.open(SRC).convert("RGB"), np.float32) / 255.0
        W, H = size_px()
        x0, y0, x1, y1 = image_rect()
        iw, ih = x1 - x0, y1 - y0
        ch = int(round(CROP_W * ih / iw))
        crop = im[CROP_Y0:CROP_Y0 + ch, CROP_X0:CROP_X0 + CROP_W]
        pm = person_mask()[CROP_Y0:CROP_Y0 + ch, CROP_X0:CROP_X0 + CROP_W]
        lum = crop @ np.array([0.36, 0.50, 0.14], np.float32)
        lum = np.asarray(Image.fromarray((lum * 255).astype(np.uint8)).resize((iw, ih), Image.LANCZOS), np.float32) / 255
        pm = np.asarray(Image.fromarray((pm * 255).astype(np.uint8)).resize((iw, ih), Image.BILINEAR), np.float32) / 255
        # 银盐颗粒
        g = ndimage.gaussian_filter(rng.normal(0, 1, (ih, iw)).astype(np.float32), 0.8)
        lum = lum + g * 0.035 * (0.4 + lum)
        img = _tone(lum)
        # 四周轻微的暗角和银镜（暗部边缘泛出一点金属灰）
        yy, xx = np.mgrid[0:ih, 0:iw]
        r2 = ((xx / iw - 0.5) * 2) ** 2 + ((yy / ih - 0.5) * 2) ** 2
        img *= (1.02 - 0.10 * r2 ** 1.5)[..., None]
        edge = np.clip((r2 - 1.1) / 0.8, 0, 1) * (lum < 0.35)
        img = img * (1 - 0.25 * edge[..., None]) + 0.25 * edge[..., None] * np.array([0.42, 0.43, 0.45])
        # 人形的空白：那位女子的位置是一片没有曝光的相纸，边缘有一圈很窄的灰（药膜被刮去处）
        pmb = np.clip(ndimage.gaussian_filter(np.clip(pm * 1.6 - 0.3, 0, 1), 0.8), 0, 1)
        halo = np.clip(ndimage.gaussian_filter(pmb, 2.0) - pmb, 0, 1)
        img = img * (1 - pmb[..., None]) + PAPER_WHITE * pmb[..., None]
        img *= (1 - 0.35 * halo)[..., None]
        out = np.ones((H, W, 3), np.float32) * PAPER_WHITE
        # 白边上的纸纹和轻微的发黄
        n = ndimage.gaussian_filter(rng.normal(0, 1, (H, W)).astype(np.float32), 1.2)
        stain = ndimage.gaussian_filter(rng.normal(0, 1, (H // 8, W // 8)).astype(np.float32), 6)
        stain = np.asarray(Image.fromarray(((stain - stain.min()) / (np.ptp(stain) + 1e-6) * 255).astype(np.uint8)).resize((W, H), Image.BILINEAR), np.float32) / 255
        out *= (1 + 0.02 * n)[..., None]
        out *= (1 - 0.06 * np.clip(stain - 0.5, 0, 1) * 2)[..., None] * np.array([1.0, 0.99, 0.95])
        out[y0:y1, x0:x1] = img
        alpha = deckle_mask(W, H, period_px=H * 0.019, depth_px=H * 0.0055)
        return np.dstack([out, alpha])
    return _cache("front", make)


def back():
    """照片背面（RGBA）：米白的相纸背面，纸纹，正面影像极淡的透影（左右相反），以及红色印刷的旧字。"""
    def make():
        rng = np.random.default_rng(1961)
        W, H = size_px()
        base = np.array([0.90, 0.875, 0.81], np.float32)
        n1 = ndimage.gaussian_filter(rng.normal(0, 1, (H, W)).astype(np.float32), 1.0)
        n2 = ndimage.gaussian_filter(rng.normal(0, 1, (H, W)).astype(np.float32), 6.0)
        out = np.ones((H, W, 3), np.float32) * base
        out *= (1 + 0.025 * n1 + 0.05 * n2 / (n2.std() + 1e-6) * 0.4)[..., None]
        fr = front()[..., :3]
        ghost = fr.mean(2)[:, ::-1]
        out *= (0.985 + 0.03 * ghost)[..., None]
        # 红色印刷的旧字：仿宋，两行居中，略带套印的错位和印刷时的墨色不匀
        red = np.asarray(look.C["red"], np.float32)
        cov = _print_text(look.trad("待到山花烂漫时　她在丛中笑"), W, H)
        mott = np.clip(0.75 + 0.25 * ndimage.gaussian_filter(rng.normal(0, 1, (H, W)).astype(np.float32), 1.5) * 2.5, 0.35, 1)
        a = cov * mott * 0.55
        out = out * (1 - a[..., None]) + (red * 0.95)[None, None] * a[..., None] * 1.0 + out * a[..., None] * 0.0
        alpha = deckle_mask(W, H, period_px=H * 0.019, depth_px=H * 0.0055)[:, ::-1]
        return np.dstack([out, alpha])
    return _cache("back", make)


def _print_text(text, W, H):
    a, b = text.split("　")
    s = skia.Surface(W, H)
    c = s.getCanvas()
    c.clear(skia.Color4f(0, 0, 0, 0))
    px = H * 0.105
    f = skia.Font(look.typeface("fang", 400), px)
    f.setEdging(skia.Font.Edging.kAntiAlias)
    p = skia.Paint(AntiAlias=True, Color=skia.Color4f(1, 1, 1, 1))
    for line, y in ((a, 0.40), (b, 0.58)):
        w = f.measureText(line)
        c.drawString(line, (W - w) / 2, y * H + px * 0.38, f, p)
    arr = s.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType, alphaType=skia.kPremul_AlphaType)
    return arr[..., 3].astype(np.float32) / 255.0
