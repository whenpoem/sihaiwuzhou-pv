"""D 段各模块共用的路径、缓存和小工具。

D 段是副歌一后半（L15–L18）与间奏一，75.4–102.05 秒。贴图第一次用到时生成，大的存进 data/cache/seg_d/，
之后的进程直接读盘；小的只在进程内缓存。
"""
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent
for p in (SCRIPTS, SCRIPTS / "style", SCRIPTS / "film"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import look  # noqa: E402
import plan  # noqa: E402
from flatcam import cached, ease, ramp  # noqa: E402,F401

ROOT = plan.ROOT
IMG = ROOT / "assets" / "images"
CACHE = ROOT / "data" / "cache" / "seg_d"
CACHE.mkdir(parents=True, exist_ok=True)
RENDERS = ROOT / "renders" / "seg_d"

WARM = np.array(look.C["warm"], np.float32)
RED = np.array(look.C["red"], np.float32)
INK = np.array(look.C["ink"], np.float32)
NIGHT = np.array(look.C["night"], np.float32)


def warm(k=1.15):
    """暗底上的歌词色（暖白），k 为亮度倍数。"""
    return tuple(float(v) for v in WARM * k)


def disk_cached(name, fn):
    """贴图存盘缓存：data/cache/seg_d/name.npy 存在就读，否则调用 fn() 生成并写盘。进程内再缓存一层。"""
    def load():
        p = CACHE / f"{name}.npy"
        if p.exists():
            return np.load(p)
        a = fn()
        np.save(p, a)
        return a
    return cached("disk:" + name, load)


def smooth(x, a, b):
    """numpy 版 smoothstep。"""
    u = np.clip((np.asarray(x, float) - a) / (b - a), 0.0, 1.0)
    return u * u * (3 - 2 * u)


def out_cubic(u):
    u = min(max(u, 0.0), 1.0)
    return 1 - (1 - u) ** 3


def in_cubic(u):
    u = min(max(u, 0.0), 1.0)
    return u ** 3


def lerp(a, b, u):
    return a + (b - a) * u


def chars(n):
    """第 n 行歌词的繁体字序列（去掉全角空格），与 plan.T(n, k) 的字序一致。"""
    return [c for c in look.trad(look.lyric(n)) if c != "　"]


def onsets(n):
    return list(plan._CHARS[n - 1])


def hash01(*k):
    """若干整数 → 稳定的 0–1 随机数（跨进程不变）。"""
    h = 2166136261
    for v in k:
        h = ((h ^ (int(v) & 0xFFFFFFFF)) * 16777619) & 0xFFFFFFFF
    h ^= h >> 13
    h = (h * 1274126177) & 0xFFFFFFFF
    return (h & 0xFFFFFF) / float(0x1000000)


def decay(t, t0, tau):
    """t0 之后按指数衰减的包络，t0 之前为 0。"""
    return math.exp(-(t - t0) / tau) if t >= t0 else 0.0
