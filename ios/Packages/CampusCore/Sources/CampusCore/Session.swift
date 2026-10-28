import Foundation

public struct ServerConfiguration: Sendable, Equatable {
    public let baseURL: URL

    public init(_ address: String, allowsInsecureHTTP: Bool = false) throws {
        guard var components = URLComponents(string: address.trimmingCharacters(in: .whitespacesAndNewlines)),
              let scheme = components.scheme?.lowercased(),
              scheme == "https" || (scheme == "http" && allowsInsecureHTTP),
              components.host?.isEmpty == false,
              components.user == nil, components.password == nil,
              components.query == nil, components.fragment == nil else {
            throw APIError(code: "INVALID_SERVER", message: "请输入有效的服务器地址；正式连接需使用 HTTPS。")
        }
        let trimmed = components.path.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        guard trimmed.isEmpty || trimmed == "api/v1" else {
            throw APIError(code: "INVALID_SERVER", message: "服务器路径应为 /api/v1。")
        }
        components.path = "/api/v1/"
        guard let url = components.url else { throw APIError(code: "INVALID_SERVER", message: "服务器地址无效。") }
        baseURL = url
    }
}

public struct TokenPair: Codable, Sendable, Equatable {
    public let accessToken: String
    public let refreshToken: String

    public init(accessToken: String, refreshToken: String) {
        self.accessToken = accessToken
        self.refreshToken = refreshToken
    }

    public init(json: JSONValue) throws {
        guard let access = json["access_token"].string?.nonEmpty,
              let refresh = json["refresh_token"].string?.nonEmpty else {
            throw APIError(code: "INVALID_RESPONSE", message: "服务器没有返回完整的登录凭据。")
        }
        self.init(accessToken: access, refreshToken: refresh)
    }
}

public struct UserProfile: Codable, Sendable, Equatable, Identifiable {
    public let id: String
    public var username: String
    public var displayName: String
    public var universityID: String
    public var universityName: String
    public var college: String
    public var major: String
    public var grade: String
    public var studentNumber: String
    public var avatarURL: String
    public var uid: String

    public init(id: String, username: String, displayName: String = "", universityID: String = "", universityName: String = "", college: String = "", major: String = "", grade: String = "", studentNumber: String = "", avatarURL: String = "", uid: String = "") {
        self.id = id; self.username = username; self.displayName = displayName.nonEmpty ?? username
        self.universityID = universityID; self.universityName = universityName
        self.college = college; self.major = major; self.grade = grade
        self.studentNumber = studentNumber; self.avatarURL = avatarURL; self.uid = uid.nonEmpty ?? id
    }

    public init(json: JSONValue) throws {
        guard let id = json["id"].string?.nonEmpty else { throw APIError(code: "INVALID_RESPONSE", message: "账号信息缺少用户标识。") }
        self.init(id: id, username: json["username"].text, displayName: json["display_name"].string ?? json["name"].text,
                  universityID: json["university_id"].text, universityName: json["university_name"].text,
                  college: json["college"].text, major: json["major"].text, grade: json["grade"].text,
                  studentNumber: json["student_number"].text, avatarURL: json["avatar_url"].text, uid: json["uid"].text)
    }
}

public struct Session: Codable, Sendable, Equatable {
    public var tokens: TokenPair
    public var user: UserProfile
    public init(tokens: TokenPair, user: UserProfile) { self.tokens = tokens; self.user = user }
}
