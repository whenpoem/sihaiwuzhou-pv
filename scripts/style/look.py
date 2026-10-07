"""四张样张共用的东西：画幅、色板、字体、文字遮罩、噪声，以及"过去"和"今天"两套调色。

色板与字体对应 构思.md 第六章。颜色是 0–1 的 sRGB 数值。
"""
import ctypes
from pathlib import Path

import numpy as np
import skia
from PIL import Image
from scipy.ndimage import gaussian_filter

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "renders" / "style"
W, H = 1920, 1080


def low_priority():
    """把本进程设为低于正常的优先级，避免和前台操作抢占处理器。"""
    try:
        ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    except Exception:
        pass


def hexc(h):
    h = h.lstrip("#")
    return np.array([int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)


C = {
    "red": hexc("B5412E"),       # 褪色红：旧字
    "yellow": hexc("E2B23F"),    # 美术字黄：旧字第二色
    "paper": hexc("E8DCC0"),     # 旧纸黄
    "ink": hexc("3A2519"),       # 墨褐：亮底上的歌词
    "warm": hexc("F3E5CA"),      # 暖白：暗底上的歌词
    "sun": hexc("FFE4A8"),       # 日光金
    "night": hexc("0E131B"),     # 夜蓝黑
    "white": hexc("FFFFFF"),     # 今白
    "black": hexc("050608"),     # 今黑
}

_FONT_FILES = {
    "serif": Path(r"C:\Windows\Fonts\NotoSerifSC-VF.ttf"),     # 思源宋体：歌词、宋体美术字
    "sans": Path(r"C:\Windows\Fonts\NotoSansSC-VF.ttf"),       # 思源黑体：黑体美术字
    "fang": ROOT / "assets" / "fonts" / "ZhuqueFangsong-Regular.ttf",   # 朱雀仿宋：诗词、报纸字栏
    "kai": ROOT / "assets" / "fonts" / "LXGWWenKai-Regular.ttf",        # 霞鹜文楷：钢笔字
}
_tf_cache = {}


def typeface(kind="serif", weight=400):
    """取字体；思源宋体和思源黑体是可变字重字体，weight 取 200–900。"""
    key = (kind, weight)
    if key not in _tf_cache:
        base = skia.Typeface.MakeFromFile(str(_FONT_FILES[kind]))
        if kind in ("serif", "sans"):
            pos = skia.FontArguments.VariationPosition.Coordinates([
                skia.FontArguments.VariationPosition.Coordinate(0x77676874, float(weight))])
            args = skia.FontArguments()
            args.setVariationDesignPosition(skia.FontArguments.VariationPosition(pos))
            base = base.makeClone(args)
        _tf_cache[key] = base
    return _tf_cache[key]


def font(kind="serif", weight=400, size=64, scale_x=1.0):
    f = skia.Font(typeface(kind, weight), size)
    f.setScaleX(scale_x)
    f.setEdging(skia.Font.Edging.kAntiAlias)
    f.setSubpixel(True)
    return f


def surface(w=W, h=H):
    return skia.Surface(skia.ImageInfo.Make(w, h, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType))


def to_np(s):
    return s.makeImageSnapshot().toarray()[..., :4].astype(np.float32) / 255.0


def white_paint(alpha=1.0, **kw):
    return skia.Paint(Color=skia.Color4f(1, 1, 1, alpha), AntiAlias=True, **kw)


def text_layer(items, w=W, h=H):
    """在整幅画面上画字，返回 0–1 遮罩。items 为 [(文字, Font, x, y, 附加矩阵或 None)]，
    x、y 是第一个字的左端和基线；矩阵作用在整行上，用于透视和旋转。"""
    s = surface(w, h)
    c = s.getCanvas()
    for text, f, x, y, m in items:
        c.save()
        if m is not None:
            c.concat(m)
        c.drawString(text, x, y, f, white_paint())
        c.restore()
    return to_np(s)[..., 3]


def glyph_mask(ch, kind="sans", weight=900, px=256, pad=0.06, scale_x=1.0):
    """单字遮罩，放在 px×px 的方格中央。"""
    s = surface(px, px)
    c = s.getCanvas()
    size = px * (1 - 2 * pad)
    f = font(kind, weight, size, scale_x)
    b = skia.Rect()
    f.measureText(ch, bounds=b)
    x = (px - b.width()) / 2 - b.left()
    y = (px - b.height()) / 2 - b.top()
    c.drawString(ch, x, y, f, white_paint())
    return to_np(s)[..., 3]


def line_width(text, f):
    return f.measureText(text)


def lyric(n):
    """第 n 行歌词（1 起算，去掉空行后编号）。行内的全角空格是乐句间隔。"""
    lines = [l.strip() for l in (ROOT / "lyrics" / "歌词.txt").read_text(encoding="utf-8").splitlines() if l.strip()]
    return lines[n - 1]


_cc = None


def trad(text):
    """简体转繁体（OpenCC 标准繁体）。过去各层里的字（歌词与旧字）用繁体，今天各层里的字用简体；
    "太陽昇"按《东方红》歌本改回"升"。"""
    global _cc
    if _cc is None:
        import opencc
        _cc = opencc.OpenCC("s2t")
    return _cc.convert(text).replace("昇", "升")


def fbm(h, w, scale=64, octaves=5, seed=0):
    """分形噪声，0–1。scale 是最粗一层的特征尺寸（像素）。"""
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, tot, s = 1.0, 0.0, float(scale)
    for _ in range(octaves):
        out += gaussian_filter(rng.normal(0, 1, (h, w)).astype(np.float32), s / 3) * amp * (s / 3) ** 0.5
        tot += amp
        amp *= 0.55
        s /= 2
    out -= out.min()
    return out / (out.max() + 1e-6)


def grade_past(x, seed=0, halation=1.6, warmth=(1.06, 0.97, 0.80), lift=0.035, gain=1.3, grain=0.028,
               vignette=0.32, scratch=True, sat=0.9):
    """过去的层：高光周围的橙色光晕、柔和的高光肩部、抬起的黑位、偏暖褪青、暗角、颗粒、一道细划痕。
    参数默认值来自本人认可的样张三。"""
    rng = np.random.default_rng(seed)
    h, w = x.shape[:2]
    x = np.clip(x, 0, None)
    hi = np.clip(x.mean(2) - 0.85, 0, None)
    x = x + gaussian_filter(hi, 26)[..., None] * np.array([1.0, 0.45, 0.15]) * halation
    x = x / (1 + 0.55 * x)
    x = lift + x * gain
    x = x * np.array(warmth)
    lum = x.mean(2, keepdims=True)
    x = lum + (x - lum) * sat
    yy, xx = np.mgrid[0:h, 0:w]
    r2 = ((xx - w / 2) / (w / 2)) ** 2 + ((yy - h / 2) / (h / 2)) ** 2
    x *= (1.08 - vignette * r2 ** 1.4)[..., None]
    g = rng.normal(0, 1, (h, w)) + gaussian_filter(rng.normal(0, 1, (h, w)), 1.1) * 1.6
    x += (g * grain * (0.4 + lum[..., 0]))[..., None]
    if scratch:
        sx = int(w * rng.uniform(0.62, 0.8))
        x[:, sx:sx + 2] = x[:, sx:sx + 2] * 0.7 + 0.3
    return np.clip(x, 0, 1)


def grade_present(x, bloom=0.35, black=0.02):
    """今天的层：纯黑底、锐利，只在亮处加一点泛光，没有颗粒和暗角。"""
    x = np.clip(x, 0, None)
    hi = np.clip(x - 0.8, 0, None)
    x = x + (gaussian_filter(hi, (6, 6, 0)) * 0.6 + gaussian_filter(hi, (30, 30, 0)) * 0.4) * bloom
    x = x / (1 + 0.15 * x)
    x = black + x * (1 - black)
    return np.clip(x, 0, 1)


def over(base, col, alpha):
    """把纯色 col 按遮罩 alpha 叠到 base 上。"""
    a = alpha[..., None]
    return base * (1 - a) + np.asarray(col) * a


def save(img, name):
    OUT.mkdir(parents=True, exist_ok=True)
    Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype("u1")).save(OUT / name)
    print(OUT / name)
