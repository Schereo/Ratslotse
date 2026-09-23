import MapKit
import RatslotseAPI
import RatslotseDesign
import SwiftUI
import UIKit

// Die Ebene „Wahlergebnis" der Stadtkarte (docs/plan-viertel-wahlkarte.md) —
// dieselbe Bauform wie im Web (`components/wahl-bezirke-zeichner.ts`,
// `components/wahl-karte.tsx`):
//
// - Stadt: die 91 Urnenbezirke in der Farbe dessen, der vorn lag, die
//   Deckkraft nach dem Vorsprung. Ein Tipp öffnet den Ortsbereich.
// - Ortsbereich: die Bezirke, die ihn berühren, in VOLLER Form (nicht
//   zugeschnitten — ein beschnittener Bezirk sähe aus wie „so hat dieser
//   Stadtteil gewählt"). Ein Tipp wählt den Bezirk.
// - Tafel: Legende, Bezirksliste, Bezirk mit allen Listen.
//
// Parteifarbe als Fläche ist die zweite Ausnahme der Designsprache (§ 2);
// in der Tafel bleibt sie ein Punkt.

// MARK: - Geometrie

/// Ein Urnenbezirk: Nummer und der Außenring seiner größten Fläche.
struct ElectionDistrictShape: Identifiable, Sendable {
    let number: Int
    let ring: [CLLocationCoordinate2D]
    var id: Int { number }

    var center: CLLocationCoordinate2D {
        DistrictShape(name: "", ring: ring).centroid
    }

    func contains(_ point: CLLocationCoordinate2D) -> Bool {
        DistrictShape(name: "", ring: ring).contains(point)
    }
}

/// Die 91 Bezirke aus dem gebündelten GeoJSON (`Resources/wahlbezirke-oldenburg.json`,
/// dieselbe Datei wie `web/frontend/public/geo/`), einmal gelesen.
enum ElectionDistrictShapes {
    nonisolated(unsafe) private static var cache: [ElectionDistrictShape]?

    static func all() -> [ElectionDistrictShape] {
        if let cache { return cache }
        var shapes: [ElectionDistrictShape] = []
        if let url = Bundle.main.url(forResource: "wahlbezirke-oldenburg", withExtension: "json"),
           let data = try? Data(contentsOf: url),
           let objects = try? MKGeoJSONDecoder().decode(data) {
            for case let feature as MKGeoJSONFeature in objects {
                guard let properties = feature.properties,
                      let json = try? JSONSerialization.jsonObject(with: properties) as? [String: Any],
                      let number = json["nr"] as? Int else { continue }
                for geometry in feature.geometry {
                    if let polygon = geometry as? MKPolygon {
                        shapes.append(ElectionDistrictShape(number: number, ring: polygon.coordinates)); break
                    }
                    if let multi = geometry as? MKMultiPolygon,
                       let largest = multi.polygons.max(by: { $0.pointCount < $1.pointCount }) {
                        shapes.append(ElectionDistrictShape(number: number, ring: largest.coordinates)); break
                    }
                }
            }
        }
        cache = shapes
        return shapes
    }
}

// MARK: - Farben

extension ElectionMapContestant {
    /// Die Listenfarbe, im Dunkeln die helle Fassung — CDU-Schwarz wäre dort eine Wand.
    var mapColor: Color {
        let light = color, dark = colorDark
        return Color(uiColor: UIColor { traits in
            UIColor(electionHex: traits.userInterfaceStyle == .dark ? dark : light) ?? .systemGray
        })
    }
}

private extension UIColor {
    convenience init?(electionHex: String) {
        var text = electionHex.trimmingCharacters(in: .whitespaces)
        if text.hasPrefix("#") { text.removeFirst() }
        guard text.count == 6, let value = UInt32(text, radix: 16) else { return nil }
        self.init(red: CGFloat((value >> 16) & 0xFF) / 255, green: CGFloat((value >> 8) & 0xFF) / 255,
                  blue: CGFloat(value & 0xFF) / 255, alpha: 1)
    }
}

extension ElectionMap {
    func fill(for district: ElectionMapDistrict?) -> (Color, Double) {
        guard let district, district.counted, let leader = contestant(district.leader) else {
            return (RatsColor.secondary, 0.05)
        }
        return (leader.mapColor, ElectionMap.opacity(margin: district.marginPct))
    }
}

func electionPercent(_ value: Double?) -> String {
    guard let value else { return "–" }
    return value.formatted(.number.precision(.fractionLength(1)).locale(Locale(identifier: "de_DE"))) + " %"
}

private func electionPoints(_ value: Double?) -> String {
    guard let value else { return "–" }
    return value.formatted(.number.precision(.fractionLength(1)).locale(Locale(identifier: "de_DE"))) + " Pkt."
}

private func electionDate(_ iso: String) -> String {
    let parser = DateFormatter()
    parser.locale = Locale(identifier: "de_DE")
    parser.dateFormat = "yyyy-MM-dd"
    guard let date = parser.date(from: iso) else { return iso }
    parser.dateFormat = "d. MMMM yyyy"
    return parser.string(from: date)
}

// MARK: - Tafel

private struct PartyDot: View {
    let contestant: ElectionMapContestant?
    var size: CGFloat = 9
    var body: some View {
        Circle()
            .fill(contestant?.mapColor ?? RatsColor.secondary)
            .overlay(Circle().stroke(Color.black.opacity(0.12), lineWidth: 0.5))
            .frame(width: size, height: size)
            .accessibilityHidden(true)
    }
}

/// Die Wahl-Chips unter den Ebenen: Ratswahl · OB-Wahl · Stichwahl.
struct ElectionChoiceChips: View {
    let map: ElectionMap
    let choose: (String) -> Void

    var body: some View {
        if map.elections.count > 1 {
            HStack(spacing: 6) {
                ForEach(map.elections) { choice in
                    let on = choice.slug == map.election.slug
                    Button { choose(choice.slug) } label: {
                        Text(choice.label)
                            .font(RatsFont.body(11.5, weight: .semibold))
                            .foregroundStyle(on ? RatsColor.card : RatsColor.secondary)
                            .padding(.horizontal, 10)
                            .frame(height: 26)
                            .background(on ? RatsColor.text : RatsColor.card.opacity(0.9), in: Capsule())
                            .overlay(Capsule().stroke(RatsColor.border))
                    }
                    .buttonStyle(RatsPlainButtonStyle())
                    .accessibilityAddTraits(on ? .isSelected : [])
                    .accessibilityLabel("Wahl: \(choice.label)")
                }
            }
        }
    }
}

private struct PostalNote: View {
    let map: ElectionMap
    var body: some View {
        if let share = map.postalSharePct {
            Text("Farben nach den Wahllokalen. \(Int(share.rounded())) % der Stimmen kamen per Brief — sie haben keinen Ort auf der Karte und stehen je Wahlbereich im Bezirk.")
                .font(RatsFont.body(12))
                .foregroundStyle(RatsColor.secondary)
                .fixedSize(horizontal: false, vertical: true)
        }
    }
}

/// Stadt-Stufe: wer in wie vielen Bezirken vorn lag.
struct ElectionCityPanel: View {
    let map: ElectionMap

    var body: some View {
        VStack(alignment: .leading, spacing: 10) {
            MonoKicker("\(map.election.label) · \(electionDate(map.election.date))")
            Text(map.counted == 0 ? "Noch kein Wahllokal gezählt" : "Wer in den Wahllokalen vorn lag")
                .font(RatsFont.title(17))
                .foregroundStyle(RatsColor.text)
            Text(map.counted == map.total ? "alle \(map.total) Urnenbezirke" : "\(map.counted) von \(map.total) Urnenbezirken gezählt")
                .font(RatsFont.body(12))
                .foregroundStyle(RatsColor.secondary)
            ForEach(map.wins, id: \.slug) { win in
                let who = map.contestant(win.slug)
                HStack(spacing: 8) {
                    PartyDot(contestant: who)
                    Text(who?.short ?? win.slug).font(RatsFont.body(14, weight: .semibold)).foregroundStyle(RatsColor.text)
                    Spacer()
                    Text("vorn in \(win.districts)").font(RatsFont.mono(12)).monospacedDigit().foregroundStyle(RatsColor.text)
                }
                .accessibilityElement(children: .combine)
            }
            if map.ties > 0 {
                HStack(spacing: 8) {
                    Circle().stroke(RatsColor.secondary, style: StrokeStyle(lineWidth: 1, dash: [2, 2])).frame(width: 9, height: 9)
                    Text("Gleichstand").font(RatsFont.body(14)).foregroundStyle(RatsColor.secondary)
                    Spacer()
                    Text("\(map.ties)").font(RatsFont.mono(12)).foregroundStyle(RatsColor.secondary)
                }
            }
            HStack(spacing: 8) {
                Text("knapp").font(RatsFont.body(11)).foregroundStyle(RatsColor.secondary)
                HStack(spacing: 0) {
                    ForEach([0.0, 4, 8, 12, 16, 20], id: \.self) { m in
                        Rectangle().fill((map.contestant(map.wins.first?.slug)?.mapColor ?? RatsColor.primary).opacity(ElectionMap.opacity(margin: m)))
                    }
                }
                .frame(height: 9)
                .clipShape(Capsule())
                Text("20 Pkt. Vorsprung").font(RatsFont.body(11)).foregroundStyle(RatsColor.secondary)
            }
            .accessibilityHidden(true)
            PostalNote(map: map)
            Text("Tippe einen Stadtteil an, um seine Wahlbezirke zu sehen.")
                .font(RatsFont.body(12))
                .foregroundStyle(RatsColor.secondary)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .ratsCard()
    }
}

/// Ortsbereich-Stufe: die Bezirke, die ihn berühren.
struct ElectionDistrictListPanel: View {
    let map: ElectionMap
    let place: String
    let select: (Int) -> Void

    var body: some View {
        let districts = map.districts(in: place)
        VStack(alignment: .leading, spacing: 8) {
            MonoKicker("\(map.election.label) · \(electionDate(map.election.date))")
            Text(districts.count == 1 ? "Ein Wahlbezirk in \(place)" : "\(districts.count) Wahlbezirke in \(place)")
                .font(RatsFont.title(17))
                .foregroundStyle(RatsColor.text)
            Text("Die Stadt schneidet Wahlbezirke nicht nach Stadtteilen — manche liegen nur zum Teil hier.")
                .font(RatsFont.body(12))
                .foregroundStyle(RatsColor.secondary)
                .fixedSize(horizontal: false, vertical: true)
            ForEach(districts) { district in
                Button { select(district.number) } label: {
                    HStack(spacing: 10) {
                        Text("\(district.number)").font(RatsFont.mono(12, weight: .bold)).monospacedDigit().foregroundStyle(RatsColor.text)
                            .frame(width: 34, alignment: .leading)
                        VStack(alignment: .leading, spacing: 2) {
                            Text(district.name).font(RatsFont.body(14, weight: .semibold)).foregroundStyle(RatsColor.text).lineLimit(1)
                            HStack(spacing: 5) {
                                if district.leader != nil { PartyDot(contestant: map.contestant(district.leader), size: 7) }
                                Text(leadText(district)).font(RatsFont.body(12)).foregroundStyle(RatsColor.secondary)
                            }
                        }
                        Spacer(minLength: 4)
                        RatsIcon(.chevronRight, size: 12).foregroundStyle(RatsColor.muted)
                    }
                    .padding(.vertical, 6)
                    .contentShape(Rectangle())
                }
                .buttonStyle(RatsPlainButtonStyle())
                .accessibilityLabel("Wahlbezirk \(district.number), \(district.name), \(leadText(district))")
            }
            PostalNote(map: map)
        }
        .padding(14)
        .frame(maxWidth: .infinity, alignment: .leading)
        .ratsCard()
    }

    private func leadText(_ d: ElectionMapDistrict) -> String {
        var text: String
        if !d.counted { text = "noch nicht gezählt" }
        else if let leader = d.leader { text = "vorn: \(map.contestant(leader)?.short ?? leader) · \(electionPoints(d.marginPct))" }
        else { text = "Gleichstand" }
        let share = d.share(in: place)
        if share < 0.8 { text += " · \(Int((share * 100).rounded())) % hier" }
        return text
    }
}

/// Ein Bezirk mit allen Listen — und der Wahlbereich mit Briefwahl daneben.
struct ElectionDistrictDetail: View {
    let map: ElectionMap
    let district: ElectionMapDistrict
    let place: String?
    let back: () -> Void

    var body: some View {
        let area = map.areas.first { $0.number == district.area }
        let areaShare = Dictionary((area?.parties ?? []).map { ($0.slug, $0.sharePct) }, uniquingKeysWith: { a, _ in a })
        VStack(alignment: .leading, spacing: 10) {
            Button(action: back) {
                HStack(spacing: 4) {
                    RatsIcon(.chevronLeft, size: 12)
                    Text(place ?? "Oldenburg")
                }
                .font(RatsFont.body(13))
                .foregroundStyle(RatsColor.secondary)
            }
            .buttonStyle(RatsPlainButtonStyle())
            MonoKicker("\(map.election.label) · Wahlbezirk \(district.number)")
            Text(district.name).font(RatsFont.title(20)).foregroundStyle(RatsColor.text)
            Text(summary).font(RatsFont.body(13)).foregroundStyle(RatsColor.secondary).fixedSize(horizontal: false, vertical: true)
            if let place, district.share(in: place) < 0.8 {
                let others = district.places.filter { $0.name != place }.map(\.name).joined(separator: ", ")
                Text("Liegt nur zu \(Int((district.share(in: place) * 100).rounded())) % in \(place)\(others.isEmpty ? "" : ", sonst in \(others)").")
                    .font(RatsFont.body(12))
                    .foregroundStyle(RatsColor.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if district.counted {
                VStack(spacing: 0) {
                    HStack {
                        Text(map.election.kind == "council" ? "Liste" : "Kandidatur")
                        Spacer()
                        Text("Anteil").frame(width: 62, alignment: .trailing)
                        Text("Stimmen").frame(width: 60, alignment: .trailing)
                        Text("WB \(area?.roman ?? "")").frame(width: 56, alignment: .trailing)
                    }
                    .font(RatsFont.body(11))
                    .foregroundStyle(RatsColor.secondary)
                    .padding(.horizontal, 10).padding(.vertical, 7)
                    .background(RatsColor.stage)
                    ForEach(district.parties.filter { ($0.votes ?? 0) > 0 }, id: \.slug) { party in
                        let who = map.contestant(party.slug)
                        Divider().overlay(RatsColor.separator)
                        HStack(spacing: 6) {
                            PartyDot(contestant: who)
                            Text(who?.short ?? party.slug).font(RatsFont.body(13.5, weight: .semibold)).foregroundStyle(RatsColor.text).lineLimit(1)
                            Spacer(minLength: 4)
                            Text(electionPercent(party.sharePct)).frame(width: 62, alignment: .trailing).foregroundStyle(RatsColor.text)
                            Text(party.votes.map { "\($0)" } ?? "–").frame(width: 60, alignment: .trailing).foregroundStyle(RatsColor.secondary)
                            Text(electionPercent(areaShare[party.slug] ?? nil)).frame(width: 56, alignment: .trailing).foregroundStyle(RatsColor.secondary)
                        }
                        .font(RatsFont.mono(12))
                        .monospacedDigit()
                        .padding(.horizontal, 10).padding(.vertical, 6)
                        .accessibilityElement(children: .combine)
                    }
                }
                .background(RatsColor.card)
                .clipShape(RoundedRectangle(cornerRadius: 12))
                .overlay(RoundedRectangle(cornerRadius: 12).stroke(RatsColor.border))
            }
            if let area {
                Text("„WB \(area.roman)\" ist der ganze Wahlbereich \(area.roman) mit Briefwahl — die Briefstimmen lassen sich keinem Wahllokal zuordnen.")
                    .font(RatsFont.body(12))
                    .foregroundStyle(RatsColor.secondary)
                    .fixedSize(horizontal: false, vertical: true)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var summary: String {
        guard district.counted else { return "Noch nicht gezählt." }
        var text: String
        if let leader = map.contestant(district.leader) {
            let name = map.election.kind == "council" ? leader.short : leader.name
            text = "Vorn: \(name), \(electionPoints(district.marginPct)) vor \(map.contestant(district.runnerUp)?.short ?? "Platz 2")."
        } else {
            text = "Gleichstand an der Spitze."
        }
        if let turnout = district.turnoutPct { text += " Beteiligung \(electionPercent(turnout))." }
        return text
    }
}
