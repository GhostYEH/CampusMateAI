import Foundation
import Observation
import CampusCore

@MainActor @Observable
final class FocusModel {
    var session: StudySession?
    var plan: FocusPlan?
    var isLoading = false
    var isWorking = false
    var error: String?
    var activeStepNumber: Int?
    @ObservationIgnored private var client: APIClient?
    @ObservationIgnored private var scope = ""
    private struct ActiveStep: Codable, Sendable { let sessionID: String; let planID: UUID; let number: Int }

    func bootstrap(client: APIClient, scope: String) async {
        guard !isLoading else { return }
        self.client = client; self.scope = scope; isLoading = true
        defer { isLoading = false }
        plan = await AccountCache.shared.load(FocusPlan.self, scope: scope, key: "focus-plan.json")
        do {
            session = try await StudyService(client: client).active()
            if let step = await AccountCache.shared.load(ActiveStep.self, scope: scope, key: "focus-step.json"), step.sessionID == session?.id, step.planID == plan?.id { activeStepNumber = step.number }
            else { activeStepNumber = nil }
        }
        catch is CancellationError { }
        catch { self.error = error.localizedDescription }
    }
    func refresh() async {
        guard let client, !isWorking else { return }
        do {
            if let session { self.session = try await StudyService(client: client).session(id: session.id) }
            else { session = try await StudyService(client: client).active() }
        } catch is CancellationError { }
        catch { self.error = error.localizedDescription }
    }
    func start(goal: String, minutes: Int, mode: String, relatedTaskID: String?, stepNumber: Int? = nil) async -> Bool {
        guard let client, !isWorking, !isLoading else { return false }
        isWorking = true; defer { isWorking = false }
        do {
            session = try await StudyService(client: client).start(goal: goal, durationSeconds: minutes * 60, mode: mode, relatedTaskID: relatedTaskID)
            activeStepNumber = stepNumber
            if let stepNumber, let plan, let session { try? await AccountCache.shared.save(ActiveStep(sessionID: session.id, planID: plan.id, number: stepNumber), scope: scope, key: "focus-step.json") }
            return true
        } catch is CancellationError { return false }
        catch { self.error = error.localizedDescription; return false }
    }
    func togglePause() async {
        guard let client, let session, session.isActive, !isWorking else { return }
        isWorking = true; defer { isWorking = false }
        do {
            if session.isPaused { self.session = try await StudyService(client: client).resume(id: session.id) }
            else { self.session = try await StudyService(client: client).pause(id: session.id) }
        } catch is CancellationError { }
        catch { self.error = error.localizedDescription }
    }
    func finish(report: String, tags: [String], completeStep: Bool) async -> Bool {
        guard let client, let session, !isWorking else { return false }
        isWorking = true; defer { isWorking = false }
        do {
            self.session = try await StudyService(client: client).finish(id: session.id, report: report, tags: tags)
            if completeStep, let activeStepNumber { _ = plan?.markCompleted(number: activeStepNumber, completed: true); await savePlan() }
            return true
        } catch is CancellationError { return false }
        catch { self.error = error.localizedDescription; return false }
    }
    func breakdown(goal: String, relatedTaskID: String?) async {
        guard let client, !isWorking, !isLoading else { return }
        isWorking = true; defer { isWorking = false }
        do {
            let value = try await StudyService(client: client).breakdown(goal: goal, taskID: relatedTaskID)
            plan = try FocusPlan(json: value); await savePlan()
        } catch is CancellationError { }
        catch { self.error = error.localizedDescription }
    }
    func markStep(number: Int, completed: Bool) async { _ = plan?.markCompleted(number: number, completed: completed); await savePlan() }
    func confirmPolicy(number: Int) async { plan?.confirmPolicy(number: number); await savePlan() }
    private func savePlan() async {
        guard let plan else { return }
        do { try await AccountCache.shared.save(plan, scope: scope, key: "focus-plan.json") }
        catch { self.error = "学习计划暂未能保存在本机。" }
    }
}
