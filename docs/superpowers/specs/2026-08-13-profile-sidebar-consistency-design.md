# 个人中心侧边栏一致性设计

## 目标

个人中心及其子页面沿用学生端公共应用外壳。桌面端默认侧边栏保持 `286px`，仅在用户点击“收起导航”后使用公共的 `82px` 折叠状态，切换路由不得自行改变侧边栏宽度或内容密度。

## 根因

`student-profile-reference.css` 使用 `.app-layout:has(.profile-redesign)` 为个人中心覆盖公共外壳，把侧边栏改为 `158px`，并同时隐藏品牌文字、缩小头像和导航项、改变顶栏尺寸。因此进入 `/profile` 时即使 `collapsed` 状态未变化，视觉上仍像侧边栏被收起。

## 设计

- 个人中心样式只负责 `.profile-redesign` 内部内容，不再选择或修改 `.app-layout`、`.sidebar`、`.topbar`、`.command-search` 等公共外壳元素。
- 公共展开态继续由 `student-home.css` 的 `.student-layout` 控制，桌面宽度为 `286px`。
- 公共折叠态继续由 `.student-layout.collapsed` 控制，桌面宽度为 `82px`，现有折叠按钮与移动端抽屉行为保持不变。
- 个人中心主体、卡片、标签页、响应式布局及数据交互不做改动。

## 验证

- 增加静态回归测试，确保个人中心样式表不再包含 `:has(.profile-redesign)` 外壳覆盖。
- 保留并运行现有折叠侧栏尺寸测试。
- 运行全部 Web Node 测试与生产构建。

