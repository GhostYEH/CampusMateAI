# CampusMate AI · HarmonyOS NEXT

`harmony/` 是独立的 ArkTS / ArkUI 客户端，界面、中文文案、主题、五栏导航和功能入口均以 `android/` 为只读基准；Android 源码不会被鸿蒙构建修改。

## 环境与构建

- DevEco Studio：通过本机环境变量 `DEVECO_HOME` 指向安装目录
- HarmonyOS / OpenHarmony SDK：6.1.1（API 24）
- Hvigor `modelVersion`：6.1.1

PowerShell 构建命令：

```powershell
$hvigor = Join-Path $env:DEVECO_HOME 'tools\hvigor\bin\hvigorw.bat'
$env:PATH = "$(Join-Path $env:DEVECO_HOME 'tools\node');$(Join-Path $env:DEVECO_HOME 'tools\hvigor\bin');$env:PATH"
$env:DEVECO_SDK_HOME = Join-Path $env:DEVECO_HOME 'sdk'
& $hvigor assembleApp --no-daemon
```

单元测试：

```powershell
& $hvigor test --no-daemon
```

构建产物：`entry/build/default/outputs/default/app/entry-default.hap`。

## 本地表情与学习行为识别

两条识别链路都在 HarmonyOS 设备本地执行，不上传、不保存相机画面：

- 表情识别使用 `rawfile/models/expression/campusmate_expression_v2.ms`。只有在 CPM/AI 页明确同意并授予相机权限后才会启动；离开页面、应用转入后台、退出登录或组件销毁时会停止。只有通过人脸质量、置信度、连续稳定性和时效检查的标签才会随对话发送。
- 学习行为识别使用 `rawfile/models/behavior/campusmate_behavior_v34.ms` 单帧人体 ROI 模型，并在需要时用 `rawfile/models/behavior/campusmate_tsm_mobilenetv2_v4.ms` 的 8 帧时序结果确认与融合。TSM V4 缺失或推理失败时明确降级为 V3.4；不稳定、无人或已停止的结果不会显示为稳定标签或触发提醒。
- 行为相机只在后端成功创建或恢复 `focus` 专注会话后启动；短休息、暂停、结束、切换模式、返回、页面隐藏和组件销毁都会停止。相机或模型失败不会回滚已成功的后端会话；相机帧最快每 500 ms 分析一次。

行为模型的输入/输出契约、标签、校准参数、SHA-256 和 TSM 转换对齐阈值记录在 `rawfile/models/behavior/model_card.json`。

## 本地表情与学习行为识别

两条识别链路都在 HarmonyOS 设备本地执行，不上传、不保存相机画面：

- 表情识别使用 `rawfile/models/expression/campusmate_expression_v2.ms`。用户只有在 CPM/AI 页明确同意并授予相机权限后才会启动；离开 CPM 页、应用转入后台、退出登录或组件销毁时会停止。链路为 `MindSporeExpressionProvider -> ExpressionRecognitionService -> withExpressionSignal`；只有通过人脸质量、置信度、连续稳定性和时效检查的标签才会随对话发送。
- 学习行为识别使用 `rawfile/models/behavior/campusmate_behavior_v34.ms` 单帧人体 ROI 模型，并在需要时用 `rawfile/models/behavior/campusmate_tsm_mobilenetv2_v4.ms` 的 8 帧时序结果做确认与融合。TSM V4 缺失或推理失败时会明确降级为 V3.4，不伪造时序结果；不稳定、无人或已停止的结果不会显示为稳定标签或触发提醒。
- 行为相机只在后端成功创建或恢复 `focus` 专注会话后启动；短休息/长休息不启动，暂停、结束、切换模式、返回、页面隐藏和组件销毁都会停止。相机或模型失败不会回滚已成功的后端会话。相机帧最快每 500 ms 分析一次。

行为模型的输入/输出契约、标签、校准参数、SHA-256 和 TSM 转换对齐阈值记录在 `rawfile/models/behavior/model_card.json`。

## 已接入页面

- 与 Android 相同素材的全屏视频登录页、海报兜底、渐变、账号/密码校验和真实登录
- 首页、课程、待办、AI 校园助手、我的五栏浮动导航
- 考试安排、专注自习
- 通知整理、文件、校园论坛、收藏、系统设置、账号与隐私、关于
- 深浅主题、减少动态效果、退出登录

## 原生导航与页面转场

登录后的五栏主界面是 ArkUI `Navigation` 的根页面，所有二级页面均由同一个 `NavPathStack` 管理，并使用标准 `NavDestination` 承载。社区详情与编辑、扫码确认、教务登录与课表等连续流程会形成真实的页面栈；页面标题栏返回、系统返回键和侧滑返回共享同一套 Pop 语义。

课程详情、待办详情、考试详情/编辑、通知详情/来源设置和课表课程详情也使用子路由；筛选项、确认弹窗和手动整理结果仍保留在所属页面内，不会伪装成独立页面。

二级页面使用 Navigation 的系统默认 Push/Pop 转场：打开时从右向左进入，关闭时从左向右退出，并由系统处理非线性曲线和交互式返回进度。开启“减少动态效果”后，路由入栈、出栈和清栈均禁用转场动画。

登录后会从真实后端读取用户、课程、待办、校园通知、论坛热门帖子、考试、专注记录、文件和收藏；AI 对话、待办完成/恢复、专注开始/暂停/继续/结束也调用真实接口。

## 后端地址

API Base URL 集中在 `entry/src/main/ets/core/ApiConfig.ets`，业务页面不直接写地址。

- Debug（DevEco Previewer 同机）：`http://127.0.0.1:8000/api/v1`
- Debug（独立 DevEco Emulator）：需把 `ApiConfig.ets` 中的 `DEV_HOST` 改为 Windows 宿主机当前局域网 IPv4（PowerShell `ipconfig` 查看），例如 `192.168.1.100`，再重新构建。**不要把具体局域网 IP 提交到仓库。**
- Release：`https://api.campusmate.example.com/api/v1`（正式 HTTPS 占位，禁止 HTTP）

HarmonyOS Emulator 没有 Android 的 `10.0.2.2` 宿主机映射，`127.0.0.1` 在独立模拟器中指向模拟器自身而非 Windows，因此 Emulator 调试必须使用 Windows 局域网 IPv4。

后端必须 `uvicorn app.main:app --host 0.0.0.0 --port 8000`，且 Windows 防火墙允许 Private 网络 TCP 8000 入站。

## 原样迁移的视觉资源

- `login_campus.mp4`
- `campus_login_poster.png`
- `exam_calendar_hero.png`
- 个人头像参考图

这些资源均复制到鸿蒙目录，未修改 Android 原文件。

## 已验证能力与平台差异

认证已保存 access/refresh 双 token，并支持并发 401 的单航班刷新、刷新后原请求重放一次以及会话失效清理。敏感 token 由独立 TokenStore 使用 AssetStoreKit 保存，不写入普通 Preferences 或日志。

本轮在本机 API 24 SDK 中确认：`ohos.permission.SUBSCRIBE_NOTIFICATION` 是 `system_basic`、`system_grant` 权限，不是普通运行时权限。工程已恢复 `NotificationSubscriberExtensionAbility` 注册、权限声明和授权入口；通知页会调用 `notificationExtensionSubscription.openSubscriptionSettings` 拉起系统授权页，并在返回后通过 `isUserGranted` 刷新状态。该能力仍需在 AGC/签名配置中获得对应资质；没有权限证书时不能安装或不能打开授权页，不能通过代码绕过。该订阅接口面向 HarmonyOS 通知扩展/穿戴同步场景，不等同于普通应用可无条件读取同一手机上的微信、企业微信、QQ/TIM 通知。当前可用来源仍包括后端站内通知、学习通账号同步和用户手动粘贴；来源解析、三个 IM 独立白名单、群名精确匹配与本地分类继续采用 fail-closed。

通知可靠队列尚未完成：当前本地记录仍使用 Preferences，不是 ArkData/RDB Outbox，失败重试与 App 重启恢复不能视为已对齐。完整状态见 `PARITY_AUDIT.md`。

表情与行为模型已完成本地代码接入、契约测试和 API 24 SDK 编译；这不等于已通过带前置摄像头的 API 24 真机验收。当前环境没有连接的 HDC 目标，且工程未配置签名，因此权限弹窗、摄像头帧回调、真机 MindSpore Lite 加载和前后台切换仍是发布前必验项。

HAP 当前未配置项目签名；连接模拟器或真机后，先在 DevEco Studio 的 Signing Configs 中使用开发者调试证书重新构建，再执行：

```powershell
$hdc='D:\DevEco Studio\sdk\default\openharmony\toolchains\hdc.exe'
& $hdc list targets
& $hdc install -r '.\entry\build\default\outputs\default\app\entry-default.hap'
& $hdc shell aa start -b com.example.campusmate -a EntryAbility
& $hdc shell hilog -x | Select-String 'CampusMate|MindSpore|Camera|EntryAbility'
```

验收时应在真机上分别覆盖：首次拒绝/同意相机权限、CPM 页进出与前后台、专注开始/暂停/继续/结束、休息模式、无人体画面、TSM 降级以及 `COMPUTER` 连续确认。
