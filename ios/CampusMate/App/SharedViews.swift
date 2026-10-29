import SwiftUI
import CampusCore

@MainActor @Observable
final class RemoteResource {
    var value: JSONValue = .null
    var isLoading = false
    var error: String?
    private var loadID = UUID()

    func load(client: APIClient, path: String, query: [String: String] = [:]) async {
        let id = UUID(); loadID = id
        isLoading = true; error = nil
        defer { if loadID == id { isLoading = false } }
        do {
            let response = try await client.request(path: path, query: query)
            guard !Task.isCancelled, loadID == id else { return }
            value = response
        } catch is CancellationError { }
        catch { if loadID == id { self.error = error.localizedDescription } }
    }
}

struct ResourceStateView: View {
    let resource: RemoteResource
    let isEmpty: Bool
    var title = "暂无内容"
    var message = "新的内容会显示在这里。"
    var systemImage = "tray"
    var retry: (() async -> Void)?

    var body: some View {
        if resource.isLoading && isEmpty { ProgressView("正在加载…").frame(maxWidth: .infinity).padding(32) }
        else if let error = resource.error {
            ContentUnavailableView {
                Label("暂时无法加载", systemImage: "wifi.exclamationmark")
            } description: { Text(error) } actions: {
                if let retry { Button("重试") { Task { await retry() } }.buttonStyle(.bordered) }
            }
        } else if isEmpty {
            ContentUnavailableView(title, systemImage: systemImage, description: Text(message))
        }
    }
}

struct RecordRow: View {
    let value: JSONValue
    var icon = "doc.text"

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: icon).foregroundStyle(.tint).frame(width: 24).padding(.top, 2)
            VStack(alignment: .leading, spacing: 5) {
                Text(value.displayTitle).font(.body.weight(.medium)).lineLimit(2)
                if let subtitle = value.displaySubtitle.nonEmpty { Text(subtitle).font(.subheadline).foregroundStyle(.secondary).lineLimit(2) }
            }
            Spacer(minLength: 0)
            if let status = value["status"].string { Text(status.localizedStatus).font(.caption).foregroundStyle(.secondary) }
        }.padding(.vertical, 4)
    }
}

struct SimpleRemoteList: View {
    @Environment(AppModel.self) private var app
    let title: String
    let path: String
    var icon = "doc.text"
    var query: [String: String] = [:]
    @State private var resource = RemoteResource()

    var body: some View {
        List {
            ResourceStateView(resource: resource, isEmpty: resource.value.items.isEmpty, retry: load)
            ForEach(Array(resource.value.items.enumerated()), id: \.offset) { _, item in
                NavigationLink { RecordDetailView(value: item, title: title) } label: { RecordRow(value: item, icon: icon) }
            }
        }
        .navigationTitle(title)
        .task { await load() }
        .refreshable { await load() }
    }
    private func load() async { await resource.load(client: app.client, path: path, query: query) }
}

struct RecordDetailView: View {
    let value: JSONValue
    var title = "详情"
    var body: some View {
        List {
            Section {
                Text(value.displayTitle).font(.title2.bold()).textSelection(.enabled)
                if let content = (value["content"].string ?? value["description"].string ?? value["body"].string ?? value["summary"].string)?.nonEmpty {
                    Text(LocalizedStringKey(content)).textSelection(.enabled)
                }
            }
            Section {
                ForEach(Self.fields, id: \.0) { key, label in
                    if let text = value[key].string?.nonEmpty { LabeledContent(label, value: key == "status" ? text.localizedStatus : text) }
                }
            }
        }.navigationTitle(title).navigationBarTitleDisplayMode(.inline)
    }
    private static let fields: [(String, String)] = [
        ("course_name", "课程"), ("teacher_name", "教师"), ("semester", "学期"),
        ("source_name", "来源"), ("status", "状态"), ("deadline", "截止时间"),
        ("due_at", "截止时间"), ("exam_date", "考试日期"), ("start_time", "开始时间"),
        ("end_time", "结束时间"), ("location", "地点"), ("seat_number", "座位"),
        ("created_at", "创建时间"), ("published_at", "发布时间"), ("notes", "备注"),
    ]
}

extension JSONValue {
    var displayTitle: String {
        for key in ["title", "name", "course_name", "goal", "filename", "file_name", "topic", "label"] {
            if let value = self[key].string?.nonEmpty { return value }
        }
        return "详情"
    }
    var displaySubtitle: String {
        for key in ["description", "summary", "course_name", "teacher_name", "source_name", "content", "created_at"] {
            if let value = self[key].string?.nonEmpty { return value }
        }
        return ""
    }
}

extension String {
    var localizedStatus: String {
        ["pending": "待完成", "completed": "已完成", "active": "进行中", "running": "进行中",
         "paused": "已暂停", "ended": "已结束", "failed": "失败", "cancelled": "已取消",
         "draft": "草稿", "archived": "已归档", "submitted": "已提交", "ready": "已就绪",
         "queued": "排队中", "accepted": "已加入", "succeeded": "已完成"][self] ?? self
    }
}

struct ErrorAlertModifier: ViewModifier {
    @Binding var message: String?
    func body(content: Content) -> some View {
        content.alert("操作未完成", isPresented: Binding(get: { message != nil }, set: { if !$0 { message = nil } })) {
            Button("好", role: .cancel) { message = nil }
        } message: { Text(message ?? "") }
    }
}

extension View {
    func errorAlert(_ message: Binding<String?>) -> some View { modifier(ErrorAlertModifier(message: message)) }
}
