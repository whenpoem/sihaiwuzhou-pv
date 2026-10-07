"""把各段的图片授权表合并成全片的总表。

各段下载图片时把来源写进 assets/images/credits_seg_*.json（fetch_images.py 的 --credits），总表
assets/images/credits.json 另有制作样张时下载的图片。这里按文件名合并：同一张图在几段里用到时，用途合并在一起，
其余字段以先出现的为准；最后另写一份按授权方式排好的文字版 assets/images/图片来源.txt，供发布时附在简介里。
文字版只列成片里实际用到的图片：各段授权表里的图片，以及文件名出现在成片脚本（scripts/seg_*、scripts/film）里的图片；
样张阶段下载、成片里没有用到的图片留在总表里，不进文字版。

    python credits.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IMG = ROOT / "assets" / "images"
SEGS = ["a1", "a2", "b", "c", "d", "e", "f", "g", "h"]
SEG_NAME = {"a1": "前奏", "a2": "主歌一", "b": "主歌一", "c": "副歌一", "d": "副歌一与间奏一", "e": "主歌二",
            "f": "副歌二", "g": "间奏二", "h": "桥段与尾段"}


def load(f):
    d = json.loads(f.read_text(encoding="utf-8"))
    if isinstance(d, list):
        return {it.get("file") or it["title"].removeprefix("File:"): it for it in d}
    return d


def used_names():
    """成片脚本的全部文字，用来判断一张图有没有被用到。"""
    code = []
    for d in list((ROOT / "scripts").glob("seg_*")) + [ROOT / "scripts" / "film"]:
        code += [f.read_text(encoding="utf-8", errors="ignore") for f in d.glob("*.py")]
    return "\n".join(code)


def author(v):
    a = (v.get("author") or "").strip().splitlines()
    a = a[0].strip() if a else ""
    return "不详" if not a or a.lower().startswith("unknown") else a


def main():
    total = load(IMG / "credits.json")
    for v in total.values():
        v.setdefault("used_in", [v["use"]] if v.get("use") else [])
    for seg in SEGS:
        f = IMG / f"credits_seg_{seg}.json"
        if not f.exists():
            continue
        for name, it in load(f).items():
            use = it.get("use_seg_" + seg) or it.get("used_in") or it.get("use") or SEG_NAME[seg]
            use = use if isinstance(use, str) else "，".join(use)
            if name not in total:
                total[name] = {k: v for k, v in it.items() if not k.startswith("use")}
                total[name]["used_in"] = []
            if use not in total[name]["used_in"]:
                total[name]["used_in"].append(use)
    for v in total.values():
        v.pop("use", None)
    (IMG / "credits.json").write_text(json.dumps(total, ensure_ascii=False, indent=1), encoding="utf-8")

    code = used_names()
    seg_names = set()
    for seg in SEGS:
        f = IMG / f"credits_seg_{seg}.json"
        if f.exists():
            seg_names |= set(load(f))
    used = {n: v for n, v in total.items() if n in seg_names or n in code or Path(n).stem in code}
    lines = ["《四海五洲》PV 使用的图片", ""]
    for lic in sorted({v.get("license", "") for v in used.values()}):
        lines.append(f"【{lic or '授权不详'}】")
        for name, v in sorted(used.items(), key=lambda kv: kv[1].get("title", kv[0])):
            if v.get("license", "") != lic:
                continue
            title = v.get("title", name).removeprefix("File:")
            lines.append(f"{title}　作者：{author(v)}　来源：{v.get('source', '')}")
            if v.get("changes"):
                lines.append(f"　　修改：{v['changes']}")
        lines.append("")
    (IMG / "图片来源.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"总表 {len(total)} 张，成片用到 {len(used)} 张")


if __name__ == "__main__":
    main()
