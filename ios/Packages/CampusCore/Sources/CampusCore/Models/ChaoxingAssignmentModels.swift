import Foundation

/// 学习通作业快照。只保留题干、选项和逐题对错，不包含学生原始作答或教师评语。
public struct ChaoxingAssignmentContent: Sendable, Equatable {
    public let taskID: String
    public let courseID: String?
    public let status: String
    public let available: Bool
    public let current: Bool
    public let canGenerate: Bool
    public let canGenerateWrong: Bool
    public let resultsAvailable: Bool
    public let resultsComplete: Bool
    public let gradedCount: Int
    public let wrongCount: Int
    public let fetchedAt: String?
    public let questions: [ChaoxingAssignmentQuestion]

    public init(json: JSONValue) throws {
        guard let taskID = json["task_id"].string?.nonEmpty else {
            throw ChaoxingAssignmentError.invalidResponse("作业内容缺少 task_id")
        }
        self.taskID = taskID
        self.courseID = json["course_id"].string?.nonEmpty
        self.status = json["status"].string ?? ""
        self.available = json["available"].bool ?? false
        self.current = json["current"].bool ?? false
        self.canGenerate = json["can_generate"].bool ?? false
        self.canGenerateWrong = json["can_generate_wrong"].bool ?? false
        self.resultsAvailable = json["results_available"].bool ?? false
        self.resultsComplete = json["results_complete"].bool ?? false
        self.gradedCount = json["graded_count"].int ?? 0
        self.wrongCount = json["wrong_count"].int ?? 0
        self.fetchedAt = json["fetched_at"].string?.nonEmpty
        self.questions = json["questions"].array?.map { ChaoxingAssignmentQuestion(json: $0) } ?? []
    }

    public var hasPartialResults: Bool { resultsAvailable && !resultsComplete }
}

public struct ChaoxingAssignmentQuestion: Sendable, Equatable, Identifiable {
    public let number: Int
    public let stem: String
    public let options: [String]
    public let isCorrect: Bool?

    public var id: Int { number }

    public init(json: JSONValue) {
        self.number = json["number"].int ?? 0
        self.stem = json["stem"].string ?? ""
        self.options = json["options"].array?.compactMap(\.string) ?? []
        self.isCorrect = json["is_correct"].bool
    }
}

/// `POST /chaoxing/assignments/{task_id}/classroom` 的生成句柄。
public struct ChaoxingAssignmentReview: Sendable, Equatable {
    public let taskID: String
    public let courseID: String
    public let workspaceID: String
    public let scope: String
    public let questionCount: Int
    public let source: String?
    public let jobID: String?
    public var jobStatus: String
    public var jobProgress: Int
    public let stageID: String?

    public init(json: JSONValue) throws {
        guard let taskID = json["task_id"].string?.nonEmpty,
              let courseID = json["course_id"].string?.nonEmpty,
              let workspaceID = json["workspace_id"].string?.nonEmpty
        else { throw ChaoxingAssignmentError.invalidResponse("课堂生成响应缺少作业/课程/工作台标识") }
        self.taskID = taskID
        self.courseID = courseID
        self.workspaceID = workspaceID
        self.scope = json["scope"].string ?? "all"
        self.questionCount = json["question_count"].int ?? 0
        self.source = json["source"].string?.nonEmpty
        let job = json["job"]
        self.jobID = job["id"].string?.nonEmpty ?? json["job_id"].string?.nonEmpty
        self.jobStatus = job["status"].string ?? "queued"
        self.jobProgress = job["progress"].int ?? 0
        self.stageID = json["stage_id"].string?.nonEmpty
    }

    public var isRunning: Bool { jobStatus == "queued" || jobStatus == "running" }
    public var isCompleted: Bool { jobStatus == "completed" }
    public var pollKey: String { "\(jobID ?? "")-\(jobStatus)" }
}

public struct ChaoxingGenerationJob: Sendable, Equatable {
    public let id: String
    public let status: String
    public let progress: Int
    public let errorCode: String?

    public init(json: JSONValue) throws {
        guard let id = json["id"].string?.nonEmpty else {
            throw ChaoxingAssignmentError.invalidResponse("课堂进度缺少 job id")
        }
        self.id = id
        self.status = json["status"].string ?? "queued"
        self.progress = json["progress"].int ?? 0
        self.errorCode = json["error_code"].string?.nonEmpty
    }
}

public enum ChaoxingAssignmentError: LocalizedError, Sendable, Equatable {
    case invalidResponse(String)

    public var errorDescription: String? {
        switch self {
        case .invalidResponse(let detail): detail
        }
    }
}

/// Stage document 是 DSL。Native 阅读器只投影讲解段落、题目、提示和解析；
/// 不渲染 TTS / whiteboard / 3D 场景，不伪造服务端判分。
public struct ChaoxingLesson: Sendable, Equatable {
    public let title: String
    public let scenes: [ChaoxingLessonScene]

    public var quizCount: Int { scenes.filter { !$0.questions.isEmpty }.count }

    public init(document: JSONValue) throws {
        guard let scenes = document["scenes"].array else {
            throw ChaoxingAssignmentError.invalidResponse("课堂文档缺少 scenes")
        }
        self.title = document["stage"]["name"].string?.nonEmpty
            ?? document["title"].string?.nonEmpty
            ?? "作业复习课堂"
        self.scenes = scenes.enumerated().compactMap { index, raw in
            ChaoxingLessonScene(json: raw, fallbackIndex: index)
        }
        if self.scenes.isEmpty { throw ChaoxingAssignmentError.invalidResponse("课堂文档没有可阅读的场景") }
    }
}

public struct ChaoxingLessonScene: Sendable, Equatable, Identifiable {
    public let id: String
    public let title: String
    public let kind: String
    public let order: Int
    public let blocks: [ChaoxingLessonBlock]
    public let questions: [ChaoxingLessonQuestion]
    public let body: String?

    public init?(json: JSONValue, fallbackIndex: Int) {
        guard json.object != nil else { return nil }
        let content = json["content"]
        let kindValue = json["type"].string ?? content["type"].string ?? "slide"
        self.id = json["id"].string?.nonEmpty ?? "scene-\(fallbackIndex)"
        self.kind = kindValue
        self.title = json["title"].string?.nonEmpty
            ?? content["title"].string?.nonEmpty
            ?? "第 \(fallbackIndex + 1) 页"
        self.order = json["order"].int ?? fallbackIndex
        switch kindValue {
        case "quiz":
            self.blocks = []
            self.questions = (content["questions"].array ?? []).compactMap { ChaoxingLessonQuestion(json: $0) }
            self.body = nil
        case "slide":
            let slide = content["slide"].object == nil ? content : content["slide"]
            self.blocks = Self.parseBlocks(slide)
            self.questions = []
            self.body = slide["body"].string?.nonEmpty
        default:
            self.blocks = []
            self.questions = []
            self.body = content["body"].string?.nonEmpty
                ?? content["html"].string?.nonEmpty
                ?? "这一页需要在线课堂交互能力，当前原生阅读器只展示文字与题目。"
        }
    }

    private static func parseBlocks(_ source: JSONValue) -> [ChaoxingLessonBlock] {
        if let sections = source["sections"].array {
            return sections.compactMap { raw in
                let heading = raw["heading"].string?.nonEmpty
                let bullets = raw["bullets"].array?.compactMap(\.string) ?? []
                return heading == nil && bullets.isEmpty ? nil : ChaoxingLessonBlock(heading: heading, bullets: bullets)
            }
        }
        let bullets = source["bullets"].array?.compactMap(\.string) ?? []
        return bullets.isEmpty ? [] : [ChaoxingLessonBlock(heading: nil, bullets: bullets)]
    }
}

public struct ChaoxingLessonBlock: Sendable, Equatable {
    public let heading: String?
    public let bullets: [String]
}

public struct ChaoxingLessonOption: Sendable, Equatable, Identifiable {
    public let label: String
    public let value: String

    public var id: String { value }
}

public struct ChaoxingLessonQuestion: Sendable, Equatable, Identifiable {
    public let id: String
    public let type: String
    public let prompt: String
    public let options: [ChaoxingLessonOption]
    public let answer: [String]
    public let analysis: String
    public let hints: [String]
    public let exerciseRole: String?
    public let sourceNumber: Int?

    public init?(json: JSONValue) {
        guard let prompt = json["question"].string?.nonEmpty ?? json["stem"].string?.nonEmpty else { return nil }
        self.id = json["id"].string?.nonEmpty ?? "question-\(prompt.hashValue)"
        self.type = json["type"].string ?? "short_answer"
        self.prompt = prompt
        self.options = (json["options"].array ?? []).enumerated().compactMap { index, raw in
            if let label = raw.string {
                return ChaoxingLessonOption(label: label, value: Self.value(from: label, index: index))
            }
            guard let label = raw["label"].string ?? raw["text"].string else { return nil }
            return ChaoxingLessonOption(label: label, value: raw["value"].string ?? label)
        }
        if let answer = json["answer"].string {
            self.answer = [answer]
        } else {
            self.answer = json["answer"].array?.compactMap(\.string) ?? []
        }
        self.analysis = json["analysis"].string?.nonEmpty
            ?? json["explanation"].string?.nonEmpty
            ?? "暂无解析。"
        self.hints = json["hints"].array?.compactMap(\.string) ?? []
        self.exerciseRole = (json["exerciseRole"].string ?? json["exercise_role"].string)?.nonEmpty
        self.sourceNumber = json["sourceQuestionNumber"].int ?? json["source_question_number"].int
    }

    public var isChoice: Bool { !options.isEmpty && type != "short_answer" }
    public var isMultiple: Bool { type == "multiple" }

    public var roleLabel: String {
        switch exerciseRole {
        case "transfer": "变式练习"
        case "retry": "原题重做"
        default: "练习"
        }
    }

    private static func value(from label: String, index: Int) -> String {
        let prefix = label.split(separator: ".").first.map(String.init)?.trimmingCharacters(in: .whitespaces) ?? ""
        if prefix.count == 1, prefix.first?.isLetter == true { return prefix }
        let letters = Array("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        return String(letters[min(index, letters.count - 1)])
    }
}

public enum ChaoxingAssignmentPresentation {
    /// 服务端错误码在 409 时仍会放在 message；把它转成学生能理解的中文。
    public static func message(for error: any Error, fallback: String) -> String {
        if let api = error as? APIError {
            switch api.message {
            case "assignment_results_unavailable": return "还没有取得逐题批改结果，暂时无法单独整理错题"
            case "assignment_no_wrong_questions": return "本次已批改题目中没有错题，不需要生成错题变式课"
            case "assignment_content_not_current": return "还没有取得提交后的题目，请先同步作业"
            case "assignment_images_require_text": return "题目包含尚未识别的图片，暂时无法生成完整讲解"
            case "assignment_content_too_large": return "这份作业内容较长，超出了单次课堂可处理的范围"
            case "assignment_not_ended": return "作业还没有截止，截止后开放复习"
            case "assignment_deadline_unknown": return "作业截止时间未知，请先同步学习通"
            case "assignment_course_unavailable": return "这项作业没有关联课程，暂时无法生成课堂"
            default: break
            }
            switch api.statusCode {
            case 401, 403: return "登录状态已失效，请重新登录"
            case 404: return "这项作业或课堂不存在"
            case 409: return "当前状态不允许该操作，请刷新后重试"
            case 422: return "请求内容不合法"
            case 503: return "互动课堂服务暂不可用"
            default: return api.message.isEmpty ? fallback : api.message
            }
        }
        return (error as? LocalizedError)?.errorDescription ?? fallback
    }
}
