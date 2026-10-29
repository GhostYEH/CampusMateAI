import Foundation
import Observation
import CampusCore

@MainActor @Observable
final class AppModel {
    private(set) var client: APIClient
    private(set) var session: Session?
    private(set) var serverURL: String
    private(set) var scope = UUID()
    private(set) var isRestoring = true
    var isSigningIn = false
    var errorMessage: String?
    var theme: String {
        didSet { UserDefaults.standard.set(theme, forKey: "campus.theme") }
    }
    var remindersEnabled: Bool {
        didSet {
            UserDefaults.standard.set(remindersEnabled, forKey: "campus.reminders")
            if !remindersEnabled { invalidateReminders() }
        }
    }
    var reduceMotion: Bool {
        didSet { UserDefaults.standard.set(reduceMotion, forKey: "campus.reduceMotion") }
    }
    @ObservationIgnored private var clientIdentity = UUID()
    @ObservationIgnored private var appliedSessionRevision: UInt64 = 0
    @ObservationIgnored private var hasStarted = false
    @ObservationIgnored private var persistSession = false
    @ObservationIgnored private var reminderTask: Task<Void, Never>?
    @ObservationIgnored private var reminderRevision = UUID()

    func refreshReminders() {
        reminderTask?.cancel()
        let revision = UUID(); reminderRevision = revision
        guard remindersEnabled, let userID = session?.user.id else { return }
        let identity = clientIdentity; let client = client
        reminderTask = Task { [weak self] in
            do {
                async let tasks = client.allRecords(path: "tasks", query: ["status": "pending"])
                async let exams = LearningService(client: client).exams()
                let values = try await (tasks, exams)
                guard let self, !Task.isCancelled, reminderRevision == revision, clientIdentity == identity,
                      remindersEnabled, session?.user.id == userID else { return }
                await ReminderScheduler.shared.reschedule(plan: ReminderPlan(tasks: values.0.compactMap { try? TaskItem(json: $0) }, exams: values.1))
            } catch { /* Keep the last valid snapshot on a temporary sync failure. */ }
        }
    }

    private func invalidateReminders() {
        reminderRevision = UUID(); reminderTask?.cancel(); reminderTask = nil
        ReminderScheduler.shared.invalidate()
    }

    init() {
        let saved = UserDefaults.standard.string(forKey: "campus.serverURL") ?? "http://localhost:8000/api/v1/"
        let configuration = (try? ServerConfiguration(saved, allowsInsecureHTTP: Self.allowsHTTP))
            ?? (try! ServerConfiguration("http://localhost:8000", allowsInsecureHTTP: true))
        serverURL = configuration.baseURL.absoluteString
        client = APIClient(baseURL: configuration.baseURL)
        #if DEBUG
        if ProcessInfo.processInfo.arguments.contains("-campus.resetLocalState") {
            UserDefaults.standard.removeObject(forKey: "campus.lastUsername")
        }
        #endif
        theme = UserDefaults.standard.string(forKey: "campus.theme") ?? "system"
        remindersEnabled = UserDefaults.standard.bool(forKey: "campus.reminders")
        reduceMotion = UserDefaults.standard.bool(forKey: "campus.reduceMotion")
    }

    static var allowsHTTP: Bool {
        #if DEBUG
        true
        #else
        false
        #endif
    }

    func start() async {
        guard !hasStarted else { return }
        hasStarted = true
        await installObserver()
        #if DEBUG
        // UI tests start from a known signed-out state without depending on the
        // device keychain left over from a previous run.
        if ProcessInfo.processInfo.arguments.contains("-campus.signOutOnLaunch") {
            try? KeychainStore.save(nil, server: serverURL)
        }
        #endif
        let saved = KeychainStore.load(server: serverURL)
        persistSession = saved != nil
        let observedClient = client; let identity = clientIdentity
        await observedClient.restore(saved)
        let snapshot = await observedClient.sessionSnapshot
        guard clientIdentity == identity else { isRestoring = false; return }
        applySession(snapshot)
        isRestoring = false
        if session != nil { await refreshProfile() }
    }

    func configureServer(_ address: String) async throws {
        let configuration = try ServerConfiguration(address, allowsInsecureHTTP: Self.allowsHTTP)
        if configuration.baseURL.absoluteString == serverURL { return }
        invalidateReminders()
        let previousClient = client
        let identity = UUID(); clientIdentity = identity
        appliedSessionRevision = 0
        persistSession = false
        client = APIClient(baseURL: configuration.baseURL)
        let configuredClient = client
        serverURL = configuration.baseURL.absoluteString
        UserDefaults.standard.set(serverURL, forKey: "campus.serverURL")
        scope = UUID()
        session = nil
        await previousClient.restore(nil)
        guard clientIdentity == identity else { throw CancellationError() }
        await installObserver()
        guard clientIdentity == identity else { throw CancellationError() }
        #if DEBUG
        // UI tests start from a known signed-out state without depending on the
        // device keychain left over from a previous run.
        if ProcessInfo.processInfo.arguments.contains("-campus.signOutOnLaunch") {
            try? KeychainStore.save(nil, server: serverURL)
        }
        #endif
        // A manual login must authenticate the supplied credentials, even if
        // the destination server already has a remembered session.
        let saved = isSigningIn ? nil : KeychainStore.load(server: serverURL)
        persistSession = saved != nil
        await configuredClient.restore(saved)
        let snapshot = await configuredClient.sessionSnapshot
        guard clientIdentity == identity else { throw CancellationError() }
        applySession(snapshot, save: !isSigningIn)
    }

    func signIn(username: String, password: String, server: String, remember: Bool) async {
        guard !isSigningIn else { return }
        isSigningIn = true; errorMessage = nil
        defer { isSigningIn = false }
        do {
            try await configureServer(server)
            let identity = clientIdentity; let observedClient = client
            let normalizedUsername = username.trimmingCharacters(in: .whitespacesAndNewlines)
            let result = try await observedClient.login(username: normalizedUsername, password: password)
            let snapshot = await observedClient.sessionSnapshot
            guard clientIdentity == identity, let current = snapshot.session, current.user.id == result.user.id else { return }
            do {
                try KeychainStore.save(remember ? current : nil, server: serverURL)
            } catch {
                await observedClient.restore(nil)
                throw error
            }
            persistSession = remember
            applySession(snapshot, save: false)
            if remember { UserDefaults.standard.set(normalizedUsername, forKey: "campus.lastUsername") }
            else { UserDefaults.standard.removeObject(forKey: "campus.lastUsername") }
        } catch is CancellationError { }
        catch { errorMessage = error.localizedDescription }
    }

    func signOut() async {
        invalidateReminders()
        let previousClient = client
        clientIdentity = UUID()
        appliedSessionRevision = 0
        client = APIClient(baseURL: previousClient.baseURL)
        session = nil; scope = UUID()
        persistSession = false
        do { try KeychainStore.save(nil, server: serverURL) }
        catch { errorMessage = error.localizedDescription }
        await installObserver()
        await previousClient.logout()
    }

    func refreshProfile() async {
        let identity = clientIdentity
        let observedClient = client
        guard let userID = session?.user.id else { return }
        do {
            let value = try await observedClient.request(path: "auth/me")
            let user = try UserProfile(json: value["user"])
            guard clientIdentity == identity, session?.user.id == userID, user.id == userID else { return }
            await observedClient.updateUser(user)
            let snapshot = await observedClient.sessionSnapshot
            guard clientIdentity == identity, session?.user.id == userID, snapshot.session?.user.id == userID else { return }
            applySession(snapshot)
        } catch is CancellationError { }
        catch { if clientIdentity == identity { errorMessage = error.localizedDescription } }
    }

    private func installObserver() async {
        let identity = clientIdentity
        let observedClient = client
        await observedClient.observeSession { [weak self] snapshot in
            Task { @MainActor [weak self] in
                guard let self, self.clientIdentity == identity, !self.isSigningIn else { return }
                self.applySession(snapshot)
            }
        }
    }

    private func applySession(_ snapshot: SessionSnapshot, save: Bool = true) {
        guard snapshot.revision > appliedSessionRevision else { return }
        appliedSessionRevision = snapshot.revision
        let previousID = session?.user.id
        let previousUniversity = session?.user.universityID
        session = snapshot.session
        if previousID != session?.user.id { invalidateReminders() }
        if previousID != session?.user.id || previousUniversity != session?.user.universityID { scope = UUID() }
        guard save else { return }
        do { try KeychainStore.save(persistSession ? session : nil, server: serverURL) }
        catch { errorMessage = error.localizedDescription }
    }
}
