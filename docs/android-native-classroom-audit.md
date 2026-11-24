# Android 原生互动课堂审计（动作顺序与设备验收轮）

> Android 源根：`android/app/src/main/java/com/example/campusai/`。
> 本轮在已接入的 Compose 播放器、经典媒体鉴权、经典讲解音频与测验链路上，补服务端 `steps` 顺序执行、取消语义和样例设备验收。
> 结论只统计实际构建、单测和本机模拟器结果；真实课程、受管工作台、学习通复习和 WebView 对照单列，未通过的不计为通过。

## 1. 本轮结论

- 服务端 `steps` 已驱动同页顺序播放：按 `action_id` 从 `actions` 找真实动作，保留单步 chips；同步语音等实际播放结束再推进，`spotlight`/`laser` 等按 fire-and-forget 处理。
- 脱敏样例上，两段讲解音频按顺序各播一次，随后播放 MP4；顺序条支持顺序播放、暂停、继续、停止、重播；翻页、退后台、退出和账号切换的取消链已接。
- 本轮修复了两个设备上暴露的真实问题：
  1. 测验页空白：`parseQuiz` 现在兼容 `prompt`、字符串选项和数字索引答案；样例可显示题目、作答、判分并退出重进回读。
  2. 退出重进后顺序播放卡死：`finish()` 不再释放 ExoPlayer，仅停止播放并清空结束小结；播放器由 `onCleared()` 释放。退出重进后顺序播放已复验通过。
- 样例上实际通过：入口打开、顺序音频、视频画面、暂停/继续、停止、快速翻页取消、测验提交、结果回读、学习小结、原生性能埋点。
- 真实课程未通过：fixture 的课程书架为 0 门课程；经典“演示课程-大学英语”进入网页后报“课堂网页脚本运行失败”；因此经典新课、历史课、自主选题真实课件、受管工作台和学习通作业复习仍无真机通过项。
- 兼容路径部分失败：样例第 3 页打开隔离网页运行时返回“课堂网页连接失败（错误码 -6）”；第 6 页 PBL 返回 `pbl_requires_compat_runtime`；白板、PBL、老师问答、语音回填、编辑/分享仍不能标为完成。
- 默认播放路径不切换：真实课件未通过验收，现有入口保持原原生/网页选择逻辑。

## 2. 环境与构建

| 项 | 实际值 |
| --- | --- |
| 本机 JDK | JDK 21（`openjdk 21.0.11`） |
| Gradle / AGP | Gradle 8.13 / AGP 8.13.0 |
| Android SDK | 由 `android/local.properties` 配置；platform `android-35`；build-tools `35.0.0` |
| 模拟器 | AVD `Medium_Phone_API_37.0`；`emulator-5554`；`sdk_gphone64_x86_64`；API 37；1080×2400；420dpi |
| 服务端 | `backend/tests/fixtures/classroom_playback_server.py`，`127.0.0.1:8000`；App API Base `http://10.0.2.2:8000/api/v1/` |
| 账号 | `student_demo / Demo123456` |
| APK | `android/app/build/outputs/apk/debug/app-debug.apk`，安装成功 |

构建与测试：

- `:app:testDebugUnitTest` 聚焦课堂用例：26 个测试、0 失败（`ClassroomActionSequenceTest` 6、`ClassroomMediaPolicyTest` 7、`ClassicClassroomPlaybackParserTest` 4、`ClassroomRewardsEngineTest` 5、`NativeClassroomParserTest` 4）。
- 全量 `:app:testDebugUnitTest --continue`：646 个测试、5 失败、1 跳过；失败均为既有且与本轮课堂无关：`PersonAnalyzerTest` Mockito、`ExpressionModelAssetContractTest` 资产缺失（含 AndroidTest 同名项）、`GlassControlCoverageTest`、`ClassicDashboardOnlyContractTest`。
- `:app:assembleDebug` 成功并安装到模拟器。
- 中文仓库路径下 Gradle 测试 worker 的 Java `@argfile` 解码会丢类路径；本轮改用仅含 ASCII 的映射路径运行测试，仅用于路径验证，不改仓库结构。

## 3. 样例设备验收

样例为 `sess_fixture_self`，共 6 个场景；开场页包含两段 WAV、一个 MP4 和实心黑 1×1 PNG。入口路径：`互动课堂 → 最近学习 → 自主学习 → 进入原生课堂`。

| 用例 | 实际操作 | 结果 |
| --- | --- | --- |
| 入口到播放 | 首页互动课堂 → 最近学习 → 进入原生课堂 | 通过；打开第 1/6 页“开场”，显示“本页动作 0/3 · 顺序播放” |
| 顺序执行 | 点击顺序播放，观察步骤与日志 | 通过；低音 → 高音 → 视频；单步 chips 保留 |
| 音频顺序与次数 | 读取 `dumpsys audio` 的 AudioTrack 创建/开始/停止时间 | 通过；重新进入后 12:21:04.366 低音、12:21:05.409 高音各一次，12:21:06.885 起视频 |
| 视频画面 | 手动“播放视频”，截图 | 通过；视频弹窗显示校园画面，系统控制条显示 `00:21` 总时长 |
| 视频暂停 | 视频弹窗“暂停”/继续 | 通过；画面停止并可继续 |
| 视频拖动 | 上一轮同一设备、同一课件已验证 Range seek 与画面变化；本轮重建后视频可播放，未再次稳定命中进度条坐标 | 上一轮通过；本轮未重复采样 |
| 顺序暂停 | 顺序开始后 350ms 点“暂停” | 通过；显示 1/3 + 继续 + 停止 |
| 顺序继续 | 点“继续” | 通过；继续执行后续步骤并进入视频 |
| 顺序停止 | 视频弹窗点“停止” | 通过；关闭视频弹窗，顺序条恢复“顺序播放”，可重开 |
| 快速翻页取消 | 顺序执行中约 1.2s 翻到下一页 | 通过；页面切到 2/6 随堂测验，旧顺序不再运行，旧 AudioTrack 停止 |
| 退出重进 | 保存并退出 → 再进原生课堂 | 通过；无残留结束弹窗，回到第 1/6 页，顺序播放再次可执行到“已完成” |
| 学习小结 | 退出确认弹窗 | 通过；显示“有效学习 36 秒 / 已访问 5/6 页 / 客观题 1/1 题正确 / 本次 +26 XP” |
| 退后台 | 本轮未取得可重复的端到端采样 | 未通过项；按代码路径 `onHostPause → resetSequenceRuntime` 已接，真机未重复确认 |
| 切换账号 | fixture 无第二正常账号可完成整段会话 | 未通过项；由 `ClassroomMediaPolicyTest` 的账号/课堂代次用例覆盖，未做设备切换 |

### 3.1 测验与回读

- 打开样例第 2/6 页“随堂测验”，题目正文与 A–D 选项正常显示。
- 题目：`函数在区间内单调递增的条件是？`；选项 A/B/C/D；正确答案为 A（JSON `answer: 0`）。
- 选择 A 并提交：显示“课堂挑战 · 结果 / 得分 1 / 1 · 答对 1 题”，A 标记“正确答案”，XP 从 60 变为 86。
- 点击退出 → 保存并退出 → 重新进入：仍显示“课堂挑战 · 结果 / 得分 1 / 1 / 答对 1 题”，XP 保持 86，未再次杜撰加分。
- 解析字段与 `explanation`/`solution` 兼容已由 `NativeClassroomParserTest` 覆盖；fixture 的 `sc_quiz` 本身没有 `analysis` 字段，因此设备上无解析文本可显示，不把“解析已显示”计为通过。

### 3.2 样例页能力盘点

| 页码 | 场景 | 实际状态 |
| --- | --- | --- |
| 1/6 | 开场 | 原生讲义、两段音频、视频；通过 |
| 2/6 | 随堂测验 | 原生题目、作答、判分、回读；通过 |
| 3/6 | 互动演示 | 提示“使用兼容课堂播放”；点“打开”进入隔离 WebView，返回“课堂网页连接失败（错误码 -6）” |
| 4/6 | 未知类型 | “这一页当前不能原生播放”；无兼容按钮 |
| 5/6 | 旧版无 id 场景 | “这一页当前不能原生播放”；无兼容按钮 |
| 6/6 | 项目式学习 | “这个场景当前无法播放（pbl_requires_compat_runtime）”；PBL 原生/网页均未完成原操作 |

## 4. 真实课程与兼容路径

### 4.1 真实课程

- `图书馆` 显示“0 门课程”，无法从课程页打开经典新课、历史课或课程历史原生入口。
- `最近学习` 的“演示课程-大学英语 · 继续上课”进入网页课堂后报“课堂网页脚本运行失败”；未打开真实课件，也没有可验证的原生经典入口。
- `sess_fixture_self` 只代表自主选题样例，不能替代课程经典新课/历史课验收。
- 受管工作台、学习通作业复习：fixture 未提供可进入的课程和任务数据，未做真机回归；不能记为通过。

### 4.2 兼容路径

- 自习室继续上课、课程历史网页入口、CPM 深链：代码入口保留，本轮未做真机点击验证。
- 白板：样例底部有“白板”按钮，但经典 playback 只有计数；未取得白板内容，不能验证原操作。
- PBL：第 6 页明确返回 `pbl_requires_compat_runtime`，既没有原生 PBL 操作，也没有可用的网页兼容运行时。
- 老师提问/点名：底部只有“讲解/同学/白板”，没有老师提问入口；未完成原操作。
- 语音回填：原生播放器只有 TTS 和本地朗读，没有 ASR 回填入口。
- 视频弹窗：顶部自定义暂停/继续已测；PlayerView 自带控制器的播放/暂停未回写 sequence.paused，可能造成顺序条状态短暂不同步，列为待修缺口。
- 编辑/导出/分享：原生播放器不提供，仍依赖网页工作台；本轮网页运行时连接失败，未验证可用性。
- 结论：上述项均列缺口，不能因为“按钮存在”或“代码有 fallback”就标为兼容完成。

## 5. 性能

采样口径：同一模拟器 `Medium_Phone_API_37.0`、同一 `sess_fixture_self` 样例、同一 `10.0.2.2:8000` 网络、debug 构建；性能浮层来自播放器内 `firstPaintMs/pageFlipMs/memoryNow()`，不是实验室基准。

| 指标 | 原生播放器 | WebView 对照 |
| --- | --- | --- |
| 首屏可读 | 241ms | 未采集；网页课堂脚本/连接失败，无可比首屏 |
| 翻页 | 70ms（第 1→2 页） | 未采集 |
| NativeHeap | 70MB（开场）；79MB（翻页到测验后） | 未采集 |
| `dumpsys meminfo` TOTAL PSS | 317,326KB（约 310MB） | 未采集 |
| 帧统计 | 1725 帧，331 Janky（19.19%）；50th 17ms、90th 28ms、95th 38ms、99th 200ms | 未采集 |

注意：

- 帧统计是 App 累计值，包含首页、滚动、弹窗和导航动画，不是课堂段隔离口径；不能据此宣称“课堂流畅”或“已优化”。
- 没有真实课件和可用 WebView 基线，本轮不做原生/网页性能优劣结论。
- 同一设备、同一课件、可比网络的 WebView 对照仍未完成，阻塞原因是网页运行时在 fixture 上连接/脚本失败。

## 6. 测试覆盖

本轮新增/修改的课堂测试：

| 测试 | 覆盖 | 结果 |
| --- | --- | --- |
| `ClassroomActionSequenceTest`（6） | steps 顺序、等待完成、切页迟到回调、暂停门、失败短路、缺失/不支持原因 | 6/6 通过 |
| `NativeClassroomParserTest`（4） | render kind、sandbox 同源拒绝、slide/quiz/pbl 投影；新增 `prompt` + 字符串选项 + 数字答案回归 | 4/4 通过 |
| `ClassroomMediaPolicyTest`（7） | 可信本站凭证、外域隔离、`/media/media/`、端口/重定向、自主前缀、账号/场景迟到响应 | 7/7 通过 |
| `ClassicClassroomPlaybackParserTest`（4） | 经典 content→原生文档、audioUrl、steps/actions 对应、unsupported 原因 | 4/4 通过 |
| `ClassroomRewardsEngineTest`（5） | 首次/重复、combo、满分、等级 | 5/5 通过 |

本轮新增的解析回归用例：

- `fixture quiz accepts prompt string options and numeric answer`：断言题干、4 个字符串选项、`answer=0` 映射为 `A`、`autoGradable=true`、解析文本保留。

未覆盖：真实课程 DTO 形状、网页运行时、账号切换的设备端到端、退后台时的实际音频停止、视频进度条重复拖动、受管/学习通入口回归。

## 7. 关键实现与修复

- `ClassroomActionSequence.kt`：`ClassroomSequenceStep`、`ClassroomActionSequencePlanner.plan(sceneId, steps, actions)`、`runClassroomSequence`；按服务端顺序，缺失/类型不一致/`supported=false` 生成原因；blocking 步骤必须 `Completed` 才推进。
- `NativeClassroomViewModel.kt`：
  - 新增顺序任务、音频/视频/白板等待器、`NativeSequenceUiState`；
  - `startSequence/pauseSequence/resumeSequence/stopSequence`；
  - 顺序音频唯一 `mediaId` + token，`onPlaybackStateChanged`/`onPlayerError` 校验当前 waiter、token、mediaId 和播放位置；
  - 视频按 URL、白板按 sceneId 过滤迟到回调；
  - 翻页/`onHostPause`/`onAccountChanged`/`releaseMedia` 取消旧任务；
  - `onSceneChanged` 初始化 steps 总数，`resetSequenceRuntime` 保留总数；
  - `finish()` 只 `resetSequenceRuntime` + `stopAudio`，不释放播放器；`_uiState.endSummary=null`；`onCleared()` 负责 `releaseMedia()`。
- `NativeClassroomPlayer.kt`：`SequenceBar`（本页动作 x/y、顺序播放/暂停/继续/停止/重播）、单步 chips；`VideoDialog` 增加 `onEnded/onFailed/paused`、暂停/继续、停止、关闭。
- `NativeClassroomParser.kt`：`parseQuiz` 兼容 `question/prompt/stem/text`、对象/字符串选项、数字/字符串/数组答案、`analysis/explanation/solution`，新增 `quizOptionLabel` 与 `quizAnswerValues`。
- 媒体鉴权链路保持 `ClassroomMediaPolicy → 共享 OkHttp/Coil/Media3 DataSource`；仅当前课堂 `media|audio` 的可信本站路径附 Bearer，外域不附，重定向再校验。

## 8. Git 与交付状态

- 本轮改动已提交并推送到 `master`，同时快进 `android-current` 与 `codex/asr-robustness-evaluation`，三个分支保持一致。
- 未删除、覆盖或伪造 `.git`；源码、测试和本文档改动均已纳入本次提交。
- 本任务 Android 侧改动集中在：`ClassroomActionSequence.kt`（新增）、`NativeClassroomViewModel.kt`、`NativeClassroomPlayer.kt`、`NativeClassroomParser.kt`、`NativeClassroomCache.kt`、`ClassroomMediaDataSource.kt`、`AppRepository.kt`、`NativePblPanel.kt`、`ChaoxingAssignmentReview.kt`、`NativeClassroomParserTest.kt`、`ClassroomRewardsEngineTest.kt`、`android/gradle.properties`；文档侧还包含 `AGENTS.md`、`README.md`、`android/README.md` 和 gamified dashboard spec 的 JDK 约束调整。

## 9. 仍未完成 / 下一轮门槛

1. 需要真实后端或导入真实课程数据，至少提供课程经典新课、历史课、自主选题各一份，以及受管工作台、学习通作业复习各一条可进入记录。
2. 需要可用的网页课堂运行时；当前 fixture 的经典网页报“课堂网页脚本运行失败”，互动页报连接错误 -6，无法验证白板/PBL/老师问答/编辑分享。
3. 需要在同一设备、同一真实课件、同一网络下补 WebView 冷开/热开、翻页、卡顿和内存采样；当前只有原生数字，不能做优劣结论。
4. 需要补设备端账号切换和退后台的音频停止采样；代码链路已有，但本轮未取得可重复结果。
5. 真实课程通过前，不切换默认播放器，不把“样例通过”写成“真实课堂通过”。
6. 游戏化美术和内容样式仍放在功能验收之后，本轮未改视觉皮肤。

## 10. 2026-11-21 会话、答题、鉴权与奖励整改

> 本轮按原审查报告 1–12 与 P3 复核当前工作区，只记录实际完成的修改和验证；未执行项单列在 10.6。

### 10.1 播放会话生命周期（报告 1）

- `NativeClassroomViewModel` 增加显式 `startSession()` / `endSession()`：ExoPlayer、TTS、图片缓存、媒体代次与视频数据源移入会话级的 `PlaybackSession`。关闭弹窗、离开页面、换号或 ViewModel 清理时，先在独立 IO 作用域按**原账号**写入学习位置与奖励，再提交待保存草稿，最后取消全部任务并释放播放器、TTS、图片加载器与媒体监听。
- `NativeClassroomPlayer` 用 `Activity.isChangingConfigurations` 区分旋转与真正退出：旋转保留当前会话（页、缩放、讲义/PPT 选择和草稿都在 ViewModel 中），其余路径结束会话；关闭后重开同一课堂会创建新的播放器与缓存。
- `finish()` 不再把释放留给 `onCleared()`；经典、自主选题、受管课堂和作业复习四个入口都通过同一播放器 `onDispose` 收口。
- 讲解与视频 ExoPlayer 设置音频焦点（`USAGE_MEDIA` + `AUDIO_CONTENT_TYPE_SPEECH`）与 becoming-noisy；系统 TTS 改用媒体流，便于系统统一打断。
- 回归：`ClassroomQuizCoordinatorTest` 覆盖会话结束前的草稿落盘；播放器生命周期需设备验证（见 10.6）。

### 10.2 测验写入（报告 2）

- 新增 `ClassroomQuizCoordinator`：同一会话共享一把写锁，草稿、提交、复核和重做按发送顺序到达服务端；每次本地作答递增编辑代次，响应回来只有「账号 + 场景 + 轮次 + 编辑代次」都对上才允许回显答案。
- 提交会排在在途草稿之后；提交失败会保留报告并补一份草稿，退出时不丢最新答案；409 `QUIZ_ATTEMPT_CONFLICT` 统一回读服务端当前作答，不当作成功。
- 重做立即申请新根 attempt；请求返回前用轮次隔离，旧轮次的迟到响应不能改写新一轮。
- 回归：`ClassroomQuizCoordinatorTest` 7 项（A 编辑→翻 B→回 A 再编辑、提交前草稿、响应丢失、409 回读、重做、换号、旧回显）。

### 10.3 令牌与信任链（报告 4）

- 新增 `AuthTokenRefreshCoordinator`：同一登录会话并发续签只发一次请求，等待者复用新 token；退出/换号后旧续签结果丢弃；`ApiClient` 的 token 与刷新回调改为 `@Volatile`，媒体客户端共享 Dispatcher/连接池并按课堂 LRU 复用。
- `ClassroomUrlPolicy` 只对合法 IPv4 字面量判私网，修复 `10.classroom.example.edu` 这类域名的误拦；正式 HTTPS 与调试本地入口规则不变。
- `ClassroomViewer` 在组件边界重新校验调用方提供的可信 Origin，加载、同源导航和麦克风授权都基于该 origin；历史、自习继续、经典、自主选题入口均传入后端 `embed_origin`。
- 回归：`AuthTokenRefreshCoordinatorTest` 5 项、`ClassroomUrlPolicyTest` 新增 2 项。

### 10.4 网页奖励（报告 5）

- 网页 HUD 提取为 `assets/classroom-rewards.js`（iOS `Resources/classroom-rewards.js` 同文件）；规则对齐原生：访问 +12、答对 ×6、满分 +20、连击从第二份起 +12、重做按场景去重、成就 ID 一致。
- 账本 key 由「服务 + 账号 + 课堂地址」派生；只有稳定 `data-scene-id` 才记账，匹配不到时显示“未计入进度”；旧 `v1` 账本不迁移、不删除，只在面板注明归属。
- 回归：`scripts/tests/classroom-rewards.test.mjs` 5 项、`ClassroomRewardsContractTest` 3 项（同一事件样例驱动 Kotlin 与 JS，并校验 iOS 副本逐字一致）。

### 10.5 取消句柄

- Android 邻页图片预取保存 Coil `Disposable` 并在翻页/退出时释放；iOS 画布媒体下载、图片预取保存任务句柄，退后台/退出时取消并丢弃迟到结果。

### 10.6 执行结果与未完成项

**执行结果（2026-11-21，Windows，JDK 21.0.11，Gradle 8.13 / AGP 8.13.0，SDK android-35）**

| 验证 | 命令 | 结果 |
| --- | --- | --- |
| 奖励脚本一致性 | `node --test scripts/tests/classroom-rewards.test.mjs` | 5 passed |
| 定向 JVM 测试 | `:app:testDebugUnitTest --tests ClassroomQuizCoordinatorTest --tests ClassroomRewardsContractTest --tests ClassroomUrlPolicyTest --tests AuthTokenRefreshCoordinatorTest` | 33 passed / 0 failed（18 URL 策略、7 测验协调、5 续签、3 奖励契约） |
| Debug 构建 | `:app:assembleDebug` | BUILD SUCCESSFUL |
| Lint | `:app:lintDebug` | 5 errors / 137 warnings / 6 hints（教室文件 0 error；剩余均为既有且与课堂无关，见下） |
| 设备 | `adb install` + App 启动 | APK 安装成功；App 启动到首页并进入「互动课堂」入口，无 crash；真实课堂数据未验证 |

说明：仓库路径含中文时 Gradle 测试 worker 的 Java `@argfile` 解码会丢类路径；本轮用仅含 ASCII 的临时驱动器映射运行测试，不改仓库结构。Kotlin 编译在该环境中改用 in-process 策略，避免 Kotlin daemon 卡死。

Lint 剩余 5 个 error 均为既有问题且不在课堂文件内：`SeeduplexRealtimeVoiceSession` 缺少录音权限检查、`local.properties` 的 Windows 路径未转义（本机生成文件）、`QrScannerScreen` 的 CameraX opt-in、`AppNavHost` 两处组合期导航访问。本轮为课堂 Media3 使用补充了 AndroidX `@OptIn(UnstableApi::class)`，课堂相关 opt-in error 从 38 个降为 0；全仓 lint 门禁仍为红，规则迁移/基线属于独立事项。

**未完成/环境限制**

- 真机或模拟器的完整课堂流程（真实账号、真实课件、竖横屏、语音、目录、翻页、草稿、提交、退出再进、换号、重复开不同课堂后的资源释放）未完成；本轮没有安装脱敏 fixture 服务依赖，模拟器虽在线但无法进入真实课堂数据。
- iOS 无 Xcode/Swift toolchain：`swift test`、App 构建、模拟器和真机均未执行；iOS 改动只有静态复查，不能表述为编译或设备通过。
- 全仓 lint 规则迁移、正式包名/签名切换仍作为独立事项；本轮只运行现有 lint。
- 网页奖励与原生账本仍各自独立；本轮只保证规则一致和网页账本按服务/账号/课堂隔离，不做跨账本迁移。
- 经典讲解合成、白板编辑、AI 同学对话等既有缺口未在本轮扩展。

## 11. 课堂投入识别（2026-11-24）

本轮在原生播放器补齐「课堂观察」事实链路与端侧推理接点。范围只覆盖互动课堂原生播放器；教师侧仍沿用已有课堂参与事实，不从摄像帧推断专注度。

### 11.1 已修复与验证

- 无脸/弱光等不可观察原因优先于「近期操作」：持续无脸达到 12 秒后，即使每 8 秒手动翻页，观察条仍显示「无法判断 · 持续未检测到人脸」；最近 10 秒窗口的翻页计数作为独立事实保留，不再把状态改成「近期有操作」。回归用例 `page turns every eight seconds never reset the no-face timer` 通过。
- 窗口使用相机帧采样时刻；课堂事件使用发生时的单调时刻，只进入截止时已发生的窗口；边界事件归属正在关闭的窗口，迟到事件不回溯改写旧窗口。自动翻页、重放和同一次失败提交的原样重试不计入主动操作。关闭、退后台、旋转、换课和退出均停止相机并清空窗口，旧会话回调带代次校验被丢弃。

### 11.2 模拟器端到端

设备：AVD `Medium_Phone_API_37.0`（API 37，1080×2400），模拟器前置摄像头为虚拟场景，画面中没有真人。服务端：`backend/tests/fixtures/classroom_playback_server.py`，`127.0.0.1:8000`，App API Base `http://10.0.2.2:8000/api/v1/`；账号 `student_demo / Demo123456`。入口：首页「互动课堂」→ 最近学习「自主学习 · 继续上课」→ 原生课堂第 4/6 页。

| 操作 | 结果 |
| --- | --- |
| 开启课堂观察并授权相机 | 通过；出现相机预览与「检测中」，Debug 构建显示「调试：课堂提醒预览（权重未发布）」 |
| 无真人画面持续 16 秒 | 通过；显示「无法判断 · 持续未检测到人脸」，事实行显示 `10秒窗口无法判断 · 持续未检测到人脸 · 翻页 0 交卷 0 提问 0` |
| 无脸期间每 8 秒手动翻页 3 次 | 通过；状态始终保持「无法判断 · 持续未检测到人脸」，翻页作为独立事实计数，未覆盖判定 |
| 开启调试预览权重（无脸） | 通过；20 秒后仍无学生提醒，预览行显示「测试权重不参与正式判断」 |
| 关闭观察 | 通过；`dumpsys media.camera` 显示 `DISCONNECT device 1 client for package com.example.campusai`，观察条回到「课堂观察未开启」 |
| 退后台→回前台 | 通过；后台时相机断开，回前台提示「课堂观察已在后台停止，返回后可重新开启」 |
| 竖屏→横屏旋转 | 通过；播放器重建、观察关闭、相机断开，需学生重新开启 |
| 保存并退出→再进入 | 通过；相机在退出确认时释放，新会话观察未开启、窗口从零开始 |

真机摄像头（含真实人脸、眼镜、逆光/弱光、机型差异）未执行；模拟器虚拟场景只能证明无脸与生命周期路径，不能替代真实摄像头验证。

2026-11-24 17:06 复核：fixture 登录后重新走首页「互动课堂」→ 最近学习 → 原生播放器，复跑相机授权、约 14 秒无脸、每 8 秒手动翻页 3 次（到第 4/6 页）、退后台和竖屏→横屏旋转；无脸判定未被翻页覆盖，后台和旋转后 `dumpsys media.camera` 活动客户端为空。显式关闭按钮在 Debug 导出行出现后被导出入口抢占为系统分享，未稳定复现其点击路径；“保存并退出→再进入”本轮未重跑，表中该两行沿用上一轮记录。

### 11.3 命令与结果

```powershell
# 离线管线（无第三方训练依赖，固定种子）
Set-Location ml\classroom_attention
$env:PYTHONPATH = 'src'
python -m unittest discover -s tests -v
python -m classroom_attention.cli run-synthetic --workdir datasets\synthetic_v1 --seed 20261124

# Android（JDK 21）
Set-Location ..\..\android
.\gradlew.bat --no-daemon --max-workers=2 :app:testDebugUnitTest --tests "*ClassroomAttention*"
.\gradlew.bat --no-daemon --max-workers=2 :app:testDebugUnitTest
.\gradlew.bat --no-daemon --max-workers=2 :app:assembleDebug
```

- 离线单元测试 21 项通过；`run-synthetic` 重跑得到与已存产物逐字节一致的窗口、κ、指标和 golden 样例。
- Android 课堂观察/投入定向测试 41 项通过（观察模型 17、导出 3、模型 10、提醒策略 11）；课堂作答协调 21 项通过。
- 全量 `:app:testDebugUnitTest`：808 项、6 失败、1 跳过。失败均为既有或工作区环境原因，与本轮改动无关：`PersonAnalyzerTest`（Mockito 未完成桩）、`ExpressionModelAssetContractTest`（Robolectric 资产缺失，含 AndroidTest 同名项）、`GlassControlCoverageTest`（仓库既有玻璃控件债务）、`ClassicDashboardOnlyContractTest`（既有首页契约）、`ClassroomRewardsContractTest`（当前工作区另一会话删除了 `ios/`，未纳入本轮提交）。
- `:app:assembleDebug` 成功，APK 安装到模拟器；Debug 包包含 `assets/classroom_attention/model-preview.json`（合成权重，`release.eligible=false`）。
- 当前发布状态：Release 无模型，只启用事实观察；Debug 可显式开启实验预览推理，不回写正式判断。没有真实试点数据，学生提醒保持关闭。

### 11.4 仍缺的输入

- 真实试点包含用于训练与发布验收的独立参与者。验收集至少需要 5 名完成标注的参与者。用最终模型及导出阈值回放后，按 [离线管线说明](../ml/classroom_attention/README.md#metrics-and-release-gate) 检查标注一致性、覆盖率、误提示和离题片段召回。
- 真机：Android 设备上的权限、前后台、旋转、退出、摄像头释放、头姿采样，以及开关观察时的播放流畅度和耗电对比。模拟器结论不能替代。
