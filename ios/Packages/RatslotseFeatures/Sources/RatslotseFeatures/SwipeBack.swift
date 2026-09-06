import SwiftUI
import UIKit

/// Das Wischen vom linken Rand zurückholen.
///
/// **Warum es fehlte.** Jede geschobene Route liegt in `RatsRouteScaffold`, und
/// der blendet die System-Navigationsleiste aus (`.toolbar(.hidden, for:
/// .navigationBar)`), weil die App ihre eigene Kopfzeile mit rundem
/// Zurück-Knopf zeichnet. UIKit schaltet mit der Leiste aber auch den
/// `interactivePopGestureRecognizer` ab — der hängt am Zurück-Knopf der Leiste,
/// den es nun nicht mehr gibt. Ergebnis: Auf **jedem** Unterscreen der App ging
/// das Wischen ins Leere, nicht nur auf der Tagesordnung (Tim, 04.09.2026).
///
/// **Warum nicht einfach den Delegaten auf `nil` setzen.** Das ist der überall
/// abgeschriebene Einzeiler und der Grund für eine bekannte Einfrierung: Ohne
/// Delegat beginnt die Geste auch auf der WURZEL, UIKit versucht zu poppen, was
/// nicht da ist, und die App nimmt keine Berührung mehr an. Deshalb steht hier
/// ein eigener Delegat, der genau eine Frage beantwortet — liegt überhaupt
/// etwas unter dieser Ansicht?
///
/// Er hängt am Navigations-Controller, nicht an der Geste: Die Geste hält ihren
/// Delegaten schwach, ein an die SwiftUI-Ansicht gebundenes Objekt wäre beim
/// ersten Zurück weg und die Geste stünde wieder ohne da.
struct SwipeBackEnabler: UIViewControllerRepresentable {
    func makeUIViewController(context: Context) -> UIViewController { Träger() }
    func updateUIViewController(_ controller: UIViewController, context: Context) {}

    final class Träger: UIViewController {
        override func didMove(toParent parent: UIViewController?) {
            super.didMove(toParent: parent)
            einschalten()
        }

        override func viewDidAppear(_ animated: Bool) {
            super.viewDidAppear(animated)
            einschalten()
        }

        private func einschalten() {
            guard let navigation = navigationController ?? parent?.navigationController,
                  let geste = navigation.interactivePopGestureRecognizer else { return }
            let delegat = PopDelegat.am(navigation)
            geste.delegate = delegat
            geste.isEnabled = true
        }
    }
}

/// Erlaubt die Geste nur, wenn es etwas zurückzugehen gibt.
private final class PopDelegat: NSObject, UIGestureRecognizerDelegate {
    private weak var navigation: UINavigationController?
    private static var schlüssel: UInt8 = 0

    /// Einer je Navigations-Controller, an ihm festgemacht — der Delegat der
    /// Geste ist schwach, irgendwer muss ihn halten.
    static func am(_ navigation: UINavigationController) -> PopDelegat {
        if let vorhanden = objc_getAssociatedObject(navigation, &schlüssel) as? PopDelegat {
            return vorhanden
        }
        let neu = PopDelegat()
        neu.navigation = navigation
        objc_setAssociatedObject(navigation, &schlüssel, neu, .OBJC_ASSOCIATION_RETAIN_NONATOMIC)
        return neu
    }

    func gestureRecognizerShouldBegin(_ gestureRecognizer: UIGestureRecognizer) -> Bool {
        (navigation?.viewControllers.count ?? 0) > 1
    }

    /// Ohne das bliebe die Geste in einer Ansicht stecken, die selbst waagerecht
    /// scrollt — die Chip-Reihen der Filter etwa. Beide dürfen erkennen; die
    /// Randgeste gewinnt am Rand, die Scroll-Ansicht in der Fläche.
    func gestureRecognizer(_ gestureRecognizer: UIGestureRecognizer,
                           shouldRecognizeSimultaneouslyWith other: UIGestureRecognizer) -> Bool {
        true
    }
}

extension View {
    /// An jede geschobene Route hängen, die ihre eigene Kopfzeile zeichnet.
    func ratsSwipeBack() -> some View {
        background(SwipeBackEnabler().frame(width: 0, height: 0).accessibilityHidden(true))
    }
}
