import RatslotseDesign
import SwiftUI

/// Der Parteichip: Punkt in Fraktionsfarbe, Kürzel daneben, Fläche in
/// derselben Farbe lasiert.
///
/// Eine Bauform für alle Stellen — Beschluss-Seite, Steckbrief und die
/// Sprecher-Zeilen der Ratsdebatten. Vorher stand er zweimal wortgleich in
/// `CouncilViews` und `ProfileAndQuizViews`; die dritte Kopie für die
/// Debatten wäre die Stelle gewesen, an der die drei auseinanderlaufen.
struct PartyChip: View {
    /// Die Fraktion, wie sie in den Daten steht — sie bestimmt die Farbe.
    let party: String
    /// Was auf dem Chip STEHT, falls nicht die Fraktion selbst: In den
    /// Debatten steht dort das Kürzel, weil „Bündnis 90/Die Grünen" den
    /// Chip über zwei Zeilen zöge.
    var label: String?
    /// Anhängsel hinter dem Label, etwa die Zahl der Anträge.
    var suffix: String?

    var body: some View {
        HStack(spacing: 6) {
            Circle().fill(color).frame(width: 8, height: 8)
            Text(suffix.map { "\(text) · \($0)" } ?? text)
                .font(RatsFont.body(10.5, weight: .semibold))
                .lineLimit(1)
        }
        .foregroundStyle(RatsColor.bodyText)
        .padding(.horizontal, 9)
        .padding(.vertical, 6)
        .background(color.opacity(0.11))
        .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
    }

    private var text: String { label ?? party }

    private var color: Color { partyChipColor(party) }
}

/// Die Fraktionsfarbe des Chips. Sie liest sowohl den ausgeschriebenen Namen
/// als auch das Kürzel („Bündnis 90/Die Grünen" wie „Grüne"), damit der Chip
/// die Farbe nicht verliert, wenn er verkürzt beschriftet wird.
func partyChipColor(_ party: String) -> Color {
    let value = party.lowercased()
    if value.contains("spd") { return Color(red: 0.82, green: 0.10, blue: 0.15) }
    if value.contains("cdu") { return RatsColor.bodyText }
    if value.contains("grün") { return Color(red: 0.18, green: 0.55, blue: 0.25) }
    if value.contains("fdp") { return Color(red: 0.93, green: 0.71, blue: 0.08) }
    if value.contains("link") { return Color(red: 0.72, green: 0.10, blue: 0.43) }
    if value.contains("volt") { return Color(red: 0.42, green: 0.17, blue: 0.62) }
    // BSW und AfD fehlten in beiden Kopien und liefen ins Hafenblau — in den
    // Ratsdebatten sitzen beide, der Chip hätte dort nichts unterschieden.
    if value.contains("bsw") { return Color(red: 0.49, green: 0.15, blue: 0.31) }
    if value.contains("afd") { return Color(red: 0.00, green: 0.52, blue: 0.74) }
    return RatsColor.primary
}
