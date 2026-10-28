import SwiftUI
import CampusCore

struct FocusHistoryView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var resource = PagedResource()

    var body: some View {
        CampusSecondaryScaffold(title: "学习足迹") {
            ScrollView {
                VStack(spacing: 10) {
                    if resource.isLoading && resource.items.isEmpty { CampusLoadingState() }
                    else if let error = resource.error, resource.items.isEmpty { CampusErrorState(message: error) { Task { await load() } } }
                    else if resource.items.isEmpty {
                        CampusEmptyState(title: "还没有专注记录", message: "完成一次专注，记录你的学习足迹。", systemImage: "timer")
                    }
                    ForEach(Array(resource.items.enumerated()), id: \.offset) { _, item in
                        if let session = try? StudySession(json: item) {
                            NavigationLink {
                                if session.isActive { FocusSetupView() }
                                else { FocusSummaryView(session: session) }
                            } label: {
                                HStack(alignment: .top, spacing: 12) {
                                    VStack(spacing: 2) {
                                        Text("\(Int(session.elapsed(at: .now) / 60))")
                                            .font(.system(size: 20, weight: .heavy)).foregroundStyle(Color(hex: 0x285B4B))
                                        Text("分钟").font(.system(size: 9)).foregroundStyle(.secondary)
                                    }
                                    .frame(width: 44)
                                    VStack(alignment: .leading, spacing: 4) {
                                        Text(session.goal.nonEmpty ?? "专注学习").campusFont(.body).fontWeight(.semibold)
                                            .foregroundStyle(CampusJournal.ink).lineLimit(1)
                                        Text(session.startedAt.formatted(.dateTime.month().day().hour().minute()))
                                            .campusFont(.caption).foregroundStyle(.secondary)
                                        if !session.report.isEmpty {
                                            Text(session.report).campusFont(.caption).foregroundStyle(.secondary).lineLimit(2)
                                        }
                                    }
                                    Spacer()
                                }
                                .padding(14)
                                .background(Color(hex: 0xFFFEF8), in: RoundedRectangle(cornerRadius: 16))
                            }
                            .buttonStyle(.plain)
                        }
                    }
                }
                .padding(20)
                .frame(maxWidth: 700)
                .frame(maxWidth: .infinity)
            }
        }
        .task { await load() }
    }

    private func load() async { await resource.loadAll(client: app.client, path: "study/sessions") }
}

struct StudyCheckinView: View {
    @Environment(AppModel.self) private var app
    @State private var history = RemoteResource()
    @State private var minutes = 60
    @State private var mood = ""
    @State private var scene = "rain"
    @State private var working = false
    @State private var status: String?
    @State private var error: String?

    var body: some View {
        CampusSecondaryScaffold(title: "每日学习") {
            ScrollView {
                VStack(spacing: 12) {
                    CampusCard {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("每日目标").campusFont(.subtitle).foregroundStyle(CampusJournal.ink)
                            Stepper("每天 \(minutes) 分钟", value: $minutes, in: 15...480, step: 15)
                                .campusFont(.body)
                            CampusSecondaryButton(title: "保存目标") {
                                perform { _ = try await app.client.request(.put, path: "study/goals/daily",
                                                                          body: ["target_minutes": .number(Double(minutes))])
                                    status = "每日目标已保存。" }
                            }
                        }
                    }
                    CampusCard {
                        VStack(alignment: .leading, spacing: 10) {
                            Text("今日签到").campusFont(.subtitle).foregroundStyle(CampusJournal.ink)
                            Picker("心情场景", selection: $scene) {
                                Text("雨").tag("rain"); Text("雪").tag("snow"); Text("云").tag("cloud")
                            }.pickerStyle(.segmented)
                            CampusTextField(placeholder: "今天的心情（可选）", text: $mood)
                            CampusPrimaryButton(title: "签到", loading: working, enabled: mood.count <= 100) {
                                perform {
                                    let result = try await app.client.request(.post, path: "study/checkins",
                                                                             body: ["scene": .string(scene), "mood": mood.nonEmpty.map(JSONValue.string) ?? .null])
                                    status = result["created"].bool == false ? "今天已经签到。" : "签到已保存。"
                                    await history.load(client: app.client, path: "study/checkins")
                                }
                            }
                            if let status { Text(status).campusFont(.caption).foregroundStyle(.secondary) }
                        }
                    }
                    CampusCard {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("签到记录").campusFont(.subtitle).foregroundStyle(CampusJournal.ink)
                            ForEach(Array(history.value.items.enumerated()), id: \.offset) { _, item in
                                HStack {
                                    Text(item["checkin_date"].string ?? item["created_at"].text.prefix(10).description)
                                        .campusFont(.caption).foregroundStyle(CampusJournal.ink)
                                    Spacer()
                                    if let mood = item["mood"].string?.nonEmpty {
                                        Text(mood).campusFont(.caption).foregroundStyle(.secondary)
                                    }
                                }
                            }
                        }
                    }
                }
                .padding(20)
                .frame(maxWidth: 700)
                .frame(maxWidth: .infinity)
            }
        }
        .task {
            if let result = try? await app.client.request(path: "study/goals/daily") {
                minutes = result["target_minutes"].int ?? 60
            }
            await history.load(client: app.client, path: "study/checkins")
        }
        .errorAlert($error)
    }

    private func perform(_ action: @escaping @MainActor () async throws -> Void) {
        working = true
        Task {
            defer { working = false }
            do { try await action() } catch { self.error = error.localizedDescription }
        }
    }
}
