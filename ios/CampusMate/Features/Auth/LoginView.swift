import SwiftUI
import UIKit
import AVFoundation
import CampusCore

/// Muted, looping campus film used behind the login form. Falls back to the
/// poster frame when the film is unavailable or motion is reduced.
struct LoopingVideoBackground: View {
    @Environment(\.scenePhase) private var scenePhase
    let resource: String
    let poster: String
    var playing: Bool = true

    @State private var player: AVQueuePlayer?
    @State private var looper: AVPlayerLooper?

    var body: some View {
        ZStack {
            Image(poster)
                .resizable()
                .scaledToFill()
            if let player {
                VideoLayer(player: player)
                    .opacity(playing ? 1 : 0)
            }
        }
        .clipped()
        .onAppear(perform: prepare)
        .onDisappear { player?.pause() }
        .onChange(of: playing) { _, value in
            if value && scenePhase == .active { player?.play() } else { player?.pause() }
        }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active && playing { player?.play() } else { player?.pause() }
        }
    }

    private func prepare() {
        if let player {
            if playing && scenePhase == .active { player.play() }
            return
        }
        guard let url = Bundle.main.url(forResource: resource, withExtension: "mp4") else { return }
        let item = AVPlayerItem(url: url)
        let queue = AVQueuePlayer(playerItem: item)
        queue.isMuted = true
        queue.actionAtItemEnd = .none
        looper = AVPlayerLooper(player: queue, templateItem: item)
        player = queue
        if playing && scenePhase == .active { queue.play() }
    }
}

private struct VideoLayer: UIViewRepresentable {
    let player: AVPlayer
    func makeUIView(context: Context) -> PlayerView {
        let view = PlayerView()
        view.playerLayer.videoGravity = .resizeAspectFill
        view.playerLayer.player = player
        return view
    }
    func updateUIView(_ view: PlayerView, context: Context) {
        view.playerLayer.player = player
    }
    final class PlayerView: UIView {
        override static var layerClass: AnyClass { AVPlayerLayer.self }
        var playerLayer: AVPlayerLayer { layer as! AVPlayerLayer }
    }
}

struct LoginView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.campus) private var palette
    @State private var username = UserDefaults.standard.string(forKey: "campus.lastUsername") ?? ""
    @State private var password = ""
    @State private var address = ""
    @State private var showServer = false
    @State private var showPassword = false
    @State private var remember = true
    @State private var error = ""
    @FocusState private var focusedField: Field?
    private enum Field { case username, passwordHidden, passwordVisible, server }

    private let ink = Color(hex: 0x111A31)
    private let blue = Color(hex: 0x596AF0)
    private let blueDeep = Color(hex: 0x3E50D9)
    private let warm = Color(hex: 0xFFA45B)
    private let formText = Color(hex: 0xF8FAFF)
    private let formMuted = Color(hex: 0xEBF0FF, opacity: 0.74)

    var body: some View {
        ZStack {
            ink.ignoresSafeArea()
            GeometryReader { proxy in
                LoopingVideoBackground(resource: "login_campus", poster: "campus_login_poster",
                                       playing: !app.reduceMotion)
                    .frame(width: proxy.size.width, height: proxy.size.height)
            }
            .ignoresSafeArea()
            LinearGradient(stops: [
                .init(color: Color(hex: 0x091632, opacity: 0.52), location: 0),
                .init(color: Color(hex: 0x091632, opacity: 0.48), location: 0.34),
                .init(color: Color(hex: 0x091632, opacity: 0.86), location: 0.64),
                .init(color: Color(hex: 0x091632, opacity: 0.97), location: 1),
            ], startPoint: .top, endPoint: .bottom)
                .ignoresSafeArea()

            GeometryReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: 0) {
                        brand
                        Spacer().frame(height: 66)
                        Text("欢迎回到校园")
                            .font(.system(size: 32, weight: .bold))
                            .tracking(-0.5)
                            .foregroundStyle(.white)
                        Spacer().frame(height: 8)
                        Text("课程、通知与每一个重要截止，\n都替你稳稳记着。")
                            .font(.system(size: 13))
                            .lineSpacing(5)
                            .foregroundStyle(.white.opacity(0.82))
                        Spacer().frame(height: 42)
                        form
                    }
                    .padding(.horizontal, 24)
                    .padding(.top, 20)
                    .padding(.bottom, 32)
                    .frame(maxWidth: 560)
                    .frame(maxWidth: .infinity, minHeight: proxy.size.height, alignment: .top)
                }
                .scrollDismissesKeyboard(.interactively)
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .background {
            KeyboardDismissGesture { dismissKeyboard() }
                .allowsHitTesting(false)
        }
        .onAppear { address = app.serverURL }
        .errorAlert(Binding(get: { app.errorMessage }, set: { app.errorMessage = $0 }))
    }

    private var brand: some View {
        HStack(spacing: 10) {
            RoundedRectangle(cornerRadius: 13, style: .continuous)
                .fill(warm)
                .frame(width: 40, height: 40)
                .overlay(Image(systemName: "graduationcap.fill").font(.system(size: 19, weight: .semibold)).foregroundStyle(.white))
            VStack(alignment: .leading, spacing: 2) {
                Text("CampusMate AI").font(.system(size: 14, weight: .bold)).foregroundStyle(.white)
                Text("校园事务 · 温和陪伴").font(.system(size: 9.5)).foregroundStyle(.white.opacity(0.7))
            }
        }
        .accessibilityElement(children: .combine)
    }

    private var form: some View {
        VStack(alignment: .leading, spacing: 16) {
            VStack(alignment: .leading, spacing: 4) {
                Text("登录 CampusMate").font(.system(size: 23, weight: .bold)).foregroundStyle(formText)
                Text("使用学校统一身份账号继续。").font(.system(size: 11.5)).foregroundStyle(formMuted)
            }

            field(label: "账号", systemImage: "person.fill") {
                TextField("", text: $username, prompt: Text("学号 / 工号 / 用户名").foregroundStyle(formMuted))
                    .textContentType(.username)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .submitLabel(.next)
                    .focused($focusedField, equals: .username)
                    .onSubmit { focusedField = showPassword ? .passwordVisible : .passwordHidden }
                    .accessibilityIdentifier("login.username")
                    .foregroundStyle(formText)
                    .font(.system(size: 14))
            }

            field(label: "密码", systemImage: "lock.fill") {
                HStack(spacing: 10) {
                    Group {
                        if showPassword {
                            TextField("", text: $password, prompt: Text("请输入密码").foregroundStyle(formMuted))
                                .focused($focusedField, equals: .passwordVisible)
                                .accessibilityIdentifier("login.password.visible")
                        } else {
                            SecureField("", text: $password, prompt: Text("请输入密码").foregroundStyle(formMuted))
                                .focused($focusedField, equals: .passwordHidden)
                                .accessibilityIdentifier("login.password")
                        }
                    }
                    .textContentType(.password)
                    .textInputAutocapitalization(.never)
                    .autocorrectionDisabled()
                    .submitLabel(.go)
                    .onSubmit(signIn)
                    .foregroundStyle(formText)
                    .font(.system(size: 14))

                    PasswordVisibilityButton(isVisible: showPassword) {
                        let wasFocused = focusedField == .passwordHidden || focusedField == .passwordVisible
                        showPassword.toggle()
                        if wasFocused { focusedField = showPassword ? .passwordVisible : .passwordHidden }
                        CampusHaptics.selection()
                    }
                    .frame(width: 44, height: 44)
                }
            }

            if !error.isEmpty {
                Text(error)
                    .font(.system(size: 11.5))
                    .foregroundStyle(Color(hex: 0xFFC5BF))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, 12)
                    .padding(.vertical, 9)
                    .background(Color(hex: 0x3E171A, opacity: 0.4), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
            }

            Button {
                remember.toggle()
                CampusHaptics.selection()
            } label: {
                HStack(spacing: 8) {
                    Image(systemName: remember ? "checkmark.square.fill" : "square")
                        .font(.system(size: 18))
                        .foregroundStyle(remember ? blue : formMuted)
                    Text("记住账号（下次自动登录）").font(.system(size: 12)).foregroundStyle(formMuted)
                }
                .frame(minHeight: 44)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityIdentifier("login.remember")
            .accessibilityAddTraits(remember ? [.isSelected, .isButton] : .isButton)

            Button(action: signIn) {
                HStack(spacing: 8) {
                    if app.isSigningIn {
                        ProgressView().tint(blueDeep).controlSize(.small)
                    } else {
                        Text("进入校园空间").font(.system(size: 14, weight: .bold))
                        Image(systemName: "arrow.right").font(.system(size: 14, weight: .semibold))
                    }
                }
                .foregroundStyle(blueDeep)
                .frame(maxWidth: .infinity)
                .frame(height: 51)
                .background(Color.white.opacity(0.96), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            }
            .buttonStyle(CampusPressStyle())
            .disabled(app.isSigningIn || username.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || password.isEmpty)
            .opacity(username.isEmpty || password.isEmpty ? 0.78 : 1)
            .accessibilityIdentifier("login.submit")
            .accessibilityLabel("登录")

            Text("登录即表示你已阅读并同意校园数据使用说明")
                .font(.system(size: 9.5))
                .foregroundStyle(.white.opacity(0.48))
                .frame(maxWidth: .infinity)

            serverSettings
        }
        .padding(.top, 4)
    }

    private func field<Content: View>(label: String, systemImage: String, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(label).font(.system(size: 11, weight: .semibold)).foregroundStyle(formMuted)
            HStack(spacing: 11) {
                Image(systemName: systemImage).font(.system(size: 15)).foregroundStyle(formMuted)
                content()
            }
            .frame(minHeight: 45)
            Rectangle()
                .fill(Color.white.opacity(focusedField != nil ? 0.92 : 0.32))
                .frame(height: 1)
                .animation(.easeOut(duration: 0.2), value: focusedField)
        }
    }

    private var serverSettings: some View {
        VStack(alignment: .leading, spacing: 8) {
            Button {
                if showServer && focusedField == .server { focusedField = nil }
                withAnimation(.easeInOut(duration: 0.22)) { showServer.toggle() }
            } label: {
                HStack(spacing: 6) {
                    Image(systemName: "server.rack").font(.system(size: 12))
                    Text("服务连接").font(.system(size: 12, weight: .semibold))
                    Image(systemName: showServer ? "chevron.up" : "chevron.down").font(.system(size: 10, weight: .semibold))
                }
                .foregroundStyle(.white.opacity(0.66))
            }
            .buttonStyle(.plain)
            if showServer {
                VStack(alignment: .leading, spacing: 7) {
                    TextField("服务器地址", text: $address)
                        .keyboardType(.URL)
                        .textContentType(.URL)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .focused($focusedField, equals: .server)
                        .accessibilityIdentifier("login.server")
                        .font(.system(size: 12))
                        .foregroundStyle(formText)
                        .padding(.horizontal, 12)
                        .padding(.vertical, 10)
                        .background(Color.white.opacity(0.10), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
                    Text("模拟器可连接本机服务；手机需使用可访问的服务地址。")
                        .font(.system(size: 10.5))
                        .foregroundStyle(.white.opacity(0.5))
                }
            }
        }
        .padding(.top, 4)
    }

    private func dismissKeyboard() { focusedField = nil }

    private func signIn() {
        guard !app.isSigningIn else { return }
        dismissKeyboard()
        guard !username.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty else {
            error = "请输入学号、工号或用户名。"; return
        }
        guard !password.isEmpty else { error = "请输入密码后继续。"; return }
        error = ""
        Task { await app.signIn(username: username, password: password, server: address, remember: remember) }
    }
}

/// Listens within the login viewport without cancelling controls or scrolling.
private struct KeyboardDismissGesture: UIViewRepresentable {
    let dismiss: () -> Void

    func makeCoordinator() -> Coordinator { Coordinator(dismiss: dismiss) }

    func makeUIView(context: Context) -> Anchor {
        let anchor = Anchor()
        anchor.isUserInteractionEnabled = false
        anchor.windowChanged = { [weak coordinator = context.coordinator, weak anchor] in
            guard let coordinator, let anchor else { return }
            coordinator.attach(to: anchor)
        }
        return anchor
    }

    func updateUIView(_ view: Anchor, context: Context) {
        context.coordinator.dismiss = dismiss
        context.coordinator.attach(to: view)
    }

    static func dismantleUIView(_ view: Anchor, coordinator: Coordinator) {
        view.windowChanged = nil
        coordinator.detach()
    }

    final class Anchor: UIView {
        var windowChanged: (() -> Void)?
        override func didMoveToWindow() {
            super.didMoveToWindow()
            windowChanged?()
        }
    }

    final class Coordinator: NSObject, UIGestureRecognizerDelegate {
        var dismiss: () -> Void
        weak var anchor: UIView?
        weak var window: UIWindow?
        private var recognizer: UITapGestureRecognizer?

        init(dismiss: @escaping () -> Void) { self.dismiss = dismiss }

        func attach(to anchor: UIView) {
            self.anchor = anchor
            guard window !== anchor.window else { return }
            detach()
            self.anchor = anchor
            guard let window = anchor.window else { return }
            let recognizer = UITapGestureRecognizer(target: self, action: #selector(tapped))
            recognizer.cancelsTouchesInView = false
            recognizer.delegate = self
            window.addGestureRecognizer(recognizer)
            self.window = window
            self.recognizer = recognizer
        }

        func detach() {
            if let recognizer { window?.removeGestureRecognizer(recognizer) }
            recognizer = nil
            window = nil
            anchor = nil
        }

        @objc private func tapped() {
            window?.endEditing(true)
            dismiss()
        }

        func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer, shouldReceive touch: UITouch) -> Bool {
            guard let anchor, let window,
                  anchor.convert(anchor.bounds, to: window).contains(touch.location(in: window)) else { return false }
            var hit = touch.view
            while let view = hit {
                if view is UIControl || view is UITextView { return false }
                hit = view.superview
            }
            return true
        }

        func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer,
                               shouldRecognizeSimultaneouslyWith otherGestureRecognizer: UIGestureRecognizer) -> Bool {
            true
        }
    }
}

/// A native button lets the dismiss recognizer distinguish the eye control
/// from empty space while keeping password editing active.
private struct PasswordVisibilityButton: UIViewRepresentable {
    let isVisible: Bool
    let toggle: () -> Void

    func makeCoordinator() -> Coordinator { Coordinator(toggle: toggle) }

    func makeUIView(context: Context) -> UIButton {
        let button = UIButton(type: .system)
        button.addTarget(context.coordinator, action: #selector(Coordinator.pressed), for: .touchUpInside)
        button.tintColor = UIColor(red: 235 / 255, green: 240 / 255, blue: 1, alpha: 0.74)
        return button
    }

    func updateUIView(_ button: UIButton, context: Context) {
        context.coordinator.toggle = toggle
        let configuration = UIImage.SymbolConfiguration(pointSize: 15)
        button.setImage(UIImage(systemName: isVisible ? "eye.slash" : "eye", withConfiguration: configuration), for: .normal)
        button.accessibilityLabel = isVisible ? "隐藏密码" : "显示密码"
    }

    final class Coordinator: NSObject {
        var toggle: () -> Void
        init(toggle: @escaping () -> Void) { self.toggle = toggle }
        @objc func pressed() { toggle() }
    }
}
