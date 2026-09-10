import RatslotseDesign
import SwiftUI

// Die Schublade unter der Stadtkarte auf dem Telefon: ein Blatt, das in
// drei Stellungen rastet — `peek` (nur der Kopf, die Karte ist die Bühne),
// `half` (Kopf und der Anfang der Liste), `full` (die ganze Tafel, scrollbar).
//
// Warum kein `.sheet` mit `presentationDetents`: Die Karte liegt im Rats-Tab
// hinter Seiten, die ein Tipp öffnet (Ort, Thema, Beschluss-Suche). Ein
// ständiges System-Sheet läge über jeder davon, und ein Wechsel des
// Abschnitts müsste es erst abräumen. Das Blatt hier ist eine gewöhnliche
// View im ZStack — es kennt den Tab, die Navigation und den Sektions-Wechsel
// nicht und stört sie darum auch nicht.
//
// Bis 09/2026 stand die Tafel in einem ScrollView UNTER einer 46 % hohen
// Karte, beides zusammen in einer abgerundeten Karte mit 72 pt Luft zur
// Tab-Leiste. Auf einem iPhone blieb der Karte damit ein Fenster von rund
// 380 pt, und der Kopf der Tafel wurde von der Kartenkante abgeschnitten.

enum MapDrawerPosition: Equatable {
    case peek, half, full
}

/// Maße des schwebenden Blatts — außerhalb der generischen View, weil ein
/// generischer Typ keine statischen Werte tragen darf.
enum MapDrawerMetrics {
    static let sideInset: CGFloat = 12
    static let gap: CGFloat = 10
}

struct MapDrawer<Header: View, Content: View>: View {
    @Binding var position: MapDrawerPosition
    /// Die Höhe des Bereichs, in dem das Blatt fährt (die Karte darunter,
    /// bis zur Oberkante der Tab-Leiste).
    let available: CGFloat
    /// Wie hoch das Blatt in seiner Stellung ist — die Karte liest das, um
    /// ihre Kamera in den freien Teil zu legen.
    let onHeight: (CGFloat) -> Void
    @ViewBuilder let header: () -> Header
    @ViewBuilder let content: () -> Content

    @GestureState private var drag: CGFloat = 0
    @State private var headHeight: CGFloat = 96
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    /// Das Blatt schwebt: seitlich so breit wie die Tab-Leiste eingerückt,
    /// mit Luft nach unten zur Leiste und nach oben zum Kopf der Seite. Ein
    /// Blatt, das bündig an der Leiste endete, sah aus, als schnitte sie es
    /// ab (Tim, 10.09.2026).
    private var fullHeight: CGFloat { max(200, available - MapDrawerMetrics.gap * 2) }
    private var halfHeight: CGFloat { min(max(280, available * 0.46), 440) }
    private var peekHeight: CGFloat { headHeight }

    private func height(of position: MapDrawerPosition) -> CGFloat {
        switch position {
        case .peek: peekHeight
        case .half: halfHeight
        case .full: fullHeight
        }
    }

    /// Die sichtbare Höhe während des Ziehens — zwischen Kopf und Vollbild
    /// begrenzt, mit einem weichen Widerstand am Anschlag.
    private var liveHeight: CGFloat {
        let raw = height(of: position) - drag
        if raw > fullHeight { return fullHeight + (raw - fullHeight) * 0.15 }
        if raw < peekHeight { return peekHeight - (peekHeight - raw) * 0.15 }
        return raw
    }

    var body: some View {
        VStack(spacing: 0) {
            head
            ScrollView(showsIndicators: false) {
                content()
                    .padding(.horizontal, 18)
                    .padding(.top, 8)
                    .padding(.bottom, 24)
            }
            .scrollDisabled(position != .full)
            // In den unteren Stellungen zieht der ganze Körper das Blatt;
            // im Vollbild scrollt er, und der Kopf bleibt der Griff.
            .simultaneousGesture(dragGesture, including: position == .full ? .subviews : .all)
        }
        // Das Blatt ist so hoch wie sein sichtbarer Teil — kein Versatz nach
        // unten, der unter der Tab-Leiste durchschiene.
        .frame(height: liveHeight, alignment: .top)
        .background(RatsColor.page)
        .clipShape(RoundedRectangle(cornerRadius: 24, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .stroke(RatsColor.border, lineWidth: 1)
        }
        .shadow(color: RatsColor.primary.opacity(0.14), radius: 22, y: 8)
        .shadow(color: .black.opacity(0.06), radius: 3, y: 1)
        .padding(.horizontal, MapDrawerMetrics.sideInset)
        .padding(.bottom, MapDrawerMetrics.gap)
        .animation(reduceMotion ? nil : RatsMotion.travel, value: position)
        .animation(reduceMotion ? nil : RatsMotion.travel, value: drag == 0)
        .onChange(of: liveHeight, initial: true) { _, value in
            onHeight(min(fullHeight, max(peekHeight, value)))
        }
        .accessibilityAction(named: position == .full ? "Blatt einklappen" : "Blatt ausklappen") {
            step(position == .full ? .down : .up)
        }
    }

    private var head: some View {
        VStack(spacing: 0) {
            Capsule()
                .fill(RatsColor.border)
                .frame(width: 36, height: 5)
                .padding(.top, 8)
                .padding(.bottom, 6)
            header()
                .padding(.horizontal, 18)
                .padding(.bottom, 12)
        }
        .frame(maxWidth: .infinity)
        .contentShape(Rectangle())
        .background(
            GeometryReader { geo in
                Color.clear.preference(key: DrawerHeadHeightKey.self, value: geo.size.height)
            }
        )
        .onPreferenceChange(DrawerHeadHeightKey.self) { headHeight = $0 }
        .gesture(dragGesture)
        .onTapGesture { step(position == .peek ? .up : (position == .full ? .down : .up)) }
        .accessibilityAddTraits(.isButton)
        .accessibilityHint("Ziehen oder tippen, um die Tafel auszuklappen.")
    }

    private var dragGesture: some Gesture {
        DragGesture(minimumDistance: 6, coordinateSpace: .global)
            .updating($drag) { value, state, _ in state = value.translation.height }
            .onEnded { value in
                // Wohin es rastet: die Stellung, deren Höhe dem Ziel am
                // nächsten liegt — mit dem Schwung, nicht nur dem Weg.
                let projected = height(of: position) - value.predictedEndTranslation.height
                let candidates: [MapDrawerPosition] = [.peek, .half, .full]
                let next = candidates.min { abs(height(of: $0) - projected) < abs(height(of: $1) - projected) } ?? .half
                position = next
            }
    }

    private enum Direction { case up, down }

    private func step(_ direction: Direction) {
        switch (position, direction) {
        case (.peek, .up): position = .half
        case (.half, .up): position = .full
        case (.full, .down): position = .half
        case (.half, .down): position = .peek
        default: break
        }
    }
}

private struct DrawerHeadHeightKey: PreferenceKey {
    static let defaultValue: CGFloat = 96
    static func reduce(value: inout CGFloat, nextValue: () -> CGFloat) { value = nextValue() }
}

/// Der Auf-/Zuklapp-Knopf im Kopf der Schublade.
struct MapDrawerToggle: View {
    @Binding var position: MapDrawerPosition

    var body: some View {
        Button {
            position = position == .peek ? .half : (position == .half ? .full : .peek)
        } label: {
            RatsIcon(.chevronDown, size: 15)
                .foregroundStyle(RatsColor.secondary)
                .rotationEffect(.degrees(position == .full ? 0 : 180))
                .frame(width: 34, height: 34)
                .background(RatsColor.card)
                .overlay(Circle().stroke(RatsColor.border))
                .clipShape(Circle())
        }
        .buttonStyle(RatsPlainButtonStyle())
        .animation(RatsMotion.flow, value: position)
        .accessibilityLabel(position == .full ? "Tafel einklappen" : "Tafel ausklappen")
    }
}
