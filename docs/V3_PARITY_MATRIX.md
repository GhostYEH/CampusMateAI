# CampusMateAI V3 Parity Matrix

更新日期：2026-08-13

状态定义：`DONE` 已接真实 Backend 且有验证；`PARTIAL` 有可用纵向链路但未覆盖完整产品规格；`PLATFORM_LIMITED` 受本机工具链限制；`MISSING` 尚未实现。

| 能力 | Backend | Android | HarmonyOS | Web | 说明 |
| --- | --- | --- | --- | --- | --- |
| 大学列表/搜索/选择 | DONE | DONE | PARTIAL | DONE | HarmonyOS 已接同一 API 和选择流，待真实设备/DevEco 编译确认 |
| University scoped 社区帖子 | DONE | DONE | PARTIAL | DONE | 帖子列表、发布、匿名、点赞/收藏；详情、图片上传和完整评论 UI 尚未覆盖三端 |
| 社区治理 | PARTIAL | N/A | N/A | MISSING | Backend 已有举报和管理员隐藏；举报列表、评论治理、封禁与限流尚缺 |
| LostFound 大学隔离 | DONE | DONE | DONE | DONE | Backend 过滤并对非所有者隐藏 private contact；现有三端复用原页面 |
| Academic Provider 抽象 | DONE | DONE | PARTIAL | DONE | 当前仅 truthful `unsupported`，不伪造学校支持，不持久化客户端密码 |
| 课表/成绩/考试同步 | MISSING | MISSING | MISSING | MISSING | 没有经验证的真实学校 Provider，保留手动课程与既有考试能力 |
| 教师端清理 | PARTIAL | DONE | DONE | DONE | Web 教师页面/路由已删；Backend 历史字段与旧路由待兼容退役 |
| 审批式办事大厅清理 | PARTIAL | DONE | DONE | PARTIAL | Android/Harmony 运行时入口移除；历史文件/表和 Web 旧能力待后续兼容清理 |
| 大学主页 | MISSING | MISSING | MISSING | MISSING | 本轮纵向切片未实现 |

## 验证证据

- Backend：`python -m pytest -q` → `175 passed, 17 warnings`。
- Android：JDK 17、隔离 Gradle project cache 下 `gradlew testDebugUnitTest` → `BUILD SUCCESSFUL`。
- Web：`node --test tests/*.test.mjs` → `17 passed`；`npm run build` 成功，保留既有大 chunk 警告。
- HarmonyOS：模型、入口和同构页面已落盘；当前环境缺少项目可执行的 Hvigor wrapper / DevEco CLI，状态不升级为 DONE。
- `git diff --check`：通过，仅有工作区 CRLF 提示。

## 已知环境噪声

- pytest 结束时 Windows 临时目录 `pytest-current` symlink 清理出现 `WinError 5`，测试进程本身退出码为 0。
- Android 系统默认 JDK 26 不兼容当前 Gradle，验证固定使用项目可用 JDK 17。
