"""同一段落换不同的提示语转写，观察结果是否随提示语改变；随提示语漂移的字可信度低。"""
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
PROMPTS = ["", "以下是中文歌曲《四海五洲》的歌词，用简体中文书写。", "歌词：",
           "这首歌写七十年代北京部队大院少年的夏天，可对照电影《阳光灿烂的日子》。以下是歌词，用简体中文书写。"]


def fmt(t):
    m, s = divmod(t, 60)
    return f"{int(m):02d}:{s:05.2f}"


def main():
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    a, b = float(sys.argv[1]), float(sys.argv[2])
    src = sys.argv[3] if len(sys.argv) > 3 else "stems/vocals.wav"
    y, _ = librosa.load(ROOT / "audio" / src, sr=SR, mono=True)
    clip = y[int(a * SR):int(b * SR)]
    clip = (clip / (np.abs(clip).max() + 1e-9) * 0.9).astype(np.float32)
    model = stable_whisper.load_model("large-v3-turbo", device="cuda")
    for p in PROMPTS:
        res = model.transcribe(clip, language="zh", initial_prompt=p or None, condition_on_previous_text=False,
                               beam_size=5, best_of=5, verbose=None)
        print(f"\n---- 提示语：{p[:20] or '（无）'}")
        for s in res.segments:
            print(f"  [{fmt(a + s.start)}] {T2S.convert(s.text.strip())}")


if __name__ == "__main__":
    main()
