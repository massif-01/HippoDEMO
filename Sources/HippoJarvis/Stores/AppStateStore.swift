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

    private func refreshCuaTargetSurface() async {
        guard snapshot.currentTask != nil else {
            cuaTargetSurface = .empty
            return
        }
        if let surface = try? await client.cuaTargetSurface() {
            cuaTargetSurface = surface
        }
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
}
