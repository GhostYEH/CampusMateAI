import Foundation

public enum ClassroomQuizAnswer: Sendable, Equatable {
    case choice(String)
    case choices([String])
    case text(String)

    public var json: JSONValue {
        switch self {
        case .choice(let value): .string(value)
        case .choices(let values): .array(values.map(JSONValue.string))
        case .text(let value): .string(value)
        }
    }

    public var isEmpty: Bool {
        switch self {
        case .choice(let value): value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        case .choices(let values): values.isEmpty
        case .text(let value): value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
        }
    }

    public static func decode(_ json: JSONValue) -> ClassroomQuizAnswer? {
        if let array = json.array {
            return .choices(array.compactMap(\.string))
        }
        if let value = json.string {
            return .choice(value)
        }
        return nil
    }
}

public struct ClassroomQuizOption: Sendable, Equatable, Identifiable {
    public let label: String
    public let value: String

    public var id: String { value }
}

public struct ClassroomQuizQuestion: Sendable, Equatable, Identifiable {
    public let id: String
    /// `single` / `multiple` / `short`。
    public let type: String
    public let prompt: String
    public let options: [ClassroomQuizOption]
    public let answers: [String]
    public let acceptedAnswers: [String]
    public let analysis: String
    public let points: Double
    public let hints: [String]
    public let sourceQuestionNumber: Int?
    public let exerciseRole: String?

    public init(json: JSONValue, fallbackIndex: Int) {
        let rawType = (json["type"].string ?? "").trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        self.type = Self.shortTypes.contains(rawType) ? "short" : (rawType == "multiple" ? "multiple" : "single")
        self.id = json["id"].string?.nonEmpty ?? "question-\(fallbackIndex + 1)"
        self.prompt = json["question"].string?.nonEmpty
            ?? json["prompt"].string?.nonEmpty
            ?? json["stem"].string?.nonEmpty
            ?? json["text"].string?.nonEmpty
            ?? "未命名题目"
        let options = (json["options"].array ?? []).enumerated().compactMap { index, raw in
            if let label = raw.string?.nonEmpty {
                return ClassroomQuizOption(label: label, value: Self.optionValue(label, index: index))
            }
            let label = raw["label"].string?.nonEmpty ?? raw["text"].string?.nonEmpty ?? "选项 \(index + 1)"
            return ClassroomQuizOption(label: label, value: raw["value"].string?.nonEmpty ?? label)
        }
        self.options = options
        let answerJSON = [json["answer"], json["answers"], json["correctAnswer"]]
            .first { $0 != .null } ?? .null
        let answer = Self.answerStrings(answerJSON, options: options)
        self.answers = Self.unique(Self.normalizingAnswers(answer, options: options))
        let accepted = Self.strings(json["acceptedAnswers"])
        self.acceptedAnswers = accepted.isEmpty ? self.answers : Self.unique(accepted)
        self.analysis = json["analysis"].string?.nonEmpty ?? json["explanation"].string?.nonEmpty ?? json["solution"].string?.nonEmpty ?? "暂无解析。"
        let rawPoints = json["points"].double ?? 0
        self.points = max(0, rawPoints == 0 ? 1 : rawPoints)
        self.hints = (json["hints"].array ?? []).compactMap(\.string).filter { !$0.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty }.prefix(3).map { $0 }
        self.sourceQuestionNumber = json["sourceQuestionNumber"].int ?? json["source_question_number"].int
        self.exerciseRole = (json["exerciseRole"].string ?? json["exercise_role"].string)?.nonEmpty
    }

    public var isMultiple: Bool { type == "multiple" }
    public var isShort: Bool { type == "short" }
    public var isChoice: Bool { !isShort && !options.isEmpty }
    public var correctOptionLabels: [String] {
        options.filter { answers.contains($0.value) }.map(\.label)
    }

    public var roleLabel: String {
        switch exerciseRole {
        case "transfer": "变式练习"
        case "retry": "原题重做"
        default: "练习"
        }
    }

    private static let shortTypes: Set<String> = ["short", "short_answer", "short-answer", "text", "freeform"]

    private static func strings(_ json: JSONValue) -> [String] {
        if let array = json.array { return array.compactMap(\.string) }
        if let value = json.string { return [value] }
        return []
    }

    /// 兼容服务端两种答案形状：选项值字符串/数组，以及 0 基选项序号
    /// （例如 fixture 的 `answer: 0` 对应第一个选项）。数字不能先被
    /// `JSONValue.string` 变成 "0"，否则选项 A 会被判成错误答案。
    private static func answerStrings(_ json: JSONValue, options: [ClassroomQuizOption]) -> [String] {
        if let array = json.array {
            return array.flatMap { answerStrings($0, options: options) }
        }
        if case .number(let value) = json {
            guard value.isFinite, value.rounded() == value else { return [] }
            let index = Int(value)
            guard options.indices.contains(index) else { return [] }
            return [options[index].value]
        }
        if let value = json.string { return [value] }
        return []
    }

    /// 题目答案可能写成选项原文（`ATP`）也可能写成选项值（`A`）。统一到选项值，
    /// 渲染与判分才不会因为两种写法得到相反结果。
    private static func normalizingAnswers(_ values: [String], options: [ClassroomQuizOption]) -> [String] {
        let optionValues = Set(options.map(\.value))
        var labelToValue: [String: String] = [:]
        for option in options where labelToValue[option.label] == nil {
            labelToValue[option.label] = option.value
        }
        return values.map { value in
            if optionValues.contains(value) { return value }
            return labelToValue[value] ?? value
        }
    }

    private static func unique(_ values: [String]) -> [String] {
        var seen = Set<String>()
        return values.compactMap { raw in
            let value = raw.trimmingCharacters(in: .whitespacesAndNewlines)
            guard !value.isEmpty, !seen.contains(value) else { return nil }
            seen.insert(value)
            return value
        }
    }

    private static func optionValue(_ label: String, index: Int) -> String {
        let prefix = label.split(separator: ".").first.map(String.init)?.trimmingCharacters(in: .whitespaces) ?? ""
        if prefix.count == 1, prefix.first?.isLetter == true { return prefix }
        let letters = Array("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
        return String(letters[min(index, letters.count - 1)])
    }
}

/// 测验场景的完整内容。`learningProfile=assignment_review` 时简答题不自动判分，
/// 与 Web 原生课堂的 `studentLed` 规则一致。
public struct ClassroomQuizSet: Sendable, Equatable {
    public let questions: [ClassroomQuizQuestion]
    public let studentLed: Bool

    public init(json: JSONValue) {
        self.questions = (json["questions"].array ?? []).enumerated().map { index, raw in
            ClassroomQuizQuestion(json: raw, fallbackIndex: index)
        }
        self.studentLed = (json["learningProfile"].string ?? json["learning_profile"].string) == "assignment_review"
    }

    public var isEmpty: Bool { questions.isEmpty }
    public var totalPoints: Double { questions.reduce(0) { $0 + $1.points } }
}

public struct ClassroomQuizEvaluation: Sendable, Equatable {
    public struct Result: Sendable, Equatable, Identifiable {
        public let questionID: String
        public let correct: Bool?
        public let earned: Double
        public let analysis: String

        public var id: String { questionID }
    }

    public let score: Double
    public let total: Double
    public let results: [Result]

    public static let empty = ClassroomQuizEvaluation(score: 0, total: 0, results: [])

    public init(score: Double, total: Double, results: [Result]) {
        self.score = score
        self.total = total
        self.results = results
    }

    public static func evaluate(questions: [ClassroomQuizQuestion], answers: [String: ClassroomQuizAnswer],
                                studentLed: Bool) -> ClassroomQuizEvaluation {
        let results = questions.map { question -> Result in
            let answer = answers[question.id]
            let answered: Bool
            switch answer {
            case .some(.choices(let values)): answered = !values.isEmpty
            case .some(.choice(let value)): answered = !value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            case .some(.text(let value)): answered = !value.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            case .none: answered = false
            }
            let graded = studentLed && (question.isShort || !answered) ? nil : isCorrect(question: question, answer: answer)
            return Result(questionID: question.id, correct: graded,
                          earned: graded == true ? question.points : 0, analysis: question.analysis)
        }
        return ClassroomQuizEvaluation(score: results.reduce(0) { $0 + $1.earned },
                                       total: zip(questions, results).reduce(0) { $0 + ($1.1.correct == nil ? 0 : $1.0.points) },
                                       results: results)
    }

    public func jsonResults() -> [JSONValue] {
        results.map { result in
            var object: [String: JSONValue] = [
                "questionId": .string(result.questionID),
                "earned": .number(result.earned),
                "analysis": .string(result.analysis),
            ]
            object["correct"] = result.correct.map(JSONValue.bool) ?? .null
            return .object(object)
        }
    }

    private static func isCorrect(question: ClassroomQuizQuestion, answer: ClassroomQuizAnswer?) -> Bool {
        guard let answer else { return false }
        switch question.type {
        case "short":
            let actual = normalizedText(value: answer)
            return question.acceptedAnswers.contains { normalizedText(value: .text($0)) == actual }
        case "multiple":
            guard case .choices(let values) = answer else { return false }
            return Set(values.map(normalizedToken)) == Set(question.answers.map(normalizedToken))
        default:
            let value: String
            switch answer {
            case .choice(let item): value = item
            case .text(let item): value = item
            case .choices(let items): value = items.first ?? ""
            }
            return Set([normalizedToken(value)]) == Set(question.answers.map(normalizedToken))
        }
    }

    private static func normalizedText(value: ClassroomQuizAnswer) -> String {
        let raw: String
        switch value {
        case .text(let text): raw = text
        case .choice(let choice): raw = choice
        case .choices(let choices): raw = choices.joined()
        }
        return raw.lowercased().filter { !$0.isWhitespace }
    }

    private static func normalizedToken(_ value: String) -> String {
        value.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
    }
}

/// `GET/POST .../quiz-attempt` 的响应。`phase` 是 `draft` / `submitted` / `reviewed`。
public struct ClassroomQuizAttempt: Sendable, Equatable {
    public let attemptID: String
    public let phase: String
    public let answers: [String: ClassroomQuizAnswer]
    public let results: [JSONValue]

    public init(json: JSONValue) throws {
        guard let attemptID = json["attempt_id"].string?.nonEmpty else {
            throw ClassroomNativeError.invalidResponse("测验作答缺少 attempt_id")
        }
        self.attemptID = attemptID
        self.phase = json["state"]["phase"].string ?? "draft"
        var parsed: [String: ClassroomQuizAnswer] = [:]
        for (key, value) in json["state"]["answers"].object ?? [:] {
            if let answer = ClassroomQuizAnswer.decode(value) { parsed[key] = answer }
        }
        self.answers = parsed
        self.results = json["state"]["results"].array ?? []
    }

    public var isSubmitted: Bool { phase == "submitted" }
    public var isReviewed: Bool { phase == "reviewed" }
    public var hasAnswers: Bool { !answers.isEmpty }

    /// 把服务端保存的字符串恢复成对应题型：简答题要作为文本参与判分。
    public func answer(for question: ClassroomQuizQuestion) -> ClassroomQuizAnswer? {
        guard let stored = answers[question.id] else { return nil }
        if question.isShort {
            if case .choice(let value) = stored { return .text(value) }
        }
        return stored
    }
}
