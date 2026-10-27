import SwiftUI
import CampusCore

@MainActor @Observable
final class WorkflowAction {
    var isWorking = false
    var error: String?
    private(set) var pending: GovernedOperation?
    private var scope = ""
    func restore(scope: String) async {
        self.scope = scope
        pending = await AccountCache.shared.load(GovernedOperation.self, scope: scope, key: "pending-workflow.json")
    }
    func perform(client: APIClient, path: String, body: JSONValue = [:]) async -> JSONValue? {
        guard !isWorking else { return nil }
        isWorking = true; error = nil; defer { isWorking = false }
        let operation: GovernedOperation
        if let pending, pending.path == path, pending.body == body { operation = pending }
        else { operation = GovernedOperation(path: path, body: body, keyInBody: path == "student-goals" || (path.hasPrefix("student-goals/") && path.hasSuffix("/progress"))) }
        pending = operation
        if !scope.isEmpty { try? await AccountCache.shared.save(operation, scope: scope, key: "pending-workflow.json") }
        do {
            let result = try await operation.perform(client: client)
            pending = nil
            if !scope.isEmpty { try? await AccountCache.shared.save(Optional<GovernedOperation>.none, scope: scope, key: "pending-workflow.json") }
            return result
        } catch is CancellationError { return nil }
        catch { self.error = error.localizedDescription; return nil }
    }
}

struct WorkflowContentView: View {
    let value: JSONValue
    var depth = 0
    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            if depth > 6 { Text("内容较长，请在产物中继续查看。").font(.caption).foregroundStyle(.secondary) }
            else if let text = value.string { Text(LocalizedStringKey(text.agentStatus)).textSelection(.enabled) }
            else if let array = value.array {
                ForEach(Array(array.prefix(100).enumerated()), id: \.offset) { index, item in
                    HStack(alignment: .top, spacing: 10) {
                        if array.count > 1 { Text("\(index + 1).").foregroundStyle(.secondary).monospacedDigit() }
                        AnyView(WorkflowContentView(value: item, depth: depth + 1))
                    }
                }
            } else if let object = value.object {
                ForEach(object.keys.sorted(), id: \.self) { key in
                    if let label = Self.labels[key], let item = object[key], item != .null, item != .array([]), item != .object([:]), item != .string("") {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(label).font(.subheadline.weight(.semibold)).foregroundStyle(.secondary)
                            if let flag = item.bool { Text(flag ? "是" : "否") }
                            else { AnyView(WorkflowContentView(value: item, depth: depth + 1)) }
                        }
                    }
                }
            }
        }.frame(maxWidth: .infinity, alignment: .leading)
    }
    private static let labels: [String: String] = [
        "step":"步骤", "source_evidence":"原文依据", "audience":"适用对象", "headline":"摘要", "stage":"阶段", "next_action":"下一步建议", "completion_percent":"完成百分比", "planned_minutes":"计划分钟", "allocated_minutes":"安排分钟", "available_minutes":"可用分钟", "item_type":"安排类型", "execution_status":"执行状态", "evidence_type":"依据类别", "relation":"关联说明", "relevance_score":"相关程度", "scheduled_minutes":"计划分钟", "state_type":"状态类别", "forecast_type":"预测类别", "data_quality":"数据质量", "computed_at":"统计时间", "as_of":"数据截至", "valid_until":"有效期", "probability":"估计概率", "evidence_summary":"参考依据", "capabilities":"支持能力", "uses_real_model_inference":"使用真实模型推理", "real_inference_observed":"已观察到真实推理", "read_only_canary_active":"只读试运行已开启", "shadow_results_modify_plans":"辅助结果会修改计划", "campusmate_lm_enabled":"学习模型已启用", "campusmate_lm_affects_production":"学习模型影响实际决策", "fixture_only":"仅固定样例", "observed_sessions_7d":"近 7 天学习次数", "observed_sessions_30d":"近 30 天学习次数", "observed_study_seconds_7d":"近 7 天学习秒数", "observed_study_seconds_30d":"近 30 天学习秒数", "observed_completed_tasks_7d":"近 7 天完成待办", "observed_completed_tasks_30d":"近 30 天完成待办", "known_pending":"已知待办", "known_overdue":"已知逾期", "known_due_24h":"24 小时内到期", "known_due_7d":"7 天内到期", "known_without_deadline":"未设置截止日期", "bucket":"截止压力", "active_goal_count":"进行中目标", "archived_goal_count":"已归档目标", "average_progress_percent":"平均进度百分比", "task_count":"待办数量", "exam_count":"考试数量", "estimated_total_minutes":"预计总分钟", "pressure_band":"负荷区间", "risk_band":"风险区间", "concentrated_dates":"事项集中日期", "conflict_count":"冲突数量", "conflicts":"时间冲突", "data_completeness":"数据完整度", "observed_session_count":"学习次数", "median_duration_minutes":"专注时长中位数", "common_time_slots":"常用学习时段", "rhythm_stability":"学习节奏稳定度", "outlook_band":"进展展望", "goals_with_recent_progress":"近期有进展的目标",
        "title":"标题", "name":"名称", "description":"说明", "summary":"摘要", "content":"内容", "body":"正文", "text":"内容", "reason":"原因", "rationale":"依据", "objective":"目标", "goal":"学习目标", "question":"问题", "answer":"回答", "plan":"计划", "steps":"步骤", "tasks":"任务", "items":"安排", "daily_items":"每日安排", "days":"每日计划", "daily_plan":"每日计划", "schedule":"时间安排", "actions":"建议行动", "recommendations":"建议", "warnings":"提示", "notes":"备注", "evidence":"依据", "sources":"来源", "citations":"参考来源", "topic":"主题", "topics":"知识主题", "chapters":"章节", "chapter":"章节", "course_name":"课程", "exam_date":"考试日期", "date":"日期", "agenda_date":"日期", "start_time":"开始时间", "end_time":"结束时间", "duration_minutes":"时长（分钟）", "estimated_minutes":"预计分钟", "minutes":"分钟", "total_minutes":"总分钟", "daily_capacity_minutes":"每日可用分钟", "feedback":"反馈", "next_steps":"后续建议", "completion_criteria":"完成标准", "success_criteria":"完成标准", "progress_percent":"完成百分比", "status":"状态", "phase":"阶段", "risk_level":"风险程度", "risk":"风险提示", "confidence":"置信度", "uncertainty":"不确定性", "limitations":"适用限制", "model_notes":"模型说明", "disclaimer":"说明", "verified":"已验证", "verification_status":"验证状态", "supporting_quote":"引用片段", "url":"来源链接", "source_title":"来源标题", "learning_items":"学习安排", "milestones":"里程碑", "milestone":"里程碑", "difficulty_notes":"困难", "proposed_changes":"建议变更", "changes":"变更", "proposal":"调整提案", "summary_text":"阶段总结", "evaluation":"评估", "signals":"参考信号", "prediction":"预测", "forecast":"预测", "explanation":"说明", "message":"提示", "label":"名称", "value":"当前值", "data_sources":"数据来源", "source_name":"来源", "source_label":"来源", "effective_assistance_mode":"实际辅助方式", "academic_policy":"学术要求", "claim":"论点", "quotes":"引文", "verification":"验证说明", "report":"研究报告", "outline":"提纲", "sections":"章节", "heading":"小节", "findings":"研究发现", "conclusion":"结论", "practice":"练习", "questions":"问题", "due_at":"截止时间", "deadline":"截止时间", "location":"地点", "submission_method":"提交方式", "materials":"所需材料",
    ]
}

struct ApprovalDecisionView: View {
    @Environment(AppModel.self) private var app
    let approvalID: String
    let summary: String
    var content: JSONValue = .null
    @State private var action = WorkflowAction()
    @State private var reason = ""
    @State private var result: JSONValue?
    @State private var decision: String?
    var body: some View {
        Form {
            Section("待确认的操作") {
                Text(summary.nonEmpty ?? "请先核对关联计划或运行记录中的操作内容。")
                if content != .null { WorkflowContentView(value: content) }
            }
            Section {
                if let result { LabeledContent("审批结果", value: result["status"].text.agentStatus) }
                else {
                    TextField("原因（可选）", text: $reason, axis: .vertical)
                    Button("同意此操作") { decision = "APPROVED" }.disabled(action.isWorking || reason.count > 256)
                    Button("拒绝此操作", role: .destructive) { decision = "REJECTED" }.disabled(action.isWorking || reason.count > 256)
                }
            } header: { Text("你的决定") } footer: { Text("服务端会再次检查权限、有效期及操作状态。过期或冲突不会视为已同意。") }
        }.navigationTitle("操作确认").navigationBarTitleDisplayMode(.inline)
        .task { await action.restore(scope: app.serverURL + "|" + (app.session?.user.id ?? "") + "|approval|" + approvalID) }
        .confirmationDialog("确认\(decision == "APPROVED" ? "同意" : "拒绝")这项操作？", isPresented: Binding(get: { decision != nil }, set: { if !$0 { decision = nil } }), titleVisibility: .visible) {
            Button("确认决定") {
                let value = decision ?? "REJECTED"; decision = nil
                Task { result = await action.perform(client: app.client, path: "agent-approvals/\(approvalID.pathComponent)/decision", body: ["decision": .string(value), "reason": reason.nonEmpty.map(JSONValue.string) ?? .null]) }
            }
        }
        .errorAlert(Binding(get: { action.error }, set: { action.error = $0 }))
    }
}

extension String {
    var agentStatus: String {
        ["QUEUED":"排队中", "RUNNING":"执行中", "AWAITING_APPROVAL":"等待你的确认", "WAITING_CONFIRMATION":"等待你的确认", "PROPOSED":"待确认", "DONE":"已执行", "PAUSED":"已暂停", "SUCCEEDED":"已完成", "PARTIAL":"部分完成", "FAILED":"失败", "CANCELLED":"已取消", "PENDING":"待确认", "APPROVED":"已同意", "REJECTED":"已拒绝", "EXPIRED":"已过期", "UNKNOWN":"未明确", "ALLOWED":"允许", "LIMITED":"有限允许", "EXAM_RESTRICTED":"考试限制", "AI_PROHIBITED":"禁止 AI 辅助", "HINT":"提示", "EXPLAIN":"讲解", "REVIEW":"复习", "FULL_SOLUTION":"完整解答", "TASK_FOCUS":"待办专注", "EXAM_PREPARATION":"考试准备", "CAMPUS_AFFAIRS":"校园事务", "GOAL_PROGRESS":"目标推进", "RESEARCH_OR_COMPETITION":"研究与竞赛", "CAREER_PREPARATION":"职业准备", "RECOVERY_BUFFER":"休息缓冲", "REVIEW_AND_REFLECT":"复盘", "LOW":"低", "MEDIUM":"中", "HIGH":"高", "low":"低", "medium":"中", "high":"高"][self] ?? localizedStatus
    }
}
