import Foundation
import Testing
@testable import CampusCore

@Suite("ASR client policy")
struct ASRPolicyTests {
    @Test func recordingLimitMatchesSixtySecondsAt16kMonoPCM16() {
        #expect(ASRPolicy.maxRecordingBytes >= 16_000 * 2 * 60)
        #expect(ASRPolicy.uploadTimeout >= 60)
    }

    @Test func backendErrorCodesMapToStableMessages() {
        #expect(ASRPolicy.message(for: APIError(code: "ASR_BUSY", message: "语音识别繁忙，请稍后重试")) == "语音识别暂不可用，请稍后重试。")
        #expect(ASRPolicy.message(for: APIError(code: "ASR_UNAVAILABLE", message: "本地语音识别未就绪")) == "语音识别暂不可用，请稍后重试。")
        #expect(ASRPolicy.message(for: APIError(code: "ASR_AUDIO_TOO_LARGE", message: "录音文件不能超过 10 MB")) == "录音过长，请分段输入。")
        #expect(ASRPolicy.message(for: APIError(code: "ASR_AUDIO_INVALID", message: "音频不是有效的 WAV 文件")) == "录音格式无法识别，请重新录制。")
        #expect(ASRPolicy.message(for: APIError(code: "ASR_LENGTH_REQUIRED", message: "语音上传必须声明 Content-Length")) == "录音上传不完整，请重新录制。")
        #expect(ASRPolicy.message(for: APIError(code: "ASR_FAILED", message: "语音识别失败，请重试")) == "语音识别失败，请重试。")
        #expect(ASRPolicy.message(for: APIError(code: "OTHER", message: "透传后端文案")) == "透传后端文案")
    }

    @Test func timeoutIsMappedBeforeGenericNetworkDescription() {
        #expect(ASRPolicy.message(for: URLError(.timedOut)) == "语音识别超时，请重试。")
    }
}
