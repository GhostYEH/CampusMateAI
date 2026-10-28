import Foundation
import Testing
@testable import CampusCore

@Suite("Conversation and focus lifecycle")
struct ConversationAndFocusTests {
    @Test func finalChatAnswerReplacesDeltasAndLateTokensAreIgnored() throws {
        var reply = ChatReply()
        try reply.consume(SSEEvent(event: "chunk", data: #"{"text":"你"}"#))
        try reply.consume(SSEEvent(event: "chunk", data: #"{"text":"好"}"#))
        try reply.consume(SSEEvent(event: "done", data: #"{"answer":"你好！","conversation_id":"conv1","mode":"llm","warnings":["说明"]}"#))
        try reply.consume(SSEEvent(event: "chunk", data: #"{"text":"late"}"#))
        #expect(reply.text == "你好！")
        #expect(reply.conversationID == "conv1")
        #expect(reply.isFinished)
        #expect(reply.warnings == ["说明"])
    }

    @Test func streamErrorsPreserveAlreadyReceivedText() throws {
        var reply = ChatReply()
        try reply.consume(SSEEvent(event: "chunk", data: #"{"text":"已收到的文字"}"#))
        #expect(throws: (any Error).self) { try reply.consume(SSEEvent(event: "error", data: #"{"code":"RAG_ERROR","message":"服务中断"}"#)) }
        #expect(reply.text == "已收到的文字")
    }

    @Test func pausedAndFinishedSessionsUseAuthoritativeTime() throws {
        let paused = try StudySession(json: ["id": "s", "started_at": "1970-01-01T00:01:40Z", "paused_at": "1970-01-01T00:03:10Z", "pause_seconds": 10, "status": "paused"])
        #expect(paused.elapsed(at: Date(timeIntervalSince1970: 500)) == 80)
        let finished = try StudySession(json: ["id": "s", "started_at": "1970-01-01T00:01:40Z", "status": "completed", "duration_seconds": 99])
        #expect(finished.elapsed(at: Date(timeIntervalSince1970: 900)) == 99)
    }

    @Test func finishingAfterTimeoutReconcilesWithoutRepeatingMutation() async throws {
        let server = FinishRecoveryServer()
        let client = APIClient(baseURL: URL(string: "https://example.com/api/v1/")!) { request in try await server.respond(request) }
        await client.restore(Self.session("u1"))
        let result = try await StudyService(client: client).finish(id: "s", report: "有收获", tags: [])
        #expect(result.status == "completed")
        #expect(await server.finishCalls == 1)
    }

    @Test func realtimeBargeInRejectsCancelledAndDuplicateResponses() {
        var state = RealtimeTranscript()
        state.consume(["type": "user_transcript_done", "text": "第一个问题", "event_id": "u1"])
        state.consume(["type": "ai_text_delta", "text": "旧回复", "response_id": "r1", "event_id": "a1"])
        state.consume(["type": "user_speech_started", "response_id": "r1"])
        state.consume(["type": "user_transcript_done", "text": "新的问题", "event_id": "u2"])
        state.consume(["type": "ai_text_delta", "text": "不应出现", "response_id": "r1", "event_id": "a2"])
        #expect(state.assistantText.isEmpty)
        state.consume(["type": "ai_text_delta", "text": "新回复", "response_id": "r2", "event_id": "a3"])
        state.consume(["type": "ai_text_delta", "text": "新回复", "response_id": "r2", "event_id": "a3"])
        #expect(state.assistantText == "新回复")
    }

    @Test func voiceEndpointCannotChangeOriginOrSession() throws {
        let value = try VoiceEndpoint(baseURL: URL(string: "https://example.com/api/v1/")!, sessionID: "voice1", path: "/focus/realtime-voice/ws/voice1", accessToken: "a.b.c")
        #expect(value.url.scheme == "wss")
        #expect(value.url.path == "/api/v1/focus/realtime-voice/ws/voice1")
        #expect(throws: (any Error).self) { try VoiceEndpoint(baseURL: URL(string: "https://example.com/api/v1/")!, sessionID: "voice1", path: "https://evil.example/voice1", accessToken: "a.b.c") }
    }

    @Test func authenticatedSSEDeliversProtocolEvents() async throws {
        let client = APIClient(baseURL: URL(string: "https://example.com/api/v1/")!, transport: nil, streamTransport: { _ in
            HTTPStreamResponse(statusCode: 200, headers: ["Content-Type": "text/event-stream"], chunks: AsyncThrowingStream { continuation in
                continuation.yield(Data("event: chunk\ndata: {\"text\":\"流式\"}\n\nevent: done\ndata: {\"answer\":\"流式回复\"}\n\n".utf8)); continuation.finish()
            })
        })
        await client.restore(Self.session("u1"))
        var reply = ChatReply()
        for try await event in try await client.events(.post, path: "counselor/chat", body: ["message": "你好", "stream": true]) { try reply.consume(event) }
        #expect(reply.text == "流式回复")
        #expect(reply.isFinished)
    }

    private static func session(_ id: String) -> Session { Session(tokens: TokenPair(accessToken: "access", refreshToken: "refresh"), user: UserProfile(id: id, username: id)) }
}

private actor FinishRecoveryServer {
    private(set) var finishCalls = 0
    func respond(_ request: URLRequest) throws -> HTTPResponse {
        if request.httpMethod == "POST" { finishCalls += 1; throw URLError(.timedOut) }
        return HTTPResponse(data: Data(#"{"id":"s","started_at":"1970-01-01T00:01:40Z","status":"completed","duration_seconds":100}"#.utf8), statusCode: 200)
    }
}
