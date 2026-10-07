"""F 段各模块共用的路径、缓存和小工具。

F 段是副歌二 L23–L32，116.0–151.3333 秒（帧 6960–9079）。画面在今天：冷白、干净、无颗粒，歌词是简体、思源宋体
细字重的纯白字；旧字只以残影出现，用繁体、褪色红、不透明度 15%–25%，是画面里唯一的红色。贴图第一次用到时生成，
大的存进 data/cache/seg_f/，之后的进程直接读盘；小的只在进程内缓存。
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
from flatcam import ease, ramp  # noqa: E402,F401

_CACHE = {}


def cached(key, fn):
    """本段自己的贴图缓存（不与其他段共用 flatcam 的缓存字典：几段在同一进程里渲染时，同名的键不会互相顶替）。"""
    if key not in _CACHE:
        _CACHE[key] = fn()
    return _CACHE[key]

ROOT = plan.ROOT
IMG = ROOT / "assets" / "images"
CACHE = ROOT / "data" / "cache" / "seg_f"
CACHE.mkdir(parents=True, exist_ok=True)
RENDERS = ROOT / "renders" / "seg_f"

RED = np.array(look.C["red"], np.float32)
WHITE = np.array([1.0, 1.0, 1.0], np.float32)
COLD = np.array([0.80, 0.88, 1.0], np.float32)        # 冷白的光
CYAN = np.array([0.55, 0.92, 1.0], np.float32)        # 冷青：行情上涨、屏幕的亮色
LYRIC_W = (1.2, 1.2, 1.2)                              # present 组里纯白的歌词（调色曲线把 1.0 压到约 0.87）
GHOST_A = (0.15, 0.25)                                 # 残影的不透明度范围


def disk_cached(name, fn):
    """贴图存盘缓存：data/cache/seg_f/name.npy 存在就读，否则调用 fn() 生成并写盘。进程内再缓存一层。"""
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


def sm(t, a, b):
    """标量 smoothstep：t 从 a 到 b 由 0 缓入缓出地变到 1。"""
    return float(ease(ramp(t, a, b)))


def out_cubic(u):
    u = min(max(u, 0.0), 1.0)
    return 1 - (1 - u) ** 3


def pulse(t, t0, decay):
    """t0 之后按指数衰减的脉冲，t0 之前为 0。"""
    return math.exp(-(t - t0) / decay) if t >= t0 else 0.0


def chars(n):
    """第 n 行歌词（简体）去掉乐句间隔后的字列表。"""
    return list(look.lyric(n).replace("　", ""))


def onsets(n):
    return plan._CHARS[n - 1]


def phrases(n):
    """第 n 行按全角空格分开的乐句，以及每个乐句第一个字的字序。"""
    parts = look.lyric(n).split("　")
    out, k = [], 0
    for p in parts:
        out.append((p, k))
        k += len(p)
    return out


def soft_disc(n=256, p=2.0):
    """柔边圆点（直通 alpha 的白色 RGBA），中心最亮。"""
    yy, xx = np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1
    a = np.clip(1 - np.hypot(xx, yy), 0, 1) ** p
    return np.dstack([np.ones((n, n, 3), np.float32), a.astype(np.float32)])
