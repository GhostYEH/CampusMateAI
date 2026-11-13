import Foundation
import Observation
import CampusCore

/// 多人在线自习室（互相监督）的轮询与状态。
///
/// 纯 HTTP 轮询，无音视频；与 `LearningRoomModel`（共同课堂）是两套能力。
/// 契约见 docs/api/05-study.md「多人在线自习室」。用 `JSONValue` 承载动态字段，
/// 避免为临时响应新增大量仅内部使用的 Codable 结构。
@MainActor @Observable
final class StudyRoomModel {
    var identity: JSONValue = .null
    var rooms: [JSONValue] = []
    var invitations: [JSONValue] = []
    var room: JSONValue = .null
    var messages: [JSONValue] = []
    var error: String?
    var fetchedAt = Date()

    private let root = "study/rooms"
    private var after = 0
    private var beat = 0
    @ObservationIgnored private var roomBound = false

    var myUID: String { identity["uid"].text }
    var isHost: Bool { !myUID.isEmpty && room["host_uid"].text == myUID }
    var hasRoom: Bool { room["id"].string != nil }

    func refreshLists(client: APIClient) async {
        do {
            async let me = client.request(path: root + "/identity")
            async let list = client.request(path: root + "/")
            async let invites = client.request(path: root + "/invitations")
            identity = try await me
            rooms = try await list.items
            invitations = try await invites.items
            error = nil
        } catch is CancellationError {
        } catch {
            self.error = error.localizedDescription
        }
    }

    /// 每约 5 秒调用：若有打开的自习室则刷新详情与消息，并周期性保活心跳。
    func poll(client: APIClient) async {
        if hasRoom, let id = room["id"].string {
            do {
                room = try await client.request(path: root + "/rooms/\(id.pathComponent)")
                fetchedAt = Date()
                try await pullMessages(client: client, roomID: id)
                if beat % 3 == 0 { _ = try? await client.request(.post, path: root + "/rooms/\(id.pathComponent)/heartbeat") }
                beat += 1
                error = nil
            } catch is CancellationError {
            } catch {
                self.error = error.localizedDescription
                if let failure = error as? APIError, [401, 403, 404, 410].contains(failure.statusCode) { closeRoom() }
            }
        } else {
            await refreshLists(client: client)
        }
    }

    private func pullMessages(client: APIClient, roomID: String) async throws {
        while !Task.isCancelled {
            let page = try await client.request(path: root + "/rooms/\(roomID.pathComponent)/messages", query: ["after": String(after)])
            let items = page.items
            for item in items where (item["id"].int ?? 0) > after {
                messages.append(item); after = item["id"].int ?? after
            }
            if messages.count > 2000 { messages.removeFirst(messages.count - 2000) }
            if items.count < 100 { break }
        }
    }

    private func open(_ detail: JSONValue) {
        roomBound = true
        room = detail
        after = 0
        beat = 0
        messages = []
        fetchedAt = Date()
    }
    private func closeRoom() { room = .null; messages = []; after = 0; roomBound = false }

    func create(title: String, client: APIClient) async {
        await perform {
            let cleaned = title.trimmingCharacters(in: .whitespacesAndNewlines)
            let detail = try await client.request(.post, path: self.root + "/", body: ["title": .string(cleaned.isEmpty ? "自习室" : cleaned)])
            self.open(detail)
            await self.refreshLists(client: client)
        }
    }
    func join(id: String, client: APIClient) async {
        await perform { self.open(try await client.request(path: self.root + "/rooms/\(id.pathComponent)")) }
    }
    func accept(id: String, client: APIClient) async {
        await perform {
            self.open(try await client.request(.post, path: self.root + "/invitations/\(id.pathComponent)/accept"))
            await self.refreshLists(client: client)
        }
    }
    func decline(id: String, client: APIClient) async {
        await perform {
            _ = try await client.request(.post, path: self.root + "/invitations/\(id.pathComponent)/decline")
            await self.refreshLists(client: client)
        }
    }
    func invite(uid: String, client: APIClient) async {
        guard let id = room["id"].string else { return }
        await perform {
            _ = try await client.request(.post, path: self.root + "/rooms/\(id.pathComponent)/invitations", body: ["uid": .string(uid.trimmingCharacters(in: .whitespacesAndNewlines))])
            self.room = try await client.request(path: self.root + "/rooms/\(id.pathComponent)")
        }
    }
    func setState(_ state: String, message: String?, client: APIClient) async {
        guard let id = room["id"].string else { return }
        await perform {
            var body: [String: JSONValue] = ["study_state": .string(state)]
            if let message, !message.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty { body["status_message"] = .string(message) }
            _ = try await client.request(.patch, path: self.root + "/rooms/\(id.pathComponent)/state", body: .object(body))
            self.room = try await client.request(path: self.root + "/rooms/\(id.pathComponent)")
        }
    }
    func controlTimer(_ action: String, client: APIClient) async {
        guard let id = room["id"].string else { return }
        await perform {
            self.room = try await client.request(.post, path: self.root + "/rooms/\(id.pathComponent)/timer", body: ["action": .string(action)])
            self.fetchedAt = Date()
        }
    }
    func send(_ text: String, client: APIClient) async -> Bool {
        guard let id = room["id"].string else { return false }
        let content = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !content.isEmpty else { return false }
        var ok = false
        await perform {
            _ = try await client.request(.post, path: self.root + "/rooms/\(id.pathComponent)/messages",
                                         body: ["content": .string(content), "client_id": .string(UUID().uuidString)])
            try await self.pullMessages(client: client, roomID: id)
            ok = true
        }
        return ok
    }
    func leave(client: APIClient) async {
        guard let id = room["id"].string else { return }
        await perform {
            _ = try await client.request(.post, path: self.root + "/rooms/\(id.pathComponent)/leave")
            self.closeRoom()
            await self.refreshLists(client: client)
        }
    }

    private func perform(_ block: @escaping () async throws -> Void) async {
        do { try await block(); error = nil }
        catch is CancellationError { }
        catch { self.error = error.localizedDescription }
    }
}
