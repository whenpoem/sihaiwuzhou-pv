"""翻板场：上万块双面翻板按时刻表翻转，起风时颤动、翘起边角，"吹"字时被风掀起、卷成旋风。

几何。场地是 360 × 150 块板，格距 1 个世界单位，铺在 z = 0 的地面上方，正对镜头（镜头朝 -z 往下看）。
板宽 0.975、厚 0.06，转轴离地 0.6（板由下面的支架托着）。第 c 列、第 r 行的板心在
x = c − 179.5、y = 74.5 − r，第 0 行在远端（画面上方），场地中心是原点。

显出是板。L33 时板拼得严丝合缝、没有一点倾斜，整片场地画成一块连续的漆面（floor_item，逐像素受光）：漆面在
逆光里一片发亮，横向的刷痕在高光里起伏，板缝只是高光里一道道很细的断口；L34 开头一道涟漪从镜头下方荡开，
涟漪经过的地方由一块块板接替，每块板被托起、晃两下，停在各自略有倾斜的位置上，板缝和深浅不一的漆色才显出来。

翻转。每块板有正反两面，翻转是绕自身水平轴（x 轴）转半圈。四幅图案（patterns.py）之间有三次翻转：
L33→L34（"集体活动"四个词各一波，从左往右）、L34→L35（"到"时从上往下翻、"吗"时停在半途侧立，"四"时
翻完出第一句，"五"时翻出第二句）、L35→BAND（"该……眼"时只有黑带里的板从左往右翻）。一块板翻过以后，朝上
的一面是新图案，朝下的一面留着上一幅的颜色，所以每帧按已翻次数的奇偶决定正反两面各漆什么颜色；翻过的板停在
π 的整数倍上，贴图不会跳变。起翻时刻只差几毫秒（一波翻转的前沿才整齐），翻转用时 0.25–0.29 秒，前段加速、
后段减速，落定时多转约 4 度再回落，像人手翻的。

风。L36 起风后几道阵风斜着扫过场地，经过时板的一边被掀起（最多约 50 度）、颤动，风过去后落回；"为我"时
风收住；鼓进入的那一下底鼓，全场一齐抖一下。"吹"时冲击波从场地中心以每秒约 700 单位向外推开，经过哪块板，
哪块板就被掀起：先绕被风兜住的那条边翻起，再被上升气流加速托向镜头，同时绕场地中心旋转；全联的十四个黄字
先各自整块飞起、在空中翻转，约 0.3 秒后才散成一块块板。

画法。板面和板边放在同一组粒子里（板边只给倾斜的板画，取朝镜头的那条长边），按深度逐个排序；倾斜的板在地上
的投影是另一组贴地的粒子；平放的板把板下的地面遮在阴影里，板立起或飞走后地面才被照亮（一张按块更新的正片叠底
贴图）。光照见 cards.py。
"""
import math

import numpy as np

from common import T, cached, smooth, smoother, out_cubic, hash01, RED, YELLOW, rot_axes, rot_x, euler_from_matrix
import cards as CD
import patterns as PT
from engine import register_material

COLS, ROWS = PT.COLS, PT.ROWS
N = COLS * ROWS
CARD_W, CARD_T, AXIS_Z = 0.975, 0.06, 0.6

# 板面颜色：深色、褪色红、美术字黄（正对灯光时的漆色）
DARK_C = np.array([0.075, 0.062, 0.056], np.float32)
PALETTE = np.stack([DARK_C, RED * 0.92, YELLOW * 1.02 * np.array([1.0, 1.0, 0.85])]).astype(np.float32)
EDGE_C = np.array([0.62, 0.53, 0.40], np.float32)

# ---------------------------------------------------------------- 时刻
T_STOP = T(33, 5)                                  # "停"
W1 = [T(34, 4), T(34, 5), T(34, 6), T(34, 7)]      # 集 体 活 动：四个词依次翻出
T_TO, T_MA = T(34, 8), T(34, 12)                   # 到 … 吗：从上往下翻，停在半途
T_SI, T_HAI, T_WU, T_ZHOU = T(35, 2), T(35, 3), T(35, 5), T(35, 6)
T_GAI, T_YAN = T(35, 9), T(35, 13)                 # 该 … 眼：黑带横穿
T_RANG, T_FAN, T_TENG = T(36, 0), T(36, 1), T(36, 2)
T_FENG, T_LEI = T(36, 4), T(36, 5)
T_WEI, T_WO, T_CHUI = T(36, 6), T(36, 7), T(36, 8)
T_KICK = 177.2633                                  # 鼓以一下底鼓进入
T_SHIVER = 167.95                                  # L34 开头：一道涟漪从镜头下方荡开，地面原来是一块块板
SHIVER_O = (-130.4, -39.2)
SHIVER_V = 380.0
HALF_ROW = (PT.BAND_R0 + PT.BAND_R1) // 2           # 75：第二波停在这一行


class Field:
    def __init__(self):
        c, r = np.meshgrid(np.arange(COLS), np.arange(ROWS))
        self.col, self.row = c.ravel(), r.ravel()
        self.x = (self.col - (COLS - 1) / 2).astype(np.float32)
        self.y = ((ROWS - 1) / 2 - self.row).astype(np.float32)
        rng = np.random.default_rng(1101)
        self.var = rng.integers(0, CD.N_VAR, N)
        self.jit = rng.normal(0, 0.006, N).clip(-0.015, 0.015)        # 起翻时刻的个体差（几毫秒，波前才连贯）
        self.dur = rng.uniform(0.25, 0.29, N)
        self.cj = (1.0 + rng.normal(0, 0.045, N)).astype(np.float32)  # 漆色深浅
        self.hue = rng.normal(0, 0.03, (N, 3)).astype(np.float32)
        self.yaw0 = np.radians(rng.normal(0, 0.5, N)).astype(np.float32)
        self.pitch0 = np.radians(rng.normal(0, 0.6, N)).astype(np.float32)
        self.z0 = (AXIS_Z + rng.normal(0, 0.012, N)).astype(np.float32)
        self.ph = rng.uniform(0, 2 * np.pi, N)
        self.ph2 = rng.uniform(0, 2 * np.pi, N)
        self.wk = rng.uniform(0.6, 1.4, N)                            # 对风的敏感程度
        self.P0 = np.stack([self.x, self.y, self.z0], 1)
        self.t_shiver = T_SHIVER + np.hypot(self.x - SHIVER_O[0], self.y - SHIVER_O[1]) / SHIVER_V
        self.t_shiver_max = float(self.t_shiver.max())
        self.pats = [PT.pattern(n).ravel() for n in ("L33", "L34", "L35", "BAND")]
        self.band = self.pats[3] != self.pats[2]
        band_rows = (self.row >= PT.BAND_R0) & (self.row <= PT.BAND_R1)
        self.band_part = band_rows
        at = CD.atlas()
        self.uv_face = at.index_uv(self.var)
        self.uv_seam = at.index_uv(CD.SEAM_I + self.var)
        self.uv_edge = at.index_uv(np.full(N, CD.EDGE_I))
        self.uv_shadow = at.index_uv(np.full(N, CD.SHADOW_I))
        self.atlas = at
        self.base = [PALETTE[p] for p in self.pats]
        self.tint = (self.cj[:, None] * (1 + self.hue)).astype(np.float32)

    # ------------------------------------------------------------ 翻转的进度
    @staticmethod
    def flip_profile(r):
        """翻转进度：r 为 (t − 起翻)/用时。前段加速、后段减速，落定时回弹约 4%。"""
        r = np.asarray(r, float)
        u = smoother(r)
        x = np.clip(r - 1.0, 0, None)
        over = 0.55 * x * np.exp(-x * 9.0)          # 只向前多转一点再回落到 1，峰值约 4 度
        return np.clip(u, 0, 1) + over

    def u1(self, t):
        """L33→L34：四个词各一波，从左往右扫过各自那一段场地。"""
        starts = np.array([0, 68, 141, 214])
        k = (self.col >= 68).astype(int) + (self.col >= 141) + (self.col >= 214)
        t0 = np.array(W1)[k] - 0.12 + (self.col - starts[k]) / 73.0 * 0.20 + self.jit
        return self.flip_profile((t - t0) / self.dur)

    def u2(self, t):
        """L34→L35：上半场"到"时从上往下翻，到"吗"停在半途（板侧立着）；"四"时翻完，翻出第一句。
        下半场"五"时从中间往下翻，翻出第二句。"""
        top = self.row < HALF_ROW
        out = np.zeros(N)
        # 上半场：波前在"到"到"吗"之间从第 0 行推到第 75 行，越来越慢
        t_go = T_TO + 0.12
        front = HALF_ROW * float(out_cubic((t - t_go) / (T_MA - t_go + 0.12))) if t > t_go else -1.0
        passed = np.clip((front - self.row) / 9.0, 0, 1)                   # 波前过后九行内转到侧立
        # 侧立的角度带一点随机：多数在 80–100 度之间
        stand = 0.41 + (self.ph - np.pi) / np.pi * 0.008
        hold = smooth(passed, 0, 1) * stand
        t_rel = T_SI - 0.10 + self.row / HALF_ROW * 0.22 + self.jit             # "四"：从上往下翻完
        rest = self.flip_profile((t - t_rel) / (self.dur * 0.8))
        top_u = hold + (1 - hold) * rest * (front >= 0)
        out[top] = top_u[top]
        # 下半场
        t_b = T_WU - 0.10 + (self.row - HALF_ROW) / (ROWS - HALF_ROW) * 0.26 + self.jit
        bot_u = self.flip_profile((t - t_b) / self.dur)
        out[~top] = bot_u[~top]
        return out

    def u3(self, t):
        """L35→BAND：黑带里的板从左往右翻成深色，波前带一点起伏（样张 D 的做法）。"""
        span = T_YAN - T_GAI + 0.05
        front = COLS * 1.05 * float(smooth((t - T_GAI) / span, 0, 1)) if t > T_GAI - 0.05 else -10.0
        wob = front + 3.0 * np.sin(self.row / 4.0)
        r = (wob - self.col) / 10.0
        return np.where(self.band_part, self.flip_profile(r), 0.0)

    def flips(self, t):
        """(翻转角 θ, 正面颜色, 背面颜色)。θ 为 π × (已翻次数 + 当前进度)。

        一块双面板翻过一次，朝上的一面换成新图案，朝下的一面留着上一幅图案的颜色；所以静止时朝下那面是
        上一幅的颜色（还没翻过的板两面相同），正在翻的板两面分别是旧图案和新图案。板被风掀起、在空中翻滚时，
        两面的颜色因此不同。"""
        us = [self.u1(t), self.u2(t), self.u3(t)]
        parts = [np.ones(N, bool), np.ones(N, bool), self.band_part]
        theta = np.zeros(N)
        n_done = np.zeros(N, int)
        cur = self.base[0].copy()
        prev = self.base[0].copy()
        nxt = self.base[0].copy()
        active = np.zeros(N, bool)
        for j, (u, part) in enumerate(zip(us, parts)):
            done = part & (u >= 1.0)
            run = part & (u > 0) & (u < 1.0) & ~active
            prev = np.where(done[:, None], cur, prev)
            cur = np.where(done[:, None], self.base[j + 1], cur)
            nxt = np.where(run[:, None], self.base[j + 1], nxt)
            theta += np.where(part, np.clip(u, 0, None), 0.0)     # 回弹（略超过 1）也算进去
            n_done += done
            active |= run
        even = (n_done % 2) == 0
        down = np.where(active[:, None], nxt, prev)                # 朝下的一面
        front = np.where(even[:, None], cur, down)
        back = np.where(even[:, None], down, cur)
        return -theta * np.pi, front, back          # 翻转方向：板的上沿朝下转，正面先迎向远端的灯

    # ------------------------------------------------------------ 风
    def wind(self, t):
        """起风后每块板附加的 (pitch, yaw)，弧度。阵风是几道斜着扫过场地的波纹，"翻""腾"两字时最强；
        "为我"时风势收住；鼓进入的那一下底鼓，全场一齐抖一下。"""
        if t < T_RANG - 0.4 or t > T_CHUI + 0.05:
            return None
        env = float(smooth(t, T_RANG - 0.4, T_RANG + 0.3)) * (1.0 - float(smooth(t, T_WEI - 0.15, T_WO + 0.05)))
        g = np.zeros(N)
        # 阵风：(出发时刻, 方向角, 速度, 宽度, 强度)
        gusts = [(T_RANG - 0.2, 0.25, 260.0, 18.0, 0.6), (T_FAN - 0.45, 0.10, 300.0, 20.0, 1.0),
                 (T_FAN - 0.25, 0.12, 300.0, 12.0, 0.6),
                 (T_TENG - 0.40, 0.35, 320.0, 22.0, 1.15), (T_TENG - 0.22, 0.33, 320.0, 12.0, 0.7),
                 (T_TENG + 0.25, -0.15, 280.0, 18.0, 0.8),
                 (T_FENG - 0.30, 0.2, 300.0, 20.0, 0.85), (T_LEI - 0.15, 0.05, 330.0, 18.0, 0.75)]
        for t0, ang, v, w, a in gusts:
            d = self.x * math.cos(ang) + self.y * math.sin(ang)
            front = -230.0 + v * (t - t0)
            g += a * np.exp(-((d - front) / w) ** 2)
        # 颤动：每块板绕自己的轴以 7–10 赫兹抖，幅度随风势起伏
        tremble = (0.05 + 0.10 * np.clip(g, 0, 1)) * env * np.sin(t * 2 * np.pi * (7.0 + self.wk * 3.0) + self.ph)
        lift = np.clip(g, 0, 1.6) * self.wk * env
        # 阵风经过时，板的一边被风掀起（最大约 50 度），风过去后落回，带一点回摆
        pitch = 0.85 * lift * (0.75 + 0.25 * np.sin(self.ph2 + t * 9.0)) + tremble
        yaw = 0.25 * lift * np.sin(self.ph + t * 3.0) + 0.5 * tremble * np.cos(self.ph2)
        # 底鼓：全场一齐抖一下（从中心向外，很快衰减）
        r = np.hypot(self.x, self.y)
        u = t - T_KICK - r / 900.0
        jolt = np.where(u > 0, 0.10 * np.exp(-u / 0.06) * np.sin(u * 60.0), 0.0)
        return pitch + jolt, yaw

    def shiver(self, t):
        """(附加的 pitch, 已显出是板的程度 0–1)。L33 的板拼得严丝合缝，没有一点倾斜，看起来是一整片漆过的地面；
        L34 开头一道涟漪荡过，每块板被托起来一点、晃两下，再停在各自略有倾斜的位置上，板缝和每块板深浅不一的
        漆色才显出来。"""
        u = t - self.t_shiver
        on = u >= 0
        uu = np.clip(u, 0, None)
        kick = np.where(on, 0.15 * np.exp(-uu / 0.20) * np.sin(uu * 2 * np.pi * 3.0), 0.0)
        settle = smooth(uu, 0.0, 0.35) * on
        return kick, settle

    # ------------------------------------------------------------ "吹"：被风掀起，卷成旋风
    def _flight_init(self):
        """每块板起飞的参数。冲击波从场地中心以每秒约 700 单位向外推开，经过哪块板，哪块板就被掀起：
        先绕被风兜住的那条边翻起，再被上升气流加速托向镜头，同时绕场地中心旋转（旋风）。全联的十四个黄字
        起初各自作为一整块被掀起、在空中翻转，约 0.3 秒后才散成一块块板。"""
        if hasattr(self, "fl"):
            return self.fl
        rng = np.random.default_rng(1777)
        r0 = np.hypot(self.x, self.y)
        f = {}
        f["t_l"] = T_CHUI - 0.015 + r0 / 700.0 * rng.uniform(0.9, 1.1, N) + rng.uniform(0, 0.03, N)
        f["r0"] = r0
        f["phi0"] = np.arctan2(self.y, self.x)
        f["v0"] = rng.uniform(140.0, 420.0, N) * (1.0 + 0.6 * np.exp(-r0 / 60.0))
        f["acc"] = rng.uniform(500.0, 1100.0, N)
        f["w0"] = rng.uniform(0.4, 1.0, N)
        f["al"] = rng.uniform(2.5, 5.0, N)
        f["shrink"] = rng.uniform(0.35, 0.6, N)
        f["rate"] = rng.uniform(5.0, 18.0, (N, 3)) * rng.choice([-1, 1], (N, 3))
        f["rate"][:, 2] *= 0.3
        f["kick"] = -rng.uniform(1.0, 2.2, N)                   # 起飞时先被兜起的角度（弧度）
        f["wob"] = rng.normal(0, 1, (N, 3))
        # 全联的黄字：第几个字（-1 表示不属于任何字）
        grp = -np.ones(N, int)
        yellow = self.pats[3] == PT.YELLOW_I
        ci = (self.col - PT.LEFT35) // (PT.CH35 + PT.GAP35)
        li = np.where(self.row < PT.TOP35 + PT.CH35 + PT.LGAP35 // 2, 0, 1)
        ok = yellow & (ci >= 0) & (ci < 7)
        grp[ok] = (li * 7 + ci)[ok]
        f["grp"] = grp
        centers = np.zeros((14, 2))
        for k in range(14):
            m = grp == k
            if m.any():
                centers[k] = [self.x[m].mean(), self.y[m].mean()]
        f["gc"] = centers
        f["g_rate"] = rng.uniform(1.5, 4.0, (14, 3)) * rng.choice([-1, 1], (14, 3))
        f["g_v0"] = rng.uniform(110.0, 170.0, 14)
        f["g_delay"] = rng.uniform(0.0, 0.05, 14)
        self.theta_final = self.flips(T_CHUI - 0.02)[0]
        self.fl = f
        return f

    def flight(self, t, idx):
        """对 idx 里已经起飞的板，返回 (掩码, 位置, 旋转矩阵)。"""
        f = self._flight_init()
        t_l = f["t_l"][idx]
        fly = t >= t_l
        if not fly.any():
            return fly, None, None
        j = idx[fly]
        u = t - f["t_l"][j]
        z = AXIS_Z + f["v0"][j] * u + 0.5 * f["acc"][j] * u * u
        phi = f["phi0"][j] + f["w0"][j] * u + 0.5 * f["al"][j] * u * u
        r = f["r0"][j] * (1.0 - f["shrink"][j] * smooth(z, 0.0, 420.0))
        wob = f["wob"][j]
        P = np.stack([r * np.cos(phi) + wob[:, 0] * u * 6.0, r * np.sin(phi) + wob[:, 1] * u * 6.0, z], 1)
        th = self.theta_final[j]
        k = np.clip(u / 0.12, 0, 1)
        pitch = th + f["kick"][j] * (k * k * (3 - 2 * k)) + f["rate"][j, 0] * np.clip(u - 0.08, 0, None)
        yaw = f["rate"][j, 1] * np.clip(u - 0.05, 0, None)
        roll = f["rate"][j, 2] * u
        R = rot_axes(yaw, pitch, roll)
        # 黄字：先作为整块一起飞，0.22 秒后逐渐散开
        g = f["grp"][j]
        gm = g >= 0
        if gm.any():
            gi = g[gm]
            ug = np.clip(u[gm] - f["g_delay"][gi], 0, None)
            c = f["gc"][gi]
            gz = AXIS_Z + f["g_v0"][gi] * ug + 0.5 * 700.0 * ug * ug
            gr0 = np.hypot(c[:, 0], c[:, 1])
            gphi = np.arctan2(c[:, 1], c[:, 0]) + 0.6 * ug + 1.8 * ug * ug
            grr = gr0 * (1.0 - 0.45 * smooth(gz, 0.0, 420.0))
            gcen = np.stack([grr * np.cos(gphi), grr * np.sin(gphi), gz], 1)
            ga = f["g_rate"][gi] * ug[:, None]
            RG = rot_axes(ga[:, 1], ga[:, 0] - 0.6 * smooth(ug, 0, 0.15), ga[:, 2])
            off = np.stack([self.x[j][gm] - c[:, 0], self.y[j][gm] - c[:, 1], np.zeros(gm.sum())], 1)
            Pg = gcen + np.einsum("nij,nj->ni", RG, off)
            Rg = np.einsum("nij,njk->nik", RG, rot_axes(np.zeros(gm.sum()), th[gm]))
            br = smooth(ug, 0.22, 0.6)[:, None]          # 散开的程度
            P[gm] = Pg * (1 - br) + P[gm] * br
            Rm = Rg * (1 - br[:, :, None]) + R[gm] * br[:, :, None]
            uu, _, vt = np.linalg.svd(Rm)                # 混合后的矩阵重新正交化
            R[gm] = np.einsum("nij,njk->nik", uu, vt)
        return fly, P.astype(np.float32), R.astype(np.float32)

    # ------------------------------------------------------------ 绘制
    def visible(self, cam):
        """按视锥裁掉看不见的板。cam 为引擎的 Cam，None 时不裁。"""
        if cam is None:
            return np.arange(N)
        r, u, f = (np.asarray(v, np.float32) for v in cam.basis())
        v = self.P0 - np.asarray(cam.eye, np.float32)[None]
        z = v @ f
        th = math.tan(math.radians(cam.fov / 2))
        m = (z > 0.05) & (np.abs(v @ r) < z * th * 16 / 9 + 2.0) & (np.abs(v @ u) < z * th + 2.0)
        return np.flatnonzero(m)

    def items(self, t, lights, prep, cam=None, extra_light=None, freeze=None, fly_light=None, z_split=None):
        """返回 [地面阴影, 板的投影, 板面与板边]。prep 为 lights.prepare(self.P0)（按全场算好）；
        cam 为镜头（裁剪视锥、计算漆面的高光、挑选朝镜头的板边），None 时按正上方很远处的镜头算、不裁剪；
        fly_light 为飞起的板额外受到的平行光。"""
        eye = None if cam is None else np.asarray(cam.eye, np.float32)
        from engine import Particles
        tt = t if freeze is None else min(t, freeze)
        storm = tt >= T_CHUI - 0.02
        theta, front, back = self.flips(min(tt, T_CHUI - 0.02))
        kick, settle = self.shiver(tt)
        pitch = theta + self.pitch0 * settle + kick
        yaw = self.yaw0 * settle
        w = self.wind(tt)
        if w is not None:
            pitch = pitch + w[0]
            yaw = yaw + w[1]
        idx = self.visible(None if storm else cam)
        if tt < self.t_shiver_max:
            idx = idx[tt >= self.t_shiver[idx]]
        pitch, yaw = pitch[idx], yaw[idx]
        n = len(idx)
        card = (tt >= self.t_shiver)[idx]
        P = self.P0[idx].copy()
        P[:, 2] = np.where(card, P[:, 2], AXIS_Z)
        rot = np.stack([yaw, pitch, np.zeros(n)], 1).astype(np.float32)
        R = None
        fly = np.zeros(n, bool)
        if storm:
            fly, Pf, Rf = self.flight(tt, idx)
            if fly.any():
                R = rot_axes(yaw, pitch)
                P[fly] = Pf
                R[fly] = Rf
                rot = euler_from_matrix(R)
                if eye is not None:                       # 镜头之后或画面以外的板不画
                    D = eye[2] - P[:, 2]
                    keep = (D > 0.06) & (np.abs(P[:, 0] - eye[0]) < D * 0.62 + 2) & \
                        (np.abs(P[:, 1] - eye[1]) < D * 0.62 + 2)
                    sel = np.flatnonzero(keep)
                    idx, P, R, rot, fly = idx[sel], P[sel], R[sel], rot[sel], fly[sel]
                    pitch, yaw, card = pitch[sel], yaw[sel], card[sel]
                    n = len(idx)
        if R is None:
            R = rot_axes(yaw, pitch)
        nrm = R[:, :, 2]
        ey = R[:, :, 1]
        pre = {k: v[idx].copy() for k, v in prep.items()}
        if fly.any():
            pf = lights.prepare(P[fly])
            for k in pre:
                pre[k][fly] = pf[k]
        tint = 1.0 + (self.tint[idx] - 1.0) * settle[idx][:, None]
        extra = list(extra_light or [])
        f_base, b_base = front[idx] * tint, back[idx] * tint
        V = None
        if eye is not None:
            V = eye[None] - P
            V /= np.linalg.norm(V, axis=1, keepdims=True) + 1e-6
        f_col = lights.shade(pre, nrm, f_base, extra, V)
        b_col = lights.shade(pre, -nrm, b_base, extra, V)
        if fly.any() and fly_light:
            fi = np.flatnonzero(fly)
            for d, c in fly_light:
                for col, nn, base in ((f_col, nrm, f_base), (b_col, -nrm, b_base)):
                    k = np.clip(nn[fi] @ np.asarray(d, np.float32), 0, None)
                    col[fi] += base[fi] * k[:, None] * np.asarray(c, np.float32)
        size = np.where(card[:, None], CARD_W, 1.0).astype(np.float32) * np.ones((n, 2), np.float32)
        col = np.c_[f_col, np.ones(n)].astype(np.float32)
        bcol = np.c_[b_col, np.ones(n)].astype(np.float32)
        uv = np.where(card[:, None], self.uv_face[idx], self.uv_seam[idx])
        pos = P
        items = []
        # 板边：只画倾斜的板，取朝镜头的那条长边
        e3 = np.asarray(eye, np.float32) if eye is not None else np.array([0, 0, 1e4], np.float32)
        ez = (ey * (e3[None] - P)).sum(1)
        tilt = (np.abs(ey[:, 2]) > 0.06) | fly
        ei = np.flatnonzero(tilt)
        if len(ei):
            sg = np.where(ez[ei] >= 0, 1.0, -1.0)
            e_pos = P[ei] + sg[:, None] * ey[ei] * (CARD_W / 2)
            if fly.any():
                Re = np.einsum("nij,njk->nik", R[ei], rot_x(-sg * np.pi / 2))
                e_rot = euler_from_matrix(Re)
            else:
                e_rot = np.stack([yaw[ei], pitch[ei] - sg * np.pi / 2, np.zeros(len(ei))], 1).astype(np.float32)
            e_n = sg[:, None] * ey[ei]
            e_col = lights.shade({k: v[ei] for k, v in pre.items()}, e_n, np.broadcast_to(EDGE_C, (len(ei), 3)),
                                 extra, None if V is None else V[ei])
            e_col = np.c_[e_col, np.ones(len(ei))].astype(np.float32)
            pos = np.r_[pos, e_pos.astype(np.float32)]
            rot = np.r_[rot, e_rot]
            size = np.r_[size, np.tile([CARD_W, CARD_T], (len(ei), 1)).astype(np.float32)]
            col = np.r_[col, e_col]
            bcol = np.r_[bcol, e_col]
            uv = np.r_[uv, self.uv_edge[idx][ei]]
            # 阴影：倾斜的板在地上投下的影子（只取主光的方向）；飞高了的板不再投影
            si = ei[P[ei, 2] < 6.0]
            if len(si):
                L = pre["L"][si, 0]
                k = L[:, :2] / L[:, 2:3]
                vv = ey[si, :2] - ey[si, 2:3] * k
                ln = np.linalg.norm(vv, axis=1) * CARD_W
                roll = np.arctan2(vv[:, 1], vv[:, 0]) - np.pi / 2
                s_pos = np.c_[P[si, :2] - P[si, 2:3] * k, np.full(len(si), 0.003)].astype(np.float32)
                amt = np.clip(np.abs(ey[si, 2]) * 2.0, 0, 1) * 0.7 * np.clip(1 - P[si, 2] / 6.0, 0, 1)
                items.append(Particles(self.atlas, s_pos, np.c_[np.full(len(si), CARD_W * 1.05), ln + 0.15],
                                       np.stack([np.zeros(len(si)), np.zeros(len(si)), roll], 1).astype(np.float32),
                                       color=np.c_[np.zeros((len(si), 3)), amt].astype(np.float32),
                                       uv=self.uv_shadow[idx][si], group="past", bias=3.0e4))
        if z_split is None:
            items.append(Particles(self.atlas, pos, size, rot, color=col, back=bcol, uv=uv, group="past"))
        else:
            # 风暴里第一层已经出现：低于它的板单独成组、先画，被层挡住；高于它的板后画
            hi = pos[:, 2] >= z_split
            for m, b in ((~hi, 300.0), (hi, -50.0)):
                if m.any():
                    items.append(Particles(self.atlas, pos[m], size[m], rot[m], color=col[m], back=bcol[m], uv=uv[m],
                                           group="past", bias=b))
        # 板下的地面：平放的板把地面遮在阴影里，板立起来或飞走后地面才被照亮
        cov = np.zeros(N, np.float32)
        if storm:
            cov[idx] = np.abs(nrm[:, 2]) * (P[:, 2] < 2.0)
        else:
            cov[:] = 1.0
            cov[idx] = np.abs(nrm[:, 2])
        items.insert(0, self.shadow_plane(cov))
        if tt < self.t_shiver_max:
            items.append(self.floor_item(tt, lights))
        return items

    def floor_item(self, t, lights):
        """L33 的漆面：涟漪荡过之前，整片场地是一块连续的漆面（逐像素受光），涟漪荡过的地方由一块块板接替。"""
        from engine import Plane, Tex
        def make_tex():
            img = PALETTE[self.pats[0]].reshape(ROWS, COLS, 3)
            img = np.repeat(np.repeat(img, 8, 0), 8, 1)           # 每块板 8×8 个像素：字的边是一格格的台阶，边缘清楚
            return Tex((np.clip(img, 0, 1) * 255 + 0.5).astype(np.uint8))
        tex = cached("floor_tex", make_tex)
        uni = dict(cached("floor_uni", lambda: _floor_uniforms(lights)))
        uni.update({"sh_t": T_SHIVER, "sh_o": SHIVER_O, "sh_v": SHIVER_V})
        return Plane(tex, center=(0.0, 0.0, AXIS_Z), size=(COLS, ROWS), material="h_lacquer", uniforms=uni,
                     group="past")

    def shadow_plane(self, cov):
        from engine import Plane, Tex
        v = (1.0 - 0.94 * cov.reshape(ROWS, COLS)).astype(np.float32)
        img = np.repeat(v[..., None], 3, 2)
        if not hasattr(self, "_shadow_tex"):
            self._shadow_tex = Tex(img, mipmap=False)
        else:
            self._shadow_tex.update(img)
        return Plane(self._shadow_tex, center=(0.0, 0.0, 0.004), size=(COLS, ROWS), blend="multiply", group="past",
                     bias=4.0e4)


def field():
    return cached("field", Field)


def _floor_uniforms(lights):
    import surround as SR
    u = {}
    for i in range(4):
        aim = np.array(SR.LIGHT_AIM[i]) - np.array(SR.LIGHT_POS[i])
        aim /= np.linalg.norm(aim)
        u[f"lp{i}"] = tuple(float(v) for v in SR.LIGHT_POS[i])
        u[f"lc{i}"] = tuple(float(v) for v in lights.color[i] * lights.power[i])
        u[f"la{i}"] = tuple(float(v) for v in aim)
    u["amb"] = tuple(float(v) for v in lights.ambient)
    u["spec_k"] = float(lights.spec)
    u["shin"] = float(lights.shininess)
    return u


register_material("h_lacquer", """
uniform vec3 lp0; uniform vec3 lp1; uniform vec3 lp2; uniform vec3 lp3;
uniform vec3 lc0; uniform vec3 lc1; uniform vec3 lc2; uniform vec3 lc3;
uniform vec3 la0; uniform vec3 la1; uniform vec3 la2; uniform vec3 la3;
uniform vec3 amb;
uniform float spec_k;
uniform float shin;
uniform float sh_t;
uniform vec2 sh_o;
uniform float sh_v;
vec3 shade1(vec3 P, vec3 N, vec3 Nd, vec3 V, vec3 base, vec3 lp, vec3 lc, vec3 la, float gloss) {
    vec3 d = lp - P;
    float r2 = dot(d, d);
    vec3 L = d * inversesqrt(r2);
    float ca = -dot(L, la);
    float u = clamp((ca - 0.86) / (0.975 - 0.86), 0.0, 1.0);
    float att = (0.10 + 0.90 * u * u * (3.0 - 2.0 * u)) / (1.0 + r2 / 67600.0);
    float ndl = dot(N, L);
    vec3 H = normalize(L + V);
    float nh0 = max(dot(Nd, H), 0.0);
    float nh = max(dot(N, H), 0.0);
    float sp = pow(nh0, shin * 0.6) * spec_k * 0.8 * (0.7 + 0.6 * gloss) + pow(nh, shin * 5.0) * spec_k * 4.0 * gloss;
    return lc * att * (base * max(dot(Nd, L), 0.0) + sp * step(0.0, ndl));
}
vec4 material(vec4 base) {
    vec3 P = v_wpos;
    // 涟漪荡过的地方由一块块板接替
    if (u_time >= sh_t + length(P.xy - sh_o) / sh_v) return vec4(0.0);
    vec3 V = normalize(u_eye - P);
    // 漆面的起伏：横向的刷痕（沿 x 拉长的噪声），加上板缝处略微下凹（只在逆光的高光里显出来）
    float b1 = vnoise(P.xy * vec2(0.35, 5.0), 3) - 0.5;
    float b2 = vnoise(P.xy * vec2(1.2, 14.0) + 7.0, 3) - 0.5;
    vec2 fr = fract(P.xy) - 0.5;                       // 板缝在整数坐标上
    // 板缝：很细的一道，只让高光断开（顺光看不出，逆光时漆面一片发亮，缝才显出来）
    float aa = fwidth(P.x) * 1.5;
    vec2 seam = sign(fr) * smoothstep(0.5 - 0.025 - aa, 0.5, abs(fr)) / (1.0 + 30.0 * aa);
    vec3 N = normalize(vec3(-seam * 0.3 + vec2(0.0, b1 * 0.08 + b2 * 0.04), 1.0));
    vec3 Nd = vec3(0.0, 0.0, 1.0);
    float gloss = (0.7 + 0.6 * (b1 + 0.5)) * (1.0 - 0.7 * max(abs(seam.x), abs(seam.y)));
    vec3 rgb = base.rgb;
    vec3 col = rgb * amb
             + shade1(P, N, Nd, V, rgb, lp0, lc0, la0, gloss) + shade1(P, N, Nd, V, rgb, lp1, lc1, la1, gloss)
             + shade1(P, N, Nd, V, rgb, lp2, lc2, la2, gloss) + shade1(P, N, Nd, V, rgb, lp3, lc3, la3, gloss);
    return vec4(col * base.a, base.a);
}
""", defaults={"spec_k": 0.5, "shin": 36.0, "sh_t": 1e9, "sh_o": (0.0, 0.0), "sh_v": 380.0})
