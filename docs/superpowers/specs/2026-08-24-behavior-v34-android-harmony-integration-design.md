# CampusMateAI V3.4 行为识别 Android/Harmony 双端接入设计

## 目标

将已训练并通过离线对比的 V3.4 四分类行为模型接入 Android 与 HarmonyOS 专注学习链路。Android 默认启用 V3.4，初始化失败时自动回退 V3.2；HarmonyOS 使用 MindSpore Lite 版本的同一模型并保持相同输出、拒识和提醒语义。真机验证不在本轮范围内。

## 模型契约

- 输入：RGB、NCHW、`[1, 3, 224, 224]`、float32、ImageNet mean/std。
- V3.4 输出：`READ`、`WRITE`、`PHONE_INTERACTION`、`NO_VISIBLE_STUDY` 四个 logits。
- 温度：`4.841172366232762`。
- 接受条件：最高概率至少 `0.30` 且最高、次高概率差至少 `0.05`。
- 不满足接受条件时输出 `UNCERTAIN`，不触发行为提醒。
- V3.2 回退契约保持 `IDLE`、`VISIBLE_STUDY` 二分类不变。

## ROI 数据流

V3.4 是基于学生检测框裁剪训练的，双端不得直接把全画面作为 V3.4 输入。

Android 复用 `PersonAnalyzer` 的最高置信度人体框。检测框和行为分析都消费 CameraX 已转正、已前摄镜像的同一 Bitmap，因此框坐标直接裁剪；裁剪前按 10% 比例扩边并限制在图像边界内。检测框暂不可用时不运行 V3.4，而是使用 V3.2 全画面回退，以避免输入域错配。

HarmonyOS provider 接收已经与预览方向对齐的 PixelMap 和人体框；使用相同扩边与裁剪规则。摄像头帧采集/人体检测若当前设备能力不可用，provider 必须报告 `UNAVAILABLE`，不得使用全画面伪装 ROI 推理。

## Android 架构

1. 将 V3.4 ONNX 打包至 `assets/models/behavior/`。
2. 把模型规格、输出解码和拒识规则拆为纯 Kotlin 单元，便于无设备测试。
3. `OnnxBehaviorRecognitionEngine` 优先初始化 V3.4，会校验输入/输出形状；失败后关闭半初始化资源并加载 V3.2。
4. `BehaviorAnalyzer` 接收最新人体框快照，V3.4 使用 ROI，V3.2 保持全画面。
5. V3.4 概率映射到现有 `StudyBehavior.READING`、`WRITING`、`PHONE_USE`、`IDLE`，拒识结果保留概率但将稳定行为标为 `UNCERTAIN`。
6. `BehaviorSignalProcessor` 接受 V3.4 ready state；持续手机交互 3 秒触发 `PHONE_DISTRACTION`，持续 `IDLE` 20 秒触发可恢复的分心事件，阅读/书写恢复后发出 `FOCUS_RECOVERED`。
7. `ExpressionSessionManager` 分别维护表情提醒与行为提醒，UI 展示时选择当前有效提醒，任一链路不得清除另一链路状态。

## HarmonyOS 架构

1. 用官方 MindSpore Lite converter 将 V3.4 ONNX 转为 `.ms`，记录源/目标 SHA-256 和转换命令。
2. 扩展 `FocusAssistProvider` 的强类型信号，标签与 Android 完全一致。
3. 新增纯 ArkTS `BehaviorV34Decision`，负责 softmax、温度、拒识和 3 秒/20 秒提醒状态机；该单元不依赖设备 API并接受单元测试。
4. 新增 MindSpore Lite provider，加载 rawfile 中的 `.ms`，校验 `[1,3,224,224]` 和四输出，执行 ROI 预处理与推理。
5. provider 或相机/人体检测能力不可用时，返回明确的 `UNAVAILABLE`/`ERROR` 与说明；不生成虚假预测。
6. `FocusPage` 展示 provider 状态、稳定行为和温和提醒；画面仅本地处理，不上传。

## 提醒语义

- `PHONE_INTERACTION` 是可观察到的手机交互，不等价于主观上“不认真”。连续 3 秒后提示用户检查当前任务。
- `NO_VISIBLE_STUDY` 连续 20 秒后提示用户把注意力拉回当前学习任务。
- `READ`/`WRITE` 恢复后清除行为提醒。
- `UNCERTAIN` 不启动、不中断计时，只表示当前证据不足。
- 提醒是辅助观察，不用于惩罚、评分或高风险自动决策。

## 错误处理与回退

- Android：V3.4 资源缺失、模型加载、契约校验或初始化失败时自动回退 V3.2；单帧 V3.4 推理失败只返回 `INFERENCE_ERROR`，不在运行中静默切换模型。
- HarmonyOS：模型转换失败、算子不支持、MindSpore Lite 初始化失败或相机/人体框不可用时显式不可用，不声称识别成功。
- 所有缓存模型使用版本化文件名，避免旧缓存覆盖新资源。

## 验证

- Android JVM tests：输出映射、温度 softmax、拒识、ROI 边界、提醒/恢复、V3.2 回退选择。
- Android：使用项目捆绑 JDK 21 运行相关单测、`assembleDebug`，检查 APK 同时包含 V3.4 与 V3.2 模型。
- HarmonyOS：ArkTS 单测覆盖判定和提醒状态机，运行 Hvigor test/build；检查 HAP 包含 `.ms` 模型。
- PC 侧对同一随机输入比较 ONNX 与 MindSpore Lite 输出，记录最大绝对误差；若转换工具缺乏 benchmark 能力，至少验证模型结构、输入输出和成功加载。
- 本轮不声明真机准确率、时延、功耗或温升通过。

