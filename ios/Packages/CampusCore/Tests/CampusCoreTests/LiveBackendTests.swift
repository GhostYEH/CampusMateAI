import Foundation
import Testing
@testable import CampusCore

/// Opt-in integration uses only the disposable loopback validation server, never a configured user service.
@Suite("Disposable backend integration", .enabled(if: ProcessInfo.processInfo.environment["CAMPUS_RUN_LOCAL_INTEGRATION"] == "1"))
struct LiveBackendTests {
    @Test func collaborativeRoomsEnforceInvitationOwnershipAndIncrementalMessages() async throws {
        let root = URL(string: "http://127.0.0.1:18927/api/v1/")!
        let host = APIClient(baseURL: root), guest = APIClient(baseURL: root)
        let health = try await host.request(path: "health", authenticated: false)
        try #require(health["env"].text == "test")
        for client in [host, guest] {
            let username = "ios_room_" + UUID().uuidString.replacingOccurrences(of: "-", with: "").prefix(14)
            let password = UUID().uuidString + "aA!"
            _ = try await client.request(.post, path: "auth/register", body: ["username": .string(username), "password": .string(password), "display_name": "iOS 协作验证"], authenticated: false)
            _ = try await client.login(username: username, password: password)
        }
        let guestID = try #require(await guest.currentSession?.user.id)
        let control = "magicclass/learning-space"
        let room = try await host.request(.post, path: control + "/rooms/native", body: ["title": "双账号隔离验证"])
        let id = try #require(room["id"].string)
        let roomPath = control + "/rooms/" + id.pathComponent
        _ = try await host.request(.post, path: roomPath + "/invitations", body: ["uid": .string(guestID)])
        do { _ = try await guest.request(path: roomPath); Issue.record("Pending invitation must not read the room") }
        catch let error as APIError { #expect(error.statusCode == 404) }
        let invitations = try await guest.request(path: control + "/invitations")
        #expect(invitations.items.contains { $0["room_id"].text == id })
        _ = try await guest.request(.post, path: control + "/invitations/\(id.pathComponent)/accept")
        var draft = RoomMessageDraft()
        let first = draft.prepare("验证消息重试")
        let sent = try await guest.request(.post, path: roomPath + "/messages", body: first)
        let repeated = try await guest.request(.post, path: roomPath + "/messages", body: first)
        #expect(sent["id"] == repeated["id"])
        for number in 1...100 {
            _ = try await host.request(.post, path: roomPath + "/messages", body: ["content": .string("分页验证 \(number)"), "client_id": .string(UUID().uuidString)])
        }
        let page1 = try await guest.request(path: roomPath + "/messages", query: ["after":"0"])
        #expect(page1.items.count == 100)
        let last = try #require(page1.items.last?["id"].int)
        let page2 = try await guest.request(path: roomPath + "/messages", query: ["after": String(last)])
        #expect(page2.items.count == 1)
        do { _ = try await guest.request(.patch, path: roomPath + "/cursor", body: ["scene_index": 0]); Issue.record("Guest must not update host cursor") }
        catch let error as APIError { #expect(error.statusCode == 403) }
        let goalOperation = GovernedOperation(path: "student-goals", body: ["name": "复习计划验证", "category":"academic"], keyInBody: true)
        let goal = try await goalOperation.perform(client: host)
        let replayedGoal = try await goalOperation.perform(client: host)
        #expect(goal["goal"]["goal_id"] == replayedGoal["goal"]["goal_id"])
        #expect(replayedGoal["created"].bool == false)
        let goalID = try #require(goal["goal"]["goal_id"].string)
        _ = try await GovernedOperation(path: "student-goals/\(goalID.pathComponent)/progress", body: ["progress_percent": 25], keyInBody: true).perform(client: host)
        let fetchedGoal = try await host.request(path: "student-goals/" + goalID.pathComponent)
        #expect(fetchedGoal["progress_percent"].double == 25)
        let capability = try await host.request(path: "agent-runtime/capabilities")
        #expect(!capability["capabilities"].items.isEmpty)
        _ = try await host.request(.post, path: roomPath + "/leave")
        do { _ = try await guest.request(path: roomPath); Issue.record("Ended room must not remain readable") }
        catch let error as APIError { #expect([404,410].contains(error.statusCode)) }
        await host.logout(); await guest.logout()
    }

    @Test func realAuthenticationTaskAndExamLifecycle() async throws {
        let client = APIClient(baseURL: URL(string: "http://127.0.0.1:18927/api/v1/")!)
        let health = try await client.request(path: "health", authenticated: false)
        try #require(health["env"].text == "test", "Integration must use an explicitly isolated test backend")
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
        let study = StudyService(client: client)
        let focused = try await study.start(goal: "验证专注", durationSeconds: 300, mode: "QUIET", relatedTaskID: created.id)
        #expect(try await study.active()?.id == focused.id)
        #expect(try await study.pause(id: focused.id).status == "paused")
        #expect(try await study.resume(id: focused.id).status == "active")
        #expect(try await study.finish(id: focused.id, report: "有收获", tags: ["专注"]).status == "completed")
        #expect(try await study.active() == nil)
        var reply = ChatReply()
        for try await event in try await client.events(.post, path: "counselor/chat", body: ["message": "你好", "stream": true]) { try reply.consume(event) }
        #expect(reply.isFinished)
        #expect(!reply.text.isEmpty)
        try await service.deleteTask(fetched)
        let exam = try await service.saveExam(ExamDraft(courseName: "验证课程", examDate: "2026-11-01", startTime: "09:00", endTime: "10:00"))
        #expect(!exam["id"].text.isEmpty)
        let exams = try await service.exams()
        #expect(exams.contains { $0["id"] == exam["id"] })
        try await service.deleteExam(id: exam["id"].text)
        let agenda = try await client.request(path: "agenda/today")
        #expect(agenda["timezone"].text == "Asia/Shanghai")
        let universities = try await PersonalService(client: client).universities(query: "大学")
        let university = try #require(universities.items.first)
        _ = try await client.request(.put, path: "profile/university", body: ["university_id": university["id"]])
        let post = try await client.request(.post, path: "community/posts", body: ["title": "iOS 验证帖子", "content": "独立测试数据", "category": "study"])
        #expect(post["is_owner"].bool == true)
        _ = try await client.request(.post, path: "community/posts/\(post["id"].text.pathComponent)/comments", body: ["content": "验证评论"])
        let liked = try await client.request(.post, path: "community/posts/\(post["id"].text.pathComponent)/like")
        #expect(liked["liked"].bool == true)
        _ = try await client.request(.delete, path: "community/posts/\(post["id"].text.pathComponent)")
        let file = try await client.request(.post, path: "personal-hub/files", body: ["name": "验证文件.txt", "source": "iOS 测试"])
        #expect(try await PersonalService(client: client).favoriteFile(id: file["id"].text)["is_favorite"].bool == true)
        try await PersonalService(client: client).removeFile(id: file["id"].text)
        await client.logout()
        #expect(await client.currentSession == nil)
    }
}
