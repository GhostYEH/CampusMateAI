import SwiftUI
import CampusCore

struct ProfileView: View {
    @Environment(AppModel.self) private var app
    @State private var confirmLogout = false

    var body: some View {
        List {
            Section {
                HStack(spacing: 15) {
                    Image(systemName: "person.crop.circle.fill").font(.system(size: 52)).foregroundStyle(.tint)
                    VStack(alignment: .leading, spacing: 5) {
                        Text(app.session?.user.displayName ?? "我的账号").font(.title3.bold())
                        Text(app.session?.user.universityName.nonEmpty ?? "尚未选择学校").foregroundStyle(.secondary)
                    }
                }.padding(.vertical, 8)
                if let user = app.session?.user { LabeledContent("UID", value: user.uid).textSelection(.enabled) }
            }
            Section("个人资料") {
                NavigationLink { AccountView() } label: { Label("账号与个人资料", systemImage: "person.text.rectangle") }
                NavigationLink { SimpleRemoteList(title: "我的文件", path: "personal-hub/files", icon: "folder") } label: { Label("我的文件", systemImage: "folder") }
                NavigationLink { SimpleRemoteList(title: "我的收藏", path: "personal-hub/favorites", icon: "star") } label: { Label("我的收藏", systemImage: "star") }
            }
            Section {
                NavigationLink { SettingsView() } label: { Label("设置", systemImage: "gearshape") }
            }
            Section { Button("退出登录", role: .destructive) { confirmLogout = true } }
        }
        .navigationTitle("我的")
        .refreshable { await app.refreshProfile() }
        .confirmationDialog("退出当前账号？", isPresented: $confirmLogout, titleVisibility: .visible) {
            Button("退出登录", role: .destructive) { Task { await app.signOut() } }
        }
    }
}

struct SettingsView: View {
    @Environment(AppModel.self) private var app
    @State private var address = ""
    @State private var error: String?
    @State private var changing = false

    var body: some View {
        @Bindable var app = app
        Form {
            Section("外观") {
                Picker("主题", selection: $app.theme) {
                    Text("跟随系统").tag("system"); Text("浅色").tag("light"); Text("深色").tag("dark")
                }
                Toggle("减少动态效果", isOn: $app.reduceMotion)
            }
            Section("提醒") { Toggle("待办和考试提醒", isOn: $app.remindersEnabled) }
            Section {
                TextField("服务器地址", text: $address).textInputAutocapitalization(.never).autocorrectionDisabled().keyboardType(.URL)
                Button(changing ? "正在切换…" : "保存服务器地址") {
                    changing = true
                    Task {
                        defer { changing = false }
                        do { try await app.configureServer(address) } catch { self.error = error.localizedDescription }
                    }
                }.disabled(changing)
            } header: { Text("服务连接") } footer: { Text("切换服务器会使用对应服务的登录状态。") }
            Section("关于") {
                LabeledContent("应用", value: "CampusMate")
                LabeledContent("版本", value: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0")
                Text("学习观察仅作辅助，不代表学习效果或心理状态判断。").font(.footnote).foregroundStyle(.secondary)
            }
        }.navigationTitle("设置").onAppear { address = app.serverURL }.errorAlert($error)
    }
}

struct AccountView: View {
    @Environment(AppModel.self) private var app
    @State private var displayName = ""
    @State private var college = ""
    @State private var major = ""
    @State private var grade = ""
    @State private var saving = false
    @State private var error: String?
    @State private var saved = false

    var body: some View {
        Form {
            Section("个人资料") {
                TextField("显示名称", text: $displayName)
                TextField("学院", text: $college)
                TextField("专业", text: $major)
                TextField("年级", text: $grade)
            }
            Section {
                Button(saving ? "正在保存…" : "保存修改") {
                    saving = true
                    Task {
                        defer { saving = false }
                        do {
                            _ = try await app.client.request(.patch, path: "auth/me", body: ["display_name": .string(displayName), "college": .string(college), "major": .string(major), "grade": .string(grade)])
                            await app.refreshProfile(); saved = true
                        } catch { self.error = error.localizedDescription }
                    }
                }.disabled(saving || displayName.isEmpty)
            }
        }
        .navigationTitle("个人资料")
        .onAppear {
            if let user = app.session?.user { displayName = user.displayName; college = user.college; major = user.major; grade = user.grade }
        }
        .errorAlert($error)
        .alert("资料已保存", isPresented: $saved) { Button("好", role: .cancel) { } }
    }
}
