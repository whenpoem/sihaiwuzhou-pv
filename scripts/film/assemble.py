"""全片的正式渲染与拼接。

各段的场景脚本各自定义 frame(t)，这里按交接表依次以成片规格（1920×1080、每秒 60 帧、2 倍超采样）渲染，
每段输出一个文件，最后用引擎的 concat 无损拼接成全片，音频按第一段的起点从 song.wav 重新取整段编码。
渲染有全机唯一的渲染锁，同一时刻只渲染一段；某段已经渲染好且脚本没有改动时跳过。

    python assemble.py render [段 ...]        渲染指定的段（缺省为全部）
    python assemble.py concat                 把已渲染的各段拼成全片
    python assemble.py status                 列出各段的渲染状态

每段的每帧子帧数取自场景模块的 SUBFRAMES 或 subframes（整数，或 t → 整数的函数），没有定义时取 2。
每段在单独的进程里渲染：各段目录里有同名的模块（common.py、mats.py 等），同一个进程里先后加载会互相顶替。
"""
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

OUT = ROOT / "renders" / "final"

# (段名, 场景脚本, 起点, 终点)；时刻都对齐到每秒 60 帧的帧边界，见 handoff.py 的交接表
SEGMENTS = [
    ("A1", "seg_a1/scene.py", 0.0, 1620 / 60),
    ("A2", "seg_a2/scene.py", 1620 / 60, 2407 / 60),
    ("B", "seg_b/scene.py", 2407 / 60, 3060 / 60),
    ("C", "seg_c/flat.py", 3060 / 60, 4524 / 60),
    ("D", "seg_d/scene.py", 4524 / 60, 6123 / 60),
    ("E", "seg_e/scene.py", 6123 / 60, 6960 / 60),
    ("F", "seg_f/scene.py", 6960 / 60, 9080 / 60),
    ("G", "seg_g/scene.py", 9080 / 60, 9896 / 60),
    ("H", "seg_h/scene.py", 9896 / 60, 11986 / 60),
]


def load(rel):
    path = HERE.parent / rel
    sys.path.insert(0, str(path.parent))
    spec = importlib.util.spec_from_file_location(f"pv_{path.parent.name}_{path.stem}", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def stamp(rel):
    """段目录里所有脚本的最新修改时间：脚本改过就要重新渲染。"""
    d = (HERE.parent / rel).parent
    return max(p.stat().st_mtime for p in d.glob("*.py"))


def status_file():
    return OUT / "status.json"


def read_status():
    f = status_file()
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}


def render_one(name):
    """在本进程里渲染一段（由 render 为每段单独启动一个进程调用）。"""
    from engine import Film
    OUT.mkdir(parents=True, exist_ok=True)
    rel, t0, t1 = next((r, a, b) for n, r, a, b in SEGMENTS if n == name)
    mod = load(rel)
    sub = getattr(mod, "SUBFRAMES", None) or getattr(mod, "subframes", None) or 2
    film = Film(mod.frame, fps=60, size=(1920, 1080), ss=2)
    t_start = time.time()
    stats = film.render(t0, t1, str(OUT / f"{name}.mp4"), subframes=sub)
    st = read_status()
    st[name] = {"stamp": stamp(rel), "seconds": round(time.time() - t_start, 1),
                "ms_per_frame": round(stats["ms_per_frame"], 1)}
    status_file().write_text(json.dumps(st, ensure_ascii=False, indent=1), encoding="utf-8")


def render(names):
    OUT.mkdir(parents=True, exist_ok=True)
    st = read_status()
    for name, rel, t0, t1 in SEGMENTS:
        if names and name not in names:
            continue
        out = OUT / f"{name}.mp4"
        if out.exists() and st.get(name, {}).get("stamp") == stamp(rel) and not names:
            print(f"{name} 已是最新，跳过")
            continue
        r = subprocess.run([sys.executable, str(Path(__file__).resolve()), "_one", name])
        if r.returncode != 0:
            raise SystemExit(f"{name} 渲染失败（返回码 {r.returncode}）")


def concat():
    from engine import concat as _concat
    parts = [OUT / f"{name}.mp4" for name, *_ in SEGMENTS]
    missing = [p.name for p in parts if not p.exists()]
    if missing:
        raise SystemExit(f"还缺这些段：{missing}")
    out = ROOT / "renders" / "四海五洲_PV.mp4"
    sfx = ROOT / "audio" / "song_sfx.wav"               # sfx.py 生成的叠加了音效的歌曲
    _concat([str(p) for p in parts], str(out), song=sfx if sfx.exists() else None)
    print(out)


def status():
    st = read_status()
    for name, rel, t0, t1 in SEGMENTS:
        out = OUT / f"{name}.mp4"
        ok = (HERE.parent / rel).exists()
        fresh = out.exists() and ok and st.get(name, {}).get("stamp") == stamp(rel)
        print(f"{name:3s} {t0:8.3f}–{t1:8.3f}  脚本{'有' if ok else '无'}  {'已渲染' if out.exists() else '未渲染'}"
              f"{'（最新）' if fresh else ''}  {st.get(name, {})}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "render":
        render(sys.argv[2:])
    elif cmd == "_one":
        render_one(sys.argv[2])
    elif cmd == "concat":
        concat()
    else:
        status()
