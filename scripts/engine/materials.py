"""材质注册表。

材质是一段 GLSL 片段，必须定义 `vec4 material(vec4 base)`：输入为预乘 alpha 的底色（纹理乘颜色），
返回预乘 alpha 的颜色。片段里可以声明自己的 uniform，并可使用这些现成的量：

  v_uv（纹理坐标，v 向下）、v_uv01（平面上 0–1 的坐标，v 向下）、v_local（平面局部坐标，世界单位，
  原点在平面中心）、v_wpos（世界坐标）、v_depth（到镜头的深度）、u_time、u_frame、u_seed、u_size、
  u_normal、u_eye、u_res、u_tex、u_texmode、u_vector、u_mask、u_hasmask、g_blur（景深模糊半径，像素）、
  g_mask（遮罩值），以及噪声函数 rnd / vnoise / gnoise / fbm。

遮罩和不透明度在 material() 之后统一乘上，材质不必处理。
"""
from . import shaders

_REGISTRY = {}


def register_material(name, glsl, defaults=None):
    """注册材质。defaults 为该材质 uniform 的默认值，平面的 uniforms 参数可以逐项覆盖。
    同名重复注册会替换旧材质（已编译的程序在下一次使用时重新编译）。"""
    if "material(" not in glsl:
        raise ValueError(f"材质 {name} 的 GLSL 片段里没有定义 vec4 material(vec4 base)")
    _REGISTRY[name] = {"glsl": glsl, "defaults": dict(defaults or {}), "version": _REGISTRY.get(name, {}).get("version", -1) + 1}


def get_material(name):
    if name not in _REGISTRY:
        raise KeyError(f"未注册的材质：{name}；已有 {sorted(_REGISTRY)}")
    return _REGISTRY[name]


def materials():
    return sorted(_REGISTRY)


register_material("flat", shaders.MAT_FLAT)
register_material("paper", shaders.MAT_PAPER, {
    "paper_amount": 1.0,
    "paper_scale": 0.04,
    "paper_tint": (0.94, 0.84, 0.64),
    "paper_stain": 0.35,
    "paper_ink": 0.5,
    "paper_edge": 0.8,
})
