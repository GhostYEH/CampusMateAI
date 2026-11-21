import Foundation
import SwiftUI
import Observation
import CampusCore

/// 生成“课程新一讲”的受理状态。生成、模型推理与服务端鉴权仍走现有服务。
@MainActor
@Observable
final class ClassroomGenerationModel {
    enum Phase: Equatable {
        case idle
        case submitting
        case running(Int)
        case failed(String)
    }

    var prompt = ""
    var mode = "slide"
    private(set) var phase: Phase = .idle
    private(set) var destination: NativeClassroomDestination?

    struct GenerationMode: Identifiable, Hashable {
        let id: String
        let label: String
    }

    static let modes: [GenerationMode] = [
        GenerationMode(id: "slide", label: "讲解"),
        GenerationMode(id: "quiz", label: "练习"),
        GenerationMode(id: "pbl", label: "项目"),
    ]

    @ObservationIgnored private var idempotencyKey = UUID().uuidString
    @ObservationIgnored private var lastPrompt = ""
    @ObservationIgnored private var lastMode = ""

    func resetKeyIfInputChanged() {
        guard prompt != lastPrompt || mode != lastMode else { return }
        lastPrompt = prompt
        lastMode = mode
        idempotencyKey = UUID().uuidString
    }

    func generate(courseID: String, client: APIClient) async {
        resetKeyIfInputChanged()
        let service = NativeClassroomService(client: client)
        phase = .submitting
        destination = nil
        do {
            let handle = try await service.homeGenerate(
                courseID: courseID, prompt: prompt, mode: mode, idempotencyKey: idempotencyKey)
            guard !handle.isLocalTemplate else {
                throw APIError(code: "GENERATION_FALLBACK", message: "模型当前不可用，只返回了模板内容。已停止进入课堂。")
            }
            guard let job = handle.job else {
                if let stageID = handle.stageID {
                    destination = NativeClassroomDestination(
                        courseID: courseID, workspaceID: handle.workspaceID,
                        stageID: stageID, title: "新课堂")
                    phase = .idle
                    return
                }
                throw APIError(code: "GENERATION_EMPTY", message: "服务端没有返回生成任务。")
            }
            phase = .running(job.progress)
            let finished = try await service.waitForJob(courseID: courseID, jobID: job.id) { latest in
                Task { @MainActor in
                    if case .running = self.phase { self.phase = .running(latest.progress) }
                }
            }
            guard finished.isCompleted else {
                throw APIError(code: finished.errorCode ?? "GENERATION_FAILED",
                               message: "生成没有完成，可以重新尝试。")
            }
            let stageID: String
            if let stage = handle.stageID {
                stageID = stage
            } else {
                let stages = try await service.stages(courseID: courseID, workspaceID: handle.workspaceID)
                guard let newest = stages.first else {
                    throw APIError(code: "GENERATION_NO_STAGE", message: "生成完成，但没有找到新的课堂。")
                }
                stageID = newest.id
            }
            let stageTitle = (try? await service.stage(
                courseID: courseID, workspaceID: handle.workspaceID, stageID: stageID).title) ?? "新课堂"
            destination = NativeClassroomDestination(
                courseID: courseID, workspaceID: handle.workspaceID,
                stageID: stageID, title: stageTitle)
            phase = .idle
        } catch is CancellationError {
            phase = .idle
        } catch {
            phase = .failed(ClassroomNativePresentation.message(for: error, fallback: "生成失败，请稍后再试。"))
        }
    }

    func clearDestination() { destination = nil }
}

/// 课程里的原生课堂入口：列出工作台与舞台、显示续读进度、生成新一讲。
/// 旧的经典网页课堂入口在同一个页面保留，互不影响。
struct ClassroomWorkspacesView: View {
    @Environment(AppModel.self) private var app
    private var palette: CampusPalette { .classroom }

    let courseID: String
    var courseName: String = "课程"

    @State private var workspaces: [ClassroomWorkspace] = []
    @State private var stages: [String: [ClassroomStageSummary]] = [:]
    @State private var progress: [String: ClassroomProgress] = [:]
    @State private var loadToken = UUID()
    @State private var error: String?
    @State private var didLoad = false
    @State private var presenting: NativeClassroomDestination?
    @State private var generation = ClassroomGenerationModel()

    private var accountKey: String { app.serverURL + "|" + (app.session?.user.id ?? "") }
    private var accountScope: String { accountKey }

    private var generationBusy: Bool {
        switch generation.phase {
        case .submitting, .running: true
        default: false
        }
    }

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                intro
                if !didLoad {
                    CampusLoadingState(message: "正在读取课程工作台…")
                } else if let error {
                    CampusErrorState(message: error, retry: { Task { await load() } })
                } else {
                    if workspaces.isEmpty {
                        CampusEmptyState(title: "还没有原生课堂",
                                         message: "这节课程尚未生成工作台。可以在下方生成第一讲，或继续使用经典课堂。",
                                         systemImage: "rectangle.on.rectangle")
                    }
                    ForEach(workspaces) { workspaceCard($0) }
                }
                generatorCard
                legacyCard
            }
            .padding(.horizontal, 16)
            .padding(.vertical, 12)
        }
        .background(CampusAmbientBackground())
        .campusPalette(.classroom)
        .navigationTitle("原生课堂")
        .navigationBarTitleDisplayMode(.inline)
        .task { await load() }
        .refreshable { await load() }
        .onChange(of: app.session?.user.id) { _, _ in
            workspaces = []
            stages = [:]
            progress = [:]
            didLoad = false
            Task { await load() }
        }
        .fullScreenCover(item: $presenting) { destination in
            NativeClassroomView(courseID: destination.courseID, workspaceID: destination.workspaceID,
                                stageID: destination.stageID, title: destination.title,
                                client: app.client, accountKey: accountKey)
                .environment(app)
                .campusPalette(.classroom)
        }
    }

    private var intro: some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(courseName)
                .campusFont(.headline)
                .foregroundStyle(palette.textPrimary)
                .lineLimit(2)
            Text("课件、讲解、练习和进度都在 App 内处理；生成仍由课程服务提供。")
                .campusFont(.caption)
                .foregroundStyle(palette.muted)
        }
    }

    private func workspaceCard(_ workspace: ClassroomWorkspace) -> some View {
        CampusCard {
            VStack(alignment: .leading, spacing: 10) {
                HStack(alignment: .firstTextBaseline) {
                    Text(workspace.name).campusFont(.subtitle).foregroundStyle(palette.textPrimary)
                    Spacer(minLength: 8)
                    Text("修订 \(workspace.revision)").campusFont(.micro).foregroundStyle(palette.muted)
                }
                if !workspace.detail.isEmpty {
                    Text(workspace.detail).campusFont(.caption).foregroundStyle(palette.muted).lineLimit(3)
                }
                let list = stages[workspace.id] ?? []
                if list.isEmpty {
                    Text("这个工作台还没有可播放的舞台。").campusFont(.caption).foregroundStyle(palette.muted)
                } else {
                    ForEach(list) { stage in stageRow(stage) }
                }
            }
        }
    }

    private func stageRow(_ stage: ClassroomStageSummary) -> some View {
        Button {
            presenting = NativeClassroomDestination(courseID: courseID, workspaceID: stage.workspaceID,
                                                    stageID: stage.id, title: stage.title)
        } label: {
            HStack(alignment: .top, spacing: 10) {
                Image(systemName: "play.rectangle")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(palette.primary)
                    .frame(width: 26, height: 26)
                    .background(RoundedRectangle(cornerRadius: 8).fill(palette.primarySoft))
                VStack(alignment: .leading, spacing: 3) {
                    Text(stage.title)
                        .campusFont(.body)
                        .foregroundStyle(palette.textPrimary)
                        .lineLimit(2)
                    HStack(spacing: 6) {
                        Text("第 \(stage.revision) 版").campusFont(.micro).foregroundStyle(palette.muted)
                        if let saved = progress[progressKey(workspaceID: stage.workspaceID, stageID: stage.id)] {
                            Text("上次到第 \(saved.sceneIndex + 1) 页")
                                .campusFont(.micro)
                                .foregroundStyle(palette.primary)
                            Text("已访问 \(saved.visitedPageCount) 页")
                                .campusFont(.micro)
                                .foregroundStyle(palette.muted)
                        } else {
                            Text("未开始").campusFont(.micro).foregroundStyle(palette.muted)
                        }
                    }
                }
                Spacer(minLength: 0)
                Image(systemName: "chevron.right").font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(palette.muted)
            }
            .padding(10)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: 11).fill(palette.background.opacity(0.62)))
        }
        .buttonStyle(.plain)
        .accessibilityLabel("打开\(stage.title)")
    }

    private var generatorCard: some View {
        CampusCard {
            VStack(alignment: .leading, spacing: 10) {
                HStack(spacing: 8) {
                    Image(systemName: "sparkles").foregroundStyle(palette.accent)
                    Text("生成新的一讲").campusFont(.subtitle).foregroundStyle(palette.textPrimary)
                }
                TextField("这节想学什么？例如：用图像理解光合作用", text: Binding(
                    get: { generation.prompt },
                    set: { generation.prompt = $0 }
                ), axis: .vertical)
                .lineLimit(2...4)
                .campusFont(.body)
                .padding(10)
                .background(RoundedRectangle(cornerRadius: 10).fill(palette.background))
                .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(palette.line.opacity(0.6), lineWidth: 1))

                Picker("形式", selection: Binding(
                    get: { generation.mode },
                    set: { generation.mode = $0 }
                )) {
                    ForEach(ClassroomGenerationModel.modes) { item in
                        Text(item.label).tag(item.id)
                    }
                }
                .pickerStyle(.segmented)

                switch generation.phase {
                case .idle:
                    EmptyView()
                case .submitting:
                    generationState("正在提交…", progress: nil)
                case .running(let progress):
                    generationState("正在生成课堂 \(progress)%", progress: Double(progress) / 100)
                case .failed(let message):
                    Text(message).campusFont(.caption).foregroundStyle(palette.dangerText)
                }

                CampusPrimaryButton(
                    title: "生成并进入课堂",
                    systemImage: "wand.and.stars",
                    loading: generation.phase == .submitting,
                    enabled: !generationBusy && !generation.prompt.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty
                ) {
                    Task {
                        await generation.generate(courseID: courseID, client: app.client)
                        if let destination = generation.destination {
                            presenting = destination
                            generation.clearDestination()
                        }
                    }
                }
                Text("生成使用课程服务，失败不会替换已有课堂；同一主题重复提交会复用服务端的生成任务。")
                    .campusFont(.micro)
                    .foregroundStyle(palette.muted)
            }
        }
    }

    private func generationState(_ text: String, progress: Double?) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 8) {
                ProgressView().controlSize(.small)
                Text(text).campusFont(.caption).foregroundStyle(palette.muted)
            }
            if let progress {
                ProgressView(value: progress).tint(palette.accent)
            }
        }
    }

    private var legacyCard: some View {
        NavigationLink {
            ClassicClassroomView(scope: .course(courseID))
        } label: {
            HStack(spacing: 10) {
                Image(systemName: "rectangle.on.rectangle.badge.play")
                    .foregroundStyle(palette.primary)
                VStack(alignment: .leading, spacing: 3) {
                    Text("经典网页课堂").campusFont(.body).foregroundStyle(palette.textPrimary)
                    Text("保留原入口、原进度和旧课件；原生播放不和它共享状态。")
                        .campusFont(.micro).foregroundStyle(palette.muted)
                }
                Spacer(minLength: 0)
                Image(systemName: "chevron.right").font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(palette.muted)
            }
            .padding(14)
            .background(RoundedRectangle(cornerRadius: 14).fill(palette.surface.opacity(0.9)))
            .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(palette.line.opacity(0.6), lineWidth: 1))
        }
        .buttonStyle(.plain)
    }

    private func load() async {
        let token = UUID()
        loadToken = token
        error = nil
        do {
            let service = NativeClassroomService(client: app.client)
            let list = try await service.workspaces(courseID: courseID)
            guard loadToken == token else { return }
            workspaces = list
            var stageMap: [String: [ClassroomStageSummary]] = [:]
            for workspace in list {
                let stages = try await service.stages(courseID: courseID, workspaceID: workspace.id)
                guard loadToken == token else { return }
                stageMap[workspace.id] = stages
            }
            stages = stageMap
            await loadProgress(token: token)
            guard loadToken == token else { return }
            didLoad = true
        } catch {
            guard loadToken == token else { return }
            didLoad = true
            error = ClassroomNativePresentation.message(for: error, fallback: "工作台读取失败。")
        }
    }

    private func progressKey(workspaceID: String, stageID: String) -> String {
        "\(workspaceID)|\(stageID)"
    }

    private func loadProgress(token: UUID) async {
        var values: [String: ClassroomProgress] = [:]
        for (workspaceID, list) in stages {
            for stage in list {
                let scope = "\(accountScope)|classroom|\(courseID)|\(workspaceID)|\(stage.id)"
                let saved: ClassroomProgress? = await AccountCache.shared.load(
                    ClassroomProgress.self, scope: scope, key: "progress.json")
                guard loadToken == token else { return }
                if let saved { values[progressKey(workspaceID: workspaceID, stageID: stage.id)] = saved }
            }
        }
        guard loadToken == token else { return }
        progress = values
    }
}

/// 首页“原生课堂”入口先选课程，再进入课程工作台。
struct NativeClassroomCoursePickerView: View {
    @Environment(AppModel.self) private var app
    private var palette: CampusPalette { .classroom }
    @State private var courses: [JSONValue] = []
    @State private var loadToken = UUID()
    @State private var didLoad = false
    @State private var error: String?

    var body: some View {
        List {
            if !didLoad {
                CampusLoadingState(message: "正在读取课程…")
            } else if let error {
                CampusErrorState(message: error, retry: { Task { await load() } })
            } else if courses.isEmpty {
                CampusEmptyState(title: "还没有课程", message: "先在课程页添加课程，再进入原生课堂。", systemImage: "books.vertical")
            } else {
                ForEach(Array(courses.enumerated()), id: \.offset) { _, course in
                    if let id = course["id"].string?.nonEmpty {
                        NavigationLink {
                            ClassroomWorkspacesView(courseID: id, courseName: course.displayTitle)
                        } label: {
                            VStack(alignment: .leading, spacing: 4) {
                                Text(course.displayTitle).campusFont(.body).foregroundStyle(palette.textPrimary)
                                if let teacher = course["teacher_name"].string?.nonEmpty {
                                    Text(teacher).campusFont(.caption).foregroundStyle(palette.muted)
                                }
                            }
                            .padding(.vertical, 3)
                        }
                    }
                }
            }
        }
        .navigationTitle("原生课堂")
        .navigationBarTitleDisplayMode(.inline)
        .campusPalette(.classroom)
        .task { await load() }
        .refreshable { await load() }
        .onChange(of: app.session?.user.id) { _, _ in
            courses = []
            didLoad = false
            Task { await load() }
        }
    }

    private func load() async {
        let token = UUID()
        loadToken = token
        error = nil
        do {
            let page = try await LearningService(client: app.client).courses()
            guard loadToken == token else { return }
            courses = page.items
            didLoad = true
        } catch {
            guard loadToken == token else { return }
            didLoad = true
            error = ClassroomNativePresentation.message(for: error, fallback: "课程读取失败。")
        }
    }
}
