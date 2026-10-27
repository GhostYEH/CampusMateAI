import SwiftUI
import CampusCore

struct FocusSetupView: View {
    @Environment(AppModel.self) private var app
    var initialGoal = ""
    var relatedTaskID: String?
    @State private var model = FocusModel()
    @State private var goal = ""
    @State private var minutes = 25
    @State private var mode = "QUIET"
    @State private var showingSession = false

    var body: some View {
        Form {
            if let session = model.session, session.isActive {
                Section("进行中的专注") {
                    Label(session.goal.nonEmpty ?? "专注学习", systemImage: "timer")
                    Text(session.isPaused ? "已暂停，可以继续。" : "会话仍在计时。收起页面不会结束会话。").font(.footnote).foregroundStyle(.secondary)
                    Button("返回专注") { showingSession = true }
                }
            }
            Section("这次想完成什么？") {
                TextField("例如：复习第三章并完成练习", text: $goal, axis: .vertical).lineLimit(2...5)
                Stepper("计划 \(minutes) 分钟", value: $minutes, in: 5...240, step: 5)
                Picker("专注方式", selection: $mode) { Text("安静专注").tag("QUIET"); Text("AI 陪伴").tag("AI_COMPANION") }
            }.disabled(model.session?.isActive == true)
            Section {
                Button(model.isWorking ? "正在准备…" : "开始专注", systemImage: "play.fill") {
                    Task { if await model.start(goal: goal, minutes: minutes, mode: mode, relatedTaskID: relatedTaskID) { showingSession = true } }
                }.disabled(model.isWorking || model.isLoading || model.session?.isActive == true)
                Button("拆解学习目标", systemImage: "list.bullet.indent") { Task { await model.breakdown(goal: goal, relatedTaskID: relatedTaskID) } }
                    .disabled(model.isWorking || model.isLoading || goal.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || model.session?.isActive == true)
            }
            if let plan = model.plan {
                Section {
                    LabeledContent(plan.goal.nonEmpty ?? "学习计划", value: "\(plan.completedCount)/\(plan.steps.count)")
                    Text(plan.mode == "llm" ? "建议由 AI 生成，请按实际情况调整。" : "当前使用规则拆解建议。").font(.caption).foregroundStyle(.secondary)
                    ForEach(plan.warnings, id: \.self) { Text($0).font(.caption).foregroundStyle(.orange) }
                }
                ForEach(plan.steps) { step in
                    Section("步骤 \(step.id)") {
                        Text(step.title).font(.headline)
                        if !step.description.isEmpty { Text(step.description).font(.subheadline) }
                        if !step.completionCriteria.isEmpty { LabeledContent("完成标准", value: step.completionCriteria).font(.footnote) }
                        if let source = step.knowledgeSource.nonEmpty { LabeledContent("参考来源", value: source).font(.footnote) }
                        if step.needsPolicyConfirmation && !plan.confirmedPolicyNumbers.contains(step.id) {
                            Text("涉及学校政策，请先核对学校官方要求。").font(.footnote).foregroundStyle(.orange)
                            Button("我已核实相关要求") { Task { await model.confirmPolicy(number: step.id) } }
                        }
                        Toggle("这一步已完成", isOn: Binding(get: { model.plan?.completedNumbers.contains(step.id) ?? false }, set: { value in Task { await model.markStep(number: step.id, completed: value) } }))
                            .disabled(!plan.canStart(number: step.id) && !plan.completedNumbers.contains(step.id))
                        Button("专注这一项 · \(step.estimatedMinutes) 分钟", systemImage: "play.circle") {
                            Task { if await model.start(goal: step.title, minutes: step.estimatedMinutes, mode: mode, relatedTaskID: plan.relatedTaskID ?? relatedTaskID, stepNumber: step.id) { showingSession = true } }
                        }.disabled(!plan.canStart(number: step.id) || model.isWorking || model.session?.isActive == true)
                    }
                }
            }
            Section {
                NavigationLink { FocusHistoryView() } label: { Label("学习足迹", systemImage: "clock.arrow.circlepath") }
                NavigationLink { StudyCheckinView() } label: { Label("每日目标与签到", systemImage: "calendar.badge.checkmark") }
            }
        }.navigationTitle("自习室")
        .task {
            if !initialGoal.isEmpty { goal = initialGoal }
            await model.bootstrap(client: app.client, scope: app.serverURL + "|" + (app.session?.user.id ?? "") + "|focus")
        }
        .fullScreenCover(isPresented: $showingSession) { NavigationStack { FocusSessionView(model: model) } }
        .errorAlert(Binding(get: { model.error }, set: { model.error = $0 }))
    }
}

struct FocusSessionView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @Environment(\.scenePhase) private var scenePhase
    let model: FocusModel
    @State private var showingFinish = false
    @State private var voice = RealtimeVoiceEngine()
    @State private var wantsVoice = false

    var body: some View {
        Group {
            if let session = model.session {
                if session.isActive {
                    ScrollView {
                        VStack(spacing: 25) {
                            Image(systemName: "leaf.circle.fill").font(.system(size: 62)).foregroundStyle(.tint).padding(.top, 20)
                            Text(session.goal.nonEmpty ?? "专注当下").font(.title2.bold()).multilineTextAlignment(.center)
                            TimelineView(.periodic(from: .now, by: 1)) { context in
                                let elapsed = Int(session.elapsed(at: context.date))
                                VStack(spacing: 12) {
                                    Text(String(format: "%02d:%02d", elapsed / 60, elapsed % 60)).font(.system(size: 68, weight: .semibold, design: .rounded)).monospacedDigit().minimumScaleFactor(0.5)
                                    Text(session.isPaused ? "已暂停" : "专注计时").foregroundStyle(.secondary)
                                    ProgressView(value: min(1, Double(elapsed) / Double(max(1, session.plannedSeconds)))).frame(maxWidth: 340)
                                    Text("计划 \(session.plannedSeconds / 60) 分钟").font(.footnote).foregroundStyle(.secondary)
                                }
                            }
                            HStack(spacing: 18) {
                                Button { Task { await model.togglePause() } } label: { Label(session.isPaused ? "继续" : "暂停", systemImage: session.isPaused ? "play.fill" : "pause.fill").frame(minWidth: 80) }.buttonStyle(.borderedProminent).disabled(model.isWorking)
                                Button("结束", systemImage: "stop.fill") { showingFinish = true }.buttonStyle(.bordered).disabled(model.isWorking)
                            }
                            if session.experienceMode != "QUIET" {
                                VStack(alignment: .leading, spacing: 15) {
                                    HStack { Label("AI 陪伴", systemImage: "waveform"); Spacer(); Text(voice.statusText).font(.caption).foregroundStyle(.secondary) }
                                    if !voice.transcript.userText.isEmpty { Text("你：" + voice.transcript.userText).font(.subheadline) }
                                    if !voice.transcript.assistantText.isEmpty { Text("CampusMate：" + voice.transcript.assistantText).font(.subheadline).textSelection(.enabled) }
                                    if let error = voice.error { Text(error).font(.footnote).foregroundStyle(.secondary) }
                                    Toggle("语音陪伴", isOn: $wantsVoice).disabled(session.isPaused)
                                    if voice.isConnected { Button("打断当前回答", systemImage: "hand.raised") { voice.interrupt() } }
                                    else if wantsVoice && !voice.isConnecting { Button("重新连接") { Task { await voice.start(client: app.client) } }.disabled(session.isPaused) }
                                }.padding(18).background(.regularMaterial, in: RoundedRectangle(cornerRadius: 22))
                            }
                        }.padding(24).frame(maxWidth: 650).frame(maxWidth: .infinity)
                    }.background(Color(uiColor: .systemGroupedBackground))
                } else { FocusSummaryView(session: session) }
            } else { ProgressView("读取会话…") }
        }
        .navigationTitle(model.session?.isActive == true ? "专注" : "本次学习")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar { ToolbarItem(placement: .cancellationAction) { Button(model.session?.isActive == true ? "收起" : "完成") { dismiss() } } }
        .sheet(isPresented: $showingFinish) { NavigationStack { FocusFinishView(model: model) { voice.stop(); wantsVoice = false } } }
        .onChange(of: wantsVoice) { _, value in if value { Task { await voice.start(client: app.client) } } else { voice.stop() } }
        .onChange(of: model.session?.status) { _, status in
            if status != "active" { voice.stop() }
            else if wantsVoice { Task { await voice.start(client: app.client) } }
        }
        .onChange(of: scenePhase) { _, phase in if phase == .active { Task { await model.refresh() } } }
        .task { while !Task.isCancelled { try? await Task.sleep(for: .seconds(10)); if !Task.isCancelled { await model.refresh() } } }
        .onDisappear { voice.stop() }
        .errorAlert(Binding(get: { model.error }, set: { model.error = $0 }))
    }
}

struct FocusFinishView: View {
    @Environment(\.dismiss) private var dismiss
    let model: FocusModel
    let onFinished: () -> Void
    @State private var report = ""
    @State private var tags: Set<String> = []
    @State private var completeStep = false
    private let choices = ["有收获", "专注", "需要复习", "有点疲惫", "有新问题"]
    var body: some View {
        Form {
            Section("这次学习感觉如何？（可选）") { TextField("写下收获或下次要做的事", text: $report, axis: .vertical).lineLimit(4...8) }
            Section("学习感受") {
                ForEach(choices, id: \.self) { tag in
                    Toggle(tag, isOn: Binding(get: { tags.contains(tag) }, set: { if $0 { tags.insert(tag) } else { tags.remove(tag) } }))
                }
            }
            if model.activeStepNumber != nil { Section { Toggle("这一步已实际完成", isOn: $completeStep) } }
            Section {
                Button(model.isWorking ? "正在保存…" : "结束并保存") {
                    Task { if await model.finish(report: report, tags: Array(tags), completeStep: completeStep) { onFinished(); dismiss() } }
                }.disabled(model.isWorking || report.count > 2000)
            } footer: { Text("只记录你主动填写的感受，不根据摄像头画面替你填写。") }
        }.navigationTitle("结束专注").navigationBarTitleDisplayMode(.inline)
        .toolbar { ToolbarItem(placement: .cancellationAction) { Button("返回") { dismiss() }.disabled(model.isWorking) } }
        .errorAlert(Binding(get: { model.error }, set: { model.error = $0 }))
    }
}

struct FocusSummaryView: View {
    let session: StudySession
    var body: some View {
        List {
            Section {
                Label("本次专注已保存", systemImage: "checkmark.circle.fill").foregroundStyle(.green)
                Text(session.goal.nonEmpty ?? "专注学习").font(.title2.bold())
                LabeledContent("专注时长", value: "\(Int(session.elapsed(at: .now)) / 60) 分 \(Int(session.elapsed(at: .now)) % 60) 秒")
                if !session.report.isEmpty { Text(session.report).textSelection(.enabled) }
                let tags = session.json["self_report_tags"].items.compactMap(\.string)
                if !tags.isEmpty { Text(tags.joined(separator: " · ")).font(.subheadline).foregroundStyle(.secondary) }
            }
            if let id = session.relatedTaskID, let task = try? TaskItem(json: ["id": .string(id), "title": "关联待办"]) {
                Section { NavigationLink("查看关联待办") { TaskDetailView(initial: task) } }
            }
        }
    }
}

struct FocusHistoryView: View {
    @Environment(AppModel.self) private var app
    @State private var resource = PagedResource()
    var body: some View {
        List {
            PagedStatusView(resource: resource, emptyTitle: "还没有专注记录", emptyMessage: "完成一次专注，记录你的学习足迹。", icon: "timer", retry: load)
            ForEach(Array(resource.items.enumerated()), id: \.offset) { _, item in
                if let session = try? StudySession(json: item) {
                    NavigationLink {
                        if session.isActive { FocusSetupView() }
                        else { FocusSummaryView(session: session).navigationTitle("专注记录") }
                    } label: {
                        VStack(alignment: .leading, spacing: 6) {
                            Text(session.goal.nonEmpty ?? "专注学习").font(.headline)
                            Text(session.startedAt, format: .dateTime.month().day().hour().minute()).font(.caption).foregroundStyle(.secondary)
                            Text(session.isActive ? session.status.localizedStatus : "\(Int(session.elapsed(at: .now)) / 60) 分钟").font(.caption).foregroundStyle(.secondary)
                            if !session.report.isEmpty { Text(session.report).font(.subheadline).foregroundStyle(.secondary).lineLimit(2) }
                        }.padding(.vertical, 4)
                    }
                }
            }
            LoadMoreRow(resource: resource) { await resource.load(client: app.client, path: "study/sessions", reset: false) }
        }.navigationTitle("学习足迹").task { await load() }.refreshable { await load() }
    }
    private func load() async { await resource.load(client: app.client, path: "study/sessions") }
}

struct StudyCheckinView: View {
    @Environment(AppModel.self) private var app
    @State private var history = RemoteResource()
    @State private var minutes = 60
    @State private var mood = ""
    @State private var scene = "rain"
    @State private var working = false
    @State private var status: String?
    @State private var error: String?
    var body: some View {
        Form {
            Section("每日目标") {
                Stepper("每天 \(minutes) 分钟", value: $minutes, in: 15...480, step: 15)
                Button("保存目标") { perform { _ = try await app.client.request(.put, path: "study/goals/daily", body: ["target_minutes": .number(Double(minutes))]); status = "每日目标已保存。" } }.disabled(working)
            }
            Section("今日签到") {
                Picker("心情场景", selection: $scene) { Text("雨").tag("rain"); Text("雪").tag("snow"); Text("云").tag("cloud") }
                TextField("今天的心情（可选）", text: $mood)
                Button("签到") {
                    perform {
                        let result = try await app.client.request(.post, path: "study/checkins", body: ["scene": .string(scene), "mood": mood.nonEmpty.map(JSONValue.string) ?? .null])
                        status = result["created"].bool == false ? "今天已经签到。" : "签到已保存。"
                        await history.load(client: app.client, path: "study/checkins")
                    }
                }.disabled(working || mood.count > 100)
                if let status { Text(status).font(.footnote).foregroundStyle(.secondary) }
            }
            Section("签到记录") {
                ResourceStateView(resource: history, isEmpty: history.value.items.isEmpty, title: "暂无签到", systemImage: "calendar")
                ForEach(Array(history.value.items.enumerated()), id: \.offset) { _, item in
                    VStack(alignment: .leading, spacing: 5) {
                        Text(item["checkin_date"].string ?? item["date"].string ?? item["created_at"].text).font(.subheadline)
                        if let mood = item["mood"].string?.nonEmpty { Text(mood).foregroundStyle(.secondary) }
                    }
                }
            }
        }.navigationTitle("每日学习")
        .task {
            do { let result = try await app.client.request(path: "study/goals/daily"); minutes = result["target_minutes"].int ?? 60 }
            catch { self.error = error.localizedDescription }
            await history.load(client: app.client, path: "study/checkins")
        }.errorAlert($error)
    }
    private func perform(_ action: @escaping @MainActor () async throws -> Void) {
        working = true
        Task { defer { working = false }; do { try await action() } catch { self.error = error.localizedDescription } }
    }
}
