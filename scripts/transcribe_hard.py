"""对转写不稳定的段落换几种输入重新转写，列出候选，供人工核对时参考。

短片段容易让模型凭空编出"字幕志愿者"之类的文字，因此每段取较长的窗口（含前后各一两句），
并把人声按峰值归一化（桥段人声很轻）。每段做五种转写：人声原速、人声放慢到 0.85 倍（音高不变）、
混音原速、人声原速加采样温度 0.3（两次）。不同做法给出的结果越一致，越可信。
"""
import ctypes
import sys
from pathlib import Path

import librosa
import numpy as np
import opencc
import stable_whisper

ROOT = Path(__file__).resolve().parent.parent
SR = 16000
T2S = opencc.OpenCC("t2s")
PROMPT = "以下是中文歌曲的歌词，用简体中文书写。"
# (起始秒, 结束秒, 说明)
SPANS = [(100.5, 125.0, "主歌二与预副歌二"), (158.0, 193.6, "桥段与尾段"), (163.5, 179.0, "桥段（单独）")]


def fmt(t):
    m, s = divmod(t, 60)
    return f"{int(m):02d}:{s:05.2f}"


def run(model, clip, offset, rate=1.0, **kw):
    opts = dict(language="zh", initial_prompt=PROMPT, condition_on_previous_text=False, verbose=None)
    opts.update(kw)
    res = model.transcribe(clip, **opts)
    return "\n      ".join(f"[{fmt(offset + s.start * rate)}] {T2S.convert(s.text.strip())}" for s in res.segments)


def norm(x):
    return (x / (np.abs(x).max() + 1e-9) * 0.9).astype(np.float32)


def main():
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    voc, _ = librosa.load(ROOT / "audio" / "stems" / "vocals.wav", sr=SR, mono=True)
    mix, _ = librosa.load(ROOT / "audio" / "song.wav", sr=SR, mono=True)
    model = stable_whisper.load_model("large-v3-turbo", device="cuda")
    spans = SPANS if len(sys.argv) < 2 else [SPANS[int(i)] for i in sys.argv[1].split(",")]
    for a, b, name in spans:
        v = norm(voc[int(a * SR):int(b * SR)])
        m = norm(mix[int(a * SR):int(b * SR)])
        slow = norm(librosa.effects.time_stretch(v, rate=0.85))
        print(f"\n==== {name} {fmt(a)}–{fmt(b)} ====")
        print("人声原速\n     ", run(model, v, a, beam_size=5, best_of=5))
        print("人声 0.85 倍\n     ", run(model, slow, a, rate=0.85, beam_size=5, best_of=5))
        print("混音原速\n     ", run(model, m, a, beam_size=5, best_of=5))
        for k in range(2):
            print(f"温度 0.3 #{k + 1}\n     ", run(model, v, a, temperature=0.3, best_of=5))


if __name__ == "__main__":
    main()
