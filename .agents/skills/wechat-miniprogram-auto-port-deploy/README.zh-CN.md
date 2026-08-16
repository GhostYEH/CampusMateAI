# wechat-miniprogram-auto-port-deploy

[English](README.md) | [简体中文](README.zh-CN.md)

**wechat-miniprogram-auto-port-deploy 是一个面向微信小程序开发、迁移、校验、预览、上传、CloudBase 接入和审核材料准备的 Codex Skill。** 它把 React、Vue、H5、原生小程序、Taro、uni-app 项目的微信小程序工程流程整理成一套可复用、可自动化、可安全检查的开发与发布工作流。

[![Codex Skill](https://img.shields.io/badge/Codex-Skill-111827)](SKILL.md)
[![微信小程序](https://img.shields.io/badge/WeChat-Mini%20Program-07C160)](https://developers.weixin.qq.com/miniprogram/dev/framework/)
[![miniprogram-ci](https://img.shields.io/badge/miniprogram--ci-supported-blue)](https://developers.weixin.qq.com/miniprogram/dev/devtools/ci.html)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

如果这个项目能帮你更快、更稳地开发微信小程序，欢迎点一个 Star，方便更多中文开发者发现它。

## 这个项目解决什么问题？

微信小程序开发并不只是写页面。真实项目通常还会遇到 AppID、上传密钥、合法域名、隐私权限、登录、支付、订阅消息、CloudBase、包体积、预览上传、审核材料等一系列工程问题。

这个仓库提供的 Codex Skill 会让 Codex 按固定流程工作：先识别项目，再选择迁移或开发路线，然后检查配置、安全、兼容性和发布条件，最后生成预览、上传结果或审核材料。它的目标是减少重复踩坑，让微信小程序开发从“人工记规则”变成“自动检查和自动执行”。

## 核心能力

- **从零创建微信小程序**：支持原生小程序、Taro、uni-app 路线判断。
- **迁移现有前端项目**：辅助 React、Vue、H5 项目迁移到微信小程序工程结构。
- **检查项目配置**：校验 `project.config.json`、`app.json`、`pages.json`、页面路径、`tabBar`、小程序源码目录等。
- **发现 Web 兼容性问题**：检查 `window`、`document`、`localStorage`、`fetch`、DOM API、Web-only SDK 等小程序不兼容点。
- **安全保护**：提供 `.env.local` 占位、`.wechat-private/` 本地密钥目录、CI Secret 建议、私钥临时文件清理和明文密钥扫描。
- **自动预览和上传**：通过 `miniprogram-ci` 生成预览二维码或上传体验版/开发版。
- **CloudBase 支持**：检查 `envId`、`wx.cloud.init`、云函数、云托管、环境绑定和权限边界。
- **审核材料生成**：生成版本说明、功能说明、隐私合规检查和发布前检查材料。
- **专属经验账本**：记录微信小程序开发中的错误、修复和经验，后续项目可以复用。
- **官方更新守卫**：检查微信官方文档、CloudBase 文档、GitHub 示例和依赖版本变化。

## 快速开始

把这个 Skill 安装到你的 Codex 工作区：

```bash
mkdir -p .codex/skills/wechat-miniprogram-auto-port-deploy
cp -R ./* .codex/skills/wechat-miniprogram-auto-port-deploy/
```

在你的项目 `package.json` 中合并这些 scripts：

```json
{
  "scripts": {
    "wx:setup": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/setup-wechat-config.js",
    "wx:secrets-init": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/setup-wechat-secrets.js",
    "wx:inspect": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/inspect-project.js",
    "wx:validate": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/validate-miniprogram.js",
    "wx:preview": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/wx-preview.js",
    "wx:upload": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/wx-upload.js",
    "wx:deploy": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/wx-deploy.js",
    "wx:review": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/generate-review-materials.js",
    "wx:learn": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/wechat-experience-ledger.js preflight",
    "wx:experience": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/wechat-experience-ledger.js",
    "wx:health-check": "node .codex/skills/wechat-miniprogram-auto-port-deploy/scripts/skill-health-check.js"
  }
}
```

首次配置建议执行：

```bash
npm run wx:setup
npm run wx:secrets-init
npm run wx:inspect
npm run wx:validate
```

## 常用命令

```bash
npm run wx:setup              # 创建或合并非敏感的小程序配置
npm run wx:secrets-init       # 创建本地密钥占位和安全目录，并扫描密钥风险
npm run wx:inspect            # 识别框架、包管理器、小程序目录、CloudBase、CI 和风险
npm run wx:validate           # 校验配置、安全、兼容性、权限、域名和包体积风险
npm run wx:preview            # 使用 miniprogram-ci 生成预览二维码
npm run wx:upload             # 使用 miniprogram-ci 上传体验版/开发版
npm run wx:deploy             # 检查、构建、复检，然后按配置预览/上传
npm run wx:review             # 生成审核材料和发布前检查材料
npm run wx:learn -- "上传密钥" # 查询微信小程序专属经验账本
npm run wx:health-check       # 检查 Skill 健康状态、官方文档可访问性和依赖变化
```

## 适合哪些场景？

| 场景 | 这个 Skill 怎么帮你 |
| --- | --- |
| 新建微信小程序 | 生成基础结构、配置、页面、请求层和校验脚本 |
| React 项目转小程序 | 默认优先 Taro，迁移路由、请求、存储和页面结构 |
| Vue 项目转小程序 | 默认优先 uni-app，迁移 `pages.json`、状态管理和 API 层 |
| H5 项目转小程序 | 先生成评估报告，再迁移业务逻辑和小程序可用结构 |
| 已有小程序维护 | 保持原结构，补齐校验、安全、CI、预览上传和审核材料 |
| 接入登录/支付/手机号 | 明确前后端边界，避免把 AppSecret、支付密钥、`session_key` 放进前端 |
| 接入 CloudBase | 检查环境、云函数、云托管、权限和绑定关系 |
| 发布前检查 | 生成验证报告、预览二维码、上传报告和审核材料 |

## 安全设计

这个项目不会鼓励把真实密钥写进仓库。

- 不提交 AppSecret。
- 不提交上传私钥内容。
- 不提交支付商户密钥、API v3 key 或证书。
- 不把 `session_key` 放进小程序前端代码或前端存储。
- 本地开发优先使用 `WECHAT_PRIVATE_KEY_PATH` 指向 `.wechat-private/` 里的本地文件。
- CI 自动化优先使用 GitHub Secrets 或其他 CI Secret。
- 登录换取 `openid/session_key`、支付下单和签名必须放在服务端或 CloudBase 云函数中。

`npm run wx:secrets-init` 会生成 `.env.local` 占位文件和 `.wechat-private/` 本地目录，并扫描明显的明文密钥风险，但不会打印密钥值。

## 会生成哪些报告？

- `artifacts/wechat-inspect-report.json`
- `artifacts/wechat-validation-report.json`
- `artifacts/wechat-preview-qrcode.jpg`
- `artifacts/wechat-upload-report.json`
- `artifacts/wechat-deploy-report.json`
- `artifacts/wechat-review-materials.md`
- `artifacts/wechat-secrets-init-report.json`
- `artifacts/wechat-skill-health-report.json`

这些 artifacts 用于本地调试和 CI 排查，默认不应该提交到仓库。

## 不能承诺什么？

这个 Skill 可以自动检查、自动生成材料、辅助预览和上传，但不能：

- 绕过微信审核。
- 保证审核通过。
- 伪造类目、资质、隐私说明或支付资料。
- 隐藏真实的数据采集行为。
- 在没有官方文档确认时声称 API 参数一定正确。
- 替代正式发布前的人工作业确认。

正式上线前，仍然需要人工确认类目、隐私、权限、支付、内容合规、生产后端和回滚方案。

## 文档入口

- [Skill 主说明](SKILL.md)
- [运行时官方文档查询策略](references/runtime-doc-lookup-policy.md)
- [首次配置说明](references/first-run-config.md)
- [迁移检查清单](references/migration-checklist.md)
- [安全检查清单](references/security-checklist.md)
- [部署检查清单](references/deployment-checklist.md)
- [CloudBase 检查清单](references/cloudbase-checklist.md)
- [故障排查](references/troubleshooting.md)

## 适合搜索的关键词

微信小程序开发、微信小程序迁移、微信小程序自动上传、微信小程序 CI/CD、miniprogram-ci、Taro 迁移、uni-app 迁移、CloudBase、小程序审核材料、小程序安全检查、小程序合法域名、小程序隐私合规、Codex Skill。

## 贡献

欢迎提交 Issue 和 Pull Request。特别欢迎补充真实迁移案例、校验规则、CloudBase 部署经验、官方文档变化记录、审核材料模板和更安全的 CI 默认配置。

请不要在 Issue 或 PR 中粘贴真实 AppID 密钥、上传私钥、支付密钥、API token、用户隐私数据或私有业务文档。

## License

MIT
