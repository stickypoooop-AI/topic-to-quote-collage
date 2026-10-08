# Manifest v1

UTF-8 JSON。可运行的权威检查器是 `scripts/manifest.py`；不依赖第三方 schema 库。完整、自包含的示例见 [合成清单](../examples/fixture/manifest.json)。以下表格描述它的全部字段，未知字段被拒绝，避免拼写错误静默失效。

路径以清单所在目录为根，使用相对 POSIX 路径。拒绝绝对路径、`..`、`./` 别名、重复分隔符、反斜杠、驱动器路径及指向目录外的符号链接；文件已存在时也检查指向同一文件的内部别名绑定。输入视频扩展名限 mp4/mov/mkv/webm/m4v；帧限单张 PNG/JPEG，并检查真实格式，不靠扩展名判断内容。

## 顶层

| 字段 | 类型/约束 | 含义 |
|---|---|---|
| `schema_version` | 整数 1 | 当前格式 |
| `kind` | `real_video` / `synthetic_fixture` | 后者永远带醒目演示标识，不能用于真实引语任务 |
| `editorial` | 对象 | `topic`、`angle`、`confirmation` 非空字符串；`status` 为 `confirmed` 或 `exact_brief` |
| `sources` | 非空数组 | 以下 source 对象，ID 唯一 |
| `cards` | 非空数组 | 以下 card 对象，不限制固定卡片数 |
| `layout` | 对象 | `width` 480–4096，`height` 640–6144，`font_size` 18–160 均整数；`hero_fraction` 0.35–0.78；`fit` 为 `contain` / `cover` |

`confirmation` 只记用户确认的编辑内容，不保存聊天 ID、私有账号或完整对话。所有数值必须有限并能安全转换为浮点表示；无法转换的极大整数会在算术前拒绝，布尔值不当作数字。

## Source

| 字段 | 约束与含义 |
|---|---|
| `id`, `title`, `language` | 非空；title 是可追溯的来源标题，language 如 en、zh、ja |
| `url` | 公开 HTTP(S) 原始来源，不含账号密码；fixture 可用 `fixture:` URI |
| `video` | 相对本地视频路径；仅布局测试时可指向尚未生成的 fixture 视频 |
| `duration_seconds` | 本地文件实际时长，正数；提取器会与 ffprobe 比较，容差 0.25 秒 |
| `rights_note` | 已知素材许可/授权或待确认的具体情况 |
| `transcript` | `kind` 为 official/manual/asr_reviewed/synthetic，后者仅限 fixture；`reference` 记录文字稿链接或定位说明；`verification_note` 说明复核依据 |
| `timing` | `offset_seconds` 为有符号秒数；`tolerance_seconds` 0–0.5；`anchors` 至少两个不同锚点 |

每个锚点包含 `transcript_seconds`、`media_seconds`、`evidence`；前两者为非负数，后者描述实际听看依据。两者差必须在容差内等于偏移；不合则停止。锚点与取帧时刻不能超出本地时长。容差不是允许忽略语义对位的余量。

## Card 与 Quote

| Card 字段 | 约束与含义 |
|---|---|
| `id` | 安全文件名：小写字母/数字开头，其后可有 `_`、`-`；1–64 字符，唯一 |
| `source_id` | 对应一个 source |
| `heading` | 编辑标题，与讲者原话分开标注 |
| `mode` | `translated_script` / `native_burned_in` |
| `hero` | frame 对象 |
| `quotes` | 1–6 条 quote；默认建议 2–3 条。超出则用更多卡片或调整需求 |

Quote 字段全部必需：

- `speaker`：这句话的说话人，不自动继承嘉宾名字。
- `start`、`end`：原文字稿时钟，前小后大；按时间排序，互不重叠。
- `original_text`、`translation_zh`：原文与核验中文。原生模式可留空译文，渲染器不画译文。
- `context_before`、`context_after`：足以防误读的前后语境。来源边界可写“已核对，这是发言开头/结束”，不能留空。
- `excerpted`：严格布尔值；为真时 `omissions_note` 必须说明删节。无省略时该说明可空。
- `reviewed`：必须为 true；表示宿主已实际审核原文与翻译，程序不能代为认证。
- `frame`：对应这句实际时间内的真实帧。

Frame 字段：`image` 为 PNG/JPEG 相对路径；`transcript_time` 为非负秒数；`crop` 为 `[left, top, right, bottom]`，各在 0–1，正面积，基于原图。引语帧必须位于该句起止范围。同一图片路径不能关联不同来源或时间点。

原生模式使用 `fit: contain`，所有字幕条的 crop 左右必须为 0 和 1，保留完整字幕宽度。裁切后的主图和字幕条必须同宽，先拼源像素再统一缩放。

## 提取记录与输出

每个取帧文件旁写入 `.frame.json`，记录 source ID、来源 URL、源视频 SHA256、帧 SHA256、原时刻、偏移和请求的本地定位时刻（不是实际帧 PTS 测量）。真实视频渲染必须校验该记录，拒绝已更改的时间、偏移、视频或图片。它证明文件绑定，不能证明引语本身真实。

`provenance.json` 保存经过验证的完整输入清单；文件路径仍相对于原清单目录，**不是输出目录**。在交付中同时给出人类可读出处，不能让用户只拿到不可解释的 JSON。`render-report.json` 列出输出、字体文件名和 QA 状态；默认 visual QA 为 pending，直到宿主实际检查图像。
