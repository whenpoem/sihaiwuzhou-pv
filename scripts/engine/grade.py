"""两套调色的参数与逐帧随机量（划痕、灰尘、片门抖动、亮度闪烁）。

参数默认值与 scripts/style/look.py 的 grade_past / grade_present 相同（来自本人认可的样张三）。
像素尺度的参数（光晕半径、划痕宽度、抖动幅度）按 1080 像素高定义，其他输出尺寸按比例换算。

逐帧随机量都由帧号决定：同一帧无论单独渲染还是在分段里渲染，颗粒和划痕都完全相同，分段拼接处没有跳变。
"""
import math
import warnings

import numpy as np

DEFAULTS = {
    "past": {
        "exposure": 1.0,                 # 调色前的曝光倍数，过曝转场时调高
        "halation": 1.6,                 # 高光周围橙色光晕的强度
        "halation_threshold": 0.85,      # 进入光晕的亮度阈值（三通道平均）
        "halation_radius": 26.0,         # 光晕的高斯半径（像素，1080p）
        "halation_color": (1.0, 0.45, 0.15),
        "shoulder": 0.55,                # 高光肩部 x/(1+k·x) 的 k
        "lift": 0.035,                   # 黑位抬起
        "gain": 1.3,
        "warmth": (1.06, 0.97, 0.80),    # 偏暖褪青
        "sat": 0.9,                      # 饱和度
        "vignette": 0.32,                # 暗角
        "grain": 0.028,                  # 胶片颗粒
        "scratch": 1.0,                  # 细划痕出现的频度（0 为没有；True 等于 1）
        "dust": 0.0,                     # 每帧灰尘斑点的平均个数
        "weave": 0.0,                    # 片门抖动幅度（像素，1080p）
        "flicker": 0.0,                  # 亮度闪烁幅度（例如 0.03）
        "bg": (0.0, 0.0, 0.0),           # 过去层的底色
    },
    "present": {
        "exposure": 1.0,
        "bloom": 0.35,                   # 亮处泛光
        "bloom_threshold": 0.8,
        "shoulder": 0.15,
        "black": 0.02,                   # 黑位
        "bg": None,                      # None 表示透明，叠在过去层之上；给颜色则不透明
    },
    "final": {
        "fade": 0.0,                     # 整体淡到 fade_color 的程度，0–1
        "fade_color": (0.0, 0.0, 0.0),
    },
}

_warned = set()


def merge(spec_grade):
    out = {g: dict(v) for g, v in DEFAULTS.items()}
    for g, params in (spec_grade or {}).items():
        if g not in out:
            if g not in _warned:
                warnings.warn(f"未知的调色组 {g!r}，可用 past / present / final")
                _warned.add(g)
            continue
        for k, v in (params or {}).items():
            if k not in out[g] and (g, k) not in _warned:
                warnings.warn(f"未知的调色参数 {g}.{k}")
                _warned.add((g, k))
            out[g][k] = v
    sc = out["past"]["scratch"]
    out["past"]["scratch"] = 1.0 if sc is True else (0.0 if sc is False or sc is None else float(sc))
    return out


def _rng(*keys):
    return np.random.default_rng([abs(int(k)) % (2 ** 32) for k in keys])


def scratches(frame, fps, rate, out_w, out_h, scale):
    """胶片划痕：时间按 0.4 秒分窗，每个窗口以一定概率出现一条划痕，持续 0.15–0.9 秒。
    划痕在持续期间位置缓慢漂移、亮度闪动、沿竖直方向轻微弯曲，像真实胶片上随片子走过片门的划痕。
    look.grade_past 的划痕是一条宽 2 像素、把颜色向白推 30% 的竖线，这里的强度为 1 时与它相同。"""
    if rate <= 0:
        return []
    t = frame / fps
    win = 0.4
    w0 = int(math.floor(t / win))
    out = []
    for w in range(w0 - 3, w0 + 1):
        r = _rng(w, 7919)
        if r.random() >= min(0.42 * rate, 0.95):
            continue
        start = (w + r.random()) * win
        dur = r.uniform(0.15, 0.9)
        if not (start <= t < start + dur):
            continue
        x0 = r.uniform(0.06, 0.94) * out_w
        drift = r.normal(0, 30) * scale
        fr = _rng(frame, w, 31)
        x = x0 + drift * (t - start) + fr.normal(0, 0.5) * scale
        strength = r.uniform(0.55, 1.0) * fr.uniform(0.55, 1.0)
        if r.random() < 0.6:
            y0, y1 = -0.1, 1.1
        else:
            a, b = sorted(r.uniform(-0.1, 1.1, 2))
            y0, y1 = a, max(b, a + 0.25)
        out.append(((x, 2.0 * scale * r.uniform(0.7, 1.2), strength, r.uniform(0, 6.28)),
                    (y0, y1, r.uniform(0, 2.5) * scale, r.uniform(2, 9))))
        if len(out) >= 8:
            break
    return out


def dust(frame, amount, out_w, out_h, scale):
    """灰尘斑点：每帧独立出现，只停留一帧。多数是暗斑，少数是亮斑（底片上的划伤）。"""
    if amount <= 0:
        return []
    r = _rng(frame, 4243)
    n = min(int(r.poisson(amount)), 32)
    out = []
    for _ in range(n):
        out.append((r.uniform(0, out_w), r.uniform(0, out_h), r.uniform(0.8, 3.2) * scale,
                    r.uniform(0.4, 0.9) * (1 if r.random() < 0.25 else -1)))
    return out


def weave(frame, fps, amount, scale):
    """片门抖动：低频的缓慢漂移加上逐帧的小跳动，返回像素偏移 (dx, dy)。"""
    if amount <= 0:
        return (0.0, 0.0)
    t = frame / fps
    r = _rng(frame, 101)
    dx = 0.6 * math.sin(t * 2.1 + 1.3) + 0.4 * math.sin(t * 5.3 + 0.2) + r.normal(0, 0.35)
    dy = 0.6 * math.sin(t * 1.7 + 4.1) + 0.4 * math.sin(t * 4.1 + 2.7) + r.normal(0, 0.35)
    return (dx * amount * scale, dy * amount * scale)


def flicker(frame, amount):
    if amount <= 0:
        return 1.0
    return 1.0 + amount * float(_rng(frame, 577).uniform(-1, 1))
