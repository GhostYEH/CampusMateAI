import Foundation
import Testing
@testable import CampusCore

@Suite("CampusCore contracts")
struct CoreContractTests {
    @Test func normalizesServerAddressAndRejectsCredentials() throws {
        let configuration = try ServerConfiguration("http://localhost:8000", allowsInsecureHTTP: true)
        #expect(configuration.baseURL.absoluteString == "http://localhost:8000/api/v1/")
        #expect(throws: (any Error).self) { try ServerConfiguration("https://name:secret@example.com") }
        #expect(throws: (any Error).self) { try ServerConfiguration("http://example.com") }
        #expect(throws: (any Error).self) { try ServerConfiguration("https://example.com?token=bad") }
    }

    @Test func parsesSSEAcrossUTF8AndCRLFBoundaries() {
        var parser = SSEParser()
        let bytes = Array("event: token\r\nid: 7\r\ndata: {\"text\":\"你好\"}\r\n\r\n".utf8)
        var events: [SSEEvent] = []
        for byte in bytes { events += parser.feed(Data([byte])) }
        #expect(events.count == 1)
        #expect(events.first?.event == "token")
        #expect(events.first?.id == "7")
        #expect(events.first?.data == "{\"text\":\"你好\"}")
    }

    @Test func parsesMultilineSSEAndIgnoresComments() {
        var parser = SSEParser()
        let events = parser.feed(Data(": heartbeat\ndata: first\ndata: second\n\ndata: [DONE]\n\n".utf8))
        #expect(events.map(\.data) == ["first\nsecond", "[DONE]"])
    }

    @Test func focusClockSurvivesBackgroundAndPauses() {
        let start = Date(timeIntervalSince1970: 100)
        var clock = FocusClock(startedAt: start)
        #expect(clock.elapsed(at: start.addingTimeInterval(90)) == 90)
        clock.pause(at: start.addingTimeInterval(90))
        #expect(clock.elapsed(at: start.addingTimeInterval(300)) == 90)
        clock.resume(at: start.addingTimeInterval(300))
        #expect(clock.elapsed(at: start.addingTimeInterval(330)) == 120)
        #expect(clock.elapsed(at: start) >= 0)
    }

    @Test func preservesBusinessErrorAndRetryAfter() async throws {
        let client = APIClient(baseURL: URL(string: "https://example.com/api/v1/")!) { _ in
            HTTPResponse(data: Data(#"{"code":"RATE_LIMITED","message":"稍后重试","request_id":"req_test"}"#.utf8), statusCode: 429, headers: ["Retry-After": "12"])
        }
        do {
            _ = try await client.request(.get, path: "health", authenticated: false)
            Issue.record("429 must fail")
        } catch let error as APIError {
            #expect(error.code == "RATE_LIMITED")
            #expect(error.statusCode == 429)
            #expect(error.retryAfter == 12)
            #expect(error.requestID == "req_test")
        }
    }

    @Test func accepts204WithoutDecodingJSON() async throws {
        let client = APIClient(baseURL: URL(string: "https://example.com/api/v1/")!) { _ in
            HTTPResponse(data: Data(), statusCode: 204)
        }
        let result = try await client.request(.delete, path: "resource", authenticated: false)
        #expect(result == .null)
    }

    @Test func rotatesTokenPairOnceForConcurrent401s() async throws {
        let server = RefreshServer()
        let client = APIClient(baseURL: URL(string: "https://example.com/api/v1/")!) { request in
            await server.respond(request)
        }
        await client.restore(Session(tokens: TokenPair(accessToken: "old", refreshToken: "refresh-old"), user: UserProfile(id: "u1", username: "student")))
        async let first = client.request(.get, path: "courses")
        async let second = client.request(.get, path: "tasks")
        _ = try await (first, second)
        #expect(await server.refreshCount == 1)
        #expect(await client.currentSession?.tokens.refreshToken == "refresh-new")
        #expect(await client.currentSession?.tokens.accessToken == "new")
    }

    @Test func discardsResponseFromPreviousAccount() async throws {
        let server = SuspendedServer()
        let client = APIClient(baseURL: URL(string: "https://example.com/api/v1/")!) { request in
            await server.respond(request)
        }
        await client.restore(Session(tokens: TokenPair(accessToken: "a", refreshToken: "ra"), user: UserProfile(id: "a", username: "a")))
        let request = Task { try await client.request(.get, path: "tasks") }
        await server.waitUntilStarted()
        await client.restore(Session(tokens: TokenPair(accessToken: "b", refreshToken: "rb"), user: UserProfile(id: "b", username: "b")))
        await server.complete()
        do {
            _ = try await request.value
            Issue.record("Old-account response must be cancelled")
        } catch is CancellationError { }
        #expect(await client.currentSession?.user.id == "b")
    }

    @Test func refusesAbsoluteRequestPaths() async {
        let client = APIClient(baseURL: URL(string: "https://example.com/api/v1/")!) { _ in
            Issue.record("Untrusted URL must never reach transport")
            return HTTPResponse(data: Data(), statusCode: 200)
        }
        do {
            _ = try await client.request(.get, path: "https://evil.example/collect", authenticated: false)
            Issue.record("Absolute paths must fail")
        } catch { }
    }
}

private actor RefreshServer {
    private(set) var refreshCount = 0

    func respond(_ request: URLRequest) async -> HTTPResponse {
        if request.url?.path.hasSuffix("auth/refresh") == true {
            refreshCount += 1
            try? await Task.sleep(for: .milliseconds(30))
            return HTTPResponse(data: Data(#"{"access_token":"new","refresh_token":"refresh-new"}"#.utf8), statusCode: 200)
        }
        if request.value(forHTTPHeaderField: "Authorization") == "Bearer old" {
            return HTTPResponse(data: Data(#"{"code":"UNAUTHORIZED","message":"expired"}"#.utf8), statusCode: 401)
        }
        return HTTPResponse(data: Data(#"{"items":[]}"#.utf8), statusCode: 200)
    }
}

private actor SuspendedServer {
    private var continuation: CheckedContinuation<HTTPResponse, Never>?
    private var started = false

    func respond(_ request: URLRequest) async -> HTTPResponse {
        started = true
        return await withCheckedContinuation { continuation = $0 }
    }

    func waitUntilStarted() async {
        while !started { await Task.yield() }
    }

    func complete() {
        continuation?.resume(returning: HTTPResponse(data: Data(#"{"items":[{"id":"old"}]}"#.utf8), statusCode: 200))
        continuation = nil
    }
}
