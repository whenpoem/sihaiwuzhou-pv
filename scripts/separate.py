"""用 Demucs（htdemucs）把歌曲分离为人声、鼓、贝斯、其他四条音轨，输出到 audio/stems/。

在独立显卡（CUDA）上运行，进程设为低于正常优先级。
"""
import ctypes
import time
from pathlib import Path

import numpy as np
import soundfile as sf
import torch
from demucs.apply import apply_model
from demucs.audio import convert_audio
from demucs.pretrained import get_model

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "audio" / "song.wav"
OUT = ROOT / "audio" / "stems"


def main():
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    OUT.mkdir(parents=True, exist_ok=True)
    model = get_model("htdemucs")
    model.eval().cuda()

    data, sr = sf.read(SRC, dtype="float32", always_2d=True)
    wav = convert_audio(torch.from_numpy(data.T), sr, model.samplerate, model.audio_channels)

    # 按 Demucs 的惯例先做响度归一化，分离后再还原
    ref = wav.mean(0)
    mean, std = ref.mean(), ref.std()
    wav = (wav - mean) / std

    t0 = time.time()
    with torch.no_grad():
        sources = apply_model(model, wav[None].cuda(), device="cuda", shifts=2, split=True, overlap=0.25)[0]
    sources = sources * std + mean
    print(f"分离耗时 {time.time() - t0:.1f} 秒")

    for name, src in zip(model.sources, sources):
        arr = src.cpu().numpy().T
        sf.write(OUT / f"{name}.wav", arr, model.samplerate, subtype="FLOAT")  # 峰值可能超过 1，用浮点避免削波
        print(name, f"峰值 {np.abs(arr).max():.3f}")


if __name__ == "__main__":
    main()
