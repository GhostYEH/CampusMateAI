# CampusMate iOS

原生 iOS 应用初始工程，使用 Swift 6 + SwiftUI，最低支持 iOS 17.0，同时支持 iPhone 和 iPad，无第三方依赖。

## 开始开发

1. 使用 Xcode 16 或更新版本打开 `CampusMate.xcodeproj`。
2. 选择 `CampusMate` Scheme 和一个已安装的 iPhone / iPad 模拟器。
3. 按 `⌘R` 运行。

也可以在当前项目根目录执行：

```bash
open ios/CampusMate.xcodeproj
```

真机运行前，在 Target → Signing & Capabilities 中选择自己的开发团队（Team），并将占位 Bundle Identifier `com.example.campusmate` 改为自己的唯一标识。

## 目录

```text
ios/
├── CampusMate.xcodeproj/        # Xcode 工程与共享 Scheme
├── CampusMate/
│   ├── CampusMateApp.swift      # 应用入口
│   ├── ContentView.swift        # 初始首页与 SwiftUI Preview
│   └── Assets.xcassets/         # 主题色和 AppIcon 占位
├── .gitignore
└── README.md
```

从 `CampusMate/ContentView.swift` 开始编写界面。`CampusMate/` 使用 Xcode 同步文件夹，后续放入其中的 Swift 源文件会自动纳入 Target。

当前仅初始化可运行的应用骨架，尚未接入后端、登录、业务页面或第三方 SDK。AppIcon 预留资源位置，上架前需要补充正式图标。

## 命令行构建

在 `ios/` 目录执行，无需为模拟器配置开发者签名：

```bash
xcodebuild \
  -project CampusMate.xcodeproj \
  -scheme CampusMate \
  -configuration Debug \
  -destination 'generic/platform=iOS Simulator' \
  -derivedDataPath build/DerivedData \
  CODE_SIGNING_ALLOWED=NO \
  build
```

`Info.plist` 由 Xcode 根据工程设置自动生成；可在 Target → Info 中配置应用信息和后续需要的权限说明。
