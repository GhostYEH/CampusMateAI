import Foundation

public struct PersonalService: Sendable {
    public let client: APIClient
    public init(client: APIClient) { self.client = client }

    public func universities(query: String = "") async throws -> JSONValue {
        try await client.request(path: "universities", query: query.isEmpty ? [:] : ["q": query])
    }
    public func updateProfile(_ fields: [String: JSONValue]) async throws -> UserProfile {
        let result = try await client.request(.patch, path: "auth/me", body: .object(fields))
        let user = try UserProfile(json: result["user"].object == nil ? result : result["user"])
        await client.updateUser(user)
        return user
    }
    public func chaoxingStatus() async throws -> JSONValue { try await client.request(path: "chaoxing/status") }
    public func connectChaoxing(username: String, password: String) async throws -> JSONValue {
        try await client.request(.post, path: "chaoxing/login", body: ["username": .string(username), "password": .string(password)])
    }
    public func syncChaoxing() async throws -> JSONValue { try await client.request(.post, path: "chaoxing/sync") }
    public func disconnectChaoxing() async throws { _ = try await client.request(.post, path: "chaoxing/disconnect") }
    public func files() async throws -> [JSONValue] { try await client.request(path: "personal-hub/files").items }
    public func favorites() async throws -> [JSONValue] { try await client.request(path: "personal-hub/favorites").items }
    public func removeFile(id: String) async throws { _ = try await client.request(.delete, path: "personal-hub/files/\(id.pathComponent)") }
    public func favoriteFile(id: String, favorite: Bool = true) async throws -> JSONValue {
        try await client.request(.post, path: "personal-hub/files/\(id.pathComponent)/favorite", body: ["favorite": .bool(favorite)])
    }
    public func removeFavorite(id: String) async throws { _ = try await client.request(.delete, path: "personal-hub/favorites/\(id.pathComponent)") }

    /// The contribution endpoint needs the image plus non-file form fields, so
    /// it cannot use the single-field upload helper.
    public func uploadExpressionSample(image: Data, mimeType: String = "image/jpeg",
                                       label: String, modelVersion: String = "ios-client-v1") async throws -> JSONValue {
        let boundary = "CampusMate-\(UUID().uuidString)"
        var body = Data()
        func append(_ value: String) { body.append(Data(value.utf8)) }
        for (name, value) in [("label", label), ("consent", "true"), ("model_version", modelVersion)] {
            append("--\(boundary)\r\n")
            append("Content-Disposition: form-data; name=\"\(name)\"\r\n\r\n")
            append("\(value)\r\n")
        }
        append("--\(boundary)\r\n")
        append("Content-Disposition: form-data; name=\"image\"; filename=\"expression.jpg\"\r\n")
        append("Content-Type: \(mimeType)\r\n\r\n")
        body.append(image)
        append("\r\n--\(boundary)--\r\n")
        let response = try await client.requestData(.post, path: "contributions/expression-samples",
                                                    data: body,
                                                    contentType: "multipart/form-data; boundary=\(boundary)")
        return try JSONValue(data: response.data)
    }

    public func deleteExpressionSample(id: String) async throws {
        _ = try await client.request(.delete, path: "contributions/expression-samples/\(id.pathComponent)")
    }
}
