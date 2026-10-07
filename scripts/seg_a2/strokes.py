"""钢笔字的笔画拆分与书写时间图。

霞鹜文楷的字形轮廓是去掉重叠后的整体（"失"只有一条轮廓，"口"是外框加一个洞），不能按子路径逐笔显现。
所以这里从字形本身恢复笔画：先把字形栅格化并细化成一像素宽的骨架，骨架在交叉处分叉；把骨架拆成若干段，
在每个分叉点把方向接近一条直线的两段接起来（横穿过竖、撇穿过横），接起来的一串就是一笔。折笔（横折、竖钩）
的转角处骨架本身不分叉，自然留在同一笔里。笔顺先按"先左后右、先上后下"的规则自动排出，个别字按楷书笔顺
在 ORDER 表里手工指定。

每一笔有一条中线（骨架折线）和起止方向。书写时间图 T 给出字形里每个像素被墨迹覆盖的时刻（0–1，以这个字的
书写时长为单位）。笔尖沿中线前进的速度不是均匀的：起笔、收笔处慢，中段快，折角处笔尖停一下；像素在笔尖经过
它在中线上的投影点时着墨，几笔相交处取最先经过的那一笔。钢笔的出墨量与笔尖停留的时间成正比，所以速度同时
决定了墨的浓淡、笔画的粗细和飞白：笔尖停留处墨多、颜色深、笔画略粗，起笔和钝的收笔处还积出一个小墨点；
笔画中段写得快，墨浅、略细，沿运笔方向出现断续的细白丝（飞白）。字形外面一圈的数值取最近的笔画，供材质
羽化边缘时使用。

结果存成一张四通道半精度贴图（见 ink_map）：R 为有向距离（em，字内为正，已含粗细变化和积墨点），G 为 T，
B 为出墨量（0–1，停留处、叠压处和积墨点处高），A 为飞白强度（0–1）。
"""
import math
import sys
from pathlib import Path

import numpy as np
import skia
from scipy import ndimage
from scipy.spatial import cKDTree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from engine import glyph_path  # noqa: E402

CACHE = ROOT / "data" / "cache" / "seg_a2"
VERSION = 5
KIND, WEIGHT = "kai", 400

# 字形在贴图里的范围（em，基线在 y = 0，y 向下）：表意字框为 [-0.88, 0.12]，四周留出羽化的余地
BOX = (-0.10, -0.98, 1.10, 0.22)

# ---------------------------------------------------------------- 骨架


def raster(ch, px_per_em, box=BOX):
    """字形覆盖率（0–1 浮点），贴图第 0 行对应 em 坐标 y = box[1]。"""
    x0, y0, x1, y1 = box
    w, h = int(round((x1 - x0) * px_per_em)), int(round((y1 - y0) * px_per_em))
    arr = np.zeros((h, w), np.uint8)
    s = skia.Surface.MakeRasterDirect(skia.ImageInfo.MakeA8(w, h), arr)
    c = s.getCanvas()
    c.scale(px_per_em, px_per_em)
    c.translate(-x0, -y0)
    c.drawPath(glyph_path(ch, KIND, WEIGHT), skia.Paint(AntiAlias=True))
    del c, s
    return arr.astype(np.float32) / 255.0


def thin(img):
    """Zhang–Suen 细化：二值图 → 一像素宽、8 连通的骨架。"""
    im = np.pad(img.astype(np.uint8), 1)
    changed = True
    while changed:
        changed = False
        for step in (0, 1):
            P = im
            p2, p3, p4 = np.roll(P, 1, 0), np.roll(np.roll(P, 1, 0), -1, 1), np.roll(P, -1, 1)
            p5, p6 = np.roll(np.roll(P, -1, 0), -1, 1), np.roll(P, -1, 0)
            p7, p8, p9 = np.roll(np.roll(P, -1, 0), 1, 1), np.roll(P, 1, 1), np.roll(np.roll(P, 1, 0), 1, 1)
            nb = [p2, p3, p4, p5, p6, p7, p8, p9]
            B = sum(n.astype(np.int32) for n in nb)
            seq = nb + [p2]
            A = sum(((seq[i] == 0) & (seq[i + 1] == 1)).astype(np.int32) for i in range(8))
            if step == 0:
                c1, c2 = p2 * p4 * p6, p4 * p6 * p8
            else:
                c1, c2 = p2 * p4 * p8, p2 * p6 * p8
            m = (P == 1) & (B >= 2) & (B <= 6) & (A == 1) & (c1 == 0) & (c2 == 0)
            if m.any():
                im = im.copy()
                im[m] = 0
                changed = True
    return im[1:-1, 1:-1].astype(bool)


_NB8 = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def skeleton_graph(sk):
    """骨架像素 → 邻接表。斜向相邻的两个像素若已经通过一个共同的上下左右邻居相连，就不再直接相连，
    这样直线上的点度数为 2，分叉点才是 3 以上。"""
    ys, xs = np.nonzero(sk)
    S = set(zip(ys.tolist(), xs.tolist()))
    adj = {}
    for y, x in S:
        nb = []
        for dy, dx in _NB8:
            q = (y + dy, x + dx)
            if q not in S:
                continue
            if dy != 0 and dx != 0 and ((y + dy, x) in S or (y, x + dx) in S):
                continue
            nb.append(q)
        adj[(y, x)] = nb
    return adj


def trace_edges(adj, merge_r):
    """把骨架拆成段：度数不为 2 的点是节点；相距 merge_r 以内的分叉点并成一个节点（文楷的交叉处骨架常常
    分成两三个相邻的分叉点，中间夹一小段）。返回 (节点列表 [中心 (y, x), 类型], 段列表 [(节点 a, 节点 b, 像素序列)])。"""
    deg = {p: len(n) for p, n in adj.items()}
    keys = [p for p, d in deg.items() if d != 2]
    junc = [p for p in keys if deg[p] >= 3]
    # 分叉点聚类
    lab = {}
    nodes = []
    if junc:
        # 贪心聚类：每个分叉点并入第一个离它不到 merge_r 的团的种子点，团的直径因此不超过 2·merge_r，
        # 不会像传递闭包那样把一串相邻的分叉点连成一个跨越半个字的大团
        J = np.array(junc, float)
        order_j = np.lexsort((J[:, 1], J[:, 0]))
        seeds, groups_l = [], []
        for i in order_j:
            for gi, s in enumerate(seeds):
                if np.hypot(*(J[i] - s)) <= merge_r:
                    groups_l[gi].append(i)
                    break
            else:
                seeds.append(J[i])
                groups_l.append([i])
        for g in groups_l:
            nid = len(nodes)
            nodes.append([J[g].mean(0), "j"])
            for i in g:
                lab[junc[i]] = nid
    for p in keys:
        if deg[p] < 3:
            lab[p] = len(nodes)
            nodes.append([np.array(p, float), "e" if deg[p] == 1 else "i"])
    # 沿度数为 2 的链走到下一个节点
    edges = []
    seen = set()
    for p in lab:
        for q in adj[p]:
            if (p, q) in seen:
                continue
            path = [p, q]
            prev, cur = p, q
            while cur not in lab:
                nxt = [r for r in adj[cur] if r != prev]
                if not nxt:
                    break
                prev, cur = cur, nxt[0]
                path.append(cur)
            seen.add((p, q))
            seen.add((path[-1], path[-2]))
            a, b = lab[p], lab.get(path[-1], None)
            if b is None:
                continue
            if a == b and len(path) <= 3:
                continue                                   # 同一个分叉团内部的短连线
            edges.append([a, b, path])
    # 去掉重复（同一段被两头各走一次）
    uniq, keyset = [], set()
    for a, b, path in edges:
        k = (min(path[0], path[-1]), max(path[0], path[-1]), len(path))
        if k in keyset:
            continue
        keyset.add(k)
        uniq.append([a, b, path])
    # 闭合的环（没有节点的骨架分量，例如"口"的字怀四周如果没有任何出头）
    covered = set()
    for p in adj:
        if p in covered:
            continue
        comp, stack = [], [p]                         # 骨架的连通分量
        covered.add(p)
        while stack:
            q = stack.pop()
            comp.append(q)
            for r in adj[q]:
                if r not in covered:
                    covered.add(r)
                    stack.append(r)
        if any(q in lab for q in comp):
            continue
        ring = [p]
        prev, cur = None, p
        while True:
            nxt = [r for r in adj[cur] if r != prev and (r == p or r not in ring)]
            if not nxt:
                break
            prev, cur = cur, nxt[0]
            if cur == p:
                break
            ring.append(cur)
        covered.update(ring)
        nid = len(nodes)
        nodes.append([np.array(ring[0], float), "i"])
        uniq.append([nid, nid, ring + [ring[0]]])
    return nodes, uniq


def _edge_len(path):
    p = np.asarray(path, float)
    return float(np.hypot(*np.diff(p, axis=0).T).sum()) if len(p) > 1 else 0.0


def _dir_from_node(path, node_xy, dist):
    """段在节点一端的出发方向：从节点中心指向沿段走 dist 像素处的点（单位向量，(y, x)）。"""
    p = np.asarray(path, float)
    if np.hypot(*(p[-1] - node_xy)) < np.hypot(*(p[0] - node_xy)):
        p = p[::-1]
    s = np.r_[0, np.cumsum(np.hypot(*np.diff(p, axis=0).T))]
    i = min(int(np.searchsorted(s, dist)), len(p) - 1)
    v = p[i] - node_xy
    n = np.hypot(*v)
    return v / n if n > 1e-6 else np.zeros(2)


def extract(ch, ppe=256):
    """自动拆出一个字的笔画：返回 (覆盖率, 距离变换, [笔画像素序列 (y, x)，已按书写方向排好])，笔画按自动笔顺排列。"""
    cov = raster(ch, ppe)
    ink = cov > 0.5
    dt = ndimage.distance_transform_edt(ink)
    sk = thin(ink)
    adj = skeleton_graph(sk)
    width = float(np.median(dt[sk])) * 2 if sk.any() else 4.0       # 典型笔画宽度（像素）
    nodes, edges = trace_edges(adj, merge_r=width * 0.75)
    # 去掉毛刺：一端是端点、另一端是分叉点、长度不到一个笔画宽的短段（笔画端头和转角的鼓包造成）
    for _ in range(4):
        deg = {}
        for a, b, _p in edges:
            deg[a] = deg.get(a, 0) + 1
            deg[b] = deg.get(b, 0) + 1
        keep = []
        removed = False
        for a, b, p in edges:
            ea, eb = nodes[a][1] == "e", nodes[b][1] == "e"
            if (ea != eb) and _edge_len(p) < width * 1.1 and deg[b if ea else a] >= 3:
                removed = True
                continue
            keep.append([a, b, p])
        edges = keep
        # 度数变成 2 的分叉点：把两段接成一段
        while True:
            deg = {}
            for i, (a, b, _p) in enumerate(edges):
                deg.setdefault(a, []).append(i)
                deg.setdefault(b, []).append(i)
            target = next((n for n, l in deg.items() if len(l) == 2 and nodes[n][1] == "j" and l[0] != l[1]), None)
            if target is None:
                break
            i, j = deg[target]
            a1, b1, p1 = edges[i]
            a2, b2, p2 = edges[j]
            c = np.array(nodes[target][0])
            p1 = p1 if np.hypot(*(np.array(p1[-1]) - c)) <= np.hypot(*(np.array(p1[0]) - c)) else p1[::-1]
            p2 = p2 if np.hypot(*(np.array(p2[0]) - c)) <= np.hypot(*(np.array(p2[-1]) - c)) else p2[::-1]
            o1 = a1 if a1 != target else b1
            o2 = b2 if b2 != target else a2
            nodes[target][1] = "x"
            edges = [e for k, e in enumerate(edges) if k not in (i, j)] + [[o1, o2, list(p1) + list(p2)]]
        if not removed:
            break
    # 在每个分叉点把接近一直线的两段配成一对
    inc = {}
    for i, (a, b, p) in enumerate(edges):
        inc.setdefault(a, []).append((i, 0))
        inc.setdefault(b, []).append((i, 1))
    link = {}
    for n, lst in inc.items():
        if nodes[n][1] != "j" or len(lst) < 3:
            continue
        c = np.array(nodes[n][0])
        dirs = [(_dir_from_node(edges[i][2] if e == 0 else edges[i][2][::-1], c, width * 2.0), (i, e)) for i, e in lst]
        cand = []
        for u in range(len(dirs)):
            for v in range(u + 1, len(dirs)):
                if dirs[u][1][0] == dirs[v][1][0]:
                    continue
                cand.append((float(dirs[u][0] @ dirs[v][0]), dirs[u][1], dirs[v][1]))
        cand.sort()
        used = set()
        for dot, a, b in cand:
            if dot > -0.72 or a in used or b in used:
                continue
            used.add(a)
            used.add(b)
            link[a] = b
            link[b] = a
    # 串成笔画：(段号, 端) 表示从这一端进入该段
    done = set()
    strokes = []
    for i in range(len(edges)):
        if i in done:
            continue
        cur, end = i, 0
        visited = {i}
        while (cur, end) in link:                      # 往"0 端"方向回溯到链头
            nxt = link[(cur, end)]
            if nxt[0] in visited:
                break
            cur, end = nxt[0], 1 - nxt[1]
            visited.add(cur)
        chain_pts = []
        e_id, enter = cur, end
        seq = set()
        while True:
            seq.add(e_id)
            p = edges[e_id][2]
            p = p if enter == 0 else p[::-1]
            chain_pts += list(p)
            nxt = link.get((e_id, 1 - enter))
            if nxt is None or nxt[0] in seq:
                break
            e_id, enter = nxt
        done |= seq
        strokes.append(np.array(chain_pts, float))
    strokes = [s for s in strokes if len(s) >= 2]
    pieces = []
    for s in strokes:
        pieces += _split_corners(s, width)
    strokes = [_orient(s, ppe) for s in pieces if _edge_len(s) > width * 0.6 or len(pieces) == 1]
    strokes = _auto_order(strokes, ppe)
    return cov, dt, strokes


def _unit(v):
    n = np.hypot(*v)
    return v / n if n > 1e-9 else v * 0


def _split_corners(s, width):
    """在折角处把一串骨架拆开，再按楷书的折笔规则把该连的接回去：向右再向下（横折）、向右再向左下（横撇）
    连成一笔；末端不到一个半笔画宽的短段是钩，并入前一段；其余折角（例如方框左下角，竖写到底、另起一横）
    拆成两笔。"""
    p = np.asarray(s, float)
    if len(p) < 6:
        return [p]
    cum = np.r_[0, np.cumsum(np.hypot(*np.diff(p, axis=0).T))]
    L = cum[-1]
    w = max(width * 1.2, 3.0)
    # 每个点前后各 w 像素处的方向，转角大于 55 度的局部极大值就是折角
    idx_b = np.searchsorted(cum, cum - w).clip(0, len(p) - 1)
    idx_f = np.searchsorted(cum, cum + w).clip(0, len(p) - 1)
    din = np.array([_unit(p[i] - p[j]) for i, j in zip(range(len(p)), idx_b)])
    dout = np.array([_unit(p[j] - p[i]) for i, j in zip(range(len(p)), idx_f)])
    cosang = (din * dout).sum(1)
    turn = np.degrees(np.arccos(np.clip(cosang, -1, 1)))
    ok = (cum > w * 0.8) & (cum < L - w * 0.8)
    cand = np.flatnonzero(ok & (turn > 55))
    corners = []
    for i in cand:
        lo, hi = np.searchsorted(cum, cum[i] - w), np.searchsorted(cum, cum[i] + w)
        if turn[i] >= turn[lo:hi + 1].max() - 1e-6 and (not corners or cum[i] - cum[corners[-1]] > w):
            corners.append(i)
    if not corners:
        return [p]
    cuts = [0] + corners + [len(p) - 1]
    segs = [p[cuts[k]:cuts[k + 1] + 1] for k in range(len(cuts) - 1)]
    closed = np.hypot(*(p[0] - p[-1])) < width * 0.8

    def kind(a, b):
        """a、b 为前后两段（书写方向），判断折角是否连笔。方向 (y, x)，y 向下。"""
        da = _unit(a[-1] - a[max(0, len(a) - 1 - int(w))])
        db = _unit(b[min(len(b) - 1, int(w))] - b[0])
        right = lambda d: d[1] > 0.8
        down = lambda d: d[0] > 0.8
        downleft = lambda d: d[0] > 0.35 and d[1] < -0.35
        if right(da) and (down(db) or downleft(db)):
            return True
        return False

    out = [segs[0]]
    for sgm in segs[1:]:
        a = out[-1]
        hook = _edge_len(sgm) < width * 1.5 and sgm is segs[-1] and not closed
        if hook or kind(a, sgm) or kind(sgm[::-1], a[::-1]):
            out[-1] = np.vstack([a, sgm[1:]])
        else:
            out.append(sgm)
    # 闭合的环：首尾两段在起点处相接，也按同样的规则判断能否连起来
    if closed and len(out) > 1:
        a, b = out[-1], out[0]
        if kind(a, b) or kind(b[::-1], a[::-1]):
            out = [np.vstack([a, b[1:]])] + out[1:-1]
    return out


def _em(p, ppe):
    """像素 (y, x) → em (x, y)。"""
    return np.c_[p[:, 1] / ppe + BOX[0], p[:, 0] / ppe + BOX[1]]


def _orient(s, ppe):
    """笔画的书写方向：一般从上往下、从左往右（撇从右上起笔）；短而平缓地向右上挑起的是提，从左下起笔。"""
    e = _em(s, ppe)
    a, b = e[0], e[-1]
    L = _edge_len(e)
    lo, hi = (a, b) if a[1] > b[1] else (b, a)          # lo 为下端
    v = hi - lo
    ang = math.degrees(math.atan2(-v[1], v[0]))          # 向右上为正
    straight = np.hypot(*(b - a)) > 0.85 * L
    if straight and 15 < ang < 42 and L < 0.32:
        return s if np.allclose(e[0], lo) else s[::-1]
    score = lambda q: q[1] + 0.4 * q[0]
    return s if score(a) <= score(b) else s[::-1]


def _auto_order(strokes, ppe):
    """自动笔顺：能左右分开的部件先左后右，能上下分开的先上后下，递归下去；同一部件内按起笔位置从上到下、
    从左到右，横与竖相交时先横后竖。"""
    E = [_em(s, ppe) for s in strokes]
    bb = [(e[:, 0].min(), e[:, 1].min(), e[:, 0].max(), e[:, 1].max()) for e in E]

    def split(ids, axis):
        lo = sorted(ids, key=lambda i: bb[i][axis])
        best = None
        for k in range(1, len(lo)):
            left, right = lo[:k], lo[k:]
            edge = max(bb[i][axis + 2] for i in left)
            start = min(bb[i][axis] for i in right)
            gap = start - edge
            if gap > -0.025 and (best is None or gap > best[0]):
                best = (gap, left, right)
        return best

    def order(ids):
        if len(ids) <= 1:
            return list(ids)
        for axis in (0, 1):
            s = split(ids, axis)
            if s is not None:
                return order(s[1]) + order(s[2])

        def key(i):
            st = E[i][0]
            d = E[i][-1] - E[i][0]
            horiz = abs(d[0]) > 2.5 * abs(d[1])
            return st[1] - (0.06 if horiz else 0.0) + 0.15 * st[0]
        return sorted(ids, key=key)

    return [strokes[i] for i in order(list(range(len(strokes))))]


# ---------------------------------------------------------------- 手工笔顺
# 自动拆分的笔画编号（extract 的结果，分析分辨率 256 像素/em）按楷书笔顺重新排列。"a+b" 表示两段接成一笔
# （后一段自动调成接在前一段末端的方向，用于竖钩的钩、被交叉点打断的横），"ar" 表示这一段倒过来写（氵的提）。
# 自动拆分在少数交叉处把撇的上半段和竖接在了一起（在、街、得的双人旁），这里不再细分：书写很快，看不出差别。

ORDER = {
    "守": "0 2 1 4 3+6 5",
    "着": "0 1 2 3 6 4+5+7 8 9 10 11 12",
    "漸": "0 1 2r 4 6 7+9 8 10 3 11 12 5 13 14",
    "消": "0 1 2r 4 3 5 6 7+10 8 9",
    "失": "1 2 3 0 4",
    "在": "2+1 0 5 4 3 6",
    "街": "0 1 2 4 3 5 7 6 8 9 10 12+11",
    "道": "4 5 6 7 9 8+13 10 11 12 0 1+2+3 14",
    "的": "1 0 2 3 4 5 6+8 7",
    "吵": "0 1 2 3 4 5 6",
    "像": "0 1 2 3 5 4 6 7 9 8+13+12 10 11 14 15",
    "角": "1 0 2+6 4 5 3",
    "落": "2 0 1 3 4 5r 6 7 8 9 10 11",
    "裏": "0 1 3 2+7 5 6 4 8 10 9 11 14+16 13 15 12",
    "貓": "0 3 4 6 7+10 8 9 2 5 1 12 11+16 13 14 15",
    "我": "1 4 3+7 6 0+8 5 2",
    "猜": "0 1+3 2 5 6 4 7 8 9+12 10 11",
    "沒": "0 1 2r 3 4 5 6 7",
    "人": "0 1",
    "記": "0 1 2 3 5 4 6 7 9 8+10",
    "得": "0 1 2 4+6 3 5 7 8 10 9+12 11",
    "她": "0+8 5+3 4 7+9 1 2",
    "笑": "0 1 2 3 4 5 6 8+9 7 10",
    "口": "1 0 2",
}

PPE_A = 256          # 笔画分析的分辨率（像素/em），ORDER 里的编号以此为准


def strokes_of(ch):
    """按手工笔顺整理后的笔画：返回 (覆盖率, 距离变换, [笔画像素序列 (y, x)])，分辨率 PPE_A。"""
    cov, dt, st = extract(ch, PPE_A)
    spec = ORDER.get(ch)
    if spec is None:
        return cov, dt, st
    out = []
    used = set()
    for tok in spec.split():
        parts = tok.split("+")
        cur = None
        for k, ptok in enumerate(parts):
            rev = ptok.endswith("r")
            i = int(ptok.rstrip("r"))
            used.add(i)
            s = st[i][::-1] if rev else st[i]
            if cur is None:
                cur = s
            else:
                # 后一段调成从离前一段末端近的一头开始
                if np.hypot(*(s[-1] - cur[-1])) < np.hypot(*(s[0] - cur[-1])):
                    s = s[::-1]
                cur = np.vstack([cur, s])
        out.append(cur)
    missing = [i for i in range(len(st)) if i not in used]
    for i in missing:                                   # 漏写的段补在最后，免得字缺笔画
        out.append(st[i])
    return cov, dt, out


# ---------------------------------------------------------------- 书写时间图


def _min_jerk_inverse(n=256):
    """笔尖沿中线前进的进度 f(u) = 10u³ − 15u⁴ + 6u⁵（最小急动度：起笔、收笔慢，中段快）的反函数表。"""
    u = np.linspace(0, 1, n)
    f = u ** 3 * (10 - 15 * u + 6 * u * u)
    return f, u


def stroke_schedule(strokes, ppe):
    """每一笔的起止时刻（0–1）：笔画写的时间按长度的 0.75 次方分配，笔与笔之间抬笔移动的时间按两点距离分配，
    再加上一个固定的停顿；总和归一到 1。"""
    L = np.array([_edge_len(s) / ppe for s in strokes])            # em
    write = 0.05 + L ** 0.75
    gaps = []
    for a, b in zip(strokes[:-1], strokes[1:]):
        d = np.hypot(*(b[0] - a[-1])) / ppe
        gaps.append(0.10 + 0.45 * d)
    total = write.sum() + sum(gaps)
    t, sched = 0.0, []
    for k, w in enumerate(write):
        sched.append((t / total, (t + w) / total))
        t += w + (gaps[k] if k < len(gaps) else 0.0)
    return sched


def _noise1d(x, seed):
    """一维值噪声（0–1），用于飞白的细丝。"""
    rng = np.random.default_rng(seed)
    tab = rng.uniform(0, 1, 4096)
    i = np.floor(x).astype(int)
    f = x - i
    f = f * f * (3 - 2 * f)
    return tab[i % 4096] * (1 - f) + tab[(i + 1) % 4096] * f


def stroke_speed(line, rad, med):
    """沿中线每个采样点的笔尖速度（相对值，最大为 1）：两端慢、中段快，折角处减速。返回 (速度, 到达各点的时间比例)。"""
    n = len(line)
    seg = np.hypot(*np.diff(line, axis=0).T)
    cs = np.r_[0, np.cumsum(seg)]
    L = max(cs[-1], 1e-6)
    x = cs / L
    # 两端的减速段按笔画宽度计，短笔画几乎全程都在起收笔里。端头比笔画细的是出锋（撇、提、钩的尖），
    # 笔尖是带着速度离开纸面的，不减速；端头饱满的是顿笔，笔尖在那里停一下
    ramp_len = min(0.40, 1.7 * med / L)
    k_s = float(np.clip((rad[0] / med - 0.70) / 0.25, 0, 1))
    k_e = float(np.clip((rad[-1] / med - 0.70) / 0.25, 0, 1))
    up = np.clip(x / ramp_len, 0, 1)
    dn = np.clip((1 - x) / ramp_len, 0, 1)
    sup = 1 - k_s * (1 - np.sin(up * np.pi / 2) ** 1.3)
    sdn = 1 - k_e * (1 - np.sin(dn * np.pi / 2) ** 1.3)
    base = 0.30 + 0.70 * np.minimum(sup, sdn)
    # 折角：前后各 1.2 个笔宽处的方向夹角
    w = max(int(1.2 * med * 2), 2)                         # 采样间距为 0.5 像素
    i0 = np.clip(np.arange(n) - w, 0, n - 1)
    i1 = np.clip(np.arange(n) + w, 0, n - 1)
    d0 = line - line[i0]
    d1 = line[i1] - line
    n0 = np.hypot(*d0.T) + 1e-9
    n1 = np.hypot(*d1.T) + 1e-9
    cosang = ((d0 * d1).sum(1) / (n0 * n1)).clip(-1, 1)
    ang = np.degrees(np.arccos(cosang))
    ang[(n0 < med) | (n1 < med)] = 0.0
    corner = ndimage.gaussian_filter1d(np.clip((ang - 25) / 60, 0, 1), max(w / 2, 1))
    v = base * (1 - 0.78 * np.clip(corner * 1.4, 0, 1))
    v = np.maximum(v, 0.08)
    dt = np.r_[0, seg / (0.5 * (v[1:] + v[:-1]))]
    tau = np.cumsum(dt)
    tau /= max(tau[-1], 1e-9)
    return v / v.max(), tau, cs, L


def ink_map(ch, ppe=1024, keep=None):
    """一个字的墨迹数据贴图（float32，(H, W, 4)，第 0 行对应 em 坐标 y = BOX[1]）：
    R 为有向距离（em，字内为正），G 为书写时间 T（0–1），B 为出墨量（0–1），A 为飞白强度（0–1）。
    keep 为笔画序号的集合时只保留这些笔画（按每个像素最近的笔画划分），用于把一个字拆成部件。"""
    cov_a, dt_a, strokes = strokes_of(ch)
    sched = stroke_schedule(strokes, PPE_A)
    cov = raster(ch, ppe)
    h, w = cov.shape
    inside = cov >= 0.5
    d_in = ndimage.distance_transform_edt(inside)
    d_out = ndimage.distance_transform_edt(~inside)
    sdf_px = np.where(inside, d_in - 0.5, -(d_out - 0.5))
    edge = (cov > 0.0) & (cov < 1.0)
    sdf_px[edge] = cov[edge] - 0.5
    sdf = sdf_px / ppe
    k = PPE_A / ppe                                                  # 输出像素 → 分析像素
    region = sdf > -0.08
    ys, xs = np.nonzero(region)
    P = np.c_[ys, xs].astype(float) * k
    N = len(P)
    T = np.full(N, np.inf)
    best_ratio = np.full(N, np.inf)
    T_near = np.zeros(N)
    count = np.zeros(N)
    ink = np.zeros(N)                    # 出墨量：取经过该像素的各笔里最大的那个
    dwell_near = np.zeros(N)             # 最近一笔在该处的停留程度（用来改变粗细）
    r_near = np.ones(N)
    owner = np.zeros(N, int)
    fly = np.zeros(N)
    blob_sdf = np.full(N, -np.inf)       # 积墨点的有向距离（分析像素）
    blob_ink = np.zeros(N)
    rng = np.random.default_rng(zlib_crc(ch))
    all_lines = [np.asarray(q, float) for q in strokes]
    for si, (s, (t0, t1)) in enumerate(zip(strokes, sched)):
        s = np.asarray(s, float)
        seg = np.hypot(*np.diff(s, axis=0).T)
        cum = np.r_[0, np.cumsum(seg)]
        Ls = max(cum[-1], 1e-6)
        n = max(int(Ls * 2), 2)
        cs0 = np.linspace(0, Ls, n)
        line = np.c_[np.interp(cs0, cum, s[:, 0]), np.interp(cs0, cum, s[:, 1])]
        rad = ndimage.map_coordinates(dt_a, line.T, order=1)
        med = float(np.median(rad))
        win = max(3, int(med * 6))
        rad = ndimage.median_filter(rad, size=win, mode="nearest").clip(None, med * 1.15)
        v, tau, cs, L = stroke_speed(line, rad, med)
        tree = cKDTree(line)
        dist, idx = tree.query(P)
        tt = t0 + (t1 - t0) * tau[idx]
        r = rad[idx]
        member = dist <= r + 0.8
        ratio = dist / np.maximum(r, 0.5)
        dwell = 1.0 - v[idx]
        T = np.where(member, np.minimum(T, tt), T)
        count += member
        press = rng.uniform(0.82, 1.0)                     # 每一笔的出墨量略有不同
        ink = np.where(member, np.maximum(ink, press * (0.45 + 0.55 * dwell ** 1.4)), ink)
        closer = ratio < best_ratio
        T_near = np.where(closer, tt, T_near)
        dwell_near = np.where(closer, dwell, dwell_near)
        owner = np.where(closer, si, owner)
        r_near = np.where(closer, r, r_near)
        best_ratio = np.minimum(best_ratio, ratio)
        # 飞白：沿运笔方向的细丝。横跨笔画的坐标 across（−1–1）上取一维噪声，沿笔画方向慢慢变化
        tan = np.gradient(line, axis=0)
        tan /= np.hypot(*tan.T)[:, None] + 1e-9
        dvec = P - line[idx]
        across = (tan[idx, 0] * dvec[:, 1] - tan[idx, 1] * dvec[:, 0]) / np.maximum(r, 0.5)
        along = cs[idx] / max(med * 4.0, 1.0)
        seed = int(rng.integers(1 << 30))
        nz = _noise1d(across * 4.0 + 0.25 * _noise1d(along * 0.7, seed + 1) * 4 + 50, seed)
        patch = _noise1d(along * 1.5 + 11, seed + 2)
        f = 0.75 * (v[idx] ** 2.5) * np.clip((nz - 0.68) / 0.18, 0, 1) * np.clip((patch - 0.48) / 0.25, 0, 1)
        f *= np.clip((0.80 - np.abs(across)) / 0.20, 0, 1)        # 笔画两侧的边始终是实的
        fly = np.where(member, np.maximum(fly, f), fly)
        # 积墨点：起笔处总有，钝的收笔处有一半的机会
        for end, chance in ((0, 0.30), (-1, 0.22)):
            r_end = rad[end]
            if r_end < 0.72 * med or rng.uniform() > chance:
                continue
            # 端点落在别的笔画里（例如"月"里两横的两头）时不积墨点：那里的墨被别的笔画盖住
            pe = line[end]
            others = [q for j, q in enumerate(all_lines) if j != si]
            if others and min(np.hypot(*(q - pe).T).min() for q in others) < 2.2 * med:
                continue
            dirv = tan[end] * (1 if end == 0 else -1)
            c = line[end] + dirv * 0.35 * r_end
            rb = r_end * rng.uniform(1.06, 1.22)
            db = np.hypot(*(P - c).T)
            blob_sdf = np.maximum(blob_sdf, rb - db)
            blob_ink = np.maximum(blob_ink, 0.7 * np.exp(-(db / (rb * 1.1)) ** 2))
    T = np.where(np.isfinite(T), T, T_near)
    ink = np.clip(np.maximum(ink, 0.45 + 0.4 * dwell_near * (ink == 0)) + 0.05 * (count - 1).clip(0, 2)
                  + 0.25 * blob_ink, 0, 1)
    # 粗细：停留处略粗、快处略细（按笔宽的比例，分析像素 → em）
    dw = (dwell_near - 0.45) * 0.20 * r_near
    sdf_r = sdf[ys, xs] + dw / PPE_A
    sdf_r = np.maximum(sdf_r, blob_sdf / PPE_A)
    sdf_out = sdf.copy()
    sdf_out[ys, xs] = sdf_r
    if keep is not None:
        kept = np.zeros((h, w), bool)
        kept[ys, xs] = np.isin(owner, list(keep))
        d_cut = (ndimage.distance_transform_edt(kept) - ndimage.distance_transform_edt(~kept)) / ppe
        sdf_out = np.minimum(sdf_out, d_cut)
    Tm = np.zeros((h, w), np.float32)
    Tm[ys, xs] = T
    Bm = np.zeros((h, w), np.float32)
    Bm[ys, xs] = ink
    Am = np.zeros((h, w), np.float32)
    Am[ys, xs] = fly * (blob_ink < 0.3)
    idx = ndimage.distance_transform_edt(~region, return_distances=False, return_indices=True)
    Tm = Tm[idx[0], idx[1]]
    Bm = Bm[idx[0], idx[1]]
    Tm = ndimage.gaussian_filter(Tm, 0.6 * ppe / 512)
    Bm = ndimage.gaussian_filter(Bm, 0.8 * ppe / 512)
    Am = ndimage.gaussian_filter(Am, 0.5 * ppe / 512)
    return np.dstack([sdf_out, Tm, Bm, Am]).astype(np.float32)


def part_tex_data(ch, ppe, keep, tag):
    """一个字的部件的墨迹贴图（编码同 ink_tex_data），存盘缓存。"""
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"ink_v{VERSION}_{ord(ch):x}_{ppe}_{tag}.npy"
    if p.exists():
        return np.load(p)
    m = ink_map(ch, ppe, keep=keep)
    m[..., 0] = 2.0 + 10.0 * np.clip(m[..., 0], -0.15, 0.15)
    m = m.astype(np.float16)
    np.save(p, m)
    return m


def zlib_crc(ch):
    import zlib
    return zlib.crc32(ch.encode("utf-8"))


def ink_tex_data(ch, ppe=1024):
    """存盘缓存的墨迹贴图数据，已编码成引擎能按半精度上传的形式：R = 2 + 10·距离（em），保证 R 大于 1，
    引擎因此按半精度浮点上传，负值不被截断；读取时在材质里解码。"""
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"ink_v{VERSION}_{ord(ch):x}_{ppe}.npy"
    if p.exists():
        return np.load(p)
    m = ink_map(ch, ppe)
    m[..., 0] = 2.0 + 10.0 * np.clip(m[..., 0], -0.15, 0.15)
    m = m.astype(np.float16)
    np.save(p, m)
    return m
