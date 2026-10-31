import Observation
import CampusCore

/// 共同课堂的消息、分页与草稿状态。
///
/// 从 `LearningRoomsView.swift` 拆出，避免网络/轮询逻辑和大量 SwiftUI 视图
/// 混在一个文件里；`AccountCache` 与 `RoomMessageDraft` 仍是现有依赖，
/// 不在此重复实现缓存或幂等规则。
@MainActor @Observable
final class LearningRoomModel {
    var room: JSONValue = .null
    var messages: [JSONValue] = []
    var error: String?
    var isLoading = false
    var isSending = false
    var unavailable = false
    var after = 0
    @ObservationIgnored private var draft = RoomMessageDraft()
    @ObservationIgnored private var cacheScope = ""

    func bootstrap(client: APIClient, roomID: String, account: String) async {
        cacheScope = account + "|room|" + roomID
        draft = await AccountCache.shared.load(RoomMessageDraft.self, scope: cacheScope, key: "message-draft.json") ?? RoomMessageDraft()
        await poll(client: client, roomID: roomID)
    }

    func poll(client: APIClient, roomID: String) async {
        guard !isLoading, !unavailable else { return }
        isLoading = true; defer { isLoading = false }
        do {
            room = try await client.request(path: roomRoot + "/rooms/\(roomID.pathComponent)")
            while !Task.isCancelled {
                let page = try await client.request(path: roomRoot + "/rooms/\(roomID.pathComponent)/messages",
                                                   query: ["after": String(after)])
                for message in page.items {
                    guard let id = message["id"].int, id > after else { continue }
                    messages.append(message); after = id
                }
                if messages.count > 2000 { messages.removeFirst(messages.count - 2000) }
                if page.items.count < 100 { break }
            }
        } catch is CancellationError { }
        catch {
            self.error = error.localizedDescription
            if let failure = error as? APIError, [401, 403, 404, 410].contains(failure.statusCode) { unavailable = true }
        }
    }

    func send(_ text: String, client: APIClient, roomID: String) async -> Bool {
        guard !isSending, !unavailable, !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty, text.count <= 2000 else { return false }
        // 先置位再 await，避免两个并发点击同时通过幂等检查并各自 POST。
        isSending = true; defer { isSending = false }
        let body = draft.prepare(text)
        try? await AccountCache.shared.save(draft, scope: cacheScope, key: "message-draft.json")
        do {
            _ = try await client.request(.post, path: roomRoot + "/rooms/\(roomID.pathComponent)/messages", body: body)
            draft.didSend()
            try? await AccountCache.shared.save(draft, scope: cacheScope, key: "message-draft.json")
            await poll(client: client, roomID: roomID)
            return true
        } catch is CancellationError { return false }
        catch { self.error = error.localizedDescription; return false }
    }
}
