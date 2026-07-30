# CampusMate AI Vue Web

独立的 Vue 3 Web 前端，基于移动端功能与 FastAPI 接口实现。

## 本地运行

```powershell
npm install
npm run dev
```

默认地址：`http://127.0.0.1:5173`

## 数据模式

- 默认使用 Mock 模式，演示账号密码统一为 `Demo123456`：
  - `student_demo`
  - `teacher_demo`
  - `admin_demo`
- 设置 `VITE_API_BASE_URL` 并将 `campus_mock_mode` 设为 `false` 后使用真实后端。
- 所有 AI、知识库和表情识别 Mock 能力均在页面中明确标注。

## 构建

```powershell
npm run build
```
