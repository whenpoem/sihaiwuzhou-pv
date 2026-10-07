"""副歌一 L12–L14 的尖塔素材：北京展览馆（原苏联展览馆）的中央塔楼与正立面、塔顶的五角星、
塔基的"中蘇友誼萬歲"横幅，以及横幅碎裂用的碎块。

L12 里向日葵飞向远处一座顶着五角星的苏式尖塔，塔身由一行行仿宋字填成，塔基挂着红色横幅；L13 向日葵在塔尖
停住后坠落进塔前的水池；L14 在水下仰望时，横幅在"摔碎"一拍从中间裂开、碎成块，沉向水底的裂沟。本模块只提供
这些物件的贴图和几何，场景动画、镜头和水面由场景代码负责。

做法
    建筑以 Shizhao 拍摄的北京展览馆正面照片（assets/images/Beijing_Exhibition_Center.jpg，CC BY-SA 3.0）为底。
    天空是均匀的浅灰，先用多项式拟合天空、再用只平均天空像素的局部高斯平均跟上云带的起伏，按像素与天空的色差抠出
    建筑，并把边缘里混进的天空色换成附近建筑的颜色。照片从偏左处拍摄，塔楼比立面靠后，视差使塔楼整体偏左约
    39 像素、尖塔还向左倾斜，所以塔楼部分按行平移并拉直，与立面的对称轴（原图 x = 1071）对齐。原横幅一带改画成
    塔楼基座落在屋顶栏杆上的样子，留给新横幅；建筑在门洞下沿附近、铁栅栏门柱顶端以上（原图 y = 2258）截断，
    这条线就是水面高度。照片里塔楼上层每单位只有约 27 像素，放大后噪点会变成歪斜的团块，所以这一段的轮廓左右
    取平均；尖塔锥身、冠部（两层杯形与叶饰）和锥顶以上的平台、栏杆、宝珠、细杆都按照片实测的尺寸用解析轮廓重画。

    建筑的表面全部由很小的繁体朱雀仿宋字逐行排满：字号 EM = 0.31、行距 LINE = 0.36（世界单位），宽的立面上
    每行的起点随机错开，窄处（尖塔、角亭）在段内居中。字的内容取五十年代的公开口号与诗词（PHRASES，不含人名、
    不用报头），塔尖第一行从"中蘇友誼萬歲"开始。照片每处的明暗决定笔画的粗细：字先画成有符号距离场，再按明暗把
    笔画边界向外或向内移动，最暗处细到发丝、最亮处约为原来的三倍；每个字另按自身的墨量做一点校正，笔画多的字
    不会显得更黑。所以拱门、柱子、窗洞、檐口和塔身的分段都能从字的疏密里看出来，远看是石头建筑，近看是字。
    颜色按照片的材质分类：石材用暖白，金色尖塔用美术字黄，门扇用褪色红，冠部用旧铜色，两翼屋顶用灰绿。

坐标系与单位
    "建筑坐标系"的原点在建筑底边中点（水面高度），x 向右，y 向上，单位是世界单位，从底边到五角星上顶点总高 80。
    原图上每个世界单位约 27.2 像素。BUILDING、SPIRE_TOP、STAR、STAR_GLOW、BANNER 都是这个坐标系里的
    dict(center=(x, y), size=(w, h))，贴图铺满对应的矩形；放进场景时，把建筑坐标系的原点放在 plan.SPIRE，
    平面中心取 plan.SPIRE + (cx, cy, 0)、尺寸取 size 即可（各贴图都在同一个竖直平面上，正面朝 +z）。
    BUILDING 的 x 范围是 −29.9 到 31.0（左右截在两翼带徽章的壁柱外缘，两侧到轴线的距离不等，所以中心 x ≈ 0.55）。
    贴图一律是 0–1 浮点 RGBA，直通 alpha，第 0 行是图像顶部；发光部分的数值超过 1。

建筑本体与塔尖
    building_rgba(variant="night" | "albedo", cut_top=False)：整座建筑，每单位 RES_BUILDING = 48 像素，
    2920×3840。夜景版已经按夜色打好光：冷蓝的环境光（与样张 B 相同的色调，上部略亮、两翼渐暗）加上五角星的暖光，
    尖塔和星附近明显亮起，镀金的尖塔反光更强；反照率版只有固有色和字的明暗，供场景自己打光。cut_top=True 时把
    SPIRE_TOP 范围内、渐变带以上的部分挖空，与塔尖贴图叠用。
    spire_top_rgba(variant)：塔尖高分辨率贴图，每单位 RES_SPIRE = 160 像素，1440×5440，覆盖 x ∈ [−4.5, 4.5]、
    y ∈ [46, 80]（冠部、锥身、平台和细杆，不含五角星）。它与建筑本体用同一套字的排布，逐像素对齐；下沿
    SPIRE_FEATHER = 1 单位的 alpha 从 0 渐变到 1，先画 building_rgba(cut_top=True)、再画塔尖，看不出接缝。
    L12 末尾镜头距塔尖约 25 单位、竖直视角 40 度，画面高约 18 单位，成片 1080p、超采样 2 倍时每单位需要约
    120 个渲染像素，塔尖贴图的 160 像素有余量。
    building_region_rgba(region, res, variant)：把建筑坐标里任一矩形 region = (x0, y0, x1, y1) 按每单位 res
    像素重新画出（同一套字，结果缓存）。L13 镜头在距立面约 13 单位处随向日葵坠落，画面高约 11 单位，此时建筑本体
    的 48 像素不够，镜头经过的那一段可以用它按 100–200 像素重画。

五角星
    star_rgba(part="all" | "body" | "glow")：苏式红宝石星。五个角各分成左右两个棱面，按左上方来的光分出明暗，
    红色玻璃自己发光、中心最亮（数值约到 2.5），金色外框和十条棱线，星的背后有一圈细的金色放射线（照片上看得到）。
    "all" 含星体、放射线和贴着星的一圈红光，位置与尺寸见 STAR（星的外接圆半径 STAR["body_radius"] ≈ 1.29）；
    "body" 不含红光；"glow" 是范围 30 单位的外圈光晕（见 STAR_GLOW），用 blend="add" 叠加。

横幅与碎块
    banner_rgba(variant="night" | "albedo")：褪色红的布，美术字黄的繁体"中蘇友誼萬歲"（思源宋体 900，横向
    放宽到 1.12 倍，即字形压扁），每单位 RES_BANNER = 150 像素，4099×408。横幅上沿在七处系在塔基上，系点之间
    略往下垂、向下散开几道斜褶，布身有疏密不匀的竖褶，越往下越松；布面有日晒褪色、雨水冲下的竖向污痕、下沿积灰、
    上下卷边和缝线，漆面有细小的剥落。位置与尺寸对齐照片里原横幅的位置（BANNER，宽 27.3、高 2.7，挂在两座角亭之间）。
    banner_shards(n=40, seed=0, variant="night")：碎块列表。种子点按变半径的泊松圆盘采样，半径从裂纹起点
    _CRACK_ORIGIN（横幅中部）向两端线性增大，所以中间碎得细、两端块大（最小块与最大块面积相差约 20 倍）；每块是
    一个种子点的维诺区域，相邻两块共用的边细分后加上抖动，两侧取同一条折线，所以碎块严丝合缝、面积之和正好铺满
    横幅。每项是 dict：poly 为 (K, 2) 多边形（横幅贴图的 0–1 坐标，u 向右、v 向下，顺时针）；centroid 为面积
    重心 (u, v)；bbox 为 (u0, v0, u1, v1)；rgba 为按 bbox 裁出的贴图（块外透明，断口处的布略亮）；center、size
    为这块贴图在建筑坐标系里的中心与尺寸，平面直接按它放置；t0 为裂纹前沿到达这一块的时刻（0–1），可用来错开
    各块脱落的先后。
    banner_cracks(n, seed)：碎开之前的裂纹，与同参数的碎块边界一致；返回 lines（覆盖率）和 time（到达时刻，
    不在裂纹上为 2），进度 p 时显示 lines * (time <= p)，乘到横幅上压暗即可。

缓存
    计算结果存在 data/cache/seg_c/spire_v1_*：照片图层和字的排布（.npz），各贴图（半精度 .npy）。贴图函数在
    同一进程里多次调用返回同一个数组，引擎按对象身份缓存纹理，不会重复上传。缓存齐全时导入模块并取出全部贴图
    约 1 秒；从头计算全部素材约 1 分钟（只用处理器）。改动算法后把 VERSION 加一即可让旧缓存失效。
    预览图由 spire_preview.py 生成，输出到 renders/seg_c/assets/。
"""
import sys
from pathlib import Path

import cv2
import numpy as np
import skia
from scipy import ndimage as ndi

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent / "style"))
import look as L  # noqa: E402

PHOTO = ROOT / "assets" / "images" / "Beijing_Exhibition_Center.jpg"
CACHE = ROOT / "data" / "cache" / "seg_c"
VERSION = "v1"

# ---------------------------------------------------------------------------
# 照片几何（在原图 2112×2816 上实测）
# ---------------------------------------------------------------------------
_Y_CUT = 2258.0          # 截断线：门洞下沿以上、铁栅栏门柱顶端以上，作为水面高度
_Y_STAR_TOP = 80.0       # 五角星上顶点
_S = (_Y_CUT - _Y_STAR_TOP) / 80.0      # 每个世界单位对应的原图像素数（约 27.2）
_AXIS = 1071.0           # 正立面的对称轴（立面左右边缘、两座角亭、拱门的中点）
_TOWER_SHIFT = 39.0      # 塔楼部分整体右移的像素数：照片从偏左处拍摄，塔楼比立面靠后，视差使它偏左
_SPIRE_LEAN = 0.018      # 尖塔向左倾斜的斜率（每向上 1 像素左移 0.018 像素），在 y<1000 处拉直
_TOWER_BAND = (700.0, 1435.0, 1568.0)   # 塔楼区域：两座角亭之间、横幅上沿以上
_BANNER_PX = (700.0, 1570.0, 1444.0, 1644.0)   # 原横幅的范围 (x0, y0, x1, y1)
_X_LEFT, _X_RIGHT = 258.0, 1914.0      # 左右截在两翼带徽章的壁柱外缘


def _px_to_world(px, py):
    """原图像素（已校正塔楼位移之后的坐标）→ 建筑坐标。"""
    return (px - _AXIS) / _S, (_Y_CUT - py) / _S


def _world_to_px(x, y):
    return _AXIS + np.asarray(x) * _S, _Y_CUT - np.asarray(y) * _S


# ---------------------------------------------------------------------------
# 建筑坐标系中的位置与尺寸
# ---------------------------------------------------------------------------
_XL, _ = _px_to_world(_X_LEFT, 0)
_XR, _ = _px_to_world(_X_RIGHT, 0)
BUILDING = dict(center=((_XL + _XR) / 2, 40.0), size=(_XR - _XL, 80.0))
SPIRE_TOP = dict(center=(0.0, 63.0), size=(9.0, 34.0))
_STAR_R = 35.0 / _S                      # 五角星外接圆半径（照片上约 35 像素）
_STAR_C = (_Y_CUT - 115.0) / _S          # 星心高度
STAR = dict(center=(0.0, _STAR_C), size=(_STAR_R * 2 * 3.2, _STAR_R * 2 * 3.2), body_radius=_STAR_R)
STAR_GLOW = dict(center=(0.0, _STAR_C), size=(30.0, 30.0))
_bx0, _by0 = _px_to_world(_BANNER_PX[0], _BANNER_PX[1])
_bx1, _by1 = _px_to_world(_BANNER_PX[2], _BANNER_PX[3])
BANNER = dict(center=((_bx0 + _bx1) / 2, (_by0 + _by1) / 2), size=(_bx1 - _bx0, _by0 - _by1))

RES_BUILDING = 48        # 建筑本体贴图：每世界单位 48 像素
RES_SPIRE = 160          # 塔尖贴图：每世界单位 160 像素
RES_BANNER = 150         # 横幅贴图
RES_STAR = 160           # 五角星贴图
RES_GLOW = 24            # 五角星外圈光晕贴图


# ---------------------------------------------------------------------------
# 缓存
# ---------------------------------------------------------------------------
def _cache_path(name):
    CACHE.mkdir(parents=True, exist_ok=True)
    return CACHE / f"spire_{VERSION}_{name}"


def _cached(name, fn):
    p = _cache_path(name + ".npz")
    if p.exists():
        with np.load(p, allow_pickle=False) as z:
            return {k: z[k] for k in z.files}
    out = fn()
    np.savez(p, **out)
    return out


# ---------------------------------------------------------------------------
# 第一步：照片 → 抠图、校正、材质
# ---------------------------------------------------------------------------
def _sky_model(im):
    """天空是均匀的浅灰，带上下左右的缓慢渐变。先找与图像上沿、两侧相连的平滑亮区作为天空样本，
    再用三次多项式拟合每个通道。"""
    H, W = im.shape[:2]
    b = cv2.GaussianBlur(im, (0, 0), 2.0)
    gm = np.zeros((H, W), np.float32)
    for c in range(3):
        gm = np.maximum(gm, np.hypot(cv2.Sobel(b[..., c], cv2.CV_32F, 1, 0), cv2.Sobel(b[..., c], cv2.CV_32F, 0, 1)))
    smooth = gm < 0.04
    smooth[1950:] = False
    lab, _ = ndi.label(smooth)
    seeds = np.unique(np.r_[lab[:5].ravel(), lab[:1900, :5].ravel(), lab[:1900, -5:].ravel()])
    sky = np.isin(lab, seeds[seeds > 0])
    sky = ndi.binary_erosion(sky, iterations=4)
    yy, xx = np.mgrid[0:H, 0:W]

    def feats(x, y):
        x = x / W * 2 - 1
        y = y / H * 2 - 1
        return np.stack([np.ones_like(x), x, y, x * x, x * y, y * y, x ** 3, x * x * y, x * y * y, y ** 3], -1)

    sel = np.flatnonzero(sky.ravel())[::5]
    A = feats(xx.ravel()[sel].astype(np.float64), yy.ravel()[sel].astype(np.float64))
    F = feats(xx.astype(np.float64), yy.astype(np.float64))
    model = np.zeros((H, W, 3), np.float32)
    for c in range(3):
        coef, *_ = np.linalg.lstsq(A, im[..., c].ravel()[sel].astype(np.float64), rcond=None)
        model[..., c] = F @ coef
    return model, sky


def _local_sky(im, sky, sigmas=(18, 50, 140)):
    """天空的局部颜色：对天空像素做归一化高斯平均（只平均天空像素），能跟上云带的起伏；
    建筑内部离天空远，依次用更大的半径外推。"""
    w = sky.astype(np.float32)
    out = np.zeros_like(im)
    got = np.zeros(im.shape[:2], np.float32)
    for s in sigmas:
        ws = cv2.GaussianBlur(w, (0, 0), s)
        cs = cv2.GaussianBlur(im * w[..., None], (0, 0), s) / np.maximum(ws, 1e-6)[..., None]
        k = np.clip(ws / 0.15, 0, 1) * (1 - got)
        out += cs * k[..., None]
        got += k
    return out / np.maximum(got, 1e-6)[..., None]


def _matte(im, model):
    """抠图。先用多项式天空模型取一个保守的天空区域，再用局部平均得到逐处的天空颜色（跟上云带），
    色差 d 在天空里约 0.01–0.04，在建筑上远大于此。建筑 = 色差大于 0.12 的大块连通区域及其内部；
    建筑内部被包围、颜色接近天空的小块（柱间、栏杆空当、拱洞里透出的天空）也算天空。
    边缘按色差与附近纯前景色差之比给出半透明。"""
    H, W = im.shape[:2]
    blur = cv2.GaussianBlur(im, (0, 0), 0.7)
    d0 = np.linalg.norm(blur - model, axis=2)
    lab, _ = ndi.label(d0 < 0.05)
    seeds = np.unique(np.r_[lab[:3].ravel(), lab[:1900, :3].ravel(), lab[:1900, -3:].ravel()])
    sky0 = np.isin(lab, seeds[seeds > 0])
    sky0[1990:] = False
    local = _local_sky(blur, ndi.binary_erosion(sky0, iterations=2))
    d = np.linalg.norm(blur - local, axis=2)
    d[int(_Y_CUT) + 2:] = 1.0
    core = d > 0.12
    lab, n = ndi.label(core)
    idx = np.arange(1, n + 1)
    area = ndi.sum(np.ones_like(d), lab, idx)
    keep = np.isin(lab, idx[area >= 400])
    keep = ndi.binary_dilation(keep, iterations=2)          # 带上边缘的过渡像素
    building = ndi.binary_fill_holes(keep | (np.arange(H)[:, None] > _Y_CUT))
    # 建筑内部被包围的天空
    holes = building & ~keep
    lab, n = ndi.label(holes | (building & (d < 0.07)))
    idx = np.arange(1, n + 1)
    mean_d = ndi.mean(d, lab, idx)
    area = ndi.sum(np.ones_like(d), lab, idx)
    cy = np.array([c[0] for c in ndi.center_of_mass(np.ones_like(d), lab, idx)]) if n else np.zeros(0)
    pocket = (mean_d < 0.06) & (cy < 1990) & (area >= 4)
    sky = ~building | np.isin(lab, idx[pocket])
    # 局部"纯前景"的色差，用于半透明边缘
    fg_d = np.where(~ndi.binary_dilation(sky, iterations=2), d, 0)
    dloc = np.maximum(ndi.maximum_filter(fg_d, 7), 0.16)
    a = np.clip((d - 0.045) / (dloc - 0.045), 0, 1)
    near = ndi.binary_dilation(sky, iterations=3)
    alpha = np.where(near, a, 1.0)
    alpha[sky & (d < 0.07)] = 0
    alpha[int(_Y_CUT) + 1:] = 0
    return alpha.astype(np.float32), d


def _decontaminate(im, alpha):
    """去掉边缘里混进来的天空色：边缘像素的颜色改用附近完全不透明像素的颜色（高斯加权平均）。"""
    solid = (alpha > 0.97).astype(np.float32)
    w = cv2.GaussianBlur(solid, (0, 0), 2.5)
    c = cv2.GaussianBlur(im * solid[..., None], (0, 0), 2.5) / np.maximum(w, 1e-4)[..., None]
    k = np.clip((alpha - 0.6) / 0.37, 0, 1)[..., None]
    out = im * k + c * (1 - k)
    out[w < 1e-3] = im[w < 1e-3]
    return out


def _shift_tower(arr):
    """塔楼部分右移并拉直尖塔：两座角亭之间、横幅上沿以上的像素按行平移。"""
    H, W = arr.shape[:2]
    x0, x1, yb = _TOWER_BAND
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    dx = np.full(H, _TOWER_SHIFT, np.float32)
    ys = np.arange(H, dtype=np.float32)
    dx += np.where(ys < 1000, _SPIRE_LEAN * (1000 - ys), 0)
    sx = xx - dx[:, None]
    inside = (yy < yb) & (xx >= x0) & (xx <= x1)
    src_ok = (sx >= x0) & (sx <= x1)
    mx = np.where(inside, sx, xx).astype(np.float32)
    arr2 = arr if arr.ndim == 3 else arr[..., None]
    out = np.dstack([cv2.remap(np.ascontiguousarray(arr2[..., c]), mx, yy, cv2.INTER_CUBIC,
                               borderMode=cv2.BORDER_REPLICATE) for c in range(arr2.shape[2])])
    kill = inside & ~src_ok
    out = np.where(inside[..., None], out, arr2)
    return out, kill


def _plinth(rgb, alpha, skyish):
    """原横幅背后：塔楼的基座一直落到屋顶平台的栏杆上，两侧是天空。基座宽度取塔楼底部线脚处的宽度，
    颜色取塔楼下部素墙每一列的平均色（模糊掉装饰，只留壁柱的明暗），上沿留一道线脚下的阴影，
    再加上取自素墙的细小颗粒。横幅两端和上沿残留的红边、角亭拱洞里透出的天空一并去掉。"""
    x0, y0, x1, y1 = 692, int(_TOWER_BAND[2]) - 3, 1441, 1655
    row = alpha[y0 - 4]
    xs = np.flatnonzero(row[850:1320] > 0.5) + 850
    lp, rp = float(xs.min()), float(xs.max() + 1)
    alpha[y0:y1, x0:x1] = 0
    # 与刚挖空的区域相连、颜色接近天空的像素（角亭拱洞里的天空）也挖掉
    hole = np.zeros(alpha.shape, bool)
    hole[y0:y1, x0:x1] = True
    lab, _ = ndi.label(hole | (skyish & (alpha < 0.999)) )
    ids = np.unique(lab[y0:y1, x0:x1])
    sky_add = np.isin(lab, ids[ids > 0]) & ~hole
    sky_add[:y0 - 40] = False
    sky_add[y1 + 2:] = False
    alpha[sky_add] = 0
    # 残留的红边
    redish = (rgb[..., 0] > rgb[..., 1] * 1.6) & (rgb[..., 0] > 0.3)
    box = np.zeros(alpha.shape, bool)
    box[y0 - 4:y1 + 2, x0 - 4:x1 + 9] = True
    alpha[box & redish & ~(np.arange(alpha.shape[1])[None, :] > 1441) ] = 0
    edge = box & redish
    rgb[edge] = rgb[edge][:, [1, 1, 2]] * np.array([1.05, 1.0, 1.0])
    col = cv2.GaussianBlur(rgb[1440:1530].mean(0)[None], (0, 0), 4)[0]
    patch = rgb[1440:1530, 1040:1100]
    grain = patch - cv2.GaussianBlur(patch, (0, 0), 3)
    hgt = y1 - y0
    ys = np.arange(hgt)
    shade = 1 - 0.30 * np.exp(-ys / 4.0) - 0.12 * np.exp(-(hgt - 1 - ys) / 3.0)
    xi = np.arange(x0, x1)
    cover = np.clip(np.minimum(xi + 0.5 - lp, rp - (xi + 0.5)), 0, 1)
    gy = ys[:, None] % grain.shape[0]
    gx = xi[None, :] % grain.shape[1]
    tex = col[None, x0:x1] * shade[:, None, None] + grain[gy, gx]
    rgb[y0:y1, x0:x1] = tex * cover[None, :, None] + rgb[y0:y1, x0:x1] * (1 - cover[None, :, None])
    alpha[y0:y1, x0:x1] = cover[None, :]
    return lp, rp


def _ss(x, a, b):
    t = np.clip((x - a) / (b - a), 0, 1)
    return t * t * (3 - 2 * t)


def _materials(rgb, alpha):
    """材质的软分类：金（尖塔、匾额字、尖顶上的小星）、红（门扇、拱心的红星）、铜（尖塔下的冠部）、
    绿（两翼的铜绿屋顶），其余为石材。另给出明暗 tone（0–1），由亮度除以该材质的典型亮度得到，
    并加上局部对比，让线脚、柱子、窗洞在字里读得出来。"""
    hsv = cv2.cvtColor(np.clip(rgb, 0, 1).astype(np.float32), cv2.COLOR_RGB2HSV)
    H, S, V = hsv[..., 0], hsv[..., 1], hsv[..., 2]
    hd = lambda h0: np.minimum(np.abs(H - h0), 360 - np.abs(H - h0))
    gold = _ss(S, 0.30, 0.46) * _ss(30 - hd(45), 0, 12) * _ss(V, 0.22, 0.38)
    red = _ss(S, 0.35, 0.55) * _ss(25 - hd(5), 0, 10)
    green = _ss(S, 0.08, 0.2) * _ss(45 - hd(165), 0, 15)
    hh, ww = rgb.shape[:2]
    yy, xx = np.mgrid[0:hh, 0:ww].astype(np.float32)
    ax = _AXIS
    crown = ((yy > 806) & (yy < 936) & (np.abs(xx - ax) < 62)).astype(np.float32)
    crown = cv2.GaussianBlur(crown, (0, 0), 1.5)
    cone = ((yy > 140) & (yy <= 806) & (np.abs(xx - ax) < 40)).astype(np.float32)
    gold = np.maximum(gold * (1 - crown), cone)
    red *= (1 - crown) * (1 - gold)
    green *= (1 - crown) * (1 - gold) * (1 - red)
    bronze = crown * (1 - cone)
    Y = rgb @ np.array([0.2126, 0.7152, 0.0722], np.float32)
    solid = alpha > 0.9
    stone_w = np.clip(1 - gold - red - green - bronze, 0, 1)
    refs = {}
    for k, m in (("stone", stone_w), ("gold", gold), ("red", red), ("green", green), ("bronze", bronze)):
        sel = solid & (m > 0.7)
        refs[k] = float(np.median(Y[sel])) if sel.sum() > 50 else 0.4
    ref = (stone_w * refs["stone"] + gold * refs["gold"] + red * refs["red"] + green * refs["green"]
           + bronze * refs["bronze"])
    ref = np.maximum(ref, 0.05)
    b1 = cv2.GaussianBlur(Y, (0, 0), 2.5)
    b2 = cv2.GaussianBlur(Y, (0, 0), 12.0)
    tone = 0.5 + 0.85 * (Y / ref - 1) + 0.9 * (b1 - b2) / ref + 0.7 * (Y - b1) / ref
    tone = _ss(tone, -0.2, 1.2)
    return dict(gold=gold, red=red, green=green, bronze=bronze, tone=tone.astype(np.float32))


def _symmetrize_top(alpha):
    """塔楼上层（冠部以下、塔楼主体顶部以上，原图 y 930–1065、轴线左右 120 像素以内）的抠图左右取平均：
    照片在这里每单位只有约 27 像素，放大六倍后噪点会变成歪斜的团块；建筑本身是左右对称的，
    取平均后小柱、拱洞和尖顶都变得端正。区域四周留出渐变，避免在边界上拼出接缝。"""
    y0, y1 = 930, 1065
    c = int(round(_AXIS - 0.5))                  # 轴线位于像素 c 与 c+1 之间
    hw = 120
    blk = alpha[y0:y1, c - hw + 1:c + hw + 1]
    sym = 0.5 * (blk + blk[:, ::-1])
    ky = np.clip(np.minimum(np.arange(y1 - y0), y1 - y0 - 1 - np.arange(y1 - y0)) / 10.0, 0, 1)[:, None]
    xs = np.abs(np.arange(-hw + 1, hw + 1) - 0.5)
    kx = np.clip((hw - xs) / 15.0, 0, 1)[None, :]
    k = ky * kx
    alpha[y0:y1, c - hw + 1:c + hw + 1] = blk * (1 - k) + sym * k


def _despeckle(alpha):
    """去掉抠图里孤立的小点（面积不超过 4 像素、与建筑不相连）。"""
    lab, n = ndi.label(alpha > 0.15)
    if n == 0:
        return
    sizes = ndi.sum(np.ones_like(alpha), lab, np.arange(1, n + 1))
    small = np.flatnonzero(sizes <= 4) + 1
    alpha[np.isin(lab, small)] = 0


def _photo():
    """读入照片，抠图、校正塔楼位置、填补横幅背后、给出材质。返回原图分辨率（每单位约 27 像素）的各图层，
    坐标已校正（_world_to_px 可直接使用）。"""
    im = cv2.imread(str(PHOTO))[..., ::-1].astype(np.float32) / 255
    model, _ = _sky_model(im)
    alpha, d = _matte(im, model)
    clean = _decontaminate(im, alpha)
    stack = np.dstack([clean, alpha, d])
    stack, kill = _shift_tower(stack)
    stack[kill] = 0
    rgb, alpha = stack[..., :3].copy(), np.clip(stack[..., 3], 0, 1).copy()
    _plinth(rgb, alpha, stack[..., 4] < 0.075)
    _symmetrize_top(alpha)
    _despeckle(alpha)
    out = dict(rgb=rgb.astype(np.float32), alpha=alpha.astype(np.float32))
    out.update(_materials(rgb, alpha))
    return out


def _layers():
    """照片图层（缓存）。"""
    return _cached("photo", _photo)


# ---------------------------------------------------------------------------
# 第二步：字的排布
# ---------------------------------------------------------------------------
LINE = 0.36              # 行距（世界单位）
EM = 0.31                # 字号（1 em 的世界长度）
ADV = EM * 1.02          # 字距
_INK_MID = 0.3625        # 朱雀仿宋字形墨迹的竖直中心在基线以上 0.3625 em

# 五十年代的公开口号与诗词，不含人名，不用报头。顺序固定，塔尖第一行从"中苏友谊万岁"开始。
PHRASES = [
    "中苏友谊万岁", "苏联的今天就是我们的明天", "巩固中苏友谊，保卫世界和平", "东风压倒西风",
    "世界是你们的，也是我们的，但是归根结底是你们的", "你们青年人朝气蓬勃，正在兴旺时期，好像早晨八九点钟的太阳",
    "希望寄托在你们身上", "中苏两国人民的伟大友谊万岁", "学习苏联先进经验", "苏联经济及文化建设成就展览会",
    "全世界无产者联合起来", "四海翻腾云水怒，五洲震荡风雷激", "不管风吹浪打，胜似闲庭信步", "一唱雄鸡天下白",
    "东方红，太阳升", "鼓足干劲，力争上游，多快好省地建设社会主义", "团结就是力量", "中苏友好同盟互助条约",
    "向苏联老大哥学习", "十五年赶上和超过英国", "长夜难明赤县天", "社会主义好",
]


def _stream():
    """无限循环的字流（繁体），句与句之间用句号隔开。"""
    rng = np.random.default_rng(7)
    order = list(range(len(PHRASES)))
    while True:
        for i in order:
            for ch in L.trad(PHRASES[i]) + "。":
                yield ch
        rng.shuffle(order)


# 尖塔顶端的几何（世界单位）：锥身是直线收分的八棱锥，锥顶以上的平台、栏杆、宝珠和细杆由程序重画
_CONE_Y0 = (_Y_CUT - 806.0) / _S         # 锥身下端（冠部上沿）
_CONE_Y1 = (_Y_CUT - 296.0) / _S         # 锥身上端（平台下沿）


def _cone_halfwidth(Y):
    ypx = _Y_CUT - np.asarray(Y) * _S
    return 0.5 * (17.0 + 0.0694 * (ypx - 310.0)) / _S


# 冠部：上下两层向上张开的杯形，杯口一圈叶饰，下面一圈小柱和一道箍。半宽（原图像素）按照片逐行实测、
# 左右取平均后取整理成控制点，用分段三次插值连成光滑的旋转体轮廓。
_CROWN_PTS = [(806, 25.0), (809, 30.0), (813, 36.5), (817, 38.5), (821, 37.6), (833, 32.6), (845, 30.4),
              (850, 31.0), (852.5, 39.5), (856, 45.0), (861, 45.4), (867, 41.5), (877, 36.2), (886, 33.0),
              (896, 32.2), (906, 32.0), (909, 34.0), (912, 36.0), (930, 36.0), (933, 40.0), (937, 42.5)]
_CROWN_Y0 = (_Y_CUT - 937.0) / _S         # 冠部解析轮廓的下端（再往下接照片抠图）
_CROWN_RIMS = (809.0, 851.0)              # 两道杯口（叶饰的根部）


def _crown_halfwidth(Y):
    from scipy.interpolate import PchipInterpolator
    ys = np.array([p[0] for p in _CROWN_PTS])
    hw = np.array([p[1] for p in _CROWN_PTS])
    f = PchipInterpolator(ys, hw, extrapolate=True)
    ypx = np.clip(_Y_CUT - np.asarray(Y) * _S, ys[0], ys[-1])
    return f(ypx) / _S


def _crown_tone(XX, YY):
    """冠部的明暗：照片在这里太糊，直接放大只是一片斑驳。改为逐行取照片中段的平均明暗（保留两层杯身、
    杯口和小柱一圈的上下层次），乘上锥身同样的横向明暗曲线；小柱那一圈另加竖向的明暗条纹。"""
    Pl = _layers()
    ys = np.arange(800, 940, dtype=np.float32)
    Yw = (_Y_CUT - (ys + 0.5)) / _S
    prof = np.zeros(len(ys), np.float32)
    for i, yv in enumerate(Yw):
        hw = float(_crown_halfwidth(yv))
        xs = np.linspace(-0.55 * hw, 0.55 * hw, 15, dtype=np.float32)
        prof[i] = _sample(Pl["tone"], xs, np.array([yv], np.float32))[0].mean()
    prof = np.convolve(np.pad(prof, 2, mode="edge"), np.ones(5) / 5, mode="valid")
    row = np.interp(-YY, -Yw, prof)
    u_prof, t_prof = _cone_profile()
    hw = _crown_halfwidth(YY)
    u = XX / np.maximum(hw, 1e-3)
    shade = np.interp(np.clip(u, -0.95, 0.95), u_prof, t_prof) / max(float(t_prof.mean()), 1e-3)
    ypx = _Y_CUT - YY * _S
    cols = (ypx > 884) & (ypx < 908)
    stripes = 0.75 + 0.25 * np.cos(np.arcsin(np.clip(u, -0.99, 0.99)) * 14)
    t = np.clip(0.15 + 0.85 * row, 0, 1) * shade
    t = np.where(cols, t * stripes, t)
    return np.clip(t, 0, 1)


def _crown_path(region, res):
    """冠部轮廓（含叶尖）的 skia 路径，像素坐标。"""
    x0, y0, x1, y1 = region
    P = lambda x, y: ((x - x0) * res, (y1 - y) * res)
    Ys = np.linspace(_CROWN_Y0, _CONE_Y0 + 0.10, 160)
    hw = _crown_halfwidth(Ys)
    path = skia.Path()
    path.moveTo(*P(-hw[0], Ys[0]))
    for yv, h in zip(Ys[1:], hw[1:]):
        path.lineTo(*P(-h, yv))
    for yv, h in zip(Ys[::-1], hw[::-1]):
        path.lineTo(*P(h, yv))
    path.close()
    # 叶饰：每道杯口的上斜面上露出两片向上、略向外翻的叶子，叶根埋进轮廓里
    for (ya, yb), tips in (((806.0, 817.0), (29.0, 35.0)), ((850.0, 861.0), (36.0, 42.5))):
        ys = np.linspace(ya, yb, 200)
        hws = _crown_halfwidth((_Y_CUT - ys) / _S) * _S
        for side in (-1, 1):
            for xt in tips:
                yb_px = float(np.interp(xt, hws, ys)) + 1.0            # 叶根：轮廓在该半宽处的高度
                yr = (_Y_CUT - yb_px) / _S
                xc = side * xt / _S
                w, h = 2.4 / _S, 5.0 / _S
                lean = side * 1.2 / _S
                leaf = skia.Path()
                leaf.moveTo(*P(xc - w, yr - 1.5 / _S))
                leaf.quadTo(*P(xc - w * 1.05, yr + h * 0.55), *P(xc + lean, yr + h))
                leaf.quadTo(*P(xc + w * 1.05, yr + h * 0.55), *P(xc + w, yr - 1.5 / _S))
                leaf.close()
                path.addPath(leaf)
    return path


def _layout_matte():
    """排字用的轮廓：照片抠图做一次闭运算（填掉栏杆空当这类比字小的缝），尖塔锥身换成解析的轮廓，
    锥顶以上（平台、宝珠、细杆、五角星）不排字。返回原图分辨率的数组。"""
    P = _layers()
    a = (P["alpha"] > 0.5).astype(np.uint8)
    a = cv2.morphologyEx(a, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8)).astype(np.float32)
    hh, ww = a.shape
    yy, xx = np.mgrid[0:hh, 0:ww].astype(np.float32)
    X, Y = _px_to_world(xx + 0.5, yy + 0.5)
    cone = (Y > _CONE_Y0) & (Y < _CONE_Y1)
    a[cone] = (np.abs(X[cone]) < _cone_halfwidth(Y[cone])).astype(np.float32)
    crown = (Y > _CROWN_Y0) & (Y <= _CONE_Y0)
    a[crown] = (np.abs(X[crown]) < _crown_halfwidth(Y[crown])).astype(np.float32)
    a[Y >= _CONE_Y1] = 0
    return a


def _make_layout():
    """逐行排字。行从上往下、每行的连续段从左往右；每段按段宽放下整数个字并两端对齐，
    比一个字还窄的段只在宽度超过 0.55 个字时放一个字（由轮廓裁切）。"""
    m = _layout_matte()
    hh, ww = m.shape
    xs = np.arange(BUILDING["center"][0] - BUILDING["size"][0] / 2,
                   BUILDING["center"][0] + BUILDING["size"][0] / 2, 0.02)
    stream = _stream()
    rng = np.random.default_rng(11)
    chars, gx, gy = [], [], []
    yc = 80.0 - LINE / 2
    while yc > LINE * 0.4:
        inside = np.ones(len(xs), bool)
        for dy in (-0.30 * EM, 0.0, 0.30 * EM):
            px, py = _world_to_px(xs, np.full(len(xs), yc + dy))
            v = cv2.remap(m, (px - 0.5).astype(np.float32)[None], (py - 0.5).astype(np.float32)[None],
                          cv2.INTER_LINEAR)[0]
            inside &= v > 0.5
        d = np.diff(np.r_[0, inside.astype(np.int8), 0])
        starts, ends = np.flatnonzero(d == 1), np.flatnonzero(d == -1)
        for s0, e0 in zip(starts, ends):
            xa, xb = xs[s0], xs[e0 - 1] + 0.02
            w = xb - xa
            if w < 0.55 * ADV:
                continue
            if w < 1.0 * ADV:
                cs = [0.5 * (xa + xb)]
            elif w < 7 * ADV:
                # 窄段（尖塔、角亭、塔楼上层）：放下整数个字，在段内居中
                n = int(np.floor(w / ADV + 0.08))
                cs = list(0.5 * (xa + xb) + (np.arange(n) - (n - 1) / 2) * min(ADV, w / n))
            else:
                # 宽段：每行随机错开字的起点，像砌墙的错缝，避免各行的字上下对齐成网格
                ph = rng.uniform(0, ADV)
                cs = list(np.arange(xa + ph + ADV / 2, xb - ADV / 2 + 1e-6, ADV))
            for c in cs:
                chars.append(next(stream))
                gx.append(c)
                gy.append(yc)
        yc -= LINE
    chars = np.array(chars)
    return dict(chars=chars, x=np.array(gx, np.float32), y=np.array(gy, np.float32), delta=_glyph_delta(chars))


def _glyph_delta(chars):
    """每个字的笔画粗细校正（em）。笔画多的字（蘇、聯）墨多，笔画少的字（一、上）墨少，远看会显出斑驳；
    按每个字的墨量与平均墨量之差除以字的轮廓长度，求出让墨量拉平所需的加粗量，取其七成，限制在 ±0.02 em。"""
    uniq = sorted(set(chars.tolist()))
    px = 96
    f = L.font("fang", 400, px)
    cov, per = {}, {}
    for ch in uniq:
        m = _alpha_mask(px * 2, px * 2, lambda c: c.drawString(ch, px * 0.5, px * 1.4, f,
                                                                skia.Paint(Color=skia.Color4f(1, 1, 1, 1), AntiAlias=True)))
        cov[ch] = m.sum() / (px * px)
        e = (m > 0.5).astype(np.uint8)
        per[ch] = max((e - cv2.erode(e, np.ones((3, 3), np.uint8))).sum() / px, 1.0)    # 轮廓长度（em）
    cbar = np.mean([cov[c] for c in chars.tolist()])
    d = {ch: float(np.clip(0.7 * (cbar - cov[ch]) / per[ch], -0.02, 0.02)) for ch in uniq}
    return np.array([d[c] for c in chars.tolist()], np.float32)


def _layout():
    return _cached("layout", _make_layout)


# ---------------------------------------------------------------------------
# 第三步：按区域、按分辨率画出贴图
# ---------------------------------------------------------------------------
def _grid(region, res):
    """region=(x0, y0, x1, y1) 为建筑坐标的矩形（y 向上）；返回像素中心的世界坐标（列 X，行 Y，第 0 行在顶部）。"""
    x0, y0, x1, y1 = region
    w, h = int(round((x1 - x0) * res)), int(round((y1 - y0) * res))
    X = x0 + (np.arange(w) + 0.5) / res
    Y = y1 - (np.arange(h) + 0.5) / res
    return X.astype(np.float32), Y.astype(np.float32)


def _sample(arr, X, Y, interp=cv2.INTER_LINEAR):
    """在照片图层上按世界坐标取样（arr 为原图分辨率，二维或三维）。"""
    px, py = _world_to_px(X, Y)
    mx = np.broadcast_to((px - 0.5).astype(np.float32)[None, :], (len(Y), len(X)))
    my = np.broadcast_to((py - 0.5).astype(np.float32)[:, None], (len(Y), len(X)))
    mx, my = np.ascontiguousarray(mx), np.ascontiguousarray(my)
    a = arr if arr.ndim == 3 else arr[..., None]
    out = np.dstack([cv2.remap(np.ascontiguousarray(a[..., c]), mx, my, interp, borderMode=cv2.BORDER_CONSTANT,
                               borderValue=0) for c in range(a.shape[2])])
    return out if arr.ndim == 3 else out[..., 0]


def _weight_offset(t):
    """明暗 → 笔画加粗量（em，每侧）：朱雀仿宋的笔画宽约 0.05 em，最暗处细到约 0.025 em，
    最亮处加粗到约 0.13 em。"""
    return -0.012 + 0.052 * t


def _text_coverage(region, res, tone, q=3, strip=256):
    """画出区域内的字并按明暗调整笔画粗细，返回 0–1 的覆盖率（输出分辨率）。

    做法：字先在 q 倍分辨率下用 skia 画出（带抗锯齿），二值化后用距离变换得到有符号距离场，
    边界像素用抗锯齿覆盖率修正到亚像素精度；再按每个像素的明暗把等值线向外或向内移动（加粗或变细），
    最后 q×q 平均缩小。为节省内存按横条处理，横条上下各留一段余量，保证距离场在条带边上也正确。"""
    lay = _layout()
    x0, y0, x1, y1 = region
    X, Y = _grid(region, res)
    H, W = len(Y), len(X)
    out = np.zeros((H, W), np.float32)
    rq = res * q
    font = L.font("fang", 400, EM * rq)
    paint = skia.Paint(Color=skia.Color4f(1, 1, 1, 1), AntiAlias=True)
    em_px = EM * rq
    margin = int(np.ceil(0.12 * em_px)) + 4
    # 只保留落在区域附近的字
    sel = (lay["x"] > x0 - EM) & (lay["x"] < x1 + EM) & (lay["y"] > y0 - LINE) & (lay["y"] < y1 + LINE)
    ch, gx, gy, gd = lay["chars"][sel], lay["x"][sel], lay["y"][sel], lay["delta"][sel]
    bx = (gx - x0) * rq - 0.5 * em_px                    # 字身左端（字宽 1 em）
    by = (y1 - (gy - _INK_MID * EM)) * rq                # 基线
    for r0 in range(0, H, strip):
        r1 = min(H, r0 + strip)
        top = r0 * q - margin
        hq = (r1 - r0) * q + 2 * margin
        surf = skia.Surface(skia.ImageInfo.Make(W * q, hq, skia.kAlpha_8_ColorType, skia.kPremul_AlphaType))
        c = surf.getCanvas()
        c.clear(skia.Color4f(0, 0, 0, 0))
        near = (by > top - em_px * 0.3) & (by < top + hq + em_px * 1.2)
        for k in np.flatnonzero(near):
            c.drawString(str(ch[k]), float(bx[k]), float(by[k] - top), font, paint)
        cov = surf.makeImageSnapshot().toarray(colorType=skia.kAlpha_8_ColorType)
        cov = np.asarray(cov, np.float32).reshape(hq, W * q) / 255.0
        ins = (cov > 0.5).astype(np.uint8)
        din = cv2.distanceTransform(ins, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
        dout = cv2.distanceTransform(1 - ins, cv2.DIST_L2, cv2.DIST_MASK_PRECISE)
        sdf = np.where(ins > 0, 0.5 - din, dout - 0.5)
        edge = (cov > 0.0) & (cov < 1.0) & (np.abs(sdf) <= 1.0)
        sdf = np.where(edge, 0.5 - cov, sdf)
        tq = cv2.resize(tone[r0:r1], (W * q, (r1 - r0) * q), interpolation=cv2.INTER_LINEAR)
        dmap = np.zeros_like(tq)
        cell_w, cell_h = ADV * rq, LINE * rq
        for k in np.flatnonzero(near):
            cxp = bx[k] + 0.5 * em_px
            cyp = (y1 - gy[k]) * rq - r0 * q
            ca, cb = int(max(0, cxp - cell_w / 2)), int(min(W * q, cxp + cell_w / 2))
            ra, rb = int(max(0, cyp - cell_h / 2)), int(min((r1 - r0) * q, cyp + cell_h / 2))
            if cb > ca and rb > ra:
                dmap[ra:rb, ca:cb] = gd[k]
        o = (_weight_offset(tq) + dmap) * em_px
        body = sdf[margin:margin + (r1 - r0) * q]
        cq = np.clip(0.5 - (body - o), 0, 1)
        out[r0:r1] = cq.reshape(r1 - r0, q, W, q).mean((1, 3))
    return out


# 色板：石材用暖白，金色部分用美术字黄，门用褪色红，冠部用墨褐与黄之间的旧铜色，屋顶用灰绿
_PAL = {
    "stone": L.C["warm"] * 0.97,
    "gold": L.C["yellow"],
    "red": L.C["red"],
    "green": np.array([0.56, 0.62, 0.58], np.float32),
    "bronze": L.C["ink"] * 0.3 + L.C["yellow"] * 0.7,
}


def _cone_profile():
    """尖塔锥身横向的明暗曲线（从照片锥身上取样平均），用于重画的平台、栏杆、宝珠和细杆。"""
    P = _layers()
    u = np.linspace(-0.95, 0.95, 39, dtype=np.float32)
    Ys = np.linspace(56, 70, 60, dtype=np.float32)
    acc = np.zeros_like(u)
    for Yv in Ys:
        hw = _cone_halfwidth(Yv)
        acc += _sample(P["tone"], u * hw, np.array([Yv], np.float32))[0]
    acc /= len(Ys)
    return u, acc


def _cyl_shade(u):
    """圆柱面的明暗：u 为 -1（左缘）到 1（右缘）的横坐标。主光来自上方的五角星（偏前），
    辅光来自左前方，左侧偏前处有一道窄的高光。"""
    u = np.clip(u, -0.999, 0.999)
    nz = np.sqrt(1 - u * u)
    key = np.clip(0.6 * nz, 0, None)
    fill = np.clip(-0.6 * u + 0.77 * nz, 0, None)
    spec = np.exp(-((u + 0.38) / 0.13) ** 2)
    return np.clip(0.10 + 0.45 * key + 0.35 * fill + 0.35 * spec, 0, 1)


def _ornaments(region, res):
    """锥顶以上由程序重画的部分：带栏杆的小平台、细杆、宝珠和颈圈，尺寸按照片实测。
    返回覆盖率和明暗；明暗按圆柱面和球面计算（_cyl_shade），栏杆立柱整体压暗，表示在平台的阴影里。"""
    x0, y0, x1, y1 = region
    X, Y = _grid(region, res)
    W, H = len(X), len(Y)
    P = lambda x, y: ((x - x0) * res, (y1 - y) * res)
    paint = skia.Paint(Color=skia.Color4f(1, 1, 1, 1), AntiAlias=True)
    star_c = STAR["center"][1]

    def rect(c, hw, ya, yb):
        (ax, ay), (bx, by) = P(-hw, yb), P(hw, ya)
        c.drawRect(skia.Rect(ax, ay, bx, by), paint)

    bars_x = 0.74 * np.sin(np.linspace(-1.40, 1.40, 17))

    def draw(c):
        path = skia.Path()                                                       # 细杆，向下略粗
        for pt in ((-0.095, star_c), (0.095, star_c), (0.16, 73.70), (-0.16, 73.70)):
            (path.lineTo if path.countPoints() else path.moveTo)(*P(*pt))
        path.close()
        c.drawPath(path, paint)
        rect(c, 0.125, 77.49, 77.62)                                             # 星下的小托
        cx, cy = P(0, 77.10)
        c.drawCircle(cx, cy, 0.23 * res, paint)                                  # 宝珠
        rect(c, 0.17, 76.24, 76.36)                                              # 颈圈
        rect(c, 0.125, 76.36, 76.42)
        rect(c, 0.78, 73.66, 73.72)                                              # 扶手
        rect(c, 0.775, 73.10, 73.13)                                             # 中间横档
        for xb in bars_x:                                                        # 立柱
            (ax, ay), (bx, by) = P(xb - 0.016, 73.67), P(xb + 0.016, 72.60)
            c.drawRect(skia.Rect(ax, ay, bx, by), paint)
        rect(c, 0.80, 72.56, 72.62)                                              # 下扶手
        path = skia.Path()                                                       # 平台外沿与收向锥顶的碗底
        path.moveTo(*P(-0.96, 72.56))
        path.lineTo(*P(0.96, 72.56))
        path.lineTo(*P(0.96, 72.42))
        path.quadTo(*P(0.78, 72.13), *P(0.295, 72.04))
        path.lineTo(*P(-0.295, 72.04))
        path.quadTo(*P(-0.78, 72.13), *P(-0.96, 72.42))
        path.close()
        c.drawPath(path, paint)
    cov = _alpha_mask(W, H, draw)
    # 细杆上竖排一行小字，从颈圈下一直排到平台，与锥身一样由字构成
    mast_em = 0.15
    f = L.font("fang", 400, mast_em * res)
    text = L.trad("中苏友谊万岁") * 3
    pitch = 0.168
    ys = np.arange(76.10 - pitch / 2, 73.80, -pitch)
    pt = skia.Paint(Color=skia.Color4f(1, 1, 1, 1), AntiAlias=True, Style=skia.Paint.kStrokeAndFill_Style,
                    StrokeWidth=0.012 * mast_em * res)

    def draw_text(c):
        for ch, yc in zip(text, ys):
            px, py = P(-0.5 * mast_em, yc - _INK_MID * mast_em)
            c.drawString(ch, px, py, f, pt)
    mast_text = _alpha_mask(W, H, draw_text) * cov
    XX, YY = np.meshgrid(X, Y)
    # 各部件的半宽，用来把横坐标归一化后算圆柱面明暗
    hw = np.full_like(XX, 0.96)
    mast = YY > 73.72
    hw = np.where(mast, 0.095 + 0.065 * (star_c - YY) / (star_c - 73.70), hw)
    hw = np.where((YY > 76.24) & (YY < 76.36), 0.17, hw)
    hw = np.where((YY >= 76.36) & (YY < 76.42), 0.125, hw)
    hw = np.where((YY > 77.49) & (YY < 77.62), 0.125, hw)
    rail = (YY > 72.62) & (YY < 73.66)
    hw = np.where(rail & (np.abs(XX) > 0.17), 0.78, hw)
    bowl = YY < 72.56
    hw = np.where(bowl, 0.295 + (0.96 - 0.295) * np.clip((YY - 72.04) / 0.52, 0, 1) ** 0.6, hw)
    tone = _cyl_shade(XX / np.maximum(hw, 0.03))
    tone = np.where(bowl & (YY < 72.42), tone * (0.55 + 0.45 * (YY - 72.04) / 0.38), tone)   # 碗底朝下，背光
    tone = np.where(rail & (np.abs(XX) > 0.17), tone * 0.7, tone)
    rb = np.hypot(XX, YY - 77.10)
    ball = rb < 0.235
    nzb = np.sqrt(np.clip(1 - (rb / 0.235) ** 2, 0, 1))
    tb = 0.10 + 0.5 * np.clip(0.75 * (YY - 77.10) / 0.235 + 0.66 * nzb, 0, None) \
        + 0.3 * np.clip(-0.6 * XX / 0.235 + 0.77 * nzb, 0, None) \
        + 0.4 * np.exp(-(((XX + 0.08) ** 2 + (YY - 77.18) ** 2) / 0.004))
    tone = np.where(ball, np.clip(tb, 0, 1), tone)
    return cov, np.clip(tone, 0, 1).astype(np.float32), mast_text


def _light(X, Y, gold):
    """夜里的光：冷蓝的环境光（上部略亮、两翼渐暗）加上五角星的暖红光（尖塔与星附近），
    镀金的尖塔反射星光，额外提亮。返回 (H, W, 3)。"""
    XX, YY = np.meshgrid(X, Y)
    amb = np.array([0.33, 0.37, 0.48], np.float32)
    k = (0.78 + 0.30 * YY / 80.0) * (1 - 0.40 * _ss(np.abs(XX), 10.0, 30.0))
    r = np.hypot(XX - STAR["center"][0], YY - STAR["center"][1])
    glow = 0.55 * np.exp(-(r / 4.5) ** 2) + 0.45 * np.exp(-(r / 16.0) ** 2) + 0.14 * np.exp(-(r / 36.0) ** 2)
    light = amb * k[..., None] + np.array([1.0, 0.55, 0.33], np.float32) * glow[..., None]
    light *= (1 + gold * 0.5 * np.exp(-(r / 12.0) ** 2))[..., None]
    return light


def _render(region, res, variant="night", q=3):
    """画出建筑坐标中一个矩形区域的贴图（每单位 res 像素）。"""
    Pl = _layers()
    X, Y = _grid(region, res)
    H, W = len(Y), len(X)
    # 轮廓：照片抠图先轻微平滑，放大后用平滑阶跃收紧边缘，使边缘过渡约为 1.3 个输出像素
    up = res / _S
    a_src = cv2.GaussianBlur(Pl["alpha"], (0, 0), float(np.clip(0.6 + 0.08 * (up - 1.76), 0.6, 0.95)))
    a = np.clip(_sample(a_src, X, Y, cv2.INTER_CUBIC), 0, 1)
    w = float(np.clip(0.5 * 1.3 / (1.6 * up), 0.06, 0.5))
    a = _ss(a, 0.5 - w, 0.5 + w)
    XX, YY = np.meshgrid(X, Y)
    cone = np.clip((_cone_halfwidth(YY) - np.abs(XX)) * res + 0.5, 0, 1)
    in_cone = (YY > _CONE_Y0) & (YY < _CONE_Y1)
    # 冠部（含伸到锥身两侧的叶尖）用解析轮廓；锥身用解析轮廓
    crown_zone = (YY > _CROWN_Y0 - 0.15) & (YY < _CONE_Y0 + 0.45)
    kc = np.zeros_like(YY)
    if crown_zone.any():
        crown = _alpha_mask(W, H, lambda c: c.drawPath(_crown_path(region, res),
                                                       skia.Paint(Color=skia.Color4f(1, 1, 1, 1), AntiAlias=True)))
        kk = _ss(YY, _CROWN_Y0 - 0.15, _CROWN_Y0 + 0.05)
        a = np.where(crown_zone, a * (1 - kk) + crown * kk, a)
        kc = _ss(YY, _CROWN_Y0, _CROWN_Y0 + 0.2) * crown_zone * np.where(YY > _CONE_Y0, 1 - cone, 1)
    a = np.where(in_cone, np.maximum(np.where(crown_zone, a, 0), cone), a)
    top = YY >= _CONE_Y1
    orn, orn_tone, orn_text = _ornaments(region, res)
    a = np.where(top, orn, a)
    tone = np.clip(_sample(Pl["tone"], X, Y, cv2.INTER_CUBIC), 0, 1)
    # 锥身：用沿高度平均的横向明暗曲线（八个棱面的明暗），照片本身的斑驳只留两成
    u_prof, t_prof = _cone_profile()
    tc = np.interp(np.clip(XX / _cone_halfwidth(YY), -0.95, 0.95), u_prof, t_prof)
    k = _ss(YY, _CONE_Y0, _CONE_Y0 + 0.6) * in_cone
    tone = tone * (1 - 0.8 * k) + tc * 0.8 * k
    tone = np.where(top, orn_tone, tone)
    if kc.any():
        tone = tone * (1 - 0.8 * kc) + _crown_tone(XX, YY) * 0.8 * kc
    m = {k: np.clip(_sample(Pl[k], X, Y), 0, 1) for k in ("gold", "red", "green", "bronze")}
    m["gold"] = np.where(top, 1.0, np.maximum(m["gold"], cone * in_cone))
    m["gold"] *= 1 - kc
    m["bronze"] = np.maximum(m["bronze"], kc)
    for k in ("red", "green"):
        m[k] *= 1 - kc
    stone = np.clip(1 - m["gold"] - m["red"] - m["green"] - m["bronze"], 0, 1)
    tcol = stone[..., None] * _PAL["stone"]
    for k in ("gold", "red", "green", "bronze"):
        tcol = tcol + m[k][..., None] * _PAL[k]
    T = _text_coverage(region, res, tone, q=q)
    b = 0.35 + 0.80 * tone
    g = 0.10 + 0.34 * tone ** 2
    g = g + m["gold"] * (0.06 + 0.12 * tone)            # 镀金面反光强，字间的底子也亮一些
    shade = g + (b - g) * T
    orn_shade = 0.18 + 0.72 * tone
    orn_shade = orn_shade * (1 - 0.45 * (YY > 73.72)) + orn_text * (0.25 + 0.75 * tone)   # 细杆：底子压暗，字亮
    shade = np.where(top, orn_shade, shade)
    alb = np.clip(tcol * shade[..., None], 0, 1)
    if variant == "night":
        rgb = alb * _light(X, Y, m["gold"])
    elif variant == "albedo":
        rgb = alb
    else:
        raise ValueError(variant)
    return np.dstack([rgb, a]).astype(np.float32)


_memo = {}


def _tex(name, fn):
    """贴图缓存：进程内只算一次、多次调用返回同一个数组（引擎按对象身份缓存纹理）；
    磁盘上以半精度 .npy 存在 data/cache/seg_c/，下次导入时直接读取。"""
    if name in _memo:
        return _memo[name]
    p = _cache_path(name + ".npy")
    if p.exists():
        arr = np.load(p).astype(np.float32)
    else:
        L.low_priority()
        arr = fn().astype(np.float32)
        np.save(p, arr.astype(np.float16))
    _memo[name] = arr
    return arr


def _rect(d):
    (cx, cy), (w, h) = d["center"], d["size"]
    return (cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2)


def building_rgba(variant="night", cut_top=False):
    """建筑本体贴图（每单位 RES_BUILDING 像素），位置与尺寸见 BUILDING。variant 取 "night" 或 "albedo"。
    cut_top=True 时把 SPIRE_TOP 范围内、渐变带以上的部分挖空，与 spire_top_rgba() 叠用时避免两张贴图
    在轮廓边缘重叠出一圈较软的边。"""
    if variant not in ("night", "albedo"):
        raise ValueError(variant)
    arr = _tex(f"building_{variant}", lambda: _render(_rect(BUILDING), RES_BUILDING, variant))
    if not cut_top:
        return arr
    key = f"building_{variant}_cut"
    if key not in _memo:
        out = arr.copy()
        X, Y = _grid(_rect(BUILDING), RES_BUILDING)
        x0, y0, x1, y1 = _rect(SPIRE_TOP)
        cols = (X >= x0) & (X <= x1)
        rows = Y > y0 + SPIRE_FEATHER
        out[np.ix_(rows, cols, [3])] = 0
        _memo[key] = out
    return _memo[key]


def building_region_rgba(region, res, variant="night"):
    """把建筑坐标里的矩形 region = (x0, y0, x1, y1) 按每单位 res 像素重新画出（同一套字的排布，与
    building_rgba 逐像素对齐）。用于镜头贴近立面的段落，结果缓存在磁盘上。"""
    if variant not in ("night", "albedo"):
        raise ValueError(variant)
    r = tuple(round(float(v), 3) for v in region)
    key = f"region_{variant}_{int(res)}_" + "_".join(f"{v:g}" for v in r)
    return _tex(key, lambda: _render(r, res, variant, q=2 if res >= 100 else 3))


SPIRE_FEATHER = 1.0      # 塔尖贴图下沿的渐变带（世界单位），与建筑本体在这一段交叠过渡


def spire_top_rgba(variant="night"):
    """塔尖高分辨率贴图（每单位 RES_SPIRE 像素），位置与尺寸见 SPIRE_TOP，与建筑本体逐像素对齐
    （同一套字的排布，只是分辨率更高）。下沿 SPIRE_FEATHER 一段的 alpha 从 0 渐变到 1，叠在建筑本体上看不出接缝。"""
    if variant not in ("night", "albedo"):
        raise ValueError(variant)

    def make():
        reg = _rect(SPIRE_TOP)
        arr = _render(reg, RES_SPIRE, variant, q=2)
        _, Y = _grid(reg, RES_SPIRE)
        arr[..., 3] *= _ss(Y, reg[1], reg[1] + SPIRE_FEATHER)[:, None]
        return arr
    return _tex(f"spire_top_{variant}", make)


# ---------------------------------------------------------------------------
# 五角星
# ---------------------------------------------------------------------------
def _star_geom(R):
    ang_tip = np.deg2rad(90 + 72 * np.arange(5))
    ang_in = ang_tip + np.deg2rad(36)
    ri = R * 0.40
    tips = np.stack([np.cos(ang_tip), np.sin(ang_tip)], 1) * R
    inner = np.stack([np.cos(ang_in), np.sin(ang_in)], 1) * ri
    outline = np.empty((10, 2))
    outline[0::2], outline[1::2] = tips, inner
    return tips, inner, outline


def _alpha_mask(N, M, draw):
    surf = skia.Surface(skia.ImageInfo.Make(N, M, skia.kAlpha_8_ColorType, skia.kPremul_AlphaType))
    c = surf.getCanvas()
    c.clear(skia.Color4f(0, 0, 0, 0))
    draw(c)
    return np.asarray(surf.makeImageSnapshot().toarray(colorType=skia.kAlpha_8_ColorType), np.float32) \
        .reshape(M, N) / 255


def _make_star():
    """苏式红宝石星：五个角各分成左右两个棱面，按左上方来的光分出明暗；红色玻璃自己发光，
    中心最亮（数值超过 1）；金色的外框和十条棱线；星的背后是一圈细的金色放射线（照片上看得到）；
    外面是贴着星的一圈红光。另做一张大而柔的外圈光晕。"""
    from scipy.ndimage import gaussian_filter
    R = _STAR_R
    res = RES_STAR
    size = STAR["size"][0]
    N = int(round(size * res))
    c0 = N / 2
    P = lambda x, y: (c0 + x * res, c0 - y * res)
    tips, inner, outline = _star_geom(R)

    def star_path(scale=1.0):
        path = skia.Path()
        path.moveTo(*P(*(outline[0] * scale)))
        for q in outline[1:]:
            path.lineTo(*P(*(q * scale)))
        path.close()
        return path

    fill = skia.Paint(Color=skia.Color4f(1, 1, 1, 1), AntiAlias=True)
    body = _alpha_mask(N, N, lambda c: c.drawPath(star_path(), fill))
    stroke = skia.Paint(Color=skia.Color4f(1, 1, 1, 1), AntiAlias=True, Style=skia.Paint.kStroke_Style,
                        StrokeWidth=0.075 * R * res, StrokeJoin=skia.Paint.kMiter_Join)
    frame = _alpha_mask(N, N, lambda c: c.drawPath(star_path(), stroke))

    def ridges(c):
        p = skia.Paint(Color=skia.Color4f(1, 1, 1, 1), AntiAlias=True, Style=skia.Paint.kStroke_Style,
                       StrokeWidth=0.028 * R * res, StrokeCap=skia.Paint.kRound_Cap)
        for t in tips:
            c.drawLine(*P(0, 0), *P(*(t * 0.94)), p)
        p.setStrokeWidth(0.018 * R * res)
        for q in inner:
            c.drawLine(*P(0, 0), *P(*q), p)
    ridge = _alpha_mask(N, N, ridges)

    def rays(c):
        p = skia.Paint(Color=skia.Color4f(1, 1, 1, 1), AntiAlias=True, Style=skia.Paint.kStroke_Style,
                       StrokeWidth=0.016 * R * res, StrokeCap=skia.Paint.kRound_Cap)
        for a in np.deg2rad(np.arange(0, 360, 4.0) + 2.0):
            r1 = R * (1.02 + 0.10 * (np.cos(5 * (a - np.pi / 2)) * 0.5 + 0.5))
            c.drawLine(*P(0.45 * R * np.cos(a), 0.45 * R * np.sin(a)), *P(r1 * np.cos(a), r1 * np.sin(a)), p)
    ray = _alpha_mask(N, N, rays) * (1 - body)

    yy, xx = np.mgrid[0:N, 0:N].astype(np.float32)
    X, Y = (xx + 0.5 - c0) / res, (c0 - yy - 0.5) / res
    phi = np.arctan2(Y, X)
    r = np.hypot(X, Y)
    # 棱面：从每个角尖的方向起，每 36 度一个面；面的朝向取该面的中线方向，光从左上方来
    sector = np.floor(((phi - np.pi / 2) % (2 * np.pi)) / np.deg2rad(36)).astype(int)
    mid = np.pi / 2 + (sector + 0.5) * np.deg2rad(36)
    lx, ly = -0.55, 0.83
    lam = 0.5 + 0.5 * (np.cos(mid) * lx + np.sin(mid) * ly)
    lam = np.where(sector % 2 == 0, lam, lam * 0.82)          # 每个角的一侧略暗，棱线更清楚
    facet = 0.50 + 0.80 * lam
    glass = np.array([1.40, 0.13, 0.07], np.float32) * facet[..., None]
    glass += np.array([0.75, 0.20, 0.09], np.float32) * np.exp(-(r / (0.38 * R)) ** 2)[..., None]
    glass *= (1 + 0.06 * (L.fbm(N, N, 0.25 * R * res, 3, 21) - 0.5))[..., None]
    gold = np.array([1.25, 0.86, 0.38], np.float32) * (0.75 + 0.45 * lam)[..., None]
    gold_m = np.clip(frame + ridge, 0, 1) * body
    col = glass * (1 - gold_m[..., None]) + gold * gold_m[..., None]
    ray_col = np.array([0.85, 0.47, 0.22], np.float32)
    ray_a = ray * 0.55 * _ss(r, 0.5 * R, 0.62 * R)
    # 贴着星的红光（窗函数保证在贴图边缘降到零）
    g1 = gaussian_filter(body, 0.22 * R * res)
    g2 = gaussian_filter(body, 0.70 * R * res)
    win = _ss(size / 2 - np.maximum(np.abs(X), np.abs(Y)), 0.0, 0.9)
    glow = np.array([1.0, 0.22, 0.10], np.float32) * ((1.0 * g1 + 0.5 * g2) * win)[..., None]
    ga = np.clip(glow.max(-1), 0, 1)
    gcol = glow / np.maximum(ga, 1e-4)[..., None]
    # 叠合（预乘）：星体 over 放射线 over 红光
    pb, ab = col * body[..., None], body
    pr, ar = ray_col * ray_a[..., None], ray_a
    pg, ag = gcol * ga[..., None], ga
    P1 = pr + pg * (1 - ar)[..., None]
    A1 = ar + ag * (1 - ar)
    Pt = pb + P1 * (1 - ab)[..., None]
    At = ab + A1 * (1 - ab)
    star = np.dstack([Pt / np.maximum(At, 1e-5)[..., None], At]).astype(np.float32)
    Pb = pb + pr * (1 - ab)[..., None]
    Ab = ab + ar * (1 - ab)
    body_only = np.dstack([Pb / np.maximum(Ab, 1e-5)[..., None], Ab]).astype(np.float32)
    # 外圈光晕：低分辨率、大范围，供 add 混合
    gs = STAR_GLOW["size"][0]
    M = int(round(gs * RES_GLOW))
    gy, gx = np.mgrid[0:M, 0:M].astype(np.float32)
    rr = np.hypot((gx + 0.5 - M / 2) / RES_GLOW, (M / 2 - gy - 0.5) / RES_GLOW)
    halo = 0.55 * np.exp(-(rr / (1.6 * R)) ** 2) + 0.22 * np.exp(-(rr / (4.0 * R)) ** 2) \
        + 0.06 * np.exp(-(rr / (9.0 * R)) ** 2)
    halo *= _ss(gs / 2 - rr, 0.0, 2.5)
    hcol = np.array([1.0, 0.36, 0.14], np.float32)
    outer = np.dstack([np.broadcast_to(hcol, (M, M, 3)), np.clip(halo, 0, 1)]).astype(np.float32)
    return dict(star=star, body=body_only, glow=outer)


def _star_layers():
    return _cached("star", _make_star)


def star_rgba(part="all"):
    """五角星贴图，0–1 浮点 RGBA（直通 alpha，发光部分超过 1），位置与尺寸见 STAR。
    part="all"：星体、背后的放射线和贴着星的一圈红光；part="body"：只有星体和放射线；
    part="glow"：外圈的大光晕（位置与尺寸见 STAR_GLOW），建议用 blend="add" 叠加。"""
    key = {"all": "star", "body": "body", "glow": "glow"}[part]
    if ("star", key) not in _memo:
        _memo[("star", key)] = _star_layers()[key].astype(np.float32)
    return _memo[("star", key)]


# ---------------------------------------------------------------------------
# 横幅
# ---------------------------------------------------------------------------
BANNER_TEXT = "中苏友谊万岁"
_TIES = 7                 # 横幅上沿的系绳点数（两角加中间五处）


def _banner_geometry():
    """横幅的褶皱高度场（世界单位）与轮廓。横幅上沿在七处系在塔基上，系点之间的布略往下垂，
    从系点向下散开几道斜褶；布身有竖向的松弛褶皱，越往下越松；再加细碎的皱纹。"""
    Wb, Hb = BANNER["size"]
    res = RES_BANNER
    W, H = int(round(Wb * res)), int(round(Hb * res))
    rng = np.random.default_rng(5)
    x = (np.arange(W) + 0.5) / res
    y = (np.arange(H) + 0.5) / res                     # 自上而下
    XX, YY = np.meshgrid(x, y)
    env = 0.35 + 0.65 * (YY / Hb)
    # 竖向的松弛褶皱：用一维噪声做出疏密不匀的褶，再按高度略微倾斜
    from scipy.ndimage import gaussian_filter1d
    xe = np.arange(W + 2 * H) / res
    h = np.zeros((H, W), np.float32)
    for sig, amp in ((1.0, 0.085), (0.35, 0.02)):
        nz = gaussian_filter1d(rng.normal(0, 1, len(xe)), sig * res)
        nz /= nz.std() + 1e-9
        drift = rng.uniform(-0.18, 0.18)
        idx = np.clip((XX + drift * YY) * res + H, 0, len(xe) - 1).astype(int)
        h += amp * nz[idx] * env
    ties = np.linspace(0.12, Wb - 0.12, _TIES)
    for xt in ties:
        dx, dy = XX - xt, YY + 0.12
        d = np.hypot(dx, dy)
        th = np.arctan2(dx, dy)
        h += 0.035 * np.exp(-d / 1.3) * np.cos(6 * th + rng.uniform(0, 6.28)) * _ss(d, 0.05, 0.35)
    h += 0.012 * (L.fbm(H, W, 0.35 * res, 4, 31) - 0.5)
    spacing = ties[1] - ties[0]
    sag = 0.05 * np.sin(np.pi * np.clip((x - ties[0]) / spacing % 1.0, 0, 1)) ** 2
    bottom = Hb - 0.025 - 0.018 * np.sin(2 * np.pi * x / 2.3 + 1.0) - 0.01 * np.sin(2 * np.pi * x / 0.9)
    top_px, bot_px = sag * res, bottom * res
    yy = np.arange(H)[:, None] + 0.5
    alpha = np.clip(yy - top_px[None, :], 0, 1) * np.clip(bot_px[None, :] - yy, 0, 1)
    return dict(h=h, alpha=alpha.astype(np.float32), res=res)


def _make_banner():
    """褪色红布上的美术字黄宋体美术字。布的明暗由褶皱高度场按左上方来的光算出，褶谷略暗；
    布面有日晒褪色（上部和成片的区域发白发粉）、雨水冲下的竖向污痕、下沿的积灰，以及上下两道卷边和缝线。
    字用思源宋体最粗字重，稍压扁（横向放宽到 1.12 倍），漆面有细小的剥落和不匀，跟着布一起起伏。"""
    from scipy.ndimage import gaussian_filter
    G = _banner_geometry()
    h, alpha, res = G["h"], G["alpha"], G["res"]
    H, W = h.shape
    Wb, Hb = BANNER["size"]
    # 明暗
    gy, gx = np.gradient(h, 1.0 / res)
    n = np.dstack([-gx, -gy, np.ones_like(h)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    Lv = np.array([-0.35, -0.55, 1.0])
    Lv /= np.linalg.norm(Lv)
    shade = (n @ Lv) / Lv[2]
    cav = h - gaussian_filter(h, 0.35 * res)
    shade = np.clip(shade * (1 + 3.0 * cav), 0.45, 1.35)
    # 布色
    yy = (np.arange(H)[:, None] + 0.5) / res * np.ones((1, W))
    fade = np.clip(0.10 + 0.35 * L.fbm(H, W, 1.6 * res, 3, 41) + 0.18 * (1 - yy / Hb) ** 2, 0, 0.7)
    red = L.C["red"]
    pale = np.array([0.84, 0.52, 0.42], np.float32)
    cloth = red * (1 - fade[..., None] * 0.55) + pale * (fade[..., None] * 0.55)
    streak = gaussian_filter(np.random.default_rng(3).normal(0, 1, (H, W)).astype(np.float32), (0.9 * res, 0.12 * res))
    streak = np.clip(streak / (streak.std() + 1e-6) * 0.5 + 0.5, 0, 1) ** 2
    cloth *= (1 - 0.14 * streak * (0.3 + 0.7 * yy / Hb))[..., None]
    cloth *= (1 - 0.12 * _ss(yy, Hb * 0.8, Hb))[..., None]
    weave = np.random.default_rng(4).normal(0, 1, (H, W)).astype(np.float32)
    weave = 0.6 * gaussian_filter(weave, 0.6) + 0.4 * gaussian_filter(weave, (0.6, 2.5))
    cloth *= (1 + 0.05 * weave / (weave.std() + 1e-6))[..., None]
    # 卷边与缝线
    hem = 0.10
    top_edge = np.argmax(alpha > 0.5, axis=0)[None, :] / res
    dist_top = yy - top_edge
    dist_bot = Hb - 0.03 - yy
    hem_m = np.maximum(_ss(hem - dist_top, -0.01, 0.01), _ss(hem - dist_bot, -0.01, 0.01))
    cloth *= (1 - 0.08 * hem_m)[..., None]
    xx = (np.arange(W)[None, :] + 0.5) / res * np.ones((H, 1))
    dash = (np.mod(xx, 0.10) < 0.06).astype(np.float32)
    stitch = (np.exp(-((dist_top - 0.075) * res / 1.2) ** 2) + np.exp(-((dist_bot - 0.075) * res / 1.2) ** 2)) * dash
    cloth *= (1 - 0.22 * np.clip(stitch, 0, 1))[..., None]
    # 字
    text = L.trad(BANNER_TEXT)
    em = 2.0 * res
    f = L.font("serif", 900, em, scale_x=1.12)
    surf = skia.Surface(skia.ImageInfo.Make(W, H, skia.kAlpha_8_ColorType, skia.kPremul_AlphaType))
    c = surf.getCanvas()
    c.clear(skia.Color4f(0, 0, 0, 0))
    tops, bots = [], []
    for ch in text:
        b = skia.Rect()
        f.measureText(ch, bounds=b)
        tops.append(b.top())
        bots.append(b.bottom())
    base = H * 0.5 - (min(tops) + max(bots)) / 2
    paint = skia.Paint(Color=skia.Color4f(1, 1, 1, 1), AntiAlias=True)
    for i, ch in enumerate(text):
        b = skia.Rect()
        f.measureText(ch, bounds=b)
        cx = W * (i + 0.5) / len(text)
        c.drawString(ch, float(cx - (b.left() + b.right()) / 2), float(base), f, paint)
    glyph = np.asarray(surf.makeImageSnapshot().toarray(colorType=skia.kAlpha_8_ColorType), np.float32).reshape(H, W) / 255
    rough = L.fbm(H, W, 6, 3, 51)
    paint_m = np.clip((gaussian_filter(glyph, 1.2) - 0.5 + (rough - 0.5) * 0.35) * 5 + 0.5, 0, 1)
    flake = L.fbm(H, W, 22, 4, 52)
    cracks = L.fbm(H, W, 9, 3, 53)
    paint_m *= np.clip((0.80 - flake) * 12, 0, 1) * np.clip((0.86 - cracks) * 14, 0, 1)
    paint_m *= 0.82 + 0.18 * L.fbm(H, W, 120, 3, 54)
    yel = L.C["yellow"]
    pale_y = np.array([0.93, 0.84, 0.58], np.float32)
    paint_col = yel * (1 - fade[..., None] * 0.5) + pale_y * (fade[..., None] * 0.5)
    alb = cloth * (1 - paint_m[..., None]) + paint_col * paint_m[..., None]
    alb = np.clip(alb * shade[..., None], 0, 1)
    return dict(albedo=alb.astype(np.float32), alpha=alpha.astype(np.float32))


def _banner_layers():
    return _cached("banner", _make_banner)


def _banner_light():
    Wb, Hb = BANNER["size"]
    cx, cy = BANNER["center"]
    X, Y = _grid((cx - Wb / 2, cy - Hb / 2, cx + Wb / 2, cy + Hb / 2), RES_BANNER)
    return _light(X, Y, np.zeros((len(Y), len(X)), np.float32))


def banner_rgba(variant="night"):
    """横幅贴图，0–1 浮点 RGBA（直通 alpha），位置与尺寸见 BANNER。variant 取 "night"（按夜色打好光）
    或 "albedo"（只有布本身的颜色和褶皱明暗，不带夜里的光）。"""
    if variant not in ("night", "albedo"):
        raise ValueError(variant)
    if ("banner", variant) not in _memo:
        B = _banner_layers()
        rgb = B["albedo"] * _banner_light() * 1.2 if variant == "night" else B["albedo"]
        _memo[("banner", variant)] = np.dstack([rgb, B["alpha"]]).astype(np.float32)
    return _memo[("banner", variant)]


# ---------------------------------------------------------------------------
# 横幅碎块
# ---------------------------------------------------------------------------
_CRACK_ORIGIN = (0.5, 0.46)     # 裂纹起点（横幅贴图的 0–1 坐标，v 向下）


def _poisson(Wb, Hb, origin, scale, rng):
    """变半径的泊松圆盘采样：半径在裂纹起点处最小，向两端线性增大，所以中间碎得细、两端块大。"""
    ox, oy = origin
    r_of = lambda p: scale * (0.42 + 0.20 * np.hypot((p[0] - ox), (p[1] - oy) * 1.5))
    pts = [np.array([ox + 0.05, oy])]
    fails = 0
    while fails < 3000:
        p = np.array([rng.uniform(0, Wb), rng.uniform(0, Hb)])
        rp = r_of(p)
        ok = True
        for q in pts:
            if np.hypot(*(p - q)) < 0.5 * (rp + r_of(q)):
                ok = False
                break
        if ok:
            pts.append(p)
            fails = 0
        else:
            fails += 1
    return np.array(pts)


def _make_shards(n, seed):
    """维诺图分块。种子点按变半径泊松圆盘采样（半径缩放用二分法调到块数接近 n），
    每块是一个点的维诺区域裁到横幅矩形内；相邻两块共用的边细分成几段并加上垂直方向的抖动，
    两侧取同一条折线，所以碎块严丝合缝；横幅外缘保持直边。"""
    from scipy.spatial import Voronoi
    Wb, Hb = BANNER["size"]
    origin = (_CRACK_ORIGIN[0] * Wb, _CRACK_ORIGIN[1] * Hb)
    lo, hi = 0.3, 6.0
    pts = None
    for _ in range(18):
        mid = (lo * hi) ** 0.5
        p = _poisson(Wb, Hb, origin, mid, np.random.default_rng(seed))
        if pts is None or abs(len(p) - n) < abs(len(pts) - n):
            pts = p
        if len(p) > n:
            lo = mid
        elif len(p) < n:
            hi = mid
        else:
            break
    m = len(pts)
    mir = [pts, pts * [-1, 1], pts * [-1, 1] + [2 * Wb, 0], pts * [1, -1], pts * [1, -1] + [0, 2 * Hb]]
    vor = Voronoi(np.vstack(mir))
    V = vor.vertices
    # 内部共享边：两侧都是原始点 → 细分加抖动
    edge_pl = {}
    for (i, j), rv in zip(vor.ridge_points, vor.ridge_vertices):
        if i >= m or j >= m or -1 in rv:
            continue
        va, vb = rv
        A, B = V[va], V[vb]
        L_ = np.hypot(*(B - A))
        k = max(2, int(L_ / 0.22))
        t = np.linspace(0, 1, k + 1)
        nrm = np.array([-(B - A)[1], (B - A)[0]]) / max(L_, 1e-9)
        r = np.random.default_rng(hash((min(va, vb), max(va, vb), seed)) % (2 ** 32))
        off = r.normal(0, 0.045, k + 1) * np.sin(np.pi * t) * min(1.0, L_ / 0.5)
        off[0] = off[-1] = 0
        pl = A[None] + t[:, None] * (B - A)[None] + off[:, None] * nrm[None]
        edge_pl[(va, vb)] = pl
        edge_pl[(vb, va)] = pl[::-1]
    shards = []
    for i in range(m):
        reg = vor.regions[vor.point_region[i]]
        if -1 in reg or len(reg) < 3:
            continue
        poly = []
        for a, b in zip(reg, reg[1:] + reg[:1]):
            pl = edge_pl.get((a, b))
            if pl is None:
                poly.append(V[a])
            else:
                poly.extend(pl[:-1])
        poly = np.array(poly)
        poly[:, 0] = np.clip(poly[:, 0], 0, Wb)
        poly[:, 1] = np.clip(poly[:, 1], 0, Hb)
        # 统一为顺时针（屏幕坐标，v 向下时为顺时针）
        area = 0.5 * np.sum(poly[:, 0] * np.roll(poly[:, 1], -1) - np.roll(poly[:, 0], -1) * poly[:, 1])
        if area < 0:
            poly = poly[::-1]
        shards.append(poly)
    return shards, origin


def _poly_centroid(poly):
    x, y = poly[:, 0], poly[:, 1]
    cr = x * np.roll(y, -1) - np.roll(x, -1) * y
    a = cr.sum() / 2
    return np.array([((x + np.roll(x, -1)) * cr).sum() / (6 * a), ((y + np.roll(y, -1)) * cr).sum() / (6 * a)])


def banner_shards(n=40, seed=0, variant="night"):
    """横幅碎块。返回列表，每项为 dict：
    poly：(K, 2) 多边形，横幅贴图的 0–1 坐标（u 向右，v 向下）；
    centroid：多边形面积重心 (u, v)；bbox：(u0, v0, u1, v1)；
    rgba：按 bbox 裁出的贴图（直通 alpha，块外透明），平面应放在 bbox 的中心、尺寸为 bbox 对应的世界尺寸；
    t0：裂纹从起点扩展到这一块的时刻（0–1，按块上离起点最近的点到起点的距离归一化），可用来错开各块脱落的先后；
    center、size：这块贴图在建筑坐标系里的中心与尺寸（与 BANNER 同一平面）。
    variant 同 banner_rgba。"""
    key = f"shards_{n}_{seed}"
    p = _cache_path(key + ".npz")
    if p.exists():
        z = np.load(p, allow_pickle=False)
        polys = [z[f"poly{i}"] for i in range(int(z["count"]))]
        origin = tuple(z["origin"])
    else:
        polys, origin = _make_shards(n, seed)
        np.savez(p, count=len(polys), origin=np.array(origin), **{f"poly{i}": q for i, q in enumerate(polys)})
    Wb, Hb = BANNER["size"]
    bcx, bcy = BANNER["center"]
    tex = banner_rgba(variant)
    H, W = tex.shape[:2]
    res = RES_BANNER
    dmax = max(np.hypot(*(np.array(c) - origin)) for c in ((0, 0), (Wb, 0), (0, Hb), (Wb, Hb)))
    out = []
    for poly in polys:
        u0, v0 = poly.min(0)
        u1, v1 = poly.max(0)
        c0, r0 = max(0, int(np.floor(u0 * res)) - 1), max(0, int(np.floor(v0 * res)) - 1)
        c1, r1 = min(W, int(np.ceil(u1 * res)) + 1), min(H, int(np.ceil(v1 * res)) + 1)
        w, h = c1 - c0, r1 - r0

        def draw(c):
            path = skia.Path()
            path.moveTo(poly[0, 0] * res - c0, poly[0, 1] * res - r0)
            for q in poly[1:]:
                path.lineTo(q[0] * res - c0, q[1] * res - r0)
            path.close()
            c.drawPath(path, skia.Paint(Color=skia.Color4f(1, 1, 1, 1), AntiAlias=True))
        mk = _alpha_mask(w, h, draw)
        crop = tex[r0:r1, c0:c1].copy()
        # 断口：离多边形内部边（不在横幅外缘上）1.5 像素以内的布略微发亮，像断开的纤维
        inner = ndi.distance_transform_edt(mk > 0.5)
        gy_, gx_ = np.mgrid[r0:r1, c0:c1]
        far = np.minimum(np.minimum(gx_, W - 1 - gx_), np.minimum(gy_ - 8, H - 1 - gy_)) > 4
        fray = np.clip(1 - inner / 2.0, 0, 1) * (mk > 0) * far
        crop[..., :3] *= (1 + 0.18 * fray)[..., None]
        crop[..., 3] *= mk
        uu = np.array([c0, r0, c1, r1], float) / [W, H, W, H]
        dmin = min(np.hypot(*(q - origin)) for q in poly)
        cen = _poly_centroid(poly)
        cw = ((uu[0] + uu[2]) / 2 - 0.5) * Wb + bcx
        ch = (0.5 - (uu[1] + uu[3]) / 2) * Hb + bcy
        out.append(dict(poly=np.column_stack([poly[:, 0] / Wb, poly[:, 1] / Hb]),
                        centroid=(cen[0] / Wb, cen[1] / Hb),
                        bbox=tuple(uu), rgba=crop.astype(np.float32),
                        t0=float(np.clip(dmin / dmax, 0, 1)),
                        center=(cw, ch), size=((uu[2] - uu[0]) * Wb, (uu[3] - uu[1]) * Hb)))
    return out


def banner_cracks(n=40, seed=0):
    """碎裂之前的裂纹：与 banner_shards(n, seed) 的碎块边界一致。返回 dict(lines=覆盖率, time=到达时刻)，
    都是横幅贴图的分辨率；time 为 0–1（裂纹前沿从起点扩展到该像素的时刻），不在裂纹上的像素为 2。
    某一进度 p 下应显示的裂纹为 lines * (time <= p)，可乘到横幅贴图上（裂纹处压暗）。"""
    shards = banner_shards(n, seed)
    Wb, Hb = BANNER["size"]
    res = RES_BANNER
    W, H = int(round(Wb * res)), int(round(Hb * res))

    def draw(c):
        p = skia.Paint(Color=skia.Color4f(1, 1, 1, 1), AntiAlias=True, Style=skia.Paint.kStroke_Style,
                       StrokeWidth=1.8, StrokeJoin=skia.Paint.kRound_Join)
        for s in shards:
            q = s["poly"] * [W, H]
            path = skia.Path()
            path.moveTo(*q[0])
            for v in q[1:]:
                path.lineTo(*v)
            path.close()
            c.drawPath(path, p)
    lines = _alpha_mask(W, H, draw)
    lines[:2] = lines[-2:] = 0
    lines[:, :2] = lines[:, -2:] = 0
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    ox, oy = _CRACK_ORIGIN[0] * W, _CRACK_ORIGIN[1] * H
    d = np.hypot(xx - ox, yy - oy)
    t = d / d.max()
    return dict(lines=lines, time=np.where(lines > 0, t, 2.0).astype(np.float32))
