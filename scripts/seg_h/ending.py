"""结尾（188.5 秒到片尾）：回到片头那张旧纸上，窗外城市夜景的灯光照着纸面，钢笔写下最后一句。

L39 唱完，阳光在约 0.2 秒里暗下去；全暗的那一刻换到夜里的书桌。窗外城市的灯光在"你"字之前亮起：冷白的 LED
光透过窗格斜照在纸上，窗格的影子横过纸面，下方混着一点路灯的暖光。纸就是片头和主歌一的那张旧纸
（handoff.paper_items 的照片与纤维纹理），左边是片头翻过的那叠照片。

L40 用主歌一 L01 同一种钢笔字（霞鹜文楷，墨迹由 seg_a2 的笔画与出墨模型生成），写成两行，用简体，墨是刚写下的
蓝黑色。这一句的"字下有字"是纸上的压痕：以前垫在上面的纸上写过的旧字，在这张纸上留下凹印，只有斜照的窗光下
才显出阴影，不着颜色，要细看才认得出。

音乐在第 113 小节首拍骤停，镜头在同一刻停住。此后画面里只有一件事在发生：墨迹由蓝黑慢慢干成墨褐，和主歌一的
旧字是同一种颜色。随后窗外的 LED 熄灭，只剩路灯的暖光，暖光也暗下去，全黑。
"""
import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import gaussian_filter

HERE = Path(__file__).resolve().parent
SCRIPTS = HERE.parent

from common import T, cached, disk_cached, smooth, look  # noqa: E402
import handoff as HO  # noqa: E402
from flatcam import FlatCam  # noqa: E402
from engine import FrameSpec, Plane, Tex, register_material  # noqa: E402

T_SWAP = 188.50                    # 阳光暗尽，换到夜里的书桌
T_LIGHT = (188.50, 188.60)         # 窗外的灯亮起
T_CUT = 11549 / 60                 # 音乐骤停之后的第一帧（192.483），镜头停住
DRY = (192.60, 2.4)                # 墨迹开始变干的时刻、变干所用的时间（墨多处再晚 1.4 秒）
T_LED_OFF = 196.70                 # 窗外的 LED 熄灭
T_WARM_OUT = (197.4, 199.25)       # 路灯的暖光暗下去
L40 = ["你肮脏的习惯", "大概和我一样吧"]
EM = 1.30                          # 字高（世界单位，与 L01 的 1.5 相近）
LINE_GAP = 1.75                    # 行距（em）
X0, Y1 = -3.6, 1.15                # 第一行左端、第一行字框中心的高度
CAM_KEYS = [(T_SWAP, -2.6, 0.15, 14.6), (T_CUT, -2.3, 0.15, 13.6)]


def _load(name, rel):
    """按路径加载别段的模块，避免和本段同名的模块互相顶替。"""
    path = SCRIPTS / rel
    if name in sys.modules:
        return sys.modules[name]
    sys.path.append(str(path.parent))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def ink_module():
    """主歌一的钢笔字（seg_a2/ink.py），它会加载同目录的 strokes 与 mats。"""
    return _load("a2_ink_mod", "seg_a2/ink.py")


def album_module():
    """片头的照片（seg_a1/album.py）；还没有时返回 None。"""
    if not (SCRIPTS / "seg_a1" / "album.py").exists():
        return None
    return _load("a1_album_mod", "seg_a1/album.py")


# ---------------------------------------------------------------- 墨迹：写完以后才变干

def _register_ink():
    IK = ink_module()
    src = sys.modules["mats"].INK
    old = "float dry = 1.0 - exp(-max(age, 0.0) / (0.6 + 1.9 * dens));"
    assert old in src
    src = src.replace(old, "float dry = smoothstep(0.0, 1.0, (u_time - dry_t0 - 1.4 * dens) / dry_dur);")
    src = "uniform float dry_t0;\nuniform float dry_dur;\n" + src
    register_material("end_ink", src, defaults={
        "ink_t0": 0.0, "ink_dur": 0.3, "ink_age": 0.0, "ink_em": 1.0,
        "ink_fresh": (0.035, 0.045, 0.10), "ink_dry": (0.20, 0.13, 0.085), "ink_old": (0.52, 0.40, 0.29),
        "ink_bleed": 0.01, "ink_gain": 1.0, "fib_tile": 0.6, "ink_wipe": (0.0, 0.0),
        "dry_t0": DRY[0], "dry_dur": DRY[1]})
    return IK


def l40_chars():
    """[(字, 字框中心, 转角, 开始时刻, 书写时长)]：按字的元音起点写，每字写满到下一个字之前。"""
    def make():
        IK = cached("end_ink_reg", _register_ink)
        onsets = [T(40, i) for i in range(13)]
        out, k = [], 0
        for li, line in enumerate(L40):
            y = Y1 - li * LINE_GAP * EM
            for j, ch in enumerate(line):
                dy, rot, sc = IK.jitter(f"L40{li}{j}{ch}")
                x = X0 + (j + 0.5) * EM * 1.02
                nxt = onsets[k + 1] if k + 1 < len(onsets) else onsets[k] + 0.42
                dur = float(np.clip(0.9 * (nxt - onsets[k]), 0.2, 0.40))
                out.append((ch, (x, y + dy * EM), rot, onsets[k] - 0.03, dur, sc))
                k += 1
        return out
    return cached("end_l40", make)


def l40_items(t):
    IK = cached("end_ink_reg", _register_ink)
    items = []
    for ch, c, rot, t0, dur, sc in l40_chars():
        if t < t0 - 0.01:
            continue
        p = IK.char_plane(ch, c, EM * sc, t0, dur, rot=rot, ppe=512, bleed=EM * 0.012)
        p.material = "end_ink"
        p.uniforms["ink_fresh"] = (0.030, 0.070, 0.34)
        p.uniforms["ink_dry"] = (0.26, 0.16, 0.085)
        items.append(p)
    return items


# ---------------------------------------------------------------- 窗外的灯光与纸上的压痕

LT_BOX = (-17.0, -9.0, 13.0, 9.0)          # 光照贴图覆盖的纸面范围（世界单位）
LT_PPU = 96                                # 每世界单位的像素数
LIGHT_DIR = np.array([0.86, 0.50])         # 窗光在纸面上的来向（从右上方斜照过来）

INDENTS = [
    # (旧字, 左端 x, 基线 y, 字高, 转角 度)
    ("四海翻騰雲水怒　五洲震盪風雷激", -15.5, 6.6, 0.95, -3.0),
    ("抓革命　促生產", -2.0, 4.4, 1.25, 2.0),
    ("大海航行靠舵手", -14.8, 3.1, 1.00, -1.5),
    ("一萬年太久　只爭朝夕", 1.0, 2.2, 0.85, 4.0),
    ("世界是你們的　也是我們的", -12.0, -2.9, 0.90, 1.0),
    ("東方紅　太陽升", 3.5, -3.6, 1.10, -2.5),
    ("不管風吹浪打　勝似閒庭信步", -15.0, -5.6, 0.80, -4.0),
    ("千萬不要忘記階級鬥爭", -2.5, -6.8, 0.95, 1.5),
    ("全國山河一片紅", 4.0, 6.0, 0.80, -6.0),
    ("換了人間", 7.5, -0.6, 1.05, 3.0),
    ("好像早晨八九點鐘的太陽", -15.8, 0.4, 0.75, 2.5),
    ("引無數英雄競折腰", 0.5, -8.4, 0.85, -1.0),
    ("團結　緊張　嚴肅　活潑", 5.0, 8.2, 0.80, 2.0),
]


def _indent_height():
    """压痕的高度图（凹处为负）：旧字用钢笔字体（霞鹜文楷）写出，按笔画压下去的深浅微有起伏。"""
    import skia
    W = int((LT_BOX[2] - LT_BOX[0]) * LT_PPU)
    H = int((LT_BOX[3] - LT_BOX[1]) * LT_PPU)
    arr = np.zeros((H, W), np.uint8)
    srf = skia.Surface.MakeRasterDirect(skia.ImageInfo.MakeA8(W, H), arr)
    c = srf.getCanvas()
    for text, x, y, h, rot in INDENTS:
        f = look.font("kai", 400, h * LT_PPU * 1.0)
        px, py = (x - LT_BOX[0]) * LT_PPU, (LT_BOX[3] - y) * LT_PPU
        c.save()
        c.translate(px, py)
        c.rotate(-rot)
        c.drawString(text, 0, 0, f, skia.Paint(AntiAlias=True, Color=skia.Color4f(1, 1, 1, 1)))
        c.restore()
    del c, srf
    m = arr.astype(np.float32) / 255
    rng = np.random.default_rng(40)
    press = 0.75 + 0.25 * gaussian_filter(rng.normal(0, 1, (H // 16 + 1, W // 16 + 1)), 2)[
        np.arange(H)[:, None] // 16, np.arange(W)[None, :] // 16]
    return -gaussian_filter(m, 1.6) * np.clip(press, 0.4, 1.2)


def _window_mask(xx, yy):
    """窗光在纸面上的形状：一扇四格窗斜投下来的平行四边形，窗框和十字窗棂留下柔和的影子。"""
    # 窗光坐标：沿来光方向拉长、略斜
    u = (xx - 3.5) * 0.92 + (yy - 0.5) * 0.30
    v = (yy - 0.5) * 0.95 - (xx - 3.5) * 0.12
    half_u, half_v = 11.5, 6.8
    pen = 1.6                                              # 半影宽度（窗离桌面越远越宽）
    inside = (np.clip((half_u - np.abs(u)) / pen + 0.5, 0, 1) * np.clip((half_v - np.abs(v)) / pen + 0.5, 0, 1))
    bar = 0.30                                             # 窗棂宽度（影子边缘随半影变软）
    mull = 1 - np.exp(-(u / bar) ** 2 / 2.5) * 0.62 - np.exp(-(v / bar) ** 2 / 2.5) * 0.62
    return inside * np.clip(mull, 0, 1)


def _night_light():
    """纸面上的光（乘在纸的颜色上）：冷白的窗光、下方一片路灯的暖光、其余是很暗的环境光；压痕只在窗光里显出。
    返回 (LED 窗光, 路灯暖光, 环境光) 三张，结尾分别熄灭。"""
    W = int((LT_BOX[2] - LT_BOX[0]) * LT_PPU)
    H = int((LT_BOX[3] - LT_BOX[1]) * LT_PPU)
    xs = LT_BOX[0] + (np.arange(W) + 0.5) / LT_PPU
    ys = LT_BOX[3] - (np.arange(H) + 0.5) / LT_PPU
    xx, yy = np.meshgrid(xs, ys)
    win = _window_mask(xx, yy)
    # 窗光不均匀：远处楼上的 LED 屏和招牌照进来，颜色有冷有暖、有一块偏青
    rng = np.random.default_rng(7)
    patch = gaussian_filter(rng.normal(0, 1, (H // 24 + 1, W // 24 + 1)), 3.0)
    patch = patch[np.arange(H)[:, None] // 24, np.arange(W)[None, :] // 24]
    patch = gaussian_filter(patch, 12)
    patch = (patch - patch.mean()) / (patch.std() + 1e-6)
    cold = np.array([0.80, 0.90, 1.08], np.float32)
    teal = np.array([0.62, 0.92, 1.0], np.float32)
    k = np.clip(0.5 + 0.35 * patch, 0, 1)[..., None]
    led = win[..., None] * (cold * (1 - k * 0.6) + teal * k * 0.6) * 0.50
    warm_c = np.array([1.0, 0.68, 0.38], np.float32)
    warm = np.exp(-(((xx - 4.0) / 15.0) ** 2 + ((yy + 8.5) / 8.0) ** 2))[..., None] * warm_c * 0.36
    amb = np.ones_like(led) * np.array([0.09, 0.10, 0.13], np.float32)
    # 压痕：凹槽朝着窗光的一壁亮、背着的一壁暗；乘在窗光上，所以只在窗光里看得见
    h = _indent_height()
    gy, gx = np.gradient(h)
    shade = -(gx * LIGHT_DIR[0] - gy * LIGHT_DIR[1]) * LT_PPU * 0.0085
    led = led * np.clip(1.0 + shade, 0.78, 1.22)[..., None]
    warm = warm * np.clip(1.0 + 0.5 * shade, 0.93, 1.07)[..., None]
    return led.astype(np.float32), warm.astype(np.float32), amb.astype(np.float32)


def light_texs():
    def make():
        data = disk_cached("end_night_light_v3", _night_light)
        return [Tex(np.dstack([d, np.ones(d.shape[:2], np.float32)])) for d in data]
    return cached("end_light_texs", make)


SCREEN = [(1.00, 1.00, 1.00), (0.70, 0.95, 1.10), (1.10, 0.92, 0.70), (0.85, 0.90, 1.12), (0.68, 1.02, 1.00),
          (1.05, 1.00, 0.92)]


def screen_color(t):
    """窗外楼上那块大屏此刻的颜色：画面每隔两拍换一次，用 0.25 秒交叉过渡；音乐停时停在当时的颜色。"""
    from common import BAR
    t = min(t, T_CUT)
    beat = (BAR(2) - BAR(1)) / 4
    x = (t - T_SWAP) / (2 * beat)
    i = int(math.floor(x))
    u = float(smooth(x - i, 0.0, 0.25 / (2 * beat)))
    a = np.array(SCREEN[i % len(SCREEN)])
    b = np.array(SCREEN[(i + 1) % len(SCREEN)])
    # 大屏的画面换得比交叉过渡的节奏晚：先停留，再过渡到下一种颜色
    return tuple(a + (b - a) * u)


def light_levels(t):
    """(LED 窗光, 路灯暖光, 环境光) 的强度。"""
    on = float(smooth(t, *T_LIGHT))
    led = on * (1.0 - float(t >= T_LED_OFF))
    warm = on * (1.0 - float(smooth(t, *T_WARM_OUT)))
    amb = on * (1.0 - float(smooth(t, T_WARM_OUT[0], T_WARM_OUT[1] - 0.3)))
    return led, warm, amb


def paper_items(t):
    """旧纸，乘上窗外的灯光（三种光在 end_light 材质里按各自的强度相加）。"""
    base = HO.paper_items(t)[0]
    led, warm, amb = light_levels(t)
    texs = light_texs()
    cx, cy = (LT_BOX[0] + LT_BOX[2]) / 2, (LT_BOX[1] + LT_BOX[3]) / 2
    size = (LT_BOX[2] - LT_BOX[0], LT_BOX[3] - LT_BOX[1])
    return [base, Plane(texs[0], center=(cx, cy, 0.002), size=size, blend="multiply", group="past", stack="paper",
                        material="end_light", uniforms={"warm_tex": texs[1], "amb_tex": texs[2],
                                                         "lv": (led, warm, amb), "shift": 0.35 * min(t, T_CUT),
                                                         "screen": screen_color(t)})]


register_material("end_light", r"""
uniform sampler2D warm_tex;
uniform sampler2D amb_tex;
uniform vec3 lv;
uniform float shift;       // 窗外屏幕画面的变化，音乐停时停住
uniform vec3 screen;       // 窗外大屏此刻的颜色
vec4 material(vec4 base) {
    vec2 w = v_wpos.xy;
    float m = vnoise(w * 0.16 + vec2(shift * 0.9, shift * 0.35), 3) * 0.6 + vnoise(w * 0.07 - vec2(shift * 0.4, 0.0), 5) * 0.4;
    vec3 tint = mix(vec3(0.86, 0.95, 1.08), vec3(1.06, 0.98, 0.90), smoothstep(0.35, 0.75, m));
    vec3 c = texture(u_tex, v_uv).rgb * lv.x * tint * screen * (0.82 + 0.36 * m)
           + texture(warm_tex, v_uv).rgb * lv.y + texture(amb_tex, v_uv).rgb * lv.z;
    return vec4(c, 1.0);
}
""", defaults={"lv": (1.0, 1.0, 1.0), "shift": 0.0, "screen": (1.0, 1.0, 1.0)})


# ---------------------------------------------------------------- 组装

CAM = FlatCam(CAM_KEYS + [(T_CUT + 0.01, *CAM_KEYS[-1][1:]), (200.0, *CAM_KEYS[-1][1:])])

GRADE = {"past": {"halation": 0.5, "lift": 0.012, "gain": 1.25, "shoulder": 0.45, "warmth": (0.97, 1.0, 1.05),
                  "sat": 0.88, "vignette": 0.42, "grain": 0.013, "scratch": 0.0, "weave": 0.0}}


def camera(t):
    return CAM(min(t, T_CUT))


def items(t):
    out = paper_items(t)
    AM = album_module()
    if AM is not None:
        out += AM.pile_items(at_end=True)
    out += l40_items(t)
    return out


def grade(t):
    g = {k: dict(v) for k, v in GRADE.items()}
    out = dict(g)
    out["final"] = {"fade": float(smooth(t, 199.2, 199.5)), "fade_color": (0.0, 0.0, 0.0)}
    return out


def frame(t):
    cam, _ = camera(t)
    return FrameSpec(cam, items(t), grade=grade(t))
