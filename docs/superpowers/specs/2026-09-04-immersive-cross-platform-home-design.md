# 沉浸式跨端首页与失物招领客户端下线设计

## 目标

将 Android 与 HarmonyOS 登录后首页统一重构为截图参考的沉浸式校园首页，同时保留底部五栏导航和真实数据能力；从两端客户端下线失物招领，不影响校园社区。

## 设计

首页采用固定信息层级，不再渲染后端运营 Banner 轮播：

1. 背景层使用现有校园海报资源，叠加浅蓝渐变和低透明度遮罩，让状态栏区域与首页背景连续。
2. 顶部问候区显示用户头像、姓名和简短问候；右侧显示通知玻璃按钮（带未读红点）和扫码玻璃按钮。
3. AI 学习助手使用 CPM 数字人资源作为左侧主视觉，卡片支持进入 `counselor`/CPM 页面。
4. 主入口使用并列大卡片：橙色“校园社区”进入 `community`，蓝色“专注自习”进入 `focus`。
5. 下方保留信息总览、今日课程、近期截止和校园动态等真实数据，采用白色/半透明圆角卡片和蓝紫主色。
6. 所有可滚动内容继续为底部悬浮导航预留现有安全空间；不修改 Android `CampusDock` 或 Harmony `AppDock` 的项目、样式、手势和选中策略。

## 跨端实现边界

- Android 在 Compose dashboard 中实现固定首页，复用 `cpm_avatar_fallback` 与 `campus_login_poster`。
- HarmonyOS 在 ArkUI dashboard 中实现等价布局，复用 `cpm_avatar` 与 `campus_login_poster`。
- 两端继续使用现有 `notifications` 与 `qr_scanner` 路由；通知状态沿用已有数据，不新增后端接口。
- 首页不再主动请求或消费 `home-banners`；后端 Banner API 保留，供其他客户端/管理端兼容使用。

## 失物招领下线边界

下线 Android/Harmony 的失物招领页面、客户端路由、客户端仓库/模型、客户端请求、专属资源和测试。

保留：

- 后端 `student/lost-found` 接口、历史数据和迁移逻辑；
- 校园社区的 `lostfound` 分类及其帖子浏览、发布、详情、编辑、互动能力；
- 其他首页入口、底部导航和校园模块。

## 失败与降级

- 用户数据为空时显示现有默认问候、课程和任务空状态，不阻塞首页布局。
- 本地背景资源始终可用；图片加载失败不影响文字和按钮操作。
- 未读通知为零时隐藏红点；通知按钮仍可进入通知页。
- 现有减少动态效果设置继续生效，首页不新增强制动画。

## 验证

- Android：运行 dashboard/导航相关单元测试，并用仓库捆绑 JDK 21 执行 `:app:testDebugUnitTest` 与 `:app:assembleDebug`。
- HarmonyOS：运行 `hvigor test --no-daemon` 与 `hvigor assembleApp --no-daemon`（若本机未配置 DevEco 环境，记录为环境阻塞）。
- 静态检查：确认两端首页不再引用 `HomeBanner` 展示、不再暴露 `lostfound` 客户端路由；确认校园社区仍保留 `lostfound` 分类代码。
- 完成前检查 `git diff`、`git diff --cached`、`git status`，确保不包含密钥、本机路径或工作区原有无关改动。
