import Foundation

/// Resolves a classroom media reference to a path inside the current session.
///
/// Backend responses normally contain a full `/api/v1/.../media/...` path.
/// Older/canvas payloads may contain the documented relative form
/// `media/file` or `audio/file`. Both must resolve under the *current*
/// session, including the historical `/media/media/` double segment, and an
/// absolute/foreign URL must never reach the authenticated downloader.
public enum ClassroomMediaPathResolver {
    public static func sessionPath(scopePath: String, sessionID: String) -> String {
        scopePath + "/" + sessionID.pathComponent
    }

    public static func resolve(scopePath: String, sessionID: String,
                               source: String, expectedKind: String) throws -> String {
        let session = sessionPath(scopePath: scopePath, sessionID: sessionID)
        let mediaBase = session + "/media/"
        guard let path = ClassroomMediaReference.apiPath(from: source) else {
            throw ClassroomNativeError.invalidResponse("课堂媒体地址不是当前服务的本站路径。")
        }

        let resolved: String
        if path.hasPrefix(mediaBase) {
            resolved = path
        } else if path.hasPrefix("media/") || path.hasPrefix("audio/") {
            resolved = mediaBase + path
        } else {
            throw ClassroomNativeError.invalidResponse("课堂媒体地址不属于当前课堂的媒体路径。")
        }

        guard resolved.hasPrefix(mediaBase) else {
            throw ClassroomNativeError.invalidResponse("课堂媒体地址不属于当前课堂的媒体路径。")
        }
        if expectedKind == "audio" {
            guard resolved.contains("/media/audio/") || resolved.hasPrefix(mediaBase + "audio/") else {
                throw ClassroomNativeError.invalidResponse("讲解音频地址不属于当前课堂的音频路径。")
            }
        }
        return resolved
    }
}