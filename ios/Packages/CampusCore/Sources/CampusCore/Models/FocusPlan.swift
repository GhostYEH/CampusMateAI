import Foundation

public struct FocusPlanStep: Codable, Sendable, Identifiable, Equatable {
    public let id: Int
    public let title: String
    public let description: String
    public let estimatedMinutes: Int
    public let dependencies: [Int]
    public let completionCriteria: String
    public let needsPolicyConfirmation: Bool
    public let knowledgeSource: String
}

public struct FocusPlan: Codable, Sendable, Identifiable, Equatable {
    public let id: UUID
    public let goal: String
    public let mode: String
    public let relatedTaskID: String?
    public let steps: [FocusPlanStep]
    public let warnings: [String]
    public private(set) var completedNumbers: Set<Int> = []
    public private(set) var confirmedPolicyNumbers: Set<Int> = []
    public var completedCount: Int { completedNumbers.count }
    public var isCompleted: Bool { !steps.isEmpty && completedNumbers.count == steps.count }

    public init(json: JSONValue) throws {
        id = UUID(); goal = json["goal"].text; mode = json["mode"].text
        relatedTaskID = json["related_task_id"].string
        warnings = json["warnings"].items.compactMap(\.string)
        steps = try json["steps"].items.map { item in
            guard let number = item["step_number"].int, (1...8).contains(number),
                  let title = item["title"].string?.nonEmpty,
                  let minutes = item["estimated_minutes"].int, (5...120).contains(minutes) else {
                throw APIError(code: "INVALID_PLAN", message: "学习步骤信息不完整，请重新拆解。")
            }
            let dependencies = item["dependencies"].items.compactMap(\.int)
            guard dependencies.allSatisfy({ $0 > 0 && $0 < number }) else { throw APIError(code: "INVALID_PLAN", message: "学习步骤的先后关系无效。") }
            return FocusPlanStep(id: number, title: title, description: item["description"].text, estimatedMinutes: minutes,
                                 dependencies: dependencies, completionCriteria: item["completion_criteria"].text,
                                 needsPolicyConfirmation: item["is_policy_step"].bool == true && item["knowledge_status"].text != "cited",
                                 knowledgeSource: item["knowledge_source"].text)
        }.sorted { $0.id < $1.id }
        let numbers = Set(steps.map(\.id))
        guard !steps.isEmpty, steps.count <= 8, numbers.count == steps.count,
              steps.allSatisfy({ $0.dependencies.allSatisfy(numbers.contains) }) else { throw APIError(code: "INVALID_PLAN", message: "学习计划没有有效的步骤。") }
    }

    public func canStart(number: Int) -> Bool {
        guard let step = steps.first(where: { $0.id == number }) else { return false }
        return step.dependencies.allSatisfy(completedNumbers.contains) && (!step.needsPolicyConfirmation || confirmedPolicyNumbers.contains(number))
    }
    @discardableResult public mutating func markCompleted(number: Int, completed: Bool) -> Bool {
        guard steps.contains(where: { $0.id == number }), !completed || canStart(number: number) else { return false }
        if completed { completedNumbers.insert(number) } else { completedNumbers.remove(number) }
        return true
    }
    public mutating func confirmPolicy(number: Int) { if steps.contains(where: { $0.id == number }) { confirmedPolicyNumbers.insert(number) } }
}
