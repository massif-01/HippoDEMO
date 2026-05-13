import AppKit
import SwiftUI

enum DashboardRouteID: String, CaseIterable, Identifiable {
    static let storageKey = "hippo.dashboard.route"

    case chat
    case liveSignal
    case activeTask
    case sessions
    case skills
    case settings

    var id: String { rawValue }

    var title: String {
        switch self {
        case .chat: "Chat"
        case .liveSignal: "Live Signal"
        case .activeTask: "Active Task"
        case .sessions: "Sessions"
        case .skills: "Skill Library"
        case .settings: "Settings"
        }
    }

    var icon: String {
        switch self {
        case .chat: "bubble.left.and.bubble.right.fill"
        case .liveSignal: "waveform.path.ecg"
        case .activeTask: "target"
        case .sessions: "clock.arrow.circlepath"
        case .skills: "sparkles"
        case .settings: "gearshape"
        }
    }
}

struct DashboardWindow: View {
    @EnvironmentObject private var store: AppStateStore
    @AppStorage(DashboardRouteID.storageKey) private var routeRaw = DashboardRouteID.liveSignal.rawValue
    @SceneStorage("hippo.dashboard.sidebar") private var sidebarRaw = "all"

    private var route: DashboardRouteID {
        get { DashboardRouteID(rawValue: routeRaw) ?? .liveSignal }
        nonmutating set { routeRaw = newValue.rawValue }
    }

    var body: some View {
        NavigationSplitView(columnVisibility: columnVisibilityBinding) {
            DashboardSidebar(
                route: routeBinding
            )
            .navigationSplitViewColumnWidth(min: 220, ideal: 240, max: 260)
        } detail: {
            detail
        }
        .navigationSplitViewStyle(.balanced)
        .frame(minWidth: 1024, idealWidth: 1280, minHeight: 640, idealHeight: 800)
        .task {
            await store.bootstrap()
        }
    }

    private var routeBinding: Binding<DashboardRouteID> {
        Binding {
            route
        } set: { next in
            route = next
        }
    }

    @ViewBuilder
    private var detail: some View {
        switch route {
        case .chat:
            DashboardChatView()
        case .liveSignal:
            DashboardLiveSignalView()
        case .activeTask:
            DashboardActiveTaskView()
        case .sessions:
            DashboardSessionsView()
        case .skills:
            DashboardSkillView()
        case .settings:
            DashboardSettingsView()
        }
    }

    private var columnVisibilityBinding: Binding<NavigationSplitViewVisibility> {
        Binding {
            sidebarRaw == "detailOnly" ? .detailOnly : .all
        } set: { next in
            sidebarRaw = next == .detailOnly ? "detailOnly" : "all"
        }
    }

}

private struct DashboardSidebar: View {
    @EnvironmentObject private var store: AppStateStore
    @Binding var route: DashboardRouteID

    var body: some View {
        List(selection: routeSelection) {
            identityRow
                .listRowInsets(.init(top: 8, leading: 8, bottom: 14, trailing: 8))
                .listRowSeparator(.hidden)

            Section {
                sidebarItem(.chat, trailing: "BETA")
                    .tag(DashboardRouteID.chat)
                sidebarItem(.liveSignal, badge: "\(liveEventCount)")
                    .tag(DashboardRouteID.liveSignal)
                sidebarItem(.activeTask, badge: store.snapshot.currentTask == nil ? nil : "1", badgeAccent: true)
                    .tag(DashboardRouteID.activeTask)
                sidebarItem(.sessions)
                    .tag(DashboardRouteID.sessions)
            }

            Section("Library") {
                ForEach(store.snapshot.skills.prefix(6)) { skill in
                    skillRow(skill)
                }
            }
        }
        .listStyle(.sidebar)
        .safeAreaInset(edge: .bottom) {
            footer
        }
    }

    private var routeSelection: Binding<DashboardRouteID?> {
        Binding {
            route
        } set: { next in
            if let next {
                route = next
            }
        }
    }

    private var identityRow: some View {
        HStack(spacing: 8) {
            HippoTile(size: 22)
            VStack(alignment: .leading, spacing: 1) {
                Text("Hippo")
                    .font(.system(size: 13, weight: .semibold))
                HStack(spacing: 4) {
                    HippoStatusDot(color: .red, pulse: isRecording, size: 5)
                    Text(identitySubtitle)
                        .font(.system(size: 11))
                        .foregroundStyle(isRecording ? .red : .secondary)
                        .lineLimit(1)
                }
            }
            Spacer(minLength: 0)
        }
    }

    private var footer: some View {
        VStack(spacing: 8) {
            HippoHairline()
                .padding(.horizontal, -8)
            HStack(spacing: 8) {
                HippoSymbolButton(systemName: "gearshape", title: "Settings", active: route == .settings) {
                    route = .settings
                }
                VStack(alignment: .leading, spacing: 1) {
                    Text("Orchestrator")
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                    HStack(spacing: 5) {
                        HippoStatusDot(color: store.snapshot.jarvisState == .error ? .orange : .green, size: 5)
                        Text("127.0.0.1:8787")
                            .font(.system(size: 11, design: .monospaced))
                            .lineLimit(1)
                    }
                }
                Spacer(minLength: 0)
            }
            .padding(.horizontal, 8)
        }
        .padding(.horizontal, 8)
        .padding(.vertical, 8)
    }

    private func sidebarItem(_ item: DashboardRouteID, trailing: String? = nil, badge: String? = nil, badgeAccent: Bool = false) -> some View {
        HStack(spacing: 8) {
            Image(systemName: item.icon)
                .font(.system(size: 13, weight: .regular))
                .frame(width: 20)
            Text(item.title)
                .font(.system(size: 13, weight: route == item ? .semibold : .medium))
                .lineLimit(1)
            Spacer(minLength: 0)
            if let trailing {
                Text(trailing)
                    .font(.system(size: 10, weight: .bold))
                    .foregroundStyle(Color.accentColor)
                    .padding(.horizontal, 6)
                    .padding(.vertical, 1)
                    .background(Color.accentColor.opacity(0.14), in: RoundedRectangle(cornerRadius: 4, style: .continuous))
            }
            if let badge {
                Text(badge)
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(badgeAccent ? .white : .secondary)
                    .padding(.horizontal, 7)
                    .padding(.vertical, 1)
                    .background(badgeAccent ? Color.accentColor : HippoTheme.subtleFill, in: Capsule())
            }
        }
        .frame(height: 28)
        .contentShape(Rectangle())
        .accessibilityLabel(item.title)
    }

    private func skillRow(_ skill: SkillRecord) -> some View {
        HStack(spacing: 6) {
            Button {
                route = .skills
            } label: {
                HStack(spacing: 8) {
                    Image(systemName: "sparkles")
                        .font(.system(size: 13, weight: .regular))
                        .foregroundStyle(route == .skills ? Color.accentColor : .secondary)
                        .frame(width: 18)
                    Text(skill.name)
                        .font(.system(size: 13, weight: route == .skills ? .semibold : .medium))
                        .lineLimit(1)
                    Spacer(minLength: 0)
                    Text(compactDate(skill.createdAt))
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                }
                .contentShape(Rectangle())
            }
            .buttonStyle(.plain)
            .accessibilityLabel(skill.name)

            Button(role: .destructive) {
                Task { await store.deleteSkill(id: skill.id) }
            } label: {
                Image(systemName: "trash")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(.secondary)
                    .frame(width: 22, height: 22)
                    .background(HippoTheme.subtleFill, in: RoundedRectangle(cornerRadius: 5, style: .continuous))
            }
            .buttonStyle(.borderless)
            .help("Delete skill")
        }
        .frame(height: 32)
        .contextMenu {
            Button("Delete", role: .destructive) {
                Task { await store.deleteSkill(id: skill.id) }
            }
        }
    }

    private var isRecording: Bool {
        store.snapshot.services.contains { service in
            service.name.localizedCaseInsensitiveCompare("ownscribe") == .orderedSame && service.status == "recording"
        } || store.snapshot.jarvisState == .meetingActive || store.snapshot.jarvisState == .sopMarking
    }

    private var identitySubtitle: String {
        if isRecording {
            return "Recording · \(currentDuration)"
        }
        return store.shortStateLabel(store.snapshot.jarvisState)
    }

    private var currentDuration: String {
        guard let session = store.snapshot.currentSession,
              let start = ISO8601DateFormatter().date(from: session.startedAt)
        else { return "live" }
        let seconds = max(0, Int(Date().timeIntervalSince(start)))
        return String(format: "%02d:%02d", seconds / 60, seconds % 60)
    }

    private var liveEventCount: Int {
        max(store.eventHistory.count, store.snapshot.currentTask == nil ? 0 : 1)
    }

    private func compactDate(_ value: String) -> String {
        guard let date = ISO8601DateFormatter().date(from: value) else { return "Local" }
        return date.formatted(.dateTime.month(.abbreviated).day())
    }
}

struct DashboardPageShell<Toolbar: View, Content: View>: View {
    @EnvironmentObject private var store: AppStateStore
    let title: String
    var subtitle: String?
    let toolbar: Toolbar
    let content: Content

    init(
        title: String,
        subtitle: String? = nil,
        @ViewBuilder toolbar: () -> Toolbar,
        @ViewBuilder content: () -> Content
    ) {
        self.title = title
        self.subtitle = subtitle
        self.toolbar = toolbar()
        self.content = content()
    }

    var body: some View {
        VStack(spacing: 0) {
            HStack(spacing: 8) {
                toolbar
            }
            .frame(height: 44)
            .padding(.horizontal, 14)
            .overlay(alignment: .bottom) {
                HippoHairline()
            }
            if let error = store.lastError, !error.isEmpty {
                HStack(spacing: 8) {
                    Image(systemName: "exclamationmark.circle.fill")
                        .foregroundStyle(.orange)
                    Text(error)
                        .font(.system(size: 12))
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                    Spacer()
                    Button {
                        store.lastError = nil
                    } label: {
                        Image(systemName: "xmark")
                            .font(.system(size: 11, weight: .semibold))
                            .frame(width: 22, height: 22)
                    }
                    .buttonStyle(.plain)
                    .foregroundStyle(.secondary)
                }
                .padding(.horizontal, 14)
                .frame(minHeight: 34)
                .background(.orange.opacity(0.08))
                .overlay(alignment: .bottom) {
                    HippoHairline()
                }
            }
            content
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .navigationTitle(title)
        .modifier(DashboardNavigationSubtitle(subtitle: subtitle))
    }
}

private struct DashboardNavigationSubtitle: ViewModifier {
    var subtitle: String?

    func body(content: Content) -> some View {
        if let subtitle {
            content.navigationSubtitle(subtitle)
        } else {
            content
        }
    }
}

struct DashboardSegmented: View {
    let items: [String]
    @Binding var selection: String
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        HStack(spacing: 0) {
            ForEach(items, id: \.self) { item in
                segmentedButton(item)
            }
        }
        .padding(2)
        .background(
            RoundedRectangle(cornerRadius: 7, style: .continuous)
                .fill(HippoTheme.segmentedBackground)
                .overlay {
                    RoundedRectangle(cornerRadius: 7, style: .continuous)
                        .strokeBorder(HippoTheme.hairline, lineWidth: 0.5)
                }
        )
        .accessibilityLabel("Filter")
    }

    private func segmentedButton(_ item: String) -> some View {
        let selected = item == selection
        return Button {
            select(item)
        } label: {
            Text(item)
                .font(.system(size: 12, weight: .medium))
                .lineLimit(1)
                .padding(.horizontal, 10)
                .frame(minWidth: 36)
                .frame(height: 24)
                .background(cellBackground(selected: selected))
        }
        .buttonStyle(.plain)
        .foregroundStyle(selected ? .primary : .secondary)
        .accessibilityLabel(item)
        .accessibilityValue(selected ? "Selected" : "")
    }

    private func select(_ item: String) {
        if reduceMotion {
            selection = item
        } else {
            withAnimation(.easeInOut(duration: 0.15)) {
                selection = item
            }
        }
    }

    private func cellBackground(selected: Bool) -> some View {
        RoundedRectangle(cornerRadius: 5, style: .continuous)
            .fill(selected ? selectedFill : Color.clear)
            .shadow(color: selected ? .black.opacity(0.06) : .clear, radius: 0.5, y: 1)
    }

    private var selectedFill: Color {
        Color(nsColor: .controlBackgroundColor).opacity(0.95)
    }
}

private struct DashboardSearchField: View {
    var placeholder = "Search"
    @Binding var text: String

    var body: some View {
        HStack(spacing: 6) {
            Image(systemName: "magnifyingglass")
                .font(.system(size: 12))
                .foregroundStyle(.secondary)
            TextField(placeholder, text: $text)
                .textFieldStyle(.plain)
                .font(.system(size: 12))
        }
        .padding(.horizontal, 10)
        .frame(width: 200, height: 28)
        .background(HippoTheme.subtleFill, in: RoundedRectangle(cornerRadius: 7, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 7, style: .continuous)
                .strokeBorder(HippoTheme.hairline, lineWidth: 0.5)
        }
    }
}

private struct DashboardLiveSignalView: View {
    @EnvironmentObject private var store: AppStateStore
    @State private var filter = "All"
    @State private var search = ""
    @State private var collapsedGroups: Set<String> = ["eng-standup", "design-review"]

    var body: some View {
        DashboardPageShell(
            title: "Live Signal",
            subtitle: "\(store.snapshot.currentSession?.title ?? "No session") · \(events.count) events"
        ) {
            DashboardSegmented(items: ["All", "Signals", "Tasks", "Artifacts"], selection: $filter)
            Spacer()
            HStack(spacing: 6) {
                HippoStatusDot(color: .green, pulse: true, size: 6)
                Text("SSE · /events")
                    .font(.system(size: 12))
                    .foregroundStyle(.secondary)
            }
            DashboardSearchField(placeholder: "Filter events", text: $search)
            HippoSymbolButton(systemName: "arrow.clockwise", title: "Refresh") {
                Task { await store.refresh() }
            }
        } content: {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    eventGroup(id: "current", title: store.snapshot.currentSession?.title ?? "Current signal", status: store.snapshot.currentSession == nil ? nil : "Active", duration: currentDuration, rows: filteredEvents)
                    eventGroup(id: "eng-standup", title: "Eng standup", status: nil, duration: "yesterday · archived", rows: [])
                    eventGroup(id: "design-review", title: "Design review", status: nil, duration: "Mon · archived", rows: [])
                }
                .padding(24)
            }
        }
    }

    private var events: [EventRecord] {
        store.eventHistory.isEmpty ? [currentEvent] : store.eventHistory
    }

    private var filteredEvents: [EventRecord] {
        let query = search.trimmingCharacters(in: .whitespacesAndNewlines)
        let byFilter = events.filter { event in
            switch filter {
            case "Tasks":
                event.type.contains("task")
            case "Artifacts":
                event.type.contains("artifact") || event.type.contains("transcript")
            case "Signals":
                event.type.contains("session") || event.type.contains("sop")
            default:
                true
            }
        }
        guard !query.isEmpty else { return byFilter }
        return byFilter.filter { event in
            event.type.localizedCaseInsensitiveContains(query)
                || event.payload.values.map(\.compactDescription).joined(separator: " ").localizedCaseInsensitiveContains(query)
        }
    }

    private var currentEvent: EventRecord {
        EventRecord(
            id: "current-\(store.snapshot.jarvisState.rawValue)",
            type: store.snapshot.currentTask == nil ? "session_state" : "active_task_generated",
            timestamp: ISO8601DateFormatter().string(from: Date()),
            sessionId: store.snapshot.currentSession?.id,
            payload: [
                "status": .string(store.stateName(store.snapshot.jarvisState)),
                "message": .string(store.statusMessage)
            ]
        )
    }

    private func eventGroup(id: String, title: String, status: String?, duration: String, rows: [EventRecord]) -> some View {
        DisclosureGroup(isExpanded: eventGroupExpansion(id)) {
            HippoInsetPanel {
                VStack(spacing: 0) {
                    ForEach(rows) { event in
                        eventRow(event)
                        if event.id != rows.last?.id {
                            HippoHairline()
                        }
                    }
                }
            }
            .padding(.top, 8)
        } label: {
            HStack(spacing: 8) {
                Text(title)
                    .font(.system(size: 13, weight: .semibold))
                if let status {
                    HippoCapsuleLabel(title: status, color: .red, systemImage: "circle.fill")
                }
                Spacer()
                Text(duration)
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
            }
            .contentShape(Rectangle())
        }
        .disclosureGroupStyle(.automatic)
        .padding(.horizontal, 4)
        .padding(.vertical, 8)
    }

    private func eventGroupExpansion(_ id: String) -> Binding<Bool> {
        Binding {
            !collapsedGroups.contains(id)
        } set: { expanded in
            if expanded {
                collapsedGroups.remove(id)
            } else {
                collapsedGroups.insert(id)
            }
        }
    }

    private func eventRow(_ event: EventRecord) -> some View {
        let meta = eventVisual(event)
        return HStack(alignment: .top, spacing: 12) {
            Text(eventTime(event.timestamp))
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(.secondary)
                .frame(width: 70, alignment: .leading)
                .padding(.top, 2)
            Image(systemName: meta.icon)
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(meta.color)
                .frame(width: 22, height: 22)
                .background(meta.color.opacity(0.12), in: RoundedRectangle(cornerRadius: 5, style: .continuous))
            VStack(alignment: .leading, spacing: 2) {
                Text(event.type.hippoTitleCasedEvent)
                    .font(.system(size: 13, weight: .semibold))
                Text(eventDetail(event))
                    .font(.system(size: 12.5))
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
                if let sessionId = event.sessionId {
                    Text("session: \(String(sessionId.prefix(8)))")
                        .font(.system(size: 11, design: .monospaced))
                        .foregroundStyle(.tertiary)
                }
            }
            Spacer()
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
    }

    private var currentDuration: String {
        guard let session = store.snapshot.currentSession,
              let start = ISO8601DateFormatter().date(from: session.startedAt)
        else { return "live" }
        let seconds = max(0, Int(Date().timeIntervalSince(start)))
        return String(format: "%02d:%02d · live", seconds / 60, seconds % 60)
    }

    private func eventVisual(_ event: EventRecord) -> (icon: String, color: Color) {
        if event.type.contains("task") { return ("target", .blue) }
        if event.type.contains("artifact") { return ("doc.text.fill", .green) }
        if event.type.contains("transcript") || event.type.contains("asr") { return ("mic.fill", .green) }
        if event.type.contains("sop") { return ("pin.fill", .orange) }
        return ("record.circle", .red)
    }

    private func eventDetail(_ event: EventRecord) -> String {
        if let action = event.payload["action"]?.compactDescription { return action }
        if let status = event.payload["status"]?.compactDescription { return status }
        if let message = event.payload["message"]?.compactDescription { return message }
        return event.payload.keys.sorted().prefix(3).joined(separator: " · ")
    }

    private func eventTime(_ value: String) -> String {
        guard let date = ISO8601DateFormatter().date(from: value) else { return value }
        return date.formatted(date: .omitted, time: .standard)
    }
}

private struct DashboardActiveTaskView: View {
    @EnvironmentObject private var store: AppStateStore
    @State private var tab = "Awaiting"

    var body: some View {
        DashboardPageShell(
            title: "Active Task"
        ) {
            DashboardSegmented(items: ["Awaiting", "Completed", "Ignored"], selection: $tab)
            Spacer()
            Button("Ignore") {
                ignoreCurrentTask()
            }
                .buttonStyle(HippoPushButtonStyle(.neutral))
                .disabled(store.isBusy)
            Button {
                insertCurrentTaskDraft()
            } label: {
                Label("Insert draft", systemImage: "arrow.right.to.line")
            }
            .buttonStyle(HippoPushButtonStyle(.preferred))
            .disabled(store.isBusy)
        } content: {
            ScrollView {
                if let task = store.snapshot.currentTask {
                    VStack(alignment: .leading, spacing: 24) {
                        taskHero(task)
                        taskMeta(task)
                        taskActions(task)
                        recentTasks
                    }
                    .frame(maxWidth: 820, alignment: .leading)
                    .padding(.vertical, 24)
                    .padding(.horizontal, 28)
                    .frame(maxWidth: .infinity)
                } else {
                    emptyState
                }
            }
        }
    }

    private func taskHero(_ task: ActiveTask) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HippoCapsuleLabel(title: "Awaiting review", color: .blue, systemImage: "target")
            Text(task.title)
                .font(.system(size: 28, weight: .bold))
                .lineLimit(2)
            Text(task.intent)
                .font(.system(size: 15))
                .foregroundStyle(.secondary)
                .lineLimit(4)
                .frame(maxWidth: 620, alignment: .leading)
        }
    }

    private func taskMeta(_ task: ActiveTask) -> some View {
        HippoInsetPanel {
            HStack(spacing: 0) {
                HippoMetadataCell(label: "Surface", value: task.proposedActions.first?.type.hippoTitleCasedEvent ?? "Mail · draft")
                verticalHairline
                HippoMetadataCell(label: "Confidence", value: "\(Int(task.confidence * 100))%")
                verticalHairline
                HippoMetadataCell(label: "Source", value: String((task.artifacts.first?.id ?? task.id).prefix(8)), mono: true)
                verticalHairline
                HippoMetadataCell(label: "Insertion", value: "Mock", muted: true)
            }
            .padding(.vertical, 12)
        }
    }

    private func taskActions(_ task: ActiveTask) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Proposed actions")
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(.secondary)
                .textCase(.uppercase)
                .padding(.horizontal, 4)
            HippoInsetPanel {
                VStack(spacing: 0) {
                    ForEach(Array(task.proposedActions.enumerated()), id: \.element.id) { offset, action in
                        HStack(spacing: 14) {
                            Text("\(offset + 1)")
                                .font(.system(size: 11, weight: .bold))
                                .foregroundStyle(.secondary)
                                .frame(width: 22, height: 22)
                                .background(HippoTheme.subtleFill, in: RoundedRectangle(cornerRadius: 5, style: .continuous))
                            VStack(alignment: .leading, spacing: 2) {
                                Text(action.label)
                                    .font(.system(size: 13, weight: .semibold))
                                Text(action.type.hippoTitleCasedEvent)
                                    .font(.system(size: 12))
                                    .foregroundStyle(.secondary)
                            }
                            Spacer()
                            HippoCapsuleLabel(title: action.status ?? "Ready", color: .green)
                        }
                        .padding(.horizontal, 16)
                        .padding(.vertical, 12)
                        if action.id != task.proposedActions.last?.id {
                            HippoHairline()
                        }
                    }
                }
            }
        }
    }

    private var recentTasks: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text("Recent")
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(.secondary)
                .textCase(.uppercase)
                .padding(.horizontal, 4)
            HippoInsetPanel {
                VStack(spacing: 0) {
                    recentTaskRow("Post standup recap to Linear", sub: "Eng standup · yesterday", state: "Completed", color: .green)
                    HippoHairline()
                    recentTaskRow("Drop design review summary into Figma", sub: "Design review · Mon", state: "Completed", color: .green)
                    HippoHairline()
                    recentTaskRow("Send 1:1 recap to Hana", sub: "1:1 · May 6", state: "Ignored", color: .secondary)
                }
            }
        }
    }

    private var emptyState: some View {
        VStack(spacing: 10) {
            Image(systemName: "target")
                .font(.system(size: 32))
                .foregroundStyle(.secondary)
            Text("No task awaiting review.")
                .font(.system(size: 20, weight: .semibold))
            Text("Live signal continues in the background.")
                .foregroundStyle(.secondary)
            Button("Open Live Signal") {
                UserDefaults.standard.set(DashboardRouteID.liveSignal.rawValue, forKey: DashboardRouteID.storageKey)
            }
            .buttonStyle(HippoPushButtonStyle(.preferred))
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .padding(60)
    }

    private var verticalHairline: some View {
        Rectangle().fill(HippoTheme.hairline).frame(width: 0.5, height: 38).padding(.horizontal, 16)
    }

    private func ignoreCurrentTask() {
        guard store.snapshot.currentTask != nil else {
            store.lastError = "No task awaiting review."
            return
        }
        Task { await store.ignoreCurrentTask() }
    }

    private func insertCurrentTaskDraft() {
        guard store.snapshot.currentTask != nil else {
            store.lastError = "No task awaiting review."
            return
        }
        Task { await store.confirmCurrentTask() }
    }

    private func recentTaskRow(_ title: String, sub: String, state: String, color: Color) -> some View {
        HStack(spacing: 14) {
            Image(systemName: "target")
                .foregroundStyle(.secondary)
            VStack(alignment: .leading, spacing: 1) {
                Text(title)
                    .font(.system(size: 13, weight: .medium))
                Text(sub)
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
            }
            Spacer()
            HippoCapsuleLabel(title: state, color: color)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
    }
}

private struct DashboardSessionsView: View {
    @EnvironmentObject private var store: AppStateStore
    @State private var tab = "All"
    @State private var search = ""
    private let startedColumnWidth: CGFloat = 150
    private let durationColumnWidth: CGFloat = 84
    private let artifactsColumnWidth: CGFloat = 86
    private let stateColumnWidth: CGFloat = 132
    private let chevronColumnWidth: CGFloat = 28

    var body: some View {
        DashboardPageShell(
            title: "Sessions"
        ) {
            DashboardSegmented(items: ["All", "Active", "Archived"], selection: $tab)
            Spacer()
            DashboardSearchField(placeholder: "Search sessions", text: $search)
            HippoSymbolButton(systemName: "arrow.clockwise", title: "Refresh") {
                Task { await store.refresh() }
            }
        } content: {
            ScrollView {
                VStack(spacing: 0) {
                    tableHeader
                    HippoInsetPanel {
                        VStack(spacing: 0) {
                            ForEach(sessions) { session in
                                sessionRow(session)
                                if session.id != sessions.last?.id {
                                    HippoHairline()
                                }
                            }
                        }
                    }
                }
                .padding(24)
            }
        }
    }

    private var tableHeader: some View {
        HStack(spacing: 14) {
            headerCell("Session")
                .frame(maxWidth: .infinity, alignment: .leading)
            headerCell("Started")
                .frame(width: startedColumnWidth, alignment: .leading)
            headerCell("Duration")
                .frame(width: durationColumnWidth, alignment: .trailing)
            headerCell("Artifacts")
                .frame(width: artifactsColumnWidth, alignment: .trailing)
            headerCell("State")
                .frame(width: stateColumnWidth, alignment: .leading)
            Color.clear.frame(width: chevronColumnWidth)
        }
        .padding(.horizontal, 16)
        .padding(.bottom, 8)
    }

    private var sessions: [SessionListItem] {
        var items: [SessionListItem] = []
        if let current = store.snapshot.currentSession {
            items.append(SessionListItem(session: current, state: store.snapshot.currentTask == nil ? "Completed" : "Active Task"))
        }
        items.append(contentsOf: [
            SessionListItem(id: "dem_9c4", title: "Eng standup", started: "Yesterday 10:30", duration: "18:32", artifacts: 2, state: "Completed"),
            SessionListItem(id: "dem_77b", title: "Design review", started: "Mon 2:00 PM", duration: "47:18", artifacts: 6, state: "Completed"),
            SessionListItem(id: "dem_4f1", title: "1:1 — Hana", started: "May 6", duration: "32:04", artifacts: 3, state: "Completed")
        ])

        let query = search.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !query.isEmpty else { return items }
        return items.filter { $0.title.localizedCaseInsensitiveContains(query) || $0.id.localizedCaseInsensitiveContains(query) }
    }

    private func sessionRow(_ item: SessionListItem) -> some View {
        HStack(spacing: 14) {
            HStack(spacing: 10) {
                Image(systemName: "record.circle")
                    .foregroundStyle(item.state == "Active Task" ? Color.accentColor : .secondary)
                VStack(alignment: .leading, spacing: 1) {
                    Text(item.title)
                        .font(.system(size: 13, weight: .semibold))
                        .lineLimit(1)
                    Text(item.id)
                        .font(.system(size: 11, design: .monospaced))
                        .foregroundStyle(.secondary)
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            Text(item.started)
                .font(.system(size: 12))
                .foregroundStyle(.secondary)
                .lineLimit(1)
                .frame(width: startedColumnWidth, alignment: .leading)
            Text(item.duration)
                .font(.system(size: 12, design: .monospaced))
                .frame(width: durationColumnWidth, alignment: .trailing)
            Text("\(item.artifacts)")
                .font(.system(size: 12, design: .monospaced))
                .frame(width: artifactsColumnWidth, alignment: .trailing)
            HippoCapsuleLabel(title: item.state, color: item.state == "Active Task" ? .blue : .green)
                .frame(width: stateColumnWidth, alignment: .leading)
            Image(systemName: "chevron.right")
                .foregroundStyle(.tertiary)
                .frame(width: chevronColumnWidth)
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(item.state == "Active Task" ? HippoTheme.subtleFill : .clear)
    }

    private func headerCell(_ title: String) -> some View {
        Text(title.uppercased())
            .font(.system(size: 10, weight: .bold))
            .foregroundStyle(.secondary)
    }
}

private struct SessionListItem: Identifiable {
    var id: String
    var title: String
    var started: String
    var duration: String
    var artifacts: Int
    var state: String

    init(id: String, title: String, started: String, duration: String, artifacts: Int, state: String) {
        self.id = id
        self.title = title
        self.started = started
        self.duration = duration
        self.artifacts = artifacts
        self.state = state
    }

    init(session: DemoSession, state: String) {
        self.id = String(session.id.prefix(8))
        self.title = session.title
        self.started = session.startedAt
        self.duration = session.endedAt == nil ? "live" : "done"
        self.artifacts = session.artifacts.count
        self.state = state
    }
}

private struct DashboardSkillView: View {
    @EnvironmentObject private var store: AppStateStore
    @State private var mode = "Preview"
    @State private var search = ""

    private var selectedSkill: SkillRecord? {
        if !store.snapshot.skills.isEmpty {
            return store.snapshot.skills.first
        }
        return nil
    }

    var body: some View {
        DashboardPageShell(
            title: selectedSkill?.name ?? "Skill Library",
            subtitle: selectedSkill == nil ? "No skill selected" : "SKILL.md"
        ) {
            DashboardSegmented(items: ["Preview", "Source"], selection: $mode)
            Text("Preview · Source")
                .font(.system(size: 12))
                .foregroundStyle(.secondary)
            Spacer()
            DashboardSearchField(placeholder: "Search skills", text: $search)
            Button {
                Task { await store.generateSkill() }
            } label: {
                Label("Generate", systemImage: "sparkles")
            }
            .buttonStyle(HippoPushButtonStyle(.neutral))
            Button {
                UserDefaults.standard.set(DashboardRouteID.chat.rawValue, forKey: DashboardRouteID.storageKey)
            } label: {
                Label("Run skill", systemImage: "play.fill")
            }
            .buttonStyle(HippoPushButtonStyle(.preferred))
        } content: {
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    if let skill = selectedSkill {
                        skillHeader(skill)
                        skillBody(skill)
                    } else {
                        ContentUnavailableView("No skills", systemImage: "sparkles", description: Text("Generate a Skill from a captured session to see it here."))
                    }
                }
                .frame(maxWidth: 720, alignment: .leading)
                .padding(.vertical, 28)
                .padding(.horizontal, 40)
                .frame(maxWidth: .infinity)
            }
        }
    }

    private func skillHeader(_ skill: SkillRecord) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 8) {
                Image(systemName: "sparkles")
                    .foregroundStyle(Color.accentColor)
                    .frame(width: 24, height: 24)
                    .background(Color.accentColor.opacity(0.12), in: RoundedRectangle(cornerRadius: 6, style: .continuous))
                Text("SKILL · \(skill.name)")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(Color.accentColor)
                HippoCapsuleLabel(title: "mock", color: .orange)
            }
            Text(skill.name)
                .font(.system(size: 32, weight: .heavy))
            Text(skill.description)
                .font(.system(size: 15))
                .foregroundStyle(.secondary)
                .lineLimit(3)
            HStack(spacing: 16) {
                inlineMeta("Source", value: skill.sourceSessionId.map { String($0.prefix(8)) } ?? "Local", mono: true)
                inlineMeta("Created", value: compactDate(skill.createdAt))
                inlineMeta("Size", value: "\(skill.content.count) chars")
                inlineMeta("Generator", value: skill.sourceSessionId == nil ? "Local" : "Cortex (mock)")
            }
            .padding(.top, 8)
            .padding(.bottom, 20)
        }
    }

    private func skillBody(_ skill: SkillRecord) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            if mode == "Source" {
                Text(skill.content)
                    .font(.system(size: 12.5, design: .monospaced))
                    .textSelection(.enabled)
                    .padding(16)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(HippoTheme.subtleFill, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
            } else {
                DashboardSkillMarkdownView(markdown: skill.content)
                if !skill.content.localizedCaseInsensitiveContains("[!callout]") {
                    mockCallout
                }
            }
        }
    }

    private var mockCallout: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: "shield.checkered")
                .foregroundStyle(.blue)
            Text("Insertion is guarded by target-surface preflight. This build only calls cua-driver after a safe editable target is detected and the user confirms.")
                .font(.system(size: 14))
        }
        .padding(14)
        .background(.orange.opacity(0.10), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .strokeBorder(.orange.opacity(0.30), lineWidth: 0.5)
        }
    }

    private func inlineMeta(_ label: String, value: String, mono: Bool = false) -> some View {
        VStack(alignment: .leading, spacing: 1) {
            Text(label.uppercased())
                .font(.system(size: 10, weight: .semibold))
                .foregroundStyle(.secondary)
            Text(value)
                .font(.system(size: 13, weight: .medium, design: mono ? .monospaced : .default))
        }
    }

    private func compactDate(_ value: String) -> String {
        guard let date = ISO8601DateFormatter().date(from: value) else { return value }
        return date.formatted(.dateTime.month(.abbreviated).day().hour().minute())
    }
}

private struct DashboardSkillMarkdownView: View {
    let markdown: String

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            ForEach(blocks) { block in
                blockView(block)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .textSelection(.enabled)
    }

    private var blocks: [DashboardSkillMarkdownBlock] {
        DashboardSkillMarkdownParser(markdown: markdown).blocks
    }

    @ViewBuilder
    private func blockView(_ block: DashboardSkillMarkdownBlock) -> some View {
        switch block.kind {
        case .heading:
            Text(block.text.uppercased())
                .font(.system(size: 11, weight: .bold))
                .tracking(0.66)
                .foregroundStyle(.secondary)
                .padding(.top, 8)
        case .paragraph:
            Text(block.text)
                .font(.system(size: 14))
                .lineSpacing(4)
                .foregroundStyle(.primary)
        case .bullet:
            HStack(alignment: .top, spacing: 8) {
                Text("•")
                    .font(.system(size: 14, weight: .semibold))
                    .foregroundStyle(.secondary)
                Text(block.text)
                    .font(.system(size: 14))
                    .lineSpacing(4)
            }
        case .code:
            ScrollView(.horizontal) {
                Text(block.text)
                    .font(.system(size: 12.5, design: .monospaced))
                    .foregroundStyle(.primary)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(16)
            }
            .background(HippoTheme.subtleFill, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 10, style: .continuous)
                    .strokeBorder(HippoTheme.hairline, lineWidth: 0.5)
            }
        case .callout:
            HStack(alignment: .top, spacing: 10) {
                Image(systemName: "shield.checkered")
                    .foregroundStyle(.orange)
                Text(block.text)
                    .font(.system(size: 14))
                    .lineSpacing(4)
            }
            .padding(14)
            .background(.orange.opacity(0.10), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .strokeBorder(.orange.opacity(0.30), lineWidth: 0.5)
            }
        }
    }
}

private struct DashboardSkillMarkdownBlock: Identifiable {
    enum Kind {
        case heading
        case paragraph
        case bullet
        case code
        case callout
    }

    let id = UUID()
    let kind: Kind
    let text: String
}

private struct DashboardSkillMarkdownParser {
    let markdown: String

    var blocks: [DashboardSkillMarkdownBlock] {
        var result: [DashboardSkillMarkdownBlock] = []
        var paragraph: [String] = []
        var code: [String] = []
        var callout: [String] = []
        var inCode = false
        var inCallout = false

        func flushParagraph(_ target: inout [DashboardSkillMarkdownBlock], _ lines: inout [String]) {
            let text = lines.joined(separator: " ").trimmingCharacters(in: .whitespacesAndNewlines)
            if !text.isEmpty {
                target.append(DashboardSkillMarkdownBlock(kind: .paragraph, text: text))
            }
            lines.removeAll()
        }

        func flushCode(_ target: inout [DashboardSkillMarkdownBlock], _ lines: inout [String]) {
            let text = lines.joined(separator: "\n").trimmingCharacters(in: .newlines)
            if !text.isEmpty {
                target.append(DashboardSkillMarkdownBlock(kind: .code, text: text))
            }
            lines.removeAll()
        }

        func flushCallout(_ target: inout [DashboardSkillMarkdownBlock], _ lines: inout [String]) {
            let text = lines.joined(separator: " ").trimmingCharacters(in: .whitespacesAndNewlines)
            if !text.isEmpty {
                target.append(DashboardSkillMarkdownBlock(kind: .callout, text: text))
            }
            lines.removeAll()
        }

        for rawLine in markdown.components(separatedBy: .newlines) {
            let line = rawLine.trimmingCharacters(in: .whitespaces)

            if line.hasPrefix("```") {
                if inCode {
                    flushCode(&result, &code)
                    inCode = false
                } else {
                    flushParagraph(&result, &paragraph)
                    inCallout = false
                    inCode = true
                }
                continue
            }

            if inCode {
                code.append(rawLine)
                continue
            }

            if line.isEmpty {
                flushParagraph(&result, &paragraph)
                if inCallout {
                    flushCallout(&result, &callout)
                    inCallout = false
                }
                continue
            }

            if line.hasPrefix(">") {
                flushParagraph(&result, &paragraph)
                var text = String(line.dropFirst()).trimmingCharacters(in: .whitespaces)
                if text.localizedCaseInsensitiveContains("[!callout]") {
                    text = text.replacingOccurrences(of: "[!callout]", with: "", options: .caseInsensitive)
                        .trimmingCharacters(in: .whitespaces)
                }
                callout.append(text)
                inCallout = true
                continue
            }

            if inCallout {
                flushCallout(&result, &callout)
                inCallout = false
            }

            if line.hasPrefix("## ") {
                flushParagraph(&result, &paragraph)
                result.append(DashboardSkillMarkdownBlock(kind: .heading, text: String(line.dropFirst(3))))
            } else if line.hasPrefix("# ") {
                flushParagraph(&result, &paragraph)
                result.append(DashboardSkillMarkdownBlock(kind: .heading, text: String(line.dropFirst(2))))
            } else if line.hasPrefix("- ") || line.hasPrefix("* ") {
                flushParagraph(&result, &paragraph)
                result.append(DashboardSkillMarkdownBlock(kind: .bullet, text: String(line.dropFirst(2))))
            } else {
                paragraph.append(line)
            }
        }

        if inCode {
            flushCode(&result, &code)
        }
        if inCallout {
            flushCallout(&result, &callout)
        }
        flushParagraph(&result, &paragraph)
        return result
    }
}

private struct DashboardSettingsView: View {
    @EnvironmentObject private var store: AppStateStore
    @AppStorage("orchestratorBaseURL") private var orchestratorBaseURL = "http://127.0.0.1:8787"
    @State private var tab = "General"

    var body: some View {
        DashboardPageShell(
            title: "Settings",
            subtitle: "Developer Console"
        ) {
            DashboardSegmented(items: ["General", "Services", "Recording", "Permissions", "About"], selection: $tab)
            Spacer()
            HippoSymbolButton(systemName: "arrow.clockwise", title: "Refresh") {
                Task {
                    await store.refresh()
                    await store.refreshOwnscribeConsole()
                }
            }
        } content: {
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    orchestratorSection
                    servicesSection
                    openChronicleSection
                    cuaDriverSection
                    permissionsSection
                    aboutSection
                }
                .frame(maxWidth: 760)
                .padding(.vertical, 24)
                .padding(.horizontal, 32)
                .frame(maxWidth: .infinity)
            }
            .task {
                await store.refreshOwnscribeConsole()
            }
        }
    }

    private var orchestratorSection: some View {
        formSection("Orchestrator", footnote: "Hippo will launch a local Orchestrator if this address is unreachable.") {
            formRow("Base URL", sub: "FastAPI on 127.0.0.1:8787") {
                TextField("Base URL", text: $orchestratorBaseURL)
                    .textFieldStyle(.roundedBorder)
                    .font(.system(size: 12.5, design: .monospaced))
                    .frame(width: 240)
            }
            HippoHairline()
            formRow("Status") {
                HStack(spacing: 6) {
                    HippoStatusDot(color: store.snapshot.jarvisState == .error ? .orange : .green, size: 7)
                    Text("\(store.stateName(store.snapshot.jarvisState)) · \(store.eventHistory.count) events buffered")
                        .font(.system(size: 12.5))
                }
            }
            HippoHairline()
            formRow("Auto-launch on app start") {
                Toggle("", isOn: .constant(true))
                    .toggleStyle(.switch)
                    .controlSize(.mini)
                    .labelsHidden()
            }
        }
    }

    private var servicesSection: some View {
        formSection("Services") {
            ForEach(store.snapshot.services.isEmpty ? placeholderServices : store.snapshot.services) { service in
                serviceFormRow(service)
                if service.id != (store.snapshot.services.isEmpty ? placeholderServices : store.snapshot.services).last?.id {
                    HippoHairline()
                }
            }
        }
    }

    private var openChronicleSection: some View {
        formSection("OpenChronicle", footnote: "Daemon commands run synchronously; capture-once and timeline-tick are safe at any time.") {
            formRow("Daemon", sub: "status, start/stop/pause/resume") {
                HStack(spacing: 6) {
                    commandButton("Start") { await store.openChronicleStart() }
                    commandButton("Pause") { await store.openChroniclePause() }
                    commandButton("Stop", variant: .destructive) { await store.openChronicleStop() }
                }
            }
            HippoHairline()
            formRow("Capture") {
                HStack(spacing: 6) {
                    commandButton("Capture once") { await store.openChronicleCaptureOnce() }
                    commandButton("Timeline tick") { await store.openChronicleTimelineTick() }
                }
            }
            HippoHairline()
            formRow("Captures index") {
                commandButton("Rebuild") { await store.openChronicleRebuildCapturesIndex() }
            }
        }
    }

    private var cuaDriverSection: some View {
        formSection("cua-driver", footnote: "Controls the local macOS Computer Use daemon used after target-surface preflight.") {
            formRow("Daemon", sub: cuaDriverService.map { store.serviceDetail($0.detail, status: $0.status) } ?? "Not reported") {
                HStack(spacing: 6) {
                    commandButton("Start") { await store.cuaDriverStart() }
                    commandButton("Restart") { await store.cuaDriverRestart() }
                    commandButton("Stop", variant: .destructive) { await store.cuaDriverStop() }
                }
            }
        }
    }


    private var permissionsSection: some View {
        formSection("Permissions", footnote: "Hippo cannot grant these for you. Open System Settings to authorize.") {
            permissionRow("Microphone", sub: "Required for ownscribe recording", icon: "mic.fill", granted: true)
            HippoHairline()
            permissionRow("Screen Recording", sub: "Required for OpenChronicle window capture", icon: "eye.fill", granted: true)
            HippoHairline()
            permissionRow("Accessibility", sub: "Required when cua-driver executes a real insertion", icon: "figure.wave", granted: false)
        }
    }

    private var aboutSection: some View {
        formSection("About") {
            formRow("HippoJarvis", sub: "Build 2026.05.13 · macOS 26 Tahoe") {
                Text("0.4.1-demo")
                    .font(.system(size: 12, design: .monospaced))
                    .foregroundStyle(.secondary)
            }
            HippoHairline()
            formRow("Diagnostics", sub: "Export runtime log + state snapshot") {
                Button("Export...") {
                    store.lastError = "Diagnostics export is not wired in this demo build yet."
                }
                    .buttonStyle(HippoPushButtonStyle(.neutral, size: .sm))
            }
        }
    }

    private var placeholderServices: [ServiceStatus] {
        [
            ServiceStatus(id: "openchronicle", name: "OpenChronicle", status: "idle", detail: "Capture · timeline · index"),
            ServiceStatus(id: "ownscribe", name: "ownscribe", status: "idle", detail: "Recording not active"),
            ServiceStatus(id: "cua-driver", name: "cua-driver", status: "idle", detail: "Computer Use daemon not checked"),
            ServiceStatus(id: "vlmac", name: "vlmac", status: "idle", detail: "Video capture not in main path")
        ]
    }

    private var cuaDriverService: ServiceStatus? {
        store.snapshot.services.first { $0.name.localizedCaseInsensitiveCompare("cua-driver") == .orderedSame }
    }

    private func formSection<Content: View>(_ title: String, footnote: String? = nil, @ViewBuilder content: () -> Content) -> some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title.uppercased())
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(.secondary)
                .padding(.horizontal, 4)
            HippoInsetPanel {
                VStack(spacing: 0) {
                    content()
                }
            }
            if let footnote {
                Text(footnote)
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 6)
            }
        }
    }

    private func formRow<Control: View>(_ label: String, sub: String? = nil, @ViewBuilder control: () -> Control) -> some View {
        HStack(spacing: 12) {
            VStack(alignment: .leading, spacing: 2) {
                Text(label)
                    .font(.system(size: 13, weight: .medium))
                if let sub {
                    Text(sub)
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                }
            }
            Spacer()
            control()
        }
        .padding(.horizontal, 14)
        .frame(minHeight: 44)
    }

    private func serviceFormRow(_ service: ServiceStatus) -> some View {
        HStack(spacing: 12) {
            HippoStatusDot(color: HippoTheme.stateColor(service.status), pulse: service.status == "recording", size: 8)
            VStack(alignment: .leading, spacing: 2) {
                Text(service.name)
                    .font(.system(size: 13, weight: .semibold, design: .monospaced))
                Text(store.serviceDetail(service.detail, status: service.status))
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
            Spacer()
            Text(store.serviceStatus(service.status))
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(.secondary)
            Image(systemName: "chevron.right")
                .foregroundStyle(.tertiary)
        }
        .padding(.horizontal, 14)
        .frame(minHeight: 52)
    }

    private func permissionRow(_ label: String, sub: String, icon: String, granted: Bool) -> some View {
        formRow(label, sub: sub) {
            HStack(spacing: 8) {
                HippoCapsuleLabel(title: granted ? "Granted" : "Not granted", color: granted ? .green : .orange, systemImage: "circle.fill")
                Button(granted ? "Manage" : "Open Settings") {
                    openSecurityPreferences()
                }
                .buttonStyle(HippoPushButtonStyle(.neutral, size: .sm))
            }
        }
        .overlay(alignment: .leading) {
            Image(systemName: icon)
                .foregroundStyle(.secondary)
                .frame(width: 28, height: 28)
                .background(HippoTheme.subtleFill, in: RoundedRectangle(cornerRadius: 7, style: .continuous))
                .padding(.leading, -36)
        }
        .padding(.leading, 36)
    }

    private func commandButton(_ title: String, variant: HippoPushVariant = .neutral, action: @escaping () async -> Void) -> some View {
        Button(title) {
            Task { await action() }
        }
        .buttonStyle(HippoPushButtonStyle(variant, size: .sm))
        .disabled(store.isBusy)
    }

    private func openSecurityPreferences() {
        guard let url = URL(string: "x-apple.systempreferences:com.apple.preference.security") else { return }
        NSWorkspace.shared.open(url)
    }
}
