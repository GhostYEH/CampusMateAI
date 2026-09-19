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

服务模板位于 `openmaic-service/.env.example`。除地址/密钥/数据库外，服务还接受可选的
上游 provider 配置；两组变量必须成对出现，缺一在启动即报错（fail-closed）：

- `OPENMAIC_PROVIDER_BASE_URL` / `OPENMAIC_PROVIDER_API_KEY` / `OPENMAIC_PROVIDER_MODEL`：
  OpenAI 兼容的 chat-completions 上游，用于学习内容生成与圆桌讨论。
  未配置时生成退回内置 local template，讨论如实返回 `provider_unavailable`。
- `OPENMAIC_TTS_BASE_URL` / `OPENMAIC_TTS_API_KEY` / `OPENMAIC_TTS_MODEL` / `OPENMAIC_TTS_VOICE`：
  语音合成上游（MiMo TTS：`mimo-v2.5-tts`，默认音色 `苏打`，响应为 base64 WAV）。
  未配置时语音合成如实返回 `provider_unavailable`。
- `OPENMAIC_RENDER_SERVICE_URL` / `OPENMAIC_RENDER_SERVICE_TOKEN`：私有 MP4 render-service；
  两者必须成对出现，服务只在配置完整时广告 `export-video`/`render`。render-service 默认绑定
  `127.0.0.1`，只接受 token 保护的受限 Stage JSON，并调用本机 ffmpeg；不得暴露到公网。
- 两组各自支持 `*_TIMEOUT_SECONDS`（默认生成 120、TTS 180）。
- 密钥只写在被 git 忽略的 `.env` 或 secret provider 里；`provider-status` 路由只暴露
  能力布尔值，永不回显密钥或上游地址。

启动脚本从仓库根目录解析路径：

```powershell
pwsh -NoProfile -File openmaic-service/scripts/start.ps1
```

运行时要求 Node.js `>=22.19.0`。如果 npm 不可用，可以直接运行仓库提供的 Node 测试和检查脚本；不能把本机绝对路径写入配置或提交。

## 本地三服务启动

本地要跑通完整链路需要三个进程，缺一不可：

| 进程 | 默认端口 | 作用 |
| --- | --- | --- |
| `openmaic-service` | 4010 | 受管 Node 运行时（DSL、编辑器、播放器、导入导出、受限 Provider） |
| FastAPI | 8000 | 网关：身份、课程权限、断言签发 |
| Vite | 5174 | Web 客户端；`/api` 反代到 FastAPI |

仓库根目录提供了一条可执行的启动与诊断路径（`scripts/openmaic-local.mjs`）：

```bash
node scripts/openmaic-local.mjs env      # 幂等补齐 backend/.env 与 openmaic-service/.env
node scripts/openmaic-local.mjs doctor   # 只读诊断：Node 版本、依赖、密钥一致性、端口与健康
node scripts/openmaic-local.mjs start    # 按序拉起三个进程
```

三个容易混淆、也最容易造成"服务都起来了却仍然 503"的点：

1. **两套地址不能混用。** `OPENMAIC_BASE_URL` 是既有课堂适配层用的上游地址（历史上指向
   3000 端口的 Next 应用）；`OPENMAIC_SERVICE_URL` 是融合网关用的受管服务地址（默认
   4010）。两者互不相干，把 3000 填进 `OPENMAIC_SERVICE_URL` 只会得到一个连不上的网关。
2. **两侧密钥必须一致。** `backend/.env` 的 `OPENMAIC_INTERNAL_SECRET` 与
   `openmaic-service/.env` 的同名变量必须是同一个值，否则每次调用都会被断言拒绝
   （表现为 `state=unavailable`、`reason=assertion_rejected`）。
3. **开关与地址/密钥要一起给。** 只开 `OPENMAIC_FUSION_ENABLED=true` 而不配地址/密钥时，
   `Settings` 在校验期就拒绝启动（fail-closed），不会等到请求时才失败。

密钥只写进被 git 忽略的 `.env`；`doctor` 只报告"是否配置、两侧是否一致"，不回显密钥值。

## 浏览器验收

真实浏览器验收（**不 mock 任何 API 路由**）从仓库根目录运行：

```bash
backend/.venv/Scripts/python.exe webreact/tests/e2e/run_openmaic_courses_e2e.py
```

它用临时数据库、随机断言密钥和空闲端口拉起上面三个**真实**进程，再以测试学生账号真实登录，
依次验证：健康链路 → 刷新后上下文恢复 → 运行中掉线（局部降级、课程列表不被替换）→
服务故障时其他课程功能仍可用 → 恢复后重试（不刷新整站）→ 320/768/1024/1440 四尺寸截图与
溢出检查 → console / pageerror / 失败请求审计。任一步失败都会转储三个子进程日志、现场截图
和当时的 DOM/响应状态；单测全绿而真实链路 503 时，只有这条命令能发现。

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

- 503 不是一句话，而是带稳定原因的。网关把每一种"不可用"翻译成
  `OPENMAIC_FUSION_UNAVAILABLE` + `details.reason`，浏览器据此区分"稍后重试"与"找管理员"：

  | `details.reason` | 含义 | 可重试 |
  | --- | --- | --- |
  | `fusion_disabled` | 本部署没有打开融合开关 | 否 |
  | `service_unconfigured` | 缺内部地址或密钥 | 否 |
  | `service_unreachable` | 连不上受管服务 | 是 |
  | `assertion_rejected` | 断言被服务端拒绝 | 否 |
  | `dependency_unavailable` | 服务在线但自身依赖未就绪 | 是 |
  | `provider_unavailable` | 该能力需要的 Provider 未配置 | 否 |
  | `unexpected_response` | 上游响应不符合契约 | 否 |

  没有 `reason` 的旧版 503 一律按可重试处理（更保守）。前端必须把原因翻译成中文可操作
  文案，绝不能把 Axios 的 `Request failed with status code 503` 直接展示给用户。

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
- `.maic.zip` 的解包面按"永不信任容器"处理：路径穿越名、Zip64、加密条目、未知压缩方法、
  软链接条目、重复条目名、CRC 或声明尺寸不符、条目数与解压总量超限，全部**按名字拒绝**，
  绝不做尽力而为的解析。解压上限按目录声明的尺寸在解压**之前**判定，再用实际解出的长度复核。
  已解出的文档仍然要走 `prepareStage`，档案不是绕开编辑器校验的旁门。
  导出响应是 `application/zip`；因为是 HTTP 头（latin-1），中文文件名使用 RFC 5987 的
  `filename*=UTF-8''…` 并附一个 ASCII 回退名。
- 生产部署不得把内部服务 origin 或访问码投影给浏览器。

## 能力状态

完整逐项状态以 `docs/openmaic-capability-matrix.md` 为准。当前状态是“部分完成”：

**本轮（课程页故障修复）已通过真实浏览器验收的部分。** 起因是课程页点"快速询问"时
`GET /api/v1/courses/{courseId}/workspaces?limit=1` 返回 503，页面中央直接显示
`Request failed with status code 503` 并把整块课程内容替换成一张错误卡片。根因有两个，
都是结构性的：一是快速询问在一个**不需要**工作台也能运行的流程里，先去做了一次必然
失败的受管服务请求；二是它把这次失败写进了**页级** error，而页级 error 由 `AsyncState`
消费，于是整页被替换。修复后 503 带稳定 `details.reason`，前端按原因给出中文文案与
正确的可重试性，快速询问的失败只出现在输入区，且服务不可用时直接进入课程辅导而不是
伪造工作台关联。以下各项经 `run_openmaic_courses_e2e.py` 在真实三服务上验证：

- 健康链路：真实登录 → `/courses` → 快速询问，`workspaces?limit=1` 为 **200**，
  并跳转到 `/counselor` 且 URL 携带 `course` / `workspace` / `prompt`；
- 刷新 `/counselor` 后课程上下文仍在（状态来自 URL，不依赖内存）；
- 运行中停掉受管服务后点击提交：得到 **503** 与局部中文错误
  （`暂时连不上受管 OpenMAIC 服务，请稍后重试。`），**31 门课程列表原样保留**、
  未出现整页错误卡片、已输入的问题与所选课程未丢失；
- 服务故障期间课程详情仍可打开（`GET /api/v1/courses/{courseId}` → 200）；
- 恢复服务后点局部错误里的「重试」直接成功（200），**不需要刷新整站**；
- 320 / 768 / 1024 / 1440 四尺寸均无横向溢出，输入工作区在视口内；
- `pageerror` 0 条、站点脚本 console error 0 条；浏览器自带的资源加载失败提示 2 条，
  逐条核对后全部是掉线场景里**故意**制造的 `workspaces` 503。

**同一轮修掉的两个页面级缺陷（都属于"能渲染但不可用"）：**

- 课程页框架是 `height: calc(100dvh - 112px)` + `overflow: hidden`（它只允许内部列表自己滚）。
  内容比框架高时若不交出滚动权，超出部分会被直接裁掉——元素仍在 DOM 里、脚本也数得到，
  但用户既看不到也滚不到：**"更多学习工具"和"我的课程"（31 门约 2479px）整块不可达**。
  现在 `.openmaic-home` 是唯一滚动容器，折叠区已可达（E2E 用几何断言兜住）。
- `.openmaic-workspace-item` 是三列栅格（图标/文案/操作），却平铺了 6 个子节点，
  操作被自动放进隐式第二行：第一列只有 32px，"进入工作台"被压成**每行一个字**，
  中间的"内容"被 `minmax(0,1fr)` 拉成一整条。现在操作收进 `.openmaic-workspace-item__actions`。

**仍未执行浏览器验收的部分**（保持"部分完成"，不得用源码测试冒充浏览器证据）：
C 切片的内容发现（文件夹树与站内搜索：`openmaic-service/src/discovery/**`、网关
`openmaic_discovery.py`、Web `DiscoveryPanel.jsx`，含工作台归档）已落地并通过
服务端/网关/Web 自动化测试，但其面板在本轮只验证了**渲染与可达**，文件夹增删改、
搜索、归档的浏览器交互未执行；E 切片中的课程资料部分
（上传/解析/引用：`openmaic-service/src/material/**`、`material_extraction.py`、
`openmaic_materials.py`、`MaterialsPanel.jsx`）同样已落地并通过三层自动化测试，
**尚未执行浏览器验收；原始字节在 2 MiB 内受限落库，并可随 stage 引用进入归档**；
`.maic.zip` 的单份 stage 导出与导入（`openmaic-service/src/archive/**`、
`openmaic_archive.py`、`archiveModel.js`、`WorkspacePanel.jsx`）已打通服务端、网关与 Web
三层并通过测试，**同样尚未执行浏览器验收；v2 档案会携带 stage 明确引用的素材资源**；
当前已补齐工作台编辑/播放、PPTX/Markdown/DOCX 导出、Provider 生成、白板、TTS、圆桌、
作业讲解确认门和受管 MP4 任务边界；完整 Stage 内容编辑、PPTX 图片/版式保真、素材原文件
字节存储、白板/音频/圆桌时间线播放、真实 Provider/ffmpeg 联调仍保持"部分完成"。
浏览器工具不可用时不得用源码测试冒充浏览器证据。
