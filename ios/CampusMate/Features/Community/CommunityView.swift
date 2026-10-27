import SwiftUI
import PhotosUI
import CampusCore

struct CommunityView: View {
    @Environment(AppModel.self) private var app
    var initialSort = "time"
    @State private var resource = PagedResource()
    @State private var search = ""
    @State private var sort = "time"
    @State private var showPublish = false
    private var query: [String: String] {
        var values = ["sort": sort]
        if let search = search.nonEmpty { values["q"] = search }
        return values
    }
    var body: some View {
        List {
            if app.session?.user.universityID.isEmpty == true {
                Section {
                    Label("选择学校后，查看本校同学的分享。", systemImage: "building.columns")
                    NavigationLink("选择学校") { UniversityPickerView() }
                }
            }
            Section {
                Picker("排序", selection: $sort) { Text("最新").tag("time"); Text("热门").tag("hot") }.pickerStyle(.segmented)
            }.listRowBackground(Color.clear)
            PagedStatusView(resource: resource, emptyTitle: "暂无帖子", emptyMessage: "分享学习经验，或发起一个讨论。", icon: "bubble.left.and.bubble.right", retry: load)
            ForEach(Array(resource.items.enumerated()), id: \.offset) { _, post in
                NavigationLink { CommunityDetailView(postID: post["id"].text) } label: {
                    VStack(alignment: .leading, spacing: 9) {
                        Text(post["title"].text).font(.headline)
                        Text(post["content"].text).font(.subheadline).foregroundStyle(.secondary).lineLimit(3)
                        HStack {
                            Text(post["author_name"].string ?? "同学")
                            Spacer()
                            Label("\(post["like_count"].int ?? 0)", systemImage: "heart")
                            Label("\(post["comment_count"].int ?? 0)", systemImage: "bubble.right")
                        }.font(.caption).foregroundStyle(.secondary)
                    }.padding(.vertical, 6)
                }
            }
            LoadMoreRow(resource: resource) { await resource.load(client: app.client, path: "community/posts", query: query, reset: false) }
        }
        .navigationTitle("校园社区").searchable(text: $search, prompt: "搜索帖子")
        .task(id: query) { if !search.isEmpty { try? await Task.sleep(for: .milliseconds(250)) }; guard !Task.isCancelled else { return }; await load() }
        .onAppear { if sort == "time" { sort = initialSort } }
        .refreshable { await load() }
        .toolbar { Button("发布", systemImage: "square.and.pencil") { showPublish = true }.disabled(app.session?.user.universityID.isEmpty != false) }
        .sheet(isPresented: $showPublish, onDismiss: { Task { await load() } }) { NavigationStack { PublishPostView() } }
    }
    private func load() async { await resource.load(client: app.client, path: "community/posts", query: query) }
}

struct CommunityDetailView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    let postID: String
    @State private var resource = RemoteResource()
    @State private var comments = PagedResource()
    @State private var reply = ""
    @State private var anonymous = false
    @State private var working = false
    @State private var error: String?
    @State private var confirmDelete = false
    private var endpoint: String { "community/posts/\(postID.pathComponent)" }
    private var post: JSONValue { resource.value }

    var body: some View {
        List {
            ResourceStateView(resource: resource, isEmpty: post == .null, retry: load)
            if post != .null {
                Section {
                    Text(post["title"].text).font(.title2.bold())
                    Text(post["author_name"].string ?? "同学").font(.caption).foregroundStyle(.secondary)
                    Text(post["content"].text).textSelection(.enabled)
                    ForEach(Array(post["images"].items.enumerated()), id: \.offset) { _, item in
                        if let url = imageURL(item.string ?? item["url"].text) {
                            AsyncImage(url: url) { image in image.resizable().scaledToFit() } placeholder: { ProgressView() }
                                .clipShape(RoundedRectangle(cornerRadius: 12)).accessibilityLabel("帖子图片")
                        }
                    }
                    HStack(spacing: 24) {
                        Button { interact("like", selected: post["liked"].bool ?? post["is_liked"].bool ?? false) } label: {
                            Label("\(post["like_count"].int ?? 0)", systemImage: (post["liked"].bool ?? post["is_liked"].bool ?? false) ? "heart.fill" : "heart")
                        }
                        Button { interact("favorite", selected: post["favorited"].bool ?? post["is_favorited"].bool ?? false) } label: {
                            Label("收藏", systemImage: (post["favorited"].bool ?? post["is_favorited"].bool ?? false) ? "star.fill" : "star")
                        }
                    }.buttonStyle(.borderless).disabled(working)
                }
                Section("讨论") {
                    PagedStatusView(resource: comments, emptyTitle: "还没有评论", emptyMessage: "说说你的想法。", icon: "bubble.right", retry: loadComments)
                    ForEach(Array(comments.items.enumerated()), id: \.offset) { _, comment in
                        VStack(alignment: .leading, spacing: 6) {
                            Text(comment["author_name"].string ?? "同学").font(.caption).foregroundStyle(.secondary)
                            Text(comment["content"].text).textSelection(.enabled)
                        }.padding(.vertical, 3)
                    }
                    LoadMoreRow(resource: comments) { await comments.load(client: app.client, path: endpoint + "/comments", reset: false) }
                    TextField("写评论…", text: $reply, axis: .vertical).lineLimit(2...6)
                    Toggle("匿名评论", isOn: $anonymous)
                    Button(working ? "正在发送…" : "发表评论") { sendReply() }.disabled(working || reply.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
                if post["author_id"].string == app.session?.user.id || post["is_owner"].bool == true {
                    Section { Button("删除帖子", role: .destructive) { confirmDelete = true } }
                }
            }
        }.navigationTitle("帖子详情").navigationBarTitleDisplayMode(.inline).task { await load(); await loadComments() }.refreshable { await load(); await loadComments() }
        .confirmationDialog("删除这篇帖子？", isPresented: $confirmDelete, titleVisibility: .visible) {
            Button("删除", role: .destructive) {
                Task { do { _ = try await app.client.request(.delete, path: endpoint); dismiss() } catch { self.error = error.localizedDescription } }
            }
        }.errorAlert($error)
    }
    private func load() async { await resource.load(client: app.client, path: endpoint) }
    private func loadComments() async { await comments.load(client: app.client, path: endpoint + "/comments") }
    private func interact(_ action: String, selected: Bool) {
        working = true
        Task {
            defer { working = false }
            do { _ = try await app.client.request(selected ? .delete : .post, path: endpoint + "/" + action); await load() }
            catch { self.error = error.localizedDescription }
        }
    }
    private func sendReply() {
        working = true
        Task {
            defer { working = false }
            do {
                _ = try await app.client.request(.post, path: endpoint + "/comments", body: ["content": .string(reply), "is_anonymous": .bool(anonymous)])
                reply = ""; await loadComments(); await load()
            } catch { self.error = error.localizedDescription }
        }
    }
    private func imageURL(_ path: String) -> URL? {
        let origin = URL(string: "/", relativeTo: app.client.baseURL)
        guard let url = URL(string: path, relativeTo: origin), ["http", "https"].contains(url.scheme), url.user == nil, url.password == nil else { return nil }
        return url
    }
}

struct PublishPostView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var title = ""
    @State private var content = ""
    @State private var category = "campus"
    @State private var anonymous = false
    @State private var photos: [PhotosPickerItem] = []
    @State private var working = false
    @State private var error: String?
    private let categories = [("campus", "校园"), ("study", "学习"), ("life", "生活"), ("secondhand", "二手"), ("question", "问答"), ("activity", "活动"), ("experience", "经验"), ("recruit", "招募"), ("errand", "互助"), ("other", "其他")]

    var body: some View {
        let photoCount = photos.count
        Form {
            Section("分享内容") {
                TextField("标题", text: $title).onChange(of: title) { _, value in if value.count > 120 { title = String(value.prefix(120)) } }
                TextEditor(text: $content).frame(minHeight: 180).accessibilityLabel("帖子正文")
            }
            Section {
                Picker("分类", selection: $category) { ForEach(categories, id: \.0) { key, label in Text(label).tag(key) } }
                Toggle("匿名发布", isOn: $anonymous)
                PhotosPicker(selection: $photos, maxSelectionCount: 9, matching: .images) { Label("选择图片（\(photoCount)/9）", systemImage: "photo.on.rectangle") }
            } footer: { Text("只上传你选择的图片；单张图片需小于 5 MB。") }
        }.navigationTitle("发布帖子").navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .cancellationAction) { Button("取消") { dismiss() }.disabled(working) }
            ToolbarItem(placement: .confirmationAction) { Button(working ? "发布中…" : "发布", action: publish).disabled(working || title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || content.count > 10000) }
        }.errorAlert($error)
    }
    private func publish() {
        working = true
        Task {
            defer { working = false }
            do {
                var images: [JSONValue] = []
                for photo in photos {
                    guard let original = try await photo.loadTransferable(type: Data.self), let image = UIImage(data: original), let data = image.jpegData(compressionQuality: 0.86), data.count <= 5 * 1024 * 1024 else { throw APIError(code: "IMAGE_TOO_LARGE", message: "有一张图片无法读取或大于 5 MB，请重新选择。") }
                    let result = try await app.client.upload(path: "community/upload-image", filename: "image.jpg", mimeType: "image/jpeg", data: data)
                    guard let url = result["url"].string else { throw APIError(code: "INVALID_RESPONSE", message: "图片上传未返回有效地址。") }
                    images.append(.string(url))
                }
                _ = try await app.client.request(.post, path: "community/posts", body: ["title": .string(title), "content": .string(content), "category": .string(category), "is_anonymous": .bool(anonymous), "images": .array(images)])
                dismiss()
            } catch is CancellationError { }
            catch { self.error = error.localizedDescription }
        }
    }
}
