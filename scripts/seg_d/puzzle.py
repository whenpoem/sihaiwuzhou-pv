"""L17 的拼图：地球裂成的硬纸板拼图块，铺在木桌上（俯视），拼到一半停住。

拼图是 9×9 块的正方形，画面是摊平的地球：一条条字带（暖白的小字印在深蓝底上），赤道以北一条褪色红的旧字，
赤道那条宽带上印着 L17 的歌词大字，三行"那些勇敢的／自卑還沒／拼完一半"。拼好的部分是一个十字形（中间一列与
中间一行，45 块，约占全图一半），四角的 36 块散在桌上。十字形正好是一个缺盖的立方体展开图：中间一格是底，
上下左右四格是四壁，L18 里它沿折线折起成缺一面的盒子。

"勇敢"和"自卑"两组碎块互相卡不进去：它们相接的那条边，两边的块都做成凸起的榫头，凸对凸，怎么也扣不上。
"自卑"一组反复试着滑进"勇敢"下面的空位，碰到榫头又弹开。

每块的贴图由整幅画面裁出，乘上由切口曲线画出的遮罩，再加上硬纸板的质感：切口处露出一圈浅色的纸板芯，
边缘略压下去发暗，印刷面有细微的纸纹和网点。阴影是遮罩的模糊，块被拿起时阴影偏移变大、变淡。
"""
import math

import numpy as np
import skia
from PIL import Image
from scipy import ndimage

from common import IMG, cached, disk_cached, look, chars, onsets, hash01, RED
from engine import Tex

N = 9                       # 9×9 块
PX = 256                    # 每块本体的像素数
MARGIN = 0.32               # 每块贴图在本体四周留出的边（块宽的比例），容纳凸出的榫头
TEX_N = int(round(PX * (1 + 2 * MARGIN)))

L17 = chars(17)
L17_T = onsets(17)
# 歌词大字所在的块（行, 列）：三行，"自卑"正好在"勇敢"下面
LYRIC_CELLS = [(3, 1), (3, 2), (3, 3), (3, 4), (3, 5),
               (4, 3), (4, 4), (4, 5), (4, 6),
               (5, 3), (5, 4), (5, 5), (5, 6)]
YONG, GAN, ZI, BEI = (3, 3), (3, 4), (4, 3), (4, 4)
CONFLICT = {((3, 3), (4, 3)), ((3, 4), (4, 4))}     # 凸对凸的两条边（上块, 下块）


def in_plus(r, c):
    return 3 <= r <= 5 or 3 <= c <= 5


# ---------------------------------------------------------------- 切口曲线

def _tab_points(jit, n=40):
    """一条边上的切口：沿边 s∈[0,1]，向外偏 h。jit 为 (中心偏移, 大小) 抖动。返回 (s, h) 折线。"""
    dc, k = jit
    segs = [((0.00, 0.0), (0.18, 0.0), (0.30 + dc, 0.01), (0.37 + dc, 0.0)),
            ((0.37 + dc, 0.0), (0.43 + dc, -0.01), (0.42 + dc, 0.07 * k), (0.38 + dc, 0.11 * k)),
            ((0.38 + dc, 0.11 * k), (0.33 + dc, 0.19 * k), (0.40 + dc, 0.27 * k), (0.50 + dc, 0.27 * k)),
            ((0.50 + dc, 0.27 * k), (0.60 + dc, 0.27 * k), (0.67 + dc, 0.19 * k), (0.62 + dc, 0.11 * k)),
            ((0.62 + dc, 0.11 * k), (0.58 + dc, 0.07 * k), (0.57 + dc, -0.01), (0.63 + dc, 0.0)),
            ((0.63 + dc, 0.0), (0.70 + dc, 0.01), (0.82, 0.0), (1.00, 0.0))]
    pts = []
    for p0, p1, p2, p3 in segs:
        for u in np.linspace(0, 1, n, endpoint=False):
            b = (1 - u) ** 3 * np.array(p0) + 3 * (1 - u) ** 2 * u * np.array(p1) + 3 * (1 - u) * u * u * np.array(p2) \
                + u ** 3 * np.array(p3)
            pts.append(b)
    pts.append(np.array([1.0, 0.0]))
    return np.array(pts)


def edges():
    """所有内部边：键为 ("h", r, c)（第 r 行与 r+1 行之间、第 c 列）或 ("v", r, c)（第 r 行、第 c 与 c+1 列之间）。
    值为 (凸起方向 σ, 抖动)：σ = +1 表示榫头凸向下方或右方的块。"""
    def make():
        rng = np.random.default_rng(17)
        out = {}
        for r in range(N - 1):
            for c in range(N):
                out[("h", r, c)] = (1 if rng.uniform() < 0.5 else -1, (rng.uniform(-0.05, 0.05), rng.uniform(0.9, 1.1)))
        for r in range(N):
            for c in range(N - 1):
                out[("v", r, c)] = (1 if rng.uniform() < 0.5 else -1, (rng.uniform(-0.05, 0.05), rng.uniform(0.9, 1.1)))
        return out
    return cached("pz_edges", make)


def piece_outline(r, c):
    """第 r 行第 c 列那块的轮廓，块本体坐标（左上角 (0,0)、右下角 (1,1)，y 向下）里的闭合折线。"""
    E = edges()
    pts = []

    def side(key, a, b, outward, sign_for_this):
        if key is None:
            return [np.array(a, float), np.array(b, float)]
        sigma, jit = E[key]
        tp = _tab_points(jit)
        a, b = np.array(a, float), np.array(b, float)
        d = b - a
        return [a + d * s + np.array(outward) * h * sign_for_this for s, h in tp]

    def sgn(key, this_is_first):
        if key is None:
            return 0
        sigma = E[key][0]
        # 冲突边：两边都凸
        if key[0] == "h" and ((key[1], key[2]), (key[1] + 1, key[2])) in CONFLICT:
            return 1
        return sigma if this_is_first else -sigma

    # 上边：与上一行之间的 h 边，本块是"下块"；本块沿边从左到右走，s 方向与边的 s 一致
    top = ("h", r - 1, c) if r > 0 else None
    right = ("v", r, c) if c < N - 1 else None
    bottom = ("h", r, c) if r < N - 1 else None
    left = ("v", r, c - 1) if c > 0 else None
    # 每条边统一按"从左到右"或"从上到下"取 s，绕轮廓走时再按方向反过来
    def seg(key, a, b, outward, first):
        sg = sgn(key, first)
        return side(key, a, b, outward, sg)
    pts += seg(top, (0, 0), (1, 0), (0, -1), False)
    pts += seg(right, (1, 0), (1, 1), (1, 0), True)
    pts += seg(bottom, (0, 1), (1, 1), (0, 1), True)[::-1]
    pts += seg(left, (0, 0), (0, 1), (-1, 0), False)[::-1]
    return np.array(pts)


def _path(pts, scale, off):
    p = skia.Path()
    p.moveTo(*(pts[0] * scale + off))
    for q in pts[1:]:
        p.lineTo(*(q * scale + off))
    p.close()
    return p


def piece_mask(r, c):
    """块的覆盖率遮罩 (TEX_N, TEX_N)。"""
    arr = np.zeros((TEX_N, TEX_N), np.uint8)
    s = skia.Surface.MakeRasterDirect(skia.ImageInfo.MakeA8(TEX_N, TEX_N), arr)
    cv = s.getCanvas()
    off = np.array([MARGIN * PX, MARGIN * PX])
    cv.drawPath(_path(piece_outline(r, c), PX, off), skia.Paint(AntiAlias=True, Color=skia.ColorWHITE))
    del cv, s
    return arr.astype(np.float32) / 255


# ---------------------------------------------------------------- 画面：摊平的地球

NAVY = np.array([0.105, 0.135, 0.205])
PAPER = np.array([0.93, 0.87, 0.76])


def picture():
    """整幅拼图画面 (H, W, 3)，四周各留 MARGIN 块的边（画面延续），便于裁出带榫头的块。"""
    def make():
        W = int(round(N * PX + 2 * MARGIN * PX))
        off = MARGIN * PX
        surf = look.surface(W, W)
        cv = surf.getCanvas()
        C4 = lambda c, a: skia.Color4f(float(c[0]), float(c[1]), float(c[2]), float(a))
        cv.clear(C4(NAVY * 0.7, 1.0))
        rng = np.random.default_rng(3)
        pool = "".join(look.trad(look.lyric(n)) for n in range(1, 41)).replace("　", "")
        red_txt = look.trad("世界是你們的　也是我們的　但是歸根結底是你們的　")

        def ribbon(y0, y1):
            cv.drawRect(skia.Rect(0, y0, W, y1), skia.Paint(Color=C4(NAVY, 1.0)))

        def text_row(y_base, size, color, alpha, text_fn, x0=0.0, gap=1.04):
            f = look.font("serif", 700, size)
            x = x0
            k = 0
            while x < W:
                ch = text_fn(k)
                if ch != "　":
                    cv.drawString(ch, x, y_base, f, skia.Paint(AntiAlias=True, Color=C4(color, alpha)))
                x += size * gap
                k += 1

        # 北、南各三行窄带（每行块里两条小字带），赤道以北紧挨着的一行是红色旧字
        for row in list(range(0, 2)) + list(range(6, 9)):
            for sub in range(2):
                y0 = off + (row + sub * 0.5) * PX + 0.06 * PX
                y1 = y0 + 0.38 * PX
                ribbon(y0, y1)
                size = 0.30 * PX
                text_row(y1 - 0.09 * PX, size, PAPER, 0.50, lambda k: pool[rng.integers(len(pool))],
                         x0=-rng.uniform(0, size))
        # 红色旧字一行
        y0, y1 = off + 2 * PX + 0.10 * PX, off + 2.9 * PX
        ribbon(y0, y1)
        text_row(y1 - 0.22 * PX, 0.52 * PX, RED * 1.0, 0.75, lambda k: red_txt[k % len(red_txt)], x0=off + 0.05 * PX,
                 gap=1.06)
        # 赤道宽带：深蓝底上很淡的细小字，再印歌词大字
        y0, y1 = off + 3.04 * PX, off + 5.96 * PX
        ribbon(y0, y1)
        for k in range(9):
            text_row(y0 + (k + 0.82) * 0.32 * PX, 0.22 * PX, PAPER, 0.16, lambda j: pool[rng.integers(len(pool))],
                     x0=-rng.uniform(0, 30))
        f = look.font("serif", 800, 0.74 * PX)
        for (r, c), ch in zip(LYRIC_CELLS, L17):
            adv = f.measureText(ch)
            x = off + (c + 0.5) * PX - adv / 2
            y = off + (r + 0.5) * PX + 0.74 * PX * 0.36
            cv.drawString(ch, x, y, f, skia.Paint(AntiAlias=True, Color=C4(PAPER * 1.04, 1.0)))
        img = look.to_np(surf)[..., :3]
        # 印刷：纸纹与轻微的网点
        h = img.shape[0]
        grain = ndimage.gaussian_filter(rng.normal(0, 1, (h, h)), 1.0) * 0.03
        img = np.clip(img * (1 + grain[..., None]) + grain[..., None] * 0.02, 0, 1)
        return img.astype(np.float32)
    return disk_cached("pz_picture_v3", make)


def back_texture():
    """拼图背面的灰色硬纸板（L18 盒子外侧看到的一面），可平铺。"""
    def make():
        rng = np.random.default_rng(8)
        n = 1024
        base = np.array([0.66, 0.60, 0.50])
        fib = ndimage.gaussian_filter(rng.normal(0, 1, (n, n)), (0.8, 6.0), mode="wrap") * 0.06
        blot = ndimage.gaussian_filter(rng.normal(0, 1, (n, n)), 40, mode="wrap") * 1.5
        fine = rng.normal(0, 0.02, (n, n))
        v = 1 + fib + blot * 0.6 + fine
        img = np.clip(base[None, None] * v[..., None], 0, 1)
        return img.astype(np.float32)
    return disk_cached("pz_back_v2", make)


# ---------------------------------------------------------------- 每块的贴图

def piece_rgba(r, c):
    """正面贴图（直通 alpha，RGBA 浮点）：画面裁片 × 遮罩，加切口处的纸板芯和压暗的边。"""
    pic = picture()
    m = piece_mask(r, c)
    y0 = int(round(r * PX))
    x0 = int(round(c * PX))
    crop = pic[y0:y0 + TEX_N, x0:x0 + TEX_N]
    if crop.shape[:2] != (TEX_N, TEX_N):
        crop = np.pad(crop, ((0, TEX_N - crop.shape[0]), (0, TEX_N - crop.shape[1]), (0, 0)), mode="edge")
    dist = ndimage.distance_transform_edt(m > 0.5)
    core = np.clip(1.0 - (dist - 1.0) / 2.5, 0, 1) * (m > 0.5)           # 外沿 1–3 像素：露出的浅色纸板芯
    press = np.clip(1.0 - (dist - 3.0) / 6.0, 0, 1) * (m > 0.5)          # 再往里一点：切刀压下去的暗边
    col = crop * (1.0 - 0.28 * press[..., None])
    col = col * (1 - core[..., None]) + np.array([0.70, 0.66, 0.58]) * core[..., None]
    # 左上方来的光：切口朝左上的一侧亮一点，朝右下的一侧暗一点
    gy, gx = np.gradient(ndimage.gaussian_filter(m, 1.2))
    lit = np.clip(-(gx * -0.7 + gy * -0.7) * 6.0, -1, 1)
    col = np.clip(col * (1 + 0.25 * lit[..., None] * core[..., None]), 0, 1)
    return np.dstack([col, m]).astype(np.float32)


def piece_tex(r, c):
    return cached(("pz_tex", r, c), lambda: Tex(piece_rgba(r, c)))


def shadow_tex(r, c):
    def make():
        m = piece_mask(r, c)
        s = ndimage.gaussian_filter(m, 7.0)
        return Tex(np.clip(s * 1.1, 0, 1).astype(np.float32))
    return cached(("pz_sh", r, c), make)


def all_textures():
    """预先生成全部块的贴图（第一次约十几秒），返回 {(r, c): (正面, 阴影)}。"""
    return {(r, c): (piece_tex(r, c), shadow_tex(r, c)) for r in range(N) for c in range(N)}


# ---------------------------------------------------------------- 木桌

def table_tex():
    """木桌：Wood planks（Amal Kumar / Poly Haven，CC0），压低饱和度、略调暗，成为旧漆木桌的颜色。"""
    def make():
        a = disk_cached("table_v1", lambda: np.asarray(Image.open(IMG / "Wood_planks_diff_8k_Amal_Kumar_via_Poly_Haven_.png")
                                                        .convert("RGB").resize((2048, 2048), Image.LANCZOS)))
        f = a.astype(np.float32) / 255
        lum = f.mean(2, keepdims=True)
        f = (lum + (f - lum) * 0.6) * np.array([0.82, 0.78, 0.74])
        return Tex((np.clip(f, 0, 1) * 255).astype(np.uint8), repeat=True)
    return cached("table_tex", make)


# ---------------------------------------------------------------- 拼合的过程

P = 0.19                            # 每块本体的世界尺寸（米）
CENTER = np.array([1.30, -0.50])    # 拼图中心：L16 地球所在处的正下方（与圆形积水同心）
T_BURST = 82.12                     # 地球裂开、碎块飞起
LAMP = np.array([CENTER[0] - 1.7, CENTER[1] + 1.3, 2.3])
LAMP_COL = np.array([1.10, 0.95, 0.78]) * 3.0
AMB = np.array([0.085, 0.095, 0.125])
YONG_SNAP = None


def slot(r, c):
    return np.array([CENTER[0] + (c - 4) * P, CENTER[1] - (r - 4) * P])


def plan_pieces():
    """每块的动作：落点、落下时刻、滑进位置的时刻。返回 {(r, c): dict}。"""
    def make():
        rng = np.random.default_rng(21)
        out = {}
        lyric = {rc: (ch, tc) for rc, ch, tc in zip(LYRIC_CELLS, L17, L17_T)}
        others = [(r, c) for r in range(N) for c in range(N) if (r, c) not in lyric]
        # 散落的位置：拼图四角的空处和四周
        spots = []
        while len(spots) < len(others):
            x, y = rng.uniform(-7.5, 7.5), rng.uniform(-5.5, 5.5)
            if abs(x) < 1.7 or abs(y) < 1.7:             # 十字形区域留空
                if not (abs(x) > 5.0 or abs(y) > 5.0):
                    continue
            spots.append((x, y))
        rng.shuffle(spots)
        plus_others = [rc for rc in others if in_plus(*rc)]
        snap_ts = np.sort(rng.uniform(82.62, 84.92, len(plus_others)))
        order = rng.permutation(len(plus_others))
        snap_of = {plus_others[i]: snap_ts[k] for k, i in enumerate(order)}
        for (r, c), (sx, sy) in zip(others, spots):
            out[(r, c)] = dict(kind="plus" if in_plus(r, c) else "loose",
                               loose=CENTER + np.array([sx, sy]) * P, loose_rot=rng.uniform(-180, 180),
                               land=T_BURST + rng.uniform(0.18, 0.42), snap=snap_of.get((r, c)),
                               dir=rng.normal(0, 1, 3), spin=rng.uniform(-900, 900))
        for rc, (ch, tc) in lyric.items():
            out[rc] = dict(kind="lyric", land=tc, rot0=rng.uniform(-25, 25), dir=rng.normal(0, 1, 3),
                           spin=rng.uniform(-600, 600))
        out[ZI]["kind"] = out[BEI]["kind"] = "conflict"
        return out
    return cached("pz_plan", make)


CONFLICT_PRESSES = [83.98, 84.50, 85.02, 85.42]


def conflict_pose(t):
    """"自卑"一组的姿态：(位移 dx, dy（块宽为单位，dy 向上即朝"勇敢"）, 转角, 抬起高度)。
    平时歪着停在空位下方一点；每次被推向"勇敢"，凸起的榫头顶住凸起的榫头，一下弹开，晃几下又停住。"""
    rest = np.array([-0.05, -0.20, -6.0, 0.030])
    pose = rest.copy()
    for tp in CONFLICT_PRESSES:
        if t < tp - 0.14:
            break
        if t < tp:                                   # 推过去：滑进空位，几乎放平
            u = (t - (tp - 0.14)) / 0.14
            e = u * u * (3 - 2 * u)
            pose = rest + (np.array([0.0, 0.03, -1.5, 0.010]) - rest) * e
        else:                                        # 顶住，弹开，阻尼晃动后回到原处
            v = t - tp
            e = math.exp(-v / 0.16)
            osc = math.cos(v * 24.0) * e
            pose = rest + np.array([-0.04 * osc, -0.22 * osc, -7.0 * osc, 0.045 * e])
    return tuple(pose)


def piece_pose(rc, t):
    """块在 t 时刻的 (x, y, z, 转角度数, 缩放, 不透明度)；还没出现时返回 None。"""
    pl = plan_pieces()[rc]
    r, c = rc
    sl = slot(r, c)
    k = pl["kind"]
    if k in ("lyric", "conflict"):
        tc = pl["land"]
        dur = 0.15
        if t < tc - dur:
            return None
        u = min((t - (tc - dur)) / dur, 1.0)
        z = 0.45 * (1 - u * u)
        rot = pl["rot0"] * (1 - u) ** 2
        if k == "conflict":
            dx, dy, rr, lift = conflict_pose(t)
            if rc == BEI:
                # 卑贴着自的右边，作为一组一起动：绕两块的中点转
                pass
            pair_c = (slot(*ZI) + slot(*BEI)) / 2 + np.array([dx, dy]) * P
            off = sl - (slot(*ZI) + slot(*BEI)) / 2
            a = math.radians(rr)
            o = np.array([off[0] * math.cos(a) - off[1] * math.sin(a), off[0] * math.sin(a) + off[1] * math.cos(a)])
            p = pair_c + o
            return p[0], p[1], max(z, lift), rr + rot, 1.0, 1.0
        # "勇敢"在每次被顶时也跟着一震
        bump = 0.0
        if rc in (YONG, GAN):
            for tp in CONFLICT_PRESSES:
                if t >= tp:
                    bump += 0.05 * math.exp(-(t - tp) / 0.07) * math.sin((t - tp) * 55)
        return sl[0], sl[1] + bump * P, z, rot, 1.0, 1.0
    # 其他块：地球裂开时飞起，再落到散落的位置；十字形里的块随后滑进去
    if t < T_BURST:
        return None
    land = pl["land"]
    p_land = pl["loose"]
    if t < land:
        return "fly"
    if k == "plus" and t >= pl["snap"]:
        u = min((t - pl["snap"]) / 0.34, 1.0)
        e = u * u * (3 - 2 * u)
        p = p_land + (sl - p_land) * e
        rot = pl["loose_rot"] % 360
        if rot > 180:
            rot -= 360
        rot = rot * (1 - e)
        lift = 0.03 * math.sin(math.pi * u)
        return p[0], p[1], lift, rot, 1.0, 1.0
    return p_land[0], p_land[1], 0.0, pl["loose_rot"], 1.0, 1.0


def fly_pose(rc, t, gc, gr):
    """地球裂开后飞起的块：从球面上的位置飞向镜头，再落到桌上散落的位置（二次贝塞尔曲线）。"""
    pl = plan_pieces()[rc]
    n = np.array(pl["dir"], float)
    n[2] = abs(n[2]) + 0.25
    n /= np.linalg.norm(n)
    p0 = np.asarray(gc, float) + gr * n
    p1 = np.array([p0[0] + n[0] * 1.4, p0[1] + n[1] * 1.4, min(p0[2] + 0.35 + 0.3 * abs(n[2]), 2.1)])
    p2 = np.array([pl["loose"][0], pl["loose"][1], 0.0])
    u = (t - T_BURST) / (pl["land"] - T_BURST)
    u = 1.0 - (1.0 - u) ** 1.6                       # 炸开时最快，落到桌上前慢下来
    b = (1 - u) ** 2 * p0 + 2 * u * (1 - u) * p1 + u * u * p2
    rot = pl["loose_rot"] + pl["spin"] * (1 - u) * 0.3
    return b[0], b[1], b[2], rot, 0.36 + 0.64 * u, min(1.0, (t - T_BURST) / 0.04)


def items(t, gc, gr, table_op=1.0, light_k=1.0):
    """桌面、拼图块和它们的影子。gc、gr 为裂开那一刻地球的球心与半径。"""
    from engine import Plane
    out = []
    lamp = dict(lamp_pos=tuple(LAMP), lamp_col=tuple(LAMP_COL * light_k), amb=tuple(AMB), lamp_fall=0.30)
    if table_op > 0.001:
        W, H = 8.0, 5.0
        out.append(Plane(table_tex(), center=(CENTER[0], CENTER[1], 0.0), size=(W, H), uv=(0, 0, W / 1.6, H / 1.6),
                         group="past", material="d_lit", uniforms=dict(lamp, gloss=0.05), opacity=table_op,
                         stack="table", bias=40.0))
    poses = []
    for r in range(N):
        for c in range(N):
            ps = piece_pose((r, c), t)
            if ps is None:
                continue
            if ps == "fly":
                ps = fly_pose((r, c), t, gc, gr)
            poses.append(((r, c), ps))
    poses.sort(key=lambda q: q[1][2])
    size = TEX_N / PX * P
    for (r, c), (x, y, z, rot, sc, op) in poses:
        tex, sh = piece_tex(r, c), shadow_tex(r, c)
        on_table = z < 0.2
        stack = "table" if on_table else None
        lift = max(z, 0.0)
        if on_table:
            off = 0.010 + lift * 0.9
            out.append(Plane(sh, center=(x + off, y - off * 1.2, 0.0), size=(size * sc * (1 + lift * 2),) * 2,
                             rot=(0, 0, rot), color=(0.0, 0.0, 0.0), opacity=0.55 * max(0.25, 1 - lift * 12) * table_op,
                             group="past", stack=stack))
        uni = dict(lamp, gloss=0.25)
        if not on_table:                       # 飞在半空的碎块带着地球的光，比桌上的亮
            uni["amb"] = (0.55, 0.55, 0.60)
        out.append(Plane(tex, center=(x, y, z), size=(size * sc,) * 2, rot=(0, 0, rot), group="past", material="d_lit",
                         uniforms=uni, opacity=op, stack=stack))
    return out
