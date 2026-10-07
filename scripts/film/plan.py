"""全片的空间布局与镜头路线（动态分镜阶段）。

坐标沿用引擎约定：右手系，+x 向右，+y 向上，镜头默认朝 -z 看，1 单位约等于 1 米。
"越往深处越早"在空间上落实为高度：今天在最上面，往下依次是第一层（家常旧物）、第二层（公共的墙与远方）、
第三层（夜与水下），桥段的翻板场在最底下。前半首的各个场景按这个顺序逐级下降、彼此在水平方向错开；
间奏二的大坠落和尾段的上冲，沿一根竖直的轴（AXIS）穿过一叠代表各层的"记忆层"平面。

镜头关键帧的时刻取 data/timing.json：字的元音起点、小节首拍和鼓的进出。
相邻场景的衔接有两种：共用几何（穿过字里的空白、落水、跟随运动的物体），或者在画面全白、全黑的瞬间换位置
（照片过曝、夜色吞没一切只剩一个光点）。后一种在画面上看不出跳变，镜头运动依然连续。
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


# ---------------------------------------------------------------- 时间

TIMING = json.loads((ROOT / "data" / "timing.json").read_text(encoding="utf-8"))
_CHARS = [[c["t"] for c in l["chars"]] for l in TIMING["lines"]]
_ENDS = [l["end"] for l in TIMING["lines"]]
BAR_LEN = TIMING["bar_period"]         # 每分钟 140 拍，4/4 拍，一小节 1.7143 秒
BEAT_LEN = TIMING["beat_period"]


def T(n, k=0):
    """第 n 行（1 起算）第 k 个字的起点（元音起点，不计乐句间隔的全角空格）。k 可以为负数，表示倒数。"""
    return _CHARS[n - 1][k]


def L_END(n):
    return _ENDS[n - 1]


def BAR(n, beat=1.0):
    """第 n 小节第 beat 拍的时刻；第 1 小节首拍在 0.4764 秒。"""
    return TIMING["first_downbeat"] + (n - 1) * BAR_LEN + (beat - 1) * BEAT_LEN


# 段落与关键时刻（秒），取自 data/timing.json 的小节网格与鼓的进出
DRUM_IN = BAR(5)                # 7.335 鼓进入
TITLE = BAR(9)                  # 14.19 前奏第二乐句，标题收拢
VERSE1 = T(1)
FLASH_SUMMER = BAR(24, 1.5)     # 40.12 鼓的过门，恢复连续演奏；照片过曝
CHORUS1 = T(9)
INTERLUDE1 = BAR(53)            # 89.62
DARK_NIGHT = BAR(60, 2)         # 102.05 间奏一最后一小节第 2 拍的重军鼓：夜色吞没一切，只剩桅顶的光点
VERSE2 = T(19)
DRUM_BACK2 = BAR(68, 1.5)       # 115.55 主歌二的鼓恢复连续演奏
CHORUS2 = T(23)
INTERLUDE2 = BAR(89)            # 151.335
BRIDGE = T(33)
STORM_KICK = BAR(104, 1.5)      # 177.26 桥段后鼓以一下底鼓进入
STORM = T(36, 8)                # 177.48 "吹"的元音与第 2 拍的军鼓同时
OUTRO = T(37)
SUN = T(38)
FINAL = T(40)
MUSIC_END = BAR(113)            # 192.48 歌曲骤停
END = TIMING["duration"]


# ---------------------------------------------------------------- 场景位置

INTRO = np.array([0.0, 230.0, 0.0])        # 今天：字海与标题（标题在 z = -180）
PAPER = np.array([0.0, 200.0, -182.0])     # 平放的旧纸，L01 写在上面；镜头俯视
SUMMER = np.array([400.0, 180.0, 0.0])     # 第一层：被单（L05），其上是天空（L06），右侧下方是枕头与木桌（L07–L08）
PILLOW = SUMMER + [30.0, -10.0, 0.0]
DESK = SUMMER + [34.0, -10.2, 0.0]
WALL = DESK + [0.0, -29.8, 0.2]            # 第二层：标语墙（墙面在 z = WALL.z，朝 +z），墙顶高 8、墙脚低 7；墙面紧贴在桌上烧穿的那行字的正下方，铁水滴下来正好落到墙头
SPIRE = WALL + [30.0, -20.0, -110.0]       # 尖塔塔基（水面高度），塔高 80
WATER_Y = SPIRE[1]
BUILDING_DY = -26.0                        # 北京展览馆整体下沉 26：水面以上露出塔楼和尖塔（约 54 高），横幅在水面下 0.75–3.45，水底以下不画
TIP = SPIRE + [0.0, 55.2, 0.4]             # 向日葵停在五角星的上顶点（SPIRE.y + 54）上
SPLASH = SPIRE + [0.0, 0.0, 6.0]           # 落水点，在立面前 6


def flight_pos(t):
    """L12 后半向日葵从手里飞到塔尖的位置：从"飛"开始缓缓升起，中段最快，落到五角星上之前收住，途中略向上拱起。"""
    t0, t1 = T(12, 4), T(12, -1)
    u = min(max((t - t0) / (t1 - t0), 0.0), 1.0)
    s = u ** 3 * (10 - 15 * u + 6 * u * u)
    return FLOWER0 * (1 - s) + TIP * s + np.array([0.0, 6.0 * np.sin(np.pi * s), 0.0])
WALL_X0 = WALL[0] - 7.0                    # 标语墙的左缘（墙宽 38）
FLOWER0 = np.array([WALL_X0 + 21.0, WALL[1] - 2.0, WALL[2] + 4.0])   # 墙前握着向日葵的手（L11）


def wall_pose(u, d, yaw, pitch=0.0, dy=0.0, fov=49.56):
    """墙前的机位：u 为沿墙位置（自墙左缘量起），d 为离墙距离，yaw 为向右偏转、pitch 为仰角（度），dy 为相对墙半高的抬升。
    返回 (眼睛, 注视点, 竖直视角)。"""
    eye = np.array([WALL_X0 + u, WALL[1] + 0.5 + dy, WALL[2] + d])
    y, p = np.radians(yaw), np.radians(pitch)
    fwd = np.array([np.sin(y) * np.cos(p), np.sin(p), -np.cos(y) * np.cos(p)])
    return eye, eye + fwd * d, fov


def frame_b_pose():
    """样张 B 的机位：由样张里墙的四个角反算（镜头只左右偏转，竖直视角 49.56 度）。"""
    return wall_pose(8.871, 16.087, 17.332)
CHASM = SPIRE + [0.0, -40.0, 0.0]          # 水底裂沟的底部：暴雨、单车、地球、拼图、立方体
GLOBE = CHASM + [0.0, 3.0, -6.0]
NIGHT = np.array([2000.0, -40.0, 0.0])     # 第三层：门上的锁片（朝 +z），后面是水下
AXIS = (NIGHT[0], NIGHT[2] - 6.0)          # 竖直轴的 x、z：风筝线、大坠落、上冲都沿它
CITY_Y = 300.0                             # 今天：城市（副歌二），在轴的顶端
BRIDGE_Y = -160.0                          # 最深处：翻板场的地面
FIELD = np.array([AXIS[0] + 20.0, BRIDGE_Y, AXIS[1] - 110.0])   # 翻板场中心（场地 360×116，长边沿 x）；
# 这样贴地滑行的起点（FIELD + [-20, 3, 110]）正好在坠落轴的正下方
SUN_Y = 420.0                              # 城市之上的阳光（尾段）


# ---------------------------------------------------------------- 镜头关键帧
# 每一项：(时刻, 眼睛位置, 注视点, 竖直视角, 上方向, 缓动)。上方向 None 表示 (0, 1, 0)；俯视时用 (0, 0, -1)。
# 缓动："ease" 缓入缓出，"linear" 匀速通过（用于连续高速段落的中间帧），"hold" 在该帧停住到下一帧，
# "cut" 表示路线在这一帧之前断开（在全白或全黑的瞬间换位置），两侧各自插值。

DOWN = (0.0, 0.0, -1.0)
UPX = (1.0, 0.0, 0.0)        # 俯视且画面上方朝 +x：在"口"字里用，方框横过来


def v(*a):
    return tuple(float(x) for x in a)


def keys():
    K = []

    def k(t, eye, tgt, fov=40.0, up=None, ease="ease"):
        K.append((float(t), v(*eye), v(*tgt), float(fov), up, ease))

    I, P = INTRO, PAPER
    # 前奏：极慢前推；鼓进入后高速穿过字海；减速看标题；标题散开后下沉、转为俯视旧纸
    k(0.0, I + [0, 0, 12], I + [0, 0, 0])
    k(DRUM_IN, I + [0, 0, 2], I + [0, 0, -10])
    k(11.0, I + [0, 0, -75], I + [0, 0, -95], ease="linear")
    k(TITLE, I + [0, 0, -140], I + [0, 0, -180])
    k(19.0, I + [6, 1.5, -158], I + [0, 0, -180])
    k(24.5, I + [-4, -1, -160], I + [0, 0, -180])
    k(VERSE1, P + [0, 17, 0], P, up=DOWN)
    # L01：先在高处看着整行字逐个写出；"吵"字落下后扎向它的"口"，在第 19 小节首拍的底鼓上落进方框。
    # 高度按等比递减，画面放大的速度看起来均匀。楷体"口"的字怀竖长约 1:1.85，下落途中镜头转 90 度，
    # 落定时方框横过来、恰好约等于 16:9 的画幅，"口"的笔画成为画面的边框
    (kx, kz), (kw, kd) = kou_geometry()
    k(T(1, -2), P + [1.0, 15.5, 0], P + [1.0, 0, 0], up=DOWN, ease="linear")
    h_fill = kw * 1.12 / (2 * np.tan(np.radians(20)))        # 竖直视角 40 度时，方框的短边略小于画面高度
    n = 7
    ts = np.linspace(T(1, -1), BAR(19), n)
    for i, tt in enumerate(ts):
        u = i / (n - 1)
        h = 14 * (h_fill / 14) ** u
        f = u ** 0.5
        a = np.radians(90) * (3 * u * u - 2 * u ** 3)
        x, z = P[0] + 1.3 + (kx - 1.3) * f, P[2] + kz * f
        k(tt, (x, P[1] + h, z), (x, P[1], z), up=(np.sin(a), 0.0, -np.cos(a)), ease="linear" if i < n - 1 else "ease")
    # L02–L04：停在"口"字的方框里；电视出现时略升高，让笔画成为电视边框；照片从亮点里长出来
    kc = (P[0] + kx, P[1], P[2] + kz)
    k(T(3), (kc[0], P[1] + h_fill * 1.2, kc[2]), kc, up=UPX)
    k(T(3, -4), (kc[0], P[1] + h_fill * 1.4, kc[2]), kc, up=UPX)
    k(T(4), (kc[0], P[1] + h_fill * 1.35, kc[2]), kc, up=UPX)
    k(FLASH_SUMMER - 0.02, (kc[0], P[1] + h_fill * 1.1, kc[2]), kc, up=UPX)
    # —— 过曝的白光里换到第一层的被单 ——
    S = SUMMER
    k(FLASH_SUMMER, S + [0, 1.4, 2.5], S + [0, 1.3, 0], ease="cut")
    k(T(5, 2), S + [0.5, 1.5, 7.5], S + [0, 1.2, 0])
    k(T(5, -4), S + [1.8, 1.6, 9.0], S + [0.8, 1.4, 0])
    k(T(6), S + [3.5, 5, 9], S + [3.5, 12, -4])                     # 灰烬升起，镜头仰起
    k(T(6, -3), S + [9, 15, 6], S + [14, 17, -6])                   # 天空里，"骑"字横穿
    k(T(7), S + [15, 15.5, 4], S + [18, 15, -6])                    # 长枪向下倾斜
    k(T(7, 6), S + [24, 4, 2], S + [30, -9, -1])                    # 跟着刀穿过云层落下
    k(T(7, -2), PILLOW + [0, 5, 0.5], PILLOW + [0.2, 0, 0], up=DOWN)
    k(T(8), DESK + [0, 4.4, -0.3], DESK + [0, 0, -0.3], up=DOWN)
    k(T(8, -1), DESK + [0, 3.7, -0.25], DESK + [0, 0, -0.25], up=DOWN)
    # 副歌一：夜色降临，刻痕灌满铁水；下一块木板上"未來被熔斷在"逐字烧穿，"斷"时木板断开、两半向下翻落；
    # 镜头从断口穿下去，向前拉开、转向墙面，跟着由铁水滴凝成的"迷失的深夜裡"一起下降；字落到墙头化成五道铁水，
    # 镜头在"像"字时落定在样张 B 的机位
    W = WALL
    D = DESK
    k(CHORUS1, D + [0, 3.2, 0.05], D + [0, 0, 0.05], up=DOWN)
    k(T(9, 4), D + [0.55, 1.7, 0.45], D + [0.65, 0, 0.5], up=DOWN)
    k(T(9, 5), D + [0.85, 0.25, 0.55], D + [0.9, -3, 0.6], up=DOWN, ease="linear")
    # 铁水字的中心高度约为 DESK.y - 0.6 - 5.5 (t - 56.3)²（见 seg_c/scene.py 的 drop_center_y），镜头始终对着它
    k(56.70, D + [0.6, -0.9, 2.2], D + [0.0, -1.9, 0.6])
    k(57.10, D + [0.5, -3.1, 4.6], D + [0.0, -4.3, 0.6], ease="linear")
    k(57.35, D + [0.7, -6.0, 6.6], D + [0.0, -6.9, 0.6], ease="linear")
    k(57.95, D + [1.2, -14.6, 9.6], D + [0.0, -16.0, 0.6], ease="linear")
    fb = frame_b_pose()
    k(T(10), fb[0], fb[1], fov=fb[2])                                 # 样张 B 的机位
    k(T(10, -1), *wall_pose(15.5, 16.5, 12.0), ease="linear")         # 沿墙横移，刷子与镜头同向
    k(T(11, 0), *wall_pose(17.5, 19.0, 8.0, pitch=6.0))                # "乌云"：后退、抬头看墙头上方的夜空
    k(T(11, 2), *wall_pose(18.5, 22.0, 5.0, pitch=20.0, dy=1.0))       # 第一个"来"
    k(T(11, 4), *wall_pose(19.5, 21.0, 4.0, pitch=19.0, dy=0.5))       # 第三个"来"
    F0 = FLOWER0
    k(T(11, 6), F0 + [-0.8, 0.0, 3.25], F0 + [-0.3, -0.5, 0], fov=40)     # 手握茎，茎顶的"她"与歌词同在一行
    k(T(12, 3), F0 + [-1.0, 0.25, 3.5], F0 + [0.15, -0.15, 0], fov=40)     # "她"变成一朵花
    # L12 后半：花离开手，镜头跟着越过墙头，望见水池对岸的尖塔；花飞在前面，身后留下"克里姆林宫的花"
    k(T(12, 4), F0 + [-1.4, 0.9, 3.6], F0 + [0, 0.6, 0], fov=40)
    t5 = T(12, 5) + 0.08
    k(t5, F0 + [-1.4, 1.3, 3.8], flight_pos(t5) + [0, 0.2, 0], fov=40)    # "飛往"写在花离开的位置，看清后再追
    fp = flight_pos(T(12, 6))
    k(T(12, 6), (F0[0] - 0.5, WALL[1] + 12, F0[2] - 3.2), fp + (TIP - fp) * 0.15, fov=42, ease="linear")   # 从墙头上方越过
    tm = (T(12, 6) + T(12, -1)) / 2
    k(tm, flight_pos(tm) + [-4.5, -7, 22], TIP, fov=42, ease="linear")   # 跟在花后面追向尖塔
    k(T(12, -1), TIP + [-3, -10, 30], TIP, fov=42)                    # 花落在塔尖的五角星上
    # L13：花跳下塔尖，频闪残影逐拍拉开；镜头后退、随花下降，"律"字落水时看清水花，随即冲向水面、没入水下
    k(T(13), TIP + [-3.5, -12, 32], TIP + [0, -2, 0], fov=44)
    k(T(13, 6), SPIRE + [-5, 32, 50], SPIRE + [0, 29, 3], fov=48, ease="linear")
    k(T(13, -5), SPIRE + [-5, 15, 42], SPLASH + [0, 4, 0], fov=46, ease="linear")   # "律"：落水
    k(T(13, -1), SPIRE + [-2.5, 2.2, 15], SPLASH + [0, -0.5, 0], fov=44)            # 俯看水面的字和波纹
    k(T(14), SPIRE + [-1.5, -3.0, 12], SPLASH + [0, -3.6, 0], fov=46)               # 水下
    k(T(14, 6), SPIRE + [-1.0, -4.2, 13], SPLASH + [0, -3.8, -2], fov=48)           # "摔"：横幅从中间裂开
    k(T(14, 6) + 0.4, SPIRE + [-0.9, -4.8, 13.2], SPLASH + [0, -4.6, -2], fov=48)   # 看清裂开，再随碎块下沉
    k(T(15) - 0.3, SPIRE + [-0.5, -15.5, 15], SPIRE + [0, -20.5, 5.8], fov=48)      # 跟着碎块和字沉向裂沟
    # L15–L18：裂沟底部，暴雨、单车、地球、拼图、立方体
    C, G = CHASM, GLOBE
    k(T(15, 5), C + [0, 2, 8], C + [0, 1.5, -10])
    k(T(16), C + [0, 2.2, 12], C + [0, 2, -10])
    k(T(16, -4), G + [8, 0.5, 3], G)
    k(T(17), G + [8.5, 0, 0], G)
    k(T(17, -1), G + [5, 0, 1], G)
    k(T(18, 5), G + [7, 1, 2], G)
    k(T(18, 9), G + [10, 5, 10], G + [0, 6, 0])                     # "帆"：退后看红帆升起；"满"落在间奏一的首拍上，帆随即起航
    # 间奏一：红帆在报纸字栏的海上疾驰，镜头贴着海面并行；后半升高、减速，帆远去成一个光点
    def sail(t):                     # 帆的位置：匀加速到每秒 22 单位
        dt = max(0.0, t - INTERLUDE1)
        a = 22 / 3.0
        x = 0.5 * a * dt ** 2 if dt < 3 else 0.5 * a * 9 + 22 * (dt - 3)
        return G + [x, 6, 0]
    for tt in (INTERLUDE1, 92.0, 94.0, 96.0):
        k(tt, sail(tt) + [-4, -3, 9], sail(tt) + [4, -4.5, 0], ease="linear" if tt not in (INTERLUDE1,) else "ease")
    k(99.0, G + [128, 20, 16], sail(99.0) + [0, -4, -10])               # 减速、升高，停在原处，帆继续远去
    k(DARK_NIGHT, G + [131, 22, 18], sail(DARK_NIGHT) + [0, 2, -20])
    # —— 夜色吞没一切只剩桅顶光点的瞬间，换到第三层的门前；晚灯放在画面上同一个位置 ——
    N = NIGHT
    k(DARK_NIGHT + 0.02, N + [0.6, 2.2, 12], N + [0, 2.6, 0], ease="cut")
    k(T(19, 5), N + [0.2, 0.3, 2.2], N + [0, 0.1, 0])
    k(T(19, -1), N + [0, 0.1, 0.35], N + [0, 0.1, 0])
    k(T(20), N + [0, 0.1, -1.0], N + [0, -1, -6])                    # 穿过锁孔，到了水下
    ax, az = AXIS
    k(T(20, -1), (ax + 1, N[1] - 12, az + 5), (ax, N[1] - 16, az))   # 跟着沉钟下沉
    k(T(21, 5), (ax + 2, N[1] - 14, az + 3), (ax, N[1] - 8, az))     # 风筝线从水底升起，镜头转向上方
    k(T(21, -1), (ax + 1.5, N[1] - 6, az + 2), (ax, N[1] + 10, az))
    # L22：沿风筝线加速上升，边升边向下看，走过的各层在下方远去；"重"字时冲出最上面一层
    k(T(22, 3), (ax + 1, N[1] + 30, az + 1), (ax, N[1] - 50, az), up=DOWN)
    k(T(22, -2), (ax + 1, CITY_Y - 120, az + 1), (ax, CITY_Y - 400, az), up=DOWN, ease="linear")
    k(T(22, -1), (ax + 1, CITY_Y - 10, az + 1), (ax, CITY_Y - 300, az), up=DOWN, ease="linear")
    # 副歌二：今天的城市（城市底图是一块竖直的大平面，在轴的前方 250 处）
    cz = az
    k(CHORUS2, (ax, CITY_Y, cz + 2), (ax, CITY_Y + 20, cz - 250))
    k(T(24), (ax + 6, CITY_Y + 2, cz - 10), (ax + 12, CITY_Y + 18, cz - 250))
    k(T(24, -1), (ax + 14, CITY_Y + 6, cz - 60), (ax + 22, CITY_Y + 20, cz - 250))   # 推近 LED 立面
    k(T(26), (ax - 10, CITY_Y + 10, cz - 30), (ax + 10, CITY_Y + 30, cz - 250))
    k(T(27), (ax + 20, CITY_Y + 40, cz - 40), (ax + 22, CITY_Y + 38, cz - 52))       # 玻璃幕墙顶
    k(T(27, -4), (ax + 20, CITY_Y - 50, cz - 40), (ax + 22, CITY_Y - 58, cz - 52), ease="linear")
    k(T(28), (ax + 20, CITY_Y - 58, cz - 40), (ax + 22, CITY_Y - 66, cz - 52))
    k(T(29), (ax + 8, CITY_Y - 60, cz - 20), (ax + 8, CITY_Y - 60, cz - 40))
    k(T(30), (ax, CITY_Y - 60, cz - 8), (ax, CITY_Y - 60, cz - 20))
    k(T(31), (ax + 6, CITY_Y - 60, cz - 12), (ax, CITY_Y - 60, cz - 20))
    k(T(32), (ax + 7, CITY_Y - 59, cz - 13), (ax, CITY_Y - 60, cz - 20))
    k(INTERLUDE2 - 0.2, (ax, CITY_Y - 57, cz - 2), (ax, CITY_Y - 52, cz - 20))
    # 间奏二：大坠落。记忆层之间的间距越往下越大，而每个小节首拍过一层，所以下坠持续加速
    k(INTERLUDE2 + 0.3, (ax, CITY_Y - 60, az + 0.5), (ax, CITY_Y - 200, az), up=DOWN)
    for tt, y in dive_layers():
        k(tt, (ax, y, az + 0.5), (ax, y - 150, az), up=DOWN, ease="linear")
    k(BRIDGE - 0.4, (ax, BRIDGE_Y + 40, az + 0.5), (ax, BRIDGE_Y, az), up=DOWN)
    # 桥段：贴地滑过巨字的脚下，再升高，最后到样张 D 的高处看全联；"为我"时微微后撤，"吹"字时被旋风卷起
    F = FIELD
    k(BRIDGE + 0.2, F + [-20, 3, 110], F + [-5, 12, 70])
    k(T(33, -1), F + [-5, 3.5, 105], F + [10, 13, 70])
    k(T(34, -1), F + [-15, 120, 170], F)
    k(T(35, -1), F + [-37, 315, 151], F, fov=34)
    k(T(36, 6), F + [-39, 322, 158], F, fov=34)                         # "为我"：后撤
    k(STORM, F + [-37, 314, 150], F, fov=34)
    # 尾段：五个"快"各冲破一层；冲出最上面一层进入阳光，速度骤减；最后一句时停住
    for tt, y in storm_layers():
        k(tt, (F[0] - 4, y, F[2] + 20), (F[0], y + 200, F[2]), fov=44, ease="linear")
    k(SUN, (F[0], SUN_Y, F[2] + 10), (F[0], SUN_Y + 3, F[2] - 10), fov=42)
    k(T(39), (F[0], SUN_Y + 1.2, F[2] + 9), (F[0], SUN_Y + 1.5, F[2] - 10), fov=42)
    k(FINAL, (F[0], SUN_Y + 1.5, F[2] + 8.5), (F[0], SUN_Y + 1.5, F[2] - 10), fov=42, ease="hold")
    k(END, (F[0], SUN_Y + 1.5, F[2] + 8.5), (F[0], SUN_Y + 1.5, F[2] - 10), fov=42)
    K.sort(key=lambda x: x[0])
    return K


def dive_layers():
    """间奏二穿过的记忆层：(过层时刻, 高度)。间奏二从第 89 小节首拍开始，镜头在这一拍翻成俯视；
    第一层（城市光点）在同一小节第 2.5 拍的底鼓上穿过，其余七层依次落在第 90–96 小节的首拍上。
    层间距按"每段平均速度递增"排定：约每秒 9、15、21、27、33、40、49 单位。"""
    bars = [BAR(89, 2.5)] + [BAR(n) for n in range(90, 97)]
    gaps = [0, 10, 26, 36, 46, 56, 68, 84]
    y = CITY_Y - 63
    out = []
    for t, g in zip(bars, gaps):
        y -= g
        out.append((t, y))
    return out


DIVE_LAYER_NAMES = ["城市光点", "电视和照片", "云和被单", "标语墙", "雨与拼图", "报纸的海", "锁孔", "深红"]
STORM_LAYER_NAMES = ["锁孔", "报纸的海", "标语墙", "云和被单", "城市光点"]


def storm_layers():
    """尾段五个"快"冲破的记忆层：(时刻, 高度)。"""
    ts = [T(37, i) for i in range(5)]
    ys = [FIELD[1] + 320, FIELD[1] + 370, FIELD[1] + 430, FIELD[1] + 500, FIELD[1] + 560]
    return list(zip(ts, ys))


# ---------------------------------------------------------------- "吵"字里"口"的位置

PAPER_KIND, PAPER_WEIGHT, PAPER_H = "kai", 400, 1.6     # 旧纸上的 L01：楷体手写，字高 1.6，字距等于字高


def paper_char_x(i):
    """L01（繁体，含全角空格）第 i 个位置的字心相对 PAPER 的 x。"""
    import sys
    sys.path.insert(0, str(ROOT / "scripts" / "style"))
    import look
    return -len(look.trad(look.lyric(1))) * PAPER_H / 2 + (i + 0.5) * PAPER_H


_KOU = None


def kou_geometry():
    """L01 末字"吵"里"口"的字怀（被笔画围住的空白）：返回 ((dx, dz), (沿 x 的宽, 沿 z 的长))，dx、dz 为字怀中心
    相对 PAPER 的位置。纸平放、字头朝 -z。用引擎的排版结果和字形轮廓求，与画面上的字形完全一致。"""
    global _KOU
    if _KOU is not None:
        return _KOU
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    sys.path.insert(0, str(ROOT / "scripts" / "style"))
    import look
    import skia
    from scipy import ndimage
    from engine import TextPlane, bounds
    i = look.trad(look.lyric(1)).index("吵")
    tp = TextPlane("吵", kind=PAPER_KIND, weight=PAPER_WEIGHT, height=PAPER_H, center=(paper_char_x(i), 0, 0),
                   rot=(0, -90, 0))
    path = tp.outline()
    x0, y0, x1, y1 = bounds(path)
    x0, y0 = x0 - 0.02, y0 - 0.02
    res = 1000
    w, h = int((x1 - x0 + 0.02) * res), int((y1 - y0 + 0.02) * res)
    arr = np.zeros((h, w), np.uint8)
    srf = skia.Surface.MakeRasterDirect(skia.ImageInfo.MakeA8(w, h), arr)
    c = srf.getCanvas()
    c.scale(res, res)
    c.translate(-x0, -y0)
    c.drawPath(path, skia.Paint(AntiAlias=True))
    c = srf = None
    lab, n = ndimage.label(arr < 128)
    border = set(np.unique(np.r_[lab[0], lab[-1], lab[:, 0], lab[:, -1]]))
    holes = [j for j in range(1, n + 1) if j not in border]
    best = max(holes, key=lambda j: (lab == j).sum() if np.nonzero(lab == j)[1].mean() < w / 2 else 0)
    ys, xs = np.nonzero(lab == best)
    ex0, ex1 = x0 + xs.min() / res, x0 + (xs.max() + 1) / res
    ey0, ey1 = y0 + ys.min() / res, y0 + (ys.max() + 1) / res
    ctr = tp.em_to_world((ex0 + ex1) / 2, (ey0 + ey1) / 2)
    _KOU = ((float(ctr[0]), float(ctr[2])), ((ex1 - ex0) * PAPER_H, (ey1 - ey0) * PAPER_H))
    return _KOU


def kou_center():
    return kou_geometry()[0]


if __name__ == "__main__":
    K = keys()
    print(len(K), "个关键帧")
    prev = None
    for t, eye, tgt, fov, up, ease in K:
        if prev is not None:
            d = np.linalg.norm(np.array(eye) - np.array(prev[1]))
            dt = t - prev[0]
            sp = d / dt if dt > 0 else float("inf")
            flag = "  <-- 换位置" if sp > 400 else ""
            print(f"{prev[0]:7.2f} → {t:7.2f}  距离 {d:8.2f}  速度 {sp:8.2f}{flag}")
        prev = (t, eye)
