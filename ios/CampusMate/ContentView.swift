import SwiftUI
import CampusCore

struct ContentView: View {
    @Environment(AppModel.self) private var app
    @Environment(\.colorScheme) private var systemScheme

    private var palette: CampusPalette {
        switch app.theme {
        case "light": return .light
        case "dark": return .dark
        default: return systemScheme == .dark ? .dark : .light
        }
    }

    private var preferredScheme: ColorScheme? {
        switch app.theme {
        case "light": return .light
        case "dark": return .dark
        default: return nil
        }
    }

    var body: some View {
        Group {
            if app.isRestoring {
                ZStack {
                    CampusScene.ink.ignoresSafeArea()
                    VStack(spacing: 14) {
                        Image("splash_twilight")
                            .resizable()
                            .scaledToFit()
                            .frame(width: 148)
                            .clipShape(RoundedRectangle(cornerRadius: 28, style: .continuous))
                        Text("CampusMate").font(.system(size: 20, weight: .bold)).foregroundStyle(.white)
                        ProgressView().tint(.white)
                    }
                }
            } else if app.session == nil {
                LoginView()
            } else {
                CampusRootView()
            }
        }
        .campusPalette(palette)
        .preferredColorScheme(preferredScheme)
        .task { await app.start() }
    }
}
