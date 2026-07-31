# CampusMate AI Vue Web

独立的 Vue 3 Web 前端，基于移动端功能与 FastAPI 接口实现。

## 本地运行

```powershell
npm install
npm run dev
```

默认地址：`http://127.0.0.1:5173`

## 后端连接

Web 端统一使用真实 FastAPI 接口，不再提供 Mock 模式或本地演示数据分支。
启动 `backend` 后，使用后端数据库中的账号登录；API 地址可通过 `VITE_API_BASE_URL` 配置，默认走 Vite 代理 `/api/v1`。

## 构建

```powershell
npm run build
```
