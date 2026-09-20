# OpenMAIC 课堂 UI 移植 — 交接提示词

> 用途：把本文件 **从「〇、任务」到「十、交付清单」之间的全部内容**复制给下一个 AI（GPT）。
> 它是自包含的：接手方不需要看到任何先前会话记录。
>
> 最后更新：第 4 轮结束时。当前 HEAD：`dd3a8015`。

---

## 〇、任务

在**保持现有架构边界**的前提下，继续把参考项目（清华大学学习平台 / OpenMAIC）的界面**逐页、逐像素**地对齐移植进本仓库的 Web 客户端，并**每完成一个切片就用真实浏览器验收**。

优先级从高到低：

1. **工作台编辑器可视化**：把 `StageEditorPanel` 现在那个「场景列表 + JSON 文本框」换成能看能改的真实画布编辑（参考 `components/edit/**` 与 `components/slide-renderer/Editor/**`）。**这是剩下最大的一块。**
2. **课堂行为补齐**：键盘快捷键（翻页、Esc 退出全屏）、演示/全屏模式、自动播放时间线（参考 `components/edit/PlaybackChromeRoot.tsx` 的状态机）。
3. **更多幻灯片版式**：现在只有 3 种（纯标题 / 要点 / 2~3 张卡片小节），补封面页、目录页、双栏对比等。
4. **图表 / 公式 / 代码高亮**：安装 `echarts` / `katex` / `shiki`，并接上已经预留的插口 `setLatexRenderer` 与 `setCodeHighlighterFactory`。**注意**：当前生成器不产出 latex/code/chart 元素，做之前先确认生成侧会产出，否则是提前做。
5. **工具栏缺失控件**（白板、元素拾取、静音、停止讨论）：各自依赖不同的 store / 运行时，逐个评估，**做不了的不要放死按钮**。

**明确做不了、不要假装做到的**（缺对应运行时）：

- PBL 的 workspace 阶段（点「开始项目」之后）依赖 chat / submission / SSE 流式运行时 → 保持显式占位。
- 圆桌的实时流式、逐智能体 TTS、语音输入（ASR）、真人头像图 → 保持不渲染入口，不放假按钮。

---

## 一、仓库与路径

| 名称 | 路径 | 说明 |
| --- | --- | --- |
| 目标仓库 | `D:\File\demo1` | 你在改的就是它 |
| Web 客户端 | `D:\File\demo1\webreact` | Vite + React 18，**纯 JavaScript（.jsx，无 TypeScript）** |
| 受管 Node 运行时 | `D:\File\demo1\openmaic-service` | 移植过来的 DSL / 编辑 / 播放 / 生成服务，TypeScript（`--experimental-strip-types`） |
| 网关 | `D:\File\demo1\backend` | FastAPI：身份、课程权限、断言签发 |
| 参考项目 | `G:\File\github\清华大学学习平台` | **只读**。Next.js 16 + React 19 + TypeScript + Tailwind 4 |

先读 `D:\File\demo1\AGENTS.md`（仓库级唯一 AI 说明），它优先于本文件的习惯性建议。

---

## 二、架构边界（违反就等于白做）

浏览器**只调 CampusMate API**。链路固定为：

```
webreact (Vite :5174)
   │ 同源 /api 反代
   ▼
FastAPI (:8000)   身份 / 课程 / 作业 / 资料 / 权限 / 上下文 / 断言
   │ 短时 user/course/scope 断言
   ▼
openmaic-service (:4010)   DSL / 编辑器 / 播放器 / 导入导出 / 受限 Provider
```

- **浏览器不得直连 :4010**，不得出现 `127.0.0.1:4010`、`OPENMAIC_INTERNAL_SECRET`。已有测试钉住这一点（`webreact/tests/openmaic-classroom-stage.test.mjs` 里的 "the ported layer cannot reach the managed service directly"）。
- **单一登录、单一课程权限**：不引入第二套账号、第二套导航、第二套课程库。
- **只有互动 HTML / 3D / 模拟 / 游戏内容**可以进 iframe，且必须用最小 `sandbox`；**不得**把产品外壳放进 iframe。

---

## 三、移植层在哪

所有从参考项目移植过来的界面都在 `webreact/src/maic/` 下（117 个文件）：

| 目录 | 内容 | 入口 |
| --- | --- | --- |
| `src/maic/classroom/` | 课堂外壳：场景栏、头栏 | `index.js` → `MaicClassroomShell` |
| `src/maic/scene/` | 四类场景渲染器（slide / quiz / interactive / pbl） | `index.js` → `MaicSceneRenderer` |
| `src/maic/slide/` | 9 种课件元素渲染器 + 播放画布 | `index.js` → `MaicSlideSurface` |
| `src/maic/roundtable/` | 圆桌讨论面板（外框 + 三栏） | `index.jsx` → `MaicRoundtable` |
| `src/maic/ui/`、`src/maic/utils/` | shadcn 的 `Button`、`cn()` | — |
| `src/styles/maic.css` | Tailwind 4 + 参考项目设计令牌 | — |

集成层（把移植界面接到 CampusMate 真实数据上）在
`webreact/src/components/openmaic/OpenMAICClassroomStage.jsx`。

服务端的合成器在 `openmaic-service/src/dsl/`：
`slide-canvas.ts`（幻灯片画布）、`pbl-project.ts`（PBL 项目）、`document-projection.ts`（读取时投影）。

---

## 四、已经做完的（不要重做，也不要破坏）

7 次提交，从新到旧：

```
dd3a8015  补上圆桌讨论面板，课堂底部恢复到参考项目的 192px 布局
1b00c870  PBL 场景合成可运行项目，课堂不再显示"项目尚未生成"
07b50eab  存量旧版幻灯片改为读取时投影，历史课堂不再只剩标题
0dbad19f  补上画布底栏，撤掉头栏里的侧栏开关与深色画布
d52bffd2  课堂侧栏渲染真实幻灯片缩略图，并只取一次舞台文档
2aadd5ad  幻灯片改为服务端合成真实画布，课堂不再只有标题
fb9c6be9  进入课堂直达学习态，并把参考课堂 UI 移植进 webreact
```

具体能力（都已在真实浏览器验收过）：

- 「我的课程 → 进入课堂」直达**学习态**（不再是编辑器），地址带 `?mode=playback`。
- 课堂结构：左场景栏（**真实幻灯片缩略图**）+ 头栏 + 16:9 画布 + 底部 **192px 圆桌**（工具栏条 36px 并入其中，三栏左 90 / 中自适应 / 右 140）。
- 四类场景都能渲染：slide（真实画布元素）、quiz（真实题目与答题界面）、interactive（沙箱 iframe）、pbl（项目 Hero）。
- 幻灯片由**服务端确定性合成**真实画布（模型只出 title/subtitle/bullets/sections）。
- 存量旧数据由**读取时投影**救回，**不改写数据库字节**。
- 圆桌能真跑多智能体讨论（`POST /discussion` → 轮询 `/jobs/{id}` → `GET /artifacts/{id}`）。
- 三服务可一键启动：`node scripts/openmaic-local.mjs start`（或双击 `start_all.bat`，会先跑只读体检）。

---

## 五、下一次要做的第一件事：编辑器可视化

现状：`webreact/src/components/openmaic/StageEditorPanel.jsx`（263 行）是一个
**场景列表 + 一个编辑 DSL JSON 的 textarea**。这正是用户抱怨的"后台样子"。
它被渲染在 `OpenMAICWorkbenchPage.jsx` 的 `.ow-stage__inner`（16:9 盒）里。

参考项目对应的是 `G:\File\github\清华大学学习平台\components\edit\**`（66 文件）
与 `components/slide-renderer/Editor/**`（画布 + 拖拽/缩放/旋转手柄约 25 文件）。

**建议的切法**（不要一次做完，按切片交付，每片都要浏览器验收）：

- **切片 A：编辑器渲染真实画布。** 在工作台编辑态里用移植的 `MaicSlideSurface` /
  `ScreenCanvas` 渲染当前场景的真实画布，替掉现在的空白 16:9 盒。
  先只读，不做交互。
- **切片 B：元素选中与移动。** 移植 `Editor/Canvas/Operate/**` 与
  `Editor/Canvas/hooks/useDragElement.ts`、`useSelectElement.ts`，做出选中框 + 拖拽。
  命令通过 `applyOpenMAICStageCommands` 提交（命令列表，不是整份文档），遵守
  `Idempotency-Key` 与 `If-Match`。
- **切片 C：文本就地编辑。** 移植 `components/element/ProsemirrorEditor.tsx`（553 行）
  与 `element/TextElement/index.tsx`。
- **切片 D：缩放手柄 / 旋转 / 对齐线 / 标尺。**

每一片都要问自己：**参考实现在这里长什么样？类名是什么？** 逐字对齐，不要"顺手简化"。

---

## 六、必须知道的坑（都是我踩过的，照做能省几小时）

1. **含 JSX 的文件必须是 `.jsx`，不能是 `.js`。**
   Vite 的模块分析会对 `.js` 里的 JSX 报
   `Failed to parse source for import analysis ... name the file with the .jsx`。
   要保留 `index.js` 这个导入路径的话，就让 `index.js` 只做再导出。

2. **不要给 Playwright 同时加 `--disable-gpu` 和 `--disable-software-rasterizer`。**
   两个一起加等于没有光栅化器 → 页面不绘制 → 元素没有 bounding box →
   Playwright 判定"不可见" → **连登录都登不进去**，而且报错是"等待选择器超时"，
   极容易被误判成前端坏了。只加 `--disable-gpu` 就好。

3. **`.maic-root` 作用域必须由承载方提供。**
   Tailwind 令牌与工具类都只在 `.maic-root` 内生效。移植组件本身**不**带这个类
   （为了类名与参考逐字一致），所以集成组件要自己加。

4. **绝对不要引入 Tailwind 的 preflight。**
   `src/styles/maic.css` 只 `@import "tailwindcss/theme.css"` 与
   `tailwindcss/utilities.css`。加了 preflight 会全局重置 margin/padding/边框，
   把站内所有手写 CSS 的页面一起改掉。已有测试钉住。

5. **参考项目的播放态，工具栏是"并入"圆桌的，不是被丢弃。**
   `components/roundtable/index.tsx` 里写着 `Toolbar strip — merged from CanvasArea`。
   底部是「工具栏条 36px + 三栏交互区 156px」共 192px。别把工具栏和圆桌叠成两条。

6. **服务端的讨论/生成任务会同时回 `job_id` 和一个 `job` 快照（通常是 `queued`）。**
   判据必须是 `job?.status !== "completed" && job_id` 才轮询。
   用 `!job` 判断会拿到快照就直接按失败处理，表现为"点了没反应、永远没结果"。

7. **读取时投影必须是确定性的：不能出现 `new Date()` / 随机数。**
   投影靠"内容没变就不重写"来避免触碰存量字节；注入时间戳会让每次读取都"变了"，
   幂等判断永久失效。

8. **改服务端读取路径要跑后端测试。**
   `WorkspaceRepository.getStage` 是所有读路径的唯一咽喉，改动会影响编辑、播放、
   导出、归档、渲染。

9. **参考项目是只读的。**
   不要把它的二进制资源（如 `public/logo-horizontal.png`）拷进仓库——那要走
   `third_party/openmaic/` 的 LICENSE / NOTICE / SHA 清单流程。缺图就用文字字标
   替代，别留破图。

10. **`.env` 里有真实密钥，已被 gitignore。**
    不要把它们写进任何提交物、日志或测试夹具。`backend/.env` 与
    `openmaic-service/.env` 两侧的 `OPENMAIC_INTERNAL_SECRET` 必须一致。

11. **`run_openmaic_courses_e2e.py` 目前是失败状态，但那是既有失效用例。**
    它驱动 `.openmaic-role-picker__trigger`，而该元素在源码里**早已不存在**
    （角色选择器被移除过）。**不要去追它**，除非你确认要顺带清理。

---

## 七、测试与验收命令

> 本机若设了 HTTP 代理，访问 `127.0.0.1` 的脚本可能被代理接管而连不上。
> 跑任何**真实浏览器**或**真实 HTTP** 的脚本前先设：
> `$env:NO_PROXY='127.0.0.1,localhost'`（单测不需要）。

```powershell
# 三服务一键启动（先体检，再按依赖顺序拉起）
cd D:\File\demo1
node scripts/openmaic-local.mjs doctor
node scripts/openmaic-local.mjs start      # 前台守着，Ctrl+C 三个一起停

# 前端单测（含大量源码级契约测试）
cd D:\File\demo1\webreact
npm test                                   # 当前应为 877 passed
npm run build

# 后端 openmaic 相关（370 个用例）
# 注意：PowerShell 不展开通配符，`pytest tests/test_openmaic_*.py` 会收集到 0 个用例
# 并报 "no tests collected" —— 照抄那种写法会以为测试通过了。用 -k 过滤。
cd D:\File\demo1\backend
.\.venv\Scripts\python.exe -m pytest tests -k openmaic -q

# 受管服务（DSL / 生成 / 编辑 / 播放 / 讨论）
cd D:\File\demo1\openmaic-service
npm test                                   # 当前应为 279 passed
npm run typecheck

# 真实浏览器验收（自己起隔离的三服务 + 临时数据库，不碰开发库）
cd D:\File\demo1
$env:NO_PROXY='127.0.0.1,localhost'
backend\.venv\Scripts\python.exe webreact\tests\e2e\run_openmaic_workbench_e2e.py
```

**测试约定（照抄现有风格）：**

- 前端测试是 `node --test`，放 `webreact/tests/*.test.mjs`。
- 这个仓库大量使用**源码级契约测试**：`read()` 出组件源码，用 `assert.match`
  钉住"必须长这样"。新增能力要照这个风格补断言，而不是只测纯函数。
  但**注意**：源码级断言挡不住逻辑错误——我在圆桌上就写了一条"必须轮询 job"的断言，
  测试是绿的，真跑浏览器才发现判据写反了。**关键链路一定要真跑。**
- 受管服务测试是 `node --experimental-strip-types --test tests/*.test.mjs`，
  可以直接 `import` `.ts` 文件。
- 临时的一次性验收脚本用完就删，不要留在仓库里。

---

## 八、浏览器验收的硬要求

- **必须真跑，不许 mock 后端。** 用仓库的 `backend\.venv\Scripts\python.exe` 跑 Playwright。
- 每个切片都要：截图 + 收集 `pageerror` / `console error` / `>=400` 的 API 响应，
  并且在结论里报出**具体数字**（"0 条"而不是"没发现问题"）。
- 窄屏至少验 **320px**。这个宽度历史上出过两次真实缺陷：侧栏占满 220px 把主列压成
  100px、头栏右簇盖住返回按钮并吃掉点击（用 `document.elementFromPoint` 才能查到）。
- 登录页有入场动画会重渲染，`fill()` 可能反复重试失败。稳妥写法：
  先 `wait_for_selector`，再 `wait_for_timeout(6000)`，然后才 `fill`。
  登录输入框用 `input[autocomplete="username"]` / `input[autocomplete="current-password"]`，
  提交按钮是 `button.login-submit`。
- 演示账号：`student_demo` / `Demo123456`。

---

## 九、提交规范

- 每个切片**独立一次提交**，提交信息**聚焦 why**（为什么这么改），用**中文**。
- 只暂存本次任务相关的文件。工作区里可能有别处遗留的改动（例如 `.gitignore`、
  `backend/data/banner_images/`），**不要一起提交**。
- 提交前跑一遍：`git diff`、`git diff --cached`、`git status`，确认没有密钥、
  没有本机绝对路径进入变更。
- **不要提交**：截图、日志、临时脚本、构建产物、`.env`。

---

## 十、交付清单（每个切片完成时必须给出）

1. 改了哪些文件（路径）。
2. **参考实现的哪个文件、哪一段**被对齐（给出参考侧的路径与行号范围）。
3. 与参考**有意不同**的地方，以及为什么（"没有对应运行时"是正当理由，
   "顺手简化了"不是）。
4. 验证证据：单测通过数、构建结果、**真实浏览器**的几何/文本实测值、
   pageerror 与 console error 的**具体条数**。
5. 还没做完的部分，明确说出来。

---

## 附：一句话起点

> 先跑 `node scripts/openmaic-local.mjs start` 把三服务起起来，
> 用 `student_demo / Demo123456` 登录 http://127.0.0.1:5174/courses 点「进入课堂」
> 看一遍现状，再打开 `webreact/src/components/openmaic/StageEditorPanel.jsx`
> 开始做「切片 A：编辑器渲染真实画布」。
