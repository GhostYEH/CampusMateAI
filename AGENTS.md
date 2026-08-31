# CampusMateAI Agent Guide

本文件是 CampusMateAI 唯一的仓库级 AI 编码说明，适用于 Codex、Claude Code、Cursor、Trae 等工具。工具专属配置保持本地，不作为项目运行依赖。

## 项目边界

| 目录 | 职责 |
| --- | --- |
| `backend/` | FastAPI 后端、数据访问、检索与服务端测试 |
| `web/` | Vue 3 Web 客户端 |
| `android/` | Kotlin / Jetpack Compose Android 客户端 |
| `harmony/` | ArkTS / ArkUI HarmonyOS 客户端 |
| `wx/` | TypeScript 微信小程序 |
| `ml/` | 模型训练、评估、导出与可复现性材料 |
| `ios/` | iOS 客户端预留目录；当前不存在时不要自行创建 |
| `.github/workflows/` | GitHub Actions；除 CI 专项任务外不要改动 |

- 不要随意删除任何端已有功能。修改跨端能力时，先检查后端契约和各客户端实现，明确需要同步的平台。
- 优先复用现有 repository、service、组件、主题和模型转换流程，避免平行实现。
- 未经明确要求，不修改数据库结构、公开 API、模型格式或部署流程。

## 安全与仓库卫生

- 禁止提交密钥、Token、密码、真实账号、生产数据、私钥或含凭据的 `.env`；只提交脱敏的 `.env.example`。
- 禁止在共享文件中写入盘符、用户名、本机 SDK/JDK/Python/IDE 路径或局域网地址。路径应从仓库根目录、环境变量或配置模板解析。
- 不要提交 AI/IDE 本地状态、Agent Skills、分析产物、临时脚本、日志、缓存、截图、录屏、测试上传文件或构建产物。
- 不要为一次任务生成大量 Markdown 报告；优先在最终回复中说明结果。确需保留的架构决策放入 `docs/`。
- `.github/workflows/`、Gradle Wrapper、包管理器锁文件、配置模板和平台必需工程文件属于共享工程配置，不得按“隐藏/生成文件”机械删除。

## JDK 21

Android/JVM 命令必须使用仓库内捆绑的 `android/.tools/jdk21-full/jdk-21.0.12+8`，禁止回退到系统 `java` 或已有 `JAVA_HOME`。

PowerShell 中从仓库根目录解析，避免硬编码本机绝对路径：

```pwsh
$repoRoot = (git rev-parse --show-toplevel).Trim()
$env:JAVA_HOME = Join-Path $repoRoot 'android\.tools\jdk21-full\jdk-21.0.12+8'
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
& "$env:JAVA_HOME\bin\java.exe" -version
```

预期版本包含 `21.0.12`。若捆绑 JDK 不存在，停止 JVM 相关操作并报告，不要建议安装或切换系统 JDK。生成 `.bat`、`.cmd` 或 `.ps1` 时同样从脚本/仓库位置解析该目录。

## 修改与验证

- 先阅读目标模块 README、现有实现与测试，再做最小范围修改；不要顺手重构无关代码。
- 后端修改运行相关 `pytest`；Web 修改运行项目现有 lint/typecheck/test/build；移动端修改运行对应平台的最小相关测试或构建。
- JVM 构建前必须按上节设置捆绑 JDK。无法运行某项验证时，明确说明原因和未验证风险。
- 完成前检查 `git diff`、`git diff --cached`、`git status`，确认没有业务源码被意外修改，也没有密钥或本机绝对路径进入变更。

## 本地 Skills

`.agents/skills/` 是可选的本地 Agent 能力目录，不是 CampusMateAI 的运行或 CI 依赖，也不提交到 Git。任务明确匹配且本地存在对应 Skill 时，先读取其 `SKILL.md`；不存在时按本文件和仓库现有约定继续，不要把第三方 Skill 内容复制进项目文档。
