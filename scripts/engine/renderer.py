"""渲染器：把一帧的描述画成图像。

一帧的流程：
  1. 按快门把一帧拆成若干子帧时刻，逐个调用 frame(t) 得到场景；
  2. 每个子帧里，past / present / raw 三组元素分别画进各自的高动态范围缓冲（超采样分辨率，
     半精度浮点，预乘 alpha）；每组内部按远近从后往前排序后混合；
  3. 子帧结果在显卡上累加平均，得到运动模糊；
  4. 各组缩小到输出尺寸后分别调色：past 走胶片调色，present 走今天的调色，raw 不调色；
     合成顺序为 past 在下、present 在上、raw 再上，最后叠加画面层（Overlay）；
  5. 输出 8 位 RGB，读回内存交给编码器。

排序规则：每个元素取一个代表点沿镜头视线方向的深度，深的先画。平面的代表点是平面矩形上离眼睛最近的点，
粒子组取位置的平均值。用视线方向的深度而不用直线距离，是因为 2.5D 场景里的层大多正对镜头：一张小纸片
在大墙面前面但偏在一侧时，它到眼睛的直线距离可能比墙更远，深度却更浅。代表点取最近点，镜头正从旁边
或洞里穿过的平面深度接近零，会最后画，这也符合它离镜头最近的事实。
同一平面上的元素（法线与平面位置都相同，例如纸和纸上的字）自动归为一组，按加入顺序连续绘制；
也可以用 stack 参数显式成组，用 bias 微调（世界单位，负值表示当作更近）。
"""
import math
from collections import OrderedDict

import moderngl
import numpy as np
import skia

from . import grade as G
from . import shaders as S
from .camera import Cam
from .gpu import LRU, Tex, TexCache, upload
from .materials import get_material
from .scene import Overlay, Particles, Plane, TextPlane

VECTOR_MIN_EM_PX = 700          # 投影后每 em 超过这么多像素才启用矢量模式，小字用栅格更省
MAX_EM_PX = 4096                # 栅格文字每 em 的像素上限
MAX_TEX = 16384                 # 单张文字纹理的边长上限


def _mat(m):
    return np.ascontiguousarray(np.asarray(m, dtype="f4").T).tobytes()


class _Target:
    """一个渲染目标：纹理 + 帧缓冲，可选多重采样。"""

    def __init__(self, ctx, size, dtype="f2", components=4, msaa=0):
        self.size = size
        self.tex = ctx.texture(size, components, dtype=dtype)
        self.tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
        self.tex.repeat_x = self.tex.repeat_y = False
        self.fbo = ctx.framebuffer(color_attachments=[self.tex])
        self.ms = None
        if msaa:
            self.rb = ctx.renderbuffer(size, components, samples=msaa, dtype=dtype)
            self.ms = ctx.framebuffer(color_attachments=[self.rb])

    @property
    def draw_fbo(self):
        return self.ms if self.ms is not None else self.fbo


class Renderer:
    def __init__(self, ctx, size=(1920, 1080), ss=2, nominal=(1920, 1080), msaa=0):
        self.ctx = ctx
        self.W, self.H = size
        self.ss = int(ss)
        self.RW, self.RH = self.W * self.ss, self.H * self.ss
        self.nominal = nominal
        self.k_ovl = self.RW / nominal[0]
        self.scale = self.H / 1080.0
        self.msaa = msaa
        self.tex = TexCache(ctx)
        self.text_cache = LRU(1500)
        self.text_tiers = {}            # 排版键 -> 已缓存的分档集合
        self.mask_cache = LRU(600)
        self.ovl_cache = LRU(400)
        self.vec_pool = []
        self.stats = {}

        quad = np.array([[-.5, -.5], [.5, -.5], [-.5, .5], [.5, .5]], "f4")
        self.quad = ctx.buffer(quad.tobytes())
        fsq = np.array([[-1, -1], [1, -1], [-1, 1], [1, 1]], "f4")
        self.fsq = ctx.buffer(fsq.tobytes())
        self._progs = {}
        self.p_part = ctx.program(vertex_shader=S.PART_VS, fragment_shader=S.PART_FS)
        self.va_part = ctx.vertex_array(self.p_part, [(self.quad, "2f", "in_corner")])
        self.p_ovl = ctx.program(vertex_shader=S.OVL_VS, fragment_shader=S.OVL_FS)
        self.va_ovl = ctx.vertex_array(self.p_ovl, [])
        self._post = {}
        for name, fs in (("accum", S.ACCUM_FS), ("down", S.DOWN_FS), ("hipass", S.HIPASS_FS), ("blur", S.BLUR_FS),
                         ("noise", S.NOISE_FS), ("comp", S.COMPOSITE_FS)):
            p = ctx.program(vertex_shader=S.FS_VS, fragment_shader=fs)
            self._post[name] = (p, ctx.vertex_array(p, [(self.fsq, "2f", "in_pos")]))
        self._part_bufs = {}
        self.white = upload(ctx, np.full((1, 1), 255, np.uint8), 1, mipmap=False)
        self.rt, self.acc, self.down = {}, {}, {}
        W, H = self.W, self.H
        self.halo = [_Target(ctx, (max(W // 4, 1), max(H // 4, 1))) for _ in range(2)]
        self.b6 = [_Target(ctx, (max(W // 2, 1), max(H // 2, 1))) for _ in range(2)]
        self.b30 = [_Target(ctx, (max(W // 4, 1), max(H // 4, 1))) for _ in range(2)]
        self.noise = [_Target(ctx, (W, H), "f4") for _ in range(3)]
        self.out = _Target(ctx, (W, H), "f1")
        self.blank = _Target(ctx, (4, 4))
        self.blank.fbo.clear(0, 0, 0, 0)

    # ------------------------------------------------------------------ 资源
    def _rt(self, g):
        if g not in self.rt:
            self.rt[g] = _Target(self.ctx, (self.RW, self.RH), "f2", 4, self.msaa)
        return self.rt[g]

    def _acc(self, g):
        if g not in self.acc:
            self.acc[g] = _Target(self.ctx, (self.RW, self.RH), "f4")
        return self.acc[g]

    def _down(self, g):
        if g not in self.down:
            self.down[g] = _Target(self.ctx, (self.W, self.H), "f2")
        return self.down[g]

    def _prog(self, material):
        mat = get_material(material)
        key = (material, mat["version"])
        hit = self._progs.get(material)
        if hit is None or hit[0] != key:
            fs = S.PLANE_FS_PRE + mat["glsl"] + "\n" + S.PLANE_FS_MAIN
            try:
                p = self.ctx.program(vertex_shader=S.PLANE_VS, fragment_shader=fs)
            except Exception as e:
                raise RuntimeError(f"材质 {material} 编译失败：\n{e}") from None
            va = self.ctx.vertex_array(p, [(self.quad, "2f", "in_pos")])
            hit = (key, p, va, mat["defaults"])
            self._progs[material] = hit
        return hit[1], hit[2], hit[3]

    _uni_cache = {}

    @classmethod
    def _members(cls, p):
        """程序的 uniform 名称到对象的字典。moderngl 的 `name in program` 每次都遍历全部成员，
        每帧上万次调用时开销明显，所以每个程序只遍历一次并缓存。"""
        m = cls._uni_cache.get(id(p))
        if m is None or m[0] is not p:
            m = (p, {name: p[name] for name in p})
            cls._uni_cache[id(p)] = m
        return m[1]

    @classmethod
    def _set(cls, p, name, value):
        u = cls._members(p).get(name)
        if u is not None:
            if isinstance(value, np.ndarray) and value.shape == (4, 4):
                u.write(_mat(value))
            else:
                u.value = value

    def _blend(self, mode):
        c = self.ctx
        if mode == "over":
            c.blend_func = (moderngl.ONE, moderngl.ONE_MINUS_SRC_ALPHA, moderngl.ONE, moderngl.ONE_MINUS_SRC_ALPHA)
        elif mode == "add":
            c.blend_func = (moderngl.ONE, moderngl.ONE, moderngl.ZERO, moderngl.ONE)
        else:  # multiply：底色乘以 lerp(1, 颜色, alpha)，alpha 不变
            c.blend_func = (moderngl.DST_COLOR, moderngl.ONE_MINUS_SRC_ALPHA, moderngl.ZERO, moderngl.ONE)

    # ------------------------------------------------------------------ 投影辅助
    def _project(self, vp, pts):
        """世界坐标点 → (渲染像素坐标 (n,2)，y 向下；clip w (n,))。"""
        P = np.c_[np.asarray(pts, float), np.ones(len(pts))] @ vp.T
        w = P[:, 3]
        ws = np.where(np.abs(w) < 1e-9, 1e-9, w)
        x = (P[:, 0] / ws * 0.5 + 0.5) * self.RW
        y = (0.5 - P[:, 1] / ws * 0.5) * self.RH
        return np.stack([x, y], 1), w

    def _em_px(self, vp, corners_world, size_em, near):
        """文字平面投影后每 em 的像素数。平面有一部分在镜头后面时返回无穷大。"""
        px, w = self._project(vp, corners_world)
        if np.any(w <= near * 1.01):
            return math.inf, False
        we, he = size_em
        e = [np.linalg.norm(px[1] - px[0]) / we, np.linalg.norm(px[2] - px[1]) / he,
             np.linalg.norm(px[3] - px[2]) / we, np.linalg.norm(px[0] - px[3]) / he]
        return max(e), True

    # ------------------------------------------------------------------ 排序
    @staticmethod
    def _sort_depth(it, eye, fwd):
        if isinstance(it, Particles):
            return float((it.sort_point() - eye) @ fwd)
        if isinstance(it, TextPlane):
            c, (w, h) = it.box_geometry()
        else:
            c, (w, h) = it.center, it.size
        R = it.R()
        loc = R.T @ (eye - c)
        q = np.array([min(max(loc[0], -w / 2), w / 2), min(max(loc[1], -h / 2), h / 2), 0.0])
        return float((c + R @ q - eye) @ fwd)

    def _sorted(self, items, cam):
        eye, fwd = cam.eye, cam.basis()[2]
        units = OrderedDict()
        planes = []                     # [(法线, 平面位置, 键)]，按容差判断是否共面
        for i, it in enumerate(items):
            if it.stack is not None:
                key = ("stack", it.stack)
            elif isinstance(it, Plane):
                n = it.normal()
                k = int(np.argmax(np.abs(n)))
                if n[k] < 0:
                    n = -n
                off = float(n @ (it.box_geometry()[0] if isinstance(it, TextPlane) else it.center))
                key = None
                for n2, off2, k2 in planes:
                    if np.abs(n - n2).max() < 1e-4 and abs(off - off2) < 1e-4 * max(1.0, abs(off)):
                        key = k2
                        break
                if key is None:
                    key = ("plane", i)
                    planes.append((n, off, key))
            else:
                key = ("solo", i)
            units.setdefault(key, []).append((i, it))
        order = []
        for key, members in units.items():
            d = min(self._sort_depth(it, eye, fwd) + it.bias for _, it in members)
            order.append((-round(d, 5), members[0][0], members))
        order.sort(key=lambda x: (x[0], x[1]))
        return [it for _, _, members in order for _, it in members]

    # ------------------------------------------------------------------ 绘制元素
    def _resolve_tex(self, tex):
        if tex is None:
            return self.white, 1
        return self.tex.get(tex)

    def _text_raster(self, lay, em_px):
        """取不低于 em_px 的最小已缓存分档；没有就按需要的分档栅格化。"""
        we, he = lay.tex_size_em
        cap = MAX_EM_PX
        while cap > 16 and max(we, he) * cap > MAX_TEX:
            cap //= 2
        need = 16
        while need < min(em_px, cap):
            need *= 2
        need = min(need, cap)
        tiers = self.text_tiers.setdefault(lay.key, set())
        for t in sorted(tiers):
            if t >= need:
                hit = self.text_cache.get((lay.key, t))
                if hit is not None:
                    return hit
                tiers.discard(t)
        arr, box = lay.raster(need)
        gl = upload(self.ctx, arr, 1)
        val = (gl, box)
        tiers.add(need)

        def rel(v, key=lay.key, tier=need):
            v[0].release()
            self.text_tiers.get(key, set()).discard(tier)
        self.text_cache.put((lay.key, need), val, int(arr.nbytes * 4 / 3), rel)
        return val

    def _vector_tex(self, it, lay, vp, k):
        """矢量模式：按当前镜头把字形轮廓逐点透视投影到渲染分辨率，再由 skia 填充。"""
        while len(self.vec_pool) <= k:
            arr = np.zeros((self.RH, self.RW), np.uint8)
            surf = skia.Surface.MakeRasterDirect(skia.ImageInfo.MakeA8(self.RW, self.RH), arr)
            gl = self.ctx.texture((self.RW, self.RH), 1, dtype="f1", alignment=1)
            gl.filter = (moderngl.NEAREST, moderngl.NEAREST)
            self.vec_pool.append((arr, surf, gl))
        arr, surf, gl = self.vec_pool[k]
        polys = lay.flat()
        allp = np.concatenate(polys, 0)
        world = np.array([it.em_to_world(x, y) for x, y in [(0, 0), (1, 0), (0, 1)]])
        # em → 世界是仿射的：用三个点确定，再整体乘以 vp
        o, ex, ey = world[0], world[1] - world[0], world[2] - world[0]
        A = np.array([[ex[0], ey[0], o[0]], [ex[1], ey[1], o[1]], [ex[2], ey[2], o[2]], [0, 0, 1]])
        Hc = vp @ A                           # em (x, y, 1) → clip (4)
        C = np.array([[self.RW / 2, 0, 0, self.RW / 2], [0, -self.RH / 2, 0, self.RH / 2], [0, 0, 0, 1]])
        Hm = C @ Hc                            # em → (px·w, py·w, w)
        P = np.c_[allp, np.ones(len(allp))] @ Hm.T
        xy = P[:, :2] / P[:, 2:3]
        canvas = surf.getCanvas()
        canvas.clear(skia.Color4f(0, 0, 0, 0))
        path = skia.Path()
        path.setFillType(skia.PathFillType.kWinding)
        i = 0
        for poly in polys:
            n = len(poly)
            seg = xy[i:i + n]
            path.addPoly([skia.Point(float(a), float(b)) for a, b in seg], True)
            i += n
        canvas.drawPath(path, skia.Paint(AntiAlias=True, Color=skia.ColorWHITE))
        gl.write(arr)
        return gl

    def _mask_tex(self, mask, it, vp):
        import skia as _sk
        if not isinstance(mask, _sk.Path):
            return self.tex.get(mask)[0]
        corners = it.corners()
        px, w = self._project(vp, corners)
        if np.any(w <= 0):
            span = 8192
        else:
            span = max(np.linalg.norm(px[1] - px[0]), np.linalg.norm(px[2] - px[1]), 1.0)
        size = it.size if not isinstance(it, TextPlane) else it.box_geometry()[1]
        aspect = size[0] / max(size[1], 1e-9)
        tier = 64
        while tier < min(span, 8192):
            tier *= 2
        mw, mh = (tier, max(8, int(round(tier / aspect)))) if aspect >= 1 else (max(8, int(round(tier * aspect))), tier)
        key = (bytes(mask.serialize()), mw, mh)
        hit = self.mask_cache.get(key)
        if hit is not None:
            return hit
        arr = np.full((mh, mw), 255, np.uint8)
        s = _sk.Surface.MakeRasterDirect(_sk.ImageInfo.MakeA8(mw, mh), arr)
        c = s.getCanvas()
        c.scale(mw, mh)
        c.drawPath(mask, _sk.Paint(AntiAlias=True, BlendMode=_sk.BlendMode.kClear))
        del c, s
        gl = upload(self.ctx, arr, 1)
        self.mask_cache.put(key, gl, int(arr.nbytes * 4 / 3), lambda g: g.release())
        return gl

    def _seed_of(self, it):
        """材质用的随机种子：优先取 uniforms["seed"]，否则由纹理内容或文字内容决定（跨进程稳定）。"""
        if "seed" in it.uniforms:
            return it.uniforms["seed"]
        if isinstance(it, TextPlane):
            import zlib
            return (zlib.crc32(it.text.encode("utf-8")) % 10007) / 10007.0
        if it.tex is None:
            return 0.37
        return self.tex._wrap(it.tex).seed

    def _visible(self, vp, corners):
        """视锥裁剪：四个角都在同一个裁剪面外侧时整块平面看不见，直接跳过，省掉 Python 端的开销。"""
        P = np.c_[np.asarray(corners, float), np.ones(4)] @ vp.T
        x, y, z, w = P[:, 0], P[:, 1], P[:, 2], P[:, 3]
        if np.all(x > w) or np.all(x < -w) or np.all(y > w) or np.all(y < -w) or np.all(z < -w) or np.all(z > w):
            return False
        return True

    def _draw_plane(self, it, cam, vp, view, t, frame, vec_k):
        if not self._visible(vp, it.corners()):
            return vec_k
        p, va, defaults = self._prog(it.material)
        unit = 3
        vector = 0
        if isinstance(it, TextPlane):
            lay = it.layout()
            box = lay.tex_box
            corners = [it.em_to_world(x, y) for x, y in ((box[0], box[3]), (box[2], box[3]), (box[2], box[1]), (box[0], box[1]))]
            em_px, in_front = self._em_px(vp, corners, lay.tex_size_em, cam.near)
            if it.vector and in_front and em_px > VECTOR_MIN_EM_PX:
                gl = self._vector_tex(it, lay, vp, vec_k)
                gl.use(2)
                self._set(p, "u_vec", 2)
                vector = 1
                vec_k += 1
                model, size = it.model_for(box)
                tex_gl, mode = self.white, 1
            else:
                tex_gl, box2 = self._text_raster(lay, em_px if math.isfinite(em_px) else 1e9)
                model, size = it.model_for(box2)
                mode = 1
        else:
            tex_gl, mode = self._resolve_tex(it.tex)
            model, size = it.model(), it.size
        tex_gl.use(0)
        self._set(p, "u_tex", 0)
        self._set(p, "u_texmode", mode)
        self._set(p, "u_vector", vector)
        if it.mask is not None:
            self._mask_tex(it.mask, it, vp).use(1)
            self._set(p, "u_mask", 1)
            self._set(p, "u_hasmask", 1)
        else:
            self._set(p, "u_hasmask", 0)
        self._set(p, "u_vp", vp)
        self._set(p, "u_view", view)
        self._set(p, "u_model", model)
        self._set(p, "u_size", tuple(map(float, size)))
        self._set(p, "u_uvrect", tuple(map(float, it.uv)))
        self._set(p, "u_color", tuple(map(float, it.color)))
        self._set(p, "u_opacity", float(it.opacity))
        self._set(p, "u_time", float(t))
        self._set(p, "u_frame", int(frame))
        self._set(p, "u_eye", tuple(map(float, cam.eye)))
        self._set(p, "u_normal", tuple(map(float, it.normal())))
        self._set(p, "u_res", (float(self.RW), float(self.RH)))
        self._set(p, "u_seed", float(self._seed_of(it)))
        focal = (self.RH / 2) / math.tan(math.radians(cam.fov) / 2)
        self._set(p, "u_dof_k", float(cam.dof * focal))
        self._set(p, "u_focus_inv", 1.0 / max(cam.focus_distance(), 1e-6))
        merged = dict(defaults)
        merged.update(it.uniforms)
        members = self._members(p)
        for name, val in merged.items():
            u = members.get(name)
            if name == "seed" or u is None:
                continue
            if isinstance(val, Tex) or (isinstance(val, np.ndarray) and val.ndim >= 2):
                self.tex.get(val)[0].use(unit)
                u.value = unit
                unit += 1
            else:
                u.value = tuple(map(float, val)) if isinstance(val, (tuple, list, np.ndarray)) else val
        self._blend(it.blend)
        va.render(moderngl.TRIANGLE_STRIP)
        return vec_k

    def _part_buf(self, name, nbytes):
        b = self._part_bufs.get(name)
        if b is None or b.size < nbytes:
            if b is not None:
                b.release()
            b = self.ctx.buffer(reserve=max(nbytes, 64), dynamic=True)
            self._part_bufs[name] = b
        return b

    def _draw_particles(self, pt, cam, vp):
        n = len(pt)
        if n == 0:
            return
        datas = [("pos", pt.pos), ("size", pt.size), ("rot", pt.rot), ("col", pt.color), ("uv", pt.uv)]
        if pt.back is not None:
            datas.append(("back", pt.back))
        for bi, (name, arr) in enumerate(datas):
            raw = np.ascontiguousarray(arr, np.float32).tobytes()
            b = self._part_buf(name, len(raw))
            b.write(raw)
            b.bind_to_storage_buffer({"pos": 0, "size": 1, "rot": 2, "col": 3, "uv": 4, "back": 5}[name])
        if pt.back is None:
            self._part_buf("back", 64).bind_to_storage_buffer(5)
        p = self.p_part
        if pt.sort:
            right, up, fwd = cam.basis()
            depth = (pt.pos - cam.eye.astype(np.float32)) @ fwd.astype(np.float32)
            order = np.argsort(-depth).astype(np.int32)          # 深度相同的粒子先后无关，用较快的快速排序
            b = self._part_buf("order", order.nbytes)
            b.write(order.tobytes())
            b.bind_to_storage_buffer(6)
        else:
            self._part_buf("order", 64).bind_to_storage_buffer(6)
        right, up, fwd = cam.basis()
        tex_gl, mode = self.tex.get(pt.atlas.tex)
        tex_gl.use(0)
        self._set(p, "u_atlas", 0)
        self._set(p, "u_texmode", mode)
        self._set(p, "u_vp", vp)
        self._set(p, "u_right", tuple(map(float, right)))
        self._set(p, "u_up", tuple(map(float, up)))
        self._set(p, "u_sorted", 1 if pt.sort else 0)
        self._set(p, "u_oriented", 1 if pt.oriented else 0)
        self._set(p, "u_hasback", 1 if pt.back is not None else 0)
        self._set(p, "u_opacity", float(pt.opacity))
        self._blend(pt.blend)
        self.va_part.render(moderngl.TRIANGLE_STRIP, instances=n)

    def _draw_overlay(self, o):
        k = self.k_ovl * o.scale
        h_anchor, _, v_anchor = o.anchor.partition("-")
        v_anchor = v_anchor or "middle"
        if o.is_text:
            em_px = max(4, int(round(o.size * k)))
            from . import text as T
            lay = T.layout(o.src, o.kind, o.weight, o.scale_x, o.tracking, o.line_height, False, o.align)
            key = (lay.key, em_px)
            hit = self.ovl_cache.get(key)
            if hit is None:
                arr, box = lay.raster(em_px)
                gl = upload(self.ctx, arr, 1)
                hit = (gl, box)
                self.ovl_cache.put(key, hit, int(arr.nbytes * 4 / 3), lambda v: v[0].release())
            gl, box = hit
            mode = 1
            ax, ay = lay.anchor(h_anchor if h_anchor in ("left", "center", "right") else "left",
                                v_anchor if v_anchor in ("top", "middle", "baseline", "bottom") else "baseline")
            x0 = (box[0] - ax) * em_px
            y0 = (box[1] - ay) * em_px
            w = (box[2] - box[0]) * em_px
            h = (box[3] - box[1]) * em_px
        else:
            gl, mode = self.tex.get(o.src)
            w, h = gl.size[0] * k, gl.size[1] * k
            fx = {"left": 0.0, "center": 0.5, "right": 1.0}.get(h_anchor, 0.0)
            fy = {"top": 0.0, "middle": 0.5, "baseline": 1.0, "bottom": 1.0}.get(v_anchor, 1.0)
            x0, y0 = -fx * w, -fy * h
        a = math.radians(-o.rot)
        ca, sa = math.cos(a), math.sin(a)
        X, Y = o.xy[0] * self.k_ovl, o.xy[1] * self.k_ovl
        corners = []
        for cx, cy in ((x0, y0), (x0 + w, y0), (x0, y0 + h), (x0 + w, y0 + h)):
            corners.append((X + cx * ca - cy * sa, Y + cx * sa + cy * ca))
        p = self.p_ovl
        gl.use(0)
        self._set(p, "u_tex", 0)
        self._set(p, "u_texmode", mode)
        p["u_corners"].value = corners
        self._set(p, "u_res", (float(self.RW), float(self.RH)))
        self._set(p, "u_color", tuple(map(float, o.color)))
        self._set(p, "u_opacity", float(o.opacity))
        self._blend("over")
        self.va_ovl.render(moderngl.TRIANGLE_STRIP, vertices=4)

    # ------------------------------------------------------------------ 一帧
    def _draw_items(self, items, overlays, cam, t, frame):
        aspect = self.RW / self.RH
        view = cam.view()
        vp = cam.proj(aspect) @ view
        vec_k = 0
        for it in self._sorted(items, cam):
            if isinstance(it, Particles):
                self._draw_particles(it, cam, vp)
            else:
                vec_k = self._draw_plane(it, cam, vp, view, t, frame, vec_k)
        for o in overlays:
            self._draw_overlay(o)

    def _fullscreen(self, name, target, **uni):
        p, va = self._post[name]
        target.fbo.use()
        unit = 0
        for k, v in uni.items():
            if k not in p:
                continue
            if isinstance(v, moderngl.Texture):
                v.use(unit)
                p[k].value = unit
                unit += 1
            else:
                p[k].value = v
        va.render(moderngl.TRIANGLE_STRIP)

    def render(self, frame_fn, frame, fps, n=1, shutter=0.5):
        """渲染第 frame 帧（时间 frame/fps），n 个子帧在 [t - 快门/2, t + 快门/2] 内均匀分布。
        返回中间子帧的 FrameSpec（调色参数取自它）。"""
        import time
        ctx = self.ctx
        t = frame / fps
        n = max(1, int(n))
        times = [t + ((i + 0.5) / n - 0.5) * shutter / fps for i in range(n)] if n > 1 else [t]
        t0 = time.perf_counter()
        specs = [frame_fn(ts) for ts in times]
        t1 = time.perf_counter()
        mid = specs[len(specs) // 2]
        grades = [G.merge(s.grade) for s in specs]
        gmid = grades[len(grades) // 2]
        self.tex.sweep()
        self.text_cache.tick()
        self.mask_cache.tick()
        self.ovl_cache.tick()

        used = set()
        for s in specs:
            for it in s.items:
                used.add(it.group)
            for o in s.overlays:
                if o.group == "past":
                    used.add("past")
        present_opaque = gmid["present"]["bg"] is not None
        if "present" in used or present_opaque:
            used.add("present")
        need_past = ("past" in used) or not present_opaque
        scene_groups = [g for g in ("past", "present", "raw") if g in used]

        ctx.disable(moderngl.DEPTH_TEST | moderngl.CULL_FACE)
        for si, (spec, gr, ts) in enumerate(zip(specs, grades, times)):
            for g in scene_groups:
                items = [it for it in spec.items if it.group == g]
                ovls = [o for o in spec.overlays if o.group == g and g == "past"]
                rt = self._rt(g)
                bg = gr[g]["bg"] if g in ("past", "present") else None
                rt.draw_fbo.use()
                if bg is None:
                    rt.draw_fbo.clear(0, 0, 0, 0)
                else:
                    rt.draw_fbo.clear(float(bg[0]), float(bg[1]), float(bg[2]), 1.0)
                ctx.enable(moderngl.BLEND)
                if items or ovls:
                    self._draw_items(items, ovls, spec.cam, ts, frame)
                ctx.disable(moderngl.BLEND)
                if rt.ms is not None:
                    ctx.copy_framebuffer(rt.fbo, rt.ms)
                if n > 1:
                    acc = self._acc(g)
                    if si == 0:
                        acc.fbo.clear(0, 0, 0, 0)
                    ctx.enable(moderngl.BLEND)
                    ctx.blend_func = (moderngl.ONE, moderngl.ONE)
                    self._fullscreen("accum", acc, u_src=rt.tex, u_w=1.0 / n)
                    ctx.disable(moderngl.BLEND)
        # 画面层（present / raw）：只用中间子帧画一次，不参与运动模糊
        plain = [o for o in mid.overlays if o.group != "past"]
        if plain:
            rt = self._rt("ovl")
            rt.draw_fbo.use()
            rt.draw_fbo.clear(0, 0, 0, 0)
            ctx.enable(moderngl.BLEND)
            for o in plain:
                self._draw_overlay(o)
            ctx.disable(moderngl.BLEND)
            if rt.ms is not None:
                ctx.copy_framebuffer(rt.fbo, rt.ms)
        # 缩小到输出尺寸
        downs = {}
        for g in scene_groups + (["ovl"] if plain else []):
            src = self.acc[g].tex if (n > 1 and g != "ovl") else self.rt[g].tex
            d = self._down(g)
            self._fullscreen("down", d, u_src=src, u_ss=self.ss)
            downs[g] = d
        if need_past and "past" not in downs:
            d = self._down("past")
            bg = gmid["past"]["bg"]
            d.fbo.clear(float(bg[0]), float(bg[1]), float(bg[2]), 1.0)
            downs["past"] = d
        self._grade_and_composite(downs, gmid, frame, fps)
        t2 = time.perf_counter()
        self.stats = {"scene_fn": t1 - t0, "gpu": t2 - t1}
        return mid

    def _grade_and_composite(self, downs, gr, frame, fps):
        P, Q, F = gr["past"], gr["present"], gr["final"]
        sc = self.scale
        uni = {"u_out": (float(self.W), float(self.H)), "u_seed": int(frame), "u_scale": sc}
        has_past = "past" in downs
        weave_px = G.weave(frame, fps, float(P["weave"]), sc)
        if has_past:
            exp = float(P["exposure"]) * G.flicker(frame, float(P["flicker"]))
            src = downs["past"].tex
            self._fullscreen("hipass", self.halo[0], u_src=src, u_f=4, u_mode=0, u_thr=float(P["halation_threshold"]),
                             u_exposure=exp, u_offset=(weave_px[0], weave_px[1]))
            sig = float(P["halation_radius"]) * sc / 4
            self._fullscreen("blur", self.halo[1], u_src=self.halo[0].tex, u_dir=(1, 0), u_sigma=max(sig, 0.3))
            self._fullscreen("blur", self.halo[0], u_src=self.halo[1].tex, u_dir=(0, 1), u_sigma=max(sig, 0.3))
            if float(P["grain"]) > 0:
                self._fullscreen("noise", self.noise[0], u_seed=int(frame))
                gs = 1.1 * sc
                self._fullscreen("blur", self.noise[1], u_src=self.noise[0].tex, u_dir=(1, 0), u_sigma=max(gs, 0.3))
                self._fullscreen("blur", self.noise[2], u_src=self.noise[1].tex, u_dir=(0, 1), u_sigma=max(gs, 0.3))
            else:
                self.noise[0].fbo.clear(0, 0, 0, 0)
                self.noise[2].fbo.clear(0, 0, 0, 0)
            scr = G.scratches(frame, fps, float(P["scratch"]), self.W, self.H, sc)
            dst = G.dust(frame, float(P["dust"]), self.W, self.H, sc)
            uni.update(t_past=src, t_halo=self.halo[0].tex, t_noise=self.noise[0].tex, t_noiseblur=self.noise[2].tex,
                       p_exposure=exp, p_halation=float(P["halation"]), p_shoulder=float(P["shoulder"]),
                       p_lift=float(P["lift"]), p_gain=float(P["gain"]), p_sat=float(P["sat"]),
                       p_vignette=float(P["vignette"]), p_grain=float(P["grain"]),
                       p_warmth=tuple(map(float, P["warmth"])), p_halo_col=tuple(map(float, P["halation_color"])),
                       p_weave=weave_px, n_scratch=len(scr), n_dust=len(dst))
            p = self._post["comp"][0]
            if scr:
                p["u_scratch"].value = [s[0] for s in scr] + [(0, 0, 0, 0)] * (8 - len(scr))
                p["u_scratch_y"].value = [s[1] for s in scr] + [(0, 0, 0, 0)] * (8 - len(scr))
            if dst:
                p["u_dust"].value = list(dst) + [(0, 0, 0, 0)] * (32 - len(dst))
        else:
            uni.update(t_past=self.blank.tex, t_halo=self.blank.tex, t_noise=self.blank.tex, t_noiseblur=self.blank.tex,
                       n_scratch=0, n_dust=0)
        if "present" in downs:
            src = downs["present"].tex
            thr, exq = float(Q["bloom_threshold"]), float(Q["exposure"])
            self._fullscreen("hipass", self.b6[0], u_src=src, u_f=2, u_mode=1, u_thr=thr, u_exposure=exq, u_offset=(0.0, 0.0))
            s6 = 6.0 * sc / 2
            self._fullscreen("blur", self.b6[1], u_src=self.b6[0].tex, u_dir=(1, 0), u_sigma=max(s6, 0.3))
            self._fullscreen("blur", self.b6[0], u_src=self.b6[1].tex, u_dir=(0, 1), u_sigma=max(s6, 0.3))
            self._fullscreen("hipass", self.b30[0], u_src=src, u_f=4, u_mode=1, u_thr=thr, u_exposure=exq, u_offset=(0.0, 0.0))
            s30 = 30.0 * sc / 4
            self._fullscreen("blur", self.b30[1], u_src=self.b30[0].tex, u_dir=(1, 0), u_sigma=max(s30, 0.3))
            self._fullscreen("blur", self.b30[0], u_src=self.b30[1].tex, u_dir=(0, 1), u_sigma=max(s30, 0.3))
            uni.update(t_present=src, t_b6=self.b6[0].tex, t_b30=self.b30[0].tex, q_exposure=exq,
                       q_bloom=float(Q["bloom"]), q_shoulder=float(Q["shoulder"]), q_black=float(Q["black"]))
        else:
            uni.update(t_present=self.blank.tex, t_b6=self.blank.tex, t_b30=self.blank.tex)
        uni.update(t_raw=downs["raw"].tex if "raw" in downs else self.blank.tex,
                   t_ovl=downs["ovl"].tex if "ovl" in downs else self.blank.tex,
                   has_past=int(has_past), has_present=int("present" in downs), has_raw=int("raw" in downs),
                   has_ovl=int("ovl" in downs), f_fade=float(F["fade"]), f_fade_col=tuple(map(float, F["fade_color"])))
        self._fullscreen("comp", self.out, **uni)

    def read(self):
        """读回输出：RGB 8 位字节串，第 0 行是画面顶部。"""
        return self.out.fbo.read(components=3, alignment=1)

    def read_into(self, buf):
        self.out.fbo.read_into(buf, components=3, alignment=1)

    def image(self):
        return np.frombuffer(self.read(), np.uint8).reshape(self.H, self.W, 3)
