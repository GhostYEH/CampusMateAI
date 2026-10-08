# 动态响应、文件、WebSocket 与开放对象契约

[总目录](README.md) · [接入流程](integration.md) · [字段字典](schemas.md)

本页补充默认 OpenAPI 未能表达的实际响应及开放对象。模块手册中的 Python 返回构造表达式用于核对字段，不是可直接执行的前端代码。下列字典来自源码，没有用数据库中的真实用户或生产数据生成示例。

## 错误信封与响应头

认证和匿名聊天限流返回 `429 {code:"RATE_LIMITED",message,details:{retry_after_seconds},request_id}`，并带 `Retry-After` 头；必须在 SSE 建立前按普通 HTTP 错误处理。测验保存冲突返回 `409 {code:"QUIZ_ATTEMPT_CONFLICT",message,details:null,request_id}`，不再返回裸 detail。社区普通用户访问他校资源返回 404 `NOT_FOUND`；管理接口已移除。意外 500 的 body.request_id 与响应头一致，允许的 Origin 可收到 CORS 响应头；内部异常文本不会回传。

非法 access token 在受保护 HTTP 接口返回 401 `UNAUTHORIZED`，实时语音 WebSocket 关闭码为 1008。可信设备自动登录的无效、撤销、过期和用户停用分支在既有 401 JSON 信封之外，附带删除原 Cookie 的 `Set-Cookie`（默认 `campus_trusted_device`、`Path=/api/v1/auth`、`Max-Age=0`）；错误码见 [认证模块](01-auth.md#post-apiv1authtrusted-deviceauto-login)。

## 普通对象与空响应

| 接口 | 实际成功响应 |
| --- | --- |
| GET /health | `{status:"ok",mode:"real_backend",env,version,knowledge_base_initialized,document_count,chunk_count,llm_provider,llm_available,fallback_enabled,retrieval_method:"bm25",study_checkins_supported:true}`；count 为整数，可用性为 boolean |
| POST /auth/logout | `{ok:true,message:"已退出登录"}` |
| POST /auth/qr/cancel | `{ok:true,status:"CANCELLED"}` |
| POST /auth/trusted-device/revoke | `{ok:true,message}`；未持有 cookie 也可能成功返回“无当前设备凭据” |
| POST /announcements/{id}/read | `{ok:true,first_time:boolean}` |
| DELETE /personal-hub/files/{id} | `{ok:true}` |
| DELETE /personal-hub/favorites/{id} | `{ok:true}` |
| DELETE /edu/binding | `{ok:true}` |

路径均省略 `/api/v1`。health 的 document_count/chunk_count 及 provider 状态用于诊断；知识库初始化不等于已经存在可回答资料，仍以 knowledge/status 的细分字段判断。

<a id="notices"></a>
## 通用 Page 的具体元素

通用 Page.items 在 OpenAPI 中是 any，但实际有固定业务对象：

| 接口 | items 元素 |
| --- | --- |
| GET /courses | [CourseOut](schemas.md#schema-courseout) |
| GET /classes | [ClassOut](schemas.md#schema-classout) |
| GET /classes/{class_id}/members | [ClassMemberOut](schemas.md#schema-classmemberout) |
| GET /classes/{class_id}/announcements | [AnnouncementOut](schemas.md#schema-announcementout) |
| GET /classes/{class_id}/assignments、GET /student/assignments | [AssignmentOut](schemas.md#schema-assignmentout) |
| GET /tasks | [PersonalTaskOut](schemas.md#schema-personaltaskout) |
| GET /notices | [NoticeOut](schemas.md#schema-noticeout) |

通知列表聚合两种资源：`kind=unified` 来自 notices 表，默认 unread=false，source/category 可为来源；`kind=announcement` 来自班级公告，学生的 unread 由已读记录决定。公告已读路径只对 announcement 的 ID 使用；不要把 unified notice ID 发送到公告已读接口。unread_only=true 会排除 unified 通知。列表按时间倒序；time 可能为空。

<a id="exams"></a>
## 个人考试响应

来源：[student_tools.py](../../backend/app/api/routes/student_tools.py)。GET 返回 `ExamRecord[]`；POST（201）和 PATCH 返回单个 ExamRecord；DELETE 返回 `{ok:true}`，没有检查是否真的删除了行。请求为 [ExamIn](schemas.md#schema-examin)，PATCH 使用同一个模型而非局部模型。

| 字段 | 响应类型 | 含义 |
| --- | --- | --- |
| id | string | 记录 ID，前缀 exam_ |
| user_id | string | 当前记录所属用户 |
| course_name | string | 课程名 |
| exam_date | string | 考试日期，建议 YYYY-MM-DD；请求只做字符串长度校验 |
| start_time / end_time | string / null | 起止时间，建议 HH:mm |
| location | string / null | 地点 |
| seat_number | string / null | 座位号 |
| exam_type | string / null | 考试类型 |
| reminder_enabled | **integer：0 / 1** | SQLite 行直接返回；请求端为 boolean，前端要转换 |
| notes | string / null | 备注 |
| created_at / updated_at | string | UTC ISO 8601 时间 |

```json
{
  "id": "exam_example",
  "user_id": "user_example",
  "course_name": "示例课程",
  "exam_date": "2026-10-08",
  "start_time": "09:00",
  "end_time": "11:00",
  "location": null,
  "seat_number": null,
  "exam_type": "期中",
  "reminder_enabled": 1,
  "notes": null,
  "created_at": "2026-09-30T01:00:00+00:00",
  "updated_at": "2026-09-30T01:00:00+00:00"
}
```

<a id="community"></a>
## 社区响应与分类 extra

来源：[community.py](../../backend/app/api/routes/community.py)、[community schema](../../backend/app/schemas/community.py)、[论坛表定义](../../backend/app/database/sqlite_db.py)。

帖子列表返回 `{items:PostRecord[],page,page_size,total}`；读取、创建、编辑、删除、点赞/取消点赞、收藏/取消收藏 都返回 PostRecord。删除是将 status 改为 deleted，返回更新后的帖子对象。详情会增加服务端 view_count；不把页面加载当成完全无副作用操作。

| PostRecord 字段 | 类型 | 含义 |
| --- | --- | --- |
| id / university_id | string | 帖子与学校 ID |
| author_id | string / null | 匿名时为 null |
| author_name | string | 匿名为“校园同学”，否则公开展示名或用户名 |
| title / content / category | string | 正文与分类，分类集合由 categories 接口提供 |
| images | string[] | 解析后的图片 URL；不返回 images_json |
| extra | object | 解析后的分类附加信息；不返回 extra_json |
| is_anonymous | boolean | 响应已转换为布尔值 |
| status | string | published / deleted / hidden |
| like_count / comment_count / favorite_count / view_count | integer | 当前计数 |
| liked / favorited | boolean | 当前查看者的点赞、收藏状态 |
| is_owner | boolean | 当前查看者是否作者 |
| created_at / updated_at | string | 时间 |

categories 返回 `{items:[{key,label,description,icon,color},...]}`；当前分类为 question/recruit/errand/campus/study/life/secondhand/activity/experience/other。

`PostCreate.extra`、`PostUpdate.extra` 虽然是 object，但 category=recruit 时按 [RecruitExtra](schemas.md#schema-recruitextra) 校验 headcount/deadline/location；category=errand 时按 [ErrandExtra](schemas.md#schema-errandextra) 校验 price/location/deadline。其他分类保留提供的对象。图片最多 9 个，title/content、评论的限制见字段字典；社区图片上传成功为 UploadImageResponse，静态地址通常从 `/static/community_images/` 解析。

评论列表 `{items:CommentRecord[],page:1,page_size:items.length,total:items.length}`，当前一次返回全部已发布评论，不提供真正服务端评论分页。创建返回 CommentRecord，父评论必须属于当前帖子。

| CommentRecord 字段 | 类型 |
| --- | --- |
| id / post_id / university_id | string |
| author_id | string / null，匿名为 null |
| author_name / content / status | string |
| parent_comment_id | string / null |
| is_anonymous | boolean |
| created_at / updated_at | string |

学校为空返回 UNIVERSITY_REQUIRED（409）；普通列表按当前学校隔离，作者才可编辑/删除。学生隐藏的他校资源可能表现为 404，不能据此判断原始资源存在性。

<a id="sync"></a>
## 学习通与课程局部同步

学习通 login 返回 `{status:"success"}`；disconnect 返回 `{status:"disconnected"}`；sync 返回 `{status:"success",stats,warnings,sections}`。HTTP 200 且 status=success 仍可能含分区失败。

stats 的整数计数：courses_fetched/courses_created/courses_updated/teachers_fetched、assignments_fetched/assignments_pending/assignments_created/assignments_updated、scores_fetched/scores_pending、exams_fetched/exams_created/exams_updated、notices_fetched/notices_created/notices_updated。warnings 为 string[]；sections 为按分区名索引的对象，每项有 status/item_count/last_synced_at/error_code/error_message。字段可能包含 null，按实际分区处理。

来源：[学习通路由](../../backend/app/api/routes/chaoxing.py)。第三方登录态错误常由 HTTPException 产生，经统一处理器输出 message；当前 Web 还保留了读取 detail 的旧分支，新前端应同时识别当前 message 与错误码，不要因外部 reauth_required 无条件退出本站。

课程局部 `POST /courses/{course_id}/sync` 返回：

```json
{
  "course_id": "course_example",
  "synced_at": "2026-09-30T01:00:00+00:00",
  "depth": "fast",
  "sections": {
    "chapters": {"status": "complete", "item_count": 3, "error": null}
  }
}
```

局部 sections 支持 chapters/materials/exams/discussions/assignments/notices/knowledge_graph；分区有 complete/partial/failed 等状态，error 是错误摘要。此处与全账号 sync 的 section 对象不同；展示 content-summary 中持久化同步状态时也应使用相应模型。来源：[course_content_sync.py](../../backend/app/services/chaoxing/course_content_sync.py)。

课程资源 open 返回 `{url:string,mode:"external"}`，URL 经过服务端校验；download 是文件 / 转发流，mime_type 与 Content-Disposition 由实际资源决定，外部授权过期会失败，不应要求前端抓取私有 Cookie。

非流式课程文件下载与内容同步交错时，缓存发布再次核对资源身份，最多尝试 3 次；持续变更导致耗尽时返回 HTTP 502 `{code:"HTTP_ERROR",message:"resource_metadata_error",details:null,request_id}`。客户端先检查状态和 Content-Type，错误 JSON 不作为文件保存；已有流式音视频和 Range 契约不变。

## 教务动态响应与兼容接口

`GET /edu/schedule/items`、`/grade/items`、`/exam/items` 返回 `{semester,items_count,items}`。semester 可空；items_count 为当前列表长度。完整条目字段直接列在外部连接模块的返回构造式中：

- schedule 包含课程、教师列表、校区/楼宇/教室、weekday、节次与时间、weeks/week_text、课程属性、课时、教学班、extra_info、is_stale/last_seen_at 等；weeks 为整数数组，teachers 为字符串数组，extra_info 为对象。
- grade 包含 id/semester/course_code/course_name/credit/score/grade_point/category/status/is_stale/last_seen_at；score、成绩字段不要强制全部转成数值，学校可能用文本等级。
- exam 包含 id/semester/course_code/course_name/exam_type/location/seat/starts_at/ends_at/notes/is_stale/last_seen_at。

这些来自已持久化数据，读取前先按需要 sync；空列表不说明已同步成功，结合绑定与同步记录判断。条目字段类型来源：[edu 数据模型](../../backend/app/models/edu.py)。

教务候选审核 API 已移除，普通用户提交 URL 不会获得全局教务配置的写入权限。

兼容 academic/providers 返回 `{items:[{university_id,provider,status,supports}],_deprecated}`；academic/status 返回 `{status,provider,last_synced_at,external_student_id,_deprecated}`；academic/binding 删除返回 `{ok:true,_deprecated}`。academic/bind 始终 ACADEMIC_UNSUPPORTED 409，不存在成功绑定响应。

## 模型 canary 门禁

`GET /learner-state/canary-gate/{capability_name}` 成功返回 `{allowed:boolean,reason:string|null,failed_gates?:string[]}`，是只读门禁查询。allowed=false 仍为 HTTP 200。reason 包括 canary_feature_flag_disabled、model_shadow_paused_for_user、candidate_model_not_configured、capability_is_not_read_only、no_promotion_decision、status_is_*、quality_gates_failed、circuit_breaker_open；allowed=true 时 reason=null。不是开启模型或改变数据的控制接口。

<a id="wallpaper"></a>
## 壁纸透传

每日壁纸 `format=json` 至少保证 image_url 为非空字符串，其余元数据透传上游，不保证每项都存在。当前测试覆盖的可选字段有 date/market/title/subtitle/headline/description/copyright/copyright_link/quiz_id/trivia/resolution/image_url_4k/image_url_1080/fetched_at/updated_at；trivia 为 `{question,options:[{bullet,text,url}]}`。format=image 为非空 image/* 二进制；format=redirect 可能是 3xx + Location。

history 返回 `{items:object[],pagination:object,...}`，常见 pagination 为 page/page_size/total；上游额外字段保留。date 不空时查询指定日期，上游不再接收 page/page_size。参数 date 与 random 同时指定每日接口会拒绝；resolution 仅 4k/1080，format 仅 image/json/redirect。运行时强制校验日期，不能只满足字符串格式。

失败 code 包括 UAPI_BAD_REQUEST/UAPI_NOT_FOUND/UAPI_RATE_LIMITED/UAPI_SERVER_ERROR/UAPI_UPSTREAM_ERROR/UAPI_TIMEOUT/UAPI_NETWORK_ERROR/UAPI_INVALID_RESPONSE，以及缺少配置的错误；上游 429 时可能有 Retry-After。两个端点另有**本地**防刷：共用同一 ASGI peer 额度（默认 30 次 / 60 秒），超限在上游调用前返回 429 `RATE_LIMITED` + `Retry-After`，不消耗上游额度；本地额度是单进程计数，不是跨实例全局配额。参见 [代理实现](../../backend/app/api/routes/bing_daily_wallpaper.py)、[契约测试](../../backend/tests/test_bing_daily_wallpaper.py)、[限流测试](../../backend/tests/test_wallpaper_rate_limit.py)。

## 文件、文本及异步视频返回

| 接口族 | 成功 Content-Type / 字段 |
| --- | --- |
| assignments/submissions attachments 下载 | FileResponse，mime_type 或 application/octet-stream，Content-Disposition 指定原始文件名 |
| courses resources/download | 文件或上游流，媒体类型/状态以响应为准 |
| assistant/tts | application/octet-stream，PCM16LE，X-Audio-* 头 |
| agent-artifacts/{id}/content | PlainTextResponse，按产物 mime_type 返回 Markdown / JSON / 纯文本 |
| stage export | application/zip；X-Archive-Sha256、X-Archive-Format-Version |
| stage export/{format} | 对应 Markdown/DOCX/PPTX 文件；X-Archive-Sha256；不支持的 format 拒绝 |
| courses/{course_id}/artifacts/{artifact_id} | 按产物类型的文件；X-Artifact-Sha256 |

受管 `POST .../stages/{stage_id}/export/video` 为 202，实际透传 `{job_id,job,format:"mp4",source:"render-service"}`。job 为 id/course_id/kind/mode/status/progress/attempts/error_code/artifact_id/scene_id/created_at/updated_at/started_at/finished_at，与受管 JobOut 字段一致；先查询 job，成功拿到 artifact_id 再下载。不是当场返回视频 Blob。

<a id="voice"></a>
## 实时语音 WebSocket

本接口未出现在 OpenAPI，但已由后端注册：`WS /api/v1/focus/realtime-voice/ws/{session_id}?access_token=<access token>`。完整收发协议来自后端 [focus_realtime_voice.py](../../backend/app/api/routes/focus_realtime_voice.py)，本次未查看其他客户端。

先 `POST /focus/realtime-voice/sessions`，201 返回 session_id 和相对 websocket_path，当前该字段不含 `/api/v1`；按基础路径拼接，并将 http/https Origin 转为 ws/wss。只能连接本用户创建的会话，无登录或不归属本用户在握手前关闭 code=1008。会话仅保存在单后端进程内，重启后丢失。

非 ASCII、非法 Base64URL 或缺失分段的 access_token 同样在握手前关闭 code=1008，不建立语音会话。

结束时先停止采集与播放，向已连接的 WebSocket 发送 `{"type":"stop"}` 或主动关闭连接；中继结束时会清理会话登记。`DELETE /focus/realtime-voice/sessions/{session_id}` 只删除内存会话登记、阻止后续握手，不会主动断开已经连接的 WebSocket，不能仅调用 DELETE 就认为音频传输已停止。DELETE 成功返回 200 `{session_id,stopped:true}`；会话已经清理、不存在或不属于本人时返回 404 `NOT_FOUND`，关闭后的清理请求可按已结束处理。

| 方向 / 帧 | 数据 |
| --- | --- |
| 客户端二进制 | PCM16LE，16000Hz，单声道，服务端转成上游音频 append |
| 客户端文本 | JSON `{type:"response.cancel"}` 或兼容 interrupt：中断当前回答，保持会话 |
| 客户端文本 | `{type:"commit"}`：提交输入音频；`{type:"stop"}`：关闭会话 |
| 服务端二进制 | PCM16LE，24000Hz，单声道音频 |
| 服务端文本 state | `{type:"state",state:"connecting" / "listening" / "speaking"}` |
| 服务端文本用户转写 | type=user_transcript_delta/user_transcript_done，text/event_id/item_id |
| 服务端文本 AI 回答 | type=ai_text_delta/ai_text_done，text/response_id/item_id/event_id |
| 服务端文本打断 | `{type:"user_speech_started",response_id}`，只在有进行中回答时转发 |
| 服务端文本关闭 / 错误 | `{type:"session_closed"}` 或 `{type:"error",message}` |
| 服务端文本扩展 | `{type:"provider_event",event}` |

上游提供方配置缺失时创建会话返回 503。这个协议与 assistant/tts 单向播放、受管课堂讲解任务不同；不要混用音频采样率和会话 ID。当前 Web 是否接入该能力见调用对照，后端已注册故仍完整记录。

<a id="dsl"></a>
## 受管课堂 document、commands 与 playback

这些字段在 FastAPI 中为开放 dict，实际结构由 [受管 DSL](../../magicclass-service/src/dsl/contract.ts)、[校验器](../../magicclass-service/src/dsl/validate.ts)、[命令实现](../../magicclass-service/src/dsl/commands.ts) 和 [播放器](../../magicclass-service/src/player/playback.ts) 决定。仅阅读受管服务的契约，不要求新前端直连其内部路由。

document 为 StageAggregate `{stage,scenes}`。stage 使用 camelCase id/name/createdAt/updatedAt，可选 description/languageDirective/style/whiteboard/videoManifest/agentIds/generatedAgentConfigs/interactiveMode/taskEngineMode；scene 核心为 id/stageId/title/order/type/content，可选 actions/whiteboards/multiAgent/createdAt/updatedAt。scene.type 与 content.type 必须一致。

| 场景 content.type | 业务字段 |
| --- | --- |
| slide | canvas 对象，可选 schemaVersion/slide；canvas.elements 为元素数组，元素按类型携带 id/type/left/top/尺寸和内容 |
| quiz | questions 数组，每题 id/type/question，可选 options/answer/analysis/points；type 为 single/multiple/short_answer，option 为 label/value，answer 为 string[] |
| interactive | html 或 url 至少有可用内容；widgetType 可为 simulation/diagram/code/game/visualization3d/procedural-skill；widgetConfig 为对应类型对象 |
| pbl | 项目学习对象，具体项目、任务、评价结构见 [pbl-project.ts](../../magicclass-service/src/dsl/pbl-project.ts) |

multiAgent 为 `{enabled:boolean,agentIds:string[],directorPrompt?:string}`。Action 必须有 id/type，可带 title/description 和对应动作业务参数。动作集合包括 spotlight/laser/play_video/speech、wb_open/draw_text/draw_shape/draw_chart/draw_latex/draw_table/draw_line/draw_code/edit_code/clear/delete/close（实际类型前缀为 `wb_`），discussion 及 widget_highlight/setState/annotation/reveal（实际前缀为 `widget_`）；spotlight/laser 仅作用于 slide，播放器会报告被丢弃的动作。

| command.type | 必填和可更新字段 |
| --- | --- |
| stage.update | 至少 name/description/style 中一项；name/style 最大 200，description 最大 4000 |
| scene.create | sceneType；可选 title/content/actions/afterSceneId；interactive 必须提供 content；新 scene id 由服务生成 |
| scene.delete | sceneId |
| scene.duplicate | sceneId，可选 title；副本插在原场景后 |
| scene.move | sceneId、toIndex 整数，按有效场景范围校验 |
| scene.update | sceneId，至少 title/content/actions/whiteboards/multiAgent 中一项；不能改变场景类型 |
| slide.element.add | sceneId、element 对象，可选 index；元素必须符合 Canvas 结构 |
| slide.element.delete | sceneId、elementId |
| slide.element.move | sceneId、elementId、left、top 有限数字 |
| slide.element.transform | sceneId、elementId，至少 left/top/width/height/rotate 中一项；width/height 正数 |
| slide.element.update | sceneId、elementId、content 字符串，当前只支持 text 元素，最大 20000 字符 |

```json
{"commands":[{"type":"scene.update","sceneId":"scene_example","title":"新的场景标题"}]}
```

同时发送 If-Match 当前 revision 和 Idempotency-Key；一次命令整体成功才替换文档。当前 DSL 限制：文档 2MiB、场景 200、每场景动作 200、白板 100、智能体 24、嵌套深度 24、单个清洗字符串 8192、inline HTML 512KiB、每场景题目 100、每题选项 26、每次命令 50。个别命令字段上限不代表最终文档能绕过 DSL 校验；最终以 [limits.ts](../../magicclass-service/src/dsl/limits.ts) 为准。

playback.render 为 `{kind,sandbox?,widget_type?,reason?}`；kind= sandbox-html / sandbox-url 时 sandbox 当前为 allow-scripts，不添加 allow-same-origin。steps 为 `{action_id,type,mode:"sync"|"fire_and_forget"}[]`；dropped_actions 为 `{action_id,type,reason}[]`；degraded 为 `{scene_id,reason}[]`。先读取 scene 正文，再按服务端播放计划决定本地渲染、沙箱及动作次序，不凭 html 字段自行判断可播放。

<a id="learning-rooms"></a>
## 共同课堂的动态响应

以下类型名用于说明实际返回对象，来自 [LearningRoomRepository](../../backend/app/repositories/learning_room_repository.py)，不是额外的 OpenAPI 模型。接口与完整流程见[共同课堂契约](14-magicclass.md#learning-rooms)。

| Identity 字段 | 类型 | 说明 |
| --- | --- | --- |
| uid | string | 账号唯一 ID，与 UserPublic.id 相同 |
| name | string | 显示名，未填写时使用用户名 |

| RoomSummary 字段 | 类型 | 说明 |
| --- | --- | --- |
| id / title / host_uid / created_at | string | 课堂 ID、标题、发起人 UID、UTC 时间 |

列表接口分别返回 `{items:RoomSummary[]}` 和 `{items:InvitationRecord[]}`，最多 100 项，不带 total/page/page_size，按创建或邀请更新时间降序排列。

| InvitationRecord 字段 | 类型 | 说明 |
| --- | --- | --- |
| room_id / title / host_uid / host_name / updated_at | string | 课堂、发起人及邀请更新时间；只返回活动课堂中的待接受邀请 |

| RoomRecord 字段 | 类型 | 说明 |
| --- | --- | --- |
| id / title / stage_id / host_uid / created_at | string | 课堂与课件标识、标题、发起人、UTC 时间 |
| scene_index | integer | 当前共享场景索引，从 0 开始 |
| scene_count | integer | 归档中的场景数量，1–1000 |
| active | integer | SQLite 标志；成功读取时为 1，不能假定是 JSON boolean |
| members | array | 每项为 `{uid:string,name:string,status:"pending"|"accepted"}`，包含发起人；没有约定成员排序 |

创建、读取和接受邀请返回 RoomRecord，均不携带归档二进制正文。邀请同学返回 `{uid:string,status:"pending"|"accepted"}`；重复邀请已处于该状态的成员会返回原状态。

| MessageRecord 字段 | 类型 | 说明 |
| --- | --- | --- |
| id | integer | 服务端递增消息 ID；供 after 游标使用 |
| uid / name / content / created_at | string | 发送者、显示名、去除首尾空白的正文、UTC 时间 |

消息读取返回 `{items:MessageRecord[]}`，最多 100 条，按 id 升序，且 id > after。发送返回 `{id:integer,content:string,created_at:string}`，不含 uid/name/client_id。重复发送同一成员、同一课堂、同一 client_id 时仍返回 201 和原消息，新的正文不会覆盖原记录。

拒绝邀请、更新页码和离开课堂返回 204，无响应体。下载归档返回 200 `application/zip` 和 `Cache-Control: no-store`，正文为创建时上传的原始 .maic.zip，不是 JSON 或 Base64，也未设置 Content-Disposition。

所有错误遵循[统一错误结构](integration.md#errors)。未接受邀请、无成员权限、课堂不存在等均使用 404 `LEARNING_ROOM_ERROR`，避免暴露其他课堂。已结束课堂的旧成员访问通常也返回 404，因为结束操作同时将成员改为 left；若仍存在 accepted 成员，则返回 410。完整分支见模块手册。

## 错误码字典

以下为当前加载的后端 AppException 子类的稳定默认错误码；具体接口可能覆盖 message 或 code，HTTPException、透传错误、流内错误另见模块说明。不是每个接口都会返回所有错误。

| HTTP | code | 默认 message |
| --- | --- | --- |
| 200 | `KNOWLEDGE_BASE_EMPTY` | 当前知识库中没有可用于回答该问题的资料。 |
| 200 | `LLM_UNAVAILABLE` | LLM 暂不可用，已切换到检索摘要模式。 |
| 400 | `EMPTY_QUESTION` | 问题为空，无法回答。 |
| 400 | `FILE_NAME_UNSAFE` | 文件名不合法，可能包含路径穿越字符。 |
| 400 | `LEARNER_DELETE_SCOPE_INVALID` | 无效的删除范围。 |
| 400 | `LEARNER_SOURCE_NOT_SUPPORTED` | 不支持的数据源。 |
| 400 | `MAGICCLASS_INVALID_REQUEST` | 请求参数不合法 |
| 400 | `NOTICE_EMPTY` | 通知文本为空，无法提取。 |
| 400 | `NOTICE_TOO_LONG` | 通知文本过长，请控制在 5000 字以内。 |
| 400 | `QR_INVALID` | 二维码无效。 |
| 401 | `INVALID_CREDENTIALS` | 用户名或密码错误。 |
| 401 | `QR_BROWSER_TOKEN_INVALID` | 浏览器凭据无效。 |
| 401 | `TRUSTED_DEVICE_EXPIRED` | 可信设备凭据已过期。 |
| 401 | `TRUSTED_DEVICE_INVALID` | 可信设备凭据无效。 |
| 401 | `TRUSTED_DEVICE_REVOKED` | 可信设备已被撤销。 |
| 401 | `UNAUTHORIZED` | 未认证或认证已失效。 |
| 403 | `AGENT_ACADEMIC_POLICY_RESTRICTED` | 学术策略限制该操作。 |
| 403 | `AGENT_PERMISSION_DENIED` | Agent 操作未被授权。 |
| 403 | `AGENT_SOURCE_POLICY_VIOLATION` | 来源策略不允许该操作。 |
| 403 | `AGENT_TOOL_REJECTED` | 工具调用被拒绝。 |
| 403 | `DEMO_SEED_REFUSED` | 当前环境不允许执行演示数据注入。 |
| 403 | `FORBIDDEN` | 无权访问该资源。 |
| 403 | `QR_USER_MISMATCH` | 确认用户与扫描用户不一致。 |
| 404 | `AGENT_RUN_NOT_FOUND` | Agent run 不存在。 |
| 404 | `ANNOUNCEMENT_NOT_FOUND` | 通知不存在。 |
| 404 | `ASSIGNMENT_NOT_FOUND` | 任务不存在。 |
| 404 | `CLASS_GROUP_NOT_FOUND` | 班级不存在。 |
| 404 | `COURSE_NOT_FOUND` | 课程不存在。 |
| 404 | `DOCUMENT_NOT_FOUND` | 文档不存在。 |
| 404 | `EDU_BINDING_NOT_FOUND` | 未绑定教务账号 |
| 404 | `HOME_BANNER_NOT_FOUND` | Home banner not found |
| 404 | `INVALID_INVITE_CODE` | 邀请码无效或班级不存在。 |
| 404 | `LEARNER_CORRECTION_NOT_FOUND` | 状态纠正记录不存在。 |
| 404 | `LEARNER_MODEL_DATA_NOT_FOUND` | 学生模型数据不存在。 |
| 404 | `MAGICCLASS_WORKSPACE_NOT_FOUND` | 未找到该学习工作台 |
| 404 | `NOT_FOUND` | 资源不存在。 |
| 404 | `PERSONAL_TASK_NOT_FOUND` | 个人待办不存在。 |
| 404 | `STUDENT_GOAL_NOT_FOUND` | 学生目标不存在。 |
| 404 | `STUDY_BREAK_NOT_FOUND` | 休息记录不存在。 |
| 404 | `STUDY_SESSION_NOT_FOUND` | 学习会话不存在。 |
| 404 | `SUBMISSION_NOT_FOUND` | 提交不存在。 |
| 404 | `UNIVERSITY_NOT_FOUND` | University not found |
| 404 | `USER_NOT_FOUND` | 用户不存在。 |
| 404 | `WORKFLOW_ACTION_NOT_FOUND` | 工作流动作不存在。 |
| 404 | `WORKFLOW_NOT_FOUND` | 通知工作流不存在。 |
| 409 | `ACADEMIC_UNSUPPORTED` | 当前学校暂未支持自动教务同步 |
| 409 | `ACTION_STATE_CONFLICT` | 动作当前状态不允许该操作。 |
| 409 | `AGENT_APPROVAL_REQUIRED` | 需要用户确认后继续。 |
| 409 | `AGENT_CAPABILITY_DISABLED` | 该 Agent 能力当前不可用。 |
| 409 | `AGENT_CONTEXT_EXPIRED` | 上下文快照已过期。 |
| 409 | `AGENT_CURSOR_INVALID` | 事件游标无效。 |
| 409 | `AGENT_IDEMPOTENCY_CONFLICT` | 幂等键已用于不同的请求。 |
| 409 | `AGENT_INVALID_STATE` | Agent 运行时状态无效。 |
| 409 | `AGENT_RUN_CANCELLED` | Agent run 已取消。 |
| 409 | `ALREADY_ENROLLED` | 该学生已加入此班级。 |
| 409 | `ASSIGNMENT_CLOSED` | 任务已截止提交。 |
| 409 | `CLASS_GROUP_FULL` | 班级已满员。 |
| 409 | `DOCUMENT_ALREADY_EXISTS` | 相同内容哈希的文档已存在。 |
| 409 | `INVALID_TRANSITION` | 状态转换不被允许。 |
| 409 | `LEARNER_CORRECTION_ALREADY_REVOKED` | 状态纠正已被撤销。 |
| 409 | `LEARNER_CORRECTION_CONFLICT` | 状态纠正幂等键已用于不同的纠正请求。 |
| 409 | `LEARNER_CORRECTION_SNAPSHOT_MISMATCH` | 纠正请求字段与目标快照不一致。 |
| 409 | `LEARNER_DELETE_IDEMPOTENCY_CONFLICT` | 删除幂等键已用于不同的删除范围。 |
| 409 | `LEARNER_DELETE_IN_PROGRESS` | 删除操作正在进行中。 |
| 409 | `LEARNER_EVENT_CONFLICT` | 事件幂等键冲突 |
| 409 | `LEARNER_MODEL_RECOMPUTE_REQUIRED` | 需要重新计算学生模型状态。 |
| 409 | `LEARNER_SOURCE_CONTROL_CONFLICT` | 数据源控制操作冲突。 |
| 409 | `LEARNER_STATE_STALE` | 学生状态已过期。 |
| 409 | `LEARNING_PLAN_EXECUTION_FAILED` | 学习计划执行失败，未完成任何部分写入。 |
| 409 | `LEARNING_PLAN_EXPIRED` | 学习计划已过期，请重新生成。 |
| 409 | `LEARNING_PLAN_IDEMPOTENCY_CONFLICT` | 幂等键已用于不同的学习计划输入。 |
| 409 | `LEARNING_PLAN_STALE` | 学习计划所依据的数据已变化，请重新生成。 |
| 409 | `LEARNING_PLAN_UNDO_CONFLICT` | 学习计划创建的任务已被修改，无法安全撤销。 |
| 409 | `MAGICCLASS_IDEMPOTENCY_CONFLICT` | 同一个幂等键被用于了不同的请求 |
| 409 | `MAGICCLASS_REVISION_CONFLICT` | 内容已被其他操作更新，请重新读取后再提交 |
| 409 | `MODEL_SHADOW_DISABLED` | 模型影子评测已停用。 |
| 409 | `PERSONAL_TASK_CONFLICT` | 个人待办当前状态不允许该操作。 |
| 409 | `QR_ALREADY_CONFIRMED` | 二维码已确认。 |
| 409 | `QR_ALREADY_CONSUMED` | 二维码已使用，不能重复兑换。 |
| 409 | `QR_ALREADY_SCANNED` | 二维码已被扫描。 |
| 409 | `QR_CANCELLED` | 二维码已取消。 |
| 409 | `QR_NOT_CONFIRMED` | 二维码尚未确认，不能兑换。 |
| 409 | `RESUBMIT_NOT_ALLOWED` | 该任务不允许重新提交。 |
| 409 | `STUDENT_GOAL_CONFLICT` | 学生目标当前状态不允许该操作。 |
| 409 | `STUDENT_NUMBER_EXISTS` | 学号已被占用。 |
| 409 | `TEACHER_NUMBER_EXISTS` | 工号已被占用。 |
| 409 | `UNIVERSITY_REQUIRED` | 请先选择你的大学 |
| 409 | `USERNAME_EXISTS` | 用户名已被占用。 |
| 409 | `WORKFLOW_STATE_CONFLICT` | 工作流当前状态不允许该操作。 |
| 410 | `QR_EXPIRED` | 二维码已过期。 |
| 413 | `ATTACHMENT_TOO_LARGE` | 附件过大。 |
| 413 | `FILE_TOO_LARGE` | 文件过大。 |
| 415 | `ATTACHMENT_TYPE_NOT_ALLOWED` | 附件类型不被允许。 |
| 415 | `FILE_TYPE_NOT_ALLOWED` | 不支持的文件类型。 |
| 422 | `AGENT_OUTPUT_SCHEMA_INVALID` | 模型输出未通过 schema 校验。 |
| 422 | `MAGICCLASS_DOCUMENT_REJECTED` | 内容未通过校验，未保存 |
| 422 | `NOTICE_UNPARSEABLE` | 无法识别为通知文本，请粘贴真实校园通知。 |
| 422 | `VALIDATION_FAILED` | 请求参数校验失败 |
| 429 | `MAGICCLASS_RATE_LIMITED` | 互动课堂服务请求过于频繁，请稍后重试 |
| 429 | `QR_RATE_LIMITED` | 创建二维码过于频繁，请稍后再试。 |
| 502 | `MAGICCLASS_AUTH_ERROR` | 互动课堂服务鉴权失败，请稍后重试 |
| 502 | `MAGICCLASS_INVALID_ORIGIN` | 互动课堂返回地址校验失败 |
| 502 | `MAGICCLASS_PROTOCOL_ERROR` | 互动课堂服务响应异常，请稍后重试 |
| 502 | `MAGICCLASS_SERVER_ERROR` | 互动课堂服务内部错误，请稍后重试 |
| 503 | `AGENT_PROVIDER_UNAVAILABLE` | 模型 provider 暂不可用。 |
| 503 | `AGENT_RUNTIME_UNAVAILABLE` | Agent 运行时当前不接受新任务。 |
| 503 | `EDU_ADAPTER_UNAVAILABLE` | 教务系统 Adapter 暂不可用 |
| 503 | `MAGICCLASS_FUSION_UNAVAILABLE` | 受管 magic class 服务当前不可用，请稍后重试 |
| 503 | `MAGICCLASS_INCOMPATIBLE` | 互动课堂服务版本不兼容，已暂停生成 |
| 503 | `MAGICCLASS_NOT_ENABLED` | 互动课堂服务未启用 |
| 503 | `MAGICCLASS_UNAVAILABLE` | 互动课堂服务不可用，请稍后重试 |


## 桌面设备凭据、事件与专用实时语音

设备绑定结果为固定状态 PENDING/CONFIRMED/EXPIRED/REVOKED；只有 CONFIRMED 提供 device_id/device_credential，其他状态值为 null。设备凭据只在 HTTPS 返回，服务端只存哈希，不能当作普通用户 JWT。绑定二维码与独立轮询 token 不可互换；详见[设备协议](15-devices.md)。事件批次回执含 accepted_event_ids 和 duplicate_event_ids，ID 改内容返回409并原子回滚整批；不会用事件改写专注时长或用户事实。

WS /api/v1/devices/me/voice-sessions/{voice_id}/ws 使用 Authorization 设备 bearer 请求头。PCM 输入16kHz/单声道/16bit，输出24kHz/单声道/16bit；文本事件和命令沿用用户语音协议，provider_event 仅透出事件类型名，不透出上游凭据。握手无权关闭1008；活连接每帧和约一秒周期核验设备、账号及专注状态，撤销或会话结束后关闭。上游不可用返回 error 事件并退出。创建会话和重试记录是进程内短时状态，未连接5分钟过期、连接最长4小时，重启后须重新创建。设备应用须支持握手请求头。

学习偏好配置未保存时 configured=false/version=0/updated_at=null，默认值不代表观测到的偏好。更新带 expected_version+idempotency_key，原请求重放返回历史操作响应；409版本冲突应重新读取并由用户处理，不能强制覆盖。计划预算受明确容量进一步限制，配置变化使未执行旧计划失效。接口行为与各端未适配情况见[学习状态协议](11-learner.md)。
