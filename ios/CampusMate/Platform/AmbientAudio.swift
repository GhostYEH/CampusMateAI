import AVFoundation
import Foundation

/// Loops the project's own focus ambience (rain, library, forest). Only plays
/// while the timer runs and the app is in the foreground; ducks under voice.
@MainActor
final class AmbientAudio {
    private var player: AVAudioPlayer?
    private var current: String?
    private var baseVolume: Float = 0.35

    var isPlaying: Bool { player?.isPlaying == true }

    func play(scene: String, volume: Float = 0.35) {
        baseVolume = volume
        if current == scene, let player {
            player.volume = volume
            if !player.isPlaying { player.play() }
            return
        }
        stop()
        guard let url = Bundle.main.url(forResource: "focus_ambient_\(scene)", withExtension: "m4a") else { return }
        do {
            let player = try AVAudioPlayer(contentsOf: url)
            player.numberOfLoops = -1
            player.volume = volume
            player.prepareToPlay()
            player.play()
            self.player = player
            current = scene
        } catch {
            player = nil
        }
    }

    func setVolume(_ volume: Float) {
        baseVolume = volume
        player?.volume = volume
    }

    /// Voice replies take priority over the ambience.
    func duck(_ ducked: Bool) {
        player?.setVolume(ducked ? baseVolume * 0.28 : baseVolume, fadeDuration: 0.35)
    }

    func pause() { player?.pause() }
    func resume() { player?.play() }

    func stop() {
        player?.stop()
        player = nil
        current = nil
    }
}
