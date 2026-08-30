import RatslotseDesign
import SwiftUI

enum GuidedTourTarget: Sendable {
    case questions
    case decisions
    case analysis
    case map
    case topics
}

private struct GuidedTourStep: Identifiable {
    let id: String
    let kicker: String
    let title: String
    let text: String
    let scene: Lotti3DScene
    let glyph: RatsGlyph
    let target: GuidedTourTarget?
}

struct GuidedTourView: View {
    let model: AppModel
    let open: (GuidedTourTarget) -> Void

    @Environment(\.dismiss) private var dismiss
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var index = 0

    private let steps: [GuidedTourStep] = [
        .init(id: "willkommen", kicker: "Lotti-Tour", title: "Moin, ich bin Lotti!", text: "Ich lotse dich einmal durch Ratslotse. Das dauert keine Minute – und du kannst jeden Bereich direkt ausprobieren.", scene: .wave, glyph: .home, target: nil),
        .init(id: "fragen", kicker: "Frag den Rat", title: "Frag, wie du sprechen würdest.", text: "Ich lese Beschlüsse, Vorlagen und Debatten. Die Quellen stehen direkt an der Antwort und führen zum amtlichen Original.", scene: .questions, glyph: .ask, target: .questions),
        .init(id: "antwort", kicker: "Beispielantwort", title: "Antworten, die sich prüfen lassen.", text: "Wichtige Zahlen werden als Grafiken gezeigt. Fußnoten öffnen die passende Quelle; Nachfragen bleiben im selben Gespräch.", scene: .explain, glyph: .ask, target: .questions),
        .init(id: "suche", kicker: "Beschlüsse", title: "Finde den Vorgang dahinter.", text: "Die Volltextsuche lässt sich nach Ergebnis, Themenfeld, Ausschuss, Partei, Ort und Zeitraum eingrenzen.", scene: .reading, glyph: .decisions, target: .decisions),
        .init(id: "analyse", kicker: "Ratsanalyse", title: "Den Rat besser verstehen.", text: "Entdecke thematische Rückblicke, Parteien, Personen, Finanzen und Ziele. Dahinter liegen immer die öffentlichen Unterlagen des Rats.", scene: .explain, glyph: .analysis, target: .analysis),
        .init(id: "karte", kicker: "Stadtkarte", title: "Sieh, wo etwas passiert.", text: "Orte erscheinen nur, wenn sie zur Auswahl passen. Ein Pin führt zu den zitierten Beschlüssen am jeweiligen Ort.", scene: .children, glyph: .map, target: .map),
        .init(id: "themen", kicker: "Deine Themen", title: "Lotti meldet sich für dich.", text: "Lege konkrete Suchbegriffe an und erhalte nur dann eine Nachricht, wenn neue Ratsunterlagen dazu passen.", scene: .questions, glyph: .topics, target: .topics),
        .init(id: "fertig", kicker: "Leinen los", title: "Du kennst jetzt die wichtigsten Wege.", text: "Die Tour findest du jederzeit unter „Mehr“. Jetzt kannst du direkt mit einer eigenen Frage starten.", scene: .celebrate, glyph: .home, target: .questions),
    ]

    var body: some View {
        ZStack {
            RatsColor.page.ignoresSafeArea()
            DecorativeTourBackground()

            VStack(spacing: 0) {
                header
                TabView(selection: $index) {
                    ForEach(Array(steps.enumerated()), id: \.element.id) { offset, step in
                        tourPage(step, number: offset)
                            .tag(offset)
                    }
                }
                .tabViewStyle(.page(indexDisplayMode: .never))
                .animation(reduceMotion ? nil : .snappy, value: index)
                footer
            }
        }
        .presentationDragIndicator(.hidden)
        .interactiveDismissDisabled(index > 0 && index < steps.count - 1)
    }

    private var header: some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 3) {
                MonoKicker("Geführte Tour")
                Text("Schritt \(index + 1) von \(steps.count)")
                    .font(RatsFont.body(12))
                    .foregroundStyle(RatsColor.secondary)
            }
            Spacer()
            Button("Schließen") { dismiss() }
                .font(RatsFont.body(13, weight: .semibold))
                .foregroundStyle(RatsColor.primary)
                .padding(.horizontal, 14)
                .frame(minHeight: 40)
                .background(RatsColor.card.opacity(0.88))
                .clipShape(Capsule())
        }
        .padding(.horizontal, 20)
        .padding(.top, 18)
        .padding(.bottom, 8)
    }

    private func tourPage(_ step: GuidedTourStep, number: Int) -> some View {
        ScrollView {
            VStack(spacing: 0) {
                Lotti3DView(scene: step.scene)
                    .frame(width: 270, height: 205)
                    .padding(.bottom, -20)
                    .accessibilityHidden(true)

                VStack(alignment: .leading, spacing: 16) {
                    Label {
                        MonoKicker(step.kicker)
                    } icon: {
                        RatsGlyphView(glyph: step.glyph, color: RatsColor.primary)
                            .frame(width: 22, height: 22)
                    }

                    Text(step.title)
                        .font(RatsFont.title(32, weight: .heavy))
                        .fixedSize(horizontal: false, vertical: true)
                    Text(step.text)
                        .font(RatsFont.body(17))
                        .foregroundStyle(RatsColor.bodyText)
                        .lineSpacing(5)

                    if step.id == "antwort" { answerDemo }

                    if let target = step.target, number != steps.count - 1 {
                        Button {
                            dismiss()
                            DispatchQueue.main.async { open(target) }
                        } label: {
                            Label("Diesen Bereich ausprobieren", systemImage: "arrow.up.right")
                                .frame(maxWidth: .infinity)
                        }
                        .buttonStyle(SecondaryButtonStyle())
                    }
                }
                .frame(maxWidth: 620, alignment: .leading)
                .ratsCard()
                .padding(.horizontal, 20)
                .padding(.bottom, 16)
            }
            .frame(maxWidth: .infinity)
        }
    }

    private var answerDemo: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Was wurde zum Radverkehr beschlossen?")
                .font(RatsFont.body(14, weight: .semibold))
                .padding(.horizontal, 13)
                .padding(.vertical, 10)
                .background(RatsColor.primary.opacity(0.10))
                .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
            Text("Der Rat hat mehrere sichere Querungen und Fahrradstraßen beraten. [1]")
                .font(RatsFont.body(15))
                .lineSpacing(4)
            Label("1  Amtliche Quelle · Beispiel", systemImage: "doc.text.magnifyingglass")
                .font(RatsFont.body(11, weight: .semibold))
                .foregroundStyle(RatsColor.primary)
                .padding(.horizontal, 11)
                .padding(.vertical, 8)
                .background(RatsColor.primary.opacity(0.07))
                .clipShape(Capsule())
        }
        .padding(14)
        .background(RatsColor.page)
        .overlay(RoundedRectangle(cornerRadius: 15, style: .continuous).stroke(RatsColor.border))
        .clipShape(RoundedRectangle(cornerRadius: 15, style: .continuous))
        .accessibilityElement(children: .combine)
        .accessibilityLabel("Beispielantwort mit amtlicher Quelle")
    }

    private var footer: some View {
        VStack(spacing: 12) {
            HStack(spacing: 6) {
                ForEach(steps.indices, id: \.self) { step in
                    Capsule()
                        .fill(step == index ? RatsColor.primary : RatsColor.border)
                        .frame(width: step == index ? 26 : 7, height: 7)
                }
            }
            HStack(spacing: 12) {
                if index > 0 {
                    Button("Zurück") { index -= 1 }
                        .buttonStyle(SecondaryButtonStyle())
                }
                Button(index == steps.count - 1 ? "Erste Frage stellen" : "Weiter") {
                    if index == steps.count - 1 {
                        Task { await model.reportBadgeEvent("tour") }
                        dismiss()
                        DispatchQueue.main.async { open(.questions) }
                    } else {
                        index += 1
                    }
                }
                .buttonStyle(PrimaryButtonStyle())
                .frame(maxWidth: .infinity)
            }
        }
        .padding(.horizontal, 20)
        .padding(.top, 12)
        .padding(.bottom, 18)
        .background(.ultraThinMaterial)
    }
}

private struct DecorativeTourBackground: View {
    var body: some View {
        GeometryReader { proxy in
            Circle()
                .fill(RatsColor.signal.opacity(0.14))
                .frame(width: 210, height: 210)
                .offset(x: proxy.size.width - 150, y: -65)
            WaveBand()
                .fill(RatsColor.primary.opacity(0.06))
                .frame(height: 180)
                .offset(y: proxy.size.height * 0.35)
        }
        .allowsHitTesting(false)
        .accessibilityHidden(true)
    }
}

private struct WaveBand: Shape {
    func path(in rect: CGRect) -> Path {
        var path = Path()
        path.move(to: CGPoint(x: 0, y: rect.height * 0.42))
        path.addCurve(
            to: CGPoint(x: rect.width, y: rect.height * 0.26),
            control1: CGPoint(x: rect.width * 0.28, y: rect.height * 0.02),
            control2: CGPoint(x: rect.width * 0.68, y: rect.height * 0.72)
        )
        path.addLine(to: CGPoint(x: rect.width, y: rect.height))
        path.addLine(to: CGPoint(x: 0, y: rect.height))
        path.closeSubpath()
        return path
    }
}
