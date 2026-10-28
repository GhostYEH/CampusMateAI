import Foundation
import Testing
@testable import CampusCore

@Suite("Expression contribution upload")
struct ExpressionContributionTests {
    @Test func multipartUploadCarriesLabelConsentAndImage() async throws {
        let recorder = MultipartRecorder()
        let client = APIClient(baseURL: URL(string: "https://example.com/api/v1/")!) { request in
            await recorder.record(request)
            let response = #"{"sample_id":"sample-1","label":"HAPPY","status":"accepted","message":"ok"}"#
            return HTTPResponse(data: Data(response.utf8), statusCode: 200)
        }
        await client.restore(Session(tokens: TokenPair(accessToken: "a", refreshToken: "r"),
                                     user: UserProfile(id: "u", username: "u")))

        let result = try await PersonalService(client: client)
            .uploadExpressionSample(image: Data([0xFF, 0xD8, 0xFF]), label: "HAPPY")

        #expect(result["sample_id"].string == "sample-1")
        let request = await recorder.request
        let contentType = try #require(request?.value(forHTTPHeaderField: "Content-Type"))
        #expect(contentType.hasPrefix("multipart/form-data; boundary="))
        let body = String(decoding: try #require(request?.httpBody), as: UTF8.self)
        #expect(body.contains("name=\"label\"\r\n\r\nHAPPY\r\n"))
        #expect(body.contains("name=\"consent\"\r\n\r\ntrue\r\n"))
        #expect(body.contains("name=\"model_version\"\r\n\r\nios-client-v1\r\n"))
        #expect(body.contains("filename=\"expression.jpg\""))
    }
}

private actor MultipartRecorder {
    private(set) var request: URLRequest?

    func record(_ request: URLRequest) {
        self.request = request
    }
}
