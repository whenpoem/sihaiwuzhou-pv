"""L16 的地球：地上一汪圆形积水，雨点激起的同心涟漪变成纬线，积水升起成一个由字带组成的球。

球不是贴图，而是在着色器里逐像素求视线与球的交点：先求镜头到这个像素的射线与球面的两个交点（近处的外表面、
远处的内表面），交点的法线换到球自身的坐标系里得到经纬度，按纬度查是哪一条字带、按经度查是带上的第几个字，
再按光照（左上方的路灯、背后夜空的边缘光）着色。字带之间留有空隙，空隙里透出球背面字带的内侧（字是反的、
更暗），再往后透出地面，所以转动时能看出它是一个镂空的真实的球。球绕自身的竖轴缓慢转动。

字带：赤道一条宽带写歌词（唱到"世界大概都"时一个字一个字定在带上），南北各四条窄带上的字不停翻换（"善變"），
赤道以北第一条是褪色红的旧字"世界是你們的　也是我們的　但是歸根結底是你們的"，固定不变。

积水：d_puddle 画一汪圆形的水，映出夜云和路灯，雨点激起涟漪；"她"时一滴大雨落在正中，激起一圈圈同心波纹，
随后波纹定住，变成球从北极看下去的纬线，球从水里升起。
"""
import math

import numpy as np
import skia

from common import RED, cached, look
from engine import Tex, Plane, register_material

POOL_TEXT = "".join(look.trad(look.lyric(n)) for n in range(1, 41)).replace("　", "")
OLD = look.trad("世界是你們的　也是我們的　但是歸根結底是你們的")
ATLAS_N = 16                     # 图集 16×16 格
CELL = 128


def atlas_keys():
    def make():
        keys = list(dict.fromkeys(POOL_TEXT + OLD.replace("　", "")))
        assert len(keys) <= ATLAS_N * ATLAS_N
        return keys
    return cached("globe_keys", make)


def atlas_tex():
    """字形图集：16×16 格，每格一个思源宋体粗字，按表意字框居中。"""
    def make():
        keys = atlas_keys()
        W = ATLAS_N * CELL
        arr = np.zeros((W, W), np.uint8)
        s = skia.Surface.MakeRasterDirect(skia.ImageInfo.MakeA8(W, W), arr)
        c = s.getCanvas()
        em = CELL * 0.80
        f = look.font("serif", 700, em)
        paint = skia.Paint(AntiAlias=True, Color=skia.ColorWHITE)
        for i, ch in enumerate(keys):
            cx, cy = (i % ATLAS_N) * CELL, (i // ATLAS_N) * CELL
            adv = f.measureText(ch)
            c.drawString(ch, cx + (CELL - adv) / 2, cy + CELL / 2 + 0.38 * em, f, paint)
        del c, s
        return Tex(arr, mipmap=True)
    return cached("globe_atlas", make)


def glyph_index(ch):
    return atlas_keys().index(ch)


# ---------------------------------------------------------------- 字带

N_BANDS = 9                       # 南四、赤道一、北四；s = (纬度 + 90°) / 180°
EQ = 4                            # 赤道宽带的序号
RED_BAND = 5                      # 赤道以北第一条：旧字
BAND_EDGES = [0.075, 0.161, 0.247, 0.333, 0.419, 0.581, 0.667, 0.753, 0.839, 0.925]
MAX_CELLS = 64


def band_cells():
    """每条带上的字数：让每格在球面上接近正方形。"""
    out = []
    for i in range(N_BANDS):
        s0, s1 = BAND_EDGES[i], BAND_EDGES[i + 1]
        lat = math.radians((0.5 * (s0 + s1) - 0.5) * 180.0)
        h = math.radians((s1 - s0) * 180.0) * 0.84
        n = int(round(2 * math.pi * math.cos(lat) / h * (0.92 if i == EQ else 1.0)))
        if i == RED_BAND:
            n = len(OLD)
        out.append(max(6, min(MAX_CELLS, n)))
    return out


def table_tex(locks):
    """每条带上每格的内容表（9 × 64，RGBA8，最近邻采样）：R 字形序号，G 是否固定（255 固定、0 不停翻换），
    B 颜色（0 暖白、255 褪色红），A 亮度（128 为 1 倍）。locks 为 [(带, 格, 字, 亮度)]。"""
    key = ("globe_table",) + tuple(locks)

    def make():
        t = np.zeros((N_BANDS, MAX_CELLS, 4), np.uint8)
        t[..., 3] = 128
        n = band_cells()[RED_BAND]
        for j, ch in enumerate(OLD):
            if ch != "　":
                t[RED_BAND, j] = (glyph_index(ch), 255, 255, 128)
            else:
                t[RED_BAND, j] = (0, 255, 255, 0)
        for b, j, ch, k in locks:
            t[b, j % band_cells()[b]] = (glyph_index(ch), 255, 0, int(min(255, 128 * k)))
        return Tex(t, premultiplied=True, mipmap=False, nearest=True)
    return cached(key, make)


def cells_tex():
    """每条带的字数与上下边（1 × 9，RGBA 浮点）：R 字数，G 下边 s0，B 上边 s1。"""
    def make():
        t = np.zeros((1, N_BANDS, 4), np.float32)
        for i, n in enumerate(band_cells()):
            t[0, i] = (n, BAND_EDGES[i], BAND_EDGES[i + 1], 1.0)
        return Tex(t, premultiplied=True, mipmap=False, nearest=True)
    return cached("globe_cells", make)


GLOBE_GLSL = """
uniform sampler2D atlas;
uniform sampler2D table;
uniform sampler2D cells;
uniform vec3 g_c;              // 球心（世界坐标）
uniform float g_r;             // 半径
uniform vec3 g_ax;             // 球自身的 x、y（极轴）、z 轴在世界里的方向
uniform vec3 g_ay;
uniform vec3 g_az;
uniform vec3 lamp_pos;
uniform vec3 lamp_col;
uniform float flip_rate;       // 窄带上的字每秒翻换几次
uniform float water;           // 水面高度（z），水下部分不画
uniform float glow;            // 字的整体亮度
uniform float crack;           // 拼图切口的显现程度（L17 之前）
uniform float reveal;          // 字带从涟漪里显出的程度
uniform vec4 red_col;
uniform float mirror_z;        // 1：画倒影（球心关于地面镜像）
uniform float eq_dim;          // 赤道宽带上未定住的字的亮度

const float PI = 3.14159265;

// 一个交点处的颜色与不透明度。back 为 1 表示从球里面看到的远侧字带内侧。
vec4 shade(vec3 p, vec3 rd, float back) {
    vec3 n = (p - g_c) / g_r;
    vec3 l = vec3(dot(n, g_ax), dot(n, g_ay), dot(n, g_az));
    float lat = asin(clamp(l.y, -1.0, 1.0));
    float lon = atan(l.x, l.z);
    float s = lat / PI + 0.5;
    // 找到所在的字带
    int bi = -1;
    float s0 = 0.0, s1 = 0.0, nc = 0.0;
    for (int i = 0; i < 9; i++) {
        vec4 c = texelFetch(cells, ivec2(i, 0), 0);
        if (s >= c.g && s < c.b) { bi = i; s0 = c.g; s1 = c.b; nc = c.r; }
    }
    vec3 L = normalize(lamp_pos - p);
    vec3 nn = back > 0.5 ? -n : n;
    float lam = max(dot(nn, L), 0.0);
    float rim = pow(1.0 - abs(dot(n, -rd)), 3.0);
    if (bi < 0) {
        // 两极的极冠：实心的暗面，带一点漆面的高光
        if (s < BAND_LO || s > BAND_HI) {
            vec3 cap = vec3(0.035, 0.045, 0.065) * (0.4 + 1.2 * lam) + rim * vec3(0.10, 0.13, 0.20);
            return vec4(cap * (back > 0.5 ? 0.5 : 1.0), 1.0);
        }
        return vec4(0.0);
    }
    float v = (s - s0) / (s1 - s0);                  // 0 为南边，1 为北边
    float edge = 0.075;
    float rib = smoothstep(edge - 0.02, edge + 0.0, v) * smoothstep(1.0 - edge + 0.02, 1.0 - edge, v);
    rib *= reveal;
    if (rib <= 0.001) return vec4(0.0);
    float cu = (lon / (2.0 * PI) + 0.5) * nc;
    float ci = floor(cu);
    float fu = cu - ci;
    float fv = 1.0 - (v - edge) / (1.0 - 2.0 * edge);   // 字顶朝北
    vec4 tb = texelFetch(table, ivec2(int(mod(ci, nc)), bi), 0);
    float gidx;
    float flip = 1.0;
    float isred = tb.b;
    float boost = tb.a * 2.0;
    if (tb.g > 0.5) {
        gidx = floor(tb.r * 255.0 + 0.5);
    } else {
        float h = rnd(ivec2(int(ci), bi), 91);
        float ph = u_time * flip_rate * (0.6 + 0.8 * h) + h * 13.0;
        float ep = floor(ph);
        gidx = floor(rnd(ivec2(int(ci) + int(ep) * 97, bi), 92) * 245.0);
        float f = fract(ph);
        // 翻字：像翻牌一样上下压扁再展开
        flip = f < 0.14 ? abs(cos(f / 0.14 * PI)) : 1.0;
        if (f < 0.07) gidx = floor(rnd(ivec2(int(ci) + int(ep - 1.0) * 97, bi), 92) * 245.0);
        if (bi == EQ_BAND) boost *= eq_dim;
    }
    float gv = (fv - 0.5) / max(flip, 0.02) + 0.5;
    float gu = back > 0.5 ? 1.0 - fu : fu;
    float gmask = 0.0;
    if (gv > 0.0 && gv < 1.0 && !(tb.g > 0.5 && tb.a < 0.01)) {
        vec2 a = (vec2(mod(gidx, 16.0), floor(gidx / 16.0)) + vec2(gu, gv)) / 16.0;
        vec2 dc = vec2(cu, fv) / 16.0;
        gmask = textureGrad(atlas, a, dFdx(dc), dFdy(dc)).r;
    }
    vec3 ribc = vec3(0.030, 0.038, 0.055) * (0.35 + 1.4 * lam) + rim * vec3(0.09, 0.12, 0.19);
    vec3 txt = mix(vec3(0.96, 0.90, 0.79), red_col.rgb, isred) * (0.42 + 0.75 * lam + 0.25 * rim) * glow * boost;
    vec3 col = mix(ribc, txt, gmask);
    // 漆面的高光
    vec3 H = normalize(L - rd);
    col += lamp_col * pow(max(dot(nn, H), 0.0), 60.0) * 0.25 * (1.0 - back);
    // 拼图切口：裂开之前先在球面上显出一道道暗线
    if (crack > 0.0) {
        vec2 q = vec2(lon / (2.0 * PI) * 12.0, s * 6.0);
        vec2 f2 = fract(q) - 0.5;
        float wob = 0.06 * sin(q.y * 6.2831 * 1.0 + floor(q.x) * 1.7);
        float cutx = abs(abs(f2.x + wob) - 0.5);
        float cuty = abs(abs(f2.y + 0.06 * sin(q.x * 6.2831 + floor(q.y))) - 0.5);
        float line = 1.0 - smoothstep(0.0, 0.02, min(cutx, cuty) - 0.003);
        col *= 1.0 - line * crack * 0.85;
    }
    if (back > 0.5) col *= 0.42;
    return vec4(col * rib, rib);
}

vec4 material(vec4 base) {
    vec3 ro = u_eye;
    vec3 rd = normalize(v_wpos - u_eye);
    vec3 oc = ro - g_c;
    float b = dot(oc, rd);
    float c = dot(oc, oc) - g_r * g_r;
    float h = b * b - c;
    if (h < 0.0) return vec4(0.0);
    float sq = sqrt(h);
    // 轮廓抗锯齿：射线离球面切点越近越透明
    float pix = length(fwidth(v_wpos)) / max(length(v_wpos - u_eye), 1e-4) * length(oc);
    float edgeaa = clamp(sq / max(pix, 1e-5) * 0.7, 0.0, 1.0);
    vec3 p1 = ro + rd * (-b - sq);
    vec3 p2 = ro + rd * (-b + sq);
    vec4 acc = vec4(0.0);
    float side = mirror_z > 0.5 ? -1.0 : 1.0;
    if (side * p1.z > side * water) {
        vec4 f = shade(p1, rd, 0.0);
        acc = f;
    }
    if (acc.a < 0.999 && side * p2.z > side * water) {
        vec4 bk = shade(p2, rd, 1.0);
        acc += bk * (1.0 - acc.a);
    }
    // 水线：球面与水面相交处一圈亮的弯月面
    if (water > -50.0 && mirror_z < 0.5) {
        float wl = exp(-pow((p1.z - water) / (g_r * 0.02), 2.0)) * step(water, g_r + g_c.z);
        acc.rgb += vec3(0.5, 0.55, 0.65) * wl * 0.6;
    }
    return acc * edgeaa;
}
"""


def register():
    glsl = GLOBE_GLSL.replace("BAND_LO", f"{BAND_EDGES[0]:.4f}").replace("BAND_HI", f"{BAND_EDGES[-1]:.4f}").replace(
        "EQ_BAND", str(EQ))
    register_material("d_globe", glsl, defaults={
        "g_c": (0.0, 0.0, 0.0), "g_r": 1.0, "g_ax": (1.0, 0.0, 0.0), "g_ay": (0.0, 1.0, 0.0), "g_az": (0.0, 0.0, 1.0),
        "lamp_pos": (-3.9, 2.3, 3.6), "lamp_col": (1.0, 0.8, 0.6), "flip_rate": 2.2, "water": -100.0, "glow": 1.0,
        "crack": 0.0, "reveal": 1.0, "red_col": tuple(list(RED * 1.15) + [1.0]), "mirror_z": 0.0, "eq_dim": 0.13})


register()


def axes(tilt, spin):
    """球的姿态：极轴先从朝向镜头（+z）倒向画面上方（+y），tilt 为 0–1；再绕极轴转 spin（弧度）。
    返回世界坐标里球自身的 x、y（极轴）、z 三个方向。"""
    a = (1.0 - tilt) * math.pi / 2               # 极轴与 +y 的夹角：tilt = 0 时极轴朝 +z
    ay = np.array([0.0, math.cos(a), math.sin(a)])
    ax0 = np.array([1.0, 0.0, 0.0])
    az0 = np.cross(ax0, ay)
    c, s = math.cos(spin), math.sin(spin)
    ax = ax0 * c - az0 * s
    az = ax0 * s + az0 * c
    return ax, ay, az


def globe_plane(center, r, tilt, spin, t, locks=(), water=-100.0, reveal=1.0, glow=1.0, crack=0.0, lamp=None,
                lamp_col=(1.0, 0.8, 0.6), opacity=1.0, mirror=False):
    """一个正对镜头的方片，在它上面用 d_globe 画出球。方片放在球心高度、比球略大，透视下也盖得住整个球。"""
    ax, ay, az = axes(tilt, spin)
    c = np.asarray(center, float)
    uni = {"atlas": atlas_tex(), "table": table_tex(tuple(locks)), "cells": cells_tex(), "g_c": tuple(c), "g_r": r,
           "g_ax": tuple(ax), "g_ay": tuple(ay), "g_az": tuple(az), "water": water, "reveal": reveal, "glow": glow,
           "crack": crack, "lamp_col": tuple(lamp_col), "mirror_z": 1.0 if mirror else 0.0}
    if lamp is not None:
        uni["lamp_pos"] = tuple(lamp)
    zc = c[2] + r if not mirror else 0.003
    size = 2.6 * r * (1.0 if not mirror else 1.6)
    return Plane(None, center=(c[0], c[1], zc), size=(size, size), group="past", material="d_globe", uniforms=uni,
                 opacity=opacity)


def lock_cell(band, spin, screen_frac=0.0):
    """赤道带上此刻正对镜头（偏 screen_frac 个格）的那一格的序号。球自身的 z 轴在 tilt=1 时朝向镜头。"""
    n = band_cells()[band]
    # 正对镜头的经度：球坐标里 (x, z) = (sin, cos)，镜头方向在球坐标里为 (-sin spin, cos spin) 对应 lon = -spin
    lon = -spin
    cu = (lon / (2 * math.pi) + 0.5) * n + screen_frac
    return int(math.floor(cu)) % n
