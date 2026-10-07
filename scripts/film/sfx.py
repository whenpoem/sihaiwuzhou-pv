"""在歌曲上叠加音效，输出 audio/song_sfx.wav，拼接全片时用它代替 song.wav。

目前只有一处：结尾窗外的 LED 熄灭（seg_h/ending.py 的 T_LED_OFF）之前，一声墙上开关的"咔嗒"。歌曲在这里
几乎无声（约 -50 dB），开关声单独就听得清楚。开关声按机械开关的发声方式合成：先是按下时很轻的一下，约 14 毫秒
后弹片翻转，发出主要的一下；每一下由一段极短的宽频噪声（触点撞击）和几个快速衰减的高频共振（塑料面板与弹片）
组成，再加一点低频（墙体）和很短的房间混响。

    python sfx.py
"""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "seg_h"))
SONG = ROOT / "audio" / "song.wav"
OUT = ROOT / "audio" / "song_sfx.wav"

T_CLICK_LEAD = 0.06                 # 开关声比灯灭早 60 毫秒：先听到开关，再看到变暗
PEAK_DB = -9.0


def _tick(sr, rng, modes, thump, dur=0.12):
    n = int(dur * sr)
    t = np.arange(n) / sr
    burst = rng.normal(0, 1, n) * np.exp(-t / 0.0012)
    burst -= np.convolve(burst, np.ones(8) / 8, mode="same")          # 去掉低频，只留撞击的"嗒"
    body = sum(a * np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)) * np.exp(-t / tau) for f, a, tau in modes)
    low = thump * np.sin(2 * np.pi * 140 * t) * np.exp(-t / 0.018) * (1 - np.exp(-t / 0.001))
    return 0.9 * burst + body + low


def click(sr):
    rng = np.random.default_rng(196)
    press = _tick(sr, rng, [(2400, 0.25, 0.006), (4100, 0.15, 0.004)], 0.10)
    snap = _tick(sr, rng, [(1850, 0.70, 0.012), (3300, 0.55, 0.009), (5400, 0.30, 0.005), (820, 0.25, 0.015)], 0.45)
    gap = int(0.014 * sr)
    x = np.zeros(gap + len(snap))
    x[:len(press)] += 0.35 * press[:len(x)]
    x[gap:] += snap
    tail = rng.normal(0, 1, int(0.25 * sr)) * np.exp(-np.arange(int(0.25 * sr)) / sr / 0.045)
    x = x + 0.06 * np.convolve(x, tail)[:len(x)]
    x = np.concatenate([x, 0.06 * np.convolve(x, tail)[len(x):len(x) + int(0.2 * sr)]])
    return x / np.abs(x).max() * 10 ** (PEAK_DB / 20)


def main():
    import ending as END
    x, sr = sf.read(SONG, dtype="float32")
    c = click(sr).astype(np.float32)
    i = int(round((END.T_LED_OFF - T_CLICK_LEAD) * sr))
    x[i:i + len(c)] += c[:, None]
    sf.write(OUT, x, sr, subtype="FLOAT")
    print(OUT, f"开关声在 {i / sr:.3f} 秒")


if __name__ == "__main__":
    main()
