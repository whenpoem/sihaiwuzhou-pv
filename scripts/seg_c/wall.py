"""副歌一样片：标语墙（L10），由样张 B 的做法改写而成，分辨率提高一倍，并拆成可以动画的几层。

墙面坐标：宽 WALL_W = 38、高 WALL_H = 15（世界单位），贴图每单位 PPU = 200 像素，原点在左上角，u 向右、v 向下。
墙在世界里的位置见 scene.py（左缘在 plan.WALL.x - 7，墙头在 plan.WALL.y + 8）。

贴图：
  albedo  uint8 RGB：砖、石灰、褪色剥落的红漆标语"抓革命　促生產"；
  aux1    float RGBA：R 铁水覆盖率，G 铁水流到该处的时刻，B 铁水的基础温度（源头热、往下冷），A 刷白带的覆盖范围；
  aux2    float RGBA：R 刷子前沿的逐行错动（单位），G 刷毛纹理，B 红色渗出的强度，A 渗出先后的随机场；
  warm    float RGBA（每单位 50 像素）：R 铁水投到墙面上的暖光，G 铁水周围一圈紧贴的光晕，B 该处光晕亮起的时刻。
时刻相对 T_BASE。显卡材质 wall_c（mats.py）按 u_time 与刷子前沿的位置合成每一帧。
"""
import sys
from pathlib import Path

import numpy as np
import skia
from scipy.ndimage import gaussian_filter, minimum_filter

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "style"))
import look as L  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / "data" / "cache" / "seg_c"
VERSION = 2
WALL_W, WALL_H = 38.0, 15.0
PPU = 200
K = PPU / 100                       # 相对样张 B（每单位 100 像素）的倍数
WW, WH = int(WALL_W * PPU), int(WALL_H * PPU)
T_BASE = 50.0
LEAD_FINAL = 24.8                   # 刷白最终停在"促"字中间（墙面坐标，单位）
BAND = (7.70, 9.75)                 # 刷白带的上下沿（v，单位）
LYRIC = dict(x=10.1, baseline=4.9, size=1.78)     # 歌词在墙面上的位置（u, v，单位）与字号
# 五道铁水：起点 u（单位）、长度（单位）、宽度（单位）、流到墙头的时刻（秒）
STREAMS = [(4.9, 11.5, 0.42, 58.22), (5.9, 7.2, 0.28, 58.31), (7.3, 9.8, 0.36, 58.27), (8.2, 5.0, 0.22, 58.42),
           (9.3, 8.0, 0.30, 58.35)]


def arrival(s0, d):
    """铁水前沿流到距墙头 d 单位处的时刻：开始快，越往下越慢（边流边冷却变稠）。"""
    return s0 + d / 7.0 + d * d / 30.0


def bricks(rng):
    bw, bh, mort = int(134 * K), int(46 * K), int(6 * K)
    col = np.zeros((WH, WW, 3), np.float32)
    joint = np.zeros((WH, WW), np.float32)
    for r in range(WH // bh + 1):
        off = (r % 2) * bw // 2
        y0 = r * bh
        for c in range(-1, WW // bw + 2):
            x0 = c * bw - off
            tone = np.array([0.50, 0.27, 0.19]) * rng.uniform(0.75, 1.15) + rng.normal(0, 0.02, 3)
            col[y0:y0 + bh, max(0, x0):max(0, x0 + bw)] = tone
        joint[y0:y0 + mort] = 1
        for c in range(-1, WW // bw + 2):
            x0 = c * bw - off
            if 0 <= x0 < WW:
                joint[y0:y0 + bh, x0:x0 + mort] = 1
    return col, gaussian_filter(joint, 1.2 * K)


def _surface():
    return skia.Surface(skia.ImageInfo.Make(WW, WH, skia.kRGBA_8888_ColorType, skia.kPremul_AlphaType))


def build(seed=4):
    CACHE.mkdir(parents=True, exist_ok=True)
    names = [CACHE / f"wall_{k}_v{VERSION}.npy" for k in ("albedo", "aux1", "aux2", "warm")]
    if all(p.exists() for p in names):
        return [np.load(p) for p in names]
    L.low_priority()
    rng = np.random.default_rng(seed)
    brick, joint = bricks(rng)
    thick = 0.65 * L.fbm(WH, WW, 420 * K, 5, seed) + 0.35 * L.fbm(WH, WW, 60 * K, 4, seed + 1)
    wash = np.clip((thick - 0.2) * 3.0, 0, 1)
    lime = np.array([0.86, 0.85, 0.80], np.float32)
    streak = gaussian_filter(rng.normal(0, 1, (WH, WW)).astype(np.float32), (90 * K, 3 * K))
    streak = np.clip(streak / streak.std() * 0.5 + 0.5, 0, 1) * np.linspace(0.2, 1.0, WH, dtype=np.float32)[:, None]
    alb = brick * (1 - wash[..., None]) + lime * (1 - 0.14 * streak[..., None]) * wash[..., None]
    alb *= (1 - 0.25 * joint * (1 - wash))[..., None]
    del brick, streak, thick

    f = L.font("sans", 900, 560 * K, scale_x=0.86)
    text = L.trad("抓革命　促生产")
    tw = L.line_width(text, f)
    s = _surface()
    s.getCanvas().drawString(text, (WW - tw) / 2, 1140 * K, f, L.white_paint())
    slogan = L.to_np(s)[..., 3]
    rough = L.fbm(WH, WW, 12 * K, 3, seed + 2)
    slogan_r = np.clip((gaussian_filter(slogan, 2.5 * K) - 0.5 + (rough - 0.5) * 0.5) * 6 + 0.5, 0, 1)
    flake = L.fbm(WH, WW, 40 * K, 4, seed + 3)
    paint = slogan_r * np.clip(0.55 + 0.45 * L.fbm(WH, WW, 300 * K, 3, seed + 4), 0, 1) * (flake < 0.68)
    red = L.C["red"] * np.array([1.18, 1.0, 1.0])
    alb = alb * (1 - paint[..., None]) + red * paint[..., None]
    del rough, flake, paint

    # 刷白带：上下沿不齐；前沿逐行错动；刷毛纹理；红色渗出
    yy = np.arange(WH, dtype=np.float32)[:, None]
    xx = np.arange(WW, dtype=np.float32)[None, :]
    # 刷白带由十几笔横向的刷痕拼成：每一笔的上下沿高低略有不同、略微倾斜，笔与笔之间有重叠；笔头处是钝的，
    # 笔尾墨（白灰）用尽，刷毛一缕缕断开，形成飞白；上下沿再加一点高频的毛边
    band = np.zeros((WH, WW), np.float32)
    srng = np.random.default_rng(seed + 11)
    hair = gaussian_filter(srng.normal(0, 1, (WH, WW)).astype(np.float32), (0.8 * K, 26 * K))
    hair = hair / (hair.std() + 1e-6)
    fuzz_t = (L.fbm(1, WW, 9 * K, 3, seed + 12)[0] - 0.5) * 16 * K
    fuzz_b = (L.fbm(1, WW, 9 * K, 3, seed + 13)[0] - 0.5) * 16 * K
    x = -120 * K
    while x < WW:
        ln = srng.uniform(950, 1750) * K
        t0 = 770 * K + srng.normal(0, 16 * K)
        b0 = 975 * K + srng.normal(0, 14 * K)
        slope = srng.normal(0, 0.014)
        dx = xx - x
        top = t0 + slope * dx + fuzz_t[None, :]
        bot = b0 + slope * dx * 0.8 + fuzz_b[None, :]
        u = dx / ln
        along = np.clip(u / 0.03, 0, 1) * (u < 1.0)
        dry = np.clip((u - 0.72) / 0.28, 0, 1)                         # 笔尾：越往后刷毛断得越多
        st = ((yy > top) & (yy < bot)).astype(np.float32) * along
        st *= np.clip(1.0 - dry * (1.6 - hair * 0.9), 0, 1)
        band = np.maximum(band, st)
        x += ln * srng.uniform(0.72, 0.86)
    band = gaussian_filter(band, 1.2 * K)
    wob = (40 * np.sin(yy / (37 * K)) + 30 * (L.fbm(WH, 1, 30 * K, 3, seed + 5)[:, :1] - 0.5)) * K / PPU
    bristle = gaussian_filter(rng.normal(0, 1, (WH, WW)).astype(np.float32), (1.2 * K, 60 * K))
    bristle = np.clip(bristle / bristle.std() * 0.5 + 0.5, 0, 1)
    bleed = gaussian_filter(slogan, 7 * K) * (0.45 + 0.55 * L.fbm(WH, WW, 50 * K, 3, seed + 6)) * band
    order = L.fbm(WH, WW, 80 * K, 3, seed + 7)

    # 铁水：覆盖率、温度、流到的时刻
    m_all = np.zeros((WH, WW), np.float32)
    temp_all = np.zeros((WH, WW), np.float32)
    arr_all = np.full((WH, WW), 99.0, np.float32)
    for k, (u0, ln, w0, s0) in enumerate(STREAMS):
        sm, st, sa = _surface(), _surface(), _surface()
        cm, ct, ca = sm.getCanvas(), st.getCanvas(), sa.getCanvas()
        y, x = -0.4 * PPU, u0 * PPU
        pts = []
        while y < ln * PPU:
            pts.append((x, y))
            y += 10 * K
            x += rng.normal(0, 1.2 * K) + 0.5 * K * np.sin(y / (70 * K) + k)
        wobw = gaussian_filter(rng.normal(0, 1, len(pts)), 4)
        wobw = wobw / (np.abs(wobw).max() + 1e-6)
        span = arrival(s0, ln) - s0 + 0.2

        def enc(yp):
            return float(np.clip((arrival(s0, max(yp, 0) / PPU) - s0) / span, 0, 1))
        for i in range(len(pts) - 1):
            u = i / len(pts)
            wdt = w0 * PPU * (1 - 0.55 * u) * (0.8 + 0.35 * wobw[i])
            tp = 1.0 - 0.75 * u ** 0.8
            cap = dict(StrokeWidth=wdt, StrokeCap=skia.Paint.kRound_Cap, AntiAlias=True)
            cm.drawLine(*pts[i], *pts[i + 1], skia.Paint(Color=skia.Color4f(1, 1, 1, 1), **cap))
            ct.drawLine(*pts[i], *pts[i + 1], skia.Paint(Color=skia.Color4f(tp, tp, tp, 1), **cap))
            e = enc(pts[i][1])
            ca.drawLine(*pts[i], *pts[i + 1], skia.Paint(Color=skia.Color4f(e, e, e, 1), **cap))
        for j in range(int(ln / 2.6)):
            i = int(rng.integers(len(pts) // 4, len(pts) - 1))
            xb, yb = pts[i]
            r = w0 * PPU * rng.uniform(0.45, 0.7) * (1 - 0.4 * i / len(pts))
            tp = 1.0 - 0.75 * (i / len(pts)) ** 0.8
            e = enc(yb)
            for cv, val in ((cm, 1.0), (ct, tp), (ca, e)):
                cv.drawOval(skia.Rect(xb - r, yb - r * 0.8, xb + r, yb + r * 1.3),
                            skia.Paint(Color=skia.Color4f(val, val, val, 1), AntiAlias=True))
        xe, ye = pts[-1]
        r = w0 * PPU * 0.42
        for cv, val in ((cm, 1.0), (ct, 0.25), (ca, 1.0)):
            cv.drawOval(skia.Rect(xe - r, ye - r * 0.4, xe + r, ye + r * 1.6),
                        skia.Paint(Color=skia.Color4f(val, val, val, 1), AntiAlias=True))
        m = L.to_np(sm)[..., 3]
        tp_ = L.to_np(st)[..., 0] / np.maximum(m, 1e-3)
        ar = s0 + L.to_np(sa)[..., 0] / np.maximum(m, 1e-3) * span
        upd = m > 0.02
        arr_all = np.where(upd, np.minimum(arr_all, ar), arr_all)
        temp_all = np.where(upd, np.maximum(temp_all, tp_), temp_all)
        m_all = np.maximum(m_all, m)

    aux1 = np.dstack([m_all, arr_all - T_BASE, np.clip(temp_all, 0, 1), band]).astype(np.float32)
    aux2 = np.dstack([np.broadcast_to(wob, (WH, WW)), bristle, bleed, order]).astype(np.float32)

    # 暖光与光晕（低分辨率）
    import cv2
    lw, lh = int(WALL_W * 50), int(WALL_H * 50)
    heat = cv2.resize(m_all * np.clip(temp_all, 0, 1) ** 1.5, (lw, lh), interpolation=cv2.INTER_AREA)
    warm = gaussian_filter(heat, 1.4 * 50) * 10.0 + gaussian_filter(heat, 0.4 * 50) * 2.5
    halo = gaussian_filter(heat, 0.07 * 50)
    arr_small = cv2.resize(np.where(m_all > 0.02, arr_all, 99.0), (lw, lh), interpolation=cv2.INTER_NEAREST)
    arr_small = minimum_filter(arr_small, size=9)
    warm4 = np.dstack([warm, halo, arr_small - T_BASE, np.ones_like(warm)]).astype(np.float32)

    albedo = (np.clip(alb, 0, 1) * 255 + 0.5).astype(np.uint8)
    for p, a in zip(names, (albedo, aux1, aux2, warm4)):
        np.save(p, a)
    return albedo, aux1, aux2, warm4


if __name__ == "__main__":
    import time
    t0 = time.time()
    out = build()
    print([a.shape for a in out], round(time.time() - t0, 1), "秒")
    from PIL import Image
    (ROOT / "renders" / "seg_c").mkdir(parents=True, exist_ok=True)
    Image.fromarray(out[0][::4, ::4]).save(ROOT / "renders" / "seg_c" / "wall_albedo_preview.png")
