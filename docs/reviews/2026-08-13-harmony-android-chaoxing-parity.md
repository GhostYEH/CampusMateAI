# Android 与鸿蒙学习通/通知流程对照

## 审计范围

本报告仅基于源码进行只读检查。审计过程中没有修改 `android/` 或 `harmony/` 下的文件。

## 结论

两端在“获取其他应用通知并转为 CampusMate 通知/待办”的总体方向一致，但在“登录并连接学习通账号、从学习通后端主动同步数据”的流程上不一致：Android 已有完整绑定流程，鸿蒙当前没有对应实现。

## 系统通知监听流程

| 环节 | Android | 鸿蒙 | 结论 |
| --- | --- | --- | --- |
| 系统通知订阅 | `CampusNotificationListenerService` 接收系统通知 | `NotificationSubscriber` / `notificationSubscriberManager` 启停订阅 | 一致 |
| 来源识别 | 支持微信、企业微信、学习通、QQ 与其他来源 | 支持微信、学习通、QQ 与其他来源 | 基本一致；Android 额外明确支持企业微信 |
| 来源开关/过滤 | `NotificationSourceSettings`、群白名单和内容过滤 | `NotificationSourceSettings` 与端侧过滤 | 方向一致，Android 当前过滤与批处理更细 |
| 本地暂存与去重 | Room 队列、指纹、会话归并与延迟任务 | 本地通知记录、指纹去重 | 方向一致，具体批处理策略不同 |
| 上传后端 | `NoticeUploadWorker` 调用通知批量接收接口 | `NotificationIngestService` 调用后端接收接口 | 一致 |
| 转待办 | 后端抽取结果进入统一通知与个人待办 | 后端抽取结果进入统一通知与个人待办 | 一致 |
| 手动粘贴通知 | 通知页支持手动整理 | 通知页支持手动整理 | 一致 |

鸿蒙通知页显示“正在监听微信、QQ等应用通知”，来源解析代码同时识别学习通包名 `com.chaoxing.mobile`。因此学习通 App 自身产生的系统通知可以作为移动端通知来源，但这不等价于登录学习通账号并主动拉取其课程、作业和通知数据。

## 学习通账号连接与主动同步流程

| 环节 | Android | 鸿蒙 | 结论 |
| --- | --- | --- | --- |
| 学习通账号/密码登录 | `ChaoxingLoginForm` 与 `ChaoxingViewModel.login` | 未发现对应页面、状态或 API 调用 | 不一致 |
| 连接状态检查 | `getChaoxingStatus`，区分 online/offline/expired/unavailable | 未发现 `/chaoxing/status` 调用 | 不一致 |
| 手动同步 | `syncNow` 调用 `/chaoxing/sync` | 未发现 `/chaoxing/sync` 调用 | 不一致 |
| 周期同步 | `ChaoxingSyncScheduler` / `ChaoxingSyncWorker` | 未发现对应调度器 | 不一致 |
| 失效恢复 | 会话失效后提示重新登录并保留已有数据 | 未发现对应状态 | 不一致 |
| 解除连接 | `disconnect` 调用 `/chaoxing/disconnect` | 未发现对应入口或 API 调用 | 不一致 |
| 展示同步统计 | 展示课程、教师、未完成作业、通知数量 | 未发现对应连接统计界面 | 不一致 |
| 读取后端同步数据 | 课程、任务、通知页面读取后端接口 | `Index.ets` 同样读取 `courses`、`tasks`、`notices` | 数据消费一致 |

## 多端数据同步判断

Android、鸿蒙和 Web 均使用 CampusMate 登录令牌访问后端课程、个人任务和通知接口。学习通主动同步所得数据在后端按 CampusMate `user_id` 写入 `courses`、`personal_tasks` 与 `notices`，所以同一 CampusMate 账号的各端会读取同一份数据。

鸿蒙虽然没有主动发起学习通账号绑定与拉取同步，但在 Web 或 Android 完成同步后，鸿蒙现有的 `courses`、`tasks`、`notices` 请求可以消费相同账号的后端结果。这实现了数据层面的多端同步，但不代表鸿蒙交互流程已经与 Android 完全一致。

## 建议

如果以后要求鸿蒙在交互层也完全对齐 Android，需要单独实现学习通连接页面、状态模型、登录/同步/解除 API 调用和周期同步调度。本次任务按约束只报告差异，不修改鸿蒙端。
