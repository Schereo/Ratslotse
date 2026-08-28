import RatslotseAPI
import RatslotseDesign
import SwiftUI

struct BadgeCollectionCard: View {
    let model: AppModel
    @Environment(\.horizontalSizeClass) private var horizontalSizeClass

    var body: some View {
        RatsSectionPanel(
            "Deine Lotsen-Abzeichen",
            detail: "Fürs Erkunden – ohne Rangliste und ohne verlorene Serien.",
            symbol: "medal.fill"
        ) {
            if let snapshot = model.badgeSnapshot {
                HStack(alignment: .firstTextBaseline, spacing: 8) {
                    Text("\(snapshot.earnedCount)")
                        .font(RatsFont.title(30))
                        .foregroundStyle(RatsColor.primary)
                        .contentTransition(.numericText())
                    Text("von \(snapshot.total) entdeckt")
                        .font(RatsFont.body(12, weight: .medium))
                        .foregroundStyle(RatsColor.secondary)
                    Spacer(minLength: 0)
                    if snapshot.earnedCount == snapshot.total {
                        Label("Komplett", systemImage: "checkmark.seal.fill")
                            .font(RatsFont.body(11, weight: .semibold))
                            .foregroundStyle(RatsColor.success)
                    }
                }

                LazyVGrid(columns: columns, alignment: .leading, spacing: 10) {
                    ForEach(snapshot.badges) { badge in
                        BadgeTile(badge: badge)
                    }
                }

                if let next = snapshot.next {
                    HStack(alignment: .top, spacing: 10) {
                        Image(systemName: "location.north.fill")
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundStyle(RatsColor.signal)
                            .frame(width: 28, height: 28)
                            .background(RatsColor.signal.opacity(0.09))
                            .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Als Nächstes: \(next.title)")
                                .font(RatsFont.body(12, weight: .semibold))
                                .foregroundStyle(RatsColor.text)
                            Text(next.hint)
                                .font(RatsFont.body(11))
                                .foregroundStyle(RatsColor.secondary)
                        }
                    }
                    .padding(.top, 2)
                }
            } else {
                HStack(spacing: 10) {
                    ProgressView().tint(RatsColor.primary)
                    Text("Sammlung wird geladen …")
                        .font(RatsFont.body(12, weight: .medium))
                        .foregroundStyle(RatsColor.secondary)
                }
                .frame(minHeight: 54)
            }
        }
        .task { await model.refreshBadges() }
    }

    private var columns: [GridItem] {
        Array(repeating: GridItem(.flexible(), spacing: 10), count: horizontalSizeClass == .regular ? 4 : 2)
    }
}

private struct BadgeTile: View {
    let badge: BadgeItem
    private var palette: BadgePalette { badgePalette(badge.id) }

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(alignment: .top) {
                BadgeMedallion(badgeID: badge.id, earned: badge.earned, size: 48)
                Spacer(minLength: 4)
                Image(systemName: badge.earned ? "sparkles" : "lock.fill")
                    .font(.system(size: 10, weight: .bold))
                    .foregroundStyle(badge.earned ? palette.accent : RatsColor.muted)
                    .frame(width: 25, height: 25)
                    .background(badge.earned ? palette.accent.opacity(0.11) : RatsColor.separator)
                    .clipShape(Circle())
            }

            Text(badge.title)
                .font(RatsFont.body(12, weight: .semibold))
                .foregroundStyle(badge.earned ? RatsColor.text : RatsColor.secondary)
                .lineLimit(2, reservesSpace: true)

            if let progress = badge.progress, !badge.earned {
                VStack(alignment: .leading, spacing: 4) {
                    GeometryReader { proxy in
                        ZStack(alignment: .leading) {
                            Capsule().fill(RatsColor.separator)
                            Capsule()
                                .fill(RatsColor.primary)
                                .frame(width: proxy.size.width * fraction(progress))
                        }
                    }
                    .frame(height: 4)
                    Text("\(progress.current)/\(progress.target)")
                        .font(RatsFont.mono(8, weight: .semibold))
                        .foregroundStyle(RatsColor.muted)
                }
            } else {
                Text(badge.earned ? "Entdeckt" : badge.hint)
                    .font(RatsFont.body(9, weight: badge.earned ? .semibold : .regular))
                    .foregroundStyle(badge.earned ? palette.accent : RatsColor.muted)
                    .lineLimit(2, reservesSpace: true)
            }
        }
        .padding(11)
        .frame(maxWidth: .infinity, minHeight: 140, alignment: .topLeading)
        .background {
            if badge.earned {
                LinearGradient(
                    colors: [palette.start.opacity(0.14), palette.end.opacity(0.055), RatsColor.card],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )
            } else {
                RatsColor.stage
            }
        }
        .overlay(alignment: .topLeading) {
            if badge.earned {
                LinearGradient(
                    colors: [Color.white.opacity(0.44), Color.clear],
                    startPoint: .top,
                    endPoint: .bottom
                )
                .frame(height: 44)
                .allowsHitTesting(false)
            }
        }
        .overlay(
            RoundedRectangle(cornerRadius: 14, style: .continuous)
                .stroke(
                    badge.earned
                        ? LinearGradient(colors: [palette.accent.opacity(0.58), palette.end.opacity(0.18)], startPoint: .topLeading, endPoint: .bottomTrailing)
                        : LinearGradient(colors: [RatsColor.border], startPoint: .top, endPoint: .bottom),
                    lineWidth: badge.earned ? 1.2 : 1
                )
        )
        .clipShape(RoundedRectangle(cornerRadius: 14, style: .continuous))
        .shadow(color: badge.earned ? palette.accent.opacity(0.11) : .clear, radius: 11, y: 5)
        .accessibilityElement(children: .combine)
        .accessibilityLabel("\(badge.title), \(badge.earned ? "entdeckt" : "noch gesperrt")")
        .accessibilityHint(badge.hint)
    }

    private func fraction(_ progress: BadgeProgress) -> CGFloat {
        guard progress.target > 0 else { return 0 }
        return min(1, max(0, CGFloat(progress.current) / CGFloat(progress.target)))
    }
}

struct BadgeCelebrationOverlay: View {
    let model: AppModel
    let badge: EarnedBadge
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        VStack {
            Spacer()
            HStack {
                Spacer()
                HStack(alignment: .center, spacing: 14) {
                    BadgeMedallion(badgeID: badge.id, earned: true, size: 62)

                    VStack(alignment: .leading, spacing: 4) {
                        MonoKicker("Abzeichen entdeckt")
                        Text(badge.title)
                            .font(RatsFont.title(22))
                            .foregroundStyle(RatsColor.text)
                        Text("Deine Sammlung liegt im Konto.")
                            .font(RatsFont.body(11))
                            .foregroundStyle(RatsColor.secondary)
                    }
                    Spacer(minLength: 4)
                    Button {
                        withAnimation(.snappy) { model.dismissBadgeCelebration() }
                    } label: {
                        Image(systemName: "xmark")
                            .font(.system(size: 12, weight: .bold))
                            .foregroundStyle(RatsColor.secondary)
                            .frame(width: 32, height: 32)
                            .background(RatsColor.stage)
                            .clipShape(Circle())
                    }
                    .accessibilityLabel("Abzeichen-Hinweis schließen")
                }
                .padding(14)
                .frame(maxWidth: 430)
                .background(.ultraThinMaterial)
                .background(RatsColor.card.opacity(0.76))
                .overlay(
                    RoundedRectangle(cornerRadius: 22, style: .continuous)
                        .stroke(RatsColor.warning.opacity(0.24))
                )
                .clipShape(RoundedRectangle(cornerRadius: 22, style: .continuous))
                .shadow(color: RatsColor.primary.opacity(0.16), radius: 22, y: 10)
            }
        }
        .padding(.horizontal, 14)
        .padding(.bottom, 92)
        .transition(.move(edge: .bottom).combined(with: .opacity))
        .task(id: badge.id) {
            try? await Task.sleep(for: .seconds(6))
            guard model.badgeCelebration?.id == badge.id else { return }
            if reduceMotion { model.dismissBadgeCelebration() }
            else { withAnimation(.snappy) { model.dismissBadgeCelebration() } }
        }
    }
}

private struct BadgeMedallion: View {
    let badgeID: String
    let earned: Bool
    let size: CGFloat

    private var palette: BadgePalette { badgePalette(badgeID) }

    var body: some View {
        ZStack {
            Circle()
                .fill(
                    earned
                        ? LinearGradient(colors: [palette.start, palette.end], startPoint: .topLeading, endPoint: .bottomTrailing)
                        : LinearGradient(colors: [RatsColor.muted.opacity(0.36), RatsColor.separator], startPoint: .topLeading, endPoint: .bottomTrailing)
                )
            Circle()
                .stroke(
                    LinearGradient(
                        colors: earned
                            ? [Color.white.opacity(0.92), palette.metal, palette.end.opacity(0.72)]
                            : [Color.white.opacity(0.35), RatsColor.muted.opacity(0.4)],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    ),
                    lineWidth: max(2, size * 0.065)
                )
                .padding(size * 0.055)
            Circle()
                .fill(Color.black.opacity(earned ? 0.10 : 0.03))
                .padding(size * 0.19)
            Image(systemName: badgeSymbol(badgeID))
                .font(.system(size: size * 0.34, weight: .bold))
                .foregroundStyle(earned ? Color.white : RatsColor.muted)
                .shadow(color: .black.opacity(earned ? 0.22 : 0), radius: 1, y: 1)
            if earned {
                Capsule()
                    .fill(Color.white.opacity(0.62))
                    .frame(width: size * 0.31, height: size * 0.075)
                    .rotationEffect(.degrees(-34))
                    .offset(x: -size * 0.17, y: -size * 0.22)
                Image(systemName: "sparkle")
                    .font(.system(size: size * 0.18, weight: .bold))
                    .foregroundStyle(palette.metal)
                    .shadow(color: palette.metal.opacity(0.7), radius: 4)
                    .offset(x: size * 0.37, y: -size * 0.31)
            }
        }
        .frame(width: size, height: size)
        .shadow(color: earned ? palette.accent.opacity(0.28) : .clear, radius: size * 0.15, y: size * 0.08)
        .accessibilityHidden(true)
    }
}

private struct BadgePalette {
    let start: Color
    let end: Color
    let accent: Color
    let metal: Color
}

private func badgePalette(_ id: String) -> BadgePalette {
    switch id {
    case "erste-frage":
        BadgePalette(start: Color(red: 0.13, green: 0.68, blue: 0.91), end: Color(red: 0.20, green: 0.25, blue: 0.74), accent: Color(red: 0.08, green: 0.45, blue: 0.76), metal: Color(red: 0.70, green: 0.92, blue: 1.00))
    case "themen-lotse":
        BadgePalette(start: Color(red: 0.98, green: 0.42, blue: 0.24), end: Color(red: 0.77, green: 0.16, blue: 0.48), accent: Color(red: 0.88, green: 0.23, blue: 0.32), metal: Color(red: 1.00, green: 0.83, blue: 0.55))
    case "quiz-serie":
        BadgePalette(start: Color(red: 0.99, green: 0.72, blue: 0.16), end: Color(red: 0.85, green: 0.35, blue: 0.08), accent: Color(red: 0.73, green: 0.39, blue: 0.04), metal: Color(red: 1.00, green: 0.94, blue: 0.61))
    case "kartograf":
        BadgePalette(start: Color(red: 0.16, green: 0.74, blue: 0.65), end: Color(red: 0.02, green: 0.42, blue: 0.60), accent: Color(red: 0.02, green: 0.50, blue: 0.55), metal: Color(red: 0.66, green: 1.00, blue: 0.88))
    case "analyst":
        BadgePalette(start: Color(red: 0.62, green: 0.39, blue: 0.94), end: Color(red: 0.26, green: 0.22, blue: 0.70), accent: Color(red: 0.44, green: 0.29, blue: 0.78), metal: Color(red: 0.88, green: 0.78, blue: 1.00))
    case "sitzungsgast":
        BadgePalette(start: Color(red: 0.10, green: 0.35, blue: 0.62), end: Color(red: 0.04, green: 0.13, blue: 0.27), accent: Color(red: 0.10, green: 0.38, blue: 0.65), metal: Color(red: 0.91, green: 0.74, blue: 0.34))
    case "fruehwarner":
        BadgePalette(start: Color(red: 0.99, green: 0.43, blue: 0.17), end: Color(red: 0.79, green: 0.10, blue: 0.13), accent: Color(red: 0.90, green: 0.25, blue: 0.10), metal: Color(red: 1.00, green: 0.84, blue: 0.53))
    case "kompass":
        BadgePalette(start: Color(red: 0.18, green: 0.48, blue: 0.91), end: Color(red: 0.15, green: 0.22, blue: 0.57), accent: Color(red: 0.18, green: 0.39, blue: 0.78), metal: Color(red: 0.56, green: 0.96, blue: 0.88))
    default:
        BadgePalette(start: RatsColor.primary, end: RatsColor.bodyText, accent: RatsColor.primary, metal: Color.white)
    }
}

private func badgeSymbol(_ id: String) -> String {
    switch id {
    case "erste-frage": "sparkles"
    case "themen-lotse": "tag.fill"
    case "quiz-serie": "trophy.fill"
    case "kartograf": "map.fill"
    case "analyst": "chart.bar.xaxis"
    case "sitzungsgast": "calendar.badge.clock"
    case "fruehwarner": "bell.badge.fill"
    case "kompass": "location.north.circle.fill"
    default: "medal.fill"
    }
}
