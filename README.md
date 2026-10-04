# CampusMate AI · 全链路学生助手

CampusMate AI 面向学生的学习与日常事务管理，围绕“通知整理 → 待办与课程 → 学习计划 → 专注模式与学习陪伴”提供辅助，并提供对话和互动课堂。各环节的可用能力取决于客户端、授权及服务配置。AI 对话的产品定位是**通用助手**，不以绑定某所学校作为聊天前提，也不能把演示资料当作真实学校规定。

> 本文区分产品定位与当前实现。Web、Android、HarmonyOS 以及微信小程序关闭 Mock 模式后的聊天请求仍调用后端 `/api/v1/counselor/chat`（后端另提供 `/assistant/chat` 别名）；除问候等短对话外，后端目前仍执行 BM25 校园知识库检索。普通问题在配置 LLM 后可以回答，但“聊天完全不检索知识库”尚未由当前代码实现。详情见[后端说明](backend/README.md)。

## 当前功能

| 功能 | 实际实现与边界 |
| --- | --- |
| AI 助手 | Web、Android 等端接入流式对话；可结合用户授权的个人待办、课程和学习状态上下文，支持可选的网页搜索及互动课堂建议。当前聊天接口仍保留历史知识库检索链路；学校制度问题不能把通用回答当作官方结论。 |
| 消息与通知整理 | **Android** 经用户开启系统通知访问权限后，接收通知栏中已展示的微信、企业微信、QQ/TIM、学习通消息；按来源开关、群名白名单和内容规则过滤，经本地队列上传，后端分类、去重、提取可执行事项并生成通知或待办。也可手动粘贴通知。这里不读取聊天记录或应用私有数据库。 |
| 学习通同步 | 用户连接学习通账号后，后端可同步课程、课程通知、作业和考试等信息；Android 有定期同步任务。它与“读取学习通系统通知”是两条独立来源，外部登录状态失效或需要验证时须重新连接。同步的作业、考试状态由学习通决定，CampusMate 中按只读处理。 |
| 可选教务连接 | 后端提供学校系统探测、账号绑定和课表、成绩、考试同步接口。能否获取真实数据取决于用户选择的学校、适配器和有效授权；聊天不要求先绑定学校。 |
| 个人事务与学习 | 待办、日程、课程、考试、专注模式、学习陪伴、学习状态和个人学习计划等页面及后端能力。各端功能覆盖不同，以各端说明为准。 |
| 在线课堂 | Web 课程内的互动课堂可按课程上下文生成内容、查看进度与组成、进入工作台编辑和播放；导航栏“学习空间”打开独立运行的上游 magic class 应用。生成、语音等能力取决于受管服务和模型配置，未启动时页面会显示真实不可用状态。 |
| 本地学习辅助 | Android 专注页使用 CameraX、LiteRT 和 ONNX Runtime 做本地表情、可见学习行为与在席观察；HarmonyOS 端也接入本地模型。结果是辅助观察，不代表专注程度、心理状态或学习效果。 |
| 知识库管理 | 后端仍提供文档导入、BM25 检索与管理接口，供现存聊天链路及相关管理功能使用；它不是通用助手的产品定位，也不自带某所学校的正式制度资料。 |

### 在线课堂的两个入口

- **课程内互动课堂**：从课程页“进入课堂”创建或复用工作台，以课程内容为上下文生成幻灯片、测验、交互或项目式学习等内容；可查看生成进度、编辑场景、播放并导出。请求中的内容类型是生成意图，实际产出以服务返回的组成信息为准。
- **导航栏“学习空间”**：Web 经后端确认服务和公开 Origin 后，内嵌独立运行的 `magicclass-app`。它与课程内工作台是两个入口，完整使用需要启动 `magicclass-service`、后端、`magicclass-app` 和 Web。

### 通知来源的端侧差异

| 客户端 | 当前能力 |
| --- | --- |
| Android | `NotificationListenerService` 读取**已展示的系统通知**；微信、企业微信、QQ/TIM 的群消息需要分别配置白名单，学习通系统通知可作为消息来源；另支持学习通账号同步。 |
| HarmonyOS | 有通知来源解析、筛选与订阅扩展代码，但系统通知订阅需要相应系统资质。普通应用不能据此承诺读取同机微信、QQ 等通知；可使用后端通知、学习通同步和手动粘贴。 |
| Web | 使用后端聚合后的通知与待办，没有手机系统通知监听能力。 |
| 微信小程序 | 提供通知查看、手动提取等演示流程，默认 Mock；不具备读取手机微信或 QQ 通知的权限。 |

## 工程组成

| 目录 | 作用 |
| --- | --- |
| [`backend/`](backend/README.md) | FastAPI、SQLite、认证、通知处理、学习通同步、AI 对话和互动课堂网关 |
| [`webreact/`](webreact/README.md) | 唯一 Web 客户端，React 18 + Vite；包含课程内互动课堂及“学习空间”入口 |
| [`android/`](android/README.md) | Kotlin + Jetpack Compose；系统通知接入、学习通、专注辅助等移动端能力 |
| [`harmony/`](harmony/README.md) | ArkTS / ArkUI 客户端；部分系统能力受 HarmonyOS 权限资质限制 |
| [`wx/`](wx/README.md) | TypeScript 微信小程序；部分功能为 Mock 演示 |
| [`ml/`](ml/) | 行为与表情模型训练、评估和导出 |
| `magicclass-service/` | CampusMate 互动课堂的受管服务 |
| `magicclass-app/` | 导航栏“学习空间”使用的上游独立应用；本地改动通过品牌规则、可逆功能补丁和逐项声明的偏离审计 |
| `render-service/` | 可选的互动课堂 MP4 导出渲染服务；需要单独配置与启动 |
| `scripts/` | 本地启动、品牌补丁及上游来源审计等工具 |
| `third_party/magicclass/` | 上游许可证、来源及审计清单 |
| `deploy/magicclass/` | 互动课堂部署配置模板 |
| `docs/` | 项目文档与设计记录 |
| `.github/workflows/` | GitHub Actions 工作流 |

系统角色为 `student` 和 `admin`；部分旧目录或示例数据仍保留 `teacher` 命名，不表示存在独立教师端。前端实际功能应以路由和权限校验为准。

## 本地运行

在 Windows 仓库根目录按需要选择：

| 脚本 | 启动内容 |
| --- | --- |
| `start_all.bat` | `magicclass-service` (4010) → FastAPI (8000) → `magicclass-app` (3000) → Vite Web (5174)；使用在线课堂与“学习空间”时运行 |
| `start_backend.bat` | 仅 FastAPI (8000) |
| `startreact.bat` | 仅 Web (5174) |

仅开发后端和普通 Web 页面时可组合运行 `start_backend.bat` 与 `startreact.bat`。在线课堂受管服务未启动或未配置时，相关入口会显示不可用；不会生成假的课堂内容。

手动启动与测试命令见各端 README。Android/JVM 命令必须使用项目约定放在 `android/.tools/jdk21-full/jdk-21.0.12+8` 的本地 JDK 21。`android/.tools/` 被 Git 忽略，不随源码分发；如果本地没有该 JDK，应停止 JVM 操作，不要回退到系统 Java：

```powershell
$repoRoot = (git rev-parse --show-toplevel).Trim()
$env:JAVA_HOME = Join-Path $repoRoot 'android\.tools\jdk21-full\jdk-21.0.12+8'
if (-not (Test-Path -LiteralPath (Join-Path $env:JAVA_HOME 'bin\java.exe'))) { throw '项目约定的本地 JDK 21 不存在，停止 JVM 操作' }
$env:PATH = "$env:JAVA_HOME\bin;$env:PATH"
& "$env:JAVA_HOME\bin\java.exe" -version
```

后端环境变量从 [`backend/.env.example`](backend/.env.example) 复制；默认 `LLM_PROVIDER=none`，通知可走规则抽取，聊天会走现有检索摘要降级。若要测试真实模型回答或课堂生成，须按对应服务配置模型提供方；不要提交 `.env` 或密钥。

## 已知边界

- 当前聊天**仍有知识库检索**，与“纯通用、无知识库检索”的目标不一致；这需要单独调整后端聊天编排及相关测试，不能只改 README 宣称已经完成。
- 仓库不自带任何学校的正式通知或教务数据。可选教务连接和学习通同步都依赖用户实际绑定、适配器及外部登录态；手机消息接入仅限系统实际展示、用户授权且通过筛选的通知。
- HarmonyOS 的跨应用通知读取受系统资质限制；微信小程序的 AI、知识库和表情相关演示内容标注为 Mock。
- 本地视觉模型输出不能用于医学、心理诊断；跨设备和环境效果仍需验证。

仓库开发与提交约定见 [`AGENTS.md`](AGENTS.md)。
