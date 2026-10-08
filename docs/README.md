# 项目文档

## 规划与后端交付范围

2026-10-08 的规划补齐仅涉及后端和接口文档。前端、设备应用、模型训练及实体硬件开发留待后续任务；历史规划中的管理员端不符合当前仅学生角色的产品边界。

| 规划 | 后端交付与验收入口 | 后续验收 |
| --- | --- | --- |
| 六层世界模型 | [后端实现与闭环](world-model-backend.md)、[偏好、纠正、预测与模拟契约](api/11-learner.md) | 真实教务接入、真实结果标签及预测校准效果；规则测试不证明预测准确率 |
| Agent Runtime v2 / EvoFlow 优化 | [运行模式、排空与恢复](../backend/README.md)、[任务与事件协议](api/12-agents.md) | 连续三天且至少五十个真实运行的灰度、生产 SLO；管理员控制面已被当前产品边界取代 |
| 嵌入式桌面陪伴助手 | [独立设备身份与可靠接入协议](api/15-devices.md) | 设备端实现、摄像头与音频兼容、数字人、性能、温升、离线存储和隐私实测；不宣称整机完成 |
| Android 游戏化首页 | 历史客户端设计，当前仅保留经典首页；本轮不恢复或修改客户端 | 如后续重新立项，应先更新产品范围和客户端契约 |
| 端侧识别链路交接 | [模型资产与客户端链路](on-device-recognition-pipeline.md)；后端只接收结构化观察 | 本轮未重新核验客户端或模型资产，旧交接文档中的资产与端侧现状须在后续开发时复核 |

设备接入和新增学习偏好接口已提供后端协议；Web、Android、HarmonyOS、微信小程序及硬件客户端本轮未适配，不能将后端验收表述为全端完成。

后续 Web 前端开发从 [接口文档总目录](api/README.md) 开始，包含所有已注册 CampusMate 接口、模块契约、请求与响应字段、鉴权、错误、流式协议、异步流程及 Web 调用对照。

- [接口接入与功能流程](api/integration.md)
- [六层世界模型：后端完成情况与接口接入](world-model-backend.md)
- [OpenAPI JSON](api/openapi.json)
- [独立学习空间 API](api/learning-space.md)
- [课程互动课堂与受管工作台 API](api/14-magicclass.md)

## 端侧 AI 能力（行为识别 / 表情识别）

行为识别（可见学习行为观察）与表情识别在设备本地推理，画面不上传服务器；后端不加载任何推理运行时，也不含模型权重文件，只接收端侧算好的结构化信号。因此基于后端已注册路由整理的 `api/` 手册里没有这两项能力的推理接口（该手册只覆盖 `ExpressionSignal` 透传与表情样本共建），也未查看 Android、HarmonyOS 与微信小程序。实现说明在端侧交接文档、`ml/` 与各端 README：

- 端侧识别链路交接（模型清单与哈希、数据流、类别与校准契约、各端现状、源码入口索引、回退语义、重写检查清单）：[端侧识别链路](on-device-recognition-pipeline.md)
- 训练、评估与导出：[行为识别](../ml/behavior_recognition/README.md)、[表情识别](../ml/expression_recognition/README.md)
- Android（CameraX + ML Kit + LiteRT / ONNX Runtime，Mock/Real 双实现与隐私边界）：[android/README.md](../android/README.md) 的“表情识别”与“本地行为识别演进与学习状态辅助”章节
- HarmonyOS（MindSpore Lite 本地模型）：[harmony/README.md](../harmony/README.md) 的“本地表情与学习行为识别”章节
- 微信小程序（本机 `createInferenceSession` 跑 ONNX：无人脸检测、模型不随包分发、需用户配置 HTTPS 下载地址，真机验证未完成）：[wx/README.md](../wx/README.md) 与 [端侧识别链路 §6.1](on-device-recognition-pipeline.md)
- Web（`webreact/`）：表情与行为识别零实现；`package-lock.json` 中的 `@mediapipe/tasks-vision` 只是 `@react-three/drei` 的传递依赖，不代表 Web 已具备检测能力。补齐路线见 [端侧识别链路 §6.2](on-device-recognition-pipeline.md)

接口层面只覆盖后端契约：`ExpressionSignal` 透传（[AI 助手](api/10-assistant-knowledge.md)、[学习陪伴](api/05-study.md)）与表情样本共建接口（[AI 助手](api/10-assistant-knowledge.md)）；后端不做 CNN 表情推理，该字段标注为“仅透传存储”。两条消费路径语义不同——对话路径只用于调整措辞、不入库，会话路径才把 `expression_signal` / `behavior_summary` 存入 `study_sessions`，细节见 [端侧识别链路 §4.3](on-device-recognition-pipeline.md)。
