"""翻板的贴图与光照。

每块板是一块上了漆的薄板：正面和背面各漆一种颜色，边是板芯的本色。板面贴图是一张近白的图集，乘上每块板的颜色
得到最后的颜色；图集里有 24 种板面（漆刷纹的方向和深浅、边角的磨损各不相同），每块板随机取一种，所以近看是
一块块手工漆过的旧板，远看连成一片。贴图里板的四周略暗一圈，相当于板边的倒角；远看时多级缩小图把这一圈
平均掉，板缝不会因为格距接近像素而出现摩尔纹。另有 24 种无缝的板面（没有倒角和磨损），L33 时用，板拼起来
看不出缝。

光照在 numpy 里逐块计算：场地四角的照明灯是聚光灯，光锥内亮、锥外只有少量散射光，再随距离平方衰减；每块板
按自己的法线算漫反射与漆面的高光。板翻转时法线扫过光的方向，先背光变暗、再迎光发亮，一波翻转因此带着一道
暗带和一道亮带向前推进，这就是翻板的明暗变化。地面的照度图和空气里灰尘的亮度用同一套灯，所以三者明暗一致。
"""
import numpy as np
from scipy.ndimage import gaussian_filter

from common import cached, disk_cached

CELL = 128          # 图集每格的像素
PAD = 8             # 每格四周留白，避免缩小图互相渗色
N_VAR = 24          # 板面的种类
SEAM_I = N_VAR      # 无缝板面（L33 的板拼得严丝合缝，看起来是一整片漆过的地面）：条目 24–47
EDGE_I = 2 * N_VAR  # 板边
SHADOW_I = EDGE_I + 1   # 阴影（软边矩形）
FLAT_I = EDGE_I + 2     # 纯白（飞散的碎片等用）
N_CELLS = EDGE_I + 3
GRID = 8            # 图集 8 × 7 格


def _card_face(rng, n, seamless=False):
    """一块板面的 RGBA（n × n，近白）。seamless=True 时没有倒角、圆角和磨损，漆色起伏也小，相邻的板拼起来
    看不出缝。"""
    yy, xx = np.mgrid[0:n, 0:n] / (n - 1)
    # 漆刷纹：沿一个方向拉长的噪声
    ang = rng.uniform(-0.25, 0.25) + (np.pi / 2 if rng.random() < 0.3 else 0.0)
    noise = rng.normal(0, 1, (n, n))
    if abs(ang) < 1.0:
        streak = gaussian_filter(noise, (0.7, 9.0))
    else:
        streak = gaussian_filter(noise, (9.0, 0.7))
    streak /= streak.std() + 1e-6
    blot = gaussian_filter(rng.normal(0, 1, (n, n)), 14.0)
    blot /= blot.std() + 1e-6
    fine = gaussian_filter(rng.normal(0, 1, (n, n)), 0.8)
    fine /= fine.std() + 1e-6
    v = 0.93 + 0.022 * streak + 0.035 * blot * rng.uniform(0.5, 1.2) + 0.012 * fine
    if seamless:
        v = 0.93 + 0.008 * fine
        return np.dstack([v, v, v, np.ones_like(v)]).astype(np.float32)
    # 倒角：四周一圈略暗
    d = np.minimum(np.minimum(xx, 1 - xx), np.minimum(yy, 1 - yy))
    v *= 0.88 + 0.12 * np.clip(d / 0.06, 0, 1) ** 0.6
    # 边角磨损：露出发灰的板芯
    wear = np.zeros((n, n))
    for _ in range(rng.integers(1, 5)):
        side = rng.integers(4)
        p = rng.uniform(0.05, 0.95)
        cx, cy = [(p, 0.0), (p, 1.0), (0.0, p), (1.0, p)][side]
        r = rng.uniform(0.03, 0.09)
        wear = np.maximum(wear, np.clip(1 - np.hypot((xx - cx) / r, (yy - cy) / (r * rng.uniform(0.6, 1.4))), 0, 1))
    wear = np.clip(wear * 3.0 + gaussian_filter(rng.normal(0, 0.4, (n, n)), 1.0) * wear, 0, 1)
    rgb = np.dstack([v, v, v])
    core = np.array([0.62, 0.56, 0.48])
    rgb = rgb * (1 - wear[..., None]) + core * wear[..., None] * v[..., None]
    # 圆角
    r = 0.06
    qx = np.clip(np.abs(xx - 0.5) - (0.5 - r), 0, None)
    qy = np.clip(np.abs(yy - 0.5) - (0.5 - r), 0, None)
    a = np.clip((r - np.hypot(qx, qy)) * n * 0.8, 0, 1)
    return np.dstack([rgb, a]).astype(np.float32)


def _edge(rng, n):
    """板边：板芯的纹理（沿长边的纤维），中间亮、两侧略暗。"""
    yy, xx = np.mgrid[0:n, 0:n] / (n - 1)
    fib = gaussian_filter(rng.normal(0, 1, (n, n)), (0.6, 12.0))
    fib /= fib.std() + 1e-6
    v = 0.9 + 0.08 * fib
    v *= 0.75 + 0.25 * np.sin(np.pi * yy) ** 0.5
    return np.dstack([v, v, v, np.ones_like(v)]).astype(np.float32)


def _shadow(n):
    yy, xx = np.mgrid[0:n, 0:n] / (n - 1)
    d = np.minimum(np.minimum(xx, 1 - xx), np.minimum(yy, 1 - yy))
    a = np.clip(d / 0.18, 0, 1) ** 1.5
    return np.dstack([np.zeros((n, n, 3)), a]).astype(np.float32)


def atlas():
    """翻板图集：engine.Atlas，条目 0–23 为板面，24–47 为无缝板面，48 为板边，49 为阴影，50 为纯白。"""
    def make_arr():
        rng = np.random.default_rng(33)
        inner = CELL - 2 * PAD
        rows = (N_CELLS + GRID - 1) // GRID
        arr = np.zeros((rows * CELL, GRID * CELL, 4), np.float32)
        for i in range(N_CELLS):
            if i < N_VAR:
                img = _card_face(rng, inner)
            elif i < EDGE_I:
                img = _card_face(rng, inner, seamless=True)
            elif i == EDGE_I:
                img = _edge(rng, inner)
            elif i == SHADOW_I:
                img = _shadow(inner)
            else:
                img = np.ones((inner, inner, 4), np.float32)
            r, c = divmod(i, GRID)
            y0, x0 = r * CELL + PAD, c * CELL + PAD
            arr[y0:y0 + inner, x0:x0 + inner] = img
            # 留白处复制边缘像素的颜色（透明度为 0），缩小图里板边不会混进黑色
            arr[y0 - PAD:y0, x0:x0 + inner, :3] = img[:1, :, :3]
            arr[y0 + inner:y0 + inner + PAD, x0:x0 + inner, :3] = img[-1:, :, :3]
            arr[y0 - PAD:y0 + inner + PAD, x0 - PAD:x0, :3] = arr[y0 - PAD:y0 + inner + PAD, x0:x0 + 1, :3]
            arr[y0 - PAD:y0 + inner + PAD, x0 + inner:x0 + inner + PAD, :3] = \
                arr[y0 - PAD:y0 + inner + PAD, x0 + inner - 1:x0 + inner, :3]
        return arr

    def make():
        from engine import Atlas
        arr = disk_cached("card_atlas", make_arr, "v5")
        h, w = arr.shape[:2]
        rects, keys = {}, []
        for i in range(N_CELLS):
            r, c = divmod(i, GRID)
            u0 = (c * CELL + PAD + 0.5) / w
            v0 = (r * CELL + PAD + 0.5) / h
            u1 = (c * CELL + CELL - PAD - 0.5) / w
            v1 = (r * CELL + CELL - PAD - 0.5) / h
            rects[i] = (u0, v0, u1, v1)
            keys.append(i)
        return Atlas(arr, rects, keys)
    return cached("card_atlas", make)


# ---------------------------------------------------------------- 光照

class Lights:
    """若干点光源（场地四角的照明灯）。pos (L,3)、color (L,3)、power (L,)。

    照度按"灯朝场地中心照"的模型计算：随距离平方衰减，偏离灯的中轴越远越暗。强度整体归一化，使场地中心一块
    平放的板受到的总照度为 1；地面的照度图、空气里灰尘的亮度都用同一个模型，所以板、地面和灰尘的明暗一致。
    shade() 逐块计算漫反射与漆面的高光。"""

    R0 = 260.0

    def __init__(self, pos, color, power, aim, cone=(0.80, 0.95), spill=0.12, ambient=(0.05, 0.045, 0.045),
                 spec=0.35, shininess=40.0):
        self.pos = np.asarray(pos, np.float32)
        self.color = np.asarray(color, np.float32)
        self.power = np.asarray(power, np.float32)
        a = np.asarray(aim, np.float32) - self.pos
        self.aim = a / np.linalg.norm(a, axis=1, keepdims=True)
        self.cone, self.spill = cone, spill
        self.ambient = np.asarray(ambient, np.float32)
        self.spec, self.shininess = spec, shininess
        L, att = self._geom(np.zeros((1, 3), np.float32))
        self.power = self.power / float((att[0] * np.clip(L[0, :, 2], 0, None)).sum()) * 1.4

    def _geom(self, P):
        """到各光源的单位方向 L (N,L,3) 与照度系数 att (N,L)：照明灯是聚光灯，光锥内亮、锥外只有少量散射光，
        再随距离平方衰减。"""
        d = self.pos[None, :, :] - P[:, None, :]                # (N, L, 3)
        r2 = (d ** 2).sum(-1)
        L = d / np.sqrt(r2)[..., None]
        cosang = -(L * self.aim[None]).sum(-1)                  # 光线方向与灯的中轴的夹角
        c0, c1 = self.cone
        u = np.clip((cosang - c0) / (c1 - c0), 0, 1)
        spot = self.spill + (1 - self.spill) * u * u * (3 - 2 * u)
        att = self.power[None, :] * spot / (1.0 + r2 / self.R0 ** 2)
        return L.astype(np.float32), att.astype(np.float32)

    def prepare(self, P):
        """对固定位置 P (N,3) 预先算好到各光源的单位方向、衰减和半角向量，供 shade() 使用。"""
        L, att = self._geom(np.asarray(P, np.float32))
        H = L + np.array([0, 0, 1.0], np.float32)
        H /= np.linalg.norm(H, axis=-1, keepdims=True)
        return {"L": L, "H": H.astype(np.float32), "att": att}

    def irradiance(self, P, up=True):
        """P (N,3) 处的照度（RGB）：up=True 时按朝上的平面算（地面），否则不计入射角（空气里的灰尘）。"""
        L, att = self._geom(np.asarray(P, np.float32))
        k = att * (np.clip(L[..., 2], 0, None) if up else 0.45)
        return k @ self.color + self.ambient

    def shade(self, prep, n, base, extra=None, V=None):
        """n (N,3) 单位法线（指向看得见的那一面）；base (N,3) 板面颜色。返回 (N,3) 光照后的颜色。
        V (N,3) 为从板指向镜头的单位向量：漆面的高光按它与灯光的半角向量计算，斜看时逆着灯光的漆面一片发亮；
        不给 V 时按镜头在正上方计算。extra 为额外的平行光 [(方向, 颜色)]，用于闪电。"""
        L, att = prep["L"], prep["att"]
        if V is None:
            H = prep["H"]
        else:
            H = L + V[:, None, :]
            H = H / (np.linalg.norm(H, axis=-1, keepdims=True) + 1e-6)
        ndl = np.einsum("nlk,nk->nl", L, n)
        ndh = np.einsum("nlk,nk->nl", H, n)
        diff = np.clip(ndl, 0, None) * att                       # (N, L)
        # 漆面的高光：亮度跟着法线与半角向量的夹角迅速变化
        spec = np.clip(ndh, 0, None) ** self.shininess * att * self.spec * (ndl > 0)
        lit = diff @ self.color + self.ambient                    # (N, 3)
        col = base * lit + spec @ self.color
        if extra:
            for d, c in extra:
                d = np.asarray(d, np.float32)
                c = np.asarray(c, np.float32)
                k = np.clip(n @ d, 0, None)
                if V is None:
                    hk = k ** 24
                else:
                    hv = d[None] + V
                    hv /= np.linalg.norm(hv, axis=1, keepdims=True) + 1e-6
                    hk = np.clip((n * hv).sum(1), 0, None) ** 14 * (k > 0) * 2.0
                col += base * k[:, None] * c[None] + hk[:, None] * c[None] * 0.3
        return col
