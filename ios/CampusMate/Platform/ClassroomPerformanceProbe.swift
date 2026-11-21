import Foundation
import Darwin

/// 可导出的客户端性能样本。只记录时间与内存，不包含课件正文、账号或题目内容。
struct ClassroomPerformanceSnapshot: Codable, Sendable, Equatable {
    var stageKey: String = ""
    var lastOpenAt: Date?
    var usedCache: Bool = false
    var firstReadableMs: Int?
    var coldOpenMs: Int?
    var warmOpenMs: Int?
    var playbackRequestMs: Int?
    var lastPageTurnMs: Int?
    var averagePageTurnMs: Int?
    var pageTurns: Int = 0
    var peakMemoryMB: Double = 0
    var visits: Int = 0
    var quizSubmits: Int = 0
    var networkFailures: Int = 0

    static func new() -> ClassroomPerformanceSnapshot { ClassroomPerformanceSnapshot() }
}

/// 对照 WKWebView 与原生播放的同一套口径：
/// - 首屏可读：从点开到第一页文字可读；冷开（无本地快照）与热开（有快照）分开记；
/// - 翻页：从点到下一页可读；
/// - 峰值内存：`phys_footprint` 的采样最大值；
/// - 服务端生成耗时不在客户端统计，单列生成任务的时间。
@MainActor
final class ClassroomPerformanceProbe {
    static let shared = ClassroomPerformanceProbe()

    private var store: [String: ClassroomPerformanceSnapshot] = [:]
    private var activeStart: Date?
    private var activeKey: String?
    private var loaded = false

    private var fileURL: URL? {
        guard let root = FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first else { return nil }
        let directory = root.appendingPathComponent("CampusMate", isDirectory: true)
        try? FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
        return directory.appendingPathComponent("ClassroomPerformance.json")
    }

    func begin(stageKey: String) {
        loadIfNeeded()
        activeStart = Date()
        activeKey = stageKey
        var sample = store[stageKey] ?? .new()
        sample.stageKey = stageKey
        sample.lastOpenAt = Date()
        sample.usedCache = false
        sample.firstReadableMs = nil
        sample.playbackRequestMs = nil
        store[stageKey] = sample
    }

    func markCachedReadable(stageKey: String, memory: Double) {
        guard activeStart != nil else { return }
        markReadable(stageKey: stageKey, usedCache: true, memory: memory)
    }

    func markNetworkReadable(stageKey: String, playbackMs: Int?, memory: Double) {
        markReadable(stageKey: stageKey, usedCache: false, memory: memory)
        var sample = store[stageKey] ?? .new()
        sample.playbackRequestMs = playbackMs
        store[stageKey] = sample
        persist()
    }

    func markNetworkFailed(stageKey: String) {
        var sample = store[stageKey] ?? .new()
        sample.networkFailures += 1
        store[stageKey] = sample
        persist()
    }

    func recordPageTurn(stageKey: String, milliseconds: Int, memory: Double) {
        var sample = store[stageKey] ?? .new()
        sample.stageKey = stageKey
        sample.lastPageTurnMs = milliseconds
        sample.pageTurns += 1
        let previous = sample.averagePageTurnMs ?? 0
        sample.averagePageTurnMs = Int((Double(previous) * Double(sample.pageTurns - 1) + Double(milliseconds)) / Double(sample.pageTurns))
        sample.peakMemoryMB = max(sample.peakMemoryMB, memory)
        store[stageKey] = sample
        if sample.pageTurns % 5 == 0 { persist() } else { schedulePersist() }
    }

    func recordVisit(stageKey: String) {
        var sample = store[stageKey] ?? .new()
        sample.visits += 1
        store[stageKey] = sample
    }

    func recordQuizSubmit(stageKey: String) {
        var sample = store[stageKey] ?? .new()
        sample.quizSubmits += 1
        store[stageKey] = sample
        persist()
    }

    func report(stageKey: String, title: String) -> String {
        loadIfNeeded()
        guard let sample = store[stageKey] else { return "还没有这节课堂的性能样本。" }
        let lines = [
            "课堂：\(title)",
            "样本时间：\(sample.lastOpenAt.map { ISO8601DateFormatter().string(from: $0) } ?? "无")",
            "本次首屏（\(sample.usedCache ? "热开-本地快照" : "冷开-网络")）：\(sample.firstReadableMs.map { "\($0) ms" } ?? "未记录")",
            "冷开首屏：\(sample.coldOpenMs.map { "\($0) ms" } ?? "未记录")",
            "热开首屏：\(sample.warmOpenMs.map { "\($0) ms" } ?? "未记录")",
            "播放计划请求：\(sample.playbackRequestMs.map { "\($0) ms" } ?? "未记录")",
            "最近翻页：\(sample.lastPageTurnMs.map { "\($0) ms" } ?? "未记录")",
            "平均翻页：\(sample.averagePageTurnMs.map { "\($0) ms" } ?? "未记录")（\(sample.pageTurns) 次）",
            "峰值内存：\(String(format: "%.1f", sample.peakMemoryMB)) MB",
            "已访问新页：\(sample.visits) 次，测验提交：\(sample.quizSubmits) 次，刷新失败：\(sample.networkFailures) 次",
            "说明：服务端生成耗时请用生成任务的时间单独对照，不混入首屏口径。",
        ]
        return lines.joined(separator: "\n")
    }

    static func residentMemoryMB() -> Double {
        var info = task_vm_info_data_t()
        var count = mach_msg_type_number_t(MemoryLayout<task_vm_info_data_t>.size / MemoryLayout<integer_t>.size)
        let result = withUnsafeMutablePointer(to: &info) { pointer in
            pointer.withMemoryRebound(to: integer_t.self, capacity: Int(count)) {
                task_info(mach_task_self_, task_flavor_t(TASK_VM_INFO), $0, &count)
            }
        }
        guard result == KERN_SUCCESS else { return 0 }
        return Double(info.phys_footprint) / 1_048_576
    }

    private func markReadable(stageKey: String, usedCache: Bool, memory: Double) {
        guard let start = activeStart, activeKey == stageKey else { return }
        let elapsed = Int(Date().timeIntervalSince(start) * 1000)
        var sample = store[stageKey] ?? .new()
        sample.stageKey = stageKey
        sample.lastOpenAt = Date()
        sample.usedCache = usedCache
        sample.firstReadableMs = elapsed
        if usedCache { sample.warmOpenMs = elapsed } else { sample.coldOpenMs = elapsed }
        sample.peakMemoryMB = max(sample.peakMemoryMB, memory)
        store[stageKey] = sample
        activeStart = nil
        persist()
    }

    private func loadIfNeeded() {
        guard !loaded else { return }
        loaded = true
        guard let fileURL, let data = try? Data(contentsOf: fileURL) else { return }
        store = (try? JSONDecoder().decode([String: ClassroomPerformanceSnapshot].self, from: data)) ?? [:]
    }

    private var persistTask: Task<Void, Never>?

    private func schedulePersist() {
        persistTask?.cancel()
        persistTask = Task { [weak self] in
            try? await Task.sleep(for: .milliseconds(800))
            guard !Task.isCancelled else { return }
            self?.persist()
        }
    }

    private func persist() {
        loadIfNeeded()
        guard let fileURL else { return }
        let values = store.count > 200 ? store.reduce(into: [String: ClassroomPerformanceSnapshot]()) { result, entry in
            if result.count < 200 { result[entry.key] = entry.value }
        } : store
        guard let data = try? JSONEncoder().encode(values) else { return }
        try? data.write(to: fileURL, options: [.atomic])
    }
}
