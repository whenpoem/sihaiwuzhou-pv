"""各段共用的平面镜头与审片工具。

平面长卷的做法来自副歌一样片（scripts/seg_c/flat.py）：素材全部正对观众，镜头始终朝 -z 看，只平移和推拉，
需要时绕视线转动。镜头状态用四个量描述：画面中心 (x, y)、画面高度 H（世界单位）和滚转角 roll（度）。镜头离
z = 0 平面的距离为 H·K，K = 1 / (2·tan(fov/2))，所以 H 直接决定 z = 0 平面上画面框住多大的范围。

关键位置之间按通道做单调三次插值（PCHIP）：相邻关键位置之间不过冲，速度连续，只有方向反转或停住的地方才减到零；
H 在对数空间插值，推拉看起来匀速。这条曲线避免了三维版"一停一顿"的问题。

    from flatcam import FlatCam, ease, ramp, cached, sheet, run
    CAM = FlatCam([(t, x, y, H), ...], fov=30)            # 第五项可选：roll（度）
    cam, H = CAM(t)                                       # 引擎的 Cam 与画面高度
    CAM.report(t0, t1)                                    # 打印平移、推拉速度的峰值，检查镜头是否太急

z ≠ 0 的平面按透视自然缩放、并以不同速度掠过画面（多层视差）。screen_to_world 把画面上的位置换算成某个深度上的
世界坐标，用来放置锁定在画面上的东西（如视觉余像、交接时的光点）。
"""
import math
import sys
import time
from pathlib import Path

import numpy as np
from scipy.interpolate import PchipInterpolator

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from engine import Cam, Film  # noqa: E402

ROOT = HERE.parents[1]


def ease(u):
    """smoothstep：0–1 之间缓入缓出。"""
    u = np.clip(u, 0.0, 1.0)
    return u * u * (3 - 2 * u)


def ramp(t, a, b):
    """t 从 a 到 b 线性地由 0 变到 1，两端截断。"""
    if b == a:
        return float(t >= a)
    return float(np.clip((t - a) / (b - a), 0.0, 1.0))


_C = {}


def cached(key, fn):
    """按键缓存贴图等只需计算一次的东西。"""
    if key not in _C:
        _C[key] = fn()
    return _C[key]


class FlatCam:
    """平面镜头。keys 为 [(t, x, y, H)] 或 [(t, x, y, H, roll)]，时间递增。

    shakes 为 [(t, 幅度, 频率, 衰减)]：幅度按画面高度的比例计，在 t 时刻起做竖直方向的阻尼振动，用于重物砸下。
    """

    def __init__(self, keys, fov=30.0, shakes=(), near=0.05, far=600.0):
        k = np.array([list(r) + [0.0] * (5 - len(r)) for r in keys], float)
        self.keys = k
        self.fov = fov
        self.K = 1.0 / (2.0 * math.tan(math.radians(fov / 2)))
        self.shakes = list(shakes)
        self.near, self.far = near, far
        if len(k) == 1:
            k = np.vstack([k, k + [1.0, 0, 0, 0, 0]])
        self._fx = PchipInterpolator(k[:, 0], k[:, 1])
        self._fy = PchipInterpolator(k[:, 0], k[:, 2])
        self._fh = PchipInterpolator(k[:, 0], np.log(k[:, 3]))
        self._fr = PchipInterpolator(k[:, 0], k[:, 4])
        self.t0, self.t1 = float(k[0, 0]), float(k[-1, 0])

    def state(self, t):
        """(x, y, H, roll)：关键位置范围之外停在两端。"""
        tt = min(max(t, self.t0), self.t1)
        x, y = float(self._fx(tt)), float(self._fy(tt))
        H, roll = float(np.exp(self._fh(tt))), float(self._fr(tt))
        for ts, amp, freq, dec in self.shakes:
            u = t - ts
            if 0 <= u < dec * 5:
                y += H * amp * math.exp(-u / dec) * math.sin(2 * math.pi * freq * u)
        return x, y, H, roll

    def __call__(self, t):
        x, y, H, roll = self.state(t)
        d = H * self.K
        r = math.radians(roll)
        up = (-math.sin(r), math.cos(r), 0.0)
        return Cam(eye=(x, y, d), target=(x, y, 0.0), up=up, fov=self.fov, near=self.near, far=self.far), H

    def screen_to_world(self, t, sx, sy, z=0.0):
        """画面上的位置 → 深度 z 处的世界坐标 (x, y)。sx、sy 为画面坐标的比例：(0, 0) 左上角，(1, 1) 右下角。
        同时返回该深度上一个画面高度对应的世界长度，用于按画面比例确定大小。"""
        x, y, H, roll = self.state(t)
        d = H * self.K
        s = (d - z) / d                              # 深度 z 处的放大比例（越远画面框住的范围越大）
        aspect = 16 / 9
        dx, dy = (sx - 0.5) * aspect * H * s, (0.5 - sy) * H * s
        r = math.radians(roll)
        wx = x + dx * math.cos(r) - dy * math.sin(r)
        wy = y + dx * math.sin(r) + dy * math.cos(r)
        return (wx, wy), H * s

    def report(self, t0=None, t1=None, dt=1 / 60, limit=0.5):
        """平移速度（每秒移过多少个画面高）与推拉速度（每秒 H 变化的倍率取对数）的峰值。
        平移超过 limit 的时段逐段列出：除非是有意设计的高速段落，否则应当放慢。"""
        t0 = self.t0 if t0 is None else t0
        t1 = self.t1 if t1 is None else t1
        ts = np.arange(t0, t1, dt)
        st = np.array([self.state(t)[:3] for t in ts])
        v = np.hypot(np.gradient(st[:, 0], dt), np.gradient(st[:, 1], dt)) / st[:, 2]
        z = np.abs(np.gradient(np.log(st[:, 2]), dt))
        print(f"平移峰值 {v.max():.2f} 画面高/秒（{ts[v.argmax()]:.2f} s），推拉峰值 {z.max():.2f}/秒（{ts[z.argmax()]:.2f} s）")
        fast = v > limit
        if fast.any():
            edges = np.flatnonzero(np.diff(np.r_[0, fast.astype(int), 0]))
            for a, b in zip(edges[::2], edges[1::2]):
                print(f"  {ts[a]:.2f}–{ts[b - 1]:.2f} s 平移超过 {limit}：峰值 {v[a:b].max():.2f}")
        return ts, v, z


# ---------------------------------------------------------------- 审片

def sheet(frame_fn, times, out, size=(640, 360), ss=1, cols=None, subframes=1):
    """按给定时刻渲染小图，拼成一张带时间码的总览图。size 是每张小图的尺寸。"""
    from PIL import Image, ImageDraw, ImageFont
    film = Film(frame_fn, fps=60, size=(1920, 1080), ss=ss)
    R = film.renderer(size=size, ss=ss)
    imgs = []
    t_start = time.time()
    for t in times:
        R.render(film.frame_fn, int(round(t * 60)), 60, subframes, 0.5)
        im = Image.fromarray(R.image().copy()[..., :3])
        d = ImageDraw.Draw(im)
        d.rectangle([0, 0, 92, 22], fill=(0, 0, 0))
        d.text((4, 3), f"{int(t // 60)}:{t % 60:05.2f}", fill=(255, 255, 0), font=ImageFont.truetype("arial.ttf", 16))
        imgs.append(im)
    print("秒/帧", round((time.time() - t_start) / max(len(times), 1), 3))
    cols = cols or min(len(imgs), 4 if size[0] > 700 else 5)
    rows = (len(imgs) + cols - 1) // cols
    sh = Image.new("RGB", (cols * (size[0] + 4) - 4, rows * (size[1] + 4) - 4), (40, 40, 40))
    for i, im in enumerate(imgs):
        sh.paste(im, ((i % cols) * (size[0] + 4), (i // cols) * (size[1] + 4)))
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    sh.save(out)
    print(out)


def run(frame_fn, name, t0, t1, out_dir, subframes=2):
    """各段脚本的统一入口：

    python scene.py preview [--from 秒 --to 秒]       每秒 30 帧、半分辨率、带时间码的预览
    python scene.py final   [--from 秒 --to 秒]       1080p、每秒 60 帧、2 倍超采样、运动模糊
    python scene.py sheet 输出.png 秒,秒,... [--size 640x360] [--ss 1]
    python scene.py still 秒 输出.png                  单帧全尺寸（2 倍超采样）
    """
    mode = sys.argv[1] if len(sys.argv) > 1 else "preview"
    args = sys.argv[2:]
    a = float(args[args.index("--from") + 1]) if "--from" in args else t0
    b = float(args[args.index("--to") + 1]) if "--to" in args else t1
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    if mode == "preview":
        film = Film(frame_fn, fps=30, size=(1920, 1080), ss=1)
        out = out_dir / f"{name}_预览.mp4"
        film.preview(a, b, str(out))
    elif mode == "final":
        film = Film(frame_fn, fps=60, size=(1920, 1080), ss=2)
        out = out_dir / f"{name}.mp4"
        film.render(a, b, str(out), subframes=subframes)
    elif mode == "sheet":
        out, times = args[0], [float(x) for x in args[1].split(",")]
        size = (640, 360)
        if "--size" in args:
            w, h = args[args.index("--size") + 1].split("x")
            size = (int(w), int(h))
        ss = int(args[args.index("--ss") + 1]) if "--ss" in args else 1
        sheet(frame_fn, times, out, size=size, ss=ss)
        return
    elif mode == "still":
        t, out = float(args[0]), args[1]
        film = Film(frame_fn, fps=60, size=(1920, 1080), ss=2)
        film.still(t, out, subframes=subframes(t) if callable(subframes) else subframes)
    else:
        raise SystemExit(run.__doc__)
    print(out)
