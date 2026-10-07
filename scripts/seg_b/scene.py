"""《四海五洲》PV 的 B 段：主歌一后半 L05–L07（40.1167–51.0 秒，帧 2407–3059）。

40.12 秒鼓的过门回来，主歌一后半恢复连续演奏，比前半明亮、有推动力。画面是正午的过去：

L05 晾衣绳上的一排被单，按样张三的做法动起来。上一段的老照片过曝成全白，画面从白光里拉出：镜头后退、
沿绳子右移，五张被单依次被风吹开、被太阳照透，"陽光和襯布"一张一字显出来；"發酵成"时最右一张从角上
发黄、焦黑、烧穿，飘起的灰片聚成"灰的味道"。
L06 灰烬往上飘，镜头随之上移，进入正午的天空。多雷版画里的堂吉诃德沿云顶从左往右骑过，歌词写在天上，
与骑士同行；云的亮部藏着极淡的旧字。
L07 骑士的长矛向下倾斜、脱手，下落中变成一把生锈的刀；镜头随刀穿过一片近云，云的白铺满画面，白光散开时
露出的就是荞麦枕头的白布枕套，焦点由虚到实。刀滑进枕头底下，窗格形状的午后阳光滑过枕面、变暗、转成黄昏的蓝，刀在最后一点光里闪一下，
屋里暗下去，交给下一段。

用法（flatcam.run）：
    python scene.py preview [--from 秒 --to 秒]
    python scene.py sheet 输出.png 秒,秒,... [--size 640x360] [--ss 1]
    python scene.py still 秒 输出.png
"""
import math
import sys

import numpy as np

from common import (INK, K, L, RENDERS, Z_BUILD, Z_FAR, Z_SHEET, Z_SKY, cached, ease, ramp, smooth,
                    visible_h)
import handoff
import plan
from engine import Cam, GRADE_DEFAULTS, FrameSpec, Plane, TextPlane
from flatcam import FlatCam, run
from plan import T

import ash as A
import bed as B
import cloth as C
import fall as F
import sky as S
import yard as Y

T0 = handoff.T_SUMMER                    # 40.1167，帧 2407：全白
T1 = handoff.T_LAMP                      # 51.0，帧 3060（不含）
T_DARK = 50.95                           # 此后整帧为 handoff.dark_frame

# ---------------------------------------------------------------- 镜头
# 关键位置 (时刻, 中心 x, 中心 y, H)：H 是 z = 0 平面上的画面高。L05 的被单在 z = 24，那里框住的高度是
# H − 24/K = H − 12.86，所以 L05 的几行按被单那一层的画面高 Hs 写成 hs(Hs)。

def hs(v):
    """被单那一层的画面高为 v 时对应的 H。"""
    return v + Z_SHEET / K


CAM_KEYS = [
    (T0,     -6.30, 0.50, hs(3.6)),      # 白光里：贴近第一张布
    (40.94,  -4.60, 0.50, hs(6.0)),      # "陽"：头两张布入画
    (41.61,  -2.30, 0.52, hs(8.6)),      # "襯"：四张
    (42.04,  -0.60, 0.56, hs(10.3)),     # "布"：一整排
    (43.00,   0.50, 0.78, hs(11.3)),
    (43.45,   0.90, 0.95, hs(11.6)),     # 灰烬聚成字，镜头开始上移
    (45.35,   3.20, 10.40, 24.6),        # 正午的天空（以下 H 指云所在的 z = 0）
    (47.00,  11.80, 10.60, 24.4),        # 与骑士同行，向右
    (47.45,  14.10, 10.25, 23.6),        # 长矛下压，镜头开始下移
    (48.37,  15.90, 4.00, 15.6),         # 随刀穿过近云：画面全白的一刻
    (49.00,  16.20, 2.60, 13.4),         # 白光散开，落在枕头上
    (T1,     16.30, 2.20, 14.0),
]
CAM = FlatCam(CAM_KEYS, fov=30.0, near=0.05, far=600.0)

GT = [T(5, k) for k in range(5)]         # 五张布被风吹开的时刻 = 五个字的元音起点


# ---------------------------------------------------------------- 光与调色

def light_l05(t):
    """L05 的太阳与天光：(sun_col, amb_col)。"""
    return (6.1, 5.6, 4.8), (0.30, 0.29, 0.28)


def grade(t):
    """以 handoff.GRADE_PAST 为基准。正午（L05、L06）光晕更强、更亮；从白光里出来时先过曝，再落回正午的数值；
    落进屋里（L07）回到标准值；50.7 秒起整帧淡向 handoff.DARK，50.95 秒与 dark_frame 接上。"""
    g = {k: v for k, v in handoff.GRADE_PAST["past"].items()}
    w = 1.0 - smooth(t, T0, 41.35)
    noon = 1.0 - smooth(t, 48.1, 48.8)
    g["exposure"] = 1.0 + 0.10 * noon + 2.6 * w ** 1.6
    g["halation"] = 1.2 + 0.4 * noon + 2.5 * w
    g["halation_threshold"] = 0.85
    # 明亮平整的天空最显颗粒（过去的调色里颗粒随亮度增强）：44.4–48.3 秒把颗粒降到标准值的 0.6 倍，
    # 进屋以后回到标准值，交接帧与 handoff.GRADE_PAST 一致
    bright = smooth(t, 43.9, 44.4) * (1.0 - smooth(t, 48.70, 49.60))
    g["grain"] = GRADE_DEFAULTS["past"]["grain"] * (1.0 - 0.4 * bright)
    if t < 45.0:
        fade = (1.0 - ramp(t, T0, 40.80)) ** 2.2
        return {"past": g, "final": {"fade": fade, "fade_color": handoff.WARM_WHITE}}
    fade = smooth(t, 50.82, T_DARK)
    return {"past": g, "final": {"fade": fade, "fade_color": handoff.DARK}}


# ---------------------------------------------------------------- 各部分

def l05(t):
    if t > 45.6:
        return []
    items = []
    items += C.sheet_items(t, light_l05(t), GT, burn_p=A.burn_p(t))
    items += C.rope_items(t)
    items += C.peg_items(t)
    return items


def cam_y(t):
    return CAM.state(t)[1]


def ash(t):
    return A.items(t, cam_y)


def backdrop(t):
    if B.revealed(t):
        return []
    items = Y.sky_items(t)
    items += Y.far_cloud_items(t)
    items += Y.cloud_items(t, focus=smooth(t, 44.2, 45.4))
    items += S.old_items(t, k=smooth(t, 45.0, 45.8) * (1 - smooth(t, 47.80, 48.10)))
    bo = 1.0 - smooth(t, 44.45, 45.15)
    items += Y.building_items(t, opacity=bo)
    return items


def l06(t):
    return S.knight_items(t) + S.front_cloud_items(t) + S.mist_items(t) + S.text_items(t)


def l07(t):
    if t < 47.3:
        return []
    light = B.light_state(t)
    items = B.bed_items(t, light)
    items += B.text_items(t)
    items += F.knife_items(t, light)
    items += B.pillow_items(t, light)
    return items


def fall(t):
    return F.lance_items(t) + F.wisp_items(t, CAM) + F.whiteout_items(t, CAM)


SCENES = [backdrop, l05, ash, l06, l07, fall]


def frame(t):
    if t < T0 + 0.5 / 60:
        return handoff.white_frame(t, handoff.WARM_WHITE)
    if t >= T_DARK:
        return handoff.dark_frame(t)
    cam, H = CAM(t)
    if B.T_SWITCH <= t < 48.86:
        # 白光散开时焦点由虚到实：景深从约 16 像素（1080 高时）收到 0，对焦距离放到无穷远
        k = 1.0 - float(ease(ramp(t, F.T_OUT0 - 0.02, 48.85)))
        d = H * K - 0.5
        cam = Cam(eye=cam.eye, target=cam.target, up=cam.up, fov=cam.fov, near=cam.near, far=cam.far,
                  dof=16.0 * d / 2015.0 * k, focus=1e6)
    items = []
    for sc in SCENES:
        items += sc(t)
    return FrameSpec(cam, items, grade=grade(t))


def report():
    """速度检查。CAM.report() 量的是 z = 0（云、骑士、枕头）；L05 的主体在 z = 24，另按那一层的画面高换算。"""
    CAM.report(T0, T1)
    for z, a, b, name in ((Z_SHEET, T0, 45.0, "被单层 z=24"), (Z_BUILD, T0, 45.6, "楼 z=16")):
        ts = np.arange(a, b, 1 / 60)
        st = np.array([CAM.state(t)[:3] for t in ts])
        Hz = st[:, 2] - z / K
        v = np.hypot(np.gradient(st[:, 0], 1 / 60), np.gradient(st[:, 1], 1 / 60)) / Hz
        zz = np.abs(np.gradient(np.log(Hz), 1 / 60))
        print(f"{name}：平移峰值 {v.max():.2f} 画面高/秒（{ts[v.argmax()]:.2f} s），推拉峰值 {zz.max():.2f}/秒（{ts[zz.argmax()]:.2f} s）")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "report":
        report()
        sys.exit()
    run(frame, "B段", T0, T1, RENDERS)
