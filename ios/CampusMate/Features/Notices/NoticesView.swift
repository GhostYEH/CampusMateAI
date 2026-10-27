import SwiftUI
import CampusCore

/// Port of `NotificationsScreen`, adapted to the real iOS notification
/// boundary: server-synced notices, manual extraction and local reminders.
struct NoticesView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var resource = PagedResource()
    @State private var unreadOnly = false
    @State private var showExtract = false
    @State private var showAll = false
    @State private var chaoxingStatus: String?
    @State private var lastSynced: String?
    @State private var selected: NoticeSelection?

    private var query: [String: String] { ["unread_only": String(unreadOnly)] }

    var body: some View {
        CampusSecondaryScaffold(title: "通知与提醒") {
            ScrollView {
                VStack(spacing: 14) {
                    syncedCard
                    sourcesCard
                    boundaryCard
                }
                .padding(.horizontal, 20)
                .padding(.top, 6)
                .padding(.bottom, 30)
                .frame(maxWidth: 760)
                .frame(maxWidth: .infinity)
            }
            .refreshable { await load() }
        }
        .task {
            await load()
            if let value = try? await app.client.request(path: "chaoxing/status") {
                chaoxingStatus = value["status"].string
                lastSynced = value["last_synced_at"].string
            }
        }
        .sheet(item: $selected) { notice in
            NavigationStack { NoticeDetailView(notice: notice.value) }
        }
        .sheet(isPresented: $showExtract, onDismiss: { Task { await load() } }) {
            NavigationStack { TaskImportView(noticeMode: true) }
        }
    }

    private var syncedCard: some View {
        CampusCard {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Text("课程与校园通知").campusFont(.subtitle).foregroundStyle(Color(hex: 0x1B2730))
                    Spacer()
                    HStack(spacing: 6) {
                        Text("只看未读").campusFont(.caption).foregroundStyle(Color(hex: 0x667784))
                        Toggle("", isOn: $unreadOnly)
                            .labelsHidden()
                            .tint(Color(hex: 0x285B4B))
                            .scaleEffect(0.86)
                            .accessibilityLabel("只看未读")
                    }
                }
                if resource.isLoading && resource.items.isEmpty {
                    CampusLoadingState(message: "正在读取通知…")
                } else if let error = resource.error, resource.items.isEmpty {
                    CampusErrorState(message: error) { Task { await load() } }
                } else if resource.items.isEmpty {
                    Text("暂无已同步通知。连接学习通后，可在图书馆更新课程通知。")
                        .campusFont(.caption).foregroundStyle(.secondary)
                } else {
                    let items = showAll ? resource.items : Array(resource.items.prefix(6))
                    ForEach(Array(items.enumerated()), id: \.offset) { index, notice in
                        if index > 0 { Divider() }
                        Button { selected = NoticeSelection(value: notice) } label: {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(notice.displayTitle).campusFont(.body).fontWeight(.semibold)
                                    .foregroundStyle(Color(hex: 0x1B2730)).lineLimit(2)
                                Text([notice["source_name"].text, notice["published_at"].text].filter { !$0.isEmpty }.joined(separator: " · "))
                                    .campusFont(.caption).foregroundStyle(.secondary).lineLimit(1)
                                let body = notice["content"].text
                                if !body.isEmpty {
                                    Text(body).campusFont(.caption).foregroundStyle(.secondary).lineLimit(2)
                                }
                            }
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.vertical, 9)
                            .contentShape(Rectangle())
                        }
                        .buttonStyle(.plain)
                    }
                    if resource.items.count > 6 {
                        Button(showAll ? "收起通知" : "查看全部 \(resource.items.count) 条") {
                            withAnimation(.easeOut(duration: 0.2)) { showAll.toggle() }
                        }
                        .campusFont(.caption).foregroundStyle(Color(hex: 0x285B4B))
                    }
                }
            }
        }
    }

    private var sourcesCard: some View {
        CampusCard {
            VStack(alignment: .leading, spacing: 0) {
                Text("通知来源与连接").campusFont(.subtitle).foregroundStyle(Color(hex: 0x1B2730))
                    .padding(.bottom, 8)
                sourceRow(icon: "doc.on.clipboard", title: "手动粘贴提取", subtitle: "复制通知原文，整理成待办",
                          status: "可用", tone: .success) { showExtract = true }
                Divider().padding(.vertical, 2)
                sourceRow(icon: "graduationcap", title: "学习通",
                          subtitle: lastSynced.map { "课程 · 作业 · 通知 · 上次 \($0.prefix(16))" } ?? "同步课程、作业与课程通知",
                          status: chaoxingStatus == "online" ? "已连接" : chaoxingStatus == "expired" ? "需重新登录" : "未连接",
                          tone: chaoxingStatus == "online" ? .success : chaoxingStatus == "expired" ? .danger : .neutral) { }
                Divider().padding(.vertical, 2)
                sourceRow(icon: "bell.badge", title: "本机提醒", subtitle: "个人待办与考试的系统通知",
                          status: "系统", tone: .info) { }
                Divider().padding(.vertical, 2)
                NavigationLink { NotificationSourcesView() } label: {
                    HStack {
                        Text("查看通知来源设置").campusFont(.body).foregroundStyle(Color(hex: 0x285B4B))
                        Spacer()
                        Image(systemName: "chevron.right").font(.system(size: 12)).foregroundStyle(.secondary)
                    }
                    .padding(.vertical, 12)
                }
                .buttonStyle(.plain)
            }
        }
    }

    private var boundaryCard: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: "info.circle").font(.system(size: 15)).foregroundStyle(Color(hex: 0x285B4B))
            Text("iOS 不允许应用读取微信、企业微信或 QQ 的通知内容。这里只展示服务端同步的通知，手动提取与本地提醒是真实可用的替代方式。")
                .campusFont(.caption).foregroundStyle(.secondary)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(hex: 0xE4EEE5).opacity(0.7), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
    }

    private func sourceRow(icon: String, title: String, subtitle: String, status: String, tone: CampusStatusTone, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 12) {
                Image(systemName: icon).font(.system(size: 17)).foregroundStyle(Color(hex: 0x285B4B)).frame(width: 26)
                VStack(alignment: .leading, spacing: 3) {
                    Text(title).campusFont(.body).foregroundStyle(Color(hex: 0x1B2730))
                    Text(subtitle).campusFont(.caption).foregroundStyle(.secondary).lineLimit(1)
                }
                Spacer(minLength: 4)
                CampusStatusTag(text: status, tone: tone)
            }
            .padding(.vertical, 8)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    private func load() async {
        await resource.load(client: app.client, path: "notices", query: query)
    }
}

struct NoticeSelection: Identifiable {
    let value: JSONValue
    var id: String { value["id"].text.isEmpty ? value.displayTitle : value["id"].text }
}

struct NoticeDetailView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    let notice: JSONValue
    @State private var extract = false
    @State private var error: String?

    var body: some View {
        CampusSecondaryScaffold(title: "通知详情") {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    Text(notice.displayTitle).campusFont(.title).foregroundStyle(Color(hex: 0x1B2730))
                    Text(notice["content"].string ?? notice["source_text"].text)
                        .campusFont(.body).foregroundStyle(Color(hex: 0x1B2730)).textSelection(.enabled)
                    Divider()
                    if let source = notice["source_name"].string?.nonEmpty {
                        LabeledContent("来源", value: source).campusFont(.caption)
                    }
                    if let date = notice["published_at"].string {
                        LabeledContent("发布时间", value: date).campusFont(.caption)
                    }
                    CampusPrimaryButton(title: "提取待办", systemImage: "text.badge.plus") { extract = true }
                    if let noticeID = notice["id"].string {
                        NavigationLink { NoticeWorkflowView(noticeID: noticeID) } label: {
                            HStack {
                                Label("通知办理与动作确认", systemImage: "checklist")
                                    .campusFont(.body).foregroundStyle(Color(hex: 0x285B4B))
                                Spacer()
                                Image(systemName: "chevron.right").font(.system(size: 12)).foregroundStyle(.secondary)
                            }
                            .padding(14)
                            .background(Color(hex: 0xFFFEF8), in: RoundedRectangle(cornerRadius: 14))
                        }
                        .buttonStyle(.plain)
                    }
                }
                .padding(20)
                .frame(maxWidth: 700)
                .frame(maxWidth: .infinity)
            }
        }
        .task {
            if let announcementID = notice["announcement_id"].string {
                do { _ = try await app.client.request(.post, path: "announcements/\(announcementID.pathComponent)/read") }
                catch { self.error = error.localizedDescription }
            }
        }
        .sheet(isPresented: $extract) {
            NavigationStack {
                TaskImportView(noticeMode: true, initialContent: notice["content"].string ?? notice["source_text"].text)
            }
        }
        .errorAlert($error)
    }
}
