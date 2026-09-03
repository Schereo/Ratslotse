import SwiftUI

public struct MonoKicker: View {
    private let text: String
    private let trailing: String?

    public init(_ text: String, trailing: String? = nil) {
        self.text = text
        self.trailing = trailing
    }

    public var body: some View {
        HStack(alignment: .firstTextBaseline) {
            Text(text.uppercased())
            Spacer(minLength: 8)
            if let trailing { Text(trailing) }
        }
        .font(RatsFont.mono())
        .tracking(1.05)
        .foregroundStyle(RatsColor.muted)
    }
}

public struct Pill: View {
    private let text: String
    private let symbol: RatsGlyph?

    public init(_ text: String, symbol: RatsGlyph? = nil) {
        self.text = text
        self.symbol = symbol
    }

    public var body: some View {
        HStack(spacing: 5) {
            if let symbol { RatsIcon(symbol, size: 12) }
            Text(text)
        }
        .font(RatsFont.body(12, weight: .semibold))
        .foregroundStyle(RatsColor.primary)
        .padding(.horizontal, 10)
        .padding(.vertical, 6)
        .background(RatsColor.primary.opacity(0.06))
        .overlay(Capsule().stroke(RatsColor.primary.opacity(0.24)))
        .clipShape(Capsule())
    }
}

public struct OutcomeBadge: View {
    private let outcome: String

    public init(_ outcome: String) { self.outcome = outcome }

    public var body: some View {
        Text(label)
            .font(RatsFont.body(11, weight: .semibold))
            .foregroundStyle(foreground)
            .padding(.horizontal, 8)
            .padding(.vertical, 4)
            .background(background)
            .clipShape(Capsule())
    }

    private var label: String {
        switch outcome {
        case "accepted": "Angenommen"
        case "rejected": "Abgelehnt"
        case "postponed": "Vertagt"
        case "noted": "Zur Kenntnis"
        case "no_decision": "Kein Beschluss"
        default: outcome.replacingOccurrences(of: "_", with: " ").capitalized
        }
    }

    private var foreground: Color {
        switch outcome {
        case "accepted": RatsColor.success
        case "rejected": RatsColor.danger
        case "postponed": RatsColor.warning
        default: RatsColor.secondary
        }
    }

    private var background: Color {
        switch outcome {
        case "accepted": RatsColor.successTint
        case "rejected": RatsColor.dangerTint
        case "postponed": RatsColor.warningTint
        default: RatsColor.separator
        }
    }
}

/// „einstimmig" bzw. „mehrheitlich" — gespeichert wird der englische Wert.
/// Freie Protokoll-Formulierungen („einstimmig bei einer Enthaltung") stehen
/// so in der Quelle und kommen unverändert durch.
public func voteLabel(_ vote: String) -> String {
    switch vote {
    case "unanimous": "einstimmig"
    case "majority": "mehrheitlich"
    default: vote
    }
}

public struct SourceRow: View {
    private let number: Int
    private let title: String
    private let meta: String?

    public init(number: Int, title: String, meta: String? = nil) {
        self.number = number
        self.title = title
        self.meta = meta
    }

    public var body: some View {
        HStack(spacing: RatsSpacing.sm) {
            FootnoteChip(number: number)
            VStack(alignment: .leading, spacing: 2) {
                Text(title).font(RatsFont.body(13, weight: .semibold)).lineLimit(2)
                if let meta { Text(meta).font(RatsFont.mono(9)).foregroundStyle(RatsColor.muted) }
            }
            Spacer(minLength: 0)
            RatsIcon(.chevronRight, size: 12).foregroundStyle(RatsColor.muted)
        }
        .foregroundStyle(RatsColor.text)
        .contentShape(Rectangle())
    }
}

public struct FootnoteChip: View {
    private let number: Int
    private let active: Bool

    public init(number: Int, active: Bool = false) {
        self.number = number
        self.active = active
    }

    public var body: some View {
        Text("\(number)")
            .font(RatsFont.body(10, weight: .bold))
            .foregroundStyle(active ? Color.white : RatsColor.primary)
            .frame(width: 18, height: 18)
            .background(active ? RatsColor.primary : RatsColor.primary.opacity(0.10))
            .clipShape(RoundedRectangle(cornerRadius: 4))
    }
}

public struct QuestionComposer: View {
    @Binding private var text: String
    private let isSending: Bool
    private let action: () -> Void

    public init(text: Binding<String>, isSending: Bool, action: @escaping () -> Void) {
        _text = text
        self.isSending = isSending
        self.action = action
    }

    public var body: some View {
        HStack(spacing: 9) {
            RatsIcon(.sparkles, size: 16)
                .foregroundStyle(RatsColor.signal)
            TextField("Was möchtest du über den Rat wissen?", text: $text, axis: .vertical)
                .font(RatsFont.body())
                .lineLimit(1...4)
                .submitLabel(.send)
                .onSubmit(action)
            Button(action: action) {
                RatsIcon(isSending ? .square : .arrowUp, size: 15)
                    .foregroundStyle(RatsColor.primaryText)
                    .frame(width: 38, height: 38)
                    .background(RatsColor.primary.opacity(text.trimmingCharacters(in: .whitespaces).isEmpty ? 0.35 : 1))
                    .clipShape(Circle())
            }
            .disabled(text.trimmingCharacters(in: .whitespacesAndNewlines).count < 4 && !isSending)
        }
        .padding(.horizontal, 12)
        .padding(.vertical, 7)
        .background(RatsColor.card)
        .overlay(RoundedRectangle(cornerRadius: 16).stroke(RatsColor.border))
        .clipShape(RoundedRectangle(cornerRadius: 16))
    }
}
