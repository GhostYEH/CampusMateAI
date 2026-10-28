import Foundation

public struct ChatReply: Sendable {
    public private(set) var text = ""
    public private(set) var conversationID: String?
    public private(set) var mode: String?
    public private(set) var warnings: [String] = []
    public private(set) var sources: [JSONValue] = []
    public private(set) var suggestedActions: [JSONValue] = []
    public private(set) var isFinished = false
    public init() { }
    public mutating func consume(_ event: SSEEvent) throws {
        guard !isFinished else { return }
        if event.data == "[DONE]" { isFinished = true; return }
        let value = event.json
        switch event.event {
        case "chunk": text += value["text"].text; mode = value["mode"].string ?? mode
        case "sources": sources = value["sources"].items
        case "done":
            guard value.object != nil else { throw APIError(code: "INVALID_STREAM", message: "收到不完整的回复，请重试。") }
            if let answer = value["answer"].string { text = answer }
            conversationID = value["conversation_id"].string
            mode = value["mode"].string ?? mode
            warnings = (value["warnings"].items + value["context_warnings"].items).compactMap(\.string)
            if value["sources"].array != nil { sources = value["sources"].items }
            suggestedActions = value["suggested_actions"].items
            isFinished = true
        case "error":
            isFinished = true
            throw APIError(code: value["code"].string ?? "STREAM_ERROR", message: value["message"].string ?? "回复中断，请重试。")
        default: break
        }
    }
}

public struct ChatMessage: Codable, Sendable, Identifiable, Equatable {
    public let id: UUID
    public let role: String
    public var text: String
    public var mode: String?
    public var warnings: [String]
    public var sources: [JSONValue]
    public var suggestedActions: [JSONValue]
    public var interrupted: Bool
    public init(id: UUID = UUID(), role: String, text: String = "", mode: String? = nil, warnings: [String] = [], sources: [JSONValue] = [], suggestedActions: [JSONValue] = [], interrupted: Bool = false) {
        self.id = id; self.role = role; self.text = text; self.mode = mode
        self.warnings = warnings; self.sources = sources; self.suggestedActions = suggestedActions; self.interrupted = interrupted
    }
}

public struct RealtimeTranscript: Sendable {
    public private(set) var userText = ""
    public private(set) var assistantText = ""
    public private(set) var phase = "idle"
    public private(set) var activeResponseID: String?
    private var userDelta = ""
    private var acceptsResponse = false
    private var cancelledResponses: Set<String> = []
    private var eventIDs: [String] = []
    public init() { }

    public mutating func consume(_ value: JSONValue) {
        if let id = value["event_id"].string?.nonEmpty {
            guard !eventIDs.contains(id) else { return }
            eventIDs.append(id)
            if eventIDs.count > 512 { eventIDs.removeFirst(eventIDs.count - 512) }
        }
        switch value["type"].text {
        case "state": phase = value["state"].text
        case "user_transcript_delta": userDelta += value["text"].text; userText = userDelta
        case "user_transcript_done":
            userText = value["text"].string?.nonEmpty ?? userDelta
            userDelta = ""; assistantText = ""; activeResponseID = nil
            acceptsResponse = !userText.isEmpty; phase = "thinking"
        case "user_speech_started":
            if let id = value["response_id"].string?.nonEmpty { cancelledResponses.insert(id) }
            cancelResponse()
        case "ai_text_delta", "ai_text_done":
            guard acceptsResponse, let id = value["response_id"].string?.nonEmpty,
                  !cancelledResponses.contains(id), activeResponseID == nil || activeResponseID == id else { return }
            activeResponseID = id
            if value["type"].text == "ai_text_done" { assistantText = value["text"].string?.nonEmpty ?? assistantText }
            else { assistantText += value["text"].text }
        case "error": phase = "error"
        case "session_closed": phase = "idle"; acceptsResponse = false
        default: break
        }
    }
    public mutating func cancelResponse() {
        if let activeResponseID { cancelledResponses.insert(activeResponseID) }
        if cancelledResponses.count > 256 { cancelledResponses = Set(cancelledResponses.suffix(128)) }
        activeResponseID = nil; assistantText = ""; acceptsResponse = false; phase = "listening"
    }
}

public struct VoiceEndpoint: Sendable {
    public let sessionID: String
    public let url: URL
    public init(baseURL: URL, sessionID: String, path: String, accessToken: String) throws {
        let tail = "focus/realtime-voice/ws/\(sessionID.pathComponent)"
        guard [tail, "/" + tail, "/api/v1/" + tail].contains(path), !accessToken.isEmpty,
              var parts = URLComponents(url: baseURL.appendingPathComponent(tail), resolvingAgainstBaseURL: true),
              ["https", "http"].contains(parts.scheme ?? ""), parts.user == nil, parts.password == nil else {
            throw APIError(code: "INVALID_VOICE_ENDPOINT", message: "语音会话地址无效。")
        }
        parts.scheme = parts.scheme == "https" ? "wss" : "ws"
        parts.queryItems = [URLQueryItem(name: "access_token", value: accessToken)]
        guard let url = parts.url else { throw APIError(code: "INVALID_VOICE_ENDPOINT", message: "语音会话地址无效。") }
        self.sessionID = sessionID; self.url = url
    }
}
