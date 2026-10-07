"""H 段各模块共用的路径、缓存和小工具。

H 段是桥段、尾段与结尾（L33–L40，164.9333–199.7654 秒，帧 9896 到片尾 11985）。贴图第一次用到时生成，
大的存进 data/cache/seg_h/，之后的进程直接读盘；小的只在进程内缓存。
"""
import hashlib
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent
for p in (SCRIPTS, SCRIPTS / "style", SCRIPTS / "film", HERE):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

import look  # noqa: E402
import plan  # noqa: E402
from plan import T, BAR  # noqa: E402,F401
from flatcam import cached, ease, ramp  # noqa: E402,F401

ROOT = plan.ROOT
IMG = ROOT / "assets" / "images"
CACHE = ROOT / "data" / "cache" / "seg_h"
CACHE.mkdir(parents=True, exist_ok=True)
RENDERS = ROOT / "renders" / "seg_h"
LAYERS = ROOT / "renders" / "layers"

RED = np.array(look.C["red"], np.float32)
YELLOW = np.array(look.C["yellow"], np.float32)
WARM = np.array(look.C["warm"], np.float32)
INK = np.array(look.C["ink"], np.float32)
SUN = np.array(look.C["sun"], np.float32)
NIGHT = np.array(look.C["night"], np.float32)
PAPER = np.array(look.C["paper"], np.float32)


def disk_cached(name, fn, version=""):
    """贴图存盘缓存：data/cache/seg_h/name.npy 存在就读，否则调用 fn() 生成并写盘。进程内再缓存一层。
    version 写进文件名，生成方法改动后换一个版本号即可让旧缓存失效。"""
    fname = f"{name}_{version}.npy" if version else f"{name}.npy"

    def load():
        p = CACHE / fname
        if p.exists():
            return np.load(p)
        a = fn()
        np.save(p, a)
        return a
    return cached("disk:" + fname, load)


def smooth(x, a, b):
    """numpy 版 smoothstep，x 可以是数组。"""
    u = np.clip((np.asarray(x, float) - a) / (b - a), 0.0, 1.0)
    return u * u * (3 - 2 * u)


def smoother(u):
    u = np.clip(u, 0.0, 1.0)
    return u * u * u * (u * (u * 6 - 15) + 10)


def out_cubic(u):
    u = np.clip(u, 0.0, 1.0)
    return 1 - (1 - u) ** 3


def in_cubic(u):
    u = np.clip(u, 0.0, 1.0)
    return u ** 3


def lerp(a, b, u):
    return a + (b - a) * u


def decay(t, t0, tau):
    """t0 之后按指数衰减的包络，t0 之前为 0。"""
    return math.exp(-(t - t0) / tau) if t >= t0 else 0.0


def chars(n, simplified=False):
    """第 n 行歌词的字序列（去掉全角空格），与 plan.T(n, k) 的字序一致。缺省为繁体。"""
    s = look.lyric(n) if simplified else look.trad(look.lyric(n))
    return [c for c in s if c != "　"]


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


def key_of(*parts):
    return hashlib.md5(repr(parts).encode("utf-8")).hexdigest()[:10]


def euler_from_matrix(R):
    """旋转矩阵 (N,3,3) → 引擎粒子的 (yaw, pitch, roll)（弧度），满足 R = Ry(yaw)·Rx(pitch)·Rz(roll)。"""
    # R[1,2] = -sin(pitch)；R[0,2] = sin(yaw)cos(pitch)，R[2,2] = cos(yaw)cos(pitch)；
    # R[1,0] = cos(pitch)sin(roll)，R[1,1] = cos(pitch)cos(roll)
    sp = np.clip(-R[:, 1, 2], -1.0, 1.0)
    pitch = np.arcsin(sp)
    yaw = np.arctan2(R[:, 0, 2], R[:, 2, 2])
    roll = np.arctan2(R[:, 1, 0], R[:, 1, 1])
    # pitch = ±90° 时 yaw 与 roll 不能分开求：取 yaw = 0，roll 由第一行求出
    sing = np.abs(sp) > 0.99999
    if sing.any():
        yaw[sing] = 0.0
        roll[sing] = np.arctan2(-R[sing, 0, 1], R[sing, 0, 0])
    return np.stack([yaw, pitch, roll], 1).astype(np.float32)


def rot_x(a):
    """绕 x 轴转 a（弧度，数组）→ (N,3,3)。"""
    c, s = np.cos(a), np.sin(a)
    R = np.zeros((len(a), 3, 3), np.float32)
    R[:, 0, 0] = 1
    R[:, 1, 1], R[:, 1, 2], R[:, 2, 1], R[:, 2, 2] = c, -s, s, c
    return R


def rot_axes(yaw, pitch, roll=None):
    """(N,) 的 yaw、pitch、roll → 旋转矩阵 (N,3,3)，R = Ry·Rx·Rz。"""
    n = len(yaw)
    cy, sy, cp, sp = np.cos(yaw), np.sin(yaw), np.cos(pitch), np.sin(pitch)
    if roll is None:
        roll = np.zeros(n)
    cr, sr = np.cos(roll), np.sin(roll)
    R = np.empty((n, 3, 3), np.float32)
    # Ry·Rx·Rz 展开
    R[:, 0, 0] = cy * cr + sy * sp * sr
    R[:, 0, 1] = -cy * sr + sy * sp * cr
    R[:, 0, 2] = sy * cp
    R[:, 1, 0] = cp * sr
    R[:, 1, 1] = cp * cr
    R[:, 1, 2] = -sp
    R[:, 2, 0] = -sy * cr + cy * sp * sr
    R[:, 2, 1] = sy * sr + cy * sp * cr
    R[:, 2, 2] = cy * cp
    return R


def facing_rot(basis):
    """正对镜头的平面转角 (yaw, pitch, roll)（度）：平面的右、上、法线分别对准画面的右、上和镜头。"""
    right, up, fwd = basis
    R = np.stack([right, up, -fwd], 1).astype(np.float32)[None]
    e = euler_from_matrix(R)[0]
    return tuple(float(v) for v in np.degrees(e))
