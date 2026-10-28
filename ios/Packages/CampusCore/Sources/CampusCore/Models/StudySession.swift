import Foundation

public struct StudySession: Sendable, Identifiable, Equatable {
    public let json: JSONValue
    public let id: String
    public let startedAt: Date
    public var status: String { json["status"].text }
    public var isActive: Bool { status == "active" || status == "paused" }
    public var isPaused: Bool { status == "paused" }
    public var goal: String { json["goal"].text }
    public var experienceMode: String { json["experience_mode"].string ?? "QUIET" }
    public var plannedSeconds: Int { json["planned_duration_seconds"].int ?? 1500 }
    public var relatedTaskID: String? { json["related_task_id"].string }
    public var report: String { json["self_report"].text }
    public init(json: JSONValue) throws {
        guard let id = json["id"].string?.nonEmpty, let start = APIDate.parse(json["started_at"].string), json["status"].string != nil else {
            throw APIError(code: "INVALID_RESPONSE", message: "专注会话信息不完整，请刷新。")
        }
        self.id = id; startedAt = start; self.json = json
    }
    public func elapsed(at now: Date) -> TimeInterval {
        if !isActive { return max(0, json["duration_seconds"].double ?? 0) }
        let end = isPaused ? APIDate.parse(json["paused_at"].string) ?? now : now
        return max(0, end.timeIntervalSince(startedAt) - (json["pause_seconds"].double ?? 0))
    }
}
