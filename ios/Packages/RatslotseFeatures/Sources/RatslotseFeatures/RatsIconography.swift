import RatslotseDesign
import SwiftUI

enum RatsGlyph: Sendable {
    case home
    case ask
    case calendar
    case decisions
    case topics
    case more
    case search
    case map
    case analysis
    case subscriptions
    case saved
    case quiz
    case profile
    case feedback
    case help
    case legal
    case logout
    case filter
    case back
    case history
    case research
}

/// A compact, code-native icon family used for Ratslotse's primary navigation.
/// The shared rounded stroke keeps the shell visually coherent instead of
/// mixing unrelated SF Symbol weights and optical sizes.
struct RatsGlyphView: View {
    let glyph: RatsGlyph
    var color: Color = RatsColor.primary
    var lineWidth: CGFloat = 1.8

    var body: some View {
        Canvas { context, size in
            let scale = min(size.width, size.height) / 24
            func point(_ x: CGFloat, _ y: CGFloat) -> CGPoint {
                CGPoint(x: x * scale + (size.width - 24 * scale) / 2,
                        y: y * scale + (size.height - 24 * scale) / 2)
            }
            func stroke(_ path: Path) {
                context.stroke(
                    path,
                    with: .color(color),
                    style: StrokeStyle(
                        lineWidth: lineWidth * scale,
                        lineCap: .round,
                        lineJoin: .round
                    )
                )
            }
            func fillCircle(_ x: CGFloat, _ y: CGFloat, _ diameter: CGFloat) {
                let rect = CGRect(
                    x: point(x, y).x,
                    y: point(x, y).y,
                    width: diameter * scale,
                    height: diameter * scale
                )
                context.fill(Path(ellipseIn: rect), with: .color(color))
            }

            var path = Path()
            switch glyph {
            case .home:
                path.move(to: point(3, 11)); path.addLine(to: point(12, 4)); path.addLine(to: point(21, 11))
                path.move(to: point(5.5, 9.2)); path.addLine(to: point(5.5, 20)); path.addLine(to: point(18.5, 20)); path.addLine(to: point(18.5, 9.2))
                path.move(to: point(9.5, 20)); path.addLine(to: point(9.5, 14)); path.addLine(to: point(14.5, 14)); path.addLine(to: point(14.5, 20))
            case .ask:
                path.addRoundedRect(in: CGRect(x: point(3, 5).x, y: point(3, 5).y, width: 15 * scale, height: 12 * scale), cornerSize: CGSize(width: 4 * scale, height: 4 * scale))
                path.move(to: point(8, 17)); path.addLine(to: point(6, 21)); path.addLine(to: point(12, 17))
                path.move(to: point(20, 3)); path.addLine(to: point(20, 7)); path.move(to: point(18, 5)); path.addLine(to: point(22, 5))
                path.move(to: point(18.6, 3.6)); path.addLine(to: point(21.4, 6.4)); path.move(to: point(21.4, 3.6)); path.addLine(to: point(18.6, 6.4))
            case .calendar:
                path.addRoundedRect(in: CGRect(x: point(3, 5).x, y: point(3, 5).y, width: 18 * scale, height: 16 * scale), cornerSize: CGSize(width: 3 * scale, height: 3 * scale))
                path.move(to: point(3, 10)); path.addLine(to: point(21, 10))
                path.move(to: point(8, 3)); path.addLine(to: point(8, 7)); path.move(to: point(16, 3)); path.addLine(to: point(16, 7))
                fillCircle(7, 13.5, 2); fillCircle(11, 13.5, 2); fillCircle(15, 13.5, 2); fillCircle(7, 17.5, 2); fillCircle(11, 17.5, 2)
            case .decisions:
                path.addRoundedRect(in: CGRect(x: point(5, 3).x, y: point(5, 3).y, width: 14 * scale, height: 18 * scale), cornerSize: CGSize(width: 2.5 * scale, height: 2.5 * scale))
                path.move(to: point(8.5, 8)); path.addLine(to: point(15.5, 8))
                path.move(to: point(8.5, 12)); path.addLine(to: point(15.5, 12))
                path.move(to: point(8.5, 16)); path.addLine(to: point(11, 18.2)); path.addLine(to: point(16, 14.2))
            case .topics:
                path.move(to: point(3, 11)); path.addLine(to: point(11, 3)); path.addLine(to: point(21, 13)); path.addLine(to: point(13, 21)); path.addLine(to: point(3, 11));
                path.addEllipse(in: CGRect(x: point(9, 7).x, y: point(9, 7).y, width: 3 * scale, height: 3 * scale))
                path.move(to: point(12, 12)); path.addLine(to: point(16, 16))
            case .more:
                for y in [4.0, 13.0] { for x in [4.0, 13.0] {
                    path.addRoundedRect(in: CGRect(x: point(x, y).x, y: point(x, y).y, width: 7 * scale, height: 7 * scale), cornerSize: CGSize(width: 2 * scale, height: 2 * scale))
                }}
            case .search:
                path.addEllipse(in: CGRect(x: point(3, 3).x, y: point(3, 3).y, width: 13 * scale, height: 13 * scale))
                path.move(to: point(14, 14)); path.addLine(to: point(21, 21))
            case .map:
                path.move(to: point(3, 6)); path.addLine(to: point(9, 3)); path.addLine(to: point(15, 6)); path.addLine(to: point(21, 3));
                path.addLine(to: point(21, 18)); path.addLine(to: point(15, 21)); path.addLine(to: point(9, 18)); path.addLine(to: point(3, 21)); path.closeSubpath()
                path.move(to: point(9, 3)); path.addLine(to: point(9, 18)); path.move(to: point(15, 6)); path.addLine(to: point(15, 21))
            case .analysis:
                path.move(to: point(4, 20)); path.addLine(to: point(4, 14)); path.addLine(to: point(8, 14)); path.addLine(to: point(8, 20));
                path.move(to: point(10, 20)); path.addLine(to: point(10, 10)); path.addLine(to: point(14, 10)); path.addLine(to: point(14, 20));
                path.move(to: point(16, 20)); path.addLine(to: point(16, 5)); path.addLine(to: point(20, 5)); path.addLine(to: point(20, 20));
                path.move(to: point(3, 20)); path.addLine(to: point(21, 20))
            case .subscriptions:
                path.move(to: point(5, 17))
                path.addCurve(to: point(8, 8), control1: point(7, 14), control2: point(6, 10))
                path.addCurve(to: point(16, 8), control1: point(10, 5), control2: point(14, 5))
                path.addCurve(to: point(19, 17), control1: point(18, 10), control2: point(17, 14))
                path.closeSubpath()
                path.move(to: point(9.5, 20)); path.addCurve(to: point(14.5, 20), control1: point(11, 22), control2: point(13, 22))
                path.move(to: point(12, 4)); path.addLine(to: point(12, 6))
            case .saved:
                path.addRoundedRect(in: CGRect(x: point(6, 3).x, y: point(6, 3).y, width: 12 * scale, height: 18 * scale), cornerSize: CGSize(width: 2 * scale, height: 2 * scale))
                path.move(to: point(6, 17)); path.addLine(to: point(12, 13)); path.addLine(to: point(18, 17))
            case .quiz:
                path.move(to: point(8, 4)); path.addLine(to: point(16, 4)); path.addLine(to: point(15, 10));
                path.addCurve(to: point(9, 10), control1: point(14, 14), control2: point(10, 14)); path.closeSubpath()
                path.move(to: point(8, 6)); path.addCurve(to: point(4, 10), control1: point(4, 6), control2: point(4, 8)); path.addCurve(to: point(9, 12), control1: point(5, 12), control2: point(7, 12))
                path.move(to: point(16, 6)); path.addCurve(to: point(20, 10), control1: point(20, 6), control2: point(20, 8)); path.addCurve(to: point(15, 12), control1: point(19, 12), control2: point(17, 12))
                path.move(to: point(12, 13)); path.addLine(to: point(12, 18)); path.move(to: point(8, 21)); path.addLine(to: point(16, 21)); path.move(to: point(9, 18)); path.addLine(to: point(15, 18))
            case .profile:
                path.addEllipse(in: CGRect(x: point(8, 3).x, y: point(8, 3).y, width: 8 * scale, height: 8 * scale))
                path.move(to: point(4, 21))
                path.addCurve(to: point(20, 21), control1: point(5, 13), control2: point(19, 13))
            case .feedback:
                path.addRoundedRect(in: CGRect(x: point(3, 4).x, y: point(3, 4).y, width: 18 * scale, height: 14 * scale), cornerSize: CGSize(width: 4 * scale, height: 4 * scale))
                path.move(to: point(8, 18)); path.addLine(to: point(6, 22)); path.addLine(to: point(13, 18))
                path.move(to: point(7, 9)); path.addLine(to: point(17, 9)); path.move(to: point(7, 13)); path.addLine(to: point(14, 13))
            case .help:
                path.addEllipse(in: CGRect(x: point(3, 3).x, y: point(3, 3).y, width: 18 * scale, height: 18 * scale))
                path.move(to: point(9, 9)); path.addCurve(to: point(13, 13), control1: point(9, 5), control2: point(17, 6)); path.addLine(to: point(12, 15)); fillCircle(11, 18, 2)
            case .legal:
                path.addRoundedRect(in: CGRect(x: point(5, 3).x, y: point(5, 3).y, width: 14 * scale, height: 18 * scale), cornerSize: CGSize(width: 2 * scale, height: 2 * scale))
                path.move(to: point(9, 8)); path.addLine(to: point(15, 8)); path.move(to: point(9, 12)); path.addLine(to: point(15, 12)); path.move(to: point(9, 16)); path.addLine(to: point(13, 16))
            case .logout:
                path.move(to: point(11, 4)); path.addLine(to: point(5, 4)); path.addLine(to: point(5, 20)); path.addLine(to: point(11, 20))
                path.move(to: point(10, 12)); path.addLine(to: point(21, 12)); path.move(to: point(17, 8)); path.addLine(to: point(21, 12)); path.addLine(to: point(17, 16))
            case .filter:
                path.move(to: point(4, 6)); path.addLine(to: point(20, 6)); path.move(to: point(7, 12)); path.addLine(to: point(17, 12)); path.move(to: point(10, 18)); path.addLine(to: point(14, 18))
                fillCircle(8, 5, 2); fillCircle(15, 11, 2); fillCircle(12, 17, 2)
            case .back:
                path.move(to: point(15, 4)); path.addLine(to: point(7, 12)); path.addLine(to: point(15, 20))
            case .history:
                path.addArc(center: point(12, 12), radius: 8 * scale, startAngle: .degrees(-65), endAngle: .degrees(255), clockwise: false)
                path.move(to: point(5.2, 4.8)); path.addLine(to: point(5.2, 9)); path.addLine(to: point(9.2, 9))
                path.move(to: point(12, 7)); path.addLine(to: point(12, 12)); path.addLine(to: point(8.5, 14))
            case .research:
                path.addRoundedRect(in: CGRect(x: point(4, 3).x, y: point(4, 3).y, width: 11 * scale, height: 15 * scale), cornerSize: CGSize(width: 2 * scale, height: 2 * scale))
                path.move(to: point(7, 7)); path.addLine(to: point(12, 7)); path.move(to: point(7, 11)); path.addLine(to: point(11, 11))
                path.addEllipse(in: CGRect(x: point(12, 12).x, y: point(12, 12).y, width: 7 * scale, height: 7 * scale))
                path.move(to: point(18, 18)); path.addLine(to: point(21, 21))
            }
            stroke(path)
        }
        .aspectRatio(1, contentMode: .fit)
        .accessibilityHidden(true)
    }
}
