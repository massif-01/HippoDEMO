import AppKit
import SwiftUI
import WebKit

struct DashboardChatView: View {
    @EnvironmentObject private var store: AppStateStore
    @State private var tab = "Chat"
    @State private var draft = ""
    @State private var confirmSandboxTakeOver = false
    @State private var computerPresentationMode: ComputerPresentationMode = .inlineCard
    @State private var composerFocusSeed = 0
    private let chatColumnMaxWidth: CGFloat = 768

    var body: some View {
        DashboardPageShell(
            title: "Hippo Manus",
            subtitle: currentThreadRemoteText
        ) {
            Button {
                tab = "Chat"
            } label: {
                HStack(spacing: 6) {
                    Text(toolbarThreadTitle)
                        .font(.system(size: 14, weight: .semibold))
                        .lineLimit(1)
                    Image(systemName: "chevron.down")
                        .font(.system(size: 9, weight: .bold))
                        .foregroundStyle(.secondary)
                }
                .padding(.horizontal, 10)
                .frame(height: 28)
                .background(tab == "Chat" ? HippoTheme.subtleFill : .clear, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
            }
            .buttonStyle(HippoPressFeedbackButtonStyle(cornerRadius: 8, pressedScale: 0.96, overlayOpacity: 0.12))
            .foregroundStyle(.primary)

            modelPicker
            Spacer()
            HippoSymbolButton(systemName: "list.bullet.rectangle", title: "Task progress", active: tab == "Plan") {
                tab = "Plan"
            }
            HippoSymbolButton(systemName: "doc.text", title: "Files", active: tab == "Files") {
                tab = "Files"
            }
            HippoSymbolButton(systemName: "display", title: "Hippo computer", active: computerPresentationMode == .sidePanel) {
                showComputer(.sidePanel)
            }
            HippoSymbolButton(systemName: "square.and.arrow.up", title: "Share") {
                store.lastError = "Sharing is not wired for this demo build yet."
            }
            HippoSymbolButton(systemName: "square.and.pencil", title: "New chat") {
                tab = "Chat"
                Task { await store.newChatThread() }
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
        case "Plan":
            planContent
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
        ZStack {
            HStack(spacing: 0) {
                VStack(spacing: 0) {
                    ScrollViewReader { proxy in
                        ScrollView {
                            VStack(alignment: .leading, spacing: 18) {
                                conversationHeader
                                ForEach(store.manusMessages) { message in
                                    messageRow(message)
                                        .id(message.id)
                                }
                                if showsStreamPanels {
                                    streamSidePanel
                                }
                                Color.clear
                                    .frame(height: 1)
                                    .id("chat-bottom")
                            }
                            .frame(maxWidth: chatColumnMaxWidth, alignment: .leading)
                            .padding(.horizontal, 28)
                            .padding(.top, 18)
                            .padding(.bottom, 28)
                            .frame(maxWidth: .infinity)
                        }
                        .onChange(of: store.manusMessages.count) { _, count in
                            guard count > 0 else { return }
                            withAnimation(.easeOut(duration: 0.18)) {
                                proxy.scrollTo("chat-bottom", anchor: .bottom)
                            }
                        }
                    }

                    HippoHairline()
                    VStack(spacing: 10) {
                        composerWorkDock
                        composer
                            .frame(maxWidth: chatColumnMaxWidth)
                    }
                    .padding(.horizontal, 28)
                    .padding(.top, 14)
                    .padding(.bottom, 18)
                }

                if computerPresentationMode == .sidePanel, shouldShowComputerSurface {
                    Rectangle()
                        .fill(HippoTheme.hairline)
                        .frame(width: 1)
                    computerSidePanel
                        .transition(.move(edge: .trailing).combined(with: .opacity))
                }
            }

            if computerPresentationMode == .overlay {
                sandboxViewerOverlay
                    .transition(.opacity.combined(with: .scale(scale: 0.985)))
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
        .animation(.easeOut(duration: 0.16), value: computerPresentationMode)
        .onChange(of: store.currentManusThread?.id) { _, _ in
            computerPresentationMode = .inlineCard
        }
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
        .buttonStyle(HippoPressFeedbackButtonStyle(cornerRadius: 999, pressedScale: 0.94, overlayOpacity: 0.14))
        .foregroundStyle(.primary)
    }

    private var sessionPill: some View {
        HStack(spacing: 8) {
            HippoStatusDot(color: chatRuntimeColor, pulse: store.snapshot.currentSession != nil, size: 6)
            Text("Chat runtime · \(chatRuntimeStatus) · \(sessionPillTitle)")
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
                    .font(.system(size: 18, weight: .medium))
                    .lineLimit(2)
                HStack(spacing: 8) {
                    HippoStatusDot(color: threadStatusColor, pulse: isThreadRunning, size: 7)
                    Text(threadStatusText)
                        .font(.system(size: 12, weight: .medium))
                        .foregroundStyle(threadStatusColor)
                    Text(currentThreadRemoteText)
                        .font(.system(size: 12))
                        .foregroundStyle(.secondary)
                    Text("\(store.manusMessages.count) messages")
                        .font(.system(size: 12))
                        .foregroundStyle(.secondary)
                }
            }
            Spacer()
            if shouldShowComputerSurface {
                Button {
                    showComputer(.sidePanel)
                } label: {
                    Label("Hippo 的电脑", systemImage: "display")
                }
                .buttonStyle(HippoPushButtonStyle(.neutral, size: .sm))
                .help("Open Hippo computer")
            }
            if isThreadRunning {
                Button {
                    Task { await store.stopManusThread() }
                } label: {
                    Label("Stop", systemImage: "stop.circle")
                }
                .buttonStyle(HippoPushButtonStyle(.neutral))
            }
        }
        .padding(.bottom, 8)
    }

    private var composer: some View {
        VStack(spacing: 12) {
            DashboardComposerTextView(text: $draft, placeholder: composerPlaceholder, focusSeed: composerFocusSeed, onCommandReturn: sendDraft)
                .frame(minHeight: 56, maxHeight: 80)

            HStack(spacing: 6) {
                roundControl("plus.circle") { appendComposerToken("Attach: ") }
                sandboxComputerControl
                Spacer()
                roundControl("livephoto") { appendComposerToken("[live audio]") }
                roundControl("mic.fill") { appendComposerToken("[voice note]") }
                Text("⌘↵")
                    .font(.system(size: 10, weight: .semibold, design: .rounded))
                    .foregroundStyle(canSend ? .secondary : .tertiary)
                    .padding(.horizontal, 6)
                    .frame(height: 22)
                    .background(HippoTheme.subtleFill, in: Capsule())
                    .accessibilityHidden(true)
                Button {
                    sendDraft()
                } label: {
                    Image(systemName: "arrow.up.circle.fill")
                        .font(.system(size: 18, weight: .semibold))
                        .frame(width: 30, height: 30)
                }
                .buttonStyle(HippoPressFeedbackButtonStyle(cornerRadius: 999, pressedScale: 0.88, overlayOpacity: 0.16))
                .foregroundStyle(canSend ? Color.accentColor : .secondary)
                .disabled(!canSend)
                .keyboardShortcut(.return, modifiers: .command)
                .help("Send")
            }
        }
        .onChange(of: store.isManusChatRunning) { _, running in
            if !running {
                composerFocusSeed += 1
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

    private var connectTools: some View {
        HStack(spacing: 10) {
            Image(systemName: "wrench.and.screwdriver.fill")
                .foregroundStyle(.secondary)
            Text("Connect more tools to Hippo")
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
                .buttonStyle(HippoPressFeedbackButtonStyle(cornerRadius: 5, pressedScale: 0.94, overlayOpacity: 0.12))
                .font(.system(size: 12, weight: .medium))
                .foregroundStyle(Color.accentColor)
            }
            .padding(.horizontal, 8)

            HippoInsetPanel(radius: 12) {
                VStack(spacing: 0) {
                    if store.manusThreads.isEmpty {
                        Text("No recent chat threads")
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
                sectionHeader("Recent Chat Threads", subtitle: "\(store.manusThreads.count) local Hippo thread records")
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
                sectionHeader("Prompt Templates", subtitle: "Click a template to send it to Chat")
                suggestionChips
                HippoInsetPanel {
                    VStack(alignment: .leading, spacing: 8) {
                        Text("Chat runtime")
                            .font(.system(size: 13, weight: .semibold))
                        Text("Templates are sent through the unified Hippo Chat route and can fall back to the local agent runtime.")
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

    private var planContent: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                sectionHeader("Task Progress", subtitle: currentThreadSubtitle)
                if store.manusPlan.isEmpty {
                    HippoInsetPanel {
                        emptyPanelText("Task progress will appear after Hippo starts planning this thread.")
                    }
                } else {
                    TaskProgressPanel(steps: store.manusPlan, variant: .inline, startsExpanded: true)
                }
                if !visibleManusTools.isEmpty {
                    toolsColumn
                }
            }
            .frame(maxWidth: 900, alignment: .leading)
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
                                Text("Sandbox access follows Manus work")
                                    .font(.system(size: 16, weight: .semibold))
                                Text("Use the computer button in Chat to open the ai-manus sandbox as a floating viewer. Hippo will not show the VNC surface until you ask for it.")
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

    private var computerInlineCard: some View {
        HippoComputerPanel(
            mode: .inlineCard,
            activity: latestComputerActivity,
            liveURL: sandboxViewerURL,
            screenshotURL: latestToolScreenshotURL,
            filePreview: computerFilePreview,
            steps: store.manusPlan,
            isLoading: store.isLoadingManusSandboxAccess || store.isLoadingManusFilePreview,
            onRefresh: prepareSandboxAccess,
            onSidePanel: { showComputer(.sidePanel) },
            onOverlay: { showComputer(.overlay) },
            onClose: { computerPresentationMode = .inlineCard }
        )
        .onTapGesture {
            showComputer(.sidePanel)
        }
    }

    private var computerSidePanel: some View {
        HippoComputerPanel(
            mode: .sidePanel,
            activity: latestComputerActivity,
            liveURL: sandboxViewerURL,
            screenshotURL: latestToolScreenshotURL,
            filePreview: computerFilePreview,
            steps: store.manusPlan,
            isLoading: store.isLoadingManusSandboxAccess || store.isLoadingManusFilePreview,
            onRefresh: prepareSandboxAccess,
            onSidePanel: { showComputer(.sidePanel) },
            onOverlay: { showComputer(.overlay) },
            onClose: { computerPresentationMode = .inlineCard }
        )
        .padding(12)
        .frame(width: 440)
        .frame(maxHeight: .infinity)
        .background(Color(nsColor: .windowBackgroundColor))
    }

    @ViewBuilder
    private var composerWorkDock: some View {
        if shouldShowInlineComputerCard {
            computerInlineCard
                .frame(maxWidth: chatColumnMaxWidth)
        } else if shouldShowComposerProgressStrip {
            TaskProgressPanel(steps: store.manusPlan, variant: .composerStrip)
                .frame(maxWidth: chatColumnMaxWidth)
        }
    }

    @ViewBuilder
    private var streamSidePanel: some View {
        if !visibleManusTools.isEmpty {
            toolsColumn
                .padding(.top, 8)
        }
    }

    private var toolsColumn: some View {
        VStack(alignment: .leading, spacing: 8) {
            HStack(spacing: 7) {
                Image(systemName: "hammer")
                    .font(.system(size: 11, weight: .semibold))
                Text("Tool activity")
                    .font(.system(size: 11, weight: .semibold))
                Text("\(visibleManusTools.count)")
                    .font(.system(size: 10, weight: .bold))
                    .foregroundStyle(.secondary)
                    .padding(.horizontal, 6)
                    .frame(height: 18)
                    .background(HippoTheme.subtleFill, in: Capsule())
                Spacer(minLength: 0)
            }
            .foregroundStyle(.secondary)

            VStack(alignment: .leading, spacing: 6) {
                ForEach(Array(visibleManusTools.prefix(5))) { tool in
                    toolActivityRow(tool)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    private var sandboxComputerControl: some View {
        Button {
            showComputer(.sidePanel)
        } label: {
            Image(systemName: "display")
                .font(.system(size: 13, weight: .medium))
                .frame(width: 30, height: 30)
                .background(shouldShowComputerSurface ? Color.accentColor.opacity(0.10) : .clear, in: Circle())
                .overlay {
                    Circle().strokeBorder(shouldShowComputerSurface ? Color.accentColor.opacity(0.35) : HippoTheme.hairline, lineWidth: 0.7)
                }
        }
        .buttonStyle(HippoPressFeedbackButtonStyle(cornerRadius: 999, pressedScale: 0.88, overlayOpacity: 0.16))
        .foregroundStyle(shouldShowComputerSurface ? Color.accentColor : .secondary)
        .disabled(!shouldShowComputerSurface)
        .help(shouldShowComputerSurface ? "Open Hippo computer" : "Hippo computer appears when a remote session or tool activity starts")
    }

    private var sandboxViewerOverlay: some View {
        GeometryReader { geometry in
            ZStack {
                Color.black.opacity(0.18)
                    .ignoresSafeArea()
                    .onTapGesture {
                        computerPresentationMode = .inlineCard
                    }

                HippoComputerPanel(
                    mode: .overlay,
                    activity: latestComputerActivity,
                    liveURL: sandboxViewerURL,
                    screenshotURL: latestToolScreenshotURL,
                    filePreview: computerFilePreview,
                    steps: store.manusPlan,
                    isLoading: store.isLoadingManusSandboxAccess || store.isLoadingManusFilePreview,
                    onRefresh: prepareSandboxAccess,
                    onSidePanel: { showComputer(.sidePanel) },
                    onOverlay: { showComputer(.overlay) },
                    onClose: { computerPresentationMode = .inlineCard }
                )
                .frame(
                    width: min(max(geometry.size.width - 96, 560), 980),
                    height: min(max(geometry.size.height - 96, 420), 680)
                )
                .shadow(color: .black.opacity(0.22), radius: 28, y: 16)
            }
        }
    }

    private func toolActivityRow(_ tool: ManusToolEvent) -> some View {
        HStack(spacing: 9) {
            Image(systemName: toolIconName(tool))
                .font(.system(size: 11, weight: .semibold))
                .foregroundStyle(toolTint(tool))
                .frame(width: 24, height: 24)
                .background(toolTint(tool).opacity(0.12), in: RoundedRectangle(cornerRadius: 6, style: .continuous))

            VStack(alignment: .leading, spacing: 2) {
                Text(toolDisplayTitle(tool))
                    .font(.system(size: 12, weight: .medium))
                    .foregroundStyle(.primary)
                    .lineLimit(1)
                if let subtitle = toolDisplaySubtitle(tool) {
                    Text(subtitle)
                        .font(.system(size: 11))
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
            }

            Spacer(minLength: 8)

            Text(toolStatusText(tool.status))
                .font(.system(size: 10, weight: .semibold))
                .foregroundStyle(toolStatusColor(tool.status))
                .padding(.horizontal, 7)
                .frame(height: 20)
                .background(toolStatusColor(tool.status).opacity(0.10), in: Capsule())
        }
        .padding(.horizontal, 9)
        .padding(.vertical, 7)
        .background(Color(nsColor: .controlBackgroundColor).opacity(0.55), in: RoundedRectangle(cornerRadius: 9, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 9, style: .continuous)
                .strokeBorder(HippoTheme.hairline.opacity(0.8), lineWidth: 0.5)
        }
    }

    private func messageRow(_ message: ManusMessage) -> some View {
        let role = message.role
        let content = message.content.isEmpty ? " " : message.content
        let isUser = role.localizedCaseInsensitiveContains("user")
        let isError = role.localizedCaseInsensitiveContains("error")

        return Group {
            if isUser {
                HStack(alignment: .top) {
                    Spacer(minLength: 48)
                    Text(content)
                        .font(.system(size: 14))
                        .foregroundStyle(.primary)
                        .textSelection(.enabled)
                        .lineSpacing(2)
                        .padding(.horizontal, 14)
                        .padding(.vertical, 10)
                        .background(Color(nsColor: .textBackgroundColor).opacity(0.96), in: RoundedRectangle(cornerRadius: 12, style: .continuous))
                        .overlay {
                            RoundedRectangle(cornerRadius: 12, style: .continuous)
                                .strokeBorder(HippoTheme.hairline, lineWidth: 0.6)
                        }
                        .frame(maxWidth: userBubbleMaxWidth, alignment: .trailing)
                }
            } else {
                VStack(alignment: .leading, spacing: 8) {
                    HStack(spacing: 8) {
                        Image(systemName: isError ? "exclamationmark.triangle.fill" : "sparkles")
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundStyle(isError ? Color.orange : Color.accentColor)
                        Text(isError ? "Manus error" : "Manus")
                            .font(.system(size: 12, weight: .medium))
                            .foregroundStyle(.secondary)
                    }
                    Text(content)
                        .font(.system(size: 14))
                        .foregroundStyle(isError ? Color.orange : Color.primary)
                        .textSelection(.enabled)
                        .lineSpacing(3)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .padding(.vertical, 2)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
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
        .buttonStyle(HippoPressFeedbackButtonStyle(cornerRadius: 8, pressedScale: 0.985, overlayOpacity: 0.10))
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
        .buttonStyle(HippoPressFeedbackButtonStyle(cornerRadius: 999, pressedScale: 0.88, overlayOpacity: 0.16))
        .foregroundStyle(.secondary)
    }

    private func sendDraft() {
        guard canSend else { return }
        let text = draft.trimmingCharacters(in: .whitespacesAndNewlines)
        draft = ""
        composerFocusSeed += 1
        Task { await store.sendChatMessage(text) }
    }

    private func sendSuggestion(_ title: String) {
        let text = prompt(for: title)
        Task { await store.sendChatMessage(text) }
    }

    private func openSandboxURL(interactive: Bool) {
        guard let raw = interactive ? store.manusSandboxAccess?.takeOverUrl : store.manusSandboxAccess?.interactiveEntryURL,
              let url = resolvedResourceURL(raw)
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

    private func showComputer(_ mode: ComputerPresentationMode) {
        guard shouldShowComputerSurface else {
            store.lastError = "Hippo computer appears after a remote session, tool activity, or task progress starts."
            return
        }
        computerPresentationMode = mode
        guard sandboxViewerURL == nil, !store.isLoadingManusSandboxAccess else { return }
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
        !draft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty && !store.isManusChatRunning
    }

    private var showsStreamPanels: Bool {
        !visibleManusTools.isEmpty
    }

    private var visibleManusTools: [ManusToolEvent] {
        store.manusTools.filter { !isInternalMessageTool($0) }
    }

    private var userBubbleMaxWidth: CGFloat {
        chatColumnMaxWidth * 0.9
    }

    private var browserToolCount: Int {
        visibleManusTools.filter(isBrowserTool).count
    }

    private var hasBrowserActivity: Bool {
        browserToolCount > 0
    }

    private var canOpenSandboxViewer: Bool {
        currentRemoteSessionID != nil || sandboxViewerURL != nil || store.isLoadingManusSandboxAccess
    }

    private var shouldShowInlineComputerCard: Bool {
        shouldShowComputerSurface && computerPresentationMode == .inlineCard
    }

    private var shouldShowComposerProgressStrip: Bool {
        !store.manusPlan.isEmpty && computerPresentationMode == .inlineCard
    }

    private var shouldShowComputerSurface: Bool {
        latestComputerActivity != nil || canOpenSandboxViewer || store.isLoadingManusFilePreview
    }

    private var toolbarThreadTitle: String {
        store.currentManusThread.flatMap { threadTitle($0) } ?? "New Task"
    }

    private var latestComputerActivity: ComputerActivity? {
        guard let tool = visibleManusTools.last else {
            if canOpenSandboxViewer {
                return ComputerActivity(
                    title: "Hippo 的电脑",
                    subtitle: sandboxViewerSubtitle,
                    kind: .browser,
                    function: nil,
                    argument: nil,
                    filePath: nil
                )
            }
            return nil
        }

        let function = tool.function.trimmingCharacters(in: .whitespacesAndNewlines)
        let text = "\(tool.name) \(tool.function)".lowercased()
        let kind: ComputerActivity.Kind
        if text.contains("browser") || text.contains("navigate") || text.contains("click") || text.contains("scroll") {
            kind = .browser
        } else if text.contains("file") || text.contains("editor") || toolFilePath(tool) != nil {
            kind = .file
        } else if text.contains("shell") || text.contains("command") || text.contains("terminal") {
            kind = .shell
        } else {
            kind = .tool
        }

        let argument = toolArgsPreview(tool)
        let verb: String
        switch kind {
        case .browser:
            verb = "正在使用浏览器"
        case .file:
            verb = "正在使用编辑器"
        case .shell:
            verb = "正在使用终端"
        case .tool:
            verb = "正在使用工具"
        }
        let detail = [function.isEmpty ? tool.name : function, argument ?? ""].compactMap { value in
            let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
            return trimmed.isEmpty ? nil : trimmed
        }.joined(separator: " ")

        return ComputerActivity(
            title: "Hippo 的电脑",
            subtitle: detail.isEmpty ? verb : "\(verb) · \(detail)",
            kind: kind,
            function: function.isEmpty ? nil : function,
            argument: argument,
            filePath: toolFilePath(tool)
        )
    }

    private var computerFilePreview: ManusFilePreview? {
        if let latestToolFilePreview {
            return latestToolFilePreview
        }
        guard latestComputerActivity?.kind == .file else { return nil }
        return store.manusFilePreview
    }

    private var latestToolFilePreview: ManusFilePreview? {
        guard let tool = visibleManusTools.reversed().first(where: { tool in
            let text = "\(tool.name) \(tool.function)".lowercased()
            return text.contains("file") || text.contains("editor") || toolFilePath(tool) != nil
        }) else { return nil }
        guard let path = toolFilePath(tool), !path.isEmpty else { return nil }
        guard let text = toolFileText(tool), !text.isEmpty else { return nil }
        return ManusFilePreview(
            fileId: nil,
            name: URL(fileURLWithPath: path).lastPathComponent,
            path: path,
            mimeType: nil,
            fileType: "text",
            content: .string(text),
            text: text,
            previewUrl: nil,
            signedUrl: nil,
            size: Double(text.utf8.count),
            truncated: nil,
            detail: "Preview from tool event"
        )
    }

    private var latestComputerFileInfo: ManusFileInfo? {
        guard let path = latestComputerActivity?.filePath, !path.isEmpty else { return nil }
        return ManusFileInfo(
            fileId: nil,
            remoteId: nil,
            name: URL(fileURLWithPath: path).lastPathComponent,
            filename: nil,
            path: path,
            filePath: nil,
            size: nil,
            sizeBytes: nil,
            mimeType: nil,
            contentType: nil,
            fileType: nil,
            type: nil,
            kind: nil,
            isDirectory: nil,
            createdAt: nil,
            updatedAt: nil,
            modifiedAt: nil,
            uploadDate: nil,
            fileUrl: nil,
            metadata: nil
        )
    }

    private var latestToolScreenshotURL: URL? {
        guard let tool = visibleManusTools.reversed().first(where: { toolContentString("screenshot", in: $0) != nil }),
              let raw = toolContentString("screenshot", in: tool)
        else { return nil }
        return resolvedResourceURL(raw)
    }

    private var currentRemoteSessionID: String? {
        guard let thread = store.currentManusThread else { return nil }
        if let remote = thread.manusSessionId, !remote.isEmpty {
            return remote
        }
        return nil
    }

    private func toolFileText(_ tool: ManusToolEvent) -> String? {
        if let text = jsonText(tool.args["content"]) {
            return text
        }
        if let text = jsonText(tool.args["text"]) {
            return text
        }
        if case .string(let text)? = tool.content {
            return text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty ? nil : text
        }
        for key in ["content", "text", "preview"] {
            if let text = toolContentString(key, in: tool), !text.isEmpty {
                return text
            }
        }
        return nil
    }

    private var sandboxViewerURL: URL? {
        let raw = store.manusSandboxAccess?.takeOverUrl ?? store.manusSandboxAccess?.interactiveUrl
        guard let raw, !raw.isEmpty else { return nil }
        return resolvedResourceURL(raw)
    }

    private var sandboxViewerSubtitle: String {
        if store.isLoadingManusSandboxAccess {
            return "Preparing live sandbox"
        }
        if hasBrowserActivity {
            return "Live browser workspace"
        }
        if store.isManusChatRunning {
            return "Manus is working"
        }
        return "Sandbox viewer"
    }

    private var chatRuntimeColor: Color {
        store.snapshot.jarvisState == .error ? .orange : .green
    }

    private var chatRuntimeStatus: String {
        if store.snapshot.jarvisState == .error {
            return "needs attention"
        }
        return "auto route"
    }

    private var isThreadRunning: Bool {
        if store.isManusChatRunning { return true }
        let status = (store.currentManusThread?.status ?? "").lowercased()
        return ["running", "pending", "queued", "streaming"].contains(status)
    }

    private var threadStatusText: String {
        let status = store.currentManusThread?.status.trimmingCharacters(in: .whitespacesAndNewlines)
        guard let status, !status.isEmpty else { return chatRuntimeStatus }
        return status.replacingOccurrences(of: "_", with: " ")
    }

    private var threadStatusColor: Color {
        let status = threadStatusText.lowercased()
        if status.contains("error") || status.contains("failed") || status.contains("unavailable") {
            return .orange
        }
        if status.contains("running") || status.contains("pending") || store.isManusChatRunning {
            return .green
        }
        if status.contains("stopped") || status.contains("local") || status.contains("not created") {
            return .secondary
        }
        return chatRuntimeColor
    }

    private var currentThreadRemoteText: String {
        guard let thread = store.currentManusThread else { return "no thread" }
        if let remote = thread.manusSessionId, !remote.isEmpty {
            return "Manus \(String(remote.suffix(8)))"
        }
        return "local draft"
    }

    private var composerPlaceholder: String {
        "Assign a task, ask Hippo to draft something, or describe what to capture next..."
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
            return "No chat thread selected"
        }
        let title = thread.title?.isEmpty == false ? thread.title! : String((thread.manusSessionId ?? thread.sessionId).suffix(8))
        return "Thread \(title) · \(thread.status)"
    }

    private var modelTitle: String {
        if let provider = store.aiManusConfig.authProvider, !provider.isEmpty {
            return "Chat · \(provider)"
        }
        if let apiBaseURL = store.aiManusConfig.apiBaseUrl, !apiBaseURL.isEmpty {
            return "Chat · \(apiBaseURL)"
        }
        return "Hippo Chat · auto"
    }

    private var toolIcons: [(systemName: String, color: Color)] {
        let mapped = visibleManusTools.map { tool in
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

    private func isInternalMessageTool(_ tool: ManusToolEvent) -> Bool {
        let name = tool.name.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        let function = tool.function.trimmingCharacters(in: .whitespacesAndNewlines).lowercased()
        return name == "message" || function.hasPrefix("message_")
    }

    private func isBrowserTool(_ tool: ManusToolEvent) -> Bool {
        let text = "\(tool.name) \(tool.function)".lowercased()
        return text.contains("browser") || text.contains("navigate") || text.contains("click") || text.contains("scroll")
    }

    private func toolDisplayTitle(_ tool: ManusToolEvent) -> String {
        let function = tool.function.trimmingCharacters(in: .whitespacesAndNewlines)
        let raw = function.isEmpty ? tool.name : function
        let cleaned = raw
            .replacingOccurrences(of: "_", with: " ")
            .replacingOccurrences(of: "-", with: " ")
            .trimmingCharacters(in: .whitespacesAndNewlines)
        guard !cleaned.isEmpty else { return "Tool" }
        return cleaned
            .split(separator: " ")
            .map { word in
                String(word.prefix(1)).uppercased() + String(word.dropFirst())
            }
            .joined(separator: " ")
    }

    private func toolDisplaySubtitle(_ tool: ManusToolEvent) -> String? {
        if let preview = toolArgsPreview(tool), !preview.isEmpty {
            return preview
        }
        if let content = tool.content {
            let text = content.compactDescription.trimmingCharacters(in: .whitespacesAndNewlines)
            return text.isEmpty ? nil : text
        }
        return nil
    }

    private func toolArgsPreview(_ tool: ManusToolEvent) -> String? {
        for key in ["query", "url", "path", "file", "command", "text"] {
            if let value = tool.args[key]?.compactDescription.trimmingCharacters(in: .whitespacesAndNewlines),
               !value.isEmpty {
                return value.replacingOccurrences(of: "\n", with: " ")
            }
        }
        return nil
    }

    private func toolFilePath(_ tool: ManusToolEvent) -> String? {
        for key in ["path", "file", "file_path", "filepath", "filename"] {
            if let value = jsonText(tool.args[key]), !value.isEmpty {
                return value
            }
            if let value = toolContentString(key, in: tool), !value.isEmpty {
                return value
            }
        }
        return nil
    }

    private func toolContentString(_ key: String, in tool: ManusToolEvent) -> String? {
        guard case .object(let object)? = tool.content,
              let value = object[key]
        else { return nil }
        return jsonText(value)
    }

    private func jsonText(_ value: JSONValue?) -> String? {
        guard let value else { return nil }
        switch value {
        case .string(let text):
            let trimmed = text.trimmingCharacters(in: .whitespacesAndNewlines)
            return trimmed.isEmpty ? nil : trimmed
        case .number, .bool:
            let text = value.compactDescription.trimmingCharacters(in: .whitespacesAndNewlines)
            return text.isEmpty ? nil : text
        case .object, .array, .null:
            return nil
        }
    }

    private func resolvedResourceURL(_ raw: String?) -> URL? {
        guard let raw else { return nil }
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return nil }
        if let absolute = URL(string: trimmed), absolute.scheme != nil {
            return absolute
        }
        guard let origin = aiManusFrontendOriginURL else {
            return URL(string: trimmed)
        }
        return URL(string: trimmed, relativeTo: origin)?.absoluteURL
    }

    private var aiManusFrontendOriginURL: URL? {
        for raw in [
            store.aiManusConfig.frontendUrl,
            store.manusSandboxAccess?.frontendUrl,
            store.aiManusConfig.baseUrl,
            store.aiManusConfig.apiBaseUrl
        ] {
            guard let raw, let url = URL(string: raw), url.scheme != nil, url.host != nil else { continue }
            var components = URLComponents(url: url, resolvingAgainstBaseURL: false)
            components?.path = ""
            components?.query = nil
            components?.fragment = nil
            return components?.url
        }
        return nil
    }

    private func toolIconName(_ tool: ManusToolEvent) -> String {
        let text = "\(tool.name) \(tool.function)".lowercased()
        if text.contains("browser") || text.contains("search") || text.contains("web") { return "globe" }
        if text.contains("file") || text.contains("write") || text.contains("read") { return "doc.text" }
        if text.contains("shell") || text.contains("terminal") || text.contains("command") { return "terminal" }
        if text.contains("code") { return "chevron.left.forwardslash.chevron.right" }
        if text.contains("python") { return "curlybraces" }
        return "wrench.and.screwdriver"
    }

    private func toolTint(_ tool: ManusToolEvent) -> Color {
        let text = "\(tool.name) \(tool.function)".lowercased()
        if text.contains("search") || text.contains("browser") || text.contains("web") { return .blue }
        if text.contains("file") || text.contains("write") || text.contains("read") { return .orange }
        if text.contains("shell") || text.contains("terminal") || text.contains("command") { return .purple }
        return Color.accentColor
    }

    private func toolStatusText(_ status: String) -> String {
        let cleaned = status.replacingOccurrences(of: "_", with: " ").trimmingCharacters(in: .whitespacesAndNewlines)
        return cleaned.isEmpty ? "active" : cleaned
    }

    private func toolStatusColor(_ status: String) -> Color {
        let lowered = status.lowercased()
        if lowered.contains("error") || lowered.contains("fail") { return .orange }
        if lowered.contains("call") || lowered.contains("run") { return .green }
        return .secondary
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
            guard let text = stringValue(child.value), !text.isEmpty, text != "nil" else { return nil }
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
            if let text = stringValue(child.value), !text.isEmpty, text != "nil" {
                return text
            }
        }
        return nil
    }

    private func stringValue(_ value: Any) -> String? {
        guard let unwrapped = unwrapOptional(value) else { return nil }
        let text: String
        if let string = unwrapped as? String {
            text = string
        } else {
            text = String(describing: unwrapped)
        }
        let cleaned = text.trimmingCharacters(in: .whitespacesAndNewlines)
        return cleaned.isEmpty || cleaned == "nil" ? nil : cleaned
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

private enum ComputerPresentationMode: Equatable {
    case inlineCard
    case sidePanel
    case overlay
}

private struct ComputerActivity: Equatable {
    enum Kind: Equatable {
        case browser
        case file
        case shell
        case tool

        var iconName: String {
            switch self {
            case .browser: "globe"
            case .file: "doc.text"
            case .shell: "terminal"
            case .tool: "wrench.and.screwdriver"
            }
        }

        var tint: Color {
            switch self {
            case .browser: .blue
            case .file: .orange
            case .shell: .purple
            case .tool: Color.accentColor
            }
        }
    }

    var title: String
    var subtitle: String
    var kind: Kind
    var function: String?
    var argument: String?
    var filePath: String?
}

private enum TaskProgressVariant {
    case inline
    case floating
    case composerStrip

    var defaultExpanded: Bool {
        switch self {
        case .inline: true
        case .floating, .composerStrip: false
        }
    }
}

private struct TaskProgressPanel: View {
    let steps: [ManusPlanStep]
    let variant: TaskProgressVariant
    @State private var isExpanded: Bool

    init(steps: [ManusPlanStep], variant: TaskProgressVariant, startsExpanded: Bool? = nil) {
        self.steps = steps
        self.variant = variant
        _isExpanded = State(initialValue: startsExpanded ?? variant.defaultExpanded)
    }

    var body: some View {
        if variant == .composerStrip {
            compactStrip
        } else {
            expandedPanel
        }
    }

    private var compactStrip: some View {
        Button {
            isExpanded.toggle()
        } label: {
            VStack(alignment: .leading, spacing: isExpanded ? 10 : 0) {
                header
                if isExpanded {
                    stepList(limit: 4)
                }
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 9)
            .background(Color(nsColor: .textBackgroundColor).opacity(0.94), in: RoundedRectangle(cornerRadius: 13, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 13, style: .continuous)
                    .strokeBorder(HippoTheme.hairline, lineWidth: 0.6)
            }
        }
        .buttonStyle(HippoPressFeedbackButtonStyle(cornerRadius: 13, pressedScale: 0.99, overlayOpacity: 0.08))
    }

    private var expandedPanel: some View {
        VStack(alignment: .leading, spacing: 10) {
            header
            if isExpanded {
                stepList(limit: variant == .floating ? 4 : 8)
            }
        }
        .padding(14)
        .background(panelBackground, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 12, style: .continuous)
                .strokeBorder(panelBorder, lineWidth: 0.7)
        }
    }

    private var header: some View {
        HStack(spacing: 8) {
            Text("任务进度")
                .font(.system(size: 13, weight: .semibold))
                .foregroundStyle(.primary)
            Spacer(minLength: 8)
            Text("\(completedCount) / \(steps.count)")
                .font(.system(size: 12, weight: .semibold))
                .foregroundStyle(.secondary)
            Image(systemName: isExpanded ? "chevron.down" : "chevron.up")
                .font(.system(size: 10, weight: .semibold))
                .foregroundStyle(.secondary)
        }
        .contentShape(Rectangle())
        .onTapGesture {
            isExpanded.toggle()
        }
    }

    private func stepList(limit: Int) -> some View {
        VStack(alignment: .leading, spacing: 9) {
            ForEach(Array(steps.prefix(limit).enumerated()), id: \.element.id) { _, step in
                HStack(alignment: .top, spacing: 9) {
                    Image(systemName: statusIcon(step.status))
                        .font(.system(size: 11, weight: .semibold))
                        .foregroundStyle(statusColor(step.status))
                        .frame(width: 16, height: 16)
                        .padding(.top, 1)
                    Text(step.description.isEmpty ? normalizedStatus(step.status) : step.description)
                        .font(.system(size: 12))
                        .foregroundStyle(statusTextColor(step.status))
                        .lineLimit(variant == .floating ? 1 : 2)
                }
            }
        }
    }

    private var completedCount: Int {
        steps.filter { isCompleted($0.status) }.count
    }

    private var panelBackground: Color {
        variant == .floating
            ? Color(nsColor: .windowBackgroundColor).opacity(0.94)
            : Color(nsColor: .controlBackgroundColor).opacity(0.62)
    }

    private var panelBorder: Color {
        variant == .floating ? HippoTheme.hairline.opacity(0.85) : HippoTheme.hairline
    }

    private func isCompleted(_ status: String) -> Bool {
        let lowered = status.lowercased()
        return lowered.contains("complete") || lowered.contains("done") || lowered.contains("success")
    }

    private func statusIcon(_ status: String) -> String {
        let lowered = status.lowercased()
        if isCompleted(status) { return "checkmark" }
        if lowered.contains("fail") || lowered.contains("error") { return "exclamationmark.triangle" }
        return "clock"
    }

    private func statusColor(_ status: String) -> Color {
        let lowered = status.lowercased()
        if isCompleted(status) { return .green }
        if lowered.contains("fail") || lowered.contains("error") { return .orange }
        return .secondary
    }

    private func statusTextColor(_ status: String) -> Color {
        isCompleted(status) ? .primary : .secondary
    }

    private func normalizedStatus(_ status: String) -> String {
        let cleaned = status.replacingOccurrences(of: "_", with: " ").trimmingCharacters(in: .whitespacesAndNewlines)
        return cleaned.isEmpty ? "pending" : cleaned
    }
}

private struct HippoComputerPanel: View {
    let mode: ComputerPresentationMode
    let activity: ComputerActivity?
    let liveURL: URL?
    let screenshotURL: URL?
    let filePreview: ManusFilePreview?
    let steps: [ManusPlanStep]
    let isLoading: Bool
    let onRefresh: () -> Void
    let onSidePanel: () -> Void
    let onOverlay: () -> Void
    let onClose: () -> Void

    var body: some View {
        VStack(spacing: 0) {
            header
            HippoHairline()
            ZStack(alignment: .bottom) {
                computerSurface
                if !steps.isEmpty {
                    TaskProgressPanel(steps: steps, variant: .floating)
                        .padding(12)
                }
            }
            .frame(maxWidth: .infinity, maxHeight: mode == .inlineCard ? 320 : .infinity)
        }
        .frame(maxWidth: .infinity, minHeight: mode == .inlineCard ? 230 : nil)
        .background(Color(nsColor: .windowBackgroundColor), in: RoundedRectangle(cornerRadius: cornerRadius, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: cornerRadius, style: .continuous)
                .strokeBorder(HippoTheme.hairline, lineWidth: 0.8)
        }
    }

    private var header: some View {
        HStack(spacing: 10) {
            Image(systemName: activity?.kind.iconName ?? "display")
                .font(.system(size: 14, weight: .semibold))
                .foregroundStyle(activity?.kind.tint ?? Color.accentColor)
                .frame(width: 32, height: 32)
                .background((activity?.kind.tint ?? Color.accentColor).opacity(0.12), in: RoundedRectangle(cornerRadius: 8, style: .continuous))

            VStack(alignment: .leading, spacing: 2) {
                Text("Hippo 的电脑")
                    .font(.system(size: mode == .inlineCard ? 15 : 16, weight: .semibold))
                Text(activity?.subtitle ?? "准备远程工作区")
                    .font(.system(size: 11))
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }

            Spacer(minLength: 8)

            iconButton("arrow.clockwise", title: "Refresh", action: onRefresh)
                .disabled(isLoading)
            if mode != .sidePanel {
                iconButton("sidebar.right", title: "Side panel", action: onSidePanel)
            }
            if mode != .overlay {
                iconButton("arrow.up.left.and.arrow.down.right", title: "Expand", action: onOverlay)
            }
            if mode != .inlineCard {
                iconButton("xmark", title: "Close", action: onClose)
            }
        }
        .padding(.horizontal, 14)
        .padding(.vertical, 12)
    }

    @ViewBuilder
    private var computerSurface: some View {
        if let liveURL {
            ZStack {
                Color.black.opacity(0.90)
                ManusSandboxWebView(url: liveURL)
                    .clipShape(RoundedRectangle(cornerRadius: mode == .inlineCard ? 8 : 10, style: .continuous))
                    .padding(mode == .inlineCard ? 10 : 12)
            }
        } else if let screenshotURL {
            ZStack {
                Color.black.opacity(0.88)
                AsyncImage(url: screenshotURL) { phase in
                    switch phase {
                    case .success(let image):
                        image
                            .resizable()
                            .scaledToFit()
                            .padding(10)
                    case .failure:
                        preparingState("截图暂时无法加载", systemImage: "photo")
                    default:
                        preparingState("正在加载工具截图", systemImage: "photo")
                    }
                }
            }
        } else if let filePreview {
            fileSurface(filePreview)
        } else {
            ZStack {
                Color.black.opacity(0.88)
                preparingState(isLoading ? "正在准备工作区" : "等待浏览器或文件活动", systemImage: "display")
            }
        }
    }

    private func fileSurface(_ preview: ManusFilePreview) -> some View {
        VStack(spacing: 0) {
            HStack {
                Text(preview.displayName)
                    .font(.system(size: 12, weight: .semibold))
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                Spacer(minLength: 0)
            }
            .padding(.horizontal, 14)
            .frame(height: 34)
            .background(Color(nsColor: .controlBackgroundColor))

            ScrollView {
                Text(preview.previewText ?? "No preview available.")
                    .font(.system(size: 13, design: .monospaced))
                    .foregroundStyle(.primary)
                    .textSelection(.enabled)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(18)
            }
            .background(Color(nsColor: .textBackgroundColor))
        }
    }

    private func preparingState(_ title: String, systemImage: String) -> some View {
        VStack(spacing: 12) {
            if isLoading {
                ProgressView()
                    .controlSize(.small)
            } else {
                Image(systemName: systemImage)
                    .font(.system(size: 24, weight: .medium))
                    .foregroundStyle(.white.opacity(0.70))
            }
            Text(title)
                .font(.system(size: 13, weight: .medium))
                .foregroundStyle(.white.opacity(0.82))
        }
        .padding(18)
    }

    private func iconButton(_ systemName: String, title: String, action: @escaping () -> Void) -> some View {
        Button(action: action) {
            Image(systemName: systemName)
                .font(.system(size: 12, weight: .semibold))
                .frame(width: 28, height: 28)
        }
        .buttonStyle(HippoPressFeedbackButtonStyle(cornerRadius: 7, pressedScale: 0.90, overlayOpacity: 0.14))
        .foregroundStyle(.secondary)
        .help(title)
    }

    private var cornerRadius: CGFloat {
        mode == .overlay ? 18 : 14
    }
}

private struct DashboardComposerTextView: NSViewRepresentable {
    @Binding var text: String
    var placeholder: String
    var focusSeed: Int
    var onCommandReturn: () -> Void

    func makeCoordinator() -> Coordinator {
        Coordinator(text: $text, focusSeed: focusSeed)
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
        view.textView.isEditable = true
        view.textView.isSelectable = true
        view.textView.onCommandReturn = onCommandReturn
        if context.coordinator.lastFocusSeed != focusSeed {
            context.coordinator.lastFocusSeed = focusSeed
            DispatchQueue.main.async {
                view.focusTextView()
            }
        }
    }

    final class Coordinator: NSObject, NSTextViewDelegate {
        var text: Binding<String>
        var lastFocusSeed: Int

        init(text: Binding<String>, focusSeed: Int) {
            self.text = text
            self.lastFocusSeed = focusSeed - 1
        }

        func textDidChange(_ notification: Notification) {
            guard let textView = notification.object as? NSTextView else { return }
            text.wrappedValue = textView.string
        }
    }

    final class ComposerContainerView: NSView {
        let scrollView = NSScrollView()
        let textView = ComposerTextView()
        let placeholderLabel = ClickThroughLabel(labelWithString: "")

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

        override func hitTest(_ point: NSPoint) -> NSView? {
            bounds.contains(point) ? textView : nil
        }

        override func mouseDown(with event: NSEvent) {
            focusTextView()
            super.mouseDown(with: event)
        }

        func focusTextView() {
            guard let window else { return }
            window.makeFirstResponder(textView)
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

    final class ComposerTextView: NSTextView {
        var onCommandReturn: (() -> Void)?

        override func keyDown(with event: NSEvent) {
            let isReturn = event.keyCode == 36 || event.keyCode == 76
            if isReturn, event.modifierFlags.contains(.command) {
                onCommandReturn?()
                return
            }
            super.keyDown(with: event)
        }
    }

    final class ClickThroughLabel: NSTextField {
        override func hitTest(_ point: NSPoint) -> NSView? {
            nil
        }
    }
}

private struct ManusSandboxWebView: NSViewRepresentable {
    var url: URL

    func makeNSView(context: Context) -> WKWebView {
        let configuration = WKWebViewConfiguration()
        configuration.preferences.javaScriptCanOpenWindowsAutomatically = true
        configuration.allowsAirPlayForMediaPlayback = false

        let webView = WKWebView(frame: .zero, configuration: configuration)
        webView.allowsBackForwardNavigationGestures = false
        webView.setValue(false, forKey: "drawsBackground")
        return webView
    }

    func updateNSView(_ webView: WKWebView, context: Context) {
        guard webView.url != url else { return }
        var request = URLRequest(url: url)
        request.cachePolicy = .reloadIgnoringLocalCacheData
        webView.load(request)
    }
}
