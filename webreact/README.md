# CampusMate React Web

这是 CampusMate 当前唯一的 Web 客户端，使用 React 18、React Router、Vite 和 Axios。它不依赖 Vue、Pinia 或 Vue 组件，源码位于本目录。

现有业务接口继续从 `src/data/api.js` 导入；`src/data/api/client.js` 负责 Axios 客户端与令牌刷新，`src/data/api/authEndpoints.js` 负责登录相关接口。

## 开发

```bash
npm install
npm run dev
```

开发服务器默认使用 `http://127.0.0.1:5174`，`/api` 和 `/static` 会代理到本地 FastAPI `8000` 端口。生产构建使用 `npm run build`。

## 验证

```bash
npm test
python tests/e2e/route-smoke.py
```

E2E 脚本需要先运行 `npm run dev`；它覆盖登录保护、全部路由族、桌面与移动端导航。
