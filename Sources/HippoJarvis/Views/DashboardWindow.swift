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
                route: route,
                onSelect: { self.route = $0 }
            )
            .navigationSplitViewColumnWidth(min: 220, ideal: 240, max: 260)
        } detail: {
            detail
        }
        .navigationSplitViewStyle(.balanced)
        .frame(minWidth: 1024, idealWidth: 1280, minHeight: 640, idealHeight: 800)
        .background(.regularMaterial)
        .task {
            await store.bootstrap()
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
    let route: DashboardRouteID
    let onSelect: (DashboardRouteID) -> Void

    var body: some View {
        VStack(spacing: 0) {
            identityRow
            activityRows
            libraryRows
            Spacer(minLength: 0)
            footer
        }
        .padding(.horizontal, 8)
        .padding(.bottom, 8)
        .background(.thinMaterial)
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
        .padding(.horizontal, 8)
        .padding(.top, 8)
        .padding(.bottom, 14)
    }

    private var activityRows: some View {
        VStack(spacing: 0) {
            sidebarItem(.chat, trailing: "Beta")
            sidebarItem(.liveSignal, badge: "\(liveEventCount)")
            sidebarItem(.activeTask, badge: store.snapshot.currentTask == nil ? nil : "1", badgeAccent: true)
            sidebarItem(.sessions)
        }
    }

    private var libraryRows: some View {
        VStack(spacing: 0) {
            HStack {
                Text("Library")
                    .font(.system(size: 11, weight: .bold))
                    .foregroundStyle(.secondary)
                Spacer()
                Button {
                    Task { await store.generateSkill() }
                } label: {
                    Image(systemName: "plus")
                        .font(.system(size: 11, weight: .semibold))
                }
                .buttonStyle(.plain)
                .foregroundStyle(.secondary)
                .accessibilityLabel("Generate skill")
            }
            .padding(.horizontal, 12)
            .padding(.top, 10)
            .padding(.bottom, 4)

            ForEach(store.snapshot.skills.prefix(6)) { skill in
                skillRow(skill)
            }
        }
    }

    private var footer: some View {
        VStack(spacing: 8) {
            HippoHairline()
                .padding(.horizontal, -8)
            HStack(spacing: 8) {
                HippoSymbolButton(systemName: "gearshape", title: "Settings", active: route == .settings) {
                    onSelect(.settings)
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
    }

    private func sidebarItem(_ item: DashboardRouteID, trailing: String? = nil, badge: String? = nil, badgeAccent: Bool = false) -> some View {
        Button {
            onSelect(item)
        } label: {
            HStack(spacing: 8) {
                Image(systemName: item.icon)
                    .font(.system(size: 13, weight: .regular))
                    .frame(width: 20)
                    .foregroundStyle(route == item ? Color.accentColor : .secondary)
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
            .padding(.horizontal, 8)
            .background(route == item ? HippoTheme.sidebarSelected : .clear, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
        }
        .buttonStyle(.plain)
        .accessibilityLabel(item.title)
    }

    private func skillRow(_ skill: SkillRecord) -> some View {
        Button {
            onSelect(.skills)
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
            .frame(height: 32)
            .padding(.horizontal, 8)
            .background(route == .skills ? HippoTheme.sidebarSelected : .clear, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
        }
        .buttonStyle(.plain)
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

private struct DashboardPageShell<Toolbar: View, Content: View>: View {
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
            titlebar
            HStack(spacing: 8) {
                toolbar
            }
            .frame(height: 44)
            .padding(.horizontal, 14)
            .overlay(alignment: .bottom) {
                HippoHairline()
            }
            content
        }
        .background(HippoTheme.panelFill.opacity(0.56))
    }

    private var titlebar: some View {
        HStack(spacing: 10) {
            Text(title)
                .font(.system(size: 13, weight: .semibold))
            if let subtitle {
                Text(subtitle)
                    .font(.system(size: 12))
                    .foregroundStyle(.secondary)
            }
            Spacer(minLength: 0)
        }
        .frame(height: 32)
        .padding(.horizontal, 14)
    }
}

private struct DashboardSegmented: View {
    let items: [String]
    @Binding var selection: String

    var body: some View {
        Picker("", selection: $selection) {
            ForEach(items, id: \.self) { item in
                Text(item).tag(item)
            }
        }
        .pickerStyle(.segmented)
        .controlSize(.small)
        .frame(minWidth: CGFloat(items.count * 80))
        .accessibilityLabel("Filter")
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

private struct DashboardChatView: View {
    @EnvironmentObject private var store: AppStateStore
    @State private var tab = "Chat"
    @State private var draft = ""

    var body: some View {
        DashboardPageShell(
            title: "Chat",
            subtitle: "Hippo · local agent"
        ) {
            DashboardSegmented(items: ["Chat", "Recent", "Templates"], selection: $tab)
            Spacer()
            modelPicker
            HippoSymbolButton(systemName: "square.and.pencil", title: "New chat") {}
        } content: {
            VStack {
                Spacer(minLength: 16)
                VStack(spacing: 0) {
                    sessionPill
                    Text("What should Hippo do?")
                        .font(.custom("New York", size: 42).weight(.regular))
                        .multilineTextAlignment(.center)
                        .padding(.bottom, 24)
                    composer
                    connectTools
                    suggestionChips
                    recentThreads
                }
                .frame(maxWidth: 720)
                .padding(.horizontal, 28)
                Spacer(minLength: 16)
            }
            .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
    }

    private var modelPicker: some View {
        Button {} label: {
            Label("Hippo Mini · local", systemImage: "cpu")
                .font(.system(size: 12, weight: .medium))
                .padding(.horizontal, 12)
                .frame(height: 28)
                .background(HippoTheme.subtleFill, in: Capsule())
        }
        .buttonStyle(.plain)
        .foregroundStyle(.primary)
    }

    private var sessionPill: some View {
        HStack(spacing: 8) {
            HippoStatusDot(color: .red, pulse: store.snapshot.currentSession != nil, size: 6)
            Text("Active session · \(store.snapshot.currentSession?.title ?? "none")")
                .font(.system(size: 12))
                .foregroundStyle(.secondary)
            Button("Attach") {}
                .buttonStyle(HippoPushButtonStyle(.plain, size: .sm))
                .foregroundStyle(Color.accentColor)
        }
        .padding(.leading, 12)
        .padding(.trailing, 4)
        .padding(.vertical, 5)
        .background(HippoTheme.subtleFill, in: Capsule())
        .padding(.bottom, 22)
    }

    private var composer: some View {
        VStack(spacing: 12) {
            TextEditor(text: $draft)
                .font(.system(size: 15))
                .scrollContentBackground(.hidden)
                .frame(minHeight: 56, maxHeight: 80)
                .overlay(alignment: .topLeading) {
                    if draft.isEmpty {
                        Text("Assign a task, ask Hippo to draft something, or describe what to capture next...")
                            .font(.system(size: 15))
                            .foregroundStyle(.secondary)
                            .padding(.top, 8)
                            .padding(.leading, 5)
                            .allowsHitTesting(false)
                    }
                }

            HStack(spacing: 6) {
                roundControl("plus.circle")
                toolChipGroup
                roundControl("display")
                Spacer()
                roundControl("livephoto")
                roundControl("mic.fill")
                Button {} label: {
                    Image(systemName: "arrow.up.circle.fill")
                        .font(.system(size: 18, weight: .semibold))
                        .frame(width: 30, height: 30)
                }
                .buttonStyle(.plain)
                .foregroundStyle(draft.isEmpty ? .secondary : Color.accentColor)
            }
        }
        .padding(16)
        .background(Color(nsColor: .textBackgroundColor).opacity(0.88), in: RoundedRectangle(cornerRadius: 18, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 18, style: .continuous)
                .strokeBorder(HippoTheme.hairline, lineWidth: 0.5)
        }
        .shadow(color: .black.opacity(0.06), radius: 12, y: 5)
        .padding(.bottom, 12)
    }

    private var toolChipGroup: some View {
        HStack(spacing: 4) {
            toolDot("envelope.fill", color: .red)
            toolDot("calendar", color: .blue)
            toolDot("chevron.left.forwardslash.chevron.right", color: .black)
            Text("+2")
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(.secondary)
                .padding(.leading, 4)
        }
        .padding(.leading, 4)
        .padding(.trailing, 10)
        .frame(height: 30)
        .background(HippoTheme.subtleFill, in: Capsule())
    }

    private var connectTools: some View {
        HStack(spacing: 10) {
            Image(systemName: "wrench.and.screwdriver.fill")
                .foregroundStyle(.secondary)
            Text("Connect more tools to Hippo")
                .font(.system(size: 12))
                .foregroundStyle(.secondary)
            Spacer()
            ForEach(["envelope.fill", "calendar", "bubble.left.and.bubble.right.fill", "chevron.left.forwardslash.chevron.right", "square.and.pencil"], id: \.self) { icon in
                Image(systemName: icon)
                    .font(.system(size: 9, weight: .bold))
                    .foregroundStyle(.white)
                    .frame(width: 18, height: 18)
                    .background(Color.accentColor, in: RoundedRectangle(cornerRadius: 5, style: .continuous))
            }
            Image(systemName: "xmark")
                .font(.system(size: 11, weight: .medium))
                .foregroundStyle(.secondary)
        }
        .padding(.horizontal, 14)
        .frame(height: 36)
        .background(HippoTheme.subtleFill, in: Capsule())
        .overlay {
            Capsule().strokeBorder(HippoTheme.hairline, lineWidth: 0.5)
        }
        .padding(.bottom, 20)
    }

    private var suggestionChips: some View {
        HippoFlowLayout(spacing: 8) {
            ForEach(["Generate a skill", "Draft follow-up", "Summarize last session", "Start capture", "More"], id: \.self) { title in
                Button(title) {}
                    .buttonStyle(HippoPushButtonStyle(.neutral, size: .lg))
            }
        }
        .frame(maxWidth: .infinity)
        .padding(.bottom, 28)
    }

    private var recentThreads: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text("Recent threads")
                    .font(.system(size: 11, weight: .bold))
                    .foregroundStyle(.secondary)
                    .textCase(.uppercase)
                Spacer()
                Button("See all") {}
                    .buttonStyle(.plain)
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(Color.accentColor)
            }
            .padding(.horizontal, 8)

            HippoInsetPanel(radius: 12) {
                VStack(spacing: 0) {
                    threadRow("Draft a reply to Hana from the Ridgeline thread", sub: "3 turns · uses Mail · 2 min ago", icon: "envelope.fill", color: .red)
                    HippoHairline()
                    threadRow("Generate a skill that posts standup notes to Linear", sub: "7 turns · references latest session · yesterday", icon: "sparkles", color: .orange)
                    HippoHairline()
                    threadRow("Summarize the design review session", sub: "2 turns · references live signal · Mon", icon: "clock.arrow.circlepath", color: .blue)
                }
            }
        }
    }

    private func roundControl(_ systemName: String) -> some View {
        Button {} label: {
            Image(systemName: systemName)
                .font(.system(size: 13, weight: .medium))
                .frame(width: 30, height: 30)
                .background(.clear, in: Circle())
                .overlay {
                    Circle().strokeBorder(HippoTheme.hairline, lineWidth: 0.5)
                }
        }
        .buttonStyle(.plain)
        .foregroundStyle(.secondary)
    }

    private func toolDot(_ systemName: String, color: Color) -> some View {
        Image(systemName: systemName)
            .font(.system(size: 10, weight: .bold))
            .foregroundStyle(.white)
            .frame(width: 22, height: 22)
            .background(color, in: Circle())
            .overlay {
                Circle().strokeBorder(.white.opacity(0.85), lineWidth: 1.5)
            }
    }

    private func threadRow(_ title: String, sub: String, icon: String, color: Color) -> some View {
        HStack(spacing: 12) {
            Image(systemName: icon)
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(color)
                .frame(width: 28, height: 28)
                .background(color.opacity(0.14), in: RoundedRectangle(cornerRadius: 7, style: .continuous))
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.system(size: 13, weight: .medium))
                    .lineLimit(1)
                Text(sub)
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
            Spacer()
            Image(systemName: "chevron.right")
                .font(.system(size: 11, weight: .bold))
                .foregroundStyle(.tertiary)
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
    }
}

private struct DashboardLiveSignalView: View {
    @EnvironmentObject private var store: AppStateStore
    @State private var filter = "All"
    @State private var search = ""

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
                    eventGroup(title: store.snapshot.currentSession?.title ?? "Current signal", status: store.snapshot.currentSession == nil ? nil : "Active", duration: currentDuration, rows: filteredEvents)
                    eventGroup(title: "Eng standup", status: nil, duration: "yesterday · archived", rows: [], collapsed: true)
                    eventGroup(title: "Design review", status: nil, duration: "Mon · archived", rows: [], collapsed: true)
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

    private func eventGroup(title: String, status: String?, duration: String, rows: [EventRecord], collapsed: Bool = false) -> some View {
        VStack(alignment: .leading, spacing: 0) {
            HStack(spacing: 8) {
                Image(systemName: collapsed ? "chevron.right" : "chevron.down")
                    .font(.system(size: 11, weight: .bold))
                    .foregroundStyle(.secondary)
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
            .padding(.horizontal, 4)
            .padding(.vertical, 8)

            if !collapsed {
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
            Button("Ignore") { Task { await store.ignoreCurrentTask() } }
                .buttonStyle(HippoPushButtonStyle(.neutral))
                .disabled(store.snapshot.currentTask == nil || store.isBusy)
            Button {
                Task { await store.confirmCurrentTask() }
            } label: {
                Label("Insert draft", systemImage: "arrow.right.to.line")
            }
            .buttonStyle(HippoPushButtonStyle(.preferred))
            .disabled(store.snapshot.currentTask == nil || store.isBusy)
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
        Grid(horizontalSpacing: 14) {
            GridRow {
                headerCell("Session", alignment: .leading)
                headerCell("Started")
                headerCell("Duration", alignment: .trailing)
                headerCell("Artifacts", alignment: .trailing)
                headerCell("State")
                Color.clear.frame(width: 28)
            }
        }
        .padding(.horizontal, 12)
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
        Grid(horizontalSpacing: 14) {
            GridRow {
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
                Text(item.started).font(.system(size: 12)).foregroundStyle(.secondary)
                Text(item.duration).font(.system(size: 12, design: .monospaced)).gridColumnAlignment(.trailing)
                Text("\(item.artifacts)").font(.system(size: 12, design: .monospaced)).gridColumnAlignment(.trailing)
                HippoCapsuleLabel(title: item.state, color: item.state == "Active Task" ? .blue : .green)
                Image(systemName: "chevron.right").foregroundStyle(.tertiary).frame(width: 28)
            }
        }
        .padding(.horizontal, 16)
        .padding(.vertical, 12)
        .background(item.state == "Active Task" ? HippoTheme.subtleFill : .clear)
    }

    private func headerCell(_ title: String, alignment: Alignment = .leading) -> some View {
        Text(title.uppercased())
            .font(.system(size: 10, weight: .bold))
            .foregroundStyle(.secondary)
            .frame(maxWidth: .infinity, alignment: alignment)
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
            } else if let attributed = try? AttributedString(markdown: skill.content) {
                Text(attributed)
                    .font(.system(size: 14))
                    .lineSpacing(4)
                    .textSelection(.enabled)
                mockCallout
            } else {
                Text(skill.content)
                    .font(.system(size: 14))
                    .textSelection(.enabled)
                mockCallout
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
        .background(.blue.opacity(0.10), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .strokeBorder(.blue.opacity(0.30), lineWidth: 0.5)
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
                Button("Export...") {}
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
