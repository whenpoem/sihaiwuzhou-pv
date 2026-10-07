"""L03 的显像管电视：节目字幕、串台的旧字、云图和电视机外壳的贴图。

字幕按当年电视台的样子做：白色宋体粗字，四周一圈黑边，压在画面下方，分两行（"重播頻繁失靈的"、"天氣預報"），
每个字在它的元音起点出现。字幕是节目信号的一部分，所以它跟着画面一起翻滚、一起被雪花盖住、一起在关机时
被压成一条线。串台的旧字是另一个频道的信号混进来的样子：雪花里断续出现的红色仿宋字"形勢大好　不是小好"。
"""
import sys
from pathlib import Path

import numpy as np
import skia

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "style"))
import look  # noqa: E402
from engine import Tex  # noqa: E402

CACHE = ROOT / "data" / "cache" / "seg_a2"
SUB_W, SUB_H = 1024, 768          # 字幕贴图覆盖整个屏幕（4:3）
SUB_LINES = None


def sub_lines():
    """L03 的两行字幕（繁体）与每个字在两行里的位置。"""
    text = look.trad(look.lyric(3))
    a, b = text.split("　")
    return [a, b]


def _font(kind, weight, size):
    f = skia.Font(look.typeface(kind, weight), size)
    f.setEdging(skia.Font.Edging.kAntiAlias)
    f.setSubpixel(True)
    return f


def subtitle_rgba(n_visible, size=0.118):
    """前 n_visible 个字已经出现的字幕贴图（预乘 RGBA，float32）。size 为字高占屏幕高的比例。"""
    lines = sub_lines()
    s = skia.Surface(SUB_W, SUB_H)
    c = s.getCanvas()
    c.clear(skia.Color4f(0, 0, 0, 0))
    px = size * SUB_H
    f = _font("serif", 800, px)
    fill = skia.Paint(AntiAlias=True, Color=skia.Color4f(1.0, 1.0, 1.0, 1.0))
    edge = skia.Paint(AntiAlias=True, Color=skia.Color4f(0, 0, 0, 1.0), Style=skia.Paint.kStroke_Style,
                      StrokeWidth=px * 0.17, StrokeJoin=skia.Paint.kRound_Join)
    k = 0
    ys = [0.765, 0.895]
    for li, line in enumerate(lines):
        w = len(line) * px * 1.04
        x = (SUB_W - w) / 2
        base = ys[li] * SUB_H + px * 0.38
        for ch in line:
            if k < n_visible:
                c.drawString(ch, x, base, f, edge)
                c.drawString(ch, x, base, f, fill)
            x += px * 1.04
            k += 1
    arr = s.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType, alphaType=skia.kPremul_AlphaType)
    return arr.astype(np.float32) / 255.0


_SUBS = {}


def subtitle_tex(n):
    if n not in _SUBS:
        _SUBS[n] = Tex(subtitle_rgba(n), premultiplied=True, mipmap=True)
    return _SUBS[n]


def oldtext_cov():
    """串台旧字的覆盖率贴图（屏幕坐标，4:3）：两行红色仿宋"形勢大好"、"不是小好"。"""
    s = skia.Surface(SUB_W, SUB_H)
    c = s.getCanvas()
    c.clear(skia.Color4f(0, 0, 0, 0))
    px = 0.20 * SUB_H
    f = _font("fang", 400, px)
    p = skia.Paint(AntiAlias=True, Color=skia.Color4f(1, 1, 1, 1))
    # 仿宋笔画细，在雪花里不易认出：描一圈细边加粗（当年电视里的标语字幕也多是粗笔）
    pe = skia.Paint(AntiAlias=True, Color=skia.Color4f(1, 1, 1, 1), Style=skia.Paint.kStroke_Style,
                    StrokeWidth=px * 0.045, StrokeJoin=skia.Paint.kRound_Join)
    for line, y in zip(look.trad("形势大好　不是小好").split("　"), (0.36, 0.62)):
        w = f.measureText(line)
        c.drawString(line, (SUB_W - w) / 2, y * SUB_H + px * 0.38, f, pe)
        c.drawString(line, (SUB_W - w) / 2, y * SUB_H + px * 0.38, f, p)
    arr = s.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType, alphaType=skia.kPremul_AlphaType)
    return arr[..., 3].astype(np.float32) / 255.0


_T = {}


def oldtext_tex():
    if "old" not in _T:
        _T["old"] = Tex(oldtext_cov())
    return _T["old"]


# ---------------------------------------------------------------- 电视机外壳
# 照片：TurnOnTheNight 在中国工业博物馆拍的"沈阳牌"SD35-4 型 35 厘米黑白电视机（Wikimedia Commons，CC BY-SA 4.0）。
# 照片略带俯视，正面是个上宽下窄的梯形；先用单应变换把正面拉成矩形，再抠掉背景，补掉后加的卡通贴纸和右下角
# 挡在机壳前面的暖水瓶把手，把屏幕玻璃挖空（屏幕由 a2_crt 材质画在外壳后面）。原机壳是红色塑料，而全片的红色只
# 属于旧字，所以整机去色成偏暖的黑白，与纸面同一盏台灯从左上方照亮。

TV_SRC = ROOT / "assets" / "images" / "Shenyang_SD35-4_35cm_television_set_20260331131901.jpg"
TV_VERSION = 1
_SC = 3840 / 1600                                  # 量取坐标用的是 1600 宽的缩略图
TV_QUAD = [(308.6, 162.0), (1281.0, 136.0), (1263.0, 768.0), (326.8, 742.0)]   # 正面四角（白色面板外缘，含红色包边）
TV_W, TV_H = 2400, 1538                            # 拉正后正面的像素尺寸（宽高比 1.56）
TV_BASE = 0.075                                    # 正面下方露出的底座高度（占正面高度的比例）
STICKER = (1186, 258, 1262, 358)                   # 贴纸（缩略图坐标）
HANDLE_X = 1252                                    # 暖水瓶把手挡住机壳的范围从这里往右（缩略图坐标）


def _cache_tv(name, fn):
    p = CACHE / f"tv_v{TV_VERSION}_{name}.npy"
    if p.exists():
        return np.load(p).astype(np.float32)
    a = fn().astype(np.float32)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.save(p, a.astype(np.float16))
    return a


def tv_rectified():
    """拉正后的电视正面（RGB，0–1），下方多留出底座的高度。贴纸和暖水瓶把手已补掉。"""
    def make():
        import cv2
        im = cv2.imread(str(TV_SRC))[:, :, ::-1]
        Hh = int(TV_H * (1 + TV_BASE))
        quad = np.array(TV_QUAD, np.float32) * _SC
        dst = np.array([[0, 0], [TV_W, 0], [TV_W, TV_H], [0, TV_H]], np.float32)
        M = cv2.getPerspectiveTransform(quad, dst)
        out = cv2.warpPerspective(im, M, (TV_W, Hh), flags=cv2.INTER_CUBIC, borderMode=cv2.BORDER_REPLICATE)
        out = np.ascontiguousarray(out)
        # 贴纸：它下方（UHF 标牌与商标牌之间）有一段同样的竖向压条面板，把这一段竖着铺上去，接缝羽化
        out = out.astype(np.float32)
        base = out.copy()
        src = out[605:690, 2175:2365].copy()
        y = 285
        while y < 530:
            h = min(src.shape[0], 530 - y)
            k = np.ones((h, 1, 1), np.float32)
            if y > 285:
                k[:12] = np.linspace(0, 1, 12)[:h, None, None] if h >= 12 else 1
            out[y:y + h, 2175:2365] = out[y:y + h, 2175:2365] * (1 - k) + src[:h] * k
            if y + h >= 530:
                break
            y += h - 12
        # 左右两侧与原面板羽化衔接
        xx = np.arange(2175, 2365)[None, :, None]
        fe = np.clip(np.minimum(xx - 2175, 2365 - xx) / 12.0, 0, 1)
        out[285:530, 2175:2365] = base[285:530, 2175:2365] * (1 - fe) + out[285:530, 2175:2365] * fe
        out = np.clip(out, 0, 255)
        out = out / 255.0
        # 暖水瓶把手挡住了机壳右下角和底座右端：用左下角左右翻转后的样子补上（机壳左右对称）
        y0 = 1470
        out[y0:, TV_W - 90:] = out[y0:, :90][:, ::-1]
        return np.clip(out, 0, 1)
    return _cache_tv("rect", make)


# 屏幕玻璃（黑色橡胶圈以内）在拉正后的贴图里的范围：圆角矩形，四边略向外凸（显像管的玻璃面是枕形的）
GLASS = (186, 154, 1666, 1336)
GLASS_R = 150
GLASS_BULGE = 14


def tv_glass_mask():
    """屏幕玻璃的范围（拉正后的像素坐标，0–1 覆盖率）。"""
    def make():
        import skia
        Hh = int(TV_H * (1 + TV_BASE))
        x0, y0, x1, y1 = GLASS
        r, b = GLASS_R, GLASS_BULGE
        path = skia.Path()
        path.moveTo(x0 + r, y0)
        path.quadTo((x0 + x1) / 2, y0 - 2 * b, x1 - r, y0)
        path.quadTo(x1, y0, x1, y0 + r)
        path.quadTo(x1 + 2 * b, (y0 + y1) / 2, x1, y1 - r)
        path.quadTo(x1, y1, x1 - r, y1)
        path.quadTo((x0 + x1) / 2, y1 + 2 * b, x0 + r, y1)
        path.quadTo(x0, y1, x0, y1 - r)
        path.quadTo(x0 - 2 * b, (y0 + y1) / 2, x0, y0 + r)
        path.quadTo(x0, y0, x0 + r, y0)
        path.close()
        s = skia.Surface.MakeRasterN32Premul(TV_W, Hh)
        c = s.getCanvas()
        c.clear(skia.Color4f(0, 0, 0, 0))
        c.drawPath(path, skia.Paint(AntiAlias=True, Color=skia.Color4f(1, 1, 1, 1)))
        return s.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)[..., 3].astype(np.float32) / 255
    return _cache_tv("glass", make)


def tv_rgba():
    """电视外壳贴图（RGBA，直通 alpha）：去色、调成偏暖的黑白，左上方受光；屏幕玻璃处透明。"""
    def make():
        import skia
        a = tv_rectified()
        Hh, W = a.shape[:2]
        lum = a @ np.array([0.30, 0.55, 0.15], np.float32)
        # 红色塑料包边去色后偏暗，略提亮，免得整圈发黑
        red = np.clip((a[..., 0] - a[..., 1]) * 2.5, 0, 1)
        lum = lum + red * 0.10
        warm_d = np.array([0.10, 0.085, 0.07], np.float32)
        warm_l = np.array([0.98, 0.93, 0.82], np.float32)
        col = warm_d + (warm_l - warm_d) * np.clip(lum, 0, 1)[..., None]
        yy, xx = np.mgrid[0:Hh, 0:W].astype(np.float32)
        light = 1.06 - 0.22 * np.clip(((xx / W) * 0.6 + (yy / Hh) * 0.8), 0, 1.4)
        col *= light[..., None]
        # 外形：正面是圆角矩形，下方的底座窄一些
        s = skia.Surface.MakeRasterN32Premul(W, Hh)
        c = s.getCanvas()
        c.clear(skia.Color4f(0, 0, 0, 0))
        p = skia.Paint(AntiAlias=True, Color=skia.Color4f(1, 1, 1, 1))
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect.MakeLTRB(2, 2, W - 2, TV_H - 2), 70, 70), p)
        c.drawRect(skia.Rect.MakeLTRB(W * 0.07, TV_H * 0.95, W * 0.95, Hh - 6), p)
        alpha = s.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)[..., 3].astype(np.float32) / 255
        alpha *= 1.0 - tv_glass_mask()
        return np.dstack([np.clip(col, 0, 1.2), alpha])
    return _cache_tv("rgba", make)


def glass_rect():
    """屏幕玻璃在外壳贴图里的范围：(中心 x, 中心 y, 宽, 高)，以外壳正面的宽为 1 的比例，y 向下。"""
    m = tv_glass_mask() > 0.5
    ys, xs = np.nonzero(m)
    W = TV_W
    return ((xs.min() + xs.max()) / 2 / W, (ys.min() + ys.max()) / 2 / W, (xs.max() - xs.min()) / W,
            (ys.max() - ys.min()) / W)


# ---------------------------------------------------------------- 云图
# 卫星云图：NOAA 的 GOES-1 卫星 1979 年 4 月 13 日拍到的热带气旋 Idylle（Wikimedia Commons，公有领域，
# 经 SSEC/CIMSS 处理）。只有云和海面，没有国界线和经纬网。取气旋周围 4:3 的一块，转成灰度、压一点对比，
# 像当年电视里转播的云图。

CLOUD_SRC = ROOT / "assets" / "images" / "Idylle_1979-04-13_0430Z.jpg"


def cloud_tex():
    if "cloud" not in _T:
        from PIL import Image
        im = np.asarray(Image.open(CLOUD_SRC).convert("L"), np.float32) / 255.0
        h, w = im.shape
        cw = w
        ch = int(cw * 3 / 4)
        cy = int(h * 0.47)
        crop = im[cy - ch // 2:cy + ch // 2, :]
        x = np.clip((crop - 0.06) / 0.92, 0, 1) ** 1.1
        _T["cloud"] = Tex(x.astype(np.float32))
    return _T["cloud"]


def subtitle_tex_text(text, key, size=0.118, line_y=0.895):
    """任意一行字幕（例如 L04 的"我猜"）。"""
    k = ("sub", key)
    if k not in _SUBS:
        s = skia.Surface(SUB_W, SUB_H)
        c = s.getCanvas()
        c.clear(skia.Color4f(0, 0, 0, 0))
        px = size * SUB_H
        f = _font("serif", 800, px)
        fill = skia.Paint(AntiAlias=True, Color=skia.Color4f(1.0, 1.0, 1.0, 1.0))
        edge = skia.Paint(AntiAlias=True, Color=skia.Color4f(0, 0, 0, 1.0), Style=skia.Paint.kStroke_Style,
                          StrokeWidth=px * 0.17, StrokeJoin=skia.Paint.kRound_Join)
        w = len(text) * px * 1.04
        x = (SUB_W - w) / 2
        for ch in text:
            c.drawString(ch, x, line_y * SUB_H + px * 0.38, f, edge)
            c.drawString(ch, x, line_y * SUB_H + px * 0.38, f, fill)
            x += px * 1.04
        arr = s.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType, alphaType=skia.kPremul_AlphaType)
        _SUBS[k] = Tex(arr.astype(np.float32) / 255.0, premultiplied=True)
    return _SUBS[k]
