# 大学生校园事务智能陪伴助手 (CampusMate AI)

一款面向大学生的智能助手,解决校园通知分散、事务流程不清、学习状态难追踪、缺乏有温度的陪伴体验等问题。

> 计算机设计大赛参赛项目 · 当前阶段: 原生 Android(Kotlin + Jetpack Compose)移动端 + Vue 3 Web 前端 + 微信小程序 + FastAPI 真实后端(Mock 与 Real 双模式可切换) + 表情识别训练与 LiteRT 部署

## 核心功能

| 模块 | 说明 |
|------|------|
| 校园通知智能整理 | 粘贴通知原文 → 分步骤动态提取任务名/截止时间/材料/地点 → 人工修正 → 保存为待办(支持真实后端 LLM 抽取 + 规则降级) |
| 个人待办与截止提醒 | 今日/即将截止/已完成/全部/日历视图,优先级、倒计时、滑动操作、撤销删除 |
| AI 导员问答 | 流式回答、参考来源引用、快捷问题、建议操作、停止/重新生成、无资料时提示咨询辅导员(支持真实 RAG) |
| 学习陪伴 | 学习计时、目标管理、表情识别(预留)、状态指示、休息提醒 |
| 校园知识库 | 文档导入(MD/TXT/PDF/DOCX)、BM25 中文检索、过期/官方/版本优先级、内容哈希去重 |
| 我的 | 用户信息、通知/提醒/权限设置、深色模式、减少动态效果、后端连接状态、清除数据、隐私政策 |

## 科学边界

CNN 识别的是**可观察到的面部表情**,不进行心理诊断。界面文案使用:
- "系统观察到当前表情可能偏低落"
- "识别结果仅供辅助参考"
- "你好像有些疲惫,需要休息一下吗?"

禁止出现"检测出你患有焦虑症"等诊断性表述。疲劳状态结合连续学习时长、用户主观反馈和后续生理信号综合判断,不简单等同于 FER2013 表情类别。

## 项目组成

| 模块 | 路径 | 技术 |
|------|------|------|
| 移动端 | `android/` | Kotlin + Jetpack Compose(Material 3) |
| Web 前端 | `web/` | Vue 3 + Vite + Pinia + vue-router + axios |
| 微信小程序 | `wx/` | TypeScript + 原生小程序框架 |
| 后端 | `backend/` | Python / FastAPI / SQLite / RAG / JWT / BM25 |
| 机器学习 | `ml/` | PyTorch / FER2013 / LiteRT 部署 |

## 技术栈

**移动端(Android)**

- **Kotlin** + **Jetpack Compose**(Material 3)
- **Navigation Compose** 路由
- **Retrofit** + **Moshi** + **OkHttp** 网络(Mock 与 Real 双模式)
- **DataStore**(`androidx.datastore.preferences`)本地持久化
- **Media3 ExoPlayer** 视频背景
- **Kotlin Coroutines + Flow** 异步

**Web 前端(独立仓库子目录 `web/`)**

- Vue 3 + Vite + Pinia + vue-router + axios

**Python 后端**(位于 [`backend/`](backend/))

- **FastAPI** + **Pydantic v2**(数据校验与 API 契约)
- **SQLite**(原型数据存储,预留 PostgreSQL 迁移)
- **jieba** + **rank_bm25**(中文分词与 BM25 检索)
- **PyPDF2** / **python-docx**(PDF / DOCX 解析)
- **OpenAI 兼容协议**(LLM Provider 抽象,支持 DeepSeek/通义/Kimi/本地 vLLM)
- **SSE**(AI 导员流式响应)
- **pytest** 后端测试
- **uvicorn** ASGI 服务器

**微信小程序**(位于 [`wx/`](wx/))

- TypeScript + 原生小程序框架
- 复用 FastAPI 接口

**机器学习**(位于 [`ml/`](ml/))

- **PyTorch** + **torchvision**(FER2013 表情识别训练)
- **ResNet18 / MobileNetV3-Small / EfficientNet-B0** 多模型对比
- **LiteRT** 模型导出与 Android 部署(`expression_model.tflite`)
- 训练审计、评估指标复现、数据清单管理

## 项目结构

```
campus_mate_ai/
├── android/                              # 原生 Android 应用(Kotlin Compose)
│   └── app/src/main/java/com/example/campusai/
│       ├── data/model/                  # 数据模型(User/Notice/Task/Course/ChatMessage/ExtractResult)
│       ├── data/local/                   # AppDataStore(DataStore 持久化)
│       ├── data/remote/                  # ApiClient / ApiService(Retrofit 封装)
│       ├── data/repository/              # AppRepository(统一数据入口,Mock/Real 可切换)
│       ├── ui/screens/                   # 各业务页面(login/shell/dashboard/tasks/counselor/study/...)
│       ├── ui/navigation/                # AppNavHost(Navigation Compose)
│       ├── ui/theme/                     # Color / Theme / Type(Material 3 主题)
│       └── ui/components/                # 通用组件与动效
├── web/                                  # Vue 3 前端
├── wx/                                   # 微信小程序(TypeScript)
├── backend/                              # Python FastAPI 后端
│   ├── app/
│   │   ├── api/routes/                   # health / notices / knowledge / counselor 路由
│   │   ├── core/                         # config / exceptions / logging / security
│   │   ├── database/                     # SQLite 包装(线程安全)
│   │   ├── models/                       # 数据行模型
│   │   ├── repositories/                 # DocumentRepository
│   │   ├── schemas/                      # Pydantic 请求/响应模型
│   │   ├── services/                     # 抽取 /  ingestion / 检索 / RAG / LLM
│   │   └── utils/                        # 文件解析 / 中文分词
│   ├── data/
│   │   ├── knowledge_base/demo/          # 5 份演示资料 Markdown
│   │   └── app.db                        # SQLite 数据库文件(运行后自动生成)
│   ├── scripts/rebuild_index.py          # 重建索引命令行
│   ├── tests/                            # pytest 测试
│   ├── .env.example
│   ├── pytest.ini
│   ├── requirements.txt
│   └── README.md                         # 后端专属文档
├── ml/                                   # 表情识别训练/评估/部署
│   └── expression_recognition/           # 模型训练、审计、评估与 LiteRT 导出
├── .github/workflows/                    # GitHub Actions CI(Backend CI)
├── AGENTS.md                             # 项目长期规范
└── README.md                             # 本文件
```

## 抽象服务层

移动端通过 `AppRepository` 统一对外提供数据,内部可在 Mock 实现与 `ApiService`(Retrofit)真实实现之间切换,UI 不直接依赖写死数据:

- 通知智能提取 → `AppRepository.extractNotice(...)`(→ `POST /api/v1/notices/extract`)
- AI 导员聊天 → 走真实 RAG(`POST /api/v1/counselor/chat`,SSE 流式)
- 校园知识库 → (`GET /api/v1/knowledge/documents`)
- 待办 / 学习记录 / 设置 → 本地 `DataStore` 持久化

后端不可用时 UI 显示"未连接"并提供重试与降级入口。

## 本地数据持久化

- `AppDataStore`(`androidx.datastore.preferences`)持久化登录态、设置、后端地址等
- 个人中心提供"清除本地数据"入口,带二次确认
- 损坏数据自动降级,启动失败也不阻断应用

## Design System(移动端)

- **色彩**: 低饱和青蓝色为主强调色,暖色(琥珀)表达截止/关怀/提醒;自动适配深色模式
- **字号**: 统一排版层级(display/title/subtitle/body/label/caption)
- **间距**: 8pt 网格
- **圆角 / 阴影**: 低饱和、不堆叠
- **动画**: 进入分层出现、卡片淡入位移、状态切换过渡;全局支持"减少动态效果"(无障碍)

## 深色模式

- `Theme.kt` 提供完整的浅色 / 深色 Material 3 主题
- 通过 `context` 主题色板自动选择变体
- 个人中心提供深色模式开关

## 动态交互

- 页面进入分层出现动画
- 卡片淡入 + 位移
- 待办完成勾选 + 进度变化 + 列表重排
- 截止时间倒计时实时更新
- 通知提取分步骤处理过程(动态反馈)
- AI 导员打字中动画 + 逐字流式输出
- 学习计时器实时变化
- 空状态/加载/错误/成功完整反馈
- 按钮按下/禁用/加载多状态
- 列表筛选/排序/搜索实时反馈

## CNN 接口设计(Kotlin 契约)

```kotlin
enum class ExpressionLabel {
    HAPPY, NEUTRAL, SAD, ANGRY, FEAR, SURPRISE, DISGUST, UNKNOWN, NO_FACE
}

data class ExpressionResult(
    val label: ExpressionLabel,
    val confidence: Double,
    val probabilities: Map<ExpressionLabel, Double>,
    val timestamp: Long,
    val isStable: Boolean,
    val modelVersion: String
)

interface ExpressionRecognitionService {
    fun results(): Flow<ExpressionResult>
    suspend fun initialize()
    suspend fun start()
    suspend fun pause()
    suspend fun stop()
    suspend fun dispose()
}
```

实现要求: 多帧概率平滑、置信度阈值过滤、状态持续时间判断、建议冷却时间。低置信度显示"暂时无法稳定判断当前表情",且**不**触发情绪安慰。已通过 CameraX + ML Kit 人脸检测 + LiteRT 实现,详见下文"CNN 面部表情识别"章节。

## 运行

### 一、后端启动(FastAPI)

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

### 二、移动端运行(Android / Kotlin Compose)

```bash
# 方式一: Android Studio
# 用 Android Studio 打开 android/ 目录 → Sync Project with Gradle Files → 运行 app 模块到模拟器 / 真机

# 方式二: 命令行构建
cd android
./gradlew :app:assembleDebug        # Linux / macOS
gradlew.bat :app:assembleDebug      # Windows
```

- 默认连接本地后端:`http://10.0.2.2:8000`(Android 模拟器映射到本机)
- 真机调试: 构建时传入电脑局域网地址，例如 `gradlew.bat :app:assembleDebug -PAPI_BASE_URL=http://192.168.1.20:8000/api/v1/`，并确保手机与电脑同网、端口可访问
- 发布或跨网络使用: 将 `API_BASE_URL` 指向云服务器的 HTTPS API 地址；安卓端不需要把 FastAPI 打包进 APK
- 后端不可用时使用本地缓存并明确提示服务状态;开发构建可通过环境配置启用 Mock 数据

### 三、Web 前端运行(Vue 3)

```bash
cd web
npm install
npm run dev        # 默认 http://127.0.0.1:5173
```

Web 端不限制角色,师生/管理员均可登录;默认连接 `http://localhost:8000`。

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

### 五、后端工程命令

```bash
cd backend

# 运行测试
pytest

# 重建知识库索引
python scripts/rebuild_index.py

# 启动后端(开发模式,自动重载)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 六、本地提醒 / 检索评测 / LLM 连通性检查

```bash
cd backend

# LLM Provider 连通性检查
python scripts/check_llm_provider.py
python scripts/check_llm_provider.py --json

# 检索评测
python scripts/evaluate_retrieval.py
python scripts/evaluate_retrieval.py --json
```

> **未配置 LLM 时**:系统仍使用**规则抽取**与**检索摘要模式**正常运行。详见 [`backend/README.md`](backend/README.md)。

## 测试覆盖

### Python 后端(pytest)

| 文件 | 说明 |
|------|------|
| `backend/tests/test_health.py` | 健康检查 / 知识库状态 / LLM 可用性 |
| `backend/tests/test_notice_extraction.py` | 15+ 真实校园通知场景 |
| `backend/tests/test_knowledge.py` | 上传 / 查询 / 删除 / 重建 / 状态 / 去重 |
| `backend/tests/test_counselor.py` | RAG 问答 / SSE 流式 / 无资料兜底 / 冲突提示 / 过期降权 / 恶意 Prompt 防御 |
| `backend/tests/test_expression_contributions.py` | CNN 共建样本的同意校验、上传保存与用户删除 |
| `backend/tests/test_services.py` | 检索服务 / RAG 编排 / 文档解析 |
| `backend/tests/test_llm.py` | LLM Stub / 降级模式 / 超时处理 |
| `backend/tests/test_check_llm_provider.py` | LLM 连通性检查脚本 |
| `backend/tests/test_retrieval_evaluation.py` | 检索评测脚本 |
| `backend/tests/test_retrieval_ranking.py` | 检索排序逻辑 |
| `backend/tests/conftest.py` | 临时数据库 + 临时知识库目录 + FakeLLM |

### 移动端(Android)

- 关键仓库与 UI 交互测试(JUnit / Compose UI test),见 `android/app/src/androidTest`、`android/app/src/test`

## 持续集成

CI 在 push / PR 到 `main` / `master` 时触发:

### Backend CI — [`.github/workflows/backend_ci.yml`](.github/workflows/backend_ci.yml)

1. **backend-test**: 安装 Python 3.11 + 依赖 → 导入 FastAPI app(语法检查) → `pytest` → `evaluate_retrieval` → `check_llm_provider`(LLM_PROVIDER=none 验证降级)
2. **backend-llm-stub**: 单独运行 LLM / RAG / 检索评测相关测试,验证 Fake/Stub Provider 与 `retrieval_summary` 降级路径

> Backend CI 不调用真实外部 LLM,不要求保存真实 API Key;任一后端测试失败时 CI 失败。

## 质量指标

**Python 后端**

- `pytest` — 测试通过
- API 启动健康检查通过
- 通知抽取覆盖 15+ 真实校园通知场景
- 知识库导入/检索/删除全链路测试通过
- RAG 问答(无资料/冲突/过期/恶意 Prompt)全部覆盖
- 检索评测: Hit@1=90.62%, Hit@3=100%, MRR=0.9479, 正确拒答率=100%, 错误接受率=0%
- LLM 降级模式: CI 中 `LLM_PROVIDER=none` 验证 `retrieval_summary` 与 fallback 行为,退出码 0

## 已知限制与下一阶段

### 当前阶段已完成

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
- 数据库迁移(旧库兼容 + 幂等)
- 正式 Release 强约束(`production` 禁止启用任何 Mock 业务开关)

**移动端 / Web**

- 原生 Android(Kotlin Compose)完整业务页面与导航、DataStore 持久化、深色模式、减少动态效果
- Android 已支持用户主动授权后的系统通知监听，当前优先接入微信与学习通；捕获内容仅本地保存，不能读取完整聊天历史，AI 自动识别和自动创建待办仍属于后续阶段
- Vue 3 Web 前端复用 FastAPI 接口

### 当前阶段尚未完成(真实限制)

- **模型训练与导出**: 已保留 PyTorch / FER2013 训练与 LiteRT 导出工程；仓库内 Android 资产使用已导出的 `expression_model.tflite`。本文不声明未独立复验的准确率、延迟或设备性能。
- **LiteRT / 原生真实推理**: Android 已集成 CameraX、ML Kit 本机人脸检测与 LiteRT 表情分类；若设备、权限或模型加载不可用，界面会如实显示不可用状态。
- **真实学校系统接入**: 未连接真实学校通知源 / 教务系统
- **真实学校正式数据**: 当前知识库为"演示资料",非用户所在学校的真实现行制度
- **PostgreSQL / Redis**: 当前 SQLite 单机文件存储
- **向量检索**: 当前 BM25 关键词检索 + 校园术语同义词扩展,未引入向量数据库 / Embedding 模型
- **本地提醒调度**: 系统层定时推送尚未实现

### 下一阶段建议

- 接入 PostgreSQL + Redis
- 引入向量检索 + 中文 Embedding 模型
- 在更多真实设备上开展经过同意的可用性与稳定性验证（不把辅助观察作为心理或医疗结论）
- 接入真实学校通知源(若可获得授权)
- 完善本地提醒调度与主要页面自动化测试

## 环境变量说明

### Python 后端(见 [`backend/.env.example`](backend/.env.example))

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `APP_ENV` | `development` | 运行环境 |
| `APP_HOST` | `0.0.0.0` | 监听地址 |
| `APP_PORT` | `8000` | 监听端口 |
| `APP_VERSION` | `0.2.0` | 后端版本号 |
| `DATABASE_URL` | `sqlite:///./data/app.db` | SQLite 数据库路径 |
| `KNOWLEDGE_BASE_PATH` | `./data/knowledge_base` | 知识库根目录 |
| `EXPRESSION_CONTRIBUTION_PATH` | `./data/expression_contributions` | CNN 共建样本存储目录 |
| `MAX_EXPRESSION_CONTRIBUTION_MB` | `3` | 单张 CNN 共建图片最大体积 |
| `MAX_UPLOAD_MB` | `10` | 单文件最大体积 |
| `ALLOWED_EXTENSIONS` | `md,txt,pdf,docx` | 允许上传的扩展名 |
| `AUTO_IMPORT_DEMO` | `false` | 启动时自动导入演示资料(仅 dev/test 需显式设为 `true`) |
| `LLM_PROVIDER` | `none` | LLM Provider(`none` / `openai_compatible`) |
| `LLM_BASE_URL` | (空) | LLM API 端点 |
| `LLM_API_KEY` | (空) | LLM API Key(禁止提交到 Git) |
| `LLM_MODEL` | (空) | LLM 模型名 |
| `LLM_TIMEOUT_SECONDS` | `30` | LLM 调用超时 |
| `ENABLE_FALLBACK_MODE` | `true` | LLM 不可用时是否启用降级 |
| `CORS_ORIGINS` | `http://localhost:*,http://127.0.0.1:*` | CORS 允许源 |
| `LOG_LEVEL` | `INFO` | 日志级别 |
| `LOG_REQUESTS` | `true` | 是否记录 HTTP 请求日志 |
| `AUTO_SEED_DEMO_USERS` | `false` | 启动时是否 seed 多角色验收账号(仅 dev/test) |

> 移动端通过 `BuildConfig.API_BASE_URL` 配置后端地址(Web 端使用 Vite proxy + axios)，默认指向 `http://localhost:8000`(Web)或 `http://10.0.2.2:8000`(Android 模拟器)。

## 常见错误排查

### Q1: 后端连接失败(未连接)

**症状**: 移动端 / Web 显示"未连接"。

**排查**:
1. 确认后端已启动: 浏览器访问 `http://localhost:8000/api/v1/health`
2. 确认客户端后端地址正确:
   - Android 模拟器: `http://10.0.2.2:8000`(不是 `localhost`)
   - Web: `http://localhost:8000`(同源)
   - 真机: `http://<电脑局域网 IP>:8000`
3. 确认后端 CORS 配置(`CORS_ORIGINS`)允许当前源

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

### Q4: 通知抽取结果中 `needs_confirmation=true`

**说明**: 这不是错误,而是温和的"需要确认"提示。

**原因**:
- 通知原文缺少年份(规则模式基于 `published_at` 或当前时间推断,但会标注 `warnings`)
- 面向对象不明确
- 提交方式不明确

**处理**: 客户端 UI 会显示"需要确认"徽章,用户可在表单中手动修正。

## 项目规范

参见 [AGENTS.md](AGENTS.md)。

## CNN 面部表情识别（已接入）

Android 的**专注自习（Focus）**是唯一正式入口，已接入 CameraX、ML Kit 本地人脸检测和 LiteRT 表情分类，保留 Mock/Real 双模式。只有用户主动开启“学习状态辅助”、明确授予相机权限、专注计时运行且页面在前台时，才在本机内存分析；暂停、关闭、离开页面或进入后台会立即暂停并解绑摄像头。画面不保存、不上传、不写日志。

连续时间窗口仅生成谨慎的辅助观察：约 8 秒未见人脸才记录可能暂时离开，约 4 秒明显头部偏转才记录可能注意力偏离，约 2 秒双眼低睁开概率才给出“建议休息”，且提醒至少间隔 3 分钟。专注结束会把分钟数、事件计数、可能注意力偏离累计时长、休息建议次数、稳定表情分布和模型版本保存进本地学习记录。只有用户点击“让 AI 导员分析本次专注”后，才会发送这份结构化摘要；不会发送照片、视频、逐帧结果或自动高频请求。

训练、审计、评估、导出复现命令和真实指标见 [`ml/expression_recognition/README.md`](ml/expression_recognition/README.md)。该能力仅描述画面中可观察到的面部表情，不用于推断心理状态、疲劳、疾病或危机，也不替代用户自述或专业咨询。低置信度与不稳定结果输出 `UNKNOWN`，不触发安慰。

## CNN 模型共建（用户主动参与）

设置页的“CNN 模型共建”提供单帧采集流程：用户明确同意后授予相机权限，主动拍摄一张照片，自己选择可观察到的表情标签，确认后通过鉴权接口上传。图片在上传前只暂存在 Android `cacheDir`，上传成功后删除本地文件；用户可以删除自己上传到服务器的样本。

后端接口为 `POST /api/v1/contributions/expression-samples` 和 `DELETE /api/v1/contributions/expression-samples/{sample_id}`。默认保存到 `backend/data/expression_contributions/`，可通过 `EXPRESSION_CONTRIBUTION_PATH` 配置；单张图片默认上限为 3 MB。当前接口只负责收集和保存经用户确认的标注数据，供后续人工复核、数据审计和离线 CNN 训练使用，不代表模型已经自动更新。正式部署前应迁移到对象存储、配置访问控制、加密、保留期限和管理员复核流程。
