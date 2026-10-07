"""纸面上的钢笔字：把 strokes 生成的墨迹数据贴图摆成平面，交给 a2_ink 材质按书写时间显出。

一个字是一块正方形平面，覆盖 strokes.BOX 的范围（em），中心就是表意字框的中心。字可以绕中心转一个小角度、
上下错开一点，这是手写字的自然起伏；也可以整体转 90 度等任意角度（"口"里的字随镜头横过来写）。
"""
import sys
import zlib
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "film"))
sys.path.insert(0, str(HERE.parent / "style"))
from engine import Plane, Tex  # noqa: E402
import handoff as HO  # noqa: E402

import mats  # noqa: E402,F401
import strokes as ST  # noqa: E402

_TEX = {}
FIB_TILE = HO.PAPER_UNI["fib_tile"]      # 纤维贴图一块的世界长度


def fiber_tex():
    """与旧纸共用的纤维纹理（handoff.paper_fibers），墨迹沿纸面上看得见的纤维洇开。"""
    return HO.paper_fibers()


def ink_tex(ch, ppe):
    key = (ch, ppe)
    if key not in _TEX:
        _TEX[key] = Tex(ST.ink_tex_data(ch, ppe).astype(np.float32), premultiplied=True)
    return _TEX[key]


# 字框中心相对贴图中心的偏移（em）：贴图覆盖 BOX，字框为 [0, 1] × [-0.88, 0.12]
_BX = ST.BOX
_TEX_C = ((_BX[0] + _BX[2]) / 2, (_BX[1] + _BX[3]) / 2)
_BOX_C = (0.5, -0.38)


def jitter(key, amp_y=0.035, amp_r=2.2, amp_s=0.035):
    """手写的起伏：由字和位置决定的固定随机量 (dy 比例, 转角 度, 缩放)。"""
    rng = np.random.default_rng(zlib.crc32(key.encode("utf-8")))
    return rng.normal(0, amp_y), rng.normal(0, amp_r), 1.0 + rng.normal(0, amp_s)


def char_plane(ch, center, em, t0, dur, age=0.0, rot=0.0, z=0.003, ppe=512, bleed=None, gain=1.0,
               stack="paper", wipe=(0.0, 0.0), group="past", opacity=1.0, sx=1.0):
    """一个钢笔字。center 为字框中心的世界坐标 (x, y)，em 为字高（世界单位），rot 为整字转角（度，逆时针）。
    t0、dur 为开始书写的时刻与书写时长（秒），age 为褪色程度。"""
    tex = ink_tex(ch, ppe)
    w = (_BX[2] - _BX[0]) * em * sx                 # sx：沿字的横向压扁（照片翻面时用）
    h = (_BX[3] - _BX[1]) * em
    # 贴图中心与字框中心不重合时按转角换算
    off = np.array([(_TEX_C[0] - _BOX_C[0]) * sx, -(_TEX_C[1] - _BOX_C[1])]) * em
    r = np.radians(rot)
    R = np.array([[np.cos(r), -np.sin(r)], [np.sin(r), np.cos(r)]])
    c = np.asarray(center, float) + R @ off
    uni = {"ink_t0": float(t0), "ink_dur": float(dur), "ink_age": float(age), "ink_em": float(em),
           "ink_bleed": float(em * 0.006 if bleed is None else bleed), "fibers": fiber_tex(), "fib_tile": FIB_TILE,
           "ink_gain": float(gain), "ink_wipe": tuple(map(float, wipe))}
    return Plane(tex, center=(c[0], c[1], z), size=(w, h), rot=(0, 0, rot), blend="multiply", material="a2_ink",
                 uniforms=uni, group=group, stack=stack, opacity=opacity)


def em_to_world(center, em, rot, ex, ey):
    """字内的 em 坐标 (ex, ey)（y 向下，基线 y = 0）→ 世界坐标。"""
    d = np.array([(ex - _BOX_C[0]) * em, -(ey - _BOX_C[1]) * em])
    r = np.radians(rot)
    R = np.array([[np.cos(r), -np.sin(r)], [np.sin(r), np.cos(r)]])
    return np.asarray(center, float) + R @ d
