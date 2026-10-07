"""主歌二（E 段，L19–L22）各模块共用的路径、缓存与小工具。"""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for p in (HERE, HERE.parent, HERE.parent / "style", HERE.parent / "film"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

IMG = ROOT / "assets" / "images"
CACHE = ROOT / "data" / "cache" / "seg_e"
OUT = ROOT / "renders" / "seg_e"
LUMA = np.array([0.299, 0.587, 0.114], np.float32)


def disk_cache(name, fn, version=1):
    """贴图只算一次：结果存成 data/cache/seg_e/{name}_v{version}.npy，之后直接读取。"""
    p = CACHE / f"{name}_v{version}.npy"
    if p.exists():
        return np.load(p)
    a = fn()
    CACHE.mkdir(parents=True, exist_ok=True)
    np.save(p, a)
    return a


def load_rgb(name, maxdim=None):
    """读取 assets/images 下的照片，返回 0–1 的 float32 RGB。"""
    from PIL import Image
    Image.MAX_IMAGE_PIXELS = None
    im = Image.open(IMG / name).convert("RGB")
    if maxdim and max(im.size) > maxdim:
        s = maxdim / max(im.size)
        im = im.resize((round(im.width * s), round(im.height * s)), Image.LANCZOS)
    return np.asarray(im, np.float32) / 255.0


def save_png(a, path, gain=1.0):
    """把 0–1 的数组存成 PNG 供检查；RGBA 按棋盘格底显示透明处。"""
    from PIL import Image
    a = np.asarray(a, np.float32)
    if a.ndim == 2:
        a = np.dstack([a] * 3)
    if a.shape[2] == 4:
        h, w = a.shape[:2]
        yy, xx = np.mgrid[0:h, 0:w]
        chk = (((yy // 32) + (xx // 32)) % 2 * 0.15 + 0.2)[..., None] * np.ones(3)
        a = a[..., :3] * a[..., 3:4] + chk * (1 - a[..., 3:4])
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray((np.clip(a[..., :3] * gain, 0, 1) * 255 + 0.5).astype(np.uint8)).save(path)


def smooth01(x, a, b):
    t = np.clip((np.asarray(x, np.float32) - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)
