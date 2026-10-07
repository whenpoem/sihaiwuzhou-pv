"""尾段：五个"快"冲破五层，"动物永不停下来"时奔涌的板与字，冲进阳光之前的那一段。

五层依次是锁孔与夜里的水、报纸字栏的海、标语墙、云与被单、城市灯光，是前面各段画面倒过来的顺序，越冲越近
今天。每层是一整幅画面大小的平面，放在镜头前进的路上（层的高度见 LAYER_Z，镜头在每个"快"之后 0.1 秒穿过
那一层）。层的画面读 renders/layers/{名字}.png（3840×2160，由间奏二的 make_layers.py 从各段渲染），文件
还不存在时读 data/cache/seg_h/layer_{名字}.png（placeholders.py 生成的占位）；文件更新后按修改时间自动换上。

层的摆放。每层有一个主体（锁孔、红帆、标语、被单、烧屏的楼），层的位置让主体正对镜头前进的方向，镜头始终朝
它冲过去；层的大小取开始看得见时画面的 1.15 倍以上，并保证以主体为中心的那一幅画面不露出层的边。层按那时
镜头的滚转角摆正，所以在屏幕上是正的。

冲破的做法。"快"字是一块漆着暖白宋体字的板，在"快"的元音起点砸到层上；砸中的那一点是裂开的起点。层预先
切成以这一点为圆心、一圈圈、一瓣瓣的碎块（在极坐标里撒种子点再求沃罗诺伊分区，碎块因此是放射状的楔形，
像玻璃或灰墙被砸碎），碎块贴图打包成一张图集。裂纹沿碎块的边由近及远出现，各块按到起点的距离依次脱落
（每秒 160 单位向外推进），层上脱落的部分在着色器里挖掉，同一块碎片作为粒子飞出：先绕靠近起点的那条边
翻起，再向外散开、翻滚，大致跟着镜头一起前进。层与层之间悬着红色的旧字"一萬年太久　只爭朝夕"，分成四段，
随每个"快"闪现。
"""
import math

import numpy as np
from PIL import Image
from scipy.ndimage import distance_transform_edt, gaussian_filter

from common import CACHE, LAYERS, T, cached, key_of, look, smooth, RED, WARM, rot_axes, rot_x, euler_from_matrix
from engine import Particles, Plane, Tex, TextPlane, register_material
from engine.text import Atlas

NAMES = ["keyhole", "newspaper", "wall", "sheets", "city"]
# 每层的主体在画面上的位置（0–1，u 向右、v 向下）
FOCUS = [(0.70, 0.70), (0.48, 0.42), (0.50, 0.58), (0.48, 0.55), (0.52, 0.62)]
KUAI = [T(37, i) for i in range(5)]
PASS = 0.10                                         # "快"之后多久镜头穿过这一层
LAYER_Z = [400.0, 372.0, 346.0, 300.0, 255.0]       # 与 scene.Z_KEYS 一致
REVEAL = [177.90] + KUAI[:4]                        # 每层开始看得见的时刻（第一层在旋风里淡入）
SCREEN_X = [0.38, 0.44, 0.50, 0.56, 0.62]           # 五个"快"砸在屏幕上的横向位置：从左往右
V_TEAR = 160.0
OLD = [look.trad(s) for s in ("一万年", "太久", "只争", "朝夕")]
K = 1.866

register_material("h_shatter", """
uniform sampler2D tbmap;
uniform float t0;
vec4 material(vec4 base) {
    vec3 m = texture(tbmap, v_uv01).rgb;
    float never = step(0.995, m.r);
    float tb = m.r * 0.5;
    float dt = u_time - t0;
    if (never < 0.5 && dt >= tb) return vec4(0.0);
    // 脱落前 40 毫秒，裂纹沿碎块的边出现：细缝发暗，缝边被挤起、略亮
    float pre = clamp((dt - (tb - 0.04)) / 0.04, 0.0, 1.0) * (1.0 - never) * step(0.0, dt + 0.005);
    float line = 1.0 - smoothstep(0.0, 0.22, m.g);
    float lip = smoothstep(0.15, 0.3, m.g) * (1.0 - smoothstep(0.3, 0.55, m.g));
    vec3 rgb = base.rgb * (1.0 - 0.92 * line * pre) + base.a * vec3(0.16, 0.15, 0.13) * lip * pre;
    return vec4(rgb, base.a);
}
""", defaults={"t0": 0.0})


# ---------------------------------------------------------------- 层的位置与大小

def cam_dist(t, cam_state_fn, i):
    x, y, H, roll = cam_state_fn(t)
    return H * K - LAYER_Z[i], roll


def layer_geom(i, cam_state_fn):
    """第 i 层的 (中心 x, y, z, 宽, 高, 滚转角, 撞击点 u, v)。"""
    def make():
        dist, roll = cam_dist(REVEAL[i], cam_state_fn, i)
        F = dist / K                                      # 开始看得见时的画面高
        uf, vf = FOCUS[i]
        w = max(F * 16 / 9 * 0.5 / min(uf, 1 - uf), F * 16 / 9 * 1.15) * 1.08
        h = max(w * 9 / 16, F * 0.5 / min(vf, 1 - vf) * 1.08)
        w = h * 16 / 9
        lx, ly = (uf - 0.5) * w, (0.5 - vf) * h          # 主体相对层中心的位置
        r = math.radians(roll)
        cx = -(lx * math.cos(r) - ly * math.sin(r))
        cy = -(lx * math.sin(r) + ly * math.cos(r))
        # 撞击点：砸下时画面上 SCREEN_X 的位置（与画面下方"快快快快快"的字序一致）
        d_hit, _ = cam_dist(KUAI[i], cam_state_fn, i)
        Fw = d_hit / K * 16 / 9
        iu = uf + (SCREEN_X[i] - 0.5) * Fw / w
        iv = vf + 0.02 * math.sin(i * 2.1)
        return (cx, cy, LAYER_Z[i], w, h, roll, iu, iv)
    return cached(f"lgeom:{i}", make)


def _to_world(u, v, g):
    cx, cy, z, w, h, roll = g[:6]
    lx, ly = (u - 0.5) * w, (0.5 - v) * h
    r = math.radians(roll)
    return cx + lx * math.cos(r) - ly * math.sin(r), cy + lx * math.sin(r) + ly * math.cos(r)


# ---------------------------------------------------------------- 层的画面与碎块

def layer_path(name):
    p = LAYERS / f"{name}.png"
    return p if p.exists() else CACHE / f"layer_{name}.png"


def layer_data(i, g):
    """第 i 层：(画面 Tex, 碎块数据 dict)。碎块数据按画面文件的修改时间与撞击点缓存到磁盘。"""
    name = NAMES[i]
    path = layer_path(name)
    st = path.stat()
    iu, iv = g[6], g[7]
    key = key_of(name, str(path), st.st_mtime_ns, st.st_size, round(iu, 4), round(iv, 4), round(g[4], 3), "v3")

    def make():
        img = np.asarray(Image.open(path).convert("RGB").resize((3840, 2160), Image.LANCZOS))
        f = CACHE / f"shards_{name}_{key}.npz"
        if f.exists():
            z = np.load(f)
            sh = {k: z[k] for k in z.files}
        else:
            sh = _shards(img, iu, iv, g[4], 100 + i)
            np.savez_compressed(f, **sh)
        return Tex(img), sh
    return cached(f"layer:{key}", make)


def _shards(img, iu, iv, h_world, seed):
    """以撞击点为圆心切碎块：在极坐标里撒种子点（半径按等比增长，越近越密），求沃罗诺伊分区。
    返回图集（RGBA uint8）、每块在图集里的 uv、每块在画面上的 0–1 外接框、每块到撞击点的距离（世界单位）、
    分区图与边界距离。"""
    from scipy.spatial import cKDTree
    from scipy import ndimage
    rng = np.random.default_rng(seed)
    H, W = 1080, 1920
    cx, cy = iu * W, iv * H
    px_per_unit = H / h_world
    sites = []
    r = 0.22 * px_per_unit                                 # 最内一圈约 0.22 单位
    while r < 2.6 * W:
        n = max(5, int(2 * math.pi * r / (r * 0.55)))        # 每圈的瓣数：碎块长宽比约 1:1.3
        a0 = rng.uniform(0, 2 * math.pi)
        for k in range(n):
            a = a0 + 2 * math.pi * (k + rng.uniform(-0.3, 0.3)) / n
            rr = r * rng.uniform(0.85, 1.15)
            sites.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
        r *= 1.42
    sites = np.array(sites)
    keep = (sites[:, 0] > -0.3 * W) & (sites[:, 0] < 1.3 * W) & (sites[:, 1] > -0.3 * H) & (sites[:, 1] < 1.3 * H)
    sites = np.r_[[[cx, cy]], sites[keep]]
    yy, xx = np.mgrid[0:H, 0:W]
    jx = gaussian_filter(rng.normal(0, 1, (H // 4 + 2, W // 4 + 2)), 1.5)
    jy = gaussian_filter(rng.normal(0, 1, (H // 4 + 2, W // 4 + 2)), 1.5)
    jx = np.kron(jx / (jx.std() + 1e-6), np.ones((4, 4)))[:H, :W] * 4
    jy = np.kron(jy / (jy.std() + 1e-6), np.ones((4, 4)))[:H, :W] * 4
    _, lab = cKDTree(sites).query(np.c_[(xx + jx).ravel(), (yy + jy).ravel()])
    lab = lab.reshape(H, W).astype(np.int32)
    n = len(sites)
    cnt = np.bincount(lab.ravel(), minlength=n)
    mx = np.bincount(lab.ravel(), xx.ravel(), n) / np.maximum(cnt, 1)
    my = np.bincount(lab.ravel(), yy.ravel(), n) / np.maximum(cnt, 1)
    dist = np.hypot(mx - cx, my - cy) / px_per_unit
    border = np.zeros((H, W), bool)
    border[:, 1:] |= lab[:, 1:] != lab[:, :-1]
    border[1:, :] |= lab[1:, :] != lab[:-1, :]
    bd = distance_transform_edt(~border)
    S = 128
    cols = int(math.ceil(math.sqrt(n)))
    rows = int(math.ceil(n / cols))
    atlas = np.zeros((rows * S, cols * S, 4), np.uint8)
    rects = np.zeros((n, 4), np.float32)
    boxes = np.zeros((n, 4), np.float32)
    objs = ndimage.find_objects(lab + 1)
    for k in range(n):
        sl = objs[k] if k < len(objs) else None
        if sl is None or cnt[k] == 0:
            continue
        y0, y1, x0, x1 = sl[0].start, sl[0].stop, sl[1].start, sl[1].stop
        boxes[k] = (x0 / W, y0 / H, x1 / W, y1 / H)
        m = (lab[y0:y1, x0:x1] == k).astype(np.uint8) * 255
        crop = img[y0 * 2:y1 * 2, x0 * 2:x1 * 2]
        mm = np.asarray(Image.fromarray(m).resize((crop.shape[1], crop.shape[0]), Image.BILINEAR))
        hh, ww = crop.shape[:2]
        sc = min(S / ww, S / hh)
        nw, nh = max(1, int(ww * sc)), max(1, int(hh * sc))
        r_, c_ = divmod(k, cols)
        atlas[r_ * S:r_ * S + nh, c_ * S:c_ * S + nw, :3] = np.asarray(Image.fromarray(crop).resize((nw, nh), Image.LANCZOS))
        atlas[r_ * S:r_ * S + nh, c_ * S:c_ * S + nw, 3] = np.asarray(Image.fromarray(mm).resize((nw, nh), Image.BILINEAR))
        rects[k] = ((c_ * S + 0.5) / atlas.shape[1], (r_ * S + 0.5) / atlas.shape[0],
                    (c_ * S + nw - 0.5) / atlas.shape[1], (r_ * S + nh - 0.5) / atlas.shape[0])
    return {"atlas": atlas, "rects": rects, "boxes": boxes, "dist": dist.astype(np.float32), "lab": lab,
            "bd": bd.astype(np.float32), "cnt": cnt}


def tbmap(i, g):
    """第 i 层的脱落时刻图（RGB uint8，1920×1080）：R = 脱落时刻偏移 / 0.5 秒（1 表示不脱落），
    G = 离碎块边界的距离（像素 / 6）。同时返回每块的脱落时刻偏移（秒）。"""
    tex, sh = layer_data(i, g)

    def make():
        tb = sh["dist"] / V_TEAR
        tb = np.where((tb < 0.49) & (sh["cnt"] > 0), tb, 9.0)
        R = np.clip(tb / 0.5, 0, 1)[sh["lab"]]
        G = np.clip(sh["bd"] / 6.0, 0, 1)
        img = (np.dstack([R, G, np.zeros_like(R)]) * 255 + 0.5).astype(np.uint8)
        return Tex(img, mipmap=False), tb
    return cached(f"tbmap:{i}:{id(sh)}", make)


def shard_atlas(i, g):
    tex, sh = layer_data(i, g)

    def make():
        n = len(sh["rects"])
        return Atlas(sh["atlas"], {k: tuple(sh["rects"][k]) for k in range(n)}, list(range(n)))
    return cached(f"shardatlas:{i}:{id(sh)}", make)


# ---------------------------------------------------------------- "快"字板

def kuai_tex():
    """暖白粗宋体的"快"，四周一圈柔和的暗影，在亮的层（被单）上也读得清。"""
    def make():
        import skia
        n = 512
        s = skia.Surface(n, n)
        c = s.getCanvas()
        f = look.font("serif", 850, n * 0.74)
        b = skia.Rect()
        f.measureText("快", bounds=b)
        x, y = (n - b.width()) / 2 - b.left(), (n - b.height()) / 2 - b.top()
        c.drawString("快", x, y, f, skia.Paint(Color=skia.ColorWHITE, AntiAlias=True))
        a = s.makeImageSnapshot().toarray()[..., 3].astype(np.float32) / 255
        sh = np.clip(gaussian_filter(a, 14) * 1.7, 0, 1)
        col = np.array(WARM) * 1.12
        rgb = col[None, None] * a[..., None] + np.array([0.035, 0.028, 0.022]) * (1 - a[..., None])
        alpha = np.maximum(a, sh * 0.7)
        return Tex(np.dstack([rgb, alpha]).astype(np.float32))
    return cached("kuai_tex", make)


# ---------------------------------------------------------------- 组装

def layer_items(t, cam_state_fn):
    items = []
    for i in range(5):
        if t < REVEAL[i] - 0.05 or t > KUAI[i] + PASS + 0.6:
            continue
        g = layer_geom(i, cam_state_fn)
        cx, cy, z, w, h, roll = g[:6]
        tex, sh = layer_data(i, g)
        tbm, tb = tbmap(i, g)
        op = 1.0 if i > 0 else float(smooth(t, REVEAL[0] - 0.05, REVEAL[0] + 0.12))
        if t < KUAI[i] + PASS + 0.02:
            items.append(Plane(tex, center=(cx, cy, z), size=(w, h), rot=(0, 0, roll), group="past",
                               material="h_shatter", uniforms={"tbmap": tbm, "t0": KUAI[i]}, opacity=op, bias=0.5))
        items += shard_items(t, i, g, sh, tb)
        items += kuai_items(t, i, g, cam_state_fn)
    items += old_text_items(t, cam_state_fn)
    return items


def shard_items(t, i, g, sh, tb):
    """已经脱落的碎块：先绕靠近撞击点的那条边翻起，再向外散开、翻滚，大致随镜头一起前进。"""
    dt = t - KUAI[i]
    gone = (tb < 9.0) & (dt >= tb)
    if not gone.any():
        return []
    k = np.flatnonzero(gone)
    u = dt - tb[k]
    cx, cy, z, w, h, roll, iu, iv = g
    bx = sh["boxes"][k]
    uc, vc = (bx[:, 0] + bx[:, 2]) / 2, (bx[:, 1] + bx[:, 3]) / 2
    sw, shh = (bx[:, 2] - bx[:, 0]) * w, (bx[:, 3] - bx[:, 1]) * h
    rng = np.random.default_rng(500 + i)
    nall = len(sh["boxes"])
    rv = rng.uniform(0.6, 1.4, nall)[k]
    vz = rng.uniform(70.0, 125.0, nall)[k]
    spin = rng.normal(0, 6.0, (nall, 3))[k]
    r = math.radians(roll)
    lx, ly = (uc - 0.5) * w, (0.5 - vc) * h
    ix, iy = (iu - 0.5) * w, (0.5 - iv) * h
    dx, dy = lx - ix, ly - iy
    dn = np.hypot(dx, dy) + 1e-3
    out = (5.0 + 12.0 * rv) * (1.0 + dn / 6.0)
    px = lx + dx / dn * out * u
    py = ly + dy / dn * out * u
    wx = cx + px * math.cos(r) - py * math.sin(r)
    wy = cy + px * math.sin(r) + py * math.cos(r)
    wz = z + vz * u + 0.5 * 150.0 * u * u
    # 绕切向的轴翻起（轴垂直于从撞击点指向碎块的方向），外侧朝镜头掀起；之后再随机翻滚。
    # R = Rz(β)·Rx(θ)·Rz(r − β)，β 为切向角：先随层转 r，再绕切向轴转 θ
    alpha = np.arctan2(dy, dx) + r
    beta = alpha + np.pi / 2
    theta = -(np.minimum(u / 0.12, 1.0) * 1.7 + np.abs(spin[:, 0]) * np.clip(u - 0.1, 0, None))
    Rz1 = rot_axes(np.zeros(len(k)), np.zeros(len(k)), beta)
    Rx_ = rot_x(theta)
    Rz2 = rot_axes(np.zeros(len(k)), np.zeros(len(k)), r - beta + spin[:, 2] * u * 0.5)
    Rm = np.einsum("nij,njk->nik", np.einsum("nij,njk->nik", Rz1, Rx_), Rz2)
    ang = euler_from_matrix(Rm)
    pos = np.c_[wx, wy, wz].astype(np.float32)
    at = shard_atlas(i, g)
    uv = sh["rects"][k].copy()
    fade = np.clip(1.0 - (u - 0.5) / 0.2, 0, 1)
    col = np.c_[np.ones((len(k), 3)), fade].astype(np.float32)
    back = np.c_[np.ones((len(k), 3)) * np.array([0.10, 0.085, 0.075]), fade].astype(np.float32)
    return [Particles(at, pos, np.c_[sw, shh].astype(np.float32), ang, color=col, back=back, uv=uv, group="past",
                      bias=-0.5)]


def kuai_items(t, i, g, cam_state_fn):
    """"快"字板：在"快"的元音起点前 50 毫秒从镜头这边砸下来，压进层里；层碎开后随碎片飞向镜头。
    字高取砸下时画面高的 0.36。"""
    tk = KUAI[i]
    if t < tk - 0.05:
        return []
    cx, cy, z, w, h, roll, iu, iv = g
    x, y = _to_world(iu, iv, g)
    d_hit, _ = cam_dist(tk, cam_state_fn, i)
    size = d_hit / K * 0.36
    u = t - tk
    if u < 0:
        a = (u + 0.05) / 0.05
        zz = z + d_hit * 0.5 * (1 - a) ** 2 + 0.03
        s = 1.0
        op = min(1.0, a * 2.0)
    else:
        uu = max(u - 0.035, 0.0)
        zz = z + 0.03 + 60.0 * uu + 0.5 * 260.0 * uu * uu
        s = 1.0 - 0.07 * math.exp(-u / 0.025) * math.sin(u * 70.0 + 0.5)
        op = 1.0
    tilt = 0.0 if u < 0.035 else (u - 0.035) * 200.0
    return [Plane(kuai_tex(), center=(x, y, zz), size=(size * s, size * s), rot=(tilt * 0.35, -tilt, roll),
                  opacity=op, group="past", bias=-1.0)]


def old_text_items(t, cam_state_fn):
    """层与层之间的红色旧字：每个"快"砸下、层碎开时，下一层前面闪现一段（一萬年、太久、只爭、朝夕），
    像压在这一层底下的字；镜头冲过去时它迅速变大，大到占半个画面之前淡去。"""
    items = []
    for i, s in enumerate(OLD):
        if t < KUAI[i] - 0.01 or t > KUAI[i + 1]:
            continue
        g = layer_geom(i + 1, cam_state_fn)
        zt = LAYER_Z[i + 1] + 4.0
        x, y, H, roll = cam_state_fn(t)
        dist = H * K - zt
        d0 = cam_state_fn(KUAI[i] + 0.02)[2] * K - zt
        h = d0 / K * 0.20                                  # 出现时约占画面高的 0.2
        frac = h / max(dist / K, 1e-3)                     # 此刻占画面高的比例
        a = float(smooth(t, KUAI[i] - 0.01, KUAI[i] + 0.04)) * (1 - float(smooth(frac, 0.3, 0.5)))
        if a <= 0.01:
            continue
        ox, oy = _to_world(g[6], g[7] - 0.10, g)            # 撞击点上方一点
        items.append(TextPlane(s, kind="sans", weight=900, height=h, color=tuple(RED * 1.3), center=(ox, oy, zt),
                               rot=(0, 0, g[5]), tracking=0.1, opacity=a, group="past", bias=-0.2))
    return items
