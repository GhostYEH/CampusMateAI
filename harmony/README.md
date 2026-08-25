# CampusMate AI · HarmonyOS NEXT

`harmony/` 是独立的 ArkTS / ArkUI 客户端，界面、中文文案、主题、五栏导航和功能入口均以 `android/` 为只读基准；Android 源码不会被鸿蒙构建修改。

## 环境与构建

- DevEco Studio：`D:\DevEco Studio`
- HarmonyOS / OpenHarmony SDK：6.1.1（API 24）
- Hvigor `modelVersion`：6.1.1

PowerShell 构建命令：

```powershell
$env:PATH='D:\DevEco Studio\tools\node;D:\DevEco Studio\tools\hvigor\bin;' + $env:PATH
$env:DEVECO_SDK_HOME='D:\DevEco Studio\sdk'
& 'D:\DevEco Studio\tools\hvigor\bin\hvigorw.bat' assembleApp --no-daemon
```

单元测试：

```powershell
& 'D:\DevEco Studio\tools\hvigor\bin\hvigorw.bat' test --no-daemon
```

构建产物：`entry/build/default/outputs/default/app/entry-default.hap`。

## 已接入页面

- 与 Android 相同素材的全屏视频登录页、海报兜底、渐变、账号/密码校验和真实登录
- 首页、课程、待办、AI 校园助手、我的五栏浮动导航
- 考试安排、空教室、办事大厅、专注自习、失物招领
- 通知整理、文件、活动、收藏、系统设置、账号与隐私、关于
- 深浅主题、减少动态效果、退出登录

## 原生导航与页面转场

登录后的五栏主界面是 ArkUI `Navigation` 的根页面，所有二级页面均由同一个 `NavPathStack` 管理，并使用标准 `NavDestination` 承载。社区详情与编辑、扫码确认、教务登录与课表等连续流程会形成真实的页面栈；页面标题栏返回、系统返回键和侧滑返回共享同一套 Pop 语义。

课程详情、待办详情、考试详情/编辑、失物招领详情/发布/我的发布、通知详情/来源设置和课表课程详情也使用子路由；筛选项、确认弹窗和手动整理结果仍保留在所属页面内，不会伪装成独立页面。

二级页面使用 Navigation 的系统默认 Push/Pop 转场：打开时从右向左进入，关闭时从左向右退出，并由系统处理非线性曲线和交互式返回进度。开启“减少动态效果”后，路由入栈、出栈和清栈均禁用转场动画。

登录后会从真实后端读取用户、课程、待办、校园通知、考试、空教室、服务申请、失物招领、专注记录、活动、文件和收藏；AI 对话、待办完成/恢复、服务申请、失物发布、专注开始/暂停/继续/结束也调用真实接口。

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
- `hero_classroom.png`
- `hero_services.png`
- `hero_lost_found.png`
- 失物卡片图片和个人头像参考图

这些资源均复制到鸿蒙目录，未修改 Android 原文件。

## 已验证能力与平台差异

认证已保存 access/refresh 双 token，并支持并发 401 的单航班刷新、刷新后原请求重放一次以及会话失效清理。敏感 token 由独立 TokenStore 使用 AssetStoreKit 保存，不写入普通 Preferences 或日志。

本轮在本机 API 24 SDK 中确认：`ohos.permission.SUBSCRIBE_NOTIFICATION` 是 `system_basic`、`system_grant` 权限；当前 CampusMateAI 构建没有该资质，不能读取本机微信、企业微信、QQ/TIM 通知。工程已移除无效权限声明和 `NotificationSubscriberExtensionAbility` 注册，自动采集状态固定为 **UNAVAILABLE**。当前真实来源是后端站内通知、学习通账号同步和用户手动粘贴；学习通已接入状态、登录、立即同步与断开接口。来源解析、三个 IM 独立白名单、群名精确匹配与本地分类继续采用 fail-closed。

通知可靠队列尚未完成：当前本地记录仍使用 Preferences，不是 ArkData/RDB Outbox，失败重试与 App 重启恢复不能视为已对齐。完整状态见 `PARITY_AUDIT.md`。

Android 表情模型当前没有已验证可在 HarmonyOS API 24 运行的等价推理 runtime/模型产物。Harmony 已接入 `ExpressionRecognitionService` 与 AI 对话 `expression_signal` 数据通路，并使用 `UnavailableExpressionProvider` 安全降级：不会生成随机表情、不会伪装为真实识别，也不会上传相机画面；provider 不可用、信号不稳定或过期时，AI 对话会省略 `expression_signal`。后续只需实现同一 provider 契约并完成 API 24 真机验证，即可接入真实模型。

HAP 当前未配置项目签名；连接模拟器或真机后，可在 DevEco Studio 的 Signing Configs 中使用开发者调试证书签名运行。
