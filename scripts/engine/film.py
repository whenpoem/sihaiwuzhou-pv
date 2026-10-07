"""成片输出：逐帧渲染、送给 ffmpeg 的 h264_nvenc 编码、静帧、预览和分段拼接。

视频只用显卡硬件编码（h264_nvenc），不用 libx264。RGB 转 YUV 时显式指定 BT.709 矩阵并写入色彩标记，
否则 ffmpeg 默认按 BT.601 转换，颜色会偏。音频取 audio/song.wav 中与画面对应的一段，编码为 AAC 256 kbps；
apad=whole_dur 在歌曲结束后补静音，保证音轨和画面一样长。

分段渲染时，帧号由时间取整得到（第 n 帧的时刻是 n/fps），颗粒和划痕以帧号为种子，所以分段之间完全衔接。
"""
import math
import os
import queue
import subprocess
import tempfile
import threading
import time
import shutil
import sys
from pathlib import Path

import numpy as np

from .gpu import BELOW_NORMAL, acquire_render_lock, create_context, low_priority
from .renderer import Renderer

ROOT = Path(__file__).resolve().parents[2]
# 优先用 conda 环境里带 NVENC 的 ffmpeg（Library/bin 下），没有时用系统路径上的
FFMPEG = Path(sys.prefix) / "Library" / "bin" / "ffmpeg.exe"
if not FFMPEG.exists():
    FFMPEG = Path(shutil.which("ffmpeg") or "ffmpeg")
SONG = ROOT / "audio" / "song.wav"
FILM_DURATION = 199.8

QUALITY = {
    "final": ["-preset", "p6", "-tune", "hq", "-rc", "vbr", "-cq", "16", "-b:v", "0", "-maxrate", "120M",
              "-bufsize", "240M", "-spatial-aq", "1", "-temporal-aq", "1", "-bf", "3", "-g", "120"],
    "preview": ["-preset", "p4", "-rc", "vbr", "-cq", "24", "-b:v", "0", "-bf", "2", "-g", "120"],
}


class _Writer:
    """ffmpeg 子进程。原始 RGB 帧经管道写入，由单独的线程负责写，渲染线程不必等待编码。"""

    def __init__(self, out, size, fps, audio_span=None, quality="final", meta=None):
        out = Path(out)
        out.parent.mkdir(parents=True, exist_ok=True)
        w, h = size
        cmd = [str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y",
               "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{w}x{h}", "-r", str(fps), "-i", "-"]
        if audio_span is not None:
            a0, dur = audio_span
            cmd += ["-ss", f"{a0:.6f}", "-t", f"{dur:.6f}", "-i", str(SONG)]
        cmd += ["-map", "0:v"]
        # setparams 把色彩标记写进帧属性，编码器据此写入码流（只给编码器参数时原色和传递函数会标成未知）
        cmd += ["-vf", "scale=out_color_matrix=bt709:out_range=tv:flags=accurate_rnd+full_chroma_int,format=yuv420p,"
                       "setparams=color_primaries=bt709:color_trc=bt709:colorspace=bt709:range=tv",
                "-c:v", "h264_nvenc", "-profile:v", "high"] + QUALITY[quality]
        if audio_span is not None:
            cmd += ["-map", "1:a", "-c:a", "aac", "-b:a", "256k", "-af", f"apad=whole_dur={audio_span[1]:.6f}",
                    "-t", f"{audio_span[1]:.6f}"]
        if meta:
            # 记下这一段的起点、帧率和帧数，concat 据此按精确的视频时长拼接并重配音频
            cmd += ["-metadata", "comment=" + ";".join(f"{k}={v}" for k, v in meta.items())]
        cmd += ["-movflags", "+faststart", str(out)]
        self.errf = tempfile.TemporaryFile()
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=self.errf,
                                     creationflags=BELOW_NORMAL)
        self.q = queue.Queue(maxsize=4)
        self.err = None
        self.th = threading.Thread(target=self._run, daemon=True)
        self.th.start()

    def _run(self):
        try:
            while True:
                b = self.q.get()
                if b is None:
                    break
                self.proc.stdin.write(b)
        except Exception as e:  # 管道断开通常意味着 ffmpeg 报错退出
            self.err = e

    def write(self, b):
        if self.err is not None:
            self.close()
        self.q.put(b)

    def close(self):
        self.q.put(None)
        self.th.join()
        try:
            self.proc.stdin.close()
        except Exception:
            pass
        rc = self.proc.wait()
        if rc != 0 or self.err is not None:
            self.errf.seek(0)
            msg = self.errf.read().decode("utf-8", "replace")[-3000:]
            raise RuntimeError(f"ffmpeg 编码失败（返回码 {rc}）：\n{msg}")


class Film:
    """一部片子的渲染入口。

    frame：t（秒）→ FrameSpec 的函数；fps、size 为成片规格；ss 为超采样倍数；
    msaa 为每个超采样像素的多重采样数（0 表示不用；大量硬边小方片，如翻板，可设 4）。
    """

    def __init__(self, frame, fps=60, size=(1920, 1080), ss=2, msaa=0):
        low_priority()
        acquire_render_lock()
        self.frame_fn = frame
        self.fps, self.size, self.ss, self.msaa = fps, tuple(size), ss, msaa
        self.ctx = create_context()
        self._renderers = {}
        self.last_stats = None

    def renderer(self, size=None, ss=None, msaa=None):
        size = tuple(size or self.size)
        ss = self.ss if ss is None else ss
        msaa = self.msaa if msaa is None else msaa
        key = (size, ss, msaa)
        if key not in self._renderers:
            # 不同规格的渲染器各自持有缓冲；同时只保留一个，节省显存
            for k in list(self._renderers):
                del self._renderers[k]
            self._renderers[key] = Renderer(self.ctx, size, ss, self.size, msaa)
        return self._renderers[key]

    def _frames(self, t0, t1):
        n0 = int(round(t0 * self.fps))
        n1 = int(round(t1 * self.fps))
        return n0, n1

    def _loop(self, t0, t1, out, r, subframes, shutter, audio, quality, timecode=False, label="渲染"):
        n0, n1 = self._frames(t0, t1)
        if n1 <= n0:
            raise ValueError(f"时间段为空：{t0}–{t1}")
        span = ((n0 / self.fps), (n1 - n0) / self.fps) if audio else None
        if audio and not SONG.exists():
            raise FileNotFoundError(f"找不到音频 {SONG}")
        meta = {"pv_t0": f"{n0 / self.fps:.6f}", "fps": self.fps, "frames": n1 - n0}
        wr = _Writer(out, (r.W, r.H), self.fps, span, quality, meta)
        times = []
        start = time.perf_counter()
        ctx = self.ctx
        nbytes = r.W * r.H * 3
        pbos = [ctx.buffer(reserve=nbytes), ctx.buffer(reserve=nbytes)]
        pending = None
        sub_hist = []
        spec_fn = _with_timecode(self.frame_fn, self.size) if timecode else self.frame_fn
        try:
            for f in range(n0, n1):
                ft = time.perf_counter()
                t = f / self.fps
                n = subframes(t) if callable(subframes) else subframes
                r.render(spec_fn, f, self.fps, n, shutter)
                # 异步读回：本帧读进一个像素缓冲，上一帧的缓冲此时已就绪，取出交给编码线程
                pbo = pbos[f % 2]
                r.read_into(pbo)
                if pending is not None:
                    wr.write(pending.read())
                pending = pbo
                times.append(time.perf_counter() - ft)
                sub_hist.append(n)
                k = f - n0 + 1
                if k % 60 == 0 or k == n1 - n0:
                    el = time.perf_counter() - start
                    avg = el / k
                    print(f"{label} {k}/{n1 - n0} 帧  平均 {avg * 1000:.1f} ms/帧  已用 {el:.0f} s  "
                          f"预计剩余 {avg * (n1 - n0 - k):.0f} s", flush=True)
            if pending is not None:
                wr.write(pending.read())
        finally:
            for b in pbos:
                b.release()
            wr.close()
        total = time.perf_counter() - start
        self.last_stats = {"frames": n1 - n0, "seconds": total, "ms_per_frame": 1000 * total / (n1 - n0),
                           "frame_ms": np.array(times) * 1000, "subframes": np.array(sub_hist)}
        print(f"{label}完成：{out}  {n1 - n0} 帧，{total:.1f} s，平均 {self.last_stats['ms_per_frame']:.1f} ms/帧", flush=True)
        return self.last_stats

    def render(self, t0, t1, out, subframes=4, audio=True, shutter=0.5):
        """正式渲染 [t0, t1) 到 mp4。subframes 为每帧子帧数，可以是常数或 t → 整数的函数。"""
        r = self.renderer()
        return self._loop(t0, t1, out, r, subframes, shutter, audio, "final")

    def preview(self, t0, t1, out, audio=True, scale=0.5, timecode=True):
        """预览：半分辨率、不超采样、不做运动模糊，右下角带时间码，供动态分镜检查节奏。"""
        size = (int(self.size[0] * scale) // 2 * 2, int(self.size[1] * scale) // 2 * 2)
        r = self.renderer(size, 1, 0)
        return self._loop(t0, t1, out, r, 1, 0.5, audio, "preview", timecode=timecode, label="预览")

    def frame_image(self, t, subframes=1, shutter=0.5):
        """渲染单帧，返回 (H, W, 3) 的 uint8 数组。"""
        r = self.renderer()
        f = int(round(t * self.fps))
        r.render(self.frame_fn, f, self.fps, subframes, shutter)
        return r.image().copy()

    def still(self, t, path, subframes=1, shutter=0.5):
        """输出单帧 PNG。"""
        from PIL import Image
        img = self.frame_image(t, subframes, shutter)
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        Image.fromarray(img).save(path)
        return img


def _with_timecode(fn, nominal):
    from .scene import Overlay

    def wrapped(t):
        spec = fn(t)
        m, s = divmod(t, 60)
        spec.overlays = list(spec.overlays) + [
            Overlay(f"{int(m)}:{s:05.2f}", xy=(nominal[0] - 24, nominal[1] - 24), anchor="right-bottom",
                    group="raw", size=34, kind="sans", weight=500, color=(1.0, 0.9, 0.2), opacity=0.9)]
        return spec
    return wrapped


def _part_info(path):
    """读出分段文件里由 Film 写入的起点、帧率和帧数。"""
    r = subprocess.run([str(FFMPEG), "-hide_banner", "-i", str(path)], capture_output=True, creationflags=BELOW_NORMAL)
    for line in r.stderr.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if line.startswith("comment") and "pv_t0=" in line:
            kv = dict(x.split("=", 1) for x in line.split(":", 1)[1].strip().split(";") if "=" in x)
            return float(kv["pv_t0"]), float(kv["fps"]), int(kv["frames"])
    raise ValueError(f"{path} 里没有 Film 写入的分段信息（pv_t0 / fps / frames），无法精确拼接")


def concat(parts, out, audio="wav", song=None):
    """把同样参数渲染的分段无损拼接：视频流直接复制，不重新编码。

    两个细节决定了拼接是否逐帧对齐。其一，每段的时长取"帧数 / 帧率"，不取容器时长：AAC 按 1024 个采样
    一包，音轨总比画面略长。其二，AAC 编码器会在音轨开头加 1024 个采样的预热，音轨的起点因此比画面早约
    23 毫秒；concat 分离器按最早的流对齐，若把音轨一起拼，画面会整体推迟约 1.4 帧。所以先把各段的视频流
    单独复制出来再拼，音频另行处理。
    audio="wav"（缺省）：从 song.wav 按第一段的起点重新取整段编码，拼接处没有咔声；
    audio="copy"：各段音频流单独拼接后复制（拼接处可能有细小的咔声）；
    audio=None：只要视频。
    song：audio="wav" 时代替 song.wav 的音频文件（例如叠加了音效的版本）。"""
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    infos = [_part_info(p) for p in parts]
    for (t0, fps, n), (t1, _, _) in zip(infos, infos[1:]):
        if abs(t0 + n / fps - t1) > 0.5 / fps:
            import warnings
            warnings.warn(f"分段不连续：{t0 + n / fps:.4f} 之后接 {t1:.4f}")
    total = sum(n / fps for _, fps, n in infos)
    tmpdir = Path(tempfile.mkdtemp(prefix="pv_concat_"))
    made = []

    def run(cmd):
        r = subprocess.run(cmd, capture_output=True, creationflags=BELOW_NORMAL)
        if r.returncode != 0:
            raise RuntimeError(f"拼接失败：\n{r.stderr.decode('utf-8', 'replace')[-3000:]}")

    def split(kind, ext):
        lst = tmpdir / f"{kind}.txt"
        lines = []
        for i, (p, (t0, fps, n)) in enumerate(zip(parts, infos)):
            q = tmpdir / f"{kind}{i}.{ext}"
            run([str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", "-i", str(p), "-map", f"0:{kind}",
                 "-c", "copy", str(q)])
            made.append(q)
            lines.append(f"file '{q.as_posix()}'\nduration {n / fps:.6f}\n")
        lst.write_text("".join(lines), encoding="utf-8")
        made.append(lst)
        return lst

    try:
        vlist = split("v", "mp4")
        cmd = [str(FFMPEG), "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(vlist)]
        if audio == "wav":
            a0 = infos[0][0]
            cmd += ["-ss", f"{a0:.6f}", "-t", f"{total:.6f}", "-i", str(song or SONG), "-map", "0:v", "-map", "1:a",
                    "-c:v", "copy", "-c:a", "aac", "-b:a", "256k", "-af", f"apad=whole_dur={total:.6f}"]
        elif audio == "copy":
            alist = split("a", "m4a")
            cmd += ["-f", "concat", "-safe", "0", "-i", str(alist), "-map", "0:v", "-map", "1:a", "-c", "copy"]
        else:
            cmd += ["-map", "0:v", "-c:v", "copy"]
        meta = f"pv_t0={infos[0][0]:.6f};fps={infos[0][1]:g};frames={sum(n for _, _, n in infos)}"
        cmd += ["-t", f"{total:.6f}", "-metadata", f"comment={meta}", "-movflags", "+faststart", str(out)]
        run(cmd)
    finally:
        for q in made:
            if q.exists():
                os.unlink(q)
        os.rmdir(tmpdir)
    return out
