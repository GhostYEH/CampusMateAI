# CampusMate AI — Android 移动端

CampusMate AI 的原生 Android 客户端，面向个人学习、消息整理和日常事务。AI 对话的产品定位是通用助手；当前后端聊天接口仍保留历史知识库检索，见[主 README](../README.md)。

## 技术栈

- **Kotlin** + **Jetpack Compose**(Material 3)
- **Navigation Compose** 路由
- **Retrofit** + **Moshi** + **OkHttp** 网络(Mock/Real 双模式)
- **DataStore Preferences** 本地持久化
- **CameraX** + **ML Kit** 人脸检测 + **LiteRT** 表情分类
- **Media3 ExoPlayer** 视频背景
- **Kotlin Coroutines + Flow** 异步

## 项目结构

```
app/src/main/java/com/example/campusai/
├── data/
│   ├── expression/          # 表情识别模块(CameraX + ML Kit + LiteRT, Mock/Real 双实现)
│   ├── focus/               # 专注状态处理
│   ├── local/               # DataStore 本地持久化
│   ├── model/               # 数据模型(User/Notice/Task/Course/ChatMessage/ext.)
│   ├── remote/              # Retrofit API 客户端与服务接口
│   └── repository/          # Repository 层(统一数据入口, Mock/Real 可切换)
├── ui/
│   ├── components/          # 通用组件与动效(EnterAnimation/CampusVideoBackground/ext.)
│   ├── navigation/          # AppNavHost(Navigation Compose 路由图)
│   ├── screens/             # 业务页面
│   ├── strings/             # 字符串资源
│   └── theme/               # Material 3 主题(Color/Type/Motion)
└── MainActivity.kt          # 入口 Activity
```

## 业务页面

| 模块 | 路径 |
|------|------|
| 仪表盘 | `ui/screens/dashboard/` |
| 登录 | `ui/screens/login/` |
| 通知 | `ui/screens/notifications/` |
| 待办任务 | `ui/screens/tasks/` |
| AI 助手 | `ui/screens/counselor/` |
| 专注自习 | `ui/screens/focus/` |
| 课程 | `ui/screens/courses/` |
| 考试 | `ui/screens/exams/` |
| 个人中心 | `ui/screens/profile/` |
| 设置 | `ui/screens/profile/SettingsScreen.kt` |

## 通知整理与学习通

用户在系统设置中授权通知访问后，`data/notification/CampusNotificationListenerService.kt` 接收**系统通知栏实际展示**的消息。当前识别微信、企业微信、QQ/TIM、学习通；微信、企业微信和 QQ 群聊分别使用来源开关与群名白名单，普通闲聊会被过滤。捕获结果进入 Room 本地队列，WorkManager 批量上传到后端分类、去重，并从可执行通知中生成待办。通知页面也提供手动粘贴提取入口。这不读取聊天记录或任何应用私有数据库。

学习通还有独立的账号连接与同步链路：后端同步课程、课程通知、作业和考试；Android 可定期触发同步，并提示登录态失效或需重新验证。学习通系统通知监听只是辅助来源，不等同于账号同步。

图书馆入口使用这条账号链路，只展示 `provider=chaoxing` 的真实课程。学生可在图书馆连接或同步学习通，再打开课程查看已同步的资料、知识点和互动课堂，并把课程或知识点作为目标带入自习室。结束时填写的学习感受会显示在总结、专注记录及相应课程的学习足迹中。自习室提供安静专注、AI 陪伴和摄像头专注三种可选方式；摄像头方式在进入专注后申请权限，本机观察结果仍需后续校准。

## 互动课堂接入

Android 在图书馆进入课程资料与课程经典课堂，在课堂大厅选择自定义主题、上传个人资料并生成课堂。课程接口保留状态、计划、生成、进度、历史、重试和内容组成。自主选题的资料、生成、进度和历史使用 [`/self-classroom` 接口](../docs/api/14-magicclass.md#self-classroom)。课程已提取的个人上传资料可用于生成上下文，自定义资料按当前学生隔离，不混用其他课程资料。

课程经典、自主选题和受管工作台已接入原生播放入口，设备验证见[原生课堂审计](../docs/android-native-classroom-audit.md)。调试可使用[脱敏课堂联调服务器](../docs/api/integration.md#脱敏联调服务器真实上游不可用时)验证媒体和作答。

原生舞台适用于新旧课件。适合立体观察的新实验通过[结构化三维模型](../docs/api/response-contracts.md#三维实验配置)接入原生旋转、缩放和对象动画。普通数值实验通过[参数实验配置](../docs/api/response-contracts.md#普通参数实验配置)使用原生滑块、实时结果、预设、曲线和老师的参数演示。已有 ε–δ 实验保留二维曲线与三维时间轨迹。需要网页专用控件的实验根据播放计划切换运行时。

仍需网页的课堂操作可从应用内 [ClassroomViewer](app/src/main/java/com/example/campusai/ui/screens/courses/ClassroomViewer.kt) 打开。地址和跳转须通过 [ClassroomUrlPolicy](app/src/main/java/com/example/campusai/data/remote/ClassroomUrlPolicy.kt) 校验。正式构建要求公开 HTTPS 与可信 Origin 精确匹配，调试例外限代码规定的本地课堂入口。经典播放使用 `session_id` 与 `classroom_id`，受管工作台通过 `workspace_id`、`stage_id` 和 `scene_id` 读取场景。编辑在有权限的工作台完成，独立课堂应用使用自身的认证。共同课堂的课件共享与通话能力另见下文。

课堂内的 AI 同学沿用上游 `ClassmatePanes`（小圆/阿拓/小满/阿哲的换页发言、沉默、点名与预算）；`ClassroomViewer` 另注入 `assets/classroom-rewards.js`（与 iOS 共用同一份脚本），规则与 Android 原生 `ClassroomRewardsEngine` 对齐：首次访问页面 +12 XP、首次交卷按答对题数 ×6、满分 +20、连击从第二份起 +12、重做按场景去重、成就 ID 与原生一致。网页账本 key 由「服务 + 账号 + 课堂地址」派生，不再使用不带账号信息的固定 key；旧 `campusmate:classroom-rewards:v1` 只在面板注明“未绑定账号、未并入”，不迁移也不删除。只有页面提供稳定的 `data-scene-id` 才记账，匹配不到稳定场景时 HUD 明确显示未计入进度，而不是按标题猜测。

原生播放器现在有明确的播放会话：经典、自主选题、受管课堂和作业复习入口共用同一套生命周期；关闭弹窗、退出页面、换号或 ViewModel 清理时先按原账号落盘学习位置、奖励与待保存草稿，再释放 ExoPlayer、TTS、会话图片缓存与媒体监听并取消任务。旋转不会结束会话，当前页、缩放和草稿保持不变；关闭后重开同一课堂会创建新的播放器与缓存。`ClassroomViewer` 在实际加载、导航和麦克风授权前会独立校验调用方提供的可信 Origin，发布版仍只接受公开 HTTPS，调试版保留 `10.0.2.2`/`127.0.0.1:3000` 的课堂入口。

### 课堂观察（互动课堂原生播放态）

互动课堂原生播放器底部、页码栏上方有「课堂观察」开关，默认关闭；学生点击「开启课堂观察」后才申请 `CAMERA` 并启用前置 CameraX。它不申请音频、不展示预览、不改变课堂接口，也不读取或上传原始画面。本节的入口只属于互动课堂原生播放器；「同学一起学」的 `LearningRoomScreen` / 共同课堂专注监督仍走原有链路，本次没有合并两套状态。

- 采样：CameraX `ImageAnalysis` 约 4 次/秒，ML Kit 快速模式返回人脸数量、头部 yaw/pitch；Y 平面平均亮度用于弱光判断。每个观察会话只绑定一条分析链，关闭时解绑。
- 窗口：以 `SystemClock.elapsedRealtime()` 聚合 10 秒非重叠窗口，记录有效采样数、无效采样数、人脸可见比例、yaw/pitch 均值/标准差/最小/最大与样本数、可获得课堂阶段（当前页类型或讲解态），以及学生主动翻页、交卷、提问的事件计数。每个窗口只取截止时点及之前的事件；自动翻页、重放事件和全局触摸移动不进入计数。
- 状态与原因：无脸、多脸、弱光、相机占用、采样中断、视频冻结、检测失败、权限拒绝或启动失败时，观察条显示「无法判断」并给出具体原因。连续 2 秒检测到人脸才确认；确认后连续 12 秒有效画面缺脸才转为无法判断；单帧漏检不改变状态。
- 第一阶段边界：观察条只呈现可观察事实，推理流程静默运行，不输出专注度、分心、学习效果结论。低头、转头、安静听课和暂时没有操作都不是分心判据，必须结合当前课堂任务解释；双人标注、按学生留出验证通过后再接入逻辑回归权重和面向学生的离题提醒，论文 benchmark 数字只作研究对照。
- Debug 复盘：仅 `BuildConfig.DEBUG` 且观察已开启、已有窗口时显示「导出CSV / 导出JSON」。文件落在应用私有 cache，由测试者主动通过系统分享面板导出；内容只有会话内相对时间、窗口数值统计、事件计数和不可观察原因，不含课堂标题、账号、设备标识、人脸特征或原始帧。日常运行的摄像帧只在本机内存处理。
- 生命周期：关闭观察、切到后台、离开播放器、换课或旋转重建时解绑 CameraX、关闭 ML Kit、取消看门狗并清空窗口；异步 ML Kit 回调带会话代次，关闭后重开的旧会话不能写入新窗口。权限对话框期间的旋转由 `rememberSaveable` 保留请求标记；取消开启后迟到的授权结果不会启动相机。旋转会重建播放器并停止观察，需要学生重新开启。
- 代码：纯规则/窗口/导出在 `data/classroom/focus/ClassroomFocusObservationModel.kt` 与 `ClassroomObservationDebugExport.kt`；相机适配在 `ClassroomFocusObservationController.kt`；事件总线在 `ClassroomFocusActivityBus.kt`；UI 在 `ui/screens/courses/nativeplayer/ClassroomFocusObservationBar.kt`。单测覆盖 10 秒边界、截止后事件、无效画面、自动/手动翻页、关闭重开与旧会话回调。本轮只完成 JVM 单测与 `assembleDebug` 编译验证，真机权限、前后台、旋转和播放流畅度仍需按验收清单实测，不能把编译或纯规则测试表述为真机通过。

### 多人共同课堂

“课程 → 同学一起学”进入原生课堂列表，支持创建讨论课堂、显示/复制本人 UID、发起人邀请、接受/拒绝邀请、课堂文字讨论和最多 8 人的 RTC 音视频。可加入已有 Web 课件课堂的通话；Android 目前显示共享页码与发起人翻页按钮，完整课件内容仍需 Web 学习空间。实现见 `data/remote/LearningRoomApi.kt`、`data/classroom/ClassroomCall.kt` 和 `ui/screens/classroom/`。

课堂内提供专注监督：进入课堂后每 15 秒同步一次粗粒度在线心跳；用户可选开启摄像头端侧观察，只上报“专注/可能分心/明显分心/离开”，不上传画面、人脸或音频；发起人可查看成员状态并发送老师提醒，学生端在麦克风关闭时用系统 TTS 朗读私人提醒，避免经 RTC 传给其他同学。共同课堂仍无多人同步计时或历史专注记录。消息发送结果不确定时，页面保留原消息及幂等 ID，允许重试或确认放弃；这份待重试状态目前只保存在页面 ViewModel 内存中，应用进程结束后不能恢复。返回课堂列表后重新进入同一课堂仍可重试；登录凭证变化（包括自动刷新）会断开通话并清除待重试状态，应先检查消息记录再重发。客户端只显示最近 300 条已拉取消息，服务端增量分页不受该本地展示上限影响。

后端必须配置 `VOLC_RTC_APP_ID`、`VOLC_RTC_APP_KEY` 并开通火山 RTC；客户端仅领取短期 Token，不包含 AppKey。按[音视频协议](../docs/api/14-magicclass.md#classroom-rtc)接入。默认入会关闭麦克风/摄像头，分别授权后开启；拒绝一项权限仍可使用另一项。后台通过可见通知的前台服务保持语音、停止摄像头，返回前台需手动重新开摄像头；通知可直接断开通话。Token 每 60 秒续期，到期前提醒也会触发续期，网络失败有界退避，到期停止通话。

RTC 锁定版本为 `3.60.104.300`，通过 typed `RTCEngine` / `RTCRoom` API 接入，使用实际入会回调、远端发布回调与视频渲染。视频发送 360p/15fps，远端小画面订阅 180p/15fps、弱网回退音频；画面关闭会停止采集和发布。用户离开列表不等于退出成员关系；“结束共同课堂”会结束所有成员的课堂，操作前有确认。服务端离开后的已有凭证最长剩余 120 秒，详见后端文档。

服务启动及 microphone 类型升级必须收到前台服务就绪确认才继续；服务归属按通话页面隔离，旧页面的关闭/销毁不能误停新通话。房间成功回调是初次入会及重连成功的唯一依据，网络恢复本身不显示“通话中”；重连时仍可立即关闭现有采集。权限回调同时检查课堂 ID 和本次通话代次，避免旧授权结果开启新通话的设备。Token 另有基于单调时钟的到期看门狗；超时和终态取消所有续期/开麦任务。视频画布只在视图或流改变时绑定，避免 RTT 更新触发重复重绑。

`ClassroomServiceLeaseTest` 与 `ClassroomConnectionTrackerTest` 覆盖服务归属、旧回调、就绪通知和入会/重连状态规则；这些 JVM 测试仍须在指定 JDK 环境运行，不将语法解析或后端测试计作安卓测试通过。

本次未完成真机验收。Android 编译必须使用下文指定的本地 JDK；缺失时停止 JVM 操作。发布前验证两台及八台真机互通、前后台/锁屏、权限拒绝、切网重连、连续续期与回声/丢包；界面显示的 RTT 只是网络往返，不能作为端到端低延迟结论。

后续接入以 [课程侧 API](../docs/api/14-magicclass.md)、[独立学习空间 API](../docs/api/learning-space.md) 和 [接口流程](../docs/api/integration.md) 为准。课程侧复用本站登录态与课程权限校验，不直接调用受管服务的 `/internal/*`。先读取状态、资料和历史，再实现生成、异步进度、播放与写入；提供方可用性、浏览器打开条件和实际内容组成须分别确认。上述说明来自源码核对，不代表真机或真实提供方验收。

## 语音输入

CPM 与共同课堂文字输入框复用 `SpeechInputButton`，将单声道 16kHz PCM16 WAV 上传到后端 `POST /assistant/asr`，识别结果追加到当前草稿；CPM 在识别等待期间输入的新文字也会保留。该能力由后端 SenseVoice 推理，与自习室系统语音识别和 RTC 通话分别管理。

录音最多 60 秒，按 PCM 帧数截断，达到上限自动释放麦克风并提交识别；正在录音时，即使页面正在发送消息也能手动结束。录音初始化、停止等待与文件清理在后台线程执行。应用进入后台或离开组件时取消录音/识别并清理临时文件；旧请求不再回填，重新进入后需重新录制。ASR 使用独立的 60 秒读取、75 秒总请求超时，保留原有鉴权与 Token 刷新；空文本提示重说，服务繁忙提示稍后重试。

回归测试覆盖 CPM 草稿编辑/回复期间的识别回填，以及录音上限与资源释放。JVM 测试须使用下文指定的本地 JDK；模拟器与真机的权限拒绝、锁屏/后台、录满 60 秒及 RTC 同时使用麦克风仍需验收。接口约定见[语音输入契约](../docs/api/10-assistant-knowledge.md#post-apiv1assistantasr)。

## 构建配置

| 配置 | 值 |
|------|-----|
| compileSdk | 35 |
| minSdk | 28 |
| targetSdk | 34 |
| JVM Target | 17 |
| Compose BOM | 2024.04.01 |
| 默认 API 地址 | `http://10.0.2.2:8000/api/v1/` |

### 构建命令

Gradle/JVM 命令使用开发机已安装的 JDK 21。优先使用 `JAVA_HOME` 指向的 JDK；未设置时使用系统 `java`。执行前确认 `java -version` 为 21.x，并确保 `JAVA_HOME` 与 `PATH` 指向同一套 JDK：

```powershell
if (-not $env:JAVA_HOME) { throw '未设置 JAVA_HOME，请指向本机 JDK 21' }
$java = Join-Path $env:JAVA_HOME 'bin\java.exe'
if (-not (Test-Path -LiteralPath $java)) { throw 'JAVA_HOME 下找不到 java.exe' }
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
& $java -version
```

```powershell
Set-Location (Join-Path $repoRoot 'android')
.\gradlew.bat :app:assembleDebug

# 真机调试时按本机网络环境传入后端地址
.\gradlew.bat :app:assembleDebug -PAPI_BASE_URL=http://<LAN_IP>:8000/api/v1/
```

## 表情识别

专注自习页面已接入 CameraX + ML Kit 本机人脸检测 + LiteRT 表情分类，保留 Mock/Real 双模式。

- 模型文件: `app/src/main/assets/expression_model.tflite`
- 实现: `data/expression/` (含 `RealExpressionRecognitionService` / `MockExpressionRecognitionService`)
- 隐私: 画面不保存、不上传、不写日志，仅在用户主动授权且专注计时运行中分析
- 详见主 README 的"CNN 面部表情识别"章节

联合模型按固定顺序输出七类表情和 `boredom/confusion/frustration` 三项原始 logits。
七类单独使用温度校准 softmax；新增状态分别使用 sigmoid，可以同时出现，十项不合计为 100%。
界面展示各项置信度，置信度不能解释为准确率。学习状态只在同一追踪人脸积累四帧后显示，
先平均状态 logits，再应用 validation 拟合的校准参数；人脸变化、无脸、质量不合格和暂停时清空。
四帧实时滑动窗口与 DAiSEE 均匀采样视频帧的分布不同，仍需前摄实机评估。
聊天继续使用通过原七类稳定性和置信度门槛的表情信号。

## Focus 架构与生命周期

`ExpressionSessionManager` 是 Activity-owned 的专注会话协调器。表情识别与行为识别共用一条 `FocusCameraPipeline`，不为行为识别启动第二个摄像头。CameraX 只有在“辅助开启 + 摄像头权限 + 计时运行 + 页面可见 + App 在前台”且模式为 `FOCUS` 时运行；暂停、离开页面或生命周期结束时会解绑/暂停 camera use case。共同课堂复用同一条相机与模型链路，但使用独立的课堂门槛，且不会与专注页同时运行。

专注页会把端侧已有行为/在席/表情观察翻译成“小伴老师”提醒：异常需持续数秒才出现，同类 3 分钟冷却、全局 45 秒冷却、每堂最多 8 次；恢复学习后给一次表扬。`SMART_GUARD` 模式下默认用系统 TTS 朗读，提醒卡也可关闭语音。该提醒只描述可观察行为，不作为专注度评分、心理判断或学习效果结论。

`attachLifecycle` / `detachLifecycle` 与 `attachPreview` / `detachPreview` 分别管理生命周期和预览；`release()` 会取消结果、状态和行为 collector jobs，解绑并释放 CameraX pipeline、行为 analyzer、表情服务和模型资源。

### 沉浸式场景专注

专注执行页默认进入“雨夜自习室”，并可切换“静谧图书馆”和“林间晨读”。三套竖屏背景与对应的循环环境声均为项目原创资产；场景选择、环境声开关和音量会保存在本机。

- 机器人位于独立的稳定前景层，场景切换只淡化背景，不会重建或打断机器人、语音状态动画。
- 环境声默认关闭；开启后仅在专注计时运行且 App 位于前台时播放，暂停或进入后台会柔和静音。
- AI 聆听、思考或回答时，环境声会自动降低，避免遮盖对话。
- 计时器、场景控制和学习观察使用自适应液态玻璃面板；低版本 Android 自动退化为轻量半透明面板。

## 本地行为识别演进与学习状态辅助

行为识别是设备端辅助观察，不是专注度、心理状态或学习效果判断。当前模型演进如下：

| 版本 | 输出类别 | 模型 | 用途 |
|------|----------|------|------|
| V1 | `READING` / `WRITING` | `assets/models/behavior/rgb_resnet18.onnx` | 研究基线，识别阅读与书写 |
| V2 | `READING` / `WRITING` / `PHONE_USE` | `assets/models/behavior/rgb_resnet18_v2.onnx` | 扩展手机使用类别，保留回滚路径 |
| V3.2 | `IDLE` / `VISIBLE_STUDY` | `assets/models/behavior/campusmate_visible_study_v32.onnx` | 无人物 ROI 或 V3.4 不可用时的安全回退 |
| V3.4 | `READING` / `WRITING` / `PHONE_USE` / `IDLE` | `assets/models/behavior/campusmate_behavior_v34.onnx` | 当前单帧主模型，在人物 ROI 上运行 |
| V4 TSM | 上述类别 + `COMPUTER` | `assets/models/behavior/campusmate_tsm_mobilenetv2_v4.onnx` | 8 帧低频时序确认，与 V3.4 融合 |

当前默认使用 V3.4 单帧模型与 V4 TSM 时序模型的混合链路。历史 ONNX 文件都保留，因为目前是科研/开发阶段，需要比较模型演进、保证实验可复现并提供 V3.2 回退。

### V1.1 工程优化

V1.1 延续 V1 的 READ/WRITE 语义，但完善了共享 CameraX pipeline、异步单线程推理、16 帧滑动窗口、推理 busy 时不重复调度、Bitmap ownership/recycle 和 Focus 生命周期释放。UI 主线程只消费 Flow 结果，不执行 ONNX 推理。

### V3.4 + V4 产品语义与数据流

V3.4 对最新采样图片识别 `READING`、`WRITING`、`PHONE_USE` 和 `IDLE`。V4 TSM 从连续相机流中保留最近 8 张采样图片，仅在低置信度、类别变化、手机交互或周期确认时运行，并补充 `COMPUTER` 时序类别。

当人物 ROI 暂时不可用或 V3.4 加载失败时，系统回退到 V3.2 二分类。V3.2 的 `IDLE / VISIBLE_STUDY` 与 V4 标签空间不兼容，因此回退结果不会参与 TSM 融合，并会清空此前的时序证据。

数据流为：

```
CameraX
→ FocusCameraPipeline / CameraFrame
→ BehaviorAnalyzer（400 ms 采样与单线程推理调度）
→ HybridBehaviorRecognitionEngine
   ├─ OnnxBehaviorRecognitionEngine（V3.4 单帧；必要时回退 V3.2）
   └─ OnnxTsmBehaviorRecognitionEngine（最近 8 帧、按条件低频运行）
→ BehaviorHybridPolicy（仅融合标签兼容的 V3.4 + V4 输出）
→ BehaviorPredictionTemporalSmoother（EMA 概率平滑）
→ BehaviorSignalProcessor（启动观察、稳定判定）
→ LearningContinuityStateMachine（会话级连续性）
→ BehaviorObservationHistory（最近 5 分钟节奏统计）
→ FocusScreen（学习状态、节奏与本次观察摘要）
```

稳定结果会映射为 `OBSERVING`、`STUDYING`、`THINKING_OR_ADJUSTING` 和 `PAUSED`。学习中短暂出现 `IDLE` 时，前 8 秒仍保留学习状态，8～20 秒显示“短暂思考或调整中”，超过 20 秒才进入“暂时停顿”。`BehaviorSignalProcessor` 负责观察期、时间窗和稳定判定；`LearningContinuityStateMachine` 只改变产品层连续性，不改变底层模型标签。

`BehaviorObservationHistory` 是当前 Focus session 的内存历史，按最近 5 分钟裁剪统计学习、暂停、最长连续学习和 meaningful switch；`FocusScreen` 通过 `behaviorObservation` Flow 显示学习节奏卡片和本次观察摘要。

### V3.2 回退

`BehaviorModelSelection` 只有在 V3.4 可用且人物 ROI 有效时选择 V3.4，否则自动使用 V3.2。需要进行受控回滚时，可在调用 `select` 时传入：

```kotlin
enableV34 = false
```

混合引擎检测到 V3.2 或模型不可用状态时会绕过 TSM 并清空时序缓存，恢复 V3.4 后需要重新积累 8 张兼容帧。

### 主要实现文件

- `data/behavior/OnnxBehaviorRecognitionEngine.kt` — 模型加载、预处理、推理、softmax 与版本类别映射
- `data/behavior/HybridBehaviorRecognitionEngine.kt` — V3.4 单帧与 V4 TSM 调度、兼容性保护和结果融合
- `data/behavior/OnnxTsmBehaviorRecognitionEngine.kt` — 8 帧 TSM 模型加载与推理
- `data/behavior/BehaviorAnalyzer.kt` — 16 帧缓冲、并发推理控制、异常恢复与 Bitmap 回收
- `data/behavior/BehaviorSignalProcessor.kt` — 观察期、时间窗口与稳定状态输出
- `data/behavior/LearningContinuityStateMachine.kt` — 会话级连续性状态
- `data/behavior/BehaviorObservationHistory.kt` — 最近 5 分钟 Focus session 节奏历史
- `data/expression/ExpressionSessionManager.kt` — 共享 CameraX pipeline、collector jobs 与生命周期释放
- `ui/screens/focus/FocusScreen.kt` — 学习状态、节奏与开发者工具 UI

### 调试采集与隐私边界

Debug 构建可在专注页的开发者工具中采集 `idle` 与 `visible_study` 目标域样本；界面和 exporter 都由 `BuildConfig.DEBUG` 守门，Release 构建无法通过该入口开启图片采集。正常运行时：

- 摄像头图像只在设备端预处理和 ONNX 推理
- 不上传服务器、不写原始图像日志
- 默认不保存原始实时摄像头画面
- Debug 导出有 24 张图片、24 条待写预测、512 KB CSV、每个 session 180 张图片且每个标签最多 8 个 session 的上限；长期开发采集仍应定期清理 app-private debug/dataset 目录

模型训练与评估说明见 [`../ml/behavior_recognition/README.md`](../ml/behavior_recognition/README.md)。

## 运行要求

- Android Studio Hedgehog (2023.1.1) 或更高版本
- JDK 21（使用开发机 JDK；JVM target 仍为 17）
- Android SDK 34
- 模拟器或 Android 8.0+ 真机

## 更多信息

- 项目规范: 参见仓库根目录 [`AGENTS.md`](../AGENTS.md)
- 后端 API: 参见 [`backend/README.md`](../backend/README.md)
- 表情识别训练、评估与科研资料仅在本地保留，不随仓库分发；客户端运行所需模型与元数据保留在 `app/src/main/assets/`。
