import SwiftUI
import CampusCore

let roomRoot = "magicclass/learning-space"

struct LearningRoomsView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.campus) private var palette
    @State private var rooms = RemoteResource()
    @State private var invitations = RemoteResource()
    @State private var title = ""
    @State private var showingCreate = false
    @State private var working = false
    @State private var error: String?
    @State private var selectedRoom: String?

    var body: some View {
        CampusSecondaryScaffold(title: "同学一起学") {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    headerCard
                    if !invitations.value.items.isEmpty {
                        Text("课堂邀请").campusFont(.body).fontWeight(.bold).foregroundStyle(palette.textPrimary)
                        ForEach(invitations.value.items, id: \.self) { invitation in
                            invitationCard(invitation)
                        }
                    }
                    if let invitationError = invitations.error {
                        Text("邀请列表：" + invitationError).campusFont(.caption).foregroundStyle(.secondary)
                    }
                    Text("已加入的课堂").campusFont(.body).fontWeight(.bold).foregroundStyle(palette.textPrimary)
                        .padding(.top, 2)
                    if rooms.isLoading && rooms.value == .null {
                        CampusLoadingState(message: "读取共同课堂…")
                    } else if let error = rooms.error, rooms.value.items.isEmpty {
                        CampusErrorState(message: error) { Task { await load() } }
                    } else if rooms.value.items.isEmpty {
                        CampusEmptyState(title: "还没有共同课堂", message: "创建讨论课堂，或让同学通过你的 UID 邀请你。", systemImage: "person.2")
                    } else {
                        if let error = rooms.error {
                            Text("刷新失败：" + error)
                                .campusFont(.caption)
                                .foregroundStyle(palette.dangerText)
                        }
                        ForEach(rooms.value.items, id: \.self) { room in
                            NavigationLink { LearningRoomView(roomID: room["id"].text) } label: {
                                roomCard(room)
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
                .padding(.horizontal, 20)
                .padding(.bottom, 30)
                .frame(maxWidth: 760)
                .frame(maxWidth: .infinity)
            }
            .refreshable { await load() }
        }
        .task { await load() }
        .navigationDestination(item: $selectedRoom) { LearningRoomView(roomID: $0) }
        .alert("新建讨论课堂", isPresented: $showingCreate) {
            TextField("课堂名称", text: $title)
            Button("创建") { create() }
                .disabled(title.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || title.count > 200)
            Button("取消", role: .cancel) { }
        }
        .errorAlert($error)
    }

    private var headerCard: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 10) {
                Image(systemName: "person.2.badge.plus").font(.system(size: 20)).foregroundStyle(palette.primary)
                VStack(alignment: .leading, spacing: 2) {
                    Text("你的 UID").campusFont(.caption).foregroundStyle(palette.muted)
                    Text(app.session?.user.id ?? "")
                        .font(.system(size: 12, design: .monospaced))
                        .foregroundStyle(palette.textPrimary)
                        .textSelection(.enabled)
                        .lineLimit(1)
                        .minimumScaleFactor(0.7)
                }
                Spacer()
                Button {
                    UIPasteboard.general.string = app.session?.user.id
                    CampusHaptics.success()
                } label: {
                    Text("复制").font(.system(size: 12, weight: .semibold)).foregroundStyle(palette.primary)
                        .padding(.horizontal, 12).padding(.vertical, 7)
                        .background(palette.primarySoft, in: Capsule())
                }
                .accessibilityLabel("复制 UID")
            }
            CampusPrimaryButton(title: "新建讨论课堂", systemImage: "plus", loading: working) {
                showingCreate = true
            }
            Text("最多 8 人。当前 iOS 支持邀请、文字交流与共享页码；音视频 SDK 尚未接入。")
                .campusFont(.caption).foregroundStyle(palette.muted)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(16)
        .background(palette.surface, in: RoundedRectangle(cornerRadius: 20, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 20).strokeBorder(palette.line.opacity(0.7), lineWidth: 1))
    }

    private func invitationCard(_ invitation: JSONValue) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(invitation["title"].text).campusFont(.subtitle).foregroundStyle(palette.textPrimary)
            Text("来自 " + invitation["host_name"].text).campusFont(.caption).foregroundStyle(palette.muted)
            HStack(spacing: 10) {
                Button { decide(invitation, action: "accept") } label: {
                    Text("接受").font(.system(size: 13, weight: .bold)).foregroundStyle(.white)
                        .frame(maxWidth: .infinity).frame(height: 40)
                        .background(palette.primary, in: RoundedRectangle(cornerRadius: 12))
                }
                .disabled(working)
                Button { decide(invitation, action: "decline") } label: {
                    Text("拒绝").font(.system(size: 13, weight: .semibold)).foregroundStyle(palette.muted)
                        .frame(maxWidth: .infinity).frame(height: 40)
                        .background(palette.background, in: RoundedRectangle(cornerRadius: 12))
                }
                .disabled(working)
            }
        }
        .padding(15)
        .background(palette.surface, in: RoundedRectangle(cornerRadius: 18))
        .overlay(RoundedRectangle(cornerRadius: 18).strokeBorder(palette.accent.opacity(0.4), lineWidth: 1))
    }

    private func roomCard(_ room: JSONValue) -> some View {
        HStack(spacing: 12) {
            RoundedRectangle(cornerRadius: 12).fill(palette.primarySoft).frame(width: 42, height: 42)
                .overlay(Image(systemName: "bubble.left.and.bubble.right").foregroundStyle(palette.primary))
            VStack(alignment: .leading, spacing: 3) {
                Text(room["title"].text).campusFont(.body).fontWeight(.semibold).foregroundStyle(palette.textPrimary).lineLimit(1)
                Text(roomSubtitle(room))
                    .campusFont(.caption).foregroundStyle(palette.muted)
            }
            Spacer()
            Image(systemName: "chevron.right").font(.system(size: 12)).foregroundStyle(palette.muted)
        }
        .padding(14)
        .background(palette.surface, in: RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).strokeBorder(palette.line.opacity(0.6), lineWidth: 1))
    }

    /// 列表接口只返回 id/title/host_uid/created_at，不能读取详情字段。
    private func roomSubtitle(_ room: JSONValue) -> String {
        if let date = APIDate.parse(room["created_at"].string) {
            return "创建于 " + date.formatted(date: .abbreviated, time: .omitted)
        }
        let host = room["host_uid"].text
        return host.isEmpty ? "点击进入课堂" : "发起人 " + host
    }

    private func create() {
        working = true
        Task {
            defer { working = false }
            do {
                let result = try await app.client.request(.post, path: roomRoot + "/rooms/native",
                                                          body: ["title": .string(title.trimmingCharacters(in: .whitespacesAndNewlines))])
                title = ""
                selectedRoom = result["id"].string
                await load()
            } catch {
                self.error = error.localizedDescription + "\n创建结果未确认时，请先刷新课堂列表，避免重复创建。"
            }
        }
    }

    private func load() async {
        async let roomLoad: () = rooms.load(client: app.client, path: roomRoot + "/rooms")
        async let invitationLoad: () = invitations.load(client: app.client, path: roomRoot + "/invitations")
        _ = await (roomLoad, invitationLoad)
    }

    private func decide(_ invitation: JSONValue, action: String) {
        working = true
        Task {
            defer { working = false }
            do {
                _ = try await app.client.request(.post, path: roomRoot + "/invitations/\(invitation["room_id"].text.pathComponent)/\(action)")
                if action == "accept" { selectedRoom = invitation["room_id"].string }
                await load()
            } catch { self.error = error.localizedDescription }
        }
    }
}

struct LearningRoomView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @Environment(\.scenePhase) private var scenePhase
    @Environment(\.dynamicTypeSize) private var dynamicTypeSize
    @Environment(\.campus) private var palette
    let roomID: String
    @State private var model = LearningRoomModel()
    @State private var input = ""
    @State private var speech = AssistantSpeech()
    @State private var inviting = false
    @State private var leaving = false
    @State private var working = false
    @State private var archive: URL?
    @FocusState private var inputFocused: Bool

    private var isHost: Bool { model.room["host_uid"].text == app.session?.user.id }
    private var roomPath: String { roomRoot + "/rooms/" + roomID.pathComponent }

    var body: some View {
        ZStack {
            palette.background.ignoresSafeArea()
            VStack(spacing: 0) {
                header
                ScrollView {
                    VStack(alignment: .leading, spacing: 12) {
                        if model.unavailable {
                            CampusEmptyState(title: "课堂已不可访问", message: "课堂可能已结束，或你已不再是成员。请返回课堂列表查看。", systemImage: "person.2.slash")
                        } else if model.room != .null {
                            roomControls
                            memberRow
                            messages
                        } else {
                            CampusLoadingState(message: "读取共同课堂…")
                        }
                    }
                    .padding(.horizontal, 16)
                    .padding(.vertical, 12)
                    .frame(maxWidth: 760)
                    .frame(maxWidth: .infinity)
                }
                .scrollDismissesKeyboard(.interactively)
                composer
            }
        }
        .campusImmersive()
        .task {
            await model.bootstrap(client: app.client, roomID: roomID, account: app.serverURL + "|" + (app.session?.user.id ?? ""))
            while !Task.isCancelled, !model.unavailable {
                try? await Task.sleep(for: .seconds(3))
                if !Task.isCancelled && scenePhase == .active { await model.poll(client: app.client, roomID: roomID) }
            }
        }
        .refreshable { await model.poll(client: app.client, roomID: roomID) }
        .sheet(isPresented: $inviting) { NavigationStack { InviteRoomMemberView(roomID: roomID) } }
        .confirmationDialog(isHost ? "结束后所有成员将离开，课件归档也会移除。" : "离开后将不能读取这间课堂。",
                            isPresented: $leaving, titleVisibility: .visible) {
            Button(isHost ? "结束课堂" : "离开课堂", role: .destructive) {
                perform { _ = try await app.client.request(.post, path: roomPath + "/leave"); dismiss() }
            }
            .accessibilityIdentifier("room.leave.confirm")
        }
        .onDisappear { if let archive { try? FileManager.default.removeItem(at: archive) } }
        .errorAlert(Binding(get: { model.error }, set: { model.error = $0 }))
    }

    private var header: some View {
        HStack(spacing: 10) {
            CampusBackButton(tint: palette.textPrimary) { dismiss() }
            VStack(alignment: .leading, spacing: 2) {
                Text(model.room["title"].text.isEmpty ? "共同课堂" : model.room["title"].text)
                    .campusFont(.title).foregroundStyle(palette.textPrimary).lineLimit(2)
                    .fixedSize(horizontal: false, vertical: true)
                Text("共享第 \((model.room["scene_index"].int ?? 0) + 1) / \(max(1, model.room["scene_count"].int ?? 1)) 页")
                    .campusFont(.micro).fontWeight(.regular).foregroundStyle(palette.muted)
            }
            Spacer(minLength: 6)
            Button { leaving = true } label: {
                Text(isHost ? "结束" : "离开")
                    .campusFont(.caption).fontWeight(.semibold)
                    .foregroundStyle(palette.danger)
                    .padding(.horizontal, 12).padding(.vertical, 7)
                    .background(palette.alertErrorBackground, in: Capsule())
            }
            .disabled(working || model.unavailable)
            .accessibilityIdentifier("room.leave")
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
    }

    private var roomControls: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 10) {
                if isHost {
                    pageButton("上一页", icon: "chevron.left", enabled: (model.room["scene_index"].int ?? 0) > 0) { changePage(-1) }
                    pageButton("下一页", icon: "chevron.right",
                               enabled: (model.room["scene_index"].int ?? 0) + 1 < (model.room["scene_count"].int ?? 1)) { changePage(1) }
                    Button { inviting = true } label: {
                        Image(systemName: "person.badge.plus").font(.system(size: 15))
                            .foregroundStyle(palette.primary)
                            .frame(width: 42, height: 42)
                            .background(palette.primarySoft, in: RoundedRectangle(cornerRadius: 12))
                    }
                    .accessibilityLabel("邀请同学")
                } else {
                    Text("发起人控制共享页码，你可以跟随阅读。").campusFont(.caption)
                        .foregroundStyle(palette.muted)
                        .fixedSize(horizontal: false, vertical: true)
                    Spacer()
                }
            }
            HStack(spacing: 14) {
                Button {
                    perform {
                        let file = try await app.client.download(path: roomPath + "/archive")
                        let url = FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString + ".maic.zip")
                        try FileManager.default.moveItem(at: file.url, to: url)
                        if let archive { try? FileManager.default.removeItem(at: archive) }
                        archive = url
                    }
                } label: {
                    Label("下载共同课件", systemImage: "arrow.down.doc").campusFont(.caption)
                        .foregroundStyle(palette.primary)
                }
                .disabled(working || model.unavailable)
                if let archive { ShareLink("保存或分享课件", item: archive).campusFont(.caption) }
                Spacer()
            }
        }
        .padding(14)
        .background(palette.surface, in: RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).strokeBorder(palette.line.opacity(0.6), lineWidth: 1))
    }

    private func pageButton(_ title: String, icon: String, enabled: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 5) {
                Image(systemName: icon).font(.system(size: 11, weight: .bold))
                Text(title).campusFont(.caption).fontWeight(.semibold)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .foregroundStyle(enabled ? palette.primary : palette.muted)
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
            .frame(minHeight: 42)
            .background(palette.primarySoft.opacity(enabled ? 1 : 0.5), in: RoundedRectangle(cornerRadius: 12))
        }
        .disabled(!enabled || working)
    }

    private var memberRow: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 8) {
                ForEach(model.room["members"].items, id: \.self) { member in
                    HStack(spacing: 6) {
                        Circle().fill(member["status"].text == "accepted" ? palette.success : palette.accent)
                            .frame(width: 6, height: 6)
                        Text(member["name"].text).campusFont(.label).foregroundStyle(palette.textPrimary)
                        if member["uid"].text == model.room["host_uid"].text {
                            Text("发起人").campusFont(.micro).fontWeight(.regular).foregroundStyle(palette.muted)
                        }
                    }
                    .padding(.horizontal, 10).padding(.vertical, 7)
                    .background(palette.surface, in: Capsule())
                }
            }
        }
    }

    private var messages: some View {
        VStack(alignment: .leading, spacing: 8) {
            if model.messages.isEmpty {
                Text("发一条消息，和同学开始讨论。").campusFont(.caption).foregroundStyle(palette.muted)
                    .frame(maxWidth: .infinity, alignment: .center).padding(.vertical, 20)
            }
            ForEach(model.messages, id: \.self) { message in
                let mine = message["uid"].text == app.session?.user.id
                HStack {
                    if mine { Spacer(minLength: dynamicTypeSize.isAccessibilitySize ? 12 : 40) }
                    VStack(alignment: .leading, spacing: 3) {
                        if !mine {
                            Text(message["name"].text).campusFont(.micro).fontWeight(.regular)
                                .foregroundStyle(palette.muted)
                        }
                        Text(message["content"].text)
                            .campusFont(.body)
                            .foregroundStyle(palette.textPrimary)
                            .textSelection(.enabled)
                    }
                    .padding(.horizontal, 12).padding(.vertical, 9)
                    .background(mine ? palette.chatUserBackground : palette.chatAssistantBackground,
                                in: RoundedRectangle(cornerRadius: 14, style: .continuous))
                    if !mine { Spacer(minLength: dynamicTypeSize.isAccessibilitySize ? 8 : 40) }
                }
            }
        }
    }

    private var composer: some View {
        VStack(alignment: .leading, spacing: 4) {
            if speech.isWorking {
                HStack(spacing: 8) {
                    ProgressView().controlSize(.small)
                    Text("正在识别语音…").campusFont(.caption).foregroundStyle(palette.muted)
                    Spacer()
                    Button("停止") { speech.stop() }
                        .campusFont(.caption).fontWeight(.semibold)
                        .foregroundStyle(palette.primary)
                }
                .padding(.horizontal, 12)
                .accessibilityIdentifier("room.mic.status")
            }
            HStack(alignment: .bottom, spacing: 10) {
                TextField("和同学聊聊…", text: $input, axis: .vertical)
                    .lineLimit(1...5)
                    .campusFont(.body)
                    .foregroundStyle(palette.textPrimary)
                    .tint(palette.primary)
                    .focused($inputFocused)
                    .padding(.horizontal, 12).padding(.vertical, 9)
                    .background(palette.surface, in: RoundedRectangle(cornerRadius: 18))
                    .overlay(RoundedRectangle(cornerRadius: 18).strokeBorder(palette.line, lineWidth: 1))
                SpeechInputButton(
                    speech: speech,
                    identifier: "room.mic",
                    enabled: !model.isSending
                ) {
                    if speech.isRecording {
                        speech.finishRecording()
                    } else {
                        Task {
                            await speech.record(client: app.client) { text in
                                input += (input.isEmpty ? "" : "\n") + text
                            }
                        }
                    }
                }
                Button {
                    let text = input
                    guard !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else { return }
                    // 先清空再等待发送：识别结果可能在 await 期间回填，不能发送完整体清空。
                    input = ""
                    Task {
                        if !(await model.send(text, client: app.client, roomID: roomID)) {
                            input = input.isEmpty ? text : text + "\n" + input
                        }
                    }
                } label: {
                    Text("发送").campusFont(.body).fontWeight(.bold).foregroundStyle(.white)
                        .padding(.horizontal, 18)
                        .padding(.vertical, 10)
                        .frame(minHeight: 40)
                        .background(palette.primary, in: Capsule())
                }
                .disabled(!canSend)
                .opacity(canSend ? 1 : 0.5)
            }
            if let message = speech.error {
                Text(message)
                    .campusFont(.caption)
                    .foregroundStyle(palette.dangerText)
                    .padding(.horizontal, 12)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 8)
        .background(.ultraThinMaterial)
        .onDisappear { speech.stop() }
    }

    private var canSend: Bool {
        !model.isSending && !model.unavailable && !speech.isRecording && !speech.isWorking
            && !input.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
            && input.count <= 2000
    }

    private func changePage(_ delta: Int) {
        let target = (model.room["scene_index"].int ?? 0) + delta
        perform {
            _ = try await app.client.request(.patch, path: roomPath + "/cursor", body: ["scene_index": .number(Double(target))])
            await model.poll(client: app.client, roomID: roomID)
        }
    }

    private func perform(_ action: @escaping @MainActor () async throws -> Void) {
        working = true
        Task {
            defer { working = false }
            do { try await action() } catch { model.error = error.localizedDescription }
        }
    }
}

private struct InviteRoomMemberView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @Environment(\.campus) private var palette
    let roomID: String
    @State private var uid = ""
    @State private var target: JSONValue = .null
    @State private var working = false
    @State private var error: String?

    var body: some View {
        CampusSecondaryScaffold(title: "邀请同学") {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    CampusCard {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("通过账号 UID 邀请").campusFont(.subtitle).foregroundStyle(palette.textPrimary)
                            CampusTextField(placeholder: "同学的 UID", text: $uid)
                                .onChange(of: uid) { _, _ in target = .null }
                            CampusSecondaryButton(title: "查找同学", enabled: !working && !uid.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty) {
                                perform {
                                    target = try await app.client.request(path: roomRoot + "/students/" + uid.trimmingCharacters(in: .whitespacesAndNewlines).pathComponent)
                                }
                            }
                        }
                    }
                    if target != .null {
                        CampusCard {
                            VStack(alignment: .leading, spacing: 10) {
                                LabeledContent("同学", value: target["name"].text)
                                Text(target["uid"].text).font(.system(size: 11, design: .monospaced)).foregroundStyle(.secondary)
                                CampusPrimaryButton(title: "发送邀请") {
                                    perform {
                                        _ = try await app.client.request(.post, path: roomRoot + "/rooms/\(roomID.pathComponent)/invitations",
                                                                         body: ["uid": target["uid"]])
                                        dismiss()
                                    }
                                }
                            }
                        }
                    }
                }
                .padding(20)
                .frame(maxWidth: 700)
                .frame(maxWidth: .infinity)
            }
        }
        .errorAlert($error)
    }

    private func perform(_ action: @escaping @MainActor () async throws -> Void) {
        working = true
        Task {
            defer { working = false }
            do { try await action() } catch { self.error = error.localizedDescription }
        }
    }
}
