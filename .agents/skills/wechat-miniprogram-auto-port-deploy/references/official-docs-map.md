# Official Docs Map

Use this map during Runtime Documentation Lookup. Update "last checked" in task notes or generated reports; do not edit this reference just to stamp routine executions.

| Source | URL | Applies to | Check before use | Common pitfalls | Last checked |
|---|---|---|---|---|---|
| WeChat Mini Program framework | https://developers.weixin.qq.com/miniprogram/dev/framework/ | App/page lifecycle, routing, config, subpackages, tabBar, Skyline, GlassEasel | Base library limits, config format, lifecycle behavior | Assuming Web DOM semantics or Vue/React browser lifecycle | TODO runtime |
| WeChat Mini Program API | https://developers.weixin.qq.com/miniprogram/dev/api/ | Login, request, upload/download, storage, payment, subscription, location, media, device APIs | Required permissions, platform support, callback/Promise behavior, base library | Calling APIs without user authorization or privacy declaration | TODO runtime |
| WeChat Mini Program components | https://developers.weixin.qq.com/miniprogram/dev/component/ | Native UI components, map, media, form, canvas | Component attributes, event names, Skyline support | Copying browser HTML attributes directly | TODO runtime |
| WeChat DevTools | https://developers.weixin.qq.com/miniprogram/dev/devtools/ | Local dev, project config, preview, upload, devtools behavior | DevTools version, project import constraints | Treating devtools-only config as deploy-safe | TODO runtime |
| DevTools CI and miniprogram-ci | https://developers.weixin.qq.com/miniprogram/dev/devtools/ci.html | Preview, upload, CI credentials, IP whitelist, private key | Required permissions, key format, IP whitelist, robot number | Printing private key or assuming CI host IP is whitelisted | TODO runtime |
| WeChat security | https://developers.weixin.qq.com/miniprogram/dev/framework/security.html | Frontend/backend boundary, secrets, session handling | Current security recommendations and prohibited storage | Putting AppSecret, merchant key, or session_key in frontend code | TODO runtime |
| WeChat GitHub organization | https://github.com/wechat-miniprogram | Official packages and examples | Repository maintenance status and README warnings | Assuming every repo is official policy | TODO runtime |
| miniprogram-demo | https://github.com/wechat-miniprogram/miniprogram-demo | Official sample patterns | Example age and base library assumptions | Copying demo code without privacy/permission checks | TODO runtime |
| api-typings | https://github.com/wechat-miniprogram/api-typings | TypeScript API types | Version compatibility with current base library | Treating types as policy documentation | TODO runtime |
| WeUI Mini Program | https://github.com/wechat-miniprogram/weui-miniprogram | Official-style UI components | Install/import method and component compatibility | Mixing incompatible component library conventions | TODO runtime |
| TDesign Mini Program | https://github.com/Tencent/tdesign-miniprogram | Tencent component library | Version, import path, custom component config | Assuming H5 TDesign API equals Mini Program TDesign API | TODO runtime |
| miniprogram-ci npm | https://www.npmjs.com/package/miniprogram-ci | Node package install and API reference | Current package version, supported Node versions | Depending on globally installed miniprogram-ci | TODO runtime |
| CloudBase docs | https://docs.cloudbase.net/ | CloudBase environment, functions, run, DB, storage | Permission model, envId, binding requirements | Assuming local env is bound to Mini Program account | TODO runtime |
| CloudBase Mini Program plugin | https://docs.cloudbase.net/framework/plugins/framework-plugin-mp | CloudBase Framework Mini Program deploy plugin | Required config fields and deploy mode | Storing private key content in repo config | TODO runtime |
| CloudBase create env | https://docs.cloudbase.net/quick-start/create-env | Environment creation and account setup | Account permission and region constraints | Assuming envId exists or is accessible | TODO runtime |
| CloudBase cloud function recipe | https://docs.cloudbase.net/recipes/add-cloud-function-wechat-miniprogram | Cloud functions for Mini Program | Directory layout and invocation permissions | Mixing cloud functions with cloud run calls | TODO runtime |
| CloudBase Run Mini Program access | https://docs.cloudbase.net/run/develop/access/mini | Cloud Run access from Mini Program | Binding, auth, service endpoint, domain requirements | Bypassing legal domain or auth checks | TODO runtime |

Runtime notes must include:

- Query date.
- Document URL.
- Current task relevance.
- Confirmed API/component/config/permission requirement.
- Version or base-library restriction.
- Impact on implementation.
- Unresolved uncertainty.
