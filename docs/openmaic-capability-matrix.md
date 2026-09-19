# OpenMAIC 能力矩阵

来源固定为 [THU-MAIC/OpenMAIC v1.0.3](https://github.com/THU-MAIC/OpenMAIC/tree/v1.0.3)，commit `e693e11a81644f84c258df73dbda378643520a62`。状态只有在实现、自动化测试和验收证据同时具备时才能变为“已验证”。

| 能力 | v1.0.3 源文件 | 依赖 | CampusMate 目标文件 | API/数据契约 | 身份与权限 | 测试文件 | 验收命令 | 状态和证据 |
|---|---|---|---|---|---|---|---|---|
| 融合首页 | `app/page.tsx`、`components/discovery/**` | DSL、workspace 数据 | `webreact/src/pages/ParityPages.jsx` | `/courses` 聚合课程与 workspace 摘要 | JWT；仅当前用户课程 | `webreact/tests/openmaic-home.test.mjs` | `node --test ...`; `npm run build` | 未开始 |
| 最近项目 | `app/page.tsx`、`lib/utils/database.ts` | workspace 映射 | `webreact/src/features/openmaic/**` | 归属用户的最近 stage | userId 归属 | 同上 | 同上 | 未开始 |
| 文件夹 | `components/discovery/folder-*`、`app/api/folders/**` | workspace 存储 | `webreact/src/components/openmaic/**` | 文件夹与 stage 映射 | 用户私有 | `openmaic-folders.test.mjs` | 精确 node test | 未开始 |
| 搜索 | `app/page.tsx`、stage 列表 API | workspace 索引 | `webreact/src/features/openmaic/search.js` | 关键词只查用户可见内容 | 用户归属 | `openmaic-search.test.mjs` | 精确 node test | 未开始 |
| 真实课程侧栏 | — | CampusMate courses/assignments | `ParityPages.jsx`、`data/api.js` | 课程名、教师、学期/代码、待办、截止时间 | course access | `openmaic-course-rail.test.mjs` | 精确 node test | 未开始 |
| 选课与切课 | — | 课程详情、会话作用域 | `features/openmaic/courseScope.js` | 当前 `courseId` 显式传递 | JWT + course permission | `openmaic-course-switch.test.mjs` | 精确 node test | 未开始 |
| 快速询问 | `app/api/chat/**` | FastAPI 上下文裁剪、SSE | `pages/OpenMAICWorkspacePage.jsx` | 会话、流式消息、恢复、中断、重试 | user/course/session 四层归属 | `openmaic-quick-ask.test.mjs`、后端会话测试 | 前后端精确测试 | 未开始 |
| 工作台 | `app/workspace/page.tsx`、`components/workbench/**` | DSL、映射、编辑器 | `pages/OpenMAICWorkspacePage.jsx` | workspace/stage 映射，不暴露独立入口 | JWT + 映射归属 | workspace contract tests | build + 浏览器 | 未开始 |
| Stage/Scene DSL | `packages/@openmaic/dsl/src/stage.ts`、`action.ts` | TypeScript runtime | `openmaic-service/src/dsl/**` | versioned Stage/Scene/Action | 服务端校验归属 | `dsl.test.ts` | service test/typecheck | 未开始 |
| 编辑器 | `components/edit/**`、`components/stage/**` | DSL、资源引用 | `webreact/src/components/openmaic/editor/**` | 命令协议、undo/redo、版本冲突 | 当前 workspace | `openmaic-editor.test.mjs` | node test + build | 未开始 |
| 播放器 | `components/classroom/**`、`components/scene-renderers/**` | renderer、DSL | `webreact/src/components/openmaic/player/**` | 场景切换、播放动作 | stage 归属 | `openmaic-player.test.mjs` | node test + 浏览器 | 未开始 |
| 白板 | `packages/@openmaic/dsl/src/stage.ts`、`components/whiteboard/**` | renderer、同步协议 | player/editor whiteboard modules | whiteboard 与 stage version | session/stage 归属 | `openmaic-whiteboard.test.mjs` | node test | 未开始 |
| PPTX 导入 | `lib/import/use-import-pptx.ts`、`packages/@openmaic/importer/**` | importer、上传策略 | `openmaic-service/src/import/**` | 文件类型/大小、导入 Stage | JWT + workspace | `openmaic-import-pptx.test.mjs` | fixture test | 未开始 |
| `.maic.zip` 导入 | `lib/import/use-import-classroom.ts` | storage、DSL | same importer boundary | zip manifest + assets | workspace 归属 | `openmaic-import-maic.test.mjs` | fixture test | 未开始 |
| `.maic.zip` 导出 | `packages/@openmaic/storage/**` | assets、DSL | export service | versioned manifest | stage 归属 | `openmaic-export-maic.test.mjs` | fixture test | 未开始 |
| PPTX 导出 | `packages/pptxgenjs/**`、export routes | renderer、fonts | export service | output job/download | 当前用户 stage | `openmaic-export-pptx.test.mjs` | fixture test | 未开始 |
| Markdown 导出 | `lib/export/**` | DSL traversal | export service | sanitized markdown | stage 归属 | `openmaic-export-markdown.test.mjs` | fixture test | 未开始 |
| DOCX 导出 | `lib/export/**`、`docx` dependency | DSL traversal | export service | docx binary job | stage 归属 | `openmaic-export-docx.test.mjs` | fixture test | 未开始 |
| 材料上传/解析/引用 | `app/api/materials/**`、`app/api/extract-document` | size/type policy | FastAPI + service material boundary | material id, hash, references | course/workspace access | backend material tests | pytest + service test | 未开始 |
| Web 搜索 | `app/api/web-search/route.ts` | server provider | backend capability proxy | sanitized citations | server-only provider | backend SSRF/search tests | pytest | 未开始 |
| slide 生成 | `packages/@openmaic/generation/**` | Agent Runtime/provider | existing generation handler | requirement → Stage | approval gate | backend generation tests | pytest | 部分完成；现有适配层 |
| quiz 生成 | same | DSL/provider | service generation boundary | Stage scene type `quiz` | approval + course | generation fixture | service test | 未开始 |
| interactive 生成 | same | widget contracts | service generation boundary | `interactive` + widget type | approval + course | generation fixture | service test | 部分完成；需真实组合 |
| PBL 生成 | `app/api/pbl/**`、generation | provider | service generation boundary | `pbl` scene | approval + course | PBL tests | service test | 未开始 |
| simulation | `packages/@openmaic/dsl/src/interactive.ts`、renderer | interactive renderer | player sandbox | widget config | stage access + sandbox | widget contract | node test + browser | 未开始 |
| diagram | same | interactive renderer | player sandbox | widget config | stage access + sandbox | widget contract | node test + browser | 未开始 |
| code | same | interactive renderer | player sandbox | widget config | stage access + sandbox | widget contract | node test + browser | 未开始 |
| game | same | interactive renderer | player sandbox | widget config | stage access + sandbox | node test + browser | node test + browser | 未开始 |
| visualization3d | same | external CDN capability | player sandbox | explicit degraded state | no internal key | capability test | browser with CDN on/off | 未开始 |
| TTS | `app/api/generate/tts`、`stage.ts` voice config | server provider | service capability proxy | audio timeline/voice refs | provider key server-only | TTS security tests | pytest + service test | 未开始 |
| 多智能体讨论 | `components/roundtable/**`、stage config | agent runtime | workspace/player | agentIds + discussion actions | course/session access | roundtable contract | service test + browser | 未开始 |
| Provider 能力检测/设置 | `app/api/provider/**`、`components/settings/**` | server config | FastAPI-safe settings view | capabilities only, never keys | user/admin policy | provider redaction tests | pytest | 未开始 |
| 作业讲解 | — | assignment context + generation | `TaskDetailPage.jsx`、openmaic routes | preview/confirm/job/status/result | assignment/course permission | `test_openmaic_assignment_explanation.py`、web test | pytest + browser | 未开始 |
| 离线降级 | `app/api/health` | FastAPI fallback | all openmaic surfaces | unavailable reason, no 401 loop | normal course auth remains | offline tests | backend + browser | 未开始 |
| 安全闭环 | `middleware.ts`、upload routes、renderer | JWT/origin/SSRF/sanitize | backend + service security modules | redacted errors, bounded input | user/course/session/mapping | security suite | pytest + service tests | 部分完成；需复核 |

“部分完成”只表示现有适配层证据，不表示 OpenMAIC 已完整融合。
