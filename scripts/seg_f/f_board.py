"""L23 的行情屏：LED 点阵大屏上的指数"未来"一路下跌，触到熔断线，全部报价停住、转灰，只剩"暂停交易"。

L09 是旧日家里的一盏灯烧断：钨丝"未來"发白、烧断、灯灭。L23 与它成对：今天被强制停住的是市场。屏幕左侧是
指数栏，指数的名字就是歌词"未来"，下面是点数和涨跌，再下面接着写"被熔断于"；右侧是分时走势，一条白线带着冷青色的
面积在往前走，下方一条虚线是熔断线；右下是滚动的报价表，名字取自这首歌里的名词（四海、五洲、晨钟……），不出现真实的
指数名称、股票代码和日期。涨跌不用红绿：涨用冷青，跌用灰白，停住以后一律转灰；红色只留给旧字。

屏幕内容先在 1600×900 的画布上用 skia 画出（content），再由材质 led_board 变成 LED 点阵：每颗灯取内容在本格里的
平均亮度，画成一个圆点，灯之间是暗缝，未点亮的灯是深灰的小点；镜头离得远、一格不到三个像素时，点阵渐渐过渡为平均
亮度，不闪烁。旧字"一唱雄雞天下白"是屏幕上的烧屏残影（长时间显示同一画面留下的永久印子），在屏幕通电全白时显出
偏红的暗印，平时在暗处极淡。
"""
import math

import numpy as np
import skia

from f_common import RENDERS, RED, cached, ease, ramp, onsets, chars
import look
from engine import Tex, register_material

CW, CH = 1600, 900                      # 内容画布的坐标（画法按这个尺寸写）
SC = 0.5                                # 实际栅格化的比例：800×450，每颗灯 2×2 个像素，逐帧重画省一半以上的时间
GRID = (400, 225)                       # LED 点阵：每颗灯 4×4 个内容像素

L23 = chars(23)                          # 未 来 被 熔 断 于 明 亮 的 深 夜 里
T23 = onsets(23)
T_NAME = T23[0]                          # "未"：指数名出现
T_WEAK = T23[1]                          # "来"：开始缓慢走弱
T_DROP = T23[2]                          # "被"：加速下跌
T_MELT = T23[3]                          # "熔"：加速下跌
T_HALT = T23[4]                          # "断"：触到熔断线，停住
T_YU = T23[5]                            # "于"
T_PAUSE = T_YU + 0.18                    # 报价与歌词退去，随后只剩"暂停交易"
T_ZH0, T_ZH1 = 116.08, 116.26           # 第一遍刷新：全白退去，只剩 L22 末字"重"
T_BOOT0, T_BOOT1 = 116.45, 116.72       # 第二遍刷新："重"退去，刷新出行情
ZH_C, ZH_SIZE = (320.0, 200.0), 300.0   # "重"在屏幕上的位置（字框中心，内容像素）与字号

PREV = 3689.27                           # 昨收（虚构）
LIMIT = -7.0                             # 熔断线（%）
PCT_TOP, PCT_BOT = 1.6, -8.4             # 走势图纵轴范围
CHART = (700, 70, 1560, 560)             # 走势图区域 (x0, y0, x1, y1)
TABLE = (700, 610, 1560, 880)            # 报价表区域
NAMES = ["四海", "五洲", "晨钟", "晚灯", "风帆", "单车", "风筝", "拼图", "尘埃", "白云", "锁孔", "风雷",
         "艳阳", "衬布", "荞麦", "晨星", "回声", "长街"]

# ---------------------------------------------------------------- 材质

register_material("f_led_board", """
uniform vec2 led_grid;          // 点阵的列数、行数
uniform float led_r;            // 灯的半径（占一格的比例）
uniform float led_gain;
uniform vec3 led_off;           // 未点亮的灯
uniform float led_glow;
uniform float led_alpha;       // 灯不亮处的不透明度：透明 LED 屏，暗处透出后面的城市
uniform float led_power;
vec4 material(vec4 base) {
    vec2 g = v_uv01 * led_grid;
    vec2 cell = floor(g);
    vec2 f = fract(g) - 0.5;
    vec2 ts = vec2(textureSize(u_tex, 0));
    float lod = log2(max(ts.x / led_grid.x, 1.0));
    vec3 c = textureLod(u_tex, (cell + 0.5) / led_grid, lod).rgb;
    float px = max(fwidth(g.x), fwidth(g.y));           // 每个画面像素跨过几颗灯
    float r = length(f);
    float aa = max(px * 0.75, 0.02);
    float d = smoothstep(led_r + aa, led_r - aa, r);
    float hot = 1.0 + 0.35 * exp(-r * r * 30.0);          // 灯芯略亮
    float cov = 3.14159 * led_r * led_r;
    float far = smoothstep(0.22, 0.55, px);               // 一格不到约 3 个像素时过渡为平均亮度
    vec3 lit = mix(c * d * hot, textureLod(u_tex, v_uv01, lod) .rgb * cov * 1.12, far);
    vec3 off = led_off * mix(d, cov, far);
    vec3 glow = textureLod(u_tex, v_uv01, lod + 2.5).rgb * led_glow;
    float on = clamp(dot(c, vec3(0.33)) * 4.0, 0.0, 1.0);
    vec3 col = (lit * led_gain + off * (1.0 - on) + glow) * led_power;
    float a = mix(led_alpha, 1.0, on * led_power) * led_power;
    return vec4(col, a);
}
""", defaults={"led_grid": GRID, "led_r": 0.36, "led_gain": 2.3, "led_off": (0.035, 0.040, 0.050), "led_glow": 0.22,
                   "led_alpha": 0.72, "led_power": 1.0})


# ---------------------------------------------------------------- 行情数据

def day_curve():
    """全天的分时曲线（虚构）：x 为 0–1 的交易时间，y 为相对昨收的涨跌幅（%）。前半段在零轴上方小幅波动。"""
    def make():
        rng = np.random.default_rng(23)
        n = 2000
        x = np.linspace(0, 1, n)
        steps = rng.normal(0, 1, n)
        walk = np.cumsum(steps) / math.sqrt(n) * 0.55
        walk -= np.linspace(0, walk[-1], n)                  # 去掉随机游走的整体漂移
        base = 0.62 + 0.22 * np.sin(x * 9.0 + 0.5) * np.exp(-x * 1.2) + 0.25 * x
        y = base + walk - walk[0]
        y += 0.06 * np.convolve(rng.normal(0, 1, n), np.ones(5) / 5, "same")
        return x, y
    return cached("day_curve", make)


def progress(t):
    """走势线画到的位置（0–1）。平时缓慢前进；"来"开始走弱以后走势线前进得快一些，下跌在走势图上是一段
    先平缓、后陡峭的斜线。"""
    if t < T_WEAK:
        return 0.52 + 0.035 * (t - 116.0)
    p0 = 0.52 + 0.035 * (T_WEAK - 116.0)
    u = min((t - T_WEAK) / (T_HALT - T_WEAK), 1.0)
    return p0 + 0.13 * u


def index_pct(t):
    """当前的涨跌幅（%）：平时沿曲线小幅波动；"来"开始缓慢走弱，"被"时加速，"断"时正好触到 −7% 熔断线。"""
    x, y = day_curve()
    if t < T_WEAK:
        return float(np.interp(progress(t), x, y))
    v0 = float(np.interp(progress(T_WEAK), x, y))
    v1 = v0 - 1.3                                       # "被"时的位置：已经走弱一截
    if t < T_DROP:
        u = (t - T_WEAK) / (T_DROP - T_WEAK)
        return v0 + (v1 - v0) * u ** 1.3 + 0.10 * math.sin(u * 19.0) * u * (1 - u) * 4
    u = min((t - T_DROP) / (T_HALT - T_DROP), 1.0)
    fall = u ** 1.9                                     # 越跌越快
    jag = 0.22 * math.sin(u * 31.0) * (1 - u) * u * 4
    return v1 + (LIMIT - v1) * fall + jag


def drop_path(t):
    """走弱与暴跌那一段的点列 (x, pct)，供走势图使用。"""
    ts = np.linspace(T_WEAK, min(t, T_HALT), 48)
    return np.array([[progress(s), index_pct(s)] for s in ts])


def table_rows():
    """报价表的行：(名字, 昨收, 平时的涨跌幅, 下跌开始的先后)。"""
    def make():
        rng = np.random.default_rng(5)
        rows = []
        for i, nm in enumerate(NAMES):
            rows.append((nm, float(rng.uniform(4.0, 68.0)), float(rng.normal(0.3, 1.1)), float(rng.uniform(0, 1))))
        return rows
    return cached("table_rows", make)


# ---------------------------------------------------------------- 画布

def _paint(rgb, a=1.0, **kw):
    return skia.Paint(Color=skia.Color4f(float(rgb[0]), float(rgb[1]), float(rgb[2]), a), AntiAlias=True, **kw)


def _text(c, s, x, y, f, rgb, align="left"):
    w = f.measureText(s)
    if align == "right":
        x -= w
    elif align == "center":
        x -= w / 2
    c.drawString(s, x, y, f, _paint(rgb))
    return w


UP = np.array([0.50, 0.90, 1.0])            # 涨：冷青
DOWN = np.array([0.80, 0.82, 0.86])         # 跌：灰白
GREY = np.array([0.30, 0.31, 0.33])         # 停住以后
LYR = np.array([1.0, 1.0, 1.0])


def zhong_mask():
    """"重"字（思源宋体 250）的覆盖率，与内容画布同尺寸。"""
    def make():
        import skia as sk
        f = look.font("serif", 250, ZH_SIZE)
        b = sk.Rect()
        w = f.measureText("重")
        x = ZH_C[0] - w / 2
        y = ZH_C[1] + ZH_SIZE * (0.88 - 0.5)                 # 字框中心在基线以上 0.38 em
        return _down(look.text_layer([("重", f, x, y, None)], CW, CH).astype(np.float32))
    return cached("board_zhong", make)


def ghost_mask():
    """烧屏残影"一唱雄雞天下白"的覆盖率（与内容画布同尺寸）：仿宋，横排在屏幕中部，笔画边缘略散开。"""
    def make():
        from scipy.ndimage import gaussian_filter
        f = look.font("fang", 400, 190)
        s = look.trad("一唱雄鸡天下白")
        w = f.measureText(s)
        g = _down(look.text_layer([(s, f, (CW - w) / 2, CH * 0.5 + 70, None)], CW, CH))
        return gaussian_filter(g, 1.1).astype(np.float32)
    return cached("board_ghost", make)


def _fonts():
    def make():
        return dict(name=look.font("serif", 250, 236), lyr=look.font("serif", 250, 140),
                    price=look.font("sans", 500, 128), chg=look.font("sans", 500, 58),
                    small=look.font("sans", 500, 44), cell=look.font("sans", 500, 48),
                    pause=look.font("sans", 700, 230))
    return cached("board_fonts", make)


def _down(a):
    """按 SC 缩小到实际的栅格尺寸（面积平均）。"""
    import cv2
    return cv2.resize(a, (int(CW * SC), int(CH * SC)), interpolation=cv2.INTER_AREA)


def content(t):
    """t 时刻屏幕上的画面（CH×CW×3，浮点，可超过 1）。"""
    F = _fonts()
    s = skia.Surface(int(CW * SC), int(CH * SC))
    c = s.getCanvas()
    c.scale(SC, SC)
    c.clear(skia.Color4f(0, 0, 0, 1))
    halted = t >= T_HALT
    gk = ramp(t, T_HALT, T_HALT + 0.12)                 # 转灰的进度
    keep = 1.0 - ramp(t, T_PAUSE, T_PAUSE + 0.15)       # 报价与歌词退去
    pause = ramp(t, T_PAUSE + 0.12, T_PAUSE + 0.30)     # 随后亮出"暂停交易"

    def tone(col):
        """停住以后颜色转灰，随后整体退去。"""
        col = np.asarray(col, float)
        return (col * (1 - gk) + GREY * gk) * keep

    pct = index_pct(t)
    tq = min(t, T_HALT)
    # ---- 走势图
    x0, y0, x1, y1 = CHART

    def Y(p):
        return y0 + (PCT_TOP - p) / (PCT_TOP - PCT_BOT) * (y1 - y0)

    def X(u):
        return x0 + u * (x1 - x0)
    if keep > 0:
        # 坐标格：很暗的横线，零轴是虚线
        for p in (1.0, 0.0, -2.0, -4.0, -6.0):
            col = tone(np.array([0.10, 0.12, 0.14]) * (1.6 if p == 0 else 1.0))
            eff = skia.DashPathEffect.Make([10, 8], 0) if p == 0 else None
            c.drawLine(x0, Y(p), x1, Y(p), _paint(col, StrokeWidth=3, PathEffect=eff))
        # 熔断线
        lim = tone(np.array([0.72, 0.76, 0.82]) * (1.0 + 0.6 * math.exp(-max(t - T_HALT, 0) / 0.2) * halted))
        c.drawLine(x0, Y(LIMIT), x1, Y(LIMIT), _paint(lim, StrokeWidth=5, PathEffect=skia.DashPathEffect.Make([22, 12], 0)))
        _text(c, "熔断线  -7.00%", x1, Y(LIMIT) - 14, F["small"], lim, "right")
        # 走势线与面积
        x, y = day_curve()
        p_now = progress(tq)
        m = x <= min(p_now, progress(T_WEAK))
        pts = np.c_[x[m], y[m]]
        if t >= T_WEAK:
            pts = np.vstack([pts, drop_path(t)])
        path = skia.Path()
        path.moveTo(X(pts[0, 0]), Y(pts[0, 1]))
        for u, p in pts[1:]:
            path.lineTo(X(u), Y(p))
        area = skia.Path(path)
        area.lineTo(X(pts[-1, 0]), y1)
        area.lineTo(X(pts[0, 0]), y1)
        area.close()
        acol = tone(np.array([0.05, 0.16, 0.21]))
        shader = skia.GradientShader.MakeLinear([(0, y0), (0, y0 + (y1 - y0) * 0.75)],
                                                [skia.Color4f(*acol, 1), skia.Color4f(0, 0, 0, 1)])
        c.drawPath(area, skia.Paint(Shader=shader, AntiAlias=True))
        c.drawPath(path, _paint(tone([1.05, 1.08, 1.12]), StrokeWidth=6, Style=skia.Paint.kStroke_Style,
                                StrokeJoin=skia.Paint.kRound_Join))
        # 当前点：一个亮点，平时缓慢呼吸
        hx, hy = X(pts[-1, 0]), Y(pts[-1, 1])
        br = 1.0 + 0.3 * math.sin(t * 9.0) * (not halted)
        c.drawCircle(hx, hy, 11, _paint(tone(np.array([1.2, 1.25, 1.3]) * br)))
        c.drawLine(hx, y0, hx, y1, _paint(tone([0.16, 0.18, 0.20]), StrokeWidth=2))
        # 报价表：三列，向上滚动；暴跌时按先后依次翻成下跌
        tx0, ty0, tx1, ty1 = TABLE
        rows = table_rows()
        rh = 88
        scroll = (tq - 116.0) * 52.0
        c.save()
        c.clipRect(skia.Rect(tx0, ty0, tx1, ty1))
        ncol = 2
        cw = (tx1 - tx0) / ncol
        first = int(scroll // rh)
        for r in range(first, first + 5):
            yy = ty0 + 62 + r * rh - scroll
            for k in range(ncol):
                i = (r * ncol + k) % len(rows)
                nm, prev, pc, lag = rows[i]
                drop = ramp(tq, T_WEAK + 0.10 + lag * 0.30, T_HALT - 0.02)
                flick = 0.15 * math.sin(tq * 13.0 + i * 2.1) * (1 - drop)
                v = pc + flick + (LIMIT - 0.5 * lag - pc) * drop ** 1.6
                col = UP if v >= 0 else DOWN
                xx = tx0 + k * cw + 20
                _text(c, nm, xx, yy, F["cell"], tone(np.array([0.78, 0.80, 0.84])))
                _text(c, f"{prev * (1 + v / 100):.2f}", xx + cw * 0.52, yy, F["cell"], tone(col), "right")
                _text(c, f"{v:+.2f}%", xx + cw - 36, yy, F["cell"], tone(col * 0.9), "right")
        c.restore()
        c.drawLine(tx0, ty0, tx1, ty0, _paint(tone([0.14, 0.16, 0.18]), StrokeWidth=3))
        # 指数栏：点数与涨跌
        price = PREV * (1 + pct / 100)
        col = UP if pct >= 0 else DOWN
        _text(c, f"{price:.2f}", 56, 450, F["price"], tone(col * 1.05))
        _text(c, f"{price - PREV:+.2f}   {pct:+.2f}%", 112, 540, F["chg"], tone(col * 0.95))
        tri = skia.Path()
        if pct >= 0:
            tri.addPoly([skia.Point(60, 538), skia.Point(82, 500), skia.Point(104, 538)], True)
        else:
            tri.addPoly([skia.Point(60, 500), skia.Point(82, 538), skia.Point(104, 500)], True)
        c.drawPath(tri, _paint(tone(col)))
        c.drawLine(40, 600, 640, 600, _paint(tone([0.14, 0.16, 0.18]), StrokeWidth=3))
    # ---- 歌词：指数名"未来"，下面写"被熔断于"；停住时不转灰，随报价一起退去
    name_k = keep
    for i, ch in enumerate(L23[:2]):
        if t >= T23[i] - 0.02:
            a = min((t - T23[i] + 0.02) / 0.06, 1.0)
            flare = 1.0 + 0.6 * math.exp(-max(t - T23[i], 0) / 0.2)
            _text(c, ch, 52 + i * 240, 262, F["name"], LYR * a * flare * name_k)
    for i, ch in enumerate(L23[2:6]):
        k = i + 2
        if t >= T23[k] - 0.02:
            a = min((t - T23[k] + 0.02) / 0.06, 1.0)
            flare = 1.0 + 0.6 * math.exp(-max(t - T23[k], 0) / 0.2)
            _text(c, ch, 58 + i * 146, 770, F["lyr"], LYR * a * flare * name_k)
    # ---- 暂停交易
    if pause > 0:
        a = pause * (0.92 + 0.08 * math.sin(t * 5.0))
        f = F["pause"]
        _text(c, "暂停交易", CW / 2, CH / 2 + 82, f, np.array([0.86, 0.88, 0.92]) * a, "center")
    img = s.makeImageSnapshot().toarray()[..., :3].astype(np.float32) / 255
    if T_HALT <= t < T_HALT + 0.10:                     # 触到熔断线的一瞬：整屏的灯闪一下，再停在灰色上
        img = img * (1.0 + 1.6 * math.exp(-(t - T_HALT) / 0.025))
    img[..., :] = img[..., [2, 1, 0]] if _bgr() else img
    # 歌词与高光：skia 的 8 位画布存不下超过 1 的亮度，按亮度把白处整体抬高
    img *= 1.0 + 0.25 * np.clip(img.mean(2, keepdims=True) - 0.85, 0, None) / 0.15
    # 通电：先全白；第一遍由上往下逐行刷新，全白退去，屏上只剩上一句的末字"重"（E 段在交接前唱到它，
    # 字落在交接的冷白里，所以由这块屏幕把它写出来）；第二遍刷新，"重"退去，出现行情
    if t < T_BOOT1:
        yb = (np.arange(img.shape[0], dtype=np.float32)[:, None, None] / img.shape[0])
        zh = zhong_mask()[..., None] * 1.30
        f1 = ramp(t, T_ZH0, T_ZH1)
        f2 = ramp(t, T_BOOT0, T_BOOT1)
        first = (yb >= f1).astype(np.float32)               # 第一遍刷新还没到的行：仍是全白
        second = (yb < f2).astype(np.float32)               # 第二遍刷新已经到的行：行情
        mid = zh * (1 - first) + 1.35 * first
        img = img * second + mid * (1 - second)
    # 烧屏残影：亮处压暗、偏红；暗处是极淡的红印
    g = ghost_mask()[..., None]
    lum = img.mean(2, keepdims=True)
    img = img * (1 - 0.30 * g * np.clip(lum, 0, 1)) + RED * 0.85 * 0.30 * g * np.clip(lum, 0, 1)
    img += RED * 0.08 * g * (1 - np.clip(lum * 3, 0, 1))
    return img


_BGR = None


def _bgr():
    """skia 的 toarray() 在 Windows 上按 BGRA 排列；画一个纯红像素判断一次。"""
    global _BGR
    if _BGR is None:
        s = skia.Surface(2, 2)
        s.getCanvas().clear(skia.Color4f(1, 0, 0, 1))
        _BGR = bool(s.makeImageSnapshot().toarray()[0, 0, 2] > 200)
    return _BGR


def content_tex(t):
    """按帧缓存的屏幕画面纹理：同一帧的几个子帧共用一张。"""
    key = round(t * 60)
    hit = cached("board_tex_slot", lambda: {})
    if hit.get("k") != key:
        hit["k"] = key
        hit["tex"] = Tex(content(key / 60).astype(np.float16))
    return hit["tex"]


if __name__ == "__main__":
    from PIL import Image
    out = []
    for t in (116.5, 117.1, 117.6, 117.85, 118.0, 118.6):
        im = content(t)
        out.append(np.clip(im, 0, 1))
    grid = np.vstack([np.hstack(out[:3]), np.hstack(out[3:])])
    Image.fromarray((grid * 255).astype(np.uint8)).resize((2400, 900)).save(
        str(RENDERS / "board_content.png"))


def bezel_tex():
    """屏幕的外框：比屏幕略大一圈的深色边框，外缘一线冷光（直通 alpha，中间透明）。覆盖 (BW + 2m) × (BH + 2m)。"""
    def make():
        w, h = 1680, 980
        m = 40                                   # 对应内容画布上的 40 像素宽的边框
        s = skia.Surface(w, h)
        c = s.getCanvas()
        c.clear(skia.Color4f(0, 0, 0, 0))
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect(2, 2, w - 2, h - 2), 10, 10), _paint((0.035, 0.038, 0.045)))
        c.drawRRect(skia.RRect.MakeRectXY(skia.Rect(3, 3, w - 3, h - 3), 9, 9),
                    _paint((0.30, 0.33, 0.38), StrokeWidth=2.5, Style=skia.Paint.kStroke_Style))
        c.drawRect(skia.Rect(m, m, w - m, h - m), skia.Paint(Color=skia.Color4f(0, 0, 0, 0), BlendMode=skia.BlendMode.kClear))
        a = s.makeImageSnapshot().toarray().astype(np.float32) / 255
        if _bgr():
            a = a[..., [2, 1, 0, 3]]
        rgb = np.where(a[..., 3:4] > 0, a[..., :3] / np.maximum(a[..., 3:4], 1e-4), 0)
        return np.dstack([rgb, a[..., 3]]).astype(np.float32)
    return cached("board_bezel", make)
