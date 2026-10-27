import Foundation
import Testing
@testable import CampusCore

/// Opt-in integration uses only the disposable loopback validation server, never a configured user service.
@Suite("Disposable backend integration", .enabled(if: ProcessInfo.processInfo.environment["CAMPUS_RUN_LOCAL_INTEGRATION"] == "1"))
struct LiveBackendTests {
    @Test func realAuthenticationTaskAndExamLifecycle() async throws {
        let client = APIClient(baseURL: URL(string: "http://127.0.0.1:18927/api/v1/")!)
        let username = "ios_" + UUID().uuidString.replacingOccurrences(of: "-", with: "").prefix(18)
        let password = UUID().uuidString + "aA!"
        _ = try await client.request(.post, path: "auth/register", body: ["username": .string(username), "password": .string(password), "display_name": "iOS 集成验证"], authenticated: false)
        let session = try await client.login(username: username, password: password)
        #expect(!session.user.id.isEmpty)
        let download = try await client.download(path: "health")
        let downloadedJSON = try JSONValue(data: Data(contentsOf: download.url))
        #expect(downloadedJSON["status"].text == "ok")
        try FileManager.default.removeItem(at: download.url)
        let service = LearningService(client: client)
        let created = try await service.saveTask(TaskDraft(title: "原生待办验证", description: "独立测试数据", priority: "medium"))
        #expect(created.title == "原生待办验证")
        let list = try await service.tasks()
        #expect(list.items.contains { $0["id"].text == created.id })
        let completed = try await service.setCompleted(created, completed: true)
        #expect(completed.isCompleted)
        let restored = try await service.setCompleted(completed, completed: false)
        #expect(!restored.isCompleted)
        _ = try await service.saveTask(TaskDraft(title: "已修改的待办", priority: "high"), existing: restored)
        let fetched = try await service.task(id: created.id)
        #expect(fetched.title == "已修改的待办")
        try await service.deleteTask(fetched)
        let exam = try await service.saveExam(ExamDraft(courseName: "验证课程", examDate: "2026-11-01", startTime: "09:00", endTime: "10:00"))
        #expect(!exam["id"].text.isEmpty)
        let exams = try await service.exams()
        #expect(exams.contains { $0["id"] == exam["id"] })
        try await service.deleteExam(id: exam["id"].text)
        let agenda = try await client.request(path: "agenda/today")
        #expect(agenda["timezone"].text == "Asia/Shanghai")
        await client.logout()
        #expect(await client.currentSession == nil)
    }
}
