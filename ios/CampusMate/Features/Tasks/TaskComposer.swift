import SwiftUI
import CampusCore

/// Journal-styled composer. Mirrors the Android chooser: write one down, or
/// paste a message and confirm the extracted task cards.
struct TaskComposerSheet: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var mode: Mode?
    @State private var title = ""
    @State private var note = ""
    @State private var hasDeadline = false
    @State private var deadline = Date.now.addingTimeInterval(86400)
    @State private var sourceName = "班群消息"
    @State private var content = ""
    @State private var review: ImportReview?
    @State private var working = false
    @State private var error: String?

    private enum Mode { case manual, extract }

    var body: some View {
        ZStack {
            JournalBackdrop()
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    heading
                    if let review {
                        reviewList(review)
                    } else if let mode {
                        if mode == .manual { manualForm } else { extractForm }
                    } else {
                        chooser
                    }
                }
                .padding(.leading, 28)
                .padding(.trailing, 20)
                .padding(.top, 20)
                .padding(.bottom, 30)
                .frame(maxWidth: 700)
                .frame(maxWidth: .infinity)
            }
            .journalBookPage()
            .padding(12)
        }
        .campusImmersive()
        .errorAlert($error)
    }

    private var heading: some View {
        HStack(alignment: .top) {
            VStack(alignment: .leading, spacing: 2) {
                Text("CAMPUS / TASK JOURNAL")
                    .font(.system(size: 10, weight: .heavy)).tracking(1.4).foregroundStyle(CampusJournal.clay)
                Text(review != nil ? "确认任务卡" : mode == .extract ? "整理一条消息" : mode == .manual ? "写下这件事" : "新建待办")
                    .font(.system(size: 23, weight: .heavy)).foregroundStyle(CampusJournal.ink)
                Text(review != nil ? "核对后再收进待办" : mode == .extract ? "粘贴通知，找出任务与时间" : "给这件事留下一张记录")
                    .font(.system(size: 12)).foregroundStyle(CampusJournal.muted)
            }
            Spacer()
            Button { dismiss() } label: {
                Image(systemName: "xmark").font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(CampusJournal.muted).frame(width: 36, height: 36)
            }
            .accessibilityLabel("关闭")
        }
    }

    private var chooser: some View {
        VStack(spacing: 0) {
            Rectangle().fill(CampusJournal.blue.opacity(0.45)).frame(height: 1)
            chooserRow(icon: "square.and.pencil", title: "手动创建", subtitle: "名称、截止时间、备注", tint: CampusJournal.clay) {
                mode = .manual
            }
            .accessibilityIdentifier("tasks.create.manual")
            Rectangle().fill(CampusJournal.blue.opacity(0.45)).frame(height: 1)
            chooserRow(icon: "doc.on.clipboard", title: "从消息提取", subtitle: "粘贴班群消息，整理成任务卡", tint: CampusJournal.blue) {
                mode = .extract
            }
            .accessibilityIdentifier("tasks.create.extract")
            Rectangle().fill(CampusJournal.blue.opacity(0.45)).frame(height: 1)
        }
    }

    private func chooserRow(icon: String, title: String, subtitle: String, tint: Color, action: @escaping () -> Void) -> some View {
        Button {
            CampusHaptics.tap()
            action()
        } label: {
            HStack(spacing: 12) {
                Image(systemName: icon).font(.system(size: 18)).foregroundStyle(tint)
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).font(.system(size: 15, weight: .bold)).foregroundStyle(CampusJournal.night)
                    Text(subtitle).font(.system(size: 11)).foregroundStyle(CampusJournal.muted)
                }
                Spacer()
                Image(systemName: "chevron.right").font(.system(size: 12, weight: .semibold)).foregroundStyle(CampusJournal.muted)
            }
            .padding(.vertical, 18)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    private var manualForm: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("01  我要做什么").font(.system(size: 12, weight: .bold)).foregroundStyle(CampusJournal.ink)
            journalField("任务名称", text: $title, identifier: "tasks.title")
            journalField("备注、材料与地点", text: $note, axis: .vertical)
            Text("02  什么时候完成").font(.system(size: 12, weight: .bold)).foregroundStyle(CampusJournal.ink)
            Toggle(isOn: $hasDeadline.animation(.easeOut(duration: 0.2))) {
                Text("设置截止时间").font(.system(size: 14)).foregroundStyle(CampusJournal.night)
            }
            .tint(CampusJournal.clay)
            if hasDeadline {
                DatePicker("截止时间", selection: $deadline, displayedComponents: [.date, .hourAndMinute])
                    .datePickerStyle(.compact)
                    .font(.system(size: 14))
                    .tint(CampusJournal.clay)
            }
            Button {
                save()
            } label: {
                HStack(spacing: 8) {
                    if working { ProgressView().controlSize(.small).tint(.white) }
                    Text(working ? "正在保存…" : "收进待办").font(.system(size: 15, weight: .bold))
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .frame(height: 48)
                .background(CampusJournal.clay, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            }
            .buttonStyle(CampusPressStyle())
            .disabled(working || title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
            .accessibilityIdentifier("tasks.save")
        }
    }

    private var extractForm: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("消息原文").font(.system(size: 12, weight: .bold)).foregroundStyle(CampusJournal.ink)
            journalField("消息来源（选填）", text: $sourceName)
            TextEditor(text: $content)
                .font(.system(size: 13))
                .foregroundStyle(CampusJournal.ink)
                .scrollContentBackground(.hidden)
                .frame(minHeight: 180)
                .padding(8)
                .background(Color.white.opacity(0.42), in: RoundedRectangle(cornerRadius: 5, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 5, style: .continuous).strokeBorder(CampusJournal.blue.opacity(0.6), lineWidth: 1))
                .accessibilityLabel("粘贴整条消息")
            Text("原文仅用于这次任务提取，并保留在任务记录中供你核对。")
                .font(.system(size: 11)).foregroundStyle(CampusJournal.muted)
            Button { analyze() } label: {
                HStack(spacing: 8) {
                    if working { ProgressView().controlSize(.small).tint(.white) }
                    Text(working ? "正在分析…" : "分析并预览").font(.system(size: 15, weight: .bold))
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .frame(height: 48)
                .background(CampusJournal.blue, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            }
            .buttonStyle(CampusPressStyle())
            .disabled(working || content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
        }
    }

    private func reviewList(_ review: ImportReview) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            if review.drafts.isEmpty {
                CampusEmptyState(title: "没有可提取的待办", message: "可以返回修改原文后重试。", systemImage: "doc.text.magnifyingglass")
            }
            ForEach(review.drafts.indices, id: \.self) { index in
                VStack(alignment: .leading, spacing: 8) {
                    HStack {
                        Toggle(isOn: Binding(get: { review.drafts[index]["selected"].bool ?? false },
                                            set: { value in withAnimation { self.review?.setSelected(value, at: index) } })) {
                            Text("待办 \(index + 1)").font(.system(size: 13, weight: .bold)).foregroundStyle(CampusJournal.night)
                        }
                        .tint(CampusJournal.clay)
                    }
                    TextField("标题", text: Binding(get: { self.review?.drafts[index]["title"].text ?? "" },
                                                  set: { self.review?.setTitle($0, at: index) }), axis: .vertical)
                        .font(.system(size: 14))
                        .foregroundStyle(CampusJournal.ink)
                    if let deadline = review.drafts[index]["deadline"].string?.nonEmpty {
                        Text("截止 \(deadline)").font(.system(size: 11)).foregroundStyle(CampusJournal.muted)
                    }
                    ForEach(review.drafts[index]["warnings"].items, id: \.self) { warning in
                        Text(warning.text).font(.system(size: 11)).foregroundStyle(CampusJournal.amber)
                    }
                    if review.drafts[index]["existing_task_id"].string?.nonEmpty != nil {
                        Text("已存在相同待办，保存时保留已有进度。").font(.system(size: 11)).foregroundStyle(CampusJournal.muted)
                    }
                }
                .padding(14)
                .background(Color(hex: 0xFFFBF2), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 12, style: .continuous).strokeBorder(Color(hex: 0xCFBDA4, opacity: 0.5), lineWidth: 1))
            }
            Button { commit(review) } label: {
                HStack(spacing: 8) {
                    if working { ProgressView().controlSize(.small).tint(.white) }
                    Text(working ? "正在保存…" : "确认加入 \(review.selectedDrafts.count) 项待办")
                        .font(.system(size: 15, weight: .bold))
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .frame(height: 48)
                .background(CampusJournal.clay, in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            }
            .buttonStyle(CampusPressStyle())
            .disabled(working || review.selectedDrafts.isEmpty || review.hasInvalidSelection)
            Button("重新分析") { self.review = nil }.font(.system(size: 13)).foregroundStyle(CampusJournal.blue)
        }
    }

    private func journalField(_ placeholder: String, text: Binding<String>, axis: Axis = .horizontal, identifier: String? = nil) -> some View {
        TextField(placeholder, text: text, axis: axis)
            .font(.system(size: 14))
            .foregroundStyle(CampusJournal.ink)
            .lineLimit(axis == .vertical ? 2...5 : 1...1)
            .padding(.horizontal, 11)
            .padding(.vertical, 12)
            .background(Color.white.opacity(0.42), in: RoundedRectangle(cornerRadius: 5, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 5, style: .continuous).strokeBorder(CampusJournal.blue.opacity(0.6), lineWidth: 1))
            .accessibilityIdentifier(identifier ?? "")
    }

    private func save() {
        working = true
        Task {
            defer { working = false }
            do {
                let draft = TaskDraft(title: title, description: note, deadline: hasDeadline ? deadline : nil,
                                      priority: "medium", sourceName: "个人待办", materials: [], location: "", submissionMethod: "")
                _ = try await LearningService(client: app.client).saveTask(draft)
                CampusHaptics.success()
                dismiss()
            } catch { self.error = error.localizedDescription }
        }
    }

    private func analyze() {
        working = true
        Task {
            defer { working = false }
            do {
                let result = try await LearningService(client: app.client).analyzeImport(content: content, sourceName: sourceName)
                review = ImportReview(json: result)
            } catch { self.error = error.localizedDescription }
        }
    }

    private func commit(_ review: ImportReview) {
        guard !review.hasInvalidSelection, !review.selectedDrafts.isEmpty else { return }
        working = true
        Task {
            defer { working = false }
            do {
                _ = try await LearningService(client: app.client).commitImport(review.selectedDrafts)
                CampusHaptics.success()
                dismiss()
            } catch { self.error = error.localizedDescription }
        }
    }
}

/// Journal detail page for one task.
struct TaskDetailView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var item: TaskItem
    @State private var showEditor = false
    @State private var confirmingDelete = false
    @State private var working = false
    @State private var error: String?
    @State private var shareText: String?

    init(initial: TaskItem) { _item = State(initialValue: initial) }

    var body: some View {
        ZStack {
            JournalBackdrop()
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    Text("CAMPUS / TASK JOURNAL")
                        .font(.system(size: 10, weight: .heavy)).tracking(1.4).foregroundStyle(CampusJournal.clay)
                    Text(item.title)
                        .font(.system(size: 26, weight: .heavy)).foregroundStyle(CampusJournal.ink)
                        .textSelection(.enabled)
                    if !item.description.isEmpty {
                        Text(item.description).font(.system(size: 14)).foregroundStyle(CampusJournal.muted).textSelection(.enabled)
                    }
                    Rectangle().fill(CampusJournal.blue.opacity(0.4)).frame(height: 1)
                    detailRows
                    if !item.canChangeCompletion {
                        Label("此任务由来源系统同步，请在原系统办理，再同步最新状态。", systemImage: "arrow.triangle.2.circlepath")
                            .font(.system(size: 12)).foregroundStyle(CampusJournal.muted)
                    }
                    actions
                }
                .padding(24)
                .frame(maxWidth: 700)
                .frame(maxWidth: .infinity)
            }
            .journalSheet()
            .padding(12)
        }
        .campusImmersive()
        .navigationTitle("")
        .safeAreaInset(edge: .top) {
            HStack(spacing: 10) {
                CampusBackButton { dismiss() }
                Text("待办详情").font(.system(size: 20, weight: .bold)).foregroundStyle(CampusJournal.ink)
                Spacer()
            }
            .padding(.horizontal, 16)
            .frame(height: 56)
        }
        .task { await reload() }
        .sheet(isPresented: $showEditor, onDismiss: { Task { await reload() } }) {
            NavigationStack { TaskEditorView(existing: item) }
        }
        .confirmationDialog("删除这项待办？", isPresented: $confirmingDelete, titleVisibility: .visible) {
            Button("删除", role: .destructive) {
                mutate { try await LearningService(client: app.client).deleteTask(item); dismiss() }
            }
        }
        .errorAlert($error)
    }

    private var detailRows: some View {
        VStack(alignment: .leading, spacing: 9) {
            detailRow("状态", item.status.localizedStatus)
            detailRow("来源", item.sourceLabel)
            if let due = item.deadline {
                detailRow("截止时间", due.formatted(.dateTime.year().month().day().hour().minute()))
            }
            if let course = item.courseName { detailRow("课程", course) }
            if let text = item.json["location"].string?.nonEmpty { detailRow("地点", text) }
            if let text = item.json["submission_method"].string?.nonEmpty { detailRow("提交方式", text) }
        }
    }

    private func detailRow(_ label: String, _ value: String) -> some View {
        HStack(alignment: .top) {
            Text(label).font(.system(size: 12)).foregroundStyle(CampusJournal.muted).frame(width: 66, alignment: .leading)
            Text(value).font(.system(size: 13)).foregroundStyle(CampusJournal.ink)
            Spacer(minLength: 0)
        }
    }

    private var actions: some View {
        VStack(spacing: 9) {
            NavigationLink { FocusSetupView(initialGoal: item.title, relatedTaskID: item.id) } label: {
                actionLabel("围绕这项任务专注", icon: "timer")
            }
            NavigationLink { AssistantView(initialPrompt: "请帮我梳理这项任务：" + item.title + "\n" + item.description, relatedTaskID: item.id) } label: {
                actionLabel("请 CPM 帮我梳理", icon: "sparkles")
            }
            if item.canChangeCompletion {
                Button {
                    mutate { item = try await LearningService(client: app.client).setCompleted(item, completed: !item.isCompleted) }
                } label: {
                    actionLabel(item.isCompleted ? "恢复为待完成" : "标记为已完成",
                                icon: item.isCompleted ? "arrow.uturn.backward" : "checkmark.circle")
                }
                .disabled(working)
                Button { showEditor = true } label: { actionLabel("编辑待办", icon: "pencil") }.disabled(working)
                Button { confirmingDelete = true } label: { actionLabel("删除待办", icon: "trash", danger: true) }.disabled(working)
            }
        }
        .padding(.top, 4)
    }

    private func actionLabel(_ title: String, icon: String, danger: Bool = false) -> some View {
        HStack(spacing: 9) {
            Image(systemName: icon).font(.system(size: 14, weight: .semibold))
            Text(title).font(.system(size: 14, weight: .semibold))
            Spacer()
        }
        .foregroundStyle(danger ? Color(hex: 0x8E3430) : CampusJournal.ink)
        .padding(.horizontal, 14)
        .frame(height: 46)
        .background(Color(hex: 0xFFFBF2), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 12, style: .continuous).strokeBorder(Color(hex: 0xCFBDA4, opacity: 0.55), lineWidth: 1))
    }

    private func reload() async {
        do { item = try await LearningService(client: app.client).task(id: item.id) }
        catch is CancellationError { }
        catch { self.error = error.localizedDescription }
    }

    private func mutate(_ action: @escaping @MainActor () async throws -> Void) {
        working = true
        Task {
            defer { working = false }
            do { try await action(); CampusHaptics.success() }
            catch { self.error = error.localizedDescription }
        }
    }
}

/// Paper editor reusing the native date picker.
struct TaskEditorView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    let existing: TaskItem
    @State private var title = ""
    @State private var description = ""
    @State private var hasDeadline = false
    @State private var deadline = Date.now
    @State private var priority = "medium"
    @State private var saving = false
    @State private var error: String?

    var body: some View {
        ZStack {
            JournalBackdrop()
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    Text("编辑待办").font(.system(size: 23, weight: .heavy)).foregroundStyle(CampusJournal.ink)
                    TextField("标题", text: $title, axis: .vertical)
                        .font(.system(size: 15)).foregroundStyle(CampusJournal.ink)
                        .padding(12)
                        .background(Color.white.opacity(0.5), in: RoundedRectangle(cornerRadius: 6))
                    TextField("说明", text: $description, axis: .vertical).lineLimit(3...8)
                        .font(.system(size: 14)).foregroundStyle(CampusJournal.ink)
                        .padding(12)
                        .background(Color.white.opacity(0.5), in: RoundedRectangle(cornerRadius: 6))
                    Toggle("设置截止时间", isOn: $hasDeadline.animation()).tint(CampusJournal.clay)
                    if hasDeadline {
                        DatePicker("截止时间", selection: $deadline, displayedComponents: .date)
                            .datePickerStyle(.graphical)
                            .tint(CampusJournal.clay)
                            .fixedSize(horizontal: false, vertical: true)
                        VStack(alignment: .leading, spacing: 2) {
                            Text("时间").campusFont(.caption).foregroundStyle(CampusJournal.muted)
                            DatePicker("时间", selection: $deadline, displayedComponents: .hourAndMinute)
                                .datePickerStyle(.wheel)
                                .labelsHidden()
                                .frame(maxWidth: .infinity)
                                .tint(CampusJournal.clay)
                        }
                    }
                    HStack(spacing: 8) {
                        ForEach([("low", "低"), ("medium", "中"), ("high", "高")], id: \.0) { value, label in
                            Button {
                                priority = value
                            } label: {
                                Text(label).font(.system(size: 12, weight: priority == value ? .bold : .regular))
                                    .foregroundStyle(priority == value ? .white : CampusJournal.ink)
                                    .padding(.horizontal, 16).padding(.vertical, 8)
                                    .background(priority == value ? CampusJournal.clay : Color.white.opacity(0.5), in: Capsule())
                            }
                        }
                    }
                    Button {
                        save()
                    } label: {
                        Text(saving ? "正在保存…" : "保存").font(.system(size: 15, weight: .bold))
                            .foregroundStyle(.white).frame(maxWidth: .infinity).frame(height: 46)
                            .background(CampusJournal.clay, in: RoundedRectangle(cornerRadius: 14))
                    }
                    .disabled(saving || title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }
                .padding(24)
                .frame(maxWidth: 700)
                .frame(maxWidth: .infinity)
            }
            .journalSheet()
            .padding(12)
            // The journal page is always light paper: keep system-provided
            // labels, values and controls in light appearance even when the
            // app is in dark mode. The date and time pickers are inline, so
            // no dark popover is presented.
            .environment(\.colorScheme, .light)
        }
        .campusImmersive()
        .safeAreaInset(edge: .top) {
            HStack {
                CampusBackButton { dismiss() }
                Text("编辑待办").font(.system(size: 18, weight: .bold)).foregroundStyle(CampusJournal.paper)
                Spacer()
            }
            .padding(.horizontal, 16).frame(height: 56)
        }
        .onAppear {
            title = existing.title; description = existing.description
            hasDeadline = existing.deadline != nil; deadline = existing.deadline ?? .now
            priority = existing.priority
        }
        .errorAlert($error)
    }

    private func save() {
        saving = true
        Task {
            defer { saving = false }
            do {
                var draft = TaskDraft(item: existing)
                draft.title = title; draft.description = description
                draft.deadline = hasDeadline ? deadline : nil
                draft.priority = priority
                _ = try await LearningService(client: app.client).saveTask(draft, existing: existing)
                dismiss()
            } catch { self.error = error.localizedDescription }
        }
    }
}

struct TaskCalendarView: View {    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var date = Date.now
    @State private var resource = PagedResource()

    private var query: [String: String] {
        let start = Calendar.current.startOfDay(for: date)
        return ["deadline_after": APIDate.string(start),
                "deadline_before": APIDate.string(Calendar.current.date(byAdding: .day, value: 1, to: start) ?? start)]
    }

    var body: some View {
        CampusSecondaryScaffold(title: "待办日历") {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    DatePicker("查看日期", selection: $date, displayedComponents: .date)
                        .datePickerStyle(.graphical)
                        .tint(CampusJournal.clay)
                        .padding(12)
                        .background(Color(hex: 0xFFFBF2), in: RoundedRectangle(cornerRadius: 16))
                    Text("当天截止").font(.system(size: 14, weight: .bold)).foregroundStyle(CampusJournal.ink)
                    if resource.isLoading && resource.items.isEmpty { CampusLoadingState() }
                    else if resource.items.isEmpty {
                        CampusEmptyState(title: "当天没有截止事项", systemImage: "calendar")
                    } else {
                        ForEach(Array(resource.items.enumerated()), id: \.offset) { _, value in
                            if let item = try? TaskItem(json: value) {
                                NavigationLink { TaskDetailView(initial: item) } label: {
                                    HStack {
                                        Text(item.title).font(.system(size: 14, weight: .semibold)).foregroundStyle(CampusJournal.ink)
                                        Spacer()
                                        Image(systemName: "chevron.right").font(.system(size: 11)).foregroundStyle(CampusJournal.muted)
                                    }
                                    .padding(14)
                                    .background(Color(hex: 0xFFFBF2), in: RoundedRectangle(cornerRadius: 12))
                                }
                                .buttonStyle(.plain)
                            }
                        }
                    }
                }
                .padding(20)
                .frame(maxWidth: 700)
                .frame(maxWidth: .infinity)
            }
        }
        .task(id: Calendar.current.startOfDay(for: date)) { await load() }
    }

    private func load() async {
        await resource.load(client: app.client, path: "tasks", query: query)
    }
}

/// Notice-to-task extraction, reached from the notification centre.
struct TaskImportView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    var noticeMode = false
    var initialContent = ""
    @State private var content = ""
    @State private var sourceName = "手动导入"
    @State private var review: ImportReview?
    @State private var working = false
    @State private var error: String?

    var body: some View {
        ZStack {
            JournalBackdrop()
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    Text(noticeMode ? "提取通知待办" : "导入待办")
                        .font(.system(size: 23, weight: .heavy)).foregroundStyle(CampusJournal.ink)
                    if let review {
                        ForEach(review.drafts.indices, id: \.self) { index in
                            VStack(alignment: .leading, spacing: 7) {
                                Toggle(isOn: Binding(get: { self.review?.drafts[index]["selected"].bool ?? false },
                                                    set: { value in self.review?.setSelected(value, at: index) })) {
                                    Text("待办 \(index + 1)").font(.system(size: 13, weight: .bold)).foregroundStyle(CampusJournal.night)
                                }
                                .tint(CampusJournal.clay)
                                TextField("标题", text: Binding(get: { self.review?.drafts[index]["title"].text ?? "" },
                                                              set: { self.review?.setTitle($0, at: index) }), axis: .vertical)
                                    .font(.system(size: 14)).foregroundStyle(CampusJournal.ink)
                                if let deadline = review.drafts[index]["deadline"].string?.nonEmpty {
                                    Text("截止 \(deadline)").font(.system(size: 11)).foregroundStyle(CampusJournal.muted)
                                }
                            }
                            .padding(14)
                            .background(Color(hex: 0xFFFBF2), in: RoundedRectangle(cornerRadius: 12))
                        }
                        Button {
                            commit(review)
                        } label: {
                            Text(working ? "正在保存…" : "确认加入 \(review.selectedDrafts.count) 项待办")
                                .font(.system(size: 15, weight: .bold)).foregroundStyle(.white)
                                .frame(maxWidth: .infinity).frame(height: 48)
                                .background(CampusJournal.clay, in: RoundedRectangle(cornerRadius: 14))
                        }
                        .disabled(working || review.selectedDrafts.isEmpty || review.hasInvalidSelection)
                    } else {
                        TextField("来源名称", text: $sourceName)
                            .font(.system(size: 14)).foregroundStyle(CampusJournal.ink)
                            .padding(11)
                            .background(Color.white.opacity(0.45), in: RoundedRectangle(cornerRadius: 5))
                        TextEditor(text: $content)
                            .font(.system(size: 13))
                            .foregroundStyle(CampusJournal.ink)
                            .scrollContentBackground(.hidden)
                            .frame(minHeight: 220)
                            .padding(8)
                            .background(Color.white.opacity(0.45), in: RoundedRectangle(cornerRadius: 5))
                        Button { analyze() } label: {
                            Text(working ? "正在分析…" : "分析并预览")
                                .font(.system(size: 15, weight: .bold)).foregroundStyle(.white)
                                .frame(maxWidth: .infinity).frame(height: 48)
                                .background(CampusJournal.blue, in: RoundedRectangle(cornerRadius: 14))
                        }
                        .disabled(working || content.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                        Text("先检查提取结果，再确认需要加入待办的条目。")
                            .font(.system(size: 11)).foregroundStyle(CampusJournal.muted)
                    }
                }
                .padding(24)
                .frame(maxWidth: 700)
                .frame(maxWidth: .infinity)
            }
            .journalSheet()
            .padding(12)
        }
        .campusImmersive()
        .safeAreaInset(edge: .top) {
            HStack {
                CampusBackButton { dismiss() }
                Text(noticeMode ? "提取通知待办" : "导入待办")
                    .font(.system(size: 18, weight: .bold)).foregroundStyle(CampusJournal.ink)
                Spacer()
            }
            .padding(.horizontal, 16).frame(height: 56)
        }
        .onAppear { if content.isEmpty { content = initialContent } }
        .errorAlert($error)
    }

    private func analyze() {
        working = true
        Task {
            defer { working = false }
            do {
                let service = LearningService(client: app.client)
                let result = try await (noticeMode
                    ? service.extractNotice(content: content, sourceName: sourceName)
                    : service.analyzeImport(content: content, sourceName: sourceName))
                review = ImportReview(json: result)
            } catch { self.error = error.localizedDescription }
        }
    }

    private func commit(_ review: ImportReview) {
        guard !review.hasInvalidSelection, !review.selectedDrafts.isEmpty else { return }
        working = true
        Task {
            defer { working = false }
            do { _ = try await LearningService(client: app.client).commitImport(review.selectedDrafts); dismiss() }
            catch { self.error = error.localizedDescription }
        }
    }
}
