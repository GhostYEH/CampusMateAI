# 进度账本（PROGRESS）

> **这是执行者跨上下文存活的唯一凭据。** 每个切片做完立刻更新本文件。
> 上下文被截断或会话被重开之后，**从这里继续，不要从零重来**。
>
> 状态只用四种：`未开始` / `进行中` / `已完成` / `无法完成`。
> `无法完成` 必须写清具体原因，并在 `03-待办.md` 对应项下同步一句。

## 使用方式

1. 开始一个切片前，把它改成 `进行中`，并在「备注」写上你打算怎么做。
2. 做完后改成 `已完成`，填上**提交号**。
3. 做不了改成 `无法完成`，写清卡在哪。
4. 每次更新都顺手把「下一步」写准——那是断线后唯一的指路标。

---

## 当前基线（开始动手前核对）

| 项 | 期望 | 实测 |
| --- | --- | --- |
| 前端 `webreact` `npm test` | 全绿 | 886 passed / 0 failed |
| 服务 `openmaic-service` `npm test` | 全绿 | 294 passed / 0 failed |
| 服务 `npm run typecheck` | 通过 | 55 TypeScript 文件检查通过 |
| 后端 `pytest tests -k openmaic` | 全绿 | 375 passed / 1883 deselected |

若实测与期望不符：**停下来问**（见 `PROMPT.md` 第 7 节）。

### 同时先跑一次 `git status`

这个仓库可能同时有别的会话在改代码（起草时是「场景讲解音频」功能）。
**不是你创建的文件一律当成别人的**：不碰、不提交、`git add` 只写你自己的路径。
详见 `PROMPT.md` 第 4 节。

开工时把 `git status` 的输出抄一份到这里，便于断线后判断"哪些是别人的"：

```
M .gitignore
?? .agents/
?? .workbuddy-ai/
?? backend/data/app.db.bak-20260913-195158
?? backend/data/app.db.bak-before-notice-migration-20260913-234341
?? backend/data/banner_images/011d3dee401647179b2422b3988b9ca1.png
?? backend/data/banner_images/05f90e81a21541c88cb1061dd97f9ce0.png
?? backend/data/banner_images/0f72281b1624431fb99c1d65eae16350.png
?? backend/data/banner_images/11ca2515323040ffb36c5f8ecbdebbfe.png
?? backend/data/banner_images/160282a7d8c946e186037a78edbe83ab.png
?? backend/data/banner_images/1e0285cb2f374b3691755ff72336cae6.png
?? backend/data/banner_images/1f89f3e3fbc94636ace77782b5e71f94.png
?? backend/data/banner_images/367811f7b21d44d2a2df229ab6387cd7.png
?? backend/data/banner_images/58376cf5522f4147b740048efadb4277.png
?? backend/data/banner_images/64fc09813ba1415a9321af64fcfd0346.png
?? backend/data/banner_images/6af1f1b757e74dbeacaeab81dba6118b.png
?? backend/data/banner_images/6ed680d5a65a42d98656f6fcce2550fd.png
?? backend/data/banner_images/851106ba8a6443649b5947a4a5a4f083.png
?? backend/data/banner_images/952c92e021a24546962b084d6b2e63cc.png
?? backend/data/banner_images/c2cf91ff1ca84ddd859f1dd11b93e6dd.png
?? backend/data/banner_images/ca703b5da29b46ad9d52d523619d524e.png
?? backend/data/banner_images/d78645785b264c56b10097787e40a7e5.png
?? backend/data/banner_images/dda226cfbebf4aedace00b5b4deba3e8.png
?? backend/data/banner_images/e320164bc1774f159558d42a7ebbd698.png
?? backend/data/banner_images/e913b7c4d4314e9ba0a0350db28913c8.png
```

---

## 切片清单

### 优先级 1 · 工作台编辑器可视化

| 切片 | 内容 | 状态 | 提交号 | 备注 |
| --- | --- | --- | --- | --- |
| P1-A | 编辑态渲染真实画布（只读） | 已完成 | 本提交 | 完整 stage 单次读取；编辑/播放共用画布；320px 上下布局 |
| P1-B | 元素选中与拖拽（命令走 `applyOpenMAICStageCommands`） | 待执行 | — | 服务端先补 `slide.element.move`，仅单选 slide 元素 |
| P1-C | 文本就地编辑（ProseMirror） | 未开始 | — | |
| P1-D | 缩放 / 旋转 / 对齐线 / 标尺 | 未开始 | — | |
| P1-E | 元素增删改 | 未开始 | — | |

### 优先级 2 · 课堂行为补齐

| 切片 | 内容 | 状态 | 提交号 | 备注 |
| --- | --- | --- | --- | --- |
| P2-A | 键盘快捷键（翻页 / Esc / Space） | 未开始 | — | |
| P2-B | 演示全屏模式（`isPresenting`） | 未开始 | — | |
| P2-C | 自动播放：按 action 时间线逐条执行 | 未开始 | — | |
| P2-D | 场景切换守卫（课程完成 / 生成中） | 未开始 | — | |

### 优先级 3 · 更多幻灯片版式

| 切片 | 内容 | 状态 | 提交号 | 备注 |
| --- | --- | --- | --- | --- |
| P3-A | 封面页 / 目录页 | 未开始 | — | |
| P3-B | 双栏对比 / 要点+结论条 | 未开始 | — | |

### 优先级 4 · 图表 / 公式 / 代码高亮

| 切片 | 内容 | 状态 | 提交号 | 备注 |
| --- | --- | --- | --- | --- |
| P4-A | 先确认生成侧会产出 latex / code / chart 元素 | 未开始 | — | 不产出就先别装依赖 |
| P4-B | 接 `setLatexRenderer`（katex） | 未开始 | — | |
| P4-C | 接 `setCodeHighlighterFactory`（shiki） | 未开始 | — | |
| P4-D | 图表换 echarts（保留外层盒与 `getChartOption`） | 未开始 | — | |

### 优先级 5 · 工具栏缺失控件

| 切片 | 内容 | 状态 | 提交号 | 备注 |
| --- | --- | --- | --- | --- |
| P5-A | 逐个评估：有运行时才做，没有的不放死按钮 | 未开始 | — | |

### 优先级 6 · 模板后台与运行时闭环

| 切片 | 内容 | 状态 | 提交号 | 备注 |
| --- | --- | --- | --- | --- |
| P6-A | PBL 导师/任务/提交/评估/模拟器/持久化 | 未开始 | — | 按 `03-待办.md` 模板依据拆分；现有占位不算完成 |
| P6-B | 圆桌实时流、逐角色音频与语音输入 | 未开始 | — | 保留已有场景讲解，不重复实现 |
| P6-C | 测验判分与学习记录闭环 | 未开始 | — | 用户/课程/舞台归属与刷新恢复 |
| P6-D | 工作台 Agent 会话与编辑闭环 | 未开始 | — | 会话、消息、事件、取消、恢复 |
| P6-E | Provider/媒体/资料完整链路 | 未开始 | — | 缺凭据只能记未验证，不能虚报通过 |
| P6-F | 资源、发布、导出与模板全量核对 | 未开始 | — | 逐项记录来源、适配、自动化和浏览器证据 |

### 现有入口缺口（接通运行时前保持显式占位）

| 项 | 原因 | 状态 |
| --- | --- | --- |
| PBL workspace 阶段 | 依赖 chat / submission / SSE 流式运行时 | 未开始（P6-A） |
| 圆桌实时流式 / 逐智能体 TTS / ASR / 真人头像图 | 待接运行时与资源 | 未开始（P6-B/E/F） |

---

## 下一步

> 每次更新本文件时把这一节写准。断线后接手方只看这一节就能继续。

- 下一个切片：**P1-B**
- 打算怎么做：按 `03-待办.md` 的 P1-B 契约，先让 commands 服务端支持
  `slide.element.move`，再接单选、pointer drag 与命令缓冲；服务端/网关/Web/浏览器证据
  齐全后才可标完成。
- 卡住的地方：无

---

## 过程记录

> 每个切片一行，倒序追加。发现的新坑也记在这里，最终会补进 `04-陷阱.md`。

- 2026-09-20：基线 HEAD `837a4928`，分支 `codex/openmaic-full-migration`；Web build 通过。服务端 4010、FastAPI 8000、Vite 5174 均空闲。
- 任务裁定：用户要求完整模板前后端移植，旧计划中的“缺运行时”是待补依赖，不是永久排除项；P1–P5 完成仍不代表全部模板能力完成。来源只读，统一登录/课程权限/网关不变。
- 任务裁定：用户确认其他会话已结束，tts/jobs/provider 的历史会话占用限制失效；保留开工未提交文件，不改其内容。
- 依赖核对：P1-A 提供完整场景画布，P1-B/C/D/E 依次复用其文档、选中状态和命令保存接口；P2-A/B/D 共用课堂组件，顺序实施；P2-C/P5 共用播放动作与音频状态，先时间线后工具栏；P3/P4 共用画布合成器，先版式后元素及渲染依赖。全部切片顺序提交，禁止并行修改同一实现。
- 下一步：P1-A 代码、前端测试、构建、真实浏览器（含 320px）及能力矩阵；同时只读核对模板后端能力缺口。
- P1-A：编辑器改为一次 `GET stage` 取得同 revision 的目录和完整画布，新增 `StageCanvasPreview`，复用课堂 `MaicSlideSurface`；动作数组保持完整而不以 outline 的计数覆盖。窄屏从左右栏改为上下栏，并以浏览器断言守住画布最小 250×140px。Web 单测 889 通过、build 通过；隔离全链路通过，320px 首个真实文本为 222.0×22.9px，页面无横向溢出、pageerror/console error/API ≥400 均为 0。
- P1-B 规划：模板的 `useSelectElement`/`useDragElement` 需要元素级持久化，但现有命令层
  只支持 stage/scene。先以受限 `slide.element.move` 补齐后端闭环；浏览器只在 pointerup
  提交最终坐标，避免拖动过程制造请求风暴或整份文档回写。
