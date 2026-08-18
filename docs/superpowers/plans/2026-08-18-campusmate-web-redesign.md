# CampusMate Web 三页重设计实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 将待办、校园论坛列表、发布帖子页统一为参考图中的 CampusMate 桌面布局，并保留真实 API 与可用交互。

**Architecture:** 复用现有 `AppShell`、`UiIcon`、`CommunityPostCard`、`ImageUploader` 与 student API；页面级视图只管理状态和请求，新增一套共享视觉覆盖样式。论坛发布从列表内嵌表单抽为独立路由，同时保留返回列表和实时预览。

**Tech Stack:** Vue 3 `<script setup>`、Vue Router、Phosphor Icons、Vite、现有 Axios 服务层。

**Spec:** 用户提供的三张 CampusMate 参考截图与 pasted-text.txt 设计要求。

## Global Constraints

- 三页必须复用统一 Sidebar / Header / AppShell，不把截图当背景。
- 核心控件必须可点击并连接已有 API；后端不可用时显示明确错误或空状态。
- 桌面优先，兼容 320px、768px、1024px、1440px。

### Task 1: 任务页视觉与入口

**Files:**
- Modify: `web/src/views/student/StudentTasksView.vue`
- Modify: `web/src/styles/student-pages.css`
- Add: `web/public/assets/generated/tasks-hero-illustration.png`

- [ ] 在任务 Hero 中放置真实插画资源、保持统计和工具栏交互。
- [ ] 运行 `npm run build`，确认任务页编译通过。

### Task 2: 论坛列表双栏与真实筛选

**Files:**
- Modify: `web/src/views/student/StudentCommunityView.vue`
- Modify: `web/src/styles/student-community.css`

- [ ] 让发布按钮跳转独立发布路由，分类/搜索/排序继续调用 API。
- [ ] 增加热门话题、公告、小贴士和空/错误状态。
- [ ] 运行构建并检查列表交互。

### Task 3: 独立发布帖子页

**Files:**
- Add: `web/src/views/student/StudentCommunityCreateView.vue`
- Modify: `web/src/router.js`
- Modify: `web/src/styles/student-community.css`

- [ ] 实现标题、正文、分类、图片上传、匿名、地点、标签、评论开关、草稿、预览与发布。
- [ ] 发布调用 `createCommunityPost`，上传复用 `ImageUploader`，成功后跳转论坛。
- [ ] 运行 `npm run build` 和浏览器检查。

### Task 4: 交付验证

- [ ] `npm run build`
- [ ] 在 1440px 与移动断点检查 `/tasks`、`/community`、`/community/create`。
- [ ] 保存 `web/design-qa.md`，记录通过项与已知后端依赖。
