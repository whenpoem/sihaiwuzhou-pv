"""从分离出的人声转写歌词（Whisper large-v3-turbo，经 stable-ts），供人工核对。

做两遍转写并互相对照：
  A  整条人声一次转写；
  B  先按人声响度切成若干乐句块（静音超过 0.8 秒即断开），每块单独转写。
两遍结果不一致、或字的置信度低的地方，就是需要人工核对的位置。

输出（lyrics/ 目录）：transcribe_A.json、transcribe_B.json，以及控制台上的逐句对照。
"""
import ctypes
import json
from pathlib import Path

import librosa
import numpy as np
import opencc
import stable_whisper

ROOT = Path(__file__).resolve().parent.parent
VOCALS = ROOT / "audio" / "stems" / "vocals.wav"
OUT = ROOT / "lyrics"
SR = 16000
PROMPT = "以下是中文歌曲《四海五洲》的歌词，用简体中文书写。"
T2S = opencc.OpenCC("t2s")


def fmt(t):
    m, s = divmod(t, 60)
    return f"{int(m):02d}:{s:05.2f}"


def vocal_chunks(y, gap=0.8, pad=0.25, hop=0.02):
    """按人声响度找乐句块：响度低于全曲第 95 百分位的 6% 视为静音。"""
    h = int(hop * SR)
    rms = librosa.feature.rms(y=y, frame_length=2 * h, hop_length=h)[0]
    on = rms > 0.06 * np.percentile(rms, 95)
    idx = np.flatnonzero(on)
    chunks, s, prev = [], idx[0], idx[0]
    for i in idx[1:]:
        if (i - prev) * hop > gap:
            chunks.append((s * hop, prev * hop))
            s = i
        prev = i
    chunks.append((s * hop, prev * hop))
    return [(max(0.0, a - pad), b + pad) for a, b in chunks if b - a > 0.3]


def to_json(res, offset=0.0):
    segs = []
    for seg in res.segments:
        words = [{"w": T2S.convert(w.word.strip()), "start": round(offset + w.start, 3), "end": round(offset + w.end, 3),
                  "prob": round(float(w.probability or 0), 3)} for w in seg.words if w.word.strip()]
        segs.append({"start": round(offset + seg.start, 3), "end": round(offset + seg.end, 3),
                     "text": T2S.convert(seg.text.strip()), "words": words})
    return segs


def main():
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    OUT.mkdir(exist_ok=True)
    y, _ = librosa.load(VOCALS, sr=SR, mono=True)
    model = stable_whisper.load_model("large-v3-turbo", device="cuda")
    opts = dict(language="zh", initial_prompt=PROMPT, condition_on_previous_text=False, beam_size=5, best_of=5,
                verbose=None)

    res_a = model.transcribe(y, **opts)
    a = to_json(res_a)
    (OUT / "transcribe_A.json").write_text(json.dumps(a, ensure_ascii=False, indent=1), encoding="utf-8")

    b = []
    chunks = vocal_chunks(y)
    for s, e in chunks:
        res = model.transcribe(y[int(s * SR):int(e * SR)], **opts)
        b.extend(to_json(res, offset=s))
    (OUT / "transcribe_B.json").write_text(json.dumps(b, ensure_ascii=False, indent=1), encoding="utf-8")

    print(f"人声块 {len(chunks)} 个：" + "，".join(f"{fmt(s)}–{fmt(e)}" for s, e in chunks))
    for name, segs in (("A", a), ("B", b)):
        print(f"\n==== 转写 {name} ====")
        for g in segs:
            low = "".join(w["w"] for w in g["words"] if w["prob"] < 0.5)
            print(f"[{fmt(g['start'])}–{fmt(g['end'])}] {g['text']}" + (f"    低置信：{low}" if low else ""))


if __name__ == "__main__":
    main()
