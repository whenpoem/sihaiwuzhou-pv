"""节拍、段落与各声部响度分析，输出 audio/analysis.json 和概览图 audio/overview.png。

节拍用鼓声音轨的起音强度跟踪；小节首拍取底鼓落点最多的相位；调性用全曲色度向量与
Krumhansl 调性轮廓的相关系数估计；段落边界取自混音的自相似矩阵（MFCC 与色度）上的新颖度峰值，
再吸附到最近的小节首拍。
"""
import json
from pathlib import Path

import librosa
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from scipy.ndimage import uniform_filter1d
from scipy.signal import find_peaks

ROOT = Path(__file__).resolve().parent.parent
AUDIO = ROOT / "audio"
SR = 22050
HOP = 512
NOTES = ["C", "C#", "D", "Eb", "E", "F", "F#", "G", "Ab", "A", "Bb", "B"]
MAJOR = np.array([6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR = np.array([6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])


def load(name):
    return librosa.load(AUDIO / name, sr=SR, mono=True)[0]


def key_estimate(y):
    chroma = librosa.feature.chroma_cqt(y=y, sr=SR, hop_length=HOP).mean(1)
    best = []
    for k in range(12):
        for prof, mode in ((MAJOR, "大调"), (MINOR, "小调")):
            best.append((np.corrcoef(np.roll(prof, k), chroma)[0, 1], f"{NOTES[k]} {mode}"))
    best.sort(reverse=True)
    return best[:3]


def novelty(y, beats_t):
    """以拍为单位的自相似矩阵上做棋盘核卷积，返回每拍的新颖度。"""
    mfcc = librosa.feature.mfcc(y=y, sr=SR, hop_length=HOP, n_mfcc=20)
    chroma = librosa.feature.chroma_cqt(y=y, sr=SR, hop_length=HOP)
    frames = librosa.time_to_frames(beats_t, sr=SR, hop_length=HOP)
    feat = np.vstack([librosa.util.normalize(librosa.util.sync(mfcc, frames), axis=0),
                      librosa.util.normalize(librosa.util.sync(chroma, frames), axis=0)])
    S = np.corrcoef(feat.T)
    n, w = len(S), 16
    g = np.outer(np.r_[np.ones(w), -np.ones(w)], np.r_[np.ones(w), -np.ones(w)])
    g *= np.outer(np.hanning(2 * w), np.hanning(2 * w))
    nov = np.zeros(n)
    Sp = np.pad(S, w, mode="edge")
    for i in range(n):
        nov[i] = (Sp[i:i + 2 * w, i:i + 2 * w] * g).sum()
    return np.clip(nov, 0, None), S


def main():
    mix, drums, bass, other, vocals = (load(n) for n in ("song.wav", "stems/drums.wav", "stems/bass.wav",
                                                           "stems/other.wav", "stems/vocals.wav"))
    duration = len(mix) / SR

    onset = librosa.onset.onset_strength(y=drums, sr=SR, hop_length=HOP)
    tempo, beat_frames = librosa.beat.beat_track(onset_envelope=onset, sr=SR, hop_length=HOP)
    tempo = float(np.atleast_1d(tempo)[0])
    beats = librosa.frames_to_time(beat_frames, sr=SR, hop_length=HOP)

    # 底鼓（30–150 Hz）与军鼓（1.5–6 kHz）的起音
    S = np.abs(librosa.stft(drums, n_fft=2048, hop_length=HOP))
    freqs = librosa.fft_frequencies(sr=SR, n_fft=2048)

    def band(lo, hi):
        env = librosa.onset.onset_strength(S=librosa.amplitude_to_db(S[(freqs >= lo) & (freqs < hi)], ref=np.max),
                                           sr=SR, hop_length=HOP)
        return env / (env.max() + 1e-9)

    kick, snare = band(30, 150), band(1500, 6000)
    phase_score = [kick[beat_frames[p::4]].sum() for p in range(4)]
    downbeats = beats[int(np.argmax(phase_score))::4]

    # 按拍同步后第 0 段是第一拍之前的部分，第 i 段从第 i-1 拍开始
    nov, _ = novelty(mix, beats)
    seg_t = np.r_[0.0, beats]
    pk, _ = find_peaks(nov, distance=8, height=np.percentile(nov, 80))
    bounds = sorted({float(downbeats[np.argmin(np.abs(downbeats - seg_t[i]))]) for i in pk})

    def rms(y):
        r = librosa.feature.rms(y=y, frame_length=2048, hop_length=HOP)[0]
        t = librosa.frames_to_time(np.arange(len(r)), sr=SR, hop_length=HOP)
        grid = np.arange(0, duration, 1 / 30)
        return np.interp(grid, t, r)

    curves = {k: rms(v) for k, v in (("mix", mix), ("vocals", vocals), ("drums", drums), ("bass", bass), ("other", other))}
    ref = np.percentile(curves["mix"], 99)
    norm = {k: (v / ref).clip(0, 1.5) for k, v in curves.items()}

    out = {"duration": duration, "tempo": tempo, "beats": beats.round(4).tolist(),
           "downbeats": downbeats.round(4).tolist(), "boundaries": [round(b, 3) for b in bounds],
           "curves_fps": 30, **{f"{k}_rms": v.round(4).tolist() for k, v in norm.items()}}
    (AUDIO / "analysis.json").write_text(json.dumps(out), encoding="utf-8")

    ibi = np.diff(beats)
    print(f"时长 {duration:.2f} 秒；速度约 {tempo:.1f} BPM；拍间隔中位数 {np.median(ibi):.4f} 秒，标准差 {ibi.std():.4f}")
    print(f"节拍 {len(beats)} 个，小节 {len(downbeats)} 个，首拍 {downbeats[0]:.2f} 秒")
    print("调性候选：", "；".join(f"{n}（{c:.2f}）" for c, n in key_estimate(mix)))
    print("段落边界（秒）：", ", ".join(f"{b:.2f}" for b in bounds))
    # 每 4 小节的平均响度，便于看出段落起伏
    print("\n每 4 小节平均响度（混音 / 人声 / 鼓 / 贝斯 / 其他）：")
    for i in range(0, len(downbeats) - 1, 4):
        a, b = downbeats[i], downbeats[min(i + 4, len(downbeats) - 1)]
        sl = slice(int(a * 30), int(b * 30))
        vals = " ".join(f"{norm[k][sl].mean():.2f}" for k in ("mix", "vocals", "drums", "bass", "other"))
        print(f"  小节 {i + 1:3d}–{i + 4:3d}  {a:6.2f}–{b:6.2f} 秒  {vals}")

    grid = np.arange(len(norm["mix"])) / 30
    fig, axes = plt.subplots(6, 1, figsize=(24, 13), sharex=True)
    names = [("mix", "混音", "k"), ("vocals", "人声", "tab:red"), ("drums", "鼓", "tab:blue"),
             ("bass", "贝斯", "tab:green"), ("other", "其他乐器", "tab:purple")]
    for ax, (k, lab, c) in zip(axes, names):
        ax.plot(grid, uniform_filter1d(norm[k], 9), lw=0.8, color=c)
        ax.set_ylabel(lab, family="Microsoft YaHei")
    axes[5].plot(seg_t, nov / (nov.max() + 1e-9), lw=0.8, color="0.3")
    axes[5].set_ylabel("新颖度", family="Microsoft YaHei")
    for ax in axes:
        for d in downbeats[::4]:
            ax.axvline(d, color="0.88", lw=0.5, zorder=0)
        for b in bounds:
            ax.axvline(b, color="tab:orange", lw=1.0, zorder=0)
    axes[-1].set_xticks(np.arange(0, duration, 5))
    axes[-1].set_xlabel("时间（秒）", family="Microsoft YaHei")
    fig.tight_layout()
    fig.savefig(AUDIO / "overview.png", dpi=70)


if __name__ == "__main__":
    main()
