import AVFoundation
import Foundation

/// 讲解音频的播放、暂停、停止与系统打断处理。
///
/// 只播本地已下载的音频，避免把鉴权 URL 交给系统播放器后泄露，也避免后台下载与播放抢带宽。
@MainActor
final class ClassroomNarrationPlayer {
    private let owner = UUID()
    private var player: AVPlayer?
    private var endObserver: (any NSObjectProtocol)?
    private var interruption = InterruptionObserver()
    private(set) var isPlaying = false

    var onFinish: (@MainActor () -> Void)?
    var onInterruption: (@MainActor () -> Void)?

    init() {
        interruption.handler = { [weak self] in
            guard let self else { return }
            Task { @MainActor in
                self.isPlaying = false
                self.onInterruption?()
            }
        }
    }

    func play(url: URL, completion: (@MainActor () -> Void)? = nil) throws {
        stop()
        try CampusAudioSession.shared.acquire(owner: owner, recording: false) { [weak self] in
            Task { @MainActor in
                self?.isPlaying = false
                self?.onInterruption?()
            }
        }
        let item = AVPlayerItem(url: url)
        let next = AVPlayer(playerItem: item)
        player = next
        let finish = completion ?? onFinish
        endObserver = NotificationCenter.default.addObserver(
            forName: AVPlayerItem.didPlayToEndTimeNotification, object: item, queue: .main
        ) { [weak self] _ in
            guard let self else { return }
            Task { @MainActor in
                self.isPlaying = false
                finish?()
            }
        }
        next.play()
        isPlaying = true
    }

    func pause() {
        player?.pause()
        isPlaying = false
    }

    func resume() {
        guard let player else { return }
        player.play()
        isPlaying = true
    }

    func stop() {
        if let endObserver { NotificationCenter.default.removeObserver(endObserver) }
        endObserver = nil
        player?.pause()
        player?.seek(to: .zero)
        player = nil
        isPlaying = false
        CampusAudioSession.shared.release(owner: owner)
    }
}

/// 系统打断通知在非主线程投递；这里只做一次跳转，播放器状态始终在 MainActor 上改。
private final class InterruptionObserver: @unchecked Sendable {
    var handler: (@MainActor () -> Void)?
    private var token: (any NSObjectProtocol)?

    init() {
        token = NotificationCenter.default.addObserver(
            forName: AVAudioSession.interruptionNotification, object: AVAudioSession.sharedInstance(), queue: .main
        ) { [weak self] note in
            guard let raw = note.userInfo?[AVAudioSessionInterruptionTypeKey] as? UInt,
                  let type = AVAudioSession.InterruptionType(rawValue: raw), type == .began
            else { return }
            Task { @MainActor in self?.handler?() }
        }
    }

    deinit {
        if let token { NotificationCenter.default.removeObserver(token) }
    }
}
