import AppKit
import AVFoundation

final class AppDelegate: NSObject, NSApplicationDelegate {
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.accessory)
        requestMicrophonePermissionIfNeeded()
        Task {
            try? await OrchestratorLauncher.shared.ensureRunning(client: OrchestratorClient())
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
