# 当前能力清单

本文件按"真实完成 / 降级模式 / 仅 Mock / 尚未完成"四档清晰区分 CampusMate AI 当前阶段的能力边界,避免演示与文档夸大。所有结论以真实运行结果为准,不虚构后端 / 知识库 / CNN 结果。

> 数据快照(最近一次验证):
>
> - 后端测试:`pytest` — 89 passed
> - Flutter 测试:`flutter test`(不含 `integration_test`)— 321 passed
> - 集成测试:`integration_test/` 共 9 条
>   - `app_flow_test.dart` 4 条,运行于 Android 模拟器
>   - `real_backend_test.dart` 5 条,无后端时优雅跳过
> - `flutter analyze` — No issues found
> - `dart format lib test` — 120 files formatted, 3 changed
> - `evaluate_retrieval.py` — Hit@1=70%, Hit@3=75%, MRR=0.7250, 正确拒答率=100%, 错误接受率=0%, 平均检索耗时=0.08ms(fixtures expected_titles 已与实际演示文档标题对齐;剩余 5 条失败为 BM25 在短查询/同义表达上的真实质量缺口,详见 [`retrieval_evaluation.md`](retrieval_evaluation.md))
> - `check_llm_provider.py` — LLM 已配置(`LLM_PROVIDER=openai_compatible`, `LLM_BASE_URL=https://spark-api-open.xf-yun.com/v1`, `LLM_MODEL=lite`),连接 OK,响应耗时 856ms

## 一、已真实完成

以下能力已在真实代码与测试中落地,可在 Mock 与 Real 双模式下运行并验证。

### 后端(FastAPI)

- **FastAPI 后端**:健康检查 / 统一异常处理 / 结构化错误响应 / SQLite 线程安全访问
- **规则通知抽取**:正则匹配截止时间 / 面向对象 / 材料 / 提交方式 / 地点;支持缺失年份推断;不确定时 `needs_confirmation=true` 并在 `warnings` 中说明;永不编造通知中不存在的材料
- **知识库导入**:支持 MD / TXT / PDF / DOCX,基于内容哈希去重,文件类型 / 大小 / 空文件 / 重复内容均校验,文件名 `sanitize_filename` 防路径穿越
- **BM25 检索**:jieba 分词 + rank_bm25,元数据优先级排序(未过期 > 过期、官方 > 非官方、新 > 旧)
- **SSE 流式**:AI 导员流式响应,严格基于知识库回答;恶意 Prompt 通过系统消息约束,不绕过
- **LLM Provider 连通性检查**:`backend/scripts/check_llm_provider.py` 真实发起最小测试请求,输出配置完整性 / 连接状态 / 响应耗时,失败不阻断后端启动,不打印完整 API Key
- **检索评测脚本**:`backend/scripts/evaluate_retrieval.py` 真实调用 `RetrievalService.search()`,计算 Hit@1 / Hit@3 / MRR / 正确拒答率 / 错误接受率 / 失败样例 / 平均检索耗时,不写死答案
- **AI 导员来源展示**:每条回答附带 `sources`(文档标题 / 段落 / 官方标记 / 过期标记 / 版本 / 适用对象)
- **证据等级**:`evidence_level` 区分 `retrieval_only` / `llm_rag` / `no_knowledge`
- **资料冲突处理**:检索到冲突资料时,明确指出冲突并展示两份来源,建议人工复核
- **过期资料提示**:过期文档降权但仍可显示,标注 `is_expired=true`
- **多任务通知拆分**:一条通知含多个独立任务时,结构化抽取为多条任务
- **重复通知检测**:粘贴已保存的通知时给出重复提示

### Flutter 前端

- **Flutter Real Backend 模式**:`ApiNotificationExtractionService` / `ApiCounselorChatService` / `ApiKnowledgeBaseService` / `ApiKnowledgeManagementService` 真实接入后端,后端不可用时降级到 Mock 并显示重试入口
- **本地提醒(flutter_local_notifications)**:`LocalNotificationReminderService` 在 Android 系统层调度任务截止时间通知,支持 2h / 24h 建议时间、添加 / 修改 / 取消、截止时间变更同步、任务完成 / 删除自动取消、设备重启后系统重新调度(`zonedSchedule`)、时区处理、权限礼貌策略(已授权不重复弹窗、已拒绝不自动请求)。详见 [`reminder_guide.md`](reminder_guide.md)
- **知识库管理页面**:文档列表 / 上传 / 删除 / 重建索引 / 状态查看,真实接入 `ApiKnowledgeManagementService`
- **数据管理入口**:个人中心提供"恢复演示数据"与"清除本地数据",带二次确认

### 跨端工程

- 抽象服务接口 + Riverpod Provider 注入,Mock 与 Real 实现可切换
- SharedPreferences 本地持久化 + 损坏 JSON 降级
- 比赛演示模式稳定可重复
- 自动化测试与 CI(`flutter analyze` / `flutter test` / APK / Web 构建)

## 二、降级模式

当外部依赖不可用时,系统自动降级,功能仍可正常运行:

- **LLM 未配置时的规则抽取**:`LLM_PROVIDER=none` 或调用失败 / 超时时,`/notices/extract` 走规则模式,返回 `extractor_mode="rules"`
- **`retrieval_summary` 模式**:LLM 不可用时,`/counselor/chat` 走检索摘要模式,直接拼接关键段落,标注 `evidence_level="retrieval_only"`
- **后端不可用时**:Flutter 端显示"未连接",提供重试与"切换到演示模式"按钮,不清空用户输入
- **Web 端本地提醒**:Web 平台不支持系统级定时通知,降级为应用内提醒

降级模式保证比赛演示无网络 / 无 LLM Key 时仍可用。

## 三、仅 Mock

以下能力当前**仅 Mock 实现**,UI 与流程可演示,但**不输出真实模型 / 真实后端结果**,代码与文案中明确标注 Mock:

- **表情识别**:`MockExpressionRecognitionService` 模拟多帧概率平滑 / 置信度阈值 / 状态持续时间判断 / 提醒冷却时间;`LiteRtExpressionRecognitionService` 仅占位,内部方法抛 `UnimplementedError`
- **CNN 时序结果**:`ExpressionResult` 时序流由 Mock 生成,无真实 CNN 推理;`NativeCameraExpressionRecognitionService` 未实现

CNN 接入接口与数据结构(`ExpressionLabel` / `ExpressionResult` / `ExpressionRecognitionService`)已预留,等待 LiteRT 部署后接入。

## 四、尚未完成

以下能力为本阶段真实限制,代码中未实现或仅占位:

- **CNN 真实训练**:PyTorch + FER2013 + 对比 ResNet18 / MobileNetV3-Small — 未启动
- **LiteRT 真实推理**:`LiteRtExpressionRecognitionService` 仍为占位实现
- **Native Camera**:Platform Channel + CameraX 接入未实现
- **用户认证**:JWT 多用户认证未实现,当前为单租户匿名模式
- **PostgreSQL**:当前 SQLite 单机文件存储,未迁移
- **扫描 PDF OCR**:PDF 解析仅提取文本层,扫描件无 OCR
- **暗色模式**:尚未完整适配
- **Golden Test**:主要页面截图测试未实现

## 相关文档

- [本地提醒功能指南](reminder_guide.md)
- [检索评测指南](retrieval_evaluation.md)
- [API 契约](api_contract.md)
- [知识库使用指南](knowledge_base_guide.md)
- [端到端验证](end_to_end_verification.md)
