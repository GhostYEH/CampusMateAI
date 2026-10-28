import SwiftUI
import WebKit
import CampusCore

@MainActor @Observable
final class WebLoginBridge {
    @ObservationIgnored weak var webView: WKWebView?

    func capture(origins: [String]) async throws -> JSONValue {
        guard let webView, let address = webView.url?.absoluteString,
              URLPolicy.isTrusted(address, origins: origins, allowLocalDebug: AppModel.allowsHTTP, requiresPublicOrigin: false) else {
            throw APIError(code: "UNTRUSTED_LOGIN", message: "当前登录页面不属于学校授权的地址。")
        }
        let cookies: [HTTPCookie] = await withCheckedContinuation { continuation in
            webView.configuration.websiteDataStore.httpCookieStore.getAllCookies { continuation.resume(returning: $0) }
        }
        let hosts = origins.compactMap { URLComponents(string: $0)?.host?.lowercased() }
        let jar: [JSONValue] = cookies.filter { cookie in
            let domain = cookie.domain.lowercased().trimmingCharacters(in: CharacterSet(charactersIn: "."))
            return hosts.contains { $0 == domain || $0.hasSuffix("." + domain) }
        }.map { cookie in
            var fields: [String: JSONValue] = ["name": .string(cookie.name), "value": .string(cookie.value), "domain": .string(cookie.domain), "path": .string(cookie.path), "secure": .bool(cookie.isSecure), "http_only": .bool(cookie.isHTTPOnly)]
            if let date = cookie.expiresDate { fields["expires"] = .number(date.timeIntervalSince1970) }
            return .object(fields)
        }
        let agent = (try? await webView.evaluateJavaScript("navigator.userAgent")) as? String
        var result: [String: JSONValue] = ["cookie_jar": .array(jar), "current_url": .string(address)]
        if let agent { result["user_agent"] = .string(agent) }
        return .object(result)
    }
}

struct TrustedWebView: UIViewRepresentable {
    let url: URL
    let origins: [String]
    var loginMode = false
    var bridge: WebLoginBridge?
    var onError: (String) -> Void = { _ in }

    func makeCoordinator() -> Coordinator { Coordinator(parent: self) }
    func makeUIView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.websiteDataStore = .nonPersistent()
        configuration.allowsInlineMediaPlayback = true
        let view = WKWebView(frame: .zero, configuration: configuration)
        view.navigationDelegate = context.coordinator
        view.allowsBackForwardNavigationGestures = true
        bridge?.webView = view
        return view
    }
    func updateUIView(_ view: WKWebView, context: Context) {
        context.coordinator.parent = self
        bridge?.webView = view
        let identity = url.absoluteString + origins.sorted().joined(separator: "|") + String(loginMode)
        guard context.coordinator.requestedIdentity != identity else { return }
        context.coordinator.requestedIdentity = identity
        guard trusted(url) else { Task { @MainActor in onError("页面地址不在可信服务列表中，已停止打开。") }; return }
        view.load(URLRequest(url: url))
    }
    static func dismantleUIView(_ uiView: WKWebView, coordinator: Coordinator) { uiView.stopLoading(); uiView.navigationDelegate = nil }
    private func trusted(_ url: URL) -> Bool { URLPolicy.isTrusted(url.absoluteString, origins: origins, allowLocalDebug: AppModel.allowsHTTP, requiresPublicOrigin: !loginMode) }

    @MainActor final class Coordinator: NSObject, WKNavigationDelegate {
        var parent: TrustedWebView
        var requestedIdentity: String?
        init(parent: TrustedWebView) { self.parent = parent }
        func webView(_ webView: WKWebView, decidePolicyFor navigationAction: WKNavigationAction) async -> WKNavigationActionPolicy {
            guard let url = navigationAction.request.url else { return .cancel }
            if url.absoluteString == "about:blank" { return .allow }
            guard parent.trusted(url) else { parent.onError("页面试图跳转到未授权地址，已阻止。"); return .cancel }
            return .allow
        }
        func webView(_ webView: WKWebView, didFailProvisionalNavigation navigation: WKNavigation!, withError error: any Error) {
            if (error as NSError).code != NSURLErrorCancelled { parent.onError(error.localizedDescription) }
        }
    }
}
