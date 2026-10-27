import SwiftUI
import CampusCore

struct ContentView: View {
    @Environment(AppModel.self) private var app
    var body: some View {
        Group {
            if app.isRestoring { ProgressView("CampusMate") }
            else if app.session == nil { LoginView() }
            else {
                TabView {
                    NavigationStack { HomeView() }.tabItem { Label("首页", systemImage: "house") }
                    NavigationStack { CoursesView() }.tabItem { Label("课程", systemImage: "books.vertical") }
                    NavigationStack { TasksView() }.tabItem { Label("待办", systemImage: "checklist") }
                    NavigationStack { AssistantView() }.tabItem { Label("CPM", systemImage: "bubble.left.and.bubble.right") }
                    NavigationStack { ProfileView() }.tabItem { Label("我的", systemImage: "person.crop.circle") }
                }.id(app.scope)
            }
        }
        .task { await app.start() }
    }
}
