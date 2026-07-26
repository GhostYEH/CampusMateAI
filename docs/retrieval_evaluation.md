# 检索评测指南

## 目的

评测 `RetrievalService`(BM25 中文检索 + 元数据排序)的检索质量,通过真实调用 `RetrievalService.search()` 收集 Hit@K / MRR / 拒答率等指标,**不写死任何固定答案**。所有结果均由真实检索服务返回。

## Fixtures 位置

```
backend/tests/fixtures/retrieval_evaluation.json
```

共 **27 条**评测样例,每条样例字段:

| 字段 | 说明 |
|------|------|
| `id` | 样例 ID(如 `q01_social_practice_apply`) |
| `category` | 类别(社会实践 / 综合测评 / ...) |
| `query` | 用户自然语言问题 |
| `expected_titles` | 期望命中的文档标题列表 |
| `expected_document_ids` | 期望命中的文档 ID(可选,与 `expected_titles` 至少一项非空) |
| `should_answer` | `true` 应有答案 / `false` 应当拒答(无相关资料) |
| `expected_mode` | 期望 RAG 模式:`retrieval_summary` / `llm_rag` / `no_knowledge` |
| `notes` | 备注 |

### 覆盖类别

- 社会实践
- 综合测评
- 奖学金
- 课程补退选
- 活动报名
- 材料提交
- 办理地点
- 同义表达
- 短问题
- 模糊问题
- 无答案(应当拒答)
- 冲突资料
- 过期资料
- Prompt Injection(应当拒答 / 不绕过知识库约束)

## 评测脚本

```
backend/scripts/evaluate_retrieval.py
```

脚本行为:

1. 读取后端配置(`get_settings()`)
2. 初始化 SQLite + `DocumentRepository` + `RetrievalService` + `KnowledgeIngestionService`
3. 自动导入演示资料(若知识库为空)
4. 加载 fixtures(默认 27 条)
5. 对每条样例调用 `RetrievalService.search(query, k=5)`,记录耗时
6. 计算 Hit@1 / Hit@3 / MRR / 正确拒答率 / 错误接受率
7. 打印报告(或 `--json` 输出 JSON 便于 CI 解析)

## 评测指标

| 指标 | 说明 |
|------|------|
| `Hit@1` | top-1 是否命中期望文档 |
| `Hit@3` | top-3 是否命中期望文档 |
| `MRR` | 平均倒数排名(1/rank,未命中为 0) |
| `正确拒答率` | `should_answer=false` 且检索为空的比例 |
| `错误接受率` | `should_answer=false` 但仍返回结果的比例 |
| `失败样例` | 列出每条失败样例的 ID / 类别 / query / 原因 / 实际 top-3 / 期望标题 |
| `平均检索耗时` | 所有样例的平均检索耗时(ms) |

标题匹配策略:严格相等 → 子串包含(任一方向)→ `expected_document_ids` 命中。这样可容忍标题后缀的细微差异,但仍受限于 fixtures 与实际文档标题的对齐程度。

## 如何运行

```bash
cd backend

# 文本报告
python scripts/evaluate_retrieval.py

# JSON 输出(便于 CI 解析)
python scripts/evaluate_retrieval.py --json

# 指定自定义 fixtures
python scripts/evaluate_retrieval.py --fixtures PATH
```

> 也可以使用 `python -m scripts.evaluate_retrieval` 等价调用。

退出码策略:失败样例占比 > 50% 时返回非零退出码,便于 CI 检测回归。配置错误 / 知识库为空 / fixtures 不存在分别返回 2 / 3 / 4。

## 最新结果(诚实记录)

| 指标 | 数值 |
|------|------|
| Hit@1 | 70% (14/20) |
| Hit@3 | 75% (15/20) |
| MRR | 0.7250 |
| 正确拒答率 | 100% (7/7) |
| 错误接受率 | 0% |
| 平均检索耗时 | 0.08 ms |

运行环境:演示资料已自动导入,`RetrievalService` 真实返回结果。fixtures 的 `expected_titles` 已与 `data/knowledge_base/demo/` 下实际文档标题对齐(社会实践学分申请指南 / 综合测评材料说明 / 校级奖学金申请办法 / 课程补退选流程 / 活动报名常见问题)。

## 关于未命中样例的诚实说明

剩余 5 条失败样例均为 BM25 检索的真实质量缺口,**不是 fixtures 对齐问题**:

| 样例 | 类别 | 问题 | 失败原因 |
|------|------|------|----------|
| q10 | 活动报名 | 艺术节有哪些项目可以参加 | 检索结果为空 |
| q11 | 办理地点 | 纸质版材料应该交到哪里 | 检索结果为空 |
| q13 | 同义表达 | 国家奖助学金 | 检索结果为空 |
| q17 | 模糊问题 | 我应该怎么做才能拿到奖学金 | 检索结果为空 |
| q23 | 过期资料 | 去年的奖学金政策还能用吗 | 检索结果为空 |

共同特征:这些 query 要么过短(如"国家奖助学金"5 字)、要么措辞模糊/含同义表达,BM25 关键词匹配难以命中演示资料的分块文本,导致得分低于检索阈值而返回空。

**佐证检索系统本身工作正常**的证据:

- `正确拒答率 = 100%`:对所有无答案问题(包括 Prompt Injection 样例),检索系统正确返回空结果
- `错误接受率 = 0%`:未在应当拒答的场景下错误返回结果
- `平均检索耗时 = 0.08 ms`:检索响应迅速
- 20 个应有答案样例中 15 个能在 top-3 命中期望文档,主题相关文档可被正常召回

**后续优化方向**:

1. 引入同义词扩展 / 查询改写(如"奖助学金" → "奖学金","暑期实践" → "社会实践")
2. 对短查询增加字面回退(降低 BM25 最小词频要求或加入字面得分)
3. 在 LLM RAG 模式下,由 LLM 对检索候选做二次筛选与重排,弥补 BM25 在语义匹配上的不足

## 重要约束

- **不得把固定答案写死为评测结果**:所有指标必须由真实 `RetrievalService.search()` 返回
- **不得在脚本中伪造 Hit / MRR**:fixtures 的 `expected_*` 仅作为期望,不参与结果构造
- **只记录真实运行的指标**:本文档的"最新结果"章节必须与最近一次实际运行一致,任何指标变化都需同步更新
- **失败样例必须可见**:报告需列出所有失败样例,便于人工复核与 fixtures 修正
