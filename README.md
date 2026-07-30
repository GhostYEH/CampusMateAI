# 大学生校园事务智能陪伴助手 (CampusMate AI)

一款面向大学生的移动端智能助手,解决校园通知分散、事务流程不清、学习状态难追踪、缺乏有温度的陪伴体验等问题。

> 计算机设计大赛参赛项目 · 当前阶段: Flutter 高质量原型 + FastAPI 真实后端(Mock 与 Real 双模式可切换)

## 核心功能

| 模块 | 说明 |
|------|------|
| 校园通知智能整理 | 粘贴通知原文 → 分步骤动态提取任务名/截止时间/材料/地点 → 人工修正 → 保存为待办(支持真实后端 LLM 抽取 + 规则降级) |
| 个人待办与截止提醒 | 今日/即将截止/已完成/全部/日历视图,优先级、倒计时、滑动操作、撤销删除 |
| AI 导员问答 | 流式回答、参考来源引用(含官方/过期/版本/适用对象)、快捷问题、建议操作、停止/重新生成、无资料时提示咨询辅导员(支持真实 RAG) |
| 学习陪伴 | 学习计时、目标管理、Mock CNN 表情识别、多帧平滑、呼吸环状态指示、休息提醒 |
| 校园知识库 | 文档导入(MD/TXT/PDF/DOCX)、BM25 中文检索、过期/官方/版本优先级、内容哈希去重 |
| 我的 | 用户信息、通知/提醒/权限设置、深色模式、减少动态效果、**后端连接状态**、恢复演示数据、清除数据、隐私政策 |

## 科学边界

CNN 识别的是**可观察到的面部表情**,不进行心理诊断。界面文案使用:
- "系统观察到当前表情可能偏低落"
- "识别结果仅供辅助参考"
- "你好像有些疲惫,需要休息一下吗?"

禁止出现"检测出你患有焦虑症"等诊断性表述。疲劳状态结合连续学习时长、用户主观反馈和后续生理信号综合判断,不简单等同于 FER2013 表情类别。

## 技术栈

**Flutter 前端**

- **Flutter** + **Dart** (>=3.5.0, Flutter >=3.22.0)
- **Riverpod** 状态管理(`flutter_riverpod` + `riverpod_annotation`)
- **go_router** 声明式路由
- **Dio** 网络请求(封装,Mock 与 Real 双模式)
- **shared_preferences** 本地持久化(JSON 序列化)
- **flutter_local_notifications** 本地提醒(预留调度)
- **camera** 摄像头(后续 CNN 接入预留)
- **equatable** 模型相等性
- **google_fonts** 字体
- **mocktail** 单元测试 Mock

**Python 后端**(位于 [`backend/`](backend/))

- **FastAPI** + **Pydantic v2**(数据校验与 API 契约)
- **SQLite**(原型数据存储,预留 PostgreSQL 迁移)
- **jieba** + **rank_bm25**(中文分词与 BM25 检索)
- **PyPDF2** / **python-docx**(PDF / DOCX 解析)
- **OpenAI 兼容协议**(LLM Provider 抽象,支持 DeepSeek/通义/Kimi/本地 vLLM)
- **SSE**(AI 导员流式响应)
- **pytest** 后端测试
- **uvicorn** ASGI 服务器

## 项目结构

```
campus_mate_ai/
├── lib/                          # Flutter 应用
│   ├── app/
│   │   ├── config/               # AppConfig(运行环境 / Mock 切换入口)
│   │   ├── design_system/        # Design System(颜色/字号/间距/圆角/阴影/动画)
│   │   ├── providers/            # Riverpod Providers(依赖抽象接口注入)
│   │   ├── router/               # go_router 路由 + 底部导航
│   │   └── theme/                # 主题(浅色 / 深色 完整适配)
│   ├── core/                     # 跨 Feature 基础设施
│   │   ├── storage/               # 本地持久化(LocalStorage 抽象 + SharedPreferences 实现)
│   │   ├── utils/                # 工具(日期 / ID 生成)
│   │   └── widgets/              # 通用组件(卡片 / 进度环 / 分层动画 / 状态视图)
│   ├── data/
│   │   ├── models/                # 数据模型(User / Task / Notice / Chat / Expression / Study / Settings)
│   │   └── services/
│   │       ├── service_interfaces.dart   # 抽象服务接口
│   │       ├── api/              # ★ 真实后端实现(ApiClient + 3 个 Api*Service)
│   │       └── litert/          # LiteRT 占位实现
│   ├── features/                 # Feature-first 业务模块
│   │   ├── home/                 # 首页
│   │   ├── notifications/        # 通知列表 + 智能整理(支持真实抽取 + 错误降级)
│   │   ├── tasks/                # 待办(列表 + 创建)
│   │   ├── counselor/            # AI 导员聊天(支持真实 SSE + 来源引用)
│   │   ├── study_companion/      # 学习陪伴
│   │   └── profile/              # 我的(含后端状态卡片)
│   └── mock/                     # Mock 数据与 Mock 服务实现
│       ├── mock_data/            # 真实中文 Mock 数据
│       └── mock_services/        # Mock 服务 + 表情多帧平滑
├── backend/                      # ★ Python FastAPI 后端
│   ├── app/
│   │   ├── api/routes/           # health / notices / knowledge / counselor 路由
│   │   ├── core/                 # config / exceptions / logging / security
│   │   ├── database/             # SQLite 包装(线程安全)
│   │   ├── models/               # 数据行模型
│   │   ├── repositories/         # DocumentRepository
│   │   ├── schemas/              # Pydantic 请求/响应模型
│   │   ├── services/
│   │   │   ├── notice_extraction_service.py   # LLM + 规则抽取
│   │   │   ├── knowledge_ingestion_service.py # 文件解析 → 分块 → 入库
│   │   │   ├── retrieval_service.py           # BM25 检索 + 元数据排序
│   │   │   ├── rag_service.py                 # RAG 编排 + SSE 流式
│   │   │   └── llm/                           # LLM 抽象 + OpenAI 兼容实现
│   │   └── utils/                # 文件解析 / 中文分词
│   ├── data/
│   │   ├── knowledge_base/demo/ # 5 份演示资料 Markdown
│   │   └── app.db               # SQLite 数据库文件(运行后自动生成)
│   ├── scripts/rebuild_index.py  # 重建索引命令行
│   ├── tests/                   # pytest 测试(309 个)
│   ├── .env.example
│   ├── pytest.ini
│   ├── requirements.txt
│   └── README.md                # 后端专属文档
├── docs/                        # ★ 项目文档
│   ├── api_overview.md          # API 概览(请求/响应/错误码/SSE 格式/RBAC)
│   ├── knowledge_base_guide.md  # 知识库使用指南
│   ├── reminder_guide.md        # 本地提醒功能指南
│   ├── retrieval_evaluation.md  # 检索评测指南
│   ├── reports/                 # 验证报告
│   └── cnn/                     # CNN 训练与 LiteRT 部署文档
├── test/                        # Flutter 测试(707 个,含真实后端 Mock 测试)
├── integration_test/            # Flutter 集成测试(9 条,Android 模拟器 / Web)
├── .github/workflows/           # GitHub Actions CI(Flutter CI + Backend CI)
├── AGENTS.md                    # 项目长期规范
└── README.md                    # 本文件
```

## 抽象服务接口

UI 层通过 Riverpod Provider 注入服务,所有 Provider **依赖抽象接口**,Mock 与真实实现可替换:

- `NotificationExtractionService` — 通知智能提取
  - Mock: `MockNotificationExtractionService`
  - Real: `ApiNotificationExtractionService`(→ `POST /api/v1/notices/extract`)
- `TaskRepository` — 待办任务仓库(含 `snapshot` / `restoreFrom` / `clearAll` / `resetToDemo`)
- `CounselorChatService` — AI 导员聊天
  - Mock: `MockCounselorChatService`
  - Real: `ApiCounselorChatService`(→ `POST /api/v1/counselor/chat`,SSE 流式)
- `KnowledgeBaseService` — 校园知识库
  - Mock: `MockKnowledgeBaseService`
  - Real: `ApiKnowledgeBaseService`(→ `GET /api/v1/knowledge/documents`)
- `StudySessionRepository` — 学习会话仓库(含 `historySnapshot` / `restoreHistoryFrom` / `clearHistory` / `resetToDemo`)
- `ExpressionRecognitionService` — 表情识别(预留 LiteRT / Native Camera 实现)
- `PermissionService` — 权限管理
- `AnalyticsService` — 埋点分析

通过 `AppConfig`(`appConfigProvider`)统一决定实现注入策略:
- `useMockBackend=true` → 注入 Mock 实现(默认,离线可用,演示数据完整)
- `useMockBackend=false` → 注入 Real 实现(走 FastAPI 后端)

## 本地数据持久化

第一阶段任务、设置、学习记录与通知仅存内存,重启即丢;第二阶段已落地完整的持久化链路:

- `LocalStorage`(抽象)+ `SharedPreferencesLocalStorage`(实现)+ `JsonCodecHelper`(JSON 编解码)
- 类型化 Storage:`SettingsStorage` / `TaskStorage` / `StudyStorage` / `NoticeStorage`
- 统一编排服务 `DataPersistenceService`,负责启动加载(`loadAll`)、运行时保存(`saveSettings/saveTasks/saveStudyHistory/saveNotices`)、清除(`clearAllData`)与恢复演示(`restoreDemoData`)
- `main.dart` 在启动时初始化 SharedPreferences、构造仓储实例、注入 Provider、加载持久化设置
- `app.dart` 监听 `appSettingsProvider` / `taskListProvider` / `campusNoticesProvider` 变化,自动写回本地
- 个人中心提供"恢复演示数据"与"清除本地数据"入口,带二次确认对话框
- 损坏 JSON 自动降级为空数据,启动失败也不阻断应用

## Design System

- **色彩**: 低饱和青蓝色为主强调色(`#2F6486`),暖色(琥珀)表达截止/关怀/提醒;上下文感知 `AppColorScheme` 自动适配深色模式
- **字号**: 统一排版层级(display/title/subtitle/body/label/caption/overline)
- **间距**: 8pt 网格(edge=16, lg=12, md=8, sm=6, xs=4)
- **圆角**: xs=4 / sm=8 / md=12 / lg=16 / xl=24
- **阴影**: subtle / elevated / focused(低饱和、不堆叠)
- **动画**: base=280ms / fast=180ms / slow=420ms;曲线 emphasized / decelerate / gentleSpring / standard
- **减少动态效果**: 全局 `reduceMotionProvider`,开启时跳过 StaggeredEnter / 呼吸环等动画;设置同步到 Provider,无障碍支持

## 深色模式

第二阶段已完整适配:

- `AppTheme.dark()` 提供完整的深色 ThemeData(scaffold / colorScheme / card / button / input / chip / navBar / switch / slider / snackbar 等)
- `AppColorScheme` 通过 `BuildContext` 自动选择浅色/深色变体,通过 `context.appColors.xxx` 使用
- 通用组件(`AppCard` / `SectionHeader` / `EmptyStateView` / `ErrorStateView` 等)已迁移到上下文感知色板
- `MaterialApp.themeMode` 跟随 `appSettingsProvider.darkMode` 切换
- 个人中心提供深色模式开关

## 动态交互

- 页面进入分层出现动画(StaggeredEnter)
- 卡片淡入 + 位移
- 待办完成勾选 + 进度变化 + 列表重排
- 截止时间倒计时实时更新
- 通知提取分步骤处理过程(6 步动态反馈)
- AI 导员打字中动画 + 逐字流式输出 + 闪烁光标
- 学习计时器实时变化
- 呼吸环 / 波形状态指示器
- 表情识别结果平滑过渡(多帧平滑)
- 空状态/加载/错误/成功完整反馈
- 按钮按下/禁用/加载/成功多状态
- 列表筛选/排序/搜索实时反馈

## 比赛演示模式

在"我的 → 比赛演示模式"中开启,提供完整数据链路:

1. 首页已有数条校园通知
2. 粘贴通知 → 动态提取 → 保存为待办
3. 首页任务进度更新
4. 向 AI 导员询问任务 → 引用模拟知识库回答
5. 开启学习陪伴 → 模拟 CNN 识别稳定表情
6. AI 导员结合任务和表情给出轻量回应
7. 完成任务 → 首页进度更新 + 完成反馈

支持"恢复演示数据"快速重置待办与学习记录为默认 MockData,带二次确认。

## CNN 接口设计(预留)

```dart
enum ExpressionLabel {
  happy, neutral, sad, angry, fear, surprise, disgust, unknown, noFace,
}

class ExpressionResult {
  final ExpressionLabel label;
  final double confidence;
  final Map<ExpressionLabel, double> probabilities;
  final DateTime timestamp;
  final bool isStable;
  final String modelVersion;
}

abstract interface class ExpressionRecognitionService {
  Stream<ExpressionResult> get results;
  Future<void> initialize();
  Future<void> start();
  Future<void> pause();
  Future<void> stop();
  Future<void> dispose();
}
```

当前实现 `MockExpressionRecognitionService`,包含:
- 多帧概率平滑(指数加权)
- 置信度阈值过滤
- 状态持续时间判断
- 建议冷却时间
- 低置信度显示"暂时无法稳定判断当前表情",且**不**触发情绪安慰

后续预留:
- `LiteRtExpressionRecognitionService`(LiteRT 部署 CNN,接口已预留,内部方法暂抛 UnimplementedError)
- `NativeCameraExpressionRecognitionService`(Platform Channel + CameraX)

## 运行

### 一、Flutter Mock 模式(默认,无需后端)

```bash
# 安装依赖
flutter pub get

# 运行(默认即 Mock 模式)
flutter run

# 或显式指定
flutter run --dart-define=USE_MOCK_BACKEND=true
```

Mock 模式特性:
- 完全离线可用,无需启动后端
- 所有交互基于 `MockData`(真实中文校园数据)
- 表情识别走 `MockExpressionRecognitionService`(多帧平滑)
- AI 导员基于规则模板回复
- 比赛演示模式与"恢复演示数据"始终可用

### 二、后端启动(FastAPI)

```bash
cd backend

# 1. 创建虚拟环境
python -m venv .venv

# Windows PowerShell(推荐)
.venv\Scripts\Activate.ps1
# 若提示执行策略受限,可临时放开(仅当前会话):
# Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Windows cmd / Git Bash
.venv\Scripts\activate.bat

# macOS / Linux
# source .venv/bin/activate

# 2. 安装依赖
pip install -r requirements.txt

# 3. 配置环境变量
cp .env.example .env
# 默认无需 LLM 即可运行(规则模式 + 检索摘要模式)

# 4. 启动后端
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

启动后访问:
- 健康检查: http://localhost:8000/api/v1/health
- Swagger 文档: http://localhost:8000/docs

### 三、Flutter Real Backend 模式

```bash
# Android 模拟器(10.0.2.2 映射到本机)
flutter run --dart-define=USE_MOCK_BACKEND=false \
            --dart-define=API_BASE_URL=http://10.0.2.2:8000

# Flutter Web(同源访问 localhost)
flutter run -d chrome --dart-define=USE_MOCK_BACKEND=false \
                       --dart-define=API_BASE_URL=http://localhost:8000

# 真机(同 Wi-Fi,IP 替换为电脑局域网 IP)
flutter run --dart-define=USE_MOCK_BACKEND=false \
            --dart-define=API_BASE_URL=http://192.168.x.x:8000
```

Real Backend 模式特性:
- 通知抽取走真实 LLM + 规则降级
- AI 导员走真实 RAG(SSE 流式)
- 知识库可导入真实校园资料
- 后端不可用时 UI 显示"未连接"并提供重试与降级入口
- 比赛演示模式仍可启用(与后端模式独立)

### 四、可选:启用 LLM(增强抽取与回答质量)

编辑 `backend/.env`:

```env
LLM_PROVIDER=openai_compatible
LLM_BASE_URL=https://api.deepseek.com/v1   # 或其它兼容端点
LLM_API_KEY=sk-xxxxxxxxxxxx                  # 禁止提交到 Git
LLM_MODEL=deepseek-chat
```

未配置 LLM 时:
- 通知抽取走规则模式(正则匹配 + 日期推断)
- AI 导员走检索摘要模式(直接拼接关键段落)
- 健康检查返回 `llm_available=false`, `mode=rules_only`

### 五、Flutter 工程命令

```bash
# 格式化
dart format lib test

# 静态检查
flutter analyze

# 测试(含真实后端 Mock 测试)
flutter test

# 构建 Android APK(debug)
flutter build apk --debug

# 构建学生专用 Release APK
# (RESTRICT_TO_STUDENT=true: 非学生角色登录会被拦截并提示改用 Web 端)
flutter build apk --release --dart-define=RESTRICT_TO_STUDENT=true

# 构建多角色 Release APK(教师/管理员也可登录,适用于内部测试)
flutter build apk --release

# 构建 Web
flutter build web --release
```

**角色分工约定**:
- **Android 学生专用 APK**:打包时传 `--dart-define=RESTRICT_TO_STUDENT=true`,
  登录阶段会拦截非学生角色(教师/管理员),提示「请使用 Web 端登录」。
  已签发的服务端 token 会被主动撤销,避免悬挂会话。
- **Web 端**:不传 `RESTRICT_TO_STUDENT`,师生均可登录,教师进入 `/teacher/workbench`,
  学生进入 `/home`,管理员进入 `/admin/users`。
- 拦截逻辑位于 `lib/app/providers/auth_providers.dart` 的 `AuthNotifier.login`,
  通过 `AppConfig.effectiveRestrictToStudent` 判断(Web 平台永远放行)。

### 六、后端工程命令

```bash
cd backend

# 运行测试
pytest

# 重建知识库索引
python scripts/rebuild_index.py

# 启动后端(开发模式,自动重载)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 七、本地提醒 / 检索评测 / LLM 连通性检查

```bash
cd backend

# LLM Provider 连通性检查 — 验证 LLM 配置是否完整、连接是否可用、响应耗时
# 未配置 LLM 时返回 not_enabled 并退出码 0,不阻断后续操作
python scripts/check_llm_provider.py
# JSON 输出(便于 CI 解析)
python scripts/check_llm_provider.py --json

# 检索评测 — 真实调用 RetrievalService,计算 Hit@1 / Hit@3 / MRR / 正确拒答率 / 错误接受率
python scripts/evaluate_retrieval.py
# JSON 输出
python scripts/evaluate_retrieval.py --json
```

> **未配置 LLM 时**:系统仍使用**规则抽取**与**检索摘要模式**正常运行,功能不依赖 LLM。`check_llm_provider.py` 会输出 `not_enabled` 并提示"系统使用规则抽取和检索摘要模式"。
>
> 本地提醒功能基于 `flutter_local_notifications`,在 Android 系统层调度任务截止时间通知,详见 [`docs/reminder_guide.md`](docs/reminder_guide.md)。
>
> 检索评测的指标含义、fixtures 结构与最新结果说明见 [`docs/retrieval_evaluation.md`](docs/retrieval_evaluation.md)。

> 详细后端启动、知识库导入、降级模式说明见 [`backend/README.md`](backend/README.md)。
> API 概览(请求/响应/错误码/SSE 格式/RBAC 权限矩阵)见 [`docs/api_overview.md`](docs/api_overview.md)。
> 知识库使用指南见 [`docs/knowledge_base_guide.md`](docs/knowledge_base_guide.md)。

## 测试覆盖

### Flutter(707 测试)

| 类别 | 测试文件 | 说明 |
|------|----------|------|
| 数据模型 | `test/data/models/notice_test.dart` | 通知提取结果模型(含 warnings / extractorMode) |
| 工具类 | `test/core/utils/date_utils_test.dart` | 日期/截止时间计算 |
| Provider | `test/app/providers/app_providers_test.dart` | Riverpod 状态管理 / 任务派生 Provider |
| ★ 配置切换 | `test/app/providers/app_config_switch_test.dart` | Mock/Real 切换 / dart-define 注入 |
| 任务仓库 | `test/mock/mock_services/mock_task_repository_test.dart` | 增删改查/恢复 |
| 表情平滑 | `test/mock/mock_services/expression_smoother_test.dart` | 多帧平滑/低置信度 |
| 建议冷却 | `test/mock/mock_services/suggestion_cooldown_test.dart` | 提醒冷却时间 |
| 首页 | `test/features/home/home_page_test.dart` | Widget 测试 |
| 通知整理 | `test/features/notifications/notification_extract_page_test.dart` | 完整流程 Widget 测试 |
| ★ 真实后端降级 | `test/features/notifications/notification_extract_real_backend_test.dart` | 连接失败/重试/降级到 Mock |
| AI 导员 | `test/features/counselor/counselor_page_test.dart` | 聊天/流式/来源/操作 Widget 测试 |
| ★ 后端状态卡 | `test/features/profile/backend_status_card_test.dart` | 4 种状态(已连接/未连接/演示/未初始化) |
| 本地存储 | `test/core/storage/local_storage_test.dart` | SharedPreferencesLocalStorage / JsonCodecHelper |
| Storage 类 | `test/core/storage/storage_test.dart` | Settings/Task/Study/Notice Storage 往返与损坏降级 |
| 持久化服务 | `test/core/storage/data_persistence_service_test.dart` | loadAll/save/clearAllData/restoreDemoData 全链路 |
| 主题与色板 | `test/app/theme/app_theme_test.dart` | AppTheme.light/dark + AppColorScheme + expressionColor |
| App 集成 | `test/app/app_test.dart` | AppConfig / Provider 注入 / 深色模式 ThemeMode / 自动持久化监听 |
| ★ API 抽取服务 | `test/data/services/api/api_notification_extraction_service_test.dart` | LLM/Rules 模式 + 错误处理 |
| ★ API 导员服务 | `test/data/services/api/api_counselor_chat_service_test.dart` | SSE 流式 / sources/chunk/done / 网络错误 |
| ★ API 知识库服务 | `test/data/services/api/api_knowledge_base_service_test.dart` | 文档列表 / 来源解析 / 元数据 |

### Python 后端(309 个 pytest 测试)

| 文件 | 说明 |
|------|------|
| `backend/tests/test_health.py` | 健康检查 / 知识库状态 / LLM 可用性 |
| `backend/tests/test_notice_extraction.py` | 15+ 真实校园通知(奖学金/综测/实践/选课/考试/材料/活动/宿舍/缺年份/缺截止/多材料/多对象/非通知/空/超长) |
| `backend/tests/test_knowledge.py` | 上传 / 查询 / 删除 / 重建 / 状态 / 去重 / 类型限制 / 大小限制 |
| `backend/tests/test_counselor.py` | RAG 问答 / SSE 流式 / 无资料兜底 / 冲突提示 / 过期降权 / 恶意 Prompt 防御 |
| `backend/tests/test_services.py` | 检索服务 / RAG 编排 / 文档解析 |
| `backend/tests/test_llm.py` | LLM Stub / 降级模式 / 超时处理 |
| `backend/tests/test_check_llm_provider.py` | LLM 连通性检查脚本 / Fake Provider 测试 |
| `backend/tests/test_retrieval_evaluation.py` | 检索评测脚本(44 条 fixtures) |
| `backend/tests/test_retrieval_ranking.py` | 检索排序逻辑(freshness bonus / 元数据加权 / 同义词扩展 / 短查询回退 / 多路召回) |
| `backend/tests/conftest.py` | 临时数据库 + 临时知识库目录 + FakeLLM |

## 持续集成

CI 在 push / PR 到 `main` / `master` 时触发,包含两个独立 workflow:

### Flutter CI — [`.github/workflows/flutter_ci.yml`](.github/workflows/flutter_ci.yml)

1. **analyze-and-test**: 安装依赖 → `dart format --set-exit-if-changed lib test integration_test` → `flutter analyze` → `flutter test --reporter=expanded`
2. **build-android**: 构建调试 APK 并上传为 artifact(依赖 1 通过)
3. **build-web**: 构建 Web release 并上传为 artifact(依赖 1 通过)

### Backend CI — [`.github/workflows/backend_ci.yml`](.github/workflows/backend_ci.yml)

1. **backend-test**: 安装 Python 3.11 + 依赖 → 导入 FastAPI app(语法检查) → `pytest` → `evaluate_retrieval`(文本+JSON) → `check_llm_provider`(LLM_PROVIDER=none 验证降级)
2. **backend-llm-stub**: 单独运行 `test_check_llm_provider.py` / `test_llm.py` / `test_counselor.py` / `test_retrieval_evaluation.py`,验证 Fake/Stub Provider 与 `retrieval_summary` 降级路径

> Backend CI 不调用真实外部 LLM,不要求保存真实 API Key;缓存 pip 依赖但**不**缓存数据库或用户数据;任一后端测试失败时 CI 失败。

## 前端设计 Skill

本项目使用 **`trae-remote-official:frontend-design:frontend-design`** Skill 指导页面设计,遵循其工作流程:
1. 确定设计方向(青年校园 / 智能温和 / 简洁现代)
2. 建立 Design System(颜色/字号/间距/圆角/阴影/动画)
3. 按 Feature 落地页面,避免模板式 UI
4. 动画服务于信息反馈,支持减少动态效果

## 质量指标

**Flutter**

- `dart format lib test integration_test` — 120 files formatted,3 changed(其他 Agent 维护范围)
- `flutter analyze` — No issues found
- `flutter test` — 全部测试通过(707 tests)
- Android APK 构建 — 通过(core library desugaring 已启用)
- Web 构建 — 通过

**Python 后端**

- `pytest` — 309 tests passed
- API 启动健康检查通过(`CampusMate AI Backend`)
- 通知抽取覆盖 15+ 真实校园通知场景
- 知识库导入/检索/删除全链路测试通过
- RAG 问答(无资料/冲突/过期/恶意 Prompt)全部覆盖
- 检索评测:Hit@1=90.62%, Hit@3=100%, MRR=0.9479, 正确拒答率=100%, 错误接受率=0%(44 条 fixtures,0 失败)
- LLM 降级模式:CI 中 `LLM_PROVIDER=none` 验证 `retrieval_summary` 与 fallback 行为,退出码 0

## 已知限制与下一阶段

### 当前阶段已完成

**Flutter 前端**

- Flutter 应用工程化(Android / Web 平台工程就绪,可构建)
- Mock 数据闭环 + 完整交互
- 抽象服务接口 + Mock 实现彻底解耦(Provider 依赖抽象,通过 AppConfig 切换)
- ★ 真实后端实现: `ApiNotificationExtractionService` / `ApiCounselorChatService` / `ApiKnowledgeBaseService`
- ★ 后端连接状态卡片(4 种状态: 已连接 / 未连接 / 演示 / 未初始化)
- ★ 错误降级: 后端不可用时显示重试与"切换到演示模式"按钮,不清空用户输入
- SharedPreferences 本地持久化 + 损坏数据降级
- 深色模式完整适配(主题 / 色板 / 通用组件 / 个人中心开关)
- 比赛演示模式稳定可重复(含"恢复演示数据")
- 页面文件拆分(首页 / 通知整理 等)
- 自动化测试与 CI

**Python 后端**

- FastAPI 基础工程(健康检查 / 统一异常处理 / 结构化错误响应)
- 通知结构化抽取(LLM 优先 + 规则降级 + 不确定时 `needs_confirmation=true`)
- 校园知识库导入(MD/TXT/PDF/DOCX + 内容哈希去重 + 安全限制)
- BM25 中文检索(jieba 分词 + 元数据优先级排序)
- RAG 问答(SSE 流式 + 来源引用 + 冲突提示 + 过期降权 + 恶意 Prompt 防御)
- LLM 降级模式(无 API Key 时走检索摘要模式)
- 5 份标注"演示资料"的内置文档
- JWT 认证 + 多角色 RBAC(student / teacher / admin)
- 课程 / 班级 / 通知 / 任务 / 提交 全 CRUD + 状态机
- 教师工作台 + 学生工作台(聚合 SQL,无 N+1)
- 附件上传与下载(安全校验 + 路径穿越防御)
- AI 导员上下文融合(权限校验 + 草稿隔离)
- 数据库迁移(旧库兼容 + 幂等)
- 正式 Release 强约束(`production` 禁止启用任何 Mock 业务开关)
- pytest 完整覆盖

### 当前阶段尚未完成(真实限制)

- **CNN 模型训练**: PyTorch + FER2013 + 对比 ResNet18 / MobileNetV3-Small — 当前仅 Mock
- **LiteRT 真实推理**: `LiteRtExpressionRecognitionService` 仍为占位实现
- **真实学校系统接入**: 未连接真实学校通知源 / 教务系统
- **真实学校正式数据**: 当前知识库为"演示资料",非用户所在学校的真实现行制度
- **PostgreSQL / Redis**: 当前 SQLite 单机文件存储
- **向量检索**: 当前 BM25 关键词检索 + 校园术语同义词扩展(对称),未引入向量数据库 / Embedding 模型
- **本地提醒调度**: `flutter_local_notifications` 真实定时推送未实现
- **Golden Test**: 主要页面截图测试未实现

### 下一阶段建议

- 接入 PostgreSQL + Redis
- 引入向量检索 + 中文 Embedding 模型(改善同义词/语义检索)
- CNN 模型训练 + LiteRT 真实部署 + Platform Channel 接 CameraX
- `flutter_local_notifications` 真实定时推送
- 接入真实学校通知源(若可获得授权)
- 增加 Redis 缓存与限流
- 完善主要页面 Golden Test

## 环境变量说明

### Flutter(dart-define)

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `USE_MOCK_BACKEND` | `true` | 是否使用 Mock 后端(`false` 切换到真实后端) |
| `USE_MOCK_EXPRESSION` | `true` | 是否使用 Mock 表情识别 |
| `API_BASE_URL` | `http://10.0.2.2:8000` | 真实后端 API 地址(Android 模拟器默认映射本机) |

### Python 后端(见 [`backend/.env.example`](backend/.env.example))

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `APP_ENV` | `development` | 运行环境 |
| `APP_HOST` | `0.0.0.0` | 监听地址 |
| `APP_PORT` | `8000` | 监听端口 |
| `APP_VERSION` | `0.2.0` | 后端版本号 |
| `DATABASE_URL` | `sqlite:///./data/app.db` | SQLite 数据库路径 |
| `KNOWLEDGE_BASE_PATH` | `./data/knowledge_base` | 知识库根目录 |
| `MAX_UPLOAD_MB` | `10` | 单文件最大体积 |
| `ALLOWED_EXTENSIONS` | `md,txt,pdf,docx` | 允许上传的扩展名 |
| `AUTO_IMPORT_DEMO` | `true` | 启动时自动导入演示资料 |
| `LLM_PROVIDER` | `none` | LLM Provider(`none` / `openai_compatible`) |
| `LLM_BASE_URL` | (空) | LLM API 端点 |
| `LLM_API_KEY` | (空) | LLM API Key(禁止提交到 Git) |
| `LLM_MODEL` | (空) | LLM 模型名 |
| `LLM_TIMEOUT_SECONDS` | `30` | LLM 调用超时 |
| `ENABLE_FALLBACK_MODE` | `true` | LLM 不可用时是否启用降级 |
| `CORS_ORIGINS` | `http://localhost:*,http://127.0.0.1:*` | CORS 允许源 |
| `LOG_LEVEL` | `INFO` | 日志级别 |

## 常见错误排查

### Q1: Flutter Real Backend 模式连接失败

**症状**: 启动后显示"未连接",`backendStatusProvider` 报错。

**排查**:
1. 确认后端已启动: 浏览器访问 `http://localhost:8000/api/v1/health`
2. 确认 `API_BASE_URL` 正确:
   - Android 模拟器: `http://10.0.2.2:8000`(不是 `localhost`)
   - Flutter Web: `http://localhost:8000`(同源)
   - 真机: `http://<电脑局域网 IP>:8000`
3. 确认后端 CORS 配置(`CORS_ORIGINS`)允许当前源
4. 临时切换到 Mock 模式继续使用: `--dart-define=USE_MOCK_BACKEND=true`

### Q2: AI 导员回答"建议咨询辅导员"

**症状**: 所有问题都返回"当前知识库无法确认..."。

**排查**:
1. 检查知识库状态: `GET /api/v1/knowledge/status`
2. 若 `document_count=0`,运行 `python scripts/rebuild_index.py` 或重启后端(自动导入演示资料)
3. 若 `index_status=error`,查看后端日志,可能是文件解析失败

### Q3: 后端启动报错 `ModuleNotFoundError`

**症状**: `ModuleNotFoundError: No module named 'jieba'` 等。

**排查**:
1. 确认已激活虚拟环境(PowerShell: `.venv\Scripts\Activate.ps1`)
2. 重新安装依赖: `pip install -r requirements.txt`
3. Windows 上若 jieba/PyPDF2 安装失败: `pip install --no-build-isolation jieba`

### Q4: Flutter Web 模式下后端连接被拒

**症状**: 浏览器控制台报 CORS 错误。

**排查**:
1. 确认 `backend/.env` 中 `CORS_ORIGINS` 包含 `http://localhost:*`
2. 重启后端使配置生效
3. Flutter Web 默认端口 55566 / 随机端口,均匹配 `http://localhost:*`

### Q5: 通知抽取结果中 `needs_confirmation=true`

**说明**: 这不是错误,而是温和的"需要确认"提示。

**原因**:
- 通知原文缺少年份(规则模式基于 `published_at` 或当前时间推断,但会标注 `warnings`)
- 面向对象不明确
- 提交方式不明确

**处理**: 客户端 UI 会显示"需要确认"徽章,用户可在表单中手动修正。

## 项目规范

参见 [AGENTS.md](AGENTS.md)。
