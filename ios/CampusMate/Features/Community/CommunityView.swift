import SwiftUI
import PhotosUI
import CampusCore

/// Port of `CommunityScreen`: forum header, hot-topic card, category chips and
/// post cards. Publishing keeps the native photo picker and upload flow.
struct CommunityView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    var initialSort = "time"
    @State private var resource = PagedResource()
    @State private var search = ""
    @State private var sort = "time"
    @State private var category: String?
    @State private var categories: [(key: String, label: String)] = []
    @State private var hot: [JSONValue] = []
    @State private var showPublish = false

    private var query: [String: String] {
        var values = ["sort": sort]
        if let search = search.nonEmpty { values["q"] = search }
        if let category { values["category"] = category }
        return values
    }

    var body: some View {
        CampusSecondaryScaffold(title: "校园论坛") {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    header
                    if app.session?.user.universityID.isEmpty != false {
                        HStack(spacing: 10) {
                            Image(systemName: "building.columns").foregroundStyle(Color(hex: 0x285B4B))
                            Text("选择学校后，查看本校同学的分享。").campusFont(.caption).foregroundStyle(.secondary)
                            Spacer()
                            NavigationLink("选择学校") { UniversityPickerView() }
                                .campusFont(.caption).foregroundStyle(Color(hex: 0x285B4B))
                        }
                        .padding(14)
                        .background(Color(hex: 0xE4EEE5), in: RoundedRectangle(cornerRadius: 16))
                    }
                    hotCard
                    categoryChips
                    searchRow
                    if resource.isLoading && resource.items.isEmpty {
                        CampusLoadingState(message: "正在读取帖子…")
                    } else if let error = resource.error, resource.items.isEmpty {
                        CampusErrorState(message: error) { Task { await load() } }
                    } else if resource.items.isEmpty {
                        CampusEmptyState(title: "暂无帖子", message: "分享学习经验，或发起一个讨论。", systemImage: "bubble.left.and.bubble.right")
                    } else {
                        ForEach(Array(resource.items.enumerated()), id: \.offset) { _, post in
                            NavigationLink { CommunityDetailView(postID: post["id"].text) } label: {
                                postCard(post)
                            }
                            .buttonStyle(.plain)
                        }
                        if resource.hasMore {
                            Button("加载更多") { Task { await resource.load(client: app.client, path: "community/posts", query: query, reset: false) } }
                                .campusFont(.caption).foregroundStyle(Color(hex: 0x285B4B))
                                .frame(maxWidth: .infinity).padding(.vertical, 10)
                        }
                    }
                }
                .padding(.horizontal, 20)
                .padding(.bottom, 30)
                .frame(maxWidth: 760)
                .frame(maxWidth: .infinity)
            }
            .refreshable { await load() }
        }
        .task {
            if sort == "time" { sort = initialSort }
            await loadCategories()
            await load()
            await loadHot()
        }
        .task(id: query) {
            if !search.isEmpty { try? await Task.sleep(for: .milliseconds(250)) }
            guard !Task.isCancelled else { return }
            await load()
        }
        .sheet(isPresented: $showPublish, onDismiss: { Task { await load(); await loadHot() } }) {
            NavigationStack { PublishPostView() }
        }
    }

    private var header: some View {
        HStack {
            Text("提问 / 招募 / 带价帮忙").font(.system(size: 12)).foregroundStyle(Color(hex: 0x667784))
            Spacer()
            Button { showPublish = true } label: {
                HStack(spacing: 5) {
                    Image(systemName: "plus").font(.system(size: 12, weight: .bold))
                    Text("发帖").font(.system(size: 13, weight: .bold))
                }
                .foregroundStyle(.white)
                .padding(.horizontal, 15).padding(.vertical, 10)
                .background(Color(hex: 0x285B4B), in: RoundedRectangle(cornerRadius: 12))
            }
            .disabled(app.session?.user.universityID.isEmpty != false)
            .opacity(app.session?.user.universityID.isEmpty != false ? 0.5 : 1)
            .accessibilityIdentifier("community.publish")
        }
    }

    private var hotCard: some View {
        NavigationLink { CommunityHotTopicsView() } label: {
            VStack(alignment: .leading, spacing: 9) {
                HStack {
                    Text("今日热门话题").font(.system(size: 18, weight: .bold)).foregroundStyle(Color(hex: 0x1B2730))
                    Spacer()
                    Text("更多 ›").font(.system(size: 13)).foregroundStyle(Color(hex: 0x285B4B))
                }
                if hot.isEmpty {
                    Text("还没有热门话题，发一篇帖子开启讨论。").campusFont(.caption).foregroundStyle(Color(hex: 0x667784))
                } else {
                    ForEach(Array(hot.prefix(3).enumerated()), id: \.offset) { index, post in
                        HStack(spacing: 8) {
                            Text("TOP\(index + 1)")
                                .font(.system(size: 10, weight: .heavy))
                                .foregroundStyle(index == 0 ? Color(hex: 0xC25450) : Color(hex: 0x285B4B))
                            Text(post["title"].text).font(.system(size: 13)).foregroundStyle(Color(hex: 0x1B2730)).lineLimit(1)
                            Spacer(minLength: 0)
                        }
                    }
                }
            }
            .padding(16)
            .background(Color(hex: 0xFFFEF8), in: RoundedRectangle(cornerRadius: 20, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).strokeBorder(Color(hex: 0xD7DED5, opacity: 0.7), lineWidth: 1))
        }
        .buttonStyle(.plain)
    }

    private var categoryChips: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                CampusFilterChip(title: "全部", isSelected: category == nil) { category = nil }
                ForEach(categories, id: \.key) { item in
                    CampusFilterChip(title: item.label, isSelected: category == item.key) { category = item.key }
                }
            }
            .padding(.vertical, 2)
        }
    }

    private var searchRow: some View {
        HStack(spacing: 10) {
            HStack(spacing: 8) {
                Image(systemName: "magnifyingglass").font(.system(size: 13)).foregroundStyle(Color(hex: 0x667784))
                TextField("搜索", text: $search)
                    .font(.system(size: 13)).foregroundStyle(Color(hex: 0x1B2730))
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
            }
            .padding(.horizontal, 12).padding(.vertical, 10)
            .background(Color(hex: 0xFFFEF8), in: RoundedRectangle(cornerRadius: 10))
            .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(Color(hex: 0xD7DED5), lineWidth: 1))
            CampusFilterChip(title: "最新", isSelected: sort == "time") { sort = "time" }
            CampusFilterChip(title: "热门", isSelected: sort == "hot") { sort = "hot" }
        }
    }

    private func postCard(_ post: JSONValue) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 7) {
                if let label = categories.first(where: { $0.key == post["category"].text })?.label {
                    Text(label)
                        .font(.system(size: 10, weight: .semibold))
                        .foregroundStyle(Color(hex: 0x285B4B))
                        .padding(.horizontal, 8).padding(.vertical, 3)
                        .background(Color(hex: 0xE4EEE5), in: Capsule())
                }
                Text(post["author_name"].string ?? "同学")
                    .font(.system(size: 11)).foregroundStyle(Color(hex: 0x667784))
                Spacer()
                Text(post["created_at"].text.prefix(10))
                    .font(.system(size: 10)).foregroundStyle(Color(hex: 0x667784))
            }
            Text(post["title"].text).font(.system(size: 16, weight: .semibold)).foregroundStyle(Color(hex: 0x1B2730)).lineLimit(2)
            Text(post["content"].text).font(.system(size: 13)).foregroundStyle(Color(hex: 0x667784)).lineLimit(3)
            HStack(spacing: 16) {
                Label("\(post["like_count"].int ?? 0)", systemImage: "heart")
                Label("\(post["comment_count"].int ?? 0)", systemImage: "bubble.right")
                Spacer()
            }
            .font(.system(size: 11)).foregroundStyle(Color(hex: 0x667784))
        }
        .padding(15)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(Color(hex: 0xFFFEF8), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).strokeBorder(Color(hex: 0xD7DED5, opacity: 0.7), lineWidth: 1))
    }

    private func loadCategories() async {
        do {
            let value = try await app.client.request(path: "community/posts/categories")
            categories = value.items.compactMap { item in
                guard let key = item["key"].string, let label = item["label"].string else { return nil }
                return (key, label)
            }
        } catch { }
    }

    private func loadHot() async {
        do {
            let value = try await app.client.request(path: "community/posts", query: ["sort": "hot", "page": "1", "page_size": "3"])
            hot = value["items"].items
        } catch { }
    }

    private func load() async {
        await resource.load(client: app.client, path: "community/posts", query: query)
    }
}

struct CommunityHotTopicsView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var resource = PagedResource()

    var body: some View {
        CampusSecondaryScaffold(title: "热门话题") {
            ScrollView {
                VStack(spacing: 10) {
                    if resource.items.isEmpty && resource.isLoading { CampusLoadingState() }
                    else if resource.items.isEmpty { CampusEmptyState(title: "还没有热门话题", systemImage: "flame") }
                    ForEach(Array(resource.items.enumerated()), id: \.offset) { index, post in
                        NavigationLink { CommunityDetailView(postID: post["id"].text) } label: {
                            HStack(spacing: 12) {
                                Text("\(index + 1)").font(.system(size: 17, weight: .heavy))
                                    .foregroundStyle(index < 3 ? Color(hex: 0xC25450) : Color(hex: 0x667784))
                                    .frame(width: 26)
                                VStack(alignment: .leading, spacing: 3) {
                                    Text(post["title"].text).font(.system(size: 14, weight: .semibold))
                                        .foregroundStyle(Color(hex: 0x1B2730)).lineLimit(2)
                                    Text("\(post["like_count"].int ?? 0) 赞 · \(post["comment_count"].int ?? 0) 评论")
                                        .font(.system(size: 11)).foregroundStyle(Color(hex: 0x667784))
                                }
                                Spacer()
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
        .task { await resource.loadAll(client: app.client, path: "community/posts", query: ["sort": "hot"]) }
    }
}

struct CommunityDetailView: View {
    @Environment(\.campus) private var palette
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
        CampusSecondaryScaffold(title: "帖子详情") {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    if resource.isLoading && post == .null { CampusLoadingState() }
                    else if let error = resource.error, post == .null { CampusErrorState(message: error) { Task { await load() } } }
                    else if post != .null {
                        Text(post["title"].text).campusFont(.title).foregroundStyle(palette.textPrimary)
                        HStack(spacing: 8) {
                            Text(post["author_name"].string ?? "同学").campusFont(.caption).foregroundStyle(.secondary)
                            Text(post["created_at"].text.prefix(10)).campusFont(.caption).foregroundStyle(.secondary)
                        }
                        Text(post["content"].text).campusFont(.body).foregroundStyle(palette.textPrimary).textSelection(.enabled)
                        ForEach(Array(post["images"].items.enumerated()), id: \.offset) { _, item in
                            if let url = imageURL(item.string ?? item["url"].text) {
                                AsyncImage(url: url) { image in image.resizable().scaledToFit() } placeholder: { ProgressView() }
                                    .clipShape(RoundedRectangle(cornerRadius: 14))
                                    .accessibilityLabel("帖子图片")
                            }
                        }
                        HStack(spacing: 22) {
                            Button { interact("like", selected: post["liked"].bool ?? post["is_liked"].bool ?? false) } label: {
                                Label("\(post["like_count"].int ?? 0)", systemImage: (post["liked"].bool ?? post["is_liked"].bool ?? false) ? "heart.fill" : "heart")
                            }
                            Button { interact("favorite", selected: post["favorited"].bool ?? post["is_favorited"].bool ?? false) } label: {
                                Label("收藏", systemImage: (post["favorited"].bool ?? post["is_favorited"].bool ?? false) ? "star.fill" : "star")
                            }
                            Spacer()
                        }
                        .font(.system(size: 13)).foregroundStyle(palette.primary)
                        .buttonStyle(.plain).disabled(working)
                        Divider()
                        Text("讨论").campusFont(.subtitle).foregroundStyle(palette.textPrimary)
                        if comments.isLoading && comments.items.isEmpty { CampusLoadingState() }
                        else if comments.items.isEmpty {
                            Text("还没有评论，说说你的想法。").campusFont(.caption).foregroundStyle(.secondary)
                        }
                        ForEach(Array(comments.items.enumerated()), id: \.offset) { _, comment in
                            VStack(alignment: .leading, spacing: 5) {
                                Text(comment["author_name"].string ?? "同学").campusFont(.caption).foregroundStyle(.secondary)
                                Text(comment["content"].text).campusFont(.body).foregroundStyle(palette.textPrimary).textSelection(.enabled)
                            }
                            .padding(12)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(palette.surface, in: RoundedRectangle(cornerRadius: 12))
                        }
                        if comments.hasMore {
                            Button("加载更多评论") { Task { await comments.load(client: app.client, path: endpoint + "/comments", reset: false) } }
                                .campusFont(.caption).foregroundStyle(palette.primary)
                        }
                        CampusTextField(placeholder: "写评论…", text: $reply)
                        Toggle("匿名评论", isOn: $anonymous).tint(palette.primary)
                        CampusPrimaryButton(title: working ? "正在发送…" : "发表评论", loading: working,
                                            enabled: !reply.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty) { sendReply() }
                        if post["author_id"].string == app.session?.user.id || post["is_owner"].bool == true {
                            Button("删除帖子", role: .destructive) { confirmDelete = true }
                                .campusFont(.body).foregroundStyle(Color(hex: 0xC25450))
                        }
                    }
                }
                .padding(20)
                .frame(maxWidth: 700)
                .frame(maxWidth: .infinity)
            }
        }
        .task { await load(); await loadComments() }
        .refreshable { await load(); await loadComments() }
        .confirmationDialog("删除这篇帖子？", isPresented: $confirmDelete, titleVisibility: .visible) {
            Button("删除", role: .destructive) {
                Task {
                    do { _ = try await app.client.request(.delete, path: endpoint); dismiss() }
                    catch { self.error = error.localizedDescription }
                }
            }
        }
        .errorAlert($error)
    }

    private func load() async { await resource.load(client: app.client, path: endpoint) }
    private func loadComments() async { await comments.load(client: app.client, path: endpoint + "/comments") }
    private func interact(_ action: String, selected: Bool) {
        working = true
        Task {
            defer { working = false }
            do {
                _ = try await app.client.request(selected ? .delete : .post, path: endpoint + "/" + action)
                CampusHaptics.tap()
                await load()
            } catch { self.error = error.localizedDescription }
        }
    }
    private func sendReply() {
        working = true
        Task {
            defer { working = false }
            do {
                _ = try await app.client.request(.post, path: endpoint + "/comments",
                                                 body: ["content": .string(reply), "is_anonymous": .bool(anonymous)])
                reply = ""; await loadComments(); await load()
            } catch { self.error = error.localizedDescription }
        }
    }
    private func imageURL(_ path: String) -> URL? {
        let origin = URL(string: "/", relativeTo: app.client.baseURL)
        guard let url = URL(string: path, relativeTo: origin), ["http", "https"].contains(url.scheme),
              url.user == nil, url.password == nil else { return nil }
        return url
    }
}

struct PublishPostView: View {
    @Environment(\.campus) private var palette
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var title = ""
    @State private var content = ""
    @State private var category = "campus"
    @State private var anonymous = false
    @State private var photos: [PhotosPickerItem] = []
    @State private var working = false
    @State private var error: String?

    private let categories = [("campus", "校园"), ("study", "学习"), ("life", "生活"), ("secondhand", "二手"),
                              ("question", "问答"), ("activity", "活动"), ("experience", "经验"),
                              ("recruit", "招募"), ("errand", "互助"), ("other", "其他")]

    var body: some View {
        let photoCount = photos.count
        return CampusSecondaryScaffold(title: "发布帖子") {
            ScrollView {
                VStack(spacing: 12) {
                    CampusCard {
                        VStack(alignment: .leading, spacing: 12) {
                            CampusTextField(placeholder: "标题", text: $title)
                            TextEditor(text: $content)
                                .font(.system(size: 14))
                                .frame(minHeight: 180)
                                .scrollContentBackground(.hidden)
                                .padding(8)
                                .background(palette.background, in: RoundedRectangle(cornerRadius: 10))
                                .accessibilityLabel("帖子正文")
                        }
                    }
                    CampusCard {
                        VStack(alignment: .leading, spacing: 12) {
                            Picker("分类", selection: $category) {
                                ForEach(categories, id: \.0) { key, label in Text(label).tag(key) }
                            }
                            .tint(Color(hex: 0x285B4B))
                            Toggle("匿名发布", isOn: $anonymous).tint(Color(hex: 0x285B4B))
                            PhotosPicker(selection: $photos, maxSelectionCount: 9, matching: .images) {
                                PhotoAttachmentLabel(count: photoCount)
                            }
                            Text("只上传你选择的图片；单张图片需小于 5 MB。").campusFont(.caption).foregroundStyle(.secondary)
                        }
                    }
                    CampusPrimaryButton(title: working ? "发布中…" : "发布", loading: working,
                                        enabled: !title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                                            && !content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                                            && content.count <= 10000) { publish() }
                }
                .padding(20)
                .frame(maxWidth: 700)
                .frame(maxWidth: .infinity)
            }
        }
        .errorAlert($error)
    }

    private func publish() {
        working = true
        Task {
            defer { working = false }
            do {
                var images: [JSONValue] = []
                for photo in photos {
                    guard let original = try await photo.loadTransferable(type: Data.self),
                          let image = UIImage(data: original),
                          let data = image.jpegData(compressionQuality: 0.86),
                          data.count <= 5 * 1024 * 1024 else {
                        throw APIError(code: "IMAGE_TOO_LARGE", message: "有一张图片无法读取或大于 5 MB，请重新选择。")
                    }
                    let result = try await app.client.upload(path: "community/upload-image", filename: "image.jpg",
                                                             mimeType: "image/jpeg", data: data)
                    guard let url = result["url"].string else {
                        throw APIError(code: "INVALID_RESPONSE", message: "图片上传未返回有效地址。")
                    }
                    images.append(.string(url))
                }
                _ = try await app.client.request(.post, path: "community/posts", body: [
                    "title": .string(title), "content": .string(content), "category": .string(category),
                    "is_anonymous": .bool(anonymous), "images": .array(images)
                ])
                CampusHaptics.success()
                dismiss()
            } catch is CancellationError { }
            catch { self.error = error.localizedDescription }
        }
    }
}

private struct PhotoAttachmentLabel: View {
    @Environment(\.campus) private var palette
    let count: Int
    nonisolated init(count: Int) { self.count = count }
    var body: some View {
        Label("选择图片（\(count)/9）", systemImage: "photo.on.rectangle")
            .campusFont(.body)
            .foregroundStyle(palette.primary)
    }
}
