"""段与段的交接状态。

全片按段落分开制作、分段渲染，再无损拼接。每个交接时刻两侧的画面必须连得上，所以交接处的状态写在这里，
相邻两段都从这里取，而不是各自去模仿对方的画面。交接有两种：

一种是共同的画面状态。前奏到主歌一在一张旧纸上交接：纸、镜头和落在纸上的灰尘由这里的函数给出，前奏把灰尘
落定在这些位置上，主歌一从这里接着往下做。

另一种是整幅画面停在一个简单状态上：全白（照片过曝、冲出最上面一层）、全暗（灯灭、沉进深水），或者全暗中只剩
一个光点（夜色吞没一切，只剩桅顶的灯）。这类交接由 *_frame(t) 直接给出整帧，前一段最后几帧和后一段最初几帧
都返回它，两侧各自负责淡入和淡出。

| 时刻（秒） | 帧号 | 前一段 → 后一段 | 交接状态 |
|---|---|---|---|
| 27.0 | 1620 | 前奏 → 主歌一前半 | 旧纸，灰尘落定（paper_*） |
| 40.1167 | 2407 | 主歌一前半 → 主歌一后半 | 暖白（white_frame，WARM_WHITE） |
| 51.0 | 3060 | 主歌一后半 → 副歌一 | 全暗（dark_frame） |
| 75.4 | 4524 | 副歌一前半 → 副歌一后半 | 深水里的暗（dark_frame，DEEP） |
| 102.05 | 6123 | 间奏一 → 主歌二 | 全暗中一个暖色光点（point_frame） |
| 116.0 | 6960 | 主歌二 → 副歌二 | 冷白（white_frame，COLD_WHITE） |

帧号按每秒 60 帧计；前一段渲染到交接帧之前（不含），后一段从交接帧开始。
"""
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "style"))
import look  # noqa: E402
from engine import FrameSpec, Particles, Plane, Tex  # noqa: E402
from flatcam import FlatCam, cached  # noqa: E402

# 过去各段的标准调色（副歌一样片所用）；各段可以在段内按需要偏离，但交接时刻回到这里
GRADE_PAST = {"past": {"halation": 1.2, "lift": 0.03, "gain": 1.25, "vignette": 0.38, "weave": 0.5, "scratch": 0.5}}

# 交接时刻
T_PAPER = 1620 / 60          # 27.0
T_SUMMER = 2407 / 60         # 40.1167
T_LAMP = 3060 / 60           # 51.0
T_DEEP = 4524 / 60           # 75.4
T_POINT = 6123 / 60          # 102.05
T_TODAY = 6960 / 60          # 116.0

WARM_WHITE = (1.0, 0.975, 0.93)      # 过曝的日光
COLD_WHITE = (0.95, 0.97, 1.0)       # 今天的冷光
DARK = (0.012, 0.012, 0.016)         # 屋里灯灭后的暗
DEEP = (0.006, 0.014, 0.020)         # 深水里的暗，略带青

_STILL = FlatCam([(0.0, 0.0, 0.0, 10.0)])


def white_frame(t, color=WARM_WHITE):
    """整幅画面为单色白。"""
    cam, _ = _STILL(t)
    return FrameSpec(cam, [], grade={"final": {"fade": 1.0, "fade_color": color}})


def dark_frame(t, color=DARK):
    """整幅画面为单色暗。"""
    cam, _ = _STILL(t)
    return FrameSpec(cam, [], grade={"final": {"fade": 1.0, "fade_color": color}})


# ---------------------------------------------------------------- 全暗中的光点（102.05）

POINT_SCREEN = (0.5, 0.40)           # 光点在画面上的位置（比例，左上角为原点）
POINT_COLOR = (1.0, 0.76, 0.46)      # 煤油灯、桅灯一类的暖光
POINT_CORE = 0.010                   # 灯芯直径，占画面高的比例
POINT_HALO = 0.16                    # 光晕直径，占画面高的比例


def _soft_dot(n=256, p=1.5):
    yy, xx = np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1
    a = np.clip(1 - np.hypot(xx, yy), 0, 1) ** p
    return np.dstack([np.ones((n, n, 3), np.float32), a.astype(np.float32)])


def point_items(cam_fn, t, k=1.0, z=1.0):
    """在当前镜头下画出交接用的光点：cam_fn 为 FlatCam（需要 screen_to_world）。k 为亮度倍数，交接时为 1。
    间奏一用它把帆远去后的桅灯落到这个位置，主歌二用它把这个光点变成晚灯。"""
    (x, y), Hs = cam_fn.screen_to_world(t, *POINT_SCREEN, z=z)
    core = cached("handoff_core", lambda: Tex(_soft_dot(128, 3.0)))
    halo = cached("handoff_halo", lambda: Tex(_soft_dot(256, 2.2)))
    c = np.array(POINT_COLOR)
    return [Plane(halo, center=(x, y, z), size=(POINT_HALO * Hs,) * 2, blend="add", color=tuple(c * 0.55 * k),
                  group="past"),
            Plane(core, center=(x, y, z + 0.001), size=(POINT_CORE * Hs * 2.2,) * 2, blend="add",
                  color=tuple(np.array([1.0, 0.93, 0.80]) * 2.2 * k), group="past")]


def point_frame(t):
    """全暗中只剩一个光点。背景不是纯黑，而是极暗的夜色。"""
    cam, H = _STILL(t)
    bg = Plane(None, center=(0, 0, -1.0), size=(60, 34), color=(0.010, 0.012, 0.018), group="past")
    return FrameSpec(cam, [bg] + point_items(_STILL, t), grade=GRADE_PAST)


# ---------------------------------------------------------------- 旧纸（27.0）
# 纸平铺在 z = 0，正对镜头。交接时镜头停在 PAPER_CAM：画面中心 (0, 0)，画面高 12（宽约 21.3），
# 主歌一的 L01 按每字 1.6 写在纸上时整行（11 个字位，17.6 宽）正好在画面里。纸比画面大得多，镜头在纸上移动不会露边。

PAPER_CAM = (0.0, 0.0, 12.0)         # (x, y, H)
PAPER_SIZE = (48.0, 30.0)
# 纸面取自 Wikimedia Commons 上一张公有领域的旧纸扫描（File:Old paper7.jpg）：发黄、有水渍和霉点，
# 一道横向折痕和一道很淡的竖向折痕。取它 1920 × 1200 的一块铺满整张纸，横折痕落在画面下方 y ≈ -4.5 处。
# 照片只负责大尺度的颜色和污渍；近看时的纸纤维由 paper_fibers() 生成的显微纹理按世界坐标叠加，
# 镜头推进到"吵"字的"口"里（画面高约 0.6）时仍有细节。主歌一的钢笔墨迹按同一张纤维纹理洇开。
PAPER_PHOTO = Path(__file__).resolve().parents[2] / "assets" / "images" / "Old_paper7.jpg"
PAPER_CROP = (0, 490, 1920, 1690)    # 照片里取用的范围（像素，x0, y0, x1, y1）
PAPER_COLOR = (0.955, 0.985, 1.0)    # 乘在照片上，使平均颜色接近旧纸黄 × 0.92
PAPER_UNI = {"fib_tile": 0.6, "fib_amount": 1.3}
PAPER_FIB_VERSION = 3


def paper_fibers():
    """纸纤维的显微纹理（2048 × 2048，四边无缝，float32 RGB）：R 为纤维在斜射灯光下的明暗起伏（0.5 为平均），
    G 为吸墨程度（纤维中心线和孔隙处高），B 为细颗粒。纤维是长约 500 像素、宽 7–18 像素的扁带，大致沿造纸的
    流向（x 方向）排列，另有大量细短的纤维丝。按 PAPER_UNI["fib_tile"] = 0.6 平铺时，一根主纤维约长 0.15、
    宽 0.004 个世界单位，与纸上 1 厘米高的钢笔字相比，正是真实纸纤维的尺度。生成一次后缓存到磁盘。"""
    def make():
        import math
        import skia
        from scipy.ndimage import gaussian_filter
        cache = Path(__file__).resolve().parents[2] / "data" / "cache" / "seg_a2" / f"fibers_v{PAPER_FIB_VERSION}.npy"
        if cache.exists():
            return np.load(cache).astype(np.float32)
        N = 2048
        rng = np.random.default_rng(1977)

        def fibers(n, len_mu, len_sig, w_lo, w_hi, curl):
            out = []
            for _ in range(n):
                x, y = rng.uniform(0, N, 2)
                th = rng.normal(0.0, 0.9) if rng.uniform() < 0.55 else rng.uniform(-math.pi, math.pi)
                L = float(np.clip(rng.lognormal(math.log(len_mu), len_sig), len_mu * 0.25, len_mu * 3.5))
                out.append((x, y, th, L, rng.uniform(w_lo, w_hi), *rng.normal(0, curl, 2)))
            return out

        def layer(fs, alpha, wk=1.0, offset=(0.0, 0.0), blur=0.0):
            arr = np.zeros((N, N), np.uint8)
            s = skia.Surface.MakeRasterDirect(skia.ImageInfo.MakeA8(N, N), arr)
            c = s.getCanvas()
            c.translate(*offset)
            for x, y, th, L, w, k1, k2 in fs:
                d = np.array([math.cos(th), math.sin(th)])
                nrm = np.array([-d[1], d[0]])
                p0 = np.array([x, y])
                p1, p2, p3 = p0 + d * L / 3 + nrm * k1 * L, p0 + d * 2 * L / 3 + nrm * k2 * L, p0 + d * L
                paint = skia.Paint(AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=w * wk,
                                   StrokeCap=skia.Paint.kRound_Cap, Color=skia.Color4f(1, 1, 1, alpha))
                for ox in (-N, 0, N):
                    for oy in (-N, 0, N):
                        o = np.array([ox, oy])
                        path = skia.Path()
                        path.moveTo(*(p0 + o))
                        path.cubicTo(*(p1 + o), *(p2 + o), *(p3 + o))
                        c.drawPath(path, paint)
            del c, s
            a = arr.astype(np.float32) / 255
            return gaussian_filter(a, blur, mode="wrap") if blur > 0 else a

        big = fibers(420, 520, 0.45, 7, 18, 0.10)
        small = fibers(2600, 120, 0.5, 1.6, 4.0, 0.18)
        lit = layer(big, 0.22, 0.85, blur=0.7) + layer(small, 0.16, 1.0, blur=0.5)
        shade = layer(big, 0.20, 0.85, (2.5, 3.0), 1.6) + layer(small, 0.10, 1.0, (1.2, 1.4), 0.8)
        pores = gaussian_filter(rng.normal(0, 1, (N, N)).astype(np.float32), 3.0, mode="wrap")
        pores = (pores - pores.mean()) / (pores.std() + 1e-6)
        R = 0.5 + 0.55 * (lit - shade) + 0.025 * pores
        core = layer(big, 0.9, 0.45, blur=1.2) + layer(small, 0.6, 0.7, blur=0.6)
        G = np.clip(np.clip(core, 0, 1.2) * 0.75 + np.clip(pores * 0.12 + 0.12, 0, 0.35), 0, 1)
        grain = gaussian_filter(rng.normal(0, 1, (N, N)).astype(np.float32), 1.2, mode="wrap")
        B = np.clip(0.5 + grain / (grain.std() + 1e-6) * 0.16, 0, 1)
        out = np.dstack([np.clip(R, 0, 1), G, B]).astype(np.float32)
        cache.parent.mkdir(parents=True, exist_ok=True)
        np.save(cache, out.astype(np.float16))
        return out
    return cached("handoff_paper_fibers", lambda: Tex(make(), repeat=True))


def _paper_material():
    """注册旧纸的材质：照片底色 × 两种尺度的纤维明暗 × 纸浆絮聚造成的云状明暗。纤维纹理按世界坐标取样，
    远看时被多级缩小图平均掉，近看时逐渐显出。"""
    from engine import register_material
    register_material("handoff_paper", r"""
uniform sampler2D fibers;
uniform float fib_tile;
uniform float fib_amount;
vec4 material(vec4 base) {
    vec2 w = v_wpos.xy;
    vec4 a = texture(fibers, w / fib_tile);
    vec4 b = texture(fibers, mat2(0.6, -0.8, 0.8, 0.6) * w / (fib_tile * 3.1) + vec2(0.31, 0.77));
    vec4 c = textureLod(fibers, mat2(-0.28, 0.96, -0.96, -0.28) * w / (fib_tile * 9.0) + vec2(0.13, 0.41), 6.0);
    float rel = (a.r - 0.5) * 1.0 + (b.r - 0.5) * 0.75;
    float floc = (c.r - 0.5) * 3.0 + (c.g - 0.3) * 0.6;
    float gr = (a.b - 0.5) * 0.5;
    vec3 col = base.rgb * (1.0 + fib_amount * (0.30 * rel + 0.10 * gr + 0.05 * floc));
    return vec4(col, base.a);
}
""", {"fib_tile": 0.6, "fib_amount": 1.0})
    return True


def paper_photo():
    """旧纸照片（RGB，float32），已裁成纸的宽高比。"""
    def make():
        from PIL import Image
        im = Image.open(PAPER_PHOTO).convert("RGB").crop(PAPER_CROP)
        a = np.asarray(im, np.float32) / 255.0
        m = a.mean((0, 1))
        a = np.clip(m + (a - m) * 1.6, 0, 1)          # 水渍和霉点加深一些，远看也认得出是旧纸
        return Tex(a)
    return cached("handoff_paper_photo", make)


def paper_light():
    """纸面上的光：一盏暖色台灯从左上方照下来，右下角暗一些（正片叠底的大渐变）。灯照得较开，L01 行尾的"吵"
    （x ≈ 7.5）仍在亮处，主歌一在那里推进到"口"字里、出现电视和照片。"""
    def make():
        n = 512
        yy, xx = np.mgrid[0:n, 0:n] / (n - 1)
        dx, dy = (xx - 0.40) * PAPER_SIZE[0], (yy - 0.32) * PAPER_SIZE[1]
        r = np.hypot(dx, dy * 1.15)
        v = 0.42 + 0.58 * np.exp(-(r / 20.0) ** 2)
        return np.dstack([v * 1.0, v * 0.95, v * 0.86, np.ones_like(v)]).astype(np.float32)
    return cached("handoff_paper_light", make)


def paper_items(t):
    """纸与纸面上的光。"""
    cached("handoff_paper_material", _paper_material)
    uni = dict(PAPER_UNI)
    uni["fibers"] = paper_fibers()
    return [Plane(paper_photo(), center=(0.0, 0.0, 0.0), size=PAPER_SIZE, color=PAPER_COLOR, material="handoff_paper",
                  uniforms=uni, group="past", stack="paper"),
            Plane(paper_light(), center=(0.0, 0.0, 0.002), size=PAPER_SIZE, blend="multiply", group="past",
                  stack="paper")]


N_DUST = 220


def dust_layout():
    """落在纸上的灰尘：位置 (N, 2)、大小 (N,)、落定时刻 (N,)。灰尘大多落在画面中部偏上，L01 将要写字的那一带
    更密，主歌一让它们随着歌词"漸漸消失"。"""
    def make():
        rng = np.random.default_rng(27)
        n = N_DUST
        x = rng.normal(0.0, 6.0, n).clip(-10.4, 10.4)
        y = rng.normal(0.6, 2.6, n).clip(-5.6, 5.6)
        size = rng.lognormal(np.log(0.035), 0.45, n).clip(0.012, 0.13)
        land = np.sort(rng.uniform(25.6, 26.95, n))[rng.permutation(n)]
        return np.c_[x, y], size, land
    return cached("handoff_dust", make)


def dust_items(t, alpha=None, z=0.004):
    """已经落定的灰尘：落在纸上的那一刻是一点微亮的光，随后在约 0.35 秒里冷却成灰色的小斑点。
    alpha 为每粒灰尘的不透明度 (N,)，主歌一用它让灰尘逐渐消失；落定之前的灰尘不画，由前奏自己画下落的过程。"""
    pos, size, land = dust_layout()
    on = t >= land
    if alpha is not None:
        on &= np.asarray(alpha) > 0.002
    if not on.any():
        return []
    a = np.ones(N_DUST) if alpha is None else np.asarray(alpha, float)
    u = np.clip((t - land) / 0.35, 0, 1)
    glow = (1 - u) ** 2
    speck = np.array([0.30, 0.27, 0.23])
    col = speck[None, :] * (1 - glow[:, None]) + np.array([1.4, 1.3, 1.1])[None, :] * glow[:, None]
    cols = np.c_[col, np.ones(N_DUST) * 0.85][on] * a[on, None]
    cols[:, 3] = 0.85 * a[on]
    P = np.c_[pos[on], np.full(on.sum(), z)]
    dot = cached("handoff_dot", lambda: __import__("engine").dot_atlas(64, 0.3))
    return [Particles(dot, P, size[on], None, cols, blend="over", group="past")]


def paper_cam():
    """交接时刻的镜头（静止）。"""
    return FlatCam([(T_PAPER, *PAPER_CAM)])


def paper_frame(t):
    """27.0 秒的整帧：纸、光和落定的灰尘。"""
    cam, _ = paper_cam()(t)
    return FrameSpec(cam, paper_items(t) + dust_items(t), grade=GRADE_PAST)


if __name__ == "__main__":
    from flatcam import sheet
    out = Path(__file__).resolve().parents[2] / "renders" / "handoff_check.png"
    which = sys.argv[1] if len(sys.argv) > 1 else "paper"
    fn = {"paper": paper_frame, "point": point_frame, "white": white_frame, "dark": dark_frame}[which]
    sheet(fn, [26.0, 26.5, 27.0] if which == "paper" else [T_POINT], str(out), size=(960, 540))
