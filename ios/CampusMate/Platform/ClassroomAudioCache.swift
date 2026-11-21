import Foundation
import CryptoKit

/// 讲解/课堂音频按「账号 + 资源键」落盘。换账号后旧文件仍然在，但不会被读出，
/// 因为目录由账号作用域哈希决定；资源键里带正文版本，过期音频不会被新课件复用。
@MainActor
final class ClassroomAudioCache {
    static let shared = ClassroomAudioCache()
    private static let extensions = ["wav", "mp3", "m4a", "aac", "ogg", "flac"]

    private let root: URL?

    private init() {
        let base = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first?
            .appendingPathComponent("CampusMate", isDirectory: true)
            .appendingPathComponent("ClassroomAudio", isDirectory: true)
        if let base { try? FileManager.default.createDirectory(at: base, withIntermediateDirectories: true) }
        root = base
        prune()
    }

    func url(accountKey: String, resourceID: String) -> URL? {
        guard let directory = directoryURL(accountKey: accountKey),
              let safeID = safeResourceID(resourceID) else { return nil }
        for ext in Self.extensions {
            let file = directory.appendingPathComponent("\(safeID).\(ext)")
            if let size = (try? file.resourceValues(forKeys: [.fileSizeKey]))?.fileSize, size > 0 {
                return file
            }
        }
        return nil
    }

    func store(_ source: URL, accountKey: String, resourceID: String, fileExtension: String = "wav") throws -> URL {
        guard let directory = directoryURL(accountKey: accountKey),
              let safeID = safeResourceID(resourceID) else {
            throw ClassroomNativeError.invalidResponse("无法创建讲解缓存目录。")
        }
        let ext = Self.extensions.contains(fileExtension.lowercased()) ? fileExtension.lowercased() : "wav"
        let destination = directory.appendingPathComponent("\(safeID).\(ext)")
        if FileManager.default.fileExists(atPath: destination.path) { return destination }
        try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        try? FileManager.default.removeItem(at: destination)
        try FileManager.default.copyItem(at: source, to: destination)
        return destination
    }

    // 兼容旧讲解产物的调用；资源键仍然是 artifact id。
    func url(accountKey: String, artifactID: String) -> URL? {
        url(accountKey: accountKey, resourceID: artifactID)
    }

    func store(_ source: URL, accountKey: String, artifactID: String) throws -> URL {
        try store(source, accountKey: accountKey, resourceID: artifactID, fileExtension: "wav")
    }

    /// 只清理过期文件，按修改时间判断，不影响正在使用的一节课堂。
    func prune(olderThan: TimeInterval = 60 * 60 * 24 * 7) {
        guard let root, let enumerator = FileManager.default.enumerator(at: root, includingPropertiesForKeys: [.contentModificationDateKey]) else { return }
        let cutoff = Date().addingTimeInterval(-olderThan)
        for case let url as URL in enumerator {
            let modified = (try? url.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate) ?? Date()
            if modified < cutoff { try? FileManager.default.removeItem(at: url) }
        }
    }

    private func directoryURL(accountKey: String) -> URL? {
        guard let root else { return nil }
        let digest = SHA256.hash(data: Data(accountKey.utf8)).map { String(format: "%02x", $0) }.joined()
        return root.appendingPathComponent(digest, isDirectory: true)
    }

    private func safeResourceID(_ resourceID: String) -> String? {
        let safeID = resourceID.filter { $0.isLetter || $0.isNumber || $0 == "-" || $0 == "_" }
        guard !safeID.isEmpty else { return nil }
        return String(safeID.prefix(128))
    }
}
