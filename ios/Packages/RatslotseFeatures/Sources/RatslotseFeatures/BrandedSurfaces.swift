import RatslotseDesign
import SwiftUI

struct RatsSectionPanel<Content: View>: View {
    let title: String
    let detail: String?
    let symbol: RatsGlyph?
    @ViewBuilder let content: Content

    init(
        _ title: String,
        detail: String? = nil,
        symbol: RatsGlyph? = nil,
        @ViewBuilder content: () -> Content
    ) {
        self.title = title
        self.detail = detail
        self.symbol = symbol
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            HStack(alignment: .top, spacing: 10) {
                if let symbol {
                    RatsIcon(symbol, size: 14)
                        .foregroundStyle(RatsColor.primary)
                        .frame(width: 30, height: 30)
                        .background(RatsColor.primary.opacity(0.08))
                        .clipShape(RoundedRectangle(cornerRadius: 9, style: .continuous))
                        .accessibilityHidden(true)
                }
                VStack(alignment: .leading, spacing: 3) {
                    Text(title)
                        .font(RatsFont.title(18))
                        .foregroundStyle(RatsColor.text)
                    if let detail {
                        Text(detail)
                            .font(RatsFont.body(12))
                            .foregroundStyle(RatsColor.secondary)
                            .lineSpacing(2)
                    }
                }
                Spacer(minLength: 0)
            }
            content
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .ratsCard()
    }
}

struct RatsLabeledField<Content: View>: View {
    let label: String
    let hint: String?
    @ViewBuilder let content: Content

    init(label: String, hint: String? = nil, @ViewBuilder content: () -> Content) {
        self.label = label
        self.hint = hint
        self.content = content()
    }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack(alignment: .firstTextBaseline) {
                Text(label)
                    .foregroundStyle(RatsColor.bodyText)
                Spacer(minLength: 8)
                if let hint {
                    Text(hint)
                        .foregroundStyle(RatsColor.muted)
                }
            }
            .font(RatsFont.body(11, weight: .semibold))

            content
                .font(RatsFont.body(15))
                .foregroundStyle(RatsColor.text)
                .padding(.horizontal, 12)
                .frame(minHeight: 46)
                .background(RatsColor.stage)
                .overlay(
                    RoundedRectangle(cornerRadius: 10, style: .continuous)
                        .stroke(RatsColor.border)
                )
                .clipShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
        }
    }
}

struct RatsSettingsRow<Content: View>: View {
    let title: String
    let detail: String?
    let symbol: RatsGlyph
    @ViewBuilder let content: Content

    init(
        _ title: String,
        detail: String? = nil,
        symbol: RatsGlyph,
        @ViewBuilder content: () -> Content
    ) {
        self.title = title
        self.detail = detail
        self.symbol = symbol
        self.content = content()
    }

    var body: some View {
        HStack(alignment: .center, spacing: 11) {
            RatsIcon(symbol, size: 13)
                .foregroundStyle(RatsColor.primary)
                .frame(width: 28, height: 28)
                .background(RatsColor.primary.opacity(0.08))
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(RatsFont.body(14, weight: .semibold))
                    .foregroundStyle(RatsColor.text)
                if let detail {
                    Text(detail)
                        .font(RatsFont.body(11))
                        .foregroundStyle(RatsColor.secondary)
                        .lineLimit(2)
                }
            }
            Spacer(minLength: 8)
            content
        }
        .frame(maxWidth: .infinity, minHeight: 44, alignment: .leading)
        .contentShape(Rectangle())
    }
}

/// Die drei Zustände, die jede Liste hat — und in allen dreien wohnt Lotti
/// (Designdoc „iOS Charakter", 5c): links das Sprite auf einer weichen
/// Tönung, rechts Kicker, Titel, Text. Leer- und Ladezustände sind die
/// häufigsten Screens einer App mit Verzugsdaten; wer Lotti dort trifft,
/// kennt sie nach einer Woche — ohne dass ein Alltagsscreen umgebaut wurde.
struct RatsStatePortrait: View {
    let animation: LottiAnimation
    var tint: Color = RatsColor.primary

    var body: some View {
        ZStack {
            Circle().fill(tint.opacity(0.08))
            LottiSpriteView(animation: animation)
                .padding(3)
        }
        .frame(width: 58, height: 58)
        .accessibilityHidden(true)
    }
}

struct RatsStateKicker: View {
    let text: String
    var color: Color = RatsColor.muted

    var body: some View {
        Text(text.uppercased())
            .font(RatsFont.mono(9))
            .tracking(0.9)
            .foregroundStyle(color)
    }
}

struct RatsEmptyState: View {
    let title: String
    let message: String
    let symbol: RatsGlyph
    /// Lotti schläft, wo nichts ist — ein leerer Zustand ist kein Fehler.
    var animation: LottiAnimation = .sleeping

    var body: some View {
        HStack(alignment: .center, spacing: 14) {
            RatsStatePortrait(animation: animation)
            VStack(alignment: .leading, spacing: 3) {
                RatsStateKicker(text: "Leer")
                Text(title)
                    .font(RatsFont.body(14, weight: .bold))
                    .foregroundStyle(RatsColor.text)
                Text(message)
                    .font(RatsFont.body(12))
                    .foregroundStyle(RatsColor.secondary)
                    .lineSpacing(2)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .ratsCard()
        .accessibilityElement(children: .combine)
    }
}

struct RatsLoadingState: View {
    let message: String

    var body: some View {
        HStack(alignment: .center, spacing: 14) {
            RatsStatePortrait(animation: .juggling)
            VStack(alignment: .leading, spacing: 3) {
                RatsStateKicker(text: "Laden")
                Text(message)
                    .font(RatsFont.body(14, weight: .bold))
                    .foregroundStyle(RatsColor.text)
                RatsLoadingBar()
                    .padding(.top, 6)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
        }
        .frame(maxWidth: .infinity, minHeight: 96)
        .ratsCard()
        .accessibilityElement(children: .combine)
    }
}

/// Ein Balken, der langsam hin und her gleitet — 1,4 s je Richtung, keine
/// Dauer-Unruhe im Blickfeld; bei reduzierter Bewegung steht er still.
private struct RatsLoadingBar: View {
    @State private var toRight = false
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        GeometryReader { geometry in
            ZStack(alignment: .leading) {
                Capsule().fill(RatsColor.separator)
                Capsule()
                    .fill(RatsColor.primary)
                    .frame(width: geometry.size.width * 0.38)
                    .offset(x: toRight ? geometry.size.width * 0.62 : 0)
            }
        }
        .frame(height: 4)
        .onAppear {
            guard !reduceMotion else { return }
            withAnimation(.easeInOut(duration: 1.4).repeatForever(autoreverses: true)) { toRight = true }
        }
    }
}

struct RatsInlineLoadingState: View {
    let message: String
    var animation: LottiAnimation = .juggling

    var body: some View {
        HStack(spacing: 10) {
            LottiSpriteView(animation: animation)
                .frame(width: 46, height: 46)
            Text(message)
                .font(RatsFont.body(12, weight: .medium))
                .foregroundStyle(RatsColor.secondary)
            Spacer(minLength: 0)
        }
        .frame(minHeight: 54)
        .accessibilityElement(children: .combine)
    }
}

struct RatsModalIntro: View {
    let kicker: String
    let title: String
    let message: String
    let symbol: RatsGlyph

    var body: some View {
        HStack(alignment: .top, spacing: 14) {
            RatsIcon(symbol, size: 22)
                .foregroundStyle(RatsColor.primaryText)
                .frame(width: 52, height: 52)
                .background(RatsColor.primary)
                .clipShape(RoundedRectangle(cornerRadius: 15, style: .continuous))
                .accessibilityHidden(true)
            VStack(alignment: .leading, spacing: 5) {
                Text(kicker.uppercased())
                    .font(RatsFont.mono(9, weight: .semibold))
                    .tracking(1)
                    .foregroundStyle(RatsColor.signal)
                Text(title)
                    .font(RatsFont.title(26))
                    .foregroundStyle(RatsColor.text)
                Text(message)
                    .font(RatsFont.body(13))
                    .foregroundStyle(RatsColor.secondary)
                    .lineSpacing(2)
            }
            Spacer(minLength: 0)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

struct RatsSheetHeader: View {
    let title: String
    let leadingTitle: String?
    let leadingAction: (() -> Void)?
    let trailingTitle: String?
    let trailingAction: (() -> Void)?

    init(
        _ title: String,
        leadingTitle: String? = nil,
        leadingAction: (() -> Void)? = nil,
        trailingTitle: String? = nil,
        trailingAction: (() -> Void)? = nil
    ) {
        self.title = title
        self.leadingTitle = leadingTitle
        self.leadingAction = leadingAction
        self.trailingTitle = trailingTitle
        self.trailingAction = trailingAction
    }

    var body: some View {
        HStack(spacing: 10) {
            action(title: leadingTitle, action: leadingAction)
            Spacer(minLength: 4)
            Text(title)
                .font(RatsFont.title(17))
                .foregroundStyle(RatsColor.text)
                .lineLimit(1)
                .minimumScaleFactor(0.76)
                .allowsTightening(true)
            Spacer(minLength: 4)
            action(title: trailingTitle, action: trailingAction)
        }
        .padding(.horizontal, 18)
        .padding(.vertical, 10)
        .background(RatsColor.page)
        .overlay(alignment: .bottom) {
            Rectangle().fill(RatsColor.separator).frame(height: 1)
        }
    }

    @ViewBuilder
    private func action(
        title: String?,
        action: (() -> Void)?
    ) -> some View {
        if let title, let action {
            Button(action: action) {
                Text(title)
                    .font(RatsFont.body(11.5, weight: .semibold))
                    .foregroundStyle(RatsColor.primary)
                    .lineLimit(1)
                    .minimumScaleFactor(0.78)
                    .allowsTightening(true)
                    .padding(.horizontal, 11)
                    .frame(width: 104, height: 34)
                    .background(RatsColor.primary.opacity(0.08))
                    .overlay(Capsule().stroke(RatsColor.primary.opacity(0.16)))
                    .clipShape(Capsule())
            }
            .buttonStyle(RatsSheetHeaderButtonStyle())
        } else {
            Color.clear.frame(width: 104, height: 34)
        }
    }
}

private struct RatsSheetHeaderButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .scaleEffect(configuration.isPressed ? 0.96 : 1)
            .opacity(configuration.isPressed ? 0.72 : 1)
            .animation(.easeOut(duration: 0.12), value: configuration.isPressed)
    }
}

extension View {
    @ViewBuilder
    func ratsLargeSheet() -> some View {
        if #available(iOS 18.0, *) {
            presentationSizing(.page)
        } else {
            presentationDetents([.large])
        }
    }
}
