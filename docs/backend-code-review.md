# CampusMateAI 后端代码质量审查报告

- 审查范围：`backend/`（FastAPI + SQLite + Pydantic），`app/` 共 **75,423 行 / 90+ 源文件**，`tests/` 235 个测试文件
- 审查方式：静态代码阅读，5 路并行深度分析（database / repositories / services / api+DI / 横切质量），**未运行时验证**、未修改任何文件
- 行号基于当前工作区状态，可复核
- 报告日期：2026-10-04

---

## 0. 总评

### 0.1 结论

**不是无药可救的屎山，而是「骨架好、肉烂了」。**

架构分层清晰且被真实遵守：`routes → services → repositories → database`，5 份分析均确认**零循环 import**（全仓无 `services → api` 导入）。安全基建扎实，异常体系完整。

问题集中在四类：

1. **层内巨型文件**（God File / God Class）
2. **层间边界被击穿**（service 写 SQL、route 写 DDL、repository 塞业务规则）
3. **样板代码存在百份手抄拷贝**
4. **没有任何静态检查兜底** —— 0 lint、0 mypy、CI 只跑 pytest

### 0.2 一个贯穿全局的定性

多路分析独立发现了同一件事：**同仓库内"正确写法"与"错误写法"并存**。

| 正确（已存在） | 错误（并存） |
| --- | --- |
| `rag_service.py:697` 用 `run_in_threadpool` | `routes/study.py:438` 不用 |
| `agent_runtime/worker.py:43-45,159-394` 每次包 `_offload` | 同目录 `tool_gateway.py:119-413` 不包 |
| `edu/session.py:201` `PreLoginSessionStore` 加 `RLock` | 同文件 `:97` `InMemorySessionStore` 裸 dict |
| `classroom_service.py:364-528` 用 `asyncio.to_thread` | `routes/magicclass_classroom.py:264-335` 不用 |
| `routes/chaoxing.py:24-39` `_sync_locks` 有锁 | `chaoxing/session_cache.py:28-38` 无锁 |
| 共享 `services/_time.py`、`_multi_role_common.py` | 7 大 service、11 个 repository 无一使用 |
| `schemas/multi_role.py:16,23` 通用 `Page`/`PageMeta` | 11 个专用 `*Page` 各写一份 |
| 多数端点有 `response_model` | 20+ 端点返回 `-> dict` |

**这说明规范存在，但从未成文、从未强制。** 这也是 Phase 0（建门禁）杠杆最高的原因。

### 0.3 明确做得好、不要动的部分

- SQL 注入面干净：全仓 f-string 拼 SQL 均为常量、PRAGMA 白名单标识符或 `?` 占位符，**未发现用户输入直接入 SQL**
- 异常体系完整：`core/exceptions.py` 有 `AppException` 基类 + ~100 子类 + 统一 `register_exception_handlers`（`:603`，4 个 handler）
- 密钥全走 pydantic-settings，`.env.example` 无真实凭据，`config.py:554` 有生产守卫
- 口令 PBKDF2-HMAC-SHA256 100k 迭代 + `hmac.compare_digest`；refresh token SHA-256 落库不明文
- SSRF：`ssrf_guard.py:73` DNS 解析后**复核解析结果**（防 rebinding）+ `safe_join_url`；`discovery_service.py:151` 每个 30x 跳转重新校验
- 路径穿越三处校验：`core/security.py:45-67`、`material_extraction.py:87-102`、`resource_proxy.py:173,178,238`
- **0 处裸 `except:`**；多数 `except Exception` 带 `# noqa: BLE001`
- `counselor.py:627`、`fusion_client.py:206-228` 的吞异常带结构化 reason，是**有意降级**，不算问题
- 乐观并发正确样板：`agent_runtime_repository.py:398,498,575,610,625`（`rowcount != 1` 回滚）、`submission_repository.py:45,222`（`BEGIN IMMEDIATE`）
- `agent_runtime` 幂等 `build_request_hash`、租约 `claim_next_run` 设计正确
- **0 处 TODO/FIXME、0 段注释掉的大段代码**
- 58 个路由模块 57 个导入鉴权依赖，未发现"操作用户数据却完全无鉴权"的端点

---

## 1. 一等威胁（正确性 / 安全）

### 1.1 会话过期判断失败开放（安全语义反转）

`app/services/edu/session.py:46-47, 191-192`

时间解析异常 → 返回 `False` → 调用方判定"未过期" → **会话永不过期**。

安全语义应 fail-closed：解析失败应**视为已过期**。

同类问题：`services/edu/discovery_service.py:79-88` `_is_intranet_url` 解析失败默认"**非内网**" → SSRF 判断偏向放行。

### 1.2 同一张表两份 DDL → 新旧库 schema 漂移

`app/database/sqlite_db.py`

| 表 | schema 版 | 迁移重建版 | 差异 |
| --- | --- | --- | --- |
| `edu_bindings` | `:867-893` | `:2577-2602` | 前者**有** `FOREIGN KEY(edu_system_id)`（`:887`），后者**没有** → 老库永久缺 FK |
| `learning_plan_feedback` | `:1353-1363` | `:2305-2312` | 前者**有** `CHECK(feedback IN ...)`（`:1357`），后者**没有** |
| `personal_tasks` 唯一约束 | `:360-361` 内联 `UNIQUE` | `:2370-2373`、`:2489-2492` partial index | 新旧库索引形状不同 |
| `chaoxing_exams` / `chaoxing_knowledge_points` | `:496-516`、`:540-556` | `:2456-2467` | **B 处为不可达死代码**（见 §7.1） |
| `idx_forum_posts_category` | `:726-727` | `:2553-2556` | 完全重复 |

根因：无 schema 版本号机制，只有幂等 `if "col" not in cols` 判断，导致同一结构被多处独立声明。

### 1.3 事务越界：内存模式下未提交事务跨调用泄漏

`app/database/sqlite_db.py`

- `transaction()`（`:2756-2768`）异常时正确 `rollback()`（`:2764-2766`）
- `_release()`（`:1981-1986`）：文件模式 `conn.close()`（未提交自动丢弃，**靠巧合正确**）；**内存模式只释放锁，不关连接、不回滚**
- `query()`（`:2770-2790`）：**从不 commit/rollback**

后果：在"只读"上下文里写了 SQL，变更残留在共享连接的开放事务上，**被下一次无关 `transaction()` 的 `conn.commit()`（`:2763`）捎带提交**，或被无关异常回滚。

同时存在**三套事务惯用法并存**：
1. `with db.transaction()` — 26 文件、176 处
2. `with db.query()` — 只读
3. 手写 `db._connect()` + `try/finally _release()` + 人肉 `commit()` — `agent_runtime_repository.py` **46 次 `_conn()` 只有 16 次 `commit()`**、`final_review_repository.py` 除 `:640` 外全部

同文件混用：`agent_runtime_repository.create_job:88` 用 ③ vs `create_run:777` 用 ①。

### 1.4 读-改-写竞态（并发丢更新）

| 位置 | 说明 |
| --- | --- |
| `routes/magicclass_quiz.py:31-60` | JSON store 竞态，**`:46-47` 注释自认窗口**，并发提交答题静默丢数据 |
| `notice_workflow_repository.py:605-621` | `mark_step_done`：`:607` 另一连接读 JSON、`:617` 再写回，**并发必丢更新** |
| `edu_repository.py:145→190`、`:436→439`、`:98→109` | read-then-write 跨连接无事务 |
| `notice_workflow_repository.py:409-445` | 一次更新用 4 条查询 / 3 个独立连接 |
| `routes/submissions.py:252-280` | `get_submission → get_assignment → upsert_submission` 三次独立连接，校验与写入间有 TOCTOU 窗口 |

**跨 repository 组合完全无共享事务：**

| 位置 | 问题 |
| --- | --- |
| `routes/final_review.py:265-276` | `create_job()` + `create_run()` **两次独立事务**，中间失败留孤儿 `agent_jobs`；而**同文件 `:454`、`:817` 用的是原子版** `create_job_with_run_and_event` |
| `routes/notice_workflows.py:201-226` | 三次独立事务（job → run → update_job_input_ref） |
| `routes/course_research.py:166-172` | 同样两步 |
| `services/edu/connector.py:613,767,792,912,953,988` | `upsert_binding` 与 `sync_*_items` 分步提交 |

### 1.5 吞异常已造成过真实事故（代码自证）

`learner_state_service.py:352-357` 注释原文大意：

> `list_for_user` 只接受 `page_size <= 100`；此前写 200 会被直接拒绝，而下面的 `except Exception: pass` 把异常吞掉，于是 **WORLD 投影的 learner event 永远是空的**（自证据隔离也因此从未真正生效过）。

**其他零日志吞异常点：**

| 位置 | 后果 |
| --- | --- |
| `learning_planner_service.py:133-140` | `except Exception: continue`，**零日志**，唯一痕迹是 `warnings.append("forecast_unavailable")` |
| `rag_service.py:487-495` | `except Exception: task_hint = ""`，零日志 |
| `routes/chaoxing.py:128-131` | **任意**异常 → `status="unavailable"` 并**缓存 30 秒** → bug 与宕机不可区分，且把 bug 结果缓存住 |
| `services/container.py:637-640` | 索引重建失败 `except Exception: pass` |

**降级只记 `type(exc).__name__`，根因不可追溯：** `learner_state_service.py:166-173`（ACADEMIC `:228`、WORLD `:290`），7 个大 service 共 35 处 `except Exception`。

### 1.6 两个明确的功能性 bug

**Bug A — 时区归一化失效**
`learner_event_service.py:678-687` `record_chaoxing_assignment_graded`
- `:678` `occurred_at = self._parse_aware_datetime(observed_at)`
- `:679-680` 只用它判 `None`
- `:687` `occurred_at=observed_at` **传入构造函数的是原始值** → 解析结果被丢弃，时区归一化实际不生效

**Bug B — 指标语义错误**
`learner_state_service.py:1182-1185`
```python
future_7d_count = 0
for item in schedule_items:
    future_7d_count += 1
density = float(future_7d_count) / 7.0
```
- 循环体只 `+= 1`，**等价于 `len(schedule_items)`**
- 变量名 `future_7d` 与实际不符：**未过滤 7 天**
- 直接影响 `:1185` 的 `density` 与 `:1186` 的 `high_density` 判定语义

### 1.7 限流与输入约束缺失

| 问题 | 位置 |
| --- | --- |
| **匿名 LLM 端点无长度限制、无限流** | `routes/counselor.py:660-667`（`current_user_optional`，`user=None` 通过）+ `schemas/chat.py:95`（`message` 只有 `min_length=1`，**无 `max_length`**） |
| **登录端点无限流/无锁定** → 撞库 | `routes/auth.py:112-124` |
| **公开注册无限流** | `routes/auth.py:127` |
| 全仓唯一限流是 QR 创建 | `routes/qr_auth.py:170` |
| `conversation_id`、`course_id` 无长度限制 | `schemas/chat.py:96,116` |
| `deadline_before/after` 裸 `str`，无日期格式校验 | `routes/personal_tasks.py:117-118` |
| `knowledge/manage/{action}` 路径参数无 `pattern` | `routes/knowledge.py:257-258` |
| `bing` 分页手写校验 → 400 而非 422，信封不一致 | `routes/bing_daily_wallpaper.py:184-194` |

### 1.8 权限闸门不一致（越权面）

**A. 两套角色闸门语义分裂**
- `require_role(*roles)`（`deps.py:97-109`）只看 `user.role`
- `student_only`（`deps.py:112-116`）额外排除 `original_role == "teacher"`
- teacher→student 运行时降级在 `deps.py:49-53`

结果：同一批"学生能力"端点中，`require_role("student")` **放行**历史 teacher 账号，`student_only` **拒绝**。

- `require_role("student")`：`dashboards.py:23`、`community.py:115,134,149,158,210,227,232,237,242,247`、`chaoxing.py:57,103,152,184`、`student_tools.py:67,75,84,93`、`academic.py:45,64,91,97`、`forecasts.py`、`simulations.py`、`learner_state.py`
- `student_only`：`final_review.py`（13 处）、`learning_plans.py:25` 系、`adaptive_interventions.py:30` 系、`learner_control.py:28` 系、`notice_workflows.py:32`、`agent_runtime.py:255`

**B. 同文件内管理员旁路不一致**
`routes/agent_runtime.py`：允许 admin — `:330,346,462,611,632`；**不允许 admin**（只比 `run["user_id"] != user.id`）— `:478`（cancel_run）、`:503`（pause/resume/retry `:550,561,572`）。管理员能读别人的 run，取消/暂停/重试却一律 403。无注释说明是否刻意。

**C. 管理端点缺租户隔离（跨校越权）**
- `community.py:286-292` `admin_list_reports` 按 `user.university_id` 过滤 ✅
- `community.py:298-306` `admin_resolve_report` **只按 `report_id` 取，无 university 过滤** ❌ → 多校部署时 A 校 admin 可处置 B 校举报

**D. 按设计公开的端点（应记录在案）**
`health.py`、`knowledge.py:52`（`/knowledge/status`，可读 chunk/doc/user 计数与 LLM 可用性）、`home_banners` 公开 feed、`community.py:95`（categories）、`bing_daily_wallpaper`、`qr_auth.py:155,214,280,332,404`、`auth.py:112,127,146`、`counselor.py:664`（匿名可聊）

### 1.9 其他安全残留

| 问题 | 位置 |
| --- | --- |
| **CORS 正则过宽**：`allow_all` 用精确相等（`:151`）、`has_wildcard` 用子串（`:150`）不一致 → 配 `https://*` 会走 `allow_credentials=True` + 正则放行；`:213` `http://localhost:*` → `^http://localhost:.*$`，`*` 译成 `.*` 可匹配任意端口与任意后缀（应译 `:\d+$`）；`:210` 非通配分支只转义 `.` 不转义 `+?()`；`:205-206` 空 origins 返回 `.*`（当前为死代码，重构即全放行） | `main.py:145-171, 203-215` |
| **SSRF 双实现**：`edu/adapters/ssrf_guard.py:30` vs `course_research/source_fetcher.py:52`，网段/redirect 规则各改各的 | — |
| `ssrf_guard.py:72-79` 解析与请求两次 DNS → rebinding/TOCTOU 残留；`:63-69` 提供 `allow_private=True` 通道被 `zhengfang_http.py:368,406` 使用 | — |
| `discovery_service.py:140,164-166` 非生产 + `edu_allow_insecure_ssl` → `verify=False` 中间人 | — |
| **绕过 `Settings` 直接 `os.getenv`**（全仓唯一 1 处），密钥不进 `.env.example` 文档/校验/测试注入链路 | `services/magicclass/service_assertion.py:40,42` |
| Token 支持走 query 参数；当前 `main.py:62` 只记 path 不泄露，但反代 access log 会落 token | `deps.py:72,88` |
| dev `jwt_secret` 默认值派生 Fernet key 完全可预测（有 `config.py:554` 生产守卫，建议加 dev 警告日志） | `core/config.py:311` → `core/security.py:28-31` |
| `.env.example` 重复配置块（运维只改一份的陷阱） | `:105-110` vs `:251-258`；`:111` vs `:265` |
| `learning_rooms.py:81-88` 用 uid 拉取同学展示名（需与产品确认） | — |

---

## 2. 性能与可用性

### 2.1 事件循环阻塞（最普遍的系统性问题）

**最严重：RAG 在锁内全量重建索引**
```
routes/study.py:425 async def task_breakdown
  → :438 await service.breakdown(...)
  → task_breakdown_service.py:448 同步 self._retrieval.search(query, k=5)
  → retrieval_service.py:381 with self._lock:      ← threading.RLock（:244）
  → :383 _rebuild_locked()
      :462-474 list_chunks + list_documents + 逐块 tokenize + BM25Okapi(全语料)
      :393 tokenize_zh(query)（jieba）
```
单请求可独占事件循环并锁死并发。**对照正确写法：`rag_service.py:697` `await run_in_threadpool(self._retrieve_context, q)`。**

**其余阻塞链路：**

| 位置 | 说明 |
| --- | --- |
| `routes/learning_plans.py:58,65` | async → 同步 `generate`（`learning_planner_service.py:85-345`，约 260 行：sha256 全量 dump、十余次同步 DB、`project_world`、5 次 forecast）。`:212,227` 同样 async → 同步 `summarize` |
| `routes/counselor.py:660-667,681-687` | **SSE 流式**接口 → 同步 `_collect_learner_state_context`（定义于 `:383`，内部 `:425-428` 跑 5 次全量 forecast）→ 阻塞直接冻结整条流 |
| `services/agent_runtime/tool_gateway.py:119,182,224,243,252,269,281,300,311,413-423` | `async def invoke` 内直接同步 SQLite。**同目录 `worker.py:43-45,159-394` 每次都包 `_offload`** |
| `services/edu/connector.py:151,850,874-996` | async 里同步 SQLite 写 + **循环内阻塞 DNS**（`ssrf_guard.py:73 socket.getaddrinfo`，`:103 assert_safe_url`） |
| `routes/edu.py:869,887,895` | async → `discovery_service.py:50,69,76,209` 同步 `read_text/write_text` |
| `routes/magicclass_classroom.py:264,288,307,335` | 直调同步 service；**同仓 `classroom_service.py:364,390,418-468,511-528` 已正确 `to_thread`** |
| `routes/final_review.py:159-194`、`routes/course_research.py:142,223,242,261,295` | async 直调仓储 → 抢 `sqlite_db.py:2759` 全局 `RLock` → **写事务期间阻塞整个事件循环** |
| `routes/magicclass_quiz.py:31-60` | async 路由 + 同步 JSON store（兼竞态） |

**无锁的进程内可变状态：**

| 位置 | 结构 |
| --- | --- |
| `services/edu/session.py:97` | `self._sessions: dict` 裸 dict，`:127-154` 读写全无锁（**同文件 `:201` `PreLoginSessionStore` 正确用了 `RLock`**） |
| `services/chaoxing/session_cache.py:28-38` | 模块级裸 dict；`_evict_if_needed` 先 `sorted(cache.items())` 再 `cache.pop`（遍历+变异非原子）→ 进线程池即 `RuntimeError: dictionary changed size during iteration` |
| `sqlite_db.py:2817,2820-2825` | `_db_instance` + 非线程安全 check-then-set |
| `services/container.py:233` | 全局 `_container` |

### 2.2 N+1 查询

| 位置 | 规模 |
| --- | --- |
| **`learning_plan_repository.py:406-419` + `get_plan:118-153`** | `list_plans` 取一页后**逐 plan 调 `get_plan()`**，而 `get_plan` 本身 1 连接 + 2 查询 + `:138-142` 循环查 evidence → 一页 20 条 × 5 item ≈ **20 次 `sqlite3.open` + ~120 条 SQL** |
| **`submission_repository.py:1071-1096`** | `teacher_analytics` 每个作业**新开连接**查分数（`:1073`），`:1083-1087` 还用 `next()` 线性扫 → **N 次连接 + O(n²)** |
| `submission_repository.py:696-710` | 列表 SQL 内 5 个相关子查询/行 |
| `submission_repository.py:974-994` | 同方法 7 个相关子查询/行 |
| `learning_planner_service.py:156-164` | 每门课 2 次查询，课程数无上限 |
| `learning_planner_service.py:665,717` | 遍历 item/action → 逐个 `get_task()` |
| `routes/community.py:199-206` | `_comment_out` 在 `author_name is None` 时查 user → **每条匿名评论白跑一次查询，结果在 `:205` 根本用不到** |
| `notice_workflow_repository.py:396-407` | 先 `list_sources_for_user` **全表读入内存**再 Python `next()` 过滤 |
| `edu_data_repository.py:186-265,436-482,600-645` | sync 循环内逐条 SELECT + INSERT/UPDATE |

### 2.3 无 LIMIT 的全量读（18+ 处，无统一有界读策略）

| 文件 | 行号 |
| --- | --- |
| `agent_runtime_repository.py` | `:748`、`:866`、`:1049`、`:1062`、`:1587` |
| `final_review_repository.py` | `:257`、`:419`、`:610` |
| `notice_workflow_repository.py` | `:367`、`:374`、`:659` |
| `edu_data_repository.py` | `:297`、`:503`、`:665`（课表/成绩/考试按 user 全量返回） |
| `learner_control_repository.py` | `:216`、`:246`、`:326-363`（10 条 `COUNT(*)` 全表扫） |
| `submission_repository.py` | `:254`、`:970`、`:1005` |
| `learning_planner_service.py:182` | `list_notices(user_id)` **无分页拉全表**再 `[:MAX_NOTICES]`（`notice_repository.py:75` 签名无 limit） |
| `forecast_service.py:323,329,335` | `list_schedule_items/exam_items/grade_items` 无界 |

对照：同层其他方法是有界的（`agent_runtime_repository.py:145-157,649-697,723-746,1130-1142`）→ 逐处决定，无规范。

**附带：** `IN (placeholders)` 变量数无上界（`learner_control_repository.py:514-595`、`edu_data_repository.py:271,488,651`）→ 规模大时撞 SQLite 变量数上限。

### 2.4 缓存与算法

**`forecast_service` 缓存三重缺陷**
```python
:144  self._cache: dict[str, ForecastOut] = {}   ← 无容量上限、无淘汰
:396  cache_key = self._cache_key(...)            ← 每次 sha256(json.dumps(全量输入))
:398  if cached ... _parse(cached.valid_until) ... ← TTL 只在读时判断，_parse 调两次
:408  self._cache[cache_key] = forecast           ← 过期条目永不清理
```
- key 含全量输入摘要（`:411-420`）→ 输入微小变化即新 key → **旧条目永久残留，内存单调增长**
- 缓存查找本身开销接近一次投影计算

**其他复杂度问题**

| 问题 | 位置 |
| --- | --- |
| O(n²) 两两比较，内层对同一 `other` 每轮重复 `fromisoformat`（`//2` 说明是无向重复计数，本可排序后线性扫） | `forecast_service.py:593-604` |
| 循环内对累积列表做 digest → O(n²) 序列化 + sha256 | `learning_planner_service.py:302-303` |
| 分页纯装饰：`:172` 循环把 5 种 forecast 全算完才在 `:184-186` 切片，`page_size=1` 也照算 | `forecast_service.py:162-186` |
| 每次 `get_forecast` 都全量 `_collect_inputs`（`:202`）→ `learning_planner:129-137` 连调 5 次 = **5 次全量采集** | — |
| `_workload` 对同一批 deadline 反复 `_parse` | `learner_state_service.py:1541` |
| 每课程全量扫描（events/content/sections/tasks）→ O(课程 × 事件总数) | `learner_state_service.py:1578-1668`，由 `:1390-1405` 触发 |

### 2.5 启动与连接开销

| 问题 | 位置 |
| --- | --- |
| 启动期对 **~95 张表逐个 `PRAGMA foreign_key_check`**（需扫表，O 总行数） | `sqlite_db.py:2123-2133` |
| 每次启动重放 27 个 schema + 16 个迁移 + 15 处 `PRAGMA table_info`，即使全新库 | `sqlite_db.py:2146-2156` |
| `_execute_schema_script` 每次启动重解析约 1900 行 SQL | `sqlite_db.py:1988-1998` |
| **每请求新建连接** + 重复 `PRAGMA journal_mode=WAL`（WAL 是持久属性） | `sqlite_db.py:1975-1979`，无连接池 |
| **每次请求 new repository → 每次请求跑 DDL `executescript`** | `routes/final_review.py:60-61`（15 处）、`routes/course_research.py:45-46`（7 处）、`routes/notice_workflows.py:38,195` → 各自 `__init__:_ensure_schema` |
| `documents` **无 `imported_at` 索引**却 `SELECT * ORDER BY imported_at DESC`，且 `content_text`/`raw_text` 是 `NOT NULL TEXT` 全文列 → 全量拉进内存排序 | schema `:59-85` vs `document_repository.py:127,230` |
| `documents` 的 `is_official`/`is_expired` 列无索引 | `:74-75` |
| `course_resource_cache` 主键 `(item_id, user_id)` **无 user_id 打头索引**，`prune_cache` 全量读再逐行 DELETE | schema `:656-673` vs `course_content_repository.py:294-307` |
| 每请求一次线程池往返打日志 + dispatch 内每请求调 `get_settings()` | `main.py:56-65` |
| 启动阻塞：`await asyncio.to_thread(...tick, batch_size=25)` 在 yield 之前 → tick 慢则健康检查不可用 | `main.py:84` |
| 每次启动都写库（验收账号 seeding + 学校名单 seed） | `main.py:100-114` |
| 迁移期循环内 `import hashlib` + 每行 `md5` | `sqlite_db.py:2732-2754` |
| `SELECT COUNT(*) FROM sqlite_master WHERE ... name=?` 应直查 | `sqlite_db.py:2714-2716` |
| `import app.main` 即产生文件系统副作用（创建静态目录） | `main.py:177-193,218` |

---

## 3. 错误契约一致性

### 3.1 至少 4 套并存

**规范（正确的一套）：** 统一信封 `{code, message, details, request_id}`，`core/exceptions.py:587-600`；注册于 `:603-667`。

**偏离 A — 裸 `HTTPException` → 业务码被压成 `HTTP_ERROR`**
`exceptions.py:643` 只映射 `404/405/500`，其余 `code_map.get(..., "HTTP_ERROR")`。受影响 **27 处**：
- `routes/course_content.py:37,171,179,188,190,194,207,209,212,232,250`（12 处，`detail="resource_not_found"` 这类**本应是业务码**的字符串）
- `routes/chaoxing.py:62,81,82,157,170,189`
- `routes/tts.py:23,25,27`
- `routes/focus_ai.py:27,32,37`、`routes/focus_realtime_voice.py:35,47`
- `routes/student_tools.py:50,88`

**偏离 B — 绕开处理器手写响应**
- `routes/magicclass_quiz.py:54` → `JSONResponse(409, {"detail": ...})`，**却声明了 `response_model=QuizAttemptStateOut`（`:39`）** → 声明与实际不符，返回体无 `code`/`request_id`
- `routes/bing_daily_wallpaper.py:31-43` `_error_response` **漏 `request_id`**（调用点 `:177,212,215`）；`:169,230` 直接透传上游状态码与 payload

**偏离 C — HTTP 200 + 业务失败**
- `routes/edu.py:380-381,392-393,406-407,420-421` 未绑定教务账号 → `EduSyncResult(status="failed")` 却 200
- `core/exceptions.py:67-71` `KnowledgeBaseEmpty.http_status = 200`、`:111-114` `LLMUnavailable.http_status = 200` —— **异常类却返回 200**，客户端无法状态码分流
- `routes/student_tools.py:96-97` DELETE **无 rowcount 判断，恒返回 `{"ok": true}`**
- `routes/counselor.py:759-773`（非流式）、`:864-874`、`:898-908`（SSE）失败仍 200 + `mode="error"`

**偏离 D — Repository 层 6 种契约并存**
① 自定义 `AppException` ② 裸 `ValueError` ③ 裸 `RuntimeError` ④ 泄漏 `sqlite3.IntegrityError`（`adaptive_intervention_repository.py:178,188`、`learning_plan_repository.py:283,290`）⑤ 返回 `None`/空列表（同类操作三种语义）⑥ 返回类型不一致（typed Row vs dict vs dataclass vs schema）

特别注意：
- `edu_repository.py:115,237,390,477` 用 **`assert result is not None` 作运行时校验** → `python -O` 下断言被剥离
- `final_review_repository.py:155-156,464-465,726-727` 的 `return None` 在 `conn.commit()` **之前**，靠 `finally: _release` 才回滚，语义隐晦
- 同类操作：`archive_campaign:162-175` 不检查 rowcount 无条件 commit，而 `activate_campaign` 返回 None
- `# type: ignore[return-value]` 掩盖写后回读可能为 None：`submission_repository.py:82,243`、`notice_workflow_repository.py:350,497,649`

### 3.2 500 响应的结构性缺口（需实测确认）

按 Starlette 中间件栈推导：`ServerErrorMiddleware` 在**最外层**，而 `RequestIdMiddleware`（`main.py:174`）与 `CORSMiddleware`（`main.py:155/164`）在其内侧 → 未捕获异常的 500 响应**不经过**这两个中间件：
- 缺 `x-request-id` 响应头（`RequestIdMiddleware` 只在 `main.py:54` 加头）
- 缺 CORS 头 → 浏览器侧表现为「CORS 错误」而非可见 JSON 错误体
- `exceptions.py:656-667` `_unhandled_exception_handler` 未记录 traceback

### 3.3 TTS 503 分支缺 `request_id`
`core/exceptions.py:646-653`，其余错误响应均带。

---

## 4. 分层泄漏与架构问题

### 4.1 Service 层绕过 Repository 手写 SQL

**最严重的架构问题：** `learner_state_service.py` 两处直接访问私有属性 `self.repository._db`，手写 **8 段裸 SQL**：

```
:367-404   with self.repository._db.query() as conn:
             :369-375  SELECT ... FROM personal_tasks        LIMIT 200
             :377-386  SELECT ... FROM personal_tasks (成绩)  LIMIT 200
             :387-394  SELECT ... FROM chaoxing_exams         LIMIT 200
             :395-401  SELECT ... FROM study_sessions         LIMIT 200
:853-890   with self.repository._db.query() as conn:
             :855-864  SELECT ... FROM personal_tasks (成绩)  LIMIT 200  ← :379-386 逐字符重复
             :865-872  SELECT ... FROM chaoxing_exams                    ← :389-394 逐字符重复
             :873-880  SELECT ... FROM chaoxing_knowledge_graphs LIMIT 100
             :881-888  SELECT ... FROM chaoxing_knowledge_points LIMIT 500
```

第三次重复在 `chaoxing_repository.py:354,381,387`。同类越界：`adaptive_agent/intervention_service.py:505` 也用 `repository._db`。

危害：私有属性越权、表名列名与魔法 `LIMIT 200/100/500` 散落 service、repository 封装形同虚设、改一处必忘一处。

### 4.2 Route 层泄漏

| 类型 | 位置 |
| --- | --- |
| **写 SQL / DDL，且用 DB 私有 API** | `routes/final_review.py:79-95`（`container.db._connect()` / `_release()` + `CREATE TABLE IF NOT EXISTS`） |
| **原始 CRUD + 每请求执行 `_ensure_tables`** | `routes/student_tools.py:33-45`(DDL)、`:68,76,85,94`(每请求 DDL)、`:69-71`(SELECT)、`:77-80`(INSERT)、`:86-89`(UPDATE)、`:95-96`(DELETE) |
| **`student_exams` DDL 两份且格式不同** | `student_tools.py:37` vs `final_review.py:82` |
| 原始 SQL | `routes/qr_auth.py:563-572,622-629`（已按 `user_id` 限定，风险是分层不是越权） |
| **直接出网（httpx）** | `routes/counselor.py:105-119`（bing RSS）、`routes/bing_daily_wallpaper.py:141-177,204-230` |
| **每次请求 new repository** | `final_review.py:60-61`（15 处）、`course_research.py:45-66`（7 处，且 `_build_pipeline` 与 `container.py:608` 重复）、`notice_workflows.py:38,195`、`learning_rooms.py:21-22`、`study.py:68`（第四种风格：把 `_repo` 自身做成依赖） |
| 巨型 handler | `counselor.py:125-310`(186 行)、`counselor.py:660-773`(114 行，SSE 延伸到 `:908`)、`final_review.py:213-382`(170)、`final_review.py:580-740`(161)、`edu.py:375-424,449-589`(内联 dict 拼装) |
| 跨层引用私有成员 | `routes/chaoxing.py:7`（`ChaoxingClient._auth_error`）、`:16`（`sync_service._normalize_deadline`） |
| 文件中段 import | `routes/edu.py:833` |

### 4.3 Repository 层反向塞业务逻辑 + 与 API 双写

| Repository 内的业务规则 | API 层重复实现 |
| --- | --- |
| `submission_repository.py:15-27`（作业关闭/可重交策略 + 抛 3 个领域异常）、`:40,53-56`（重交状态机：→ `resubmitted`、清空 score/comment）、`:387-395,916-920`（逾期判定）、`:1033-1168`（完整统计分析） | `routes/submissions.py:232-233,261-265,300-303`（同一套关闭/重交校验）、`:267-273`（late/resubmitted 决策） |
| `edu_repository.py:70-96`（请求校验 6 个 `ValueError`）、`:149-186,266-331`（两套 merge 语义） | — |
| `agent_runtime_repository.py:44-69`（幂等哈希 + 输入白名单）、`:925-1026`（`retry_run_with_control` 可重试判定） | — |
| `chaoxing_repository.py:11` 仓储层做 cookie `encrypt/decrypt` | — |
| `document_repository.py:11` 仓储层做文档分块 `chunk_text/extract_sections` | — |
| `agent_artifact_repository.py:32-60` 仓储层做文件系统 `mkdir` + 原子 rename | — |
| `adaptive_intervention_repository.py:24`、`learner_event_repository.py:12` 引用 `..schemas`（API schema 层）→ **分层倒置** | — |

### 4.4 DI 实为 Service Locator

| 问题 | 位置 |
| --- | --- |
| 全局单例 + **惰性自建**（导入任意路由模块即可能触发数据库初始化与全量服务构造） | `container.py:233`、`:646-653`、`:656-659`；`deps.py:44` |
| **三种注入风格并存** | ① 45 个路由各复制一份 `_container()` helper ② 41 处 `Depends(get_container)`（`agent_runtime.py` 19 处、`final_review.py` 13 处…）③ handler 函数体内直接 `get_container()` → **无法 override 测试**（`knowledge.py:54,85,142,237,247,269`、`counselor.py:667,796`、`notices.py:266,285,311`、`focus_realtime_voice.py:61`、`learning_rooms.py:22,83`、`health.py:14`） |
| 循环回指：容器构造完把自身塞回工具对象 | `container.py:635` |
| 占位引用 + 事后再绑定 | `container.py:411-413,642` |
| 构造期做数据写入 | `container.py:313`（`home_banner_repository.seed_defaults()`） |
| 测试重置不停旧 worker | `container.py:662-671` |

**优点**：反向依赖方向正确，多数 handler 仍是 `Depends(_container)`，具备最小可替换性。

### 4.5 God File / God Class

| 文件 | 实际行数 | 判定 |
| --- | --- | --- |
| `database/sqlite_db.py` | **2842** | Schema DDL + 迁移 + 连接层三合一（**非 CRUD God**，0 处业务 CRUD；71% 是 DDL，95 表 / 179 索引 / 37 处 `ALTER` / 16 个迁移函数） |
| `services/learner_state_service.py` | **1858** | 6 类职责、3 条重复流水线（CORE/ACADEMIC/WORLD）、8 个指标算法 |
| `services/learner_event_service.py` | **1564** | 30 个同模板 `record_*` + 3 入口 6 内部 backfill + **29 处硬编码表名** |
| `services/notice_extraction_service.py` | **1506** | 规则引擎 + LLM 抽取 + 分段去重三合一 |
| `services/task_breakdown_service.py` | **1035** | 中度，LLM 胶水与检索耦合 |
| `services/learning_planner_service.py` | **800** | `generate:85` 主流程约 **260 行**（85-345） |
| `services/forecast_service.py` | **841** | 6 仓储采集 + 5 算法 + 缓存混在一起 |
| `services/rag_service.py` | **885** | 检索编排 + prompt + LLM 调用 + 引用渲染 + 记忆（**但 async 规范最好**） |

---

## 5. 重复代码实测量级

| 样板 | 份数 | 代表证据 |
| --- | --- | --- |
| **分页 COUNT + SELECT...LIMIT/OFFSET** | **~25 份** | `announcement_repository.py:122-141` ≡ `assignment_repository.py:119-138`（逐行同构，仅表名与 ORDER BY 不同） |
| **动态 `UPDATE t SET {', '.join(sets)}`** | **15 份** | 13 个 repository：`agent_runtime:396,496,861`、`notice_workflow:470,570,717`、`course:96`、`user:120`… |
| **`def _now()`** | **13 份** | `_multi_role_common.py:9` 已是标准实现，11 文件不用 |
| **`_uuid()/ _id()/ _new_id()`** | **8 份** | `_multi_role_common.py:13` 已有 |
| **时间解析 `_parse/_iso/_require_utc/_digest/_confidence/_parse_dt/_parse_aware_datetime`** | **8+ 份且已分叉** | 共享 `services/_time.py` 存在并被 5 个其他模块使用，**7 大 service 无一使用** |
| **`_StrictModel`** | **6 份** | `schemas/agent_runtime.py:25`、`course_research.py:19`、`final_review.py:14`、`model_capability.py:8`、`notice_workflow.py:15` + 变体 `agent_observability.py:16` |
| **专用 `*Page` 分页模型** | **11 个** | 通用 `Page`/`PageMeta`（`schemas/multi_role.py:16,23`）几乎无人用 |
| **`extra="forbid"` 内联** | **~95 次** | 38 个 schema 文件 / 418 class，无共享 StrictBase |
| **`UniversityRequired` 异常** | **3 份** | `academic.py:19`、`community.py:29`、`edu.py:65` |
| **`student_exams` DDL** | **2 份** | `student_tools.py:37` vs `final_review.py:82` |
| **风险分档 / momentum 公式** | 双写 | `forecast:612-619` ≡ `learner_state:571-588`；`forecast:627` ≡ `learner_state:616`（`max(0,14-conflict_count)`）；`forecast:643-691` ≡ `learner_state:791-818` |
| **LLM 围栏剥离 + `json.loads`** | **3 份** | `notice:653-662` ≡ `:846-854` ≡ `:1452-1459` |
| **LLM 三重 except 模板** | 8 处 | `rag:748,799,855,871`、`notice:1085,1139`、`task_breakdown:301-322` |
| **backfill try/except 六连** | 6 份 | `learner_event:1371,1418,1454,1483,1497,1549` |
| **补列 `if "x" not in cols: ALTER`** | **37 处显式 ALTER** | 风格 A（字典驱动 `sqlite_db.py:2183-2254`）只用 1 次；同一函数里 if 链与 tuple 循环并存（`:2377-2402`、`:2431-2454`）；`users` 表在两个函数各补一次（`:2406-2427`、`:2512-2518`） |
| **唯一索引探测样板** | 2 份 | `sqlite_db.py:2356-2373` ≡ `:2477-2492` |
| **迁移脚本框架** | 3 份 | `final_review_migration.py:150-279`、`course_research_repository.py:112-`、`notice_workflow_repository.py:157-203` |
| **同构 sync 方法** | 3 份 ~330 行可合一 | `edu_data_repository.py:134-295` / `:397-501` / `:558-663`（结构 100% 相同） |
| **同段 10 条 COUNT** | 2 份 | `learner_control_repository.py:326-363` ≡ `:463-500` |
| **"采集 ids + DELETE IN" 段** | 4 份 | `learner_control_repository.py:505-517,518-531,532-544,569-582`；plan_ids 段 2 份 `:546-564,584-602` |
| **`row→dict` 三种风格并存** | — | `Model.from_row`（40 处）/ 私有 `_row_to_*` / 裸 `dict(row)`（`agent_runtime_repository` 几乎全文件无类型安全） |
| **5 类 forecast_type 元组** | 6 处 | `forecast:163-169`、`learning_planner:129-132`、`simulation:54`、`intervention_service:48`、`routes/forecasts.py:23`、`schemas/forecast.py:18` |
| **提交状态三元组 `("submitted","resubmitted","late")`** | 10 处 | `submission_repository:40,197,388,444,523,701,979,1010,1105` + `assignment_repository:170` |
| **分页参数内联** | 29 处 | 上限三档不一致：`le=100`(19 处)、`le=200`(4 处)、`le=500`(2 处)、默认 50 |
| **文件名清洗** | 3 份 | `core/security.py:45`、`material_extraction.py:87-102`（语义是"拒绝"非 "basename"，差异无文档）、`resource_proxy.py:45` |

**`app/utils/` 共享层形同虚设**：只有 `text_utils.py`、`file_parsers.py` 两个文件，消费方仅 3 个。

**分层去重已有的但没推广的资产**：`repositories/_schema_helpers.py`（19 行，`_table_exists`/`_table_columns`，只有 3 个文件用）；`repositories/_multi_role_common.py`（`_now_iso`/`_new_id`，16 文件用，11 文件不用）；`services/_time.py`（被 5 模块用，7 大 service 不用）；`schemas/multi_role.py:16,23` 通用 `Page`。

---

## 6. Pydantic Schema 使用

- **作为请求体校验（`Body(...)`）用得规范**；`agent_runtime.py:267-271` 对 `dict` 型 `input_ref` 做 handler schema 二次校验，是**关键兜底，做得对**
- **问题在"已有模型却手工 dict"：**
  - `schemas/learner_state.py:56-361` 定义了完整值模型，生产者仍全程拼 dict（`learner_state_service.py:1249,1259,1307,460,987` + `:318-401` 裸 dict）；`ComputedSnapshot.value: dict[str, Any]`（`:62`）跨 1858 行无类型约束
  - `notice_extraction_service.py:50-53` `_LLMBatchResult(BaseModel)` 却声明 `tasks: List[dict[str, Any]]` —— 用 Pydantic 包了一个 dict
  - `notice_extraction_service.py:893-946 _normalize_llm_output` 手工 `obj.get(...)` + 手工白名单 + 手工 clamp + 手工 `fromisoformat`，本应由 `NoticeExtractResponse.model_validate` 完成
  - `task_breakdown_service.py:620-703` 手工 dict 解析 LLM 步骤候选
  - `forecast_service.py:367-383` 用 `getattr(r, "completed_at", None)` 鸭子类型 → **字段改名静默返回默认值而非报错**
  - `magicclass_*.py` 多处 `payload.get(...)` 手工拼返回 dict（判定：对上游响应整形，非缺陷，但**无响应模型 → OpenAPI 只能靠手写文档**）

---

## 7. 死代码与卫生

### 7.1 可直接清理

| 项 | 位置 |
| --- | --- |
| **死表** `conversations` / `app_meta` / `audit_logs` + 2 条索引（全仓库 0 引用） | `sqlite_db.py:100-124` |
| **不可达迁移**（`_migrate()` 在 `:2154` 执行时 27 个 schema step 已在 `:2146-2153` 跑完，表必然存在 → 分支恒为假） | `sqlite_db.py:2456-2467` |
| 每次启动的无效退役 DROP（第一次后永远 no-op） | `sqlite_db.py:2338-2339` |
| `edu_bindings_legacy_v1` 永不 DROP，旧数据永久留库 | `sqlite_db.py:2572` |
| `_migrate_edu_bindings` 双调用（恒空操作的第二次） | `sqlite_db.py:2097` + `:2665` |
| `_today()` 定义后从未调用 | `final_review_repository.py:35-36` |
| **10 个零引用 Row 类**（`models/agent_runtime.py:13-163`，仅 `AgentApprovalRow` 被用） | — |
| 注入但未使用的死依赖（只在 `:75` 判空，`:77-89` 自己写 SQL；`container.py:300` 白传） | `study_session_repository.py:55-59` |
| `input_limit` 参数与属性全文件无第二处引用 | `forecast_service.py:135,143` |
| `state_repository` 全文件无第二处引用（**`container.py:347` 仍注入**） | `learning_planner_service.py:69,76` |
| 三处 `batch_size` 形参声明 + 1..100 校验，函数体内从未使用 | `learner_event_service.py:1354,1390,1428`（外层校验 `:1338-1339`） |
| `text_norm` 计算后未使用 | `notice_extraction_service.py:289,486` |
| `_student()` 定义后全仓无调用点（实际用 `require_role("student")`） | `routes/student_tools.py:48-51` |
| 两个异常类定义后**从未 raise** | `routes/edu.py:71 EduBindingNotFound`、`:77 EduAdapterUnavailable` |
| `UniversityRequired` 三份中的重复 | 见 §5 |
| `reset_container_for_tests` 不停旧 worker | `container.py:662-671` |
| `dispose()` 生产路径未接入（只被测试调用） | `sqlite_db.py:2792-2814` |
| `repositories/__init__.py` 为空（0 行） | — |
| **零测试模块** | `edu/registry.py`、`edu/detector.py`、`edu/discovery_constants.py` |
| **薄/无专属测试** | `magicclass/quiz_attempt_store.py`（**且是竞态载体**）、`magicclass/redaction.py`（**脱敏逻辑无测试属安全缺口**）、`magicclass/compatibility.py`、`agent_runtime/observability.py` |
| 仅间接覆盖 | `learning_planner_service`（800 行 + 260 行主流程缺直接测试） |

### 7.2 结构性问题但不是 bug

- 索引创建散落在迁移里，表结构被拆到两个函数（`personal_tasks` schema `:327-364` 零索引，7 条索引全在 `:2469-2475,2370-2373,2489-2492`）
- DDL 双轨：`sqlite_db.py` + 3 个 repository 构造函数 `_ensure_schema()`，其中 `course_research_repository.py:210` 用 `executescript()`（**会隐式提交**，正是 `sqlite_db.py:1990` 特意规避的问题）
- 阶段编号乱序（曾被打乱的痕迹）：`sqlite_db.py:2667,2677,2709`
- 快照陈旧风险：`course_cols` 在 `:2378` 取一次，`:2401` 判断仍用旧集合
- 嵌套 `transaction()` 无重入保护（无 depth 计数 / savepoint）
- `learner_control_repository.py` 连纯读都用 `transaction()`：`:161,178,209,217,247,269,308,328,607,632,693`
- `LIKE` 通配符未转义（非注入，可被滥用拖慢扫描）：`submission_repository.py:340,676,878`、`community_repository.py:52`、`university_repository.py:44`
- `community_repository.toggle(table, count_column, ...)` 签名允许任意标识符（当前调用点均传字面量，但**无集中 quote helper 兜底**，全仓 49 处 `conn.execute(f"...")` 全靠自律）

---

## 8. 按严重程度排序的完整清单

### 🔴 S — 严重（正确性 / 安全 / 数据完整性）

| # | 问题 | 位置 |
| --- | --- | --- |
| S1 | 会话过期判断失败开放（fail-open）→ 会话永不过期 | `edu/session.py:46-47,191-192` |
| S2 | 同一张表两份 DDL → 新旧库 schema 漂移（缺 FK / 缺 CHECK / 索引形状不同） | `sqlite_db.py:867-893 vs 2577-2602`、`:1353-1363 vs 2305-2312`、`:360-361 vs 2370-2373` |
| S3 | 内存模式未提交事务跨调用泄漏，被无关 `commit()` 捎带提交 | `sqlite_db.py:1981-1986, 2763, 2773-2782` |
| S4 | 读-改-写竞态丢更新（quiz 提交、mark_step_done、upsert） | `magicclass_quiz.py:31-60`、`notice_workflow_repository.py:605-621`、`edu_repository.py:145→190` |
| S5 | 跨 repository 无共享事务 + 同文件原子/非原子版混用 | `final_review.py:265-276 vs 454,817`、`notice_workflows.py:201-226`、`course_research.py:166-172` |
| S6 | 吞异常已致功能性静默失效（WORLD 投影 event 永远为空） | `learner_state_service.py:352-357` |
| S7 | 匿名 LLM 端点无长度限制 + 无限流 | `counselor.py:660-667` + `schemas/chat.py:95` |
| S8 | 登录/注册无限流 → 撞库 | `auth.py:112,127` |
| S9 | 权限闸门语义分裂（历史 teacher 放行不一致）+ admin 读控不一致 + 跨校越权 | `deps.py:97-116`、`agent_runtime.py:478,503 vs 330,346`、`community.py:298-306` |
| S10 | SSRF 判定 fail-open（内网解析失败默认"非内网"） | `discovery_service.py:79-88` |
| S11 | 真 bug：时区归一化结果被丢弃 | `learner_event_service.py:678-687` |
| S12 | 真 bug：`future_7d` 未过滤 7 天 + 无意义循环 → density/high_density 语义错 | `learner_state_service.py:1182-1186` |

### 🟠 H — 高（性能 / 可用性）

| # | 问题 | 位置 |
| --- | --- | --- |
| H1 | RAG 在 `RLock` 内全量重建 BM25 + jieba 分词 | `retrieval_service.py:381,462-474` ← `study.py:438` |
| H2 | async 直调同步重服务：SSE counselor / learning_plans 260 行 / tool_gateway SQLite / connector DNS | `counselor.py:660-687`、`learning_plans.py:58,65`、`tool_gateway.py:119-413`、`connector.py:850-996` |
| H3 | async 路由同步抢全局 `RLock` → 阻塞整个事件循环 | `sqlite_db.py:2759` ← `final_review.py:159-194`、`course_research.py:142` |
| H4 | async 路由直调同步文件 IO | `routes/edu.py:869,887,895`、`magicclass_classroom.py:264-335` |
| H5 | `list_plans` 双重 N+1（20 连接 / ~120 SQL 每页） | `learning_plan_repository.py:406-419` + `:118-142` |
| H6 | `teacher_analytics` 每行开连接 + O(n²) | `submission_repository.py:1071-1096` |
| H7 | 18+ 处无 LIMIT 全量读 | 见 §2.3 |
| H8 | forecast 缓存无界 + TTL 只读判 + key 计算昂贵 | `forecast_service.py:144,396-408` |
| H9 | 启动期 95 表 `foreign_key_check` + 每请求新建连接 + 每请求跑 DDL | `sqlite_db.py:2123-2133,1975-1979`、`final_review.py:60-61` |
| H10 | `documents` 排序列无索引 + 全文列全量入内存 | schema `:59-85` vs `document_repository.py:127` |
| H11 | 任意异常吞并缓存 30 秒为 `unavailable` | `routes/chaoxing.py:128-131` |

### 🟡 M — 中（一致性 / 可维护性）

| # | 问题 | 位置 |
| --- | --- | --- |
| M1 | 错误契约 4-6 套并存（27 处 `HTTP_ERROR`、3 处 200-失败、手写信封漏 `request_id`、恒 `ok:true`） | 见 §3 |
| M2 | Service 层绕过 `_db` 手写 8 段裸 SQL（4 段逐字重复） | `learner_state_service.py:368,854` |
| M3 | Route 层写 SQL/DDL/私有 DB API + 每请求 `_ensure_tables` + 出网 | `final_review.py:79-95`、`student_tools.py:33-96`、`counselor.py:105-119` |
| M4 | Repository 反向塞业务规则 + 与 API 层双写 | `submission_repository.py:15-56` ↔ `routes/submissions.py:232-273` |
| M5 | Service Locator 三种注入风格并存，handler 内联取容器无法测试 | `container.py:233,656-659` + 45/41/12 处 |
| M6 | 20+ 端点缺 `response_model`（`-> dict`） | `community.py` 17 处、`student_tools.py` 4、`edu.py` 5、`academic.py` 4 等 |
| M7 | CORS 正则过宽 + 判断不一致 + 空 origins 潜在全放行 | `main.py:145-171,203-215` |
| M8 | SSRF 双实现 + DNS 两次解析 + `allow_private` 通道 + `verify=False` | 见 §1.9 |
| M9 | 无锁全局状态（同文件已有正确实现却不用） | `edu/session.py:97`、`chaoxing/session_cache.py:28-38` |
| M10 | 重复代码百份拷贝（见 §5 全表） | — |
| M11 | God File / God Class（见 §4.5） | — |
| M12 | 时间工具 8 份且已分叉（`learning_planner:50` 与 `learner_state:28` 行为不同） | 共享 `_time.py` 未被采用 |
| M13 | 启动阻塞 + 每次启动写库 + import 期副作用 | `main.py:84,100-114,177-193,218` |
| M14 | 分页 29 处内联、上限三档不一致、手写校验 400 而非 422 | 见 §1.7 |
| M15 | 测试缺口：无并发竞态测试、无 event-loop 阻塞检测、CORS 纯函数无单测、SSRF 双实现无一致性断言、脱敏逻辑无测试 | 见 §7.1 |

### 🔵 L — 低（卫生）

见 §7.1 死代码全表 + `.env.example` 重复块 + 日志字段 `headers_duration_ms` 实为端到端耗时（`main.py:34`）+ Token 可走 query（`deps.py:72,88`）+ `knowledge.py:52` 匿名可读统计。

---

## 9. 建议的分阶段优化路线

**原则：先止血 → 再建规矩 → 后拆山。** 每阶段独立可提交、可回滚、有验证。

> ⚠️ 前置约束（来自 `AGENTS.md`）：
> - 涉及响应契约变化必须同步 `docs/api/`，并跑 `python scripts/sync_api_docs.py` + `--check` + `backend/tests/test_openapi_docs.py`
> - 需区分已适配 / 待适配 / 未验证平台（`webreact` / `android` / `harmony` / `wx`）
> - 任务完成后需精确暂存并提交本次相关文件

### Phase 0 — 建规矩（约半天，最高杠杆）

- 加 `ruff`（lint + format）+ `mypy`（先 `--ignore-missing-imports`，只覆盖 `core/`、`schemas/`）
- 加 pre-commit，CI (`backend_ci.yml`) 加门禁步骤
- **为什么放最前**：当前 0 lint 配置、0 类型检查，下面任何清理都会继续腐化

### Phase 1 — 止血（1-2 天，只改行为不改结构）

1. 修 12 个一等威胁（S1-S12）：会话 fail-closed、schema 漂移统一、事务 rollback、竞态加锁/原子写、真 bug ×2、SSRF fail-closed
2. 5 条最热 async 链路补 `run_in_threadpool`（RAG / counselor SSE / learning_plans / tool_gateway / connector DNS）
3. `ChatRequest.message` 加 `max_length`；登录 + 匿名 LLM 端点加限流
4. 权限闸门统一（`require_role("student")` vs `student_only`）+ `admin_resolve_report` 补 university 过滤
5. 所有零日志吞异常补 `logger.warning(..., exc_info=True)`
6. 验证：全量 `pytest`（235 个测试文件）+ 每个修复补回归测试

### Phase 2 — 消重复（2-3 天，纯等价替换，风险低）

建共享 helper，每替换一批跑一次全量 pytest：
- `now_iso()` / `new_id()` 收敛（13 + 8 份 → 各 1）
- 时间解析强制走 `services/_time.py`（消除已分叉的 8 份）
- 抽 `paginate()` helper（~25 份 → 1）、`update_fields()`（15 份 → 1）
- `_StrictModel` 合一（6 → 1）、`*Page` 收敛到通用 `Page`（11 → 1）
- `UniversityRequired`、`student_exams` DDL 各归一处
- 风险分档 / momentum 公式抽到共享模块

### Phase 3 — 修边界（3-5 天，结构调整，**契约可能变化**）

- 8 段裸 SQL 下沉 `LearnerStateRepository`；route 层 DDL/CRUD 下沉；每请求 new repository 改容器单例
- 业务规则从 repository 提到 service（消 `submissions` 双写）
- 错误契约统一到 `AppException`（消 27 处 `HTTP_ERROR`、3 处 200-失败）
- DI 三风格统一为 `Depends(get_container)`
- **必须同步 `docs/api/`**，标注各端适配状态

### Phase 4 — 拆山（1-2 周，按需）

- `sqlite_db` 拆 `schema/*.sql` + `migrations/`，**引入 schema 版本号**替代幂等 if（根治 §1.2）
- `learner_state` 拆 3 条投影流水线 + 8 个指标纯函数
- `learner_event` 30 个方法改声明式 `EventSpec` 表 + backfill 独立成模块
- `learning_planner.generate` 拆 5 段
- `notice_extraction` 拆 `notice_rules` / `notice_llm` / `notice_dedupe`
- `forecast` 拆 `InputsCollector` + 5 strategy + `Cache`

### 建议顺序

**Phase 0 + Phase 1 先行**——没有 lint 和测试门禁，Phase 2/3 的大规模替换会很危险。

---

## 10. 验证状态声明

- ✅ 全部结论基于**静态代码阅读**，行号可复核
- ❌ **未运行任何测试、构建或 lint**（审查任务为只读）
- ⚠️ 唯一标注"需实测确认"的是 §3.2（500 响应是否缺 CORS / `x-request-id` 头），由 Starlette 中间件栈结构推导
- ⚠️ `except Exception`（约 195 处）与 schema class（418 个）计数因 grep 返回上限为近似值
- ⚠️ `backend/.env` 按仓库约束未读取，密钥类结论仅覆盖 `.env.example` 与源码字面量
