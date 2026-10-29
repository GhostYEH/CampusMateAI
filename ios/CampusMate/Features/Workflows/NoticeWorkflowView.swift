import SwiftUI
import CampusCore

struct NoticeWorkflowView: View {
    @Environment(AppModel.self) private var app
    let noticeID: String
    @State private var resource = RemoteResource()
    @State private var action = WorkflowAction()
    @State private var workflowID: String?
    @State private var confirming: (id: String, verb: String, title: String)?
    @State private var reason = ""
    var body: some View {
        List {
            if workflowID == nil {
                Section {
                    Text("分析这条通知的办理步骤、所需材料和可执行动作。若你已为该来源开启自动化，服务端可能自动创建待办和材料清单；需确认的动作仍会等待你决定。")
                    Button("分析通知") { Task {
                        if let result = await action.perform(client: app.client, path: "notices/\(noticeID.pathComponent)/workflow") {
                            workflowID = result["workflow_id"].string; resource.value = result
                            try? await AccountCache.shared.save(result["workflow_id"].text, scope: cacheScope, key: "notice-workflow.json")
                        }
                    } }.disabled(action.isWorking)
                }
            } else {
                ResourceStateView(resource: resource, isEmpty: resource.value == .null, retry: load)
                if resource.value != .null {
                    Section("通知办理建议") {
                        LabeledContent("状态", value: resource.value["status"].text.agentStatus)
                        WorkflowContentView(value: resource.value)
                        if let error = resource.value["error_message"].string?.nonEmpty { Text(error).font(.footnote).foregroundStyle(.secondary) }
                        Button("重新分析") { Task { if let workflowID, let result = await action.perform(client: app.client, path: "notice-workflows/\(workflowID.pathComponent)/reanalyze") { resource.value = result; await load() } } }.disabled(action.isWorking)
                    }
                    ForEach(Array(resource.value["actions"].items.enumerated()), id: \.offset) { _, item in
                        Section(item["title"].string ?? "办理动作") {
                            LabeledContent("状态", value: item["status"].text.agentStatus)
                            if let date = item["expires_at"].string { LabeledContent("有效期", value: date) }
                            if let error = item["error_message"].string { Text(error).font(.footnote).foregroundStyle(.secondary) }
                            let state = item["status"].text.uppercased()
                            if ["PENDING","PROPOSED","AWAITING_APPROVAL"].contains(state) {
                                Button("同意此动作") { confirming = (item["action_id"].text, "approve", item["title"].text) }.disabled(action.isWorking)
                                Button("拒绝此动作", role: .destructive) { confirming = (item["action_id"].text, "reject", item["title"].text) }.disabled(action.isWorking)
                            }
                            if state == "APPROVED" { Button("执行此动作") { confirming = (item["action_id"].text, "execute", item["title"].text) }.disabled(action.isWorking) }
                            if let reference = item["external_ref"].string, item["action_type"].text.lowercased() == "create_task", ["DONE","EXECUTED","SUCCEEDED"].contains(state) {
                                NavigationLink { PersonalTaskDestination(taskID: reference) } label: { Text("查看创建的待办") }
                            }
                        }
                    }
                }
            }
        }.campusWorkflowChrome("通知事务")
        .task {
            await action.restore(scope: cacheScope)
            workflowID = await AccountCache.shared.load(String.self, scope: cacheScope, key: "notice-workflow.json")
            await load()
        }.refreshable { await load() }
        .confirmationDialog(confirming?.title ?? "确认这项通知动作？", isPresented: Binding(get: { confirming != nil }, set: { if !$0 { confirming = nil } }), titleVisibility: .visible) {
            Button("确认") {
                guard let selection = confirming else { return }; confirming = nil
                Task {
                    let path = "notice-workflow-actions/\(selection.id.pathComponent)/" + (selection.verb == "execute" ? "execute" : "decision")
                    let body: JSONValue = selection.verb == "execute" ? [:] : ["decision": .string(selection.verb == "approve" ? "APPROVED" : "REJECTED")]
                    if await action.perform(client: app.client, path: path, body: body) != nil { await load() }
                }
            }
        }
        .errorAlert(Binding(get: { action.error }, set: { action.error = $0 }))
    }
    private var cacheScope: String { app.serverURL + "|" + (app.session?.user.id ?? "") + "|notice|" + noticeID }
    private func load() async { if let workflowID { await resource.load(client: app.client, path: "notice-workflows/" + workflowID.pathComponent) } }
}

private struct PersonalTaskDestination: View {
    @Environment(AppModel.self) private var app
    let taskID: String
    @State private var task: TaskItem?
    @State private var error: String?
    var body: some View { Group { if let task { TaskDetailView(initial: task) } else { ProgressView("读取待办…") } }.task { do { task = try await LearningService(client: app.client).task(id: taskID) } catch { self.error = error.localizedDescription } }.errorAlert($error) }
}
