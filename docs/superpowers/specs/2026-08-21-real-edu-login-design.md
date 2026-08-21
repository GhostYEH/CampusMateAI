# 真实教务登录与课表导入设计

## 目标

Android 端连接真实教务系统时，不再把真实用户降级为 mock 数据；无验证码时直接登录，有图片验证码、滑块、短信或多因素验证时自动打开应用内 WebView，由用户本人完成验证。登录成功后必须验证服务端会话、抓取课表、持久化，并通过读取持久化课表确认导入成功。

河南财经政法大学（`https://xk.huel.edu.cn/jwglxt/xtgl/login_slogin.html`）是首个黄金学校。该站点已经验证为正方 JWGL2：初始页面具有 `csrftoken`、`yhm`、`mm` 字段，登录前通过 `login_getPublicKey.html` 获取 RSA 公钥；初始页无验证码，连续错误后才要求验证码。

## 非目标

- 不识别、破解或自动填写任何验证码、短信验证码、滑块或 MFA。
- 不把真实账号、密码、Cookie、CSRF token、响应正文或课程内容加入代码、夹具、日志、错误消息或提交。
- 不在生产、开发或 Android 客户端的真实连接流程中回退到 MockEduAdapter；mock 只供显式测试数据使用。

## 状态与数据流

1. Android 提交学校 URL 与账号密码，后端探测页面的 provider、登录字段、验证码可见性和登录模式。
2. 对无验证码且支持的正方表单，Adapter 获取初始 Cookie/CSRF/RSA 公钥，RSA 加密密码并提交表单。
3. 登录响应若成功，Adapter 以受保护接口验证身份，Connector 建立内存会话和真实 binding。
4. 若初始页面或提交响应表明需要人工操作，Adapter 抛出 `NeedUserAction`；Connector 将连接切换为 `waiting_user_login`，保存不含敏感值的错误码和登录 URL。
5. Android 检测该状态后自动导航至既有 WebView。用户在学校页面完成操作；应用仅回传 Cookie、当前 URL 与 user agent，服务端再次访问受保护身份接口校验。
6. Connector 依次同步 profile、schedule、grade。课表响应只有在 `status=success`、`items_count>0` 且 `persisted=true` 时才算导入成功；Android 再读取 `/edu/schedule/items` 确认条数大于零再显示“查看课表”。

## 后端边界

- `ZhengfangHttpClient` 负责 Cookie、请求和 SSRF 防护；新增的轻量页面/公钥读取能力只返回必要字段。
- `ZhengfangAdapter` 负责 JWGL2 表单协议和从响应中识别人工验证，不保存密码。
- `EduConnectorService` 负责把 `NeedUserAction` 映射为稳定的连接状态，禁止真实 provider 的 mock fallback，并在同步失败时保留可读错误。
- 真实配置必须来自已验证的 `edu_systems` 或本次明确输入的 URL；河南财经政法大学配置会使用 `zhengfang`、`jwgl2`、`backend_http`、已验证登录 URL 与适配器端点覆盖。

## Android 边界

- `EduViewModel` 只根据连接状态触发导航；无验证码成功时绝不创建 WebView。
- `EduSystemScreen` 根据 `waiting_user_login` 自动发出一次性打开登录页事件，并清楚标识真实/不支持/仅测试 mock 状态。
- `EduLoginScreen` 保持密码和验证交给学校页面，回传 Cookie 后等待服务端确认，不在 UI 中显示敏感状态。

## 验收

1. 单元测试覆盖：无验证码直接登录、图片验证码转 WebView、Cookie 回传验证、未知/未实现 provider 不回退 mock、课表持久化失败不报成功。
2. Android 单元测试覆盖：等待用户操作状态只触发一次浏览器事件，且持久化课表为空时显示失败。
3. 真实黄金学校验收仅在本次会话中使用用户提供的凭证：确认直登或明确转入 WebView；成功后验证绑定 provider 为 `zhengfang`，同步结果已持久化，`/edu/schedule/items` 返回至少一条真实课程。若校方触发验证码，则由用户在前端浏览器完成，之后自动继续相同验证。
