"""读取 data/timing.json（由 scripts/timing.py 生成），并提供常用的缓动函数。

编号约定与 timing.json 和 构思.md 一致：歌词行号 1–40（即 L01–L40），行内字序从 1 起、不计全角空格；
小节号从 1 起；小节内的拍从 1 起，可以是小数（1.5 表示第一拍后的八分音符）。
字的起点取 timing.json 里修正到元音开始处的 "t"。

用法：
    from engine import timing as T
    T.char(1, 11)            # L01 第 11 个字"吵"的起点
    T.bar(17)                # 第 17 小节首拍
    T.beat(17, 3)            # 第 17 小节第 3 拍
    T.kicks(55, 60)          # 55–60 秒之间的底鼓起点
    T.ease("out_cubic", T.ramp(t, 1.0, 2.0))
"""
import bisect
import json
import math
from functools import lru_cache
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
PATH = ROOT / "data" / "timing.json"


class TimingMissing(FileNotFoundError):
    pass


@lru_cache(maxsize=1)
def _load(path_str, mtime):
    with open(path_str, encoding="utf-8") as f:
        return json.load(f)


def data(path=None):
    """读取并返回 timing.json 的全部内容（按文件修改时间缓存，文件更新后自动重新读取）。"""
    p = Path(path) if path else PATH
    if not p.exists():
        raise TimingMissing(f"找不到 {p}。这个文件由 scripts/timing.py 生成（逐字时间、小节网格、鼓点），"
                            "请先运行它，再使用 engine.timing。")
    return _load(str(p), p.stat().st_mtime)


# ---------------------------------------------------------------------------
# 歌词
# ---------------------------------------------------------------------------

def line(n):
    """第 n 行歌词（1 起）的完整记录：text、start、end、phrases、chars。"""
    lines = data()["lines"]
    if not 1 <= n <= len(lines):
        raise IndexError(f"歌词行号应在 1–{len(lines)}，收到 {n}")
    return lines[n - 1]


def chars(n):
    return line(n)["chars"]


def char(n, k, key="t"):
    """第 n 行第 k 个字（1 起，不计空格）的起点；key 可取 t（元音起点，缺省）、t_aligned、t_grid、end。"""
    cs = chars(n)
    if not 1 <= k <= len(cs):
        raise IndexError(f"L{n:02d} 只有 {len(cs)} 个字，收到第 {k} 个")
    return float(cs[k - 1][key])


def char_end(n, k):
    return char(n, k, "end")


def find_char(n, ch, occurrence=1):
    """在第 n 行里找第 occurrence 次出现的字 ch，返回它的字序（1 起）。"""
    seen = 0
    for i, c in enumerate(chars(n), 1):
        if c["ch"] == ch:
            seen += 1
            if seen == occurrence:
                return i
    raise KeyError(f"L{n:02d} 里没有第 {occurrence} 个“{ch}”")


def char_times(n, key="t"):
    return np.array([c[key] for c in chars(n)], float)


def line_span(n):
    L = line(n)
    return float(L["start"]), float(L["end"])


def line_at(t):
    """t 时正在唱（或刚唱完、下一行还没开始）的行号；前奏里返回 None。"""
    lines = data()["lines"]
    cur = None
    for L in lines:
        if L["start"] <= t:
            cur = L["n"]
        else:
            break
    return cur


# ---------------------------------------------------------------------------
# 节拍网格
# ---------------------------------------------------------------------------

def beat_period():
    return float(data()["beat_period"])


def bar_period():
    return float(data()["bar_period"])


def bar(k):
    """第 k 小节（1 起）首拍的时刻。超出列表时按恒定速度外推。"""
    d = data()
    bars = d["bars"]
    if 1 <= k <= len(bars):
        return float(bars[k - 1])
    return float(d["first_downbeat"]) + (k - 1) * float(d["bar_period"])


def beat(k, b=1.0):
    """第 k 小节第 b 拍（1 起，可为小数）的时刻。"""
    return bar(k) + (b - 1.0) * beat_period()


def bar_at(t):
    """t 所在的小节号与小节内的拍位置 (k, b)，b 从 1 起的小数。"""
    d = data()
    x = (t - float(d["first_downbeat"])) / float(d["bar_period"])
    k = int(math.floor(x)) + 1
    return k, 1.0 + (x - (k - 1)) * 4.0


def beats(t0=-math.inf, t1=math.inf):
    b = np.array(data()["beats"], float)
    return b[(b >= t0) & (b < t1)]


def bars(t0=-math.inf, t1=math.inf):
    b = np.array(data()["bars"], float)
    return b[(b >= t0) & (b < t1)]


def section(name):
    """按英文名或中文标签取段落 {name, label, start, end, first_bar, last_bar}。"""
    for s in data()["sections"]:
        if s["name"] == name or s["label"] == name:
            return s
    raise KeyError(f"没有段落 {name}；可用 {[s['name'] for s in data()['sections']]}")


def sections():
    return data()["sections"]


def event(name):
    """按名称取事件时刻（如 drums_in、cut），同名多个时返回列表。"""
    hits = [float(e["t"]) for e in data()["events"] if e["name"] == name]
    if not hits:
        raise KeyError(f"没有事件 {name}")
    return hits[0] if len(hits) == 1 else hits


# ---------------------------------------------------------------------------
# 鼓点
# ---------------------------------------------------------------------------

def _drum(kind, t0, t1, min_strength):
    xs = data()["drums"][kind]
    return np.array([x["t"] for x in xs if t0 <= x["t"] < t1 and x.get("strength", 1.0) >= min_strength], float)


def kicks(t0=-math.inf, t1=math.inf, min_strength=0.0):
    """底鼓起点。"""
    return _drum("kick", t0, t1, min_strength)


def snares(t0=-math.inf, t1=math.inf, min_strength=0.0):
    """军鼓起点。"""
    return _drum("snare", t0, t1, min_strength)


def hats(t0=-math.inf, t1=math.inf, min_strength=0.0):
    return _drum("hat", t0, t1, min_strength)


def last_before(times, t):
    """times（升序）中不晚于 t 的最后一个；没有时返回 None。"""
    i = bisect.bisect_right(list(times), t)
    return float(times[i - 1]) if i > 0 else None


def next_after(times, t):
    i = bisect.bisect_right(list(times), t)
    return float(times[i]) if i < len(times) else None


def hit(t, times, decay=0.25, attack=0.0):
    """鼓点包络：最近一次起点之后按指数衰减（decay 为时间常数，秒），attack>0 时起点前线性升起。"""
    times = np.asarray(times, float)
    if len(times) == 0:
        return 0.0
    v = 0.0
    p = last_before(times, t)
    if p is not None:
        v = math.exp(-(t - p) / decay)
    if attack > 0:
        q = next_after(times, t)
        if q is not None and q - t < attack:
            v = max(v, 1 - (q - t) / attack)
    return v


# ---------------------------------------------------------------------------
# 缓动
# ---------------------------------------------------------------------------

def clamp01(x):
    return min(max(x, 0.0), 1.0)


def ramp(t, t0, t1):
    """把 t 在 [t0, t1] 上线性映射到 0–1 并截断。"""
    if t1 == t0:
        return 1.0 if t >= t1 else 0.0
    return clamp01((t - t0) / (t1 - t0))


def lerp(a, b, u):
    return a + (b - a) * u


def linear(u):
    return u


def smoothstep(u):
    u = clamp01(u)
    return u * u * (3 - 2 * u)


def smootherstep(u):
    u = clamp01(u)
    return u * u * u * (u * (u * 6 - 15) + 10)


def in_quad(u): return u * u
def out_quad(u): return 1 - (1 - u) ** 2
def in_out_quad(u): return 2 * u * u if u < 0.5 else 1 - (-2 * u + 2) ** 2 / 2
def in_cubic(u): return u ** 3
def out_cubic(u): return 1 - (1 - u) ** 3
def in_out_cubic(u): return 4 * u ** 3 if u < 0.5 else 1 - (-2 * u + 2) ** 3 / 2
def in_quart(u): return u ** 4
def out_quart(u): return 1 - (1 - u) ** 4
def in_out_quart(u): return 8 * u ** 4 if u < 0.5 else 1 - (-2 * u + 2) ** 4 / 2
def in_quint(u): return u ** 5
def out_quint(u): return 1 - (1 - u) ** 5
def in_sine(u): return 1 - math.cos(u * math.pi / 2)
def out_sine(u): return math.sin(u * math.pi / 2)
def in_out_sine(u): return -(math.cos(math.pi * u) - 1) / 2
def in_expo(u): return 0.0 if u <= 0 else 2 ** (10 * u - 10)
def out_expo(u): return 1.0 if u >= 1 else 1 - 2 ** (-10 * u)
def in_out_expo(u):
    if u <= 0: return 0.0
    if u >= 1: return 1.0
    return 2 ** (20 * u - 10) / 2 if u < 0.5 else (2 - 2 ** (-20 * u + 10)) / 2
def in_circ(u): return 1 - math.sqrt(max(1 - u * u, 0.0))
def out_circ(u): return math.sqrt(max(1 - (u - 1) ** 2, 0.0))
def in_back(u, s=1.70158): return (s + 1) * u ** 3 - s * u ** 2
def out_back(u, s=1.70158): return 1 + (s + 1) * (u - 1) ** 3 + s * (u - 1) ** 2
def out_elastic(u):
    if u <= 0: return 0.0
    if u >= 1: return 1.0
    return 2 ** (-10 * u) * math.sin((u * 10 - 0.75) * (2 * math.pi) / 3) + 1


_EASES = {k: v for k, v in dict(globals()).items()
          if callable(v) and (k.startswith(("in_", "out_")) or k in ("linear", "smoothstep", "smootherstep"))}


def ease(name, u):
    """按名称取缓动：linear、smoothstep、smootherstep、in_/out_/in_out_ 加 quad、cubic、quart、quint、sine、
    expo、circ，以及 in_back、out_back、out_elastic。u 先截断到 0–1。"""
    if name not in _EASES:
        raise KeyError(f"没有缓动 {name}；可用 {sorted(_EASES)}")
    return _EASES[name](clamp01(u))


def tween(t, t0, t1, a, b, name="in_out_cubic"):
    """t 在 [t0, t1] 内按缓动 name 从 a 过渡到 b（a、b 可以是数或 numpy 数组）。"""
    u = ease(name, ramp(t, t0, t1))
    return np.asarray(a) + (np.asarray(b) - np.asarray(a)) * u if not np.isscalar(a) else a + (b - a) * u
