import Foundation

public enum HTTPMethod: String, Sendable { case get = "GET", post = "POST", patch = "PATCH", put = "PUT", delete = "DELETE" }

public struct HTTPResponse: Sendable {
    public let data: Data
    public let statusCode: Int
    public let headers: [String: String]
    public init(data: Data, statusCode: Int, headers: [String: String] = [:]) {
        self.data = data; self.statusCode = statusCode; self.headers = headers
    }
    public func header(_ name: String) -> String? { headers.first { $0.key.caseInsensitiveCompare(name) == .orderedSame }?.value }
}

public struct APIError: Error, LocalizedError, Sendable, Equatable {
    public let statusCode: Int
    public let code: String
    public let message: String
    public let requestID: String?
    public let retryAfter: TimeInterval?
    public let details: JSONValue
    public var errorDescription: String? { message }
    public init(statusCode: Int = 0, code: String, message: String, requestID: String? = nil, retryAfter: TimeInterval? = nil, details: JSONValue = .null) {
        self.statusCode = statusCode; self.code = code; self.message = message
        self.requestID = requestID; self.retryAfter = retryAfter; self.details = details
    }
    public init(response: HTTPResponse) {
        let json = (try? JSONValue(data: response.data)) ?? .null
        self.init(statusCode: response.statusCode, code: json["code"].string ?? "HTTP_\(response.statusCode)",
                  message: json["message"].string ?? "请求失败（\(response.statusCode)），请稍后重试。",
                  requestID: json["request_id"].string ?? response.header("X-Request-ID"),
                  retryAfter: response.header("Retry-After").flatMap(Double.init) ?? json["details"]["retry_after_seconds"].double,
                  details: json["details"])
    }
}

public typealias HTTPTransport = @Sendable (URLRequest) async throws -> HTTPResponse

public struct DownloadedResource: Sendable {
    public let url: URL
    public let filename: String
    public let mimeType: String?
}

private final class SameOriginRedirectDelegate: NSObject, URLSessionTaskDelegate, Sendable {
    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse,
                    newRequest request: URLRequest, completionHandler: @escaping @Sendable (URLRequest?) -> Void) {
        let old = response.url.flatMap { URLComponents(url: $0, resolvingAgainstBaseURL: true) }
        let new = request.url.flatMap { URLComponents(url: $0, resolvingAgainstBaseURL: true) }
        let allowed = old?.scheme == new?.scheme && old?.host == new?.host && old?.port == new?.port
        completionHandler(allowed ? request : nil)
    }
}

private enum HTTPRuntime {
    static let session: URLSession = {
        let configuration = URLSessionConfiguration.default
        configuration.timeoutIntervalForRequest = 60
        configuration.timeoutIntervalForResource = 600
        configuration.httpShouldSetCookies = false
        configuration.urlCache = nil
        return URLSession(configuration: configuration, delegate: SameOriginRedirectDelegate(), delegateQueue: nil)
    }()

    static func send(_ request: URLRequest) async throws -> HTTPResponse {
        let (data, response) = try await session.data(for: request)
        guard let http = response as? HTTPURLResponse else { throw APIError(code: "INVALID_RESPONSE", message: "服务器响应无效。") }
        return HTTPResponse(data: data, statusCode: http.statusCode,
                            headers: http.allHeaderFields.reduce(into: [:]) { result, field in result[String(describing: field.key)] = String(describing: field.value) })
    }
}

public actor APIClient {
    public nonisolated let baseURL: URL
    public private(set) var currentSession: Session?
    private let transport: HTTPTransport
    private var generation: UInt64 = 0
    private var refreshTask: Task<TokenPair, any Error>?
    private var sessionObserver: (@Sendable (Session?) -> Void)?

    public init(baseURL: URL, transport: HTTPTransport? = nil) {
        self.baseURL = baseURL
        self.transport = transport ?? HTTPRuntime.send
    }

    public func observeSession(_ observer: @escaping @Sendable (Session?) -> Void) { sessionObserver = observer }

    public func restore(_ session: Session?) {
        generation &+= 1; refreshTask?.cancel(); refreshTask = nil
        currentSession = session; sessionObserver?(session)
    }

    @discardableResult
    public func login(username: String, password: String) async throws -> Session {
        restore(nil)
        let epoch = generation
        let json = try await request(.post, path: "auth/login", body: ["username": .string(username), "password": .string(password)], authenticated: false)
        try validate(epoch)
        let tokens = try TokenPair(json: json)
        let user: UserProfile
        if json["user"].object != nil { user = try UserProfile(json: json["user"]) }
        else {
            let request = try makeRequest(.get, path: "auth/me", token: tokens.accessToken)
            let response = try await transport(request)
            try validate(epoch); try check(response)
            user = try UserProfile(json: try JSONValue(data: response.data)["user"])
        }
        let session = Session(tokens: tokens, user: user)
        currentSession = session; sessionObserver?(session)
        return session
    }

    public func logout() async {
        let previous = currentSession
        restore(nil)
        guard let previous else { return }
        if let request = try? makeRequest(.post, path: "auth/logout", body: ["refresh_token": .string(previous.tokens.refreshToken)], token: previous.tokens.accessToken) {
            _ = try? await transport(request)
        }
    }

    public func updateUser(_ user: UserProfile) {
        guard currentSession?.user.id == user.id else { return }
        currentSession?.user = user; sessionObserver?(currentSession)
    }

    public func request(_ method: HTTPMethod = .get, path: String, query: [String: String] = [:], body: JSONValue? = nil,
                        authenticated: Bool = true, headers: [String: String] = [:]) async throws -> JSONValue {
        let response = try await send(method, path: path, query: query, data: body?.encoded(), authenticated: authenticated,
                                      contentType: body == nil ? nil : "application/json", headers: headers)
        return response.data.isEmpty ? .null : try JSONValue(data: response.data)
    }

    public func requestData(_ method: HTTPMethod = .get, path: String, query: [String: String] = [:], data: Data? = nil,
                            contentType: String? = nil, headers: [String: String] = [:]) async throws -> HTTPResponse {
        try await send(method, path: path, query: query, data: data, authenticated: true, contentType: contentType, headers: headers)
    }

    public func upload(path: String, fieldName: String = "file", filename: String, mimeType: String, data: Data) async throws -> JSONValue {
        let boundary = "CampusMate-\(UUID().uuidString)"
        let cleanFilename = filename.replacingOccurrences(of: "\"", with: "_").replacingOccurrences(of: "\r", with: "").replacingOccurrences(of: "\n", with: "")
        var body = Data("--\(boundary)\r\nContent-Disposition: form-data; name=\"\(fieldName)\"; filename=\"\(cleanFilename)\"\r\nContent-Type: \(mimeType)\r\n\r\n".utf8)
        body.append(data); body.append(Data("\r\n--\(boundary)--\r\n".utf8))
        let response = try await requestData(.post, path: path, data: body, contentType: "multipart/form-data; boundary=\(boundary)")
        return try JSONValue(data: response.data)
    }

    /// Large resources go directly to a temporary file instead of being held in memory.
    public func download(path: String) async throws -> DownloadedResource {
        let epoch = generation
        guard currentSession != nil else { throw APIError(statusCode: 401, code: "UNAUTHORIZED", message: "请先登录。") }
        for attempt in 0...1 {
            let token = currentSession?.tokens.accessToken
            let request = try makeRequest(.get, path: path, token: token)
            let (file, response) = try await HTTPRuntime.session.download(for: request)
            do {
                try validate(epoch)
                guard let http = response as? HTTPURLResponse else { throw APIError(code: "INVALID_RESPONSE", message: "下载响应无效。") }
                let headers = http.allHeaderFields.reduce(into: [String: String]()) { $0[String(describing: $1.key)] = String(describing: $1.value) }
                if !(200..<300).contains(http.statusCode) {
                    let data = (try? Data(contentsOf: file)) ?? Data()
                    let result = HTTPResponse(data: data, statusCode: http.statusCode, headers: headers)
                    if attempt == 0 && authenticationFailed(result), let token {
                        try? FileManager.default.removeItem(at: file)
                        try await refresh(expectedGeneration: epoch, failedToken: token)
                        continue
                    }
                    throw APIError(response: result)
                }
                let filename = URL(fileURLWithPath: response.suggestedFilename ?? "资源").lastPathComponent
                return DownloadedResource(url: file, filename: filename, mimeType: response.mimeType)
            } catch {
                try? FileManager.default.removeItem(at: file)
                throw error
            }
        }
        throw APIError(code: "DOWNLOAD_FAILED", message: "下载失败，请重试。")
    }

    private func send(_ method: HTTPMethod, path: String, query: [String: String], data: Data?, authenticated: Bool,
                      contentType: String?, headers: [String: String]) async throws -> HTTPResponse {
        let epoch = generation
        if authenticated && currentSession == nil { throw APIError(statusCode: 401, code: "UNAUTHORIZED", message: "请先登录。") }
        let token = authenticated ? currentSession?.tokens.accessToken : nil
        var request = try makeRequest(method, path: path, query: query, token: token, data: data, contentType: contentType, headers: headers)
        var response = try await transport(request)
        try validate(epoch)
        if authenticated && authenticationFailed(response), let token {
            try await refresh(expectedGeneration: epoch, failedToken: token)
            try validate(epoch)
            request.setValue(currentSession.map { "Bearer \($0.tokens.accessToken)" }, forHTTPHeaderField: "Authorization")
            response = try await transport(request)
            try validate(epoch)
        }
        try check(response)
        return response
    }

    private func refresh(expectedGeneration epoch: UInt64, failedToken: String) async throws {
        try validate(epoch)
        guard let session = currentSession else { throw APIError(statusCode: 401, code: "UNAUTHORIZED", message: "登录已失效，请重新登录。") }
        if session.tokens.accessToken != failedToken { return }
        let task: Task<TokenPair, any Error>
        if let existing = refreshTask { task = existing }
        else {
            let request = try makeRequest(.post, path: "auth/refresh", body: ["refresh_token": .string(session.tokens.refreshToken)])
            let transport = self.transport
            task = Task {
                let response = try await transport(request)
                guard (200..<300).contains(response.statusCode) else { throw APIError(response: response) }
                return try TokenPair(json: JSONValue(data: response.data))
            }
            refreshTask = task
        }
        do {
            let tokens = try await task.value
            try validate(epoch)
            // Another waiter may already have published the same rotation.
            if currentSession?.tokens.accessToken == failedToken {
                currentSession?.tokens = tokens; sessionObserver?(currentSession)
            }
            refreshTask = nil
        } catch {
            if generation == epoch {
                refreshTask = nil
                if let error = error as? APIError, error.statusCode == 401 || error.statusCode == 403 { restore(nil) }
            }
            throw error
        }
    }

    private func validate(_ epoch: UInt64) throws {
        try Task.checkCancellation()
        if generation != epoch { throw CancellationError() }
    }

    private func check(_ response: HTTPResponse) throws {
        if !(200..<300).contains(response.statusCode) { throw APIError(response: response) }
    }

    private func authenticationFailed(_ response: HTTPResponse) -> Bool {
        guard response.statusCode == 401 else { return false }
        return ["UNAUTHORIZED", "TOKEN_EXPIRED", "INVALID_TOKEN"].contains(APIError(response: response).code)
            || response.header("WWW-Authenticate")?.lowercased().contains("bearer") == true
    }

    private func makeRequest(_ method: HTTPMethod, path: String, query: [String: String] = [:], body: JSONValue? = nil,
                             token: String? = nil, data: Data? = nil, contentType: String? = nil, headers: [String: String] = [:]) throws -> URLRequest {
        guard !path.hasPrefix("/"), !path.contains("://"), !path.contains("?"), !path.contains("#"), !path.contains("\\"),
              !path.removingPercentEncoding.orEmpty.split(separator: "/").contains(".."),
              let url = URL(string: path, relativeTo: baseURL)?.absoluteURL,
              url.scheme == baseURL.scheme, url.host == baseURL.host, url.port == baseURL.port,
              var components = URLComponents(url: url, resolvingAgainstBaseURL: true) else {
            throw APIError(code: "INVALID_PATH", message: "请求地址无效。")
        }
        if !query.isEmpty { components.queryItems = query.sorted { $0.key < $1.key }.map { URLQueryItem(name: $0.key, value: $0.value) } }
        guard let finalURL = components.url else { throw APIError(code: "INVALID_PATH", message: "请求地址无效。") }
        var request = URLRequest(url: finalURL)
        request.httpMethod = method.rawValue
        request.httpBody = try data ?? body?.encoded()
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        if request.httpBody != nil { request.setValue(contentType ?? "application/json", forHTTPHeaderField: "Content-Type") }
        for (key, value) in headers where key.caseInsensitiveCompare("Authorization") != .orderedSame { request.setValue(value, forHTTPHeaderField: key) }
        if let token { request.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization") }
        return request
    }
}

private extension Optional where Wrapped == String { var orEmpty: String { self ?? "" } }
