import SwiftUI

@main
struct CampusMateApp: App {
    @State private var model = AppModel()
    var body: some Scene {
        WindowGroup {
            ContentView()
                .environment(model)
                .tint(Color(red: 0.16, green: 0.44, blue: 0.34))
                .preferredColorScheme(model.theme == "system" ? nil : model.theme == "dark" ? .dark : .light)
        }
    }
}

