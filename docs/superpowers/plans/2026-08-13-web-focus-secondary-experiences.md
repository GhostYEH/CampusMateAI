# Web 专注二级体验实现计划

1. 添加结构测试，锁定六类入口、对话框语义、关键动效和降级规则。
2. 创建 `StudyExperienceLayer.vue`，集中承载六类体验及键盘/遮罩关闭逻辑。
3. 在 `StudentStudyView.vue` 接通现有会话、AI 拆解和任务 API。
4. 添加 `study-secondary.css`，实现响应式动态层与非默认动效。
5. 更新旧交互契约，运行完整 Web 测试、生产构建和浏览器视觉检查。
