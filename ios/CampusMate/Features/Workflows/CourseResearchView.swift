import SwiftUI
import CampusCore

struct CourseResearchView: View {
    @Environment(AppModel.self) private var app
    @State private var runs = RemoteResource()
    @State private var creating = false
    var body: some View {
        List {
            ResourceStateView(resource: runs, isEmpty: runs.value.items.isEmpty, title: "还没有研究记录", message: "提出一个问题，结合课程资料整理可核查的来源。", systemImage: "magnifyingglass", retry: load)
            ForEach(Array(runs.value.items.enumerated()), id: \.offset) { _, run in
                NavigationLink { ResearchDetailView(runID: run["run_id"].text) } label: {
                    VStack(alignment: .leading, spacing: 7) { Text(run["question"].text).lineLimit(3); Text(run["status"].text.agentStatus).font(.caption).foregroundStyle(.secondary) }
                }
            }
        }.campusWorkflowChrome("课程研究", actionTitle: "发起研究", action: { creating = true }).task { await load() }.refreshable { await load() }
        .sheet(isPresented: $creating, onDismiss: { Task { await load() } }) { NavigationStack { ResearchEditorView() } }
    }
    private func load() async { await runs.load(client: app.client, path: "course-research/runs") }
}

private struct ResearchEditorView: View {
    @Environment(AppModel.self) private var app
    @State private var question = ""
    @State private var courseID = ""
    @State private var courses = RemoteResource()
    @State private var mode = "EXPLAIN"
    @State private var policy = "UNKNOWN"
    @State private var allowWeb = true
    @State private var action = WorkflowAction()
    @State private var resultID: String?
    var body: some View {
        Form {
            Section("研究问题") {
                TextField("你想弄清楚什么？", text: $question, axis: .vertical).lineLimit(4...8)
                Picker("关联课程", selection: $courseID) {
                    Text("不关联课程").tag("")
                    ForEach(Array(courses.value.items.enumerated()), id: \.offset) { _, course in Text(course["name"].text).tag(course["id"].text) }
                }
                if let error = courses.error { Text("课程列表暂不可用：" + error).font(.caption).foregroundStyle(.secondary) }
                Picker("辅助方式", selection: $mode) { ForEach(["HINT","EXPLAIN","REVIEW","FULL_SOLUTION"], id: \.self) { Text($0.agentStatus).tag($0) } }
            }
            Section {
                Picker("课程的 AI 使用要求", selection: $policy) { ForEach(["UNKNOWN","LIMITED","EXAM_RESTRICTED","AI_PROHIBITED","ALLOWED"], id: \.self) { Text($0.agentStatus).tag($0) } }
                Toggle("允许公共网络检索", isOn: $allowWeb)
            } header: { Text("资料与学术要求") } footer: { Text("优先使用课程资料。实际辅助方式以服务端校验后的最严格课程要求为准；生成内容和引用仍需核查。") }
            Section {
                Button(action.isWorking ? "正在提交…" : "开始研究") { Task {
                    let body: JSONValue = ["question": .string(question.trimmingCharacters(in: .whitespacesAndNewlines)), "course_id": courseID.nonEmpty.map(JSONValue.string) ?? .null,
                                           "assistance_mode": .string(mode), "academic_policy": .string(policy), "source_policy": ["course_material_priority": true, "allow_web": .bool(allowWeb), "allow_user_upload": false]]
                    if let result = await action.perform(client: app.client, path: "course-research/runs", body: body) { resultID = result["run_id"].string }
                } }.disabled(action.isWorking || question.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || question.count > 2000)
            }
        }.campusWorkflowChrome("发起研究")
        .task {
            await action.restore(scope: app.serverURL + "|" + (app.session?.user.id ?? "") + "|research-create")
            await courses.load(client: app.client, path: "courses", query: ["page_size":"100"])
        }
        .navigationDestination(item: $resultID) { ResearchDetailView(runID: $0) }
        .errorAlert(Binding(get: { action.error }, set: { action.error = $0 }))
    }
}

private struct ResearchDetailView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.scenePhase) private var scenePhase
    let runID: String
    @State private var resource = RemoteResource()
    @State private var artifacts = RemoteResource()
    var body: some View {
        List {
            ResourceStateView(resource: resource, isEmpty: resource.value == .null, retry: load)
            if resource.value != .null {
                Section("研究进度") {
                    Text(resource.value["question"].text).font(.headline)
                    LabeledContent("状态", value: resource.value["status"].text.agentStatus)
                    LabeledContent("实际辅助方式", value: resource.value["effective_assistance_mode"].text.agentStatus)
                    LabeledContent("学术要求", value: resource.value["academic_policy"].text.agentStatus)
                    if resource.value["status"].text == "PARTIAL" { Text("仅部分完成，请结合已有产物和来源查看。").font(.footnote).foregroundStyle(.orange) }
                    NavigationLink("查看运行记录与控制") { AgentRunView(runID: runID) }
                }
                Section("研究产物") {
                    ForEach(Array(artifacts.value["artifacts"].items.enumerated()), id: \.offset) { _, artifact in
                        if let id = artifact["artifact_id"].string { NavigationLink { AgentArtifactView(artifactID: id) } label: { Text(artifact["title"].string ?? "研究产物") } }
                    }
                    if let error = artifacts.error { Text(error).font(.footnote).foregroundStyle(.secondary) }
                }
                Section("引用与核查") {
                    ForEach(Array(artifacts.value["sources"].items.enumerated()), id: \.offset) { _, source in
                        VStack(alignment: .leading, spacing: 7) {
                            Text(source["title"].string ?? source["source_title"].string ?? "参考来源").font(.headline)
                            if let status = source["verification_status"].string { Text("核查状态：" + status).font(.caption).foregroundStyle(.secondary) }
                            if let quote = source["supporting_quote"].string { Text(quote).font(.subheadline) }
                            if let url = URL(string: source["url"].text), url.scheme == "https", url.user == nil { Link("打开来源", destination: url) }
                        }
                    }
                    Text("来源被列出不代表内容已经证实；请结合核查状态与原文判断。").font(.footnote).foregroundStyle(.secondary)
                }
            }
        }.campusWorkflowChrome("研究详情")
        .task {
            await load()
            while !Task.isCancelled, !["SUCCEEDED","FAILED","CANCELLED","PARTIAL"].contains(resource.value["status"].text), resource.error == nil {
                try? await Task.sleep(for: .seconds(5))
                if !Task.isCancelled && scenePhase == .active { await load() }
            }
        }.refreshable { await load() }
    }
    private func load() async { await resource.load(client: app.client, path: "course-research/runs/" + runID.pathComponent); await artifacts.load(client: app.client, path: "course-research/runs/\(runID.pathComponent)/artifacts") }
}
