import Foundation

public struct RecordPage: Sendable {
    public let items: [JSONValue]
    public let total: Int
    public let page: Int
    public let hasMore: Bool
    public var nextPage: Int { page + 1 }

    public init(json: JSONValue) throws {
        if let array = json.array { items = array; total = array.count; page = 1; hasMore = false; return }
        guard json["items"].array != nil || json["total"].int != nil || json["page"].int != nil else {
            throw APIError(code: "INVALID_RESPONSE", message: "服务器返回的列表格式不正确。")
        }
        items = json["items"].array ?? []
        total = json["total"].int ?? items.count
        page = max(1, json["page"].int ?? 1)
        hasMore = json["has_more"].bool ?? (page * max(1, json["page_size"].int ?? items.count) < total)
    }
}

public struct TaskItem: Sendable, Identifiable, Equatable {
    public let json: JSONValue
    public let id: String
    public var title: String { json["title"].text }
    public var description: String { json["description"].text }
    public var source: String { json["source"].text }
    public var status: String { json["status"].text }
    public var priority: String { json["priority"].string ?? "medium" }
    public var deadline: Date? { APIDate.parse(json["deadline"].string) }
    public var courseID: String? { json["course_id"].string?.nonEmpty }
    public var isCompleted: Bool { status == "completed" }
    public var isEditable: Bool { source != "chaoxing" && status != "deleted" && source != "course_notice" }
    public var canChangeCompletion: Bool { isEditable }
    public var sourceLabel: String {
        switch source {
        case "chaoxing": "学习通 · 同步状态"
        case "learning_plan": "学习计划"
        case "course_notice": "课程通知 · 本机确认"
        default: json["source_name"].string?.nonEmpty ?? "个人待办"
        }
    }
    public init(json: JSONValue) throws {
        guard let id = json["id"].string?.nonEmpty else { throw APIError(code: "INVALID_RESPONSE", message: "待办缺少有效标识。") }
        self.id = id; self.json = json
    }
}

public struct TaskDraft: Sendable {
    public var title: String
    public var description: String
    public var deadline: Date?
    public var priority: String
    public var sourceName: String
    public var materials: [String]
    public var location: String
    public var submissionMethod: String

    public init(title: String = "", description: String = "", deadline: Date? = nil, priority: String = "medium", sourceName: String = "", materials: [String] = [], location: String = "", submissionMethod: String = "") {
        self.title = title; self.description = description; self.deadline = deadline; self.priority = priority
        self.sourceName = sourceName; self.materials = materials; self.location = location; self.submissionMethod = submissionMethod
    }
    public init(item: TaskItem) {
        self.init(title: item.title, description: item.description, deadline: item.deadline, priority: item.priority,
                  sourceName: item.json["source_name"].text, materials: item.json["materials"].items.compactMap(\.string),
                  location: item.json["location"].text, submissionMethod: item.json["submission_method"].text)
    }
    public var body: JSONValue {
        ["title": .string(title.trimmingCharacters(in: .whitespacesAndNewlines)),
         "description": description.nonEmpty.map(JSONValue.string) ?? .null,
         "deadline": deadline.map { .string(APIDate.string($0)) } ?? .null,
         "priority": .string(priority), "source_name": sourceName.nonEmpty.map(JSONValue.string) ?? .null,
         "materials": .array(materials.map(JSONValue.string)),
         "location": location.nonEmpty.map(JSONValue.string) ?? .null,
         "submission_method": submissionMethod.nonEmpty.map(JSONValue.string) ?? .null]
    }
}

public struct ExamDraft: Sendable {
    public var courseName: String
    public var examDate: String
    public var startTime: String
    public var endTime: String
    public var location: String
    public var notes: String
    public var reminderEnabled: Bool
    public var seatNumber: String
    public var examType: String
    public init(courseName: String = "", examDate: String = "", startTime: String = "", endTime: String = "", location: String = "", notes: String = "", reminderEnabled: Bool = true, seatNumber: String = "", examType: String = "") {
        self.courseName = courseName; self.examDate = examDate; self.startTime = startTime; self.endTime = endTime
        self.location = location; self.notes = notes; self.reminderEnabled = reminderEnabled; self.seatNumber = seatNumber; self.examType = examType
    }
    public var body: JSONValue {
        ["course_name": .string(courseName), "exam_date": .string(examDate),
         "start_time": startTime.nonEmpty.map(JSONValue.string) ?? .null,
         "end_time": endTime.nonEmpty.map(JSONValue.string) ?? .null,
         "location": location.nonEmpty.map(JSONValue.string) ?? .null,
         "notes": notes.nonEmpty.map(JSONValue.string) ?? .null,
         "seat_number": seatNumber.nonEmpty.map(JSONValue.string) ?? .null,
         "exam_type": examType.nonEmpty.map(JSONValue.string) ?? .null,
         "reminder_enabled": .bool(reminderEnabled)]
    }
}

public enum APIDate {
    public static func parse(_ value: String?) -> Date? {
        guard let value, !value.isEmpty else { return nil }
        let fractional = ISO8601DateFormatter()
        fractional.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        return fractional.date(from: value) ?? ISO8601DateFormatter().date(from: value)
    }
    public static func string(_ value: Date) -> String { ISO8601DateFormatter().string(from: value) }
    public static func dateOnly(_ value: Date) -> String {
        let formatter = DateFormatter(); formatter.locale = Locale(identifier: "en_US_POSIX"); formatter.dateFormat = "yyyy-MM-dd"
        return formatter.string(from: value)
    }
    public static func timeOnly(_ value: Date) -> String {
        let formatter = DateFormatter(); formatter.locale = Locale(identifier: "en_US_POSIX"); formatter.dateFormat = "HH:mm"
        return formatter.string(from: value)
    }
}
