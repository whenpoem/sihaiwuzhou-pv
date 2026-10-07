"""L26 的尖塔残影：副歌一那座展览馆尖塔，今天只剩一个淡淡的轮廓，像屏幕上的烧屏残影一样印在夜空里。

素材取自副歌一 scripts/seg_c/spire.py 已经算好的建筑反照率贴图（data/cache/seg_c 里的缓存，只读）：塔楼和尖塔
那一段（建筑坐标 x −8.5–8.5、y 24–80）的外轮廓画成一线冷白的细线，楼面上由小字排成的明暗（拱门、窗洞、塔身分段）
模糊成一层很淡的影子；塔顶的五角星只剩褪色红的轮廓，塔基的"中蘇友誼萬歲"是褪色红的淡字。红色只属于旧字。
贴图是预乘的发光 RGBA，场景里按 opacity 控制浓淡（15%–25%）。
"""
import sys

import cv2
import numpy as np

from f_common import CACHE, ROOT, SCRIPTS, RED, cached, disk_cached
import look

sys.path.append(str(SCRIPTS / "seg_c"))
import spire as SP  # noqa: E402

SRC = ROOT / "data" / "cache" / "seg_c"
REGION = (-16.0, 22.0, 16.0, 83.5)             # 建筑坐标里取用的范围（塔楼、尖塔、五角星）
PPU = 48                                    # 与建筑贴图相同的每单位像素数


def _tower():
    a = np.load(SRC / "spire_v1_building_albedo.npy").astype(np.float32)
    bx0 = SP.BUILDING["center"][0] - SP.BUILDING["size"][0] / 2
    x0, y0, x1, y1 = REGION
    c0, c1 = int((x0 - bx0) * PPU), int((x1 - bx0) * PPU)
    r0, r1 = int((80.0 - min(y1, 80.0)) * PPU), int((80.0 - y0) * PPU)
    crop = a[r0:r1, c0:c1]
    pad = int((y1 - 80.0) * PPU)
    crop = np.vstack([np.zeros((pad, crop.shape[1], 4), np.float32), crop])
    alpha = crop[..., 3]
    lum = crop[..., :3].mean(2) * alpha
    # 外轮廓：alpha 的形态学梯度，一两个像素宽
    m = (alpha > 0.5).astype(np.uint8)
    edge = cv2.morphologyEx(m, cv2.MORPH_GRADIENT, np.ones((3, 3), np.uint8)).astype(np.float32)
    edge = cv2.GaussianBlur(edge, (0, 0), 0.8)
    # 楼面明暗：小字的疏密模糊成影子，再提一点对比
    shade = cv2.GaussianBlur(lum, (0, 0), 2.2)
    shade = np.clip((shade - 0.08) * 1.6, 0, 1) * alpha
    # 五角星：只留褪色红的轮廓
    st = np.load(SRC / "spire_v1_star.npz")["body"].astype(np.float32)
    sa = st[..., 3]
    sm = (sa > 0.5).astype(np.uint8)
    sedge = cv2.morphologyEx(sm, cv2.MORPH_GRADIENT, np.ones((5, 5), np.uint8)).astype(np.float32)
    sedge = cv2.GaussianBlur(sedge, (0, 0), 1.2)
    sc, ss = SP.STAR["center"], SP.STAR["size"]
    w = int(ss[0] * PPU)
    sedge = cv2.resize(sedge, (w, w), interpolation=cv2.INTER_AREA)
    sfill = cv2.resize(sa, (w, w), interpolation=cv2.INTER_AREA)
    star = np.zeros_like(alpha)
    starf = np.zeros_like(alpha)
    cx = int((sc[0] - x0) * PPU) - w // 2
    cy = int((y1 - sc[1]) * PPU) - w // 2
    ys, xs = max(cy, 0), max(cx, 0)
    ye, xe = min(cy + w, star.shape[0]), min(cx + w, star.shape[1])
    star[ys:ye, xs:xe] = sedge[ys - cy:ye - cy, xs - cx:xe - cx]
    starf[ys:ye, xs:xe] = sfill[ys - cy:ye - cy, xs - cx:xe - cx]
    # 星所在处不画塔的线，免得白线压在红星上
    keep = 1 - np.clip(starf * 1.5, 0, 1)
    white = (edge * 1.1 + shade * 0.5) * keep
    rgb = white[..., None] * np.array([0.82, 0.90, 1.0]) + (star * 0.8 + starf * 0.15)[..., None] * RED * 1.5
    a_ = np.clip(white + star + starf * 0.2, 0, 1)
    return np.dstack([rgb, a_]).astype(np.float16)


def tower_tex():
    from engine import Tex
    return cached("ghost_tower", lambda: Tex(disk_cached("ghost_tower_v3", _tower).astype(np.float32),
                                             premultiplied=True))


def veil_tex():
    """残影的暗影：塔楼与尖塔的剪影（边缘略散开），黑色。叠在城市上，把残影背后的灯光压暗一层，白色的轮廓线和
    红色的字因此在明亮的楼群前面也读得清。"""
    def make():
        from engine import Tex
        a = np.load(SRC / "spire_v1_building_albedo.npy").astype(np.float32)[..., 3]
        bx0 = SP.BUILDING["center"][0] - SP.BUILDING["size"][0] / 2
        x0, y0, x1, y1 = REGION
        c0, c1 = int((x0 - bx0) * PPU), int((x1 - bx0) * PPU)
        r0, r1 = int((80.0 - min(y1, 80.0)) * PPU), int((80.0 - y0) * PPU)
        crop = a[r0:r1, c0:c1]
        pad = int((y1 - 80.0) * PPU)
        crop = np.vstack([np.zeros((pad, crop.shape[1]), np.float32), crop])
        m = cv2.GaussianBlur(crop, (0, 0), 3.0)
        return Tex(np.dstack([np.zeros(m.shape + (3,), np.float32), m]).astype(np.float32), premultiplied=True)
    return cached("ghost_veil3", make)


BANNER_K = 1.5                                    # 残影横幅相对原横幅放大的倍数：字要一眼读得出


def banner_tex():
    """塔基横幅的位置上只剩褪色红的"中蘇友誼萬歲"（思源宋体 900，横向放宽，与副歌一的横幅同一字形），字占横幅高度的
    八成多，边缘略散开；字后面是一块很淡的暗色布影（横幅原来的布），让红字在灯光前也看得清。"""
    def make():
        from engine import Tex
        bw, bh = SP.BANNER["size"]
        W, H = int(bw * 60), int(bh * 60)
        f = look.font("serif", 900, H * 0.84, scale_x=1.12)
        s = look.trad("中苏友谊万岁")
        tw = f.measureText(s)
        g = look.text_layer([(s, f, (W - tw) / 2, H * 0.82, None)], W, H)
        g = cv2.GaussianBlur(g, (0, 0), 1.4)
        yy, xx = np.mgrid[0:H, 0:W] / np.array([H - 1, W - 1])[:, None, None]
        cloth = np.clip(np.minimum.reduce([xx, 1 - xx, yy, 1 - yy]) / 0.06, 0, 1) * 0.55
        rgb = g[..., None] * RED * 1.45
        a = np.clip(g + cloth * (1 - g), 0, 1)
        return Tex(np.dstack([rgb, a]).astype(np.float32), premultiplied=True)
    return cached("ghost_banner2", make)


def items(origin, scale, opacity, z=0.05, banner_op=None, veil_op=0.0, group="present"):
    """尖塔残影的平面：origin 为建筑坐标原点（底边中点）在世界里的位置，scale 为缩放。banner_op 为横幅的
    不透明度（缺省同 opacity），veil_op 为暗影的不透明度。"""
    from engine import Plane
    x0, y0, x1, y1 = REGION
    c = (origin[0] + (x0 + x1) / 2 * scale, origin[1] + (y0 + y1) / 2 * scale, z)
    size = ((x1 - x0) * scale, (y1 - y0) * scale)
    out = []
    if veil_op > 0:
        out.append(Plane(veil_tex(), center=(c[0], c[1], z - 0.002), size=size, opacity=veil_op, group=group))
    out.append(Plane(tower_tex(), center=c, size=size, opacity=opacity, group=group))
    bc, bs = SP.BANNER["center"], SP.BANNER["size"]
    out.append(Plane(banner_tex(), center=(origin[0] + bc[0] * scale, origin[1] + bc[1] * scale, z + 0.001),
                     size=(bs[0] * scale * BANNER_K, bs[1] * scale * BANNER_K),
                     opacity=opacity if banner_op is None else banner_op, group=group))
    return out


def star_top():
    """五角星上顶点的建筑坐标。"""
    return np.array([0.0, 80.0])
