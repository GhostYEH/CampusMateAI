import SwiftUI
import UIKit

/// Top-level destinations reachable from the twilight campus scene. Secondary
/// pages keep using `NavigationLink` with concrete views, matching how the
/// Android `NavHost` mixes root portals with nested destinations.
enum CampusRoute: Hashable {
    case courses
    case tasks
    case notices
    case exams
    case community
    case profile
    case focus
    case focusHistory
    case classroomHub
    case counselor
    case learningRooms
    case goals
    case finalReview
    case courseResearch
    case settings
    case account
    case files
    case favorites
    case qrLogin
    case chaoxing
    case eduSystem
    case helpFeedback
    case notificationSettings
}

// MARK: - Chrome

/// Secondary navigation bar from `StickySecondaryNavigation`: a 44 pt glass
/// back control and a 20 pt bold title, floating above the page.
struct CampusSecondaryBar: View {
    @Environment(\.campus) private var palette
    let title: String
    var tint: Color?
    let onBack: () -> Void

    var body: some View {
        HStack(spacing: 12) {
            CampusBackButton(tint: tint, action: onBack)
            Text(title)
                .campusFont(.title)
                .foregroundStyle(tint ?? palette.textPrimary)
                .lineLimit(1)
                .minimumScaleFactor(0.8)
            Spacer(minLength: 0)
        }
        .padding(.horizontal, 16)
        .frame(height: CampusMetric.navBarHeight)
    }
}

/// Page scaffold for secondary destinations: bar + scrolling content area.
struct CampusSecondaryScaffold<Content: View>: View {
    @Environment(\.campus) private var palette
    @Environment(\.dismiss) private var dismiss
    let title: String
    var tint: Color?
    var background: Color?
    @ViewBuilder var content: Content

    var body: some View {
        VStack(spacing: 0) {
            CampusSecondaryBar(title: title, tint: tint) { dismiss() }
            content
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background {
            if let background { background.ignoresSafeArea() }
            else { CampusAmbientBackground() }
        }
        .toolbar(.hidden, for: .navigationBar)
        .interactivePopGestureEnabled()
    }
}

/// Keeps the iOS edge-swipe back gesture alive while the system navigation bar
/// is hidden, so the Android chrome does not cost users the native gesture.
struct InteractivePopGestureEnabler: UIViewControllerRepresentable {
    func makeUIViewController(context: Context) -> UIViewController {
        Controller()
    }
    func updateUIViewController(_ controller: UIViewController, context: Context) {
        (controller as? Controller)?.enable()
    }
    final class Controller: UIViewController {
        override func didMove(toParent parent: UIViewController?) {
            super.didMove(toParent: parent)
            enable()
        }
        override func viewDidAppear(_ animated: Bool) {
            super.viewDidAppear(animated)
            enable()
        }
        func enable() {
            guard let navigation = navigationController ?? parent?.navigationController,
                  let gesture = navigation.interactivePopGestureRecognizer else { return }
            gesture.isEnabled = navigation.viewControllers.count > 1
            // Keep the system delegate; overriding it makes the recognizer
            // compete with taps on controls near the leading edge.
        }
    }
}

extension View {
    func interactivePopGestureEnabled() -> some View {
        background(InteractivePopGestureEnabler().frame(width: 0, height: 0))
    }

    /// Hides the system bar for screens that draw the Android header themselves.
    func campusImmersive() -> some View {
        toolbar(.hidden, for: .navigationBar)
            .interactivePopGestureEnabled()
    }
}

// MARK: - Root routing

struct CampusRootView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.campus) private var palette
    @State private var path: [CampusRoute] = []

    var body: some View {
        NavigationStack(path: $path) {
            TwilightHomeView()
                .navigationDestination(for: CampusRoute.self) { route in
                    CampusRouteView(route: route)
                }
        }
        .tint(palette.primary)
        .id(app.scope)
    }
}

struct CampusRouteView: View {
    let route: CampusRoute

    var body: some View {
        switch route {
        case .courses: CoursesView()
        case .tasks: TasksView()
        case .notices: NoticesView()
        case .exams: ExamsView()
        case .community: CommunityView()
        case .profile: ProfileView()
        case .focus: FocusSetupView()
        case .focusHistory: FocusHistoryView()
        case .classroomHub: ClassroomHubView()
        case .counselor: AssistantView()
        case .learningRooms: LearningRoomsView()
        case .goals: GoalsView()
        case .finalReview: FinalReviewView()
        case .courseResearch: CourseResearchView()
        case .settings: SettingsView()
        case .account: AccountView()
        case .files: PersonalHubView()
        case .favorites: PersonalHubView(favorites: true)
        case .qrLogin: QRLoginView()
        case .chaoxing: ChaoxingView()
        case .eduSystem: EduSystemView()
        case .helpFeedback: HelpFeedbackView()
        case .notificationSettings: NotificationSourcesView()
        }
    }
}

/// Shared chrome for the agent/workflow pages: the Android secondary bar, the
/// ambient page background and a clear list surface. These screens keep their
/// existing data flows; only the surrounding chrome is unified.
struct CampusWorkflowChrome: ViewModifier {
    @Environment(\.campus) private var palette
    @Environment(\.dismiss) private var dismiss
    let title: String
    var actionTitle: String?
    var action: (() -> Void)?

    func body(content: Content) -> some View {
        content
            .scrollContentBackground(.hidden)
            .background(CampusAmbientBackground())
            .safeAreaInset(edge: .top) {
                HStack(spacing: 10) {
                    CampusBackButton { dismiss() }
                    Text(title)
                        .campusFont(.title)
                        .foregroundStyle(palette.textPrimary)
                        .lineLimit(1)
                    Spacer()
                    if let actionTitle, let action {
                        Button(action: action) {
                            Image(systemName: "plus")
                                .font(.system(size: 18, weight: .semibold))
                                .frame(width: 44, height: 44)
                        }
                        .accessibilityLabel(actionTitle)
                    }
                }
                .padding(.horizontal, 16)
                .frame(minHeight: 56)
                .background(.ultraThinMaterial)
            }
            .toolbar(.hidden, for: .navigationBar)
            .interactivePopGestureEnabled()
    }
}

extension View {
    func campusWorkflowChrome(_ title: String, actionTitle: String? = nil, action: (() -> Void)? = nil) -> some View {
        modifier(CampusWorkflowChrome(title: title, actionTitle: actionTitle, action: action))
    }
}
