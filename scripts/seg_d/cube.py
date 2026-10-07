"""L18 的立方体：拼好的十字形沿折线折起，成为一个缺盖的盒子，用轴测图的平面画法画出。

十字形中间一格是盒底，上下左右四格是四壁。每一面都是一块平面图形：先在盒子自己的三维坐标里把它绕折线转过
θ 角，再用正投影（轴测投影）投到画面上，得到一个平行四边形；着色器 d_affine 把这一面的贴图按仿射变换贴进
这个平行四边形，所以整个过程只有平面上的仿射变换，没有透视，也没有在三维里斜看平面。视角同时从正上方（拼图
的俯视）转到轴测角度，桌面、散落的拼图块也用同一个投影画，三者始终在同一个空间里。

光照在盒子坐标里计算：一盏灯在左上方（与 L17 照亮桌面的是同一盏），每一面按它朝向灯的程度变亮或变暗，
所以折起来以后几个面的明暗关系一致。拼图印刷的一面朝里，盒子外侧看到的是灰色硬纸板的背面。
"""
import math

import numpy as np
from scipy import ndimage

import puzzle as PZ
from common import cached, disk_cached
from engine import Plane, Tex, register_material

S3 = 3 * PZ.P                     # 盒子的边长（三块）
FACE_PX = 3 * PZ.PX

# 十字形的五面：名称 → (行起, 列起, 折线所在的边, 折起的方向)
FACES = {"C": (3, 3), "N": (0, 3), "S": (6, 3), "W": (3, 0), "E": (3, 6)}

AFFINE_GLSL = """
uniform sampler2D ftex;
uniform vec2 f_o;              // 平行四边形一角（世界 xy）
uniform vec4 f_inv;            // [e1 e2] 的逆矩阵（按列：a, b, c, d → [[a, c], [b, d]]）
uniform vec4 f_uv;             // 贴图子区域 (u0, v0, u1, v1)
uniform vec3 p_o;              // 这一面在盒子坐标里的一角与两条边，用来求每个像素的三维位置
uniform vec3 p_e1;
uniform vec3 p_e2;
uniform vec3 p_n;              // 看得见的那一侧的法线（盒子坐标）
uniform vec3 lamp_box;         // 灯（盒子坐标）
uniform vec3 lamp_col;
uniform vec3 amb;
uniform float lamp_fall;
uniform float gloss;
uniform vec3 eye_dir;          // 盒子坐标里指向观者的方向（正投影）
uniform float mono;            // 1：贴图是覆盖率（影子），乘 tint
uniform vec3 tint;
uniform float lit;             // 0：不打光（影子）

vec4 material(vec4 base) {
    vec2 q = v_wpos.xy - f_o;
    vec2 ab = vec2(f_inv.x * q.x + f_inv.z * q.y, f_inv.y * q.x + f_inv.w * q.y);
    vec2 fw = fwidth(ab);
    float inside = smoothstep(-fw.x, fw.x, ab.x) * smoothstep(1.0 + fw.x, 1.0 - fw.x, ab.x)
                 * smoothstep(-fw.y, fw.y, ab.y) * smoothstep(1.0 + fw.y, 1.0 - fw.y, ab.y);
    if (inside <= 0.0) return vec4(0.0);
    vec2 uv = mix(f_uv.xy, f_uv.zw, clamp(ab, 0.0, 1.0));
    vec4 tx = texture(ftex, uv);
    if (mono > 0.5) tx = vec4(tint * tx.r, tx.r);
    vec3 col = tx.rgb;
    if (lit > 0.5) {
        vec3 P3 = p_o + ab.x * p_e1 + ab.y * p_e2;
        vec3 Ld = lamp_box - P3;
        float dl = length(Ld);
        Ld /= dl;
        float fall = 1.0 / (1.0 + dl * dl * lamp_fall);
        col = tx.rgb * (amb + lamp_col * fall * max(dot(p_n, Ld), 0.0));
        vec3 H = normalize(Ld + eye_dir);
        col += lamp_col * fall * pow(max(dot(p_n, H), 0.0), 30.0) * gloss * tx.a;
    }
    return vec4(col, tx.a) * inside;
}
"""
register_material("d_affine", AFFINE_GLSL, defaults={
    "f_o": (0.0, 0.0), "f_inv": (1.0, 0.0, 0.0, 1.0), "f_uv": (0.0, 0.0, 1.0, 1.0), "p_o": (0.0, 0.0, 0.0),
    "p_e1": (1.0, 0.0, 0.0), "p_e2": (0.0, -1.0, 0.0), "p_n": (0.0, 0.0, 1.0), "lamp_box": (-1.7, 1.3, 2.3),
    "lamp_col": (1.0, 0.8, 0.6), "amb": (0.05, 0.05, 0.06), "lamp_fall": 0.3, "gloss": 0.0, "eye_dir": (0.0, 0.0, 1.0),
    "mono": 0.0, "tint": (0.0, 0.0, 0.0), "lit": 1.0})


# ---------------------------------------------------------------- 投影

class Proj:
    """盒子坐标 (X 右, Y 桌面上朝画面上方, Z 离开桌面) → 画面上的世界 xy（以 org 为原点）。
    先绕 Z 转 phi，再按仰角 el 正投影：el = 90° 为正上方俯视。"""

    def __init__(self, el, phi, org, scale=1.0):
        self.el, self.phi = math.radians(el), math.radians(phi)
        self.org = np.asarray(org, float)
        self.k = scale
        se, ce = math.sin(self.el), math.cos(self.el)
        sp, cp = math.sin(self.phi), math.cos(self.phi)
        # u = X cos φ - Y sin φ；v = (X sin φ + Y cos φ) sin el + Z cos el
        self.M = np.array([[cp, -sp, 0.0], [sp * se, cp * se, ce]]) * scale
        self.w = np.array([-sp * ce, -cp * ce, se])          # 指向观者
        self.depth_axis = self.w

    def lin(self, v):
        return self.M @ np.asarray(v, float)

    def pt(self, p):
        return self.org + self.M @ np.asarray(p, float)

    def depth(self, p):
        return float(np.dot(self.w, p))


def affine_plane(tex, proj, o3, e1, e2, n_vis, z, lamp, uv=(0, 0, 1, 1), mono=False, tint=(0, 0, 0), lit=True,
                 opacity=1.0, gloss=0.2, stack=None):
    """把贴图贴进盒子坐标里由一角 o3 与两边 e1、e2 张成的平面块，按 proj 投到画面上。"""
    o = proj.pt(o3)
    a, b = proj.lin(e1), proj.lin(e2)
    det = a[0] * b[1] - a[1] * b[0]
    if abs(det) < 1e-7:
        return None
    inv = (b[1] / det, -a[1] / det, -b[0] / det, a[0] / det)
    corners = np.array([o, o + a, o + b, o + a + b])
    lo, hi = corners.min(0), corners.max(0)
    pad = 0.004
    c = (lo + hi) / 2
    size = (hi - lo) + 2 * pad
    uni = {"ftex": tex, "f_o": tuple(o), "f_inv": inv, "f_uv": tuple(uv), "p_o": tuple(o3), "p_e1": tuple(e1),
           "p_e2": tuple(e2), "p_n": tuple(n_vis), "eye_dir": tuple(proj.w), "mono": 1.0 if mono else 0.0,
           "tint": tuple(tint), "lit": 1.0 if lit else 0.0, "gloss": gloss}
    uni.update(lamp)
    return Plane(None, center=(c[0], c[1], z), size=tuple(size), group="past", material="d_affine", uniforms=uni,
                 opacity=opacity, stack=stack)


# ---------------------------------------------------------------- 各面的贴图

def face_rgba(name):
    """一面的贴图：这一面的 9 块按位置叠在一起（相邻块的榫头互相咬合，接缝处露出纸板芯的细线），超出这一面的
    榫头裁掉。盒底上"自卑"两块没扣进去，歪着搁在空位上，带一点影子。"""
    def make():
        r0, c0 = FACES[name]
        W = FACE_PX
        out = np.zeros((W, W, 4), np.float32)
        m = int(round(PZ.MARGIN * PZ.PX))

        def over(rgba, x, y):
            h, w = rgba.shape[:2]
            xa, ya = max(x, 0), max(y, 0)
            xb, yb = min(x + w, W), min(y + h, W)
            if xa >= xb or ya >= yb:
                return
            src = rgba[ya - y:yb - y, xa - x:xb - x]
            a = src[..., 3:4]
            out[ya:yb, xa:xb, :3] = out[ya:yb, xa:xb, :3] * (1 - a) + src[..., :3] * a
            out[ya:yb, xa:xb, 3:4] = out[ya:yb, xa:xb, 3:4] * (1 - a) + a

        later = []
        for r in range(r0, r0 + 3):
            for c in range(c0, c0 + 3):
                if (r, c) in (PZ.ZI, PZ.BEI):
                    later.append((r, c))
                    continue
                over(PZ.piece_rgba(r, c), (c - c0) * PZ.PX - m, (r - r0) * PZ.PX - m)
        if later:
            dx, dy, rot, lift = PZ.conflict_pose(86.5)
            pair = np.zeros((PZ.TEX_N, PZ.TEX_N + PZ.PX, 4), np.float32)
            for k, rc in enumerate(sorted(later, key=lambda q: q[1])):
                a = PZ.piece_rgba(*rc)
                x = k * PZ.PX
                pa = pair[:, x:x + PZ.TEX_N]
                al = a[..., 3:4]
                pa[..., :3] = pa[..., :3] * (1 - al) + a[..., :3] * al
                pa[..., 3:4] = pa[..., 3:4] * (1 - al) + al
            pr = ndimage.rotate(pair, -rot, reshape=False, order=1)
            sh = ndimage.gaussian_filter(pr[..., 3], 8) * 0.6
            x0 = (PZ.ZI[1] - c0) * PZ.PX - m + int(round(dx * PZ.PX))
            y0 = (PZ.ZI[0] - r0) * PZ.PX - m - int(round(dy * PZ.PX))
            shadow = np.zeros_like(pr)
            shadow[..., 3] = sh
            over(shadow, x0 + 10, y0 + 12)
            over(pr, x0, y0)
        # 没有被块盖住的地方（理论上没有）填成纸板芯的颜色
        a = out[..., 3:4]
        out[..., :3] = out[..., :3] + np.array([0.62, 0.58, 0.50]) * (1 - a)
        out[..., 3] = 1.0
        return out
    return disk_cached(f"face_{name}_v2", make)


def face_tex(name):
    return cached(("face_tex", name), lambda: Tex(face_rgba(name)))


def back_tex():
    return cached("back_tex", lambda: Tex(PZ.back_texture(), repeat=True))


def table_tex():
    return PZ.table_tex()


# ---------------------------------------------------------------- 折叠

def _rot(axis, ang):
    x, y, z = axis
    c, s = math.cos(ang), math.sin(ang)
    C = 1 - c
    return np.array([[c + x * x * C, x * y * C - z * s, x * z * C + y * s],
                     [y * x * C + z * s, c + y * y * C, y * z * C - x * s],
                     [z * x * C - y * s, z * y * C + x * s, c + z * z * C]])


def face_frame(name, theta):
    """一面在盒子坐标里的一角与两条边（折起 theta 弧度之后），以及印刷面的法线。
    平放时 o3 是这一面在俯视图里的左上角，e1 向右、e2 向下（-Y），与贴图的方向一致。"""
    h = S3 / 2
    if name == "C":
        o, e1, e2, hinge, axis = np.array([-h, h, 0.0]), np.array([S3, 0, 0]), np.array([0, -S3, 0]), None, None
    elif name == "N":
        o, e1, e2, hinge, axis = np.array([-h, 3 * h, 0.0]), np.array([S3, 0, 0]), np.array([0, -S3, 0]), np.array([0, h, 0]), (1, 0, 0)
    elif name == "S":
        o, e1, e2, hinge, axis = np.array([-h, -h, 0.0]), np.array([S3, 0, 0]), np.array([0, -S3, 0]), np.array([0, -h, 0]), (-1, 0, 0)
    elif name == "W":
        o, e1, e2, hinge, axis = np.array([-3 * h, h, 0.0]), np.array([S3, 0, 0]), np.array([0, -S3, 0]), np.array([-h, 0, 0]), (0, 1, 0)
    else:
        o, e1, e2, hinge, axis = np.array([h, h, 0.0]), np.array([S3, 0, 0]), np.array([0, -S3, 0]), np.array([h, 0, 0]), (0, -1, 0)
    n = np.array([0.0, 0.0, 1.0])
    if hinge is not None and theta != 0.0:
        R = _rot(axis, theta)
        o = hinge + R @ (o - hinge)
        e1, e2, n = R @ e1, R @ e2, R @ n
    return o, e1, e2, n


def box_items(t, theta, el, phi, org, scale=1.0, table_op=1.0, loose_op=1.0, light_k=1.0, z0=0.0, inside=(),
              box_op=1.0):
    """桌面（轴测）、散落的块、盒子的五面。theta 为四壁折起的角度（弧度），el、phi 为视角，org 为盒底中心在画面上的
    世界坐标。返回元素列表（按远近排好，放在同一个 stack 里依次画）。"""
    proj = Proj(el, phi, org, scale)
    lamp_box = np.array([PZ.LAMP[0] - PZ.CENTER[0], PZ.LAMP[1] - PZ.CENTER[1], PZ.LAMP[2]])
    lamp = {"lamp_box": tuple(lamp_box), "lamp_col": tuple(PZ.LAMP_COL * light_k), "amb": tuple(PZ.AMB),
            "lamp_fall": 0.30}
    out = []
    zz = [z0]

    def add(it):
        if it is not None:
            zz[0] += 1e-4
            it.center = np.array([it.center[0], it.center[1], zz[0]])
            it.stack = "box"
            out.append(it)

    # 桌面：比画面大得多的一块，四周落进暗处
    if table_op > 0.001:
        W, H = 26.0, 18.0
        tp = affine_plane(table_tex(), proj, np.array([-W / 2, H / 2, 0.0]), np.array([W, 0, 0]), np.array([0, -H, 0]),
                          np.array([0, 0, 1.0]), 0.0, lamp, uv=(0, 0, W / 1.6, H / 1.6), opacity=table_op, gloss=0.05)
        add(tp)
    # 散落在桌上的块（四角那些没拼上的）
    if loose_op > 0.001:
        size = PZ.TEX_N / PZ.PX * PZ.P
        for (r, c), pl in PZ.plan_pieces().items():
            if pl["kind"] != "loose":
                continue
            x, y = pl["loose"] - PZ.CENTER
            a = math.radians(pl["loose_rot"])
            ex = np.array([math.cos(a), math.sin(a), 0.0]) * size
            ey = np.array([math.sin(a), -math.cos(a), 0.0]) * size
            o3 = np.array([x, y, 0.0]) - ex / 2 - ey / 2
            add(affine_plane(PZ.shadow_tex(r, c), proj, o3 + np.array([0.010, -0.012, 0]), ex, ey, np.array([0, 0, 1.0]),
                             0.0, lamp, mono=True, tint=(0, 0, 0), lit=False, opacity=0.5 * loose_op))
            add(affine_plane(PZ.piece_tex(r, c), proj, o3, ex, ey, np.array([0, 0, 1.0]), 0.0, lamp,
                             opacity=loose_op, gloss=0.25))
    # 盒子投在桌上的影子（灯在左上方）：盒底外扩一圈的柔和暗块
    sh = cached("box_shadow", lambda: Tex(_soft_square()))
    th = theta if isinstance(theta, dict) else {n: theta for n in "NSWE"}
    k = math.sin(min(th.values()))
    o3 = np.array([-S3 / 2 - 0.05 + 0.10 * k, S3 / 2 + 0.05 - 0.14 * k, 0.0])
    add(affine_plane(sh, proj, o3, np.array([S3 + 0.10 + 0.25 * k, 0, 0]), np.array([0, -(S3 + 0.10 + 0.25 * k), 0]),
                     np.array([0, 0, 1.0]), 0.0, lamp, mono=True, tint=(0, 0, 0), lit=False, opacity=0.55 * k * box_op))
    # 五面：按离观者的远近从远到近画
    faces = []
    for name in ("C", "N", "S", "W", "E"):
        o3, e1, e2, n = face_frame(name, 0.0 if name == "C" else th[name])
        ctr = o3 + e1 / 2 + e2 / 2
        faces.append((proj.depth(ctr) + (-1.0 if name == "C" else 0.0), name, o3, e1, e2, n))
    faces.sort(key=lambda f: f[0])
    inside = list(inside)
    for _, name, o3, e1, e2, n in faces:
        front = float(np.dot(n, proj.w)) >= 0.0
        if not front and inside:                 # 盒子里的东西（升起的帆）画在后壁之后、前壁之前
            for it in inside:
                add(it)
            inside = []
        if front:
            add(affine_plane(face_tex(name), proj, o3, e1, e2, n, 0.0, lamp, gloss=0.22, opacity=box_op))
        else:
            add(affine_plane(back_tex(), proj, o3, e1, e2, -n, 0.0, lamp, uv=(0, 0, 1.6, 1.6), gloss=0.05,
                             opacity=box_op))
        # 纸板的厚度：面的上沿（离开盒底的那条边）画一道浅色的窄条
        if name != "C" and th[name] > 0.05:
            thick = 0.006
            far = o3 if name in ("N",) else None
            # 上沿是离折线最远的那条边：N 的 o3–o3+e1，S 的 o3+e2–o3+e1+e2，W 的 o3–o3+e2，E 的 o3+e1–o3+e1+e2
            if name == "N":
                a0, ed = o3, e1
            elif name == "S":
                a0, ed = o3 + e2, e1
            elif name == "W":
                a0, ed = o3, e2
            else:
                a0, ed = o3 + e1, e2
            up = n * thick
            add(affine_plane(back_tex(), proj, a0 - up / 2, ed, up, np.array([0, 0, 1.0]), 0.0, lamp, uv=(0, 0, 1, 0.02),
                             gloss=0.0, opacity=box_op))
    for it in inside:
        add(it)
    return out, proj


def _soft_square(n=256):
    a = np.zeros((n, n), np.float32)
    a[40:-40, 40:-40] = 1.0
    return ndimage.gaussian_filter(a, 18)
