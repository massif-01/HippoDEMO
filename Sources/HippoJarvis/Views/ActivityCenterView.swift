import Foundation
import SwiftUI

struct ActivityCenterView: View {
    @EnvironmentObject private var store: AppStateStore

    var body: some View {
        NavigationSplitView {
            sidebar
        } detail: {
            ScrollView {
                HStack(alignment: .top, spacing: 16) {
                    VStack(alignment: .leading, spacing: 14) {
                        timelinePanel
                        recordingTimelinePanel
                    }
                        .frame(minWidth: 380, maxWidth: .infinity, alignment: .topLeading)

                    VStack(alignment: .leading, spacing: 14) {
                        currentSignalPanel
                        taskPanel
                        artifactsPanel
                        servicesPanel
                    }
                    .frame(width: 300, alignment: .topLeading)
                }
                .padding(20)
                .frame(maxWidth: 980, alignment: .topLeading)
                .frame(maxWidth: .infinity, alignment: .top)
            }
            .navigationTitle(store.text(.activityCenter))
        }
        .task {
            await store.bootstrap()
        }
    }

    private var sidebar: some View {
        List {
            Section(store.text(.current)) {
                sidebarRow(store.statusTitle, detail: store.statusMessage, icon: store.menuBarSystemImage)
                if let task = store.snapshot.currentTask {
                    sidebarRow(task.title, detail: task.intent, icon: "bolt.circle")
                }
            }

            Section(store.text(.signal)) {
                ForEach(timelineEvents.prefix(8)) { event in
                    sidebarRow(event.typeLabel, detail: event.shortTime, icon: icon(for: event))
                }
            }

            Section(store.text(.task)) {
                if let task = store.snapshot.currentTask {
                    sidebarRow(task.title, detail: store.stateName(task.state), icon: "checklist")
                } else {
                    sidebarRow(store.text(.noActiveTask), detail: store.text(.noActiveTaskDescription), icon: "moon.zzz")
                }
            }
        }
        .listStyle(.sidebar)
        .navigationTitle(store.text(.activity))
    }

    private var timelinePanel: some View {
        HUDSection(store.text(.timeline), systemImage: "point.topleft.down.curvedto.point.bottomright.up") {
            VStack(alignment: .leading, spacing: 0) {
                ForEach(timelineEvents) { event in
                    TimelineRow(event: event, color: color(for: event))
                        .padding(.vertical, 6)
                    if event.id != timelineEvents.last?.id {
                        Divider()
                            .padding(.leading, 28)
                    }
                }
            }
        }
    }

    private var currentSignalPanel: some View {
        HUDSection(store.text(.currentSignal), systemImage: store.menuBarSystemImage) {
            HStack(alignment: .center, spacing: 12) {
                StatusPulse(color: accentColor, systemImage: store.menuBarSystemImage, isActive: store.snapshot.jarvisState != .idle)
                    .scaleEffect(0.72)
                    .frame(width: 62, height: 62)

                VStack(alignment: .leading, spacing: 5) {
                    Text(store.statusTitle)
                        .font(.headline)
                        .lineLimit(1)
                    Text(store.statusMessage)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(3)
                }
            }

            HStack(spacing: 8) {
                ArtifactBadge(title: store.shortStateLabel(store.snapshot.jarvisState), systemImage: "waveform.path.ecg", color: accentColor)
                ArtifactBadge(title: "\(timelineEvents.count)", systemImage: "timeline.selection", color: .blue)
            }
        }
    }

    @ViewBuilder
    private var taskPanel: some View {
        HUDSection(store.text(.task), systemImage: "checklist") {
            if let task = store.snapshot.currentTask {
                VStack(alignment: .leading, spacing: 10) {
                    HStack(alignment: .top, spacing: 10) {
                        VStack(alignment: .leading, spacing: 4) {
                            Text(task.title)
                                .font(.headline)
                                .lineLimit(2)
                            Text(task.intent)
                                .font(.caption)
                                .foregroundStyle(.secondary)
                                .lineLimit(3)
                        }
                        Spacer(minLength: 0)
                        Text("\(Int(task.confidence * 100))%")
                            .font(.system(size: 18, weight: .semibold, design: .rounded))
                            .foregroundStyle(accentColor)
                    }

                    if !task.proposedActions.isEmpty {
                        Divider()
                        ForEach(task.proposedActions) { action in
                            HStack(spacing: 8) {
                                Image(systemName: action.requiresConfirmation ? "hand.raised" : "arrow.triangle.2.circlepath")
                                    .foregroundStyle(.secondary)
                                    .frame(width: 16)
                                Text(action.label)
                                    .font(.caption)
                                    .lineLimit(1)
                                Spacer(minLength: 0)
                                Text(action.status ?? action.type)
                                    .font(.caption2)
                                    .foregroundStyle(.tertiary)
                            }
                        }
                    }

                    targetSurfaceRow

                    HStack(spacing: 8) {
                        Button {
                            Task { await store.confirmCurrentTask() }
                        } label: {
                            Label(store.text(.insertToCurrentTask), systemImage: "arrow.down.doc.fill")
                        }
                        .buttonStyle(.borderedProminent)
                        .disabled(!store.canInsertCurrentTask)

                        Button {
                            Task { await store.completeCurrentTask() }
                        } label: {
                            Image(systemName: "checkmark.circle")
                        }

                        Button {
                            Task { await store.ignoreCurrentTask() }
                        } label: {
                            Image(systemName: "xmark.circle")
                        }
                    }
                    .controlSize(.small)
                }
            } else {
                VStack(alignment: .leading, spacing: 5) {
                    Text(store.text(.noActiveTask))
                        .font(.headline)
                    Text(store.text(.noActiveTaskDescription))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                        .lineLimit(3)
                }
            }
        }
    }

    private var targetSurfaceRow: some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: store.cuaTargetSurface.safe ? "shield.checkered" : "shield.slash")
                .foregroundStyle(store.cuaTargetSurface.safe ? .green : .orange)
                .frame(width: 16)
            VStack(alignment: .leading, spacing: 2) {
                HStack(spacing: 6) {
                    Text(store.cuaTargetSurface.displayName)
                        .font(.caption)
                        .lineLimit(1)
                    Text(store.cuaTargetSurface.modeLabel)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .padding(.horizontal, 5)
                        .padding(.vertical, 1)
                        .background(.quaternary.opacity(0.5), in: Capsule())
                }
                Text(store.cuaTargetSurface.reason)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }
            Spacer(minLength: 0)
        }
        .padding(8)
        .background(.quaternary.opacity(0.25), in: RoundedRectangle(cornerRadius: 8, style: .continuous))
    }

    private var artifactsPanel: some View {
        HUDSection(store.text(.artifacts), systemImage: "shippingbox") {
            let artifacts = sessionArtifacts
            if artifacts.isEmpty {
                Text(store.text(.notReported))
                    .font(.caption)
                    .foregroundStyle(.secondary)
            } else {
                FlowLayout(spacing: 8) {
                    ForEach(artifacts) { artifact in
                        ArtifactBadge(title: artifact.title, systemImage: artifactIcon(for: artifact.kind), color: accentColor)
                    }
                }
            }
        }
    }

    @ViewBuilder
    private var recordingTimelinePanel: some View {
        if let timeline = latestRecordingTimeline {
            HUDSection(store.text(.recordingTimeline), systemImage: "timeline.selection") {
                VStack(alignment: .leading, spacing: 10) {
                    HStack(spacing: 8) {
                        ArtifactBadge(title: timeline.audioSource?.uppercased() ?? store.text(.audioSource), systemImage: "waveform.and.mic", color: .cyan)
                        if let status = timeline.status {
                            ArtifactBadge(title: status.uppercased(), systemImage: "checkmark.seal", color: .green)
                        }
                    }

                    LazyVGrid(columns: [
                        GridItem(.flexible(), spacing: 10),
                        GridItem(.flexible(), spacing: 10)
                    ], spacing: 10) {
                        timelineMetric(store.text(.start), value: formattedTimestamp(timeline.recordingStartedAt), icon: "record.circle")
                        timelineMetric(store.text(.stop), value: formattedTimestamp(timeline.recordingStoppedAt), icon: "stop.circle")
                        timelineMetric(store.text(.wallClockAlignment), value: formatSeconds(timeline.wallDurationSeconds), icon: "clock")
                        timelineMetric(store.text(.audioCapture), value: formatSeconds(timeline.audioFile?.durationSeconds), icon: "waveform")
                    }

                    if let dataFormat = timeline.audioFile?.dataFormat {
                        Text(dataFormat)
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .lineLimit(1)
                    }

                    if let formula = timeline.alignment?.formula {
                        Text(formula)
                            .font(.caption2)
                            .fontDesign(.monospaced)
                            .foregroundStyle(.tertiary)
                            .textSelection(.enabled)
                    }
                }
            }
        }
    }

    private var servicesPanel: some View {
        HUDSection(store.text(.health), systemImage: "dot.radiowaves.left.and.right") {
            VStack(alignment: .leading, spacing: 9) {
                ForEach(store.snapshot.services) { service in
                    HStack(spacing: 8) {
                        ServiceLight(
                            service: service,
                            title: service.name,
                            detail: store.serviceDetail(service.detail, status: service.status),
                            compact: true
                        )
                        Spacer(minLength: 0)
                        Text(store.serviceStatus(service.status))
                            .font(.caption2)
                            .fontWeight(.semibold)
                            .foregroundStyle(StatusVisuals.serviceColor(service.status))
                    }
                    .help(store.serviceDetail(service.detail, status: service.status))
                }
            }
        }
    }

    private var timelineEvents: [EventRecord] {
        if store.eventHistory.isEmpty {
            [currentSignalEvent]
        } else {
            store.eventHistory
        }
    }

    private var currentSignalEvent: EventRecord {
        EventRecord(
            id: "current-signal-\(store.snapshot.jarvisState.rawValue)",
            type: store.snapshot.currentTask == nil ? "current_signal" : "task_signal",
            timestamp: ISO8601DateFormatter().string(from: Date()),
            sessionId: store.snapshot.currentSession?.id,
            payload: [
                "status": .string(store.stateName(store.snapshot.jarvisState)),
                "message": .string(store.statusMessage),
                "services": .number(Double(store.snapshot.services.count))
            ]
        )
    }

    private var sessionArtifacts: [Artifact] {
        if let artifacts = store.snapshot.currentSession?.artifacts, !artifacts.isEmpty {
            return artifacts
        }
        return store.snapshot.currentTask?.artifacts ?? []
    }

    private var latestRecordingTimeline: RecordingTimeline? {
        sessionArtifacts
            .filter { $0.kind == "recording_timeline" }
            .compactMap(decodeRecordingTimeline)
            .first
    }

    private var accentColor: Color {
        StatusVisuals.jarvisColor(store.snapshot.jarvisState)
    }

    private func sidebarRow(_ title: String, detail: String, icon: String) -> some View {
        HStack(spacing: 10) {
            Image(systemName: icon)
                .foregroundStyle(.secondary)
                .frame(width: 16)
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .lineLimit(1)
                Text(detail)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
        }
    }

    private func icon(for event: EventRecord) -> String {
        if event.type.contains("task") {
            return "bolt.circle"
        }
        if event.type.contains("service") {
            return "switch.2"
        }
        if event.type.contains("error") {
            return "exclamationmark.triangle"
        }
        return "waveform.path.ecg"
    }

    private func color(for event: EventRecord) -> Color {
        if event.type.contains("error") {
            return .red
        }
        if event.type.contains("task") {
            return .blue
        }
        if event.type.contains("service") {
            return .green
        }
        return accentColor
    }

    private func artifactIcon(for kind: String) -> String {
        switch kind {
        case "skill": "sparkles"
        case "file": "doc"
        case "message": "text.bubble"
        case "recording_timeline": "timeline.selection"
        case "audio_recording": "waveform"
        case "meeting_transcript": "text.quote"
        case "meeting_minutes": "doc.text"
        default: "shippingbox"
        }
    }

    private func decodeRecordingTimeline(_ artifact: Artifact) -> RecordingTimeline? {
        guard let content = artifact.content, let data = content.data(using: .utf8) else {
            return nil
        }
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return try? decoder.decode(RecordingTimeline.self, from: data)
    }

    private func timelineMetric(_ title: String, value: String, icon: String) -> some View {
        HStack(spacing: 8) {
            Image(systemName: icon)
                .foregroundStyle(.secondary)
                .frame(width: 16)
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                Text(value)
                    .font(.caption)
                    .fontWeight(.medium)
                    .lineLimit(1)
            }
            Spacer(minLength: 0)
        }
        .padding(8)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
    }

    private func formattedTimestamp(_ value: String?) -> String {
        guard let value, let date = ISO8601DateFormatter().date(from: value) else {
            return store.text(.notReported)
        }
        return date.formatted(date: .omitted, time: .standard)
    }

    private func formatSeconds(_ value: Double?) -> String {
        guard let value else {
            return store.text(.notReported)
        }
        return String(format: "%.1fs", value)
    }
}

private extension EventRecord {
    var typeLabel: String {
        type.replacingOccurrences(of: "_", with: " ").capitalized
    }

    var shortTime: String {
        guard let date = ISO8601DateFormatter().date(from: timestamp) else {
            return timestamp
        }
        return date.formatted(date: .omitted, time: .shortened)
    }
}

private struct FlowLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? 260
        return layout(in: width, subviews: subviews).size
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let rows = layout(in: bounds.width, subviews: subviews).rows
        var y = bounds.minY

        for row in rows {
            var x = bounds.minX
            for item in row.items {
                subviews[item.index].place(
                    at: CGPoint(x: x, y: y),
                    proposal: ProposedViewSize(item.size)
                )
                x += item.size.width + spacing
            }
            y += row.height + spacing
        }
    }

    private func layout(in width: CGFloat, subviews: Subviews) -> (rows: [Row], size: CGSize) {
        var rows: [Row] = []
        var current = Row()
        var currentWidth: CGFloat = 0

        for index in subviews.indices {
            let size = subviews[index].sizeThatFits(.unspecified)
            let nextWidth = current.items.isEmpty ? size.width : currentWidth + spacing + size.width
            if nextWidth > width, !current.items.isEmpty {
                rows.append(current)
                current = Row()
                currentWidth = 0
            }

            current.items.append(Item(index: index, size: size))
            currentWidth = current.items.count == 1 ? size.width : currentWidth + spacing + size.width
            current.height = max(current.height, size.height)
        }

        if !current.items.isEmpty {
            rows.append(current)
        }

        let height = rows.reduce(CGFloat(0)) { partial, row in
            partial + row.height
        } + CGFloat(max(rows.count - 1, 0)) * spacing

        return (rows, CGSize(width: width, height: height))
    }

    private struct Row {
        var items: [Item] = []
        var height: CGFloat = 0
    }

    private struct Item {
        var index: Int
        var size: CGSize
    }
}
