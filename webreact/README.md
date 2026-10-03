# CampusMate React Web

这是 CampusMate 当前唯一的 Web 客户端，使用 React 18、React Router、Vite 和 Axios。它不依赖 Vue、Pinia 或 Vue 组件，源码位于本目录。

现有业务接口继续从 `src/data/api.js` 导入；`src/data/http/client.js` 负责 Axios 客户端与令牌刷新，`src/data/http/authEndpoints.js` 负责登录相关接口。

## 主要入口

- `/counselor`：通用 AI 助手界面。当前调用后端兼容接口 `/api/v1/counselor/chat`，后端对非问候问题仍会检索现有校园知识库；详见[主 README](../README.md)。
- `/notifications`、`/tasks`、`/profile/chaoxing`：查看服务端整理的通知与待办、连接并同步学习通。Web 不读取手机系统通知，微信/QQ 消息接入发生在获授权的 Android 端。
- `/courses/:courseId/classroom`、`/courses/:courseId/workspaces/:workspaceId`：课程内互动课堂，可创建或复用工作台、生成场景、编辑、播放和导出；实际可用性取决于受管服务及模型配置。
- `/learning-space`：导航栏“学习空间”，经后端状态校验后内嵌独立进程运行的 `magicclass-app`。未配置公开 Origin 或服务不可达时会显示原因。

## 开发

```bash
npm install
npm run dev
```

开发服务器默认使用 `http://127.0.0.1:5174`，`/api` 和 `/static` 会代理到本地 FastAPI `8000` 端口。生产构建使用 `npm run build`。体验完整在线课堂链路时，在仓库根目录运行 `start_all.bat` 启动受管服务、后端、独立学习空间和 Web。

## 验证

```bash
npm run lint
npm test
npm run build
python tests/e2e/route-smoke.py
```

`lint` 检查全部 JS/JSX/TS/TSX 源码的基础错误、未使用符号及 Hook 调用规则；它不替代 TypeScript 类型检查。测试还会检查实际生产分包，防止路由专属引擎和样式进入首屏。

学习状态页由 `pages/LearningStatePage.jsx` 编排，数据与操作在 `hooks/useLearningState.js`，展示组件在 `components/learningState/`。学习状态页与趋势页共用 `useAsyncResource`，避免刷新或切换条件时旧响应覆盖新结果。

E2E 脚本需要先运行 `npm run dev`；它覆盖登录保护、全部路由族、桌面与移动端导航。
