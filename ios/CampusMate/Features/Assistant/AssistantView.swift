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

/// Port of the CPM conversation: dreamscape header, warm assistant bubbles and
/// the existing streaming + speech pipeline.
private struct AssistantConversationView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var model: AssistantModel
    @State private var speech = AssistantSpeech()
    @State private var input: String
    @State private var confirmClear = false
    @State private var showPlans = false
    @FocusState private var inputFocused: Bool

    init(client: APIClient, scope: String, initialPrompt: String, courseID: String?, relatedTaskID: String?) {
        _model = State(initialValue: AssistantModel(client: client, scope: scope, courseID: courseID, relatedTaskID: relatedTaskID))
        _input = State(initialValue: initialPrompt)
    }

    var body: some View {
        ZStack(alignment: .top) {
            Color(hex: 0xF1F3EA).ignoresSafeArea()
            Image("cpm_campus_dreamscape")
                .resizable()
                .scaledToFill()
                .frame(height: 260)
                .clipped()
                .overlay(LinearGradient(colors: [.clear, Color(hex: 0xF1F3EA)], startPoint: .center, endPoint: .bottom))
                .ignoresSafeArea(edges: .top)
                .allowsHitTesting(false)

            VStack(spacing: 0) {
                header
                ScrollViewReader { proxy in
                    ScrollView {
                        LazyVStack(alignment: .leading, spacing: 14) {
                            if model.messages.isEmpty { emptyState }
                            ForEach(model.messages) { message in
                                bubble(message).id(message.id)
                            }
                        }
                        .padding(.horizontal, 16)
                        .padding(.top, 8)
                        .padding(.bottom, 20)
                    }
                    .scrollDismissesKeyboard(.interactively)
                    .onChange(of: model.messages.last?.text) { _, _ in
                        if let id = model.messages.last?.id {
                            withAnimation(.easeOut(duration: 0.2)) { proxy.scrollTo(id, anchor: .bottom) }
                        }
                    }
                }
            }
        }
        .campusImmersive()
        .safeAreaInset(edge: .bottom) { composer }
        .task { await model.load() }
        .onDisappear { model.cancel(); speech.stop() }
        .toolbar(.hidden, for: .navigationBar)
        .confirmationDialog("清空本机当前对话？", isPresented: $confirmClear, titleVisibility: .visible) {
            Button("清空并开始新对话", role: .destructive) { model.clear() }
        }
        .sheet(isPresented: $showPlans) { plansSheet.presentationDetents([.medium]) }
        .errorAlert(Binding(get: { model.error }, set: { model.error = $0 }))
        .errorAlert(Binding(get: { speech.error }, set: { speech.error = $0 }))
    }

    private var header: some View {
        HStack(spacing: 10) {
            CampusBackButton { dismiss() }
            Image("cpm_avatar_fallback")
                .resizable().scaledToFill()
                .frame(width: 38, height: 38)
                .clipShape(Circle())
                .overlay(Circle().strokeBorder(.white.opacity(0.7), lineWidth: 1))
            VStack(alignment: .leading, spacing: 1) {
                Text("CPM").font(.system(size: 18, weight: .bold)).foregroundStyle(Color(hex: 0x1B2730))
                Text(model.isSending ? "正在回应…" : "学习与事务的陪伴助手")
                    .font(.system(size: 10)).foregroundStyle(Color(hex: 0x667784))
            }
            Spacer()
            Button { showPlans = true } label: {
                Image(systemName: "square.grid.2x2")
                    .font(.system(size: 16))
                    .foregroundStyle(Color(hex: 0x1B2730))
                    .frame(width: 40, height: 40)
                    .background(.ultraThinMaterial, in: Circle())
            }
            .accessibilityLabel("学习计划与工作流")
            Button { confirmClear = true } label: {
                Image(systemName: "square.and.pencil")
                    .font(.system(size: 16))
                    .foregroundStyle(Color(hex: 0x1B2730))
                    .frame(width: 40, height: 40)
                    .background(.ultraThinMaterial, in: Circle())
            }
            .accessibilityLabel("新对话")
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
    }

    private var emptyState: some View {
        VStack(spacing: 12) {
            Image("ai_campus_robot").resizable().scaledToFit().frame(height: 120)
            Text("今天想聊些什么？").font(.system(size: 18, weight: .bold)).foregroundStyle(Color(hex: 0x1B2730))
            Text("可以讨论学习问题、梳理待办，或为下一次专注做准备。")
                .font(.system(size: 12)).foregroundStyle(Color(hex: 0x667784)).multilineTextAlignment(.center)
            HStack(spacing: 8) {
                quickPrompt("帮我拆解今天的待办")
                quickPrompt("陪我准备期末考试")
            }
            .padding(.top, 4)
        }
        .frame(maxWidth: .infinity)
        .padding(.top, 40)
        .padding(.horizontal, 20)
    }

    private func quickPrompt(_ text: String) -> some View {
        Button {
            input = text
            inputFocused = true
        } label: {
            Text(text)
                .font(.system(size: 11, weight: .medium))
                .foregroundStyle(Color(hex: 0x285B4B))
                .padding(.horizontal, 12).padding(.vertical, 8)
                .background(Color(hex: 0xE4EEE5), in: Capsule())
        }
        .buttonStyle(.plain)
    }

    @ViewBuilder
    private func bubble(_ message: ChatMessage) -> some View {
        let isUser = message.role == "user"
        HStack(alignment: .top, spacing: 8) {
            if isUser { Spacer(minLength: 40) }
            if !isUser {
                Image("cpm_avatar_fallback").resizable().scaledToFill()
                    .frame(width: 30, height: 30).clipShape(Circle())
            }
            VStack(alignment: .leading, spacing: 6) {
                if message.text.isEmpty && model.isSending && message.id == model.messages.last?.id {
                    HStack(spacing: 7) {
                        ProgressView().controlSize(.small).tint(Color(hex: 0x285B4B))
                        Text("正在思考…").font(.system(size: 12)).foregroundStyle(.secondary)
                    }
                } else {
                    Text(LocalizedStringKey(message.text))
                        .font(.system(size: 14))
                        .lineSpacing(3)
                        .foregroundStyle(Color(hex: 0x1B2730))
                        .textSelection(.enabled)
                }
                ForEach(message.warnings, id: \.self) { warning in
                    Text(warning).font(.system(size: 11)).foregroundStyle(.secondary)
                }
                if let mode = message.mode, ["retrieval_summary", "no_knowledge", "error"].contains(mode) {
                    Label(mode == "retrieval_summary" ? "当前回复来自检索摘要" : "当前服务能力有限",
                          systemImage: "info.circle")
                        .font(.system(size: 10)).foregroundStyle(.secondary)
                }
                ForEach(Array(message.sources.enumerated()), id: \.offset) { _, source in
                    if let url = URL(string: source["url"].text), ["https", "http"].contains(url.scheme ?? ""), url.user == nil {
                        Link(source["title"].string?.nonEmpty ?? "参考来源", destination: url).font(.system(size: 11))
                    } else if let title = source["title"].string?.nonEmpty {
                        Text(title).font(.system(size: 11)).foregroundStyle(.secondary)
                    }
                }
                if message.interrupted {
                    HStack(spacing: 8) {
                        Label("回复已停止", systemImage: "stop.circle").font(.system(size: 11)).foregroundStyle(.secondary)
                        if message.id == model.messages.last?.id {
                            Button("重试") { model.send(model.lastPrompt, retry: true) }
                                .font(.system(size: 11, weight: .semibold))
                                .disabled(model.isSending || model.lastPrompt.isEmpty)
                        }
                    }
                }
                if !isUser, !message.text.isEmpty, !model.isSending {
                    Button {
                        speech.speak(message.text, client: app.client)
                    } label: {
                        Label("朗读", systemImage: "speaker.wave.2")
                            .font(.system(size: 11))
                            .foregroundStyle(Color(hex: 0x285B4B))
                    }
                    .disabled(speech.isWorking || speech.isRecording)
                }
            }
            .padding(.horizontal, 13)
            .padding(.vertical, 11)
            .background(isUser ? Color(hex: 0xF4F0E5) : Color(hex: 0xEAF0E8),
                        in: RoundedRectangle(cornerRadius: 16, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 16).strokeBorder(Color(hex: 0xD7DED5, opacity: 0.6), lineWidth: 1))
            if !isUser { Spacer(minLength: 30) }
        }
    }

    private var composer: some View {
        VStack(spacing: 0) {
            if speech.isPlaying || speech.isWorking {
                HStack(spacing: 8) {
                    if speech.isWorking { ProgressView().controlSize(.small) }
                    Text(speech.isPlaying ? "正在朗读" : "正在处理语音…").font(.system(size: 11))
                    Spacer()
                    Button("停止") { speech.stop() }.font(.system(size: 11, weight: .semibold))
                }
                .padding(.horizontal, 16).padding(.top, 6)
            }
            HStack(alignment: .bottom, spacing: 10) {
                Button {
                    if speech.isRecording { speech.finishRecording() }
                    else { Task { await speech.record(client: app.client) { text in input += (input.isEmpty ? "" : "\n") + text } } }
                } label: {
                    Image(systemName: speech.isRecording ? "stop.circle.fill" : "mic.circle")
                        .font(.system(size: 27))
                        .foregroundStyle(speech.isRecording ? Color(hex: 0xC25450) : Color(hex: 0x285B4B))
                }
                .disabled(model.isSending || speech.isWorking || speech.isPlaying)
                .accessibilityLabel(speech.isRecording ? "结束录音" : "语音输入")

                TextField("发消息…", text: $input, axis: .vertical)
                    .lineLimit(1...6)
                    .font(.system(size: 14))
                    .focused($inputFocused)
                    .padding(.horizontal, 12).padding(.vertical, 9)
                    .background(Color(hex: 0xFFFEF8), in: RoundedRectangle(cornerRadius: 18))
                    .overlay(RoundedRectangle(cornerRadius: 18).strokeBorder(Color(hex: 0xD7DED5), lineWidth: 1))

                if model.isSending {
                    Button { model.cancel() } label: {
                        Image(systemName: "stop.circle.fill").font(.system(size: 31)).foregroundStyle(Color(hex: 0x285B4B))
                    }
                    .accessibilityLabel("停止回复")
                } else {
                    Button(action: send) {
                        Image(systemName: "arrow.up.circle.fill").font(.system(size: 31)).foregroundStyle(Color(hex: 0x285B4B))
                    }
                    .disabled(input.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                    .accessibilityLabel("发送")
                }
            }
            .padding(.horizontal, 16)
            .padding(.top, 8)
            .padding(.bottom, 8)
        }
        .background(.ultraThinMaterial)
        .overlay(alignment: .top) { Rectangle().fill(Color(hex: 0xD7DED5, opacity: 0.6)).frame(height: 0.5) }
    }

    private var plansSheet: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text("学习计划与工作流").font(.system(size: 18, weight: .bold)).foregroundStyle(Color(hex: 0x1B2730))
                .padding(.bottom, 8)
            planRow("目标与计划", icon: "target", detail: "执行目标、更新进度") { GoalsView() }
            planRow("期末复习", icon: "book.closed", detail: "生成复习计划并运行") { FinalReviewView() }
            planRow("课程研究", icon: "magnifyingglass", detail: "围绕课程做资料研究") { CourseResearchView() }
            Spacer()
        }
        .padding(20)
        .background(Color(hex: 0xF1F3EA))
    }

    private func planRow<Destination: View>(_ title: String, icon: String, detail: String, @ViewBuilder destination: () -> Destination) -> some View {
        NavigationLink {
            destination().onDisappear { showPlans = false }
        } label: {
            HStack(spacing: 12) {
                Image(systemName: icon).font(.system(size: 17)).foregroundStyle(Color(hex: 0x285B4B)).frame(width: 26)
                VStack(alignment: .leading, spacing: 2) {
                    Text(title).font(.system(size: 15, weight: .semibold)).foregroundStyle(Color(hex: 0x1B2730))
                    Text(detail).font(.system(size: 11)).foregroundStyle(.secondary)
                }
                Spacer()
                Image(systemName: "chevron.right").font(.system(size: 12)).foregroundStyle(.secondary)
            }
            .padding(.vertical, 12)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    private func send() {
        let text = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !model.isSending else { return }
        input = ""
        model.send(text)
    }
}
