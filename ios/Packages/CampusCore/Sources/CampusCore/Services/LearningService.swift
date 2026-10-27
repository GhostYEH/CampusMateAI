import Foundation

public struct LearningService: Sendable {
    public let client: APIClient
    public init(client: APIClient) { self.client = client }

    public func tasks(status: String? = nil, page: Int = 1) async throws -> RecordPage {
        var query = ["page": String(page), "page_size": "50"]
        if let status { query["status"] = status }
        return try RecordPage(json: await client.request(path: "tasks", query: query))
    }
    public func task(id: String) async throws -> TaskItem {
        try TaskItem(json: await client.request(path: "tasks/\(id.pathComponent)"))
    }
    public func saveTask(_ draft: TaskDraft, existing: TaskItem? = nil) async throws -> TaskItem {
        if let existing, !existing.isEditable { throw readOnlyError() }
        guard !draft.title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { throw APIError(code: "VALIDATION_FAILED", message: "请填写待办标题。") }
        let path = existing.map { "tasks/\($0.id.pathComponent)" } ?? "tasks"
        return try TaskItem(json: await client.request(existing == nil ? .post : .patch, path: path, body: draft.body))
    }
    public func setCompleted(_ item: TaskItem, completed: Bool) async throws -> TaskItem {
        guard item.canChangeCompletion else { throw readOnlyError() }
        return try TaskItem(json: await client.request(.post, path: "tasks/\(item.id.pathComponent)/\(completed ? "complete" : "restore")"))
    }
    public func deleteTask(_ item: TaskItem) async throws {
        guard item.isEditable else { throw readOnlyError() }
        _ = try await client.request(.delete, path: "tasks/\(item.id.pathComponent)")
    }
    public func courses(query: String = "", page: Int = 1) async throws -> RecordPage {
        var parameters = ["page": String(page), "page_size": "50"]
        if let query = query.nonEmpty { parameters["query"] = query }
        return try RecordPage(json: await client.request(path: "courses", query: parameters))
    }
    public func course(id: String) async throws -> JSONValue { try await client.request(path: "courses/\(id.pathComponent)") }
    public func content(courseID: String, page: Int = 1) async throws -> JSONValue {
        try await client.request(path: "courses/\(courseID.pathComponent)/content", query: ["page": String(page), "page_size": "100"])
    }
    public func graph(courseID: String) async throws -> JSONValue { try await client.request(path: "courses/\(courseID.pathComponent)/knowledge-graph") }
    public func syncCourse(id: String) async throws -> JSONValue { try await client.request(.post, path: "courses/\(id.pathComponent)/sync") }
    public func notices(page: Int = 1) async throws -> RecordPage {
        try RecordPage(json: await client.request(path: "notices", query: ["page": String(page), "page_size": "50"]))
    }
    public func extractNotice(content: String, sourceName: String) async throws -> JSONValue {
        try await client.request(.post, path: "notices/extract-multi", body: ["content": .string(content), "source_name": .string(sourceName)])
    }
    public func analyzeImport(content: String, sourceName: String) async throws -> JSONValue {
        try await client.request(.post, path: "tasks/import/analyze", body: ["content": .string(content), "source_name": .string(sourceName)])
    }
    public func commitImport(_ drafts: [JSONValue]) async throws -> JSONValue {
        try await client.request(.post, path: "tasks/import/commit", body: ["tasks": .array(drafts)])
    }
    public func exams() async throws -> [JSONValue] { try await client.request(path: "student/exams").items }
    public func saveExam(_ draft: ExamDraft, id: String? = nil) async throws -> JSONValue {
        try await client.request(id == nil ? .post : .patch, path: id.map { "student/exams/\($0.pathComponent)" } ?? "student/exams", body: draft.body)
    }
    public func deleteExam(id: String) async throws { _ = try await client.request(.delete, path: "student/exams/\(id.pathComponent)") }
    private func readOnlyError() -> APIError { APIError(code: "READ_ONLY_SOURCE", message: "这项任务的状态由来源系统同步，请前往原课程查看。") }
}
