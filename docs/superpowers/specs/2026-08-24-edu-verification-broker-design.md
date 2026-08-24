# 教务系统应用内验证代理设计

## 背景与目标

CampusMate 已有教务连接状态机、正方适配器、图片验证码表单以及 Android WebView / Harmony ArkWeb 页面，但当前实现存在以下断点：

- 登录页出现图片验证码时会被直接分流到 WebView，绕过图片抽取表单。
- 验证码响应按文本解码，可能破坏 PNG/JPEG 原始字节。
- Web 普通浏览器无法可靠 iframe 嵌入学校页面。
- Cookie 被压平成无域名信息的键值对，跨域 SSO 容易丢失会话。
- 教务登录会话仅保存在单进程内存中，重启后失效。
- 强智、青果仍是占位适配器；正方也缺少真实学校金样验证。

本次目标是先以河南财经政法大学正方 JWGLXT 为真实金样，建立可复用的人机验证协议，使图片验证码在 CampusMate 表单内完成，复杂滑块、短信或 MFA 在应用内的短时交互浏览器中由用户本人完成，并让成功会话能够安全恢复和同步课表、成绩与考试数据。

## 已确认的学校协议

公开登录页为 `https://xk.huel.edu.cn/jwglxt/xtgl/login_slogin.html`，当前确认：

- 登录字段：`yhm`、`mm`、`csrftoken`，验证码字段 `yzm`。
- 密码使用 `/jwglxt/xtgl/login_getPublicKey.html` 返回的 RSA 公钥加密。
- 图片验证码端点为 `/jwglxt/kaptcha`。
- 登录会话使用路径为 `/jwglxt` 的 HttpOnly `JSESSIONID`。
- 响应包含 `X-Frame-Options: SAMEORIGIN`，普通 CampusMate Web 页面不能直接 iframe 嵌入。

账号密码属于临时联调输入，不进入源码、文档、测试夹具、数据库或日志。

## 总体架构

### 1. Verification Broker

后端新增明确的验证挑战模型，而不是用松散的 `error_code` 推断 UI：

- `none`：可以直接提交账号密码。
- `image`：后端提取原始图片字节和 MIME 类型，前端展示并收集文本答案。
- `interactive`：滑块、短信、MFA 或未知 JavaScript 挑战，进入交互浏览器。

每次预登录创建短时 `verification_session`，绑定：

- 当前 CampusMate 用户；
- 教务连接；
- 学校和允许的 origin；
- Cookie Jar、CSRF、公钥及挑战版本；
- 创建时间、过期时间和单次消费状态。

令牌不可跨用户、跨连接、跨学校使用；提交成功后立即销毁，失败后由服务端决定刷新挑战或继续交互。

### 2. 图片验证码路径

HTTP 响应同时保留 `content: bytes` 和用于 HTML/JSON 解析的 `text`。验证码下载验证：

- 状态码为 200；
- Content-Type 属于允许的图片类型，或内容通过安全图片签名检测；
- 大小不超过配置上限；
- URL 通过 SSRF 与允许 origin 校验。

API 返回 `data:<mime>;base64,...` 所需的 MIME 和 Base64 数据，不把学校验证码 URL直接暴露给客户端作为主路径。

### 3. 普通浏览器交互验证

由于学校响应禁止跨源 iframe，Web 的复杂挑战使用服务器端隔离浏览器：

- 每用户最多一个短时浏览器上下文；
- 只允许访问已确认的学校 origin 及登录过程显式允许的 SSO origin；
- 浏览器画面通过同源 WebSocket/帧接口显示在 CampusMate 全屏验证面板；
- 鼠标、触摸和键盘事件由用户本人发送，系统不生成验证码答案或伪造滑块轨迹；
- 完成登录后 Cookie 保留在服务器会话中，前端永远拿不到原始 Cookie；
- 默认五分钟无活动销毁，并限制并发、帧率、分辨率和输入速率。

浏览器运行时不可用时，接口返回明确的 `INTERACTIVE_RUNTIME_UNAVAILABLE`，不得谎报为已支持。该能力使用独立开关，图片验证码与移动端 WebView 不依赖它。

### 4. Android 与 Harmony

Android WebView 和 Harmony ArkWeb 继续承载复杂验证，但会话回传改为结构化 Cookie：name、value、domain、path、secure、httpOnly、sameSite（平台无法提供的属性显式为空），同时携带实际 User-Agent 和当前 URL。

客户端必须：

- 仅加载连接返回的允许 origin；
- 拦截并拒绝外部 scheme 和非允许跳转；
- 在解绑、切换账号或验证取消时清理对应学校 Cookie；
- 页面销毁时释放 WebView/ArkWeb 资源；
- 登录完成后回到原连接状态机，不创建并行绑定。

### 5. 可恢复会话

正式教务 Cookie Jar 使用带认证加密保存。生产环境必须配置独立的教务会话密钥；密钥缺失或格式错误时禁止启用持久会话。数据库只保存密文、nonce、版本、过期时间和最少索引字段。

恢复时重新执行轻量认证探测；失败则标记 `session_expired` 并引导用户在应用内重新验证。预登录验证码和交互浏览器状态仍只做短时存储，不长期持久化。

## 正方适配策略

正方适配器按显式学校配置工作，不猜测数据接口。河南财经政法大学作为 golden-school 配置至少记录：登录入口、验证码入口、公钥入口、版本、编码、认证方式和允许 origin。

课表、成绩、考试接口必须通过真实登录后的网络证据确认后才写入配置。没有证据的端点保持 `unsupported`，不得返回 Mock 数据冒充成功。

强智、青果和其他厂商不在本轮伪造通用实现；它们使用交互登录也只有在后端具备对应会话验证与抓取适配器后才能声明支持。

## API 契约

现有 `pre-login` 保持兼容，并补充：

- `challenge_type`；
- `captcha_mime_type`；
- `verification_session_id`；
- `interactive_url`（CampusMate 自身路由，不是学校 URL）；
- `allowed_origins` 的服务端摘要信息；
- 稳定的错误码和可重试标志。

现有 `continue` 接受兼容的验证码字段，并验证令牌所有权。结构化 Cookie 使用新字段，旧字典只在兼容期内接受。

交互浏览器 API 分为创建、状态、画面、输入、完成和取消；所有端点均要求当前用户所有权并执行速率限制。

## 安全与隐私

- 不记录账号、密码、验证码答案、Cookie、Authorization 或浏览器画面内容。
- 对 URL、重定向和 DNS 每跳执行 SSRF 防护。
- 登录失败信息不回显学校原始敏感响应。
- 验证会话令牌使用高熵随机值并防重放。
- 浏览器输入只接受白名单事件和范围校验坐标。
- WebSocket 校验 access token、Origin 和会话所有权。
- 错误密码联调最多主动执行一次，之后只使用真实密码或验证码刷新。

## 测试与验收

自动化测试覆盖：

- 二进制图片经过 HTTP 层后逐字节一致；
- HUEL 初始无验证码和错误后图片验证码页面解析；
- 图片挑战不会被错误分流到 `client_webview`；
- 预登录令牌的所有权、连接绑定、过期和重放；
- Cookie 域、路径与同名 Cookie 不丢失；
- 持久会话加密、恢复、密钥轮换版本和篡改失败；
- 交互浏览器的 origin、并发、TTL、输入范围和取消；
- Web、Android、Harmony 的状态映射及回退文案。

真实联调按最小风险顺序执行：公开页面探测、预登录、最多一次错误登录触发验证码、验证码图片显示、用户凭证登录、认证探测、课表/成绩/考试同步。若发现锁定或频率限制信号立即停止。

## 非目标

- 不自动识别图片验证码。
- 不自动求解、绕过或模拟滑块验证。
- 不在没有真实协议证据时宣称支持所有教务厂商。
- 不把真实账号密码写入任何持久介质。
