# OpenMAIC Campus Fusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `subagent-driven-development` (recommended) or `executing-plans` to implement one child plan at a time. Steps use checkbox (`- [ ]`) syntax for tracking. Do not start the next child plan until the current checkpoint is reviewed.

**Goal:** 将 OpenMAIC v1.0.3 的完整可用能力融合进 CampusMate 的课程页和作业场景，同时保持单一登录、单一课程权限体系和单一浏览器 React 运行时。

**Architecture:** `webreact/` 承担全部浏览器 UI；FastAPI 承担公开 API 与课程权限；仓库内受管 `openmaic-service/` 承担 OpenMAIC 服务端运行时和独立持久化。设计真源为 `docs/superpowers/specs/2026-09-18-openmaic-campus-fusion-design.md`。

**Tech Stack:** React 18、Vite、React Router、FastAPI、Pydantic、Node.js 22.19+、TypeScript、PostgreSQL、SSE、Vitest、Node test runner、pytest、Playwright。

## Global Constraints

- 只从固定 commit `e693e11a81644f84c258df73dbda378643520a62` 迁移正式源码。
- 本地参考副本只做视觉和交互比对，不复制未知来源文件。
- 每个子计划单独建立工作分支或 worktree，按任务逐次提交。
- 每个任务必须先看到指定测试失败，再写最小实现，再运行计划中的验证命令。
- 不修改 CampusMate 数据库结构，不引入第二登录，不使用整站 iframe，不加载第二份 React。
- 子计划中列出的路径是提交白名单；发现必须越界时先修订设计和计划。
- 每个子计划结束时运行 `git diff --check`、目标模块完整测试和构建，并请求代码审查。

## 子计划与依赖

| 顺序 | 子计划 | 交付物 | 前置依赖 |
| ---: | --- | --- | --- |
| 1 | [01 来源、服务骨架与内部认证](2026-09-18-openmaic-fusion-01-source-service.md) | 来源审计、受管 Node 服务、状态 API、内部断言 | 无 |
| 2 | [02 课程首页与桥接](2026-09-18-openmaic-fusion-02-courses-home-bridge.md) | 重构 `/courses`、右侧课程栏、课程 Stage 绑定 | 01 |
| 3 | [03 工作台、会话与流式运行](2026-09-18-openmaic-fusion-03-workbench-sessions.md) | 工作台、会话、消息、SSE、取消、重试、恢复 | 01、02 |
| 4 | [04 编辑器、播放器与白板](2026-09-18-openmaic-fusion-04-editor-player.md) | Stage 契约、编辑命令、场景元素、播放、白板 | 03 |
| 5 | [05 材料、媒体与生成工具](2026-09-18-openmaic-fusion-05-materials-media.md) | 材料、全格式导入导出、MP4、互动/PBL、媒体语音、多智能体、Job/i18n | 03、04 |
| 6 | [06 课程详情与作业讲解](2026-09-18-openmaic-fusion-06-course-task-explain.md) | 课程入口、讲解计划、讲解执行、追问与播放 | 03、04、05 |
| 7 | [07 持久化、安全与最终验收](2026-09-18-openmaic-fusion-07-persistence-acceptance.md) | PostgreSQL、健康检查、启动配置、安全回归、E2E | 01—06 |

```text
01 source/service/auth
        |
02 courses/home/binding
        |
03 workbench/session/SSE
        |
04 editor/player/whiteboard
        |
05 materials/import/export/media
        |
06 course/assignment explanation
        |
07 persistence/security/E2E
```

## 阶段检查点

### Checkpoint A：基础可用

完成 01—02 后必须证明：

- 固定来源和许可证可追溯。
- Node 服务不公开独立 UI，FastAPI 可安全探活。
- `/courses` 展示真实课程栏，并能幂等获得课程 Stage。
- 功能开关关闭时旧课程行为不变。

### Checkpoint B：核心创作闭环

完成 03—04 后必须证明：

- 用户可从课程提问进入工作台，刷新和断线后恢复。
- 编辑命令具备 revision 冲突和 commandId 幂等保护。
- 编辑器与播放器使用同一 Stage 契约。

### Checkpoint C：完整能力与课程融合

完成 05—06 后必须证明：

- 能力矩阵中的材料、导入导出、生成、语音和多智能体逐项可用。
- 作业内容只在授权和脱敏后进入讲解流程。
- 讲解结果可以继续追问、编辑和播放。

### Checkpoint D：发布候选

完成 07 后必须证明：

- 服务重启后数据恢复，依赖故障时课程页可降级。
- 后端、Web、Node 服务测试和构建全部通过。
- Playwright 覆盖课程提问、编辑播放、材料导入导出和作业讲解。
- 设计文档能力矩阵的每一行都有 `verified` 证据。

## 完成定义

全部子计划完成、四个检查点通过且代码审查无阻塞问题，才允许声明“完整融合”。仅有页面外观、代理接口或演示数据不得算作完成。
