"""从 Wikimedia Commons 下载公开授权的图片（标准尺寸的缩略图，宽 1920 像素；Wikimedia 对非标准尺寸限流），并记录作者、授权与来源，
供视频简介署名。用法：python fetch_images.py "File:标题1" "File:标题2" ...，或 python fetch_images.py @标题清单.txt（每行一个标题）；加 --width 3840 下载更大的缩略图

图片存到 assets/images/，授权信息追加到 assets/images/credits.json；几段并行制作时，各段用 --credits 文件名
写进自己的授权表（如 --credits credits_seg_a.json，同样放在 assets/images/ 下），避免同时改写同一个文件，最后再合并。
"""
import json
import re
import sys
import time
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "assets" / "images"
API = "https://commons.wikimedia.org/w/api.php"
UA = {"User-Agent": "pv-research-script/0.1 (image licence survey)"}


def get(url, **kw):
    for k in range(5):
        r = requests.get(url, headers=UA, timeout=60, **kw)
        if r.status_code == 200:
            return r
        time.sleep((15 if r.status_code == 429 else 3) * (k + 1))
    r.raise_for_status()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    args = sys.argv[1:]
    cred_name = "credits.json"
    if "--credits" in args:                    # 各段自己的授权表
        i = args.index("--credits")
        cred_name = args[i + 1]
        args = args[:i] + args[i + 2:]
    cred_path = OUT / cred_name
    credits = json.loads(cred_path.read_text(encoding="utf-8")) if cred_path.exists() else {}
    titles = []
    width = 1920
    if "--width" in args:                      # 标准缩略图宽度之一：1920 或 3840
        i = args.index("--width")
        width = int(args[i + 1])
        args = args[:i] + args[i + 2:]
    for a in args:
        titles += [l.strip() for l in Path(a[1:]).read_text(encoding="utf-8").splitlines() if l.strip()] if a.startswith("@") else [a]
    for title in titles:
        j = get(API, params={"action": "query", "titles": title, "prop": "imageinfo", "iiurlwidth": width,
                             "iiprop": "url|size|extmetadata", "format": "json"}).json()
        page = next(iter(j["query"]["pages"].values()))
        if "imageinfo" not in page:
            print("找不到", title)
            continue
        ii = page["imageinfo"][0]
        md = ii.get("extmetadata", {})
        clean = lambda k: re.sub(r"<[^>]+>", "", md.get(k, {}).get("value", "")).strip()
        url = ii.get("thumburl") or ii["url"]
        ext = Path(url.split("?")[0]).suffix.lower() or ".jpg"
        name = re.sub(r"[^\w一-鿿\-]+", "_", title.removeprefix("File:").rsplit(".", 1)[0])[:60] + ext
        if not (OUT / name).exists():
            (OUT / name).write_bytes(get(url).content)
        credits[name] = {"title": title, "author": clean("Artist"), "license": clean("LicenseShortName"),
                         "license_url": clean("LicenseUrl"), "source": ii["descriptionurl"],
                         "date": clean("DateTimeOriginal")}
        print(f"{name}  {clean('LicenseShortName')}  {clean('Artist')[:40]}")
        cred_path.write_text(json.dumps(credits, ensure_ascii=False, indent=1), encoding="utf-8")
        time.sleep(2.5)


if __name__ == "__main__":
    main()
