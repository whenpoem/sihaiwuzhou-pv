"""场景元素：平面、文字平面、画面层、粒子，以及一帧的描述 FrameSpec。

这些类只记录参数，不碰显卡；渲染器在画的时候再解析纹理、选择文字分辨率。所以 frame(t) 每次都可以
重新创建它们，代价很小，纹理和文字栅格由渲染器按内容缓存。

平面默认正面朝 +z（镜头默认朝 -z 看，所以正对镜头），图像顶部朝 +y。rot=(yaw, pitch, roll) 以度为单位，
旋转矩阵为 Ry(yaw)·Rx(pitch)·Rz(roll)：yaw 绕 +y 轴（正值把正面转向 +x），pitch 绕 +x 轴（正值把上沿
转向 +z，即朝镜头倾），roll 绕 +z 轴（从正面看逆时针）。平面两面都画，背面看到的是左右反向的图像。
"""
import math

import numpy as np

from . import text as T

GROUPS = ("past", "present", "raw")
BLENDS = ("over", "add", "multiply")


def rot_matrix(yaw=0.0, pitch=0.0, roll=0.0, degrees=True):
    if degrees:
        yaw, pitch, roll = math.radians(yaw), math.radians(pitch), math.radians(roll)
    cy, sy, cp, sp, cr, sr = math.cos(yaw), math.sin(yaw), math.cos(pitch), math.sin(pitch), math.cos(roll), math.sin(roll)
    Ry = np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]])
    Rx = np.array([[1, 0, 0], [0, cp, -sp], [0, sp, cp]])
    Rz = np.array([[cr, -sr, 0], [sr, cr, 0], [0, 0, 1]])
    return Ry @ Rx @ Rz


def _check(group, blend):
    if group not in GROUPS:
        raise ValueError(f"group 只能是 {GROUPS}，收到 {group!r}")
    if blend not in BLENDS:
        raise ValueError(f"blend 只能是 {BLENDS}，收到 {blend!r}")


class _Item:
    group = "past"
    stack = None
    bias = 0.0

    def sort_point(self):
        raise NotImplementedError


class Plane(_Item):
    """带纹理的平面。

    tex：None（纯色，取 color）、numpy 数组、PIL 图像、图片路径或 engine.Tex；
    size：(宽, 高)，世界单位；color：乘在纹理上的颜色，可超过 1；
    blend：over（普通叠放）、add（加亮，用于光）、multiply（正片叠底，用于污渍和阴影）；
    group：past / present / raw，决定走哪套调色；material：材质名（见 register_material）；
    uniforms：材质参数，数组或 Tex 会作为纹理绑定；
    mask：挖洞遮罩。可以是数组或 Tex（1 保留，0 挖掉，按平面的 0–1 坐标铺满），也可以是 skia.Path，
          路径以平面的 0–1 坐标描述（u 向右、v 向下），路径内部就是洞；路径遮罩按投影大小分档栅格化，
          近看边缘也清楚；
    uv：纹理子区域 (u0, v0, u1, v1)，v 向下；配合 Tex(repeat=True) 可平铺；
    stack：同一个 stack 键的元素按加入顺序连续绘制，作为一个整体参与远近排序（例如纸和纸上的字）；
    bias：排序深度的偏移（世界单位，负值表示当作更近）。
    """

    def __init__(self, tex=None, center=(0, 0, 0), size=(1, 1), rot=(0, 0, 0), opacity=1.0, blend="over",
                 group="past", material="flat", uniforms=None, mask=None, color=(1, 1, 1), uv=(0, 0, 1, 1),
                 stack=None, bias=0.0):
        _check(group, blend)
        self.tex, self.center, self.size, self.rot = tex, np.asarray(center, float), tuple(size), tuple(rot)
        self.opacity, self.blend, self.group, self.material = float(opacity), blend, group, material
        self.uniforms = uniforms or {}
        self.mask, self.color, self.uv = mask, tuple(color), tuple(uv)
        self.stack, self.bias = stack, float(bias)

    def R(self):
        # 旋转矩阵在一次绘制中会被多次用到（排序、投影、模型矩阵），缓存起来
        if getattr(self, "_R", None) is None:
            self._R = rot_matrix(*self.rot)
        return self._R

    def model(self):
        """单位方形（-0.5–0.5）到世界坐标的 4×4 矩阵。"""
        m = np.eye(4)
        m[:3, :3] = self.R() @ np.diag([self.size[0], self.size[1], 1.0])
        m[:3, 3] = self.center
        return m

    def corners(self):
        R = self.R()
        w, h = self.size
        return [self.center + R @ np.array([x * w, y * h, 0.0]) for x, y in ((-.5, -.5), (.5, -.5), (.5, .5), (-.5, .5))]

    def normal(self):
        return self.R()[:, 2]

    def sort_point(self):
        return self.center


class TextPlane(Plane):
    """文字平面。height 为字号（1 em）的世界长度；center 为锚点，水平位置按 align（left / center / right），
    竖直位置按 valign（top / middle / baseline / bottom），旋转也绕锚点进行。

    引擎按平面在画面上的投影大小自动选择栅格分辨率（每 em 的像素数取 2 的幂分档并缓存），近看不糊。
    vector=True 且整个平面在镜头前方、投影又足够大时，引擎按当前镜头算出平面到画面的透视变换，
    把字形轮廓逐点投影到画面分辨率下直接填充，用于镜头穿进字里。
    """

    def __init__(self, text, kind="serif", weight=400, height=1.0, color=(1, 1, 1), center=(0, 0, 0), rot=(0, 0, 0),
                 group="past", trad=False, scale_x=1.0, align="center", vector=False, opacity=1.0, blend="over",
                 material="flat", uniforms=None, mask=None, valign="middle", tracking=0.0, line_height=1.3,
                 vertical=False, stack=None, bias=0.0):
        super().__init__(None, center, (1, 1), rot, opacity, blend, group, material, uniforms, mask, color,
                         (0, 0, 1, 1), stack, bias)
        self.text = T.to_trad(text) if trad else text
        self.kind, self.weight, self.height = kind, weight, float(height)
        self.scale_x, self.align, self.valign, self.vector = scale_x, align, valign, vector
        self.tracking, self.line_height, self.vertical = tracking, line_height, vertical
        self._lay = None

    def layout(self):
        if self._lay is None:
            self._lay = T.layout(self.text, self.kind, self.weight, self.scale_x, self.tracking, self.line_height,
                                 self.vertical, self.align)
        return self._lay

    def em_to_local(self, x, y):
        """em 坐标（y 向下）→ 平面局部坐标（以锚点为原点，世界单位，y 向上）。"""
        ax, ay = self.layout().anchor(self.align, self.valign)
        return np.array([(x - ax) * self.height, -(y - ay) * self.height, 0.0])

    def em_to_world(self, x, y):
        """em 坐标 → 世界坐标。用于定位字里的某个部件，例如"吵"字左边的"口"。"""
        return self.center + self.R() @ self.em_to_local(x, y)

    def box_geometry(self, box=None):
        """返回 (平面中心, 尺寸)：box 为 em 范围 (x0, y0, x1, y1)，缺省为栅格覆盖范围。"""
        if box is None:
            if getattr(self, "_geo", None) is None:
                self._geo = self.box_geometry(self.layout().tex_box)
            return self._geo
        x0, y0, x1, y1 = box
        c = self.em_to_world((x0 + x1) / 2, (y0 + y1) / 2)
        return c, ((x1 - x0) * self.height, (y1 - y0) * self.height)

    def outline(self):
        """整段文字的轮廓（skia Path，em 坐标，y 向下）。"""
        return self.layout().path()

    def glyph_paths(self):
        return self.layout().glyph_paths()

    def model_for(self, box):
        c, (w, h) = self.box_geometry(box)
        m = np.eye(4)
        m[:3, :3] = self.R() @ np.diag([w, h, 1.0])
        m[:3, 3] = c
        return m, (w, h)

    def corners(self):
        c, (w, h) = self.box_geometry()
        R = self.R()
        return [c + R @ np.array([x * w, y * h, 0.0]) for x, y in ((-.5, -.5), (.5, -.5), (.5, .5), (-.5, .5))]

    def sort_point(self):
        return self.box_geometry()[0]


class Overlay:
    """跟随镜头的画面层，坐标为成片的像素坐标（左上角为原点，y 向下，预览时自动按比例缩小）。

    tex_or_text 为字符串时按 size（像素字号）、kind、weight、color 排字；也可以给图像。
    anchor 为 "水平-竖直"：水平取 left / center / right，竖直取 top / middle / baseline / bottom；
    图像没有基线，baseline 按 bottom 处理。

    group 决定这一层与调色的关系：present（缺省）和 raw 在调色之后最后叠加，颜色原样输出，
    白字就是纯白、边缘锐利（与样张 C 的做法相同）；past 画进过去层、在调色之前叠加，
    带上与背景相同的胶片颗粒、光晕和暖色，用于过去段落里需要融进画面的字。
    """

    def __init__(self, tex_or_text, xy=(0, 0), anchor="left-baseline", group="present", opacity=1.0, size=60,
                 kind="serif", weight=300, color=(1, 1, 1), scale_x=1.0, trad=False, tracking=0.0, line_height=1.3,
                 align="left", rot=0.0, scale=1.0):
        if group not in GROUPS:
            raise ValueError(f"group 只能是 {GROUPS}")
        self.src = tex_or_text
        self.is_text = isinstance(tex_or_text, str)
        if self.is_text and trad:
            self.src = T.to_trad(tex_or_text)
        self.xy, self.anchor, self.group, self.opacity = tuple(xy), anchor, group, float(opacity)
        self.size, self.kind, self.weight, self.color = float(size), kind, weight, tuple(color)
        self.scale_x, self.tracking, self.line_height, self.align = scale_x, tracking, line_height, align
        self.rot, self.scale = float(rot), float(scale)


class Particles(_Item):
    """实例化绘制的粒子。每个粒子是一个小方片。

    atlas：engine.Atlas（glyph_atlas() 生成的字形图集或 dot_atlas() 的柔边圆点）；
    pos (N,3)：中心位置；size (N,) 或 (N,2)：边长（世界单位）；
    rot：(N,) 时方片始终面向镜头，值为绕视线的转角（弧度）；(N,3) 时按 (yaw, pitch, roll)（弧度）
         在空间中定向，可用于翻板，此时 back (N,4) 给出背面颜色；
    color (N,4)：颜色与不透明度；uv (N,4)：每个粒子在图集里的纹理坐标，缺省取图集第一个条目；
    blend 为 over 时按远近排序后绘制，add 时不排序。
    整个粒子组作为一个整体与平面排序（按位置的平均值），粒子与平面之间不逐个交错。
    """

    def __init__(self, atlas, pos, size, rot=None, color=None, uv=None, blend="over", group="past", back=None,
                 opacity=1.0, sort=None, stack=None, bias=0.0):
        _check(group, blend)
        self.atlas = atlas
        self.pos = np.ascontiguousarray(pos, np.float32).reshape(-1, 3)
        n = len(self.pos)
        size = np.asarray(size, np.float32)
        if size.ndim == 0:
            size = np.full((n, 2), float(size), np.float32)
        elif size.ndim == 1:
            size = np.repeat(size[:, None], 2, 1)
        self.size = np.ascontiguousarray(size, np.float32)
        if rot is None:
            rot = np.zeros(n, np.float32)
        rot = np.asarray(rot, np.float32)
        self.oriented = rot.ndim == 2
        r3 = np.zeros((n, 3), np.float32)
        if self.oriented:
            r3[:] = rot
        else:
            r3[:, 0] = rot
        self.rot = r3
        if color is None:
            color = np.ones((n, 4), np.float32)
        self.color = np.ascontiguousarray(np.broadcast_to(np.asarray(color, np.float32), (n, 4)))
        if uv is None:
            uv = np.broadcast_to(np.array(atlas.rects[atlas.keys[0]], np.float32), (n, 4))
        self.uv = np.ascontiguousarray(np.broadcast_to(np.asarray(uv, np.float32), (n, 4)))
        self.back = None if back is None else np.ascontiguousarray(np.broadcast_to(np.asarray(back, np.float32), (n, 4)))
        self.blend, self.group, self.opacity = blend, group, float(opacity)
        self.sort = (blend == "over") if sort is None else sort
        self.stack, self.bias = stack, float(bias)

    def __len__(self):
        return len(self.pos)

    def sort_point(self):
        if len(self.pos) == 0:
            return np.zeros(3)
        if getattr(self, "_sp", None) is None:
            self._sp = self.pos.mean(axis=0)
        return self._sp


class FrameSpec:
    """一帧的描述：镜头、元素列表和调色参数。

    grade = {"past": {...}, "present": {...}, "final": {...}}，只需写出要改变的参数，其余取默认值
    （见 engine.grade.DEFAULTS）；每帧都可以不同，用于过渡。
    """

    def __init__(self, cam, items, grade=None):
        self.cam = cam
        flat = []

        def walk(x):
            if x is None:
                return
            if isinstance(x, (list, tuple)):
                for y in x:
                    walk(y)
            else:
                flat.append(x)
        walk(items)
        self.items = [x for x in flat if not isinstance(x, Overlay)]
        self.overlays = [x for x in flat if isinstance(x, Overlay)]
        self.grade = grade or {}
