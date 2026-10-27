import Foundation
import Testing
@testable import CampusCore

@Suite("Learning business contracts")
struct LearningContractTests {
    @Test func upstreamAssignmentsCannotBeModified() throws {
        let item = try TaskItem(json: ["id": "upstream", "title": "作业", "source": "chaoxing", "status": "pending"])
        #expect(!item.isEditable)
        #expect(!item.canChangeCompletion)
        let plan = try TaskItem(json: ["id": "plan", "title": "计划", "source": "learning_plan", "status": "pending"])
        #expect(plan.isEditable)
        #expect(plan.canChangeCompletion)
    }

    @Test func readonlyMutationNeverReachesServer() async throws {
        let client = APIClient(baseURL: URL(string: "https://example.com/api/v1/")!) { _ in
            Issue.record("Read-only task must never be submitted")
            return HTTPResponse(data: Data(), statusCode: 204)
        }
        let item = try TaskItem(json: ["id": "upstream", "title": "作业", "source": "chaoxing", "status": "pending"])
        do {
            _ = try await LearningService(client: client).setCompleted(item, completed: true)
            Issue.record("Read-only mutation must fail")
        } catch let error as APIError { #expect(error.code == "READ_ONLY_SOURCE") }
    }

    @Test func preservesPageMetadataAndStableIDs() throws {
        let page = try RecordPage(json: ["items": [["id": "same", "title": "标题"]], "page": 2, "page_size": 1, "total": 3, "has_more": true])
        #expect(page.items.first?["id"].text == "same")
        #expect(page.hasMore)
        #expect(page.nextPage == 3)
        let last = try RecordPage(json: ["items": [], "page": 3, "has_more": false])
        #expect(!last.hasMore)
        #expect(throws: (any Error).self) { try RecordPage(json: ["unexpected": "invalid"]) }
    }

    @Test func draftClearsDeadlineWithoutSendingStatus() throws {
        let draft = TaskDraft(title: "准备复习", description: "章节一", deadline: nil, priority: "medium")
        #expect(draft.body["deadline"] == .null)
        #expect(draft.body.object?["status"] == nil)
        #expect(draft.body["title"].text == "准备复习")
    }

    @Test func examUpdatesIncludeRequiredFields() throws {
        let exam = ExamDraft(courseName: "数学", examDate: "2026-11-01", startTime: "09:00", endTime: "11:00", location: "教室", notes: "", reminderEnabled: true)
        #expect(exam.body["course_name"].text == "数学")
        #expect(exam.body["exam_date"].text == "2026-11-01")
        #expect(exam.body["reminder_enabled"].bool == true)
    }

    @Test func separatesThirdPartyReauthenticationFromAppSession() async throws {
        let counter = RequestCounter()
        let client = APIClient(baseURL: URL(string: "https://example.com/api/v1/")!) { request in
            await counter.record(request)
            return HTTPResponse(data: Data(#"{"code":"HTTP_ERROR","message":"reauth_required"}"#.utf8), statusCode: 401)
        }
        await client.restore(Session(tokens: TokenPair(accessToken: "valid", refreshToken: "refresh"), user: UserProfile(id: "u1", username: "student")))
        do { _ = try await client.request(.post, path: "chaoxing/sync") } catch { }
        #expect(await client.currentSession?.user.id == "u1")
        #expect(await counter.paths == ["/api/v1/chaoxing/sync"])
    }

    @Test func parsesFractionalAndPlainAPIDates() throws {
        #expect(APIDate.parse("2026-10-27T08:00:00+08:00") != nil)
        #expect(APIDate.parse("2026-10-27T08:00:00.123+08:00") != nil)
        #expect(APIDate.parse("not-a-date") == nil)
    }

    @Test func fileFavoriteSetsExplicitDesiredState() async throws {
        let client = APIClient(baseURL: URL(string: "https://example.com/api/v1/")!) { request in
            let body = try JSONValue(data: request.httpBody ?? Data())
            #expect(body["favorite"].bool == false)
            return HTTPResponse(data: Data(#"{"id":"f1","is_favorite":false}"#.utf8), statusCode: 200)
        }
        await client.restore(Session(tokens: TokenPair(accessToken: "access", refreshToken: "refresh"), user: UserProfile(id: "u1", username: "u1")))
        _ = try await PersonalService(client: client).favoriteFile(id: "f1", favorite: false)
    }
}

private actor RequestCounter {
    private(set) var paths: [String] = []
    func record(_ request: URLRequest) { paths.append(request.url?.path ?? "") }
}
