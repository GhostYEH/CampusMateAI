import Foundation

/// 画布视频缓存：总量上限 + 过期清理 + 正在播放保护。
/// 复制与扫描在后台串行队列执行，临时文件写完后原子发布。
final class ClassroomVideoCache: @unchecked Sendable {
    static let shared = ClassroomVideoCache()
    static let extensions = ["mp4", "m4v", "mov", "webm"]
    private static let ioQueue = DispatchQueue(
        label: "com.campusmate.classroom-video-cache", qos: .utility)
    private static let maxBytes: Int64 = 256 * 1024 * 1024
    private static let maxAge: TimeInterval = 60 * 60 * 24 * 7

    private let root: URL?
    private let lock = NSLock()
    private var protectedPaths: Set<String> = []

    private init() {
        let base = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first?
            .appendingPathComponent("CampusMate", isDirectory: true)
            .appendingPathComponent("ClassroomVideo", isDirectory: true)
        if let base { try? FileManager.default.createDirectory(at: base, withIntermediateDirectories: true) }
        root = base
        let cache = self
        Self.ioQueue.async { cache.prune() }
    }

    func url(cacheID: String) -> URL? {
        guard let root else { return nil }
        for ext in Self.extensions {
            let file = root.appendingPathComponent("\(cacheID).\(ext)")
            if let size = (try? file.resourceValues(forKeys: [.fileSizeKey]))?.fileSize, size > 0 {
                return file
            }
        }
        return nil
    }

    func store(_ source: URL, cacheID: String, fileExtension: String) async throws -> URL {
        guard let root else { throw ClassroomNativeError.invalidResponse("无法创建视频缓存目录。") }
        let ext = Self.extensions.contains(fileExtension.lowercased()) ? fileExtension.lowercased() : "mp4"
        let destination = root.appendingPathComponent("\(cacheID).\(ext)")
        return try await withCheckedThrowingContinuation { continuation in
            Self.ioQueue.async {
                do {
                    if let size = (try? destination.resourceValues(forKeys: [.fileSizeKey]))?.fileSize, size > 0 {
                        continuation.resume(returning: destination)
                        return
                    }
                    let temp = root.appendingPathComponent("\(cacheID).\(ext).\(UUID().uuidString).tmp")
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

    func markPlaying(_ url: URL) {
        lock.lock()
        protectedPaths.insert(url.path)
        lock.unlock()
    }

    func clearPlaying() {
        lock.lock()
        protectedPaths.removeAll()
        lock.unlock()
    }

    func prune() {
        let cache = self
        Self.ioQueue.async {
            guard let root = cache.root,
                  let files = try? FileManager.default.contentsOfDirectory(
                    at: root, includingPropertiesForKeys: [.contentModificationDateKey, .fileSizeKey]) else { return }
            let cutoff = Date().addingTimeInterval(-Self.maxAge)
            cache.lock.lock()
            let protected = cache.protectedPaths
            cache.lock.unlock()

            var retained: [(url: URL, date: Date, size: Int64)] = []
            var total: Int64 = 0
            for file in files {
                if file.pathExtension == "tmp" {
                    try? FileManager.default.removeItem(at: file)
                    continue
                }
                let values = try? file.resourceValues(forKeys: [.contentModificationDateKey, .fileSizeKey])
                let date = values?.contentModificationDate ?? Date()
                let size = Int64(values?.fileSize ?? 0)
                if protected.contains(file.path) || date >= cutoff {
                    retained.append((file, date, size))
                    total += size
                } else {
                    try? FileManager.default.removeItem(at: file)
                }
            }
            guard total > Self.maxBytes else { return }
            for entry in retained.sorted(by: { $0.date < $1.date }) {
                if total <= Self.maxBytes { break }
                if protected.contains(entry.url.path) { continue }
                try? FileManager.default.removeItem(at: entry.url)
                total -= entry.size
            }
        }
    }
}
