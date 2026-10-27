import SwiftUI
import CampusCore

@MainActor @Observable
final class AgentRunModel {
    var run: JSONValue = .null
    var timeline: AgentTimeline
    var isLoading = false
    var connection = ""
    var error: String?
    var candidates: [JSONValue] = []
    let action = WorkflowAction()
    var terminal: Bool { ["SUCCEEDED", "PARTIAL", "FAILED", "CANCELLED"].contains(run["status"].text) }
    init(runID: String) { timeline = AgentTimeline(runID: runID) }
    func refresh(client: APIClient) async throws {
        run = try await client.request(path: "agent-runs/\(timeline.runID.pathComponent)")
        while !Task.isCancelled {
            let page = try await client.request(path: "agent-runs/\(timeline.runID.pathComponent)/events", query: ["after_sequence": String(timeline.sequence), "limit": "100"])
            for event in page.items { try timeline.append(event) }
            if page.items.count < 100 { return }
        }
    }
    func observe(client: APIClient, scope: String) async {
        isLoading = true
        await action.restore(scope: scope + "|run|" + timeline.runID)
        defer { isLoading = false }
        for attempt in 0..<5 {
            guard !Task.isCancelled else { return }
            do {
                try await refresh(client: client)
                isLoading = false
                guard !terminal else { connection = "运行已结束"; return }
                connection = "实时更新中"
                var headers: [String:String] = [:]
                if let id = timeline.lastEventID { headers["Last-Event-ID"] = id }
                for try await event in try await client.events(path: "agent-runs/\(timeline.runID.pathComponent)/events/stream", headers: headers) {
                    guard !Task.isCancelled else { return }
                    try timeline.append(event.json)
                    if let state = event.json["status"].string { var object = run.object ?? [:]; object["status"] = .string(state); run = .object(object) }
                }
                try await refresh(client: client)
                if terminal { connection = "运行已结束"; return }
            } catch is CancellationError { return }
            catch let failure as APIError where ["AGENT_CURSOR_INVALID","AGENT_EVENT_GAP"].contains(failure.code) { timeline = AgentTimeline(runID: timeline.runID) }
            catch {
                if let failure = error as? APIError, [401,403,404].contains(failure.statusCode) { self.error = error.localizedDescription; connection = "已停止更新"; return }
                self.error = error.localizedDescription
            }
            connection = "连接中断，正在恢复"
            try? await Task.sleep(for: .seconds(pow(2, Double(attempt))))
        }
        connection = "自动恢复已暂停，请刷新"
    }
    func control(_ verb: String, client: APIClient) async -> String? {
        let previous = timeline.runID
        guard let result = await action.perform(client: client, path: "agent-runs/\(previous.pathComponent)/\(verb)") else { return nil }
        if verb == "retry" {
            let next = result["run_id"].text
            if !next.isEmpty, next != previous { return next }
            if let jobID = run["job_id"].string { candidates = (try? await client.request(path: "agent-jobs/\(jobID.pathComponent)/runs").items.filter { $0["retry_of"].text == previous }) ?? [] }
            error = "重试响应未返回新运行，请在下方核对已有重试记录后进入。"
        }
        try? await refresh(client: client); return nil
    }
}

struct AgentRunView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.scenePhase) private var scenePhase
    @State private var model: AgentRunModel
    @State private var nextRun: String?
    @State private var confirmAction: String?
    @State private var reload = UUID()
    init(runID: String) { _model = State(initialValue: AgentRunModel(runID: runID)) }
    var body: some View {
        List {
            Section("运行状态") {
                if model.isLoading { ProgressView("读取运行…") }
                LabeledContent("当前状态", value: model.run["status"].text.agentStatus)
                if !model.connection.isEmpty { Text(model.connection).font(.caption).foregroundStyle(.secondary) }
                if let error = model.run["error"]["message"].string?.nonEmpty { Text(error).font(.footnote).foregroundStyle(.secondary) }
                let state = model.run["status"].text
                HStack {
                    if ["QUEUED","RUNNING"].contains(state) { Button("暂停") { control("pause") } }
                    if state == "PAUSED" { Button("恢复") { control("resume") } }
                    if ["FAILED","PARTIAL","CANCELLED"].contains(state) { Button("重试") { confirmAction = "retry" } }
                    if !["SUCCEEDED","FAILED","CANCELLED"].contains(state) { Button("取消运行", role: .destructive) { confirmAction = "cancel" } }
                }.disabled(model.action.isWorking)
            }
            if model.run["status"].text == "AWAITING_APPROVAL", let approval = model.timeline.events.last(where: { $0["approval_id"].string != nil }) {
                Section("需要你的确认") {
                    NavigationLink { ApprovalDecisionView(approvalID: approval["approval_id"].text, summary: approval["summary"].text) } label: { Label(approval["summary"].string?.nonEmpty ?? "查看待确认操作", systemImage: "hand.raised") }
                }
            }
            if !model.candidates.isEmpty {
                Section("核对重试记录") { ForEach(Array(model.candidates.enumerated()), id: \.offset) { _, item in NavigationLink { AgentRunView(runID: item["run_id"].text) } label: { Text(item["created_at"].text + " · " + item["status"].text.agentStatus) } } }
            }
            Section("运行记录") {
                if model.timeline.events.isEmpty { Text("尚未收到运行事件。").foregroundStyle(.secondary) }
                ForEach(Array(model.timeline.events.enumerated()), id: \.offset) { _, event in
                    VStack(alignment: .leading, spacing: 6) {
                        Text(event["summary"].string?.nonEmpty ?? event["status"].text.agentStatus)
                        if let percent = event["progress"]["percent"].double { ProgressView(value: max(0,min(100,percent)), total: 100) }
                        Text(event["created_at"].text).font(.caption).foregroundStyle(.secondary)
                        if let artifact = event["artifact_id"].string { NavigationLink("查看产物") { AgentArtifactView(artifactID: artifact) } }
                    }.padding(.vertical, 4)
                }
            }
            if !model.run["artifact_ids"].items.isEmpty {
                Section("产物") { ForEach(model.run["artifact_ids"].items.compactMap(\.string), id: \.self) { id in NavigationLink("查看学习产物") { AgentArtifactView(artifactID: id) } } }
            }
        }.campusWorkflowChrome("执行记录")
        .task(id: String(scenePhase == .active) + reload.uuidString) { if scenePhase == .active { await model.observe(client: app.client, scope: app.serverURL + "|" + (app.session?.user.id ?? "")) } }
        .refreshable { reload = UUID() }
        .navigationDestination(item: $nextRun) { AgentRunView(runID: $0) }
        .confirmationDialog(confirmAction == "retry" ? "为此任务创建一次新的运行？" : "取消当前运行？", isPresented: Binding(get: { confirmAction != nil }, set: { if !$0 { confirmAction = nil } }), titleVisibility: .visible) {
            Button("确认") { let verb = confirmAction ?? "cancel"; confirmAction = nil; control(verb) }
        }
        .errorAlert(Binding(get: { model.error ?? model.action.error }, set: { model.error = $0; model.action.error = $0 }))
    }
    private func control(_ verb: String) { Task { nextRun = await model.control(verb, client: app.client); reload = UUID() } }
}

struct AgentArtifactView: View {
    @Environment(AppModel.self) private var app
    let artifactID: String
    @State private var resource = RemoteResource()
    @State private var content = ""
    @State private var error: String?
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 20) {
                ResourceStateView(resource: resource, isEmpty: resource.value == .null, retry: load)
                if resource.value != .null {
                    Text(resource.value["title"].string ?? "学习产物").font(.title2.bold())
                    if let json = content.data(using: .utf8).flatMap({ try? JSONValue(data: $0) }), json.object != nil || json.array != nil { WorkflowContentView(value: json) }
                    else { Text(LocalizedStringKey(content)).textSelection(.enabled) }
                    if !content.isEmpty { ShareLink("分享文本", item: content) }
                }
            }.padding()
        }.campusWorkflowChrome("学习产物").task { await load() }
        .errorAlert($error)
    }
    private func load() async {
        await resource.load(client: app.client, path: "agent-artifacts/\(artifactID.pathComponent)")
        guard resource.error == nil else { return }
        do {
            let response = try await app.client.requestData(path: "agent-artifacts/\(artifactID.pathComponent)/content")
            guard response.data.count <= 4 * 1024 * 1024 else { throw APIError(code: "ARTIFACT_SIZE", message: "产物较大，请在完整客户端中查看。") }
            content = String(data: response.data, encoding: .utf8) ?? ""
        } catch { self.error = error.localizedDescription }
    }
}
