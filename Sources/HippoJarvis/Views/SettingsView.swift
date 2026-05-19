import SwiftUI

struct SettingsView: View {
    @EnvironmentObject private var store: AppStateStore
    @AppStorage("orchestratorBaseURL") private var orchestratorBaseURL = "http://127.0.0.1:8787"
    @State private var asrBaseURLDraft = ""
    @State private var asrModelDraft = ""
    @State private var asrKeyDraft = ""
    @State private var summaryBaseURLDraft = ""
    @State private var summaryModelDraft = ""
    @State private var summaryKeyDraft = ""
    @State private var aiManusBaseURLDraft = ""
    @State private var aiManusFrontendURLDraft = ""
    @State private var aiManusAuthProviderDraft = ""
    @State private var aiManusTimeoutDraft = ""
    @State private var aiManusAPIBaseDraft = ""
    @State private var aiManusModelDraft = ""
    @State private var aiManusKeyDraft = ""
    @State private var aiManusTemperatureDraft = ""
    @State private var aiManusMaxTokensDraft = ""
    @State private var aiManusExtraHeadersDraft = ""
    @State private var vlmacBaseURLDraft = ""
    @State private var vlmacModelDraft = ""
    @State private var vlmacKeyDraft = ""
    @State private var basicMemorySearchDraft = ""

    private let serviceColumns = [
        GridItem(.adaptive(minimum: 210), spacing: 10, alignment: .top)
    ]

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                header
                runtimeOverview
                serviceMatrix
                ownscribeAudioConsole
                aiManusRuntimeConsole
                basicMemoryConsole
                contextMemoryConsole
                vlmacConsole
                openChronicleConsole
                cuaDriverConsole
                secondaryControls
            }
            .padding(20)
            .frame(maxWidth: 980, alignment: .topLeading)
            .frame(maxWidth: .infinity, alignment: .top)
        }
        .task {
            await store.bootstrap()
            await store.refreshOwnscribeConsole()
            await store.refreshManus()
            await store.refreshBasicMemory()
            await store.refreshContextFragments()
            await store.refreshVlmacPreflight()
            syncProviderDrafts()
            syncAiManusDrafts()
            syncVlmacDrafts()
        }
        .onChange(of: store.ownscribeConfig) {
            syncProviderDrafts()
        }
        .onChange(of: store.aiManusConfig) {
            syncAiManusDrafts()
        }
        .onChange(of: store.vlmacConfig) {
            syncVlmacDrafts()
        }
    }

    private var header: some View {
        HStack(alignment: .center, spacing: 14) {
            StatusPulse(color: accentColor, systemImage: "switch.2", isActive: store.snapshot.jarvisState != .idle)

            VStack(alignment: .leading, spacing: 6) {
                Text(store.text(.developerConsole))
                    .font(.system(size: 24, weight: .semibold, design: .rounded))
                Text(store.statusMessage)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }

            Spacer(minLength: 0)

            JarvisActionButton(title: store.text(.refreshState), systemImage: "arrow.clockwise", tone: .quiet) {
                Task { await store.refresh() }
            }
            .frame(width: 170)
            .disabled(store.isBusy)
        }
    }

    private var runtimeOverview: some View {
        HUDSection(store.text(.runtime), systemImage: "server.rack") {
            VStack(alignment: .leading, spacing: 12) {
                HStack(alignment: .firstTextBaseline, spacing: 10) {
                    TextField(store.text(.baseURL), text: $orchestratorBaseURL)
                        .textFieldStyle(.roundedBorder)
                        .font(.system(.body, design: .monospaced))
                    statusBadge(store.snapshot.jarvisState.rawValue, title: store.shortStateLabel(store.snapshot.jarvisState))
                }

                LazyVGrid(columns: [
                    GridItem(.flexible(), spacing: 10),
                    GridItem(.flexible(), spacing: 10),
                    GridItem(.flexible(), spacing: 10)
                ], spacing: 10) {
                    SignalMetric(title: store.text(.baseURL), value: orchestratorBaseURL, systemImage: "network", color: .blue)
                    SignalMetric(title: store.text(.state), value: store.stateName(store.snapshot.jarvisState), systemImage: store.menuBarSystemImage, color: accentColor)
                    SignalMetric(title: store.text(.services), value: "\(store.snapshot.services.count)", systemImage: "switch.2", color: .green)
                }
            }
        }
    }

    private var serviceMatrix: some View {
        HUDSection(store.text(.serviceMatrix), systemImage: "point.3.connected.trianglepath.dotted") {
            LazyVGrid(columns: serviceColumns, spacing: 10) {
                ForEach(store.snapshot.services) { service in
                    VStack(alignment: .leading, spacing: 8) {
                        HStack(spacing: 8) {
                            ServiceLight(
                                service: service,
                                title: service.name,
                                detail: store.serviceDetail(service.detail, status: service.status),
                                compact: true
                            )
                            Spacer(minLength: 0)
                            statusBadge(service.status, title: store.serviceStatus(service.status))
                        }

                        Text(store.serviceDetail(service.detail, status: service.status))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                            .lineLimit(2)
                    }
                    .padding(10)
                    .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
                    .overlay {
                        RoundedRectangle(cornerRadius: 10, style: .continuous)
                            .strokeBorder(StatusVisuals.serviceColor(service.status).opacity(0.18), lineWidth: 0.7)
                    }
                }
            }
        }
    }

    private var ownscribeAudioConsole: some View {
        HUDSection(store.text(.audioCapture), systemImage: "waveform.and.mic") {
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 10) {
                    if let ownscribeService {
                        ServiceLight(
                            service: ownscribeService,
                            title: "ownscribe",
                            detail: store.serviceDetail(ownscribeService.detail, status: ownscribeService.status)
                        )
                    } else {
                        Text(store.text(.notReported))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    Spacer(minLength: 0)

                    statusBadge(ownscribeService?.status ?? "unknown", title: ownscribeService.map { store.serviceStatus($0.status) })
                }

                Divider()

                VStack(alignment: .leading, spacing: 10) {
                    Text(store.text(.audioSource))
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundStyle(.secondary)

                    Picker(store.text(.audioSource), selection: Binding(
                        get: { store.ownscribeConfig.audioSource },
                        set: { nextSource in
                            Task { await store.updateOwnscribeConfig(audioSource: nextSource) }
                        }
                    )) {
                        ForEach(OwnscribeAudioSource.allCases) { source in
                            Text(audioSourceLabel(source))
                                .tag(source)
                        }
                    }
                    .pickerStyle(.segmented)
                    .disabled(store.isBusy)
                }

                HStack(alignment: .top, spacing: 12) {
                    VStack(alignment: .leading, spacing: 8) {
                        Text(store.text(.selectedMicrophone))
                            .font(.caption)
                            .fontWeight(.medium)
                            .foregroundStyle(.secondary)

                        Picker(store.text(.selectedMicrophone), selection: Binding(
                            get: { store.ownscribeConfig.micDevice ?? "" },
                            set: { nextDevice in
                                Task { await store.updateOwnscribeConfig(micDevice: nextDevice) }
                            }
                        )) {
                            Text(store.text(.notReported))
                                .tag("")
                            ForEach(store.ownscribeDevices.devices) { device in
                                Text(device.isDefault ? "\(device.name) • default" : device.name)
                                    .tag(device.name)
                            }
                        }
                        .disabled(store.isBusy || store.ownscribeConfig.audioSource == .system)
                    }

                    VStack(alignment: .leading, spacing: 8) {
                        Text(store.text(.preflight))
                            .font(.caption)
                            .fontWeight(.medium)
                            .foregroundStyle(.secondary)

                        HStack(spacing: 8) {
                            commandButton(store.text(.refresh), icon: "arrow.clockwise", tone: .quiet) {
                                await store.refreshOwnscribeConsole()
                            }
                            commandButton(store.text(.runPreflight), icon: "checkmark.seal", tone: .primary) {
                                await store.refreshOwnscribeConsole(networkPreflight: true)
                            }
                        }
                    }
                }

                providerControls

                if !store.ownscribePreflight.checks.isEmpty {
                    LazyVGrid(columns: [
                        GridItem(.flexible(), spacing: 8),
                        GridItem(.flexible(), spacing: 8)
                    ], spacing: 8) {
                        ForEach(store.ownscribePreflight.checks) { check in
                            preflightRow(check)
                        }
                    }
                }
            }
        }
    }

    private var providerControls: some View {
        VStack(alignment: .leading, spacing: 10) {
            Divider()

            HStack(spacing: 8) {
                Text(store.text(.runtimeProvider))
                    .font(.caption)
                    .fontWeight(.medium)
                    .foregroundStyle(.secondary)
                Spacer(minLength: 0)
                statusBadge(
                    store.ownscribeConfig.asrApiKeyConfigured == true ? "available" : "stopped",
                    title: store.ownscribeConfig.asrApiKeyConfigured == true ? store.text(.apiKeyConfigured) : store.text(.apiKeyMissing)
                )
                statusBadge(
                    store.ownscribeConfig.summaryApiKeyConfigured == true ? "available" : "stopped",
                    title: store.ownscribeConfig.summaryApiKeyConfigured == true ? store.text(.summaryConfigured) : store.text(.summaryMissing)
                )
            }

            LazyVGrid(columns: [
                GridItem(.flexible(), spacing: 10),
                GridItem(.flexible(), spacing: 10)
            ], spacing: 10) {
                providerField(store.text(.asrBaseURL), text: $asrBaseURLDraft)
                providerField(store.text(.asrModel), text: $asrModelDraft)
                providerSecureField(store.text(.asrApiKey), text: $asrKeyDraft)
                providerField(store.text(.summaryBaseURL), text: $summaryBaseURLDraft)
                providerField(store.text(.summaryModel), text: $summaryModelDraft)
                providerSecureField(store.text(.summaryApiKey), text: $summaryKeyDraft)
            }

            HStack(spacing: 8) {
                commandButton(store.text(.saveProvider), icon: "square.and.arrow.down", tone: .primary) {
                    await saveProviderConfig()
                }
                Text(store.text(.keyStoredLocally))
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
        }
    }

    private var vlmacProviderControls: some View {
        VStack(alignment: .leading, spacing: 10) {
            HStack(spacing: 8) {
                Text("VLM OpenAI API")
                    .font(.caption)
                    .fontWeight(.medium)
                    .foregroundStyle(.secondary)
                Spacer(minLength: 0)
                statusBadge(
                    store.vlmacConfig.vlmApiKeyConfigured == true ? "available" : "stopped",
                    title: store.vlmacConfig.vlmApiKeyConfigured == true ? "API key saved" : "local or no-key"
                )
            }

            LazyVGrid(columns: [
                GridItem(.flexible(), spacing: 10),
                GridItem(.flexible(), spacing: 10)
            ], spacing: 10) {
                providerField("OpenAI-compatible Base URL", text: $vlmacBaseURLDraft)
                providerField("MODEL_NAME", text: $vlmacModelDraft)
                providerSecureField("API Key", text: $vlmacKeyDraft)
            }

            HStack(spacing: 8) {
                commandButton("Save VLM API", icon: "square.and.arrow.down", tone: .primary) {
                    await saveVlmacConfig()
                }
                Text("Use the /v1 base URL. Restart applies changes to a running vlmac service.")
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
            .disabled(store.isBusy)
        }
    }

    private var aiManusRuntimeConsole: some View {
        HUDSection("ai-manus Runtime", systemImage: "cpu") {
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 10) {
                    if let aiManusService {
                        ServiceLight(
                            service: aiManusService,
                            title: "ai-manus",
                            detail: store.serviceDetail(aiManusService.detail, status: aiManusService.status)
                        )
                    } else {
                        Text(store.text(.notReported))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    Spacer(minLength: 0)

                    statusBadge(store.aiManusStatus.status, title: store.serviceStatus(store.aiManusStatus.status))
                    if store.aiManusConfig.restartRequired == true {
                        statusBadge("mock", title: "restart required")
                    }
                }

                Divider()

                LazyVGrid(columns: [
                    GridItem(.flexible(), spacing: 10),
                    GridItem(.flexible(), spacing: 10)
                ], spacing: 10) {
                    providerField("Hippo base_url", text: $aiManusBaseURLDraft)
                    providerField("Frontend URL", text: $aiManusFrontendURLDraft)
                    providerField("AUTH_PROVIDER", text: $aiManusAuthProviderDraft)
                    providerField("Timeout seconds", text: $aiManusTimeoutDraft)
                    providerField("API_BASE", text: $aiManusAPIBaseDraft)
                    providerField("MODEL_NAME", text: $aiManusModelDraft)
                    providerSecureField("API_KEY", text: $aiManusKeyDraft)
                    providerField("TEMPERATURE", text: $aiManusTemperatureDraft)
                    providerField("MAX_TOKENS", text: $aiManusMaxTokensDraft)
                }

                providerField("EXTRA_HEADERS", text: $aiManusExtraHeadersDraft)

                VStack(alignment: .leading, spacing: 8) {
                    HStack(spacing: 8) {
                        commandButton("Start ai-manus", icon: "play.fill", tone: .primary) {
                            await store.aiManusRuntimeStart()
                            syncAiManusDrafts()
                        }
                        .disabled(store.isRunningAiManusRuntimeCommand)

                        commandButton("Restart", icon: "arrow.triangle.2.circlepath", tone: .amber) {
                            await store.aiManusRuntimeRestart()
                            syncAiManusDrafts()
                        }
                        .disabled(store.isRunningAiManusRuntimeCommand)

                        commandButton("Stop", icon: "stop.fill", tone: .destructive) {
                            await store.aiManusRuntimeStop()
                            syncAiManusDrafts()
                        }
                        .disabled(store.isRunningAiManusRuntimeCommand)

                        commandButton("Logs", icon: "terminal", tone: .quiet) {
                            await store.refreshAiManusRuntimeLogs()
                        }
                        .disabled(store.isRunningAiManusRuntimeCommand)
                    }

                    if let commandDetail = aiManusRuntimeCommandDetail {
                        Text(commandDetail)
                            .font(.caption2)
                            .foregroundStyle(.secondary)
                            .lineLimit(2)
                    }

                    if !aiManusRuntimeLogLines.isEmpty {
                        VStack(alignment: .leading, spacing: 3) {
                            ForEach(Array(aiManusRuntimeLogLines.enumerated()), id: \.offset) { _, line in
                                Text(line)
                                    .font(.system(size: 10, design: .monospaced))
                                    .foregroundStyle(.secondary)
                                    .lineLimit(1)
                            }
                        }
                        .padding(8)
                        .frame(maxWidth: .infinity, alignment: .leading)
                        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
                    }
                }

                HStack(spacing: 8) {
                    commandButton("Save ai-manus", icon: "square.and.arrow.down", tone: .primary) {
                        await saveAiManusConfig()
                    }
                    commandButton(store.text(.refresh), icon: "arrow.clockwise", tone: .quiet) {
                        await store.refreshManus()
                        syncAiManusDrafts()
                    }
                    Text(aiManusRuntimeDetail)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }
            }
        }
    }

    private var basicMemoryConsole: some View {
        HUDSection("basic-memory", systemImage: "brain.head.profile") {
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 10) {
                    if let basicMemoryService {
                        ServiceLight(
                            service: basicMemoryService,
                            title: "basic-memory",
                            detail: store.serviceDetail(basicMemoryService.detail, status: basicMemoryService.status)
                        )
                    } else {
                        Text(store.text(.notReported))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    Spacer(minLength: 0)

                    statusBadge(store.basicMemoryStatus.status, title: store.serviceStatus(store.basicMemoryStatus.status))
                    if store.basicMemoryConfig.toolsAvailable == true {
                        statusBadge("available", title: store.basicMemoryConfig.runtimeKind ?? "runtime")
                    }
                }

                Divider()

                LazyVGrid(columns: [
                    GridItem(.flexible(), spacing: 10),
                    GridItem(.flexible(), spacing: 10)
                ], spacing: 10) {
                    SignalMetric(
                        title: "Project",
                        value: store.basicMemoryStatus.project ?? store.basicMemoryConfig.project ?? "not configured",
                        systemImage: "folder",
                        color: .blue
                    )
                    SignalMetric(
                        title: "Project Dir",
                        value: store.basicMemoryStatus.projectPath ?? store.basicMemoryConfig.projectPath ?? "not setup",
                        systemImage: "folder.badge.gearshape",
                        color: .green
                    )
                    SignalMetric(
                        title: "Config Dir",
                        value: store.basicMemoryConfig.configPath ?? "not reported",
                        systemImage: "gearshape",
                        color: .orange
                    )
                    SignalMetric(
                        title: "Runtime",
                        value: basicMemoryRuntimeLabel,
                        systemImage: "terminal",
                        color: .purple
                    )
                    SignalMetric(
                        title: "Sync",
                        value: store.basicMemoryStatus.syncStatus ?? store.basicMemoryLastSync?.status ?? "unknown",
                        systemImage: "arrow.triangle.2.circlepath",
                        color: .blue
                    )
                }

                HStack(spacing: 8) {
                    commandButton("Setup", icon: "wrench.and.screwdriver", tone: .primary) {
                        await store.setupBasicMemory()
                    }
                    .disabled(store.isRunningBasicMemoryCommand)

                    commandButton(store.text(.refresh), icon: "arrow.clockwise", tone: .quiet) {
                        await store.refreshBasicMemory()
                    }
                    .disabled(store.isRunningBasicMemoryCommand)

                    commandButton("Recent", icon: "clock", tone: .quiet) {
                        await store.loadBasicMemoryRecent()
                    }
                    .disabled(store.isRunningBasicMemoryCommand)
                }

                HStack(alignment: .bottom, spacing: 8) {
                    providerField("Search notes", text: $basicMemorySearchDraft)
                    commandButton("Search", icon: "magnifyingglass", tone: .primary) {
                        await store.searchBasicMemory(basicMemorySearchDraft)
                    }
                    .frame(width: 130)
                    .disabled(store.isRunningBasicMemoryCommand || basicMemorySearchDraft.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty)
                }

                HStack(spacing: 8) {
                    commandButton("Sync Session", icon: "rectangle.stack.badge.plus", tone: .quiet) {
                        await store.syncCurrentSessionToBasicMemory()
                    }
                    commandButton("Sync Task", icon: "checklist", tone: .quiet) {
                        await store.syncCurrentTaskToBasicMemory()
                    }
                    commandButton("Sync Skill", icon: "sparkles", tone: .quiet) {
                        await store.syncLatestSkillToBasicMemory()
                    }
                }
                .disabled(store.isRunningBasicMemoryCommand)

                if let detail = basicMemorySyncDetail {
                    Text(detail)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }

                LazyVGrid(columns: [
                    GridItem(.flexible(), spacing: 10),
                    GridItem(.flexible(), spacing: 10)
                ], spacing: 10) {
                    basicMemoryList(title: "Search", results: store.basicMemorySearch.results)
                    basicMemoryRecentList
                }

                if let note = store.basicMemoryNotePreview {
                    VStack(alignment: .leading, spacing: 8) {
                        HStack(spacing: 8) {
                            Image(systemName: "doc.text.magnifyingglass")
                                .foregroundStyle(.secondary)
                            Text(note.title ?? note.path ?? "Note preview")
                                .font(.caption)
                                .fontWeight(.medium)
                                .lineLimit(1)
                            Spacer(minLength: 0)
                            if let path = note.path {
                                Text(path)
                                    .font(.caption2)
                                    .foregroundStyle(.secondary)
                                    .lineLimit(1)
                            }
                        }
                        Text(note.content ?? note.summary ?? "No preview content.")
                            .font(.system(size: 11, design: .monospaced))
                            .foregroundStyle(.secondary)
                            .lineLimit(10)
                            .textSelection(.enabled)
                    }
                    .padding(10)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
                }

                if let detail = store.basicMemoryStatus.detail ?? store.basicMemoryConfig.detail {
                    Text(detail)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }

                if let runtimeDetail = basicMemoryRuntimeDetail {
                    Text(runtimeDetail)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }
            }
        }
    }

    private var contextMemoryConsole: some View {
        HUDSection("Context Memory", systemImage: "text.bubble") {
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 10) {
                    if let service = voiceProducerService {
                        ServiceLight(
                            service: service,
                            title: "voice producer",
                            detail: store.serviceDetail(service.detail, status: service.status)
                        )
                    } else {
                        ServiceLight(
                            service: ServiceStatus(id: "voice-context", name: "voice producer", status: "idle", detail: "No voice context producer reported"),
                            title: "voice producer",
                            detail: "No voice context producer reported"
                        )
                    }

                    Spacer(minLength: 0)

                    statusBadge(voiceProducerService?.status ?? "idle", title: voiceProducerService.map { store.serviceStatus($0.status) })
                }

                Divider()

                LazyVGrid(columns: [
                    GridItem(.flexible(), spacing: 10),
                    GridItem(.flexible(), spacing: 10),
                    GridItem(.flexible(), spacing: 10)
                ], spacing: 10) {
                    SignalMetric(
                        title: "Latest",
                        value: formattedContextTimestamp(latestContextFragment?.endedAt ?? latestContextFragment?.startedAt),
                        systemImage: "clock",
                        color: .cyan
                    )
                    SignalMetric(
                        title: "Pending",
                        value: "\(pendingContextCount)",
                        systemImage: "tray",
                        color: .orange
                    )
                    SignalMetric(
                        title: "Synced",
                        value: "\(syncedContextCount)",
                        systemImage: "checkmark.icloud",
                        color: .green
                    )
                }

                HStack(spacing: 8) {
                    commandButton(store.text(.refresh), icon: "arrow.clockwise", tone: .quiet) {
                        await store.refreshContextFragments()
                    }
                    .disabled(store.isRunningBasicMemoryCommand)

                    commandButton("Sync Recent", icon: "arrow.triangle.2.circlepath", tone: .primary) {
                        await store.syncLatestContextFragmentToBasicMemory()
                    }
                    .disabled(store.isRunningBasicMemoryCommand || latestContextFragment == nil)

                    Text(contextMemoryDetail)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }

                if let detail = contextMemorySyncDetail {
                    Text(detail)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }
            }
        }
    }

    private var vlmacConsole: some View {
        HUDSection("vlmac", systemImage: "eye.fill") {
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 10) {
                    if let vlmacService {
                        ServiceLight(
                            service: vlmacService,
                            title: "vlmac",
                            detail: store.serviceDetail(vlmacService.detail, status: vlmacService.status)
                        )
                    } else {
                        Text(store.text(.notReported))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    Spacer(minLength: 0)

                    statusBadge(vlmacService?.status ?? "unknown", title: vlmacService.map { store.serviceStatus($0.status) })
                }

                Divider()

                vlmacProviderControls

                LazyVGrid(columns: [
                    GridItem(.flexible(), spacing: 10),
                    GridItem(.flexible(), spacing: 10)
                ], spacing: 10) {
                    SignalMetric(
                        title: "Storage",
                        value: vlmacStorageDetail,
                        systemImage: "externaldrive",
                        color: .green
                    )
                    SignalMetric(
                        title: "VLM API",
                        value: vlmacVLMDetail,
                        systemImage: "network",
                        color: .purple
                    )
                    SignalMetric(
                        title: "Preflight",
                        value: store.vlmacPreflight?.compactDescription ?? "not checked",
                        systemImage: "checkmark.seal",
                        color: .blue
                    )
                }

                HStack(spacing: 8) {
                    commandButton(store.text(.start), icon: "play.fill", tone: .primary) {
                        await store.vlmacStart()
                    }
                    commandButton(store.text(.restart), icon: "arrow.clockwise", tone: .amber) {
                        await store.vlmacRestart()
                    }
                    commandButton(store.text(.stop), icon: "stop.fill", tone: .destructive) {
                        await store.vlmacStop()
                    }
                    commandButton("Preflight", icon: "checkmark.seal", tone: .quiet) {
                        await store.refreshVlmacPreflight(network: true)
                    }
                    Link(destination: URL(string: "http://127.0.0.1:59092")!) {
                        Label("Open WebUI", systemImage: "safari")
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                }
                .disabled(store.isBusy)

                if let detail = vlmacService?.detail {
                    Text(detail)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }
            }
        }
    }

    private var openChronicleConsole: some View {
        HUDSection(store.text(.openChronicleControls), systemImage: "record.circle") {
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 10) {
                    if let openChronicleService {
                        ServiceLight(
                            service: openChronicleService,
                            title: store.text(.service),
                            detail: store.serviceDetail(openChronicleService.detail, status: openChronicleService.status)
                        )
                    } else {
                        Text(store.text(.notReported))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    Spacer(minLength: 0)

                    statusBadge(openChronicleService?.status ?? "unknown", title: openChronicleService.map { store.serviceStatus($0.status) })
                }

                Divider()

                LazyVGrid(columns: [
                    GridItem(.flexible(), spacing: 10),
                    GridItem(.flexible(), spacing: 10),
                    GridItem(.flexible(), spacing: 10),
                    GridItem(.flexible(), spacing: 10)
                ], spacing: 10) {
                    commandButton(store.text(.start), icon: "play.fill", tone: .primary) { await store.openChronicleStart() }
                    commandButton(store.text(.stop), icon: "stop.fill", tone: .destructive) { await store.openChronicleStop() }
                    commandButton(store.text(.pause), icon: "pause.fill", tone: .quiet) { await store.openChroniclePause() }
                    commandButton(store.text(.resume), icon: "playpause.fill", tone: .quiet) { await store.openChronicleResume() }
                    commandButton(store.text(.captureOnce), icon: "camera.viewfinder", tone: .quiet) { await store.openChronicleCaptureOnce() }
                    commandButton(store.text(.timelineTick), icon: "clock.arrow.circlepath", tone: .quiet) { await store.openChronicleTimelineTick() }
                    commandButton(store.text(.rebuildCapturesIndex), icon: "arrow.triangle.2.circlepath", tone: .amber) { await store.openChronicleRebuildCapturesIndex() }
                }
            }
        }
    }

    private var cuaDriverConsole: some View {
        HUDSection(store.text(.cuaDriverControls), systemImage: "cursorarrow.click.2") {
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 10) {
                    if let cuaDriverService {
                        ServiceLight(
                            service: cuaDriverService,
                            title: store.text(.service),
                            detail: store.serviceDetail(cuaDriverService.detail, status: cuaDriverService.status)
                        )
                    } else {
                        Text(store.text(.notReported))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    Spacer(minLength: 0)

                    statusBadge(cuaDriverService?.status ?? "unknown", title: cuaDriverService.map { store.serviceStatus($0.status) })
                }

                Divider()

                LazyVGrid(columns: [
                    GridItem(.flexible(), spacing: 10),
                    GridItem(.flexible(), spacing: 10),
                    GridItem(.flexible(), spacing: 10)
                ], spacing: 10) {
                    commandButton(store.text(.start), icon: "play.fill", tone: .primary) { await store.cuaDriverStart() }
                    commandButton(store.text(.stop), icon: "stop.fill", tone: .destructive) { await store.cuaDriverStop() }
                    commandButton(store.text(.restart), icon: "arrow.clockwise", tone: .amber) { await store.cuaDriverRestart() }
                }
            }
        }
    }

    private var secondaryControls: some View {
        LazyVGrid(columns: [
            GridItem(.flexible(), spacing: 12),
            GridItem(.flexible(), spacing: 12)
        ], spacing: 12) {
            HUDSection(store.text(.language), systemImage: "globe") {
                Picker(store.text(.language), selection: Binding(
                    get: { store.language },
                    set: { store.setLanguage($0) }
                )) {
                    ForEach(AppLanguage.allCases) { language in
                        Text(language.displayName)
                            .tag(language)
                    }
                }
                .pickerStyle(.segmented)
            }

            HUDSection(store.text(.permissions), systemImage: "lock.shield") {
                VStack(alignment: .leading, spacing: 8) {
                    permissionRow(store.text(.microphone), icon: "mic", detail: AppCopy.permissionDetail(.microphone, language: store.language))
                    permissionRow(store.text(.screenRecording), icon: "rectangle.inset.filled", detail: AppCopy.permissionDetail(.screenRecording, language: store.language))
                    permissionRow(store.text(.accessibility), icon: "figure.wave", detail: AppCopy.permissionDetail(.accessibility, language: store.language))
                }
            }
        }
    }

    private var openChronicleService: ServiceStatus? {
        store.snapshot.services.first { $0.name == "OpenChronicle" }
    }

    private var cuaDriverService: ServiceStatus? {
        store.snapshot.services.first { $0.name.lowercased() == "cua-driver" }
    }

    private var ownscribeService: ServiceStatus? {
        store.snapshot.services.first { $0.name.lowercased() == "ownscribe" }
    }

    private var vlmacService: ServiceStatus? {
        store.snapshot.services.first { $0.name.lowercased() == "vlmac" }
    }

    private var aiManusService: ServiceStatus? {
        store.snapshot.services.first { $0.name.lowercased() == "ai-manus" }
    }

    private var basicMemoryService: ServiceStatus? {
        store.snapshot.services.first { $0.name.lowercased() == "basic-memory" }
    }

    private var voiceProducerService: ServiceStatus? {
        store.snapshot.services.first { service in
            let name = service.name.lowercased()
            return name == "ownscribe_context_worker"
                || name == "ownscribe-context-worker"
                || name == "voice-context"
                || name == "voice context"
        } ?? ownscribeService
    }

    private var aiManusRuntimeDetail: String {
        let env = store.aiManusConfig.envPath ?? "ai-manus/.env"
        let source = store.aiManusConfig.envExists == true ? "env" : (store.aiManusConfig.envSource ?? "missing")
        let restart = store.aiManusConfig.restartRequired == true ? " · restart ai-manus backend to apply" : ""
        return "\(env) · \(source)\(restart)"
    }

    private var aiManusRuntimeCommandDetail: String? {
        guard let command = store.aiManusRuntimeLastCommand else { return nil }
        let action = command.action ?? "runtime"
        let status = command.status ?? "unknown"
        let pid = command.pid.map { " · pid \($0)" } ?? ""
        let logPath = command.logPath.map { " · log \($0)" } ?? ""
        return "\(action) \(status)\(pid)\(logPath)"
    }

    private var aiManusRuntimeLogLines: [String] {
        let lines = store.aiManusRuntimeLogs.lines
        if lines.count <= 6 { return lines }
        return Array(lines.suffix(6))
    }

    private var basicMemorySyncDetail: String? {
        guard let sync = store.basicMemoryLastSync else { return nil }
        let status = sync.status ?? (sync.ok == true ? "synced" : "unknown")
        let path = sync.path ?? sync.note?.path ?? sync.permalink ?? sync.note?.permalink
        if let path {
            return "\(status) · \(path)"
        }
        return sync.detail ?? status
    }

    private var vlmacStorageDetail: String {
        if let detail = vlmacService?.detail, let range = detail.range(of: "storage=") {
            return String(detail[range.upperBound...]).trimmingCharacters(in: .whitespaces)
        }
        return store.basicMemoryStatus.projectPath ?? store.basicMemoryConfig.projectPath ?? "not configured"
    }

    private var vlmacVLMDetail: String {
        store.vlmacConfig.vlmBaseUrl ?? "not configured"
    }

    private var basicMemoryRuntimeLabel: String {
        store.basicMemoryConfig.runtimeKind ?? store.basicMemoryConfig.status ?? "missing"
    }

    private var basicMemoryRuntimeDetail: String? {
        let path = store.basicMemoryConfig.runtimePath
            ?? store.basicMemoryConfig.bundledRuntimePath
            ?? store.basicMemoryConfig.devRuntimePath
        guard let path else { return nil }
        if let command = store.basicMemoryConfig.commandDescription {
            return "\(path) · \(command)"
        }
        return path
    }

    private var basicMemoryRecentList: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Recent")
                .font(.caption)
                .fontWeight(.medium)
                .foregroundStyle(.secondary)

            if store.basicMemoryRecent.resolvedNotes.isEmpty {
                basicMemoryEmptyRow("No recent notes.")
            } else {
                ForEach(store.basicMemoryRecent.resolvedNotes) { note in
                    Button {
                        Task { await store.loadBasicMemoryNotePreview(note) }
                    } label: {
                        basicMemoryNoteLabel(
                            title: note.title ?? note.path ?? "Untitled note",
                            subtitle: note.updatedAt ?? note.createdAt ?? note.summary ?? ""
                        )
                    }
                    .buttonStyle(HippoPressFeedbackButtonStyle(cornerRadius: 8, pressedScale: 0.985, overlayOpacity: 0.10))
                }
            }
        }
    }

    private var latestContextFragment: ContextFragment? {
        store.contextFragments.first
    }

    private var pendingContextCount: Int {
        store.contextFragments.filter { $0.syncedAt == nil }.count
    }

    private var syncedContextCount: Int {
        store.contextFragments.filter { $0.syncedAt != nil }.count
    }

    private var contextMemoryDetail: String {
        guard let fragment = latestContextFragment else {
            return "No recent voice context."
        }
        let source = fragment.source ?? "voice"
        let confidence = fragment.confidence.map { " · \(Int($0 * 100))%" } ?? ""
        return "\(source)\(confidence) · \(fragment.syncedAt == nil ? "pending" : "synced")"
    }

    private var contextMemorySyncDetail: String? {
        guard let sync = store.basicMemoryLastSync, sync.fragmentId != nil else { return nil }
        let status = sync.status ?? (sync.ok == true ? "synced" : "unknown")
        if let path = sync.path ?? sync.note?.path ?? sync.permalink ?? sync.note?.permalink {
            return "\(status) · \(path)"
        }
        return sync.detail ?? status
    }

    private func audioSourceLabel(_ source: OwnscribeAudioSource) -> String {
        switch source {
        case .system:
            store.text(.systemAudio)
        case .mic:
            store.text(.micOnly)
        case .both:
            store.text(.systemAndMic)
        }
    }

    private func preflightRow(_ check: OwnscribePreflightCheck) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: check.ok ? "checkmark.circle.fill" : "exclamationmark.triangle.fill")
                .foregroundStyle(check.ok ? .green : .orange)
                .frame(width: 16)
            VStack(alignment: .leading, spacing: 2) {
                Text(check.name.replacingOccurrences(of: "_", with: " ").capitalized)
                    .font(.caption)
                    .fontWeight(.medium)
                    .lineLimit(1)
                Text(check.detail)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }
            Spacer(minLength: 0)
        }
        .padding(8)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
    }

    private func basicMemoryList(title: String, results: [BasicMemorySearchResult]) -> some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(title)
                .font(.caption)
                .fontWeight(.medium)
                .foregroundStyle(.secondary)

            if results.isEmpty {
                basicMemoryEmptyRow("No search results.")
            } else {
                ForEach(results) { result in
                    Button {
                        Task { await store.loadBasicMemoryNotePreview(result) }
                    } label: {
                        basicMemoryNoteLabel(
                            title: result.title ?? result.path ?? "Untitled result",
                            subtitle: result.snippet ?? result.type ?? result.permalink ?? ""
                        )
                    }
                    .buttonStyle(HippoPressFeedbackButtonStyle(cornerRadius: 8, pressedScale: 0.985, overlayOpacity: 0.10))
                }
            }
        }
    }

    private func basicMemoryNoteLabel(title: String, subtitle: String) -> some View {
        HStack(alignment: .top, spacing: 8) {
            Image(systemName: "doc.text")
                .foregroundStyle(.secondary)
                .frame(width: 16)
            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(.caption)
                    .fontWeight(.medium)
                    .lineLimit(1)
                if !subtitle.isEmpty {
                    Text(subtitle)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }
            }
            Spacer(minLength: 0)
        }
        .padding(8)
        .frame(maxWidth: .infinity, alignment: .leading)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
    }

    private func basicMemoryEmptyRow(_ title: String) -> some View {
        Text(title)
            .font(.caption2)
            .foregroundStyle(.secondary)
            .padding(8)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 8, style: .continuous))
    }

    private func formattedContextTimestamp(_ value: String?) -> String {
        guard let value, let date = ISO8601DateFormatter().date(from: value) else {
            return store.text(.notReported)
        }
        return date.formatted(date: .omitted, time: .shortened)
    }

    private func providerField(_ title: String, text: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(title)
                .font(.caption2)
                .foregroundStyle(.secondary)
            TextField(title, text: text)
                .textFieldStyle(.roundedBorder)
                .font(.system(.caption, design: .monospaced))
        }
    }

    private func providerSecureField(_ title: String, text: Binding<String>) -> some View {
        VStack(alignment: .leading, spacing: 5) {
            Text(title)
                .font(.caption2)
                .foregroundStyle(.secondary)
            SecureField(title, text: text)
                .textFieldStyle(.roundedBorder)
                .font(.system(.caption, design: .monospaced))
        }
    }

    private func saveProviderConfig() async {
        await store.updateOwnscribeConfig(
            asrProvider: "openai-compatible",
            asrBaseUrl: nonEmpty(asrBaseURLDraft),
            asrModel: nonEmpty(asrModelDraft),
            asrApiKey: nonEmpty(asrKeyDraft),
            summaryProvider: "openai-compatible",
            summaryBaseUrl: nonEmpty(summaryBaseURLDraft),
            summaryModel: nonEmpty(summaryModelDraft),
            summaryApiKey: nonEmpty(summaryKeyDraft)
        )
        syncProviderDrafts()
    }

    private func syncProviderDrafts() {
        asrBaseURLDraft = store.ownscribeConfig.asrBaseUrl ?? ""
        asrModelDraft = store.ownscribeConfig.asrModel ?? ""
        summaryBaseURLDraft = store.ownscribeConfig.summaryBaseUrl ?? ""
        summaryModelDraft = store.ownscribeConfig.summaryModel ?? ""
    }

    private func saveVlmacConfig() async {
        await store.updateVlmacConfig(
            vlmBaseUrl: nonEmpty(vlmacBaseURLDraft),
            vlmModel: nonEmpty(vlmacModelDraft),
            vlmApiKey: nonEmpty(vlmacKeyDraft)
        )
        syncVlmacDrafts()
    }

    private func syncVlmacDrafts() {
        vlmacBaseURLDraft = store.vlmacConfig.vlmBaseUrl ?? ""
        vlmacModelDraft = store.vlmacConfig.vlmModel ?? ""
    }

    private func saveAiManusConfig() async {
        await store.updateAiManusConfig(
            baseUrl: nonEmpty(aiManusBaseURLDraft),
            frontendUrl: nonEmpty(aiManusFrontendURLDraft),
            authProvider: nonEmpty(aiManusAuthProviderDraft),
            timeoutSeconds: doubleValue(aiManusTimeoutDraft),
            apiBase: nonEmpty(aiManusAPIBaseDraft),
            modelName: nonEmpty(aiManusModelDraft),
            apiKey: nonEmpty(aiManusKeyDraft),
            temperature: doubleValue(aiManusTemperatureDraft),
            maxTokens: intValue(aiManusMaxTokensDraft),
            extraHeaders: nonEmpty(aiManusExtraHeadersDraft)
        )
        syncAiManusDrafts()
    }

    private func syncAiManusDrafts() {
        aiManusBaseURLDraft = store.aiManusConfig.baseUrl ?? ""
        aiManusFrontendURLDraft = store.aiManusConfig.frontendUrl ?? ""
        aiManusAuthProviderDraft = store.aiManusConfig.authProvider ?? "none"
        aiManusTimeoutDraft = store.aiManusConfig.timeoutSeconds.map { formatNumber($0) } ?? ""
        aiManusAPIBaseDraft = store.aiManusConfig.apiBase ?? ""
        aiManusModelDraft = store.aiManusConfig.modelName ?? ""
        aiManusTemperatureDraft = store.aiManusConfig.temperature.map { formatNumber($0) } ?? ""
        aiManusMaxTokensDraft = store.aiManusConfig.maxTokens.map(String.init) ?? ""
        aiManusExtraHeadersDraft = store.aiManusConfig.extraHeaders ?? ""
    }

    private func nonEmpty(_ value: String) -> String? {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
    }

    private func doubleValue(_ value: String) -> Double? {
        guard let text = nonEmpty(value) else { return nil }
        return Double(text)
    }

    private func intValue(_ value: String) -> Int? {
        guard let text = nonEmpty(value) else { return nil }
        return Int(text)
    }

    private func formatNumber(_ value: Double) -> String {
        value.rounded() == value ? String(Int(value)) : String(value)
    }

    private func commandButton(_ title: String, icon: String, tone: JarvisActionButton.Tone, action: @escaping () async -> Void) -> some View {
        JarvisActionButton(title: title, systemImage: icon, tone: tone) {
            Task { await action() }
        }
        .disabled(store.isBusy)
    }

    private func permissionRow(_ title: String, icon: String, detail: String) -> some View {
        HStack(spacing: 9) {
            Image(systemName: icon)
                .foregroundStyle(.secondary)
                .frame(width: 18)
            VStack(alignment: .leading, spacing: 1) {
                Text(title)
                    .font(.caption)
                    .fontWeight(.medium)
                Text(detail)
                    .font(.caption2)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
            }
            Spacer(minLength: 0)
        }
    }

    private func statusBadge(_ status: String, title: String? = nil) -> some View {
        Text((title ?? status).uppercased())
            .font(.system(size: 10, weight: .bold, design: .rounded))
            .tracking(0.7)
            .foregroundStyle(StatusVisuals.serviceColor(status))
            .padding(.horizontal, 7)
            .padding(.vertical, 3)
            .background(StatusVisuals.serviceColor(status).opacity(0.10), in: Capsule())
            .overlay {
                Capsule()
                    .strokeBorder(StatusVisuals.serviceColor(status).opacity(0.22), lineWidth: 0.7)
            }
    }

    private var accentColor: Color {
        StatusVisuals.jarvisColor(store.snapshot.jarvisState)
    }
}
