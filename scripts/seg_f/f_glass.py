"""L28 的玻璃：镜头前一块玻璃，"摔"时从中心裂开、裂纹向四周放射，"碎"时碎成几十块落下。

副歌一的 L14 在水下，"中蘇友誼萬歲"的横幅从中间裂开、碎成四十块沉进裂沟。今天碎的是一块玻璃。真实的钢化前
的平板玻璃受到点冲击时，先从冲击点放射出十几条径向裂纹，再在径向裂纹之间出现一圈圈同心的环向裂纹，把玻璃分成
内小外大的扇形碎块。这里按这个结构生成裂纹：径向裂纹是从冲击点出发、带随机折角的折线，环向裂纹是相邻两条径向
裂纹之间的一段锯齿弧，碎块就是径向与环向裂纹围出的格子。

玻璃本身看不见，看得见的是光在它上面的变化：裂纹的断面把光散射成一条亮线，紧挨着亮线有一道因折射而发暗的边；
每一块碎玻璃的倾角略有不同，反射的城市灯光亮度也不同（一层很淡的光泽）；完整的玻璃有一层极淡的冷色。贴图在
"玻璃坐标"里画出：原点在冲击点，单位是世界长度，y 向上。
"""
import math

import cv2
import numpy as np
import skia

from f_common import cached

GW, GH = 5.4, 3.2                       # 玻璃的宽、高（世界单位）
PPU = 700                               # 贴图每世界单位的像素数
N_RAD = 14
RING_KEEP = [1.0, 0.92, 0.62, 0.36, 0.18, 0.08]    # 各圈环向裂纹裂开的比例：越往外越稀
RINGS = [0.06, 0.13, 0.24, 0.40, 0.64, 1.0]


def _jag(p0, p1, n, amp, rng):
    """p0 到 p1 之间带随机折角的折线（n 段）。"""
    t = np.linspace(0, 1, n + 1)[:, None]
    pts = p0 + (p1 - p0) * t
    d = (p1 - p0) / (np.linalg.norm(p1 - p0) + 1e-9)
    nrm = np.array([-d[1], d[0]])
    off = np.cumsum(rng.normal(0, amp, n + 1))
    off -= np.linspace(off[0], off[-1], n + 1)
    pts += nrm * off[:, None]
    return pts


def geometry(seed=28):
    """裂纹与碎块：radials 为每条径向裂纹的折线（极坐标 r 递增），shards 为碎块多边形列表（玻璃坐标），
    rings 为环向裂纹的折线（附各自的半径）。"""
    def make():
        rng = np.random.default_rng(seed)
        ang = np.sort(np.linspace(0, 2 * np.pi, N_RAD, endpoint=False) + rng.uniform(-0.18, 0.18, N_RAD) + 0.2)
        R = [0.0] + RINGS + [4.0]
        # 每条径向裂纹在各个半径上的点（角度随半径缓慢偏转）
        rad_pts = []
        for a in ang:
            drift = np.cumsum(rng.normal(0, 0.05, len(R)))
            pts = [np.array([0.0, 0.0])]
            for j, r in enumerate(R[1:], 1):
                aa = a + drift[j] * 0.6
                pts.append(np.array([r * math.cos(aa), r * math.sin(aa)]))
            rad_pts.append(pts)
        radials = []
        for pts in rad_pts:
            line = [pts[0]]
            for p0, p1 in zip(pts[:-1], pts[1:]):
                seg = _jag(p0, p1, 6, 0.006 + 0.01 * np.linalg.norm(p1) ** 0.5, rng)
                line.extend(seg[1:])
            radials.append(np.array(line))
        # 环向裂纹：相邻两条径向之间的锯齿弧。里面几圈几乎都裂开，往外越来越少，碎块因此内小外大
        ring_lines = []
        arcs, kept = {}, {}
        for j in range(1, len(R) - 1):
            for i in range(N_RAD):
                p0, p1 = rad_pts[i][j], rad_pts[(i + 1) % N_RAD][j]
                mid = (p0 + p1) / 2
                mid = mid / (np.linalg.norm(mid) + 1e-9) * R[j] * rng.uniform(0.97, 1.06)
                pts = np.vstack([_jag(p0, mid, 3, 0.005, rng), _jag(mid, p1, 3, 0.005, rng)[1:]])
                arcs[(i, j)] = pts
                kept[(i, j)] = rng.uniform() < RING_KEEP[min(j - 1, len(RING_KEEP) - 1)]
                if kept[(i, j)]:
                    ring_lines.append((pts, R[j]))
        # 碎块：两条相邻径向裂纹之间、两道裂开的环向裂纹之间的一块；没有裂开的环向不分块
        shards = []
        last = len(R) - 1
        for i in range(N_RAD):
            i2 = (i + 1) % N_RAD
            ja = 0
            while ja < last:
                jb = ja + 1
                while jb < last and not kept[(i, jb)]:
                    jb += 1
                Lp = radials[i][ja * 6: jb * 6 + 1]
                Rp = radials[i2][ja * 6: jb * 6 + 1]
                O = arcs[(i, jb)] if jb < last else np.array([rad_pts[i][jb], rad_pts[i2][jb]])
                parts = [Lp, O[1:-1] if len(O) > 2 else np.zeros((0, 2)), Rp[::-1]]
                if ja >= 1:
                    parts.append(arcs[(i, ja)][::-1][1:-1])
                poly = np.vstack([q for q in parts if len(q)])
                shards.append(dict(poly=poly, ring=ja, sector=i))
                ja = jb
        return dict(radials=radials, rings=ring_lines, shards=shards, R=R)
    return cached(f"glass_geo_{seed}", make)


def _canvas(box, ppu):
    x0, y0, x1, y1 = box
    W, H = int(round((x1 - x0) * ppu)), int(round((y1 - y0) * ppu))
    s = skia.Surface(W, H)
    c = s.getCanvas()
    c.clear(skia.Color4f(0, 0, 0, 0))
    m = skia.Matrix()
    m.setScale(ppu, -ppu)
    m.postTranslate(-x0 * ppu, y1 * ppu)
    c.concat(m)
    return s, c, W, H


def _path(pts, close=False):
    p = skia.Path()
    p.moveTo(float(pts[0][0]), float(pts[0][1]))
    for x, y in pts[1:]:
        p.lineTo(float(x), float(y))
    if close:
        p.close()
    return p





def crack_maps(center_uv=(0.5, 0.5)):
    """完整玻璃上的裂纹贴图（覆盖整块玻璃）：返回 (亮线, 暗边, 每块碎片的透光与光泽, 到冲击点的距离)。
    径向裂纹从冲击点一直延伸到玻璃边缘，近处粗而亮、远处细而淡，中途分出一两条支裂纹；环向裂纹只在里面几圈
    完整，往外越来越稀。紧挨裂纹的一道暗边是断面的折射；每块碎片的倾角略有不同，透过来的光和反射的光泽也不同。"""
    def make():
        g = geometry()
        rng = np.random.default_rng(91)
        cx, cy = (center_uv[0] - 0.5) * GW, (0.5 - center_uv[1]) * GH
        box = (-GW / 2 - cx, -GH / 2 - cy, GW / 2 - cx, GH / 2 - cy)
        ppu = PPU / 2
        s, c, W, H = _canvas(box, ppu)
        for line in g["radials"]:
            r = np.hypot(line[:, 0], line[:, 1])
            for p0, p1, rr in zip(line[:-1], line[1:], r[1:]):
                w = 0.0065 * math.exp(-rr / 0.9) + 0.0022
                k = 0.55 + 0.45 * math.exp(-rr / 0.6)
                c.drawLine(float(p0[0]), float(p0[1]), float(p1[0]), float(p1[1]),
                           skia.Paint(Color=skia.Color4f(k, k, k, 1), AntiAlias=True, StrokeWidth=w,
                                      StrokeCap=skia.Paint.kRound_Cap))
            # 支裂纹
            for _ in range(rng.integers(0, 3)):
                j = int(rng.integers(3, len(line) - 4))
                p0 = line[j]
                ang = math.atan2(p0[1], p0[0]) + rng.choice([-1, 1]) * rng.uniform(0.25, 0.5)
                L = rng.uniform(0.12, 0.5) * (0.5 + np.hypot(*p0))
                p1 = p0 + L * np.array([math.cos(ang), math.sin(ang)])
                br = _jag(p0, p1, 5, 0.006, rng)
                c.drawPath(_path(br), skia.Paint(Color=skia.Color4f(0.6, 0.6, 0.6, 1), AntiAlias=True,
                                                  Style=skia.Paint.kStroke_Style, StrokeWidth=0.0026))
        for pts, r in g["rings"]:
            k = 0.45 + 0.4 * math.exp(-r / 0.3)
            c.drawPath(_path(pts), skia.Paint(Color=skia.Color4f(k, k, k, 1), AntiAlias=True,
                                               Style=skia.Paint.kStroke_Style, StrokeWidth=0.0030))
        # 冲击点：一小圈压碎的白色粉末和密集的细裂纹
        for _ in range(40):
            a0 = rng.uniform(0, 2 * np.pi)
            L = rng.uniform(0.01, 0.05)
            c.drawLine(0, 0, L * math.cos(a0), L * math.sin(a0),
                       skia.Paint(Color=skia.Color4f(0.8, 0.8, 0.8, 1), AntiAlias=True, StrokeWidth=0.0018))
        arr = s.makeImageSnapshot().toarray().astype(np.float32) / 255
        line = arr[..., 3] * arr[..., :3].mean(2)                 # toarray() 为未预乘的颜色
        dark = np.clip(cv2.GaussianBlur((line > 0.05).astype(np.float32), (0, 0), 2.2) * 1.6 - line * 2.0, 0, 1)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        X = box[0] + (xx + 0.5) / ppu
        Y = box[3] - (yy + 0.5) / ppu
        dist = np.hypot(X, Y)
        # 每块碎片的透光与光泽：按扇区和圈数给一个随机值，再沿一个随机方向有一点渐变
        ang = np.arctan2(Y, X)
        sector = np.floor((ang + np.pi) / (2 * np.pi) * N_RAD * 1.0 + 0.3 * np.sin(dist * 9)).astype(int) % N_RAD
        ring = np.searchsorted(np.array(g["R"]), dist)
        hsh = (sector * 7919 + ring * 104729) % 1000 / 1000.0
        hsh2 = (sector * 6037 + ring * 7841) % 1000 / 1000.0
        trans = 1.0 - 0.28 * hsh * np.exp(-dist / 0.9)            # 近处的小碎片倾角大，透过来的光变化也大
        sheen = (0.015 + 0.07 * hsh2 ** 3) * (0.6 + 0.4 * np.cos(X * 3.1 + Y * 2.3 + hsh * 6)) * np.exp(-dist / 1.4)
        return line, dark, trans.astype(np.float32), sheen.astype(np.float32), dist
    return cached("glass_cracks2", make)


def crack_tex(front):
    """裂纹前沿到达半径 front（世界单位）时完整玻璃的两张贴图：发光层（亮线与光泽，预乘 RGBA）和透光层
    （暗边与各碎片的透光，正片叠底）。按前沿量化缓存。"""
    from engine import Tex
    q = round(min(front, 4.0) * 40) / 40
    slot = cached("glass_crack_slot", lambda: {})
    if q not in slot:
        if len(slot) > 40:
            slot.clear()
        line, dark, trans, sheen, dist = crack_maps()
        vis = np.clip((q - dist) / 0.03, 0, 1)
        core = np.exp(-(dist / 0.022) ** 2) * (q > 0.01)
        L = line * vis * 1.25 + core * 0.8
        S = sheen * vis
        rgb = L[..., None] * np.array([1.12, 1.18, 1.28]) + S[..., None] * np.array([0.75, 0.85, 1.0])
        a = np.clip(L, 0, 1)
        glow = Tex(np.dstack([rgb, a]).astype(np.float32), premultiplied=True)
        m = 1.0 - (1.0 - trans) * vis - dark * vis * 0.55
        mul = Tex(np.dstack([m, m, m * 1.02, np.ones_like(m)]).astype(np.float32))
        slot[q] = (glow, mul)
    return slot[q]


def shard_textures(center_uv=(0.5, 0.5), seed=4):
    """每块碎玻璃的贴图与几何：dict(tex, center, size, centroid, ring, sector)。贴图里是这一块的边缘亮线、
    挨着亮线的暗边和一层随机倾角的光泽；坐标为玻璃坐标（原点在冲击点）。"""
    def make():
        from engine import Tex
        g = geometry()
        rng = np.random.default_rng(seed)
        cx, cy = (center_uv[0] - 0.5) * GW, (0.5 - center_uv[1]) * GH
        clip = (-GW / 2 - cx, -GH / 2 - cy, GW / 2 - cx, GH / 2 - cy)
        out = []
        for sh in g["shards"]:
            poly = sh["poly"].copy()
            poly[:, 0] = np.clip(poly[:, 0], clip[0], clip[2])
            poly[:, 1] = np.clip(poly[:, 1], clip[1], clip[3])
            x0, y0 = poly.min(0) - 0.01
            x1, y1 = poly.max(0) + 0.01
            if (x1 - x0) * (y1 - y0) < 1e-4:
                continue
            ppu = PPU / 2 if sh["ring"] >= 4 else PPU * 0.75
            s, c, W, H = _canvas((x0, y0, x1, y1), ppu)
            path = _path(poly, close=True)
            c.drawPath(path, skia.Paint(Color=skia.Color4f(1, 1, 1, 1), AntiAlias=True))
            fill = s.makeImageSnapshot().toarray()[..., 3].astype(np.float32) / 255
            s2, c2, _, _ = _canvas((x0, y0, x1, y1), ppu)
            c2.drawPath(path, skia.Paint(Color=skia.Color4f(1, 1, 1, 1), AntiAlias=True, Style=skia.Paint.kStroke_Style,
                                         StrokeWidth=0.0045))
            edge = s2.makeImageSnapshot().toarray()[..., 3].astype(np.float32) / 255 * fill
            inner = np.clip(cv2.GaussianBlur(edge, (0, 0), 2.5) * 2.0 - edge, 0, 1) * fill
            yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
            ang = rng.uniform(0, np.pi)
            grad = (xx * math.cos(ang) + yy * math.sin(ang)) / max(W, H)
            sheen = (0.02 + 0.05 * rng.uniform() * (0.5 + 0.5 * np.sin(grad * 6 + rng.uniform(0, 6)))) * fill
            L = edge * rng.uniform(0.7, 1.15)
            rgb = L[..., None] * np.array([1.15, 1.2, 1.3]) + sheen[..., None] * np.array([0.7, 0.8, 1.0])
            a = np.clip(np.maximum(L, inner * 0.5) + sheen * 2.0 + fill * 0.16, 0, 1)
            cen = poly.mean(0)
            out.append(dict(tex=Tex(np.dstack([rgb, a]).astype(np.float32), premultiplied=True),
                            center=np.array([(x0 + x1) / 2, (y0 + y1) / 2]), size=(x1 - x0, y1 - y0),
                            centroid=cen, ring=sh["ring"], sector=sh["sector"], poly=poly))
        return out
    return cached("glass_shards", make)


def find_shard(p):
    """玻璃坐标 p 落在哪一块碎玻璃里（返回序号）。"""
    for i, sh in enumerate(shard_textures()):
        if cv2.pointPolygonTest(sh["poly"].astype(np.float32), (float(p[0]), float(p[1])), False) >= 0:
            return i
    return None
