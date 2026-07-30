# CampusMate AI Backend

> Python FastAPI 后端 — 校园通知结构化抽取 / 校园知识库 RAG 问答 /
> **教师-课程-班级-学生协同平台**

本后端为原生 Android(Kotlin Compose)移动端与 Vue 3 Web 前端提供真实业务能力。
**正式 Release 不包含任何"演示模式"或 Mock 业务切换开关**;所有教师、学生、课程、班级、通知、任务、提交、已读状态和统计数据均来自真实 FastAPI 接口与持久化数据库。

## 当前能力

| 能力 | 实现状态 | 说明 |
|------|----------|------|
| 健康检查 | 已实现 | `GET /api/v1/health` 返回运行模式、知识库状态、LLM 可用性 |
| 通知结构化抽取 | 已实现 | LLM 优先 + 规则降级,缺少年份/对象/方式时标记 `needs_confirmation` |
| 校园知识库导入 | 已实现 | 支持 Markdown / TXT / PDF / DOCX,基于内容哈希去重 |
| BM25 中文检索 | 已实现 | jieba 分词 + rank_bm25,与向量数据库解耦,预留 hybrid 接口 |
| 知识库状态 | 已实现 | 文档/分块数量、索引状态、检索方式 |
| RAG 问答 | 已实现 | SSE 流式输出 + 来源引用 + 冲突提示 + 无依据时人工兜底 |
| LLM 降级 | 已实现 | 未配置或调用失败时返回检索摘要模式(明确标注,不伪装 LLM 结果) |
| 测试环境资料 | 已内置 | 5 份标注 `is_demo=true` 的 Markdown,仅 dev/test 启动时导入 |
| **JWT 认证** | **已实现** | access + refresh token,PBKDF2 密码哈希 |
| **多角色 RBAC** | **已实现** | student / teacher / admin 三角色,后端真实执行 |
| **课程 / 班级 / 选课** | **已实现** | 教师-课程-班级-学生协同,邀请码加入 |
| **通知发布与已读回执** | **已实现** | 草稿 / 发布 / 已读统计 |
| **任务发布与提交** | **已实现** | 草稿 / 提交 / 重新提交 / 逾期 / 评分 |
| **附件上传** | **已实现** | 安全校验 + 路径穿越防御 |
| **教师 / 学生工作台** | **已实现** | 聚合 SQL,一次返回所有摘要,无写死数字 |
| **AI 导员上下文融合** | **已实现** | 任务/通知/课程/班级 可注入 RAG,草稿对学生不可见 |
| **数据库迁移** | **已实现** | 旧库兼容 + 幂等 |
| **production 强约束** | **已实现** | `app_env=production` 禁止启用测试开关(详见下文) |

## 不在本后端范围

- PostgreSQL / Redis / Docker(SQLite 单机,预留 PG 迁移)
- 真实学校内部系统接入
- CNN 训练与 LiteRT 推理
- 向量数据库(预留接口)
- 用户注册接口(生产由管理员创建;dev/test 可通过 seeder 或仓库创建验收账号)
- 附件下载接口(当前仅上传 + 列表)
- 任务提醒推送(由客户端轮询 dashboard)
- **任何"演示模式 / 一键重置演示数据 / 比赛演示数据恢复"等生产接口**(已下线)

## 目录结构

```
backend/
├── app/
│   ├── main.py                   # FastAPI 应用入口 + lifespan
│   ├── api/
│   │   ├── router.py            # 路由聚合(prefix /api/v1)
│   │   ├── deps.py              # 认证依赖 / RBAC / 权限校验
│   │   └── routes/              # 各业务路由
│   │       ├── health.py        # GET /health
│   │       ├── notices.py       # POST /notices/extract
│   │       ├── knowledge.py     # 文档 CRUD / rebuild / status
│   │       ├── counselor.py     # POST /counselor/chat (SSE)
│   │       ├── auth.py          # POST /auth/login / refresh / logout / me
│   │       ├── courses.py       # 课程 CRUD
│   │       ├── classes.py       # 班级 CRUD / 加入 / 成员管理
│   │       ├── announcements.py # 通知 CRUD / 发布 / 已读
│   │       ├── assignments.py   # 任务 CRUD / 发布 / 统计 / 学生状态
│   │       ├── submissions.py   # 提交 CRUD / 评分 / 附件
│   │       └── dashboard.py     # 教师 / 学生工作台
│   ├── core/                    # 配置 / 异常 / 日志 / 安全(JWT/密码/文件名)
│   ├── database/                # SQLite 包装(线程安全,内存模式共享连接)
│   ├── models/                  # 数据行模型(含多角色 multi_role.py)
│   ├── repositories/            # DocumentRepository + multi_role_repository.py
│   ├── schemas/                 # Pydantic 请求/响应模型(含 multi_role.py)
│   ├── services/
│   │   ├── notice_extraction_service.py  # LLM + 规则抽取
│   │   ├── knowledge_ingestion_service.py # 文件解析→分块→入库
│   │   ├── retrieval_service.py          # BM25 检索 + 元数据排序
│   │   ├── rag_service.py                # RAG 编排 + SSE 流式
│   │   ├── demo_seeder.py                 # 多角色演示数据 seeding
│   │   ├── container.py                  # ServiceContainer(依赖注入)
│   │   └── llm/                          # LLM 抽象 + OpenAI 兼容实现
│   └── utils/                   # 文件解析 / 中文分词
├── data/
│   ├── knowledge_base/
│   │   └── demo/                # 5 份演示资料 Markdown
│   ├── submission_attachments/  # 学生提交附件(运行后自动生成)
│   └── app.db                   # SQLite 数据库文件(运行后自动生成)
├── scripts/
│   ├── rebuild_index.py         # 重建索引命令行
│   ├── check_llm_provider.py    # LLM 连通性检查(支持 Fake Provider)
│   └── evaluate_retrieval.py    # 检索评测(Hit@1/Hit@3/MRR/拒答率/失败样例)
├── tests/                       # pytest 测试(含多角色测试)
├── .env.example
├── pytest.ini
├── requirements.txt
└── README.md
```

## 快速开始

### 1. 安装依赖

```bash
cd backend
python -m venv .venv

# Windows PowerShell(推荐)
.venv\Scripts\Activate.ps1
# 若提示执行策略受限,可临时放开(仅当前会话):
# Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Windows cmd / Git Bash
.venv\Scripts\activate.bat

# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
```

> Windows 上若 jieba / PyPDF2 / python-docx 安装失败,可加 `--no-build-isolation`。

### 2. 配置环境

```bash
cp .env.example .env
# 默认无需 LLM 即可运行(规则模式 + 检索摘要模式)
```

如需启用 LLM 抽取/回答,编辑 `.env`:

```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.deepseek.com/v1   # 或其它兼容端点
LLM_API_KEY=sk-xxxxxxxxxxxx
LLM_MODEL=deepseek-chat
```

### 3. 启动后端

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启动后访问:
- 健康检查: http://localhost:8000/api/v1/health
- Swagger 文档: http://localhost:8000/docs

### 4. 运行测试

```bash
pytest
```

### 5. 重建索引

```bash
python scripts/rebuild_index.py
```

### 6. LLM 连通性检查与检索评测

```bash
# LLM Provider 连通性检查 — 验证 LLM 配置完整性 / 连接可用性 / 响应耗时
# 未配置 LLM 时返回 not_enabled 并退出码 0,不阻断后续操作
python scripts/check_llm_provider.py
python scripts/check_llm_provider.py --json   # JSON 输出(便于 CI 解析)

# 检索评测 — 真实调用 RetrievalService,计算 Hit@1 / Hit@3 / MRR / 正确拒答率 / 错误接受率
python scripts/evaluate_retrieval.py
python scripts/evaluate_retrieval.py --json   # JSON 输出
```

> 检索评测的 fixtures(44 条样例)、指标含义与最新结果说明见 [`../docs/retrieval_evaluation.md`](../docs/retrieval_evaluation.md)。
> 未配置 LLM 时,系统仍使用规则抽取与检索摘要模式正常运行,详见下方"降级模式"。
>
> **`retrieval_summary` vs `llm_rag` 区别**:
> - `retrieval_summary`:LLM 不可用时,直接拼接 BM25 检索段落 + 来源元数据,标注 `evidence_level="retrieval_only"`,不调用 LLM
> - `llm_rag`:LLM 可用时,基于检索段落调用 LLM 生成自然语言回答,标注 `evidence_level="llm_rag"`
> - 两者都严格基于知识库,不编造政策/截止时间/材料要求

## 通知抽取说明

`POST /api/v1/notices/extract` 接受中文校园通知原文,返回结构化 JSON。

**LLM 模式**(`LLM_PROVIDER=openai_compatible` 且 API Key 已配置):
- 调用 LLM 输出结构化 JSON
- 失败/超时自动降级到规则模式

**规则模式**(默认,无 LLM 也能用):
- 正则匹配:截止日期、面向对象、材料、提交方式、地点
- 支持缺失年份推断(基于 `published_at` 或当前时间)
- 不确定时设置 `needs_confirmation=true` 并在 `warnings` 中说明
- 永不编造通知中不存在的材料

规则模式已覆盖的语法:
- `2026年7月30日前` / `7月30日前` / `截止时间为...` / `截至...`
- `第8周周五17:00` / `本周五` / `下周一`
- `提交至/交到/上传到/通过...提交`
- `2024级本科生` / `XX学院学生` / `XX专业` / `XX班`
- `行政楼XX办公室` / `学院办公室` / `学生事务中心` 等
- 申请表/证明材料/成绩单/开题报告/创新创业材料 等 20+ 材料关键词

## 知识库说明

### 测试环境资料

`data/knowledge_base/demo/` 内置 5 份 Markdown,**仅 dev/test 启动时**通过 `AUTO_IMPORT_DEMO=true` 显式导入(默认关闭,production 已被 config 校验拦截):

1. 社会实践申请指南
2. 综合测评材料说明
3. 校级奖学金申请办法
4. 课程补退选流程
5. 活动报名常见问题

每份资料顶部明确标注:**"测试环境资料,并非用户所在学校的真实现行制度"**,数据库中以 `is_demo=true` 区分。
production 环境下,这些资料不会进入生产数据。

### 上传文档

```bash
curl -X POST http://localhost:8000/api/v1/knowledge/documents \
  -F "file=@doc.md" \
  -F "title=测试文档" \
  -F "source_department=XX学院" \
  -F "is_official=true"
```

支持格式: `.md .txt .pdf .docx`(可在 `ALLOWED_EXTENSIONS` 调整)
单文件上限: 10 MB(可在 `MAX_UPLOAD_MB` 调整)

### 检索排序

文档与分块的元数据用于优先级排序(元数据加权合计上限 +0.30,不覆盖明显更高的语义相关性):

1. 未过期 > 过期(+0.15)
2. 官方 > 非官方(+0.10)
3. 新鲜度 bonus:30 天内满额 +0.05,30~365 天线性衰减,超过 365 天归零
4. BM25 相关度作为主体分(标题/小节字段加权 ×2,正文 ×1)
5. 校园术语同义词对称扩展(奖助学金↔奖学金、暑期实践↔社会实践、政策↔办法 等)
6. 短查询回退:1 token 短查询 min_overlap=1,2 token 短查询 min_overlap=2,含未知 token 时 +1
7. 多路召回:复杂查询按标点拆分为子查询,合并去重

## RAG 问答说明

`POST /api/v1/counselor/chat` 支持 SSE 流式输出,严格基于知识库回答:

- 检索证据不足 → `sources=[]`, `needs_human_confirmation=true`,回答"建议咨询辅导员"
- 检索到冲突资料 → 明确指出冲突,展示两份来源,建议人工复核
- 过期资料 → 降权但仍可显示,标注 `is_expired=true`
- LLM 不可用 → 检索摘要模式,直接拼接关键段落,标注"检索摘要模式"
- 恶意 Prompt → 系统消息强制约束"只能基于知识库回答",不绕过

## 降级模式

未配置 LLM(`LLM_PROVIDER=none`)时,接口显式降级,并**明确标注**返回结果来自规则或检索摘要,不伪装为 LLM 输出:

| 接口 | 降级行为 | 标注字段 |
|------|----------|----------|
| `/notices/extract` | 规则抽取 | `extractor_mode="rules"` |
| `/counselor/chat` | 检索摘要 + 模板整理 | `evidence_level="retrieval_only"`, `mode="retrieval_summary"` |
| `/health` | 真实返回 `llm_available=false`, `fallback_enabled=true` | — |

降级模式保证无 LLM Key 时仍可运行真实业务流程,但绝不返回伪造的 LLM 结果或 Mock 业务数据。

## API 概览

完整请求/响应字段、错误码、SSE 事件格式、RBAC 权限矩阵参见 [`../docs/api_overview.md`](../docs/api_overview.md)。

## 知识库使用指南

导入格式、冲突处理、过期文档等参见 [`../docs/knowledge_base_guide.md`](../docs/knowledge_base_guide.md)。

## 安全边界

- 后端不保存、不记录 LLM API Key(仅运行时读取环境变量)
- 日志不记录完整用户对话内容、摄像头数据、表情数据
- 上传文件名经过 `sanitize_filename`,防止路径穿越
- 文件类型/大小/空文件/重复内容均校验
- RAG 不得编造学校政策/截止时间/办理地点/材料要求
- 密码仅以 PBKDF2-HMAC-SHA256 哈希存储,日志不记录 token 与密码
- 错误响应不泄露用户名是否存在(`INVALID_CREDENTIALS` 统一返回)
- 教师只能访问与教学直接相关的学生信息,不得跨课程读取(详见下方 RBAC 矩阵)

## 多角色协同平台

### 角色与权限矩阵

| 资源 | student | teacher | admin |
|------|---------|---------|-------|
| 课程 — 列表/详情 | 仅自己已加入班级所属课程 | 仅自己负责的课程 | 全部 |
| 课程 — 创建/修改 | ❌ | ✅(仅自己负责的) | ✅ |
| 班级 — 列表/详情 | 仅自己加入的 | 仅自己课程下的 | 全部 |
| 班级 — 创建/修改/成员管理 | ❌ | ✅(仅自己课程) | ✅ |
| 班级 — 加入(邀请码) | ✅ | ❌ | ❌ |
| 通知 — 查看 | 已加入班级且已发布 | 自己班级内 | 全部 |
| 通知 — 创建/发布 | ❌ | ✅(自己班级) | ✅ |
| 通知 — 已读回执 | ✅(自己) | 查看(自己班级聚合) | 查看 |
| 任务 — 查看 | 已加入班级且已发布 | 自己班级内 | 全部 |
| 任务 — 创建/发布/关闭 | ❌ | ✅(自己班级) | ✅ |
| 任务 — 提交 | ✅(自己,只能自己) | ❌ | ❌ |
| 任务 — 学生状态 | 仅自己 | 自己班级(全部学生) | 全部 |
| 提交 — 查看 | 仅自己 | 自己班级所有学生 | 全部 |
| 提交 — 修改 | 仅自己(未截止) | ❌ | ❌ |
| 提交 — 评分/评论 | ❌ | ✅(自己课程) | ✅ |
| 工作台 | `/student/dashboard` | `/teacher/dashboard` | 两者均可 |

### 教师可见的学生信息边界(强制)

允许:姓名 / 学号 / 学院 / 专业 / 年级 / 所属班级 / 通知已读状态 / 任务提交状态 / 提交时间 /
是否逾期 / 成绩 / 教师评论 / 当前课程完成率。

**禁止** 教师访问:学生私人 AI 对话、私人待办、个人学习陪伴记录、摄像头画面、表情识别结果、
与当前课程无关的信息、密码和 token。详见
[`../docs/api_overview.md` §RBAC 权限矩阵](../docs/api_overview.md#rbac-权限矩阵简表)。

### AI 导员上下文融合

`POST /api/v1/counselor/chat` 新增可选上下文字段 `course_id` / `class_id` / `assignment_id` /
`announcement_id`。携带任一字段时必须携带有效 access token,后端会真实校验访问权限,
草稿对学生不可见。详见
[`../docs/api_overview.md` §4 AI 导员](../docs/api_overview.md#4-ai-导员-counselor)。

### 验收账号(dev/test 环境)

> 正式 Release 不提供任何"演示账号"或绕过认证的特殊账号。
> 验收账号为**普通用户**,走完整真实业务流程(JWT 登录 / RBAC 校验 / 真实 SQL),
> 不持有任何特殊权限或 Mock 数据开关。

dev/test 环境可通过 `AUTO_SEED_DEMO_USERS=true` 显式启用 seeding(默认关闭,
production 已被 config 校验拦截):

| 用户名 | 密码 | 角色 |
|--------|------|------|
| `teacher_demo` | `Demo123456` | teacher |
| `student_demo` | `Demo123456` | student |
| `admin_demo` | `Demo123456` | admin |

完整 seeding 规模:2 教师 / 3 课程 / 4 班级 / 31 学生 / 6 通知 / 8 任务,
覆盖已读/未读/已交/未交/逾期/已评分等不同状态。所有 seeding 数据明确标注
(display_name 含"(演示)"后缀,文档 `is_demo=true`),不冒充真实学校数据。
正式生产环境中,验收账号应由管理员通过真实业务流程在数据库中创建。

### 性能策略

- 教师统计使用聚合 SQL(`COUNT` / `GROUP BY`),不逐个学生循环查询
- `student-status` 接口支持分页、状态筛选(`read_status` / `submission_status`)与姓名/学号搜索
- `dashboard` 接口一次返回所有摘要,避免客户端连续请求十几个接口
- 附件列表不返回文件内容,仅返回元数据
- `Enrollment` / `Receipt` / `Submission` 写入使用 `INSERT OR IGNORE` / 唯一约束防重复
- 长列表均分页,默认 page_size=20,最大 100
- SQLite 启用 WAL 模式,写操作避免长时间持锁

### 数据库迁移

- 沿用现有 SQLite 封装,不重建 `app.db`,不破坏知识库 / 通知抽取 / RAG 表
- 新增多角色表(users / courses / class_groups / enrollments / announcements /
  announcement_read_receipts / assignments / submissions / submission_attachments)
- 索引: `users.username` / `users.student_number` / `users.teacher_number` /
  `courses.teacher_id` / `class_groups.course_id` / `enrollments.class_group_id` /
  `enrollments.user_id` / `announcements.class_group_id` / `assignments.class_group_id` /
  `assignments.deadline` / `submissions.assignment_id` / `submissions.student_id` /
  `submissions.status` / `read_receipts.announcement_id` / `read_receipts.student_id`
- 旧库迁移幂等:重复启动不重复创建数据,不破坏索引

### 附件限制

- 文件类型:与知识库一致(`.md .txt .pdf .docx`,可在 `ALLOWED_EXTENSIONS` 调整)
- 单文件上限: 10 MB(`MAX_UPLOAD_MB`)
- 文件名: `sanitize_filename` 处理,拒绝路径穿越(`../` / 绝对路径等)
- 空文件拒绝,文件大小必须 > 0
- 附件列表不返回文件内容,仅返回元数据(`original_filename` / `mime_type` / `size_bytes` 等)

### 当前限制

- 附件下载接口尚未实现(当前仅上传 + 列表)
- 用户注册接口未实现(生产由管理员创建)
- 任务提醒推送未实现(由客户端轮询 dashboard)
- 多角色权限测试不覆盖 SSE 流式 AI 上下文(仅覆盖非流式)

## 正式 Release 强约束

正式 Release 不得启用任何 Mock 业务开关。`Settings._normalize` 在 `app_env=production` 下强制校验:

| 配置 | dev/test 默认 | production 强制 |
|------|--------------|------------------|
| `AUTO_SEED_DEMO_USERS` | False | **True 抛 ValidationError** |
| `AUTO_IMPORT_DEMO` | False | **True 抛 ValidationError** |
| `DEMO_MODE` / `USE_MOCK_BACKEND` / `MOCK_BACKEND` | (不存在) | 扫描测试 `test_no_demo_mode_or_mock_backend_flags_in_app` 保证不引入 |

新增 13 个强约束测试(`tests/test_production_hardening.py`):
- production 禁用 AUTO_SEED / AUTO_IMPORT(2 个)
- 生产代码无 Mock 业务开关(1 个)
- `/knowledge/restore-demo` 接口已下线(1 个)
- `/knowledge/manage/restore_demo` action 已下线(1 个)
- 合法数据管理 action 仍可用(1 个)
- 学生工作台空数据返回真实 0(1 个)
- 教师工作台数字与 SQL 聚合一致(1 个)
- 后端不可用返回真实 401/403,不返回 Mock 数据(3 个)
- production 启动不调用 demo_seeder(1 个)
- production 启动不导入测试环境资料(1 个)

## 已知限制

- SQLite 单机文件存储,不支持多实例横向扩展(预留 PostgreSQL 迁移)
- BM25 关键词检索 + 校园术语同义词扩展(对称),未引入向量数据库 / Embedding 模型,语义检索能力有限
- 测试环境资料非真实学校制度,仅用于 dev/test 验证检索/RAG 链路
- 扫描型 PDF 不支持 OCR(仅提取文本层)
- CNN 仍为 Mock(后端不涉及 CNN 推理,此限制仅说明项目整体状态)
- 多角色附件仅上传 + 列表,未实现下载接口
- 多角色权限测试不覆盖 SSE 流式 AI 上下文

## 下一阶段

- 接入 PostgreSQL + Redis(从 SQLite 迁移)
- 引入向量检索 + Embedding 模型(中文友好)
- 接入真实学校通知源
- 增加限流与缓存
- 实现附件下载接口
- 增加用户注册流程
