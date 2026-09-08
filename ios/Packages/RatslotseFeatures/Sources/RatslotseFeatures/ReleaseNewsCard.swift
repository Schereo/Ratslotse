import AVFoundation
import RatslotseAPI
import RatslotseDesign
import SwiftUI

/// „Neu bei Ratslotse" — was eine neue Ausgabe gebracht hat, auf „Heute".
///
/// Dieselbe Karte wie im Web (`components/release-news-card.tsx`), mit
/// denselben Regeln: **Wer sie sieht, entscheidet der Server** (`GET /api/news`,
/// die App meldet sich mit `X-Client: ios` und bekommt die Aufnahmen aus der
/// App). **Eine Bühne, keine Stichpunktliste** — jedes Highlight bringt einen
/// Clip oder ein Bild mit, und man blättert durch sie. **Kein Selbstlauf**: Die
/// Bühne wechselt nur auf Tipp oder Wisch; was sich von selbst bewegt, ist der
/// Clip, und der zeigt das Feature. **„Alles klar" setzt eine Hochwassermarke
/// am Konto**, nicht am Gerät — auf dem Telefon weggewischt heißt auch am
/// Laptop weg. Gemeldet wird die Version, die diese Karte GEZEIGT hat.
///
/// **Geführter Durchgang** (Tims Befund 07.09.2026): „Weiter" ist der
/// Hauptknopf und springt zur nächsten Station, die noch nicht abgehakt ist;
/// erst wenn alle einmal dastanden, wird daraus „Alles klar". Die Reiter
/// darunter tragen Nummer und Haken.
struct ReleaseNewsCard: View {
    let model: AppModel
    /// Geladen von „Heute" (`TodayView.load`), wie jede andere Karte dort —
    /// die Karte selbst ist reine Anzeige. Eine Karte, die sich selbst lädt,
    /// hinge mit ihrem `.task` an einer leeren Gruppe, und eine leere Gruppe
    /// „erscheint" in SwiftUI nie: Der Ruf lief kein einziges Mal (08.09.2026).
    let state: NewsState
    let newest: ReleaseNews
    /// „Alles klar": Heute räumt die Karte weg und meldet die Version.
    let onDone: () -> Void

    var body: some View {
        ReleaseNewsStage(model: model, state: state, newest: newest, onDone: onDone)
    }
}

/// „2.3.0" → „2.3" — die Patch-Null sagt niemandem etwas.
func shortReleaseVersion(_ version: String) -> String {
    version.hasSuffix(".0") ? String(version.dropLast(2)) : version
}

private struct ReleaseNewsStage: View {
    let model: AppModel
    let state: NewsState
    let newest: ReleaseNews
    let onDone: () -> Void
    @State private var index = 0
    /// Die erste Station hat man mit dem Aufschlagen der Karte gesehen.
    @State private var seen: Set<Int> = [0]
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    private var highlights: [ReleaseHighlight] { newest.highlights }
    /// Bühne oder Liste: Die Registry verlangt alle Aufnahmen oder keine.
    private var staged: Bool { !highlights.isEmpty && highlights.allSatisfy { $0.media != nil } }
    private var allSeen: Bool { seen.count >= highlights.count }
    private var current: ReleaseHighlight? { highlights.indices.contains(index) ? highlights[index] : nil }

    var body: some View {
        RatsWidget(headline, accent: .harbor, glyph: .sparkles, trailing: { versionPill }) {
            VStack(alignment: .leading, spacing: 12) {
                Text(newest.title)
                    .font(RatsFont.title(19, weight: .bold))
                    .foregroundStyle(RatsColor.text)
                    .fixedSize(horizontal: false, vertical: true)
                if staged, let current { stage(current) } else { list }
                if state.releases.count > 1 { older }
                footer
            }
        }
        .accessibilityElement(children: .contain)
        .accessibilityLabel("Neu bei Ratslotse: \(newest.title)")
    }

    /// Eine Ausgabe nennt ihre Nummer, mehrere sagen, dass hier
    /// Liegengebliebenes steht.
    private var headline: String {
        state.releases.count > 1 ? "Neu seit deinem letzten Besuch" : "Neu bei Ratslotse"
    }

    private var versionPill: some View {
        Text(state.releases.map { shortReleaseVersion($0.version) }.joined(separator: " · "))
            .font(RatsFont.mono(10, weight: .semibold))
            .tracking(0.6)
            .foregroundStyle(RatsColor.primary)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(RatsColor.primary.opacity(0.10))
            .clipShape(Capsule())
            .fixedSize()
    }

    // MARK: Bühne

    private func stage(_ highlight: ReleaseHighlight) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            if let media = highlight.media { mediaBox(media) }
            VStack(alignment: .leading, spacing: 4) {
                // Der Zähler sagt vor dem ersten Tipp, dass es mehr als das
                // eine gibt.
                MonoKicker("\(index + 1) von \(highlights.count)")
                Text(highlight.title)
                    .font(RatsFont.body(15, weight: .semibold))
                    .foregroundStyle(RatsColor.text)
                    .fixedSize(horizontal: false, vertical: true)
                Text(highlight.text)
                    .font(RatsFont.body(13.5))
                    .foregroundStyle(RatsColor.secondary)
                    .lineSpacing(2)
                    .fixedSize(horizontal: false, vertical: true)
            }
            .id(index)
            .transition(.opacity)
            HStack(spacing: 10) {
                if allSeen {
                    Button(action: onDone) { buttonLabel("Alles klar", .check, iconFirst: true) }
                        .buttonStyle(PrimaryButtonStyle())
                } else {
                    Button(action: next) { buttonLabel("Weiter", .arrowRight) }
                        .buttonStyle(PrimaryButtonStyle())
                }
                Button { open(highlight.url) } label: { buttonLabel("Ansehen", .arrowRight) }
                    .buttonStyle(SecondaryButtonStyle())
            }
            tabs
        }
        .animation(reduceMotion ? nil : RatsMotion.stage, value: index)
    }

    /// Der Kasten hat die Form seiner Aufnahme (`aspect` aus der Registry):
    /// ein Telefon-Bildschirm steht hochkant, mittig und nimmt sich die Höhe
    /// (320 pt — wie die 300 px der Web-Karte auf dem Telefon; 400 füllten
    /// den halben Bildschirm mit einem Kasten);
    /// ein Browser-Fenster liegt quer über die Breite. Alle Medien einer
    /// Ausgabe teilen sich ein Verhältnis — der Kasten springt beim Blättern
    /// nicht. Der Wechsel blendet nur: Eine Strecke gäbe es nicht zu zeigen.
    private func mediaBox(_ media: ReleaseMedia) -> some View {
        let ratio = media.aspectRatio ?? 16.0 / 9.0
        let portrait = ratio < 1
        // Reihenfolge ist Bedeutung: Erst die Höhe vorschlagen, dann das
        // Verhältnis einpassen — andersherum nimmt sich ein Telefon-Bildschirm
        // die volle Breite und wird 700 pt hoch (gemessen 08.09.2026).
        return ReleaseMediaView(media: media, resolve: model.api.url(forPath:), reduceMotion: reduceMotion)
            .id(index)
            .transition(.opacity)
            .aspectRatio(ratio, contentMode: .fit)
            .frame(height: portrait ? 320 : nil)
            .background(RatsColor.stage)
            .clipShape(RoundedRectangle(cornerRadius: 12, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 12, style: .continuous).stroke(RatsColor.border))
            .frame(maxWidth: .infinity)
            .accessibilityLabel(media.alt)
            .gesture(
                DragGesture(minimumDistance: 24)
                    .onEnded { value in
                        guard abs(value.translation.width) > abs(value.translation.height) else { return }
                        show(value.translation.width < 0 ? index + 1 : index - 1)
                    }
            )
    }

    /// Die Reiter tragen Nummer und Titel, nicht bloß Punkte: Man soll vorher
    /// wissen, wohin man blättert, und hinterher sehen, was man schon hatte.
    private var tabs: some View {
        ScrollViewReader { proxy in
            ScrollView(.horizontal, showsIndicators: false) {
                tabRow
                    .padding(.vertical, 1)
            }
            // Der aktive Reiter rückt ins Bild: „Weiter" schaltet sonst auf
            // eine Station, deren Reiter rechts abgeschnitten steht.
            .onChange(of: index) { _, neu in
                withAnimation(reduceMotion ? nil : RatsMotion.flow) { proxy.scrollTo(neu, anchor: .center) }
            }
        }
    }

    private var tabRow: some View {
            HStack(spacing: 6) {
                ForEach(Array(highlights.enumerated()), id: \.offset) { position, highlight in
                    let active = position == index
                    let done = seen.contains(position) && !active
                    Button { show(position) } label: {
                        HStack(spacing: 6) {
                            ZStack {
                                Circle().fill(
                                    active ? RatsColor.primary
                                        : done ? RatsColor.primary.opacity(0.15)
                                        : RatsColor.muted.opacity(0.18)
                                )
                                if done {
                                    RatsIcon(.check, size: 9).foregroundStyle(RatsColor.primary)
                                } else {
                                    Text("\(position + 1)")
                                        .font(RatsFont.mono(9, weight: .bold))
                                        .foregroundStyle(active ? RatsColor.primaryText : RatsColor.secondary)
                                }
                            }
                            .frame(width: 16, height: 16)
                            Text(highlight.title)
                                .font(RatsFont.body(11.5, weight: .medium))
                                .lineLimit(1)
                        }
                        .padding(.horizontal, 10)
                        .padding(.vertical, 6)
                        .foregroundStyle(active ? RatsColor.primary : RatsColor.secondary)
                        .background(active ? RatsColor.primary.opacity(0.10) : RatsColor.card)
                        .overlay(Capsule().stroke(active ? RatsColor.primary.opacity(0.4) : RatsColor.border))
                        .clipShape(Capsule())
                    }
                    .buttonStyle(RatsPlainButtonStyle())
                    .accessibilityLabel("\(position + 1) von \(highlights.count): \(highlight.title)")
                    .accessibilityAddTraits(active ? [.isSelected] : [])
                    .id(position)
                }
            }
    }

    // MARK: Liste (ohne Aufnahmen)

    private var list: some View {
        VStack(alignment: .leading, spacing: 10) {
            ForEach(highlights) { highlight in
                Button { open(highlight.url) } label: {
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

    private var footer: some View {
        HStack(spacing: 12) {
            // Mit Bühne trägt DEREN Hauptknopf das Wegräumen — zwei „Alles
            // klar" wären der Schnellausstieg, der die Karte wirkungslos machte.
            if !staged {
                Button(action: onDone) { buttonLabel("Alles klar", .check, iconFirst: true) }
                    .buttonStyle(PrimaryButtonStyle())
            }
            Button { model.handle(route: .web(model.api.url(forPath: "/changelog"))) } label: {
                Text(changelogLabel)
                    .font(RatsFont.body(13))
                    .underline()
                    .foregroundStyle(RatsColor.secondary)
            }
            .buttonStyle(RatsPlainButtonStyle())
        }
    }

    /// „dieser Version" stimmt nur, wenn es wirklich eine ist.
    private var changelogLabel: String {
        if state.olderCount > 0 {
            return "Alle Änderungen — auch \(state.olderCount) ältere Version\(state.olderCount == 1 ? "" : "en")"
        }
        return state.releases.count > 1 ? "Alle Änderungen im Einzelnen" : "Alle Änderungen dieser Version"
    }

    // MARK: Steuerung

    private func buttonLabel(_ title: String, _ glyph: RatsGlyph, iconFirst: Bool = false) -> some View {
        HStack(spacing: 6) {
            if iconFirst { RatsIcon(glyph, size: 14) }
            Text(title)
            if !iconFirst { RatsIcon(glyph, size: 14) }
        }
    }

    private func show(_ target: Int) {
        let count = highlights.count
        guard count > 0 else { return }
        let next = ((target % count) + count) % count
        index = next
        seen.insert(next)
    }

    /// „Weiter" springt zur nächsten Station, die noch NICHT abgehakt ist —
    /// wer über die Reiter gesprungen ist, bekommt trotzdem jede Neuerung
    /// einmal zu sehen, statt am Ende in einer Schleife zu landen.
    private func next() {
        let count = highlights.count
        for step in 1...max(count, 1) {
            let candidate = (index + step) % count
            if !seen.contains(candidate) { return show(candidate) }
        }
        show(index + 1)
    }

    /// Derselbe Weg wie Push und Mail: Der App-Pfad des Highlights wird zur Route.
    private func open(_ path: String) {
        model.handle(pushPath: path)
    }
}

// MARK: - Medium

/// Clip oder Bild. Ein Clip läuft stumm in Schleife und startet beim Blättern
/// von vorn; unter dem Clip liegt sein Standbild, bis das erste Bild da ist.
/// Wer Bewegung abgeschaltet hat, sieht nur das Standbild — dieselbe Regel
/// wie im Web.
private struct ReleaseMediaView: View {
    let media: ReleaseMedia
    let resolve: (String) -> URL
    let reduceMotion: Bool

    var body: some View {
        ZStack {
            RemoteImage(url: resolve(media.isVideo ? (media.poster ?? media.src) : media.src))
            if media.isVideo, !reduceMotion {
                LoopingVideo(url: resolve(media.src))
            }
        }
        .clipped()
    }
}

private struct RemoteImage: View {
    let url: URL

    var body: some View {
        AsyncImage(url: url) { phase in
            switch phase {
            case .success(let image):
                image.resizable().scaledToFill()
            default:
                Color.clear
            }
        }
    }
}

/// Ein stummer, endlos laufender Clip ohne Steuerung — `VideoPlayer` brächte
/// Regler mit, und ein Regler auf einer Karte lädt zum Bedienen ein statt
/// zum Zusehen.
private struct LoopingVideo: UIViewRepresentable {
    let url: URL

    func makeUIView(context: Context) -> LoopingPlayerView {
        let view = LoopingPlayerView()
        view.play(url)
        return view
    }

    func updateUIView(_ view: LoopingPlayerView, context: Context) {
        if view.url != url { view.play(url) }
    }

    static func dismantleUIView(_ view: LoopingPlayerView, coordinator: ()) {
        view.stop()
    }
}

final class LoopingPlayerView: UIView {
    override class var layerClass: AnyClass { AVPlayerLayer.self }

    private var playerLayer: AVPlayerLayer { layer as! AVPlayerLayer }
    private var player: AVQueuePlayer?
    private var looper: AVPlayerLooper?
    private(set) var url: URL?

    func play(_ url: URL) {
        self.url = url
        let player = AVQueuePlayer()
        player.isMuted = true
        player.preventsDisplaySleepDuringVideoPlayback = false
        looper = AVPlayerLooper(player: player, templateItem: AVPlayerItem(url: url))
        playerLayer.player = player
        playerLayer.videoGravity = .resizeAspectFill
        self.player = player
        player.play()
    }

    func stop() {
        player?.pause()
        looper = nil
        player = nil
        playerLayer.player = nil
    }
}
