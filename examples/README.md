# 自制 fixture

所有画面是 `scripts/make_fixture.py` 用几何形状绘制的虚构人物；所有英文和中文句子为自写测试文案。没有真实人物、真实语录、真实视频或第三方照片。

- `fixture/manifest.json` 是可运行的格式示例；相对路径基于 `fixture/`。
- `fixture/frames/` 是无视频依赖的 compositor 输入。
- `demo/` 展示最终布局、原尺寸及可选预览。其 provenance 中的素材路径仍基于 `fixture/`。
- 示例的 `fixture.mp4` 故意不随包分发；需要真实取帧测试时，测试程序用 FFmpeg 在临时目录生成自己的颜色块视频。

演示图片标明“演示素材”“非真实引语”“不是视频截图”。任何实际任务都必须使用核验过的真实帧，不能拿此图冒充视频结果。
