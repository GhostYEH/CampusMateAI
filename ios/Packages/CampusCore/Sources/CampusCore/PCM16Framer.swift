import Foundation

/// Retains a split sample across network chunks; each websocket/audio stream owns one framer.
public struct PCM16Framer: Sendable {
    private var tail: UInt8?
    private var checkedHeader = false
    public var hasPartialSample: Bool { tail != nil }
    public init() { }
    public mutating func reset() { tail = nil; checkedHeader = false }
    public mutating func append(_ chunk: Data) throws -> [Float] {
        guard chunk.count <= 1_048_576 else { throw APIError(code: "AUDIO_OVERFLOW", message: "音频分块过大，已停止播放。") }
        guard !chunk.isEmpty else { return [] }
        if !checkedHeader {
            guard !chunk.starts(with: Data("OggS".utf8)), !chunk.starts(with: Data("RIFF".utf8)) else {
                throw APIError(code: "AUDIO_FORMAT", message: "服务端返回的音频与 PCM16LE 协议不符。")
            }
            checkedHeader = true
        }
        var bytes = [UInt8](); bytes.reserveCapacity(chunk.count + 1)
        if let tail { bytes.append(tail) }; bytes.append(contentsOf: chunk)
        tail = bytes.count.isMultiple(of: 2) ? nil : bytes.removeLast()
        return stride(from: 0, to: bytes.count, by: 2).map { Float(Int16(bitPattern: UInt16(bytes[$0]) | UInt16(bytes[$0 + 1]) << 8)) / 32768 }
    }
}
