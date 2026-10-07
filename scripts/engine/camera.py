"""镜头与镜头路线。

坐标为右手系：+x 向右，+y 向上，镜头默认朝 -z 看。矩阵按行主序的 numpy 数组保存，传给着色器时转置。

CamPath 的插值分三层考虑：
  1. 每个通道（眼睛位置、目标点、上方向、滚转、视角）用 Hermite 样条插值，关键帧处的切线
     用三点差分（对不等间距的关键帧也准确），再用 Fritsch–Carlson 方法限幅，保证在两个关键帧
     之间单调、不过冲：数据单调的通道插值后仍单调，不会越过关键帧的数值。
  2. 推进或拉远时，眼睛到目标点的距离可能在一段内变化几十倍（例如从 17 降到 0.45）。线性空间里
     插值会让画面放大速度集中在段尾。为此另算一条"对数距离"曲线：目标点照常插值，眼睛相对目标点
     的方向和距离的对数分别插值。两种曲线在关键帧处位置和速度都相同，按每段"推进程度"加权混合，
     所以混合后仍然速度连续。目标点在一段内基本不动且距离变化超过 1.25 倍时开始启用对数插值，
     变化到 2.5 倍时完全使用；目标点移动较多（平移、摇镜头、带前视点的穿行）时只用普通插值，
     眼睛固定的摇镜头因此保持眼睛不动。
  3. "cut" 把路线断成互不影响的几段，每段只用自己的关键帧算切线；"hold" 在关键帧处停住直到下一帧。
"""
import math
import warnings

import numpy as np


def _v(x):
    return np.asarray(x, dtype=np.float64)


def _normalize(v):
    n = np.linalg.norm(v)
    return v / n if n > 1e-12 else v


def perspective(fovy, aspect, near, far):
    f = 1.0 / math.tan(math.radians(fovy) / 2)
    m = np.zeros((4, 4))
    m[0, 0], m[1, 1] = f / aspect, f
    m[2, 2], m[2, 3] = (far + near) / (near - far), 2 * far * near / (near - far)
    m[3, 2] = -1.0
    return m


def look_at(eye, target, up=(0.0, 1.0, 0.0), roll=0.0):
    """视图矩阵。roll 为正时镜头绕视线逆时针转（画面里的景物看起来顺时针转），单位为度。"""
    eye, target, up = _v(eye), _v(target), _v(up)
    f = _normalize(target - eye)
    s = np.cross(f, up)
    if np.linalg.norm(s) < 1e-9:                     # 视线与上方向平行时换一个参考方向
        s = np.cross(f, [0.0, 0.0, -1.0] if abs(f[1]) > 0.9 else [0.0, 1.0, 0.0])
    s = _normalize(s)
    u = np.cross(s, f)
    if roll:
        a = math.radians(roll)
        s, u = s * math.cos(a) + u * math.sin(a), -s * math.sin(a) + u * math.cos(a)
    m = np.eye(4)
    m[0, :3], m[1, :3], m[2, :3] = s, u, -f
    m[:3, 3] = -m[:3, :3] @ eye
    return m


class Cam:
    """一个镜头状态。fov 为竖直视角（度）。

    dof 控制景深的强度（0 表示不虚化），focus 为对焦距离，缺省时取眼睛到目标点的距离；
    near、far 为裁剪面，near 取得小，镜头才能贴着平面穿过去。
    """

    def __init__(self, eye=(0, 0, 10), target=(0, 0, 0), up=(0, 1, 0), roll=0.0, fov=45.0,
                 dof=0.0, focus=None, near=0.005, far=5000.0):
        self.eye, self.target, self.up = _v(eye), _v(target), _v(up)
        self.roll, self.fov = float(roll), float(fov)
        self.dof, self.focus = float(dof), (None if focus is None else float(focus))
        self.near, self.far = near, far

    def view(self):
        return look_at(self.eye, self.target, self.up, self.roll)

    def proj(self, aspect):
        return perspective(self.fov, aspect, self.near, self.far)

    def vp(self, aspect):
        return self.proj(aspect) @ self.view()

    @property
    def forward(self):
        return _normalize(self.target - self.eye)

    @property
    def distance(self):
        return float(np.linalg.norm(self.target - self.eye))

    def focus_distance(self):
        return self.focus if self.focus is not None else self.distance

    def basis(self):
        """返回世界坐标里的 (右, 上, 前) 三个单位向量（已含滚转）。"""
        v = self.view()
        return v[0, :3].copy(), v[1, :3].copy(), -v[2, :3].copy()

    def copy(self, **kw):
        c = Cam(self.eye, self.target, self.up, self.roll, self.fov, self.dof, self.focus, self.near, self.far)
        for k, val in kw.items():
            setattr(c, k, _v(val) if k in ("eye", "target", "up") else val)
        return c

    def __repr__(self):
        e, t = np.round(self.eye, 3).tolist(), np.round(self.target, 3).tolist()
        return f"Cam(eye={e}, target={t}, roll={self.roll:.2f}, fov={self.fov:.2f})"


# ---------------------------------------------------------------------------
# 关键帧插值
# ---------------------------------------------------------------------------

def _hermite_basis(s):
    s2, s3 = s * s, s * s * s
    return 2 * s3 - 3 * s2 + 1, s3 - 2 * s2 + s, -2 * s3 + 3 * s2, s3 - s2


def _smoothstep(e0, e1, x):
    t = min(max((x - e0) / (e1 - e0), 0.0), 1.0)
    return t * t * (3 - 2 * t)


def _fc_limit(h, d, m):
    """Fritsch–Carlson 限幅：逐段检查切线，保证每段 Hermite 曲线在两端数值之间单调。
    h：各段时长 (n-1,)；d：各段割线斜率 (n-1, c)；m：关键帧切线 (n, c)，原地修改。"""
    for k in range(len(h)):
        dk = d[k]
        flat = np.abs(dk) < 1e-12
        m[k][flat] = 0.0
        m[k + 1][flat] = 0.0
        safe = np.where(flat, 1.0, dk)
        a = np.where(flat, 0.0, m[k] / safe)
        b = np.where(flat, 0.0, m[k + 1] / safe)
        a = np.where(a < 0, 0.0, a)          # 切线与割线反向会造成过冲
        b = np.where(b < 0, 0.0, b)
        r = a * a + b * b
        tau = np.where(r > 9.0, 3.0 / np.sqrt(np.maximum(r, 1e-30)), 1.0)
        m[k] = np.where(flat, 0.0, tau * a * dk)
        m[k + 1] = np.where(flat, 0.0, tau * b * dk)
    return m


def _tangents(ts, P, start_rule, end_rule, zero_mask):
    """计算一段（不跨 cut/hold）内各关键帧的切线。
    start_rule / end_rule：'zero' 或 'secant'；zero_mask[i] 为真表示该帧缓入缓出（切线为零）。"""
    n = len(ts)
    m = np.zeros_like(P)
    if n < 2:
        return m
    h = np.diff(ts)
    d = np.diff(P, axis=0) / h[:, None]
    for i in range(1, n - 1):
        if zero_mask[i]:
            continue
        # 三点差分：对不等间距的关键帧，等于过三点的抛物线在中间点的导数
        m[i] = (h[i] * d[i - 1] + h[i - 1] * d[i]) / (h[i - 1] + h[i])
        m[i][d[i - 1] * d[i] <= 0] = 0.0     # 局部极值处切线为零，不越过关键帧
    m[0] = 0.0 if start_rule == "zero" else d[0]
    m[-1] = 0.0 if end_rule == "zero" else d[-1]
    _fc_limit(h, d, m)
    for i in range(n):                        # 限幅不会把零切线变成非零，这里再保证一次
        if zero_mask[i] or (i == 0 and start_rule == "zero") or (i == n - 1 and end_rule == "zero"):
            m[i] = 0.0
    return m


def _parse_mode(mode):
    if mode is None:
        return {"linear"}
    toks = {t for t in str(mode).replace("+", " ").replace(",", " ").split() if t}
    bad = toks - {"ease", "linear", "hold", "cut"}
    if bad:
        raise ValueError(f"未知的关键帧方式 {bad}；可用 ease / linear / hold / cut")
    return toks


# 通道布局：eye 0:3, target 3:6, up 6:9, roll 9, fov 10, dof 11
_NCH = 12


def _pack(c):
    return np.concatenate([c.eye, c.target, _normalize(c.up), [c.roll, c.fov, c.dof]])


class _Side:
    """路线中不被 cut/hold 打断的一段。"""

    def __init__(self, ts, cams, modes, start_rule):
        self.ts = np.asarray(ts, float)
        self.cams = cams
        n = len(ts)
        self.P = np.stack([_pack(c) for c in cams])
        self.focus = [c.focus for c in cams]
        self.near = cams[0].near
        self.far = cams[0].far
        zero = [("ease" in md) or ("hold" in md) for md in modes]
        end_rule = "zero" if zero[-1] else "secant"
        self.M = _tangents(self.ts, self.P, start_rule, end_rule, zero)
        if n < 2:
            return
        # 对数距离曲线：σ = ln|eye-target|，方向 n = (eye-target)/|eye-target|
        E, T = self.P[:, 0:3], self.P[:, 3:6]
        mE, mT = self.M[:, 0:3], self.M[:, 3:6]
        O = E - T
        dist = np.maximum(np.linalg.norm(O, axis=1), 1e-9)
        N = O / dist[:, None]
        dO = mE - mT
        dd = np.einsum("ij,ij->i", N, dO)
        self.sig = np.log(dist)[:, None]
        self.N = N
        # 由普通曲线的速度换算对数曲线的切线，两条曲线在关键帧处的速度因此一致
        self.msig = (dd / dist)[:, None]
        self.mN = (dO - dd[:, None] * N) / dist[:, None]
        h = np.diff(self.ts)
        _fc_limit(h, np.diff(self.sig, axis=0) / h[:, None], self.msig)
        # 每段的混合权重：距离变化大、目标点基本不动时使用对数曲线
        self.w = np.zeros(n - 1)
        for k in range(n - 1):
            ratio = abs(math.log(dist[k + 1] / dist[k]))
            rho = np.linalg.norm(T[k + 1] - T[k]) / min(dist[k], dist[k + 1])
            self.w[k] = _smoothstep(math.log(1.25), math.log(2.5), ratio) * (1 - _smoothstep(0.15, 0.6, rho))

    @property
    def t0(self):
        return self.ts[0]

    @property
    def t1(self):
        return self.ts[-1]

    def eval(self, t):
        """返回 (通道向量, 焦距或 None)。t 应在本段时间范围内（越界时夹到端点）。"""
        ts, n = self.ts, len(self.ts)
        if n == 1 or t <= ts[0]:
            return self.P[0].copy(), self.focus[0]
        if t >= ts[-1]:
            return self.P[-1].copy(), self.focus[-1]
        k = int(np.searchsorted(ts, t, side="right") - 1)
        k = min(max(k, 0), n - 2)
        h = ts[k + 1] - ts[k]
        s = (t - ts[k]) / h
        h00, h10, h01, h11 = _hermite_basis(s)
        p = h00 * self.P[k] + h10 * h * self.M[k] + h01 * self.P[k + 1] + h11 * h * self.M[k + 1]
        w = self.w[k]
        if w > 1e-6:
            sig = h00 * self.sig[k] + h10 * h * self.msig[k] + h01 * self.sig[k + 1] + h11 * h * self.msig[k + 1]
            nv = h00 * self.N[k] + h10 * h * self.mN[k] + h01 * self.N[k + 1] + h11 * h * self.mN[k + 1]
            eye_log = p[3:6] + math.exp(float(sig[0])) * _normalize(nv)
            p[0:3] = (1 - w) * p[0:3] + w * eye_log
        f0, f1 = self.focus[k], self.focus[k + 1]
        focus = None if (f0 is None or f1 is None) else f0 + (f1 - f0) * h01   # h01 即平滑的 0→1
        return p, focus

    def end_velocity(self):
        return self.M[-1].copy()


def _unpack(p, focus, near, far):
    return Cam(eye=p[0:3], target=p[3:6], up=_normalize(p[6:9]), roll=p[9], fov=p[10], dof=max(p[11], 0.0),
               focus=focus, near=near, far=far)


class CamPath:
    """镜头关键帧路线。keys 为 [(t, Cam, 方式), ...]，时间严格递增。

    方式：
      "ease"   缓入缓出：在该帧速度降为零（短暂停顿后再加速离开）；
      "linear" 匀速通过：不减速地穿过该帧，速度与前后两段连续；
      "hold"   在该帧停住，直到下一帧的时刻；下一帧从静止出发；
      "cut"    路线在这一帧之前断开，镜头在这一帧的时刻瞬间换到这一帧的位置；
               断开两侧各自插值，计算切线时互不使用对侧的关键帧。
    "cut" 可以与 "ease" 组合，例如 "cut ease" 表示跳到这一帧后从静止出发；单独的 "cut" 跳过去后按
    后面几帧的速度继续运动。cut 之前那一段在最后一个关键帧之后按末速度匀速外推，直到跳变时刻。
    """

    def __init__(self, keys):
        if not keys:
            raise ValueError("CamPath 至少需要一个关键帧")
        parsed = []
        for k in keys:
            if len(k) == 2:
                t, c, md = k[0], k[1], None
            else:
                t, c, md = k[0], k[1], k[2]
            parsed.append((float(t), c, _parse_mode(md)))
        for a, b in zip(parsed, parsed[1:]):
            if b[0] <= a[0]:
                raise ValueError(f"关键帧时间必须严格递增：{a[0]} 之后是 {b[0]}")
        self.keys = parsed
        self.sides = []       # [(_Side, gap_kind_after)]，gap_kind 为 'hold' / 'cut' / None
        cur = [0]
        groups = []
        for i in range(1, len(parsed)):
            if "cut" in parsed[i][2] or "hold" in parsed[i - 1][2]:
                groups.append(cur)
                cur = [i]
            else:
                cur.append(i)
        groups.append(cur)
        for gi, g in enumerate(groups):
            first = parsed[g[0]]
            if gi > 0 and "hold" in parsed[groups[gi - 1][-1]][2] and "cut" not in first[2]:
                start_rule = "zero"                     # hold 之后从静止出发
                prev = parsed[groups[gi - 1][-1]][1]
                if np.linalg.norm(prev.eye - first[1].eye) > 1e-6 or np.linalg.norm(prev.target - first[1].target) > 1e-6:
                    warnings.warn(f"t={first[0]} 的关键帧紧跟 hold，但位置与停住的位置不同，镜头会在该时刻跳变；"
                                  "如需跳变请写成 cut。")
            elif "ease" in first[2] or ("hold" in first[2] and len(g) == 1):
                start_rule = "zero"
            else:
                start_rule = "secant"
            side = _Side([parsed[i][0] for i in g], [parsed[i][1] for i in g], [parsed[i][2] for i in g], start_rule)
            gap = None
            if gi < len(groups) - 1:
                gap = "hold" if "hold" in parsed[g[-1]][2] else "cut"
            self.sides.append((side, gap))

    def _locate(self, t):
        for i, (side, gap) in enumerate(self.sides):
            nxt = self.sides[i + 1][0].t0 if i + 1 < len(self.sides) else math.inf
            if t < nxt:
                return i
        return len(self.sides) - 1

    def _eval(self, t):
        i = self._locate(t)
        side, gap = self.sides[i]
        if t <= side.t1 or gap is None:
            p, focus = side.eval(t)
        elif gap == "hold":
            p, focus = side.eval(side.t1)
        else:                                            # cut 之前：按末速度匀速外推
            p, focus = side.eval(side.t1)
            p = p + side.end_velocity() * (t - side.t1)
        return p, focus, side

    def __call__(self, t):
        p, focus, side = self._eval(float(t))
        return _unpack(p, focus, side.near, side.far)

    def _span(self, t):
        """t 所在的连续区间 [a, b)，用于在 cut 两侧分别求导。"""
        i = self._locate(t)
        a = self.sides[i][0].t0 if i > 0 else -math.inf
        b = self.sides[i + 1][0].t0 if i + 1 < len(self.sides) else math.inf
        return a, b

    def _diff(self, t, fn, h=1e-3):
        a, b = self._span(t)
        t0, t1 = max(t - h, a), min(t + h, b - 1e-9)
        if t1 <= t0:
            return 0.0
        return fn(t0, t1) / (t1 - t0)

    def velocity(self, t):
        a, b = self._span(t)
        h = 1e-3
        t0, t1 = max(t - h, a), min(t + h, b - 1e-9)
        if t1 <= t0:
            return np.zeros(3)
        return (self(t1).eye - self(t0).eye) / (t1 - t0)

    def speed(self, t):
        """眼睛的移动速度（单位/秒），用于决定运动模糊的子帧数。"""
        return float(np.linalg.norm(self.velocity(t)))

    def angular_speed(self, t):
        """镜头朝向（含滚转）的转动速度（度/秒）。"""
        def ang(t0, t1):
            A, B = np.stack(self(t0).basis()), np.stack(self(t1).basis())
            R = A @ B.T
            c = (np.trace(R) - 1) / 2
            return math.degrees(math.acos(min(max(c, -1.0), 1.0)))
        return float(self._diff(t, ang))

    def zoom_rate(self, t):
        """到目标点距离的对数变化率（每秒），推进时为负。"""
        def z(t0, t1):
            return math.log(max(self(t1).distance, 1e-9) / max(self(t0).distance, 1e-9))
        return float(self._diff(t, z))

    def subframes(self, fps=60, height=1080, base=1, maximum=12, px_per_sub=6.0, shutter=0.5, depth=None):
        """返回一个 t → 子帧数 的函数：按每帧画面上的位移估计运动模糊需要的子帧数。

        位移由三部分估计：镜头转动、眼睛平移（按到目标点的距离或给定的 depth 换算成像素）、推拉造成的缩放。
        每 px_per_sub 个像素的模糊长度用一个子帧，静止处取 base。"""
        def fn(t):
            c = self(t)
            focal = (height / 2) / math.tan(math.radians(c.fov) / 2)
            ref = depth if depth is not None else max(c.distance, 1e-3)
            px = math.radians(self.angular_speed(t)) * focal
            px += self.speed(t) / ref * focal * 0.5
            px += abs(self.zoom_rate(t)) * height * 0.5
            blur = px / fps * shutter
            return int(min(max(math.ceil(blur / px_per_sub), base), maximum))
        return fn
