# 多 worker / 多实例就绪清单

> 结论先行：**当前部署是单服务进程，下列问题都不会触发。**
> 这份清单回答的是"如果要把后端水平扩展，需要先解决什么"。
> 核对时间：2026-09-20。所有条目都来自实际代码，不是推测。

## 当前部署形态（证据）

- 仓库内**所有**启动入口都是 `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`，
  **没有 `--workers`**：`start_backend.bat`、`README.md`(×3)、`backend/README.md`、
  `docs/DEVICE_TEST_CHECKLIST.md`；
- 仓库内没有 gunicorn / Dockerfile / docker-compose / K8s manifest；
- 因此只有一个服务进程，进程内状态天然一致。

**触发条件**：`--workers N`、gunicorn 多 worker、或 K8s 多副本 —— 任一出现，下面的条目立刻生效。

## 进程内状态清单

| 组件 | 进程内状态 | 多 worker 下的行为 | 严重性 |
| --- | --- | --- | --- |
| `ModelShadowRunner._circuits` | 熔断失败计数 / `opened_at` / 探测权 / 代次 | 阈值不聚合（打开延迟 ≤ N 倍）；`canary_gate` 只反映当前 worker（同一用户在 A 放行、B 拒绝）；冷却结束后 N 个 worker 同时探测 | **中**（影子/金丝雀非关键路径） |
| `RetrievalService` BM25 索引 | `_bm25` / `_chunks` / `_doc_by_id` / `_needs_rebuild` | **新入库的资料在未重建的 worker 上检索不到**，结果随路由漂移；内存占用 ×N | **高**（影响检索正确性） |
| `chaoxing._sync_locks` | 每用户 `threading.Lock` | 同一用户的并发同步落在不同 worker 时**不再互斥**，`409 sync_in_progress` 不再可靠，会真的并发触网同步 | **中** |
| `container._container` | 容器单例 | 设计如此，无影响 | — |
| `config.get_settings` `@lru_cache` | 配置缓存 | 只读，无影响 | — |
| `edu._ADAPTERS` | 4 个适配器实例 | 已核实**无实例状态**（只持有 parser/validator），无影响 | — |
| 教育会话 | `EncryptedSqliteEduSessionStore`（`EDU_SESSION_STORE=auto` 时**生产**走加密 SQLite） | 生产已跨进程安全；但 `auto` 在**非生产**环境是 `memory` —— 那种环境下多 worker 会丢会话（仅影响 dev/test） | — |
| `AgentWorker` / `AdaptiveReplanningWorker` | 无内存状态 | 用**数据库租约 + CAS** 协调，已按多 worker 设计 | — |
| `magicclass result_store` | 进程内线程锁 | 真正的互斥靠文件 `O_CREAT\|O_EXCL` 预占 + 租约，跨进程安全 | — |
| `sqlite_db` `RLock` | 进程内连接守卫 | 跨进程由 SQLite 文件锁 + `timeout=30` 负责 | — |

## 需要修的两项（都需要授权，均未实施）

### 1) 检索索引跨 worker 失效（严重性：高）

**现状**：索引重建发生在
`container` 启动时（每进程一次）、知识库写路由（`api/routes/knowledge.py` ×4、
`knowledge_ingestion_service.py`）、以及 **`GET /api/v1/health`**。
前三者只影响**执行写入的那个进程**，没有任何跨进程失效信号。

**后果**：worker A 入库一份资料后，B..N 仍服务旧索引；用户刷新时"有时能搜到、有时搜不到"。
唯一偶然的缓解是 `GET /health` 会重建索引 —— 但那只在负载均衡把探测打到该 worker 时才生效，
而且健康探测频率下每次全量重建 BM25 本身是浪费。

**修复类别**（需授权，二选一）：

- **索引版本号（推荐）**：加一张 `knowledge_index_versions` 表（或复用既有表的一个单调列），
  写入后自增；`RetrievalService` 缓存版本号，读路径先比一次版本、落后才重建。
  新增一张表 + 每次读多一次轻量查询。
- **外部共享索引**：把 BM25 索引放到 Redis / 独立的检索服务。成本更高，但内存也不再 ×N。

顺带建议（无论是否多 worker）：`GET /health` 每次全量重建索引应收敛为
"索引缺失才重建"，把新鲜度交给显式失效 —— 但这会去掉上面那个偶然的跨进程刷新，
所以必须与索引版本号一起做，不能单独改。

### 2) 熔断状态跨 worker 不共享（严重性：中）

最小可行方案：新增 `model_circuit_state` 表
（`capability_name` 主键 + `failures` / `opened_at` / `probe_owner` / `probe_expires_at` / `generation`），
用条件 UPDATE 做 CAS 占用探测权，`probe_expires_at` 防止实例崩溃后永久卡死。
每次放行/记账多一次数据库往返（SQLite 本地约 0.1–1ms）。

**注意**：本仓库已经有一模一样的先例 —— `adaptive_interventions.claim_decision` 就是
"owner + 过期租约 + CAS"，`adaptive_replan_decisions` 也是。实现时应当复用同一套写法，
不要发明第二套租约语义。

### 3) Chaoxing 同步互斥（严重性：中）

`_sync_locks` 是每进程的。要么改成数据库侧的"用户同步租约"（与 `claim_decision` 同款），
要么明确接受多 worker 下同一用户可能并发同步（需要确认下游幂等键足以兜住重复）。

## 触发重新评估

- 把 `--workers` 调到 > 1、换成 gunicorn、或部署多副本；
- 知识库写入频率上升（索引陈旧窗口变长）；
- 影子评测/金丝雀从"只读展示"升级为影响生产决策。

## 相关

- 熔断并发语义（单进程内）与门禁/探测权所有权：`docs/learner-model-demo.md`
  的「熔断与探测权」「并发语义：熔断代次」「线程模型」三节。
