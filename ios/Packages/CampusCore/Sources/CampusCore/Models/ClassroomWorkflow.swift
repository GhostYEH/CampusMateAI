import Foundation

public enum ClassroomScope: Codable, Sendable, Hashable {
    case personal
    case course(String)
    public var path: String {
        switch self { case .personal: return "self-classroom"; case .course(let id): return "courses/\(id.pathComponent)/interactive-classroom" }
    }
    public func validatedPath() throws -> String {
        if case .course(let id) = self, id.isEmpty || id == "__self_study__" { throw APIError(code: "CLASSROOM_SCOPE", message: "请选择真实课程，或使用自主选题入口。") }
        return path
    }
    public var materialsPath: String {
        switch self { case .personal: return "self-classroom/materials"; case .course(let id): return "courses/\(id.pathComponent)/materials" }
    }
}

public enum ClassroomPlayback {
    public static func validURL(session: JSONValue, status: JSONValue, allowLocalDebug: Bool = false) -> URL? {
        guard session["status"].text == "succeeded", session["partial"].bool != true,
              status["browser_embed_available"].bool == true,
              let origin = status["embed_origin"].string,
              let address = session["url"].string,
              URLPolicy.isTrusted(address, origins: [origin], allowLocalDebug: allowLocalDebug) else { return nil }
        return URL(string: address)
    }
}

public struct AgentTimeline: Codable, Sendable {
    public let runID: String
    public private(set) var events: [JSONValue] = []
    public private(set) var sequence = 0
    public var lastEventID: String? { events.last?["id"].string }
    public init(runID: String) { self.runID = runID }
    public mutating func append(_ event: JSONValue) throws {
        guard event["run_id"].text == runID, let next = event["sequence"].int, next > 0, event["id"].string?.nonEmpty != nil else {
            throw APIError(code: "AGENT_EVENT_INVALID", message: "运行事件身份不一致，请重新读取记录。")
        }
        guard next > sequence else { return }
        guard next == sequence + 1 else { throw APIError(code: "AGENT_EVENT_GAP", message: "运行事件缺失，正在重新读取。") }
        events.append(event); sequence = next
    }
}

/// One object represents one intent. Network retry reuses it; a new user action creates a new object.
public struct GovernedOperation: Codable, Sendable, Equatable {
    public let key: String
    public let path: String
    public let body: JSONValue
    public let keyInBody: Bool
    public init(path: String, body: JSONValue, key: String = UUID().uuidString, keyInBody: Bool = false) { self.key = key; self.path = path; self.body = body; self.keyInBody = keyInBody }
    public func perform(client: APIClient) async throws -> JSONValue {
        var requestBody = body
        if keyInBody { var fields = body.object ?? [:]; fields["idempotency_key"] = .string(key); requestBody = .object(fields) }
        return try await client.request(.post, path: path, body: requestBody, headers: ["Idempotency-Key": key])
    }
}

public struct RoomMessageDraft: Codable, Sendable {
    private var pendingText = ""
    private var clientID = UUID().uuidString
    public init() { }
    public mutating func prepare(_ text: String) -> JSONValue {
        let text = text.trimmingCharacters(in: .whitespacesAndNewlines)
        if text != pendingText { clientID = UUID().uuidString; pendingText = text }
        return ["content": .string(text), "client_id": .string(clientID)]
    }
    public mutating func didSend() { pendingText = ""; clientID = UUID().uuidString }
}
