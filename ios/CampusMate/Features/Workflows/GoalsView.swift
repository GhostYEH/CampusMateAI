import SwiftUI
import CampusCore

struct GoalsView: View {
    @Environment(\.campus) private var palette
    @Environment(AppModel.self) private var app
    @State private var resource = PagedResource()
    @State private var creating = false
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                CampusCard {
                    VStack(spacing: 0) {
                        link("学习计划", detail: "把目标拆成可执行的步骤", icon: "list.bullet.clipboard") { LearningPlansView() }
                        Divider()
                        link("执行记录", detail: "查看 Agent 运行与产物", icon: "clock.arrow.circlepath") { AgentJobsView() }
                        Divider()
                        link("学习状态与数据来源", detail: "了解数据从哪里来", icon: "chart.line.uptrend.xyaxis") { LearnerStateView() }
                        Divider()
                        link("服务能力", detail: "当前后端可用的能力", icon: "info.circle") { AgentCapabilitiesView() }
                    }
                }
                Text("我的目标").campusFont(.subtitle).foregroundStyle(palette.textPrimary)
                    .frame(maxWidth: .infinity, alignment: .leading).padding(.top, 4)
                if resource.isLoading && resource.items.isEmpty { CampusLoadingState() }
                else if let error = resource.error, resource.items.isEmpty { CampusErrorState(message: error) { Task { await load() } } }
                else if resource.items.isEmpty {
                    CampusEmptyState(title: "还没有学习目标", message: "写下一个目标，再生成适合自己的行动计划。", systemImage: "target")
                } else {
                    ForEach(Array(resource.items.enumerated()), id: \.offset) { _, goal in
                        NavigationLink { GoalDetailView(goalID: goal["goal_id"].text) } label: {
                            VStack(alignment: .leading, spacing: 8) {
                                HStack {
                                    Text(goal["name"].text).campusFont(.body).fontWeight(.semibold)
                                        .foregroundStyle(palette.textPrimary).lineLimit(2)
                                    Spacer()
                                    Text(goal["status"].text.localizedStatus)
                                        .campusFont(.caption).foregroundStyle(.secondary)
                                }
                                ProgressView(value: goal["progress_percent"].double ?? 0, total: 100)
                                    .tint(Color(hex: 0x285B4B))
                                Text("\(Int(goal["progress_percent"].double ?? 0))% 完成")
                                    .campusFont(.caption).foregroundStyle(.secondary)
                            }
                            .padding(15)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .background(palette.surface, in: RoundedRectangle(cornerRadius: 16))
                            .overlay(RoundedRectangle(cornerRadius: 16).strokeBorder(Color(hex: 0xD7DED5, opacity: 0.7), lineWidth: 1))
                        }
                        .buttonStyle(.plain)
                    }
                    if resource.hasMore {
                        Button("加载更多") { Task { await resource.load(client: app.client, path: "student-goals", reset: false) } }
                            .campusFont(.caption).foregroundStyle(palette.primary)
                    }
                }
            }
            .padding(20)
            .frame(maxWidth: 700)
            .frame(maxWidth: .infinity)
        }
        .campusWorkflowChrome("目标与计划", actionTitle: "新建目标", action: { creating = true })
        .task { await load() }
        .refreshable { await load() }
        .sheet(isPresented: $creating, onDismiss: { Task { await load() } }) { NavigationStack { GoalEditorView() } }
    }

    private func link<Destination: View>(_ title: String, detail: String, icon: String, @ViewBuilder destination: () -> Destination) -> some View {
        NavigationLink { destination() } label: {
            HStack(spacing: 12) {
                Image(systemName: icon).font(.system(size: 16)).foregroundStyle(palette.primary).frame(width: 24)
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).campusFont(.body).foregroundStyle(palette.textPrimary)
                    Text(detail).campusFont(.caption).foregroundStyle(.secondary)
                }
                Spacer()
                Image(systemName: "chevron.right").font(.system(size: 12)).foregroundStyle(.secondary)
            }
            .padding(.vertical, 12)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    private func load() async { await resource.load(client: app.client, path: "student-goals") }
}

private struct GoalEditorView: View {
    @Environment(\.campus) private var palette
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var name = ""
    @State private var category = "academic"
    @State private var hasDate = false
    @State private var date = Date.now.addingTimeInterval(86400 * 30)
    @State private var action = WorkflowAction()
    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 12) {
                CampusCard {
                    VStack(alignment: .leading, spacing: 12) {
                        Text("目标内容").campusFont(.subtitle).foregroundStyle(palette.textPrimary)
                        TextField("目标名称", text: $name, axis: .vertical).lineLimit(2...5)
                            .campusFont(.body)
                            .padding(12)
                            .background(palette.background, in: RoundedRectangle(cornerRadius: 10))
                            .accessibilityIdentifier("goals.name")
                        Picker("类别", selection: $category) {
                            ForEach(Self.categories, id: \.0) { Text($0.1).tag($0.0) }
                        }
                        .tint(Color(hex: 0x285B4B))
                        Toggle("设置目标日期", isOn: $hasDate.animation()).tint(Color(hex: 0x285B4B))
                        if hasDate { DatePicker("目标日期", selection: $date, displayedComponents: .date).tint(Color(hex: 0x285B4B)) }
                    }
                }
                CampusPrimaryButton(title: action.isWorking ? "正在保存…" : "保存",
                                    loading: action.isWorking,
                                    enabled: !name.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && name.count <= 200) {
                    Task {
                        var body: [String: JSONValue] = ["name": .string(name.trimmingCharacters(in: .whitespacesAndNewlines)), "category": .string(category)]
                        if hasDate { body["target_date"] = .string(date.formatted(.iso8601.year().month().day().dateSeparator(.dash))) }
                        if await action.perform(client: app.client, path: "student-goals", body: .object(body)) != nil { dismiss() }
                    }
                }
            }
            .padding(20)
            .frame(maxWidth: 700)
            .frame(maxWidth: .infinity)
        }
        .campusWorkflowChrome("新建目标")
        .task { await action.restore(scope: app.serverURL + "|" + (app.session?.user.id ?? "") + "|goal-create") }
        .errorAlert(Binding(get: { action.error }, set: { action.error = $0 }))
    }
    private static let categories = [("academic","学业"), ("research","研究"), ("competition","竞赛"), ("certificate","证书"), ("job_search","求职"), ("internship","实习"), ("campus_affair","校园事务"), ("health_habit","健康习惯"), ("personal_growth","个人成长")]
}

private struct GoalDetailView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    let goalID: String
    @State private var resource = RemoteResource()
    @State private var minutes = 60
    @State private var progress = 0.0
    @State private var milestone = ""
    @State private var action = WorkflowAction()
    @State private var runID: String?
    @State private var archive = false
    var body: some View {
        Form {
            ResourceStateView(resource: resource, isEmpty: resource.value == .null, retry: load)
            if resource.value != .null {
                Section { Text(resource.value["name"].text).font(.title2.bold()); if let date = resource.value["target_date"].string { LabeledContent("目标日期", value: date) } }
                Section("更新实际进展") {
                    Slider(value: $progress, in: 0...100, step: 1)
                    LabeledContent("当前进度", value: "\(Int(progress))%")
                    TextField("达到的里程碑（可选）", text: $milestone)
                    Button("保存进度") { Task {
                        if await action.perform(client: app.client, path: "student-goals/\(goalID.pathComponent)/progress", body: ["progress_percent": .number(progress), "milestone_reached": milestone.nonEmpty.map(JSONValue.string) ?? .null]) != nil { await load() }
                    } }.disabled(action.isWorking || milestone.count > 128 || resource.value["status"].text == "archived")
                }
                Section("生成行动计划") {
                    Stepper("可用 \(minutes) 分钟", value: $minutes, in: 15...600, step: 15)
                    Button("生成计划", systemImage: "sparkles") { Task {
                        if let job = await action.perform(client: app.client, path: "agent-jobs", body: ["job_kind": "learning_goal", "input_ref": ["goal_id": .string(goalID), "available_minutes": .number(Double(minutes))]]) { runID = job["latest_run_id"].string }
                    } }.disabled(action.isWorking || resource.value["status"].text == "archived")
                }
                Section { Button("归档目标", role: .destructive) { archive = true }.disabled(action.isWorking || resource.value["status"].text == "archived") }
            }
        }.campusWorkflowChrome("学习目标")
        .task { await action.restore(scope: app.serverURL + "|" + (app.session?.user.id ?? "") + "|goal|" + goalID); await load() }
        .navigationDestination(item: $runID) { AgentRunView(runID: $0) }
        .confirmationDialog("归档这个目标？", isPresented: $archive, titleVisibility: .visible) { Button("归档", role: .destructive) { Task { if await action.perform(client: app.client, path: "student-goals/\(goalID.pathComponent)/archive") != nil { dismiss() } } } }
        .errorAlert(Binding(get: { action.error }, set: { action.error = $0 }))
    }
    private func load() async { await resource.load(client: app.client, path: "student-goals/" + goalID.pathComponent); progress = resource.value["progress_percent"].double ?? 0 }
}

struct AgentJobsView: View {
    @Environment(AppModel.self) private var app
    @State private var resource = RemoteResource()
    var body: some View {
        List {
            ResourceStateView(resource: resource, isEmpty: resource.value.items.isEmpty, title: "暂无执行记录", message: "从学习目标、复习计划或研究问题开始。", systemImage: "clock", retry: load)
            ForEach(Array(resource.value.items.enumerated()), id: \.offset) { _, job in
                if let runID = job["latest_run_id"].string {
                    NavigationLink { AgentRunView(runID: runID) } label: {
                        VStack(alignment: .leading, spacing: 6) {
                            Text(["learning_goal":"学习目标", "final_review":"期末复习", "course_research":"课程研究", "notice_workflow":"通知事务", "interactive_classroom":"互动课堂"][job["job_kind"].text] ?? "学习任务")
                            Text(job["status"].text.agentStatus + " · " + job["created_at"].text).font(.caption).foregroundStyle(.secondary)
                        }
                    }
                }
            }
        }.campusWorkflowChrome("执行记录").task { await load() }.refreshable { await load() }
    }
    private func load() async { await resource.load(client: app.client, path: "agent-jobs") }
}

struct LearningPlansView: View {
    @Environment(AppModel.self) private var app
    @State private var resource = PagedResource()
    var body: some View {
        List {
            PagedStatusView(resource: resource, emptyTitle: "还没有学习计划", emptyMessage: "可在目标详情中生成计划，审核后创建个人待办。", icon: "list.bullet.clipboard", retry: load)
            ForEach(Array(resource.items.enumerated()), id: \.offset) { _, plan in NavigationLink { LearningPlanView(planID: plan["plan_id"].text) } label: { VStack(alignment: .leading) { Text(plan["llm_summary"].string?.nonEmpty ?? "学习计划").lineLimit(2); Text(plan["status"].text.agentStatus + " · " + plan["created_at"].text).font(.caption).foregroundStyle(.secondary) } } }
            LoadMoreRow(resource: resource) { await resource.load(client: app.client, path: "learning-plans", reset: false) }
        }.campusWorkflowChrome("学习计划").task { await load() }.refreshable { await load() }
    }
    private func load() async { await resource.load(client: app.client, path: "learning-plans") }
}

struct LearningPlanView: View {
    @Environment(AppModel.self) private var app
    let planID: String
    @State private var resource = RemoteResource()
    @State private var summary = RemoteResource()
    @State private var action = WorkflowAction()
    @State private var confirming: String?
    @State private var nextPlan: String?
    var body: some View {
        List {
            ResourceStateView(resource: resource, isEmpty: resource.value == .null, retry: load)
            if resource.value != .null {
                Section("计划概况") {
                    LabeledContent("状态", value: resource.value["status"].text.agentStatus)
                    if let headline = summary.value["headline"].string { Text(headline).font(.headline) }
                    if let percent = summary.value["completion_percent"].double { ProgressView(value: percent, total: 100) }
                    if let text = summary.value["next_action"].string { Text(text).font(.footnote).foregroundStyle(.secondary) }
                    if let text = resource.value["llm_summary"].string { Text(text) }
                    LabeledContent("计划分钟", value: resource.value["allocated_minutes"].text)
                }
                Section("学习安排") { WorkflowContentView(value: resource.value["items"]) }
                Section {
                    Button("接受计划") { confirming = "accept" }.disabled(action.isWorking)
                    Button("创建个人待办") { confirming = "execute" }.disabled(action.isWorking)
                    Button("重新规划") { confirming = "replan" }.disabled(action.isWorking)
                    Button("撤回已创建的待办", role: .destructive) { confirming = "undo" }.disabled(action.isWorking)
                } footer: { Text("计划需先接受再执行。是否可执行、过期或撤回由服务端检查；不会直接提交来源系统的作业。") }
            }
        }.campusWorkflowChrome("学习计划")
        .task { await action.restore(scope: app.serverURL + "|" + (app.session?.user.id ?? "") + "|plan|" + planID); await load() }
        .refreshable { await load() }
        .navigationDestination(item: $nextPlan) { LearningPlanView(planID: $0) }
        .confirmationDialog("确认执行所选操作？", isPresented: Binding(get: { confirming != nil }, set: { if !$0 { confirming = nil } }), titleVisibility: .visible) {
            Button("确认") { let verb = confirming ?? ""; confirming = nil; Task {
                let result = await action.perform(client: app.client, path: "learning-plans/\(planID.pathComponent)/" + (verb == "accept" ? "decision" : verb), body: verb == "accept" ? ["decision": "ACCEPT"] : [:])
                if let result { if verb == "replan", let next = result["plan_id"].string, next != planID { nextPlan = next }; await load() }
            } }
        }
        .errorAlert(Binding(get: { action.error }, set: { action.error = $0 }))
    }
    private func load() async { await resource.load(client: app.client, path: "learning-plans/" + planID.pathComponent); await summary.load(client: app.client, path: "learning-plans/\(planID.pathComponent)/summary") }
}

private struct AgentCapabilitiesView: View {
    @Environment(AppModel.self) private var app
    @State private var resource = RemoteResource()
    var body: some View {
        List {
            ResourceStateView(resource: resource, isEmpty: resource.value == .null, retry: load)
            ForEach(Array(resource.value["capabilities"].items.enumerated()), id: \.offset) { _, item in
                VStack(alignment: .leading, spacing: 7) { Text(item["name"].text); Text(item["requires_approval"].bool == true ? "执行需要你的确认" : "按服务端权限执行").font(.caption).foregroundStyle(.secondary) }
            }
        }.campusWorkflowChrome("服务能力").task { await load() }
    }
    private func load() async { await resource.load(client: app.client, path: "agent-runtime/capabilities") }
}

private struct LearnerStateView: View {
    @Environment(AppModel.self) private var app
    @State private var controls = RemoteResource()
    @State private var error: String?
    @State private var working = false
    var body: some View {
        List {
            Section("学习状态") {
                NavigationLink("状态摘要") { LearnerRecordsView(title: "状态摘要", path: "learner-state/snapshots", query: ["projection_kind": "CORE"]) }
                NavigationLink("校园生活与目标预测") { LearnerRecordsView(title: "参考预测", path: "learner-state/forecasts") }
                NavigationLink("调整与效果") { LearnerRecordsView(title: "学习调整", path: "adaptive-interventions") }
                NavigationLink("模型透明度") { WorkflowRemoteDocumentView(title: "模型透明度", path: "learner-state/model-transparency") }
            }
            Section {
                ResourceStateView(resource: controls, isEmpty: controls.value.items.isEmpty, title: "暂无数据来源设置", message: "请刷新或稍后重试。", retry: load)
                ForEach(Array(controls.value.items.enumerated()), id: \.offset) { _, source in
                    let enabled = source["status"].text == "ENABLED"
                    Toggle(Self.sourceNames[source["source_key"].text] ?? source["source_key"].text, isOn: Binding(get: { enabled }, set: { value in
                        working = true
                        Task { defer { working = false }; do {
                            _ = try await app.client.request(.put, path: "learner-state/data-controls/" + source["source_key"].text.pathComponent, body: ["status": .string(value ? "ENABLED" : "PAUSED"), "idempotency_key": .string(UUID().uuidString)])
                            await load()
                        } catch { self.error = error.localizedDescription } }
                    })).disabled(working || (enabled ? source["can_pause"].bool == false : source["can_resume"].bool == false))
                }
            } header: { Text("参与学习状态分析的数据") } footer: { Text("暂停只影响后续分析，不修改课程、待办或已保存的学习事实。预测仅作参考，不代表实际结果。") }
        }.campusWorkflowChrome("学习状态与来源").task { await load() }.refreshable { await load() }.errorAlert($error)
    }
    private func load() async { await controls.load(client: app.client, path: "learner-state/data-controls") }
    private static let sourceNames = ["CORE_STUDY":"学习记录", "PERSONAL_TASK":"个人待办", "CHAOXING":"学习通", "EDU":"教务数据", "MODEL_SHADOW":"辅助模型", "PROACTIVE_SUGGESTIONS":"主动建议"]
}

private struct LearnerRecordsView: View {
    @Environment(AppModel.self) private var app
    let title: String
    let path: String
    var query: [String:String] = [:]
    @State private var resource = PagedResource()
    var body: some View {
        List {
            PagedStatusView(resource: resource, retry: load)
            ForEach(Array(resource.items.enumerated()), id: \.offset) { _, item in
                Section {
                    WorkflowContentView(value: item)
                    if let id = item["intervention_id"].string { NavigationLink("查看效果") { WorkflowRemoteDocumentView(title: "调整效果", path: "adaptive-interventions/\(id.pathComponent)/outcome") } }
                    if let id = item["snapshot_id"].string { NavigationLink("查看依据") { WorkflowRemoteDocumentView(title: "参考依据", path: "learner-state/snapshots/\(id.pathComponent)/evidence") } }
                }
            }
            LoadMoreRow(resource: resource) { await resource.load(client: app.client, path: path, query: query, reset: false) }
        }.campusWorkflowChrome(title).task { await load() }.refreshable { await load() }
    }
    private func load() async { await resource.load(client: app.client, path: path, query: query) }
}

struct WorkflowRemoteDocumentView: View {
    @Environment(AppModel.self) private var app
    let title: String
    let path: String
    @State private var resource = RemoteResource()
    var body: some View { List { ResourceStateView(resource: resource, isEmpty: resource.value == .null, retry: load); if resource.value != .null { WorkflowContentView(value: resource.value) } }.campusWorkflowChrome(title).task { await load() }.refreshable { await load() } }
    private func load() async { await resource.load(client: app.client, path: path) }
}
