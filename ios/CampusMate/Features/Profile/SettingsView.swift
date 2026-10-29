import SwiftUI
import UniformTypeIdentifiers
import QuickLook
import UserNotifications
import CampusCore

struct SettingsView: View {
    @Environment(\.campus) private var palette
    @Environment(AppModel.self) private var app
    @State private var confirmSignOut = false
    @State private var address = ""
    @State private var error: String?
    @State private var changing = false
    @State private var notificationStatus: UNAuthorizationStatus = .notDetermined

    var body: some View {
        @Bindable var app = app
        CampusSecondaryScaffold(title: "系统设置") {
            ScrollView {
                VStack(spacing: 14) {
                    CampusCard {
                        VStack(alignment: .leading, spacing: 14) {
                            Text("外观").campusFont(.subtitle).foregroundStyle(palette.textPrimary)
                            Picker("主题", selection: $app.theme) {
                                Text("跟随系统").tag("system"); Text("浅色").tag("light"); Text("深色").tag("dark")
                            }
                            .pickerStyle(.segmented)
                            Toggle("减少动态效果", isOn: $app.reduceMotion).tint(palette.primary)
                                .campusFont(.body)
                        }
                    }
                    CampusCard {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("提醒").campusFont(.subtitle).foregroundStyle(palette.textPrimary)
                            Toggle("待办和考试提醒", isOn: $app.remindersEnabled).tint(palette.primary)
                            Text(reminderHint).campusFont(.caption).foregroundStyle(.secondary)
                            if notificationStatus == .denied {
                                Button("前往系统设置开启通知") {
                                    if let url = URL(string: UIApplication.openSettingsURLString) { UIApplication.shared.open(url) }
                                }
                                .campusFont(.caption).foregroundStyle(palette.primary)
                            }
                        }
                    }
                    CampusCard {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("服务连接").campusFont(.subtitle).foregroundStyle(palette.textPrimary)
                            CampusTextField(placeholder: "服务器地址", text: $address, systemImage: "server.rack", keyboard: .URL)
                            Text("切换服务器会使用对应服务的登录状态。").campusFont(.caption).foregroundStyle(.secondary)
                            CampusSecondaryButton(title: changing ? "正在切换…" : "保存服务器地址", systemImage: "checkmark", enabled: !changing) {
                                changing = true
                                Task {
                                    defer { changing = false }
                                    do { try await app.configureServer(address) } catch { self.error = error.localizedDescription }
                                }
                            }
                        }
                    }
                    CampusCard {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("关于").campusFont(.subtitle).foregroundStyle(palette.textPrimary)
                            LabeledContent("应用", value: "CampusMate")
                            LabeledContent("版本", value: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0")
                            Text("学习观察仅作辅助，不代表学习效果或心理状态判断。iOS 不读取其他应用的通知，通知整理依赖服务端同步、手动导入与本机提醒。")
                                .campusFont(.caption).foregroundStyle(.secondary)
                        }
                    }
                    CampusCard {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("AI 与模型共建").campusFont(.subtitle).foregroundStyle(palette.textPrimary)
                            NavigationLink { ExpressionContributionView() } label: {
                                HStack(spacing: 12) {
                                    Image(systemName: "face.smiling")
                                        .font(.system(size: 18)).foregroundStyle(palette.primary).frame(width: 26)
                                    VStack(alignment: .leading, spacing: 3) {
                                        Text("CNN 模型共建").campusFont(.body).foregroundStyle(palette.textPrimary)
                                        Text("主动拍摄或选择图片，打标后上传")
                                            .campusFont(.caption).foregroundStyle(.secondary)
                                            .fixedSize(horizontal: false, vertical: true)
                                    }
                                    Spacer(minLength: 4)
                                    Image(systemName: "chevron.right").font(.system(size: 12)).foregroundStyle(.secondary)
                                }
                                .padding(.vertical, 4)
                                .contentShape(Rectangle())
                            }
                            .buttonStyle(.plain)
                            .accessibilityIdentifier("settings.contribution")
                            Text("只上传你主动选择的一张图片；样本可随时删除，不用于心理诊断。")
                                .campusFont(.caption).foregroundStyle(palette.muted)
                        }
                    }
                    CampusCard {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("账号").campusFont(.subtitle).foregroundStyle(palette.textPrimary)
                            Text(app.session?.user.displayName ?? "当前账号").campusFont(.caption).foregroundStyle(.secondary)
                            Button(role: .destructive) { confirmSignOut = true } label: {
                                Text("退出登录").campusFont(.body).fontWeight(.semibold)
                                    .foregroundStyle(Color(hex: 0xC25450))
                                    .frame(maxWidth: .infinity).frame(height: 44)
                                    .background(Color(hex: 0xF6DAD8), in: RoundedRectangle(cornerRadius: 14))
                            }
                            .accessibilityIdentifier("settings.signout")
                        }
                    }
                    NavigationLink { NotificationSourcesView() } label: {
                        HStack {
                            Label("通知来源与权限", systemImage: "bell.badge")
                                .campusFont(.body).foregroundStyle(palette.textPrimary)
                            Spacer()
                            Image(systemName: "chevron.right").font(.system(size: 12)).foregroundStyle(.secondary)
                        }
                        .padding(16)
                        .background(palette.surface, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                    }
                    .buttonStyle(.plain)
                }
                .padding(20)
                .frame(maxWidth: 700)
                .frame(maxWidth: .infinity)
            }
        }
        .onAppear { address = app.serverURL }
        .confirmationDialog("退出当前账号？", isPresented: $confirmSignOut, titleVisibility: .visible) {
            Button("退出登录", role: .destructive) { Task { await app.signOut() } }
        }
        .task { notificationStatus = await ReminderScheduler.shared.authorizationStatus() }
        .onChange(of: app.remindersEnabled) { _, enabled in
            Task {
                if enabled {
                    _ = await ReminderScheduler.shared.requestAuthorization()
                    notificationStatus = await ReminderScheduler.shared.authorizationStatus()
                    if app.remindersEnabled { app.refreshReminders() }
                } else {
                    await ReminderScheduler.shared.cancelAll()
                }
            }
        }
        .errorAlert($error)
    }

    private var reminderHint: String {
        switch notificationStatus {
        case .authorized, .provisional: "已允许通知，按待办设置的提前量提醒（默认 30 分钟），考试前 1 小时提醒。"
        case .denied: "通知权限已关闭，提醒不会送达。可在系统设置中重新开启。"
        default: "开启后会请求系统通知权限；来源系统的待办保持原系统的提醒。"
        }
    }
}
