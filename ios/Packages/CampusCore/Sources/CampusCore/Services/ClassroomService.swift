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
}
