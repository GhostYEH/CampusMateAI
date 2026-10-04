# CampusMateAI Agent Guide

本文件是 CampusMateAI 唯一的仓库级 AI 编码说明，适用于 Codex、Claude Code、Cursor、Trae 等工具。工具专属配置保持本地，不作为项目运行依赖。

## 项目边界

| 目录 | 职责 |
| --- | --- |
| `backend/` | FastAPI 后端、数据访问、检索与服务端测试 |
| `webreact/` | React 18 Web 客户端（Vite + React Router） |
| `android/` | Kotlin / Jetpack Compose Android 客户端 |
| `harmony/` | ArkTS / ArkUI HarmonyOS 客户端 |
| `wx/` | TypeScript 微信小程序 |
| `ml/` | 模型训练、评估、导出与可复现性材料 |
| `magicclass-app/` | 上游 magic class v1.0.3 入库源码，供导航栏「学习空间」独立进程运行；本地改动必须由 `scripts/magicclass-brand.mjs` 的品牌规则、`scripts/magicclass-feature.edits.json` 的可逆功能补丁或脚本中逐项说明的已声明偏离覆盖，并通过 `node scripts/magicclass-brand.mjs check` 与 `verify` 校验 |
| `ios/` | iOS 客户端预留目录；当前不存在时不要自行创建 |
| `.github/workflows/` | GitHub Actions；除 CI 专项任务外不要改动 |

- 当前 Web 客户端唯一入口是 `webreact/`；旧的 `web/` Vue 客户端已移除。涉及 Web 代码时不要按 `web/` 查找或新建目录。
- 不要随意删除任何端已有功能。修改跨端能力时，先检查后端契约和各客户端实现，明确需要同步的平台。
- 优先复用现有 repository、service、组件、主题和模型转换流程，避免平行实现。
- 修改 `magicclass-app/` 的功能时，现有上游文件的精确文本替换及新增文件内容必须同步到功能补丁清单；不得只修改入库源码或扩大已声明偏离来绕过校验。CI 的来源完整性门禁验证补丁状态和逆向还原。
- 未经明确要求，不修改数据库结构、公开 API、模型格式或部署流程。

## 后端接口文档与跨端协作

- **后端接口变更必须同步写入接口文档，并与实现一起提交；文档未同步时，不得宣告任务完成。** 此要求适用于新增、修改、废弃和删除接口，以及路径、HTTP 方法、请求/响应字段、字段类型、必填/可空/默认值、鉴权、权限、状态码、错误码或业务行为的变化。不能只在最终回复、提交信息或临时报告中说明。
- `docs/api/README.md` 是 Web、Android、HarmonyOS 和微信小程序共同使用的后端接口文档入口。变更时更新所属模块 Markdown；涉及共享字段、实际响应、接入流程或调用关系时，同步更新 `schemas.md`、`response-contracts.md`、`integration.md`、`web-map.md` 等对应文件。新增、删除接口或模型时，同步维护目录、覆盖范围和数量。
- 文档须足够让其他 Agent 独立开发客户端：说明完整方法与路径、参数和请求体、成功响应、鉴权与权限、业务前置条件、错误处理，并提供脱敏的请求/响应示例。文件上传下载、分页、幂等、异步任务、SSE、WebSocket 等接口还须说明对应协议和流程。动态字典或未声明完整响应模型的接口必须补充实际响应契约，不能只依赖自动生成的 OpenAPI。
- 使用后端 Python 环境运行 `python scripts/sync_api_docs.py` 同步 `docs/api/openapi.json`，再运行 `python scripts/sync_api_docs.py --check` 和相关 `pytest`（包括 `backend/tests/test_openapi_docs.py`）检查声明与文档一致性。涉及 Web 调用对照时运行 `node --test scripts/tests/web-api-docs.test.mjs`。自动生成的快照不能替代上述 Markdown 说明；无法执行验证时须明确说明原因和未验证范围。
- 修改契约前检查 `webreact/`、`android/`、`harmony/`、`wx/` 的相关调用，文档中注明受影响平台、兼容性和迁移/适配要求。区分已适配、待适配和未验证的平台，不得将仅验证某一端表述为全端完成。客户端 Agent 开始接入前须阅读对应接口文档；发现实现与文档不一致时须核对并同步修正，不得自行猜测契约。

## 安全与仓库卫生

- 禁止提交密钥、Token、密码、真实账号、生产数据、私钥或含凭据的 `.env`；只提交脱敏的 `.env.example`。
- 禁止在共享文件中写入盘符、用户名、本机 SDK/JDK/Python/IDE 路径或局域网地址。路径应从仓库根目录、环境变量或配置模板解析。
- 不要提交 AI/IDE 本地状态、Agent Skills、分析产物、临时脚本、日志、缓存、截图、录屏、测试上传文件或构建产物。
- 不要为一次任务生成大量 Markdown 报告；优先在最终回复中说明结果。确需保留的架构决策放入 `docs/`。
- `.github/workflows/`、Gradle Wrapper、包管理器锁文件、配置模板和平台必需工程文件属于共享工程配置，不得按“隐藏/生成文件”机械删除。

## JDK 21

Android/JVM 命令必须使用仓库目录下本地预置的 `android/.tools/jdk21-full/jdk-21.0.12+8`。`android/.tools/` 被 Git 忽略，不随源码分发；禁止回退到系统 `java` 或已有 `JAVA_HOME`。

PowerShell 中从仓库根目录解析，避免硬编码本机绝对路径：

```pwsh
$repoRoot = (git rev-parse --show-toplevel).Trim()
$env:JAVA_HOME = Join-Path $repoRoot 'android\.tools\jdk21-full\jdk-21.0.12+8'
if (-not (Test-Path -LiteralPath (Join-Path $env:JAVA_HOME 'bin\java.exe'))) { throw '项目约定的本地 JDK 21 不存在，停止 JVM 操作' }
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
& "$env:JAVA_HOME\bin\java.exe" -version
```

预期版本包含 `21.0.12`。若本地预置 JDK 不存在，停止 JVM 相关操作并报告，不要建议安装或切换系统 JDK。生成 `.bat`、`.cmd` 或 `.ps1` 时同样从脚本/仓库位置解析该目录。

## 修改与验证

- 先阅读目标模块 README、现有实现与测试，再做最小范围修改；不要顺手重构无关代码。
- 后端修改运行相关 `pytest`；Web 修改运行项目现有 lint/typecheck/test/build；移动端修改运行对应平台的最小相关测试或构建。
- JVM 构建前必须按上节设置本地预置 JDK。无法运行某项验证时，明确说明原因和未验证风险。
- 完成前检查 `git diff`、`git diff --cached`、`git status`，确认没有业务源码被意外修改，也没有密钥或本机绝对路径进入变更。
- **做完工作一定要提交**：任务完成后，必须将本次会话产生的业务源码改动精确暂存并创建一次提交。只提交本次任务相关的文件，不要纳入其他会话遗留的未提交改动。提交信息聚焦"why"。若用户明确要求暂不提交，则例外。

## 本地 Skills

`.agents/skills/` 是可选的本地 Agent 能力目录，不是 CampusMateAI 的运行或 CI 依赖，也不提交到 Git。任务明确匹配且本地存在对应 Skill 时，先读取其 `SKILL.md`；不存在时按本文件和仓库现有约定继续，不要把第三方 Skill 内容复制进项目文档。
