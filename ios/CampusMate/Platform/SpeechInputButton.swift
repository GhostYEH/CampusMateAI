import SwiftUI

/// 与 Android `SpeechInputButton` 对齐的麦克风按钮。
///
/// CPM 与共同课堂共用同一命中区域、录音/识别状态和无障碍语义，避免两处
/// 平行实现各自漂移。按钮本身只负责外观与状态，录音和上传仍由
/// `AssistantSpeech` 处理。
struct SpeechInputButton: View {
    let speech: AssistantSpeech
    let identifier: String
    var enabled = true
    let action: () -> Void

    @Environment(\.campus) private var palette

    var body: some View {
        Button(action: action) {
            Image(systemName: speech.isRecording ? "stop.circle.fill" : "mic.circle")
                .font(.system(size: 27))
                .foregroundStyle(speech.isRecording ? palette.danger : palette.primary)
                .frame(width: 44, height: 44)
                .contentShape(Rectangle())
        }
        .disabled(!enabled || speech.isWorking)
        .accessibilityIdentifier(identifier)
        .accessibilityLabel(speech.isRecording ? "结束录音" : "语音输入")
        .accessibilityValue(speech.isWorking ? "正在识别" : speech.isRecording ? "正在录音" : "空闲")
    }
}
