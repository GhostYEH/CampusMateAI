import SwiftUI
import UniformTypeIdentifiers
import QuickLook
import UserNotifications
import CampusCore

struct NotificationSourcesView: View {
    @Environment(\.campus) private var palette
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var status: String?
    @State private var lastSynced: String?
    @State private var showExtract = false
    @State private var notificationStatus: UNAuthorizationStatus = .notDetermined

    var body: some View {
        CampusSecondaryScaffold(title: "通知与提醒") {
            ScrollView {
                VStack(spacing: 12) {
                    CampusCard {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("iOS 的通知边界").campusFont(.body).fontWeight(.semibold).foregroundStyle(palette.textPrimary)
                            Text("系统不允许第三方应用读取微信、企业微信或 QQ 的通知内容。CampusMate 不会假装拥有该能力。可以用下面的三种真实来源整理事务。")
                                .campusFont(.caption).foregroundStyle(.secondary)
                        }
                    }
                    CampusCard {
                        VStack(alignment: .leading, spacing: 12) {
                            sourceRow(icon: "doc.on.clipboard", title: "手动粘贴提取", subtitle: "复制通知原文，提取成待办", status: "可用", tone: .success) {
                                showExtract = true
                            }
                            Divider()
                            sourceRow(icon: "arrow.triangle.2.circlepath", title: "学习通同步", subtitle: lastSynced.map { "课程 · 作业 · 通知 · 上次 \($0.prefix(16))" } ?? "同步课程、作业与课程通知",
                                      status: status == "online" ? "已连接" : status == "expired" ? "需重新登录" : "未连接",
                                      tone: status == "online" ? .success : status == "expired" ? .danger : .neutral) {
                            }
                            Divider()
                            sourceRow(icon: "bell", title: "本机提醒", subtitle: "个人待办与考试的系统本地通知",
                                      status: notificationStatus == .authorized ? "已允许" : notificationStatus == .denied ? "已关闭" : "未开启",
                                      tone: notificationStatus == .authorized ? .success : notificationStatus == .denied ? .danger : .neutral) {
                                Task {
                                    _ = await ReminderScheduler.shared.requestAuthorization()
                                    notificationStatus = await ReminderScheduler.shared.authorizationStatus()
                                }
                            }
                        }
                    }
                    NavigationLink { ChaoxingView() } label: {
                        HStack {
                            Label("连接或同步学习通", systemImage: "graduationcap")
                                .campusFont(.body).foregroundStyle(palette.primary)
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
        .task {
            notificationStatus = await ReminderScheduler.shared.authorizationStatus()
            if let value = try? await app.client.request(path: "chaoxing/status") {
                status = value["status"].string
                lastSynced = value["last_synced_at"].string
            }
        }
        .sheet(isPresented: $showExtract) { NavigationStack { TaskImportView(noticeMode: true) } }
    }

    private func sourceRow(icon: String, title: String, subtitle: String, status: String, tone: CampusStatusTone, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 12) {
                Image(systemName: icon).font(.system(size: 17)).foregroundStyle(palette.primary).frame(width: 26)
                VStack(alignment: .leading, spacing: 3) {
                    Text(title).campusFont(.body).foregroundStyle(palette.textPrimary)
                    Text(subtitle).campusFont(.caption).foregroundStyle(.secondary).lineLimit(2)
                }
                Spacer(minLength: 4)
                CampusStatusTag(text: status, tone: tone)
            }
            .padding(.vertical, 4)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }
}
