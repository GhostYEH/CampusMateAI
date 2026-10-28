import SwiftUI
import CampusCore

/// Port of `ExamsScreen`: a countdown hero, date-grouped timeline and the
/// native date/time pickers for editing.
struct ExamsView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var resource = RemoteResource()
    @State private var filter = "全部"
    @State private var editing: JSONValue?
    @State private var showEditor = false
    @State private var deleting: JSONValue?
    @State private var error: String?
    @State private var now = Date.now

    private var exams: [JSONValue] {
        resource.value.items.sorted { ($0.startDate ?? .distantFuture) < ($1.startDate ?? .distantFuture) }
    }
    private var upcoming: [JSONValue] { exams.filter { ($0.startDate ?? .distantPast) > now } }
    private var filtered: [JSONValue] {
        switch filter {
        case "即将开始": upcoming
        case "已结束": exams.filter { ($0.startDate ?? .distantPast) <= now }
        default: exams
        }
    }
    private var grouped: [(String, [JSONValue])] {
        let groups = Dictionary(grouping: filtered) { $0["exam_date"].text.isEmpty ? "待定" : $0["exam_date"].text }
        return groups.keys.sorted().map { ($0, groups[$0] ?? []) }
    }

    var body: some View {
        CampusSecondaryScaffold(title: "考试安排") {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    overview
                    HStack(spacing: 8) {
                        ForEach(["全部", "即将开始", "已结束"], id: \.self) { option in
                            CampusFilterChip(title: option, isSelected: filter == option) { filter = option }
                        }
                        Spacer()
                        Button { editing = nil; showEditor = true } label: {
                            HStack(spacing: 5) {
                                Image(systemName: "plus").font(.system(size: 12, weight: .bold))
                                Text("添加").font(.system(size: 12, weight: .bold))
                            }
                            .foregroundStyle(.white)
                            .padding(.horizontal, 14).padding(.vertical, 9)
                            .background(Color(hex: 0x285B4B), in: Capsule())
                        }
                        .accessibilityLabel("添加考试")
                    }
                    if resource.isLoading && resource.value == .null {
                        CampusLoadingState(message: "正在读取考试安排…")
                    } else if let error = resource.error, resource.value == .null {
                        CampusErrorState(message: error) { Task { await load() } }
                    } else if filtered.isEmpty {
                        CampusEmptyState(title: "还没有考试安排", message: "添加个人考试安排，或前往学习通同步考试。", systemImage: "calendar.badge.clock")
                    } else {
                        ForEach(Array(grouped.enumerated()), id: \.offset) { _, group in
                            Text(dateLabel(group.0)).campusFont(.caption).fontWeight(.bold)
                                .foregroundStyle(Color(hex: 0x667784))
                                .padding(.top, 4)
                            ForEach(Array(group.1.enumerated()), id: \.offset) { _, exam in
                                examRow(exam)
                            }
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
        .task { await load() }
        .sheet(isPresented: $showEditor, onDismiss: { Task { await load() } }) {
            NavigationStack { ExamEditorView(existing: editing) }
        }
        .confirmationDialog("删除这场考试？", isPresented: Binding(get: { deleting != nil }, set: { if !$0 { deleting = nil } }), titleVisibility: .visible) {
            if let deleting {
                Button("删除", role: .destructive) {
                    Task {
                        do {
                            try await LearningService(client: app.client).deleteExam(id: deleting["id"].text)
                            self.deleting = nil
                            await load()
                        } catch { self.error = error.localizedDescription }
                    }
                }
            }
        }
        .errorAlert($error)
    }

    private var overview: some View {
        Group {
            if let next = upcoming.first {
                NavigationLink { ExamDetailView(exam: next) { Task { await load() } } } label: {
                    ZStack(alignment: .trailing) {
                        LinearGradient(colors: [Color(hex: 0x285B4B), Color(hex: 0x1B473B)],
                                       startPoint: .leading, endPoint: .trailing)
                        Image("exam_calendar_hero")
                            .resizable().scaledToFill()
                            .frame(width: 190)
                            .opacity(0.55)
                            .clipped()
                            .mask(LinearGradient(colors: [.clear, .black], startPoint: .leading, endPoint: .trailing))
                        VStack(alignment: .leading, spacing: 7) {
                            Text("下一场考试").font(.system(size: 11, weight: .semibold)).foregroundStyle(.white.opacity(0.75))
                            Text(next["course_name"].text).font(.system(size: 20, weight: .bold)).foregroundStyle(.white).lineLimit(2)
                            HStack(spacing: 6) {
                                Image(systemName: "calendar").font(.system(size: 11))
                                Text([next["exam_date"].text, next["start_time"].text].filter { !$0.isEmpty }.joined(separator: " "))
                                    .font(.system(size: 12))
                            }
                            .foregroundStyle(.white.opacity(0.85))
                            HStack(spacing: 8) {
                                Text(daysText(next)).font(.system(size: 26, weight: .heavy)).foregroundStyle(.white)
                                Text("还有 \(upcoming.count) 场待考").font(.system(size: 11)).foregroundStyle(.white.opacity(0.7))
                            }
                            .padding(.top, 2)
                        }
                        .padding(18)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    }
                    .frame(minHeight: 152)
                    .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
                }
                .buttonStyle(CampusPressStyle())
            } else {
                HStack(spacing: 13) {
                    Circle().fill(Color(hex: 0xE4EEE5)).frame(width: 48, height: 48)
                        .overlay(Image(systemName: "calendar.badge.clock").foregroundStyle(Color(hex: 0x285B4B)))
                    VStack(alignment: .leading, spacing: 5) {
                        Text("暂时没有即将到来的考试").font(.system(size: 17, weight: .bold)).foregroundStyle(Color(hex: 0x1B2730))
                        Text("添加考试后，这里会显示倒计时。").font(.system(size: 12)).foregroundStyle(Color(hex: 0x667784))
                    }
                    Spacer()
                }
                .padding(18)
                .background(Color(hex: 0xFFFEF8), in: RoundedRectangle(cornerRadius: 24, style: .continuous))
                .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).strokeBorder(Color(hex: 0xD7DED5), lineWidth: 1))
            }
        }
    }

    private func examRow(_ exam: JSONValue) -> some View {
        NavigationLink { ExamDetailView(exam: exam) { Task { await load() } } } label: {
            HStack(alignment: .top, spacing: 12) {
                VStack(spacing: 2) {
                    Text(exam["start_time"].text.isEmpty ? "--:--" : String(exam["start_time"].text.prefix(5)))
                        .font(.system(size: 15, weight: .bold)).foregroundStyle(Color(hex: 0x285B4B))
                    Rectangle().fill(Color(hex: 0x285B4B).opacity(0.25)).frame(width: 1, height: 26)
                }
                .frame(width: 48)
                VStack(alignment: .leading, spacing: 5) {
                    Text(exam["course_name"].text).campusFont(.body).fontWeight(.semibold).foregroundStyle(Color(hex: 0x1B2730))
                    HStack(spacing: 10) {
                        if let location = exam["location"].string?.nonEmpty {
                            Label(location, systemImage: "mappin.and.ellipse")
                        }
                        if let seat = exam["seat_number"].string?.nonEmpty {
                            Label(seat, systemImage: "chair.lounge")
                        }
                    }
                    .campusFont(.caption).foregroundStyle(.secondary)
                    if let notes = exam["notes"].string?.nonEmpty {
                        Text(notes).campusFont(.caption).foregroundStyle(.secondary).lineLimit(2)
                    }
                }
                Spacer(minLength: 0)
                Image(systemName: "chevron.right").font(.system(size: 12)).foregroundStyle(.secondary)
            }
            .padding(14)
            .background(Color(hex: 0xFFFEF8), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(Color(hex: 0xD7DED5, opacity: 0.7), lineWidth: 1))
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .contextMenu {
            Button("删除", role: .destructive) { deleting = exam }
        }
    }

    private func dateLabel(_ raw: String) -> String {
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd"
        guard let date = formatter.date(from: raw) else { return raw }
        return date.formatted(.dateTime.month(.wide).day().weekday(.wide))
    }

    private func daysText(_ exam: JSONValue) -> String {
        guard let start = exam.startDate else { return "—" }
        let days = Calendar.current.dateComponents([.day], from: Calendar.current.startOfDay(for: now),
                                                  to: Calendar.current.startOfDay(for: start)).day ?? 0
        return days <= 0 ? "今天" : "\(days) 天"
    }

    private func load() async {
        await resource.load(client: app.client, path: "student/exams")
        now = .now
        if app.remindersEnabled { app.refreshReminders() }
    }
}

extension JSONValue {
    var startDate: Date? {
        let date = self["exam_date"].string ?? ""
        let time = self["start_time"].string ?? "08:00"
        guard !date.isEmpty else { return nil }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd HH:mm"
        return formatter.date(from: "\(date.prefix(10)) \(time.count >= 5 ? String(time.prefix(5)) : "08:00")")
    }
}


/// Full exam page with countdown, reminder control and destructive actions.
/// Reached from the timeline rows and the next-exam hero.
struct ExamDetailView: View {
    @Environment(\.campus) private var palette
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var exam: JSONValue
    @State private var showEditor = false
    @State private var confirmDelete = false
    @State private var working = false
    @State private var error: String?
    let onChanged: () -> Void

    init(exam: JSONValue, onChanged: @escaping () -> Void = {}) {
        _exam = State(initialValue: exam)
        self.onChanged = onChanged
    }

    private var name: String { exam["course_name"].text }
    private var date: String { exam["exam_date"].string ?? "" }
    private var startTime: String { exam["start_time"].string ?? "" }
    private var endTime: String { exam["end_time"].string ?? "" }
    private var location: String { exam["location"].string ?? "" }
    private var seat: String { exam["seat_number"].string ?? "" }
    private var notes: String { exam["notes"].string ?? "" }
    private var examType: String { exam["exam_type"].text }
    private var reminderEnabled: Bool { exam["reminder_enabled"].bool ?? false }
    private var start: Date? { exam.startDate }

    var body: some View {
        CampusSecondaryScaffold(title: "考试详情") {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    header
                    details
                    reminderCard
                    actions
                }
                .padding(20)
                .frame(maxWidth: 700)
                .frame(maxWidth: .infinity)
            }
        }
        .sheet(isPresented: $showEditor) {
            NavigationStack {
                ExamEditorView(existing: exam, onSaved: { saved in
                    exam = saved
                    app.refreshReminders()
                    onChanged()
                })
            }
        }
        .confirmationDialog("删除这场考试？", isPresented: $confirmDelete, titleVisibility: .visible) {
            Button("删除", role: .destructive) { delete() }
        } message: {
            Text("删除后无法恢复，相关本地提醒也会一并清理。")
        }
        .errorAlert($error)
    }

    private var header: some View {
        CampusCard {
            VStack(alignment: .leading, spacing: 12) {
                HStack(alignment: .top, spacing: 12) {
                    Text(name)
                        .font(.system(size: 21, weight: .bold))
                        .foregroundStyle(palette.textPrimary)
                        .fixedSize(horizontal: false, vertical: true)
                    Spacer(minLength: 0)
                    CampusStatusTag(text: statusText, tone: statusTone)
                }
                if !examType.isEmpty {
                    CampusStatusTag(text: examType, tone: .neutral)
                }
                if let start, start > .now {
                    TimelineView(.periodic(from: .now, by: 60)) { context in
                        HStack(spacing: 7) {
                            Image(systemName: "timer").font(.system(size: 13))
                            Text(countdown(start: start, now: context.date))
                                .font(.system(size: 14, weight: .semibold))
                        }
                        .foregroundStyle(palette.primary)
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private var details: some View {
        CampusCard {
            VStack(alignment: .leading, spacing: 0) {
                detailRow(icon: "calendar", label: "日期", value: dateText)
                divider
                detailRow(icon: "clock", label: "时间", value: timeText)
                divider
                detailRow(icon: "mappin.and.ellipse", label: "地点", value: location.nonEmpty ?? "未填写")
                divider
                detailRow(icon: "chair.lounge", label: "座位", value: seat.nonEmpty ?? "未填写")
                if !notes.isEmpty {
                    divider
                    detailRow(icon: "note.text", label: "备注", value: notes)
                }
            }
        }
    }

    private var reminderCard: some View {
        CampusCard {
            VStack(alignment: .leading, spacing: 8) {
                Toggle("考试提醒", isOn: Binding(get: { reminderEnabled }, set: { setReminder($0) }))
                    .tint(palette.primary)
                    .campusFont(.body)
                    .disabled(working)
                Text(reminderEnabled ? "已开启，考试开始前 1 小时提醒。" : "关闭后不会为这场考试安排本机提醒。")
                    .campusFont(.caption).foregroundStyle(palette.muted)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
    }

    private var actions: some View {
        VStack(spacing: 10) {
            CampusPrimaryButton(title: "编辑考试", systemImage: "pencil", enabled: !working) {
                showEditor = true
            }
            .accessibilityIdentifier("exam.detail.edit")
            Button(role: .destructive) {
                confirmDelete = true
            } label: {
                Text(working ? "正在处理…" : "删除考试")
                    .campusFont(.body).fontWeight(.semibold)
                    .foregroundStyle(palette.dangerText)
                    .frame(maxWidth: .infinity)
                    .frame(minHeight: 46)
                    .background(palette.dangerText.opacity(0.10), in: RoundedRectangle(cornerRadius: 14))
            }
            .buttonStyle(.plain)
            .disabled(working)
            .accessibilityIdentifier("exam.detail.delete")
        }
    }

    private var divider: some View {
        Divider().padding(.vertical, 6)
    }

    private func detailRow(icon: String, label: String, value: String) -> some View {
        HStack(alignment: .top, spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 16)).foregroundStyle(palette.primary).frame(width: 24)
            Text(label).campusFont(.caption).foregroundStyle(palette.muted).frame(width: 52, alignment: .leading)
            Text(value).campusFont(.body).foregroundStyle(palette.textPrimary)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
        }
        .padding(.vertical, 4)
    }

    private var dateText: String {
        guard let start else { return date.isEmpty ? "待定" : date }
        return start.formatted(.dateTime.year().month(.wide).day().weekday(.wide))
    }

    private var timeText: String {
        let start = startTime.prefix(5)
        guard !start.isEmpty else { return "待定" }
        let end = endTime.prefix(5)
        return end.isEmpty ? String(start) : "\(start) – \(end)"
    }

    private var statusText: String {
        guard let start else { return "日期待定" }
        return start > .now ? "即将开始" : "已结束"
    }

    private var statusTone: CampusStatusTone {
        guard let start else { return .neutral }
        return start > .now ? .info : .neutral
    }

    private func countdown(start: Date, now: Date) -> String {
        let seconds = max(0, Int(start.timeIntervalSince(now)))
        let days = seconds / 86_400
        let hours = (seconds % 86_400) / 3_600
        let minutes = (seconds % 3_600) / 60
        if days > 0 { return "距离考试还有 \(days) 天 \(hours) 小时" }
        if hours > 0 { return "距离考试还有 \(hours) 小时 \(minutes) 分钟" }
        return "距离考试还有 \(minutes) 分钟"
    }

    private func setReminder(_ enabled: Bool) {
        guard !working else { return }
        working = true
        Task {
            defer { working = false }
            do {
                let draft = ExamDraft(courseName: name, examDate: date,
                                      startTime: startTime, endTime: endTime,
                                      location: location, notes: notes,
                                      reminderEnabled: enabled, seatNumber: seat,
                                      examType: examType)
                let saved = try await LearningService(client: app.client).saveExam(draft, id: exam["id"].string)
                exam = saved
                if enabled { _ = await ReminderScheduler.shared.requestAuthorization() }
                app.refreshReminders()
                onChanged()
            } catch { self.error = error.localizedDescription }
        }
    }

    private func delete() {
        guard !working, let id = exam["id"].string else { return }
        working = true
        Task {
            defer { working = false }
            do {
                try await LearningService(client: app.client).deleteExam(id: id)
                app.refreshReminders()
                onChanged()
                dismiss()
            } catch { self.error = error.localizedDescription }
        }
    }
}

struct ExamEditorView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    var existing: JSONValue?
    var onSaved: ((JSONValue) -> Void)? = nil
    @State private var name = ""
    @State private var date = Date.now
    @State private var start = Date.now
    @State private var end = Date.now.addingTimeInterval(3600)
    @State private var location = ""
    @State private var seat = ""
    @State private var examType = ""
    @State private var notes = ""
    @State private var reminder = true
    @State private var saving = false
    @State private var error: String?

    var body: some View {
        CampusSecondaryScaffold(title: existing == nil ? "添加考试" : "编辑考试") {
            ScrollView {
                VStack(spacing: 12) {
                    CampusCard {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("考试信息").campusFont(.subtitle).foregroundStyle(Color(hex: 0x1B2730))
                            CampusTextField(placeholder: "课程名称", text: $name, systemImage: "book")
                            DatePicker("日期", selection: $date, displayedComponents: .date).tint(Color(hex: 0x285B4B))
                            DatePicker("开始", selection: $start, displayedComponents: .hourAndMinute).tint(Color(hex: 0x285B4B))
                            DatePicker("结束", selection: $end, displayedComponents: .hourAndMinute).tint(Color(hex: 0x285B4B))
                            CampusTextField(placeholder: "考试类型（可选）", text: $examType)
                        }
                    }
                    CampusCard {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("考场").campusFont(.subtitle).foregroundStyle(Color(hex: 0x1B2730))
                            CampusTextField(placeholder: "地点", text: $location, systemImage: "mappin.and.ellipse")
                            CampusTextField(placeholder: "座位号", text: $seat)
                        }
                    }
                    CampusCard {
                        VStack(alignment: .leading, spacing: 12) {
                            Toggle("考试提醒", isOn: $reminder).tint(Color(hex: 0x285B4B))
                            CampusTextField(placeholder: "备注", text: $notes)
                            Text("系统提醒需允许通知；考试前 1 小时提醒。").campusFont(.caption).foregroundStyle(.secondary)
                        }
                    }
                    CampusPrimaryButton(title: saving ? "保存中…" : "保存", loading: saving,
                                        enabled: !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty) { save() }
                }
                .padding(20)
                .frame(maxWidth: 700)
                .frame(maxWidth: .infinity)
            }
        }
        .onAppear {
            guard let item = existing else { return }
            name = item["course_name"].text
            location = item["location"].text
            seat = item["seat_number"].text
            examType = item["exam_type"].text
            notes = item["notes"].text
            reminder = item["reminder_enabled"].bool ?? true
            let formatter = DateFormatter()
            formatter.locale = Locale(identifier: "en_US_POSIX")
            formatter.dateFormat = "yyyy-MM-dd"
            date = formatter.date(from: item["exam_date"].text) ?? .now
            formatter.dateFormat = "HH:mm"
            start = formatter.date(from: item["start_time"].text) ?? .now
            end = formatter.date(from: item["end_time"].text) ?? .now.addingTimeInterval(3600)
        }
        .errorAlert($error)
    }

    private func save() {
        saving = true
        Task {
            defer { saving = false }
            do {
                let draft = ExamDraft(courseName: name, examDate: APIDate.dateOnly(date),
                                      startTime: APIDate.timeOnly(start), endTime: APIDate.timeOnly(end),
                                      location: location, notes: notes, reminderEnabled: reminder,
                                      seatNumber: seat, examType: examType)
                let saved = try await LearningService(client: app.client).saveExam(draft, id: existing?["id"].string)
                onSaved?(saved)
                if reminder { _ = await ReminderScheduler.shared.requestAuthorization() }
                CampusHaptics.success()
                dismiss()
            } catch { self.error = error.localizedDescription }
        }
    }
}
