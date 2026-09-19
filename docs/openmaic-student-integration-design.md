# OpenMAIC 与 CampusMate 完整融合设计

本文件与 `docs/openmaic-capability-matrix.md`、`docs/openmaic-deployment.md` 共同描述当前唯一有效边界。它不把现有课堂适配层称为完整迁移。

## v1.0.3 事实基线

官方 DSL 的 scene type 只有：

- `slide`
- `quiz`
- `interactive`
- `pbl`

`simulation`、`diagram`、`code`、`game`、`visualization3d` 和 `procedural-skill` 是 `interactive` 内部的 widget type；白板、TTS 和多智能体讨论是 Stage/Scene 字段或 Action，不是额外 scene type。CampusMate 的生成请求必须使用 requirement 表达意图，并在读取真实 Stage 后报告实际生成组成。

## 产品边界

CampusMate 保留四项事实源：JWT 身份、课程/作业、资料和权限。OpenMAIC 运行时只提供经过审计的内容 DSL、渲染、编辑、导入导出和 Provider 能力。用户在 `/courses`、课程详情、工作台和作业页面内完成全部操作，不跳转独立 OpenMAIC 首页，不出现第二导航、账号或课程库。

允许 iframe 的唯一范围是互动 HTML、3D、模拟或游戏内容本身。该 iframe 必须经过 HTML 净化、限制大小和类型，使用最小 `sandbox`，并且不能承载首页、工作台、编辑器或播放器整体。

## 现有适配层

以下能力已经存在并继续复用，不建立第二套适配层：

- `backend/app/services/openmaic/**` 的 HTTP 客户端、课程上下文、生成编排、状态/重试/历史和组成解析。
- `backend/app/api/routes/openmaic_classroom.py` 的 JWT、课程权限、状态、计划、生成、轮询、历史、组成和重试接口。
- Agent Runtime 的审批门、幂等、审计和 `interactive_classroom` handler。
- `webreact/src/components/interactive/**` 的课程详情课堂入口和受控播放容器。

这些能力不能被描述为首页、工作台、编辑器、导入导出或完整迁移。

## 目标融合流

```text
/courses
  ├─ 主输入：创建学习内容 / 快速询问
  ├─ 最近项目、文件夹、搜索、导入
  └─ 当前用户真实课程栏
       └─ courseId
           └─ workspace/stage 映射（服务端持久化并绑定 userId）
               ├─ chat/session（上下文由 FastAPI 裁剪）
               ├─ editor（DSL 命令、undo/redo、版本冲突）
               └─ player（场景、动作、白板、音频时间线）
```

`courseId`、`workspaceId` 和 `stageId` 永远分开传递。旧请求带来的响应必须通过课程 epoch 丢弃，避免切课串写。

## API 与身份

浏览器只调用 CampusMate API。FastAPI 在服务端重新读取并裁剪课程上下文，检查用户/课程/会话/映射四层归属，再通过短时最小 scope 断言调用受管服务。内部 URL、Cookie、JWT 和 Provider Key 不出现在前端。

OpenMAIC 不存在的取消接口不被伪造：生成任务的“停止查看”只停止本地轮询；重试表示 CampusMate 按原始用户输入提交新任务；恢复表示从 CampusMate 历史重新打开归属内容。

## 迁移顺序和验收

1. A：来源审计、受管服务、断言强制、状态代理和最近内容聚合。**已完成并验证**
   （来源声明真实值；断言是唯一信任入口；jti 落库且与写操作同事务；缺配置即拒绝启动；
   `fusion/status` 四态；`fusion/recent` 一次聚合取代浏览器逐课程请求）。
2. B：`/courses` 首页和真实课程栏。**已完成并验证**（入口按真实 capability 开放，
   无占位文案；深链 `?tab=mentoring&session=` 可在页面内打开已有课堂）。
3. C：课程映射、快速询问和工作台。**进行中**：工作台的持久化
   （`openmaic-service/src/workspace/**`）、FastAPI 网关
   （`backend/app/api/routes/openmaic_workspaces.py`，含 `Idempotency-Key` /
   `If-Match` 强制、412→409 翻译、内部地址不外泄）与课程内工作台面板
   （`webreact/src/components/openmaic/WorkspacePanel.jsx`，按真实 capability
   开关）已落地并验证；编辑器与播放器未接入。
   本轮补齐了**内容发现**这一层：文件夹树与站内搜索
   （`openmaic-service/src/discovery/**` + `backend/app/api/routes/openmaic_discovery.py`
   + `webreact/src/components/openmaic/DiscoveryPanel.jsx`），并让工作台可以归档到
   文件夹（`folder_id`）。文件夹与搜索的浏览器验收仍未执行。
4. D：DSL、编辑器和播放器。未开始。
5. E：材料、导入导出、高级能力和 Provider 设置。未开始。
6. F：作业讲解确认门和最小上下文。未开始。
7. G：安全回归、离线降级和浏览器验收。离线降级四态已验证；其余未开始。

每一行能力必须有源码依据、CampusMate 文件、契约、权限、测试、命令和证据；未实现能力不能显示为可点击入口。矩阵全部完成前，项目状态必须是“部分完成”。
