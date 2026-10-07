"""L06：正午的天空，白云骑士沿云顶从左往右骑过，歌词写在天上；云的亮部藏着极淡的旧字。
L07 开头：骑士的长矛向下倾斜、脱手，下落中经过一缕近云时变成一把生锈的刀（刀见 bed.py）。

骑士是 knight.py 抠出的多雷版画，放在云所在的 z = 0，约占画面高的三分之一；马蹄下面有一缕从前面飘过的
小云团（mist_items），遮住版画里马前腿的截断线。路线沿积云照片的云顶：先走在左边那朵浮云的顶上，
再越过两朵云之间的一段空天（"在天上飄"），踏上右边高耸的云塔，最后从塔顶往右走进天空，长矛在那里脱手。马的起伏按每秒 12 张取样：起伏和前后
摇摆的数值每 1/12 秒才更新一次，中间保持不变，看上去是手工逐张画出的步态。

歌词"寂寞的　白雲騎士　在天上飄"排成一行写在骑士上方的天空里，墨褐色宋体，随骑士从左往右逐字出现。
旧字"寂寞嫦娥舒廣袖"（《蝶恋花·答李淑一》）用仿宋竖排，藏在右边云塔受光最亮的一面上，褪色的红，
不透明度很低，并且只在云亮的地方显出来，近看才认得出。
"""
import math

import numpy as np

import knight as KN
import yard as Y
from common import INK, RED, L, Z_SKY, cached, ease, ramp, smooth
from engine import Plane, Tex, TextPlane, register_material
from plan import T

# ---------------------------------------------------------------- 骑士

KNIGHT_H = 8.6                                    # 马和人的高度（世界单位）：约占画面高的三分之一
PX_PER_U = 480.0 / KNIGHT_H                      # 贴图里马和人高 480 像素
ANCHOR = (240.0, 618.0)                           # 马蹄着地处在贴图里的像素位置
T_ENTER, X_ENTER = 44.95, -23.3
SPEED = 16.0                                      # 世界单位/秒
# 路线：(x, 马蹄所在的 y)。浮云顶 → 空天 → 云塔顶 → 右边的云堤
def _path_table():
    """路线：沿积云照片的云顶走（cloud_top_profile 平滑后），两朵云之间的空天里走一段平缓的弧（"在天上飄"）。"""
    def make():
        from scipy.ndimage import gaussian_filter1d
        wx, wy = Y.cloud_top_profile()
        xs = np.arange(-30.0, 34.0, 0.25)
        prof = np.interp(xs, wx, wy)
        prof = gaussian_filter1d(prof, 5.0)
        a, b = 0.0, 13.6                             # 空天的两端
        ya, yb = float(np.interp(a, xs, prof)), float(np.interp(b, xs, prof))
        u = np.clip((xs - a) / (b - a), 0, 1)
        arc = ya + (yb - ya) * (3 * u * u - 2 * u ** 3) + 0.4 * np.sin(np.pi * u)
        inside = (xs > a) & (xs < b)
        path = np.where(inside, np.maximum(prof, arc), prof)
        # 云塔右边是陡坡：骑士不跟着沉下去，而是从塔顶往右缓缓走下，走进天空（长矛在这里脱手）
        c = 19.6
        yc = float(np.interp(c, xs, path))
        path = np.where(xs > c, np.maximum(path, yc - 0.35 * (xs - c)), path)
        return xs, gaussian_filter1d(path, 2.0)
    return cached("pathtable", make)


def path_y(x):
    xs, ys = _path_table()
    return np.interp(x, xs, ys)


SINK = 0.35                                       # 马蹄陷进云里的深度
GAIT_HZ = 2.1                                     # 一步的频率
T_TILT0, T_DROP = 47.15, 47.70                    # 长矛开始下压；脱手（"蕎"之前一拍，L07 开始）
T_SWITCH = 48.37                                  # 镜头穿过近云、画面全白的一刻：天空换成屋里（见 fall.whiteout_items）


def knight_x(t):
    """长矛脱手以后，骑士加速往右远去，在镜头下移、穿过近云之前离开画面，不和下落的刀挤在一起。"""
    u = max(t - T_DROP, 0.0)
    return X_ENTER + SPEED * (t - T_ENTER) + 0.5 * 70.0 * u * u


def stepped(t, fps=12.0):
    """按每秒 12 张取样的时间：每 1/12 秒跳一格。先取到所在的那一帧（每秒 60 帧）的时刻，同一帧的几个子帧落在
    同一格里，运动模糊不会把相邻两张叠成重影。"""
    tf = round(t * 60.0) / 60.0
    return math.floor(tf * fps + 1e-6) / fps


def knight_pose(t):
    """(马蹄着地点 x, y, 转角度数)。起伏和摇摆按每秒 12 张更新。"""
    x = knight_x(t)
    ts = stepped(t)
    ph = 2 * math.pi * GAIT_HZ * ts
    bob = 0.025 * KNIGHT_H * abs(math.sin(ph))    # 每一步把人和马往上送一下
    rock = 2.2 * math.sin(ph + 0.6)               # 前后摇摆
    y = float(path_y(x)) - SINK + bob
    return x, y, rock


def knight_tex():
    def make():
        b, l, hand, tip = KN.textures()
        return Tex(b), Tex(l), hand, tip
    return cached("knight_tex", make)


def _rot(v, deg):
    a = math.radians(deg)
    return np.array([v[0] * math.cos(a) - v[1] * math.sin(a), v[0] * math.sin(a) + v[1] * math.cos(a)])


def lance_angle(t):
    """长矛相对原图的转角（度，负为顺时针，即矛尖往下压）。"""
    if t < T_TILT0:
        return 0.0
    u = ramp(t, T_TILT0, T_DROP)
    return -88.0 * float(ease(u)) ** 1.3


def knight_items(t, opacity=1.0):
    if t < T_ENTER - 0.05 or t >= T_SWITCH:
        return []
    body, lance, hand, tip = knight_tex()
    h, w = body.data.shape[:2]
    W, H = w / PX_PER_U, h / PX_PER_U
    x, y, rock = knight_pose(t)
    # 平面中心相对马蹄着地点的偏移（世界单位，y 向上），绕着地点摇摆
    off = np.array([(w / 2 - ANCHOR[0]) / PX_PER_U, (ANCHOR[1] - h / 2) / PX_PER_U])
    c = np.array([x, y]) + _rot(off, rock)
    items = [Plane(body, center=(c[0], c[1], Z_SKY + 0.30), size=(W, H), rot=(0, 0, rock), group="past",
                   opacity=opacity, stack="knight")]
    if t < T_DROP:
        hand_w = np.array([x, y]) + _rot(np.array([(hand[0] - ANCHOR[0]) / PX_PER_U, (ANCHOR[1] - hand[1]) / PX_PER_U]), rock)
        ang = rock + lance_angle(t)
        loff = np.array([(w / 2 - hand[0]) / PX_PER_U, (hand[1] - h / 2) / PX_PER_U])
        lc = hand_w + _rot(loff, ang)
        items.append(Plane(lance, center=(lc[0], lc[1], Z_SKY + 0.31), size=(W, H), rot=(0, 0, ang), group="past",
                           opacity=opacity, stack="knight"))
    return items


def lance_state_at_drop():
    """脱手瞬间长矛的握手点位置与转角（世界坐标），供下落使用。"""
    body, lance, hand, tip = knight_tex()
    x, y, rock = knight_pose(T_DROP - 1e-4)
    hand_w = np.array([x, y]) + _rot(np.array([(hand[0] - ANCHOR[0]) / PX_PER_U, (ANCHOR[1] - hand[1]) / PX_PER_U]), rock)
    return hand_w, rock + lance_angle(T_DROP - 1e-4)


# ---------------------------------------------------------------- 天上的歌词

L06 = L.trad(L.lyric(6))                          # 寂寞的　白雲騎士　在天上飄
CHAR_H = 2.3
TEXT_Y = 19.9
TEXT_X0 = -17.6
STEP = 2.75
GAP = 1.6                                          # 乐句之间多空一点


def text_layout():
    out, x = [], TEXT_X0
    k = 0
    for ch in L06:
        if ch == "　":
            x += GAP
            continue
        out.append((ch, x, T(6, k)))
        x += STEP
        k += 1
    return out


def text_items(t):
    if t < T(6, 0) - 0.05 or t >= T_SWITCH:
        return []
    items = []
    for ch, x, tc in text_layout():
        if t < tc - 0.03:
            continue
        a = float(ease((t - tc + 0.03) / 0.16))
        # 字落定时略带一点下沉，像墨写上去
        dy = 0.12 * (1 - a)
        items.append(TextPlane(ch, kind="serif", weight=700, height=CHAR_H, color=INK, center=(x, TEXT_Y - dy, Z_SKY + 0.4),
                               group="past", opacity=a, stack="l06text"))
    return items


# ---------------------------------------------------------------- 云里的旧字

OLD = L.trad("寂寞嫦娥舒广袖")
OLD_POS = (15.6, 7.5)                              # 云塔受光最亮的一面
OLD_H = 0.85

INK_GLSL = r"""
uniform sampler2D cloudlum;     // 云的亮度
uniform vec4 cloud_rect;        // 云照片的世界范围：x0、y 顶、宽、高
vec4 material(vec4 base) {
    vec2 p = v_wpos.xy;
    vec2 uv = vec2((p.x - cloud_rect.x) / cloud_rect.z, (cloud_rect.y - p.y) / cloud_rect.w);
    float cl = texture(cloudlum, uv).r;
    // 只在云亮的地方显出来，像是云的亮部里透出的一层旧字；云薄、云暗的地方就没有
    float k = smoothstep(0.22, 0.48, cl);
    return base * k;
}
"""
register_material("cloudink_b", INK_GLSL)


def old_items(t, k=1.0):
    """云里的旧字。云的高光在调色时已经接近饱和，正片叠底在那里不起作用，所以按普通叠放、低不透明度画上去。"""
    if k <= 0.002:
        return []
    import bed as B
    cx, cy, W, H = Y.cloud_geom()
    uni = {"cloudlum": B.cloud_lum_tex(), "cloud_rect": (cx - W / 2, cy + H / 2, W, H)}
    return [TextPlane(OLD, kind="fang", weight=400, height=OLD_H, color=RED, center=(*OLD_POS, Z_SKY + 0.05),
                      vertical=True, valign="top", group="past", opacity=0.50 * k, material="cloudink_b", uniforms=uni,
                      stack="cloudbank")]


# ---------------------------------------------------------------- 骑士陷进云里

FRONT_GLSL = r"""
uniform sampler2D pathtex;      // 路线：R 通道为马蹄所在的 y
uniform vec2 path_x;            // 路线覆盖的 x 范围
uniform float band;             // 路线以下多深的云挡在骑士前面
vec4 material(vec4 base) {
    float u = clamp((v_wpos.x - path_x.x) / (path_x.y - path_x.x), 0.0, 1.0);
    float yp = texture(pathtex, vec2(u, 0.5)).r;
    // 只留路线以下的云（马腿陷在里面），往上 0.6 个单位内渐隐，远离路线处也不画（不挡别的东西）
    float k = smoothstep(yp + 0.15, yp - 0.55, v_wpos.y) * smoothstep(yp - band - 1.5, yp - band, v_wpos.y);
    // 只在云厚的地方挡住马腿：云边上半透明的絮不挡，免得把马切成碎块
    k *= smoothstep(0.55, 0.85, base.a);
    return base * k;
}
"""
register_material("cloudfront_b", FRONT_GLSL, defaults={"path_x": (-30.0, 34.0), "band": 1.0})


def path_tex():
    def make():
        xs = np.linspace(-30.0, 34.0, 1024)
        ys = path_y(xs) - SINK
        a = np.zeros((1, len(xs), 4), np.float32)
        a[0, :, 0] = ys
        a[0, :, 3] = 1.0
        a[0, :, 1] = 2.0                                  # 让数组含有大于 1 的值，按半精度上传，保留精度
        return Tex(a, premultiplied=True, mipmap=False)
    return cached("pathtex", make)


def front_cloud_items(t, opacity=1.0):
    """云堤再画一遍，只取路线以下的一窄条，放在骑士前面：马蹄和腿陷进云顶。"""
    if t < T_ENTER - 0.1 or t >= T_SWITCH:
        return []
    cx, cy, W, H = Y.cloud_geom()
    return [Plane(Y.cloud_tex(), center=(cx, cy, Z_SKY + 0.34), size=(W, H), group="past", opacity=opacity,
                  material="cloudfront_b", uniforms={"pathtex": path_tex()}, stack="knight")]


# ---------------------------------------------------------------- 马蹄下的一缕云

MIST_W = 15.0                                     # 世界宽度；高按贴图比例
MIST_SRC = (130, 1350, 1050, 1800)                # 取自第二张积云照片左下的一排小云团（x0, y0, x1, y1，像素）
MIST_TOP = 0.20                                   # 云团上沿约在贴图 20% 高处


def mist_tex():
    """一缕从马蹄前飘过的云：取第二张积云照片（Lance Vanlewen，CC BY-SA 4.0）左下一排小云团，按与云堤相同的
    方法抠出、调成暖色，下半部和两端淡出。放大后的版画在马前腿处有一道直的截断线（原画里前腿被房子挡住），
    这缕云遮住马蹄以下，骑士像是踏着一小团云走。"""
    def make():
        from scipy.ndimage import gaussian_filter
        from common import lum, photo
        x0, y0, x1, y1 = MIST_SRC
        im = photo(Y.FAR_PHOTO)[y0:y1, x0:x1]
        r, g, b = im[..., 0], im[..., 1], im[..., 2]
        lu = lum(im)
        chroma = b - (r + g) / 2
        a = np.clip((0.19 - chroma) / 0.11, 0, 1) * np.clip((lu - 0.25) / 0.2, 0, 1)
        a = gaussian_filter(a, 1.2)
        h, w = a.shape
        v = np.arange(h)[:, None] / h
        u = np.arange(w)[None, :] / w
        a = a * np.clip((1.0 - v) / 0.55, 0, 1) ** 1.2 * np.clip(np.minimum(u, 1 - u) / 0.16, 0, 1) ** 1.3
        a = a * np.clip(v / 0.06, 0, 1)            # 上边也淡出，裁切处不留直边
        grey = lu[..., None] * np.ones(3)
        col = grey * 0.85 + im * 0.15
        k = np.clip((lu - 0.35) / 0.6, 0, 1)[..., None]
        col = col * (np.array([0.80, 0.74, 0.70]) * (1 - k) + np.array([1.16, 1.08, 0.92]) * k) * (1.0 + 0.35 * k ** 2)
        col = 0.10 + col * 1.08
        return Tex(np.dstack([col, a]).astype(np.float32))
    return cached("hoofmist", make)


def mist_items(t, opacity=1.0):
    if t < T_ENTER - 0.1 or t >= T_SWITCH:
        return []
    tex = mist_tex()
    h, w = tex.data.shape[:2]
    MH = MIST_W * h / w
    x = knight_x(t)
    drift = 1.0 - 0.75 * (t - T_ENTER)              # 相对骑士慢慢往后漂：云从马蹄前飘过
    top = float(path_y(x)) - SINK + 0.13 * KNIGHT_H # 云团上沿在马蹄以上约 0.13 个骑士高处，盖住前腿的截断线
    cy = top + MIST_TOP * MH - MH / 2
    return [Plane(tex, center=(x + drift, cy, Z_SKY + 0.36), size=(MIST_W, MH), group="past", opacity=opacity,
                  stack="knight")]
