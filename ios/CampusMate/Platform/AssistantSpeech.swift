import AVFoundation
import UIKit
import Observation
import CampusCore

@MainActor @Observable
final class AssistantSpeech: NSObject, AVAudioRecorderDelegate {
    private(set) var isRecording = false
    private(set) var isWorking = false
    private(set) var isPlaying = false
    var error: String?
    @ObservationIgnored private var recorder: AVAudioRecorder?
    @ObservationIgnored private var recordingURL: URL?
    @ObservationIgnored private var client: APIClient?
    @ObservationIgnored private var onText: ((String) -> Void)?
    @ObservationIgnored private var player: PCMPlayer?
    @ObservationIgnored private var request: Task<Void, Never>?
    @ObservationIgnored private var generation = UUID()
    @ObservationIgnored private var owner: UUID?
    @ObservationIgnored private var observer: NSObjectProtocol?
    @ObservationIgnored private var backgroundObserver: NSObjectProtocol?

    func record(client: APIClient, onText: @escaping (String) -> Void) async {
        guard !isWorking, !isRecording else { return }
        stop(); error = nil
        let run = generation
        guard await AVAudioApplication.requestRecordPermission() else { error = "请在系统设置中允许麦克风后再使用语音输入。"; return }
        guard run == generation, !Task.isCancelled else { return }
        do {
            try acquire(recording: true)
            let url = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString + ".wav")
            recordingURL = url
            let recorder = try AVAudioRecorder(url: url, settings: [
                AVFormatIDKey: kAudioFormatLinearPCM, AVSampleRateKey: 16000,
                AVNumberOfChannelsKey: 1, AVLinearPCMBitDepthKey: 16,
                AVLinearPCMIsBigEndianKey: false, AVLinearPCMIsFloatKey: false,
                AVLinearPCMIsNonInterleaved: false,
            ])
            self.recorder = recorder; self.client = client; self.onText = onText
            recorder.delegate = self
            guard recorder.prepareToRecord(), recorder.record(forDuration: 60) else { throw APIError(code: "AUDIO_RECORD", message: "无法开始录音。") }
            isRecording = true
            // A short message recording is not a background conversation.
            backgroundObserver = NotificationCenter.default.addObserver(forName: UIApplication.didEnterBackgroundNotification, object: nil, queue: .main) { [weak self] _ in
                Task { @MainActor [weak self] in self?.stop() }
            }
        } catch { stop(); self.error = error.localizedDescription }
    }

    func finishRecording() { guard isRecording else { return }; isRecording = false; recorder?.stop() }
    nonisolated func audioRecorderDidFinishRecording(_ recorder: AVAudioRecorder, successfully flag: Bool) {
        Task { @MainActor [weak self] in
            guard let self, self.recorder === recorder else { return }
            if flag { self.transcribe() } else { self.stop(); self.error = "录音没有完成，请重试。" }
        }
    }
    private func transcribe() {
        guard let url = recordingURL, let client else { return }
        isRecording = false; isWorking = true; recorder = nil; releaseAudio()
        let run = generation
        request = Task { [weak self] in
            guard let self else { return }
            defer { try? FileManager.default.removeItem(at: url); if generation == run { isWorking = false; request = nil; recordingURL = nil } }
            do {
                let data = try Data(contentsOf: url)
                guard data.count <= 2_000_000 else { throw APIError(code: "AUDIO_SIZE", message: "录音超过一分钟，请分段输入。") }
                let result = try await client.upload(path: "assistant/asr", fieldName: "audio", filename: "message.wav", mimeType: "audio/wav", data: data)
                guard generation == run, !Task.isCancelled else { return }
                if let text = result["text"].string?.nonEmpty { onText?(text) }
                else { error = "没听清，请再说一次。" }
            } catch is CancellationError { }
            catch { if generation == run { self.error = error.localizedDescription } }
        }
    }

    func speak(_ text: String, client: APIClient) {
        stop(); error = nil
        guard !text.isEmpty else { return }
        guard text.count <= 1500 else { error = "请选取不超过 1500 字的内容朗读。"; return }
        isWorking = true; let run = generation
        request = Task { [weak self] in
            guard let self else { return }
            defer { if generation == run { isWorking = false; request = nil } }
            do {
                let response = try await client.requestData(.post, path: "assistant/tts", data: JSONValue.object(["text": .string(text)]).encoded(), contentType: "application/json")
                guard generation == run, !Task.isCancelled else { return }
                let headers = Dictionary(response.headers.map { ($0.key.lowercased(), $0.value) }, uniquingKeysWith: { first, _ in first })
                guard headers["x-audio-format"]?.lowercased() == "pcm16le", headers["x-audio-channels"] == "1",
                      let sampleRate = headers["x-audio-sample-rate"].flatMap(Double.init), (8000...48000).contains(sampleRate),
                      !response.data.isEmpty, response.data.count.isMultiple(of: 2), response.data.count <= Int(sampleRate * 2 * 240) else {
                    throw APIError(code: "AUDIO_FORMAT", message: "语音数据格式不完整，无法播放。")
                }
                try acquire(recording: false)
                let player = PCMPlayer(sampleRate: sampleRate); self.player = player
                player.onDrained = { [weak self] in self?.stop() }
                isPlaying = true
                // Keep each scheduled buffer bounded while the player handles sample boundaries.
                for offset in stride(from: 0, to: response.data.count, by: 65536) {
                    // Full TTS is bounded to four minutes; apply pacing to the playback queue.
                    while !Task.isCancelled, generation == run, !player.isEmpty { try await Task.sleep(for: .milliseconds(30)) }
                    guard generation == run, !Task.isCancelled else { return }
                    let end = min(response.data.count, offset + 65536)
                    player.onDrained = end == response.data.count ? { [weak self] in self?.stop() } : nil
                    try player.enqueue(response.data.subdata(in: offset..<end))
                }
            } catch is CancellationError { }
            catch { if generation == run { stop(); self.error = error.localizedDescription } }
        }
    }

    private func acquire(recording: Bool) throws {
        let owner = UUID(); self.owner = owner
        try CampusAudioSession.shared.acquire(owner: owner, recording: recording) { [weak self] in self?.stop() }
        observer = NotificationCenter.default.addObserver(forName: AVAudioSession.interruptionNotification, object: nil, queue: .main) { [weak self] note in
            let began = (note.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt) == AVAudioSession.InterruptionType.began.rawValue
            if began { Task { @MainActor [weak self] in self?.stop() } }
        }
    }
    private func releaseAudio() {
        if let owner { CampusAudioSession.shared.release(owner: owner) }; owner = nil
        if let observer { NotificationCenter.default.removeObserver(observer) }; observer = nil
        if let backgroundObserver { NotificationCenter.default.removeObserver(backgroundObserver) }; backgroundObserver = nil
    }
    func stop() {
        generation = UUID(); request?.cancel(); request = nil
        recorder?.delegate = nil; recorder?.stop(); recorder = nil
        player?.stop(); player = nil; releaseAudio()
        if let recordingURL { try? FileManager.default.removeItem(at: recordingURL) }; recordingURL = nil
        isRecording = false; isWorking = false; isPlaying = false; onText = nil; client = nil
    }
}
