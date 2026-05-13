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
    private var eventsTask: Task<Void, Never>?
    private var manusChatTask: Task<Void, Never>?

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
        guard !bootstrapped else { return }
        bootstrapped = true
        await ensureOrchestrator()
        await refresh()
        startEvents()
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
            ownscribeConfig = try await client.ownscribeConfig()
            ownscribeDevices = try await client.ownscribeAudioDevices()
            ownscribePreflight = try await client.ownscribePreflight(network: networkPreflight)
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func refreshManus() async {
        isBusy = true
        defer { isBusy = false }

        do {
            var config = try await client.aiManusConfig()
            aiManusStatus = try await client.aiManusStatus()
            config.status = aiManusStatus.status
            aiManusConfig = config
            manusThreads = try await client.manusSessions().sessions
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
            basicMemoryConfig = try await client.basicMemoryConfig()
            basicMemoryStatus = try await client.basicMemoryStatus()
            applyBasicMemoryService(basicMemoryStatus.service)
            basicMemoryRecent = (try? await client.recentBasicMemoryNotes(limit: 8)) ?? basicMemoryRecent
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func setupBasicMemory() async {
        isRunningBasicMemoryCommand = true
        defer { isRunningBasicMemoryCommand = false }

        do {
            basicMemoryStatus = try await client.setupBasicMemory()
            basicMemoryConfig = try await client.basicMemoryConfig()
            applyBasicMemoryService(basicMemoryStatus.service)
            basicMemoryRecent = (try? await client.recentBasicMemoryNotes(limit: 8)) ?? basicMemoryRecent
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
            basicMemorySearch = try await client.searchBasicMemory(query: trimmed, limit: 8)
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
            basicMemoryRecent = try await client.recentBasicMemoryNotes(limit: 8)
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
            var config = try await client.updateAiManusConfig(request)
            aiManusStatus = try await client.aiManusStatus()
            config.status = aiManusStatus.status
            aiManusConfig = config
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
            aiManusRuntimeLogs = try await client.aiManusRuntimeLogs(limit: 80)
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func newManusThread() async {
        isBusy = true
        defer { isBusy = false }

        do {
            let response = try await client.createManusSession()
            manusThreads = try await client.manusSessions().sessions
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
            let response = try await client.createChatSession()
            manusThreads = (try? await client.manusSessions().sessions) ?? manusThreads
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

        manusChatTask?.cancel()
        isBusy = true
        defer { isBusy = false }

        do {
            let sessionID: String
            if let currentManusThread {
                sessionID = currentManusThread.id
            } else {
                let response = try await client.createManusSession()
                sessionID = response.sessionId
                manusThreads = try await client.manusSessions().sessions
                try await loadManusThreadWithoutBusy(sessionID)
            }

            appendLocalManusMessage(role: "user", content: message, attachments: attachments)
            try await client.streamManusChat(sessionID: sessionID, message: message, attachments: attachments) { event in
                await MainActor.run {
                    self.applyManusStreamEvent(event)
                }
            }
            manusThreads = try await client.manusSessions().sessions
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func sendChatMessage(_ content: String, attachments: [JSONValue]? = nil) async {
        let message = content.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !message.isEmpty else { return }

        manusChatTask?.cancel()
        isBusy = true
        defer { isBusy = false }

        do {
            let sessionID: String
            if let currentManusThread, !currentManusThread.id.hasPrefix("local-") {
                sessionID = currentManusThread.id
            } else {
                let response = try await client.createChatSession()
                sessionID = response.sessionId
                manusThreads = (try? await client.manusSessions().sessions) ?? manusThreads
                try await loadManusThreadWithoutBusy(sessionID)
            }

            appendLocalManusMessage(role: "user", content: message, attachments: attachments)
            try await client.streamChatMessage(sessionID: sessionID, message: message, attachments: attachments) { event in
                await MainActor.run {
                    self.applyManusStreamEvent(event)
                }
            }
            manusThreads = (try? await client.manusSessions().sessions) ?? manusThreads
            lastError = nil
        } catch {
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
        guard let currentManusThread else { return }
        manusChatTask?.cancel()
        manusChatTask = nil

        isBusy = true
        defer { isBusy = false }

        do {
            try await client.stopManusSession(sessionID: currentManusThread.id)
            manusThreads = try await client.manusSessions().sessions
            self.currentManusThread = manusThreads.first { $0.id == currentManusThread.id } ?? currentManusThread
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func loadManusSandboxAccess() async {
        guard let currentManusThread else {
            resetManusPhaseTwoState()
            return
        }

        isLoadingManusSandboxAccess = true
        defer { isLoadingManusSandboxAccess = false }

        do {
            manusSandboxAccess = try await client.manusSandboxAccess(sessionID: currentManusThread.id)
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
            manusFilesResponse = try await client.manusFiles(sessionID: currentManusThread.id)
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
            manusFilePreview = try await client.manusFilePreview(sessionID: currentManusThread.id, file: file)
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
            let link = try await client.manusFileDownloadLink(fileID: file.fileIdentifier)
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
            vlmacConfig = try await client.vlmacConfig()
            let service = try await client.vlmacStatus()
            applyVlmacService(service)
            vlmacPreflight = try await client.vlmacPreflight(network: network)
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
            vlmacConfig = try await client.updateVlmacConfig(
                VlmacConfigRequest(
                    vlmBaseUrl: vlmBaseUrl,
                    vlmModel: vlmModel,
                    vlmApiKey: vlmApiKey
                )
            )
            let service = try await client.vlmacStatus()
            applyVlmacService(service)
            vlmacPreflight = try await client.vlmacPreflight(network: false)
            snapshot = try await client.state()
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
            ownscribeConfig = try await client.updateOwnscribeConfig(
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
            ownscribePreflight = try await client.ownscribePreflight(network: false)
            snapshot = try await client.state()
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

    private func run(_ operation: @escaping () async throws -> AppSnapshot) async {
        isBusy = true
        defer { isBusy = false }

        do {
            let next = try await operation()
            snapshot = next
            skillStore.persist(next.skills)
            await refreshCuaTargetSurface()
            await refreshEventHistory()
            await loadContextFragments(reportErrors: false)
            lastError = nil
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
        }
    }

    private func refreshEventHistory() async {
        if let events = try? await client.eventHistory(limit: 80) {
            eventHistory = events
        }
    }

    private func loadContextFragments(reportErrors: Bool) async {
        do {
            let response = try await client.recentContextFragments(
                sessionID: snapshot.currentSession?.id,
                modality: "voice",
                limit: 8
            )
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
        if let surface = try? await client.cuaTargetSurface() {
            cuaTargetSurface = surface
        }
    }

    private func runAiManusRuntimeCommand(
        _ operation: @escaping () async throws -> AiManusRuntimeCommandResponse
    ) async {
        isRunningAiManusRuntimeCommand = true
        defer { isRunningAiManusRuntimeCommand = false }

        do {
            let response = try await operation()
            aiManusRuntimeLastCommand = response
            applyAiManusRuntimeService(response.service)
            aiManusRuntimeLogs = (try? await client.aiManusRuntimeLogs(limit: 80)) ?? aiManusRuntimeLogs
            try? await Task.sleep(nanoseconds: 1_000_000_000)
            await refreshManus()
            aiManusRuntimeLogs = (try? await client.aiManusRuntimeLogs(limit: 80)) ?? aiManusRuntimeLogs
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
            basicMemoryNotePreview = try await client.basicMemoryNotePreview(request)
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    private func syncBasicMemorySession(_ sessionID: String) async {
        isRunningBasicMemoryCommand = true
        defer { isRunningBasicMemoryCommand = false }

        do {
            basicMemoryLastSync = try await client.syncBasicMemorySession(sessionID)
            basicMemoryRecent = (try? await client.recentBasicMemoryNotes(limit: 8)) ?? basicMemoryRecent
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    private func syncBasicMemoryTask(_ taskID: String) async {
        isRunningBasicMemoryCommand = true
        defer { isRunningBasicMemoryCommand = false }

        do {
            basicMemoryLastSync = try await client.syncBasicMemoryTask(taskID)
            basicMemoryRecent = (try? await client.recentBasicMemoryNotes(limit: 8)) ?? basicMemoryRecent
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    private func syncBasicMemorySkill(_ skillID: String) async {
        isRunningBasicMemoryCommand = true
        defer { isRunningBasicMemoryCommand = false }

        do {
            basicMemoryLastSync = try await client.syncBasicMemorySkill(skillID)
            basicMemoryRecent = (try? await client.recentBasicMemoryNotes(limit: 8)) ?? basicMemoryRecent
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    private func syncBasicMemoryContext(_ fragmentID: String) async {
        isRunningBasicMemoryCommand = true
        defer { isRunningBasicMemoryCommand = false }

        do {
            basicMemoryLastSync = try await client.syncBasicMemoryContext(fragmentID: fragmentID)
            basicMemoryRecent = (try? await client.recentBasicMemoryNotes(limit: 8)) ?? basicMemoryRecent
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
        let detail = try await client.manusThreadDetail(sessionID: sessionID)
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
        if !manusThreads.contains(where: { $0.id == detail.sessionId }), let currentManusThread {
            manusThreads.insert(currentManusThread, at: 0)
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
        case "plan":
            manusPlan = planSteps(from: data)
        case "step":
            if let step = makePlanStep(from: data) {
                if let index = manusPlan.firstIndex(where: { $0.id == step.id }) {
                    manusPlan[index] = step
                } else {
                    manusPlan.append(step)
                }
            }
        case "tool":
            if let tool = makeToolEvent(from: data) {
                if let index = manusTools.firstIndex(where: { $0.id == tool.id }) {
                    manusTools[index] = tool
                } else {
                    manusTools.append(tool)
                }
            }
        case "title":
            updateCurrentManusTitle(from: data)
        case "error":
            lastError = stringField("error", in: data)
        default:
            break
        }
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

    private func arrayField(_ key: String, in object: [String: JSONValue]) -> [JSONValue]? {
        guard case .array(let value)? = object[key] else { return nil }
        return value
    }

    private func objectField(_ key: String, in object: [String: JSONValue]) -> [String: JSONValue]? {
        guard case .object(let value)? = object[key] else { return nil }
        return value
    }

    private func ensureOrchestrator() async {
        do {
            try await launcher.ensureRunning(client: client)
        } catch {
            let prefix = language == .simplifiedChinese ? "无法启动 Orchestrator" : "Could not start Orchestrator"
            lastError = "\(prefix): \(error.localizedDescription)"
        }
    }

    private func startEvents() {
        guard eventsTask == nil else { return }

        eventsTask = Task { [weak self] in
            guard let self else { return }
            do {
                try await self.client.listenForEvents {
                    await self.refresh()
                }
            } catch {
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
