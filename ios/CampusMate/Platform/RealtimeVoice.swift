import AVFoundation
import UIKit
import Observation
import CampusCore

@MainActor @Observable
final class RealtimeVoiceEngine {
    private(set) var isConnecting = false
    private(set) var isConnected = false
    private(set) var transcript = RealtimeTranscript()
    private(set) var error: String?
    var statusText: String {
        if isConnecting { return "正在连接" }
        if !isConnected { return "已关闭" }
        switch transcript.phase { case "speaking": return "正在回答"; case "thinking": return "正在思考"; default: return "正在聆听" }
    }
    @ObservationIgnored private var generation = UUID()
    @ObservationIgnored private var audioOwner: UUID?
    @ObservationIgnored private var socket: URLSessionWebSocketTask?
    @ObservationIgnored private var webSession: URLSession?
    @ObservationIgnored private var endpoint: VoiceEndpoint?
    @ObservationIgnored private var client: APIClient?
    @ObservationIgnored private var player: PCMPlayer?
    @ObservationIgnored private var tapped = false
    @ObservationIgnored private var allowAudio = true
    @ObservationIgnored private var receiveTask: Task<Void, Never>?
    @ObservationIgnored private var sendTask: Task<Void, Never>?
    @ObservationIgnored private var timeoutTask: Task<Void, Never>?
    @ObservationIgnored private var authTask: Task<Void, Never>?
    @ObservationIgnored private var observers: [NSObjectProtocol] = []
    @ObservationIgnored private var outgoing: AsyncThrowingStream<VoiceFrame, Error>.Continuation?
    private enum VoiceFrame: Sendable { case pcm(Data); case control(String) }

    func start(client: APIClient) async {
        guard !isConnecting, !isConnected else { return }
        error = nil; isConnecting = true; transcript = RealtimeTranscript()
        let run = UUID(); generation = run; self.client = client
        do {
            guard await AVAudioApplication.requestRecordPermission() else { throw APIError(code: "MIC_DENIED", message: "请在系统设置中允许麦克风后再开启语音。") }
            guard generation == run else { return }; try Task.checkCancellation()
            let endpoint = try await StudyService(client: client).createVoice()
            guard generation == run, !Task.isCancelled else { try? await StudyService(client: client).stopVoice(id: endpoint.sessionID); if generation == run { stop() }; return }
            self.endpoint = endpoint
            let config = URLSessionConfiguration.ephemeral
            config.httpCookieStorage = nil; config.urlCache = nil; config.timeoutIntervalForRequest = 30
            let webSession = URLSession(configuration: config, delegate: VoiceRedirectGuard(origin: client.baseURL), delegateQueue: nil)
            self.webSession = webSession
            let socket = webSession.webSocketTask(with: endpoint.url); self.socket = socket
            socket.maximumMessageSize = 1_048_576
            let frames = AsyncThrowingStream<VoiceFrame, Error>.makeStream(bufferingPolicy: .bufferingOldest(32))
            outgoing = frames.continuation; allowAudio = false
            sendTask = Task { [weak self] in
                do {
                    for try await frame in frames.stream {
                        try Task.checkCancellation()
                        switch frame { case .pcm(let bytes): try await socket.send(.data(bytes)); case .control(let text): try await socket.send(.string(text)) }
                    }
                } catch { if self?.generation == run { self?.fail("音频上传连接已中断。") } }
            }
            socket.resume()
            receiveTask = Task { [weak self] in
                do {
                    while !Task.isCancelled {
                        let message = try await socket.receive()
                        guard let self, self.generation == run else { return }
                        switch message {
                        case .data(let data): if self.allowAudio { try self.player?.enqueue(data) }
                        case .string(let text): try self.handle(text, run: run)
                        @unknown default: break
                        }
                    }
                } catch { if self?.generation == run { self?.fail("实时语音连接已结束，请重新连接。") } }
            }
            timeoutTask = Task { [weak self] in
                try? await Task.sleep(for: .seconds(30))
                if !Task.isCancelled, self?.generation == run, self?.isConnecting == true { self?.fail("语音服务未能就绪，请稍后重试。") }
            }
            let userID = await client.currentSession?.user.id
            authTask = Task { [weak self] in
                while !Task.isCancelled {
                    try? await Task.sleep(for: .seconds(1))
                    guard !Task.isCancelled, self?.generation == run else { return }
                    if await client.currentSession?.user.id != userID { self?.stop(); return }
                }
            }
        } catch is CancellationError { if generation == run { stop() } }
        catch { if generation == run { fail(error.localizedDescription) } }
    }

    private func handle(_ text: String, run: UUID) throws {
        guard let data = text.data(using: .utf8) else { return }
        let value = try JSONDecoder().decode(JSONValue.self, from: data)
        let type = value["type"].text
        if type == "error" { fail(value["message"].string ?? "实时语音暂时不可用。"); return }
        if type == "session_closed" { stop(); return }
        if type == "user_speech_started" { player?.clear(); allowAudio = false }
        if type == "user_transcript_done" { allowAudio = false }
        transcript.consume(value)
        if ["ai_text_delta", "ai_text_done"].contains(type), transcript.activeResponseID != nil { allowAudio = true }
        if type == "state", ["listening", "speaking"].contains(value["state"].text), !isConnected {
            try beginAudio(run: run)
            isConnecting = false; isConnected = true; timeoutTask?.cancel(); timeoutTask = nil
        }
    }

    private func beginAudio(run: UUID) throws {
        guard UIApplication.shared.applicationState == .active else { throw APIError(code: "AUDIO_FOREGROUND", message: "请回到应用后重新开启语音。") }
        let owner = UUID(); audioOwner = owner
        try CampusAudioSession.shared.acquire(owner: owner, recording: true) { [weak self] in self?.fail("音频已被其他功能接管。") }
        let engine = AVAudioEngine()
        // Voice processing is enabled before reading the hardware format.
        try engine.inputNode.setVoiceProcessingEnabled(true)
        let format = engine.inputNode.outputFormat(forBus: 0)
        let converter = try MicrophonePCMConverter(source: format)
        let player = PCMPlayer(engine: engine); self.player = player
        guard let outgoing else { throw CancellationError() }
        engine.inputNode.installTap(onBus: 0, bufferSize: 2048, format: format) { buffer, _ in
            do {
                let data = try converter.convert(buffer)
                guard !data.isEmpty else { return }
                if case .dropped = outgoing.yield(.pcm(data)) { outgoing.finish(throwing: APIError(code: "AUDIO_BACKPRESSURE", message: "网络暂时无法传输音频。")) }
            } catch { outgoing.finish(throwing: error) }
        }
        tapped = true; engine.prepare(); try engine.start()
        let center = NotificationCenter.default
        observers = [
            center.addObserver(forName: AVAudioSession.interruptionNotification, object: nil, queue: .main) { [weak self] note in
                let began = (note.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt) == AVAudioSession.InterruptionType.began.rawValue
                if began { Task { @MainActor [weak self] in if self?.generation == run { self?.fail("语音被系统音频中断，点击后可重新连接。") } } }
            },
            center.addObserver(forName: AVAudioSession.routeChangeNotification, object: nil, queue: .main) { [weak self] note in
                let removed = (note.userInfo?[AVAudioSessionRouteChangeReasonKey] as? UInt) == AVAudioSession.RouteChangeReason.oldDeviceUnavailable.rawValue
                if removed { Task { @MainActor [weak self] in if self?.generation == run { self?.fail("音频设备已断开，语音已停止。") } } }
            }
        ]
    }

    func interrupt() {
        transcript.cancelResponse(); player?.clear(); allowAudio = false
        if case .dropped = outgoing?.yield(.control("{\"type\":\"response.cancel\"}")) { fail("网络拥堵，语音已停止。") }
    }
    private func fail(_ message: String) { stop(); error = message }
    func stop() {
        generation = UUID(); isConnected = false; isConnecting = false
        if tapped { player?.engine.inputNode.removeTap(onBus: 0); tapped = false }
        player?.stop(); player = nil
        if let owner = audioOwner { CampusAudioSession.shared.release(owner: owner) }; audioOwner = nil
        observers.forEach(NotificationCenter.default.removeObserver); observers = []
        outgoing?.finish(); outgoing = nil
        sendTask?.cancel(); receiveTask?.cancel(); timeoutTask?.cancel(); authTask?.cancel()
        sendTask = nil; receiveTask = nil; timeoutTask = nil; authTask = nil
        socket?.cancel(with: .normalClosure, reason: nil); socket = nil
        webSession?.invalidateAndCancel(); webSession = nil
        if let endpoint, let client { Task { try? await StudyService(client: client).stopVoice(id: endpoint.sessionID) } }
        endpoint = nil; client = nil; transcript.consume(["type": "session_closed"])
    }
}

private final class VoiceRedirectGuard: NSObject, URLSessionTaskDelegate, Sendable {
    let origin: URL
    init(origin: URL) { self.origin = origin }
    func urlSession(_ session: URLSession, task: URLSessionTask, willPerformHTTPRedirection response: HTTPURLResponse, newRequest request: URLRequest, completionHandler: @escaping @Sendable (URLRequest?) -> Void) {
        // A voice credential URL is never forwarded by a redirect.
        completionHandler(nil)
    }
}
