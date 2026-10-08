# 验证报告

## 实际完成

- macOS 本地 Python 3.9.6、Pillow 11.3.0，使用已有 CJK 字体；没有安装依赖。
- 当前 53 项 unittest：52 通过，1 跳过。跳过项是需要 FFmpeg/ffprobe 的真实解码集成测试；当前 Mac 未发现二者，不能声称在此机器验证了实际取帧。
- 已通过：异常 JSON/重复键/类型、未知字段、非有限数、绝对路径和目录穿越、符号链接越界、错格式媒体、无效和零像素裁切、未审译文、缺上下文、乱序片段、重复 ID/帧名、两锚点校准、正负偏移、变化偏移拒绝、陈旧帧/媒体绑定拒绝。
- 已通过：两条和三条字幕渲染、RGB 与原尺寸、720×960 可选预览、同环境重复渲染字节一致、有效 JPEG 解码、默认不覆盖/显式覆盖、长中文和长标题溢出阻止输出、原生模式不会绘制翻译文本。
- 已打开实际合成预览像素检查布局；未将程序“成功”当作图像已经看过。合成图片标明自制、虚构和非真实引语，不包含真实人像、第三方截图或真实语录。
- 8 个 Python 文件已通过语法编译检查；包内相对文档链接与基础 frontmatter 检查通过。skill-creator 的 quick_validate 因本机缺 PyYAML 未能运行，未安装补齐，也未把自有检查称作该工具通过。
- 上游 README、SKILL 与 MIT LICENSE 已只读核查；本包未复制上游代码或素材，致谢范围见 NOTICE。

## 独立 Linux 复核

独立 Linux 环境为 Python 3.12.14 / Pillow 12.3.0 / FFmpeg 与 ffprobe 7.1.5-0+deb13u1 / NotoSansCJK-Regular.ttc。此前基线 44 项全部通过；路径别名与输入错误处理修订后的 51 项也已全部通过，包括真实 FFmpeg 解码。该 51 项快照同时通过官方 skill-creator quick_validate 和包审计。分发包为 30 文件，ZIP 已验证可按字节复现。

额外检查使用自制媒体，实际完成编码、取帧、真实视频模式收据校验和拼图：正/负偏移，两来源两张图，原生和译文模式，480×640，PNG/JPEG，修改来源 URL/时间/偏移/帧/视频后拒绝旧收据，第二张图溢出时不输出半套，以及默认不覆盖。实际打开渲染像素检查可读性；八类输入的路由与角度确认规则也已审阅。

非规范路径（包括 `./`）现会被前置校验拒绝；已存在文件按真实文件身份检查冲突，非 UTF-8 输入返回明确校验错误。独立审阅又复现了两个混合整数/浮点数算术边界：极大偏移与浮点锚点、极大帧时刻与浮点偏移。当前数值入口捕获 isfinite 转换溢出，在进入算术前拒绝无法安全表示的整数，并为这两个输入新增回归测试。当前 53 项在 macOS 52 通过、1 跳过；独立 Linux 最终重跑 53 项全部通过，包括真实 FFmpeg 解码集成测试，官方 quick_validate 与 30 文件包审计也通过。

## 尚未证明的事项

- macOS 验证机器未实际运行 FFmpeg 视频编码/解码；测试套件提供生成自有颜色块视频的集成测试，检测到依赖才执行，缺失时明确 skip。
- Windows 未实测；Linux 已完成上述独立检查。路径、字体和可执行文件均可配置，不能因此声称所有平台已全量通过。
- 没有在此包中验证在线搜索/下载、自动转录、引语语义或真实视频端到端生产。它们依靠宿主，合成样例不证明这些能力。
- 清单的语义审核、权利说明和校时证据是宿主填写的记录，脚本无法自动证真；图像主体和罕见字字形仍需实际查看。
- 项目所有者已确认作者署名 stickypoooop-AI 与 MIT 许可；本报告不声称已全局安装。

## 复现

从解压后的技能根目录运行：

```bash
python3 scripts/check_environment.py --render-only
python3 scripts/manifest.py examples/fixture/manifest.json --check-images
python3 scripts/render_collage.py examples/fixture/manifest.json --out output-check --preview
python3 -m unittest discover -s tests -v
python3 scripts/audit_package.py
python3 scripts/audit_package.py --zip ../topic-to-quote-collage.zip
```

完整环境再运行 `check_environment.py`，并检查 unittest 中 FFmpeg 测试显示 `ok` 而非 `skipped`。ZIP 检查含 CRC、稳定文件顺序、固定时间戳，不打包缓存、工作输出、字体、视频、平台私有传输代码或对话资料。静态隐私扫描是启发式检查，还应人工审阅新增内容。
