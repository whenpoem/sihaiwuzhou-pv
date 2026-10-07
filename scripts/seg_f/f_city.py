"""今天的城市：陆家嘴夜景照片（Larry Qian，CC0）按样张 C 的做法压成冷色单色调，作为整段的底图。

做法与样张 C 的风格化处理相同，只是作用在整张照片上（3840×2560），而不是样张 C 的取景：
先用保边滤波压平照片的细碎纹理，再按亮度映射成冷色双色调（暗部压到近黑，中间调偏蓝灰，亮部到白），暖黄的灯保留
一点暖白，霓虹的红紫粉一律褪成冷白；天空从照片上沿往下压暗，抹掉紫色的雾；原图最亮的点重新提亮并加两层光晕。
结果允许超过 1，表示灯的高光。

坐标：照片中心在世界原点，每世界单位 100 像素，所以整张照片宽 38.4、高 25.6；px_to_world 把原图像素换算成世界坐标。
照片本身是 2.5D 场景里最远的一层（z = CITY_Z），各句的物件放在它前面。
"""
import cv2
import numpy as np
from PIL import Image
from scipy.ndimage import gaussian_filter

from f_common import RENDERS, IMG, cached, disk_cached

PHOTO = IMG / "Shanghai_Lujiazui_night_skyline_2017_-_Flickr.jpg"
PW, PH = 3840, 2560
PPU = 100.0                                   # 每世界单位的像素数
SIZE = (PW / PPU, PH / PPU)
VERSION = 4

# 照片里几处要用到的位置（原图像素）
AURORA = np.float32([[2575, 1240], [2836, 1236], [2842, 1950], [2598, 1950]])   # 震旦大厦 LED 立面（样张 C 的四个角）
RIVER_Y = 2085                                # 近岸江面的上沿


def px_to_world(px, py, z=0.0):
    return np.array([px / PPU - SIZE[0] / 2, SIZE[1] / 2 - py / PPU])


def world_to_px(x, y):
    return np.array([(x + SIZE[0] / 2) * PPU, (SIZE[1] / 2 - y) * PPU])


# 照片里能认出的商业标识和 LED 广告（原图像素矩形 x0, y0, x1, y1）。画面里不出现真实企业的名称：这些字样先按周围的
# 楼面修补掉，风格化之后在原处补一块无字的灯光，天际线的明暗节奏不变。
SIGNS = [
    (1936, 1264, 2026, 1296),      # 楼顶英文字样与徽标（左侧高楼）
    (1906, 1551, 2049, 1594),      # 酒店字样
    (1926, 1414, 1954, 1444),      # 酒店徽标
    (2279, 1359, 2416, 1391),      # 楼顶英文字样（玻璃幕墙高楼）
    (1306, 1651, 1419, 1684),      # 穹顶楼上的中文字样
    (1391, 1803, 1549, 1834),      # 商场中文字样
    (1346, 1828, 1594, 1856),      # 商场英文字样
    (1698, 1486, 1802, 1529),      # 圆楼楼顶字样
    (1600, 1636, 1634, 1666),      # 楼面上的圆形徽标
    (2946, 1286, 3024, 1334),      # 楼顶中文字样（右侧方楼）
    (3151, 1284, 3206, 1329),      # 楼顶英文徽标
    (2976, 1992, 3094, 2024),      # 楼脚字样
    (2585, 1236, 2765, 1355),      # 圆柱楼楼顶的中文招牌
    (156, 1715, 224, 1734),        # 左侧楼顶红字
    (966, 1695, 1031, 1730),       # 右侧塔楼上的红字
    (156, 1903, 217, 1927),        # 左下小招牌
    (1040, 1953, 1081, 1971),      # 小招牌
    (2166, 1748, 2238, 1772),      # 尖顶小楼上的银行字样
    (524, 1931, 548, 1959),        # 左侧楼顶的字母徽标
]
SIGN_GLOW = [0, 1, 3, 6, 9, 10]    # 补上无字灯光的几处（楼顶的灯箱），其余直接修补成楼面
CITI_LED = (3060, 1378, 3236, 2000)   # 方楼立面上的 LED 字母广告：用同一立面左半边的窗带镜像覆盖


def _retouch(im):
    """抹掉商业标识与 LED 广告：字样用 Telea 修补；方楼立面的字母广告用同一立面左半边的窗带镜像覆盖；
    圆柱楼的 LED 立面整片压成暗色，留给烧屏残影的立面。"""
    u8 = (np.clip(im, 0, 1) * 255).astype(np.uint8)
    # 方楼立面
    x0, y0, x1, y1 = CITI_LED
    w = x1 - x0
    src = u8[y0:y1, x0 - w:x0][:, ::-1].astype(np.float32)
    feather = np.clip(np.minimum(np.arange(w) / 14.0, (w - 1 - np.arange(w)) / 6.0), 0, 1)[None, :, None]
    u8[y0:y1, x0:x1] = (src * feather + u8[y0:y1, x0:x1] * (1 - feather)).astype(np.uint8)
    # 圆柱楼的 LED 立面：按样张 C 的四边形压暗
    poly = AURORA.copy()
    poly[0, 1] -= 4
    poly[1, 1] -= 4
    m = np.zeros(u8.shape[:2], np.uint8)
    cv2.fillPoly(m, [poly.astype(np.int32)], 255)
    m = cv2.GaussianBlur(m.astype(np.float32) / 255, (0, 0), 3)[..., None]
    dark = cv2.GaussianBlur(u8, (0, 0), 25).astype(np.float32) * 0.25
    u8 = (u8 * (1 - m) + dark * m).astype(np.uint8)
    # 字样
    mask = np.zeros(u8.shape[:2], np.uint8)
    for x0, y0, x1, y1 in SIGNS:
        mask[y0 - 3:y1 + 3, x0 - 3:x1 + 3] = 255
    u8 = cv2.inpaint(u8, mask, 7, cv2.INPAINT_TELEA)
    return u8.astype(np.float32) / 255


def _sign_lights():
    """补在楼顶的无字灯光：一条横向的柔光，亮度与原来的灯箱相当，看起来是楼冠的泛光照明。"""
    out = np.zeros((PH, PW), np.float32)
    for i in SIGN_GLOW:
        x0, y0, x1, y1 = SIGNS[i]
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        w, h = (x1 - x0) * 0.42, max((y1 - y0) * 0.18, 4)
        cv2.ellipse(out, (int(cx), int(cy)), (int(w), int(h)), 0, 0, 360, 1.0, -1)
    return cv2.GaussianBlur(out, (0, 0), 5)


def _photo():
    return _retouch(np.asarray(Image.open(PHOTO).convert("RGB"), np.float32) / 255)


def _stylize(im):
    """压平纹理，映射成冷色双色调，天空压暗，灯重新提亮。逐式取自样张 C。"""
    flat = cv2.edgePreservingFilter((np.clip(im, 0, 1) * 255).astype(np.uint8), flags=1, sigma_s=30, sigma_r=0.3)
    flat = flat.astype(np.float32) / 255
    lum = flat @ np.array([0.3, 0.55, 0.15], np.float32)
    hsv = cv2.cvtColor(flat, cv2.COLOR_RGB2HSV)
    hue, sat = hsv[..., 0], hsv[..., 1]
    warmish = np.clip(1 - np.abs(hue - 40) / 25, 0, 1) * np.clip(sat * 1.5, 0, 1)
    t = np.clip((lum - 0.06) / 0.8, 0, 1) ** 1.35
    dark, mid, light = np.array([0.012, 0.016, 0.026]), np.array([0.20, 0.27, 0.40]), np.array([0.96, 0.98, 1.0])
    tt = t[..., None]
    col = np.where(tt < 0.5, dark + (mid - dark) * (tt / 0.5), mid + (light - mid) * ((tt - 0.5) / 0.5))
    col = col * (1 - 0.35 * warmish[..., None]) + col * np.array([1.12, 0.95, 0.72]) * 0.35 * warmish[..., None]
    # 天空：样张 C 的取景（原图 y 520–1960）里从画面上沿到 45% 处压暗 60%；整张照片沿用同样的原图高度，
    # 520 以上的空天再压暗一些
    yy = np.arange(PH, dtype=np.float32)[:, None, None]
    sky = np.clip(1 - (yy - 520) / 648, 0, 1) * 0.6 + np.clip((520 - yy) / 520, 0, 1) * 0.25
    col = col * (1 - sky)
    bright = np.clip((lum - 0.62) / 0.3, 0, 1)
    col += (bright[..., None] * 0.5 + gaussian_filter(bright, 3)[..., None] * 0.35
            + gaussian_filter(bright, 14)[..., None] * 0.25) * np.array([0.9, 0.95, 1.0])
    g = _sign_lights()
    col += (g[..., None] * 0.40 + gaussian_filter(g, 10)[..., None] * 0.35) * np.array([0.85, 0.92, 1.0])
    return col.astype(np.float32)


def styled():
    """风格化后的整张照片，(2560, 3840, 3) 半精度，数值可超过 1。"""
    return disk_cached(f"city_v{VERSION}", lambda: _stylize(_photo()).astype(np.float16))


def styled_tex():
    from engine import Tex
    return cached("city_tex", lambda: Tex(styled().astype(np.float32)))


def blurred_tex(sigma=10):
    """虚化的城市（景深之外）：按原图像素做高斯模糊，亮处的光斑因此散成圆形的光团。"""
    from engine import Tex

    def make():
        def calc():
            a = styled().astype(np.float32)
            small = cv2.resize(a, (PW // 2, PH // 2), interpolation=cv2.INTER_AREA)
            b = cv2.GaussianBlur(small, (0, 0), sigma / 2)
            hi = np.clip(small - 0.7, 0, None)                    # 灯的光斑：亮处单独再散开一层，像焦外的光团
            b += cv2.GaussianBlur(hi, (0, 0), sigma) * 0.6
            return b.astype(np.float16)
        return Tex(disk_cached(f"city_blur{sigma}_v{VERSION}", calc).astype(np.float32))
    return cached(f"city_blur{sigma}", make)


if __name__ == "__main__":
    import look
    a = styled().astype(np.float32)
    small = cv2.resize(a, (1920, 1280), interpolation=cv2.INTER_AREA)
    out = look.grade_present(small, bloom=0.3)
    Image.fromarray((np.clip(out, 0, 1) * 255).astype(np.uint8)).save(
        str(RENDERS / "city_styled.png"))
