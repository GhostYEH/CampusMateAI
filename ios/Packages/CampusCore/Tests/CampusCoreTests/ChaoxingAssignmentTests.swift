import Foundation
import Testing
@testable import CampusCore

@Suite("Chaoxing assignment review")
struct ChaoxingAssignmentTests {
    @Test func contentKeepsOnlyGradingFlagsAndQuestionText() throws {
        let content = try ChaoxingAssignmentContent(json: [
            "task_id": "task-1",
            "course_id": "course-1",
            "status": "ended",
            "available": true,
            "current": true,
            "can_generate": true,
            "can_generate_wrong": true,
            "results_available": true,
            "results_complete": false,
            "graded_count": 2,
            "wrong_count": 1,
            "questions": [
                ["number": 1, "stem": "题干一", "options": ["A. 甲", "B. 乙"], "is_correct": true],
                ["number": 2, "stem": "题干二", "options": ["A. 甲", "B. 乙"], "is_correct": false],
                ["number": 3, "stem": "题干三", "options": [], "is_correct": .null],
            ],
        ])
        #expect(content.taskID == "task-1")
        #expect(content.courseID == "course-1")
        #expect(content.hasPartialResults)
        #expect(content.gradedCount == 2)
        #expect(content.wrongCount == 1)
        #expect(content.questions.count == 3)
        #expect(content.questions[0].isCorrect == true)
        #expect(content.questions[1].isCorrect == false)
        #expect(content.questions[2].isCorrect == nil)
    }

    @Test func lessonExposesTransferQuestionHintsAndAnalysisWithoutRetry() throws {
        let lesson = try ChaoxingLesson(document: [
            "title": "错题变式讲解",
            "scenes": [
                [
                    "id": "slide-1",
                    "type": "slide",
                    "title": "方法回顾",
                    "content": [
                        "slide": [
                            "sections": [
                                ["heading": "核心思路", "bullets": ["先识别题型", "再列条件"]],
                            ],
                            "body": "先看方法，再做练习。",
                        ],
                    ],
                ],
                [
                    "id": "quiz-1",
                    "type": "quiz",
                    "title": "变式练习",
                    "content": [
                        "questions": [
                            [
                                "id": "q1",
                                "type": "single",
                                "question": "下列哪一步先做？",
                                "options": [["label": "先整理条件", "value": "A"], ["label": "直接背答案", "value": "B"]],
                                "answer": ["A"],
                                "analysis": "先整理条件，再代入计算。",
                                "hints": ["注意题目给了两个约束"],
                                "exerciseRole": "transfer",
                                "sourceQuestionNumber": 3,
                            ],
                            [
                                "id": "q2",
                                "type": "short_answer",
                                "question": "说明理由",
                                "answer": [],
                                "analysis": "参考思路",
                            ],
                        ],
                    ],
                ],
            ],
        ])
        #expect(lesson.title == "错题变式讲解")
        #expect(lesson.quizCount == 1)
        #expect(lesson.scenes.count == 2)
        #expect(lesson.scenes[0].blocks.first?.heading == "核心思路")
        #expect(lesson.scenes[0].blocks.first?.bullets == ["先识别题型", "再列条件"])
        #expect(lesson.scenes[0].body == "先看方法，再做练习。")

        let question = lesson.scenes[1].questions[0]
        #expect(question.isChoice)
        #expect(!question.isMultiple)
        #expect(question.answer == ["A"])
        #expect(question.hints == ["注意题目给了两个约束"])
        #expect(question.exerciseRole == "transfer")
        #expect(question.roleLabel == "变式练习")
        #expect(question.sourceNumber == 3)
        #expect(question.analysis == "先整理条件，再代入计算。")
        #expect(!lesson.scenes[1].questions[1].isChoice)
        #expect(lesson.scenes[1].questions[1].answer.isEmpty)
    }

    @Test func serviceUsesManagedRoutesAndScopeOnlyBody() async throws {
        let recorder = AssignmentRequestRecorder()
        let client = APIClient(baseURL: URL(string: "https://example.com/api/v1/")!) { request in
            await recorder.respond(request)
        }
        await client.restore(Session(tokens: TokenPair(accessToken: "a", refreshToken: "r"),
                                     user: UserProfile(id: "u", username: "u")))
        let service = ChaoxingAssignmentService(client: client)
        _ = try await service.content(taskID: "task /1")
        _ = try await service.generate(taskID: "task /1", scope: "wrong")
        _ = try await service.job(courseID: "course /1", jobID: "job /1")
        _ = try await service.retryJob(courseID: "course /1", jobID: "job /1")
        _ = try await service.stages(courseID: "course /1", workspaceID: "ws /1")
        _ = try await service.stage(courseID: "course /1", workspaceID: "ws /1", stageID: "stage /1")

        let records = await recorder.records
        #expect(records.map(\.path) == [
            "chaoxing/assignments/task%20%2F1/content",
            "chaoxing/assignments/task%20%2F1/classroom",
            "courses/course%20%2F1/jobs/job%20%2F1",
            "courses/course%20%2F1/jobs/job%20%2F1/retry",
            "courses/course%20%2F1/workspaces/ws%20%2F1/stages",
            "courses/course%20%2F1/workspaces/ws%20%2F1/stages/stage%20%2F1",
        ])
        #expect(records[1].method == "POST")
        #expect(records[1].scope == "wrong")
    }

    @Test func latestStageUsesUpdatedAtAndPresentationMapsAssignmentCodes() async throws {
        let client = APIClient(baseURL: URL(string: "https://example.com/api/v1/")!) { request in
            let body = Data("""
            {"items":[
              {"id":"stage-old","updated_at":"2026-01-01T00:00:00+00:00"},
              {"id":"stage-new","updated_at":"2026-10-01T00:00:00+00:00"}
            ]}
            """.utf8)
            _ = request
            return HTTPResponse(data: body, statusCode: 200)
        }
        await client.restore(Session(tokens: TokenPair(accessToken: "a", refreshToken: "r"),
                                     user: UserProfile(id: "u", username: "u")))
        let service = ChaoxingAssignmentService(client: client)
        let latest = try await service.latestStageID(courseID: "c", workspaceID: "w")
        #expect(latest == "stage-new")

        let error = APIError(statusCode: 409, code: "CONFLICT", message: "assignment_results_unavailable")
        #expect(ChaoxingAssignmentPresentation.message(for: error, fallback: "fallback").contains("逐题批改"))
        let ended = APIError(statusCode: 409, code: "CONFLICT", message: "assignment_not_ended")
        #expect(ChaoxingAssignmentPresentation.message(for: ended, fallback: "fallback").contains("截止"))
    }
}

private actor AssignmentRequestRecorder {
    struct Record: Sendable {
        let path: String
        let method: String
        let scope: String?
    }
    var records: [Record] = []

    func respond(_ request: URLRequest) async -> HTTPResponse {
        let absolute = request.url?.absoluteString ?? ""
        let path = (absolute.components(separatedBy: "/api/v1/").last ?? "")
            .components(separatedBy: "?").first ?? ""
        let body = (try? JSONValue(data: request.httpBody ?? Data())) ?? .null
        records.append(Record(path: path, method: request.httpMethod ?? "GET", scope: body["scope"].string))
        let payload: String
        if path.hasSuffix("/content") {
            payload = #"{"task_id":"task-1","course_id":"course-1","available":true,"can_generate":true}"#
        } else if path.hasSuffix("/classroom") {
            payload = #"{"task_id":"task-1","course_id":"course-1","workspace_id":"ws-1","job":{"id":"job-1","status":"queued","progress":0}}"#
        } else if path.contains("/jobs/") {
            payload = #"{"id":"job-1","status":"completed","progress":100}"#
        } else if path.hasSuffix("/stages") {
            payload = #"{"items":[{"id":"stage-1","updated_at":"2026-10-01T00:00:00+00:00"}]}"#
        } else {
            payload = #"{"id":"stage-1","document":{"scenes":[{"id":"scene-1","type":"quiz","content":{"questions":[]}}]}}"#
        }
        return HTTPResponse(data: Data(payload.utf8), statusCode: 200)
    }
}
