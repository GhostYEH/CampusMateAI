import SwiftUI
import CampusCore

struct HomeView: View {
    @Environment(AppModel.self) private var app
    @State private var agenda = RemoteResource()

    var body: some View {
        List {
            Section {
                VStack(alignment: .leading, spacing: 7) {
                    Text("你好，\(app.session?.user.displayName ?? "同学")").font(.title2.bold())
                    Text(Date.now.formatted(.dateTime.month(.wide).day().weekday(.wide)))
                        .font(.subheadline).foregroundStyle(.secondary)
                }.padding(.vertical, 10)
            }.listRowBackground(Color.clear)

            Section("今日安排") {
                ResourceStateView(resource: agenda, isEmpty: agenda.value.items.isEmpty,
                                  title: "今天暂时没有待办", message: "课程、个人待办和学习计划会汇总到这里。", systemImage: "checkmark.circle", retry: load)
                ForEach(Array(agenda.value.items.enumerated()), id: \.offset) { _, item in
                    NavigationLink { RecordDetailView(value: item, title: "今日安排") } label: { RecordRow(value: item, icon: "checklist") }
                }
                if agenda.value["stale"].bool == true { Label("同步数据可能不是最新，请前往学习通刷新。", systemImage: "clock.badge.exclamationmark").font(.footnote).foregroundStyle(.secondary) }
            }

            Section("学习与生活") {
                NavigationLink { SimpleRemoteList(title: "专注记录", path: "study/sessions", icon: "timer") } label: { Label("自习室与学习足迹", systemImage: "timer") }
                NavigationLink { SimpleRemoteList(title: "互动课堂", path: "self-classroom", icon: "rectangle.on.rectangle") } label: { Label("互动课堂", systemImage: "rectangle.on.rectangle") }
                NavigationLink { CommunityView() } label: { Label("校园社区", systemImage: "bubble.left.and.bubble.right") }
                NavigationLink { ExamsView() } label: { Label("考试安排", systemImage: "calendar.badge.clock") }
                NavigationLink { NoticesView() } label: { Label("通知中心", systemImage: "bell") }
            }
            Section("学习计划") {
                NavigationLink { SimpleRemoteList(title: "目标与计划", path: "student-goals", icon: "target") } label: { Label("目标与计划", systemImage: "target") }
                NavigationLink { SimpleRemoteList(title: "期末复习", path: "final-review/campaigns", icon: "book.closed") } label: { Label("期末复习", systemImage: "book.closed") }
                NavigationLink { SimpleRemoteList(title: "课程研究", path: "course-research/runs", icon: "magnifyingglass") } label: { Label("课程研究", systemImage: "magnifyingglass") }
            }
            Section {
                NavigationLink { CommunityView(initialSort: "hot") } label: { Label("校园热搜", systemImage: "flame") }
            }
        }
        .navigationTitle("首页")
        .task { await load() }
        .refreshable { await load() }
    }
    private func load() async { await agenda.load(client: app.client, path: "agenda/today") }
}
