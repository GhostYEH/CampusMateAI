# 独立学习空间 API

> 核对日期：2026-09-30。当前独立应用 app/api 下 69 个 route.ts 文件的全部导出 HTTP handler 均列入本手册。它与本站课程工作台的数据、身份、路径前缀不同。

[总目录](README.md) · [课程侧 54 个接口](14-magicclass.md) · [已有模块说明](../magicclass-module-report.md)

## Origin、认证与能力

Web 导航 /learning-space 先调用本站 GET /api/v1/magicclass/learning-space/status，取可信 embed_origin 并加载 iframe。iframe 内的下列 /api 路径发往独立应用 Origin，不能拼在 CampusMate /api/v1 后面，也不使用 magicclass-service 的 /internal 路径。本站 JWT 不会自动转换成这里的身份。

若服务设置 ACCESS_CODE，中间件除 /api/access-code/* 与 /api/health 外要求 magicclass_access 签名 cookie，否则返回 HTTP 401。stages/folders/materials 等工作台资源采用 request owner cookie；persistence 的 documents/assets/runtime 分别使用不同授权规则，见 [持久化子路由](#persistence-contract)。ACCESS_CODE 不是 CampusMate 账号。以实际部署 cookie/CORS 与 iframe 访问条件为准。参见 [中间件](../../magicclass-app/middleware.ts)、[响应封装](../../magicclass-app/lib/server/api-response.ts)。

apiSuccess 返回 {success:true,...业务字段}，apiError 返回 {success:false,errorCode,error,details?}；ownerJson 直接返回传入的业务对象，不增加 success/data 包装，ownerNotFound 为 404 纯文本。文件、流、持久化和代理响应按各节实际构造解析。健康检查只声明 webSearch/imageGeneration/videoGeneration/tts，不表示全部能力可用。

功能开关：[feature-flags.ts](../../magicclass-app/lib/config/feature-flags.ts)。stages/folders/materials/Agent 持久化路由通常要求 MAGICCLASS_AGENT_RUNTIME_ENABLED 和 DATABASE_URL；stage-meta 使用较弱的服务端持久化条件（DATABASE_URL）。工作台还受 NEXT_PUBLIC_PRO_WORKBENCH_ENABLED 控制；未开启可能返回 404。其余生成、媒体、语音、ASR、搜索、PBL、导入/导出等以各 handler 的前置条件及提供方配置为准。

很多生成 / 评分 / 媒体接口读取 x-model、x-api-key、x-base-url、x-provider-type 等模型配置头，具体以接口章节为准；后续前端优先使用服务器已有提供方配置，示例不得包含真实密钥。工作台资源的写入与私有列表以当前 owner 为准，可读取资源的范围见授权规则；独立应用 ID 不应复用本站 course_id/stage_id。

## 功能流程

- 普通生成：输入需求或解析上传资料 → generate/outline → 逐场景 generate/content 与 generate/actions → 浏览器课堂状态、播放、编辑及本地导出。此过程由上游界面编排，不能仅调用一个整课端点就替代所有界面逻辑。
- 服务端整课生成：POST /api/generate-classroom → HTTP 202 与 jobId/pollUrl/pollIntervalMs → GET /api/generate-classroom/{jobId} → 读取生成课堂。
- 持久化工作台：owner / 功能开关满足后管理 stages/folders/materials，按当前接口的资源归属与字段校验执行；不要套用课程网关的 If-Match / Idempotency-Key。Agent sessions 的事件和审批另有自己的协议。
- 教师问答、圆桌、测验、PBL v2 导师/模拟器/评价/状态、搜索、图像/视频、TTS/ASR/音色克隆等是独立路由；由本节后面的完整 handler 索引查找。
- 本应用课堂 DSL 包含 slide/quiz/interactive/pbl 四类；Canvas、Action、Widget 和 PBL 数据由 [packages/@magicclass/dsl/src](../../magicclass-app/packages/@magicclass/dsl/src) 与 [lib/types](../../magicclass-app/lib/types) 定义。服务端动态开放内容不表示无须按 DSL 组织。

## 全部路由索引

共 86 个方法与路径组合。

| 方法 | 路径（相对独立 Origin） | 实现 |
| --- | --- | --- |
| GET | `/api/access-code/status` | [magicclass-app/app/api/access-code/status/route.ts](../../magicclass-app/app/api/access-code/status/route.ts) |
| POST | `/api/access-code/verify` | [magicclass-app/app/api/access-code/verify/route.ts](../../magicclass-app/app/api/access-code/verify/route.ts) |
| GET | `/api/agent/owner-events` | [magicclass-app/app/api/agent/owner-events/route.ts](../../magicclass-app/app/api/agent/owner-events/route.ts) |
| GET | `/api/agent/runtime` | [magicclass-app/app/api/agent/runtime/route.ts](../../magicclass-app/app/api/agent/runtime/route.ts) |
| POST | `/api/agent/sessions/{id}/cancel` | [magicclass-app/app/api/agent/sessions/[id]/cancel/route.ts](../../magicclass-app/app/api/agent/sessions/[id]/cancel/route.ts) |
| GET | `/api/agent/sessions/{id}/events` | [magicclass-app/app/api/agent/sessions/[id]/events/route.ts](../../magicclass-app/app/api/agent/sessions/[id]/events/route.ts) |
| POST | `/api/agent/sessions/{id}/messages` | [magicclass-app/app/api/agent/sessions/[id]/messages/route.ts](../../magicclass-app/app/api/agent/sessions/[id]/messages/route.ts) |
| GET | `/api/agent/sessions/{id}` | [magicclass-app/app/api/agent/sessions/[id]/route.ts](../../magicclass-app/app/api/agent/sessions/[id]/route.ts) |
| PATCH | `/api/agent/sessions/{id}` | [magicclass-app/app/api/agent/sessions/[id]/route.ts](../../magicclass-app/app/api/agent/sessions/[id]/route.ts) |
| POST | `/api/agent/sessions` | [magicclass-app/app/api/agent/sessions/route.ts](../../magicclass-app/app/api/agent/sessions/route.ts) |
| GET | `/api/agent/sessions` | [magicclass-app/app/api/agent/sessions/route.ts](../../magicclass-app/app/api/agent/sessions/route.ts) |
| GET | `/api/agent/sessions/status` | [magicclass-app/app/api/agent/sessions/status/route.ts](../../magicclass-app/app/api/agent/sessions/status/route.ts) |
| GET | `/api/agent/skills/{id}` | [magicclass-app/app/api/agent/skills/[id]/route.ts](../../magicclass-app/app/api/agent/skills/[id]/route.ts) |
| DELETE | `/api/agent/skills/{id}` | [magicclass-app/app/api/agent/skills/[id]/route.ts](../../magicclass-app/app/api/agent/skills/[id]/route.ts) |
| GET | `/api/agent/skills` | [magicclass-app/app/api/agent/skills/route.ts](../../magicclass-app/app/api/agent/skills/route.ts) |
| POST | `/api/agent/skills` | [magicclass-app/app/api/agent/skills/route.ts](../../magicclass-app/app/api/agent/skills/route.ts) |
| POST | `/api/azure-voices` | [magicclass-app/app/api/azure-voices/route.ts](../../magicclass-app/app/api/azure-voices/route.ts) |
| POST | `/api/chat/pi` | [magicclass-app/app/api/chat/pi/route.ts](../../magicclass-app/app/api/chat/pi/route.ts) |
| POST | `/api/chat/pi/whiteboard-visibility` | [magicclass-app/app/api/chat/pi/whiteboard-visibility/route.ts](../../magicclass-app/app/api/chat/pi/whiteboard-visibility/route.ts) |
| POST | `/api/chat` | [magicclass-app/app/api/chat/route.ts](../../magicclass-app/app/api/chat/route.ts) |
| GET | `/api/classroom-media/{classroomId}/{...path}` | [magicclass-app/app/api/classroom-media/[classroomId]/[...path]/route.ts](../../magicclass-app/app/api/classroom-media/[classroomId]/[...path]/route.ts) |
| POST | `/api/classroom` | [magicclass-app/app/api/classroom/route.ts](../../magicclass-app/app/api/classroom/route.ts) |
| GET | `/api/classroom` | [magicclass-app/app/api/classroom/route.ts](../../magicclass-app/app/api/classroom/route.ts) |
| GET | `/api/comfyui-workflows` | [magicclass-app/app/api/comfyui-workflows/route.ts](../../magicclass-app/app/api/comfyui-workflows/route.ts) |
| GET | `/api/export-video/capability` | [magicclass-app/app/api/export-video/capability/route.ts](../../magicclass-app/app/api/export-video/capability/route.ts) |
| GET | `/api/export-video/render/{jobId}/download` | [magicclass-app/app/api/export-video/render/[jobId]/download/route.ts](../../magicclass-app/app/api/export-video/render/[jobId]/download/route.ts) |
| GET | `/api/export-video/render/{jobId}` | [magicclass-app/app/api/export-video/render/[jobId]/route.ts](../../magicclass-app/app/api/export-video/render/[jobId]/route.ts) |
| DELETE | `/api/export-video/render/{jobId}` | [magicclass-app/app/api/export-video/render/[jobId]/route.ts](../../magicclass-app/app/api/export-video/render/[jobId]/route.ts) |
| POST | `/api/export-video/render` | [magicclass-app/app/api/export-video/render/route.ts](../../magicclass-app/app/api/export-video/render/route.ts) |
| POST | `/api/extract-document` | [magicclass-app/app/api/extract-document/route.ts](../../magicclass-app/app/api/extract-document/route.ts) |
| PATCH | `/api/folders/{id}` | [magicclass-app/app/api/folders/[id]/route.ts](../../magicclass-app/app/api/folders/[id]/route.ts) |
| DELETE | `/api/folders/{id}` | [magicclass-app/app/api/folders/[id]/route.ts](../../magicclass-app/app/api/folders/[id]/route.ts) |
| POST | `/api/folders/members` | [magicclass-app/app/api/folders/members/route.ts](../../magicclass-app/app/api/folders/members/route.ts) |
| GET | `/api/folders` | [magicclass-app/app/api/folders/route.ts](../../magicclass-app/app/api/folders/route.ts) |
| POST | `/api/folders` | [magicclass-app/app/api/folders/route.ts](../../magicclass-app/app/api/folders/route.ts) |
| GET | `/api/generate-classroom/{jobId}` | [magicclass-app/app/api/generate-classroom/[jobId]/route.ts](../../magicclass-app/app/api/generate-classroom/[jobId]/route.ts) |
| POST | `/api/generate-classroom` | [magicclass-app/app/api/generate-classroom/route.ts](../../magicclass-app/app/api/generate-classroom/route.ts) |
| POST | `/api/generate/agent-profiles` | [magicclass-app/app/api/generate/agent-profiles/route.ts](../../magicclass-app/app/api/generate/agent-profiles/route.ts) |
| POST | `/api/generate/image` | [magicclass-app/app/api/generate/image/route.ts](../../magicclass-app/app/api/generate/image/route.ts) |
| POST | `/api/generate/scene-actions` | [magicclass-app/app/api/generate/scene-actions/route.ts](../../magicclass-app/app/api/generate/scene-actions/route.ts) |
| POST | `/api/generate/scene-content` | [magicclass-app/app/api/generate/scene-content/route.ts](../../magicclass-app/app/api/generate/scene-content/route.ts) |
| POST | `/api/generate/scene-outlines-stream` | [magicclass-app/app/api/generate/scene-outlines-stream/route.ts](../../magicclass-app/app/api/generate/scene-outlines-stream/route.ts) |
| POST | `/api/generate/tts` | [magicclass-app/app/api/generate/tts/route.ts](../../magicclass-app/app/api/generate/tts/route.ts) |
| POST | `/api/generate/video` | [magicclass-app/app/api/generate/video/route.ts](../../magicclass-app/app/api/generate/video/route.ts) |
| POST | `/api/generate/voice` | [magicclass-app/app/api/generate/voice/route.ts](../../magicclass-app/app/api/generate/voice/route.ts) |
| GET | `/api/health` | [magicclass-app/app/api/health/route.ts](../../magicclass-app/app/api/health/route.ts) |
| GET | `/api/materials/{id}` | [magicclass-app/app/api/materials/[id]/route.ts](../../magicclass-app/app/api/materials/[id]/route.ts) |
| GET | `/api/materials` | [magicclass-app/app/api/materials/route.ts](../../magicclass-app/app/api/materials/route.ts) |
| POST | `/api/materials` | [magicclass-app/app/api/materials/route.ts](../../magicclass-app/app/api/materials/route.ts) |
| POST | `/api/parse-pdf` | [magicclass-app/app/api/parse-pdf/route.ts](../../magicclass-app/app/api/parse-pdf/route.ts) |
| POST | `/api/pbl/v2/evaluate` | [magicclass-app/app/api/pbl/v2/evaluate/route.ts](../../magicclass-app/app/api/pbl/v2/evaluate/route.ts) |
| POST | `/api/pbl/v2/instructor` | [magicclass-app/app/api/pbl/v2/instructor/route.ts](../../magicclass-app/app/api/pbl/v2/instructor/route.ts) |
| POST | `/api/pbl/v2/open-task` | [magicclass-app/app/api/pbl/v2/open-task/route.ts](../../magicclass-app/app/api/pbl/v2/open-task/route.ts) |
| POST | `/api/pbl/v2/simulator` | [magicclass-app/app/api/pbl/v2/simulator/route.ts](../../magicclass-app/app/api/pbl/v2/simulator/route.ts) |
| POST | `/api/pbl/v2/task/update` | [magicclass-app/app/api/pbl/v2/task/update/route.ts](../../magicclass-app/app/api/pbl/v2/task/update/route.ts) |
| GET | `/api/persistence/{...path}` | [magicclass-app/app/api/persistence/[...path]/route.ts](../../magicclass-app/app/api/persistence/[...path]/route.ts) |
| POST | `/api/persistence/{...path}` | [magicclass-app/app/api/persistence/[...path]/route.ts](../../magicclass-app/app/api/persistence/[...path]/route.ts) |
| PUT | `/api/persistence/{...path}` | [magicclass-app/app/api/persistence/[...path]/route.ts](../../magicclass-app/app/api/persistence/[...path]/route.ts) |
| PATCH | `/api/persistence/{...path}` | [magicclass-app/app/api/persistence/[...path]/route.ts](../../magicclass-app/app/api/persistence/[...path]/route.ts) |
| DELETE | `/api/persistence/{...path}` | [magicclass-app/app/api/persistence/[...path]/route.ts](../../magicclass-app/app/api/persistence/[...path]/route.ts) |
| POST | `/api/provider/probe-models` | [magicclass-app/app/api/provider/probe-models/route.ts](../../magicclass-app/app/api/provider/probe-models/route.ts) |
| POST | `/api/proxy-media` | [magicclass-app/app/api/proxy-media/route.ts](../../magicclass-app/app/api/proxy-media/route.ts) |
| POST | `/api/quiz-grade` | [magicclass-app/app/api/quiz-grade/route.ts](../../magicclass-app/app/api/quiz-grade/route.ts) |
| GET | `/api/server-providers` | [magicclass-app/app/api/server-providers/route.ts](../../magicclass-app/app/api/server-providers/route.ts) |
| GET | `/api/skills/{id}` | [magicclass-app/app/api/skills/[id]/route.ts](../../magicclass-app/app/api/skills/[id]/route.ts) |
| GET | `/api/stage-meta/{stageId}` | [magicclass-app/app/api/stage-meta/[stageId]/route.ts](../../magicclass-app/app/api/stage-meta/[stageId]/route.ts) |
| GET | `/api/stages/{id}/freshness` | [magicclass-app/app/api/stages/[id]/freshness/route.ts](../../magicclass-app/app/api/stages/[id]/freshness/route.ts) |
| POST | `/api/stages/{id}/generation-complete` | [magicclass-app/app/api/stages/[id]/generation-complete/route.ts](../../magicclass-app/app/api/stages/[id]/generation-complete/route.ts) |
| GET | `/api/stages/{id}/manifest` | [magicclass-app/app/api/stages/[id]/manifest/route.ts](../../magicclass-app/app/api/stages/[id]/manifest/route.ts) |
| POST | `/api/stages/{id}/publish` | [magicclass-app/app/api/stages/[id]/publish/route.ts](../../magicclass-app/app/api/stages/[id]/publish/route.ts) |
| GET | `/api/stages/{id}` | [magicclass-app/app/api/stages/[id]/route.ts](../../magicclass-app/app/api/stages/[id]/route.ts) |
| PATCH | `/api/stages/{id}` | [magicclass-app/app/api/stages/[id]/route.ts](../../magicclass-app/app/api/stages/[id]/route.ts) |
| PUT | `/api/stages/{id}` | [magicclass-app/app/api/stages/[id]/route.ts](../../magicclass-app/app/api/stages/[id]/route.ts) |
| DELETE | `/api/stages/{id}` | [magicclass-app/app/api/stages/[id]/route.ts](../../magicclass-app/app/api/stages/[id]/route.ts) |
| GET | `/api/stages/{id}/scenes` | [magicclass-app/app/api/stages/[id]/scenes/route.ts](../../magicclass-app/app/api/stages/[id]/scenes/route.ts) |
| GET | `/api/stages/{id}/status` | [magicclass-app/app/api/stages/[id]/status/route.ts](../../magicclass-app/app/api/stages/[id]/status/route.ts) |
| POST | `/api/stages/{id}/unpublish` | [magicclass-app/app/api/stages/[id]/unpublish/route.ts](../../magicclass-app/app/api/stages/[id]/unpublish/route.ts) |
| GET | `/api/stages` | [magicclass-app/app/api/stages/route.ts](../../magicclass-app/app/api/stages/route.ts) |
| POST | `/api/stages` | [magicclass-app/app/api/stages/route.ts](../../magicclass-app/app/api/stages/route.ts) |
| POST | `/api/transcription` | [magicclass-app/app/api/transcription/route.ts](../../magicclass-app/app/api/transcription/route.ts) |
| GET | `/api/usage` | [magicclass-app/app/api/usage/route.ts](../../magicclass-app/app/api/usage/route.ts) |
| POST | `/api/verify-image-provider` | [magicclass-app/app/api/verify-image-provider/route.ts](../../magicclass-app/app/api/verify-image-provider/route.ts) |
| POST | `/api/verify-model` | [magicclass-app/app/api/verify-model/route.ts](../../magicclass-app/app/api/verify-model/route.ts) |
| POST | `/api/verify-pdf-provider` | [magicclass-app/app/api/verify-pdf-provider/route.ts](../../magicclass-app/app/api/verify-pdf-provider/route.ts) |
| POST | `/api/verify-video-provider` | [magicclass-app/app/api/verify-video-provider/route.ts](../../magicclass-app/app/api/verify-video-provider/route.ts) |
| POST | `/api/web-search` | [magicclass-app/app/api/web-search/route.ts](../../magicclass-app/app/api/web-search/route.ts) |

## 接口契约

下面的请求解析、约束与返回构造直接摘自当前 handler，使用 TypeScript 而非伪造统一 JSON 模型。变量表示运行时结果；动态代理 / 流式响应需要按响应 Content-Type 解析。导入的请求类型一并展开，开放 DSL / Provider 类型保留源码链接。错误构造中的 status 为实际返回状态，apiSuccess 默认 200。

### `GET /api/access-code/status`

实现：[magicclass-app/app/api/access-code/status/route.ts](../../magicclass-app/app/api/access-code/status/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

成功 / 直接响应构造：

```ts
apiSuccess({ enabled, authenticated })
```

### `POST /api/access-code/verify`

实现：[magicclass-app/app/api/access-code/verify/route.ts](../../magicclass-app/app/api/access-code/verify/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
request.json()
```

成功 / 直接响应构造：

```ts
apiSuccess({ valid: true })
```

显式异常响应：

```ts
apiError('RATE_LIMITED', 429, 'Too many access-code attempts')

apiError('INVALID_REQUEST', 400, 'Invalid JSON body')

apiError('INVALID_REQUEST', 401, 'Invalid access code')
```

共享实现返回 / 转发表达式：

```ts
response
```

### `GET /api/agent/owner-events`

实现：[magicclass-app/app/api/agent/owner-events/route.ts](../../magicclass-app/app/api/agent/owner-events/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
resolveRequestOwnerId(req, responseHeaders)
```

请求头读取：

```ts
req.headers.get('last-event-id')
```

Query 读取：

```ts
url.searchParams.get('lastEventId')
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

new Response(stream, { headers: responseHeaders })
```

共享实现返回 / 转发表达式：

```ts
false

true

write(
          `event: resync_required\ndata: ${JSON.stringify({
            type: 'resync_required',
            reason,
            fromEventId: lastEventId.toString(),
            currentEventId: currentEventId.toString(),
          })}\n\n`,
        )

Promise.resolve()

pollInFlight
```

### `GET /api/agent/runtime`

实现：[magicclass-app/app/api/agent/runtime/route.ts](../../magicclass-app/app/api/agent/runtime/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
isAgentRuntimeEnabled()
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

成功 / 直接响应构造：

```ts
Response.json({
    enabled: isAgentRuntimeConfigured(),
    runtimeEnabled: isAgentRuntimeEnabled(),
  })
```

### `POST /api/agent/sessions/{id}/cancel`

实现：[magicclass-app/app/api/agent/sessions/[id]/cancel/route.ts](../../magicclass-app/app/api/agent/sessions/[id]/cancel/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

new Response('Not found', { status: 404, headers: responseHeaders })

NextResponse.json(
        {
          code: 'SESSION_ALREADY_TERMINAL',
          status: meta.status,
          error: `session is already ${meta.status}`,
        },
        { status: 409, headers: responseHeaders },
      )

NextResponse.json(
      { id, cancelRequested: true },
      { status: 202, headers: responseHeaders },
    )
```

共享实现返回 / 转发表达式：

```ts
withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    const { id } = await params;
    const store = await getAgentSessionStore();
    const meta = await store.getSession(id);
    if (!meta || meta.ownerId !== ownerId) {
      return new Response('Not found', { status: 404, headers: responseHeaders });
    }
    if (meta.status === 'succeeded' || meta.status === 'failed' || meta.status === 'cancelled') {
      return NextResponse.json(
        {
          code: 'SESSION_ALREADY_TERMINAL',
          status: meta.status,
          error: `session is already ${meta.status}`,
        },
        { status: 409, headers: responseHeaders },
      );
    }

    await store.requestCancel(id);
    return NextResponse.json(
      { id, cancelRequested: true },
      { status: 202, headers: responseHeaders },
    );
  })
```

### `GET /api/agent/sessions/{id}/events`

实现：[magicclass-app/app/api/agent/sessions/[id]/events/route.ts](../../magicclass-app/app/api/agent/sessions/[id]/events/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
resolveRequestOwnerId(req, responseHeaders)
```

请求头读取：

```ts
req.headers.get('last-event-id')
```

Query 读取：

```ts
url.searchParams.get('lastEventId')
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

new Response('Not found', { status: 404, headers: responseHeaders })

new Response(stream, { headers: responseHeaders })
```

共享实现返回 / 转发表达式：

```ts
false

true

Promise.resolve()

pollInFlight
```

### `POST /api/agent/sessions/{id}/messages`

实现：[magicclass-app/app/api/agent/sessions/[id]/messages/route.ts](../../magicclass-app/app/api/agent/sessions/[id]/messages/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
req.json()
```

handler 使用的业务字段：`body.text`、`body.materialIds`、`body.materialIds.some`、`body.elementRefs`、`body.courseRefs`。

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

new Response('Not found', { status: 404, headers: responseHeaders })

NextResponse.json(
        {
          id,
          message: { seq: posted.seq, text, delivery: posted.delivery },
          elementRefsAccepted: decodedElementRefs.refs.length > 0,
          courseRefsAccepted: decodedCourseRefs.refs.length > 0,
        },
        { status: 202, headers: responseHeaders },
      )

new Response('Forbidden', { status: 403, headers: responseHeaders })
```

显式异常响应：

```ts
apiError('INVALID_REQUEST', 400, 'invalid JSON body')

apiError('INVALID_REQUEST', 400, 'materialIds must be an array of strings')

apiError('INVALID_REQUEST', 400, 'materialIds are invalid')

apiError('INVALID_REQUEST', 400, decodedElementRefs.error)

apiError('INVALID_REQUEST', 400, decodedCourseRefs.error)

apiError('MISSING_REQUIRED_FIELD', 400, 'text is required')

apiError(
        'INVALID_REQUEST',
        400,
        `text exceeds the ${MAX_SESSION_TEXT_LENGTH} character limit`,
      )
```

共享实现返回 / 转发表达式：

```ts
withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    const { id } = await params;
    const store = await getAgentSessionStore();
    const meta = await store.getSession(id);
    if (!meta || meta.ownerId !== ownerId) {
      return new Response('Not found', { status: 404, headers: responseHeaders });
    }

    let body: {
      text?: string;
      materialIds?: unknown;
      elementRefs?: unknown;
      courseRefs?: unknown;
    } = {};
    try {
      body = ((await req.json()) ?? {}) as typeof body;
    } catch {
      const response = apiError('INVALID_REQUEST', 400, 'invalid JSON body');
      responseHeaders.forEach((value, name) => response.headers.append(name, value));
      return response;
    }

    const text = (body.text ?? '').toString().trim();
    if (
      body.materialIds !== undefined &&
      (!Array.isArray(body.materialIds) || body.materialIds.some((id) => typeof id !== 'string'))
    ) {
      const response = apiError('INVALID_REQUEST', 400, 'materialIds must be an array of strings');
      responseHeaders.forEach((value, name) => response.headers.append(name, value));
      return response;
    }
    const materialIds = [...new Set((body.materialIds ?? []).map((id: string) => id.trim()))];
    if (materialIds.length > 20 || materialIds.some((id) => !id)) {
      const response = apiError('INVALID_REQUEST', 400, 'materialIds are invalid');
      responseHeaders.forEach((value, name) => response.headers.append(name, value));
      return response;
    }
    const decodedElementRefs = decodeElementRefs(body.elementRefs ?? []);
    if (!decodedElementRefs.ok) {
      const response = apiError('INVALID_REQUEST', 400, decodedElementRefs.error);
      responseHeaders.forEach((value, name) => response.headers.append(name, value));
      return response;
    }
    const decodedCourseRefs = decodeCourseRefs(body.courseRefs ?? []);
    if (!decodedCourseRefs.ok) {
      const response = apiError('INVALID_REQUEST', 400, decodedCourseRefs.error);
      responseHeaders.forEach((value, name) => response.headers.append(name, value));
      return response;
    }
    if (!text && materialIds.length === 0) {
      const response = apiError('MISSING_REQUIRED_FIELD', 400, 'text is required');
      responseHeaders.forEach((value, name) => response.headers.append(name, value));
      return response;
    }
    if (text.length > MAX_SESSION_TEXT_LENGTH) {
      const response = apiError(
        'INVALID_REQUEST',
        400,
        `text exceeds the ${MAX_SESSION_TEXT_LENGTH} character limit`,
      );
      responseHeaders.forEach((value, name) => response.headers.append(name, value));
      return response;
    }

    try {
      const materials = materialIds.length
        ? await bindOwnerMaterialsToSession(id, ownerId, materialIds)
        : [];
      const posted = await store.postUserMessage(
        id,
        {
          text,
          ...(materials.length ? { materials } : {}),
          ...(decodedElementRefs.refs.length ? { elementRefs: decodedElementRefs.refs } : {}),
          ...(decodedCourseRefs.refs.length ? { courseRefs: decodedCourseRefs.refs } : {}),
        },
        { expectedOwnerId: ownerId },
      );
      if (text) scheduleConversationTitle(id, ownerId);
      return NextResponse.json(
        {
          id,
          message: { seq: posted.seq, text, delivery: posted.delivery },
          elementRefsAccepted: decodedElementRefs.refs.length > 0,
          courseRefsAccepted: decodedCourseRefs.refs.length > 0,
        },
        { status: 202, headers: responseHeaders },
      );
    } catch (error) {
      if (error instanceof SessionMaterialBindingError) {
        return new Response('Not found', { status: 404, headers: responseHeaders });
      }
      if (error instanceof AgentSessionAccessError) {
        return new Response('Forbidden', { status: 403, headers: responseHeaders });
      }
      throw error;
    }
  })

response
```

### `GET /api/agent/sessions/{id}`

实现：[magicclass-app/app/api/agent/sessions/[id]/route.ts](../../magicclass-app/app/api/agent/sessions/[id]/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

new Response('Not found', { status: 404, headers: responseHeaders })

NextResponse.json(meta, { headers: responseHeaders })
```

共享实现返回 / 转发表达式：

```ts
withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    const { id } = await params;
    const store = await getAgentSessionStore();
    const meta = await store.getSession(id);
    if (!meta || meta.ownerId !== ownerId) {
      return new Response('Not found', { status: 404, headers: responseHeaders });
    }
    return NextResponse.json(meta, { headers: responseHeaders });
  })
```

### `PATCH /api/agent/sessions/{id}`

实现：[magicclass-app/app/api/agent/sessions/[id]/route.ts](../../magicclass-app/app/api/agent/sessions/[id]/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
req.json()
```

handler 使用的业务字段：`body.title`。

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

new Response('Not found', { status: 404, headers: responseHeaders })

NextResponse.json({ title: meta.title ?? null }, { headers: responseHeaders })
```

显式异常响应：

```ts
apiError('INVALID_REQUEST', 400, 'invalid JSON body')

apiError('MISSING_REQUIRED_FIELD', 400, 'title is required')

apiError('INVALID_REQUEST', 400, 'title must be a string or null')
```

共享实现返回 / 转发表达式：

```ts
withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    const { id } = await params;
    const store = await getAgentSessionStore();

    let body: { title?: unknown } | null;
    try {
      body = (await req.json()) as typeof body;
    } catch {
      const response = apiError('INVALID_REQUEST', 400, 'invalid JSON body');
      responseHeaders.forEach((value, name) => response.headers.append(name, value));
      return response;
    }
    if (!body || typeof body !== 'object' || !Object.hasOwn(body, 'title')) {
      const response = apiError('MISSING_REQUIRED_FIELD', 400, 'title is required');
      responseHeaders.forEach((value, name) => response.headers.append(name, value));
      return response;
    }
    if (body.title !== null && typeof body.title !== 'string') {
      const response = apiError('INVALID_REQUEST', 400, 'title must be a string or null');
      responseHeaders.forEach((value, name) => response.headers.append(name, value));
      return response;
    }
    const title = normalizeSessionTitleOverride(body.title);
    const meta = await store.setManualSessionTitle(id, ownerId, title);
    if (!meta) {
      return new Response('Not found', { status: 404, headers: responseHeaders });
    }
    return NextResponse.json({ title: meta.title ?? null }, { headers: responseHeaders });
  })

response
```

### `POST /api/agent/sessions`

实现：[magicclass-app/app/api/agent/sessions/route.ts](../../magicclass-app/app/api/agent/sessions/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
req.json()
```

handler 使用的业务字段：`body.existingCourse`、`body.stageId?.toString().trim`、`body.stageId?.toString`、`body.stageId`、`body.prompt`、`body.materialIds`、`body.materialIds.some`、`body.courseRefs`、`body.skill`。

请求 / 局部契约 `CreateSessionBody`（[magicclass-app/app/api/agent/sessions/route.ts](../../magicclass-app/app/api/agent/sessions/route.ts)）：

```ts
interface CreateSessionBody {
  prompt?: string;
  stageId?: string;
  skill?: string;
  /** Attach to an already-built classroom instead of starting a new course. */
  existingCourse?: boolean;
  /** Existing owner-library uploads to bind before the first run is queued. */
  materialIds?: unknown;
  /** Classrooms named on the opening message. */
  courseRefs?: unknown;
}
```

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

new NextResponse(
          JSON.stringify({
            success: false as const,
            errorCode: 'INVALID_REQUEST',
            error: `unknown skill "${explicitSkillId}"; installed: ${
              known.map((s) => s.id).join(', ') || '(none)'
            }`,
          }),
          { status: 400, headers: responseHeaders },
        )

NextResponse.json(meta, { status: 202, headers: responseHeaders })

NextResponse.json(
        {
          ...meta,
          status: 'queued',
          ...(decodedCourseRefs.refs.length ? { courseRefs: decodedCourseRefs.refs } : {}),
        },
        { status: 202, headers: responseHeaders },
      )

new Response('Not found', { status: 404, headers: responseHeaders })
```

显式异常响应：

```ts
apiError('INVALID_REQUEST', 400, 'invalid JSON body')

apiError('MISSING_REQUIRED_FIELD', 400, 'existingCourse requires stageId')

apiError('INVALID_REQUEST', 400, 'existingCourse stageId has an invalid format')

apiError('MISSING_REQUIRED_FIELD', 400, 'prompt is required')

apiError(
      'INVALID_REQUEST',
      400,
      `prompt exceeds the ${MAX_SESSION_TEXT_LENGTH} character limit`,
    )

apiError('INVALID_REQUEST', 400, 'materialIds must be an array of strings')

apiError('INVALID_REQUEST', 400, 'materialIds are invalid')

apiError(
      'INVALID_REQUEST',
      400,
      'existingCourse does not accept attachments; send them on the first message instead',
    )

apiError('INVALID_REQUEST', 400, decodedCourseRefs.error)
```

共享实现返回 / 转发表达式：

```ts
withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    // An EXPLICIT skill — a `?skill=` launch link, not composer UI — is
    // rejected here rather than at claim time: a session created with a typo'd
    // skill would otherwise sit queued and then quietly build an ordinary
    // conversation. The runner's `findSkill` matches a reference by id OR name
    // (a user skill's natural handle is `name`, `my-*`), so the route validates
    // with the same lookup and freezes the resolved id.
    let explicitSkillId = (body.skill ?? '').toString().trim() || undefined;
    if (explicitSkillId) {
      const found = await findSkill(explicitSkillId, ownerId);
      if (!found) {
        const known = await listSkills(ownerId);
        return new NextResponse(
          JSON.stringify({
            success: false as const,
            errorCode: 'INVALID_REQUEST',
            error: `unknown skill "${explicitSkillId}"; installed: ${
              known.map((s) => s.id).join(', ') || '(none)'
            }`,
          }),
          { status: 400, headers: responseHeaders },
        );
      }
      explicitSkillId = found.id;
    }
    /**
     * Otherwise, read the skill off the message itself.
     *
     * Skills are written as `/handle` TEXT — there is no chip and no skill
     * field in the UI, because an input box is an input box. Nothing needs to
     * parse that text for the agent (skills are listed in the system prompt
     * and opened with pi's native `read`), but the session's `skillId` still
     * feeds the outline-constraint pointer. So the SERVER recognises the
     * structure in the text and records it.
     *
     * Forgiving by design: an unrecognised handle simply means no skill — never
     * an error, never a fallback to a default — and the text stays in the
     * prompt either way, so the model still sees what the user asked for.
     */
    const skillId = explicitSkillId ?? (await inferSkillIdFromPrompt(prompt, ownerId));

    // Upstream classrooms do not carry an owner partition, so existing-course
    // sessions validate only the identifier format here. Full existence and
    // ownership validation is deferred until a later slice consumes stageId —
    // the upstream document store has no owner partition yet.
    const store = await getAgentSessionStore();
    const hasOpeningContext = materialIds.length > 0 || decodedCourseRefs.refs.length > 0;
    const meta = await store.createSession({
      ownerId,
      prompt,
      ...(stageId ? { stageId } : {}),
      ...(skillId ? { skillId } : {}),
      existingCourse,
      titleState: 'pending',
      origin: buildRequestOrigin(req),
      // Keep the runner from claiming the session until its opening materials
      // and references are durable. postUserMessage below atomically requeues it.
      ...(existingCourse || hasOpeningContext ? { status: 'succeeded' as const } : {}),
    });

    if (!hasOpeningContext) {
      if (!existingCourse) scheduleConversationTitle(meta.id, ownerId);
      return NextResponse.json(meta, { status: 202, headers: responseHeaders });
    }

    try {
      const openingText = existingCourse ? explicitPrompt : prompt;
      const materials = materialIds.length
        ? await bindOwnerMaterialsToSession(meta.id, ownerId, materialIds)
        : [];
      await store.postUserMessage(
        meta.id,
        {
          text: openingText,
          ...(materials.length ? { materials } : {}),
          ...(decodedCourseRefs.refs.length ? { courseRefs: decodedCourseRefs.refs } : {}),
        },
        { expectedOwnerId: ownerId },
      );
      if (openingText) scheduleConversationTitle(meta.id, ownerId);
      return NextResponse.json(
        {
          ...meta,
          status: 'queued',
          ...(decodedCourseRefs.refs.length ? { courseRefs: decodedCourseRefs.refs } : {}),
        },
        { status: 202, headers: responseHeaders },
      );
    } catch (error) {
      await store.softDeleteSession(meta.id, ownerId).catch(() => false);
      if (error instanceof SessionMaterialBindingError) {
        return new Response('Not found', { status: 404, headers: responseHeaders });
      }
      throw error;
    }
  })
```

### `GET /api/agent/sessions`

实现：[magicclass-app/app/api/agent/sessions/route.ts](../../magicclass-app/app/api/agent/sessions/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

NextResponse.json(sessions, { headers: responseHeaders })
```

共享实现返回 / 转发表达式：

```ts
withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    const store = await getAgentSessionStore();
    const sessions = await store.listSessionsByOwner(ownerId);
    return NextResponse.json(sessions, { headers: responseHeaders });
  })
```

### `GET /api/agent/sessions/status`

实现：[magicclass-app/app/api/agent/sessions/status/route.ts](../../magicclass-app/app/api/agent/sessions/status/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

NextResponse.json(statuses, { headers: responseHeaders })
```

共享实现返回 / 转发表达式：

```ts
withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    const store = await getAgentSessionStore();
    const sessions = await store.listSessionsByOwner(ownerId);
    const statuses = Object.fromEntries(sessions.map((session) => [session.id, session.status]));
    return NextResponse.json(statuses, { headers: responseHeaders });
  })
```

### `GET /api/agent/skills/{id}`

实现：[magicclass-app/app/api/agent/skills/[id]/route.ts](../../magicclass-app/app/api/agent/skills/[id]/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

NextResponse.json(
      { id: skill.id, content: skill.content },
      { headers: responseHeaders },
    )
```

共享实现返回 / 转发表达式：

```ts
withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    const { id } = await params;
    const skill = await findUserSkill(id, ownerId);
    if (!skill) return new Response('Not found', { status: 404 });
    return NextResponse.json(
      { id: skill.id, content: skill.content },
      { headers: responseHeaders },
    );
  })
```

### `DELETE /api/agent/skills/{id}`

实现：[magicclass-app/app/api/agent/skills/[id]/route.ts](../../magicclass-app/app/api/agent/skills/[id]/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

new Response('Built-in skills cannot be deleted.', {
        status: 405,
        headers: responseHeaders,
      })

new Response(null, { status: 204, headers: responseHeaders })

new Response('Not found', { status: 404, headers: responseHeaders })
```

共享实现返回 / 转发表达式：

```ts
withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    const { id } = await params;
    if (!id.startsWith('usk_')) {
      return new Response('Built-in skills cannot be deleted.', {
        status: 405,
        headers: responseHeaders,
      });
    }
    try {
      await deleteUserSkill(ownerId, id);
      return new Response(null, { status: 204, headers: responseHeaders });
    } catch (error) {
      if (error instanceof UserSkillError && error.code === 'not-found') {
        return new Response('Not found', { status: 404, headers: responseHeaders });
      }
      throw error;
    }
  })
```

### `GET /api/agent/skills`

实现：[magicclass-app/app/api/agent/skills/route.ts](../../magicclass-app/app/api/agent/skills/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

NextResponse.json(
      skills.map((s) => ({
        id: s.id,
        name: s.name,
        ...(s.title ? { title: s.title } : {}),
        description: s.description,
        hasConstraints: !!s.constraints,
        source: s.source,
      })),
      { headers: responseHeaders },
    )
```

共享实现返回 / 转发表达式：

```ts
withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    const skills = await listSkills(ownerId);
    return NextResponse.json(
      skills.map((s) => ({
        id: s.id,
        name: s.name,
        ...(s.title ? { title: s.title } : {}),
        description: s.description,
        hasConstraints: !!s.constraints,
        source: s.source,
      })),
      { headers: responseHeaders },
    );
  })
```

### `POST /api/agent/skills`

实现：[magicclass-app/app/api/agent/skills/route.ts](../../magicclass-app/app/api/agent/skills/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
form = await req.formData()
upload = form.get('file')
```

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

new Response('A skill file is required.', {
          status: 400,
          headers: responseHeaders,
        })

new Response('The skill upload is too large.', {
          status: 413,
          headers: responseHeaders,
        })

NextResponse.json(
        {
          id: skill.id,
          name: skill.name,
          title: skill.title,
          description: skill.description,
          hasConstraints: false,
          source: 'user',
        },
        { status: 201, headers: responseHeaders },
      )

NextResponse.json(
          { error: error.code, message: error.message },
          { status, headers: responseHeaders },
        )

NextResponse.json(
          { error: 'invalid-upload', message: error.message },
          { status: 400, headers: responseHeaders },
        )
```

共享实现返回 / 转发表达式：

```ts
withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    try {
      const form = await req.formData();
      const upload = form.get('file');
      if (!upload || typeof upload === 'string' || typeof upload.arrayBuffer !== 'function') {
        return new Response('A skill file is required.', {
          status: 400,
          headers: responseHeaders,
        });
      }
      const bytes = Buffer.from(await upload.arrayBuffer());
      // Exported owner zips are at most a little over the 64 KiB content cap.
      // Bound compressed input before JSZip expands it; field validation below
      // remains the authoritative create limit after parsing.
      if (bytes.byteLength > 1_048_576) {
        return new Response('The skill upload is too large.', {
          status: 413,
          headers: responseHeaders,
        });
      }
      const input = upload.name.toLowerCase().endsWith('.zip')
        ? await parseUserSkillZip(bytes)
        : parseUserSkillMarkdown(bytes.toString('utf8'));
      const skill = await createUserSkill(ownerId, input);
      return NextResponse.json(
        {
          id: skill.id,
          name: skill.name,
          title: skill.title,
          description: skill.description,
          hasConstraints: false,
          source: 'user',
        },
        { status: 201, headers: responseHeaders },
      );
    } catch (error) {
      if (error instanceof UserSkillError) {
        const status = error.code === 'duplicate' || error.code === 'quota' ? 409 : 400;
        return NextResponse.json(
          { error: error.code, message: error.message },
          { status, headers: responseHeaders },
        );
      }
      if (error instanceof UserSkillUploadError) {
        return NextResponse.json(
          { error: 'invalid-upload', message: error.message },
          { status: 400, headers: responseHeaders },
        );
      }
      throw error;
    }
  })
```

### `POST /api/azure-voices`

实现：[magicclass-app/app/api/azure-voices/route.ts](../../magicclass-app/app/api/azure-voices/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
body = await req.json()
```

handler 使用的业务字段：`body.baseUrl`。

成功 / 直接响应构造：

```ts
apiSuccess({ voices })
```

显式异常响应：

```ts
apiError('MISSING_API_KEY', 400, 'API Key is required')

apiError('MISSING_REQUIRED_FIELD', 400, 'Base URL is required')

apiError('INVALID_URL', 403, ssrfError)

apiError('REDIRECT_NOT_ALLOWED', 403, 'Redirects are not allowed')

apiError(
        'UPSTREAM_ERROR',
        response.status,
        'Failed to fetch voices from Azure',
        errorText || response.statusText,
      )

apiError(
      'INTERNAL_ERROR',
      500,
      'Failed to fetch voices',
      error instanceof Error ? error.message : 'Unknown error',
    )
```

### `POST /api/chat/pi`

实现：[magicclass-app/app/api/chat/pi/route.ts](../../magicclass-app/app/api/chat/pi/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isPiChatEnabled()
```

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
body: StatelessChatRequest = await req.json()
```

handler 使用的业务字段：`body.model`、`body.messages?.length`、`body.messages`、`body.storeState`、`body.config`、`body.config.agentIds`、`body.elementReference`、`body.apiKey`、`body.baseUrl`、`body.providerType`、`body.thinkingConfig`、`body.thinking`、`body.config.agentIds.join`、`body.config.piEnableWhiteboardTools`、`body.storeState.stage?.id`、`body.storeState.stage`、`body.webSearchProviderId`、`body.webSearchApiKey`、`body.webSearchBaseUrl`、`body.webSearchModelId`、`body.baiduSubSources`、`body.messages.length`、`body.storeState.whiteboardManualVisibilityRevision`。

请求 / 局部契约 `StatelessChatRequest`（[magicclass-app/lib/types/chat.ts](../../magicclass-app/lib/types/chat.ts)）：

```ts
export interface StatelessChatRequest {
  /** Conversation history (client-maintained) */
  messages: UIMessage<ChatMessageMetadata>[];
  /** Current application state */
  storeState: {
    stage: Stage | null;
    scenes: Scene[];
    /** Thin course map available to the Pi Director before it reads any scene. */
    outlines?: SceneOutline[];
    currentSceneId: string | null;
    mode: StageMode;
    whiteboardOpen: boolean;
    /** Browser-owned manual visibility revision captured for this request. */
    whiteboardManualVisibilityRevision?: number;
    /**
     * Post-submit quiz state for the CURRENT scene, hydrated by the client
     * from localStorage when the active scene is a graded quiz. Lets the
     * agent give targeted feedback on the student's actual answers
     * (correct/incorrect, written response, AI grader comment) instead of
     * guessing. Absent when the student has not submitted yet, or when the
     * active scene is not a quiz.
     */
    quizResults?: {
      sceneId: string;
      answers: Record<string, string | string[]>;
      results: Array<{
        questionId: string;
        correct: boolean | null;
        status: 'correct' | 'incorrect';
        earned: number;
        aiComment?: string;
      }>;
    };
  };
  /** Optional Pi-only, identity-only reference to one classroom component. */
  elementReference?: ElementReference;
  /** Agent configuration */
  config: {
    agentIds: string[];
    sessionType?: 'qa' | 'discussion';
    /** Discussion topic (for agent-initiated discussions) */
    discussionTopic?: string;
    /** Discussion prompt (for agent-initiated discussions) */
    discussionPrompt?: string;
    /** Which agent should speak first in a discussion */
    triggerAgentId?: string;
    /** Full agent configs for generated (non-default) agents that aren't in the server-side registry */
    agentConfigs?: Array<{
      id: string;
      name: string;
      role: string;
      persona: string;
      avatar: string;
      color: string;
      allowedActions: string[];
      priority: number;
      isGenerated?: boolean;
      boundStageId?: string;
    }>;
    /** Pi PoC: max child agent turns in one server-side loop. */
    piMaxAgentTurns?: number;
    /** Pi PoC: max emitted actions per child agent turn. */
    piMaxActionsPerAgent?: number;
    /** Pi PoC: opt in to whiteboard tools; defaults off to keep the first A/B pass comparable. */
    piEnableWhiteboardTools?: boolean;
  };
  /** Accumulated director state from previous per-agent requests */
  directorState?: DirectorState;
  /** Pi-only context for the first request in a newly created live UI session. */
  piSessionBoundary?: PiSessionBoundaryContext;
  /** User profile for personalization */
  userProfile?: {
    nickname?: string;
    bio?: string;
  };
  /** OpenAI-compatible API credentials */
  apiKey: string;
  baseUrl?: string;
  model?: string;
  providerType?: string;
  /**
   * Opt-in: enable provider-side thinking for this request. Default is
   * `{ enabled: false }` (low-latency chat). Eval harness sets this to
   * `{ enabled: true }` when `EVAL_ENABLE_THINKING=1`.
   */
  thinking?: ThinkingConfig;
  /** UI-selected per-model thinking config. Takes precedence over `thinking`. */
  thinkingConfig?: ThinkingConfig;
  /** Toolbar-selected Web Search provider. Resolved server-side independently from the LLM. */
  webSearchProviderId?: WebSearchProviderId;
  /** Selected provider credential only; server-managed credentials remain authoritative. */
  webSearchApiKey?: string;
  /** Selected provider base URL only; validated server-side and ignored for managed providers. */
  webSearchBaseUrl?: string;
  /** Selected Claude Web Search model only. */
  webSearchModelId?: string;
  /** Selected Baidu Web Search sub-sources only. */
  baiduSubSources?: BaiduSubSources;
}
```

请求 / 局部契约 `SendEvent`（[magicclass-app/lib/chat/pi/types.ts](../../magicclass-app/lib/chat/pi/types.ts)）：

```ts
export type SendEvent = (event: StatelessEvent) => Promise<void>;
```

请求 / 局部契约 `ThinkingConfig`（[magicclass-app/lib/types/provider.ts](../../magicclass-app/lib/types/provider.ts)）：

```ts
export interface ThinkingConfig {
  /** Modern mode control. Kept separate from legacy enabled for provider APIs with auto/default. */
  mode?: ThinkingMode;
  /** Discrete reasoning effort used by OpenAI/OpenRouter-style APIs. */
  effort?: ThinkingEffort;
  /** Discrete thinking level used by Gemini 3-style APIs. */
  level?: ThinkingLevel;
  /**
   * Whether thinking should be enabled.
   * - true: enable (use model default or specified budget)
   * - false: disable (adapter uses best-effort for non-toggleable models)
   * - undefined: use model default behavior
   */
  enabled?: boolean;
  /**
   * Budget hint in tokens. Only used when enabled=true or undefined.
   * Adapter maps to closest supported value per provider.
   */
  budgetTokens?: number;
  /** Provider-specific option for APIs that can suppress reasoning text from responses. */
  excludeReasoningOutput?: boolean;
}
```

成功 / 直接响应构造：

```ts
new Response(readable, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
        ...(elementReference ? { [ELEMENT_REFERENCE_ACCEPTED_HEADER]: '1' } : {}),
      },
    })
```

显式异常响应：

```ts
apiError('INVALID_REQUEST', 404, 'Pi chat runtime is disabled')

apiError('MISSING_REQUIRED_FIELD', 400, 'Missing required field: messages')

apiError('MISSING_REQUIRED_FIELD', 400, 'Missing required field: storeState')

apiError('MISSING_REQUIRED_FIELD', 400, 'Missing required field: config.agentIds')

apiError('INVALID_REQUEST', 400, 'Courseware references are disabled')

apiError('INVALID_REQUEST', 400, error.message)

apiError(
        'INVALID_REQUEST',
        400,
        'config.agentIds must be a non-empty array of unique, non-empty strings',
      )

apiError('MISSING_API_KEY', 401, 'API Key is required')

apiError(
        'INVALID_REQUEST',
        400,
        `Unknown classroom agents in config.agentIds: ${unresolvedAgentIds.join(', ')}`,
      )

apiError(
        'INVALID_REQUEST',
        400,
        `No valid classroom agents found for config.agentIds: ${body.config.agentIds.join(', ')}`,
      )

apiError('INVALID_REQUEST', 400, message)

apiError(
      'INTERNAL_ERROR',
      500,
      error instanceof Error ? error.message : 'Failed to process request',
    )
```

### `POST /api/chat/pi/whiteboard-visibility`

实现：[magicclass-app/app/api/chat/pi/whiteboard-visibility/route.ts](../../magicclass-app/app/api/chat/pi/whiteboard-visibility/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
req.json()
```

handler 使用的业务字段：`body.queryId`、`body.queryId.length`、`body.stageId`、`body.stageId.length`、`body.visibility`。

请求 / 局部契约 `BODY_KEYS`（[magicclass-app/app/api/chat/pi/whiteboard-visibility/route.ts](../../magicclass-app/app/api/chat/pi/whiteboard-visibility/route.ts)）：

```ts
BODY_KEYS = new Set(['queryId', 'stageId', 'visibility'])
```

成功 / 直接响应构造：

```ts
new Response(null, { status: 204 })
```

显式异常响应：

```ts
apiError('INVALID_CREDENTIALS', 401, 'Invalid persistence development binding')

apiError('INVALID_REQUEST', 400, 'Invalid whiteboard visibility response')

apiError('INVALID_REQUEST', 404, 'Whiteboard visibility query is not pending here')
```

### `POST /api/chat`

实现：[magicclass-app/app/api/chat/route.ts](../../magicclass-app/app/api/chat/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
body: StatelessChatRequest = await req.json()
```

handler 使用的业务字段：`body.model`、`body.messages?.length`、`body.messages`、`body.storeState`、`body.config`、`body.config.agentIds`、`body.config.agentIds.length`、`body.apiKey`、`body.baseUrl`、`body.providerType`、`body.thinkingConfig`、`body.thinking`、`body.config.agentIds.join`、`body.messages.length`、`body.directorState?.turnCount`、`body.directorState`、`body.config?.agentIds?.length`、`body.config?.agentIds`。

请求 / 局部契约 `StatelessChatRequest`（[magicclass-app/lib/types/chat.ts](../../magicclass-app/lib/types/chat.ts)）：

```ts
export interface StatelessChatRequest {
  /** Conversation history (client-maintained) */
  messages: UIMessage<ChatMessageMetadata>[];
  /** Current application state */
  storeState: {
    stage: Stage | null;
    scenes: Scene[];
    /** Thin course map available to the Pi Director before it reads any scene. */
    outlines?: SceneOutline[];
    currentSceneId: string | null;
    mode: StageMode;
    whiteboardOpen: boolean;
    /** Browser-owned manual visibility revision captured for this request. */
    whiteboardManualVisibilityRevision?: number;
    /**
     * Post-submit quiz state for the CURRENT scene, hydrated by the client
     * from localStorage when the active scene is a graded quiz. Lets the
     * agent give targeted feedback on the student's actual answers
     * (correct/incorrect, written response, AI grader comment) instead of
     * guessing. Absent when the student has not submitted yet, or when the
     * active scene is not a quiz.
     */
    quizResults?: {
      sceneId: string;
      answers: Record<string, string | string[]>;
      results: Array<{
        questionId: string;
        correct: boolean | null;
        status: 'correct' | 'incorrect';
        earned: number;
        aiComment?: string;
      }>;
    };
  };
  /** Optional Pi-only, identity-only reference to one classroom component. */
  elementReference?: ElementReference;
  /** Agent configuration */
  config: {
    agentIds: string[];
    sessionType?: 'qa' | 'discussion';
    /** Discussion topic (for agent-initiated discussions) */
    discussionTopic?: string;
    /** Discussion prompt (for agent-initiated discussions) */
    discussionPrompt?: string;
    /** Which agent should speak first in a discussion */
    triggerAgentId?: string;
    /** Full agent configs for generated (non-default) agents that aren't in the server-side registry */
    agentConfigs?: Array<{
      id: string;
      name: string;
      role: string;
      persona: string;
      avatar: string;
      color: string;
      allowedActions: string[];
      priority: number;
      isGenerated?: boolean;
      boundStageId?: string;
    }>;
    /** Pi PoC: max child agent turns in one server-side loop. */
    piMaxAgentTurns?: number;
    /** Pi PoC: max emitted actions per child agent turn. */
    piMaxActionsPerAgent?: number;
    /** Pi PoC: opt in to whiteboard tools; defaults off to keep the first A/B pass comparable. */
    piEnableWhiteboardTools?: boolean;
  };
  /** Accumulated director state from previous per-agent requests */
  directorState?: DirectorState;
  /** Pi-only context for the first request in a newly created live UI session. */
  piSessionBoundary?: PiSessionBoundaryContext;
  /** User profile for personalization */
  userProfile?: {
    nickname?: string;
    bio?: string;
  };
  /** OpenAI-compatible API credentials */
  apiKey: string;
  baseUrl?: string;
  model?: string;
  providerType?: string;
  /**
   * Opt-in: enable provider-side thinking for this request. Default is
   * `{ enabled: false }` (low-latency chat). Eval harness sets this to
   * `{ enabled: true }` when `EVAL_ENABLE_THINKING=1`.
   */
  thinking?: ThinkingConfig;
  /** UI-selected per-model thinking config. Takes precedence over `thinking`. */
  thinkingConfig?: ThinkingConfig;
  /** Toolbar-selected Web Search provider. Resolved server-side independently from the LLM. */
  webSearchProviderId?: WebSearchProviderId;
  /** Selected provider credential only; server-managed credentials remain authoritative. */
  webSearchApiKey?: string;
  /** Selected provider base URL only; validated server-side and ignored for managed providers. */
  webSearchBaseUrl?: string;
  /** Selected Claude Web Search model only. */
  webSearchModelId?: string;
  /** Selected Baidu Web Search sub-sources only. */
  baiduSubSources?: BaiduSubSources;
}
```

请求 / 局部契约 `ThinkingConfig`（[magicclass-app/lib/types/provider.ts](../../magicclass-app/lib/types/provider.ts)）：

```ts
export interface ThinkingConfig {
  /** Modern mode control. Kept separate from legacy enabled for provider APIs with auto/default. */
  mode?: ThinkingMode;
  /** Discrete reasoning effort used by OpenAI/OpenRouter-style APIs. */
  effort?: ThinkingEffort;
  /** Discrete thinking level used by Gemini 3-style APIs. */
  level?: ThinkingLevel;
  /**
   * Whether thinking should be enabled.
   * - true: enable (use model default or specified budget)
   * - false: disable (adapter uses best-effort for non-toggleable models)
   * - undefined: use model default behavior
   */
  enabled?: boolean;
  /**
   * Budget hint in tokens. Only used when enabled=true or undefined.
   * Adapter maps to closest supported value per provider.
   */
  budgetTokens?: number;
  /** Provider-specific option for APIs that can suppress reasoning text from responses. */
  excludeReasoningOutput?: boolean;
}
```

请求 / 局部契约 `StatelessEvent`（[magicclass-app/lib/types/chat.ts](../../magicclass-app/lib/types/chat.ts)）：

```ts
export type StatelessEvent =
  | {
      type: 'agent_start';
      data: {
        messageId: string;
        agentId: string;
        agentName: string;
        agentAvatar?: string;
        agentColor?: string;
      };
    }
  | { type: 'agent_end'; data: { messageId: string; agentId: string } }
  | { type: 'text_delta'; data: { content: string; messageId?: string } }
  | {
      type: 'action';
      data: {
        actionId: string;
        actionName: string;
        params: Record<string, unknown>;
        agentId: string;
        messageId?: string;
      };
    }
  | {
      type: 'thinking';
      data: { stage: 'director' | 'agent_loading'; agentId?: string };
    }
  | {
      type: 'whiteboard';
      data:
        | { kind: 'visibility_query'; queryId: string; stageId: string }
        | {
            kind: 'open' | 'close';
            stageId: string;
            manualVisibilityRevision: number;
          }
        | { kind: 'projection'; stageId: string; lastSeq: number };
    }
  | { type: 'cue_user'; data: { fromAgentId?: string; prompt?: string } }
  | {
      type: 'done';
      data: {
        totalActions: number;
        totalAgents: number;
        agentHadContent?: boolean;
        cueUserReceived?: boolean;
        sessionClosed?: boolean;
        endReason?: string;
        directorCompaction?: DirectorCompactionTrace;
        directorToolTrace?: DirectorToolTraceEntry[];
        directorState?: DirectorState;
      };
    }
  | { type: 'error'; data: { message: string } };
```

成功 / 直接响应构造：

```ts
new Response(readable, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
      },
    })
```

显式异常响应：

```ts
apiError('MISSING_REQUIRED_FIELD', 400, 'Missing required field: messages')

apiError('MISSING_REQUIRED_FIELD', 400, 'Missing required field: storeState')

apiError('MISSING_REQUIRED_FIELD', 400, 'Missing required field: config.agentIds')

apiError('MISSING_API_KEY', 401, 'API Key is required')

apiError(
      'INTERNAL_ERROR',
      500,
      error instanceof Error ? error.message : 'Failed to process request',
    )
```

### `GET /api/classroom-media/{classroomId}/{...path}`

实现：[magicclass-app/app/api/classroom-media/[classroomId]/[...path]/route.ts](../../magicclass-app/app/api/classroom-media/[classroomId]/[...path]/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求头读取：

```ts
req.headers.get('range')
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

成功 / 直接响应构造：

```ts
NextResponse.json({ error: 'Invalid classroom ID' }, { status: 400 })

NextResponse.json({ error: 'Invalid path' }, { status: 400 })

NextResponse.json({ error: 'Invalid path' }, { status: 404 })

NextResponse.json({ error: 'Not found' }, { status: 404 })

new NextResponse(null, {
        status: 416,
        headers: {
          'Cache-Control': 'no-store',
          'Content-Range': `bytes */${stat.size}`,
        },
      })

new NextResponse(toWebStream(stream), {
        status: 206,
        headers: {
          ...CACHE_HEADERS,
          'Content-Type': contentType,
          'Content-Length': String(range.end - range.start + 1),
          'Content-Range': `bytes ${range.start}-${range.end}/${stat.size}`,
          'Accept-Ranges': 'bytes',
        },
      })

new NextResponse(toWebStream(createReadStream(realPath)), {
      status: 200,
      headers: {
        ...CACHE_HEADERS,
        'Content-Type': contentType,
        'Content-Length': String(stat.size),
        'Accept-Ranges': 'bytes',
      },
    })

NextResponse.json({ error: 'Internal error' }, { status: 500 })
```

### `POST /api/classroom`

实现：[magicclass-app/app/api/classroom/route.ts](../../magicclass-app/app/api/classroom/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
body = await request.json()
```

成功 / 直接响应构造：

```ts
apiSuccess({ id: persisted.id, url: persisted.url }, 201)
```

显式异常响应：

```ts
apiError(
        API_ERROR_CODES.MISSING_REQUIRED_FIELD,
        400,
        'Missing required fields: stage, scenes',
      )

apiError(API_ERROR_CODES.INVALID_REQUEST, 400, 'Invalid classroom stage')

apiError(
        API_ERROR_CODES.INVALID_REQUEST,
        400,
        'Invalid classroom scenes: must be an array',
      )

apiError(
          API_ERROR_CODES.INVALID_REQUEST,
          400,
          `Invalid classroom scene at index ${index}`,
          first ? describeSceneIssue(first) : undefined,
        )

apiError(API_ERROR_CODES.INVALID_REQUEST, 400, 'Invalid classroom id')

apiError(API_ERROR_CODES.INVALID_REQUEST, 409, 'Classroom id collision')

apiError(
      API_ERROR_CODES.INTERNAL_ERROR,
      500,
      'Failed to store classroom',
      error instanceof Error ? error.message : String(error),
    )
```

### `GET /api/classroom`

实现：[magicclass-app/app/api/classroom/route.ts](../../magicclass-app/app/api/classroom/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

Query 读取：

```ts
request.nextUrl.searchParams.get('id')
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

成功 / 直接响应构造：

```ts
apiSuccess({ classroom: sanitizeSceneContent(classroom) })
```

显式异常响应：

```ts
apiError(
        API_ERROR_CODES.MISSING_REQUIRED_FIELD,
        400,
        'Missing required parameter: id',
      )

apiError(API_ERROR_CODES.INVALID_REQUEST, 400, 'Invalid classroom id')

apiError(API_ERROR_CODES.INVALID_REQUEST, 404, 'Classroom not found')

apiError(
      API_ERROR_CODES.INTERNAL_ERROR,
      500,
      'Failed to retrieve classroom',
      error instanceof Error ? error.message : String(error),
    )
```

### `GET /api/comfyui-workflows`

实现：[magicclass-app/app/api/comfyui-workflows/route.ts](../../magicclass-app/app/api/comfyui-workflows/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

成功 / 直接响应构造：

```ts
NextResponse.json({ workflows: await listComfyuiWorkflows() })

NextResponse.json({ workflows: [] })
```

### `GET /api/export-video/capability`

实现：[magicclass-app/app/api/export-video/capability/route.ts](../../magicclass-app/app/api/export-video/capability/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

成功 / 直接响应构造：

```ts
apiSuccess({ ...capability })
```

### `GET /api/export-video/render/{jobId}/download`

实现：[magicclass-app/app/api/export-video/render/[jobId]/download/route.ts](../../magicclass-app/app/api/export-video/render/[jobId]/download/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

成功 / 直接响应构造：

```ts
new NextResponse(upstream.body, {
      status: 200,
      headers: {
        'Content-Type': 'video/mp4',
        ...(upstream.headers.get('content-length')
          ? { 'Content-Length': upstream.headers.get('content-length')! }
          : {}),
        'Content-Disposition': `attachment; filename="${jobId}.mp4"`,
        'Cache-Control': 'private, no-store',
      },
    })
```

显式异常响应：

```ts
apiError('PROVIDER_DISABLED', 501, 'Render service is not configured')

apiError('UPSTREAM_ERROR', status, 'Render output not available')

apiError('UPSTREAM_ERROR', 502, 'Failed to reach render service')
```

共享实现返回 / 转发表达式：

```ts
NextResponse.redirect(location, 302)
```

### `GET /api/export-video/render/{jobId}`

实现：[magicclass-app/app/api/export-video/render/[jobId]/route.ts](../../magicclass-app/app/api/export-video/render/[jobId]/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

成功 / 直接响应构造：

```ts
apiSuccess({ ...data, pollIntervalMs: 3000 })
```

显式异常响应：

```ts
apiError('PROVIDER_DISABLED', 501, 'Render service is not configured')

apiError('UPSTREAM_ERROR', status, 'Render job lookup failed')

apiError('UPSTREAM_ERROR', 502, 'Failed to reach render service')
```

### `DELETE /api/export-video/render/{jobId}`

实现：[magicclass-app/app/api/export-video/render/[jobId]/route.ts](../../magicclass-app/app/api/export-video/render/[jobId]/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

成功 / 直接响应构造：

```ts
apiSuccess({ cancelled: true })
```

显式异常响应：

```ts
apiError('PROVIDER_DISABLED', 501, 'Render service is not configured')

apiError('UPSTREAM_ERROR', 502, 'Failed to cancel render job')

apiError('UPSTREAM_ERROR', 502, 'Failed to reach render service')
```

### `POST /api/export-video/render`

实现：[magicclass-app/app/api/export-video/render/route.ts](../../magicclass-app/app/api/export-video/render/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求头读取：

```ts
req.headers.get('content-length')
req.headers.get('content-type')
```

请求体：multipart/form-data 的导出 ZIP，原始流直接转发渲染服务；最大 300 MiB，不能使用 JSON。成功 202 返回 jobId 与 pollIntervalMs=3000；未配置服务为 501。

成功 / 直接响应构造：

```ts
apiSuccess({ jobId: data.jobId, pollIntervalMs: 3000 }, 202)
```

显式异常响应：

```ts
apiError('PROVIDER_DISABLED', 501, 'Render service is not configured')

apiError('INVALID_REQUEST', 413, 'Export archive is too large')

apiError('INVALID_REQUEST', 400, 'Expected multipart/form-data')

apiError(code, status, 'Render service rejected the request', detail)

apiError(
      'UPSTREAM_ERROR',
      502,
      'Failed to reach render service',
      error instanceof Error ? error.message : String(error),
    )
```

### `POST /api/extract-document`

实现：[magicclass-app/app/api/extract-document/route.ts](../../magicclass-app/app/api/extract-document/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求头读取：

```ts
req.headers.get('content-type')
```

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
formData = await req.formData()
documentFile = (formData.get('file') || formData.get('pdf')) as File | null
req.json()
```

handler 使用的业务字段：`body.assetId`、`body.assetId.length`、`body.fileName`、`body.mimeType`、`body.providerId`、`body.apiKey`、`body.baseUrl`、`body.accessKeyId`、`body.accessKeySecret`。

请求 / 局部契约 `ExtractLogState`（[magicclass-app/app/api/extract-document/route.ts](../../magicclass-app/app/api/extract-document/route.ts)）：

```ts
interface ExtractLogState {
  fileName?: string;
  resolvedProviderId?: string;
}
```

请求 / 局部契约 `ExtractSource`（[magicclass-app/app/api/extract-document/route.ts](../../magicclass-app/app/api/extract-document/route.ts)）：

```ts
interface ExtractSource {
  fileName: string;
  fileSize: number;
  /** Normalized canonical MIME type (see `normalizeDocumentMimeType`). */
  mimeType: string;
  buffer: Buffer;
}
```

请求 / 局部契约 `ExtractRequestConfig`（[magicclass-app/app/api/extract-document/route.ts](../../magicclass-app/app/api/extract-document/route.ts)）：

```ts
interface ExtractRequestConfig {
  providerId?: string;
  apiKey?: string;
  baseUrl?: string;
  accessKeyId?: string;
  accessKeySecret?: string;
}
```

请求 / 局部契约 `AssetIdExtractRequest`（[magicclass-app/app/api/extract-document/route.ts](../../magicclass-app/app/api/extract-document/route.ts)）：

```ts
interface AssetIdExtractRequest extends ExtractRequestConfig {
  assetId?: string;
  fileName?: string;
  mimeType?: string;
}
```

请求 / 局部契约 `ServerAssetResolution`（[magicclass-app/lib/persistence/resolve-server-asset.ts](../../magicclass-app/lib/persistence/resolve-server-asset.ts)）：

```ts
export type ServerAssetResolution =
  | { status: 'resolved'; buffer: Buffer; mimeType: string }
  | { status: 'unconfigured' }
  | { status: 'unauthenticated' }
  | { status: 'missing' }
  | { status: 'too_large' };
```

请求 / 局部契约 `ParsedPdfContent`（[magicclass-app/lib/types/pdf.ts](../../magicclass-app/lib/types/pdf.ts)）：

```ts
export interface ParsedPdfContent {
  /** Extracted text content from the PDF */
  text: string;

  /** Array of images as base64 data URLs */
  images: string[];

  /** Extracted tables (MinerU feature) */
  tables?: Array<{
    page: number;
    data: string[][];
    caption?: string;
  }>;

  /** Extracted formulas (MinerU feature) */
  formulas?: Array<{
    page: number;
    latex: string;
    position?: { x: number; y: number; width: number; height: number };
  }>;

  /** Layout analysis (MinerU feature) */
  layout?: Array<{
    page: number;
    type: 'title' | 'text' | 'image' | 'table' | 'formula';
    content: string;
    position?: { x: number; y: number; width: number; height: number };
  }>;

  /** Metadata about the PDF */
  metadata?: {
    fileName?: string;
    fileSize?: number;
    pageCount: number;
    parser?: string; // 'unpdf' | 'mineru'
    processingTime?: number;
    taskId?: string; // MinerU task ID
    /** Image ID to base64 URL mapping (used in generation pipeline) */
    imageMapping?: Record<string, string>; // e.g., { "img_1": "data:image/png;base64,..." }
    /** PdfImage array with page numbers (used in generation pipeline) */
    pdfImages?: Array<{
      id: string;
      src: string;
      pageNumber: number;
      description?: string;
      width?: number;
      height?: number;
      /**
       * Pool asset id of the image bytes. Present only on cache-rebuilt
       * results in asset-id mode (RFC #1153 part 2 C): a server-backed cache
       * hit names the image's pool asset instead of materializing its bytes.
       */
      assetId?: string;
    }>;
    [key: string]: unknown;
  };
}
```

请求 / 局部契约 `PDFProviderId`（[magicclass-app/lib/pdf/types.ts](../../magicclass-app/lib/pdf/types.ts)）：

```ts
export type PDFProviderId = 'unpdf' | 'mineru' | 'mineru-cloud' | 'alidocmind';
```

成功 / 直接响应构造：

```ts
apiSuccess({ data: mediaResult })

apiSuccess({ data: resultWithMetadata })
```

显式异常响应：

```ts
apiError('MISSING_REQUIRED_FIELD', 400, 'No course material file provided')

apiError(
          'INVALID_REQUEST',
          400,
          `Unsupported course material type for "${documentFile.name}"`,
        )

apiError(
          'INVALID_REQUEST',
          413,
          `Course material file is too large. Maximum size is ${Math.floor(
            MAX_EXTRACT_DOCUMENT_FILE_SIZE_BYTES / 1024 / 1024,
          )}MB.`,
        )

apiError('INVALID_REQUEST', 400, 'Invalid JSON body for asset-id extraction.')

apiError('INVALID_REQUEST', 400, 'Invalid request body for asset-id extraction')

apiError('MISSING_REQUIRED_FIELD', 400, 'No asset id provided')

apiError(
          'INTERNAL_ERROR',
          500,
          'The server asset store is unavailable. Please try again later.',
        )

apiError(
          'INVALID_REQUEST',
          503,
          'Server persistence is not configured; asset-id extraction requires a server-backed asset pool.',
        )

apiError(
          'UNAUTHENTICATED',
          401,
          'Asset-id extraction requires server persistence credentials.',
        )

apiError(
          'ASSET_NOT_FOUND',
          404,
          'No course material asset was found for the requested asset id.',
        )

apiError('INVALID_REQUEST', 400, 'Unsupported course material type.')

apiError(
        'INVALID_REQUEST',
        400,
        `Invalid Content-Type: expected multipart/form-data or application/json, got "${contentType}"`,
      )

apiError(
        'PARSE_FAILED',
        500,
        'The course material could not be parsed. Please try again later.',
      )

apiError('PARSE_FAILED', 500, error instanceof Error ? error.message : 'Unknown error')

apiError(
        'INVALID_REQUEST',
        400,
        'The requested extractor cannot process this course material.',
      )

apiError(
      'INVALID_REQUEST',
      400,
      'The requested document extractor cannot process this course material.',
    )

apiError(
        'INVALID_REQUEST',
        400,
        `Provider "${requestConfig.providerId}" cannot extract ${mimeType}. Choose a media-capable provider (AliDocMind or local ffmpeg).`,
      )

apiError('INVALID_URL', 403, ssrfError)

apiError(
        'PARSE_FAILED',
        422,
        isAssetIdForm
          ? 'No transcript, keyframes, or synopsis could be extracted from this course material.'
          : `No transcript, keyframes, or synopsis could be extracted from "${fileName}".`,
      )

apiError(
      'INVALID_REQUEST',
      400,
      `Unknown document extractor provider: ${requestConfig.providerId}`,
    )

apiError(
      'INVALID_REQUEST',
      400,
      isAssetIdForm
        ? 'The requested document extractor cannot process this course material.'
        : error instanceof Error
          ? error.message
          : `Unsupported course material type "${mimeType}"`,
    )

apiError(
        'INVALID_REQUEST',
        422,
        `${requestedTypeLabel(mimeType)} extraction requires a configured MinerU document extractor. ` +
          `Self-hosted MinerU was selected, but no self-hosted MinerU base URL is configured, so it is ` +
          `unavailable. Documents are not sent to MinerU Cloud automatically: configure a self-hosted MinerU ` +
          `base URL in PDF provider settings, or set ALLOW_MINERU_CLOUD_FALLBACK=1 to explicitly allow the ` +
          `MinerU Cloud fallback.`,
      )
```

共享实现返回 / 转发表达式：

```ts
providerValidationError

await runExtraction(source, requestConfig, logState, isAssetIdForm)
```

### `PATCH /api/folders/{id}`

实现：[magicclass-app/app/api/folders/[id]/route.ts](../../magicclass-app/app/api/folders/[id]/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
req.json()
```

请求 / 局部契约 `Params`（[magicclass-app/app/api/folders/[id]/route.ts](../../magicclass-app/app/api/folders/[id]/route.ts)）：

```ts
type Params = { params: Promise<{ id: string }> };
```

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

ownerJson({ folder: folderResponse(updated, ownerId) }, 200, responseHeaders)

NextResponse.json({ error: { code, message } }, { status, headers })
```

显式异常响应：

```ts
jsonError(400, 'INVALID_BODY', 'request body must be JSON')

jsonError(400, 'FOLDER_NAME_INVALID', 'name must be a string')

jsonError(
      400,
      check.kind === 'empty' ? 'FOLDER_NAME_EMPTY' : 'FOLDER_NAME_TOO_LONG',
      check.kind === 'empty' ? 'folder name must not be empty' : 'folder name is too long',
    )

jsonError(
          409,
          'FOLDER_NAME_DUPLICATE',
          'a folder with this name already exists',
          responseHeaders,
        )

jsonError(404, 'FOLDER_NOT_FOUND', 'folder not found', responseHeaders)

jsonError(500, 'FOLDER_RENAME_FAILED', 'Failed to rename folder', responseHeaders)
```

共享实现返回 / 转发表达式：

```ts
jsonError(400, 'INVALID_BODY', 'request body must be JSON')

jsonError(400, 'FOLDER_NAME_INVALID', 'name must be a string')

jsonError(
      400,
      check.kind === 'empty' ? 'FOLDER_NAME_EMPTY' : 'FOLDER_NAME_TOO_LONG',
      check.kind === 'empty' ? 'folder name must not be empty' : 'folder name is too long',
    )

withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    const { id } = await params;
    try {
      const store = (await getOwnerScopedDocumentStore(ownerId)) as unknown as DocumentFolderStore;
      // Excluding itself, same case-insensitive rule as create.
      const existing = await store.listFolders();
      const clash = existing.some(
        (folder) => folder.id !== id && folder.name.toLowerCase() === trimmed.toLowerCase(),
      );
      if (clash) {
        return jsonError(
          409,
          'FOLDER_NAME_DUPLICATE',
          'a folder with this name already exists',
          responseHeaders,
        );
      }

      const updated = await store.renameFolder(id, trimmed);
      if (!updated) {
        return jsonError(404, 'FOLDER_NOT_FOUND', 'folder not found', responseHeaders);
      }
      return ownerJson({ folder: folderResponse(updated, ownerId) }, 200, responseHeaders);
    } catch (error) {
      // The rename re-checks the name through the unique index; a duplicate
      // that slipped past the pre-check answers the same 409.
      const nameError = folderNameErrorResponse(error);
      if (nameError) {
        for (const [key, value] of responseHeaders) nameError.headers.append(key, value);
        return nameError;
      }
      console.error(`[Folders] Failed to rename [owner=${ownerId}, id=${id}]:`, error);
      return jsonError(500, 'FOLDER_RENAME_FAILED', 'Failed to rename folder', responseHeaders);
    }
  })

jsonError(
          409,
          'FOLDER_NAME_DUPLICATE',
          'a folder with this name already exists',
          responseHeaders,
        )

jsonError(404, 'FOLDER_NOT_FOUND', 'folder not found', responseHeaders)

ownerJson({ folder: folderResponse(updated, ownerId) }, 200, responseHeaders)

nameError

jsonError(500, 'FOLDER_RENAME_FAILED', 'Failed to rename folder', responseHeaders)
```

### `DELETE /api/folders/{id}`

实现：[magicclass-app/app/api/folders/[id]/route.ts](../../magicclass-app/app/api/folders/[id]/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

Query 读取：

```ts
req.nextUrl.searchParams.get('mode')
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

请求 / 局部契约 `Params`（[magicclass-app/app/api/folders/[id]/route.ts](../../magicclass-app/app/api/folders/[id]/route.ts)）：

```ts
type Params = { params: Promise<{ id: string }> };
```

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

ownerJson({ ok: true, removedStageIds: result.removedStageIds }, 200, responseHeaders)

NextResponse.json({ error: { code, message } }, { status, headers })
```

显式异常响应：

```ts
jsonError(404, 'FOLDER_NOT_FOUND', 'folder not found', responseHeaders)

jsonError(500, 'FOLDER_DELETE_FAILED', 'Failed to delete folder', responseHeaders)
```

共享实现返回 / 转发表达式：

```ts
withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    const { id } = await params;
    try {
      const store = (await getOwnerScopedDocumentStore(ownerId)) as unknown as DocumentFolderStore;
      const result = await store.deleteFolder(id, mode);
      if (!result) {
        return jsonError(404, 'FOLDER_NOT_FOUND', 'folder not found', responseHeaders);
      }
      return ownerJson({ ok: true, removedStageIds: result.removedStageIds }, 200, responseHeaders);
    } catch (error) {
      console.error(`[Folders] Failed to delete [owner=${ownerId}, id=${id}]:`, error);
      return jsonError(500, 'FOLDER_DELETE_FAILED', 'Failed to delete folder', responseHeaders);
    }
  })

jsonError(404, 'FOLDER_NOT_FOUND', 'folder not found', responseHeaders)

ownerJson({ ok: true, removedStageIds: result.removedStageIds }, 200, responseHeaders)

jsonError(500, 'FOLDER_DELETE_FAILED', 'Failed to delete folder', responseHeaders)
```

### `POST /api/folders/members`

实现：[magicclass-app/app/api/folders/members/route.ts](../../magicclass-app/app/api/folders/members/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
req.json()
```

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

ownerJson({ ok: true }, 200, responseHeaders)

NextResponse.json({ error: { code, message } }, { status, headers })
```

显式异常响应：

```ts
jsonError(400, 'INVALID_BODY', 'request body must be JSON')

jsonError(400, 'MISSING_STAGE_ID', 'stageId must be a non-empty string')

jsonError(400, 'INVALID_FOLDER_ID', 'folderId must be a non-empty string or null')

jsonError(404, 'FOLDER_NOT_FOUND', 'folder not found', responseHeaders)

jsonError(
        500,
        'FOLDER_MEMBER_FAILED',
        'Failed to set folder membership',
        responseHeaders,
      )
```

共享实现返回 / 转发表达式：

```ts
jsonError(400, 'INVALID_BODY', 'request body must be JSON')

jsonError(400, 'MISSING_STAGE_ID', 'stageId must be a non-empty string')

jsonError(400, 'INVALID_FOLDER_ID', 'folderId must be a non-empty string or null')

withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    try {
      const store = (await getOwnerScopedDocumentStore(ownerId)) as unknown as DocumentFolderStore;
      const ok = await store.setStageFolder(stageId, folderId);
      if (!ok) {
        return jsonError(404, 'FOLDER_NOT_FOUND', 'folder not found', responseHeaders);
      }
      return ownerJson({ ok: true }, 200, responseHeaders);
    } catch (error) {
      console.error(
        `[Folders] Failed to set membership [owner=${ownerId}, stage=${stageId}]:`,
        error,
      );
      return jsonError(
        500,
        'FOLDER_MEMBER_FAILED',
        'Failed to set folder membership',
        responseHeaders,
      );
    }
  })

jsonError(404, 'FOLDER_NOT_FOUND', 'folder not found', responseHeaders)

ownerJson({ ok: true }, 200, responseHeaders)

jsonError(
        500,
        'FOLDER_MEMBER_FAILED',
        'Failed to set folder membership',
        responseHeaders,
      )
```

### `GET /api/folders`

实现：[magicclass-app/app/api/folders/route.ts](../../magicclass-app/app/api/folders/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

ownerJson(
        { folders: folders.map((folder) => folderResponse(folder, ownerId)) },
        200,
        responseHeaders,
      )

NextResponse.json({ error: { code, message } }, { status, headers })
```

显式异常响应：

```ts
jsonError(500, 'FOLDER_LIST_FAILED', 'Failed to list folders', responseHeaders)
```

共享实现返回 / 转发表达式：

```ts
withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    try {
      const store = (await getOwnerScopedDocumentStore(ownerId)) as unknown as DocumentFolderStore;
      const folders = await listFoldersForOwner(store);
      return ownerJson(
        { folders: folders.map((folder) => folderResponse(folder, ownerId)) },
        200,
        responseHeaders,
      );
    } catch (error) {
      console.error(`[Folders] Failed to list [owner=${ownerId}]:`, error);
      return jsonError(500, 'FOLDER_LIST_FAILED', 'Failed to list folders', responseHeaders);
    }
  })

ownerJson(
        { folders: folders.map((folder) => folderResponse(folder, ownerId)) },
        200,
        responseHeaders,
      )

jsonError(500, 'FOLDER_LIST_FAILED', 'Failed to list folders', responseHeaders)
```

### `POST /api/folders`

实现：[magicclass-app/app/api/folders/route.ts](../../magicclass-app/app/api/folders/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
req.json()
```

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

ownerJson({ folder: folderResponse(folder, ownerId) }, 200, responseHeaders)

NextResponse.json({ error: { code, message } }, { status, headers })
```

显式异常响应：

```ts
jsonError(400, 'INVALID_BODY', 'request body must be JSON')

jsonError(400, 'FOLDER_NAME_INVALID', 'name must be a string')

jsonError(
      400,
      check.kind === 'empty' ? 'FOLDER_NAME_EMPTY' : 'FOLDER_NAME_TOO_LONG',
      check.kind === 'empty' ? 'folder name must not be empty' : 'folder name is too long',
    )

jsonError(500, 'FOLDER_CREATE_FAILED', 'Failed to create folder', responseHeaders)
```

共享实现返回 / 转发表达式：

```ts
jsonError(400, 'INVALID_BODY', 'request body must be JSON')

jsonError(400, 'FOLDER_NAME_INVALID', 'name must be a string')

jsonError(
      400,
      check.kind === 'empty' ? 'FOLDER_NAME_EMPTY' : 'FOLDER_NAME_TOO_LONG',
      check.kind === 'empty' ? 'folder name must not be empty' : 'folder name is too long',
    )

withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    try {
      const store = (await getOwnerScopedDocumentStore(ownerId)) as unknown as DocumentFolderStore;
      const { folder } = await createFolderForOwner(store, trimmed, { reuseExisting: false });
      return ownerJson({ folder: folderResponse(folder, ownerId) }, 200, responseHeaders);
    } catch (error) {
      // The storage re-checks duplicates + count limit inside its owner-scoped
      // transaction; map its refusals onto the same machine codes the
      // pre-checks use.
      const nameError = folderNameErrorResponse(error);
      if (nameError) {
        for (const [key, value] of responseHeaders) nameError.headers.append(key, value);
        return nameError;
      }
      console.error(`[Folders] Failed to create [owner=${ownerId}]:`, error);
      return jsonError(500, 'FOLDER_CREATE_FAILED', 'Failed to create folder', responseHeaders);
    }
  })

ownerJson({ folder: folderResponse(folder, ownerId) }, 200, responseHeaders)

nameError

jsonError(500, 'FOLDER_CREATE_FAILED', 'Failed to create folder', responseHeaders)
```

### `GET /api/generate-classroom/{jobId}`

实现：[magicclass-app/app/api/generate-classroom/[jobId]/route.ts](../../magicclass-app/app/api/generate-classroom/[jobId]/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

成功 / 直接响应构造：

```ts
apiSuccess({
      jobId: job.id,
      status: job.status,
      step: job.step,
      progress: job.progress,
      message: job.message,
      pollUrl,
      pollIntervalMs: 5000,
      scenesGenerated: job.scenesGenerated,
      totalScenes: job.totalScenes,
      result: job.result,
      error: job.error,
      done: job.status === 'succeeded' || job.status === 'failed',
    })
```

显式异常响应：

```ts
apiError('INVALID_REQUEST', 400, 'Invalid classroom generation job id')

apiError('INVALID_REQUEST', 404, 'Classroom generation job not found')

apiError(
      'INTERNAL_ERROR',
      500,
      'Failed to retrieve classroom generation job',
      error instanceof Error ? error.message : String(error),
    )
```

### `POST /api/generate-classroom`

实现：[magicclass-app/app/api/generate-classroom/route.ts](../../magicclass-app/app/api/generate-classroom/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
rawBody = (await req.json()) as Partial<GenerateClassroomInput>
```

handler 使用的业务字段：`rawBody.requirement?.substring`、`rawBody.requirement`、`rawBody.pdfContent`、`rawBody.enableWebSearch`、`rawBody.webSearchProviderId`、`rawBody.webSearchApiKey`、`rawBody.webSearchModelId`、`rawBody.baiduSubSources`、`rawBody.enableImageGeneration`、`rawBody.enableVideoGeneration`、`rawBody.enableTTS`、`rawBody.agentMode`。

请求 / 局部契约 `GenerateClassroomInput`（[magicclass-app/lib/server/classroom-generation.ts](../../magicclass-app/lib/server/classroom-generation.ts)）：

```ts
export interface GenerateClassroomInput {
  requirement: string;
  pdfContent?: { text: string; images: string[] };
  enableWebSearch?: boolean;
  webSearchProviderId?: WebSearchProviderId;
  webSearchApiKey?: string;
  webSearchModelId?: string;
  baiduSubSources?: BaiduSubSources;
  enableImageGeneration?: boolean;
  enableVideoGeneration?: boolean;
  enableTTS?: boolean;
  agentMode?: 'default' | 'generate';
}
```

成功 / 直接响应构造：

```ts
apiSuccess(
      {
        jobId,
        status: job.status,
        step: job.step,
        message: job.message,
        pollUrl,
        pollIntervalMs: 5000,
      },
      202,
    )
```

显式异常响应：

```ts
apiError('MISSING_REQUIRED_FIELD', 400, 'Missing required field: requirement')

apiError(
      'INTERNAL_ERROR',
      500,
      'Failed to create classroom generation job',
      error instanceof Error ? error.message : 'Unknown error',
    )
```

### `POST /api/generate/agent-profiles`

实现：[magicclass-app/app/api/generate/agent-profiles/route.ts](../../magicclass-app/app/api/generate/agent-profiles/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求头读取：

```ts
req.headers.get('x-model') / req.headers.get('x-api-key') / req.headers.get('x-base-url') / req.headers.get('x-provider-type') // resolveModelFromRequest 读取；body 与服务器配置优先级见 resolve-model.ts
```

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
body = (await req.json()) as RequestBody
```

请求 / 局部契约 `RequestBody`（[magicclass-app/app/api/generate/agent-profiles/route.ts](../../magicclass-app/app/api/generate/agent-profiles/route.ts)）：

```ts
interface RequestBody {
  stageInfo: { name: string; description?: string };
  sceneOutlines?: { title: string; description?: string }[];
  languageDirective: string;
  availableAvatars: string[];
  avatarDescriptions?: Array<{ path: string; desc: string }>;
  availableVoices?: Array<{
    providerId: string;
    modelId?: string;
    voiceId: string;
    voiceName: string;
    voiceLanguage?: string;
  }>;
  /** The user's globally selected TTS voice; the teacher/narrator must use it. */
  narratorVoice?: {
    providerId: string;
    voiceId: string;
    modelId?: string;
  };
}
```

请求 / 局部契约 `VoiceBinding`（[magicclass-app/app/api/generate/agent-profiles/route.ts](../../magicclass-app/app/api/generate/agent-profiles/route.ts)）：

```ts
interface VoiceBinding {
  providerId: string;
  modelId?: string;
  voiceId: string;
}
```

请求 / 局部契约 `AdvertisedVoice`（[magicclass-app/app/api/generate/agent-profiles/route.ts](../../magicclass-app/app/api/generate/agent-profiles/route.ts)）：

```ts
type AdvertisedVoice = NonNullable<RequestBody['availableVoices']>[number];
```

成功 / 直接响应构造：

```ts
apiSuccess({ agents })
```

显式异常响应：

```ts
apiError('MISSING_REQUIRED_FIELD', 400, 'stageInfo.name is required')

apiError('MISSING_REQUIRED_FIELD', 400, 'languageDirective is required')

apiError(
        'MISSING_REQUIRED_FIELD',
        400,
        'availableAvatars is required and must not be empty',
      )

apiError('PARSE_FAILED', 500, 'Failed to parse agent profiles from LLM response')

apiError(
        'GENERATION_FAILED',
        500,
        `Expected at least 2 agents but LLM returned ${parsed.agents?.length ?? 0}`,
      )

apiError(
        'GENERATION_FAILED',
        500,
        `Expected exactly 1 teacher but LLM returned ${teacherCount}`,
      )

apiError('INTERNAL_ERROR', 500, error instanceof Error ? error.message : String(error))
```

共享实现返回 / 转发表达式：

```ts
{
        id: `gen-${nanoid(8)}`,
        name: agent.name,
        role: agent.role,
        persona: agent.persona,
        avatar: agent.avatar || availableAvatars[index % availableAvatars.length],
        color: agent.color || AGENT_COLOR_PALETTE[index % AGENT_COLOR_PALETTE.length],
        priority:
          agent.priority ?? (agent.role === 'teacher' ? 10 : agent.role === 'assistant' ? 7 : 5),
        ...(voiceConfig ? { voiceConfig } : {}),
        ...(voiceDesign ? { voiceDesign } : {}),
      }
```

### `POST /api/generate/image`

实现：[magicclass-app/app/api/generate/image/route.ts](../../magicclass-app/app/api/generate/image/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求头读取：

```ts
request.headers.get('x-image-provider')
request.headers.get('x-api-key')
request.headers.get('x-base-url')
request.headers.get('x-image-model')
```

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
body = (await request.json()) as ImageGenerationOptions
```

handler 使用的业务字段：`body.prompt`。

请求 / 局部契约 `ImageGenerationOptions`（[magicclass-app/lib/media/types.ts](../../magicclass-app/lib/media/types.ts)）：

```ts
export interface ImageGenerationOptions {
  /** Text prompt describing the desired image */
  prompt: string;
  /** Optional negative prompt to exclude undesired elements */
  negativePrompt?: string;
  /** Desired output width in pixels */
  width?: number;
  /** Desired output height in pixels */
  height?: number;
  /** Desired aspect ratio (provider will calculate dimensions if width/height not set) */
  aspectRatio?: '16:9' | '4:3' | '1:1' | '9:16';
  /** Optional artistic style (must be supported by the chosen provider) */
  style?: string;
  /** Owning stage, for server-side attribution of a generation call. */
  stageId?: string;
  /** Cancel server-side provider I/O (agent runtime / background callers). */
  signal?: AbortSignal;
}
```

请求 / 局部契约 `ImageProviderId`（[magicclass-app/lib/media/types.ts](../../magicclass-app/lib/media/types.ts)）：

```ts
export type ImageProviderId =
  | 'seedream'
  | 'openai-image'
  | 'qwen-image'
  | 'nano-banana'
  | 'minimax-image'
  | 'grok-image'
  | 'comfyui-image'
  | 'lemonade';
```

成功 / 直接响应构造：

```ts
apiSuccess({ result })
```

显式异常响应：

```ts
apiError('MISSING_REQUIRED_FIELD', 400, 'Missing prompt')

apiError('MISSING_PROVIDER', 400, 'No image provider configured')

apiError('PROVIDER_DISABLED', 403, 'This image provider is disabled by the server')

apiError('INVALID_URL', 403, ssrfError)

apiError(
        'MISSING_API_KEY',
        401,
        `No API key configured for image provider: ${providerId}`,
      )

apiError(
        'MISSING_MODEL',
        400,
        `No model configured for image provider: ${providerId}`,
      )

apiError('CONTENT_SENSITIVE', 400, message)

apiError('INTERNAL_ERROR', 500, message)
```

### `POST /api/generate/scene-actions`

实现：[magicclass-app/app/api/generate/scene-actions/route.ts](../../magicclass-app/app/api/generate/scene-actions/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求头读取：

```ts
req.headers.get('x-model') / req.headers.get('x-api-key') / req.headers.get('x-base-url') / req.headers.get('x-provider-type') // resolveModelFromRequest 读取；body 与服务器配置优先级见 resolve-model.ts
```

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
body = await req.json()
```

请求 / 局部契约 `SceneOutline`（[magicclass-app/lib/types/generation.ts](../../magicclass-app/lib/types/generation.ts)）：

```ts
export interface SceneOutline {
  id: string;
  type: 'slide' | 'quiz' | 'interactive' | 'pbl';
  title: string;
  description: string; // 1-2 sentences describing the purpose
  keyPoints: string[]; // 3-5 core key points
  teachingObjective?: string;
  estimatedDuration?: number; // seconds
  order: number;
  languageNote?: string; // LLM-inferred language note for this scene
  // Suggested image IDs (from PDF-extracted images)
  suggestedImageIds?: string[]; // e.g., ["img_1", "img_3"]
  // AI-generated media requests (when PDF images are insufficient)
  mediaGenerations?: MediaGenerationRequest[]; // e.g., [{ type: 'image', prompt: '...', elementId: 'gen_img_1' }]
  // Quiz-specific config
  quizConfig?: {
    questionCount: number;
    difficulty: 'easy' | 'medium' | 'hard';
    questionTypes: ('single' | 'multiple' | 'text')[];
  };
  /**
   * @deprecated Use widgetType + widgetOutline instead
   * Legacy interactive config - kept for backward compatibility only
   */
  interactiveConfig?: {
    conceptName: string;
    conceptOverview: string;
    designIdea: string;
    subject?: string;
  };
  // PBL-specific config
  pblConfig?: {
    projectTopic: string;
    projectDescription: string;
    targetSkills: string[];
    issueCount?: number;
    /** Opt into role-play scenario planning on top of the standard PBL v2 structure. */
    scenarioRoleplay?: boolean;
    /** Optional scenario brief used only when scenarioRoleplay is true. */
    scenarioBrief?: string;
  };
  // Widget fields (required for type === 'interactive' in unified mode)
  widgetType?: WidgetType;
  widgetOutline?: WidgetOutline;
}
```

请求 / 局部契约 `GeneratedSlideContent`（[magicclass-app/lib/types/generation.ts](../../magicclass-app/lib/types/generation.ts)）：

```ts
export interface GeneratedSlideContent {
  elements: PPTElement[];
  background?: SlideBackground;
  remark?: string;
}
```

请求 / 局部契约 `GeneratedQuizContent`（[magicclass-app/lib/types/generation.ts](../../magicclass-app/lib/types/generation.ts)）：

```ts
export interface GeneratedQuizContent {
  questions: QuizQuestion[];
}
```

请求 / 局部契约 `GeneratedInteractiveContent`（[magicclass-app/lib/types/generation.ts](../../magicclass-app/lib/types/generation.ts)）：

```ts
export interface GeneratedInteractiveContent {
  html: string;
  scientificModel?: ScientificModel;
  widgetType?: WidgetType;
  widgetConfig?: WidgetConfig;
}
```

请求 / 局部契约 `GeneratedPBLContent`（[magicclass-app/lib/types/generation.ts](../../magicclass-app/lib/types/generation.ts)）：

```ts
export interface GeneratedPBLContent {
  projectV2: PBLProjectV2;
}
```

请求 / 局部契约 `PBLContent`（[magicclass-app/lib/types/stage.ts](../../magicclass-app/lib/types/stage.ts)）：

```ts
export type PBLContent = DslPBLContent & {
  projectConfig?: PBLProjectConfig & Record<string, unknown>;
  projectV2?: PBLProjectV2;
};
```

成功 / 直接响应构造：

```ts
apiSuccess({ scene, previousSpeeches: outputPreviousSpeeches })
```

显式异常响应：

```ts
apiError('MISSING_REQUIRED_FIELD', 400, 'outline is required')

apiError(
        'MISSING_REQUIRED_FIELD',
        400,
        'allOutlines is required and must not be empty',
      )

apiError('MISSING_REQUIRED_FIELD', 400, 'content is required')

apiError('MISSING_REQUIRED_FIELD', 400, 'stageId is required')

apiError('GENERATION_FAILED', 500, `Failed to build scene: ${outline.title}`)
```

共享实现返回 / 转发表达式：

```ts
result.text

llmApiError(error)
```

### `POST /api/generate/scene-content`

实现：[magicclass-app/app/api/generate/scene-content/route.ts](../../magicclass-app/app/api/generate/scene-content/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求头读取：

```ts
req.headers.get('x-model') / req.headers.get('x-api-key') / req.headers.get('x-base-url') / req.headers.get('x-provider-type') // resolveModelFromRequest 读取；body 与服务器配置优先级见 resolve-model.ts
```

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
body = await req.json()
```

请求 / 局部契约 `SceneOutline`（[magicclass-app/lib/types/generation.ts](../../magicclass-app/lib/types/generation.ts)）：

```ts
export interface SceneOutline {
  id: string;
  type: 'slide' | 'quiz' | 'interactive' | 'pbl';
  title: string;
  description: string; // 1-2 sentences describing the purpose
  keyPoints: string[]; // 3-5 core key points
  teachingObjective?: string;
  estimatedDuration?: number; // seconds
  order: number;
  languageNote?: string; // LLM-inferred language note for this scene
  // Suggested image IDs (from PDF-extracted images)
  suggestedImageIds?: string[]; // e.g., ["img_1", "img_3"]
  // AI-generated media requests (when PDF images are insufficient)
  mediaGenerations?: MediaGenerationRequest[]; // e.g., [{ type: 'image', prompt: '...', elementId: 'gen_img_1' }]
  // Quiz-specific config
  quizConfig?: {
    questionCount: number;
    difficulty: 'easy' | 'medium' | 'hard';
    questionTypes: ('single' | 'multiple' | 'text')[];
  };
  /**
   * @deprecated Use widgetType + widgetOutline instead
   * Legacy interactive config - kept for backward compatibility only
   */
  interactiveConfig?: {
    conceptName: string;
    conceptOverview: string;
    designIdea: string;
    subject?: string;
  };
  // PBL-specific config
  pblConfig?: {
    projectTopic: string;
    projectDescription: string;
    targetSkills: string[];
    issueCount?: number;
    /** Opt into role-play scenario planning on top of the standard PBL v2 structure. */
    scenarioRoleplay?: boolean;
    /** Optional scenario brief used only when scenarioRoleplay is true. */
    scenarioBrief?: string;
  };
  // Widget fields (required for type === 'interactive' in unified mode)
  widgetType?: WidgetType;
  widgetOutline?: WidgetOutline;
}
```

请求 / 局部契约 `PdfImage`（[magicclass-app/lib/types/generation.ts](../../magicclass-app/lib/types/generation.ts)）：

```ts
export interface PdfImage {
  id: string; // e.g., "img_1", "img_2"
  src: string; // base64 data URL (empty when stored in IndexedDB)
  pageNumber: number; // Page number in PDF
  description?: string; // Optional description for AI context
  storageId?: string; // Reference to IndexedDB (session_xxx_img_1)
  /**
   * Pool asset id of the image bytes. Present on server-backed deployments
   * (RFC #1153 part 2 B): the extracted images are pool assets, so generation
   * is fed by id and no IndexedDB bytes are materialized. Browser-backed
   * images carry `storageId` instead — never both.
   */
  assetId?: string; // Allocated asset-pool id (server-backed transport)
  width?: number; // Image width (px or normalized)
  height?: number; // Image height (px or normalized)
  originalId?: string; // ID assigned by the extractor before bundle-level normalization
  sourceDocumentId?: string; // DocumentBundle source ID
  sourceDocumentName?: string; // Original source filename for citation back to material
  sourceDocumentOrder?: number; // Upload order in the bundle
  visionPriority?: number; // Higher values are attached first when vision budget is limited
}
```

请求 / 局部契约 `ImageMapping`（[magicclass-app/lib/types/generation.ts](../../magicclass-app/lib/types/generation.ts)）：

```ts
export type ImageMapping = Record<string, string>;
```

请求 / 局部契约 `UserRequirements`（[magicclass-app/lib/types/generation.ts](../../magicclass-app/lib/types/generation.ts)）：

```ts
export interface UserRequirements {
  requirement: string; // Single free-form text for all user input
  userNickname?: string; // Student nickname for personalization
  userBio?: string; // Student background for personalization
  webSearch?: boolean; // Enable web search for richer context
  interactiveMode?: boolean; // Enable Interactive Mode for interactive-first generation
  taskEngineMode?: boolean; // Enable vocational task-engine generation path
}
```

请求 / 局部契约 `VisionPromptImage`（[magicclass-app/lib/persistence/resolve-vision-images.ts](../../magicclass-app/lib/persistence/resolve-vision-images.ts)）：

```ts
export interface VisionPromptImage {
  id: string;
  src: string;
  width?: number;
  height?: number;
}
```

成功 / 直接响应构造：

```ts
apiSuccess({ content, effectiveOutline })
```

显式异常响应：

```ts
apiError('MISSING_REQUIRED_FIELD', 400, 'outline is required')

apiError(
        'MISSING_REQUIRED_FIELD',
        400,
        'allOutlines is required and must not be empty',
      )

apiError('MISSING_REQUIRED_FIELD', 400, 'stageId is required')

apiError(
        'GENERATION_FAILED',
        500,
        `Failed to generate content: ${effectiveOutline.title}`,
      )
```

共享实现返回 / 转发表达式：

```ts
result.text

llmApiError(error)
```

### `POST /api/generate/scene-outlines-stream`

实现：[magicclass-app/app/api/generate/scene-outlines-stream/route.ts](../../magicclass-app/app/api/generate/scene-outlines-stream/route.ts)。

鉴权 / 功能前置条件调用：

```ts
requirements?.requirement?.substring(0, 60)
requirements.requirement.substring(0, 50)
ensureUniqueOutlineId(normalized, usedOutlineIds)
```

请求头读取：

```ts
req.headers.get('x-model') / req.headers.get('x-api-key') / req.headers.get('x-base-url') / req.headers.get('x-provider-type') // resolveModelFromRequest 读取；body 与服务器配置优先级见 resolve-model.ts
req.headers.get('x-image-generation-enabled')
req.headers.get('x-video-generation-enabled')
```

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
body = await req.json()
```

handler 使用的业务字段：`body.requirements`。

请求 / 局部契约 `UserRequirements`（[magicclass-app/lib/types/generation.ts](../../magicclass-app/lib/types/generation.ts)）：

```ts
export interface UserRequirements {
  requirement: string; // Single free-form text for all user input
  userNickname?: string; // Student nickname for personalization
  userBio?: string; // Student background for personalization
  webSearch?: boolean; // Enable web search for richer context
  interactiveMode?: boolean; // Enable Interactive Mode for interactive-first generation
  taskEngineMode?: boolean; // Enable vocational task-engine generation path
}
```

请求 / 局部契约 `PdfImage`（[magicclass-app/lib/types/generation.ts](../../magicclass-app/lib/types/generation.ts)）：

```ts
export interface PdfImage {
  id: string; // e.g., "img_1", "img_2"
  src: string; // base64 data URL (empty when stored in IndexedDB)
  pageNumber: number; // Page number in PDF
  description?: string; // Optional description for AI context
  storageId?: string; // Reference to IndexedDB (session_xxx_img_1)
  /**
   * Pool asset id of the image bytes. Present on server-backed deployments
   * (RFC #1153 part 2 B): the extracted images are pool assets, so generation
   * is fed by id and no IndexedDB bytes are materialized. Browser-backed
   * images carry `storageId` instead — never both.
   */
  assetId?: string; // Allocated asset-pool id (server-backed transport)
  width?: number; // Image width (px or normalized)
  height?: number; // Image height (px or normalized)
  originalId?: string; // ID assigned by the extractor before bundle-level normalization
  sourceDocumentId?: string; // DocumentBundle source ID
  sourceDocumentName?: string; // Original source filename for citation back to material
  sourceDocumentOrder?: number; // Upload order in the bundle
  visionPriority?: number; // Higher values are attached first when vision budget is limited
}
```

请求 / 局部契约 `ImageMapping`（[magicclass-app/lib/types/generation.ts](../../magicclass-app/lib/types/generation.ts)）：

```ts
export type ImageMapping = Record<string, string>;
```

请求 / 局部契约 `SceneOutline`（[magicclass-app/lib/types/generation.ts](../../magicclass-app/lib/types/generation.ts)）：

```ts
export interface SceneOutline {
  id: string;
  type: 'slide' | 'quiz' | 'interactive' | 'pbl';
  title: string;
  description: string; // 1-2 sentences describing the purpose
  keyPoints: string[]; // 3-5 core key points
  teachingObjective?: string;
  estimatedDuration?: number; // seconds
  order: number;
  languageNote?: string; // LLM-inferred language note for this scene
  // Suggested image IDs (from PDF-extracted images)
  suggestedImageIds?: string[]; // e.g., ["img_1", "img_3"]
  // AI-generated media requests (when PDF images are insufficient)
  mediaGenerations?: MediaGenerationRequest[]; // e.g., [{ type: 'image', prompt: '...', elementId: 'gen_img_1' }]
  // Quiz-specific config
  quizConfig?: {
    questionCount: number;
    difficulty: 'easy' | 'medium' | 'hard';
    questionTypes: ('single' | 'multiple' | 'text')[];
  };
  /**
   * @deprecated Use widgetType + widgetOutline instead
   * Legacy interactive config - kept for backward compatibility only
   */
  interactiveConfig?: {
    conceptName: string;
    conceptOverview: string;
    designIdea: string;
    subject?: string;
  };
  // PBL-specific config
  pblConfig?: {
    projectTopic: string;
    projectDescription: string;
    targetSkills: string[];
    issueCount?: number;
    /** Opt into role-play scenario planning on top of the standard PBL v2 structure. */
    scenarioRoleplay?: boolean;
    /** Optional scenario brief used only when scenarioRoleplay is true. */
    scenarioBrief?: string;
  };
  // Widget fields (required for type === 'interactive' in unified mode)
  widgetType?: WidgetType;
  widgetOutline?: WidgetOutline;
}
```

成功 / 直接响应构造：

```ts
new Response(stream, {
      headers: {
        'Content-Type': 'text/event-stream',
        'Cache-Control': 'no-cache',
        Connection: 'keep-alive',
      },
    })
```

显式异常响应：

```ts
apiError('MISSING_REQUIRED_FIELD', 400, 'Requirements are required')

apiError('INTERNAL_ERROR', 500, 'Prompt template not found')

apiError('INTERNAL_ERROR', 500, error instanceof Error ? error.message : String(error))
```

### `POST /api/generate/tts`

实现：[magicclass-app/app/api/generate/tts/route.ts](../../magicclass-app/app/api/generate/tts/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
body = await req.json()
```

handler 使用的业务字段：`body.ttsProviderId`、`body.ttsVoice`、`body.ttsVoice.trim`、`body.audioId`。

请求 / 局部契约 `TTSProviderId`（[magicclass-app/lib/audio/types.ts](../../magicclass-app/lib/audio/types.ts)）：

```ts
export type TTSProviderId = BuiltInTTSProviderId | `custom-tts-${string}`;
```

成功 / 直接响应构造：

```ts
apiSuccess({
      audioId,
      base64,
      format,
    })
```

显式异常响应：

```ts
apiError(
        'MISSING_REQUIRED_FIELD',
        400,
        'Missing required fields: text, audioId, ttsProviderId, ttsVoice',
      )

apiError('INVALID_REQUEST', 400, 'browser-native-tts must be handled client-side')

apiError('PROVIDER_DISABLED', 403, 'This TTS provider is disabled by the server')

apiError(
        'VOXCPM_AUTO_VOICE_REQUIRES_CONTEXT',
        400,
        'VoxCPM Auto Voice requires agent context',
      )

apiError('INVALID_URL', 403, ssrfError)

apiError(
        'MISSING_API_KEY',
        400,
        `No API key configured for TTS provider: ${ttsProviderId}`,
      )

apiError('INVALID_URL', 403, blocked.message)

apiError('RATE_LIMITED', 429, error.message)

apiError(error.code, error.httpStatus, error.message)

apiError(error.code, error.httpStatus || 502, qwenVoiceCloneErrorMessage(error))

apiError(
      'GENERATION_FAILED',
      500,
      error instanceof Error ? error.message : String(error),
    )
```

### `POST /api/generate/video`

实现：[magicclass-app/app/api/generate/video/route.ts](../../magicclass-app/app/api/generate/video/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求头读取：

```ts
request.headers.get('x-video-provider')
request.headers.get('x-api-key')
request.headers.get('x-base-url')
request.headers.get('x-video-model')
```

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
body = (await request.json()) as VideoGenerationOptions
```

handler 使用的业务字段：`body.prompt`、`body.prompt.slice`。

请求 / 局部契约 `VideoGenerationOptions`（[magicclass-app/lib/media/types.ts](../../magicclass-app/lib/media/types.ts)）：

```ts
export interface VideoGenerationOptions {
  /** Text prompt describing the desired video */
  prompt: string;
  /** Desired video duration in seconds */
  duration?: number;
  /** Desired aspect ratio */
  aspectRatio?: '16:9' | '4:3' | '1:1' | '9:16' | '3:4' | '21:9';
  /** Desired output resolution */
  resolution?: '480p' | '720p' | '1080p';
  /** Owning stage, for server-side attribution of a generation call. */
  stageId?: string;
  /** Cancel server-side provider I/O (agent runtime / background callers). */
  signal?: AbortSignal;
}
```

请求 / 局部契约 `VideoProviderId`（[magicclass-app/lib/media/types.ts](../../magicclass-app/lib/media/types.ts)）：

```ts
export type VideoProviderId =
  | 'seedance'
  | 'kling'
  | 'veo'
  | 'minimax-video'
  | 'grok-video'
  | 'happyhorse';
```

成功 / 直接响应构造：

```ts
apiSuccess({ result })
```

显式异常响应：

```ts
apiError('MISSING_REQUIRED_FIELD', 400, 'Missing prompt')

apiError('MISSING_PROVIDER', 400, 'No video provider configured')

apiError('PROVIDER_DISABLED', 403, 'This video provider is disabled by the server')

apiError('INVALID_URL', 403, ssrfError)

apiError(
        'MISSING_API_KEY',
        401,
        `No API key configured for video provider: ${providerId}`,
      )

apiError(
        'MISSING_MODEL',
        400,
        `No model configured for video provider: ${providerId}`,
      )

apiError('CONTENT_SENSITIVE', 400, message)

apiError('INTERNAL_ERROR', 500, message)
```

### `POST /api/generate/voice`

实现：[magicclass-app/app/api/generate/voice/route.ts](../../magicclass-app/app/api/generate/voice/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
body = (await req.json()) as {
      providerId?: string;
      voiceId?: string;
      descriptor?: unknown;
      language?: string;
      referenceAudioBase64?: string;
      mimeType?: string;
      refText?: string;
      ttsApiKey?: string;
      ttsBaseUrl?: string;
      ttsModelId?: string;
      action?: 'register' | 'delete';
    }
```

handler 使用的业务字段：`body.providerId`、`body.voiceId`、`body.voiceId.trim`、`body.descriptor`、`body.action`、`body.referenceAudioBase64`、`body.ttsBaseUrl`、`body.ttsApiKey`、`body.ttsModelId`、`body.ttsApiKey?.trim`、`body.mimeType`、`body.refText`、`body.language`。

请求 / 局部契约 `VoiceRegistrationConfig`（[magicclass-app/lib/audio/voice-registration.ts](../../magicclass-app/lib/audio/voice-registration.ts)）：

```ts
export interface VoiceRegistrationConfig {
  baseUrl: string;
  apiKey?: string;
  model?: string;
  /**
   * `true` pins a client-supplied BYOK `baseUrl` to the strict public policy;
   * unset falls back to the process-wide `ALLOW_LOCAL_NETWORKS` behavior.
   */
  publicOnly?: boolean;
}
```

成功 / 直接响应构造：

```ts
apiSuccess({
          voiceId,
          deleted: false,
          vendorDeleted: false,
          localOnly: true,
          message:
            'The local voice profile can be removed, but the provider voice was not deleted.',
        })

apiSuccess({ voiceId, deleted: true, vendorDeleted: true, localOnly: false })

apiSuccess({ voiceId, registered: true })

apiSuccess({ voiceId: registeredVoiceId, registered: true })

apiSuccess({
      voiceId: registeredVoiceId,
      registered: true,
      referenceAudioBase64: clip.referenceAudioBase64,
      mimeType: clip.mimeType,
    })
```

显式异常响应：

```ts
apiError('MISSING_REQUIRED_FIELD', 400, 'providerId is required')

apiError('MISSING_REQUIRED_FIELD', 400, 'voiceId is required')

apiError(
        'MISSING_REQUIRED_FIELD',
        400,
        'descriptor or referenceAudioBase64 is required',
      )

apiError('PROVIDER_DISABLED', 403, 'This TTS provider is disabled by the server')

apiError(
        'INVALID_REQUEST',
        400,
        `Provider "${providerId}" does not support voice registration`,
      )

apiError('INVALID_URL', 403, ssrfError)

apiError('MISSING_REQUIRED_FIELD', 400, 'TTS base URL is required')

apiError('INVALID_REQUEST', 400, 'This provider does not support voice deletion')

apiError(
        'INVALID_REQUEST',
        400,
        'This provider requires reference audio and a verbatim transcript',
      )

apiError('INVALID_URL', 403, blocked.message)

apiError(error.code, error.httpStatus || 502, qwenVoiceCloneErrorMessage(error))

apiError(error.code, 400, error.message)

apiError('QWEN_VC_TIMEOUT', 504, 'The voice registration request timed out.')

apiError(
      'GENERATION_FAILED',
      500,
      error instanceof Error ? error.message : String(error),
    )
```

### `GET /api/health`

实现：[magicclass-app/app/api/health/route.ts](../../magicclass-app/app/api/health/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

成功 / 直接响应构造：

```ts
apiSuccess({
    status: 'ok',
    version,
    capabilities: {
      // A capability is available only when at least one provider is enabled —
      // force-disabled providers (disabled: true) do not count (#665).
      webSearch: Object.values(getServerWebSearchProviders()).some((info) => !info.disabled),
      imageGeneration: Object.values(getServerImageProviders()).some((info) => !info.disabled),
      videoGeneration: Object.values(getServerVideoProviders()).some((info) => !info.disabled),
      tts: Object.values(getServerTTSProviders()).some((info) => !info.disabled),
    },
  })
```

### `GET /api/materials/{id}`

实现：[magicclass-app/app/api/materials/[id]/route.ts](../../magicclass-app/app/api/materials/[id]/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

Query 读取：

```ts
new URL(req.url).searchParams.get('sessionId')
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

请求 / 局部契约 `Params`（[magicclass-app/app/api/materials/[id]/route.ts](../../magicclass-app/app/api/materials/[id]/route.ts)）：

```ts
type Params = { params: Promise<{ id: string }> };
```

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

ownerJson({ material: publicMaterialView(material) }, 200, responseHeaders)
```

显式异常响应：

```ts
apiError('MISSING_REQUIRED_FIELD', 400, 'sessionId is required')
```

共享实现返回 / 转发表达式：

```ts
withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    const session = await resolveOwnedSession(sessionId, ownerId);
    if (!session) return ownerNotFound(responseHeaders);
    const { id } = await params;
    const material = await getSessionMaterial(sessionId, id);
    if (!material) return ownerNotFound(responseHeaders);
    return ownerJson({ material: publicMaterialView(material) }, 200, responseHeaders);
  })

ownerNotFound(responseHeaders)

ownerJson({ material: publicMaterialView(material) }, 200, responseHeaders)
```

### `GET /api/materials`

实现：[magicclass-app/app/api/materials/route.ts](../../magicclass-app/app/api/materials/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

Query 读取：

```ts
url.searchParams.get('sessionId')
url.searchParams.get('limit')
url.searchParams.get('before')
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

ownerJson(
      { materials: materials.map((material) => publicMaterialView(material)) },
      200,
      responseHeaders,
    )
```

显式异常响应：

```ts
apiError('MISSING_REQUIRED_FIELD', 400, 'sessionId is required')

apiError(
      'INVALID_REQUEST',
      400,
      `limit must be an integer between 1 and ${MAX_MATERIAL_LIST_LIMIT}`,
    )
```

共享实现返回 / 转发表达式：

```ts
withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    const session = await resolveOwnedSession(sessionId, ownerId);
    if (!session) return ownerNotFound(responseHeaders);
    const materials = await listSessionMaterials(sessionId, {
      ...(parsedLimit.limit === undefined ? {} : { limit: parsedLimit.limit }),
      ...(before ? { before } : {}),
    });
    return ownerJson(
      { materials: materials.map((material) => publicMaterialView(material)) },
      200,
      responseHeaders,
    );
  })

ownerNotFound(responseHeaders)

ownerJson(
      { materials: materials.map((material) => publicMaterialView(material)) },
      200,
      responseHeaders,
    )
```

### `POST /api/materials`

实现：[magicclass-app/app/api/materials/route.ts](../../magicclass-app/app/api/materials/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

请求头读取：

```ts
req.headers.get('content-type')
req.headers.get('content-length')
req.headers.get('x-request-id')
req.headers.get('x-material-filename')
```

请求体：原始文件二进制流（不是 FormData）；Content-Type 为文件媒体类型，X-Material-Filename 为必需文件名（可 encodeURIComponent），Content-Length 可选。文档/图片上限 min(maxDocumentBytes,maxUploadBytes)，音视频上限 maxUploadBytes，声明长度和实际流字节均校验；超限 413、类型不支持 415、owner 配额不足 429。成功 201 返回 materialId/originalName/bytes/mime/extraction；响应回传 X-Request-ID。

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

NextResponse.json(
          {
            materialId: view.materialId,
            originalName: view.originalName,
            bytes: view.bytes,
            mime: view.mime,
            extraction: view.extraction,
          },
          { status: 201 },
        )
```

显式异常响应：

```ts
apiError(
            'INVALID_REQUEST',
            415,
            `unsupported material mime type: ${mime || '(missing)'}`,
          )

apiError('INVALID_REQUEST', 413, `upload exceeds ${uploadLimit} bytes`)

apiError('INVALID_REQUEST', 400, 'empty body')

apiError('MISSING_REQUIRED_FIELD', 400, 'x-material-filename header is required')

apiError('INVALID_REQUEST', 429, error.message)

apiError('INVALID_REQUEST', 413, 'upload body exceeds its declared content length')

apiError('INTERNAL_ERROR', 500, 'material upload failed')
```

共享实现返回 / 转发表达式：

```ts
response

withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    try {
      phase = 'validate_request';
      const rawMime = (req.headers.get('content-type') ?? '').split(';', 1)[0];
      declaredMime = rawMime;
      const originalName = materialFilename(req);
      // A generic content-type (empty, octet-stream, zip-family, or the
      // generic Office container some Linux browsers report for OOXML —
      // #1497) is resolved from the filename extension; a specific but
      // unsupported type falls through verbatim for the whitelist to reject.
      mime = resolveWorkbenchMaterialMime({ mimeType: rawMime, fileName: originalName });
      if (!isWorkbenchMaterialMime(mime)) {
        return reject(
          apiError(
            'INVALID_REQUEST',
            415,
            `unsupported material mime type: ${mime || '(missing)'}`,
          ),
          'unsupported_mime',
          responseHeaders,
        );
      }
      const uploadLimit = MEDIA_MIME_SET.has(mime)
        ? agentRuntimeConfig.maxUploadBytes
        : DOCUMENT_UPLOAD_LIMIT;

      declaredBytes = Number(req.headers.get('content-length') ?? 0);
      if (Number.isFinite(declaredBytes) && declaredBytes > uploadLimit) {
        return reject(
          apiError('INVALID_REQUEST', 413, `upload exceeds ${uploadLimit} bytes`),
          'declared_body_too_large',
          responseHeaders,
        );
      }
      if (!req.body) {
        return reject(
          apiError('INVALID_REQUEST', 400, 'empty body'),
          'empty_body',
          responseHeaders,
        );
      }

      if (!originalName) {
        return reject(
          apiError('MISSING_REQUIRED_FIELD', 400, 'x-material-filename header is required'),
          'missing_filename',
          responseHeaders,
        );
      }
      const createdMaterialId = createMaterialId();
      materialId = createdMaterialId;
      const ossKey = ownerMaterialObjectKey(ownerId, createdMaterialId);

      const provider = await getServerPersistenceProvider(process.env.DATABASE_URL ?? '');
      const byteStore = getMaterialByteStore();

      // Browsers send Content-Length for a File body. When an intermediary
      // strips it, reserve the per-file maximum so an unmeasured stream can
      // never bypass the owner byte quota; finalize shrinks the reservation to
      // its actual size.
      const reservedBytes =
        Number.isFinite(declaredBytes) && declaredBytes > 0 ? declaredBytes : uploadLimit;

      // Reclaim uploads that crashed before finalize and are older than the
      // 24-hour horizon. Each reservation's byte object is removed first; the reservation is
      // deleted only after that, so a failure here keeps the reservation for
      // the next pass instead of losing the pointer to its bytes.
      phase = 'reclaim_stale_uploads';
      await reclaimStaleOwnerMaterialUploads(
        provider.pool as unknown as ConnectableQueryable,
        ownerId,
        async (objectKey) => {
          try {
            await byteStore.delete(objectKey);
          } catch (error) {
            console.warn(
              'material stale byte deletion failed; keeping its reservation for the next pass',
              context({ objectKey }),
              error,
            );
            throw error;
          }
        },
      ).catch((error) => {
        console.warn(
          'material stale-upload reclaim failed; retrying on the next upload',
          context(),
          error,
        );
      });

      phase = 'reserve_material';
      try {
        await registerOwnerMaterial(
          provider.pool as unknown as ConnectableQueryable,
          {
            id: createdMaterialId,
            ownerId,
            kind: 'source',
            mime,
            bytes: reservedBytes,
            originalName,
            ossKey,
            extraction: { status: 'idle' },
          },
          {
            maxCount: agentRuntimeConfig.maxMaterialsPerOwner,
            maxTotalBytes: agentRuntimeConfig.maxMaterialBytesPerOwner,
          },
        );
      } catch (error) {
        if (error instanceof MaterialQuotaExceededError) {
          return reject(
            apiError('INVALID_REQUEST', 429, error.message),
            'quota_exceeded',
            responseHeaders,
          );
        }
        throw error;
      }

      phase = 'store_bytes';
      // Read the body through a sha256 meter, enforcing the per-class cap on
      // the streamed size (an unmeasured stream cannot bypass the cap).
      let bytes: Buffer;
      try {
        bytes = await readMeteredBody(req, uploadLimit);
        receivedBytes = bytes.byteLength;
      } catch (error) {
        if (error instanceof MaterialPayloadTooLarge) {
          await abandonOwnerMaterial(
            provider.pool as unknown as ConnectableQueryable,
            createdMaterialId,
          ).catch(() => undefined);
          return reject(
            apiError('INVALID_REQUEST', 413, `upload exceeds ${uploadLimit} bytes`),
            'streamed_body_too_large',
            responseHeaders,
          );
        }
        failureLogged = true;
        await abandonOwnerMaterial(
          provider.pool as unknown as ConnectableQueryable,
          createdMaterialId,
        ).catch(() => undefined);
        throw error;
      }
      if (bytes.byteLength === 0) {
        await abandonOwnerMaterial(
          provider.pool as unknown as ConnectableQueryable,
          createdMaterialId,
        ).catch(() => undefined);
        return reject(
          apiError('INVALID_REQUEST', 400, 'empty body'),
          'empty_stream',
          responseHeaders,
        );
      }
      if (bytes.byteLength > reservedBytes) {
        await abandonOwnerMaterial(
          provider.pool as unknown as ConnectableQueryable,
          createdMaterialId,
        ).catch(() => undefined);
        return reject(
          apiError('INVALID_REQUEST', 413, 'upload body exceeds its declared content length'),
          'declared_length_mismatch',
          responseHeaders,
        );
      }

      // The object key is recorded by the reservation before bytes are stored.
      // A crash after the write therefore leaves a durable pointer for the
      // 24-hour reclaim, preserving delete-before-reservation-removal order.
      const hash = createHash('sha256').update(bytes).digest('hex');
      let bytesStored = false;
      try {
        await byteStore.put(ossKey, bytes, mime);
        bytesStored = true;
        const row = await finalizeOwnerMaterial(
          provider.pool as unknown as ConnectableQueryable,
          createdMaterialId,
          bytes.byteLength,
          hash,
        );
        const view = publicMaterial(row);
        const res = NextResponse.json(
          {
            materialId: view.materialId,
            originalName: view.originalName,
            bytes: view.bytes,
            mime: view.mime,
            extraction: view.extraction,
          },
          { status: 201 },
        );
        res.headers.set('x-request-id', requestId);
        for (const [key, value] of responseHeaders) res.headers.append(key, value);
        console.info('material upload completed', context({ status: 201 }));
        return res;
      } catch (error) {
        let bytesDeleted = !bytesStored;
        if (bytesStored) {
          try {
            await byteStore.delete(ossKey);
            bytesDeleted = true;
          } catch (cleanupError) {
            console.warn(
              'material byte cleanup failed; keeping its reservation for stale reclaim',
              context({ objectKey: ossKey }),
              cleanupError,
            );
          }
        }
        if (bytesDeleted) {
          await abandonOwnerMaterial(
            provider.pool as unknown as ConnectableQueryable,
            createdMaterialId,
          ).catch(() => undefined);
        }
        throw error;
      }
    } catch (error) {
      if (!failureLogged) console.error('material upload failed', context({ status: 500 }), error);
      const res = apiError('INTERNAL_ERROR', 500, 'material upload failed');
      res.headers.set('x-request-id', requestId);
      for (const [key, value] of responseHeaders) res.headers.append(key, value);
      return res;
    }
  })

reject(
          apiError(
            'INVALID_REQUEST',
            415,
            `unsupported material mime type: ${mime || '(missing)'}`,
          ),
          'unsupported_mime',
          responseHeaders,
        )

reject(
          apiError('INVALID_REQUEST', 413, `upload exceeds ${uploadLimit} bytes`),
          'declared_body_too_large',
          responseHeaders,
        )

reject(
          apiError('INVALID_REQUEST', 400, 'empty body'),
          'empty_body',
          responseHeaders,
        )

reject(
          apiError('MISSING_REQUIRED_FIELD', 400, 'x-material-filename header is required'),
          'missing_filename',
          responseHeaders,
        )

reject(
            apiError('INVALID_REQUEST', 429, error.message),
            'quota_exceeded',
            responseHeaders,
          )

reject(
            apiError('INVALID_REQUEST', 413, `upload exceeds ${uploadLimit} bytes`),
            'streamed_body_too_large',
            responseHeaders,
          )

reject(
          apiError('INVALID_REQUEST', 400, 'empty body'),
          'empty_stream',
          responseHeaders,
        )

reject(
          apiError('INVALID_REQUEST', 413, 'upload body exceeds its declared content length'),
          'declared_length_mismatch',
          responseHeaders,
        )

res
```

### `POST /api/parse-pdf`

实现：[magicclass-app/app/api/parse-pdf/route.ts](../../magicclass-app/app/api/parse-pdf/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求头读取：

```ts
req.headers.get('content-type')
```

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
formData = await req.formData()
pdfFile = formData.get('pdf') as File | null
providerId = formData.get('providerId') as PDFProviderId | null
apiKey = formData.get('apiKey') as string | null
baseUrl = formData.get('baseUrl') as string | null
```

请求 / 局部契约 `PDFProviderId`（[magicclass-app/lib/pdf/types.ts](../../magicclass-app/lib/pdf/types.ts)）：

```ts
export type PDFProviderId = 'unpdf' | 'mineru' | 'mineru-cloud' | 'alidocmind';
```

请求 / 局部契约 `ParsedPdfContent`（[magicclass-app/lib/types/pdf.ts](../../magicclass-app/lib/types/pdf.ts)）：

```ts
export interface ParsedPdfContent {
  /** Extracted text content from the PDF */
  text: string;

  /** Array of images as base64 data URLs */
  images: string[];

  /** Extracted tables (MinerU feature) */
  tables?: Array<{
    page: number;
    data: string[][];
    caption?: string;
  }>;

  /** Extracted formulas (MinerU feature) */
  formulas?: Array<{
    page: number;
    latex: string;
    position?: { x: number; y: number; width: number; height: number };
  }>;

  /** Layout analysis (MinerU feature) */
  layout?: Array<{
    page: number;
    type: 'title' | 'text' | 'image' | 'table' | 'formula';
    content: string;
    position?: { x: number; y: number; width: number; height: number };
  }>;

  /** Metadata about the PDF */
  metadata?: {
    fileName?: string;
    fileSize?: number;
    pageCount: number;
    parser?: string; // 'unpdf' | 'mineru'
    processingTime?: number;
    taskId?: string; // MinerU task ID
    /** Image ID to base64 URL mapping (used in generation pipeline) */
    imageMapping?: Record<string, string>; // e.g., { "img_1": "data:image/png;base64,..." }
    /** PdfImage array with page numbers (used in generation pipeline) */
    pdfImages?: Array<{
      id: string;
      src: string;
      pageNumber: number;
      description?: string;
      width?: number;
      height?: number;
      /**
       * Pool asset id of the image bytes. Present only on cache-rebuilt
       * results in asset-id mode (RFC #1153 part 2 C): a server-backed cache
       * hit names the image's pool asset instead of materializing its bytes.
       */
      assetId?: string;
    }>;
    [key: string]: unknown;
  };
}
```

成功 / 直接响应构造：

```ts
apiSuccess({ data: resultWithMetadata })
```

显式异常响应：

```ts
apiError(
        'INVALID_REQUEST',
        400,
        `Invalid Content-Type: expected multipart/form-data, got "${contentType}"`,
      )

apiError('MISSING_REQUIRED_FIELD', 400, 'No PDF file provided')

apiError('INVALID_URL', 403, ssrfError)

apiError('PARSE_FAILED', 500, error instanceof Error ? error.message : 'Unknown error')
```

### `POST /api/pbl/v2/evaluate`

实现：[magicclass-app/app/api/pbl/v2/evaluate/route.ts](../../magicclass-app/app/api/pbl/v2/evaluate/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求头读取：

```ts
req.headers.get('x-model') / req.headers.get('x-api-key') / req.headers.get('x-base-url') / req.headers.get('x-provider-type') // resolveModelFromRequest 读取；body 与服务器配置优先级见 resolve-model.ts
```

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
req.json()
```

handler 使用的业务字段：`body.kind`、`body.milestoneId`、`body.microtaskId`、`body.project`、`body.recentChatSummary`。

请求 / 局部契约 `EvaluateRequest`（[magicclass-app/app/api/pbl/v2/evaluate/route.ts](../../magicclass-app/app/api/pbl/v2/evaluate/route.ts)）：

```ts
interface EvaluateRequest {
  project: PBLProjectV2;
  kind: EvalKind;
  milestoneId?: string;
  microtaskId?: string;
  recentChatSummary?: string;
}
```

请求 / 局部契约 `PBLProjectV2`（[magicclass-app/lib/pbl/v2/types.ts](../../magicclass-app/lib/pbl/v2/types.ts)）：

```ts
export type PBLProjectV2 = RuntimeOverlay<
  ContractPBLProject,
  {
    milestones: PBLMilestone[];
    submissions: PBLSubmission[];
    evaluations: PBLEvaluation[];
    threads: PBLAgentThread[];
    engagementEvents: PBLEngagementEvent[];
    proficiencyAssessment?: PBLProficiencyAssessment;
    runtimeEvents?: PBLRuntimeEvent[];
    runtimeResetEpoch?: number;
    pendingHandover?: PBLHandover;
    pendingTaskCompletion?: PBLPendingTaskCompletion;
    pendingOpenTaskPriorQuizResults?: PriorQuizResult[];
  }
>;
```

请求 / 局部契约 `EvalKind`（[magicclass-app/app/api/pbl/v2/evaluate/route.ts](../../magicclass-app/app/api/pbl/v2/evaluate/route.ts)）：

```ts
type EvalKind = 'task' | 'milestone' | 'final';
```

响应由共享服务 / SSE / 代理方法生成；参见该 handler 的链接与下方转发表达式。

显式异常响应：

```ts
apiError('INVALID_REQUEST', 400, 'Request body must be valid JSON.')

apiError('MISSING_REQUIRED_FIELD', 400, '`project` is required.')

apiError('INVALID_REQUEST', 400, "`kind` must be 'task' | 'milestone' | 'final'.")

apiError(
      'MISSING_REQUIRED_FIELD',
      400,
      "kind='task' requires both milestoneId and microtaskId.",
    )

apiError('MISSING_REQUIRED_FIELD', 400, "kind='milestone' requires milestoneId.")

apiError('INVALID_REQUEST', 400, err instanceof Error ? err.message : String(err))
```

共享实现返回 / 转发表达式：

```ts
createSSEResponse(
      runTaskEvaluation({
        project: body.project,
        milestoneId: body.milestoneId!,
        microtaskId: body.microtaskId!,
        languageModel: model,
        thinkingConfig,
        recentChatSummary: body.recentChatSummary,
        hasVision,
        signal: req.signal,
      }),
      { signal: req.signal },
    )

createSSEResponse(
      runMilestoneEvaluation({
        project: body.project,
        milestoneId: body.milestoneId!,
        languageModel: model,
        thinkingConfig,
        recentChatSummary: body.recentChatSummary,
        signal: req.signal,
      }),
      { signal: req.signal },
    )

createSSEResponse(
    runFinalEvaluation({
      project: body.project,
      languageModel: model,
      thinkingConfig,
      recentChatSummary: body.recentChatSummary,
      signal: req.signal,
    }),
    { signal: req.signal },
  )
```

### `POST /api/pbl/v2/instructor`

实现：[magicclass-app/app/api/pbl/v2/instructor/route.ts](../../magicclass-app/app/api/pbl/v2/instructor/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求头读取：

```ts
req.headers.get('x-model') / req.headers.get('x-api-key') / req.headers.get('x-base-url') / req.headers.get('x-provider-type') // resolveModelFromRequest 读取；body 与服务器配置优先级见 resolve-model.ts
```

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
req.json()
```

handler 使用的业务字段：`body.userMessage`、`body.userMessage.trim().length`、`body.userMessage.trim`、`body.phase`、`body.project`。

请求 / 局部契约 `InstructorRequest`（[magicclass-app/app/api/pbl/v2/instructor/route.ts](../../magicclass-app/app/api/pbl/v2/instructor/route.ts)）：

```ts
interface InstructorRequest {
  project: PBLProjectV2;
  userMessage: string;
  /** Optional override; defaults to 'instructing'. */
  phase?: InstructorPhase;
}
```

请求 / 局部契约 `PBLProjectV2`（[magicclass-app/lib/pbl/v2/types.ts](../../magicclass-app/lib/pbl/v2/types.ts)）：

```ts
export type PBLProjectV2 = RuntimeOverlay<
  ContractPBLProject,
  {
    milestones: PBLMilestone[];
    submissions: PBLSubmission[];
    evaluations: PBLEvaluation[];
    threads: PBLAgentThread[];
    engagementEvents: PBLEngagementEvent[];
    proficiencyAssessment?: PBLProficiencyAssessment;
    runtimeEvents?: PBLRuntimeEvent[];
    runtimeResetEpoch?: number;
    pendingHandover?: PBLHandover;
    pendingTaskCompletion?: PBLPendingTaskCompletion;
    pendingOpenTaskPriorQuizResults?: PriorQuizResult[];
  }
>;
```

请求 / 局部契约 `InstructorPhase`（[magicclass-app/lib/pbl/v2/agents/instructor.ts](../../magicclass-app/lib/pbl/v2/agents/instructor.ts)）：

```ts
export type InstructorPhase = 'greeting' | 'setup' | 'instructing';
```

响应由共享服务 / SSE / 代理方法生成；参见该 handler 的链接与下方转发表达式。

显式异常响应：

```ts
apiError('INVALID_REQUEST', 400, 'Request body must be valid JSON.')

apiError('MISSING_REQUIRED_FIELD', 400, '`project` is required.')

apiError('MISSING_REQUIRED_FIELD', 400, '`userMessage` is required.')

apiError('INVALID_REQUEST', 400, err instanceof Error ? err.message : String(err))
```

共享实现返回 / 转发表达式：

```ts
createSSEResponse(
    runInstructorTurn({
      project: body.project,
      userMessage: body.userMessage,
      phase,
      languageModel: model,
      thinkingConfig,
      signal: req.signal,
    }),
    { signal: req.signal },
  )
```

### `POST /api/pbl/v2/open-task`

实现：[magicclass-app/app/api/pbl/v2/open-task/route.ts](../../magicclass-app/app/api/pbl/v2/open-task/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求头读取：

```ts
req.headers.get('x-model') / req.headers.get('x-api-key') / req.headers.get('x-base-url') / req.headers.get('x-provider-type') // resolveModelFromRequest 读取；body 与服务器配置优先级见 resolve-model.ts
```

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
req.json()
```

handler 使用的业务字段：`body.phase`、`body.project`、`body.priorQuizResults`、`body.priorQuizResults.length`、`body.project.proficiency`。

请求 / 局部契约 `OpenTaskRequest`（[magicclass-app/app/api/pbl/v2/open-task/route.ts](../../magicclass-app/app/api/pbl/v2/open-task/route.ts)）：

```ts
interface OpenTaskRequest {
  project: PBLProjectV2;
  phase: 'greeting' | 'setup';
  /** Optional pre-play quiz snapshot piggybacked from the Hero when
   *  the learner first opens the project. Folded into
   *  `project.proficiencyAssessment` before the Instructor runs. */
  priorQuizResults?: PriorQuizResult[];
}
```

请求 / 局部契约 `PBLProjectV2`（[magicclass-app/lib/pbl/v2/types.ts](../../magicclass-app/lib/pbl/v2/types.ts)）：

```ts
export type PBLProjectV2 = RuntimeOverlay<
  ContractPBLProject,
  {
    milestones: PBLMilestone[];
    submissions: PBLSubmission[];
    evaluations: PBLEvaluation[];
    threads: PBLAgentThread[];
    engagementEvents: PBLEngagementEvent[];
    proficiencyAssessment?: PBLProficiencyAssessment;
    runtimeEvents?: PBLRuntimeEvent[];
    runtimeResetEpoch?: number;
    pendingHandover?: PBLHandover;
    pendingTaskCompletion?: PBLPendingTaskCompletion;
    pendingOpenTaskPriorQuizResults?: PriorQuizResult[];
  }
>;
```

请求 / 局部契约 `PriorQuizResult`（[magicclass-app/lib/pbl/v2/types.ts](../../magicclass-app/lib/pbl/v2/types.ts)）：

```ts
export interface PriorQuizResult {
  sceneId: string;
  sceneTitle: string;
  totalQuestions: number;
  correctCount: number;
  incorrectCount: number;
  /** Short-answer questions without `hasAnswer` cannot be auto-graded
   *  and are excluded from the accuracy ratio. */
  unscoredCount: number;
  /** `correctCount / (correctCount + incorrectCount)`, or null when
   *  no submitted result was auto-gradable. */
  accuracy: number | null;
}
```

响应由共享服务 / SSE / 代理方法生成；参见该 handler 的链接与下方转发表达式。

显式异常响应：

```ts
apiError('INVALID_REQUEST', 400, 'Request body must be valid JSON.')

apiError('MISSING_REQUIRED_FIELD', 400, '`project` is required.')

apiError('INVALID_REQUEST', 400, "`phase` must be 'greeting' or 'setup'.")

apiError('INVALID_REQUEST', 400, err instanceof Error ? err.message : String(err))
```

共享实现返回 / 转发表达式：

```ts
createSSEResponse(
    runInstructorTurn({
      project: body.project,
      userMessage: '',
      phase: body.phase,
      languageModel: model,
      thinkingConfig,
      signal: req.signal,
    }),
    { signal: req.signal },
  )
```

### `POST /api/pbl/v2/simulator`

实现：[magicclass-app/app/api/pbl/v2/simulator/route.ts](../../magicclass-app/app/api/pbl/v2/simulator/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求头读取：

```ts
req.headers.get('x-model') / req.headers.get('x-api-key') / req.headers.get('x-base-url') / req.headers.get('x-provider-type') // resolveModelFromRequest 读取；body 与服务器配置优先级见 resolve-model.ts
```

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
req.json()
```

handler 使用的业务字段：`body.phase`、`body.project`、`body.userMessage`。

请求 / 局部契约 `SimulatorRequest`（[magicclass-app/app/api/pbl/v2/simulator/route.ts](../../magicclass-app/app/api/pbl/v2/simulator/route.ts)）：

```ts
interface SimulatorRequest {
  project: PBLProjectV2;
  userMessage?: string;
  /** 'greeting' opens the scene (narration + character first line);
   *  'instructing' responds to the learner. Defaults to 'instructing'. */
  phase?: SimulatorPhase;
}
```

请求 / 局部契约 `SimulatorPhase`（[magicclass-app/lib/pbl/v2/agents/simulator.ts](../../magicclass-app/lib/pbl/v2/agents/simulator.ts)）：

```ts
export type SimulatorPhase = 'greeting' | 'instructing';
```

请求 / 局部契约 `PBLProjectV2`（[magicclass-app/lib/pbl/v2/types.ts](../../magicclass-app/lib/pbl/v2/types.ts)）：

```ts
export type PBLProjectV2 = RuntimeOverlay<
  ContractPBLProject,
  {
    milestones: PBLMilestone[];
    submissions: PBLSubmission[];
    evaluations: PBLEvaluation[];
    threads: PBLAgentThread[];
    engagementEvents: PBLEngagementEvent[];
    proficiencyAssessment?: PBLProficiencyAssessment;
    runtimeEvents?: PBLRuntimeEvent[];
    runtimeResetEpoch?: number;
    pendingHandover?: PBLHandover;
    pendingTaskCompletion?: PBLPendingTaskCompletion;
    pendingOpenTaskPriorQuizResults?: PriorQuizResult[];
  }
>;
```

响应由共享服务 / SSE / 代理方法生成；参见该 handler 的链接与下方转发表达式。

显式异常响应：

```ts
apiError('INVALID_REQUEST', 400, 'Request body must be valid JSON.')

apiError('MISSING_REQUIRED_FIELD', 400, '`project` is required.')

apiError('INVALID_REQUEST', 400, err instanceof Error ? err.message : String(err))
```

共享实现返回 / 转发表达式：

```ts
createSSEResponse(
    runSimulatorTurn({
      project: body.project,
      userMessage: body.userMessage ?? '',
      phase,
      languageModel: model,
      thinkingConfig,
      signal: req.signal,
    }),
    { signal: req.signal },
  )
```

### `POST /api/pbl/v2/task/update`

实现：[magicclass-app/app/api/pbl/v2/task/update/route.ts](../../magicclass-app/app/api/pbl/v2/task/update/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
req.json()
```

handler 使用的业务字段：`body.project`、`body.action`、`body.microtaskId`。

请求 / 局部契约 `UpdateRequest`（[magicclass-app/app/api/pbl/v2/task/update/route.ts](../../magicclass-app/app/api/pbl/v2/task/update/route.ts)）：

```ts
interface UpdateRequest {
  project: PBLProjectV2;
  action:
    | 'start'
    | 'continue_handover'
    | 'enter_scenario'
    | 'complete_act'
    | 'complete_pending_task';
  microtaskId?: string;
}
```

请求 / 局部契约 `PBLProjectV2`（[magicclass-app/lib/pbl/v2/types.ts](../../magicclass-app/lib/pbl/v2/types.ts)）：

```ts
export type PBLProjectV2 = RuntimeOverlay<
  ContractPBLProject,
  {
    milestones: PBLMilestone[];
    submissions: PBLSubmission[];
    evaluations: PBLEvaluation[];
    threads: PBLAgentThread[];
    engagementEvents: PBLEngagementEvent[];
    proficiencyAssessment?: PBLProficiencyAssessment;
    runtimeEvents?: PBLRuntimeEvent[];
    runtimeResetEpoch?: number;
    pendingHandover?: PBLHandover;
    pendingTaskCompletion?: PBLPendingTaskCompletion;
    pendingOpenTaskPriorQuizResults?: PriorQuizResult[];
  }
>;
```

成功 / 直接响应构造：

```ts
apiSuccess({ project })

apiSuccess({ project, activatedMicrotaskId: r.activatedMicrotaskId })

apiSuccess({
        project,
        completedMicrotaskId: current.microtask.id,
        milestoneId: current.milestone.id,
        milestoneCompleted: adv.milestoneCompleted,
        projectCompleted: adv.projectCompleted,
        nextMicrotaskId: adv.nextMicrotaskId,
      })

apiSuccess({
        project,
        activatedMicrotaskId: cont.ok ? cont.activatedMicrotaskId : undefined,
      })
```

显式异常响应：

```ts
apiError('INVALID_REQUEST', 400, 'Request body must be valid JSON.')

apiError('MISSING_REQUIRED_FIELD', 400, '`project` is required.')

apiError('MISSING_REQUIRED_FIELD', 400, '`microtaskId` is required for start.')

apiError('INVALID_REQUEST', 400, 'No pending handover to consume.')

apiError('INVALID_REQUEST', 400, 'No active microtask to complete.')

apiError('INVALID_REQUEST', 400, 'No pending task completion to confirm.')

apiError('INVALID_REQUEST', 400, `Could not complete task: ${adv.error}`)

apiError('INVALID_REQUEST', 400, 'Not a scenario project.')

apiError('INVALID_REQUEST', 400, 'No active scenario prep stage to advance.')

apiError('INVALID_REQUEST', 400, `Could not complete prep stage: ${adv.error}`)

apiError('INVALID_REQUEST', 400, `Could not finish act: ${r.error}`)

apiError('INVALID_REQUEST', 400, `Unknown action: ${String(body.action)}`)
```

### `GET /api/persistence/{...path}`

实现：[magicclass-app/app/api/persistence/[...path]/route.ts](../../magicclass-app/app/api/persistence/[...path]/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求体与响应：catch-all 下有具体的文档、资源和 RuntimeStore 子路由，见 [持久化子路由](#persistence-contract)；不能对任意路径发送任意 JSON。

handler 使用的业务字段：`body.push`、`body.length`。

请求 / 局部契约 `PersistenceRequestDeps`（[magicclass-app/app/api/persistence/[...path]/route.ts](../../magicclass-app/app/api/persistence/[...path]/route.ts)）：

```ts
interface PersistenceRequestDeps {
  poolFactory?: PersistencePoolFactory;
}
```

请求 / 局部契约 `DocumentAccess`（[magicclass-app/lib/persistence/document-access.ts](../../magicclass-app/lib/persistence/document-access.ts)）：

```ts
export type DocumentAccess = 'allow' | 'forbid' | 'not-found';
```

请求 / 局部契约 `ResponseCallback`（[magicclass-app/app/api/persistence/[...path]/route.ts](../../magicclass-app/app/api/persistence/[...path]/route.ts)）：

```ts
type ResponseCallback = () => void;
```

请求 / 局部契约 `PersistencePoolFactory`（[magicclass-app/lib/persistence/server-provider.ts](../../magicclass-app/lib/persistence/server-provider.ts)）：

```ts
export type PersistencePoolFactory = (connectionString: string) => Pool;
```

成功 / 直接响应构造：

```ts
Response.json({ error: { code, message } }, { status })

new Response(
            suppressesResponseBody(request, status) || body.length === 0
              ? undefined
              : Buffer.concat(body),
            {
              status,
              headers,
            },
          )
```

显式异常响应：

```ts
jsonError(404, 'PERSISTENCE_NOT_CONFIGURED', 'server persistence not configured')

jsonError(
      503,
      'PERSISTENCE_DEV_TOKEN_MISSING',
      'server persistence requires PERSISTENCE_DEV_TOKEN (development auth only)',
    )

jsonError(404, 'DOCUMENT_NOT_FOUND', '@magicclass/storage: document not found')

jsonError(
        500,
        'PERSISTENCE_INIT_FAILED',
        'server persistence initialization failed',
      )
```

### `POST /api/persistence/{...path}`

实现：[magicclass-app/app/api/persistence/[...path]/route.ts](../../magicclass-app/app/api/persistence/[...path]/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求体与响应：catch-all 下有具体的文档、资源和 RuntimeStore 子路由，见 [持久化子路由](#persistence-contract)；不能对任意路径发送任意 JSON。

handler 使用的业务字段：`body.push`、`body.length`。

请求 / 局部契约 `PersistenceRequestDeps`（[magicclass-app/app/api/persistence/[...path]/route.ts](../../magicclass-app/app/api/persistence/[...path]/route.ts)）：

```ts
interface PersistenceRequestDeps {
  poolFactory?: PersistencePoolFactory;
}
```

请求 / 局部契约 `DocumentAccess`（[magicclass-app/lib/persistence/document-access.ts](../../magicclass-app/lib/persistence/document-access.ts)）：

```ts
export type DocumentAccess = 'allow' | 'forbid' | 'not-found';
```

请求 / 局部契约 `ResponseCallback`（[magicclass-app/app/api/persistence/[...path]/route.ts](../../magicclass-app/app/api/persistence/[...path]/route.ts)）：

```ts
type ResponseCallback = () => void;
```

请求 / 局部契约 `PersistencePoolFactory`（[magicclass-app/lib/persistence/server-provider.ts](../../magicclass-app/lib/persistence/server-provider.ts)）：

```ts
export type PersistencePoolFactory = (connectionString: string) => Pool;
```

成功 / 直接响应构造：

```ts
Response.json({ error: { code, message } }, { status })

new Response(
            suppressesResponseBody(request, status) || body.length === 0
              ? undefined
              : Buffer.concat(body),
            {
              status,
              headers,
            },
          )
```

显式异常响应：

```ts
jsonError(404, 'PERSISTENCE_NOT_CONFIGURED', 'server persistence not configured')

jsonError(
      503,
      'PERSISTENCE_DEV_TOKEN_MISSING',
      'server persistence requires PERSISTENCE_DEV_TOKEN (development auth only)',
    )

jsonError(404, 'DOCUMENT_NOT_FOUND', '@magicclass/storage: document not found')

jsonError(
        500,
        'PERSISTENCE_INIT_FAILED',
        'server persistence initialization failed',
      )
```

### `PUT /api/persistence/{...path}`

实现：[magicclass-app/app/api/persistence/[...path]/route.ts](../../magicclass-app/app/api/persistence/[...path]/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求体与响应：catch-all 下有具体的文档、资源和 RuntimeStore 子路由，见 [持久化子路由](#persistence-contract)；不能对任意路径发送任意 JSON。

handler 使用的业务字段：`body.push`、`body.length`。

请求 / 局部契约 `PersistenceRequestDeps`（[magicclass-app/app/api/persistence/[...path]/route.ts](../../magicclass-app/app/api/persistence/[...path]/route.ts)）：

```ts
interface PersistenceRequestDeps {
  poolFactory?: PersistencePoolFactory;
}
```

请求 / 局部契约 `DocumentAccess`（[magicclass-app/lib/persistence/document-access.ts](../../magicclass-app/lib/persistence/document-access.ts)）：

```ts
export type DocumentAccess = 'allow' | 'forbid' | 'not-found';
```

请求 / 局部契约 `ResponseCallback`（[magicclass-app/app/api/persistence/[...path]/route.ts](../../magicclass-app/app/api/persistence/[...path]/route.ts)）：

```ts
type ResponseCallback = () => void;
```

请求 / 局部契约 `PersistencePoolFactory`（[magicclass-app/lib/persistence/server-provider.ts](../../magicclass-app/lib/persistence/server-provider.ts)）：

```ts
export type PersistencePoolFactory = (connectionString: string) => Pool;
```

成功 / 直接响应构造：

```ts
Response.json({ error: { code, message } }, { status })

new Response(
            suppressesResponseBody(request, status) || body.length === 0
              ? undefined
              : Buffer.concat(body),
            {
              status,
              headers,
            },
          )
```

显式异常响应：

```ts
jsonError(404, 'PERSISTENCE_NOT_CONFIGURED', 'server persistence not configured')

jsonError(
      503,
      'PERSISTENCE_DEV_TOKEN_MISSING',
      'server persistence requires PERSISTENCE_DEV_TOKEN (development auth only)',
    )

jsonError(404, 'DOCUMENT_NOT_FOUND', '@magicclass/storage: document not found')

jsonError(
        500,
        'PERSISTENCE_INIT_FAILED',
        'server persistence initialization failed',
      )
```

### `PATCH /api/persistence/{...path}`

实现：[magicclass-app/app/api/persistence/[...path]/route.ts](../../magicclass-app/app/api/persistence/[...path]/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求体与响应：catch-all 下有具体的文档、资源和 RuntimeStore 子路由，见 [持久化子路由](#persistence-contract)；不能对任意路径发送任意 JSON。

handler 使用的业务字段：`body.push`、`body.length`。

请求 / 局部契约 `PersistenceRequestDeps`（[magicclass-app/app/api/persistence/[...path]/route.ts](../../magicclass-app/app/api/persistence/[...path]/route.ts)）：

```ts
interface PersistenceRequestDeps {
  poolFactory?: PersistencePoolFactory;
}
```

请求 / 局部契约 `DocumentAccess`（[magicclass-app/lib/persistence/document-access.ts](../../magicclass-app/lib/persistence/document-access.ts)）：

```ts
export type DocumentAccess = 'allow' | 'forbid' | 'not-found';
```

请求 / 局部契约 `ResponseCallback`（[magicclass-app/app/api/persistence/[...path]/route.ts](../../magicclass-app/app/api/persistence/[...path]/route.ts)）：

```ts
type ResponseCallback = () => void;
```

请求 / 局部契约 `PersistencePoolFactory`（[magicclass-app/lib/persistence/server-provider.ts](../../magicclass-app/lib/persistence/server-provider.ts)）：

```ts
export type PersistencePoolFactory = (connectionString: string) => Pool;
```

成功 / 直接响应构造：

```ts
Response.json({ error: { code, message } }, { status })

new Response(
            suppressesResponseBody(request, status) || body.length === 0
              ? undefined
              : Buffer.concat(body),
            {
              status,
              headers,
            },
          )
```

显式异常响应：

```ts
jsonError(404, 'PERSISTENCE_NOT_CONFIGURED', 'server persistence not configured')

jsonError(
      503,
      'PERSISTENCE_DEV_TOKEN_MISSING',
      'server persistence requires PERSISTENCE_DEV_TOKEN (development auth only)',
    )

jsonError(404, 'DOCUMENT_NOT_FOUND', '@magicclass/storage: document not found')

jsonError(
        500,
        'PERSISTENCE_INIT_FAILED',
        'server persistence initialization failed',
      )
```

### `DELETE /api/persistence/{...path}`

实现：[magicclass-app/app/api/persistence/[...path]/route.ts](../../magicclass-app/app/api/persistence/[...path]/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求体与响应：catch-all 下有具体的文档、资源和 RuntimeStore 子路由，见 [持久化子路由](#persistence-contract)；不能对任意路径发送任意 JSON。

handler 使用的业务字段：`body.push`、`body.length`。

请求 / 局部契约 `PersistenceRequestDeps`（[magicclass-app/app/api/persistence/[...path]/route.ts](../../magicclass-app/app/api/persistence/[...path]/route.ts)）：

```ts
interface PersistenceRequestDeps {
  poolFactory?: PersistencePoolFactory;
}
```

请求 / 局部契约 `DocumentAccess`（[magicclass-app/lib/persistence/document-access.ts](../../magicclass-app/lib/persistence/document-access.ts)）：

```ts
export type DocumentAccess = 'allow' | 'forbid' | 'not-found';
```

请求 / 局部契约 `ResponseCallback`（[magicclass-app/app/api/persistence/[...path]/route.ts](../../magicclass-app/app/api/persistence/[...path]/route.ts)）：

```ts
type ResponseCallback = () => void;
```

请求 / 局部契约 `PersistencePoolFactory`（[magicclass-app/lib/persistence/server-provider.ts](../../magicclass-app/lib/persistence/server-provider.ts)）：

```ts
export type PersistencePoolFactory = (connectionString: string) => Pool;
```

成功 / 直接响应构造：

```ts
Response.json({ error: { code, message } }, { status })

new Response(
            suppressesResponseBody(request, status) || body.length === 0
              ? undefined
              : Buffer.concat(body),
            {
              status,
              headers,
            },
          )
```

显式异常响应：

```ts
jsonError(404, 'PERSISTENCE_NOT_CONFIGURED', 'server persistence not configured')

jsonError(
      503,
      'PERSISTENCE_DEV_TOKEN_MISSING',
      'server persistence requires PERSISTENCE_DEV_TOKEN (development auth only)',
    )

jsonError(404, 'DOCUMENT_NOT_FOUND', '@magicclass/storage: document not found')

jsonError(
        500,
        'PERSISTENCE_INIT_FAILED',
        'server persistence initialization failed',
      )
```

### `POST /api/provider/probe-models`

实现：[magicclass-app/app/api/provider/probe-models/route.ts](../../magicclass-app/app/api/provider/probe-models/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
body = await req.json()
```

成功 / 直接响应构造：

```ts
apiSuccess({
      models: chatModels.map((m) => ({ id: m.id, ownedBy: m.ownedBy })),
      total: models.length,
      filtered: models.length - chatModels.length,
    })
```

显式异常响应：

```ts
apiError('MISSING_REQUIRED_FIELD', 400, 'baseUrl is required')

apiError('INVALID_REQUEST', 400, ssrfError)

apiError('REDIRECT_NOT_ALLOWED', 403, 'Redirects are not allowed')

apiError('INVALID_REQUEST', 401, 'API key is invalid or expired')

apiError('INVALID_REQUEST', 404, 'This provider does not expose a model list')

apiError('INTERNAL_ERROR', 502, error.message)

apiError(
      'INTERNAL_ERROR',
      500,
      error instanceof Error ? error.message : 'Failed to probe models',
    )
```

### `POST /api/proxy-media`

实现：[magicclass-app/app/api/proxy-media/route.ts](../../magicclass-app/app/api/proxy-media/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
request.json()
```

成功 / 直接响应构造：

```ts
new NextResponse(blob, {
      headers: {
        'Content-Type': contentType,
        'Content-Length': String(blob.size),
        'Cache-Control': 'private, max-age=3600',
      },
    })
```

显式异常响应：

```ts
apiError('MISSING_REQUIRED_FIELD', 400, 'Missing or invalid url')

apiError('INVALID_URL', 403, ssrfError)

apiError('UPSTREAM_ERROR', 502, 'Redirect response without Location header')

apiError('TOO_MANY_REDIRECTS', 502, 'Too many redirects')

apiError('INVALID_URL', 502, 'Invalid redirect Location')

apiError('INVALID_URL', 403, hopError)

apiError('UPSTREAM_ERROR', status, `Upstream returned ${response!.status}`)

apiError('UPSTREAM_ERROR', 502, `Upstream asset too large (${contentLength} bytes)`)

apiError('UPSTREAM_ERROR', 502, `Upstream asset too large (${blob.size} bytes)`)

apiError('INVALID_URL', 403, blocked.message)

apiError('INTERNAL_ERROR', 500, error instanceof Error ? error.message : String(error))
```

### `POST /api/quiz-grade`

实现：[magicclass-app/app/api/quiz-grade/route.ts](../../magicclass-app/app/api/quiz-grade/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求头读取：

```ts
req.headers.get('x-model') / req.headers.get('x-api-key') / req.headers.get('x-base-url') / req.headers.get('x-provider-type') // resolveModelFromRequest 读取；body 与服务器配置优先级见 resolve-model.ts
```

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
body = (await req.json()) as GradeRequest
```

请求 / 局部契约 `GradeRequest`（[magicclass-app/app/api/quiz-grade/route.ts](../../magicclass-app/app/api/quiz-grade/route.ts)）：

```ts
interface GradeRequest {
  question: string;
  userAnswer: string;
  points: number;
  commentPrompt?: string;
  language?: string;
}
```

请求 / 局部契约 `GradeResponse`（[magicclass-app/app/api/quiz-grade/route.ts](../../magicclass-app/app/api/quiz-grade/route.ts)）：

```ts
interface GradeResponse {
  score: number;
  comment: string;
}
```

成功 / 直接响应构造：

```ts
apiSuccess({ ...gradeResult })
```

显式异常响应：

```ts
apiError('MISSING_REQUIRED_FIELD', 400, 'question and userAnswer are required')

apiError('INVALID_REQUEST', 400, 'points must be a positive number')

apiError('INTERNAL_ERROR', 500, 'Failed to grade answer')
```

### `GET /api/server-providers`

实现：[magicclass-app/app/api/server-providers/route.ts](../../magicclass-app/app/api/server-providers/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

成功 / 直接响应构造：

```ts
apiSuccess({
      providers: getServerProviders(),
      tts: getServerTTSProviders(),
      asr: getServerASRProviders(),
      pdf: getServerPDFProviders(),
      image: getServerImageProviders(),
      video: getServerVideoProviders(),
      webSearch: getServerWebSearchProviders(),
      generation: {
        parallelSceneConcurrency: getParallelSceneConcurrency(),
      },
    })
```

显式异常响应：

```ts
apiError(
      'INTERNAL_ERROR',
      500,
      error instanceof Error ? error.message : 'Unknown error',
    )
```

### `GET /api/skills/{id}`

实现：[magicclass-app/app/api/skills/[id]/route.ts](../../magicclass-app/app/api/skills/[id]/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

new Response('Invalid skill id', { status: 400 })

new Response('Not found', { status: 404, headers: responseHeaders })

new Response(new Uint8Array(zip), { headers })
```

共享实现返回 / 转发表达式：

```ts
zip ? zipResponse(id, zip) : new Response('Not found', { status: 404 })

zipResponse(id, builtin)

withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    const skill = await findUserSkill(id, ownerId);
    if (!skill) return new Response('Not found', { status: 404, headers: responseHeaders });
    return zipResponse(
      id,
      await buildUserSkillZip({
        name: skill.name,
        title: skill.title,
        description: skill.description,
        content: skill.content,
      }),
      responseHeaders,
    );
  })

zipResponse(
      id,
      await buildUserSkillZip({
        name: skill.name,
        title: skill.title,
        description: skill.description,
        content: skill.content,
      }),
      responseHeaders,
    )
```

### `GET /api/stage-meta/{stageId}`

实现：[magicclass-app/app/api/stage-meta/[stageId]/route.ts](../../magicclass-app/app/api/stage-meta/[stageId]/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isServerPersistenceConfigured()
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

请求 / 局部契约 `Params`（[magicclass-app/app/api/stage-meta/[stageId]/route.ts](../../magicclass-app/app/api/stage-meta/[stageId]/route.ts)）：

```ts
type Params = { params: Promise<{ stageId: string }> };
```

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

NextResponse.json({ error: 'not_found' }, { status: 404, headers: responseHeaders })

NextResponse.json(
        {
          isOwner,
          isPublic: access.isPublic,
          publishedAt: access.publishedAt,
          generationComplete: access.generationComplete,
          // Which layer answered. Diagnostic only — the client must not branch
          // on it.
          source: access.source,
        },
        { status: 200, headers: responseHeaders },
      )

NextResponse.json(
        { error: 'internal_error' },
        { status: 500, headers: responseHeaders },
      )
```

共享实现返回 / 转发表达式：

```ts
withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    const { stageId } = await params;
    try {
      const access = await resolveStageAccess(stageId);

      // Absent or tombstoned — indistinguishable, deliberately.
      if (!access) {
        return NextResponse.json({ error: 'not_found' }, { status: 404, headers: responseHeaders });
      }

      // Identity comparison, and nothing else: this boolean is the client's
      // ONLY owner signal, so a `true` here must mean every write through the
      // owner-bound store will be accepted (the store re-checks the owner
      // scope inside its write transactions).
      const isOwner = access.ownerId === ownerId;

      return NextResponse.json(
        {
          isOwner,
          isPublic: access.isPublic,
          publishedAt: access.publishedAt,
          generationComplete: access.generationComplete,
          // Which layer answered. Diagnostic only — the client must not branch
          // on it.
          source: access.source,
        },
        { status: 200, headers: responseHeaders },
      );
    } catch (error) {
      console.error('Failed to resolve stage meta', {
        stageId,
        error: error instanceof Error ? error.message : String(error),
      });
      return NextResponse.json(
        { error: 'internal_error' },
        { status: 500, headers: responseHeaders },
      );
    }
  })
```

### `GET /api/stages/{id}/freshness`

实现：[magicclass-app/app/api/stages/[id]/freshness/route.ts](../../magicclass-app/app/api/stages/[id]/freshness/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
resolveRequestOwnerId(req, responseHeaders)
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

请求 / 局部契约 `Params`（[magicclass-app/app/api/stages/[id]/freshness/route.ts](../../magicclass-app/app/api/stages/[id]/freshness/route.ts)）：

```ts
type Params = { params: Promise<{ id: string }> };
```

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      ...Object.fromEntries(responseHeaders),
    },
  })
```

共享实现返回 / 转发表达式：

```ts
ownerNotFound(responseHeaders)

false

true
```

### `POST /api/stages/{id}/generation-complete`

实现：[magicclass-app/app/api/stages/[id]/generation-complete/route.ts](../../magicclass-app/app/api/stages/[id]/generation-complete/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

请求 / 局部契约 `Params`（[magicclass-app/app/api/stages/[id]/generation-complete/route.ts](../../magicclass-app/app/api/stages/[id]/generation-complete/route.ts)）：

```ts
type Params = { params: Promise<{ id: string }> };
```

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

NextResponse.json({ error: 'not_found' }, { status: 404, headers: responseHeaders })

NextResponse.json({ error: 'forbidden' }, { status: 403, headers: responseHeaders })

NextResponse.json({ ok: true }, { status: 200, headers: responseHeaders })

NextResponse.json(
        { error: 'internal_error' },
        { status: 500, headers: responseHeaders },
      )
```

共享实现返回 / 转发表达式：

```ts
withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    const { id: stageId } = await params;
    try {
      const access = await resolveStageAccess(stageId);

      // Absent and tombstoned are the same 404 — the caller must not learn
      // that an id used to be a real course, and a deleted course has no
      // state left worth repairing.
      if (!access) {
        return NextResponse.json({ error: 'not_found' }, { status: 404, headers: responseHeaders });
      }

      // Owner only.
      if (access.ownerId !== ownerId) {
        return NextResponse.json({ error: 'forbidden' }, { status: 403, headers: responseHeaders });
      }

      const db = await getStageAccessDb();
      const touched = await markStageGenerationComplete(db, stageId);

      if (!touched) {
        return NextResponse.json({ error: 'not_found' }, { status: 404, headers: responseHeaders });
      }

      console.info('Stage generation marked complete', { stageId, ownerId });
      return NextResponse.json({ ok: true }, { status: 200, headers: responseHeaders });
    } catch (error) {
      console.error('Failed to mark stage generation complete', {
        stageId,
        error: error instanceof Error ? error.message : String(error),
      });
      return NextResponse.json(
        { error: 'internal_error' },
        { status: 500, headers: responseHeaders },
      );
    }
  })
```

### `GET /api/stages/{id}/manifest`

实现：[magicclass-app/app/api/stages/[id]/manifest/route.ts](../../magicclass-app/app/api/stages/[id]/manifest/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

请求 / 局部契约 `Params`（[magicclass-app/app/api/stages/[id]/manifest/route.ts](../../magicclass-app/app/api/stages/[id]/manifest/route.ts)）：

```ts
type Params = { params: Promise<{ id: string }> };
```

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

ownerJson(manifest, 200, responseHeaders)
```

共享实现返回 / 转发表达式：

```ts
withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    const { id } = await params;
    const store = await getOwnerScopedDocumentStore(ownerId);
    const manifest = await store.readFreshnessManifest(id);
    if (!manifest) return ownerNotFound(responseHeaders);
    return ownerJson(manifest, 200, responseHeaders);
  })

ownerNotFound(responseHeaders)

ownerJson(manifest, 200, responseHeaders)
```

### `POST /api/stages/{id}/publish`

实现：[magicclass-app/app/api/stages/[id]/publish/route.ts](../../magicclass-app/app/api/stages/[id]/publish/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

请求 / 局部契约 `Params`（[magicclass-app/app/api/stages/[id]/publish/route.ts](../../magicclass-app/app/api/stages/[id]/publish/route.ts)）：

```ts
type Params = { params: Promise<{ id: string }> };
```

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

NextResponse.json(
          { error: 'login_required' },
          { status: 401, headers: responseHeaders },
        )

NextResponse.json({ error: 'not_found' }, { status: 404, headers: responseHeaders })

NextResponse.json({ error: 'forbidden' }, { status: 403, headers: responseHeaders })

NextResponse.json(
          { success: true, publishedAt: access.publishedAt, name: access.name },
          { status: 200, headers: responseHeaders },
        )

NextResponse.json(
        { success: true, publishedAt, name: access.name },
        { status: 200, headers: responseHeaders },
      )

NextResponse.json(
        { error: 'internal_error' },
        { status: 500, headers: responseHeaders },
      )
```

共享实现返回 / 转发表达式：

```ts
withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    const { id: stageId } = await params;
    try {
      if (ownerId.startsWith('anon:')) {
        return NextResponse.json(
          { error: 'login_required' },
          { status: 401, headers: responseHeaders },
        );
      }

      const access = await resolveStageAccess(stageId);
      if (!access) {
        return NextResponse.json({ error: 'not_found' }, { status: 404, headers: responseHeaders });
      }
      if (access.ownerId !== ownerId) {
        return NextResponse.json({ error: 'forbidden' }, { status: 403, headers: responseHeaders });
      }

      if (access.isPublic) {
        return NextResponse.json(
          { success: true, publishedAt: access.publishedAt, name: access.name },
          { status: 200, headers: responseHeaders },
        );
      }

      const publishedAt = Date.now();
      const db = await getStageAccessDb();
      await setStagePublished(db, stageId, true, publishedAt);

      console.info('Stage published', { stageId, ownerId });
      return NextResponse.json(
        { success: true, publishedAt, name: access.name },
        { status: 200, headers: responseHeaders },
      );
    } catch (error) {
      console.error('Failed to publish stage', {
        stageId,
        error: error instanceof Error ? error.message : String(error),
      });
      return NextResponse.json(
        { error: 'internal_error' },
        { status: 500, headers: responseHeaders },
      );
    }
  })
```

### `GET /api/stages/{id}`

实现：[magicclass-app/app/api/stages/[id]/route.ts](../../magicclass-app/app/api/stages/[id]/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

请求 / 局部契约 `Params`（[magicclass-app/app/api/stages/[id]/route.ts](../../magicclass-app/app/api/stages/[id]/route.ts)）：

```ts
type Params = { params: Promise<{ id: string }> };
```

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

ownerJson(document, 200, responseHeaders)
```

共享实现返回 / 转发表达式：

```ts
withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    const { id } = await params;
    const store = await getOwnerScopedDocumentStore(ownerId);
    const document = await store.loadDocument(id);
    if (!document) return ownerNotFound(responseHeaders);
    return ownerJson(document, 200, responseHeaders);
  })

ownerNotFound(responseHeaders)

ownerJson(document, 200, responseHeaders)
```

### `PATCH /api/stages/{id}`

实现：[magicclass-app/app/api/stages/[id]/route.ts](../../magicclass-app/app/api/stages/[id]/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
req.json()
```

请求 / 局部契约 `Params`（[magicclass-app/app/api/stages/[id]/route.ts](../../magicclass-app/app/api/stages/[id]/route.ts)）：

```ts
type Params = { params: Promise<{ id: string }> };
```

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

ownerJson({ success: true, name }, 200, responseHeaders)
```

显式异常响应：

```ts
apiError('INVALID_REQUEST', 400, 'invalid JSON body')

apiError('INVALID_REQUEST', 400, 'name must be a non-empty string')

apiError(
      'INVALID_REQUEST',
      400,
      `name exceeds the ${STAGE_NAME_MAX_LENGTH} character limit`,
    )

ownerApiError(
      'INVALID_REQUEST',
      400,
      'document was written by a newer client; reload before saving',
      headers,
      error.message,
    )

ownerApiError('INVALID_REQUEST', 400, 'invalid stage document', headers, error.message)
```

共享实现返回 / 转发表达式：

```ts
withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    const { id } = await params;
    const store = await getOwnerScopedDocumentStore(ownerId);
    const document = await store.loadDocument(id);
    if (!document) return ownerNotFound(responseHeaders);
    try {
      await store.saveDocument({
        ...document,
        stage: { ...document.stage, name, updatedAt: Date.now() },
      });
    } catch (error) {
      return mapSaveError(error, responseHeaders);
    }
    return ownerJson({ success: true, name }, 200, responseHeaders);
  })

ownerNotFound(responseHeaders)

mapSaveError(error, responseHeaders)

ownerJson({ success: true, name }, 200, responseHeaders)
```

### `PUT /api/stages/{id}`

实现：[magicclass-app/app/api/stages/[id]/route.ts](../../magicclass-app/app/api/stages/[id]/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
req.json()
```

请求 / 局部契约 `Params`（[magicclass-app/app/api/stages/[id]/route.ts](../../magicclass-app/app/api/stages/[id]/route.ts)）：

```ts
type Params = { params: Promise<{ id: string }> };
```

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

ownerJson({ success: true }, 200, responseHeaders)
```

显式异常响应：

```ts
apiError('INVALID_REQUEST', 400, 'invalid JSON body')

apiError(
      'INVALID_REQUEST',
      400,
      'request body must be a stage document with `stage` and `scenes`',
    )

ownerApiError(
        'INVALID_REQUEST',
        400,
        'document stage id does not match the requested stage',
        responseHeaders,
      )

ownerApiError(
      'INVALID_REQUEST',
      400,
      'document was written by a newer client; reload before saving',
      headers,
      error.message,
    )

ownerApiError('INVALID_REQUEST', 400, 'invalid stage document', headers, error.message)
```

共享实现返回 / 转发表达式：

```ts
withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    const { id } = await params;
    if (candidate.stage!.id !== id) {
      return ownerApiError(
        'INVALID_REQUEST',
        400,
        'document stage id does not match the requested stage',
        responseHeaders,
      );
    }
    const store = await getOwnerScopedDocumentStore(ownerId);
    // Save is existence-gated (the reference's update path is too): PUT
    // updates a course that exists; it must not resurrect a deleted one or
    // mint a course under a client-chosen id. The owner scope is re-checked
    // inside the write transaction, so a foreign id still refuses there.
    const existing = await store.loadDocument(id);
    if (!existing) return ownerNotFound(responseHeaders);
    try {
      // The server is authoritative for "last modified": bumping updatedAt
      // keeps the manifest/freshness signal accurate for this route's writes.
      // The full payload is validated inside the store before anything is
      // persisted (invalid stage/scene shapes throw and map to 400 below).
      await store.saveDocument({
        ...(body as MaicDocument),
        stage: { ...(body as MaicDocument).stage, updatedAt: Date.now() },
      });
    } catch (error) {
      return mapSaveError(error, responseHeaders);
    }
    return ownerJson({ success: true }, 200, responseHeaders);
  })

ownerApiError(
        'INVALID_REQUEST',
        400,
        'document stage id does not match the requested stage',
        responseHeaders,
      )

ownerNotFound(responseHeaders)

mapSaveError(error, responseHeaders)

ownerJson({ success: true }, 200, responseHeaders)
```

### `DELETE /api/stages/{id}`

实现：[magicclass-app/app/api/stages/[id]/route.ts](../../magicclass-app/app/api/stages/[id]/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

请求 / 局部契约 `Params`（[magicclass-app/app/api/stages/[id]/route.ts](../../magicclass-app/app/api/stages/[id]/route.ts)）：

```ts
type Params = { params: Promise<{ id: string }> };
```

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

ownerJson({ ok: true }, 200, responseHeaders)
```

共享实现返回 / 转发表达式：

```ts
withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    const { id } = await params;
    const store = await getOwnerScopedDocumentStore(ownerId);
    await store.deleteDocument(id);
    return ownerJson({ ok: true }, 200, responseHeaders);
  })

ownerJson({ ok: true }, 200, responseHeaders)
```

### `GET /api/stages/{id}/scenes`

实现：[magicclass-app/app/api/stages/[id]/scenes/route.ts](../../magicclass-app/app/api/stages/[id]/scenes/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

Query 读取：

```ts
new URL(req.url).searchParams.get('ids')
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

请求 / 局部契约 `Params`（[magicclass-app/app/api/stages/[id]/scenes/route.ts](../../magicclass-app/app/api/stages/[id]/scenes/route.ts)）：

```ts
type Params = { params: Promise<{ id: string }> };
```

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

ownerJson({ scenes }, 200, responseHeaders)
```

显式异常响应：

```ts
apiError('INVALID_REQUEST', 400, 'empty_scene_ids')

apiError(
      'INVALID_REQUEST',
      400,
      'too_many_scene_ids',
      `limit ${MAX_BATCH_SCENE_IDS}, requested ${requested.length}`,
    )
```

共享实现返回 / 转发表达式：

```ts
withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    const { id } = await params;
    const store = await getOwnerScopedDocumentStore(ownerId);
    const document = await store.loadDocument(id);
    if (!document) return ownerNotFound(responseHeaders);
    const wanted = new Set(requested);
    const scenes = document.scenes.filter((scene) => wanted.has(scene.id));
    return ownerJson({ scenes }, 200, responseHeaders);
  })

ownerNotFound(responseHeaders)

ownerJson({ scenes }, 200, responseHeaders)
```

### `GET /api/stages/{id}/status`

实现：[magicclass-app/app/api/stages/[id]/status/route.ts](../../magicclass-app/app/api/stages/[id]/status/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

请求 / 局部契约 `Params`（[magicclass-app/app/api/stages/[id]/status/route.ts](../../magicclass-app/app/api/stages/[id]/status/route.ts)）：

```ts
type Params = { params: Promise<{ id: string }> };
```

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

NextResponse.json({ error: 'not_found' }, { status: 404 })

NextResponse.json({ isPublic: access.isPublic, publishedAt: access.publishedAt })

NextResponse.json({ error: 'internal_error' }, { status: 500 })
```

### `POST /api/stages/{id}/unpublish`

实现：[magicclass-app/app/api/stages/[id]/unpublish/route.ts](../../magicclass-app/app/api/stages/[id]/unpublish/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

请求 / 局部契约 `Params`（[magicclass-app/app/api/stages/[id]/unpublish/route.ts](../../magicclass-app/app/api/stages/[id]/unpublish/route.ts)）：

```ts
type Params = { params: Promise<{ id: string }> };
```

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

NextResponse.json(
          { error: 'login_required' },
          { status: 401, headers: responseHeaders },
        )

NextResponse.json({ error: 'not_found' }, { status: 404, headers: responseHeaders })

NextResponse.json({ error: 'forbidden' }, { status: 403, headers: responseHeaders })

NextResponse.json({ success: true }, { status: 200, headers: responseHeaders })

NextResponse.json(
        { error: 'internal_error' },
        { status: 500, headers: responseHeaders },
      )
```

共享实现返回 / 转发表达式：

```ts
withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    const { id: stageId } = await params;
    try {
      if (ownerId.startsWith('anon:')) {
        return NextResponse.json(
          { error: 'login_required' },
          { status: 401, headers: responseHeaders },
        );
      }

      const access = await resolveStageAccess(stageId);
      if (!access) {
        return NextResponse.json({ error: 'not_found' }, { status: 404, headers: responseHeaders });
      }
      if (access.ownerId !== ownerId) {
        return NextResponse.json({ error: 'forbidden' }, { status: 403, headers: responseHeaders });
      }

      const db = await getStageAccessDb();
      await setStagePublished(db, stageId, false, null);

      console.info('Stage unpublished', { stageId, ownerId });
      return NextResponse.json({ success: true }, { status: 200, headers: responseHeaders });
    } catch (error) {
      console.error('Failed to unpublish stage', {
        stageId,
        error: error instanceof Error ? error.message : String(error),
      });
      return NextResponse.json(
        { error: 'internal_error' },
        { status: 500, headers: responseHeaders },
      );
    }
  })
```

### `GET /api/stages`

实现：[magicclass-app/app/api/stages/route.ts](../../magicclass-app/app/api/stages/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

ownerJson({ stages }, 200, responseHeaders)
```

共享实现返回 / 转发表达式：

```ts
withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    const store = await getOwnerScopedDocumentStore(ownerId);
    const stages = await store.listDocuments();
    return ownerJson({ stages }, 200, responseHeaders);
  })

ownerJson({ stages }, 200, responseHeaders)
```

### `POST /api/stages`

实现：[magicclass-app/app/api/stages/route.ts](../../magicclass-app/app/api/stages/route.ts)。

鉴权 / 功能前置条件调用：

```ts
isAgentRuntimeConfigured()
```

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
req.json()
```

请求 / 局部契约 `AppDocumentOutline`（[magicclass-app/lib/document-store/persistence-types.ts](../../magicclass-app/lib/document-store/persistence-types.ts)）：

```ts
export interface AppDocumentOutline {
  outlines: SceneOutline[];
  /**
   * The requirement text the plan was generated from (agent runtime only).
   * Doubles as the replan idempotency key: a `generate_outline` replan
   * carrying the same requirement is a retry, not a new plan.
   */
  requirement?: string;
  generationComplete?: boolean;
  /** Absent = `'client'`, i.e. every course written before the agent runtime. */
  producer?: DocumentProducer;
  /** Opaque handle of the producing job, when one owns the course. */
  producerRef?: string;
  /**
   * Receipts of completed `import_pptx` calls, keyed by the same
   * `import_pptx:<key>` string that rides `requirement`. A material whose
   * receipt names pages still present in the stage is already imported — a
   * retry reports those pages instead of appending a second copy. The first
   * write onto a legacy document migrates the legacy `requirement` receipt
   * here so a later retry of that material stays a report.
   */
  pptxImports?: Record<string, { sceneIds: string[]; importedAt: number }>;
  createdAt: number;
  updatedAt: number;
}
```

成功 / 直接响应构造：

```ts
new Response('Not found', { status: 404 })

ownerJson(
      {
        stage: {
          id,
          name: trimmedName,
          ...(trimmedDescription ? { description: trimmedDescription } : {}),
          createdAt: now,
          updatedAt: now,
          sceneCount: 0,
        },
      },
      201,
      responseHeaders,
    )
```

显式异常响应：

```ts
apiError('INVALID_REQUEST', 400, 'invalid JSON body')

apiError('INVALID_REQUEST', 400, 'request body must be a JSON object')

apiError('MISSING_REQUIRED_FIELD', 400, 'name is required')

apiError(
      'INVALID_REQUEST',
      400,
      `name exceeds the ${STAGE_NAME_MAX_LENGTH} character limit`,
    )

apiError('INVALID_REQUEST', 400, 'description must be a string when present')
```

共享实现返回 / 转发表达式：

```ts
withRequestOwnerId(req, async (ownerId, responseHeaders) => {
    const id = createStageId();
    const now = Date.now();
    const outline: AppDocumentOutline = {
      outlines: [],
      requirement: trimmedName,
      generationComplete: false,
      createdAt: now,
      updatedAt: now,
    };
    const store = await getOwnerScopedDocumentStore(ownerId);
    await store.saveDocument({
      stage: {
        id,
        name: trimmedName,
        ...(trimmedDescription ? { description: trimmedDescription } : {}),
        createdAt: now,
        updatedAt: now,
      },
      scenes: [],
      outline,
    });
    return ownerJson(
      {
        stage: {
          id,
          name: trimmedName,
          ...(trimmedDescription ? { description: trimmedDescription } : {}),
          createdAt: now,
          updatedAt: now,
          sceneCount: 0,
        },
      },
      201,
      responseHeaders,
    );
  })

ownerJson(
      {
        stage: {
          id,
          name: trimmedName,
          ...(trimmedDescription ? { description: trimmedDescription } : {}),
          createdAt: now,
          updatedAt: now,
          sceneCount: 0,
        },
      },
      201,
      responseHeaders,
    )
```

### `POST /api/transcription`

实现：[magicclass-app/app/api/transcription/route.ts](../../magicclass-app/app/api/transcription/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
formData = await req.formData()
audioFile = formData.get('audio') as File
providerId = formData.get('providerId') as ASRProviderId | null
modelId = (formData.get('modelId') as string | null)?.trim() || undefined
language = formData.get('language') as string | null
apiKey = formData.get('apiKey') as string | null
baseUrl = formData.get('baseUrl') as string | null
```

请求 / 局部契约 `ASRProviderId`（[magicclass-app/lib/audio/types.ts](../../magicclass-app/lib/audio/types.ts)）：

```ts
export type ASRProviderId = BuiltInASRProviderId | `custom-asr-${string}`;
```

成功 / 直接响应构造：

```ts
apiSuccess({ text: result.text })
```

显式异常响应：

```ts
apiError('MISSING_REQUIRED_FIELD', 400, 'Audio file is required')

apiError('MISSING_PROVIDER', 400, 'No enabled ASR provider is configured')

apiError('PROVIDER_DISABLED', 403, 'This ASR provider is disabled by the server')

apiError('INVALID_URL', 403, ssrfError)

apiError('INVALID_URL', 403, blocked.message)

apiError(
      'TRANSCRIPTION_FAILED',
      500,
      'Transcription failed',
      error instanceof Error ? error.message : 'Unknown error',
    )
```

### `GET /api/usage`

实现：[magicclass-app/app/api/usage/route.ts](../../magicclass-app/app/api/usage/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

Query 读取：

```ts
req.nextUrl.searchParams.get('months')
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

请求 / 局部契约 `Bucket`（[magicclass-app/app/api/usage/route.ts](../../magicclass-app/app/api/usage/route.ts)）：

```ts
interface Bucket {
  key: string;
  kind: UsageKind;
  unit: UsageUnit;
  requests: number;
  // LLM token totals (0 for non-LLM).
  inputTokens: number;
  outputTokens: number;
  cacheReadTokens: number;
  cacheCreationTokens: number;
  totalTokens: number;
  // Non-token quantity (images / seconds / characters).
  quantity: number;
}
```

请求 / 局部契约 `UsageKind`（[magicclass-app/lib/server/usage-storage.ts](../../magicclass-app/lib/server/usage-storage.ts)）：

```ts
export type UsageKind = 'llm' | 'image' | 'video' | 'tts' | 'asr';
```

请求 / 局部契约 `UsageUnit`（[magicclass-app/lib/server/usage-storage.ts](../../magicclass-app/lib/server/usage-storage.ts)）：

```ts
export type UsageUnit = 'token' | 'image' | 'second' | 'character';
```

请求 / 局部契约 `UsageRecord`（[magicclass-app/lib/server/usage-storage.ts](../../magicclass-app/lib/server/usage-storage.ts)）：

```ts
export interface UsageRecord {
  id: string;
  createdAt: number;
  kind: UsageKind;
  source: string;
  providerId: string;
  modelId: string;
  modelString: string;
  // LLM token counts (0 for non-LLM rows).
  inputTokens: number;
  outputTokens: number;
  cacheReadTokens: number;
  cacheCreationTokens: number;
  reasoningTokens: number;
  // Non-token usage (e.g. image count, video seconds, TTS characters).
  quantity?: number;
  unit?: UsageUnit;
}
```

成功 / 直接响应构造：

```ts
apiSuccess({
      totals: { requests: totalRequests, llmTokens: totalLlmTokens },
      byModel: [...byModel.values()].sort((a, b) => b.requests - a.requests),
      byDay: [...byDay.values()].sort((a, b) => a.key.localeCompare(b.key)),
      byKind: [...byKind.values()],
    })
```

显式异常响应：

```ts
apiError(
      'INTERNAL_ERROR',
      500,
      error instanceof Error ? error.message : 'Failed to read usage',
    )
```

### `POST /api/verify-image-provider`

实现：[magicclass-app/app/api/verify-image-provider/route.ts](../../magicclass-app/app/api/verify-image-provider/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求头读取：

```ts
request.headers.get('x-image-provider')
request.headers.get('x-image-model')
request.headers.get('x-api-key')
request.headers.get('x-base-url')
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

请求 / 局部契约 `ImageProviderId`（[magicclass-app/lib/media/types.ts](../../magicclass-app/lib/media/types.ts)）：

```ts
export type ImageProviderId =
  | 'seedream'
  | 'openai-image'
  | 'qwen-image'
  | 'nano-banana'
  | 'minimax-image'
  | 'grok-image'
  | 'comfyui-image'
  | 'lemonade';
```

成功 / 直接响应构造：

```ts
apiSuccess({ message: result.message })
```

显式异常响应：

```ts
apiError('MISSING_PROVIDER', 400, 'No image provider configured')

apiError('PROVIDER_DISABLED', 403, 'This image provider is disabled by the server')

apiError('INVALID_URL', 403, ssrfError)

apiError('MISSING_API_KEY', 400, 'No API key configured')

apiError(
        'MISSING_MODEL',
        400,
        `No model configured for image provider: ${providerId}`,
      )

apiError('UPSTREAM_ERROR', 500, result.message)

apiError('INTERNAL_ERROR', 500, `Connectivity test error: ${err}`)
```

### `POST /api/verify-model`

实现：[magicclass-app/app/api/verify-model/route.ts](../../magicclass-app/app/api/verify-model/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
body = await req.json()
```

handler 使用的业务字段：`body.model`。

成功 / 直接响应构造：

```ts
apiSuccess({
      message: 'Connection successful',
      response: text,
    })
```

显式异常响应：

```ts
apiError('MISSING_REQUIRED_FIELD', 400, 'Model name is required')

apiError(
        'INVALID_REQUEST',
        401,
        error instanceof Error ? error.message : String(error),
      )

apiError('INTERNAL_ERROR', 500, errorMessage)
```

### `POST /api/verify-pdf-provider`

实现：[magicclass-app/app/api/verify-pdf-provider/route.ts](../../magicclass-app/app/api/verify-pdf-provider/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
body = await req.json()
```

handler 使用的业务字段：`body.providerId`。

成功 / 直接响应构造：

```ts
apiSuccess({ message: 'Connection successful' })

apiSuccess({
        message: 'Connection successful',
        status: response.status,
      })

apiSuccess({
      message: 'Connection successful',
      status: response.status,
    })
```

显式异常响应：

```ts
apiError('MISSING_REQUIRED_FIELD', 400, 'Provider ID is required')

apiError('INTERNAL_ERROR', 500, 'AliDocMind is not configured on the server')

apiError(
            'MISSING_REQUIRED_FIELD',
            400,
            'AccessKey ID and AccessKey Secret are required for AliDocMind',
          )

apiError('INVALID_URL', 403, ssrfError)

apiError('INVALID_CREDENTIALS', 400, `Authentication failed: ${result.error}`)

apiError('MISSING_REQUIRED_FIELD', 400, 'API Key is required for MinerU Cloud')

apiError('REDIRECT_NOT_ALLOWED', 403, 'Redirects are not allowed')

apiError(
          'INTERNAL_ERROR',
          500,
          `Authentication failed: ${text || response.statusText}`,
        )

apiError('MISSING_REQUIRED_FIELD', 400, 'Base URL is required')

apiError('INTERNAL_ERROR', 500, errorMessage)
```

### `POST /api/verify-video-provider`

实现：[magicclass-app/app/api/verify-video-provider/route.ts](../../magicclass-app/app/api/verify-video-provider/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求头读取：

```ts
request.headers.get('x-video-provider')
request.headers.get('x-video-model')
request.headers.get('x-api-key')
request.headers.get('x-base-url')
```

请求体：本 handler 及同文件调用的辅助函数未读取 JSON / FormData 请求体；请求头、查询和共享返回表达式见本节。

请求 / 局部契约 `VideoProviderId`（[magicclass-app/lib/media/types.ts](../../magicclass-app/lib/media/types.ts)）：

```ts
export type VideoProviderId =
  | 'seedance'
  | 'kling'
  | 'veo'
  | 'minimax-video'
  | 'grok-video'
  | 'happyhorse';
```

成功 / 直接响应构造：

```ts
apiSuccess({ message: result.message })
```

显式异常响应：

```ts
apiError('MISSING_PROVIDER', 400, 'No video provider configured')

apiError('PROVIDER_DISABLED', 403, 'This video provider is disabled by the server')

apiError('INVALID_URL', 403, ssrfError)

apiError('MISSING_API_KEY', 400, 'No API key configured')

apiError(
        'MISSING_MODEL',
        400,
        `No model configured for video provider: ${providerId}`,
      )

apiError('UPSTREAM_ERROR', 500, result.message)

apiError('INTERNAL_ERROR', 500, `Connectivity test error: ${err}`)
```

### `POST /api/web-search`

实现：[magicclass-app/app/api/web-search/route.ts](../../magicclass-app/app/api/web-search/route.ts)。

鉴权：受上述中间件及 handler 调用的 owner / provider / 业务校验约束；没有 CampusMate Bearer 依赖。

请求头读取：

```ts
req.headers.get('x-model') / req.headers.get('x-api-key') / req.headers.get('x-base-url') / req.headers.get('x-provider-type') // resolveModelFromRequest 读取；body 与服务器配置优先级见 resolve-model.ts
```

请求体解析（JSON / FormData / 二进制等以实际调用为准）：

```ts
body = await req.json()
```

请求 / 局部契约 `WebSearchProviderId`（[magicclass-app/lib/web-search/types.ts](../../magicclass-app/lib/web-search/types.ts)）：

```ts
export type WebSearchProviderId =
  | 'tavily'
  | 'exa'
  | 'bocha'
  | 'brave'
  | 'baidu'
  | 'claude'
  | 'minimax'
  | 'doubao'
  | 'searxng';
```

请求 / 局部契约 `BaiduSubSources`（[magicclass-app/lib/web-search/types.ts](../../magicclass-app/lib/web-search/types.ts)）：

```ts
export interface BaiduSubSources {
  webSearch: boolean;
  baike: boolean;
  scholar: boolean;
}
```

成功 / 直接响应构造：

```ts
apiSuccess({
      answer: result.answer,
      sources: result.sources,
      context,
      query: result.query,
      responseTime: result.responseTime,
    })
```

显式异常响应：

```ts
apiError('MISSING_REQUIRED_FIELD', 400, 'query is required')

apiError(
        'PROVIDER_DISABLED',
        403,
        'This web search provider is disabled by the server',
      )

apiError(
        'MISSING_API_KEY',
        400,
        `${provider.name} API key is not configured. Set it in Settings -> Web Search or configure ${getWebSearchEnvKey(providerId)} on the server.`,
      )

apiError('INVALID_REQUEST', 400, message)

apiError(
        'MISSING_REQUIRED_FIELD',
        400,
        getMissingBaseUrlMessage(providerId, provider.name),
      )

apiError('INTERNAL_ERROR', 500, message)
```

共享实现返回 / 转发表达式：

```ts
result.text
```


<a id="persistence-contract"></a>
## 持久化 catch-all 的具体子路由

上述 /api/persistence/{...path} 的五个显式 HTTP 导出委托给 createStorageHttpHandler；下表展开实际 documents/assets/runtime 子路由，计数仍归入 86 个导出 handler。无 KVStore 路由。路径在下表已加 /api/persistence 前缀。

前置条件：DATABASE_URL 缺失返回 404 PERSISTENCE_NOT_CONFIGURED，PERSISTENCE_DEV_TOKEN 缺失返回 503 PERSISTENCE_DEV_TOKEN_MISSING。工作台 owner cookie 与 ACCESS_CODE 中间件仍适用。

| 分支 | 当前应用授权限制（优先于包的通用契约） |
| --- | --- |
| documents | 读取已登记且未删除的 stage；创建或修改要求 owner。GET /documents 全局列表当前明确禁止（403），改用 /api/stages。不存在/删除的 stage 读取 404；其他 owner 的写入 403 |
| assets | 当前采用共享资源分区；可分配新资源、读取内容。PUT 替换和 DELETE 删除被应用层禁止（403），不应作为前端按钮调用 |
| runtime | Authorization: Bearer <持久化开发凭据> 与 X-Learner-Key；与 CampusMate JWT 不同。身份验证仍为开发验证器，production 默认拒绝，具体开关与含义见 server-auth.ts。merge 与管理员批量删除当前明确禁止（403） |

授权实现：[document-access.ts](../../magicclass-app/lib/persistence/document-access.ts)、[server-auth.ts](../../magicclass-app/lib/persistence/server-auth.ts)、[路由挂载](../../magicclass-app/app/api/persistence/[...path]/route.ts)。

### DocumentStore 子接口

| Method | Path | Purpose | Success |
| --- | --- | --- | --- |
| `PUT` | `/api/persistence/documents/{stageId}` | Save the full `MaicDocument`; body `stage.id` must match the path. The store migrates stale input, stamps `dslVersion`, replaces stage/outline data, upserts incoming scenes, and removes omitted scenes atomically. | `204` |
| `GET` | `/api/persistence/documents/{stageId}` | Load and migrate one complete document. | `200` with `MaicDocument`, or `404 DOCUMENT_NOT_FOUND` |
| `GET` | `/api/persistence/documents` | List version-independent summaries. | `200` with `DocumentSummary[]` |
| `DELETE` | `/api/persistence/documents/{stageId}` | Cascade-delete a document, its scenes, and its outline. Idempotent and intentionally not version-guarded. | `204` |
| `PUT` | `/api/persistence/documents/{stageId}/stage` | Validate and replace the stage row of an existing current-version document; body `id` must match the path. | `204` |
| `PUT` | `/api/persistence/documents/{stageId}/scenes/{sceneId}` | Validate and upsert a scene in an existing current-version document; body `id` and `stageId` must match the path. | `204` |
| `GET` | `/api/persistence/documents/{stageId}/scenes/{sceneId}` | Read one scene through the parent document's migrate-on-read semantics. | `200` with the scene, or `404` |
| `DELETE` | `/api/persistence/documents/{stageId}/scenes/{sceneId}` | Delete one scene. Idempotent for an absent scene or document, but version-guarded when the parent exists. | `204` |

完整字段、校验、错误与重试契约：[magicclass-app/packages/@magicclass/storage/docs/document-http-contract.md](../../magicclass-app/packages/@magicclass/storage/docs/document-http-contract.md)。下列应用限制覆盖表内的通用成功状态。

### AssetStore 子接口

| Method | Path | Purpose | Success |
| --- | --- | --- | --- |
| `POST` | `/api/persistence/assets` | Allocate a new id and store the submitted bytes under it. | `201` with `{ "id": "ast_…" }` and `X-Asset-Revision` |
| `GET` | `/api/persistence/assets/{id}/content` | Read the bytes stored under an id. | `200` with the bytes |
| `HEAD` | `/api/persistence/assets/{id}/content` | Read identity headers without reading the byte layer. | `200`, no body |
| `PUT` | `/api/persistence/assets/{id}/content` | Replace the bytes stored under an existing id. | `204` with `X-Asset-Revision` |
| `DELETE` | `/api/persistence/assets/{id}` | Remove the registry entry. | `204` for any id the policy admits |

完整字段、校验、错误与重试契约：[magicclass-app/packages/@magicclass/storage/docs/asset-http-contract.md](../../magicclass-app/packages/@magicclass/storage/docs/asset-http-contract.md)。下列应用限制覆盖表内的通用成功状态。

### RuntimeStore 子接口

| Method | Path | Purpose | Success |
| --- | --- | --- | --- |
| `POST` | `/api/persistence/runtime/sessions` | Create a session from a `RuntimeSessionInit`. The server stamps `runtimeDslVersion`; a client-submitted value is ignored. | `201` with the full `RuntimeSession` |
| `GET` | `/api/persistence/runtime/sessions/{sessionId}` | Get one session. | `200` with the `RuntimeSession`, or `404` if absent |
| `PATCH` | `/api/persistence/runtime/sessions/{sessionId}/status` | Set status from `{ "status", "updatedAt", "expectedLastSeq"? }`. `expectedLastSeq` is a non-negative integer or `null`. | `204` |
| `DELETE` | `/api/persistence/runtime/sessions/{sessionId}` | Delete a session and all of its records. | `204` |
| `GET` | `/api/persistence/runtime/stages/{stageId}/learners/{learnerKey}/sessions` | List a partition's sessions, ordered by the instant represented by `createdAt`, then by `id` for deterministic ties. | `200` with `RuntimeSession[]` |
| `POST` | `/api/persistence/runtime/sessions/{sessionId}/records` | Append a `RuntimeRecordInit` plus optional top-level `expectedLastSeq` and `sessionTransition`; body `sessionId` must match the path. | `201` with the full `RuntimeRecord` |
| `GET` | `/api/persistence/runtime/sessions/{sessionId}/records` | List records ordered by `seq`. Optional `?sceneId={sceneId}` returns only records anchored to that scene and excludes unanchored records. | `200` with `RuntimeRecord[]` |
| `POST` | `/api/persistence/runtime/learners/merge` | Atomically re-key all sessions across all stages from `{ "fromLearnerKey", "toLearnerKey" }`. | `200` with `{ "moved": number }` |
| `DELETE` | `/api/persistence/runtime/stages/{stageId}/learners/{learnerKey}` | Delete one learner's sessions and records on one stage. | `204` |
| `DELETE` | `/api/persistence/runtime/stages/{stageId}` | Cascade-delete every learner's sessions and records on one stage. | `204` |
| `DELETE` | `/api/persistence/runtime` | Delete every runtime session and record. Idempotent; an administrative operation — servers MUST gate it behind an operator-level authorization check, never expose it to learner credentials. | `204` |

完整字段、校验、错误与重试契约：[magicclass-app/packages/@magicclass/storage/docs/runtime-http-contract.md](../../magicclass-app/packages/@magicclass/storage/docs/runtime-http-contract.md)。下列应用限制覆盖表内的通用成功状态。

### 子路由请求与响应字段

- DocumentStore：全量 PUT 请求 {stage,scenes,outline?,dslVersion?}，增量 PUT 分别发送完整 Stage / Scene；id、stageId 必须与路径一致，scenes 数组未包含的旧场景会移除。GET 返回迁移后的文档；写入 204 无响应体。document 的时间通常为毫秒数。完整 Stage/Scene 结构与应用校验见 [DSL](../../magicclass-app/packages/@magicclass/dsl/src)、[文档验证器](../../magicclass-app/lib/document-store/validators.ts)。
- AssetStore：POST multipart 按顺序提供 meta（application/json 文件 part，含 filename）与 bytes（真实媒体 Content-Type 的文件 part）；两部分均带 filename。meta 不回传。成功 201 {id} 与 X-Asset-Revision；GET 为完整二进制、200、无 Range；读取 nosniff、Cache-Control:private,no-store。可选间接出口为 302 signed URL，客户端 follow 后仍依据实际 Content-Type。Next 未显式导出 HEAD，框架从 GET 自动处理；HEAD 内容由路由的 suppressesResponseBody 清空，不能计为新增显式 handler。
- RuntimeSessionInit：id/kind/stageId/learnerKey/status/createdAt/updatedAt 均必需；status=active/completed/archived，时间 ISO 8601 含时区。服务端赋 runtimeDslVersion，创建 201 返回完整 RuntimeSession。
- RuntimeRecordInit：id/sessionId/createdAt/payload 必需；sceneId/actionIndex/subAnchor 可选。seq 从 0 开始由服务端分配；append 可带 expectedLastSeq（非负整数或 null）与 sessionTransition:{status,updatedAt}，成功 201 返回完整 RuntimeRecord；尾部不匹配为 409 RUNTIME_APPEND_CONFLICT 且不修改数据。status PATCH 发送 {status,updatedAt,expectedLastSeq?}，成功 204。
- Runtime payload：chat 要求 ChatMessageSkeleton（role/content），quizAttempt 要求 QuizAttemptSkeleton（phase/answers），whiteboard 使用应用注入的验证器；完整类型见 [runtime.ts](../../magicclass-app/packages/@magicclass/dsl/src/runtime.ts)、[payload-validators.ts](../../magicclass-app/lib/runtime/payload-validators.ts)、[whiteboard 验证器](../../magicclass-app/lib/whiteboard/runtime/validate.ts)。

JSON 读写体默认最大 32 MiB，文档/Runtime 仅接受 JSON 可安全序列化的值。Asset multipart 独立限制见包契约。路径片段按 UTF-8 percent-encode；asset 路由不接受任何 query。失败使用 {error:{code,message,details?}}，与 apiError 的 {success:false,...} 不同；401/403/404/405/409/413 需按当前分支处理，204 不解析 JSON。

## 独立应用的 SSE 分帧与续传

- /api/agent/sessions/{id}/events：Last-Event-ID 请求头或 lastEventId query 是数值 seq，回放 seq 大于游标的事件；与 CampusMate Agent 的 evt 字符串游标不同。帧为 id/event/data；caught_up 表示回放追平，degraded=true 需完整回读。session_end 仅是一次运行结束，连接继续保持。断开不会停止 runner；资源归属由 anonymous_id cookie 控制，陌生或缺失 session 均 404。
- /api/agent/owner-events：当前 owner 的持久化汇总事件；按 caught_up/degraded/resync_required/owner_moved 等信号回读列表或切换 owner。完整帧与游标见 [owner-events handler](../../magicclass-app/app/api/agent/owner-events/route.ts)。
- /api/chat 与 /api/chat/pi：客户端传完整 messages/storeState/config，文本与工具事件按 StatelessEvent 解析，不能作为 CampusMate counselor 的 chunk/done 来读。每次请求为一次生成，取消使用 AbortSignal。
- /api/pbl/v2/instructor、evaluate、simulator：Content-Type=text/event-stream；event=<type>、data=<完整 PBLSSEEvent JSON>，token.delta 累加；project_patch 按 patch.kind 更新项目；done 结束，error 展示失败。共享 SSE helper 默认每 15 秒注释心跳，异常会发 error 后 done，不得把 done 单独当成功。

PBL v2 流事件字段直接列出共享定义：[sse.ts](../../magicclass-app/lib/pbl/v2/api/sse.ts)。嵌套项目/评估类型见 [types.ts](../../magicclass-app/lib/pbl/v2/types.ts)。

```ts
export interface SSETokenEvent {
  type: 'token';
  /** The text chunk to append to the current assistant message. */
  delta: string;
}
```

```ts
export interface SSEToolCallEvent {
  type: 'tool_call';
  toolName: string;
  args: Record<string, unknown>;
  toolCallId: string;
}
```

```ts
export interface SSEProjectPatchEvent {
  type: 'project_patch';
  /** The shape mirrors the tool effect:
   *   - 'advance' → microtask id + flags
   *   - 'closing_check' / 'observation' → engagement event added
   *   - 'evaluation' → new PBLEvaluation appended (for milestone/final later)
   *   - 'message' → assistant message that should be appended verbatim
   */
  patch:
    | {
        kind: 'message';
        message: PBLChatMessage;
      }
    | {
        kind: 'advance';
        microtaskId: string;
        milestoneCompleted: boolean;
        projectCompleted: boolean;
        nextMicrotaskId?: string;
        /** Authoritative server snapshots after advanceMicrotask()
         *  mutates process data. The client project is the source sent
         *  to /evaluate, so these fields must cross the SSE boundary
         *  or milestone/final evaluators lose completion evidence. */
        completedMicrotask?: PBLMicrotask;
        nextMicrotask?: PBLMicrotask;
        milestone?: PBLMilestone;
        engagementEvents?: PBLEngagementEvent[];
        runtimeEvents?: PBLRuntimeEvent[];
        /**
         * Should the client follow up with /api/pbl/v2/evaluate after
         * the Instructor stream closes? Three orthogonal flags so the
         * client can chain them deterministically:
         *
         *  - shouldEvaluateTask:      run task eval (only when the
         *                             microtask has at least one
         *                             submission — PR 6 D1-B)
         *  - shouldEvaluateMilestone: run milestone eval (when this
         *                             advance completed the milestone)
         *  - shouldEvaluateFinal:     run final eval (when this advance
         *                             completed the whole project)
         *
         * Chaining order is task → milestone → final; each eval's
         * `done` triggers the next one. The server doesn't know the
         * client's stream state, so we communicate "what to do next"
         * declaratively here, not by running the evaluator inline
         * with the Instructor (that would interleave two LLM streams,
         * see the design notes in agents/evaluator.ts).
         */
        shouldEvaluateTask?: boolean;
        shouldEvaluateMilestone?: boolean;
        shouldEvaluateFinal?: boolean;
      }
    | {
        kind: 'engagement_event';
        /** Authoritative server event. Older patches may only carry
         *  eventKind/payload; clients keep backward compatibility. */
        event?: PBLEngagementEvent;
        eventKind: string;
        microtaskId?: string;
        milestoneId?: string;
        ts?: string;
        payload?: Record<string, unknown>;
      }
    | {
        kind: 'evaluation';
        evaluation: PBLEvaluation;
      }
    | {
        kind: 'handover';
        handover: NonNullable<PBLProjectV2['pendingHandover']>;
      }
    /**
     * Adaptive proficiency engine state update. Replaces the project's
     * `proficiencyAssessment` wholesale on the client. By product
     * decision the chat does NOT show this — the patch is only
     * consumed by the dev badge (`PBL_V2_DEV_PROFICIENCY_BADGE=true`)
     * and the engagement-event ledger. `tierChanged` is included so
     * the dev tooling can highlight transitions without diffing the
     * full assessment.
     */
    | {
        kind: 'proficiency';
        assessment: PBLProficiencyAssessment;
        tierChanged: boolean;
      };
}
```

```ts
export interface SSESimPhaseEvent {
  type: 'sim_phase';
  phase: 'narration' | 'character';
}
```

```ts
export interface SSEResetDraftEvent {
  type: 'reset_draft';
}
```

```ts
export interface SSEErrorEvent {
  type: 'error';
  code: string;
  message: string;
}
```

```ts
export interface SSEDoneEvent {
  type: 'done';
}
```

```ts
export type PBLSSEEvent =
  | SSETokenEvent
  | SSEToolCallEvent
  | SSEProjectPatchEvent
  | SSESimPhaseEvent
  | SSEResetDraftEvent
  | SSEErrorEvent
  | SSEDoneEvent;
```
