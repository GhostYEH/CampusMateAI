import SwiftUI
import CampusCore

struct NoticesView: View {
    @Environment(AppModel.self) private var app
    @State private var resource = PagedResource()
    @State private var unreadOnly = false
    @State private var showExtract = false
    private var query: [String: String] { ["unread_only": String(unreadOnly)] }
    var body: some View {
        List {
            Section {
                Toggle("只看未读", isOn: $unreadOnly)
                NavigationLink { ChaoxingView() } label: { Label("学习通同步", systemImage: "arrow.triangle.2.circlepath") }
            }
            Section("通知") {
                PagedStatusView(resource: resource, emptyTitle: "暂无通知", emptyMessage: "同步学习通或手动粘贴通知后查看。", icon: "bell", retry: load)
                ForEach(Array(resource.items.enumerated()), id: \.offset) { _, notice in
                    NavigationLink { NoticeDetailView(notice: notice) } label: { RecordRow(value: notice, icon: "bell") }
                }
                LoadMoreRow(resource: resource) { await resource.load(client: app.client, path: "notices", query: query, reset: false) }
            }
            Section {
                Text("iOS 通过服务端同步和手动导入整理通知。你可以复制其他应用中的通知原文，再在这里提取待办。")
                    .font(.footnote).foregroundStyle(.secondary)
            }
        }
        .navigationTitle("通知中心").task(id: unreadOnly) { await load() }.refreshable { await load() }
        .toolbar { Button("提取", systemImage: "text.badge.plus") { showExtract = true } }
        .sheet(isPresented: $showExtract, onDismiss: { Task { await load() } }) { NavigationStack { TaskImportView(noticeMode: true) } }
    }
    private func load() async { await resource.load(client: app.client, path: "notices", query: query) }
}

struct NoticeDetailView: View {
    @Environment(AppModel.self) private var app
    let notice: JSONValue
    @State private var extract = false
    @State private var error: String?
    var body: some View {
        List {
            Section {
                Text(notice.displayTitle).font(.title2.bold())
                Text(notice["content"].string ?? notice["source_text"].text).textSelection(.enabled)
            }
            Section {
                if let source = notice["source_name"].string?.nonEmpty { LabeledContent("来源", value: source) }
                if let date = notice["published_at"].string { LabeledContent("发布时间", value: date) }
                Button("提取待办", systemImage: "text.badge.plus") { extract = true }
            }
        }.navigationTitle("通知详情").navigationBarTitleDisplayMode(.inline)
        .task {
            let announcementID = notice["announcement_id"].string
            if let announcementID {
                do { _ = try await app.client.request(.post, path: "announcements/\(announcementID.pathComponent)/read") }
                catch { self.error = error.localizedDescription }
            }
        }
        .sheet(isPresented: $extract) { NavigationStack { TaskImportView(noticeMode: true) } }
        .errorAlert($error)
    }
}
