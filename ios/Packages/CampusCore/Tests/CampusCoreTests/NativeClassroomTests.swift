import Foundation
import Testing
@testable import CampusCore

@Suite("Native classroom playback")
struct NativeClassroomTests {
    @Test func stockSlideTemplateDetectionPreservesCustomBackgrounds() throws {
        let elements: [JSONValue] = [
            .object(["id": "el_title", "type": "text", "content": "严格单调"]),
            .object(["id": "el_accent", "type": "shape", "fill": "#722ed1"]),
        ]
        let stock: [String: JSONValue] = [
            "theme": .object(["backgroundColor": "#ffffff", "fontColor": "#1f2937"]),
            "elements": .array(elements),
        ]
        let canvas = try #require(ClassroomCanvas(json: .object(stock)))
        #expect(canvas.usesStockTemplate)
        #expect(canvas.background == ClassroomColor(css: "#ffffff"))
        #expect(canvas.elements.first?.id == "0:el_title")

        var custom = stock
        custom["background"] = .object(["image": .object(["src": "path/background.png"])])
        #expect(ClassroomCanvas(json: .object(custom))?.usesStockTemplate == false)
        custom["background"] = .object(["gradient": .object(["colors": .array(["#ffffff", "#000000"])])])
        let gradient = try #require(ClassroomCanvas(json: .object(custom)))
        #expect(!gradient.usesStockTemplate)
        #expect(gradient.backgroundGradient.count == 2)
    }

    // MARK: - Fixtures

    private func playbackPlanJSON(scenes: [JSONValue], revision: Int = 3, startIndex: Int = 0) -> JSONValue {
        .object([
            "stage_id": "stage-1",
            "workspace_id": "ws-1",
            "title": "光合作用",
            "revision": .number(Double(revision)),
            "dsl_version": "2.0",
            "start_index": .number(Double(startIndex)),
            "scenes": .array(scenes),
            "degraded": .array([]),
        ])
    }

    private func playbackScene(_ id: String, type: String = "slide", kind: String = "native") -> JSONValue {
        .object([
            "id": .string(id),
            "type": .string(type),
            "title": .string("页面 \(id)"),
            "order": .number(1),
            "render": .object(["kind": .string(kind)]),
            "steps": .array([]),
            "dropped_actions": .array([]),
            "whiteboards": .number(0),
            "multi_agent": .bool(false),
        ])
    }

    private func slideScene(_ id: String, title: String = "页面") -> JSONValue {
        .object([
            "id": .string(id),
            "type": .string("slide"),
            "title": .string(title),
            "order": .number(1),
            "content": .object([
                "type": .string("slide"),
                "title": .string(title),
                "canvas": .object([
                    "width": .number(1000),
                    "height": .number(562.5),
                    "elements": .array([]),
                ]),
                "slide": .object(["title": .string(title), "bullets": .array(["要点一", "要点二"])]),
            ]),
        ])
    }

    private func documentJSON(scenes: [JSONValue], revision: Int = 3) -> JSONValue {
        .object([
            "id": "stage-1",
            "workspace_id": "ws-1",
            "title": "光合作用",
            "revision": .number(Double(revision)),
            "dsl_version": "2.0",
            "document": .object([
                "stage": .object(["id": "stage-1", "name": "光合作用"]),
                "scenes": .array(scenes),
            ]),
        ])
    }

    private func quizContent() -> JSONValue {
        .object([
            "type": .string("quiz"),
            "learningProfile": .string("assignment_review"),
            "questions": .array([
                .object([
                    "id": .string("q1"),
                    "type": .string("short"),
                    "question": .string("简述光反应的地点"),
                    "answer": .string("类囊体薄膜"),
                    "hints": .array(["想一想叶绿体的结构"]),
                    "points": .number(2),
                    "analysis": .string("光反应发生在类囊体薄膜上。"),
                ]),
                .object([
                    "id": .string("q2"),
                    "type": .string("multiple"),
                    "question": .string("哪些属于光反应产物"),
                    "options": .array(["ATP", "氧气", "葡萄糖"]),
                    "answer": .array(["ATP", "氧气"]),
                    "points": .number(1),
                ]),
            ]),
        ])
    }

    // MARK: - Playback mapping

    @Test func playbackAndDocumentMustShareRevisionAndSceneIDs() throws {
        let plan = try ClassroomPlaybackPlan(json: playbackPlanJSON(
            scenes: [playbackScene("s1"), playbackScene("s2")]))
        let document = try ClassroomStageDocument(json: documentJSON(
            scenes: [slideScene("s1"), slideScene("s2")]))
        let availability = ClassroomPlaybackAvailability.evaluate(plan: plan, document: document)
        #expect(availability.isEligible)
        #expect(plan.startIndex == 0)

        let stalePlan = try ClassroomPlaybackPlan(json: playbackPlanJSON(
            scenes: [playbackScene("s1")], revision: 4))
        let mismatch = ClassroomPlaybackAvailability.evaluate(plan: stalePlan, document: document)
        #expect(!mismatch.isEligible)
        #expect(mismatch.detail?.contains("更新") == true)

        let missingScenePlan = try ClassroomPlaybackPlan(json: playbackPlanJSON(
            scenes: [playbackScene("s1"), playbackScene("s9")]))
        #expect(!ClassroomPlaybackAvailability.evaluate(plan: missingScenePlan, document: document).isEligible)
    }

    @Test func resumePrefersSavedSceneAndFallsBackWhenItDisappeared() throws {
        let plan = try ClassroomPlaybackPlan(json: playbackPlanJSON(
            scenes: [playbackScene("s1"), playbackScene("s2"), playbackScene("s3")], startIndex: 1))
        let document = try ClassroomStageDocument(json: documentJSON(
            scenes: [slideScene("s1"), slideScene("s2"), slideScene("s3")]))

        var progress = ClassroomProgress(courseID: "c", workspaceID: "ws-1", stageID: "stage-1")
        progress.visit(sceneID: "s3", index: 2, revision: 3)
        let decision = ClassroomResumeDecision.resolve(plan: plan, document: document, progress: progress)
        #expect(decision.index == 2)
        #expect(decision.restored)
        #expect(decision.note != nil)

        var stale = ClassroomProgress(courseID: "c", workspaceID: "ws-1", stageID: "stage-1")
        stale.visit(sceneID: "removed", index: 2, revision: 3)
        let fallback = ClassroomResumeDecision.resolve(plan: plan, document: document, progress: stale)
        #expect(fallback.index == 1)
        #expect(!fallback.restored)

        let otherStage = ClassroomProgress(courseID: "c", workspaceID: "ws-1", stageID: "another")
        #expect(ClassroomResumeDecision.resolve(plan: plan, document: document, progress: otherStage).index == 1)
    }

    // MARK: - Canvas and text

    @Test func htmlTextKeepsParagraphsListsAndInlineStyle() {
        let html = """
        <p style="font-size:42px;color:#153B34;text-align:center;font-weight:700">光合作用</p>
        <ul><li style="font-size:24px">光反应</li><li>暗反应 &amp; 能量</li></ul>
        <ol><li>第一步</li><li><strong>第二步</strong></li></ol>
        <p>第一行<br/>第二行</p>
        """
        let paragraphs = ClassroomRichTextParser.parse(html: html, baseFontSize: 28, baseColor: nil)
        #expect(paragraphs.count == 6)
        #expect(paragraphs[0].text == "光合作用")
        #expect(paragraphs[0].style.fontSize == 42)
        #expect(paragraphs[0].style.bold)
        #expect(paragraphs[0].style.alignment == .center)
        #expect(paragraphs[0].style.color == ClassroomColor(css: "#153b34"))
        #expect(paragraphs[1].marker == "•")
        #expect(paragraphs[2].text == "暗反应 & 能量")
        #expect(paragraphs[3].marker == "1.")
        #expect(paragraphs[4].marker == "2.")
        #expect(paragraphs[4].style.bold)
        #expect(paragraphs[5].text == "第一行\n第二行")
    }

    @Test func canvasReadsElementsAndLimitsInlinedImages() throws {
        let tinyPNG = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
        let canvasJSON: JSONValue = .object([
            "width": .number(1000),
            "height": .number(562.5),
            "background": .object(["color": .string("#FFFBF2")]),
            "elements": .array([
                .object(["id": .string("t"), "type": .string("text"), "left": .number(40), "top": .number(20),
                         "width": .number(600), "height": .number(80), "fontSize": .number(40),
                         "content": .string("<p style=\"font-size:40px\">标题</p>")]),
                .object(["id": .string("s"), "type": .string("shape"), "left": .number(0), "top": .number(0),
                         "width": .number(200), "height": .number(80), "fill": .string("#153B34"),
                         "path": .string("M 0 0 L 200 0 A 16 16 0 0 1 216 16 Z")]),
                .object(["id": .string("i"), "type": .string("image"), "left": .number(0), "top": .number(0),
                         "width": .number(64), "height": .number(64), "alt": .string("示意图"),
                         "dataUri": .string("data:image/png;base64,\(tinyPNG)")]),
                .object(["id": .string("bad"), "type": .string("image"), "dataUri": .string("data:text/html;base64,PGh0bWw+")]),
            ]),
        ])
        let canvas = try #require(ClassroomCanvas(json: canvasJSON))
        #expect(canvas.elements.count == 4)
        guard case .text(let text) = canvas.elements[0] else { Issue.record("缺少文本元素"); return }
        #expect(text.paragraphs.first?.text == "标题")
        guard case .shape(let shape) = canvas.elements[1] else { Issue.record("缺少形状元素"); return }
        #expect(shape.cornerRadius == 16)
        guard case .image(let image) = canvas.elements[2] else { Issue.record("缺少图片元素"); return }
        #expect(image.hasImage)
        #expect(image.alt == "示意图")
        guard case .image(let rejected) = canvas.elements[3] else { Issue.record("缺少被拒绝的图片"); return }
        #expect(!rejected.hasImage)
    }

    @Test func legacySlideWithoutCanvasStillHasAReadableOutline() throws {
        let content: JSONValue = .object([
            "type": .string("slide"),
            "title": .string("旧课件"),
            "slide": .object([
                "title": .string("旧课件"),
                "bullets": .array([.string("第一条")]),
                "sections": .array([.object(["heading": .string("分区"), "bullets": .array(["细节"])])]),
                "conclusion": .string("结论"),
            ]),
        ])
        let slide = ClassroomSlide(json: content)
        #expect(!slide.prefersCanvas)
        #expect(!slide.isEmpty)
        #expect(slide.outline.sections.first?.heading == "分区")
    }

    // MARK: - Quiz

    @Test func quizRegressionMirrorsWebGradingAndStudentLedRules() throws {
        let set = ClassroomQuizSet(json: quizContent())
        #expect(set.questions.count == 2)
        #expect(set.studentLed)
        #expect(set.questions[0].points == 2)
        #expect(set.questions[1].answers == ["A", "B"])
        #expect(set.questions[1].options.map(\.value) == ["A", "B", "C"])

        var answers: [String: ClassroomQuizAnswer] = [
            "q1": .text(" 类囊体薄膜 "),
            "q2": .choices(["A", "B"]),
        ]
        let evaluation = ClassroomQuizEvaluation.evaluate(questions: set.questions, answers: answers, studentLed: true)
        #expect(evaluation.score == 1)
        #expect(evaluation.total == 1)
        #expect(evaluation.results[0].correct == nil)
        #expect(evaluation.results[1].correct == true)

        answers["q1"] = .text("叶绿体基质")
        let graded = ClassroomQuizEvaluation.evaluate(questions: set.questions, answers: answers, studentLed: false)
        #expect(graded.score == 1)
        #expect(graded.results[0].correct == false)

        let unanswered = ClassroomQuizEvaluation.evaluate(questions: set.questions, answers: [:], studentLed: true)
        #expect(unanswered.total == 0)
        #expect(unanswered.results[0].correct == nil)
        #expect(unanswered.results[1].correct == nil)
    }

    @Test func quizAttemptRestoresAnswersAndMarksSubmittedState() throws {
        let attemptJSON: JSONValue = .object([
            "attempt_id": .string("attempt-1"),
            "state": .object([
                "phase": .string("submitted"),
                "answers": .object(["q1": .string("类囊体薄膜"), "q2": .array(["ATP"])]),
                "results": .array([]),
            ]),
        ])
        let attempt = try ClassroomQuizAttempt(json: attemptJSON)
        #expect(attempt.attemptID == "attempt-1")
        #expect(attempt.isSubmitted)
        #expect(attempt.hasAnswers)
        #expect(attempt.answer(for: ClassroomQuizSet(json: quizContent()).questions[0]) == .text("类囊体薄膜"))
    }

    // MARK: - Runtime

    @Test func simulationSnapsToStepAndComputesWithGuardrails() throws {
        let simulation = ClassroomSimulation(json: .object([
            "title": .string("加速度"),
            "formula": .string("force / mass"),
            "resultLabel": .string("加速度"),
            "parameters": .array([
                .object(["id": .string("force"), "label": .string("力"), "min": .number(0),
                         "max": .number(100), "step": .number(10), "value": .number(0), "unit": .string("N")]),
                .object(["id": .string("mass"), "label": .string("质量"), "min": .number(1),
                         "max": .number(10), "step": .number(0.5), "value": .number(2), "unit": .string("kg")]),
            ]),
        ]), fallbackTitle: "实验")
        var state = simulation.initialState()
        state = simulation.applying(.set(id: "force", value: 37), to: state)
        #expect(state.values["force"] == 40)
        state = simulation.applying(.run, to: state)
        #expect(state.result?.value == 20)
        state = simulation.applying(.set(id: "mass", value: 0), to: state)
        #expect(state.values["mass"] == 1)
        #expect(!state.hasRun)
        state = simulation.applying(.reset, to: state)
        #expect(state.values["force"] == 0)
    }

    @Test func pblReadsBothProjectAndLegacyPhaseShapes() {
        let project: JSONValue = .object([
            "project": .object([
                "title": .string("校园水质调查"),
                "description": .string("完成取样与分析"),
                "milestones": .array([
                    .object(["title": .string("取样"), "tasks": .array([
                        .object(["id": .string("t1"), "title": .string("设计取样点")]),
                        .object(["title": .string("记录水样")]),
                    ])]),
                ]),
            ]),
        ])
        let pbl = ClassroomPBL(json: project)
        #expect(pbl.title == "校园水质调查")
        #expect(pbl.taskIDs == ["t1", "task-0-1"])
        let progress = ClassroomPBLProgress(pbl: pbl, completedIDs: Set(["t1"]))
        #expect(progress.completed == 1)
        #expect(progress.percent == 50)

        let legacy: JSONValue = .object(["title": .string("旧项目"),
                                         "phases": .array([.object(["title": .string("阶段"), "tasks": .array(["任务"])])])])
        #expect(ClassroomPBL(json: legacy).phases.count == 1)

        let grouped: JSONValue = .object([
            "project": .object([
                "title": .string("项目"),
                "milestones": .object([
                    "title": .string("里程碑"),
                    "tasks": .array([.object(["id": .string("t2"), "title": .string("完成报告")])]),
                ]),
            ]),
        ])
        let groupedPBL = ClassroomPBL(json: grouped)
        #expect(groupedPBL.phases.count == 1)
        #expect(groupedPBL.taskIDs == ["t2"])
    }

    @Test func sandboxPolicyBlocksUnsafeAndCrossOriginNavigation() {
        #expect(ClassroomSandboxPolicy.allowsURL(URL(string: "https://example.com/game")!))
        #expect(!ClassroomSandboxPolicy.allowsURL(URL(string: "http://user:pass@example.com/game")!))
        #expect(!ClassroomSandboxPolicy.allowsURL(URL(string: "file:///etc/passwd")!))
        #expect(ClassroomSandboxPolicy.blockedNavigationReason(
            target: URL(string: "https://other.example/phish")!,
            allowedOrigin: URL(string: "https://example.com/game")!) != nil)
        #expect(ClassroomSandboxPolicy.blockedNavigationReason(
            target: URL(string: "https://example.com/next")!,
            allowedOrigin: URL(string: "https://example.com/game")!) == nil)
        #expect(ClassroomSandboxPolicy.blockedNavigationReason(
            target: URL(string: "data:text/html,hi")!, allowedOrigin: nil) == nil)
    }

    @Test func narrationIsPlayableOnlyWhenACompletedArtifactExists() throws {
        let pending = ClassroomNarrationState(json: .object([
            "scene_id": .string("s1"), "available": .bool(true), "has_script": .bool(true),
            "job": .object(["id": .string("job"), "status": .string("running"), "progress": .number(30)]),
        ]))
        #expect(pending.playableArtifactID == nil)
        #expect(pending.isGenerating)
        #expect(!pending.needsSynthesis)

        let ready = ClassroomNarrationState(json: .object([
            "scene_id": .string("s1"), "available": .bool(true), "has_script": .bool(true),
            "job": .object(["id": .string("job"), "status": .string("completed"), "progress": .number(100),
                            "artifact_id": .string("artifact")]),
        ]))
        #expect(ready.playableArtifactID == "artifact")

        let failed = ClassroomNarrationState(json: .object([
            "scene_id": .string("s1"), "has_script": .bool(true),
            "job": .object(["id": .string("job"), "status": .string("failed"), "error_code": .string("tts_unavailable")]),
        ]))
        #expect(failed.failureMessage != nil)
        #expect(failed.needsSynthesis)
    }

    @Test func progressDeduplicatesPagesAndBoundsHistory() {
        var progress = ClassroomProgress(courseID: "c", workspaceID: "w", stageID: "s")
        #expect(progress.visit(sceneID: "p1", index: 0, revision: 1))
        #expect(!progress.visit(sceneID: "p1", index: 0, revision: 1))
        #expect(progress.visit(sceneID: "p2", index: 1, revision: 1))
        #expect(progress.visitedPageCount == 2)
        #expect(progress.sceneIndex == 1)
        for index in 0..<600 {
            progress.visit(sceneID: "x\(index)", index: index, revision: 1)
        }
        #expect(progress.visitedSceneIDs.count <= 500)
    }

    // MARK: - Service

    @Test func playbackRetriesWithoutResumeSceneWhenServerSaysGone() async throws {
        let recorder = NativeClassroomTransport(responses: [
            HTTPResponse(data: Data("{\"detail\":\"scene_not_found\"}".utf8), statusCode: 404),
            HTTPResponse(data: try JSONValue(data: playbackPlanJSON(
                scenes: [playbackScene("s1")]).encoded()), statusCode: 200),
        ])
        let client = APIClient(baseURL: URL(string: "https://example.com/api/v1/")!) { request in
            await recorder.respond(request)
        }
        await client.restore(Session(tokens: TokenPair(accessToken: "a", refreshToken: "r"),
                                     user: UserProfile(id: "u", username: "u")))
        let plan = try await NativeClassroomService(client: client).playback(
            courseID: "course", workspaceID: "ws-1", stageID: "stage-1", sceneID: "gone")
        #expect(plan.scenes.count == 1)
        let requests = await recorder.requests
        #expect(requests.count == 2)
        let firstNames = requests[0].url.flatMap {
            URLComponents(url: $0, resolvingAgainstBaseURL: false)?.queryItems?.map(\.name)
        } ?? []
        let secondNames = requests[1].url.flatMap {
            URLComponents(url: $0, resolvingAgainstBaseURL: false)?.queryItems?.map(\.name)
        } ?? []
        #expect(firstNames.contains("scene_id"))
        #expect(secondNames.contains("scene_id") == false)
    }

    @Test func generationCarriesIdempotencyKeyAndRejectsLocalTemplates() async throws {
        let recorder = NativeClassroomTransport(responses: [
            HTTPResponse(data: try JSONValue(data: .object([
                "workspace_id": .string("ws-1"),
                "stage_id": .string("stage-1"),
                "source": .string("local-template"),
                "job": .object(["id": .string("job-1"), "status": .string("queued"), "progress": .number(0)]),
            ]).encoded()), statusCode: 200),
        ])
        let client = APIClient(baseURL: URL(string: "https://example.com/api/v1/")!) { request in
            await recorder.respond(request)
        }
        await client.restore(Session(tokens: TokenPair(accessToken: "a", refreshToken: "r"),
                                     user: UserProfile(id: "u", username: "u")))
        let service = NativeClassroomService(client: client)
        let handle = try await service.homeGenerate(courseID: "course", prompt: "光合作用",
                                                    mode: "slide", idempotencyKey: "key-1")
        #expect(handle.isLocalTemplate)
        #expect(handle.stageID == "stage-1")
        let requests = await recorder.requests
        let request = try #require(requests.first)
        #expect(request.value(forHTTPHeaderField: "Idempotency-Key") == "key-1")

        #expect(throws: (any Error).self) {
            try service.validatedPrompts(prompt: "   ", mode: "slide")
        }
        #expect(throws: (any Error).self) {
            try service.validatedPrompts(prompt: String(repeating: "长", count: 800), mode: "slide")
        }
    }

    @Test func classicPlaybackProjectsIntoTheSharedPlanAndDocument() throws {
        let raw: JSONValue = .object([
            "session_id": .string("session-1"),
            "classroom_id": .string("classroom-1"),
            "course_id": .string("course-1"),
            "title": .string("经典课堂"),
            "contract_version": .string("classroom-playback/1"),
            "start_index": .int(0),
            "scenes": .array([
                .object([
                    "id": .string("s1"),
                    "type": .string("slide"),
                    "title": .string("第一页"),
                    "order": .int(0),
                    "content": .object([
                        "canvas": .object([
                            "width": .int(1000),
                            "height": .int(562),
                            "elements": .array([
                                .object([
                                    "type": .string("text"), "left": .int(20), "top": .int(20),
                                    "width": .int(200), "height": .int(50),
                                    "content": .string("<p>经典</p>"),
                                ]),
                            ]),
                        ]),
                    ]),
                    "render": .object(["kind": .string("native")]),
                    "steps": .array([]),
                    "dropped_actions": .array([]),
                    "whiteboards": .int(0),
                    "multi_agent": .bool(false),
                ]),
            ]),
        ])
        let classic = try ClassroomClassicPlayback(json: raw)
        let plan = try ClassroomPlaybackPlan(json: classic.planJSON)
        let document = try ClassroomStageDocument(json: classic.stageJSON)
        #expect(classic.stageID == "session-1")
        #expect(plan.stageID == "session-1")
        #expect(plan.workspaceID == "course-1")
        #expect(plan.scenes.count == 1)
        #expect(document.scenes.count == 1)
        if case .slide(let slide) = document.scenes[0].content {
            #expect(slide.canvas != nil)
            #expect(slide.prefersCanvas)
        } else {
            Issue.record("经典 slide 没有投影成画布")
        }
    }

    @Test func presentationTranslatesContractErrors() {
        let conflict = APIError(statusCode: 409, code: "QUIZ_ATTEMPT_CONFLICT", message: "conflict")
        #expect(ClassroomNativePresentation.message(for: conflict, fallback: "x").contains("重新读取"))
        let gone = APIError(statusCode: 404, code: "scene_not_found", message: "gone")
        #expect(ClassroomNativePresentation.message(for: gone, fallback: "x").contains("第一页"))
        let denied = APIError(statusCode: 403, code: "FORBIDDEN", message: "denied")
        #expect(ClassroomNativePresentation.message(for: denied, fallback: "x").contains("权限"))
    }
    private func classicAudioPlayback(contentVersion: String = "v1",
                                      actionID: String = "a1",
                                      audioURL: String = "/api/v1/courses/course-1/interactive-classroom/session-1/media/audio/tts.mp3",
                                      supported: Bool = true,
                                      mediaAvailable: Bool = true,
                                      mediaReason: String? = nil) -> JSONValue {
        var media: [String: JSONValue] = [
            "id": .string("audio/tts.mp3"),
            "kind": .string("audio"),
            "role": .string("narration"),
            "element_id": .string(actionID),
            "content_type": .string("audio/mpeg"),
            "url": .string(audioURL),
            "available": .bool(mediaAvailable),
        ]
        if let mediaReason { media["reason"] = .string(mediaReason) }
        return .object([
            "session_id": .string("session-1"),
            "classroom_id": .string("classroom-1"),
            "course_id": .string("course-1"),
            "title": .string("经典课堂"),
            "contract_version": .string("classroom-playback/1"),
            "content_version": .string(contentVersion),
            "start_index": .int(0),
            "degraded": .array([]),
            "scenes": .array([
                .object([
                    "id": .string("s1"),
                    "type": .string("slide"),
                    "title": .string("第一页"),
                    "order": .int(0),
                    "content": .object([
                        "canvas": .object([
                            "width": .int(1000),
                            "height": .int(562),
                            "elements": .array([]),
                        ]),
                    ]),
                    "render": .object(["kind": .string("native")]),
                    "steps": .array([
                        .object(["action_id": .string(actionID), "type": .string("speech"), "mode": .string("sync")]),
                    ]),
                    "dropped_actions": .array([]),
                    "actions": .array([
                        .object([
                            "id": .string(actionID),
                            "type": .string("speech"),
                            "mode": .string("sync"),
                            "supported": .bool(supported),
                            "reason": supported ? JSONValue.null : JSONValue.string("speech_action_unsupported"),
                            "payload": .object(["audioUrl": .string(audioURL)]),
                        ]),
                    ]),
                    "media": .array([.object(media)]),
                    "whiteboards": .int(0),
                    "multi_agent": .bool(false),
                ]),
            ]),
        ])
    }

    @Test func classicSpeechAudioUsesActionIDMediaAndContentVersion() throws {
        let classic = try ClassroomClassicPlayback(json: classicAudioPlayback())
        let plan = try ClassroomPlaybackPlan(json: classic.planJSON)
        let document = try ClassroomStageDocument(json: classic.stageJSON)
        #expect(plan.contentVersion == "v1")
        #expect(plan.revision == ClassroomContentRevision.stable(from: "v1"))
        #expect(plan.revision != 0)
        #expect(plan.scenes[0].actions.count == 1)
        #expect(plan.scenes[0].media.count == 1)
        #expect(ClassroomPlaybackAvailability.evaluate(plan: plan, document: document).isEligible)

        switch ClassroomSpeechAudioResolver.resolve(scene: plan.scenes[0], contentVersion: plan.contentVersion) {
        case .playable(let audio):
            #expect(audio.actionID == "a1")
            #expect(audio.mediaID == "audio/tts.mp3")
            #expect(audio.apiPath == "courses/course-1/interactive-classroom/session-1/media/audio/tts.mp3")
            #expect(audio.cacheID.hasPrefix("classic_"))
        default:
            Issue.record("经典 speech 音频没有解析为可播放")
        }
    }

    @Test func classicNarrationRequiresSupportedActionAndAvailableMedia() throws {
        let blocked = try ClassroomClassicPlayback(json: classicAudioPlayback(
            mediaAvailable: false, mediaReason: "narration_audio_unavailable"))
        let blockedPlan = try ClassroomPlaybackPlan(json: blocked.planJSON)
        switch ClassroomSpeechAudioResolver.resolve(scene: blockedPlan.scenes[0], contentVersion: blockedPlan.contentVersion) {
        case .unavailable(let reason):
            #expect(reason == "narration_audio_unavailable")
        default:
            Issue.record("不可用媒体没有降级")
        }

        let unsupported = try ClassroomClassicPlayback(json: classicAudioPlayback(supported: false))
        let unsupportedPlan = try ClassroomPlaybackPlan(json: unsupported.planJSON)
        switch ClassroomSpeechAudioResolver.resolve(scene: unsupportedPlan.scenes[0], contentVersion: unsupportedPlan.contentVersion) {
        case .unavailable(let reason):
            #expect(reason == "speech_action_unsupported")
        default:
            Issue.record("不支持的 speech 没有降级")
        }

        let external = try ClassroomClassicPlayback(json: classicAudioPlayback(
            audioURL: "https://cdn.example.com/tts.mp3"))
        let externalPlan = try ClassroomPlaybackPlan(json: external.planJSON)
        switch ClassroomSpeechAudioResolver.resolve(scene: externalPlan.scenes[0], contentVersion: externalPlan.contentVersion) {
        case .unavailable(let reason):
            #expect(reason == "speech_audio_not_site_media")
        default:
            Issue.record("外链音频没有拒绝")
        }
    }

    @Test func classicContentVersionChangesRevisionAndAudioCacheKey() throws {
        let v1 = try ClassroomClassicPlayback(json: classicAudioPlayback(contentVersion: "v1"))
        let v2 = try ClassroomClassicPlayback(json: classicAudioPlayback(contentVersion: "v2"))
        #expect(v1.revision != v2.revision)
        let p1 = try ClassroomPlaybackPlan(json: v1.planJSON)
        let p2 = try ClassroomPlaybackPlan(json: v2.planJSON)
        guard case .playable(let a1) = ClassroomSpeechAudioResolver.resolve(scene: p1.scenes[0], contentVersion: p1.contentVersion),
              case .playable(let a2) = ClassroomSpeechAudioResolver.resolve(scene: p2.scenes[0], contentVersion: p2.contentVersion) else {
            Issue.record("版本变化后音频不可播放")
            return
        }
        #expect(a1.cacheID != a2.cacheID)

        let documentV1 = try ClassroomStageDocument(json: v1.stageJSON)
        let mismatchedPlan = try ClassroomPlaybackPlan(json: .object([
            "stage_id": .string("session-1"),
            "workspace_id": .string("course-1"),
            "revision": .int(v1.revision),
            "content_version": .string("v2"),
            "scenes": .array([
                .object([
                    "id": .string("s1"), "type": .string("slide"), "render": .object(["kind": .string("native")])
                ]),
            ]),
        ]))
        let mismatch = ClassroomPlaybackAvailability.evaluate(plan: mismatchedPlan, document: documentV1)
        #expect(!mismatch.isEligible)
        #expect(mismatch.detail?.contains("版本") == true)
    }

    @Test func mediaReferenceOnlyAcceptsSiteRelativePaths() {
        #expect(ClassroomMediaReference.apiPath(
            from: "/api/v1/courses/c1/interactive-classroom/s1/media/audio/a.mp3") == "courses/c1/interactive-classroom/s1/media/audio/a.mp3")
        #expect(ClassroomMediaReference.apiPath(from: "https://evil.example/a.mp3") == nil)
        #expect(ClassroomMediaReference.apiPath(from: "//evil.example/a.mp3") == nil)
        #expect(ClassroomMediaReference.apiPath(from: "data:audio/mp3;base64,AAA") == nil)
        #expect(ClassroomMediaReference.apiPath(from: "/api/v1/courses/../secret.mp3") == nil)
        #expect(ClassroomMediaReference.apiPath(from: "/api/v1/courses/c1/a.mp3?token=x") == nil)
        #expect(ClassroomMediaReference.apiPath(from: "/api/v1/courses/c1\\a.mp3") == nil)
        #expect(ClassroomMediaReference.audioExtension(path: "a.mp3", contentType: "application/octet-stream") == "mp3")
    }

    @Test func classicCanvasKeepsOnlySiteAudioAndVideo() throws {
        let raw: JSONValue = .object([
            "session_id": .string("session-1"),
            "course_id": .string("course-1"),
            "content_version": .string("v1"),
            "scenes": .array([
                .object([
                    "id": .string("s1"), "type": .string("slide"), "title": .string("媒体页"), "order": .int(0),
                    "render": .object(["kind": .string("native")]),
                    "content": .object([
                        "canvas": .object([
                            "width": .int(1000), "height": .int(562),
                            "elements": .array([
                                .object([
                                    "id": .string("audio-ok"), "type": .string("audio"),
                                    "src": .string("/api/v1/courses/c1/interactive-classroom/session-1/media/audio/a.mp3"),
                                    "contentType": .string("audio/mpeg"), "left": .int(0), "top": .int(0),
                                    "width": .int(200), "height": .int(60),
                                ]),
                                .object([
                                    "id": .string("audio-bad"), "type": .string("audio"),
                                    "src": .string("https://cdn.example.com/a.mp3"), "left": .int(0), "top": .int(80),
                                    "width": .int(200), "height": .int(60),
                                ]),
                                .object([
                                    "id": .string("video-ok"), "type": .string("video"),
                                    "src": .string("/api/v1/courses/c1/interactive-classroom/session-1/media/media/v.mp4"),
                                    "contentType": .string("video/mp4"), "left": .int(300), "top": .int(0),
                                    "width": .int(300), "height": .int(180),
                                ]),
                            ]),
                        ]),
                    ]),
                ]),
            ]),
        ])
        let classic = try ClassroomClassicPlayback(json: raw)
        let document = try ClassroomStageDocument(json: classic.stageJSON)
        guard case .slide(let slide) = document.scenes[0].content, let canvas = slide.canvas else {
            Issue.record("媒体页没有画布"); return
        }
        guard case .audio(let ok) = canvas.elements[0], case .audio(let bad) = canvas.elements[1],
              case .video(let video) = canvas.elements[2] else {
            Issue.record("画布媒体类型没有投影"); return
        }
        #expect(ok.isPlayable)
        #expect(!bad.isPlayable)
        #expect(video.isPlayable)
    }
    // MARK: - Classic sequence and media path regressions

    private func sequenceSceneJSON(secondSupported: Bool = true,
                                   secondType: String = "speech",
                                   omitSecondAction: Bool = false) -> JSONValue {
        let audioURL = "/api/v1/courses/c1/interactive-classroom/s1/media/audio/a1.mp3"
        let audio2URL = "/api/v1/courses/c1/interactive-classroom/s1/media/audio/a2.mp3"
        var actions: [JSONValue] = [
            .object([
                "id": .string("a1"), "type": .string("speech"), "mode": .string("sync"),
                "supported": .bool(true),
                "payload": .object(["audioUrl": .string(audioURL)]),
            ]),
            .object([
                "id": .string("a2"), "type": .string(secondType), "mode": .string("sync"),
                "supported": .bool(secondSupported),
                "reason": secondSupported ? JSONValue.null : JSONValue.string("speech_action_unsupported"),
                "payload": .object(["audioUrl": .string(audio2URL)]),
            ]),
            .object([
                "id": .string("a3"), "type": .string("play_video"), "mode": .string("sync"),
                "supported": .bool(true),
                "payload": .object(["elementId": .string("video-1")]),
            ]),
        ]
        if omitSecondAction { actions.remove(at: 1) }
        return .object([
            "id": .string("s1"), "type": .string("slide"), "title": .string("顺序页"), "order": .int(0),
            "render": .object(["kind": .string("native")]),
            "steps": .array([
                .object(["action_id": .string("a1"), "type": .string("speech"), "mode": .string("sync")]),
                .object(["action_id": .string("a2"), "type": .string("speech"), "mode": .string("sync")]),
                .object(["action_id": .string("a3"), "type": .string("play_video"), "mode": .string("sync")]),
            ]),
            "actions": .array(actions),
            "media": .array([
                .object([
                    "id": .string("audio/a1.mp3"), "kind": .string("audio"), "role": .string("narration"),
                    "element_id": .string("a1"), "content_type": .string("audio/mpeg"),
                    "url": .string(audioURL), "available": .bool(true),
                ]),
                .object([
                    "id": .string("audio/a2.mp3"), "kind": .string("audio"), "role": .string("narration"),
                    "element_id": .string("a2"), "content_type": .string("audio/mpeg"),
                    "url": .string(audio2URL), "available": .bool(true),
                ]),
                .object([
                    "id": .string("media/v1.mp4"), "kind": .string("video"), "role": .string("slide_element"),
                    "element_id": .string("video-1"), "content_type": .string("video/mp4"),
                    "url": .string("/api/v1/courses/c1/interactive-classroom/s1/media/media/v1.mp4"),
                    "available": .bool(true),
                ]),
            ]),
            "dropped_actions": .array([]),
            "whiteboards": .int(0),
            "multi_agent": .bool(false),
        ])
    }

    private func sequencePlan(secondSupported: Bool = true,
                              secondType: String = "speech",
                              omitSecondAction: Bool = false) throws -> ClassroomPlaybackPlan {
        try ClassroomPlaybackPlan(json: .object([
            "stage_id": .string("s1"), "workspace_id": .string("c1"),
            "title": .string("经典课堂"), "revision": .int(1), "content_version": .string("v1"),
            "start_index": .int(0), "degraded": .array([]),
            "scenes": .array([sequenceSceneJSON(
                secondSupported: secondSupported, secondType: secondType,
                omitSecondAction: omitSecondAction)]),
        ]))
    }

    @Test func classicSequenceFollowsServiceStepOrderAndResolvesEachSpeech() throws {
        let plan = try sequencePlan()
        let planned = ClassroomActionSequencePlanner.plan(scene: plan.scenes[0])
        #expect(planned.total == 3)
        #expect(planned.operations.map(\.actionID) == ["a1", "a2", "a3"])
        #expect(planned.operations.map(\.actionType) == ["speech", "speech", "play_video"])
        #expect(ClassroomActionSequencePlanner.isFireAndForget("spotlight"))
        #expect(ClassroomActionSequencePlanner.isFireAndForget("laser"))
        #expect(!ClassroomActionSequencePlanner.isFireAndForget("speech"))

        guard case .playable(let first) = ClassroomSpeechAudioResolver.resolve(
            action: plan.scenes[0].actions[0], in: plan.scenes[0], contentVersion: plan.contentVersion
        ), case .playable(let second) = ClassroomSpeechAudioResolver.resolve(
            action: plan.scenes[0].actions[1], in: plan.scenes[0], contentVersion: plan.contentVersion
        ) else {
            Issue.record("两段顺序讲解音频没有分别解析")
            return
        }
        #expect(first.actionID == "a1")
        #expect(second.actionID == "a2")
        #expect(first.cacheID != second.cacheID)
    }

    @Test func classicSequenceBlocksUnsupportedMissingAndMismatchedActions() throws {
        let unsupported = ClassroomActionSequencePlanner.plan(
            scene: try sequencePlan(secondSupported: false).scenes[0])
        guard case .blocked(_, _, let unsupportedReason) = unsupported.operations[1] else {
            Issue.record("supported=false 没有阻塞"); return
        }
        #expect(unsupportedReason == "speech_action_unsupported")

        let missing = ClassroomActionSequencePlanner.plan(
            scene: try sequencePlan(omitSecondAction: true).scenes[0])
        guard case .blocked(_, _, let missingReason) = missing.operations[1] else {
            Issue.record("缺失动作没有阻塞"); return
        }
        #expect(missingReason == "action_missing")

        let mismatch = ClassroomActionSequencePlanner.plan(
            scene: try sequencePlan(secondType: "play_video").scenes[0])
        guard case .blocked(_, _, let mismatchReason) = mismatch.operations[1] else {
            Issue.record("类型不一致没有阻塞"); return
        }
        #expect(mismatchReason == "action_type_mismatch")
    }

    @Test func quizFixturePromptStringOptionsAndNumericAnswerAreAccepted() throws {
        let set = ClassroomQuizSet(json: .object([
            "questions": .array([
                .object([
                    "id": .string("q1"),
                    "type": .string("single"),
                    "prompt": .string("函数在区间内单调递增的条件是？"),
                    "options": .array([.string("A"), .string("B"), .string("C"), .string("D")]),
                    "answer": .int(0),
                ]),
            ]),
        ]))
        let question = try #require(set.questions.first)
        #expect(question.prompt == "函数在区间内单调递增的条件是？")
        #expect(question.options.map(\.value) == ["A", "B", "C", "D"])
        #expect(question.answers == ["A"])
        let evaluation = ClassroomQuizEvaluation.evaluate(
            questions: set.questions, answers: ["q1": .choice("A")], studentLed: false)
        #expect(evaluation.score == 1)
        #expect(evaluation.total == 1)
        #expect(evaluation.results.first?.correct == true)
    }

    @Test func classicMediaRequestCarriesBearerForTrustedSessionPath() async throws {
        let client = APIClient(baseURL: URL(string: "https://class.example/api/v1/")!) { request in
            #expect(request.url?.path == "/api/v1/courses/c1/interactive-classroom/s1/media/audio/a.wav")
            #expect(request.value(forHTTPHeaderField: "Authorization") == "Bearer trusted-token")
            return HTTPResponse(data: Data(), statusCode: 200)
        }
        await client.restore(Session(
            tokens: TokenPair(accessToken: "trusted-token", refreshToken: "refresh"),
            user: UserProfile(id: "u", username: "u")
        ))
        let path = try ClassroomMediaPathResolver.resolve(
            scopePath: "courses/c1/interactive-classroom", sessionID: "s1",
            source: "audio/a.wav", expectedKind: "audio"
        )
        _ = try await client.requestData(.get, path: path)
    }

    @Test func classicMediaPathAcceptsRelativeAndDoubleMediaWithinSession() throws {
        let scope = "courses/c1/interactive-classroom"
        let session = "s1"
        let full = "/api/v1/courses/c1/interactive-classroom/s1/media/media/v.mp4"
        #expect(try ClassroomMediaPathResolver.resolve(
            scopePath: scope, sessionID: session,
            source: full, expectedKind: "video"
        ) == "courses/c1/interactive-classroom/s1/media/media/v.mp4")
        #expect(try ClassroomMediaPathResolver.resolve(
            scopePath: scope, sessionID: session,
            source: "media/v.mp4", expectedKind: "video"
        ) == "courses/c1/interactive-classroom/s1/media/media/v.mp4")
        #expect(try ClassroomMediaPathResolver.resolve(
            scopePath: scope, sessionID: session,
            source: "audio/a.wav", expectedKind: "audio"
        ) == "courses/c1/interactive-classroom/s1/media/audio/a.wav")

        #expect((try? ClassroomMediaPathResolver.resolve(
            scopePath: scope, sessionID: session,
            source: "https://evil.example/v.mp4", expectedKind: "video"
        )) == nil)
        #expect((try? ClassroomMediaPathResolver.resolve(
            scopePath: scope, sessionID: session,
            source: "courses/c2/interactive-classroom/s2/media/media/v.mp4", expectedKind: "video"
        )) == nil)
        #expect((try? ClassroomMediaPathResolver.resolve(
            scopePath: scope, sessionID: session,
            source: "/api/v1/courses/c2/interactive-classroom/s2/media/media/v.mp4", expectedKind: "video"
        )) == nil)
        #expect((try? ClassroomMediaPathResolver.resolve(
            scopePath: scope, sessionID: session,
            source: "media/media/v.mp4", expectedKind: "audio"
        )) == nil)
        #expect((try? ClassroomMediaPathResolver.resolve(
            scopePath: scope, sessionID: session,
            source: "../secret", expectedKind: "video"
        )) == nil)
    }
}

private actor NativeClassroomTransport {
    var requests: [URLRequest] = []
    private var responses: [HTTPResponse]

    init(responses: [HTTPResponse]) { self.responses = responses }

    func respond(_ request: URLRequest) -> HTTPResponse {
        requests.append(request)
        guard !responses.isEmpty else { return HTTPResponse(data: Data("{}".utf8), statusCode: 200) }
        return responses.removeFirst()
    }
}
