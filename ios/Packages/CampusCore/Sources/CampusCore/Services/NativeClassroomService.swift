import Foundation

/// 受管工作台课堂的原生播放数据通路。
///
/// 全部接口都已经是公开契约：工作台、舞台、播放计划、场景、讲解与测验作答。
/// 这里不碰经典课堂的 `session_id` 路径，也不猜任何未声明的字段。
public struct NativeClassroomService: Sendable {
    public static let generationPromptLimit = 750
    public static let generationModeLimit = 80

    private let client: APIClient

    public init(client: APIClient) { self.client = client }

    private func root(courseID: String) -> String {
        "courses/\(courseID.pathComponent)"
    }

    private func stagePath(courseID: String, workspaceID: String, stageID: String) -> String {
        root(courseID: courseID) + "/workspaces/\(workspaceID.pathComponent)/stages/\(stageID.pathComponent)"
    }

    // MARK: - Workspaces and stages

    public func workspaces(courseID: String) async throws -> [ClassroomWorkspace] {
        let json = try await client.request(path: root(courseID: courseID) + "/workspaces", query: ["limit": "50"])
        return try json.items.map { try ClassroomWorkspace(json: $0) }
    }

    public func stages(courseID: String, workspaceID: String) async throws -> [ClassroomStageSummary] {
        let path = root(courseID: courseID) + "/workspaces/\(workspaceID.pathComponent)/stages"
        let json = try await client.request(path: path, query: ["limit": "50"])
        return try json.items.map { try ClassroomStageSummary(json: $0) }
    }

    public func stageEnvelope(courseID: String, workspaceID: String, stageID: String) async throws -> JSONValue {
        try await client.request(path: stagePath(courseID: courseID, workspaceID: workspaceID, stageID: stageID))
    }

    public func stage(courseID: String, workspaceID: String, stageID: String) async throws -> ClassroomStageDocument {
        try ClassroomStageDocument(json: try await stageEnvelope(courseID: courseID, workspaceID: workspaceID, stageID: stageID))
    }

    // MARK: - Playback

    public func playbackJSON(courseID: String, workspaceID: String, stageID: String,
                             sceneID: String? = nil) async throws -> JSONValue {
        let path = stagePath(courseID: courseID, workspaceID: workspaceID, stageID: stageID) + "/playback"
        var query: [String: String] = [:]
        if let sceneID, !sceneID.isEmpty { query["scene_id"] = sceneID }
        do {
            return try await client.request(path: path, query: query)
        } catch let error as APIError where error.statusCode == 404 && query["scene_id"] != nil {
            return try await client.request(path: path)
        }
    }

    /// `scene_id` 指向上次停留的页。服务端明确返回 404（页面已被删除）时，
    /// 去掉该参数重试一次，让播放退回收到的 `start_index`，而不是整节课打不开。
    public func playback(courseID: String, workspaceID: String, stageID: String,
                         sceneID: String? = nil) async throws -> ClassroomPlaybackPlan {
        try ClassroomPlaybackPlan(json: try await playbackJSON(
            courseID: courseID, workspaceID: workspaceID, stageID: stageID, sceneID: sceneID))
    }

    // MARK: - Generation

    /// 课程“新生成一讲”：服务端会解析或创建课程工作台，再排入首舞台任务。
    public func homeGenerate(courseID: String, prompt: String, mode: String = "slide",
                             idempotencyKey: String = UUID().uuidString) async throws -> ClassroomGenerationHandle {
        let trimmed = try validatedPrompts(prompt: prompt, mode: mode)
        let json = try await client.request(
            .post,
            path: root(courseID: courseID) + "/home-generate",
            body: ["mode": .string(trimmed.mode), "prompt": .string(trimmed.prompt)],
            headers: ["Idempotency-Key": validatedKey(idempotencyKey)])
        return try ClassroomGenerationHandle(json: json)
    }

    /// 在既有工作台里再生成一个舞台。
    public func generateStage(courseID: String, workspaceID: String, prompt: String,
                              mode: String = "slide", idempotencyKey: String = UUID().uuidString) async throws -> ClassroomGenerationHandle {
        let trimmed = try validatedPrompts(prompt: prompt, mode: mode)
        let path = root(courseID: courseID) + "/workspaces/\(workspaceID.pathComponent)/generate"
        let json = try await client.request(
            .post,
            path: path,
            body: ["mode": .string(trimmed.mode), "prompt": .string(trimmed.prompt)],
            headers: ["Idempotency-Key": validatedKey(idempotencyKey)])
        return try ClassroomGenerationHandle(json: json)
    }

    public func job(courseID: String, jobID: String) async throws -> ClassroomGenerationJob {
        let path = root(courseID: courseID) + "/jobs/\(jobID.pathComponent)"
        return try ClassroomGenerationJob(json: try await client.request(path: path))
    }

    /// 轮询到终态。取消会传播到调用方，过期任务不会把结果写进新页面。
    public func waitForJob(courseID: String, jobID: String, timeout: TimeInterval = 180,
                           pollInterval: Duration = .milliseconds(900),
                           onProgress: (@Sendable (ClassroomGenerationJob) -> Void)? = nil) async throws -> ClassroomGenerationJob {
        let deadline = Date().addingTimeInterval(timeout)
        var latest = try await job(courseID: courseID, jobID: jobID)
        onProgress?(latest)
        while latest.isRunning {
            try Task.checkCancellation()
            guard Date() < deadline else { throw APIError(statusCode: 504, code: "JOB_TIMEOUT", message: "生成任务超时，请稍后重试。") }
            try await Task.sleep(for: pollInterval)
            latest = try await job(courseID: courseID, jobID: jobID)
            onProgress?(latest)
        }
        return latest
    }

    // MARK: - Narration

    public func narration(courseID: String, workspaceID: String, stageID: String, sceneID: String) async throws -> ClassroomNarrationState {
        let path = stagePath(courseID: courseID, workspaceID: workspaceID, stageID: stageID)
            + "/scenes/\(sceneID.pathComponent)/narration"
        return ClassroomNarrationState(json: try await client.request(path: path))
    }

    /// 服务端三层去重复用同一任务；这里只负责提交与读取任务号。
    public func synthesizeNarration(courseID: String, workspaceID: String, stageID: String,
                                    sceneID: String, idempotencyKey: String = UUID().uuidString) async throws -> ClassroomNarrationState {
        let path = stagePath(courseID: courseID, workspaceID: workspaceID, stageID: stageID)
            + "/scenes/\(sceneID.pathComponent)/narration"
        let json = try await client.request(.post, path: path, headers: ["Idempotency-Key": validatedKey(idempotencyKey)])
        return ClassroomNarrationState(json: json)
    }

    /// 讲解产物只允许音频；类型不符时宁可报错，也不塞给播放器变成静音。
    public func downloadNarration(courseID: String, artifactID: String) async throws -> DownloadedResource {
        let resource = try await client.download(path: root(courseID: courseID) + "/artifacts/\(artifactID.pathComponent)")
        let type = (resource.mimeType ?? "").lowercased()
        let suffix = resource.url.pathExtension.lowercased()
        guard type.contains("audio") || ["wav", "mp3", "m4a", "aac"].contains(suffix) else {
            throw ClassroomNativeError.invalidResponse("讲解产物不是音频文件（\(resource.mimeType ?? "未知类型")）。")
        }
        return resource
    }

    // MARK: - Quiz attempts

    public func quizAttempt(courseID: String, workspaceID: String, stageID: String, sceneID: String) async throws -> ClassroomQuizAttempt {
        let path = stagePath(courseID: courseID, workspaceID: workspaceID, stageID: stageID)
            + "/scenes/\(sceneID.pathComponent)/quiz-attempt"
        return try ClassroomQuizAttempt(json: try await client.request(path: path))
    }

    public func saveQuizAttempt(courseID: String, workspaceID: String, stageID: String, sceneID: String,
                                attemptID: String, phase: String, answers: [String: ClassroomQuizAnswer],
                                results: [JSONValue]?, startNewAttempt: Bool) async throws -> ClassroomQuizAttempt {
        let path = stagePath(courseID: courseID, workspaceID: workspaceID, stageID: stageID)
            + "/scenes/\(sceneID.pathComponent)/quiz-attempt"
        var body: [String: JSONValue] = [
            "attempt_id": .string(attemptID),
            "phase": .string(phase),
            "answers": .object(answers.mapValues(\.json)),
            "start_new_attempt": .bool(startNewAttempt),
        ]
        body["results"] = .array(results ?? [])
        return try ClassroomQuizAttempt(json: try await client.request(.post, path: path, body: .object(body)))
    }

    // MARK: - Validation

    public func validatedPrompts(prompt: String, mode: String) throws -> (prompt: String, mode: String) {
        let prompt = prompt.trimmingCharacters(in: .whitespacesAndNewlines)
        let mode = mode.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !prompt.isEmpty else { throw ClassroomNativeError.emptyGenerationPrompt }
        guard prompt.count <= Self.generationPromptLimit else {
            throw ClassroomNativeError.promptTooLong(Self.generationPromptLimit)
        }
        return (prompt, mode.isEmpty ? "slide" : String(mode.prefix(Self.generationModeLimit)))
    }

    private func validatedKey(_ key: String) -> String {
        let trimmed = key.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return UUID().uuidString }
        return String(trimmed.prefix(180))
    }
}
