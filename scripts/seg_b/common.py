"""B 段（主歌一后半 L05–L07，40.1167–51.0 秒）各模块共用的东西：路径、缓存、读图、世界坐标的分层。

世界的分层。B 段三句在三个深度上展开，镜头始终正对画面，只平移和推拉（flatcam.FlatCam），z 只用来分前后：

    Z_SHEET = 24   晾衣绳和被单（L05）；离镜头最近
    Z_BUILD = 16   虚化的苏式楼
    Z_SKY   = 0    积云、骑士、天上的歌词（L06），以及枕头和床单（L07）
    Z_FAR   = -80  远处的天色

FlatCam 的画面高 H 指 z = 0 平面上框住的高度。深度 z 处框住的高度为 H − z / K（K = 1 / (2 tan 15°)），所以 L05 里
被单那一层看到的范围比 H 小 12.86。三个深度拉开，是为了 L05→L06 镜头上移时被单落得快、楼落得慢、云几乎不动，
画面上自然显出远近；L06→L07 下移时，放在 z = 8–20 的近云从镜头前扫过，形成穿过云层的感觉。
"""
import hashlib
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent
ROOT = SCRIPTS.parent
for p in (HERE, SCRIPTS, SCRIPTS / "style", SCRIPTS / "film"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import look as L  # noqa: E402

IMG = ROOT / "assets" / "images"
CACHE = ROOT / "data" / "cache" / "seg_b"
RENDERS = ROOT / "renders" / "seg_b"
CHECK = RENDERS / "check"

FOV = 30.0
K = 1.0 / (2.0 * math.tan(math.radians(FOV / 2)))
Z_SHEET, Z_BUILD, Z_SKY, Z_FAR = 24.0, 16.0, 0.0, -80.0

LUMA = np.array([0.3, 0.55, 0.15], np.float32)
INK = tuple(float(c) for c in L.C["ink"])
RED = tuple(float(c) for c in L.C["red"])

_MEM = {}


def cached(key, fn):
    """进程内缓存：贴图只在第一次用到时生成。"""
    if key not in _MEM:
        _MEM[key] = fn()
    return _MEM[key]


def disk(name, fn, *key, dtype=np.float16):
    """把计算量大的数组存进 data/cache/seg_b/（npz），键里包含参数；参数或版本号变了就重新计算。"""
    CACHE.mkdir(parents=True, exist_ok=True)
    h = hashlib.md5(repr(key).encode()).hexdigest()[:10]
    mk = ("disk", name, h)
    if mk in _MEM:                                   # 同一进程里只读一次盘（frame(t) 每个子帧都可能调用）
        return _MEM[mk]
    p = CACHE / f"{name}_{h}.npz"
    if p.exists():
        with np.load(p) as z:
            a = z["a"].astype(np.float32) if dtype == np.float16 else z["a"]
    else:
        a = np.asarray(fn())
        np.savez(p, a=a.astype(dtype))
        a = a.astype(np.float32) if dtype == np.float16 else a
    _MEM[mk] = a
    return a


def photo(name):
    return np.asarray(Image.open(IMG / name).convert("RGB"), np.float32) / 255


def lum(im):
    return im[..., :3] @ LUMA


def ease(u):
    u = np.clip(u, 0.0, 1.0)
    return u * u * (3 - 2 * u)


def ramp(t, a, b):
    if b == a:
        return float(t >= a)
    return float(np.clip((t - a) / (b - a), 0.0, 1.0))


def smooth(t, a, b):
    return float(ease(ramp(t, a, b)))


def visible_h(H, z):
    """FlatCam 画面高为 H 时，深度 z 处框住的高度。"""
    return H - z / K


def save_png(arr, name):
    """检查用：把 0–1（可超过 1）的数组存成 PNG，放在 renders/seg_b/check/。"""
    CHECK.mkdir(parents=True, exist_ok=True)
    a = np.asarray(arr, np.float32)
    if a.ndim == 3 and a.shape[2] == 4:
        bg = np.ones_like(a[..., :3]) * 0.25
        bg[(np.indices(a.shape[:2]).sum(0) // 16) % 2 == 0] = 0.32
        a = bg * (1 - a[..., 3:4]) + a[..., :3] * a[..., 3:4]          # 直通 alpha
    Image.fromarray((np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)).save(CHECK / name)
    print(CHECK / name)
