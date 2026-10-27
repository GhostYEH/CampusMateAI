import SwiftUI
import CampusCore

struct ChaoxingView: View {
    @Environment(AppModel.self) private var app
    @State private var resource = RemoteResource()
    @State private var username = ""
    @State private var password = ""
    @State private var working = false
    @State private var error: String?
    @State private var result: String?
    @State private var confirmingDisconnect = false
    var body: some View {
        Form {
            Section("连接状态") {
                if resource.isLoading { ProgressView() }
                if let error = resource.error { Text(error).foregroundStyle(.secondary) }
                if let status = resource.value["status"].string { LabeledContent("状态", value: status.localizedStatus) }
                if let date = resource.value["last_synced_at"].string { LabeledContent("上次同步", value: date) }
                ForEach(resource.value["warnings"].items, id: \.self) { Text($0.text).font(.footnote).foregroundStyle(.orange) }
                if let result { Text(result).font(.footnote) }
            }
            Section {
                TextField("学习通账号", text: $username).textContentType(.username).textInputAutocapitalization(.never).autocorrectionDisabled()
                SecureField("学习通密码", text: $password).textContentType(.password)
                Button(working ? "正在处理…" : "连接学习通") {
                    perform {
                        let response = try await PersonalService(client: app.client).connectChaoxing(username: username, password: password)
                        password = ""; result = response["message"].string ?? "连接请求已完成，请检查同步状态。"
                    }
                }.disabled(working || username.isEmpty || password.isEmpty)
            } header: { Text("连接或重新认证") } footer: { Text("用于你主动授权的课程、作业、考试和通知同步。本站登录与学习通登录是独立的。") }
            Section {
                Button("立即同步", systemImage: "arrow.triangle.2.circlepath") {
                    perform {
                        let response = try await PersonalService(client: app.client).syncChaoxing()
                        let warnings = response["warnings"].items.compactMap(\.string)
                        result = warnings.isEmpty ? "同步请求已完成，课程与待办将以最新返回数据为准。" : warnings.joined(separator: "\n")
                    }
                }.disabled(working)
                Button("解除连接", role: .destructive) { confirmingDisconnect = true }.disabled(working)
            }
        }.navigationTitle("学习通").task { await load() }.refreshable { await load() }
        .confirmationDialog("解除学习通连接？", isPresented: $confirmingDisconnect, titleVisibility: .visible) {
            Button("解除连接", role: .destructive) { perform { try await PersonalService(client: app.client).disconnectChaoxing(); result = "连接已解除。" } }
        }.errorAlert($error)
    }
    private func load() async { await resource.load(client: app.client, path: "chaoxing/status") }
    private func perform(_ action: @escaping @MainActor () async throws -> Void) {
        working = true
        Task { defer { working = false }; do { try await action(); await load() } catch { self.error = error.localizedDescription } }
    }
}

struct UniversityPickerView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var search = ""
    @State private var resource = PagedResource()
    @State private var error: String?
    @State private var selected: String?
    private var query: [String: String] { search.isEmpty ? [:] : ["q": search] }
    var body: some View {
        List {
            PagedStatusView(resource: resource, emptyTitle: "没有找到学校", emptyMessage: "试试学校全称或更短的关键词。", icon: "building.columns", retry: load)
            ForEach(Array(resource.items.enumerated()), id: \.offset) { _, school in
                Button {
                    selected = school["id"].text
                    Task {
                        defer { selected = nil }
                        do {
                            _ = try await app.client.request(.put, path: "profile/university", body: ["university_id": school["id"]])
                            await app.refreshProfile(); dismiss()
                        } catch { self.error = error.localizedDescription }
                    }
                } label: {
                    HStack {
                        VStack(alignment: .leading, spacing: 5) {
                            Text(school["name"].text).foregroundStyle(.primary)
                            Text([school["province"].text, school["city"].text].filter { !$0.isEmpty }.joined(separator: " · ")).font(.caption).foregroundStyle(.secondary)
                        }
                        Spacer()
                        if selected == school["id"].text { ProgressView() }
                        else if school["id"].string == app.session?.user.universityID { Image(systemName: "checkmark") }
                    }
                }.disabled(selected != nil)
            }
            LoadMoreRow(resource: resource) { await resource.load(client: app.client, path: "universities", query: query, reset: false) }
        }.navigationTitle("选择学校").searchable(text: $search, prompt: "搜索学校")
        .task(id: search) { if !search.isEmpty { try? await Task.sleep(for: .milliseconds(250)) }; guard !Task.isCancelled else { return }; await load() }
        .errorAlert($error)
    }
    private func load() async { await resource.load(client: app.client, path: "universities", query: query) }
}

struct EduSystemView: View {
    @Environment(AppModel.self) private var app
    @State private var binding = RemoteResource()
    @State private var systems = RemoteResource()
    @State private var error: String?
    @State private var working = false
    @State private var confirmDisconnect = false
    var body: some View {
        List {
            Section("学校") { NavigationLink(app.session?.user.universityName.nonEmpty ?? "选择学校") { UniversityPickerView() } }
            Section("教务连接") {
                if binding.isLoading { ProgressView() }
                if let error = binding.error { Text(error).foregroundStyle(.secondary) }
                if binding.value != .null {
                    if let name = binding.value["external_student_name"].string { LabeledContent("姓名", value: name) }
                    LabeledContent("状态", value: binding.value["connection_status"].text.localizedStatus)
                    if let error = binding.value["last_error"].string?.nonEmpty { Text(error).font(.footnote).foregroundStyle(.orange) }
                    ForEach([("profile", "个人信息"), ("schedule", "课表"), ("grade", "成绩"), ("exam", "考试")], id: \.0) { key, title in
                        Button("同步\(title)", systemImage: "arrow.triangle.2.circlepath") { sync(key) }.disabled(working)
                        if key != "profile" { NavigationLink("查看\(title)") { SimpleRemoteList(title: title, path: "edu/\(key)/items", icon: "calendar") } }
                    }
                    Button("解除教务连接", role: .destructive) { confirmDisconnect = true }
                } else { Text("尚未连接教务系统").foregroundStyle(.secondary) }
            }
            if app.session?.user.universityID.isEmpty == false {
                Section("可连接的系统") {
                    ResourceStateView(resource: systems, isEmpty: systems.value.items.isEmpty, title: "未找到可用系统", message: "学校可能尚未提供适配信息。", systemImage: "network", retry: load)
                    ForEach(Array(systems.value.items.enumerated()), id: \.offset) { _, system in
                        NavigationLink { EduLoginView(system: system) } label: {
                            VStack(alignment: .leading, spacing: 6) {
                                Text(system["name"].text)
                                if system["requires_campus_network"].bool == true { Text("需要校园网").font(.caption).foregroundStyle(.secondary) }
                                if system["requires_vpn"].bool == true { Text("需要学校 VPN").font(.caption).foregroundStyle(.secondary) }
                            }
                        }
                    }
                }
            }
        }.navigationTitle("教务系统").task { await load() }.refreshable { await load() }.errorAlert($error)
        .confirmationDialog("解除教务系统连接？", isPresented: $confirmDisconnect, titleVisibility: .visible) {
            Button("解除连接", role: .destructive) { Task { do { _ = try await app.client.request(.delete, path: "edu/binding"); await load() } catch { self.error = error.localizedDescription } } }
        }
    }
    private func load() async {
        await binding.load(client: app.client, path: "edu/binding")
        if let university = app.session?.user.universityID.nonEmpty { await systems.load(client: app.client, path: "edu/systems/\(university.pathComponent)") }
    }
    private func sync(_ kind: String) {
        working = true
        Task { defer { working = false }; do { _ = try await app.client.request(.post, path: "edu/sync/\(kind)"); await load() } catch { self.error = error.localizedDescription } }
    }
}

struct EduLoginView: View {
    @Environment(AppModel.self) private var app
    let system: JSONValue
    @State private var connection: JSONValue = .null
    @State private var prelogin: JSONValue = .null
    @State private var username = ""
    @State private var password = ""
    @State private var captcha = ""
    @State private var smsCode = ""
    @State private var mfaCode = ""
    @State private var working = false
    @State private var error: String?
    @State private var showWebLogin = false

    var body: some View {
        Form {
            Section {
                Text(system["name"].text).font(.headline)
                if let message = connection["error_message"].string?.nonEmpty { Text(message).foregroundStyle(.orange) }
                if connection["state"].text == "connected" { Label("已连接", systemImage: "checkmark.circle.fill").foregroundStyle(.green) }
            }
            if connection["state"].text != "connected" {
                if connection["login_execution_mode"].text != "client_webview" { Section("教务账号") {
                    TextField("账号", text: $username).textContentType(.username).textInputAutocapitalization(.never).autocorrectionDisabled()
                    SecureField("密码", text: $password).textContentType(.password)
                    if let image = captchaImage { Image(uiImage: image).resizable().scaledToFit().frame(maxHeight: 100).accessibilityLabel("教务验证码") }
                    if prelogin["captcha_required"].bool == true { TextField("图片验证码", text: $captcha).textInputAutocapitalization(.never).autocorrectionDisabled() }
                    if connection["state"].text.contains("sms") || prelogin["challenge_type"].text.contains("sms") { TextField("短信验证码", text: $smsCode).keyboardType(.numberPad) }
                    if connection["state"].text.contains("mfa") || prelogin["challenge_type"].text.contains("mfa") { TextField("动态验证码", text: $mfaCode).keyboardType(.numberPad) }
                    Button(working ? "正在连接…" : "连接教务系统") { connect() }.disabled(working || username.isEmpty || password.isEmpty)
                    if connection["id"].string != nil { Button("刷新验证码") { Task { await prepare() } }.disabled(working) }
                } }
                if connection["login_execution_mode"].text == "client_webview", connection["portal_url"].string != nil {
                    Section {
                        Text("此学校需要在网页登录后继续验证。").font(.footnote).foregroundStyle(.secondary)
                        Button("打开学校登录页", systemImage: "safari") { showWebLogin = true }.disabled(working)
                    }
                }
            }
        }.navigationTitle("连接教务").navigationBarTitleDisplayMode(.inline).task { await prepare() }.errorAlert($error)
        .sheet(isPresented: $showWebLogin) {
            if let url = URL(string: connection["portal_url"].text) {
                NavigationStack {
                    EduWebLoginView(connectionID: connection["id"].text, url: url, origins: connection["allowed_origins"].items.compactMap(\.string)) { result in connection = result }
                }
            }
        }
    }
    private var captchaImage: UIImage? {
        guard let value = prelogin["captcha_image_base64"].string,
              let data = Data(base64Encoded: value.contains(",") ? String(value.split(separator: ",", maxSplits: 1)[1]) : value) else { return nil }
        return UIImage(data: data)
    }
    private func prepare() async {
        guard !working else { return }; working = true
        defer { working = false }
        do {
            if connection["id"].string == nil { connection = try await app.client.request(.post, path: "edu/connections", body: ["edu_system_id": system["id"]]) }
            if connection["login_execution_mode"].text != "client_webview" {
                prelogin = try await app.client.request(.post, path: "edu/connections/\(connection["id"].text.pathComponent)/pre-login")
            }
        } catch { self.error = error.localizedDescription }
    }
    private func connect() {
        working = true
        Task {
            defer { working = false }
            do {
                guard let id = connection["id"].string else { throw APIError(code: "NO_CONNECTION", message: "请返回并重新打开连接页面。") }
                var body: [String: JSONValue] = ["username": .string(username), "password": .string(password)]
                for (key, value) in [("captcha", captcha), ("sms_code", smsCode), ("mfa_code", mfaCode)] where !value.isEmpty { body[key] = .string(value) }
                for key in ["pre_login_token", "verification_session_id"] where prelogin[key].string != nil { body[key] = prelogin[key] }
                connection = try await app.client.request(.post, path: "edu/connections/\(id.pathComponent)/continue", body: .object(body))
                if connection["state"].text == "connected" { password = "" }
                else if let message = connection["error_message"].string?.nonEmpty { error = message }
            } catch { self.error = error.localizedDescription }
        }
    }
}

struct EduWebLoginView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    let connectionID: String
    let url: URL
    let origins: [String]
    let onConnected: (JSONValue) -> Void
    @State private var bridge = WebLoginBridge()
    @State private var error: String?
    @State private var working = false
    var body: some View {
        TrustedWebView(url: url, origins: origins, loginMode: true, bridge: bridge) { error = $0 }
            .navigationTitle("学校登录").navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("关闭") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) {
                    Button(working ? "验证中…" : "已登录，继续") {
                        working = true
                        Task {
                            defer { working = false }
                            do {
                                let body = try await bridge.capture(origins: origins)
                                let result = try await app.client.request(.post, path: "edu/connections/\(connectionID.pathComponent)/continue", body: body)
                                onConnected(result)
                                if result["state"].text == "connected" { dismiss() }
                                else { error = result["error_message"].string ?? "尚未检测到有效登录，请确认已进入教务系统首页后再继续。" }
                            } catch { self.error = error.localizedDescription }
                        }
                    }.disabled(working)
                }
            }.errorAlert($error)
    }
}
