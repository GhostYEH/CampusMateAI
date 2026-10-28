import Foundation
import Testing
@testable import CampusCore

@Suite("Reminder eligibility and complete list loading")
struct ReminderAndPaginationTests {
    private let now = Date(timeIntervalSince1970: 1_800_000_000)

    @Test func remindersExcludeCompletedTasksAndDisabledExams() throws {
        func task(_ id: String, status: String, source: String = "personal") throws -> TaskItem {
            try TaskItem(json: ["id": .string(id), "title": "任务", "status": .string(status), "source": .string(source), "deadline": .string(APIDate.string(now.addingTimeInterval(7200)))])
        }
        let tasks = try [task("pending", status: "pending"), task("done", status: "completed"), task("remote", status: "pending", source: "chaoxing")]
        let exams: [JSONValue] = [["id": "disabled", "course_name": "考试", "exam_date": "2027-12-01", "start_time": "09:00", "reminder_enabled": false]]
        let plan = ReminderPlan(tasks: tasks, exams: exams, now: now)
        #expect(plan.entries.map(\.id) == ["task.pending"])
    }

    @Test func systemLimitKeepsEarliestAcrossBothKindsAndHonorsTaskLeadTime() throws {
        let tasks = try (0..<80).map { index in
            try TaskItem(json: ["id": .string(String(index)), "title": "任务", "status": "pending", "deadline": .string(APIDate.string(now.addingTimeInterval(Double(80 - index) * 3600))), "reminder_minutes": 15])
        }
        var calendar = Calendar(identifier: .gregorian)
        calendar.timeZone = TimeZone(secondsFromGMT: 0)!
        let start = APIDate.string(now.addingTimeInterval(3600))
        let exams: [JSONValue] = [["id": "soon", "course_name": "近期考试", "exam_date": .string(String(start.prefix(10))), "start_time": .string(String(start.dropFirst(11).prefix(5)))]]
        let plan = ReminderPlan(tasks: tasks, exams: exams, now: now, calendar: calendar)
        #expect(plan.entries.count == 60)
        #expect(plan.entries.first?.id == "exam.soon")
        #expect(plan.entries[1].id == "task.79")
        #expect(plan.entries[1].fire == now.addingTimeInterval(2700))
    }

    @Test func examDateUsesGregorianDateWithTheUsersTimeZone() throws {
        var calendar = Calendar(identifier: .buddhist)
        calendar.timeZone = TimeZone(secondsFromGMT: 8 * 3600)!
        let exams: [JSONValue] = [["id": "calendar", "course_name": "考试", "exam_date": "2027-12-01", "start_time": "09:00"]]
        let entry = try #require(ReminderPlan(tasks: [], exams: exams, now: now, calendar: calendar).entries.first)
        #expect(entry.fire == APIDate.parse("2027-12-01T00:00:00Z"))
    }

    @Test func reminderWithinLeadWindowStillArrivesBeforeDeadline() throws {
        let task = try TaskItem(json: ["id": "soon", "title": "即将截止", "status": "pending", "deadline": .string(APIDate.string(now.addingTimeInterval(300)))])
        #expect(ReminderPlan(tasks: [task], exams: [], now: now).entries.first?.fire == now.addingTimeInterval(1))
        let first = ReminderPlan(tasks: [task], exams: [], now: now).entries.first
        let refreshed = ReminderPlan(tasks: [task], exams: [], now: now.addingTimeInterval(60)).entries.first
        #expect(first?.eventKey == refreshed?.eventKey, "Refreshing during the lead window must not create another reminder event")
    }

    @Test func allRecordsIncludesLaterPagesAndStopsRepeatedPages() async throws {
        let recorder = PageServer()
        let client = APIClient(baseURL: URL(string: "https://example.com/api/v1/")!) { request in try await recorder.respond(request) }
        await client.restore(Session(tokens: TokenPair(accessToken: "a", refreshToken: "r"), user: UserProfile(id: "u", username: "u")))
        let result = try await client.allRecords(path: "tasks")
        #expect(result.map { $0["id"].text } == ["first", "later"])
        #expect(await recorder.calls == 3)
    }
}

private actor PageServer {
    var calls = 0
    func respond(_ request: URLRequest) throws -> HTTPResponse {
        calls += 1
        let page = URLComponents(url: request.url!, resolvingAgainstBaseURL: false)?.queryItems?.first { $0.name == "page" }?.value ?? "1"
        let body: JSONValue = ["items": [["id": .string(page == "1" ? "first" : "later")]], "page": .number(Double(page) ?? 1), "has_more": true]
        return HTTPResponse(data: try body.encoded(), statusCode: 200)
    }
}
