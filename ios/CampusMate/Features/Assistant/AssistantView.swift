import SwiftUI
import CampusCore

struct AssistantView: View {
    @Environment(AppModel.self) private var app
    @State private var messages: [Message] = []
    @State private var input = ""
    @State private var sending = false
    @State private var error: String?
    @State private var conversationID: String?

    private struct Message: Identifiable { let id = UUID(); let role: String; var text: String }

    var body: some View {
        ScrollViewReader { proxy in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 20) {
                    if messages.isEmpty {
                        ContentUnavailableView("今天想聊些什么？", systemImage: "sparkles", description: Text("可以讨论学习问题、梳理待办，或为下一次专注做准备。"))
                            .padding(.top, 60)
                    }
                    ForEach(messages) { message in
                        VStack(alignment: .leading, spacing: 7) {
                            Text(message.role == "user" ? "你" : "CampusMate").font(.caption.weight(.semibold)).foregroundStyle(.secondary)
                            Text(LocalizedStringKey(message.text)).textSelection(.enabled).frame(maxWidth: .infinity, alignment: .leading)
                        }.padding(15).background(message.role == "user" ? Color.accentColor.opacity(0.09) : Color(uiColor: .secondarySystemGroupedBackground), in: RoundedRectangle(cornerRadius: 18)).id(message.id)
                    }
                    if sending { ProgressView("正在思考…").padding() }
                }.padding()
            }
            .onChange(of: messages.count) { _, _ in if let id = messages.last?.id { withAnimation { proxy.scrollTo(id, anchor: .bottom) } } }
        }
        .navigationTitle("CPM")
        .safeAreaInset(edge: .bottom) {
            HStack(alignment: .bottom, spacing: 12) {
                TextField("发消息…", text: $input, axis: .vertical).lineLimit(1...6).padding(11).background(.background, in: RoundedRectangle(cornerRadius: 16))
                Button(action: send) { Image(systemName: "arrow.up.circle.fill").font(.system(size: 34)) }
                    .disabled(sending || input.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty).accessibilityLabel("发送")
            }.padding().background(.bar)
        }
        .errorAlert($error)
    }

    private func send() {
        let text = input.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty, !sending else { return }
        input = ""; messages.append(Message(role: "user", text: text)); sending = true
        Task {
            defer { sending = false }
            do {
                var body: [String: JSONValue] = ["message": .string(text), "stream": .bool(false)]
                if let conversationID { body["conversation_id"] = .string(conversationID) }
                let result = try await app.client.request(.post, path: "counselor/chat", body: .object(body))
                conversationID = result["conversation_id"].string
                guard let answer = result["answer"].string?.nonEmpty else { throw APIError(code: "EMPTY_ANSWER", message: "暂未生成答复，请稍后重试。") }
                messages.append(Message(role: "assistant", text: answer))
            } catch is CancellationError { }
            catch { self.error = error.localizedDescription }
        }
    }
}
