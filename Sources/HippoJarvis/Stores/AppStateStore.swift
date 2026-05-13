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
    @Published private(set) var openChronicleModelConfig: OpenChronicleModelConfig = .empty
    @Published private(set) var vlmacConfig: VlmacConfig = .empty
    @Published private(set) var basicMemoryEmbeddingConfig: BasicMemoryEmbeddingConfig = .empty
    @Published private(set) var projectCortexConfig: ProjectCortexConfig = .empty
    @Published private(set) var planStatus: PlanStatus = .empty
    @Published private(set) var cuaTargetSurface: CuaTargetSurface = .empty
    @Published private(set) var aiManusConfig: AiManusConfig = .empty
    @Published private(set) var aiManusStatus: AiManusStatus = .empty
    @Published private(set) var aiManusRuntimeLastCommand: AiManusRuntimeCommandResponse?
    @Published private(set) var aiManusRuntimeLogs: AiManusRuntimeLogsResponse = .empty
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
        guard let task = snapshot.currentTask, !isBusy else { return false }
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

    func refreshPlan() async {
        isBusy = true
        defer { isBusy = false }

        do {
            planStatus = try await client.plan()
            applyPlanStatus(planStatus)
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func detectIntervention() async {
        await run(refreshTargetSurface: false) {
            try await self.client.detectIntervention()
        }
    }

    func highlight() async {
        await run {
            try await self.client.highlight()
        }
    }

    func refreshFrontmost() async {
        isBusy = true
        defer { isBusy = false }

        do {
            let frontmost = try await client.frontmost()
            snapshot.frontmostContext = frontmost
            planStatus.frontmostContext = frontmost
            lastError = nil
        } catch {
            lastError = error.localizedDescription
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

    func refreshProviderConsoles() async {
        isBusy = true
        defer { isBusy = false }

        do {
            openChronicleModelConfig = try await client.openChronicleModelConfig()
            vlmacConfig = try await client.vlmacConfig()
            applyServiceStatus(try await client.vlmacStatus())
            basicMemoryEmbeddingConfig = try await client.basicMemoryEmbeddingConfig()
            applyServiceStatus(try await client.basicMemoryStatus())
            projectCortexConfig = try await client.projectCortexConfig()
            applyServiceStatus(try await client.projectCortexStatus())
            snapshot = try await client.state()
            applyPlanFields(from: snapshot)
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func updateOpenChronicleModelConfig(
        stage: String? = nil,
        model: String? = nil,
        baseUrl: String? = nil,
        apiKeyEnv: String? = nil,
        apiKey: String? = nil,
        maxTokens: Int? = nil
    ) async {
        isBusy = true
        defer { isBusy = false }

        do {
            openChronicleModelConfig = try await client.updateOpenChronicleModelConfig(
                OpenChronicleModelConfigUpdateRequest(
                    stage: stage ?? "default",
                    model: model,
                    baseUrl: baseUrl,
                    apiKeyEnv: apiKeyEnv,
                    apiKey: apiKey,
                    maxTokens: maxTokens
                )
            )
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func updateVlmacConfig(
        serviceBaseUrl: String? = nil,
        vllmBaseUrl: String? = nil,
        vllmModel: String? = nil,
        vllmApiKey: String? = nil,
        temperature: Double? = nil,
        maxTokens: Int? = nil,
        timeoutSeconds: Double? = nil
    ) async {
        isBusy = true
        defer { isBusy = false }

        do {
            vlmacConfig = try await client.updateVlmacConfig(
                VlmacConfigUpdateRequest(
                    serviceBaseUrl: serviceBaseUrl,
                    vllmBaseUrl: vllmBaseUrl,
                    vllmModel: vllmModel,
                    vllmApiKey: vllmApiKey,
                    temperature: temperature,
                    maxTokens: maxTokens,
                    timeoutSeconds: timeoutSeconds
                )
            )
            snapshot = try await client.state()
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func updateBasicMemoryEmbeddingConfig(
        semanticSearchEnabled: Bool? = nil,
        semanticEmbeddingProvider: String? = nil,
        semanticEmbeddingModel: String? = nil,
        semanticEmbeddingBaseUrl: String? = nil,
        semanticEmbeddingApiKey: String? = nil,
        semanticEmbeddingApiKeyEnv: String? = nil,
        semanticEmbeddingDimensions: Int? = nil,
        semanticEmbeddingBatchSize: Int? = nil,
        semanticEmbeddingRequestConcurrency: Int? = nil,
        semanticEmbeddingTimeout: Double? = nil
    ) async {
        isBusy = true
        defer { isBusy = false }

        do {
            basicMemoryEmbeddingConfig = try await client.updateBasicMemoryEmbeddingConfig(
                BasicMemoryEmbeddingConfigUpdateRequest(
                    semanticSearchEnabled: semanticSearchEnabled,
                    semanticEmbeddingProvider: semanticEmbeddingProvider,
                    semanticEmbeddingModel: semanticEmbeddingModel,
                    semanticEmbeddingBaseUrl: semanticEmbeddingBaseUrl,
                    semanticEmbeddingApiKey: semanticEmbeddingApiKey,
                    semanticEmbeddingApiKeyEnv: semanticEmbeddingApiKeyEnv,
                    semanticEmbeddingDimensions: semanticEmbeddingDimensions,
                    semanticEmbeddingBatchSize: semanticEmbeddingBatchSize,
                    semanticEmbeddingRequestConcurrency: semanticEmbeddingRequestConcurrency,
                    semanticEmbeddingTimeout: semanticEmbeddingTimeout
                )
            )
            snapshot = try await client.state()
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func updateProjectCortexConfig(
        useReal: Bool? = nil,
        serviceBaseUrl: String? = nil,
        openaiBaseUrl: String? = nil,
        openaiModel: String? = nil,
        openaiApiKey: String? = nil,
        temperature: Double? = nil,
        maxTokens: Int? = nil,
        timeoutSeconds: Double? = nil
    ) async {
        isBusy = true
        defer { isBusy = false }

        do {
            projectCortexConfig = try await client.updateProjectCortexConfig(
                ProjectCortexConfigUpdateRequest(
                    useReal: useReal,
                    serviceBaseUrl: serviceBaseUrl,
                    openaiBaseUrl: openaiBaseUrl,
                    openaiModel: openaiModel,
                    openaiApiKey: openaiApiKey,
                    temperature: temperature,
                    maxTokens: maxTokens,
                    timeoutSeconds: timeoutSeconds
                )
            )
            applyServiceStatus(try await client.projectCortexStatus())
            snapshot = try await client.state()
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
        cuaTargetSurface = .empty
        await run(refreshTargetSurface: false) { try await self.client.jarvisOff() }
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

    func generateFollowUp() async {
        isBusy = true
        defer { isBusy = false }

        do {
            let package = try await client.followUp()
            snapshot.followUpPackage = package
            planStatus.followUpPackage = package
            snapshot = try await client.state()
            applyPlanFields(from: snapshot)
            await refreshEventHistory()
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func mailDraft() async {
        isBusy = true
        defer { isBusy = false }

        do {
            let result = try await client.mailDraft()
            snapshot.mailDraftInsertResult = result
            planStatus.mailDraftInsertResult = result
            snapshot = try await client.state()
            applyPlanFields(from: snapshot)
            await refreshCuaTargetSurface()
            await refreshEventHistory()
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
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

    func refreshBasicMemoryStatus() async {
        isBusy = true
        defer { isBusy = false }

        do {
            applyServiceStatus(try await client.basicMemoryStatus())
            lastError = nil
        } catch {
            lastError = error.localizedDescription
        }
    }

    func refreshVlmacStatus() async {
        isBusy = true
        defer { isBusy = false }

        do {
            applyServiceStatus(try await client.vlmacStatus())
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

    private func run(refreshTargetSurface: Bool = false, _ operation: @escaping () async throws -> AppSnapshot) async {
        isBusy = true
        defer { isBusy = false }

        do {
            let next = try await operation()
            snapshot = next
            applyPlanFields(from: next)
            skillStore.persist(next.skills)
            if refreshTargetSurface {
                await refreshCuaTargetSurface()
            } else if next.currentTask == nil {
                cuaTargetSurface = .empty
            }
            await refreshEventHistory()
            lastError = nil
        } catch {
            lastError = error.localizedDescription
            snapshot = AppSnapshot(
                jarvisState: .error,
                statusMessage: error.localizedDescription,
                currentSession: snapshot.currentSession,
                sopCapture: snapshot.sopCapture,
                highlightSegment: snapshot.highlightSegment,
                frontmostContext: snapshot.frontmostContext,
                followUpPackage: snapshot.followUpPackage,
                mailDraftInsertResult: snapshot.mailDraftInsertResult,
                workerStatuses: snapshot.workerStatuses,
                memoryContextChunks: snapshot.memoryContextChunks,
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

    private func applyAiManusRuntimeService(_ service: ServiceStatus?) {
        guard let service else { return }
        aiManusStatus = AiManusStatus(
            ok: service.status == "online",
            status: service.status,
            detail: service.detail,
            config: aiManusConfig
        )
    }

    private func applyServiceStatus(_ service: ServiceStatus) {
        if let index = snapshot.services.firstIndex(where: { $0.name.localizedCaseInsensitiveCompare(service.name) == .orderedSame }) {
            snapshot.services[index] = service
        } else {
            snapshot.services.append(service)
        }
    }

    private func applyPlanStatus(_ status: PlanStatus) {
        snapshot.highlightSegment = status.highlightSegment
        snapshot.frontmostContext = status.frontmostContext
        snapshot.followUpPackage = status.followUpPackage
        snapshot.mailDraftInsertResult = status.mailDraftInsertResult
        snapshot.workerStatuses = status.workerStatuses
        snapshot.memoryContextChunks = status.memoryContextChunks
    }

    private func applyPlanFields(from snapshot: AppSnapshot) {
        planStatus = PlanStatus(
            highlightSegment: snapshot.highlightSegment,
            frontmostContext: snapshot.frontmostContext,
            followUpPackage: snapshot.followUpPackage,
            mailDraftInsertResult: snapshot.mailDraftInsertResult,
            workerStatuses: snapshot.workerStatuses ?? [],
            memoryContextChunks: snapshot.memoryContextChunks ?? []
        )
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

    private func makeManusMessage(from value: JSONValue) -> ManusMessage? {
        guard case .object(let object) = value else { return nil }
        let content = stringField("content", in: object) ?? stringField("message", in: object)
        guard let content else { return nil }
        let eventId = stringField("event_id", in: object) ?? stringField("eventId", in: object)
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
