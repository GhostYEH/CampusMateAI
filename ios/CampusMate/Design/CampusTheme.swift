import SwiftUI
import UIKit

// MARK: - Palette

/// Mirrors `android/.../ui/theme/Color.kt`. The values are the product's
/// design tokens, not a new iOS palette: every screen in the Android client
/// reads from this same table.
struct CampusPalette: Equatable {
    var primary: Color
    var primaryHover: Color
    var primarySoft: Color
    var accent: Color
    var danger: Color
    var success: Color
    var textPrimary: Color
    var muted: Color
    var line: Color
    var surface: Color
    var background: Color
    var dangerText: Color
    var successText: Color
    var loginBackground: Color
    var sidebarActiveBackground: Color
    var avatarBackground: Color
    var chatAssistantBackground: Color
    var chatUserBackground: Color
    var robotAvatarBackground: Color
    var unreadDot: Color
    var pendingBadgeBackground: Color
    var pendingBadgeText: Color
    var focusRing: Color
    var inputBorder: Color
    var inputFocusBorder: Color
    var alertErrorBackground: Color
    var alertErrorText: Color
    var alertInfoBackground: Color
    var alertInfoText: Color

    static let light = CampusPalette(
        primary: Color(hex: 0x285B4B),
        primaryHover: Color(hex: 0x1B473B),
        primarySoft: Color(hex: 0xE4EEE5),
        accent: Color(hex: 0xE08A4E),
        danger: Color(hex: 0xC25450),
        success: Color(hex: 0x4E8C6A),
        textPrimary: Color(hex: 0x1B2730),
        muted: Color(hex: 0x667784),
        line: Color(hex: 0xD7DED5),
        surface: Color(hex: 0xFFFEF8),
        background: Color(hex: 0xF1F3EA),
        dangerText: Color(hex: 0xE35F42),
        successText: Color(hex: 0x4E8C6A),
        loginBackground: Color(hex: 0x071424),
        sidebarActiveBackground: Color(hex: 0xE4EEE5),
        avatarBackground: Color(hex: 0xDEEBDF),
        chatAssistantBackground: Color(hex: 0xEAF0E8),
        chatUserBackground: Color(hex: 0xF4F0E5),
        robotAvatarBackground: Color(hex: 0xDEEBDF),
        unreadDot: Color(hex: 0xED6E52),
        pendingBadgeBackground: Color(hex: 0xED6E52),
        pendingBadgeText: .white,
        focusRing: Color(hex: 0x7AB6DC),
        inputBorder: Color(hex: 0xCAD5DD),
        inputFocusBorder: Color(hex: 0x285B4B),
        alertErrorBackground: Color(hex: 0xF6DAD8),
        alertErrorText: Color(hex: 0x8E3430),
        alertInfoBackground: Color(hex: 0xE4EEE5),
        alertInfoText: Color(hex: 0x1B473B)
    )

    /// Blue-teal night palette from `DarkCampusColors`.
    static let dark = CampusPalette(
        primary: Color(hex: 0x9CC7D0),
        primaryHover: Color(hex: 0xB8DEE3),
        primarySoft: Color(hex: 0x1C3C45),
        accent: Color(hex: 0xF3B078),
        danger: Color(hex: 0xE68780),
        success: Color(hex: 0x79B492),
        textPrimary: Color(hex: 0xE8F0F4),
        muted: Color(hex: 0xA6B5BE),
        line: Color(hex: 0x2B424A),
        surface: Color(hex: 0x14272E),
        background: Color(hex: 0x09161C),
        dangerText: Color(hex: 0xFFB4AB),
        successText: Color(hex: 0x91D0AA),
        loginBackground: Color(hex: 0x071424),
        sidebarActiveBackground: Color(hex: 0x1C3C45),
        avatarBackground: Color(hex: 0x244850),
        chatAssistantBackground: Color(hex: 0x19343C),
        chatUserBackground: Color(hex: 0x234A54),
        robotAvatarBackground: Color(hex: 0x244850),
        unreadDot: Color(hex: 0xFF8C72),
        pendingBadgeBackground: Color(hex: 0xFF8C72),
        pendingBadgeText: Color(hex: 0x1C2528),
        focusRing: Color(hex: 0x83C9D6),
        inputBorder: Color(hex: 0x38525B),
        inputFocusBorder: Color(hex: 0x9CC7D0),
        alertErrorBackground: Color(hex: 0x4A2928),
        alertErrorText: Color(hex: 0xFFB4AB),
        alertInfoBackground: Color(hex: 0x1C3C45),
        alertInfoText: Color(hex: 0xB8DEE3)
    )
}

/// Scene tokens used by the twilight campus home, the library and the focus
/// rooms. These live outside the palette because they are illustration-bound.
enum CampusScene {
    static let ink = Color(hex: 0x101F3F)
    static let cream = Color(hex: 0xFFEBCB)
    static let libraryCream = Color(hex: 0xF5F2E8)
    static let libraryGreen = Color(hex: 0x214E3D)
    static let libraryPaper = Color(hex: 0xF5F0E3, opacity: 234.0 / 255.0)
    static let libraryShelfEdge = Color(hex: 0xE4BD7C)
    static let libraryGold = Color(hex: 0xEBD5A8)
    static let twilightDusk = Color(hex: 0x14243D)
    static let nightGlass = Color(hex: 0x203B45)
    static let robotGradientTop = Color(hex: 0x24477B)
    static let robotGradientBottom = Color(hex: 0x536DED)
}

/// `TaskJournalStyle.kt` tokens.
enum CampusJournal {
    static let ink = Color(hex: 0x263B50)
    static let paper = Color(hex: 0xF7F2E8)
    static let muted = Color(hex: 0x596B72)
    static let amber = Color(hex: 0xC58B55)
    static let night = Color(hex: 0x263B50)
    static let clay = Color(hex: 0xAA684D)
    static let blue = Color(hex: 0x6D8B9B)
    static let shelfShadow = Color(hex: 0x3A241C)
}

// MARK: - Environment

private struct CampusPaletteKey: EnvironmentKey {
    static let defaultValue = CampusPalette.light
}

extension EnvironmentValues {
    var campus: CampusPalette {
        get { self[CampusPaletteKey.self] }
        set { self[CampusPaletteKey.self] = newValue }
    }
}

// MARK: - Typography

/// Named text roles mirroring `AppTypography`. Sizes scale with Dynamic Type
/// through `@ScaledMetric`, so the Android hierarchy survives accessibility
/// settings instead of being replaced by generic system styles.
enum CampusTextRole {
    case display, hero, headline, title, subtitle, body, bodySmall, caption, label, micro

    var size: CGFloat {
        switch self {
        case .display: 32
        case .hero: 28
        case .headline: 22
        case .title: 20
        case .subtitle: 16
        case .body: 14
        case .bodySmall: 13
        case .caption: 12
        case .label: 11
        case .micro: 10
        }
    }

    var weight: Font.Weight {
        switch self {
        case .display, .hero, .headline, .title: .bold
        case .subtitle: .semibold
        case .body: .regular
        case .bodySmall: .regular
        case .caption: .medium
        case .label: .semibold
        case .micro: .bold
        }
    }

    var relativeTo: Font.TextStyle {
        switch self {
        case .display, .hero, .headline: .title
        case .title, .subtitle: .title3
        case .body: .body
        case .bodySmall: .subheadline
        case .caption, .label: .caption
        case .micro: .caption2
        }
    }
}

private struct CampusFontModifier: ViewModifier {
    @ScaledMetric private var size: CGFloat
    private let weight: Font.Weight
    init(_ role: CampusTextRole) {
        _size = ScaledMetric(wrappedValue: role.size, relativeTo: role.relativeTo)
        weight = role.weight
    }
    func body(content: Content) -> some View {
        content.font(.system(size: size, weight: weight))
    }
}

extension View {
    func campusFont(_ role: CampusTextRole) -> some View { modifier(CampusFontModifier(role)) }

    /// Applies the palette to a subtree and keeps the status bar legible.
    func campusPalette(_ palette: CampusPalette) -> some View {
        environment(\.campus, palette)
    }
}

// MARK: - Metrics

enum CampusMetric {
    static let pageInset: CGFloat = 20
    static let cardRadius: CGFloat = 18
    static let panelRadius: CGFloat = 22
    static let controlRadius: CGFloat = 14
    static let chipRadius: CGFloat = 999
    static let navBarHeight: CGFloat = 60
    static let backButton: CGFloat = 44
    /// Android reserves 68 + 4 + 8 dp for the floating dock.
    static let dockReserved: CGFloat = 80
}

// MARK: - Color helper

extension Color {
    init(hex: UInt32, opacity: Double = 1) {
        self.init(
            .sRGB,
            red: Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8) & 0xFF) / 255,
            blue: Double(hex & 0xFF) / 255,
            opacity: opacity
        )
    }
}

// MARK: - Surfaces

/// Glass panel equivalent of `Modifier.campusGlass`. iOS uses the system
/// material for real backdrop blur and keeps the Android tint, hairline border
/// and warm corner highlight on top.
struct CampusGlassPanel: ViewModifier {
    @Environment(\.campus) private var palette
    var radius: CGFloat = CampusMetric.cardRadius
    var tint: Color?
    var strokeOpacity: Double = 0.38
    var elevated: Bool = false

    func body(content: Content) -> some View {
        content
            .background {
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .fill(.ultraThinMaterial)
                    .overlay {
                        RoundedRectangle(cornerRadius: radius, style: .continuous)
                            .fill((tint ?? palette.surface).opacity(0.62))
                    }
            }
            .overlay {
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .strokeBorder(Color.white.opacity(strokeOpacity), lineWidth: 1)
            }
            .clipShape(RoundedRectangle(cornerRadius: radius, style: .continuous))
            .shadow(color: Color.black.opacity(elevated ? 0.14 : 0.06), radius: elevated ? 18 : 8, y: elevated ? 8 : 3)
    }
}

extension View {
    func campusGlass(radius: CGFloat = CampusMetric.cardRadius, tint: Color? = nil, elevated: Bool = false) -> some View {
        modifier(CampusGlassPanel(radius: radius, tint: tint, elevated: elevated))
    }
}

/// White card used by the light content pages (`CampusCard`).
struct CampusCard<Content: View>: View {
    @Environment(\.campus) private var palette
    var padding: CGFloat = 16
    var radius: CGFloat = CampusMetric.cardRadius
    @ViewBuilder var content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 0) { content }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(padding)
            .background {
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .fill(palette.surface.opacity(0.94))
            }
            .overlay {
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .strokeBorder(palette.line.opacity(0.62), lineWidth: 1)
            }
            .clipShape(RoundedRectangle(cornerRadius: radius, style: .continuous))
    }
}

/// Ambient page background from `CampusGlassScene`: a soft vertical wash with
/// a primary glow top-right and a violet glow bottom-left.
struct CampusAmbientBackground: View {
    @Environment(\.campus) private var palette
    var body: some View {
        ZStack {
            LinearGradient(colors: [palette.background, palette.background.opacity(0.92), palette.primarySoft.opacity(0.55)],
                           startPoint: .top, endPoint: .bottom)
            RadialGradient(colors: [palette.primary.opacity(0.16), .clear],
                           center: UnitPoint(x: 0.86, y: 0.1), startRadius: 0, endRadius: 420)
            RadialGradient(colors: [Color(hex: 0x8E7CFF).opacity(0.10), .clear],
                           center: UnitPoint(x: 0.08, y: 0.78), startRadius: 0, endRadius: 360)
        }
        .ignoresSafeArea()
    }
}

// MARK: - Text & tags

struct CampusSectionHeader: View {
    @Environment(\.campus) private var palette
    let title: String
    var subtitle: String?
    var trailing: String?

    var body: some View {
        HStack(alignment: .firstTextBaseline) {
            VStack(alignment: .leading, spacing: 3) {
                Text(title).campusFont(.subtitle).foregroundStyle(palette.textPrimary)
                if let subtitle { Text(subtitle).campusFont(.caption).foregroundStyle(palette.muted) }
            }
            Spacer(minLength: 8)
            if let trailing { Text(trailing).campusFont(.caption).foregroundStyle(palette.muted) }
        }
        .accessibilityElement(children: .combine)
    }
}

enum CampusStatusTone { case info, success, warning, danger, neutral }

struct CampusStatusTag: View {
    @Environment(\.campus) private var palette
    let text: String
    var tone: CampusStatusTone = .neutral

    private var colors: (Color, Color) {
        switch tone {
        case .info: (palette.primarySoft, palette.primary)
        case .success: (palette.success.opacity(0.14), palette.success)
        case .warning: (palette.accent.opacity(0.14), palette.accent)
        case .danger: (palette.dangerText.opacity(0.12), palette.dangerText)
        case .neutral: (palette.background, palette.muted)
        }
    }

    var body: some View {
        Text(text)
            .campusFont(.micro)
            .foregroundStyle(colors.1)
            .padding(.horizontal, 9)
            .padding(.vertical, 4)
            .background(Capsule().fill(colors.0))
    }
}

// MARK: - Controls

struct CampusPrimaryButton: View {
    @Environment(\.campus) private var palette
    @Environment(\.colorScheme) private var colorScheme
    let title: String
    var systemImage: String?
    var loading = false
    var enabled = true
    let action: () -> Void

    var body: some View {
        Button {
            guard enabled && !loading else { return }
            CampusHaptics.tap()
            action()
        } label: {
            HStack(spacing: 8) {
                if loading { ProgressView().tint(colorScheme == .dark ? palette.background : .white).controlSize(.small) }
                else if let systemImage { Image(systemName: systemImage).font(.system(size: 15, weight: .semibold)) }
                Text(loading ? "请稍候…" : title).campusFont(.subtitle)
            }
            .foregroundStyle(colorScheme == .dark ? palette.background : .white)
            .frame(maxWidth: .infinity)
            .frame(minHeight: 48)
            .fixedSize(horizontal: false, vertical: true)
            .background(
                RoundedRectangle(cornerRadius: CampusMetric.controlRadius, style: .continuous)
                    .fill(palette.primary.opacity(enabled ? 1 : 0.45))
            )
        }
        .buttonStyle(CampusPressStyle())
        .disabled(!enabled || loading)
        .accessibilityLabel(title)
    }
}

struct CampusSecondaryButton: View {
    @Environment(\.campus) private var palette
    let title: String
    var systemImage: String?
    var enabled = true
    let action: () -> Void

    var body: some View {
        Button {
            guard enabled else { return }
            CampusHaptics.tap()
            action()
        } label: {
            HStack(spacing: 8) {
                if let systemImage { Image(systemName: systemImage).font(.system(size: 14, weight: .semibold)) }
                Text(title).campusFont(.body)
            }
            .foregroundStyle(palette.primary)
            .frame(maxWidth: .infinity)
            .frame(minHeight: 44)
            .fixedSize(horizontal: false, vertical: true)
            .background(
                RoundedRectangle(cornerRadius: CampusMetric.controlRadius, style: .continuous)
                    .fill(palette.primarySoft.opacity(0.7))
            )
            .overlay(
                RoundedRectangle(cornerRadius: CampusMetric.controlRadius, style: .continuous)
                    .strokeBorder(palette.primary.opacity(0.28), lineWidth: 1)
            )
        }
        .buttonStyle(CampusPressStyle())
        .disabled(!enabled)
    }
}

struct CampusPressStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.975 : 1)
            .opacity(configuration.isPressed ? 0.92 : 1)
            .animation(.spring(response: 0.25, dampingFraction: 0.8), value: configuration.isPressed)
    }
}

/// Circular glass back control from `StickySecondaryNavigation`.
struct CampusBackButton: View {
    @Environment(\.campus) private var palette
    var tint: Color?
    /// Dark glass keeps a white chevron legible on photographic headers.
    var onDarkBackground = false
    var label = "返回"
    let action: () -> Void

    var body: some View {
        Button {
            CampusHaptics.tap()
            action()
        } label: {
            Image(systemName: "chevron.left")
                .font(.system(size: 17, weight: .semibold))
                .foregroundStyle(tint ?? (onDarkBackground ? .white : palette.textPrimary))
                .frame(width: CampusMetric.backButton, height: CampusMetric.backButton)
                .background {
                    if onDarkBackground {
                        Circle().fill(Color.black.opacity(0.30))
                    } else {
                        Circle().fill(.ultraThinMaterial)
                    }
                }
                .overlay(Circle().fill(onDarkBackground ? Color.white.opacity(0.06) : palette.surface.opacity(0.24)))
                .overlay(Circle().strokeBorder(Color.white.opacity(onDarkBackground ? 0.38 : 0.34), lineWidth: 1))
                .shadow(color: .black.opacity(0.18), radius: 6, y: 2)
        }
        .buttonStyle(CampusPressStyle())
        .accessibilityLabel(label)
    }
}

/// Filter chips (`FilterChipRow`).
struct CampusFilterChip: View {
    @Environment(\.campus) private var palette
    let title: String
    let isSelected: Bool
    let action: () -> Void

    var body: some View {
        Button {
            CampusHaptics.selection()
            action()
        } label: {
            Text(title)
                .campusFont(.caption)
                .fontWeight(isSelected ? .semibold : .regular)
                .foregroundStyle(isSelected ? palette.primary : palette.muted)
                .padding(.horizontal, 14)
                .padding(.vertical, 8)
                .background(Capsule().fill(isSelected ? palette.primarySoft : palette.surface))
                .overlay(Capsule().strokeBorder(isSelected ? palette.primary : palette.line, lineWidth: 1))
        }
        .buttonStyle(CampusPressStyle())
        .accessibilityAddTraits(isSelected ? [.isSelected, .isButton] : .isButton)
    }
}

/// Text field with the Android input border/focus treatment.
struct CampusTextField: View {
    @Environment(\.campus) private var palette
    let placeholder: String
    @Binding var text: String
    var systemImage: String?
    var secure = false
    var keyboard: UIKeyboardType = .default
    var contentType: UITextContentType?
    var submitLabel: SubmitLabel = .return
    var onSubmit: (() -> Void)?

    @FocusState private var focused: Bool

    var body: some View {
        HStack(spacing: 10) {
            if let systemImage {
                Image(systemName: systemImage)
                    .font(.system(size: 15, weight: .medium))
                    .foregroundStyle(focused ? palette.primary : palette.muted)
            }
            Group {
                if secure { SecureField(placeholder, text: $text) }
                else { TextField(placeholder, text: $text, axis: .vertical) }
            }
            .campusFont(.body)
            .foregroundStyle(palette.textPrimary)
            .textInputAutocapitalization(keyboard == .URL || keyboard == .emailAddress ? .never : .sentences)
            .autocorrectionDisabled(keyboard == .URL)
            .keyboardType(keyboard)
            .textContentType(contentType)
            .submitLabel(submitLabel)
            .focused($focused)
            .onSubmit { onSubmit?() }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .background(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(palette.surface.opacity(0.92))
        )
        .overlay(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .strokeBorder(focused ? palette.inputFocusBorder : palette.inputBorder, lineWidth: focused ? 1.6 : 1)
        )
    }
}

// MARK: - States

struct CampusLoadingState: View {
    @Environment(\.campus) private var palette
    var message = "正在加载…"
    var body: some View {
        VStack(spacing: 12) {
            ProgressView().tint(palette.primary).controlSize(.regular)
            Text(message).campusFont(.caption).foregroundStyle(palette.muted)
        }
        .frame(maxWidth: .infinity, minHeight: 160)
    }
}

struct CampusErrorState: View {
    @Environment(\.campus) private var palette
    let message: String
    var retry: (() -> Void)?

    var body: some View {
        VStack(spacing: 10) {
            Image(systemName: "exclamationmark.triangle")
                .font(.system(size: 30, weight: .light))
                .foregroundStyle(palette.dangerText)
            Text(message)
                .campusFont(.caption)
                .foregroundStyle(palette.muted)
                .multilineTextAlignment(.center)
            if let retry {
                Button("重试") { retry() }
                    .campusFont(.body)
                    .fontWeight(.semibold)
                    .foregroundStyle(.white)
                    .padding(.horizontal, 22)
                    .padding(.vertical, 9)
                    .background(Capsule().fill(palette.primary))
                    .padding(.top, 2)
            }
        }
        .frame(maxWidth: .infinity, minHeight: 160)
        .padding(.horizontal, 24)
    }
}

struct CampusEmptyState: View {
    @Environment(\.campus) private var palette
    let title: String
    var message: String?
    var systemImage = "tray"

    var body: some View {
        VStack(spacing: 9) {
            Image(systemName: systemImage)
                .font(.system(size: 28, weight: .light))
                .foregroundStyle(palette.muted.opacity(0.8))
            Text(title).campusFont(.body).fontWeight(.semibold).foregroundStyle(palette.textPrimary)
            if let message {
                Text(message).campusFont(.caption).foregroundStyle(palette.muted).multilineTextAlignment(.center)
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, 34)
        .padding(.horizontal, 20)
    }
}

// MARK: - Haptics

@MainActor enum CampusHaptics {
    static func tap() {
        UIImpactFeedbackGenerator(style: .light).impactOccurred()
    }
    static func selection() {
        UISelectionFeedbackGenerator().selectionChanged()
    }
    static func success() {
        UINotificationFeedbackGenerator().notificationOccurred(.success)
    }
    static func warning() {
        UINotificationFeedbackGenerator().notificationOccurred(.warning)
    }
}

// MARK: - Motion

enum CampusMotion {
    static let route = Animation.timingCurve(0.2, 0.8, 0.2, 1, duration: 0.34)
    static let settle = Animation.spring(response: 0.42, dampingFraction: 0.82)
    static let quick = Animation.easeOut(duration: 0.2)
}

extension View {
    /// Applies `repository.reduceMotion` semantics to SwiftUI animations.
    func campusAnimation(_ animation: Animation, reduceMotion: Bool, value: some Equatable) -> some View {
        self.animation(reduceMotion ? nil : animation, value: value)
    }
}

/// Full-bleed scene image that never influences the layout width. A plain
/// `scaledToFill` image reports its intrinsic size and can widen the enclosing
/// `ZStack`, which shifts every control on the page.
struct CampusSceneBackground: View {
    let name: String
    var body: some View {
        GeometryReader { proxy in
            Image(name)
                .resizable()
                .scaledToFill()
                .frame(width: proxy.size.width, height: proxy.size.height)
                .clipped()
        }
        .ignoresSafeArea()
        .allowsHitTesting(false)
    }
}
