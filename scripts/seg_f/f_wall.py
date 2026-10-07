"""L27 的玻璃幕墙：照片里那栋玻璃幕墙高楼的正立面，近看每一层的窗带都是一行行极小的字。

做法与副歌一的展览馆相同：照片每处的明暗决定字的亮度，所以远看仍是照片里那栋楼（亮着灯的窗、暗的楼冠），
近看是字。立面按楼层分成一条条窗带（层高 FLOOR 世界单位），每条窗带里排一行小字，字的内容是这首歌的全部歌词
（简体），按窗格的竖框断开；字的亮度取照片在该处的亮度，亮窗的字发白，暗窗的字只剩极淡的一点。窗带之间是
楼板的窄条和暗色的玻璃，玻璃上叠一层照片本身压暗后的颜色，竖框是一线冷光。立面的左右边缘按照片原有的圆角
渐隐，与照片衔接。

旧字"不管風吹浪打　勝似閒庭信步"是印在幕墙上的两列繁体淡红残影（另一张贴图，场景里控制浓淡），与圆柱楼立面上
"抓革命　促生產"的竖排两列同一种样子。
"""
import cv2
import numpy as np
import skia

import f_city as CT
from f_common import RENDERS, RED, cached, disk_cached
import look

FACE = (2262, 1340, 2456, 2062)          # 照片里的正立面（原图像素）
PPU = 360                                 # 贴图每世界单位的像素数
FLOOR = 0.125                             # 层高（世界单位）
MULLION = 0.193                           # 竖框间距
VERSION = 2


def geometry():
    x0, y0, x1, y1 = FACE
    a, b = CT.px_to_world(x0, y0), CT.px_to_world(x1, y1)
    return ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2), (b[0] - a[0], a[1] - b[1])


def _make():
    x0, y0, x1, y1 = FACE
    (cx, cy), (W, H) = geometry()
    tw, th = int(round(W * PPU)), int(round(H * PPU))
    photo = CT.styled().astype(np.float32)[y0:y1, x0:x1]
    base = cv2.resize(photo, (tw, th), interpolation=cv2.INTER_CUBIC)
    lum = cv2.GaussianBlur(base.mean(2), (0, 0), 3)
    # 一行行小字
    text = "".join(look.lyric(n) for n in range(1, 41)).replace("　", "")
    f = look.font("sans", 400, FLOOR * PPU * 0.56)
    adv = f.measureText("国") * 1.02
    s = skia.Surface(tw, th)
    c = s.getCanvas()
    c.clear(skia.Color4f(0, 0, 0, 1))
    paint = skia.Paint(Color=skia.Color4f(1, 1, 1, 1), AntiAlias=True)
    nfl = int(H / FLOOR) + 1
    k = 0
    mpx = MULLION * PPU
    for r in range(nfl):
        yb = (r + 0.78) * FLOOR * PPU
        x = 2.0 + (r * 37) % 11
        while x < tw - adv:
            col = int(x // mpx)
            if (x + adv) // mpx != col:              # 字不跨竖框：跳到下一格
                x = (col + 1) * mpx + 2
                continue
            c.drawString(text[k % len(text)], x, yb, f, paint)
            k += 1
            x += adv
    glyphs = s.makeImageSnapshot().toarray()[..., 0].astype(np.float32) / 255
    yy = (np.arange(th, dtype=np.float32) / PPU) % FLOOR / FLOOR
    band = ((yy > 0.12) & (yy < 0.92)).astype(np.float32)[:, None]        # 窗带；其余是楼板
    band = cv2.GaussianBlur(band * np.ones((1, tw), np.float32), (0, 0), 0.8)
    xx = (np.arange(tw, dtype=np.float32) / PPU) % MULLION / MULLION
    mull = np.exp(-((np.minimum(xx, 1 - xx)) * MULLION * PPU / 1.2) ** 2)[None, :]
    lit = np.clip((lum - 0.10) * 1.9, 0, 1.6)
    glass = base * 0.32 * band[..., None] + base * 0.12 * (1 - band[..., None])
    words = glyphs * band * (0.06 + lit)
    img = glass + words[..., None] * np.array([0.92, 0.96, 1.0])
    img += mull[..., None] * band[..., None] * np.array([0.10, 0.12, 0.15])
    img += (1 - band[..., None]) * np.array([0.03, 0.035, 0.045])
    # 楼冠（上部没有灯的一段）保留照片原样，只叠很淡的字
    crown = np.clip(((1515 - y0) / (y1 - y0) * th - np.arange(th)) / 30.0, 0, 1)[:, None, None]
    img = img * (1 - crown) + (base + words[..., None] * 0.15) * crown
    # 左右边缘：照片里的圆角，渐隐成照片本身
    u = np.arange(tw, dtype=np.float32) / tw
    a = np.clip(np.minimum(u, 1 - u) / 0.05, 0, 1)[None, :] * np.ones((th, 1), np.float32)
    return np.dstack([img, a]).astype(np.float16)


def wall_tex():
    from engine import Tex
    return cached("wall_tex", lambda: Tex(disk_cached(f"wall_v{VERSION}", _make).astype(np.float32)))


def ghost_tex():
    """幕墙上的旧字残影：两列繁体，右列"不管風吹浪打"、左列"勝似閒庭信步"，仿宋，笔画边缘略散开。"""
    def make():
        from engine import Tex
        (cx, cy), (W, H) = geometry()
        tw, th = 600, int(600 * H / W)
        f = look.font("fang", 400, tw * 0.40)
        items = []
        for col_i, word in enumerate([look.trad("不管风吹浪打"), look.trad("胜似闲庭信步")]):
            x = tw * (0.73 if col_i == 0 else 0.27)
            for k, ch in enumerate(word):
                b = skia.Rect()
                f.measureText(ch, bounds=b)
                y = th * 0.30 + k * tw * 0.42
                items.append((ch, f, x - b.width() / 2 - b.left(), y - b.top() - b.height() / 2, None))
        g = look.text_layer(items, tw, th)
        g = cv2.GaussianBlur(g, (0, 0), 2.0)
        return Tex(np.dstack([g[..., None] * RED * 1.3, g]).astype(np.float32), premultiplied=True)
    return cached("wall_ghost", make)


def items(opacity=1.0, ghost=0.2, z=0.006):
    from engine import Plane
    (cx, cy), (W, H) = geometry()
    out = [Plane(wall_tex(), center=(cx, cy, z), size=(W, H), opacity=opacity, group="present")]
    if ghost > 0:
        out.append(Plane(ghost_tex(), center=(cx, cy, z + 0.001), size=(W, H), opacity=ghost, group="present"))
    return out


if __name__ == "__main__":
    from PIL import Image
    a = disk_cached(f"wall_v{VERSION}", _make).astype(np.float32)
    img = np.clip(a[..., :3] / (1 + 0.15 * a[..., :3]), 0, 1)
    Image.fromarray((img[900:1700] * 255).astype(np.uint8)).save(str(RENDERS / "wall_crop.png"))
    small = cv2.resize(img, (img.shape[1] // 4, img.shape[0] // 4), interpolation=cv2.INTER_AREA)
    Image.fromarray((small * 255).astype(np.uint8)).save(str(RENDERS / "wall_small.png"))
