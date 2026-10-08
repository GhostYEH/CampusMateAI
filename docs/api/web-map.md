# Web 页面与接口调用对照

> 只核对 webreact/src；不读取其他客户端。下表保留实际封装位置、函数名和 HTTP 路径。动态路径按占位符匹配；页面路径来自 App.jsx。存在封装不表示页面当前一定使用它。

[文档导航](README.md)

## Web 路由

| 页面路径 | 页面 / 重定向 |
| --- | --- |
| `/login` | <LoginPage /> |
| `/` | <Navigate to="/home" replace /> |
| `/home` | <Page name="HomePage" /> |
| `/courses` | <Page name="CoursesPage" /> |
| `/courses/:courseId/classroom` | <Page name="MagicClassClassroomEntryPage" /> |
| `/courses/:courseId/magicclass-preview` | <Page name="MagicClassGenerationPreviewPage" /> |
| `/courses/:courseId/workspaces/:workspaceId` | <Page name="MagicClassWorkbenchPage" /> |
| `/courses/:courseId/workspaces/:workspaceId/legacy` | <Page name="MagicClassWorkspacePage" /> |
| `/courses/:courseId` | <Page name="CourseDetailPage" /> |
| `/learning-space` | <Page name="LearningSpacePage" /> |
| `/tasks` | <Page name="TasksPage" /> |
| `/tasks/:kind/:id` | <Page name="TaskDetailPage" /> |
| `/community` | <Page name="CommunityPage" /> |
| `/community/create` | <Page name="CommunityCreatePage" /> |
| `/community/:postId` | <Page name="CommunityDetailPage" /> |
| `/university` | <Page name="UniversityPage" /> |
| `/counselor` | <Page name="CounselorPage" /> |
| `/notifications` | <Page name="NotificationsPage" /> |
| `/announcements/:announcementId` | <Page name="AnnouncementDetailPage" /> |
| `/study` | <Page name="StudyPage" /> |
| `/learning-state` | <Page name="LearningStatePage" /> |
| `/prediction` | <Page name="PredictionPage" /> |
| `/agent/final-review` | <Page name="FinalReviewPage" /> |
| `/agent/course-research` | <Page name="CourseResearchPage" /> |
| `/agent/notice-workflow` | <Page name="NoticeWorkflowPage" /> |
| `/final-review` | <Page name="FinalReviewPage" /> |
| `/course-research` | <Page name="CourseResearchPage" /> |
| `/island` | <Page name="IslandPage" /> |
| `/plans` | <Page name="PlansPage" /> |
| `/docs` | <Page name="DocsPage" /> |
| `/statistics` | <Page name="StatisticsPage" /> |
| `/exams` | <Page name="ExamsPage" /> |
| `/exams/:examId` | <Page name="ExamDetailPage" /> |
| `/exams/:examId/edit` | <Page name="ExamEditPage" /> |
| `/profile` | <Page name="ProfilePage" /> |
| `/profile/chaoxing` | <Page name="ChaoxingPage" /> |
| `/profile/academic` | <Page name="AcademicPage" /> |
| `/profile/settings` | <Page name="SettingsPage" /> |
| `/profile/:section` | <Page name="ProfileSectionPage" /> |
| `*` | <Navigate to="/" replace /> |

## HTTP 调用清单

| 封装位置 | 函数 | 方法 | 路径（相对 /api/v1） | 后端匹配 |
| --- | --- | --- | --- | --- |
| [webreact/src/data/agentApi.js:7](../../webreact/src/data/agentApi.js) | listCampaigns | GET | `/final-review/campaigns` | [期末复习与课程研究](13-workflows.md) |
| [webreact/src/data/agentApi.js:8](../../webreact/src/data/agentApi.js) | createCampaign | POST | `/final-review/campaigns` | [期末复习与课程研究](13-workflows.md) |
| [webreact/src/data/agentApi.js:9](../../webreact/src/data/agentApi.js) | generatePlan | POST | `/final-review/campaigns/{id}/plans/generate` | [期末复习与课程研究](13-workflows.md) |
| [webreact/src/data/agentApi.js:10](../../webreact/src/data/agentApi.js) | activatePlan | POST | `/final-review/campaigns/{id}/activate` | [期末复习与课程研究](13-workflows.md) |
| [webreact/src/data/agentApi.js:11](../../webreact/src/data/agentApi.js) | todayAgenda | GET | `/final-review/campaigns/{id}/agendas/today` | [期末复习与课程研究](13-workflows.md) |
| [webreact/src/data/agentApi.js:12](../../webreact/src/data/agentApi.js) | completeDailyItem | POST | `/final-review/daily-items/{id}/complete` | [期末复习与课程研究](13-workflows.md) |
| [webreact/src/data/agentApi.js:13](../../webreact/src/data/agentApi.js) | createResearch | POST | `/course-research/sessions` | 未匹配，见下一节 |
| [webreact/src/data/agentApi.js:14](../../webreact/src/data/agentApi.js) | createManualNotice | POST | `/notices/manual` | [个人待办、通知提取与通知事务](04-tasks-notices.md) |
| [webreact/src/data/agentApi.js:15](../../webreact/src/data/agentApi.js) | analyzeNotice | POST | `/notices/{id}/workflow` | [个人待办、通知提取与通知事务](04-tasks-notices.md) |
| [webreact/src/data/agentApi.js:16](../../webreact/src/data/agentApi.js) | confirmNotice | POST | `/notice-workflows/{id}/confirm` | 未匹配，见下一节 |
| [webreact/src/data/agentApi.js:17](../../webreact/src/data/agentApi.js) | executeNotice | POST | `/notice-workflows/{id}/execute` | 未匹配，见下一节 |
| [webreact/src/data/agentApi.js:20](../../webreact/src/data/agentApi.js) | createAgentEventStream | GET | `/agent-runs/{encodeURIComponent(runId)}/events/stream` | [Agent 运行时、审批、记忆、产物](12-agents.md) |
| [webreact/src/data/agentRuntimeApi.js:50](../../webreact/src/data/agentRuntimeApi.js) | getAgentCapabilities | GET | `/agent-runtime/capabilities` | [Agent 运行时、审批、记忆、产物](12-agents.md) |
| [webreact/src/data/agentRuntimeApi.js:54](../../webreact/src/data/agentRuntimeApi.js) | createAgentJob | POST | `/agent-jobs` | [Agent 运行时、审批、记忆、产物](12-agents.md) |
| [webreact/src/data/agentRuntimeApi.js:58](../../webreact/src/data/agentRuntimeApi.js) | getAgentJob | GET | `/agent-jobs/{jobId}` | [Agent 运行时、审批、记忆、产物](12-agents.md) |
| [webreact/src/data/agentRuntimeApi.js:62](../../webreact/src/data/agentRuntimeApi.js) | listAgentJobs | GET | `/agent-jobs` | [Agent 运行时、审批、记忆、产物](12-agents.md) |
| [webreact/src/data/agentRuntimeApi.js:66](../../webreact/src/data/agentRuntimeApi.js) | listAgentJobRuns | GET | `/agent-jobs/{jobId}/runs` | [Agent 运行时、审批、记忆、产物](12-agents.md) |
| [webreact/src/data/agentRuntimeApi.js:70](../../webreact/src/data/agentRuntimeApi.js) | getAgentRun | GET | `/agent-runs/{runId}` | [Agent 运行时、审批、记忆、产物](12-agents.md) |
| [webreact/src/data/agentRuntimeApi.js:74](../../webreact/src/data/agentRuntimeApi.js) | cancelAgentRun | POST | `/agent-runs/{runId}/cancel` | [Agent 运行时、审批、记忆、产物](12-agents.md) |
| [webreact/src/data/agentRuntimeApi.js:78](../../webreact/src/data/agentRuntimeApi.js) | pauseAgentRun | POST | `/agent-runs/{runId}/pause` | [Agent 运行时、审批、记忆、产物](12-agents.md) |
| [webreact/src/data/agentRuntimeApi.js:82](../../webreact/src/data/agentRuntimeApi.js) | resumeAgentRun | POST | `/agent-runs/{runId}/resume` | [Agent 运行时、审批、记忆、产物](12-agents.md) |
| [webreact/src/data/agentRuntimeApi.js:86](../../webreact/src/data/agentRuntimeApi.js) | retryAgentRun | POST | `/agent-runs/{runId}/retry` | [Agent 运行时、审批、记忆、产物](12-agents.md) |
| [webreact/src/data/agentRuntimeApi.js:90](../../webreact/src/data/agentRuntimeApi.js) | resolveAgentApproval | POST | `/agent-approvals/{approvalId}/decision` | [Agent 运行时、审批、记忆、产物](12-agents.md) |
| [webreact/src/data/agentRuntimeApi.js:94](../../webreact/src/data/agentRuntimeApi.js) | getAgentArtifact | GET | `/agent-artifacts/{artifactId}` | [Agent 运行时、审批、记忆、产物](12-agents.md) |
| [webreact/src/data/agentRuntimeApi.js:105](../../webreact/src/data/agentRuntimeApi.js) | createFinalReviewCampaign | POST | `/final-review/campaigns` | [期末复习与课程研究](13-workflows.md) |
| [webreact/src/data/agentRuntimeApi.js:109](../../webreact/src/data/agentRuntimeApi.js) | getFinalReviewCampaigns | GET | `/final-review/campaigns` | [期末复习与课程研究](13-workflows.md) |
| [webreact/src/data/agentRuntimeApi.js:116](../../webreact/src/data/agentRuntimeApi.js) | generateFinalReviewPlan | POST | `/final-review/campaigns/{campaignId}/plans/generate` | [期末复习与课程研究](13-workflows.md) |
| [webreact/src/data/agentRuntimeApi.js:120](../../webreact/src/data/agentRuntimeApi.js) | getFinalReviewPlanVersions | GET | `/final-review/campaigns/{campaignId}/plan-versions` | [期末复习与课程研究](13-workflows.md) |
| [webreact/src/data/agentRuntimeApi.js:124](../../webreact/src/data/agentRuntimeApi.js) | activateFinalReviewCampaign | POST | `/final-review/campaigns/{campaignId}/activate` | [期末复习与课程研究](13-workflows.md) |
| [webreact/src/data/agentRuntimeApi.js:128](../../webreact/src/data/agentRuntimeApi.js) | getTodayAgenda | GET | `/final-review/campaigns/{campaignId}/agendas/today` | [期末复习与课程研究](13-workflows.md) |
| [webreact/src/data/agentRuntimeApi.js:132](../../webreact/src/data/agentRuntimeApi.js) | completeFinalReviewItem | POST | `/final-review/daily-items/{itemId}/complete` | [期末复习与课程研究](13-workflows.md) |
| [webreact/src/data/agentRuntimeApi.js:136](../../webreact/src/data/agentRuntimeApi.js) | createDailyCheckin | POST | `/final-review/campaigns/{campaignId}/daily-checkins` | [期末复习与课程研究](13-workflows.md) |
| [webreact/src/data/agentRuntimeApi.js:140](../../webreact/src/data/agentRuntimeApi.js) | analyzeAdjustment | POST | `/final-review/campaigns/{campaignId}/adjustments/analyze` | [期末复习与课程研究](13-workflows.md) |
| [webreact/src/data/agentRuntimeApi.js:144](../../webreact/src/data/agentRuntimeApi.js) | resolveAdjustmentProposal | POST | `/final-review/adjustment-proposals/{proposalId}/decision` | [期末复习与课程研究](13-workflows.md) |
| [webreact/src/data/agentRuntimeApi.js:154](../../webreact/src/data/agentRuntimeApi.js) | getNotificationSources | GET | `/notification-sources` | [个人待办、通知提取与通知事务](04-tasks-notices.md) |
| [webreact/src/data/agentRuntimeApi.js:158](../../webreact/src/data/agentRuntimeApi.js) | updateNotificationSource | PATCH | `/notification-sources/{sourceId}` | [个人待办、通知提取与通知事务](04-tasks-notices.md) |
| [webreact/src/data/agentRuntimeApi.js:162](../../webreact/src/data/agentRuntimeApi.js) | createManualNotice | POST | `/notices/manual` | [个人待办、通知提取与通知事务](04-tasks-notices.md) |
| [webreact/src/data/agentRuntimeApi.js:166](../../webreact/src/data/agentRuntimeApi.js) | createNoticeWorkflow | POST | `/notices/{noticeId}/workflow` | [个人待办、通知提取与通知事务](04-tasks-notices.md) |
| [webreact/src/data/agentRuntimeApi.js:170](../../webreact/src/data/agentRuntimeApi.js) | getNoticeWorkflow | GET | `/notice-workflows/{workflowId}` | [个人待办、通知提取与通知事务](04-tasks-notices.md) |
| [webreact/src/data/agentRuntimeApi.js:174](../../webreact/src/data/agentRuntimeApi.js) | reanalyzeNoticeWorkflow | POST | `/notice-workflows/{workflowId}/reanalyze` | [个人待办、通知提取与通知事务](04-tasks-notices.md) |
| [webreact/src/data/agentRuntimeApi.js:178](../../webreact/src/data/agentRuntimeApi.js) | decideNoticeWorkflowAction | POST | `/notice-workflow-actions/{actionId}/decision` | [个人待办、通知提取与通知事务](04-tasks-notices.md) |
| [webreact/src/data/agentRuntimeApi.js:182](../../webreact/src/data/agentRuntimeApi.js) | executeNoticeWorkflowAction | POST | `/notice-workflow-actions/{actionId}/execute` | [个人待办、通知提取与通知事务](04-tasks-notices.md) |
| [webreact/src/data/agentRuntimeApi.js:188](../../webreact/src/data/agentRuntimeApi.js) | createCourseResearchRun | POST | `/course-research/runs` | [期末复习与课程研究](13-workflows.md) |
| [webreact/src/data/agentRuntimeApi.js:194](../../webreact/src/data/agentRuntimeApi.js) | cancelCourseResearchRun | POST | `/course-research/runs/{runId}/cancel` | [期末复习与课程研究](13-workflows.md) |
| [webreact/src/data/agentRuntimeApi.js:198](../../webreact/src/data/agentRuntimeApi.js) | getCourseResearchArtifacts | GET | `/course-research/runs/{runId}/artifacts` | [期末复习与课程研究](13-workflows.md) |
| [webreact/src/data/api.js:11](../../webreact/src/data/api.js) | getDashboard | GET | `/dashboard/student` | [首页、今日待办、横幅与壁纸](02-home.md) |
| [webreact/src/data/api.js:16](../../webreact/src/data/api.js) | getTodayAgenda | GET | `/agenda/today` | [首页、今日待办、横幅与壁纸](02-home.md) |
| [webreact/src/data/api.js:17](../../webreact/src/data/api.js) | getCourses | GET | `/courses` | [课程、班级、公告、作业与提交](03-courses.md) |
| [webreact/src/data/api.js:20](../../webreact/src/data/api.js) | getCourse | GET | `/courses/{courseId}` | [课程、班级、公告、作业与提交](03-courses.md) |
| [webreact/src/data/api.js:22](../../webreact/src/data/api.js) | getCourseDetail | GET | `/courses/{courseId}` | [课程、班级、公告、作业与提交](03-courses.md) |
| [webreact/src/data/api.js:22](../../webreact/src/data/api.js) | getCourseDetail | GET | `/courses/{courseId}/content-summary` | [课程、班级、公告、作业与提交](03-courses.md) |
| [webreact/src/data/api.js:22](../../webreact/src/data/api.js) | getCourseDetail | GET | `/courses/{courseId}/content` | [课程、班级、公告、作业与提交](03-courses.md) |
| [webreact/src/data/api.js:22](../../webreact/src/data/api.js) | getCourseDetail | GET | `/classes/{item.id}/assignments` | [课程、班级、公告、作业与提交](03-courses.md) |
| [webreact/src/data/api.js:22](../../webreact/src/data/api.js) | getCourseDetail | GET | `/classes/{item.id}/announcements` | [课程、班级、公告、作业与提交](03-courses.md) |
| [webreact/src/data/api.js:40](../../webreact/src/data/api.js) | syncCourse | POST | `/courses/{courseId}/sync` | [课程、班级、公告、作业与提交](03-courses.md) |
| [webreact/src/data/api.js:45](../../webreact/src/data/api.js) | getCourseKnowledgeGraph | GET | `/courses/{courseId}/knowledge-graph` | [课程、班级、公告、作业与提交](03-courses.md) |
| [webreact/src/data/api.js:48](../../webreact/src/data/api.js) | openCourseResource | GET | `/courses/{courseId}/resources/{itemId}/open` | [课程、班级、公告、作业与提交](03-courses.md) |
| [webreact/src/data/api.js:59](../../webreact/src/data/api.js) | downloadCourseResource | GET | `/courses/{courseId}/resources/{itemId}/download` | [课程、班级、公告、作业与提交](03-courses.md) |
| [webreact/src/data/api.js:64](../../webreact/src/data/api.js) | getAssignments | GET | `/student/assignments` | [课程、班级、公告、作业与提交](03-courses.md) |
| [webreact/src/data/api.js:65](../../webreact/src/data/api.js) | getTasks | GET | `/tasks` | [个人待办、通知提取与通知事务](04-tasks-notices.md) |
| [webreact/src/data/api.js:67](../../webreact/src/data/api.js) | getNotices | GET | `/notices` | [个人待办、通知提取与通知事务](04-tasks-notices.md) |
| [webreact/src/data/api.js:68](../../webreact/src/data/api.js) | getTask | GET | `/tasks/{id}` | [个人待办、通知提取与通知事务](04-tasks-notices.md) |
| [webreact/src/data/api.js:69](../../webreact/src/data/api.js) | createTask | POST | `/tasks` | [个人待办、通知提取与通知事务](04-tasks-notices.md) |
| [webreact/src/data/api.js:70](../../webreact/src/data/api.js) | analyzeTaskImport | POST | `/tasks/import/analyze` | [个人待办、通知提取与通知事务](04-tasks-notices.md) |
| [webreact/src/data/api.js:71](../../webreact/src/data/api.js) | commitTaskImport | POST | `/tasks/import/commit` | [个人待办、通知提取与通知事务](04-tasks-notices.md) |
| [webreact/src/data/api.js:72](../../webreact/src/data/api.js) | updateTask | PATCH | `/tasks/{id}` | [个人待办、通知提取与通知事务](04-tasks-notices.md) |
| [webreact/src/data/api.js:73](../../webreact/src/data/api.js) | completeTask | POST | `/tasks/{id}/complete` | [个人待办、通知提取与通知事务](04-tasks-notices.md) |
| [webreact/src/data/api.js:73](../../webreact/src/data/api.js) | completeTask | POST | `/tasks/{id}/restore` | [个人待办、通知提取与通知事务](04-tasks-notices.md) |
| [webreact/src/data/api.js:74](../../webreact/src/data/api.js) | deleteTask | DELETE | `/tasks/{id}` | [个人待办、通知提取与通知事务](04-tasks-notices.md) |
| [webreact/src/data/api.js:75](../../webreact/src/data/api.js) | getAssignment | GET | `/assignments/{id}` | [课程、班级、公告、作业与提交](03-courses.md) |
| [webreact/src/data/api.js:76](../../webreact/src/data/api.js) | getSubmission | GET | `/assignments/{id}/my-submission` | [课程、班级、公告、作业与提交](03-courses.md) |
| [webreact/src/data/api.js:77](../../webreact/src/data/api.js) | saveSubmission | POST | `/assignments/{id}/submissions` | [课程、班级、公告、作业与提交](03-courses.md) |
| [webreact/src/data/api.js:78](../../webreact/src/data/api.js) | submitSubmission | POST | `/submissions/{id}/submit` | [课程、班级、公告、作业与提交](03-courses.md) |
| [webreact/src/data/api.js:81](../../webreact/src/data/api.js) | getAnnouncement | GET | `/announcements/{id}` | [课程、班级、公告、作业与提交](03-courses.md) |
| [webreact/src/data/api.js:82](../../webreact/src/data/api.js) | markAnnouncementRead | POST | `/announcements/{id}/read` | [课程、班级、公告、作业与提交](03-courses.md) |
| [webreact/src/data/api.js:83](../../webreact/src/data/api.js) | getProfile | GET | `/auth/me` | [认证、账号与扫码登录](01-auth.md) |
| [webreact/src/data/api.js:84](../../webreact/src/data/api.js) | updateProfile | PATCH | `/auth/me` | [认证](01-auth.md) |
| [webreact/src/data/api.js:89](../../webreact/src/data/api.js) | getStudySessions | GET | `/study/sessions` | [专注学习、签到与专注 AI](05-study.md) |
| [webreact/src/data/api.js:90](../../webreact/src/data/api.js) | getActiveStudySession | GET | `/study/sessions/active` | [专注学习、签到与专注 AI](05-study.md) |
| [webreact/src/data/api.js:91](../../webreact/src/data/api.js) | getDailyStudyGoal | GET | `/study/goals/daily` | [专注学习、签到与专注 AI](05-study.md) |
| [webreact/src/data/api.js:92](../../webreact/src/data/api.js) | updateDailyStudyGoal | PUT | `/study/goals/daily` | [专注学习、签到与专注 AI](05-study.md) |
| [webreact/src/data/api.js:93](../../webreact/src/data/api.js) | startStudySession | POST | `/study/sessions` | [专注学习、签到与专注 AI](05-study.md) |
| [webreact/src/data/api.js:94](../../webreact/src/data/api.js) | pauseStudySession | POST | `/study/sessions/{id}/pause` | [专注学习、签到与专注 AI](05-study.md) |
| [webreact/src/data/api.js:95](../../webreact/src/data/api.js) | resumeStudySession | POST | `/study/sessions/{id}/resume` | [专注学习、签到与专注 AI](05-study.md) |
| [webreact/src/data/api.js:96](../../webreact/src/data/api.js) | finishStudySession | POST | `/study/sessions/{id}/finish` | [专注学习、签到与专注 AI](05-study.md) |
| [webreact/src/data/api.js:97](../../webreact/src/data/api.js) | breakdownStudyTask | POST | `/study/task-breakdown` | [专注学习、签到与专注 AI](05-study.md) |
| [webreact/src/data/api.js:106](../../webreact/src/data/api.js) | getStudyCheckins | GET | `/study/checkins` | [专注学习、签到与专注 AI](05-study.md) |
| [webreact/src/data/api.js:110](../../webreact/src/data/api.js) | createStudyCheckin | POST | `/study/checkins` | [专注学习、签到与专注 AI](05-study.md) |
| [webreact/src/data/api.js:118](../../webreact/src/data/api.js) | getKnowledgeDocuments | GET | `/knowledge/documents` | [AI 对话、语音与知识库](10-assistant-knowledge.md) |
| [webreact/src/data/api.js:120](../../webreact/src/data/api.js) | getExams | GET | `/student/exams` | [个人考试安排](07-exams.md) |
| [webreact/src/data/api.js:121](../../webreact/src/data/api.js) | saveExam | PATCH | `/student/exams/{id}` | [个人考试安排](07-exams.md) |
| [webreact/src/data/api.js:121](../../webreact/src/data/api.js) | saveExam | POST | `/student/exams` | [个人考试安排](07-exams.md) |
| [webreact/src/data/api.js:122](../../webreact/src/data/api.js) | deleteExam | DELETE | `/student/exams/{id}` | [个人考试安排](07-exams.md) |
| [webreact/src/data/api.js:123](../../webreact/src/data/api.js) | getUniversities | GET | `/universities` | [学校、个人文件与收藏](06-profile.md) |
| [webreact/src/data/api.js:124](../../webreact/src/data/api.js) | selectUniversity | PUT | `/profile/university` | [学校、个人文件与收藏](06-profile.md) |
| [webreact/src/data/api.js:126](../../webreact/src/data/api.js) | getCommunityPosts | GET | `/community/posts` | [校园社区与内容管理](08-community.md) |
| [webreact/src/data/api.js:127](../../webreact/src/data/api.js) | getCommunityCategories | GET | `/community/posts/categories` | [校园社区与内容管理](08-community.md) |
| [webreact/src/data/api.js:128](../../webreact/src/data/api.js) | getCommunityPost | GET | `/community/posts/{id}` | [校园社区与内容管理](08-community.md) |
| [webreact/src/data/api.js:129](../../webreact/src/data/api.js) | createCommunityPost | POST | `/community/posts` | [校园社区与内容管理](08-community.md) |
| [webreact/src/data/api.js:130](../../webreact/src/data/api.js) | updateCommunityPost | PUT | `/community/posts/{id}` | [校园社区与内容管理](08-community.md) |
| [webreact/src/data/api.js:131](../../webreact/src/data/api.js) | deleteCommunityPost | DELETE | `/community/posts/{id}` | [校园社区与内容管理](08-community.md) |
| [webreact/src/data/api.js:132](../../webreact/src/data/api.js) | likePost | POST | `/community/posts/{id}/like` | [校园社区与内容管理](08-community.md) |
| [webreact/src/data/api.js:133](../../webreact/src/data/api.js) | unlikePost | DELETE | `/community/posts/{id}/like` | [校园社区与内容管理](08-community.md) |
| [webreact/src/data/api.js:134](../../webreact/src/data/api.js) | favoritePost | POST | `/community/posts/{id}/favorite` | [校园社区与内容管理](08-community.md) |
| [webreact/src/data/api.js:135](../../webreact/src/data/api.js) | unfavoritePost | DELETE | `/community/posts/{id}/favorite` | [校园社区与内容管理](08-community.md) |
| [webreact/src/data/api.js:136](../../webreact/src/data/api.js) | getComments | GET | `/community/posts/{id}/comments` | [校园社区与内容管理](08-community.md) |
| [webreact/src/data/api.js:137](../../webreact/src/data/api.js) | createComment | POST | `/community/posts/{id}/comments` | [校园社区与内容管理](08-community.md) |
| [webreact/src/data/api.js:138](../../webreact/src/data/api.js) | uploadCommunityImage | POST | `/community/upload-image` | [校园社区与内容管理](08-community.md) |
| [webreact/src/data/api.js:152](../../webreact/src/data/api.js) | getAcademicStatus | GET | `/academic/status` | [学习通、教务连接与兼容接口](09-integrations.md) |
| [webreact/src/data/api.js:153](../../webreact/src/data/api.js) | getAcademicProviders | GET | `/academic/providers` | [学习通、教务连接与兼容接口](09-integrations.md) |
| [webreact/src/data/api.js:154](../../webreact/src/data/api.js) | getEduBinding | GET | `/edu/binding` | [学习通、教务连接与兼容接口](09-integrations.md) |
| [webreact/src/data/api.js:155](../../webreact/src/data/api.js) | bindEdu | POST | `/edu/bind` | [学习通、教务连接与兼容接口](09-integrations.md) |
| [webreact/src/data/api.js:156](../../webreact/src/data/api.js) | unbindEdu | DELETE | `/edu/binding` | [学习通、教务连接与兼容接口](09-integrations.md) |
| [webreact/src/data/api.js:157](../../webreact/src/data/api.js) | syncEdu | POST | `/edu/sync/schedule` | [学习通、教务连接与兼容接口](09-integrations.md) |
| [webreact/src/data/api.js:157](../../webreact/src/data/api.js) | syncEdu | POST | `/edu/sync/grade` | [学习通、教务连接与兼容接口](09-integrations.md) |
| [webreact/src/data/api.js:157](../../webreact/src/data/api.js) | syncEdu | POST | `/edu/sync/exam` | [学习通、教务连接与兼容接口](09-integrations.md) |
| [webreact/src/data/api.js:158](../../webreact/src/data/api.js) | getEduSyncRecords | GET | `/edu/sync/records` | [学习通、教务连接与兼容接口](09-integrations.md) |
| [webreact/src/data/api.js:160](../../webreact/src/data/api.js) | probeEduPortal | POST | `/edu/discovery/probe` | [学习通、教务连接与兼容接口](09-integrations.md) |
| [webreact/src/data/api.js:161](../../webreact/src/data/api.js) | createEduConnection | POST | `/edu/connections/from-url` | [学习通、教务连接与兼容接口](09-integrations.md) |
| [webreact/src/data/api.js:162](../../webreact/src/data/api.js) | getEduConnection | GET | `/edu/connections/{id}` | [学习通、教务连接与兼容接口](09-integrations.md) |
| [webreact/src/data/api.js:163](../../webreact/src/data/api.js) | continueEduConnection | POST | `/edu/connections/{id}/continue` | [学习通、教务连接与兼容接口](09-integrations.md) |
| [webreact/src/data/api.js:165](../../webreact/src/data/api.js) | preLoginEdu | POST | `/edu/connections/{id}/pre-login` | [学习通、教务连接与兼容接口](09-integrations.md) |
| [webreact/src/data/api.js:166](../../webreact/src/data/api.js) | getScheduleItems | GET | `/edu/schedule/items` | [学习通、教务连接与兼容接口](09-integrations.md) |
| [webreact/src/data/api.js:167](../../webreact/src/data/api.js) | getGradeItems | GET | `/edu/grade/items` | [学习通、教务连接与兼容接口](09-integrations.md) |
| [webreact/src/data/api.js:168](../../webreact/src/data/api.js) | getExamItems | GET | `/edu/exam/items` | [学习通、教务连接与兼容接口](09-integrations.md) |
| [webreact/src/data/api.js:170](../../webreact/src/data/api.js) | getChaoxingStatus | GET | `/chaoxing/status` | [学习通、教务连接与兼容接口](09-integrations.md) |
| [webreact/src/data/api.js:171](../../webreact/src/data/api.js) | loginChaoxing | POST | `/chaoxing/login` | [学习通、教务连接与兼容接口](09-integrations.md) |
| [webreact/src/data/api.js:174](../../webreact/src/data/api.js) | syncChaoxing | POST | `/chaoxing/sync` | [学习通、教务连接与兼容接口](09-integrations.md) |
| [webreact/src/data/api.js:175](../../webreact/src/data/api.js) | disconnectChaoxing | POST | `/chaoxing/disconnect` | [学习通、教务连接与兼容接口](09-integrations.md) |
| [webreact/src/data/api.js:184](../../webreact/src/data/api.js) | getInteractiveClassroomStatus | GET | `/courses/{courseId}/interactive-classroom/status` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:193](../../webreact/src/data/api.js) | getInteractiveClassroomPlan | GET | `/courses/{courseId}/interactive-classroom/plan` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:216](../../webreact/src/data/api.js) | generateInteractiveClassroom | POST | `/courses/{courseId}/interactive-classroom/generate` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:221](../../webreact/src/data/api.js) | getInteractiveClassroomComposition | GET | `/courses/{courseId}/interactive-classroom/{sessionId}/composition` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:226](../../webreact/src/data/api.js) | getInteractiveClassroomJob | GET | `/courses/{courseId}/interactive-classroom/jobs/{sessionId}` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:231](../../webreact/src/data/api.js) | listInteractiveClassrooms | GET | `/courses/{courseId}/interactive-classroom` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:240](../../webreact/src/data/api.js) | getMagicClassFusionStatus | GET | `/magicclass/fusion/status` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:248](../../webreact/src/data/api.js) | getMagicClassRecent | GET | `/magicclass/fusion/recent` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:252](../../webreact/src/data/api.js) | getMagicClassProviderStatus | GET | `/magicclass/fusion/providers` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:262](../../webreact/src/data/api.js) | getMagicClassCourseContext | GET | `/courses/{courseId}/magicclass-context` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:278](../../webreact/src/data/api.js) | listMagicClassWorkspaces | GET | `/courses/{courseId}/workspaces` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:286](../../webreact/src/data/api.js) | createMagicClassWorkspace | POST | `/courses/{courseId}/workspaces` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:296](../../webreact/src/data/api.js) | getMagicClassWorkspace | GET | `/courses/{courseId}/workspaces/{workspaceId}` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:307](../../webreact/src/data/api.js) | updateMagicClassWorkspace | PATCH | `/courses/{courseId}/workspaces/{workspaceId}` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:319](../../webreact/src/data/api.js) | deleteMagicClassWorkspace | DELETE | `/courses/{courseId}/workspaces/{workspaceId}` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:327](../../webreact/src/data/api.js) | listMagicClassStages | GET | `/courses/{courseId}/workspaces/{workspaceId}/stages` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:335](../../webreact/src/data/api.js) | getMagicClassStage | GET | `/courses/{courseId}/workspaces/{workspaceId}/stages/{stageId}` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:339](../../webreact/src/data/api.js) | createMagicClassStage | POST | `/courses/{courseId}/workspaces/{workspaceId}/stages` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:349](../../webreact/src/data/api.js) | replaceMagicClassStage | PUT | `/courses/{courseId}/workspaces/{workspaceId}/stages/{stageId}` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:360](../../webreact/src/data/api.js) | generateMagicClassStage | POST | `/courses/{courseId}/workspaces/{workspaceId}/generate` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:369](../../webreact/src/data/api.js) | generateMagicClassHome | POST | `/courses/{courseId}/home-generate` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:377](../../webreact/src/data/api.js) | getMagicClassJob | GET | `/courses/{courseId}/jobs/{jobId}` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:381](../../webreact/src/data/api.js) | cancelMagicClassJob | POST | `/courses/{courseId}/jobs/{jobId}/cancel` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:385](../../webreact/src/data/api.js) | retryMagicClassJob | POST | `/courses/{courseId}/jobs/{jobId}/retry` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:389](../../webreact/src/data/api.js) | synthesizeMagicClassTts | POST | `/courses/{courseId}/tts` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:397](../../webreact/src/data/api.js) | runMagicClassDiscussion | POST | `/courses/{courseId}/discussion` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:412](../../webreact/src/data/api.js) | getMagicClassSceneNarration | GET | `/courses/{courseId}/workspaces/{workspaceId}/stages/{stageId}/scenes/{sceneId}/narration` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:425](../../webreact/src/data/api.js) | synthesizeMagicClassSceneNarration | POST | `/courses/{courseId}/workspaces/{workspaceId}/stages/{stageId}/scenes/{sceneId}/narration` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:434](../../webreact/src/data/api.js) | getMagicClassArtifact | GET | `/courses/{courseId}/artifacts/{artifactId}` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:443](../../webreact/src/data/api.js) | enqueueMagicClassStageVideo | POST | `/courses/{courseId}/workspaces/{workspaceId}/stages/{stageId}/export/video` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:451](../../webreact/src/data/api.js) | addMagicClassWhiteboard | POST | `/courses/{courseId}/workspaces/{workspaceId}/stages/{stageId}/whiteboard` | 未匹配，见下一节 |
| [webreact/src/data/api.js:464](../../webreact/src/data/api.js) | listMagicClassFolders | GET | `/courses/{courseId}/folders` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:472](../../webreact/src/data/api.js) | createMagicClassFolder | POST | `/courses/{courseId}/folders` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:484](../../webreact/src/data/api.js) | updateMagicClassFolder | PATCH | `/courses/{courseId}/folders/{folderId}` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:495](../../webreact/src/data/api.js) | deleteMagicClassFolder | DELETE | `/courses/{courseId}/folders/{folderId}` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:503](../../webreact/src/data/api.js) | searchMagicClassContent | GET | `/courses/{courseId}/search` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:517](../../webreact/src/data/api.js) | listMagicClassMaterials | GET | `/courses/{courseId}/materials` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:525](../../webreact/src/data/api.js) | uploadMagicClassMaterial | POST | `/courses/{courseId}/materials` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:536](../../webreact/src/data/api.js) | getMagicClassMaterial | GET | `/courses/{courseId}/materials/{materialId}` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:540](../../webreact/src/data/api.js) | deleteMagicClassMaterial | DELETE | `/courses/{courseId}/materials/{materialId}` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:549](../../webreact/src/data/api.js) | resolveMagicClassMaterials | POST | `/courses/{courseId}/materials/resolve` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:570](../../webreact/src/data/api.js) | exportMagicClassStage | GET | `/courses/{courseId}/workspaces/{workspaceId}/stages/{stageId}/export` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:578](../../webreact/src/data/api.js) | exportMagicClassStageFormat | GET | `/courses/{courseId}/workspaces/{workspaceId}/stages/{stageId}/export/{format}` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:586](../../webreact/src/data/api.js) | importMagicClassStage | POST | `/courses/{courseId}/workspaces/{workspaceId}/import` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:596](../../webreact/src/data/api.js) | importMagicClassPptx | POST | `/courses/{courseId}/workspaces/{workspaceId}/import/pptx` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:612](../../webreact/src/data/api.js) | getMagicClassStageOutline | GET | `/courses/{courseId}/workspaces/{workspaceId}/stages/{stageId}/outline` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:619](../../webreact/src/data/api.js) | getMagicClassStagePlayback | GET | `/courses/{courseId}/workspaces/{workspaceId}/stages/{stageId}/playback` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:627](../../webreact/src/data/api.js) | getMagicClassStageScene | GET | `/courses/{courseId}/workspaces/{workspaceId}/stages/{stageId}/scenes/{sceneId}` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:635](../../webreact/src/data/api.js) | getMagicClassQuizAttempt | GET | `/courses/{courseId}/workspaces/{workspaceId}/stages/{stageId}/scenes/{sceneId}/quiz-attempt` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:639](../../webreact/src/data/api.js) | saveMagicClassQuizAttempt | POST | `/courses/{courseId}/workspaces/{workspaceId}/stages/{stageId}/scenes/{sceneId}/quiz-attempt` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:643](../../webreact/src/data/api.js) | applyMagicClassStageCommands | POST | `/courses/{courseId}/workspaces/{workspaceId}/stages/{stageId}/commands` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:654](../../webreact/src/data/api.js) | retryInteractiveClassroom | POST | `/courses/{courseId}/interactive-classroom/{sessionId}/retry` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/data/api.js:659](../../webreact/src/data/api.js) | createAgentJob | POST | `/agent-jobs` | [Agent 运行时、审批、记忆、产物](12-agents.md) |
| [webreact/src/data/api.js:664](../../webreact/src/data/api.js) | getAgentJob | GET | `/agent-jobs/{jobId}` | [Agent 运行时、审批、记忆、产物](12-agents.md) |
| [webreact/src/data/api.js:669](../../webreact/src/data/api.js) | decideAgentApproval | POST | `/agent-approvals/{approvalId}/decision` | [Agent 运行时、审批、记忆、产物](12-agents.md) |
| [webreact/src/data/api.js:678](../../webreact/src/data/api.js) | chatStream | POST | `/counselor/chat` | [AI 对话、语音与知识库](10-assistant-knowledge.md) |
| [webreact/src/data/api.js:737](../../webreact/src/data/api.js) | streamAssistantSpeech | POST | `/assistant/tts` | [AI 对话、语音与知识库](10-assistant-knowledge.md) |
| [webreact/src/data/api.js:749](../../webreact/src/data/api.js) | extractNotice | POST | `/notices/extract-multi` | [个人待办、通知提取与通知事务](04-tasks-notices.md) |
| [webreact/src/data/api.js:751](../../webreact/src/data/api.js) | downloadAssignmentAttachment | GET | `/assignments/{assignmentId}/attachments/{attachmentId}` | [课程、班级、公告、作业与提交](03-courses.md) |
| [webreact/src/data/http/authEndpoints.js:5](../../webreact/src/data/http/authEndpoints.js) | probeBackend | GET | `/health` | [首页、今日待办、横幅与壁纸](02-home.md) |
| [webreact/src/data/http/authEndpoints.js:9](../../webreact/src/data/http/authEndpoints.js) | login | POST | `/auth/login` | [认证、账号与扫码登录](01-auth.md) |
| [webreact/src/data/http/authEndpoints.js:9](../../webreact/src/data/http/authEndpoints.js) | login | GET | `/auth/me` | [认证、账号与扫码登录](01-auth.md) |
| [webreact/src/data/http/authEndpoints.js:25](../../webreact/src/data/http/authEndpoints.js) | qrCreate | POST | `/auth/qr/create` | [认证、账号与扫码登录](01-auth.md) |
| [webreact/src/data/http/authEndpoints.js:26](../../webreact/src/data/http/authEndpoints.js) | qrStatus | GET | `/auth/qr/{sessionId}/status` | [认证、账号与扫码登录](01-auth.md) |
| [webreact/src/data/http/authEndpoints.js:27](../../webreact/src/data/http/authEndpoints.js) | qrExchange | POST | `/auth/qr/exchange` | [认证、账号与扫码登录](01-auth.md) |
| [webreact/src/data/http/authEndpoints.js:28](../../webreact/src/data/http/authEndpoints.js) | trustedDeviceAutoLogin | POST | `/auth/trusted-device/auto-login` | [认证、账号与扫码登录](01-auth.md) |
| [webreact/src/data/http/authEndpoints.js:32](../../webreact/src/data/http/authEndpoints.js) | revokeTrustedDevice | POST | `/auth/trusted-device/revoke` | [认证、账号与扫码登录](01-auth.md) |
| [webreact/src/data/http/client.js:205](../../webreact/src/data/http/client.js) | refreshAccessToken | POST | `/auth/refresh` | [认证、账号与扫码登录](01-auth.md) |
| [webreact/src/data/learnerStateApi.js:34](../../webreact/src/data/learnerStateApi.js) | getLearnerStateRuns | GET | `/learner-state/runs` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md)；封装尚未透传新增 projection_kind |
| [webreact/src/data/learnerStateApi.js:38](../../webreact/src/data/learnerStateApi.js) | getLearnerStateChanges | GET | `/learner-state/changes` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md)；封装尚未透传新增 projection_kind |
| [webreact/src/data/learnerStateApi.js:49](../../webreact/src/data/learnerStateApi.js) | getLearnerStateSnapshots | GET | `/learner-state/snapshots` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learnerStateApi.js:61](../../webreact/src/data/learnerStateApi.js) | getSnapshotEvidence | GET | `/learner-state/snapshots/{snapshotId}/evidence` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learnerStateApi.js:67](../../webreact/src/data/learnerStateApi.js) | generateLearningPlan | POST | `/learning-plans/generate` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learnerStateApi.js:71](../../webreact/src/data/learnerStateApi.js) | getLearningPlans | GET | `/learning-plans` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learnerStateApi.js:75](../../webreact/src/data/learnerStateApi.js) | getAdaptiveInterventions | GET | `/adaptive-interventions` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learnerStateApi.js:79](../../webreact/src/data/learnerStateApi.js) | getAdaptiveInterventionOutcome | GET | `/adaptive-interventions/{interventionId}/outcome` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learnerStateApi.js:83](../../webreact/src/data/learnerStateApi.js) | getLearningPlan | GET | `/learning-plans/{planId}` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learnerStateApi.js:87](../../webreact/src/data/learnerStateApi.js) | decideLearningPlan | POST | `/learning-plans/{planId}/decision` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learnerStateApi.js:91](../../webreact/src/data/learnerStateApi.js) | executeLearningPlan | POST | `/learning-plans/{planId}/execute` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learnerStateApi.js:95](../../webreact/src/data/learnerStateApi.js) | undoLearningPlan | POST | `/learning-plans/{planId}/undo` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learnerStateApi.js:99](../../webreact/src/data/learnerStateApi.js) | replanLearningPlan | POST | `/learning-plans/{planId}/replan` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learnerStateApi.js:103](../../webreact/src/data/learnerStateApi.js) | submitPlanFeedback | POST | `/learning-plans/{planId}/feedback` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learnerStateApi.js:107](../../webreact/src/data/learnerStateApi.js) | getPlanEvaluation | GET | `/learning-plans/{planId}/evaluation` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learnerStateApi.js:111](../../webreact/src/data/learnerStateApi.js) | getPlanSummary | GET | `/learning-plans/{planId}/summary` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learnerStateApi.js:117](../../webreact/src/data/learnerStateApi.js) | createCorrection | POST | `/learner-state/corrections` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learnerStateApi.js:121](../../webreact/src/data/learnerStateApi.js) | getCorrections | GET | `/learner-state/corrections` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learnerStateApi.js:125](../../webreact/src/data/learnerStateApi.js) | revokeCorrection | POST | `/learner-state/corrections/{correctionId}/revoke` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learnerStateApi.js:131](../../webreact/src/data/learnerStateApi.js) | getDataControls | GET | `/learner-state/data-controls` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learnerStateApi.js:135](../../webreact/src/data/learnerStateApi.js) | updateDataControl | PUT | `/learner-state/data-controls/{sourceKey}` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learnerStateApi.js:141](../../webreact/src/data/learnerStateApi.js) | requestDeletion | POST | `/learner-state/delete-request` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learnerStateApi.js:145](../../webreact/src/data/learnerStateApi.js) | getDeleteStatus | GET | `/learner-state/delete-status` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learnerStateApi.js:151](../../webreact/src/data/learnerStateApi.js) | getDataSummary | GET | `/learner-state/data-summary` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learnerStateApi.js:157](../../webreact/src/data/learnerStateApi.js) | getModelTransparency | GET | `/learner-state/model-transparency` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learnerStateApi.js:163](../../webreact/src/data/learnerStateApi.js) | getForecasts | GET | `/learner-state/forecasts` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learnerStateApi.js:176](../../webreact/src/data/learnerStateApi.js) | createSimulation | POST | `/learner-state/simulations` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learnerStateApi.js:182](../../webreact/src/data/learnerStateApi.js) | getStudentGoals | GET | `/student-goals` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learnerStateApi.js:191](../../webreact/src/data/learnerStateApi.js) | createStudentGoal | POST | `/student-goals` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learnerStateApi.js:195](../../webreact/src/data/learnerStateApi.js) | updateStudentGoal | PATCH | `/student-goals/{goalId}` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learnerStateApi.js:199](../../webreact/src/data/learnerStateApi.js) | recordGoalProgress | POST | `/student-goals/{goalId}/progress` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learnerStateApi.js:203](../../webreact/src/data/learnerStateApi.js) | archiveStudentGoal | POST | `/student-goals/{goalId}/archive` | [学习状态、预测、模拟、目标与自适应计划](11-learner.md) |
| [webreact/src/data/learningSpaceApi.js:11](../../webreact/src/data/learningSpaceApi.js) | getLearningSpaceStatus | GET | `/magicclass/learning-space/status` | [课程互动课堂、受管工作台与学习空间入口](14-magicclass.md) |
| [webreact/src/magicclass/scene/quiz-view.jsx:121](../../webreact/src/magicclass/scene/quiz-view.jsx) | gradeShortAnswerQuestion | POST | `/api/quiz-grade` | 未匹配，见下一节 |

## 无对应注册路由的调用与核对边界

以下是当前代码中保留的调用，不能据此给新前端实现出一个不存在的 API。活动模块已移除，旧 agentApi 仍有旧路径；未在当前页面使用的封装仍需避开。本人资料更新已使用 `PATCH /auth/me`。普通请求优先复用 api.js、agentRuntimeApi.js、learnerStateApi.js 中与本手册匹配的函数。

| 方法 | 路径 | 函数 | 说明 |
| --- | --- | --- | --- |
| POST | `/course-research/sessions` | createResearch | 应使用 POST /course-research/runs |
| POST | `/notice-workflows/{id}/confirm` | confirmNotice | 审批与执行使用 /notice-workflow-actions/{action_id}/decision 和 /execute |
| POST | `/notice-workflows/{id}/execute` | executeNotice | 审批与执行使用 /notice-workflow-actions/{action_id}/decision 和 /execute |
| GET | `/activities` | getActivities | 旧活动封装；后端未注册活动接口 |
| GET | `/activities/{id}` | getActivity | 旧活动封装；后端未注册活动接口 |
| GET | `/activities/{id}/registration` | getActivityRegistration | 旧活动封装；后端未注册活动接口 |
| POST | `/activities/{id}/registration` | registerActivity | 旧活动封装；后端未注册活动接口 |
| DELETE | `/activities/{id}/registration` | cancelActivityRegistration | 旧活动封装；后端未注册活动接口 |
| POST | `/courses/{courseId}/workspaces/{workspaceId}/stages/{stageId}/whiteboard` | addMagicClassWhiteboard | 受管服务有内部实现，但 CampusMate 网关未注册该公开路径；新前端不能直接调用内部服务 |
| POST | `/api/quiz-grade` | gradeShortAnswerQuestion | magicclass 源码保留的独立上游路径；不是本站 /api/v1 接口，本站测验使用[课程场景 quiz-attempt 契约](14-magicclass.md) |

覆盖方式：314 个后端操作均单独列入模块手册；没有 Web 封装的接口也保留。调用清单通过字面量 HTTP 调用及 _get/_post/_put/_patch 封装核对，动态 fetch 的聊天、Agent SSE、音频请求由协议文档补充。独立学习空间在 iframe 内发往自己的 Origin，见 [学习空间 API](learning-space.md)，不能拼接本站 /api/v1。

## 动态地址与流式调用补充

以下请求的地址由返回字段或局部变量构造，不能仅靠字面量列表覆盖。

| Web 位置 | 请求 | 地址与解析 |
| --- | --- | --- |
| [data/http/client.js](../../webreact/src/data/http/client.js) | Axios POST 刷新令牌 | baseUrl + /auth/refresh；已纳入上表与认证模块 |
| [data/agentRuntimeApi.js](../../webreact/src/data/agentRuntimeApi.js) | client.get/post/patch(path) 共 3 个内部包装调用 | 实际地址来自本文件 _get/_post/_patch 调用点，已逐项纳入上表；不是额外接口 |
| [data/learnerStateApi.js](../../webreact/src/data/learnerStateApi.js) | client.get/post/put/patch(path) 共 4 个内部包装调用 | 实际地址来自本文件 _get/_post/_put/_patch 调用点，已逐项纳入上表 |
| [pages/CourseResearchPage.jsx](../../webreact/src/pages/CourseResearchPage.jsx) | client.get(target.download_url) / client.get(art.download_url) | 研究产物 download_url，分别 text / blob；返回路径为 /agent-artifacts/{artifact_id}/content，Axios 按 baseURL 拼接 /api/v1 并沿用 Bearer 拦截器 |
| [pages/FinalReviewPage.jsx](../../webreact/src/pages/FinalReviewPage.jsx) | client.get(art.download_url) | 复习产物下载，responseType=blob；按 mime_type 展示或保存 |
| [data/agentSseStream.js](../../webreact/src/data/agentSseStream.js) | fetch_ 别名请求 | Agent /events/stream；续传、错误与终态见 [Agent 协议](integration.md#agents) |
| [data/api.js](../../webreact/src/data/api.js) | fetch 动态 API 地址 | 聊天 SSE / assistant/tts；见 [聊天与音频协议](integration.md#chat) |

当前 Web 未创建实时语音 WebSocket；后端已经注册的 /focus/realtime-voice/ws/{session_id} 仍完整列入 [实时语音协议](response-contracts.md#voice)。

2026-10-08 新增设备及学习偏好接口本轮未开发 Web 封装，客户端适配待后续任务；完整契约见[设备](15-devices.md)及[学习状态](11-learner.md)。
