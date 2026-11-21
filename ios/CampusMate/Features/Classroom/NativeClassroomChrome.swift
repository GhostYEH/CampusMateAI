import SwiftUI

enum NativeClassroomAppearance {
    // Matches the Android native classroom palette and the shared evening interior asset.
    static let board: CampusPalette = {
        var palette = CampusPalette.dark
        palette.background = Color(hex: 0x101F2B)
        palette.surface = Color(hex: 0x192F39)
        palette.line = Color(hex: 0x3E535E)
        palette.primary = Color(hex: 0xDAB27A)
        palette.primarySoft = Color(hex: 0x2D484A)
        palette.accent = Color(hex: 0xB4D2C3)
        palette.textPrimary = Color(hex: 0xF2E9D3)
        palette.muted = Color(hex: 0xB6C7CB)
        return palette
    }()

    static let paper: CampusPalette = {
        var palette = CampusPalette.classroom
        palette.primary = Color(hex: 0x27594E)
        palette.primarySoft = Color(hex: 0xE6EEDD)
        palette.accent = Color(hex: 0x865526)
        palette.textPrimary = Color(hex: 0x213832)
        palette.muted = Color(hex: 0x53685F)
        palette.line = Color(hex: 0xD7C8AC)
        palette.surface = Color(hex: 0xFFFBF1)
        palette.background = Color(hex: 0xF3E7D2)
        palette.dangerText = Color(hex: 0x9A4032)
        palette.success = Color(hex: 0x35694F)
        palette.successText = palette.success
        return palette
    }()

    static let wood = Color(hex: 0xAD7A50)
}

struct NativeClassroomBackdrop: View {
    var body: some View {
        GeometryReader { geometry in
            Image("classroom_evening_interior")
                .resizable()
                .scaledToFill()
                .frame(width: geometry.size.width, height: geometry.size.height)
                .clipped()
                .overlay {
                    LinearGradient(colors: [
                        Color(hex: 0x101D2B).opacity(0.30),
                        Color(hex: 0x101D2B).opacity(0.40),
                        Color(hex: 0x182638).opacity(0.71)
                    ], startPoint: .top, endPoint: .bottom)
                }
        }
        .ignoresSafeArea()
        .accessibilityHidden(true)
    }
}

struct NativeClassroomGoldButton: ButtonStyle {
    @Environment(\.campus) private var palette
    @Environment(\.isEnabled) private var isEnabled

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: 14, weight: .semibold))
            .lineLimit(1)
            .foregroundStyle(isEnabled ? palette.background : palette.muted.opacity(0.70))
            .padding(.horizontal, 11)
            .frame(minHeight: 44)
            .background(isEnabled ? palette.primary : palette.primarySoft, in: RoundedRectangle(cornerRadius: 10))
            .opacity(configuration.isPressed ? 0.8 : 1)
    }
}

struct NativeClassroomSlideToolbar: View {
    @Environment(\.campus) private var palette
    let hasNotes: Bool
    let showingCanvas: Bool
    let lectureActive: Bool
    let stretches: Bool
    let stacked: Bool
    @Binding var readNotes: Bool
    @Binding var zoom: CGFloat

    var body: some View {
        if stacked && hasNotes && showingCanvas {
            VStack(alignment: .leading, spacing: 2) {
                modePicker
                zoomControls.frame(maxWidth: .infinity, alignment: .trailing)
            }
        } else {
            HStack(spacing: 6) {
                if hasNotes { modePicker }
                if stretches { Spacer(minLength: 0) }
                if showingCanvas { zoomControls }
            }
        }
    }

    private var modePicker: some View {
        HStack(spacing: 8) {
            mode("PPT", selected: showingCanvas) { readNotes = false }
            mode("讲义", selected: !showingCanvas) { readNotes = true }
                .disabled(lectureActive)
                .opacity(lectureActive ? 0.55 : 1)
        }
    }

    private func mode(_ title: String, selected: Bool, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Text(title)
                .font(.system(size: 14, weight: .semibold))
                .padding(.horizontal, 12)
                .frame(height: 32)
                .foregroundStyle(selected ? palette.background : palette.muted)
                .background(selected ? palette.primary : .clear, in: RoundedRectangle(cornerRadius: 8))
                .overlay(RoundedRectangle(cornerRadius: 8).strokeBorder(selected ? .clear : palette.line))
                .frame(minHeight: 44)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityAddTraits(selected ? .isSelected : [])
    }

    private var zoomControls: some View {
        HStack(spacing: 0) {
            zoomButton("minus", label: "缩小课件") { zoom = max(0.7, zoom - 0.1) }
            Text("\(Int((zoom * 100).rounded()))%")
                .font(.system(size: 12).monospacedDigit())
                .foregroundStyle(palette.textPrimary)
                .accessibilityLabel("课件缩放 \(Int((zoom * 100).rounded()))%")
            zoomButton("plus", label: "放大课件") { zoom = min(1.6, zoom + 0.1) }
            zoomButton("arrow.up.left.and.arrow.down.right", label: "整页") { zoom = 1 }
        }
    }

    private func zoomButton(_ icon: String, label: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: icon)
                .font(.system(size: 16, weight: .semibold))
                .foregroundStyle(palette.primary)
                .frame(width: 44, height: 44)
                .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .accessibilityLabel(label)
    }
}

enum NativeClassroomPanel: String, Identifiable {
    case directory, narration, classmates, whiteboard, diagnostics

    var id: String { rawValue }

    var label: String {
        switch self {
        case .directory: "目录"
        case .narration: "讲解"
        case .classmates: "同学"
        case .whiteboard: "白板"
        case .diagnostics: "性能"
        }
    }

    var title: String {
        switch self {
        case .directory: "课堂地图"
        case .narration: "讲解与朗读"
        case .classmates: "AI 同学"
        case .whiteboard: "白板"
        case .diagnostics: "性能样本"
        }
    }

    var symbol: String {
        switch self {
        case .directory: "book.fill"
        case .narration: "speaker.wave.2.fill"
        case .classmates: "person.3.fill"
        case .whiteboard: "square.and.pencil"
        case .diagnostics: "speedometer"
        }
    }
}

struct NativeClassroomPager: View {
    @Environment(\.campus) private var palette
    let index: Int
    let count: Int
    let compact: Bool
    let goTo: @MainActor (Int) -> Void
    let onPanel: @MainActor (NativeClassroomPanel) -> Void
    @State private var dragValue: Double?

    var body: some View {
        VStack(spacing: 0) {
            Rectangle().fill(palette.line).frame(height: 1)
            if compact {
                HStack(spacing: 8) {
                    pageControls
                    Rectangle().fill(palette.line).frame(width: 1, height: 30)
                    tools.frame(width: 216)
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 3)
            } else {
                VStack(spacing: 0) {
                    pageControls
                    Rectangle().fill(palette.line.opacity(0.65)).frame(height: 1)
                    tools
                }
                .padding(.horizontal, 10)
                .padding(.vertical, 3)
            }
        }
        .background { palette.background.ignoresSafeArea(edges: .bottom) }
    }

    private var pageControls: some View {
        HStack(spacing: 6) {
            Button { goTo(index - 1) } label: {
                Text("上一页")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(index > 0 ? palette.primary : palette.muted.opacity(0.50))
                    .lineLimit(1)
                    .padding(.horizontal, 6)
                    .frame(minHeight: 44)
                    .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .disabled(index <= 0)
            .accessibilityIdentifier("native.classroom.previous")

            VStack(spacing: 0) {
                Text("\(index + 1) / \(count)")
                    .font(.system(size: 11, weight: .semibold).monospacedDigit())
                    .foregroundStyle(palette.textPrimary)
                if count > 1 {
                    Slider(value: Binding(
                        get: { dragValue ?? Double(index) },
                        set: { dragValue = $0 }
                    ), in: 0...Double(count - 1), step: 1, onEditingChanged: { editing in
                        if !editing, let value = dragValue {
                            dragValue = nil
                            goTo(Int(value.rounded()))
                        }
                    })
                    .tint(palette.primary)
                    .frame(height: 29)
                    .accessibilityLabel("跳页")
                    .accessibilityValue("第 \(index + 1) 页，共 \(count) 页")
                    .accessibilityAdjustableAction { direction in
                        switch direction {
                        case .increment: goTo(min(count - 1, index + 1))
                        case .decrement: goTo(max(0, index - 1))
                        @unknown default: break
                        }
                    }
                }
            }
            .frame(maxWidth: .infinity)

            Button { goTo(index + 1) } label: {
                Label("下一页", systemImage: "arrow.right").labelStyle(NativeClassroomForwardLabelStyle())
            }
            .buttonStyle(NativeClassroomGoldButton())
            .disabled(index + 1 >= count)
            .accessibilityIdentifier("native.classroom.next")
        }
    }

    private var tools: some View {
        HStack(spacing: 0) {
            ForEach([NativeClassroomPanel.directory, .narration, .classmates, .whiteboard]) { tool in
                Button { onPanel(tool) } label: {
                    VStack(spacing: 3) {
                        Image(systemName: tool.symbol)
                            .font(.system(size: 18, weight: .semibold))
                            .foregroundStyle(palette.accent)
                        Text(tool.label)
                            .font(.system(size: 11, weight: .medium))
                            .foregroundStyle(palette.textPrimary)
                    }
                    .frame(maxWidth: .infinity, minHeight: 48)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                .accessibilityIdentifier("native.classroom.\(tool == .directory ? "outline" : tool.rawValue)")
            }
        }
    }
}

private struct NativeClassroomForwardLabelStyle: LabelStyle {
    func makeBody(configuration: Configuration) -> some View {
        HStack(spacing: 4) {
            configuration.title
            configuration.icon.font(.system(size: 14, weight: .semibold))
        }
    }
}
