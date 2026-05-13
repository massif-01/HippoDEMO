import AppKit

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        Task {
            try? await OrchestratorLauncher.shared.ensureRunning(client: OrchestratorClient())
        }
    }
}
