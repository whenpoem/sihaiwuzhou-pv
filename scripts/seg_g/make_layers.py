"""从各段渲染"层"的静帧：间奏二向下穿过的各层、主歌二上升时掠过的层带、尾段五个"快"冲破的各层，都是观众前面看到过的画面。

每层取对应段落里最有代表性的一帧，按 3840×2160 渲染，存到 renders/layers/{名字}.png。
python make_layers.py [名字 ...]
"""
import importlib.util
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
OUT = ROOT / "renders" / "layers"

# (名字, 场景脚本, 时刻)
LAYERS = [
    ("sail", "seg_f/scene.py", 9079 / 60),          # 副歌二最后一帧：间奏二从这里撕开
    ("city", "seg_f/scene.py", 122.6),              # 今天的城市与烧屏的 LED 立面
    ("tv", "seg_a2/scene.py", 35.1),                # 电视里的卫星云图（雪花里闪过的口号印在下面的旧纸上）
    ("sheets", "seg_b/scene.py", 42.2),             # 逆光的被单
    ("wall", "seg_c/flat.py", 61.2),                # 标语墙
    ("rain", "seg_d/scene.py", 77.9),               # 暴雨与单车的干轮廓
    ("newspaper", "seg_d/scene.py", 93.0),          # 报纸字栏的海
    ("keyhole", "seg_e/scene.py", 106.12),          # 锁片上的锁孔：间奏二从锁孔里穿过去
]


def load(rel):
    path = HERE.parent / rel
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(f"pv_{path.parent.name}_{path.stem}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def clean(fn):
    """去掉胶片颗粒、划痕、暗角和片门抖动再渲染：间奏二会给这些层重新加上随帧变化的颗粒，
    静帧里烤死的颗粒随层放大时会显得像贴在画面上。"""
    def wrapped(t):
        spec = fn(t)
        g = {k: dict(v) for k, v in (spec.grade or {}).items()}
        p = g.setdefault("past", {})
        p.update(grain=0.0, scratch=0.0, dust=0.0, weave=0.0, flicker=0.0, vignette=0.0)
        spec.grade = g
        return spec
    return wrapped


def main(names):
    from engine import Film
    OUT.mkdir(parents=True, exist_ok=True)
    film = None
    for name, rel, t in LAYERS:
        if names and name not in names:
            continue
        if not (HERE.parent / rel).exists():
            print(f"{name}：{rel} 还不存在，跳过")
            continue
        mod = load(rel)
        if film is None:
            film = Film(mod.frame, fps=60, size=(1920, 1080), ss=1)
        fn = clean(mod.frame)
        film.frame_fn = fn
        R = film.renderer(size=(3840, 2160), ss=1)
        R.render(fn, int(round(t * 60)), 60, 1, 0.5)
        img = R.image().copy()
        Image.fromarray(img).save(OUT / f"{name}.png")
        print(name, t, OUT / f"{name}.png")


if __name__ == "__main__":
    main(sys.argv[1:])
