import Foundation

/// Elapsed time derives from persisted timestamps, not a timer running in the background.
public struct FocusClock: Codable, Sendable, Equatable {
    public private(set) var startedAt: Date?
    public private(set) var accumulated: TimeInterval
    public var isRunning: Bool { startedAt != nil }

    public init(startedAt: Date? = nil, accumulated: TimeInterval = 0) {
        self.startedAt = startedAt; self.accumulated = max(0, accumulated)
    }
    public func elapsed(at now: Date) -> TimeInterval { accumulated + max(0, startedAt.map { now.timeIntervalSince($0) } ?? 0) }
    public mutating func pause(at now: Date) { accumulated = elapsed(at: now); startedAt = nil }
    public mutating func resume(at now: Date) { if startedAt == nil { startedAt = now } }
}
