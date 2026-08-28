import RatslotseAPI
import RatslotseFeatures
import SwiftUI

@main
struct RatslotseApp: App {
    @UIApplicationDelegateAdaptor(RatslotseAppDelegate.self) private var appDelegate
    @State private var model = Self.makeModel()
    @State private var didHandleDebugRoute = false

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
                .onAppear {
#if DEBUG
                    guard !didHandleDebugRoute,
                          let path = ProcessInfo.processInfo.environment["RATSLOTSE_DEBUG_ROUTE"],
                          path.hasPrefix("/") else { return }
                    didHandleDebugRoute = true
                    model.handle(pushPath: path)
#endif
                }
        }
    }

    private static func makeModel() -> AppModel {
#if DEBUG
        if let rawURL = ProcessInfo.processInfo.environment["RATSLOTSE_API_BASE_URL"],
           let baseURL = URL(string: rawURL) {
            return AppModel(api: APIClient(baseURL: baseURL))
        }
#endif
        return AppModel()
    }
}
