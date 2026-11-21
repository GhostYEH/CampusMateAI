import AVFoundation
import Foundation
import Observation
import CampusCore

/// 画布媒体（音频/视频）的按需下载与系统播放器封装。
/// 只使用当前 session 的本站鉴权路径；下载失败、类型不符或越界路径都回到可读状态，
/// 不把外链交给 AVPlayer。
@MainActor
@Observable
final class ClassroomCanvasMediaPlayer {
    enum Phase: Equatable {
        case idle
        case loading
        case ready
        case playing
        case failed(String)
    }

    private(set) var phase: Phase = .idle
    private(set) var isPlaying = false

    @ObservationIgnored private var player: AVPlayer?
    @ObservationIgnored private var endObserver: (any NSObjectProtocol)?
    @ObservationIgnored private var generation = 0
    @ObservationIgnored private let owner = UUID()

    var videoPlayer: AVPlayer? { player }

    func toggle(kind: String, elementID: String, source: String, version: String,
                sessionID: String, scope: ClassroomScope, client: APIClient, accountKey: String,
                onVideoReady: @escaping @MainActor () -> Void) async {
        if phase == .loading { return }
        if isPlaying {
            pause()
            return
        }
        if let player, phase == .ready {
            do { try activateAudioSession() } catch {
                phase = .failed("音频会话不可用：\(error.localizedDescription)")
                return
            }
            player.play()
            phase = .playing
            isPlaying = true
            if kind == "video" { onVideoReady() }
            return
        }
        generation += 1
        let token = generation
        phase = .loading
        do {
            let url = try await cachedURL(kind: kind, elementID: elementID, source: source,
                                          version: version, sessionID: sessionID, scope: scope,
                                          client: client, accountKey: accountKey)
            guard token == generation else { return }
            start(url: url, kind: kind, onVideoReady: onVideoReady)
        } catch is CancellationError {
            phase = .idle
        } catch {
            guard token == generation else { return }
            phase = .failed(ClassroomNativePresentation.message(for: error, fallback: "媒体下载失败，请检查网络后重试。"))
        }
    }

    func pause() {
        player?.pause()
        isPlaying = false
        phase = player == nil ? .idle : .ready
    }

    func stop() {
        player?.pause()
        player?.seek(to: .zero)
        isPlaying = false
        phase = player == nil ? .idle : .ready
        CampusAudioSession.shared.release(owner: owner)
    }

    func shutdown() {
        generation += 1
        player?.pause()
        player = nil
        isPlaying = false
        phase = .idle
        CampusAudioSession.shared.release(owner: owner)
        if let endObserver {
            NotificationCenter.default.removeObserver(endObserver)
            self.endObserver = nil
        }
    }

    private func start(url: URL, kind: String, onVideoReady: @escaping @MainActor () -> Void) {
        let item = AVPlayerItem(url: url)
        let newPlayer = AVPlayer(playerItem: item)
        player?.pause()
        player = newPlayer
        if let endObserver {
            NotificationCenter.default.removeObserver(endObserver)
        }
        endObserver = NotificationCenter.default.addObserver(
            forName: AVPlayerItem.didPlayToEndTimeNotification, object: item, queue: .main
        ) { [weak self] _ in
            Task { @MainActor in
                self?.isPlaying = false
                self?.phase = .ready
            }
        }
        do { try activateAudioSession() } catch {
            phase = .failed("音频会话不可用：\(error.localizedDescription)")
            return
        }
        newPlayer.play()
        phase = .playing
        isPlaying = true
        if kind == "video" { onVideoReady() }
    }

    private func activateAudioSession() throws {
        try CampusAudioSession.shared.acquire(owner: owner, recording: false) { [weak self] in
            Task { @MainActor in self?.pause() }
        }
    }

    private func cachedURL(kind: String, elementID: String, source: String, version: String,
                           sessionID: String, scope: ClassroomScope, client: APIClient,
                           accountKey: String) async throws -> URL {
        let cacheID = "canvas_\(ClassroomContentRevision.token("\(accountKey)|\(version)|\(sessionID)|\(elementID)|\(source)"))"
        if kind == "audio", let cached = ClassroomAudioCache.shared.url(accountKey: accountKey, resourceID: cacheID) {
            return cached
        }
        if kind == "video", let cached = try videoCacheURL(cacheID: cacheID) {
            return cached
        }
        let resource = try await ClassroomService(client: client, scope: scope)
            .downloadSessionMedia(sessionID: sessionID, mediaURL: source, expectedKind: kind)
        let temporaryURL = resource.url
        var deliveredURL: URL?
        defer {
            if let deliveredURL, deliveredURL == temporaryURL {
                // 缓存不可用时下载文件本身就是播放源，不能删除。
            } else {
                try? FileManager.default.removeItem(at: temporaryURL)
            }
        }
        if kind == "audio" {
            let ext = ClassroomMediaReference.audioExtension(path: source, contentType: resource.mimeType) ?? "mp3"
            let stored = try ClassroomAudioCache.shared.store(resource.url, accountKey: accountKey,
                                                            resourceID: cacheID, fileExtension: ext)
            deliveredURL = stored
            return stored
        }
        let ext = ClassroomMediaReference.videoExtension(path: source, contentType: resource.mimeType) ?? "mp4"
        let copied = try copyVideoToCache(resource.url, cacheID: cacheID, fileExtension: ext)
        deliveredURL = copied
        return copied
    }

    private func videoCacheDirectory() throws -> URL {
        let base = FileManager.default.urls(for: .cachesDirectory, in: .userDomainMask).first!
            .appendingPathComponent("CampusMate", isDirectory: true)
            .appendingPathComponent("ClassroomVideo", isDirectory: true)
        try FileManager.default.createDirectory(at: base, withIntermediateDirectories: true)
        return base
    }

    private func videoCacheURL(cacheID: String) throws -> URL? {
        let directory = try videoCacheDirectory()
        for ext in ClassroomMediaReference.videoExtensions {
            let file = directory.appendingPathComponent("\(cacheID).\(ext)")
            if let size = (try? file.resourceValues(forKeys: [.fileSizeKey]))?.fileSize, size > 0 {
                return file
            }
        }
        return nil
    }

    private func copyVideoToCache(_ source: URL, cacheID: String, fileExtension: String) throws -> URL {
        let directory = try videoCacheDirectory()
        let destination = directory.appendingPathComponent("\(cacheID).\(fileExtension)")
        if FileManager.default.fileExists(atPath: destination.path) { return destination }
        try? FileManager.default.removeItem(at: destination)
        try FileManager.default.copyItem(at: source, to: destination)
        return destination
    }
}
