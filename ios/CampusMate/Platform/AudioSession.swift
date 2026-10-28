import AVFoundation
import CampusCore

@MainActor
final class CampusAudioSession {
    static let shared = CampusAudioSession()
    private var owner: UUID?
    private var displaced: (() -> Void)?

    func acquire(owner: UUID, recording: Bool, onDisplaced: @escaping () -> Void) throws {
        if self.owner != owner { displaced?() }
        let session = AVAudioSession.sharedInstance()
        try session.setCategory(recording ? .playAndRecord : .playback, mode: recording ? .voiceChat : .spokenAudio,
                                options: recording ? [.defaultToSpeaker, .allowBluetoothHFP] : [])
        try session.setActive(true)
        self.owner = owner; displaced = onDisplaced
    }
    func release(owner: UUID) {
        guard self.owner == owner else { return }
        self.owner = nil; displaced = nil
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
    }
}

@MainActor
final class PCMPlayer {
    let engine: AVAudioEngine
    private let player = AVAudioPlayerNode()
    private var format: AVAudioFormat
    private var framer = PCM16Framer()
    private var bufferedFrames = 0
    private var generation = UUID()
    var onDrained: (() -> Void)?

    init(engine: AVAudioEngine = AVAudioEngine(), sampleRate: Double = 24000) {
        self.engine = engine
        format = AVAudioFormat(standardFormatWithSampleRate: sampleRate, channels: 1)!
        engine.attach(player); engine.connect(player, to: engine.mainMixerNode, format: format)
    }
    var isEmpty: Bool { bufferedFrames == 0 }
    func enqueue(_ data: Data) throws {
        let samples = try framer.append(data)
        guard !samples.isEmpty else { return }
        guard bufferedFrames + samples.count <= Int(format.sampleRate * 20) else {
            throw APIError(code: "AUDIO_BACKPRESSURE", message: "语音接收过快，已停止以避免长时间延迟。")
        }
        guard let buffer = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: AVAudioFrameCount(samples.count)), let channel = buffer.floatChannelData?[0] else { throw APIError(code: "AUDIO_BUFFER", message: "无法创建音频缓冲。") }
        buffer.frameLength = AVAudioFrameCount(samples.count)
        samples.withUnsafeBufferPointer { channel.update(from: $0.baseAddress!, count: samples.count) }
        if !engine.isRunning { try engine.start() }
        if !player.isPlaying { player.play() }
        bufferedFrames += samples.count
        let run = generation; let count = samples.count
        player.scheduleBuffer(buffer, completionCallbackType: .dataPlayedBack) { [weak self] _ in
            Task { @MainActor [weak self] in
                guard let self, self.generation == run else { return }
                self.bufferedFrames = max(0, self.bufferedFrames - count)
                if self.bufferedFrames == 0 { self.onDrained?() }
            }
        }
    }
    func clear() { generation = UUID(); player.stop(); bufferedFrames = 0; framer.reset() }
    func stop() { clear(); engine.stop() }
}

/// Confined to the serial audio input tap. No buffers escape the callback.
final class MicrophonePCMConverter: @unchecked Sendable {
    private let converter: AVAudioConverter
    private let target: AVAudioFormat
    init(source: AVAudioFormat) throws {
        target = AVAudioFormat(commonFormat: .pcmFormatInt16, sampleRate: 16000, channels: 1, interleaved: true)!
        guard source.sampleRate > 0, source.channelCount > 0, let converter = AVAudioConverter(from: source, to: target) else {
            throw APIError(code: "AUDIO_INPUT", message: "当前设备没有可用的麦克风输入。")
        }
        self.converter = converter; converter.downmix = true
    }
    func convert(_ input: AVAudioPCMBuffer) throws -> Data {
        let capacity = AVAudioFrameCount(ceil(Double(input.frameLength) * 16000 / input.format.sampleRate)) + 64
        guard let output = AVAudioPCMBuffer(pcmFormat: target, frameCapacity: capacity) else { throw APIError(code: "AUDIO_CONVERT", message: "无法转换录音格式。") }
        var supplied = false
        var error: NSError?
        let status = converter.convert(to: output, error: &error) { _, flag in
            if supplied { flag.pointee = .noDataNow; return nil }
            supplied = true; flag.pointee = .haveData; return input
        }
        if let error { throw error }
        guard status != .error, let samples = output.int16ChannelData?[0] else { throw APIError(code: "AUDIO_CONVERT", message: "录音格式转换失败。") }
        return Data(bytes: samples, count: Int(output.frameLength) * 2)
    }
}
