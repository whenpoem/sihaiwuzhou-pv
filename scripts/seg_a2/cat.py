"""L02 末尾走进角落的猫：Muybridge《Animal Locomotion》第 716 号图版（1887，公有领域）的墨色剪影动画。

图版是 4 行 × 6 格的连续照片，一只虎斑猫从左往右走，第一行 6 格是行走，第二行起渐渐伏低、转成奔跑。这里取
第一行的 6 格做行走，第二行前几格做最后冲进角落的一蹿（"走路，转成奔跑"正是这张图版的题目）。每一格先用
YOLO 的分割模型（COCO 的"猫"类）求出猫的轮廓，再用灰度阈值补上分割漏掉的细尾巴和爪子，去掉背景网格线。
各格按身体（不含四肢和尾巴的躯干）对齐，这样猫在原地迈步，前进的距离由场景按步频另加，脚掌不会打滑。

剪影存成与钢笔字相同格式的墨迹数据贴图（有向距离、书写时间、浓淡），由 a2_ink 材质画在纸上，边缘一样沿纸
纤维洇开，看起来是用同一支笔的墨画的。动画按每秒 12 张切换，是手绘动画的节奏。
"""
import sys
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import strokes as ST  # noqa: E402

SRC = ROOT / "assets" / "images" / "Muybridge_Eadweard_-_Gehende_Katze_wechselt_zum_Galopp_0_31_.jpg"
YOLO = ROOT / "assets" / "models" / "yolo26s-seg.pt"     # Ultralytics YOLO26 分割模型
CACHE = ROOT / "data" / "cache" / "seg_a2"
VERSION = 6
COLS, ROWS = 6, 4


def cells():
    """把图版切成 24 格：返回 [(行, 列, 灰度图 0–1)]。格子的边界按每行、每列的暗色分隔带确定。"""
    im = np.asarray(Image.open(SRC).convert("L"), np.float32) / 255.0
    h, w = im.shape
    # 分隔带是接近黑色的粗条：按行、列的平均亮度找低谷
    rowm = im.mean(1)
    colm = im.mean(0)
    def bands(m, n, size):
        dark = m < 0.35
        lab, k = ndimage.label(dark)
        cuts = [0]
        for j in range(1, k + 1):
            idx = np.flatnonzero(lab == j)
            if 0 < idx.mean() < size - 1:
                cuts.append(int(idx.mean()))
        cuts.append(size)
        cuts = sorted(set(cuts))
        return cuts
    rc = bands(rowm, ROWS, h)
    cc = bands(colm, COLS, w)
    return im, rc, cc


XS = [(36, 544), (556, 1060), (1080, 1580), (1594, 2100), (2114, 2624), (2640, 3160)]   # 各列的范围（像素）
YS = [(20, 410), (415, 798)]                                                             # 第一、二行
UP = 2                                                                                   # 分割时放大的倍数


def _yolo_masks():
    from ultralytics import YOLO as Y
    model = Y(str(YOLO))
    im = Image.open(SRC).convert("RGB")
    out = {}
    for r, (y0, y1) in enumerate(YS):
        for c, (x0, x1) in enumerate(XS):
            big = im.crop((x0, y0, x1, y1)).resize(((x1 - x0) * UP, (y1 - y0) * UP), Image.LANCZOS)
            res = model.predict(np.asarray(big)[:, :, ::-1], imgsz=1024, conf=0.10, retina_masks=True, verbose=False)[0]
            best = None
            if res.masks is not None:
                for k in range(len(res.boxes)):
                    if res.names[int(res.boxes.cls[k])] not in ("cat", "dog"):
                        continue
                    m = res.masks.data[k].cpu().numpy()
                    if best is None or m.sum() > best.sum():
                        best = m
            out[(r, c)] = best if best is not None else np.zeros((big.height, big.width), np.float32)
    return out


# 第一行 6 格里 YOLO 和阈值都抓不全的猫头：照图版逐格描出的头部轮廓（坐标为格内以 (330, 80) 为原点、
# 未放大的像素）。头的浅色脸颊与背景几乎同色，只能手工描。
HEADS = {
    0: [(68, 78), (96, 60), (112, 49), (110, 66), (118, 74), (126, 92), (131, 108), (124, 118), (112, 121), (100, 116), (85, 108), (68, 100)],
    1: [(88, 76), (115, 60), (130, 50), (128, 67), (136, 76), (144, 95), (149, 110), (140, 119), (128, 121), (115, 116), (100, 110), (88, 104)],
    2: [(80, 78), (107, 62), (118, 52), (117, 68), (124, 76), (130, 95), (135, 112), (127, 121), (115, 123), (103, 117), (90, 110), (80, 104)],
    3: [(75, 85), (95, 66), (108, 59), (112, 64), (123, 56), (122, 72), (130, 82), (138, 98), (142, 113), (133, 122), (120, 124), (105, 118), (88, 110), (75, 106)],
    4: [(83, 88), (95, 68), (102, 62), (112, 70), (127, 57), (126, 73), (134, 84), (141, 100), (146, 115), (138, 124), (124, 126), (110, 120), (95, 112), (83, 108)],
    5: [(92, 95), (98, 72), (103, 63), (115, 70), (128, 72), (140, 58), (138, 76), (145, 88), (152, 102), (158, 115), (150, 124), (137, 126), (122, 121), (105, 114), (92, 110)],
}


def silhouette(r, c, yolo):
    """一格里猫的剪影（放大 UP 倍后的像素，0–1）。以 YOLO 的轮廓为确定前景、向外扩出的一圈为可能前景，
    用 GrabCut 按灰度、纹理和平滑后的灰度三个特征分割；第一行的头部再并上手工描的轮廓。最后用比网格线宽、
    比腿细的圆盘做开运算削掉连在身上的网格线，补洞，取最大的连通块。"""
    import cv2
    from scipy.ndimage import binary_dilation, binary_erosion, binary_fill_holes, binary_opening, binary_closing,         label, gaussian_filter, uniform_filter
    im = Image.open(SRC).convert("L")
    x0, x1 = XS[c]
    y0, y1 = YS[r]
    g = np.asarray(im.crop((x0, y0, x1, y1)).resize(((x1 - x0) * UP, (y1 - y0) * UP), Image.LANCZOS), np.float32) / 255
    ym = yolo > 0.5
    mu = uniform_filter(g, 9)
    sd = np.sqrt(np.clip(uniform_filter(g * g, 9) - mu * mu, 0, None))
    mask = np.full(g.shape, cv2.GC_BGD, np.uint8)
    roi = binary_dilation(ym, iterations=80)
    mask[roi] = cv2.GC_PR_BGD
    mask[roi & ((sd > 0.06) | (gaussian_filter(g, 2) < 0.55))] = cv2.GC_PR_FGD
    mask[binary_erosion(ym, iterations=6)] = cv2.GC_FGD
    head = np.zeros(g.shape, bool)
    if r == 0 and c in HEADS:
        import skia
        sfc = skia.Surface.MakeRasterN32Premul(g.shape[1], g.shape[0])
        cv = sfc.getCanvas()
        cv.clear(skia.Color4f(0, 0, 0, 0))
        path = skia.Path()
        pts = [((330 + px) * UP, (80 + py) * UP) for px, py in HEADS[c]]
        path.addPoly([skia.Point(*q) for q in pts], True)
        cv.drawPath(path, skia.Paint(AntiAlias=True, Color=skia.Color4f(1, 1, 1, 1)))
        head = sfc.makeImageSnapshot().toarray(colorType=skia.kRGBA_8888_ColorType)[..., 3] > 127
        mask[head] = cv2.GC_FGD
    bgd, fgd = np.zeros((1, 65)), np.zeros((1, 65))
    feat = np.dstack([g * 255, sd * 255 * 3, gaussian_filter(g, 3) * 255]).clip(0, 255).astype(np.uint8)
    cv2.grabCut(feat, mask, None, bgd, fgd, 6, cv2.GC_INIT_WITH_MASK)
    m = (mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD) | head
    yy, xx = np.mgrid[-5:6, -5:6]
    disk = (xx * xx + yy * yy) <= 20
    m = binary_opening(m, structure=disk) | head
    m = binary_fill_holes(binary_closing(m, structure=disk))
    # 背景网格的粗竖线：在原格里找出大半截都是暗色的列；这些列上，剪影只有一条窄缝那么宽的部分是线，不是猫
    dark_cols = np.flatnonzero((g < 0.45).mean(0) > 0.45)
    for cx in dark_cols:
        for yy_ in np.flatnonzero(m[:, cx]):
            row = m[yy_]
            a_ = cx
            while a_ > 0 and row[a_ - 1]:
                a_ -= 1
            b_ = cx
            while b_ < len(row) - 1 and row[b_ + 1]:
                b_ += 1
            if b_ - a_ < 18:
                m[yy_, a_:b_ + 1] = False
    lab, n = label(m)
    if n > 1:
        sizes = np.bincount(lab.ravel())
        sizes[0] = 0
        m = lab == np.argmax(sizes)
    # 残留的网格竖线：比 8 像素窄、又竖得很长的部分去掉（尾巴比它粗，保留）
    thin = m & ~binary_opening(m, structure=np.ones((1, 9), bool))
    lab_t, nt = label(thin)
    for j in range(1, nt + 1):
        ys_, xs_ = np.nonzero(lab_t == j)
        if np.ptp(ys_) > 6 * max(np.ptp(xs_), 1):
            m[lab_t == j] = False
    lab, n = label(m)
    if n > 1:
        sizes = np.bincount(lab.ravel())
        sizes[0] = 0
        m = lab == np.argmax(sizes)
    return gaussian_filter(m.astype(np.float32), 1.2)


def masks():
    """12 格剪影（第一行行走、第二行转成奔跑），存盘缓存。返回 dict[(行, 列)] -> 0–1 数组。"""
    p = CACHE / f"cat_v{VERSION}_masks.npz"
    if p.exists():
        z = np.load(p)
        return {(int(k[1]), int(k[2])): z[k].astype(np.float32) / 255 for k in z.files}
    yolo = _yolo_masks()
    out = {k: silhouette(k[0], k[1], v) for k, v in yolo.items()}
    CACHE.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(p, **{f"m{r}{c}": (v * 255).astype(np.uint8) for (r, c), v in out.items()})
    return out


FRAMES = [(0, c) for c in range(6)] + [(1, 0), (1, 1), (1, 2), (1, 3)]    # 行走 6 格 + 转成奔跑的 4 格
BOX_H = 1.45          # 猫贴图的高度（以猫站立时的肩高为 1）
BOX_W = 3.40


def aligned():
    """各格剪影按躯干对齐、脚底落在同一条地平线上：返回 (剪影列表, 每格躯干的原始位置 (x, y)，像素/放大后)。
    躯干位置取剪影中间一段（去掉腿和尾巴）的形心。"""
    ms = masks()
    out, pos = [], []
    for k in FRAMES:
        m = ms[k]
        ys, xs = np.nonzero(m > 0.5)
        top, bot = ys.min(), ys.max()
        band = (ys > top + 0.25 * (bot - top)) & (ys < top + 0.60 * (bot - top))
        xb = xs[band]
        lo, hi = np.percentile(xb, 20), np.percentile(xb, 95)
        sel = band & (xs >= lo) & (xs <= hi)
        pos.append((float(xs[sel].mean()), float(bot)))
        out.append(m)
    return out, pos


def ink_frames(ppe_h=420):
    """猫的墨迹数据贴图（与 strokes.ink_tex_data 同格式：R = 2 + 10·有向距离，单位为"猫高"，G 为书写时间，
    恒为 0，B 为浓淡）。贴图宽 BOX_W、高 BOX_H 个猫高，躯干形心在贴图水平中点，脚底在离下沿 0.08 处。
    返回 (贴图列表, 猫高对应的放大后像素数)。"""
    p = CACHE / f"cat_v{VERSION}_ink3_{ppe_h}.npz"
    if p.exists():
        z = np.load(p)
        return [z[f"f{i}"].astype(np.float32) for i in range(len(FRAMES))], float(z["unit"])
    ms, pos = aligned()
    # 猫高：第一格的肩高（躯干形心到脚底的距离的 1.6 倍，近似背线高度）
    unit = float(np.median([b - masks()[k][:, :].nonzero()[0].min() for k, (x, b) in zip(FRAMES, pos)]))
    W, H = int(BOX_W * ppe_h), int(BOX_H * ppe_h)
    s = ppe_h / unit
    frames = []
    for m, (cx, by) in zip(ms, pos):
        # 平移缩放到贴图坐标：躯干形心 → (W/2, ·)，脚底 → H − 0.08·ppe_h
        from scipy.ndimage import affine_transform, distance_transform_edt
        oy = by - (H - 0.08 * ppe_h) / s
        ox = cx - (W / 2) / s
        cov = affine_transform(m, [1 / s, 1 / s], offset=[oy, ox], output_shape=(H, W), order=1)
        inside = cov >= 0.5
        sdf = np.where(inside, distance_transform_edt(inside) - 0.5, -(distance_transform_edt(~inside) - 0.5))
        edge = (cov > 0) & (cov < 1)
        sdf[edge] = cov[edge] - 0.5
        sdf = sdf / ppe_h                                   # 单位：猫高
        R = 2.0 + 10.0 * np.clip(sdf, -0.15, 0.15)
        # 出墨量取 0.8（剪影是一笔一笔填满的浓墨），没有飞白
        frames.append(np.dstack([R, np.zeros_like(R), np.full_like(R, 0.8), np.zeros_like(R)]).astype(np.float32))
    np.savez_compressed(p, unit=unit, **{f"f{i}": f.astype(np.float16) for i, f in enumerate(frames)})
    return frames, unit


if __name__ == "__main__":
    fr, unit = ink_frames()
    strip = np.concatenate([np.clip((f[..., 0] - 2.0) * 50, 0, 1) for f in fr], 1)
    Image.fromarray(((1 - strip) * 255).astype(np.uint8)).resize((strip.shape[1] // 3, strip.shape[0] // 3)).save(
        CACHE / "cat_ink_strip.png")
    ms = masks()
    tiles = []
    for r in range(2):
        for c in range(6):
            m = ms[(r, c)]
            tiles.append(Image.fromarray(((1 - m) * 255).astype(np.uint8)).resize((m.shape[1] // 4, m.shape[0] // 4)))
    W, H = tiles[0].size
    sh = Image.new("L", (W * 6, H * 2), 255)
    for i, t in enumerate(tiles):
        sh.paste(t.resize((W, H)), ((i % 6) * W, (i // 6) * H))
    sh.save(CACHE / "cat_masks_preview.png")
