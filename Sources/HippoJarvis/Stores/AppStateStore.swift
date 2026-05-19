import Foundation
import SwiftUI

@MainActor
final class AppStateStore: ObservableObject {
    private static let languageKey = "appLanguage"

    @Published private(set) var snapshot: AppSnapshot = .empty
    @Published private(set) var eventHistory: [EventRecord] = []
    @Published private(set) var ownscribeConfig: OwnscribeConfig = .empty
    @Published private(set) var ownscribeDevices: OwnscribeAudioDevicesResponse = .empty
    @Published private(set) var ownscribePreflight: OwnscribePreflight = .empty
    @Published private(set) var cuaTargetSurface: CuaTargetSurface = .empty
    @Published private(set) var aiManusConfig: AiManusConfig = .empty
    @Published private(set) var aiManusStatus: AiManusStatus = .empty
    @Published private(set) var aiManusRuntimeLastCommand: AiManusRuntimeCommandResponse?
    @Published private(set) var aiManusRuntimeLogs: AiManusRuntimeLogsResponse = .empty
    @Published private(set) var aiManusModelValidation: ModelValidationResponse?
    @Published private(set) var basicMemoryConfig: BasicMemoryConfig = .empty
    @Published private(set) var basicMemoryStatus: BasicMemoryStatus = .empty
    @Published private(set) var basicMemorySearch: BasicMemorySearchResponse = .empty
    @Published private(set) var basicMemoryRecent: BasicMemoryRecentResponse = .empty
    @Published private(set) var basicMemoryNotePreview: BasicMemoryNote?
    @Published private(set) var basicMemoryLastSync: BasicMemorySyncResponse?
    @Published private(set) var vlmacConfig: VlmacConfig = .empty
    @Published private(set) var vlmacPreflight: JSONValue?
    @Published private(set) var contextFragments: [ContextFragment] = []
    @Published private(set) var manusThreads: [ManusThread] = []
    @Published private(set) var currentManusThread: ManusThread?
    @Published private(set) var manusMessages: [ManusMessage] = []
    @Published private(set) var manusPlan: [ManusPlanStep] = []
    @Published private(set) var manusTools: [ManusToolEvent] = []
    @Published private(set) var manusSandboxAccess: ManusSandboxAccess?
    @Published private(set) var manusFilesResponse: ManusFilesResponse = .empty
    @Published private(set) var manusFilePreview: ManusFilePreview?
    @Published private(set) var manusFileDownloadLink: ManusFileDownloadLink?
    @Published private(set) var isLoadingManusSandboxAccess = false
    @Published private(set) var isLoadingManusFiles = false
    @Published private(set) var isLoadingManusFilePreview = false
    @Published private(set) var isLoadingManusFileDownloadLink = false
    @Published private(set) var isRunningAiManusRuntimeCommand = false
    @Published private(set) var isRunningBasicMemoryCommand = false
    @Published private(set) var isManusChatRunning = false
    @Published private(set) var isBusy = false
    @Published var language: AppLanguage {
        didSet {
            UserDefaults.standard.set(language.rawValue, forKey: Self.languageKey)
        }
    }
    @Published var lastError: String?

    private let client = OrchestratorClient()
    private let launcher = OrchestratorLauncher.shared
    private let skillStore = SkillStore()
    private var bootstrapped = false
    private var isBootstrapping = false
    private var isRecoveringOrchestrator = false
    private var eventsTask: Task<Void, Never>?
    private var manusChatTask: Task<Void, Never>?
    private var activeManusChatRunID: UUID?

    private enum ManusChatStreamRoute {
        case directManus
        case hippoChat
    }

    init() {
        let storedLanguage = UserDefaults.standard.string(forKey: Self.languageKey)
        language = storedLanguage.flatMap(AppLanguage.init(rawValue:)) ?? AppLanguage.defaultLanguage
    }

    var menuBarSystemImage: String {
        switch snapshot.jarvisState {
        case .idle:
            "circle"
        case .meetingActive, .sopMarking:
            "waveform.circle.fill"
        case .sopGenerating, .thinking, .taskExecuting:
            "sparkles"
        case .activeTaskCandidate, .taskSurfaceDetected, .patternDetected:
            "bolt.circle.fill"
        case .taskReviewing:
            "checkmark.circle"
        case .paused:
            "pause.circle"
        case .error:
            "exclamationmark.triangle.fill"
        }
    }

    var statusTitle: String {
        AppCopy.statusTitle(snapshot.jarvisState, language: language)
    }

    var statusMessage: String {
        AppCopy.statusMessage(snapshot.statusMessage, state: snapshot.jarvisState, language: language)
    }

    var canJarvisOn: Bool { snapshot.jarvisState == .idle || snapshot.jarvisState == .error }
    var canJarvisOff: Bool { snapshot.currentSession != nil && snapshot.jarvisState != .idle }
    var canCaptureSkill: Bool { snapshot.jarvisState == .meetingActive }
    var canFinishCapture: Bool { snapshot.jarvisState == .sopMarking }
    var manusConfig: AiManusConfig { aiManusConfig }
    var manusFiles: [ManusFileInfo] { manusFilesResponse.files }
    var canInsertCurrentTask: Bool {
        guard let task = snapshot.currentTask, cuaTargetSurface.safe, !isBusy else { return false }
        let insertStatus = task.proposedActions.first?.status ?? "proposed"
        return !["inserted", "insert_requested"].contains(insertStatus)
    }

    func bootstrap() async {
        let startedAt = AppLog.start()
        if bootstrapped { return }
        if isBootstrapping {
            while isBootstrapping && !bootstrapped {
                try? await Task.sleep(nanoseconds: 100_000_000)
            }
            return
        }
        isBootstrapping = true
        defer { isBootstrapping = false }
        await ensureOrchestrator()
        await refresh()
        startEvents()
        bootstrapped = true
        AppLog.event(action: "app_state.bootstrap", status: "ok", startedAt: startedAt)
    }

    func refresh() async {
        await run {
            try await self.client.state()
        }
    }

    func detectIntervention() async {
        await run {
            try await self.client.detectIntervention()
        }
    }

    func refreshOwnscribeConsole(networkPreflight: Bool = false) async {
        isBusy = true
        defer { isBusy = false }

        do {
            ownscribeConfig = try await withOrchestratorRecovery(action: "app_state.refresh_ownscribe.config") {
                try await client.ownscribeConfig()
            }
            ownscribeDevices = try await withOrchestratorRecovery(action: "app_state.refresh_ownscribe.devices") {
                try await client.ownscribeAudioDevices()
            }
            ownscribePreflight = try await withOrchestratorRecovery(action: "app_state.refresh_ownscribe.preflight") {
                try await client.ownscribePreflight(network: networkPreflight)
            }
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func refreshManus() async {
        isBusy = true
        defer { isBusy = false }

        do {
            var config = try await withOrchestratorRecovery(action: "app_state.refresh_manus.config") {
                try await client.aiManusConfig()
            }
            aiManusConfig = config
            do {
                aiManusStatus = try await withOrchestratorRecovery(action: "app_state.refresh_manus.status") {
                    try await client.aiManusStatus()
                }
                config.status = aiManusStatus.status
                aiManusConfig = config
            } catch {
                if isOrchestratorUnavailable(error) {
                    throw error
                }
                AppLog.event(action: "app_state.refresh_manus.status", status: "error", error: error)
            }
            do {
                manusThreads = try await withOrchestratorRecovery(action: "app_state.refresh_manus.sessions") {
                    try await client.manusSessions().sessions
                }
            } catch {
                if isOrchestratorUnavailable(error) {
                    throw error
                }
                AppLog.event(action: "app_state.refresh_manus.sessions", status: "error", error: error)
            }
            if let currentManusThread {
                self.currentManusThread = manusThreads.first { $0.id == currentManusThread.id } ?? currentManusThread
            }
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func refreshBasicMemory() async {
        isRunningBasicMemoryCommand = true
        defer { isRunningBasicMemoryCommand = false }

        do {
            basicMemoryConfig = try await withOrchestratorRecovery(action: "app_state.refresh_basic_memory.config") {
                try await client.basicMemoryConfig()
            }
            basicMemoryStatus = try await withOrchestratorRecovery(action: "app_state.refresh_basic_memory.status") {
                try await client.basicMemoryStatus()
            }
            applyBasicMemoryService(basicMemoryStatus.service)
            basicMemoryRecent = (try? await withOrchestratorRecovery(action: "app_state.refresh_basic_memory.recent") {
                try await client.recentBasicMemoryNotes(limit: 8)
            }) ?? basicMemoryRecent
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func setupBasicMemory() async {
        isRunningBasicMemoryCommand = true
        defer { isRunningBasicMemoryCommand = false }

        do {
            basicMemoryStatus = try await withOrchestratorRecovery(action: "app_state.setup_basic_memory") {
                try await client.setupBasicMemory()
            }
            basicMemoryConfig = try await withOrchestratorRecovery(action: "app_state.setup_basic_memory.config") {
                try await client.basicMemoryConfig()
            }
            applyBasicMemoryService(basicMemoryStatus.service)
            basicMemoryRecent = (try? await withOrchestratorRecovery(action: "app_state.setup_basic_memory.recent") {
                try await client.recentBasicMemoryNotes(limit: 8)
            }) ?? basicMemoryRecent
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func searchBasicMemory(_ query: String) async {
        let trimmed = query.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !trimmed.isEmpty else { return }

        isRunningBasicMemoryCommand = true
        defer { isRunningBasicMemoryCommand = false }

        do {
            basicMemorySearch = try await withOrchestratorRecovery(action: "app_state.search_basic_memory") {
                try await client.searchBasicMemory(query: trimmed, limit: 8)
            }
            if let first = basicMemorySearch.results.first {
                await loadBasicMemoryNotePreview(first)
            }
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func loadBasicMemoryRecent() async {
        isRunningBasicMemoryCommand = true
        defer { isRunningBasicMemoryCommand = false }

        do {
            basicMemoryRecent = try await withOrchestratorRecovery(action: "app_state.load_basic_memory_recent") {
                try await client.recentBasicMemoryNotes(limit: 8)
            }
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func refreshContextFragments() async {
        await loadContextFragments(reportErrors: true)
    }

    func loadBasicMemoryNotePreview(_ result: BasicMemorySearchResult) async {
        await loadBasicMemoryNotePreview(
            BasicMemoryNotePreviewRequest(
                identifier: result.identifier,
                path: result.path,
                permalink: result.permalink
            )
        )
    }

    func loadBasicMemoryNotePreview(_ note: BasicMemoryNote) async {
        await loadBasicMemoryNotePreview(
            BasicMemoryNotePreviewRequest(
                identifier: note.identifier,
                path: note.path,
                permalink: note.permalink
            )
        )
    }

    func syncCurrentSessionToBasicMemory() async {
        guard let session = snapshot.currentSession else {
            lastError = "No current session is available to sync."
            return
        }
        await syncBasicMemorySession(session.id)
    }

    func syncCurrentTaskToBasicMemory() async {
        guard let task = snapshot.currentTask else {
            lastError = "No current task is available to sync."
            return
        }
        await syncBasicMemoryTask(task.id)
    }

    func syncLatestSkillToBasicMemory() async {
        guard let skill = snapshot.skills.first else {
            lastError = "No skill is available to sync."
            return
        }
        await syncBasicMemorySkill(skill.id)
    }

    func syncLatestContextFragmentToBasicMemory() async {
        guard let fragment = contextFragments.first else {
            lastError = "No voice context fragment is available to sync."
            return
        }
        await syncBasicMemoryContext(fragment.id)
    }

    func updateAiManusConfig(
        baseUrl: String? = nil,
        frontendUrl: String? = nil,
        authProvider: String? = nil,
        timeoutSeconds: Double? = nil,
        apiBase: String? = nil,
        modelName: String? = nil,
        apiKey: String? = nil,
        temperature: Double? = nil,
        maxTokens: Int? = nil,
        extraHeaders: String? = nil
    ) async {
        isBusy = true
        defer { isBusy = false }

        do {
            let request = AiManusConfigUpdateRequest(
                baseUrl: baseUrl,
                frontendUrl: frontendUrl,
                authProvider: authProvider,
                apiKey: apiKey,
                timeoutSeconds: timeoutSeconds,
                apiBase: apiBase,
                modelName: modelName,
                temperature: temperature,
                maxTokens: maxTokens,
                extraHeaders: extraHeaders
            )
            var config = try await withOrchestratorRecovery(action: "app_state.update_ai_manus") {
                try await client.updateAiManusConfig(request)
            }
            aiManusConfig = config
            do {
                aiManusStatus = try await withOrchestratorRecovery(action: "app_state.update_ai_manus.status") {
                    try await client.aiManusStatus()
                }
                config.status = aiManusStatus.status
                aiManusConfig = config
            } catch {
                if isOrchestratorUnavailable(error) {
                    throw error
                }
                AppLog.event(action: "app_state.update_ai_manus.status", status: "error", error: error)
            }
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func aiManusRuntimeStart(build: Bool = false) async {
        await runAiManusRuntimeCommand {
            try await self.client.aiManusRuntimeStart(build: build)
        }
    }

    func aiManusRuntimeStop() async {
        await runAiManusRuntimeCommand {
            try await self.client.aiManusRuntimeStop()
        }
    }

    func aiManusRuntimeRestart(build: Bool = false) async {
        await runAiManusRuntimeCommand {
            try await self.client.aiManusRuntimeRestart(build: build)
        }
    }

    func refreshAiManusRuntimeLogs() async {
        do {
            aiManusRuntimeLogs = try await withOrchestratorRecovery(action: "app_state.refresh_ai_manus_runtime_logs") {
                try await client.aiManusRuntimeLogs(limit: 80)
            }
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func validateAiManusModel() async {
        isBusy = true
        defer { isBusy = false }

        do {
            aiManusModelValidation = try await withOrchestratorRecovery(action: "app_state.validate_ai_manus_model") {
                try await client.validateAiManusModel()
            }
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func newManusThread() async {
        isBusy = true
        defer { isBusy = false }

        do {
            let response = try await withOrchestratorRecovery(action: "app_state.new_manus_thread") {
                try await client.createManusSession()
            }
            manusThreads = try await withOrchestratorRecovery(action: "app_state.new_manus_thread.sessions") {
                try await client.manusSessions().sessions
            }
            try await loadManusThreadWithoutBusy(response.sessionId)
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func newChatThread() async {
        isBusy = true
        defer { isBusy = false }

        do {
            let response = try await withOrchestratorRecovery(action: "app_state.new_chat_thread") {
                try await client.createChatSession()
            }
            manusThreads = (try? await withOrchestratorRecovery(action: "app_state.new_chat_thread.sessions") {
                try await client.manusSessions().sessions
            }) ?? manusThreads
            try await loadManusThreadWithoutBusy(response.sessionId)
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func loadManusThread(_ thread: ManusThread) async {
        await loadManusThread(thread.id)
    }

    func loadManusThread(_ sessionID: String) async {
        isBusy = true
        defer { isBusy = false }

        do {
            try await loadManusThreadWithoutBusy(sessionID)
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func sendManusMessage(_ content: String, attachments: [JSONValue]? = nil) async {
        let message = content.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !message.isEmpty else { return }
        guard !isManusChatRunning else {
            lastError = "A Manus response is still running. Stop it before sending another message."
            return
        }

        manusChatTask?.cancel()
        isManusChatRunning = true
        isBusy = true

        do {
            let sessionID: String
            if let currentManusThread {
                sessionID = currentManusThread.id
            } else {
                let response = try await withOrchestratorRecovery(action: "app_state.send_manus.create_session") {
                    try await client.createManusSession()
                }
                sessionID = response.sessionId
                manusThreads = try await withOrchestratorRecovery(action: "app_state.send_manus.sessions") {
                    try await client.manusSessions().sessions
                }
                try await loadManusThreadWithoutBusy(sessionID)
            }

            appendLocalManusMessage(role: "user", content: message, attachments: attachments)
            isBusy = false
            startManusChatStream(route: .directManus, sessionID: sessionID, message: message, attachments: attachments)
        } catch {
            isBusy = false
            isManusChatRunning = false
            lastError = error.localizedDescription
        }
    }

    func sendChatMessage(_ content: String, attachments: [JSONValue]? = nil) async {
        let message = content.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !message.isEmpty else { return }
        guard !isManusChatRunning else {
            lastError = "A Manus response is still running. Stop it before sending another message."
            return
        }

        manusChatTask?.cancel()
        isManusChatRunning = true
        isBusy = true

        do {
            let sessionID: String
            if let currentManusThread, !currentManusThread.id.hasPrefix("local-") {
                sessionID = currentManusThread.id
            } else {
                let response = try await withOrchestratorRecovery(action: "app_state.send_chat.create_session") {
                    try await client.createChatSession()
                }
                sessionID = response.sessionId
                manusThreads = (try? await withOrchestratorRecovery(action: "app_state.send_chat.sessions") {
                    try await client.manusSessions().sessions
                }) ?? manusThreads
                try await loadManusThreadWithoutBusy(sessionID)
            }

            appendLocalManusMessage(role: "user", content: message, attachments: attachments)
            isBusy = false
            startManusChatStream(route: .hippoChat, sessionID: sessionID, message: message, attachments: attachments)
        } catch {
            isBusy = false
            isManusChatRunning = false
            lastError = error.localizedDescription
        }
    }

    func queueLocalManusDraft(_ content: String, attachments: [JSONValue]? = nil) {
        let message = content.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !message.isEmpty else { return }

        ensureLocalDraftThread(title: message)
        appendLocalManusMessage(role: "user", content: message, attachments: attachments)
        lastError = "Manus is unavailable. Draft was kept locally and can be sent after reconnect."
    }

    func startLocalManusDraftThread() {
        ensureLocalDraftThread(title: "Local draft")
        lastError = nil
    }

    func stopManusThread() async {
        manusChatTask?.cancel()
        manusChatTask = nil
        activeManusChatRunID = nil
        isManusChatRunning = false
        guard let currentManusThread else { return }

        do {
            try await withOrchestratorRecovery(action: "app_state.stop_manus") {
                try await client.stopManusSession(sessionID: currentManusThread.id)
            }
            manusThreads = (try? await withOrchestratorRecovery(action: "app_state.stop_manus.sessions") {
                try await client.manusSessions().sessions
            }) ?? manusThreads
            self.currentManusThread = manusThreads.first { $0.id == currentManusThread.id } ?? currentManusThread
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    private func startManusChatStream(
        route: ManusChatStreamRoute,
        sessionID: String,
        message: String,
        attachments: [JSONValue]?
    ) {
        let runID = UUID()
        activeManusChatRunID = runID
        isManusChatRunning = true
        lastError = nil

        let task = Task { @MainActor [weak self] in
            guard let self else { return }
            defer {
                if self.activeManusChatRunID == runID {
                    self.isManusChatRunning = false
                    self.manusChatTask = nil
                    self.activeManusChatRunID = nil
                }
            }

            do {
                switch route {
                case .directManus:
                    try await self.client.streamManusChat(sessionID: sessionID, message: message, attachments: attachments) { event in
                        await MainActor.run {
                            self.applyManusStreamEvent(event)
                        }
                    }
                    await self.refreshManusThreadAfterStream(sessionID)
                case .hippoChat:
                    try await self.client.streamChatMessage(sessionID: sessionID, message: message, attachments: attachments) { event in
                        await MainActor.run {
                            self.applyManusStreamEvent(event)
                        }
                    }
                    await self.refreshManusThreadAfterStream(sessionID)
                }

                if self.activeManusChatRunID == runID, self.manusMessages.last?.role != "assistant_error" {
                    self.lastError = nil
                }
            } catch {
                guard self.activeManusChatRunID == runID else { return }
                if self.isCancellation(error) {
                    return
                }
                if self.isOrchestratorConnectionFailure(error) {
                    try? await self.recoverLocalOrchestrator(action: "app_state.manus_chat_stream", originalError: error)
                }
                self.lastError = error.localizedDescription
                self.appendManusErrorMessage(
                    from: .object([
                        "event_id": .string("client_stream_error_\(Int(Date().timeIntervalSince1970))"),
                        "timestamp": .number(Date().timeIntervalSince1970),
                        "error": .string("Chat stream failed: \(error.localizedDescription)")
                    ])
                )
            }
        }
        manusChatTask = task
    }

    private func refreshManusThreadAfterStream(_ sessionID: String) async {
        manusThreads = (try? await withOrchestratorRecovery(action: "app_state.refresh_manus_thread_after_stream.sessions") {
            try await client.manusSessions().sessions
        }) ?? manusThreads
        try? await loadManusThreadWithoutBusy(sessionID)
    }

    func loadManusSandboxAccess() async {
        guard let currentManusThread else {
            resetManusPhaseTwoState()
            return
        }

        isLoadingManusSandboxAccess = true
        defer { isLoadingManusSandboxAccess = false }

        do {
            manusSandboxAccess = try await withOrchestratorRecovery(action: "app_state.load_manus_sandbox_access") {
                try await client.manusSandboxAccess(sessionID: currentManusThread.id)
            }
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func loadManusFiles() async {
        guard let currentManusThread else {
            resetManusPhaseTwoState()
            return
        }

        isLoadingManusFiles = true
        defer { isLoadingManusFiles = false }

        do {
            manusFilesResponse = try await withOrchestratorRecovery(action: "app_state.load_manus_files") {
                try await client.manusFiles(sessionID: currentManusThread.id)
            }
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func loadManusFilePreview(_ file: ManusFileInfo) async {
        guard let currentManusThread else { return }
        guard file.path?.isEmpty == false || file.filePath?.isEmpty == false else {
            lastError = "Manus file preview requires a sandbox file path."
            return
        }

        isLoadingManusFilePreview = true
        defer { isLoadingManusFilePreview = false }

        do {
            manusFilePreview = try await withOrchestratorRecovery(action: "app_state.load_manus_file_preview") {
                try await client.manusFilePreview(sessionID: currentManusThread.id, file: file)
            }
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func loadManusDownloadLink(for file: ManusFileInfo) async -> ManusFileDownloadLink? {
        guard !file.fileIdentifier.isEmpty else {
            lastError = "Manus file is missing a file id."
            return nil
        }

        isLoadingManusFileDownloadLink = true
        defer { isLoadingManusFileDownloadLink = false }

        do {
            let link = try await withOrchestratorRecovery(action: "app_state.load_manus_download_link") {
                try await client.manusFileDownloadLink(fileID: file.fileIdentifier)
            }
            manusFileDownloadLink = link
            lastError = nil
            return link
        } catch {
            lastError = error.localizedDescription
            return nil
        }
    }

    func jarvisOn() async {
        await run { try await self.client.jarvisOn() }
    }

    func jarvisOff() async {
        await run { try await self.client.jarvisOff() }
    }

    func pause() async {
        await run { try await self.client.pause() }
    }

    func resume() async {
        await run { try await self.client.resume() }
    }

    func captureSkill() async {
        await run { try await self.client.captureStart() }
    }

    func finishCapture() async {
        await run { try await self.client.captureFinish() }
    }

    func generateActiveTask() async {
        await run { try await self.client.generateActiveTask() }
    }

    func confirmCurrentTask() async {
        guard let id = snapshot.currentTask?.id else { return }
        await run { try await self.client.confirm(taskID: id) }
    }

    func ignoreCurrentTask() async {
        guard let id = snapshot.currentTask?.id else { return }
        await run { try await self.client.ignore(taskID: id) }
    }

    func completeCurrentTask() async {
        guard let id = snapshot.currentTask?.id else { return }
        await run { try await self.client.complete(taskID: id) }
    }

    func generateSkill() async {
        await run { try await self.client.generateSkill() }
    }

    func deleteSkill(id: SkillRecord.ID) async {
        await run { try await self.client.deleteSkill(skillID: id) }
    }

    func openChronicleStart() async {
        await run { try await self.client.openChronicleStart() }
    }

    func openChronicleStop() async {
        await run { try await self.client.openChronicleStop() }
    }

    func openChroniclePause() async {
        await run { try await self.client.openChroniclePause() }
    }

    func openChronicleResume() async {
        await run { try await self.client.openChronicleResume() }
    }

    func openChronicleCaptureOnce() async {
        await run { try await self.client.openChronicleCaptureOnce() }
    }

    func openChronicleRebuildCapturesIndex() async {
        await run { try await self.client.openChronicleRebuildCapturesIndex() }
    }

    func openChronicleTimelineTick() async {
        await run { try await self.client.openChronicleTimelineTick() }
    }

    func refreshVlmacPreflight(network: Bool = false) async {
        isBusy = true
        defer { isBusy = false }

        do {
            vlmacConfig = try await withOrchestratorRecovery(action: "app_state.refresh_vlmac.config") {
                try await client.vlmacConfig()
            }
            let service = try await withOrchestratorRecovery(action: "app_state.refresh_vlmac.status") {
                try await client.vlmacStatus()
            }
            applyVlmacService(service)
            vlmacPreflight = try await withOrchestratorRecovery(action: "app_state.refresh_vlmac.preflight") {
                try await client.vlmacPreflight(network: network)
            }
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func vlmacStart() async {
        await run { try await self.client.vlmacStart() }
    }

    func vlmacStop() async {
        await run { try await self.client.vlmacStop() }
    }

    func vlmacRestart() async {
        await run { try await self.client.vlmacRestart() }
    }

    func updateVlmacConfig(
        vlmBaseUrl: String? = nil,
        vlmModel: String? = nil,
        vlmApiKey: String? = nil
    ) async {
        isBusy = true
        defer { isBusy = false }

        do {
            vlmacConfig = try await withOrchestratorRecovery(action: "app_state.update_vlmac") {
                try await client.updateVlmacConfig(
                    VlmacConfigRequest(
                        vlmBaseUrl: vlmBaseUrl,
                        vlmModel: vlmModel,
                        vlmApiKey: vlmApiKey
                    )
                )
            }
            let service = try await withOrchestratorRecovery(action: "app_state.update_vlmac.status") {
                try await client.vlmacStatus()
            }
            applyVlmacService(service)
            vlmacPreflight = try await withOrchestratorRecovery(action: "app_state.update_vlmac.preflight") {
                try await client.vlmacPreflight(network: false)
            }
            snapshot = try await withOrchestratorRecovery(action: "app_state.update_vlmac.state") {
                try await client.state()
            }
            await refreshEventHistory()
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func cuaDriverStart() async {
        await run { try await self.client.cuaDriverStart() }
    }

    func cuaDriverStop() async {
        await run { try await self.client.cuaDriverStop() }
    }

    func cuaDriverRestart() async {
        await run { try await self.client.cuaDriverRestart() }
    }

    func updateOwnscribeConfig(
        audioSource: OwnscribeAudioSource? = nil,
        micDevice: String? = nil,
        audioDisplay: Bool? = nil,
        asrProvider: String? = nil,
        asrBaseUrl: String? = nil,
        asrModel: String? = nil,
        asrApiKey: String? = nil,
        summaryProvider: String? = nil,
        summaryBaseUrl: String? = nil,
        summaryModel: String? = nil,
        summaryApiKey: String? = nil,
        apiKey: String? = nil
    ) async {
        isBusy = true
        defer { isBusy = false }

        do {
            ownscribeConfig = try await withOrchestratorRecovery(action: "app_state.update_ownscribe") {
                try await client.updateOwnscribeConfig(
                    OwnscribeConfigRequest(
                        audioSource: audioSource,
                        micDevice: micDevice,
                        audioDisplay: audioDisplay,
                        asrProvider: asrProvider,
                        asrBaseUrl: asrBaseUrl,
                        asrModel: asrModel,
                        asrApiKey: asrApiKey,
                        summaryProvider: summaryProvider,
                        summaryBaseUrl: summaryBaseUrl,
                        summaryModel: summaryModel,
                        summaryApiKey: summaryApiKey,
                        apiKey: apiKey
                    )
                )
            }
            ownscribePreflight = try await withOrchestratorRecovery(action: "app_state.update_ownscribe.preflight") {
                try await client.ownscribePreflight(network: false)
            }
            snapshot = try await withOrchestratorRecovery(action: "app_state.update_ownscribe.state") {
                try await client.state()
            }
            await refreshEventHistory()
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func setLanguage(_ nextLanguage: AppLanguage) {
        language = nextLanguage
    }

    func text(_ key: AppCopyKey) -> String {
        AppCopy.text(key, language: language)
    }

    func shortStateLabel(_ state: JarvisState) -> String {
        AppCopy.shortStateLabel(state, language: language)
    }

    func stateName(_ state: JarvisState) -> String {
        AppCopy.stateName(state, language: language)
    }

    func serviceStatus(_ status: String) -> String {
        AppCopy.serviceStatus(status, language: language)
    }

    func serviceDetail(_ detail: String?, status: String) -> String {
        AppCopy.serviceDetail(detail, status: status, language: language)
    }

    private func withOrchestratorRecovery<T>(
        action: String,
        _ operation: () async throws -> T
    ) async throws -> T {
        do {
            return try await operation()
        } catch {
            guard shouldRecoverLocalOrchestrator(after: error) else {
                throw error
            }
            try await recoverLocalOrchestrator(action: action, originalError: error)
            return try await operation()
        }
    }

    private func shouldRecoverLocalOrchestrator(after error: Error) -> Bool {
        guard isLocalOrchestratorBaseURL else { return false }
        return isOrchestratorConnectionFailure(error)
    }

    private func recoverLocalOrchestrator(action: String, originalError: Error) async throws {
        let startedAt = AppLog.start()
        if isRecoveringOrchestrator {
            AppLog.event(action: "orchestrator.recover", path: action, status: "waiting", startedAt: startedAt, error: originalError)
            while isRecoveringOrchestrator {
                try await Task.sleep(nanoseconds: 100_000_000)
            }
            if (try? await client.health()) == true {
                AppLog.event(action: "orchestrator.recover", path: action, status: "ready_after_wait", startedAt: startedAt)
                return
            }
        }

        isRecoveringOrchestrator = true
        defer { isRecoveringOrchestrator = false }

        AppLog.event(action: "orchestrator.recover", path: action, status: "starting", startedAt: startedAt, error: originalError)
        do {
            try await launcher.ensureRunning(client: client)
            AppLog.event(action: "orchestrator.recover", path: action, status: "ready", startedAt: startedAt)
        } catch {
            AppLog.event(action: "orchestrator.recover", path: action, status: "error", startedAt: startedAt, error: error)
            throw error
        }
    }

    private var isLocalOrchestratorBaseURL: Bool {
        let stored = UserDefaults.standard.string(forKey: "orchestratorBaseURL")
        let value = stored?.isEmpty == false ? stored! : "http://127.0.0.1:8787"
        guard let url = URL(string: value), let host = url.host?.lowercased() else {
            return true
        }
        return host == "127.0.0.1" || host == "localhost" || host == "::1"
    }

    private func isOrchestratorConnectionFailure(_ error: Error) -> Bool {
        guard let urlError = error as? URLError else { return false }
        switch urlError.code {
        case .cannotConnectToHost, .networkConnectionLost, .cannotFindHost, .dnsLookupFailed:
            return true
        default:
            return false
        }
    }

    private func isOrchestratorUnavailable(_ error: Error) -> Bool {
        if isOrchestratorConnectionFailure(error) {
            return true
        }
        if case OrchestratorError.badStatus(let code, _) = error, code < 0 {
            return true
        }
        return false
    }

    private func run(_ operation: @escaping () async throws -> AppSnapshot) async {
        let startedAt = AppLog.start()
        isBusy = true
        defer { isBusy = false }

        do {
            let next = try await withOrchestratorRecovery(action: "app_state.run") {
                try await operation()
            }
            snapshot = next
            skillStore.persist(next.skills)
            await refreshCuaTargetSurface()
            await refreshEventHistory()
            await loadContextFragments(reportErrors: false)
            lastError = nil
            AppLog.event(action: "app_state.run", status: "ok", startedAt: startedAt, eventCount: eventHistory.count)
        } catch {
            lastError = error.localizedDescription
            snapshot = AppSnapshot(
                jarvisState: .error,
                statusMessage: error.localizedDescription,
                currentSession: snapshot.currentSession,
                sopCapture: snapshot.sopCapture,
                currentTask: snapshot.currentTask,
                skills: snapshot.skills,
                services: snapshot.services
            )
            AppLog.event(action: "app_state.run", status: "error", startedAt: startedAt, error: error)
        }
    }

    private func refreshEventHistory() async {
        let events = try? await withOrchestratorRecovery(action: "app_state.refresh_event_history") {
            try await client.eventHistory(limit: 80)
        }
        if let events {
            eventHistory = events
        }
    }

    private func loadContextFragments(reportErrors: Bool) async {
        do {
            let response = try await withOrchestratorRecovery(action: "app_state.load_context_fragments") {
                try await client.recentContextFragments(
                    sessionID: snapshot.currentSession?.id,
                    modality: "voice",
                    limit: 8
                )
            }
            contextFragments = response.resolvedFragments
            if reportErrors {
                lastError = nil
            }
        } catch {
            if reportErrors {
                lastError = error.localizedDescription
            }
        }
    }

    private func refreshCuaTargetSurface() async {
        guard snapshot.currentTask != nil else {
            cuaTargetSurface = .empty
            return
        }
        let surface = try? await withOrchestratorRecovery(action: "app_state.refresh_cua_target_surface") {
            try await client.cuaTargetSurface()
        }
        if let surface {
            cuaTargetSurface = surface
        }
    }

    private func runAiManusRuntimeCommand(
        _ operation: @escaping () async throws -> AiManusRuntimeCommandResponse
    ) async {
        isRunningAiManusRuntimeCommand = true
        defer { isRunningAiManusRuntimeCommand = false }

        do {
            let response = try await withOrchestratorRecovery(action: "app_state.ai_manus_runtime_command") {
                try await operation()
            }
            aiManusRuntimeLastCommand = response
            applyAiManusRuntimeService(response.service)
            aiManusRuntimeLogs = (try? await withOrchestratorRecovery(action: "app_state.ai_manus_runtime_command.logs_before_refresh") {
                try await client.aiManusRuntimeLogs(limit: 80)
            }) ?? aiManusRuntimeLogs
            try? await Task.sleep(nanoseconds: 1_000_000_000)
            await refreshManus()
            aiManusRuntimeLogs = (try? await withOrchestratorRecovery(action: "app_state.ai_manus_runtime_command.logs_after_refresh") {
                try await client.aiManusRuntimeLogs(limit: 80)
            }) ?? aiManusRuntimeLogs
            await refreshEventHistory()
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    private func loadBasicMemoryNotePreview(_ request: BasicMemoryNotePreviewRequest) async {
        guard request.identifier?.isEmpty == false || request.path?.isEmpty == false || request.permalink?.isEmpty == false else {
            return
        }

        do {
            basicMemoryNotePreview = try await withOrchestratorRecovery(action: "app_state.load_basic_memory_note_preview") {
                try await client.basicMemoryNotePreview(request)
            }
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    private func syncBasicMemorySession(_ sessionID: String) async {
        isRunningBasicMemoryCommand = true
        defer { isRunningBasicMemoryCommand = false }

        do {
            basicMemoryLastSync = try await withOrchestratorRecovery(action: "app_state.sync_basic_memory_session") {
                try await client.syncBasicMemorySession(sessionID)
            }
            basicMemoryRecent = (try? await withOrchestratorRecovery(action: "app_state.sync_basic_memory_session.recent") {
                try await client.recentBasicMemoryNotes(limit: 8)
            }) ?? basicMemoryRecent
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    private func syncBasicMemoryTask(_ taskID: String) async {
        isRunningBasicMemoryCommand = true
        defer { isRunningBasicMemoryCommand = false }

        do {
            basicMemoryLastSync = try await withOrchestratorRecovery(action: "app_state.sync_basic_memory_task") {
                try await client.syncBasicMemoryTask(taskID)
            }
            basicMemoryRecent = (try? await withOrchestratorRecovery(action: "app_state.sync_basic_memory_task.recent") {
                try await client.recentBasicMemoryNotes(limit: 8)
            }) ?? basicMemoryRecent
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    private func syncBasicMemorySkill(_ skillID: String) async {
        isRunningBasicMemoryCommand = true
        defer { isRunningBasicMemoryCommand = false }

        do {
            basicMemoryLastSync = try await withOrchestratorRecovery(action: "app_state.sync_basic_memory_skill") {
                try await client.syncBasicMemorySkill(skillID)
            }
            basicMemoryRecent = (try? await withOrchestratorRecovery(action: "app_state.sync_basic_memory_skill.recent") {
                try await client.recentBasicMemoryNotes(limit: 8)
            }) ?? basicMemoryRecent
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    private func syncBasicMemoryContext(_ fragmentID: String) async {
        isRunningBasicMemoryCommand = true
        defer { isRunningBasicMemoryCommand = false }

        do {
            basicMemoryLastSync = try await withOrchestratorRecovery(action: "app_state.sync_basic_memory_context") {
                try await client.syncBasicMemoryContext(fragmentID: fragmentID)
            }
            basicMemoryRecent = (try? await withOrchestratorRecovery(action: "app_state.sync_basic_memory_context.recent") {
                try await client.recentBasicMemoryNotes(limit: 8)
            }) ?? basicMemoryRecent
            await loadContextFragments(reportErrors: false)
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    private func applyAiManusRuntimeService(_ service: ServiceStatus?) {
        guard let service else { return }
        aiManusStatus = AiManusStatus(
            ok: service.status == "online",
            status: service.status,
            detail: service.detail,
            config: aiManusConfig
        )
    }

    private func applyBasicMemoryService(_ service: ServiceStatus?) {
        guard let service else { return }
        if let index = snapshot.services.firstIndex(where: { $0.id == service.id || $0.name.lowercased() == service.name.lowercased() }) {
            snapshot.services[index] = service
        } else {
            snapshot.services.append(service)
        }
    }

    private func applyVlmacService(_ service: ServiceStatus?) {
        guard let service else { return }
        if let index = snapshot.services.firstIndex(where: { $0.id == service.id || $0.name.lowercased() == service.name.lowercased() }) {
            snapshot.services[index] = service
        } else {
            snapshot.services.append(service)
        }
    }

    private func loadManusThreadWithoutBusy(_ sessionID: String) async throws {
        let detail = try await withOrchestratorRecovery(action: "app_state.load_manus_thread") {
            try await client.manusThreadDetail(sessionID: sessionID)
        }
        currentManusThread = ManusThread(
            sessionId: detail.sessionId,
            manusSessionId: detail.manusSessionId,
            title: detail.title ?? detail.remote?.title,
            status: detail.remoteStatus ?? detail.remote?.status ?? detail.status,
            latestMessage: nil,
            latestMessageAt: nil,
            unreadMessageCount: nil,
            isShared: detail.isShared
        )
        if let currentManusThread {
            if let index = manusThreads.firstIndex(where: { $0.id == detail.sessionId || $0.sessionId == detail.sessionId }) {
                manusThreads[index] = currentManusThread
            } else {
                manusThreads.insert(currentManusThread, at: 0)
            }
        }
        manusMessages = []
        manusPlan = []
        manusTools = []
        resetManusPhaseTwoState()
        if let messages = detail.messages {
            manusMessages = messages
        }
        for event in detail.events {
            if detail.messages?.isEmpty == false, event.event == "message" {
                continue
            }
            applyManusStreamEvent(event)
        }
    }

    private func appendLocalManusMessage(role: String, content: String, attachments: [JSONValue]? = nil) {
        let now = Int(Date().timeIntervalSince1970)
        manusMessages.append(
            ManusMessage(
                id: "local_\(role)_\(now)_\(manusMessages.count)",
                role: role,
                content: content,
                timestamp: now,
                eventId: nil,
                attachments: attachments
            )
        )
    }

    private func ensureLocalDraftThread(title: String) {
        if currentManusThread != nil { return }

        let now = Date()
        let timestamp = Int(now.timeIntervalSince1970)
        let trimmedTitle = title.trimmingCharacters(in: .whitespacesAndNewlines)
        let displayTitle = trimmedTitle.isEmpty ? "Local draft" : String(trimmedTitle.prefix(48))
        let thread = ManusThread(
            sessionId: "local-\(UUID().uuidString)",
            title: displayTitle,
            status: "local_draft",
            latestMessage: trimmedTitle,
            latestMessageAt: timestamp,
            unreadMessageCount: 0,
            isShared: false,
            createdAt: ISO8601DateFormatter().string(from: now),
            updatedAt: ISO8601DateFormatter().string(from: now)
        )
        currentManusThread = thread
        manusThreads.insert(thread, at: 0)
        manusMessages = []
        manusPlan = []
        manusTools = []
    }

    private func applyManusStreamEvent(_ event: ManusStreamEvent) {
        guard let data = event.data else { return }
        switch event.event {
        case "message":
            if let message = makeManusMessage(from: data) {
                manusMessages.append(message)
            }
        case "message_delta":
            appendAssistantMessageDelta(from: data)
        case "message_complete":
            break
        case "plan", "plan_updated":
            manusPlan = planSteps(from: data)
        case "step":
            if let step = makePlanStep(from: data) {
                if let index = manusPlan.firstIndex(where: { $0.id == step.id }) {
                    manusPlan[index] = step
                } else {
                    manusPlan.append(step)
                }
            }
        case "tool", "tool_event":
            if let tool = makeToolEvent(from: data) {
                if let index = manusTools.firstIndex(where: { $0.id == tool.id }) {
                    manusTools[index] = tool
                } else {
                    manusTools.append(tool)
                }
            }
        case "thread":
            updateCurrentManusThread(from: data)
        case "title":
            updateCurrentManusTitle(from: data)
        case "error", "auth_required":
            appendManusErrorMessage(from: data)
        default:
            break
        }
    }

    private func appendManusErrorMessage(from value: JSONValue) {
        let now = Int(Date().timeIntervalSince1970)
        let message: String
        let eventId: String?
        let timestamp: Int?
        if case .object(let object) = value {
            message = stringField("error", in: object)
                ?? stringField("message", in: object)
                ?? stringField("detail", in: object)
                ?? "Manus returned an error."
            eventId = normalizedEventId(from: object)
            timestamp = intField("timestamp", in: object)
        } else if case .string(let text) = value {
            message = text.isEmpty ? "Manus returned an error." : text
            eventId = nil
            timestamp = nil
        } else {
            message = value.compactDescription.isEmpty ? "Manus returned an error." : value.compactDescription
            eventId = nil
            timestamp = nil
        }

        lastError = message
        if manusMessages.last?.role == "assistant_error", manusMessages.last?.content == message {
            return
        }
        manusMessages.append(
            ManusMessage(
                id: eventId ?? "message_error_\(timestamp ?? now)_\(manusMessages.count)",
                role: "assistant_error",
                content: message,
                timestamp: timestamp ?? now,
                eventId: eventId,
                attachments: nil
            )
        )
    }

    private func isCancellation(_ error: Error) -> Bool {
        if error is CancellationError {
            return true
        }
        if let urlError = error as? URLError, urlError.code == .cancelled {
            return true
        }
        return false
    }

    private func appendAssistantMessageDelta(from value: JSONValue) {
        guard case .object(let object) = value else { return }
        let delta = stringField("content", in: object) ?? stringField("delta", in: object) ?? stringField("answer", in: object)
        guard let delta, !delta.isEmpty else { return }
        let eventId = normalizedEventId(from: object)
        let timestamp = intField("timestamp", in: object)

        if let eventId,
           let index = manusMessages.lastIndex(where: { $0.role == "assistant" && $0.eventId == eventId }) {
            manusMessages[index].content += delta
            manusMessages[index].timestamp = timestamp ?? manusMessages[index].timestamp
            return
        }

        if eventId == nil,
           let index = manusMessages.indices.last,
           manusMessages[index].role == "assistant",
           manusMessages[index].eventId == nil {
            manusMessages[index].content += delta
            manusMessages[index].timestamp = timestamp ?? manusMessages[index].timestamp
            return
        }

        manusMessages.append(
            ManusMessage(
                id: eventId ?? "message_delta_\(timestamp ?? Int(Date().timeIntervalSince1970))_\(manusMessages.count)",
                role: "assistant",
                content: delta,
                timestamp: timestamp,
                eventId: eventId,
                attachments: arrayField("attachments", in: object)
            )
        )
    }

    private func makeManusMessage(from value: JSONValue) -> ManusMessage? {
        guard case .object(let object) = value else { return nil }
        let content = stringField("content", in: object) ?? stringField("message", in: object)
        guard let content else { return nil }
        let eventId = normalizedEventId(from: object)
        let timestamp = intField("timestamp", in: object)
        return ManusMessage(
            id: eventId ?? "message_\(timestamp ?? Int(Date().timeIntervalSince1970))_\(manusMessages.count)",
            role: stringField("role", in: object) ?? "assistant",
            content: content,
            timestamp: timestamp,
            eventId: eventId,
            attachments: arrayField("attachments", in: object)
        )
    }

    private func planSteps(from value: JSONValue) -> [ManusPlanStep] {
        guard case .object(let object) = value, let steps = arrayField("steps", in: object) else {
            return []
        }
        return steps.compactMap(makePlanStep)
    }

    private func makePlanStep(from value: JSONValue) -> ManusPlanStep? {
        guard case .object(let object) = value, let id = stringField("id", in: object) else { return nil }
        return ManusPlanStep(
            id: id,
            description: stringField("description", in: object) ?? "",
            status: stringField("status", in: object) ?? "pending",
            timestamp: intField("timestamp", in: object),
            eventId: stringField("event_id", in: object) ?? stringField("eventId", in: object)
        )
    }

    private func normalizedEventId(from object: [String: JSONValue]) -> String? {
        let raw = stringField("event_id", in: object) ?? stringField("eventId", in: object) ?? stringField("message_id", in: object) ?? stringField("messageId", in: object)
        guard let raw else { return nil }
        let trimmed = raw.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }

    private func makeToolEvent(from value: JSONValue) -> ManusToolEvent? {
        guard case .object(let object) = value else { return nil }
        let callID = stringField("tool_call_id", in: object) ?? stringField("toolCallId", in: object)
        guard let callID else { return nil }
        return ManusToolEvent(
            toolCallId: callID,
            name: stringField("name", in: object) ?? "",
            function: stringField("function", in: object) ?? "",
            status: stringField("status", in: object) ?? "calling",
            args: objectField("args", in: object) ?? [:],
            content: object["content"],
            timestamp: intField("timestamp", in: object),
            eventId: stringField("event_id", in: object) ?? stringField("eventId", in: object)
        )
    }

    private func updateCurrentManusTitle(from value: JSONValue) {
        guard let title = stringField("title", in: value), var thread = currentManusThread else { return }
        thread.title = title
        currentManusThread = thread
        if let index = manusThreads.firstIndex(where: { $0.id == thread.id }) {
            manusThreads[index] = thread
        }
    }

    private func updateCurrentManusThread(from value: JSONValue) {
        guard case .object(let object) = value else { return }
        let sessionID = stringField("session_id", in: object)
            ?? stringField("sessionId", in: object)
            ?? currentManusThread?.sessionId
        guard let sessionID else { return }

        var thread = currentManusThread
        if thread?.sessionId != sessionID {
            thread = manusThreads.first { $0.sessionId == sessionID || $0.id == sessionID }
        }

        var updated = thread ?? ManusThread(
            sessionId: sessionID,
            title: nil,
            status: "unknown",
            latestMessage: nil,
            latestMessageAt: nil,
            unreadMessageCount: nil,
            isShared: nil
        )
        updated.id = stringField("id", in: object) ?? updated.id
        updated.sessionId = sessionID
        updated.manusSessionId = stringField("manus_session_id", in: object)
            ?? stringField("manusSessionId", in: object)
            ?? updated.manusSessionId
        updated.title = stringField("title", in: object) ?? updated.title
        updated.status = stringField("status", in: object) ?? updated.status
        updated.latestMessage = stringField("latest_message", in: object)
            ?? stringField("latestMessage", in: object)
            ?? updated.latestMessage
        updated.latestMessageAt = intField("latest_message_at", in: object)
            ?? intField("latestMessageAt", in: object)
            ?? updated.latestMessageAt
        updated.unreadMessageCount = intField("unread_message_count", in: object)
            ?? intField("unreadMessageCount", in: object)
            ?? updated.unreadMessageCount
        updated.isShared = boolField("is_shared", in: object)
            ?? boolField("isShared", in: object)
            ?? updated.isShared
        updated.createdAt = stringField("created_at", in: object)
            ?? stringField("createdAt", in: object)
            ?? updated.createdAt
        updated.updatedAt = stringField("updated_at", in: object)
            ?? stringField("updatedAt", in: object)
            ?? updated.updatedAt

        currentManusThread = updated
        if let index = manusThreads.firstIndex(where: { $0.id == updated.id || $0.sessionId == sessionID }) {
            manusThreads[index] = updated
        } else {
            manusThreads.insert(updated, at: 0)
        }
    }

    private func stringField(_ key: String, in value: JSONValue) -> String? {
        guard case .object(let object) = value else { return nil }
        return stringField(key, in: object)
    }

    private func stringField(_ key: String, in object: [String: JSONValue]) -> String? {
        guard case .string(let value)? = object[key] else { return nil }
        return value
    }

    private func intField(_ key: String, in object: [String: JSONValue]) -> Int? {
        switch object[key] {
        case .number(let value):
            return Int(value)
        case .string(let value):
            return Int(value)
        default:
            return nil
        }
    }

    private func boolField(_ key: String, in object: [String: JSONValue]) -> Bool? {
        guard case .bool(let value)? = object[key] else { return nil }
        return value
    }

    private func arrayField(_ key: String, in object: [String: JSONValue]) -> [JSONValue]? {
        guard case .array(let value)? = object[key] else { return nil }
        return value
    }

    private func objectField(_ key: String, in object: [String: JSONValue]) -> [String: JSONValue]? {
        guard case .object(let value)? = object[key] else { return nil }
        return value
    }

    private func ensureOrchestrator() async {
        let startedAt = AppLog.start()
        do {
            try await launcher.ensureRunning(client: client)
            AppLog.event(action: "app_state.ensure_orchestrator", status: "ok", startedAt: startedAt)
        } catch {
            let prefix = language == .simplifiedChinese ? "无法启动 Orchestrator" : "Could not start Orchestrator"
            lastError = "\(prefix): \(error.localizedDescription)"
            AppLog.event(action: "app_state.ensure_orchestrator", status: "error", startedAt: startedAt, error: error)
        }
    }

    private func startEvents() {
        guard eventsTask == nil else { return }
        AppLog.event(action: "app_state.start_events", path: "events", status: "starting")

        eventsTask = Task { [weak self] in
            guard let self else { return }
            let startedAt = AppLog.start()
            defer {
                self.eventsTask = nil
            }
            do {
                try await self.withOrchestratorRecovery(action: "app_state.start_events") {
                    try await self.client.listenForEvents {
                        await self.refresh()
                    }
                }
                AppLog.event(action: "app_state.start_events", path: "events", status: "ended", startedAt: startedAt)
            } catch {
                AppLog.event(action: "app_state.start_events", path: "events", status: "error", startedAt: startedAt, error: error)
                await MainActor.run {
                    let prefix = self.language == .simplifiedChinese ? "事件流已断开" : "Event stream disconnected"
                    self.lastError = "\(prefix): \(error.localizedDescription)"
                }
            }
        }
    }

    private func resetManusPhaseTwoState() {
        manusSandboxAccess = nil
        manusFilesResponse = .empty
        manusFilePreview = nil
        manusFileDownloadLink = nil
    }
}
