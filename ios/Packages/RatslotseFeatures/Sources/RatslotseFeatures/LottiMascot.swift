import SwiftUI

enum LottiPose: Sendable {
    case wave
    case point
    case search
}

/// Native vector version of the Lotti mascot used by the former WebView
/// onboarding. Drawing it in SwiftUI keeps the greeting sharp at every Dynamic
/// Type and iPad size without shipping another raster rendition.
struct LottiMascot: View {
    let pose: LottiPose
    var animated = true

    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var isFloating = false

    var body: some View {
        Canvas { context, size in
            let scale = min(size.width, size.height) / 200
            context.translateBy(
                x: (size.width - 200 * scale) / 2,
                y: (size.height - 200 * scale) / 2
            )
            context.scaleBy(x: scale, y: scale)
            drawLotti(in: &context)
        }
        .offset(y: isFloating ? -3 : 3)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Lotti, die Lotsenmöwe")
        .task {
            guard animated, !reduceMotion else { return }
            withAnimation(.easeInOut(duration: 1.6).repeatForever(autoreverses: true)) {
                isFloating = true
            }
        }
    }

    private func drawLotti(in context: inout GraphicsContext) {
        drawTail(in: &context)
        if pose == .wave { drawWaveWing(in: &context) }
        drawBody(in: &context)
        drawLeftWing(in: &context)
        switch pose {
        case .point: drawPointWing(in: &context)
        case .search: drawFoldedWing(in: &context)
        case .wave: break
        }
        drawFeet(in: &context)
        drawFace(in: &context)
        if pose == .search { drawSpyglass(in: &context) }
        drawCap(in: &context)
    }

    private func drawBody(in context: inout GraphicsContext) {
        var body = Path()
        body.move(to: point(100, 58))
        body.addCurve(to: point(154, 124), control1: point(134, 58), control2: point(154, 88))
        body.addCurve(to: point(100, 180), control1: point(154, 158), control2: point(131, 180))
        body.addCurve(to: point(46, 124), control1: point(69, 180), control2: point(46, 158))
        body.addCurve(to: point(100, 58), control1: point(46, 88), control2: point(66, 58))
        context.fill(body, with: .color(.white))

        var shade = Path()
        shade.move(to: point(67, 158))
        shade.addCurve(to: point(100, 173), control1: point(76, 168), control2: point(88, 173))
        shade.addCurve(to: point(133, 158), control1: point(112, 173), control2: point(124, 168))
        shade.addCurve(to: point(100, 180), control1: point(126, 171), control2: point(114, 180))
        shade.addCurve(to: point(67, 158), control1: point(86, 180), control2: point(74, 171))
        context.fill(shade, with: .color(color(0xE4EEF6).opacity(0.8)))
    }

    private func drawTail(in context: inout GraphicsContext) {
        var tail = Path()
        tail.move(to: point(52, 140))
        tail.addCurve(to: point(33, 166), control1: point(40, 146), control2: point(34, 156))
        tail.addCurve(to: point(60, 150), control1: point(44, 164), control2: point(54, 158))
        tail.closeSubpath()
        context.fill(tail, with: .color(color(0xC7D6E4)))
    }

    private func drawLeftWing(in context: inout GraphicsContext) {
        var wing = Path()
        wing.move(to: point(56, 102))
        wing.addCurve(to: point(40, 148), control1: point(42, 112), control2: point(36, 130))
        wing.addCurve(to: point(74, 144), control1: point(52, 156), control2: point(66, 154))
        wing.addCurve(to: point(56, 102), control1: point(66, 132), control2: point(60, 118))
        context.fill(wing, with: .color(color(0xC7D6E4)))

        var tip = Path()
        tip.move(to: point(42, 138))
        tip.addCurve(to: point(40, 148), control1: point(42, 142), control2: point(41, 145))
        tip.addCurve(to: point(60, 151), control1: point(46, 152), control2: point(53, 153))
        tip.addCurve(to: point(42, 138), control1: point(54, 148), control2: point(47, 144))
        context.fill(tip, with: .color(color(0x8CA6BC)))
    }

    private func drawFoldedWing(in context: inout GraphicsContext) {
        var wing = Path()
        wing.move(to: point(144, 102))
        wing.addCurve(to: point(160, 148), control1: point(158, 112), control2: point(164, 130))
        wing.addCurve(to: point(126, 144), control1: point(148, 156), control2: point(134, 154))
        wing.addCurve(to: point(144, 102), control1: point(134, 132), control2: point(140, 118))
        context.fill(wing, with: .color(color(0xC7D6E4)))
    }

    private func drawWaveWing(in context: inout GraphicsContext) {
        var wing = Path()
        wing.move(to: point(144, 108))
        wing.addCurve(to: point(166, 56), control1: point(158, 92), control2: point(166, 74))
        wing.addCurve(to: point(136, 82), control1: point(154, 58), control2: point(142, 68))
        wing.addCurve(to: point(144, 108), control1: point(138, 92), control2: point(141, 101))
        context.fill(wing, with: .color(color(0xC7D6E4)))

        var tip = Path()
        tip.move(to: point(162, 64))
        tip.addCurve(to: point(166, 56), control1: point(164, 61), control2: point(165, 58))
        tip.addCurve(to: point(149, 64), control1: point(160, 57), control2: point(154, 60))
        tip.addCurve(to: point(162, 64), control1: point(153, 65), control2: point(158, 65))
        context.fill(tip, with: .color(color(0x8CA6BC)))
    }

    private func drawPointWing(in context: inout GraphicsContext) {
        var wing = Path()
        wing.move(to: point(140, 110))
        wing.addCurve(to: point(184, 104), control1: point(158, 104), control2: point(172, 102))
        wing.addCurve(to: point(158, 122), control1: point(180, 112), control2: point(170, 120))
        wing.addCurve(to: point(140, 110), control1: point(151, 119), control2: point(145, 115))
        context.fill(wing, with: .color(color(0xC7D6E4)))
    }

    private func drawFeet(in context: inout GraphicsContext) {
        var left = Path()
        left.move(to: point(78, 176))
        left.addCurve(to: point(62, 187), control1: point(70, 184), control2: point(66, 186))
        left.addCurve(to: point(84, 185), control1: point(68, 190), control2: point(78, 190))
        left.closeSubpath()
        context.fill(left, with: .color(color(0xD9531E)))

        var right = Path()
        right.move(to: point(122, 176))
        right.addCurve(to: point(138, 187), control1: point(130, 184), control2: point(134, 186))
        right.addCurve(to: point(116, 185), control1: point(132, 190), control2: point(122, 190))
        right.closeSubpath()
        context.fill(right, with: .color(color(0xD9531E)))
    }

    private func drawFace(in context: inout GraphicsContext) {
        drawEye(center: point(82, 96), in: &context)
        drawEye(center: point(118, 96), in: &context)

        context.fill(
            Path(ellipseIn: CGRect(x: 59, y: 105.4, width: 14, height: 9.2)),
            with: .color(color(0xFFAD85).opacity(0.55))
        )
        context.fill(
            Path(ellipseIn: CGRect(x: 127, y: 105.4, width: 14, height: 9.2)),
            with: .color(color(0xFFAD85).opacity(0.55))
        )

        var beak = Path()
        beak.move(to: point(100, 105))
        beak.addCurve(to: point(111, 111), control1: point(107, 105), control2: point(111, 108))
        beak.addCurve(to: point(100, 116), control1: point(111, 114), control2: point(106, 116))
        beak.addCurve(to: point(89, 111), control1: point(94, 116), control2: point(89, 114))
        beak.addCurve(to: point(100, 105), control1: point(89, 108), control2: point(93, 105))
        context.fill(beak, with: .color(color(0xF66623)))
    }

    private func drawEye(center: CGPoint, in context: inout GraphicsContext) {
        context.fill(
            Path(ellipseIn: CGRect(x: center.x - 8, y: center.y - 8, width: 16, height: 16)),
            with: .color(color(0x122A40))
        )
        context.fill(
            Path(ellipseIn: CGRect(x: center.x - 5.8, y: center.y - 6, width: 6, height: 6)),
            with: .color(.white)
        )
    }

    private func drawSpyglass(in context: inout GraphicsContext) {
        var tube = Path(roundedRect: CGRect(x: 112, y: 89, width: 46, height: 14), cornerRadius: 5)
        context.fill(tube, with: .color(color(0x143A5C)))
        tube = Path(roundedRect: CGRect(x: 148, y: 87, width: 9, height: 18), cornerRadius: 3)
        context.fill(tube, with: .color(color(0x0E2B46)))
        context.fill(Path(ellipseIn: CGRect(x: 109.5, y: 87.5, width: 17, height: 17)), with: .color(color(0x0E2B46)))
        context.fill(Path(ellipseIn: CGRect(x: 112.5, y: 90.5, width: 11, height: 11)), with: .color(color(0xBFE3F7)))
    }

    private func drawCap(in context: inout GraphicsContext) {
        var crown = Path()
        crown.move(to: point(60, 58))
        crown.addCurve(to: point(100, 22), control1: point(60, 34), control2: point(77, 22))
        crown.addCurve(to: point(140, 58), control1: point(123, 22), control2: point(140, 34))
        crown.addCurve(to: point(100, 50), control1: point(128, 52.5), control2: point(114, 50))
        crown.addCurve(to: point(60, 58), control1: point(86, 50), control2: point(72, 52.5))
        context.fill(crown, with: .color(color(0x143A5C)))

        var band = Path()
        band.move(to: point(59, 55))
        band.addCurve(to: point(100, 47), control1: point(71.5, 49.5), control2: point(85, 47))
        band.addCurve(to: point(141, 55), control1: point(115, 47), control2: point(128.5, 49.5))
        band.addCurve(to: point(141, 66), control1: point(142.5, 59), control2: point(142.5, 62.5))
        band.addCurve(to: point(100, 58), control1: point(128.5, 60.5), control2: point(115, 58))
        band.addCurve(to: point(59, 66), control1: point(85, 58), control2: point(71.5, 60.5))
        band.addCurve(to: point(59, 55), control1: point(57.5, 62.5), control2: point(57.5, 59))
        context.fill(band, with: .color(color(0x0E2B46)))

        context.fill(Path(ellipseIn: CGRect(x: 94, y: 32, width: 12, height: 12)), with: .color(color(0xF2B441)))
        var star = Path()
        star.move(to: point(100, 33))
        star.addLine(to: point(101.8, 36.2))
        star.addLine(to: point(105, 38))
        star.addLine(to: point(101.8, 39.8))
        star.addLine(to: point(100, 43))
        star.addLine(to: point(98.2, 39.8))
        star.addLine(to: point(95, 38))
        star.addLine(to: point(98.2, 36.2))
        star.closeSubpath()
        context.fill(star, with: .color(color(0x0E2B46)))
    }

    private func point(_ x: CGFloat, _ y: CGFloat) -> CGPoint { CGPoint(x: x, y: y) }

    private func color(_ hex: UInt32) -> Color {
        Color(
            red: Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8) & 0xFF) / 255,
            blue: Double(hex & 0xFF) / 255
        )
    }
}
