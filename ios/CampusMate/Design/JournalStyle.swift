import SwiftUI

// MARK: - Journal paper

/// Paper grain shared by the task journal pages. Drawing the grain with
/// `Canvas` keeps the asset-free look of the Android client and stays crisp at
/// every scale factor.
struct JournalGrain: View {
    var spacing: CGFloat = 22
    var dotOpacity: Double = 0.06
    var lineOpacity: Double = 0.075

    var body: some View {
        Canvas { context, size in
            var y: CGFloat = 0
            while y < size.height {
                var path = Path()
                path.move(to: CGPoint(x: 14, y: y))
                path.addLine(to: CGPoint(x: size.width - 12, y: y))
                context.stroke(path, with: .color(Color(hex: 0xA78968, opacity: lineOpacity)), lineWidth: 0.6)
                y += spacing
            }
            let columns = max(6, Int(size.width / 34))
            let rows = max(6, Int(size.height / 34))
            for row in 0...rows {
                for column in 0...columns {
                    let point = CGPoint(
                        x: size.width * (CGFloat(column) + 0.4) / CGFloat(columns),
                        y: size.height * (CGFloat(row) + 0.35) / CGFloat(rows)
                    )
                    context.fill(Path(ellipseIn: CGRect(x: point.x, y: point.y, width: 1.2, height: 1.2)),
                                 with: .color(Color(hex: 0xA88460, opacity: dotOpacity)))
                }
            }
        }
        .allowsHitTesting(false)
    }
}

struct JournalBookShape: Shape {
    var topLeading: CGFloat = 5
    var topTrailing: CGFloat = 22
    var bottomTrailing: CGFloat = 4
    var bottomLeading: CGFloat = 4

    func path(in rect: CGRect) -> Path {
        var path = Path()
        path.move(to: CGPoint(x: rect.minX + topLeading, y: rect.minY))
        path.addLine(to: CGPoint(x: rect.maxX - topTrailing, y: rect.minY))
        path.addQuadCurve(to: CGPoint(x: rect.maxX, y: rect.minY + topTrailing),
                          control: CGPoint(x: rect.maxX, y: rect.minY))
        path.addLine(to: CGPoint(x: rect.maxX, y: rect.maxY - bottomTrailing))
        path.addQuadCurve(to: CGPoint(x: rect.maxX - bottomTrailing, y: rect.maxY),
                          control: CGPoint(x: rect.maxX, y: rect.maxY))
        path.addLine(to: CGPoint(x: rect.minX + bottomLeading, y: rect.maxY))
        path.addQuadCurve(to: CGPoint(x: rect.minX, y: rect.maxY - bottomLeading),
                          control: CGPoint(x: rect.minX, y: rect.maxY))
        path.addLine(to: CGPoint(x: rect.minX, y: rect.minY + topLeading))
        path.addQuadCurve(to: CGPoint(x: rect.minX + topLeading, y: rect.minY),
                          control: CGPoint(x: rect.minX, y: rect.minY))
        path.closeSubpath()
        return path
    }
}

extension View {
    /// One continuous open page: visible spine, warm paper, quiet ruled lines.
    func journalBookPage() -> some View {
        self
            .background {
                ZStack(alignment: .leading) {
                    LinearGradient(
                        colors: [Color(hex: 0xD1C2A7), Color(hex: 0xF3EBDD), Color(hex: 0xFFFAEF), Color(hex: 0xF0E8DA)],
                        startPoint: .leading, endPoint: .trailing
                    )
                    HStack(spacing: 3) {
                        Rectangle().fill(Color(hex: 0x978069, opacity: 0.47)).frame(width: 1)
                        Rectangle().fill(Color.white.opacity(0.4)).frame(width: 1)
                        Spacer()
                    }
                    .padding(.leading, 12)
                    JournalGrain().padding(.leading, 24)
                }
            }
            .clipShape(JournalBookShape())
            .overlay {
                JournalBookShape().stroke(Color(hex: 0xC7B798, opacity: 0.53), lineWidth: 1)
            }
    }

    /// Rounded warm sheet used for dialogs and detail blocks.
    func journalSheet() -> some View {
        self
            .background {
                ZStack(alignment: .leading) {
                    LinearGradient(colors: [Color(hex: 0xFFFBF2), CampusJournal.paper, Color(hex: 0xECE8DC)],
                                   startPoint: .top, endPoint: .bottom)
                    HStack {
                        Rectangle().fill(Color(hex: 0xBD9D76, opacity: 0.27)).frame(width: 0.8)
                        Spacer()
                    }
                    .padding(.leading, 12)
                    JournalGrain(spacing: 30, dotOpacity: 0.05)
                }
            }
            .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 20, style: .continuous)
                    .strokeBorder(Color(hex: 0xCFBDA4, opacity: 0.4), lineWidth: 1)
            }
    }
}

/// Quiet desk-light backdrop of the task pages.
struct JournalBackdrop: View {
    var body: some View {
        ZStack {
            LinearGradient(colors: [Color(hex: 0x11253B), Color(hex: 0x2E3957), Color(hex: 0x584440)],
                           startPoint: .top, endPoint: .bottom)
            Canvas { context, size in
                let center = CGPoint(x: size.width * 0.86, y: size.height * 0.12)
                let radius = size.width * 0.75
                context.fill(
                    Path(ellipseIn: CGRect(x: center.x - radius, y: center.y - radius, width: radius * 2, height: radius * 2)),
                    with: .radialGradient(Gradient(colors: [Color(hex: 0xDFA76A, opacity: 0.33), .clear]),
                                          center: center, startRadius: 0, endRadius: radius)
                )
                let line = Color(hex: 0xD7BA91, opacity: 0.14)
                var first = Path()
                first.move(to: CGPoint(x: 0, y: size.height * 0.71))
                first.addLine(to: CGPoint(x: size.width, y: size.height * 0.63))
                context.stroke(first, with: .color(line), lineWidth: 1)
                var second = Path()
                second.move(to: CGPoint(x: 0, y: size.height * 0.71 + 18))
                second.addLine(to: CGPoint(x: size.width, y: size.height * 0.63 + 18))
                context.stroke(second, with: .color(line), lineWidth: 1)
                for row in 0...16 {
                    for column in 0...9 {
                        let point = CGPoint(x: size.width * (CGFloat(column) + 0.35) / 10,
                                            y: size.height * (CGFloat(row) + 0.45) / 17)
                        context.fill(Path(ellipseIn: CGRect(x: point.x, y: point.y, width: 1.4, height: 1.4)),
                                     with: .color(Color(hex: 0xFFF1D7, opacity: 0.08)))
                    }
                }
            }
        }
        .ignoresSafeArea()
    }
}

/// Paper "add" affordance used in the task journal header.
struct PaperPlusButton: View {
    let action: () -> Void

    var body: some View {
        Button {
            CampusHaptics.tap()
            action()
        } label: {
            ZStack {
                FoldedPageShape()
                    .fill(Color(hex: 0xF7EBD5))
                    .overlay(FoldedPageShape().stroke(Color(hex: 0xDBB985), lineWidth: 1))
                    .frame(width: 37, height: 37)
                Image(systemName: "plus")
                    .font(.system(size: 17, weight: .semibold))
                    .foregroundStyle(CampusJournal.ink)
                    .offset(y: 1)
            }
            .frame(width: 48, height: 48)
        }
        .buttonStyle(CampusPressStyle())
        .accessibilityLabel("新增个人待办")
    }
}

struct FoldedPageShape: Shape {
    func path(in rect: CGRect) -> Path {
        let fold = min(9, rect.width / 4)
        var path = Path()
        path.move(to: CGPoint(x: rect.minX + 1, y: rect.minY + 1))
        path.addLine(to: CGPoint(x: rect.maxX - fold, y: rect.minY + 1))
        path.addLine(to: CGPoint(x: rect.maxX - 1, y: rect.minY + fold))
        path.addLine(to: CGPoint(x: rect.maxX - 1, y: rect.maxY - 1))
        path.addLine(to: CGPoint(x: rect.minX + 1, y: rect.maxY - 1))
        path.closeSubpath()
        return path
    }
}

/// Ink stamp that lands on a task row when it is completed.
struct JournalStamp: View {
    let text: String
    var body: some View {
        Text(text)
            .font(.system(size: 15, weight: .black))
            .foregroundStyle(CampusJournal.ink)
            .padding(.horizontal, 8)
            .padding(.vertical, 3)
            .overlay(
                RoundedRectangle(cornerRadius: 6, style: .continuous)
                    .strokeBorder(CampusJournal.ink, lineWidth: 2)
            )
            .rotationEffect(.degrees(-12))
    }
}
