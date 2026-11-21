import SwiftUI
import AVKit
import AVFoundation
import Foundation
import Combine
import CampusCore

/// iOS 原生互动课堂播放器。
///
/// 受管工作台用 `course_id / workspace_id / stage_id`，经典课堂用 `classicScope + session_id`；
/// 两者的数据在模型层投影成同一份播放计划和文档，UI 不维护第二套翻页/测验逻辑。
struct NativeClassroomView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @Environment(\.scenePhase) private var scenePhase
    private var palette: CampusPalette { NativeClassroomAppearance.board }

    private let classicScope: ClassroomScope?
    private let webClassroom: NativeClassroomWebFallback?
    @State private var model: NativeClassroomModel
    @State private var panel: NativeClassroomPanel?
    @State private var showWebCompatibility = false
    @State private var webError: String?
    @State private var sandboxMessage: String?
    @State private var zoom: CGFloat = 1
    @State private var readNotes = false
    @State private var transcriptExpanded = true

    init(courseID: String, workspaceID: String, stageID: String, title: String? = nil,
         client: APIClient, accountKey: String, classicScope: ClassroomScope? = nil,
         webClassroom: NativeClassroomWebFallback? = nil) {
        self.classicScope = classicScope
        self.webClassroom = webClassroom
        _model = State(initialValue: NativeClassroomModel(
            courseID: courseID, workspaceID: workspaceID, stageID: stageID,
            title: title, client: client, accountKey: accountKey, classicScope: classicScope))
    }

    var body: some View {
        GeometryReader { geometry in
            let landscape = geometry.size.width > geometry.size.height
            let split = landscape && geometry.size.width >= 580
            let controlsInHeader = currentSlide != nil && split && geometry.size.width >= 720
            VStack(spacing: 0) {
                header(compact: landscape, controlsInHeader: controlsInHeader)
                Rectangle().fill(palette.line).frame(height: 1)
                content(landscape: landscape, split: split, controlsInHeader: controlsInHeader)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
                if case .ready = model.phase, model.sceneCount > 0 {
                    NativeClassroomPager(index: model.index, count: model.sceneCount, compact: split,
                                         goTo: model.go(to:), onPanel: { panel = $0 })
                }
            }
        }
        .background { NativeClassroomBackdrop() }
        .campusPalette(palette)
        .preferredColorScheme(.dark)
        .accessibilityIdentifier("native.classroom.player")
        .task { await model.open() }
        .onChange(of: scenePhase) { _, phase in model.handleScenePhase(phase == .active) }
        .onChange(of: app.session?.user.id) { _, _ in model.shutdown(); dismiss() }
        .onChange(of: model.currentSceneID) { _, _ in
            readNotes = false
            transcriptExpanded = true
        }
        .onChange(of: lectureActive) { _, active in
            if active { readNotes = false }
        }
        .onDisappear { model.shutdown() }
        .sheet(item: $panel) { tool in classroomPanel(tool) }
        .sheet(isPresented: sequenceVideoPresented) {
            if let video = model.sequenceVideo {
                SequenceVideoSheet(video: video) { model.sequenceVideoSheetClosed() }
            }
        }
        .alert("互动页已阻止跳转", isPresented: Binding(
            get: { sandboxMessage != nil },
            set: { if !$0 { sandboxMessage = nil } }
        )) {
            Button("好", role: .cancel) { sandboxMessage = nil }
        } message: {
            Text(sandboxMessage ?? "")
        }
    }

    // MARK: - Chrome

    private func header(compact: Bool, controlsInHeader: Bool) -> some View {
        HStack(spacing: 0) {
            Button {
                CampusHaptics.tap()
                dismiss()
            } label: {
                Image(systemName: "arrow.left")
                    .font(.system(size: 21, weight: .medium))
                    .foregroundStyle(palette.textPrimary)
                    .frame(width: 48, height: 48)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel("退出课堂")
            .accessibilityIdentifier("native.classroom.close")

            VStack(alignment: .leading, spacing: 2) {
                Text(model.title)
                    .font(.system(size: compact ? 16 : 18, weight: .bold))
                    .foregroundStyle(palette.textPrimary)
                    .lineLimit(compact ? 1 : 2)
                if model.restoredFromCache {
                    Text("正在使用缓存").font(.system(size: 11)).foregroundStyle(palette.accent)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.trailing, 8)
            if controlsInHeader {
                slideToolbar(stretches: false).padding(.trailing, 8)
            }
            if model.sceneCount > 0 {
                let visited = model.sceneInfos.lazy.filter(\.visited).count
                Label("已学 \(visited)/\(model.sceneCount)", systemImage: "star.fill")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(palette.primary)
                    .lineLimit(1)
                    .padding(.horizontal, 9)
                    .padding(.vertical, 7)
                    .background(palette.primarySoft, in: RoundedRectangle(cornerRadius: 10))
                    .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(palette.line))
                    .fixedSize(horizontal: true, vertical: false)
            }
            Button {
                panel = .diagnostics
            } label: {
                Image(systemName: "speedometer")
                    .font(.system(size: 21, weight: .medium))
                    .foregroundStyle(palette.muted)
                    .frame(width: 48, height: 48)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel("查看性能样本")
        }
        .padding(.horizontal, 4)
        .padding(.vertical, compact ? 0 : 5)
        .background { palette.background.opacity(0.96).ignoresSafeArea(edges: .top) }
    }

    @ViewBuilder
    private func content(landscape: Bool, split: Bool, controlsInHeader: Bool) -> some View {
        switch model.phase {
        case .loading:
            VStack(spacing: 10) {
                CampusLoadingState(message: "正在打开课堂…")
                Spacer(minLength: 0)
            }
        case .failed(let message):
            VStack(spacing: 12) {
                CampusErrorState(message: message, retry: { model.retryLoad() })
                Text("也可以退出后从课程页进入网页课堂，原有进度仍保存在那一条路径里。")
                    .campusFont(.micro)
                    .foregroundStyle(palette.muted)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, 28)
                Spacer(minLength: 0)
            }
            .padding(.top, 40)
        case .ready:
            readyContent(landscape: landscape, split: split, controlsInHeader: controlsInHeader)
        }
    }

    private func readyContent(landscape: Bool, split: Bool, controlsInHeader: Bool) -> some View {
        VStack(spacing: 0) {
            if let notice = model.notice {
                banner(text: notice, tone: .warning, dismiss: { model.dismissNotice() })
                    .padding(.horizontal, 12).padding(.top, 6)
            }
            if model.downgradedScenes.contains(model.currentSceneID) {
                banner(text: "这一页在服务端被标记为降级，只保留可读内容。", tone: .neutral, dismiss: nil)
                    .padding(.horizontal, 12).padding(.top, 6)
            }
            if let resumeNote = model.resumeNote {
                banner(text: resumeNote, tone: .neutral, dismiss: nil)
                    .padding(.horizontal, 12).padding(.top, 6)
            }
            Group {
                if let slide = currentSlide {
                    lectureLayout(slide, landscape: landscape, split: split, controlsInHeader: controlsInHeader)
                } else {
                    VStack(spacing: 11) {
                        if model.currentQuizSet == nil { pageHeader(compact: landscape) }
                        sceneBody.frame(maxWidth: .infinity, maxHeight: .infinity)
                        if model.hasSequenceSteps || model.sequence != nil { sequenceBar }
                    }
                    .padding(.horizontal, 14)
                    .padding(.vertical, landscape ? 8 : 12)
                }
            }
            .id(model.currentSceneID)
            .onAppear { model.pageDidRender() }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }

    private func pageHeader(compact: Bool) -> some View {
        let type = model.currentPlaybackScene?.type
        let isProject = type == "pbl"
        let isInteraction = type == "interactive" || type == "simulation"
        return HStack(spacing: 10) {
            Image(systemName: isProject ? "flag.fill" : isInteraction ? "play.fill" : "book.fill")
                .font(.system(size: 20))
                .foregroundStyle(palette.primary)
                .frame(width: compact ? 34 : 42, height: compact ? 34 : 42)
                .background(palette.surface, in: RoundedRectangle(cornerRadius: 12))
                .overlay(RoundedRectangle(cornerRadius: 12).strokeBorder(palette.line))
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 2) {
                Text(isProject ? "项目任务" : isInteraction ? "课堂互动" : "课件")
                    .font(.system(size: 11, weight: .semibold)).foregroundStyle(palette.primary)
                Text(model.currentPlaybackScene?.title ?? "课堂")
                    .font(.system(size: compact ? 17 : 25, weight: .bold))
                    .foregroundStyle(palette.textPrimary)
                    .lineLimit(2)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // MARK: - Lesson stage

    private var currentSlide: ClassroomSlide? {
        guard model.currentRender == .native, case .slide(let slide)? = model.currentContent else { return nil }
        return slide
    }

    private var slideNotes: [ClassroomCanvas.TextElement] {
        currentSlide?.canvas?.elements.compactMap { element in
            guard case .text(let text) = element, !text.plainText.isEmpty,
                  text.plainText != model.currentScene?.title else { return nil }
            return text
        } ?? []
    }

    private var lectureActive: Bool {
        if model.sequence?.active == true || model.narrationIsPaused { return true }
        switch model.narrationPhase {
        case .playing, .generating, .loadingAudio: return true
        default: return false
        }
    }

    private var showingCanvas: Bool { !readNotes || slideNotes.isEmpty || lectureActive }

    private func lectureLayout(_ slide: ClassroomSlide, landscape: Bool, split: Bool,
                               controlsInHeader: Bool) -> some View {
        GeometryReader { geometry in
            if split {
                let room = geometry.size.width - 36
                let toolbarHeight: CGFloat = controlsInHeader ? 0 : 52
                let fittedWidth = max(0, geometry.size.height - 30 - toolbarHeight) * slide.presentationAspectRatio + 14
                let railWidth = min(max(228, min(room * 0.46, 400)), max(228, room - fittedWidth))
                HStack(spacing: 12) {
                    slideStage(slide, width: room - railWidth, fitted: true, controlsInHeader: controlsInHeader)
                    teacherPanel(side: true).frame(width: railWidth)
                }
                .padding(.horizontal, 12)
                .padding(.vertical, 8)
            } else {
                ScrollView {
                    VStack(spacing: 11) {
                        slideStage(slide, width: max(0, geometry.size.width - 28), fitted: false, controlsInHeader: false)
                        teacherPanel(side: false)
                    }
                    .padding(.horizontal, 14)
                    .padding(.vertical, landscape ? 8 : 12)
                }
                .scrollBounceBehavior(.basedOnSize)
            }
        }
    }

    private func slideToolbar(stretches: Bool, stacked: Bool = false) -> some View {
        NativeClassroomSlideToolbar(hasNotes: !slideNotes.isEmpty, showingCanvas: showingCanvas,
                                    lectureActive: lectureActive, stretches: stretches, stacked: stacked,
                                    readNotes: $readNotes, zoom: $zoom)
    }

    private func slideStage(_ slide: ClassroomSlide, width: CGFloat, fitted: Bool,
                            controlsInHeader: Bool) -> some View {
        let innerWidth = max(0, width - 14)
        return VStack(spacing: 4) {
            if !controlsInHeader {
                slideToolbar(stretches: true, stacked: innerWidth < 300)
            }
            if showingCanvas {
                NativeSlideSurface(slide: slide, sceneID: model.currentSceneID, imageScope: model.imageScope,
                                   mediaSessionID: model.isClassicSession ? model.stageID : nil,
                                   mediaScope: classicScope, mediaVersion: model.imageScope,
                                   client: app.client, accountKey: model.accountKey, zoom: $zoom)
                    .frame(height: fitted ? nil : innerWidth / slide.presentationAspectRatio)
            } else if fitted {
                ScrollView { notesBody }.scrollBounceBehavior(.basedOnSize)
            } else {
                notesBody
            }
        }
        .padding(7)
        .frame(width: max(0, width))
        .frame(maxHeight: fitted ? .infinity : nil, alignment: .top)
        .background(palette.surface, in: RoundedRectangle(cornerRadius: 15))
        .overlay(RoundedRectangle(cornerRadius: 15).strokeBorder(NativeClassroomAppearance.wood.opacity(0.82)))
    }

    private var notesBody: some View {
        let paper = NativeClassroomAppearance.paper
        return VStack(alignment: .leading, spacing: 10) {
            ForEach(slideNotes) { element in
                let heading = element.paragraphs.first?.style.bold == true
                    && !element.plainText.contains("\n") && element.plainText.count <= 42
                Text(element.plainText)
                    .font(.system(size: heading ? 18 : 16, weight: heading ? .bold : .regular))
                    .foregroundStyle(heading ? paper.primary : paper.textPrimary)
                    .lineSpacing(4)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(paper.background, in: RoundedRectangle(cornerRadius: 10))
        .accessibilityLabel("讲义正文")
    }

    private var usesSequenceForLecture: Bool {
        model.hasSequenceSteps && model.isClassicSession && model.classicAudio != nil
    }

    private var canStartLecture: Bool {
        if model.sequence?.active == true || usesSequenceForLecture { return true }
        switch model.narrationPhase {
        case .available, .ready, .playing, .failed: return true
        default: return false
        }
    }

    private var lectureLabel: String {
        if model.sequence?.paused == true || model.narrationIsPaused { return "继续讲课" }
        if model.sequence?.active == true || model.audioIsPlaying { return "暂停讲课" }
        if let sequence = model.sequence, sequence.total > 0, sequence.completed >= sequence.total { return "重新讲解" }
        return "开始讲课"
    }

    private var lectureStatus: String {
        if model.sequence?.paused == true || model.narrationIsPaused { return "已暂停" }
        if model.sequence?.active == true && model.sequenceVideo != nil { return "演示中" }
        if model.audioIsPlaying { return "正在讲解" }
        switch model.narrationPhase {
        case .checking, .loadingAudio: return "正在准备语音"
        case .generating(let progress): return "正在生成讲解 \(progress)%"
        case .none: return "本页暂无语音"
        case .failed: return "讲解暂不可用"
        default: break
        }
        if let sequence = model.sequence {
            if sequence.active { return "正在讲解" }
            if sequence.total > 0 && sequence.completed >= sequence.total { return "本页讲完" }
        }
        return "可以开始讲课"
    }

    private func activateLecture() {
        readNotes = false
        if model.sequence?.active == true {
            if model.sequence?.paused == true { model.resumeSequence() } else { model.pauseSequence() }
        } else if usesSequenceForLecture, !model.audioIsPlaying, !model.narrationIsPaused {
            model.startSequence()
        } else {
            model.toggleNarration()
        }
    }

    private var lectureTranscript: (label: String, text: String)? {
        let actions = model.currentPlaybackScene?.speechActions.filter(\.supported) ?? []
        func script(_ action: ClassroomPlaybackAction) -> String? {
            action.payload["text"].string?.nonEmpty ?? action.payload["script"].string?.nonEmpty
                ?? action.payload["description"].string?.nonEmpty
        }
        if let actionID = model.sequence?.currentActionID, let action = actions.first(where: { $0.id == actionID }),
           let text = script(action) {
            return ("讲解字幕", text)
        }
        let scripts = actions.compactMap(script)
        let text = (scripts.isEmpty ? slideNotes.map(\.plainText) : scripts).joined(separator: "\n\n")
        return text.isEmpty ? nil : ("本页讲稿", text)
    }

    private func teacherPanel(side: Bool) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: side ? 4 : 8) {
                if !side {
                    Image(systemName: "person.wave.2.fill")
                        .font(.system(size: 21))
                        .foregroundStyle(palette.primary)
                        .frame(width: 40, height: 40)
                        .background(palette.primarySoft, in: RoundedRectangle(cornerRadius: 10))
                        .accessibilityHidden(true)
                }
                VStack(alignment: .leading, spacing: 3) {
                    Text("AI 老师").font(.system(size: 14, weight: .bold)).foregroundStyle(palette.textPrimary)
                    Text(lectureStatus).font(.system(size: 12, weight: .semibold)).foregroundStyle(palette.primary)
                        .lineLimit(2)
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                Button(action: activateLecture) {
                    Label(lectureLabel, systemImage: lectureLabel == "暂停讲课" ? "pause.fill" : "play.fill")
                }
                .buttonStyle(NativeClassroomGoldButton())
                .disabled(!canStartLecture)
                .accessibilityIdentifier("native.classroom.teach")
                if lectureActive {
                    Button {
                        if model.sequence?.active == true { model.stopSequence() } else { model.stopNarration() }
                    } label: {
                        Image(systemName: "stop.fill").font(.system(size: 14, weight: .semibold))
                            .foregroundStyle(palette.primary).frame(width: 44, height: 44)
                            .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                    .accessibilityLabel("停止")
                }
            }
            if let sequence = model.sequence, sequence.total > 1 {
                ProgressView(value: Double(sequence.completed), total: Double(sequence.total)).tint(palette.primary)
            }
            if let notice = model.sequence?.message ?? lectureError {
                Text(notice)
                    .font(.system(size: 12))
                    .foregroundStyle(palette.muted)
                    .lineLimit(side ? 2 : nil)
            }
            if let transcript = lectureTranscript {
                transcriptCard(label: transcript.label, text: transcript.text, scrollable: side)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, maxHeight: side ? .infinity : nil, alignment: .topLeading)
        .background(palette.surface, in: RoundedRectangle(cornerRadius: 15))
        .overlay(RoundedRectangle(cornerRadius: 15).strokeBorder(palette.line))
    }

    private var lectureError: String? {
        if case .failed(let message) = model.narrationPhase { return message }
        return nil
    }

    private func transcriptCard(label: String, text: String, scrollable: Bool) -> some View {
        VStack(spacing: 0) {
            HStack(spacing: 6) {
                Label(label, systemImage: "speaker.wave.2.fill")
                    .font(.system(size: 12)).foregroundStyle(palette.accent)
                Spacer(minLength: 5)
                Button(transcriptExpanded ? "收起" : "展开") { transcriptExpanded.toggle() }
                    .buttonStyle(.plain)
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(palette.primary)
                    .frame(minWidth: 44, minHeight: 44)
            }
            if transcriptExpanded {
                let content = Text(text)
                    .font(.system(size: 14))
                    .lineSpacing(5)
                    .foregroundStyle(palette.textPrimary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .fixedSize(horizontal: false, vertical: true)
                    .padding(.bottom, 10)
                if scrollable {
                    ScrollView { content }
                        .id(text)
                        .frame(maxHeight: .infinity)
                } else {
                    content
                }
            }
        }
        .padding(.horizontal, 10)
        .background(palette.background, in: RoundedRectangle(cornerRadius: 9))
    }

    private var sequenceBar: some View {
        HStack(alignment: .top, spacing: 9) {
            Image(systemName: "list.number")
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(palette.accent)
                .padding(.top, 2)
            VStack(alignment: .leading, spacing: 2) {
                Text(model.sequenceTitle)
                    .campusFont(.caption)
                    .foregroundStyle(palette.textPrimary)
                if let message = model.sequence?.message {
                    Text(message)
                        .campusFont(.micro)
                        .foregroundStyle(palette.muted)
                        .lineLimit(3)
                } else if let current = model.sequenceCurrentLabel {
                    Text("当前：\(current)").campusFont(.micro).foregroundStyle(palette.muted)
                }
            }
            Spacer(minLength: 4)
            if model.sequence?.active == true {
                Button(model.sequence?.paused == true ? "继续" : "暂停") {
                    if model.sequence?.paused == true { model.resumeSequence() } else { model.pauseSequence() }
                }
                .campusFont(.caption)
                .foregroundStyle(palette.primary)
                Button("停止") { model.stopSequence() }
                    .campusFont(.micro)
                    .foregroundStyle(palette.muted)
            } else {
                Button("顺序播放") { model.startSequence() }
                    .campusFont(.caption)
                    .foregroundStyle(palette.primary)
            }
        }
        .padding(.horizontal, 11)
        .padding(.vertical, 8)
        .background(RoundedRectangle(cornerRadius: 10).fill(palette.primarySoft.opacity(0.5)))
        .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(palette.line.opacity(0.45), lineWidth: 1))
        .accessibilityElement(children: .contain)
        .accessibilityIdentifier("native.classroom.sequence")
    }

    @ViewBuilder
    private var sceneBody: some View {
        switch model.currentRender {
        case .unsupported:
            NativeUnsupportedPanel(title: "这一页暂时无法原生播放",
                                   detail: unsupportedDetail)
        case .sandboxHTML:
            if case .interactive(let interactive)? = model.currentContent, let html = interactive.html {
                ClassroomSandboxView(html: html, url: nil) { sandboxMessage = $0 }
            } else {
                NativeUnsupportedPanel(title: "互动内容缺失", detail: "这一页没有可加载的互动内容。")
            }
        case .sandboxURL:
            if case .interactive(let interactive)? = model.currentContent, let url = interactive.url {
                ClassroomSandboxView(html: nil, url: url) { sandboxMessage = $0 }
            } else {
                NativeUnsupportedPanel(title: "互动链接不可用",
                                       detail: "这一页的互动地址不是受支持的安全链接。")
            }
        case .native:
            nativeBody
        }
    }

    @ViewBuilder
    private var nativeBody: some View {
        switch model.currentContent {
        case .slide(let slide)?:
            NativeSlideSurface(slide: slide, sceneID: model.currentSceneID, imageScope: model.imageScope,
                               mediaSessionID: model.isClassicSession ? model.stageID : nil,
                               mediaScope: classicScope, mediaVersion: model.imageScope,
                               client: app.client, accountKey: model.accountKey, zoom: $zoom)
        case .quiz(let set)?:
            NativeQuizPanel(set: set, model: model)
                .campusPalette(NativeClassroomAppearance.paper)
                .environment(\.colorScheme, .light)
        case .interactive(let interactive)?:
            if let simulation = interactive.simulation {
                NativeSimulationPanel(simulation: simulation, model: model)
            } else {
                NativeUnsupportedPanel(title: "互动组件暂不支持",
                                       detail: interactive.invalidReason ?? "这一页的互动组件没有可执行的播放脚本。")
            }
        case .pbl(let pbl)?:
            NativePBLPanel(pbl: pbl, model: model)
                .campusPalette(NativeClassroomAppearance.paper)
                .environment(\.colorScheme, .light)
        case .unsupported(_, let reason)?:
            NativeUnsupportedPanel(title: "这一页暂时无法原生播放", detail: reason)
        case .none:
            NativeUnsupportedPanel(title: "找不到这一页", detail: "播放计划与课堂文档没有对应上。")
        }
    }

    private var unsupportedDetail: String {
        if let explanation = model.currentPlaybackScene?.render.unsupportedExplanation { return explanation }
        if case .unsupported(_, let reason)? = model.currentContent { return reason }
        return "服务端没有为这一页提供可播放的内容。"
    }

    // MARK: - Extra playback controls

    private var narrationBar: some View {
        HStack(spacing: 9) {
            Image(systemName: "waveform")
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(palette.accent)
            VStack(alignment: .leading, spacing: 2) {
                Text(narrationTitle).campusFont(.caption).foregroundStyle(palette.textPrimary)
                if let notice = model.narrationNotice {
                    Text(notice).campusFont(.micro).foregroundStyle(palette.muted).lineLimit(2)
                }
            }
            Spacer(minLength: 4)
            if model.sequence?.active == true {
                Text("顺序播放中，讲解由动作序列控制")
                    .campusFont(.micro)
                    .foregroundStyle(palette.muted)
            } else {
                narrationButtons
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 7)
        .background(palette.surface.opacity(0.82))
        .overlay(alignment: .top) { Divider().overlay(palette.line.opacity(0.4)) }
        .accessibilityElement(children: .contain)
        .accessibilityLabel("讲解")
    }

    private var narrationTitle: String {
        switch model.narrationPhase {
        case .checking: "正在检查这一页的讲解…"
        case .none: model.isClassicSession ? "这一页没有原生讲解音频" : "这一页没有可讲解的文字"
        case .available: model.isClassicSession ? "这一页有教师讲解音频" : "这一页有讲稿，可以生成讲解"
        case .generating(let progress): "正在生成讲解 \(progress)%"
        case .loadingAudio: model.isClassicSession ? "正在下载教师讲解…" : "正在准备音频…"
        case .ready: model.isClassicSession ? "教师讲解已暂停" : "讲解已暂停"
        case .playing: model.isClassicSession ? "正在播放教师讲解" : "正在播放讲解"
        case .failed(let message): message
        }
    }

    @ViewBuilder
    private var narrationButtons: some View {
        switch model.narrationPhase {
        case .checking:
            ProgressView().controlSize(.small)
        case .none:
            EmptyView()
        case .available:
            if model.isClassicSession {
                Button("播放讲解") { model.toggleNarration() }
                    .campusFont(.caption).foregroundStyle(palette.primary)
            } else {
                Button("生成讲解") { model.generateNarration() }
                    .campusFont(.caption).foregroundStyle(palette.primary)
            }
        case .generating:
            HStack(spacing: 8) {
                ProgressView().controlSize(.small)
                Button("取消") { model.stopNarration() }
                    .campusFont(.micro).foregroundStyle(palette.muted)
            }
        case .loadingAudio:
            ProgressView().controlSize(.small)
        case .ready, .playing:
            Button {
                model.toggleNarration()
            } label: {
                Image(systemName: model.audioIsPlaying ? "pause.fill" : "play.fill")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(palette.primary)
                    .frame(width: 34, height: 34)
                    .background(Circle().fill(palette.primarySoft))
            }
            .accessibilityLabel(model.audioIsPlaying ? "暂停讲解" : "播放讲解")
            Button {
                model.stopNarration()
            } label: {
                Image(systemName: "stop.fill")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(palette.muted)
                    .frame(width: 34, height: 34)
                    .background(Circle().fill(palette.background))
            }
            .accessibilityLabel("停止讲解")
        case .failed:
            Button("重试") {
                model.toggleNarration()
            }
            .campusFont(.caption).foregroundStyle(palette.primary)
        }
    }

    private func banner(text: String, tone: CampusStatusTone, dismiss: (() -> Void)?) -> some View {
        HStack(alignment: .top, spacing: 7) {
            Image(systemName: "info.circle")
                .font(.system(size: 12))
                .foregroundStyle(tone == .warning ? palette.accent : palette.muted)
            Text(text).campusFont(.micro).foregroundStyle(palette.textPrimary)
                .fixedSize(horizontal: false, vertical: true)
            Spacer(minLength: 0)
            if let dismiss {
                Button(action: dismiss) {
                    Image(systemName: "xmark").font(.system(size: 10, weight: .semibold))
                        .foregroundStyle(palette.muted)
                }
                .accessibilityLabel("关闭提示")
            }
        }
        .padding(.horizontal, 11)
        .padding(.vertical, 8)
        .background(RoundedRectangle(cornerRadius: 10).fill(palette.primarySoft.opacity(0.5)))
    }

    // MARK: - Sheets

    private var sequenceVideoPresented: Binding<Bool> {
        Binding(
            get: { model.sequenceVideo != nil },
            set: { presented in
                if !presented { model.sequenceVideoSheetClosed() }
            }
        )
    }


    private func classroomPanel(_ tool: NativeClassroomPanel) -> some View {
        VStack(spacing: 0) {
            HStack {
                Text(tool.title).font(.system(size: 18, weight: .bold)).foregroundStyle(palette.textPrimary)
                Spacer(minLength: 8)
                Button("关闭") { panel = nil }
                    .buttonStyle(.plain)
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(palette.primary)
                    .frame(minWidth: 48, minHeight: 44)
            }
            .padding(.horizontal, 16)
            Rectangle().fill(palette.line).frame(height: 1)
            panelContent(tool).frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .background { palette.background.ignoresSafeArea() }
        .campusPalette(palette)
        .presentationDetents([.medium, .large])
        .fullScreenCover(isPresented: $showWebCompatibility) {
            if let webClassroom { compatibilityView(webClassroom) }
        }
    }

    @ViewBuilder
    private func panelContent(_ tool: NativeClassroomPanel) -> some View {
        switch tool {
        case .directory:
            outline
        case .narration:
            ScrollView {
                VStack(spacing: 10) {
                    narrationBar
                    if model.hasSequenceSteps || model.sequence != nil {
                        sequenceBar
                    }
                    if model.isClassicSession && model.classicAudio == nil { webFallbackButton }
                }
                .padding(14)
            }
        case .classmates:
            compatibilityPanel(webClassroom == nil ? "当前课堂未提供 AI 同学讨论入口。" : "AI 同学讨论可在网页课堂继续。")
        case .whiteboard:
            if let canvas = model.document?.whiteboardCanvas {
                VStack(spacing: 8) {
                    ClassroomCanvasView(canvas: canvas, sceneID: model.currentSceneID, imageScope: model.imageScope)
                        .aspectRatio(CGFloat(max(1, canvas.width) / max(1, canvas.height)), contentMode: .fit)
                        .clipShape(RoundedRectangle(cornerRadius: 9))
                        .accessibilityLabel("课堂白板")
                    Text("只读").font(.system(size: 12)).foregroundStyle(palette.muted)
                }
                .padding(14)
            } else {
                compatibilityPanel(webClassroom != nil && model.hasWhiteboardOnPage
                    ? "本页白板可在网页课堂查看。" : "本页没有可显示的白板。")
            }
        case .diagnostics:
            ScrollView {
                VStack(alignment: .leading, spacing: 12) {
                    Text(model.diagnosticsText)
                        .font(.system(.footnote, design: .monospaced))
                        .textSelection(.enabled)
                        .foregroundStyle(palette.textPrimary)
                        .frame(maxWidth: .infinity, alignment: .leading)
                    ShareLink(item: model.diagnosticsText) {
                        Label("导出性能样本", systemImage: "square.and.arrow.up").foregroundStyle(palette.primary)
                    }
                }
                .padding(16)
            }
        }
    }

    private var outline: some View {
        let infos = model.sceneInfos
        let scenes = model.document?.scenesByID ?? [:]
        return ScrollView {
            LazyVStack(alignment: .leading, spacing: 8) {
                Text("共 \(infos.count) 页 · 已学 \(infos.filter(\.visited).count) 页")
                    .font(.system(size: 12)).foregroundStyle(palette.muted)
                ForEach(Array(infos.enumerated()), id: \.offset) { index, info in
                    Button {
                        model.jump(to: info.id)
                        panel = nil
                    } label: {
                        HStack(spacing: 10) {
                            outlinePreview(info, content: scenes[info.id]?.content, index: index)
                            VStack(alignment: .leading, spacing: 3) {
                                Text(info.title)
                                    .font(.system(size: 14, weight: .semibold))
                                    .foregroundStyle(index == model.index ? palette.primary : palette.textPrimary)
                                    .lineLimit(2)
                                Text(info.type.label + (info.render == .unsupported ? " · 网页兼容" : ""))
                                    .font(.system(size: 11)).foregroundStyle(palette.muted)
                            }
                            Spacer(minLength: 6)
                            if index == model.index || info.visited {
                                Text(index == model.index ? "当前" : "已学").font(.system(size: 11))
                                    .foregroundStyle(index == model.index ? palette.primary : palette.accent)
                            }
                        }
                        .padding(9)
                        .background(palette.surface, in: RoundedRectangle(cornerRadius: 11))
                        .overlay(RoundedRectangle(cornerRadius: 11).strokeBorder(index == model.index ? palette.primary : palette.line))
                        .contentShape(Rectangle())
                    }
                    .buttonStyle(.plain)
                }
            }
            .padding(14)
        }
    }

    private func outlinePreview(_ info: NativeClassroomModel.SceneInfo, content: ClassroomSceneContent?, index: Int) -> some View {
        ZStack(alignment: .bottomLeading) {
            if case .slide(let slide)? = content, let canvas = slide.canvas {
                ClassroomCanvasView(canvas: canvas, sceneID: info.id, imageScope: model.imageScope)
            } else {
                Rectangle().fill(palette.primarySoft)
                Image(systemName: info.type == .quiz ? "checkmark.square" : "book")
                    .foregroundStyle(palette.primary).frame(maxWidth: .infinity, maxHeight: .infinity)
            }
            Text("\(index + 1)").font(.system(size: 10, weight: .semibold))
                .foregroundStyle(palette.textPrimary).padding(.horizontal, 5).padding(.vertical, 2)
                .background(palette.background.opacity(0.85))
        }
        .frame(width: 72, height: 41)
        .clipShape(RoundedRectangle(cornerRadius: 5))
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }

    private func compatibilityPanel(_ message: String) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text(message).font(.system(size: 14)).foregroundStyle(palette.textPrimary)
            webFallbackButton
        }
        .padding(16)
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: .topLeading)
    }

    @ViewBuilder
    private var webFallbackButton: some View {
        if webClassroom != nil {
            Button("打开网页课堂") { showWebCompatibility = true }
                .buttonStyle(NativeClassroomGoldButton())
        }
    }

    private func compatibilityView(_ classroom: NativeClassroomWebFallback) -> some View {
        NavigationStack {
            TrustedWebView(url: classroom.url, origins: [classroom.origin],
                           injectedScript: ClassroomRewards.script(accountKey: model.accountKey, classroom: model.stageID) + "\n" + ClassroomMobileLayout.script + "\n" + ClassroomSlideTheme.script,
                           persistentStorage: true, onError: { webError = $0 })
                .navigationTitle("互动课堂")
                .navigationBarTitleDisplayMode(.inline)
                .toolbar {
                    ToolbarItem(placement: .cancellationAction) {
                        Button("关闭") { showWebCompatibility = false }
                    }
                }
                .errorAlert($webError)
        }
    }
}

struct NativeClassroomWebFallback {
    let url: URL
    let origin: String
}

/// 从课程页/首页进入原生课堂时使用的目标值。
struct NativeClassroomDestination: Identifiable, Hashable {
    let courseID: String
    let workspaceID: String
    let stageID: String
    let title: String

    var id: String { "\(courseID)|\(workspaceID)|\(stageID)" }
}


/// Sequence-owned video sheet. The player is created from an already
/// authenticated local download; closing it is treated as completing the
/// video step so the order can continue without waiting forever.
private struct SequenceVideoSheet: View {
    let video: NativeClassroomModel.SequenceVideo
    let onClose: @MainActor () -> Void
    @Environment(\.scenePhase) private var scenePhase
    @State private var player: AVPlayer
    @State private var didFinish = false

    init(video: NativeClassroomModel.SequenceVideo, onClose: @escaping @MainActor () -> Void) {
        self.video = video
        self.onClose = onClose
        _player = State(initialValue: AVPlayer(url: video.url))
    }

    var body: some View {
        ZStack(alignment: .topTrailing) {
            VideoPlayer(player: player)
                .ignoresSafeArea()
            Button {
                didFinish = true
                player.pause()
                onClose()
            } label: {
                Image(systemName: "xmark.circle.fill")
                    .font(.system(size: 28, weight: .semibold))
                    .foregroundStyle(.white, .black.opacity(0.55))
                    .padding(16)
            }
            .accessibilityLabel("关闭课堂视频")
            .accessibilityIdentifier("native.classroom.sequence.video.close")
        }
            .onAppear {
                player.play()
            }
            .onReceive(NotificationCenter.default.publisher(
                for: AVPlayerItem.didPlayToEndTimeNotification,
                object: player.currentItem
            )) { _ in
                guard !didFinish else { return }
                didFinish = true
                player.pause()
                onClose()
            }
            .onChange(of: scenePhase) { _, phase in
                if phase != .active { player.pause() }
            }
            .onDisappear {
                player.pause()
                if !didFinish {
                    didFinish = true
                    onClose()
                }
            }
            .accessibilityIdentifier("native.classroom.sequence.video")
    }
}
