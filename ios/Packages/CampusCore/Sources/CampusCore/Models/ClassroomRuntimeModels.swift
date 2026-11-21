import Foundation

// MARK: - Stage document

public enum ClassroomSceneType: String, Sendable, Equatable {
    case slide
    case quiz
    case interactive
    case pbl
    case unknown

    public init(type: String) {
        self = ClassroomSceneType(rawValue: type) ?? .unknown
    }

    public var label: String {
        switch self {
        case .slide: "讲解"
        case .quiz: "练习"
        case .interactive: "互动"
        case .pbl: "项目"
        case .unknown: "场景"
        }
    }
}

public struct ClassroomInteractive: Sendable, Equatable {
    public let html: String?
    public let url: URL?
    public let widgetType: String?
    public let config: JSONValue
    public let invalidReason: String?

    public init(json: JSONValue) {
        let html = json["html"].string?.nonEmpty
        let rawURL = json["url"].string?.nonEmpty
        let widgetType = json["widgetType"].string?.nonEmpty ?? json["widget_type"].string?.nonEmpty
        self.html = html
        self.widgetType = widgetType
        self.config = [json["widgetConfig"], json["widget_config"], json["config"], json["simulation"]]
            .first { $0 != .null } ?? .null
        var parsedURL: URL?
        var reason: String?
        if let rawURL {
            if let url = URL(string: rawURL), ClassroomSandboxPolicy.allowsURL(url) {
                parsedURL = url
            } else {
                reason = "互动内容的地址不是受支持的安全链接。"
            }
        }
        self.url = parsedURL
        self.invalidReason = reason
    }

    /// `widgetType=simulation` 的互动实验可以完全原生执行。
    public var simulation: ClassroomSimulation? {
        guard widgetType == "simulation" else { return nil }
        let simulation = ClassroomSimulation(json: config, fallbackTitle: "互动实验")
        return simulation.parameters.isEmpty ? nil : simulation
    }

    public var kind: ClassroomRenderKind {
        if html != nil { return .sandboxHTML }
        if url != nil { return .sandboxURL }
        return .unsupported
    }
}

public struct ClassroomPBL: Sendable, Equatable {
    public struct Task: Sendable, Equatable, Identifiable {
        public let id: String
        public let title: String
        public let detail: String
    }

    public struct Phase: Sendable, Equatable, Identifiable {
        public let id: String
        public let title: String
        public let detail: String
        public let tasks: [Task]
    }

    public let title: String
    public let detail: String
    public let phases: [Phase]

    public init(json: JSONValue) {
        let project = json["project"].object == nil ? nil : json["project"]
        let title = project?["title"].string?.nonEmpty ?? json["title"].string?.nonEmpty ?? "项目式学习"
        let detail = project?["description"].string?.nonEmpty ?? json["description"].string?.nonEmpty
            ?? "按阶段完成任务，逐步形成最终交付物。"
        var sourcePhases = json["phases"].array ?? []
        if let milestones = project?["milestones"] {
            if let phases = milestones.array {
                sourcePhases = phases
            } else if let tasks = milestones["tasks"].array {
                sourcePhases = [.object([
                    "title": .string(milestones["title"].string?.nonEmpty ?? title),
                    "description": .string(milestones["description"].string?.nonEmpty ?? detail),
                    "tasks": .array(tasks),
                ])]
            }
        }
        var phases = sourcePhases.prefix(6).enumerated().compactMap { index, raw -> Phase? in
            guard raw.object != nil else { return nil }
            let tasks = (raw["tasks"].array ?? []).prefix(6).enumerated().compactMap { taskIndex, taskRaw -> Task? in
                let taskTitle = taskRaw["title"].string?.nonEmpty ?? taskRaw.string?.nonEmpty
                guard let taskTitle else { return nil }
                let id = taskRaw["id"].string?.nonEmpty ?? "task-\(index)-\(taskIndex)"
                return Task(id: id, title: taskTitle, detail: taskRaw["description"].string?.nonEmpty ?? taskTitle)
            }
            let heading = raw["title"].string?.nonEmpty ?? tasks.first?.title ?? "项目阶段"
            guard !tasks.isEmpty else { return nil }
            return Phase(id: raw["id"].string?.nonEmpty ?? "phase-\(index)", title: heading,
                         detail: raw["description"].string?.nonEmpty ?? heading, tasks: tasks)
        }
        if phases.isEmpty, let single = json["tasks"].array {
            let tasks = single.prefix(6).enumerated().compactMap { index, raw -> Task? in
                guard let taskTitle = raw["title"].string?.nonEmpty ?? raw.string?.nonEmpty else { return nil }
                return Task(id: raw["id"].string?.nonEmpty ?? "task-0-\(index)", title: taskTitle,
                            detail: raw["description"].string?.nonEmpty ?? taskTitle)
            }
            if !tasks.isEmpty { phases = [Phase(id: "phase-0", title: title, detail: detail, tasks: tasks)] }
        }
        self.title = title
        self.detail = detail
        self.phases = phases
    }

    public var taskIDs: [String] { phases.flatMap { $0.tasks.map(\.id) } }
    public var isEmpty: Bool { phases.isEmpty }
}

public struct ClassroomPBLProgress: Sendable, Equatable {
    public let completed: Int
    public let total: Int

    public init(pbl: ClassroomPBL, completedIDs: Set<String>) {
        let tasks = pbl.taskIDs
        self.total = tasks.count
        self.completed = tasks.filter { completedIDs.contains($0) }.count
    }

    public var percent: Int { total == 0 ? 0 : Int((Double(completed) / Double(total) * 100).rounded()) }
    public var isFinished: Bool { total > 0 && completed == total }
}

public enum ClassroomSceneContent: Sendable, Equatable {
    case slide(ClassroomSlide)
    case quiz(ClassroomQuizSet)
    case interactive(ClassroomInteractive)
    case pbl(ClassroomPBL)
    case unsupported(type: String, reason: String)

    public var kind: ClassroomSceneType {
        switch self {
        case .slide: .slide
        case .quiz: .quiz
        case .interactive: .interactive
        case .pbl: .pbl
        case .unsupported: .unknown
        }
    }
}

public struct ClassroomScene: Sendable, Equatable, Identifiable {
    public let id: String
    public let title: String
    public let order: Int
    public let type: ClassroomSceneType
    public let content: ClassroomSceneContent
    public let whiteboardCount: Int
    public let hasMultiAgent: Bool

    public init?(json: JSONValue, fallbackIndex: Int, documentWhiteboardCount: Int) {
        guard json.object != nil else { return nil }
        let content = json["content"]
        let rawType = json["type"].string ?? content["type"].string ?? ""
        self.id = json["id"].string?.nonEmpty ?? "scene-\(fallbackIndex)"
        self.title = json["title"].string?.nonEmpty ?? content["title"].string?.nonEmpty ?? "第 \(fallbackIndex + 1) 页"
        self.order = json["order"].int ?? fallbackIndex
        self.type = ClassroomSceneType(type: rawType)
        var boards = max(0, json["whiteboards"].array?.count ?? 0)
        if boards == 0 && documentWhiteboardCount > 0 && fallbackIndex == 0 { boards = documentWhiteboardCount }
        self.whiteboardCount = boards
        self.hasMultiAgent = json["multiAgent"]["enabled"].bool == true
            || json["multi_agent"]["enabled"].bool == true
            || json["multiAgent"].bool == true
            || json["multi_agent"].bool == true
        switch self.type {
        case .slide:
            let slide = ClassroomSlide(json: content)
            self.content = slide.isEmpty ? .unsupported(type: rawType, reason: "这一页没有可读的课件内容。") : .slide(slide)
        case .quiz:
            let quiz = ClassroomQuizSet(json: content)
            self.content = quiz.isEmpty ? .unsupported(type: rawType, reason: "这一页没有题目。") : .quiz(quiz)
        case .interactive:
            let interactive = ClassroomInteractive(json: content)
            self.content = .interactive(interactive)
        case .pbl:
            let pbl = ClassroomPBL(json: content)
            self.content = pbl.isEmpty ? .unsupported(type: rawType, reason: "这个项目还没有可执行阶段。") : .pbl(pbl)
        case .unknown:
            self.content = .unsupported(type: rawType, reason: "这一页的场景类型暂不支持原生播放。")
        }
    }
}

public struct ClassroomStageDocument: Sendable, Equatable {
    public let stageID: String
    public let workspaceID: String
    public let title: String
    public let revision: Int
    public let contentVersion: String?
    public let dslVersion: String
    public let scenes: [ClassroomScene]
    public let whiteboardCanvas: ClassroomCanvas?

    public init(json: JSONValue) throws {
        let container = json["document"].object == nil ? json : json["document"]
        let stage = container["stage"]
        let rawScenes = container["scenes"].array ?? []
        guard !rawScenes.isEmpty else { throw ClassroomNativeError.stageWithoutScenes }
        let whiteboards = stage["whiteboard"].array?.count ?? json["whiteboards"].array?.count ?? 0
        let rawBoard = stage["whiteboard"]
        let boards = rawBoard.array ?? (rawBoard.object != nil ? [rawBoard] : rawScenes.flatMap { $0["whiteboards"].array ?? [] })
        self.whiteboardCanvas = boards.lazy.compactMap { board in
            ClassroomCanvas(json: board["canvas"].object == nil ? board : board["canvas"])
        }.first { !$0.isEmpty }
        self.stageID = json["stage_id"].string?.nonEmpty ?? json["id"].string?.nonEmpty
            ?? stage["id"].string?.nonEmpty ?? "stage"
        self.workspaceID = json["workspace_id"].string?.nonEmpty ?? ""
        self.title = json["title"].string?.nonEmpty ?? stage["name"].string?.nonEmpty ?? "互动课堂"
        self.revision = max(0, json["revision"].int ?? stage["revision"].int ?? container["revision"].int ?? 0)
        self.contentVersion = json["content_version"].string?.nonEmpty ?? container["content_version"].string?.nonEmpty
        self.dslVersion = json["dsl_version"].string ?? container["dslVersion"].string ?? stage["dslVersion"].string ?? ""
        self.scenes = rawScenes.enumerated().compactMap { index, raw in
            ClassroomScene(json: raw, fallbackIndex: index, documentWhiteboardCount: whiteboards)
        }.sorted { $0.order == $1.order ? $0.id < $1.id : $0.order < $1.order }
        guard !self.scenes.isEmpty else { throw ClassroomNativeError.stageWithoutScenes }
    }

    public var scenesByID: [String: ClassroomScene] {
        Dictionary(scenes.map { ($0.id, $0) }, uniquingKeysWith: { first, _ in first })
    }
    public var whiteboardCount: Int { scenes.map(\.whiteboardCount).max() ?? 0 }
}

// MARK: - Narration

public struct ClassroomNarrationState: Sendable, Equatable {
    public let sceneID: String
    public let available: Bool
    public let hasScript: Bool
    public let scriptChars: Int
    public let truncated: Bool
    public let stale: Bool
    public let job: ClassroomGenerationJob?

    public init(json: JSONValue) {
        self.sceneID = json["scene_id"].string ?? ""
        self.available = json["available"].bool ?? false
        self.hasScript = json["has_script"].bool ?? true
        self.scriptChars = json["script_chars"].int ?? 0
        self.truncated = json["truncated"].bool ?? false
        self.stale = json["stale"].bool ?? false
        self.job = json["job"].object.flatMap { try? ClassroomGenerationJob(json: .object($0)) }
    }

    /// 服务端说 `available` 但没有成品时不能算可播放；成品的判据只有 completed + artifact_id。
    public var playableArtifactID: String? {
        guard available || job?.isCompleted == true,
              let job, job.isCompleted, let artifact = job.artifactID
        else { return nil }
        return artifact
    }

    public var isGenerating: Bool { job?.isRunning == true }

    public var failureMessage: String? {
        guard let job, job.isFailed else { return nil }
        switch job.errorCode {
        case "tts_unavailable": return "讲解合成服务暂不可用，可以稍后重试。"
        case "tts_no_speech": return "这一页的文字无法合成为语音。"
        default: return "讲解生成失败，可以重试。"
        }
    }

    public var needsSynthesis: Bool { hasScript && playableArtifactID == nil && !isGenerating }
}

// MARK: - Progress

/// 每个账号、每节课堂独立保存；按 scene id 去重“已访问页”，与 WebView 旧状态不共享。
public struct ClassroomProgress: Codable, Sendable, Equatable {
    public var courseID: String
    public var workspaceID: String
    public var stageID: String
    public var revision: Int
    public var sceneID: String
    public var sceneIndex: Int
    public var visitedSceneIDs: [String]
    public var updatedAt: Date

    public init(courseID: String, workspaceID: String, stageID: String, revision: Int = 0,
                sceneID: String = "", sceneIndex: Int = 0, visitedSceneIDs: [String] = [], updatedAt: Date = Date()) {
        self.courseID = courseID
        self.workspaceID = workspaceID
        self.stageID = stageID
        self.revision = revision
        self.sceneID = sceneID
        self.sceneIndex = sceneIndex
        self.visitedSceneIDs = visitedSceneIDs
        self.updatedAt = updatedAt
    }

    public var visitedPageCount: Int { visitedSceneIDs.count }

    /// 返回是否是第一次到达这一页。往返翻页不会重复计入进度。
    @discardableResult
    public mutating func visit(sceneID: String, index: Int, revision: Int) -> Bool {
        self.sceneID = sceneID
        self.sceneIndex = index
        self.revision = revision
        self.updatedAt = Date()
        guard !sceneID.isEmpty, !visitedSceneIDs.contains(sceneID) else { return false }
        visitedSceneIDs.append(sceneID)
        if visitedSceneIDs.count > 500 { visitedSceneIDs.removeFirst(visitedSceneIDs.count - 500) }
        return true
    }
}

public struct ClassroomLocalState: Codable, Sendable, Equatable {
    public var pblCompleted: [String: [String]]
    public var updatedAt: Date

    public init(pblCompleted: [String: [String]] = [:], updatedAt: Date = Date()) {
        self.pblCompleted = pblCompleted
        self.updatedAt = updatedAt
    }

    public mutating func toggle(taskID: String, sceneID: String) {
        var completed = pblCompleted[sceneID] ?? []
        if let index = completed.firstIndex(of: taskID) { completed.remove(at: index) } else { completed.append(taskID) }
        pblCompleted[sceneID] = completed
        updatedAt = Date()
    }

    public func completed(sceneID: String) -> Set<String> { Set(pblCompleted[sceneID] ?? []) }
}

// MARK: - Simulation

public struct ClassroomSimulation: Sendable, Equatable {
    public struct Parameter: Sendable, Equatable, Identifiable {
        public let id: String
        public let label: String
        public let min: Double
        public let max: Double
        public let step: Double
        public let initial: Double
        public let unit: String

        public init(id: String, label: String, min: Double, max: Double, step: Double, initial: Double, unit: String) {
            self.id = id
            self.label = label
            self.min = min
            self.max = max
            self.step = step
            self.initial = initial
            self.unit = unit
        }
    }

    public struct Result: Sendable, Equatable {
        public let label: String
        public let value: Double
    }

    public struct State: Sendable, Equatable {
        public var values: [String: Double]
        public var result: Result?
        public var hasRun: Bool
    }

    public enum Action: Sendable {
        case set(id: String, value: Double)
        case run
        case reset
    }

    public let title: String
    public let parameters: [Parameter]
    public let formula: String
    public let resultLabel: String

    public init(json: JSONValue, fallbackTitle: String) {
        self.title = json["title"].string?.nonEmpty ?? fallbackTitle
        self.formula = (json["formula"].string ?? "").trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        self.resultLabel = json["resultLabel"].string?.nonEmpty ?? "实验结果"
        self.parameters = (json["parameters"].array ?? []).compactMap { raw -> Parameter? in
            guard let id = raw["id"].string?.nonEmpty else { return nil }
            let lower = raw["min"].double ?? 0
            let upperValue = raw["max"].double ?? max(lower, raw["value"].double ?? 0)
            let upper = Swift.max(lower, upperValue)
            let step = raw["step"].double ?? 1
            let initial = raw["value"].double ?? lower
            return Parameter(id: id, label: raw["label"].string?.nonEmpty ?? id, min: lower, max: upper,
                             step: step > 0 ? step : 1, initial: initial,
                             unit: raw["unit"].string ?? "")
        }
    }

    public func initialState() -> State {
        State(values: parameters.reduce(into: [:]) { result, parameter in
            result[parameter.id] = clamped(parameter, parameter.initial)
        }, result: nil, hasRun: false)
    }

    public func applying(_ action: Action, to state: State) -> State {
        switch action {
        case .reset:
            return initialState()
        case .set(let id, let value):
            guard let parameter = parameters.first(where: { $0.id == id }) else { return state }
            var next = state
            next.values[id] = clamped(parameter, value)
            next.result = nil
            next.hasRun = false
            return next
        case .run:
            var next = state
            next.result = Result(label: resultLabel, value: evaluate(values: state.values))
            next.hasRun = true
            return next
        }
    }

    public func clamped(_ parameter: Parameter, _ raw: Double) -> Double {
        let bounded = Swift.min(parameter.max, Swift.max(parameter.min, raw))
        guard parameter.step > 0 else { return bounded }
        let steps = ((bounded - parameter.min) / parameter.step).rounded()
        let value = parameter.min + steps * parameter.step
        return Swift.min(parameter.max, Swift.max(parameter.min, value))
    }

    public func evaluate(values: [String: Double]) -> Double {
        switch formula {
        case "force / mass":
            let mass = values["mass"] ?? 0
            return mass == 0 ? 0 : rounded((values["force"] ?? 0) / mass)
        case "distance / time":
            let time = values["time"] ?? 0
            return time == 0 ? 0 : rounded((values["distance"] ?? 0) / time)
        default:
            return 0
        }
    }

    private func rounded(_ value: Double) -> Double {
        guard value.isFinite else { return 0 }
        return (value * 10000).rounded() / 10000
    }
}

// MARK: - Sandbox policy

/// iOS 没有 iframe 的 `sandbox` 属性，等价物是「独立、非持久、无脚本桥」的 WKWebView：
/// 它读不到本站 Cookie/存储，也不能回调原生。顶层跳转只允许同一来源。
public enum ClassroomSandboxPolicy {
    public static func allowsURL(_ url: URL) -> Bool {
        guard let scheme = url.scheme?.lowercased(), scheme == "https" || scheme == "http",
              url.user == nil, url.password == nil,
              let host = url.host, !host.isEmpty
        else { return false }
        return true
    }

    public static func allowsHTML(_ html: String) -> Bool {
        !html.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
    }

    /// 返回拦截原因；nil 表示允许这一次顶层导航。
    public static func blockedNavigationReason(target: URL, allowedOrigin: URL?) -> String? {
        guard let scheme = target.scheme?.lowercased() else { return nil }
        if scheme == "about" || scheme == "data" || scheme == "blob" { return nil }
        guard allowsURL(target) else { return "互动内容试图打开不安全的链接。" }
        guard let allowedOrigin else {
            return "互动页没有受信任的来源，已阻止跳转。"
        }
        guard target.scheme?.lowercased() == allowedOrigin.scheme?.lowercased(),
              target.host == allowedOrigin.host,
              target.port == allowedOrigin.port
        else { return "互动内容试图跳转到其他站点，已阻止。" }
        return nil
    }
}

// MARK: - Presentation

public enum ClassroomNativePresentation {
    /// 服务端错误码 / HTTP 状态转成学生能理解的一句话；未知错误保留原文。
    public static func message(for error: any Error, fallback: String) -> String {
        if let api = error as? APIError {
            switch api.code {
            case "scene_not_found": return "这一页已经不在课堂里，已从可播放的第一页继续。"
            case "QUIZ_ATTEMPT_CONFLICT": return "答题记录与服务器不一致，已重新读取，请再提交一次。"
            case "MAGICCLASS_FUSION_UNAVAILABLE": return "互动课堂服务暂不可用，请稍后再试。"
            case "provider_unavailable": return "课堂生成模型当前不可用，已保留原有内容。"
            default: break
            }
            switch api.message {
            case "stage_not_found": return "这节课堂不存在或已被删除。"
            case "revision_conflict": return "课堂内容正在被修改，请重新打开。"
            default: break
            }
            switch api.statusCode {
            case 401, 403: return "登录状态已失效，或没有这门课程的访问权限。"
            case 404: return "这节课堂或其中的页面不存在。"
            case 409: return "当前状态不允许这次操作，请刷新后重试。"
            case 422: return "请求内容不合法。"
            case 503: return "互动课堂服务暂不可用。"
            default: return api.message.isEmpty ? fallback : api.message
            }
        }
        if let native = error as? ClassroomNativeError, let detail = native.errorDescription { return detail }
        return (error as? LocalizedError)?.errorDescription ?? fallback
    }
}
