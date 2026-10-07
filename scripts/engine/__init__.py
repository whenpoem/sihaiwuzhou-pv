"""《四海五洲》PV 的 2.5D 渲染引擎。

    import sys; sys.path.insert(0, r"...\\creative\\scripts")
    from engine import Film, Cam, CamPath, Plane, TextPlane, Overlay, Particles, FrameSpec, timing

说明见同目录的 README.md。
"""
from . import timing
from .camera import Cam, CamPath, look_at, perspective
from .film import FILM_DURATION, Film, concat
from .gpu import Tex, low_priority
from .grade import DEFAULTS as GRADE_DEFAULTS
from .materials import materials, register_material
from .scene import FrameSpec, Overlay, Particles, Plane, TextPlane, rot_matrix
from .text import Atlas, bounds, contours, dot_atlas, flatten, glyph_atlas, glyph_path, layout, to_trad

__all__ = ["Film", "Cam", "CamPath", "Plane", "TextPlane", "Overlay", "Particles", "FrameSpec", "timing",
           "Tex", "register_material", "materials", "glyph_atlas", "dot_atlas", "Atlas", "glyph_path", "contours",
           "flatten", "bounds", "layout", "to_trad", "concat", "rot_matrix", "look_at", "perspective",
           "GRADE_DEFAULTS", "FILM_DURATION", "low_priority"]
