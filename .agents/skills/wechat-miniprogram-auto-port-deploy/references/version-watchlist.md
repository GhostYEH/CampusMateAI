# Version Watchlist

| Package | Current Version Detection Command | Latest Version Check Command | Risk | Auto-Update Allowed | Notes |
|---|---|---|---|---|---|
| `miniprogram-ci` | `node -e "const p=require('./package.json'); console.log((p.dependencies&&p.dependencies['miniprogram-ci'])||(p.devDependencies&&p.devDependencies['miniprogram-ci'])||'missing')"` | `npm view miniprogram-ci version` | high | false | Patch/minor can be recommended. Major requires human confirmation. |
| `@tarojs/cli` | same package.json dependency lookup | `npm view @tarojs/cli version` | high | false | Taro major requires human confirmation. |
| `@tarojs/taro` | same package.json dependency lookup | `npm view @tarojs/taro version` | high | false | Taro runtime changes can affect migration output. |
| `@dcloudio/uni-app` | same package.json dependency lookup | `npm view @dcloudio/uni-app version` | high | false | uni-app major requires human confirmation. |
| `@vue/runtime-core` | same package.json dependency lookup | `npm view @vue/runtime-core version` | medium | false | Vue major requires human confirmation. |
| `react` | same package.json dependency lookup | `npm view react version` | medium | false | React major requires migration/lint review. |
| `typescript` | same package.json dependency lookup | `npm view typescript version` | medium | false | TypeScript major can affect generated wrappers and CI. |
| `weui-miniprogram` | same package.json dependency lookup | `npm view weui-miniprogram version` | medium | false | UI library major requires component compatibility review. |
| `tdesign-miniprogram` | same package.json dependency lookup | `npm view tdesign-miniprogram version` | medium | false | UI library major requires component compatibility review. |
| `@cloudbase/cli` | same package.json dependency lookup | `npm view @cloudbase/cli version` | high | false | CloudBase CLI major requires deployment review. |
| `@cloudbase/framework-plugin-mp` | same package.json dependency lookup | `npm view @cloudbase/framework-plugin-mp version` | high | false | Plugin major requires deployment config review. |

Rules:

- Never automatically upgrade dependencies from this skill.
- `miniprogram-ci` patch/minor can be recommended, not applied.
- `miniprogram-ci` major must be manually confirmed.
- Taro/uni-app major must be manually confirmed.
- React/Vue/TypeScript major must be manually confirmed.
- UI library major must be manually confirmed.
- CloudBase CLI/plugin major must be manually confirmed.
