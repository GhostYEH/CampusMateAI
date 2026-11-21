import Foundation

/// 经典课堂（`session_id` / `classroom_id`）的播放数据已经是完整文档：
/// 每个场景自带 `content`，不需要再读舞台文档。这里把它投影成与受管工作台
/// 相同的 `ClassroomPlaybackPlan` / `ClassroomStageDocument`，让播放器只维护一套
/// 翻页、测验、进度和缓存逻辑。
public struct ClassroomClassicPlayback: Sendable, Equatable {
    public struct Scene: Sendable, Equatable {
        public let id: String
        public let type: String
        public let title: String
        public let order: Int
        public let content: JSONValue
        /// 服务端动作摘要只在这里保留；讲解音频按 `action.id` 关联。
        public let actions: JSONValue
        public let media: JSONValue
        public let warnings: JSONValue
        public let hasMultiAgent: Bool
        public let raw: JSONValue

        init(json: JSONValue, index: Int) {
            self.raw = json
            self.id = json["id"].string?.nonEmpty ?? "scene-\(index)"
            self.type = json["type"].string?.nonEmpty ?? "unknown"
            self.title = json["title"].string?.nonEmpty ?? "第 \(index + 1) 页"
            self.order = json["order"].int ?? index
            self.content = json["content"].object == nil ? .null : json["content"]
            self.actions = json["actions"].array == nil ? .array([]) : json["actions"]
            self.media = json["media"].array == nil ? .array([]) : json["media"]
            self.warnings = json["warnings"].array == nil ? .array([]) : json["warnings"]
            self.hasMultiAgent = json["multi_agent"].bool == true
                || json["multi_agent"]["enabled"].bool == true
                || json["multiAgent"].bool == true
        }

        var planJSON: JSONValue {
            .object([
                "id": .string(id),
                "type": .string(type),
                "title": .string(title),
                "order": .int(order),
                "render": raw["render"],
                "steps": raw["steps"],
                "dropped_actions": raw["dropped_actions"],
                "actions": actions,
                "media": media,
                "whiteboards": raw["whiteboards"],
                "multi_agent": .bool(hasMultiAgent),
            ])
        }

        var stageJSON: JSONValue {
            .object([
                "id": .string(id),
                "type": .string(type),
                "title": .string(title),
                "order": .int(order),
                "content": content,
                "multiAgent": .bool(hasMultiAgent),
            ])
        }
    }

    public let sessionID: String
    public let classroomID: String
    public let courseID: String
    public let title: String
    public let contractVersion: String
    /// 服务端正文哈希。参与 revision、快照刷新和音频缓存键，不能丢弃。
    public let contentVersion: String
    public let revision: Int
    public let startIndex: Int
    public let scenes: [Scene]
    public let degraded: JSONValue

    public init(json: JSONValue) throws {
        guard json.object != nil,
              let rawScenes = json["scenes"].array, !rawScenes.isEmpty
        else { throw ClassroomNativeError.invalidResponse("经典课堂播放数据缺少 scenes") }
        let sessionID = json["session_id"].string?.nonEmpty ?? ""
        let classroomID = json["classroom_id"].string?.nonEmpty ?? ""
        guard !sessionID.isEmpty || !classroomID.isEmpty else {
            throw ClassroomNativeError.invalidResponse("经典课堂播放数据缺少 session_id 与 classroom_id")
        }
        let contentVersion = json["content_version"].string?.nonEmpty
            ?? json["generated_at"].string?.nonEmpty
            ?? ""
        self.sessionID = sessionID
        self.classroomID = classroomID
        self.courseID = json["course_id"].string?.nonEmpty ?? "__self_study__"
        self.title = json["title"].string?.nonEmpty ?? "互动课堂"
        self.contractVersion = json["contract_version"].string?.nonEmpty ?? "classroom-playback/1"
        self.contentVersion = contentVersion
        self.revision = ClassroomContentRevision.stable(from: contentVersion)
        self.startIndex = max(0, json["start_index"].int ?? 0)
        self.scenes = rawScenes.enumerated().map { index, raw in Scene(json: raw, index: index) }
        self.degraded = json["degraded"].array == nil ? .array([]) : json["degraded"]
    }

    public var stageID: String { sessionID.nonEmpty ?? classroomID.nonEmpty ?? "classic" }

    /// 转成原生播放器已有的计划形状。经典课堂没有 workspace/stage 版本，
    /// 用 `content_version` 的稳定哈希作为 revision：同一份响应生成的计划与文档
    /// 互相校验，快照也能区分正文是否更新，绝不跨会话猜测。
    public var planJSON: JSONValue {
        .object([
            "stage_id": .string(stageID),
            "workspace_id": .string(courseID),
            "title": .string(title),
            "revision": .int(revision),
            "content_version": .string(contentVersion),
            "dsl_version": .string(contractVersion),
            "start_index": .int(startIndex),
            "scenes": .array(scenes.map(\.planJSON)),
            "degraded": degraded,
        ])
    }

    public var stageJSON: JSONValue {
        .object([
            "content_version": .string(contentVersion),
            "document": .object([
                "stage": .object(["id": .string(stageID), "name": .string(title), "revision": .int(revision)]),
                "scenes": .array(scenes.map(\.stageJSON)),
            ]),
        ])
    }
}
