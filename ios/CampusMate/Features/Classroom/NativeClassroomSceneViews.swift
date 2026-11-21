import Foundation
import SwiftUI
import AVKit
import UIKit
import WebKit
import CampusCore

extension ClassroomColor {
    var swiftUIColor: Color { Color(red: red, green: green, blue: blue, opacity: alpha) }
}

// MARK: - Slide canvas

/// 课件画布按 1000 × 562.5 的设计坐标绘制，再整体缩放到可用区域。
/// 双指缩放与拖动只改变展示比例，不改变文档坐标，所以换页、旋转、重进后版面一致。
struct NativeSlideSurface: View {
    let slide: ClassroomSlide
    let sceneID: String
    var imageScope: String = ""
    var mediaSessionID: String? = nil
    var mediaScope: ClassroomScope? = nil
    var mediaVersion: String = ""
    var client: APIClient? = nil
    var accountKey: String = ""
    @Binding var zoom: CGFloat
    @State private var pinchStart: CGFloat?
    @State private var offset: CGSize = .zero
    @State private var lastOffset: CGSize = .zero

    var body: some View {
        GeometryReader { proxy in
            let width = min(proxy.size.width, proxy.size.height * slide.presentationAspectRatio)
            let fitted = CGSize(width: width, height: width / slide.presentationAspectRatio)
            page
                .frame(width: fitted.width, height: fitted.height)
                .clipped()
                .scaleEffect(zoom)
                .offset(offset)
                .frame(width: fitted.width, height: fitted.height)
                .clipShape(RoundedRectangle(cornerRadius: 9))
                .contentShape(Rectangle())
                .simultaneousGesture(magnification)
                .simultaneousGesture(pan(in: fitted), including: zoom > 1 ? .all : .subviews)
                .onChange(of: zoom) { _, _ in boundOffset(in: fitted) }
                .onChange(of: fitted) { _, size in boundOffset(in: size) }
                .frame(maxWidth: .infinity, maxHeight: .infinity)
                .accessibilityElement(children: .contain)
        }
        .accessibilityLabel(slide.prefersCanvas ? "课件画布" : "课件文字页")
    }

    @ViewBuilder private var page: some View {
        if slide.prefersCanvas, let canvas = slide.canvas {
            ClassroomCanvasView(canvas: canvas, sceneID: sceneID, imageScope: imageScope,
                                mediaSessionID: mediaSessionID, mediaScope: mediaScope,
                                mediaVersion: mediaVersion, client: client, accountKey: accountKey)
        } else {
            ClassroomOutlinePage(outline: slide.outline)
                .background(NativeClassroomAppearance.paper.background)
                .campusPalette(NativeClassroomAppearance.paper)
        }
    }

    private var magnification: some Gesture {
        MagnifyGesture()
            .onChanged { value in
                let start = pinchStart ?? zoom
                pinchStart = start
                zoom = min(1.6, max(0.7, start * value.magnification))
            }
            .onEnded { _ in pinchStart = nil }
    }

    private func pan(in size: CGSize) -> some Gesture {
        DragGesture(minimumDistance: 8)
            .onChanged { value in
                offset = constrained(CGSize(width: lastOffset.width + value.translation.width,
                                            height: lastOffset.height + value.translation.height), in: size)
            }
            .onEnded { _ in lastOffset = offset }
    }

    private func boundOffset(in size: CGSize) {
        offset = constrained(offset, in: size)
        lastOffset = offset
    }

    private func constrained(_ position: CGSize, in size: CGSize) -> CGSize {
        let horizontal = max(0, (zoom - 1) * size.width / 2)
        let vertical = max(0, (zoom - 1) * size.height / 2)
        return CGSize(width: min(horizontal, max(-horizontal, position.width)),
                      height: min(vertical, max(-vertical, position.height)))
    }
}

extension ClassroomSlide {
    var presentationAspectRatio: CGFloat {
        guard let canvas, canvas.width.isFinite, canvas.height.isFinite,
              canvas.width > 0, canvas.height > 0 else { return 16.0 / 9.0 }
        return CGFloat(canvas.width / canvas.height)
    }
}

struct ClassroomCanvasView: View {
    @Environment(\.campus) private var palette
    let canvas: ClassroomCanvas
    let sceneID: String
    var imageScope: String = ""
    var mediaSessionID: String? = nil
    var mediaScope: ClassroomScope? = nil
    var mediaVersion: String = ""
    var client: APIClient? = nil
    var accountKey: String = ""

    var body: some View {
        GeometryReader { proxy in
            let sx = proxy.size.width / max(1, canvas.width)
            let sy = proxy.size.height / max(1, canvas.height)
            ZStack(alignment: .topLeading) {
                canvasBackground
                ForEach(canvas.elements) { element in
                    elementView(element, sx: sx, sy: sy)
                }
            }
            .clipped()
        }
    }

    @ViewBuilder
    private var canvasBackground: some View {
        if canvas.usesStockTemplate {
            LinearGradient(colors: [Color(hex: 0x203E41), Color(hex: 0x11282E)],
                           startPoint: .topLeading, endPoint: .bottomTrailing)
        } else if canvas.backgroundGradient.count > 1 {
            LinearGradient(colors: canvas.backgroundGradient.map(\.swiftUIColor),
                           startPoint: .topLeading, endPoint: .bottomTrailing)
        } else {
            Rectangle().fill(canvas.background?.swiftUIColor ?? Color(hex: 0xFFFBF2))
        }
    }

    @ViewBuilder
    private func elementView(_ element: ClassroomCanvas.Element, sx: CGFloat, sy: CGFloat) -> some View {
        switch element {
        case .text(let text):
            let frame = scaled(text.frame, sx: sx, sy: sy)
            TextStack(paragraphs: text.paragraphs, scale: min(sx, sy), vertical: text.verticalAlignment,
                      usesStockTemplate: canvas.usesStockTemplate)
                .frame(width: frame.width, height: frame.height,
                       alignment: alignment(text.verticalAlignment))
                .rotationEffect(.degrees(text.rotate))
                .position(x: frame.midX, y: frame.midY)
        case .shape(let shape):
            let frame = scaled(shape.frame, sx: sx, sy: sy)
            let accent = canvas.usesStockTemplate && shape.fill == ClassroomColor(css: "#722ed1")
            let card = canvas.usesStockTemplate && shape.fill == ClassroomColor(css: "#f5f3ff")
            let radius = accent ? 3 : (card && shape.cornerRadius <= 0 ? 12 : shape.cornerRadius)
            let colour = accent ? Color(hex: 0xEDBE80)
                : card ? Color(hex: 0x284B4D) : shape.fill?.swiftUIColor ?? .clear
            let border = shape.stroke?.swiftUIColor ?? (card ? Color(hex: 0x547B72) : .clear)
            let borderWidth = card && shape.strokeWidth <= 0 ? 1 : shape.strokeWidth
            let path = RoundedRectangle(cornerRadius: max(0, radius * min(sx, sy)), style: .continuous)
            path.fill(colour)
                .overlay { path.strokeBorder(border, lineWidth: borderWidth * min(sx, sy)) }
                .frame(width: frame.width, height: frame.height)
                .rotationEffect(.degrees(shape.rotate))
                .position(x: frame.midX, y: frame.midY)
        case .image(let image):
            let frame = scaled(image.frame, sx: sx, sy: sy)
            Group {
                if let picture = ClassroomImageCache.shared.image(sceneID: sceneID, element: image, scope: imageScope) {
                    Image(uiImage: picture).resizable().scaledToFill()
                } else {
                    ZStack {
                        RoundedRectangle(cornerRadius: 8).fill(palette.primarySoft)
                        Image(systemName: "photo").foregroundStyle(palette.muted)
                    }
                }
            }
            .frame(width: frame.width, height: frame.height)
            .clipped()
            .rotationEffect(.degrees(image.rotate))
            .position(x: frame.midX, y: frame.midY)
            .accessibilityLabel(image.alt)
        case .audio(let audio):
            let frame = scaled(audio.frame, sx: sx, sy: sy)
            ClassroomCanvasMediaView(kind: "audio", elementID: audio.id, title: audio.title,
                                     source: audio.source, sessionID: mediaSessionID,
                                     scope: mediaScope, mediaVersion: mediaVersion,
                                     client: client, accountKey: accountKey)
                .frame(width: max(44, frame.width), height: max(36, frame.height))
                .rotationEffect(.degrees(audio.rotate))
                .position(x: frame.midX, y: frame.midY)
        case .video(let video):
            let frame = scaled(video.frame, sx: sx, sy: sy)
            ClassroomCanvasMediaView(kind: "video", elementID: video.id, title: video.title,
                                     source: video.source, sessionID: mediaSessionID,
                                     scope: mediaScope, mediaVersion: mediaVersion,
                                     client: client, accountKey: accountKey)
                .frame(width: max(80, frame.width), height: max(56, frame.height))
                .rotationEffect(.degrees(video.rotate))
                .position(x: frame.midX, y: frame.midY)
        case .unknown:
            EmptyView()
        }
    }

    private func scaled(_ rect: ClassroomRect, sx: CGFloat, sy: CGFloat) -> CGRect {
        CGRect(x: rect.x * sx, y: rect.y * sy, width: rect.width * sx, height: rect.height * sy)
    }

    private func alignment(_ value: ClassroomVerticalAlignment) -> Alignment {
        switch value {
        case .top: .topLeading
        case .middle: .leading
        case .bottom: .bottomLeading
        }
    }
}

/// 画布音频/视频元素。资源只接受当前课堂的本站鉴权路径；外链、缺失文件或下载失败
/// 都显示实际状态，并提示网页课堂仍可查看。
struct ClassroomCanvasMediaView: View {
    @Environment(\.campus) private var palette
    let kind: String
    let elementID: String
    let title: String
    let source: String?
    let sessionID: String?
    let scope: ClassroomScope?
    var mediaVersion: String = ""
    let client: APIClient?
    let accountKey: String
    @Environment(\.scenePhase) private var scenePhase
    @State private var media = ClassroomCanvasMediaPlayer()
    @State private var showVideo = false
    @State private var loadTask: Task<Void, Never>?

    var body: some View {
        ZStack {
            RoundedRectangle(cornerRadius: 8).fill(palette.primarySoft)
            VStack(spacing: 2) {
                Image(systemName: kind == "audio" ? "waveform" : "play.rectangle")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(palette.primary)
                Text(title).campusFont(.micro).foregroundStyle(palette.textPrimary).lineLimit(1)
                Text(status).campusFont(.micro).foregroundStyle(palette.muted).lineLimit(1)
            }
            .padding(4)
        }
        .contentShape(Rectangle())
        .onTapGesture { play() }
        .sheet(isPresented: $showVideo, onDismiss: { media.pause() }) {
            if let player = media.videoPlayer {
                VideoPlayer(player: player).ignoresSafeArea()
            } else {
                ProgressView().padding()
            }
        }
        .onChange(of: scenePhase) { _, phase in
            if phase != .active {
                loadTask?.cancel()
                media.pause()
            }
        }
        .onDisappear {
            loadTask?.cancel()
            loadTask = nil
            media.shutdown()
        }
        .accessibilityLabel("\(title)，\(status)")
    }

    private var canPlay: Bool {
        source != nil && sessionID != nil && scope != nil && client != nil
    }

    private var status: String {
        guard source != nil else { return "资源不可用，网页课堂可查看" }
        guard canPlay else { return "仅网页课堂可播放" }
        switch media.phase {
        case .idle: return "点击播放"
        case .loading: return "正在下载…"
        case .ready: return media.isPlaying ? "正在播放" : "已暂停"
        case .playing: return "正在播放"
        case .failed(let message): return message
        }
    }

    private func play() {
        guard let source, let sessionID, let scope, let client else { return }
        loadTask?.cancel()
        loadTask = Task {
            await media.toggle(kind: kind, elementID: elementID, source: source,
                               version: mediaVersion, sessionID: sessionID, scope: scope,
                               client: client, accountKey: accountKey) {
                showVideo = true
            }
        }
    }
}

/// 课件文本逐段渲染，保留字号、颜色、粗细、对齐与列表符号。
struct TextStack: View {
    let paragraphs: [ClassroomParagraph]
    let scale: CGFloat
    let vertical: ClassroomVerticalAlignment
    var usesStockTemplate = false

    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            ForEach(paragraphs) { paragraph in
                HStack(alignment: .top, spacing: max(3, 6 * scale)) {
                    if let marker = paragraph.marker {
                        Text(marker)
                            .font(.system(size: max(7, paragraph.style.fontSize * scale * 0.9),
                                          weight: paragraph.style.bold ? .bold : .regular))
                            .foregroundStyle(paragraphColor(paragraph))
                            .frame(minWidth: max(10, 18 * scale), alignment: .trailing)
                    }
                    Text(paragraph.text)
                        .font(.system(size: max(7, paragraph.style.fontSize * scale),
                                      weight: paragraph.style.isHeading || paragraph.style.bold ? .bold : .regular))
                        .foregroundStyle(paragraphColor(paragraph))
                        .lineSpacing(max(0, min(8, (paragraph.style.lineHeight - 1) * paragraph.style.fontSize * scale)))
                        .multilineTextAlignment(textAlignment(paragraph.style.alignment))
                        .fixedSize(horizontal: false, vertical: true)
                }
                .frame(maxWidth: .infinity, alignment: stackAlignment(paragraph.style.alignment))
                .padding(.bottom, max(1, 4 * scale))
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity, alignment: contentAlignment)
        .accessibilityElement(children: .combine)
        .accessibilityLabel(ClassroomRichTextParser.plainText(paragraphs))
    }

    private var contentAlignment: Alignment {
        switch vertical {
        case .top: .topLeading
        case .middle: .leading
        case .bottom: .bottomLeading
        }
    }

    private func paragraphColor(_ paragraph: ClassroomParagraph) -> Color {
        let color = paragraph.style.color
        if usesStockTemplate {
            if color == nil || color == ClassroomColor(css: "#1f2937") { return Color(hex: 0xF4ECD9) }
            if color == ClassroomColor(css: "#374151") { return Color(hex: 0xDCEAE3) }
            if color == ClassroomColor(css: "#6b7280") { return Color(hex: 0xAAC5B9) }
            if color == ClassroomColor(css: "#722ed1") { return Color(hex: 0xEDBE80) }
        }
        return color?.swiftUIColor ?? Color(red: 0.13, green: 0.20, blue: 0.17)
    }

    private func textAlignment(_ value: ClassroomTextAlignment) -> TextAlignment {
        switch value {
        case .center: .center
        case .trailing: .trailing
        default: .leading
        }
    }

    private func stackAlignment(_ value: ClassroomTextAlignment) -> Alignment {
        switch value {
        case .center: .center
        case .trailing: .trailing
        default: .leading
        }
    }
}

/// 历史课件没有画布元素时的可读版面：标题、要点、分区、对照与结论。
struct ClassroomOutlinePage: View {
    @Environment(\.campus) private var palette
    let outline: ClassroomSlideOutline

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                if !outline.title.isEmpty {
                    Text(outline.title)
                        .campusFont(.title)
                        .foregroundStyle(palette.textPrimary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                if let subtitle = outline.subtitle {
                    Text(subtitle)
                        .campusFont(.bodySmall)
                        .foregroundStyle(palette.muted)
                }
                if !outline.bullets.isEmpty {
                    VStack(alignment: .leading, spacing: 9) {
                        ForEach(Array(outline.bullets.enumerated()), id: \.offset) { _, bullet in
                            bulletRow(bullet)
                        }
                    }
                }
                ForEach(outline.sections) { section in
                    VStack(alignment: .leading, spacing: 8) {
                        if let heading = section.heading {
                            Text(heading)
                                .campusFont(.subtitle)
                                .foregroundStyle(palette.primary)
                        }
                        ForEach(Array(section.bullets.enumerated()), id: \.offset) { _, bullet in
                            bulletRow(bullet)
                        }
                    }
                }
                if let comparison = outline.comparison {
                    HStack(alignment: .top, spacing: 12) {
                        comparisonCard(comparison.left, tint: palette.primarySoft)
                        comparisonCard(comparison.right, tint: palette.primarySoft.opacity(0.7))
                    }
                }
                if !outline.toc.isEmpty {
                    VStack(alignment: .leading, spacing: 7) {
                        ForEach(Array(outline.toc.enumerated()), id: \.offset) { index, item in
                            HStack(spacing: 8) {
                                Text("\(index + 1)")
                                    .campusFont(.micro)
                                    .foregroundStyle(palette.muted)
                                    .frame(width: 18, height: 18)
                                    .background(Circle().fill(palette.primarySoft))
                                Text(item).campusFont(.bodySmall).foregroundStyle(palette.textPrimary)
                            }
                        }
                    }
                }
                if let conclusion = outline.conclusion {
                    Text(conclusion)
                        .campusFont(.body)
                        .foregroundStyle(palette.textPrimary)
                        .padding(12)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(RoundedRectangle(cornerRadius: 12).fill(palette.primarySoft.opacity(0.6)))
                }
            }
            .padding(18)
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .accessibilityElement(children: .contain)
    }

    private func bulletRow(_ text: String) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Circle().fill(palette.accent).frame(width: 5, height: 5).padding(.top, 7)
            Text(text).campusFont(.body).foregroundStyle(palette.textPrimary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }

    private func comparisonCard(_ section: ClassroomSlideOutline.Section, tint: Color) -> some View {
        VStack(alignment: .leading, spacing: 7) {
            if let heading = section.heading {
                Text(heading).campusFont(.caption).foregroundStyle(palette.muted)
            }
            ForEach(Array(section.bullets.enumerated()), id: \.offset) { _, bullet in
                Text(bullet).campusFont(.bodySmall).foregroundStyle(palette.textPrimary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RoundedRectangle(cornerRadius: 12).fill(tint))
    }
}

// MARK: - Quiz

struct NativeQuizPanel: View {
    @Environment(\.campus) private var palette
    let set: ClassroomQuizSet
    let model: NativeClassroomModel

    var body: some View {
        ScrollViewReader { reader in
            ScrollView {
                LazyVStack(alignment: .leading, spacing: 12) {
                    header.id("quiz-header")
                    if let error = model.quizError {
                        Text(error).campusFont(.caption).foregroundStyle(palette.dangerText)
                    }
                    if let session = model.quiz {
                        if session.phase == .reviewed, let evaluation = session.evaluation {
                            scoreCard(session: session, evaluation: evaluation)
                        }
                        ForEach(set.questions) { question in
                            questionCard(question, session: session)
                        }
                        actions(session: session)
                    } else if model.quizError == nil {
                        HStack(spacing: 8) {
                            ProgressView().controlSize(.small)
                            Text("正在读取答题记录…").campusFont(.caption).foregroundStyle(palette.muted)
                        }
                        .frame(maxWidth: .infinity, alignment: .center)
                        .padding(.vertical, 24)
                    }
                }
                .padding(14)
            }
            .onChange(of: model.quiz?.phase) { _, phase in
                if phase == .reviewed {
                    reader.scrollTo("quiz-header", anchor: .top)
                }
            }
        }
        .background(palette.background, in: RoundedRectangle(cornerRadius: 16))
        .clipShape(RoundedRectangle(cornerRadius: 16))
        .overlay(RoundedRectangle(cornerRadius: 16).strokeBorder(palette.line))
    }

    private var header: some View {
        let session = model.quiz
        let evaluation = session?.phase == .reviewed ? session?.evaluation : nil
        let title = model.currentPlaybackScene?.title ?? "课堂挑战"
        return VStack(alignment: .leading, spacing: 9) {
            HStack(spacing: 10) {
                Image(systemName: "flag.fill")
                    .font(.system(size: 21))
                    .foregroundStyle(palette.primary)
                    .frame(width: 40, height: 40)
                    .background(palette.primarySoft, in: RoundedRectangle(cornerRadius: 10))
                    .accessibilityHidden(true)
                VStack(alignment: .leading, spacing: 3) {
                    Text(evaluation == nil ? title : "\(title) · 结果")
                        .font(.system(size: 22, weight: .bold)).foregroundStyle(palette.textPrimary)
                    if let evaluation {
                        let correct = evaluation.results.filter { $0.correct == true }.count
                        Text("得分 \(scoreText(evaluation.score)) / \(scoreText(evaluation.total)) · 答对 \(correct) 题")
                            .font(.system(size: 13)).foregroundStyle(palette.muted)
                    } else {
                        Text("满分 \(scoreText(set.totalPoints)) 分")
                            .font(.system(size: 13)).foregroundStyle(palette.muted)
                    }
                }
            }
            if let session, evaluation == nil, !set.questions.isEmpty {
                Text("已作答 \(session.answeredCount) / \(set.questions.count) 题")
                    .font(.system(size: 12, weight: .medium)).foregroundStyle(palette.primary)
                ProgressView(value: Double(session.answeredCount), total: Double(set.questions.count))
                    .tint(palette.primary)
            }
            if set.studentLed {
                Text("作业复习：简答题不自动判分，结果以老师批改和解析为准。")
                    .campusFont(.caption).foregroundStyle(palette.muted)
            }
        }
        .padding(13)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(palette.surface, in: RoundedRectangle(cornerRadius: 12))
    }

    private func scoreCard(session: NativeClassroomModel.QuizSession, evaluation: ClassroomQuizEvaluation) -> some View {
        let objective = evaluation.results.filter { $0.correct != nil }
        let correct = objective.filter { $0.correct == true }.count
        let subjective = set.questions.filter(\.isShort).count
        return VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 10) {
                scoreBadge("客观题", "\(correct)/\(objective.count)", tint: palette.successText)
                scoreBadge("主观题", subjective == 0 ? "无" : "\(subjective) 题", tint: palette.accent)
            }
            if let message = session.message {
                Text(message).campusFont(.caption).foregroundStyle(palette.muted)
            }
            if session.needsSync {
                Button("重新同步结果") {
                    Task { await model.syncQuizIfNeeded() }
                }
                .campusFont(.caption)
                .foregroundStyle(palette.primary)
            }
        }
    }

    private func scoreBadge(_ title: String, _ value: String, tint: Color) -> some View {
        VStack(alignment: .leading, spacing: 3) {
            Text(title).font(.system(size: 12)).foregroundStyle(palette.muted)
            Text(value).font(.system(size: 17, weight: .bold)).foregroundStyle(tint)
        }
        .padding(12)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(palette.surface, in: RoundedRectangle(cornerRadius: 11))
    }

    private func questionCard(_ question: ClassroomQuizQuestion, session: NativeClassroomModel.QuizSession) -> some View {
        let result = session.evaluation?.results.first { $0.questionID == question.id }
        let selected = selectedValues(session: session, question: question)
        return VStack(alignment: .leading, spacing: 10) {
            HStack(alignment: .top, spacing: 8) {
                Text("\(questionIndex(question) + 1)")
                    .campusFont(.micro)
                    .foregroundStyle(palette.muted)
                    .frame(width: 22, height: 22)
                    .background(Circle().fill(palette.primarySoft))
                VStack(alignment: .leading, spacing: 4) {
                    Text(question.prompt)
                        .campusFont(.body)
                        .foregroundStyle(palette.textPrimary)
                        .fixedSize(horizontal: false, vertical: true)
                    HStack(spacing: 6) {
                        Text(question.roleLabel).campusFont(.micro).foregroundStyle(palette.muted)
                        Text("\(scoreText(question.points)) 分").campusFont(.micro).foregroundStyle(palette.muted)
                        if question.isMultiple {
                            Text("多选").campusFont(.micro).foregroundStyle(palette.accent)
                        }
                    }
                }
                Spacer(minLength: 0)
                if let result {
                    resultBadge(result)
                }
            }

            if question.isShort {
                shortAnswerField(question: question, session: session, enabled: session.phase == .answering)
            } else {
                VStack(alignment: .leading, spacing: 8) {
                    ForEach(question.options) { option in
                        optionRow(question: question, option: option,
                                  selected: selected.contains(option.value),
                                  revealed: result != nil,
                                  correct: question.answers.contains(option.value),
                                  enabled: session.phase == .answering)
                    }
                }
            }

            if session.phase == .reviewed {
                Text(question.analysis)
                    .campusFont(.bodySmall)
                    .foregroundStyle(palette.textPrimary)
                    .padding(11)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(RoundedRectangle(cornerRadius: 10).fill(palette.background))
                if !question.hints.isEmpty {
                    hintSection(question: question, session: session)
                }
            } else if !question.hints.isEmpty {
                hintSection(question: question, session: session)
            }
        }
        .padding(14)
        .background(RoundedRectangle(cornerRadius: 16).fill(palette.surface))
        .overlay(RoundedRectangle(cornerRadius: 16).strokeBorder(palette.line.opacity(0.7), lineWidth: 1))
    }

    private func optionRow(question: ClassroomQuizQuestion, option: ClassroomQuizOption, selected: Bool,
                           revealed: Bool, correct: Bool, enabled: Bool) -> some View {
        Button {
            model.select(option: option, for: question)
        } label: {
            HStack(spacing: 9) {
                Text(option.value)
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(selected ? .white : palette.primary)
                    .frame(width: 22, height: 22)
                    .background(Circle().fill(selected ? palette.primary : palette.primarySoft))
                Text(option.label)
                    .campusFont(.bodySmall)
                    .foregroundStyle(palette.textPrimary)
                    .multilineTextAlignment(.leading)
                Spacer(minLength: 0)
                if revealed && correct {
                    Image(systemName: "checkmark.circle.fill").foregroundStyle(palette.success)
                } else if revealed && selected && !correct {
                    Image(systemName: "xmark.circle.fill").foregroundStyle(palette.dangerText)
                }
            }
            .padding(10)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(RoundedRectangle(cornerRadius: 11).fill(selected ? palette.primarySoft.opacity(0.7) : palette.background))
            .overlay(RoundedRectangle(cornerRadius: 11).strokeBorder(selected ? palette.primary.opacity(0.5) : palette.line.opacity(0.4), lineWidth: 1))
        }
        .buttonStyle(.plain)
        .disabled(!enabled)
        .accessibilityLabel("\(option.value). \(option.label)")
        .accessibilityAddTraits(selected ? .isSelected : [])
    }

    private func shortAnswerField(question: ClassroomQuizQuestion, session: NativeClassroomModel.QuizSession, enabled: Bool) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            TextField("写下你的答案", text: Binding(
                get: {
                    if case .text(let value)? = session.answers[question.id] { return value }
                    if case .choice(let value)? = session.answers[question.id] { return value }
                    return ""
                },
                set: { model.setShortAnswer($0, for: question) }
            ), axis: .vertical)
            .lineLimit(2...5)
            .disabled(!enabled)
            .campusFont(.body)
            .padding(10)
            .background(RoundedRectangle(cornerRadius: 10).fill(palette.background))
            .overlay(RoundedRectangle(cornerRadius: 10).strokeBorder(palette.line.opacity(0.6), lineWidth: 1))
            if !enabled, let answer = question.acceptedAnswers.first {
                Text("参考答案：\(answer)").campusFont(.caption).foregroundStyle(palette.muted)
            }
        }
    }

    private func hintSection(question: ClassroomQuizQuestion, session: NativeClassroomModel.QuizSession) -> some View {
        let shown = session.hintsShown[question.id, default: 0]
        return VStack(alignment: .leading, spacing: 6) {
            ForEach(Array(question.hints.prefix(shown).enumerated()), id: \.offset) { index, hint in
                HStack(alignment: .top, spacing: 7) {
                    Image(systemName: "lightbulb").font(.system(size: 11)).foregroundStyle(palette.accent)
                    Text("提示 \(index + 1)：\(hint)").campusFont(.caption).foregroundStyle(palette.muted)
                        .fixedSize(horizontal: false, vertical: true)
                }
            }
            if shown < question.hints.count {
                Button(shown == 0 ? "看提示" : "再看一条提示") {
                    model.revealHint(for: question)
                }
                .campusFont(.caption)
                .foregroundStyle(palette.primary)
            }
        }
    }

    private func resultBadge(_ result: ClassroomQuizEvaluation.Result) -> some View {
        Group {
            if let correct = result.correct {
                CampusStatusTag(text: correct ? "正确 +\(scoreText(result.earned))" : "需订正",
                                tone: correct ? .success : .danger)
            } else {
                CampusStatusTag(text: "待老师查看", tone: .warning)
            }
        }
    }

    @ViewBuilder
    private func actions(session: NativeClassroomModel.QuizSession) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            if session.phase == .answering || session.phase == .submitting {
                CampusPrimaryButton(title: session.phase == .submitting ? "正在提交…" : "提交并查看解析",
                                    systemImage: "checkmark.seal",
                                    loading: session.phase == .submitting,
                                    enabled: session.answeredCount > 0) {
                    Task { await model.submitQuiz() }
                }
                .accessibilityIdentifier("native.quiz.submit")
            }
            if session.phase == .reviewed {
                HStack(spacing: 10) {
                    CampusSecondaryButton(title: "重新作答", systemImage: "arrow.counterclockwise") {
                        model.retryQuiz()
                    }
                    Text("重做会新建一次作答记录，旧记录仍保留。")
                        .campusFont(.micro).foregroundStyle(palette.muted)
                }
            }
            if let message = session.message, session.phase != .reviewed {
                Text(message).campusFont(.caption).foregroundStyle(palette.dangerText)
            }
            Text("草稿会自动保存；切页或退出后回来仍能继续。")
                .campusFont(.micro).foregroundStyle(palette.muted)
        }
    }

    private func answerValues(session: NativeClassroomModel.QuizSession, question: ClassroomQuizQuestion) -> [String] {
        switch session.answers[question.id] {
        case .choice(let value)?: return [value]
        case .choices(let values)?: return values
        default: return []
        }
    }

    private func selectedValues(session: NativeClassroomModel.QuizSession, question: ClassroomQuizQuestion) -> Set<String> {
        Set(answerValues(session: session, question: question))
    }

    private func questionIndex(_ question: ClassroomQuizQuestion) -> Int {
        set.questions.firstIndex { $0.id == question.id } ?? 0
    }

    private func scoreText(_ value: Double) -> String {
        value.rounded() == value ? String(format: "%.0f", value) : String(format: "%.1f", value)
    }
}

// MARK: - PBL

struct NativePBLPanel: View {
    @Environment(\.campus) private var palette
    let pbl: ClassroomPBL
    let model: NativeClassroomModel

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                VStack(alignment: .leading, spacing: 6) {
                    Text(pbl.title).campusFont(.headline).foregroundStyle(palette.textPrimary)
                    Text(pbl.detail).campusFont(.bodySmall).foregroundStyle(palette.muted)
                        .fixedSize(horizontal: false, vertical: true)
                    let progress = ClassroomPBLProgress(pbl: pbl, completedIDs: model.pblCompleted)
                    HStack(spacing: 9) {
                        ProgressView(value: Double(progress.percent), total: 100)
                            .tint(palette.accent)
                        Text("\(progress.completed)/\(progress.total) 阶段任务")
                            .campusFont(.caption).foregroundStyle(palette.muted)
                    }
                    .padding(.top, 4)
                }
                ForEach(Array(pbl.phases.enumerated()), id: \.offset) { index, phase in
                    VStack(alignment: .leading, spacing: 9) {
                        HStack(spacing: 8) {
                            Text("\(index + 1)")
                                .font(.system(size: 12, weight: .bold))
                                .foregroundStyle(.white)
                                .frame(width: 22, height: 22)
                                .background(Circle().fill(palette.primary))
                            Text(phase.title).campusFont(.subtitle).foregroundStyle(palette.textPrimary)
                        }
                        Text(phase.detail).campusFont(.caption).foregroundStyle(palette.muted)
                        ForEach(phase.tasks) { task in
                            let done = model.pblCompleted.contains(task.id)
                            Button {
                                model.togglePBLTask(task.id)
                            } label: {
                                HStack(alignment: .top, spacing: 9) {
                                    Image(systemName: done ? "checkmark.circle.fill" : "circle")
                                        .foregroundStyle(done ? palette.success : palette.muted)
                                    VStack(alignment: .leading, spacing: 3) {
                                        Text(task.title).campusFont(.bodySmall).foregroundStyle(palette.textPrimary)
                                        if task.detail != task.title {
                                            Text(task.detail).campusFont(.micro).foregroundStyle(palette.muted)
                                                .fixedSize(horizontal: false, vertical: true)
                                        }
                                    }
                                    Spacer(minLength: 0)
                                }
                                .padding(10)
                                .frame(maxWidth: .infinity, alignment: .leading)
                                .background(RoundedRectangle(cornerRadius: 10).fill(done ? palette.primarySoft.opacity(0.45) : palette.background))
                            }
                            .buttonStyle(.plain)
                            .accessibilityLabel("\(task.title)，\(done ? "已完成" : "未完成")")
                        }
                    }
                    .padding(14)
                    .background(RoundedRectangle(cornerRadius: 16).fill(palette.surface))
                    .overlay(RoundedRectangle(cornerRadius: 16).strokeBorder(palette.line.opacity(0.65), lineWidth: 1))
                }
                Text("项目完成度保存在当前账号的这台设备上，和网页课堂共用同一份任务顺序。")
                    .campusFont(.micro).foregroundStyle(palette.muted)
            }
            .padding(16)
        }
    }
}

// MARK: - Simulation

struct NativeSimulationPanel: View {
    @Environment(\.campus) private var palette
    let simulation: ClassroomSimulation
    let model: NativeClassroomModel

    var body: some View {
        let state = model.simulationState ?? simulation.initialState()
        ScrollView {
            VStack(alignment: .leading, spacing: 16) {
                VStack(alignment: .leading, spacing: 5) {
                    Text(simulation.title).campusFont(.headline).foregroundStyle(palette.textPrimary)
                    Text("拖动参数后运行，结果由课堂里的公式计算，不请求外部服务。")
                        .campusFont(.caption).foregroundStyle(palette.muted)
                }
                ForEach(simulation.parameters) { parameter in
                    VStack(alignment: .leading, spacing: 6) {
                        HStack {
                            Text(parameter.label).campusFont(.bodySmall).foregroundStyle(palette.textPrimary)
                            Spacer()
                            Text("\(format(state.values[parameter.id] ?? parameter.initial))\(parameter.unit)")
                                .campusFont(.caption).foregroundStyle(palette.muted)
                        }
                        Slider(value: Binding(
                            get: { state.values[parameter.id] ?? parameter.initial },
                            set: { model.simulate(.set(id: parameter.id, value: $0)) }
                        ), in: parameter.min...max(parameter.min + 0.001, parameter.max), step: parameter.step)
                        .tint(palette.accent)
                        .accessibilityLabel(parameter.label)
                    }
                    .padding(12)
                    .background(RoundedRectangle(cornerRadius: 12).fill(palette.surface))
                }
                HStack(spacing: 10) {
                    CampusPrimaryButton(title: "运行", systemImage: "play.fill") {
                        model.simulate(.run)
                    }
                    CampusSecondaryButton(title: "重置", systemImage: "arrow.counterclockwise") {
                        model.simulate(.reset)
                    }
                }
                if let result = state.result {
                    VStack(alignment: .leading, spacing: 6) {
                        Text(result.label).campusFont(.caption).foregroundStyle(palette.muted)
                        Text(format(result.value)).campusFont(.title).foregroundStyle(palette.primary)
                    }
                    .padding(14)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(RoundedRectangle(cornerRadius: 14).fill(palette.primarySoft.opacity(0.6)))
                }
                Text("公式：\(simulation.formula.isEmpty ? "未提供" : simulation.formula)")
                    .campusFont(.micro).foregroundStyle(palette.muted)
            }
            .padding(16)
        }
    }

    private func format(_ value: Double) -> String {
        value.rounded() == value ? String(format: "%.0f", value) : String(format: "%.2f", value)
    }
}

// MARK: - Sandbox

/// 受限 Web 容器：非持久存储、无原生桥、只允许同一来源的顶层跳转。
struct ClassroomSandboxView: View {
    @Environment(\.campus) private var palette
    let html: String?
    let url: URL?
    var onBlocked: (String) -> Void

    var body: some View {
        VStack(spacing: 8) {
            HStack(spacing: 6) {
                Image(systemName: "lock.shield").font(.system(size: 12)).foregroundStyle(palette.muted)
                Text("受限互动页 · 不读取本站登录状态").campusFont(.micro).foregroundStyle(palette.muted)
                Spacer()
            }
            ClassroomSandboxWebView(html: html, url: url, onBlocked: onBlocked)
                .clipShape(RoundedRectangle(cornerRadius: 14))
                .overlay(RoundedRectangle(cornerRadius: 14).strokeBorder(palette.line.opacity(0.7), lineWidth: 1))
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
    }
}

struct ClassroomSandboxWebView: UIViewRepresentable {
    let html: String?
    let url: URL?
    let onBlocked: (String) -> Void

    func makeCoordinator() -> Coordinator { Coordinator(allowedOrigin: url, onBlocked: onBlocked) }

    func makeUIView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
        configuration.defaultWebpagePreferences.allowsContentJavaScript = true
        configuration.preferences.javaScriptCanOpenWindowsAutomatically = false
        let view = WKWebView(frame: .zero, configuration: configuration)
        view.navigationDelegate = context.coordinator
        view.isOpaque = false
        view.backgroundColor = .clear
        view.scrollView.bounces = true
        if let html, ClassroomSandboxPolicy.allowsHTML(html) {
            view.loadHTMLString(html, baseURL: nil)
        } else if let url, ClassroomSandboxPolicy.allowsURL(url) {
            view.load(URLRequest(url: url))
        }
        return view
    }

    func updateUIView(_ view: WKWebView, context: Context) {}

    @MainActor final class Coordinator: NSObject, WKNavigationDelegate {
        private let allowedOrigin: URL?
        private let onBlocked: (String) -> Void

        init(allowedOrigin: URL?, onBlocked: @escaping (String) -> Void) {
            self.allowedOrigin = allowedOrigin
            self.onBlocked = onBlocked
        }

        func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction,
                     decisionHandler: @escaping (WKNavigationActionPolicy) -> Void) {
            guard let target = navigationAction.request.url else {
                decisionHandler(.allow)
                return
            }
            if navigationAction.targetFrame == nil, let origin = allowedOrigin {
                if let reason = ClassroomSandboxPolicy.blockedNavigationReason(target: target, allowedOrigin: origin) {
                    onBlocked(reason)
                    decisionHandler(.cancel)
                    return
                }
            }
            if navigationAction.navigationType == .linkActivated, let origin = allowedOrigin,
               let reason = ClassroomSandboxPolicy.blockedNavigationReason(target: target, allowedOrigin: origin) {
                onBlocked(reason)
                decisionHandler(.cancel)
                return
            }
            decisionHandler(.allow)
        }
    }
}

// MARK: - Unavailable

struct NativeUnsupportedPanel: View {
    @Environment(\.campus) private var palette
    let title: String
    let detail: String

    var body: some View {
        VStack(spacing: 11) {
            Image(systemName: "rectangle.on.rectangle.slash")
                .font(.system(size: 30, weight: .light))
                .foregroundStyle(palette.muted)
            Text(title).campusFont(.subtitle).foregroundStyle(palette.textPrimary)
            Text(detail).campusFont(.caption).foregroundStyle(palette.muted)
                .multilineTextAlignment(.center)
            Text("这页仍保留在课堂进度里，翻页或退出不会丢失位置。")
                .campusFont(.micro).foregroundStyle(palette.muted)
        }
        .padding(26)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
