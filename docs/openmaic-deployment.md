# OpenMAIC 独立部署与接入指南

本文说明如何把 **OpenMAIC**（清华大学 THU-MAIC 开源项目）作为**独立服务**部署，并接入
CampusMateAI 的「课程智能辅导」。CampusMate 不重新实现 OpenMAIC 的生成引擎，也不复制其源码。

> 参考版本：**OpenMAIC 1.0.1**（`CHANGELOG.md` 最新条目 `## [1.0.1] - 2026-09-06`）
> 许可：**MIT License，Copyright (c) 2026 THU-MAIC**
> 参考目录不是 git 仓库，无法记录 commit；版本以上述 `package.json` / `CHANGELOG.md` 为准。
>
> 本仓库提供的脱敏配置模板：`deploy/openmaic/.env.example`（这是 **OpenMAIC 服务侧**的环境模板，
> 与 `backend/.env.example`（CampusMate 侧）不是同一个文件）。

---

## 1. 拓扑

```
Browser / Android
      │  只访问 CampusMate 站点
      ▼
CampusMate Web / App  ──►  CampusMate FastAPI（唯一权限与业务网关）
                                │  内部网络；ACCESS_CODE 只在此跳
                                ▼
                        OpenMAIC 独立服务（生成与运行）
                                │
                                ├─ LLM Provider
                                ├─ 图像 / TTS / ASR Provider
                                └─ render-service（可选，MP4 导出）
```

- **生成 / 查询 / 历史**：全部经 CampusMate 后端。浏览器从不直接调用 OpenMAIC 的 `/api/*`。
- **打开课堂**：浏览器直连 OpenMAIC 的**公开子域**（iframe 或新窗口），不带任何凭据。

## 2. 访问路径选择（必读）

OpenMAIC **不支持 `basePath`**：`next.config.ts` 没有 `basePath`/`assetPrefix`，
客户端所有请求都是根绝对路径（`/api/...`、`/logos/...`、`/avatars/...`）。
因此 `https://campus.example.com/openmaic/...` 这种**同源子路径不可用**（除非改其源码，禁止）。

### 方案 A（推荐）：独立可信子域 + 不启用 ACCESS_CODE + 网络层保护

| 项 | 取值 |
| --- | --- |
| 公开地址 | `https://classroom.example.com`（根路径） |
| `ALLOWED_FRAME_ANCESTORS` | `https://campus.example.com` |
| `ACCESS_CODE` | **留空** |
| 访问控制 | 由反向代理 / 校园网 / VPN / forward-auth 承担 |

**为什么 `ACCESS_CODE` 要留空**：OpenMAIC 的访问码以 `openmaic_access` cookie 承载，
属性为 `HttpOnly + SameSite=Lax`。跨站 iframe 不会携带该 cookie，课堂页自身的数据请求
（`/api/classroom?id=...`、`/api/stage-meta/*`）会 401，页面打不开。
CampusMate 也**绝不会**把访问码下发到浏览器。因此需要浏览器直连的场景下，
只能由**网络层**而不是应用层做访问控制。

**网络层保护责任（必须由部署方落实，应用层不替代）**：

- 课堂子域**不得**对公网匿名开放；
- 至少落实其中一项：
  - 反向代理前置认证（forward-auth / OAuth2-proxy / mTLS）；
  - 仅允许校园网段或 VPN 网段访问；
  - 由 CampusMate 后端签发**短时签名路径**，反代校验签名后放行；
- **不允许**把"课堂 ID 不可枚举"当作唯一授权手段。课堂 ID 是不可枚举的随机串，
  但它是**纵深防御**的一层，不是授权机制。

**CampusMate 侧仍然强制校验**：所有生成、状态、历史、打开请求都按
`user_id + course_id + session_id` 校验归属，与网络层控制相互独立、不可替代。

### 方案 B（保留 ACCESS_CODE 时）：由 CampusMate 反代整个课堂页

由 CampusMate 后端代理课堂页 HTML 及其 `/api/classroom*`、`/api/classroom-media/*`、
`/api/stage-meta/*`、`/_next/*`、`/logos/*`、`/avatars/*`，把 `openmaic_access` cookie
保留在服务端。

- 优点：浏览器零凭据、同源（无跨源 iframe 问题）。
- 代价：等于**用反代自己实现 `basePath`**，要重写一整个 Next.js SPA 的请求图与资源路径；
  OpenMAIC 升级可能打破重写规则。**仅在安全评审强制要求保留 ACCESS_CODE 时启用。**

## 3. 启动 OpenMAIC

要求 **Node >= 22.19.0**、**pnpm 10.x**。

### 3.1 Docker Compose（推荐）

```bash
# 1) 取得 OpenMAIC 源码（独立目录，不要放进 CampusMate 仓库）
git clone <openmaic-upstream-url> openmaic && cd openmaic

# 2) 准备环境文件（compose 要求 .env.local 存在）
cp .env.example .env.local
#    编辑 .env.local：至少填一个 LLM Provider Key 与 DEFAULT_MODEL

# 3) 启动
docker compose up -d --build
```

`docker-compose.yml` 中的服务：

| 服务 | 端口 | 说明 |
| --- | --- | --- |
| `openmaic` | `3000:3000`（宿主已发布） | Next.js 应用（standalone 输出） |
| `postgres` | 内部 5432，未发布 | 可选 profile `server-persistence` |
| `render-service` | 内部 9000（`expose`） | 可选 profile `video-export`，MP4 导出 |

注意：

- `openmaic` 与 `render-service` **没有 healthcheck**，编排层不能依赖 compose 就绪探测；
- `ALLOWED_FRAME_ANCESTORS` 是**构建期**变量（见 §4），改动后必须重新 `--build`。

### 3.2 本地 Node 方式

```bash
pnpm install
pnpm dev            # 开发
# 或
pnpm build && pnpm start
```

> 用 `pnpm start` 启动时 `npm_package_version` 可用，`/api/health` 会上报真实版本。
> 用 Docker 镜像里的 `node server.js` 启动时该变量为空，`/api/health` 会回落成硬编码的
> `0.1.0` —— 因此 CampusMate **不把版本字符串作为兼容性判据**（见 §6）。

## 4. 反向代理与 iframe 放行

OpenMAIC 默认下发 `X-Frame-Options: SAMEORIGIN` 与 CSP `frame-ancestors 'self'`，
跨源 iframe 会被浏览器直接拒绝。放行方式是设置**构建期**变量：

```bash
# .env.local（或 docker build-arg）
ALLOWED_FRAME_ANCESTORS=https://campus.example.com
```

- 该变量在 `next.config.ts` 的 `headers()` 里被读取并写入 CSP，**构建时内联**，
  改后必须重新构建镜像；
- 多个来源用空格分隔；
- 反代必须转发 `x-forwarded-host` 与 `x-forwarded-proto`，否则作业轮询地址
  （`pollUrl`）会按容器内地址生成。

## 5. 环境变量清单

OpenMAIC 的完整变量表见其 `.env.example`（500+ 行）。接入本功能最少需要：

| 变量 | 必需性 | 说明 |
| --- | --- | --- |
| `<PROVIDER>_API_KEY` | **必需** | 至少一个 LLM Provider，例如 `OPENAI_API_KEY` / `DEEPSEEK_API_KEY` / `QWEN_API_KEY` 等 |
| `DEFAULT_MODEL` | **必需** | 服务端默认模型。缺失且请求未带 `x-model` 时 `resolveModel` 会直接抛错 |
| `ALLOWED_FRAME_ANCESTORS` | 内嵌必需 | 见 §4 |
| `ACCESS_CODE` | 见 §2 | 方案 A 留空 |
| `DATABASE_URL` + `OPENMAIC_AGENT_RUNTIME_ENABLED` | 可选 | 打开 `GET /api/stages` 列表能力（本功能不使用） |
| `RENDER_SERVICE_URL` | 可选 | MP4 导出；由 compose 固定为 `http://render-service:9000` |
| `TRUST_PROXY_HEADERS` | 有反代时建议 | 让客户端标识与 origin 取真实值 |

**可选能力（按需配置，未配置即为不可用）**：

| 能力 | 变量前缀 | 影响 |
| --- | --- | --- |
| 图像生成 | `IMAGE_*` | 课堂配图 |
| 语音讲解 (TTS) | `TTS_*` | `generating_tts` 阶段是否产出音频 |
| 语音识别 (ASR) | `ASR_*` | 语音输入；本地音视频抽取还需系统 `ffmpeg`/`ffprobe` |
| 联网检索 | `TAVILY_*` / `EXA_*` / `BOCHA_*` / `SEARXNG_BASE_URL` 等 | `researching` 阶段 |

CampusMate 会读取 OpenMAIC 的 `GET /api/health`，用其中的
`capabilities.{webSearch,imageGeneration,videoGeneration,tts}` 决定请求里发送哪些 `enable*` 开关，
再与本地的 `OPENMAIC_ENABLE_*` 运维开关取交集。**能力不可用时不会假装调用。**

## 6. CampusMate 侧配置与契约指纹

CampusMate 侧变量见 `backend/.env.example` 的「OpenMAIC 互动课堂」段。关键点：

- `OPENMAIC_BASE_URL` 是**内部**地址，只用于服务间调用，绝不下发给客户端；
- `OPENMAIC_EMBED_ORIGIN` 是**浏览器公开** Origin，未配置时客户端 fail-closed；
- 生产环境要求 `OPENMAIC_EMBED_ORIGIN` 为 https 且不是回环/私网/保留地址。

CampusMate 用**三个只读探针**判断目标部署是否兼容（契约指纹）：

| # | 探针 | 期望 |
| --- | --- | --- |
| P1 | `GET /api/health` | 200，`success:true`，`status:'ok'`，`capabilities` 为对象 |
| P2 | `GET /api/access-code/status` | 200，`success:true`，`enabled` 为布尔 |
| P3 | `GET /api/generate-classroom/__probe__` | **404** + `errorCode:'INVALID_REQUEST'` + "not found" |

三个探针都是 GET，**不会创建任何生成任务、不产生任何费用**。P3 用一个格式合法但
必然不存在的 jobId 来验证作业族存在且语义稳定。

版本字符串**只记录、不决定兼容性**：因为 Docker 部署下 `/api/health` 会上报回落的
`0.1.0`。越界只写 `version_out_of_range` 供运维排查。

## 7. 3D 可视化的外部依赖

`interactive` 场景里的 `visualization3d` 组件，其 HTML 在沙箱 iframe 内通过 importmap
从 **`https://unpkg.com`** 加载 `three@0.160.0`，**没有本地回退**。

- 学生网络必须能访问 `https://unpkg.com`（以及 `three` 的 addons 路径）；
- 若不可达：把 CampusMate 的 `OPENMAIC_EXTERNAL_3D_AVAILABLE` 置为 `false`。
  此时 `adaptive` 不再推荐 3D，UI 会把 3D 标记为"当前环境不可用"，
  但 `simulation` / `diagram` / `code` / `game` 仍可正常使用；
- 课堂整体成功但 3D 依赖失败时，CampusMate 报 `degraded`，**不会**伪报整个课堂失败。

## 8. 许可与合规（部署方必须落实）

参考项目为 MIT，但独立部署会**分发**其产物，因此需要落实以下义务：

1. **MIT**：随部署分发 OpenMAIC 的 `LICENSE`（`Copyright (c) 2026 THU-MAIC`）。
   注意：v0.3.0（2026-06-28）之前为 **AGPL-3.0**，固定到更早的 tag 会继承 AGPL 义务。
2. **LGPL-3.0-or-later — `mathml2omml`**：该包经 `next.config.ts` 的 `transpilePackages`
   **打包进应用 bundle**，属于"分发库"。需随附 LGPL 全文与该库源码，并允许替换/重新链接。
3. **GSAP（GreenSock Standard License，非 OSI 许可）**：`public/vendor/gsap.min.js` 随镜像
   与每个导出 ZIP 分发，仓库内**没有**许可文本，需自行附上并遵守其条款。
4. **字体**：`packages/@openmaic/renderer` 的字体**二进制不在仓库里**，`fonts.css` 指向
   第三方主机 `https://file.maic.chat/fonts/*` —— 这是**运行期外部依赖**。
   若自托管，需原样保留 `font-licenses/{ARPHIC-PL.txt, OFL.txt, ZcoolHappy-LICENSE.txt}`
   （`WenDingPLKaiTi` 源自 `AR PL KaitiM GB`，为 **Arphic Public License 1999**，属 copyleft 字体许可）。
5. **`public/logos/*`**：35 个第三方商标（OpenAI / Anthropic / Google 等），仅有指示性使用，
   无附带商标声明。
6. **`public/avatars/*`**：33 个图片，仓库内**没有任何许可或出处证据**，需自行评估。
7. 仓库**不提供** `NOTICE` / `THIRD-PARTY` 文件，需自建。

## 9. 本仓库的边界

- CampusMate **不复制** OpenMAIC 的源码、SDK、组件或素材；只通过 HTTP 契约对接。
- CampusMate **不 vendor** 整个 OpenMAIC 仓库。
- 不使用 npm 上的 `@openmaic/*` 包：OpenMAIC 应用是 **React 19**，CampusMate Web 是 **React 18**，
  混装组件未经验证，禁止。
- `render-service` 的 MP4 导出**本轮不接入**（已列入 backlog）。
- 学生侧只使用 OpenMAIC 的课堂**运行**能力；教师工作台（`/api/stages*`、`publish`、
  `workbench`）一律不暴露给学生。

## 10. 生产注意事项

- 示例配置里的值（`127.0.0.1`、`example.com`、空的 Key）**仅供本地开发**，
  生产必须替换为真实域名与**独立生成**的密钥，不得照搬示例。
- 不得把真实 Provider Key、`ACCESS_CODE`、Cookie 或 Token 写入仓库、日志或客户端。
- 生产环境不得开启 OpenMAIC 的宽松开发开关（如 `ALLOW_LOCAL_NETWORKS`、
  `PERSISTENCE_ALLOW_INSECURE_DEV_AUTH`）。
