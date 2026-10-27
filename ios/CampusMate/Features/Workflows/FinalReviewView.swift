import SwiftUI
import CampusCore

struct FinalReviewView: View {
    @Environment(AppModel.self) private var app
    @State private var resource = RemoteResource()
    @State private var creating = false
    var body: some View {
        List {
            ResourceStateView(resource: resource, isEmpty: resource.value.items.isEmpty, title: "还没有复习活动", message: "先在考试安排中添加考试，再为考试生成复习计划。", systemImage: "book.closed", retry: load)
            ForEach(Array(resource.value.items.enumerated()), id: \.offset) { _, campaign in
                NavigationLink { ReviewCampaignView(campaignID: campaign["campaign_id"].text) } label: {
                    VStack(alignment: .leading, spacing: 6) {
                        Text("\(campaign["exam_ids"].items.count) 场考试的复习计划").font(.headline)
                        Text("每日 \(campaign["daily_capacity_minutes"].text) 分钟 · " + campaign["status"].text.agentStatus).font(.caption).foregroundStyle(.secondary)
                    }
                }
            }
        }.campusWorkflowChrome("期末复习").task { await load() }.refreshable { await load() }
        .toolbar { Button("新建复习活动", systemImage: "plus") { creating = true } }
        .sheet(isPresented: $creating, onDismiss: { Task { await load() } }) { NavigationStack { ReviewCampaignEditor() } }
    }
    private func load() async { await resource.load(client: app.client, path: "final-review/campaigns") }
}

private struct ReviewCampaignEditor: View {
    @Environment(AppModel.self) private var app
    @State private var exams = RemoteResource()
    @State private var selected: Set<String> = []
    @State private var minutes = 60
    @State private var intensity = "medium"
    @State private var action = WorkflowAction()
    @State private var resultID: String?
    var body: some View {
        Form {
            Section("选择考试") {
                ResourceStateView(resource: exams, isEmpty: exams.value.items.isEmpty, title: "暂无考试", message: "请先在考试安排添加自己的考试。", systemImage: "calendar", retry: load)
                ForEach(Array(exams.value.items.enumerated()), id: \.offset) { _, exam in
                    Toggle(isOn: Binding(get: { selected.contains(exam["id"].text) }, set: { if $0 { selected.insert(exam["id"].text) } else { selected.remove(exam["id"].text) } })) {
                        VStack(alignment: .leading, spacing: 5) { Text(exam["course_name"].text); Text(exam["exam_date"].text).font(.caption).foregroundStyle(.secondary) }
                    }
                }
            }
            Section("学习节奏") {
                Stepper("每天可用 \(minutes) 分钟", value: $minutes, in: 15...600, step: 15)
                Picker("强度", selection: $intensity) { Text("轻松").tag("low"); Text("适中").tag("medium"); Text("集中").tag("high") }
            }
            Section { Button("创建复习活动") { Task {
                if let result = await action.perform(client: app.client, path: "final-review/campaigns", body: ["exam_ids": .array(selected.sorted().map(JSONValue.string)), "daily_capacity_minutes": .number(Double(minutes)), "intensity": .string(intensity)]) { resultID = result["campaign_id"].string }
            } }.disabled(action.isWorking || selected.isEmpty || selected.count > 20) }
        }.campusWorkflowChrome("新建复习活动")
        .task { await action.restore(scope: app.serverURL + "|" + (app.session?.user.id ?? "") + "|review-create"); await load() }
        .navigationDestination(item: $resultID) { ReviewCampaignView(campaignID: $0) }
        .errorAlert(Binding(get: { action.error }, set: { action.error = $0 }))
    }
    private func load() async { await exams.load(client: app.client, path: "student/exams") }
}

private struct ReviewCampaignView: View {
    @Environment(AppModel.self) private var app
    let campaignID: String
    @State private var campaign = RemoteResource()
    @State private var versions = RemoteResource()
    @State private var agenda = RemoteResource()
    @State private var proposals = RemoteResource()
    @State private var action = WorkflowAction()
    @State private var runID: String?
    @State private var report = ""
    @State private var insufficientTime = false
    @State private var checkedItems: Set<String> = []
    @State private var message: String?
    private var root: String { "final-review/campaigns/" + campaignID.pathComponent }
    var body: some View {
        List {
            ResourceStateView(resource: campaign, isEmpty: campaign.value == .null, retry: load)
            if campaign.value != .null {
                Section("复习活动") {
                    LabeledContent("每日可用", value: campaign.value["daily_capacity_minutes"].text + " 分钟")
                    LabeledContent("状态", value: campaign.value["status"].text.agentStatus)
                    if let version = campaign.value["active_version"].int { LabeledContent("使用中的计划", value: "版本 \(version)") }
                    Button("生成新版计划", systemImage: "sparkles") { perform(path: root + "/plans/generate") }.disabled(action.isWorking)
                    if let message { Text(message).font(.footnote).foregroundStyle(.secondary) }
                }
                Section("计划版本") {
                    ForEach(Array(versions.value.items.enumerated()), id: \.offset) { _, version in
                        NavigationLink { ReviewPlanVersionView(campaignID: campaignID, version: version["version"].int ?? 1) } label: { LabeledContent("版本 \(version["version"].text)", value: version["created_at"].text) }
                    }
                    if let error = versions.error { Text(error).font(.footnote).foregroundStyle(.secondary) }
                }
                Section("今日复习") {
                    if let error = agenda.error { Text(error).font(.footnote).foregroundStyle(.secondary) }
                    ForEach(Array(agenda.value["items"].items.enumerated()), id: \.offset) { _, item in
                        VStack(alignment: .leading, spacing: 9) {
                            Text(item["title"].text).font(.headline)
                            Text(item["scheduled_minutes"].text + " 分钟 · " + item["status"].text.agentStatus).font(.caption).foregroundStyle(.secondary)
                            if item["status"].text.lowercased() != "completed" {
                                Button("标记这项已完成") { perform(path: "final-review/daily-items/\(item["item_id"].text.pathComponent)/complete", body: ["feedback": .null]) }.disabled(action.isWorking)
                            }
                            Toggle("纳入今日完成反馈", isOn: Binding(get: { checkedItems.contains(item["item_id"].text) }, set: { if $0 { checkedItems.insert(item["item_id"].text) } else { checkedItems.remove(item["item_id"].text) } }))
                        }.padding(.vertical, 5)
                    }
                    if agenda.value["agenda_date"].string != nil {
                        Toggle("今天时间不足", isOn: $insufficientTime)
                        TextField("遇到的困难（可选）", text: $report, axis: .vertical)
                        Button("提交今日反馈") {
                            perform(path: root + "/daily-checkins", body: ["report_date": agenda.value["agenda_date"], "completed_item_ids": .array(checkedItems.sorted().map(JSONValue.string)), "insufficient_time": .bool(insufficientTime), "difficulty_notes": report.nonEmpty.map(JSONValue.string) ?? .null])
                        }.disabled(action.isWorking || report.count > 500)
                    }
                }
                Section("调整建议") {
                    Button("根据反馈分析调整") { perform(path: root + "/adjustments/analyze") }.disabled(action.isWorking)
                    ForEach(Array(proposals.value.items.enumerated()), id: \.offset) { _, proposal in NavigationLink { ReviewAdjustmentView(proposal: proposal) } label: { Text("版本 \(proposal["source_version"].text) 的调整 · " + proposal["status"].text.agentStatus) } }
                    if let error = proposals.error { Text(error).font(.footnote).foregroundStyle(.secondary) }
                }
            }
        }.campusWorkflowChrome("复习活动")
        .task { await action.restore(scope: app.serverURL + "|" + (app.session?.user.id ?? "") + "|campaign|" + campaignID); await load() }
        .refreshable { await load() }
        .navigationDestination(item: $runID) { AgentRunView(runID: $0) }
        .errorAlert(Binding(get: { action.error }, set: { action.error = $0 }))
    }
    private func load() async {
        await campaign.load(client: app.client, path: root)
        await versions.load(client: app.client, path: root + "/plan-versions")
        await agenda.load(client: app.client, path: root + "/agendas/today")
        await proposals.load(client: app.client, path: root + "/adjustment-proposals")
    }
    private func perform(path: String, body: JSONValue = [:]) {
        Task { if let result = await action.perform(client: app.client, path: path, body: body) {
            runID = result["run_id"].string; message = "请求已受理，请查看最新计划和运行状态。"; await load()
        } }
    }
}

private struct ReviewPlanVersionView: View {
    @Environment(AppModel.self) private var app
    let campaignID: String
    let version: Int
    @State private var resource = RemoteResource()
    @State private var action = WorkflowAction()
    @State private var runID: String?
    @State private var activated = false
    var body: some View {
        List {
            ResourceStateView(resource: resource, isEmpty: resource.value == .null, retry: load)
            if resource.value != .null {
                Section("版本 \(version)") { WorkflowContentView(value: resource.value["plan"]) }
                Section("采用此计划") {
                    if let id = resource.value["approval_id"].string {
                        NavigationLink { ApprovalDecisionView(approvalID: id, summary: "允许激活版本 \(version) 的期末复习计划", content: resource.value["plan"]) } label: { Label("查看并确认计划", systemImage: "hand.raised") }
                    }
                    Button("激活这个版本") { Task {
                        if let result = await action.perform(client: app.client, path: "final-review/campaigns/\(campaignID.pathComponent)/activate", body: ["version": .number(Double(version))]) {
                            activated = result["activated"].bool == true; runID = result["run_id"].string
                        }
                    } }.disabled(action.isWorking)
                    if activated { Label("此版本已激活", systemImage: "checkmark.circle") }
                    Text("先阅读并确认计划，再请求激活。激活仍会校验审批、计划版本与有效期。").font(.footnote).foregroundStyle(.secondary)
                }
            }
        }.campusWorkflowChrome("复习计划")
        .task { await action.restore(scope: app.serverURL + "|" + (app.session?.user.id ?? "") + "|campaign|" + campaignID + "|version|\(version)"); await load() }
        .navigationDestination(item: $runID) { AgentRunView(runID: $0) }
        .errorAlert(Binding(get: { action.error }, set: { action.error = $0 }))
    }
    private func load() async { await resource.load(client: app.client, path: "final-review/campaigns/\(campaignID.pathComponent)/plan-versions/\(version)") }
}

private struct ReviewAdjustmentView: View {
    @Environment(AppModel.self) private var app
    let proposal: JSONValue
    @State private var action = WorkflowAction()
    @State private var reason = ""
    @State private var result: JSONValue?
    @State private var confirming: String?
    var body: some View {
        Form {
            Section("建议变更") { WorkflowContentView(value: proposal["proposal"]); LabeledContent("当前状态", value: (result ?? proposal)["status"].text.agentStatus) }
            Section("你的决定") {
                TextField("原因（可选）", text: $reason)
                Button("采用调整") { confirming = "APPROVED" }.disabled(action.isWorking || result != nil || reason.count > 256)
                Button("拒绝调整", role: .destructive) { confirming = "REJECTED" }.disabled(action.isWorking || result != nil || reason.count > 256)
            }
        }.campusWorkflowChrome("调整建议")
        .task { await action.restore(scope: app.serverURL + "|" + (app.session?.user.id ?? "") + "|adjustment|" + proposal["proposal_id"].text) }
        .confirmationDialog("确认对这项调整作出决定？", isPresented: Binding(get: { confirming != nil }, set: { if !$0 { confirming = nil } }), titleVisibility: .visible) { Button("确认") {
            let decision = confirming ?? "REJECTED"; confirming = nil
            Task { result = await action.perform(client: app.client, path: "final-review/adjustment-proposals/\(proposal["proposal_id"].text.pathComponent)/decision", body: ["decision": .string(decision), "reason": reason.nonEmpty.map(JSONValue.string) ?? .null]) }
        } }
        .errorAlert(Binding(get: { action.error }, set: { action.error = $0 }))
    }
}
