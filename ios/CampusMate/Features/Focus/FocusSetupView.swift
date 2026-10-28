import SwiftUI
import CampusCore

// MARK: - Hall

/// Port of the focus hall: a study-desk backdrop and a paper "study room"
/// card that decides goal, duration and mode before entering the scene.
struct FocusSetupView: View {
    @Environment(AppModel.self) private var app
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
        .overlay(alignment: .top) {
            HStack(spacing: 0) {
                CampusBackButton(tint: .white, onDarkBackground: true) { dismiss() }
                    .padding(.leading, 16)
                Spacer(minLength: 0)
            }
            .frame(maxWidth: 760)
            .frame(maxWidth: .infinity)
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
                        if option.value == "SMART_GUARD" { Text("暂未接入").font(.caption2).foregroundStyle(copper) }
                        if selected { Text("✓").font(.system(size: 15, weight: .bold)).foregroundStyle(copper) }
                    }
                    .padding(.horizontal, 12).padding(.vertical, 12)
                    .background(selected ? Color(hex: 0xF0DFC1) : Color(hex: 0xFFFCF4),
                                in: RoundedRectangle(cornerRadius: 13))
                    .overlay(RoundedRectangle(cornerRadius: 13).strokeBorder(selected ? copper : line, lineWidth: 1))
                }
                .buttonStyle(.plain)
                .disabled(option.value == "SMART_GUARD")
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

    private func loadStats() async {
        guard let value = try? await app.client.request(path: "study/sessions", query: ["page": "1", "page_size": "100"]) else { return }
        let sessions = value.items.compactMap { try? StudySession(json: $0) }
        stats = FocusStats(sessions: sessions)
    }

    private static let modes: [(value: String, title: String, description: String)] = [
        ("QUIET", "安静专注", "只保留倒计时，减少打扰"),
        ("AI_COMPANION", "AI 陪伴", "AI 语音陪你完成专注"),
        ("SMART_GUARD", "摄像头＋语音", "iOS 摄像头模型尚未接入；当前可使用安静专注和 AI 语音"),
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
