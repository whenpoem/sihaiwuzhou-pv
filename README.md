# 《四海五洲》文字 PV 渲染代码

这里是《四海五洲》文字 PV 的全部渲染代码。歌曲由 TOPKINGCREAM 作词作曲，原唱星尘，每分钟 140 拍，时长 3 分 19.77 秒；PV 由 leaderone、opus 制作。成片 1920×1080、每秒 60 帧，每一帧都由程序生成，没有使用剪辑软件、视频素材或现成的动效模板。

## 这部 PV 是怎样做出来的

整部片子以歌词为主角，一切画面都从字的变化里延伸出来。画面的含义靠"字下有字"表达：歌词底下压着它所引用的旧文本，也就是诗词和那个年代的口号，在擦除、褪色、烧穿的时候露出一部分。全片在空间上越往深处年代越早，开头和结尾在一张旧纸上，中间穿过晾衣绳上的被单、标语墙、霓虹城市、翻板体育场等不同的层。

为此专门写了一个 2.5D 渲染引擎（`scripts/engine/`）。画面里的一切，包括字、纸、布、墙、翻板和剪影，都是放在三维空间里的带纹理的平面，镜头在平面之间平移、推拉和穿行；静止时画面看起来是二维的，运动起来才有纵深。渲染用 OpenGL 4.3（Python 的 moderngl 库），文字用 skia 栅格化或按矢量轮廓填充。画面分"过去"和"今天"两种质感，引擎把元素分成三组分别画进高动态范围缓冲，过去的一组加胶片颗粒、暖色和光晕，今天的一组保持干净锐利，再合成到同一帧里。引擎的用法、材质和调色参数在 [scripts/engine/README.md](scripts/engine/README.md) 中有详细说明。

全片按歌曲结构分成九段，每段是一个目录（`scripts/seg_a1/` 到 `scripts/seg_h/`），各自提供一个函数 `frame(t)`，返回第 t 秒的镜头、画面元素和调色参数。相邻两段在一个事先约定的时刻和画面上相接，这些交接画面集中写在 `scripts/film/handoff.py`，所以九段可以分开制作，拼起来仍是连续的。画面上的动作对准歌曲的时间：大的转场落在小节首拍和鼓点上，每个字在它的元音起点出现。这些时间数据由 `scripts/timing.py` 从分离出的音轨和逐字对齐结果计算，做法见 [data/timing说明.md](data/timing说明.md)。

## 目录结构

| 路径 | 内容 |
|---|---|
| `scripts/engine/` | 渲染引擎：平面与粒子、材质与着色器、文字、镜头、调色、逐帧渲染与硬件编码 |
| `scripts/film/` | 全片层面的代码：镜头与空间布局（`plan.py`）、平面镜头（`flatcam.py`）、交接画面（`handoff.py`）、正式渲染与拼接（`assemble.py`）、结尾的关灯声（`sfx.py`）、图片来源汇总（`credits.py`） |
| `scripts/seg_a1/` | 前奏：旧纸上的老照片随鼓点翻开，再印出片名与署名 |
| `scripts/seg_a2/` | 主歌一前半：钢笔字、猫、电视里的卫星云图 |
| `scripts/seg_b/` | 主歌一后半：晾衣绳上的被单、白云骑士 |
| `scripts/seg_c/` | 副歌一前半：灯丝熔断、标语墙、展览馆尖塔（入口为 `flat.py`） |
| `scripts/seg_d/` | 副歌一后半与间奏一：雨夜的砖地、积水、单车 |
| `scripts/seg_e/` | 主歌二：马灯照亮的木门、锁孔、水下与上升的地层 |
| `scripts/seg_f/` | 副歌二：LED 行情屏、霓虹城市、白帆 |
| `scripts/seg_g/` | 间奏二：镜头向下穿过前面各段画面做成的层 |
| `scripts/seg_h/` | 桥段与尾段：夜里的翻板体育场、风暴、阳光，以及纸上的结尾 |
| `scripts/style/look.py` | 两种质感的调色参考实现、色板、字体与繁简转换 |
| 数据准备脚本 | `separate.py`（Demucs 分离人声与鼓）、`analyze_audio.py`（节拍与响度）、`transcribe*.py` 与 `align_lyrics.py`（Whisper 逐字对齐）、`timing.py`（逐字时间与鼓点）、`fetch_images.py`（从 Wikimedia Commons 下载公开授权的图片并记录授权） |

## 仓库里不包含的内容

仓库只放代码。歌曲音频和歌词的版权属于原作者，没有放进来；画面用到的照片、纹理和字体也不在仓库里，它们来自 Wikimedia Commons、Poly Haven 和开源字体（霞鹜文楷、朱雀仿宋），授权各不相同。渲染时还会用到 Ultralytics 的 YOLO26 分割模型（`yolo26s-seg.pt`）来抠出照片里的猫和人。由于这些文件不在仓库中，克隆下来以后不能直接渲染出成片；代码的主要用途是参考具体做法。若要自己运行，需要在项目根目录下按代码中的路径准备 `audio/`、`lyrics/`、`assets/images/`、`assets/fonts/` 和 `assets/models/`，再依次运行数据准备脚本生成 `data/timing.json`。

## 运行环境

制作时的环境为 Windows 11、NVIDIA RTX 4060 Laptop 显卡、Python 3.11（conda 环境），依赖的软件包及版本见 [requirements.txt](requirements.txt)，其中 torch 为 CUDA 12.8 版本。视频编码只用显卡的硬件编码器 h264_nvenc，需要带 NVENC 的 ffmpeg（代码优先使用 conda 环境 `Library/bin` 下的 ffmpeg，没有时使用系统路径上的）。各段渲染与拼接的命令为：

```bash
python scripts/film/assemble.py render
```

```bash
python scripts/film/sfx.py
```

```bash
python scripts/film/assemble.py concat
```

第一条命令逐段渲染到 `renders/final/`，每段在单独的进程中运行，因为各段目录里有同名的模块；第二条命令在歌曲上叠加结尾的关灯声；第三条命令把各段无损拼接，配上整条音轨，输出成片。每段目录下的场景脚本也可以单独运行，输出预览、对照图或单帧，用法写在各脚本开头的说明里。

## 许可

代码以 MIT 许可发布，见 [LICENSE](LICENSE)。歌曲、歌词以及画面中使用的图片和字体不在此许可范围内，分别归各自的作者所有。
