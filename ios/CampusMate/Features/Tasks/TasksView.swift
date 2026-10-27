import SwiftUI
import CampusCore

/// Port of `TasksScreen`: a paper task journal with margin tabs, stamped
/// completion and course-grouped assignments.
struct TasksView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var resource = PagedResource()
    @State private var filter = "待完成"
    @State private var search = ""
    @State private var selectedCourse: String?
    @State private var expandedCourses: Set<String> = []
    @State private var showEditor = false
    @State private var showCourseFilter = false
    @State private var showCalendar = false
    @State private var selectedTask: TaskItem?
    @State private var error: String?
    @State private var toast: String?

    private let filters = ["全部", "待完成", "已完成", "个人事务"]

    private var allTasks: [TaskItem] { resource.items.compactMap { try? TaskItem(json: $0) } }
    private var courseNames: [String] {
        Array(Set(allTasks.compactMap(\.courseName).filter { !$0.isEmpty })).sorted()
    }
    private var visible: [TaskItem] {
        let base: [TaskItem]
        switch filter {
        case "已完成": base = allTasks.filter(\.isCompleted)
        case "个人事务": base = allTasks.filter { !$0.isCourseAssignment }
        case "全部": base = allTasks
        default: base = allTasks.filter { !$0.isCompleted }
        }
        return base
            .filter { filter == "个人事务" || selectedCourse == nil || $0.courseName == selectedCourse }
            .filter {
                search.isEmpty || $0.title.localizedCaseInsensitiveContains(search)
                    || ($0.courseName ?? "").localizedCaseInsensitiveContains(search)
            }
            .sorted { left, right in
                if filter == "全部", left.isCompleted != right.isCompleted { return !left.isCompleted }
                return (left.deadline ?? .distantFuture) < (right.deadline ?? .distantFuture)
            }
    }
    private var upcoming: [TaskItem] { visible.filter { !$0.isCompleted } }
    private var todayTasks: [TaskItem] { upcoming.filter { ($0.deadline ?? .distantFuture) < .now.addingTimeInterval(24 * 3600) } }
    private var weekTasks: [TaskItem] { upcoming.filter { !todayTasks.contains($0) && ($0.deadline ?? .distantFuture) < .now.addingTimeInterval(7 * 24 * 3600) } }
    private var laterTasks: [TaskItem] { upcoming.filter { !todayTasks.contains($0) && !weekTasks.contains($0) } }
    private var pendingCount: Int { allTasks.filter { !$0.isCompleted }.count }

    var body: some View {
        ZStack(alignment: .topLeading) {
            JournalBackdrop()
            ScrollView {
                VStack(alignment: .leading, spacing: 5) {
                    header
                    if let error {
                        HStack(spacing: 7) {
                            Image(systemName: "icloud.slash").font(.system(size: 14)).foregroundStyle(CampusJournal.amber)
                            Text(error).font(.system(size: 12)).foregroundStyle(Color(hex: 0x8E3430)).lineLimit(2)
                            Spacer()
                            Button("重试") { Task { await load() } }.font(.system(size: 12, weight: .semibold))
                        }
                        .padding(.horizontal, 13)
                        .padding(.vertical, 9)
                        .background(Color(hex: 0xF6DAD8), in: RoundedRectangle(cornerRadius: 15, style: .continuous))
                    }
                    journalMeta
                    sectionHeader
                    taskSections
                    if let toast {
                        Text(toast).font(.system(size: 11)).foregroundStyle(CampusJournal.clay).padding(.top, 4)
                    }
                }
                .padding(.leading, 26)
                .padding(.trailing, 40)
                .padding(.top, 9)
                .padding(.bottom, 34)
                .frame(maxWidth: 760)
            }
            .scrollIndicators(.hidden)
            .journalBookPage()
            .padding(.leading, 12)
            .padding(.trailing, 4)
            .padding(.top, 8)
            .padding(.bottom, 10)

            filterTabs
                .frame(maxWidth: .infinity, alignment: .trailing)
                .padding(.top, 6)
        }
        .campusImmersive()
        .task { await load() }
        .refreshable { await load() }
        .navigationDestination(isPresented: Binding(get: { selectedTask != nil },
                                                    set: { if !$0 { selectedTask = nil } })) {
            if let task = selectedTask { TaskDetailView(initial: task) }
        }
        .sheet(isPresented: $showEditor, onDismiss: { Task { await load() } }) {
            NavigationStack { TaskComposerSheet() }
        }
        .sheet(isPresented: $showCalendar) { NavigationStack { TaskCalendarView() } }
        .sheet(isPresented: $showCourseFilter) { courseFilterSheet.presentationDetents([.medium]) }
        .errorAlert($error)
    }

    private var header: some View {
        HStack(alignment: .center, spacing: 8) {
            CampusBackButton { dismiss() }
            VStack(alignment: .leading, spacing: 2) {
                Text("待办手账").font(.system(size: 25, weight: .heavy)).foregroundStyle(CampusJournal.night)
                Text("\(pendingCount) 件待处理 · \(todayTasks.count) 件今天优先")
                    .font(.system(size: 11)).foregroundStyle(CampusJournal.muted)
            }
            Spacer(minLength: 0)
            PaperPlusButton { showEditor = true }
                .accessibilityIdentifier("tasks.add")
            Menu {
                Button("待办日历", systemImage: "calendar") { showCalendar = true }
                NavigationLink { ExamsView() } label: { Label("考试安排", systemImage: "calendar.badge.clock") }
            } label: {
                Image(systemName: "calendar").font(.system(size: 17)).foregroundStyle(CampusJournal.night)
                    .frame(width: 40, height: 40)
            }
            .accessibilityLabel("日历与考试")
        }
        .frame(minHeight: 72)
    }

    private var journalMeta: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("CAMPUS / TASK JOURNAL     ·     \(filter)")
                .font(.system(size: 10, weight: .heavy))
                .tracking(1)
                .foregroundStyle(CampusJournal.clay)
            HStack(spacing: 8) {
                Image(systemName: "magnifyingglass").font(.system(size: 13)).foregroundStyle(CampusJournal.blue)
                TextField("搜索作业或课程", text: $search)
                    .font(.system(size: 13))
                    .foregroundStyle(CampusJournal.ink)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
            }
            .padding(.horizontal, 11)
            .padding(.vertical, 9)
            .background(Color.white.opacity(0.42), in: RoundedRectangle(cornerRadius: 5, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 5, style: .continuous).strokeBorder(CampusJournal.blue.opacity(0.55), lineWidth: 1))

            if filter != "个人事务" {
                Button { showCourseFilter = true } label: {
                    HStack(spacing: 7) {
                        Image(systemName: "slider.horizontal.3").font(.system(size: 13)).foregroundStyle(CampusJournal.blue)
                        Text(selectedCourse ?? "按课程筛选").font(.system(size: 12)).foregroundStyle(CampusJournal.night).lineLimit(1)
                        Spacer()
                        Image(systemName: "chevron.right").font(.system(size: 11, weight: .semibold)).foregroundStyle(CampusJournal.muted)
                    }
                    .padding(.vertical, 9)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
            }
            Rectangle().fill(CampusJournal.blue.opacity(0.38)).frame(height: 1)
        }
        .padding(.vertical, 8)
    }

    private var sectionHeader: some View {
        HStack {
            Text(filter == "待完成" ? "接下来要做" : filter)
                .font(.system(size: 17, weight: .heavy)).foregroundStyle(CampusJournal.night)
            Spacer()
            Text("\(visible.count) 项").font(.system(size: 13)).foregroundStyle(CampusJournal.muted)
        }
        .padding(.top, 2)
    }

    @ViewBuilder
    private var taskSections: some View {
        if visible.isEmpty {
            VStack(spacing: 8) {
                Image(systemName: "checkmark.seal").font(.system(size: 26, weight: .light)).foregroundStyle(CampusJournal.clay)
                Text("这页手账暂时空着").font(.system(size: 14, weight: .bold)).foregroundStyle(CampusJournal.night)
                Text(filter == "已完成" ? "完成一件事后，印章会留在这里" : "给今天留一点空间，也可以添加一件小事")
                    .font(.system(size: 12)).foregroundStyle(CampusJournal.muted)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 34)
        } else {
            let sections: [(String, [TaskItem])] = filter == "已完成"
                ? [("已盖章", visible)]
                : [("今天优先", todayTasks), ("本周待办", weekTasks), ("之后处理", laterTasks)]
                    + ((filter == "全部" || filter == "个人事务") ? [("已完成", visible.filter(\.isCompleted))] : [])
            ForEach(Array(sections.enumerated()), id: \.offset) { _, section in
                if !section.1.isEmpty {
                    Text("\(section.0)  /  \(section.1.count)")
                        .font(.system(size: 12, weight: .bold))
                        .foregroundStyle(CampusJournal.clay)
                        .padding(.top, 6)
                    taskGroup(section.1)
                }
            }
        }
    }

    @ViewBuilder
    private func taskGroup(_ tasks: [TaskItem]) -> some View {
        ForEach(tasks.filter { !$0.isCourseAssignment }) { task in
            TaskJournalRow(task: task, onOpen: { selectedTask = task }) {
                Task { await toggle(task) }
            }
        }
        let grouped = Dictionary(grouping: tasks.filter(\.isCourseAssignment)) { $0.courseName ?? "课程作业" }
        ForEach(Array(grouped.keys.sorted()), id: \.self) { course in
            let courseTasks = grouped[course] ?? []
            Button {
                CampusHaptics.selection()
                if expandedCourses.contains(course) { expandedCourses.remove(course) } else { expandedCourses.insert(course) }
            } label: {
                HStack(spacing: 7) {
                    Image(systemName: "book.closed").font(.system(size: 14)).foregroundStyle(CampusJournal.blue)
                    Text(course).font(.system(size: 13, weight: .bold)).foregroundStyle(CampusJournal.night).lineLimit(1)
                    Spacer()
                    Text("\(courseTasks.count) 项").font(.system(size: 11)).foregroundStyle(CampusJournal.muted)
                    Image(systemName: expandedCourses.contains(course) ? "chevron.up" : "chevron.down")
                        .font(.system(size: 12, weight: .semibold)).foregroundStyle(CampusJournal.blue)
                }
                .padding(.vertical, 11)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel(expandedCourses.contains(course) ? "收起\(course)" : "展开\(course)")
            if expandedCourses.contains(course) {
                ForEach(courseTasks) { task in
                    TaskJournalRow(task: task, onOpen: { selectedTask = task }) {
                        Task { await toggle(task) }
                    }
                }
            }
        }
    }

    private var filterTabs: some View {
        VStack(spacing: 5) {
            ForEach(filters, id: \.self) { label in
                let active = filter == label
                Button {
                    filter = label
                    selectedCourse = nil
                    CampusHaptics.selection()
                } label: {
                    Text(label.map(String.init).joined(separator: "\n"))
                        .font(.system(size: 10, weight: active ? .heavy : .medium))
                        .multilineTextAlignment(.center)
                        .foregroundStyle(.white)
                        .frame(width: active ? 33 : 28, height: 69)
                        .background(tabColor(label), in: UnevenRoundedRectangle(topLeadingRadius: 7, bottomLeadingRadius: 7))
                }
                .buttonStyle(.plain)
                .accessibilityLabel("筛选\(label)")
                .accessibilityAddTraits(active ? [.isSelected, .isButton] : .isButton)
            }
        }
    }

    private func tabColor(_ label: String) -> Color {
        switch label {
        case "待完成": CampusJournal.clay
        case "已完成": CampusJournal.blue
        case "个人事务": Color(hex: 0x9B8064)
        default: Color(hex: 0x61758A)
        }
    }

    private var courseFilterSheet: some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("按课程筛选").font(.system(size: 19, weight: .bold)).foregroundStyle(CampusJournal.night)
            ScrollView {
                VStack(spacing: 0) {
                    Button { selectedCourse = nil; showCourseFilter = false } label: {
                        HStack {
                            Text("所有课程").font(.system(size: 15)).foregroundStyle(CampusJournal.ink)
                            Spacer()
                            if selectedCourse == nil { Image(systemName: "checkmark").foregroundStyle(CampusJournal.clay) }
                        }
                        .padding(.vertical, 13).contentShape(Rectangle())
                    }
                    ForEach(courseNames, id: \.self) { name in
                        Button {
                            selectedCourse = name
                            expandedCourses.insert(name)
                            showCourseFilter = false
                        } label: {
                            HStack {
                                Text(name).font(.system(size: 15)).foregroundStyle(CampusJournal.ink).lineLimit(1)
                                Spacer()
                                if selectedCourse == name { Image(systemName: "checkmark").foregroundStyle(CampusJournal.clay) }
                            }
                            .padding(.vertical, 13).contentShape(Rectangle())
                        }
                    }
                }
            }
            Button("关闭") { showCourseFilter = false }
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(CampusJournal.clay)
                .frame(maxWidth: .infinity, alignment: .trailing)
        }
        .padding(20)
        .background(CampusJournal.paper)
    }

    private func load() async {
        await resource.load(client: app.client, path: "tasks")
        error = resource.error
    }

    private func toggle(_ task: TaskItem) async {
        guard task.canChangeCompletion else {
            error = "这项任务的状态由来源系统同步，请前往原课程查看。"
            return
        }
        do {
            _ = try await LearningService(client: app.client).setCompleted(task, completed: !task.isCompleted)
            CampusHaptics.success()
            await load()
        } catch { self.error = error.localizedDescription }
    }
}

/// One ruled line in the journal. Completion stamps the page before the row
/// settles into its "已完成" state.
struct TaskJournalRow: View {
    let task: TaskItem
    let onOpen: () -> Void
    let onToggle: () -> Void
    @Environment(AppModel.self) private var app
    @State private var stamping = false

    private var accent: Color {
        if task.isCompleted { return CampusJournal.blue }
        if (task.deadline ?? .distantFuture) < .now.addingTimeInterval(24 * 3600) { return CampusJournal.amber }
        if task.isCourseAssignment { return CampusJournal.clay }
        return CampusJournal.blue
    }

    var body: some View {
        Button(action: onOpen) {
            HStack(alignment: .center, spacing: 0) {
                Rectangle().fill(accent).frame(width: 3, height: 36)
                Spacer().frame(width: 5)
                if task.isCourseAssignment {
                    Image(systemName: "doc.text.fill")
                        .font(.system(size: 18))
                        .foregroundStyle(CampusJournal.night)
                        .frame(width: 38, height: 38)
                        .accessibilityLabel("课程作业")
                } else {
                    Button {
                        guard !stamping else { return }
                        if app.reduceMotion || task.isCompleted { onToggle() }
                        else {
                            stamping = true
                            CampusHaptics.success()
                            Task {
                                try? await Task.sleep(for: .milliseconds(560))
                                onToggle()
                                stamping = false
                            }
                        }
                    } label: {
                        Image(systemName: task.isCompleted || stamping ? "checkmark.square.fill" : "square")
                            .font(.system(size: 21))
                            .foregroundStyle(CampusJournal.clay)
                            .frame(width: 38, height: 38)
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel(task.isCompleted ? "恢复为待完成" : "标记为已完成")
                }
                Spacer().frame(width: 4)
                VStack(alignment: .leading, spacing: 3) {
                    Text(task.title)
                        .font(.system(size: 14, weight: .bold))
                        .foregroundStyle(task.isCompleted ? CampusJournal.muted : CampusJournal.night)
                        .strikethrough(task.isCompleted, color: CampusJournal.muted)
                        .lineLimit(1)
                    Text("\(task.courseName ?? "个人事务") · 截止 \(deadlineText)")
                        .font(.system(size: 11))
                        .foregroundStyle(CampusJournal.muted)
                        .lineLimit(1)
                    if !task.isCompleted, ["chaoxing_notice", "course_notice"].contains(task.source) {
                        Text("提交状态待确认").font(.system(size: 10)).foregroundStyle(Color(hex: 0x966942))
                    }
                }
                Spacer(minLength: 4)
                if task.isCompleted {
                    Text("已完成")
                        .font(.system(size: 10, weight: .bold))
                        .foregroundStyle(CampusJournal.clay)
                        .padding(.horizontal, 4)
                        .padding(.vertical, 2)
                        .overlay(RoundedRectangle(cornerRadius: 3).strokeBorder(CampusJournal.clay.opacity(0.7), lineWidth: 1))
                }
            }
            .padding(.vertical, 7)
            .frame(minHeight: 64)
            .overlay(alignment: .bottom) {
                Rectangle().fill(CampusJournal.blue.opacity(0.32)).frame(height: 1)
            }
            .overlay(alignment: .bottomTrailing) {
                if stamping && !app.reduceMotion {
                    JournalStamp(text: "已完成")
                        .scaleEffect(1)
                        .padding(.trailing, 10)
                        .padding(.bottom, 5)
                        .transition(.scale(scale: 1.4).combined(with: .opacity))
                }
            }
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    private var deadlineText: String {
        guard let deadline = task.deadline else { return "未设置" }
        return deadline.formatted(.dateTime.year().month(.twoDigits).day(.twoDigits).hour().minute())
    }
}

extension TaskItem {
    var courseName: String? {
        let value = json["course"].string ?? json["course_name"].string ?? ""
        return value.isEmpty ? nil : value
    }
    var isCourseAssignment: Bool {
        ["chaoxing", "chaoxing_notice", "course_notice"].contains(source)
    }
}
