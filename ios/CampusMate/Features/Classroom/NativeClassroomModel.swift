import Foundation
import Observation
import AVFoundation
import SwiftUI
import CampusCore

/// 原生播放器的唯一可见状态源。网络与资源处理在异步任务里完成，所有写状态都回到 MainActor。
@MainActor
@Observable
final class NativeClassroomModel {
    enum LoadPhase: Equatable {
        case loading
        case ready
        case failed(String)
    }

    enum NarrationPhase: Equatable {
        case checking
        case none
        case available
        case generating(Int)
        case loadingAudio
        case ready
        case playing
        case failed(String)
    }

    struct SceneInfo: Identifiable, Equatable {
        let id: String
        let title: String
        let type: ClassroomSceneType
        let render: ClassroomRenderKind
        let visited: Bool
    }

    enum QuizPhase: Equatable {
        case answering
        case reviewed
        case submitting
    }

    struct QuizSession {
        var attemptID: String
        var phase: QuizPhase
        var answers: [String: ClassroomQuizAnswer]
        var evaluation: ClassroomQuizEvaluation?
        var hintsShown: [String: Int]
        var message: String?
        var needsSync: Bool
        var startNewOnNextSave: Bool

        var answeredCount: Int {
            answers.values.filter { !$0.isEmpty }.count
        }
    }

    struct SequenceState: Equatable {
        let sceneID: String
        let total: Int
        var completed: Int
        var currentIndex: Int
        var currentActionID: String?
        var active: Bool
        var paused: Bool
        var message: String?
    }

    struct SequenceVideo: Identifiable, Equatable {
        let id = UUID()
        let url: URL
        let title: String

        init(url: URL, title: String) {
            self.url = url
            self.title = title
        }
    }

    let courseID: String
    let workspaceID: String
    let stageID: String
    let accountKey: String

    private(set) var phase: LoadPhase = .loading
    private(set) var plan: ClassroomPlaybackPlan?
    private(set) var document: ClassroomStageDocument?
    private(set) var index = 0
    private(set) var restoredFromCache = false
    private(set) var resumeNote: String?
    private(set) var notice: String?
    private(set) var quiz: QuizSession?
    private(set) var quizError: String?
    private(set) var narrationPhase: NarrationPhase = .checking
    private(set) var narrationNotice: String?
    private(set) var narrationIsPaused = false
    private(set) var classicAudio: ClassroomSpeechAudio?
    private(set) var classicAudioReason: String?
    private(set) var sequence: SequenceState?
    private(set) var sequenceVideo: SequenceVideo?

    var title = "互动课堂"

    @ObservationIgnored private let service: NativeClassroomService
    @ObservationIgnored private let client: APIClient
    @ObservationIgnored private let classic: ClassicBinding?
    @ObservationIgnored private let cache = AccountCache.shared
    @ObservationIgnored private let audioCache = ClassroomAudioCache.shared
    @ObservationIgnored private let player = ClassroomNarrationPlayer()
    @ObservationIgnored private let images = ClassroomImageCache.shared
    @ObservationIgnored private var rawPlan: JSONValue?
    @ObservationIgnored private var rawStage: JSONValue?
    private var progress = ClassroomProgress(courseID: "", workspaceID: "", stageID: "")
    private var localState = ClassroomLocalState()
    @ObservationIgnored private var narrationTask: Task<Void, Never>?
    @ObservationIgnored private var draftTask: Task<Void, Never>?
    @ObservationIgnored private var quizLoadTask: Task<Void, Never>?
    @ObservationIgnored private var quizSubmitTask: Task<Void, Never>?
    @ObservationIgnored private var quizSyncTask: Task<Void, Never>?
    @ObservationIgnored private var saveTask: Task<Void, Never>?
    @ObservationIgnored private var stateTask: Task<Void, Never>?
    /// 本地作答代次与轮次：同步/提交/重做期间翻页、换号或改答案后，迟到响应不能写回。
    @ObservationIgnored private var quizSceneGeneration = 0
    @ObservationIgnored private var quizAnswerVersion = 0
    @ObservationIgnored private var quizRound = 0
    @ObservationIgnored private var submittingQuiz = false
    @ObservationIgnored private var syncingQuiz = false
    @ObservationIgnored private let quizWriteGate = ClassroomQuizWriteGate()
    @ObservationIgnored private var started = false
    @ObservationIgnored private var revisionToken = UUID()
    @ObservationIgnored private var pageTurnStartedAt: Date?
    @ObservationIgnored private var firstReadReported = false
    @ObservationIgnored private var lastPlaybackMs: Int?
    @ObservationIgnored private var sequenceTask: Task<Void, Never>?
    @ObservationIgnored private var sequenceToken = UUID()
    @ObservationIgnored private var sequenceAudioContinuation: CheckedContinuation<Bool, Never>?
    @ObservationIgnored private var sequenceAudioToken: UUID?
    @ObservationIgnored private var sequenceAudioActionID: String?
    @ObservationIgnored private var sequenceAudioFailure: String?
    @ObservationIgnored private var sequenceVideoContinuation: CheckedContinuation<Bool, Never>?
    @ObservationIgnored private var sequenceVideoToken: UUID?
    @ObservationIgnored private var sequenceVideoActionID: String?
    private var simulationStates: [String: ClassroomSimulation.State] = [:]

    init(courseID: String, workspaceID: String, stageID: String, title: String? = nil,
         client: APIClient, accountKey: String, classicScope: ClassroomScope? = nil) {
        self.client = client
        self.service = NativeClassroomService(client: client)
        self.accountKey = accountKey
        if let classicScope {
            self.classic = ClassicBinding(scope: classicScope, sessionID: stageID)
            if case .course(let course) = classicScope {
                self.courseID = course
            } else {
                self.courseID = "__self_study__"
            }
            self.workspaceID = "classic"
            self.stageID = stageID
        } else {
            self.classic = nil
            self.courseID = courseID
            self.workspaceID = workspaceID
            self.stageID = stageID
        }
        if let title, !title.isEmpty { self.title = title }
        player.onFinish = { [weak self] in self?.handleAudioFinished() }
        player.onInterruption = { [weak self] in self?.handleAudioInterrupted() }
    }

    // MARK: - Derived state

    var scenes: [ClassroomPlaybackScene] { plan?.scenes ?? [] }
    var sceneCount: Int { scenes.count }
    var currentPlaybackScene: ClassroomPlaybackScene? {
        guard let plan, plan.scenes.indices.contains(index) else { return nil }
        return plan.scenes[index]
    }
    var currentScene: ClassroomScene? {
        guard let document, let id = currentPlaybackScene?.id else { return nil }
        return document.scenesByID[id]
    }
    var currentContent: ClassroomSceneContent? { currentScene?.content }
    var currentRender: ClassroomRenderKind { currentPlaybackScene?.render.kind ?? .native }
    var currentSceneID: String { currentPlaybackScene?.id ?? "" }
    var currentQuizSet: ClassroomQuizSet? {
        if case .quiz(let set)? = currentContent { return set }
        return nil
    }
    var canGoPrevious: Bool { index > 0 }
    var canGoNext: Bool { index + 1 < sceneCount }
    var pageLabel: String { sceneCount == 0 ? "准备中" : "第 \(index + 1) / \(sceneCount) 页" }
    var progressFraction: Double { sceneCount <= 1 ? 1 : Double(index) / Double(sceneCount - 1) }
    var sceneInfos: [SceneInfo] {
        guard let plan, let document else { return [] }
        return plan.scenes.enumerated().map { offset, scene in
            SceneInfo(id: scene.id, title: scene.title, type: ClassroomSceneType(type: scene.type),
                      render: scene.render.kind, visited: progress.visitedSceneIDs.contains(scene.id))
        }
    }
    var hasWhiteboardOnPage: Bool { (currentPlaybackScene?.whiteboardCount ?? 0) > 0 }
    var hasMultiAgentOnPage: Bool { currentPlaybackScene?.hasMultiAgent == true }
    var downgradedScenes: [String] { plan?.degraded ?? [] }
    var pblCompleted: Set<String> {
        guard let scene = currentScene else { return [] }
        return localState.completed(sceneID: scene.id)
    }
    var currentSimulation: ClassroomSimulation? {
        guard case .interactive(let interactive)? = currentContent else { return nil }
        return interactive.simulation
    }
    var simulationState: ClassroomSimulation.State? {
        guard let scene = currentScene, let simulation = currentSimulation else { return nil }
        return simulationStates[scene.id] ?? simulation.initialState()
    }
    var audioIsPlaying: Bool { player.isPlaying }
    var isClassicSession: Bool { classic != nil }

    var hasSequenceSteps: Bool {
        guard let scene = currentPlaybackScene else { return false }
        return !scene.steps.isEmpty
    }

    var sequenceTitle: String {
        guard let sequence else { return "顺序播放课堂动作" }
        if sequence.active {
            return "顺序动作 \(sequence.completed)/\(sequence.total)"
        }
        if sequence.completed >= sequence.total {
            return "顺序动作已完成 \(sequence.completed)/\(sequence.total)"
        }
        return "顺序动作 \(sequence.completed)/\(sequence.total)"
    }

    var sequenceCurrentLabel: String? {
        guard let actionID = sequence?.currentActionID,
              let action = currentPlaybackScene?.actions.first(where: { $0.id == actionID })
        else { return nil }
        switch action.type {
        case "speech": return "教师讲解"
        case "play_video": return "播放视频"
        case "wb_open", "wb_close", "wb_draw": return "白板"
        case "spotlight": return "聚光灯"
        case "laser": return "激光笔"
        case "widget_highlight", "widget_setState", "widget_annotation", "widget_reveal":
            return "互动组件"
        default: return action.type
        }
    }

    /// Current session's authenticated media base. Used only for defensive
    /// relative image payloads; absolute `/api/v1/` links keep their own path.
    var mediaBasePath: String? {
        guard let classic, let base = try? classic.scope.validatedPath() else { return nil }
        return base + "/" + classic.sessionID.pathComponent + "/media/"
    }

    // MARK: - Open

    func open() async {
        guard !started else { return }
        started = true
        let token = UUID()
        revisionToken = token
        pageTurnStartedAt = nil
        firstReadReported = false
        lastPlaybackMs = nil
        ClassroomPerformanceProbe.shared.begin(stageKey: cacheKey)
        await loadCachedSnapshot()
        await refreshFromNetwork(token: token)
    }

    private func loadCachedSnapshot() async {
        let savedProgress: ClassroomProgress? = await cache.load(ClassroomProgress.self, scope: scope, key: "progress.json")
        if let savedProgress, savedProgress.stageID == stageID { progress = savedProgress }
        if let local: ClassroomLocalState = await cache.load(ClassroomLocalState.self, scope: scope, key: "state.json") {
            localState = local
        }
        guard let snapshot: StageSnapshot = await cache.load(StageSnapshot.self, scope: scope, key: "stage.json"),
              let cachedPlan = try? ClassroomPlaybackPlan(json: snapshot.plan),
              let cachedDocument = try? ClassroomStageDocument(json: snapshot.stage)
        else { return }
        rawPlan = snapshot.plan
        rawStage = snapshot.stage
        apply(plan: cachedPlan, document: cachedDocument, savedProgress: savedProgress, fromCache: true)
        phase = .ready
        restoredFromCache = true
        sceneDidChange(previous: nil, autoplayNarration: false)
    }

    private func refreshFromNetwork(token: UUID) async {
        if let classic {
            await refreshClassic(token: token, binding: classic)
            return
        }
        do {
            let startedAt = Date()
            async let playbackJSON = service.playbackJSON(
                courseID: courseID, workspaceID: workspaceID, stageID: stageID,
                sceneID: progress.sceneID.isEmpty ? nil : progress.sceneID)
            async let stageJSON = service.stageEnvelope(courseID: courseID, workspaceID: workspaceID, stageID: stageID)
            let (planJSON, documentJSON) = try await (playbackJSON, stageJSON)
            let playbackMs = Int(Date().timeIntervalSince(startedAt) * 1000 / 2)
            guard revisionToken == token else { return }
            let fetchedPlan = try ClassroomPlaybackPlan(json: planJSON)
            let fetchedDocument = try ClassroomStageDocument(json: documentJSON)
            let availability = ClassroomPlaybackAvailability.evaluate(plan: fetchedPlan, document: fetchedDocument)
            guard availability.isEligible else {
                throw ClassroomNativeError.playbackMismatch(availability.detail ?? "播放计划与课堂文档不一致。")
            }
            let savedProgress: ClassroomProgress? = progress.stageID == stageID ? progress : nil
            let previousSceneID = currentSceneID
            let previousRevision = plan?.revision
            apply(plan: fetchedPlan, document: fetchedDocument, savedProgress: savedProgress, fromCache: false)
            rawPlan = planJSON
            rawStage = documentJSON
            await persistSnapshot()
            phase = .ready
            restoredFromCache = false
            lastPlaybackMs = playbackMs
            if previousSceneID.isEmpty || previousSceneID != currentSceneID || previousRevision != fetchedPlan.revision {
                sceneDidChange(previous: previousSceneID.isEmpty ? nil : previousSceneID, autoplayNarration: false)
            }
        } catch is CancellationError {
            return
        } catch {
            guard revisionToken == token else { return }
            if phase == .ready {
                notice = ClassroomNativePresentation.message(for: error, fallback: "课堂刷新失败，正在使用本地缓存。")
            } else {
                phase = .failed(ClassroomNativePresentation.message(for: error, fallback: "这节课堂打不开。"))
            }
            ClassroomPerformanceProbe.shared.markNetworkFailed(stageKey: cacheKey)
        }
    }

    /// 经典课堂没有舞台文档接口，`playback` 响应本身已经带每个场景的 content。
    /// 这里投影成同一份计划/文档后，后面的翻页、测验、进度与缓存逻辑完全复用。
    private func refreshClassic(token: UUID, binding: ClassicBinding) async {
        do {
            let startedAt = Date()
            let service = ClassroomService(client: client, scope: binding.scope)
            let json = try await service.playbackJSON(
                sessionID: binding.sessionID, sceneID: progress.sceneID.isEmpty ? nil : progress.sceneID)
            let playbackMs = Int(Date().timeIntervalSince(startedAt) * 1000)
            guard revisionToken == token else { return }
            let classic = try ClassroomClassicPlayback(json: json)
            let fetchedPlan = try ClassroomPlaybackPlan(json: classic.planJSON)
            let fetchedDocument = try ClassroomStageDocument(json: classic.stageJSON)
            let availability = ClassroomPlaybackAvailability.evaluate(plan: fetchedPlan, document: fetchedDocument)
            guard availability.isEligible else {
                throw ClassroomNativeError.playbackMismatch(availability.detail ?? "经典课堂播放数据不一致。")
            }
            let savedProgress: ClassroomProgress? = progress.stageID == stageID ? progress : nil
            let previousSceneID = currentSceneID
            let previousRevision = plan?.revision
            apply(plan: fetchedPlan, document: fetchedDocument, savedProgress: savedProgress, fromCache: false)
            rawPlan = classic.planJSON
            rawStage = classic.stageJSON
            await persistSnapshot()
            phase = .ready
            restoredFromCache = false
            lastPlaybackMs = playbackMs
            if previousSceneID.isEmpty || previousSceneID != currentSceneID || previousRevision != fetchedPlan.revision {
                sceneDidChange(previous: previousSceneID.isEmpty ? nil : previousSceneID, autoplayNarration: false)
            }
        } catch is CancellationError {
            return
        } catch {
            guard revisionToken == token else { return }
            if phase == .ready {
                notice = ClassroomNativePresentation.message(for: error, fallback: "经典课堂刷新失败，正在使用本地缓存。")
            } else {
                phase = .failed(ClassroomNativePresentation.message(for: error, fallback: "这节经典课堂打不开。"))
            }
            ClassroomPerformanceProbe.shared.markNetworkFailed(stageKey: cacheKey)
        }
    }

    private func apply(plan: ClassroomPlaybackPlan, document: ClassroomStageDocument,
                       savedProgress: ClassroomProgress?, fromCache: Bool) {
        self.plan = plan
        self.document = document
        if self.title.isEmpty || self.title == "互动课堂" { self.title = plan.title }
        var resolved = savedProgress ?? ClassroomProgress(courseID: courseID, workspaceID: workspaceID, stageID: stageID)
        if resolved.stageID != stageID || resolved.courseID != courseID || resolved.workspaceID != workspaceID {
            resolved = ClassroomProgress(courseID: courseID, workspaceID: workspaceID, stageID: stageID)
        }
        resolved.stageID = stageID
        let decision = ClassroomResumeDecision.resolve(plan: plan, document: document, progress: savedProgress)
        index = decision.index
        resumeNote = decision.note
        progress = resolved
        progress.visit(sceneID: decision.sceneID, index: decision.index, revision: plan.revision)
        images.removeAll()
    }

    // MARK: - Navigation

    func go(to newIndex: Int) {
        guard scenes.indices.contains(newIndex), newIndex != index else { return }
        let previous = currentSceneID
        index = newIndex
        pageTurnStartedAt = Date()
        let sceneID = currentSceneID
        let revision = plan?.revision ?? 0
        let firstVisit = progress.visit(sceneID: sceneID, index: newIndex, revision: revision)
        if firstVisit { ClassroomPerformanceProbe.shared.recordVisit(stageKey: cacheKey) }
        sceneDidChange(previous: previous, autoplayNarration: false)
        saveProgress()
    }

    func next() { go(to: index + 1) }
    func previous() { go(to: index - 1) }

    func jump(to sceneID: String) {
        guard let target = plan?.index(ofScene: sceneID) else { return }
        go(to: target)
    }

    private func sceneDidChange(previous: String?, autoplayNarration: Bool) {
        resetSequenceRuntime()
        narrationTask?.cancel()
        narrationTask = nil
        draftTask?.cancel()
        draftTask = nil
        quizLoadTask?.cancel()
        quizLoadTask = nil
        quizSubmitTask?.cancel()
        quizSubmitTask = nil
        quizSyncTask?.cancel()
        quizSyncTask = nil
        quizSceneGeneration &+= 1
        quizAnswerVersion = 0
        quizRound = 0
        player.stop()
        audioCache.clearPlaying()
        narrationIsPaused = false
        currentAudioResourceID = nil
        classicAudio = nil
        classicAudioReason = nil
        if classic == nil {
            narrationPhase = .checking
            narrationNotice = nil
        }
        quiz?.message = nil
        quizError = nil
        quiz = nil
        guard let scene = currentScene else {
            narrationPhase = .none
            narrationNotice = "这一页没有对应的讲解音频。"
            return
        }
        if case .quiz = scene.content {
            quizLoadTask?.cancel()
            quizLoadTask = Task { [weak self] in
                await self?.loadQuiz(sceneID: scene.id)
            }
        }
        prefetchNeighbours()
        if classic == nil {
            refreshNarration(sceneID: scene.id)
        } else {
            resolveClassicAudio()
        }
    }

    private func prefetchNeighbours() {
        guard let plan, let document else { return }
        images.cancelPreloads()
        for offset in [index, index + 1, index + 2, index - 1] where plan.scenes.indices.contains(offset) {
            let scene = plan.scenes[offset]
            guard let content = document.scenesByID[scene.id] else { continue }
            if case .slide(let slide) = content.content, let canvas = slide.canvas {
                images.preload(sceneID: scene.id, canvas: canvas, scope: imageScope, client: client, mediaBasePath: mediaBasePath)
            }
        }
    }

    // MARK: - Persistence

    private var scope: String {
        "\(accountKey)|classroom|\(courseID)|\(workspaceID)|\(stageID)"
    }

    private var cacheKey: String { scope }
    var imageScope: String { "\(scope)|rev\(plan?.revision ?? 0)" }

    private func persistSnapshot() async {
        guard let rawPlan, let rawStage else { return }
        let snapshot = StageSnapshot(plan: rawPlan, stage: rawStage, savedAt: Date())
        try? await cache.save(snapshot, scope: scope, key: "stage.json")
    }

    private func saveProgress() {
        saveTask?.cancel()
        let value = progress
        saveTask = Task {
            try? await Task.sleep(for: .milliseconds(250))
            guard !Task.isCancelled else { return }
            try? await cache.save(value, scope: scope, key: "progress.json")
        }
    }

    private func saveLocalState() {
        stateTask?.cancel()
        let value = localState
        stateTask = Task {
            try? await Task.sleep(for: .milliseconds(200))
            guard !Task.isCancelled else { return }
            try? await cache.save(value, scope: scope, key: "state.json")
        }
    }

    // MARK: - Quiz

    private func fetchQuizAttempt(sceneID: String) async throws -> ClassroomQuizAttempt {
        if let classic {
            return try await ClassroomService(client: client, scope: classic.scope)
                .quizAttempt(sessionID: classic.sessionID, sceneID: sceneID)
        }
        return try await service.quizAttempt(
            courseID: courseID, workspaceID: workspaceID, stageID: stageID, sceneID: sceneID)
    }

    private func persistQuizAttempt(sceneID: String, attemptID: String, phase: String,
                                    answers: [String: ClassroomQuizAnswer], results: [JSONValue]?,
                                    startNewAttempt: Bool) async throws -> ClassroomQuizAttempt {
        if let classic {
            return try await ClassroomService(client: client, scope: classic.scope).saveQuizAttempt(
                sessionID: classic.sessionID, sceneID: sceneID, attemptID: attemptID,
                phase: phase, answers: answers, results: results, startNewAttempt: startNewAttempt)
        }
        return try await service.saveQuizAttempt(
            courseID: courseID, workspaceID: workspaceID, stageID: stageID, sceneID: sceneID,
            attemptID: attemptID, phase: phase, answers: answers, results: results,
            startNewAttempt: startNewAttempt)
    }

    /// 只在当前场景、代次和轮次都未变化时允许写入。
    private struct QuizWriteIdentity {
        let sceneID: String
        let sceneGeneration: Int
        let round: Int
    }

    private func quizWriteIdentity(requireAnswering: Bool = false) -> QuizWriteIdentity? {
        guard let session = quiz, !currentSceneID.isEmpty else { return nil }
        if requireAnswering, session.phase != .answering { return nil }
        return QuizWriteIdentity(
            sceneID: currentSceneID,
            sceneGeneration: quizSceneGeneration,
            round: quizRound
        )
    }

    private func isQuizContextCurrent(_ identity: QuizWriteIdentity) -> Bool {
        currentSceneID == identity.sceneID &&
            quizSceneGeneration == identity.sceneGeneration &&
            quizRound == identity.round
    }

    private func loadQuiz(sceneID: String) async {
        let generation = quizSceneGeneration
        guard currentSceneID == sceneID, generation == quizSceneGeneration, let set = currentQuizSet else { return }
        let version = quizAnswerVersion
        do {
            let attempt = try await fetchQuizAttempt(sceneID: sceneID)
            guard currentSceneID == sceneID, generation == quizSceneGeneration else { return }
            var answers: [String: ClassroomQuizAnswer] = [:]
            for question in set.questions {
                if let answer = attempt.answer(for: question) { answers[question.id] = answer }
            }
            var session = QuizSession(
                attemptID: attempt.attemptID,
                phase: attempt.isReviewed || attempt.isSubmitted ? .reviewed : .answering,
                answers: version == quizAnswerVersion ? answers : (quiz?.answers ?? answers),
                evaluation: nil,
                hintsShown: [:],
                message: nil,
                needsSync: attempt.isSubmitted,
                startNewOnNextSave: false
            )
            if attempt.isReviewed || attempt.isSubmitted {
                session.evaluation = ClassroomQuizEvaluation.evaluate(
                    questions: set.questions, answers: session.answers, studentLed: set.studentLed)
                if attempt.isSubmitted {
                    session.message = "上一次提交的结果还在同步，先显示本地判分。"
                }
            }
            quiz = session
        } catch is CancellationError {
            return
        } catch {
            guard currentSceneID == sceneID, generation == quizSceneGeneration else { return }
            quizError = ClassroomNativePresentation.message(for: error, fallback: "答题记录读取失败。")
        }
    }

    func select(option: ClassroomQuizOption, for question: ClassroomQuizQuestion) {
        guard var session = quiz, session.phase == .answering, !submittingQuiz else { return }
        if question.isMultiple {
            var values: [String]
            if case .choices(let existing)? = session.answers[question.id] { values = existing } else { values = [] }
            if let index = values.firstIndex(of: option.value) { values.remove(at: index) } else { values.append(option.value) }
            session.answers[question.id] = .choices(values)
        } else {
            session.answers[question.id] = .choice(option.value)
        }
        session.evaluation = nil
        session.phase = .answering
        session.message = nil
        quizAnswerVersion &+= 1
        quiz = session
        scheduleDraftSave()
    }

    func setShortAnswer(_ text: String, for question: ClassroomQuizQuestion) {
        guard var session = quiz, session.phase == .answering, !submittingQuiz else { return }
        session.answers[question.id] = .text(text)
        session.evaluation = nil
        session.phase = .answering
        session.message = nil
        quizAnswerVersion &+= 1
        quiz = session
        scheduleDraftSave()
    }

    func revealHint(for question: ClassroomQuizQuestion) {
        guard var session = quiz, !question.hints.isEmpty else { return }
        let shown = session.hintsShown[question.id, default: 0]
        guard shown < question.hints.count else { return }
        session.hintsShown[question.id] = shown + 1
        quiz = session
    }

    private func scheduleDraftSave() {
        draftTask?.cancel()
        guard let identity = quizWriteIdentity(requireAnswering: true) else { return }
        let version = quizAnswerVersion
        draftTask = Task { [weak self] in
            try? await Task.sleep(for: .milliseconds(500))
            guard !Task.isCancelled else { return }
            await self?.saveDraft(identity: identity, answerVersion: version)
        }
    }

    private func saveDraft(identity: QuizWriteIdentity, answerVersion: Int) async {
        guard isQuizContextCurrent(identity), let session = quiz,
              session.phase == .answering, answerVersion == quizAnswerVersion else { return }
        await quizWriteGate.acquire()
        if Task.isCancelled {
            await quizWriteGate.release()
            return
        }
        guard isQuizContextCurrent(identity), let current = quiz,
              current.phase == .answering else {
            await quizWriteGate.release()
            return
        }
        // 写锁内读取最新 attempt 与 start_new 标记：重做分配可能刚刚完成。
        let attemptID = current.attemptID
        let startNew = current.startNewOnNextSave
        let answers = current.answers
        do {
            let saved = try await persistQuizAttempt(
                sceneID: identity.sceneID, attemptID: attemptID, phase: "draft",
                answers: answers, results: nil, startNewAttempt: startNew)
            await quizWriteGate.release()
            guard isQuizContextCurrent(identity), var latest = quiz else { return }
            latest.attemptID = saved.attemptID
            latest.startNewOnNextSave = false
            quiz = latest
        } catch is CancellationError {
            await quizWriteGate.release()
        } catch {
            await quizWriteGate.release()
            // 草稿保存失败不打断答题；提交时会再次校验。
        }
    }

    func submitQuiz() async {
        guard !submittingQuiz, !syncingQuiz,
              var session = quiz, session.phase == .answering,
              let set = currentQuizSet,
              let identity = quizWriteIdentity()
        else { return }
        submittingQuiz = true
        defer { submittingQuiz = false }
        draftTask?.cancel()
        draftTask = nil
        let evaluation = ClassroomQuizEvaluation.evaluate(
            questions: set.questions, answers: session.answers, studentLed: set.studentLed)
        session.phase = .submitting
        session.message = nil
        quiz = session

        await quizWriteGate.acquire()
        if Task.isCancelled {
            await quizWriteGate.release()
            return
        }
        guard isQuizContextCurrent(identity), let current = quiz, current.phase == .submitting else {
            await quizWriteGate.release()
            return
        }
        let sentAttemptID = current.attemptID
        let startNew = current.startNewOnNextSave
        let answers = current.answers
        let submitted: ClassroomQuizAttempt
        do {
            submitted = try await persistQuizAttempt(
                sceneID: identity.sceneID, attemptID: sentAttemptID, phase: "submitted",
                answers: answers, results: nil, startNewAttempt: startNew)
        } catch is CancellationError {
            await quizWriteGate.release()
            return
        } catch {
            await quizWriteGate.release()
            guard isQuizContextCurrent(identity), var failed = quiz else { return }
            failed.phase = .answering
            failed.evaluation = nil
            if let api = error as? APIError, api.code == "QUIZ_ATTEMPT_CONFLICT" {
                failed.message = ClassroomNativePresentation.message(for: error, fallback: "答题记录已变化，请重新提交。")
                quiz = failed
                await loadQuiz(sceneID: identity.sceneID)
                if currentSceneID == identity.sceneID, var reloaded = quiz {
                    reloaded.message = failed.message
                    quiz = reloaded
                }
            } else {
                failed.message = ClassroomNativePresentation.message(for: error, fallback: "提交失败，请重试。")
                quiz = failed
                // 提交未被确认时补一份草稿，退出课堂也不会丢失最新答案。
                scheduleDraftSave()
            }
            return
        }
        guard isQuizContextCurrent(identity), var updated = quiz else {
            await quizWriteGate.release()
            return
        }
        updated.attemptID = submitted.attemptID
        updated.startNewOnNextSave = false
        updated.phase = .reviewed
        updated.evaluation = evaluation
        quiz = updated
        do {
            let reviewed = try await persistQuizAttempt(
                sceneID: identity.sceneID, attemptID: submitted.attemptID, phase: "reviewed",
                answers: updated.answers, results: evaluation.jsonResults(), startNewAttempt: false)
            await quizWriteGate.release()
            guard isQuizContextCurrent(identity), var latest = quiz else { return }
            latest.attemptID = reviewed.attemptID
            latest.needsSync = false
            latest.message = nil
            quiz = latest
            ClassroomPerformanceProbe.shared.recordQuizSubmit(stageKey: cacheKey)
        } catch is CancellationError {
            await quizWriteGate.release()
        } catch {
            await quizWriteGate.release()
            guard isQuizContextCurrent(identity), var latest = quiz else { return }
            latest.needsSync = true
            latest.message = "结果已判分，但还没有同步到服务器。可以点“重新同步结果”。"
            quiz = latest
        }
    }

    /// 已提交但结果没落库时，用本地判分补一次 reviewed；场景/轮次变化后不写回。
    func syncQuizIfNeeded() async {
        guard !syncingQuiz, !submittingQuiz,
              let session = quiz, session.needsSync,
              let set = currentQuizSet,
              let identity = quizWriteIdentity()
        else { return }
        syncingQuiz = true
        defer { syncingQuiz = false }
        let evaluation = ClassroomQuizEvaluation.evaluate(
            questions: set.questions, answers: session.answers, studentLed: set.studentLed)

        await quizWriteGate.acquire()
        if Task.isCancelled {
            await quizWriteGate.release()
            return
        }
        guard isQuizContextCurrent(identity), let current = quiz, current.needsSync else {
            await quizWriteGate.release()
            return
        }
        do {
            let reviewed = try await persistQuizAttempt(
                sceneID: identity.sceneID, attemptID: current.attemptID, phase: "reviewed",
                answers: current.answers, results: evaluation.jsonResults(), startNewAttempt: false)
            await quizWriteGate.release()
            guard isQuizContextCurrent(identity), var latest = quiz else { return }
            latest.attemptID = reviewed.attemptID
            latest.evaluation = evaluation
            latest.needsSync = false
            latest.message = nil
            quiz = latest
        } catch is CancellationError {
            await quizWriteGate.release()
        } catch {
            await quizWriteGate.release()
            guard isQuizContextCurrent(identity), var latest = quiz else { return }
            latest.message = ClassroomNativePresentation.message(for: error, fallback: "结果同步失败。")
            quiz = latest
        }
    }

    /// 重做立即申请新根 attempt；即使响应未返回，也用轮次隔离上一轮。
    func retryQuiz() {
        guard !submittingQuiz, !syncingQuiz, var session = quiz else { return }
        draftTask?.cancel()
        draftTask = nil
        quizLoadTask?.cancel()
        quizLoadTask = nil
        quizSubmitTask?.cancel()
        quizSubmitTask = nil
        quizSyncTask?.cancel()
        quizSyncTask = nil
        quizAnswerVersion &+= 1
        quizRound &+= 1
        session.phase = .answering
        session.answers = [:]
        session.evaluation = nil
        session.hintsShown = [:]
        session.message = nil
        session.needsSync = false
        session.startNewOnNextSave = true
        quiz = session
        guard let identity = quizWriteIdentity() else { return }
        quizSubmitTask = Task { [weak self] in
            await self?.allocateQuizAttempt(identity: identity)
        }
    }

    private func allocateQuizAttempt(identity: QuizWriteIdentity) async {
        await quizWriteGate.acquire()
        if Task.isCancelled {
            await quizWriteGate.release()
            return
        }
        guard isQuizContextCurrent(identity), let current = quiz,
              current.phase == .answering, current.startNewOnNextSave else {
            await quizWriteGate.release()
            return
        }
        do {
            let allocated = try await persistQuizAttempt(
                sceneID: identity.sceneID, attemptID: current.attemptID, phase: "draft",
                answers: [:], results: nil, startNewAttempt: true)
            await quizWriteGate.release()
            guard isQuizContextCurrent(identity), var latest = quiz else { return }
            latest.attemptID = allocated.attemptID
            latest.startNewOnNextSave = false
            quiz = latest
        } catch is CancellationError {
            await quizWriteGate.release()
        } catch {
            await quizWriteGate.release()
            guard isQuizContextCurrent(identity), var latest = quiz else { return }
            latest.message = ClassroomNativePresentation.message(for: error, fallback: "重新答题失败。")
            quiz = latest
        }
    }

    // MARK: - PBL / simulation

    func togglePBLTask(_ taskID: String) {
        guard let scene = currentScene else { return }
        localState.toggle(taskID: taskID, sceneID: scene.id)
        saveLocalState()
    }

    func simulate(_ action: ClassroomSimulation.Action) {
        guard let scene = currentScene, let simulation = currentSimulation else { return }
        let state = simulationStates[scene.id] ?? simulation.initialState()
        simulationStates[scene.id] = simulation.applying(action, to: state)
    }

    // MARK: - Narration

    private func refreshNarration(sceneID: String) {
        narrationPhase = .checking
        narrationTask = Task { [weak self] in
            await self?.loadNarration(sceneID: sceneID, synthesize: false, play: false)
        }
    }

    private func loadNarration(sceneID: String, synthesize: Bool, play: Bool) async {
        guard classic == nil else { return }
        guard currentSceneID == sceneID else { return }
        do {
            let state = try await service.narration(
                courseID: courseID, workspaceID: workspaceID, stageID: stageID, sceneID: sceneID)
            guard currentSceneID == sceneID else { return }
            narrationNotice = state.truncated ? "讲稿过长，已截取开头部分。" : nil
            if let artifact = state.playableArtifactID {
                try await prepareAudio(artifactID: artifact, sceneID: sceneID, play: play)
                return
            }
            if let job = state.job, job.isRunning {
                narrationPhase = .generating(job.progress)
                let finished = try await service.waitForJob(courseID: courseID, jobID: job.id)
                guard currentSceneID == sceneID else { return }
                if let artifact = finished.artifactID, finished.isCompleted {
                    try await prepareAudio(artifactID: artifact, sceneID: sceneID, play: play)
                } else {
                    narrationPhase = .failed(state.failureMessage ?? "讲解生成失败，可以重试。")
                }
                return
            }
            if let job = state.job, job.isFailed {
                narrationPhase = .failed(state.failureMessage ?? "讲解生成失败，可以重试。")
                return
            }
            guard state.hasScript else {
                narrationPhase = .none
                narrationNotice = "这一页没有可讲解的文字。"
                return
            }
            if synthesize {
                narrationPhase = .generating(0)
                let accepted = try await service.synthesizeNarration(
                    courseID: courseID, workspaceID: workspaceID, stageID: stageID, sceneID: sceneID)
                guard currentSceneID == sceneID else { return }
                if let artifact = accepted.playableArtifactID {
                    try await prepareAudio(artifactID: artifact, sceneID: sceneID, play: play)
                } else if let job = accepted.job, job.isRunning {
                    let finished = try await service.waitForJob(courseID: courseID, jobID: job.id)
                    guard currentSceneID == sceneID else { return }
                    if let artifact = finished.artifactID, finished.isCompleted {
                        try await prepareAudio(artifactID: artifact, sceneID: sceneID, play: play)
                    } else {
                        narrationPhase = .failed(accepted.failureMessage ?? "讲解生成失败，可以重试。")
                    }
                } else {
                    narrationPhase = .failed("服务端没有返回可播放的讲解。")
                }
            } else {
                narrationPhase = .available
            }
        } catch is CancellationError {
            return
        } catch {
            guard currentSceneID == sceneID else { return }
            narrationPhase = .failed(ClassroomNativePresentation.message(for: error, fallback: "讲解加载失败，可以重试。"))
        }
    }

    private func prepareAudio(artifactID: String, sceneID: String, play: Bool) async throws {
        narrationPhase = .loadingAudio
        let url: URL
        if let cached = audioCache.url(accountKey: accountKey, artifactID: artifactID) {
            audioCache.markPlaying(accountKey: accountKey, resourceID: artifactID)
            url = cached
        } else {
            let resource = try await service.downloadNarration(courseID: courseID, artifactID: artifactID)
            url = try await audioCache.store(resource.url, accountKey: accountKey, artifactID: artifactID)
            audioCache.markPlaying(accountKey: accountKey, resourceID: artifactID)
        }
        guard currentSceneID == sceneID else { return }
        currentAudioResourceID = artifactID
        narrationPhase = .ready
        if play {
            try startAudio(at: url)
        }
    }

    /// 经典课堂的成品音频：先查本地缓存，未命中才走当前 session 的鉴权媒体下载。
    private func playClassicNarration() {
        guard sequence?.active != true else { return }
        guard classic != nil else { return }
        guard let audio = classicAudio else {
            if let reason = classicAudioReason {
                narrationPhase = .failed(ClassroomSpeechAudioResolver.message(for: reason))
            } else {
                resolveClassicAudio()
            }
            return
        }
        if let cached = audioCache.url(accountKey: accountKey, resourceID: audio.cacheID) {
            currentAudioResourceID = audio.cacheID
            narrationPhase = .ready
            do {
                try startAudio(at: cached)
            } catch {
                narrationPhase = .failed("音频无法播放：\(error.localizedDescription)")
            }
            return
        }
        let sceneID = currentSceneID
        narrationTask?.cancel()
        narrationTask = Task { [weak self] in
            await self?.loadClassicAudio(audio, sceneID: sceneID)
        }
    }

    private func loadClassicAudio(_ audio: ClassroomSpeechAudio, sceneID: String) async {
        guard let classic, currentSceneID == sceneID else { return }
        do {
            narrationPhase = .loadingAudio
            let resource = try await ClassroomService(client: client, scope: classic.scope)
                .downloadSessionAudio(sessionID: classic.sessionID, audioURL: audio.audioURL)
            let temporaryURL = resource.url
            var deliveredURL: URL?
            defer {
                if let deliveredURL, deliveredURL == temporaryURL {
                    // 缓存不可用时下载文件本身就是播放源，不能删除。
                } else {
                    try? FileManager.default.removeItem(at: temporaryURL)
                }
            }
            guard currentSceneID == sceneID, classicAudio?.cacheID == audio.cacheID else { return }
            let ext = ClassroomMediaReference.audioExtension(
                path: audio.apiPath, contentType: resource.mimeType ?? audio.contentType) ?? "wav"
            let url = try await audioCache.store(resource.url, accountKey: accountKey,
                                                 resourceID: audio.cacheID, fileExtension: ext)
            audioCache.markPlaying(accountKey: accountKey, resourceID: audio.cacheID)
            deliveredURL = url
            guard currentSceneID == sceneID, classicAudio?.cacheID == audio.cacheID else { return }
            currentAudioResourceID = audio.cacheID
            narrationPhase = .ready
            try startAudio(at: url)
        } catch is CancellationError {
            return
        } catch {
            guard currentSceneID == sceneID, classicAudio?.cacheID == audio.cacheID else { return }
            narrationPhase = .failed("讲解音频加载失败：\(ClassroomNativePresentation.message(for: error, fallback: "请检查网络后重试。"))")
        }
    }

    /// 经典 playback 已把 `speech` 动作和媒体登记一起下发；这里只按 action_id
    /// 关联，不跨场景找音频，也不猜测缺失的媒体地址。
    private func resolveClassicAudio() {
        classicAudio = nil
        classicAudioReason = nil
        guard let scene = currentPlaybackScene else {
            narrationPhase = .none
            narrationNotice = "这一页没有对应的讲解音频。"
            return
        }
        switch ClassroomSpeechAudioResolver.resolve(scene: scene, contentVersion: plan?.contentVersion) {
        case .playable(let audio):
            classicAudio = audio
            narrationPhase = .available
            narrationNotice = "教师讲解音频来自这节课堂的成品。"
        case .unavailable(let reason):
            classicAudioReason = reason
            narrationPhase = .none
            narrationNotice = ClassroomSpeechAudioResolver.message(for: reason)
        case .absent:
            narrationPhase = .none
            narrationNotice = "这一页没有已生成的教师讲解音频；网页课堂仍可播放讲解。"
        }
    }

    func generateNarration() {
        guard sequence?.active != true else { return }
        if classic != nil {
            playClassicNarration()
            return
        }
        let sceneID = currentSceneID
        guard !sceneID.isEmpty else { return }
        narrationTask?.cancel()
        narrationTask = Task { [weak self] in
            await self?.loadNarration(sceneID: sceneID, synthesize: true, play: true)
        }
    }

    func toggleNarration() {
        guard sequence?.active != true else { return }
        switch narrationPhase {
        case .ready, .playing:
            if player.isPlaying {
                player.pause()
                narrationPhase = .ready
                narrationIsPaused = true
            } else if narrationIsPaused {
                player.resume()
                narrationIsPaused = false
                narrationPhase = .playing
            } else if classic != nil {
                playClassicNarration()
            } else if let id = currentAudioResourceID,
                      let url = audioCache.url(accountKey: accountKey, resourceID: id) {
                do {
                    try startAudio(at: url)
                } catch {
                    narrationPhase = .failed("音频无法播放：\(error.localizedDescription)")
                }
            }
        case .available, .failed:
            if classic != nil { playClassicNarration() } else { generateNarration() }
        default:
            break
        }
    }

    func stopNarration() {
        guard sequence?.active != true else { return }
        player.stop()
        narrationTask?.cancel()
        narrationTask = nil
        currentAudioResourceID = nil
        narrationIsPaused = false
        switch narrationPhase {
        case .ready, .playing, .generating, .loadingAudio: narrationPhase = .available
        default: break
        }
    }

    private var currentAudioResourceID: String?

    private func startAudio(at url: URL) throws {
        try player.play(url: url)
        narrationIsPaused = false
        narrationPhase = .playing
    }

    private func handleAudioFinished() {
        narrationIsPaused = false
        if narrationPhase == .playing {
            narrationPhase = classic == nil ? .ready : .available
        }
    }

    private func handleAudioInterrupted() {
        narrationIsPaused = false
        if sequence?.active == true, sequenceAudioContinuation != nil {
            pauseSequence()
            narrationNotice = "音频被系统打断，顺序播放已暂停；回到课堂后可点继续。"
            return
        }
        if narrationPhase == .playing { narrationPhase = classic == nil ? .ready : .available }
        narrationNotice = "音频被系统打断，可以继续播放。"
    }

    /// 由可见内容在首次出现时回调。首屏可读与翻页耗时的“结束时刻”都在这里，
    /// 不在状态赋值时提前记账。
    func pageDidRender() {
        guard case .ready = phase else { return }
        let memory = ClassroomPerformanceProbe.residentMemoryMB()
        if !firstReadReported {
            firstReadReported = true
            if restoredFromCache {
                ClassroomPerformanceProbe.shared.markCachedReadable(stageKey: cacheKey, memory: memory)
            } else {
                ClassroomPerformanceProbe.shared.markNetworkReadable(
                    stageKey: cacheKey, playbackMs: lastPlaybackMs, memory: memory)
            }
        }
        if let start = pageTurnStartedAt {
            pageTurnStartedAt = nil
            let elapsed = Int(Date().timeIntervalSince(start) * 1000)
            ClassroomPerformanceProbe.shared.recordPageTurn(
                stageKey: cacheKey, milliseconds: elapsed, memory: memory)
        }
    }

    func handleScenePhase(_ isActive: Bool) {
        guard !isActive else { return }
        if sequence?.active == true {
            pauseSequence()
        }
        if player.isPlaying {
            player.pause()
            narrationPhase = .ready
        }
    }

    func shutdown() {
        stopSequence()
        narrationTask?.cancel()
        narrationTask = nil
        draftTask?.cancel()
        draftTask = nil
        quizLoadTask?.cancel()
        quizLoadTask = nil
        quizSubmitTask?.cancel()
        quizSubmitTask = nil
        quizSyncTask?.cancel()
        quizSyncTask = nil
        saveTask?.cancel()
        saveTask = nil
        stateTask?.cancel()
        stateTask = nil
        audioCache.clearPlaying()
        player.stop()
        narrationIsPaused = false
        started = false
    }

    func dismissNotice() { notice = nil }

    // MARK: - Diagnostics

    var diagnosticsText: String {
        ClassroomPerformanceProbe.shared.report(stageKey: cacheKey, title: title)
    }

    var currentMemoryMB: Double { ClassroomPerformanceProbe.residentMemoryMB() }

    func retryLoad() {
        guard phaseIsFailed else { return }
        started = false
        phase = .loading
        Task { await open() }
    }

    private var phaseIsFailed: Bool {
        if case .failed = phase { return true }
        return false
    }
}

extension NativeClassroomModel {
    fileprivate struct ClassicBinding: Sendable {
        let scope: ClassroomScope
        let sessionID: String
    }

    fileprivate struct StageSnapshot: Codable, Sendable {
        var plan: JSONValue
        var stage: JSONValue
        var savedAt: Date
    }
}

/// 串行化同一会话的测验写入：提交、同步、重做与草稿按进入顺序到达服务端。
private actor ClassroomQuizWriteGate {
    private var locked = false
    private var waiters: [CheckedContinuation<Void, Never>] = []

    func acquire() async {
        if !locked {
            locked = true
            return
        }
        await withCheckedContinuation { continuation in
            waiters.append(continuation)
        }
    }

    func release() {
        if waiters.isEmpty {
            locked = false
        } else {
            waiters.removeFirst().resume()
        }
    }
}

// MARK: - Service-declared action sequence

private struct SequenceFailure: Error {
    let message: String
}

private struct SequenceAbort: Error {}

extension NativeClassroomModel {
    /// Start the service-declared `steps` order. The sequence is deliberately
    /// owned by the model, not by a scene view: paging, backgrounding, account
    /// changes and exit all cancel it through one path.
    func startSequence() {
        guard let scene = currentPlaybackScene, !scene.steps.isEmpty else { return }
        let plan = ClassroomActionSequencePlanner.plan(scene: scene)
        guard !plan.isEmpty else {
            sequence = SequenceState(
                sceneID: scene.id, total: 0, completed: 0, currentIndex: 0,
                currentActionID: nil, active: false, paused: false,
                message: "服务端没有返回可执行的课堂动作步骤。"
            )
            return
        }

        stopNarration()
        resetSequenceRuntime()
        let token = UUID()
        sequenceToken = token
        sequence = SequenceState(
            sceneID: scene.id, total: plan.total, completed: 0, currentIndex: 0,
            currentActionID: plan.operations.first?.actionID, active: true, paused: false,
            message: nil
        )
        sequenceTask = Task { [weak self] in
            await self?.runSequence(sceneID: scene.id, token: token, operations: plan.operations)
        }
    }

    func pauseSequence() {
        guard var state = sequence, state.active, !state.paused else { return }
        state.paused = true
        sequence = state
        if sequenceAudioContinuation != nil {
            player.pause()
            if narrationPhase == .playing { narrationPhase = classic == nil ? .ready : .available }
        }
    }

    func resumeSequence() {
        guard var state = sequence, state.active, state.paused else { return }
        state.paused = false
        sequence = state
        if sequenceAudioContinuation != nil {
            player.resume()
            narrationPhase = .playing
        }
    }

    func stopSequence() {
        resetSequenceRuntime()
        if narrationPhase == .playing { narrationPhase = classic == nil ? .ready : .available }
    }

    /// Dismissing the video sheet is a user close; the service contract treats
    /// a closed video as a finished step so the sequence can continue.
    func sequenceVideoSheetClosed() {
        finishSequenceVideo(completed: true)
    }

    private func runSequence(sceneID: String, token: UUID,
                             operations: [ClassroomSequenceOperation]) async {
        do {
            for (offset, operation) in operations.enumerated() {
                try await waitForSequenceResume(sceneID: sceneID, token: token)
                try abortIfStale(sceneID: sceneID, token: token)
                guard var state = sequence, state.active else { return }
                state.currentIndex = offset
                state.currentActionID = operation.actionID
                state.message = nil
                sequence = state

                try await executeSequenceOperation(operation, sceneID: sceneID, token: token)

                try abortIfStale(sceneID: sceneID, token: token)
                guard var completed = sequence, completed.active else { return }
                completed.completed = offset + 1
                if offset + 1 >= operations.count {
                    completed.active = false
                    completed.paused = false
                    completed.currentActionID = nil
                    completed.currentIndex = operations.count
                    completed.message = "顺序动作已完成。"
                } else {
                    completed.currentActionID = operations[offset + 1].actionID
                }
                sequence = completed
            }
            sequenceTask = nil
        } catch is SequenceAbort {
            return
        } catch is CancellationError {
            return
        } catch let failure as SequenceFailure {
            failSequence(message: failure.message, sceneID: sceneID, token: token)
        } catch {
            failSequence(message: "顺序动作执行失败：\(error.localizedDescription)", sceneID: sceneID, token: token)
        }
    }

    private func executeSequenceOperation(_ operation: ClassroomSequenceOperation,
                                          sceneID: String, token: UUID) async throws {
        switch operation {
        case .blocked(let actionID, let type, let reason):
            throw SequenceFailure(
                message: "动作 \(actionID)（\(type)）无法执行：\(reason)。可退出后使用网页课堂继续。"
            )
        case .action(let action):
            switch action.type {
            case "speech":
                try await playSequenceSpeech(action, sceneID: sceneID, token: token)
            case "play_video":
                try await playSequenceVideo(action, sceneID: sceneID, token: token)
            case "spotlight", "laser":
                // Fire-and-forget visual hints must not hold the sequence.
                return
            case let type where type.hasPrefix("wb_"):
                throw SequenceFailure(message: "白板动作需要网页课堂，原生播放器不会假装执行完成。")
            default:
                if ClassroomActionSequencePlanner.isFireAndForget(action.type) || action.mode == "fire_and_forget" {
                    return
                }
                throw SequenceFailure(
                    message: "\(action.type) 当前没有原生执行入口；可退出后使用网页课堂继续。"
                )
            }
        }
    }

    private func playSequenceSpeech(_ action: ClassroomPlaybackAction,
                                    sceneID: String, token: UUID) async throws {
        guard let scene = currentPlaybackScene else { throw SequenceAbort() }
        switch ClassroomSpeechAudioResolver.resolve(
            action: action, in: scene, contentVersion: plan?.contentVersion
        ) {
        case .playable(let audio):
            let url: URL
            do {
                url = try await classicAudioFile(audio, sceneID: sceneID)
            } catch is CancellationError {
                throw SequenceAbort()
            } catch is SequenceAbort {
                throw SequenceAbort()
            } catch {
                throw SequenceFailure(message: "讲解音频加载失败：\(ClassroomNativePresentation.message(for: error, fallback: "请检查网络后重试。"))")
            }
            try await waitForSequenceResume(sceneID: sceneID, token: token)
            try abortIfStale(sceneID: sceneID, token: token)
            try await playSequenceAudio(
                url: url, cacheID: audio.cacheID,
                actionID: action.id, sceneID: sceneID, token: token
            )
        case .unavailable(let reason):
            try await playSequenceFallbackSpeech(
                action, reason: reason, sceneID: sceneID, token: token
            )
        case .absent:
            try await playSequenceFallbackSpeech(
                action, reason: nil, sceneID: sceneID, token: token
            )
        }
    }

    /// A speech step without a finished audio artifact must not deadlock the
    /// sequence. Wait for the script's text duration, while surfacing that the
        /// web classroom remains the fallback for actual narration.
    private func playSequenceFallbackSpeech(_ action: ClassroomPlaybackAction,
                                            reason: String?, sceneID: String,
                                            token: UUID) async throws {
        if let seconds = sequenceSpeechFallbackDuration(action) {
            if var state = sequence {
                state.message = "没有成品讲解音频，按文本时长继续；网页课堂仍可播放：\(ClassroomSpeechAudioResolver.message(for: reason))"
                sequence = state
            }
            try await waitSequence(seconds: seconds, sceneID: sceneID, token: token)
            return
        }
        throw SequenceFailure(message: ClassroomSpeechAudioResolver.message(for: reason))
    }
    private func playSequenceAudio(url: URL, cacheID: String, actionID: String,
                                   sceneID: String, token: UUID) async throws {
        try abortIfStale(sceneID: sceneID, token: token)
        sequenceAudioToken = token
        sequenceAudioActionID = actionID
        sequenceAudioFailure = nil
        currentAudioResourceID = cacheID
        narrationPhase = .playing

        let finished: Bool = await withCheckedContinuation { continuation in
            sequenceAudioContinuation = continuation
            do {
                try player.play(url: url) { [weak self] in
                    self?.finishSequenceAudio(token: token, actionID: actionID, completed: true)
                }
            } catch {
                sequenceAudioContinuation = nil
                sequenceAudioFailure = error.localizedDescription
                continuation.resume(returning: false)
            }
        }
        guard finished else {
            if let failure = sequenceAudioFailure {
                sequenceAudioFailure = nil
                throw SequenceFailure(message: "讲解音频无法播放：\(failure)")
            }
            throw SequenceAbort()
        }
    }

    private func finishSequenceAudio(token: UUID, actionID: String, completed: Bool) {
        guard sequenceAudioToken == token, sequenceAudioActionID == actionID,
              let continuation = sequenceAudioContinuation else { return }
        sequenceAudioContinuation = nil
        sequenceAudioToken = nil
        sequenceAudioActionID = nil
        if narrationPhase == .playing { narrationPhase = classic == nil ? .ready : .available }
        continuation.resume(returning: completed)
    }

    private func abortSequenceAudio() {
        sequenceAudioToken = nil
        sequenceAudioActionID = nil
        sequenceAudioFailure = nil
        guard let continuation = sequenceAudioContinuation else { return }
        sequenceAudioContinuation = nil
        continuation.resume(returning: false)
    }

    private func playSequenceVideo(_ action: ClassroomPlaybackAction,
                                   sceneID: String, token: UUID) async throws {
        guard let scene = currentPlaybackScene, let classic else { throw SequenceAbort() }
        let elementID = action.payload["elementId"].string?.nonEmpty
            ?? action.payload["element_id"].string?.nonEmpty
            ?? action.payload["targetId"].string?.nonEmpty
        guard let elementID else {
            throw SequenceFailure(message: "视频动作没有给出画布元素 ID，无法确认要播放哪段视频。")
        }
        let media = scene.media.first {
            $0.available && $0.kind == "video" && $0.elementID == elementID
        }
        guard let media, let mediaURL = media.url else {
            let blocked = scene.media.first {
                $0.kind == "video" && $0.elementID == elementID && !$0.available
            }
            throw SequenceFailure(
                message: "视频媒体不可用：\(blocked?.reason ?? "media_reference_missing")。可退出后使用网页课堂。"
            )
        }

        try abortIfStale(sceneID: sceneID, token: token)
        let resource: DownloadedResource
        do {
            resource = try await ClassroomService(client: client, scope: classic.scope)
                .downloadSessionMedia(sessionID: classic.sessionID, mediaURL: mediaURL, expectedKind: "video")
        } catch is CancellationError {
            throw SequenceAbort()
        } catch {
            throw SequenceFailure(message: "视频媒体加载失败：\(ClassroomNativePresentation.message(for: error, fallback: "请检查网络后重试。"))")
        }
        try await waitForSequenceResume(sceneID: sceneID, token: token)
        try abortIfStale(sceneID: sceneID, token: token)

        let title = action.payload["title"].string?.nonEmpty
            ?? action.payload["caption"].string?.nonEmpty
            ?? "课堂视频"
        let video = SequenceVideo(url: resource.url, title: title)
        sequenceVideo = video
        sequenceVideoToken = token
        sequenceVideoActionID = action.id

        let completed: Bool = await withCheckedContinuation { continuation in
            sequenceVideoContinuation = continuation
        }
        guard completed else { throw SequenceAbort() }
    }

    private func finishSequenceVideo(completed: Bool) {
        sequenceVideoToken = nil
        sequenceVideoActionID = nil
        guard let continuation = sequenceVideoContinuation else {
            sequenceVideo = nil
            return
        }
        sequenceVideoContinuation = nil
        sequenceVideo = nil
        continuation.resume(returning: completed)
    }

    private func abortSequenceVideo() {
        sequenceVideoToken = nil
        sequenceVideoActionID = nil
        guard let continuation = sequenceVideoContinuation else {
            sequenceVideo = nil
            return
        }
        sequenceVideoContinuation = nil
        sequenceVideo = nil
        continuation.resume(returning: false)
    }

    private func resetSequenceRuntime() {
        sequenceToken = UUID()
        sequenceTask?.cancel()
        sequenceTask = nil
        abortSequenceAudio()
        abortSequenceVideo()
        sequence = nil
        player.stop()
    }

    private func failSequence(message: String, sceneID: String, token: UUID) {
        guard sequenceToken == token, currentSceneID == sceneID else { return }
        if var state = sequence {
            state.active = false
            state.paused = false
            state.message = message
            sequence = state
        }
        abortSequenceAudio()
        abortSequenceVideo()
        player.stop()
        sequenceTask = nil
    }

    private func abortIfStale(sceneID: String, token: UUID) throws {
        if Task.isCancelled || sequenceToken != token || currentSceneID != sceneID {
            throw SequenceAbort()
        }
    }

    private func waitForSequenceResume(sceneID: String, token: UUID) async throws {
        while sequence?.paused == true {
            try abortIfStale(sceneID: sceneID, token: token)
            try await Task.sleep(for: .milliseconds(50))
        }
        try abortIfStale(sceneID: sceneID, token: token)
    }

    private func waitSequence(seconds: Double, sceneID: String, token: UUID) async throws {
        let deadline = Date().addingTimeInterval(max(0.1, seconds))
        while Date() < deadline {
            try await waitForSequenceResume(sceneID: sceneID, token: token)
            try await Task.sleep(for: .milliseconds(50))
        }
        try abortIfStale(sceneID: sceneID, token: token)
    }

    private func sequenceSpeechFallbackDuration(_ action: ClassroomPlaybackAction) -> Double? {
        if let value = action.payload["durationSec"].double ?? action.payload["duration"].double,
           value > 0 {
            return min(30, max(1, value))
        }
        let text = action.payload["text"].string?.nonEmpty
            ?? action.payload["script"].string?.nonEmpty
            ?? currentSpeechText(sceneID: currentSceneID)
        guard let text, !text.isEmpty else { return nil }
        return max(1, min(20, Double(text.count) * 0.2))
    }

    private func currentSpeechText(sceneID: String) -> String? {
        guard currentSceneID == sceneID, let scene = currentPlaybackScene else { return nil }
        return scene.speechActions.first?.payload["text"].string?.nonEmpty
    }

    private func classicAudioFile(_ audio: ClassroomSpeechAudio, sceneID: String) async throws -> URL {
        if let cached = audioCache.url(accountKey: accountKey, resourceID: audio.cacheID) {
            return cached
        }
        guard let classic else { throw SequenceAbort() }
        let resource = try await ClassroomService(client: client, scope: classic.scope)
            .downloadSessionAudio(sessionID: classic.sessionID, audioURL: audio.audioURL)
        try abortIfStale(sceneID: sceneID, token: sequenceToken)
        let ext = ClassroomMediaReference.audioExtension(
            path: audio.apiPath, contentType: resource.mimeType ?? audio.contentType) ?? "wav"
        let stored = try await audioCache.store(resource.url, accountKey: accountKey,
                                                resourceID: audio.cacheID, fileExtension: ext)
        audioCache.markPlaying(accountKey: accountKey, resourceID: audio.cacheID)
        return stored
    }
}
