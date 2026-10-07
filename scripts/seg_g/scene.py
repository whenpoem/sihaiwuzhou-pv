"""间奏二（151.3333–164.9333 秒）：从今天一路穿过所有层，坠到最深处，落在桥段的翻板场地上。

构思里"越往深处越早"在这里一次走完：镜头朝下坠落，前面各段的画面一层层迎面而来，每层在一个小节首拍上被撕开，
镜头从破口穿过去，进入更早的一层；层与层的间距越往后越大，而每层都占一个小节，所以速度持续加快。
每层画面下面压着一张印着旧字的旧纸（poster.py），画面撕开后先露出旧字，旧纸随后也被撕开（字下有字）。
最后一层是主歌二的锁孔，镜头不撕开它，而是从锁孔里穿过去；穿过以后减速，落在桥段场地的上方，交给桥段。

每一层是一整幅画面大小的平面，贴图是那一段渲染出来的静帧（renders/layers/*.png，由 make_layers.py 生成），
所以穿过的每一层都和观众前面看到的画面一模一样。层的平面正对镜头，镜头只沿 -z 下坠并缓慢滚转。

坐标直接用桥段（seg_h/scene.py）的世界坐标：+x 向右、+y 向画面上方，镜头朝 -z 往下看，桥段场地在 z = 0。
各层叠在场地正上方，第 k 层在 z = Z[k]；镜头经过第 k-1 层时，第 k 层恰好铺满画面。落定时的镜头位置、视角
（30 度）与桥段第一帧的镜头完全相同，最后一秒画面里的场地就是桥段的场地本身（seg_h.items），交接没有接缝。
"""
import importlib.util
import math
import sys
from pathlib import Path

import numpy as np
from scipy.interpolate import CubicHermiteSpline, PchipInterpolator

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "style"))
sys.path.insert(0, str(HERE.parent / "film"))
import look  # noqa: E402
import plan  # noqa: E402
from plan import BAR  # noqa: E402
from engine import Cam, FrameSpec, Plane, Tex, TextPlane, register_material  # noqa: E402
from flatcam import cached, ease, ramp, run  # noqa: E402
import poster as P  # noqa: E402


def _load_bridge():
    path = HERE.parent / "seg_h" / "scene.py"
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location("pv_seg_h_scene", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


HB = _load_bridge()

ROOT = HERE.parents[1]
LAYER_DIR = ROOT / "renders" / "layers"
T0, T1 = 9080 / 60, 9896 / 60
FOV = 30.0                                  # 与桥段相同
K = 1.0 / (2.0 * math.tan(math.radians(FOV / 2)))
ASPECT = 16 / 9

# 依次穿过的层：(贴图名, 穿过的时刻, 旧字, 样式)。样式：0 撕纸，1 烧穿，2 碎裂，3 从锁孔里穿过（不撕开）。
# 顺序按年代由近及远：今天的白帆与城市，主歌一的电视，第一层的被单，副歌一的标语墙，第二层的雨夜与报纸字栏的海，
# 第三层的锁孔。旧字一栏只作说明，画面里的旧字印在 poster.py 的旧纸上。
LAYERS = [
    ("sail", BAR(89, 2.5), "希望寄託在你們身上", 0),
    ("city", BAR(90), "", 2),
    ("tv", BAR(91), "形勢大好　不是小好", 0),
    ("sheets", BAR(92), "東方紅　太陽升", 1),
    ("wall", BAR(93), "不管風吹浪打", 0),
    ("rain", BAR(94), "", 0),
    ("newspaper", BAR(95), "歸根結底是你們的", 1),
    ("keyhole", BAR(96), "", 3),
]
GAPS = [6.0, 10.0, 16.0, 22.0, 28.0, 34.0, 42.0, 50.0]          # 相邻两层的间距，越往深处越大
T_LAND = T1                                                     # 落定在桥段场地上方


def _land():
    """落定时的镜头：桥段第一帧的镜头眼睛位置。"""
    cam, _ = HB.camera(T_LAND)
    return np.array(cam.eye, float)


EYE_LAND = _land()
OX, OY = (float(v) for v in HB.CAM.state(163.5)[:2])     # 各层的中心：桥段镜头在交接前 1.4 秒的画面中心
DESCENT = 24.0                                           # 穿过锁孔以后再下降的距离，镜头在这一段里减速


def layer_z():
    z, out = float(EYE_LAND[2]) + DESCENT, []
    for g in reversed(GAPS[1:]):
        out.append(z)
        z += g
    out.append(z)
    return list(reversed(out))


Z = layer_z()
Z_START = Z[0] + GAPS[0]


def _curve():
    """镜头高度：在各层的时刻正好穿过该层（PCHIP）；穿过锁孔以后用一段三次 Hermite 曲线减速，
    落定时的高度和下降速度与桥段的镜头一致。"""
    keys = [(T0, Z_START), (T0 + 0.25, Z_START - 0.25)] + [(tk, z) for (_, tk, _, _), z in zip(LAYERS, Z)]
    k = np.array(keys)
    pc = PchipInterpolator(k[:, 0], k[:, 1])
    tk, zk = k[-1]
    s0 = float(pc.derivative()(tk))
    dt = 1 / 120
    s1 = (HB.camera(T_LAND + dt)[0].eye[2] - HB.camera(T_LAND - dt)[0].eye[2]) / (2 * dt)
    tail = CubicHermiteSpline([tk, T_LAND], [zk, float(EYE_LAND[2])], [s0, s1])
    return pc, tail, tk


def eye_z(t):
    pc, tail, tk = cached("g_cam", _curve)
    t = min(max(t, T0), T_LAND)
    return float(pc(t)) if t <= tk else float(tail(t))


def eye_vz(t):
    d = 1 / 240
    return (eye_z(t + d) - eye_z(t - d)) / (2 * d)


def roll(t):
    """坠落中镜头缓慢滚转，越往深处转得越快一点，穿过锁孔之前回正。"""
    u = float(ease(ramp(t, T0, 159.0)))
    back = float(ease(ramp(t, 160.5, LAYERS[-1][1] - 0.3)))
    return 9.0 * u * (1 - back)


def cam_xy(t):
    """画面中心：交接前 1.4 秒起跟着桥段的镜头极慢地横移，之前停在各层的中心。"""
    if t <= 163.5:
        return OX, OY
    x, y = HB.CAM.state(t)[:2]
    return float(x), float(y)


def camera(t):
    ze = eye_z(t)
    x, y = cam_xy(t)
    r = math.radians(roll(t))
    return Cam(eye=(x, y, ze), target=(x, y, ze - 10.0), up=(-math.sin(r), math.cos(r), 0.0), fov=FOV,
               near=0.02, far=2000.0)


# ---------------------------------------------------------------- 层的贴图

def layer_tex(name):
    """renders/layers/{name}.png；文件还没有时用占位：一张深色带层名的纸。"""
    def make():
        f = LAYER_DIR / f"{name}.png"
        if f.exists():
            from PIL import Image
            return Tex(np.asarray(Image.open(f).convert("RGB"), np.float32) / 255.0)
        rng = np.random.default_rng(abs(hash(name)) % 1000)
        h, w = 540, 960
        base = rng.uniform(0.08, 0.3, 3)
        img = np.ones((h, w, 3), np.float32) * base
        return Tex(img)
    return cached(f"g_layer_{name}", make)


register_material("tear", """
uniform vec2 hc;            // 破口中心（世界坐标）
uniform float s0;           // 长度单位：撕开开始时画面高度的一半（世界单位）
uniform float radius;       // 破口半径（以 s0 为 1）
uniform float style;        // 0 撕纸，1 烧穿，2 碎裂
uniform float seed;
uniform vec3 edge_col;
// 玻璃碎裂的破口：9 个角点，角度均匀、半径随机，角点之间连直线，所以破口是不规则的多边形
float poly_R(float a, int sd) {
    const int N = 9;
    float stp = 6.2831853 / float(N);
    float ph = mod(a + 6.2831853 * 4.0, 6.2831853);
    int i = int(floor(ph / stp));
    float fl = ph - float(i) * stp;
    float r0 = 0.55 + 0.9 * rnd(ivec2(i, 0), sd);
    float r1 = 0.55 + 0.9 * rnd(ivec2((i + 1) % N, 0), sd);
    return r0 * r1 * sin(stp) / (r0 * sin(fl) + r1 * sin(stp - fl));
}
vec4 material(vec4 base) {
    // 破口按世界坐标计算，画面和压在它下面的旧纸用同一个形状，只是半径不同
    vec2 p = (v_wpos.xy - hc) / s0;
    float th = seed * 0.9;
    p = mat2(cos(th), -sin(th), sin(th), cos(th)) * p;
    p.x /= 1.35;
    float a = atan(p.y, p.x);
    float r = length(p);
    // 角度方向上的起伏用在圆周上取样的噪声，首尾相接。大的豁口和中等的撕痕随破口一起放大；
    // 细的锯齿用固定的绝对尺度，破口变大时不会被拉成长刺
    vec2 cs = vec2(cos(a), sin(a));
    float n = vnoise(cs * 1.6 + seed, 3) * 0.62 + vnoise(cs * 5.0 - seed, 4) * 0.38;
    float jag = style > 1.5 ? (abs(fract(a * 1.9 + seed) - 0.5) * 0.6 + n * 0.4) : n;
    float fine = vnoise(cs * 40.0 + seed * 2.0, 5) * 0.6 + vnoise(cs * 130.0 - seed, 6) * 0.4;
    float R = radius * (0.55 + 0.9 * jag) + 0.035 * (fine - 0.5) * min(radius * 4.0, 1.0);
    int sd = int(seed * 13.0);
    if (style > 1.5) R = radius * poly_R(a, sd);
    float d = r - R;                          // 大于 0 在破口外（纸还在）
    float aa = fwidth(d) * 1.5 + 0.002;
    float on = step(0.002, radius);
    vec2 rad_dir = r * vec2(0.6, 0.8);
    vec3 col = base.rgb;
    float alpha;
    if (style < 0.5) {
        // 撕纸：纸边伸出一些沿径向的短纤维，半透明；纸芯露出一圈白边，宽窄沿边缘变化，
        // 有的地方撕出一条斜的宽白边，有的地方几乎没有
        float fibr = vnoise(cs * 260.0 + rad_dir * 22.0 + seed, 7);
        float fuzz = 0.016 * smoothstep(0.5, 0.9, fibr) * on;
        alpha = smoothstep(-aa, aa, d + fuzz) * mix(0.75, 1.0, smoothstep(-aa, aa, d));
        float wband = 0.005 + 0.045 * smoothstep(0.35, 0.85, vnoise(cs * 3.2 + seed * 3.0, 8));
        float inband = (1.0 - smoothstep(wband * 0.6, wband * 1.2 + aa, d)) * on;
        float tex = vnoise(cs * 600.0 + rad_dir * 60.0, 9);
        vec3 white = vec3(0.93, 0.90, 0.84) * (0.80 + 0.28 * tex);
        // 白边外侧是纸被撕起时翘起的一道浅影
        float lift = exp(-max(d - wband, 0.0) / 0.02) * (1.0 - inband) * on;
        col = mix(col * (1.0 - 0.25 * lift), white, inband);
    } else if (style < 1.5) {
        // 烧穿：一圈焦痕向外由黑褐渐淡成焦黄，紧贴破口是一道细的余烬，只有一段段发亮
        alpha = smoothstep(-aa, aa, d);
        float scorch = exp(-max(d, 0.0) / (0.07 + 0.05 * n)) * on;
        float toast = exp(-max(d, 0.0) / (0.20 + 0.08 * n)) * on;
        col *= mix(vec3(1.0), vec3(0.78, 0.62, 0.42), toast);
        col *= 1.0 - 0.9 * scorch;
        float glow = smoothstep(0.35, 0.75, vnoise(cs * 11.0 + seed * 4.0, 7))
                   * (0.7 + 0.3 * vnoise(cs * 90.0 - seed, 10));
        float band = exp(-max(d, 0.0) / (0.006 + 0.004 * n)) * on;
        col += edge_col * band * (0.15 + 0.85 * glow);
    } else {
        // 玻璃碎裂：破口外先裂出放射状和两圈环状的细裂纹，裂纹比破口跑得快；破口的直边上有一道亮边
        alpha = smoothstep(-aa, aa, d);
        float clen = (0.25 + 2.6 * radius) * on;
        float crack = 0.0;
        for (int j = 0; j < 12; j++) {
            float b = float(j) * 0.5235988 + (rnd(ivec2(j, 7), sd) - 0.5) * 0.35;
            vec2 dir = vec2(cos(b), sin(b));
            float along = dot(p, dir);
            float off = abs(dir.x * p.y - dir.y * p.x) + 0.004 * (vnoise(vec2(along * 40.0, float(j)), 11) - 0.5);
            float lw = 0.0025 + 0.0015 * rnd(ivec2(j, 9), sd);
            crack = max(crack, exp(-off / lw) * step(0.0, along) * smoothstep(clen, clen * 0.75, along));
        }
        for (int k = 1; k <= 2; k++) {
            float rr = (0.12 + radius) * (1.0 + 0.55 * float(k)) * poly_R(a + float(k), sd + k);
            float vis = smoothstep(rr * 1.05, rr * 0.9, clen);
            crack = max(crack, exp(-abs(r - rr) / 0.003) * vis * on);
        }
        col = mix(col, vec3(0.92, 0.95, 1.0), crack * 0.75 * step(0.0, d));
        float band = exp(-max(d, 0.0) / 0.006) * on;
        col += vec3(0.8, 0.85, 0.9) * band * 0.8;
    }
    return vec4(col * alpha * base.a, alpha * base.a);
}
""", defaults={"hc": (0.0, 0.0), "s0": 1.0, "radius": 0.0, "style": 0.0, "seed": 0.0, "edge_col": (1.6, 0.6, 0.2)})


# 撕开的节奏（秒，以镜头穿过这一层的时刻 tk 为准，x = tk − t）。压着旧纸的层分三步：画面在 x = 0.80–0.55 撕开，
# 露出整张旧纸；旧纸完整停留到 x = 0.25，旧字在这 0.3 秒里读得清；随后旧纸撕开，镜头穿过。没有旧纸的层只撕一次，
# 在 x = 0.40–0.15。第一层（副歌二的白帆）在间奏二第一拍就撕开。
PIC_SPAN = 0.25
POSTER_HOLD = (0.55, 0.25)
POSTER_SPAN = 0.20
PIC_R, POSTER_R = 3.0, 1.0      # 撕开结束时的破口半径（以 s0 为 1），此时破口已超出画面


def tear_times(i):
    """(画面开始撕开的时刻, 旧纸开始撕开的时刻或 None)。"""
    name, tk = LAYERS[i][0], LAYERS[i][1]
    if i == 0:
        return T0 + 0.02, None                  # 白帆上本来印着旧字，不再垫旧纸，第一拍就撕开
    if P.POSTERS.get(name) is not None:
        return tk - 0.80, tk - POSTER_HOLD[1]
    return max(tk - 0.40, T0 + 0.02), None


def grow(t, t0, span, rmax, pw):
    """破口半径：先是一道小口，随后迅速扯开；t0 + span 时达到 rmax，之后继续扩大。"""
    w = (t - t0) / span
    return 0.0 if w <= 0 else rmax * min(w, 1.6) ** pw


def tear_geom(i):
    """第 i 层撕开的尺度和位置：s0 是画面开始撕开时画面高度的一半（世界单位），破口中心略偏离画面中心，每层不同。"""
    def make():
        z = Z[i]
        s0 = (eye_z(tear_times(i)[0]) - z) / (2 * K)
        seed = i * 7.3
        return s0, (OX + s0 * 0.15 * math.sin(seed * 1.3), OY + s0 * 0.10 * math.cos(seed * 0.7))
    return cached(f"g_tear_{i}", make)


def poster_h(i):
    """旧纸平面的高度：旧纸完整停留的中点，两行旧字约占画面高度的六成。"""
    tk, z = LAYERS[i][1], Z[i]
    d = eye_z(tk - sum(POSTER_HOLD) / 2) - z
    return 0.6 / (P.CHAR_H * (2 + P.LINE_GAP)) * d / K


def poster_tex(name):
    def make():
        a = P.poster(name)
        return None if a is None else Tex(a)
    return cached(f"g_poster_{name}", make)


# 锁孔那一层取自主歌二锁片的特写（106.12 秒）。锁孔在 3840 × 2160 的画面里是圆头（圆心 (1919, 1240)，
# 半径约 298 像素）接一段向下变宽的窄槽；这里按量得的尺寸画成矢量形状挖空，近看边缘也清楚。
# 平面整体上移，让锁孔的圆心正对镜头的路线，镜头就从锁孔里穿过去，与主歌二"穿过锁孔"前后呼应。
KH_C = (1919 / 3840, 1240 / 2160)
KH_R = 292.0
KH_SLOT = ((1440, 290.0), (2300, 440.0))          # 窄槽：(y, 宽度)，像素
KH_DY = KH_C[1] - 0.5                              # 圆心低于画面中心的量（以画面高为 1）


def keyhole_path():
    def make():
        import skia
        path = skia.Path()
        path.addOval(skia.Rect.MakeLTRB(KH_C[0] - KH_R / 3840, KH_C[1] - KH_R / 2160,
                                        KH_C[0] + KH_R / 3840, KH_C[1] + KH_R / 2160))
        (y0, w0), (y1, w1) = KH_SLOT
        cx = KH_C[0]
        path.addPoly([skia.Point(cx - w0 / 2 / 3840, y0 / 2160), skia.Point(cx + w0 / 2 / 3840, y0 / 2160),
                      skia.Point(cx + w1 / 2 / 3840, y1 / 2160), skia.Point(cx - w1 / 2 / 3840, y1 / 2160)], True)
        return path
    return cached("g_keyhole_path", make)


def keyhole_items(name, z, H):
    """锁孔层：挖空锁孔的画面，后面叠五层同形状、逐渐变暗的铜色薄片，穿过时看得出锁孔的深度。"""
    cy = H * KH_DY
    items = [Plane(layer_tex(name), center=(OX, OY + cy, z), size=(H * ASPECT, H), mask=keyhole_path(), group="past")]
    for j in range(1, 6):
        k = 1.0 - j / 6.0
        col = (0.05 + 0.16 * k, 0.04 + 0.11 * k, 0.025 + 0.05 * k)
        items.append(Plane(None, center=(OX, OY + cy, z - j * 0.035 * H), size=(H * ASPECT, H), mask=keyhole_path(),
                           color=col, group="past"))
    return items


def layers(t):
    items = []
    ze = eye_z(t)
    for i, ((name, tk, old, style), z) in enumerate(zip(LAYERS, Z)):
        if ze < z - 0.01:                     # 已经穿过
            continue
        gap = GAPS[i]
        H = gap / K * (1.0 if i == 0 else 1.6)   # 镜头在上一层时这一层铺满画面；滚转时四角不露边
        dist = ze - z
        if style == 3:
            items += keyhole_items(name, z, H)
            if dist > gap * 1.05:
                break
            continue
        s0, hc = tear_geom(i)
        ta, tp = tear_times(i)
        uni = {"hc": hc, "s0": s0, "style": float(style), "seed": float(i * 7.3)}
        # 字下有字：画面下面压着一张印着旧字的旧纸，画面撕开后先露出它，稍后它也被撕开。
        # 两张纸几乎重合，渲染器会把它们当作同一个平面按加入顺序绘制，所以编成一组，先画旧纸、再画画面
        key = f"g_layer_{i}"
        pt = poster_tex(name)
        if pt is not None and t > ta:
            hs = poster_h(i)
            items.append(Plane(pt, center=(hc[0], hc[1], z - 0.004), size=(hs * ASPECT, hs), material="tear",
                               uniforms=dict(uni, radius=grow(t, tp, POSTER_SPAN, POSTER_R, 1.6)), group="past",
                               stack=key))
        items.append(Plane(layer_tex(name), center=(OX, OY, z), size=(H * ASPECT, H), material="tear",
                           uniforms=dict(uni, radius=grow(t, ta, PIC_SPAN, PIC_R, 1.8)), group="past", stack=key))
        if dist > gap * 1.05:
            break                              # 更远的层被这一层挡住
    # 桥段场地：锁孔成为最前面的一层以后，透过锁孔看得见下面的场地，用的就是桥段自己的元素
    if ze < Z[-2]:
        items += HB.items(max(t, 163.5))
    return items


# ---------------------------------------------------------------- 撕下的纸片

def scrap_shapes():
    """八种碎纸片的形状（256 × 128，1 保留）：狭长、有棱角的撕条，边上有细锯齿。每种形状另有一张略大一圈的
    遮罩，用来在纸片背后衬出撕开处露出的白色纸芯（烧焦的碎片衬的是余烬的光）。"""
    def make():
        import skia
        from scipy.ndimage import gaussian_filter, grey_dilation
        rng = np.random.default_rng(91)
        out = []
        for k in range(8):
            n = int(rng.integers(4, 7))
            ang = np.sort(rng.uniform(0, 2 * math.pi, n) + np.linspace(0, 2 * math.pi, n, endpoint=False)) % (2 * math.pi)
            ang = np.sort(ang)
            rad = rng.uniform(0.6, 1.0, n)
            pts = []
            for j in range(n):
                a0, a1 = ang[j], ang[(j + 1) % n] + (2 * math.pi if j == n - 1 else 0)
                for s in np.linspace(0, 1, 9, endpoint=False):
                    a = a0 + (a1 - a0) * s
                    # 两个角点之间连直线，再加细锯齿，形成有棱角的撕边
                    p0 = np.array([math.cos(a0), math.sin(a0)]) * rad[j]
                    p1 = np.array([math.cos(a1), math.sin(a1)]) * rad[(j + 1) % n]
                    q = p0 * (1 - s) + p1 * s
                    q *= 1 + rng.normal(0, 0.03)
                    pts.append((128 + 120 * q[0], 64 + 58 * q[1]))
            path = skia.Path()
            path.moveTo(*pts[0])
            for q in pts[1:]:
                path.lineTo(*q)
            path.close()
            arr = np.zeros((128, 256), np.uint8)
            srf = skia.Surface.MakeRasterDirect(skia.ImageInfo.MakeA8(256, 128), arr)
            srf.getCanvas().drawPath(path, skia.Paint(AntiAlias=True, Color=skia.Color4f(1, 1, 1, 1)))
            del srf
            m = arr.astype(np.float32) / 255
            fuzz = gaussian_filter(rng.normal(0, 1, m.shape).astype(np.float32), 0.7)
            dil = grey_dilation(m, size=(7, 7))
            rim = np.clip(dil + 0.6 * fuzz * (grey_dilation(m, size=(11, 11)) > 0.01) * (m < 0.5), 0, 1)
            rim = gaussian_filter(rim, 0.8)
            out.append((Tex(np.clip(gaussian_filter(m, 0.6), 0, 1)), Tex(rim)))
        return out
    return cached("g_scrap_shapes3", make)


def scrap_list(i):
    """第 i 层撕开时扯下的纸片：在破口边缘经过时脱落，向外、向镜头飞来，一边翻飞。一半来自画面，一半来自旧纸。"""
    def make():
        rng = np.random.default_rng(300 + i)
        has_poster = poster_tex(LAYERS[i][0]) is not None
        out = []
        for k in range(12):
            src = "poster" if (has_poster and k % 2) else "pic"
            out.append(dict(src=src, a=rng.uniform(0, 2 * math.pi), r0=rng.uniform(0.12, 1.1),
                            size=rng.uniform(0.09, 0.26), asp=rng.uniform(1.6, 2.8), shape=int(rng.integers(0, 8)), vr=rng.uniform(0.6, 1.8),
                            vz=rng.uniform(0.08, 0.35), spin=rng.uniform(-260, 260), flut=rng.uniform(5, 11),
                            amp=rng.uniform(35, 70), ph=rng.uniform(0, 6.3), roll0=rng.uniform(0, 360)))
        return out
    return cached(f"g_scraps_{i}", make)


def scraps(t):
    items = []
    ze = eye_z(t)
    shapes = scrap_shapes()
    for i, ((name, tk, old, style), z) in enumerate(zip(LAYERS, Z)):
        if style == 3:
            continue
        ta, tp = tear_times(i)
        if t < ta or t > tk + 0.6:
            continue
        s0, hc = tear_geom(i)
        v_cam = -eye_vz(ta)                       # 撕开时镜头接近这一层的速度（世界单位/秒）
        gap = GAPS[i]
        H = gap / K * (1.0 if i == 0 else 1.6)
        th = i * 7.3 * 0.9
        c, s = math.cos(-th), math.sin(-th)
        for sc in scrap_list(i):
            # 破口边缘经过这块纸片所在位置的时刻（grow 的反函数）
            if sc["src"] == "poster":
                t0 = tp + POSTER_SPAN * (sc["r0"] / POSTER_R) ** (1 / 1.6)
            else:
                t0 = ta + PIC_SPAN * (sc["r0"] / PIC_R) ** (1 / 1.8)
            if t < t0:
                continue
            dt = t - t0
            # 破口坐标里的位置换回世界坐标（与材质里的旋转、拉长相反）
            px, py = sc["r0"] * math.cos(sc["a"]) * 1.35, sc["r0"] * math.sin(sc["a"])
            wx, wy = c * px - s * py, s * px + c * py
            dn = math.hypot(wx, wy) + 1e-6
            out = sc["vr"] * s0 * (1 - math.exp(-dt / 0.5)) * 0.5
            if sc["src"] == "poster" and sc["r0"] > 0.9:
                continue                          # 旧纸撕开时画面已经很近，外圈的纸片在画面以外
            x0, y0 = hc[0] + s0 * wx, hc[1] + s0 * wy
            x, y = x0 + wx / dn * out, y0 + wy / dn * out
            zz = z + 0.01 + sc["vz"] * v_cam * 0.4 * (1 - math.exp(-dt / 0.4))
            if zz > ze - 0.05:
                continue                          # 已经从镜头旁飞过
            sz = sc["size"] * s0
            yaw = sc["amp"] * math.sin(sc["flut"] * dt + sc["ph"])
            pitch = sc["amp"] * 0.8 * math.sin(sc["flut"] * 0.83 * dt + sc["ph"] * 1.7)
            roll_ = sc["roll0"] + sc["spin"] * dt
            if sc["src"] == "poster":
                tex = poster_tex(name)
                hs = poster_h(i)
                pw, ph = hs * ASPECT, hs
                cu, cv = (x0 - hc[0]) / pw + 0.5, 0.5 - (y0 - hc[1]) / ph
                su, sv = sz / pw, sz / ph
            else:
                tex = layer_tex(name)
                pw, ph = H * ASPECT, H
                cu, cv = (x0 - OX) / pw + 0.5, 0.5 - (y0 - OY) / ph
                su, sv = sz / pw, sz / ph
            w_, h_ = sz * sc["asp"], sz
            su = w_ / pw
            # 贴近镜头的碎片在占满画面之前淡出
            a = min(1.0, dt / 0.04) * float(np.clip((ze - zz) / (w_ * 2.5) - 0.3, 0.0, 1.0))
            if a <= 0.0:
                continue
            m, rim = shapes[sc["shape"]]
            key = f"scrap_{i}_{id(sc)}"
            uvr = (cu - su / 2, cv - sv / 2, cu + su / 2, cv + sv / 2)
            if style == 2:
                # 玻璃碎片：带着这一块的画面，略透明，边上一道亮边
                items.append(Plane(tex, center=(x, y, zz), size=(w_, h_), rot=(yaw, pitch, roll_), uv=uvr, mask=m,
                                   color=(1.08, 1.1, 1.14), opacity=a * 0.85, group="past", stack=key))
                items.append(Plane(None, center=(x, y, zz + 0.001), size=(w_, h_), rot=(yaw, pitch, roll_), mask=rim,
                                   color=(0.75, 0.8, 0.85), opacity=a * 0.35, blend="add", group="past", stack=key))
            elif style == 1:
                # 烧焦的碎片：焦黑的纸，边上一圈余烬的光
                items.append(Plane(None, center=(x, y, zz), size=(w_, h_), rot=(yaw, pitch, roll_), mask=rim,
                                   color=(1.5, 0.55, 0.16), opacity=a * 0.8, blend="add", group="past", stack=key))
                items.append(Plane(tex, center=(x, y, zz), size=(w_, h_), rot=(yaw, pitch, roll_), uv=uvr, mask=m,
                                   color=(0.16, 0.12, 0.10), opacity=a, group="past", stack=key))
            else:
                # 撕下的纸片：背后衬一圈撕开处露出的白色纸芯
                items.append(Plane(None, center=(x, y, zz), size=(w_, h_), rot=(yaw, pitch, roll_), mask=rim,
                                   color=(0.90, 0.87, 0.80), opacity=a, group="past", stack=key))
                items.append(Plane(tex, center=(x, y, zz), size=(w_, h_), rot=(yaw, pitch, roll_), uv=uvr, mask=m,
                                   opacity=a, group="past", stack=key))
    return items


# 层的贴图已经是各段调过色的画面，这里只用中性的调色（不再提亮、不再加暖、不压高光），加上随帧变化的颗粒、
# 划痕和暗角；越往深处，整体越暗、越偏红
GRADE = {"past": {"exposure": 1 / 1.08, "gain": 1.0, "lift": 0.0, "shoulder": 0.0, "warmth": (1.0, 1.0, 1.0), "sat": 1.0, "halation": 0.7,
                  "vignette": 0.42, "grain": 0.028, "scratch": 0.6, "weave": 0.6}}


# 引擎的暗角是 x *= 1.08 − vignette·r^2.8，暗角为 0 时整幅画面也提亮 8%，所以曝光取 1/1.08 抵消。
# 第一层是副歌二的画面，属于"今天"一组，本来没有暗角；按下面的参数，第一帧与副歌二的最后一帧逐像素接近
IDENTITY = {"exposure": 1 / 1.08, "halation": 0.0, "shoulder": 0.0, "lift": 0.0, "gain": 1.0,
            "warmth": (1.0, 1.0, 1.0), "sat": 1.0, "vignette": 0.0, "grain": 0.0, "scratch": 0.0, "weave": 0.0}


def _mix(a, b, u):
    """两套过去层调色按 u 混合；缺的参数取引擎的默认值。"""
    from engine.grade import DEFAULTS
    d = DEFAULTS["past"]
    out = {}
    for k in set(a) | set(b):
        va, vb = a.get(k, d.get(k)), b.get(k, d.get(k))
        if isinstance(va, (tuple, list)):
            out[k] = tuple(float(x) + (float(y) - float(x)) * u for x, y in zip(va, vb))
        else:
            out[k] = float(va) + (float(vb) - float(va)) * u
    return out


def grade(t):
    """越往深处越暗、越偏红；穿过锁孔前后的 0.8 秒里过渡到桥段的调色（锁孔四周是暗的铜，画面里主要是场地），
    落定时与桥段第一帧完全相同。"""
    # 第一帧与副歌二最后一帧完全相同：贴图里已经是副歌二调好的画面，这里不加任何处理；
    # 到第一次撕开时逐渐加上旧片的颗粒、划痕、暗角和光晕
    g = _mix(IDENTITY, GRADE["past"], float(ease(ramp(t, T0, LAYERS[0][1]))))
    k = ramp(t, T0, LAYERS[-1][1])
    g["warmth"] = (1.0 + 0.10 * k, 1.0 - 0.22 * k, 1.0 - 0.32 * k)
    g["gain"] = 1.0 - 0.30 * k
    w = float(ease(ramp(t, LAYERS[-1][1] - 0.3, LAYERS[-1][1] + 0.5)))
    if w > 0:
        g = _mix(g, HB.grade(max(t, 163.5))["past"], w)
    return {"past": g}


def frame(t):
    cam = camera(t)
    return FrameSpec(cam, layers(t) + scraps(t), grade=grade(t))


def SUBFRAMES(t):
    """运动模糊需要的子帧数：按画面边缘每帧的位移计算，约每 8 像素一个子帧。镜头朝前一层推进时，画面边缘的
    位移约为 960 × 下降速度 /（60 × 到前一层的距离）像素。"""
    ze = eye_z(t)
    ahead = [ze - z for z in Z if z < ze - 0.01] or [ze]
    d = max(min(ahead), 0.5)
    px = 960.0 * abs(eye_vz(t)) / (60.0 * d)
    return int(min(16, max(2, math.ceil(px / 8.0))))


if __name__ == "__main__":
    run(frame, "间奏二", T0, T1, ROOT / "renders" / "seg_g", subframes=SUBFRAMES)
