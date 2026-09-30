# 项目文档

后续 Web 前端开发从 [接口文档总目录](api/README.md) 开始，包含所有已注册 CampusMate 接口、模块契约、请求与响应字段、鉴权、错误、流式协议、异步流程及 Web 调用对照。

- [接口接入与功能流程](api/integration.md)
- [OpenAPI JSON](api/openapi.json)
- [独立学习空间 API](api/learning-space.md)
- [原有 magic class 模块说明](magicclass-module-report.md)

## 端侧 AI 能力（行为识别 / 表情识别）

行为识别（可见学习行为观察）与表情识别在设备本地推理，画面不上传服务器、不经过后端 HTTP，因此基于后端已注册路由整理的 `api/` 手册不含这两项能力，该手册也未查看 Android、HarmonyOS 与微信小程序。实现说明在 `ml/` 与各端 README：

- 端侧识别链路交接（模型清单与哈希、数据流、类别与校准契约、回退语义、重写检查清单）：[端侧识别链路](on-device-recognition-pipeline.md)
- 训练、评估与导出：[行为识别](../ml/behavior_recognition/README.md)、[表情识别](../ml/expression_recognition/README.md)
- Android（CameraX + ML Kit + LiteRT / ONNX Runtime，Mock/Real 双实现与隐私边界）：[android/README.md](../android/README.md) 的“表情识别”与“本地行为识别演进与学习状态辅助”章节
- HarmonyOS（MindSpore Lite 本地模型）：[harmony/README.md](../harmony/README.md) 的“本地表情与学习行为识别”章节
- 微信小程序：仅 Mock 演示，见 [wx/README.md](../wx/README.md)

接口层面只覆盖后端契约：`ExpressionSignal` 透传（[AI 助手](api/10-assistant-knowledge.md)、[学习陪伴](api/05-study.md)）与表情样本共建接口（[AI 助手](api/10-assistant-knowledge.md)）；后端不做 CNN 表情推理，该字段标注为“仅透传存储”。
