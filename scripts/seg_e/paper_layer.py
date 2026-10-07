"""把前奏与主歌一交接处的旧纸（handoff.paper_frame，27.0 秒：纸面、台灯的光和落定的灰尘）按 3840×2160 渲染成一张图，
供上升段"旧纸"那几条层带使用。去掉颗粒、划痕、暗角和片门抖动，原因与 scripts/seg_g/make_layers.py 相同：
层带在上升段里会重新加上随帧变化的颗粒。输出 data/cache/seg_e/layer_paper.png。

python paper_layer.py
"""
import common
import handoff
from engine import Film
from PIL import Image

OUT = common.CACHE / "layer_paper.png"


def clean(t):
    spec = handoff.paper_frame(t)
    g = {k: dict(v) for k, v in (spec.grade or {}).items()}
    g.setdefault("past", {}).update(grain=0.0, scratch=0.0, dust=0.0, weave=0.0, flicker=0.0, vignette=0.0)
    spec.grade = g
    return spec


if __name__ == "__main__":
    film = Film(clean, fps=60, size=(1920, 1080), ss=1)
    R = film.renderer(size=(3840, 2160), ss=1)
    R.render(clean, int(round(handoff.T_PAPER * 60)), 60, 1, 0.5)
    common.CACHE.mkdir(parents=True, exist_ok=True)
    Image.fromarray(R.image().copy()).save(OUT)
    print(OUT)
