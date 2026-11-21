# CampusMate iOS

CampusMate 的原生 iOS 客户端，Swift 6 + SwiftUI，最低 iOS 17，支持 iPhone 与 iPad。界面、品牌资产与交互流程以当前 Android 客户端为准；系统能力（返回手势、键盘、文件/照片选择、分享、预览、日期选择、权限弹窗、本地通知、触觉反馈、动态字体、无障碍）在保留 Android 产品设计的前提下接入。

## 运行

1. 使用 Xcode 16 或更新版本打开 `CampusMate.xcodeproj`。
2. 选择 `CampusMate` Scheme 和一个 iPhone / iPad 模拟器。
3. 按 `⌘R` 运行，或在登录页的「服务连接」中填写后端地址。

真机运行前，在 Target → Signing & Capabilities 选择开发团队，并把占位 Bundle Identifier `com.example.campusmate` 改成自己的唯一标识。

## 结构

```text
ios/
├── CampusMate.xcodeproj/            # Xcode 工程与共享 Scheme
├── CampusMate/
│   ├── App/                         # AppModel、分页资源、共享行视图
│   ├── Design/                      # CampusTheme（色板/字号/玻璃）、JournalStyle（手账纸张）
│   ├── Navigation/                  # CampusRoute、沉浸式页面骨架、二级导航与工作流 chrome
│   ├── Features/
│   │   ├── Home/                    # Twilight 校园场景首页（场景热点 + 五个拱门入口）
│   │   ├── Auth/                    # 登录（校园短片背景 + 海报兜底）
│   │   ├── Courses/                 # 图书馆书架、课程藏书详情、知识点、班级
│   │   ├── Tasks/                   # 待办手账、任务卡编辑/导入、待办日历
│   │   ├── Notices/                 # 通知与提醒、通知详情
│   │   ├── Exams/                   # 考试倒计时、时间线、编辑
│   │   ├── Community/               # 校园论坛、热门话题、发帖与评论
│   │   ├── Focus/                   # 自习室、沉浸式专注、总结、学习足迹、签到
│   │   ├── Assistant/               # CPM 对话与工作流入口
│   │   ├── Classroom/               # 互动课堂、共同课堂
│   │   ├── Workflows/               # 目标、学习计划、期末复习、课程研究、通知事务
│   │   ├── Profile/                 # 我的、账号、设置、个人文件与收藏、扫码登录
│   │   └── Integrations/            # 学习通、教务系统
│   ├── Platform/                    # Keychain、音频、实时语音、通知提醒、可信 WebView
│   ├── Resources/                   # 从 Android 复制的环境声（转 m4a）与登录短片
│   └── Assets.xcassets/             # 从 Android drawable-nodpi 复制的品牌素材
├── CampusMateUITests/               # 原生 UI 流程与主要界面截图
└── scripts/validate.py              # 隔离后端 + Core 测试（可加 --ui）
```

## 设计来源

- 色板、字号、圆角、玻璃与手账质感来自 `android/.../ui/theme`、`ui/components/CampusKit.kt`、`ui/screens/tasks/TaskJournalStyle.kt`。
- 首页布局来自 `TwilightDashboardScreen.kt`（场景比例 841:1870、三个场景热点、五个拱门入口）。
- 图书馆、待办、通知、考试、社区、我的、自习室、CPM、共同课堂均按对应 Android 屏幕的层级与组件重建。
- 图片、视频与环境声直接取自 `android/app/src/main/res/drawable-nodpi` 与 `res/raw`；Ogg 环境声在导入时转为 m4a。

## 构建与测试

```bash
xcodebuild -project CampusMate.xcodeproj -scheme CampusMate -configuration Debug \
  -destination 'platform=iOS Simulator,id=<UDID>' \
  -derivedDataPath /tmp/campus-dd build
```

`ios/scripts/validate.py` 会启动一个显式指定临时数据库的隔离后端，运行 CampusCore 测试；加 `--build` 会继续构建 App target（需要完整 Xcode），加 `--ui --device <UDID>` 会继续运行原生 UI 测试。脚本拒绝复用已占用 18927 端口的服务。模拟器构建使用 Xcode 默认签名，不要设置 `CODE_SIGNING_ALLOWED=NO`：禁用签名可能使模拟器应用缺少钥匙串访问所需的签名权限，导致登录和会话恢复测试失败。

在受限沙箱中（SwiftPM 无法应用 sandbox profile 时）需要额外传入：

```bash
OTHER_SWIFT_FLAGS='$(inherited) -disable-sandbox'
```

并在运行前执行 `defaults write com.apple.dt.Xcode IDEPackageSupportDisableManifestSandbox -bool YES`。这是本机环境的绕过方式，不写入工程配置。

## 已知边界

- iOS 不能读取其他应用的通知：通知整理使用服务端同步、手动粘贴提取和本机提醒，不提供虚假的通知监听。
- 学习通、课堂生成和语音客户端已接入；真实学校连接、语音效果与后台音频仍需账号、服务及真机验收。
- iOS 的 RTC 音视频 SDK、摄像头模型推理、数字人渲染与相机二维码扫描尚未实现；当前共同课堂支持邀请、消息及页码，网页登录二维码需要粘贴内容。不得将这些能力表述为仅待真机验收。
- 模型共建使用系统照片选择或相机拍摄单张图片，上传后可按编号删除自己的样本；multipart 契约已有自动化测试，照片选择、真实相机与上传流程仍需在目标设备验收。
- 本地提醒按当前账号的完整待办/考试快照统一调度，遵守已完成状态、考试提醒开关及待办提前量；退出账号、切换服务或关闭提醒会清除旧通知。
- 课堂播放依赖服务端返回的可信 Origin 与 `browser_embed_available`；不满足时不提供打开按钮。
- 课堂 AI 同学沿用上游课堂的 `ClassmatePanes`（换页发言、沉默、点名与预算）；`TrustedWebView` 通过 `injectedScript` 注入 `ClassroomRewards.script(accountKey:classroom:)`、`ClassroomMobileLayout.script` 和 `ClassroomSlideTheme.script`：奖励脚本与 Android `assets/classroom-rewards.js` 共用同一份文件（`scripts/tests/classroom-rewards.test.mjs` 校验逐字一致），规则对齐原生 `ClassroomRewardsEngine`（访问 +12、答对 ×6、满分 +20、连击从第二份起 +12、重做按场景去重），账本按服务 + 账号 + 课堂隔离；只有稳定 `data-scene-id` 才记账，旧 v1 账本不迁移也不删除。中者与 Android `classroomMobileFix` 使用同一份窄屏布局契约（对话区拖拽手柄、课件双指缩放、教师气泡收起），后者统一课堂配色与中文字体。已在本机 Xcode 27.1 的 `CampusMate SE Audit` 模拟器验证构建和 7 项原生 UI 测试；测试前重置模拟器，避免上一次运行残留的横屏/返回态造成假失败。真机仍未验收。

## 原生互动课堂

- 入口：首页「互动课堂 → 原生课堂」先选课程；课程详情的「原生课堂」直接列出该课程的工作台、舞台与续读页码。原来的「自主选题课堂」「互动课堂」「同学一起学」入口不变；经典自主选题/课程课堂生成成功后，`ClassicClassroomView` 额外提供「在 App 内播放」。
- 数据：受管工作台用 `course_id + workspace_id + stage_id + scene_id`，读取 stage document 与 `/playback`；经典课堂用 `session_id`，读取 `.../{session}/playback` 的 `scenes[].content` 并投影成同构计划/文档，不需要伪造 `workspace_id`。计划与文档必须 revision 一致、scene id 集合一致才播放；经典额外比较 `content_version`，其稳定哈希参与 revision、快照刷新与音频缓存键。续播优先本地 `progress.sceneID`，该页被删除时退回收到的 `start_index`。
- 渲染：`NativeSlideSurface` 按 1000×562.5 画布绘制 text/shape/image/audio/video；经典站内图片与画布媒体的 `src` 走 `APIClient` 鉴权下载，绝对外链不请求，图片与画布媒体缓存键包含当前 `revision`（经典由 `content_version` 稳定哈希得到）。旧 `content.slide` 回退到讲义版面；`NativeQuizPanel`、`NativePBLPanel`、`NativeSimulationPanel` 与受限 `WKWebView` 分别处理 quiz/PBL/simulation/sandbox。受管课堂的讲解音频只在用户点击后合成，下载校验 audio 后落本地缓存，用 `AVPlayer` 播放；经典 playback 已下发 `actions[].payload.audioUrl` 时按 `action_id` 关联 `speech` 与 `media[]`，校验 `supported/available` 后走同一套下载/缓存/播放器，无成品时显示真实原因并提示回网页课堂，不调用受管合成端点。
- 播放入口：经典 `session_id` 课堂和自主选题课堂生成成功后显示「进入原生课堂」。有效的受信链接提供「网页兼容」入口。原生进度按账号和课堂保存，已访问页按 scene id 去重。网页进度继续使用原会话。
- 原生课件采用安卓的暮色黑板设计。竖屏将 PPT 放在 AI 老师与讲稿上方，横屏并排显示。翻页、目录、讲解、同学与白板位于底栏。受管课堂的白板正文可只读查看，白板编辑和 AI 同学讨论继续通过可用的网页入口完成。
- 性能样本：`ClassroomPerformanceProbe` 记录冷开/热开首屏、播放计划请求、翻页、峰值内存与失败次数，落在 `Application Support/CampusMate/ClassroomPerformance.json`；播放器「更多 → 查看性能样本」可读。服务端生成耗时单独统计。
- 覆盖、旧课兼容、性能口径、未验证项与接口缺口见 [`docs/native-classroom-ios.md`](../docs/native-classroom-ios.md)；单测在 `Packages/CampusCore/Tests/CampusCoreTests/NativeClassroomTests.swift`。当前 Windows 环境无 Xcode/Swift，`scripts/validate.py --build` 启动隔离后端后在 `swift test` 步骤报 `FileNotFoundError: [WinError 2]`，App target、CampusCore 单测、模拟器与真机均未进入；已完成后端播放契约 24 项测试和 12 个改动 Swift 文件的语法解析。`scripts/validate.py --build --ui --device <UDID>` 需在完整 Xcode 环境执行。
- UI 测试标识：`native.classroom.player`、`native.classroom.close`、`native.classroom.outline`、`native.classroom.previous`、`native.classroom.next`、`native.quiz.submit`、`native.pbl.<taskID>`、`classic.classroom.nativePlay`。

## 语音输入

- cpm（Assistant）与共同课堂（LearningRoom）文字输入框共用 `SpeechInputButton`：录音（16k/单声道/PCM16 WAV，≤60s）经 `AssistantSpeech` 上传后端 `assistant/asr` 本地识别后回填。按钮统一 44pt 命中区域、VoiceOver 录音/识别状态，并在识别期间显示进度与停止入口。
- 上传使用 120 秒独立超时；`ASRPolicy` 把 `ASR_BUSY`/`ASR_UNAVAILABLE` 映射为可重试提示，把体积/时长错误映射为分段输入提示。课堂发送在 `await` 前清空输入并仅在失败时恢复，避免吞掉并发回填的识别文本。
- 麦克风按钮在已有录音时始终允许结束录音，消息发送状态只限制新录音；避免 CPM 录音后发送已有文字时无法手动停止。
- 验证：`swift test --filter ASRPolicyTests` 已通过 3 项测试（包含 CampusCore 与测试目标编译），相关 App 源文件的 `swiftc -parse` 通过；语法检查不代表 App 构建通过。App target 与 UI 测试仍需要完整 Xcode，当前机器仅 Command Line Tools；真机录音、权限拒绝、来电中断、切后台和 60 秒自动停止均未验收。
