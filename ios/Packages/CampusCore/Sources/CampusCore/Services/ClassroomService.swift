import Foundation

public struct ClassroomService: Sendable {
    public let client: APIClient
    public let scope: ClassroomScope
    public init(client: APIClient, scope: ClassroomScope) { self.client = client; self.scope = scope }
    public func status() async throws -> JSONValue { try await client.request(path: scope.validatedPath() + "/status") }
    public func history() async throws -> [JSONValue] { try await client.request(path: scope.validatedPath()).items }
    public func progress(sessionID: String) async throws -> JSONValue { try await client.request(path: scope.validatedPath() + "/jobs/" + sessionID.pathComponent) }
    public func plan(mode: String) async throws -> JSONValue {
        guard case .course = scope else { return .null }
        return try await client.request(path: scope.validatedPath() + "/plan", query: ["mode": mode])
    }
    public func generate(body: JSONValue, retrySessionID: String? = nil) async throws -> JSONValue {
        var path = try scope.validatedPath()
        if let retrySessionID {
            guard case .course = scope else { throw APIError(code: "CLASSROOM_RETRY", message: "自主选题请重新确认生成内容后再提交。") }
            path += "/" + retrySessionID.pathComponent + "/retry"
        } else { path += "/generate" }
        return try await client.request(.post, path: path, body: body)
    }
    public func upload(filename: String, mimeType: String, data: Data, key: String) async throws -> JSONValue {
        _ = try scope.validatedPath()
        guard data.count <= 2 * 1024 * 1024, !filename.contains("/"), !filename.contains("\\"), filename.count <= 255 else {
            throw APIError(code: "CLASSROOM_MATERIAL", message: "请使用不超过 2 MiB 的 PDF、Word 或文本资料。")
        }
        return try await client.upload(path: scope.materialsPath, filename: filename, mimeType: mimeType, data: data, headers: ["Idempotency-Key": key])
    }

    // MARK: - 经典课堂原生播放

    private func sessionPath(_ sessionID: String) throws -> String {
        ClassroomMediaPathResolver.sessionPath(scopePath: try scope.validatedPath(), sessionID: sessionID)
    }

    public func playbackJSON(sessionID: String, sceneID: String? = nil) async throws -> JSONValue {
        let path = try sessionPath(sessionID) + "/playback"
        var query: [String: String] = [:]
        if let sceneID, !sceneID.isEmpty { query["scene_id"] = sceneID }
        do {
            return try await client.request(path: path, query: query)
        } catch let error as APIError where error.statusCode == 404 && query["scene_id"] != nil {
            return try await client.request(path: path)
        }
    }

    public func quizAttempt(sessionID: String, sceneID: String) async throws -> ClassroomQuizAttempt {
        let path = try sessionPath(sessionID) + "/scenes/\(sceneID.pathComponent)/quiz-attempt"
        return try ClassroomQuizAttempt(json: try await client.request(path: path))
    }

    public func saveQuizAttempt(sessionID: String, sceneID: String, attemptID: String,
                                phase: String, answers: [String: ClassroomQuizAnswer],
                                results: [JSONValue]?, startNewAttempt: Bool) async throws -> ClassroomQuizAttempt {
        let path = try sessionPath(sessionID) + "/scenes/\(sceneID.pathComponent)/quiz-attempt"
        var body: [String: JSONValue] = [
            "attempt_id": .string(attemptID),
            "phase": .string(phase),
            "answers": .object(answers.mapValues(\.json)),
            "start_new_attempt": .bool(startNewAttempt),
        ]
        body["results"] = .array(results ?? [])
        return try ClassroomQuizAttempt(json: try await client.request(.post, path: path, body: .object(body)))
    }

    // MARK: - 经典课堂媒体

    /// 经典讲解音频只允许当前 session 的 `media/audio/`，并从已鉴权的 APIClient 下载。
    /// 调用方拿到的是临时文件，落缓存前必须校验类型与体积。
    public func downloadSessionAudio(sessionID: String, audioURL: String,
                                     maxBytes: Int = 64 * 1024 * 1024) async throws -> DownloadedResource {
        let path = try ClassroomMediaPathResolver.resolve(
            scopePath: try scope.validatedPath(),
            sessionID: sessionID,
            source: audioURL,
            expectedKind: "audio"
        )
        guard ClassroomMediaReference.audioExtension(path: path) != nil else {
            throw ClassroomNativeError.invalidResponse("讲解音频不是受支持的音频格式。")
        }
        return try await downloadValidatedMedia(path: path, expectedKind: "audio", maxBytes: maxBytes)
    }

    /// 画布里的音频/视频元素使用与讲解相同的本站鉴权路径，不把外链交给系统播放器。
    public func downloadSessionMedia(sessionID: String, mediaURL: String,
                                     expectedKind: String, maxBytes: Int = 128 * 1024 * 1024) async throws -> DownloadedResource {
        let path = try ClassroomMediaPathResolver.resolve(
            scopePath: try scope.validatedPath(),
            sessionID: sessionID,
            source: mediaURL,
            expectedKind: expectedKind
        )
        return try await downloadValidatedMedia(path: path, expectedKind: expectedKind, maxBytes: maxBytes)
    }

    private func downloadValidatedMedia(path: String, expectedKind: String,
                                        maxBytes: Int) async throws -> DownloadedResource {
        let resource = try await client.download(path: path)
        do {
            let size = (try? resource.url.resourceValues(forKeys: [.fileSizeKey]))?.fileSize ?? 0
            guard size > 0, size <= maxBytes else {
                throw ClassroomNativeError.invalidResponse("课堂媒体文件为空或超过大小限制。")
            }
            let type = (resource.mimeType ?? "").trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
            let ext = (path as NSString).pathExtension.lowercased()
            if expectedKind == "audio" {
                let audioExtensions = ClassroomMediaReference.audioExtensions
                guard type.isEmpty || type.hasPrefix("audio/") || type == "application/octet-stream",
                      audioExtensions.contains(ext) else {
                    throw ClassroomNativeError.invalidResponse("讲解音频不是音频文件（\(resource.mimeType ?? "未知类型")）。")
                }
            } else if expectedKind == "video" {
                let videoExtensions = ["mp4", "webm", "mov", "m4v"]
                guard type.isEmpty || type.hasPrefix("video/") || type == "application/octet-stream",
                      videoExtensions.contains(ext) else {
                    throw ClassroomNativeError.invalidResponse("课堂视频不是视频文件（\(resource.mimeType ?? "未知类型")）。")
                }
            } else {
                throw ClassroomNativeError.invalidResponse("不支持的课堂媒体类型。")
            }
            return resource
        } catch {
            try? FileManager.default.removeItem(at: resource.url)
            throw error
        }
    }
}
