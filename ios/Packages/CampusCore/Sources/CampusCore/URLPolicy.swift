import Foundation
import Darwin

public enum URLPolicy {
    public static func origin(_ address: String) -> String? {
        guard let parts = URLComponents(string: address), let scheme = parts.scheme?.lowercased(),
              ["http", "https"].contains(scheme), let host = parts.host?.lowercased(), !host.isEmpty,
              parts.user == nil, parts.password == nil else { return nil }
        let port = parts.port ?? (scheme == "https" ? 443 : 80)
        return "\(scheme)://\(host):\(port)"
    }

    public static func isTrusted(_ address: String, origins: [String], allowLocalDebug: Bool = false, requiresPublicOrigin: Bool = true) -> Bool {
        guard let parts = URLComponents(string: address), let url = parts.url,
              let candidate = origin(address), origins.compactMap(origin).contains(candidate),
              url.user == nil, url.password == nil,
              !parts.percentEncodedPath.removingPercentEncoding.orEmpty.split(separator: "/").contains("..") else { return false }
        let host = (parts.host ?? "").lowercased().trimmingCharacters(in: CharacterSet(charactersIn: "[]"))
        let loopback = ["localhost", "127.0.0.1", "::1"].contains(host)
        if parts.scheme?.lowercased() == "http" { return allowLocalDebug && loopback }
        guard parts.scheme?.lowercased() == "https" else { return false }
        return !requiresPublicOrigin || !isPrivateHost(host)
    }

    public static func isPrivateHost(_ host: String) -> Bool {
        let value = host.lowercased().trimmingCharacters(in: CharacterSet(charactersIn: "[]"))
        if value == "localhost" || value.hasSuffix(".localhost") || value.hasSuffix(".local") { return true }
        var ipv6 = in6_addr()
        if inet_pton(AF_INET6, value, &ipv6) == 1 {
            let bytes = withUnsafeBytes(of: &ipv6) { Array($0) }
            let unspecifiedOrLoopback = bytes.prefix(15).allSatisfy { $0 == 0 } && bytes[15] <= 1
            let mappedIPv4 = bytes.prefix(10).allSatisfy { $0 == 0 } && bytes[10] == 0xff && bytes[11] == 0xff
            return unspecifiedOrLoopback || mappedIPv4 || bytes[0] & 0xfe == 0xfc
                || (bytes[0] == 0xfe && bytes[1] & 0xc0 == 0x80) || bytes[0] == 0xff
        }
        var ipv4 = in_addr()
        if inet_aton(value, &ipv4) == 1 {
            let octets = withUnsafeBytes(of: &ipv4) { Array($0) }
            return octets[0] == 0 || octets[0] == 10 || octets[0] == 127 || octets[0] >= 224
                || (octets[0] == 169 && octets[1] == 254) || (octets[0] == 192 && octets[1] == 168)
                || (octets[0] == 172 && (16...31).contains(Int(octets[1])))
        }
        return false
    }
}

public struct QRLoginPayload: Sendable, Equatable {
    public let sessionID: String
    public let scanToken: String
    public var body: JSONValue { ["session_id": .string(sessionID), "scan_token": .string(scanToken)] }

    public init(_ value: String) throws {
        guard let parts = URLComponents(string: value.trimmingCharacters(in: .whitespacesAndNewlines)),
              parts.scheme == "campusmate", parts.host == "auth", parts.path == "/web-login",
              parts.user == nil, parts.password == nil, parts.port == nil, parts.fragment == nil,
              let query = parts.queryItems, query.count == 3,
              Set(query.map(\.name)) == Set(["v", "sid", "token"]),
              query.first(where: { $0.name == "v" })?.value == "1",
              let sid = query.first(where: { $0.name == "sid" })?.value, (16...64).contains(sid.count),
              let token = query.first(where: { $0.name == "token" })?.value, (32...128).contains(token.count) else {
            throw APIError(code: "INVALID_QR", message: "这不是有效的 CampusMate 网页登录二维码。")
        }
        sessionID = sid; scanToken = token
    }
}

private extension Optional where Wrapped == String { var orEmpty: String { self ?? "" } }
