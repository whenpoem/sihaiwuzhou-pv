# 2.5D 渲染引擎

这个引擎为《四海五洲》PV 渲染全部画面。构思里规定画面中的一切都是带纹理的平面，包括字、纸、布、墙、翻板和剪影，它们放在三维空间里前后排开，镜头在其间连续穿行，静止时看起来是二维的，运动起来才有纵深。引擎因此只处理三类东西：空间中的平面（含文字平面）、成批绘制的小方片（粒子），以及跟随镜头的画面层。所有绘制都在 RTX 4060 上用 OpenGL 4.3 完成（Python 的 moderngl 库），文字用 skia 栅格化或按矢量轮廓直接填充，成片交给显卡硬件编码器 h264_nvenc。

画面分"过去"和"今天"两种质感。引擎把场景元素分成 past、present、raw 三组，各自画进独立的高动态范围缓冲，分别调色后再合成，所以同一帧里可以同时出现带胶片颗粒和暖色的过去层与干净锐利的今天层。两套调色逐式移植自 scripts/style/look.py 的 numpy 参考实现，在样张 A 和样张 C 的原始底图上，显卡结果与参考实现的平均差约为 0.4/255（检验见"测试"一节）。

## 快速上手

引擎是 scripts/ 下的一个 Python 包。场景代码只需要写一个函数 frame(t)，返回第 t 秒的镜头、元素和调色参数，其余交给 Film。

```python
import sys
sys.path.insert(0, "scripts")            # 项目根目录下的 scripts/
from engine import Film, Cam, CamPath, Plane, TextPlane, Overlay, Particles, FrameSpec, Tex, timing

path = CamPath([
    (0.0, Cam(eye=(0, 0, 12), target=(0, 0, 0)), "ease"),
    (4.0, Cam(eye=(0, 0, 3), target=(0, 0, 0)), "ease"),
])
paper = Tex(paper_array)                       # paper_array 为 numpy 数组，第 0 行是图像顶部

def frame(t):
    items = [
        Plane(paper, center=(0, 0, 0), size=(8, 5), material="paper", stack="sheet"),
        TextPlane("陽光和襯布", kind="serif", weight=800, height=0.8, color=(0.23, 0.15, 0.10),
                  center=(0, 0, 0), material="paper", stack="sheet"),
        Overlay("阳光和衬布　发酵成　灰的味道", xy=(120, 150), size=60, weight=250),
    ]
    return FrameSpec(path(t), items, grade={"past": {"weave": 0.6}})

film = Film(frame, fps=60, size=(1920, 1080), ss=2)
film.preview(0, 4, "p.mp4")                    # 半分辨率、带时间码，检查节奏
film.still(2.0, "x.png")
film.render(0, 4, "out.mp4", subframes=path.subframes(base=1, maximum=12))
```

Film 在创建时把进程设为低于正常的优先级，取得一把全机唯一的渲染锁，再创建 OpenGL 上下文并确认它落在 NVIDIA 独立显卡上，否则报错退出。渲染锁是一个 Windows 命名互斥量：已有一个进程在渲染时，第二个进程会打印提示并等待，前一个进程结束（包括异常退出）后系统自动释放，这样同一时刻最多只有一个渲染进程占用显卡。

## 坐标与单位

场景代码给出的位置、角度和像素坐标，都按下面的约定解释。坐标为右手系，+x 向右，+y 向上，镜头默认朝 -z 看；单位任意，建议 1 单位约等于 1 米。平面默认正面朝 +z，也就是正对默认镜头，图像顶部朝 +y。平面的 rot=(yaw, pitch, roll) 以度为单位，旋转矩阵为 Ry(yaw)·Rx(pitch)·Rz(roll)：yaw 绕 +y 轴，正值把正面转向 +x；pitch 绕 +x 轴，正值把上沿转向镜头；roll 绕 +z 轴，从正面看为逆时针。镜头的 roll 与 fov 同样以度为单位，fov 是竖直视角，roll 为正时镜头绕视线逆时针转，画面里的景物看起来顺时针转。粒子的转角以弧度为单位，因为它们通常由 numpy 公式逐帧算出。平面两面都画，从背面看到的是左右反向的图像，正好符合布和纸透光的样子。

画面层（Overlay）的坐标是成片的像素坐标，原点在左上角，y 向下，按 1920×1080 书写；预览时引擎自动按比例缩小。调色里的像素尺度参数（光晕半径、划痕宽度、片门抖动幅度）也按 1080 像素高定义，其他输出尺寸按比例换算。

## 一帧是怎样画出来的

理解渲染流程，才能判断一个效果应该放在哪一组、用什么混合方式。引擎先按快门把一帧拆成若干子帧时刻：第 n 帧的时刻是 n/fps，subframes 个子帧均匀分布在以它为中心、宽为"快门 × 帧间隔"的区间里（快门缺省为 0.5，即 180 度快门），每个子帧各调用一次 frame(t)。每个子帧里，past、present、raw 三组元素分别画进各自的缓冲，缓冲是超采样分辨率（ss=2 时为 3840×2160）的半精度浮点纹理，颜色按预乘 alpha 存放。子帧画完后在显卡上累加平均，得到运动模糊。随后各组按 ss×ss 的方框平均缩小到输出尺寸，past 组走过去的调色，present 组走今天的调色，raw 组不调色。合成时 past 在最下面，present 按自身的透明度叠在上面，raw 再叠一层，最后叠加画面层。结果是 8 位 RGB，经像素缓冲异步读回，由单独的线程写进 ffmpeg。

颜色空间与 look.py 相同：数值就是显示用的 sRGB 值，允许超过 1 表示高光，不做线性化。这样做的理由是两套调色在参考实现里就是按这种数值定义的，沿用同一空间才能逐式对应、看起来一致。

每组内部按远近从后往前画（画家算法），排序依据是每个元素一个代表点沿镜头视线方向的深度。平面的代表点取平面矩形上离眼睛最近的点，粒子组取位置的平均值。用视线方向的深度而不用直线距离，是因为 2.5D 场景里的层大多正对镜头：一张小纸片在大墙面前方但偏在画面一侧时，它到眼睛的直线距离可能比墙更远，沿视线的深度却更浅。代表点取最近点，则镜头正从旁边或洞里穿过的平面深度接近零，会最后画，这也符合它离镜头最近的事实。同一平面上的元素，即法线与平面位置在容差内相同的元素（例如纸和纸上的字），自动归为一组，按加入顺序连续绘制，所以字永远压在它的纸上。需要人为指定顺序时有两个参数：stack 让同一个键的元素作为一个整体参与排序、组内按加入顺序绘制；bias 给排序深度加一个偏移（世界单位，负值表示当作更近）。

## 镜头与路线

全片一镜到底，镜头运动由一条集中管理的路线描述，每个子帧调用 frame(t) 时从这条路线取当时的镜头。Cam(eye, target, up=(0,1,0), roll=0, fov=45) 描述一个镜头状态。另有几个可选参数：dof 为景深的光圈直径（世界单位，0 表示不虚化），focus 为对焦距离（缺省取眼睛到目标点的距离），near 与 far 为裁剪面。near 缺省取 0.005，镜头才能贴着平面穿过洞口而不把洞边裁掉。

CamPath 由关键帧 (t, Cam, 方式) 组成，时间严格递增，调用 path(t) 得到插值后的镜头。方式有四种。"ease" 表示缓入缓出，镜头在该帧速度降为零，短暂停顿后再加速离开。"linear" 表示匀速通过，镜头不减速地穿过该帧，速度与前后两段连续；两个相邻关键帧都是 linear 且前后无其他帧时，这一段是严格的匀速直线。"hold" 表示在该帧停住，直到下一帧的时刻，下一帧从静止出发；下一帧的位置应与停住的位置相同，不同时会在下一帧的时刻跳变并给出警告。"cut" 表示路线在这一帧之前断开，镜头在这一帧的时刻瞬间换到这一帧的位置；断开的两侧各自插值，计算切线时不使用对侧的关键帧，所以跳变之前镜头不会朝跳变方向甩出去。cut 之前那一段在其最后一个关键帧之后按末速度匀速外推，直到跳变时刻；若最后一帧是 ease，则停在原处。cut 可以与 ease 组合成 "cut ease"，表示跳过去之后从静止出发。全片两处跳变（0:40.1 照片过曝成全白时、1:42.3 夜色只剩一个光点时）都用 cut 写。

插值的每个通道（眼睛位置、目标点、上方向、滚转、视角、景深）都用 Hermite 样条。关键帧处的切线取三点差分，对不等间距的关键帧也准确；再用 Fritsch–Carlson 方法限幅，保证在两个关键帧之间单调：某个通道在两帧之间是递减的，插值结果就不会低于后一帧的数值，镜头因此不会冲过关键帧再折回来。

推进字里的空白或从高处降到贴近地面时，眼睛到目标点的距离在一段内可能变化几十倍，例如从 17 降到 0.45。若在线性空间里插值，画面放大的速度会集中在这一段的末尾。引擎为此另算一条"对数距离"曲线：目标点照常插值，眼睛相对目标点的方向和距离的对数分别插值，距离因此按固定的倍率缩小，画面的放大速度均匀。普通曲线和对数曲线在关键帧处位置与速度都相同，引擎按每段的"推进程度"把两者加权混合，混合后仍然速度连续。推进程度由两点决定：这一段里目标点基本不动，且距离变化超过 1.25 倍时开始使用对数曲线，超过 2.5 倍时完全使用；目标点移动较多时（平移、摇镜头、带前视点的穿行）只用普通曲线。所以眼睛固定、只转动目标点的摇镜头，眼睛保持不动；想要匀速坠落而不是越接近越慢，就把目标点设成随眼睛一起移动的前视点。

路线还提供几个辅助量：path.speed(t) 为眼睛的移动速度（单位/秒），path.angular_speed(t) 为朝向的转动速度（度/秒，含滚转），path.zoom_rate(t) 为距离对数的变化率，path.velocity(t) 为速度向量。path.subframes(base, maximum, px_per_sub, depth) 返回一个 t → 子帧数 的函数，按每帧画面上的位移估计运动模糊需要的子帧数，可以直接传给 film.render。估计时平移按 depth（缺省为到目标点的距离）换算成像素；镜头擦着近处物体穿行时，把 depth 设成近处物体的距离更准确。

## 场景元素

镜头之外，frame(t) 返回的元素有四类：平面、文字平面、画面层和粒子。它们只记录参数、不碰显卡，所以每次调用都可以重新创建，纹理和文字栅格由渲染器按内容缓存。

### 平面

```python
Plane(tex, center=(x, y, z), size=(w, h), rot=(yaw, pitch, roll), opacity=1.0, blend="over",
      group="past", material="flat", uniforms={}, mask=None, color=(1, 1, 1), uv=(0, 0, 1, 1),
      stack=None, bias=0.0)
```

tex 可以是 None（纯色，取 color）、numpy 数组、PIL 图像、图片路径或 engine.Tex。二维数组按覆盖率理解，画出时乘以 color，适合字形和图案；三通道数组为不透明 RGB；四通道数组按直通 alpha 理解，上传前预乘。浮点数据里有大于 1 的值时按半精度上传，保留高光。纹理按对象身份缓存：同一个数组每帧被引用多次也只上传一次，数组被回收后显存自动释放；数组在原处被修改后要改用 Tex 并调用 update()。color 乘在纹理上，可以超过 1。blend 取 over（普通叠放）、add（加亮，用于光，不改变本组的透明度）或 multiply（正片叠底，用于污渍和阴影）。uv 是纹理子区域，v 向下；配合 Tex(..., repeat=True) 把 uv 设成超出 0–1，纹理就会平铺。

mask 用于在平面上挖洞，镜头可以从洞里穿进下一层。它可以是数组或 Tex，1 表示保留、0 表示挖掉，按平面的 0–1 坐标铺满；也可以是一条 skia.Path，用平面的 0–1 坐标描述（u 向右、v 向下），路径内部就是洞。路径遮罩按平面在画面上的投影大小分档栅格化，最高 8192 像素，镜头贴近洞口时边缘仍然清楚。

### 文字平面

```python
TextPlane(text, kind="serif", weight=400, height=1.0, color=(r, g, b), center=..., rot=..., group=...,
          trad=False, scale_x=1.0, align="center", vector=False,
          valign="middle", tracking=0.0, line_height=1.3, vertical=False,
          opacity=1.0, blend="over", material="flat", uniforms={}, mask=None, stack=None, bias=0.0)
```

kind 取 serif（思源宋体）、sans（思源黑体）、fang（朱雀仿宋）、kai（霞鹜文楷），前两种是可变字重字体，weight 取 200–900。height 是字号（1 em）的世界长度。center 是锚点，水平位置按 align（left / center / right），竖直位置按 valign（top / middle / baseline / bottom），旋转也绕锚点进行。trad=True 时用 look.trad() 转成繁体。文字可以含换行；vertical=True 时竖排，每列从上到下、列从右往左；tracking 为字距（em）。汉字按表意字框对齐，字框上沿在基线上方 0.88 em、下沿在基线下方 0.12 em，所以 middle 指字框居中，汉字看起来正好在中间。

引擎每个子帧都会计算文字平面投影到画面上每 em 占多少像素，按 2 的幂分档栅格化并缓存（16 到 4096 像素每 em），优先复用已有的更高分档，所以镜头推近时只在跨档时栅格化一次，拉远时不再重画。栅格化时不做字形微调，各分档的字形形状一致，切换时看不出跳变。vector=True 时，只要整个文字平面在镜头前方、投影又超过每 em 700 像素，引擎就按当前镜头算出从字形坐标到画面像素的透视变换，把字形轮廓折线化后逐点投影到渲染分辨率下，再交给 skia 填充。这样放大到字里的笔画占满画面，边缘仍是一两个像素宽的抗锯齿过渡；测试短片里"吵"字左边的"口"放大到方框占满画面时，每 em 约 2900 个渲染像素（ss=2，即成片每 em 约 1450 像素），笔画边缘依然锐利。

字形轮廓可以直接取用，供之后的笔画拆分和字形切开使用。tp.outline() 返回整段文字的 skia.Path，tp.glyph_paths() 返回逐字轮廓，坐标都是 em 坐标（基线在 y=0，y 向下）；tp.em_to_world(x, y) 把 em 坐标换算成世界坐标，用于定位字里的部件。模块级函数 glyph_path(字, kind, weight)、contours(path)（按闭合子路径拆开）、flatten(path)（折线化为多边形数组）、bounds(path) 和 layout(...)（排版结果，含逐字位置、排版框和栅格化方法）可以脱离场景使用。思源宋体的笔画是相互重叠的独立轮廓，"口"中间的空白不是单独的子路径，求空白时要在栅格上取不与边界相连的连通区域，测试短片的 kou_geometry() 是一个例子。

### 画面层

```python
Overlay(tex_or_text, xy=(px, py), anchor="left-baseline", group="present", opacity=1.0,
        size=60, kind="serif", weight=300, color=(1, 1, 1), scale_x=1.0, trad=False, tracking=0.0,
        line_height=1.3, align="left", rot=0.0, scale=1.0)
```

画面层跟随镜头，用于高速段落里必须读得清的歌词。给字符串时按 size（像素字号）排字，也可以给图像。anchor 写作"水平-竖直"，水平取 left / center / right，竖直取 top / middle / baseline / bottom，图像没有基线，baseline 按底边处理；rot 以度为单位，绕锚点旋转。

group 决定画面层与调色的关系。present（缺省）和 raw 在调色之后最后叠加，颜色原样输出，白字就是纯白、边缘锐利，与样张 C 里歌词不受调色影响的做法相同；它们只用中间子帧画一次，不参与运动模糊。past 画进过去层、在调色之前叠加，带上与背景相同的颗粒、光晕和暖色，用于过去段落里需要融进画面的字。

### 粒子

```python
Particles(atlas, pos, size, rot=None, color=None, uv=None, blend="over", group="past",
          back=None, opacity=1.0, sort=None, stack=None, bias=0.0)
```

粒子用显卡实例化绘制，每个粒子是一个小方片，属性放在着色器存储缓冲里。pos 为 (N,3)；size 为 (N,) 或 (N,2) 的世界长度；color 为 (N,4)；uv 为 (N,4)，即每个粒子在图集里的纹理坐标。rot 为 (N,) 时方片始终面向镜头，值为绕视线的转角；为 (N,3) 时方片按 (yaw, pitch, roll) 在空间中定向，此时 back 给出背面颜色，可以直接做翻板。blend 为 over 时引擎每个子帧按深度排序（只上传排序后的序号，不搬动数据），add 时不排序。图集由 glyph_atlas(字串, kind, weight, cell=128, trad=False) 生成，每个字占一个方格，按表意字框居中；atlas.uv("四海五洲") 或 atlas.index_uv(序号数组) 给出纹理坐标；dot_atlas(hardness) 是柔边圆点。3 万个字形粒子的上传、排序和绘制每个子帧约 2 毫秒。20 万个字形粒子在 1080p、ss=2、单个子帧下整帧（含调色和读回）约 23 毫秒，按 add 混合不排序时约 17 毫秒，其中排序和数据上传占了大半；实际场景里，生成这些数据的 numpy 代码往往比绘制本身更慢。整个粒子组作为一个整体与平面排序，粒子和平面之间不逐个交错。

## 材质

平面画出时，底色先经过材质再参与混合，载体的质感（纸纹、布纹、扫描线）就在这一步加上。材质是一段 GLSL 片段，必须定义 vec4 material(vec4 base)：输入是预乘 alpha 的底色（纹理乘颜色），返回预乘 alpha 的颜色；遮罩和不透明度在 material() 之后统一乘上。内置两种材质：flat 原样返回底色；paper 在平面自身的坐标里生成纸纹（细纹、纤维、大块偏黄的污渍），纸纹随平面移动，近看仍有细节，远看时过细的倍频按每像素跨过的尺度淡出，运动中不闪烁；画在纸上的字（覆盖率纹理）在纸纹凸起处掉墨，挖洞的边缘泛出焦黄。paper 的参数为 paper_amount（纸纹强度，缺省 1.0）、paper_scale（纸纹尺度，世界单位，0.04）、paper_tint（污渍颜色）、paper_stain（污渍强度，0.35）、paper_ink（掉墨程度，0.5）和 paper_edge（洞边焦黄，0.8），都可以在平面的 uniforms 里逐项覆盖。

之后各段要添加的布、墙、玻璃、水、显像管等材质，用 register_material 注册：

```python
from engine import register_material

register_material("crt", """
uniform float crt_lines;          // 扫描线条数
uniform float crt_roll;           // 画面上下翻滚的速度
vec4 material(vec4 base) {
    float y = fract(v_uv01.y + u_time * crt_roll);
    float scan = 0.75 + 0.25 * sin(y * crt_lines * 6.2831853);
    float snow = rnd(ivec2(gl_FragCoord.xy), u_frame) * 0.15;
    return vec4(base.rgb * scan + snow * base.a, base.a);
}
""", defaults={"crt_lines": 240.0, "crt_roll": 0.0})

Plane(tv_image, ..., material="crt", uniforms={"crt_roll": 0.3})
```

片段里可以使用这些现成的量：v_uv（纹理坐标，v 向下）、v_uv01（平面上 0–1 的坐标，v 向下）、v_local（平面局部坐标，世界单位，原点在平面中心）、v_wpos（世界坐标）、v_depth（到镜头的深度）、u_time（子帧时刻）、u_frame（帧号）、u_seed（每个平面一个稳定的 0–1 随机数，由纹理或文字内容决定，跨进程不变）、u_size、u_normal、u_eye、u_res、u_tex、u_texmode、u_vector、u_mask、u_hasmask、g_blur（景深模糊半径，像素）、g_mask（遮罩值），以及噪声函数 rnd、vnoise、gnoise 和带抗锯齿的 fbm。uniforms 里的数组或 Tex 会作为纹理自动绑定到同名的 sampler2D 上。同名重复注册会替换旧材质，已编译的程序在下次使用时重新编译。

## 调色

各组画完并缩小到输出尺寸之后才调色，所以调色参数按帧给出，而不是按元素给出。参数写在 FrameSpec 的 grade 里，只需写出要改变的项，其余取下表的缺省值；每帧都可以不同，用于过渡。

```python
FrameSpec(cam, items, grade={"past": {"exposure": 1.6, "halation": 2.0}, "present": {"bg": (0.02, 0.024, 0.03)}})
```

过去的调色依次做这些事，与 look.grade_past 逐式对应：乘曝光；取三通道平均超过阈值的部分，高斯模糊后按橙色加回，形成高光周围的光晕；用 x/(1+k·x) 压出柔和的高光肩部；抬起黑位并乘增益；乘偏暖褪青的通道系数；调饱和度；乘暗角；加颗粒；画划痕；截断到 0–1。颗粒是两路以帧号为种子的标准正态噪声，一路直接用，一路经 1.1 像素的高斯模糊后乘 1.6 再加上，强度随亮度增加，与参考实现的统计性质相同。划痕在参考实现里是一条固定的竖线；成片需要它像真实胶片一样偶尔出现，所以引擎把时间按 0.4 秒分窗，每个窗口以一定概率出现一条持续 0.15–0.9 秒的划痕，持续期间位置缓慢漂移、亮度闪动、沿竖直方向轻微弯曲，强度为 1 时与参考实现的那条线相同。片门抖动、亮度闪烁和灰尘斑点是参考实现没有的三项，缺省为零。

今天的调色与 look.grade_present 对应：亮处超过阈值的部分分别经 6 像素和 30 像素的高斯模糊后加回（泛光），再用 x/(1+0.15x) 压高光、抬起一点黑位。present 组有透明处时按预乘 alpha 叠在过去之上，泛光既作用于本层，也溢到下面的过去层。present 组的白色经过这条曲线后约为 0.87，所以今天的白字若要纯白，应当用画面层（present 组画面层不调色），或把 color 设到 1.2 左右。

| 组 | 参数 | 缺省值 | 含义 |
|---|---|---|---|
| past | exposure | 1.0 | 调色前的曝光倍数，过曝转场时调高 |
| past | halation | 1.6 | 光晕强度 |
| past | halation_threshold | 0.85 | 进入光晕的亮度阈值（三通道平均） |
| past | halation_radius | 26 | 光晕的高斯半径（像素，1080p） |
| past | halation_color | (1.0, 0.45, 0.15) | 光晕颜色 |
| past | shoulder | 0.55 | 高光肩部 x/(1+k·x) 的 k |
| past | lift | 0.035 | 黑位抬起 |
| past | gain | 1.3 | 增益 |
| past | warmth | (1.06, 0.97, 0.80) | 三通道系数（偏暖褪青） |
| past | sat | 0.9 | 饱和度 |
| past | vignette | 0.32 | 暗角 |
| past | grain | 0.028 | 颗粒强度 |
| past | scratch | 1.0 | 划痕出现的频度，0 为没有 |
| past | dust | 0.0 | 每帧灰尘斑点的平均个数 |
| past | weave | 0.0 | 片门抖动幅度（像素，1080p），0.5–1 较自然 |
| past | flicker | 0.0 | 亮度闪烁幅度，例如 0.03 |
| past | bg | (0, 0, 0) | 过去层的底色 |
| present | exposure | 1.0 | 调色前的曝光倍数 |
| present | bloom | 0.35 | 泛光强度 |
| present | bloom_threshold | 0.8 | 泛光阈值 |
| present | shoulder | 0.15 | 高光肩部的 k |
| present | black | 0.02 | 黑位 |
| present | bg | None | None 为透明（叠在过去之上）；给颜色则不透明，过去层不再渲染 |
| final | fade | 0.0 | 整体淡到 fade_color 的程度，0–1 |
| final | fade_color | (0, 0, 0) | 淡入淡出的颜色 |

## 输出

调色合成后的帧经由下面几个入口写成文件。film.render(t0, t1, out, subframes=4, audio=True, shutter=0.5) 渲染 [t0, t1) 并写出 mp4，subframes 可以是常数，也可以是 t → 整数的函数（静止处取 1，高速处多取）。视频用 h264_nvenc 编码，参数为 -preset p6 -tune hq -rc vbr -cq 16、yuv420p、high profile；RGB 转 YUV 时显式指定 BT.709 矩阵并把色彩标记写进码流，否则 ffmpeg 默认按 BT.601 转换，颜色会偏。音频取 audio/song.wav 中与画面对应的一段，编码为 AAC 256 kbps，apad=whole_dur 在歌曲结束后补静音，保证音轨和画面一样长。ffmpeg 子进程同样以低于正常的优先级运行。film.still(t, path, subframes=1) 输出 PNG；film.frame_image(t) 返回 numpy 数组。film.preview(t0, t1, out) 以半分辨率、不超采样、不做运动模糊渲染，右下角带时间码，配上音乐，供动态分镜检查节奏。

全片分段渲染时，第 n 帧的时刻固定为 n/fps，颗粒、划痕、纸纹的随机量都由帧号或内容决定，同一帧无论单独渲染还是在哪一段里渲染，结果都完全相同。分段用 engine.concat([段1, 段2, ...], out) 无损拼接，视频流直接复制，不重新编码。拼接时有两个细节会影响逐帧对齐，引擎都已处理。其一，每段的时长取"帧数 / 帧率"而不取容器时长，因为 AAC 按 1024 个采样一包，音轨总比画面略长。其二，AAC 编码器在音轨开头加约 23 毫秒的预热，concat 分离器按最早开始的流对齐，若连同音轨一起拼，画面会整体推迟约 1.4 帧、多出一帧；所以引擎先把各段的视频流单独复制出来再拼。音频缺省从 song.wav 按第一段的起点重新取整段编码（audio="wav"），拼接处没有咔声；也可以用 audio="copy" 直接拼接各段音频。为此 Film 会在每个输出文件的元数据里记下起点、帧率和帧数。

成片的码率较高：过去层的胶片颗粒是高频细节，cq 16 下测试短片约为每秒 110 兆比特，全片约 2.7 GB。这是母版的合理大小，上传前可再转码。

## 时间数据

画面的动作要对准字的元音起点、小节首拍和鼓点，这些时刻由 engine.timing 提供。它读取 data/timing.json（由 scripts/timing.py 生成），文件不存在时抛出 TimingMissing 并说明如何生成；文件更新后按修改时间自动重新读取。编号与 timing.json 和构思一致：歌词行号 1–40（即 L01–L40），行内字序从 1 起、不计全角空格；小节号从 1 起，小节内的拍从 1 起，可以是小数。

```python
from engine import timing as T
T.char(1, 11)                 # L01 第 11 个字"吵"的起点（修正到元音开始处的 t）
T.find_char(1, "吵")           # 字序 11
T.line(5), T.line_span(5)      # 整行记录，(起点, 终点)
T.bar(17), T.beat(17, 3)       # 第 17 小节首拍、第 3 拍
T.bar_at(60.0)                 # (小节号, 拍位置)
T.kicks(55, 60), T.snares(), T.hats()      # 底鼓、军鼓、镲片起点
T.event("drums_in"), T.section("chorus1")  # 事件与段落
T.hit(t, T.kicks(), decay=0.25)            # 最近一次底鼓之后按指数衰减的包络
T.ease("out_cubic", T.ramp(t, 1.0, 2.0))   # 缓动
T.tween(t, 1.0, 2.0, a, b, "in_out_cubic") # 按缓动从 a 过渡到 b
```

缓动函数包括 linear、smoothstep、smootherstep，in_ / out_ / in_out_ 加 quad、cubic、quart、quint、sine、expo、circ，以及 in_back、out_back、out_elastic。

## 性能

下表是测试短片（12 秒，720 帧）在 RTX 4060 Laptop 上的实测值，包含场景函数、绘制、调色、读回和编码的全部时间。场景是 6 层约 50 个纸张与文字平面、一个矢量模式的大字、3 万个字形粒子和一行画面层。

| 设置 | 平均（毫秒/帧） | 穿层段 | 推进"口"字段（矢量） | 粒子段 |
|---|---|---|---|---|
| 1080p，ss=2，固定 4 个子帧 | 57 | 63 | 61 | 43 |
| 1080p，ss=2，自适应 4–16 个子帧（平均 7.1） | 96 | 123 | 88 | 67 |
| 预览：960×540，ss=1，1 个子帧 | 16 | 18 | 15 | 13 |

固定 4 个子帧时 p95 为 79 毫秒/帧。按这个速度，全片 3 分 20 秒（12000 帧）正式渲染约需 11–19 分钟，取决于子帧数；预览约 3 分钟。时间大致按子帧数线性增长，每个子帧约 12–14 毫秒，其中多数是 Python 端的开销（调用 frame(t)、生成粒子数据、逐个平面设置着色器参数），显卡绘制只占一小部分，所以场景代码写得是否高效，比元素多少更影响速度。矢量模式每个子帧要在 3840×2160 下用 skia 填充一次字形并上传，推进段的元素比穿层段少得多，耗时却相当。文字跨分档时的首次栅格化会让个别帧变慢，不影响平均值。

## 测试

scripts/tests/ 下的五个脚本覆盖引擎的全部功能，输出在 renders/tests/。engine_demo.py 渲染测试短片 engine_demo.mp4、预览 engine_demo_preview.mp4 和四张静帧（穿层、穿洞、"口"字占满画面、"四海五洲"成形），并把计时写进 engine_demo_timing.json；它同时检验了颗粒逐帧变化（相邻两帧纯背景区域之差的标准差为 5.5 个 8 位量化级）和渲染的确定性（同一帧重复渲染逐位相同）。

其余四个脚本分别检验一个方面。grade_check.py 用样张 A、样张 C 的原始底图比较显卡调色与 look.py：过去的调色平均差 0.0015、99% 分位 0.0047，颗粒标准差之比 1.002，今天的调色平均差 0.0016，对比图为 grade_check.png。camera_check.py 检验镜头路线的 15 项性质，包括下降与多段推进不过冲、推进按对数距离、关键帧处速度连续、眼睛固定的摇镜头保持不动、cut 两侧互不影响且不回甩、hold 停住并从静止出发，全部通过。concat_check.py 把同一秒分两段渲染后拼接，结果为 60 帧、1.00 秒，拼接处的帧与第二段的首帧逐位相同。features_check.py 检验测试短片没有用到的功能（present 组底色、raw 组、add 与 multiply 混合、带背面颜色的翻板粒子、多重采样、竖排文字、数组遮罩、平铺纹理、旋转的图像画面层、engine.timing），并给出各功能的最小用例，输出 features_check.png；其中 raw 组色块的输出值精确等于褪色红 #B5412E。

## 接口补充

相对最初约定的接口，类名、构造参数和方法都保持不变，只补充了可选参数与几个辅助函数。CamPath 的方式按 ease / linear / hold / cut 实现，并允许 "cut ease" 组合。平面和镜头的角度以度为单位，粒子的转角以弧度为单位。画面层的 group 按上文"画面层"一节解释：present 与 raw 在调色之后叠加、颜色原样输出，past 画进过去层参与调色。补充的可选参数有：Plane 的 color、uv、stack、bias；TextPlane 的 valign、tracking、line_height、vertical 以及与 Plane 相同的材质、遮罩、混合参数；Overlay 的 size、kind、weight、color、rot、scale 等排字参数；Particles 的 back、opacity、sort；Cam 的 dof、focus、near、far；Film 的 msaa（每个超采样像素的多重采样数，大量硬边小方片如翻板可设 4）；film.render 的 shutter；grade 的 final 组。新增的辅助接口有 Tex、path.subframes / angular_speed / zoom_rate / velocity、film.frame_image、engine.concat、glyph_path / contours / flatten / bounds / layout，以及 TextPlane 的 outline / glyph_paths / em_to_world。

## 范围与局限

排序以元素为单位进行，没有逐像素的深度比较，所以相互穿插的平面无法正确遮挡，铺在镜头下方、向远处延伸的大地面会因为离镜头最近而被画在最上面；这两种情况要用 bias 或 stack 指定顺序，粒子组与平面之间也只能整体排序。运动模糊由子帧平均得到，子帧不够时细笔画会出现几道分开的残影：测试短片穿层段的最快处在固定 4 个子帧下能看到四道残影，按 path.subframes() 自适应取到 10–12 个子帧后才连成平滑的模糊，因此正式渲染应当用自适应子帧。景深用纹理的多级缩小图近似，适合"略微虚化"，模糊半径大时会显得发块，也不作用于矢量模式的字和粒子；矢量模式只在整个文字平面位于镜头前方时启用，镜头斜着穿过字时退回栅格，最高每 em 4096 个渲染像素。
