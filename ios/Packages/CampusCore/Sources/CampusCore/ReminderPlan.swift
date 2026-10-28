import Foundation

public struct LocalReminder: Sendable, Equatable, Identifiable {
    public let id: String
    public let title: String
    public let body: String
    public let fire: Date
    public let eventKey: String
}

/// One account's complete snapshot, ordered before applying iOS's pending-request budget.
public struct ReminderPlan: Sendable {
    public let entries: [LocalReminder]

    public init(tasks: [TaskItem], exams: [JSONValue], now: Date = .now, calendar: Calendar = .current, limit: Int = 60) {
        var entries = tasks.compactMap { task -> LocalReminder? in
            guard task.canChangeCompletion, !task.isCompleted, let deadline = task.deadline, deadline > now.addingTimeInterval(1) else { return nil }
            let lead = max(0, task.json["reminder_minutes"].int ?? 30)
            let fire = max(now.addingTimeInterval(1), deadline.addingTimeInterval(-Double(lead) * 60))
            return LocalReminder(id: "task." + task.id, title: "待办快到期", body: task.title, fire: fire,
                                 eventKey: "task.\(task.id).\(deadline.timeIntervalSince1970).\(lead)")
        }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.calendar = Calendar(identifier: .gregorian); formatter.timeZone = calendar.timeZone
        formatter.dateFormat = "yyyy-MM-dd HH:mm"; formatter.isLenient = false
        for exam in exams where exam["reminder_enabled"].bool != false {
            guard let id = exam["id"].string?.nonEmpty, let date = exam["exam_date"].string else { continue }
            let time = exam["start_time"].string?.nonEmpty ?? "08:00"
            guard let start = formatter.date(from: "\(date.prefix(10)) \(time.prefix(5))"), start > now.addingTimeInterval(1) else { continue }
            entries.append(LocalReminder(id: "exam." + id, title: "考试提醒",
                                         body: [exam["course_name"].text, exam["location"].text].filter { !$0.isEmpty }.joined(separator: " · "),
                                         fire: max(now.addingTimeInterval(1), start.addingTimeInterval(-3600)),
                                         eventKey: "exam.\(id).\(start.timeIntervalSince1970)"))
        }
        self.entries = Array(entries.sorted { ($0.fire, $0.id) < ($1.fire, $1.id) }.prefix(max(0, limit)))
    }
}
