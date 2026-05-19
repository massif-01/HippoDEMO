import AppKit
import SwiftUI

struct MenuBarRootView: View {
    @EnvironmentObject private var store: AppStateStore
    @Environment(\.openWindow) private var openWindow

    var body: some View {
        Group {
            if let task = store.snapshot.currentTask {
                ReviewPopover(task: task)
                    .frame(width: 320)
                    .transition(.opacity)
            } else {
                StatusPopover()
                    .frame(width: 320)
                    .transition(.opacity)
            }
        }
        .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 16, style: .continuous))
        .clipShape(RoundedRectangle(cornerRadius: 16, style: .continuous))
        .task {
            await store.bootstrap()
        }
    }

    private func openDashboard(route: DashboardRouteID) {
        UserDefaults.standard.set(route.rawValue, forKey: DashboardRouteID.storageKey)
        NSApp.activate(ignoringOtherApps: true)
        openWindow(id: "dashboard")
    }

    private struct StatusPopover: View {
        @EnvironmentObject private var store: AppStateStore
        @Environment(\.openWindow) private var openWindow

        var body: some View {
            VStack(spacing: 0) {
                header
                HippoHairline()

                VStack(alignment: .leading, spacing: 12) {
                    if let error = store.lastError {
                        errorStrip(error)
                    }
                    statusRow
                    controls
                }
                .padding(14)

                HippoHairline()
                servicesList
                HippoHairline()
                footer
            }
            .accessibilityElement(children: .contain)
        }

        private var header: some View {
            HStack(spacing: 10) {
                HippoTile(size: 28)
                VStack(alignment: .leading, spacing: 1) {
                    Text("Hippo")
                        .font(.system(size: 13, weight: .semibold))
                    Text(sessionLine)
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
                Spacer(minLength: 0)
                HippoSymbolButton(systemName: "ellipsis.circle", title: "More") {}
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 12)
        }

        private var statusRow: some View {
            HStack(spacing: 12) {
                HippoWaveform()
                VStack(alignment: .leading, spacing: 3) {
                    Text(store.statusTitle)
                        .font(.system(size: 13, weight: .semibold))
                        .lineLimit(1)
                    Text(store.statusMessage)
                        .font(.system(size: 12))
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }
                Spacer(minLength: 0)
            }
        }

        private var controls: some View {
            HStack(spacing: 8) {
                Button {
                    Task {
                        if store.canJarvisOff {
                            await store.jarvisOff()
                        } else {
                            await store.jarvisOn()
                        }
                    }
                } label: {
                    Label(primaryTitle, systemImage: primaryIcon)
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(HippoPushButtonStyle(store.canJarvisOff ? .stop : .preferred, size: .lg, fullWidth: true))
                .disabled(store.isBusy)

                Button {
                    Task {
                        if store.canFinishCapture {
                            await store.finishCapture()
                        } else {
                            await store.captureSkill()
                        }
                    }
                } label: {
                    Label(captureTitle, systemImage: "pin.fill")
                }
                .buttonStyle(HippoPushButtonStyle(.neutral, size: .lg))
                .disabled(store.isBusy || (!store.canCaptureSkill && !store.canFinishCapture))
            }
        }

        private var servicesList: some View {
            VStack(spacing: 0) {
                ForEach(priorityServices) { service in
                    serviceRow(service)
                    if service.id != priorityServices.last?.id {
                        HippoHairline()
                            .padding(.leading, 48)
                    }
                }
            }
            .padding(.vertical, 4)
        }

        private func serviceRow(_ service: ServiceStatus) -> some View {
            HStack(spacing: 10) {
                Image(systemName: icon(for: service.name))
                    .font(.system(size: 14, weight: .medium))
                    .foregroundStyle(.secondary)
                    .frame(width: 22, height: 22)
                Text(service.name)
                    .font(.system(size: 13, weight: .medium))
                Spacer(minLength: 8)
                Text(store.serviceDetail(service.detail, status: service.status))
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                HippoStatusDot(color: HippoTheme.stateColor(service.status), pulse: service.status == "recording", size: 6)
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 7)
            .accessibilityLabel("\(service.name), \(store.serviceStatus(service.status))")
        }

        private var footer: some View {
            HStack(spacing: 6) {
                footerButton("waveform.path.ecg", title: "Activity", route: .liveSignal)
                footerButton("sparkles", title: "Library", route: .skills)
                footerButton("gearshape", title: "Settings", route: .settings)
                Spacer(minLength: 0)
                Button {
                    toggleLanguage()
                } label: {
                    Text(store.language == .simplifiedChinese ? "ZH" : "EN")
                        .font(.system(size: 11, weight: .semibold, design: .monospaced))
                        .frame(width: 28, height: 28)
                }
                .buttonStyle(HippoPressFeedbackButtonStyle(cornerRadius: 7, pressedScale: 0.88, overlayOpacity: 0.16))
                .foregroundStyle(.secondary)
                .accessibilityLabel("Language")

                HippoSymbolButton(systemName: "arrow.clockwise", title: "Refresh") {
                    Task { await store.refresh() }
                }
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 8)
        }

        private func footerButton(_ image: String, title: String, route: DashboardRouteID) -> some View {
            HippoSymbolButton(systemName: image, title: title) {
                UserDefaults.standard.set(route.rawValue, forKey: DashboardRouteID.storageKey)
                NSApp.activate(ignoringOtherApps: true)
                openWindow(id: "dashboard")
            }
        }

        private func errorStrip(_ error: String) -> some View {
            HStack(alignment: .top, spacing: 8) {
                Image(systemName: "exclamationmark.triangle.fill")
                    .foregroundStyle(.red)
                Text(error)
                    .font(.system(size: 11))
                    .foregroundStyle(.red)
                    .lineLimit(3)
            }
            .padding(10)
            .background(.red.opacity(0.08), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
            .accessibilityLabel("Error: \(error)")
        }

        private var primaryTitle: String {
            store.canJarvisOff ? "Stop Jarvis" : "Jarvis ON"
        }

        private var primaryIcon: String {
            store.canJarvisOff ? "stop.fill" : "power"
        }

        private var captureTitle: String {
            store.canFinishCapture ? "Finish Capture" : "Capture"
        }

        private var sessionLine: String {
            if let session = store.snapshot.currentSession {
                return "\(session.title) · \(sessionDuration(session))"
            }
            return "No active session"
        }

        private var priorityServices: [ServiceStatus] {
            let priority = ["OpenChronicle", "ownscribe", "Voice Context", "cua-driver", "vlmac"]
            return priority.map { expectedName in
                if expectedName == "Voice Context" {
                    return voiceContextService
                }
                return store.snapshot.services.first { $0.name.localizedCaseInsensitiveCompare(expectedName) == .orderedSame }
                    ?? ServiceStatus(id: expectedName, name: expectedName, status: "idle", detail: "Not reported")
            }
        }

        private var voiceContextService: ServiceStatus {
            guard let fragment = store.contextFragments.first else {
                return ServiceStatus(id: "voice-context", name: "Voice Context", status: "idle", detail: "No recent context")
            }

            let timestamp = formattedContextTimestamp(fragment.endedAt ?? fragment.startedAt)
            let status = fragment.syncedAt == nil ? "available" : "online"
            return ServiceStatus(id: "voice-context", name: "Voice Context", status: status, detail: "Last \(timestamp)")
        }

        private func icon(for name: String) -> String {
            switch name.lowercased() {
            case "openchronicle": "clock.arrow.circlepath"
            case "ownscribe": "mic.fill"
            case "voice context": "text.bubble"
            case "cua-driver": "cursorarrow.click.2"
            case "vlmac": "eye.fill"
            default: "circle"
            }
        }

        private func sessionDuration(_ session: DemoSession) -> String {
            guard let start = ISO8601DateFormatter().date(from: session.startedAt) else {
                return "live"
            }
            let end = session.endedAt.flatMap { ISO8601DateFormatter().date(from: $0) } ?? Date()
            let seconds = max(0, Int(end.timeIntervalSince(start)))
            return String(format: "%02d:%02d", seconds / 60, seconds % 60)
        }

        private func formattedContextTimestamp(_ value: String?) -> String {
            guard let value, let date = ISO8601DateFormatter().date(from: value) else {
                return "not reported"
            }
            return date.formatted(date: .omitted, time: .shortened)
        }

        private func toggleLanguage() {
            store.setLanguage(store.language == .english ? .simplifiedChinese : .english)
        }
    }

    private struct ReviewPopover: View {
        @EnvironmentObject private var store: AppStateStore
        @Environment(\.openWindow) private var openWindow
        let task: ActiveTask

        var body: some View {
            VStack(spacing: 0) {
                header
                HippoHairline()
                taskBody
                metadataStrip
                proposedActions
                targetSafetyStrip
                HippoHairline()
                actionFooter
            }
        }

        private var header: some View {
            HStack(spacing: 10) {
                HippoTile(size: 28)
                VStack(alignment: .leading, spacing: 1) {
                    Text("Ready to act")
                        .font(.system(size: 13, weight: .semibold))
                    Text("1 task · awaiting review")
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                }
                Spacer(minLength: 0)
                HippoSymbolButton(systemName: "ellipsis.circle", title: "More") {}
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 12)
        }

        private var taskBody: some View {
            VStack(alignment: .leading, spacing: 8) {
                HippoCapsuleLabel(title: "Active Task", color: .blue, systemImage: "target")
                Text(task.title)
                    .font(.system(size: 17, weight: .bold))
                    .lineLimit(2)
                Text(task.intent)
                    .font(.system(size: 13))
                    .foregroundStyle(.secondary)
                    .lineLimit(3)
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(.horizontal, 14)
            .padding(.top, 14)
            .padding(.bottom, 4)
        }

        private var metadataStrip: some View {
            HStack(spacing: 0) {
                HippoMetadataCell(label: "Surface", value: targetSurface)
                verticalHairline
                HippoMetadataCell(label: "Confidence", value: "\(Int(task.confidence * 100))%")
                verticalHairline
                HippoMetadataCell(label: "Mode", value: taskMode, muted: true)
            }
            .padding(.horizontal, 12)
            .padding(.vertical, 10)
            .background(HippoTheme.subtleFill, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
            .padding(.horizontal, 14)
            .padding(.vertical, 12)
        }

        private var proposedActions: some View {
            VStack(alignment: .leading, spacing: 6) {
                Text("Proposed")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(.secondary)
                    .textCase(.uppercase)
                    .padding(.horizontal, 10)
                ForEach(Array(task.proposedActions.enumerated()), id: \.element.id) { offset, action in
                    HStack(spacing: 10) {
                        Text("\(offset + 1)")
                            .font(.system(size: 10, weight: .bold))
                            .foregroundStyle(.secondary)
                            .frame(width: 18, height: 18)
                            .background(HippoTheme.subtleFill, in: RoundedRectangle(cornerRadius: 4, style: .continuous))
                        Text(action.label)
                            .font(.system(size: 13, weight: .medium))
                            .lineLimit(1)
                        Spacer(minLength: 0)
                        Text(action.status ?? action.type)
                            .font(.system(size: 11))
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                    }
                    .padding(.horizontal, 10)
                    .padding(.vertical, 5)
                }
            }
            .padding(.horizontal, 6)
            .padding(.bottom, 6)
        }

        private var actionFooter: some View {
            VStack(spacing: 6) {
                HStack(spacing: 8) {
                    Button {
                        Task { await store.confirmCurrentTask() }
                    } label: {
                        Label("Insert draft", systemImage: "arrow.right.to.line")
                            .frame(maxWidth: .infinity)
                    }
                    .buttonStyle(HippoPushButtonStyle(.preferred, fullWidth: true))
                    .disabled(!store.canInsertCurrentTask)

                    Button("Ignore") {
                        Task { await store.ignoreCurrentTask() }
                    }
                    .buttonStyle(HippoPushButtonStyle(.neutral))
                    .disabled(store.isBusy)
                }

                Button {
                    UserDefaults.standard.set(DashboardRouteID.activeTask.rawValue, forKey: DashboardRouteID.storageKey)
                    NSApp.activate(ignoringOtherApps: true)
                    openWindow(id: "dashboard")
                } label: {
                    Label("Open in Activity", systemImage: "arrow.up.right")
                        .labelStyle(.titleAndIcon)
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(HippoPushButtonStyle(.plain))
                .foregroundStyle(Color.accentColor)
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
        }

        private var verticalHairline: some View {
            Rectangle()
                .fill(HippoTheme.hairline)
                .frame(width: 0.5, height: 30)
                .padding(.horizontal, 12)
        }

        private var targetSurface: String {
            if store.cuaTargetSurface.status != "unknown" {
                return store.cuaTargetSurface.displayName
            }
            return task.proposedActions.first?.type.isEmpty == false
                ? task.proposedActions.first!.type.replacingOccurrences(of: "_", with: " ").capitalized
                : "Waiting"
        }

        private var taskMode: String {
            store.cuaTargetSurface.safe ? store.cuaTargetSurface.modeLabel : "Guarded"
        }

        private var targetSafetyStrip: some View {
            HStack(alignment: .top, spacing: 9) {
                Image(systemName: store.cuaTargetSurface.safe ? "shield.checkered" : "shield.slash")
                    .font(.system(size: 13, weight: .semibold))
                    .foregroundStyle(store.cuaTargetSurface.safe ? .green : .orange)
                    .frame(width: 18)
                VStack(alignment: .leading, spacing: 2) {
                    Text(store.cuaTargetSurface.safe ? store.text(.targetReady) : store.text(.targetBlocked))
                        .font(.system(size: 12, weight: .semibold))
                    Text(store.cuaTargetSurface.reason)
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }
                Spacer(minLength: 0)
            }
            .padding(.horizontal, 14)
            .padding(.bottom, 10)
        }
    }
}
