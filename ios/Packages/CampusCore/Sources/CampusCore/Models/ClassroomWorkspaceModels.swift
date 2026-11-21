import Foundation

/// 受管工作台与舞台的公开投影。
///
/// 经典课堂用 `session_id` / `classroom_id` 寻址，受管工作台用
/// `course_id` + `workspace_id` + `stage_id` 寻址；两者之间没有服务端映射，
/// 客户端不能把经典课堂的 session 推导成一个舞台。原生播放只接受后一组标识。
public struct ClassroomWorkspace: Sendable, Equatable, Identifiable, Hashable {
    public let id: String
    public let courseID: String
    public let name: String
    public let detail: String
    public let revision: Int
    public let createdAt: String
    public let updatedAt: String

    public init(json: JSONValue) throws {
        guard let id = json["id"].string?.nonEmpty,
              let courseID = json["course_id"].string?.nonEmpty
        else { throw ClassroomNativeError.invalidResponse("工作台缺少 id 或 course_id") }
        self.id = id
        self.courseID = courseID
        self.name = json["name"].string?.nonEmpty ?? "学习工作台"
        self.detail = json["description"].string?.nonEmpty ?? ""
        self.revision = max(0, json["revision"].int ?? 0)
        self.createdAt = json["created_at"].string ?? ""
        self.updatedAt = json["updated_at"].string ?? ""
    }

    public var displayUpdatedAt: String { updatedAt.nonEmpty ?? "未记录更新时间" }
}

public struct ClassroomStageSummary: Sendable, Equatable, Identifiable, Hashable {
    public let id: String
    public let workspaceID: String
    public let courseID: String
    public let title: String
    public let revision: Int
    public let dslVersion: String
    public let createdAt: String
    public let updatedAt: String

    public init(json: JSONValue) throws {
        guard let id = json["id"].string?.nonEmpty,
              let workspaceID = json["workspace_id"].string?.nonEmpty
        else { throw ClassroomNativeError.invalidResponse("舞台缺少 id 或 workspace_id") }
        self.id = id
        self.workspaceID = workspaceID
        self.courseID = json["course_id"].string ?? ""
        self.title = json["title"].string?.nonEmpty ?? "未命名课堂"
        self.revision = max(0, json["revision"].int ?? 0)
        self.dslVersion = json["dsl_version"].string ?? ""
        self.createdAt = json["created_at"].string ?? ""
        self.updatedAt = json["updated_at"].string ?? ""
    }
}

/// 生成任务（`GET /courses/{course_id}/jobs/{job_id}`）。
///
/// 讲解合成也复用这一形状：`kind=tts`、`artifact_id` 指向 `courses/.../artifacts/...`。
public struct ClassroomGenerationJob: Sendable, Equatable, Identifiable {
    public let id: String
    public let status: String
    public let progress: Int
    public let artifactID: String?
    public let errorCode: String?
    public let sceneID: String?

    public init(json: JSONValue) throws {
        guard let id = json["id"].string?.nonEmpty else {
            throw ClassroomNativeError.invalidResponse("生成任务缺少 id")
        }
        self.id = id
        self.status = json["status"].string ?? "queued"
        self.progress = max(0, min(100, json["progress"].int ?? 0))
        self.artifactID = json["artifact_id"].string?.nonEmpty
        self.errorCode = json["error_code"].string?.nonEmpty
        self.sceneID = json["scene_id"].string?.nonEmpty
    }

    public var isQueued: Bool { status == "queued" }
    public var isRunning: Bool { status == "queued" || status == "running" }
    public var isCompleted: Bool { status == "succeeded" || status == "completed" }
    public var isFailed: Bool { status == "failed" || status == "cancelled" || errorCode != nil }
}

/// `POST /courses/{course_id}/home-generate` 或
/// `POST /courses/{course_id}/workspaces/{workspace_id}/generate` 的受理结果。
public struct ClassroomGenerationHandle: Sendable, Equatable {
    public let workspaceID: String
    public let stageID: String?
    public let source: String?
    public let job: ClassroomGenerationJob?

    public init(json: JSONValue) throws {
        guard let workspaceID = json["workspace_id"].string?.nonEmpty else {
            throw ClassroomNativeError.invalidResponse("生成结果缺少 workspace_id")
        }
        self.workspaceID = workspaceID
        self.stageID = json["stage_id"].string?.nonEmpty
        self.source = json["source"].string?.nonEmpty
        if let job = json["job"].object {
            self.job = try ClassroomGenerationJob(json: .object(job))
        } else {
            self.job = nil
        }
    }

    /// `local-template` 表示服务端模型不可用、拿模板冒充内容；调用方必须拒绝进入。
    public var isLocalTemplate: Bool { source == "local-template" }
}

public enum ClassroomNativeError: LocalizedError, Sendable, Equatable {
    case invalidResponse(String)
    case playbackMismatch(String)
    case stageWithoutScenes
    case emptyGenerationPrompt
    case promptTooLong(Int)

    public var errorDescription: String? {
        switch self {
        case .invalidResponse(let detail): detail
        case .playbackMismatch(let detail): detail
        case .stageWithoutScenes: "这节课堂还没有可播放的场景。"
        case .emptyGenerationPrompt: "请先写下这次要学习的主题。"
        case .promptTooLong(let limit): "主题不能超过 \(limit) 个字符。"
        }
    }
}