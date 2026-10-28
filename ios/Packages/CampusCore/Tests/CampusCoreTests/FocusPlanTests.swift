import Foundation
import Testing
@testable import CampusCore

@Suite("Focus plan progression")
struct FocusPlanTests {
    @Test func dependentStepCannotStartBeforePrerequisite() throws {
        var plan = try FocusPlan(json: Self.fixture)
        #expect(!plan.canStart(number: 2))
        let refused = plan.markCompleted(number: 2, completed: true)
        #expect(!refused)
        let accepted = plan.markCompleted(number: 1, completed: true)
        #expect(accepted)
        #expect(plan.canStart(number: 2))
        #expect(plan.completedCount == 1)
        #expect(!plan.isCompleted)
    }

    @Test func unverifiedPolicyStepRequiresExplicitConfirmation() throws {
        var plan = try FocusPlan(json: ["goal": "办理事务", "mode": "rule", "steps": [["step_number": 1, "title": "核对政策", "estimated_minutes": 5, "completion_criteria": "核实官方来源", "is_policy_step": true, "knowledge_status": "needs_confirmation"]]])
        #expect(!plan.canStart(number: 1))
        plan.confirmPolicy(number: 1)
        #expect(plan.canStart(number: 1))
    }

    @Test func planRestoresStableIdentityAndManualProgress() throws {
        var plan = try FocusPlan(json: Self.fixture)
        _ = plan.markCompleted(number: 1, completed: true)
        let restored = try JSONDecoder().decode(FocusPlan.self, from: JSONEncoder().encode(plan))
        #expect(restored.id == plan.id)
        #expect(restored.completedCount == 1)
        #expect(restored.steps.map(\.id) == [1, 2])
    }

    private static var fixture: JSONValue {
        ["goal": "复习章节", "mode": "rule", "steps": [
            ["step_number": 1, "title": "阅读", "estimated_minutes": 10, "completion_criteria": "读完本节", "dependencies": []],
            ["step_number": 2, "title": "练习", "estimated_minutes": 15, "completion_criteria": "完成练习", "dependencies": [1]],
        ]]
    }
}
