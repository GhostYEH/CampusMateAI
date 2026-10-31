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

`ios/scripts/validate.py` 会启动一个显式指定临时数据库的隔离后端，运行 CampusCore 测试；加 `--ui --device <UDID>` 会继续运行原生 UI 测试。脚本拒绝复用已占用 18927 端口的服务。模拟器构建使用 Xcode 默认签名，不要设置 `CODE_SIGNING_ALLOWED=NO`：禁用签名可能使模拟器应用缺少钥匙串访问所需的签名权限，导致登录和会话恢复测试失败。

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

## 语音输入

- cpm（Assistant）与共同课堂（LearningRoom）文字输入框均有麦克风按钮：录音（16k/单声道/PCM16 WAV，≤60s）经 `AssistantSpeech` 上传后端 `assistant/asr` 本地识别后回填。cpm 此前已接入；本轮为课堂输入框补上同一入口（复用 `AssistantSpeech`）。
- 验证：全量 `swiftc -parse` 通过（50 个源文件 0 error）；CampusCore 库 `swift build` 通过。`swift test` 需完整 Xcode 的 Swift Testing 宏插件，本机仅 Command Line Tools，无法运行测试目标（非代码问题）。
