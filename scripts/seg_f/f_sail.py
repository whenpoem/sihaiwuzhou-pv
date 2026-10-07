"""L32 的白帆：中式帆船的主帆，帆布、竹撑条和桅杆按照片重画，读起来是一面真的布帆。

形状取自 D 段用的那张帆船照片（assets/images/Duk_Ling_in_HK_harbour.jpg，NickStenning 摄，CC BY-SA 2.0；左右翻转后
使用，与 D 段一致）：主帆的外轮廓按红色阈值取出，补满孔洞、只留最大的一块、把边缘磨圆，所以边缘干净，没有混进来的
索具和别的帆角；五根竹撑条和上方的帆桁按照片上的位置（在暗部上逐条拟合过）重新画成竹竿，桅杆也重画成一根
干净的木杆。

帆布的明暗按布的受力来画：每两根撑条之间的一幅布被风吹得向外鼓起，像一段横放的圆柱面，上半部朝向左上方的光、
较亮，下半部背光、较暗；布在撑条下方被压住，紧贴撑条的地方有一道窄的阴影，撑条上方有一线亮边；鼓起在一幅布的
横向中部最明显、两端贴着帆边较平。再叠上照片里帆布本身的细小皱褶（高通滤波后的亮度，压掉大块的明暗和暗色的
补丁）、布纹，以及沿帆边一圈的卷边和缝线。"满"时风把帆鼓满：billow 由 0.55 变到 1，明暗对比随之加大。

帆上印着旧字"希望寄託在你們身上"两行（思源宋体最粗字重），褪色红，浓度约一半，随布面的明暗起伏，边缘有少量剥落。
贴图坐标是翻转后照片的像素（BOX 范围），按 SCALE 倍画出；直通 alpha 的 RGBA。
"""
import math

import numpy as np
import skia
from PIL import Image
from scipy import ndimage

from f_common import RENDERS, IMG, RED, cached, disk_cached
import look

PHOTO = IMG / "Duk_Ling_in_HK_harbour.jpg"
PW = 1920
BOX = (600, 240, 1300, 1260)                      # 贴图覆盖的照片像素范围（翻转后）
SCALE = 2                                         # 贴图每照片像素 2×2
# 帆的轮廓（照片像素，翻转后）：顶点、沿帆桁到后缘、后缘经各撑条后端、帆脚、前缘经各撑条前端回到顶点
PEAK = (965, 293)
YARD_END = (1140, 515)
LEECH = [(1150, 585), (1175, 675), (1200, 765), (1220, 851), (1230, 916)]
LUFF = [(650, 947), (645, 845), (655, 718), (705, 577), (795, 435)]
# 撑条与帆桁：自上而下，(前端, 后端)
YARD = (PEAK, YARD_END)
BATTENS = [((795, 435), (1150, 585)), ((705, 577), (1175, 675)), ((655, 718), (1200, 765)),
           ((645, 845), (1220, 851)), ((650, 947), (1230, 916))]
MAST = ((1093, 350), (1137, 1250), 13)            # 桅杆：上端、下端、粗细
TEXT = [("希望寄托", (872, 688), 80), ("在你们身上", (880, 806), 74)]   # 旧字：中心、字号（照片像素）
VERSION = 5


def _outline(billow):
    """帆的外轮廓（skia 路径，照片像素）：相邻两个轮廓点之间的布边向外鼓出一点，"满"时鼓得更多。"""
    pts = [PEAK, YARD_END] + LEECH + LUFF
    bulge = 4.0 + 7.0 * billow
    path = skia.Path()
    path.moveTo(*pts[0])
    for k in range(len(pts)):
        p0, p1 = np.array(pts[k], float), np.array(pts[(k + 1) % len(pts)], float)
        d = p1 - p0
        n = np.array([d[1], -d[0]]) / (np.linalg.norm(d) + 1e-9)       # 顺时针轮廓的外法向
        amt = 0.0 if k == 0 else bulge * (0.4 if k == len(pts) - 1 else 1.0)   # 帆桁那一段是直的
        if k == len(LEECH) + 1:                                          # 帆脚：沿帆脚杆，略向下垂
            amt = 2.0
        c = (p0 + p1) / 2 + n * amt
        path.quadTo(float(c[0]), float(c[1]), float(p1[0]), float(p1[1]))
    path.close()
    return path


def _line_y(seg, x):
    (x0, y0), (x1, y1) = seg
    return y0 + (y1 - y0) * (x - x0) / (x1 - x0)


def _build(billow):
    import cv2
    x0, y0, x1, y1 = BOX
    S = SCALE
    W, H = (x1 - x0) * S, (y1 - y0) * S
    surf = skia.Surface(W, H)
    cv = surf.getCanvas()
    cv.clear(skia.Color4f(0, 0, 0, 0))
    cv.scale(S, S)
    cv.translate(-x0, -y0)
    cv.drawPath(_outline(billow), skia.Paint(AntiAlias=True, Color=skia.Color4f(1, 1, 1, 1)))
    m = surf.makeImageSnapshot().toarray()[..., 3].astype(np.float32) / 255
    # 照片里帆布的皱褶：红通道，先用灰度闭运算抹掉细的暗线（索具、缝线），再取高通
    a = np.asarray(Image.open(PHOTO).convert("RGB"), np.float32)[:, ::-1] / 255
    lum = ndimage.grey_closing(a[..., 0], size=(5, 5))
    L = cv2.resize(lum[y0:y1, x0:x1], (W, H), interpolation=cv2.INTER_CUBIC)
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    px, py = x0 + (xx + 0.5) / S, y0 + (yy + 0.5) / S
    # 帆布的鼓起：按撑条把帆分成一幅幅，v 为在上下两根撑条之间的位置（0 上，1 下），h 为横向位置
    ys = np.stack([_line_y(bt, px) for bt in BATTENS], 0)
    top = np.where(px >= PEAK[0], _line_y(YARD, px), _line_y((LUFF[-1], PEAK), px))        # 最上面一幅的上沿
    v = np.zeros_like(px)
    for k in range(len(BATTENS)):
        upper = top if k == 0 else ys[k - 1]
        lower = ys[k]
        sel = (py >= upper) & (py < lower)
        v = np.where(sel, (py - upper) / np.maximum(lower - upper, 1.0), v)
    rows_l = np.argmax(m > 0.5, axis=1).astype(np.float32)
    rows_r = (W - 1 - np.argmax((m > 0.5)[:, ::-1], axis=1)).astype(np.float32)
    h = np.clip((xx - rows_l[:, None]) / np.maximum(rows_r - rows_l, 1)[:, None], 0, 1)
    bulge = np.clip(np.sin(np.pi * h), 0, 1) ** 0.7
    b = billow
    shade = 1.0 + (0.15 + 0.12 * b) * np.cos(np.pi * v) * bulge         # 上半朝光，下半背光
    shade -= (0.24 + 0.06 * b) * np.exp(-v / 0.05)                      # 撑条下方压住的一道阴影
    shade += 0.07 * np.exp(-(1 - v) / 0.025)                            # 撑条上方的一线亮边
    shade -= 0.05 * np.clip((h - 0.75) / 0.25, 0, 1) * (1 - v)          # 后缘略暗
    hp = L - ndimage.gaussian_filter(L, 18 * S)
    hp = ndimage.gaussian_filter(np.clip(hp, -0.035, 0.035), 1.0 * S) * 0.9
    weave = ndimage.gaussian_filter(np.random.default_rng(32).normal(0, 1, (H, W)), (0.7, 0.7)) * 0.016
    # 拼缝：一幅幅布条竖着缝在一起，缝线略向前缘倾斜（照片里的样子）
    tilt = -0.18 + 0.20 * h
    sx = (px - tilt * (py - 600.0)) / 46.0
    seam = np.exp(-((sx - np.round(sx)) * 46.0 / 0.9) ** 2)
    shade = shade + hp + weave - 0.045 * seam + 0.02 * np.exp(-((sx - np.round(sx)) * 46.0 - 1.6) ** 2 / 0.8)
    cloth = np.array([0.86, 0.855, 0.835]) * shade[..., None]
    cloth = cloth + np.array([-0.012, 0.0, 0.018]) * (1 - shade[..., None])              # 暗处略偏冷
    # 卷边与缝线
    dist = ndimage.distance_transform_edt(m > 0.5) / S
    hem = np.clip(1 - dist / 6.0, 0, 1)
    cloth *= (1 - 0.10 * hem)[..., None]
    stitch = np.exp(-((dist - 4.0) / 0.45) ** 2) * (0.5 + 0.5 * (np.sin((px + py) * 1.6) > 0))
    cloth *= (1 - 0.10 * stitch)[..., None]
    # 旧字
    surf = skia.Surface(W, H)
    cv = surf.getCanvas()
    cv.clear(skia.Color4f(0, 0, 0, 0))
    for text, (cx, cy), size in TEXT:
        t = look.trad(text)
        f = look.font("serif", 900, size * S, scale_x=0.95)
        tr = size * S * 0.10
        adv = sum(f.measureText(ch) for ch in t) + tr * (len(t) - 1)
        x = (cx - x0) * S - adv / 2
        base = (cy - y0) * S + size * S * 0.36
        for ch in t:
            cv.drawString(ch, x, base, f, skia.Paint(AntiAlias=True, Color=skia.Color4f(1, 1, 1, 1)))
            x += f.measureText(ch) + tr
    g = surf.makeImageSnapshot().toarray()[..., 3].astype(np.float32) / 255
    g = ndimage.gaussian_filter(g, 0.8)
    wear = ndimage.gaussian_filter(np.random.default_rng(33).normal(0, 1, (H, W)), 2.5 * S)
    wear = np.clip((wear + 1.6) / 0.8, 0.35, 1)
    ink = (g * wear * 0.52)[..., None]
    red_c = np.array(RED) * 1.12 * np.clip(shade, 0.6, 1.2)[..., None]
    col = cloth * (1 - ink) + red_c * ink
    alpha = m.copy()
    # 撑条、帆桁与桅杆：竹竿与木杆，带一线高光；撑条两端略伸出帆边
    surf = skia.Surface(W, H)
    cv = surf.getCanvas()
    cv.clear(skia.Color4f(0, 0, 0, 0))
    cv.scale(S, S)
    cv.translate(-x0, -y0)

    def pole(p0, p1, w, rgb, hl):
        path = skia.Path()
        path.moveTo(*p0)
        path.lineTo(*p1)
        cv.drawPath(path, skia.Paint(AntiAlias=True, Color=skia.Color4f(*rgb, 1), Style=skia.Paint.kStroke_Style,
                                     StrokeWidth=w, StrokeCap=skia.Paint.kRound_Cap))
        d = np.array(p1, float) - np.array(p0, float)
        n = np.array([d[1], -d[0]]) / np.linalg.norm(d) * w * 0.22
        if n[1] > 0:
            n = -n
        path = skia.Path()
        path.moveTo(p0[0] + n[0], p0[1] + n[1])
        path.lineTo(p1[0] + n[0], p1[1] + n[1])
        cv.drawPath(path, skia.Paint(AntiAlias=True, Color=skia.Color4f(*hl, 1), Style=skia.Paint.kStroke_Style,
                                     StrokeWidth=w * 0.28, StrokeCap=skia.Paint.kRound_Cap))
    for k, ((ax, ay), (bx, by)) in enumerate([YARD] + BATTENS):
        d = np.array([bx - ax, by - ay], float)
        d /= np.linalg.norm(d)
        p0 = (ax - d[0] * 14, ay - d[1] * 14)
        p1 = (bx + d[0] * 8, by + d[1] * 8)
        pole(p0, p1, 9.0 if k else 10.0, (0.34, 0.31, 0.26), (0.66, 0.62, 0.55))
        for j in range(1, 8):                                       # 竹节
            u = j / 8
            q = (p0[0] + (p1[0] - p0[0]) * u, p0[1] + (p1[1] - p0[1]) * u)
            cv.drawCircle(q[0], q[1], 3.2, skia.Paint(AntiAlias=True, Color=skia.Color4f(0.22, 0.21, 0.19, 1)))
    (mx0, my0), (mx1, my1), mw = MAST
    pole((mx0, my0), (mx1, my1), mw, (0.20, 0.19, 0.18), (0.50, 0.49, 0.46))
    cv.drawCircle(mx0, my0 - 4, 7, skia.Paint(AntiAlias=True, Color=skia.Color4f(0.20, 0.19, 0.18, 1)))
    # 帆脚索：从撑条后端收到桅杆下方，细而淡
    for (ax, ay), (bx, by) in BATTENS:
        cv.drawLine(bx + 4, by, mx1 + 40, 1180, skia.Paint(AntiAlias=True, Color=skia.Color4f(0.42, 0.41, 0.40, 0.8),
                                                           StrokeWidth=1.3))
    arr = surf.makeImageSnapshot().toarray().astype(np.float32) / 255
    pa = arr[..., 3]
    prgb = arr[..., :3]
    if _bgr():
        prgb = prgb[..., ::-1]
    # 撑条在帆布上投下一道很窄的影子（光从左上来，影子落在下方偏右）
    sh = ndimage.shift(ndimage.gaussian_filter(pa, 2.0 * S), (4 * S, 2 * S), order=1) * m * 0.35
    col = col * (1 - sh[..., None])
    col = col * (1 - pa[..., None]) + prgb * pa[..., None]
    alpha = np.maximum(alpha, pa)
    return np.dstack([np.clip(col, 0, 1.5), alpha]).astype(np.float16)


_BGR = None


def _bgr():
    global _BGR
    if _BGR is None:
        s = skia.Surface(2, 2)
        s.getCanvas().clear(skia.Color4f(1, 0, 0, 1))
        _BGR = bool(s.makeImageSnapshot().toarray()[0, 0, 2] > 200)
    return _BGR


def sail_rgba(billow):
    key = "full" if billow >= 0.99 else "calm"
    return disk_cached(f"sail_{key}_v{VERSION}", lambda: _build(1.0 if key == "full" else 0.55))


def sail_tex(billow_key):
    from engine import Tex
    return cached(f"sail_tex_{billow_key}", lambda: Tex(sail_rgba(1.0 if billow_key == "full" else 0.0).astype(np.float32)))


if __name__ == "__main__":
    for key in ("calm", "full"):
        a = sail_rgba(1.0 if key == "full" else 0.0).astype(np.float32)
        bg = np.array([0.04, 0.05, 0.07])
        img = a[..., :3] * a[..., 3:] + bg * (1 - a[..., 3:])
        Image.fromarray((np.clip(img, 0, 1) * 255).astype(np.uint8)).save(
            str(RENDERS / f"sail_{key}.png"))
