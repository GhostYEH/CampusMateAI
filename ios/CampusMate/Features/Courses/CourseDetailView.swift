import SwiftUI
import QuickLook
import UniformTypeIdentifiers
import CampusCore

/// The course "book" opened from the shelf. Android presents this as a bottom
/// sheet; iOS keeps the same book-cover hierarchy in a large sheet so the
/// chapter list can breathe.
struct CourseBookSheet: View {
    @Environment(\.dismiss) private var dismiss
    let course: CourseSummary

    var body: some View {
        NavigationStack {
            CourseBookBody(courseID: course.id, summary: course, showsClose: true) { dismiss() }
        }
        .presentationDetents([.large])
        .presentationDragIndicator(.visible)
    }
}

/// Full page variant used by deep links (task → course, classroom → course).
struct CourseDetailView: View {
    let courseID: String
    var body: some View {
        CourseBookBody(courseID: courseID, summary: nil, showsClose: false) { }
    }
}

private struct CourseBookBody: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @Environment(\.openURL) private var openURL
    let courseID: String
    let summary: CourseSummary?
    let showsClose: Bool
    let onClose: () -> Void

    @State private var detail = RemoteResource()
    @State private var content = PagedResource()
    @State private var syncing = false
    @State private var filter = "全部"
    @State private var preview: URL?
    @State private var downloading: String?
    @State private var error: String?

    private let ink = Color(hex: 0x263A50)
    private let copper = Color(hex: 0xAE6C49)
    private let line = Color(hex: 0xD7C19C)
    private let filters = ["全部", "章节", "资料", "作业", "通知", "考试", "讨论"]

    private var course: JSONValue {
        detail.value["course"].object == nil ? detail.value : detail.value["course"]
    }
    private var items: [JSONValue] { content.items }
    private var kinds: [String: Set<String>] {
        ["章节": ["chapter"],
         "资料": ["document", "video", "audio", "image", "material", "link"],
         "作业": ["assignment"], "通知": ["notice"], "考试": ["exam"], "讨论": ["discussion"]]
    }
    private var options: [String] {
        let populated = filters.dropFirst().filter { name in items.contains { kinds[name]?.contains($0["kind"].text) == true } }
        return populated.count > 1 ? ["全部"] + populated : (populated.isEmpty ? ["全部"] : Array(populated))
    }
    private var visible: [JSONValue] {
        guard let accepted = kinds[filter] else { return items }
        return items.filter { accepted.contains($0["kind"].text) }
    }
    private var displayName: String {
        summary?.name ?? course["name"].text.nonEmpty ?? "课程"
    }

    var body: some View {
        ZStack {
            LinearGradient(colors: [Color(hex: 0xF8F1E2), Color(hex: 0xEDE1CA)], startPoint: .top, endPoint: .bottom)
                .ignoresSafeArea()
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    cover
                    if detail.isLoading && detail.value == .null {
                        CampusLoadingState(message: "正在翻开课程…")
                    } else if let error = detail.error, detail.value == .null {
                        CampusErrorState(message: error) { Task { await load() } }
                    } else {
                        meta
                        filterChips
                        contentList
                        navigationRows
                        if course["provider"].text == "chaoxing" { syncRow }
                        if let warning = course["sync_warning"].string?.nonEmpty {
                            Text(warning).font(.system(size: 11)).foregroundStyle(copper)
                        }
                    }
                }
                .padding(.horizontal, 22)
                .padding(.bottom, 34)
                .frame(maxWidth: 760)
                .frame(maxWidth: .infinity)
            }
        }
        .campusImmersive()
        .safeAreaInset(edge: .top) {
            HStack(spacing: 10) {
                CampusBackButton { showsClose ? onClose() : dismiss() }
                Spacer()
                if showsClose {
                    Button("收起") { onClose() }
                        .font(.system(size: 13, weight: .semibold))
                        .foregroundStyle(ink)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 8)
                        .background(Color(hex: 0xF8F0DF), in: Capsule())
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 4)
            .padding(.bottom, 4)
            .background(Color(hex: 0xF8F1E2).opacity(0.94))
        }
        .task { await load() }
        .refreshable { await load() }
        .quickLookPreview($preview)
        .errorAlert($error)
    }

    private var cover: some View {
        HStack(spacing: 0) {
            Rectangle().fill(ink).frame(width: 9)
            VStack(alignment: .leading, spacing: 5) {
                Text("课程藏书  /  \(summary?.type ?? course["type"].text.nonEmpty ?? "课程")")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(copper)
                Text(displayName)
                    .font(.system(size: 24, weight: .bold))
                    .foregroundStyle(ink)
                    .lineLimit(3)
                Text([summary?.teacher ?? course["teacher_name"].text,
                      summary?.semester ?? course["semester"].text].filter { !$0.isEmpty }.joined(separator: " · "))
                    .font(.system(size: 12))
                    .foregroundStyle(ink.opacity(0.62))
                if let description = course["description"].string?.nonEmpty {
                    Text(description)
                        .font(.system(size: 12))
                        .foregroundStyle(ink.opacity(0.72))
                        .lineLimit(3)
                        .padding(.top, 2)
                }
            }
            .padding(16)
            Spacer(minLength: 0)
        }
        .frame(minHeight: 118)
        .background(Color(hex: 0xF8F0DF))
        .overlay(Rectangle().strokeBorder(line, lineWidth: 1))
    }

    private var meta: some View {
        HStack(spacing: 8) {
            tag("\(items.count) 条内容", tone: copper)
            if let classes = detail.value["classes"].array, !classes.isEmpty {
                tag("\(classes.count) 个班级", tone: ink)
            }
            if course["provider"].text == "chaoxing" { tag("学习通", tone: CampusScene.libraryGreen) }
            Spacer()
        }
    }

    private func tag(_ text: String, tone: Color) -> some View {
        Text(text)
            .font(.system(size: 10.5, weight: .semibold))
            .foregroundStyle(tone)
            .padding(.horizontal, 9)
            .padding(.vertical, 4)
            .background(tone.opacity(0.10), in: Capsule())
    }

    private var filterChips: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(options, id: \.self) { option in
                    Button {
                        filter = option
                        CampusHaptics.selection()
                    } label: {
                        Text(option)
                            .font(.system(size: 12, weight: filter == option ? .semibold : .regular))
                            .foregroundStyle(filter == option ? Color.white : ink)
                            .padding(.horizontal, 14)
                            .padding(.vertical, 8)
                            .background(filter == option ? ink : Color(hex: 0xFBF4E6), in: Capsule())
                            .overlay(Capsule().strokeBorder(filter == option ? ink : line, lineWidth: 1))
                    }
                    .buttonStyle(CampusPressStyle())
                }
            }
            .padding(.vertical, 2)
        }
    }

    @ViewBuilder
    private var contentList: some View {
        if content.isLoading && items.isEmpty {
            CampusLoadingState(message: "正在读取目录…")
        } else if let error = content.error, items.isEmpty {
            CampusErrorState(message: error) { Task { await load() } }
        } else if visible.isEmpty {
            VStack(spacing: 6) {
                Image(systemName: "book.closed").font(.system(size: 26, weight: .light)).foregroundStyle(copper)
                Text("这一栏还没有内容").font(.system(size: 14, weight: .bold)).foregroundStyle(ink)
                Text("同步课程后会显示学习通返回的章节、资料与通知。").font(.system(size: 12)).foregroundStyle(ink.opacity(0.6))
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 30)
            .background(Color(hex: 0xFFFBF2), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(line.opacity(0.7), lineWidth: 1))
        } else {
            VStack(spacing: 0) {
                ForEach(Array(visible.enumerated()), id: \.offset) { index, item in
                    contentRow(item)
                    if index != visible.count - 1 {
                        Rectangle().fill(line.opacity(0.55)).frame(height: 1).padding(.leading, 44)
                    }
                }
            }
            .background(Color(hex: 0xFFFBF2), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(line.opacity(0.7), lineWidth: 1))
            if content.hasMore {
                Button("加载更多") { Task { await content.load(client: app.client, path: contentPath, reset: false) } }
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(copper)
                    .frame(maxWidth: .infinity)
            }
        }
    }

    private func contentRow(_ item: JSONValue) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            HStack(alignment: .top, spacing: 11) {
                Image(systemName: icon(for: item["kind"].text))
                    .font(.system(size: 16, weight: .medium))
                    .foregroundStyle(copper)
                    .frame(width: 24)
                VStack(alignment: .leading, spacing: 3) {
                    Text(item.displayTitle).font(.system(size: 14, weight: .semibold)).foregroundStyle(ink).lineLimit(2)
                    let subtitle = item.displaySubtitle
                    if !subtitle.isEmpty {
                        Text(subtitle).font(.system(size: 11)).foregroundStyle(ink.opacity(0.58)).lineLimit(2)
                    }
                }
                Spacer(minLength: 0)
            }
            if item["can_download"].bool == true || item["can_open"].bool == true {
                HStack(spacing: 14) {
                    if item["can_download"].bool == true {
                        Button(downloading == item["id"].text ? "正在下载…" : "下载并预览") { download(item) }
                            .disabled(downloading != nil)
                    }
                    if item["can_open"].bool == true {
                        Button("打开原资料") { open(item) }
                    }
                    Spacer()
                }
                .font(.system(size: 11.5, weight: .semibold))
                .foregroundStyle(copper)
                .padding(.leading, 35)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
    }

    private var navigationRows: some View {
        VStack(spacing: 0) {
            NavigationLink { KnowledgeGraphView(courseID: courseID) } label: {
                row(icon: "point.3.connected.trianglepath.dotted", title: "课程知识点", subtitle: "查看同步的知识结构与标签")
            }
            Rectangle().fill(line.opacity(0.55)).frame(height: 1).padding(.leading, 46)
            NavigationLink { ClassicClassroomView(scope: .course(courseID)) } label: {
                row(icon: "play.rectangle", title: "互动课堂", subtitle: "围绕这门课生成课堂")
            }
            if let classes = detail.value["classes"].array, !classes.isEmpty {
                Rectangle().fill(line.opacity(0.55)).frame(height: 1).padding(.leading, 46)
                NavigationLink { ClassDetailView(classID: classes[0]["id"].text, name: classes[0]["name"].text) } label: {
                    row(icon: "person.2", title: "班级与成员", subtitle: "\(classes.count) 个班级")
                }
            }
            Rectangle().fill(line.opacity(0.55)).frame(height: 1).padding(.leading, 46)
            NavigationLink { FocusSetupView(initialGoal: displayName) } label: {
                row(icon: "timer", title: "围绕这门课专注", subtitle: "把课程带到自习室")
            }
        }
        .background(Color(hex: 0xFFFBF2), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(line.opacity(0.7), lineWidth: 1))
    }

    private func row(icon: String, title: String, subtitle: String) -> some View {
        HStack(spacing: 12) {
            Image(systemName: icon).font(.system(size: 17)).foregroundStyle(copper).frame(width: 24)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.system(size: 14, weight: .semibold)).foregroundStyle(ink)
                Text(subtitle).font(.system(size: 11)).foregroundStyle(ink.opacity(0.55))
            }
            Spacer()
            Image(systemName: "chevron.right").font(.system(size: 12, weight: .semibold)).foregroundStyle(ink.opacity(0.35))
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 13)
        .contentShape(Rectangle())
    }

    private var syncRow: some View {
        Button {
            guard !syncing else { return }
            syncing = true
            Task {
                defer { syncing = false }
                do { _ = try await LearningService(client: app.client).syncCourse(id: courseID); await load() }
                catch { self.error = error.localizedDescription }
            }
        } label: {
            HStack(spacing: 8) {
                if syncing { ProgressView().controlSize(.small).tint(ink) }
                else { Image(systemName: "arrow.triangle.2.circlepath").font(.system(size: 14, weight: .semibold)) }
                Text(syncing ? "正在同步课程内容…" : "同步课程内容").font(.system(size: 14, weight: .bold))
            }
            .foregroundStyle(ink)
            .frame(maxWidth: .infinity)
            .frame(height: 46)
            .background(Color(hex: 0xF0E2CA), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(Color(hex: 0xBD9B72), lineWidth: 1))
        }
        .buttonStyle(CampusPressStyle())
        .disabled(syncing)
    }

    private var contentPath: String { "courses/\(courseID.pathComponent)/content" }

    private func load() async {
        await detail.load(client: app.client, path: "courses/\(courseID.pathComponent)")
        await content.load(client: app.client, path: contentPath)
        if let canonical = detail.value["course"]["id"].string, canonical != courseID {
            await content.load(client: app.client, path: "courses/\(canonical.pathComponent)/content")
        }
    }

    private func icon(for kind: String) -> String {
        switch kind {
        case "chapter": "folder"
        case "assignment": "square.and.pencil"
        case "notice": "megaphone"
        case "exam": "calendar.badge.clock"
        case "video": "play.rectangle"
        case "discussion": "bubble.left.and.bubble.right"
        default: "doc.text"
        }
    }

    private func download(_ item: JSONValue) {
        let id = item["id"].text
        downloading = id
        Task {
            defer { downloading = nil }
            do {
                let result = try await app.client.download(path: "courses/\(courseID.pathComponent)/resources/\(id.pathComponent)/download")
                let directory = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString, isDirectory: true)
                try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
                let destination = directory.appendingPathComponent(result.filename)
                try FileManager.default.moveItem(at: result.url, to: destination)
                preview = destination
            } catch is CancellationError { }
            catch { self.error = error.localizedDescription }
        }
    }

    private func open(_ item: JSONValue) {
        Task {
            do {
                let result = try await app.client.request(path: "courses/\(courseID.pathComponent)/resources/\(item["id"].text.pathComponent)/open")
                guard let url = URL(string: result["url"].text), ["https", "http"].contains(url.scheme), url.user == nil, url.password == nil else {
                    throw APIError(code: "INVALID_URL", message: "资料未返回有效的访问地址。")
                }
                openURL(url)
            } catch { self.error = error.localizedDescription }
        }
    }
}

// MARK: - Knowledge

struct KnowledgeGraphView: View {
    @Environment(AppModel.self) private var app
    let courseID: String
    @State private var resource = RemoteResource()
    @State private var search = ""

    private var points: [JSONValue] {
        resource.value["points"].items.filter { search.isEmpty || $0["name"].text.localizedCaseInsensitiveContains(search) }
    }

    var body: some View {
        CampusSecondaryScaffold(title: "课程知识点") {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    CampusTextField(placeholder: "搜索知识点", text: $search, systemImage: "magnifyingglass")
                    if resource.isLoading && resource.value == .null {
                        CampusLoadingState()
                    } else if let error = resource.error {
                        CampusErrorState(message: error) { Task { await load() } }
                    } else if points.isEmpty {
                        CampusEmptyState(title: "尚未同步知识点", message: "返回课程详情同步学习通课程后再试。", systemImage: "point.3.connected.trianglepath.dotted")
                    } else {
                        ForEach(Array(points.enumerated()), id: \.offset) { _, point in
                            CampusCard {
                                VStack(alignment: .leading, spacing: 6) {
                                    Text(point["name"].text).campusFont(.subtitle).foregroundStyle(CampusJournal.ink)
                                    let tags = point["tags"].items.compactMap(\.string)
                                    if !tags.isEmpty {
                                        Text(tags.joined(separator: " · ")).campusFont(.caption).foregroundStyle(.secondary)
                                    }
                                    if let summary = point["summary"].string?.nonEmpty {
                                        Text(summary).campusFont(.caption).foregroundStyle(.secondary).lineLimit(3)
                                    }
                                }
                            }
                        }
                    }
                }
                .padding(20)
                .frame(maxWidth: 760)
                .frame(maxWidth: .infinity)
            }
        }
        .task { await load() }
    }

    private func load() async {
        await resource.load(client: app.client, path: "courses/\(courseID.pathComponent)/knowledge-graph")
    }
}

// MARK: - Class

struct ClassDetailView: View {
    let classID: String
    var name: String = "班级"

    var body: some View {
        CampusSecondaryScaffold(title: name.isEmpty ? "班级" : name) {
            ScrollView {
                VStack(spacing: 12) {
                    NavigationLink { SimpleRemoteList(title: "课程公告", path: "classes/\(classID.pathComponent)/announcements", icon: "megaphone") } label: {
                        classRow("课程公告", icon: "megaphone")
                    }
                    NavigationLink { SimpleRemoteList(title: "课程作业", path: "classes/\(classID.pathComponent)/assignments", icon: "doc.text") } label: {
                        classRow("课程作业", icon: "doc.text")
                    }
                    NavigationLink { SimpleRemoteList(title: "班级成员", path: "classes/\(classID.pathComponent)/members", icon: "person.2") } label: {
                        classRow("班级成员", icon: "person.2")
                    }
                }
                .padding(20)
                .frame(maxWidth: 760)
                .frame(maxWidth: .infinity)
            }
        }
    }

    private func classRow(_ title: String, icon: String) -> some View {
        HStack(spacing: 12) {
            Image(systemName: icon).foregroundStyle(CampusJournal.ink).frame(width: 24)
            Text(title).campusFont(.subtitle).foregroundStyle(CampusJournal.ink)
            Spacer()
            Image(systemName: "chevron.right").font(.system(size: 12, weight: .semibold)).foregroundStyle(.secondary)
        }
        .padding(16)
        .background(Color(hex: 0xFFFBF2), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(CampusJournal.paper, lineWidth: 1))
    }
}

/// Course content list kept for callers that need the plain paged view.
struct CourseContentView: View {
    @Environment(AppModel.self) private var app
    let courseID: String
    @State private var resource = PagedResource()

    var body: some View {
        CampusSecondaryScaffold(title: "章节与资料") {
            ScrollView {
                VStack(spacing: 10) {
                    if resource.isLoading && resource.items.isEmpty { CampusLoadingState() }
                    else if let error = resource.error, resource.items.isEmpty { CampusErrorState(message: error) { Task { await load() } } }
                    else if resource.items.isEmpty {
                        CampusEmptyState(title: "还没有课程资料", message: "可返回课程详情同步最新内容。", systemImage: "folder")
                    } else {
                        ForEach(Array(resource.items.enumerated()), id: \.offset) { _, item in
                            CampusCard {
                                VStack(alignment: .leading, spacing: 8) {
                                    Text(item.displayTitle).campusFont(.subtitle).foregroundStyle(CampusJournal.ink)
                                    let subtitle = item.displaySubtitle
                                    if !subtitle.isEmpty { Text(subtitle).campusFont(.caption).foregroundStyle(.secondary).lineLimit(2) }
                                }
                            }
                        }
                    }
                }
                .padding(20)
                .frame(maxWidth: 760)
                .frame(maxWidth: .infinity)
            }
        }
        .task { await load() }
    }

    private func load() async {
        await resource.load(client: app.client, path: "courses/\(courseID.pathComponent)/content")
    }
}
