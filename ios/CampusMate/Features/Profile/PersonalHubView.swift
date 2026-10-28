import SwiftUI
import UniformTypeIdentifiers
import QuickLook
import UserNotifications
import CampusCore

struct PersonalHubView: View {
    @Environment(\.campus) private var palette
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    var favorites = false
    @State private var resource = RemoteResource()
    @State private var importing = false
    @State private var working = false
    @State private var error: String?
    @State private var deleting: JSONValue?
    private var scope: String { app.serverURL + "|" + (app.session?.user.id ?? "") }

    var body: some View {
        CampusSecondaryScaffold(title: favorites ? "我的收藏" : "我的文件") {
            ScrollView {
                VStack(spacing: 10) {
                    if resource.isLoading && resource.value == .null { CampusLoadingState() }
                    else if let error = resource.error, resource.value == .null { CampusErrorState(message: error) { Task { await load() } } }
                    else if resource.value.items.isEmpty {
                        CampusEmptyState(title: favorites ? "还没有收藏" : "还没有个人文件",
                                         message: favorites ? "收藏的内容会保存在这里。" : "选择一个文件，整理你的学习资料。",
                                         systemImage: favorites ? "star" : "folder")
                    } else {
                        ForEach(Array(resource.value.items.enumerated()), id: \.offset) { _, item in
                            NavigationLink {
                                if favorites { SavedDestinationView(value: item) } else { PersonalFileView(item: item) }
                            } label: {
                                hubRow(item)
                            }
                            .buttonStyle(.plain)
                            .contextMenu {
                                Button(favorites ? "移除收藏" : "删除", role: .destructive) { deleting = item }
                            }
                        }
                    }
                    if !favorites {
                        Text("文件信息可跨设备同步；原文件保留在本机。用于生成课堂的文件，请在互动课堂页面另行上传。")
                            .campusFont(.caption).foregroundStyle(.secondary)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                .padding(20)
                .frame(maxWidth: 700)
                .frame(maxWidth: .infinity)
            }
        }
        .toolbar {
            if !favorites {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { importing = true } label: { Image(systemName: "plus") }
                        .accessibilityLabel("添加文件")
                }
            }
        }
        .task { await load() }
        .refreshable { await load() }
        .fileImporter(isPresented: $importing, allowedContentTypes: [.item], allowsMultipleSelection: false) { result in
            do { if let url = try result.get().first { add(url) } } catch { self.error = error.localizedDescription }
        }
        .confirmationDialog(favorites ? "移除这项收藏？" : "删除这项文件记录和本机副本？",
                            isPresented: Binding(get: { deleting != nil }, set: { if !$0 { deleting = nil } }), titleVisibility: .visible) {
            if let deleting {
                Button("确认删除", role: .destructive) {
                    Task {
                        do {
                            if favorites { try await PersonalService(client: app.client).removeFavorite(id: deleting["id"].text) }
                            else {
                                try await PersonalService(client: app.client).removeFile(id: deleting["id"].text)
                                try LocalFileStore.remove(id: deleting["id"].text, scope: scope)
                            }
                            self.deleting = nil; await load()
                        } catch { self.error = error.localizedDescription }
                    }
                }
            }
        }
        .errorAlert($error)
    }

    private func hubRow(_ item: JSONValue) -> some View {
        HStack(spacing: 12) {
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(Color(hex: 0xE4EEE5)).frame(width: 42, height: 42)
                .overlay(Image(systemName: favorites ? "star.fill" : "doc.text")
                    .font(.system(size: 17)).foregroundStyle(palette.primary))
            VStack(alignment: .leading, spacing: 3) {
                Text(item.displayTitle).campusFont(.body).foregroundStyle(palette.textPrimary).lineLimit(1)
                let subtitle = [item["category"].text, item["size_label"].text].filter { !$0.isEmpty }.joined(separator: " · ")
                if !subtitle.isEmpty { Text(subtitle).campusFont(.caption).foregroundStyle(.secondary) }
            }
            Spacer()
            Image(systemName: "chevron.right").font(.system(size: 12)).foregroundStyle(.secondary)
        }
        .padding(14)
        .background(palette.surface, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(Color(hex: 0xD7DED5, opacity: 0.6), lineWidth: 1))
    }

    private func load() async {
        await resource.load(client: app.client, path: favorites ? "personal-hub/favorites" : "personal-hub/files")
    }

    private func add(_ source: URL) {
        working = true
        Task {
            defer { working = false }
            var copied: URL?
            do {
                let file = try LocalFileStore.importFile(source, scope: scope); copied = file
                let size = (try? file.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? 0
                let result = try await app.client.request(.post, path: "personal-hub/files", body: [
                    "name": .string(source.lastPathComponent), "category": "学习资料", "source": "iOS 本机",
                    "size_label": .string(ByteCountFormatter.string(fromByteCount: Int64(size), countStyle: .file))
                ])
                guard let id = result["id"].string else { throw APIError(code: "INVALID_RESPONSE", message: "文件记录未返回有效标识。") }
                try LocalFileStore.register(file, id: id, scope: scope)
                copied = nil; await load()
            } catch {
                if let copied { try? FileManager.default.removeItem(at: copied) }
                self.error = error.localizedDescription
            }
        }
    }
}

struct PersonalFileView: View {
    @Environment(\.campus) private var palette
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    let item: JSONValue
    @State private var current: JSONValue = .null
    @State private var preview: URL?
    @State private var working = false
    @State private var error: String?
    private var value: JSONValue { current == .null ? item : current }
    private var scope: String { app.serverURL + "|" + (app.session?.user.id ?? "") }
    private var localFile: URL? { LocalFileStore.file(id: item["id"].text, scope: scope) }

    var body: some View {
        CampusSecondaryScaffold(title: "文件详情") {
            ScrollView {
                VStack(spacing: 12) {
                    CampusCard {
                        VStack(alignment: .leading, spacing: 8) {
                            Text(value["name"].text).campusFont(.title).foregroundStyle(palette.textPrimary)
                            if let size = value["size_label"].string { LabeledContent("大小", value: size).campusFont(.caption) }
                            if let category = value["category"].string { LabeledContent("分类", value: category).campusFont(.caption) }
                            if let source = value["source"].string { LabeledContent("来源", value: source).campusFont(.caption) }
                        }
                    }
                    if let file = localFile {
                        CampusPrimaryButton(title: "预览文件", systemImage: "doc.text.magnifyingglass") { preview = file }
                        ShareLink(item: file) {
                            Label("分享文件", systemImage: "square.and.arrow.up")
                                .campusFont(.body).foregroundStyle(palette.primary)
                                .frame(maxWidth: .infinity).frame(height: 44)
                                .background(Color(hex: 0xE4EEE5), in: RoundedRectangle(cornerRadius: 14))
                        }
                    } else {
                        Label("原文件不在这台设备上", systemImage: "icloud.slash").campusFont(.caption).foregroundStyle(.secondary)
                    }
                    CampusSecondaryButton(title: value["is_favorite"].bool == true ? "取消收藏" : "收藏",
                                          systemImage: value["is_favorite"].bool == true ? "star.fill" : "star",
                                          enabled: !working) { favorite() }
                }
                .padding(20)
                .frame(maxWidth: 700)
                .frame(maxWidth: .infinity)
            }
        }
        .quickLookPreview($preview)
        .errorAlert($error)
    }

    private func favorite() {
        working = true
        Task {
            defer { working = false }
            do {
                current = try await PersonalService(client: app.client).favoriteFile(id: item["id"].text,
                                                                                     favorite: value["is_favorite"].bool != true)
                let favoriteID = "file:" + item["id"].text
                if current["is_favorite"].bool == true {
                    _ = try await app.client.request(.post, path: "personal-hub/favorites", body: [
                        "id": .string(favoriteID), "title": item["name"], "type": "文件",
                        "subtitle": item["category"], "source_route": "files"
                    ])
                } else {
                    try await PersonalService(client: app.client).removeFavorite(id: favoriteID)
                }
            } catch { self.error = error.localizedDescription }
        }
    }
}

struct SavedDestinationView: View {
    let value: JSONValue
    var body: some View {
        let route = value["source_route"].text.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        let parts = route.split(separator: "/").map(String.init)
        if parts.count >= 2 && parts[0] == "courses" { CourseDetailView(courseID: parts[1]) }
        else if parts.count >= 2 && parts[0] == "community_detail" { CommunityDetailView(postID: parts[1]) }
        else if parts.count >= 2 && parts[0] == "task_detail", let task = try? TaskItem(json: ["id": .string(parts[1]), "title": value["title"]]) { TaskDetailView(initial: task) }
        else if route == "files" && value["id"].text.hasPrefix("file:") {
            PersonalFileView(item: ["id": .string(String(value["id"].text.dropFirst(5))), "name": value["title"]])
        } else { RecordDetailView(value: value, title: "收藏详情") }
    }
}
