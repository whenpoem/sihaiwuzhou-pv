"""L31–L32 借用副歌一后半（D 段，scripts/seg_d/）已经做好的拼图、立方体和帆船素材（只读导入，不改它的文件）。

D 段的模块都从它自己的 common.py 取工具函数，所以导入时临时把 scripts/seg_d 放到搜索路径最前面，导入完再把
sys.modules 里的 common 恢复原状；D 段模块里已经绑定的是它自己的那一份。

今天重演的是同一副拼图、同一个立方体：拼图块和盒子各面的贴图、拼图块的落点、"自卑"一组顶不进去的动作、
盒子的折法都直接用 D 段的函数，只把它们挪到本段的位置（平移，不缩放），灯换成冷白的点光，归入今天的画面组
（present，没有胶片颗粒）。帆另外做，见 f_sail.py。
"""
import importlib
import sys

import numpy as np

from f_common import SCRIPTS, RED, cached, disk_cached
import look

D_DIR = str(SCRIPTS / "seg_d")
_MODS = {}


def _load():
    """导入 D 段的模块。D 段的模块按裸名 common 导入它自己的工具模块：导入期间让 sys.modules 里的 common 指向
    D 段的那一份，导入完把原来的（若有）放回去，不影响同一进程里其他段的同名模块。"""
    if _MODS:
        return _MODS
    saved = sys.modules.pop("common", None)
    sys.path.insert(0, D_DIR)
    try:
        importlib.import_module("common")
        _MODS["mats"] = importlib.import_module("mats_d")
        _MODS["PZ"] = importlib.import_module("puzzle")
        _MODS["CB"] = importlib.import_module("cube")
        _MODS["SL"] = importlib.import_module("sail")
    finally:
        sys.path.remove(D_DIR)
        sys.modules.pop("common", None)
        if saved is not None:
            sys.modules["common"] = saved
    return _MODS


def PZ():
    return _load()["PZ"]


def CB():
    return _load()["CB"]


def SL():
    return _load()["SL"]


# 今天的拼图：与 D 段的 d_lit 相同的打光，另外把印刷面上的红字压成约 20% 的残影（红色只以残影出现）。
# 红字按"红通道明显高于绿、蓝"认出，向拼图的深蓝底色混合
from engine import register_material  # noqa: E402

register_material("f_lit", """
uniform vec3 lamp_pos;
uniform vec3 lamp_col;
uniform vec3 amb;
uniform float gloss;
uniform float lamp_fall;
uniform float red_keep;
vec4 material(vec4 base) {
    vec3 c0 = base.a > 0.0 ? base.rgb / base.a : vec3(0.0);
    float redness = clamp((c0.r - max(c0.g, c0.b) - 0.10) / 0.18, 0.0, 1.0);
    vec3 navy = vec3(0.105, 0.135, 0.205);
    c0 = mix(c0, mix(navy, c0, red_keep), redness);
    vec3 P = v_wpos;
    vec3 Ld = lamp_pos - P;
    float dl = length(Ld);
    Ld /= dl;
    float fall = 1.0 / (1.0 + dl * dl * lamp_fall);
    vec3 n = vec3(0.0, 0.0, 1.0);
    vec3 col = c0 * base.a * (amb + lamp_col * fall * max(dot(n, Ld), 0.0));
    vec3 V = normalize(u_eye - P);
    vec3 H = normalize(Ld + V);
    col += lamp_col * fall * pow(max(dot(n, H), 0.0), 30.0) * gloss * base.a;
    return vec4(col, base.a);
}
""", defaults={"lamp_pos": (0.0, 0.0, 3.0), "lamp_col": (1.0, 0.8, 0.6), "amb": (0.05, 0.05, 0.06), "gloss": 0.0,
               "lamp_fall": 0.3, "red_keep": 0.22})

COLD_LAMP = np.array([0.82, 0.92, 1.10]) * 2.6
COLD_AMB = np.array([0.050, 0.058, 0.075])


def _retarget(items, dx, dy, z, light_k=1.0):
    """把 D 段的元素平移 (dx, dy)、放到深度 z，灯换成冷白，归入 present 组。"""
    for it in items:
        c = np.asarray(it.center, float)
        it.center = np.array([c[0] + dx, c[1] + dy, z + c[2]])
        it.group = "present"
        if it.material == "d_lit":
            it.material = "f_lit"
        u = it.uniforms
        if "lamp_pos" in u:
            lp = np.asarray(u["lamp_pos"], float)
            u["lamp_pos"] = (lp[0] + dx, lp[1] + dy, lp[2] + z)
        if "f_o" in u:
            u["f_o"] = (u["f_o"][0] + dx, u["f_o"][1] + dy)
        if "lamp_col" in u:
            u["lamp_col"] = tuple(COLD_LAMP * light_k)
        if "amb" in u and tuple(u["amb"]) != (0.55, 0.55, 0.60):
            u["amb"] = tuple(COLD_AMB * light_k)
    return items


def puzzle_items(t_d, origin, z, light_k=1.0):
    """D 段时刻 t_d 的拼图（不含桌面），拼图中心挪到 origin。"""
    pz = PZ()
    items = pz.items(t_d, (0.0, 0.0, 0.0), 1.0, table_op=0.0, light_k=1.0)
    d = np.asarray(origin, float) - pz.CENTER
    return _retarget(items, d[0], d[1], z, light_k)


def _affine_material():
    """D 段盒子的 d_affine 材质加上同样的红字压淡（盒子内壁印着拼图的画面，其中有红色的旧字）。"""
    def make():
        glsl = CB().AFFINE_GLSL
        key = "    vec3 col = tx.rgb;"
        assert key in glsl
        fade = """    if (mono < 0.5) {
        vec3 c0 = tx.a > 0.0 ? tx.rgb / tx.a : vec3(0.0);
        float rd = clamp((c0.r - max(c0.g, c0.b) - 0.10) / 0.18, 0.0, 1.0);
        c0 = mix(c0, mix(vec3(0.105, 0.135, 0.205), c0, 0.22), rd);
        tx.rgb = c0 * tx.a;
    }
"""
        from engine import register_material as reg
        from engine.materials import get_material
        reg("f_affine", glsl.replace(key, fade + key), defaults=get_material("d_affine")["defaults"])
        return True
    return cached("f_affine_registered", make)


def board_tex():
    """盒子外侧的灰纸板：D 段的纸板背面（pz_back）纹理太细，在今天这一帧的近景里看起来是平涂的灰，这里另画一张：
    纸浆的大块斑驳、顺一个方向的纤维、细颗粒，以及几道浅浅的压痕。只铺一遍（不平铺），每面一张。"""
    def make():
        from engine import Tex
        from scipy import ndimage
        rng = np.random.default_rng(81)
        n = 1024
        mott = ndimage.gaussian_filter(rng.normal(0, 1, (n, n)), 26)
        mott = mott / (mott.std() + 1e-6) * 0.045
        fib = ndimage.gaussian_filter(rng.normal(0, 1, (n, n)), (0.7, 7.0))
        fib = fib / (fib.std() + 1e-6) * 0.028
        fine = ndimage.gaussian_filter(rng.normal(0, 1, (n, n)), 0.6) * 0.05
        yy, xx = np.mgrid[0:n, 0:n] / (n - 1)
        crease = sum(0.035 * np.exp(-((xx * np.cos(a) + yy * np.sin(a) - c) / 0.004) ** 2)
                     for a, c in ((0.3, 0.42), (1.9, 0.18), (2.6, -0.35)))
        edge = 1.0 - 0.10 * np.clip(1 - np.minimum.reduce([xx, yy, 1 - xx, 1 - yy]) / 0.04, 0, 1)
        v = (1 + mott + fib + fine - crease) * edge
        img = np.array([0.60, 0.585, 0.55])[None, None] * v[..., None]
        return Tex(np.clip(img, 0, 1).astype(np.float32))
    return cached("f_board_tex", make)


def box_items(th, el, phi, origin, z, inside=(), box_op=1.0, loose_op=1.0, light_k=1.0, amb=None):
    """D 段的盒子：四壁折起角度 th（dict 或数值），视角 el、phi，盒底中心在 origin。"""
    cb = CB()
    items, proj = cb.box_items(0.0, th, el, phi, np.asarray(origin, float), inside=list(inside), box_op=box_op,
                               table_op=0.0, loose_op=loose_op, z0=0.0)
    _affine_material()
    for it in items:
        if it in inside:
            continue
        it.group = "present"
        if it.material == "d_affine":
            it.material = "f_affine"
        elif it.material == "d_lit":
            it.material = "f_lit"
        u = it.uniforms
        if u.get("ftex") is cb.back_tex():
            if tuple(u.get("f_uv", (0, 0, 1, 1))) == (0, 0, 1.6, 1.6):          # 外侧的一整面：换成整张纸板
                u["ftex"] = board_tex()
                u["f_uv"] = (0.0, 0.0, 1.0, 1.0)
                u["gloss"] = 0.08
        if "lamp_col" in u:
            u["lamp_col"] = tuple(COLD_LAMP * light_k)
            u["amb"] = tuple(COLD_AMB * light_k if amb is None else amb)
    for it in items:
        c = np.asarray(it.center, float)
        it.center = np.array([c[0], c[1], z + c[2]])
    return items, proj
