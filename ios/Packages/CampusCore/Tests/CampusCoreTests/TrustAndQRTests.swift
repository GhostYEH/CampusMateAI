import Foundation
import Testing
@testable import CampusCore

@Suite("Trusted navigation and QR login")
struct TrustAndQRTests {
    @Test func classroomOriginsMustMatchExactly() {
        #expect(URLPolicy.isTrusted("https://class.example/player?id=1", origins: ["https://class.example"]))
        #expect(!URLPolicy.isTrusted("https://class.example.evil.test/player", origins: ["https://class.example"]))
        #expect(!URLPolicy.isTrusted("https://class.example:444/player", origins: ["https://class.example"]))
        #expect(!URLPolicy.isTrusted("https://user:password@class.example/player", origins: ["https://class.example"]))
        #expect(!URLPolicy.isTrusted("https://127.0.0.1/player", origins: ["https://127.0.0.1"]))
        #expect(!URLPolicy.isTrusted("https://192.168.1.3/player", origins: ["https://192.168.1.3"]))
        #expect(!URLPolicy.isTrusted("https://127.1/player", origins: ["https://127.1"]))
        #expect(!URLPolicy.isTrusted("https://2130706433/player", origins: ["https://2130706433"]))
        #expect(!URLPolicy.isTrusted("https://[fe90::1]/player", origins: ["https://[fe90::1]"]))
        #expect(!URLPolicy.isTrusted("https://[0:0:0:0:0:ffff:7f00:1]/player", origins: ["https://[0:0:0:0:0:ffff:7f00:1]"]))
        #expect(URLPolicy.isTrusted("https://[2606:4700:4700::1111]/player", origins: ["https://[2606:4700:4700::1111]"]))
    }

    @Test func localDebugIsExplicitAndNeverAnArbitraryOriginException() {
        #expect(!URLPolicy.isTrusted("http://127.0.0.1:3000/player", origins: ["http://127.0.0.1:3000"]))
        #expect(URLPolicy.isTrusted("http://127.0.0.1:3000/player", origins: ["http://127.0.0.1:3000"], allowLocalDebug: true))
        #expect(!URLPolicy.isTrusted("http://127.0.0.1:3000/player", origins: ["http://localhost:3000"], allowLocalDebug: true))
    }

    @Test func qrOnlyAcceptsVersionedCampusMateLoginPayload() throws {
        let sid = String(repeating: "s", count: 20)
        let token = String(repeating: "t", count: 40)
        let value = "campusmate://auth/web-login?v=1&sid=\(sid)&token=\(token)"
        let payload = try QRLoginPayload(value)
        #expect(payload.sessionID == sid)
        #expect(payload.scanToken == token)
        #expect(payload.body.object?["browser_token"] == nil)
        #expect(throws: (any Error).self) { try QRLoginPayload(value.replacingOccurrences(of: "v=1", with: "v=2")) }
        #expect(throws: (any Error).self) { try QRLoginPayload(value + "&token=another") }
        #expect(throws: (any Error).self) { try QRLoginPayload(value.replacingOccurrences(of: "campusmate://auth", with: "https://evil.example")) }
    }

    @Test func schoolSearchUsesDocumentedQParameter() async throws {
        let client = APIClient(baseURL: URL(string: "https://example.com/api/v1/")!) { request in
            let query = URLComponents(url: request.url!, resolvingAgainstBaseURL: true)?.queryItems
            #expect(query?.first(where: { $0.name == "q" })?.value == "大学")
            return HTTPResponse(data: Data("[]".utf8), statusCode: 200)
        }
        await client.restore(Session(tokens: TokenPair(accessToken: "valid", refreshToken: "refresh"), user: UserProfile(id: "u", username: "u")))
        _ = try await PersonalService(client: client).universities(query: "大学")
    }
}
