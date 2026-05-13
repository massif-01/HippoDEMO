import SwiftUI

@main
struct HippoJarvisApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) private var appDelegate
    @StateObject private var store = AppStateStore()

    var body: some Scene {
        MenuBarExtra {
            MenuBarRootView()
                .environmentObject(store)
        } label: {
            HStack(spacing: 3) {
                HippoGlyphView(size: 16, foreground: .primary)
                if isRecording {
                    HippoStatusDot(color: .red, pulse: true, size: 5)
                }
            }
            .accessibilityLabel(isRecording ? "Hippo recording" : "Hippo")
        }
        .menuBarExtraStyle(.window)

        Window("Hippo", id: "dashboard") {
            DashboardWindow()
                .environmentObject(store)
                .frame(minWidth: 1024, idealWidth: 1280, minHeight: 640, idealHeight: 800)
        }
        .defaultSize(width: 1280, height: 800)
        .windowToolbarStyle(.unified(showsTitle: true))
    }

    private var isRecording: Bool {
        store.snapshot.services.contains { service in
            service.name.localizedCaseInsensitiveCompare("ownscribe") == .orderedSame && service.status == "recording"
        } || store.snapshot.jarvisState == .meetingActive || store.snapshot.jarvisState == .sopMarking
    }
}
