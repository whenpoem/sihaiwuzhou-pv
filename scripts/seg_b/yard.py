"""L05 的院子与天：虚化的苏式楼、正午的天色、太阳，以及横贯 L05、L06 的积云。

苏式楼沿用样张三的照片（ruiraykwok，CC BY-SA 3.0）和调色：取左边那栋楼，强烈虚化，压暗、去掉一半饱和度、
偏暖。与样张三不同的是，楼的天空部分按颜色抠掉了，楼顶往上淡出，楼后面露出真正的天和积云，这样 L05→L06
镜头上移时，楼往下落，天和云接着出现，三层以不同的速度移动。

积云取 Commons 上 Lance Vanlewen 的照片（White Cumulus Clouds against Blue Sky (2)，CC BY-SA 4.0）：一整排
积云，顶部起伏连成一线，下半部是厚实的云体。按"白的程度"把蓝天抠掉，云的亮部提亮到略微过曝、偏奶油色，
暗部偏暖灰，和正午逆光统一。云顶那条起伏的线就是 L06 骑士走的路。
"""
import numpy as np
from scipy.ndimage import gaussian_filter, zoom

from common import IMG, L, Z_BUILD, Z_FAR, Z_SKY, cached, disk, lum, photo
from engine import Plane, Tex

# ---------------------------------------------------------------- 苏式楼

BUILD_PHOTO = "北科大_苏式楼_凝固的时光_-_panoramio.jpg"
BUILD_PPU = 42.5                                 # 照片每世界单位的像素数
BUILD_CROP = (0, 1190)                           # 只用左边那栋楼（照片 x 范围）
BUILD_TOP_Y = 8.1                                # 照片顶边的世界 y；楼顶在 6.5 附近淡出


def building_tex():
    """RGBA（直通 alpha）：楼与近处的院子，天空透明，顶部淡出。"""
    def make():
        im = photo(BUILD_PHOTO)[:, BUILD_CROP[0]:BUILD_CROP[1]]
        h, w = im.shape[:2]
        r, g, b = im[..., 0], im[..., 1], im[..., 2]
        sky = np.clip((b - r - 0.05) / 0.10, 0, 1) * np.clip((b - 0.40) / 0.15, 0, 1)
        sky = gaussian_filter(sky, 2.0)
        a = 1.0 - sky
        # 顶部淡出：楼在照片顶边被截断，往上让它化进过曝的天光里
        yy = np.arange(h)[:, None] / h
        a = a * np.clip((yy - 0.02) / 0.12, 0, 1) ** 1.5
        # 右缘淡出
        xx = np.arange(w)[None, :] / w
        a = a * np.clip((1.0 - xx) / 0.15, 0, 1)
        # 预乘后再模糊，透明处的颜色不会渗进来
        pm = im * a[..., None]
        pm = gaussian_filter(pm, (3.2, 3.2, 0))
        a = gaussian_filter(a, 3.2)
        col = pm / np.maximum(a[..., None], 1e-4)
        lu = col.mean(2, keepdims=True)
        col = (col * 0.5 + lu * 0.5) * 0.62 * np.array([1.08, 0.90, 0.70])
        # 楼面被天光照着的上部略亮（样张三在画面上部加了一层天光）
        col = col + np.clip(0.30 - yy, 0, None)[..., None] ** 1.5 * np.array([1.6, 1.4, 1.05])
        return np.dstack([col, a]).astype(np.float32)
    return cached("building", lambda: Tex(disk("building", make, BUILD_PHOTO, BUILD_CROP, "v2")))


def building_items(t, opacity=1.0):
    if opacity <= 0.002:
        return []
    tex = building_tex()
    h, w = tex.data.shape[:2]
    W, H = w / BUILD_PPU, h / BUILD_PPU
    x0 = 0.5 - 600 / BUILD_PPU                    # 照片 x = 600 落在 L05 构图中心 x = 0.5 附近（与样张三的取景相同）
    return [Plane(tex, center=(x0 + W / 2, BUILD_TOP_Y - H / 2, Z_BUILD), size=(W, H), group="past", opacity=opacity)]


# ---------------------------------------------------------------- 天色与太阳

SUN = (16.0, 30.0)                               # 太阳在远天上的位置（z = Z_FAR）：L05、L06 都在画面右上方之外


def sky_tex():
    """正午的天：靠太阳一侧发白、过曝，远离太阳处是褪了色的浅蓝灰。"""
    def make():
        n = 512
        yy, xx = np.mgrid[0:n, 0:n] / (n - 1)
        # 平面 240 × 160，中心 (6, 10)；太阳在 (16, 30) → 平面坐标
        X = (xx - 0.5) * 240 + 6
        Y = (0.5 - yy) * 160 + 10
        d = np.hypot(X - SUN[0], (Y - SUN[1]) * 1.1)
        glow = np.exp(-(d / 42.0) ** 2)
        far = np.array([0.50, 0.58, 0.70])
        near = np.array([1.05, 1.0, 0.92])
        col = far * (1 - glow[..., None]) + near * glow[..., None]
        col = col * (0.92 + 0.10 * np.clip(Y / 60, -1, 1))[..., None]
        return col.astype(np.float32)
    return cached("skytex", lambda: Tex(make()))


def sun_tex():
    def make():
        n = 512
        yy, xx = np.mgrid[0:n, 0:n] / (n - 1) * 2 - 1
        r = np.hypot(xx, yy)
        a = np.exp(-(r / 0.06) ** 2) * 2.2 + np.exp(-(r / 0.20) ** 2) * 0.35 + np.exp(-(r / 0.55) ** 2) * 0.10
        return np.dstack([a * 1.0, a * 0.93, a * 0.78, np.ones_like(a)]).astype(np.float32)
    return cached("suntex", lambda: Tex(make(), premultiplied=True))


def sky_items(t, sun_k=1.0):
    items = [Plane(sky_tex(), center=(6.0, 10.0, Z_FAR), size=(240.0, 160.0), group="past")]
    if sun_k > 0:
        items.append(Plane(sun_tex(), center=(SUN[0], SUN[1], Z_FAR + 0.5), size=(70.0, 70.0), blend="add",
                           color=(sun_k,) * 3, group="past"))
    return items


# ---------------------------------------------------------------- 积云

CLOUD_PHOTO = "White_Cumulus_Clouds_against_Blue_Sky_2_.jpg"
CLOUD_PPU = 72.0                                 # 照片每世界单位的像素数（照片 3840 × 2160 → 53.3 × 30）
CLOUD_TOP = 17.5                                 # 照片顶边的世界 y：浮云顶在 y ≈ 7–8，云塔顶 8.5
CLOUD_X0 = -22.0                                 # 照片左边的世界 x


def cloud_rgba():
    """积云的抠图（直通 alpha，0–1 以上为高光）与亮度图。"""
    def make():
        im = photo(CLOUD_PHOTO)
        h, w = im.shape[:2]
        # 底边两角有一点屋檐，切掉最下面 3%
        im = im[: int(h * 0.97)]
        r, g, b = im[..., 0], im[..., 1], im[..., 2]
        lu = lum(im)
        # 天是饱和的蓝（蓝通道比红绿的平均高 0.2 以上），云是灰白的；暗的天不当作云
        chroma = b - (r + g) / 2
        a = np.clip((0.19 - chroma) / 0.11, 0, 1) * np.clip((lu - 0.25) / 0.2, 0, 1)
        # 云体内部偏蓝的暗影会被误当作天：只有与上边连通的天才是真正的天，其余的洞填上
        from scipy import ndimage
        low = a < 0.4
        lab, n = ndimage.label(low)
        top = np.unique(np.r_[lab[0], lab[: h // 2, 0], lab[: h // 2, -1]])
        sky = np.isin(lab, top[top > 0])
        hole = low & ~sky
        a0 = a.copy()
        a = np.maximum(a, gaussian_filter(hole.astype(np.float32), 3.0) * 0.96)
        # 洞里原来是蓝天的颜色：用周围云的颜色补上（按原 alpha 加权的大半径平均）
        wgt = gaussian_filter(a0, 18) + 1e-4
        fillc = np.dstack([gaussian_filter(im[..., i] * a0, 18) for i in range(3)]) / wgt[..., None]
        hm = gaussian_filter(hole.astype(np.float32), 4.0)[..., None]
        im = im * (1 - hm) + fillc * hm
        r, g, b = im[..., 0], im[..., 1], im[..., 2]
        lu = lum(im)
        a = gaussian_filter(a, 1.2)
        # 照片的上边淡出；左右两边不淡出，场景里左右各接一份镜像，接缝是连续的
        yy = np.arange(a.shape[0])[:, None] / a.shape[0]
        xx = np.arange(a.shape[1])[None, :] / a.shape[1]
        a = a * np.clip(yy / 0.04, 0, 1)
        # 去掉蓝天在云边上的残色：按 alpha 把颜色推向灰
        grey = lu[..., None] * np.ones(3)
        col = grey * 0.85 + im * 0.15
        # 暖色：亮部奶油色、略微过曝；暗部偏暖灰
        k = np.clip((lu - 0.35) / 0.6, 0, 1)[..., None]
        warm_hi = np.array([1.16, 1.08, 0.92])
        warm_lo = np.array([0.80, 0.74, 0.70])
        col = col * (warm_lo * (1 - k) + warm_hi * k) * (1.0 + 0.35 * k ** 2)
        col = 0.10 + col * 1.08                       # 抬起暗部：正午的云体透光，不发灰
        return np.dstack([col, a]).astype(np.float32)
    return disk("cloudbank", make, CLOUD_PHOTO, "v5")


def cloud_tex(blur=False):
    """blur=True 时给虚化的版本：L05 对焦在被单上，远处的云是虚的；镜头上移时焦点移到云上。"""
    if not blur:
        return cached("cloudtex", lambda: Tex(cloud_rgba()))

    def make():
        a = cloud_rgba()
        pm = a[..., :3] * a[..., 3:4]
        pm = gaussian_filter(pm, (11, 11, 0))
        al = gaussian_filter(a[..., 3], 11)
        return np.dstack([pm / np.maximum(al[..., None], 1e-4), al]).astype(np.float32)
    return cached("cloudtex_b", lambda: Tex(disk("cloudbank_blur", make, CLOUD_PHOTO, "v5")))


def cloud_geom():
    h, w = cloud_rgba().shape[:2]
    W, H = w / CLOUD_PPU, h / CLOUD_PPU
    return CLOUD_X0 + W / 2, CLOUD_TOP - H / 2, W, H


def cloud_items(t, opacity=1.0, focus=1.0):
    """focus：0 为虚（L05），1 为清楚（L06 起）。"""
    cx, cy, W, H = cloud_geom()
    items = []
    # 照片左右各接一份镜像，云堤一直铺到画面外
    for dx, uv in ((-W, (1, 0, 0, 1)), (0.0, (0, 0, 1, 1)), (W, (1, 0, 0, 1))):
        if focus < 0.999:
            items.append(Plane(cloud_tex(True), center=(cx + dx, cy, Z_SKY), size=(W, H), uv=uv, group="past",
                               opacity=opacity, stack="cloudbank"))
        if focus > 0.001:
            items.append(Plane(cloud_tex(), center=(cx + dx, cy, Z_SKY), size=(W, H), uv=uv, group="past",
                               opacity=opacity * focus, stack="cloudbank"))
    return items


def cloud_top_profile():
    """云顶的轮廓：每个世界 x 处，云体 alpha 首次超过 0.5 的世界 y（从上往下找），平滑后返回 (xs, ys)。"""
    def make():
        a = cloud_rgba()[..., 3]
        h, w = a.shape
        xs = np.arange(0, w, 8)
        ys = []
        for x in xs:
            col = gaussian_filter(a[:, max(0, x - 12):x + 12].mean(1), 6)
            idx = np.argmax(col > 0.55)
            ys.append(idx if col[idx] > 0.55 else h)
        return np.array([xs, ys], np.float32)
    xs, ys = cached("cloudprof", make)
    wx = CLOUD_X0 + xs / CLOUD_PPU
    wy = CLOUD_TOP - ys / CLOUD_PPU
    return wx, wy


# ---------------------------------------------------------------- 远处的一层云

FAR_PHOTO = "White_Cumulus_Clouds_against_Blue_Sky_3_.jpg"
FAR_Z = -30.0
FAR_PPU = 60.0
FAR_TOP = 13.0
FAR_X0 = -40.0


def far_cloud_tex():
    """另一张积云照片（同一作者，CC BY-SA 4.0）做远处的一层：缩小、略虚、对比降低、偏向天色，填在两层云之间的空天里，
    镜头移动时比近处的云走得慢。"""
    def make():
        im = photo(FAR_PHOTO)
        h, w = im.shape[:2]
        im = im[: int(h * 0.97)]
        r, g, b = im[..., 0], im[..., 1], im[..., 2]
        lu = lum(im)
        chroma = b - (r + g) / 2
        a = np.clip((0.19 - chroma) / 0.11, 0, 1) * np.clip((lu - 0.25) / 0.2, 0, 1)
        a = gaussian_filter(a, 2.5)
        yy = np.arange(a.shape[0])[:, None] / a.shape[0]
        xx = np.arange(a.shape[1])[None, :] / a.shape[1]
        a = a * np.clip(yy / 0.05, 0, 1)
        grey = gaussian_filter(lu, 2.0)[..., None] * np.ones(3)
        k = np.clip((grey - 0.35) / 0.6, 0, 1)
        col = grey * (np.array([0.80, 0.76, 0.74]) * (1 - k) + np.array([1.10, 1.04, 0.92]) * k)
        haze = np.array([0.80, 0.82, 0.84])
        col = col * 0.7 + haze * 0.3
        return np.dstack([col, a * 0.85]).astype(np.float32)
    return cached("farcloud", lambda: Tex(disk("farcloud", make, FAR_PHOTO, "f2")))


def far_cloud_items(t, opacity=1.0):
    tex = far_cloud_tex()
    h, w = tex.data.shape[:2]
    W, H = w / FAR_PPU, h / FAR_PPU
    return [Plane(tex, center=(FAR_X0 + W / 2 + dx, FAR_TOP - H / 2, FAR_Z), size=(W, H), uv=uv, group="past",
                  opacity=opacity) for dx, uv in ((-W, (1, 0, 0, 1)), (0.0, (0, 0, 1, 1)), (W, (1, 0, 0, 1)))]
