"""H 段：桥段、尾段与结尾（L33–L40，164.9333–199.7654 秒，帧 9896 到片尾 11985）。

桥段是全片最深的一层：一座夜里的旧体育场，场地中央铺着上万块双面翻板，四周是跑道、水泥看台和四座照明灯塔。
交接帧是正上方的俯视，此后镜头一边极慢地横移，一边压低、倾斜：L33 贴着漆面掠过，逆着远端左角的灯光，巨大的
"記"字的笔画向远处延伸、按透视收小，刷痕和板缝在漆面的高光里显出来，"停得住"时几乎停住；L34 地面荡开一道
涟漪，看出是一块块翻板，镜头升高、仍是斜看，翻板一波波翻出一行字，看台、跑道、照明灯依次入画，"到此为止吗"
时翻转停在半途；L35 两拍各翻出一句，镜头在斜上方，看台和灯塔框住整片场地，一条黑色的翻板带横穿全联；L36 起风，
远处天上两次闪电的冷光照亮场地，镜头慢慢转回正上方，"为我"时略微后撤，"吹"字与鼓声同时到来，整片翻板被风
掀起卷成旋风。尾段五个"快"各冲破一层（storm.py），"动物永不停下来"时旋风里的板和字成群奔向远处的光
（herd.py），"浮"字时冲进正午的阳光，尘埃里拼出"永遠愛她"（sun.py），L40 回到今天，最后一句停在旧字的残影上，
音乐骤停后画面停住、淡出，只剩一束光里的一粒尘埃（final.py）。歌词的位置见 lyrics.py。

坐标（世界单位，右手系，+x 向右、+y 向远端，+z 向上，场地在 z = 0 附近）。
  翻板场：360 × 150 块板，格距 1，中心在原点；第 c 列、第 r 行的板心在 x = c − 179.5、y = 74.5 − r
          （第 0 行在远端），板宽 0.975、厚 0.06，转轴离地 z = 0.6。场地覆盖 x ∈ [−180, 180]、y ∈ [−75, 75]。
  地面：z = 0，场地四周 9 单位的土地、20 单位宽的六道煤渣跑道；看台内沿是半宽 232、半高 127、转角半径 49 的
        圆角矩形，台阶向外 45、升高 22（stadium.py）；照明灯在 (±236, ±124, 82)；夜空远景立在 y = 330。
  镜头：竖直视角 30 度。交接帧之前和"为我"之后用平面镜头：画面中心 (x, y)、画面高 H 时，眼睛在 (x, y, H·K)，
        K = 1/(2·tan 15°) = 1.866，朝 −z 看。164.9333 秒（交接帧）镜头在 x = −135.0、y = −38.8、H = 34.0
        （眼睛高 63.44，画面宽 60.4），不滚转，对着"記"字的言字旁；交接帧之前的镜头 CAM 保持不变，供间奏二取用。
        交接帧之后到 177.42 秒用斜看的镜头（BRIDGE_KEYS，见下文"镜头"一节）。

各段共用的接口：camera(t) 返回 (引擎的 Cam, 附加量)；items(t) 返回元素列表；grade(t) 返回调色参数；
frame(t) 只把三者组装成 FrameSpec。items(t) 在 163.5 秒以后都能调用：交接之前它返回静止的整片场地（L33 的巨大
红字，不按画面裁剪），间奏二可以用自己的镜头从上方落到这片场地上；grade(t) 在交接帧之前是过去的标准调色。

    python scene.py preview | sheet 输出.png 秒,秒,... [--size 640x360] [--ss 2] | still 秒 输出.png
"""
import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
# 别的段也有同名的模块（common.py 等）：同一个进程里先加载过它们时（例如 make_layers.py），先移走，再加载本段的
for _n in ("common", "patterns", "cards", "field", "surround", "storm", "herd", "sun", "final", "lightning",
           "stadium", "lyrics", "ending"):
    _m = sys.modules.get(_n)
    if _m is not None and Path(getattr(_m, "__file__", "") or ".").resolve().parent != HERE:
        del sys.modules[_n]
import numpy as np  # noqa: E402

import common as C  # noqa: E402
from common import T, BAR, cached, smooth, look  # noqa: E402
import flatcam  # noqa: E402
from flatcam import FlatCam  # noqa: E402
import handoff  # noqa: E402
from engine import Film, FrameSpec, Overlay  # noqa: E402
from engine.grade import DEFAULTS as GRADE_DEF  # noqa: E402

import field as FD  # noqa: E402
import surround as SR  # noqa: E402
import cards as CD  # noqa: E402
import storm as ST  # noqa: E402
import herd as HD  # noqa: E402
import sun as SN  # noqa: E402
import final as FN  # noqa: E402
import lightning as LT  # noqa: E402
import ending as END  # noqa: E402
import stadium as ST_  # noqa: E402
import lyrics as LY  # noqa: E402

T0 = 9896 / 60                 # 164.9333
T1 = 11986 / 60                # 片尾（渲染到第 11985 帧为止）
GRADE = handoff.GRADE_PAST

# ---------------------------------------------------------------- 镜头
# 交接帧之前用平面镜头 FlatCam（画面中心 x、y 与画面高 H，镜头在 z = H·K 处朝下看场地），交接帧之后到 177.42 秒
# 用斜看的镜头（BRIDGE_KEYS）。"吹"之后镜头被卷进旋风，
# 一路向前（朝 -z）冲破五层，再在阳光里骤然慢下来，L40 停住；这一段的高度 z(t) 另用一条三次 Hermite 曲线给出，
# 好让镜头在冲进阳光的那一刻仍带着全速，随后按指数在约 0.2 秒里慢下来（PCHIP 会在那之前就先减速）。

X33, Y33 = -135.0, -38.8        # L33 镜头贴近"記"字：言字旁的几道长横和"己"的横折
T_PULL = 177.42                 # "为我"后撤的最高点，之后交给风暴的镜头曲线
CAM = FlatCam([
    (163.50, X33 - 2.4, Y33 + 0.3, 34.0),
    (T0, X33, Y33, 34.0),
    (FD.T_STOP, X33 + 4.6, Y33 - 0.4, 33.6),
    (167.30, X33 + 4.6, Y33 - 0.4, 33.6),
    (168.40, -112.0, -30.0, 68.0),
    (FD.W1[0], -90.0, -20.0, 118.0),
    (FD.W1[3], -30.0, -6.0, 212.0),
    (FD.T_MA, 0.0, 0.0, 220.0),
    (172.30, 0.0, 0.0, 226.0),
    (173.50, 0.0, 0.0, 232.0),
    (176.70, 0.0, 0.0, 234.0),
    (T_PULL, 0.0, 0.0, 250.0),
], fov=30.0, near=0.05, far=1500.0)
K = CAM.K

# 交接以后的桥段镜头：围着画面中心对准的地面点（目标点）转动的斜看镜头。五个通道：目标点 x、y，镜头到目标点的
# 距离（对数空间插值），倾角 tilt（0 为正上方俯视，越大越贴近地面），朝向 heading（0 为朝 +y 看，正值向左转；
# 俯视时等于画面的滚转角）。164.9333 秒这一帧与 CAM 完全相同（正上方、x −135、y −38.8、眼睛高 63.44），
# 起步时只带着 CAM 原有的极慢横移，倾角、距离、朝向都从静止开始变化；177.42 秒回到正上方，接风暴的镜头。
#   L33  一边横移一边压低、倾斜，"停得住"时几乎停住，唱完时贴着漆面掠过，逆着远端左角的灯光；
#   L34  升高，仍是低角度斜看，看台、照明灯、跑道依次入画，"到此为止吗"时看台上方露出天；
#   L35  升到斜上方，看台和照明灯框住整片场地，看全联；
#   L36  起风以后慢慢转回正上方，"为我"时略微后撤。
BRIDGE_KEYS = [
    # (时刻, 目标 x, 目标 y, 距离, 倾角, 朝向)
    (T0, X33, Y33, 34.0 * 1.8660254, 0.0, 0.0),
    (165.85, X33 + 1.6, Y33 - 6.5, 54.0, 17.0, 5.0),
    (FD.T_STOP + 0.02, X33 + 3.5, Y33 - 13.0, 47.0, 35.0, 10.0),
    (167.22, X33 + 4.5, Y33 - 14.5, 46.0, 38.0, 11.0),
    (168.25, X33 + 9.0, Y33 - 18.5, 44.0, 59.0, 12.0),
    (168.90, -123.0, -53.0, 60.0, 60.5, 11.0),
    (169.35, -117.0, -43.0, 86.0, 61.5, 9.5),
    (169.85, -100.0, -27.0, 135.0, 62.5, 7.5),
    (170.45, -70.0, -6.0, 225.0, 63.5, 5.0),
    (FD.T_MA, -25.0, 14.0, 400.0, 63.0, 3.0),
    (172.20, 0.0, 18.0, 590.0, 63.5, 1.0),
    (173.40, 0.0, 14.0, 615.0, 61.0, 0.0),
    (173.90, 0.0, 12.0, 605.0, 58.0, 0.0),
    (175.00, 0.0, 7.0, 530.0, 38.0, 0.0),
    (176.10, 0.0, 3.0, 465.0, 18.0, 0.0),
    (176.90, 0.0, 1.0, 448.0, 5.0, 0.0),
    (T_PULL, 0.0, 0.0, 250.0 * 1.8660254, 0.0, 0.0),
]


def _bridge_curves():
    """各通道的三次 Hermite 曲线：内部关键帧的速度按 PCHIP 取（不过冲），两端的速度单独给出——
    起点与 CAM 在交接帧的横移速度一致，其余为零；终点全部为零（接风暴镜头时静止）。"""
    from scipy.interpolate import PchipInterpolator, CubicHermiteSpline
    k = np.array(BRIDGE_KEYS, float)
    k[:, 3] = np.log(k[:, 3])
    dt = 1 / 240
    v0 = (np.array(CAM.state(T0 + dt)[:2]) - np.array(CAM.state(T0 - dt)[:2])) / (2 * dt)
    curves = []
    for c in range(1, 6):
        d = PchipInterpolator(k[:, 0], k[:, c]).derivative()(k[:, 0])
        d[0] = v0[c - 1] if c <= 2 else 0.0
        d[-1] = 0.0
        curves.append(CubicHermiteSpline(k[:, 0], k[:, c], d))
    return curves


def bridge_state(t):
    """(目标点 x, y, 距离, 倾角（度）, 朝向（度）)。"""
    cs = cached("bridge_curves", _bridge_curves)
    tt = min(max(t, T0), T_PULL)
    tx, ty, ld, tilt, head = (float(c(tt)) for c in cs)
    return tx, ty, math.exp(ld), tilt, head


def bridge_pose(t):
    """(眼睛, 目标点, 上方向) 三个 numpy 向量。"""
    tx, ty, dist, tilt, head = bridge_state(t)
    a, h = math.radians(tilt), math.radians(head)
    hd = np.array([-math.sin(h), math.cos(h), 0.0])
    z = np.array([0.0, 0.0, 1.0])
    tgt = np.array([tx, ty, 0.0])
    eye = tgt + dist * (math.cos(a) * z - math.sin(a) * hd)
    up = math.cos(a) * hd + math.sin(a) * z
    return eye, tgt, up

KUAI = [T(37, i) for i in range(5)]                 # 五个"快"
T_SUN = T(38, 0)                                    # "浮"：冲进阳光
T_STILL = T(40, 0)                                  # L40：镜头完全停住
# 镜头高度 z 的关键位置：每个"快"之后 0.1 秒穿过那一层（层的高度见 storm.LAYER_Z）
Z_KEYS = [(T_PULL, 250.0 * 1.866), (177.56, 464.0), (KUAI[0] + 0.10, 400.0), (KUAI[1] + 0.10, 372.0),
          (KUAI[2] + 0.10, 346.0), (KUAI[3] + 0.10, 300.0), (KUAI[4] + 0.10, 255.0), (180.72, 150.0),
          (T_SUN, 40.0)]
SUN_DECAY = 5.0                 # 冲进阳光后速度按 e^(-5u) 衰减
Z_REST = 15.0                   # L40 停住的高度


def _z_curve():
    from scipy.interpolate import PchipInterpolator, CubicHermiteSpline
    k = np.array(Z_KEYS)
    k[0, 1] = CAM.state(T_PULL)[2] * K
    pc = PchipInterpolator(k[:, 0], k[:, 1])
    d = pc.derivative()(k[:, 0])
    d[0] = 0.0
    d[-1] = (k[-1, 1] - k[-2, 1]) / (k[-1, 0] - k[-2, 0]) * 1.08
    return CubicHermiteSpline(k[:, 0], k[:, 1], d), float(d[-1])


def _z_after_sun(t):
    """冲进阳光之后：全速按指数衰减，再以很慢的速度漂到 L40，停住。"""
    curve, v_s = cached("zcurve", _z_curve)
    z_s = Z_KEYS[-1][1]
    u = t - T_SUN
    z = z_s + v_s / SUN_DECAY * (1.0 - math.exp(-SUN_DECAY * u))
    z_a = z_s + v_s / SUN_DECAY
    # 慢漂：从 z_a 漂到 Z_REST，L40 开始时停住
    w = float(smooth(t, T_SUN + 0.3, T_STILL))
    return z + (Z_REST - z_a) * w


def storm_roll(t):
    """被旋风卷起时镜头绕视线转动（度）：吹的一刻起转，越转越慢，冲进阳光后渐渐停在 86 度附近；
    L40 时完全停住。"""
    if t < FD.T_CHUI:
        return 0.0
    t = min(t, T_STILL)
    return 86.0 * (1.0 - math.exp(-(t - FD.T_CHUI) / 1.25))


GAZE = (0.33, 0.20)            # 视线压低以后太阳在画面上的位置：左上方（画面坐标的正切值）


def gaze(t):
    """冲出来以后视线压低的程度 0–1：头两秒正对太阳，随后缓缓压低，L39 之前完成。"""
    return float(smooth(t, T_SUN + 0.45, T_SUN + 2.9))


SHAKES = [(FD.T_CHUI, 0.030, 9.0, 0.10)] + [(tk, 0.016 + 0.003 * i, 11.0, 0.07) for i, tk in enumerate(KUAI)]


def cam_state(t):
    """(x, y, H, roll)。"""
    if t <= T_PULL:
        return CAM.state(t)
    curve, _ = cached("zcurve", _z_curve)
    z = float(curve(t)) if t < T_SUN else _z_after_sun(t)
    H = z / K
    y = 0.0
    x = 0.0
    for ts, amp, freq, dec in SHAKES:
        u = t - ts
        if 0 <= u < dec * 5:
            e = H * amp * math.exp(-u / dec)
            x += e * 0.6 * math.sin(2 * math.pi * freq * u + 1.0)
            y += e * math.sin(2 * math.pi * freq * u)
    return x, y, H, storm_roll(t)


def camera(t):
    """(引擎的 Cam, (x, y, H))。镜头在 z = H·K 处朝 -z 看，画面中心 (x, y)；冲进阳光以后视线向画面右下方
    偏转（太阳因此移到左上方），偏转角按 gaze(t) 缓入缓出。"""
    from engine import Cam
    if T0 < t < T_PULL:
        eye, tgt, up = bridge_pose(t)
        tx, ty, dist, tilt, head = bridge_state(t)
        return Cam(eye=tuple(eye), target=tuple(tgt), up=tuple(up), fov=30.0, near=0.05, far=4000.0), None
    x, y, H, roll = cam_state(t)
    d = H * K
    r = math.radians(roll)
    up = np.array([-math.sin(r), math.cos(r), 0.0])
    fwd = np.array([0.0, 0.0, -1.0])
    g = gaze(t)
    if g > 0:
        right = np.array([math.cos(r), math.sin(r), 0.0])
        fwd = fwd + right * GAZE[0] * g - up * GAZE[1] * g
        fwd /= np.linalg.norm(fwd)
    eye = np.array([x, y, d])
    near = 0.05 if t < FD.T_CHUI else 0.02
    return Cam(eye=tuple(eye), target=tuple(eye + fwd * 10.0), up=tuple(up), fov=30.0, near=near, far=2000.0), (x, y, H)


def cam_basis(t):
    cam, _ = camera(t)
    r, u, f = cam.basis()
    return np.array(cam.eye, np.float32), (r.astype(np.float32), u.astype(np.float32), f.astype(np.float32))


def cam_rest():
    """镜头停住时的位置与朝向（L40）：阳光里的灰尘按它来撒。"""
    def make():
        e, (r, u, f) = cam_basis(T_STILL + 0.5)
        return e, r, u, f
    return cached("cam_rest", make)


def report():
    """桥段镜头的速度（交接帧到 177.42）。平移按目标点在画面上的移动计（每秒移过几个画面高）；转动按视线方向的
    角速度计；推进按距离对数的变化率计；画面内容的速度取画面上 5×5 个点对应的地面点，看它们下一帧在画面上移动
    多少（画面高/秒），报告中位数和最快的一点。"""
    ts = np.arange(T0 + 1e-3, T_PULL, 1 / 60)
    G, F, D = [], [], []
    for t in ts:
        tx, ty, dist, tilt, head = bridge_state(t)
        e, g, u = bridge_pose(t)
        G.append(g)
        F.append((g - e) / dist)
        D.append(dist)
    G, F, D = np.array(G), np.array(F), np.array(D)
    vt = np.linalg.norm(np.gradient(G, ts, axis=0), axis=1) / (D * 0.5359)
    ang = np.degrees(np.arccos(np.clip((F[1:] * F[:-1]).sum(1), -1, 1))) * 60
    ang = np.r_[ang, ang[-1]]
    z = np.abs(np.gradient(np.log(D), ts))
    th = math.tan(math.radians(15))

    def basis(t):
        e, g, u = bridge_pose(t)
        f = (g - e) / np.linalg.norm(g - e)
        return e, f, u, np.cross(f, u)
    grid = [(sx, sy) for sx in np.linspace(0.1, 0.9, 5) for sy in np.linspace(0.1, 0.9, 5)]
    tc = np.arange(T0 + 1e-3, T_PULL - 0.02, 1 / 30)
    med, mx = [], []
    for t in tc:
        e, f, u, r = basis(t)
        e2, f2, u2, r2 = basis(t + 1 / 120)
        sp = []
        for sx, sy in grid:
            d = f + r * (sx - 0.5) * 2 * th * 16 / 9 + u * (0.5 - sy) * 2 * th
            d /= np.linalg.norm(d)
            P = e + d * min(-e[2] / d[2] if d[2] < -1e-3 else 600.0, 3000.0)
            v = P - e2
            zz = v @ f2
            sp.append(math.hypot(((v @ r2) / zz / (2 * th * 16 / 9) + 0.5 - sx) * 16 / 9,
                                 (0.5 - (v @ u2) / zz / (2 * th) - sy)) * 120)
        med.append(np.median(sp))
        mx.append(max(sp))
    med, mx = np.array(med), np.array(mx)
    for a, b in [(T0, 167.9), (167.9, 171.4), (171.4, 174.0), (174.0, T_PULL)]:
        m, mc = (ts >= a) & (ts < b), (tc >= a) & (tc < b)
        print(f"{a:7.2f}–{b:7.2f}  平移 {vt[m].max():4.2f}  转动 {ang[m].max():4.1f} 度/秒  推进 {z[m].max():4.2f}/秒  "
              f"画面内容 中位数 {med[mc].max():4.2f}、最快点 {mx[mc].max():4.2f} 画面高/秒")


# ---------------------------------------------------------------- 光

def lights():
    return SR.lights()


def field_prep():
    return cached("field_prep", lambda: lights().prepare(FD.field().P0))


def dust_light(P):
    """灰尘处的光强：与地面的照度图同一套光，再加上离地越高越暗。"""
    return lights().irradiance(P, up=False).mean(1) * 1.6


# ---------------------------------------------------------------- 组装

def items(t):
    cam, _ = camera(t)
    # 交接之前（间奏二用自己的镜头落下来）不按镜头裁剪；灰尘的焦点按交接帧的镜头算
    cull = None if t < T0 else cam
    dcam = camera(T0)[0] if t < T0 else cam
    els = []
    bolt_light, bolt_g, bolt_flash = LT.field_light(t)
    if t < 178.15:                             # 第一层出现以后，地面和场边都在它后面，不再画
        els += SR.ground(t, flash=bolt_g)
        if t >= T0:
            els += ST_.outer_ground_items(t, bolt_flash)
            els += ST_.stand_items(t, bolt_flash)
            els += ST_.tower_items(t, cam, bolt_flash)
            els += ST_.beam_items(t, cam)
            els += ST_.sky_items(t, LT.sky_flash(t))
            els += LT.items(t)
    if t < ST.KUAI[2]:
        fly_light = None
        z_split = None
        if t >= FD.T_CHUI:
            # 飞近镜头的板也要看得见：一道来自上方（镜头一侧）的散射光
            fly_light = [((0.0, 0.0, 1.0), (0.55, 0.47, 0.40)), ((0.3, 0.6, 0.74), (0.25, 0.22, 0.2))]
        if t >= ST.REVEAL[0] - 0.05:
            z_split = ST.LAYER_Z[0] if t < ST.KUAI[0] + ST.PASS else ST.LAYER_Z[1]
        els += FD.field().items(t, lights(), field_prep(), cam=cull if t < FD.T_CHUI - 0.02 else cam,
                                fly_light=fly_light, z_split=z_split, extra_light=bolt_light)
    if t < FD.T_SHIVER + 0.5:
        els += SR.grime_items(t)
    if t < FD.T_CHUI + 0.1:
        els += SR.dust_items(t, dcam, dust_light)
    if t >= ST.REVEAL[0] - 0.1 and t < ST.KUAI[4] + 1.0:
        els += ST.layer_items(t, cam_state)
    els += HD.items(t, cam_state)
    if t >= ST.KUAI[4] - 0.05 and t < SN.T_DIM + 1.2:
        els += SN.background(t, storm_roll(T_STILL))
    if t >= SN.T_SUN - 0.08 and t < SN.T_DIM + 1.0:
        e, basis = cam_basis(t)
        els += SN.dust_items(t, e, basis, cam_rest())
        els += SN.piece_items(t, e, basis, cam_rest())
        els += SN.loyalty_items(t, e, basis)
        els += LY.sun_items(t, e, basis, SN.DF)
    if t >= SN.T_DIM:
        e, basis = cam_basis(t)
        els += FN.items(t, e, basis)
    els += LY.bridge_items(t, lambda tt: camera(tt)[0])
    els += LY.l37_items(t)
    return els


BRIDGE_GRADE = {"halation": 1.0, "lift": 0.025, "gain": 1.25, "vignette": 0.48, "weave": 0.5, "scratch": 0.5,
                "warmth": (1.03, 0.97, 0.88), "sat": 0.96}


def _mix_grade(a, b, u):
    out = {}
    for k in set(a) | set(b):
        va = a.get(k, GRADE_DEF["past"][k] if k in GRADE_DEF["past"] else None)
        vb = b.get(k, GRADE_DEF["past"][k] if k in GRADE_DEF["past"] else None)
        if isinstance(va, (tuple, list)):
            out[k] = tuple(float(x) + (float(y) - float(x)) * u for x, y in zip(va, vb))
        else:
            out[k] = float(va) + (float(vb) - float(va)) * u
    return out


SUN_GRADE = {"halation": 2.0, "halation_threshold": 0.85, "lift": 0.035, "gain": 1.25, "vignette": 0.36,
             "weave": 0.5, "scratch": 0.5, "warmth": (1.08, 0.97, 0.80), "sat": 0.92}


def grade(t):
    """交接时刻（164.93）为过去的标准调色，之后 1.5 秒内过渡到桥段的调色：褪色少一点，红色不偏橙，暗角更重。
    冲进阳光时曝光在 0.3 秒里升到 3.4 倍（整幅画面过曝成暖金色），随后在一秒里回落到 1.15，光晕加重、黑位抬起，
    是刺眼的正午；L40 前阳光暗下去，过去的一层曝光降到 0，今天的一层盖上来。"""
    u = float(smooth(t, T0, T0 + 1.5))
    g = _mix_grade(dict(GRADE["past"]), BRIDGE_GRADE, u)
    s_ = float(smooth(t, SN.T_SUN - 0.3, SN.T_SUN + 0.1))
    if s_ > 0:
        g = _mix_grade(g, SUN_GRADE, s_)
    exp = 1.0
    if t >= SN.T_SUN - 0.32:
        up = float(smooth(t, SN.T_SUN - 0.32, SN.T_SUN)) ** 2
        down = math.exp(-max(t - SN.T_SUN, 0.0) / 0.22)
        exp = 1.0 + (3.0 - 1.0) * up * down + 0.10 * float(smooth(t, SN.T_SUN, SN.T_SUN + 0.8))
    exp *= 1.0 - float(smooth(t, 188.28, END.T_SWAP))      # 阳光在 L39 唱完后暗尽，换到结尾的书桌
    lv = LT.level(t, 0) + LT.level(t, 1)
    exp *= 1.0 + 0.12 * lv                                         # 闪电的一下：画面略亮，主要是冷光
    g["exposure"] = exp
    if lv > 0:
        w = min(lv, 1.0) * 0.8                                     # 闪的那两帧颜色偏冷，不加暖、不加橙色光晕
        g["warmth"] = tuple(a * (1 - w) + b * w for a, b in zip(g.get("warmth", (1.06, 0.97, 0.80)), (0.94, 0.99, 1.08)))
        g["halation"] = g.get("halation", 1.2) * (1 - w)
    out = {"past": g}
    if t >= SN.T_DIM + 0.85:
        # 阳光完全暗下去以后，过去的一层不再画（今天的一层底色不透明），画面停住以后不再有颗粒和划痕在动；
        # 最后几帧淡到纯黑
        out["present"] = {"bg": (0.0, 0.0, 0.0)}
        out["final"] = {"fade": float(smooth(t, FN.T_BEAM_OUT[1] - 0.1, FN.T_BEAM_OUT[1] + 0.2)),
                        "fade_color": (0.0, 0.0, 0.0)}
    return out


def frame(t):
    if t >= END.T_SWAP:
        return END.frame(t)
    cam, _ = camera(t)
    return FrameSpec(cam, items(t), grade=grade(t))


def SUBFRAMES(t):
    """正式渲染每帧的子帧数（运动模糊）：桥段 2–3 个；"吹"之后到冲进阳光是全片最快的一段，12 个；
    冲进阳光后减速的那一秒 8 个；之后 2 个。"""
    if FD.T_CHUI - 0.05 <= t < SN.T_SUN:
        return 12
    if SN.T_SUN <= t < SN.T_SUN + 0.9:
        return 8
    if 167.9 <= t < 169.8:
        return 3
    return 2


def _film_msaa():
    """翻板是大量硬边小方片：给 flatcam 里创建的 Film 加上 4 倍多重采样。"""
    import functools
    flatcam.Film = functools.partial(Film, msaa=4)


if __name__ == "__main__":
    _film_msaa()
    # still 只接受整数子帧数：按那一刻取
    sub = SUBFRAMES(float(sys.argv[2])) if len(sys.argv) > 2 and sys.argv[1] == "still" else SUBFRAMES
    flatcam.run(frame, "H段", T0, T1, C.RENDERS, subframes=sub)
