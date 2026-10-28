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
    @ObservationIgnored private var hasStarted = false
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
        await client.restore(saved)
        session = saved
        isRestoring = false
        if saved != nil { await refreshProfile() }
    }

    func configureServer(_ address: String) async throws {
        let configuration = try ServerConfiguration(address, allowsInsecureHTTP: Self.allowsHTTP)
        if configuration.baseURL.absoluteString == serverURL { return }
        invalidateReminders()
        clientIdentity = UUID()
        await client.restore(nil)
        client = APIClient(baseURL: configuration.baseURL)
        serverURL = configuration.baseURL.absoluteString
        UserDefaults.standard.set(serverURL, forKey: "campus.serverURL")
        scope = UUID()
        session = nil
        await installObserver()
        #if DEBUG
        // UI tests start from a known signed-out state without depending on the
        // device keychain left over from a previous run.
        if ProcessInfo.processInfo.arguments.contains("-campus.signOutOnLaunch") {
            try? KeychainStore.save(nil, server: serverURL)
        }
        #endif
        let saved = KeychainStore.load(server: serverURL)
        await client.restore(saved)
        session = saved
    }

    func signIn(username: String, password: String, server: String) async {
        guard !isSigningIn else { return }
        isSigningIn = true; errorMessage = nil
        defer { isSigningIn = false }
        do {
            try await configureServer(server)
            let result = try await client.login(username: username.trimmingCharacters(in: .whitespacesAndNewlines), password: password)
            try KeychainStore.save(result, server: serverURL)
            session = result; scope = UUID()
            UserDefaults.standard.set(username, forKey: "campus.lastUsername")
        } catch is CancellationError { }
        catch { errorMessage = error.localizedDescription }
    }

    func signOut() async {
        invalidateReminders()
        let previousClient = client
        session = nil; scope = UUID()
        try? KeychainStore.save(nil, server: serverURL)
        await previousClient.logout()
    }

    func refreshProfile() async {
        let identity = clientIdentity
        let observedClient = client
        let userID = session?.user.id
        let previousUniversity = session?.user.universityID
        do {
            let value = try await observedClient.request(path: "auth/me")
            let user = try UserProfile(json: value["user"])
            guard clientIdentity == identity, session?.user.id == userID, user.id == userID else { return }
            await observedClient.updateUser(user)
            let current = await observedClient.currentSession
            guard clientIdentity == identity, current?.user.id == userID else { return }
            session = current
            if previousUniversity != session?.user.universityID { scope = UUID() }
        } catch is CancellationError { }
        catch { if clientIdentity == identity { errorMessage = error.localizedDescription } }
    }

    private func installObserver() async {
        let identity = clientIdentity
        let address = serverURL
        let observedClient = client
        await client.observeSession { [weak self] session in
            Task { @MainActor [weak self] in
                let current = await observedClient.currentSession
                guard let self, self.clientIdentity == identity, current == session else { return }
                let previousID = self.session?.user.id
                if previousID != session?.user.id { self.invalidateReminders() }
                self.session = session
                if previousID != session?.user.id { self.scope = UUID() }
                do { try KeychainStore.save(session, server: address) }
                catch { self.errorMessage = error.localizedDescription }
            }
        }
    }
}
