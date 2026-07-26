# CampusMate AI Backend

> Python FastAPI 后端 — 校园通知结构化抽取 / 校园知识库 RAG 问答

本后端为 Flutter 应用 [CampusMate AI](../README.md) 提供真实业务能力,Mock 模式与之并存可切换。

## 当前能力

| 能力 | 实现状态 | 说明 |
|------|----------|------|
| 健康检查 | 已实现 | `GET /api/v1/health` 返回运行模式、知识库状态、LLM 可用性 |
| 通知结构化抽取 | 已实现 | LLM 优先 + 规则降级,缺少年份/对象/方式时标记 `needs_confirmation` |
| 校园知识库导入 | 已实现 | 支持 Markdown / TXT / PDF / DOCX,基于内容哈希去重 |
| BM25 中文检索 | 已实现 | jieba 分词 + rank_bm25,与向量数据库解耦,预留 hybrid 接口 |
| 知识库状态 | 已实现 | 文档/分块数量、索引状态、检索方式 |
| RAG 问答 | 已实现 | SSE 流式输出 + 来源引用 + 冲突提示 + 无依据时人工兜底 |
| LLM 降级 | 已实现 | 未配置或调用失败时返回检索摘要模式,不返回错误 |
| 演示资料 | 已内置 | 5 份标注"演示资料"的 Markdown 文档 |

## 不在本后端范围

- JWT 认证与多用户系统
- PostgreSQL / Redis / Docker
- 真实学校内部系统接入
- CNN 训练与 LiteRT 推理
- 向量数据库(预留接口)

## 目录结构

```
backend/
├── app/
│   ├── main.py                   # FastAPI 应用入口 + lifespan
│   ├── api/
│   │   ├── router.py            # 路由聚合(prefix /api/v1)
│   │   └── routes/              # 各业务路由
│   │       ├── health.py        # GET /health
│   │       ├── notices.py       # POST /notices/extract
│   │       ├── knowledge.py     # 文档 CRUD / rebuild / status
│   │       └── counselor.py     # POST /counselor/chat (SSE)
│   ├── core/                    # 配置/异常/日志/安全
│   ├── database/                # SQLite 包装(线程安全,内存模式共享连接)
│   ├── models/                  # 数据行模型(DocumentRow/ChunkRow/RetrievedChunk)
│   ├── repositories/            # DocumentRepository
│   ├── schemas/                 # Pydantic 请求/响应模型
│   ├── services/
│   │   ├── notice_extraction_service.py  # LLM + 规则抽取
│   │   ├── knowledge_ingestion_service.py # 文件解析→分块→入库
│   │   ├── retrieval_service.py          # BM25 检索 + 元数据排序
│   │   ├── rag_service.py                # RAG 编排 + SSE 流式
│   │   └── llm/                          # LLM 抽象 + OpenAI 兼容实现
│   └── utils/                   # 文件解析 / 中文分词
├── data/
│   ├── knowledge_base/
│   │   └── demo/                # 5 份演示资料 Markdown
│   └── app.db                   # SQLite 数据库文件(运行后自动生成)
├── scripts/
│   ├── rebuild_index.py         # 重建索引命令行
│   ├── check_llm_provider.py    # LLM 连通性检查(支持 Fake Provider)
│   ├── evaluate_retrieval.py    # 检索评测(Hit@1/Hit@3/MRR/拒答率/失败样例)
│   └── _debug_retrieval.py      # 检索调试辅助脚本(不参与 CI)
├── tests/                       # 112 个 pytest 测试
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

### 演示资料

`data/knowledge_base/demo/` 内置 5 份 Markdown,启动时自动导入(可在 `.env` 设置 `AUTO_IMPORT_DEMO=false` 关闭):

1. 社会实践申请指南
2. 综合测评材料说明
3. 校级奖学金申请办法
4. 课程补退选流程
5. 活动报名常见问题

每份资料顶部明确标注:**"演示资料,并非用户所在学校的真实现行制度"**。

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

未配置 LLM(`LLM_PROVIDER=none`)时:

| 接口 | 降级行为 |
|------|----------|
| `/notices/extract` | 规则抽取,返回 `extractor_mode="rules"` |
| `/counselor/chat` | 检索摘要 + 模板整理,标注 `evidence_level="retrieval_only"` |
| `/health` | `llm_available=false`, `fallback_enabled=true` |

降级模式保证比赛演示无网络/无 LLM Key 时仍可用。

## API 契约

完整请求/响应字段、错误码、SSE 事件格式参见 [`../docs/api_contract.md`](../docs/api_contract.md)。

## 知识库使用指南

导入格式、冲突处理、过期文档等参见 [`../docs/knowledge_base_guide.md`](../docs/knowledge_base_guide.md)。

## 安全边界

- 后端不保存、不记录 LLM API Key(仅运行时读取环境变量)
- 日志不记录完整用户对话内容、摄像头数据、表情数据
- 上传文件名经过 `sanitize_filename`,防止路径穿越
- 文件类型/大小/空文件/重复内容均校验
- RAG 不得编造学校政策/截止时间/办理地点/材料要求

## 已知限制

- SQLite 单机文件存储,不支持多实例横向扩展(预留 PostgreSQL 迁移)
- BM25 关键词检索 + 校园术语同义词扩展(对称),未引入向量数据库 / Embedding 模型,语义检索能力有限
- 演示资料非真实学校制度,回答仅作演示
- 没有用户系统(单租户匿名模式),所有请求共享同一知识库
- 扫描型 PDF 不支持 OCR(仅提取文本层)
- CNN 仍为 Mock(后端不涉及 CNN 推理,此限制仅说明项目整体状态)

## 下一阶段

- 接入 PostgreSQL + JWT 认证
- 引入向量检索 + Embedding 模型(中文友好)
- 接入真实学校通知源
- 增加 Redis 缓存与限流
