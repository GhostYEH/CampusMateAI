import SwiftUI
import CampusCore

// MARK: - Hall

/// Port of the focus hall: a study-desk backdrop and a paper "study room"
/// card that decides goal, duration and mode before entering the scene.
struct FocusSetupView: View {
    @Environment(AppModel.self) private var app
    @Environment(CampusRouter.self) private var router
    @Environment(\.dismiss) private var dismiss
    var initialGoal = ""
    var relatedTaskID: String?
    @State private var model = FocusModel()
    @State private var goal = ""
    @State private var minutes = 25
    @State private var mode = "QUIET"
    @State private var showingSession = false
    @State private var customMinutes = ""
    @State private var showCustom = false
    @State private var stats: FocusStats = .empty
    @State private var loadError: String?

    private let ink = Color(hex: 0x203A31)
    private let paper = Color(hex: 0xF8F3E8)
    private let paperSoft = Color(hex: 0xEEEDE2)
    private let line = Color(hex: 0xD5D2C3)
    private let copper = Color(hex: 0xAA7548)
    private let wood = Color(hex: 0x9C633E)

    private var activeSession: StudySession? {
        guard let session = model.session, session.isActive else { return nil }
        return session
    }

    var body: some View {
        ZStack {
            CampusSceneBackground(name: "focus_study_desk_twilight")
            LinearGradient(stops: [
                .init(color: Color(hex: 0x101F22, opacity: 0.60), location: 0),
                .init(color: Color(hex: 0x0E211C, opacity: 0.20), location: 0.20),
                .init(color: .clear, location: 0.72),
                .init(color: Color(hex: 0x10181A, opacity: 0.33), location: 1),
            ], startPoint: .top, endPoint: .bottom)
                .ignoresSafeArea()

            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    header
                    if let loadError {
                        HStack(spacing: 8) {
                            Image(systemName: "icloud.slash").foregroundStyle(.white)
                            Text(loadError).font(.system(size: 12)).foregroundStyle(.white)
                            Spacer()
                        }
                        .padding(12)
                        .background(Color(hex: 0x8E3430, opacity: 0.6), in: RoundedRectangle(cornerRadius: 16))
                    }
                    if let session = activeSession { recoveryCard(session) }
                    studyCard
                    statsStrip
                    historyLink
                }
                .padding(.horizontal, 16)
                .padding(.top, 28)
                .padding(.bottom, 34)
                .frame(maxWidth: 760)
                .frame(maxWidth: .infinity)
            }
        }
        .overlay(alignment: .topLeading) {
            CampusBackButton(tint: .white, onDarkBackground: true) { pop() }
                .padding(.leading, 16)
                .padding(.top, 8)
        }
        .toolbar(.hidden, for: .navigationBar)
        .task {
            if !initialGoal.isEmpty, goal.isEmpty { goal = initialGoal }
            await model.bootstrap(client: app.client, scope: app.serverURL + "|" + (app.session?.user.id ?? "") + "|focus")
            await loadStats()
            if model.session?.isActive == true { showingSession = true }
        }
        .fullScreenCover(isPresented: $showingSession, onDismiss: { Task { await model.refresh(); await loadStats() } }) {
            FocusSessionView(model: model)
        }
        .sheet(isPresented: $showCustom) { customSheet.presentationDetents([.height(260)]) }
        .errorAlert(Binding(get: { model.error }, set: { model.error = $0 }))
    }

    private var header: some View {
        HStack(spacing: 12) {
            Color.clear.frame(width: CampusMetric.backButton, height: CampusMetric.backButton)
            VStack(alignment: .leading, spacing: 2) {
                Text("自习室").font(.system(size: 23, weight: .bold)).foregroundStyle(.white)
                Text("选好节奏，再进入专注空间").font(.system(size: 12)).foregroundStyle(.white.opacity(0.8))
            }
            Spacer()
        }
    }

    private func recoveryCard(_ session: StudySession) -> some View {
        Button { showingSession = true } label: {
            HStack(spacing: 12) {
                Image(systemName: session.isPaused ? "pause.circle.fill" : "timer")
                    .font(.system(size: 22)).foregroundStyle(wood)
                VStack(alignment: .leading, spacing: 3) {
                    Text("有一场专注还在进行").font(.system(size: 14, weight: .bold)).foregroundStyle(ink)
                    Text(session.goal.nonEmpty ?? "专注学习").font(.system(size: 12)).foregroundStyle(Color(hex: 0x5D7066)).lineLimit(1)
                }
                Spacer()
                Text("继续").font(.system(size: 13, weight: .bold)).foregroundStyle(wood)
            }
            .padding(14)
            .background(paper, in: RoundedRectangle(cornerRadius: 18, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 18).strokeBorder(Color(hex: 0xBD9B72), lineWidth: 1))
        }
        .buttonStyle(CampusPressStyle())
    }

    private var studyCard: some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack {
                Text("CAMPUSMATE  /  STUDY ROOM").font(.system(size: 10, weight: .bold)).tracking(1).foregroundStyle(ink)
                Spacer()
                Text("✦  01").font(.system(size: 12, weight: .bold)).foregroundStyle(copper)
            }
            Spacer().frame(height: 8)
            Rectangle().fill(copper.opacity(0.52)).frame(height: 1)
            Spacer().frame(height: 9)
            Text("从现在开始，专注一件事").font(.system(size: 22, weight: .bold)).foregroundStyle(ink)
            if initialGoal.isEmpty {
                Text("进入后可以切换雨夜、图书馆与林间场景")
                    .font(.system(size: 13)).foregroundStyle(Color(hex: 0x5D7066))
            } else {
                Text(initialGoal).font(.system(size: 14)).foregroundStyle(Color(hex: 0x5D7066)).lineLimit(2)
            }
            Spacer().frame(height: 18)
            Text("这次准备完成什么？").font(.system(size: 15, weight: .semibold)).foregroundStyle(ink)
            Spacer().frame(height: 8)
            if initialGoal.isEmpty {
                TextField("", text: $goal, prompt: Text("例如：做完两道习题（可以跳过）").foregroundStyle(Color(hex: 0x8A9A90)))
                    .font(.system(size: 14))
                    .foregroundStyle(ink)
                    .padding(.horizontal, 13).padding(.vertical, 12)
                    .background(paper, in: RoundedRectangle(cornerRadius: 16))
                    .overlay(RoundedRectangle(cornerRadius: 16).strokeBorder(line, lineWidth: 1))
                    .accessibilityIdentifier("focus.goal")
            } else {
                Text(initialGoal).font(.system(size: 15, weight: .medium)).foregroundStyle(copper)
            }
            Spacer().frame(height: 19)
            Rectangle().fill(line).frame(height: 1)
            Spacer().frame(height: 16)
            Text("01  专注时长").font(.system(size: 13, weight: .bold)).foregroundStyle(ink)
            Spacer().frame(height: 8)
            HStack(spacing: 6) {
                ForEach([25, 45, 60], id: \.self) { value in
                    chip("\(value) 分钟", selected: minutes == value) { minutes = value }
                }
                chip(minutes != 25 && minutes != 45 && minutes != 60 ? "\(minutes) 分" : "自定义",
                     selected: minutes != 25 && minutes != 45 && minutes != 60) {
                    customMinutes = String(minutes); showCustom = true
                }
            }
            Spacer().frame(height: 15)
            Rectangle().fill(line).frame(height: 1)
            Spacer().frame(height: 16)
            Text("02  专注方式").font(.system(size: 13, weight: .bold)).foregroundStyle(ink)
            Spacer().frame(height: 8)
            ForEach(Self.modes, id: \.value) { option in
                let selected = mode == option.value
                Button {
                    mode = option.value
                    CampusHaptics.selection()
                } label: {
                    HStack(spacing: 9) {
                        Circle().fill(selected ? copper : Color(hex: 0xAEBBB0)).frame(width: 8, height: 8)
                        Text(option.title).font(.system(size: 13, weight: selected ? .bold : .regular)).foregroundStyle(ink)
                        Spacer()
                        if selected { Text("✓").font(.system(size: 15, weight: .bold)).foregroundStyle(copper) }
                    }
                    .padding(.horizontal, 12).padding(.vertical, 12)
                    .background(selected ? Color(hex: 0xF0DFC1) : Color(hex: 0xFFFCF4),
                                in: RoundedRectangle(cornerRadius: 13))
                    .overlay(RoundedRectangle(cornerRadius: 13).strokeBorder(selected ? copper : line, lineWidth: 1))
                }
                .buttonStyle(.plain)
                .padding(.bottom, 6)
            }
            Text(Self.modes.first { $0.value == mode }?.description ?? "")
                .font(.system(size: 12)).lineSpacing(4).foregroundStyle(Color(hex: 0x5D7066))
                .padding(.leading, 16).padding(.bottom, 15)
            Button {
                start()
            } label: {
                HStack(spacing: 6) {
                    if model.isWorking || model.isLoading {
                        ProgressView().controlSize(.small).tint(wood)
                    } else {
                        Image(systemName: "play.fill").font(.system(size: 15))
                    }
                    Text(model.isWorking ? "正在准备…" : model.session?.isActive == true ? "返回专注" : "开始专注")
                        .font(.system(size: 15, weight: .bold))
                }
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity)
                .frame(height: 52)
                .background(wood, in: RoundedRectangle(cornerRadius: 15, style: .continuous))
            }
            .buttonStyle(CampusPressStyle())
            .disabled(model.isWorking || model.isLoading)
            .accessibilityLabel("开始专注")
        }
        .padding(.horizontal, 21)
        .padding(.vertical, 20)
        .background {
            ZStack {
                paper
                Image("focus_study_paper_texture")
                    .resizable()
                    .scaledToFill()
                    .opacity(0.55)
                    .clipped()
                JournalGrain(spacing: 26, dotOpacity: 0.04)
            }
        }
        .clipShape(RoundedRectangle(cornerRadius: 26, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 26).strokeBorder(Color(hex: 0xC7B79A), lineWidth: 1))
        .shadow(color: .black.opacity(0.3), radius: 14, y: 6)
    }

    private func chip(_ title: String, selected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(ink)
                .lineLimit(1)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 11)
                .background(selected ? Color(hex: 0xF0DFC1) : paperSoft, in: Capsule())
                .overlay(Capsule().strokeBorder(selected ? copper : line, lineWidth: 1))
        }
        .buttonStyle(.plain)
    }

    private var statsStrip: some View {
        HStack(spacing: 9) {
            Text("今日\n学习").font(.system(size: 12, weight: .bold)).lineSpacing(3).foregroundStyle(ink)
            Rectangle().fill(Color(hex: 0xAA7548, opacity: 0.4)).frame(width: 1, height: 35)
            stat(stats.minutes, "分钟", "专注")
            stat(stats.streak, "天", "连续")
            stat(stats.count, "次", "完成")
        }
        .padding(.horizontal, 13)
        .padding(.vertical, 10)
        .background(Color(hex: 0xF0E2CA), in: UnevenRoundedRectangle(topLeadingRadius: 5, bottomLeadingRadius: 5, bottomTrailingRadius: 5, topTrailingRadius: 17))
        .overlay(UnevenRoundedRectangle(topLeadingRadius: 5, bottomLeadingRadius: 5, bottomTrailingRadius: 5, topTrailingRadius: 17)
            .strokeBorder(Color(hex: 0xBD9B72), lineWidth: 1))
    }

    private func stat(_ value: String, _ unit: String, _ label: String) -> some View {
        VStack(spacing: 1) {
            HStack(alignment: .firstTextBaseline, spacing: 2) {
                Text(value).font(.system(size: 18, weight: .bold)).foregroundStyle(ink)
                Text(unit).font(.system(size: 9)).foregroundStyle(Color(hex: 0x5D7066))
            }
            Text(label).font(.system(size: 10)).foregroundStyle(Color(hex: 0x5D7066))
        }
        .frame(maxWidth: .infinity)
    }

    private var historyLink: some View {
        NavigationLink { FocusHistoryView() } label: {
            HStack {
                Image(systemName: "clock.arrow.circlepath").font(.system(size: 15))
                Text("学习足迹").font(.system(size: 14, weight: .semibold))
                Spacer()
                Image(systemName: "chevron.right").font(.system(size: 12, weight: .semibold))
            }
            .foregroundStyle(.white)
            .padding(14)
            .background(Color.white.opacity(0.14), in: RoundedRectangle(cornerRadius: 16))
        }
        .buttonStyle(.plain)
    }

    private var customSheet: some View {
        VStack(spacing: 14) {
            Text("自定义专注时长").font(.system(size: 19, weight: .bold)).foregroundStyle(ink)
            Text("给这段学习留一段完整的时间").font(.system(size: 13)).foregroundStyle(Color(hex: 0x5D7066))
            TextField("分钟", text: $customMinutes)
                .keyboardType(.numberPad)
                .font(.system(size: 20, weight: .semibold))
                .multilineTextAlignment(.center)
                .padding(12)
                .background(paperSoft, in: RoundedRectangle(cornerRadius: 14))
            Text("可设置 5–240 分钟").font(.system(size: 12)).foregroundStyle(Color(hex: 0x5D7066))
            Button {
                if let value = Int(customMinutes), (5...240).contains(value) {
                    minutes = value; showCustom = false
                }
            } label: {
                Text("确定").font(.system(size: 15, weight: .bold)).foregroundStyle(.white)
                    .frame(maxWidth: .infinity).frame(height: 46)
                    .background(wood, in: RoundedRectangle(cornerRadius: 14))
            }
            .disabled(Int(customMinutes).map { !(5...240).contains($0) } ?? true)
            .opacity(Int(customMinutes).map { (5...240).contains($0) } ?? false ? 1 : 0.5)
        }
        .padding(22)
        .background(paper)
    }

    private func start() {
        if let session = model.session, session.isActive { showingSession = true; return }
        Task {
            let started = await model.start(goal: goal, minutes: minutes, mode: mode, relatedTaskID: relatedTaskID)
            if started { showingSession = true }
        }
    }

    private func pop() {
        if router.path.isEmpty { dismiss() } else { router.pop() }
    }

    private func loadStats() async {
        guard let value = try? await app.client.request(path: "study/sessions", query: ["page": "1", "page_size": "100"]) else { return }
        let sessions = value.items.compactMap { try? StudySession(json: $0) }
        stats = FocusStats(sessions: sessions)
    }

    private static let modes: [(value: String, title: String, description: String)] = [
        ("QUIET", "安静专注", "只保留倒计时，减少打扰"),
        ("AI_COMPANION", "AI 陪伴", "AI 语音陪你完成专注"),
        ("SMART_GUARD", "摄像头＋语音", "AI 语音陪伴，并在本机观察学习状态"),
    ]
}

struct FocusStats {
    var minutes: String = "0"
    var streak: String = "0"
    var count: String = "0"
    static let empty = FocusStats()

    init() { }
    init(sessions: [StudySession]) {
        let calendar = Calendar.current
        let completed = sessions.filter { !$0.isActive }
        let today = completed.filter { calendar.isDateInToday($0.startedAt) }
        minutes = String(today.reduce(0) { $0 + Int($1.elapsed(at: .now) / 60) })
        count = String(today.count)
        var streak = 0
        var day = calendar.startOfDay(for: .now)
        while completed.contains(where: { calendar.isDate($0.startedAt, inSameDayAs: day) }) {
            streak += 1
            guard let previous = calendar.date(byAdding: .day, value: -1, to: day) else { break }
            day = previous
        }
        self.streak = String(streak)
    }
}

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
                if session.isActive { activeContent(session) }
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
                if ambientEnabled { ambient.play(scene: scene) } else { ambient.pause() }
            } else {
                ambient.pause()
            }
        }
        .onChange(of: ambientEnabled) { _, enabled in
            if enabled, scenePhase == .active { ambient.play(scene: scene) } else { ambient.stop() }
        }
        .onChange(of: scene) { _, value in
            if ambientEnabled, scenePhase == .active { ambient.play(scene: value) } else { ambient.stop() }
        }
        .onChange(of: model.session?.status) { _, status in
            if status != "active" { voice.stop(); ambient.stop() }
        }
        .onDisappear { voice.stop(); ambient.stop() }
        .task {
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
                    Toggle("", isOn: $wantsVoice).labelsHidden().tint(Color(hex: 0xE08A4E))
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

struct FocusHistoryView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var resource = PagedResource()

    var body: some View {
        CampusSecondaryScaffold(title: "学习足迹") {
            ScrollView {
                VStack(spacing: 10) {
                    if resource.isLoading && resource.items.isEmpty { CampusLoadingState() }
                    else if let error = resource.error, resource.items.isEmpty { CampusErrorState(message: error) { Task { await load() } } }
                    else if resource.items.isEmpty {
                        CampusEmptyState(title: "还没有专注记录", message: "完成一次专注，记录你的学习足迹。", systemImage: "timer")
                    }
                    ForEach(Array(resource.items.enumerated()), id: \.offset) { _, item in
                        if let session = try? StudySession(json: item) {
                            NavigationLink {
                                if session.isActive { FocusSetupView() }
                                else { FocusSummaryView(session: session) }
                            } label: {
                                HStack(alignment: .top, spacing: 12) {
                                    VStack(spacing: 2) {
                                        Text("\(Int(session.elapsed(at: .now) / 60))")
                                            .font(.system(size: 20, weight: .heavy)).foregroundStyle(Color(hex: 0x285B4B))
                                        Text("分钟").font(.system(size: 9)).foregroundStyle(.secondary)
                                    }
                                    .frame(width: 44)
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text(session.goal.nonEmpty ?? "专注学习").campusFont(.body).fontWeight(.semibold)
                                            .foregroundStyle(CampusJournal.ink).lineLimit(1)
                                        Text(session.startedAt.formatted(.dateTime.month().day().hour().minute()))
                                            .campusFont(.caption).foregroundStyle(.secondary)
                                        if !session.report.isEmpty {
                                            Text(session.report).campusFont(.caption).foregroundStyle(.secondary).lineLimit(2)
                                        }
                                    }
                                    Spacer()
                                }
                                .padding(14)
                                .background(Color(hex: 0xFFFEF8), in: RoundedRectangle(cornerRadius: 16))
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
                .padding(20)
                .frame(maxWidth: 700)
                .frame(maxWidth: .infinity)
            }
        }
        .task { await load() }
    }

    private func load() async { await resource.load(client: app.client, path: "study/sessions") }
}

struct StudyCheckinView: View {
    @Environment(AppModel.self) private var app
    @State private var history = RemoteResource()
    @State private var minutes = 60
    @State private var mood = ""
    @State private var scene = "rain"
    @State private var working = false
    @State private var status: String?
    @State private var error: String?

    var body: some View {
        CampusSecondaryScaffold(title: "每日学习") {
            ScrollView {
                VStack(spacing: 12) {
                    CampusCard {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("每日目标").campusFont(.subtitle).foregroundStyle(CampusJournal.ink)
                            Stepper("每天 \(minutes) 分钟", value: $minutes, in: 15...480, step: 15)
                                .campusFont(.body)
                            CampusSecondaryButton(title: "保存目标") {
                                perform { _ = try await app.client.request(.put, path: "study/goals/daily",
                                                                          body: ["target_minutes": .number(Double(minutes))])
                                    status = "每日目标已保存。" }
                            }
                        }
                    }
                    CampusCard {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("今日签到").campusFont(.subtitle).foregroundStyle(CampusJournal.ink)
                            Picker("心情场景", selection: $scene) {
                                Text("雨").tag("rain"); Text("雪").tag("snow"); Text("云").tag("cloud")
                            }.pickerStyle(.segmented)
                            CampusTextField(placeholder: "今天的心情（可选）", text: $mood)
                            CampusPrimaryButton(title: "签到", loading: working, enabled: mood.count <= 100) {
                                perform {
                                    let result = try await app.client.request(.post, path: "study/checkins",
                                                                             body: ["scene": .string(scene), "mood": mood.nonEmpty.map(JSONValue.string) ?? .null])
                                    status = result["created"].bool == false ? "今天已经签到。" : "签到已保存。"
                                    await history.load(client: app.client, path: "study/checkins")
                                }
                            }
                            if let status { Text(status).campusFont(.caption).foregroundStyle(.secondary) }
                        }
                    }
                    CampusCard {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("签到记录").campusFont(.subtitle).foregroundStyle(CampusJournal.ink)
                            ForEach(Array(history.value.items.enumerated()), id: \.offset) { _, item in
                                HStack {
                                    Text(item["checkin_date"].string ?? item["created_at"].text.prefix(10).description)
                                        .campusFont(.caption).foregroundStyle(CampusJournal.ink)
                                    Spacer()
                                    if let mood = item["mood"].string?.nonEmpty {
                                        Text(mood).campusFont(.caption).foregroundStyle(.secondary)
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
        .task {
            if let result = try? await app.client.request(path: "study/goals/daily") {
                minutes = result["target_minutes"].int ?? 60
            }
            await history.load(client: app.client, path: "study/checkins")
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
