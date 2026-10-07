"""L30 的地球：一团高速旋转的白色细字。

副歌一后半（D 段）的地球是着色器里画出的实心球，字带上的字不停翻换，其中一条是红色的旧字。今天的地球只剩字：
雨窗上的雾原来是一粒粒极小的白字，"她"时它们离开玻璃、卷成一个球，按纬度一圈圈排开，绕着倾斜的极轴飞快地转。
字始终正对观众，离得远的（球背面的）暗、近的亮，所以看得出是一个球在转。赤道以北一圈是褪色红的旧字
"世界是你們的　也是我們的　但是歸根結底是你們的"，只剩残影（不透明度约 20%），随球一起转。
"""
import math

import numpy as np

from f_common import RED, cached
import look

R_ROW = 5.0                     # 纬度圈的间距（度）
N_EQ = 104                      # 赤道一圈的字数
TILT = math.radians(23.5)       # 极轴向画面右侧倾斜
OLD = look.trad("世界是你们的　也是我们的　但是归根结底是你们的　")
RED_LAT = 17.5


def pool():
    return "".join(dict.fromkeys("".join(look.lyric(n) for n in range(1, 41)).replace("　", "")))


def atlas():
    from engine import glyph_atlas
    return cached("globe_atlas", lambda: glyph_atlas(pool(), "serif", 300, cell=96))


def red_atlas():
    from engine import glyph_atlas
    return cached("globe_atlas_red", lambda: glyph_atlas("".join(dict.fromkeys(OLD.replace("　", ""))), "fang", 400, cell=128))


def layout():
    """球面上每个字的 (纬度, 经度)（弧度）、字的序号、是否在红色旧字那一圈。"""
    def make():
        rng = np.random.default_rng(30)
        P = pool()
        lat, lon, idx = [], [], []
        for la in np.arange(-80, 80.01, R_ROW):
            if abs(la - RED_LAT) < 2.0:
                continue
            n = max(6, int(round(N_EQ * math.cos(math.radians(la)))))
            off = rng.uniform(0, 2 * np.pi)
            for j in range(n):
                lat.append(math.radians(la))
                lon.append(off + 2 * np.pi * j / n)
                idx.append(int(rng.integers(0, len(P))))
        red = [(c, math.radians(RED_LAT), 2 * np.pi * j / len(OLD)) for j, c in enumerate(OLD)]
        return np.array(lat), np.array(lon), np.array(idx), red
    return cached("globe_layout", make)


def sphere_points(lat, lon, spin):
    """球面上的点（单位球）绕倾斜的极轴转 spin 弧度后在世界里的方向 (x, y, z)，z 朝向观众。"""
    x = np.cos(lat) * np.sin(lon + spin)
    z = np.cos(lat) * np.cos(lon + spin)
    y = np.sin(lat)
    c, s = math.cos(TILT), math.sin(TILT)
    return np.stack([x * c + y * s, -x * s + y * c, z], -1)
