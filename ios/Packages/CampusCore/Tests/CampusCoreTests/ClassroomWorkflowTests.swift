import Foundation
import Testing
@testable import CampusCore

@Suite("Classroom and governed workflows")
struct ClassroomWorkflowTests {
    @Test func personalClassroomCannotBecomeAManagedCourse() throws {
        #expect(ClassroomScope.personal.path == "self-classroom")
        #expect(try ClassroomScope.course("course /1").validatedPath() == "courses/course%20%2F1/interactive-classroom")
        #expect(throws: (any Error).self) { try ClassroomScope.course("__self_study__").validatedPath() }
    }
    @Test func readyClassroomStillRequiresAnExplicitTrustedEmbedOrigin() throws {
        let session: JSONValue = ["session_id": "s", "status": "succeeded", "url": "https://class.example/play/s"]
        #expect(ClassroomPlayback.validURL(session: session, status: ["browser_embed_available": true, "embed_origin": "https://class.example"]) != nil)
        #expect(ClassroomPlayback.validURL(session: session, status: ["browser_embed_available": true, "embed_origin": "https://class.example.evil"]) == nil)
        #expect(ClassroomPlayback.validURL(session: session, status: ["browser_embed_available": false, "embed_origin": "https://class.example"]) == nil)
        #expect(ClassroomPlayback.validURL(session: ["status": "running", "url": "https://class.example/play/s"], status: ["browser_embed_available": true, "embed_origin": "https://class.example"]) == nil)
    }
    @Test func runEventsRejectCrossRunAndGapsWithoutAdvancingResumeCursor() throws {
        var timeline = AgentTimeline(runID: "r")
        try timeline.append(["id": "e1", "sequence": 1, "run_id": "r", "summary": "已开始"])
        try timeline.append(["id": "e1", "sequence": 1, "run_id": "r"])
        #expect(timeline.events.count == 1)
        #expect(throws: (any Error).self) { try timeline.append(["id": "e3", "sequence": 3, "run_id": "r"]) }
        #expect(throws: (any Error).self) { try timeline.append(["id": "e2", "sequence": 2, "run_id": "other"]) }
        #expect(timeline.sequence == 1)
        #expect(timeline.lastEventID == "e1")
    }
    @Test func messageRetryRetainsIDButEditedMessageGetsANewIdentity() {
        var draft = RoomMessageDraft()
        let first = draft.prepare("相同消息")
        #expect(draft.prepare("相同消息")["client_id"] == first["client_id"])
        #expect(draft.prepare("修改消息")["client_id"] != first["client_id"])
        draft.didSend()
        #expect(draft.prepare("修改消息")["client_id"] != first["client_id"])
    }
    @Test func independentRunControlsUseFreshKeysWhileOneRetryKeepsItsKey() async throws {
        let server = WorkflowRequestRecorder()
        let client = APIClient(baseURL: URL(string: "https://example.com/api/v1/")!) { request in await server.respond(request) }
        await client.restore(Session(tokens: TokenPair(accessToken: "a", refreshToken: "r"), user: UserProfile(id: "u", username: "u")))
        let pending = GovernedOperation(path: "agent-runs/r/pause", body: [:])
        _ = try await pending.perform(client: client); _ = try await pending.perform(client: client)
        let next = GovernedOperation(path: "agent-runs/r/pause", body: [:]); _ = try await next.perform(client: client)
        let keys = await server.keys
        #expect(keys.count == 3); #expect(keys[0] == keys[1]); #expect(keys[1] != keys[2])
    }
    @Test func goalCreationCarriesItsKeyInTheDeclaredBodyField() async throws {
        let client = APIClient(baseURL: URL(string: "https://example.com/api/v1/")!) { request in
            let body = try JSONValue(data: request.httpBody ?? Data())
            #expect(body["idempotency_key"].text == "goal-key")
            return HTTPResponse(data: Data("{}".utf8), statusCode: 200)
        }
        await client.restore(Session(tokens: TokenPair(accessToken: "a", refreshToken: "r"), user: UserProfile(id: "u", username: "u")))
        _ = try await GovernedOperation(path: "student-goals", body: ["name": "复习", "category": "academic"], key: "goal-key", keyInBody: true).perform(client: client)
    }
}

private actor WorkflowRequestRecorder {
    var keys: [String] = []
    func respond(_ request: URLRequest) -> HTTPResponse {
        keys.append(request.value(forHTTPHeaderField: "Idempotency-Key") ?? "")
        return HTTPResponse(data: Data("{}".utf8), statusCode: 200)
    }
}
