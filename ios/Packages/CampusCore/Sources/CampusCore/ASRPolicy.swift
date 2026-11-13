import Foundation

/// 语音输入的客户端侧约束与错误映射。
///
/// 与后端 `POST /assistant/asr` 契约保持一致：16k/单声道/PCM16 WAV、
/// 60 秒上限（16k × 2 字节 × 60 ≈ 1.92MB，预留 2MB）和稳定错误码。
/// 放在 CampusCore 以便单元测试覆盖，App 层只负责录音与 UI 状态。
public enum ASRPolicy {
    /// 16kHz/16bit/单声道的 60 秒上限；留出少量余量给 WAV 头。
    public static let maxRecordingBytes = 2_000_000
    /// 录音上传弱网下比普通请求更需要余量，单独放宽到 120 秒。
    public static let uploadTimeout: TimeInterval = 120

    /// 把网络/后端错误映射为可直接展示的中文提示。
    public static func message(for error: Error) -> String {
        if let urlError = error as? URLError, urlError.code == .timedOut {
            return "语音识别超时，请重试。"
        }
        guard let api = error as? APIError else { return error.localizedDescription }
        switch api.code {
        case "ASR_BUSY", "ASR_UNAVAILABLE":
            return "语音识别暂不可用，请稍后重试。"
        case "ASR_AUDIO_TOO_LARGE", "ASR_AUDIO_TOO_LONG", "AUDIO_SIZE":
            return "录音过长，请分段输入。"
        case "ASR_AUDIO_INVALID":
            return "录音格式无法识别，请重新录制。"
        case "ASR_LENGTH_REQUIRED":
            return "录音上传不完整，请重新录制。"
        case "ASR_FAILED":
            return "语音识别失败，请重试。"
        default:
            return api.message
        }
    }
}
