import AVFoundation
import RatslotseAPI
import RatslotseDesign
import SwiftUI

/// Der Story-Spieler zu „Neu bei Ratslotse" — Vollbild, auf Tipp einer
/// Video-Kachel (`ReleaseNewsCard`). Dieselbe Bedienung wie im Web
/// (`components/neuigkeiten-spieler.tsx`):
///
/// - oben je Clip ein Balken, der **mit der Videozeit** läuft;
/// - Tipp links/rechts blättert, Tipp in die Mitte hält an, seitwärts wischen
///   blättert, **nach unten wischen schließt**;
/// - unten Titel und Text, „‹ Zurück", „<Feature> ausprobieren →" (führt zum
///   Feature und schließt den Spieler), „Weiter ›".
///
/// **Am Ende eines Clips kommt der nächste** — nur wenn Bewegung nicht
/// abgeschaltet ist. Ein Mensch hat den Spieler geöffnet, um die Clips zu
/// sehen; gewechselt wird erst, wenn der laufende zu Ende ist, und die Balken
/// kündigen es an (DESIGNSPRACHE §7, „Story-Spieler"). Mit „Bewegung
/// reduzieren" startet kein Clip von selbst (Standbild + Abspielknopf), und
/// am Ende schaltet nichts weiter.
///
/// **Immer dunkel**: die Kinofläche eines Videoplayers, keine dunkle Karte.
struct ReleaseStoryPlayer: View {
    let sequence: [ReleaseHighlight]
    let start: Int
    /// Ein Nebenbei-Clip steht allein: kein „2 von 3", kein Weiterschalten.
    let aside: Bool
    let resolve: (String) -> URL
    let onSeen: (ReleaseHighlight) -> Void
    let onTry: (ReleaseHighlight) -> Void

    @Environment(\.dismiss) private var dismiss
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var index: Int
    @State private var playback = StoryPlayback()
    @State private var dragOffset: CGFloat = 0

    /// Die dunkle Seitenfarbe hsl(213 50% 7%), deckend (DESIGNSPRACHE §5).
    static let stage = ReleaseTileColor.rgb(0x09111B)

    init(
        sequence: [ReleaseHighlight], start: Int, aside: Bool,
        resolve: @escaping (String) -> URL,
        onSeen: @escaping (ReleaseHighlight) -> Void,
        onTry: @escaping (ReleaseHighlight) -> Void
    ) {
        self.sequence = sequence
        self.start = start
        self.aside = aside
        self.resolve = resolve
        self.onSeen = onSeen
        self.onTry = onTry
        _index = State(initialValue: min(max(start, 0), max(sequence.count - 1, 0)))
    }

    private var current: ReleaseHighlight { sequence[index] }
    private var tint: Color { ReleaseTileColor.color(current.color) }
    private var isLast: Bool { index >= sequence.count - 1 }

    var body: some View {
        VStack(spacing: 0) {
            header
            stage
            footer
        }
        .padding(.horizontal, 16)
        .padding(.top, 8)
        .padding(.bottom, 12)
        .background(Self.stage.ignoresSafeArea())
        .offset(y: dragOffset)
        .opacity(dragOffset > 0 ? max(0.5, 1 - dragOffset / 700) : 1)
        .simultaneousGesture(swipe)
        .preferredColorScheme(.dark)
        .onAppear { load() }
        .onChange(of: index) { _, _ in load() }
        .onDisappear { playback.stop() }
    }

    // MARK: Kopf

    private var header: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 6) {
                ForEach(Array(sequence.enumerated()), id: \.offset) { position, _ in
                    Capsule()
                        .fill(.white.opacity(0.25))
                        .overlay(alignment: .leading) {
                            Capsule()
                                .fill(.white)
                                .scaleEffect(x: fraction(for: position), y: 1, anchor: .leading)
                        }
                        .frame(height: 4)
                        .clipShape(Capsule())
                }
            }
            .accessibilityHidden(true)
            HStack(alignment: .top) {
                Text(aside ? "Außerdem · \(current.title)" : "\(index + 1) von \(sequence.count) · \(current.title)")
                    .font(RatsFont.body(15, weight: .semibold))
                    .foregroundStyle(.white)
                    .fixedSize(horizontal: false, vertical: true)
                    .accessibilityAddTraits(.isHeader)
                Spacer(minLength: 8)
                Button { dismiss() } label: {
                    RatsIcon(.circleX, size: 24)
                        .foregroundStyle(.white)
                        .frame(width: 44, height: 44)
                        .contentShape(Rectangle())
                }
                .buttonStyle(RatsPlainButtonStyle())
                .padding(.top, -10)
                .padding(.trailing, -10)
                .accessibilityLabel("Schließen")
            }
        }
    }

    private func fraction(for position: Int) -> CGFloat {
        if position < index { return 1 }
        if position > index { return 0 }
        return CGFloat(playback.progress)
    }

    // MARK: Bühne

    private var stage: some View {
        let media = current.media
        let ratio = media?.aspectRatio ?? 16.0 / 9.0
        return ZStack {
            if let media {
                // Unter dem Clip sein Standbild, bis das erste Bild läuft —
                // und bei „Bewegung reduzieren", solange niemand abspielt.
                AsyncImage(url: resolve(media.poster ?? media.src)) { phase in
                    if case .success(let image) = phase { image.resizable().scaledToFit() } else { Color.black }
                }
                if media.isVideo {
                    StoryVideoView(player: playback.player)
                        .opacity(playback.hasStarted ? 1 : 0)
                }
            }
            tapZones
            if media?.isVideo == true, !playback.isPlaying { bigPlayButton }
        }
        .aspectRatio(ratio, contentMode: .fit)
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .shadow(color: .black.opacity(0.6), radius: 30, y: 20)
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(.vertical, 12)
        .accessibilityElement(children: .ignore)
        .accessibilityLabel(media?.alt ?? current.title)
        .accessibilityAddTraits(.startsMediaSession)
        .accessibilityAction(named: playback.isPlaying ? "Anhalten" : "Abspielen") { playback.toggle() }
    }

    /// Links zurück, rechts weiter, die Mitte hält an. Die Knöpfe unten
    /// können dasselbe — die Zonen sind die Abkürzung für den Daumen.
    private var tapZones: some View {
        GeometryReader { proxy in
            HStack(spacing: 0) {
                Color.clear.contentShape(Rectangle())
                    .frame(width: proxy.size.width * 0.3)
                    .onTapGesture { previous() }
                Color.clear.contentShape(Rectangle())
                    .onTapGesture { playback.toggle() }
                Color.clear.contentShape(Rectangle())
                    .frame(width: proxy.size.width * 0.3)
                    .onTapGesture { advanceByUser() }
            }
        }
        .accessibilityHidden(true)
    }

    private var bigPlayButton: some View {
        Button { playback.toggle() } label: {
            ZStack {
                Circle().fill(.white.opacity(0.94))
                RatsIcon(playback.ended ? .rotateCcw : .play, size: 28)
                    .foregroundStyle(tint)
                    .offset(x: playback.ended ? 0 : 2)
            }
            .frame(width: 72, height: 72)
            .shadow(color: .black.opacity(0.4), radius: 14, y: 8)
        }
        .buttonStyle(RatsPlainButtonStyle())
        .accessibilityLabel(playback.ended ? "Noch einmal ansehen" : "Abspielen")
    }

    // MARK: Fuß

    private var footer: some View {
        VStack(alignment: .leading, spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text(current.title)
                    .font(RatsFont.title(20, weight: .bold))
                    .foregroundStyle(.white)
                    .fixedSize(horizontal: false, vertical: true)
                Text(current.text)
                    .font(RatsFont.body(14.5))
                    .foregroundStyle(.white.opacity(0.86))
                    .lineSpacing(2)
                    .fixedSize(horizontal: false, vertical: true)
            }
            // Der Weg zum Feature allein in der ersten Zeile — drei Knöpfe
            // nebeneinander brachen „Mein Viertel ausprobieren" um.
            Button { playback.stop(); onTry(current) } label: {
                HStack(spacing: 8) {
                    Text(current.action ?? "Ausprobieren")
                    RatsIcon(.arrowRight, size: 16)
                }
                .font(RatsFont.body(16, weight: .bold))
                .foregroundStyle(.white)
                .frame(maxWidth: .infinity, minHeight: 50)
                .background(tint)
                .clipShape(Capsule())
            }
            .buttonStyle(RatsPlainButtonStyle())
            HStack(spacing: 10) {
                if !aside {
                    Button(action: previous) {
                        quietLabel { RatsIcon(.chevronLeft, size: 18); Text("Zurück") }
                    }
                    .buttonStyle(RatsPlainButtonStyle())
                    .disabled(index == 0)
                    .opacity(index == 0 ? 0.4 : 1)
                }
                Button { isLast ? dismiss() : advanceByUser() } label: {
                    quietLabel {
                        Text(isLast ? "Fertig" : "Weiter")
                        if !isLast { RatsIcon(.chevronRight, size: 18) }
                    }
                }
                .buttonStyle(RatsPlainButtonStyle())
            }
        }
    }

    private func quietLabel<C: View>(@ViewBuilder _ content: () -> C) -> some View {
        HStack(spacing: 4) { content() }
            .font(RatsFont.body(16, weight: .semibold))
            .foregroundStyle(.white)
            .frame(maxWidth: .infinity, minHeight: 48)
            .background(.white.opacity(0.14))
            .clipShape(Capsule())
    }

    // MARK: Gesten

    /// Nach unten wischen schließt, seitwärts blättert.
    private var swipe: some Gesture {
        DragGesture(minimumDistance: 24)
            .onChanged { value in
                guard !reduceMotion else { return }
                let dy = value.translation.height
                if dy > 0, dy > abs(value.translation.width) { dragOffset = dy * 0.6 }
            }
            .onEnded { value in
                let dx = value.translation.width, dy = value.translation.height
                withAnimation(reduceMotion ? nil : RatsMotion.flow) { dragOffset = 0 }
                if dy > 100, dy > abs(dx) { dismiss(); return }
                if abs(dx) > 60, abs(dx) > abs(dy) { dx < 0 ? advanceByUser() : previous() }
            }
    }

    // MARK: Steuerung

    private func load() {
        onSeen(current)
        guard let media = current.media, media.isVideo else { playback.stop(); return }
        playback.onEnd = { reachedEnd() }
        playback.load(resolve(media.src), autoplay: !reduceMotion)
    }

    private func reachedEnd() {
        if !reduceMotion, !aside, !isLast { index += 1 }
    }

    private func advanceByUser() {
        if !isLast { index += 1 }
    }

    private func previous() {
        if index > 0 { index -= 1 }
    }
}

// MARK: - Wiedergabe

/// Ein `AVPlayer` samt Fortschritt und Ende — stumm, ohne Systemregler.
@MainActor
@Observable
final class StoryPlayback {
    let player = AVPlayer()
    private(set) var progress: Double = 0
    private(set) var isPlaying = false
    private(set) var ended = false
    /// Hat der Clip schon ein Bild gezeigt? Bis dahin steht das Standbild.
    private(set) var hasStarted = false
    var onEnd: (() -> Void)?

    @ObservationIgnored private var timeObserver: Any?
    @ObservationIgnored private var endObserver: NSObjectProtocol?

    init() {
        player.isMuted = true
        player.preventsDisplaySleepDuringVideoPlayback = true
    }

    func load(_ url: URL, autoplay: Bool) {
        removeEndObserver()
        let item = AVPlayerItem(url: url)
        player.replaceCurrentItem(with: item)
        progress = 0
        ended = false
        hasStarted = false
        endObserver = NotificationCenter.default.addObserver(
            forName: .AVPlayerItemDidPlayToEndTime, object: item, queue: .main
        ) { [weak self] _ in
            MainActor.assumeIsolated { self?.finish() }
        }
        if timeObserver == nil {
            timeObserver = player.addPeriodicTimeObserver(
                forInterval: CMTime(value: 1, timescale: 30), queue: .main
            ) { [weak self] time in
                MainActor.assumeIsolated { self?.tick(time) }
            }
        }
        if autoplay { play() } else { player.pause(); isPlaying = false }
    }

    func toggle() {
        if isPlaying {
            player.pause()
            isPlaying = false
        } else {
            if ended {
                player.seek(to: .zero)
                ended = false
            }
            play()
        }
    }

    func stop() {
        player.pause()
        isPlaying = false
        removeEndObserver()
        if let timeObserver { player.removeTimeObserver(timeObserver) }
        timeObserver = nil
        onEnd = nil
    }

    private func play() {
        player.play()
        isPlaying = true
        hasStarted = true
    }

    private func tick(_ time: CMTime) {
        guard let duration = player.currentItem?.duration, duration.isNumeric, duration.seconds > 0 else { return }
        progress = min(1, max(0, time.seconds / duration.seconds))
    }

    private func finish() {
        progress = 1
        isPlaying = false
        ended = true
        onEnd?()
    }

    private func removeEndObserver() {
        if let endObserver { NotificationCenter.default.removeObserver(endObserver) }
        endObserver = nil
    }
}

/// Die Bildfläche des Clips — `AVPlayerLayer` ohne Regler (`VideoPlayer`
/// brächte die Systemsteuerung mit, die hier die Tippzonen verdeckte).
private struct StoryVideoView: UIViewRepresentable {
    let player: AVPlayer

    func makeUIView(context: Context) -> PlayerLayerView {
        let view = PlayerLayerView()
        view.playerLayer.player = player
        view.playerLayer.videoGravity = .resizeAspect
        return view
    }

    func updateUIView(_ view: PlayerLayerView, context: Context) {
        if view.playerLayer.player !== player { view.playerLayer.player = player }
    }
}

final class PlayerLayerView: UIView {
    override class var layerClass: AnyClass { AVPlayerLayer.self }
    var playerLayer: AVPlayerLayer { layer as! AVPlayerLayer }
}
