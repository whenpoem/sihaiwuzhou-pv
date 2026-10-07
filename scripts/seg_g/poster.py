"""间奏二里每层画面下面压着的旧标语纸。

每层画面撕开时，先露出贴在它下面的一张旧纸，纸上印着这一层的旧字，随后旧纸也被撕开，才露出更早的那一层。
旧纸的底取自 handoff 用过的同一张公有领域旧纸扫描（Old_paper7.jpg），每层取不同的一块；旧字用美术字
（思源宋体或思源黑体的最粗字重），印刷磨损造成的缺墨和套印偏移按噪声生成。红纸黄字的那几层，把纸染成褪色红，
字印成美术字黄。

贴图 2560 × 1440，字的大小以贴图高为单位给出，场景里旧纸平面的高度是撕开那一刻画面高度的 2.7 倍，
所以字高 0.155 对应撕开时约 42% 的画面高。
"""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "style"))
sys.path.insert(0, str(HERE.parent / "film"))
import look  # noqa: E402
import handoff  # noqa: E402

ROOT = HERE.parents[1]
CACHE = ROOT / "data" / "cache" / "seg_g"
VERSION = 2
W, H = 2560, 1440

# 各层旧纸：(行, 字体, 纸色, 字色, 照片上取用的左上角)。纸色为 None 时用旧纸本色。
# 旧纸上的字不重复这一层画面里已经看得见的旧字，而是同一出处里的另一句，或这一段里出现过的另一句旧字：
# 电视雪花里闪过的口号印在它下面的纸上；标语墙下面是副歌一水花里那句诗；报纸字栏的海里帆上是"大海航行靠舵手"，
# 下面压着 D 段地球上的那句。第一层白帆上本来就印着旧字，城市、雨夜和锁孔三层不垫旧纸。
POSTERS = {
    "tv": (["形勢大好", "不是小好"], "sans", None, "red", (300, 200)),
    "sheets": (["東方紅", "太陽升"], "sans", "red", "yellow", (600, 100)),
    "wall": (["不管風吹浪打", "勝似閒庭信步"], "serif", None, "red", (150, 500)),
    "newspaper": (["歸根結底", "是你們的"], "serif", None, "red", (450, 350)),
}
CHAR_H = 0.155          # 字高（贴图高为 1）
LINE_GAP = 0.30         # 行距（字高为 1）


def _text_mask(lines, kind, rng):
    import skia
    from scipy.ndimage import gaussian_filter
    s = look.surface(W, H)
    c = s.getCanvas()
    px = CHAR_H * H
    f = look.font(kind, 900, px)
    n = len(lines)
    total = n * px + (n - 1) * px * LINE_GAP
    y0 = (H - total) / 2
    for i, line in enumerate(lines):
        b = skia.Rect()
        f.measureText(line, bounds=b)
        trk = px * 0.12
        width = sum(f.measureText(ch) for ch in line) + trk * (len(line) - 1)
        x = (W - width) / 2
        base = y0 + i * px * (1 + LINE_GAP) + px * 0.88
        for ch in line:
            # 每个字略有高低和转角，像手工排的大字
            c.save()
            c.translate(x + f.measureText(ch) / 2, base - px * 0.4)
            c.rotate(float(rng.normal(0, 0.8)))
            c.translate(-(x + f.measureText(ch) / 2), -(base - px * 0.4))
            c.drawString(ch, x, base + float(rng.normal(0, px * 0.012)), f, look.white_paint())
            c.restore()
            x += f.measureText(ch) + trk
    m = look.to_np(s)[..., 3]
    return gaussian_filter(m, 0.8)


def _wear(rng, shape):
    """印刷磨损：大块的缺墨（纸面不平处没有沾到墨）和细碎的白点。"""
    from scipy.ndimage import gaussian_filter
    h, w = shape
    big = gaussian_filter(rng.normal(0, 1, (h // 8, w // 8)).astype(np.float32), 6)
    big = np.kron(big / (big.std() + 1e-6), np.ones((8, 8), np.float32))[:h, :w]
    big = gaussian_filter(big, 4)
    fine = gaussian_filter(rng.normal(0, 1, shape).astype(np.float32), 1.2)
    fine /= fine.std() + 1e-6
    keep = np.clip(0.5 + 0.45 * big, 0, 1) * np.clip(1.6 + 0.9 * fine, 0, 1)
    return np.clip(0.35 + 0.75 * keep, 0, 1)


def poster(name):
    """返回 (H, W, 3) float32 的旧纸贴图；没有旧字的层返回 None。"""
    if name not in POSTERS:
        return None
    f = CACHE / f"poster_{name}_v{VERSION}.npy"
    if f.exists():
        return np.load(f).astype(np.float32)
    from PIL import Image
    from scipy.ndimage import gaussian_filter
    lines, kind, paper_c, ink_c, (ox, oy) = POSTERS[name]
    rng = np.random.default_rng(sum(map(ord, name)) * 31 + 7)
    photo = Image.open(handoff.PAPER_PHOTO).convert("RGB")
    pw, ph = photo.size
    cw = min(pw - ox, int((ph - oy) * W / H))
    crop = photo.crop((ox, oy, ox + cw, oy + int(cw * H / W))).resize((W, H), Image.LANCZOS)
    paper = np.asarray(crop, np.float32) / 255.0
    m = paper.mean((0, 1))
    paper = np.clip(m + (paper - m) * 1.5, 0, 1)
    lum = paper.mean(2, keepdims=True) / max(float(m.mean()), 1e-3)
    if paper_c is not None:
        # 染成褪色红的纸：保留照片的明暗和污渍，颜色换成红
        base = look.C[paper_c] * np.array([0.92, 0.95, 0.95], np.float32)
        paper = np.clip(base * lum ** 1.2, 0, 1)
    mask = _text_mask(lines, kind, rng)
    wear = _wear(rng, mask.shape)
    ink = mask * wear
    # 套印偏移：墨色略淡的一层错开几个像素，字边因此有一圈浅色
    shift = np.roll(np.roll(mask, 4, 0), -3, 1) * 0.25 * wear
    ink_rgb = look.C[ink_c].astype(np.float32)
    if paper_c is None:
        # 红墨印在白纸上：正片叠底
        out = paper * (1 - ink[..., None]) + paper * ink_rgb * ink[..., None]
        out = out * (1 - shift[..., None] * 0.3) + paper * ink_rgb * shift[..., None] * 0.3
    else:
        # 黄墨印在红纸上：墨盖住纸，墨里透出纸的纹理
        ink_col = ink_rgb * (0.75 + 0.25 * lum)
        out = paper * (1 - ink[..., None]) + ink_col * ink[..., None]
    # 纸边有一圈发黄发暗的旧痕，越靠外越深
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    e = np.minimum(np.minimum(xx, W - 1 - xx) / W, np.minimum(yy, H - 1 - yy) / H)
    out *= (0.82 + 0.18 * np.clip(e / 0.08, 0, 1))[..., None]
    out = np.clip(gaussian_filter(out, (0.5, 0.5, 0)), 0, 1).astype(np.float32)
    CACHE.mkdir(parents=True, exist_ok=True)
    np.save(f, out.astype(np.float16))
    return out


if __name__ == "__main__":
    from PIL import Image
    out = ROOT / "renders" / "seg_g"
    out.mkdir(parents=True, exist_ok=True)
    for n in (sys.argv[1:] or POSTERS):
        a = poster(n)
        Image.fromarray((a * 255).astype(np.uint8)).resize((W // 2, H // 2)).save(out / f"poster_{n}.png")
        print(n)
