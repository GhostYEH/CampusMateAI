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
    private var revision = UUID()

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

    /// Invalidates any suspended scheduling operation before removing the old account's requests.
    func invalidate() {
        revision = UUID()
        center.removeAllPendingNotificationRequests()
        center.removeAllDeliveredNotifications()
    }

    func reschedule(plan: ReminderPlan) async {
        let run = UUID(); revision = run
        guard await isAuthorized else { return }
        guard revision == run, !Task.isCancelled else { return }
        let existing = await center.pendingNotificationRequests().filter { $0.identifier.hasPrefix(prefix) }
        let delivered = await center.deliveredNotifications()
        guard revision == run, !Task.isCancelled else { return }
        let deliveredKeys = Set(delivered.compactMap { $0.request.content.userInfo["event_key"] as? String })
        let desiredKeys = Set(plan.entries.map(\.eventKey))
        var retainedKeys: Set<String> = []
        let obsolete = existing.filter { request in
            guard let key = request.content.userInfo["event_key"] as? String,
                  desiredKeys.contains(key), !deliveredKeys.contains(key),
                  let entry = plan.entries.first(where: { $0.eventKey == key }), entry.body == request.content.body else { return true }
            retainedKeys.insert(key); return false
        }.map(\.identifier)
        center.removePendingNotificationRequests(withIdentifiers: obsolete)
        for entry in plan.entries {
            guard revision == run, !Task.isCancelled else { return }
            guard !deliveredKeys.contains(entry.eventKey), !retainedKeys.contains(entry.eventKey) else { continue }
            let id = prefix + run.uuidString + "." + entry.id
            await add(id: id, entry: entry)
            // A logout can occur while UNUserNotificationCenter is adding the request.
            if revision != run || Task.isCancelled { center.removePendingNotificationRequests(withIdentifiers: [id]); return }
        }
    }

    func cancelAll() async {
        invalidate()
    }

    private func add(id: String, entry: LocalReminder) async {
        let content = UNMutableNotificationContent()
        content.title = entry.title
        content.body = entry.body.isEmpty ? "打开 CampusMate 查看详情。" : entry.body
        content.sound = .default
        content.userInfo = ["event_key": entry.eventKey]
        let trigger = UNTimeIntervalNotificationTrigger(timeInterval: max(1, entry.fire.timeIntervalSinceNow), repeats: false)
        try? await center.add(UNNotificationRequest(identifier: id, content: content, trigger: trigger))
    }

}
