import AppKit
import AVFoundation

final class AppDelegate: NSObject, NSApplicationDelegate {
    private var launchTask: Task<Void, Never>?

    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        requestMicrophonePermissionIfNeeded()
        launchTask = Task { @MainActor in
            let startedAt = AppLog.start()
            do {
                try await OrchestratorLauncher.shared.ensureRunning(client: OrchestratorClient())
                AppLog.event(action: "app.launch.ensure_orchestrator", status: "ok", startedAt: startedAt)
            } catch {
                AppLog.event(action: "app.launch.ensure_orchestrator", status: "error", startedAt: startedAt, error: error)
            }
        }
    }

    private func requestMicrophonePermissionIfNeeded() {
        switch AVCaptureDevice.authorizationStatus(for: .audio) {
        case .notDetermined:
            AVCaptureDevice.requestAccess(for: .audio) { _ in }
        case .authorized, .denied, .restricted:
            break
        @unknown default:
            break
        }
    }
}
