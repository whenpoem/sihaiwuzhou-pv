"""封面：繁体大字"四海五洲"横贯画面，从一架老式地球仪的铜子午圈里穿过。

图形取地球仪，因为"四海五洲"出自的那首词开头就是"小小寰球"。画面是一张旧纸作背景，台灯从左上方照下来；
地球仪在画面中央，地图只画海陆、地形色和经纬线，不画国界和地名。四个字（思源宋体粗体，朱红色）从球前经过，
铜圈在左侧压在"海"字上面，在右侧从"五"字后面绕过去，所以这一行字看上去是从环里穿过去的。字在球面上投下
弯曲的影子，球面的弧度靠影子显出来。字下面按片子"字下有字"的做法，淡淡印着褪色红的"四海翻騰雲水怒　五洲
震盪風雷激"，被地球仪的支架从全角空格处隔开。B 站封面是 16:10，右下角会被时长标签盖住，构图避开那里。

画面按层合成，而不是做严格的三维渲染：背景纸 → 球的投影 → 球 → 铜圈后半 → 字 → 铜圈前半。各层之间的
影子按假定的前后距离偏移和模糊，球面上的影子按球面到字所在平面的距离逐点计算。

    python cover.py            输出 renders/cover/封面.png（3200×2000）和缩小的 封面_小.png
"""
import math
import sys
from pathlib import Path

import numpy as np
import skia
from PIL import Image
from scipy.ndimage import gaussian_filter, map_coordinates

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "style"))
import look  # noqa: E402

IMG = ROOT / "assets" / "images"
OUT = ROOT / "renders" / "cover"
W, H = 3200, 2000

INK = np.array([0.66, 0.11, 0.07], np.float32)          # 字取老标语的朱红，比片名的墨褐醒目，压在浅色球面上也清楚
RED = np.array(look.C["red"], np.float32)
BRASS = np.array([0.78, 0.60, 0.30], np.float32)

# 构图（像素，y 向下）
CX, CY = 1600, 960            # 地球仪中心
R = 540                       # 球半径
TILT = math.radians(23.5)     # 地轴向右倾
LAT0, LON0 = math.radians(22), math.radians(108)   # 正对观众的经纬度：中国一带
RR, RW = 1.13 * R, 0.085 * R  # 铜圈半径与宽度
RING_TURN = math.radians(-16)  # 铜圈绕地轴转开的角度，负值时左半在前
TITLE = "四海五洲"
EM = 700                      # 字号
PITCH = 735                   # 字距
WEIGHT = 850
OLD = ("四海翻騰雲水怒", "五洲震盪風雷激")
LIGHT = np.array([-0.52, 0.58, 0.63])           # 指向台灯（x 右、y 上、z 朝观众）
LIGHT /= np.linalg.norm(LIGHT)
LAMP_XY = (700, 250)          # 台灯光斑中心

yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)


def blur(a, s):
    return gaussian_filter(a, s) if s > 0 else a


def shift(a, dx, dy, order=1):
    """把图层平移 (dx, dy) 像素（向右、向下为正），用于投影。"""
    return map_coordinates(a, [yy - dy, xx - dx], order=order, mode="constant", cval=0.0)


# ---------------------------------------------------------------- 背景纸与台灯

def lamp():
    d2 = ((xx - LAMP_XY[0]) ** 2 + (yy - LAMP_XY[1]) ** 2) / (2300.0 ** 2)
    return (0.42 + 0.78 * np.exp(-d2 * 2.2)).astype(np.float32)


def paper():
    im = Image.open(IMG / "Old_paper7.jpg").convert("RGB")
    im = im.resize((int(im.width * W / im.width * 1.0), int(im.height * W / im.width)), Image.LANCZOS)
    a = np.asarray(im, np.float32)[:H, :W] / 255.0
    if a.shape[0] < H:
        a = np.vstack([a, a[::-1][: H - a.shape[0]]])
    lum = a.mean(axis=2, keepdims=True)
    tex = 1.0 + 0.9 * (lum - lum.mean())          # 只取纸的明暗纹理，颜色统一成旧纸黄
    return np.array(look.C["paper"], np.float32) * tex


# ---------------------------------------------------------------- 字

def glyph_masks():
    """四个字的遮罩，以及每个字的外框（用来判断铜圈压在哪个字上）。"""
    s = look.surface(W, H)
    c = s.getCanvas()
    f = look.font("serif", WEIGHT, EM)
    for k, ch in enumerate(TITLE):
        b = skia.Rect()
        f.measureText(ch, bounds=b)
        x = CX + (k - 1.5) * PITCH - b.width() / 2 - b.left()
        y = CY - b.height() / 2 - b.top()
        c.drawString(ch, x, y, f, look.white_paint())
    return look.to_np(s)[..., 3]


def old_line_mask():
    s = look.surface(W, H)
    c = s.getCanvas()
    f = look.font("fang", 400, 84)
    for k, txt in enumerate(OLD):
        wsum = sum(f.measureText(ch) for ch in txt)
        gap = 0.16 * 84
        total = wsum + gap * (len(txt) - 1)
        x0 = (CX - 160 - total) if k == 0 else CX + 160
        y = 1748
        for ch in txt:
            c.drawString(ch, x0, y, f, look.white_paint())
            x0 += f.measureText(ch) + gap
    return look.to_np(s)[..., 3]


# ---------------------------------------------------------------- 地球仪

def globe_texture():
    """老式地球仪的地图：海是褪色的青蓝，陆地按原图的明暗染成赭黄到橄榄绿，画海岸线和每 15° 一条的经纬线。"""
    a = np.asarray(Image.open(IMG / "Whole_world_-_land_and_oceans.jpg").convert("RGB"), np.float32) / 255.0
    r, g, b = a[..., 0], a[..., 1], a[..., 2]
    ocean = ((b > r + 0.04) & (b > g - 0.02) & (a.mean(axis=2) < 0.45)).astype(np.float32)
    ocean = gaussian_filter(ocean, 1.2)
    land = 1.0 - ocean
    lum = a.mean(axis=2)
    green = np.clip((g - r) * 6 + 0.5, 0, 1)
    ochre = np.array([0.90, 0.80, 0.58])
    olive = np.array([0.74, 0.76, 0.54])
    snow = np.array([0.93, 0.91, 0.85])
    lc = ochre * (1 - green[..., None]) + olive * green[..., None]
    lc = lc * (0.82 + 0.45 * (lum[..., None] - 0.3))
    lc = lc * (1 - np.clip((lum - 0.75) * 4, 0, 1)[..., None]) + snow * np.clip((lum - 0.75) * 4, 0, 1)[..., None]
    deep = gaussian_filter(1 - lum, 8)
    oc = np.array([0.70, 0.81, 0.80]) * (1.02 - 0.10 * deep[..., None])
    col = oc * ocean[..., None] + lc * land[..., None]
    coast = np.clip(np.abs(gaussian_filter(land, 1.0) - gaussian_filter(land, 3.0)) * 5, 0, 1)
    col = col * (1 - 0.45 * coast[..., None])
    hh, ww = lum.shape
    lat = (0.5 - (np.arange(hh) + 0.5) / hh) * 180
    lon = ((np.arange(ww) + 0.5) / ww - 0.5) * 360
    gl = np.zeros((hh, ww), np.float32)
    for v in range(-75, 90, 15):
        gl[np.abs(lat - v) < (0.22 if v else 0.40)] = 1.0
    for v in range(-180, 180, 15):
        gl[:, np.abs(lon - v) < 0.22] = 1.0
    col = col * (1 - 0.30 * gl[..., None])
    return col.astype(np.float32)


def globe_layer(tex):
    """球：正投影，按经纬度取地图，加台灯的漫反射、清漆的高光和泛黄。返回颜色、遮罩、球面深度。"""
    dx, dy = (xx - CX) / R, -(yy - CY) / R
    r2 = dx * dx + dy * dy
    inside = r2 < 1.0
    nz = np.sqrt(np.clip(1 - r2, 0, 1))
    # 转到地球坐标：先去掉地轴的倾斜，再把 LAT0 转到正前方
    c, s = math.cos(TILT), math.sin(TILT)
    x1, y1 = dx * c - dy * s, dx * s + dy * c
    ce, se = math.cos(-LAT0), math.sin(-LAT0)
    y2, z2 = y1 * ce - nz * se, y1 * se + nz * ce
    lat = np.arcsin(np.clip(y2, -1, 1))
    lon = LON0 + np.arctan2(x1, z2)
    th, tw = tex.shape[:2]
    u = ((lon / (2 * np.pi) + 0.5) % 1.0) * tw - 0.5
    v = (0.5 - lat / np.pi) * th - 0.5
    col = np.dstack([map_coordinates(tex[..., k], [v, u], order=1, mode="wrap") for k in range(3)])
    n = np.dstack([dx, dy, nz])
    ndl = np.clip((n * LIGHT).sum(axis=2), 0, 1)
    hv = LIGHT + np.array([0, 0, 1.0])
    hv /= np.linalg.norm(hv)
    ndh = np.clip((n * hv).sum(axis=2), 0, 1)
    shade = 0.50 + 0.66 * ndl
    col = col * shade[..., None] * np.array([1.0, 0.95, 0.84])          # 清漆泛黄
    col = col + (0.38 * ndh ** 90 + 0.07 * ndh ** 10)[..., None] * np.array([1.0, 0.95, 0.85])
    col = col * (1 - 0.18 * (1 - nz) ** 3)[..., None]
    rng = np.random.default_rng(23)
    dirt = gaussian_filter(rng.normal(0, 1, (H // 4, W // 4)).astype(np.float32), 3)
    dirt = np.kron(dirt, np.ones((4, 4), np.float32))[:H, :W]
    col = col * (1 + 0.04 * dirt[..., None])
    edge = np.clip((1 - np.sqrt(r2)) * R / 1.5, 0, 1)                   # 边缘抗锯齿
    return col.astype(np.float32), (edge * inside).astype(np.float32), nz


def ring_layer():
    """铜子午圈：在包含地轴的平面里的一圈扁平铜带，正面刻着度数。返回前半与后半的颜色和遮罩。"""
    a = np.array([math.sin(TILT), math.cos(TILT), 0.0])                  # 地轴（屏幕坐标，y 向上）
    p = np.array([math.cos(TILT), -math.sin(TILT), 0.0])
    u = math.cos(RING_TURN) * p + np.array([0, 0, math.sin(RING_TURN)])
    M = np.array([[a[0], u[0]], [a[1], u[1]]])
    Mi = np.linalg.inv(M)
    X, Y = xx - CX, -(yy - CY)
    sa = Mi[0, 0] * X + Mi[0, 1] * Y
    tu = Mi[1, 0] * X + Mi[1, 1] * Y
    rho = np.sqrt(sa * sa + tu * tu)
    phi = np.degrees(np.arctan2(tu, sa)) % 360                        # 从北极起算
    d = np.abs(rho - RR)
    band = np.clip((RW / 2 - d) / 1.5 + 0.5, 0, 1)
    # 铜带：中间平、两边的圆角亮一些，加拉丝纹和整体随角度变化的明暗
    edge = np.clip(d / (RW / 2), 0, 1)
    bevel = np.clip((edge - 0.70) / 0.30, 0, 1)
    rng = np.random.default_rng(5)
    brush = map_coordinates(gaussian_filter(rng.normal(0, 1, 4000).astype(np.float32), 1.5),
                            [((rho - RR + RW) * 25) % 4000], order=1, mode="wrap")
    ang = np.radians(phi)
    # 圈上各处朝向不同，用圈的切向和台灯的关系近似金属的明暗
    tang = -np.sin(ang)[..., None] * a + np.cos(ang)[..., None] * u
    glint = np.abs((tang * LIGHT).sum(axis=-1))
    lum = 0.55 + 0.35 * (1 - glint) ** 2 + 0.45 * bevel * (1 - glint) + 0.05 * brush
    col = BRASS[None, None, :] * lum[..., None]
    col = col + (0.5 * np.clip(1 - glint * 3.0, 0, 1) ** 4 * (0.4 + 0.6 * bevel))[..., None] * np.array([1.0, 0.9, 0.7])
    # 刻度：每 5° 一道短刻线，每 10° 一道长刻线
    tick = np.zeros_like(rho)
    for step, length in ((5, 0.35), (10, 0.60)):
        dphi = np.abs(((phi + step / 2) % step) - step / 2) * np.pi / 180 * rho
        on = (dphi < 1.6) & (rho > RR + RW / 2 - RW * length) & (rho < RR + RW / 2 - RW * 0.08)
        tick = np.maximum(tick, on.astype(np.float32))
    col = col * (1 - 0.55 * blur(tick, 0.6)[..., None])
    z = tu * math.sin(RING_TURN)
    front = (z > 0).astype(np.float32)
    front = blur(front, 1.0)
    return col.astype(np.float32), band * front, band * (1 - front), a, u


def stand_layer(a, u):
    """支架：从铜圈最低点向下的一根车削木柱，被画面下边截断；两极处各有一颗铜轴钉。"""
    s = look.surface(W, H)
    c = s.getCanvas()
    # 铜圈最低点
    best = None
    for k in range(3600):
        ph = math.radians(k / 10)
        v = RR * (math.cos(ph) * a + math.sin(ph) * u)
        if best is None or v[1] < best[1]:
            best = v
    bx, by = CX + best[0], CY - best[1]
    path = skia.Path()
    w0, w1 = 46, 70
    path.moveTo(bx - w0 / 2, by - 6)
    path.lineTo(bx + w0 / 2, by - 6)
    path.cubicTo(bx + w0 / 2, by + 80, bx + w1 / 2 + 30, by + 120, bx + w1 / 2, by + 200)
    path.lineTo(bx + w1 / 2 + 6, H + 10)
    path.lineTo(bx - w1 / 2 - 6, H + 10)
    path.lineTo(bx - w1 / 2, by + 200)
    path.cubicTo(bx - w1 / 2 - 30, by + 120, bx - w0 / 2, by + 80, bx - w0 / 2, by - 6)
    c.drawPath(path, look.white_paint())
    collar = skia.Rect.MakeXYWH(bx - 50, by - 24, 100, 40)
    c.drawRoundRect(collar, 10, 10, look.white_paint())
    m = look.to_np(s)[..., 3]
    # 木柱：深褐，左亮右暗
    t = np.clip((xx - (bx - w1)) / (2 * w1), 0, 1)
    wood = np.array([0.30, 0.18, 0.10]) * (1.25 - 0.8 * t)[..., None]
    wood = wood + (0.18 * np.exp(-((t - 0.32) / 0.08) ** 2))[..., None] * np.array([1, 0.85, 0.6])
    # 轴钉
    s2 = look.surface(W, H)
    c2 = s2.getCanvas()
    for sign in (1, -1):
        v = sign * (R + 0.6 * (RR - R)) * a
        c2.drawCircle(CX + v[0], CY - v[1], 20, look.white_paint())
        v2 = sign * R * a
        p2 = skia.Paint(AntiAlias=True, Color=skia.Color4f(1, 1, 1, 1), StrokeWidth=14,
                        Style=skia.Paint.kStroke_Style)
        c2.drawLine(CX + v2[0], CY - v2[1], CX + sign * RR * a[0], CY - sign * RR * a[1], p2)
    pins = look.to_np(s2)[..., 3]
    return wood.astype(np.float32), m.astype(np.float32), pins.astype(np.float32)


# ---------------------------------------------------------------- 合成

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    L = lamp()
    img = paper()
    old = old_line_mask()
    img = img * (1 - 0.72 * old[..., None] * (1 - RED[None, None, :]))          # 褪色红印在纸上（正片叠底）
    gm = glyph_masks()
    tex = globe_texture()
    gcol, gmask, gz = globe_layer(tex)
    rcol, rfront, rback, a, u = ring_layer()
    wood, smask, pins = stand_layer(a, u)

    # 背景上的投影：球、支架、铜圈、字，光从左上方来，影子落向右下
    sh_bg = np.maximum.reduce([
        0.50 * blur(shift(gmask, 150, 170), 55),
        0.40 * blur(shift(np.maximum(smask, pins), 120, 140), 30),
        0.40 * blur(shift(np.maximum(rfront, rback), 130, 150), 22),
        0.45 * blur(shift(gm, 95, 105), 26),
    ])
    img = img * (1 - sh_bg[..., None])

    # 支架与轴钉
    img = img * (1 - smask[..., None]) + wood * smask[..., None]
    pin_col = BRASS * 0.9
    img = img * (1 - pins[..., None]) + pin_col * pins[..., None]
    # 铜圈后半
    img = img * (1 - rback[..., None]) + rcol * rback[..., None]
    # 球，球面上有字和铜圈前半的影子：偏移随球面到字所在平面的距离增大（越靠近边缘越远），模糊也随之增大
    gap = 24 + 0.22 * R * (1 - gz)
    ox, oy = gap * 0.85, gap * 0.95
    sharp = map_coordinates(gm, [yy - oy, xx - ox], order=1, mode="constant")
    soft = map_coordinates(blur(gm, 12), [yy - oy, xx - ox], order=1, mode="constant")
    wsoft = np.clip((gap - 18) / 90, 0, 1)
    sh_g = 0.38 * (blur(sharp, 2.5) * (1 - wsoft) + soft * wsoft)
    ring_sh = map_coordinates(blur(rfront, 6), [yy - oy * 0.5, xx - ox * 0.5], order=1, mode="constant")
    sh_g = np.maximum(sh_g, 0.45 * ring_sh)
    gc = gcol * (1 - sh_g[..., None])
    img = img * (1 - gmask[..., None]) + gc * gmask[..., None]
    # 铜圈后半在球外的部分已画；球前面只有前半

    # 台灯照明乘在以上各层上
    img = img * L[..., None] * np.array([1.06, 1.0, 0.90])

    # 字：墨褐，印在一层薄纸上的质感（细颗粒、墨色深浅），上方受光略亮；字上有铜圈前半的影子
    rng = np.random.default_rng(1964)
    grain = gaussian_filter(rng.normal(0, 1, (H, W)).astype(np.float32), 1.2)
    mott = gaussian_filter(rng.normal(0, 1, (H // 8, W // 8)).astype(np.float32), 4)
    mott = np.kron(mott, np.ones((8, 8), np.float32))[:H, :W]
    inkc = INK[None, None, :] * (1 + 0.10 * grain[..., None] + 0.12 * mott[..., None])
    inkc = inkc * (0.88 + 0.22 * L[..., None])
    rim = np.clip(gm - shift(gm, 3, 3), 0, 1)                         # 左上边缘受光的一道细亮边
    inkc = inkc + 0.10 * rim[..., None]
    rsh = 0.45 * blur(shift(rfront, 26, 30), 7)
    inkc = inkc * (1 - rsh[..., None])
    img = img * (1 - gm[..., None]) + inkc * gm[..., None]

    # 铜圈前半，受台灯照明
    rf = rcol * (0.75 + 0.35 * L[..., None])
    img = img * (1 - rfront[..., None]) + rf * rfront[..., None]

    # 胶片质感：高光的光晕、暗角、颗粒
    lum = img.mean(axis=2)
    halo = blur(np.clip(lum - 0.85, 0, 1), 18)
    img = img + 0.35 * halo[..., None] * np.array([1.0, 0.75, 0.5])
    r2 = ((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2
    img = img * (1.04 - 0.30 * r2 ** 1.3)[..., None]
    img = img + 0.018 * rng.normal(0, 1, (H, W, 1)).astype(np.float32)
    img = np.clip(img, 0, 1)
    out = Image.fromarray((img * 255 + 0.5).astype(np.uint8))
    out.save(OUT / "封面.png")
    out.resize((1146, 716), Image.LANCZOS).save(OUT / "封面_小.png")
    print(OUT / "封面.png")


if __name__ == "__main__":
    main()
