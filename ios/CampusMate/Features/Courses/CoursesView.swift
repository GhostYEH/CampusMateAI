import SwiftUI
import QuickLook
import CampusCore

struct CoursesView: View {
    @Environment(AppModel.self) private var app
    @State private var resource = PagedResource()
    @State private var search = ""
    private var query: [String: String] { search.isEmpty ? [:] : ["query": search] }

    var body: some View {
        List {
            Section {
                NavigationLink { ChaoxingView() } label: { Label("学习通连接与同步", systemImage: "arrow.triangle.2.circlepath") }
                NavigationLink { SimpleRemoteList(title: "共同课堂", path: "magicclass/learning-space/rooms", icon: "person.2") } label: { Label("同学一起学", systemImage: "person.2") }
            }
            Section("我的课程") {
                PagedStatusView(resource: resource, emptyTitle: "还没有课程", emptyMessage: "连接学习通并同步课程，或查看你已加入的课程。", icon: "books.vertical", retry: load)
                ForEach(Array(resource.items.enumerated()), id: \.offset) { _, course in
                    NavigationLink { CourseDetailView(courseID: course["id"].text) } label: {
                        VStack(alignment: .leading, spacing: 7) {
                            Text(course["name"].text).font(.headline)
                            Text([course["teacher_name"].text, course["semester"].text].filter { !$0.isEmpty }.joined(separator: " · ")).font(.subheadline).foregroundStyle(.secondary)
                            if course["provider"].text == "chaoxing" { Label("学习通", systemImage: "arrow.triangle.2.circlepath").font(.caption).foregroundStyle(.secondary) }
                        }.padding(.vertical, 6)
                    }
                }
                LoadMoreRow(resource: resource) { await resource.load(client: app.client, path: "courses", query: query, reset: false) }
            }
        }
        .navigationTitle("课程").searchable(text: $search, prompt: "搜索课程")
        .task(id: search) {
            if !search.isEmpty { try? await Task.sleep(for: .milliseconds(250)) }
            guard !Task.isCancelled else { return }
            await load()
        }.refreshable { await load() }
    }
    private func load() async { await resource.load(client: app.client, path: "courses", query: query) }
}

struct CourseDetailView: View {
    @Environment(AppModel.self) private var app
    let courseID: String
    @State private var resource = RemoteResource()
    @State private var syncing = false
    @State private var error: String?
    private var course: JSONValue { resource.value["course"].object == nil ? resource.value : resource.value["course"] }

    var body: some View {
        List {
            ResourceStateView(resource: resource, isEmpty: resource.value == .null, retry: load)
            if resource.value != .null {
                Section {
                    Text(course["name"].text).font(.title2.bold())
                    if let text = course["description"].string?.nonEmpty { Text(text).foregroundStyle(.secondary) }
                    if let name = course["teacher_name"].string?.nonEmpty { LabeledContent("教师", value: name) }
                    if let semester = course["semester"].string?.nonEmpty { LabeledContent("学期", value: semester) }
                }
                Section("学习内容") {
                    NavigationLink { CourseContentView(courseID: courseID) } label: { Label("章节与资料", systemImage: "doc.on.doc") }
                    NavigationLink { KnowledgeGraphView(courseID: courseID) } label: { Label("知识点", systemImage: "point.3.connected.trianglepath.dotted") }
                    NavigationLink { SimpleRemoteList(title: "课程课堂", path: "courses/\(courseID.pathComponent)/interactive-classroom", icon: "play.rectangle") } label: { Label("互动课堂", systemImage: "play.rectangle") }
                }
                if let classes = resource.value["classes"].array, !classes.isEmpty {
                    Section("班级") {
                        ForEach(Array(classes.enumerated()), id: \.offset) { _, item in
                            NavigationLink(item["name"].text) { ClassDetailView(classID: item["id"].text) }
                        }
                    }
                }
                if course["provider"].text == "chaoxing" {
                    Section {
                        Button(syncing ? "正在同步…" : "同步课程内容", systemImage: "arrow.triangle.2.circlepath") {
                            syncing = true
                            Task { defer { syncing = false }; do { _ = try await LearningService(client: app.client).syncCourse(id: courseID); await load() } catch { self.error = error.localizedDescription } }
                        }.disabled(syncing)
                    }
                }
            }
        }.navigationTitle("课程详情").navigationBarTitleDisplayMode(.inline).task { await load() }.refreshable { await load() }.errorAlert($error)
    }
    private func load() async { await resource.load(client: app.client, path: "courses/\(courseID.pathComponent)") }
}

struct CourseContentView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.openURL) private var openURL
    let courseID: String
    @State private var resource = PagedResource()
    @State private var preview: URL?
    @State private var downloading: String?
    @State private var error: String?

    var body: some View {
        List {
            PagedStatusView(resource: resource, emptyTitle: "还没有课程资料", emptyMessage: "可返回课程详情同步最新内容。", icon: "folder", retry: load)
            ForEach(Array(resource.items.enumerated()), id: \.offset) { _, item in
                VStack(alignment: .leading, spacing: 9) {
                    RecordRow(value: item, icon: item["kind"].text == "chapter" ? "folder" : "doc.text")
                    if let text = item["description"].string?.nonEmpty { Text(text).font(.subheadline).foregroundStyle(.secondary).textSelection(.enabled) }
                    HStack {
                        if item["can_download"].bool == true {
                            Button(downloading == item["id"].text ? "正在下载…" : "下载并预览", systemImage: "arrow.down.doc") { download(item) }.disabled(downloading != nil)
                        }
                        if item["can_open"].bool == true {
                            Button("打开原资料", systemImage: "arrow.up.right.square") { open(item) }
                        }
                    }.font(.subheadline).buttonStyle(.borderless)
                }.padding(.vertical, 4)
            }
            LoadMoreRow(resource: resource) { await resource.load(client: app.client, path: endpoint, reset: false) }
        }
        .navigationTitle("章节与资料").navigationBarTitleDisplayMode(.inline)
        .task { await load() }.refreshable { await load() }
        .quickLookPreview($preview).errorAlert($error)
    }
    private var endpoint: String { "courses/\(courseID.pathComponent)/content" }
    private func load() async { await resource.load(client: app.client, path: endpoint) }
    private func download(_ item: JSONValue) {
        let id = item["id"].text; downloading = id
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
                guard let url = URL(string: result["url"].text), ["https", "http"].contains(url.scheme), url.user == nil, url.password == nil else { throw APIError(code: "INVALID_URL", message: "资料未返回有效的访问地址。") }
                openURL(url)
            } catch { self.error = error.localizedDescription }
        }
    }
}

struct KnowledgeGraphView: View {
    @Environment(AppModel.self) private var app
    let courseID: String
    @State private var resource = RemoteResource()
    @State private var search = ""
    private var points: [JSONValue] { resource.value["points"].items.filter { search.isEmpty || $0["name"].text.localizedCaseInsensitiveContains(search) } }
    var body: some View {
        List {
            ResourceStateView(resource: resource, isEmpty: resource.value["points"].items.isEmpty, title: "尚未同步知识点", message: "返回课程详情同步学习通课程后再试。", systemImage: "point.3.connected.trianglepath.dotted", retry: load)
            ForEach(Array(points.enumerated()), id: \.offset) { _, point in
                VStack(alignment: .leading, spacing: 7) {
                    Text(point["name"].text).font(.headline)
                    let tags = point["tags"].items.compactMap(\.string)
                    if !tags.isEmpty { Text(tags.joined(separator: " · ")).font(.caption).foregroundStyle(.secondary) }
                }.padding(.vertical, 4)
            }
        }.navigationTitle("课程知识点").searchable(text: $search).task { await load() }.refreshable { await load() }
    }
    private func load() async { await resource.load(client: app.client, path: "courses/\(courseID.pathComponent)/knowledge-graph") }
}

struct ClassDetailView: View {
    @Environment(AppModel.self) private var app
    let classID: String
    var body: some View {
        List {
            NavigationLink { SimpleRemoteList(title: "课程公告", path: "classes/\(classID.pathComponent)/announcements", icon: "megaphone") } label: { Label("课程公告", systemImage: "megaphone") }
            NavigationLink { SimpleRemoteList(title: "课程作业", path: "classes/\(classID.pathComponent)/assignments", icon: "doc.text") } label: { Label("课程作业", systemImage: "doc.text") }
            NavigationLink { SimpleRemoteList(title: "班级成员", path: "classes/\(classID.pathComponent)/members", icon: "person.2") } label: { Label("班级成员", systemImage: "person.2") }
        }.navigationTitle("班级").navigationBarTitleDisplayMode(.inline)
    }
}
