import SwiftUI
import CampusCore

/// Port of `TwilightDashboardScreen`: one continuous illustration where the
/// library, study room and classroom are the navigation, plus the five arch
/// destinations along the bottom of the scene.
struct TwilightHomeView: View {
    @Environment(AppModel.self) private var app

    @State private var entrance: Double = 0
    @State private var entrancePlayed = false

    private let archLabels = ["社区", "学习足迹", "待办", "CPM", "我的"]
    private let archRoutes: [CampusRoute] = [.community, .focusHistory, .tasks, .counselor, .profile]

    var body: some View {
        GeometryReader { proxy in
            let sceneWidth = proxy.size.width
            let sceneHeight = sceneWidth * (1870.0 / 841.0)
            ScrollView(.vertical, showsIndicators: false) {
                scene(width: sceneWidth, height: sceneHeight)
                    .frame(width: sceneWidth, height: sceneHeight)
                    .frame(maxWidth: .infinity)
            }
            .scrollBounceBehavior(.basedOnSize)
            .background(CampusScene.ink.ignoresSafeArea())
        }
        .background(CampusScene.ink.ignoresSafeArea())
        .toolbar(.hidden, for: .navigationBar)
        .interactivePopGestureEnabled()
        .onAppear(perform: playEntrance)
        .onChange(of: app.reduceMotion) { _, _ in playEntrance() }
        .accessibilityElement(children: .contain)
    }

    private var entranceProgress: Double { app.reduceMotion ? 1 : entrance }

    private func playEntrance() {
        if app.reduceMotion {
            entrance = 1
            entrancePlayed = true
            return
        }
        guard !entrancePlayed else { entrance = 1; return }
        entrance = 0
        withAnimation(.easeOut(duration: 0.85).delay(0.08)) { entrance = 1 }
        entrancePlayed = true
    }

    private func scene(width: CGFloat, height: CGFloat) -> some View {
        ZStack(alignment: .topLeading) {
            Image("campus_twilight_original")
                .resizable()
                .interpolation(.high)
                .scaledToFill()
                .frame(width: width, height: height)
                .clipped()
                .accessibilityHidden(true)
                .scaleEffect(1 + 0.018 * (1 - entranceProgress))
                .animation(app.reduceMotion ? nil : .easeOut(duration: 0.85), value: entranceProgress)

            LinearGradient(colors: [Color(hex: 0x101E3A, opacity: 0.65), .clear],
                           startPoint: .top, endPoint: .bottom)
                .frame(width: width, height: height * 0.20)
                .allowsHitTesting(false)

            VStack(alignment: .leading, spacing: 2) {
                Text("CampusMate")
                    .font(.system(size: 30, weight: .bold))
                    .foregroundStyle(.white)
                Text("沿着灯光，走进今天的学习")
                    .font(.system(size: 14))
                    .foregroundStyle(CampusScene.cream)
            }
            .padding(.horizontal, 24)
            .padding(.top, 18)
            .opacity(titleReveal)
            .offset(y: (1 - titleReveal) * 6)
            .animation(app.reduceMotion ? nil : .easeOut(duration: 0.6), value: entranceProgress)
            .allowsHitTesting(false)

            landmark(title: "二楼图书馆", sign: "图书馆", alignment: .bottomTrailing,
                     x: width * 0.11, y: height * 0.19, width: width * 0.39, height: height * 0.20,
                     route: .courses)
            landmark(title: "一楼自习室", sign: "自习室", alignment: .bottomLeading,
                     x: width * 0.10, y: height * 0.39, width: width * 0.40, height: height * 0.15,
                     route: .focus)
            landmark(title: "互动课堂", sign: "互动课堂", alignment: .topLeading,
                     x: width * 0.58, y: height * 0.38, width: width * 0.42, height: height * 0.28,
                     route: .classroomHub)

            ForEach(Array(archLabels.enumerated()), id: \.offset) { index, label in
                let x = width * (0.065 + Double(index) * 0.19)
                arch(label: label, route: archRoutes[index], index: index,
                     x: x,
                     y: height * 0.835,
                     width: min(width * 0.18, width - x), height: height * 0.087)
            }
        }
        .frame(width: width, height: height)
        .clipped()
    }

    private var titleReveal: Double {
        min(max((entranceProgress - 0.12) / 0.45, 0), 1)
    }

    @ViewBuilder
    private func landmark(title: String, sign: String, alignment: Alignment,
                          x: CGFloat, y: CGFloat, width: CGFloat, height: CGFloat,
                          route: CampusRoute) -> some View {
        NavigationLink(value: route) {
            Rectangle()
                .fill(.clear)
                .frame(width: width, height: height)
                .overlay(alignment: alignment) {
                    Text(sign)
                        .font(.system(size: 11, weight: .medium))
                        .tracking(0.5)
                        .foregroundStyle(CampusScene.cream)
                        .padding(.horizontal, 7)
                        .padding(.vertical, 3)
                        .background(CampusScene.ink.opacity(0.72), in: RoundedRectangle(cornerRadius: 3))
                        .overlay(
                            RoundedRectangle(cornerRadius: 3)
                                .strokeBorder(CampusScene.cream.opacity(0.34), lineWidth: 0.5)
                        )
                        .padding(8)
                }
                .contentShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
        }
        .buttonStyle(LandmarkButtonStyle(reduceMotion: app.reduceMotion))
        .offset(x: x, y: y)
        .accessibilityLabel("进入\(title)")
        .accessibilityHint("打开\(title)页面")
    }

    @ViewBuilder
    private func arch(label: String, route: CampusRoute, index: Int,
                      x: CGFloat, y: CGFloat, width: CGFloat, height: CGFloat) -> some View {
        let reveal = min(max((entranceProgress - (0.42 + Double(index) * 0.07)) / 0.22, 0), 1)
        NavigationLink(value: route) {
            Rectangle()
                .fill(.clear)
                .frame(width: width, height: height)
                .overlay(alignment: .bottom) {
                    Text(label)
                        .font(.system(size: 10, weight: .bold))
                        .foregroundStyle(.white)
                        .padding(.horizontal, 5)
                        .background(CampusScene.ink.opacity(0.58), in: RoundedRectangle(cornerRadius: 8))
                        .padding(.bottom, 5)
                        .opacity(reveal)
                        .offset(y: (1 - reveal) * 4)
                }
                .contentShape(ArchShape(topRadius: 36, bottomRadius: 8))
        }
        .buttonStyle(LandmarkButtonStyle(reduceMotion: app.reduceMotion))
        .offset(x: x, y: y)
        .accessibilityLabel("打开\(label)")
    }
}

struct ArchShape: Shape {
    var topRadius: CGFloat = 36
    var bottomRadius: CGFloat = 8

    func path(in rect: CGRect) -> Path {
        let top = min(topRadius, rect.width / 2)
        let bottom = min(bottomRadius, rect.width / 2)
        var path = Path()
        path.move(to: CGPoint(x: rect.minX, y: rect.maxY - bottom))
        path.addLine(to: CGPoint(x: rect.minX, y: rect.minY + top))
        path.addQuadCurve(to: CGPoint(x: rect.minX + top, y: rect.minY),
                          control: CGPoint(x: rect.minX, y: rect.minY))
        path.addLine(to: CGPoint(x: rect.maxX - top, y: rect.minY))
        path.addQuadCurve(to: CGPoint(x: rect.maxX, y: rect.minY + top),
                          control: CGPoint(x: rect.maxX, y: rect.minY))
        path.addLine(to: CGPoint(x: rect.maxX, y: rect.maxY - bottom))
        path.addQuadCurve(to: CGPoint(x: rect.maxX - bottom, y: rect.maxY),
                          control: CGPoint(x: rect.maxX, y: rect.maxY))
        path.addLine(to: CGPoint(x: rect.minX + bottom, y: rect.maxY))
        path.addQuadCurve(to: CGPoint(x: rect.minX, y: rect.maxY - bottom),
                          control: CGPoint(x: rect.minX, y: rect.maxY))
        path.closeSubpath()
        return path
    }
}

struct LandmarkButtonStyle: ButtonStyle {
    var reduceMotion = false
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 1.012 : 1)
            .animation(reduceMotion ? nil : .easeOut(duration: 0.18), value: configuration.isPressed)
    }
}
