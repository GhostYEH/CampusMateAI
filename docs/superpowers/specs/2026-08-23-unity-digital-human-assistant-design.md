# CampusMate AI Unity 数字人接入设计

## 目标

在现有 CampusMate AI Web 校园助手中嵌入 Rusk Unity 数字人。校园问答继续由 DeepSeek 生成；回答完成后由 Xiaomi MiMo V2.5 TTS 使用“冰糖”音色流式合成语音。数字人随语音驱动口型，并通过低幅度头颈动作、眨眼和视线变化提升自然感。

## 范围

- CampusMate AI 后端：DeepSeek 配置、MiMo TTS 客户端、鉴权接口、错误降级和测试。
- CampusMate AI Web：Unity WebGL 容器、TTS 播放、Unity 消息桥接、交互和响应式布局。
- Unity 数字人项目：外部语音电平输入、头颈程序化动作、WebGL JavaScript 桥接、测试和 WebGL 构建。
- 不引入语音识别、动作捕捉、情绪分类或新的 3D 模型。

## 架构

### DeepSeek 问答

沿用现有 FastAPI `OpenAICompatibleClient` 与校园 RAG 流程。运行时配置使用：

- `LLM_PROVIDER=openai_compatible`
- `LLM_BASE_URL=https://api.deepseek.com`
- `LLM_MODEL=deepseek-v4-flash`
- 非思考模式用于校园助手，降低首字延迟并避免把推理过程交给前端。

DeepSeek 密钥只从后端未跟踪的 `.env` 或进程环境读取。

### MiMo TTS

新增独立的 MiMo TTS 客户端，不复用 DeepSeek 客户端配置：

- Base URL：`https://api.xiaomimimo.com/v1`
- Model：`mimo-v2.5-tts`
- Voice：`冰糖`
- Format：`pcm16`
- Sample rate：24000 Hz、单声道、PCM16LE

目标播报文本放在 `assistant` 消息中；可选的播报风格放在 `user` 消息中。后端解析 MiMo SSE 中的 Base64 音频块，并以原始 PCM 字节流返回浏览器。

新增受鉴权保护的 `POST /api/v1/assistant/tts` 接口。请求包含待播报文本，后端限制字符数、拒绝空文本，并移除 Markdown 链接标记、代码围栏和不适合朗读的格式。响应使用分块流，并通过响应头返回采样率、声道数和音频格式。

### Web 音频与 Unity 桥接

校园助手保持现有 SSE 文字流。收到最终回答后：

1. 前端将最终回答转换为适合朗读的纯文本。
2. 调用 TTS 流接口。
3. 使用 Web Audio API 按顺序调度 PCM16 音频块，避免块间断音。
4. 从播放数据计算平滑 RMS 电平，并调用 Unity `SendMessage` 更新说话强度。
5. 播放开始和结束时分别通知 Unity 进入或退出说话状态。

用户可关闭自动朗读、立即停止当前语音或重新朗读。浏览器自动播放策略阻止音频时，界面显示明确的“点击播放”操作，不丢失文字回答。

### Unity 数字人

现有 `RuskDigitalHuman` 保留自动定位面部 Renderer、五组口型 BlendShape 和自动眨眼。扩展为同时支持：

- 编辑器/桌面测试：继续从 `AudioSource` 读取电平。
- WebGL 嵌入：接收浏览器传入的归一化语音电平。
- 外部说话状态：在无音频块的短暂间隙内保持自然动作，结束后平滑回到待机。

新增独立的程序化头部动作组件。它缓存 Head 和 Neck 的初始局部旋转，在 `LateUpdate` 中叠加平滑、受限的旋转：

- 待机：低频轻微 yaw/pitch/roll 漂移和呼吸感。
- 说话：随平滑语音强度产生轻微点头与重音响应。
- 偶发动作：间隔随机但受控的视线/头部微偏移。
- 退出说话：平滑回到待机轨迹，不瞬间归零。

动作幅度保持克制：头部总偏转不超过约 4 度，颈部不超过约 2 度，点头峰值不超过约 1.5 度。所有参数可在 Inspector 调整，运行时不得积累旋转漂移。

### 页面布局

桌面端将数字人放在校园助手右侧栏的专属卡片中，替代现有静态助手插图区域，并提供展开查看。Unity Canvas 使用透明背景，与现有浅色卡片融合。

窄屏下数字人卡片折叠为可打开的抽屉/浮层，不挤压聊天正文。Unity 未加载或 WebGL 不可用时，保留静态 CampusMate AI 卡片作为降级内容。

## 安全与隐私

- DeepSeek 与 MiMo 使用不同环境变量；真实密钥不进入代码、场景、WebGL 构建或 Git。
- 后端日志不记录 Authorization、API Key、Base64 音频或完整 TTS 请求正文。
- TTS 接口复用现有用户鉴权并设置文本长度上限，避免被匿名滥用。
- 前端只访问 CampusMate 后端，不直接访问 DeepSeek 或 MiMo。
- `.env.example` 只包含占位符。

## 错误处理

- DeepSeek 不可用：沿用现有检索摘要降级。
- MiMo 不可用、超时或返回异常：停止本轮朗读并展示非阻塞提示，文字回答不受影响。
- 流中断：停止剩余音频、释放 AudioContext 调度资源并通知 Unity 退出说话状态。
- Unity 加载失败：显示静态助手卡片；聊天和 TTS 控件仍可工作。
- 页面切换或发起新问题：取消上一轮 TTS，避免多段语音重叠。

## 测试与验收

### 后端

- 先写失败测试，验证 MiMo 请求的模型、`assistant` 文本、`pcm16` 和“冰糖”音色。
- 验证 MiMo SSE/Base64 音频解析、上游错误、超时、空文本和长度限制。
- 验证响应头、鉴权和日志/错误信息不泄露密钥。
- 验证 DeepSeek 使用当前模型配置，现有 RAG 测试继续通过。

### Web

- 测试 PCM16 转换、顺序播放、停止/取消、RMS 平滑和 Unity 消息桥接。
- 测试回答完成后自动朗读、静音设置持久化、自动播放受限与 Unity 加载失败降级。
- 运行现有 Web 单元测试、构建与目标页面浏览器检查。

### Unity

- EditMode 测试验证外部语音电平夹取与口型权重。
- PlayMode/EditMode 测试验证 Head/Neck 最大幅度、平滑回正和无旋转漂移。
- 检查 Unity 编译控制台无错误，运行场景验证眨眼、口型和头部动作。
- 构建 WebGL，并在 CampusMate 页面中验证加载、透明背景、消息桥接和音画同步。

## 完成标准

- 校园助手真实使用 DeepSeek V4 Flash 回答。
- 每次完整回答可用 MiMo V2.5 TTS“冰糖”音色播放。
- Rusk 在播放时嘴型随音量变化，Head/Neck 有自然、克制的待机与说话动作。
- 用户可静音、停止和重新朗读，不出现语音重叠。
- Unity WebGL 在页面内正常显示；失败时聊天仍完整可用。
- 两枚密钥均未出现在 Git diff、构建产物或日志中。
