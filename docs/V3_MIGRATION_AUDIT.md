# CampusMateAI V3 Migration Audit

更新日期：2026-08-13

## 审计基线

- 工作分支：`codex/chaoxing-course-content`。
- 工作区在审计开始前已有大量未提交修改，覆盖 Android、Backend、HarmonyOS、Web 和微信小程序。本次迁移必须原地保留这些修改，不执行 reset、clean、checkout、restore 或 commit。
- Backend 基线：`python -m pytest -q`，150 passed，17 warnings。
- Web 基线：`npm run build` 成功；存在 Vite 既有大 chunk 警告。
- Android 基线：系统默认 JDK 26 无法运行 Gradle；切换项目可用 JDK 17 后，Kotlin 增量缓存出现既有注册冲突并回退到非 daemon 编译。V3 阶段验证统一使用 JDK 17。
- 产品文档已声明正式角色只有 `student` 和 `admin`，但运行代码仍存在教师工作流、教师文件与审批型办事大厅，文档和实现不一致。

## 决策表

| 状态 | 范围 | 审计结论 | 迁移动作 |
| --- | --- | --- | --- |
| REMOVE | `web/src/views/teacher/` | 教师工作台、教师作业、评分、分析和教师 AI 助手属于错误产品方向 | 客户端切换完成后删除目录及引用 |
| REMOVE | Web `/teacher/chaoxing*` | 旧教师语义兼容地址；正式学生入口已是 `/profile/chaoxing` | 移除兼容路由，保留学生学习通入口 |
| REMOVE | Android `service_leave`、`service_repair`、`service_form/certificate`、`service_form/venue`、`service_mine`、`service_detail` | 模拟真实学校审批 | 用“校园生活”入口替代并清理导航、UI、repository 与测试 |
| REMOVE | HarmonyOS/Web 审批型 services 页面 | 同上 | 三端切换后删除，不保留假审批状态 |
| REMOVE | Backend 教师 dashboard、grading、assignment publishing、approval 运行时路由 | 正式角色不是教师 | 先确认客户端不再调用，再撤下 router/service 暴露 |
| KEEP | `course.teacher_id`、`course.teacher_name`、Android `Course.teacher` | 任课教师是学生课程元数据，不代表教师角色 | 继续作为课程/课表详情只读信息 |
| KEEP | 学生 assignment 查询、截止时间与提交状态 | 学生学习流程仍有价值 | 只移除教师创建、发布、评分、管理能力 |
| RENAME | `TeacherChaoxing*` | 学习通是学生学习平台连接 | 迁移为 `StudentChaoxing*`；已有学生实现优先复用 |
| RENAME | “办事大厅” | 名称和功能暗示 OA 审批 | 重定位为“校园生活”，仅展示真实可用服务或官方办理指南 |
| MIGRATE | `users` | 缺少独立大学身份 | 增加 nullable `university_id` 外键；旧用户可稍后选择 |
| MIGRATE | 失物招领、校园活动 | 当前没有一致的大学隔离 | 增加 `university_id` 并默认按当前用户过滤 |
| MIGRATE | 课程来源 | 已有 manual/Chaoxing/后端演示来源 | 统一 `provider`、`external_id`、`last_synced_at`，增加 academic 来源且保持幂等 |
| COMPATIBILITY_ONLY | `users.teacher_number`（若存在） | 历史数据库兼容字段 | 不物理 DROP；标记 deprecated，新代码不得依赖或返回 |
| COMPATIBILITY_ONLY | `submissions.teacher_comment`、评分列 | 历史提交数据 | 暂不 DROP；新运行时不暴露教师评分工作流 |
| COMPATIBILITY_ONLY | 历史 service request 表 | 物理删除会增加演示数据库迁移风险 | 客户端切换后退役；代码不再访问，后续独立 migration 清理 |

## V3 目标域

### University Core

- Backend 是大学列表和学校能力状态唯一来源。
- `User -> University` 是校园公共域的租户边界。
- 旧用户 `university_id = null` 可以继续使用 AI、个人待办与学习陪伴；进入社区、失物招领、校园活动时提示选择大学。
- `student_demo` 绑定明确标记为“演示数据”的 Demo University，不宣称真实教务接入。

### Community

- 独立表：posts、comments、likes、favorites、reports；失物招领与活动不合表。
- 学生查询和写入强制使用当前大学；管理员可跨大学治理。
- 匿名仅影响展示，Backend 始终保留 `author_id`。
- 权限、限流、内容状态和举报决策只在 Backend 执行。

### Academic Integration

- `AcademicProvider` adapter 负责认证与同步；不按学校堆叠巨大 if/else。
- 当前没有可独立验证的真实学校 Provider，因此 V3 首版只提供 `UNSUPPORTED` 和手动课程 fallback，不伪造绑定成功。
- API、日志和客户端持久化均不得出现教务密码；数据库只保存受保护的 credential reference/session material。
- 同步以 `user_id + provider + external_id + semester` 保证幂等。

## 迁移顺序

1. 新表、新列、新 API 与兼容迁移。
2. Android 切换 University、Community、Academic、Schedule、Grades。
3. HarmonyOS 和 Web 使用同一 `/api/v1` 契约切换。
4. LostFound/Activities 改为 University scoped。
5. 移除旧教师和审批型客户端入口。
6. 撤下无客户端调用的旧运行时 route/service，保留高风险历史列/表一版。
7. 清理 dead imports/tests，完成全端构建与权限/隔离验证。

## 明确不改范围

除 University Context 的最小扩展外，不重写 NotificationListener、ExpressionSessionManager、CameraX、FocusStateProcessor、AI Counselor、RAG、Auth Refresh 或 WorkManager。

## 2026-08-13 实施结果

- Web 教师路由和教师页面已从运行时删除，学生学习通入口保留。
- Backend 已增加 University、Community、Academic compatibility schema/API；旧库通过幂等表创建和列迁移获得 `users.university_id`，历史教师与 service request 表暂不物理删除。
- Android 已接入“我的大学 / 校园社区 / 教务系统”，首页审批式“办事大厅”入口已替换为校园社区；直接意见反馈仍作为非审批支持渠道保留。
- HarmonyOS 已使用同一 Backend 契约增加对应入口和页面；本机缺少可执行 Hvigor wrapper，因此只记录为 PARTIAL。
- Web 已增加三页及导航，空态、错误态和不支持教务状态可在首屏理解。
- 失物招领已按 `university_id` 隔离，private 联系方式只向发布者展示。
- 当前社区纵向切片尚未实现限流、图片上传、完整详情/评论管理和管理员举报工作台；Academic 尚无真实学校 Provider、课表或成绩同步。
- 真实完成度以 `docs/V3_PARITY_MATRIX.md` 为准，不将静态 UI 或未编译客户端标记为 DONE。
