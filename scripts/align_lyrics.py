"""把校订后的歌词（lyrics/歌词.txt）与分离出的人声对齐，得到逐行、逐字的时间。

把人声分成四块分别对齐，每块只与所属的歌词行对齐，避免一行歌词跨过间奏（副歌一单独成块，
与主歌一合在一起对齐时有三行会挤到同一时刻）：
  0:27–1:02 第 0–9 行（主歌一、预副歌一），1:02–1:31 第 10–17 行（副歌一）；
  1:42–2:33 第 18–31 行（主歌二、预副歌二、副歌二）；
  2:44–3:13 第 32–39 行（桥段与尾段）。
歌词中的全角空格是乐句内的停顿，对齐时去掉，另存为每个字所属的短语编号。

输出 lyrics/lines.json：每行的文字、起止时间、短语划分，每个字的起止时间与对齐置信度。
"""
import ctypes
import json
from pathlib import Path

import librosa
import stable_whisper

ROOT = Path(__file__).resolve().parent.parent
LYR = ROOT / "lyrics"
SR = 16000
CHUNKS = [(26.8, 61.6, 0, 9), (61.5, 92.0, 10, 17), (101.8, 154.0, 18, 31), (163.8, 194.5, 32, 39)]


def fmt(t):
    m, s = divmod(t, 60)
    return f"{int(m):02d}:{s:05.2f}"


def main():
    ctypes.windll.kernel32.SetPriorityClass(ctypes.windll.kernel32.GetCurrentProcess(), 0x4000)
    raw = [l.strip() for l in (LYR / "歌词.txt").read_text(encoding="utf-8").splitlines()]
    stanza, stanzas, lines = 0, [], []
    for l in raw:
        if not l:
            stanza += 1 if lines and stanzas[-1] == stanza else 0
            continue
        lines.append(l)
        stanzas.append(stanza)
    assert len(lines) == 40, len(lines)

    audio, _ = librosa.load(ROOT / "audio" / "stems" / "vocals.wav", sr=SR, mono=True)
    model = stable_whisper.load_model("large-v3-turbo", device="cuda")

    out = []
    for a, b, i0, i1 in CHUNKS:
        clip = audio[int(a * SR):int(b * SR)]
        text = "\n".join(l.replace("　", "") for l in lines[i0:i1 + 1])
        res = model.align(clip, text, language="zh", original_split=True, verbose=None)
        assert len(res.segments) == i1 - i0 + 1, f"{fmt(a)} 段对齐后行数不符：{len(res.segments)}"
        for k, seg in enumerate(res.segments):
            line = lines[i0 + k]
            phrase_of = []
            for p, part in enumerate(line.split("　")):
                phrase_of += [p] * len(part)
            chars = []
            for w in seg.words:
                txt = w.word.strip()
                for m, ch in enumerate(txt):
                    s = a + w.start + (w.end - w.start) * m / len(txt)
                    e = a + w.start + (w.end - w.start) * (m + 1) / len(txt)
                    chars.append({"ch": ch, "start": round(s, 3), "end": round(e, 3),
                                  "prob": round(float(w.probability or 0), 3)})
            assert "".join(c["ch"] for c in chars) == line.replace("　", ""), line
            for c, p in zip(chars, phrase_of):
                c["phrase"] = p
            out.append({"index": i0 + k, "stanza": stanzas[i0 + k], "text": line,
                        "start": chars[0]["start"], "end": chars[-1]["end"], "chars": chars})

    (LYR / "lines.json").write_text(json.dumps({"lines": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    for l in out:
        low = "".join(c["ch"] for c in l["chars"] if c["prob"] < 0.2)
        print(f"{l['index']:2d} 段{l['stanza']} [{fmt(l['start'])}–{fmt(l['end'])}] {l['end'] - l['start']:5.2f}s "
              f"{l['text']}" + (f"   低置信：{low}" if low else ""))


if __name__ == "__main__":
    main()
