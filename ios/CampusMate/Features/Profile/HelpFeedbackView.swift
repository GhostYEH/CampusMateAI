import SwiftUI
import UniformTypeIdentifiers
import QuickLook
import UserNotifications
import CampusCore

struct HelpFeedbackView: View {
    @Environment(\.campus) private var palette
    @Environment(AppModel.self) private var app
    @State private var online: Bool?

    var body: some View {
        CampusSecondaryScaffold(title: "帮助与反馈") {
            ScrollView {
                VStack(spacing: 12) {
                    HStack(spacing: 12) {
                        Image(systemName: online == true ? "checkmark.icloud" : "exclamationmark.icloud")
                            .font(.system(size: 20))
                            .foregroundStyle(online == true ? Color(hex: 0x17A66A) : Color(hex: 0xF0784A))
                        VStack(alignment: .leading, spacing: 3) {
                            Text(online == true ? "服务连接正常" : "正在重新连接服务")
                                .campusFont(.body).fontWeight(.semibold).foregroundStyle(palette.textPrimary)
                            Text(online == true ? "当前功能可以使用真实后端数据。" : "请稍候，或检查此设备的后端地址与网络。")
                                .campusFont(.caption).foregroundStyle(.secondary)
                        }
                        Spacer()
                    }
                    .padding(16)
                    .background(online == true ? Color(hex: 0xEAF8F0) : Color(hex: 0xFFEFEA), in: RoundedRectangle(cornerRadius: 20, style: .continuous))

                    Text("常见问题").campusFont(.body).fontWeight(.bold).foregroundStyle(palette.textPrimary)
                        .frame(maxWidth: .infinity, alignment: .leading).padding(.leading, 4)
                    helpCard("为什么会显示未连接？", "登录后应用会自动检查服务；真机调试需使用电脑可访问的服务地址，而不是模拟器专用的 10.0.2.2。")
                    helpCard("如何重新检查连接？", "回到设置页或本页下拉即可刷新服务状态；连接恢复后无需重新登录。")
                    helpCard("为什么 iOS 收不到微信通知？", "iOS 不允许应用读取其他应用的通知。请使用通知页的手动粘贴提取，或连接学习通同步课程通知。")
                    helpCard("数据与隐私", "专注画面默认仅在本机分析、不保存不上传；样本贡献必须由你主动授权。")
                }
                .padding(20)
                .frame(maxWidth: 700)
                .frame(maxWidth: .infinity)
            }
        }
        .task {
            do { _ = try await app.client.request(path: "health"); online = true }
            catch { online = false }
        }
    }

    private func helpCard(_ title: String, _ detail: String) -> some View {
        HStack(alignment: .top, spacing: 12) {
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(Color(hex: 0xE4EEE5)).frame(width: 40, height: 40)
                .overlay(Image(systemName: "questionmark.circle").font(.system(size: 18)).foregroundStyle(palette.primary))
            VStack(alignment: .leading, spacing: 4) {
                Text(title).campusFont(.body).fontWeight(.semibold).foregroundStyle(palette.textPrimary)
                Text(detail).campusFont(.caption).foregroundStyle(.secondary)
            }
            Spacer(minLength: 0)
        }
        .padding(16)
        .background(palette.surface, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
    }
}

// MARK: - Notification sources

/// iOS cannot observe other apps' notification streams. This page states that
/// limitation and routes the same intent through real, available channels.
