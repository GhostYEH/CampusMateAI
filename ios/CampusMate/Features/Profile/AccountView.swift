import SwiftUI
import UniformTypeIdentifiers
import QuickLook
import UserNotifications
import CampusCore

struct AccountView: View {
    @Environment(\.campus) private var palette
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
                                    Text(app.session?.user.displayName ?? "同学").campusFont(.subtitle).foregroundStyle(palette.textPrimary)
                                    Text(app.session?.user.universityName ?? "尚未选择学校").campusFont(.caption).foregroundStyle(.secondary)
                                }
                                Spacer()
                            }
                            Divider()
                            LabeledContent("UID", value: app.session?.user.uid ?? "—")
                                .campusFont(.caption)
                            NavigationLink { UniversityPickerView() } label: {
                                HStack {
                                    Text("我的学校").campusFont(.body).foregroundStyle(palette.textPrimary)
                                    Spacer()
                                    Text(app.session?.user.universityName ?? "选择").campusFont(.caption).foregroundStyle(.secondary)
                                    Image(systemName: "chevron.right").font(.system(size: 12)).foregroundStyle(.secondary)
                                }
                            }
                        }
                    }
                    CampusCard {
                        VStack(alignment: .leading, spacing: 12) {
                            Text("个人资料").campusFont(.subtitle).foregroundStyle(palette.textPrimary)
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
