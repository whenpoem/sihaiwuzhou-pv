"""《四海五洲》PV 的时间数据：节拍网格、鼓点、逐字起点。

输入
  audio/song.wav、audio/stems/{drums,vocals}.wav   混音与 Demucs 分轨
  lyrics/lines.json                                 Whisper（stable-ts）逐字对齐结果，只读
  lyrics/manual_fixes.json                          人工修正，覆盖自动结果（不存在时自动建立空模板）
输出
  data/timing.json                                  全部时间数据
  audio/check/                                      校对音轨与校对图
  data/cache/vocal_features.npz                     人声基频等特征的缓存（pyin 较慢，约一分钟）

做法概要
  1. 节拍网格：在鼓分轨上检测底鼓，音头用 1–8 kHz 的击打声定位；把起点归到八分音符网格上做线性
     回归，得到恒定拍长与相位；再分段回归、看残差随时间的走势，检验速度是否恒定。小节首拍的相位由
     “底鼓在 1、3 拍，军鼓在 2、4 拍”确定到半小节，再由鼓在休止后的第一击落在小节首拍上确定到整小节。
  2. 鼓点：底鼓、军鼓、镲片按频段分开检测，起点修正到音头，并标注最近的十六分音符网格位置；离网格
     20 毫秒以上的高频起点是人声擦音串进鼓分轨的声音，舍去。
  3. 字的起点：人声是歌声合成软件制作的，音符落在十六分音符网格上，元音从音符开头响起，辅音在音符
     之前。因此在人声分轨上检测“嗓音响起”的候选时刻（浊音概率上升、中低频能量上升、音高跳变、
     频谱跳变），再把全曲的字按顺序分配给候选时刻（动态规划），分配时兼顾候选强度、声母类型、
     停顿位置、网格位置和原对齐时间。
  4. 人工修正：读 lyrics/manual_fixes.json，覆盖对应字的起点或结束时刻，然后统一计算结束时刻、
     乐句和网格位置。

运行：python scripts/timing.py
"""
import ctypes
import json
import subprocess
import shutil
import sys
from pathlib import Path

import librosa
import matplotlib
import numpy as np
import soundfile as sf
from pypinyin import Style, lazy_pinyin
from scipy.ndimage import uniform_filter1d
from scipy.signal import butter, find_peaks, hilbert, sosfiltfilt

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

plt.rcParams["font.family"] = ["Microsoft YaHei", "SimHei", "sans-serif"]
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parent.parent
AUDIO = ROOT / "audio"
LYR = ROOT / "lyrics"
DATA = ROOT / "data"
CHECK = AUDIO / "check"
CACHE = DATA / "cache"
# 优先用 conda 环境里带 NVENC 的 ffmpeg（Library/bin 下），没有时用系统路径上的
FFMPEG = Path(sys.prefix) / "Library" / "bin" / "ffmpeg.exe"
if not FFMPEG.exists():
    FFMPEG = Path(shutil.which("ffmpeg") or "ffmpeg")

SR = 44100
FH = 0.01            # 人声特征的帧长：10 毫秒
MIN_GAP = 0.08       # 相邻两字起点的最小间隔（十六分音符约 0.107 秒，留一点测量误差）
MF_WEIGHT = 0.4      # 梅尔频谱变化量在新颖度中的权重（0、0.4、0.6、0.8、1.0 中，0.4 使字起点最贴近网格）


def low_priority():
    """把本进程设为低于正常优先级，避免长时间计算拖慢前台。"""
    try:
        k = ctypes.windll.kernel32
        k.SetPriorityClass(k.GetCurrentProcess(), 0x4000)
    except Exception:
        pass


def load_mono(path):
    y, sr = sf.read(path, always_2d=True)
    assert sr == SR, f"{path} 采样率是 {sr}，预期 {SR}"
    return y.mean(1)


# ======================================================================
# 一、鼓分轨的频段包络与起点
# ======================================================================
DRUM_HOP = 128                                   # 约 2.9 毫秒一帧
BANDS = {"low": (30, 110), "mid": (150, 350), "noise": (1000, 5000), "high": (7000, 16000)}


def drum_bands(y):
    """各频段的对数能量（dB），帧时刻 = 帧号 × hop / sr（STFT 居中加窗）。"""
    S = np.abs(librosa.stft(y, n_fft=1024, hop_length=DRUM_HOP, center=True)) ** 2
    f = librosa.fft_frequencies(sr=SR, n_fft=1024)
    env = {k: 10 * np.log10(S[(f >= lo) & (f < hi)].sum(0) + 1e-10) for k, (lo, hi) in BANDS.items()}
    return env, np.arange(S.shape[1]) * DRUM_HOP / SR


def band_peaks(e, min_dist_s, rise_db):
    """在一个频段的对数能量上找起音：能量在约 9 毫秒内比此前 35 毫秒的最低点上升至少 rise_db。

    返回 (帧号, 上升量 dB, 峰值电平 dB)。用“上升量”而不是绝对电平判断起音，是因为副歌里镲片和
    混响铺满高频，绝对电平一直很高，只有上升沿才对应一次击打。
    """
    n = len(e)
    pre = np.full(n, np.inf)
    for k in range(1, 13):                       # 此前 12 帧（约 35 毫秒）里的最低点
        pre[k:] = np.minimum(pre[k:], e[:-k])
    post = e.copy()
    for k in range(1, 4):                        # 此后 3 帧（约 9 毫秒）里的最高点
        post[:-k] = np.maximum(post[:-k], e[k:])
    rise = np.where(np.isfinite(pre), post - pre, 0)
    rise = uniform_filter1d(rise, 3)
    pk, _ = find_peaks(rise, height=rise_db, distance=max(1, int(min_dist_s * SR / DRUM_HOP)))
    level = np.array([e[p:p + 8].max() for p in pk])
    return pk, rise[pk], level


def refine_attack(env_lin, t_coarse, frac=0.3, before=0.06, after=0.04):
    """把粗略起点修正到音头：在包络峰值之前，包络首次超过“底 + frac × 峰高”的时刻。

    制作软件里鼓的采样从音头开始放在网格上，听感上的起点也在音头，所以取上升沿的前段而不取峰值
    （峰值要晚 10 到 30 毫秒）。搜索窗口为粗略起点前 before 秒到后 after 秒；频段能量的上升沿峰值
    比真实音头晚 20–40 毫秒（低频尤甚），所以默认窗口向前多取一些。
    """
    out = []
    for t in t_coarse:
        a = max(0, int((t - before) * SR))
        b = min(len(env_lin), int((t + after) * SR))
        seg = env_lin[a:b]
        p = int(np.argmax(seg))
        base = seg[:max(1, p)].min() if p > 0 else seg[0]
        thr = base + frac * (seg[p] - base)
        i = p
        while i > 0 and seg[i] > thr:
            i -= 1
        out.append((a + i) / SR)
    return np.array(out)


def band_envelope(y, lo, hi):
    """零相位带通（不引入时延）后的希尔伯特包络，再做 1 毫秒平滑。"""
    sos = butter(4, [lo, min(hi, SR / 2 - 100)], btype="band", fs=SR, output="sos")
    env = np.abs(hilbert(sosfiltfilt(sos, y)))
    w = int(0.001 * SR)
    return np.convolve(env, np.ones(w) / w, mode="same")


def detect_drums(y):
    """检测底鼓、军鼓、镲片的起点与强度。

    底鼓：30–110 Hz 能量的上升沿，音头用 1–8 kHz 的击打声定位（见下文）。
    军鼓：150–350 Hz（鼓身）和 1–5 kHz（响弦噪声）同时上升；只有一个频段上升的，多半是底鼓的
          泛音或镲片，不算军鼓。
    镲片：7–16 kHz 的上升沿，且不与军鼓同时（军鼓的噪声也延伸到高频）。
    强度：该频段起音后的峰值电平，按全曲同类击打的第 98 百分位归一化到 0–1。
    """
    env, ft = drum_bands(y)
    ref = {k: np.percentile(v, 99.5) for k, v in env.items()}
    H = DRUM_HOP / SR

    # 底鼓：上升至少 15 dB、峰值不低于全曲高位 24 dB。上升只有 7–10 dB 的，是上一下底鼓衰减时
    # 低频能量的起伏；电平很低的，多半是贝斯串进鼓分轨的声音。
    kp, kr, kl = band_peaks(env["low"], 0.07, 15.0)
    keep = kl > ref["low"] - 24
    kp, kr, kl = kp[keep], kr[keep], kl[keep]

    # 军鼓：以鼓身频段（150–350 Hz）的强上升为主，同时要求响弦噪声频段（1–5 kHz）在 25 毫秒内
    # 也有上升。底鼓也会让鼓身频段上升，但电平低 5–10 dB，所以与底鼓同时（60 毫秒内）的候选，
    # 只有鼓身电平接近全曲高位时才算军鼓。
    mp, mr, ml = band_peaks(env["mid"], 0.06, 20.0)
    sp, _, _ = band_peaks(env["noise"], 0.05, 6.0)
    snare = []
    for p, r, l in zip(mp, mr, ml):
        if l < ref["mid"] - 6:
            continue
        if not len(sp) or np.min(np.abs(sp - p)) * H > 0.025:
            continue
        near_kick = len(kp) and np.min(np.abs(kp - p)) * H < 0.06
        if near_kick and l < ref["mid"] - 4:
            continue
        snare.append((p, r, l))
    snare = np.array(snare) if snare else np.zeros((0, 3))

    # 镲片：高频（7–16 kHz）的上升沿，排除与军鼓同时的（军鼓的噪声也延伸到高频）
    hp, hr, hl = band_peaks(env["high"], 0.05, 5.0)
    st = snare[:, 0] if len(snare) else np.array([])
    hat_keep = np.array([len(st) == 0 or np.min(np.abs(st - p)) * H > 0.025 for p in hp], bool)
    hp, hr, hl = hp[hat_keep], hr[hat_keep], hl[hat_keep]

    # 底鼓的音头分两步定位：先用低频包络（35–130 Hz，15% 处）找到这一下底鼓，再在其前 25 毫秒到后
    # 8 毫秒内用 1–8 kHz 的“击打声”包络取音头。低频包络上升慢，比击打声晚约 15 毫秒；击打声的起点
    # 与军鼓音头一致，全曲离散程度也最小。第二步的窗口很窄，避免把相邻的镲片误当作击打声。
    kick_low_env = band_envelope(y, 35, 130)
    kick_env = band_envelope(y, 1000, 8000)
    snare_env = band_envelope(y, 150, 5000)
    hat_env = band_envelope(y, 7000, 16000)

    def pack(frames, level, env_lin, first_env=None):
        if first_env is None:
            t = refine_attack(env_lin, frames * DRUM_HOP / SR)
        else:
            t = refine_attack(first_env, frames * DRUM_HOP / SR, frac=0.15)
            t = refine_attack(env_lin, t, before=0.025, after=0.008)
        lin = 10 ** (level / 20)
        strength = np.clip(lin / np.percentile(lin, 98), 0, 1) if len(lin) else lin
        # 两个粗略起点可能修正到同一个音头上，25 毫秒内只保留较强的一个
        order = np.argsort(t)
        t, strength = t[order], strength[order]
        keep = np.ones(len(t), bool)
        for i in range(1, len(t)):
            j = i - 1
            while j >= 0 and not keep[j]:
                j -= 1
            if j >= 0 and t[i] - t[j] < 0.025:
                if strength[i] > strength[j]:
                    keep[j] = False
                else:
                    keep[i] = False
        return t[keep], strength[keep]

    kick_t, kick_s = pack(kp, kl, kick_env, first_env=kick_low_env)
    snare_t, snare_s = pack(snare[:, 0].astype(int), snare[:, 2], snare_env) if len(snare) else (np.array([]), np.array([]))
    hat_t, hat_s = pack(hp, hl, hat_env)
    hk = hat_s >= 0.05                           # 极弱的高频起伏（多为其他声部串音）不计
    hat_t, hat_s = hat_t[hk], hat_s[hk]
    return {"kick": (kick_t, kick_s), "snare": (snare_t, snare_s), "hat": (hat_t, hat_s)}, env, ft


# ======================================================================
# 二、节拍网格
# ======================================================================
def fit_grid(kick_t, kick_s):
    """用较强的底鼓起点拟合恒定拍长与相位。

    底鼓除了落在拍上，也常落在反拍（八分音符的后半）上，所以先把每个起点归到八分音符网格的最近
    格点，再对“格点序号—时刻”做线性回归；残差超过 35 毫秒的点（装饰音、误检）剔除后重新回归，
    迭代四次。拍长初值由对八分音符周期的圆周统计量扫描得到（各起点相位越集中，周期越可能正确）。
    """
    x = kick_t[kick_s > 0.35]
    best = None
    for P in np.arange(0.40, 0.44, 0.00002):
        r = abs(np.exp(2j * np.pi * x / (P / 2)).sum()) / len(x)
        if best is None or r > best[0]:
            best = (r, P)
    P = best[1]
    # 平均相位角 θ 对应的格点为 x = θ/(2π)·(P/2) + k·(P/2)
    ph = np.angle(np.exp(2j * np.pi * x / (P / 2)).sum()) / (2 * np.pi) * (P / 2)
    c = np.array([ph % (P / 2), P / 2])
    for _ in range(4):
        n = np.round((x - c[0]) / c[1])
        A = np.c_[np.ones_like(n), n]
        res = x - A @ c
        keep = np.abs(res) < 0.035
        c = np.linalg.lstsq(A[keep], x[keep], rcond=None)[0]
    n = np.round((x - c[0]) / c[1])
    res = x - (c[0] + c[1] * n)
    keep = np.abs(res) < 0.035
    # 八分音符网格的格点有“正拍”和“反拍”两类；底鼓的力度主要落在正拍上，据此确定哪类是拍
    s_kept = kick_s[kick_s > 0.35][keep]
    if s_kept[np.mod(n[keep], 2) == 1].sum() > s_kept[np.mod(n[keep], 2) == 0].sum():
        c[0] += c[1]
        n = n - 1
    # 斜率的标准误，用来判断拟合拍长与整数速度（如每分钟 140 拍）的差别是否显著
    A = np.c_[np.ones(keep.sum()), n[keep]]
    sigma = res[keep].std(ddof=2)
    cov = sigma ** 2 * np.linalg.inv(A.T @ A)
    return {"t0": float(c[0]), "period": float(2 * c[1]), "period_se": float(2 * np.sqrt(cov[1, 1])),
            "x": x[keep], "n": n[keep], "res": res[keep], "res_std": float(sigma), "n_used": int(keep.sum()),
            "n_total": int(len(x))}


def tempo_check(fit, segments):
    """分段回归：每段单独拟合拍长，并计算该段残差相对全曲网格的平均值（毫秒）。

    若速度有变化，分段拍长会系统性地偏离，全局残差也会随时间单调漂移；若速度恒定，分段拍长只在
    测量误差范围内波动，残差均值都接近 0。
    """
    rows = []
    for name, a, b in segments:
        m = (fit["x"] >= a) & (fit["x"] < b)
        if m.sum() < 8:
            continue
        A = np.c_[np.ones(m.sum()), fit["n"][m]]
        c = np.linalg.lstsq(A, fit["x"][m], rcond=None)[0]
        r = fit["x"][m] - A @ c
        se = r.std(ddof=2) * np.sqrt(np.linalg.inv(A.T @ A)[1, 1]) * 2
        rows.append({"segment": name, "start": a, "end": b, "n": int(m.sum()),
                     "beat_period": round(float(2 * c[1]), 6), "beat_period_se": round(float(se), 6),
                     "bpm": round(float(30 / c[1]), 3),
                     "mean_residual_ms": round(float(1000 * fit["res"][m].mean()), 2),
                     "residual_std_ms": round(float(1000 * r.std()), 2)})
    # 残差对时间的线性趋势（毫秒/分钟）：恒定速度下应接近 0
    slope = np.polyfit(fit["x"] / 60, fit["res"] * 1000, 1)[0]
    return rows, float(slope)


def downbeat_phase(t0, P, kick, snare, entries, duration):
    """确定哪一拍是小节首拍（拍序号对 4 取余的值）。

    第一步：4/4 拍流行乐的底鼓重在 1、3 拍，军鼓在 2、4 拍，据此把相位确定到“1/3 拍”或“2/4 拍”
            两种之一（只能确定到半小节，因为 1 与 3 的鼓型相同）。
    第二步：鼓在长时间休止后重新进入、段落开始时，总是落在小节首拍上；用这些进入点在两种候选
            相位中二选一。
    """
    def score(times, strength, phase):
        k = np.round((times - t0) / P)
        on = np.abs(times - (t0 + k * P)) < 0.03
        return float(strength[on & (np.mod(k, 2) == phase)].sum())

    kick_odd = score(*kick, 1) - score(*kick, 0)
    snare_odd = score(*snare, 1) - score(*snare, 0)
    kick_parity = 1 if kick_odd - snare_odd > 0 else 0          # 底鼓所在拍的奇偶
    cands = [kick_parity, kick_parity + 2]
    votes = []
    for ph in cands:
        v = 0
        for t in entries:
            k = (t - t0) / P
            if abs(k - round(k)) < 0.12 and int(round(k)) % 4 == ph:
                v += 1
        votes.append(v)
    phase = cands[int(np.argmax(votes))]
    return phase, {"kick_on_odd_minus_even": round(kick_odd, 2), "snare_on_odd_minus_even": round(snare_odd, 2),
                   "candidate_phases": cands, "entry_votes": votes}


def drum_entries(drums, duration, gap=1.5):
    """鼓在休止至少 gap 秒之后重新开始连续演奏的时刻（底鼓或军鼓的第一下）。

    主歌前半和主歌二里每两小节只有一下底鼓，这种稀疏的单击不算“鼓回来”：要求进入后 2.5 秒内
    至少还有 6 下底鼓或军鼓。返回 (连续演奏的进入点, 所有休止后的第一下)，后者用于判断小节相位。
    """
    t = np.sort(np.r_[drums["kick"][0][drums["kick"][1] > 0.2], drums["snare"][0][drums["snare"][1] > 0.2]])
    dense, any_entry = [], []
    for i, x in enumerate(t):
        if i == 0 or x - t[i - 1] >= gap:
            any_entry.append(float(x))
            if ((t > x) & (t <= x + 2.5)).sum() >= 6:
                dense.append(float(x))
    return dense, any_entry


def cut_time(mix, start=170.0):
    """歌曲戛然而止的时刻：混音 10 毫秒电平最后一次处在“结尾前 10 秒的响亮电平减 6 dB”以上的时刻。

    结尾的骤停之后还有约一秒的混响尾音，电平是逐渐衰减的，所以不找“骤降”，而找响亮部分的终点。
    """
    fr = int(0.01 * SR)
    seg = mix[int(start * SR):]
    n = len(seg) // fr
    db = 20 * np.log10(np.sqrt((seg[:n * fr].reshape(n, fr) ** 2).mean(1)) + 1e-9)
    sm = uniform_filter1d(db, 3)
    loud_ref = np.percentile(sm, 90)
    idx = np.where(sm >= loud_ref - 6)[0]
    return float(start + (idx[-1] + 1) * 0.01) if len(idx) else None


# ======================================================================
# 三、人声特征与“嗓音响起”的候选时刻
# ======================================================================
def vocal_features(vocals):
    """10 毫秒一帧的人声特征。

    vprob：pyin 给出的浊音概率（声带振动、有音高的概率），辅音和停顿处下降；f0：基频。
    这两项计算较慢（约一分钟），缓存在 data/cache/vocal_features.npz，人声文件变化时自动重算。
    lm：100–3000 Hz 能量（dB），元音的主要能量在此；tot：全频带能量（dB），用于判断真正的停顿
    （擦音处 lm 很低但 tot 不低）；hf：4 kHz 以上能量占比，擦音、送气音（s、sh、x、c、q、h 等）
    在此处显著升高；mf：梅尔频谱变化量（见 mel_flux）。后四项每次重新计算。
    """
    src = AUDIO / "stems" / "vocals.wav"
    key = f"{src.stat().st_size}-{int(src.stat().st_mtime)}-v2"
    cache = CACHE / "vocal_features.npz"
    feats = None
    if cache.exists():
        z = np.load(cache, allow_pickle=False)
        if str(z["key"]) == key:
            feats = {k: z[k] for k in ("vprob", "f0")}
    if feats is None:
        print("计算人声基频（pyin，约一分钟）……")
        y16 = librosa.resample(vocals, orig_sr=SR, target_sr=16000)
        f0, _, vprob = librosa.pyin(y16, fmin=90, fmax=1100, sr=16000, frame_length=1024, hop_length=160, center=True)
        feats = {"vprob": vprob, "f0": f0}
        CACHE.mkdir(parents=True, exist_ok=True)
        np.savez(cache, key=key, **feats)
    S = np.abs(librosa.stft(vocals, n_fft=1024, hop_length=441, center=True)) ** 2
    f = librosa.fft_frequencies(sr=SR, n_fft=1024)
    tot = S.sum(0) + 1e-12
    n = min(len(feats["f0"]), S.shape[1])
    feats = {"vprob": feats["vprob"][:n], "f0": feats["f0"][:n],
             "lm": (10 * np.log10(S[(f >= 100) & (f < 3000)].sum(0) + 1e-12))[:n],
             "tot": (10 * np.log10(tot))[:n], "hf": (S[f >= 4000].sum(0) / tot)[:n]}
    feats["mf"] = mel_flux(vocals, n)
    return feats


def mel_flux(vocals, n):
    """120–3800 Hz 梅尔频谱的正向变化量（各频带对数能量上升量的平均），10 毫秒一帧。

    连唱时前后两个字之间没有停顿，但共振峰和音高会变，频谱整体发生跳变；这个量对低通处理过的
    人声（桥段）同样有效，因为它只用 3.8 kHz 以下的频带。按人声响亮帧的第 95 百分位归一化。
    """
    M = librosa.feature.melspectrogram(y=vocals, sr=SR, n_fft=1024, hop_length=441, n_mels=48, fmin=120, fmax=3800)
    L = 10 * np.log10(M + 1e-10)
    L = np.maximum(L, np.percentile(L, 99) - 60)
    fl = np.r_[0, np.clip(np.diff(L, axis=1), 0, None).mean(0)]
    fl = fl[:n]
    loud = L.max(0)[:n] > np.percentile(L.max(0), 99) - 30
    return fl / (np.percentile(fl[loud], 95) + 1e-9)


def onset_candidates(F):
    """在 10 毫秒帧上计算“嗓音响起”的新颖度曲线，取其峰值作候选。

    四个分量各对应一种字与字的交界：
      dv：浊音概率在 30 毫秒内的上升——清辅音（擦音、塞音）之后元音响起；
      de：中低频能量比此前 50 毫秒最低点的上升（每 12 dB 记 1）——停顿或鼻音、边音之后元音响起；
      dp：前后各 50 毫秒的音高中位数相差超过 0.7 个半音——连唱时靠换音区分前后两个字；
      ds：梅尔频谱变化量 × 0.4——连唱时共振峰的跳变，也是低通处理过的桥段人声里最可靠的线索。
    新颖度取四者最大值；每个候选记下哪一个分量占主导，作为修正方法的标注。
    候选的精确时刻取新颖度峰值之前、首次达到峰高一半的时刻（线性插值），即上升沿的中点。
    用全曲的强候选检验：这样取得的时刻相对十六分音符网格的离散程度最小（中位绝对偏差约 4.5 毫秒），
    比取峰值（约 5 毫秒）或取浊音概率越过 0.5 的时刻（约 12 毫秒）都稳定。
    """
    vp, f0, lm, hf = F["vprob"], F["f0"], F["lm"], F["hf"]
    n = len(vp)
    voiced = (vp > 0.5) & ~np.isnan(f0)
    midi = 12 * np.log2(np.where(np.isnan(f0), 440.0, f0) / 440.0) + 69

    def lagmin(x, k0, k1):
        out = np.full(n, np.inf)
        for k in range(k0, k1 + 1):
            out[k:] = np.minimum(out[k:], x[:-k])
        return out

    dv = np.clip(vp - lagmin(vp, 1, 3), 0, None)
    dv[~np.isfinite(dv)] = 0
    de = np.clip((lm - lagmin(lm, 1, 5)) / 12.0, 0, None)
    de[~np.isfinite(de)] = 0
    pre = np.full(n, np.nan)
    post = np.full(n, np.nan)
    for k in range(5, n - 5):
        a, b = voiced[k - 5:k], voiced[k:k + 5]
        if a.sum() >= 3 and b.sum() >= 3:
            pre[k] = np.median(midi[k - 5:k][a])
            post[k] = np.median(midi[k:k + 5][b])
    dp = np.nan_to_num(np.clip((np.abs(post - pre) - 0.7) / 2.0, 0, 1))
    ds = np.clip(F["mf"] * MF_WEIGHT, 0, 2.5)
    comp = np.vstack([dv, de, dp, ds])
    N = uniform_filter1d(comp.max(0), 3)
    pk, pr = find_peaks(N, height=0.12, distance=6)
    cands = []
    for p in pk:
        h = N[p]
        i = p
        while i > 0 and N[i - 1] >= 0.5 * h and p - i < 8:
            i -= 1
        # 在 i-1 与 i 之间对半高点线性插值
        if i > 0 and N[i] != N[i - 1]:
            frac = (0.5 * h - N[i - 1]) / (N[i] - N[i - 1])
            t = (i - 1 + np.clip(frac, 0, 1)) * FH
        else:
            t = i * FH
        # 半高点通常在峰值前 20–35 毫秒；上升特别缓慢时（多见于句首的擦音，噪声本身也抬高了中低频
        # 能量），半高点会落进辅音里，此时改取峰值前 35 毫秒
        t = max(t, p * FH - 0.035)
        kind = ["voicing", "energy", "pitch", "spectral"][int(np.argmax(comp[:, max(0, p - 1):p + 2].max(1)))]
        a, b = max(0, p - 10), p
        # 响度太低的“上升”不是唱出来的元音（多为换气声或混响里的起伏）：起音后 80 毫秒内的中低频
        # 电平比前后 1.5 秒内的最高电平低 15 dB 以上的候选舍去
        k = int(t / FH)
        local_ref = lm[max(0, k - 150):k + 150].max()
        if lm[k:k + 8].max() < local_ref - 15:
            continue
        # 候选之前 30–150 毫秒内全频带的最低电平比局部最高电平低多少（dB）：数值大说明前面是一段
        # 停顿。用全频带而不用中低频，是因为擦音处中低频能量很低，但并不是停顿
        tot = F["tot"]
        gap_db = float(tot[max(0, k - 150):k + 150].max() - tot[max(0, k - 15):max(1, k - 2)].min())
        cands.append({"t": float(t), "h": float(h), "kind": kind, "gap_db": gap_db,
                      "unvoiced_before": bool(vp[max(0, p - 10):max(1, p - 1)].min() < 0.4),
                      "hf_before": float(hf[max(0, p - 12):p + 1].max()),
                      "lm_dip": float(lm[p:p + 6].max() - lm[a:b + 1].min())})
    return cands, N


# 声母分类：清擦音和塞擦音、送气塞音的元音起点明显晚于辅音起点；浊辅音（m、n、l、r）和零声母
# 的字没有清辅音段，元音几乎紧接着响起。
SIB = {"s", "sh", "x", "c", "ch", "q", "z", "zh", "j"}
FRIC = {"f", "h"}
ASP = {"p", "t", "k"}
STOP = {"b", "d", "g"}
SON = {"m", "n", "l", "r"}
CLASS_MU = {"sib": 0.07, "fric": 0.06, "asp": 0.06, "stop": 0.03, "son": 0.02, "zero": 0.0}


def initial_class(ini):
    if ini in SIB:
        return "sib"
    if ini in FRIC:
        return "fric"
    if ini in ASP:
        return "asp"
    if ini in STOP:
        return "stop"
    if ini in SON:
        return "son"
    return "zero"


# ======================================================================
# 四、把字分配给候选时刻（动态规划）
# ======================================================================
def grid_points(t0, P, a, b):
    q = P / 4
    k0, k1 = int(np.ceil((a - t0) / q)), int(np.floor((b - t0) / q))
    return [t0 + k * q for k in range(k0, k1 + 1)]


def consonant_evidence(cls, d):
    """候选之前的声学特征与这个字的声母是否相符，返回加减分。

    清擦音、塞擦音（s、sh、x、c、ch、q、z、zh、j）在元音之前必有一段高频噪声，所以候选前 120 毫秒内
    高频占比超过 0.5 加分，在 0.25–0.5 之间少加，没有噪声则扣分；f、h 和送气塞音 p、t、k 的噪声较弱，
    只要求前面有清音段或一定的高频噪声；不送气塞音 b、d、g 只有很短的闭塞，前面有能量低谷即可。
    反过来，浊辅音（m、n、l、r）和零声母的字前面不应出现强烈的擦音噪声，出现了说明这个候选更可能
    属于一个以擦音开头的字。
    """
    hf, unv = d["hf_before"], d["unvoiced_before"]
    if cls == "sib":
        return 0.6 if hf > 0.5 else (0.3 if hf > 0.25 else -0.6)
    if cls in ("fric", "asp"):
        return 0.4 if (unv or hf > 0.25) else -0.4
    if cls == "stop":
        return (0.2 if (unv or d["lm_dip"] > 6) else 0.0) - (0.2 if hf > 0.5 else 0.0)
    return -0.4 if hf > 0.5 else 0.0


def pause_evidence(phrase_start, d):
    """候选之前是否有停顿与这个字在乐句中的位置是否相符，返回加减分。

    歌词里的全角空格标出了乐句的分界，乐句（包括每行）的第一个字前面通常有停顿或换气；
    乐句中间的字与前一个字连着唱，前面不应出现完全的静音。前面有静音（低于局部最高电平 25 dB 以上）
    的候选给乐句首字加分，静音更深（30 dB 以上）时给乐句中间的字扣分。
    """
    if phrase_start:
        return 0.4 if d["gap_db"] > 25 else 0.0
    return -0.5 if d["gap_db"] > 30 else 0.0


def assign_all(chars, cands, t0, P, duration, calib):
    """把全曲的字按时间顺序分配给节点（声学候选 + 十六分音符格点），使总得分最大（动态规划）。

    全曲一起分配而不是逐行分配，是因为行尾的字和下一行的第一个字会争夺同一个候选：逐行分配时，
    上一行的末字可能占走下一行首字的元音起点。
    单个字 i 落在节点 j 的得分：
      声学证据：候选强度（上限 2），加上声母与候选前声学特征是否相符的加减分（见 consonant_evidence），
            以及候选前有无停顿与字在乐句中的位置是否相符的加减分（见 pause_evidence）；
      网格：候选离最近的十六分音符格点越近得分越高（最多 +0.6）；
      先验：与“原对齐起点 + 该类声母的典型辅音时长”的距离按高斯形式扣分（标准差 0.2 秒），
            对齐概率极低的字放宽到 0.25 秒，时长为零的字放宽到 0.35 秒并允许离原起点更远；
      纯格点节点没有声学证据，得分为 0，只在附近没有可用候选时被选中（即推断值）。
    同一行相邻两字之间被跳过的强候选（强度 ≥ 0.7）要扣分，因为一个清楚的“嗓音响起”通常意味着
    一个字；由音高跳变产生的候选扣分减为三成，因为一字多音的拖腔也会产生这种候选。两行之间的
    候选（换气、和声、伴奏串音）跳过不扣分。
    约束：相邻两字起点至少相隔 MIN_GAP。
    """
    q = P / 4
    nodes = [{**c, "grid": False} for c in cands]
    nodes += [{"t": g + calib, "h": 0.0, "kind": "grid", "grid": True} for g in grid_points(t0, P, 0.0, duration)]
    nodes.sort(key=lambda d: d["t"])
    T = np.array([d["t"] for d in nodes])
    d16 = np.abs((T - calib - t0) / q - np.round((T - calib - t0) / q)) * q
    gridness = np.exp(-(d16 / 0.02) ** 2)
    pen = np.array([0.0 if d["grid"] or d["h"] < 0.7 else 0.5 * min(d["h"], 2.0) * (0.3 if d["kind"] == "pitch" else 1.0)
                    for d in nodes])
    cum = np.cumsum(pen)

    # 每个字的可选节点及其得分
    valid, E = [], []
    for ch in chars:
        mu = CLASS_MU[ch["cls"]]
        # 时长为零的字，对齐器把它压缩到了相邻字上，原起点基本不可信；概率极低的字只是识别把握小，
        # 时间通常仍由前后文对齐得出，所以只适度放宽
        if ch["zero_dur"]:
            sigma, early, late = 0.35, 0.8, 0.8
        elif ch["failed"]:
            sigma, early, late = 0.25, 0.45, 0.45
        else:
            sigma, early, late = 0.2, 0.35, 0.40
        js = np.where((T >= ch["start"] - early) & (T <= ch["start"] + late))[0]
        sc = []
        for j in js:
            d = nodes[j]
            dt = d["t"] - ch["start"]
            prior = -0.5 * min(((dt - mu) / sigma) ** 2, 9.0)
            ev = 0.0 if d["grid"] else (min(d["h"], 2.0) + 0.6 * gridness[j]
                                        + (consonant_evidence(ch["cls"], d) if ch["hf_ok"] else 0.0)
                                        + pause_evidence(ch["phrase_start"], d))
            sc.append(ev + prior)
        valid.append(js)
        E.append(np.array(sc))

    D = [E[0].copy()]
    B = [np.zeros(len(valid[0]), int)]
    for i in range(1, len(chars)):
        same_line = chars[i]["line"] == chars[i - 1]["line"]
        jp, Dp = valid[i - 1], D[-1]
        Di = np.full(len(valid[i]), -np.inf)
        Bi = np.zeros(len(valid[i]), int)
        for a, j in enumerate(valid[i]):
            ok = (T[j] - T[jp]) >= MIN_GAP
            if not ok.any():
                continue
            skip = (cum[j - 1] - cum[jp]) if same_line else 0.0
            val = np.where(ok, Dp - skip, -np.inf)
            k = int(np.argmax(val))
            if np.isfinite(val[k]):
                Di[a] = val[k] + E[i][a]
                Bi[a] = k
        if not np.isfinite(Di).any():
            # 窗口内没有满足间隔约束的节点（极少见）：放宽为只要求晚于上一个字
            for a, j in enumerate(valid[i]):
                ok = T[j] > T[jp]
                if ok.any():
                    val = np.where(ok, Dp, -np.inf)
                    k = int(np.argmax(val))
                    Di[a], Bi[a] = val[k] + E[i][a], k
        D.append(Di)
        B.append(Bi)
    a = int(np.argmax(D[-1]))
    path = [a]
    for i in range(len(chars) - 1, 0, -1):
        a = B[i][a]
        path.append(a)
    path = path[::-1]
    out = []
    for i, a in enumerate(path):
        j = valid[i][a]
        out.append({"t": float(T[j]), "node": nodes[j], "d16_ms": float(d16[j] * 1000), "score": float(E[i][a])})
    return out


def confidence_of(res, failed):
    """置信度（0–1）：由所选候选的强度、是否落在网格上、是否只是格点推断三方面给出。"""
    d = res["node"]
    if d["grid"]:
        return 0.2 if failed else 0.3
    h = d["h"]
    c = 0.95 if h >= 1.2 else (0.8 if h >= 0.6 else (0.6 if h >= 0.3 else 0.45))
    if res["d16_ms"] > 30:
        c -= 0.2
    if d["kind"] == "pitch":
        c -= 0.1
    return round(float(np.clip(c, 0.05, 1.0)), 2)


def voicing_offset(F, t, t_max):
    """乐句末字的结束时刻：从起点之后 80 毫秒开始，中低频能量比该字起音后 300 毫秒内的峰值低 15 dB
    以上、并持续 50 毫秒的起点。

    长音里浊音概率常在 0.3 上下波动（颤音、效果器），不能用来判断结束；能量的骤降更可靠。
    """
    lm = F["lm"]
    k0 = int(t / FH)
    peak = lm[k0:k0 + 30].max()
    k = k0 + 8
    k1 = min(len(lm) - 5, int(t_max / FH))
    while k < k1:
        if lm[k:k + 5].max() < peak - 15:
            return k * FH
        k += 1
    return t_max


# ======================================================================
# 五、人工修正
# ======================================================================
MANUAL_TEMPLATE = {
    "_说明": [
        "这里记录人工核对后的修正，运行 scripts/timing.py 时会覆盖自动结果。",
        "chars 中每一条修正一个字：line 是行号（1–40），char 是该字在行内的序号（从 1 开始，不计空格），",
        "ch 是这个字本身，用来核对行号和序号没有写错，对不上时这一条会被跳过并给出提示。",
        "可选字段：t 为起点的绝对时刻（秒）；shift_ms 为在自动结果上的平移（毫秒，正数表示推后），",
        "t 与 shift_ms 只写一个；end 为结束时刻（秒），用于长音；note 为备注，不参与计算。",
        "lines 中每一条修正一行的结束时刻：line 为行号，end 为结束时刻（秒）。",
        "被人工修正的字 confidence 记为 1，method 记为 manual，inferred 记为 false。",
        "格式示例见 _示例，_示例 本身不会生效。"
    ],
    "_示例": {
        "chars": [
            {"line": 36, "char": 9, "ch": "吹", "t": 177.470, "note": "按听感校正"},
            {"line": 3, "char": 3, "ch": "频", "shift_ms": -20},
            {"line": 18, "char": 14, "ch": "满", "end": 90.40, "note": "长音结束时刻"}
        ],
        "lines": [{"line": 18, "end": 90.40}]
    },
    "chars": [],
    "lines": []
}


def load_manual():
    path = LYR / "manual_fixes.json"
    if not path.exists():
        path.write_text(json.dumps(MANUAL_TEMPLATE, ensure_ascii=False, indent=2), encoding="utf-8")
    return json.loads(path.read_text(encoding="utf-8"))


# ======================================================================
# 六、主流程
# ======================================================================
def pos_of(t, first_db, P, step=0.25):
    """把时刻换算成“第几小节第几拍”（拍数按 step 拍取整，默认十六分音符），以及偏差（毫秒）。"""
    b = (t - first_db) / P
    bq = np.round(b / step) * step
    bar = int(np.floor(bq / 4)) + 1
    beat = bq - (bar - 1) * 4 + 1
    off = (t - (first_db + bq * P)) * 1000
    return bar, round(float(beat), 2), round(float(off), 1)


def main():
    low_priority()
    DATA.mkdir(exist_ok=True)
    CHECK.mkdir(parents=True, exist_ok=True)
    mix = load_mono(AUDIO / "song.wav")
    drums_y = load_mono(AUDIO / "stems" / "drums.wav")
    vocals = load_mono(AUDIO / "stems" / "vocals.wav")
    duration = len(mix) / SR
    lines_src = json.loads((LYR / "lines.json").read_text(encoding="utf-8"))["lines"]
    manual = load_manual()

    # ---------- 1. 鼓点与节拍网格 ----------
    drums, drum_env, drum_ft = detect_drums(drums_y)
    fit = fit_grid(*drums["kick"])
    P, t0 = fit["period"], fit["t0"] % fit["period"]
    # t0 取在 [0, P) 内：第 0 拍
    rough_sections = [("前奏", 0, 27.5), ("主歌一", 27.5, 55.3), ("副歌一", 55.3, 89.9), ("间奏一", 89.9, 102.8),
                      ("主歌二", 102.8, 117.0), ("副歌二", 117.0, 151.5), ("间奏二", 151.5, 165.0),
                      ("桥段", 165.0, 178.2), ("尾段", 178.2, 192.4)]
    seg_rows, drift = tempo_check(fit, rough_sections)
    entries, any_entries = drum_entries(drums, duration)
    cut = cut_time(mix)
    phase, phase_info = downbeat_phase(t0, P, drums["kick"], drums["snare"], any_entries, duration)
    first_db = t0 + phase * P
    while first_db - P * 4 >= 0:
        first_db -= 4 * P
    # 鼓是在制作软件里按网格编排的，底鼓、军鼓的音头离十六分音符格点都在 2 毫秒左右；高频检测出的
    # “镲片”里有一部分离格点 20 毫秒以上，且大多紧挨着字的起点，是人声擦音串进鼓分轨的声音，舍去
    ht, hs = drums["hat"]
    hq = P / 4
    hoff = np.abs((ht - t0) / hq - np.round((ht - t0) / hq)) * hq
    n_hat_raw = len(ht)
    drums["hat"] = (ht[hoff <= 0.02], hs[hoff <= 0.02])
    print(f"镲片：检出 {n_hat_raw} 个，离网格 20 毫秒以上的 {n_hat_raw - len(drums['hat'][0])} 个视为人声串音舍去")
    beats = np.arange(t0, duration, P)
    bars = np.arange(first_db, duration, 4 * P)
    print(f"拍长 {P:.6f} 秒（±{fit['period_se'] * 1e6:.1f} 微秒），每分钟 {60 / P:.3f} 拍；第 0 拍 {t0:.4f} 秒；"
          f"首个小节首拍 {first_db:.4f} 秒；残差标准差 {fit['res_std'] * 1000:.2f} 毫秒（{fit['n_used']}/{fit['n_total']} 个底鼓）")
    print(f"残差随时间的趋势 {drift:+.3f} 毫秒/分钟；相位判断 {phase_info}")
    for r in seg_rows:
        print(f"  {r['segment']:4s} 拍长 {r['beat_period']:.5f}±{r['beat_period_se']:.5f}  每分钟 {r['bpm']:.2f} 拍  "
              f"残差均值 {r['mean_residual_ms']:+.2f} 毫秒  n={r['n']}")

    def bar_time(k):  # 第 k 小节首拍（k 从 1 开始）
        return first_db + (k - 1) * 4 * P

    # 段落按小节划分：每行歌词占两小节，各段的小节数由歌词行数推出（见说明文档）
    sec_bars = [("intro", "前奏", 1, 16), ("verse1", "主歌一", 17, 32), ("chorus1", "副歌一", 33, 52),
                ("interlude1", "间奏一", 53, 60), ("verse2", "主歌二", 61, 68), ("chorus2", "副歌二", 69, 88),
                ("interlude2", "间奏二", 89, 96), ("bridge", "桥段", 97, 104), ("outro", "尾段", 105, 112)]
    sections = []
    for key, name, b0, b1 in sec_bars:
        sections.append({"name": key, "label": name, "start": round(0.0 if b0 == 1 else bar_time(b0), 4),
                         "end": round(bar_time(b1 + 1), 4), "first_bar": b0, "last_bar": b1})
    sections.append({"name": "ending", "label": "结尾（寂静）", "start": round(bar_time(113), 4),
                     "end": round(duration, 4), "first_bar": 113, "last_bar": None})

    # ---------- 2. 字的起点 ----------
    F = vocal_features(vocals)
    cands, novelty = onset_candidates(F)
    q = P / 4
    # 校准：强候选相对十六分音符格点的中位偏差，用于把纯格点推断值放到与实测值一致的位置
    ct = np.array([c["t"] for c in cands if c["h"] >= 1.0])
    off = ((ct - t0) / q - np.round((ct - t0) / q)) * q
    calib = float(np.median(off[np.abs(off) < 0.04]))
    print(f"强候选相对网格的中位偏差 {calib * 1000:+.1f} 毫秒")

    out_lines, flat = [], []
    for li, L in enumerate(lines_src):
        text_nospace = L["text"].replace("　", "")
        # 声母按整行文字取，多音字（如“重播”的“重”）由上下文决定读音
        inis = lazy_pinyin(text_nospace, style=Style.INITIALS, strict=True)
        pys = lazy_pinyin(text_nospace, style=Style.NORMAL)
        # 桥段的人声经过低通处理（4 kHz 以上几乎没有能量），擦音噪声和清音段都无从判断，
        # 这几行不使用声母证据：一行内高频占比的第 97 百分位低于 0.15 即视为低通
        a, b = int(max(0, L["start"] - 0.3) / FH), int(L["end"] / FH)
        hf_ok = bool(np.percentile(F["hf"][a:b], 97) >= 0.15)
        chars = []
        for c, ini, py in zip(L["chars"], inis, pys):
            # 对齐失败：起止相同（时长为零）或置信概率极低
            zero_dur = c["end"] - c["start"] < 0.03
            failed = zero_dur or (c["prob"] < 0.01)
            chars.append({**c, "ini": ini, "py": py, "cls": initial_class(ini), "failed": failed, "line": li,
                          "zero_dur": zero_dur,
                          "hf_ok": hf_ok, "phrase_start": (not chars) or chars[-1]["phrase"] != c["phrase"]})
        out_lines.append({"n": li + 1, "text": L["text"], "stanza": L["stanza"], "chars": chars})
        flat += chars
    res = assign_all(flat, cands, t0, P, duration, calib)
    for c, r in zip(flat, res):
        c["t"] = r["t"]
        c["method"] = r["node"]["kind"]
        c["confidence"] = confidence_of(r, c["failed"])
        c["inferred"] = bool(c["failed"])
        c["strength"] = r["node"]["h"]

    # ---------- 3. 人工修正 ----------
    applied = []
    for fx in manual.get("chars", []):
        try:
            L = out_lines[fx["line"] - 1]
            c = L["chars"][fx["char"] - 1]
        except (IndexError, KeyError, TypeError):
            print(f"人工修正无法定位，已跳过：{fx}")
            continue
        if fx.get("ch") and fx["ch"] != c["ch"]:
            print(f"人工修正的字对不上（第 {fx['line']} 行第 {fx['char']} 字是“{c['ch']}”），已跳过：{fx}")
            continue
        if "t" in fx:
            c["t"] = float(fx["t"])
        elif "shift_ms" in fx:
            c["t"] += float(fx["shift_ms"]) / 1000
        if "end" in fx:
            c["end_manual"] = float(fx["end"])
        if "t" in fx or "shift_ms" in fx:
            c["method"], c["confidence"], c["inferred"] = "manual", 1.0, False
        applied.append(fx)
    line_end_fix = {fx["line"]: float(fx["end"]) for fx in manual.get("lines", []) if "line" in fx and "end" in fx}

    # ---------- 4. 结束时刻、乐句、汇总 ----------
    all_t = []
    for li, L in enumerate(out_lines):
        cs = L["chars"]
        next_line_t = out_lines[li + 1]["chars"][0]["t"] if li + 1 < len(out_lines) else min(duration, (cut or duration))
        for k, c in enumerate(cs):
            last_in_phrase = (k == len(cs) - 1) or (cs[k + 1]["phrase"] != c["phrase"])
            if "end_manual" in c:
                c["end"] = c["end_manual"]
            elif not last_in_phrase:
                c["end"] = cs[k + 1]["t"]
            else:
                limit = cs[k + 1]["t"] - 0.02 if k + 1 < len(cs) else next_line_t - 0.02
                c["end"] = voicing_offset(F, c["t"], min(limit, c["t"] + 3.0))
            all_t.append(c["t"])
        if L["n"] in line_end_fix:
            cs[-1]["end"] = line_end_fix[L["n"]]
    order_bad = [i for i in range(1, len(all_t)) if all_t[i] <= all_t[i - 1]]
    if order_bad:
        print(f"注意：有 {len(order_bad)} 处字的起点不是递增的，请检查人工修正。")

    json_lines = []
    for L in out_lines:
        cs = L["chars"]
        phrases = []
        for p in sorted({c["phrase"] for c in cs}):
            pc = [c for c in cs if c["phrase"] == p]
            phrases.append({"start": round(pc[0]["t"], 3), "end": round(pc[-1]["end"], 3),
                            "text": "".join(c["ch"] for c in pc)})
        jc = []
        for c in cs:
            bar, beat, offm = pos_of(c["t"], first_db, P)
            tg = first_db + ((bar - 1) * 4 + beat - 1) * P
            jc.append({"ch": c["ch"], "t": round(c["t"], 3), "t_aligned": round(c["start"], 3), "end": round(c["end"], 3),
                       "shift_ms": round((c["t"] - c["start"]) * 1000, 1), "confidence": c["confidence"],
                       "inferred": c["inferred"], "phrase": c["phrase"], "method": c["method"],
                       "pinyin": c["py"], "t_grid": round(tg, 3), "bar": bar, "beat": beat, "grid_offset_ms": offm})
        json_lines.append({"n": L["n"], "text": L["text"], "stanza": L["stanza"], "start": jc[0]["t"],
                           "end": round(cs[-1]["end"], 3), "phrases": phrases, "chars": jc})

    def drum_list(t, s):
        out = []
        for x, st in sorted(zip(t, s)):
            bar, beat, offm = pos_of(x, first_db, P)
            out.append({"t": round(float(x), 4), "strength": round(float(st), 3), "bar": bar, "beat": beat,
                        "offset_ms": offm})
        return out

    # 事件：drums_in 为鼓休止后恢复连续演奏；sparse_kick 为休止段落里每两小节一次的单独底鼓
    events = []
    for e in sorted(any_entries):
        bar, beat, offm = pos_of(e, first_db, P)
        events.append({"name": "drums_in" if e in entries else "sparse_kick", "t": round(e, 4), "bar": bar,
                       "beat": beat, "offset_ms": offm})
    if cut:
        bar, beat, offm = pos_of(cut, first_db, P)
        events.append({"name": "cut", "t": round(cut, 4), "bar": bar, "beat": beat, "offset_ms": offm})

    shifts = np.array([c["shift_ms"] for L in json_lines for c in L["chars"]])
    conf = np.array([c["confidence"] for L in json_lines for c in L["chars"]])
    out = {
        "tempo_bpm": round(60 / P, 4),
        "beat_period": round(P, 7),
        "bar_period": round(4 * P, 6),
        "first_beat": round(t0, 4),
        "first_downbeat": round(first_db, 4),
        "time_signature": "4/4",
        "duration": round(duration, 4),
        "beats": [round(float(b), 4) for b in beats],
        "bars": [round(float(b), 4) for b in bars],
        "tempo_check": {"beat_period_se": round(fit["period_se"], 8), "residual_std_ms": round(fit["res_std"] * 1000, 2),
                        "kicks_used": fit["n_used"], "kicks_total": fit["n_total"],
                        "residual_trend_ms_per_min": round(drift, 3), "segments": seg_rows,
                        "downbeat_phase": phase_info},
        "sections": sections,
        "events": events,
        "drums": {k: drum_list(*v) for k, v in drums.items()},
        "lines": json_lines,
        "lyrics_stats": {"chars": int(len(shifts)), "median_shift_ms": round(float(np.median(shifts)), 1),
                         "median_abs_shift_ms": round(float(np.median(np.abs(shifts))), 1),
                         "max_abs_shift_ms": round(float(np.abs(shifts).max()), 1),
                         "onset_calibration_ms": round(calib * 1000, 1),
                         "manual_fixes_applied": len(applied)},
    }
    (DATA / "timing.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"字起点修正量：中位数 {np.median(np.abs(shifts)):.0f} 毫秒，最大 {np.abs(shifts).max():.0f} 毫秒；"
          f"低置信（<0.5）{int((conf < 0.5).sum())} 个；推断 {sum(c['inferred'] for L in json_lines for c in L['chars'])} 个")

    make_check_audio(mix, vocals, out)
    make_plots(out, F, novelty, vocals, fit, drum_env, drum_ft)
    return out


# ======================================================================
# 七、校对材料
# ======================================================================
def click(freq, dur, decay, sr=SR):
    t = np.arange(int(dur * sr)) / sr
    return np.sin(2 * np.pi * freq * t) * np.exp(-t / decay)


def make_check_audio(mix, vocals, out):
    """左声道放原曲（或人声分轨），右声道放提示音：小节首拍是低沉的 800 Hz 短音，字的起点是清脆的
    2600 Hz 短音（推断的字用 1700 Hz，便于听出哪些是推断值）。"""
    n = len(mix)
    right = np.zeros(n)
    tock = click(800, 0.08, 0.025) * 0.55
    tick = click(2600, 0.04, 0.010) * 0.5
    tick_inf = click(1700, 0.05, 0.012) * 0.5
    for b in out["bars"]:
        i = int(b * SR)
        right[i:i + len(tock)] += tock[:max(0, min(len(tock), n - i))]
    for L in out["lines"]:
        for c in L["chars"]:
            i = int(c["t"] * SR)
            s = tick_inf if c["inferred"] else tick
            right[i:i + len(s)] += s[:max(0, min(len(s), n - i))]
    for name, left in (("check_mix_clicks", mix), ("check_vocals_clicks", vocals)):
        left = left / (np.abs(left).max() + 1e-9) * 0.8
        st = np.c_[left, np.clip(right, -0.95, 0.95)]
        wav = CHECK / f"{name}.wav"
        sf.write(wav, st, SR, subtype="PCM_16")
        if FFMPEG.exists():
            subprocess.run([str(FFMPEG), "-y", "-loglevel", "error", "-i", str(wav), "-c:a", "aac", "-b:a", "192k",
                            str(CHECK / f"{name}.m4a")], check=False)


def make_plots(out, F, novelty, vocals, fit, drum_env, drum_ft):
    P, first_db = out["beat_period"], out["first_downbeat"]
    t0 = out["first_beat"]

    # 图一：节拍网格与鼓点总览
    fig, axes = plt.subplots(3, 1, figsize=(26, 12), gridspec_kw={"height_ratios": [1.2, 2, 1.2]})
    ax = axes[0]
    ax.scatter(fit["x"], fit["res"] * 1000, s=6, c="tab:blue")
    ax.axhline(0, color="k", lw=0.6)
    for r in out["tempo_check"]["segments"]:
        ax.hlines(r["mean_residual_ms"], r["start"], r["end"], color="tab:red", lw=2)
        ax.text((r["start"] + r["end"]) / 2, 9, f"{r['segment']}\n{r['bpm']:.2f}", ha="center", fontsize=8)
    ax.set_ylim(-15, 15)
    ax.set_ylabel("底鼓相对网格的残差（毫秒）")
    ax.set_title(f"恒定速度检验：全曲拟合 每分钟 {out['tempo_bpm']:.3f} 拍，残差标准差 {out['tempo_check']['residual_std_ms']:.2f} 毫秒；"
                 f"红线为各段残差均值，文字为分段拟合速度")
    ax = axes[1]
    ft = drum_ft
    for i, (k, col) in enumerate((("low", "tab:blue"), ("mid", "tab:orange"), ("noise", "tab:green"), ("high", "tab:purple"))):
        e = drum_env[k]
        e = np.clip((e - np.percentile(e, 99.5)) / 40 + 1, 0, 1)
        step = 8
        ax.plot(ft[::step], e[::step] * 0.9 + i, color=col, lw=0.4)
    for i, (k, col) in enumerate((("kick", "tab:blue"), ("snare", "tab:orange"), ("hat", "tab:purple"))):
        ts = [d["t"] for d in out["drums"][k]]
        ss = [d["strength"] for d in out["drums"][k]]
        ax.vlines(ts, 4.2 + i * 0.6, 4.2 + i * 0.6 + np.array(ss) * 0.5, color=col, lw=0.6)
    ax.set_yticks([0.5, 1.5, 2.5, 3.5, 4.45, 5.05, 5.65])
    ax.set_yticklabels(["30–110 Hz", "150–350 Hz", "1–5 kHz", "7–16 kHz", "底鼓", "军鼓", "镲片"])
    for ax in axes[1:]:
        for s in out["sections"]:
            ax.axvspan(s["start"], s["end"], color="0.93" if s["name"] in ("verse1", "verse2", "bridge") else "white", zorder=0)
            ax.text(s["start"] + 0.3, ax.get_ylim()[1] if ax is axes[2] else 6.1, s["label"], fontsize=9, va="bottom")
        for b in out["bars"]:
            ax.axvline(b, color="0.8", lw=0.3, zorder=0)
        for e in out["events"]:
            if e["name"] != "sparse_kick":
                ax.axvline(e["t"], color="red", lw=1)
    ax = axes[2]
    tt = np.arange(len(F["vprob"])) * FH
    ax.plot(tt, uniform_filter1d(np.clip((F["lm"] - np.percentile(F["lm"], 99)) / 50 + 1, 0, 1), 5), color="tab:red", lw=0.4)
    for L in out["lines"]:
        ax.text(L["start"], 1.02, f"L{L['n']:02d}", fontsize=7)
        ax.vlines([c["t"] for c in L["chars"]], 0, 0.15, color="k", lw=0.5)
    ax.set_ylabel("人声中低频能量")
    for a in axes:
        a.set_xlim(0, out["duration"])
        a.set_xticks(np.arange(0, out["duration"], 5))
    axes[2].set_xlabel("时间（秒）；灰线为小节首拍，红线为鼓进入与结尾骤停")
    fig.tight_layout()
    fig.savefig(CHECK / "grid_overview.png", dpi=70)
    plt.close(fig)

    # 图二：修正量与网格偏差的分布
    ch = [c for L in out["lines"] for c in L["chars"]]
    sh = np.array([c["shift_ms"] for c in ch])
    q = P / 4
    ta = np.array([c["t_aligned"] for c in ch])
    tc = np.array([c["t"] for c in ch])
    oa = ((ta - t0) / q - np.round((ta - t0) / q)) * q * 1000
    oc = ((tc - t0) / q - np.round((tc - t0) / q)) * q * 1000
    fig, axes = plt.subplots(1, 2, figsize=(14, 4.5))
    axes[0].hist(sh, bins=np.arange(-400, 420, 20), color="tab:blue")
    axes[0].set_xlabel("修正量 = 修正后起点 − 原对齐起点（毫秒）")
    axes[0].set_title(f"中位数 {np.median(sh):+.0f}，绝对值中位数 {np.median(np.abs(sh)):.0f}，最大 {np.abs(sh).max():.0f}")
    axes[1].hist(oa, bins=np.arange(-55, 56, 5), alpha=0.5, label="原对齐起点")
    axes[1].hist(oc, bins=np.arange(-55, 56, 5), alpha=0.6, label="修正后起点")
    axes[1].set_xlabel("相对最近十六分音符格点的偏差（毫秒）")
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(CHECK / "shift_summary.png", dpi=80)
    plt.close(fig)

    # 图三：逐行校对图（每张四行）
    lines = out["lines"]
    for g in range(0, len(lines), 4):
        grp = lines[g:g + 4]
        fig, axes = plt.subplots(len(grp), 1, figsize=(26, 5.2 * len(grp)))
        for ax, L in zip(np.atleast_1d(axes), grp):
            a = min(L["start"], min(c["t_aligned"] for c in L["chars"])) - 0.45
            b = L["end"] + 0.3
            seg = vocals[int(a * SR):int(b * SR)]
            S = librosa.amplitude_to_db(np.abs(librosa.stft(seg, n_fft=1024, hop_length=128)) + 1e-9, ref=np.max)
            f = librosa.fft_frequencies(sr=SR, n_fft=1024)
            tt = a + np.arange(S.shape[1]) * 128 / SR
            keep = f < 8000
            ax.pcolormesh(tt, f[keep], S[keep], vmin=-70, vmax=0, cmap="magma", shading="auto")
            fr = np.arange(len(F["vprob"])) * FH
            m = (fr >= a) & (fr < b)
            ax.plot(fr[m], F["vprob"][m] * 1500 + 8300, color="lime", lw=1.0)
            ax.plot(fr[m], novelty[m].clip(0, 2.5) / 2.5 * 1500 + 8300, color="w", lw=0.8)
            ax.plot(fr[m], np.where(np.isnan(F["f0"][m]), np.nan, F["f0"][m] * 4), color="cyan", lw=1.2)
            k0, k1 = int(np.ceil((a - t0) / q)), int((b - t0) / q)
            for k in range(k0, k1 + 1):
                x = t0 + k * q
                is_db = (k % 16) == int(round((first_db - t0) / q)) % 16
                ax.axvline(x, ymin=0, ymax=0.04 if k % 4 else (0.1 if not is_db else 0.16),
                           color="red" if is_db else "w", lw=1.5 if is_db else 0.7)
            for c in L["chars"]:
                ax.plot([c["t_aligned"]] * 2, [0, 3800], color="orange", lw=1.2, ls="--")
                col = "yellow" if c["method"] == "manual" else ("magenta" if c["inferred"] else "deepskyblue")
                ax.plot([c["t"]] * 2, [2000, 8000], color=col, lw=2.0)
                ax.text(c["t"] + 0.005, 7300, c["ch"], color="w", fontsize=13, fontweight="bold")
                ax.text(c["t"] + 0.005, 6700, f"{c['shift_ms']:+.0f}", color="w", fontsize=8)
                ax.text(c["t"] + 0.005, 6250, f"{c['confidence']:.2f}", color=("w" if c["confidence"] >= 0.5 else "red"), fontsize=8)
            ax.set_xlim(a, b)
            ax.set_ylim(0, 9900)
            ax.set_xticks(np.arange(np.ceil(a * 10) / 10, b, 0.1))
            ax.tick_params(axis="x", labelsize=7, rotation=90)
            ax.set_yticks([])
            ax.set_title(f"L{L['n']:02d}  {L['start']:.2f}–{L['end']:.2f} 秒   橙色虚线：原对齐起点；蓝色实线：修正后起点"
                         f"（品红为推断，黄色为人工）；数字为修正量（毫秒）与置信度；底部刻度为十六分音符网格，红色为小节首拍；"
                         f"青色为基频×4，绿色为浊音概率，白色为起音新颖度", fontsize=10, loc="left")
        fig.tight_layout()
        fig.savefig(CHECK / f"lyrics_L{grp[0]['n']:02d}-L{grp[-1]['n']:02d}.png", dpi=55)
        plt.close(fig)


if __name__ == "__main__":
    main()
