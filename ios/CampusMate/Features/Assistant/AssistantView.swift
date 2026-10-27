import SwiftUI
import CampusCore

struct AssistantView: View {
    @Environment(AppModel.self) private var app
    var initialPrompt = ""
    var courseID: String?
    var relatedTaskID: String?
    var body: some View {
        AssistantConversationView(client: app.client,
                                  scope: app.serverURL + "|" + (app.session?.user.id ?? "") + "|" + (courseID ?? "") + "|" + (relatedTaskID ?? ""),
                                  initialPrompt: initialPrompt, courseID: courseID, relatedTaskID: relatedTaskID)
    }
}

private struct AssistantConversationView: View {
    @Environment(AppModel.self) private var app
    @State private var model: AssistantModel
    @State private var speech = AssistantSpeech()
    @State private var input: String
    @State private var confirmClear = false
    init(client: APIClient, scope: String, initialPrompt: String, courseID: String?, relatedTaskID: String?) {
        _model = State(initialValue: AssistantModel(client: client, scope: scope, courseID: courseID, relatedTaskID: relatedTaskID))
        _input = State(initialValue: initialPrompt)
    }

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 20) {
                    if model.messages.isEmpty {
                        ContentUnavailableView("今天想聊些什么？", systemImage: "sparkles", description: Text("可以讨论学习问题、梳理待办，或为下一次专注做准备。"))
                            .padding(.top, 60)
                    }
                    ForEach(model.messages) { message in
                        VStack(alignment: .leading, spacing: 7) {
                            Text(message.role == "user" ? "你" : "CampusMate").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                            if message.text.isEmpty && model.isSending && message.id == model.messages.last?.id { ProgressView("正在思考…") }
                            else { Text(LocalizedStringKey(message.text)).textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading) }
                            ForEach(message.warnings, id: \.self) { Text($0).font(.caption).foregroundStyle(.secondary) }
                            if let mode = message.mode, ["retrieval_summary", "no_knowledge", "error"].contains(mode) {
                                Label(mode == "retrieval_summary" ? "当前回复来自检索摘要" : "当前服务能力有限", systemImage: "info.circle").font(.caption).foregroundStyle(.secondary)
                            }
                            ForEach(Array(message.sources.enumerated()), id: \.offset) { _, source in
                                if let url = URL(string: source["url"].text), ["https", "http"].contains(url.scheme ?? ""), url.user == nil {
                                    Link(source["title"].string?.nonEmpty ?? "参考来源", destination: url).font(.caption)
                                } else if let title = source["title"].string?.nonEmpty { Text(title).font(.caption).foregroundStyle(.secondary) }
                            }
                            if message.interrupted {
                                Label("回复已停止", systemImage: "stop.circle").font(.caption).foregroundStyle(.secondary)
                                if message.id == model.messages.last?.id { Button("重试") { model.send(model.lastPrompt, retry: true) }.font(.caption).disabled(model.isSending || model.lastPrompt.isEmpty) }
                            }
                            if message.role == "assistant", !message.text.isEmpty, !model.isSending {
                                Button("朗读", systemImage: "speaker.wave.2") { speech.speak(message.text, client: app.client) }.font(.caption).disabled(speech.isWorking || speech.isRecording)
                            }
                        }.padding(15).background(message.role == "user" ? Color.accentColor.opacity(0.09) : Color(uiColor: .secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 18)).id(message.id)
                    }
                }.padding()
            }
            .onChange(of: model.messages.last?.text) { _, _ in if let id = model.messages.last?.id { proxy.scrollTo(id, anchor: .bottom) } }
        }
        .navigationTitle("CPM")
        .safeAreaInset(edge: .bottom) {
            if speech.isPlaying || speech.isWorking {
                HStack { if speech.isWorking { ProgressView() }; Text(speech.isPlaying ? "正在朗读" : "正在处理语音…").font(.footnote); Spacer(); Button("停止") { speech.stop() } }.padding(.horizontal).padding(.top, 8).background(.bar)
            }
            HStack(alignment: .bottom, spacing: 12) {
                Button {
                    if speech.isRecording { speech.finishRecording() }
                    else { Task { await speech.record(client: app.client) { text in input += (input.isEmpty ? "" : "\n") + text } } }
                } label: { Image(systemName: speech.isRecording ? "stop.circle.fill" : "mic.circle").font(.system(size: 29)).foregroundStyle(speech.isRecording ? Color.red : Color.accentColor) }
                    .disabled(model.isSending || speech.isWorking || speech.isPlaying).accessibilityLabel(speech.isRecording ? "结束录音" : "语音输入")
                TextField("发消息…", text: $input, axis: .vertical).lineLimit(1...6).padding(11).background(.background, in: RoundedRectangle(cornerRadius: 16))
                if model.isSending {
                    Button { model.cancel() } label: { Image(systemName: "stop.circle.fill").font(.system(size: 34)) }.accessibilityLabel("停止回复")
                } else {
                    Button(action: send) { Image(systemName: "arrow.up.circle.fill").font(.system(size: 34)) }
                        .disabled(input.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty).accessibilityLabel("发送")
                }
            }.padding().background(.bar)
        }
        .task { await model.load() }.onDisappear { model.cancel(); speech.stop() }
        .toolbar { Button("新对话", systemImage: "square.and.pencil") { confirmClear = true } }
        .confirmationDialog("清空本机当前对话？", isPresented: $confirmClear, titleVisibility: .visible) { Button("清空并开始新对话", role: .destructive) { model.clear() } }
        .errorAlert(Binding(get: { model.error }, set: { model.error = $0 }))
        .errorAlert(Binding(get: { speech.error }, set: { speech.error = $0 }))
    }

    private func send() {
        let text = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !model.isSending else { return }
        input = ""; model.send(text)
    }
}
