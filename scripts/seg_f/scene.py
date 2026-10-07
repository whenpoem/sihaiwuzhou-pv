"""F 段：副歌二 L23–L32（116.0–151.3333 秒，帧 6960–9079）。

副歌二把副歌一的动作在今天重演一遍。歌词把"迷失的深夜"改成了"明亮的深夜"，前一句刚唱完"回到从前"：想回到从前，
重播出来的却是今天灯光下的样子。所以画面是今天的城市夜色：陆家嘴夜景照片压成的冷色单色调（f_city.py），屏幕、玻璃和
水面；歌词是简体、思源宋体细字重的纯白字；旧字只以残影出现（烧屏、淡影），用繁体、褪色红，是画面里唯一的红色。
构图与副歌一左右镜像，节奏更快。

空间是平面的：城市照片在 z = 0，宽 38.4、高 25.6，照片中心在原点；各句的物件放在它前面（z > 0），镜头朝 -z 看，
只平移和推拉（FlatCam）。全段在同一座城市里连续进行，各句的位置如下。

116.0 从上一段的冷白接过来：冷白是一块 LED 行情屏通电时的全白，镜头贴在屏上，白光由上往下刷新退去，屏上只剩上一句
的末字"重"（E 段在交接之前唱到它）；第二遍刷新出行情，镜头从屏前拉开。L23 指数"未来"一路下跌、触到熔断线，报价
停住转灰，只剩"暂停交易"，镜头拉开看见灯火通明的城市（f_board.py）。L24 行情屏熄灭，后面圆柱楼的 LED 立面通电，
烧屏残影"抓革命　促生產"始终在，"挥之不去"时刷新亮带扫过（f_facade.py）。L25 三个"来"以信号故障的样子砸在三栋楼的
屏幕上，随后立面上亮起白色线描的手和花（f_neon.py）。L26 花展开、飞向天际线上淡淡的展览馆尖塔残影（f_ghost.py）。
L27 花沿玻璃幕墙下坠，幕墙的窗带是一行行小字（f_wall.py），频闪残影逐拍拉开，落进江里。L28 镜头前的一块玻璃从中心
裂开、碎落（f_glass.py）。L29 雨窗起雾，雾上抹出单车的轮廓又被雾盖住（f_rain.py）。L30 雾里的字卷成飞快旋转的地球
（f_globe.py）。L31–L32 副歌一后半的拼图与缺一面的立方体原样重演，缺口里升起白帆，"满"时帆被鼓满（f_dlink.py 借用
D 段的素材），151.1 秒以后画面停稳，交给间奏二。

    python scene.py preview | sheet 输出.png 秒,秒,... [--size 640x360] | still 秒 输出.png | report
"""
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import f_common as C  # noqa: E402
from f_common import cached, ease, ramp, sm, chars, onsets, LYRIC_W  # noqa: E402
import handoff  # noqa: E402
import look  # noqa: E402
from flatcam import FlatCam, run  # noqa: E402
from plan import T, BAR  # noqa: E402
from engine import FrameSpec, Overlay, Particles, Plane, Tex, TextPlane  # noqa: E402

import f_city as CT  # noqa: E402
import f_board as BD  # noqa: E402
import f_facade as FC  # noqa: E402

T0, T1 = handoff.T_TODAY, 9080 / 60          # 116.0–151.3333：渲染帧 6960–9079
FOV = 30.0
K = 1.0 / (2.0 * math.tan(math.radians(FOV / 2)))
ASPECT = 16 / 9

# ---------------------------------------------------------------- L23：行情屏

BW, BH, ZB = 8.0, 4.5, 8.0                   # 屏幕的宽、高与所在深度（在城市前方）
BOARD_C = np.array([9.45, -2.06])            # 屏幕中心
END23 = (4.5, -1.2, 15.0)                    # L23 末尾的全景：(中心 x, 中心 y, z=0 处的画面高)


def board_point(u, v):
    """屏幕内容坐标 (u, v)（0–1，v 向下）→ 世界坐标 (x, y)。"""
    return np.array([BOARD_C[0] - BW / 2 + u * BW, BOARD_C[1] + BH / 2 - v * BH])


D_OFF = BAR(89) - BAR(53)                         # 36 个小节：副歌二比副歌一晚这么多
PZ_O = np.array([4.3, -7.60])                     # 拼图中心（本段的世界坐标）
ZP = 9.0                                          # 拼图与盒子所在的深度
D_CAM = [(82.05, 1.30, -0.48, 2.04), (83.05, 1.30 - 0.095, -0.50, 1.50), (85.55, 1.30 - 0.095, -0.50, 1.46)]
# D 段 scene.py 里 L17 的镜头关键位置（L18 的镜头本段另排）
MOUTH = np.array([4.3, -7.60 + 0.57 * math.cos(math.radians(33.0))])   # 盒口中心（轴测视角 33 度时）


def _d_cam_end():
    """"满"之前镜头停稳的位置：帆升满后整幅画面（盒子、帆和竖排的歌词）都在画面里。"""
    return (MOUTH[0] - 0.30, MOUTH[1] + 0.375, 1.85 + ZP / K)


def _cam_keys():
    keys = []
    # 116.0–117.0：从通电全白的 LED 特写里拉出来。按屏幕所在深度上的画面高 Hb 的对数插值，拉远的视觉速度先快后慢
    p0 = board_point(0.20, 0.22)
    Hb0, Hb1 = 0.30, 6.43
    c1 = np.array([BOARD_C[0] - 0.13 * ASPECT * Hb1, BOARD_C[1]])
    for i in range(12):
        u = i / 11
        s = 1 - (1 - u) ** 2.6
        Hb = math.exp(math.log(Hb0) + (math.log(Hb1) - math.log(Hb0)) * s)
        # 画面中心从特写点移到构图中心，按画面放大的进度同步移动，特写点在画面上的位置连续变化
        w = (Hb - Hb0) / (Hb1 - Hb0)
        c = p0 + (c1 - p0) * w
        keys.append((116.0 + 1.0 * u, c[0], c[1], Hb + ZB / K))
    keys.append((117.95, c1[0] + 0.15, c1[1] + 0.05, 6.15 + ZB / K))      # 唱"未来被熔断"时极慢地推近
    keys.append((118.25, c1[0] + 0.10, c1[1] + 0.02, 6.30 + ZB / K))
    keys.append((119.95, *END23))                                         # "明亮的深夜里"：拉开，看见灯火通明的城市
    keys.append((120.95, 6.0, -0.4, 13.6))                                 # L24：屏幕熄灭，向后面的圆柱楼推近
    keys.append((123.40, 7.3, -1.9, 9.4))
    keys.append((124.20, 7.9, -2.5, 9.9))                                  # L25：三栋楼的立面都在画面里
    keys.append((125.00, 7.95, -2.55, 9.95))
    keys.append((125.75, 6.9, -2.5, 7.6))                                  # "先别松开她的手"：推近霓虹的手和花
    keys.append((126.75, 6.85, -2.35, 7.35))
    keys.append((127.95, 6.95, -1.75, 7.7))                                # "让她变朵"：花展开，略微后退
    keys.append((128.95, 5.6, -0.6, 8.8))                                  # "飞往"：跟着花飞向左边的尖塔残影
    keys.append((129.95, 3.8, -2.4, 9.9))                                  # 花落在星尖上：尖塔、塔楼上部和花在一幅画面里
    keys.append((130.55, 3.8, -2.35, 9.9))                                 # L27"跳"
    keys.append((131.45, 4.0, -4.0, 9.4))                                  # 沿玻璃幕墙随花下坠
    keys.append((132.25, 4.3, -6.6, 8.4))
    keys.append((132.85, 4.5, -8.2, 7.7))                                  # "律"：落水，水花、字环和塔基横幅是画面的主体
    keys.append((133.60, 4.3, -7.52, 7.55))                                # L28：镜头停住，前面是一块玻璃
    keys.append((135.20, 4.3, -7.55, 7.45))
    keys.append((136.90, 4.3, -7.6, 7.35))
    keys.append((140.45, 4.3, -7.68, 7.2))                                 # L29：隔着下雨的玻璃
    keys.append((143.40, 4.3, -7.62, 6.95))                                # L30：雾化成的字卷成地球
    # L31–L32 重演 D 段 L17–L18 的镜头（晚 36 个小节），平移到本段拼图所在的位置，按拼图所在深度换算画面高
    for td, x, y, Hd in D_CAM:
        keys.append((td + D_OFF, x - 1.30 + PZ_O[0], y + 0.50 + PZ_O[1], Hd + ZP / K))
    # L32：盒子折起时拉开（与 D 段相同），帆开始升起以后缓慢推近，151.0 秒时帆和盒口占画面高度的七成，停在这里
    keys.append((149.20, MOUTH[0] - 0.25, MOUTH[1] + 0.25, 2.55 + ZP / K))
    keys.append((151.00, *_d_cam_end()))
    keys.append((151.3334, *_d_cam_end()))
    return keys


SLAMS = [T(25, 2), T(25, 3), T(25, 4)]          # 三个"来"
CAM = FlatCam(_cam_keys(), fov=FOV, shakes=[(SLAMS[0], 0.010, 8.0, 0.10), (SLAMS[1], 0.013, 8.0, 0.11),
                                             (SLAMS[2], 0.018, 7.5, 0.13), (T(28, 6), 0.006, 9.0, 0.08)])


# ---------------------------------------------------------------- 城市

def city(t):
    """城市底图：唱"未来被熔断"时在屏幕后面压暗、虚化（景深外的光团），拉开时对焦回来、亮起来；L29 镜头对焦到
    雨窗上，城市又虚成光斑。"""
    focus = sm(t, 118.2, 119.4) if t < 121 else 1.0 - sm(t, 136.9, 137.4)
    lum = (0.42 + 0.48 * sm(t, 118.2, 119.6)) * background_dim(t)
    lum *= 1.0 - 0.30 * (sm(t, 128.2, 129.2) - sm(t, 133.0, 133.6))      # 花飞向尖塔残影、坠落时城市退后一层
    sz = CT.SIZE
    items = []
    if focus < 1.0:
        items.append(Plane(CT.blurred_tex(), center=(0, 0, -0.01), size=sz, color=(lum,) * 3, group="present"))
    if focus > 0.0:
        items.append(Plane(CT.styled_tex(), center=(0, 0, 0.0), size=sz, color=(lum,) * 3, opacity=focus,
                           group="present"))
    return items


T_OFF = (120.22, 120.50)                     # L24 开始前，停住的行情屏熄灭，后面的圆柱楼立面亮起


def board(t):
    """透明 LED 屏：灯亮处是画面，暗处是深色的玻璃，透出后面的城市。L24 之前熄灭，只剩外框，随后外框也隐进夜色。"""
    if t > T_OFF[1] + 0.3:
        return []
    power = 1.0 - sm(t, *T_OFF)
    items = []
    c = (BOARD_C[0], BOARD_C[1], ZB)
    m = 40 / 1600 * BW
    items.append(Plane(BD.bezel_tex(), center=(c[0], c[1], ZB - 0.001), size=(BW + 2 * m, BH + 2 * m),
                       opacity=1.0 - sm(t, T_OFF[0] + 0.1, T_OFF[1] + 0.3), group="present"))
    if power > 0:
        items.append(Plane(BD.content_tex(t), center=c, size=(BW, BH), material="f_led_board",
                           uniforms={"led_power": power}, group="present"))
    return items


def facade(t):
    """圆柱楼的立面：L23 时暗着、只有极淡的红印；L24"像"时通电亮起，"挥之不去"时刷新亮带扫过；L25 第二个"来"
    砸在它上面；霓虹的手和花亮起以后，屏幕暗下去，只剩残影。"""
    if t > 141.0:
        return []
    power = 0.55 + 0.45 * sm(t, 120.3, 120.9)
    power *= 1.0 - 0.72 * sm(t, NEON_ON, NEON_ON + 0.5) * (1 - sm(t, T_FLY + 0.3, T_FLY + 1.3))
    power *= 1.0 - 0.15 * sm(t, T_FLY + 1.0, T_FLY + 2.0)              # 之后回到平时暗着的样子，只剩残影
    # 刷新亮带：L24"像"时屏幕通电，一道亮带从上往下扫过，整面亮起；"挥"时第二道亮带扫过，残影仍在。
    # 亮带扫过以后继续缓慢下行（超出立面），亮着的部分随之一点点暗回底亮
    band, fresh = -1.0, 0.65
    for tb0, dur, k in ((T(24, 0) - 0.08, 0.85, 0.55), (T(24, 8), 0.75, 0.65)):
        if t >= tb0:
            u = (t - tb0) / dur
            band = u * 1.15 - 0.05 if u < 1 else 1.10 + 0.35 * (u - 1)
            fresh = k
    lit = 0.30 + 0.16 * sm(t, T(24, 0), T(24, 0) + 1.2) * (1 - sm(t, T(25, 0) - 0.2, T(25, 0) + 0.3))
    g = slam_state(t, 1, "aurora") if t < T_OUT + 0.5 else None
    if g:
        power = max(power, 0.6)
    if t > 137.3:
        return []
    its = FC.items(t, band=band, power=power, glitch=g, fresh=fresh, base_lit=lit * (1 - 0.6 * static_k(t)))
    # 城市在景深之外（L23 的行情屏前、L29 的雨窗前）时立面也一起隐去，只留虚化底图里那块暗的楼面
    vis = sm(t, 118.2, 119.4) * (1.0 - sm(t, 136.9, 137.3))
    for it in its:
        it.opacity = vis
    return its


# ---------------------------------------------------------------- L25：三个"来"砸在三面屏幕上

FACE_ORDER = ["right", "aurora", "left"]          # 与副歌一（左、中、右）镜像：右、中、左
T_STATIC = (T(25, 0) - 0.05, T(25, 5) + 0.15)     # "乌云"：三面屏幕亮起暗色的雪花
T_OUT = T(25, 5) - 0.05                           # "先"：三个"来"故障着熄灭
NEON_ON = T(25, 5)


def static_k(t):
    if t < T_STATIC[0] or t > T_STATIC[1] + 0.3:
        return 0.0
    k = sm(t, T_STATIC[0], T_STATIC[0] + 0.25) * (1 - sm(t, T_STATIC[1], T_STATIC[1] + 0.3))
    return k * (0.75 + 0.25 * math.sin(t * 37.0) * math.sin(t * 23.0))


def slam_state(t, i, name):
    """第 i 个"来"在它那面屏幕上的状态：砸下前 0.14 秒从屏幕上沿外滑下，落定时整屏闪白、横向块错位；
    之后故障渐弱，偶尔再跳一下；"先"时全部故障着熄灭。"""
    ts = SLAMS[i]
    st = static_k(t)
    if t < ts - 0.14 and st <= 0:
        return None
    asp = FC.face_aspect(name)
    w = 0.86
    h = w * asp
    c_end = 0.30
    if t < ts - 0.14:
        c, amt, k, fl = -1.0, 0.0, 0.0, 0.0
    else:
        u = min((t - ts + 0.14) / 0.14, 1.0)
        c = -h + (c_end + h) * u ** 2.2
        amt = 1.0 if t < ts else 0.12 + 0.88 * math.exp(-(t - ts) / 0.22)
        amt += 0.5 * max(0.0, math.sin(t * 5.3 + i * 2.0)) ** 30                 # 偶尔再跳一下
        k = 1.35
        fl = 1.4 * math.exp(-(t - ts) / 0.07) if t >= ts else 0.0
    off = sm(t, T_OUT, T_OUT + 0.28)
    if off > 0:
        amt = max(amt, off * 1.2)
        k *= 1.0 - sm(t, T_OUT + 0.12, T_OUT + 0.30)
    rect = (0.5 - w / 2, c - h / 2, 0.5 + w / 2, c + h / 2)
    return dict(glyph=FC.glyph_tex("来"), rect=rect, k=k, amt=min(amt, 1.0), static=st, flash=fl, seed=0.2 + 0.3 * i)


def faces(t):
    items = []
    for i, name in enumerate(FACE_ORDER):
        if name == "aurora":
            continue
        g = slam_state(t, i, name)
        if g:
            on = max(min(g["static"] * 1.5, 1.0), 1.0 if g["k"] > 0 else 0.0)
            items += FC.face_items(name, g["glyph"], g["rect"], k=g["k"], amt=g["amt"], static=g["static"],
                                   flash=g["flash"], seed=g["seed"], screen_a=0.88 * on)
    return items


# ---------------------------------------------------------------- L25 后半：霓虹的手和花

import f_neon as NE  # noqa: E402

FLOWER_O = np.array([7.9, -1.0])                  # 花心（"她"字）的位置：圆柱楼立面的上部
S_FL = 3.8                                        # 花的缩放：花心"她"字高 0.80
Z_NEON = 0.35
ROW_GAP = 1.0


def neon_flicker(t, t0):
    """霓虹灯管通电时的闪烁：几下明灭之后稳定。"""
    if t < t0:
        return 0.0
    u = t - t0
    if u > 0.42:
        return 1.0
    seq = [(0.00, 0.05, 0.7), (0.09, 0.03, 0.3), (0.15, 0.07, 1.0), (0.26, 0.03, 0.4), (0.31, 0.11, 1.0)]
    v = 0.0
    for a, d, k in seq:
        if a <= u < a + d:
            v = k
    return v if u < 0.42 else 1.0


def neon(t):
    if t < NEON_ON or t > 131.0:
        return []
    k = neon_flicker(t, NEON_ON) * (1 - sm(t, 129.6, 130.4))
    if k <= 0:
        return []
    o = FLOWER_O
    items = []
    c, sz = NE.box_plane(NE.stem_box(), o, S_FL, Z_NEON - 0.01)
    items.append(Plane(NE.stem_tex(), center=c, size=sz, opacity=k, group="present"))
    c, sz = NE.box_plane(NE.hand_box(), o, S_FL, Z_NEON + 0.01)
    items.append(Plane(NE.hand_tex(), center=c, size=sz, opacity=k, group="present"))
    return items


def flower_head(t):
    if t < NEON_ON:
        return []
    return head(t, neon_flicker(t, NEON_ON))


# ---------------------------------------------------------------- L26：花展开、飞向尖塔残影

T_BLOOM0, T_BLOOM1 = T(26, 1), T(26, 3)           # "她"到"朵"：笔画展开成花瓣
T_FLY, T_LAND = T(26, 4), T(26, -1)               # "飞"起飞，"花"落在星尖上
GHOST_S = 0.18                                    # 尖塔残影的缩放：从江面到星尖约 10，塔楼宽约 2.4
GHOST_O = np.array([3.0, -10.6 - 23.91 * GHOST_S])  # 残影的建筑坐标原点：残影立在江里，塔基横幅落在近处的江面上
#                                                  （与副歌一里淹在水池里的展览馆成对），星尖在 y ≈ -0.5
S_LAND = 2.8                                      # 落在星尖上时花的缩放：花的直径约 2.5，占画面高度的四分之一以上
PERCH = np.array([GHOST_O[0], GHOST_O[1] + 80.0 * GHOST_S + 0.30 * S_LAND * 1.04])


def bloom_u(t):
    return float(1 - (1 - ramp(t, T_BLOOM0, T_BLOOM1)) ** 3)


def flight_s(t):
    s = ramp(t, T_FLY, T_LAND)
    return s ** 3 * (10 - 15 * s + 6 * s * s)


T_JUMP = T(27, 0)                                 # "跳"
T_SPLASH = BAR(78)                                # 第 78 小节首拍，与"律"几乎同时：落水
WATER_Y = -9.1                                    # 落水点的高度（近岸江面）
V0 = 2.0                                          # 起跳时向上的初速度
G_FALL = 2 * (PERCH[1] - WATER_Y + V0 * (T_SPLASH - T_JUMP)) / (T_SPLASH - T_JUMP) ** 2
DRIFT = 1.6                                       # 下坠中向右漂，贴着玻璃幕墙落下，落在横幅右端的上方
GHOST_T = [BAR(77, b) for b in (1, 2, 3, 4)]      # 频闪：每一拍留下一个残影


def flower_pos(t):
    """花心的位置与缩放。起飞以后沿一条向右上方拱起的弧线飞向左上方的星尖，起落都缓；"跳"以后按自由落体下坠。"""
    if t >= T_JUMP:
        tau = min(t, T_SPLASH + 0.3) - T_JUMP
        y = PERCH[1] + V0 * tau - 0.5 * G_FALL * tau * tau
        return np.array([PERCH[0] + DRIFT * (1 - math.exp(-tau / 0.5)), y]), S_LAND
    if t < T_FLY:
        return FLOWER_O.copy(), S_FL
    if t < T_LAND:
        s = flight_s(t)
        p = FLOWER_O * (1 - s) + PERCH * s
        d = PERCH - FLOWER_O
        n = np.array([d[1], -d[0]]) / np.linalg.norm(d)            # 路线的右侧法向
        p = p + n * 1.4 * math.sin(math.pi * s)
        return p, S_FL * (1 - s) + S_LAND * s
    return PERCH.copy(), S_LAND


def flower_spin(t):
    if t >= T_JUMP:
        return 140.0 * (t - T_JUMP) ** 1.4
    if T_FLY <= t < T_LAND:
        s = ramp(t, T_FLY, T_LAND)
        return -25.0 * math.sin(math.pi * s) * (1 - s)
    return 0.0


def head(t, k=1.0):
    """花头：L25 只有花心的"她"，L26 展开成花、飞走，L27 从星尖跳下、落进江里。"""
    if t > T_SPLASH + 0.04:
        return []
    p, S = flower_pos(t)
    boost = 1.0 + 0.8 * C.pulse(t, T(25, -3), 0.35) + 0.6 * C.pulse(t, T(26, 1), 0.35)   # 唱到"她"时花心的字亮一下
    boost += 0.5 * C.pulse(t, T_LAND, 0.4)
    c, sz = NE.box_plane(NE.HEAD_BOX, p, S, Z_NEON + 0.02)
    return [Plane(NE.head_tex(bloom_u(t)), center=c, size=sz, rot=(0, 0, flower_spin(t)), opacity=k,
                  color=(boost,) * 3, group="present")]


def ghost(t):
    """尖塔残影：花起飞时在夜空里慢慢显出，淡而可读；L27 花跳下以后随镜头下行渐渐淡去。"""
    a = sm(t, T_FLY - 0.2, T_FLY + 0.9) * (1 - sm(t, 133.0, 133.6))
    if a <= 0:
        return []
    import f_ghost as GH
    return GH.items(GHOST_O, GHOST_S, 0.85 * a, z=0.05, banner_op=0.48 * a, veil_op=0.70 * a)


# ---------------------------------------------------------------- L27：沿玻璃幕墙下坠，落进江里

import f_wall as WL  # noqa: E402
from engine import register_material  # noqa: E402


def curtain(t):
    """玻璃幕墙：照片里那栋楼的正立面换成由小字排成窗带的高分辨率立面（远看与照片一致）。频闪的每一下，
    花附近的幕墙被照亮一下，墙上的旧字残影也跟着显出来。"""
    if t < 127.4 or t > 137.4:
        return []
    a = sm(t, 127.4, 128.4) * (1 - sm(t, 136.9, 137.3))
    flash = sum(C.pulse(t, tk, 0.10) for tk in GHOST_T)
    ghost_k = 0.16 + 0.10 * sm(t, T_JUMP, T_JUMP + 0.6) + 0.25 * flash
    items = WL.items(opacity=a, ghost=0.0, z=0.002)
    if flash > 0.01:
        p, S = flower_pos(t)
        soft = cached("soft_disc", lambda: Tex(C.soft_disc(256, 2.2)))
        items.append(Plane(soft, center=(p[0], p[1], 0.01), size=(4.0, 4.0), blend="add",
                           color=tuple(np.array([0.55, 0.62, 0.75]) * 0.5 * flash), group="present"))
    return items


def strobe(t):
    """频闪：坠落中每一拍留下一个残影，残影间距按自由落体逐拍拉大，像物理课本里的频闪照片。"""
    if t < GHOST_T[0] or t > 134.0:
        return []
    items = []
    fade_all = 1.0 - sm(t, 133.0, 133.7)
    for tk in GHOST_T:
        if t < tk:
            continue
        p, S = flower_pos(tk)
        a = 0.62 * math.exp(-(t - tk) / 2.5) * fade_all
        fl = 0.6 * math.exp(-(t - tk) / 0.12)
        c, sz = NE.box_plane(NE.HEAD_BOX, p, S, Z_NEON - 0.01)
        items.append(Plane(NE.head_tex(1.0), center=c, size=sz, rot=(0, 0, flower_spin(tk)), opacity=a,
                           color=(0.75 + fl, 0.85 + fl, 1.0 + fl), group="present"))
    return items


register_material("f_river", """
uniform sampler2D city;
uniform vec4 city_rect;          // 照片在世界里的范围 (x0, y0, x1, y1)
uniform float wtop;              // 江面上沿（对岸）的高度
uniform vec2 sp;                 // 落水点
uniform float st;                // 落水后经过的时间（秒），小于 0 表示还没落水
vec4 material(vec4 b) {
    vec2 p = v_wpos.xy;
    float depth = max(wtop - p.y, 0.0);
    float k = 0.012 + 0.022 * depth;                     // 越近的水面波纹越大
    vec2 off = vec2((vnoise(vec2(p.x * 1.4, p.y * 8.0 - u_time * 1.1), 3) - 0.5) * k * 1.6,
                    (vnoise(vec2(p.x * 0.6 + u_time * 0.25, p.y * 12.0), 4) - 0.5) * k * 0.7);
    float ring = 0.0;
    if (st >= 0.0) {
        vec2 d = (p - sp) * vec2(1.0, 3.4);               // 斜看水面，圆形的波纹压扁成椭圆
        float r = length(d);
        for (int i = 0; i < 3; i++) {
            float R = (st - 0.14 * float(i)) * 2.6;
            if (R <= 0.0) continue;
            float w = sin((r - R) * 13.0) * exp(-abs(r - R) * 2.4) * exp(-st * 0.8);
            off += normalize(d + 1e-4) * w * 0.05;
            ring += exp(-pow((r - R) * 9.0, 2.0)) * exp(-st * 1.1) * (1.0 - 0.3 * float(i));
        }
    }
    vec2 q = p + off;
    vec2 uv = vec2((q.x - city_rect.x) / (city_rect.z - city_rect.x), (city_rect.w - q.y) / (city_rect.w - city_rect.y));
    vec3 c = texture(city, uv).rgb;
    c += vec3(0.55, 0.62, 0.75) * ring * 0.9;
    float a = smoothstep(0.0, 0.25, depth);
    return vec4(c * a * b.rgb, a);
}
""", defaults={"wtop": -8.55, "sp": (0.0, 0.0), "st": -1.0, "city_rect": (0, 0, 1, 1)})


def river(t):
    """江面：照片里的江面换成会动的水，对岸灯光的倒影随波纹晃动；落水后波纹从落水点扩开。"""
    if t < 129.0 or t > 141.0:
        return []
    sz = CT.SIZE
    p0, _ = flower_pos(T_SPLASH)
    uni = {"city": CT.styled_tex(), "city_rect": (-sz[0] / 2, -sz[1] / 2, sz[0] / 2, sz[1] / 2), "wtop": -8.55,
           "sp": (float(p0[0]), WATER_Y), "st": (t - T_SPLASH) if t >= T_SPLASH else -1.0}
    lum = 0.90
    blur = sm(t, 136.9, 137.4)
    out = []
    if blur < 1:
        out.append(Plane(None, center=(0.0, -10.75, 0.003), size=(sz[0], 4.3), color=(lum,) * 3, material="f_river",
                         uniforms=uni, opacity=1 - blur, group="present"))
    if blur > 0:
        u2 = dict(uni, city=CT.blurred_tex())
        out.append(Plane(None, center=(0.0, -10.75, 0.0035), size=(sz[0], 4.3), color=(lum,) * 3, material="f_river",
                         uniforms=u2, opacity=blur, group="present"))
    return out


OLD27 = look.trad("不管风吹浪打　胜似闲庭信步　")


def old_ring(t):
    """旧字"不管風吹浪打　勝似閒庭信步"排成一圈褪色红的淡字，随落水的波纹在江面上扩开（与副歌一的字环成对）。
    字平躺在水面上，按斜看的角度压扁。"""
    u = t - T_SPLASH - 0.12
    if u <= 0 or u > 3.2:
        return []
    p0, _ = flower_pos(T_SPLASH)
    r = 0.9 + 3.0 * u ** 0.7
    op = 0.32 * sm(u, 0.0, 0.25) * math.exp(-u / 2.4)
    n = max(10, int(2 * math.pi * r / 0.80))
    items = []
    for i in range(n):
        ch = OLD27[i % len(OLD27)]
        if ch == "　":
            continue
        a = 2 * math.pi * i / n + 0.12 * u
        c = (p0[0] + r * math.cos(a), WATER_Y + 0.02 + r * math.sin(a) / 3.4, Z_NEON - 0.05 - 0.01 * math.sin(a))
        items.append(TextPlane(ch, kind="fang", height=0.76, color=tuple(C.RED * 1.6), center=c, scale_x=1.0,
                               rot=(0, -72, -math.degrees(a) - 90), group="present", opacity=op))
    return items


def splash(t):
    """落水：一圈冠状的水花溅起再落回，中心冒起一股细水柱；落水那一下的白光。"""
    u = t - T_SPLASH
    if u < -0.01 or u > 1.6:
        return []
    from engine import dot_atlas
    p0, _ = flower_pos(T_SPLASH)
    x0, y0, zc = float(p0[0]), WATER_Y, 0.4
    items = []
    soft = cached("soft_disc", lambda: Tex(C.soft_disc(256, 2.2)))
    f = math.exp(-max(u, 0) / 0.09)
    if f > 0.01:
        items.append(Plane(soft, center=(x0, y0 + 0.1, zc), size=(4.6, 2.0), blend="add",
                           color=(0.9 * f, 0.95 * f, 1.0 * f), group="present"))
    if u > 0:
        rng = np.random.default_rng(42)
        n = 420
        ang = math.pi / 2 + rng.normal(0, 0.55, n)
        sp_ = rng.uniform(3.5, 11.5, n) * (1 - 0.35 * np.abs(np.cos(ang)))
        vx, vy = np.cos(ang) * sp_ * 0.6, np.sin(ang) * sp_
        g = 14.0
        px = x0 + rng.normal(0, 0.15, n) + vx * u
        py = y0 + vy * u - 0.5 * g * u * u
        alive = py > y0 - 0.05
        if alive.any():
            vyy = vy - g * u
            spd = np.hypot(vx, vyy)
            rot = np.arctan2(vyy, vx) - math.pi / 2
            P = np.c_[px, py, np.full(n, zc)][alive]
            a = np.clip(1.15 - u / 1.1, 0, 1)
            w = rng.uniform(0.06, 0.17, n)
            sz = np.c_[w, w * (1 + np.clip(spd * 0.07, 0, 1.8))][alive]
            col = np.c_[np.full(n, 0.85), np.full(n, 0.92), np.full(n, 1.0), np.ones(n)][alive] * a
            dot = cached("dot_atlas", lambda: dot_atlas(64, 0.35))
            items.append(Particles(dot, P, sz, rot[alive], col, blend="add", group="present"))
    return items


def focus(t):
    """霓虹亮起后，四周的城市渐渐压暗，视线集中到手和花上（正片叠底的径向渐变，放在城市与霓虹之间）。"""
    k = sm(t, NEON_ON, NEON_ON + 0.8)
    k *= 1.0 - (sm(t, 128.2, 129.2) - sm(t, 133.0, 133.6))             # 花飞走、坠落、落江时不压暗江面
    if k <= 0:
        return []

    def make():
        n = 512
        yy, xx = np.mgrid[0:n, 0:n] / (n - 1)
        dx, dy = (xx - 0.5) * 60, (yy - 0.5) * 40
        r = np.sqrt(dx ** 2 + (dy / 0.9) ** 2)
        v = 1.0 - 0.6 * np.clip((r - 2.5) / 6.0, 0, 1) ** 1.2
        return np.dstack([v, v, v, np.ones_like(v)]).astype(np.float32)
    tex = cached("focus25", make)
    return [Plane(tex, center=(FLOWER_O[0] - 0.6, FLOWER_O[1] - 1.8, 0.1), size=(60, 40), blend="multiply", opacity=k,
                  group="present")]


# ---------------------------------------------------------------- 歌词

def lyric_chars(text, times, x, y, size, t, weight=250, gap=1.0, fade=0.08, out=None, vertical=False, rise=6):
    """逐字出现的白色细宋体（画面层，纯白、不受调色影响）。out=(t0, t1) 时整行淡出。"""
    f = look.font("serif", weight, size)
    items = []
    a_out = 1.0 - sm(t, *out) if out else 1.0
    if a_out <= 0:
        return items
    pos = 0.0
    for ch, tc in zip(text, times):
        if ch == "　":
            pos += size * 0.6
            continue
        if t >= tc - 0.03:
            a = sm(t, tc - 0.03, tc - 0.03 + fade) * a_out
            dy = rise * (1 - sm(t, tc - 0.03, tc + 0.15))
            if vertical:
                items.append(Overlay(ch, xy=(x, y + pos + dy), anchor="center-top", size=size, weight=weight,
                                     opacity=a))
            else:
                items.append(Overlay(ch, xy=(x + pos, y + dy), anchor="left-baseline", size=size, weight=weight,
                                     opacity=a))
        pos += (size * 1.06 if vertical else f.measureText(ch) * gap)
    return items


def lyrics(t):
    items = []
    L23, T23 = chars(23), onsets(23)
    if 118.0 < t < 120.6:
        items += lyric_chars(L23[6:], T23[6:], 150, 215, 104, t, out=(120.0, 120.35))
    if 120.3 < t < 124.0:
        L24, T24 = chars(24), onsets(24)
        items += lyric_chars(L24[:8], T24[:8], 120, 250, 108, t, out=(123.3, 123.6))
        items += lyric_chars(L24[8:], T24[8:], 120, 400, 108, t, out=(123.3, 123.6))
    if T(30, 0) - 0.1 < t < T(31, 0) + 0.2:
        items += lyric30(t)
    if t > T(32, 0) - 0.1:
        items += lyric32(t)
    if T(29, 0) - 0.1 < t < T(30, 0) + 0.3:
        L29, T29 = chars(29), onsets(29)
        items += lyric_chars(L29[:2], T29[:2], 120, 160, 96, t, out=(T(30, 0) - 0.2, T(30, 0) + 0.1))
        items += row29(t)
    L25, T25 = chars(25), onsets(25)
    if 123.3 < t < 125.6:
        items += lyric_chars(L25[:2], T25[:2], 120, 200, 100, t, out=(125.1, 125.4))
    if NEON_ON - 0.1 < t < 127.2:
        items += row25(t)
    if T(26, 0) - 0.1 < t < 131.0:
        items += lyric26(t)
    if T(27, 0) - 0.1 < t < 134.0:
        items += lyric27(t)
    return items


def lyric27(t):
    """"跳进池底吧"竖排在星尖左侧；"在自然规律"排成一列跟着下坠的花走：刚唱出的字在花的右边、与花同高，先唱的字
    依次排在它上面，整列随花落下，"律"落水时整列停在江面上；"的作用下"浮在江面上，随水波轻轻起伏。"""
    L27, T27 = chars(27), onsets(27)
    items = []
    h = 0.84
    op = 1.0 - sm(t, 132.2, 132.7)
    for i, (ch, tc) in enumerate(zip(L27[:5], T27[:5])):
        if t >= tc - 0.03 and op > 0:
            items.append(TextPlane(ch, kind="serif", weight=250, height=h, color=LYRIC_W, group="present",
                                   center=(PERCH[0] - 0.55 * S_LAND - 0.75, PERCH[1] - 0.2 - (i + 0.5) * h * 1.1,
                                           Z_NEON), opacity=op * sm(t, tc - 0.03, tc + 0.06)))
    op2 = 1.0 - sm(t, 133.15, 133.6)
    text, on = L27[5:10], T27[5:10]
    n = sum(1 for tc in on if t >= tc - 0.03)
    if n and op2 > 0:
        tq = min(t, T_SPLASH)
        p, S = flower_pos(tq)
        hh, step = 0.86, 0.96
        ax = p[0] + 0.50 * S + 0.55
        ay = max(p[1], WATER_Y + 0.55)                  # 最新的字与花同高；落水以后停在江面上
        for i in range(n):
            ch, tc = text[i], on[i]
            y = ay + (n - 1 - i) * step
            items.append(TextPlane(ch, kind="serif", weight=250, height=hh, color=LYRIC_W, group="present",
                                   center=(ax, y, Z_NEON + 0.02), opacity=op2 * sm(t, tc - 0.03, tc + 0.06)))
    op3 = 1.0 - sm(t, 133.45, 133.75)
    x_s = flower_pos(T_SPLASH)[0][0]
    for k, (ch, tc) in enumerate(zip(L27[10:], T27[10:])):
        if t >= tc - 0.03 and op3 > 0:
            bob = 0.05 * math.sin(t * 4.0 + k * 1.3)
            items.append(TextPlane(ch, kind="serif", weight=250, height=0.78, color=LYRIC_W, group="present",
                                   center=(x_s + 0.50 * S_LAND + 0.55 + 0.86 * k, WATER_Y - 0.5 + bob, Z_NEON),
                                   opacity=op3 * sm(t, tc - 0.03, tc + 0.08)))
    return items


def lyric26(t):
    """让她变朵：以花心的"她"为中心，花瓣展开时把两边的字推开；起飞后"飞往"留在花离开的位置；
    "克里姆林宫的花"竖排在花的右侧（与副歌一镜像），随花一起飞，落定后停在星尖右边。"""
    L26, T26 = chars(26), onsets(26)
    items = []
    u = bloom_u(t)
    G, h = ROW_GAP, 0.80
    gap = G + (2.15 - G) * u
    op = 1.0 - sm(t, T_FLY - 0.17, T_FLY + 0.02)
    for ch, tc, dx in zip(L26[:4], T26[:4], (-gap, None, gap, gap + G)):
        if dx is None or t < tc - 0.03 or op <= 0:
            continue
        items.append(TextPlane(ch, kind="serif", weight=250, height=h, color=LYRIC_W, group="present",
                               center=(FLOWER_O[0] + dx, FLOWER_O[1], Z_NEON + 0.03),
                               opacity=op * sm(t, tc - 0.03, tc + 0.06)))
    op2 = 1.0 - sm(t, T_FLY + 0.5, T_FLY + 0.8)
    for ch, tc, dx in zip(L26[4:6], T26[4:6], (-1.6 - G, -1.6)):
        if t >= tc - 0.03 and op2 > 0:
            items.append(TextPlane(ch, kind="serif", weight=250, height=h, color=LYRIC_W, group="present",
                                   center=(FLOWER_O[0] + dx, FLOWER_O[1] + 0.9, Z_NEON + 0.03),
                                   opacity=op2 * sm(t, tc - 0.03, tc + 0.06)))
    text, on = L26[6:], T26[6:]
    op3 = 1.0 - sm(t, 130.45, 130.9)
    for i, (ch, tc) in enumerate(zip(text, on)):
        if t < tc - 0.03 or op3 <= 0:
            continue
        tl = min(t - 0.05 * i, T_LAND) if t < T_LAND + 0.5 else T_LAND
        p, S = flower_pos(tl)
        hh = 0.80
        c = (p[0] + 0.50 * S + 0.55 * hh, p[1] + 0.30 * S - (i + 0.5) * hh * 1.08, Z_NEON + 0.03)
        items.append(TextPlane(ch, kind="serif", weight=250, height=hh, color=LYRIC_W, group="present", center=c,
                               opacity=op3 * sm(t, tc - 0.03, tc + 0.08)))
    return items


def lyric32(t):
    """"总算差了一面"写在盒子下方；"希望风帆装饰的满"竖排在帆的左侧（与 D 段镜像），"满"大一号。"""
    L32, T32 = chars(32), onsets(32)
    items = []
    out = 1.0 - sm(t, T32[6] - 0.2, T32[7])
    f = look.font("serif", 250, 100)
    h = 0.18
    w = sum(f.measureText(ch) for ch in L32[:6]) / 100 * h
    x = PZ_O[0] - w / 2
    for ch, tc in zip(L32[:6], T32[:6]):
        cw = f.measureText(ch) / 100 * h
        if t >= tc - 0.03 and out > 0:
            items.append(TextPlane(ch, kind="serif", weight=250, height=h, color=LYRIC_W, group="present",
                                   center=(x + cw / 2, PZ_O[1] - 0.40, ZP + 0.3),
                                   opacity=sm(t, tc - 0.03, tc + 0.06) * out))
        x += cw
    for i, (ch, tc) in enumerate(zip(L32[6:], T32[6:])):
        if t < tc - 0.03:
            continue
        big = i == len(L32) - 7
        hh = 0.23 if big else 0.15
        y = MOUTH[1] + 1.12 - 0.165 * i - (0.04 if big else 0.0)
        flare = 0.35 * math.exp(-(t - tc) / 0.05) if big and t >= tc else 0.0          # 交接帧之前已经平息
        a = sm(t, tc - 0.03, tc + 0.06)
        items.append(TextPlane(ch, kind="serif", weight=250, height=hh, group="present",
                               color=tuple(np.array(LYRIC_W) * (1 + flare)),
                               center=(MOUTH[0] - 0.90, y, ZP + 0.3), opacity=a))
    return items


def lyric30(t):
    """"她善变的"竖排在地球右侧，"和我无关"竖排在左侧（与 D 段镜像）；"世界大概都"一个个定在地球正面的赤道上，
    不随球转。"""
    L30, T30 = chars(30), onsets(30)
    items = []
    out = 1.0 - sm(t, T(31, 0) - 0.2, T(31, 0) + 0.15)
    h = 0.17
    for i, (ch, tc) in enumerate(zip(L30[:4], T30[:4])):
        if t >= tc - 0.03:
            items.append(TextPlane(ch, kind="serif", weight=250, height=h, color=LYRIC_W, group="present",
                                   center=(GL_C[0] + GL_R + 0.42, GL_C[1] + 0.42 - i * h * 1.12, GL_C[2] + 0.7),
                                   opacity=sm(t, tc - 0.03, tc + 0.06) * out))
    lock = L30[4:9]
    f = look.font("serif", 300, 100)
    w = sum(f.measureText(ch) for ch in lock) / 100 * 0.17
    x = GL_C[0] - w / 2
    for ch, tc in zip(lock, T30[4:9]):
        cw = f.measureText(ch) / 100 * 0.17
        if t >= tc - 0.03:
            a = sm(t, tc - 0.03, tc + 0.08) * out
            items.append(TextPlane(ch, kind="serif", weight=300, height=0.17, color=(1.35, 1.35, 1.38), group="present",
                                   center=(x + cw / 2, GL_C[1] - 0.02, GL_C[2] + GL_R + 0.02), opacity=a))
        x += cw
    for i, (ch, tc) in enumerate(zip(L30[9:], T30[9:])):
        if t >= tc - 0.03:
            items.append(TextPlane(ch, kind="serif", weight=250, height=h, color=LYRIC_W, group="present",
                                   center=(GL_C[0] - GL_R - 0.42, GL_C[1] + 0.25 - i * h * 1.12, GL_C[2] + 0.7),
                                   opacity=sm(t, tc - 0.03, tc + 0.06) * out))
    return items


def row29(t):
    """"谁的单车没回来"：写在雨窗下方的玻璃上，起雾时也被雾盖住一些。"""
    L29, T29 = chars(29), onsets(29)
    text, on = L29[5:], T29[5:]
    f = look.font("serif", 250, 100)
    h = 0.15
    w = sum(f.measureText(ch) for ch in text) / 100 * h
    x = R_C[0] - w / 2 + 0.05
    items = []
    out_k = 1.0 - sm(t, T(30, 0) - 0.15, T(30, 0) + 0.25)
    for ch, tc in zip(text, on):
        cw = f.measureText(ch) / 100 * h
        if t >= tc - 0.03:
            items.append(TextPlane(ch, kind="serif", weight=250, height=h, color=LYRIC_W, group="present",
                                   center=(x + cw / 2, R_C[1] - 0.66, ZR + 0.0012),
                                   opacity=sm(t, tc - 0.03, tc + 0.06) * out_k))
        x += cw
    return items


def row25(t):
    """"先别松开她的手"：与花心的"她"排成一行（世界坐标里的白色细宋体），"她"就是花心那个霓虹字。"""
    L25, T25 = chars(25), onsets(25)
    text, on = L25[5:], T25[5:]
    kk = text.index("她")
    items = []
    leave = 1.0 - sm(t, T(26, 0) - 0.25, T(26, 0) - 0.03)          # 在"让"出现之前让出位置
    for i, (ch, tc) in enumerate(zip(text, on)):
        if i == kk or t < tc - 0.03 or leave <= 0:
            continue
        a = sm(t, tc - 0.03, tc + 0.06) * leave
        items.append(TextPlane(ch, kind="serif", weight=250, height=0.80, color=LYRIC_W, group="present",
                               center=(FLOWER_O[0] + (i - kk) * ROW_GAP, FLOWER_O[1], Z_NEON + 0.02), opacity=a))
    return items


# ---------------------------------------------------------------- L28：镜头前的玻璃裂开、碎落

import f_glass as GL  # noqa: E402

ZG = 10.0                                         # 玻璃所在深度（镜头在 z ≈ 14 处）
G_ORIGIN = np.array([4.42, -7.47])                # 冲击点（玻璃坐标原点）的世界位置
T_SHOW = T(28, 0) - 0.30                          # 玻璃显出来：一道反光扫过
T_SPLIT = T(28, 2)                                # "抱"：一道细裂纹穿过"抱"字，"扌"与"包"分开
T_CRACK = T(28, 6)                                # "摔"：冲击点放射出裂纹
T_SHATTER = T(28, 7)                              # "碎"：碎成几十块落下
ROW1_Y, ROW2_Y = 0.42, -0.36                      # 两行歌词在玻璃上的高度（玻璃坐标）
GH_ = 0.205                                       # 玻璃上的字高


def shard_motion():
    """每块碎玻璃的落下参数：起落的先后、向外的初速度、旋转和翻转的角速度。"""
    def make():
        rng = np.random.default_rng(11)
        out = []
        for sh in GL.shard_textures():
            c = sh["centroid"]
            r = float(np.hypot(*c))
            d = c / (r + 1e-6)
            out.append(dict(delay=0.03 * sh["ring"] + rng.uniform(0, 0.05), v=d * rng.uniform(0.15, 0.45) * (1.2 - 0.15 * sh["ring"]),
                            vy=rng.uniform(-0.1, 0.35), spin=rng.uniform(-260, 260), yaw=rng.uniform(-170, 170),
                            pitch=rng.uniform(-170, 170), g=rng.uniform(5.5, 7.5)))
        return out
    return cached("shard_motion", make)


def shard_state(i, t):
    """第 i 块碎玻璃在 t 时的位移 (dx, dy)、转角 (yaw, pitch, roll) 与光泽（翻转到某个角度时反光一闪）。"""
    m = shard_motion()[i]
    u = max(t - T_SHATTER - m["delay"], 0.0)
    dx = m["v"][0] * u
    dy = m["v"][1] * u + m["vy"] * u - 0.5 * m["g"] * u * u
    rot = (m["yaw"] * u, m["pitch"] * u, m["spin"] * u)
    glint = 1.0 + 2.5 * abs(math.sin(math.radians(rot[0] * 0.7 + rot[1]))) ** 12
    return dx, dy, rot, glint, u


def glass_pane(t):
    if t < T_SHOW or t > T(29, 0) + 0.2:
        return []
    items = []
    gx, gy = G_ORIGIN
    show = sm(t, T_SHOW, T_SHOW + 0.3)
    intact = t < T_SHATTER
    if intact:
        # 玻璃本身：一层极淡的冷色，加一道缓慢移动的斜向反光
        items.append(Plane(None, center=(gx, gy, ZG - 0.004), size=(GL.GW, GL.GH), color=(0.02, 0.025, 0.035),
                           opacity=0.38 * show, group="present"))
        sweep = cached("glass_sweep", lambda: Tex(_sweep_tex()))
        sx = -2.6 + 4.2 * ramp(t, T_SHOW, T_SHOW + 1.6)
        items.append(Plane(sweep, center=(gx + sx, gy, ZG - 0.003), size=(1.4, GL.GH), blend="add",
                           color=(0.10 * show, 0.12 * show, 0.15 * show), group="present"))
        if t >= T_CRACK:
            front = 4.0 * C.out_cubic((t - T_CRACK) / 0.28)
            glow, mul = GL.crack_tex(front)
            items.append(Plane(mul, center=(gx, gy, ZG - 0.0025), size=(GL.GW, GL.GH), blend="multiply", group="present"))
            items.append(Plane(glow, center=(gx, gy, ZG - 0.002), size=(GL.GW, GL.GH), group="present"))
            fl = math.exp(-(t - T_CRACK) / 0.06)
            soft = cached("soft_disc", lambda: Tex(C.soft_disc(256, 2.2)))
            items.append(Plane(soft, center=(gx, gy, ZG - 0.001), size=(0.35, 0.35), blend="add",
                               color=(0.9 * fl, 0.95 * fl, 1.0 * fl), group="present"))
    else:
        for i, sh in enumerate(GL.shard_textures()):
            dx, dy, rot, glint, u = shard_state(i, t)
            if dy < -3.5:
                continue
            c = sh["centroid"]
            off = sh["center"] - c                              # 贴图中心相对旋转中心（碎块重心）的位置
            R = _rot2(rot[2])
            cc = c + R @ off
            items.append(Plane(sh["tex"], center=(gx + cc[0] + dx, gy + cc[1] + dy, ZG - 0.002 - 0.0005 * (i % 7)),
                               size=sh["size"], rot=rot, color=(glint,) * 3, opacity=1.0 - sm(u, 0.6, 1.0),
                               group="present"))
    items += glass_text(t)
    return items


def _rot2(deg):
    a = math.radians(deg)
    return np.array([[math.cos(a), -math.sin(a)], [math.sin(a), math.cos(a)]])


def _sweep_tex():
    n = 256
    xx = np.linspace(-1, 1, n)[None, :] * np.ones((n * 2, 1))
    yy = np.linspace(-1, 1, n * 2)[:, None]
    a = np.exp(-((xx + 0.35 * yy) / 0.25) ** 2) * 0.8 + np.exp(-((xx + 0.35 * yy - 0.45) / 0.06) ** 2) * 0.5
    return np.dstack([np.ones_like(a)] * 3 + [np.clip(a, 0, 1)]).astype(np.float32)


def glass_layout():
    """两行歌词在玻璃上的位置（玻璃坐标）：[(字, 起点时刻, x, y)]。"""
    def make():
        L28, T28 = chars(28), onsets(28)
        f = look.font("serif", 250, 100)
        out = []
        row1, row2 = L28[:6], L28[6:]
        w1 = sum(f.measureText(ch) for ch in row1) / 100 * GH_
        x = -w1 / 2 - 0.25
        for ch, tc in zip(row1, T28[:6]):
            w = f.measureText(ch) / 100 * GH_
            out.append((ch, tc, x + w / 2, ROW1_Y))
            x += w
        w2 = sum(f.measureText(ch) for ch in row2) / 100 * GH_
        x = -w2 / 2 + 0.45
        for ch, tc in zip(row2, T28[6:]):
            w = f.measureText(ch) / 100 * GH_
            out.append((ch, tc, x + w / 2, ROW2_Y))
            x += w
        return out
    return cached("glass_layout", make)


def glass_text(t):
    """写在玻璃上的歌词。"抱"字在"抱"那一拍被一道细裂纹分成"扌"和"包"；"碎"以后每个字跟着它所在的那块碎玻璃
    一起落下；"进沟里"三个字在玻璃碎了以后才唱到，从碎块的位置直接往下落。"""
    gx, gy = G_ORIGIN
    items = []
    for k, (ch, tc, x, y) in enumerate(glass_layout()):
        if t < tc - 0.03:
            continue
        a = sm(t, tc - 0.03, tc + 0.06)
        dx = dy = 0.0
        roll = 0.0
        if t >= T_SHATTER:
            if tc < T_SHATTER:
                i = _char_shard(k)
                if i is not None:
                    sdx, sdy, rot, glint, u = shard_state(i, t)
                    c = GL.shard_textures()[i]["centroid"]
                    R = _rot2(rot[2])
                    p = c + R @ (np.array([x, y]) - c)
                    dx, dy, roll = p[0] - x + sdx, p[1] - y + sdy, rot[2]
                    a *= 1.0 - sm(u, 0.5, 0.9)
            else:
                u = t - tc
                dy = -0.5 * 3.0 * u * u
                roll = (k - 8) * 25 * u
                a *= 1.0 - sm(u, 0.55, 0.9)
        if a <= 0:
            continue
        cpos = (gx + x + dx, gy + y + dy, ZG + 0.001)
        if ch == "抱" and t >= T_SPLIT:
            # 裂纹从"扌"和"包"之间穿过：把"抱"字本身的轮廓按部件分成两半，两半沿裂纹各自错开一点、微微转开
            sp = sm(t, T_SPLIT, T_SPLIT + 0.45)
            sep = sp * 0.022
            for k2, (dxs, dys, rr) in enumerate(((-sep, 0.010 * sp, 4.0), (sep, -0.010 * sp, -3.0))):
                tex = split_tex("抱", 250)[k2]
                items.append(Plane(tex, center=(cpos[0] + dxs, cpos[1] + dys, cpos[2]), size=(1.04 * GH_, 1.04 * GH_),
                                   rot=(0, 0, roll + rr * sp), color=LYRIC_W, opacity=a, group="present"))
            continue
        items.append(TextPlane(ch, kind="serif", weight=250, height=GH_, color=LYRIC_W, group="present", center=cpos,
                               rot=(0, 0, roll), opacity=a))
    # "抱"字上的细裂纹
    if T_SPLIT <= t < T_SHATTER:
        ch, tc, x, y = [r for r in glass_layout() if r[0] == "抱"][0]
        ln = sm(t, T_SPLIT - 0.02, T_SPLIT + 0.10)
        crack = cached("bao_crack", lambda: Tex(_bao_crack_tex(), premultiplied=True))
        items.append(Plane(crack, center=(gx + x - 0.022, gy + y, ZG - 0.001), size=(0.10, GH_ * 1.9 * ln + 1e-3),
                           group="present", opacity=ln))
    return items


def split_tex(ch, weight, split_x=0.39):
    """把一个字按部件分成左右两半的覆盖率贴图：字形的闭合轮廓按外框右缘是否在 split_x（em）以左分组，
    "抱"的左边一组正好是"扌"。贴图覆盖 em 坐标 x −0.02–1.02、y −0.90–0.14，与 TextPlane 的字框中心对齐。"""
    def make():
        import skia
        from engine import glyph_path, contours, bounds
        cs = contours(glyph_path(ch, "serif", weight))
        px = 512
        out = []
        for left in (True, False):
            n = int(1.04 * px)
            srf = skia.Surface(n, n)
            cv = srf.getCanvas()
            cv.clear(skia.Color4f(0, 0, 0, 0))
            cv.scale(px, px)
            cv.translate(0.02, 0.90)
            path = skia.Path()
            path.setFillType(skia.PathFillType.kWinding)
            for c in cs:
                if (bounds(c)[2] <= split_x) == left:
                    path.addPath(c)
            cv.drawPath(path, skia.Paint(Color=skia.Color4f(1, 1, 1, 1), AntiAlias=True))
            a = srf.makeImageSnapshot().toarray()[..., 3].astype(np.float32) / 255
            out.append(Tex(a))
        return out
    return cached(f"split_{ch}_{weight}", make)


def _char_shard(k):
    m = cached("char_shards", lambda: {})
    if k not in m:
        ch, tc, x, y = glass_layout()[k]
        m[k] = GL.find_shard((x, y))
    return m[k]


def _bao_crack_tex():
    """穿过"抱"字的一道细裂纹（竖向、带折角的亮线）。"""
    import skia
    w, h = 120, 480
    s = skia.Surface(w, h)
    c = s.getCanvas()
    rng = np.random.default_rng(3)
    pts = [(w / 2 + rng.normal(0, 7), y) for y in np.linspace(0, h, 9)]
    p = skia.Path()
    p.moveTo(*pts[0])
    for q in pts[1:]:
        p.lineTo(*q)
    c.drawPath(p, skia.Paint(Color=skia.Color4f(1, 1, 1, 1), AntiAlias=True, Style=skia.Paint.kStroke_Style, StrokeWidth=2.2))
    a = s.makeImageSnapshot().toarray()[..., 3].astype(np.float32) / 255
    glow = cv2_blur(a, 4) * 0.6
    rgb = (a + glow)[..., None] * np.array([1.1, 1.15, 1.25])
    return np.dstack([rgb, np.clip(a + glow * 0.5, 0, 1)]).astype(np.float32)


def cv2_blur(a, s_):
    import cv2
    return cv2.GaussianBlur(a, (0, 0), s_)


# ---------------------------------------------------------------- L29：雨窗、三个"拜"、雾上的单车

import f_rain as RN  # noqa: E402

ZR = 10.5                                         # 雨窗所在深度
R_C = np.array([4.3, -7.64])                      # 雨窗中心
RW_, RH_ = 3.5, 2.0                               # 雨窗的宽、高（比这一深度上的画面略大）
T_RAIN = T(29, 0)                                 # "暴"：雨点打上玻璃
BAI = [T(29, 2), T(29, 3), T(29, 4)]              # 三个"拜"
BAI_X = [0.95, 0.0, -0.95]                        # 从右往左砸下（与 D 段镜像）
FOG = (BAI[2] + 0.12, T(29, 5) + 0.35)            # 起雾
T_BIKE = T(29, 7)                                 # "单"：雾上抹出单车
T_REFOG = (T(29, 9) - 0.1, T(29, 11) + 0.15)      # "没回来"：雾气重新盖住


def g2w(u, v):
    """雨窗的 0–1 坐标（v 向下）→ 世界坐标。"""
    return R_C[0] - RW_ / 2 + u * RW_, R_C[1] + RH_ / 2 - v * RH_


def rain_glass(t):
    if t < T_RAIN - 0.2 or t > T(30, 0) + 0.6:
        return []
    items = []
    out_k = 1.0 - sm(t, T(30, 0) - 0.05, T(30, 0) + 0.5)          # L30 时雨窗退去
    # 挂住的水珠
    pos, size, t0 = RN.beads()
    on = t >= t0
    if on.any():
        x, y = g2w(pos[on, 0], pos[on, 1])
        pop = np.clip((t - t0[on]) / 0.05, 0, 1)
        P = np.c_[x, y, np.full(on.sum(), ZR + 0.0005)]
        a = (0.9 * pop * out_k)[:, None]
        col = np.c_[np.ones((on.sum(), 3)), np.ones(on.sum())] * a
        items.append(Particles(_drop_atlas(), P, size[on] * (0.6 + 0.4 * pop), None, col, blend="over",
                               group="present"))
    # 往下流的水珠和水痕
    xs, ys, t0s, vs, szs, phs = RN.runners()
    for x0, y0, tr, v, sz, ph in zip(xs, ys, t0s, vs, szs, phs):
        if t < tr:
            continue
        d = RN.run_y(t, tr, v, ph)
        y1 = y0 + d
        if y1 > 1.1:
            continue
        wx, wy0 = g2w(x0, y0)
        _, wy1 = g2w(x0, y1)
        L = max(wy0 - wy1, 1e-3)
        items.append(Plane(RN.trail_tex(), center=(wx, (wy0 + wy1) / 2, ZR + 0.0004), size=(sz * 0.55, L),
                           opacity=0.8 * out_k, group="present"))
        items.append(Particles(_drop_atlas(), np.array([[wx, wy1, ZR + 0.0006]]), np.array([[sz, sz * 1.25]]), None,
                               np.array([[out_k, out_k, out_k, out_k]]), blend="over", group="present"))
    # 雾
    fog_k = 0.92 * sm(t, *FOG)
    if fog_k > 0:
        asp = RN.bike_aspect()
        bw = 0.50
        bh = bw * RW_ / RH_ / asp
        rect = (0.52 - bw / 2, 0.42 - bh / 2, 0.52 + bw / 2, 0.42 + bh / 2)
        bike_k = (1.0 if t >= T_BIKE else 0.0) * (1 - sm(t, *T_REFOG))
        sweep = ramp(t, T_BIKE, T_BIKE + 0.42) * 1.1
        items.append(Plane(None, center=(R_C[0], R_C[1], ZR + 0.001), size=(RW_, RH_), color=(1, 1, 1),
                           material="f_fog", opacity=out_k,
                           uniforms={"fog_k": fog_k, "bike": RN.bike_mask(), "bike_rect": rect, "bike_k": bike_k,
                                     "bike_sweep": sweep}, group="present"))
    items += bai(t, out_k)
    return items


def _drop_atlas():
    return cached("drop_atlas_custom", lambda: _DropAtlas())


class _DropAtlas:
    """粒子用的图集：只有一格，就是 RN.drop_tex() 那颗水珠（预乘发光的 RGBA，不能交给 engine.Atlas 再预乘一次）。"""
    def __init__(self):
        self.tex = RN.drop_tex()
        self.rects = {"drop": (0.0, 0.0, 1.0, 1.0)}
        self.keys = ["drop"]


def bai(t, out_k):
    """三个"拜"：从右往左一个个砸在玻璃上，砸下的一瞬间溅起一圈水花；起雾以后渐渐隐进雾里。"""
    items = []
    fogged = 1.0 - 0.85 * sm(t, FOG[0] + 0.1, FOG[1])
    for i, (tb, bx) in enumerate(zip(BAI, BAI_X)):
        if t < tb - 0.06:
            continue
        u = t - tb
        sc = 1.0 + 0.35 * (1 - sm(t, tb - 0.06, tb)) if u < 0 else 1.0
        a = sm(t, tb - 0.06, tb) * fogged * out_k
        cx, cy = R_C[0] + bx, R_C[1] + 0.30
        items.append(TextPlane("拜", kind="serif", weight=250, height=0.40 * sc, color=LYRIC_W, group="present",
                               center=(cx, cy, ZR + 0.0008), opacity=a))
        if 0 <= u < 0.6:
            rng = np.random.default_rng(100 + i)
            n = 70
            ang = rng.uniform(0, 2 * np.pi, n)
            sp = rng.uniform(0.6, 1.6, n)
            r = sp * (1 - math.exp(-u / 0.08)) * 0.32
            P = np.c_[cx + np.cos(ang) * r, cy + np.sin(ang) * r * 0.9, np.full(n, ZR + 0.0007)]
            k = math.exp(-u / 0.25) * out_k
            col = np.c_[np.full(n, k), np.full(n, k), np.full(n, k), np.full(n, k)]
            items.append(Particles(_drop_atlas(), P, rng.uniform(0.008, 0.02, n), None, col, blend="over",
                                   group="present"))
            fl = math.exp(-u / 0.06)
            soft = cached("soft_disc", lambda: Tex(C.soft_disc(256, 2.2)))
            items.append(Plane(soft, center=(cx, cy, ZR + 0.0009), size=(0.9, 0.9), blend="add",
                               color=(0.5 * fl, 0.55 * fl, 0.6 * fl), group="present"))
    return items


# ---------------------------------------------------------------- L30：雾化成白色细字，卷成飞快旋转的地球

import f_globe as GB  # noqa: E402

GL_C = np.array([4.3, -7.60, 9.4])                # 球心
GL_R = 0.72                                       # 半径
T_GATHER = (T(30, 0) - 0.12, T(30, 0) + 0.75)     # 雾里的字离开玻璃、卷成球
T_GL_OUT = T(31, 0) - 0.15                        # L31：地球散开


def globe_spin(t):
    """自转角（弧度）：卷起时转得最快，之后稳定在每秒约 0.42 圈。"""
    t0 = T_GATHER[0]
    u = max(t - t0, 0.0)
    return 2 * math.pi * (0.42 * u + 0.5 * (1 - math.exp(-u / 0.5)))


def globe(t):
    if t < T_GATHER[0] or t > T(31, 0) + 1.2:
        return []
    lat, lon, idx, red = GB.layout()
    n = len(lat)
    spin = globe_spin(t)
    d = GB.sphere_points(lat, lon, spin)
    P_s = GL_C + d * GL_R
    rng = cached("globe_rng", lambda: np.random.default_rng(31))
    start = cached("globe_start", lambda: np.c_[rng.uniform(R_C[0] - RW_ / 2, R_C[0] + RW_ / 2, n),
                                                 rng.uniform(R_C[1] - RH_ / 2, R_C[1] + RH_ / 2, n),
                                                 np.full(n, ZR + 0.002)])
    delay = cached("globe_delay", lambda: rng.uniform(0, 0.35, n))
    u = np.clip((t - T_GATHER[0] - delay) / (T_GATHER[1] - T_GATHER[0] - 0.35), 0, 1)
    e = u * u * (3 - 2 * u)
    # 从玻璃上的位置沿一条绕球心的螺线卷进去
    sw = (1 - e)[:, None]
    mid = P_s + (start - P_s) * sw
    ang = (1 - e) * 2.2
    rel = mid[:, :2] - GL_C[:2]
    ca, sa = np.cos(ang), np.sin(ang)
    mid[:, 0] = GL_C[0] + rel[:, 0] * ca - rel[:, 1] * sa
    mid[:, 1] = GL_C[1] + rel[:, 0] * sa + rel[:, 1] * ca
    depth = d[:, 2]
    bright = 0.20 + 0.80 * np.clip((depth + 0.35) / 1.35, 0, 1) ** 1.5
    a_fog = 0.25 + 0.75 * e                           # 在玻璃上时是很淡的雾粒
    out = 1.0 - sm(t, T_GL_OUT, T_GL_OUT + 0.55)
    burst = C.out_cubic((t - T_GL_OUT) / 0.55) if t > T_GL_OUT else 0.0
    if burst > 0:                                     # 散开：球面裂成拼图块的一刻，字沿球面法向飞出、很快淡去
        mid = mid + np.c_[d[:, 0], d[:, 1], d[:, 2] * 0.3] * burst * 0.55
    k = (bright * e + (1 - e) * 0.45) * a_fog * out
    col = np.c_[k * 1.15, k * 1.17, k * 1.22, k]
    size = (0.040 + 0.009 * depth) * (0.55 + 0.45 * e)
    A = GB.atlas()
    keys = GB.pool()
    items = [Particles(A, mid, size, None, col, uv=A.index_uv(idx), blend="add", group="present")]
    # 红色旧字的一圈：只剩残影
    ra = GB.red_atlas()
    rl = np.array([r[1] for r in red])
    ro = np.array([r[2] for r in red])
    rd = GB.sphere_points(rl, ro, spin * 0.98)
    keep = np.array([r[0] != "　" for r in red])
    rp = GL_C + rd * GL_R * 1.02
    rk = (0.22 * (0.25 + 0.75 * np.clip((rd[:, 2] + 0.3) / 1.3, 0, 1)) * sm(t, T_GATHER[1] - 0.3, T_GATHER[1] + 0.3) * out)
    rcol = np.c_[np.tile(C.RED * 1.6, (len(red), 1)), rk]            # 粒子的颜色按直通 alpha 理解：rgb 不再乘不透明度
    chars_ = [r[0] for r in red]
    items.append(Particles(ra, rp[keep], np.full(keep.sum(), 0.075), None, rcol[keep],
                           uv=ra.uv([c for c in chars_ if c != "　"]), blend="over", group="present"))
    return items


# ---------------------------------------------------------------- L31–L32：副歌一的拼图、缺一面的立方体与白帆

import f_dlink as DL  # noqa: E402
import f_sail as SL_  # noqa: E402

T_PZ = T_GL_OUT                                   # 地球散开的一刻，拼图块飞出（D 段 82.12 秒加 36 个小节）
T_FOLD = T(32, 0) - 0.06                          # 由逐块的拼图换成按面画的盒子
EL_ISO, PHI_ISO = 33.0, 36.0
T_MAN = T(32, -1)                                 # "满"：帆被风鼓满
SAIL_SCALE = 1.0 / 680                            # 照片像素 → 世界单位：主帆高约 1


def background_dim(t):
    """L30 以后城市虚成很暗的光斑，衬在拼图和盒子后面。"""
    return 1.0 - 0.45 * sm(t, T(30, 0), T(30, 0) + 1.0)


def puzzle(t):
    """L31：D 段那副拼图原样出现。地球散开时碎块飞出，落定的位置、歌词块按字落下、十字形里的块滑进去、
    "自卑"一组顶不进去又弹开，全部按 D 段的动作晚 36 个小节重演，仍然停在一半。"""
    if t < T_PZ or t >= T_FOLD:
        return []
    td = t - D_OFF
    pz = DL.PZ()
    gc = (pz.CENTER[0] + (GL_C[0] - PZ_O[0]), pz.CENTER[1] + (GL_C[1] - PZ_O[1]), GL_C[2] - ZP)
    items = pz.items(td, gc, GL_R, table_op=0.0, light_k=1.0)
    d = PZ_O - pz.CENTER
    return DL._retarget(items, d[0], d[1], ZP, light_k=1.45)


def fold_state(t):
    """四壁依次折起（与 D 段相同的折法，按本行的字）：西、北、东三面在"总算差了"时折起，南面在"面"字落下的
    一拍合上；视角同时从正上方转到轴测角度。"""
    T32 = onsets(32)
    FOLD = {"W": (T32[0], T32[1] + 0.33), "N": (T32[1], T32[2] + 0.37), "E": (T32[2], T32[3] + 0.41),
            "S": (T32[4] - 0.33, T32[5])}
    th = {}
    for n, (a, b) in FOLD.items():
        u = ramp(t, a, b)
        e = u * u * (3 - 2 * u)
        if u >= 1.0:
            e = 1.0 - 0.02 * math.exp(-(t - b) / 0.05) * math.sin((t - b) * 70)
        th[n] = e * math.pi / 2
    v = float(ease(ramp(t, T32[0], T32[5] - 0.1)))
    return th, 90.0 + (EL_ISO - 90.0) * v, PHI_ISO * v


def sail_rise(t):
    """主帆从盒口升起的高度（帆底相对盒口）：从"希"开始，"帆"时升满。"""
    T32 = onsets(32)
    u = float(ease(ramp(t, T32[6] - 0.1, T32[9] + 0.15)))
    return -1.05 + 1.25 * u


def billow(t):
    """"满"：帆被风鼓满。在交接帧（151.3333）之前完全停稳。"""
    return float(ease(ramp(t, T_MAN - 0.05, T_MAN + 0.09)))


def sail_planes(proj, t):
    """白帆、竹撑条与桅杆（f_sail.py）：从盒口里升起，盒口以下的部分裁掉（盒子的前壁挡住开口以下的那一段）。
    "满"时由平常的帆换成鼓满的帆，横向略微撑开。"""
    x0, y0, x1, y1 = SL_.BOX
    k = SAIL_SCALE
    top = proj.pt((0.0, 0.0, DL.CB().S3))
    rise = sail_rise(t)
    ax, ay = 1115.0, 965.0                            # 桅杆对准盒口中心，帆脚对准盒口以上 rise 处

    def place(px, py):
        return np.array([top[0] + (px - ax) * k, top[1] + rise + (ay - py) * k])
    c = place((x0 + x1) / 2, (y0 + y1) / 2)
    H = (y1 - y0) * k
    bw = billow(t)
    sx = 1.0 + 0.05 * bw
    h3 = DL.CB().S3 / 2
    cs = [proj.pt((a_, b_, DL.CB().S3)) for a_ in (-h3, h3) for b_ in (-h3, h3)]
    cs.sort(key=lambda q: q[0])
    clip_y = max(cs[0][1], cs[-1][1])
    v_bottom = min(1.0, max(0.0, (c[1] + H / 2 - clip_y) / H))
    if v_bottom <= 0.001:
        return []
    hh = H * v_bottom
    cy = c[1] + H / 2 - hh / 2
    cx = top[0] + (c[0] - top[0]) * sx
    out = []
    for key, op in (("calm", 1.0), ("full", bw)):
        if op <= 0.001:
            continue
        out.append(Plane(SL_.sail_tex(key), center=(cx, cy, 0.0), size=((x1 - x0) * k * sx, hh),
                         uv=(0, 0, 1, v_bottom), opacity=op, color=(1.0, 1.0, 1.0), group="present"))
    return out


def box(t):
    """L32：拼好的十字形折成缺一面的盒子，缺口里升起一面白帆，"满"时帆被鼓满，随后画面停稳交给下一段。"""
    if t < T_FOLD:
        return []
    th, el, phi = fold_state(t)
    cb = DL.CB()
    proj = cb.Proj(el, phi, PZ_O)
    inside = sail_planes(proj, t) if t >= onsets(32)[6] - 0.15 else []
    items, _ = DL.box_items(th, el, phi, PZ_O, ZP, inside=inside, loose_op=1.0 - sm(t, T(32, 5), T(32, 7)),
                            light_k=1.25, amb=(0.10, 0.11, 0.14))
    return items


# ---------------------------------------------------------------- 组装

SCENES = [city, river, old_ring, facade, curtain, faces, focus, ghost, board, neon, strobe, flower_head, splash,
          glass_pane, rain_glass, globe, puzzle, box, lyrics]


def grade(t):
    g = {"present": {"bloom": 0.35}}
    if t < 116.2:                                    # 116.0 从上一段冲出最上面一层的冷白里接过来
        g["final"] = {"fade": 1.0 - float(ease(ramp(t, 116.0, 116.2))), "fade_color": handoff.COLD_WHITE}
    return g


def frame(t):
    if t < T0 + 0.5 / 60:
        return handoff.white_frame(t, handoff.COLD_WHITE)
    cam, _ = CAM(t)
    items = []
    for sc in SCENES:
        items += sc(t)
    return FrameSpec(cam, items, grade=grade(t))


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "report":
        CAM.report(T0, T1)
    else:
        run(frame, "F段", T0, T1, C.RENDERS)
