"""L18 与间奏一的红帆船：香港"鸭灵号"（Duk Ling）的侧面照片抠出来，风格化成那个年代的红帆。

照片（assets/images/Duk_Ling_in_HK_harbour.jpg，NickStenning 摄，CC BY-SA 2.0）是一艘三桅中式帆船的正侧面，背景是
灰白的雾气和水面。帆是红色，船身、桅杆和帆骨是深褐色，都和背景分得开：取"红"（R 明显高于 G、B）与"暗"两种
阈值的并集，再用包住船的多边形去掉水面。现代的痕迹去掉：船身上的英文船名和数字涂成船身的颜色，帆下面那座
红白相间的铁架子挖掉。帆的颜色换成褪色红（#B5412E），保留布面的明暗、帆骨和褶皱。主帆上用褪色的美术字黄
印着旧字"大海航行"与"靠舵手"两行，颜色随布面的明暗走，边缘有剥落。

照片里船头朝左；片中船向右航行，所以把照片左右翻转后使用（翻转在文字印上去之前做，帆上的字是正的）。
三面帆分成单独的图层（被风鼓满时各自变形），船身和桅杆是一层。下面的坐标都是翻转后照片的像素（1920×1440）。
"""
import numpy as np
import skia
from PIL import Image
from scipy import ndimage

from common import IMG, RED, cached, disk_cached, look
from engine import Tex

PHOTO = IMG / "Duk_Ling_in_HK_harbour.jpg"
PW = 1920


def _fx(pts):
    """原照片坐标 → 翻转后的坐标。"""
    return [(PW - x, y) for x, y in pts]
BBOX = (PW - 1740, 280, PW - 300, 1250)           # 船在照片里的范围 (x0, y0, x1, y1)
MAST_TOP = (PW - 826, 352)                        # 主桅顶（桅灯的位置）
BOW = (PW - 440, 1110)                            # 船头破浪处：船首柱与画面上看得见的浪顶相交的地方（激起水花）
WATERLINE = 1228
HULL_POLY = _fx([(320, 985), (420, 975), (640, 1000), (1220, 1000), (1350, 975), (1500, 935), (1590, 960), (1580, 1030),
             (1530, 1060), (1470, 1130), (1395, 1200), (1335, 1236), (520, 1238), (455, 1205), (405, 1085), (330, 1035)])
SAILS = {"fore": _fx([(318, 520), (500, 520), (640, 700), (640, 1010), (318, 1010)]),
         "main": _fx([(680, 285), (980, 285), (1285, 840), (1285, 965), (680, 965)]),
         "mizzen": _fx([(1470, 620), (1560, 620), (1725, 870), (1725, 935), (1470, 935)])}
MASTS = [((PW - a[0], a[1]), (PW - b[0], b[1]), w) for a, b, w in
         [((440, 545), (445, 1000), 9), ((828, 345), (785, 990), 12), ((1512, 680), (1512, 960), 8)]]
MODERN = [(PW - 790, 880, PW - 655, 995)]         # 红白铁架
LETTERS = [(PW - x1, y0, PW - x0, y1) for x0, y0, x1, y1 in
           [(410, 1050, 545, 1125), (1350, 1015, 1515, 1068), (440, 1150, 480, 1185), (1225, 1215, 1265, 1235)]]
MAIN_X = (PW - 1285, PW - 680)                    # 主帆的横向范围


def _poly(shape, pts):
    h, w = shape
    arr = np.zeros((h, w), np.uint8)
    s = skia.Surface.MakeRasterDirect(skia.ImageInfo.MakeA8(w, h), arr)
    c = s.getCanvas()
    p = skia.Path()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    p.close()
    c.drawPath(p, skia.Paint(AntiAlias=True, Color=skia.ColorWHITE))
    del c, s
    return arr.astype(np.float32) / 255


def _lines(shape, segs):
    h, w = shape
    arr = np.zeros((h, w), np.uint8)
    s = skia.Surface.MakeRasterDirect(skia.ImageInfo.MakeA8(w, h), arr)
    c = s.getCanvas()
    for a, b, wd in segs:
        c.drawLine(*a, *b, skia.Paint(AntiAlias=True, Color=skia.ColorWHITE, StrokeWidth=wd,
                                      StrokeCap=skia.Paint.kRound_Cap))
    del c, s
    return arr.astype(np.float32) / 255


def _old_text_mask(shape):
    """主帆上的旧字：两行宋体美术字，压扁一点，按帆面的位置排好。"""
    h, w = shape
    arr = np.zeros((h, w), np.uint8)
    s = skia.Surface.MakeRasterDirect(skia.ImageInfo.MakeA8(w, h), arr)
    c = s.getCanvas()
    for text, cy, size in ((look.trad("大海航行"), 655, 100), (look.trad("靠舵手"), 815, 104)):
        f = look.font("serif", 900, size, scale_x=0.95)
        adv = f.measureText(text)
        tracking = size * 0.10
        x = (PW - 985) - (adv + tracking * (len(text) - 1)) / 2
        for ch in text:
            c.drawString(ch, x, cy + size * 0.36, f, skia.Paint(AntiAlias=True, Color=skia.ColorWHITE))
            x += f.measureText(ch) + tracking
    del c, s
    return arr.astype(np.float32) / 255


def layers():
    """{"hull", "fore", "main", "mizzen"}：各层的 RGBA（直通 alpha，裁到 BBOX）。"""
    def make():
        a = np.asarray(Image.open(PHOTO).convert("RGB"), np.float32)[:, ::-1] / 255
        a = np.ascontiguousarray(a)
        H, W = a.shape[:2]
        R, G, B = a[..., 0], a[..., 1], a[..., 2]
        lum = a.mean(2)
        red = np.clip(((R - (G + B) / 2) - 0.05) / 0.06, 0, 1)
        dark = np.clip((0.42 - lum) / 0.09, 0, 1)
        hullish = np.clip((0.58 - lum) / 0.10, 0, 1)          # 雾里的船身偏灰，比水面暗得多
        hull_reg = _poly((H, W), HULL_POLY)
        mast_reg = _lines((H, W), [(p, q, wd * 2.2) for p, q, wd in MASTS])
        sail_regs = {k: _poly((H, W), v) for k, v in SAILS.items()}
        any_sail = np.clip(sum(sail_regs.values()), 0, 1)
        modern = np.zeros((H, W), np.float32)
        for x0, y0, x1, y1 in MODERN:
            modern[y0:y1, x0:x1] = 1.0
        modern *= 1 - mast_reg
        # 船身：暗部阈值，再闭运算补齐，水线以下截掉
        hull = hullish * hull_reg
        hull = ndimage.grey_closing(hull, size=(5, 5))
        hull[WATERLINE:] = 0
        # 船身上的英文名和数字：用周围船身的颜色填掉
        col = a.copy()
        hole = np.zeros((H, W), bool)
        for x0, y0, x1, y1 in LETTERS:
            sub = lum[y0:y1, x0:x1]
            hole[y0:y1, x0:x1] = sub > 0.45
        hole = ndimage.binary_dilation(hole, iterations=3)
        keep = (~hole) & (hull > 0.5)
        wsum = ndimage.gaussian_filter(keep.astype(np.float32), 6)
        for k in range(3):
            fill = ndimage.gaussian_filter(col[..., k] * keep, 6) / np.maximum(wsum, 1e-4)
            col[..., k] = np.where(hole, fill, col[..., k])
        hull = np.where(hole, 1.0, hull) * hull_reg
        masts = np.maximum(dark, 0) * mast_reg
        hull_l = np.clip(np.maximum(hull, masts) * (1 - modern), 0, 1)
        # 帆：红色阈值与帆骨（帆面范围内的暗线）
        out = {}
        x0, y0, x1, y1 = BBOX
        # 帆的颜色：亮度保留布面的明暗，色相换成褪色红
        sl = col.mean(2, keepdims=True)
        red_col = RED[None, None, :] * (sl / 0.52) ** 0.9
        bat_col = np.array([0.20, 0.13, 0.10]) * (sl / 0.3)
        txt = _old_text_mask((H, W))
        wear = ndimage.gaussian_filter(np.random.default_rng(4).normal(0, 1, (H, W)), 2.0)
        wear = np.clip((wear + 0.9) / 0.6, 0, 1)
        yel = (np.array(look.C["yellow"]) * 0.7 + 0.3 * np.array(look.C["yellow"]).mean()) * 0.8 * (sl / 0.52) ** 0.9
        for k, reg in sail_regs.items():
            m = np.clip(np.maximum(red, hullish * 0.95) * reg * (1 - modern), 0, 1)
            m = m * (1 - np.clip(mast_reg * dark * 1.5, 0, 1))          # 桅杆留在船身层
            rr = np.clip(red, 0, 1)[..., None]
            c3 = red_col * rr + bat_col * (1 - rr)
            if k == "main":
                tm = (txt * wear * rr[..., 0])[..., None] * 0.62
                c3 = c3 * (1 - tm) + yel * tm
            out[k] = np.dstack([np.clip(c3, 0, 2), m])[y0:y1, x0:x1].astype(np.float32)
        # 船身：雾气去掉，换成深褐的旧木色，保留木纹与明暗
        hl = col.mean(2, keepdims=True)
        hc = np.array([0.17, 0.115, 0.085])[None, None, :] * (hl / 0.33) ** 1.4
        out["hull"] = np.dstack([hc, hull_l])[y0:y1, x0:x1].astype(np.float32)
        return np.stack([out["hull"], out["fore"], out["main"], out["mizzen"]])
    arr = disk_cached("junk_layers_v3", make)
    return dict(zip(("hull", "fore", "main", "mizzen"), arr))


def textures():
    def make():
        return {k: Tex(v) for k, v in layers().items()}
    return cached("junk_tex", make)


if __name__ == "__main__":
    import sys
    L = layers()
    x0, y0, x1, y1 = BBOX
    bg = np.zeros((y1 - y0, x1 - x0, 3), np.float32) + np.array([0.12, 0.14, 0.18])
    for k in ("hull", "fore", "mizzen", "main"):
        a = L[k]
        bg = bg * (1 - a[..., 3:]) + np.clip(a[..., :3], 0, 1) * a[..., 3:]
    Image.fromarray((np.clip(bg, 0, 1) * 255).astype(np.uint8)).save(sys.argv[1])
