"""副歌一样片（L10–L14）的背景：夜空、远景剪影、水池水面、院子地面、水下，以及水底与裂沟。

这一段是五六十年代的夜。看过动态分镜后，大片纯黑的背景显得简陋，所以背景改用真实的公开照片和贴图，再按样张 B
的夜色风格化：夜蓝黑（#0E131B）的底，冷色的环境光，只在月亮、云边和几扇窗里留一点暖色。背景只作衬托，
亮度普遍压在 0.05–0.3 之间（调色前的数值，与样张 B 同一空间），最亮的是月亮（约 1.2，过去的调色会给它一圈
暖色光晕）；细节也收着，远处融进同一片夜色或水色里。所有素材都放在过去组（group="past"），合成时按
GRADE = {"past": {"halation": 1.2, "lift": 0.03, "gain": 1.25, "vignette": 0.38}} 调色。

空间布局与 scripts/film/plan.py 一致：墙面在 z = WALL.z，墙头 WALL.y + 8，墙脚 WALL.y - 7（院子地面）；
被淹没的北京展览馆立面在 z = SPIRE.z，建筑坐标原点在 SPIRE + (0, BUILDING_DY = -26, 0)，水面 WATER_Y = SPIRE.y，
露出水面的塔楼和尖塔到 SPIRE.y + 54；水底 SEABED_Y = WATER_Y - 13，裂沟底部在 CHASM.y - 2。

素材与推荐摆放

镜头在水面以上时用 sky_items()、silhouette_items()、pool_items(cam)、yard_items(cam)，在水面以下时用
underwater_items(cam, t)；backdrop_items(cam, t) 按镜头高度自动选择。每个函数返回 engine 的元素列表，
世界尺寸和位置都已按布局算好，下表列出它们的几何。

| 元素 | 函数 | 位置与朝向 | 世界尺寸 | 贴图 |
|---|---|---|---|---|
| 夜空 | sky_items() | 以 SKY_CENTER 为中心、半边长 1500 的立方体的前、左、右、顶四面 | 3000 × 1980（侧面） | sky_faces()，由全景投影 |
| 月亮 | sky_items(moon_dir=(偏航, 仰角)) | 方向 MOON_DIR = (-10°, 30°)，距中心 1440 | 月面直径 2.2°，月晕 7 倍 | moon_textures() |
| 远剪影带 | silhouette_items() | 中心 (SPIRE.x, WATER_Y + 21.5, SPIRE.z - 150)，正对 +z | 560 × 49 | silhouette_band("far") |
| 近剪影带 | silhouette_items() | 中心 (SPIRE.x, WATER_Y + 20.75, SPIRE.z - 75)，正对 +z | 440 × 47.5 | silhouette_band("near") |
| 水池水面 | pool_items(cam) | y = WATER_Y，z 从 WALL.z - 3 到 SPIRE.z - 75.5，以立面为界分成前后两块 | 520 × 183 | 材质 bd_water |
| 院子地面 | yard_items(cam) | y = 墙脚，自墙面向 +z 铺 40，左右比墙各宽 40 | 118 × 40 | yard_texture()，每 12 单位重复 |
| 水色背景 | underwater_items | 镜头前方 150 处，始终正对镜头 | 随视角 | 材质 bd_uw_fog |
| 水面下视 | underwater_items | 与水池水面同一块，正面朝下 | 520 × 183 | 材质 bd_uw_surface |
| 光柱 | underwater_items | 上端在立面前方的水面上（网格布点），沿折射后的月光方向斜向下，宽面始终对着镜头 | 宽 3–8，长约 20 | 材质 bd_uw_rays |
| 悬浮颗粒 | underwater_items | 镜头周围 70 × 36 × 70 的周期方盒，颗粒固定在世界里缓慢漂移 | 约 5000 粒，直径 0.04–0.13 | Particles，加法混合 |
| 水底 | underwater_items | y = SEABED_Y，以尖塔为中心，挖出裂沟的口 | 260 × 260 | seabed_texture()，材质 bd_floor |
| 沟壁与沟底 | underwater_items | 沿裂沟两岸，从水底竖直向下 5，再向外张开 8 直到 CHASM.y - 2 | 两岸各 47 段，每段上下两块 | crack_wall_texture()，材质 bd_floor |

夜空全景（sky_panorama()，8192 × 2730）横向覆盖偏航 -135°–135°、纵向覆盖仰角 80°–-10°，左右两端首尾相接，
也可以直接当一块大平面用：放在约 1500 单位外、宽约 8000、高约 2700。剪影带、水面贴图和地面贴图也可以单独取用，
函数的文档字符串写明了各自的格式。全部贴图都是 0–1 的浮点 RGBA（直通 alpha，第 0 行是图像顶部），亮部可以略超过 1。

排序

引擎按元素上离镜头最近的点排序，铺在镜头下方或四周的大平面因此会被误当作最近的元素，画在最上面。本模块
按当前镜头给这些平面算好偏移：天空、水下背景、水面下视、水底与沟壁总是最先画；水池水面的后一块（立面以后）
排在近剪影带之后、立面之前，前一块（立面以前）排在立面之后；院子地面排在墙之前。所以 pool_items、yard_items、
underwater_items 都要传入当前镜头，并且每个子帧重新调用。场景里的其他元素（墙、字、花、尖塔、碎块）照常排序，
都会画在这些背景之上。

与尖塔和水下物体的接口

水面倒影里的尖塔用 spire_card(立面贴图) 生成卡片，传给 pool_items(cam, cards=[卡片])；卡片的格式是
(纹理, (中心 x, 中心 y, 宽, 高), z)，描述一块正对 +z 的竖直平面，只有水面以上的部分会被反射到。立面前方的水面
略透明（see_alpha，缺省 0.82）：刚没入水面的横幅隐约透出约两成，越深越看不见。要看到这个效果，立面和横幅必须先于
前方水面画出，做法是给它们和前方水面同一个 stack（pool_items 的 front_stack 参数），并按"立面、横幅、前方水面"
的顺序加入画面。水下的立面、横幅、碎块和字可以用材质 bd_uw_obj，它按水深加上水下的光色、按距离融进水色，
与背景一致（uniforms 用 dict(UW_DEFAULTS, uo_light=1.0)，uo_light 为 0 时只加雾、不改颜色）。

裂沟开在立面脚下：远岸在立面背后约 1.5–2.2 单位，近岸在立面正前方鼓出，正中离立面约 18 单位，向两侧收窄，
到 ±75 单位处合拢。x ∈ [SPIRE.x - 8.5, SPIRE.x + 8.5] 范围内，开口覆盖 z ∈ [SPIRE.z - 1.45, SPIRE.z + 14.7]，
横幅碎块和"摔碎進溝裡"五个字都直接沉进沟里；镜头下降到 SPIRE + (-0.5, -15.5, 15) 时在沟口以下 2.5 单位、
两岸沟壁之间。沉进沟里的物体照常排序即可，水底与沟壁总是先画。

材质参数

导入模块时注册六种材质：bd_water、bd_ground、bd_uw_fog、bd_uw_surface、bd_uw_rays、bd_floor，以及给水下物体用的
bd_uw_obj。值得调整的参数都可以作为关键字传给对应的函数：pool_items 的 bw_ripple_k（细纹强度，0.010）、
bw_swell_k（大尺度起伏，0.010）、bw_flow（细纹流速，0.18 单位/秒）、bw_refl（倒影强度，0.9）、bw_glitter
（月光碎光，1.0）；underwater_items 的 ur_k（光柱亮度，1.0）、uf_caustic（水底焦散，0.5）、uf_adapt（镜头进到
沟里以后沟壁提亮的倍数，3.5）、us_bright（水面下视的天光增益，2.6），以及 UW_DEFAULTS 里的水色和能见距离。
水面的细纹、倒影的摇晃、光柱的摆动、水底焦散和颗粒漂移都随时间连续变化，由帧时刻决定，分段渲染时结果一致。

做法与授权

夜空取三张 CC0 照片（Kolleröd 的两张月夜云、Brofjorden 的月夜云），去掉月亮、星点和地面后换算成"相对晴空的
亮度"，在全景上羽化拼接，再按仰角映射成夜蓝黑到冷灰的云，月亮另做一层，可以单独移动。剪影从白杨照片
（SK53，CC BY-SA 2.0）和北科大苏式楼的两张照片（ruiraykwok，CC BY-SA 3.0）按与天空的色差抠出，楼两端补出
四坡顶的斜脊，排成远近两条带。水面细纹取自 Brofjorden 照片的远处水面。院子地面混合 Poly Haven 的旧砖铺地
（Rob Tuytel）与夯土（Charlotte Baglioni），水底与沟壁用 Poly Haven 的干河床岩石（Amal Kumar），三张贴图都是 CC0，
由 scripts/fetch_images.py 从 Wikimedia Commons 下载，授权记录在 assets/images/credits.json。剪影用到的照片是
CC BY-SA，成片要在视频简介里署名。计算量大的结果缓存在 data/cache/seg_c/bd_*.npz，改了参数会按新的键重新计算。

运行 python backdrop.py 输出每样素材的单图和合成参考到 renders/seg_c/assets/（previews 或 composites 只运行其一）。

范围与局限

水面倒影只反射天空、月亮、两条剪影带和最多两张卡片，墙、花和字不进倒影；倒影按射线与竖直卡片求交，卡片以外的
物体需要的话要另做卡片。水下仰望时，露出水面的塔楼会直接画在水面下视之上，没有折射变形，镜头在水下时宜把立面
截到水面以下。
"""
import hashlib
import math
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "style"))
sys.path.insert(0, str(HERE.parent / "film"))
import look as L  # noqa: E402

IMG = ROOT / "assets" / "images"
CACHE = ROOT / "data" / "cache" / "seg_c"
OUT = ROOT / "renders" / "seg_c" / "assets"
VERSION = "bd5"

LUMA = np.array([0.3, 0.55, 0.15], np.float32)
NIGHT = L.C["night"].astype(np.float32)          # 夜蓝黑 #0E131B


# ---------------------------------------------------------------------------
# 通用：缓存、读图、噪声
# ---------------------------------------------------------------------------

def _cached(name, fn, *key):
    """把计算量大的结果存进 data/cache/seg_c/（半精度 npz），键里包含版本号和参数。"""
    CACHE.mkdir(parents=True, exist_ok=True)
    h = hashlib.md5(repr((VERSION,) + key).encode()).hexdigest()[:10]
    p = CACHE / f"bd_{name}_{h}.npz"
    if p.exists():
        with np.load(p) as z:
            return z["a"].astype(np.float32)
    a = np.asarray(fn(), np.float32)
    np.savez(p, a=a.astype(np.float16))
    return a


def _photo(name):
    return np.asarray(Image.open(IMG / name).convert("RGB"), np.float32) / 255


def _lum(im):
    return im @ LUMA


def _ramp(x, a, b):
    return np.clip((x - a) / (b - a), 0.0, 1.0)


def _smooth(x, a, b):
    t = _ramp(x, a, b)
    return t * t * (3 - 2 * t)


def _remove_points(im, thresh=0.06, size=7):
    """去掉照片里的星点和噪点：比周围亮出一截的小亮点，用周围像素修补。"""
    lum = _lum(im)
    opened = cv2.morphologyEx(lum, cv2.MORPH_OPEN, np.ones((size, size), np.uint8))
    m = ((lum - opened) > thresh).astype(np.uint8)
    m = cv2.dilate(m, np.ones((5, 5), np.uint8))
    if m.sum() == 0:
        return im
    u8 = (np.clip(im, 0, 1) * 255).astype(np.uint8)
    return cv2.inpaint(u8, m * 255, 5, cv2.INPAINT_TELEA).astype(np.float32) / 255


def _remove_disc(im, cx, cy, r, soften=0):
    """挖掉圆盘（月亮），用周围的云修补；soften 为修补后在圆盘附近追加的模糊半径。"""
    m = np.zeros(im.shape[:2], np.uint8)
    cv2.circle(m, (int(cx), int(cy)), int(r), 255, -1)
    u8 = (np.clip(im, 0, 1) * 255).astype(np.uint8)
    out = cv2.inpaint(u8, m, 9, cv2.INPAINT_TELEA).astype(np.float32) / 255
    if soften:
        yy, xx = np.mgrid[0:im.shape[0], 0:im.shape[1]].astype(np.float32)
        w = np.exp(-((xx - cx) ** 2 + (yy - cy) ** 2) / (2 * (r * 1.6) ** 2))[..., None]
        out = out * (1 - w) + cv2.GaussianBlur(out, (0, 0), soften) * w
    return out


# ---------------------------------------------------------------------------
# 一、夜空全景
# ---------------------------------------------------------------------------
# 全景按"经纬"展开：横向是方位角（偏航），纵向是仰角，每度约 30.3 像素。
# 横向覆盖 -135°–135°（0° 为 -z 方向，正值偏向 +x），左右两端首尾相接；纵向覆盖仰角 80°（顶）到 -10°（底）。

PANO_W, PANO_H = 8192, 2730
YAW0, YAW1 = -135.0, 135.0
EL_TOP, EL_BOT = 80.0, -10.0
PX_DEG = PANO_W / (YAW1 - YAW0)
MOON_DIR = (-10.0, 30.0)                 # 月亮的缺省方向（偏航、仰角，度），与全景里月光照亮的云对齐；改动后全景重新计算
K_FILE = "Moon_in_clouds_over_Kolleröd.jpg"
B_FILE = "Moon_and_clouds_over_Kolleröd_beach_4.jpg"
F_FILE = "Moon_and_clouds_over_Brofjorden_2.jpg"
K_MOON = (1214.0, 1075.0, 101.0)          # 照片 K 里月亮的圆心与半径（像素）
K_SCALE = 0.62


def yaw_to_x(yaw):
    return (np.asarray(yaw) - YAW0) * PX_DEG


def el_to_y(el):
    return (EL_TOP - np.asarray(el)) * PX_DEG


def _relative(im, clear_q=0.5, local=0.5, local_sigma=260):
    """照片 → (相对亮度 r, 偏暖程度 w, 晴空程度 c)。

    r = log2(亮度 / 参照亮度)：比参照亮的云（月光照亮的云边）为正，暗的云团为负。参照亮度是晴空亮度与大尺度平滑
    亮度按 local 加权的几何平均：local 越大，照片里大范围的明暗渐变（例如暮色天空一侧亮一侧暗）被消去得越多，
    只留下云本身的明暗。这样不同照片的曝光和渐变差别被消去，拼接处只比较云。
    w 为云里偏粉、偏暖的程度（相对晴空的蓝），c 为晴空的程度（饱和的蓝、细节少）。"""
    lum = np.maximum(_lum(im), 1e-3)
    hsv = cv2.cvtColor(np.clip(im, 0, 1), cv2.COLOR_RGB2HSV)
    sat = hsv[..., 1]
    rb = (im[..., 0] - im[..., 2]) / lum
    clear0 = sat > np.quantile(sat, 0.7)
    ref_lum = float(np.quantile(lum[clear0], clear_q))
    ref_rb = float(np.median(rb[clear0]))
    small = cv2.resize(lum, None, fx=0.125, fy=0.125, interpolation=cv2.INTER_AREA)
    bg = cv2.resize(gaussian_filter(small, local_sigma / 8, mode="nearest"), (lum.shape[1], lum.shape[0]),
                    interpolation=cv2.INTER_CUBIC)
    ref = np.exp((1 - local) * np.log(ref_lum) + local * np.log(np.maximum(bg, 1e-3)))
    r = np.log2(lum / ref)
    r -= float(np.median(r[clear0]))                      # 晴空处 r 归零，各张照片的晴空对齐
    detail = np.abs(lum - gaussian_filter(lum, 6)) / lum
    c = _ramp(sat, 0.32, 0.52)
    c = gaussian_filter(c * np.clip(1 - detail * 12, 0, 1), 4)
    w = np.clip((rb - ref_rb) * 1.6, 0, 1) * (1 - c)
    return np.dstack([r, w, c]).astype(np.float32)


def _sky_sources():
    """三张 CC0 夜空照片，去掉月亮、星点和地面，换算成相对亮度。"""
    K = _photo(K_FILE)
    K = _remove_points(K)
    K = _remove_disc(K, K_MOON[0], K_MOON[1], K_MOON[2] * 1.12, soften=14)
    B = _photo(B_FILE)[:1090]
    B = _remove_points(B)
    B = _remove_disc(B, 2513, 442, 46, soften=10)
    F = _photo(F_FILE)[:1000, 1440:]
    F = _remove_points(F)
    rk, rb, rf = _relative(K, local=0.45), _relative(B, local=0.6), _relative(F, local=0.9, local_sigma=180)
    rf[..., 0] *= 0.85
    # F 下部是暮色里最亮的一段天，经过亮度归一后仍偏亮偏暖：越往下压得越多，暖色也去掉
    yy = np.arange(rf.shape[0], dtype=np.float32)[:, None]
    rf[..., 0] -= 0.35 * _ramp(yy, 450, 950) * np.maximum(rf[..., 0], 0) + 0.12 * _ramp(yy, 500, 950)
    rf[..., 1] *= 0.3
    # B 的月亮藏在云里，周围一圈亮云；月亮已另做成单独的一层，这里把那圈亮光压下去，只留云边
    yy, xx = np.mgrid[0:rb.shape[0], 0:rb.shape[1]].astype(np.float32)
    halo = np.exp(-((xx - 2513) ** 2 + (yy - 442) ** 2) / (2 * 190.0 ** 2))
    rb[..., 0] -= 0.75 * halo * np.maximum(rb[..., 0], 0) + 0.25 * halo
    rk = cv2.resize(rk, None, fx=K_SCALE, fy=K_SCALE, interpolation=cv2.INTER_AREA)
    return rk, rb, rf


def _feather(h, w, left, right, top, bottom):
    """粘贴用的羽化权重：四边各自从 0 渐变到 1（给 0 表示该边不羽化）。"""
    yy = np.arange(h, dtype=np.float32)[:, None]
    xx = np.arange(w, dtype=np.float32)[None, :]
    m = np.ones((h, w), np.float32)
    if left:
        m *= _smooth(xx, 0, left)
    if right:
        m *= _smooth(w - 1 - xx, 0, right)
    if top:
        m *= _smooth(yy, 0, top)
    if bottom:
        m *= _smooth(h - 1 - yy, 0, bottom)
    return m


def _paste(canvas, src, x0, y0, weight):
    """把 src 按权重叠到 canvas 上，x 方向首尾相接（超出右端的部分绕回左端）。"""
    H, W = canvas.shape[:2]
    h, w = src.shape[:2]
    ya, yb = max(0, y0), min(H, y0 + h)
    sa = ya - y0
    xs = (np.arange(w) + x0) % W
    # 按连续段写入，避免逐列循环
    cuts = np.where(np.diff(xs) < 0)[0] + 1
    for seg in np.split(np.arange(w), cuts):
        if len(seg) == 0:
            continue
        cx0 = xs[seg[0]]
        sl = slice(cx0, cx0 + len(seg))
        wgt = weight[sa:sa + (yb - ya), seg[0]:seg[-1] + 1, None]
        canvas[ya:yb, sl] = canvas[ya:yb, sl] * (1 - wgt) + src[sa:sa + (yb - ya), seg[0]:seg[-1] + 1] * wgt


def _sky_relative_pano():
    """在全景上排布三张照片（相对亮度表示），羽化拼接，首尾相接。

    正前方（偏航 0° 附近）是主景：上方是照片 K 里月亮周围被照亮的大片云，月亮落在 MOON_DIR；下方贴着地平线是
    照片 B 缩小后的一带低云，两者之间留出一段较亮的晴空，远景剪影就衬在这段亮处。左右两侧是 B（原尺寸）与
    F 的长条层云，一直绕到全景两端，首尾相接。"""
    rk, rb, rf = _sky_sources()
    H, W = PANO_H, PANO_W
    rng = np.random.default_rng(7)
    canvas = np.zeros((H, W, 3), np.float32)
    n = cv2.resize(rng.normal(0, 1, (H // 64, W // 64)).astype(np.float32), (W, H), interpolation=cv2.INTER_CUBIC)
    n = gaussian_filter(n, 90)
    canvas[..., 0] = n / (n.std() + 1e-6) * 0.035
    canvas[..., 2] = 1.0

    def place(src, x0, y0, fl, fr, ft, fb, extend=True):
        h, w = src.shape[:2]
        _paste(canvas, src, x0, y0, _feather(h, w, fl, fr, ft, fb))
        below = H - (y0 + h) + fb
        if extend and below > 0:                    # 下沿以下：把最下面的云向下翻折，直到全景底部
            ext = src[::-1][:below]
            _paste(canvas, ext, x0, y0 + h - fb, _feather(len(ext), w, fl, fr, fb, 0))

    # 两侧：F 的长条层云在左，B 的积云带在右，绕回全景左端与 F 相接
    hf, wf = rf.shape[:2]
    place(rf, 640, int(el_to_y(1.5)) - hf, 500, 700, 320, 60)
    hb, wb = rb.shape[:2]
    place(rb, 5300, int(el_to_y(-1.0)) - hb, 600, 420, 300, 40)
    # 正前方贴地平线的低云：B 缩小到 0.6，从左往右略微错开，避开它自己右侧那片已压暗的亮云
    rb2 = cv2.resize(rb[:, :2300], None, fx=0.6, fy=0.6, interpolation=cv2.INTER_AREA)
    h2, w2 = rb2.shape[:2]
    place(rb2, int(yaw_to_x(-36)), int(el_to_y(-1.5)) - h2, 520, 520, 260, 30)
    # 主景：K
    hk, wk = rk.shape[:2]
    mx, my = K_MOON[0] * K_SCALE, K_MOON[1] * K_SCALE
    xk = int(yaw_to_x(MOON_DIR[0]) - mx)
    yk = int(el_to_y(MOON_DIR[1]) - my)
    place(rk, xk, yk, 700, 560, 380, 420, extend=False)
    # 地平线以下（被剪影和水面挡住的部分）逐渐压平，避免翻折出来的云像倒影
    el = EL_TOP - np.arange(H, dtype=np.float32) / PX_DEG
    k = _smooth(-el, 1.0, 8.0)[:, None]
    canvas[..., 0] = canvas[..., 0] * (1 - k) + (gaussian_filter(canvas[..., 0], 30) * 0.5 - 0.25) * k
    # 贴近地平线的几小块亮云（原照片里被暮光照亮）会从剪影的缝里露出亮斑，压到与周围相当
    cap = 0.05 + 0.55 * _ramp(el, 3.0, 16.0)[:, None]
    canvas[..., 0] = np.minimum(canvas[..., 0], cap + 0.25 * np.tanh((canvas[..., 0] - cap) / 0.25).clip(0))
    return canvas


def _sky_colorize(rel):
    """相对亮度 → 这一段的夜色（调色前的数值，与样张 B 同一空间）。

    晴空取夜蓝黑，天顶更暗、近地平线略亮；比晴空暗的云团压成更暗、更灰的蓝黑；被月光照亮的云边提亮成冷灰，
    原照片里偏粉的云边保留一点暖灰。亮度整体收着：最亮的云边约 0.3，不抢前景的字。"""
    r, w, c = rel[..., 0], rel[..., 1], rel[..., 2]
    H, W = r.shape
    el = EL_TOP - (np.arange(H, dtype=np.float32) / PX_DEG)
    # 晴空亮度随仰角：天顶 0.85 倍，往下逐渐变亮，地平线处约 1.9 倍（相对夜蓝黑的 1.45 倍）。
    # 地平线一带的天光最亮，远景剪影衬在这段亮处才看得清
    gk = (0.85 + 0.35 * np.exp(-np.maximum(el, 0) / 30.0) + 0.7 * np.exp(-np.maximum(el, 0) / 9.0))[:, None]
    base_l = float(NIGHT @ LUMA) * 1.65 * gk
    # 局部对比：云团内部的褶皱和明暗按 40 像素的尺度加强一些，暗的云团才不是一片平的灰
    rr = gaussian_filter(r, 1.2)
    small = cv2.resize(rr, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)
    blur = cv2.resize(gaussian_filter(small, 10), (W, H), interpolation=cv2.INTER_LINEAR)
    rr = rr + 0.9 * (rr - blur)
    lum = base_l * np.exp2(np.where(rr > 0, rr * 1.45, rr * 0.7))
    lum = lum / (1 + np.maximum(lum - 0.28, 0) * 2.0)          # 云边的高光压一个软肩
    cloud = np.clip(1 - c, 0, 1)
    blue = NIGHT / float(NIGHT @ LUMA)                          # 夜蓝黑的色相（单位亮度）
    gray = np.array([0.88, 1.0, 1.16], np.float32)               # 云：冷灰
    warm = np.array([1.12, 1.0, 0.86], np.float32)               # 偏粉的云边：暖灰
    lit = _ramp(rr, 0.1, 0.8)
    tint = blue[None, None] * (1 - cloud[..., None] * 0.6) + gray[None, None] * cloud[..., None] * 0.6
    wk = (w * cloud * lit * _ramp(el, 12.0, 22.0)[:, None])[..., None] * 0.75     # 暖灰只留给高处月光照亮的云边
    tint = tint * (1 - wk) + warm[None, None] * wk
    tint = tint / (tint @ LUMA)[..., None]
    return (lum[..., None] * tint).astype(np.float32)


def _sky_rel():
    return _cached("skyrel", _sky_relative_pano, PANO_W, PANO_H, MOON_DIR, K_SCALE)


def sky_panorama():
    """夜空全景（不含月亮和星点），float32 RGBA，(2730, 8192, 4)，alpha 恒为 1，第 0 行是仰角 80°。

    横向 8192 像素对应偏航 -135°–135°，纵向对应仰角 80°–-10°，地平线在第 2427 行；左右两端首尾相接，
    可以平铺。直接当一块大平面用时，建议放在约 1500 单位外、宽约 8000、高约 2700。
    一般用 sky_items()，它把全景投影到围绕镜头的几块大平面上，镜头怎样转都看不出接缝。"""
    def make():
        rel = _sky_rel()
        col = _sky_colorize(rel)
        return np.dstack([col, np.ones(col.shape[:2], np.float32)])
    return _cached("skypano", make, PANO_W, PANO_H, MOON_DIR, K_SCALE, "c2")


def moon_textures():
    """月亮：(月面 RGBA, 月晕 RGBA)。

    月面取自照片 K 的上弦月，去掉背景天空后压成偏暖的银白，亮部约 1.25（略超过 1，过去的调色会给它一圈暖色光晕）；
    纹理边长 512，月面直径约占 440 像素。月晕是以月亮为中心的柔和光斑，用 blend="add" 叠加，边长同样对应月面直径的
    7 倍。两者都放在同一个中心上，月面平面的边长取直径 ×512/440，月晕平面取直径 ×7。"""
    def make():
        im = _photo(K_FILE)
        cx, cy, r = K_MOON
        R = int(r * 1.22)
        crop = im[int(cy) - R:int(cy) + R, int(cx) - R:int(cx) + R]
        lum = _lum(crop)
        # 天空背景：月面以外一圈的亮度，月面减去它，剩下的是月亮本身
        yy, xx = np.mgrid[0:2 * R, 0:2 * R].astype(np.float32)
        d = np.hypot(xx - R, yy - R)
        # 月面亮度在 0.8 以上，旁边被照亮的云最多约 0.7：按亮度阈值取月面，闭运算补上环形山的暗斑
        core = (lum > 0.76) & (d < r * 1.06)
        core = cv2.morphologyEx(core.astype(np.uint8), cv2.MORPH_CLOSE, np.ones((9, 9), np.uint8))
        n_, lab, st, _ = cv2.connectedComponentsWithStats(core)
        core = (lab == 1 + int(np.argmax(st[1:, 4]))).astype(np.float32)
        a = np.clip(cv2.GaussianBlur(core, (0, 0), 1.2) * 1.15, 0, 1)
        moon_l = lum[core > 0.5]
        tone = 0.78 + 0.32 * np.clip((lum - moon_l.min()) / (np.quantile(moon_l, 0.97) - moon_l.min() + 1e-3), 0, 1.1)
        rgb = np.array([1.0, 0.96, 0.86], np.float32)[None, None] * tone[..., None] * 1.08
        moon = np.dstack([rgb, a]).astype(np.float32)
        moon = cv2.resize(moon, (512, 512), interpolation=cv2.INTER_AREA)
        return moon
    moon = _cached("moon", make, K_MOON)
    n = 512
    yy, xx = np.mgrid[0:n, 0:n].astype(np.float32)
    d = np.hypot(xx - n / 2 + 0.5, yy - n / 2 + 0.5) / (n / 2)           # 0 中心，1 边缘（= 3.5 个月面直径）
    rr = d * 3.5                                                          # 以月面直径为单位的距离
    glow = 0.55 * np.exp(-rr / 0.32) + 0.12 * np.exp(-(rr / 1.3) ** 2) + 0.03 * np.exp(-rr / 1.6)
    glow *= _smooth(1 - d, 0.0, 0.25)
    halo = np.dstack([glow[..., None] * np.array([0.78, 0.84, 0.98], np.float32), np.ones((n, n), np.float32)])
    return moon, halo.astype(np.float32)


# ---------------------------------------------------------------------------
# 场景布局（与 scripts/film/plan.py 一致）
# ---------------------------------------------------------------------------
try:
    import plan as _plan
    WALL = np.asarray(_plan.WALL, float)            # 墙面中点：墙面在 z = WALL.z，墙头 WALL.y + 8，墙脚 WALL.y - 7
    SPIRE = np.asarray(_plan.SPIRE, float)          # 尖塔塔基（水面高度）
    WATER_Y = float(_plan.WATER_Y)
    CHASM = np.asarray(_plan.CHASM, float)          # 裂沟底部
except Exception:                                    # 单独使用本模块时的后备数值
    WALL = np.array([434.0, 140.0, 0.2])
    SPIRE = WALL + [30.0, -20.0, -110.0]
    WATER_Y = float(SPIRE[1])
    CHASM = SPIRE + [0.0, -40.0, 0.0]
GROUND_Y = WALL[1] - 7.0                             # 院子地面 = 墙脚
SEABED_Y = WATER_Y - 13.0                            # 水底
SKY_CENTER = np.array([SPIRE[0] - 10.0, SPIRE[1] + 40.0, SPIRE[2] + 50.0])
SKY_DIST = 1500.0


def dir_from(yaw, el):
    """偏航、仰角（度）→ 世界方向（单位向量）。偏航 0 指向 -z，正值偏向 +x。"""
    y, e = math.radians(yaw), math.radians(el)
    return np.array([math.sin(y) * math.cos(e), math.sin(e), -math.cos(y) * math.cos(e)])


# 天空的四个面：(名称, 旋转, 纹理宽, 纹理高, 面的下沿在面坐标里的位置 ly_min)
_FACES = [("front", (0.0, 0.0, 0.0), 3072, 2028, -0.32),
          ("left", (90.0, 0.0, 0.0), 3072, 2028, -0.32),
          ("right", (-90.0, 0.0, 0.0), 3072, 2028, -0.32),
          ("top", (0.0, 90.0, 0.0), 3072, 3072, -1.0)]


def _face_dirs(rot, w, h, ly_min):
    from engine import rot_matrix
    R = rot_matrix(*rot)
    lx = (np.arange(w, dtype=np.float32) + 0.5) / w * 2 - 1
    ly = 1 - (np.arange(h, dtype=np.float32) + 0.5) / h * (1 - ly_min)
    LX, LY = np.meshgrid(lx, ly)
    d = -R[:, 2][None, None] + R[:, 0][None, None] * LX[..., None] + R[:, 1][None, None] * LY[..., None]
    return (d / np.linalg.norm(d, axis=2, keepdims=True)).astype(np.float32)


def _sample_pano(pano, dirs):
    yaw = np.degrees(np.arctan2(dirs[..., 0], -dirs[..., 2]))
    el = np.degrees(np.arcsin(np.clip(dirs[..., 1], -1, 1)))
    px = ((yaw - YAW0) * PX_DEG) % PANO_W
    py = np.clip((EL_TOP - el) * PX_DEG, 0, PANO_H - 1.001)
    return cv2.remap(pano, px.astype(np.float32), py.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_WRAP)


def _stars(dirs, clear, seed):
    """极淡的星点：只撒在晴空处、仰角 10° 以上，越往地平线越少；平均每 100 平方度不到一颗。"""
    rng = np.random.default_rng(seed)
    h, w = clear.shape
    el = np.degrees(np.arcsin(np.clip(dirs[..., 1], -1, 1)))
    out = np.zeros((h, w), np.float32)
    n = int(h * w / 60000)
    ys, xs = rng.integers(0, h, n), rng.integers(0, w, n)
    keep = (el[ys, xs] > 10) & (rng.uniform(0, 1, n) < clear[ys, xs] ** 2 * _ramp(el[ys, xs], 10, 30))
    ys, xs = ys[keep], xs[keep]
    amp = 0.035 + 0.16 * rng.uniform(0, 1, len(ys)) ** 6
    out[ys, xs] = amp
    out = gaussian_filter(out, 0.9) * 2 * math.pi * 0.81
    return out


def sky_faces():
    """把全景投影到围绕镜头的四块大平面（前、左、右、顶）上，加上星点。返回 {名称: RGBA}。"""
    out = {}
    pano = None
    for k, (name, rot, w, h, lym) in enumerate(_FACES):
        def make(rot=rot, w=w, h=h, lym=lym, k=k):
            nonlocal pano
            if pano is None:
                pano = np.ascontiguousarray(sky_panorama()[..., :3])
                rel = _sky_rel()
                pano = np.dstack([pano, rel[..., 2:3]])
            dirs = _face_dirs(rot, w, h, lym)
            s = _sample_pano(pano, dirs)
            col, clear = s[..., :3], np.clip(s[..., 3], 0, 1)
            col = col + _stars(dirs, clear, 11 + k)[..., None] * np.array([0.92, 0.95, 1.0], np.float32)
            return np.dstack([col, np.ones((h, w), np.float32)])
        out[name] = _cached("sky_" + name, make, rot, w, h, lym, PANO_W, MOON_DIR, "f2")
    return out


_TEX = {}


def _tex(key, fn, **kw):
    """场景用的纹理对象，按键缓存在进程里（同一数组只上传一次显卡）。"""
    if key not in _TEX:
        from engine import Tex
        _TEX[key] = Tex(fn(), **kw)
    return _TEX[key]


def sky_items(moon_dir=None, moon_size=2.2, moon=True, center=None, dist=SKY_DIST, group="past"):
    """夜空：四块天空平面 + 月晕 + 月面。

    天空平面组成一个以 center（缺省 SKY_CENTER）为中心、半边长 dist（缺省 1500）的立方体的前、左、右、顶四个面，
    镜头在这个立方体里任意移动几十个单位都几乎看不出视差。四个面都设 bias=1e4、同属 stack "bd_sky"，
    所以总是最先画（引擎按离镜头最近的点排序，铺在镜头侧面和头顶的大平面不加偏移会被画到最上面）。
    moon_dir 为月亮方向（偏航、仰角，度），缺省 MOON_DIR=(-10, 30)，与全景里月光照亮的那片云对齐；
    moon_size 为月面直径（度）。"""
    from engine import Plane, rot_matrix
    c = SKY_CENTER if center is None else np.asarray(center, float)
    faces = sky_faces()
    items = []
    for name, rot, w, h, lym in _FACES:
        R = rot_matrix(*rot)
        lyc = (1 + lym) / 2
        ctr = c - R[:, 2] * dist + R[:, 1] * lyc * dist
        tex = _tex("sky_" + name, lambda n=name: faces[n], repeat=False)
        items.append(Plane(tex, center=ctr, size=(2 * dist, (1 - lym) * dist), rot=rot, group=group,
                           stack="bd_sky", bias=1e4))
    if moon:
        yaw, el = MOON_DIR if moon_dir is None else moon_dir
        d = dir_from(yaw, el)
        dm = dist * 0.96
        pos = c + d * dm
        # 平面朝向球心：yaw 使法线水平分量对准 -d，pitch 使法线竖直分量为 -d.y
        yaw_p = math.degrees(math.atan2(-d[0], -d[2]))
        pitch_p = math.degrees(math.asin(np.clip(d[1], -1, 1)))
        rot = (yaw_p, pitch_p, 0.0)
        diam = 2 * dm * math.tan(math.radians(moon_size) / 2)
        mtex, htex = moon_textures()
        mt = _tex("moon", lambda: mtex)
        ht = _tex("moon_halo", lambda: htex)
        items.append(Plane(ht, center=pos, size=(diam * 7, diam * 7), rot=rot, blend="add", group=group,
                           stack="bd_sky", bias=1e4))
        items.append(Plane(mt, center=pos, size=(diam * 512 / 440, diam * 512 / 440), rot=rot, group=group,
                           stack="bd_sky", bias=1e4))
    return items


# ---------------------------------------------------------------------------
# 二、远景剪影
# ---------------------------------------------------------------------------
# 白杨取自 geograph 的白杨剪影照片（SK53，CC BY-SA 2.0），苏式楼取自北科大的两张照片（ruiraykwok，CC BY-SA 3.0）。
# 先在照片里估出天空的颜色场，按与天空的色差抠出轮廓（细枝处是半透明的），再把各个轮廓排成两条带。

POPLAR_FILE = "Poplar_silhouette_-_geograph_org_uk_-_6023568.jpg"
USTB_FILE = "北科大的苏式楼_USTB_-_panoramio.jpg"
NINGGU_FILE = "北科大_苏式楼_凝固的时光_-_panoramio.jpg"


def _sky_field(im, sky0, sigma=60):
    """由确定是天空的像素估出整幅照片的天空颜色（归一化卷积）：天空被遮住处取周围天空颜色的平滑外推。"""
    f = 4
    small = cv2.resize(im, (im.shape[1] // f, im.shape[0] // f), interpolation=cv2.INTER_AREA)
    w = cv2.resize(sky0.astype(np.float32), (im.shape[1] // f, im.shape[0] // f), interpolation=cv2.INTER_AREA)
    out = np.zeros_like(small)
    acc = np.zeros(w.shape, np.float32)
    for s in (sigma / f, sigma * 3 / f, sigma * 9 / f):
        num = gaussian_filter(small * w[..., None], (s, s, 0), mode="nearest")
        den = gaussian_filter(w, s, mode="nearest")
        est = num / np.maximum(den, 1e-6)[..., None]
        k = np.clip(den * 4, 0, 1) * (1 - acc)
        out += est * k[..., None]
        acc += k
    out /= np.maximum(acc, 1e-6)[..., None]
    return cv2.resize(out, (im.shape[1], im.shape[0]), interpolation=cv2.INTER_CUBIC)


def _cut_poplar():
    """白杨剪影照片：天空是浅紫灰，树枝暗。按亮度与天空的差抠出，树下的树篱和地面全部不透明。"""
    im = _photo(POPLAR_FILE)
    lum = _lum(im)
    var = np.abs(lum - gaussian_filter(lum, 3))
    sky0 = (lum > 0.6) & (var < 0.012)
    sky0[640:] = False
    sky = _lum(_sky_field(im, sky0, 30))
    a = np.clip((sky - lum - 0.04) / np.maximum(sky - 0.16, 0.2), 0, 1) ** 0.75
    # 树篱的上沿：每一列自 600 行往下第一个持续变暗的位置，以下全部不透明
    h, w = lum.shape
    yy = np.arange(h)[:, None]
    dark = gaussian_filter((lum < 0.33).astype(np.float32), (3, 2)) > 0.6
    dark[:615] = False
    top = np.where(dark.any(0), dark.argmax(0), h)
    top = gaussian_filter(top.astype(np.float32), 2)
    a = np.maximum(a, _smooth(yy - top[None, :], -3, 3))
    return a.astype(np.float32), im


def _cut_ustb():
    """北科大苏式楼（单栋，带坡顶和烟囱）：按与天空颜色场的色差抠出；楼身以下全部不透明。右边的现代楼裁掉。"""
    im = _photo(USTB_FILE)[:, :1168]
    lum = _lum(im)
    hsv = cv2.cvtColor(im, cv2.COLOR_RGB2HSV)
    var = np.abs(lum - gaussian_filter(lum, 2))
    sky0 = (im[..., 2] - im[..., 0] > 0.18) & (hsv[..., 1] > 0.35) & (var < 0.01)
    sky0[1000:] = False
    sky = _sky_field(im, sky0, 40)
    d = np.linalg.norm(im - sky, axis=2)
    a = np.clip((d - 0.035) / 0.09, 0, 1)
    # 楼与地面：自第一行不透明处往下全部填实（只对楼的范围，树冠里的空隙保留）
    h, w = a.shape
    solid = a > 0.6
    first = np.where(solid.any(0), solid.argmax(0), h)
    yy = np.arange(h)[:, None]
    bldg = np.zeros(w, bool)
    bldg[330:] = True
    fill = (yy >= first[None, :] + 2) & bldg[None, :]
    a = np.maximum(a, fill.astype(np.float32))
    a[(yy >= 585).ravel(), 120:] = 1.0                 # 楼左侧远处那排楼：在照片里偏灰蓝，按色差抠不干净，直接填实
    a[1000:] = 1.0
    return a.astype(np.float32), im


def _cut_ninggu():
    """北科大苏式楼（远处那栋，带老虎窗的坡顶）连同两侧的树：裁出中间一段，去掉横过天空的电线。"""
    im = _photo(NINGGU_FILE)[470:990, 990:1570]
    lum = _lum(im)
    var = np.abs(lum - gaussian_filter(lum, 2))
    sky0 = (im[..., 2] > 0.6) & (im[..., 2] - im[..., 0] > 0.08) & (var < 0.015)
    sky = _sky_field(im, sky0, 30)
    d = np.linalg.norm(im - sky, axis=2)
    a = np.clip((d - 0.05) / 0.12, 0, 1)
    # 电线是 3–5 像素宽的细线：开运算去掉，再与原遮罩取交，保留树冠的边缘
    op = cv2.morphologyEx(a, cv2.MORPH_OPEN, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (7, 7)))
    keep = cv2.dilate(op, np.ones((9, 9), np.uint8))
    a = a * np.clip(keep * 1.5, 0, 1)
    h, w = a.shape
    solid = a > 0.7
    first = np.where(solid.any(0), solid.argmax(0), h)
    yy = np.arange(h)[:, None]
    a = np.maximum(a, ((yy >= first[None, :] + 3) & (yy > 120)).astype(np.float32))
    return a.astype(np.float32), im


def _hip(a, x0, x1, ridge, eave, left=True, right=True, run=1.3):
    """坡顶两端的斜脊：把 x0–x1 之间屋脊以上、两端斜线以外的部分挖掉。照片里楼的两端常被裁掉或被树挡住，
    直接用会成为竖直切开的方盒子；按四坡顶的样子补出两端的斜坡，轮廓才像苏式楼。"""
    a = a.copy()
    h, w = a.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    hw = (eave - ridge) * run
    cut = np.zeros((h, w), bool)
    if left:
        line = eave - (xx - x0) / hw * (eave - ridge)
        cut |= (xx < x0 + hw) & (yy < line) & (yy < eave)
        cut |= xx < x0
    if right:
        line = eave - (x1 - xx) / hw * (eave - ridge)
        cut |= (xx > x1 - hw) & (yy < line) & (yy < eave)
        cut |= xx > x1
    a[cut & (yy < eave + 2)] = 0
    if left:
        a[:, :int(x0)] = 0
    if right:
        a[:, int(x1):] = 0
    # 檐口：屋檐处向外挑出一小截
    t = max(2, int((eave - ridge) * 0.08))
    e0, e1 = int(eave - t), int(eave + t)
    if left:
        a[e0:e1, max(0, int(x0) - 2 * t):int(x0) + 1] = 1
    if right:
        a[e0:e1, int(x1) - 1:min(w, int(x1) + 2 * t)] = 1
    return gaussian_filter(a, 0.6)


def _silhouette_elements():
    """抠好的轮廓：{名称: (alpha, 细节亮度, 这一块抠图对应的实际高度（单位）, 窗户列表)}。
    窗户以抠图坐标的矩形 (x0, y0, x1, y1) 给出，只点亮其中极少几扇。"""
    pa, pim = _cut_poplar()
    ua, uim = _cut_ustb()
    na, nim = _cut_ninggu()
    pl = _lum(pim)
    # 白杨：树篱以下只留树干，左右两边羽化，避免裁切处出现竖直的直边
    pop = pa[40:690, 110:840].copy()
    h, w = pop.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    trunk = _smooth(xx, 322, 338) * _smooth(418 - xx, 0, 14)
    pop *= 1 - _smooth(yy, 560, 590) * (1 - trunk)
    pop *= _smooth(xx, 0, 20) * _smooth(w - 1 - xx, 0, 20)
    tr = pa[430:690, 765:1000].copy()
    h, w = tr.shape
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    tr *= 1 - _smooth(yy, 185, 205) * (1 - _smooth(xx, 92, 104) * _smooth(132 - xx, 0, 12))
    tr *= _smooth(xx, 0, 12) * _smooth(w - 1 - xx, 0, 12)
    # 苏式楼：右端在照片里被裁掉，补出斜脊；左端的树和远楼保留
    us = _hip(ua[150:1160], 0, 1166, 66, 156, left=False, right=True, run=1.0)
    # 远处那栋：去掉左边的树（树另外排），两端补出斜脊
    ng = na[:460].copy()
    ng[:, :128] = 0
    return {
        "poplar": (pop, pl[40:690, 110:840], 25.5, []),
        "tree": (tr, pl[430:690, 765:1000], 10.0, []),
        "ustb": (us, _lum(uim)[150:1160], 15.5, [(868, 505, 965, 658), (452, 505, 475, 665)]),
        "ninggu": (ng, _lum(nim)[:460], 18.0, [(255, 210, 288, 250)]),
    }


# 需要在加长之后补斜脊的楼：(左端, 右端, 屋脊行, 屋檐行, 坡长倍数)，坐标为抠图坐标
_HIPS = {"ninggu": (128, 576, 101, 170, 1.4)}


def _hedge_profile():
    """白杨照片底部那一线树篱和远树的上沿高度（照片像素，自地面往上量），作为剪影带地面的轮廓反复使用。"""
    im = _photo(POPLAR_FILE)
    lum = _lum(im)
    dark = gaussian_filter((lum < 0.33).astype(np.float32), (3, 2)) > 0.6
    dark[:615] = False
    top = np.where(dark.any(0), dark.argmax(0), 700).astype(np.float32)
    return np.clip(700 - gaussian_filter(top, 1.5), 4, None)


def _elongate(a, d, wins, x0, x1, times):
    """把一栋楼中间 x0–x1 这一段重复若干次，楼变长（坡顶的屋脊是水平的，重复后看不出接缝）。"""
    A = np.concatenate([a[:, :x0]] + [a[:, x0:x1]] * times + [a[:, x1:]], 1)
    D = np.concatenate([d[:, :x0]] + [d[:, x0:x1]] * times + [d[:, x1:]], 1)
    shift = (x1 - x0) * (times - 1)
    W = [(wx0 + (shift if wx0 >= x1 else 0), wy0, wx1 + (shift if wx0 >= x1 else 0), wy1)
         for wx0, wy0, wx1, wy1 in wins]
    return A, D, W


def _window_light(h, w, rect, rng):
    """一扇亮着的窗：暖黄的灯光，中间是十字形的窗框，下半截挂着窗帘、略暗。"""
    x0, y0, x1, y1 = rect
    m = np.zeros((h, w), np.float32)
    x0, x1 = max(0, x0), min(w, x1)
    y0, y1 = max(0, y0), min(h, y1)
    ww, hh = x1 - x0, y1 - y0
    if ww < 2 or hh < 3:
        return m
    yy, xx = np.mgrid[0:hh, 0:ww].astype(np.float32)
    v = 0.75 + 0.25 * np.exp(-((xx / ww - 0.5) ** 2 + (yy / hh - 0.35) ** 2) / 0.12)
    v *= np.where(yy > hh * rng.uniform(0.45, 0.65), 0.7, 1.0)                 # 窗帘
    bar = max(1, int(round(ww * 0.08)))
    v[:, ww // 2 - bar // 2:ww // 2 - bar // 2 + bar] *= 0.15                   # 竖框
    v[int(hh * 0.33):int(hh * 0.33) + bar, :] *= 0.15                            # 横框
    m[y0:y1, x0:x1] = v
    return m


# 两条剪影带的规格：贴图宽高（像素）、世界宽度、离尖塔的纵深（负值为在塔后）、底边与顶边的高度、地面高度、
# 颜色（夜蓝黑的倍数）、照片细节的强度、轮廓光强度、排布的随机种子
BANDS = {
    "near": dict(w=8192, h=884, world_w=440.0, z_off=-75.0, y0=WATER_Y - 3.0, y1=WATER_Y + 44.5,
                 ground=WATER_Y + 1.5, tone=0.52, detail=0.12, rim=0.055, seed=3),
    "far": dict(w=6144, h=538, world_w=560.0, z_off=-150.0, y0=WATER_Y - 3.0, y1=WATER_Y + 46.0,
                ground=WATER_Y + 2.0, tone=0.78, detail=0.06, rim=0.035, seed=8),
}


def _band_layout(name, rng):
    """剪影带里每个轮廓的位置：(名称, 中心位置（单位，自带左端量起）, 尺寸倍数, 横向压缩, 是否镜像, 亮窗序号, 加长次数)。
    尖塔在带的正中。楼放在尖塔两侧显眼处，白杨高低错落地插在楼与楼之间，一直排满整条带。"""
    W = BANDS[name]["world_w"]
    c = W / 2
    L_ = []
    if name == "near":
        L_ += [("ninggu", c + 32, 1.0, 1.0, False, [], 2), ("ustb", c - 62, 1.0, 1.0, False, [0], 1),
               ("ustb", c + 82, 0.95, 1.0, True, [1], 1), ("ninggu", c - 142, 0.95, 1.0, True, [0], 3),
               ("ninggu", c + 150, 1.0, 1.0, False, [], 2), ("ustb", c - 200, 0.9, 1.0, True, [], 1),
               ("ninggu", c + 205, 0.9, 1.0, True, [], 2)]
        u = 3.0
        while u < W - 3:
            if rng.uniform() < 0.62:
                L_.append(("poplar", u, rng.uniform(0.78, 1.12), rng.uniform(0.36, 0.62), bool(rng.integers(2)), [], 1))
                u += rng.uniform(6, 15)
            else:
                L_.append(("tree", u, rng.uniform(0.9, 1.4), rng.uniform(0.8, 1.2), bool(rng.integers(2)), [], 1))
                u += rng.uniform(5, 11)
    else:
        L_ += [("ninggu", c - 85, 0.9, 1.0, False, [], 3), ("ninggu", c + 65, 0.85, 1.0, True, [0], 2),
               ("ustb", c - 175, 0.85, 1.0, True, [], 1), ("ninggu", c + 165, 0.9, 1.0, False, [], 3),
               ("ustb", c - 7, 0.9, 1.0, False, [], 1), ("ninggu", c - 250, 0.85, 1.0, True, [], 2),
               ("ustb", c + 245, 0.85, 1.0, False, [], 1)]
        u = 2.0
        while u < W - 2:
            if rng.uniform() < 0.45:
                L_.append(("poplar", u, rng.uniform(0.6, 0.95), rng.uniform(0.32, 0.55), bool(rng.integers(2)), [], 1))
                u += rng.uniform(4, 10)
            else:
                L_.append(("tree", u, rng.uniform(0.7, 1.2), rng.uniform(0.9, 1.4), bool(rng.integers(2)), [], 1))
                u += rng.uniform(3, 8)
    return L_


def silhouette_band(name="near"):
    """一条远景剪影带，float32 RGBA（直通 alpha），第 0 行是带的顶边。

    颜色是比天空略暗的深蓝黑，远带更浅（更接近地平线的天色）、细节更少；轮廓朝左上方（月亮所在方向）的边缘带一道
    很淡的冷灰轮廓光；楼里点亮了极少几扇暖黄的窗（数值约 1.35，过去的调色会给它一点光晕）。带的底部在水面以下
    3 单位，全部不透明，摆放时不会在水面处露出缝。推荐摆法见 silhouette_items()。"""
    B = BANDS[name]

    def make():
        rng = np.random.default_rng(B["seed"])
        E = _silhouette_elements()
        W, H = B["w"], B["h"]
        ppu = W / B["world_w"]
        g = int(round((B["y1"] - B["ground"]) * ppu))
        A = np.zeros((H, W), np.float32)
        Dt = np.zeros((H, W), np.float32)
        Wl = np.zeros((H, W), np.float32)
        layout = _band_layout(name, rng)
        # 楼先画、树后画：树挡在楼前时，楼的亮窗被树遮住
        layout.sort(key=lambda e: 0 if e[0] in ("ustb", "ninggu") else 1)
        for kind, u, sc, xs, flip, lit, times in layout:
            a, d, hu, wins = E[kind]
            shift = 0
            if times > 1:
                x0e, x1e = int(a.shape[1] * 0.4), int(a.shape[1] * 0.62)
                a, d, wins = _elongate(a, d, wins, x0e, x1e, times)
                shift = (x1e - x0e) * (times - 1)
            if kind in _HIPS:
                hx0, hx1, hr, he, run = _HIPS[kind]
                a = _hip(a, hx0, hx1 + shift, hr, he, run=run)
            h_px = hu * sc * ppu
            k = h_px / a.shape[0]
            nw, nh = max(2, int(a.shape[1] * k * xs)), max(2, int(round(h_px)))
            interp = cv2.INTER_AREA if k < 1 else cv2.INTER_LINEAR
            a2 = cv2.resize(a, (nw, nh), interpolation=interp)
            d2 = cv2.resize(d, (nw, nh), interpolation=interp)
            d2 = (d2 - gaussian_filter(d2, max(1.5, nh / 80))) * _ramp(a2, 0.9, 1.0)   # 只取实心处的细小明暗
            light = np.zeros_like(a2)
            for i in lit:
                x0r, y0r, x1r, y1r = wins[i]
                r2 = (int(x0r * k * xs), int(y0r * k), max(int(x1r * k * xs), int(x0r * k * xs) + 2),
                      max(int(y1r * k), int(y0r * k) + 3))
                light = np.maximum(light, _window_light(nh, nw, r2, rng))
            if flip:
                a2, d2, light = a2[:, ::-1], d2[:, ::-1], light[:, ::-1]
            x0 = int(u * ppu - nw / 2)
            y0 = g - nh + (int(0.8 * ppu) if kind in ("poplar", "tree") else 0)    # 树干根部埋进地面一截
            xa, xb = max(0, x0), min(W, x0 + nw)
            ya, yb = max(0, y0), min(H, y0 + nh)
            if xb <= xa or yb <= ya:
                continue
            sa = a2[ya - y0:yb - y0, xa - x0:xb - x0]
            Wl[ya:yb, xa:xb] = Wl[ya:yb, xa:xb] * (1 - sa) + light[ya - y0:yb - y0, xa - x0:xb - x0] * sa
            Dt[ya:yb, xa:xb] = Dt[ya:yb, xa:xb] * (1 - sa) + d2[ya - y0:yb - y0, xa - x0:xb - x0] * sa
            A[ya:yb, xa:xb] = 1 - (1 - A[ya:yb, xa:xb]) * (1 - sa)
        A[g - 2:] = 1.0
        # 地面一带：低矮的树丛连成一线，接住各个轮廓的底部
        prof = _hedge_profile()                                   # 照片像素；照片里树高 650 像素约合 25.5 单位
        k_h = ppu * 25.5 / 650
        hedge = np.zeros(W, np.float32)
        x = 0
        while x < W:                                             # 照片的树篱轮廓随机截段、镜像、伸缩后首尾接起来
            seg = prof[rng.integers(0, 300):][:rng.integers(400, 700)]
            if rng.integers(2):
                seg = seg[::-1]
            sx = rng.uniform(0.8, 1.3) * k_h
            n = max(2, int(len(seg) * sx))
            seg = np.interp(np.linspace(0, len(seg) - 1, n), np.arange(len(seg)), seg) * k_h * rng.uniform(0.8, 1.15)
            m = min(n, W - x)
            hedge[x:x + m] = seg[:m]
            x += m
        hedge = gaussian_filter(hedge, 1.0) + 0.4 * ppu
        yy = np.arange(H, dtype=np.float32)
        A = np.maximum(A, _smooth(yy[:, None] - (g - hedge[None, :]), -1.5, 1.5))
        # 颜色：深蓝黑，照片里的明暗作为极淡的细节保留
        col = (NIGHT * B["tone"])[None, None] * (1 + B["detail"] * np.clip(Dt * 4, -1, 1))[..., None]
        # 轮廓光：朝左上方（月亮）的边缘，只加在成片的实心处（细枝本来就半透明，不再提亮）
        k = max(2, int(ppu * 0.12))
        sh = np.zeros_like(A)
        sh[k:, k:] = A[:-k, :-k]
        rim = np.clip(A - sh, 0, 1) * _ramp(gaussian_filter(A, ppu * 0.25), 0.45, 0.8)
        rim = gaussian_filter(rim, 0.8)
        col += rim[..., None] * np.array([0.11, 0.125, 0.15], np.float32) * (B["rim"] / 0.055)
        # 远带近地面处有一层薄雾，往下略微变浅
        if name == "far":
            mist = _ramp(yy, g - 5 * ppu, g)[:, None, None]
            col = col * (1 - 0.25 * mist) + (NIGHT * 1.15)[None, None] * 0.25 * mist
        # 带的左右两端在最后 4% 的长度里淡出，镜头偏得很开时不会看到一刀切齐的端头
        xx = np.arange(W, dtype=np.float32)
        A = A * np.minimum(_smooth(xx, 0, W * 0.04), _smooth(W - 1 - xx, 0, W * 0.04))[None, :]
        # 亮窗
        warm = np.array([1.0, 0.68, 0.34], np.float32) * 1.2
        col = col * (1 - Wl[..., None]) + warm * Wl[..., None]
        return np.dstack([col, A]).astype(np.float32)
    return _cached("band_" + name, make, B, "b6")


def silhouette_items(group="past"):
    """两条远景剪影带，竖直放在尖塔后方、正对 +z：近带在塔后 75 单位（宽 360、高 47.5），远带在塔后 150 单位
    （宽 470、高 49），两带的中心都对准尖塔，底边在水面以下 3 单位。远近两带之间的距离让镜头横移和升降时有视差。"""
    from engine import Plane
    items = []
    for name in ("far", "near"):
        B = BANDS[name]
        tex = _tex("band_" + name, lambda n=name: silhouette_band(n))
        items.append(Plane(tex, center=(SPIRE[0], (B["y0"] + B["y1"]) / 2, SPIRE[2] + B["z_off"]),
                           size=(B["world_w"], B["y1"] - B["y0"]), group=group))
    return items


def band_card(name):
    """供水面材质反射用的剪影带描述：(纹理, (中心 x, 中心 y, 宽, 高), z)。"""
    B = BANDS[name]
    tex = _tex("band_" + name, lambda: silhouette_band(name))
    return tex, (float(SPIRE[0]), (B["y0"] + B["y1"]) / 2, B["world_w"], B["y1"] - B["y0"]), float(SPIRE[2] + B["z_off"])


# ---------------------------------------------------------------------------
# 三、水池水面
# ---------------------------------------------------------------------------
# 细波纹取自 Brofjorden 那张 CC0 照片的远处水面：照片里平静的水面上有一道道横向拉长的细纹。
# 先做带通滤波留下细纹，再按透视把竖向压扁的纹理拉回去，最后做成四边无缝的贴图。

WATER_TILE = 16.0                 # 细纹贴图一块对应的世界边长（单位）


def water_ripple():
    """水面细纹的高度图，(2048, 2048) float32，0–1，四边无缝，可平铺。一块对应世界里 WATER_TILE=16 单位见方。"""
    def make():
        im = _photo(F_FILE)
        lum = _lum(im)[1240:1580, 800:3300]
        lum = cv2.medianBlur((lum * 255).astype(np.uint8), 3).astype(np.float32) / 255
        bp = cv2.GaussianBlur(lum, (0, 0), 1.2) - cv2.GaussianBlur(lum, (0, 0), 30)
        # 照片里还有岸边树木、灯光在水里的竖向倒影，它们不是波纹：沿竖向平滑后减掉，只留横向的细纹
        bp = bp - gaussian_filter(bp, (14, 1.0))
        # 远处的行细纹更密、更弱：逐行按局部标准差归一
        sd = np.sqrt(gaussian_filter(bp ** 2, (12, 80)))
        bp = bp / np.maximum(sd, 1e-4)
        # 透视把水面竖向压扁了五六倍：拉回去
        tile = cv2.resize(bp, (2048, 2048), interpolation=cv2.INTER_CUBIC)
        tile = gaussian_filter(tile, (2.0, 3.5))
        # 四边无缝：先在横向、再在竖向与错开半块的自身按窗函数混合（两次一维混合，接缝处权重恰好为零），
        # 混合处按方差补偿，纹理强度不减
        n = 2048
        w1 = (np.sin(np.linspace(0, np.pi, n, endpoint=False) + np.pi / (2 * n)) ** 2).astype(np.float32)
        wx = w1[None, :]
        out = (tile * wx + np.roll(tile, n // 2, 1) * (1 - wx)) / np.sqrt(wx ** 2 + (1 - wx) ** 2)
        wy = w1[:, None]
        out = (out * wy + np.roll(out, n // 2, 0) * (1 - wy)) / np.sqrt(wy ** 2 + (1 - wy) ** 2)
        out = out / (out.std() + 1e-6)
        return np.clip(0.5 + out * 0.16, 0, 1)
    return _cached("ripple", make, "r3")


def water_texture(streaks=True, size=2048, seed=5):
    """水面贴图（静态），float32 RGBA，(size, size, 4)：深色水面、细碎的波纹；streaks=True 时烘焙进月光和
    远处灯光拉出的竖向倒影条纹，条纹沿贴图的竖直方向，适合镜头从贴图下沿一侧斜看或俯视时直接贴用。
    在引擎里一般用 pool_items()：它用 bd_water 材质实时算倒影，条纹会随镜头位置和波纹自然变化。"""
    def make():
        rng = np.random.default_rng(seed)
        h = cv2.resize(water_ripple(), (size, size), interpolation=cv2.INTER_AREA)
        hp = h - 0.5
        gy, gx = np.gradient(h)
        shade = np.clip(0.5 + (gx * 0.6 - gy) * 60, 0, 1)
        yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / size
        col = (NIGHT * 0.55)[None, None] * (0.85 + 0.3 * shade)[..., None]
        # 远处（贴图上方）反射更多天光，略亮
        col *= (1.0 + 0.5 * (1 - yy))[..., None]
        if streaks:
            def streak(x0, width, top, bot, color, amp):
                # 竖向条纹由一个个横向的小亮片组成：波纹朝镜头倾斜的地方才反射到光源
                band = np.exp(-((xx - x0) / width) ** 2 * (1 + 3 * yy))
                band *= _smooth(yy, top, top + 0.06) * _smooth(bot - yy, 0, 0.1)
                spark = np.clip((shade - 0.56) * 6, 0, 1) ** 1.5
                spark = gaussian_filter(spark, (0.6, 2.5))
                return band[..., None] * (0.25 + 1.6 * spark)[..., None] * np.asarray(color, np.float32) * amp
            col += streak(0.42, 0.03, 0.02, 0.95, (1.0, 0.95, 0.82), 0.3)          # 月光
            for x0 in rng.uniform(0.6, 0.95, 3):                                    # 远处的几盏暖灯
                col += streak(x0, 0.005, 0.0, rng.uniform(0.25, 0.5), (1.0, 0.68, 0.34), 0.5)
        return np.dstack([col, np.ones((size, size), np.float32)]).astype(np.float32)
    return _cached("water_tex", make, streaks, size, seed, "w3")


# 水面材质 bd_water：水面本身很暗，画面里看到的主要是倒影。每个像素先由细纹贴图（两层，朝不同方向缓慢流动）
# 和一层大尺度的起伏算出水面法线，把视线按法线反射，再用反射方向去取：夜空全景（按方向取，天空在无穷远）、
# 若干张竖直的"倒影卡片"（剪影带、尖塔，按射线与卡片平面的交点取），以及月亮（反射方向落在月面上时是碎光，
# 落在月晕里时是一道柔和的光柱）。波纹在动，反射方向跟着变，倒影就轻微摇晃，月光和窗灯在水面上拉成竖向的
# 碎光条纹，条纹总是朝向镜头，这是真实水面反射的几何结果，不需要另外画。
WATER_GLSL = """
uniform sampler2D bw_sky;
uniform sampler2D bw_ripple;
uniform sampler2D bw_card0; uniform vec4 bw_card0_r; uniform float bw_card0_z;
uniform sampler2D bw_card1; uniform vec4 bw_card1_r; uniform float bw_card1_z;
uniform sampler2D bw_card2; uniform vec4 bw_card2_r; uniform float bw_card2_z;
uniform sampler2D bw_card3; uniform vec4 bw_card3_r; uniform float bw_card3_z;
uniform vec3 bw_moon;          // 月亮方向（单位向量）
uniform float bw_moon_r;       // 月面角半径（弧度）
uniform vec3 bw_moon_col;
uniform float bw_tile;         // 细纹贴图一块的世界边长
uniform float bw_ripple_k;     // 细纹的法线强度
uniform float bw_swell_k;      // 大尺度起伏的法线强度
uniform float bw_flow;         // 细纹流动的速度（单位/秒）
uniform float bw_refl;         // 倒影强度
uniform float bw_glitter;      // 月光碎光的强度
uniform float bw_alpha;        // 透过水面看到水下立面时，水面最小的不透明度
uniform vec4 bw_see;           // 水下立面：(中心 x, 立面所在 z, 半宽, 透明随深度消失的特征深度)；半宽为 0 时水面完全不透明
uniform float bw_surf;         // 水面高度

vec3 bw_skycol(vec3 R) {
    float yaw = degrees(atan(R.x, -R.z));
    float el = degrees(asin(clamp(R.y, -1.0, 1.0)));
    vec2 uv = vec2((yaw + 135.0) / 270.0, clamp((80.0 - el) / 90.0, 0.0, 1.0));
    return textureLod(bw_sky, uv, 1.0).rgb;
}

vec4 bw_card(sampler2D tex, vec4 r, float cz, vec3 P, vec3 R) {
    if (r.z <= 0.0 || R.z > -1e-4) return vec4(0.0);
    float s = (cz - P.z) / R.z;
    if (s <= 0.0) return vec4(0.0);
    vec3 H = P + s * R;
    vec2 uv = vec2((H.x - r.x) / r.z + 0.5, 0.5 - (H.y - r.y) / r.w);
    if (uv.x < 0.0 || uv.x > 1.0 || uv.y < 0.0 || uv.y > 1.0) return vec4(0.0);
    return textureLod(tex, uv, 0.7);
}

float bw_h(vec2 uv) { return texture(bw_ripple, uv).r; }

vec4 material(vec4 base) {
    vec3 P = v_wpos;
    vec2 q = P.xz;
    float t = u_time * bw_flow;
    // 两层细纹：尺度不同、朝不同方向流动；差分步长取当前像素的贴图跨度，远处细纹自动变平，水面像镜子
    vec2 uv1 = (q + vec2(t, 0.35 * t)) / bw_tile;
    vec2 uv2 = (q * 1.73 + vec2(3.1 - 0.55 * t, 7.7 + 0.8 * t)) / bw_tile;
    float e1 = clamp(length(fwidth(uv1)) * 0.5, 1.0 / 2048.0, 0.02);
    float e2 = clamp(length(fwidth(uv2)) * 0.5, 1.0 / 2048.0, 0.02);
    vec2 g1 = vec2(bw_h(uv1 + vec2(e1, 0)) - bw_h(uv1 - vec2(e1, 0)), bw_h(uv1 + vec2(0, e1)) - bw_h(uv1 - vec2(0, e1))) / (2.0 * e1);
    vec2 g2 = vec2(bw_h(uv2 + vec2(e2, 0)) - bw_h(uv2 - vec2(e2, 0)), bw_h(uv2 + vec2(0, e2)) - bw_h(uv2 - vec2(0, e2))) / (2.0 * e2);
    vec2 g = (g1 / bw_tile + g2 * 1.73 / bw_tile) * bw_ripple_k;
    // 大尺度的缓慢起伏，让倒影整体轻轻摇晃
    float sw = 0.9;
    vec2 sp = q / 7.0 + vec2(0.13 * u_time, -0.09 * u_time);
    vec2 gs = vec2(gnoise(sp + vec2(0.05, 0.0), 41) - gnoise(sp - vec2(0.05, 0.0), 41),
                   gnoise(sp + vec2(0.0, 0.05), 41) - gnoise(sp - vec2(0.0, 0.05), 41)) / 0.1;
    g += gs * bw_swell_k;
    vec3 N = normalize(vec3(-g.x, 1.0, -g.y));
    vec3 V = normalize(P - u_eye);
    vec3 R = reflect(V, N);
    R.y = max(R.y, 0.004);
    R = normalize(R);
    vec3 col = bw_skycol(R);
    vec4 c;
    c = bw_card(bw_card0, bw_card0_r, bw_card0_z, P, R); col = col * (1.0 - c.a) + c.rgb;
    c = bw_card(bw_card1, bw_card1_r, bw_card1_z, P, R); col = col * (1.0 - c.a) + c.rgb;
    c = bw_card(bw_card2, bw_card2_r, bw_card2_z, P, R); col = col * (1.0 - c.a) + c.rgb;
    c = bw_card(bw_card3, bw_card3_r, bw_card3_z, P, R); col = col * (1.0 - c.a) + c.rgb;
    // 月亮：落在月面上是碎光，落在月晕里是柔和的光柱
    float cm = dot(R, bw_moon);
    float ang = acos(clamp(cm, -1.0, 1.0));
    float disc = 1.0 - smoothstep(bw_moon_r * 0.7, bw_moon_r * 1.25, ang);
    float halo = exp(-ang * ang / (2.0 * 0.05 * 0.05)) * 0.22 + exp(-ang / 0.11) * 0.05 + exp(-ang / 0.4) * 0.05;
    col += bw_moon_col * (disc * 1.6 + halo) * bw_glitter;
    // 掠射时反射更强（菲涅耳）；正上方往下看时更多看到水体本身的暗色
    float ct = clamp(dot(-V, N), 0.0, 1.0);
    float k = bw_refl * (0.5 + 0.5 * pow(1.0 - ct, 3.0));
    vec3 outc = base.rgb * (1.0 - k) + col * k;
    // 透过水面看水下的立面：视线（忽略折射）在水下碰到立面的地方，水面略微透明，越深越不透明；
    // 掠射时反射占了大半，几乎看不进水里
    float a = 1.0;
    if (bw_see.z > 0.0 && V.z < -1e-4 && P.z > bw_see.y) {
        float s = (bw_see.y - P.z) / V.z;
        vec3 H = P + s * V;
        float dep = bw_surf - H.y;
        if (abs(H.x - bw_see.x) < bw_see.z && dep > 0.0) {
            float seen = exp(-dep / bw_see.w) * (1.0 - k * 0.6);
            a = mix(1.0, bw_alpha, seen * smoothstep(0.0, 1.5, bw_see.z - abs(H.x - bw_see.x)));
        }
    }
    return vec4(outc * a, a);
}
"""


def _register_materials():
    from engine import register_material
    register_material("bd_water", WATER_GLSL, {
        "bw_moon": tuple(dir_from(*MOON_DIR)), "bw_moon_r": math.radians(1.1), "bw_moon_col": (1.0, 0.95, 0.84),
        "bw_tile": WATER_TILE, "bw_ripple_k": 0.010, "bw_swell_k": 0.010, "bw_flow": 0.18,
        "bw_refl": 0.9, "bw_glitter": 1.0, "bw_alpha": 1.0,
        "bw_see": (0.0, 0.0, 0.0, 1.0), "bw_surf": WATER_Y,
        "bw_card0_r": (0, 0, 0, 0), "bw_card1_r": (0, 0, 0, 0), "bw_card2_r": (0, 0, 0, 0), "bw_card3_r": (0, 0, 0, 0),
        "bw_card0_z": 0.0, "bw_card1_z": 0.0, "bw_card2_z": 0.0, "bw_card3_z": 0.0,
    })


def _depth(item, cam):
    """引擎排序用的深度（元素上离镜头最近的点沿视线方向的距离），用来给大平面算排序偏移。"""
    from engine.renderer import Renderer
    return Renderer._sort_depth(item, cam.eye, cam.basis()[2])


POOL_Z0 = WALL[2] - 3.0                     # 水池近岸（紧贴墙后）
POOL_Z1 = SPIRE[2] + BANDS["near"]["z_off"] - 0.5   # 远岸：近剪影带的底部
POOL_HALF_W = 260.0


FACADE_HALF_W = 31.0               # 被淹没的展览馆立面的半宽（用于水面透视和排序）
FACADE_TOP = SPIRE[1] + 54.0       # 立面最高处（塔尖五角星顶点）


def spire_card(tex, width=2 * FACADE_HALF_W, height=None, bottom=None):
    """把尖塔（展览馆立面）贴图写成水面倒影卡片：立面平面在 z = SPIRE.z、正对 +z，建筑坐标原点在
    SPIRE + (0, BUILDING_DY, 0)。tex 为立面贴图（RGBA，直通 alpha，第 0 行是顶部），覆盖从 bottom 到
    bottom + height 的高度（缺省为整座建筑：bottom = SPIRE.y - 26，height = 80）。只有水面以上的部分会被反射到。"""
    if bottom is None:
        bottom = SPIRE[1] - 26.0
    if height is None:
        height = 80.0
    return tex, (float(SPIRE[0]), float(bottom + height / 2), float(width), float(height)), float(SPIRE[2])


def pool_items(cam, cards=None, moon_dir=None, moon_size=2.2, see_alpha=0.82, front_stack=None, group="past",
               **uniforms):
    """水池水面：y = WATER_Y 的水平面，从墙后 3 单位一直铺到近剪影带脚下（约 183 单位长、400 宽），
    材质 bd_water 实时算出天空、剪影、尖塔和月亮的倒影。只在镜头位于水面以上时返回元素。
    水面在立面所在的 z = SPIRE.z 处分成两块：立面后方的一块排在立面之前画，立面前方的一块排在立面之后画。

    cards：额外的倒影卡片，最多两张，按由远及近的顺序给出。每张卡片描述一块正对 +z 的竖直平面，格式为
    (纹理, (中心 x, 中心 y, 宽, 高), z)，纹理是 engine.Tex 或 RGBA 数组（直通 alpha，第 0 行是顶部）。
    尖塔用 spire_card(立面贴图) 生成即可（立面在 z = SPIRE.z，建筑坐标原点在 SPIRE + (0, -26, 0)，
    露出水面的部分从 WATER_Y 到 SPIRE.y + 54）。两条剪影带自动作为最远的两张卡片。

    see_alpha：透过立面前方的水面看水下立面时，水面最小的不透明度（缺省 0.82，即刚没入水面的横幅约透出两成，
    越深越看不见；设为 1 则完全不透明）。要让水下的横幅透出来，横幅和立面必须先于前方水面画出：
    把立面、横幅等水下可见的元素和返回的前方水面放进同一个 stack（参数 front_stack），并按
    "立面、横幅……、前方水面"的顺序加入画面；不给 front_stack 时，前方水面的排序深度恰好排在立面代理之前。

    uniforms 可以覆盖材质参数，例如 bw_ripple_k（细纹强度，缺省 0.010）、bw_swell_k（起伏，0.010）、
    bw_flow（流速，0.18）、bw_refl（倒影强度，0.9）、bw_glitter（月光碎光强度，1.0）。"""
    from engine import Plane
    if cam.eye[1] <= WATER_Y + 0.02:
        return []
    yaw, el = MOON_DIR if moon_dir is None else moon_dir
    sky = _tex("pano_wrap", lambda: sky_panorama(), repeat=True)
    rip = _tex("ripple", lambda: water_ripple(), repeat=True)
    allc = [band_card("far"), band_card("near")] + list(cards or [])[:2]
    uni = {"bw_sky": sky, "bw_ripple": rip, "bw_moon": tuple(dir_from(yaw, el)),
           "bw_moon_r": math.radians(moon_size / 2)}
    for i in range(4):
        if i < len(allc):
            tex, r, z = allc[i]
            uni[f"bw_card{i}"] = tex
            uni[f"bw_card{i}_r"] = tuple(map(float, r))
            uni[f"bw_card{i}_z"] = float(z)
        else:
            uni[f"bw_card{i}"] = rip
            uni[f"bw_card{i}_r"] = (0.0, 0.0, 0.0, 0.0)
    uni.update(uniforms)
    body = tuple(NIGHT * 0.6)
    zs = float(SPIRE[2])
    back = Plane(None, center=(SPIRE[0], WATER_Y, (zs + POOL_Z1) / 2), size=(2 * POOL_HALF_W, zs - POOL_Z1),
                 rot=(0.0, -90.0, 0.0), color=body, group=group, material="bd_water", uniforms=uni)
    fu = dict(uni, bw_alpha=float(see_alpha), bw_see=(float(SPIRE[0]), zs, FACADE_HALF_W, 2.2))
    front = Plane(None, center=(SPIRE[0], WATER_Y, (zs + POOL_Z0) / 2), size=(2 * POOL_HALF_W, POOL_Z0 - zs),
                  rot=(0.0, -90.0, 0.0), color=body, group=group, material="bd_water", uniforms=fu, stack=front_stack)
    near = Plane(None, center=(SPIRE[0], (BANDS["near"]["y0"] + BANDS["near"]["y1"]) / 2, SPIRE[2] + BANDS["near"]["z_off"]),
                 size=(BANDS["near"]["world_w"], 50))
    facade = Plane(None, center=(SPIRE[0], (SEABED_Y + FACADE_TOP) / 2, zs), size=(2 * FACADE_HALF_W, FACADE_TOP - SEABED_Y))
    back.bias = _depth(near, cam) - _depth(back, cam) - 0.5
    front.bias = _depth(facade, cam) - _depth(front, cam) - 0.05
    return [back, front]


# ---------------------------------------------------------------------------
# 四、院子地面
# ---------------------------------------------------------------------------
# 旧砖铺地（Poly Haven "Brick floor"，Rob Tuytel，CC0，人字纹的旧砖，砖缝里有青苔）与夯土（Poly Haven
# "Dirt"，Charlotte Baglioni，CC0）按一张大尺度的噪声混合：大部分是被踩实的土，旧砖从土下断续露出来。

BRICK_FILE = "Brick_floor_diff_8k_Rob_Tuytel_via_Poly_Haven_.png"
DIRT_FILE = "Dirt_diff_8k_Charlotte_Baglioni_via_Poly_Haven_.png"
RIVERBED_FILE = "Dry_riverbed_rock_diff_16k_Amal_Kumar_via_Poly_Haven_.png"
YARD_TILE = 12.0                  # 地面贴图一块对应的世界边长（单位）
YARD_DEPTH = 40.0                 # 院子从墙脚向镜头一侧延伸的深度


def _tileable_mix(a, b, w):
    return a * (1 - w[..., None]) + b * w[..., None]


def _wrap_noise(size, cells, rng, smooth=0.0):
    """四边无缝的平滑噪声：在 cells×cells 的格子上取随机数，按环面周期插值放大到 size。"""
    n = rng.normal(0, 1, (cells, cells)).astype(np.float32)
    if smooth:
        n = gaussian_filter(n, smooth, mode="wrap")
    big = cv2.resize(np.tile(n, (3, 3)), (size * 3, size * 3), interpolation=cv2.INTER_CUBIC)
    return big[size:2 * size, size:2 * size]


def _poly(name, size):
    """读入 Poly Haven 贴图并缩放到 size（这些贴图本身四边无缝）。"""
    im = Image.open(IMG / name).convert("RGB")
    return np.asarray(im.resize((size, size), Image.LANCZOS), np.float32) / 255


def yard_texture(size=4096):
    """院子地面的颜色贴图，float32 RGBA，(size, size, 4)，四边无缝，一块对应 YARD_TILE=12 单位见方。

    已按夜色调好：夯土和旧砖去掉大半饱和度、压暗到约 0.05–0.08，偏冷的蓝灰；砖缝更暗，土面有细小的颗粒。
    亮度与样张 B 墙前的地面相当，被铁水照亮的暖光由材质 bd_ground 的 bg_warm 参数另加。"""
    def make():
        rng = np.random.default_rng(12)
        # 原贴图每块约 2.5 米见方：在 12 单位里重复 5×5 次（砖），土重复 4×4 次
        brick = _poly(BRICK_FILE, size // 5 + 1)[: size // 5, : size // 5]
        brick = np.tile(brick, (5, 5, 1))
        brick = cv2.resize(brick, (size, size), interpolation=cv2.INTER_AREA)
        dirt = _poly(DIRT_FILE, size // 4)
        dirt = np.tile(dirt, (4, 4, 1))
        # 混合遮罩：四边无缝的大尺度噪声（在环面上取样），土占大约六成
        u = np.linspace(0, 2 * np.pi, size, endpoint=False)
        U, V = np.meshgrid(u, u)
        n = np.zeros((size, size), np.float32)
        for k, (f, a) in enumerate([(2, 1.0), (3, 0.6), (5, 0.4), (9, 0.22), (17, 0.12)]):
            ph = rng.uniform(0, 2 * np.pi, 4)
            n += a * (np.sin(f * U + ph[0]) * np.cos(f * V + ph[1]) + np.sin(f * (U + V) * 0.7 + ph[2]) * 0.5 *
                      np.cos(f * (U - V) * 0.7 + ph[3]))
        n = (n - n.mean()) / n.std()
        grit = _wrap_noise(size, size // 8, rng)
        m = _smooth(n + 0.35 * grit, -0.1, 0.8)                       # 1 为土
        col = _tileable_mix(brick, dirt, m)
        lum = col @ LUMA
        # 夜色：去饱和、压暗、偏冷
        col = lum[..., None] * 0.55 + col * 0.45
        col = col * (1 + 0.35 * (1 - m))[..., None]                                   # 露出的砖面略亮于土
        col = col * (np.array([0.30, 0.34, 0.44], np.float32) * 0.85)[None, None]
        # 土面上零星的深色湿斑
        wet = _wrap_noise(size, size // 16, rng, smooth=2.0)
        wet = gaussian_filter(_smooth(wet / (wet.std() + 1e-6), 0.4, 2.2), 6, mode="wrap")
        col *= (1 - 0.12 * np.clip(wet, 0, 1) * m)[..., None]
        return np.dstack([col, np.ones((size, size), np.float32)]).astype(np.float32)
    return _cached("yard", make, size, "y3")


GROUND_GLSL = """
uniform float bg_tile;          // 贴图一块的世界边长
uniform vec3 bg_light;          // 整体乘的光色（缺省 1，即贴图里已调好的夜色）
uniform vec4 bg_warm;           // 暖光的位置 (x, y, z) 与半径 w，例如墙上铁水投到地上的光
uniform vec3 bg_warm_col;       // 暖光颜色与强度（缺省 0，不加）
uniform float bg_wall_z;        // 墙面所在的 z：墙脚处地面更暗（墙挡住了一半天光）
vec4 material(vec4 base) {
    vec2 p = v_wpos.xz;
    // 大尺度的明暗起伏，打散贴图的重复
    float fw = length(fwidth(p / 9.0));
    float big = fbm(p / 9.0, 4, fw, 7);
    float mid = fbm(p / 2.3 + 11.0, 3, length(fwidth(p / 2.3)), 9);
    vec3 col = base.rgb * (0.72 + 0.5 * big) * (0.9 + 0.2 * mid) * bg_light;
    float ao = mix(0.55, 1.0, smoothstep(0.0, 2.5, v_wpos.z - bg_wall_z));
    col *= ao;
    float d = length(v_wpos - bg_warm.xyz);
    col += base.rgb * bg_warm_col * exp(-d * d / max(bg_warm.w * bg_warm.w, 1e-4)) * 6.0;
    return vec4(col, base.a);
}
"""


def yard_items(cam, warm=None, group="past"):
    """院子地面：墙前的一块水平平面，y = 墙脚高度，从墙面向镜头一侧铺 40 单位，左右比墙各宽出 40 单位
    （宽 118、深 40）。贴图平铺，每 12 单位重复一次，材质 bd_ground 再叠一层世界坐标里的大尺度明暗，看不出重复。
    warm=((x, y, z), 半径, (r, g, b)) 可以加一团暖光，例如墙上铁水在地上的反光。

    排序：地面铺在镜头下方，按当前镜头给它一个偏移，使它恰好排在墙之前，墙前的手、花和字都画在地面之上。"""
    from engine import Plane
    x0 = WALL[0] - 7.0
    wall_w = 38.0
    tex = _tex("yard", lambda: yard_texture(), repeat=True)
    w_x, d_z = wall_w + 80.0, YARD_DEPTH
    uni = {"bg_tile": YARD_TILE, "bg_light": (1.0, 1.0, 1.0), "bg_wall_z": float(WALL[2]),
           "bg_warm": (0.0, 0.0, 0.0, 1.0), "bg_warm_col": (0.0, 0.0, 0.0)}
    if warm is not None:
        (wx, wy, wz), rad, wc = warm
        uni["bg_warm"] = (float(wx), float(wy), float(wz), float(rad))
        uni["bg_warm_col"] = tuple(map(float, wc))
    ground = Plane(tex, center=(x0 + wall_w / 2, GROUND_Y, WALL[2] + d_z / 2), size=(w_x, d_z), rot=(0.0, -90.0, 0.0),
                   uv=(0.0, 0.0, w_x / YARD_TILE, d_z / YARD_TILE), group=group, material="bd_ground", uniforms=uni)
    wall = Plane(None, center=(x0 + wall_w / 2, WALL[1] + 0.5, WALL[2]), size=(wall_w, 15.0))
    ground.bias = _depth(wall, cam) - _depth(ground, cam) + 0.2
    return [ground]


def _register_ground():
    from engine import register_material
    register_material("bd_ground", GROUND_GLSL, {"bg_tile": YARD_TILE, "bg_light": (1.0, 1.0, 1.0),
                                                 "bg_warm": (0.0, 0.0, 0.0, 1.0), "bg_warm_col": (0.0, 0.0, 0.0),
                                                 "bg_wall_z": float(WALL[2])})


# ---------------------------------------------------------------------------
# 五、水下
# ---------------------------------------------------------------------------
# 水下的一切都按"视线方向和距离"上色：同一个雾色函数 uw_fog() 被背景、水底、沟壁和水面下视共用，
# 远处的东西都融进同一片深蓝绿里，几层之间没有接缝。往上看最亮（月光从水面透下来），平视是深蓝绿，往下看
# 接近黑色；镜头离水面越深，整体越暗。

UW_COMMON = """
uniform vec3 uw_top;            // 仰望水面方向的水色
uniform vec3 uw_mid;            // 平视方向的水色
uniform vec3 uw_deep;           // 俯视方向的水色
uniform float uw_surf;          // 水面高度
uniform float uw_vis;           // 能见距离（单位）：这么远处的东西约有六成融进水色
uniform float uw_atten;         // 水越深越暗的特征深度（单位）
uniform vec3 uw_light;          // 水下的月光（已带水的颜色），照在水底和沟壁上
uniform vec3 uw_moon;           // 月亮方向（单位向量，水面以上）

vec3 uw_fog(vec3 d) {
    vec3 c = mix(uw_deep, uw_mid, smoothstep(-0.75, 0.05, d.y));
    c = mix(c, uw_top, smoothstep(0.05, 0.85, d.y));
    float depth = max(uw_surf - u_eye.y, 0.0);
    return c * exp(-depth / (uw_atten * 2.5));
}

float uw_fogk = 1.0;            // 雾的距离倍数（沟壁取得小一些，近处的岩层看得清）
vec3 uw_apply_fog(vec3 col) {
    vec3 d = v_wpos - u_eye;
    float dist = length(d);
    float f = 1.0 - exp(-dist * uw_fogk / uw_vis);
    return mix(col, uw_fog(d / max(dist, 1e-4)), f);
}

// 焦散：水面的波纹把月光聚成一张缓慢游动的亮网。两层脊状噪声相乘，网线细而亮，网眼里暗
float uw_caustic(vec2 p, float t) {
    vec2 q = p + vec2(0.35 * sin(0.4 * t + p.y * 0.7), 0.35 * cos(0.33 * t + p.x * 0.6));
    float a = 1.0 - abs(gnoise(q * 1.1 + vec2(0.21 * t, 0.13 * t), 51) * 1.6);
    float b = 1.0 - abs(gnoise(q * 1.7 - vec2(0.17 * t, -0.19 * t), 52) * 1.6);
    return pow(clamp(a, 0.0, 1.0), 7.0) * 0.7 + pow(clamp(a * b, 0.0, 1.0), 5.0) * 0.9;
}
"""

# 背景：一块始终正对镜头、放在镜头前方远处的平面，颜色只取决于视线方向，所以镜头怎样转都连续
UW_FOG_GLSL = UW_COMMON + """
vec4 material(vec4 base) {
    vec3 d = normalize(v_wpos - u_eye);
    vec3 c = uw_fog(d);
    // 极淡的明暗起伏，水不是一块平涂的颜色
    float n = vnoise(d.xz / max(abs(d.y) + 0.35, 0.2) * 3.0 + vec2(0.03 * u_time, 0.0), 61);
    c *= 0.9 + 0.2 * n;
    return vec4(c, 1.0);
}
"""

# 水面下视：水下仰望时，水面在约 48.6° 的圆锥（斯涅尔窗）里透出天空，窗外是全反射，映出下面的深水。
# 窗口边缘最亮、略带彩边；波纹让整个窗口轻轻晃动；月亮在窗里是一团晃动的亮光。
UW_SURFACE_GLSL = UW_COMMON + """
uniform sampler2D bw_sky;
uniform float us_bright;        // 窗里天光的增益（天光透进水里后看上去比天空本身亮）
uniform float us_moon_k;        // 窗里月亮的亮度
vec3 us_skycol(vec3 R) {
    float yaw = degrees(atan(R.x, -R.z));
    float el = degrees(asin(clamp(R.y, -1.0, 1.0)));
    vec2 uv = vec2((yaw + 135.0) / 270.0, clamp((80.0 - el) / 90.0, 0.0, 1.0));
    return textureLod(bw_sky, uv, 2.0).rgb;
}
vec4 material(vec4 base) {
    vec3 V = normalize(v_wpos - u_eye);
    if (V.y <= 0.0) return vec4(uw_apply_fog(uw_deep), 1.0);
    vec2 q = v_wpos.xz;
    float t = u_time;
    vec2 g = vec2(gnoise(q * 0.45 + vec2(0.3 * t, 0.1 * t), 71) - gnoise(q * 0.45 + vec2(0.3 * t, 0.1 * t) + vec2(0.07, 0.0), 71),
                  gnoise(q * 0.45 + vec2(0.3 * t, 0.1 * t), 72) - gnoise(q * 0.45 + vec2(0.3 * t, 0.1 * t) + vec2(0.0, 0.07), 72)) / 0.07;
    g += vec2(gnoise(q * 1.7 - vec2(0.2 * t, -0.35 * t), 73), gnoise(q * 1.7 + vec2(0.31 * t, 0.12 * t), 74)) * 0.6;
    vec3 Vp = normalize(V + vec3(g.x, 0.0, g.y) * 0.022);
    float s_in = length(Vp.xz);                      // 视线与竖直方向夹角的正弦
    float s_out = s_in * 1.333;
    vec3 col;
    float crit = smoothstep(0.985, 1.0, s_out);
    if (s_out < 1.0) {
        float c_out = sqrt(1.0 - s_out * s_out);
        vec3 R = vec3(Vp.x / max(s_in, 1e-5) * s_out, c_out, Vp.z / max(s_in, 1e-5) * s_out);
        vec3 sky = us_skycol(R) * us_bright;
        float edge = smoothstep(0.75, 0.99, s_out);
        sky *= 1.0 + 0.8 * edge;                     // 窗口边缘：地平线一带的天光被压缩在一圈里，更亮
        float ang = acos(clamp(dot(R, uw_moon), -1.0, 1.0));
        sky += vec3(1.0, 0.96, 0.86) * (smoothstep(0.06, 0.02, ang) * 1.0 + exp(-ang / 0.09) * 0.35) * us_moon_k;
        col = sky * mix(vec3(0.75, 1.0, 0.98), vec3(1.0), 0.4);
    } else {
        col = mix(uw_deep, uw_mid, 0.75);              // 全反射：映出下方的深水
    }
    col = mix(col, mix(uw_deep, uw_mid, 0.75), crit * 0.6);
    // 水面本身的细碎亮纹（波纹的焦散）
    col += uw_top * uw_caustic(q * 1.6, t) * 0.16 * (1.0 - crit);
    return vec4(uw_apply_fog(col), 1.0);
}
"""

# 光柱：一组竖长的平面，加法混合。每块平面上沿着光的方向排着几道细光，光的横向位置随时间缓慢摇动，
# 亮度也缓慢起伏；越往下越暗，两侧淡出。
UW_RAYS_GLSL = """
uniform float ur_k;             // 亮度
uniform vec3 ur_col;
uniform float ur_n;             // 每块平面上光的道数（约）
uniform float ur_seed;
vec4 material(vec4 base) {
    float u = v_uv01.x, v = v_uv01.y;
    float t = u_time;
    float x = u * ur_n + 0.35 * sin(0.21 * t + v * 2.0 + ur_seed * 6.0) + 0.2 * sin(0.37 * t + ur_seed * 3.0);
    float n = fbm(vec2(x, 0.04 * t + ur_seed * 9.0), 3, 0.0, int(ur_seed * 97.0));
    float rays = smoothstep(0.5, 0.8, n);
    float fine = vnoise(vec2(x * 4.0, 0.1 * t), int(ur_seed * 31.0) + 3);
    rays *= 0.5 + 0.9 * fine;
    float flick = 0.75 + 0.25 * sin(0.6 * t + ur_seed * 11.0) * sin(0.23 * t + ur_seed * 5.0);
    float fade = smoothstep(0.0, 0.14, v) * (exp(-v * 3.2) * 0.8 + 0.2 * (1.0 - v)) * smoothstep(0.0, 0.2, u) * smoothstep(1.0, 0.8, u);
    vec3 c = ur_col * rays * fade * flick * ur_k;
    return vec4(c, 0.0);
}
"""

# 水底与沟壁：岩石与泥沙的贴图，被透下的月光照亮（越深越暗），水底上有缓慢游动的焦散，远处融进水色。
# 沟壁在水底以下迅速变暗，十几个单位以下接近全黑，但近处仍看得出岩层。
UW_FLOOR_GLSL = UW_COMMON + """
uniform float uf_caustic;       // 焦散强度
uniform float uf_dark;          // 水底以下变暗的特征深度（只用于沟壁）
uniform float uf_floor_y;       // 水底高度
uniform float uf_is_wall;       // 1 为沟壁
uniform float uf_adapt;         // 镜头进到沟里以后，沟壁与沟底提亮的倍数（相当于眼睛适应了暗处）
vec4 material(vec4 base) {
    vec3 p = v_wpos;
    float depth = max(uw_surf - max(p.y, uf_floor_y), 0.0);       // 沟里的光按沟口的水深算，沟内另按 uf_dark 变暗
    vec3 light = uw_light * exp(-depth / uw_atten);
    float fw = length(fwidth(p.xz / 11.0));
    float big = fbm(p.xz / 11.0 + p.y * 0.05, 4, fw, 81);
    vec3 alb = base.rgb * (0.7 + 0.6 * big);
    float c = uw_caustic(p.xz * 0.8, u_time) * uf_caustic;
    float below = max(uf_floor_y - p.y, 0.0);
    // 沟壁是竖直的，只接到一部分从上面透下的光：沟口处约为水底的六成，往下按 uf_dark 迅速变暗；
    // 另有一份在水里散射开的微光，衰减得慢，沟壁深处的岩层因此仍隐约可辨。
    // 沟口紧下方再压暗一截，沟沿是一条清楚的明暗分界
    float shade = uf_is_wall > 0.5 ? (0.45 * exp(-below / uf_dark) + 0.22 * exp(-below / 22.0))
                                     * (0.5 + 0.5 * smoothstep(0.0, 0.8, below)) : 1.0;
    c *= uf_is_wall > 0.5 ? exp(-below / 1.5) * 0.4 : 1.0;
    vec3 col = alb * light * (0.8 + c) * shade;
    if (uf_is_wall > 0.5) col *= mix(1.0, uf_adapt, smoothstep(uf_floor_y - 0.5, uf_floor_y - 4.0, u_eye.y));
    uw_fogk = uf_is_wall > 0.5 ? 0.6 : 1.0;
    return vec4(uw_apply_fog(col), base.a);
}
"""

# 给水下的其他平面（立面的水下部分、横幅、碎块、字）用的材质：按水深加上水下的光色，再按距离融进水色，
# 与背景的雾一致。uo_light 为水下光色的作用程度（0 为保持原色，只加雾）。
UW_OBJ_GLSL = UW_COMMON + """
uniform float uo_light;
vec4 material(vec4 base) {
    if (base.a <= 0.0) return base;
    vec3 c = base.rgb / base.a;
    float depth = max(uw_surf - v_wpos.y, 0.0);
    vec3 tint = mix(vec3(1.0), uw_light / max(max(uw_light.r, uw_light.g), uw_light.b), uo_light);
    c *= tint * mix(1.0, exp(-depth / uw_atten), uo_light);
    return vec4(uw_apply_fog(c) * base.a, base.a);
}
"""

UW_DEFAULTS = {
    "uw_top": (0.15, 0.40, 0.41), "uw_mid": (0.05, 0.18, 0.205), "uw_deep": (0.016, 0.062, 0.074),
    "uw_surf": WATER_Y, "uw_vis": 30.0, "uw_atten": 14.0, "uw_light": (0.85, 1.6, 1.6),
    "uw_moon": tuple(dir_from(*MOON_DIR)),
}


def seabed_texture(size=4096):
    """水底的颜色贴图，float32 RGB，四边无缝，一块对应 12 单位见方：干河床的岩石（Poly Haven "Dry riverbed rock"，
    Amal Kumar，CC0）上盖着一层泥沙（"Dirt"），去饱和、略偏青绿。亮度是反照率（0.15–0.3），
    实际明暗由材质 bd_floor 按水深、月光和焦散算出。"""
    def make():
        rng = np.random.default_rng(21)
        rock = _poly(RIVERBED_FILE, size // 2)
        rock = np.tile(rock, (2, 2, 1))
        dirt = _poly(DIRT_FILE, size // 3 + 1)[: size // 3, : size // 3]
        dirt = cv2.resize(np.tile(dirt, (3, 3, 1)), (size, size), interpolation=cv2.INTER_AREA)
        n = _wrap_noise(size, 24, rng, smooth=1.2)
        n = n / (n.std() + 1e-6) + 0.3 * _wrap_noise(size, size // 16, rng)
        m = _smooth(n, -0.4, 0.7)                                     # 1 为泥沙
        col = rock * (1 - m[..., None]) + dirt * m[..., None]
        lum = col @ LUMA
        col = lum[..., None] * 0.7 + col * 0.3
        col = col * np.array([0.82, 0.98, 0.95], np.float32) * 0.62
        return col.astype(np.float32)
    return _cached("seabed", make, size, "s1")


def crack_wall_texture(size=2048):
    """沟壁的颜色贴图：同一张干河床岩石，转成横向的岩层，四边无缝，一块对应 8 单位见方。"""
    def make():
        rock = _poly(RIVERBED_FILE, size)
        lum = rock @ LUMA
        col = lum[..., None] * 0.75 + rock * 0.25
        col = col * np.array([0.85, 0.97, 0.95], np.float32) * 0.6
        return col.astype(np.float32)
    return _cached("crackwall", make, size, "c1")


# 裂沟的形状：沿 x 方向的一道沟，开在被淹没的展览馆立面脚下。远岸紧贴在立面背后（z ≈ SPIRE.z - 1.8），
# 在立面宽度内几乎是直的；近岸在立面正前方向镜头一侧鼓出，正中离立面约 17.5 单位，向两侧收窄，到 ±75 单位处合拢。
# 这样横幅碎块和"摔碎進溝裡"五个字（z 在 SPIRE.z 到 SPIRE.z + 6.6 之间）直接沉进沟里，镜头下降到
# SPIRE + (-0.5, -15.5, 15) 时也正好在沟口以下、沟壁之间。
CRACK = dict(x0=SPIRE[0] - 75.0, x1=SPIRE[0] + 75.0, far=SPIRE[2] - 1.8, bulge=13.5, bulge_w=16.0, base_w=6.0,
             flare=8.0, upper=5.0, seed=17)


def crack_outline(n=160):
    """裂沟在水底平面上的轮廓：返回 (x, 近岸 z, 远岸 z)，近岸在 +z 一侧（镜头一侧）。"""
    C = CRACK
    rng = np.random.default_rng(C["seed"])
    x = np.linspace(C["x0"], C["x1"], n)
    u = (x - C["x0"]) / (C["x1"] - C["x0"])
    dx = x - SPIRE[0]
    taper = np.sin(np.pi * u) ** 0.45
    w = (C["base_w"] + C["bulge"] * np.exp(-(dx / C["bulge_w"]) ** 2)) * taper
    jag_n = gaussian_filter(rng.normal(0, 1, n), 0.7) * 0.5 + gaussian_filter(rng.normal(0, 1, n), 3) * 0.7
    jag_f = gaussian_filter(rng.normal(0, 1, n), 0.7) * 0.25
    # 远岸：立面宽度（±31）以内贴着立面背后，以外渐渐弯向 +z，并带一点起伏
    far = C["far"] + jag_f + np.clip(np.abs(dx) - 31, 0, None) ** 1.3 * 0.05
    near = far + w + jag_n * taper
    return x, near, far


SEABED_SIZE = 260.0


def _seabed_mask_path():
    """水底平面上挖出裂沟的路径（平面的 0–1 坐标，u 向右即 +x，v 向下即 +z）。"""
    import skia
    x, near, far = crack_outline()
    cx, cz = SPIRE[0], SPIRE[2]
    uu = lambda xx: (xx - cx) / SEABED_SIZE + 0.5
    vv = lambda zz: (zz - cz) / SEABED_SIZE + 0.5
    p = skia.Path()
    p.moveTo(float(uu(x[0])), float(vv(near[0])))
    for xi, zi in zip(x[1:], near[1:]):
        p.lineTo(float(uu(xi)), float(vv(zi)))
    for xi, zi in zip(x[::-1], far[::-1]):
        p.lineTo(float(uu(xi)), float(vv(zi)))
    p.close()
    return p


def _wall_segments():
    """沟壁的平面：每岸沿轮廓分成若干段，每段上下两块——上段从水底竖直向下 upper 单位，下段再向外张开 flare
    单位、一直到裂沟底部（plan.CHASM 以下 2 单位）。张开的下段让沟底比沟口宽，镜头进到沟里有空间。"""
    from engine import rot_matrix
    C = CRACK
    x, near, far = crack_outline(48)
    y_top, y_mid, y_bot = SEABED_Y + 0.3, SEABED_Y - C["upper"], CHASM[1] - 2.0
    segs = []
    for side, zs in (("far", far), ("near", near)):
        out = -1.0 if side == "far" else 1.0          # 向外（离开沟中心）的 z 方向
        for i in range(len(x) - 1):
            a = np.array([x[i], 0, zs[i]])
            b = np.array([x[i + 1], 0, zs[i + 1]])
            d = b - a
            L = float(np.linalg.norm(d)) * 1.08
            yaw = math.degrees(math.atan2(-d[2], d[0]))   # 平面的 +x 轴沿这一段
            if side == "near":
                yaw += 180.0                              # 近岸的壁面朝 -z（朝沟内）
            mid = (a + b) / 2
            # 上段：竖直
            h1 = y_top - y_mid
            segs.append(dict(center=(mid[0], (y_top + y_mid) / 2, mid[2] + out * 0.25), size=(L, h1),
                             rot=(yaw, 0.0, 0.0), v0=0.0, v1=h1))
            # 下段：底边向外张开 flare
            h2 = y_mid - y_bot
            tilt = math.degrees(math.atan2(C["flare"], h2))
            slant = math.hypot(h2, C["flare"])
            cz = mid[2] + out * (0.25 + C["flare"] / 2)
            segs.append(dict(center=(mid[0], (y_mid + y_bot) / 2, cz), size=(L, slant),
                             rot=(yaw, tilt, 0.0), v0=h1, v1=h1 + slant))
    return segs


def underwater_items(cam, t, particles=True, rays=True, crack=True, moon_dir=None, group="past", **uniforms):
    """水下的一整套背景，只在镜头位于水面以下时返回元素：

    水色背景：一块始终正对镜头、放在镜头前方 150 单位处的大平面（材质 bd_uw_fog），颜色只随视线方向变化；
    水面下视：y = WATER_Y 的水平平面（与水面同样大小，材质 bd_uw_surface），斯涅尔窗里透出夜空和月亮；
    光柱：从水面斜着透下来的 7 块竖长平面（材质 bd_uw_rays，加法混合），朝向随镜头转，始终以宽面对着镜头；
    颗粒：镜头周围 70×36×70 单位的空间里约 5000 粒悬浮的细小颗粒（Particles，加法混合），缓慢漂移；
    水底：y = SEABED_Y（水面以下 13 单位）、260 单位见方的平面（材质 bd_floor），挖出裂沟的口；
    沟壁：沿裂沟两岸的若干块平面，一直延伸到 plan.CHASM 以下 2 单位，越深越黑。

    排序：背景、水面下视、水底与沟壁都按镜头给了偏移，依次最先画；光柱、颗粒和场景里的其他元素照常排序。
    沉进裂沟的碎块在沟口以下时，要给它们比水底更远的排序深度（例如 stack 或 bias），否则会画在水底之上。"""
    from engine import Particles, Plane, dot_atlas, rot_matrix
    if cam.eye[1] > WATER_Y - 0.02:
        return []
    U = dict(UW_DEFAULTS)
    if moon_dir is not None:
        U["uw_moon"] = tuple(dir_from(*moon_dir))
    U.update({k: v for k, v in uniforms.items() if k.startswith("uw_")})
    items = []
    right, up, fwd = cam.basis()
    eye = np.asarray(cam.eye, float)
    # 水色背景
    D = 150.0
    hh = D * math.tan(math.radians(cam.fov) / 2) * 1.6
    yaw = math.degrees(math.atan2(-fwd[0], -fwd[2]))
    pitch = math.degrees(math.asin(np.clip(fwd[1], -1, 1)))
    fog = Plane(None, center=eye + fwd * D, size=(hh * 2 * 1.9, hh * 2 * 1.9), rot=(yaw, pitch, 0.0), group=group,
                material="bd_uw_fog", uniforms=U, bias=2e4)
    items.append(fog)
    # 水面下视
    sky = _tex("pano_wrap", lambda: sky_panorama(), repeat=True)
    su = dict(U, bw_sky=sky, us_bright=uniforms.get("us_bright", 2.6), us_moon_k=uniforms.get("us_moon_k", 1.4))
    surf = Plane(None, center=(SPIRE[0], WATER_Y, (POOL_Z0 + POOL_Z1) / 2), size=(2 * POOL_HALF_W, POOL_Z0 - POOL_Z1),
                 rot=(0.0, 90.0, 0.0), group=group, material="bd_uw_surface", uniforms=su)
    surf.bias = 1.5e4 - _depth(surf, cam)
    items.append(surf)
    # 水底与沟壁
    floor_items = []
    if crack:
        wt = _tex("crackwall", lambda: crack_wall_texture(), repeat=True)
        fu = dict(U, uf_caustic=0.0, uf_dark=7.0, uf_floor_y=SEABED_Y, uf_is_wall=1.0,
                  uf_adapt=uniforms.get("uf_adapt", 3.5))
        floor_items.append(Plane(wt, center=(CRACK["x0"] / 2 + CRACK["x1"] / 2, CHASM[1] - 2.0, SPIRE[2] + 8.0),
                                 size=(CRACK["x1"] - CRACK["x0"], 60.0), rot=(0.0, -90.0, 0.0),
                                 uv=(0.0, 0.0, (CRACK["x1"] - CRACK["x0"]) / 8.0, 60.0 / 8.0),
                                 group=group, material="bd_floor", uniforms=fu, stack="bd_floor"))
        for sg in _wall_segments():
            w, h = sg["size"]
            floor_items.append(Plane(wt, center=sg["center"], size=sg["size"], rot=sg["rot"], group=group,
                                     uv=(sg["center"][0] / 8.0, sg["v0"] / 8.0, sg["center"][0] / 8.0 + w / 8.0,
                                         sg["v1"] / 8.0),
                                     material="bd_floor", uniforms=fu, stack="bd_floor"))
    st = _tex("seabed", lambda: seabed_texture(), repeat=True)
    bu = dict(U, uf_caustic=uniforms.get("uf_caustic", 0.5), uf_dark=7.0, uf_floor_y=SEABED_Y, uf_is_wall=0.0, uf_adapt=1.0)
    if "_mask" not in _TEX:
        _TEX["_mask"] = _seabed_mask_path()
    k = SEABED_SIZE / 12.0
    bed = Plane(st, center=(SPIRE[0], SEABED_Y, SPIRE[2]), size=(SEABED_SIZE, SEABED_SIZE), rot=(0.0, -90.0, 0.0),
                uv=(0.0, 0.0, k, k), group=group, material="bd_floor", uniforms=bu,
                mask=_TEX["_mask"] if crack else None, stack="bd_floor")
    floor_items.append(bed)
    for it in floor_items:
        it.bias = 1e4
    items += floor_items
    # 光柱：从水面向下斜射，方向由月光折射进水里决定
    if rays:
        md = np.asarray(U["uw_moon"], float)
        h_m = np.array([md[0], 0.0, md[2]])
        h_m /= max(np.linalg.norm(h_m), 1e-6)
        s_in = math.sqrt(max(0.0, 1 - md[1] ** 2))
        s_out = s_in / 1.333
        ldir = -h_m * s_out + np.array([0.0, -math.sqrt(1 - s_out ** 2), 0.0])   # 光在水里前进的方向（向下）
        rng = np.random.default_rng(5)
        L = (WATER_Y - SEABED_Y) / max(-ldir[1], 0.3) * 1.15
        # 光柱的上端固定在水面上：立面前方的水面上按约 9 单位的间距布一张带抖动的网格（世界坐标里固定），
        # 只画镜头前方 3–45 单位内最近的 14 道；每块平面绕光的方向转动，始终以宽面对着镜头
        gx, gz = np.meshgrid(np.arange(-60, 61, 9.0), np.arange(0.5, 61, 9.0))
        tops = np.c_[SPIRE[0] + gx.ravel() + rng.uniform(-3.5, 3.5, gx.size), np.full(gx.size, WATER_Y),
                     SPIRE[2] + gz.ravel() + rng.uniform(-3.0, 3.0, gx.size)]
        tops[:, 2] = np.maximum(tops[:, 2], SPIRE[2] + 0.5)
        n_all = len(tops)
        widths, ks, ns, seeds = (rng.uniform(3, 8, n_all), rng.uniform(0.55, 1.2, n_all), rng.uniform(5.0, 9.0, n_all),
                                 rng.uniform(0, 1, n_all))
        ctrs = tops + ldir[None, :] * L / 2
        rel = ctrs - eye[None, :]
        dist = np.linalg.norm(rel, axis=1)
        ahead = rel @ fwd
        ok = np.where((dist > 3) & (dist < 45) & (ahead > -2))[0]
        ok = ok[np.argsort(dist[ok])][:14]
        ax = -ldir / np.linalg.norm(ldir)
        for i in ok:
            ctr = ctrs[i]
            to_cam = eye - ctr
            nrm = to_cam - ax * (to_cam @ ax)
            nrm /= max(np.linalg.norm(nrm), 1e-6)
            xax = np.cross(ax, nrm)
            R = np.stack([xax, ax, nrm], 1)
            fade_d = float(np.clip((45 - dist[i]) / 10, 0, 1))          # 远处的光柱逐渐淡出，进出范围时不跳
            items.append(Plane(None, center=ctr, size=(float(widths[i]), L), rot=_euler(R), blend="add", group=group,
                               material="bd_uw_rays", bias=-500.0,
                               uniforms={"ur_k": uniforms.get("ur_k", 1.0) * float(ks[i]) * fade_d,
                                         "ur_col": (0.55, 0.95, 0.92), "ur_n": float(ns[i]), "ur_seed": float(seeds[i])}))
    if particles:
        items.append(_marine_snow(eye, t, group))
    return items


def _euler(R):
    """旋转矩阵 → 引擎的 (yaw, pitch, roll)（度），对应 Ry(yaw)·Rx(pitch)·Rz(roll)。"""
    sb = -R[1, 2]
    pitch = math.asin(max(-1.0, min(1.0, sb)))
    if abs(math.cos(pitch)) < 1e-6:
        yaw, roll = math.atan2(-R[2, 0], R[0, 0]), 0.0
    else:
        yaw, roll = math.atan2(R[0, 2], R[2, 2]), math.atan2(R[1, 0], R[1, 1])
    return tuple(math.degrees(v) for v in (yaw, pitch, roll))


_SNOW = {}


def _marine_snow(eye, t, group, n=5000, box=(70.0, 36.0, 70.0)):
    """悬浮颗粒：在一个随镜头平移、但颗粒本身固定在世界里的周期性方盒中，颗粒缓慢下沉、横向漂移；
    越靠近水面越亮，远处融进水里。"""
    from engine import Particles, dot_atlas
    if "data" not in _SNOW:
        rng = np.random.default_rng(31)
        _SNOW["data"] = dict(p=rng.uniform(0, 1, (n, 3)).astype(np.float32),
                             v=(rng.normal(0, 1, (n, 3)) * [0.05, 0.02, 0.05] + [0.02, -0.06, 0.0]).astype(np.float32),
                             s=(0.04 + 0.09 * rng.uniform(0, 1, n) ** 3).astype(np.float32),
                             b=rng.uniform(0.3, 1.0, n).astype(np.float32), ph=rng.uniform(0, 6.28, n).astype(np.float32))
        _SNOW["atlas"] = dot_atlas(64, 0.35)
    d = _SNOW["data"]
    B = np.array(box, np.float32)
    p = d["p"] * B + d["v"] * t
    p[:, 0] += 0.15 * np.sin(0.3 * t + d["ph"])
    lo = eye.astype(np.float32) - B / 2
    p = lo + np.mod(p - lo, B)
    dist = np.linalg.norm(p - eye.astype(np.float32), axis=1)
    depth = np.maximum(WATER_Y - p[:, 1], 0)
    k = d["b"] * np.exp(-dist / 18.0) * np.exp(-depth / 16.0) * 1.1 * (p[:, 1] < WATER_Y)
    col = np.c_[0.55 * k, 0.95 * k, 0.9 * k, np.ones(n, np.float32)]
    return Particles(_SNOW["atlas"], p, d["s"], None, col, blend="add", group=group)


# ---------------------------------------------------------------------------
# 材质注册（导入本模块即完成）
# ---------------------------------------------------------------------------

def register_materials():
    """注册本模块的全部材质：bd_water（水面倒影）、bd_ground（院子地面）、bd_uw_fog（水下背景）、
    bd_uw_surface（水下仰望的水面）、bd_uw_rays（光柱）、bd_floor（水底与沟壁）。导入模块时已自动调用一次。"""
    from engine import register_material
    _register_materials()
    _register_ground()
    register_material("bd_uw_fog", UW_FOG_GLSL, dict(UW_DEFAULTS))
    register_material("bd_uw_surface", UW_SURFACE_GLSL, dict(UW_DEFAULTS, us_bright=2.6, us_moon_k=1.4))
    register_material("bd_uw_rays", UW_RAYS_GLSL, {"ur_k": 1.0, "ur_col": (0.55, 0.95, 0.92), "ur_n": 3.5, "ur_seed": 0.3})
    register_material("bd_uw_obj", UW_OBJ_GLSL, dict(UW_DEFAULTS, uo_light=1.0))
    register_material("bd_floor", UW_FLOOR_GLSL, dict(UW_DEFAULTS, uf_caustic=0.5, uf_dark=7.0, uf_floor_y=SEABED_Y,
                                                      uf_is_wall=0.0, uf_adapt=3.5))


register_materials()


# ---------------------------------------------------------------------------
# 预览：每样素材的单图与三张合成参考，输出到 renders/seg_c/assets/
# ---------------------------------------------------------------------------

GRADE = {"past": {"halation": 1.2, "lift": 0.03, "gain": 1.25, "vignette": 0.38}}


def _graded(img, vignette=0.0, seed=1):
    """单图预览：按样张 B 的参数过一遍"过去"的调色（不加暗角和划痕），数值才和成片里看到的一致。"""
    return L.grade_past(np.asarray(img, np.float32)[..., :3], seed=seed, halation=1.2, lift=0.03, gain=1.25,
                        vignette=vignette, scratch=False)


def _save(img, name):
    OUT.mkdir(parents=True, exist_ok=True)
    Image.fromarray((np.clip(img, 0, 1) * 255 + 0.5).astype("u1")).save(OUT / name)
    print(OUT / name)


def _over(rgba, bg):
    a = rgba[..., 3:4]
    return rgba[..., :3] * a + np.asarray(bg, np.float32) * (1 - a)


def previews():
    """每样素材的单图（都已按"过去"的调色显示）。"""
    L.low_priority()
    # 夜空全景：把月亮按缺省位置叠上去，缩到 4096 宽
    pano = sky_panorama()[..., :3].copy()
    moon, halo = moon_textures()
    d_px = 2.2 * PX_DEG
    cx, cy = float(yaw_to_x(MOON_DIR[0])), float(el_to_y(MOON_DIR[1]))
    for tex, size, add in ((halo, d_px * 7, True), (moon, d_px * 512 / 440, False)):
        n = int(round(size))
        t = cv2.resize(tex, (n, n), interpolation=cv2.INTER_AREA)
        x0, y0 = int(cx - n / 2), int(cy - n / 2)
        reg = pano[y0:y0 + n, x0:x0 + n]
        if add:
            reg += t[..., :3]
        else:
            reg[:] = reg * (1 - t[..., 3:]) + t[..., :3] * t[..., 3:]
    small = cv2.resize(pano, (4096, int(4096 * PANO_H / PANO_W)), interpolation=cv2.INTER_AREA)
    _save(_graded(small), "夜空全景.png")
    # 月亮（单独一层）
    m = cv2.resize(moon, (256, 256), interpolation=cv2.INTER_AREA)
    h = cv2.resize(halo, (768, 768), interpolation=cv2.INTER_AREA)
    canvas = np.zeros((768, 768, 3), np.float32) + NIGHT * 1.3
    canvas += h[..., :3]
    canvas[256:512, 256:512] = _over(m, canvas[256:512, 256:512])
    _save(_graded(canvas), "月亮.png")
    # 剪影带：衬在地平线附近的天色上
    for name, label in (("near", "近"), ("far", "远")):
        b = silhouette_band(name)
        bg = np.zeros(b.shape[:2] + (3,), np.float32) + NIGHT * 1.65 * 1.6
        img = _over(b, bg)
        w = 4096
        _save(_graded(cv2.resize(img, (w, int(w * b.shape[0] / b.shape[1])), interpolation=cv2.INTER_AREA)),
              f"剪影带_{label}.png")
    # 水面：静态贴图与细纹高度图
    _save(_graded(cv2.resize(water_texture(), (1024, 1024), interpolation=cv2.INTER_AREA)), "水面贴图_静态.png")
    r = cv2.resize(water_ripple(), (1024, 1024), interpolation=cv2.INTER_AREA)
    _save(np.dstack([r] * 3), "水面细纹_高度图.png")
    # 院子地面
    _save(_graded(cv2.resize(yard_texture(), (1024, 1024), interpolation=cv2.INTER_AREA)), "院子地面.png")
    # 水底与沟壁（乘上水底处的水下光色后显示）
    light = np.asarray(UW_DEFAULTS["uw_light"], np.float32) * math.exp(-13.0 / UW_DEFAULTS["uw_atten"])
    _save(_graded(cv2.resize(seabed_texture(), (1024, 1024), interpolation=cv2.INTER_AREA) * light), "水底.png")
    cw = cv2.resize(crack_wall_texture(), (1024, 1024), interpolation=cv2.INTER_AREA) * light * 2.4
    yy = np.linspace(0, 1, 1024, dtype=np.float32)[:, None, None]
    _save(_graded(cw * np.exp(-yy * 30 / 11.0)), "沟壁_自沟口向下30单位.png")


def _placeholders(under):
    """合成参考里的占位：墙（灰色平面）和被淹没的展览馆（深色的竖长平面，水面以上是塔楼，下面是立面）。"""
    from engine import Plane
    x0 = WALL[0] - 7.0
    items = []
    wall = Plane(None, center=(x0 + 19.0, WALL[1] + 0.5, WALL[2]), size=(38.0, 15.0), color=(0.26, 0.26, 0.25))
    tower_col = tuple(NIGHT * 0.45)
    if not under:
        items.append(wall)
        items.append(Plane(None, center=(SPIRE[0], WATER_Y + 27.0, SPIRE[2]), size=(14.0, 54.0), color=tower_col))
        items.append(Plane(None, center=(SPIRE[0], WATER_Y + 3.0, SPIRE[2] + 0.01), size=(62.0, 6.0), color=tower_col))
    else:
        fa = np.zeros((130, 310, 4), np.float32)
        fa[..., :3] = NIGHT * 2.2
        fa[..., 3] = 1
        for r in range(8, 130, 18):
            fa[r:r + 4, :, :3] = NIGHT * 1.2
        items.append(Plane(fa, center=(SPIRE[0], (SEABED_Y + WATER_Y) / 2, SPIRE[2]), size=(62.0, WATER_Y - SEABED_Y),
                           material="bd_uw_obj", uniforms=dict(UW_DEFAULTS, uo_light=1.0), stack="facade"))
        items.append(Plane(None, center=(SPIRE[0], WATER_Y - 2.1, SPIRE[2] + 0.05), size=(28.0, 2.7),
                           color=tuple(L.C["red"] * 0.9), material="bd_uw_obj",
                           uniforms=dict(UW_DEFAULTS, uo_light=1.0), stack="facade"))
    return items


COMPOSITES = {
    # 名称：(眼睛, 注视点, 竖直视角, 时刻)
    "合成_墙前仰望墙头和夜空": (None, None, None, 61.6),
    "合成_越过墙头望向水池和夜空": (None, None, 62.0, 66.0),
    "合成_水下仰望": (SPIRE + np.array([-2.0, -9.0, 24.0]), SPIRE + np.array([-2.0, 3.0, 14.0]), 52.0, 72.0),
    "合成_沉向裂沟": (SPIRE + np.array([-0.5, -15.5, 15.0]), SPIRE + np.array([0.0, -20.5, 5.8]), 48.0, 73.5),
    "合成_水下望立面": (SPIRE + np.array([-1.5, -3.0, 12.0]), SPIRE + np.array([0.0, -3.6, 6.0]), 46.0, 71.5),
    "合成_水底裂沟": (SPIRE + np.array([-6.0, -7.5, 34.0]), SPIRE + np.array([0.0, -15.0, 6.0]), 50.0, 72.5),
}


def _composite_cam(name):
    from engine import Cam
    eye, tgt, fov, t = COMPOSITES[name]
    if name == "合成_墙前仰望墙头和夜空":
        import plan
        eye, tgt, fov = plan.wall_pose(18.5, 22.0, 5.0, pitch=20.0, dy=1.0)
    elif name == "合成_越过墙头望向水池和夜空":
        # 机位取 L12 后半越过墙头时的位置（plan 的 T(12, 6)），朝向略压低，让水池和倒影进画
        import plan
        f0 = plan.FLOWER0
        eye = np.array([f0[0] - 1.0, WALL[1] + 13.0, f0[2] - 3.0])
        d = np.asarray(plan.TIP, float) - eye
        d[1] = 0.0
        d = d / np.linalg.norm(d)
        tgt = eye + d * 100 + np.array([0.0, 100 * math.tan(math.radians(1.5)), 0.0])
    return Cam(eye=eye, target=tgt, fov=fov), t


def composites(names=None, size=(1920, 1080), ss=2):
    """按空间布局摆放全部背景和占位物，用引擎渲染合成参考。"""
    from engine import FrameSpec, Film
    names = names or list(COMPOSITES)
    state = {}

    def frame(t):
        cam = state["cam"]
        under = cam.eye[1] < WATER_Y
        # 塔楼占位也作为水面倒影的卡片
        card = (_tex("tower_card_ph", lambda: np.dstack([np.zeros((8, 4, 3), np.float32) + NIGHT * 0.45,
                                                        np.ones((8, 4), np.float32)])),
                (float(SPIRE[0]), WATER_Y + 27.0, 14.0, 54.0), float(SPIRE[2]))
        items = backdrop_items(cam, t, cards=[card]) + _placeholders(under)
        return FrameSpec(cam, items, grade=GRADE)

    film = Film(frame, fps=60, size=size, ss=ss)
    for n in names:
        cam, t = _composite_cam(n)
        state["cam"] = cam
        film.still(t, OUT / f"{n}.png", subframes=1)
        print(OUT / f"{n}.png")


def backdrop_items(cam, t, moon_dir=None, cards=None, group="past"):
    """按镜头位置返回全部背景：镜头在水面以上时是夜空、剪影、水面和院子地面；在水面以下时是水下的一整套。"""
    if cam.eye[1] >= WATER_Y:
        return (sky_items(moon_dir=moon_dir, group=group) + silhouette_items(group=group)
                + pool_items(cam, cards=cards, moon_dir=moon_dir, group=group) + yard_items(cam, group=group))
    return underwater_items(cam, t, moon_dir=moon_dir, group=group)


if __name__ == "__main__":
    args = sys.argv[1:]
    if not args or "previews" in args:
        previews()
    if not args or "composites" in args:
        composites()
