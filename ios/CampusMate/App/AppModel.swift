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
        didSet { UserDefaults.standard.set(remindersEnabled, forKey: "campus.reminders") }
    }
    var reduceMotion: Bool {
        didSet { UserDefaults.standard.set(reduceMotion, forKey: "campus.reduceMotion") }
    }
    @ObservationIgnored private var clientIdentity = UUID()
    @ObservationIgnored private var hasStarted = false

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
        let previousClient = client
        session = nil; scope = UUID()
        try? KeychainStore.save(nil, server: serverURL)
        await previousClient.logout()
    }

    func refreshProfile() async {
        let previousUniversity = session?.user.universityID
        do {
            let value = try await client.request(path: "auth/me")
            let user = try UserProfile(json: value["user"])
            await client.updateUser(user)
            session = await client.currentSession
            if previousUniversity != session?.user.universityID { scope = UUID() }
        } catch is CancellationError { }
        catch { errorMessage = error.localizedDescription }
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
                self.session = session
                if previousID != session?.user.id { self.scope = UUID() }
                do { try KeychainStore.save(session, server: address) }
                catch { self.errorMessage = error.localizedDescription }
            }
        }
    }
}
