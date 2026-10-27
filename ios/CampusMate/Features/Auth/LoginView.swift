import SwiftUI
import CampusCore

struct LoginView: View {
    @Environment(AppModel.self) private var app
    @State private var username = UserDefaults.standard.string(forKey: "campus.lastUsername") ?? ""
    @State private var password = ""
    @State private var address = ""
    @State private var showServer = false
    @FocusState private var focusedField: Field?
    private enum Field { case username, password }

    var body: some View {
        NavigationStack {
            Form {
                Section {
                    VStack(alignment: .leading, spacing: 12) {
                        Image(systemName: "graduationcap.circle.fill").font(.system(size: 62)).foregroundStyle(.tint)
                        Text("欢迎使用 CampusMate").font(.title2.bold())
                        Text("管理课程与待办，让学习有条不紊。").font(.subheadline).foregroundStyle(.secondary)
                    }.padding(.vertical, 20).frame(maxWidth: .infinity, alignment: .leading)
                }.listRowBackground(Color.clear)

                Section("登录账号") {
                    TextField("用户名", text: $username)
                        .textContentType(.username).textInputAutocapitalization(.never).autocorrectionDisabled()
                        .focused($focusedField, equals: .username).submitLabel(.next)
                        .onSubmit { focusedField = .password }
                    SecureField("密码", text: $password)
                        .textContentType(.password).focused($focusedField, equals: .password).submitLabel(.go)
                        .onSubmit(signIn)
                }
                Section {
                    Button(action: signIn) {
                        HStack {
                            Spacer()
                            if app.isSigningIn { ProgressView().padding(.trailing, 6) }
                            Text(app.isSigningIn ? "正在登录…" : "登录").fontWeight(.semibold)
                            Spacer()
                        }.padding(.vertical, 5)
                    }.disabled(username.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty || password.isEmpty || app.isSigningIn)
                } footer: { Text("登录凭据保存在本机钥匙串，密码不会保存在应用中。") }

                Section {
                    DisclosureGroup("服务器设置", isExpanded: $showServer) {
                        TextField("服务器地址", text: $address).keyboardType(.URL).textContentType(.URL)
                            .textInputAutocapitalization(.never).autocorrectionDisabled()
                        Text("请填写 CampusMate 服务地址。模拟器可连接本机服务；手机需使用可访问的服务地址。")
                            .font(.footnote).foregroundStyle(.secondary)
                    }
                }
            }
            .navigationTitle("CampusMate")
            .onAppear { address = app.serverURL }
            .errorAlert(Binding(get: { app.errorMessage }, set: { app.errorMessage = $0 }))
        }
    }

    private func signIn() {
        guard !username.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty, !password.isEmpty else { return }
        focusedField = nil
        Task { await app.signIn(username: username, password: password, server: address) }
    }
}
