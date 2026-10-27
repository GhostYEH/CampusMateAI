import SwiftUI
import UniformTypeIdentifiers
import CampusCore

/// Port of the classroom hub: an evening classroom scene with the three real
/// entry points (self-topic, course classroom, classmates).
struct ClassroomHubView: View {
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        CampusSecondaryScaffold(title: "互动课堂") {
            ScrollView {
                VStack(spacing: 14) {
                    ZStack(alignment: .bottomLeading) {
                        Image("classroom_evening_interior")
                            .resizable().scaledToFill()
                            .frame(height: 210)
                            .clipped()
                        LinearGradient(colors: [.clear, Color(hex: 0x101F3F, opacity: 0.85)],
                                       startPoint: .center, endPoint: .bottom)
                        VStack(alignment: .leading, spacing: 4) {
                            Text("把一门课变成一次对话").font(.system(size: 20, weight: .bold)).foregroundStyle(.white)
                            Text("课堂由真实课程资料生成，进度与播放地址来自服务端。")
                                .font(.system(size: 11)).foregroundStyle(.white.opacity(0.8))
                        }
                        .padding(16)
                    }
                    .frame(height: 210)
                    .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))

                    NavigationLink { ClassicClassroomView(scope: .personal) } label: {
                        hubRow(icon: "sparkles", title: "自主选题课堂",
                               detail: "自己定主题，上传资料后生成", accent: Color(hex: 0xE08A4E))
                    }
                    .buttonStyle(.plain)
                    NavigationLink { CoursesView() } label: {
                        hubRow(icon: "books.vertical", title: "从课程开始",
                               detail: "进入图书馆，选择一门真实课程", accent: Color(hex: 0x285B4B))
                    }
                    .buttonStyle(.plain)
                    NavigationLink { LearningRoomsView() } label: {
                        hubRow(icon: "person.2", title: "同学一起学",
                               detail: "共同课堂、文字讨论与共享页码", accent: Color(hex: 0x6D8B9B))
                    }
                    .buttonStyle(.plain)

                    HStack(alignment: .top, spacing: 9) {
                        Image(systemName: "info.circle").font(.system(size: 13)).foregroundStyle(Color(hex: 0x285B4B))
                        Text("自主选题和课程课堂分别保存。共同课堂通过 UID 邀请同学，文字与通话权限按成员关系校验。")
                            .campusFont(.caption).foregroundStyle(.secondary)
                    }
                    .padding(14)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(Color(hex: 0xE4EEE5).opacity(0.7), in: RoundedRectangle(cornerRadius: 16))
                }
                .padding(.horizontal, 20)
                .padding(.bottom, 30)
                .frame(maxWidth: 760)
                .frame(maxWidth: .infinity)
            }
        }
    }

    private func hubRow(icon: String, title: String, detail: String, accent: Color) -> some View {
        HStack(spacing: 13) {
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(accent.opacity(0.14)).frame(width: 46, height: 46)
                .overlay(Image(systemName: icon).font(.system(size: 20, weight: .medium)).foregroundStyle(accent))
            VStack(alignment: .leading, spacing: 3) {
                Text(title).campusFont(.subtitle).foregroundStyle(Color(hex: 0x1B2730))
                Text(detail).campusFont(.caption).foregroundStyle(.secondary)
            }
            Spacer()
            Image(systemName: "chevron.right").font(.system(size: 12, weight: .semibold)).foregroundStyle(.secondary)
        }
        .padding(15)
        .background(Color(hex: 0xFFFEF8), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 18).strokeBorder(Color(hex: 0xD7DED5, opacity: 0.7), lineWidth: 1))
    }
}

struct ClassicClassroomView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @Environment(\.scenePhase) private var scenePhase
    let scope: ClassroomScope
    @State private var model = ClassroomModel()
    @State private var goal = ""
    @State private var difficulty = ""
    @State private var minutes = 25
    @State private var mode = "adaptive"
    @State private var practice = false
    @State private var importing = false
    @State private var playing = false
    @State private var confirmRetry = false
    @State private var upload: PendingUpload?
    private struct PendingUpload { let name: String; let mime: String; let data: Data; let key = UUID().uuidString }

    var body: some View {
        CampusSecondaryScaffold(title: scope == .personal ? "自主选题课堂" : "课程课堂") {
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    if model.isLoading && model.status == .null { CampusLoadingState(message: "读取课堂服务…") }
                    if model.status != .null && model.status["enabled"].bool != true {
                        HStack(alignment: .top, spacing: 9) {
                            Image(systemName: "exclamationmark.triangle").foregroundStyle(Color(hex: 0xC25450))
                            VStack(alignment: .leading, spacing: 4) {
                                Text("课堂生成暂不可用").campusFont(.body).fontWeight(.semibold).foregroundStyle(Color(hex: 0x1B2730))
                                Text(model.status["reason"].string ?? model.status["compatibility_reason"].string ?? "请联系服务维护者配置课堂服务。")
                                    .campusFont(.caption).foregroundStyle(.secondary)
                            }
                            Spacer()
                        }
                        .padding(14)
                        .background(Color(hex: 0xF6DAD8), in: RoundedRectangle(cornerRadius: 16))
                    }
                    CampusCard {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("学习内容").campusFont(.subtitle).foregroundStyle(Color(hex: 0x1B2730))
                            CampusTextField(placeholder: scope == .personal ? "想学习什么？" : "本次学习目标（可选）", text: $goal)
                            CampusTextField(placeholder: "当前卡在哪里？（可选）", text: $difficulty)
                            Picker("希望的形式", selection: $mode) {
                                ForEach(Self.modes, id: \.0) { value, label in Text(label).tag(value) }
                            }
                            .tint(Color(hex: 0x285B4B))
                            Stepper("大约 \(minutes) 分钟", value: $minutes, in: 5...180, step: 5).campusFont(.body)
                            Toggle("多一些练习", isOn: $practice).tint(Color(hex: 0x285B4B))
                            if let reason = model.coursePlan["adaptive_reason"].string?.nonEmpty {
                                Text(reason).campusFont(.caption).foregroundStyle(.secondary)
                            }
                            Text(model.coursePlan["intent_note"].string ?? "内容形式是生成意图，实际内容以生成结果为准。")
                                .campusFont(.caption).foregroundStyle(.secondary)
                        }
                    }
                    CampusCard {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("参考资料").campusFont(.subtitle).foregroundStyle(Color(hex: 0x1B2730))
                            ForEach(Array(model.materials.enumerated()), id: \.offset) { _, material in
                                let id = material["id"].text
                                let extracted = (material["extraction_status"].text == "extracted" && (material["text_chars"].int ?? 0) > 0)
                                    || (scope != .personal && material["extraction_status"] == .null && material["title"].string?.nonEmpty != nil)
                                Toggle(isOn: Binding(get: { model.selectedMaterials.contains(id) },
                                                     set: { if $0 { model.selectedMaterials.insert(id) } else { model.selectedMaterials.remove(id) } })) {
                                    VStack(alignment: .leading, spacing: 2) {
                                        Text(material["filename"].string ?? material["title"].string ?? "课程资料")
                                            .campusFont(.body).foregroundStyle(Color(hex: 0x1B2730))
                                        Text(extracted ? "可用于生成" : material["extraction_status"].string ?? "待服务端解析")
                                            .campusFont(.caption).foregroundStyle(.secondary)
                                    }
                                }
                                .tint(Color(hex: 0x285B4B))
                                .disabled(!extracted)
                            }
                            CampusSecondaryButton(title: "上传学习资料", systemImage: "doc.badge.plus", enabled: !model.isWorking) {
                                importing = true
                            }
                            if let upload {
                                Button("重试上传 \(upload.name)") {
                                    Task { if await model.upload(name: upload.name, mime: upload.mime, data: upload.data, key: upload.key) { self.upload = nil } }
                                }
                                .campusFont(.caption).foregroundStyle(Color(hex: 0xE08A4E))
                            }
                            Text("支持 PDF、Word 和文本，每份不超过 2 MiB。上传成功后，还需解析出正文才可用于生成。")
                                .campusFont(.caption).foregroundStyle(.secondary)
                        }
                    }
                    CampusPrimaryButton(title: model.isWorking ? "正在提交…" : "生成互动课堂",
                                        systemImage: "play.rectangle", loading: model.isWorking,
                                        enabled: model.canGenerate && goal.count <= 500 && difficulty.count <= 500
                                            && (scope != .personal || !goal.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)) {
                        Task { await generate() }
                    }
                    if !model.sessionID.isEmpty { sessionSection }
                    if !model.history.isEmpty {
                        CampusCard {
                            VStack(alignment: .leading, spacing: 8) {
                                Text("历史课堂").campusFont(.subtitle).foregroundStyle(Color(hex: 0x1B2730))
                                ForEach(Array(model.history.enumerated()), id: \.offset) { _, item in
                                    Button { Task { await model.selectHistory(item) } } label: {
                                        HStack {
                                            VStack(alignment: .leading, spacing: 3) {
                                                Text(Self.modes.first { $0.0 == item["mode"].text }?.1 ?? "互动课堂")
                                                    .campusFont(.body).foregroundStyle(Color(hex: 0x1B2730))
                                                Text(item["created_at"].text).campusFont(.caption).foregroundStyle(.secondary)
                                            }
                                            Spacer()
                                            Image(systemName: "chevron.right").font(.system(size: 12)).foregroundStyle(.secondary)
                                        }
                                        .padding(.vertical, 6)
                                        .contentShape(Rectangle())
                                    }
                                    .buttonStyle(.plain)
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
        .task { await load() }
        .refreshable { await load() }
        .task(id: model.sessionID) {
            let started = Date()
            while !Task.isCancelled, !model.sessionID.isEmpty, !model.isTerminal, !model.pollingStopped {
                try? await Task.sleep(for: .seconds(model.interval))
                guard !Task.isCancelled else { return }
                if Date().timeIntervalSince(started) > model.maxPollSeconds { model.pollingStopped = true; return }
                if scenePhase == .active { await model.refresh() }
            }
        }
        .fullScreenCover(isPresented: $playing) {
            NavigationStack {
                if let url = ClassroomPlayback.validURL(session: model.session, status: model.status, allowLocalDebug: AppModel.allowsHTTP) {
                    TrustedWebView(url: url, origins: [model.status["embed_origin"].text], onError: { model.error = $0 })
                        .navigationTitle("互动课堂").navigationBarTitleDisplayMode(.inline)
                        .toolbar { ToolbarItem(placement: .cancellationAction) { Button("关闭") { playing = false } } }
                }
            }
        }
        .fileImporter(isPresented: $importing,
                      allowedContentTypes: [.pdf, .plainText, UTType(filenameExtension: "md") ?? .plainText,
                                            UTType(filenameExtension: "docx") ?? .data]) { result in
            do {
                let url = try result.get()
                let granted = url.startAccessingSecurityScopedResource()
                defer { if granted { url.stopAccessingSecurityScopedResource() } }
                let size = try url.resourceValues(forKeys: [.fileSizeKey]).fileSize ?? 0
                guard size <= 2 * 1024 * 1024 else { throw APIError(code: "FILE_TOO_LARGE", message: "资料不能超过 2 MiB。") }
                let file = PendingUpload(name: url.lastPathComponent,
                                         mime: UTType(filenameExtension: url.pathExtension)?.preferredMIMEType ?? "application/octet-stream",
                                         data: try Data(contentsOf: url))
                upload = file
                Task { if await model.upload(name: file.name, mime: file.mime, data: file.data, key: file.key) { upload = nil } }
            } catch { model.error = error.localizedDescription }
        }
        .confirmationDialog("重新提交可能生成新课堂。确认先检查过原任务进度？", isPresented: $confirmRetry, titleVisibility: .visible) {
            Button("确认重新生成") { Task { await generate(retry: true) } }
        }
        .errorAlert(Binding(get: { model.error }, set: { model.error = $0 }))
    }

    private var sessionSection: some View {
        CampusCard {
            VStack(alignment: .leading, spacing: 9) {
                Text("当前课堂").campusFont(.subtitle).foregroundStyle(Color(hex: 0x1B2730))
                LabeledContent("状态", value: model.session["status"].text.localizedStatus).campusFont(.caption)
                if !model.isTerminal {
                    ProgressView(value: Double(model.session["progress"].int ?? 0), total: 100)
                        .tint(Color(hex: 0x285B4B))
                }
                if let message = model.session["message"].string?.nonEmpty {
                    Text(message).campusFont(.caption).foregroundStyle(.secondary)
                }
                if let warning = model.result["materials_warning"].string?.nonEmpty {
                    Text(warning).campusFont(.caption).foregroundStyle(Color(hex: 0xE08A4E))
                }
                if let error = model.session["error"].string?.nonEmpty {
                    Text(error).campusFont(.caption).foregroundStyle(.secondary)
                }
                if ClassroomPlayback.validURL(session: model.session, status: model.status, allowLocalDebug: AppModel.allowsHTTP) != nil {
                    CampusPrimaryButton(title: "开始学习", systemImage: "play.fill") { playing = true }
                } else if model.session["status"].text == "succeeded" {
                    Text(model.session["url_unavailable_reason"].string ?? model.status["browser_embed_reason"].string ?? "课堂已生成，当前没有可安全打开的播放地址。")
                        .campusFont(.caption).foregroundStyle(.secondary)
                }
                HStack(spacing: 10) {
                    Button("刷新进度") { Task { model.pollingStopped = false; await model.refresh() } }
                        .campusFont(.caption).foregroundStyle(Color(hex: 0x285B4B))
                    if case .course = scope, model.session["retryable"].bool == true {
                        Button("重新生成") { confirmRetry = true }
                            .campusFont(.caption).foregroundStyle(Color(hex: 0xE08A4E))
                            .disabled(model.isWorking)
                    }
                }
                if model.pollingStopped {
                    Text("自动检查已暂停，刷新进度可读取最新状态。").campusFont(.caption).foregroundStyle(.secondary)
                }
            }
        }
    }

    private func load() async {
        await model.load(client: app.client, scope: scope, account: app.serverURL + "|" + (app.session?.user.id ?? ""))
    }
    private func generate(retry: Bool = false) async {
        await model.generate(goal: goal, difficulty: difficulty, minutes: minutes, mode: mode, practice: practice, retry: retry)
    }
    private static let modes = [("adaptive", "智能推荐"), ("explain", "讲解"), ("quiz", "测验"), ("simulation", "模拟"),
                                ("visualization", "可视化"), ("mindmap", "思维导图"), ("coding", "编程练习"),
                                ("pbl", "项目学习"), ("review", "复习")]
}
