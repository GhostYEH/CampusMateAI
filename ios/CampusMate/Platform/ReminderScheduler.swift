import Foundation
import UserNotifications
import CampusCore

/// Local reminders for personal deadlines. iOS cannot read other apps'
/// notifications, so reminders are scheduled from data the app already has and
/// never claim to observe WeChat/QQ.
@MainActor
final class ReminderScheduler {
    static let shared = ReminderScheduler()
    private let center = UNUserNotificationCenter.current()
    private let prefix = "campus.reminder."

    var isAuthorized: Bool {
        get async {
            let settings = await center.notificationSettings()
            return settings.authorizationStatus == .authorized || settings.authorizationStatus == .provisional
        }
    }

    func requestAuthorization() async -> Bool {
        do { return try await center.requestAuthorization(options: [.alert, .sound, .badge]) }
        catch { return false }
    }

    func authorizationStatus() async -> UNAuthorizationStatus {
        await center.notificationSettings().authorizationStatus
    }

    /// Replaces pending reminders with the current deadline set. Only personal
    /// tasks and personal exams are scheduled; read-only synced items keep
    /// their source system's own reminders.
    func reschedule(tasks: [TaskItem], exams: [JSONValue]) async {
        guard await isAuthorized else { return }
        let existing = await center.pendingNotificationRequests().map(\.identifier).filter { $0.hasPrefix(prefix) }
        center.removePendingNotificationRequests(withIdentifiers: existing)
        for task in tasks where task.canChangeCompletion {
            guard let deadline = task.deadline, deadline > .now.addingTimeInterval(60) else { continue }
            let fire = deadline.addingTimeInterval(-30 * 60)
            guard fire > .now else { continue }
            await add(id: prefix + "task." + task.id,
                      title: "待办快到期",
                      body: task.title,
                      fire: fire,
                      deepLink: "campus://tasks")
        }
        for exam in exams {
            guard let fire = Self.examFireDate(exam) else { continue }
            await add(id: prefix + "exam." + exam["id"].text,
                      title: "考试提醒",
                      body: [exam["course_name"].text, exam["location"].text].filter { !$0.isEmpty }.joined(separator: " · "),
                      fire: fire,
                      deepLink: "campus://exams")
        }
    }

    func cancelAll() async {
        let existing = await center.pendingNotificationRequests().map(\.identifier).filter { $0.hasPrefix(prefix) }
        center.removePendingNotificationRequests(withIdentifiers: existing)
    }

    private func add(id: String, title: String, body: String, fire: Date, deepLink: String) async {
        let content = UNMutableNotificationContent()
        content.title = title
        content.body = body.isEmpty ? "打开 CampusMate 查看详情。" : body
        content.sound = .default
        content.userInfo = ["deep_link": deepLink]
        let components = Calendar.current.dateComponents([.year, .month, .day, .hour, .minute], from: fire)
        let trigger = UNCalendarNotificationTrigger(dateMatching: components, repeats: false)
        try? await center.add(UNNotificationRequest(identifier: id, content: content, trigger: trigger))
    }

    static func examFireDate(_ exam: JSONValue) -> Date? {
        let date = exam["exam_date"].string ?? ""
        let time = exam["start_time"].string ?? "08:00"
        guard !date.isEmpty else { return nil }
        let formatter = DateFormatter()
        formatter.locale = Locale(identifier: "en_US_POSIX")
        formatter.dateFormat = "yyyy-MM-dd HH:mm"
        let normalized = time.count >= 5 ? String(time.prefix(5)) : "08:00"
        guard let start = formatter.date(from: "\(date.prefix(10)) \(normalized)") else { return nil }
        let fire = start.addingTimeInterval(-3600)
        return fire > .now ? fire : nil
    }
}
