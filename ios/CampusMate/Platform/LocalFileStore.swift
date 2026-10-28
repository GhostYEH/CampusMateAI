import Foundation
import CryptoKit
import CampusCore

/// Personal-hub APIs sync file metadata; original documents remain account-scoped on this device.
enum LocalFileStore {
    static func directory(scope: String) throws -> URL {
        let digest = SHA256.hash(data: Data(scope.utf8)).map { String(format: "%02x", $0) }.joined()
        guard let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask).first else { throw CocoaError(.fileNoSuchFile) }
        let directory = documents.appendingPathComponent("CampusMateFiles", isDirectory: true).appendingPathComponent(digest, isDirectory: true)
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        return directory
    }

    static func importFile(_ source: URL, scope: String) throws -> URL {
        let granted = source.startAccessingSecurityScopedResource()
        defer { if granted { source.stopAccessingSecurityScopedResource() } }
        let folder = try directory(scope: scope).appendingPathComponent(UUID().uuidString, isDirectory: true)
        try FileManager.default.createDirectory(at: folder, withIntermediateDirectories: true)
        let destination = folder.appendingPathComponent(source.lastPathComponent)
        try FileManager.default.copyItem(at: source, to: destination)
        return destination
    }

    static func register(_ file: URL, id: String, scope: String) throws {
        let root = try directory(scope: scope)
        guard file.standardizedFileURL.path.hasPrefix(root.standardizedFileURL.path + "/") else { throw CocoaError(.fileReadNoPermission) }
        var index = readIndex(root)
        index[id] = String(file.path.dropFirst(root.path.count + 1))
        try JSONEncoder().encode(index).write(to: root.appendingPathComponent("index.json"), options: .atomic)
    }

    static func file(id: String, scope: String) -> URL? {
        guard let root = try? directory(scope: scope), let relative = readIndex(root)[id] else { return nil }
        let file = root.appendingPathComponent(relative).standardizedFileURL
        guard file.path.hasPrefix(root.standardizedFileURL.path + "/"), FileManager.default.fileExists(atPath: file.path) else { return nil }
        return file
    }

    static func remove(id: String, scope: String) throws {
        let root = try directory(scope: scope)
        if let file = file(id: id, scope: scope) { try FileManager.default.removeItem(at: file) }
        var index = readIndex(root); index.removeValue(forKey: id)
        try JSONEncoder().encode(index).write(to: root.appendingPathComponent("index.json"), options: .atomic)
    }
    private static func readIndex(_ root: URL) -> [String: String] {
        guard let data = try? Data(contentsOf: root.appendingPathComponent("index.json")) else { return [:] }
        return (try? JSONDecoder().decode([String: String].self, from: data)) ?? [:]
    }
}
