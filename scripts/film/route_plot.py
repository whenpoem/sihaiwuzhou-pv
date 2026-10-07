"""把镜头路线画成三视图（俯视 x–z、侧视 z–y、正视 x–y），按时间着色并标出段落起点，用来核对空间关系和连续性。
插值用简单的 Catmull-Rom，只作检查；正式渲染时由引擎的 CamPath 插值。"""
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import plan

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei"]
plt.rcParams["axes.unicode_minus"] = False


def sample(K, n=6000):
    ts = np.array([k[0] for k in K])
    P = np.array([k[1] for k in K])
    cut = np.array([k[5] == "cut" for k in K])
    tt = np.linspace(ts[0], ts[-1], n)
    out = []
    for t in tt:
        i = np.clip(np.searchsorted(ts, t) - 1, 0, len(ts) - 2)
        t0, t1 = ts[i], ts[i + 1]
        u = 0 if t1 == t0 else (t - t0) / (t1 - t0)
        if cut[i + 1]:                                              # 断开处：不插值
            out.append(P[i] if u < 1 else P[i + 1])
            continue
        i0 = i - 1 if i > 0 and not cut[i] else i                   # 样条不跨过断点取邻居
        i3 = i + 2 if i + 2 < len(P) and not cut[i + 2] else i + 1
        p0, p1, p2, p3 = P[i0], P[i], P[i + 1], P[i3]
        out.append(0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u ** 2
                          + (-p0 + 3 * p1 - 3 * p2 + p3) * u ** 3))
    return tt, np.array(out)


def main():
    K = plan.keys()
    tt, P = sample(K)
    marks = {"前奏": 0, "主歌一": plan.VERSE1, "过曝": plan.FLASH_SUMMER, "副歌一": plan.CHORUS1,
             "间奏一": plan.INTERLUDE1, "主歌二": plan.VERSE2, "副歌二": plan.CHORUS2, "间奏二": plan.INTERLUDE2,
             "桥段": plan.BRIDGE, "风暴": plan.STORM, "阳光": plan.SUN, "最后一句": plan.FINAL}
    segs = [(0, plan.FLASH_SUMMER, "前奏—主歌一前半（今天、旧纸）"), (plan.FLASH_SUMMER, plan.DARK_NIGHT, "主歌一后半—间奏一（第一、二层）"),
            (plan.DARK_NIGHT, plan.END, "主歌二—结尾（第三层、竖直轴）")]
    fig, axes = plt.subplots(3, 3, figsize=(21, 18))
    for row, (a, b, title) in enumerate(segs):
        m = (tt >= a) & (tt <= b)
        for col, (ix, iy, lab) in enumerate([(0, 2, "俯视 x–z"), (2, 1, "侧视 z–y"), (0, 1, "正视 x–y")]):
            ax = axes[row, col]
            sc = ax.scatter(P[m, ix], P[m, iy], c=tt[m], s=2, cmap="viridis")
            for name, t in marks.items():
                if a <= t <= b:
                    j = np.argmin(np.abs(tt - t))
                    ax.annotate(name, (P[j, ix], P[j, iy]), fontsize=9, color="crimson")
            ax.set_title(f"{title}  {lab}")
            ax.set_aspect("equal", adjustable="datalim")
            if col == 2:
                fig.colorbar(sc, ax=ax, label="时间（秒）")
    out = plan.ROOT / "renders" / "tests" / "route_plot2.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out, dpi=70)
    print(out)


if __name__ == "__main__":
    main()
