import SwiftUI
import UniformTypeIdentifiers
import QuickLook
import UserNotifications
import CampusCore

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
                .accessibilityIdentifier("profile.settings")
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
            menuRow(icon: "doc.text", title: "我的文件") { PersonalHubView() }
            divider
            menuRow(icon: "bell.badge", title: "系统消息") { NoticesView() }
                .accessibilityIdentifier("profile.notices")
            divider
            menuRow(icon: "building.columns", title: "教务系统") { EduSystemView() }
            divider
            menuRow(icon: "lock.shield", title: "隐私与数据") { SettingsView() }
            divider
            menuRow(icon: "headphones", title: "帮助与反馈") { HelpFeedbackView() }
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

    private func menuRow<Destination: View>(icon: String, title: String, @ViewBuilder destination: () -> Destination) -> some View {
        NavigationLink(destination: destination) {
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
