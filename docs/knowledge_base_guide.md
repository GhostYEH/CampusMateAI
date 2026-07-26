# 校园知识库使用指南

> 本文件说明如何向 CampusMate AI 后端导入、管理、检索校园资料,
> 以及演示资料的标识、冲突处理、过期文档等关键规则。
>
> 后端实现见 [`backend/app/services/knowledge_ingestion_service.py`](../backend/app/services/knowledge_ingestion_service.py)
> 与 [`backend/app/services/retrieval_service.py`](../backend/app/services/retrieval_service.py)。

---

## 目录

- [1. 支持的文件格式](#1-支持的文件格式)
- [2. 演示资料](#2-演示资料)
- [3. 导入文档](#3-导入文档)
- [4. 文档元数据](#4-文档元数据)
- [5. 检索优先级](#5-检索优先级)
- [6. 过期文档处理](#6-过期文档处理)
- [7. 冲突资料处理](#7-冲突资料处理)
- [8. 重建索引](#8-重建索引)
- [9. 删除文档](#9-删除文档)
- [10. 安全限制](#10-安全限制)
- [11. 常见问题](#11-常见问题)

---

## 1. 支持的文件格式

按解析优先级排列:

| 扩展名 | 解析方式 | 备注 |
|--------|----------|------|
| `.md` | 直接读取,Markdown 标题作为小节 | **推荐**(中文友好、可读性高) |
| `.txt` | 直接读取,空行分段 | 适合纯文本通知原文 |
| `.pdf` | `PyPDF2` 提取文本,按页分块 | 复杂排版可能丢失结构 |
| `.docx` | `python-docx` 提取段落与表格 | 仅支持 Word 2007+ |

可在 `backend/.env` 的 `ALLOWED_EXTENSIONS` 调整(逗号分隔,小写,不含点):

```env
ALLOWED_EXTENSIONS=md,txt,pdf,docx
```

> 不在本列表的文件类型会被后端拒绝,返回 `FILE_TYPE_NOT_ALLOWED`(415)。

---

## 2. 演示资料

后端内置 5 份 Markdown 演示资料,位于
[`backend/data/knowledge_base/demo/`](../backend/data/knowledge_base/demo/):

| 文件 | 主题 | 来源部门 |
|------|------|----------|
| `01_social_practice_guide.md` | 社会实践申请指南 | 校团委 |
| `02_comprehensive_evaluation.md` | 综合测评材料说明 | 学工处 |
| `03_scholarship_policy.md` | 校级奖学金申请办法 | 学生资助中心 |
| `04_course_add_drop.md` | 课程补退选流程 | 教务处 |
| `05_activity_registration_faq.md` | 活动报名常见问题 | 校园活动中心 |

### 关键标识

每份演示资料的**顶部**明确标注:

```markdown
> 演示资料,并非用户所在学校的真实现行制度。
> 用于演示 RAG 流程,实际使用时请替换为本校真实资料。
```

### 自动导入

启动后端时(默认 `AUTO_IMPORT_DEMO=true`),会自动检查演示资料是否已导入:
- 若知识库为空,自动导入 5 份演示资料
- 若已存在(按 `content_hash` 判定),跳过

在 `.env` 中关闭自动导入:

```env
AUTO_IMPORT_DEMO=false
```

### 演示资料 ≠ 真实资料

- 演示资料内容是**自然但虚构**的,不引用任何真实学校制度
- AI 导员回答时不会把演示资料冒充真实学校政策
- 客户端在 `sources` 中可通过 `is_official=false` 区分(演示资料默认非官方)
- 比赛演示中回答**应明确说明**这是演示资料

---

## 3. 导入文档

### 通过 API 上传

```bash
curl -X POST http://localhost:8000/api/v1/knowledge/documents \
  -F "file=@/path/to/scholarship_2026.md" \
  -F "title=2026年校级奖学金申请办法" \
  -F "source_department=学生资助中心" \
  -F "source_type=official_document" \
  -F "published_at=2026-07-01T00:00:00+08:00" \
  -F "version=v2.0" \
  -F "applicable_students=全体本科生" \
  -F "is_official=true"
```

详细字段见 [API 契约](api_contract.md#3-知识库-knowledge)。

### 通过文件系统

直接将文件放入 `backend/data/knowledge_base/`(非 `demo/` 子目录),
重启后端后通过 `POST /api/v1/knowledge/rebuild` 重建索引。
**注意**:此方式不会自动写入元数据(标题/部门等),建议优先用 API 上传。

### 处理流程

```
上传文件
  ↓
[1] 文件校验(类型/大小/文件名/空文件)
  ↓
[2] 计算 SHA256 内容哈希
  ↓
[3] 查重(命中 → 返回 DOCUMENT_ALREADY_EXISTS 409)
  ↓
[4] 解析为纯文本(按扩展名选择解析器)
  ↓
[5] 分块(按标题/段落/页码,保留元数据)
  ↓
[6] 写入 SQLite(documents + chunks 表)
  ↓
[7] 更新 BM25 索引
  ↓
返回 DocumentSummary
```

---

## 4. 文档元数据

每份文档保存以下元数据:

| 字段 | 说明 | 是否必填 |
|------|------|----------|
| `document_id` | 文档 ID(后端生成) | 自动 |
| `title` | 文档标题 | 否(留空则从内容首行/文件名推断) |
| `source_department` | 来源部门(如"教务处") | 否 |
| `source_type` | 来源类型(如"official_document"/"notice"/"faq") | 否 |
| `original_filename` | 原始文件名(经 sanitize) | 自动 |
| `content_hash` | SHA256 内容哈希 | 自动 |
| `published_at` | 发布时间(ISO 8601) | 否 |
| `updated_at` | 更新时间 | 否 |
| `effective_from` | 生效起始时间 | 否 |
| `effective_to` | 生效截止时间(过期判定依据) | 否 |
| `version` | 版本号(如 `v2.0`) | 否 |
| `applicable_students` | 适用对象(如"2024级本科生"/"全体本科生") | 否 |
| `is_official` | 是否官方资料 | 否(默认 false) |
| `is_expired` | 是否过期(基于 `effective_to` 自动计算) | 自动 |
| `file_size` | 文件大小(字节) | 自动 |
| `file_ext` | 扩展名 | 自动 |
| `imported_at` | 导入时间 | 自动 |

### 元数据缺失时的行为

- `title` 留空 → 从内容首行(若为 Markdown 标题)或文件名(去扩展名)推断
- `published_at` 留空 → 不影响检索,但优先级排序时此文档视为"时间未知"
- `effective_to` 留空 → 视为"未设定截止时间",`is_expired=false`
- `is_official` 留空 → 默认 `false`,检索优先级低于官方资料

---

## 5. 检索优先级

`retrieval_service.py` 中实现的排序规则:

```
1. 未过期(is_expired=false)  >  过期(is_expired=true)
2. 官方(is_official=true)    >  非官方(is_official=false)
3. 更新时间(updated_at)新    >  旧
4. BM25 相关度(relevance_score)高 > 低   ← 仅作为辅助
```

### 分块元数据保留

每个分块(chunk)继承所属文档的元数据,并额外保存:

- 所属文档标题(用于 `sources[].title`)
- 小节标题(Markdown `##` / `###`,用于 `sources[].section`)
- 段落位置或页码(用于 `sources[].section`)
- 来源部门(用于 `sources[].source_department`)
- 发布日期(用于 `sources[].published_at`)
- 版本(用于 `sources[].version`)
- 适用对象(用于 `sources[].applicable_students`)

### BM25 实现

- 中文分词: `jieba`(精确模式)
- BM25 算法: `rank_bm25.BM25Okapi`
- 与向量数据库**解耦**:不依赖 Pinecone/Milvus/Chroma 等外部服务
- 预留 hybrid 接口:后续可叠加向量检索(`retrieval_method=hybrid`)

---

## 6. 过期文档处理

### 判定规则

- 若 `effective_to < 当前时间` → `is_expired=true`
- 若 `effective_to` 留空 → `is_expired=false`(视为未设定截止)
- 后端每次启动时批量更新 `is_expired` 字段

### 检索行为

- 过期文档**不会默认作为最高优先级证据**
- 若知识库中只有过期文档,会在 `sources` 中显示,但:
  - `is_expired=true` 标记传给客户端
  - `evidence_level` 降级为 `medium` 或 `low`
  - 回答中会附加提示:"该资料已过期,请以最新官方通知为准"
- 客户端可据此显示"过期"徽章(暖橙色,不显眼)

### 示例

```json
{
  "document_id": "doc_2",
  "title": "2020年综合测评办法",
  "version": "v1.0",
  "effective_to": "2021-01-01T00:00:00+08:00",
  "is_expired": true,
  "excerpt": "综合测评由学业成绩、综合素质、社会实践三部分组成..."
}
```

AI 导员回答时会说:
> 根据《2020年综合测评办法》(已过期,仅作参考),综合测评由...组成。
> **建议查阅最新版综合测评办法**,该资料可能已不适用。

---

## 7. 冲突资料处理

### 冲突判定

当检索到 **2 份或以上内容矛盾** 的资料时(如同一事项的不同版本规定):

- `2024年奖学金办法` 要求"绩点 ≥ 3.5"
- `2026年奖学金办法` 要求"绩点 ≥ 3.7"

### 处理规则

1. **明确指出冲突**:回答中说明"存在多个版本的规定"
2. **展示两个来源**:在 `sources` 中并列展示,优先级按上述排序
3. **优先提示最新官方资料**:`is_official=true` 且 `updated_at` 最新
4. **建议人工复核**:`needs_human_confirmation=true`

### 回答模板

> 关于奖学金绩点要求,目前知识库中存在多份资料:
>
> - 根据《2024年校级奖学金申请办法》(校学生资助中心,v1.0):绩点要求 ≥ 3.5
> - 根据《2026年校级奖学金申请办法》(校学生资助中心,v2.0):绩点要求 ≥ 3.7
>
> 两份资料存在差异,**建议以 2026 年版本为准**(发布更新、官方资料)。
> 如需确认,请咨询校学生资助中心。

---

## 8. 重建索引

### 何时需要重建

- 删除文档后
- 修改了 BM25 参数(如 `k1` / `b`)
- 索引损坏或异常(`index_status=error`)
- 升级了分词器/解析器

### 通过 API

```bash
curl -X POST http://localhost:8000/api/v1/knowledge/rebuild
```

返回:

```json
{
  "success": true,
  "document_count": 5,
  "chunk_count": 42,
  "message": "索引重建完成"
}
```

### 通过脚本

```bash
cd backend
python scripts/rebuild_index.py
```

脚本会:
1. 读取 `.env` 配置
2. 初始化 SQLite
3. 重新解析所有已导入文档
4. 重建 BM25 索引
5. 输出统计信息

---

## 9. 删除文档

```bash
curl -X DELETE http://localhost:8000/api/v1/knowledge/documents/doc_1
```

返回:

```json
{"success": true, "document_id": "doc_1"}
```

删除行为:
- 从 SQLite 中删除 `documents` 与 `chunks` 表对应记录
- 自动触发索引重建
- 不会删除原始上传文件(避免误操作)
- 文档不存在时返回 `DOCUMENT_NOT_FOUND`(404)

---

## 10. 安全限制

### 文件类型

```env
ALLOWED_EXTENSIONS=md,txt,pdf,docx
```

不在列表的类型返回 `FILE_TYPE_NOT_ALLOWED`(415)。

### 文件大小

```env
MAX_UPLOAD_MB=10
```

超过限制返回 `FILE_TOO_LARGE`(413)。

### 文件名安全

后端 `sanitize_filename` 处理:
- 拒绝 `../`、绝对路径(`/`、`\` 开头)
- 拒绝空文件名
- 仅保留 `[a-zA-Z0-9_\-\.\u4e00-\u9fff]`
- 不安全时返回 `FILE_NAME_UNSAFE`(400)

### 空文件

- 文件大小为 0 字节 → 拒绝
- 解析后文本为空(如 PDF 仅含图片)→ 拒绝,返回 `NOTICE_UNPARSEABLE`(422)

### 重复文件

- 基于 SHA256 内容哈希
- 重复上传返回 `DOCUMENT_ALREADY_EXISTS`(409)
- 不会覆盖已有文档

### 路径穿越

- 上传文件名不会被原样使用
- 所有文件保存到 `data/knowledge_base/{uuid}_{sanitized_filename}`
- 攻击者无法通过文件名访问服务器其他路径

---

## 11. 常见问题

### Q1: 上传 PDF 后检索不到内容?

A: 可能原因:
1. PDF 是扫描件(图片),`PyPDF2` 无法提取文本 → 后端拒绝并返回 422
2. PDF 加密 → 同上
3. 文本提取成功但中文过少 → 检查 `chunk_count` 是否为 0

解决:使用 `.docx` 或 `.md` 重新制作资料。

### Q2: 演示资料可以删除吗?

A: 可以。通过 `DELETE /api/v1/knowledge/documents/{document_id}` 删除。
但下次启动时若 `AUTO_IMPORT_DEMO=true` 且知识库为空,会再次自动导入。
如需永久关闭,设置 `AUTO_IMPORT_DEMO=false`。

### Q3: 如何区分"官方资料"与"非官方"?

A: 上传时设置 `is_official=true`。客户端在 `sources[].is_official` 中读取:
- `true` → 显示"官方"徽章(青蓝色)
- `false` → 不显示徽章或显示"参考"

### Q4: 同一份文档的不同版本如何处理?

A: 上传时填写 `version` 字段(如 `v1.0` / `v2.0`)。检索时:
- 两个版本都会被检索到
- 排序按 `updated_at` 新 > 旧
- 优先级冲突时触发 [冲突资料处理](#7-冲突资料处理) 规则

### Q5: 演示资料会污染真实知识库吗?

A: 不会,只要:
- 演示资料 `is_official=false`
- 真实资料上传时设置 `is_official=true`
- 检索排序中官方资料优先级更高

但建议正式使用时:
1. 删除所有演示资料
2. 设置 `AUTO_IMPORT_DEMO=false`
3. 上传真实学校资料

### Q6: 知识库可以多人共享吗?

A: 当前实现是单租户模式,所有请求共享同一知识库。
后续接入 JWT 后会支持多用户独立知识库(预留扩展)。

### Q7: BM25 检索的中文准确度如何?

A: BM25 基于 `jieba` 精确模式分词,对常见校园术语(奖学金/综测/实践学分等)
检索效果良好。但对同义词(如"奖学金" vs "助学金")、口语化表达(如"综测" vs "综合测评")
命中率较低。后续可叠加向量检索改善(`retrieval_method=hybrid`)。

### Q8: 如何备份知识库?

A: 备份两个部分:
1. SQLite 数据库: `backend/data/app.db`
2. 原始上传文件: `backend/data/knowledge_base/`(除 `demo/` 外)

恢复时:
1. 还原 `app.db` 与 `data/knowledge_base/` 文件
2. 运行 `python scripts/rebuild_index.py` 重建索引
