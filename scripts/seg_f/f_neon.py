"""L25–L27 的白色线描：握花的"扌"、花茎和由"她"字笔画展开的向日葵，画成霓虹灯管一样的白色细线。

几何全部取自副歌一的 scripts/seg_c/flower.py（只读导入）：花瓣是"她"字（思源宋体 900）的笔画，展开动画用
flower.bloom_state(u) 给出的每片花瓣的锚点、主轴、缩放和翘起角；茎是"她"字竖画拉长后的轮廓；"扌"是思源黑体 900
的字形，握持点与副歌一相同。不同的只是画法：副歌一是带纸纹和墨描边的彩色贴图，这里只画每一笔的轮廓线，
线是冷白的灯管，外面一圈冷色的光晕；花瓣内部填一层半透明的暗色，后面的线被前面的花瓣挡住一部分，看得出层次。
花心的"她"就是歌词里的那个字，线更亮。

坐标沿用 flower.py 的"花的坐标"（花心为原点，y 向上，花的直径约 0.9）；贴图按 PPU 像素/花的单位画出，
场景里按花的缩放 S 换算成世界尺寸。
"""
import math
import sys

import cv2
import numpy as np
import skia

from f_common import RENDERS, SCRIPTS, cached

sys.path.append(str(SCRIPTS / "seg_c"))
import flower as FL  # noqa: E402
from engine import Tex, glyph_path, contours  # noqa: E402

PPU = 1400                                   # 贴图像素 / 花的单位
LINE = 0.0075                                # 灯管粗细（花的单位）
GLOW = np.array([0.50, 0.68, 1.0])           # 光晕的颜色
CORE = 1.35                                  # 灯管的亮度


def _to_canvas(box, ppu):
    x0, y0, x1, y1 = box
    m = skia.Matrix()
    m.setScale(ppu, -ppu)
    m.postTranslate(-x0 * ppu, y1 * ppu)
    return m, int(round((x1 - x0) * ppu)), int(round((y1 - y0) * ppu))


def _petal_path(st):
    """一片花瓣（或字里原位的一笔）在花的坐标里的轮廓：笔画坐标里的轮廓按缩放、翘起的透视缩短、主轴方向摆好。"""
    s = FL.strokes()[st["stroke"]]
    kk = math.cos(math.radians(st["tilt"]))
    m = skia.Matrix()
    m.setScale(st["scale"] * st["fx"], -st["scale"] * kk)      # y 向下的笔画坐标 → y 向上，外端朝 +y
    r = skia.Matrix()
    r.setRotate(math.degrees(st["axis"]) - 90.0)
    m.postConcat(r)
    m.postTranslate(float(st["anchor"][0]), float(st["anchor"][1]))
    p = skia.Path(s.rpath)
    p.transform(m)
    return p


def _center_path(E=FL.E_CENTER):
    p = skia.Path(glyph_path("她", FL.KIND, FL.WEIGHT))
    m = skia.Matrix()
    m.setScale(E, -E)
    m.preTranslate(-0.5, 0.38)
    p.transform(m)
    return p


def _stem_path():
    P = FL._stem_poly()
    p = skia.Path()
    p.addPoly([skia.Point(float(x), float(y)) for x, y in P], True)
    return p


def _hand_path():
    g = FL.stem_geometry()["grip"]
    p = skia.Path(glyph_path("扌", FL.HAND_KIND, FL.HAND_WEIGHT))
    m = skia.Matrix()
    m.setScale(FL.HAND_EM, -FL.HAND_EM)
    m.preTranslate(-FL.HAND_GRIP_EM[0], -FL.HAND_GRIP_EM[1])
    m.postTranslate(float(g[0]), float(g[1]))
    p.transform(m)
    return p


def _render(paths, box, ppu, fills=None, bright=None):
    """把一组轮廓画成灯管：返回预乘的 RGBA（rgb 可超过 alpha，表示发光）。
    fills 给出每条轮廓内部暗色的不透明度，bright 给出每条灯管的亮度倍数。"""
    M, W, H = _to_canvas(box, ppu)
    s = skia.Surface(W, H)
    c = s.getCanvas()
    c.clear(skia.Color4f(0, 0, 0, 0))
    c.concat(M)
    core = skia.Surface(W, H)
    cc = core.getCanvas()
    cc.clear(skia.Color4f(0, 0, 0, 0))
    cc.concat(M)
    for i, p in enumerate(paths):
        f = fills[i] if fills else 0.0
        b = bright[i] if bright else 1.0
        if f > 0:
            # 先把后面的灯管按这片的形状压暗（遮挡），再画自己的暗色填充
            cc.drawPath(p, skia.Paint(Color=skia.Color4f(0, 0, 0, f), AntiAlias=True,
                                      BlendMode=skia.BlendMode.kDstOut))
            c.drawPath(p, skia.Paint(Color=skia.Color4f(0.012, 0.014, 0.02, f), AntiAlias=True))
        g = min(b / 1.6, 1.0)
        cc.drawPath(p, skia.Paint(Color=skia.Color4f(g, g, g, 1.0), AntiAlias=True, Style=skia.Paint.kStroke_Style,
                                  StrokeWidth=LINE, StrokeJoin=skia.Paint.kRound_Join))
    fill = s.makeImageSnapshot().toarray().astype(np.float32)[..., 3] / 255
    line = core.makeImageSnapshot().toarray().astype(np.float32)
    la = line[..., 3] / 255
    lum = line[..., 0] / 255 * la * 1.6                           # 灯管亮度（≤ 1.6）；toarray() 给出的是未预乘的颜色
    glow = cv2.GaussianBlur(lum, (0, 0), LINE * ppu * 2.2) * 0.9 + cv2.GaussianBlur(lum, (0, 0), LINE * ppu * 7) * 0.5
    rgb = lum[..., None] * CORE * np.array([0.97, 0.99, 1.0]) + glow[..., None] * GLOW * 0.55
    a = np.clip(np.maximum(fill * 0.85, la * lum / 1.6), 0, 1)
    return np.dstack([rgb, a]).astype(np.float32)


HEAD_BOX = (-0.52, -0.52, 0.52, 0.52)


def head_rgba(u, E=FL.E_CENTER, center_boost=1.0):
    """展开进度 u 时的花头（花瓣、圆盘、花心的"她"），覆盖 HEAD_BOX。u = 0 时只有"她"字。"""
    paths, fills, bright = [], [], []
    disc = None
    for st in FL.bloom_state(u, E):
        if st["kind"] == "petal":
            if st["progress"] <= 0.001:
                continue                                      # 还没离开字里的原位：与花心的字重合，不重复画
            paths.append(_petal_path(st))
            fills.append(0.75 * min(st["progress"] * 3, 1.0))
            bright.append(1.0)
        elif st["kind"] == "disc":
            disc = st
    if disc is not None:
        r = disc["size"][0] / 2 * 0.80
        p = skia.Path()
        p.addCircle(0, 0, r)
        paths.append(p)
        fills.append(0.92 * disc["opacity"])
        bright.append(0.8 * disc["opacity"])
        pos, size, th, rr = FL.seed_layout()
        q = skia.Path()
        k = r / FL.R_DISC
        for (x, y), sz in zip(pos * k, size * k):
            q.addCircle(float(x), float(y), float(sz) * 0.16)
        paths.append(q)
        fills.append(0.0)
        bright.append(0.55 * disc["opacity"])
    paths.append(_center_path(E))
    fills.append(0.9)
    bright.append(1.6 * center_boost)
    return _render(paths, HEAD_BOX, PPU, fills, bright)


def head_tex(u):
    """按展开进度量化缓存的花头贴图（同一进度只画一次）。"""
    q = round(float(np.clip(u, 0, 1)) * 60) / 60
    slot = cached("neon_head_slot", lambda: {})
    if q not in slot:
        if len(slot) > 80:
            slot.clear()
        slot[q] = Tex(head_rgba(q), premultiplied=True)
    return slot[q]


def stem_box():
    g = FL.stem_geometry()
    x0, y0, x1, y1 = g["box"]
    return (x0 - 0.02, y0 - 0.02, x1 + 0.02, y1 + 0.02)


def stem_tex():
    return cached("neon_stem", lambda: Tex(_render([_stem_path()], stem_box(), PPU, [0.6], [0.9]), premultiplied=True))


def hand_box():
    b = _hand_path().computeTightBounds()
    return (b.left() - 0.02, b.top() - 0.02, b.right() + 0.02, b.bottom() + 0.02)


def hand_tex():
    return cached("neon_hand", lambda: Tex(_render([_hand_path()], hand_box(), PPU, [0.7], [1.0]), premultiplied=True))


def box_plane(box, origin, S, z):
    """花的坐标里的矩形 box → 世界里的平面中心与尺寸（花在 origin，缩放 S）。"""
    x0, y0, x1, y1 = box
    return (origin[0] + (x0 + x1) / 2 * S, origin[1] + (y0 + y1) / 2 * S, z), ((x1 - x0) * S, (y1 - y0) * S)


if __name__ == "__main__":
    from PIL import Image
    tiles = []
    for u in (0.0, 0.3, 0.6, 1.0):
        a = head_rgba(u)
        a = cv2.resize(a, (700, 700), interpolation=cv2.INTER_AREA)
        bg = np.array([0.03, 0.035, 0.05])
        tiles.append(np.clip(a[..., :3] + bg * (1 - a[..., 3:4]), 0, 1))
    st = _render([_stem_path(), _hand_path()], (-0.3, -1.35, 0.2, 0.05), 500, [0.6, 0.7], [0.9, 1.0])
    st = cv2.resize(st, (int(st.shape[1] * 700 / st.shape[0]), 700), interpolation=cv2.INTER_AREA)
    tiles.append(np.clip(st[..., :3] + np.array([0.03, 0.035, 0.05]) * (1 - st[..., 3:4]), 0, 1))
    img = np.hstack(tiles)
    Image.fromarray((img * 255).astype(np.uint8)).save(str(RENDERS / "neon_test.png"))
