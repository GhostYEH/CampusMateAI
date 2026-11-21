import Foundation
import Observation
import CampusCore

@MainActor @Observable
final class ClassroomModel {
    var status: JSONValue = .null
    var history: [JSONValue] = []
    var materials: [JSONValue] = []
    var coursePlan: JSONValue = .null
    var session: JSONValue = .null
    var result: JSONValue = .null
    var isLoading = false
    var isWorking = false
    var error: String?
    var pollingStopped = false
    var pollEpoch = 0
    private(set) var consecutivePollFailures = 0
    var selectedMaterials: Set<String> = []
    var sessionID: String { session["session_id"].text }
    var isTerminal: Bool { session["terminal"].bool == true || ["succeeded", "failed", "cancelled"].contains(session["status"].text) }
    var canGenerate: Bool { status["enabled"].bool == true && status["available"].bool == true && !isWorking && (sessionID.isEmpty || isTerminal) }
    var interval: Double { min(30, max(1, Double(status["poll_interval_ms"].int ?? 5000) / 1000)) }
    var maxPollSeconds: Double { min(3600, max(30, Double(status["poll_max_seconds"].int ?? 1800))) }
    /// 临时网络错误按上限退避，最多连续 5 次后暂停自动刷新。
    var pollDelay: Double { min(30, interval * pow(2, Double(min(consecutivePollFailures, 3)))) }
    @ObservationIgnored private var service: ClassroomService?
    @ObservationIgnored private var cacheScope = ""
    private struct Snapshot: Codable, Sendable { let session: JSONValue; let materials: [JSONValue] }

    func load(client: APIClient, scope: ClassroomScope, account: String) async {
        guard !isLoading else { return }
        service = ClassroomService(client: client, scope: scope); cacheScope = account + "|" + scope.path
        isLoading = true; defer { isLoading = false }
        if session == .null, let saved = await AccountCache.shared.load(Snapshot.self, scope: cacheScope, key: "classroom.json") { session = saved.session; materials = saved.materials }
        do {
            guard let service else { return }
            status = try await service.status()
            history = try await service.history()
            if case .course = scope {
                coursePlan = try await service.plan(mode: "adaptive")
                materials = coursePlan["materials"].items
                selectedMaterials = Set(coursePlan["selected_material_ids"].items.compactMap(\.string))
            }
            if !sessionID.isEmpty { await refresh() }
        } catch is CancellationError { }
        catch { self.error = error.localizedDescription }
    }
    func refresh() async {
        guard let service, !sessionID.isEmpty else { return }
        let target = sessionID
        do {
            let latest = try await service.progress(sessionID: target)
            // 历史切换后，旧会话的迟到进度不能覆盖当前会话。
            guard sessionID == target else { return }
            session = latest
            consecutivePollFailures = 0
            await save()
        } catch is CancellationError {
        } catch {
            guard sessionID == target else { return }
            if isTerminalPollingError(error) {
                consecutivePollFailures = 0
                pollingStopped = true
                self.error = error.localizedDescription
            } else {
                consecutivePollFailures += 1
                if consecutivePollFailures >= 5 {
                    pollingStopped = true
                    self.error = "自动刷新已暂停：\(error.localizedDescription)。可点“刷新进度”恢复。"
                }
            }
        }
    }

    /// 手动恢复：重置退避并只保留一个轮询任务（由 pollEpoch 触发 .task 重启）。
    func resumePolling() {
        consecutivePollFailures = 0
        pollingStopped = false
        pollEpoch &+= 1
    }

    private func isTerminalPollingError(_ error: Error) -> Bool {
        guard let api = error as? APIError else { return false }
        return [401, 403, 404, 410].contains(api.statusCode)
    }
    func selectHistory(_ item: JSONValue) async { session = item; pollingStopped = false; await refresh() }
    func generate(goal: String, difficulty: String, minutes: Int, mode: String, practice: Bool, retry: Bool = false) async {
        guard let service, !isWorking else { return }
        let previous = sessionID
        isWorking = true; defer { isWorking = false }
        do {
            let body: JSONValue = ["mode": .string(mode), "learning_objective": goal.nonEmpty.map(JSONValue.string) ?? .null,
                                   "current_difficulty": difficulty.nonEmpty.map(JSONValue.string) ?? .null,
                                   "desired_duration_minutes": .number(Double(minutes)), "wants_more_practice": .bool(practice),
                                   "selected_material_ids": .array(selectedMaterials.sorted().map(JSONValue.string))]
            result = try await service.generate(body: body, retrySessionID: retry ? previous : nil)
            session = result["session"]; pollingStopped = false
            await save()
        } catch is CancellationError { }
        catch { self.error = error.localizedDescription + "\n提交结果可能尚未确认，请先刷新历史和进度再重试。" }
    }
    func upload(name: String, mime: String, data: Data, key: String) async -> Bool {
        guard let service, !isWorking else { return false }
        isWorking = true; defer { isWorking = false }
        do {
            let material = try await service.upload(filename: name, mimeType: mime, data: data, key: key)
            materials.removeAll { $0["id"] == material["id"] }; materials.append(material)
            if material["extraction_status"].text == "extracted", material["text_chars"].int ?? 0 > 0 { selectedMaterials.insert(material["id"].text) }
            await save(); return true
        } catch is CancellationError { return false }
        catch { self.error = error.localizedDescription; return false }
    }
    private func save() async {
        try? await AccountCache.shared.save(Snapshot(session: session, materials: materials), scope: cacheScope, key: "classroom.json")
    }
}
