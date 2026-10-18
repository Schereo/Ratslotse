import RatslotseAPI
import RatslotseDesign
import SwiftUI

/// „Neu bei Ratslotse" — was eine neue Ausgabe gebracht hat, auf „Heute".
///
/// Dieselbe Karte wie im Web (`components/release-news-card.tsx`), mit
/// denselben Regeln. **Wer sie sieht, entscheidet der Server**
/// (`GET /api/news`; die App meldet sich mit `X-Client: ios` und bekommt die
/// Aufnahmen aus der App).
///
/// **Video-Kacheln statt einer Bühne zum Durchklicken** (seit 3.0.0, Tims
/// Befund 07.10.2026: „Die Karte fühlt sich langweilig an … mehr Bilder, mehr
/// Anreiz"). Je Neuerung eine große Kachel mit Titelbild, Farbe, Titel und
/// Länge des Clips, waagerecht zum Wischen; ein Tipp öffnet den
/// Story-Spieler (`ReleaseStoryPlayer`). Kleinere Neuerungen (`aside`) stehen
/// als Zeile „Außerdem: …" darunter. Ohne Aufnahmen fällt die Karte auf die
/// Listenform zurück.
///
/// **Wann die Karte endgültig geht** — wie im Web: Die Marke am Konto
/// (`news_seen_version`) setzt erstens „alle Kacheln angesehen" (die Karte
/// bleibt dann bis zum nächsten Laden stehen, alle abgehakt) und zweitens das
/// kleine × in der Ecke. Welche Kacheln angesehen sind, merkt sich nur dieses
/// Gerät (`UserDefaults`).
///
/// **Die ausgelieferte App** kennt keines der neuen Felder und zeigt weiter
/// ihre Bühne: Alles Neue im Vertrag ist optional (`ios_vertrag.py
/// --ausgeliefert`).
struct ReleaseNewsCard: View {
    let model: AppModel
    /// Geladen von „Heute" (`TodayView.load`), wie jede andere Karte dort —
    /// die Karte selbst ist reine Anzeige. Eine Karte, die sich selbst lädt,
    /// hinge mit ihrem `.task` an einer leeren Gruppe, und eine leere Gruppe
    /// „erscheint" in SwiftUI nie: Der Ruf lief kein einziges Mal (08.09.2026).
    let state: NewsState
    let newest: ReleaseNews
    /// × — Heute räumt die Karte weg und meldet die Version.
    let onDismiss: () -> Void
    /// Alle Kacheln angesehen — die Marke setzen, die Karte bleibt stehen.
    let onAllWatched: () -> Void

    @State private var watched: Set<String> = []
    @State private var request: StoryRequest?
    /// Wohin „… ausprobieren" führt — erst NACH dem Schließen des Spielers,
    /// sonst navigiert die App hinter einer Vollbild-Präsentation.
    @State private var pendingPath: String?
    @State private var reported = false
    @State private var visibleTile: String?
    /// Breite der Karte, gemessen — die Kachel nimmt 78 % davon, höchstens
    /// 300 pt (wie im Web), und steht 4 : 5.
    @State private var carouselWidth: CGFloat = 360
    @Environment(\.horizontalSizeClass) private var sizeClass

    private var tiles: [ReleaseHighlight] { newest.highlights.filter { !$0.aside } }
    private var asides: [ReleaseHighlight] { newest.highlights.filter(\.aside) }
    /// Kacheln oder Liste: Die Registry verlangt alle Aufnahmen oder keine.
    private var staged: Bool { !tiles.isEmpty && newest.highlights.allSatisfy { $0.media != nil } }
    private var watchedCount: Int { tiles.filter { watched.contains($0.id) }.count }

    var body: some View {
        ScrollViewReader { proxy in
            card
                .id(Self.anchor)
                .task { await debugHooks(proxy) }
        }
    }

    private static let anchor = "release-news-card"

    /// Sichtprobe ohne Finger (nur `#if DEBUG`, wie die anderen
    /// `RATSLOTSE_DEBUG_*`-Schalter): `RATSLOTSE_DEBUG_NEWS=card` rollt „Heute"
    /// bis zur Karte, eine Zahl öffnet zusätzlich den Spieler an dieser Kachel
    /// (`=1` → „2 von 3").
    private func debugHooks(_ proxy: ScrollViewProxy) async {
#if DEBUG
        guard let mode = ratsDebugValue("RATSLOTSE_DEBUG_NEWS") else { return }
        try? await Task.sleep(for: .milliseconds(800))
        proxy.scrollTo(Self.anchor, anchor: .top)
        if let start = Int(mode), tiles.indices.contains(start) {
            try? await Task.sleep(for: .milliseconds(500))
            request = StoryRequest(sequence: tiles, start: start, aside: false)
        }
#endif
    }

    private var card: some View {
        VStack(alignment: .leading, spacing: 0) {
            header
                .padding(.horizontal, 16)
                .padding(.top, 16)
            if staged {
                carousel.padding(.top, 16)
                ForEach(asides) { aside in
                    asideRow(aside).padding(.horizontal, 16).padding(.top, 12)
                }
            } else {
                list.padding(.horizontal, 16).padding(.top, 12)
            }
            if state.releases.count > 1 {
                older.padding(.horizontal, 16).padding(.top, 14)
            }
            changelogLink
                .padding(.horizontal, 16)
                .padding(.top, 12)
                .padding(.bottom, 16)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(RatsColor.card)
        .overlay(RoundedRectangle(cornerRadius: 16, style: .continuous).stroke(RatsColor.border, lineWidth: 1))
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .shadow(color: .black.opacity(0.04), radius: 2, y: 1)
        .accessibilityElement(children: .contain)
        .onAppear { watched = ReleaseWatchStore.load(newest.version) }
        .onChange(of: watchedCount) { _, _ in reportIfComplete() }
        .fullScreenCover(item: $request, onDismiss: {
            if let path = pendingPath {
                pendingPath = nil
                model.handle(pushPath: path)
            }
        }) { request in
            ReleaseStoryPlayer(
                sequence: request.sequence,
                start: request.start,
                aside: request.aside,
                resolve: model.api.url(forPath:),
                onSeen: markWatched,
                onTry: { highlight in
                    pendingPath = highlight.url
                    self.request = nil
                }
            )
        }
    }

    // MARK: Kopf

    private var header: some View {
        HStack(alignment: .top, spacing: 12) {
            LottiSpriteView(animation: .idea, animated: false)
                .frame(width: 56, height: 56)
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 3) {
                Text(kicker.uppercased())
                    .font(RatsFont.mono(11, weight: .semibold))
                    .tracking(0.9)
                    .foregroundStyle(RatsColor.primary)
                    .fixedSize(horizontal: false, vertical: true)
                Text(newest.title)
                    .font(RatsFont.title(24, weight: .heavy))
                    .foregroundStyle(RatsColor.text)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityAddTraits(.isHeader)
                if let teaser = newest.teaser {
                    Text(teaser)
                        .font(RatsFont.notice())
                        .foregroundStyle(RatsColor.secondary)
                        .fixedSize(horizontal: false, vertical: true)
                }
                // Auf dem iPad steht der Fortschritt im Kopf; am Telefon
                // sagen es die Haken auf den Kacheln (wie im Web).
                if staged, sizeClass == .regular, tiles.count > 1 { progress.padding(.top, 6) }
            }
            Spacer(minLength: 0)
        }
        // Platz für das × — es schwebt in der Ecke, statt dem Titel eine
        // ganze Spalte zu nehmen („Das Lotti-Update" brach sonst um).
        .padding(.trailing, 22)
        .overlay(alignment: .topTrailing) {
            // Klein und in der Ecke: „Alles klar" stand in der ersten Fassung
            // gleichberechtigt neben der Bühne, und drei von vier Neuerungen
            // sah nie jemand (Tims Befund 07.09.2026).
            Button(action: onDismiss) {
                RatsIcon(.circleX, size: 20)
                    .foregroundStyle(RatsColor.muted)
                    .frame(width: 44, height: 44)
                    .contentShape(Rectangle())
            }
            .buttonStyle(RatsPlainButtonStyle())
            .padding(.top, -12)
            .padding(.trailing, -14)
            .accessibilityLabel("Neuigkeiten ausblenden")
        }
    }

    /// Eine Ausgabe nennt ihre Nummer, mehrere sagen, dass hier
    /// Liegengebliebenes steht.
    private var kicker: String {
        let versions = state.releases.map { shortReleaseVersion($0.version) }
        return versions.count > 1
            ? "Neu seit deinem letzten Besuch · " + versions.joined(separator: " und ")
            : "Neu bei Ratslotse · " + (versions.first ?? "")
    }

    private var progress: some View {
        VStack(alignment: .leading, spacing: 5) {
            HStack(spacing: 5) {
                ForEach(0..<tiles.count, id: \.self) { i in
                    Capsule().fill(i < watchedCount ? RatsColor.signal : RatsColor.border)
                        .frame(width: 30, height: 5)
                }
            }
            Text("\(watchedCount) von \(tiles.count) angesehen")
                .font(RatsFont.metadata())
                .foregroundStyle(RatsColor.muted)
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("\(watchedCount) von \(tiles.count) Videos angesehen")
    }

    // MARK: Kacheln

    /// Waagerecht zum Wischen, mit Einrasten; die nächste Kachel schaut
    /// angeschnitten herein — das sagt ohne Worte, dass es weitergeht.
    private var carousel: some View {
        // Feste Maße statt `containerRelativeFrame`: Ein Titelbild mit
        // `scaledToFill` meldet seine eigene Größe nach oben, und die Kachel
        // wuchs darüber über ihre Nachbarin hinaus (Sichtprobe 07.10.2026).
        let width = min(max(carouselWidth - 32, 200) * 0.82, 300)
        let size = CGSize(width: width, height: (width * 1.25).rounded())
        return VStack(spacing: 10) {
            ScrollView(.horizontal, showsIndicators: false) {
                LazyHStack(spacing: 12) {
                    ForEach(Array(tiles.enumerated()), id: \.element.id) { position, highlight in
                        ReleaseTile(
                            highlight: highlight,
                            number: position + 1,
                            watched: watched.contains(highlight.id),
                            size: size,
                            resolve: model.api.url(forPath:)
                        ) {
                            request = StoryRequest(sequence: tiles, start: position, aside: false)
                        }
                        .id(highlight.id)
                    }
                }
                .scrollTargetLayout()
                .padding(.vertical, 6)
            }
            .contentMargins(.horizontal, 16, for: .scrollContent)
            .scrollTargetBehavior(.viewAligned)
            .scrollPosition(id: $visibleTile)
            .frame(height: size.height + 12)
            if tiles.count > 1 { dots }
        }
        .background {
            GeometryReader { proxy in
                Color.clear
                    .onAppear { carouselWidth = proxy.size.width }
                    .onChange(of: proxy.size.width) { _, width in carouselWidth = width }
            }
        }
    }

    private var dots: some View {
        let active = tiles.firstIndex { $0.id == visibleTile } ?? 0
        return HStack(spacing: 6) {
            ForEach(0..<tiles.count, id: \.self) { i in
                Capsule()
                    .fill(i == active ? RatsColor.signal : RatsColor.border)
                    .frame(width: i == active ? 20 : 8, height: 8)
            }
        }
        .frame(maxWidth: .infinity)
        .animation(RatsMotion.flow, value: active)
        .accessibilityHidden(true)
    }

    /// „Außerdem: …" — eine Neuerung ohne eigene Kachel; ein Tipp öffnet
    /// ihren Clip allein.
    private func asideRow(_ highlight: ReleaseHighlight) -> some View {
        Button {
            request = StoryRequest(sequence: [highlight], start: 0, aside: true)
        } label: {
            HStack(spacing: 10) {
                (Text("Außerdem: ").fontWeight(.semibold) + Text(highlight.title))
                    .font(RatsFont.body(15))
                    .foregroundStyle(RatsColor.text)
                    .multilineTextAlignment(.leading)
                    .fixedSize(horizontal: false, vertical: true)
                Spacer(minLength: 0)
                RatsIcon(.arrowRight, size: 16).foregroundStyle(RatsColor.primary)
            }
            .padding(12)
            .background(RatsColor.primary.opacity(0.06))
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
            .contentShape(Rectangle())
        }
        .buttonStyle(RatsPlainButtonStyle())
        .accessibilityLabel("Außerdem: \(highlight.title). Video ansehen")
    }

    // MARK: Liste (ohne Aufnahmen)

    private var list: some View {
        VStack(alignment: .leading, spacing: 10) {
            ForEach(newest.highlights) { highlight in
                Button { model.handle(pushPath: highlight.url) } label: {
                    VStack(alignment: .leading, spacing: 3) {
                        HStack(spacing: 4) {
                            Text(highlight.title)
                                .font(RatsFont.body(14, weight: .semibold))
                                .foregroundStyle(RatsColor.text)
                            RatsIcon(.arrowRight, size: 12).foregroundStyle(RatsColor.primary)
                        }
                        Text(highlight.text)
                            .font(RatsFont.body(13))
                            .foregroundStyle(RatsColor.secondary)
                            .lineSpacing(2)
                    }
                    .multilineTextAlignment(.leading)
                    .contentShape(Rectangle())
                }
                .buttonStyle(RatsPlainButtonStyle())
            }
        }
    }

    // MARK: Ältere Ausgaben, Fuß

    private var older: some View {
        VStack(alignment: .leading, spacing: 6) {
            Divider().overlay(RatsColor.separator)
            MonoKicker("Außerdem seit deinem letzten Besuch")
            ForEach(state.releases.dropFirst()) { release in
                (Text(shortReleaseVersion(release.version)).fontWeight(.semibold).foregroundStyle(RatsColor.text)
                    + Text(" — " + release.highlights.map(\.title).joined(separator: " · ")))
                    .font(RatsFont.body(13))
                    .foregroundStyle(RatsColor.secondary)
                    .lineSpacing(2)
            }
        }
    }

    private var changelogLink: some View {
        Button { model.handle(route: .web(model.api.url(forPath: "/changelog"))) } label: {
            Text(changelogLabel)
                .font(RatsFont.body(13))
                .underline()
                .foregroundStyle(RatsColor.secondary)
        }
        .buttonStyle(RatsPlainButtonStyle())
    }

    /// „dieser Version" stimmt nur, wenn es wirklich eine ist.
    private var changelogLabel: String {
        if state.olderCount > 0 {
            return "Alle Änderungen — auch \(state.olderCount) ältere Version\(state.olderCount == 1 ? "" : "en")"
        }
        return state.releases.count > 1 ? "Alle Änderungen im Einzelnen" : "Alle Änderungen dieser Version"
    }

    // MARK: Angesehen

    private func markWatched(_ highlight: ReleaseHighlight) {
        guard !highlight.aside else { return } // Nebenbei zählt nicht.
        watched = ReleaseWatchStore.mark(newest.version, highlight.id)
    }

    /// Alle angesehen → die Marke am Konto, einmal je Karte.
    private func reportIfComplete() {
        guard staged, !reported, !tiles.isEmpty, watchedCount >= tiles.count else { return }
        reported = true
        onAllWatched()
    }
}

/// „2.3.0" → „2.3" — die Patch-Null sagt niemandem etwas.
func shortReleaseVersion(_ version: String) -> String {
    version.hasSuffix(".0") ? String(version.dropLast(2)) : version
}

/// Was der Spieler zeigen soll: alle Kacheln ab einer — oder ein einzelnes
/// Nebenbei-Highlight.
struct StoryRequest: Identifiable {
    let id = UUID()
    let sequence: [ReleaseHighlight]
    let start: Int
    let aside: Bool
}

// MARK: - Farben

/// Die Farben der Video-Kacheln — die Werte stehen in DESIGNSPRACHE.md
/// („Neuigkeiten-Kacheln") und gleich im Web (`lib/neuigkeiten.ts`).
///
/// **Feste Werte statt `RatsColor`**: Auf der Kachel steht Weiß, und im
/// Dunkelmodus würden Primär und Signal hell — Weiß fiele dort unter 4,5 : 1.
/// Die Kachel ist ein Titelbild und wechselt mit dem Erscheinungsbild nicht die
/// Farbe. `tests/test_releases.py` hält jeden Namen der Registry gegen diese
/// Liste.
enum ReleaseTileColor {
    static func color(_ name: String?) -> Color {
        switch name {
        case "signal": return rgb(0xCE4709)  // Signal-Orange, Weiß darauf 4,65 : 1
        case "green": return rgb(0x15803D)   // Grün der Bebauungspläne, 5,02 : 1
        case "primary": return rgb(0x0764A6) // Hafenblau, 6,20 : 1
        default: return rgb(0x0764A6)
        }
    }

    /// Die helle Textfarbe hsl(212 55% 11%) — der Abdunkler über dem Bild.
    static let shade = rgb(0x0D2032)

    static func rgb(_ hex: UInt32) -> Color {
        Color(
            .sRGB,
            red: Double((hex >> 16) & 0xFF) / 255,
            green: Double((hex >> 8) & 0xFF) / 255,
            blue: Double(hex & 0xFF) / 255
        )
    }
}

// MARK: - Angesehen merken

/// Welche Kacheln auf diesem Gerät schon angesehen sind — je Ausgabe. Eine
/// Lesehilfe, keine Entscheidung: Ob die Karte erscheint, sagt die Marke am
/// Konto. Derselbe Schlüssel wie im Web (`localStorage`).
enum ReleaseWatchStore {
    static func key(_ version: String) -> String { "ratslotse.neuigkeiten.gesehen.\(version)" }

    static func load(_ version: String, defaults: UserDefaults = .standard) -> Set<String> {
        Set(defaults.stringArray(forKey: key(version)) ?? [])
    }

    static func mark(_ version: String, _ id: String, defaults: UserDefaults = .standard) -> Set<String> {
        var current = load(version, defaults: defaults)
        guard !current.contains(id) else { return current }
        current.insert(id)
        defaults.set(Array(current).sorted(), forKey: key(version))
        return current
    }
}

// MARK: - Kachel

/// Eine Video-Kachel: Titelbild, Farbe, Titel, eine Zeile, Länge, Abspielen.
/// Die ganze Kachel ist EIN Knopf.
private struct ReleaseTile: View {
    let highlight: ReleaseHighlight
    let number: Int
    let watched: Bool
    let size: CGSize
    let resolve: (String) -> URL
    let open: () -> Void

    private var tint: Color { ReleaseTileColor.color(highlight.color) }

    var body: some View {
        Button(action: open) {
            ZStack(alignment: .bottomLeading) {
                ReleaseTileColor.shade
                if let media = highlight.media {
                    AsyncImage(url: resolve(media.tileImage)) { phase in
                        if case .success(let image) = phase {
                            // Oben angeschlagen wie im Web (`object-top`): Die
                            // untere Hälfte deckt ohnehin die Kachelfarbe.
                            image.resizable().scaledToFill()
                                .frame(width: size.width, height: size.height, alignment: .top)
                                .clipped()
                        } else {
                            Color.clear
                        }
                    }
                    .frame(width: size.width, height: size.height)
                    .clipped()
                }
                // Ab gut der Hälfte deckt die Farbe zu 95 %, ab drei Vierteln
                // ganz — dort steht die Schrift (DESIGNSPRACHE § 2).
                LinearGradient(
                    stops: [
                        .init(color: ReleaseTileColor.shade.opacity(0), location: 0.20),
                        .init(color: ReleaseTileColor.shade.opacity(0.5), location: 0.40),
                        .init(color: tint.opacity(0.95), location: 0.58),
                        .init(color: tint, location: 0.74),
                    ],
                    startPoint: .top, endPoint: .bottom
                )
                VStack(alignment: .leading, spacing: 6) {
                    Text(highlight.title)
                        .font(RatsFont.title(22, weight: .heavy))
                        .foregroundStyle(.white)
                        .fixedSize(horizontal: false, vertical: true)
                    if let tagline = highlight.tagline {
                        Text(tagline)
                            .font(RatsFont.body(14))
                            .foregroundStyle(.white.opacity(0.9))
                            .fixedSize(horizontal: false, vertical: true)
                    }
                }
                .multilineTextAlignment(.leading)
                .padding(16)
                .frame(width: size.width, alignment: .leading)
            }
            .overlay(alignment: .topLeading) { badge.padding(12) }
            .overlay(alignment: .topTrailing) { durationPill.padding(12) }
            .overlay { playButton }
            .frame(width: size.width, height: size.height)
            .clipShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
            .shadow(color: Color(red: 2 / 255, green: 32 / 255, blue: 64 / 255).opacity(0.28), radius: 14, y: 10)
            .contentShape(RoundedRectangle(cornerRadius: 18, style: .continuous))
        }
        .buttonStyle(RatsPlainButtonStyle())
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(accessibilityText)
        .accessibilityAddTraits(.isButton)
    }

    private var accessibilityText: String {
        var text = "Video ansehen: \(highlight.title)"
        if let spoken = highlight.media?.durationSpoken { text += ", \(spoken)" }
        if watched { text += " (schon angesehen)" }
        return text
    }

    private var badge: some View {
        ZStack {
            Circle().fill(.white.opacity(0.95))
            if watched {
                RatsIcon(.check, size: 15).foregroundStyle(tint)
            } else {
                Text("\(number)")
                    .font(RatsFont.title(17, weight: .heavy))
                    .foregroundStyle(tint)
            }
        }
        .frame(width: 32, height: 32)
    }

    @ViewBuilder private var durationPill: some View {
        if let label = highlight.media?.durationLabel {
            HStack(spacing: 4) {
                RatsIcon(.play, size: 11)
                Text(label).monospacedDigit()
            }
            .font(RatsFont.body(13, weight: .semibold))
            .foregroundStyle(.white)
            .padding(.horizontal, 10)
            .padding(.vertical, 5)
            .background(ReleaseTileColor.shade.opacity(0.62))
            .clipShape(Capsule())
        }
    }

    private var playButton: some View {
        GeometryReader { proxy in
            ZStack {
                Circle().fill(.white.opacity(0.94))
                    .shadow(color: .black.opacity(0.35), radius: 12, y: 8)
                RatsIcon(.play, size: 26).foregroundStyle(tint).offset(x: 2)
            }
            .frame(width: 64, height: 64)
            .position(x: proxy.size.width / 2, y: proxy.size.height * 0.40)
        }
        .allowsHitTesting(false)
    }
}
