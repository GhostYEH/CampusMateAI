import Foundation
import Observation
import CampusCore

@MainActor @Observable
final class AssistantModel {
    var messages: [ChatMessage] = []
    var isSending = false
    var error: String?
    private(set) var conversationID: String?
    private(set) var lastPrompt = ""
    @ObservationIgnored private let client: APIClient
    @ObservationIgnored private let scope: String
    @ObservationIgnored private let courseID: String?
    @ObservationIgnored private let relatedTaskID: String?
    @ObservationIgnored private var request: Task<Void, Never>?
    @ObservationIgnored private var generation = UUID()
    @ObservationIgnored private var loaded = false

    private struct History: Codable, Sendable { let messages: [ChatMessage]; let conversationID: String? }

    init(client: APIClient, scope: String, courseID: String?, relatedTaskID: String?) {
        self.client = client; self.scope = scope; self.courseID = courseID; self.relatedTaskID = relatedTaskID
    }
    func load() async {
        guard !loaded else { return }; loaded = true
        if let history = await AccountCache.shared.load(History.self, scope: scope, key: "chat.json"), messages.isEmpty {
            messages = history.messages; conversationID = history.conversationID
            lastPrompt = messages.last(where: { $0.role == "user" })?.text ?? ""
        }
    }

    func send(_ text: String, retry: Bool = false) {
        let text = text.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !isSending, !text.isEmpty else { return }
        guard text.count <= 20000 else { error = "消息不能超过 20000 字，请缩短后重试。"; return }
        error = nil; lastPrompt = text
        let run = UUID(); generation = run
        if !retry { messages.append(ChatMessage(role: "user", text: text)) }
        else if messages.last?.role == "assistant" { messages.removeLast() }
        let replyID = UUID(); messages.append(ChatMessage(id: replyID, role: "assistant"))
        isSending = true
        request = Task { [weak self] in
            guard let self else { return }
            defer { if generation == run { isSending = false; request = nil } }
            do {
                var body: [String: JSONValue] = ["message": .string(text), "stream": true]
                if let conversationID { body["conversation_id"] = .string(conversationID) }
                if let courseID { body["course_id"] = .string(courseID) }
                if let relatedTaskID { body["recent_tasks"] = [["id": .string(relatedTaskID)]] }
                var reply = ChatReply()
                for try await event in try await client.events(.post, path: "counselor/chat", body: .object(body)) {
                    guard !Task.isCancelled, generation == run else { throw CancellationError() }
                    try reply.consume(event)
                    if let index = messages.firstIndex(where: { $0.id == replyID }) {
                        messages[index].text = reply.text; messages[index].mode = reply.mode
                        messages[index].warnings = reply.warnings; messages[index].sources = reply.sources
                        messages[index].suggestedActions = reply.suggestedActions
                    }
                    if reply.isFinished { break }
                }
                guard generation == run else { return }
                if !reply.isFinished { throw APIError(code: "STREAM_INTERRUPTED", message: "连接中断，已保留收到的回复。") }
                conversationID = reply.conversationID ?? conversationID
            } catch is CancellationError { }
            catch {
                if generation == run {
                    self.error = error.localizedDescription
                    if let index = messages.firstIndex(where: { $0.id == replyID }) { messages[index].interrupted = true }
                }
            }
            if generation == run { isSending = false; request = nil }
            await save()
        }
    }

    func cancel() {
        guard request != nil else { return }
        generation = UUID(); request?.cancel(); request = nil; isSending = false
        if messages.last?.role == "assistant" { messages[messages.count - 1].interrupted = true }
        Task { await save() }
    }
    func clear() {
        cancel(); messages = []; conversationID = nil; lastPrompt = ""; error = nil
        Task { await save() }
    }
    private func save() async {
        let snapshot = History(messages: Array(messages.suffix(120)), conversationID: conversationID)
        do { try await AccountCache.shared.save(snapshot, scope: scope, key: "chat.json") }
        catch { if self.error == nil { self.error = "对话暂未能保存在本机。" } }
    }
}
