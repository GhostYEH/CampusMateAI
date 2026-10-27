import SwiftUI
import CampusCore

struct TasksView: View {
    @Environment(AppModel.self) private var app
    @State private var resource = PagedResource()
    @State private var status = "pending"
    @State private var search = ""
    @State private var showEditor = false
    @State private var showImport = false
    @State private var showCalendar = false
    @State private var error: String?
    @State private var sort = "deadline"
    private var query: [String: String] { status.isEmpty ? [:] : ["status": status] }
    private var tasks: [TaskItem] {
        resource.items.compactMap { try? TaskItem(json: $0) }.filter { search.isEmpty || $0.title.localizedCaseInsensitiveContains(search) || $0.description.localizedCaseInsensitiveContains(search) }
            .sorted {
                if sort == "priority" {
                    let ranks = ["urgent": 0, "high": 1, "important": 2, "normal": 3, "medium": 3, "low": 4]
                    let left = ranks[$0.json["importance"].string ?? $0.priority] ?? 3
                    let right = ranks[$1.json["importance"].string ?? $1.priority] ?? 3
                    if left != right { return left < right }
                }
                return ($0.deadline ?? .distantFuture, $0.id) < ($1.deadline ?? .distantFuture, $1.id)
            }
    }

    var body: some View {
        List {
            Section {
                Picker("状态", selection: $status) {
                    Text("待完成").tag("pending"); Text("已完成").tag("completed"); Text("全部").tag("")
                }.pickerStyle(.segmented)
            }.listRowBackground(Color.clear)
            PagedStatusView(resource: resource, emptyTitle: "没有待办", emptyMessage: "新建一项待办，或从通知和学习计划中导入。", icon: "checkmark.circle", retry: load)
            ForEach(tasks) { item in
                NavigationLink { TaskDetailView(initial: item) } label: {
                    HStack(alignment: .top, spacing: 12) {
                        Image(systemName: item.isCompleted ? "checkmark.circle.fill" : item.isEditable ? "circle" : "arrow.triangle.2.circlepath")
                            .foregroundStyle(item.isCompleted ? Color.accentColor : .secondary).padding(.top, 3)
                        VStack(alignment: .leading, spacing: 6) {
                            Text(item.title).strikethrough(item.isCompleted).font(.body.weight(.medium))
                            HStack {
                                Text(item.sourceLabel)
                                if let deadline = item.deadline { Text(deadline, format: .dateTime.month().day().hour().minute()) }
                            }.font(.caption).foregroundStyle(.secondary)
                        }
                    }.padding(.vertical, 4)
                }
                .swipeActions(edge: .leading) {
                    if item.canChangeCompletion {
                        Button(item.isCompleted ? "恢复" : "完成", systemImage: item.isCompleted ? "arrow.uturn.backward" : "checkmark") {
                            Task {
                                do { _ = try await LearningService(client: app.client).setCompleted(item, completed: !item.isCompleted); await load() }
                                catch { self.error = error.localizedDescription }
                            }
                        }.tint(.green)
                    }
                }
            }
            LoadMoreRow(resource: resource) { await resource.load(client: app.client, path: "tasks", query: query, reset: false) }
        }
        .navigationTitle("待办")
        .searchable(text: $search, prompt: "搜索待办")
        .task(id: status) { await load() }
        .task(id: search) {
            guard !search.isEmpty else { return }
            try? await Task.sleep(for: .milliseconds(250))
            guard !Task.isCancelled else { return }
            await resource.loadRemaining(client: app.client, path: "tasks", query: query)
        }
        .refreshable { await load() }
        .toolbar {
            ToolbarItem(placement: .topBarLeading) {
                Menu {
                    Picker("排序", selection: $sort) { Text("截止时间").tag("deadline"); Text("重要程度").tag("priority") }
                    Button("日历", systemImage: "calendar") { showCalendar = true }
                    Button("评定重要程度", systemImage: "sparkles") {
                        Task {
                            do { _ = try await app.client.request(.post, path: "tasks/rank-importance", body: ["task_ids": []]); await load() }
                            catch { self.error = error.localizedDescription }
                        }
                    }
                } label: { Image(systemName: "line.3.horizontal.decrease") }.accessibilityLabel("筛选和排序")
            }
            ToolbarItem(placement: .topBarTrailing) {
                Menu {
                    Button("新建待办", systemImage: "plus") { showEditor = true }
                    Button("从文本导入", systemImage: "doc.text.viewfinder") { showImport = true }
                } label: { Image(systemName: "plus") }.accessibilityIdentifier("tasks.add").accessibilityLabel("添加待办")
            }
        }
        .sheet(isPresented: $showEditor, onDismiss: { Task { await load() } }) { NavigationStack { TaskEditorView() } }
        .sheet(isPresented: $showImport, onDismiss: { Task { await load() } }) { NavigationStack { TaskImportView() } }
        .sheet(isPresented: $showCalendar) { NavigationStack { TaskCalendarView() } }
        .errorAlert($error)
    }
    private func load() async { await resource.load(client: app.client, path: "tasks", query: query) }
}

struct TaskEditorView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    var existing: TaskItem?
    @State private var title = ""
    @State private var description = ""
    @State private var hasDeadline = false
    @State private var deadline = Date.now.addingTimeInterval(86400)
    @State private var priority = "medium"
    @State private var sourceName = ""
    @State private var location = ""
    @State private var submissionMethod = ""
    @State private var saving = false
    @State private var error: String?

    var body: some View {
        Form {
            Section("待办内容") {
                TextField("标题", text: $title, axis: .vertical).lineLimit(1...3).accessibilityIdentifier("tasks.title")
                TextField("说明", text: $description, axis: .vertical).lineLimit(3...8)
            }
            Section("安排") {
                Toggle("设置截止时间", isOn: $hasDeadline)
                if hasDeadline { DatePicker("截止时间", selection: $deadline) }
                Picker("优先级", selection: $priority) { Text("低").tag("low"); Text("中").tag("medium"); Text("高").tag("high") }
            }
            Section("补充信息") {
                TextField("来源名称", text: $sourceName)
                TextField("地点", text: $location)
                TextField("提交方式", text: $submissionMethod)
            }
        }
        .navigationTitle(existing == nil ? "新建待办" : "编辑待办").navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .cancellationAction) { Button("取消") { dismiss() } }
            ToolbarItem(placement: .confirmationAction) { Button(saving ? "保存中…" : "保存", action: save).disabled(saving || title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty).accessibilityIdentifier("tasks.save") }
        }
        .onAppear {
            if let item = existing {
                title = item.title; description = item.description; hasDeadline = item.deadline != nil
                deadline = item.deadline ?? .now; priority = item.priority; sourceName = item.json["source_name"].text
                location = item.json["location"].text; submissionMethod = item.json["submission_method"].text
            }
        }
        .errorAlert($error)
    }

    private func save() {
        saving = true
        Task {
            defer { saving = false }
            do {
                var draft = TaskDraft(title: title, description: description, deadline: hasDeadline ? deadline : nil, priority: priority, sourceName: sourceName, location: location, submissionMethod: submissionMethod)
                draft.materials = existing?.json["materials"].items.compactMap(\.string) ?? []
                _ = try await LearningService(client: app.client).saveTask(draft, existing: existing)
                dismiss()
            } catch { self.error = error.localizedDescription }
        }
    }
}

struct TaskDetailView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var item: TaskItem
    @State private var showEditor = false
    @State private var confirmingDelete = false
    @State private var working = false
    @State private var error: String?
    init(initial: TaskItem) { _item = State(initialValue: initial) }

    var body: some View {
        List {
            Section {
                Text(item.title).font(.title2.bold()).textSelection(.enabled)
                if !item.description.isEmpty { Text(item.description).textSelection(.enabled) }
            }
            Section("安排") {
                LabeledContent("状态", value: item.status.localizedStatus)
                LabeledContent("来源", value: item.sourceLabel)
                if let due = item.deadline { LabeledContent("截止时间") { Text(due, format: .dateTime.year().month().day().hour().minute()) } }
                if let text = item.json["location"].string?.nonEmpty { LabeledContent("地点", value: text) }
                if let text = item.json["submission_method"].string?.nonEmpty { LabeledContent("提交方式", value: text) }
                if let courseID = item.courseID { NavigationLink("查看课程") { CourseDetailView(courseID: courseID) } }
            }
            if !item.canChangeCompletion {
                Section { Label("此任务由来源系统同步，请在原系统办理，再同步最新状态。", systemImage: "arrow.triangle.2.circlepath").font(.footnote).foregroundStyle(.secondary) }
            } else {
                Section {
                    Button(item.isCompleted ? "恢复为待完成" : "标记为已完成", systemImage: item.isCompleted ? "arrow.uturn.backward" : "checkmark.circle") {
                        mutate { item = try await LearningService(client: app.client).setCompleted(item, completed: !item.isCompleted) }
                    }.disabled(working)
                    Button("编辑待办", systemImage: "pencil") { showEditor = true }.disabled(working)
                    Button("删除待办", role: .destructive) { confirmingDelete = true }.disabled(working)
                }
            }
        }
        .navigationTitle("待办详情").navigationBarTitleDisplayMode(.inline)
        .task { await reload() }
        .sheet(isPresented: $showEditor, onDismiss: { Task { await reload() } }) { NavigationStack { TaskEditorView(existing: item) } }
        .confirmationDialog("删除这项待办？", isPresented: $confirmingDelete, titleVisibility: .visible) {
            Button("删除", role: .destructive) { mutate { try await LearningService(client: app.client).deleteTask(item); dismiss() } }
        }
        .errorAlert($error)
    }
    private func reload() async {
        do { item = try await LearningService(client: app.client).task(id: item.id) }
        catch is CancellationError { }
        catch { self.error = error.localizedDescription }
    }
    private func mutate(_ action: @escaping @MainActor () async throws -> Void) {
        working = true
        Task { defer { working = false }; do { try await action() } catch { self.error = error.localizedDescription } }
    }
}

struct TaskImportView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    var noticeMode = false
    @State private var content = ""
    @State private var sourceName = "手动导入"
    @State private var review: ImportReview?
    @State private var working = false
    @State private var error: String?

    var body: some View {
        Form {
            if review == nil {
                Section("原文") { TextEditor(text: $content).frame(minHeight: 180).accessibilityLabel("导入文本") }
                Section { TextField("来源名称", text: $sourceName) }
                Section {
                    Button(working ? "正在分析…" : "分析并预览") { analyze() }.disabled(working || content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                } footer: { Text("先检查提取结果，再确认需要加入待办的条目。") }
            } else if let current = review {
                if current.drafts.isEmpty { ContentUnavailableView("没有可提取的待办", systemImage: "doc.text.magnifyingglass", description: Text("可以返回修改原文后重试。")) }
                ForEach(current.drafts.indices, id: \.self) { index in
                    Section("待办 \(index + 1)") {
                        Toggle("加入待办", isOn: Binding(get: { review?.drafts[index]["selected"].bool ?? false }, set: { review?.setSelected($0, at: index) }))
                        TextField("标题", text: Binding(get: { review?.drafts[index]["title"].text ?? "" }, set: { review?.setTitle($0, at: index) }), axis: .vertical)
                        TextField("说明", text: Binding(get: { review?.drafts[index]["description"].text ?? "" }, set: { review?.set(.string($0), key: "description", at: index) }), axis: .vertical)
                        if let deadline = current.drafts[index]["deadline"].string?.nonEmpty { LabeledContent("截止时间", value: deadline) }
                        ForEach(current.drafts[index]["warnings"].items, id: \.self) { warning in Text(warning.text).font(.footnote).foregroundStyle(.orange) }
                        if current.drafts[index]["existing_task_id"].string?.nonEmpty != nil { Text("已存在相同待办，保存时保留已有进度。").font(.footnote).foregroundStyle(.secondary) }
                    }
                }
                Section {
                    Button(working ? "正在保存…" : "确认加入 \(current.selectedDrafts.count) 项待办") { commit() }
                        .disabled(working || current.selectedDrafts.isEmpty || current.hasInvalidSelection)
                    Button("重新分析") { review = nil }.disabled(working)
                }
            }
        }
        .navigationTitle(noticeMode ? "提取通知待办" : "导入待办").navigationBarTitleDisplayMode(.inline)
        .toolbar { ToolbarItem(placement: .cancellationAction) { Button("关闭") { dismiss() } } }
        .errorAlert($error)
    }
    private func analyze() {
        working = true
        Task {
            defer { working = false }
            do {
                let service = LearningService(client: app.client)
                let result = try await (noticeMode ? service.extractNotice(content: content, sourceName: sourceName) : service.analyzeImport(content: content, sourceName: sourceName))
                review = ImportReview(json: result)
            } catch { self.error = error.localizedDescription }
        }
    }
    private func commit() {
        guard let review, !review.hasInvalidSelection, !review.selectedDrafts.isEmpty else { return }
        working = true
        Task {
            defer { working = false }
            do { _ = try await LearningService(client: app.client).commitImport(review.selectedDrafts); dismiss() }
            catch { self.error = error.localizedDescription }
        }
    }
}

struct TaskCalendarView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var date = Date.now
    @State private var resource = PagedResource()
    private var query: [String: String] {
        let start = Calendar.current.startOfDay(for: date)
        return ["deadline_after": APIDate.string(start), "deadline_before": APIDate.string(Calendar.current.date(byAdding: .day, value: 1, to: start) ?? start)]
    }
    var body: some View {
        List {
            DatePicker("查看日期", selection: $date, displayedComponents: .date).datePickerStyle(.graphical)
            Section("当天截止") {
                PagedStatusView(resource: resource, emptyTitle: "当天没有截止事项", icon: "calendar", retry: load)
                ForEach(Array(resource.items.enumerated()), id: \.offset) { _, value in
                    if let item = try? TaskItem(json: value) { NavigationLink { TaskDetailView(initial: item) } label: { RecordRow(value: value, icon: "checklist") } }
                }
                LoadMoreRow(resource: resource) { await resource.load(client: app.client, path: "tasks", query: query, reset: false) }
            }
        }.navigationTitle("待办日历").task(id: Calendar.current.startOfDay(for: date)) { await load() }
            .toolbar { ToolbarItem(placement: .cancellationAction) { Button("关闭") { dismiss() } } }
    }
    private func load() async { await resource.load(client: app.client, path: "tasks", query: query) }
}
