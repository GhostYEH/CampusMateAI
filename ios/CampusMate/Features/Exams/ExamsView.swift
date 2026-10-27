import SwiftUI
import CampusCore

struct ExamsView: View {
    @Environment(AppModel.self) private var app
    @State private var resource = RemoteResource()
    @State private var showingEditor = false
    @State private var selected: JSONValue?
    @State private var deleting: JSONValue?
    @State private var error: String?

    var body: some View {
        List {
            ResourceStateView(resource: resource, isEmpty: resource.value.items.isEmpty, title: "还没有考试安排", message: "添加个人考试安排，或前往学习通同步考试。", systemImage: "calendar.badge.clock", retry: load)
            ForEach(Array(resource.value.items.enumerated()), id: \.offset) { _, exam in
                Button { selected = exam; showingEditor = true } label: {
                    VStack(alignment: .leading, spacing: 7) {
                        Text(exam["course_name"].text).font(.headline).foregroundStyle(.primary)
                        Label([exam["exam_date"].text, exam["start_time"].text].filter { !$0.isEmpty }.joined(separator: " "), systemImage: "calendar").font(.subheadline).foregroundStyle(.secondary)
                        if let location = exam["location"].string?.nonEmpty { Label(location, systemImage: "mappin.and.ellipse").font(.caption).foregroundStyle(.secondary) }
                    }.padding(.vertical, 4)
                }.swipeActions { Button("删除", role: .destructive) { deleting = exam } }
            }
        }.navigationTitle("考试安排").task { await load() }.refreshable { await load() }
        .toolbar { Button("添加", systemImage: "plus") { selected = nil; showingEditor = true } }
        .sheet(isPresented: $showingEditor, onDismiss: { Task { await load() } }) { NavigationStack { ExamEditorView(existing: selected) } }
        .confirmationDialog("删除这场考试？", isPresented: Binding(get: { deleting != nil }, set: { if !$0 { deleting = nil } }), titleVisibility: .visible) {
            if let deleting {
                Button("删除", role: .destructive) {
                    Task {
                        do { try await LearningService(client: app.client).deleteExam(id: deleting["id"].text); self.deleting = nil; await load() }
                        catch { self.error = error.localizedDescription }
                    }
                }
            }
        }.errorAlert($error)
    }
    private func load() async { await resource.load(client: app.client, path: "student/exams") }
}

struct ExamEditorView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    var existing: JSONValue?
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
        Form {
            Section("考试信息") {
                TextField("课程名称", text: $name)
                DatePicker("日期", selection: $date, displayedComponents: .date)
                DatePicker("开始", selection: $start, displayedComponents: .hourAndMinute)
                DatePicker("结束", selection: $end, displayedComponents: .hourAndMinute)
                TextField("考试类型", text: $examType)
            }
            Section("考场") { TextField("地点", text: $location); TextField("座位号", text: $seat) }
            Section {
                Toggle("考试提醒", isOn: $reminder)
                TextField("备注", text: $notes, axis: .vertical).lineLimit(3...8)
            } footer: { Text("系统提醒需允许通知，并在应用设置中开启提醒。") }
        }
        .navigationTitle(existing == nil ? "添加考试" : "编辑考试").navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .cancellationAction) { Button("取消") { dismiss() } }
            ToolbarItem(placement: .confirmationAction) { Button(saving ? "保存中…" : "保存", action: save).disabled(saving || name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty) }
        }
        .onAppear {
            guard let item = existing else { return }
            name = item["course_name"].text; location = item["location"].text; seat = item["seat_number"].text
            examType = item["exam_type"].text; notes = item["notes"].text; reminder = item["reminder_enabled"].bool ?? true
            let formatter = DateFormatter(); formatter.locale = Locale(identifier: "en_US_POSIX"); formatter.dateFormat = "yyyy-MM-dd"
            date = formatter.date(from: item["exam_date"].text) ?? .now
            formatter.dateFormat = "HH:mm"
            start = formatter.date(from: item["start_time"].text) ?? .now
            end = formatter.date(from: item["end_time"].text) ?? .now.addingTimeInterval(3600)
        }.errorAlert($error)
    }
    private func save() {
        saving = true
        Task {
            defer { saving = false }
            do {
                let draft = ExamDraft(courseName: name, examDate: APIDate.dateOnly(date), startTime: APIDate.timeOnly(start), endTime: APIDate.timeOnly(end), location: location, notes: notes, reminderEnabled: reminder, seatNumber: seat, examType: examType)
                _ = try await LearningService(client: app.client).saveExam(draft, id: existing?["id"].string)
                dismiss()
            } catch { self.error = error.localizedDescription }
        }
    }
}
