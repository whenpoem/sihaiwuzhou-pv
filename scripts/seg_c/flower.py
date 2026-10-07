"""副歌一 L11–L12 的向日葵：由"她"字笔画组成的花瓣、黄金角排列的小"她"字花心、"扌"和花茎。

这一组素材服务于两个镜头。L11 时茎顶只有一个完整的"她"字，由一个"扌"握着花茎；L12 唱到"让她变朵"时，
"她"的笔画复制、旋转着展开成一圈花瓣，"她"字本身留在花心，随后花离开手飞向尖塔。花瓣因此必须真的是
"她"字的笔画，每一笔都要有两套几何：笔画在字里的原位，以及笔画作为花瓣的终位。下面给出这两套几何、
全部贴图，以及一个在两者之间插值的现成动画 bloom_items(u)。

一、坐标系、单位与贴图约定

花的局部坐标系以花心为原点，x 向右，y 向上，z 朝向观众（与引擎平面的正面一致），单位为世界单位。整朵花
直径约 0.9（外圈花瓣尖端离花心 0.40–0.49，内圈 0.34–0.40），花心圆盘半径 R_DISC = 0.20。花心的"她"字
字号 E_CENTER = 0.21（1 em 的世界长度），表意字框中心在原点，与
TextPlane("她", kind="serif", weight=900, height=E_CENTER, center=原点) 的位置完全重合。字体设计用的
"em 坐标"以基线左端为原点，x 向右、y 向下，换算到花的坐标为 E·(x − 0.5, −(y + 0.38))，见 em_to_flower()。

所有贴图都是 0–1 浮点 RGBA，直通 alpha，第 0 行是图像顶部。颜色是不受光照的固有色，协调者用平面的 color
乘上光照即可。过去层的调色本身偏暖，光再偏暖，美术字黄就会变成橙色，所以照在花上的光宜接近中性，
例如冷蓝环境光 (0.30, 0.34, 0.44) 加上一点暖光和中性补光，合计约 (0.8, 0.75, 0.7)；assets_preview.py 的
flower_light() 是一个例子。贴图第一次生成后存成 PNG 放在 data/cache/seg_c/（文件名带 VERSION），之后直接
读取；同一进程里每张贴图只返回同一个数组，引擎按数组身份缓存显存。

二、笔画拆分

思源宋体 900 的"她"字恰好由八个闭合轮廓组成，每个轮廓就是一个完整的笔画，不需要再合并或拆分。strokes()
按外框把轮廓对应到固定的序号：0 撇、1 撇点之撇、2 撇点之点（这三笔属于"女"）、3 横（女）、4 横折钩
（不含起笔的细横）、5 横（"也"的起笔细横）、6 竖、7 竖弯钩。其中 PETAL_STROKES = (0, 1, 2, 4, 6) 这五笔
用作花瓣：两条横只有 0.03 em 宽，放大成花瓣只是一根细线；竖弯钩是 L 形，按半径方向摆放时横向伸出很远，
破坏花的圆形轮廓，所以这三笔只留在花心的大字里。

每一笔作为花瓣时有一个"内端"（靠近花心、被圆盘压住的一端）和一个"外端"。撇和横折钩取起笔的粗头朝内，
尖尾和钩朝外；撇点之点取圆头朝内、尖头朝外；竖和撇点之撇取收笔一端朝内，让宋体起笔处带耳朵的笔头成为
花瓣尖端，这是最能让人认出"宋体笔画"的部位。Stroke 记录这些量：inner、outer 是两端在 em 坐标里的位置，
phi 是从内端指向外端的方向角（弧度，花的坐标系，从 +x 逆时针量），length 是两端距离（em），width 是
最宽处（em）。

笔画贴图放在"笔画坐标"里：内端锚点在原点，外端朝上。stroke_tex(k, style) 给出第 k 笔的贴图，覆盖
Stroke.rbox（笔画外框加 0.03 em 留白），分辨率 PX_EM = 1536 像素/em；Stroke.size_em 是它的 em 尺寸，
Stroke.anchor_uv 是内端锚点在贴图里的位置 (u, v)（v 向下）。花瓣在镜头 2 单位远、竖直视角 40 度、引擎
超采样 2 倍时，每个世界单位约占 1480 个渲染像素，而花瓣的贴图密度为每世界单位 2200–3800 像素，留有
1.5 倍以上的余量。style="petal" 是花瓣的样子：美术字黄为主，根部是偏红的深赭、尖端略浅；两侧微暗，像
花瓣微微卷起；沿笔画有几条与边缘平行、靠根部明显的淡叶脉；边缘一道粗细略有起伏的墨褐描线；再加纸张
颗粒和零星掉墨。style="glyph" 是花心大字的样子（暖白、只带颗粒），与 petal 逐像素对齐，动画开始时
笔画副本先用 glyph 的样子与花心的字重合，再渐变成 petal。

place(k, anchor, axis, scale, fx, tilt, z) 是两套几何共用的摆放函数：把第 k 笔的内端锚点放在花的坐标
anchor 处，主轴方向角为 axis（弧度），沿主轴每 em 为 scale 个世界单位，横向再乘 fx，外端朝观众翘起 tilt
度，锚点的 z 为 z；返回引擎平面的 center、size、roll（度）和 rot=(yaw, pitch, roll)（度）。笔画在字里的
原位由 stroke_home(k, E) 给出，它就是 place(k, em_to_flower(inner), phi, E)，roll 等于 phi − 90°。

三、花瓣终位

petal_layout() 返回 34 片花瓣，外圈 21 片、内圈 13 片，按绘制顺序排列（先外圈后内圈，圈内顺序打乱，
叠压关系自然），每片是一个 dict：stroke 用哪一笔；ring 为 0（外圈）或 1（内圈）；theta 花瓣的方向角；
axis 主轴方向角（theta 加 ±4° 的偏差）；anchor、r_anchor 内端锚点的位置与到花心的距离；scale 沿主轴的
世界单位/em；fx 横向倍率；tilt 翘起角（度）；z 锚点的 z；center、size、roll、rot 是 place() 算出的引擎
平面参数；tint 乘在这片花瓣上的颜色（明暗 ±8%、冷暖略有差别，内圈整体略深略暖）；order 绘制顺序。

两圈的参数在 RINGS 里。外圈锚点半径 0.125、花瓣长 0.335、最宽处 0.076、翘起 7°；内圈锚点半径 0.11、
花瓣长 0.255、最宽处 0.070、翘起 15°。各笔的长度相差将近一倍（点 0.45 em，撇 0.82 em），所以 scale 按
"花瓣长度 / 笔画长度"取，同一圈的花瓣长度一致，花的外轮廓才是圆的；宽度则用 fx 拉到接近同一值，范围
限制在 0.72–1.55，竖和撇点之撇是等宽的直笔，加宽后像木条，fx 不超过 1。同一圈里相邻两片不用同一笔，
各笔出现的次数按权重分配，撇和点最多。

四、花心

disc_tex() 是深褐色圆盘（不含中央大字），覆盖 [−0.25, 0.25]² 的正方形，2048 像素见方，平面中心在原点、
尺寸 0.5×0.5。盘面是 170 个小"她"字，第 i 个在半径 0.95·R_DISC·√((i+0.5)/170)、角度 i·137.508° 处，
字头朝外，构成向日葵籽的螺线；底色中心最深，向外渐亮，最外一圈偏黄，像开放的小花与花粉。每个小字向
右下投一点淡影，显出厚度；中央大字周围压暗一圈，让暖白的字从小字里跳出来；圆盘外缘还有一圈很淡的
投影，压暗花瓣根部。seed_layout() 给出小字的位置、字号与角度。

center_tex() 是花心完整的"她"字（暖白，宋体 900），覆盖 em 矩形 CENTER_BOX = (−0.06, −0.94, 1.06, 0.18)，
center_home(E) 给出平面中心与尺寸。L11 时它就是茎顶那个完整的"她"字，可以单独使用；它是歌词里的字，
color 设到 1.1–1.2 时像样张 B 的歌词一样微微发亮。

五、扌和茎

茎取"她"字竖画（第 6 笔）的轮廓，起笔与收笔保留原来的形状，中段拉长到 STEM_LEN = 1.25，宽 0.04。
茎的顶端在 (0, −0.04)，藏在圆盘背后；握持点在 (−0.075, −0.815)，底端在 (−0.075, −1.29)。茎在手的上方
向右弯向花心，穿过手时是竖直的。stem_tex() 是茎的贴图（偏绿的橄榄褐，带顺茎的纤维、圆柱形的明暗和墨褐
描线），stem_geometry() 给出平面的 center、size（花的坐标）、建议的 z（−0.012，在花瓣之后）以及 top、
bottom、grip 三个点。茎属于花，花飞走时随花一起离开。

"扌"用思源黑体 900，字号 HAND_EM = 0.60，墨褐色，带颗粒、少量掉墨和略毛的边。黑体的"扌"横和提都伸到
竖钩右边，握持点取在横与提的右段之间、竖钩右侧，em 坐标 (0.445, −0.49)：茎从这里穿过，画在"扌"后面，
横和提压在茎上，看起来是两道手指握住了茎。hand_tex() 是贴图，hand_geometry(grip) 给出让握持点落在 grip
（缺省为茎的握持点）时"扌"平面的 center 与 size（缺省时中心 (−0.162, −0.869)，尺寸 0.384×0.672）。
grip_shadow_tex() 与"扌"同一矩形，是横和提投在茎上的淡影，只在茎经过处不透明，放在茎和"扌"之间，
花离手时淡出。

六、整朵合成与展开动画

flower_tex() 是花瓣、圆盘与花心大字在二维里合成的一张贴图（远景用），覆盖 [−0.5, 0.5]²，2048 像素见方；
flower_tex(with_stem=True) 连同茎一起，覆盖 flower_full_box() = (−0.5, −1.31, 0.5, 0.5)，像素密度相同。
compose(u, ...) 可以合成任意展开进度的二维图。

bloom_state(u) 给出展开进度 u（0–1）时每个元素的状态，bloom_items(u, origin, rot, scale, light) 把它变成
一组引擎 Plane（含茎），按绘制顺序排列，共用 stack="flower"；hand_items(...) 给出"扌"和握持淡影。
u = 0 时只有花心的"她"字，u = 1 时是完整的向日葵。中间每片花瓣是对应笔画的副本：内端锚点从它在字里的
位置出发，沿逆时针的螺线移到花瓣位置（swirl=−1 为顺时针，0 为走最短的角度），主轴同时转正到半径方向，
尺寸从字号放大到花瓣大小，横向倍率从 1 变到 fx，颜色在进度 0.04–0.45 之间从暖白渐变为黄；各片按方向角
先后错开 0.30 的进度，绕一圈依次展开，内圈再晚 0.05。圆盘在 u ≈ 0.12–0.72 之间从花心长出。"让她变朵"
65.16–66.04 秒只有 0.88 秒，u 可以用 T.tween(t, 65.16, 66.04, 0, 1, "out_cubic")。origin、rot（度）是整朵花
在世界中的位置与朝向，light(p) 返回世界坐标 p 处的光照颜色，乘在各平面的 color 上。花飞走时，"扌"的
origin 保持不动，花的 origin 随路线移动，握持淡影的 shadow 降到 0。

运行 python flower.py 会生成全部贴图缓存，并输出笔画拆分图 renders/seg_c/assets/flower_01_笔画拆分.png；
引擎渲染的预览由 assets_preview.py 生成。

范围与局限：花瓣是平面，翘起只有 7°–15°，镜头从侧面超过约 60° 看时花会显得很薄；花心大字与小字都画在
同一块圆盘上，镜头贴近到 0.5 单位以内时小字会因贴图密度不足而略软。
"""
import math
import sys
from functools import lru_cache
from pathlib import Path

import cv2
import numpy as np
import skia
from PIL import Image
from scipy.ndimage import distance_transform_edt, gaussian_filter, maximum_filter
from scipy.optimize import linear_sum_assignment

ROOT = Path(__file__).resolve().parents[2]
for _p in (ROOT / "scripts", ROOT / "scripts" / "style"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import look  # noqa: E402
from engine import bounds, contours, flatten, glyph_path  # noqa: E402
from engine.text import make_font  # noqa: E402

CACHE = ROOT / "data" / "cache" / "seg_c"
ASSETS = ROOT / "renders" / "seg_c" / "assets"
VERSION = 6

KIND, WEIGHT = "serif", 900          # "她"字与花瓣笔画的字体
PX_EM = 1536                         # 笔画贴图分辨率（像素/em）
E_CENTER = 0.21                      # 花心"她"字的字号（世界单位/em）
R_DISC = 0.20                        # 花心圆盘半径
DISC_TEX_R = 0.25                    # 圆盘贴图覆盖的半边长（含外缘投影）
FLOWER_TEX_R = 0.50                  # 整朵合成贴图覆盖的半边长
EM_MID = -0.38                       # 表意字框中心的 em 纵坐标（相对基线，y 向下）

Y = look.C["yellow"]
INK = look.C["ink"]
WARM = look.C["warm"]
RED = look.C["red"]

NAMES = ["撇", "撇点之撇", "撇点之点", "横（女）", "横折钩", "横（也）", "竖", "竖弯钩"]
PETAL_STROKES = (0, 1, 2, 4, 6)
# 思源宋体 900 里八个轮廓的外框（em），用于把轮廓对应到上面的笔画序号
_REF_BOX = {
    0: (0.025, -0.675, 0.429, 0.088), 1: (0.038, -0.855, 0.303, -0.258), 2: (0.038, -0.310, 0.405, 0.002),
    3: (0.026, -0.613, 0.332, -0.585), 4: (0.712, -0.677, 0.960, -0.171), 5: (0.371, -0.653, 0.865, -0.442),
    6: (0.628, -0.853, 0.776, -0.104), 7: (0.442, -0.707, 0.981, 0.054),
}
# 作为花瓣时哪一端朝内："head" 为起笔一端（字里靠上的一端），"tail" 为收笔一端
_INNER = {1: "tail", 2: "tail", 6: "tail"}


def em_to_flower(x, y, E=E_CENTER):
    """em 坐标（y 向下、基线 y=0）换算到花的坐标（y 向上，原点为花心"她"字的字框中心）。"""
    return np.array([E * (x - 0.5), -E * (y - EM_MID)])


def _smooth(e0, e1, x):
    t = np.clip((np.asarray(x, np.float32) - e0) / (e1 - e0), 0, 1)
    return t * t * (3 - 2 * t)


def _mix(a, b, t):
    return np.asarray(a) * (1 - t) + np.asarray(b) * t


def _noise(h, w, scale, octaves=4, seed=0, aniso=(1.0, 1.0)):
    """平滑噪声，0–1。scale 为最粗一层的特征尺寸（像素）；aniso=(sy, sx) 把特征尺寸按方向拉伸。"""
    rng = np.random.default_rng(seed)
    out = np.zeros((h, w), np.float32)
    amp, tot, s = 1.0, 0.0, float(scale)
    for _ in range(octaves):
        gh = max(2, int(h / max(s * aniso[0], 1)) + 2)
        gw = max(2, int(w / max(s * aniso[1], 1)) + 2)
        g = rng.random((gh, gw)).astype(np.float32)
        out += cv2.resize(g, (w, h), interpolation=cv2.INTER_CUBIC) * amp
        tot += amp
        amp *= 0.5
        s /= 2
    out /= tot
    lo, hi = np.percentile(out, 1), np.percentile(out, 99)
    return np.clip((out - lo) / (hi - lo + 1e-6), 0, 1)


def _raster(path, box, px, ss=1):
    """把 skia 路径在 em 矩形 box（y 向下）上栅格化为覆盖率（0–1），第 0 行是 box 的上沿。"""
    x0, y0, x1, y1 = box
    W, H = int(round((x1 - x0) * px)), int(round((y1 - y0) * px))
    arr = np.zeros((H * ss, W * ss), np.uint8)
    s = skia.Surface.MakeRasterDirect(skia.ImageInfo.MakeA8(W * ss, H * ss), arr)
    c = s.getCanvas()
    c.scale(px * ss, px * ss)
    c.translate(-x0, -y0)
    c.drawPath(path, skia.Paint(AntiAlias=True))
    del c, s
    a = arr.astype(np.float32) / 255
    if ss > 1:
        a = cv2.resize(a, (W, H), interpolation=cv2.INTER_AREA)
    return a


def _rot2(a):
    c, s = math.cos(a), math.sin(a)
    return np.array([[c, -s], [s, c]])


def _rot_matrix(yaw, pitch, roll):
    from engine import rot_matrix
    return rot_matrix(yaw, pitch, roll)


def _rx(deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    return np.array([[1, 0, 0], [0, c, -s], [0, s, c]])


def _rz(rad):
    c, s = math.cos(rad), math.sin(rad)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]])


def euler_from_matrix(M):
    """把旋转矩阵分解为引擎的 (yaw, pitch, roll)（度），M = Ry(yaw)·Rx(pitch)·Rz(roll)。"""
    p = math.asin(float(np.clip(-M[1, 2], -1, 1)))
    if abs(math.cos(p)) > 1e-6:
        r = math.atan2(M[1, 0], M[1, 1])
        y = math.atan2(M[0, 2], M[2, 2])
    else:
        r = 0.0
        y = math.atan2(-M[2, 0], M[0, 0])
    return (math.degrees(y), math.degrees(p), math.degrees(r))


# ---------------------------------------------------------------------------
# 笔画拆分
# ---------------------------------------------------------------------------

class Stroke:
    """"她"字的一笔。几何量见模块说明；rpath / rbox 是"笔画坐标"里的轮廓和贴图矩形：
    以内端锚点为原点、外端朝上（y 向下的 em 单位，外端在 (0, −length)）。"""

    def __init__(self, idx, path):
        self.idx, self.name, self.path = idx, NAMES[idx], path
        self.bbox = bounds(path)
        self.petal = idx in PETAL_STROKES
        self._axis()
        self._canonical()

    def _axis(self):
        """主轴与两端：在 256 像素/em 的栅格上做主成分分析，取主轴两端各 8% 像素的重心，再沿主轴推到轮廓边缘。"""
        px = 256
        x0, y0, x1, y1 = self.bbox
        box = (x0 - 0.02, y0 - 0.02, x1 + 0.02, y1 + 0.02)
        A = _raster(self.path, box, px) > 0.5
        yy, xx = np.nonzero(A)
        pts = np.c_[xx, yy].astype(float) / px + [box[0], box[1]]
        m = pts.mean(0)
        _, _, vt = np.linalg.svd(pts - m, full_matrices=False)
        d = vt[0] if vt[0][1] >= 0 else -vt[0]          # 指向字里的下方（em 的 +y）
        proj = (pts - m) @ d
        lo, hi = np.percentile(proj, 8), np.percentile(proj, 92)
        head = pts[proj <= lo].mean(0)
        tail = pts[proj >= hi].mean(0)
        head = head + d * (proj.min() - (head - m) @ d)
        tail = tail + d * (proj.max() - (tail - m) @ d)
        if _INNER.get(self.idx, "head") == "head":
            self.inner, self.outer = head, tail
        else:
            self.inner, self.outer = tail, head
        v = self.outer - self.inner
        self.length = float(np.hypot(*v))
        self.phi = float(math.atan2(-v[1], v[0]))        # 花的坐标系（y 向上）里从内端指向外端的方向角
        self.width = float(2 * distance_transform_edt(A).max() / px)

    def _canonical(self):
        """把轮廓转到笔画坐标：内端在原点，外端朝上。"""
        alpha = math.pi / 2 - self.phi                   # 花的坐标系里逆时针转 alpha，主轴朝上
        m = skia.Matrix()
        m.setRotate(-math.degrees(alpha))                # y 向下的画布里，逆时针 alpha 即 rotate(−alpha)
        m.preTranslate(-float(self.inner[0]), -float(self.inner[1]))
        self.alpha = alpha
        self.rmatrix = m
        self.rpath = skia.Path(self.path)
        self.rpath.transform(m)
        x0, y0, x1, y1 = bounds(self.rpath)
        pad = 0.03
        self.rbox = (x0 - pad, y0 - pad, x1 + pad, y1 + pad)

    @property
    def size_em(self):
        x0, y0, x1, y1 = self.rbox
        return (x1 - x0, y1 - y0)

    @property
    def anchor_uv(self):
        """内端锚点在贴图里的位置 (u, v)，u 向右、v 向下，0–1。"""
        x0, y0, x1, y1 = self.rbox
        return (-x0 / (x1 - x0), -y0 / (y1 - y0))

    def offset(self):
        """笔画坐标里从锚点到贴图中心的向量（em，y 向上）。"""
        x0, y0, x1, y1 = self.rbox
        return np.array([(x0 + x1) / 2, -(y0 + y1) / 2])


@lru_cache(maxsize=4)
def strokes(kind=KIND, weight=WEIGHT):
    """"她"字的八个笔画，序号见模块说明。"""
    cs = contours(glyph_path("她", kind, weight))
    if len(cs) != 8:
        raise RuntimeError(f"{kind} {weight} 的'她'字有 {len(cs)} 个轮廓，笔画拆分按 8 个轮廓设计")
    boxes = np.array([bounds(c) for c in cs])
    ref = np.array([_REF_BOX[i] for i in range(8)])
    cost = ((boxes[:, None, :] - ref[None]) ** 2).sum(-1)
    rows, cols = linear_sum_assignment(cost)
    order = [None] * 8
    for r, c in zip(rows, cols):
        order[c] = cs[r]
    return tuple(Stroke(i, order[i]) for i in range(8))


def glyph_advance(kind=KIND, weight=WEIGHT):
    return make_font(kind, weight, 256.0).measureText("她") / 256.0


def place(k, anchor, axis, scale, fx=1.0, tilt=0.0, z=0.0):
    """把第 k 笔的贴图平面放到花的坐标系里：内端锚点在 anchor (x, y)、主轴方向角 axis（弧度）、
    沿主轴 scale（世界单位/em）、横向再乘 fx、外端朝观众翘起 tilt 度、锚点的 z。
    返回 dict(center=(x, y, z), size=(w, h), roll（度）, rot=(yaw, pitch, roll)（度）, M=3×3 旋转)。"""
    s = strokes()[k]
    roll = axis - math.pi / 2
    w, h = s.size_em
    off = s.offset() * np.array([scale * fx, scale])
    M = _rz(roll) @ _rx(tilt)
    c = np.array([anchor[0], anchor[1], z]) + M @ np.array([off[0], off[1], 0.0])
    return {"center": c, "size": (w * scale * fx, h * scale), "roll": math.degrees(roll),
            "rot": euler_from_matrix(M) if tilt else (0.0, 0.0, math.degrees(roll)), "M": M}


def stroke_home(k, E=E_CENTER):
    """第 k 笔在字里的原位（花心"她"字字号为 E 时）：平面 center、size、roll（度），以及内端锚点 anchor 与主轴角 axis。"""
    s = strokes()[k]
    a = em_to_flower(*s.inner, E)
    d = place(k, a, s.phi, E)
    d.update(anchor=a, axis=s.phi, scale=E)
    return d


CENTER_BOX = (-0.06, -0.94, 1.06, 0.18)          # 花心大字贴图覆盖的 em 矩形


def center_home(E=E_CENTER):
    """花心大字的平面中心与尺寸。"""
    x0, y0, x1, y1 = CENTER_BOX
    return {"center": em_to_flower((x0 + x1) / 2, (y0 + y1) / 2, E), "size": ((x1 - x0) * E, (y1 - y0) * E)}


# ---------------------------------------------------------------------------
# 贴图缓存
# ---------------------------------------------------------------------------

_mem = {}


def _memo(name, fn):
    """贴图第一次生成后存成 PNG（8 位 RGBA，直通 alpha），之后直接读取；进程内再缓存一份，
    保证同一张贴图每次返回同一个数组（引擎按数组身份缓存显存）。"""
    if name in _mem:
        return _mem[name]
    CACHE.mkdir(parents=True, exist_ok=True)
    f = CACHE / f"flower_v{VERSION}_{name}.png"
    if not f.exists():
        img = np.clip(fn(), 0, 1).astype(np.float32)
        Image.fromarray((img * 255 + 0.5).astype(np.uint8), "RGBA").save(f)
    _mem[name] = np.asarray(Image.open(f), np.float32) / 255
    return _mem[name]


# ---------------------------------------------------------------------------
# 笔画贴图
# ---------------------------------------------------------------------------

def _grain(h, w, seed, amount=1.0):
    """纸张颗粒：细颗粒加一层略粗的斑驳，乘在颜色上，均值约为 1。"""
    fine = _noise(h, w, 6, 3, seed)
    mid = _noise(h, w, 40, 3, seed + 1)
    return 1 + amount * (0.07 * (fine - 0.5) + 0.06 * (mid - 0.5))


PETAL_ROOT = _mix(Y, RED, 0.38) * 0.82          # 根部：偏红的深赭
PETAL_TIP = _mix(Y, WARM, 0.20) * 1.02           # 尖端：略浅的黄


def _petal_rgba(A, u, px, seed):
    """把覆盖率 A 着色成花瓣。u 为沿花瓣从内端（0）到外端（1）的坐标，px 为每 em 像素数。"""
    h, w = A.shape
    inside = A > 0.5
    dt = distance_transform_edt(inside).astype(np.float32)
    ridge = maximum_filter(dt, size=int(0.16 * px) | 1)
    q = np.clip(dt / np.maximum(ridge, 1), 0, 1)          # 0 在边缘，1 在笔画中线
    t1 = _smooth(0.0, 0.6, u)[..., None]
    t2 = _smooth(0.55, 1.0, u)[..., None]
    col = _mix(_mix(PETAL_ROOT, Y, t1), PETAL_TIP, t2)
    col = col * (0.82 + 0.18 * np.sqrt(q))[..., None]      # 边缘略暗，像花瓣两侧微微卷起
    # 叶脉：与边缘平行的细线，靠根部明显、到尖端淡去，再被噪声打断
    vn = _noise(h, w, 0.08 * px, 3, seed + 5)
    veins = sum(np.exp(-((q - c) / 0.045) ** 2) for c in (0.40, 0.72))
    veins = veins * (1 - _smooth(0.35, 1.0, u)) * (0.4 + 0.6 * vn)
    col = col * (1 - 0.11 * veins)[..., None]
    mid = np.exp(-((q - 1.0) / 0.12) ** 2) * (1 - _smooth(0.2, 0.9, u))
    col = col * (1 + 0.06 * mid)[..., None]
    col = col * _grain(h, w, seed)[..., None]
    # 掉墨：零星露出底下纸色的小点
    spk = _noise(h, w, 3, 2, seed + 7)
    drop = _smooth(0.82, 0.93, spk) * 0.3
    col = _mix(col, WARM * 0.92, drop[..., None])
    # 墨褐描边：粗细略有起伏
    lw = 0.010 * px * (0.6 + 0.8 * _noise(h, w, 0.05 * px, 2, seed + 9))
    band = 1 - _smooth(0.4 * lw, lw, dt)
    col = _mix(col, INK * 1.15, (0.75 * band * inside)[..., None])
    return np.dstack([col, A])


def _glyph_rgba(A, seed):
    """花心大字的样子：暖白，带很淡的颗粒。"""
    h, w = A.shape
    col = np.ones((h, w, 3), np.float32) * WARM
    col = col * (1 + 0.6 * (_grain(h, w, seed) - 1))[..., None]
    return np.dstack([col, A])


def stroke_tex(k, style="petal"):
    """第 k 笔的 RGBA 贴图，覆盖笔画坐标里的 rbox（内端在下、外端在上），PX_EM 像素/em。
    style="petal" 为花瓣的样子，"glyph" 为花心大字的样子，两者逐像素对齐。"""
    s = strokes()[k]

    def make():
        A = _raster(s.rpath, s.rbox, PX_EM, ss=2)
        if style == "petal":
            x0, y0, x1, y1 = s.rbox
            yy = y0 + (np.arange(A.shape[0], dtype=np.float32) + 0.5) / PX_EM
            u = np.clip(-yy / s.length, 0, 1)[:, None] * np.ones((1, A.shape[1]), np.float32)
            return _petal_rgba(A, u, PX_EM, seed=100 + k)
        return _glyph_rgba(A, seed=200 + k)
    return _memo(f"stroke{k}_{style}", make)


def center_tex():
    """花心完整的"她"字，覆盖 CENTER_BOX（em），PX_EM 像素/em。"""
    return _memo("center", lambda: _glyph_rgba(_raster(glyph_path("她", KIND, WEIGHT), CENTER_BOX, PX_EM, ss=2), 300))


# ---------------------------------------------------------------------------
# 花瓣终位
# ---------------------------------------------------------------------------

def _ring_types(n, rng, weights):
    """给一圈 n 片花瓣分配笔画，相邻两片不重复（首尾也不重复），按权重控制各笔出现的次数。"""
    keys = list(weights)
    w = np.array([weights[k] for k in keys], float)
    counts = np.floor(w / w.sum() * n).astype(int)
    while counts.sum() < n:
        counts[np.argmax(w / w.sum() * n - counts)] += 1
    seq = []
    for _ in range(500):
        pool = [k for k, c in zip(keys, counts) for _ in range(c)]
        rng.shuffle(pool)
        seq = []
        while pool:
            cand = [i for i, k in enumerate(pool) if not seq or k != seq[-1]]
            if not cand:
                break
            seq.append(pool.pop(cand[0]))
        if not pool and seq[0] != seq[-1]:
            return seq
    return seq


RINGS = (
    # 外圈 21 片：内端锚点半径、花瓣长度与最宽处宽度（世界单位）、翘起角、锚点 z、整圈色调
    dict(n=21, r_anchor=0.125, length=0.335, width=0.076, tilt=7.0, z=-0.006, phase=0.0,
         tone=(1.0, 1.0, 1.0), weights={0: 6, 1: 3, 2: 5, 4: 3, 6: 4}),
    # 内圈 13 片：略短，压在外圈之上，角度与外圈错开
    dict(n=13, r_anchor=0.110, length=0.255, width=0.070, tilt=15.0, z=-0.003, phase=0.47,
         tone=(0.97, 0.92, 0.84), weights={0: 4, 1: 2, 2: 4, 4: 1, 6: 2}),
)
FX_RANGE = (0.72, 1.55)          # 横向倍率的范围：把各笔的最宽处调到接近同一宽度，又不让笔画变形太多
FX_MAX = {1: 1.0, 6: 1.0}      # 竖和撇点之撇是等宽的直笔，加宽太多像木板，单独限制


@lru_cache(maxsize=8)
def petal_layout(seed=7):
    """34 片花瓣的终位，按绘制顺序排列（先外圈、后内圈，圈内顺序打乱）。字段见模块说明。"""
    S = strokes()
    rng = np.random.default_rng(seed)
    out = []
    for ring, R in enumerate(RINGS):
        n = R["n"]
        types = _ring_types(n, rng, R["weights"])
        step = 2 * math.pi / n
        base = math.pi / 2 + R["phase"] * step
        items = []
        for j in range(n):
            k = types[j]
            s = S[k]
            theta = base + j * step + rng.uniform(-0.15, 0.15) * step
            scale = R["length"] / s.length * rng.uniform(0.93, 1.07)
            fx = float(np.clip(R["width"] / (s.width * scale) * rng.uniform(0.92, 1.08), FX_RANGE[0],
                               FX_MAX.get(k, FX_RANGE[1])))
            r_a = R["r_anchor"] * rng.uniform(0.94, 1.06)
            axis = theta + math.radians(rng.uniform(-4, 4))
            anchor = r_a * np.array([math.cos(theta), math.sin(theta)])
            tilt = R["tilt"] * rng.uniform(0.6, 1.4)
            pl = place(k, anchor, axis, scale, fx, tilt, R["z"])
            shade = rng.uniform(0.90, 1.06)
            warmth = rng.uniform(-0.03, 0.03)
            tone = np.array(R["tone"])
            tint = tuple(float(x) for x in tone * shade * np.array([1 + warmth, 1.0, 1 - 2 * warmth]))
            items.append(dict(stroke=k, ring=ring, theta=theta, axis=axis, r_anchor=r_a, anchor=anchor,
                              scale=scale, fx=fx, tilt=tilt, z=R["z"], roll=pl["roll"], rot=pl["rot"],
                              center=tuple(float(x) for x in pl["center"]), size=pl["size"], tint=tint))
        perm = rng.permutation(n)
        out.extend(items[i] for i in perm)
    for i, p in enumerate(out):
        p["order"] = i
    return tuple(out)


# ---------------------------------------------------------------------------
# 花心圆盘
# ---------------------------------------------------------------------------

DISC_PX = 2048
SEEDS = 170
GOLDEN = math.radians(137.50776)


def seed_layout(n=SEEDS):
    """花心小"她"字：第 i 粒在半径 R·0.95·√((i+0.5)/n)、角度 i·137.508° 处，字头朝外。
    返回位置 (n, 2)、字号 (n,)、角度 (n,)（弧度）、相对半径 (n,)。"""
    i = np.arange(n)
    r = R_DISC * 0.95 * np.sqrt((i + 0.5) / n)
    th = i * GOLDEN
    pos = np.c_[r * np.cos(th), r * np.sin(th)]
    spacing = R_DISC * math.sqrt(math.pi / n)
    size = spacing * (0.80 + 0.16 * r / R_DISC)
    return pos, size, th, r / R_DISC


def disc_tex():
    """花心圆盘（不含中央大字），覆盖 [-DISC_TEX_R, DISC_TEX_R]²，DISC_PX 像素见方。"""
    def make():
        N = DISC_PX
        px = N / (2 * DISC_TEX_R)                      # 像素/世界单位
        yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
        X = (xx + 0.5) / px - DISC_TEX_R
        Yw = DISC_TEX_R - (yy + 0.5) / px
        r = np.hypot(X, Yw) / R_DISC
        edge = 1.0 + 0.018 * (_noise(N, N, 90, 3, 41) - 0.5)
        body = 1 - _smooth(0.985, 1.0, r / edge)
        # 底色：中心最深，向外渐亮，最外一圈偏黄褐（开放的小花与花粉）
        deep = np.array([0.075, 0.045, 0.028])
        brown = np.array([0.16, 0.095, 0.05])
        rim = np.array([0.36, 0.22, 0.08])
        base = _mix(deep, brown, _smooth(0.3, 0.85, r)[..., None])
        base = _mix(base, rim, (_smooth(0.88, 1.0, r) * 0.7)[..., None])
        base = base * (0.88 + 0.24 * _noise(N, N, 25, 4, 42))[..., None]
        # 小"她"字
        pos, size, th, rr = seed_layout()
        colimg = np.zeros((N, N, 4), np.uint8)
        surf = skia.Surface.MakeRasterDirect(skia.ImageInfo.Make(N, N, skia.kRGBA_8888_ColorType,
                                                                 skia.kPremul_AlphaType), colimg)
        c = surf.getCanvas()
        rng = np.random.default_rng(5)
        gp = glyph_path("她", KIND, WEIGHT)
        adv = glyph_advance()
        for (x, y), sz, t, q in zip(pos, size, th, rr):
            tone = _mix(np.array([0.30, 0.17, 0.08]), np.array([0.66, 0.44, 0.15]), _smooth(0.35, 0.95, q))
            tone = _mix(tone, np.array([0.84, 0.62, 0.20]), _smooth(0.88, 1.0, q) * 0.75)
            tone = np.clip(tone * rng.uniform(0.80, 1.12), 0, 1)
            c.save()
            c.translate((x + DISC_TEX_R) * px, (DISC_TEX_R - y) * px)
            c.rotate(-math.degrees(t - math.pi / 2))      # 字头朝外
            k = sz * px
            c.scale(k, k)
            c.translate(-adv / 2, -EM_MID)
            c.drawPath(gp, skia.Paint(AntiAlias=True, Color=skia.Color4f(*map(float, tone), 1.0)))
            c.restore()
        del c, surf
        sc = colimg.astype(np.float32) / 255
        a = sc[..., 3:4]
        seedcol = np.where(a > 1e-3, sc[..., :3] / np.maximum(a, 1e-3), 0) * _grain(N, N, 43)[..., None]
        # 每粒向右下投一点淡影，显出一点厚度
        shadow = np.roll(gaussian_filter(a[..., 0], 4.0), (6, 4), axis=(0, 1))
        base = base * (1 - 0.6 * shadow)[..., None]
        col = base * (1 - a) + seedcol * a
        # 花心大字周围压暗一圈，让暖白的字从小字里跳出来
        big = np.zeros((N, N), np.uint8)
        s2 = skia.Surface.MakeRasterDirect(skia.ImageInfo.MakeA8(N, N), big)
        c2 = s2.getCanvas()
        c2.translate((DISC_TEX_R - 0.5 * E_CENTER) * px, (DISC_TEX_R - EM_MID * E_CENTER) * px)
        c2.scale(E_CENTER * px, E_CENTER * px)
        c2.drawPath(gp, skia.Paint(AntiAlias=True))
        del c2, s2
        halo_big = np.clip(gaussian_filter(big.astype(np.float32) / 255, 0.010 * px) * 2.2, 0, 1)
        col = col * (1 - 0.72 * halo_big)[..., None]
        halo = (1 - _smooth(1.0, 1.24, r)) * (1 - body)                # 圆盘外缘投在花瓣根部的淡影
        alpha = np.maximum(body, 0.6 * halo)
        col = np.where(body[..., None] > 0.01, col, np.array([0.05, 0.03, 0.02]))
        return np.dstack([col, alpha])
    return _memo("disc", make)


# ---------------------------------------------------------------------------
# 茎与扌
# ---------------------------------------------------------------------------

STEM_LEN = 1.25                 # 茎长（顶端在圆盘背后）
STEM_W = 0.040                  # 茎宽
STEM_TOP = np.array([0.0, -0.04])
STEM_GRIP_V = 0.62              # 握持点在茎上的位置（0 顶端，1 底端）
STEM_LEAN = 0.075               # 握持点相对花心向左偏移：茎在手上方向右弯向花，穿过手时是竖直的
STEM_PX = 1200                  # 茎贴图分辨率（像素/世界单位）


def stem_centerline(v):
    """茎中线上参数 v（0 顶端，1 底端）处的点（花的坐标）。握持点以下是竖直的直线。"""
    v = np.asarray(v, float)
    g = STEM_GRIP_V
    x = STEM_LEAN * (np.clip((g - v) / g, 0, None) ** 2 - 1)
    return np.stack([STEM_TOP[0] + x, STEM_TOP[1] - v * STEM_LEN], -1)


def _stem_poly():
    """茎的轮廓：取"她"字竖画（第 6 笔）的轮廓，起笔与收笔各保留原比例，中段拉长，再按中线弯曲。"""
    s = strokes()[6]
    poly = max(flatten(s.path, 24), key=len)
    x0, y0, x1, y1 = s.bbox
    L = y1 - y0
    k = STEM_W / s.width
    vh, vt = 0.14, 0.10
    v = (poly[:, 1] - y0) / L
    head, tail = vh * L * k, vt * L * k
    midlen = STEM_LEN - head - tail
    d = np.where(v < vh, v * L * k,
                 np.where(v > 1 - vt, head + midlen + (v - (1 - vt)) * L * k,
                          head + (v - vh) / (1 - vh - vt) * midlen))
    X = (poly[:, 0] - (x0 + x1) / 2) * k
    cl = stem_centerline(d / STEM_LEN)
    return np.c_[cl[:, 0] + X, cl[:, 1]]


def stem_geometry():
    """茎平面的中心与尺寸（花的坐标），以及顶端、底端、握持点与建议的 z。"""
    P = _stem_poly()
    pad = 0.02
    x0, x1 = P[:, 0].min() - pad, P[:, 0].max() + pad
    y0, y1 = P[:, 1].min() - pad, P[:, 1].max() + pad
    return {"center": np.array([(x0 + x1) / 2, (y0 + y1) / 2]), "size": (x1 - x0, y1 - y0),
            "box": (x0, y0, x1, y1), "top": stem_centerline(0.0), "bottom": stem_centerline(1.0),
            "grip": stem_centerline(STEM_GRIP_V), "z": -0.012}


def stem_tex():
    """茎的 RGBA 贴图，覆盖 stem_geometry()["size"]，STEM_PX 像素/世界单位。"""
    def make():
        g = stem_geometry()
        x0, y0, x1, y1 = g["box"]
        P = _stem_poly()
        path = skia.Path()
        path.addPoly([skia.Point(float(x), float(-y)) for x, y in P], True)      # 换成 y 向下
        A = _raster(path, (x0, -y1, x1, -y0), STEM_PX, ss=2)
        h, w = A.shape
        yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
        Yw = y1 - (yy + 0.5) / STEM_PX
        v = np.clip((STEM_TOP[1] - Yw) / STEM_LEN, 0, 1)
        cl = stem_centerline(v)[..., 0]
        Xw = x0 + (xx + 0.5) / STEM_PX
        lat = np.clip((Xw - cl) / (STEM_W / 2), -1.3, 1.3)            # 横向：−1 左缘，+1 右缘
        base = _mix(INK, Y, 0.30) * np.array([0.85, 1.05, 0.72])           # 偏绿的橄榄褐
        base = base * (1.05 - 0.15 * v)[..., None]                    # 越往下越暗
        shade = 0.70 + 0.30 * np.cos(np.clip(lat, -1, 1) * 1.3) + 0.10 * np.exp(-((lat + 0.35) / 0.25) ** 2)
        fib = _noise(h, w, 4, 3, 51, aniso=(18, 1))                   # 顺着茎的纤维
        col = base * shade[..., None] * (0.9 + 0.2 * fib)[..., None]
        col = col * _grain(h, w, 52)[..., None]
        dt = distance_transform_edt(A > 0.5)
        lw = 0.0035 * STEM_PX
        band = 1 - _smooth(0.4 * lw, lw, dt)
        col = _mix(col, INK * 0.9, (0.6 * band)[..., None])
        return np.dstack([col, A])
    return _memo("stem", make)


HAND_KIND, HAND_WEIGHT = "sans", 900
HAND_EM = 0.60                                   # "扌"的字号
HAND_BOX = (-0.02, -0.96, 0.62, 0.16)            # "扌"贴图覆盖的 em 矩形
HAND_GRIP_EM = np.array([0.445, -0.490])          # 握持点（em）：横与提的右段之间、竖钩右侧


def hand_geometry(grip=None):
    """"扌"平面的中心与尺寸，使握持点落在 grip（花的坐标，缺省为茎的握持点）。"""
    if grip is None:
        grip = stem_geometry()["grip"]
    x0, y0, x1, y1 = HAND_BOX
    off = np.array([(x0 + x1) / 2 - HAND_GRIP_EM[0], -((y0 + y1) / 2 - HAND_GRIP_EM[1])]) * HAND_EM
    return {"center": np.asarray(grip) + off, "size": ((x1 - x0) * HAND_EM, (y1 - y0) * HAND_EM),
            "grip": np.asarray(grip), "z": 0.004}


def hand_tex():
    """"扌"的 RGBA 贴图（墨褐，带颗粒、少量掉墨与略毛的边），覆盖 HAND_BOX，PX_EM 像素/em。"""
    def make():
        A = _raster(glyph_path("扌", HAND_KIND, HAND_WEIGHT), HAND_BOX, PX_EM, ss=2)
        h, w = A.shape
        rough = _noise(h, w, 5, 3, 61)
        A2 = np.clip((gaussian_filter(A, 1.2) - 0.5 + (rough - 0.5) * 0.35) * 5 + 0.5, 0, 1)
        A2 = np.minimum(A2, gaussian_filter(A, 0.8) * 1.6)
        col = np.ones((h, w, 3), np.float32) * INK * 0.85
        col = col * (0.94 + 0.12 * _noise(h, w, 160, 3, 62))[..., None] * _grain(h, w, 63, 1.2)[..., None]
        spk = _noise(h, w, 3, 2, 64)
        col = _mix(col, INK * 1.9, (_smooth(0.84, 0.94, spk) * 0.35)[..., None])
        return np.dstack([col, A2])
    return _memo("hand", make)


def grip_shadow_tex():
    """"扌"的横和提投在茎上的淡影，覆盖与 hand_tex() 相同的矩形；alpha 只在茎经过处不为零。"""
    def make():
        x0, y0, x1, y1 = HAND_BOX
        fingers = skia.Path()
        for c in contours(glyph_path("扌", HAND_KIND, HAND_WEIGHT)):
            bx = bounds(c)
            if bx[3] - bx[1] < 0.5:                 # 横与提（竖钩是高的那一笔）
                fingers.addPath(c)
        q = PX_EM // 4
        F = _raster(fingers, HAND_BOX, q)
        sh = np.clip(gaussian_filter(F, 0.02 * q) * 1.5, 0, 1)
        W, H = int(round((x1 - x0) * PX_EM)), int(round((y1 - y0) * PX_EM))
        sh = cv2.resize(sh, (W, H), interpolation=cv2.INTER_CUBIC)
        ex = x0 + (np.arange(W, dtype=np.float32) + 0.5) / PX_EM
        half = STEM_W / HAND_EM / 2 * 1.1
        band = 1 - _smooth(half * 0.75, half, np.abs(ex - HAND_GRIP_EM[0]))
        a = np.clip(sh, 0, 1) * band[None, :] * 0.85
        col = np.ones((H, W, 3), np.float32) * np.array([0.05, 0.035, 0.025])
        return np.dstack([col, a])
    return _memo("grip_shadow", make)


# ---------------------------------------------------------------------------
# 展开动画
# ---------------------------------------------------------------------------

def _ease(x):
    x = np.clip(x, 0, 1)
    return float(x * x * x * (x * (6 * x - 15) + 10))


def _wrap(a):
    return (a + math.pi) % (2 * math.pi) - math.pi


SPREAD = 0.30           # 各片花瓣开始时间的错开量（占总进度）


def bloom_state(u, E=E_CENTER, swirl=1):
    """bloom 进度 u（0–1）时各元素的状态，按绘制顺序排列。每项是 dict：
    kind="petal"：stroke、anchor、axis、scale、fx、tilt、z、mix（0 为字形样子，1 为花瓣样子）、tint、progress，
                  以及 place() 给出的 center（三维）、size、roll、rot；
    kind="disc"：center、size、opacity；kind="center"：center、size。
    swirl=1 时笔画副本沿逆时针螺线展开，−1 为顺时针，0 为走最短的角度。"""
    S = strokes()
    out = []
    for p in petal_layout():
        k = p["stroke"]
        s = S[k]
        a0 = em_to_flower(*s.inner, E)
        r0, th0 = float(np.hypot(*a0)), float(math.atan2(a0[1], a0[0]))
        th1 = p["theta"]
        d = th1 - th0
        d = d % (2 * math.pi) if swirl > 0 else (-((-d) % (2 * math.pi)) if swirl < 0 else _wrap(d))
        delay = SPREAD * ((th1 - math.pi / 2) % (2 * math.pi)) / (2 * math.pi)
        if p["ring"] == 1:
            delay = min(SPREAD, delay + 0.05)
        x = (u - delay) / (1 - SPREAD)
        t = _ease(x)
        theta = th0 + d * t
        r = r0 + (p["r_anchor"] - r0) * _ease(x * 1.15)
        anchor = r * np.array([math.cos(theta), math.sin(theta)])
        rel0, rel1 = _wrap(s.phi - th0), _wrap(p["axis"] - th1)
        axis = theta + rel0 + (rel1 - rel0) * _ease(t * 1.4)
        scale = E + (p["scale"] - E) * t
        fx = 1 + (p["fx"] - 1) * t
        tilt = p["tilt"] * t
        pl = place(k, anchor, axis, scale, fx, tilt, p["z"])
        st = dict(kind="petal", stroke=k, ring=p["ring"], anchor=anchor, axis=axis, scale=scale, fx=fx, tilt=tilt,
                  z=p["z"], mix=float(_smooth(0.04, 0.45, t)), tint=p["tint"], progress=t, order=p["order"])
        st.update(center=pl["center"], size=pl["size"], roll=pl["roll"], rot=pl["rot"])
        out.append(st)
    disc_u = _ease((u - 0.12) / 0.6)
    if disc_u > 0:
        sc = 0.35 + 0.65 * disc_u
        out.append(dict(kind="disc", center=np.array([0.0, 0.0, -0.001]),
                        size=(2 * DISC_TEX_R * sc, 2 * DISC_TEX_R * sc), opacity=float(_smooth(0.0, 0.35, disc_u))))
    ch = center_home(E)
    out.append(dict(kind="center", center=np.array([ch["center"][0], ch["center"][1], 0.001]), size=ch["size"]))
    return out


def bloom_items(u, origin=(0, 0, 0), rot=(0, 0, 0), scale=1.0, light=None, group="past", stack="flower",
                with_stem=True, E=E_CENTER, center_color=(1.0, 1.0, 1.0)):
    """bloom 进度 u 时整朵花（含茎）的引擎平面列表，按绘制顺序排列。origin、rot（度）为花在世界中的
    位置与朝向，scale 为整体缩放；light(p) 给出世界坐标 p 处的光照颜色（缺省为白光），乘在各平面的
    color 上；center_color 再乘在花心大字上，设到 1.1–1.2 时它像歌词一样微微发亮。"""
    from engine import Plane
    R = _rot_matrix(*rot)
    o = np.asarray(origin, float)
    lit = light or (lambda p: (1.0, 1.0, 1.0))

    def world(c):
        return o + R @ (np.asarray(c, float) * scale)

    def col(p, mult=(1, 1, 1)):
        return tuple(float(x) for x in np.asarray(lit(p), float) * np.asarray(mult, float))

    flat_rot = euler_from_matrix(R)
    items = []
    if with_stem:
        g = stem_geometry()
        p = world([g["center"][0], g["center"][1], g["z"]])
        items.append(Plane(stem_tex(), center=p, size=tuple(np.array(g["size"]) * scale), rot=flat_rot,
                           color=col(p), group=group, stack=stack))
    for st in bloom_state(u, E):
        p = world(st["center"])
        size = tuple(np.array(st["size"]) * scale)
        if st["kind"] == "petal":
            r3 = euler_from_matrix(R @ _rot_matrix(*st["rot"]))
            k = st["stroke"]
            if st["mix"] < 1:
                items.append(Plane(stroke_tex(k, "glyph"), center=p, size=size, rot=r3, opacity=1 - st["mix"],
                                   color=col(p, center_color), group=group, stack=stack))
            if st["mix"] > 0:
                items.append(Plane(stroke_tex(k, "petal"), center=p, size=size, rot=r3, opacity=st["mix"],
                                   color=col(p, st["tint"]), group=group, stack=stack))
        elif st["kind"] == "disc":
            items.append(Plane(disc_tex(), center=p, size=size, rot=flat_rot, opacity=st["opacity"], color=col(p),
                               group=group, stack=stack))
        else:
            items.append(Plane(center_tex(), center=p, size=size, rot=flat_rot, color=col(p, center_color),
                               group=group, stack=stack))
    return items


def hand_items(origin=(0, 0, 0), rot=(0, 0, 0), scale=1.0, light=None, group="past", stack="flower",
               grip=None, shadow=1.0):
    """"扌"与握持淡影的引擎平面，用与 bloom_items 相同的花的坐标系（握持点缺省在茎的握持点）。
    花离手时把 shadow 降到 0；"扌"若要留在原处，固定 origin、rot 即可。"""
    from engine import Plane
    R = _rot_matrix(*rot)
    o = np.asarray(origin, float)
    lit = light or (lambda p: (1.0, 1.0, 1.0))
    hg = hand_geometry(grip)
    size = tuple(np.array(hg["size"]) * scale)
    items = []
    for tex, z, op in ((grip_shadow_tex(), hg["z"] - 0.002, shadow), (hand_tex(), hg["z"], 1.0)):
        if op <= 0:
            continue
        p = o + R @ (np.array([hg["center"][0], hg["center"][1], z]) * scale)
        items.append(Plane(tex, center=p, size=size, rot=euler_from_matrix(R), opacity=op,
                           color=tuple(float(x) for x in lit(p)), group=group, stack=stack))
    return items


# ---------------------------------------------------------------------------
# 二维合成（远景贴图、预览）
# ---------------------------------------------------------------------------

def _premul(img):
    return np.dstack([img[..., :3] * img[..., 3:4], img[..., 3:4]])


def _paste(canvas, tex, center, size, roll_deg, frame, tint=(1, 1, 1), opacity=1.0):
    """把直通 alpha 贴图 tex 按平面（中心、尺寸、roll）画进预乘 alpha 画布。
    frame = (x0, y1, px)：画布左上角的世界坐标与每单位像素数。"""
    H, W = canvas.shape[:2]
    x0, y1, px = frame
    th, tw = tex.shape[:2]
    a = math.radians(roll_deg)
    ca, sa = math.cos(a), math.sin(a)
    sx, sy = size[0] / tw, size[1] / th
    M = np.array([[ca * sx * px, sa * sy * px], [-sa * sx * px, ca * sy * px]])
    ox = (center[0] - x0) * px - (M[0, 0] * tw + M[0, 1] * th) / 2
    oy = (y1 - center[1]) * px - (M[1, 0] * tw + M[1, 1] * th) / 2
    src = _premul(tex) * np.array([*tint, 1.0], np.float32) * opacity
    scale = math.sqrt(abs(np.linalg.det(M)))
    if scale < 0.7:                                     # 缩得很小时先预缩，避免锯齿
        f = max(scale * 1.4, 0.02)
        sw, sh = max(2, int(tw * f)), max(2, int(th * f))
        src = cv2.resize(src, (sw, sh), interpolation=cv2.INTER_AREA)
        M = M * np.array([tw / sw, th / sh])
    A = np.array([[M[0, 0], M[0, 1], ox + 0.5 * (M[0, 0] + M[0, 1]) - 0.5],
                  [M[1, 0], M[1, 1], oy + 0.5 * (M[1, 0] + M[1, 1]) - 0.5]], np.float32)
    out = cv2.warpAffine(src, A, (W, H), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_CONSTANT, borderValue=0)
    canvas[...] = out + canvas * (1 - out[..., 3:4])


def compose(u=1.0, res=2048, half=FLOWER_TEX_R, center_xy=(0.0, 0.0), with_stem=False, with_hand=False,
            background=None, E=E_CENTER):
    """在二维里按 bloom 进度 u 合成整朵花（正面平行投影），返回直通 alpha 的 RGBA；给出 background
    颜色时返回叠在该颜色上的 RGB。覆盖以 center_xy 为中心、半边长 half 的正方形。"""
    canvas = np.zeros((res, res, 4), np.float32)
    px = res / (2 * half)
    frame = (center_xy[0] - half, center_xy[1] + half, px)
    if with_stem:
        g = stem_geometry()
        _paste(canvas, stem_tex(), g["center"], g["size"], 0, frame)
    if with_hand:
        hg = hand_geometry()
        _paste(canvas, grip_shadow_tex(), hg["center"], hg["size"], 0, frame)
        _paste(canvas, hand_tex(), hg["center"], hg["size"], 0, frame)
    for st in bloom_state(u, E):
        if st["kind"] == "petal":
            k = st["stroke"]
            # 平行投影：贴图沿主轴缩短 cos(tilt)，中心随之向锚点收拢
            kk = math.cos(math.radians(st["tilt"]))
            a = np.asarray(st["anchor"])
            ax = np.array([math.cos(st["axis"]), math.sin(st["axis"])])
            c2 = np.asarray(st["center"][:2])
            rel = c2 - a
            along = rel @ ax
            c2 = a + rel - ax * along * (1 - kk)
            size = (st["size"][0], st["size"][1] * kk)
            if st["mix"] < 1:
                _paste(canvas, stroke_tex(k, "glyph"), c2, size, st["roll"], frame, opacity=1 - st["mix"])
            if st["mix"] > 0:
                _paste(canvas, stroke_tex(k, "petal"), c2, size, st["roll"], frame, tint=st["tint"],
                       opacity=st["mix"])
        elif st["kind"] == "disc":
            _paste(canvas, disc_tex(), st["center"], st["size"], 0, frame, opacity=st["opacity"])
        else:
            _paste(canvas, center_tex(), st["center"], st["size"], 0, frame)
    if background is not None:
        return canvas[..., :3] + np.asarray(background) * (1 - canvas[..., 3:4])
    a = canvas[..., 3:4]
    return np.dstack([np.where(a > 1e-4, canvas[..., :3] / np.maximum(a, 1e-4), 0), a])


def flower_full_box():
    """带茎的整朵合成贴图覆盖的矩形（花的坐标）：(x0, y0, x1, y1)。"""
    g = stem_geometry()
    return (-FLOWER_TEX_R, float(g["box"][1]), FLOWER_TEX_R, FLOWER_TEX_R)


def flower_tex(with_stem=False):
    """整朵向日葵的合成贴图（远景用）。不带茎时覆盖 [-FLOWER_TEX_R, FLOWER_TEX_R]²，2048 像素见方；
    带茎时覆盖 flower_full_box()，像素密度相同。"""
    if not with_stem:
        return _memo("composite", lambda: compose(1.0, 2048))

    def make():
        x0, y0, x1, y1 = flower_full_box()
        px = 2048 / (2 * FLOWER_TEX_R)
        W, H = int(round((x1 - x0) * px)), int(round((y1 - y0) * px))
        side = max(W, H)
        img = compose(1.0, side, half=side / px / 2, center_xy=((x0 + x1) / 2, (y0 + y1) / 2), with_stem=True)
        oy, ox = (side - H) // 2, (side - W) // 2
        return img[oy:oy + H, ox:ox + W]
    return _memo("composite_stem", make)


# ---------------------------------------------------------------------------
# 笔画拆分图
# ---------------------------------------------------------------------------

def stroke_sheet(path=None):
    """笔画拆分图：左边是"她"字，每一笔一个色块并标注序号、花瓣的内端（圆点）与外端（箭头）；
    右边是五个花瓣笔画的贴图（笔画坐标：内端在下、外端在上）。"""
    S = strokes()
    Wd, Ht = 2400, 1200
    bgc = np.array([0.93, 0.91, 0.86])
    img = np.ones((Ht, Wd, 3), np.float32) * bgc
    pal = [(0.85, 0.30, 0.25), (0.20, 0.55, 0.80), (0.95, 0.62, 0.12), (0.62, 0.60, 0.56),
           (0.55, 0.30, 0.70), (0.62, 0.60, 0.56), (0.20, 0.62, 0.40), (0.86, 0.45, 0.65)]
    em_px, ox, oy = 1000, 90, 1010
    for k, s in enumerate(S):
        A = _raster(s.path, (-ox / em_px, -oy / em_px, (1150 - ox) / em_px, (Ht - oy) / em_px), em_px)
        img[:, :1150] = _mix(img[:, :1150], np.array(pal[k]), (A * 0.8)[..., None])
    surf = look.surface(Wd, Ht)
    c = surf.getCanvas()
    rgb = (np.clip(img, 0, 1) * 255).astype(np.uint8)
    c.drawImage(skia.Image.fromarray(np.dstack([rgb, np.full((Ht, Wd), 255, np.uint8)]),
                                     colorType=skia.kRGBA_8888_ColorType), 0, 0)
    fnt = look.font("sans", 700, 30)
    fsm = look.font("sans", 500, 26)
    ink = skia.Paint(AntiAlias=True, Color=skia.Color(40, 28, 20))
    pen = skia.Paint(AntiAlias=True, Color=skia.Color(30, 20, 15), StrokeWidth=3, Style=skia.Paint.kStroke_Style)
    label_at = {3: (0.02, -0.62), 5: (0.55, -0.60), 7: (0.86, -0.08)}
    for k, s in enumerate(S):
        cx, cy = label_at.get(k, ((s.bbox[0] + s.bbox[2]) / 2, (s.bbox[1] + s.bbox[3]) / 2))
        X, Yp = ox + cx * em_px, oy + cy * em_px
        c.drawCircle(X, Yp, 22, skia.Paint(AntiAlias=True, Color=skia.Color(255, 255, 255, 235)))
        c.drawString(str(k), X - 9, Yp + 11, fnt, ink)
        if s.petal:
            ix, iy = ox + s.inner[0] * em_px, oy + s.inner[1] * em_px
            ex, ey = ox + s.outer[0] * em_px, oy + s.outer[1] * em_px
            c.drawLine(ix, iy, ex, ey, pen)
            c.drawCircle(ix, iy, 9, skia.Paint(AntiAlias=True, Color=skia.Color(30, 20, 15)))
            ang = math.atan2(ey - iy, ex - ix)
            for da in (2.6, -2.6):
                c.drawLine(ex, ey, ex + 24 * math.cos(ang + da), ey + 24 * math.sin(ang + da), pen)
    c.drawString("「她」思源宋体 900 的八个轮廓就是八个笔画；圆点为花瓣内端，箭头指向外端", 60, 52, fsm, ink)
    c.drawString("0 撇　1 撇点之撇　2 撇点之点　4 横折钩　6 竖　用作花瓣；3、5 两横太细，7 竖弯钩呈 L 形，只留在花心",
                 60, 1165, fsm, ink)
    c.drawString("花瓣贴图（内端在下，外端在上）", 1250, 110, fsm, ink)
    cells = [(1200 + i * 236, 160) for i in range(5)]
    hmax = max(S[k].size_em[1] for k in PETAL_STROKES)
    f = 860 / (hmax * PX_EM)
    for (x, yb), k in zip(cells, PETAL_STROKES):
        t = stroke_tex(k, "petal")
        h, w = t.shape[:2]
        small = cv2.resize(t, (max(1, int(w * f)), max(1, int(h * f))), interpolation=cv2.INTER_AREA)
        sh, sw = small.shape[:2]
        rgba = (np.clip(_premul(small), 0, 1) * 255).astype(np.uint8)
        im = skia.Image.fromarray(np.ascontiguousarray(rgba), colorType=skia.kRGBA_8888_ColorType,
                                  alphaType=skia.kPremul_AlphaType)
        au, av = S[k].anchor_uv
        c.drawImage(im, x + 110 - au * sw, yb + 900 - av * sh)
        c.drawCircle(x + 110, yb + 900, 7, skia.Paint(AntiAlias=True, Color=skia.Color(30, 20, 15)))
        c.drawString(f"{k} {S[k].name}", x + 40, yb + 960, fsm, ink)
    del c
    out = surf.makeImageSnapshot().toarray()[..., :3]
    path = path or (ASSETS / "flower_01_笔画拆分.png")
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(out).save(path)
    print(path)
    return out


if __name__ == "__main__":
    look.low_priority()
    for k in PETAL_STROKES:
        stroke_tex(k, "petal")
        stroke_tex(k, "glyph")
    center_tex(), disc_tex(), stem_tex(), hand_tex(), grip_shadow_tex()
    flower_tex(), flower_tex(with_stem=True)
    stroke_sheet()
    for s in strokes():
        print(s.idx, s.name, "len %.3f phi %.1f° width %.3f" % (s.length, math.degrees(s.phi), s.width))
