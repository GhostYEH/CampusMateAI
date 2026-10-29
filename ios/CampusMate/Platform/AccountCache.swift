import Foundation
import CryptoKit

actor AccountCache {
    static let shared = AccountCache()
    private var revisions: [String: UInt64] = [:]

    func load<Value: Decodable & Sendable>(_ type: Value.Type, scope: String, key: String) -> Value? {
        guard let url = try? location(scope: scope, key: key), let data = try? Data(contentsOf: url) else { return nil }
        return try? JSONDecoder().decode(type, from: data)
    }

    func save<Value: Encodable & Sendable>(_ value: Value, scope: String, key: String, revision: UInt64 = DispatchTime.now().uptimeNanoseconds) throws {
        let identity = scope + "|" + key
        guard revision >= revisions[identity, default: 0] else { return }
        let data = try JSONEncoder().encode(value)
        try data.write(to: location(scope: scope, key: key), options: [.atomic, .completeFileProtectionUntilFirstUserAuthentication])
        revisions[identity] = revision
    }

    private func location(scope: String, key: String) throws -> URL {
        guard !key.contains("/"), !key.contains(".."), !key.isEmpty,
              let root = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first else { throw CocoaError(.fileWriteInvalidFileName) }
        let name = SHA256.hash(data: Data(scope.utf8)).map { String(format: "%02x", $0) }.joined()
        let directory = root.appendingPathComponent("CampusMate", isDirectory: true).appendingPathComponent(name, isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        return directory.appendingPathComponent(key)
    }
}
