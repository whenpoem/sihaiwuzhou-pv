"""L09 的吊灯：老式透明白炽灯泡，灯丝就是"未來"两个字。

灯泡取自 Yann Forget 拍摄的"低电压下发光的电灯泡"（Wikimedia Commons，CC BY-SA 4.0，
assets/images/Electric_bulb_working_in_very_low_voltage.jpg）：黑底，透明玻璃被里面暗橙色的灯丝照亮，玻璃上
有灰尘和斑驳，灯口朝上，正是吊着的方向。原来的灯丝只是玻璃柱下端的一团亮光，用周围的玻璃把它补掉；玻璃柱、
灯口的喇叭形玻璃和玻璃上的反光都保留。照片按加法叠在画面上（黑底不遮挡后面的东西，玻璃只添上反光和被照亮的
灰尘），亮度随灯丝一起变化。

灯丝是"未來"两个字的细线（思源黑体 ExtraLight，笔画近似等粗，像一根绕成字形的钨丝），由玻璃柱下端伸出的
两根引线挂住两端，中间一根短的连接丝把两个字连成一根，连接丝中点挂在玻璃柱的支撑钩上。"斷"时就从这一点
烧断。灯口上方是胶木灯头和一根双股绞合的花线，向上伸出画面。

坐标：贴图像素在照片原图（3264 × 3264）里量取；灯丝中心 ANCHOR_PX 对应场景里的灯丝位置，每世界单位 PPU 像素。
所有贴图都是 0–1 浮点 RGB(A)，第 0 行是图像顶部，缓存在 data/cache/seg_c/bulb_*。
"""
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "style"))
import look  # noqa: E402

PHOTO = ROOT / "assets" / "images" / "Electric_bulb_working_in_very_low_voltage.jpg"
CACHE = ROOT / "data" / "cache" / "seg_c"
VERSION = 2

CROP = (700, 760, 2580, 3080)          # 灯泡在原图里的范围 (x0, y0, x1, y1)
NECK_Y = 790                           # 灯口玻璃的上沿
ANCHOR_PX = (1636, 2050)               # 灯丝中心（玻璃最宽处的中线上、玻璃柱下端以下 330 像素）
STEM_TIP = (1608, 1722)                # 玻璃柱下端
PPU = 1018.0                           # 每世界单位的像素数：玻璃高 2240 像素 ≈ 2.2 单位
CHAR_PX, GAP_PX = 380, 60              # 灯丝字的字号与两字间距（像素）
FIL_PAD = 120                          # 灯丝贴图四周的留白


def _cache(name, fn):
    p = CACHE / f"bulb_v{VERSION}_{name}.npy"
    if p.exists():
        return np.load(p)
    a = fn().astype(np.float32)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.save(p, a)
    return a


def px_to_world(px, py, anchor_world):
    """原图像素 → 世界坐标（anchor_world 为灯丝中心的世界位置）。"""
    return (anchor_world[0] + (px - ANCHOR_PX[0]) / PPU, anchor_world[1] - (py - ANCHOR_PX[1]) / PPU)


def crop_geometry(anchor_world):
    """玻璃贴图平面的中心与尺寸。"""
    x0, y0, x1, y1 = CROP
    c = px_to_world((x0 + x1) / 2, (y0 + y1) / 2, anchor_world)
    return c, ((x1 - x0) / PPU, (y1 - y0) / PPU)


def glass():
    """玻璃（RGB，黑底，按加法叠加）：补掉原来的灯丝，留下玻璃柱、灯口和反光。"""
    def make():
        im = np.asarray(Image.open(PHOTO).convert("RGB"), np.float32) / 255
        lum = im @ np.array([0.3, 0.55, 0.15], np.float32)
        yy, xx = np.mgrid[0:im.shape[0], 0:im.shape[1]].astype(np.float32)
        d2 = (xx - 1810) ** 2 + (yy - 1930) ** 2
        # 原灯丝一带用右侧 330 像素外的一块玻璃补：取它的低频亮度压暗、保留它的灰尘细节，羽化接缝
        m = np.clip(1.4 - np.sqrt(d2) / 230.0, 0, 1)
        m = np.maximum(m, ((lum > 0.30) & (xx > 1640) & (xx < 1990) & (yy > 1730) & (yy < 2130)).astype(np.float32))
        m = gaussian_filter(m, 18)
        src = np.roll(im, -330, axis=1)
        detail = src - gaussian_filter(src, (6, 6, 0))
        base = gaussian_filter(np.roll(im, -330, axis=1), (40, 40, 0)) * 0.55
        fill = np.clip(base + detail, 0, None)
        out = im * (1 - m[..., None]) + fill * m[..., None]
        # 原灯丝四周的大片辉光和左下的强反光压下去一些，灯丝换了位置，辉光由新的灯丝重新加上
        glow = np.exp(-d2 / (2 * 320.0 ** 2))[..., None]
        refl = np.exp(-((xx - 1440) ** 2 / (2 * 160.0 ** 2) + (yy - 2270) ** 2 / (2 * 110.0 ** 2)))[..., None]
        out = out * (1 - 0.40 * glow) * (1 - 0.5 * refl)
        x0, y0, x1, y1 = CROP
        out = out[y0:y1, x0:x1]
        return np.clip(out - 0.018, 0, None)                              # 黑底压到 0，加法叠加时不发灰
    return _cache("glass", make)


def _glyph_mask(text, size_px):
    f = look.font("sans", 250, size_px)
    w = int(f.measureText(text)) + 40
    m = np.asarray(look.text_layer([(text, f, 20, size_px * 0.88 + 20, None)], w, size_px + 40), np.float32)
    ys, xs = np.where(m > 0.05)
    return m[ys.min():ys.max() + 1, xs.min():xs.max() + 1]           # 裁到字形的实际外框


FIL_BOX = (1180, 1680, 2100, 2330)     # 灯丝画布在原图里的范围：与原图像素一一对应


def filament_layers():
    """灯丝各部分的遮罩（画布覆盖原图 FIL_BOX）：0 "未"、1 "來"、2 和 3 连接丝的左右两半、4 引线与支撑钩
    （不发光的金属丝）、5 整根灯丝的辉光（模糊后的遮罩）。"""
    def make():
        X0, Y0, X1, Y1 = FIL_BOX
        W, H = X1 - X0, Y1 - Y0
        a, b = _glyph_mask("未", CHAR_PX), _glyph_mask("來", CHAR_PX)
        total = a.shape[1] + GAP_PX + b.shape[1]
        cx, cy = ANCHOR_PX[0] - X0, ANCHOR_PX[1] - Y0
        xa = int(cx - total / 2)
        xb = xa + a.shape[1] + GAP_PX
        ya, yb = int(cy - a.shape[0] / 2), int(cy - b.shape[0] / 2)
        L = np.zeros((6, H, W), np.float32)
        L[0, ya:ya + a.shape[0], xa:xa + a.shape[1]] = a
        L[1, yb:yb + b.shape[0], xb:xb + b.shape[1]] = b
        th = 9

        def line(k, pts, w=th):
            img = np.zeros((H, W), np.uint8)
            cv2.polylines(img, [np.array(pts, np.int32)], False, 255, w, cv2.LINE_AA)
            L[k] = np.maximum(L[k], img / 255.0)
        mid = (xa + a.shape[1] + xb) // 2
        line(2, [(xa + a.shape[1] - 20, cy + 6), (mid, cy + 6)])
        line(3, [(mid, cy + 6), (xb + 20, cy + 6)])
        st = (STEM_TIP[0] - X0, STEM_TIP[1] - Y0)
        # 引线从玻璃柱下端斜着伸到两个字的外上角；支撑钩竖直下来、末端弯成小钩挂住连接丝的中点
        line(4, [st, (xa + 12, ya + int(0.18 * a.shape[0]))], 7)
        line(4, [st, (xb + b.shape[1] - 12, yb + int(0.18 * b.shape[0]))], 7)
        line(4, [st, (mid - 2, cy - 30), (mid - 12, cy + 4), (mid, cy + 16), (mid + 10, cy + 4)], 5)
        glow_src = np.clip(L[0] + L[1] + L[2] + L[3], 0, 1)
        L[5] = gaussian_filter(glow_src, 14) * 2.5 + gaussian_filter(glow_src, 55) * 7.0
        return L
    return _cache("filament2", make)


def filament_box(anchor_world):
    """灯丝画布的中心与尺寸（世界坐标）。"""
    X0, Y0, X1, Y1 = FIL_BOX
    return px_to_world((X0 + X1) / 2, (Y0 + Y1) / 2, anchor_world), ((X1 - X0) / PPU, (Y1 - Y0) / PPU)


def bridge_point(anchor_world):
    """连接丝中点（烧断处）的世界坐标。"""
    L = filament_layers()
    return px_to_world(ANCHOR_PX[0], ANCHOR_PX[1] + 6, anchor_world)


def socket():
    """胶木灯头（RGBA）：深褐近黑的圆柱，几道横向凹槽，左侧一道高光，下沿可被灯泡照亮（lit 层另给）。"""
    def make():
        w, h = 1040, 560
        x = np.linspace(-1, 1, w)[None, :]
        y = np.linspace(0, 1, h)[:, None]
        shade = 0.55 + 0.45 * np.sqrt(np.clip(1 - x ** 2, 0, 1))
        hl = np.exp(-((x + 0.45) / 0.10) ** 2) * 0.9 + np.exp(-((x - 0.6) / 0.05) ** 2) * 0.25
        grooves = 1 - 0.35 * (np.abs(np.sin(y * np.pi * 7)) ** 18)
        base = np.array([0.075, 0.055, 0.042])
        rgb = base * (shade * grooves)[..., None] + (hl * grooves)[..., None] * np.array([0.16, 0.14, 0.12])
        rng = np.random.default_rng(4)
        rgb *= (1 + 0.08 * gaussian_filter(rng.standard_normal((h, w)), 2))[..., None]
        edge = np.clip((1 - np.abs(x)) * 40, 0, 1) * np.ones_like(y)
        lit = np.clip((y - 0.70) / 0.30, 0, 1) ** 2 * np.sqrt(np.clip(1 - x ** 2, 0, 1))   # 下沿被灯泡照亮的部分
        return np.dstack([rgb, edge, lit * edge]).astype(np.float32)
    return _cache("socket", make)


def cord():
    """双股绞合的花线（RGBA），竖直一段，可平铺：两股布包线交替缠绕，深褐色，布纹细密。"""
    def make():
        w, h = 200, 1600
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        period = 150.0
        ph = 2 * np.pi * yy / period
        img = np.zeros((h, w, 4), np.float32)
        rng = np.random.default_rng(9)
        weave = 1 + 0.12 * np.sin(yy * 0.9 + xx * 0.6) * np.sin(yy * 0.5 - xx * 0.8)
        weave *= 1 + 0.06 * gaussian_filter(rng.standard_normal((h, w)), 1.2)
        for k, off in enumerate((0.0, np.pi)):
            cx = w / 2 + 34 * np.sin(ph + off)
            depth = np.cos(ph + off)                        # 前面的一股更亮、盖住后面的一股
            r = 42
            d = np.abs(xx - cx) / r
            m = np.clip((1 - d) * 6, 0, 1)
            shade = (0.55 + 0.45 * np.sqrt(np.clip(1 - d ** 2, 0, 1))) * (0.75 + 0.25 * depth)
            col = np.array([0.16, 0.10, 0.06]) * (shade * weave)[..., None]
            front = (depth > 0) if k == 0 else (depth <= 0)
            sel = m > 0.01
            put = sel & (front | (img[..., 3] < 0.01))
            img[put, :3] = col[put]
            img[put, 3] = np.maximum(img[put, 3], m[put])
        return img
    return _cache("cord", make)


if __name__ == "__main__":
    g = glass()
    L = filament_layers()
    print(g.shape, L.shape, socket().shape, cord().shape)
    out = ROOT / "renders" / "seg_c" / "assets"
    out.mkdir(parents=True, exist_ok=True)
    Image.fromarray((np.clip(g * 2.2, 0, 1) * 255).astype(np.uint8)).resize((g.shape[1] // 3, g.shape[0] // 3)).save(out / "bulb_01_玻璃.png")
    vis = np.clip(L[0] + L[1] + L[2] * 0.7 + L[3] * 0.7 + L[4] * 0.4, 0, 1)
    comp = g.copy() * 1.6
    X0, Y0, X1, Y1 = FIL_BOX
    x0, y0 = X0 - CROP[0], Y0 - CROP[1]
    comp[y0:y0 + vis.shape[0], x0:x0 + vis.shape[1]] += vis[..., None] * np.array([1.0, 0.85, 0.6])
    Image.fromarray((np.clip(comp, 0, 1) * 255).astype(np.uint8)).resize((g.shape[1] // 3, g.shape[0] // 3)).save(out / "bulb_02_灯丝.png")
