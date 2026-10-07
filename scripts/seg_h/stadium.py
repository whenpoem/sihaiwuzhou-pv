"""翻板场四周的体育场：水泥看台、照明灯塔、灯光在空气里的光束、看台外的地面和远处的夜空。

镜头在桥段里会压低、斜看，所以四周的东西都按三维搭出来，而不是画在地面上。

看台。环绕跑道一周，内沿离跑道外沿 3 个单位，先是一道 1.8 高的挡墙，墙顶往外是 28 级台阶，水平进深 45、
升高 22。看台的平面图是圆角矩形，直边各是一整块斜面，转角由 12 条窄斜面拼成扇形，每条用梯形遮罩裁齐，
拼缝不留空隙。台阶是在着色器里画的：每一级的踏面朝上、立面朝场地，各按自己的法线受光，光来自与翻板相同的
四盏照明灯（聚光灯，光锥、衰减与 cards.Lights 一致），所以看台的明暗和场地、地面连在一起。水泥的底色用
Poly Haven 的岩壁贴图（Amal Kumar，CC0，经 Wikimedia Commons）平铺后去色、压暗。

照明灯塔。四角各一座钢架灯塔，高 82，塔身是一张绕竖直轴转向镜头的平面（钢架的两根主柱、斜撑和横撑），
塔顶是朝场地的灯盘，4 × 6 盏灯；灯的光晕是始终面向镜头的粒子。近端左角那座的灯坏了，只剩很暗的余光。
灯盘背向镜头时看不见灯。

光束。每盏亮着的灯塔从灯盘射向自己的照射点，光束是一张沿光束轴线、尽量正对镜头的长条（加亮混合），
靠灯的一端窄而亮，向外张开、渐暗，里面有一缕缕灰尘造成的明暗。

夜空。看台外是一片很暗的土地，再往外（y = 560）立着一张夜空的远景：云取自一张月夜云层的照片（月亮那一角
不用），去色后按体育场灯光照亮云底的样子染成暖灰，越往上越暗；地平线上是一排杨树的剪影（取自一张杨树照片）。
"""
import math

import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter, zoom

from common import IMG, cached, disk_cached, smooth, rot_axes, euler_from_matrix
from engine import Particles, Plane, Tex, register_material, dot_atlas
import surround as SR

FIELD_HW, FIELD_HH = SR.FIELD_HW, SR.FIELD_HH
IN_HW = FIELD_HW + SR.MARGIN + SR.TRACK_W + 3.0           # 看台内沿（圆角矩形的半宽、半高）
IN_HH = FIELD_HH + SR.MARGIN + SR.TRACK_W + 3.0
IN_R = 26.0 + SR.TRACK_W + 3.0                            # 看台内沿转角的半径
WALL_H = 1.8
DEPTH, RISE = 45.0, 22.0
N_STEPS = 28
SKY_Y = 330.0

LIGHT_DEF = {"lp": SR.LIGHT_POS, "la": SR.LIGHT_AIM}


def _light_uniforms():
    L = SR.lights()
    u = {}
    for i in range(4):
        aim = np.array(SR.LIGHT_AIM[i]) - np.array(SR.LIGHT_POS[i])
        aim /= np.linalg.norm(aim)
        u[f"lp{i}"] = tuple(float(v) for v in SR.LIGHT_POS[i])
        u[f"lc{i}"] = tuple(float(v) for v in L.color[i] * L.power[i])
        u[f"la{i}"] = tuple(float(v) for v in aim)
    u["amb"] = tuple(float(v) for v in L.ambient)
    return u


SPOT_GLSL = """
uniform vec3 lp0; uniform vec3 lp1; uniform vec3 lp2; uniform vec3 lp3;
uniform vec3 lc0; uniform vec3 lc1; uniform vec3 lc2; uniform vec3 lc3;
uniform vec3 la0; uniform vec3 la1; uniform vec3 la2; uniform vec3 la3;
uniform vec3 amb;
uniform float flash;
uniform vec3 flash_dir;
uniform vec3 flash_col;
uniform float spill;
vec3 spot(vec3 P, vec3 N, vec3 lp, vec3 lc, vec3 la) {
    vec3 d = lp - P;
    float r2 = dot(d, d);
    vec3 L = d * inversesqrt(r2);
    float ca = -dot(L, la);
    float u = clamp((ca - 0.86) / (0.975 - 0.86), 0.0, 1.0);
    float sp = spill + (1.0 - spill) * u * u * (3.0 - 2.0 * u);
    return lc * sp / (1.0 + r2 / 67600.0) * max(dot(N, L), 0.0);
}
vec3 irr(vec3 P, vec3 N) {
    return amb + spot(P, N, lp0, lc0, la0) + spot(P, N, lp1, lc1, la1) + spot(P, N, lp2, lc2, la2)
         + spot(P, N, lp3, lc3, la3) + flash * flash_col * max(dot(N, flash_dir), 0.0);
}
"""

register_material("h_stand", SPOT_GLSL + """
uniform float n_steps;
uniform float kind;            // 0 台阶斜面，1 挡墙
vec4 material(vec4 base) {
    vec3 P = v_wpos;
    vec3 Nr = normalize(vec3(u_normal.xy, 0.0));
    vec3 col;
    if (kind < 0.5) {
        // 沿斜面从上（外沿）往下：每一级先是踏面，再是立面；踏面外缘（台阶的棱）略亮，立面底部积灰略暗
        // 远处一级台阶不到两个像素时，踏面和立面按面积平均，不出现摩尔纹
        float w = fwidth(v_uv01.y * n_steps);
        float f = fract(v_uv01.y * n_steps);
        float tread = 1.0 - smoothstep(0.62 - w, 0.62 + w, f);
        float nose = exp(-pow((f - 0.62) / max(0.035, w), 2.0)) * (1.0 - smoothstep(0.3, 0.6, w));
        float far = smoothstep(0.25, 0.6, w);
        vec3 It = irr(P, vec3(0.0, 0.0, 1.0)), Ir = irr(P, Nr);
        vec3 I = mix(mix(Ir, It, tread), mix(Ir, It, 0.62), far);
        float dark = mix(1.0 - 0.25 * smoothstep(0.85, 1.0, f), 0.96, far);
        col = base.rgb * I * (1.0 + 0.25 * nose) * dark;
    } else {
        col = base.rgb * irr(P, Nr);
    }
    return vec4(col * base.a, base.a);
}
""", defaults={"n_steps": 28.0, "kind": 0.0, "flash": 0.0, "flash_dir": (0.0, 0.0, 1.0),
               "flash_col": (0.0, 0.0, 0.0), "spill": 0.35})

register_material("h_lit", SPOT_GLSL + """
uniform float facing;          // 1：按平面法线受光；0：按竖直向上受光
vec4 material(vec4 base) {
    vec3 N = mix(vec3(0.0, 0.0, 1.0), u_normal, facing);
    return vec4(base.rgb * irr(v_wpos, N), base.a);
}
""", defaults={"facing": 0.0, "flash": 0.0, "flash_dir": (0.0, 0.0, 1.0), "flash_col": (0.0, 0.0, 0.0),
               "spill": 0.10})


# ---------------------------------------------------------------- 看台

def _concrete():
    src = np.asarray(Image.open(IMG / "Rock_wall_10_diff_8k_Amal_Kumar_via_Poly_Haven_.png").convert("RGB")
                     .resize((1024, 1024), Image.LANCZOS), np.float32) / 255
    lum = src.mean(2)
    lum = (lum - lum.mean()) / (lum.std() + 1e-6)
    v = np.clip(0.50 + 0.10 * lum, 0.2, 0.8)
    rng = np.random.default_rng(12)
    stain = gaussian_filter(rng.normal(0, 1, (1024, 1024)), (40, 6), mode="wrap")
    stain /= stain.std() + 1e-6
    v *= 1.0 - 0.12 * np.clip(stain, 0, 3)                       # 雨水冲出的竖向污痕
    rgb = np.dstack([v * 0.98, v * 0.95, v * 0.90])
    return rgb.astype(np.float32)


def concrete_tex():
    return cached("st_conc", lambda: Tex(disk_cached("concrete", _concrete, "v1"), repeat=True))


def _edge_path(r_add=0.0, n_corner=12):
    """看台内沿（或向外偏移 r_add）的圆角矩形，按逆时针排列的顶点；直边各两个端点，转角各 n_corner 段。"""
    hw, hh, r = IN_HW - IN_R, IN_HH - IN_R, IN_R + r_add
    pts = []
    for cx, cy, a0 in ((hw, -hh, -90.0), (hw, hh, 0.0), (-hw, hh, 90.0), (-hw, -hh, 180.0)):
        for k in range(n_corner + 1):
            a = math.radians(a0 + 90.0 * k / n_corner)
            pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    return pts


def _frame(xa, ya, za):
    """列向量为 x、y、z 轴的旋转矩阵 → 平面的 (yaw, pitch, roll)（度）。"""
    R = np.stack([xa, ya, za], 1)[None].astype(np.float32)
    return tuple(float(v) for v in np.degrees(euler_from_matrix(R)[0]))


def stand_geometry():
    """看台的平面：[(中心, 尺寸, 转角, 遮罩, 种类, uv)]。种类 0 为台阶斜面，1 为挡墙。"""
    def make():
        import skia
        out = []
        inner = _edge_path(0.0)
        outer = _edge_path(DEPTH)
        z0 = WALL_H
        for i in range(len(inner)):
            j = (i + 1) % len(inner)
            p0, p1 = np.array(inner[i]), np.array(inner[j])
            q0, q1 = np.array(outer[i]), np.array(outer[j])
            seg = p1 - p0
            if np.linalg.norm(seg) < 1e-3:
                continue
            t = seg / np.linalg.norm(seg)
            n = np.array([t[1], -t[0]])                         # 逆时针走时，外侧在右手
            xa = np.array([-t[0], -t[1], 0.0])                 # 从场地里看，平面的 x 轴朝右
            # 斜面：底边 p0–p1（高 z0），顶边 q0–q1（高 z0 + RISE），用梯形遮罩
            s3 = np.array([n[0] * DEPTH, n[1] * DEPTH, RISE])
            slant = np.linalg.norm(s3)
            ya = s3 / slant
            za = np.cross(xa, ya)
            wb, wt = np.linalg.norm(p1 - p0), np.linalg.norm(q1 - q0)
            W = max(wb, wt) + 0.6
            c2 = (p0 + p1 + q0 + q1) / 4
            center = (c2[0], c2[1], z0 + RISE / 2)
            # 遮罩：平面 0–1 坐标（u 向右，即沿 −t；v 向下，即从顶边到底边）
            path = skia.Path()
            # 顶边（v = 0）宽 wt，底边（v = 1）宽 wb，都以中线对称
            path.moveTo(0.5 - (wt / 2 + 0.3) / W, 0.0)
            path.lineTo(0.5 + (wt / 2 + 0.3) / W, 0.0)
            path.lineTo(0.5 + (wb / 2 + 0.3) / W, 1.0)
            path.lineTo(0.5 - (wb / 2 + 0.3) / W, 1.0)
            path.close()
            inv = skia.Path()
            inv.addRect(skia.Rect(-1, -1, 2, 2))
            mask = skia.Op(inv, path, skia.PathOp.kDifference_PathOp)    # 路径内部是洞：挖掉梯形以外的部分
            uvw = W / 12.0
            out.append((center, (W, slant), _frame(xa, ya, za), mask, 0, (0, 0, uvw, slant / 12.0)))
            # 挡墙
            ya2 = np.array([0.0, 0.0, 1.0])
            za2 = np.cross(xa, ya2)
            cw = (p0 + p1) / 2
            out.append(((cw[0], cw[1], WALL_H / 2), (wb + 0.3, WALL_H), _frame(xa, ya2, za2), None, 1,
                        (0, 0, (wb + 0.3) / 12.0, WALL_H / 12.0)))
        return out
    return cached("stand_geo", make)


def stand_items(t, flash=None):
    uni = dict(cached("st_uni", _light_uniforms))
    if flash is not None:
        uni.update(flash)
    tex = concrete_tex()
    items = []
    for center, size, rot, mask, kind, uv in stand_geometry():
        u = dict(uni)
        u["kind"] = float(kind)
        u["n_steps"] = float(N_STEPS)
        items.append(Plane(tex, center=center, size=size, rot=rot, uv=uv, mask=mask, material="h_stand", uniforms=u,
                           group="past", stack="stands", bias=2.0e4))
    return items


# ---------------------------------------------------------------- 看台外的地面

def _outer_ground():
    n = 768
    rng = np.random.default_rng(7)
    d = gaussian_filter(rng.normal(0, 1, (n, n)), 2.0)
    d2 = gaussian_filter(rng.normal(0, 1, (n, n)), 18.0)
    v = 0.16 + 0.03 * d / (d.std() + 1e-6) + 0.04 * d2 / (d2.std() + 1e-6)
    return np.dstack([v * 1.0, v * 0.92, v * 0.82]).astype(np.float32)


def outer_ground_items(t, flash=None):
    tex = cached("og_tex", lambda: Tex(disk_cached("outer_ground", _outer_ground, "v1"), repeat=True))
    uni = dict(cached("st_uni", _light_uniforms))
    uni["facing"] = 0.0
    if flash is not None:
        uni.update(flash)
    y0, y1 = -900.0, SKY_Y                                    # 只铺到夜空远景的脚下，不挡住远景
    return [Plane(tex, center=(0.0, (y0 + y1) / 2, -0.2), size=(3400.0, y1 - y0), uv=(0, 0, 3400 / 60, (y1 - y0) / 60),
                  material="h_lit", uniforms=uni, group="past", bias=9.0e4)]


# ---------------------------------------------------------------- 照明灯塔

TOWER_H = 80.0


def _mast():
    """钢架塔身（RGBA，128×2048）：两根主柱从下往上收窄，交叉斜撑和横撑。"""
    import skia
    W, H = 160, 2560
    s = skia.Surface(W, H)
    c = s.getCanvas()
    c.clear(skia.Color4f(0, 0, 0, 0))
    p = skia.Paint(Color=skia.Color4f(1, 1, 1, 1), AntiAlias=True, Style=skia.Paint.kStroke_Style)

    def half(y):                                   # y 从顶（0）到底（H）：塔身的半宽
        return 22 + 48 * (y / H)
    p.setStrokeWidth(7)
    c.drawLine(W / 2 - half(0), 0, W / 2 - half(H), H, p)
    c.drawLine(W / 2 + half(0), 0, W / 2 + half(H), H, p)
    p.setStrokeWidth(3)
    ys = np.linspace(0, H, 34)
    for a, b in zip(ys[:-1], ys[1:]):
        c.drawLine(W / 2 - half(a), a, W / 2 + half(b), b, p)
        c.drawLine(W / 2 + half(a), a, W / 2 - half(b), b, p)
        c.drawLine(W / 2 - half(a), a, W / 2 + half(a), a, p)
    a = s.makeImageSnapshot().toarray()[..., 3].astype(np.float32) / 255
    return np.dstack([np.full((H, W, 3), 0.85, np.float32), a])


def _lamp_panel():
    """灯盘（RGBA）：深色的框架上 4 × 6 盏圆灯，灯面为 1，框架为暗灰。另返回只有灯面的发光贴图。"""
    W, H = 600, 400
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
    frame = np.zeros((H, W), np.float32)
    frame[(xx > 20) & (xx < W - 20) & (yy > 20) & (yy < H - 20)] = 1.0
    lamps = np.zeros((H, W), np.float32)
    for i in range(4):
        for j in range(6):
            cx, cy = 70 + j * 92, 65 + i * 90
            r = np.hypot(xx - cx, yy - cy)
            lamps = np.maximum(lamps, np.clip(36 - r, 0, 1))
            frame = np.maximum(frame, np.clip(42 - r, 0, 1))
    rgb = np.dstack([np.full((H, W), 0.12)] * 3) * (1 - lamps[..., None]) + lamps[..., None]
    return np.dstack([rgb, frame]).astype(np.float32), lamps


def tower_tex():
    def make():
        panel, lamps = _lamp_panel()
        return Tex(_mast()), Tex(panel), Tex(np.dstack([np.ones(lamps.shape + (3,), np.float32), lamps]))
    return cached("tower_tex", make)


def tower_items(t, cam, flash=None):
    """四座灯塔：塔身、灯盘、灯的光晕。cam 为当前镜头。"""
    mast, panel, glow = tower_tex()
    eye = np.asarray(cam.eye, float)
    uni = dict(cached("st_uni", _light_uniforms))
    uni["facing"] = 1.0
    if flash is not None:
        uni.update(flash)
    dot = cached("tw_dot", lambda: dot_atlas(64, 0.0))
    items = []
    gp, gs, gc = [], [], []
    for (lx, ly, lz), col, pw, aim in zip(SR.LIGHT_POS, SR.LIGHT_COL, SR.LIGHT_POW, SR.LIGHT_AIM):
        base = np.array([lx * 1.02, ly * 1.04, 0.0])
        # 塔身：绕竖直轴转向镜头
        to = eye[:2] - base[:2]
        to = to / (np.linalg.norm(to) + 1e-6)
        za = np.array([to[0], to[1], 0.0])
        ya = np.array([0.0, 0.0, 1.0])
        xa = np.cross(ya, za)
        items.append(Plane(mast, center=(base[0], base[1], TOWER_H / 2), size=(5.0, TOWER_H), rot=_frame(xa, ya, za),
                           color=(0.075, 0.068, 0.062), group="past", bias=3.0e4))
        # 灯盘：朝向照射点
        top = np.array([lx, ly, lz])
        d = np.array(aim) - top
        d /= np.linalg.norm(d)
        za = -d * -1.0                                            # 灯盘的正面朝照射点
        za = d
        xa = np.cross(np.array([0.0, 0.0, 1.0]), za)
        xa /= np.linalg.norm(xa)
        ya = np.cross(za, xa)
        facing = float(np.dot(za, (eye - top) / np.linalg.norm(eye - top)))
        k = pw / 1.0
        items.append(Plane(panel, center=tuple(top), size=(15.0, 10.0), rot=_frame(xa, ya, za),
                           color=(0.5, 0.48, 0.45), group="past", bias=1.6e4))
        if facing > 0:
            on = np.array(col) * (3.0 * k) * min(facing * 2.0, 1.0)
            items.append(Plane(glow, center=tuple(top + za * 0.05), size=(15.0, 10.0), rot=_frame(xa, ya, za),
                               blend="add", color=tuple(on), group="past", bias=1.55e4))
            # 光晕：每盏灯一个，加上整个灯盘的一大团
            for i in range(4):
                for j in range(6):
                    p = top + xa * ((70 + j * 92) / 600 - 0.5) * 15.0 + ya * (0.5 - (65 + i * 90) / 400) * 10.0
                    gp.append(p + za * 0.3)
                    gs.append(2.2)
                    gc.append(np.r_[np.array(col) * 0.55 * k * facing, 1.0])
            gp.append(top + za * 0.5)
            gs.append(55.0)
            gc.append(np.r_[np.array(col) * 0.20 * k * facing, 1.0])
    if gp:
        items.append(Particles(dot, np.array(gp, np.float32), np.array(gs, np.float32), None,
                               np.array(gc, np.float32), blend="add", group="past", bias=1.5e4))
    return items


# ---------------------------------------------------------------- 光束

def _beam_tex():
    nu, nv = 512, 128
    u = np.linspace(0, 1, nu)[None, :]
    v = np.linspace(-1, 1, nv)[:, None]
    w = 0.12 + 0.88 * u
    a = np.exp(-(v / w) ** 2 * 3.0) * smooth(u, 0.0, 0.05) * np.exp(-u * 1.6) * (1 - smooth(u, 0.75, 1.0))
    rng = np.random.default_rng(5)
    st = gaussian_filter(rng.normal(0, 1, (nv, nu)), (1.5, 40.0), mode="wrap")
    a *= np.clip(1.0 + 0.35 * st / (st.std() + 1e-6), 0.3, 2.0)
    a /= a.max()
    return np.dstack([np.ones((nv, nu, 3), np.float32), a.astype(np.float32)])


def beam_items(t, cam, k=1.0):
    """光束：沿光束轴线的长条，绕轴线转到尽量正对镜头。"""
    tex = cached("st_beam", lambda: Tex(_beam_tex()))
    eye = np.asarray(cam.eye, float)
    items = []
    for (lx, ly, lz), col, pw, aim in zip(SR.LIGHT_POS, SR.LIGHT_COL, SR.LIGHT_POW, SR.LIGHT_AIM):
        if pw < 0.2:
            continue
        A = np.array([lx, ly, lz])
        B = np.array(aim, float) + (np.array(aim, float) - A) * 0.1
        L = np.linalg.norm(B - A)
        xa = (B - A) / L
        mid = (A + B) / 2
        vc = eye - mid
        za = vc - xa * np.dot(vc, xa)
        za /= np.linalg.norm(za) + 1e-6
        ya = np.cross(za, xa)
        items.append(Plane(tex, center=tuple(mid), size=(L, L * 0.42), rot=_frame(xa, ya, za), blend="add",
                           color=tuple(np.array(col) * 0.22 * pw * k), group="past", bias=-2.0e4))
    return items


# ---------------------------------------------------------------- 夜空

def _sky():
    """夜空远景（RGB，4096×1200，HDR）：云底被体育场的灯光照成暖灰，越往上越暗；地平线上一排杨树的剪影。"""
    W, H = 4096, 1200
    src = Image.open(IMG / "Moon_in_clouds_over_Kolleröd.jpg").convert("RGB")
    w0, h0 = src.size
    crop = src.crop((int(w0 * 0.45), 0, w0, int(h0 * 0.95)))            # 不要月亮那一角
    a = np.asarray(crop.resize((W // 2, H), Image.LANCZOS), np.float32) / 255
    a = np.concatenate([a, a[:, ::-1]], 1)                               # 左右镜像拼成整幅，接缝对称
    lum = a.mean(2)
    lum = (lum - lum.min()) / (lum.max() - lum.min() + 1e-6)
    yy = np.linspace(0, 1, H)[:, None]                                    # 0 为顶部
    glow = np.exp(-((1 - yy) / 0.22)) * 1.0                               # 越靠地平线越亮（灯光照亮云底）
    cloud = lum ** 1.4
    v = 0.03 + 0.42 * cloud * (0.25 + 0.75 * glow) + 0.20 * glow
    rgb = np.dstack([v * 1.10, v * 0.92, v * 0.80])
    # 杨树剪影：取照片里比天暗的部分
    tr = np.asarray(Image.open(IMG / "Poplar_silhouette_-_geograph_org_uk_-_6023568.jpg").convert("L"),
                    np.float32) / 255
    sil = np.clip((0.55 - tr) / 0.2, 0, 1)
    th, tw = sil.shape
    rng = np.random.default_rng(3)
    mask = np.zeros((H, W), np.float32)
    x = 0
    while x < W:
        s = rng.uniform(0.055, 0.085)
        hh = int(th * s)
        ww = int(tw * s)
        tree = np.asarray(Image.fromarray((sil * 255).astype(np.uint8)).resize((ww, hh), Image.LANCZOS),
                          np.float32) / 255
        if rng.random() < 0.5:
            tree = tree[:, ::-1]
        y0 = H - hh
        x1 = min(W, x + ww)
        mask[y0:H, x:x1] = np.maximum(mask[y0:H, x:x1], tree[:, :x1 - x])
        x += int(ww * rng.uniform(0.35, 0.9))
    mask[int(H * 0.985):] = 1.0                                           # 地平线以下
    rgb = rgb * (1 - mask[..., None]) + np.array([0.006, 0.006, 0.007]) * mask[..., None]
    return rgb.astype(np.float16)


def sky_tex():
    return cached("st_sky", lambda: Tex(disk_cached("sky", _sky, "v4").astype(np.float32)))


SKY_W, SKY_H, SKY_Z0 = 3600.0, 1055.0, -20.0


def sky_items(t, flash=0.0):
    k = 1.0 + 3.0 * flash
    return [Plane(sky_tex(), center=(0.0, SKY_Y, SKY_Z0 + SKY_H / 2), size=(SKY_W, SKY_H), rot=(0.0, 90.0, 0.0),
                  color=(k, k, k * 1.1), group="past", bias=1.0e5)]
