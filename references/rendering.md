# 渲染与命令

以下从技能根目录执行；在其他目录运行时将 `scripts/` 换成技能的实际位置。不要假设宿主工作目录等于技能目录。Windows 可以用 `py -3` 替代 `python3`。

## 已实现与外部能力

| 功能 | 提供方 |
|---|---|
| 清单结构、时钟偏移、裁切、重复路径与审核标记检查 | `manifest.py`，仅标准库；检查图片时需要 Pillow |
| 本地视频取帧，源/帧哈希绑定 | `extract_frames.py`，需要已安装 FFmpeg 和 ffprobe |
| 中文换行、主图与字幕条、来源标识、PNG/JPEG、可选预览 | `render_collage.py`，Pillow + 本机 CJK 字体 |
| 环境检查，原创建模测试素材 | `check_environment.py`、`make_fixture.py` |
| 搜索、下载、转录、字幕解析、翻译与事实/权利判断 | **宿主 Agent 的已有工具**，本包不内置、不保证成功 |

不包含下载器、ASR 模型、付费服务、浏览器登录或 cookies 操作，不自动安装软件。缺依赖就具体说明，继续不依赖它的步骤。

## 只读检查

```bash
python3 scripts/check_environment.py
python3 scripts/check_environment.py --render-only
```

可传 `--ffmpeg`、`--ffprobe`、`--font` 指定已安装文件；也可设置 `QUOTE_FFMPEG`、`QUOTE_FFPROBE`、`QUOTE_FONT`。字体依次尝试 macOS、Windows、Linux 常见 CJK 字体。仅检测文件可加载，不保证每个罕见字都存在，必须看实际输出。字体不随包分发。

## 已有媒体与清单

```bash
python3 scripts/manifest.py job/manifest.json --check-videos
python3 scripts/extract_frames.py job/manifest.json
python3 scripts/manifest.py job/manifest.json --check-images
python3 scripts/render_collage.py job/manifest.json --out output-v1 --preview
```

`job` 是用户工作的目录，需要自己准备；它不是包中已提供的真实来源示例。提取器只读本地媒体，禁止网络协议输入。改变取帧时间后另存清单和帧路径，或确认替换后用 `extract_frames.py ... --overwrite`；源哈希与时刻变化会令旧帧失效。真实渲染需要视频原文件及提取记录。当前没有把外部任意截图自动登记为真实视频证据的入口。

## 版式调节

默认起点为 1080×1440、较大的真实主帧和 2–3 条字幕。代码支持 1–6 条；图数由内容决定。标题、来源行或译文放不下会报错而不截字。优先拆完整语义单元、改版式或另做一张，不删除限定词来“适配”。有界修改后重新看图，不能宣称自动排版保证美观。

`contain` 保留裁后图的完整比例，可能留边；`cover` 等比铺满后居中裁去溢出区域。`crop` 先确定人物和画面范围，再使用 fit；cover 仍可能切脸，必须检查。两者都不拉伸。原生字幕强制 contain，主图与条带在源像素尺寸拼接后整体等比缩放，不重绘字幕、不同条不单独放大。原生模式的主图高度由 hero.crop 决定，hero_fraction 仅用于翻译模式。

译文模式在帧条上加暗色覆盖以便阅读，明确写“中文翻译”；主帧不遮盖讲者。烧录字幕存在时应选择不让原字幕与后期译文重叠的 crop，或选择原生模式；不能把自己的译文称作截图原字幕。heading 始终独立标明编辑性质。

## 格式与预览

默认输出 RGB PNG；`--format jpg` 输出 RGB JPEG，原尺寸不变。`--preview` 另外生成 720×960 RGB PNG，等比留边，不会覆盖/缩小原图。某个客户端不能展示原图时，再附单张预览即可，不能认定 JPEG 格式普遍有问题。

所有输出默认拒绝覆盖；明确要替换才使用 `--overwrite`。检测到长句溢出时整批渲染尚未写入；磁盘 I/O 故障可能造成部分文件落地，应说明并使用新目录重试。相同依赖、字体和输入产生相同像素；跨操作系统、字体或 Pillow/FFmpeg 版本不保证字节一致。
