import AppKit
import SwiftUI

struct DashboardChatView: View {
    @EnvironmentObject private var store: AppStateStore
    @State private var tab = "Chat"
    @State private var draft = ""
    @State private var sandboxPreviewEnabled = false
    @State private var confirmSandboxTakeOver = false

    var body: some View {
        DashboardPageShell(
            title: "Chat",
            subtitle: "Hippo · local agent"
        ) {
            DashboardSegmented(items: ["Chat", "Recent", "Templates", "Files", "Sandbox"], selection: $tab)
            Spacer()
            modelPicker
            HippoSymbolButton(systemName: "square.and.pencil", title: "New chat") {
                tab = "Chat"
                if manusAvailable {
                    Task { await store.newManusThread() }
                } else {
                    store.startLocalManusDraftThread()
                }
            }
        } content: {
            dashboardContent
                .task {
                    await store.refreshManus()
                }
        }
    }

    @ViewBuilder
    private var dashboardContent: some View {
        switch tab {
        case "Recent":
            recentContent
        case "Templates":
            templatesContent
        case "Files":
            filesContent
        case "Sandbox":
            sandboxContent
        default:
            if hasMessages {
                conversationContent
            } else {
                emptyContent
            }
        }
    }

    private var emptyContent: some View {
        VStack {
            Spacer(minLength: 16)
            VStack(spacing: 0) {
                sessionPill
                Text("What should Hippo do?")
                    .font(.system(size: 42, weight: .regular, design: .serif))
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

    private var conversationContent: some View {
        VStack(spacing: 0) {
            ScrollViewReader { proxy in
                ScrollView {
                    VStack(alignment: .leading, spacing: 14) {
                        conversationHeader
                        ForEach(Array(store.manusMessages.enumerated()), id: \.offset) { offset, message in
                            messageRow(message)
                                .id(offset)
                        }
                        streamSidePanel
                    }
                    .frame(maxWidth: 820, alignment: .leading)
                    .padding(.horizontal, 28)
                    .padding(.vertical, 24)
                    .frame(maxWidth: .infinity)
                }
                .onChange(of: store.manusMessages.count) { _, count in
                    guard count > 0 else { return }
                    withAnimation(.easeOut(duration: 0.18)) {
                        proxy.scrollTo(count - 1, anchor: .bottom)
                    }
                }
            }

            HippoHairline()
            composer
                .frame(maxWidth: 820)
                .padding(.horizontal, 28)
                .padding(.top, 14)
                .padding(.bottom, 18)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    private var modelPicker: some View {
        Button {
            Task { await store.refreshManus() }
        } label: {
            Label(modelTitle, systemImage: "cpu")
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
            HippoStatusDot(color: manusAvailable ? .green : .red, pulse: manusAvailable && store.snapshot.currentSession != nil, size: 6)
            Text("Manus \(manusStatus) · \(sessionPillTitle)")
                .font(.system(size: 12))
                .foregroundStyle(.secondary)
            Button("Attach") {
                appendComposerToken("[current session]")
            }
                .buttonStyle(HippoPushButtonStyle(.plain, size: .sm))
                .foregroundStyle(Color.accentColor)
        }
        .padding(.leading, 12)
        .padding(.trailing, 4)
        .padding(.vertical, 5)
        .background(HippoTheme.subtleFill, in: Capsule())
        .padding(.bottom, 22)
    }

    private var conversationHeader: some View {
        HStack(alignment: .center, spacing: 12) {
            VStack(alignment: .leading, spacing: 4) {
                Text(store.currentManusThread.flatMap { threadTitle($0) } ?? "Current thread")
                    .font(.system(size: 24, weight: .semibold))
                    .lineLimit(2)
                HStack(spacing: 8) {
                    HippoCapsuleLabel(title: manusStatus, color: manusAvailable ? .green : .red, systemImage: "circle.fill")
                    Text("\(store.manusMessages.count) messages")
                        .font(.system(size: 12))
                        .foregroundStyle(.secondary)
                }
            }
            Spacer()
            Button {
                Task { await store.stopManusThread() }
            } label: {
                Label("Stop", systemImage: "stop.circle")
            }
            .buttonStyle(HippoPushButtonStyle(.neutral))
        }
        .padding(.bottom, 8)
    }

    private var composer: some View {
        VStack(spacing: 12) {
            DashboardComposerTextView(text: $draft, placeholder: composerPlaceholder)
                .frame(minHeight: 56, maxHeight: 80)

            HStack(spacing: 6) {
                roundControl("plus.circle") { appendComposerToken("Attach: ") }
                toolChipGroup
                roundControl("display") { appendComposerToken("[screen context]") }
                Spacer()
                roundControl("livephoto") { appendComposerToken("[live audio]") }
                roundControl("mic.fill") { appendComposerToken("[voice note]") }
                Button {
                    sendDraft()
                } label: {
                    Image(systemName: "arrow.up.circle.fill")
                        .font(.system(size: 18, weight: .semibold))
                        .frame(width: 30, height: 30)
                }
                .buttonStyle(.plain)
                .foregroundStyle(canSend ? Color.accentColor : .secondary)
                .disabled(!canSend)
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
            let icons = toolIcons
            ForEach(Array(icons.prefix(3).enumerated()), id: \.offset) { offset, icon in
                toolDot(icon.systemName, color: icon.color)
            }
            if icons.count > 3 {
                Text("+\(icons.count - 3)")
                    .font(.system(size: 11, weight: .semibold))
                    .foregroundStyle(.secondary)
                    .padding(.leading, 4)
            }
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
            Text(manusAvailable ? "Connect more tools to Hippo" : "Manus unavailable")
                .font(.system(size: 12))
                .foregroundStyle(.secondary)
            Spacer()
            ForEach(toolIcons.prefix(5), id: \.systemName) { icon in
                Image(systemName: icon.systemName)
                    .font(.system(size: 9, weight: .bold))
                    .foregroundStyle(.white)
                    .frame(width: 18, height: 18)
                    .background(icon.color, in: RoundedRectangle(cornerRadius: 5, style: .continuous))
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
                Button(title) {
                    sendSuggestion(title)
                }
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
                Button("See all") {
                    tab = "Recent"
                }
                .buttonStyle(.plain)
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(Color.accentColor)
            }
            .padding(.horizontal, 8)

            HippoInsetPanel(radius: 12) {
                VStack(spacing: 0) {
                    if store.manusThreads.isEmpty {
                        Text("No recent Manus threads")
                            .font(.system(size: 12))
                            .foregroundStyle(.secondary)
                            .frame(maxWidth: .infinity, alignment: .leading)
                            .padding(.horizontal, 14)
                            .padding(.vertical, 12)
                    } else {
                        ForEach(Array(store.manusThreads.prefix(3).enumerated()), id: \.offset) { offset, thread in
                            threadRow(thread)
                            if offset < min(store.manusThreads.count, 3) - 1 {
                                HippoHairline()
                            }
                        }
                    }
                }
            }
        }
    }

    private var recentContent: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                sectionHeader("Recent Manus Threads", subtitle: "\(store.manusThreads.count) local Hippo thread records")
                recentThreads
            }
            .frame(maxWidth: 820, alignment: .leading)
            .padding(28)
            .frame(maxWidth: .infinity, alignment: .top)
        }
    }

    private var templatesContent: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                sectionHeader("Prompt Templates", subtitle: "Click a template to send it to Manus")
                suggestionChips
                HippoInsetPanel {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Local draft fallback")
                            .font(.system(size: 13, weight: .semibold))
                        Text("When Manus is unavailable, template clicks are kept as local draft messages instead of disappearing.")
                            .font(.system(size: 12))
                            .foregroundStyle(.secondary)
                    }
                    .padding(14)
                }
            }
            .frame(maxWidth: 820, alignment: .leading)
            .padding(28)
            .frame(maxWidth: .infinity, alignment: .top)
        }
    }

    private var filesContent: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                sectionHeader("Sandbox Files", subtitle: currentThreadSubtitle)
                HStack(spacing: 8) {
                    Button {
                        loadFilesFromCurrentThread()
                    } label: {
                        Label(store.isLoadingManusFiles ? "Loading" : "Refresh files", systemImage: "arrow.clockwise")
                    }
                    .buttonStyle(HippoPushButtonStyle(.neutral))

                    if let count = store.manusFilesResponse.count {
                        HippoCapsuleLabel(title: "\(count) files", color: .blue, systemImage: "doc")
                    }
                }

                HippoInsetPanel {
                    VStack(spacing: 0) {
                        if store.currentManusThread == nil {
                            emptyPanelText("Create or select a Manus thread before browsing sandbox files.")
                        } else if store.manusFiles.isEmpty {
                            emptyPanelText("No sandbox files loaded.")
                        } else {
                            ForEach(Array(store.manusFiles.enumerated()), id: \.offset) { offset, file in
                                fileRow(file)
                                if offset < store.manusFiles.count - 1 {
                                    HippoHairline()
                                }
                            }
                        }
                    }
                }

                if let preview = store.manusFilePreview {
                    filePreview(preview)
                }
            }
            .frame(maxWidth: 900, alignment: .leading)
            .padding(28)
            .frame(maxWidth: .infinity, alignment: .top)
        }
        .task(id: store.currentManusThread?.id) {
            guard store.currentManusThread != nil, store.manusFiles.isEmpty else { return }
            await store.loadManusFiles()
        }
    }

    private var sandboxContent: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                sectionHeader("Manus Sandbox", subtitle: currentThreadSubtitle)
                HippoInsetPanel {
                    VStack(alignment: .leading, spacing: 14) {
                        HStack(alignment: .top, spacing: 12) {
                            Image(systemName: "display.and.arrow.down")
                                .font(.system(size: 22, weight: .semibold))
                                .foregroundStyle(Color.accentColor)
                                .frame(width: 42, height: 42)
                                .background(Color.accentColor.opacity(0.12), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
                            VStack(alignment: .leading, spacing: 4) {
                                Text("Sandbox access is on demand")
                                    .font(.system(size: 16, weight: .semibold))
                                Text("Hippo opens ai-manus' own VNC/takeover surface only after you request it. The main Jarvis path stays read-only here.")
                                    .font(.system(size: 12))
                                    .foregroundStyle(.secondary)
                            }
                            Spacer()
                            HippoCapsuleLabel(title: store.manusSandboxAccess?.status ?? "standby", color: store.manusSandboxAccess == nil ? .secondary : .green, systemImage: "circle.fill")
                        }

                        HStack(spacing: 8) {
                            Button {
                                prepareSandboxAccess()
                            } label: {
                                Label(store.isLoadingManusSandboxAccess ? "Preparing" : "Prepare sandbox", systemImage: "key.viewfinder")
                            }
                            .buttonStyle(HippoPushButtonStyle(.preferred))

                            Button {
                                openSandboxURL(interactive: false)
                            } label: {
                                Label("Open viewer", systemImage: "rectangle.on.rectangle")
                            }
                            .buttonStyle(HippoPushButtonStyle(.neutral))

                            Button {
                                guard store.manusSandboxAccess?.takeOverUrl != nil else {
                                    store.lastError = "Take Over URL is not available yet."
                                    return
                                }
                                confirmSandboxTakeOver = true
                            } label: {
                                Label("Take Over", systemImage: "cursorarrow.motionlines")
                            }
                            .buttonStyle(HippoPushButtonStyle(.neutral))
                        }

                        if let access = store.manusSandboxAccess {
                            sandboxAccessDetails(access)
                        } else {
                            Text("No signed sandbox access has been requested for this thread.")
                                .font(.system(size: 12))
                                .foregroundStyle(.secondary)
                        }
                    }
                    .padding(16)
                }
            }
            .frame(maxWidth: 900, alignment: .leading)
            .padding(28)
            .frame(maxWidth: .infinity, alignment: .top)
        }
        .confirmationDialog(
            "Open interactive Take Over?",
            isPresented: $confirmSandboxTakeOver,
            titleVisibility: .visible
        ) {
            Button("Open Take Over") {
                openSandboxURL(interactive: true)
            }
            Button("Cancel", role: .cancel) {}
        } message: {
            Text("This opens the interactive ai-manus VNC surface. Use it only when you intend to control the sandbox.")
        }
    }

    private var streamSidePanel: some View {
        HStack(alignment: .top, spacing: 12) {
            planColumn
            toolsColumn
        }
        .padding(.top, 8)
    }

    private var planColumn: some View {
        HippoInsetPanel {
            VStack(alignment: .leading, spacing: 8) {
                Label("Plan", systemImage: "list.bullet.rectangle")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(.secondary)
                if store.manusPlan.isEmpty {
                    Text("No active plan")
                        .font(.system(size: 12))
                        .foregroundStyle(.secondary)
                } else {
                    ForEach(store.manusPlan.prefix(4)) { step in
                        HStack(alignment: .top, spacing: 6) {
                            Circle()
                                .fill(HippoTheme.stateColor(step.status))
                                .frame(width: 6, height: 6)
                                .padding(.top, 5)
                            Text(step.description.isEmpty ? step.status : step.description)
                                .font(.system(size: 12))
                                .foregroundStyle(.secondary)
                                .lineLimit(2)
                        }
                    }
                }
            }
            .padding(12)
        }
    }

    private var toolsColumn: some View {
        HippoInsetPanel {
            VStack(alignment: .leading, spacing: 8) {
                Label("Tools", systemImage: "hammer")
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(.secondary)
                if store.manusTools.isEmpty {
                    Text("No tools active")
                        .font(.system(size: 12))
                        .foregroundStyle(.secondary)
                } else {
                    ForEach(Array(store.manusTools.prefix(4).enumerated()), id: \.offset) { _, tool in
                        Text(displayText(tool, fallback: "Tool"))
                            .font(.system(size: 12))
                            .lineLimit(1)
                    }
                }
            }
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(12)
        }
    }

    private func messageRow(_ message: Any) -> some View {
        let role = fieldString(message, keys: ["role", "author", "sender"]) ?? "assistant"
        let content = fieldString(message, keys: ["content", "text", "message"]) ?? displayText(message, fallback: "")
        let isUser = role.localizedCaseInsensitiveContains("user")

        return HStack(alignment: .top) {
            if isUser { Spacer(minLength: 80) }
            VStack(alignment: .leading, spacing: 5) {
                Text(role.hippoTitleCasedEvent)
                    .font(.system(size: 10, weight: .bold))
                    .foregroundStyle(.secondary)
                    .textCase(.uppercase)
                Text(content)
                    .font(.system(size: 14))
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 11)
            .background(isUser ? Color.accentColor.opacity(0.12) : HippoTheme.panelFill, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .strokeBorder(HippoTheme.hairline, lineWidth: 0.5)
            }
            if !isUser { Spacer(minLength: 80) }
        }
    }

    private func threadRow(_ thread: Any) -> some View {
        Button {
            guard let id = threadID(thread) else {
                store.lastError = "Thread is missing an id."
                return
            }
            Task { await store.loadManusThread(id) }
        } label: {
            HStack(spacing: 12) {
                Image(systemName: threadIcon(thread))
                    .font(.system(size: 13, weight: .medium))
                    .foregroundStyle(threadColor(thread))
                    .frame(width: 28, height: 28)
                    .background(threadColor(thread).opacity(0.14), in: RoundedRectangle(cornerRadius: 7, style: .continuous))
                VStack(alignment: .leading, spacing: 2) {
                    Text(threadTitle(thread) ?? "Untitled thread")
                        .font(.system(size: 13, weight: .medium))
                        .lineLimit(1)
                    Text(threadSubtitle(thread))
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
        .buttonStyle(.plain)
    }

    private func sectionHeader(_ title: String, subtitle: String) -> some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(title)
                .font(.system(size: 24, weight: .semibold))
            Text(subtitle)
                .font(.system(size: 12))
                .foregroundStyle(.secondary)
                .lineLimit(2)
        }
    }

    private func emptyPanelText(_ text: String) -> some View {
        Text(text)
            .font(.system(size: 12))
            .foregroundStyle(.secondary)
            .frame(maxWidth: .infinity, alignment: .leading)
            .padding(14)
    }

    private func fileRow(_ file: ManusFileInfo) -> some View {
        HStack(spacing: 12) {
            Image(systemName: file.isDirectory == true ? "folder" : "doc.text")
                .font(.system(size: 14, weight: .medium))
                .foregroundStyle(file.isDirectory == true ? .orange : Color.accentColor)
                .frame(width: 30, height: 30)
                .background(HippoTheme.subtleFill, in: RoundedRectangle(cornerRadius: 8, style: .continuous))

            VStack(alignment: .leading, spacing: 3) {
                Text(file.displayName)
                    .font(.system(size: 13, weight: .semibold))
                    .lineLimit(1)
                Text([file.typeLabel, file.effectiveSize.map(formatBytes), file.path ?? file.filePath].compactMap { $0 }.joined(separator: " · "))
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
            Spacer(minLength: 0)

            Button("Preview") {
                Task { await store.loadManusFilePreview(file) }
            }
            .buttonStyle(HippoPushButtonStyle(.neutral, size: .sm))

            Button("Open") {
                openFile(file)
            }
            .buttonStyle(HippoPushButtonStyle(.neutral, size: .sm))
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 10)
    }

    private func filePreview(_ preview: ManusFilePreview) -> some View {
        HippoInsetPanel {
            VStack(alignment: .leading, spacing: 10) {
                HStack {
                    Label(preview.displayName, systemImage: "doc.text.magnifyingglass")
                        .font(.system(size: 13, weight: .semibold))
                    Spacer()
                    if preview.truncated == true {
                        HippoCapsuleLabel(title: "truncated", color: .orange)
                    }
                }
                ScrollView {
                    Text(preview.previewText ?? "No text preview available.")
                        .font(.system(size: 12, design: .monospaced))
                        .textSelection(.enabled)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .padding(12)
                }
                .frame(minHeight: 120, maxHeight: 260)
                .background(Color(nsColor: .textBackgroundColor).opacity(0.72), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
            }
            .padding(14)
        }
    }

    private func sandboxAccessDetails(_ access: ManusSandboxAccess) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            if let takeOver = access.takeOverUrl {
                metadataLine("Takeover", takeOver)
            }
            if let interactive = access.interactiveUrl {
                metadataLine("Viewer", interactive)
            }
            if let websocket = access.websocketUrl {
                metadataLine("WebSocket", websocket)
            }
        }
    }

    private func metadataLine(_ label: String, _ value: String) -> some View {
        HStack(alignment: .firstTextBaseline, spacing: 8) {
            Text(label)
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(.secondary)
                .frame(width: 72, alignment: .leading)
            Text(value)
                .font(.system(size: 11, design: .monospaced))
                .foregroundStyle(.secondary)
                .lineLimit(1)
                .truncationMode(.middle)
        }
    }

    private func roundControl(_ systemName: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
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

    private func sendDraft() {
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        draft = ""
        if manusAvailable {
            Task { await store.sendManusMessage(text) }
        } else {
            store.queueLocalManusDraft(text)
        }
    }

    private func sendSuggestion(_ title: String) {
        let text = prompt(for: title)
        if manusAvailable {
            Task { await store.sendManusMessage(text) }
        } else {
            store.queueLocalManusDraft(text)
        }
    }

    private func openSandboxURL(interactive: Bool) {
        guard let raw = interactive ? store.manusSandboxAccess?.takeOverUrl : store.manusSandboxAccess?.interactiveEntryURL,
              let url = URL(string: raw)
        else {
            store.lastError = interactive ? "Take Over URL is not available yet." : "Sandbox viewer URL is not available yet."
            return
        }
        NSWorkspace.shared.open(url)
    }

    private func openFile(_ file: ManusFileInfo) {
        if let raw = file.fileUrl, let url = URL(string: raw) {
            NSWorkspace.shared.open(url)
            return
        }
        Task {
            if let link = await store.loadManusDownloadLink(for: file), let url = link.downloadURL {
                NSWorkspace.shared.open(url)
            }
        }
    }

    private func loadFilesFromCurrentThread() {
        guard store.currentManusThread != nil else {
            store.lastError = "Create or select a Manus thread before browsing sandbox files."
            return
        }
        Task { await store.loadManusFiles() }
    }

    private func prepareSandboxAccess() {
        guard store.currentManusThread != nil else {
            store.lastError = "Create or select a Manus thread before requesting sandbox access."
            return
        }
        Task { await store.loadManusSandboxAccess() }
    }

    private func appendComposerToken(_ token: String) {
        if draft.isEmpty {
            draft = token
        } else {
            draft += draft.hasSuffix(" ") ? token : " \(token)"
        }
    }

    private func prompt(for suggestion: String) -> String {
        switch suggestion {
        case "Generate a skill":
            return "Review the current Hippo context and propose a reusable Skill.md for this workflow. Keep it actionable and concise."
        case "Draft follow-up":
            return "Draft a concise follow-up message based on the current session context. Include next steps if they are available."
        case "Summarize last session":
            return "Summarize the latest Hippo session into key decisions, action items, and open questions."
        case "Start capture":
            return "Help me plan what to capture for a reusable workflow skill in the current context."
        default:
            return suggestion
        }
    }

    private var hasMessages: Bool {
        !store.manusMessages.isEmpty
    }

    private var canSend: Bool {
        !draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !store.isBusy
    }

    private var manusAvailable: Bool {
        !manusStatus.localizedCaseInsensitiveContains("unavailable")
            && !manusStatus.localizedCaseInsensitiveContains("offline")
            && !manusStatus.localizedCaseInsensitiveContains("error")
            && !manusStatus.localizedCaseInsensitiveContains("auth")
    }

    private var manusStatus: String {
        if store.aiManusStatus.ok != true {
            return "unavailable"
        }
        if store.snapshot.jarvisState == .error {
            return "unavailable"
        }
        return store.aiManusStatus.status.isEmpty ? "available" : store.aiManusStatus.status
    }

    private var composerPlaceholder: String {
        manusAvailable
            ? "Assign a task, ask Hippo to draft something, or describe what to capture next..."
            : "Manus is unavailable. You can keep a draft here until the agent reconnects."
    }

    private var sessionPillTitle: String {
        if let title = store.snapshot.currentSession?.title, !title.isEmpty {
            return title
        }
        if let title = store.currentManusThread?.title, !title.isEmpty {
            return title
        }
        if let id = store.currentManusThread?.manusSessionId ?? store.currentManusThread?.sessionId {
            return String(id.suffix(8))
        }
        return "none"
    }

    private var currentThreadSubtitle: String {
        guard let thread = store.currentManusThread else {
            return "No Manus thread selected"
        }
        let title = thread.title?.isEmpty == false ? thread.title! : String((thread.manusSessionId ?? thread.sessionId).suffix(8))
        return "Thread \(title) · \(thread.status)"
    }

    private var modelTitle: String {
        if let provider = store.aiManusConfig.authProvider, !provider.isEmpty {
            return "Manus · \(provider)"
        }
        if let apiBaseURL = store.aiManusConfig.apiBaseUrl, !apiBaseURL.isEmpty {
            return "Manus · \(apiBaseURL)"
        }
        return "Hippo Mini · local"
    }

    private var toolIcons: [(systemName: String, color: Color)] {
        let mapped = store.manusTools.map { tool in
            let name = displayText(tool, fallback: "tool").lowercased()
            if name.contains("mail") || name.contains("email") { return ("envelope.fill", Color.red) }
            if name.contains("calendar") { return ("calendar", Color.blue) }
            if name.contains("code") || name.contains("shell") { return ("chevron.left.forwardslash.chevron.right", Color.black) }
            if name.contains("browser") { return ("globe", Color.green) }
            return ("wrench.and.screwdriver.fill", Color.accentColor)
        }
        return mapped.isEmpty
            ? [("envelope.fill", .red), ("calendar", .blue), ("chevron.left.forwardslash.chevron.right", .black), ("bubble.left.and.bubble.right.fill", .green), ("square.and.pencil", .orange)]
            : mapped
    }

    private func threadID(_ value: Any) -> String? {
        fieldString(value, keys: ["id", "threadID", "threadId"])
    }

    private func threadTitle(_ value: Any) -> String? {
        fieldString(value, keys: ["title", "name", "summary"])
    }

    private func threadSubtitle(_ value: Any) -> String {
        let turns = fieldString(value, keys: ["turnCount", "messageCount", "messagesCount"]).map { "\($0) turns" }
        let status = fieldString(value, keys: ["status", "state"])
        let updated = fieldString(value, keys: ["updatedAt", "lastUpdatedAt", "createdAt"])
        return [turns, status, updated].compactMap { $0 }.joined(separator: " · ")
    }

    private func threadIcon(_ value: Any) -> String {
        let text = displayText(value, fallback: "").lowercased()
        if text.contains("mail") || text.contains("reply") { return "envelope.fill" }
        if text.contains("skill") { return "sparkles" }
        if text.contains("session") || text.contains("summary") { return "clock.arrow.circlepath" }
        return "bubble.left.and.bubble.right.fill"
    }

    private func threadColor(_ value: Any) -> Color {
        let text = displayText(value, fallback: "").lowercased()
        if text.contains("mail") || text.contains("reply") { return .red }
        if text.contains("skill") { return .orange }
        if text.contains("session") || text.contains("summary") { return .blue }
        return Color.accentColor
    }

    private func displayText(_ value: Any, fallback: String) -> String {
        let value = unwrapOptional(value) ?? value
        if let text = value as? String, !text.isEmpty {
            return text
        }
        if let title = threadTitle(value), !title.isEmpty {
            return title
        }
        let reflected = Mirror(reflecting: value)
        let fields = reflected.children.compactMap { child -> String? in
            guard let label = child.label else { return nil }
            if label.hasPrefix("_") { return nil }
            let text = String(describing: child.value)
            guard !text.isEmpty, text != "nil" else { return nil }
            return "\(label): \(text)"
        }
        let text = fields.prefix(4).joined(separator: " · ")
        return text.isEmpty ? fallback : text
    }

    private func fieldString(_ value: Any, keys: [String]) -> String? {
        guard let value = unwrapOptional(value) ?? Optional(value) else {
            return nil
        }
        let mirror = Mirror(reflecting: value)
        for child in mirror.children {
            guard let label = child.label else { continue }
            guard keys.contains(where: { $0.caseInsensitiveCompare(label) == .orderedSame }) else { continue }
            let raw = String(describing: child.value)
            let cleaned = raw
                .trimmingCharacters(in: CharacterSet(charactersIn: "Optional()"))
                .trimmingCharacters(in: .whitespacesAndNewlines)
            if !cleaned.isEmpty, cleaned != "nil" {
                return cleaned
            }
        }
        return nil
    }

    private func unwrapOptional(_ value: Any) -> Any? {
        let mirror = Mirror(reflecting: value)
        guard mirror.displayStyle == .optional else { return value }
        return mirror.children.first?.value
    }

    private func formatBytes(_ value: Double) -> String {
        let units = ["B", "KB", "MB", "GB"]
        var amount = max(0, value)
        var index = 0
        while amount >= 1024, index < units.count - 1 {
            amount /= 1024
            index += 1
        }
        return index == 0 ? "\(Int(amount)) \(units[index])" : String(format: "%.1f %@", amount, units[index])
    }
}

private struct DashboardComposerTextView: NSViewRepresentable {
    @Binding var text: String
    var placeholder: String

    func makeCoordinator() -> Coordinator {
        Coordinator(text: $text)
    }

    func makeNSView(context: Context) -> ComposerContainerView {
        let view = ComposerContainerView()
        view.textView.delegate = context.coordinator
        return view
    }

    func updateNSView(_ view: ComposerContainerView, context: Context) {
        context.coordinator.text = $text
        if view.textView.string != text {
            view.textView.string = text
        }
        view.placeholderLabel.stringValue = placeholder
        view.placeholderLabel.isHidden = !text.isEmpty
    }

    final class Coordinator: NSObject, NSTextViewDelegate {
        var text: Binding<String>

        init(text: Binding<String>) {
            self.text = text
        }

        func textDidChange(_ notification: Notification) {
            guard let textView = notification.object as? NSTextView else { return }
            text.wrappedValue = textView.string
        }
    }

    final class ComposerContainerView: NSView {
        let scrollView = NSScrollView()
        let textView = NSTextView()
        let placeholderLabel = NSTextField(labelWithString: "")

        override var isFlipped: Bool { true }

        override init(frame frameRect: NSRect) {
            super.init(frame: frameRect)
            configureTextView()
            configurePlaceholder()
            addSubview(scrollView)
            addSubview(placeholderLabel)
        }

        required init?(coder: NSCoder) {
            fatalError("init(coder:) has not been implemented")
        }

        override func layout() {
            super.layout()
            scrollView.frame = bounds
            textView.frame = bounds
            textView.minSize = NSSize(width: 0, height: bounds.height)
            textView.maxSize = NSSize(width: CGFloat.greatestFiniteMagnitude, height: CGFloat.greatestFiniteMagnitude)
            textView.textContainer?.containerSize = NSSize(width: bounds.width, height: CGFloat.greatestFiniteMagnitude)
            placeholderLabel.frame = NSRect(x: 0, y: 0, width: bounds.width, height: 22)
        }

        private func configureTextView() {
            scrollView.borderType = .noBorder
            scrollView.drawsBackground = false
            scrollView.hasVerticalScroller = false
            scrollView.hasHorizontalScroller = false
            scrollView.autohidesScrollers = true

            textView.drawsBackground = false
            textView.font = .systemFont(ofSize: 15)
            textView.textColor = .labelColor
            textView.insertionPointColor = .controlAccentColor
            textView.isRichText = false
            textView.importsGraphics = false
            textView.allowsUndo = true
            textView.isEditable = true
            textView.isSelectable = true
            textView.isHorizontallyResizable = false
            textView.isVerticallyResizable = true
            textView.textContainerInset = .zero
            textView.textContainer?.lineFragmentPadding = 0
            textView.textContainer?.widthTracksTextView = true
            textView.textContainer?.heightTracksTextView = false
            scrollView.documentView = textView
        }

        private func configurePlaceholder() {
            placeholderLabel.font = .systemFont(ofSize: 15)
            placeholderLabel.textColor = .secondaryLabelColor
            placeholderLabel.backgroundColor = .clear
            placeholderLabel.isBordered = false
            placeholderLabel.isEditable = false
            placeholderLabel.isSelectable = false
            placeholderLabel.lineBreakMode = .byTruncatingTail
        }
    }
}
