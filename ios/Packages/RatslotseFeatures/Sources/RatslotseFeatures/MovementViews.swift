import RatslotseAPI
import RatslotseDesign
import SwiftUI

// MARK: - Zeitleiste
//
// Dieselbe Rechnung wie `web/frontend/lib/zeitleiste.ts`: Die ACHSE kommt vom
// Server (`axis`), hier wird nur ausgerechnet, wo ein Datum darauf liegt.
// Wer eine der beiden ändert, ändert die andere mit — sonst stünde „2024"
// in der App an einer anderen Stelle als im Web.

enum ZeitleisteStufe: CaseIterable {
    case ok, no, wait, noted, open

    init(outcome: String) {
        switch outcome {
        case "accepted", "amended": self = .ok
        case "rejected": self = .no
        case "postponed", "referred": self = .wait
        case "noted": self = .noted
        default: self = .open
        }
    }

    var text: String {
        switch self {
        case .ok: "beschlossen"
        case .no: "abgelehnt"
        case .wait: "vertagt oder verwiesen"
        case .noted: "zur Kenntnis"
        case .open: "ohne Ergebnis"
        }
    }

    var farbe: Color {
        switch self {
        case .ok: RatsColor.success
        case .no: RatsColor.danger
        case .wait: Color(red: 0.85, green: 0.47, blue: 0.02)
        case .noted: RatsColor.muted
        case .open: .clear
        }
    }
}

enum ZeitleisteRechnung {
    private static func tage(_ iso: String) -> Double? {
        let teile = iso.prefix(10).split(separator: "-").compactMap { Int($0) }
        guard let jahr = teile.first else { return nil }
        var k = DateComponents()
        k.year = jahr
        k.month = teile.count > 1 ? teile[1] : 1
        k.day = teile.count > 2 ? teile[2] : 1
        var kalender = Calendar(identifier: .gregorian)
        kalender.timeZone = TimeZone(identifier: "UTC") ?? .current
        guard let datum = kalender.date(from: k) else { return nil }
        return datum.timeIntervalSince1970 / 86_400
    }

    /// Wo ein Datum auf der Achse liegt, 0…1 — geklemmt, nicht verworfen.
    static func anteil(_ datum: String?, _ achse: TimeAxis) -> Double? {
        guard let datum, let start = achse.start, let end = achse.end,
              let a = tage(start), let b = tage(end), let t = tage(datum) else { return nil }
        guard b > a else { return 0.5 }
        return min(1, max(0, (t - a) / (b - a)))
    }

    static func jahresmarken(_ achse: TimeAxis) -> [(jahr: Int, anteil: Double)] {
        guard let s = achse.start, let e = achse.end,
              let von = Int(s.prefix(4)), let bis = Int(e.prefix(4)), von <= bis else { return [] }
        return (von...bis).compactMap { jahr in
            anteil("\(jahr)-01-01", achse).map { (jahr, $0) }
        }
    }

    /// Nahe Punkte in Spuren legen statt sie in der Zeit zu verschieben —
    /// dieselbe Regel wie `spuren` in `lib/zeitleiste.ts`: Spur 0 ist die
    /// Linie, dann +1, −1; ist keine frei, überlappt der Punkt in Spur 0.
    static func spuren(_ anteile: [Double], abstand: Double = 0.032) -> [Int] {
        var letzte: [Int: Double] = [:]
        return anteile.map { a in
            let frei = [0, 1, -1].first { a - (letzte[$0] ?? -.infinity) >= abstand } ?? 0
            letzte[frei] = a
            return frei
        }
    }

    /// Die Leiste als Satz — für VoiceOver, das keine Punkte sieht.
    static func satz(_ punkte: [TimelinePoint]) -> String {
        guard !punkte.isEmpty else { return "Keine Vorlagen." }
        let staedte = Set(punkte.map(\.city)).count
        let jahre = punkte.compactMap { $0.date.map { String($0.prefix(4)) } }
        var zeitraum = ""
        if let von = jahre.min(), let bis = jahre.max() {
            zeitraum = von == bis ? " \(von)" : " \(von) bis \(bis)"
        }
        let zaehler = Dictionary(grouping: punkte, by: { ZeitleisteStufe(outcome: $0.outcome) })
        let worte = ["", "einmal", "zweimal", "dreimal", "viermal", "fünfmal"]
        let teile = ZeitleisteStufe.allCases.compactMap { s -> String? in
            guard let n = zaehler[s]?.count, n > 0 else { return nil }
            return "\(n < worte.count ? worte[n] : "\(n)-mal") \(s.text)"
        }
        return "\(staedte == 1 ? "1 Stadt" : "\(staedte) Städte"),\(zeitraum): \(teile.joined(separator: ", "))."
    }
}

struct Zeitleiste: View {
    let achse: TimeAxis
    let punkte: [TimelinePoint]
    var label: String?
    var hoehe: CGFloat = 34

    var body: some View {
        GeometryReader { geo in
            let breite = geo.size.width
            ZStack(alignment: .leading) {
                Rectangle().fill(RatsColor.border).frame(height: 1)
                    .frame(maxHeight: .infinity)
                ForEach(ZeitleisteRechnung.jahresmarken(achse), id: \.jahr) { marke in
                    Path { p in
                        p.move(to: CGPoint(x: marke.anteil * breite, y: 3))
                        p.addLine(to: CGPoint(x: marke.anteil * breite, y: hoehe - 3))
                    }
                    .stroke(RatsColor.border, style: StrokeStyle(lineWidth: 1, dash: [3, 3]))
                }
                let datiert = punkte.compactMap { p in
                    ZeitleisteRechnung.anteil(p.date, achse).map { (punkt: p, anteil: $0) }
                }.sorted { $0.anteil < $1.anteil }
                let spur = ZeitleisteRechnung.spuren(datiert.map(\.anteil))
                ForEach(Array(datiert.enumerated()), id: \.element.punkt.id) { i, eintrag in
                    let stufe = ZeitleisteStufe(outcome: eintrag.punkt.outcome)
                    Circle()
                        .fill(stufe == .open ? RatsColor.card : stufe.farbe)
                        .overlay(Circle().stroke(stufe == .open ? RatsColor.muted : RatsColor.card,
                                                 lineWidth: stufe == .open ? 1.5 : 2))
                        .frame(width: 11, height: 11)
                        .position(x: min(max(eintrag.anteil * breite, 6), breite - 6),
                                  y: hoehe / 2 + CGFloat(spur[i]) * 8)
                }
            }
        }
        .frame(height: hoehe)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(label ?? ZeitleisteRechnung.satz(punkte))
    }
}

struct Jahresskala: View {
    let achse: TimeAxis

    var body: some View {
        GeometryReader { geo in
            // Das letzte Jahr ist das ENDE der Achse — als Zahl stünde es für
            // ein Jahr, in dem nichts liegt.
            ForEach(Array(ZeitleisteRechnung.jahresmarken(achse).dropLast()), id: \.jahr) { marke in
                Text(String(marke.jahr))
                    .font(RatsFont.mono(10.5, weight: .regular))
                    .foregroundStyle(RatsColor.muted)
                    .fixedSize()
                    .offset(x: marke.anteil * geo.size.width)
            }
        }
        .frame(height: 14)
        .accessibilityHidden(true)
    }
}

struct ZeitleisteLegende: View {
    var body: some View {
        FlowRow(spacing: 12) {
            ForEach(ZeitleisteStufe.allCases, id: \.self) { s in
                HStack(spacing: 5) {
                    Circle()
                        .fill(s == .open ? RatsColor.card : s.farbe)
                        .overlay(Circle().stroke(s == .open ? RatsColor.muted : .clear, lineWidth: 1.5))
                        .frame(width: 9, height: 9)
                    Text(s.text).font(RatsFont.body(12)).foregroundStyle(RatsColor.muted)
                }
            }
        }
        .accessibilityElement(children: .combine)
    }
}

/// Ein einfacher Zeilenumbruch für Legende und Chips — ohne Layout-Protokoll
/// wäre die Legende auf dem iPhone SE abgeschnitten.
struct FlowRow: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let breite = proposal.width ?? .infinity
        var x: CGFloat = 0, y: CGFloat = 0, zeile: CGFloat = 0, weiteste: CGFloat = 0
        for v in subviews {
            let g = v.sizeThatFits(.unspecified)
            if x > 0, x + g.width > breite { y += zeile + 6; x = 0; zeile = 0 }
            x += g.width + spacing
            zeile = max(zeile, g.height)
            weiteste = max(weiteste, x - spacing)
        }
        return CGSize(width: min(weiteste, breite), height: y + zeile)
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        var x = bounds.minX, y = bounds.minY, zeile: CGFloat = 0
        for v in subviews {
            let g = v.sizeThatFits(.unspecified)
            if x > bounds.minX, x + g.width > bounds.maxX { y += zeile + 6; x = bounds.minX; zeile = 0 }
            v.place(at: CGPoint(x: x, y: y), proposal: ProposedViewSize(g))
            x += g.width + spacing
            zeile = max(zeile, g.height)
        }
    }
}

// MARK: - Pillen

/// Der Stand in Oldenburg — dieselben vier Stufen und Worte wie im Web
/// (`components/ideen/stand.tsx`).
struct StandPille: View {
    let status: String

    static let text: [String: String] = [
        "missing": "In Oldenburg nicht gefunden",
        "partial": "Teilweise vorhanden",
        "present": "Oldenburg hat das",
        "not_applicable": "Für Oldenburg nicht anwendbar",
    ]

    var body: some View {
        if let text = Self.text[status] {
            Text(text)
                .font(RatsFont.body(12, weight: .semibold))
                .foregroundStyle(vorder)
                .padding(.horizontal, 10).padding(.vertical, 3)
                .background(hinter)
                .clipShape(Capsule())
        }
    }

    private var vorder: Color {
        switch status {
        case "missing": RatsColor.primary
        case "partial": RatsColor.warning
        default: RatsColor.muted
        }
    }

    private var hinter: Color {
        switch status {
        case "missing": RatsColor.primary.opacity(0.10)
        case "partial": RatsColor.warningTint
        default: RatsColor.separator
        }
    }
}

/// Wie eine Vorlage ausging — die acht Ergebnisse der Städte.
struct ErgebnisPille: View {
    let outcome: String

    static let text: [String: String] = [
        "accepted": "Beschlossen", "amended": "Geändert beschlossen", "rejected": "Abgelehnt",
        "postponed": "Vertagt", "referred": "Verwiesen", "noted": "Zur Kenntnis",
        "withdrawn": "Zurückgezogen", "none": "Ohne Ergebnis",
    ]

    var body: some View {
        let stufe = ZeitleisteStufe(outcome: outcome)
        Text(Self.text[outcome] ?? "Ohne Ergebnis")
            .font(RatsFont.body(11.5, weight: .semibold))
            .foregroundStyle(stufe == .ok ? RatsColor.success : stufe == .no ? RatsColor.danger
                             : stufe == .wait ? RatsColor.warning : RatsColor.muted)
            .padding(.horizontal, 9).padding(.vertical, 3)
            .background(stufe == .ok ? RatsColor.successTint : stufe == .no ? RatsColor.dangerTint
                        : stufe == .wait ? RatsColor.warningTint : .clear)
            .overlay(Capsule().stroke(stufe == .open ? RatsColor.border : .clear,
                                      style: StrokeStyle(lineWidth: 1, dash: [3, 2])))
            .clipShape(Capsule())
    }
}

// MARK: - Karte

enum BewegungText {
    static func staedte(_ b: Movement, hoechstens: Int = 3) -> String {
        let namen = b.cities.map(\.city)
        if namen.count <= hoechstens {
            return namen.count == 1 ? namen[0]
                : namen.dropLast().joined(separator: ", ") + " und " + (namen.last ?? "")
        }
        return namen.prefix(hoechstens).joined(separator: ", ") + " und \(namen.count - hoechstens) weitere"
    }

    static func zeitraum(_ b: Movement) -> String? {
        guard let von = b.firstDate?.prefix(4), let bis = b.lastDate?.prefix(4) else { return nil }
        return von == bis ? String(von) : "\(von)–\(bis)"
    }

    static func bilanz(_ b: Movement) -> String {
        let ok = b.timeline.filter { ZeitleisteStufe(outcome: $0.outcome) == .ok }.count
        let nein = b.timeline.filter { ZeitleisteStufe(outcome: $0.outcome) == .no }.count
        var teile = ["\(b.members) \(b.members == 1 ? "Vorlage" : "Vorlagen")"]
        if ok > 0 { teile.append("\(ok) beschlossen") }
        if nein > 0 { teile.append("\(nein) abgelehnt") }
        return teile.joined(separator: " · ")
    }
}

struct MovementCard: View {
    let model: AppModel
    let bewegung: Movement
    let achse: TimeAxis

    var body: some View {
        Button {
            model.navigation.append(.movement(id: bewegung.clusterID))
        } label: {
            VStack(alignment: .leading, spacing: 9) {
                let kicker = [bewegung.field.map(IdeasView.feldLabel), BewegungText.zeitraum(bewegung)]
                    .compactMap { $0 }.joined(separator: " · ")
                if !kicker.isEmpty {
                    Text(kicker.uppercased())
                        .font(RatsFont.mono(11))
                        .tracking(0.7)
                        .foregroundStyle(RatsColor.muted)
                }
                Text(bewegung.label)
                    .font(RatsFont.title(17))
                    .foregroundStyle(RatsColor.text)
                    .multilineTextAlignment(.leading)
                    .fixedSize(horizontal: false, vertical: true)
                (Text("\(bewegung.cities.count) Städte: ").bold() + Text(BewegungText.staedte(bewegung)))
                    .font(RatsFont.body(14))
                    .foregroundStyle(RatsColor.bodyText)
                    .fixedSize(horizontal: false, vertical: true)
                VStack(alignment: .leading, spacing: 1) {
                    Zeitleiste(achse: achse, punkte: bewegung.timeline)
                    Jahresskala(achse: achse)
                }
                Text(BewegungText.bilanz(bewegung))
                    .font(RatsFont.metadata())
                    .foregroundStyle(RatsColor.muted)
                oldenburg
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .ratsCard()
        }
        .buttonStyle(RatsPlainButtonStyle())
    }

    private var oldenburg: some View {
        HStack(alignment: .top, spacing: 8) {
            RoundedRectangle(cornerRadius: 2).fill(RatsColor.signal)
                .frame(width: 8, height: 8).padding(.top, 5)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 4) {
                if let u = bewegung.oldenburg {
                    StandPille(status: u.status)
                    if !u.situation.isEmpty {
                        Text(u.situation)
                            .font(RatsFont.body(14))
                            .foregroundStyle(RatsColor.bodyText)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                } else {
                    Text("Ob Oldenburg das schon hat, ist noch nicht geprüft.")
                        .font(RatsFont.body(14))
                        .foregroundStyle(RatsColor.muted)
                }
            }
        }
        .padding(.top, 8)
        .overlay(alignment: .top) { Rectangle().fill(RatsColor.separator).frame(height: 1) }
    }
}

// MARK: - Liste (Teil der Ideen-Übersicht)

/// Die Bewegungen oberhalb der Einzelideen: Tafel „Gerade in Bewegung",
/// Feld-Chips, der Stand in Oldenburg als Filter, die Karten.
///
/// Gefiltert, gezählt und geblättert wird auf dem Server — dieselben
/// Parameter wie im Web.
struct MovementsSection: View {
    let model: AppModel
    let felder: [IdeaFieldSummary]
    @State private var feld: String?
    @State private var stand = "offen"
    @State private var antwort: MovementsResponse?
    @State private var tafel: MovementsResponse?
    @State private var seite = 1
    @State private var fehler: String?

    private static let staende: [(wert: String, text: String, parameter: String)] = [
        ("offen", "Noch offen", "missing,partial"),
        ("vorhanden", "Hat Oldenburg", "present"),
        ("alle", "Alle", ""),
    ]

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            if feld == nil, stand == "offen", let tafel, !tafel.items.isEmpty {
                RatsWidget("Gerade in Bewegung", accent: .harbor, note: "ab 5 Städten", board: true) {
                    EmptyView()
                } content: {
                    VStack(alignment: .leading, spacing: 10) {
                        ForEach(tafel.items) { b in
                            MovementCard(model: model, bewegung: b, achse: tafel.axis)
                        }
                        ZeitleisteLegende()
                    }
                }
            }
            Text("Ideen, die mehrere Räte hatten")
                .font(RatsFont.title(19))
                .foregroundStyle(RatsColor.text)
                .accessibilityAddTraits(.isHeader)
            chips
            Picker("Stand in Oldenburg", selection: $stand) {
                ForEach(Self.staende, id: \.wert) { s in Text(s.text).tag(s.wert) }
            }
            .pickerStyle(.segmented)
            if let fehler {
                Text(fehler).font(RatsFont.body(13)).foregroundStyle(RatsColor.danger)
            } else if let antwort {
                Text("\(antwort.total) \(antwort.total == 1 ? "Idee" : "Ideen") · ab 2 Städten")
                    .font(RatsFont.metadata())
                    .foregroundStyle(RatsColor.muted)
                ForEach(antwort.items) { b in
                    MovementCard(model: model, bewegung: b, achse: antwort.axis)
                }
                if antwort.items.isEmpty {
                    Text("Unter diesen Filtern gibt es keine Idee, die mehrere Räte hatten.")
                        .font(RatsFont.body(14))
                        .foregroundStyle(RatsColor.muted)
                        .fixedSize(horizontal: false, vertical: true)
                }
                if antwort.items.count < antwort.total {
                    Button("Weitere laden") { Task { await lade(anhaengen: true) } }
                        .font(RatsFont.body(14, weight: .semibold))
                        .foregroundStyle(RatsColor.primary)
                        .frame(maxWidth: .infinity)
                }
            } else {
                ProgressView().frame(maxWidth: .infinity).padding(.top, 12)
            }
        }
        .task { await ladeTafel() }
        .task(id: "\(feld ?? "")|\(stand)") { await lade(anhaengen: false) }
    }

    private var chips: some View {
        ScrollView(.horizontal, showsIndicators: false) {
            HStack(spacing: 6) {
                chip("Alle Felder", zahl: felder.reduce(0) { $0 + $1.movements }, an: feld == nil) { feld = nil }
                ForEach(felder.filter { $0.movements > 0 }.sorted { $0.movements > $1.movements }) { f in
                    chip(IdeasView.feldLabel(f.field), zahl: f.movements, an: feld == f.field) { feld = f.field }
                }
            }
        }
    }

    private func chip(_ text: String, zahl: Int, an: Bool, _ aktion: @escaping () -> Void) -> some View {
        Button(action: aktion) {
            HStack(spacing: 5) {
                Text(text).font(RatsFont.body(14))
                Text("\(zahl)").font(RatsFont.mono(11.5)).opacity(0.85)
            }
            .foregroundStyle(an ? RatsColor.primaryText : RatsColor.text)
            .padding(.horizontal, 12).padding(.vertical, 7)
            .background(an ? RatsColor.primary : RatsColor.card)
            .overlay(Capsule().stroke(an ? RatsColor.primary : RatsColor.border))
            .clipShape(Capsule())
        }
        .buttonStyle(RatsPlainButtonStyle())
        .accessibilityAddTraits(an ? .isSelected : [])
    }

    private func ladeTafel() async {
        do {
            let r: MovementsResponse = try await model.api.get(
                "/api/council/cities/movements",
                query: [URLQueryItem(name: "min_cities", value: "5"),
                        URLQueryItem(name: "oldenburg", value: "missing,partial"),
                        // Die zuletzt bewegten — nach Städten sortiert stünden
                        // hier dieselben drei wie oben in der Liste.
                        URLQueryItem(name: "sort", value: "zuletzt"),
                        URLQueryItem(name: "per_page", value: "3")])
            tafel = r
        } catch {
            tafel = nil
        }
    }

    private func lade(anhaengen: Bool) async {
        let neueSeite = anhaengen ? seite + 1 : 1
        var query = [URLQueryItem(name: "oldenburg",
                                  value: Self.staende.first { $0.wert == stand }?.parameter ?? ""),
                     URLQueryItem(name: "page", value: String(neueSeite)),
                     URLQueryItem(name: "per_page", value: "12")]
        if let feld { query.append(URLQueryItem(name: "field", value: feld)) }
        do {
            let r: MovementsResponse = try await model.api.get("/api/council/cities/movements", query: query)
            if anhaengen, let alt = antwort {
                antwort = r.mitVorher(alt.items)
            } else {
                antwort = r
            }
            seite = neueSeite
            fehler = nil
        } catch {
            fehler = error.localizedDescription
        }
    }
}

private extension MovementsResponse {
    /// Beim „Weitere laden" die vorigen Karten vorn behalten.
    func mitVorher(_ vorher: [Movement]) -> MovementsResponse {
        MovementsResponse(items: vorher + items, total: total, page: page, perPage: perPage,
                          axis: axis, counts: counts)
    }
}

// MARK: - Ideen-Seite

struct MovementDetailView: View {
    let model: AppModel
    let clusterID: Int
    @State private var detail: MovementDetail?
    @State private var fehler: String?
    @State private var gesagt = ""

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 18) {
                if let detail {
                    inhalt(detail)
                } else if fehler != nil {
                    Text("Diese Idee gibt es nicht (mehr).")
                        .font(RatsFont.body(15))
                        .foregroundStyle(RatsColor.muted)
                        .padding(.top, 24)
                } else {
                    ProgressView().frame(maxWidth: .infinity).padding(.top, 32)
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 32)
        }
        .background(RatsColor.page)
        .navigationTitle("Idee")
        .navigationBarTitleDisplayMode(.inline)
        .task(id: clusterID) { await lade() }
    }

    @ViewBuilder
    private func inhalt(_ d: MovementDetail) -> some View {
        let b = d.movement
        VStack(alignment: .leading, spacing: 8) {
            if let feld = b.field {
                Text(IdeasView.feldLabel(feld).uppercased())
                    .font(RatsFont.mono(11)).tracking(0.7).foregroundStyle(RatsColor.muted)
            }
            Text(b.label)
                .font(RatsFont.title(26))
                .foregroundStyle(RatsColor.text)
                .fixedSize(horizontal: false, vertical: true)
                .accessibilityAddTraits(.isHeader)
            Text([ "\(b.cities.count) Städte", BewegungText.bilanz(b), BewegungText.zeitraum(b) ]
                    .compactMap { $0 }.joined(separator: " · "))
                .font(RatsFont.metadata())
                .foregroundStyle(RatsColor.muted)
                .fixedSize(horizontal: false, vertical: true)
        }
        .padding(.top, 8)

        oldenburg(d)
        buehne(d)

        VStack(alignment: .leading, spacing: 0) {
            Text("Alle Vorlagen, nach Datum")
                .font(RatsFont.title(16))
                .foregroundStyle(RatsColor.text)
                .padding(.bottom, 8)
            ForEach(d.documents.sorted { ($0.date ?? "9999") < ($1.date ?? "9999") }) { dok in
                eintrag(dok)
                Divider().overlay(RatsColor.separator)
            }
        }

        bilanz(b)

        Text("Die Vorlagen stammen aus den Ratsinformationssystemen der Städte. "
             + "Den Stand in Oldenburg beurteilt ein Sprachmodell an Oldenburger "
             + "Ratsunterlagen — nachprüfbar an den Belegen. Ein „Warum“ steht nur, "
             + "wo die Niederschrift selbst eine Begründung nennt.")
            .font(RatsFont.notice())
            .foregroundStyle(RatsColor.muted)
            .fixedSize(horizontal: false, vertical: true)

        if !d.similar.isEmpty {
            VStack(alignment: .leading, spacing: 6) {
                Text("IM SELBEN THEMENFELD").font(RatsFont.mono(11)).tracking(0.7)
                    .foregroundStyle(RatsColor.muted)
                ForEach(d.similar) { a in
                    Button {
                        model.navigation.append(.movement(id: a.clusterID))
                    } label: {
                        HStack {
                            Text(a.label).font(RatsFont.body(15, weight: .medium))
                                .foregroundStyle(RatsColor.primary)
                                .multilineTextAlignment(.leading)
                            Spacer(minLength: 8)
                            Text("\(a.cities) Städte").font(RatsFont.metadata())
                                .foregroundStyle(RatsColor.muted)
                        }
                    }
                    .buttonStyle(RatsPlainButtonStyle())
                }
            }
        }
    }

    private func buehne(_ d: MovementDetail) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Wie die Idee durch die Räte lief")
                .font(RatsFont.title(16))
                .foregroundStyle(RatsColor.text)
            ForEach(d.movement.cities) { c in
                let punkte = d.movement.timeline.filter { $0.bodyID == c.bodyID }
                HStack(spacing: 10) {
                    Text(c.city)
                        .font(RatsFont.body(13, weight: .semibold))
                        .foregroundStyle(RatsColor.text)
                        .frame(width: 92, alignment: .leading)
                        .lineLimit(2)
                    Zeitleiste(achse: d.axis, punkte: punkte,
                               label: "\(c.city): \(ZeitleisteRechnung.satz(punkte))")
                }
            }
            HStack(spacing: 10) {
                Color.clear.frame(width: 92, height: 1)
                Jahresskala(achse: d.axis)
            }
            ZeitleisteLegende()
        }
        .padding(16)
        .background(RatsColor.stage)
        .overlay(RoundedRectangle(cornerRadius: 18, style: .continuous).stroke(RatsColor.border))
        .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
    }

    private func eintrag(_ d: MovementDocument) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(spacing: 8) {
                Text(d.city).font(RatsFont.body(14, weight: .semibold)).foregroundStyle(RatsColor.text)
                Text(Self.datum(d.date)).font(RatsFont.metadata()).foregroundStyle(RatsColor.muted)
                Spacer(minLength: 0)
                ErgebnisPille(outcome: d.outcome)
            }
            if let web = d.web, let url = URL(string: web) {
                Link(destination: url) {
                    (Text(d.name) + Text("  ↗").foregroundColor(RatsColor.muted))
                        .font(RatsFont.sourceTitle())
                        .foregroundStyle(RatsColor.text)
                        .multilineTextAlignment(.leading)
                }
            } else {
                Text(d.name).font(RatsFont.sourceTitle()).foregroundStyle(RatsColor.text)
            }
            if let summary = d.summary, !summary.isEmpty {
                Text(summary).font(RatsFont.reading()).foregroundStyle(RatsColor.bodyText)
                    .fixedSize(horizontal: false, vertical: true)
            }
            if let p = d.protocolNote, !p.why.isEmpty {
                VStack(alignment: .leading, spacing: 3) {
                    Text(p.why).font(RatsFont.reading()).italic().foregroundStyle(RatsColor.bodyText)
                        .fixedSize(horizontal: false, vertical: true)
                    Text(["aus der Niederschrift", p.organization, p.date.map(Self.datum), p.vote]
                            .compactMap { $0 }.joined(separator: " · "))
                        .font(RatsFont.metadata()).foregroundStyle(RatsColor.muted)
                        .fixedSize(horizontal: false, vertical: true)
                }
                .padding(.leading, 10)
                .overlay(alignment: .leading) { Rectangle().fill(RatsColor.border).frame(width: 2) }
            } else if d.protocolSource == "withheld" {
                Text("Die Stadt veröffentlicht ihre Niederschriften nicht.")
                    .font(RatsFont.metadata()).foregroundStyle(RatsColor.muted)
            }
        }
        .padding(.vertical, 12)
    }

    private func oldenburg(_ d: MovementDetail) -> some View {
        RatsWidget("Und in Oldenburg?", accent: .buoy, board: true) {
            EmptyView()
        } content: {
            VStack(alignment: .leading, spacing: 10) {
                if let u = d.movement.oldenburg {
                    StandPille(status: u.status)
                    if !u.situation.isEmpty {
                        Text(u.situation).font(RatsFont.reading()).foregroundStyle(RatsColor.text)
                            .fixedSize(horizontal: false, vertical: true)
                    }
                    if !u.evidence.isEmpty { belege("WORAUF SICH DAS STÜTZT", u.evidence) }
                    if !u.related.isEmpty {
                        belege("VERWANDTES AUS OLDENBURG", u.related,
                               hinweis: "Berührt die Sache, belegt den Stand aber nicht.")
                    }
                    rueckmeldung
                } else {
                    Text("Ob Oldenburg das schon hat, ist noch nicht geprüft.")
                        .font(RatsFont.reading()).foregroundStyle(RatsColor.muted)
                }
            }
        }
    }

    private func belege(_ titel: String, _ liste: [IdeaEvidence], hinweis: String? = nil) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(titel).font(RatsFont.mono(11)).tracking(0.7).foregroundStyle(RatsColor.muted)
            if let hinweis {
                Text(hinweis).font(RatsFont.body(12.5)).foregroundStyle(RatsColor.muted)
            }
            ForEach(liste) { beleg in
                if let id = beleg.decisionID {
                    Button { model.navigation.append(.decision(id: id)) } label: {
                        HStack(alignment: .top) {
                            Text(beleg.title).font(RatsFont.body(14)).foregroundStyle(RatsColor.text)
                                .multilineTextAlignment(.leading)
                            Spacer(minLength: 6)
                            RatsIcon(.chevronRight, size: 12).foregroundStyle(RatsColor.muted)
                        }
                    }
                    .buttonStyle(RatsPlainButtonStyle())
                } else {
                    Text(beleg.title).font(RatsFont.body(14)).foregroundStyle(RatsColor.text)
                }
            }
        }
    }

    private var rueckmeldung: some View {
        HStack(spacing: 12) {
            Text("Stimmt das?").font(RatsFont.body(12.5)).foregroundStyle(RatsColor.muted)
            ForEach(["right", "wrong"], id: \.self) { wert in
                Button(wert == "right" ? "Ja" : "Nein") { Task { await sagen(wert) } }
                    .font(RatsFont.body(12.5, weight: gesagt == wert ? .semibold : .regular))
                    .foregroundStyle(gesagt == wert ? RatsColor.primary : RatsColor.muted)
            }
        }
    }

    private func bilanz(_ b: Movement) -> some View {
        // Eine Liste und kein Balken — „keine Stimm-/Abstimmungsgrafiken"
        // (Designsprache § 8).
        let reihe = ["accepted", "amended", "rejected", "postponed", "referred", "noted", "withdrawn", "none"]
        let zaehler = Dictionary(grouping: b.timeline, by: \.outcome).mapValues(\.count)
        return VStack(alignment: .leading, spacing: 8) {
            Text("So haben die Räte entschieden").font(RatsFont.title(16)).foregroundStyle(RatsColor.text)
            ForEach(reihe.filter { (zaehler[$0] ?? 0) > 0 }, id: \.self) { k in
                HStack {
                    ErgebnisPille(outcome: k)
                    Spacer()
                    Text("\(zaehler[k] ?? 0)").font(RatsFont.mono(14)).monospacedDigit()
                        .foregroundStyle(RatsColor.text)
                }
            }
            Text("Je Vorlage, nicht je Stadt.").font(RatsFont.metadata()).foregroundStyle(RatsColor.muted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .ratsCard()
    }

    private func lade() async {
        do {
            let r: MovementDetail = try await model.api.get(
                "/api/council/cities/movements/detail",
                query: [URLQueryItem(name: "id", value: String(clusterID))])
            detail = r
            fehler = nil
        } catch {
            fehler = error.localizedDescription
        }
    }

    private func sagen(_ wert: String) async {
        gesagt = wert
        do {
            try await model.api.sendVoid(
                "/api/council/cities/movements/feedback",
                query: [URLQueryItem(name: "id", value: String(clusterID)),
                        URLQueryItem(name: "verdict", value: wert)])
        } catch {
            gesagt = ""
        }
    }

    private static func datum(_ iso: String?) -> String {
        guard let iso, iso.count >= 10 else { return "ohne Datum" }
        let t = iso.prefix(10).split(separator: "-")
        return t.count == 3 ? "\(t[2]).\(t[1]).\(t[0])" : iso
    }
}
