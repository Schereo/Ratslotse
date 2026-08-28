import RatslotseFeatures
import SwiftUI

@main
struct RatslotseApp: App {
    @UIApplicationDelegateAdaptor(RatslotseAppDelegate.self) private var appDelegate
    @State private var model = AppModel()

    var body: some Scene {
        WindowGroup {
            NativeRootView(model: model)
                .onOpenURL { model.handle(url: $0) }
                .onContinueUserActivity(NSUserActivityTypeBrowsingWeb) { activity in
                    if let url = activity.webpageURL { model.handle(url: url) }
                }
                .onReceive(NotificationCenter.default.publisher(for: .ratslotsePushToken)) { note in
                    guard let token = note.object as? String else { return }
                    Task { await model.registerPushToken(token) }
                }
                .onReceive(NotificationCenter.default.publisher(for: .ratslotsePushRoute)) { note in
                    guard let path = note.object as? String else { return }
                    model.handle(pushPath: path)
                }
        }
    }
}
