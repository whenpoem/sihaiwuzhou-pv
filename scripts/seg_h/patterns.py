"""翻板场上拼出的四幅图案。

场地是 COLS × ROWS 块翻板（360 × 150），格距 1 个世界单位，第 0 行在远端（画面上方）。每块板记一个颜色序号：
0 为深色（未上漆的暗面），1 为褪色红，2 为美术字黄。四幅图案依次是：

L33  "千萬不要忘記階級鬥爭"，两行各五字、每字 64 块，红字、深色底：镜头起初贴近"記"字；
L34  "團結　緊張　嚴肅　活潑"，一行八字、每字 28 块，靠场地左侧（x −178 到 100），黄字、红底；
L35  "四海翻騰雲水怒　五洲震盪風雷激"，两行各七字、每字 44 块（与样张 D 相同），黄字、红底；
BAND 在 L35 上，一条深色的板带横穿全联中部（第一句下部、两句之间、第二句上部）。

字用思源黑体最粗一档画成，略微压扁，模仿团体操背景台的美术字；每块板取所在格子的墨量，过半即为字的颜色。
"""
import numpy as np
import skia

from common import look, cached

COLS, ROWS = 360, 150
DARK, RED_I, YELLOW_I = 0, 1, 2

# 全联（与样张 D 相同的字格）：每字 44 块，字距 6，行距 12，左右边距 8；两行居中
CH35, GAP35, LGAP35 = 44, 6, 12
TOP35 = (ROWS - (2 * CH35 + LGAP35)) // 2                       # 25
LEFT35 = (COLS - (7 * CH35 + 6 * GAP35)) // 2                   # 8
# 黑带：盖住第一句下部 32%、两句之间和第二句上部 32%（样张 D 的比例）
BAND_R0 = TOP35 + int(CH35 * 0.68)
BAND_R1 = TOP35 + CH35 + LGAP35 + int(CH35 * 0.32)

# L33 的大字：每字 64 块，字距 4，行距 10
CH33, GAP33, LGAP33 = 64, 5, 10
TOP33 = (ROWS - (2 * CH33 + LGAP33)) // 2
LEFT33 = (COLS - (5 * CH33 + 4 * GAP33)) // 2

# L34 的一行：每字 28 块，词内字距 3，词间距 14；放在场地偏左（中心 x ≈ −40），镜头从左边的"記"字升起时
# 一个个词依次进入画面
CH34, GAP34, WGAP34 = 28, 3, 14
W34 = 8 * CH34 + 4 * GAP34 + 3 * WGAP34
LEFT34 = 1
TOP34 = (ROWS - CH34) // 2


def _draw(cells, k=8, weight=850, scale_x=0.94):
    """cells：[(字, 左列, 顶行, 字格块数)] → (ROWS, COLS) 的墨量。每块板按 k×k 个采样点求平均。"""
    w, h = COLS * k, ROWS * k
    arr = np.zeros((h, w), np.uint8)
    s = skia.Surface.MakeRasterDirect(skia.ImageInfo.MakeA8(w, h), arr)
    c = s.getCanvas()
    paint = skia.Paint(AntiAlias=True, Color=skia.ColorWHITE)
    for ch, col, row, n in cells:
        f = look.font("sans", weight, n * k * 0.98, scale_x=scale_x)
        b = skia.Rect()
        f.measureText(ch, bounds=b)
        x = col * k + (n * k - b.width()) / 2 - b.left()
        y = row * k + (n * k - b.height()) / 2 - b.top()
        c.drawString(ch, x, y, f, paint)
    del c, s
    return arr.reshape(ROWS, k, COLS, k).mean((1, 3)) / 255.0


def ink33():
    def make():
        t = look.trad("千万不要忘记阶级斗争")
        cells = []
        for i, ch in enumerate(t):
            r, j = divmod(i, 5)
            cells.append((ch, LEFT33 + j * (CH33 + GAP33), TOP33 + r * (CH33 + LGAP33), CH33))
        return _draw(cells, weight=900, scale_x=0.92)
    return cached("ink33", make)


def ink34():
    def make():
        words = [look.trad(w) for w in ("团结", "紧张", "严肃", "活泼")]
        cells, x = [], LEFT34
        for w in words:
            cells.append((w[0], x, TOP34, CH34))
            cells.append((w[1], x + CH34 + GAP34, TOP34, CH34))
            x += 2 * CH34 + GAP34 + WGAP34
        return _draw(cells, weight=850, scale_x=0.94)
    return cached("ink34", make)


def ink35():
    def make():
        cells = []
        for i, line in enumerate([look.trad("四海翻腾云水怒"), look.trad("五洲震荡风雷激")]):
            for j, ch in enumerate(line):
                cells.append((ch, LEFT35 + j * (CH35 + GAP35), TOP35 + i * (CH35 + LGAP35), CH35))
        return _draw(cells, weight=800, scale_x=0.96)
    return cached("ink35", make)


def pattern(name):
    """颜色序号 (ROWS, COLS)，uint8。"""
    def make():
        if name == "L33":
            return np.where(ink33() > 0.45, RED_I, DARK).astype(np.uint8)
        if name == "L34":
            return np.where(ink34() > 0.45, YELLOW_I, RED_I).astype(np.uint8)
        if name == "L35":
            return np.where(ink35() > 0.45, YELLOW_I, RED_I).astype(np.uint8)
        if name == "BAND":
            p = pattern("L35").copy()
            p[BAND_R0:BAND_R1 + 1] = DARK
            return p
        raise KeyError(name)
    return cached("pattern:" + name, make)


if __name__ == "__main__":
    from PIL import Image
    from common import CACHE
    pal = np.array([[30, 26, 24], [181, 65, 46], [226, 178, 63]], np.uint8)
    rows = [pal[pattern(n)] for n in ("L33", "L34", "L35", "BAND")]
    sep = np.full((6, COLS, 3), 255, np.uint8)
    img = np.concatenate(sum([[r, sep] for r in rows], [])[:-1], 0)
    Image.fromarray(img).resize((COLS * 3, img.shape[0] * 3), Image.NEAREST).save(CACHE / "patterns_preview.png")
    print(CACHE / "patterns_preview.png", TOP35, LEFT35, BAND_R0, BAND_R1, TOP33, LEFT33, LEFT34, TOP34)
