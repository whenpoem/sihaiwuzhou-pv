"""文字：排版、栅格化、字形轮廓、字形图集。

字体逻辑来自 scripts/style/look.py（思源宋体与思源黑体是可变字重字体）。排版在"em 坐标"里进行：
1 em 等于字号，x 向右、y 向下，第一行基线在 y=0。汉字按表意字框对齐：字框上沿在基线上方 0.88 em、
下沿在基线下方 0.12 em（思源字体的设计值），所以"居中"指字框居中，汉字看起来正好在中间。

栅格化时不做字形微调（hinting），不同分辨率下字形的形状一致，引擎在分档之间切换时看不出跳变。
"""
import math
import sys
from functools import lru_cache
from pathlib import Path

import numpy as np
import skia

_STYLE = Path(__file__).resolve().parents[1] / "style"
if str(_STYLE) not in sys.path:
    sys.path.insert(0, str(_STYLE))
import look  # noqa: E402

EM_TOP, EM_BOTTOM = -0.88, 0.12          # 表意字框（em，相对基线，y 向下）
BASE = 256.0                              # 求轮廓与度量时使用的字号
PAD = 0.12                                # 栅格四周的留白（em），给 mip 缩小和墨迹溢出留余地


def make_font(kind="serif", weight=400, size=BASE, scale_x=1.0):
    f = skia.Font(look.typeface(kind, int(round(weight))), size)
    f.setScaleX(scale_x)
    f.setEdging(skia.Font.Edging.kAntiAlias)
    f.setSubpixel(True)
    f.setHinting(skia.FontHinting.kNone)
    f.setLinearMetrics(True)
    return f


def to_trad(text):
    return look.trad(text)


class Layout:
    """一段文字的排版结果（em 坐标）。

    glyphs：[(字, 字形号, x, y)]，(x, y) 为该字基线左端；
    box：排版框 (x0, y0, x1, y1)，按表意字框计算，不含留白；
    tex_box：栅格覆盖的范围，含墨迹溢出和留白。
    """

    def __init__(self, text, kind, weight, scale_x, tracking, line_height, vertical, align):
        self.text, self.kind, self.weight, self.scale_x = text, kind, weight, scale_x
        self.tracking, self.line_height, self.vertical, self.align = tracking, line_height, vertical, align
        self.key = (text, kind, round(float(weight), 2), round(float(scale_x), 4), round(float(tracking), 4),
                    round(float(line_height), 4), bool(vertical), align)
        f = make_font(kind, weight, BASE, scale_x)
        self.font = f
        lines = text.split("\n")
        self.glyphs = []
        if not vertical:
            widths = []
            rows = []
            for li, line in enumerate(lines):
                ids = f.textToGlyphs(line) if line else []
                adv = [w / BASE for w in f.getWidths(ids)] if line else []
                x = 0.0
                row = []
                for ch, gid, a in zip(line, ids, adv):
                    row.append((ch, gid, x))
                    x += a + tracking
                w = x - tracking if row else 0.0
                widths.append(w)
                rows.append(row)
            W = max(widths) if widths else 0.0
            for li, (row, w) in enumerate(zip(rows, widths)):
                off = {"left": 0.0, "right": W - w}.get(align, (W - w) / 2)
                y = li * line_height
                for ch, gid, x in row:
                    self.glyphs.append((ch, gid, x + off, y))
            n = len(lines)
            self.box = (0.0, EM_TOP, W, EM_BOTTOM + (n - 1) * line_height)
        else:
            # 竖排：每列从上到下，列从右往左；字在 1 em 宽的列里水平居中
            cols = []
            for line in lines:
                ids = f.textToGlyphs(line) if line else []
                adv = [w / BASE for w in f.getWidths(ids)] if line else []
                cols.append(list(zip(line, ids, adv)))
            n = len(cols)
            H = max((len(c) * (1 + tracking) - tracking) for c in cols) if cols else 0.0
            for ci, col in enumerate(cols):
                L = len(col) * (1 + tracking) - tracking if col else 0.0
                off = {"left": 0.0, "right": H - L}.get(align, (H - L) / 2)
                cx = (n - 1 - ci) * line_height + 0.5
                for k, (ch, gid, a) in enumerate(col):
                    top = off + k * (1 + tracking)
                    self.glyphs.append((ch, gid, cx - a / 2, top - EM_TOP))
            self.box = (0.0, 0.0, (n - 1) * line_height + 1.0, H)
        # 墨迹范围
        ink = None
        self._paths = []
        for ch, gid, x, y in self.glyphs:
            p = f.getPath(gid)
            if p is None or p.isEmpty():
                self._paths.append(None)
                continue
            p = skia.Path(p)
            p.transform(skia.Matrix.MakeAll(1 / BASE, 0, x, 0, 1 / BASE, y, 0, 0, 1))
            self._paths.append(p)
            b = p.computeTightBounds()
            r = (b.left(), b.top(), b.right(), b.bottom())
            ink = r if ink is None else (min(ink[0], r[0]), min(ink[1], r[1]), max(ink[2], r[2]), max(ink[3], r[3]))
        bx = self.box
        if ink is None:
            ink = bx
        self.ink = ink
        self.tex_box = (min(bx[0], ink[0]) - PAD, min(bx[1], ink[1]) - PAD,
                        max(bx[2], ink[2]) + PAD, max(bx[3], ink[3]) + PAD)
        self._flat = None

    @property
    def tex_size_em(self):
        x0, y0, x1, y1 = self.tex_box
        return x1 - x0, y1 - y0

    def anchor(self, align=None, valign="middle"):
        """锚点（em 坐标）：水平按 align，竖直按 valign（top / middle / baseline / bottom）。"""
        x0, y0, x1, y1 = self.box
        align = align or self.align
        ax = {"left": x0, "right": x1}.get(align, (x0 + x1) / 2)
        if self.vertical:
            ay = {"top": y0, "bottom": y1}.get(valign, (y0 + y1) / 2)
        else:
            ay = {"top": y0, "bottom": y1, "baseline": 0.0}.get(valign, (y0 + y1) / 2)
        return ax, ay

    def path(self):
        """整段文字的轮廓（skia Path，em 坐标，y 向下）。"""
        out = skia.Path()
        for p in self._paths:
            if p is not None:
                out.addPath(p)
        return out

    def glyph_paths(self):
        """逐字轮廓：[(字, skia Path)]，em 坐标。之后的笔画拆分、字形切开从这里取。"""
        return [(g[0], p) for g, p in zip(self.glyphs, self._paths) if p is not None]

    def flat(self, samples=24):
        """把轮廓折线化：返回 [ndarray(k, 2)] 的闭合多边形列表（em 坐标），曲线按 samples 段细分。
        矢量模式在画面分辨率下逐点做透视投影，再交给 skia 填充，放得再大边缘也是准确的。"""
        if self._flat is None:
            polys = []
            for p in self._paths:
                if p is not None:
                    polys.extend(flatten(p, samples))
            self._flat = polys
        return self._flat

    def raster(self, em_px):
        """按每 em em_px 个像素栅格化。返回 (uint8 覆盖率数组, 该数组实际覆盖的 em 范围)。
        数组尺寸向上取整，所以覆盖范围比 tex_box 略大；平面按实际覆盖范围摆放，字的位置因此精确。"""
        x0, y0, x1, y1 = self.tex_box
        w = max(1, int(math.ceil((x1 - x0) * em_px)))
        h = max(1, int(math.ceil((y1 - y0) * em_px)))
        arr = np.zeros((h, w), np.uint8)
        s = skia.Surface.MakeRasterDirect(skia.ImageInfo.MakeA8(w, h), arr)
        c = s.getCanvas()
        f = make_font(self.kind, self.weight, em_px, self.scale_x)
        paint = skia.Paint(AntiAlias=True, Color=skia.ColorWHITE)
        for ch, gid, x, y in self.glyphs:
            blob = skia.TextBlob.MakeFromText(ch, f)
            if blob is not None:
                c.drawTextBlob(blob, (x - x0) * em_px, (y - y0) * em_px, paint)
        del c, s
        return arr, (x0, y0, x0 + w / em_px, y0 + h / em_px)


_layout_cache = {}


def layout(text, kind="serif", weight=400, scale_x=1.0, tracking=0.0, line_height=1.3, vertical=False, align="center"):
    key = (text, kind, round(float(weight), 2), round(float(scale_x), 4), round(float(tracking), 4),
           round(float(line_height), 4), bool(vertical), align)
    lay = _layout_cache.get(key)
    if lay is None:
        if len(_layout_cache) > 4000:
            _layout_cache.clear()
        lay = Layout(text, kind, weight, scale_x, tracking, line_height, vertical, align)
        _layout_cache[key] = lay
    return lay


# ---------------------------------------------------------------------------
# 字形轮廓工具
# ---------------------------------------------------------------------------

def glyph_path(ch, kind="serif", weight=400, scale_x=1.0):
    """单字轮廓（skia Path），em 坐标：基线在 y=0，y 向下，字的左端在 x=0。"""
    f = make_font(kind, weight, BASE, scale_x)
    gid = f.textToGlyphs(ch)[0]
    p = skia.Path(f.getPath(gid))
    p.transform(skia.Matrix.Scale(1 / BASE, 1 / BASE))
    return p


def contours(path):
    """把轮廓按闭合子路径拆开，返回 [skia Path]。字的部件、笔画外形、内部的空白（字怀）各自是一条子路径。"""
    out, cur = [], None
    it = skia.Path.Iter(path, False)
    while True:
        verb, pts = it.next()
        if verb == skia.Path.kDone_Verb:
            break
        if verb == skia.Path.kMove_Verb:
            if cur is not None and not cur.isEmpty():
                out.append(cur)
            cur = skia.Path()
            cur.moveTo(pts[0])
        elif verb == skia.Path.kLine_Verb:
            cur.lineTo(pts[1])
        elif verb == skia.Path.kQuad_Verb:
            cur.quadTo(pts[1], pts[2])
        elif verb == skia.Path.kConic_Verb:
            cur.conicTo(pts[1], pts[2], it.conicWeight())
        elif verb == skia.Path.kCubic_Verb:
            cur.cubicTo(pts[1], pts[2], pts[3])
        elif verb == skia.Path.kClose_Verb:
            cur.close()
    if cur is not None and not cur.isEmpty():
        out.append(cur)
    return out


def flatten(path, samples=24):
    """把 skia Path 折线化为闭合多边形列表 [ndarray(k, 2)]。"""
    polys, cur, last = [], [], None
    it = skia.Path.Iter(path, False)
    s = np.linspace(0, 1, samples + 1)[1:, None]
    while True:
        verb, pts = it.next()
        if verb == skia.Path.kDone_Verb:
            break
        P = np.array([[p.x(), p.y()] for p in pts], np.float64) if pts else None
        if verb == skia.Path.kMove_Verb:
            if len(cur) > 2:
                polys.append(np.array(cur))
            cur = [P[0]]
        elif verb == skia.Path.kLine_Verb:
            cur.append(P[1])
        elif verb == skia.Path.kQuad_Verb:
            q = (1 - s) ** 2 * P[0] + 2 * (1 - s) * s * P[1] + s ** 2 * P[2]
            cur.extend(q)
        elif verb == skia.Path.kConic_Verb:
            w = it.conicWeight()
            num = (1 - s) ** 2 * P[0] + 2 * w * (1 - s) * s * P[1] + s ** 2 * P[2]
            den = (1 - s) ** 2 + 2 * w * (1 - s) * s + s ** 2
            cur.extend(num / den)
        elif verb == skia.Path.kCubic_Verb:
            q = (1 - s) ** 3 * P[0] + 3 * (1 - s) ** 2 * s * P[1] + 3 * (1 - s) * s ** 2 * P[2] + s ** 3 * P[3]
            cur.extend(q)
        elif verb == skia.Path.kClose_Verb:
            if len(cur) > 2:
                polys.append(np.array(cur))
            cur = []
    if len(cur) > 2:
        polys.append(np.array(cur))
    return polys


def bounds(path):
    b = path.computeTightBounds()
    return b.left(), b.top(), b.right(), b.bottom()


# ---------------------------------------------------------------------------
# 字形图集（粒子用）
# ---------------------------------------------------------------------------

class Atlas:
    """一张纹理加上每个条目的纹理坐标 (u0, v0, u1, v1)，v 向下。mode 1 为覆盖率，0 为预乘 RGBA。"""

    def __init__(self, data, rects, keys):
        from .gpu import Tex
        self.tex = Tex(data)
        self.rects = rects            # key -> (u0, v0, u1, v1)
        self.keys = list(keys)

    def uv(self, keys):
        """按条目序列返回 (N, 4) 的纹理坐标数组；keys 可以是字符串（逐字）或列表。"""
        return np.array([self.rects[k] for k in keys], np.float32)

    def index_uv(self, idx):
        """按条目序号数组返回 (N, 4) 纹理坐标。"""
        table = np.array([self.rects[k] for k in self.keys], np.float32)
        return table[np.asarray(idx) % len(self.keys)]


def glyph_atlas(chars, kind="serif", weight=400, cell=128, scale_x=1.0, trad=False):
    """把一组字画进一张图集：每个字占 cell×cell 的方格，按表意字框居中。返回 Atlas。"""
    if trad:
        chars = to_trad(chars)
    keys = list(dict.fromkeys(ch for ch in chars if not ch.isspace()))
    n = len(keys)
    cols = int(math.ceil(math.sqrt(n)))
    rows = int(math.ceil(n / cols))
    W, H = cols * cell, rows * cell
    arr = np.zeros((H, W), np.uint8)
    s = skia.Surface.MakeRasterDirect(skia.ImageInfo.MakeA8(W, H), arr)
    c = s.getCanvas()
    em = cell / (1 + 2 * 0.06)
    f = make_font(kind, weight, em, scale_x)
    paint = skia.Paint(AntiAlias=True, Color=skia.ColorWHITE)
    rects = {}
    for i, ch in enumerate(keys):
        cx, cy = (i % cols) * cell, (i // cols) * cell
        adv = f.measureText(ch)
        x = cx + (cell - adv) / 2
        y = cy + cell / 2 - (EM_TOP + EM_BOTTOM) / 2 * em
        c.drawString(ch, x, y, f, paint)
        rects[ch] = (cx / W, cy / H, (cx + cell) / W, (cy + cell) / H)
    del c, s
    return Atlas(arr, rects, keys)


def dot_atlas(res=64, hardness=0.0):
    """柔边圆点：hardness=0 为高斯形，越接近 1 边缘越硬。"""
    y, x = np.mgrid[0:res, 0:res].astype(np.float32)
    r = np.hypot(x - (res - 1) / 2, y - (res - 1) / 2) / (res / 2)
    soft = np.exp(-(r ** 2) * 4.0)
    hard = np.clip((1 - r) * res * 0.25, 0, 1)
    a = soft * (1 - hardness) + hard * hardness
    a[r >= 1] = 0
    return Atlas(a.astype(np.float32), {"dot": (0, 0, 1, 1)}, ["dot"])


