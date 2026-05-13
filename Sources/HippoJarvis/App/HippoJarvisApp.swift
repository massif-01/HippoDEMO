import SwiftUI

@main
struct HippoJarvisApp: App {
    @NSApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var store = AppStateStore()

    var body: some Scene {
        MenuBarExtra {
            MenuBarRootView()
                .environmentObject(store)
        } label: {
            HStack(spacing: 3) {
                HippoMenuBarIcon()
                if isRecording {
                    HippoStatusDot(color: .red, pulse: true, size: 5)
                }
            }
            .task {
                await store.bootstrap()
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

private struct HippoMenuBarIcon: View {
    private static let image: NSImage = {
        if let url = Bundle.main.url(forResource: "HippoJarvisIcon", withExtension: "png"),
           let image = NSImage(contentsOf: url) {
            image.isTemplate = true
            image.size = NSSize(width: 22, height: 22)
            return image
        }
        if let url = Bundle.module.url(forResource: "HippoJarvisIcon", withExtension: "png"),
           let image = NSImage(contentsOf: url) {
            image.isTemplate = true
            image.size = NSSize(width: 22, height: 22)
            return image
        }
        let fallback = NSImage(systemSymbolName: "sparkles", accessibilityDescription: nil) ?? NSImage()
        fallback.isTemplate = true
        fallback.size = NSSize(width: 22, height: 22)
        return fallback
    }()

    var body: some View {
        Image(nsImage: Self.image)
            .renderingMode(.template)
            .resizable()
            .interpolation(.high)
            .scaledToFit()
            .frame(width: 22, height: 22)
            .accessibilityHidden(true)
    }
}
