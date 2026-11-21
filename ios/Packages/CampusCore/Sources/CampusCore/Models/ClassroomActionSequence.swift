import Foundation

/// A single operation in the service-declared classroom `steps` order.
///
/// The service owns the ordering and the `actions` payload. The client only
/// resolves each step through `action_id`; it never reorders or synthesises
/// steps of its own.
public enum ClassroomSequenceOperation: Sendable, Equatable {
    case action(ClassroomPlaybackAction)
    case blocked(actionID: String, type: String, reason: String)

    public var actionID: String {
        switch self {
        case .action(let action):
            return action.id
        case .blocked(let actionID, _, _):
            return actionID
        }
    }

    public var actionType: String {
        switch self {
        case .action(let action):
            return action.type
        case .blocked(_, let type, _):
            return type
        }
    }
}

public struct ClassroomSequencePlan: Sendable, Equatable {
    public let sceneID: String
    public let operations: [ClassroomSequenceOperation]

    public init(sceneID: String, operations: [ClassroomSequenceOperation]) {
        self.sceneID = sceneID
        self.operations = operations
    }

    public var total: Int { operations.count }
    public var isEmpty: Bool { operations.isEmpty }
}

public enum ClassroomActionSequencePlanner {
    /// Build a deterministic, ordered plan from the service response.
    ///
    /// A missing action, a type mismatch, or `supported == false` becomes a
    /// blocked operation instead of being silently skipped. The player must
    /// surface the reason and offer the compatibility entry rather than wait
    /// forever for an action that cannot finish.
    public static func plan(scene: ClassroomPlaybackScene) -> ClassroomSequencePlan {
        var actionsByID: [String: ClassroomPlaybackAction] = [:]
        for action in scene.actions where actionsByID[action.id] == nil {
            actionsByID[action.id] = action
        }

        let operations = scene.steps.map { step -> ClassroomSequenceOperation in
            guard let action = actionsByID[step.actionID] else {
                return .blocked(actionID: step.actionID, type: step.type, reason: "action_missing")
            }
            guard action.supported else {
                return .blocked(actionID: step.actionID, type: action.type, reason: action.reason ?? "action_unsupported")
            }
            if !step.type.isEmpty, step.type != action.type {
                return .blocked(actionID: step.actionID, type: step.type, reason: "action_type_mismatch")
            }
            return .action(action)
        }

        return ClassroomSequencePlan(sceneID: scene.id, operations: operations)
    }

    /// Visual hints are intentionally fire-and-forget; they must not hold the
    /// sequence open while a canvas animation runs.
    public static func isFireAndForget(_ type: String) -> Bool {
        type == "spotlight" || type == "laser"
    }
}