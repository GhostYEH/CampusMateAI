# Web 专注页设计 QA

- source visual truth: `C:/Users/32883/AppData/Local/Temp/codex-clipboard-b79db327-fc16-43b1-914f-5d899a6d310d.png`
- implementation screenshot: `F:/demo1/artifacts/web-focus-final-1678x941.png`
- side-by-side comparison: `F:/demo1/artifacts/web-focus-reference-comparison.png`
- viewport: 1678 × 941, DPR 1
- state: Web `/study`，学生演示会话，空学习记录，四条待办模拟数据，浅色主题

## Findings

- No actionable P0/P1/P2 findings remain.
- Typography: Noto Sans SC 与参考图同属现代无衬线中文体系；桌面标题、卡片标题、数字层级、正文和微文案的字号、粗细与换行接近参考图。实现标题略粗，属于可接受的 P3 差异。
- Spacing and layout: 254px 侧栏、76px 顶栏、主内容 40px 桌面边距、左右主区、四项指标和三列底部布局在同视口对照中一致。页面高度 942px，仅比视口多 1px，无横向溢出。
- Colors and tokens: 白色/淡蓝紫背景、靛蓝主色、绿色/琥珀/紫色统计状态与参考图一致；边框、圆角和阴影层级接近。
- Image quality: Web 专属 1536×1024 机器人学习插画使用透明 PNG，边缘清晰，主体、台灯、书本和配色符合参考图。主体造型并非原始像素资产，属于同风格重绘的可接受 P3 差异。
- Copy: 标题、专注会话、学习计划、指标、最近记录、趋势和待完成计划文案均与参考图语义一致；保留现有产品的服务端记录说明。
- Interactions: 时长、自定义时间、开始、暂停/继续、结束记录、专注模式、通知与声音开关、学习目标、AI 拆解、待办回填和页面跳转均保留现有绑定。
- Responsive evidence: `F:/demo1/artifacts/web-focus-1280x900.png` 与 `F:/demo1/artifacts/web-focus-390x844.png` 均无横向溢出；移动端卡片单列且主操作可见。

## Patches made after comparison

- 将 Web 专注页主内容左边界、侧栏内部间距和首屏纵向位置向参考图收齐。
- 增加 Web 专属机器人学习透明插画并替换旧的校园数据插画。
- 将趋势区改为真实数据驱动的柔和折线图；空数据时显示低强度示例趋势并明确提示。
- 增加 `/study` 壳层作用域和页面级 CSS，避免影响其他路由或客户端。

## Focused region comparison

主专注卡、学习计划卡、四项指标和底部趋势区均在同一张 3356×941 拼接对照图中保持可读，因此无需额外放大裁切。机器人主体的透明边缘另行以原始 PNG 检查，四角透明且无明显绿色边缘。

## Residual P3 polish

- 参考图机器人更偏柔白、体积更小；实现插画饱和度更高、表情更活泼。
- 参考图背景有教学楼淡水印；实现保留更克制的淡紫光晕，避免新增不可靠装饰资产。

final result: passed
