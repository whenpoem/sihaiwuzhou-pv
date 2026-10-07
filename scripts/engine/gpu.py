"""显卡上下文、进程优先级、渲染互斥锁和纹理管理。

渲染只允许在独立显卡上进行：创建上下文后检查 GL_RENDERER，不含 NVIDIA 就报错退出。
同一时刻只允许一个渲染进程占用显卡，用 Windows 命名互斥量实现：第二个进程会在这里等待，
前一个进程结束（包括异常退出）后系统自动释放互斥量。
"""
import ctypes
import os
import sys
import time
import weakref
from pathlib import Path

import moderngl
import numpy as np

BELOW_NORMAL = 0x4000          # Windows 的 BELOW_NORMAL_PRIORITY_CLASS
_MUTEX_NAME = "Local\\pv_sihaiwuzhou_render_lock"
_mutex_handle = None


def low_priority():
    """把本进程设为低于正常的优先级，避免和前台操作抢占处理器。"""
    try:
        k = ctypes.windll.kernel32
        k.SetPriorityClass(k.GetCurrentProcess(), BELOW_NORMAL)
    except Exception:
        pass


def acquire_render_lock():
    """取得全机唯一的渲染锁。已有别的渲染进程时在这里等待，保证同时最多一个渲染进程。"""
    global _mutex_handle
    if _mutex_handle is not None or os.environ.get("PV_NO_RENDER_LOCK"):
        return
    k = ctypes.windll.kernel32
    k.CreateMutexW.restype = ctypes.c_void_p
    k.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    h = k.CreateMutexW(None, False, _MUTEX_NAME)
    if not h:
        return
    WAIT_OBJECT_0, WAIT_ABANDONED, WAIT_TIMEOUT = 0, 0x80, 0x102
    r = k.WaitForSingleObject(h, 0)
    if r == WAIT_TIMEOUT:
        print("另一个渲染进程正在占用显卡，等待它结束……", flush=True)
        while True:
            r = k.WaitForSingleObject(h, 5000)
            if r != WAIT_TIMEOUT:
                break
    if r in (WAIT_OBJECT_0, WAIT_ABANDONED):
        _mutex_handle = h


def create_context():
    """创建独立的 OpenGL 4.3 上下文，并确认用的是 NVIDIA 独立显卡。"""
    ctx = moderngl.create_standalone_context(require=430)
    renderer = ctx.info["GL_RENDERER"]
    if "NVIDIA" not in renderer:
        ctx.release()
        raise RuntimeError(f"渲染必须使用 NVIDIA 独立显卡，当前上下文落在：{renderer}。"
                           "请在 Windows 图形设置里把 python.exe 设为高性能。")
    return ctx


# ---------------------------------------------------------------------------
# 纹理
# ---------------------------------------------------------------------------

class Tex:
    """场景代码使用的纹理句柄。持有 numpy 数据，第一次被画到时才上传显卡，之后复用。

    data 可以是：
      (H, W) 或 (H, W, 1)：覆盖率（0–1 或 0–255），画出时乘以颜色，适合字形、遮罩；
      (H, W, 3)：不透明 RGB；
      (H, W, 4)：RGBA，默认按直通 alpha 理解，上传前预乘；premultiplied=True 表示已经预乘。
    第 0 行是图像顶部。浮点数据里有大于 1 的值时按半精度浮点上传，保留高光（例如逆光的布）。
    数据在原处被修改后要调用 update()，否则显卡上仍是旧图。
    """

    def __init__(self, data, premultiplied=False, mipmap=True, repeat=False, nearest=False):
        self.mipmap, self.repeat, self.nearest = mipmap, repeat, nearest
        self.version = 0
        self._set(data, premultiplied)

    def _set(self, data, premultiplied):
        a = to_array(data)
        if a.ndim == 3 and a.shape[2] == 1:
            a = a[..., 0]
        if a.ndim == 2:
            self.mode = 1                       # 覆盖率
            if a.dtype != np.uint8:
                a = (np.clip(a, 0, 1) * 255 + 0.5).astype(np.uint8)
            self.hdr = False
        else:
            self.mode = 0                       # 预乘 RGBA
            if a.shape[2] == 3:
                alpha = np.ones(a.shape[:2] + (1,), np.float32) if a.dtype != np.uint8 else \
                    np.full(a.shape[:2] + (1,), 255, np.uint8)
                a = np.concatenate([a, alpha], 2)
                premultiplied = True
            if a.dtype == np.uint8:
                self.hdr = False
                if not premultiplied:
                    f = a.astype(np.float32) / 255
                    f[..., :3] *= f[..., 3:4]
                    a = (f * 255 + 0.5).astype(np.uint8)
            else:
                f = a.astype(np.float32)
                if not premultiplied:
                    f = f.copy()
                    f[..., :3] *= f[..., 3:4]
                self.hdr = bool(f[..., :3].max() > 1.0)
                a = f.astype(np.float16) if self.hdr else (np.clip(f, 0, 1) * 255 + 0.5).astype(np.uint8)
        self.data = np.ascontiguousarray(a)
        self.size = (self.data.shape[1], self.data.shape[0])

    def update(self, data, premultiplied=False):
        self._set(data, premultiplied)
        self.version += 1

    @property
    def seed(self):
        """由图像内容决定的 0–1 随机种子（材质用来错开纸纹等）。用内容而不用对象地址，
        分段渲染在不同进程里得到相同的值，拼接处纹理不跳。"""
        if getattr(self, "_seed", None) is None:
            import zlib
            sy = max(1, self.data.shape[0] // 64)
            sx = max(1, self.data.shape[1] // 64)
            self._seed = (zlib.crc32(np.ascontiguousarray(self.data[::sy, ::sx]).tobytes()) % 10007) / 10007.0
        return self._seed

    @property
    def nbytes(self):
        return self.data.nbytes * (4 / 3 if self.mipmap else 1)


def to_array(data):
    """把各种图像来源统一成 numpy 数组。"""
    if isinstance(data, np.ndarray):
        return data
    if isinstance(data, (str, Path)):
        from PIL import Image
        return np.asarray(Image.open(data).convert("RGBA"))
    try:
        from PIL import Image
        if isinstance(data, Image.Image):
            return np.asarray(data.convert("RGBA"))
    except ImportError:
        pass
    import skia
    if isinstance(data, skia.Surface):
        data = data.makeImageSnapshot()
    if isinstance(data, skia.Image):
        return data.toarray(colorType=skia.kRGBA_8888_ColorType, alphaType=skia.kUnpremul_AlphaType)
    raise TypeError(f"无法识别的纹理来源：{type(data)}")


def upload(ctx, data, components, dtype="f1", mipmap=True, repeat=False, nearest=False):
    """把 numpy 数组上传为显卡纹理（第 0 行放在纹理坐标 v=0 处，着色器里约定 v 向下）。"""
    h, w = data.shape[:2]
    tex = ctx.texture((w, h), components, np.ascontiguousarray(data).tobytes(), dtype=dtype, alignment=1)
    if mipmap:
        tex.build_mipmaps()
        tex.filter = (moderngl.LINEAR_MIPMAP_LINEAR, moderngl.LINEAR)
        tex.anisotropy = 16.0
    elif nearest:
        tex.filter = (moderngl.NEAREST, moderngl.NEAREST)
    else:
        tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
    tex.repeat_x = tex.repeat_y = repeat
    return tex


class TexCache:
    """把 Tex 或 numpy 数组映射到显卡纹理。

    以对象身份为键并持有弱引用：同一个数组每帧被引用多次也只上传一次；数组被回收后，
    对应的显卡纹理在下一次清理时释放。显存按最近使用的帧号做淘汰，超出预算时先释放最久没用的。
    """

    def __init__(self, ctx, budget_mb=2500):
        self.ctx = ctx
        self.budget = budget_mb * 1024 * 1024
        self.entries = {}          # id -> [weakref, version, gltex, mode, nbytes, last_frame, tex_obj_or_None]
        self.wrapped = {}          # id(ndarray) -> (weakref(ndarray), Tex)
        self.frame = 0
        self.total = 0

    def _wrap(self, obj):
        if isinstance(obj, Tex):
            return obj
        key = id(obj)
        hit = self.wrapped.get(key)
        if hit is not None and hit[0]() is obj:
            return hit[1]
        t = Tex(obj)
        try:
            ref = weakref.ref(obj)
        except TypeError:
            ref = (lambda o: (lambda: o))(obj)
        self.wrapped[key] = (ref, t)
        return t

    def get(self, obj):
        """返回 (显卡纹理, 模式)。模式 0：预乘 RGBA；1：单通道覆盖率。"""
        t = self._wrap(obj)
        key = id(t)
        e = self.entries.get(key)
        if e is not None and e[0]() is t and e[1] == t.version:
            e[5] = self.frame
            return e[2], e[3]
        if e is not None:
            self._release(key)
        comps = 1 if t.mode == 1 else 4
        dtype = "f2" if t.hdr else "f1"
        gl = upload(self.ctx, t.data, comps, dtype, t.mipmap, t.repeat, t.nearest)
        nb = int(t.nbytes)
        self.entries[key] = [weakref.ref(t), t.version, gl, t.mode, nb, self.frame, None]
        self.total += nb
        self._evict()
        return gl, t.mode

    def _release(self, key):
        e = self.entries.pop(key)
        e[2].release()
        self.total -= e[4]

    def sweep(self):
        """释放已被回收的数组对应的纹理。每帧调用一次。"""
        self.frame += 1
        for key in [k for k, e in self.entries.items() if e[0]() is None]:
            self._release(key)
        for key in [k for k, v in self.wrapped.items() if v[0]() is None]:
            del self.wrapped[key]

    def _evict(self):
        if self.total <= self.budget:
            return
        for key, e in sorted(self.entries.items(), key=lambda kv: kv[1][5]):
            if e[5] >= self.frame:
                break
            self._release(key)
            if self.total <= self.budget * 0.8:
                break


class LRU:
    """按字节计量的显卡资源缓存（文字栅格、遮罩栅格），超出预算时释放最久没用的项。"""

    def __init__(self, budget_mb=1500):
        self.budget = budget_mb * 1024 * 1024
        self.items = {}            # key -> [value, nbytes, last_frame, release_fn]
        self.total = 0
        self.frame = 0

    def get(self, key):
        e = self.items.get(key)
        if e is None:
            return None
        e[2] = self.frame
        return e[0]

    def put(self, key, value, nbytes, release):
        self.items[key] = [value, nbytes, self.frame, release]
        self.total += nbytes
        if self.total > self.budget:
            for k, e in sorted(self.items.items(), key=lambda kv: kv[1][2]):
                if e[2] >= self.frame:
                    break
                e[3](e[0])
                self.total -= e[1]
                del self.items[k]
                if self.total <= self.budget * 0.8:
                    break

    def keys(self):
        return self.items.keys()

    def tick(self):
        self.frame += 1


def timer():
    return time.perf_counter()
