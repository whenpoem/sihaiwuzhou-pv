"""副歌一样片：木桌桌面（L08 的刻字、L09 前半句烧穿）。

桌面是一张俯视的平面，镜头从上往下看，画面上方朝 -z。底图是 Poly Haven 的旧木板照片（CC0），截取上下相邻的四块木板。
L08"嚴格了　三十年後　誰　的腰"刻在第二块木板上；L09 前半句"未來被熔斷在"在第三块木板上逐字烧穿，"斷"字时这块木板
从中间断开，两半向下翻落。

贴图分三张：
  albedo  uint8 RGBA，RGB 为木纹，A 为 L08 每个字刻出的时刻（编码见 CARVE_T0、CARVE_SPAN）；
  aux     float RGBA，R 为 L08 凹槽的覆盖率，G 为铁水灌到该处的时刻，B 为 L09 字形的覆盖率，A 为该处烧穿的时刻；
  glow    float RGBA（低分辨率），R 为凹槽向周围木面投下的暖光，G 为烧穿的字投下的暖光。
时刻都相对 T_BASE（秒）。显卡材质 desk_c（见 mats.py）按 u_time 决定每个像素此刻的样子，所以动画不需要逐帧重画贴图。
"""
import sys
from pathlib import Path

import numpy as np
import skia
from scipy import ndimage

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "style"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "film"))
import look  # noqa: E402
import plan  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "cache" / "seg_c"
WOOD = ROOT / "assets" / "images" / "Wood_planks_diff_8k_Amal_Kumar_via_Poly_Haven_.png"

ROW0, ROW1 = 960, 2674             # 照片里截取的行：四块木板，木板缝在 1426、1818、2212
SRC_PPU = 389.5                    # 照片每世界单位的像素数
SIZE = (3840 / SRC_PPU, (ROW1 - ROW0) / SRC_PPU)     # 桌面尺寸 (沿 x, 沿 z) ≈ (9.86, 4.40)
UP = 1.6                           # 底图放大倍数
AUX_SCALE = 0.75                   # aux 相对底图的分辨率
T_BASE = 50.0
CARVE_T0, CARVE_SPAN = 50.8, 4.0   # A 通道 = (刻出时刻 - CARVE_T0) / CARVE_SPAN
NEVER = 99.0
VERSION = 4                        # 改动贴图的做法后加 1，缓存随之更新


def z_of_row(row):
    return (row - ROW0) / SRC_PPU - SIZE[1] / 2


PLANK = [(z_of_row(a), z_of_row(b)) for a, b in ((960, 1426), (1426, 1818), (1818, 2212), (2212, 2674))]
L08_Z = sum(PLANK[1]) / 2          # L08 所在木板的中线（相对桌面中心）
L09_Z = sum(PLANK[2]) / 2
L08_H, L09_H = 0.34, 0.56          # 字高（世界单位）
L08_KIND, L09_KIND = ("sans", 700), ("serif", 900)


def _px(shape):
    """世界坐标（相对桌面中心，x 向右、z 向下）→ 像素坐标的比例与偏移。"""
    h, w = shape
    return w / SIZE[0], h / SIZE[1]


def _text_mask(text, kind, weight, height, cx, cz, shape, spacing=1.0):
    """把一行字画进 shape 大小的覆盖率图：字高 height，字距 height×spacing，整行居中于 (cx, cz)。
    返回覆盖率和逐字信息 [(字, 字心 x, 字心 z, 该字的覆盖率图)]。全角空格占一个字位。"""
    sx, sz = _px(shape)
    em = height * sz
    f = look.font(kind, weight, em)
    n = len(text)
    out = np.zeros(shape, np.float32)
    chars = []
    for i, ch in enumerate(text):
        if ch == "　":
            continue
        x = cx + (i - (n - 1) / 2) * height * spacing
        s = skia.Surface(shape[1], shape[0])
        c = s.getCanvas()
        b = skia.Rect()
        f.measureText(ch, bounds=b)
        px = (x + SIZE[0] / 2) * sx - (b.left() + b.right()) / 2
        pz = (cz + SIZE[1] / 2) * sz - (b.top() + b.bottom()) / 2
        c.drawString(ch, px, pz, f, look.white_paint())
        m = look.to_np(s)[..., 3]
        out = np.maximum(out, m)
        chars.append((ch, x, cz, m))
    return out, chars


def build():
    CACHE.mkdir(parents=True, exist_ok=True)
    fa, fx, fg = (CACHE / f"desk_{k}_v{VERSION}.npy" for k in ("albedo", "aux", "glow"))
    if fa.exists() and fx.exists() and fg.exists():
        return np.load(fa), np.load(fx), np.load(fg)
    look.low_priority()
    from PIL import Image, ImageFilter
    im = Image.open(WOOD).convert("RGB").crop((0, ROW0, 3840, ROW1))
    W, H = int(3840 * UP), int((ROW1 - ROW0) * UP)
    im = im.resize((W, H), Image.LANCZOS).filter(ImageFilter.UnsharpMask(radius=2.0, percent=60, threshold=2))
    wood = np.asarray(im, np.float32) / 255
    # 旧桌面：清漆发暗、偏红褐，边缘被手磨得更暗
    wood = wood ** 1.15 * np.array([0.92, 0.80, 0.68])
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    rim = np.clip(np.minimum(np.minimum(xx, W - xx), np.minimum(yy, H - yy)) / (0.35 * SRC_PPU * UP), 0, 1)
    wood *= (0.82 + 0.18 * rim)[..., None]

    # L08 刻字：覆盖率与刻出时刻
    ah, aw = int(H * AUX_SCALE), int(W * AUX_SCALE)
    t08 = plan._CHARS[7]
    text08 = look.trad(look.lyric(8))
    g08, chars08 = _text_mask(text08, *L08_KIND, L08_H, 0.0, L08_Z, (ah, aw))
    carve = np.zeros((ah, aw), np.float32)
    for (ch, x, z, m), tc in zip(chars08, t08):
        carve = np.where(m > 0.02, tc, carve)
    # 字外的像素取最近那个字的时刻：缩放贴图时字的边缘不会混进更早的时刻，字不会提前露出轮廓
    idx = ndimage.distance_transform_edt(carve <= 0, return_indices=True)[1]
    carve = carve[idx[0], idx[1]]
    # 铁水沿整行从左往右灌满：在第 33 小节首拍到下一拍之间，每个字内部再从上往下略有先后
    t0, t1 = plan.BAR(33), plan.BAR(33, 2)
    sx, sz = _px((ah, aw))
    xs = np.array([c[1] for c in chars08])
    ux = ((np.arange(aw) / sx - SIZE[0] / 2) - xs.min() + L08_H / 2) / (xs.max() - xs.min() + L08_H)
    uz = (np.arange(ah) / sz - SIZE[1] / 2 - (L08_Z - L08_H / 2)) / L08_H
    fill = t0 + (t1 - t0) * (np.clip(ux, 0, 1)[None, :] * 0.85 + np.clip(uz, 0, 1)[:, None] * 0.15)
    fill += look.fbm(ah, aw, 30, 3, 11) * 0.06

    # L09 前半句：烧穿的字。烧穿的时刻从笔画中心往外推进（中心先穿，边缘后穿），字外的焦痕继续向外慢慢扩开
    text09 = look.trad(look.lyric(9).split("　")[0])
    t09 = plan._CHARS[8][:len(text09)]
    g09, chars09 = _text_mask(text09, *L09_KIND, L09_H, 0.0, L09_Z, (ah, aw), spacing=1.08)
    burn = np.full((ah, aw), NEVER, np.float32)
    ppu = sx
    noise = look.fbm(ah, aw, 18, 4, 12)
    for (ch, x, z, m), tc in zip(chars09, t09):
        inside = m > 0.5
        d_in = ndimage.distance_transform_edt(inside) / ppu              # 到字形边界的距离（世界单位）
        d_out = ndimage.distance_transform_edt(~inside) / ppu
        dmax = max(d_in.max(), 1e-4)
        tb = np.where(inside, tc + 0.03 + 0.16 * (1 - d_in / dmax), tc + 0.19 + d_out * 7.0)
        tb = tb + (noise - 0.5) * 0.06
        near = d_out < 0.12
        burn = np.where(near & (tb < burn), tb, burn)
    aux = np.dstack([g08, fill - T_BASE, g09, np.minimum(burn, NEVER) - T_BASE]).astype(np.float32)

    # 暖光：凹槽和烧穿的字向周围木面投下的光，按距离衰减
    gh, gw = 450, int(450 * SIZE[0] / SIZE[1])
    from cv2 import resize, INTER_AREA
    small08 = resize(g08, (gw, gh), interpolation=INTER_AREA)
    small09 = resize(g09, (gw, gh), interpolation=INTER_AREA)
    # 每个字的暖光从它自己烧起的时刻才亮：记下每处暖光主要来自哪个字
    per = []
    for (ch, x, z, m), tc in zip(chars09, t09):
        sm = resize(m, (gw, gh), interpolation=INTER_AREA)
        per.append(ndimage.gaussian_filter(sm, 0.4 * (gw / SIZE[0])))
    owner = np.argmax(np.stack(per), axis=0)
    t_on = np.array(t09, np.float32)[owner] - T_BASE
    gppu = gw / SIZE[0]
    glow08 = ndimage.gaussian_filter(small08, 0.12 * gppu) * 3.0 + ndimage.gaussian_filter(small08, 0.5 * gppu) * 4.0
    glow09 = ndimage.gaussian_filter(small09, 0.08 * gppu) * 2.0 + ndimage.gaussian_filter(small09, 0.4 * gppu) * 2.5
    glow = np.dstack([glow08, glow09, t_on, np.ones_like(glow08)]).astype(np.float32)

    code = np.clip((resize(carve, (W, H)) - CARVE_T0) / CARVE_SPAN, 0, 1)
    albedo = np.dstack([np.clip(wood, 0, 1), code])
    albedo = (albedo * 255 + 0.5).astype(np.uint8)
    np.save(fa, albedo)
    np.save(fx, aux)
    np.save(fg, glow)
    return albedo, aux, glow


def char_positions():
    """L09 前半句各字的字心 (x, z)，相对桌面中心；供滴落的铁水和镜头使用。"""
    text09 = look.trad(look.lyric(9).split("　")[0])
    n = len(text09)
    return [((i - (n - 1) / 2) * L09_H * 1.08, L09_Z) for i in range(n)]


if __name__ == "__main__":
    a, x, g = build()
    print(a.shape, x.shape, g.shape, SIZE, PLANK, L08_Z, L09_Z)
    from PIL import Image
    Image.fromarray(a[::4, ::4, :3]).save(ROOT / "renders" / "seg_c" / "desk_albedo_preview.png")
