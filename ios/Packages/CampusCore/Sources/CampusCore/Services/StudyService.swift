import Foundation

public struct StudyService: Sendable {
    public let client: APIClient
    public init(client: APIClient) { self.client = client }
    public func active() async throws -> StudySession? {
        let result = try await client.request(path: "study/sessions/active")
        return result == .null ? nil : try StudySession(json: result)
    }
    public func session(id: String) async throws -> StudySession { try StudySession(json: await client.request(path: "study/sessions/\(id.pathComponent)")) }
    public func start(goal: String, durationSeconds: Int, mode: String, relatedTaskID: String? = nil) async throws -> StudySession {
        guard (300...14400).contains(durationSeconds), ["QUIET", "AI_COMPANION", "SMART_GUARD"].contains(mode), goal.count <= 500 else { throw APIError(code: "VALIDATION_FAILED", message: "请选择 5–240 分钟的专注时长和有效模式。") }
        var body: [String: JSONValue] = ["mode": "focus", "experience_mode": .string(mode), "goal": goal.nonEmpty.map(JSONValue.string) ?? .null, "planned_duration_seconds": .number(Double(durationSeconds))]
        if let relatedTaskID { body["related_task_id"] = .string(relatedTaskID) }
        return try StudySession(json: await client.request(.post, path: "study/sessions", body: .object(body)))
    }
    public func pause(id: String) async throws -> StudySession { try StudySession(json: await client.request(.post, path: "study/sessions/\(id.pathComponent)/pause")) }
    public func resume(id: String) async throws -> StudySession { try StudySession(json: await client.request(.post, path: "study/sessions/\(id.pathComponent)/resume")) }
    public func finish(id: String, report: String, tags: [String], behaviorSummary: JSONValue? = nil) async throws -> StudySession {
        var body: [String: JSONValue] = ["self_report": report.nonEmpty.map(JSONValue.string) ?? .null, "self_report_tags": .array(tags.map(JSONValue.string))]
        if let behaviorSummary { body["behavior_summary"] = behaviorSummary }
        do { return try StudySession(json: await client.request(.post, path: "study/sessions/\(id.pathComponent)/finish", body: .object(body))) }
        catch {
            if !Task.isCancelled, error is URLError || (error as? APIError)?.statusCode ?? 0 >= 500,
               let recovered = try? await session(id: id), recovered.status == "completed" { return recovered }
            throw error
        }
    }
    public func breakdown(goal: String, taskID: String? = nil) async throws -> JSONValue {
        var body: [String: JSONValue] = ["goal": .string(goal)]
        if let taskID { body["task_id"] = .string(taskID) }
        return try await client.request(.post, path: "study/task-breakdown", body: .object(body))
    }
    public func createVoice() async throws -> VoiceEndpoint {
        let result = try await client.request(.post, path: "focus/realtime-voice/sessions")
        guard let session = await client.currentSession else { throw CancellationError() }
        return try VoiceEndpoint(baseURL: client.baseURL, sessionID: result["session_id"].text, path: result["websocket_path"].text, accessToken: session.tokens.accessToken)
    }
    public func stopVoice(id: String) async throws {
        do { _ = try await client.request(.delete, path: "focus/realtime-voice/sessions/\(id.pathComponent)") }
        catch let error as APIError where error.statusCode == 404 { return }
    }
}
