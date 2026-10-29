import SwiftUI
import CampusCore

// MARK: - Session

/// Immersive focus room with the three project scenes, the robot companion,
/// ambient sound and the existing realtime voice client.
struct FocusSessionView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @Environment(\.scenePhase) private var scenePhase
    let model: FocusModel

    @AppStorage("campus.focus.scene") private var scene = "rainy_room"
    @AppStorage("campus.focus.ambient") private var ambientEnabled = false
    @State private var showingFinish = false
    @State private var voice = RealtimeVoiceEngine()
    @State private var wantsVoice = false
    @State private var ambient = AmbientAudio()

    private let scenes: [(id: String, title: String)] = [
        ("rainy_room", "雨夜自习室"), ("quiet_library", "静谧图书馆"), ("forest_morning", "林间晨读"),
    ]

    var body: some View {
        ZStack {
            CampusSceneBackground(name: "focus_scene_\(scene)")
            LinearGradient(colors: [Color.black.opacity(0.35), .clear, Color.black.opacity(0.62)],
                           startPoint: .top, endPoint: .bottom)
                .ignoresSafeArea()

            if let session = model.session {
                if session.isActive {
                    GeometryReader { geometry in
                        ScrollView {
                            activeContent(session)
                                .frame(maxWidth: 760)
                                .frame(minHeight: geometry.size.height)
                                .frame(maxWidth: .infinity)
                        }
                        .scrollBounceBehavior(.basedOnSize)
                    }
                }
                else { FocusSummaryView(session: session) { dismiss() } }
            } else {
                ProgressView("读取会话…").tint(.white).foregroundStyle(.white)
            }
        }
        .campusImmersive()
        .sheet(isPresented: $showingFinish) {
            NavigationStack { FocusFinishView(model: model) { voice.stop(); ambient.stop(); wantsVoice = false } }
        }
        .onChange(of: wantsVoice) { _, value in
            if value { Task { await voice.start(client: app.client) } } else { voice.stop() }
        }
        .onChange(of: voice.isConnected) { _, connected in ambient.duck(connected) }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active {
                Task { await model.refresh() }
                syncAmbient()
            } else {
                ambient.pause()
            }
        }
        .onChange(of: ambientEnabled) { _, _ in syncAmbient() }
        .onChange(of: scene) { _, _ in syncAmbient() }
        .onChange(of: model.session?.status) { _, status in
            if status != "active" { voice.stop(); ambient.stop() }
            else {
                syncAmbient()
                if wantsVoice, scenePhase == .active { Task { await voice.start(client: app.client) } }
            }
        }
        .onDisappear { voice.stop(); ambient.stop() }
        .task {
            syncAmbient()
            while !Task.isCancelled {
                try? await Task.sleep(for: .seconds(10))
                if !Task.isCancelled { await model.refresh() }
            }
        }
        .errorAlert(Binding(get: { model.error }, set: { model.error = $0 }))
    }

    private func activeContent(_ session: StudySession) -> some View {
        VStack(spacing: 0) {
            topBar
            Spacer(minLength: 0)
            Image("ai_campus_robot")
                .resizable()
                .scaledToFit()
                .frame(height: 150)
                .shadow(color: .black.opacity(0.35), radius: 18, y: 8)
                .scaleEffect(voice.isConnected ? 1.02 : 1)
                .animation(app.reduceMotion ? nil : .easeInOut(duration: 2.4).repeatForever(autoreverses: true), value: voice.isConnected)
            TimelineView(.periodic(from: .now, by: 1)) { context in
                let elapsed = Int(session.elapsed(at: context.date))
                VStack(spacing: 10) {
                    Text(timeText(elapsed))
                        .font(.system(size: 62, weight: .semibold, design: .rounded))
                        .monospacedDigit()
                        .foregroundStyle(.white)
                        .minimumScaleFactor(0.5)
                    Text(session.isPaused ? "已暂停" : "专注计时")
                        .font(.system(size: 12)).foregroundStyle(.white.opacity(0.8))
                    ZStack(alignment: .leading) {
                        Capsule().fill(Color.white.opacity(0.22)).frame(width: 240, height: 5)
                        Capsule().fill(Color(hex: 0xFFEBCB))
                            .frame(width: 240 * min(1, Double(elapsed) / Double(max(1, session.plannedSeconds))), height: 5)
                    }
                    Text(session.goal.nonEmpty ?? "专注当下")
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundStyle(.white.opacity(0.92))
                        .multilineTextAlignment(.center)
                        .lineLimit(2)
                        .padding(.horizontal, 32)
                }
            }
            Spacer(minLength: 0)
            controlPanel(session)
        }
        .padding(.top, 8)
    }

    private var topBar: some View {
        HStack(spacing: 10) {
            CampusBackButton(tint: .white, onDarkBackground: true) { dismiss() }
            Spacer()
            Menu {
                ForEach(scenes, id: \.id) { item in
                    Button {
                        scene = item.id
                        CampusHaptics.selection()
                    } label: { Label(item.title, systemImage: scene == item.id ? "checkmark" : "leaf") }
                }
            } label: {
                Image(systemName: "leaf.fill")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(.white)
                    .frame(width: 44, height: 44)
                    .background(.ultraThinMaterial, in: Circle())
            }
            .accessibilityLabel("切换专注场景")
            Button {
                ambientEnabled.toggle()
                CampusHaptics.selection()
            } label: {
                Image(systemName: ambientEnabled ? "speaker.wave.2.fill" : "speaker.slash.fill")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(.white)
                    .frame(width: 44, height: 44)
                    .background(.ultraThinMaterial, in: Circle())
            }
            .accessibilityLabel(ambientEnabled ? "关闭环境声" : "开启环境声")
        }
        .padding(.horizontal, 16)
    }

    private func controlPanel(_ session: StudySession) -> some View {
        VStack(spacing: 12) {
            if session.experienceMode != "QUIET" {
                HStack(spacing: 8) {
                    Image(systemName: "waveform").font(.system(size: 13))
                    Text(voice.statusText).font(.system(size: 12))
                    Spacer()
                    Toggle("语音陪伴", isOn: $wantsVoice).labelsHidden().tint(Color(hex: 0xE08A4E))
                        .disabled(session.isPaused)
                }
                .foregroundStyle(.white.opacity(0.9))
                if !voice.transcript.assistantText.isEmpty || !voice.transcript.userText.isEmpty {
                    VStack(alignment: .leading, spacing: 4) {
                        if !voice.transcript.userText.isEmpty {
                            Text("你：" + voice.transcript.userText).font(.system(size: 12)).foregroundStyle(.white.opacity(0.7)).lineLimit(2)
                        }
                        if !voice.transcript.assistantText.isEmpty {
                            Text("CampusMate：" + voice.transcript.assistantText)
                                .font(.system(size: 13)).foregroundStyle(.white).lineLimit(4)
                        }
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                }
                if let error = voice.error {
                    Text(error).font(.system(size: 11)).foregroundStyle(.white.opacity(0.7))
                }
            }
            HStack(spacing: 12) {
                Button {
                    Task { await model.togglePause(); CampusHaptics.tap() }
                } label: {
                    Label(session.isPaused ? "继续" : "暂停",
                          systemImage: session.isPaused ? "play.fill" : "pause.fill")
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundStyle(Color(hex: 0x203A31))
                        .frame(maxWidth: .infinity).frame(height: 48)
                        .background(Color(hex: 0xFFEBCB), in: RoundedRectangle(cornerRadius: 14))
                }
                .disabled(model.isWorking)
                Button { showingFinish = true } label: {
                    Label("结束", systemImage: "stop.fill")
                        .font(.system(size: 15, weight: .semibold))
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity).frame(height: 48)
                        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 14))
                }
                .disabled(model.isWorking)
            }
        }
        .padding(18)
        .background(.ultraThinMaterial, in: UnevenRoundedRectangle(topLeadingRadius: 26, topTrailingRadius: 26))
        .overlay(alignment: .top) {
            Rectangle().fill(Color.white.opacity(0.25)).frame(height: 0.5)
        }
    }

    private func timeText(_ seconds: Int) -> String {
        String(format: "%02d:%02d", seconds / 60, seconds % 60)
    }

    private func syncAmbient() {
        guard ambientEnabled, scenePhase == .active, model.session?.status == "active" else { ambient.stop(); return }
        ambient.play(scene: scene)
        ambient.duck(voice.isConnected)
    }
}

struct FocusFinishView: View {
    @Environment(\.dismiss) private var dismiss
    let model: FocusModel
    let onFinished: () -> Void
    @State private var report = ""
    @State private var tags: Set<String> = []
    @State private var completeStep = false
    private let choices = ["有收获", "专注", "需要复习", "有点疲惫", "有新问题"]

    var body: some View {
        CampusSecondaryScaffold(title: "结束专注") {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    Text("这次学习感觉如何？（可选）").campusFont(.body).fontWeight(.semibold).foregroundStyle(CampusJournal.ink)
                    TextField("写下收获或下次要做的事", text: $report, axis: .vertical)
                        .lineLimit(4...8)
                        .font(.system(size: 14))
                        .padding(12)
                        .background(Color(hex: 0xFFFBF2), in: RoundedRectangle(cornerRadius: 10))
                    Text("学习感受").campusFont(.body).fontWeight(.semibold).foregroundStyle(CampusJournal.ink)
                    FlowTags(options: choices, selected: $tags)
                    if model.activeStepNumber != nil {
                        Toggle("这一步已实际完成", isOn: $completeStep).tint(Color(hex: 0xAA7548))
                    }
                    Text("只记录你主动填写的感受，不根据摄像头画面替你填写。")
                        .campusFont(.caption).foregroundStyle(.secondary)
                    CampusPrimaryButton(title: model.isWorking ? "正在保存…" : "结束并保存", loading: model.isWorking,
                                        enabled: report.count <= 2000) {
                        Task {
                            if await model.finish(report: report, tags: Array(tags), completeStep: completeStep) {
                                onFinished(); dismiss()
                            }
                        }
                    }
                }
                .padding(20)
                .frame(maxWidth: 700)
                .frame(maxWidth: .infinity)
            }
        }
        .errorAlert(Binding(get: { model.error }, set: { model.error = $0 }))
    }
}

struct FlowTags: View {
    let options: [String]
    @Binding var selected: Set<String>
    var body: some View {
        LazyVGrid(columns: [GridItem(.adaptive(minimum: 88), spacing: 8)], alignment: .leading, spacing: 8) {
            ForEach(options, id: \.self) { option in
                let active = selected.contains(option)
                Button {
                    if active { selected.remove(option) } else { selected.insert(option) }
                    CampusHaptics.selection()
                } label: {
                    Text(option)
                        .font(.system(size: 12, weight: active ? .semibold : .regular))
                        .foregroundStyle(active ? Color.white : CampusJournal.ink)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, 9)
                        .background(active ? Color(hex: 0xAA7548) : Color(hex: 0xFFFBF2), in: Capsule())
                        .overlay(Capsule().strokeBorder(Color(hex: 0xCFBDA4), lineWidth: 1))
                }
                .buttonStyle(.plain)
            }
        }
    }
}

struct FocusSummaryView: View {
    let session: StudySession
    var onDone: (() -> Void)?
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        CampusSecondaryScaffold(title: "本次专注总结") {
            ScrollView {
                VStack(alignment: .leading, spacing: 14) {
                    HStack(spacing: 8) {
                        Image(systemName: "checkmark.seal.fill").foregroundStyle(Color(hex: 0x4E8C6A))
                        Text("本次专注已保存").campusFont(.body).fontWeight(.semibold).foregroundStyle(CampusJournal.ink)
                    }
                    Text(session.goal.nonEmpty ?? "专注学习")
                        .font(.system(size: 24, weight: .heavy)).foregroundStyle(CampusJournal.ink)
                    Text("专注时长 \(Int(session.elapsed(at: .now)) / 60) 分 \(Int(session.elapsed(at: .now)) % 60) 秒")
                        .campusFont(.body).foregroundStyle(.secondary)
                    if !session.report.isEmpty {
                        Text(session.report).campusFont(.body).foregroundStyle(CampusJournal.ink).textSelection(.enabled)
                    }
                    let tags = session.json["self_report_tags"].items.compactMap(\.string)
                    if !tags.isEmpty {
                        Text(tags.joined(separator: " · ")).campusFont(.caption).foregroundStyle(.secondary)
                    }
                    if let id = session.relatedTaskID, let task = try? TaskItem(json: ["id": .string(id), "title": "关联待办"]) {
                        NavigationLink("查看关联待办") { TaskDetailView(initial: task) }
                            .campusFont(.body).foregroundStyle(Color(hex: 0x285B4B))
                    }
                    CampusPrimaryButton(title: "完成") { if let onDone { onDone() } else { dismiss() } }
                }
                .padding(20)
                .frame(maxWidth: 700)
                .frame(maxWidth: .infinity)
            }
        }
    }
}
