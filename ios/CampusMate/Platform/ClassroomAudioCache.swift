import CryptoKit
import Foundation

/// 讲解/课堂音频按「账号 + 资源键」落盘。
///
/// 目录扫描与文件复制在后台串行队列执行，复制先写同目录临时文件再原子替换；
/// 正在播放的资源会被 protect，不会被过期清理删除。
final class ClassroomAudioCache: @unchecked Sendable {
    static let shared = ClassroomAudioCache()
    private static let extensions = ["wav", "mp3", "m4a", "aac", "ogg", "flac"]
    private static let ioQueue = DispatchQueue(
        label: "com.campusmate.classroom-audio-cache", qos: .utility)

    private let root: URL?
    private let lock = NSLock()
    private var protectedKeys: Set<String> = []

    private init() {
        let base = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first?
            .appendingPathComponent("CampusMate", isDirectory: true)
            .appendingPathComponent("ClassroomAudio", isDirectory: true)
        if let base { try? FileManager.default.createDirectory(at: base, withIntermediateDirectories: true) }
        root = base
        // 初始化不再同步扫描主线程。
        let cache = self
        Self.ioQueue.async { cache.prune() }
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

    func store(_ source: URL, accountKey: String, resourceID: String, fileExtension: String = "wav") async throws -> URL {
        guard let directory = directoryURL(accountKey: accountKey),
              let safeID = safeResourceID(resourceID) else {
            throw ClassroomNativeError.invalidResponse("无法创建讲解缓存目录。")
        }
        let ext = Self.extensions.contains(fileExtension.lowercased()) ? fileExtension.lowercased() : "wav"
        let destination = directory.appendingPathComponent("\(safeID).\(ext)")
        return try await withCheckedThrowingContinuation { continuation in
            Self.ioQueue.async {
                do {
                    try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
                    if let size = (try? destination.resourceValues(forKeys: [.fileSizeKey]))?.fileSize, size > 0 {
                        continuation.resume(returning: destination)
                        return
                    }
                    let temp = directory.appendingPathComponent(
                        "\(safeID).\(ext).\(UUID().uuidString).tmp")
                    try? FileManager.default.removeItem(at: temp)
                    try FileManager.default.copyItem(at: source, to: temp)
                    if FileManager.default.fileExists(atPath: destination.path) {
                        _ = try FileManager.default.replaceItemAt(destination, withItemAt: temp)
                    } else {
                        try FileManager.default.moveItem(at: temp, to: destination)
                    }
                    continuation.resume(returning: destination)
                } catch {
                    continuation.resume(throwing: error)
                }
            }
        }
    }

    // 兼容旧讲解产物的调用；资源键仍然是 artifact id。
    func url(accountKey: String, artifactID: String) -> URL? {
        url(accountKey: accountKey, resourceID: artifactID)
    }

    func store(_ source: URL, accountKey: String, artifactID: String) async throws -> URL {
        try await store(source, accountKey: accountKey, resourceID: artifactID, fileExtension: "wav")
    }

    /// 正在播放的文件不参与清理；离开课堂时统一释放。
    func markPlaying(accountKey: String, resourceID: String) {
        guard let safeID = safeResourceID(resourceID) else { return }
        lock.lock()
        protectedKeys.insert(safeID)
        lock.unlock()
    }

    func clearPlaying() {
        lock.lock()
        protectedKeys.removeAll()
        lock.unlock()
    }

    /// 只清理过期文件，按修改时间判断；受保护资源与最近写入的文件保留。
    func prune(olderThan: TimeInterval = 60 * 60 * 24 * 7) {
        let cache = self
        Self.ioQueue.async {
            guard let root = cache.root,
                  let enumerator = FileManager.default.enumerator(
                    at: root, includingPropertiesForKeys: [.contentModificationDateKey]) else { return }
            let cutoff = Date().addingTimeInterval(-olderThan)
            cache.lock.lock()
            let protected = cache.protectedKeys
            cache.lock.unlock()
            for case let url as URL in enumerator {
                if url.pathExtension == "tmp" {
                    try? FileManager.default.removeItem(at: url)
                    continue
                }
                if protected.contains(where: { url.lastPathComponent.hasPrefix("\($0).") }) { continue }
                let modified = (try? url.resourceValues(forKeys: [.contentModificationDateKey]).contentModificationDate)
                    ?? Date()
                if modified < cutoff { try? FileManager.default.removeItem(at: url) }
            }
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
