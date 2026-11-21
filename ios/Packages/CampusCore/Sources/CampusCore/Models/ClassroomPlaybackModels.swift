import Foundation

/// `render.kind` 是服务端播放计划的唯一判据：`native` 由客户端自渲染，
/// `sandbox-*` 放进受限 Web 容器，`unsupported` 必须带原因显示，不能伪装成空白页。
/// 经典课堂的 `actions`/`media` 也在这一层保留。
public enum ClassroomRenderKind: String, Sendable, Equatable {
    case native
    case sandboxHTML = "sandbox-html"
    case sandboxURL = "sandbox-url"
    case unsupported

    public init(kind: String) {
        self = ClassroomRenderKind(rawValue: kind) ?? .unsupported
    }

    public var requiresSandbox: Bool { self == .sandboxHTML || self == .sandboxURL }
}

public struct ClassroomRender: Sendable, Equatable {
    public let kind: ClassroomRenderKind
    public let sandbox: String?
    public let widgetType: String?
    public let reason: String?

    public init(json: JSONValue) {
        self.kind = ClassroomRenderKind(kind: json["kind"].string ?? "")
        self.sandbox = json["sandbox"].string?.nonEmpty
        self.widgetType = json["widget_type"].string?.nonEmpty
        self.reason = json["reason"].string?.nonEmpty
    }

    public var unsupportedExplanation: String? {
        guard kind == .unsupported else { return nil }
        switch reason {
        case "scene_type_unsupported": return "这一页是当前客户端还不认识的场景类型，需要在网页课堂里查看。"
        case "widget_type_unknown": return "这一页的互动组件不在当前客户端的支持范围内。"
        case "widget_requires_external_cdn": return "这一页依赖外部 3D/CDN 资源，当前网络环境无法加载。"
        case "interactive_payload_missing": return "这一页缺少可播放的互动内容。"
        default: return reason.map { "这一页暂时无法播放（\($0)）。" } ?? "这一页暂时无法播放。"
        }
    }
}

public struct ClassroomActionStep: Sendable, Equatable, Identifiable {
    public let actionID: String
    public let type: String
    /// `sync` 必须按顺序完成；`fire_and_forget` 可以并行。
    public let mode: String

    public var id: String { actionID }
}

public struct ClassroomDroppedAction: Sendable, Equatable, Identifiable {
    public let actionID: String
    public let type: String
    public let reason: String

    public var id: String { actionID }
}

/// 经典播放的原始动作。`payload` 保留动作除 id/type/mode 外的全部字段，
/// `speech` 的成品音频在 `payload.audioUrl` 上，地址只允许本站相对路径。
public struct ClassroomPlaybackAction: Sendable, Equatable, Identifiable {
    public let id: String
    public let type: String
    public let mode: String
    public let supported: Bool
    public let reason: String?
    public let payload: JSONValue

    public init?(json: JSONValue, index: Int) {
        guard json.object != nil else { return nil }
        self.id = json["id"].string?.nonEmpty ?? "action-\(index)"
        self.type = json["type"].string?.nonEmpty ?? "unknown"
        self.mode = json["mode"].string?.nonEmpty ?? "sync"
        self.supported = json["supported"].bool ?? false
        self.reason = json["reason"].string?.nonEmpty
        self.payload = json["payload"].object == nil ? .object([:]) : json["payload"]
    }

    public var audioURL: String? {
        guard type == "speech" else { return nil }
        return payload["audioUrl"].string?.nonEmpty
    }
}

/// 服务端为单个场景登记的媒体。`url` 只有在本站鉴权路径下才存在；
/// `available=false` 时客户端只按 `reason` 降级，不猜上游地址。
public struct ClassroomPlaybackMedia: Sendable, Equatable, Identifiable {
    public let id: String
    public let kind: String
    public let role: String
    public let elementID: String?
    public let contentType: String
    public let url: String?
    public let available: Bool
    public let reason: String?

    public init(json: JSONValue, index: Int) {
        self.id = json["id"].string?.nonEmpty ?? "media-\(index)"
        self.kind = json["kind"].string?.nonEmpty ?? "unknown"
        self.role = json["role"].string?.nonEmpty ?? ""
        self.elementID = json["element_id"].string?.nonEmpty
        self.contentType = json["content_type"].string?.nonEmpty ?? "application/octet-stream"
        self.url = json["url"].string?.nonEmpty
        self.available = json["available"].bool ?? false
        self.reason = json["reason"].string?.nonEmpty
    }
}

public struct ClassroomPlaybackScene: Sendable, Equatable, Identifiable {
    public let id: String
    public let type: String
    public let title: String
    public let order: Int
    public let render: ClassroomRender
    public let steps: [ClassroomActionStep]
    public let droppedActions: [ClassroomDroppedAction]
    public let actions: [ClassroomPlaybackAction]
    public let media: [ClassroomPlaybackMedia]
    public let whiteboardCount: Int
    public let hasMultiAgent: Bool

    public init(json: JSONValue) throws {
        guard let id = json["id"].string?.nonEmpty else {
            throw ClassroomNativeError.invalidResponse("播放计划里的场景缺少 id")
        }
        self.id = id
        self.type = json["type"].string ?? "unknown"
        self.title = json["title"].string?.nonEmpty ?? "未命名页面"
        self.order = json["order"].int ?? 0
        self.render = ClassroomRender(json: json["render"])
        self.steps = json["steps"].array?.compactMap { raw in
            guard let actionID = raw["action_id"].string?.nonEmpty else { return nil }
            return ClassroomActionStep(actionID: actionID, type: raw["type"].string ?? "", mode: raw["mode"].string ?? "sync")
        } ?? []
        self.droppedActions = json["dropped_actions"].array?.compactMap { raw in
            guard let actionID = raw["action_id"].string?.nonEmpty else { return nil }
            return ClassroomDroppedAction(actionID: actionID, type: raw["type"].string ?? "", reason: raw["reason"].string ?? "")
        } ?? []
        self.actions = json["actions"].array?.enumerated().compactMap { index, raw in
            ClassroomPlaybackAction(json: raw, index: index)
        } ?? []
        self.media = json["media"].array?.enumerated().map { index, raw in
            ClassroomPlaybackMedia(json: raw, index: index)
        } ?? []
        self.whiteboardCount = max(0, json["whiteboards"].int ?? 0)
        self.hasMultiAgent = json["multi_agent"].bool ?? false
    }

    public var speechActions: [ClassroomPlaybackAction] {
        actions.filter { $0.type == "speech" }
    }
}

public struct ClassroomPlaybackPlan: Sendable, Equatable {
    public let stageID: String
    public let workspaceID: String
    public let title: String
    public let revision: Int
    /// 经典课堂用正文版本做缓存与刷新判据；受管工作台通常没有这个字段。
    public let contentVersion: String?
    public let dslVersion: String
    public let startIndex: Int
    public let scenes: [ClassroomPlaybackScene]
    public let degraded: [String]

    public init(json: JSONValue) throws {
        guard let stageID = json["stage_id"].string?.nonEmpty,
              let workspaceID = json["workspace_id"].string?.nonEmpty,
              let scenes = json["scenes"].array
        else { throw ClassroomNativeError.invalidResponse("播放计划缺少 stage_id、workspace_id 或 scenes") }
        let parsed = try scenes.map { try ClassroomPlaybackScene(json: $0) }
        guard !parsed.isEmpty else { throw ClassroomNativeError.stageWithoutScenes }
        self.stageID = stageID
        self.workspaceID = workspaceID
        self.title = json["title"].string?.nonEmpty ?? "互动课堂"
        self.revision = max(0, json["revision"].int ?? 0)
        self.contentVersion = json["content_version"].string?.nonEmpty
        self.dslVersion = json["dsl_version"].string ?? ""
        self.startIndex = min(max(0, json["start_index"].int ?? 0), parsed.count - 1)
        self.scenes = parsed
        self.degraded = json["degraded"].array?.compactMap { $0["scene_id"].string?.nonEmpty } ?? []
    }

    public func index(ofScene sceneID: String) -> Int? {
        scenes.firstIndex { $0.id == sceneID }
    }
}

/// 播放计划与舞台文档必须指向同一次 revision、同一批 scene id。任一处不一致，
/// 客户端就不能用“自认为的”顺序播放别人的内容，只能退回网页课堂。
public struct ClassroomPlaybackAvailability: Sendable, Equatable {
    public let isEligible: Bool
    public let detail: String?
    public let degradedSceneIDs: [String]

    public init(isEligible: Bool, detail: String?, degradedSceneIDs: [String]) {
        self.isEligible = isEligible
        self.detail = detail
        self.degradedSceneIDs = degradedSceneIDs
    }

    public static func evaluate(plan: ClassroomPlaybackPlan, document: ClassroomStageDocument) -> ClassroomPlaybackAvailability {
        guard !document.scenes.isEmpty else {
            return ClassroomPlaybackAvailability(isEligible: false, detail: "这节课堂还没有可播放的场景。", degradedSceneIDs: [])
        }
        guard plan.revision == document.revision else {
            return ClassroomPlaybackAvailability(
                isEligible: false,
                detail: "课堂内容已更新（计划第 \(plan.revision) 版 / 文档第 \(document.revision) 版），请重新打开。",
                degradedSceneIDs: [])
        }
        if let planVersion = plan.contentVersion, let documentVersion = document.contentVersion,
           !planVersion.isEmpty, !documentVersion.isEmpty, planVersion != documentVersion {
            return ClassroomPlaybackAvailability(
                isEligible: false,
                detail: "课堂内容版本（\(planVersion) / \(documentVersion)）不一致，请重新打开。",
                degradedSceneIDs: [])
        }
        let planIDs = plan.scenes.map(\.id)
        let documentIDs = Set(document.scenes.map(\.id))
        guard planIDs.count == documentIDs.count, Set(planIDs) == documentIDs else {
            return ClassroomPlaybackAvailability(
                isEligible: false,
                detail: "播放计划的场景与课堂文档不一致，请重新打开这节课堂。",
                degradedSceneIDs: [])
        }
        let degraded = plan.scenes.filter { $0.render.kind == .unsupported }.map(\.id)
        return ClassroomPlaybackAvailability(isEligible: true, detail: nil, degradedSceneIDs: degraded)
    }
}

/// 续播位置：优先回到上次停留的 scene_id；该页已被删除时退回收到的 start_index。
public struct ClassroomResumeDecision: Sendable, Equatable {
    public let index: Int
    public let sceneID: String
    public let restored: Bool
    public let note: String?

    public static func resolve(plan: ClassroomPlaybackPlan, document: ClassroomStageDocument, progress: ClassroomProgress?) -> ClassroomResumeDecision {
        if let progress,
           progress.stageID == plan.stageID,
           let index = plan.index(ofScene: progress.sceneID) {
            return ClassroomResumeDecision(index: index, sceneID: progress.sceneID, restored: true, note: "已回到上次阅读的页面。")
        }
        if let progress, progress.stageID == plan.stageID, !progress.sceneID.isEmpty {
            let fallback = min(max(0, plan.startIndex), plan.scenes.count - 1)
            return ClassroomResumeDecision(index: fallback, sceneID: plan.scenes[fallback].id, restored: false,
                                           note: "上次的页面已不在这节课堂里，从开头继续。")
        }
        let index = min(max(0, plan.startIndex), plan.scenes.count - 1)
        return ClassroomResumeDecision(index: index, sceneID: plan.scenes[index].id, restored: false, note: nil)
    }
}

/// 正文版本 → 稳定 revision。经典 playback 没有数字 revision；
/// 同一份 `content_version` 必须得到同一个值（不能使用 Swift 每次启动随机化的 hash），
/// 否则同一账号的热开快照会被误判成“内容已更新”。
public enum ClassroomContentRevision {
    public static func stable(from version: String) -> Int {
        let trimmed = version.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return 0 }
        var hash: UInt32 = 2_166_136_261
        for byte in trimmed.utf8 {
            hash = (hash ^ UInt32(byte)) &* 16_777_619
        }
        return Int(hash & 0x7FFF_FFFF)
    }
}
