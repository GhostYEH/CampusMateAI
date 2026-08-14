# 微信小程序前后端联调强化 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 修复微信小程序真实模式接口契约、登录态和业务数据流，使关键流程可端到端运行。

**Architecture:** 页面继续依赖统一仓库；仓库负责 DTO 映射、token 生命周期和错误归一化。真实数据与 Mock 数据按模式严格隔离。

**Tech Stack:** 微信小程序 TypeScript、Node.js 契约检查、FastAPI/Pydantic、pytest。

## Global Constraints

- 不修改 `android/` 下任何文件。
- 不静默用 Mock 数据掩盖真实接口错误。
- 写操作仅在后端成功后显示成功。

---

### Task 1: 联调契约回归检查

**Files:**
- Create: `wx/scripts/check_backend_contracts.js`
- Modify: `wx/package.json`

- [ ] 编写覆盖 `/tasks`、`content`、`stream: false`、refresh token、真实课程/通知读取和异步保存的失败检查。
- [ ] 运行 `npm run check:contracts`，确认因当前契约错位失败。

### Task 2: 请求层与 DTO 映射

**Files:**
- Modify: `wx/miniprogram/services/types.ts`
- Create: `wx/miniprogram/services/date-utils.ts`
- Modify: `wx/miniprogram/services/repository.ts`

- [ ] 对齐认证、待办、通知解析和聊天契约。
- [ ] 增加 token 刷新、会话模式隔离、错误透传和真实课程/通知数据方法。
- [ ] 运行契约检查和 TypeScript 检查。

### Task 3: 页面真实数据流

**Files:**
- Modify: `wx/miniprogram/pages/index/index.ts`
- Modify: `wx/miniprogram/pages/courses/courses.ts`
- Modify: `wx/miniprogram/pages/notices/notices.ts`
- Modify: `wx/miniprogram/pages/tasks/tasks.ts`
- Modify: `wx/miniprogram/pages/profile/profile.ts`
- Modify: `wx/miniprogram/custom-tab-bar/index.ts`

- [ ] 将课程、通知、首页和角标切换为异步仓库数据。
- [ ] 修正多任务通知保存、动态周日期和模式切换重新认证。
- [ ] 运行小程序完整检查。

### Task 4: 端到端验证

**Files:**
- Test only

- [ ] 运行后端全量 pytest。
- [ ] 使用 FastAPI TestClient 验证登录、课程、通知、待办和聊天。
- [ ] 运行 `git diff --check` 并确认没有对 Android 执行写入。

