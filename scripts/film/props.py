"""各段共用的占位素材：文字转图像、字形图集、字形采样点、报纸字栏纹理、翻板场纹理、标签纹理。
都返回 0–1 的 RGBA 浮点数组（直通 alpha），交给引擎做成纹理。"""
import sys
from pathlib import Path

import numpy as np
import skia
from scipy.ndimage import gaussian_filter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "style"))
import look  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def text_rgba(text, kind="serif", weight=400, size=48, color=(1, 1, 1), trad=False, pad=None, scale_x=1.0):
    """把一行字画成紧贴字形的 RGBA 图像；size 是字号（像素）。"""
    if trad:
        text = look.trad(text)
    f = look.font(kind, weight, size, scale_x)
    w = int(np.ceil(f.measureText(text))) + 2
    pad = int(size * 0.25) if pad is None else pad
    m = look.text_layer([(text, f, pad, pad + size * 0.88, None)], w + 2 * pad, int(size * 1.25) + 2 * pad)
    rgba = np.zeros(m.shape + (4,), np.float32)
    rgba[..., :3] = color
    rgba[..., 3] = m
    return rgba


def glyph_atlas(chars, kind="serif", weight=600, cell=96):
    """字形图集（引擎的 Atlas）：atlas.uv("字串") 或 atlas.index_uv(序号数组) 给出纹理坐标。"""
    from engine import glyph_atlas as _ga
    return _ga(chars, kind, weight, cell)


def sample_text_points(text, n, height=1.0, center=(0, 0, 0), kind="serif", weight=500, seed=0):
    """在一行字（竖直平面、正对 +z）的字形内部均匀采样 n 个点，返回 (n, 3) 世界坐标。"""
    rng = np.random.default_rng(seed)
    px = 160
    f = look.font(kind, weight, px)
    w = int(f.measureText(text)) + 20
    m = look.text_layer([(text, f, 10, px * 0.88 + 10, None)], w, px + 40)
    ys, xs = np.nonzero(m > 0.5)
    i = rng.choice(len(xs), n, replace=len(xs) < n)
    s = height / px
    x = (xs[i] - w / 2 + rng.uniform(-0.5, 0.5, n)) * s
    y = -(ys[i] - (px + 40) / 2 + rng.uniform(-0.5, 0.5, n)) * s
    return np.c_[x, y, np.zeros(n)] + np.asarray(center, float)


def newsprint_texture(w=1024, h=1024, seed=3):
    """报纸字栏：竖排的仿宋小字一栏栏排开，栏间有细线；纸色偏黄。用作字栏铺成的海。"""
    rng = np.random.default_rng(seed)
    pool = "".join(look.lyric(n) for n in range(1, 41)).replace("　", "")
    s = look.surface(w, h)
    c = s.getCanvas()
    c.clear(skia.Color4f(*look.C["paper"], 1))
    f = look.font("fang", 400, 22)
    col_w = 26
    for x in range(8, w - 20, col_w):
        if (x // col_w) % 12 == 11:
            c.drawLine(x + 6, 0, x + 6, h, skia.Paint(Color=skia.Color4f(0.3, 0.25, 0.2, 0.5), StrokeWidth=1))
            continue
        y = 22.0
        while y < h:
            ch = pool[rng.integers(len(pool))]
            c.drawString(look.trad(ch), x, y, f, skia.Paint(Color=skia.Color4f(0.18, 0.15, 0.12, 0.85), AntiAlias=True))
            y += 24
    img = look.to_np(s)
    return np.dstack([img[..., :3], np.ones((h, w), np.float32)])


def label_texture(name, col, w=640, h=360):
    """纯色底加一行说明文字，作暂时没有素材的占位。"""
    s = look.surface(w, h)
    c = s.getCanvas()
    c.clear(skia.Color4f(*col, 1))
    f = look.font("serif", 600, 56)
    tw = f.measureText(name)
    lum = sum(col) / 3
    tc = (0.1, 0.1, 0.1) if lum > 0.5 else (0.9, 0.9, 0.9)
    c.drawString(name, (w - tw) / 2, h / 2 + 20, f, skia.Paint(Color=skia.Color4f(*tc, 1), AntiAlias=True))
    img = look.to_np(s)
    return np.dstack([img[..., :3], np.ones((h, w), np.float32)])


def card_field_texture(text, rows=2, ch_cells=44, px=6):
    """翻板场：每块板 px×px 像素、板间留 1 像素暗缝；红底，墨量过半的格子为黄色。text 里的全角空格分行。"""
    lines = text.split("　") if rows == 2 else [text.replace("、", "")]
    ncol = max(len(l) for l in lines)
    gap, margin, lgap = 6, 8, 12
    C = 2 * margin + ncol * ch_cells + (ncol - 1) * gap
    R = 2 * margin + len(lines) * ch_cells + (len(lines) - 1) * lgap
    k = 8
    f = look.font("sans", 800, ch_cells * k * 0.97, scale_x=0.96)
    items = []
    for i, t in enumerate(lines):
        x = (C - (len(t) * ch_cells + (len(t) - 1) * gap)) / 2 * k
        top = (margin + i * (ch_cells + lgap)) * k
        for ch in t:
            b = skia.Rect()
            f.measureText(ch, bounds=b)
            items.append((ch, f, x + (ch_cells * k - b.width()) / 2 - b.left(),
                          top + (ch_cells * k - b.height()) / 2 - b.top(), None))
            x += (ch_cells + gap) * k
    m = look.text_layer(items, C * k, R * k).reshape(R, k, C, k).mean((1, 3)) > 0.45
    rng = np.random.default_rng(1)
    col = np.where(m[..., None], look.C["yellow"], look.C["red"]) * (1 + rng.normal(0, 0.05, (R, C, 1)))
    img = np.zeros((R * px, C * px, 3), np.float32) + 0.03
    for r in range(R):
        img[r * px:(r + 1) * px - 1, :, :] = np.repeat(col[r], px, axis=0)[None]
    img[:, px - 1::px] = 0.03
    return np.dstack([np.clip(img, 0, 1), np.ones(img.shape[:2], np.float32)])


def soft_dot(n=64):
    yy, xx = np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1
    a = np.clip(1 - np.hypot(xx, yy), 0, 1) ** 1.5
    return np.dstack([np.ones((n, n, 3), np.float32), a.astype(np.float32)])


def soft_square(n=32):
    a = np.ones((n, n), np.float32)
    a = gaussian_filter(np.pad(a, 2), 0.8)[2:-2, 2:-2]
    return np.dstack([np.ones((n, n, 3), np.float32), a])


def square_atlas(n=32):
    """单个柔边方片的图集，用于翻板碎片。"""
    from engine import Atlas
    return Atlas(soft_square(n)[..., 3], {"sq": (0, 0, 1, 1)}, ["sq"])


def dot():
    from engine import dot_atlas
    return dot_atlas(64, 0.0)
