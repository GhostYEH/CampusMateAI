import SwiftUI
import QuickLook
import UniformTypeIdentifiers
import CampusCore

/// Port of `LibraryScreen`: the course list is a bookshelf, and each book is a
/// real synced course. Only courses confirmed to come from the student's own
/// Chaoxing account are shelved.
struct CoursesView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.dismiss) private var dismiss
    @State private var resource = PagedResource()
    @State private var search = ""
    @State private var status: String?
    @State private var lastSynced: String?
    @State private var checkingStatus = true
    @State private var syncing = false
    @State private var showSync = false
    @State private var syncMessage: String?
    @State private var selected: CourseSummary?

    private var courses: [CourseSummary] {
        resource.items.compactMap { CourseSummary(json: $0) }.filter { $0.provider.lowercased() == "chaoxing" }
    }
    private var matching: [CourseSummary] {
        guard !search.trimmingCharacters(in: .whitespaces).isEmpty else { return courses }
        let needle = search.trimmingCharacters(in: .whitespaces)
        return courses.filter {
            [$0.name, $0.teacher, $0.code].contains { $0.localizedCaseInsensitiveContains(needle) }
        }
    }
    private var term: (start: Date, end: Date) { CourseTerm.current() }
    private var currentTermCourses: [CourseSummary] {
        matching.filter { $0.isInTerm(term.start, term.end) }.sorted(by: CourseSummary.shelfOrder)
    }
    private var otherCourses: [CourseSummary] {
        matching.filter { !$0.isInTerm(term.start, term.end) }.sorted(by: CourseSummary.shelfOrder)
    }

    var body: some View {
        ZStack {
            CampusSceneBackground(name: "focus_scene_quiet_library")
            LinearGradient(colors: [Color(hex: 0x152536, opacity: 0.79),
                                    Color(hex: 0x152536, opacity: 0.56),
                                    Color(hex: 0x0C1A25, opacity: 0.86)],
                           startPoint: .top, endPoint: .bottom)
                .ignoresSafeArea()

            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    header
                    shelfHeading
                    learningRoomsLink
                    searchField
                    content
                    Text("轻触一本书，查看课程目录")
                        .font(.system(size: 12))
                        .foregroundStyle(.white.opacity(0.72))
                }
                .padding(.horizontal, 20)
                .padding(.top, 18)
                .padding(.bottom, 36)
                .frame(maxWidth: 760)
                .frame(maxWidth: .infinity)
            }
            .refreshable { await load() }
        }
        .campusImmersive()
        .task { await bootstrap() }
        .sheet(item: $selected) { course in
            CourseBookSheet(course: course)
        }
        .sheet(isPresented: $showSync) {
            syncDialog.presentationDetents([.medium, .large])
                .presentationBackground(Color.clear)
        }
    }

    private var header: some View {
        HStack(spacing: 14) {
            CampusBackButton(tint: .white, onDarkBackground: true) { dismiss() }
            VStack(alignment: .leading, spacing: 2) {
                Text("图书馆").font(.system(size: 25, weight: .bold)).foregroundStyle(.white)
                Text("从你的课程出发，找到今天要学的内容")
                    .font(.system(size: 12)).foregroundStyle(.white.opacity(0.82))
            }
            Spacer(minLength: 0)
        }
        .padding(.bottom, 2)
    }

    private var shelfHeading: some View {
        HStack(alignment: .center) {
            VStack(alignment: .leading, spacing: 3) {
                Text("我的课程书架").font(.system(size: 20, weight: .bold)).foregroundStyle(.white)
                Text("\(courses.count) 门课程").font(.system(size: 12)).foregroundStyle(.white.opacity(0.76))
            }
            Spacer()
            Button { showSync = true; CampusHaptics.tap() } label: {
                Text("同步课程")
                    .font(.system(size: 13, weight: .bold))
                    .foregroundStyle(Color(hex: 0x2A433B))
                    .padding(.horizontal, 14)
                    .padding(.vertical, 10)
                    .background(Color(hex: 0xF2DFC0), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
            }
            .buttonStyle(CampusPressStyle())
        }
    }

    private var learningRoomsLink: some View {
        NavigationLink { LearningRoomsView() } label: {
            Text("同学一起学 · 共同课堂")
                .font(.system(size: 14, weight: .bold))
                .foregroundStyle(CampusScene.libraryGreen)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 16)
                .padding(.vertical, 14)
                .background(Color(hex: 0xF5F0E3, opacity: 0.92), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
        }
        .buttonStyle(CampusPressStyle())
    }

    private var searchField: some View {
        HStack(spacing: 10) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 15, weight: .medium))
                .foregroundStyle(CampusScene.libraryGreen)
            TextField("查找课程、老师或课程号", text: $search)
                .font(.system(size: 14))
                .foregroundStyle(CampusScene.libraryGreen)
                .textInputAutocapitalization(.never)
                .autocorrectionDisabled()
            if !search.isEmpty {
                Button { search = "" } label: {
                    Image(systemName: "xmark.circle.fill").foregroundStyle(CampusScene.libraryGreen.opacity(0.8))
                }
                .accessibilityLabel("清除搜索")
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
        .background(Color(hex: 0xF5F0E3, opacity: 0.92), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
        .overlay(
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .strokeBorder(Color(hex: 0xD6BA8C, opacity: 0.6), lineWidth: 1)
        )
    }

    @ViewBuilder
    private var content: some View {
        if checkingStatus && courses.isEmpty {
            CampusLoadingState(message: "正在检查学习通连接…")
                .foregroundStyle(.white)
        } else if resource.isLoading && courses.isEmpty {
            CampusLoadingState(message: "正在整理课程书架…")
        } else if let error = resource.error, courses.isEmpty {
            CampusErrorState(message: error) { Task { await load() } }
        } else if status == "online" {
            if courses.isEmpty {
                LibraryNote(title: "还没有同步到课程",
                            message: "同步后会展示学习通返回的课程；这里不会填入演示课程。")
            } else if matching.isEmpty {
                LibraryNote(title: "没有找到这门课", message: "试试课程名称、老师或课程号。")
            } else {
                if !currentTermCourses.isEmpty {
                    ShelfHeadingRow(title: "本学期", subtitle: "最近开课的课程放在前面", count: currentTermCourses.count)
                    shelfRows(currentTermCourses, offset: 0)
                }
                if !otherCourses.isEmpty {
                    ShelfHeadingRow(title: "其他课程", subtitle: "按开课时间从新到旧", count: otherCourses.count)
                    shelfRows(otherCourses, offset: currentTermCourses.count)
                }
            }
        } else {
            LibraryNote(title: status == "expired" ? "学习通登录已失效" : "尚未连接学习通",
                        message: "连接后，这里会按你的真实课程摆上书架。")
            Button { showSync = true } label: {
                Text(status == "expired" ? "重新连接学习通" : "连接学习通")
                    .font(.system(size: 14, weight: .bold))
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .frame(height: 46)
                    .background(
                        LinearGradient(colors: [Color(hex: 0xBD9C5E), Color(hex: 0x71653F)],
                                       startPoint: .leading, endPoint: .trailing),
                        in: RoundedRectangle(cornerRadius: 14, style: .continuous)
                    )
            }
            .buttonStyle(CampusPressStyle())
        }
    }

    @ViewBuilder
    private func shelfRows(_ list: [CourseSummary], offset: Int) -> some View {
        let rows = stride(from: 0, to: list.count, by: 3).map { Array(list[$0..<min($0 + 3, list.count)]) }
        ForEach(Array(rows.enumerated()), id: \.offset) { rowIndex, row in
            CourseShelfRow(courses: row, baseIndex: offset + rowIndex * 3) { course in
                CampusHaptics.tap()
                selected = course
            }
        }
    }

    private var syncDialog: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("同步课程").font(.system(size: 21, weight: .bold)).foregroundStyle(.white)
            Text(statusText).font(.system(size: 13)).foregroundStyle(.white.opacity(0.88))
            if status == "online" {
                if let lastSynced {
                    Text("上次同步：\(lastSynced.prefix(16).replacingOccurrences(of: "T", with: " "))")
                        .font(.system(size: 12)).foregroundStyle(.white.opacity(0.73))
                }
                Text("这里更新课程书架。进入某门课程后，可单独更新它的章节、资料、作业与通知。")
                    .font(.system(size: 12)).foregroundStyle(.white.opacity(0.78))
                Button {
                    Task { await sync() }
                } label: {
                    HStack(spacing: 8) {
                        if syncing { ProgressView().tint(.white).controlSize(.small) }
                        Text(syncing ? "正在同步…" : "同步课程").font(.system(size: 15, weight: .bold))
                    }
                    .foregroundStyle(.white)
                    .frame(maxWidth: .infinity)
                    .frame(height: 46)
                    .background(
                        LinearGradient(colors: [Color(hex: 0xBD9C5E), Color(hex: 0x71653F)],
                                       startPoint: .leading, endPoint: .trailing),
                        in: RoundedRectangle(cornerRadius: 14, style: .continuous)
                    )
                }
                .disabled(syncing)
            } else if status == "offline" || status == "expired" {
                NavigationLink { ChaoxingView() } label: {
                    Text(status == "expired" ? "重新连接学习通" : "连接学习通")
                        .font(.system(size: 15, weight: .bold))
                        .foregroundStyle(.white)
                        .frame(maxWidth: .infinity)
                        .frame(height: 46)
                        .background(
                            LinearGradient(colors: [Color(hex: 0xBD9C5E), Color(hex: 0x71653F)],
                                           startPoint: .leading, endPoint: .trailing),
                            in: RoundedRectangle(cornerRadius: 14, style: .continuous)
                        )
                }
            } else {
                Button("重试连接") { Task { await checkStatus() } }
                    .font(.system(size: 15, weight: .bold)).foregroundStyle(.white)
            }
            if let syncMessage { Text(syncMessage).font(.system(size: 12)).foregroundStyle(.white) }
            Button("关闭") { showSync = false }
                .font(.system(size: 14))
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity, alignment: .trailing)
                .padding(.top, 2)
        }
        .padding(20)
        .background(
            LinearGradient(colors: [Color(hex: 0x173B35), Color(hex: 0x4D6247)],
                           startPoint: .topLeading, endPoint: .bottomTrailing),
            in: RoundedRectangle(cornerRadius: 24, style: .continuous)
        )
        .overlay(
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .strokeBorder(Color(hex: 0xE9D7A8, opacity: 0.6), lineWidth: 1)
        )
        .padding(20)
    }

    private var statusText: String {
        switch status {
        case "online": "已连接学习通 · \(courses.count) 门课程"
        case "expired": "学习通登录已失效"
        case "offline": "尚未连接学习通"
        case "checking": "正在检查连接…"
        default: "暂时无法确认连接，请检查网络"
        }
    }

    private func bootstrap() async {
        await checkStatus()
        await load()
    }

    private func checkStatus() async {
        checkingStatus = true
        defer { checkingStatus = false }
        do {
            let value = try await app.client.request(path: "chaoxing/status")
            status = value["status"].string ?? "unavailable"
            lastSynced = value["last_synced_at"].string
        } catch is CancellationError { }
        catch { status = "unavailable" }
    }

    private func load() async {
        await resource.load(client: app.client, path: "courses", query: search.isEmpty ? [:] : ["query": search])
    }

    private func sync() async {
        guard !syncing else { return }
        syncing = true
        defer { syncing = false }
        do {
            let result = try await app.client.request(.post, path: "chaoxing/sync")
            let ok = result["success"].bool ?? (result["status"].string == "ok")
            if ok {
                await load()
                lastSynced = try? await app.client.request(path: "chaoxing/status")["last_synced_at"].string
                syncMessage = "课程已更新"
                CampusHaptics.success()
            } else {
                let reason = result["reason"].string ?? result["message"].string ?? "同步失败"
                if reason.contains("reauth") || reason.contains("verification") {
                    status = "expired"; syncMessage = "登录已失效，请重新连接"
                } else { syncMessage = "同步失败：\(reason)" }
                CampusHaptics.warning()
            }
        } catch { syncMessage = error.localizedDescription }
    }
}

// MARK: - Course model

struct CourseSummary: Identifiable, Hashable {
    let json: JSONValue
    var id: String { json["id"].text }
    var name: String { json["name"].text.isEmpty ? "未命名课程" : json["name"].text }
    var teacher: String { json["teacher_name"].string ?? json["teacher"].string ?? "" }
    var code: String { json["code"].string ?? "" }
    var semester: String { json["semester"].string ?? "" }
    var provider: String { json["provider"].string ?? "" }
    var type: String { json["type"].string ?? json["course_type"].string ?? "课程" }
    var startDate: Date? {
        for key in ["starts_at", "start_date", "started_at"] {
            if let raw = json[key].string, raw.count >= 10 {
                let formatter = DateFormatter()
                formatter.locale = Locale(identifier: "en_US_POSIX")
                formatter.dateFormat = "yyyy-MM-dd"
                if let date = formatter.date(from: String(raw.prefix(10))) { return date }
            }
        }
        return nil
    }
    func isInTerm(_ start: Date, _ end: Date) -> Bool {
        if semester.contains("本学期") { return true }
        guard let date = startDate else { return false }
        return date >= start && date <= end
    }
    static func shelfOrder(_ left: CourseSummary, _ right: CourseSummary) -> Bool {
        switch (left.startDate, right.startDate) {
        case let (l?, r?): return l == r ? left.name < right.name : l > r
        case (nil, _?): return false
        case (_?, nil): return true
        default: return left.name < right.name
        }
    }
}

enum CourseTerm {
    static func current(_ today: Date = .now) -> (Date, Date) {
        let calendar = Calendar.current
        let year = calendar.component(.year, from: today)
        let month = calendar.component(.month, from: today)
        var components = DateComponents()
        components.year = month <= 2 ? year - 1 : year
        components.month = (3...8).contains(month) ? 3 : (month <= 2 ? 9 : 9)
        let start = calendar.date(from: components) ?? today
        let end = calendar.date(byAdding: DateComponents(month: 6, day: -1), to: start) ?? today
        return (start, end)
    }
}

// MARK: - Shelf

private struct ShelfHeadingRow: View {
    let title: String
    let subtitle: String
    let count: Int
    var body: some View {
        HStack(alignment: .bottom) {
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(.system(size: 21, weight: .bold)).foregroundStyle(.white)
                Text(subtitle).font(.system(size: 11)).foregroundStyle(.white.opacity(0.68))
            }
            Spacer()
            Text("\(count) 本").font(.system(size: 12, weight: .bold)).foregroundStyle(CampusScene.libraryGold)
        }
        .padding(.top, 6)
    }
}

private struct CourseShelfRow: View {
    let courses: [CourseSummary]
    let baseIndex: Int
    let onOpen: (CourseSummary) -> Void

    private let colors: [Color] = [
        Color(hex: 0x325F5A), Color(hex: 0x994D3D), Color(hex: 0x3B527C),
        Color(hex: 0x8B6A3D), Color(hex: 0x5B526F), Color(hex: 0x3F654A),
    ]

    var body: some View {
        ZStack(alignment: .bottom) {
            RoundedRectangle(cornerRadius: 3)
                .fill(LinearGradient(colors: [Color(hex: 0xB88A58), Color(hex: 0x68442F), Color(hex: 0x3A241C)],
                                     startPoint: .top, endPoint: .bottom))
                .frame(height: 18)
                .shadow(color: .black.opacity(0.35), radius: 7, y: 3)
            HStack(alignment: .bottom, spacing: 0) {
                ForEach(Array(courses.enumerated()), id: \.element.id) { index, course in
                    BookSpine(course: course, index: baseIndex + index, color: colors[(baseIndex + index) % colors.count]) {
                        onOpen(course)
                    }
                    .frame(maxWidth: .infinity)
                }
                ForEach(0..<(3 - courses.count), id: \.self) { _ in
                    Color.clear.frame(maxWidth: .infinity)
                }
            }
            .padding(.bottom, 17)
            Rectangle()
                .fill(CampusScene.libraryShelfEdge.opacity(0.65))
                .frame(height: 2)
        }
        .frame(height: 164)
    }
}

private struct BookSpine: View {
    let course: CourseSummary
    let index: Int
    let color: Color
    let onOpen: () -> Void
    @State private var pressed = false

    var body: some View {
        Button {
            onOpen()
        } label: {
            VStack(alignment: .leading, spacing: 0) {
                Rectangle().fill(CampusScene.libraryGold).frame(height: 1)
                Spacer().frame(height: 10)
                Text(course.name)
                    .font(.system(size: 13, weight: .bold))
                    .foregroundStyle(Color(hex: 0xFFF4D8))
                    .lineSpacing(4)
                    .lineLimit(4)
                    .frame(maxHeight: .infinity, alignment: .topLeading)
                Text(course.teacher.isEmpty ? "课程藏书" : course.teacher)
                    .font(.system(size: 9))
                    .foregroundStyle(CampusScene.libraryGold.opacity(0.87))
                    .lineLimit(1)
            }
            .padding(.leading, 13)
            .padding(.trailing, 7)
            .padding(.top, 11)
            .padding(.bottom, 10)
            .frame(maxWidth: .infinity, alignment: .leading)
            .frame(height: CGFloat(128 + (index % 3) * 5))
            .background(
                LinearGradient(colors: [color.opacity(0.84), color, Color(hex: 0x172B28)],
                               startPoint: .leading, endPoint: .trailing),
                in: RoundedRectangle(cornerRadius: 4, style: .continuous)
            )
            .overlay(
                RoundedRectangle(cornerRadius: 4, style: .continuous)
                    .strokeBorder(Color(hex: 0xE4CFA4, opacity: 0.87), lineWidth: 1)
            )
            .shadow(color: .black.opacity(0.3), radius: 7, y: 4)
            .rotationEffect(.degrees([-3, 2, 0][index % 3]), anchor: .bottom)
            .offset(y: pressed ? -18 : 0)
            .padding(.horizontal, 4)
        }
        .buttonStyle(.plain)
        .simultaneousGesture(DragGesture(minimumDistance: 0).onChanged { _ in pressed = true }.onEnded { _ in pressed = false })
        .animation(.easeOut(duration: 0.18), value: pressed)
        .accessibilityLabel("打开\(course.name)")
    }
}

private struct LibraryNote: View {
    let title: String
    let message: String
    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title).font(.system(size: 15, weight: .bold)).foregroundStyle(CampusScene.libraryGreen)
            Text(message).font(.system(size: 12)).foregroundStyle(Color(hex: 0x596B61))
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(17)
        .background(Color(hex: 0xF5F2E8, opacity: 0.84), in: RoundedRectangle(cornerRadius: 20, style: .continuous))
    }
}
