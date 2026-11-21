import Foundation

/// 经典课堂里可直接播放的教师讲解音频。
///
/// 只认服务端在 `actions[].payload.audioUrl` 上给出的本站媒体地址，并且必须能在
/// 同一场景的 `media[]` 里找到 `available=true` 的音频登记；地址、媒体类型或
/// 支持状态任一不满足时都返回不可用，不猜上游地址，也不把外链交给播放器。
public struct ClassroomSpeechAudio: Sendable, Equatable {
    public let actionID: String
    public let audioURL: String
    public let apiPath: String
    public let mediaID: String?
    public let contentType: String
    /// 写入本地缓存时使用的稳定键；正文版本变化会得到新键，旧音频不会被复用。
    public let cacheID: String

    public init(actionID: String, audioURL: String, apiPath: String, mediaID: String?,
                contentType: String, cacheID: String) {
        self.actionID = actionID
        self.audioURL = audioURL
        self.apiPath = apiPath
        self.mediaID = mediaID
        self.contentType = contentType
        self.cacheID = cacheID
    }
}

public enum ClassroomSpeechAudioResolution: Sendable, Equatable {
    case playable(ClassroomSpeechAudio)
    case unavailable(reason: String?)
    case absent
}

extension ClassroomContentRevision {
    /// 缓存键里使用短且稳定的十六进制串，避免把原始 ID 直接拼进文件名。
    public static func token(_ value: String) -> String {
        String(stable(from: value), radix: 16)
    }
}

public enum ClassroomSpeechAudioResolver {
    public static func resolve(scene: ClassroomPlaybackScene, contentVersion: String?) -> ClassroomSpeechAudioResolution {
        let speeches = scene.speechActions
        guard !speeches.isEmpty else { return .absent }
        var reason: String?
        for action in speeches {
            switch resolve(action: action, in: scene, contentVersion: contentVersion) {
            case .playable(let audio):
                return .playable(audio)
            case .unavailable(let actionReason):
                reason = actionReason
            case .absent:
                break
            }
        }
        return .unavailable(reason: reason)
    }

    /// Resolve one speech action. A sequence may contain multiple speech
    /// actions on the same scene, so the scene-level first-playable resolver
    /// cannot be reused for step execution.
    public static func resolve(action: ClassroomPlaybackAction, in scene: ClassroomPlaybackScene,
                               contentVersion: String?) -> ClassroomSpeechAudioResolution {
        guard action.type == "speech" else { return .unavailable(reason: "speech_action_missing") }
        guard action.supported else { return .unavailable(reason: action.reason ?? "speech_action_unsupported") }
        guard let rawURL = action.audioURL else { return .unavailable(reason: "speech_audio_missing") }
        guard let apiPath = ClassroomMediaReference.apiPath(from: rawURL),
              apiPath.contains("/media/audio/")
                || apiPath.hasPrefix("audio/")
                || apiPath.hasPrefix("media/audio/")
        else {
            return .unavailable(reason: "speech_audio_not_site_media")
        }
        let matched = scene.media.first { item in
            item.available
                && item.kind == "audio"
                && (item.url == rawURL
                    || (item.role == "narration" && item.elementID == action.id))
        }
        guard let media = matched else {
            let blocked = scene.media.first {
                $0.kind == "audio" && $0.elementID == action.id && !$0.available
            }
            return .unavailable(reason: blocked?.reason ?? "media_reference_missing")
        }
        guard ClassroomMediaReference.isAudio(contentType: media.contentType, path: apiPath) else {
            return .unavailable(reason: "media_not_audio")
        }
        let versionToken = ClassroomContentRevision.token(contentVersion ?? "")
        let cacheID = "classic_\(versionToken)_\(ClassroomContentRevision.token(scene.id))_"
            + "\(ClassroomContentRevision.token(action.id))_\(ClassroomContentRevision.token(media.id))"
        return .playable(ClassroomSpeechAudio(
            actionID: action.id, audioURL: rawURL, apiPath: apiPath,
            mediaID: media.id, contentType: media.contentType, cacheID: cacheID))
    }
    /// 把服务端 `reason` 或播放层的警告码翻成学生能看懂的一句话。
    public static func message(for reason: String?) -> String {
        switch reason {
        case "external_media_not_proxied":
            return "这一页的讲解音频是外部地址，没有经过本站授权，网页课堂仍可播放。"
        case "media_src_missing":
            return "这一页的讲解音频缺少可读取的地址。"
        case "media_reference_unresolved":
            return "这一页的讲解音频引用无法解析为本站媒体。"
        case "media_owned_by_other_classroom":
            return "这一页的讲解音频属于其他课堂，已拒绝读取。"
        case "narration_audio_unavailable":
            return "这一页的讲解音频不可代理，网页课堂仍可播放文字讲解。"
        case "narration_audio_asset_ref_only", "media_reference_missing":
            return "这一页的讲解音频只有资源引用，服务端没有给出可播放文件。"
        case "speech_audio_missing":
            return "这一页的讲解动作没有成品音频。"
        case "speech_audio_not_site_media":
            return "这一页的讲解音频不是当前课堂的本站媒体地址。"
        case "speech_action_unsupported":
            return "这一页的教师讲解动作当前客户端不能执行，网页课堂仍可播放。"
        case "media_not_audio":
            return "服务端登记的讲解媒体不是音频格式。"
        case let reason? where !reason.isEmpty:
            return "这一页的讲解音频暂不可用（\(reason)）；网页课堂仍可播放讲解。"
        default:
            return "这一页的讲解音频暂不可用；网页课堂仍可播放讲解。"
        }
    }
}

/// 本站媒体引用只接受相对路径。预览、下载和播放都必须再经过 APIClient 的
/// `baseURL` 与鉴权，不能把绝对外链交给系统播放器。
public enum ClassroomMediaReference {
    public static let audioExtensions = ["mp3", "m4a", "wav", "aac", "ogg", "flac"]

    public static func apiPath(from source: String) -> String? {
        let trimmed = source.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty,
              !trimmed.hasPrefix("//"),
              !trimmed.contains("\\"),
              !trimmed.contains("?"),
              !trimmed.contains("#")
        else { return nil }
        let lower = trimmed.lowercased()
        if lower.hasPrefix("http://") || lower.hasPrefix("https://")
            || lower.hasPrefix("data:") || lower.hasPrefix("blob:")
            || lower.hasPrefix("file:") || lower.hasPrefix("javascript:") {
            return nil
        }
        if trimmed.contains("://") { return nil }
        var path = trimmed
        if let range = path.range(of: "/api/v1/") {
            path = String(path[range.upperBound...])
        } else if path.hasPrefix("api/v1/") {
            path = String(path.dropFirst("api/v1/".count))
        }
        while path.hasPrefix("/") { path.removeFirst() }
        guard !path.isEmpty else { return nil }
        let decoded = path.removingPercentEncoding ?? path
        let components = decoded.split(separator: "/", omittingEmptySubsequences: false)
        guard !components.contains(".."), !components.contains(".") else { return nil }
        return path
    }

    public static func audioExtension(path: String, contentType: String? = nil) -> String? {
        let ext = (path as NSString).pathExtension.lowercased()
        if audioExtensions.contains(ext) { return ext }
        switch (contentType ?? "").lowercased() {
        case "audio/mpeg", "audio/mp3": return "mp3"
        case "audio/mp4", "audio/m4a", "audio/x-m4a": return "m4a"
        case "audio/wav", "audio/x-wav", "audio/wave": return "wav"
        case "audio/aac": return "aac"
        case "audio/ogg": return "ogg"
        case "audio/flac": return "flac"
        default: return nil
        }
    }

    public static func isAudio(contentType: String, path: String) -> Bool {
        let type = contentType.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        if type.hasPrefix("audio/") { return true }
        if type.isEmpty || type == "application/octet-stream" {
            return audioExtension(path: path) != nil
        }
        return false
    }

    public static let videoExtensions = ["mp4", "webm", "mov", "m4v"]

    public static func videoExtension(path: String, contentType: String? = nil) -> String? {
        let ext = (path as NSString).pathExtension.lowercased()
        if videoExtensions.contains(ext) { return ext }
        switch (contentType ?? "").lowercased() {
        case "video/mp4": return "mp4"
        case "video/webm": return "webm"
        case "video/quicktime": return "mov"
        case "video/x-m4v": return "m4v"
        default: return nil
        }
    }

    public static func isVideo(contentType: String, path: String) -> Bool {
        let type = contentType.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        if type.hasPrefix("video/") { return true }
        if type.isEmpty || type == "application/octet-stream" {
            return videoExtension(path: path) != nil
        }
        return false
    }
}
