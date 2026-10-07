"""把一个字拆成笔画：思源宋体的笔画是相互重叠的独立轮廓，每条闭合子路径基本就是一笔。
每一笔画进自己的覆盖率贴图（裁到这一笔的外接框），返回贴图和它在字形 em 坐标里的位置，供"手"字张开、
"風"字的笔画从指缝间穿过时逐笔移动。"""
import numpy as np

import common  # noqa: F401
import look
from engine import Tex, bounds, contours, glyph_path
from flatcam import cached

EM_MID = -0.38          # 表意字框的竖直中点（em，y 向下，基线为 0）


def strokes(ch, kind="serif", weight=800, res=1100, pad=0.02):
    """返回 [(Tex, (x0, y0, x1, y1) em 外接框)]，顺序与字形轮廓的顺序相同。"""
    def make():
        import skia
        path = glyph_path(ch, kind, weight)
        out = []
        for c in contours(path):
            x0, y0, x1, y1 = bounds(c)
            x0, y0, x1, y1 = x0 - pad, y0 - pad, x1 + pad, y1 + pad
            w, h = int(np.ceil((x1 - x0) * res)), int(np.ceil((y1 - y0) * res))
            arr = np.zeros((h, w), np.uint8)
            srf = skia.Surface.MakeRasterDirect(skia.ImageInfo.MakeA8(w, h), arr)
            cv = srf.getCanvas()
            cv.scale(res, res)
            cv.translate(-x0, -y0)
            cv.drawPath(c, skia.Paint(AntiAlias=True))
            del cv, srf
            out.append((Tex(arr.copy()), (x0, y0, x1, y1)))
        return out
    return cached(("strokes", ch, kind, weight), make)


def em_to_world(ex, ey, center, h):
    """字形 em 坐标 → 世界坐标：center 为字框中心，h 为字高（1 em 的长度）。"""
    return np.array([center[0] + (ex - 0.5) * h, center[1] - (ey - EM_MID) * h])
