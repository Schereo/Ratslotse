import SwiftUI
import UIKit

public enum RatsSpacing {
    public static let xs: CGFloat = 5
    public static let sm: CGFloat = 8
    public static let md: CGFloat = 12
    public static let lg: CGFloat = 18
    public static let xl: CGFloat = 24
    public static let section: CGFloat = 28
}

public enum RatsRadius {
    public static let chip: CGFloat = 999
    public static let card: CGFloat = 14
    public static let panel: CGFloat = 18
    public static let button: CGFloat = 11
}

public enum RatsFont {
    public static func body(_ size: CGFloat = 15, weight: Font.Weight = .regular) -> Font {
        .custom("Inter", size: size, relativeTo: .body).weight(weight)
    }

    public static func title(_ size: CGFloat = 28, weight: Font.Weight = .bold) -> Font {
        .custom("Bricolage Grotesque", size: size, relativeTo: .title).weight(weight)
    }

    public static func mono(_ size: CGFloat = 10, weight: Font.Weight = .medium) -> Font {
        .custom("IBM Plex Mono", size: size, relativeTo: .caption).weight(weight)
    }
}

public enum RatsDate {
    public static func short(_ raw: String?) -> String? {
        guard let date = date(raw) else { return raw }
        return date.formatted(
            .dateTime
                .locale(Locale(identifier: "de_DE"))
                .day()
                .month(.abbreviated)
                .year()
        )
    }

    public static func weekday(_ raw: String?) -> String? {
        guard let date = date(raw) else { return raw }
        return date.formatted(
            .dateTime
                .locale(Locale(identifier: "de_DE"))
                .weekday(.abbreviated)
                .day()
                .month(.abbreviated)
        )
    }

    private static func date(_ raw: String?) -> Date? {
        guard let raw, raw.count >= 10 else { return nil }
        let parts = raw.prefix(10).split(separator: "-").compactMap { Int($0) }
        guard parts.count == 3 else { return nil }
        return Calendar(identifier: .gregorian).date(
            from: DateComponents(year: parts[0], month: parts[1], day: parts[2], hour: 12)
        )
    }
}

public enum RatsColor {
    public static let page = Color.adaptive(light: 0xF6FAFC, dark: 0x09111B)
    public static let stage = Color.adaptive(light: 0xF1F7FA, dark: 0x0E1B29)
    public static let card = Color.adaptive(light: 0xFFFFFF, dark: 0x101E2C)
    public static let border = Color.adaptive(light: 0xDCE5EB, dark: 0x1C3043)
    public static let separator = Color.adaptive(light: 0xEBF1F4, dark: 0x192C3D)
    public static let text = Color.adaptive(light: 0x0D2132, dark: 0xF3F8FA)
    public static let bodyText = Color.adaptive(light: 0x17364D, dark: 0xDFEAF0)
    public static let secondary = Color.adaptive(light: 0x596B78, dark: 0x91A7B7)
    public static let muted = Color.adaptive(light: 0x7C8C97, dark: 0x71899A)
    public static let primary = Color.adaptive(light: 0x076FA6, dark: 0x45B8ED)
    public static let primaryText = Color.adaptive(light: 0xFFFFFF, dark: 0x062238)
    public static let signal = Color.adaptive(light: 0xF05A22, dark: 0xFA7440)
    public static let success = Color.adaptive(light: 0x15803D, dark: 0x62D98B)
    public static let successTint = Color.adaptive(light: 0xDCFCE7, dark: 0x102B1D)
    public static let danger = Color.adaptive(light: 0xB91C1C, dark: 0xFF8B8B)
    public static let dangerTint = Color.adaptive(light: 0xFEF2F2, dark: 0x321616)
    public static let warning = Color.adaptive(light: 0x92400E, dark: 0xF4BD68)
    public static let warningTint = Color.adaptive(light: 0xFFFBEB, dark: 0x33260E)
}

private extension Color {
    static func adaptive(light: UInt32, dark: UInt32) -> Color {
        Color(uiColor: UIColor { traits in
            UIColor(hex: traits.userInterfaceStyle == .dark ? dark : light)
        })
    }
}

private extension UIColor {
    convenience init(hex: UInt32) {
        self.init(
            red: CGFloat((hex >> 16) & 0xFF) / 255,
            green: CGFloat((hex >> 8) & 0xFF) / 255,
            blue: CGFloat(hex & 0xFF) / 255,
            alpha: 1
        )
    }
}

public struct PrimaryButtonStyle: ButtonStyle {
    public init() {}

    public func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(RatsFont.body(15, weight: .semibold))
            .foregroundStyle(RatsColor.primaryText)
            .padding(.horizontal, RatsSpacing.lg)
            .frame(minHeight: 42)
            .background(RatsColor.primary.opacity(configuration.isPressed ? 0.75 : 1))
            .clipShape(RoundedRectangle(cornerRadius: RatsRadius.button, style: .continuous))
    }
}

public struct SecondaryButtonStyle: ButtonStyle {
    public init() {}

    public func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(RatsFont.body(15, weight: .semibold))
            .foregroundStyle(RatsColor.primary)
            .padding(.horizontal, RatsSpacing.lg)
            .frame(minHeight: 42)
            .background(RatsColor.card.opacity(configuration.isPressed ? 0.7 : 1))
            .overlay(
                RoundedRectangle(cornerRadius: RatsRadius.button, style: .continuous)
                    .stroke(RatsColor.border)
            )
            .clipShape(RoundedRectangle(cornerRadius: RatsRadius.button, style: .continuous))
    }
}

public struct SignalButtonStyle: ButtonStyle {
    public init() {}

    public func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(RatsFont.body(15, weight: .semibold))
            .foregroundStyle(Color.white)
            .padding(.horizontal, RatsSpacing.lg)
            .frame(minHeight: 42)
            .background(RatsColor.signal.opacity(configuration.isPressed ? 0.76 : 1))
            .clipShape(RoundedRectangle(cornerRadius: RatsRadius.button, style: .continuous))
    }
}

public struct CardSurface: ViewModifier {
    public init() {}

    public func body(content: Content) -> some View {
        content
            .padding(RatsSpacing.lg)
            .background(RatsColor.card)
            .overlay(
                RoundedRectangle(cornerRadius: RatsRadius.card, style: .continuous)
                    .stroke(RatsColor.border, lineWidth: 1)
            )
            .clipShape(RoundedRectangle(cornerRadius: RatsRadius.card, style: .continuous))
            .shadow(color: .black.opacity(0.04), radius: 2, y: 1)
    }
}

public extension View {
    func ratsCard() -> some View { modifier(CardSurface()) }
}
