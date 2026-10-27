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
    public func favoriteFile(id: String) async throws -> JSONValue { try await client.request(.post, path: "personal-hub/files/\(id.pathComponent)/favorite") }
    public func removeFavorite(id: String) async throws { _ = try await client.request(.delete, path: "personal-hub/favorites/\(id.pathComponent)") }
}
