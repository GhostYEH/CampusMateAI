import SwiftUI
import UniformTypeIdentifiers
import QuickLook
import UserNotifications
import CampusCore

// MARK: - Profile

struct ProfileView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var showAbout = false

    var body: some View {
        ZStack {
            CampusSceneBackground(name: "campus_twilight_original")
            Color(hex: 0x132634, opacity: 0.64).ignoresSafeArea()
            ScrollView {
                VStack(spacing: 14) {
                    hero
                    Text("更多服务")
                        .font(.system(size: 17, weight: .bold))
                        .foregroundStyle(Color(hex: 0xFFECD0))
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(.horizontal, 20)
                    menu
                }
                .padding(.bottom, 30)
                .frame(maxWidth: 760)
                .frame(maxWidth: .infinity)
            }
        }
        .campusImmersive()
        .refreshable { await app.refreshProfile() }
        .alert("关于 CampusMate", isPresented: $showAbout) {
            Button("知道了", role: .cancel) { }
        } message: {
            Text("面向大学生的成长型智能陪伴助手。CPM 的回答仅作辅助建议，学校正式通知为准。")
        }
    }

    private var hero: some View {
        VStack(spacing: 0) {
            VStack(alignment: .leading, spacing: 0) {
                HStack(alignment: .top) {
                    VStack(alignment: .leading, spacing: 3) {
                        HStack(spacing: 10) {
                            CampusBackButton(tint: .white, onDarkBackground: true) { dismiss() }
                            Text("我的").font(.system(size: 28, weight: .bold)).foregroundStyle(.white)
                        }
                        Text("今天也照顾好自己的节奏")
                            .font(.system(size: 11)).foregroundStyle(.white.opacity(0.74))
                            .padding(.leading, 2)
                    }
                    Spacer()
                    NavigationLink { QRLoginView() } label: {
                        Image(systemName: "viewfinder")
                            .font(.system(size: 19, weight: .medium))
                            .foregroundStyle(.white)
                            .frame(width: 40, height: 40)
                            .background(Color.white.opacity(0.12), in: Circle())
                    }
                    .accessibilityLabel("扫一扫")
                }
                .padding(.horizontal, 20)
                .padding(.top, 15)

                Spacer().frame(height: 26)

                NavigationLink { AccountView() } label: {
                    HStack(spacing: 17) {
                        Image("profile_avatar_reference")
                            .resizable()
                            .scaledToFill()
                            .frame(width: 82, height: 82)
                            .clipShape(Circle())
                            .padding(3)
                            .background(Color(hex: 0xFFFEF8), in: Circle())
                            .accessibilityLabel("个人头像")
                        VStack(alignment: .leading, spacing: 7) {
                            Text(app.session?.user.displayName ?? "我的账号")
                                .font(.system(size: 24, weight: .bold))
                                .foregroundStyle(.white)
                                .lineLimit(1)
                            Text(detailLine)
                                .font(.system(size: 14))
                                .foregroundStyle(.white.opacity(0.84))
                                .lineLimit(1)
                            HStack(spacing: 6) {
                                Circle().fill(Color(hex: 0x9BE1C0)).frame(width: 6, height: 6)
                                Text("点击查看和编辑个人资料")
                                    .font(.system(size: 9))
                                    .foregroundStyle(.white.opacity(0.88))
                            }
                            .padding(.horizontal, 9)
                            .padding(.vertical, 5)
                            .background(Color.white.opacity(0.12), in: Capsule())
                        }
                        Spacer(minLength: 0)
                        Image(systemName: "chevron.right").font(.system(size: 14, weight: .semibold)).foregroundStyle(.white.opacity(0.8))
                    }
                    .padding(.horizontal, 20)
                    .contentShape(Rectangle())
                }
                .buttonStyle(.plain)
                Spacer().frame(height: 58)
            }
            .frame(height: 318)
            .background(
                LinearGradient(colors: [Color(hex: 0x172747, opacity: 0.82),
                                        Color(hex: 0x1E3553, opacity: 0.76),
                                        Color(hex: 0x172747, opacity: 0.55)],
                               startPoint: .top, endPoint: .bottom),
                in: UnevenRoundedRectangle(bottomLeadingRadius: 30, bottomTrailingRadius: 30)
            )
            .overlay(alignment: .topTrailing) {
                Circle().fill(Color.white.opacity(0.055)).frame(width: 150).offset(x: 40, y: -40).allowsHitTesting(false)
            }
            .clipped()

            quickActions
                .padding(.horizontal, 9)
                .offset(y: -64)
                .padding(.bottom, -64)
        }
    }

    private var detailLine: String {
        let user = app.session?.user
        let parts = [user?.major, user?.grade].compactMap { $0 }.filter { !$0.isEmpty }
        if !parts.isEmpty { return parts.joined(separator: " · ") }
        return user?.universityName.isEmpty == false ? user!.universityName : "尚未选择学校"
    }

    private var quickActions: some View {
        HStack(spacing: 0) {
            NavigationLink { AccountView() } label: { quickAction(icon: "person.fill", label: "资料", accent: false) }
            NavigationLink { PersonalHubView(favorites: true) } label: { quickAction(icon: "bookmark.fill", label: "收藏", accent: true) }
            NavigationLink { SettingsView() } label: { quickAction(icon: "gearshape.fill", label: "设置", accent: false) }
        }
        .frame(height: 94)
        .padding(.horizontal, 7)
        .padding(.vertical, 16)
        .background(Color(hex: 0xFFFEF8), in: RoundedRectangle(cornerRadius: 24, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 24, style: .continuous).strokeBorder(Color(hex: 0xD7DED5, opacity: 0.7), lineWidth: 1))
        .frame(height: 126)
    }

    private func quickAction(icon: String, label: String, accent: Bool) -> some View {
        VStack(spacing: 9) {
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .fill(accent ? Color(hex: 0xE08A4E, opacity: 0.12) : Color(hex: 0xE4EEE5))
                .frame(width: 43, height: 43)
                .overlay(Image(systemName: icon).font(.system(size: 18, weight: .medium))
                    .foregroundStyle(accent ? Color(hex: 0xE08A4E) : Color(hex: 0x285B4B)))
            Text(label).font(.system(size: 12, weight: .semibold)).foregroundStyle(Color(hex: 0x1B2730))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .contentShape(Rectangle())
    }

    private var menu: some View {
        VStack(spacing: 0) {
            menuRow(icon: "doc.text", title: "我的文件", route: AnyView(PersonalHubView()))
            divider
            menuRow(icon: "bell.badge", title: "系统消息", route: AnyView(NoticesView()))
            divider
            menuRow(icon: "building.columns", title: "教务系统", route: AnyView(EduSystemView()))
            divider
            menuRow(icon: "lock.shield", title: "隐私与数据", route: AnyView(SettingsView()))
            divider
            menuRow(icon: "headphones", title: "帮助与反馈", route: AnyView(HelpFeedbackView()))
            divider
            Button { showAbout = true } label: {
                HStack {
                    Image(systemName: "info.circle").font(.system(size: 22)).foregroundStyle(Color(hex: 0x285B4B))
                    Text("关于 CampusMate").font(.system(size: 16, weight: .medium)).foregroundStyle(Color(hex: 0x1B2730))
                    Spacer()
                    Image(systemName: "chevron.right").font(.system(size: 13, weight: .semibold)).foregroundStyle(Color(hex: 0x667784))
                }
                .padding(.horizontal, 16)
                .frame(height: 70)
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
        }
        .background(Color(hex: 0xFFFEF8), in: RoundedRectangle(cornerRadius: 22, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 22, style: .continuous).strokeBorder(Color(hex: 0xD7DED5, opacity: 0.7), lineWidth: 1))
        .padding(.horizontal, 16)
    }

    private func menuRow(icon: String, title: String, route: AnyView) -> some View {
        NavigationLink { route } label: {
            HStack {
                Image(systemName: icon).font(.system(size: 21)).foregroundStyle(Color(hex: 0x285B4B))
                Text(title).font(.system(size: 16, weight: .medium)).foregroundStyle(Color(hex: 0x1B2730)).padding(.leading, 14)
                Spacer()
                Image(systemName: "chevron.right").font(.system(size: 13, weight: .semibold)).foregroundStyle(Color(hex: 0x667784))
            }
            .padding(.horizontal, 16)
            .frame(height: 70)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }

    private var divider: some View {
        Rectangle().fill(Color(hex: 0xD7DED5)).frame(height: 1).padding(.leading, 53)
    }
}

// MARK: - Account

struct AccountView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var displayName = ""
    @State private var college = ""
    @State private var major = ""
    @State private var grade = ""
    @State private var saving = false
    @State private var error: String?
    @State private var saved = false

    var body: some View {
        CampusSecondaryScaffold(title: "账号设置") {
            ScrollView {
                VStack(spacing: 14) {
                    CampusCard {
                        VStack(alignment: .leading, spacing: 12) {
                            HStack(spacing: 14) {
                                Image("profile_avatar_reference").resizable().scaledToFill()
                                    .frame(width: 62, height: 62).clipShape(Circle())
                                VStack(alignment: .leading, spacing: 4) {
                                    Text(app.session?.user.displayName ?? "同学").campusFont(.subtitle).foregroundStyle(Color(hex: 0x1B2730))
                                    Text(app.session?.user.universityName ?? "尚未选择学校").campusFont(.caption).foregroundStyle(.secondary)
                                }
                                Spacer()
                            }
                            Divider()
                            LabeledContent("UID", value: app.session?.user.uid ?? "—")
                                .campusFont(.caption)
                            NavigationLink { UniversityPickerView() } label: {
                                HStack {
                                    Text("我的学校").campusFont(.body).foregroundStyle(Color(hex: 0x1B2730))
                                    Spacer()
                                    Text(app.session?.user.universityName ?? "选择").campusFont(.caption).foregroundStyle(.secondary)
                                    Image(systemName: "chevron.right").font(.system(size: 12)).foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                    CampusCard {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("个人资料").campusFont(.subtitle).foregroundStyle(Color(hex: 0x1B2730))
                            field("显示名称", text: $displayName)
                            field("学院", text: $college)
                            field("专业", text: $major)
                            field("年级", text: $grade)
                            CampusPrimaryButton(title: saving ? "正在保存…" : "保存修改", loading: saving,
                                                enabled: !displayName.isEmpty) { save() }
                        }
                    }
                    if saved {
                        Text("资料已保存").campusFont(.caption).foregroundStyle(Color(hex: 0x4E8C6A))
                    }
                }
                .padding(20)
                .frame(maxWidth: 700)
                .frame(maxWidth: .infinity)
            }
        }
        .onAppear {
            guard let user = app.session?.user else { return }
            displayName = user.displayName; college = user.college; major = user.major; grade = user.grade
        }
        .errorAlert($error)
    }

    private func field(_ placeholder: String, text: Binding<String>) -> some View {
        CampusTextField(placeholder: placeholder, text: text)
    }

    private func save() {
        saving = true
        Task {
            defer { saving = false }
            do {
                _ = try await app.client.request(.patch, path: "auth/me",
                                                 body: ["display_name": .string(displayName), "college": .string(college),
                                                        "major": .string(major), "grade": .string(grade)])
                await app.refreshProfile()
                saved = true
                CampusHaptics.success()
            } catch { self.error = error.localizedDescription }
        }
    }
}

// MARK: - Settings

struct SettingsView: View {
    @Environment(AppModel.self) private var app
    @State private var confirmSignOut = false
    @State private var address = ""
    @State private var error: String?
    @State private var changing = false
    @State private var notificationStatus: UNAuthorizationStatus = .notDetermined

    var body: some View {
        @Bindable var app = app
        CampusSecondaryScaffold(title: "系统设置") {
            ScrollView {
                VStack(spacing: 14) {
                    CampusCard {
                        VStack(alignment: .leading, spacing: 14) {
                            Text("外观").campusFont(.subtitle).foregroundStyle(Color(hex: 0x1B2730))
                            Picker("主题", selection: $app.theme) {
                                Text("跟随系统").tag("system"); Text("浅色").tag("light"); Text("深色").tag("dark")
                            }
                            .pickerStyle(.segmented)
                            Toggle("减少动态效果", isOn: $app.reduceMotion).tint(Color(hex: 0x285B4B))
                                .campusFont(.body)
                        }
                    }
                    CampusCard {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("提醒").campusFont(.subtitle).foregroundStyle(Color(hex: 0x1B2730))
                            Toggle("待办和考试提醒", isOn: $app.remindersEnabled).tint(Color(hex: 0x285B4B))
                            Text(reminderHint).campusFont(.caption).foregroundStyle(.secondary)
                            if notificationStatus == .denied {
                                Button("前往系统设置开启通知") {
                                    if let url = URL(string: UIApplication.openSettingsURLString) { UIApplication.shared.open(url) }
                                }
                                .campusFont(.caption).foregroundStyle(Color(hex: 0x285B4B))
                            }
                        }
                    }
                    CampusCard {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("服务连接").campusFont(.subtitle).foregroundStyle(Color(hex: 0x1B2730))
                            CampusTextField(placeholder: "服务器地址", text: $address, systemImage: "server.rack", keyboard: .URL)
                            Text("切换服务器会使用对应服务的登录状态。").campusFont(.caption).foregroundStyle(.secondary)
                            CampusSecondaryButton(title: changing ? "正在切换…" : "保存服务器地址", systemImage: "checkmark", enabled: !changing) {
                                changing = true
                                Task {
                                    defer { changing = false }
                                    do { try await app.configureServer(address) } catch { self.error = error.localizedDescription }
                                }
                            }
                        }
                    }
                    CampusCard {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("关于").campusFont(.subtitle).foregroundStyle(Color(hex: 0x1B2730))
                            LabeledContent("应用", value: "CampusMate")
                            LabeledContent("版本", value: Bundle.main.infoDictionary?["CFBundleShortVersionString"] as? String ?? "1.0")
                            Text("学习观察仅作辅助，不代表学习效果或心理状态判断。iOS 不读取其他应用的通知，通知整理依赖服务端同步、手动导入与本机提醒。")
                                .campusFont(.caption).foregroundStyle(.secondary)
                        }
                    }
                    CampusCard {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("账号").campusFont(.subtitle).foregroundStyle(Color(hex: 0x1B2730))
                            Text(app.session?.user.displayName ?? "当前账号").campusFont(.caption).foregroundStyle(.secondary)
                            Button(role: .destructive) { confirmSignOut = true } label: {
                                Text("退出登录").campusFont(.body).fontWeight(.semibold)
                                    .foregroundStyle(Color(hex: 0xC25450))
                                    .frame(maxWidth: .infinity).frame(height: 44)
                                    .background(Color(hex: 0xF6DAD8), in: RoundedRectangle(cornerRadius: 14))
                            }
                            .accessibilityIdentifier("settings.signout")
                        }
                    }
                    NavigationLink { NotificationSourcesView() } label: {
                        HStack {
                            Label("通知来源与权限", systemImage: "bell.badge")
                                .campusFont(.body).foregroundStyle(Color(hex: 0x1B2730))
                            Spacer()
                            Image(systemName: "chevron.right").font(.system(size: 12)).foregroundStyle(.secondary)
                        }
                        .padding(16)
                        .background(Color(hex: 0xFFFEF8), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                    }
                    .buttonStyle(.plain)
                }
                .padding(20)
                .frame(maxWidth: 700)
                .frame(maxWidth: .infinity)
            }
        }
        .onAppear { address = app.serverURL }
        .confirmationDialog("退出当前账号？", isPresented: $confirmSignOut, titleVisibility: .visible) {
            Button("退出登录", role: .destructive) { Task { await app.signOut() } }
        }
        .task { notificationStatus = await ReminderScheduler.shared.authorizationStatus() }
        .onChange(of: app.remindersEnabled) { _, enabled in
            Task {
                if enabled {
                    _ = await ReminderScheduler.shared.requestAuthorization()
                    notificationStatus = await ReminderScheduler.shared.authorizationStatus()
                } else {
                    await ReminderScheduler.shared.cancelAll()
                }
            }
        }
        .errorAlert($error)
    }

    private var reminderHint: String {
        switch notificationStatus {
        case .authorized, .provisional: "已允许通知，将在截止前 30 分钟提醒个人待办，考试前 1 小时提醒。"
        case .denied: "通知权限已关闭，提醒不会送达。可在系统设置中重新开启。"
        default: "开启后会请求系统通知权限；来源系统的待办保持原系统的提醒。"
        }
    }
}

// MARK: - Personal hub

struct PersonalHubView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    var favorites = false
    @State private var resource = RemoteResource()
    @State private var importing = false
    @State private var working = false
    @State private var error: String?
    @State private var deleting: JSONValue?
    private var scope: String { app.serverURL + "|" + (app.session?.user.id ?? "") }

    var body: some View {
        CampusSecondaryScaffold(title: favorites ? "我的收藏" : "我的文件") {
            ScrollView {
                VStack(spacing: 10) {
                    if resource.isLoading && resource.value == .null { CampusLoadingState() }
                    else if let error = resource.error, resource.value == .null { CampusErrorState(message: error) { Task { await load() } } }
                    else if resource.value.items.isEmpty {
                        CampusEmptyState(title: favorites ? "还没有收藏" : "还没有个人文件",
                                         message: favorites ? "收藏的内容会保存在这里。" : "选择一个文件，整理你的学习资料。",
                                         systemImage: favorites ? "star" : "folder")
                    } else {
                        ForEach(Array(resource.value.items.enumerated()), id: \.offset) { _, item in
                            NavigationLink {
                                if favorites { SavedDestinationView(value: item) } else { PersonalFileView(item: item) }
                            } label: {
                                hubRow(item)
                            }
                            .buttonStyle(.plain)
                            .contextMenu {
                                Button(favorites ? "移除收藏" : "删除", role: .destructive) { deleting = item }
                            }
                        }
                    }
                    if !favorites {
                        Text("文件信息可跨设备同步；原文件保留在本机。用于生成课堂的文件，请在互动课堂页面另行上传。")
                            .campusFont(.caption).foregroundStyle(.secondary)
                            .frame(maxWidth: .infinity, alignment: .leading)
                    }
                }
                .padding(20)
                .frame(maxWidth: 700)
                .frame(maxWidth: .infinity)
            }
        }
        .toolbar {
            if !favorites {
                ToolbarItem(placement: .topBarTrailing) {
                    Button { importing = true } label: { Image(systemName: "plus") }
                        .accessibilityLabel("添加文件")
                }
            }
        }
        .task { await load() }
        .refreshable { await load() }
        .fileImporter(isPresented: $importing, allowedContentTypes: [.item], allowsMultipleSelection: false) { result in
            do { if let url = try result.get().first { add(url) } } catch { self.error = error.localizedDescription }
        }
        .confirmationDialog(favorites ? "移除这项收藏？" : "删除这项文件记录和本机副本？",
                            isPresented: Binding(get: { deleting != nil }, set: { if !$0 { deleting = nil } }), titleVisibility: .visible) {
            if let deleting {
                Button("确认删除", role: .destructive) {
                    Task {
                        do {
                            if favorites { try await PersonalService(client: app.client).removeFavorite(id: deleting["id"].text) }
                            else {
                                try await PersonalService(client: app.client).removeFile(id: deleting["id"].text)
                                try LocalFileStore.remove(id: deleting["id"].text, scope: scope)
                            }
                            self.deleting = nil; await load()
                        } catch { self.error = error.localizedDescription }
                    }
                }
            }
        }
        .errorAlert($error)
    }

    private func hubRow(_ item: JSONValue) -> some View {
        HStack(spacing: 12) {
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(Color(hex: 0xE4EEE5)).frame(width: 42, height: 42)
                .overlay(Image(systemName: favorites ? "star.fill" : "doc.text")
                    .font(.system(size: 17)).foregroundStyle(Color(hex: 0x285B4B)))
            VStack(alignment: .leading, spacing: 3) {
                Text(item.displayTitle).campusFont(.body).foregroundStyle(Color(hex: 0x1B2730)).lineLimit(1)
                let subtitle = [item["category"].text, item["size_label"].text].filter { !$0.isEmpty }.joined(separator: " · ")
                if !subtitle.isEmpty { Text(subtitle).campusFont(.caption).foregroundStyle(.secondary) }
            }
            Spacer()
            Image(systemName: "chevron.right").font(.system(size: 12)).foregroundStyle(.secondary)
        }
        .padding(14)
        .background(Color(hex: 0xFFFEF8), in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).strokeBorder(Color(hex: 0xD7DED5, opacity: 0.6), lineWidth: 1))
    }

    private func load() async {
        await resource.load(client: app.client, path: favorites ? "personal-hub/favorites" : "personal-hub/files")
    }

    private func add(_ source: URL) {
        working = true
        Task {
            defer { working = false }
            var copied: URL?
            do {
                let file = try LocalFileStore.importFile(source, scope: scope); copied = file
                let size = (try? file.resourceValues(forKeys: [.fileSizeKey]).fileSize) ?? 0
                let result = try await app.client.request(.post, path: "personal-hub/files", body: [
                    "name": .string(source.lastPathComponent), "category": "学习资料", "source": "iOS 本机",
                    "size_label": .string(ByteCountFormatter.string(fromByteCount: Int64(size), countStyle: .file))
                ])
                guard let id = result["id"].string else { throw APIError(code: "INVALID_RESPONSE", message: "文件记录未返回有效标识。") }
                try LocalFileStore.register(file, id: id, scope: scope)
                copied = nil; await load()
            } catch {
                if let copied { try? FileManager.default.removeItem(at: copied) }
                self.error = error.localizedDescription
            }
        }
    }
}

struct PersonalFileView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    let item: JSONValue
    @State private var current: JSONValue = .null
    @State private var preview: URL?
    @State private var working = false
    @State private var error: String?
    private var value: JSONValue { current == .null ? item : current }
    private var scope: String { app.serverURL + "|" + (app.session?.user.id ?? "") }
    private var localFile: URL? { LocalFileStore.file(id: item["id"].text, scope: scope) }

    var body: some View {
        CampusSecondaryScaffold(title: "文件详情") {
            ScrollView {
                VStack(spacing: 12) {
                    CampusCard {
                        VStack(alignment: .leading, spacing: 8) {
                            Text(value["name"].text).campusFont(.title).foregroundStyle(Color(hex: 0x1B2730))
                            if let size = value["size_label"].string { LabeledContent("大小", value: size).campusFont(.caption) }
                            if let category = value["category"].string { LabeledContent("分类", value: category).campusFont(.caption) }
                            if let source = value["source"].string { LabeledContent("来源", value: source).campusFont(.caption) }
                        }
                    }
                    if let file = localFile {
                        CampusPrimaryButton(title: "预览文件", systemImage: "doc.text.magnifyingglass") { preview = file }
                        ShareLink(item: file) {
                            Label("分享文件", systemImage: "square.and.arrow.up")
                                .campusFont(.body).foregroundStyle(Color(hex: 0x285B4B))
                                .frame(maxWidth: .infinity).frame(height: 44)
                                .background(Color(hex: 0xE4EEE5), in: RoundedRectangle(cornerRadius: 14))
                        }
                    } else {
                        Label("原文件不在这台设备上", systemImage: "icloud.slash").campusFont(.caption).foregroundStyle(.secondary)
                    }
                    CampusSecondaryButton(title: value["is_favorite"].bool == true ? "取消收藏" : "收藏",
                                          systemImage: value["is_favorite"].bool == true ? "star.fill" : "star",
                                          enabled: !working) { favorite() }
                }
                .padding(20)
                .frame(maxWidth: 700)
                .frame(maxWidth: .infinity)
            }
        }
        .quickLookPreview($preview)
        .errorAlert($error)
    }

    private func favorite() {
        working = true
        Task {
            defer { working = false }
            do {
                current = try await PersonalService(client: app.client).favoriteFile(id: item["id"].text,
                                                                                     favorite: value["is_favorite"].bool != true)
                let favoriteID = "file:" + item["id"].text
                if current["is_favorite"].bool == true {
                    _ = try await app.client.request(.post, path: "personal-hub/favorites", body: [
                        "id": .string(favoriteID), "title": item["name"], "type": "文件",
                        "subtitle": item["category"], "source_route": "files"
                    ])
                } else {
                    try await PersonalService(client: app.client).removeFavorite(id: favoriteID)
                }
            } catch { self.error = error.localizedDescription }
        }
    }
}

struct SavedDestinationView: View {
    let value: JSONValue
    var body: some View {
        let route = value["source_route"].text.trimmingCharacters(in: CharacterSet(charactersIn: "/"))
        let parts = route.split(separator: "/").map(String.init)
        if parts.count >= 2 && parts[0] == "courses" { CourseDetailView(courseID: parts[1]) }
        else if parts.count >= 2 && parts[0] == "community_detail" { CommunityDetailView(postID: parts[1]) }
        else if parts.count >= 2 && parts[0] == "task_detail", let task = try? TaskItem(json: ["id": .string(parts[1]), "title": value["title"]]) { TaskDetailView(initial: task) }
        else if route == "files" && value["id"].text.hasPrefix("file:") {
            PersonalFileView(item: ["id": .string(String(value["id"].text.dropFirst(5))), "name": value["title"]])
        } else { RecordDetailView(value: value, title: "收藏详情") }
    }
}

// MARK: - Help

struct HelpFeedbackView: View {
    @Environment(AppModel.self) private var app
    @State private var online: Bool?

    var body: some View {
        CampusSecondaryScaffold(title: "帮助与反馈") {
            ScrollView {
                VStack(spacing: 12) {
                    HStack(spacing: 12) {
                        Image(systemName: online == true ? "checkmark.icloud" : "exclamationmark.icloud")
                            .font(.system(size: 20))
                            .foregroundStyle(online == true ? Color(hex: 0x17A66A) : Color(hex: 0xF0784A))
                        VStack(alignment: .leading, spacing: 3) {
                            Text(online == true ? "服务连接正常" : "正在重新连接服务")
                                .campusFont(.body).fontWeight(.semibold).foregroundStyle(Color(hex: 0x1B2730))
                            Text(online == true ? "当前功能可以使用真实后端数据。" : "请稍候，或检查此设备的后端地址与网络。")
                                .campusFont(.caption).foregroundStyle(.secondary)
                        }
                        Spacer()
                    }
                    .padding(16)
                    .background(online == true ? Color(hex: 0xEAF8F0) : Color(hex: 0xFFEFEA), in: RoundedRectangle(cornerRadius: 20, style: .continuous))

                    Text("常见问题").campusFont(.body).fontWeight(.bold).foregroundStyle(Color(hex: 0x1B2730))
                        .frame(maxWidth: .infinity, alignment: .leading).padding(.leading, 4)
                    helpCard("为什么会显示未连接？", "登录后应用会自动检查服务；真机调试需使用电脑可访问的服务地址，而不是模拟器专用的 10.0.2.2。")
                    helpCard("如何重新检查连接？", "回到设置页或本页下拉即可刷新服务状态；连接恢复后无需重新登录。")
                    helpCard("为什么 iOS 收不到微信通知？", "iOS 不允许应用读取其他应用的通知。请使用通知页的手动粘贴提取，或连接学习通同步课程通知。")
                    helpCard("数据与隐私", "专注画面默认仅在本机分析、不保存不上传；样本贡献必须由你主动授权。")
                }
                .padding(20)
                .frame(maxWidth: 700)
                .frame(maxWidth: .infinity)
            }
        }
        .task {
            do { _ = try await app.client.request(path: "health"); online = true }
            catch { online = false }
        }
    }

    private func helpCard(_ title: String, _ detail: String) -> some View {
        HStack(alignment: .top, spacing: 12) {
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .fill(Color(hex: 0xE4EEE5)).frame(width: 40, height: 40)
                .overlay(Image(systemName: "questionmark.circle").font(.system(size: 18)).foregroundStyle(Color(hex: 0x285B4B)))
            VStack(alignment: .leading, spacing: 4) {
                Text(title).campusFont(.body).fontWeight(.semibold).foregroundStyle(Color(hex: 0x1B2730))
                Text(detail).campusFont(.caption).foregroundStyle(.secondary)
            }
            Spacer(minLength: 0)
        }
        .padding(16)
        .background(Color(hex: 0xFFFEF8), in: RoundedRectangle(cornerRadius: 20, style: .continuous))
    }
}

// MARK: - Notification sources

/// iOS cannot observe other apps' notification streams. This page states that
/// limitation and routes the same intent through real, available channels.
struct NotificationSourcesView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var status: String?
    @State private var lastSynced: String?
    @State private var showExtract = false
    @State private var notificationStatus: UNAuthorizationStatus = .notDetermined

    var body: some View {
        CampusSecondaryScaffold(title: "通知与提醒") {
            ScrollView {
                VStack(spacing: 12) {
                    CampusCard {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("iOS 的通知边界").campusFont(.body).fontWeight(.semibold).foregroundStyle(Color(hex: 0x1B2730))
                            Text("系统不允许第三方应用读取微信、企业微信或 QQ 的通知内容。CampusMate 不会假装拥有该能力。可以用下面的三种真实来源整理事务。")
                                .campusFont(.caption).foregroundStyle(.secondary)
                        }
                    }
                    CampusCard {
                        VStack(alignment: .leading, spacing: 12) {
                            sourceRow(icon: "doc.on.clipboard", title: "手动粘贴提取", subtitle: "复制通知原文，提取成待办", status: "可用", tone: .success) {
                                showExtract = true
                            }
                            Divider()
                            sourceRow(icon: "arrow.triangle.2.circlepath", title: "学习通同步", subtitle: lastSynced.map { "课程 · 作业 · 通知 · 上次 \($0.prefix(16))" } ?? "同步课程、作业与课程通知",
                                      status: status == "online" ? "已连接" : status == "expired" ? "需重新登录" : "未连接",
                                      tone: status == "online" ? .success : status == "expired" ? .danger : .neutral) {
                            }
                            Divider()
                            sourceRow(icon: "bell", title: "本机提醒", subtitle: "个人待办与考试的系统本地通知",
                                      status: notificationStatus == .authorized ? "已允许" : notificationStatus == .denied ? "已关闭" : "未开启",
                                      tone: notificationStatus == .authorized ? .success : notificationStatus == .denied ? .danger : .neutral) {
                                Task {
                                    _ = await ReminderScheduler.shared.requestAuthorization()
                                    notificationStatus = await ReminderScheduler.shared.authorizationStatus()
                                }
                            }
                        }
                    }
                    NavigationLink { ChaoxingView() } label: {
                        HStack {
                            Label("连接或同步学习通", systemImage: "graduationcap")
                                .campusFont(.body).foregroundStyle(Color(hex: 0x285B4B))
                            Spacer()
                            Image(systemName: "chevron.right").font(.system(size: 12)).foregroundStyle(.secondary)
                        }
                        .padding(16)
                        .background(Color(hex: 0xFFFEF8), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
                    }
                    .buttonStyle(.plain)
                }
                .padding(20)
                .frame(maxWidth: 700)
                .frame(maxWidth: .infinity)
            }
        }
        .task {
            notificationStatus = await ReminderScheduler.shared.authorizationStatus()
            if let value = try? await app.client.request(path: "chaoxing/status") {
                status = value["status"].string
                lastSynced = value["last_synced_at"].string
            }
        }
        .sheet(isPresented: $showExtract) { NavigationStack { TaskImportView(noticeMode: true) } }
    }

    private func sourceRow(icon: String, title: String, subtitle: String, status: String, tone: CampusStatusTone, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            HStack(spacing: 12) {
                Image(systemName: icon).font(.system(size: 17)).foregroundStyle(Color(hex: 0x285B4B)).frame(width: 26)
                VStack(alignment: .leading, spacing: 3) {
                    Text(title).campusFont(.body).foregroundStyle(Color(hex: 0x1B2730))
                    Text(subtitle).campusFont(.caption).foregroundStyle(.secondary).lineLimit(2)
                }
                Spacer(minLength: 4)
                CampusStatusTag(text: status, tone: tone)
            }
            .padding(.vertical, 4)
            .contentShape(Rectangle())
        }
        .buttonStyle(.plain)
    }
}
