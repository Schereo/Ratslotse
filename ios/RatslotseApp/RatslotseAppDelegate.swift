import UIKit
import UserNotifications

extension Notification.Name {
    static let ratslotsePushToken = Notification.Name("de.ratslotse.push-token")
    static let ratslotsePushRoute = Notification.Name("de.ratslotse.push-route")
}

final class RatslotseAppDelegate: NSObject, UIApplicationDelegate, UNUserNotificationCenterDelegate {
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]? = nil
    ) -> Bool {
        UNUserNotificationCenter.current().delegate = self
        if let notification = launchOptions?[.remoteNotification] as? [AnyHashable: Any],
           let path = notification["url"] as? String {
            DispatchQueue.main.async {
                NotificationCenter.default.post(name: .ratslotsePushRoute, object: path)
            }
        }
        return true
    }

    func application(_ application: UIApplication, didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data) {
        let token = deviceToken.map { String(format: "%02x", $0) }.joined()
        NotificationCenter.default.post(name: .ratslotsePushToken, object: token)
    }

    func application(
        _ application: UIApplication,
        didFailToRegisterForRemoteNotificationsWithError error: Error
    ) {
        // Registration is best-effort; iOS will retry on a later launch.
    }

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification
    ) async -> UNNotificationPresentationOptions {
        [.banner, .list, .sound, .badge]
    }

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse
    ) async {
        guard let path = response.notification.request.content.userInfo["url"] as? String else { return }
        await MainActor.run {
            NotificationCenter.default.post(name: .ratslotsePushRoute, object: path)
        }
    }
}
