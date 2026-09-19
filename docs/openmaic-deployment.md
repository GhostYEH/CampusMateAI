# OpenMAIC 融合部署说明

本文是 CampusMate 内部受管 OpenMAIC 运行时的部署说明。用户入口始终是 CampusMate Web；OpenMAIC 不作为独立产品首页、独立登录或独立课程库暴露。

## 固定来源

- Repository: `https://github.com/THU-MAIC/OpenMAIC.git`
- Tag: `v1.0.3`
- Commit: `e693e11a81644f84c258df73dbda378643520a62`
- License: MIT，版权与全文见 `third_party/openmaic/LICENSE`
- Provenance、能力清单和 SHA-256 清单见 `third_party/openmaic/`

受管服务只接入经过审计的必要 DSL、renderer、editor、importer/exporter 和服务端能力；不复制 `.git`、`node_modules`、`.next`、运行时数据、日志、密钥或本机配置。

### 本机运行副本（不是来源）

开发机上另有一份 OpenMAIC 运行副本。它**不是**上述来源，也不能作为 provenance：

- `package.json` 版本为 `1.0.1`，比固定的 `v1.0.3` 旧；
- 没有 `.git` 元数据，无法证明 commit；
- 含构建产物、运行时数据和本地凭据文件。

逐文件比对（`third_party/openmaic/source-manifest.sha256`，2976 条）：2760 条一致、166 条不同、50 条缺失。
其中 `packages/@openmaic/dsl/src/**` 全部 16 个文件与 v1.0.3 **逐字节一致**，因此 DSL 契约的移植结论对该运行副本同样成立。
它可以被当作只读的“实际运行行为”参考，但任何提交产物、清单或 NOTICE 都不得引用它，也不得把它的路径写进仓库文件。

## 拓扑和边界

```text
CampusMate Web (React 18)
        │ CampusMate JWT / same-origin API
        ▼
CampusMate FastAPI
  身份、课程、作业、资料、权限、上下文、审批、审计
        │ 短时 user/course/scope 断言
        ▼
openmaic-service (private Node runtime)
  DSL、编辑器、播放器、导入导出和受限 Provider 能力
```

浏览器不直接调用受管服务；服务不提供公开首页或第二登录。互动 HTML、3D、模拟和游戏内容可以在净化后的 `srcDoc`/URL iframe 中运行，但必须使用 `sandbox`，不能把产品外壳放进 iframe。

## 配置

FastAPI 的脱敏模板位于 `backend/.env.example`：

- `OPENMAIC_FUSION_ENABLED`：融合运行时总开关，默认关闭。
- `OPENMAIC_SERVICE_URL`：仅服务端可见的内部 origin。
- `OPENMAIC_INTERNAL_SECRET`：短时断言共享密钥，只通过 secret provider 注入。
- `OPENMAIC_SERVICE_TIMEOUT_SECONDS`：内部调用超时。
- 既有 `OPENMAIC_*` 课堂适配配置继续由 `backend/app/services/openmaic/**` 使用。

服务模板位于 `openmaic-service/.env.example`。启动脚本从仓库根目录解析路径：

```powershell
pwsh -NoProfile -File openmaic-service/scripts/start.ps1
```

运行时要求 Node.js `>=22.19.0`。如果 npm 不可用，可以直接运行仓库提供的 Node 测试和检查脚本；不能把本机绝对路径写入配置或提交。

## 健康检查

- `GET /internal/health/live`：进程存活，不检查依赖，**匿名**。
- `GET /internal/health/ready`：依赖就绪；需要 `service:status` 断言，失败返回 503。
- CampusMate `GET /api/v1/openmaic/fusion/status`：唯一面向浏览器的能力状态。
  响应里的 `state` 是唯一判据，取值 `disabled` / `unavailable` / `degraded` / `ready`：

  | state | 含义 | `capabilities` |
  | --- | --- | --- |
  | `disabled` | `OPENMAIC_FUSION_ENABLED=false`，网关不去连服务 | 空 |
  | `unavailable` | 未配置地址/密钥、连不上、或断言被拒（`service_unconfigured` / `service_unreachable` / `assertion_rejected`） | 空 |
  | `degraded` | 服务在线但自身依赖未就绪（`dependency_unavailable`） | 空 |
  | `ready` | 服务与依赖都就绪 | 服务端实际挂载的能力标签 |

  只有 `ready` 才下发 capability —— 依赖没就绪时声称能力可用，会让浏览器打开一个必然失败的入口。
  任何状态都不泄露内部 URL、断言或密钥。

- `GET /api/v1/openmaic/fusion/recent?limit=20`：当前用户**所有可见课程**的最近学习内容，
  一次请求取代浏览器对每门课程分别拉取历史。limit 默认 20、上限 50。
  课程可见性复用统一策略（`can_view_course`），条目只含终态成功的课堂，
  并附带站内深链 `/courses/{courseId}?tab=mentoring&session={sessionId}`。

服务离线时，课程、作业查看、保存和提交仍由 CampusMate 正常提供；OpenMAIC 入口显示不可用或降级状态，不使用静态假数据。
前端只按 `state` + 真实 `capabilities` 逐项开放入口：`disabled`/`unavailable`/`degraded` 一律关闭，不显示"正在接入"这类占位文案。

## 安全要求

- 每次内部调用绑定 `userId`、`courseId`、scope、签发时间、过期时间和 jti；Node 服务拒绝过期、篡改、课程不匹配、缺 scope 和 replay。
- Provider Key 只存在服务端，不能进入前端 bundle、API 响应、快照、数据库或日志。
- `OPENMAIC_SERVICE_URL` 启动时拒绝凭据、query、fragment 和路径；后续出站调用仍需遵守 SSRF allowlist。
- 上传必须限制大小、类型和解压路径；HTML 必须净化；跨源内容必须使用最小 sandbox。
  课程资料的上传额外有三条硬规则：**格式由扩展名决定**（客户端声明的 Content-Type 不参与判断，
  否则二进制可以被当成文本来解码）、**解析不了就记 `unsupported` 且正文为空**（不伪造正文）、
  **状态与正文必须一致**（`unsupported` 带正文会被服务端拒绝）。
  正文解析依赖 `python-docx` 与 `PyPDF2`（已在 `backend/requirements.txt`）；缺失时该格式降级为
  `unsupported`，而不是报错。
- 生产部署不得把内部服务 origin 或访问码投影给浏览器。

## 能力状态

完整逐项状态以 `docs/openmaic-capability-matrix.md` 为准。当前状态是“部分完成”：
A 切片（来源审计、受管服务、断言强制、状态代理与最近内容聚合）与 B 切片
（`/courses` 原生首页与真实课程栏）已完成并验证；C 切片中的内容发现部分
（文件夹树与站内搜索：`openmaic-service/src/discovery/**`、网关
`openmaic_discovery.py`、Web `DiscoveryPanel.jsx`，含工作台归档）已落地并通过
服务端/网关/Web 自动化测试，但**尚未执行浏览器验收**；E 切片中的课程资料部分
（上传/解析/引用：`openmaic-service/src/material/**`、`material_extraction.py`、
`openmaic_materials.py`、`MaterialsPanel.jsx`）同样已落地并通过三层自动化测试，
**尚未执行浏览器验收，且本切片不保留上传文件的字节**；工作台的编辑器与播放器、
素材存储、导入导出、TTS、多智能体和作业讲解仍需后续切片完成和验证。
