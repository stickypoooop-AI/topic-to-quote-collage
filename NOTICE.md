# Attribution and release status

本包的工作流与视觉方向参考了 [chengyi-ai/native-subtitle-quote-image](https://github.com/chengyi-ai/native-subtitle-quote-image)，特别是区分烧录字幕像素和后期脚本字幕、真实帧组合以及可读性检查。于 2026-10-07 只读检查上游 README、SKILL 和 [LICENSE](https://github.com/chengyi-ai/native-subtitle-quote-image/blob/main/LICENSE)：上游采用 MIT，版权标注为 `Copyright (c) 2026 程意`。

本包的代码与文档在本任务中自写；未复制或改编上游代码，也没有把上游的示例图片或文字稿打包。它是受启发的独立实现，不是上游官方版本、分支或背书。本包采用独立的主题确认、上下文 provenance 和本地清单接口。以后如复制上游代码或实质部分，必须保留相应完整版权及许可通知。

Pillow、Python、FFmpeg 及系统字体属于各自作者；本包只调用用户环境已有的依赖，不分发其代码、二进制或字体。依赖的许可不被本包 MIT 替代。

`examples/fixture` 的几何图形和测试文字由本包自写生成。它们是明确标示的合成演示，不是真实讲者、引语或第三方视频截图；可随本包按所选代码许可使用。示例演示能证明机械布局，不能证明真实视频搜索、下载和引用核查已经完成。

`LICENSE` 的版权署名为 **stickypoooop-AI**，项目所有者已确认以 MIT License 发布本包自写代码、文档与合成测试素材。第三方视频、人物、讲稿、字体及依赖不在本包授权范围内。
