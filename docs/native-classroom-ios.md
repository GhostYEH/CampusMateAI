# iOS 原生互动课堂（经典课堂与受管工作台）

本文记录 iOS 端把「已授权、功能已验收的普通课件」接入 App 内原生播放器的范围、契约、兼容路径与验证口径。生成、模型推理和服务端鉴权不变；本轮只新增客户端读取与渲染。

## 1. 入口与覆盖

| 入口 | 原有行为 | 数据来源 | 原生或兼容实现 | 验证方式 | 结果 |
| --- | --- | --- | --- | --- | --- |
| 首页「互动课堂」→ 自主选题课堂 | 上传资料、计划、生成、轮询、失败重试和播放 | `self-classroom/*` + `/playback` + `ClassroomPlayback.validURL` | 「进入原生课堂」打开 `NativeClassroomView`，受信 URL 提供「网页兼容」 | `ClassroomWorkflowTests`、手动入口 | 新版入口待 Xcode 验证 |
| 首页「互动课堂」→ 从课程开始 | 进入课程库，再进课程详情 | `LearningService.courses` | `CoursesView` 不动 | 现有 UI 流程 | 保留 |
| 首页「互动课堂」→ 原生课堂 | 新增：选课程 → 工作台/舞台列表 | `GET courses/{id}/workspaces`、`.../stages` | `NativeClassroomCoursePickerView` → `ClassroomWorkspacesView` | 需构建 + 手动 | 已接线，未编译验证 |
| 课程详情 →「互动课堂」 | 经典课程课堂（session） | `courses/{id}/interactive-classroom` + `/playback` | `ClassicClassroomView(scope: .course)` 以「进入原生课堂」为主操作，受信 URL 提供「网页兼容」 | 现有流程 + 原生入口 | 新版入口待 Xcode 验证 |
| 课程详情 →「原生课堂」 | 新增：同一课程的工作台、舞台、续读进度、生成新一讲 | 受管工作台端点 | `ClassroomWorkspacesView` | 需构建 + 手动 | 已接线，未编译验证 |
| 历史重进 | 经典课堂按账号/课程恢复 session；两种课堂的原生播放按账号+课堂标识恢复 `scene_id` 与已访问页 | `ClassroomProgress`（`AccountCache`） | `NativeClassroomModel.open()` 先读快照再刷新；经典用 `/playback` 的 `scene_id` | `NativeClassroomTests.resumePrefersSavedSceneAndFallsBackWhenItDisappeared` | 逻辑已写，未运行 |
| 深链 | `TrustedWebView` 仅打开 `status=succeeded`、非 partial、服务端声明 `browser_embed_available` 且 Origin 受信的 URL | `ClassroomPlayback.validURL` | 原逻辑保留；原生入口不打开未受信 URL | `ClassroomWorkflowTests` | 保留 |
| 工作台/舞台列表 | 无原生入口 | `GET .../workspaces`、`GET .../stages` | 列表 + 每个舞台续读页码 | 需构建 + 手动 | 已实现，未编译验证 |
| 生成新一讲 | 原经典生成只产 session | `POST courses/{id}/home-generate` + `GET jobs/{id}` | 拒绝 `local-template`，轮询进度，完成后打开播放器 | `NativeClassroomTests.generationCarriesIdempotencyKeyAndRejectsLocalTemplates` | 已实现，未运行 |
| 课件版式 | 网页渲染 | 受管 `stage.document.scenes[].content.canvas`；经典 `playback.scenes[].content.canvas` | `NativeSlideSurface` 按 1000×562.5 坐标绘制 text/shape/image/audio/video；经典站内图片与画布媒体走 APIClient 鉴权下载后交给系统播放器；旧 `content.slide` 用讲义兜底 | 单测解析（含画布媒体）+ 后端共用样例；真实课件对照未执行 | 已实现，未编译验证 |
| 翻页/跳页/目录 | 网页导航 | `playback.scenes` 顺序 + `start_index` | `next/previous/go/jump`；目录 sheet | 手动 + 性能样本 | 已实现 |
| 双指缩放/拖拽 | `ClassroomMobileLayout` 注入网页 | 客户端手势 | 0.7–1.6 倍缩放、平移与整页复位，使用与安卓一致的工具栏 | 手动（iPhone/iPad） | 待 Xcode 验证 |
| 测验 | Web `QuizRuntimePanel` + quiz-attempt | `content` quiz + `.../quiz-attempt` | `NativeQuizPanel`：draft 500ms 防抖、submitted→reviewed、409 回读、重做新 attempt、`studentLed` 简答不判分；兼容 `prompt`/`text` 题干、字符串选项和数字答案（0 基映射到选项值） | `NativeClassroomTests.quizRegression...` + 新增 `quizFixturePromptStringOptionsAndNumericAnswerAreAccepted` | 已实现；新增兼容测试，未运行 |
| 项目式 | Web `PblRuntimePanel` | `project.milestones` / 旧 `phases` | `NativePBLPanel` 本地完成项按账号+舞台保存 | 单测 + 手动 | 已实现 |
| 仿真 | Web `SimulationRuntimePanel` | `widgetType=simulation` | `NativeSimulationPanel` 参数 clamp/step、公式本地计算 | 单测 | 已实现 |
| 受限互动 | Web `sandbox` iframe | `render.kind=sandbox-html/sandbox-url` | 非持久 `WKWebView`、无桥、同源顶层跳转限制 | 单测策略 + 手动 | 已实现 |
| 讲解音频（受管） | Web `<audio controls>`，用户点击生成 | `.../narration` + `artifacts/{id}` | GET 发现成品/任务；POST 才合成；下载校验 audio；`AVPlayer` 本地缓存、暂停/继续/停止、中断与后台暂停 | `ClassroomNarrationPlayer` 手动 + 单测状态 | 已实现，未运行 |
| 讲解音频（经典） | Web 播放成品音频 | 经典 `/playback` 的 `scenes[].actions[].payload.audioUrl` + `media[]` | 按 `action_id` 关联 `speech` 动作；只接受 `supported=true`、`available=true` 的本站 `media/audio/` 地址，允许完整 `/api/v1/.../media/audio/` 与相对 `audio/`、`media/audio/`；`APIClient.download` 鉴权下载、本地缓存、`AVPlayer` 播放/暂停/停止，翻页即停；每段 speech 有独立完成回调；无成品时按文本时长继续并显示网页入口，不调用受管 narration 合成 | `NativeClassroomTests` 新增经典音频解析/版本/路径与顺序用例；后端 `test_magicclass_playback.py` 24 项通过 | 已实现；静态语法通过，未编译验证 |
| 动作顺序（`steps`） | Web 按 teacher script 播放 | `scenes[].steps[]` + `scenes[].actions[]` | `ClassroomActionSequencePlanner` 严格按 `steps` 顺序、用 `action_id` 找 `actions`；`speech` 等实际播放结束后推进，`play_video` 由视频结束或用户关闭视为完成，`spotlight`/`laser` fire-and-forget；`supported=false`、动作缺失、类型不一致或媒体失败给出实际原因并停止，不无限等待 | 新增 `classicSequenceFollows...` / `classicSequenceBlocks...` 单测；样例设备验收需 Xcode | 已实现；静态语法通过，未编译/未真机 |
| 白板 | 网页查看/编辑/导出/共享 | `stage.whiteboard` / playback `whiteboards` | 从底栏打开白板，有画布正文时提供只读预览，受信网页入口覆盖其余操作 | 手动 | 待 Xcode 验证 |
| 教师/学生 AI 对话、换页发言、沉默、点名、预算 | 上游 `ClassmatePanes` 在网页运行 | `multi_agent` / `steps` | 非 speech/video 的 `steps` 仍由网页课堂执行；原生只显示「含 AI 同学对话」标签，不伪造气泡或点名 | 手动 | 未覆盖（网页兜底） |
| XP/等级/连击/成就 | `ClassroomRewards.script` 写 localStorage | `Resources/classroom-rewards.js` + 网页 localStorage | 原生播放器仍不复刻奖励；网页 HUD 与 Android 共用同一份脚本，规则对齐原生（访问 +12、答对 ×6、满分 +20、连击从第二份起 +12、重做按场景去重），key 按服务 + 账号 + 课堂隔离；只有稳定 `data-scene-id` 才记账 | `scripts/tests/classroom-rewards.test.mjs` 5 项 + Android `ClassroomRewardsContractTest` | 脚本一致性已自动验证；真机未验收 |
| 学习通题目复习/错题讲解 | `ChaoxingAssignmentReview` + `ChaoxingLessonReader` | lesson 文档 + quiz-attempt | 原路径不动 | `ChaoxingAssignmentTests` | 保留 |
| 同学一起学 | 邀请、加入、消息、共享页码、成员权限 | Learning Rooms 端点 | 原路径不动；不共享原生播放页 | 现有 UI 流程 | 保留（无播放共享） |

## 2. 两类课堂的标识

- **经典课堂**：`session_id` / `classroom_id`。`GET .../{session}/composition` 仍只返回场景计数摘要，不能把经典 session 推导成受管舞台；但 `GET .../{session}/playback` 已返回 `scenes[].content` 与动作/媒体摘要。iOS 把这份响应投影成与受管工作台同构的 `plan`/`stage document`，因此翻页、测验、进度和缓存共用一套原生实现。通过校验的网页播放地址由「网页兼容」入口打开。
- **受管工作台**：`course_id` + `workspace_id` + `stage_id` + `scene_id`。原生播放读取同一份 `stage document` 与 `/playback` 计划；`playback.start_index` 是服务端给的起点，客户端再用本地 `progress.sceneID` 作为 `scene_id` 查询续播页。`scene_id` 不存在时服务端 404，客户端去掉参数重试并退回收到的 `start_index`。
- **一致性门禁**：只有 `playback.revision == document.revision` 且两边 scene id 集合完全一致才允许原生播放；否则显示刷新提示，不猜测顺序。经典课堂额外比较 `content_version`，并把它的稳定哈希作为 revision：同一正文的冷/热快照得到同一个值，正文变化时计划/文档门禁、邻页图片缓存和讲解音频缓存键一起更新。

## 3. 原生渲染范围

- 画布：`text`（HTML 片段→段落样式，保留字号/颜色/粗细/对齐/行高/列表符号）、`shape`（圆角矩形半径来自 SVG `A` 指令）、`image`。受管内联图片只接受 `data:image/*;base64`，单张 6MB 上限；经典课堂的站内 `src` 必须通过已鉴权 `APIClient.download` 取回，绝对外链不请求。
- 旧课件：只有 `content.slide` 时使用 `ClassroomOutlinePage` 的标题/要点/分区/对照/目录/结论版面；不伪造画布坐标。
- 画布元素 ID 在解析时加索引前缀，避免同页重复 id 导致 SwiftUI 身份冲突。
- 画布媒体：`audio`/`video` 元素只保留本站相对 `src`；`ClassroomMediaPathResolver` 接受当前 session 的完整 `/api/v1/.../media/...` 与相对 `media/...`、`audio/...`，保留历史 `/media/media/` 双段，拒绝外域、其他 session、`..` 和 query/fragment；`ClassroomService` 再校验文件类型与大小，下载后才交给 `AVPlayer`/`VideoPlayer`。下载走 `APIClient.download`，携带 Bearer 并由 `SameOriginRedirectDelegate` 拒绝跨 scheme/host/port 重定向，外域不会拿到本站凭证。缓存键包含当前 `revision`（经典课堂由 `content_version` 稳定哈希得到），版本变化不会复用旧媒体；外链、缺失文件、401/404、超出体积或类型不符都显示实际状态并提示网页课堂可查看；下载任务在页面消失、换页、退后台或退出时失效，不会播放过期资源。
- 测验答案统一到选项值：题目答案可能写选项原文或选项值，解析时做一次映射；多选集合相等、简答 `lowercase` 去空白后与 `acceptedAnswers` 比较。
- 沙盒：`WKWebsiteDataStore.nonPersistent()`，不注入本站 Cookie/脚本桥，顶层跳转限制同源；`data:`/`blob:`/`about:` 允许作为页面自身导航。

## 4. 旧状态与账号隔离

- `ClassroomRewards.script(accountKey:classroom:)` 注入的账本 key 由服务、账号和课堂派生；旧版单一 key `campusmate:classroom-rewards:v1` 不带账号身份，**不迁移、不删除**，只在 HUD 面板注明“旧版网页奖励未绑定账号，未并入本课堂”。页面没有稳定 `data-scene-id` 时不按标题猜身份，只显示未计入进度。原生播放器仍不读取或合并这份网页账本，避免在无法确认属主时凭空迁移。
- 原生进度是新数据：受管课堂 `AccountCache` scope = `serverURL|userID|classroom|courseID|workspaceID|stageID`；经典课堂把 `workspaceID` 固定为 `classic`、`stageID` 为 session id，每课堂一个 `progress.json`；已访问页按 scene id 去重，最多保留 500 个。切换账号不会读到其他账号的进度。
- 本地舞台快照（`stage.json`）同样按账号+舞台分目录；切账号、换课件 revision 后旧快照不会顶替新计划。经典快照保存 `content_version` 派生的 revision；正文更新时刷新当前场景并重新解析讲解音频，旧版本缓存键不复用。
- 经典课堂的 session、历史记录和网页进度保持原路径，不因原生入口出现而被删除或改写；原生进度是另一份新数据，不与 WKWebView localStorage 混用。

## 5. 性能口径与对照

同一设备、同一课件、可比网络下记录：

| 指标 | WKWebView 基线 | 原生 v1 | 备注 |
| --- | --- | --- | --- |
| 冷开首屏可读 | 未采集 | 未采集 | 无本地 `stage.json`，从点开到第一页文字出现 |
| 热开首屏可读 | 未采集 | 未采集 | 有快照；仍会后台刷新 |
| 翻页耗时 | 未采集 | 未采集 | 从点击到新页内容 `onAppear` |
| 帧卡顿 | 未采集 | 未采集 | 需 Instruments / MetricKit |
| 峰值内存 | 未采集 | 未采集 | `phys_footprint` 采样；图片缓存 48MB/300 上限 |
| 服务端生成耗时 | 不适用 | 未采集 | 用 job 创建到终态单独统计，不混入首屏 |

已做的可测优化：

1. 首屏不再等网络：受管课堂先读本地快照立即显示，再并行刷新 `playback` 与 `stage`；经典课堂先读快照，再刷新 `/playback`。网络失败保留快照并提示。
2. 邻页图片后台解码：`prefetchNeighbours` 只投递任务，`Task.detached(priority: .utility)` 解码内联 data URI；经典站内图片走 `APIClient.download` 后解码，再回主线程入缓存，翻页时不做同步 `UIImage(data:)`。
3. 图片缓存按「账号|课程|工作台|舞台|revision|场景|元素」索引，48MB/300 条上限；换课堂或内容版本变化时不会复用旧图，scene id 跨课堂也不会串图；经典远程图片只接受当前 session 的 `/api/v1/` 媒体路径或相对 `media/`、`audio/`，其他课程与绝对外链不请求。画布视频缓存键同样加入账号、session、元素和内容版本，换账号不会复用另一个账号下载的视频。
4. 讲解音频按「账号哈希 + 资源键」落盘：受管用 artifact id，经典用 `content_version|scene|action|media` 的稳定哈希；7 天清理；播放只读本地文件，不把鉴权 URL 交给系统播放器。顺序播放的每段 speech 使用独立 completion，翻页/停止通过 token+actionID 过滤迟到回调；系统音频中断会暂停顺序并由用户继续，旧音频回调不会启动新页动作。
5. 测验草稿 500ms 防抖；切页/退出取消未完成任务，避免过期写回。
6. 性能样本 JSON 落在 `Application Support/CampusMate/ClassroomPerformance.json`，玩家内「更多 → 查看性能样本」可读。

`ClassroomPerformanceProbe` 的「首屏可读」由可见内容首次 `onAppear` 触发，不在状态赋值时提前记账；「翻页」从 `go(to:)` 到新页 `onAppear` 计时。

### 6.3 2026-11-21 会话、答题与缓存整改

| 问题 | 本轮处理 | 验证 |
| --- | --- | --- |
| 同步/提交期间翻页会把旧 quiz 写回新场景 | `loadQuiz`/`saveDraft`/`submitQuiz`/`syncQuizIfNeeded` 统一捕获场景、场景代次、轮次；成功和失败分支都复核，旧响应只丢弃不写回 | 静态复查；`NativeClassroomTests` 既有纯模型用例不受影响 |
| 连续点击提交、同步重入 | 模型层 `submittingQuiz` / `syncingQuiz` 门闩；写操作经 `ClassroomQuizWriteGate` 串行到达服务端 | 静态复查 |
| 重做尚未取得新 attemptID | `retryQuiz` 增加轮次并立即申请新根 attempt；写锁内读取最新 attempt/`start_new` 标记，旧轮次响应不能改写新一轮 | 静态复查 |
| 浮层测试期间切页/换号 | `sceneDidChange`/`shutdown` 取消 quiz 读取、提交、同步与草稿任务；响应写回前复核场景与轮次 | 静态复查 |
| 音频缓存主线程 I/O、非原子复制 | `ClassroomAudioCache` 改为后台串行队列；同目录临时文件 + 原子替换；初始化不再同步扫描 | 静态复查 |
| 视频缓存无上限/无过期 | 新增 `ClassroomVideoCache`：256 MB 总量、7 天过期、播放中保护、临时文件原子发布 | 静态复查 |
| 缓存路径强制解包 | 移除视频缓存目录的 `first!`；目录不可用时返回可读错误 | 静态复查 |
| 邻页图片预取不可取消 | `ClassroomImageCache` 保存预取任务句柄，翻页/退出 `cancelPreloads()`；下载文件读取前先查大小并清理临时文件 | 静态复查 |
| 画布媒体下载不可取消 | 视图保存 `loadTask`，退后台/消失时取消；播放器 `shutdown` 清理播放保护 | 静态复查 |
| 生成成功后复用旧幂等键 | 成功后轮换；服务端明确失败（4xx 或已知生成错误码）轮换；取消/5xx/网络中断等未确认结果保留原键 | 静态复查 |
| 轮询一次网络错误即永久停止 | 临时错误有上限退避（最多 5 次，间隔上限 30s）；401/403/404/410 与终态停止；手动恢复重置退避并只保留一个 `.task` | 静态复查 |
| 迟到进度覆盖当前会话 | `refresh()` 捕获目标 sessionID，写回前复核；`resumePolling()` 通过 `pollEpoch` 重启轮询 | 静态复查 |
| 网页奖励未按账号隔离、规则漂移 | 与 Android 共用 `classroom-rewards.js`；key 按服务 + 账号 + 课堂；稳定 `data-scene-id` 才记账；旧 v1 不迁移不删除 | `scripts/tests/classroom-rewards.test.mjs` 5 项通过（Windows Node 24） |

**未验证**：以上 iOS 改动均未在完整 Xcode 环境编译；`ClassroomQuizWriteGate`、缓存 actor/队列与 `pollEpoch` 的并发行为需在 Mac 上运行 `swift test` 与模拟器/真机验收。Windows 没有 Swift toolchain，不得把静态复查表述为构建或真机通过。

## 6. 验证状态

- **已写、未运行**：`ios/Packages/CampusCore/Tests/CampusCoreTests/NativeClassroomTests.swift`（播放计划/文档一致性、续播回退、HTML 段落、画布元素与图片限制、经典 `speech` 音频的 action_id 关联/媒体可用性/外链拒绝/`content_version` revision 与缓存键/画布音视频解析、旧讲义兜底、测验判分与 studentLed、attempt 恢复、仿真 clamp、PBL 的数组/任务组两种形状、沙盒同源策略、讲解成品判据、进度去重与上限、404 去 `scene_id` 重试、生成幂等键与模板拒绝、错误文案、经典 `/playback` 投影）。本轮新增 5 个 iOS 用例：`classicSequenceFollowsServiceStepOrderAndResolvesEachSpeech`、`classicSequenceBlocksUnsupportedMissingAndMismatchedActions`、`quizFixturePromptStringOptionsAndNumericAnswerAreAccepted`、`classicMediaRequestCarriesBearerForTrustedSessionPath`、`classicMediaPathAcceptsRelativeAndDoubleMediaWithinSession`。
- **本轮可执行验证**：`backend/tests/test_magicclass_playback.py` 在 Windows 隔离环境 24 项通过（2026-11-19），确认真实契约里 `actions[].payload.audioUrl`、`media[].element_id/available/content_type/url` 与画布 `audio`/`video` 元素形状；本轮 12 个 iOS 源码/测试文件用 tree-sitter-swift 做语法解析，均无 ERROR 节点。该解析只检查语法，不做类型检查、宏展开和 Swift 并发隔离检查。
- **阻塞位置**：当前 Windows 环境没有 Xcode / Swift toolchain。`ios/scripts/validate.py --build` 能启动隔离后端，但在第一项 `swift test` 因 `FileNotFoundError: [WinError 2]`（找不到 `swift`）退出，尚未进入 `xcodebuild`；因此 App target 构建、CampusCore 单测、模拟器 UI 和真机验证均未执行。App 构建需完整 Xcode + iOS SDK，模拟器需 `xcrun simctl` 可用设备，真机还需签名与 UDID。
- **未验证**：真实课件版式/坐标/公式/图片/音视频、真实生成服务、iPhone 窄屏与 iPad、VoiceOver、动态字体、音频中断、旋转、窗口尺寸变化、账号切换、后台恢复、WKWebView 对照数字。本轮 iOS 顺序执行、经典媒体鉴权和测验兼容均只有静态语法与契约级验证，**没有编译、单测或设备验收数据**；不能引用 Android 样例结果替代 iOS。
- **需要真实账号**：工作台/舞台列表、课程权限、历史课堂、讲解合成任务、测验 attempt 冲突。
- **UI 自动化标识**：`native.classroom.player/close/outline/previous/next`、`native.quiz.submit`、`native.pbl.<taskID>`、`classic.classroom.nativePlay`，可在完整 Xcode 环境用 `NativeWorkflowTests` 扩展同一真实入口。

### 6.1 完整 Xcode 环境的执行清单

以下命令本轮均未执行，只作为在 Mac 上复现验证的入口；`<UDID>` 换成目标模拟器。

```sh
swift test --package-path ios/Packages/CampusCore
xcodebuild -project ios/CampusMate.xcodeproj -scheme CampusMate -configuration Debug \
  -destination 'platform=iOS Simulator,id=<UDID>' build
python3 ios/scripts/validate.py --build --ui --device <UDID>
```

执行后按下表分别记录，不要把模拟器结果写成真机结果，也不要把本地模板或缓存样本写成真实生成服务结果。

| 验证层 | 覆盖内容 | 结果 |
| --- | --- | --- |
| 后端播放契约 | `backend/tests/test_magicclass_playback.py` | 24 passed（Windows，2026-11-19） |
| CampusCore 单测 | `NativeClassroomTests`、`ClassroomWorkflowTests`、`ChaoxingAssignmentTests` | 未执行（无 Swift toolchain） |
| 模拟器 | CampusMate App target、iPhone 窄屏、iPad、VoiceOver、动态字体、旋转、窗口尺寸变化 | 未执行 |
| 真机 | 音频中断、前后台、账号切换、真实课件版式 | 未执行 |
| 真实生成服务 | `home-generate` 轮询、失败恢复、讲解合成、测验 attempt 冲突 | 未执行 |
| WKWebView 对照 | 同一设备/课件/网络下的冷开、热开、翻页、内存 | 未采集 |

### 6.2 2026-11-19 iOS 同源修复范围

本轮由 Android 验收问题反查 iOS，确认 iOS 不是空预留目录：`ios/CampusMate` 为 App target，`ios/Packages/CampusCore` 为共享 Swift Package，测试在 `ios/Packages/CampusCore/Tests/CampusCoreTests`。iOS 原本已有 `ClassroomPlaybackScene.steps/actions` 解析和本站媒体 Bearer 下载，但以下问题与 Android 修复前同类，已在本轮补齐：

| 问题 | iOS 原状 | 本轮处理 | 验证 |
| --- | --- | --- | --- |
| `steps` 只解析不执行 | 无顺序执行器，UI 手动触发单个动作 | 新增 `ClassroomActionSequencePlanner`；模型按 `steps` 顺序、用 `action_id` 找 `actions`；blocking 动作完成才推进，`spotlight`/`laser` 立即完成 | 2 个 planner 单测；静态语法通过 |
| 相对媒体路径 | `ClassroomService` 只接受完整 `session/media/...`；相对 `audio/`/`media/` 被拒绝 | 新增 `ClassroomMediaPathResolver`，接受完整本站路径与相对形式，保留 `/media/media/`，拒绝外域、其他 session 和 `..`；音频额外要求 `/media/audio/` | 2 个路径/鉴权单测；静态语法通过 |
| 图片相对路径 | `ClassroomImageCache` 相对图片按 API Base 拼，可能落到错误路径 | `preload(... mediaBasePath:)` 把相对 `media/...`/`audio/...` 图片拼到当前 session 的 `/media/`；绝对外链拒绝 | 单测解析路径；未设备验证 |
| 同一页多段 speech | `ClassroomNarrationPlayer` 只有全局 `onFinish`，无法区分 action | `play(url:completion:)` 每次播放独立回调；每段 speech 有 actionID/token 过滤，完成才推进 | 静态语法通过；未运行 |
| 视频顺序步骤 | 只有画布内手动视频 sheet，关闭不回写顺序 | 新增 `SequenceVideoSheet` 与 `sequenceVideo` 状态；自然结束或用户关闭都完成步骤；停止/翻页会关闭并拒绝旧回调 | 静态语法通过；未设备验证 |
| 翻页/退后台/退出 | 翻页只停讲解；退后台只暂停讲解；`shutdown` 不取消保存任务 | 翻页 `sceneDidChange` 取消 sequence 并恢复旧 continuation；退后台 `handleScenePhase` 暂停 sequence/音频/画布媒体；`shutdown` 取消 sequence、讲解、草稿、保存与状态任务并 `started=false`；旧音频回调不会启动新页 | 静态语法通过；未设备验证 |
| 测验兼容 | 只认 `question`/`stem`；数字 `answer:0` 变 `"0"`，与选项 `A` 不匹配 | 增加 `prompt`/`text`；数字答案按 0 基索引映射选项值；解析增加 `solution` fallback | 1 个兼容单测；静态语法通过 |
| 白板/PBL/老师提问 | 网页路径保留，原生无执行器 | 顺序执行遇到 `wb_*` 或未支持 type 返回真实原因并提示网页课堂，不无限等待；原网页入口不变 | 契约核对；未真实课件验收 |

**兼容路径**：经典课堂生成成功后以「进入原生课堂」为主操作。网页地址通过 Origin 校验后显示「网页兼容」，供白板编辑、共享、教师和 AI 同学对话使用。

**未验证/已知缺口**：

- Windows 无 Swift/Xcode，本轮没有编译、`swift test`、模拟器或真机数据；tree-sitter 只做语法解析。
- `SequenceVideoSheet` 使用系统 `VideoPlayer`，系统控制器的暂停不会回写 `sequence.paused`；关闭/播放结束会完成步骤，暂停语义需真机确认。
- 视频临时下载文件依赖系统临时目录，未显式清理；长期缓存策略未验证。
- 真实 iOS 课程、受管工作台、学习通作业复习、WKWebView 对照、冷/热开性能均未采集。
- 本轮 iOS 改动已随在线课堂重构一并提交并推送。
## 7. 接口缺口与最小共享方案

**已解决**：经典课堂不需要伪造 `workspace_id` / `stage_id`。`GET /api/v1/courses/{course_id}/interactive-classroom/{session_id}/playback` 与 `GET /api/v1/self-classroom/{session_id}/playback` 已经返回 `scenes[].content`、`render`、`actions`、`media` 和 `start_index`；iOS 用 `ClassroomClassicPlayback` 投影成同构 `plan`/`stage document`，翻页、测验、进度和缓存复用同一套代码。`composition` 仍只用于摘要。

**仍缺的能力（本轮不改 API）**：

1. **经典讲解合成（仅缺生成）**：经典 playback 已经下发 `speech` 成品 `payload.audioUrl` 与 `media[]`，iOS 已接通已有音频；仍没有 narration GET/POST，也没有 `artifact_id`。当场景没有成品时只显示真实原因并保留网页课堂，不伪造音频。若要在 App 内生成新讲解，最小共享方案仍是按受管同一形状增加 `GET/POST .../{session_id}/scenes/{scene_id}/narration` 和 `self-classroom` 对应路由，返回同样的 `{available,has_script,job}`；权限沿用 course/session 鉴权，成品仍走 `GET courses/{course}/artifacts/{artifact_id}`。
2. **经典画布音频/视频元素（已接通已有资源）**：`content.canvas.elements[]` 的 audio/video 已解析并走 `src` + 鉴权下载；`scenes[].media[]` 仍用于核对 `kind/role/content_type/url/available`。目前服务端没有稳定给出 `duration`，播放器以文件时长为准；权限边界与图片相同，只允许本站 `/api/v1/` 资源，不接受匿名外链。真实课件里的坐标/尺寸仍需 Xcode 环境验收。
3. **教师/AI 同学动作**：`actions[]` 已有 `id/type/mode/supported/reason/payload`，`steps[]` 有 `action_id/type/mode`。iOS 已有按 `steps` 顺序的 `ClassroomActionSequencePlanner`，原生执行 `speech` 与 `play_video`，`spotlight`/`laser` 按 fire-and-forget 处理；`wb_*`、气泡、换页发言、点名等仍返回真实原因并保留网页课堂，不假装完成。最小下一步不是新增接口，而是补一份按 `action.type` 的 payload 契约（字段、可空性、权限、失败行为），再实现其余 type；未实现的 type 继续显示“网页课堂可操作”。
4. **白板与共享课堂**：playback 只给 `whiteboards` 计数，没有白板文档/编辑/导出端点；`同学一起学` 现有 iOS 能力只有邀请、加入、消息、共享页码和成员权限，没有“共享播放”端点。若下一阶段要做原生共享，需要白板文档/变更接口和房间级 `page/scene` 同步接口，权限按房间成员角色校验；本轮保持网页兜底。

## 8. 下一阶段接入点

- 进度节点：`ClassroomProgress.visitedSceneIDs`、`sceneIndex`、`revision` 已是稳定数据源，可直接驱动「课堂目标 → 知识讲解 → 练习挑战 → 复盘」的时间线；不要另造教学顺序。
- 对话状态：`ClassroomPlaybackScene.hasMultiAgent` 与 `steps/droppedActions` 保留真实动作数量；`ClassroomActionSequencePlanner` 已按 `steps` 驱动 speech/video，下一阶段接 AI 同学/教师气泡时沿用同一 `action_id` 顺序，不用装饰性台词替代。
- 讲解音频：先使用 `actions[].payload.audioUrl` 或受管 artifact；没有成品时不要自动合成，先用真实课件统计覆盖率，再决定是否补经典 narration 生成端点。
- 主题：`CampusPalette.classroom`、`JournalBackdrop`、`CampusCard` 与现有讲义组件可复用到暮色校园/暖光黑板/手账风格；场景 id、原题、提示、评分与解析仍由 stage 文档决定。
- iPhone/iPad：`NativeSlideSurface` 已按可用区域等比适配，`sizeClass == .regular` 提高画布最大高度；后续样式层不应改变文档坐标与进度状态。
