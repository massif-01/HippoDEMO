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
    @State private var openChronicleModelDraft = ""
    @State private var openChronicleBaseURLDraft = ""
    @State private var openChronicleKeyEnvDraft = ""
    @State private var openChronicleKeyDraft = ""
    @State private var openChronicleMaxTokensDraft = ""
    @State private var openChronicleStageDraft = "default"
    @State private var vlmacServiceBaseURLDraft = ""
    @State private var vlmacVLLMBaseURLDraft = ""
    @State private var vlmacModelDraft = ""
    @State private var vlmacKeyDraft = ""
    @State private var vlmacTemperatureDraft = ""
    @State private var vlmacMaxTokensDraft = ""
    @State private var vlmacTimeoutDraft = ""
    @State private var basicMemorySemanticEnabledDraft = true
    @State private var basicMemoryProviderDraft = ""
    @State private var basicMemoryModelDraft = ""
    @State private var basicMemoryBaseURLDraft = ""
    @State private var basicMemoryKeyEnvDraft = ""
    @State private var basicMemoryKeyDraft = ""
    @State private var basicMemoryDimensionsDraft = ""
    @State private var basicMemoryBatchSizeDraft = ""
    @State private var basicMemoryConcurrencyDraft = ""
    @State private var basicMemoryTimeoutDraft = ""
    @State private var projectCortexUseRealDraft = false
    @State private var projectCortexServiceBaseURLDraft = ""
    @State private var projectCortexOpenAIBaseURLDraft = ""
    @State private var projectCortexModelDraft = ""
    @State private var projectCortexKeyDraft = ""
    @State private var projectCortexTemperatureDraft = ""
    @State private var projectCortexMaxTokensDraft = ""
    @State private var projectCortexTimeoutDraft = ""

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
                projectCortexSkillConsole
                basicMemoryEmbeddingConsole
                vlmacRuntimeConsole
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
            await store.refreshProviderConsoles()
            syncProviderDrafts()
            syncAiManusDrafts()
            syncOpenChronicleDrafts()
            syncVlmacDrafts()
            syncBasicMemoryDrafts()
            syncProjectCortexDrafts()
        }
        .onChange(of: store.ownscribeConfig) {
            syncProviderDrafts()
        }
        .onChange(of: store.aiManusConfig) {
            syncAiManusDrafts()
        }
        .onChange(of: store.openChronicleModelConfig) {
            syncOpenChronicleDrafts()
        }
        .onChange(of: store.vlmacConfig) {
            syncVlmacDrafts()
        }
        .onChange(of: store.basicMemoryEmbeddingConfig) {
            syncBasicMemoryDrafts()
        }
        .onChange(of: store.projectCortexConfig) {
            syncProjectCortexDrafts()
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
                Text("OpenAI Compatible API · ownscribe ASR + Summary")
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

    private var aiManusRuntimeConsole: some View {
        HUDSection("OpenAI Compatible API · ai-manus Agent", systemImage: "cpu") {
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
                    providerField("OpenAI Compatible Base URL", text: $aiManusAPIBaseDraft)
                    providerField("Agent Model", text: $aiManusModelDraft)
                    providerSecureField("Agent API Key", text: $aiManusKeyDraft)
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

    private var projectCortexSkillConsole: some View {
        HUDSection("OpenAI Compatible API · Skill Generator", systemImage: "wand.and.stars") {
            VStack(alignment: .leading, spacing: 12) {
                HStack(spacing: 10) {
                    if let projectCortexService {
                        ServiceLight(
                            service: projectCortexService,
                            title: "Project_Cortex",
                            detail: store.serviceDetail(projectCortexService.detail, status: projectCortexService.status)
                        )
                    } else {
                        Text(store.text(.notReported))
                            .font(.caption)
                            .foregroundStyle(.secondary)
                    }

                    Spacer(minLength: 0)

                    statusBadge(
                        store.projectCortexConfig.openaiApiKeyConfigured == true ? "available" : "stopped",
                        title: store.projectCortexConfig.openaiApiKeyConfigured == true ? "skill key set" : "skill key optional"
                    )
                    if store.projectCortexConfig.useReal == true {
                        statusBadge("available", title: "Project_Cortex service")
                    }
                }

                Divider()

                Toggle("Use Project_Cortex service instead of direct OpenAI-compatible fallback", isOn: $projectCortexUseRealDraft)
                    .toggleStyle(.switch)

                LazyVGrid(columns: [
                    GridItem(.flexible(), spacing: 10),
                    GridItem(.flexible(), spacing: 10)
                ], spacing: 10) {
                    providerField("Project_Cortex Service URL", text: $projectCortexServiceBaseURLDraft)
                    providerField("OpenAI Compatible Base URL", text: $projectCortexOpenAIBaseURLDraft)
                    providerField("Skill Model", text: $projectCortexModelDraft)
                    providerSecureField("Skill API Key", text: $projectCortexKeyDraft)
                    providerField("Temperature", text: $projectCortexTemperatureDraft)
                    providerField("Max Tokens", text: $projectCortexMaxTokensDraft)
                    providerField("Timeout seconds", text: $projectCortexTimeoutDraft)
                }

                HStack(spacing: 8) {
                    commandButton("Save Skill Generator", icon: "square.and.arrow.down", tone: .primary) {
                        await saveProjectCortexConfig()
                    }
                    commandButton(store.text(.refresh), icon: "arrow.clockwise", tone: .quiet) {
                        await store.refreshProviderConsoles()
                        syncProjectCortexDrafts()
                    }
                    Text(projectCortexDetail)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }
            }
        }
    }

    private var basicMemoryEmbeddingConsole: some View {
        HUDSection("OpenAI Compatible API · Basic Memory Embeddings", systemImage: "brain") {
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

                    statusBadge(
                        store.basicMemoryEmbeddingConfig.semanticEmbeddingApiKeyConfigured == true ? "available" : "stopped",
                        title: store.basicMemoryEmbeddingConfig.semanticEmbeddingApiKeyConfigured == true ? "embedding key set" : "embedding key missing"
                    )
                    if store.basicMemoryEmbeddingConfig.restartRequired == true {
                        statusBadge("mock", title: "restart required")
                    }
                }

                Divider()

                Toggle("Semantic search", isOn: $basicMemorySemanticEnabledDraft)
                    .toggleStyle(.switch)

                LazyVGrid(columns: [
                    GridItem(.flexible(), spacing: 10),
                    GridItem(.flexible(), spacing: 10)
                ], spacing: 10) {
                    providerField("Provider (fastembed/openai-compatible)", text: $basicMemoryProviderDraft)
                    providerField("Embedding Model", text: $basicMemoryModelDraft)
                    providerField("Embedding Base URL", text: $basicMemoryBaseURLDraft)
                    providerSecureField("Embedding API Key", text: $basicMemoryKeyDraft)
                    providerField("API Key Env", text: $basicMemoryKeyEnvDraft)
                    providerField("Dimensions", text: $basicMemoryDimensionsDraft)
                    providerField("Batch Size", text: $basicMemoryBatchSizeDraft)
                    providerField("Request Concurrency", text: $basicMemoryConcurrencyDraft)
                    providerField("Timeout seconds", text: $basicMemoryTimeoutDraft)
                }

                HStack(spacing: 8) {
                    commandButton("Save Basic Memory", icon: "square.and.arrow.down", tone: .primary) {
                        await saveBasicMemoryConfig()
                    }
                    commandButton(store.text(.refresh), icon: "arrow.clockwise", tone: .quiet) {
                        await store.refreshProviderConsoles()
                        syncBasicMemoryDrafts()
                    }
                    Text(basicMemoryDetail)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
                }
            }
        }
    }

    private var vlmacRuntimeConsole: some View {
        HUDSection("OpenAI Compatible API · vlmac VLM", systemImage: "eye") {
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

                    statusBadge(
                        store.vlmacConfig.vllmApiKeyConfigured == true ? "available" : "stopped",
                        title: store.vlmacConfig.vllmApiKeyConfigured == true ? "VLM key set" : "VLM key optional"
                    )
                    if store.vlmacConfig.restartRequired == true {
                        statusBadge("mock", title: "restart vlmac")
                    }
                }

                Divider()

                LazyVGrid(columns: [
                    GridItem(.flexible(), spacing: 10),
                    GridItem(.flexible(), spacing: 10)
                ], spacing: 10) {
                    providerField("vlmac Service URL", text: $vlmacServiceBaseURLDraft)
                    providerField("OpenAI Compatible Base URL", text: $vlmacVLLMBaseURLDraft)
                    providerField("Vision Model", text: $vlmacModelDraft)
                    providerSecureField("Vision API Key", text: $vlmacKeyDraft)
                    providerField("Temperature", text: $vlmacTemperatureDraft)
                    providerField("Max Tokens", text: $vlmacMaxTokensDraft)
                    providerField("Timeout seconds", text: $vlmacTimeoutDraft)
                }

                HStack(spacing: 8) {
                    commandButton("Save vlmac", icon: "square.and.arrow.down", tone: .primary) {
                        await saveVlmacConfig()
                    }
                    commandButton(store.text(.refresh), icon: "arrow.clockwise", tone: .quiet) {
                        await store.refreshProviderConsoles()
                        syncVlmacDrafts()
                    }
                    Text(vlmacRuntimeDetail)
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

                Divider()

                HStack(spacing: 8) {
                    Text("OpenAI Compatible API · OpenChronicle Writer")
                        .font(.caption)
                        .fontWeight(.medium)
                        .foregroundStyle(.secondary)
                    Spacer(minLength: 0)
                    statusBadge(
                        store.openChronicleModelConfig.apiKeyConfigured == true ? "available" : "stopped",
                        title: store.openChronicleModelConfig.apiKeyConfigured == true ? "key set" : "key missing"
                    )
                    if store.openChronicleModelConfig.restartRequired == true {
                        statusBadge("mock", title: "restart OpenChronicle")
                    }
                }

                LazyVGrid(columns: [
                    GridItem(.flexible(), spacing: 10),
                    GridItem(.flexible(), spacing: 10)
                ], spacing: 10) {
                    providerField("Stage (default/timeline/reducer/classifier/compact)", text: $openChronicleStageDraft)
                    providerField("Model", text: $openChronicleModelDraft)
                    providerField("Base URL", text: $openChronicleBaseURLDraft)
                    providerField("API Key Env", text: $openChronicleKeyEnvDraft)
                    providerSecureField("API Key", text: $openChronicleKeyDraft)
                    providerField("Max Tokens", text: $openChronicleMaxTokensDraft)
                }

                HStack(spacing: 8) {
                    commandButton("Save OpenChronicle Model", icon: "square.and.arrow.down", tone: .primary) {
                        await saveOpenChronicleConfig()
                    }
                    commandButton(store.text(.refresh), icon: "arrow.clockwise", tone: .quiet) {
                        await store.refreshProviderConsoles()
                        syncOpenChronicleDrafts()
                    }
                    Text(openChronicleModelDetail)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(2)
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

    private var vlmacService: ServiceStatus? {
        store.snapshot.services.first { $0.name.lowercased() == "vlmac" }
    }

    private var basicMemoryService: ServiceStatus? {
        store.snapshot.services.first { $0.name.lowercased() == "basic-memory" }
    }

    private var projectCortexService: ServiceStatus? {
        store.snapshot.services.first { $0.name.lowercased() == "project_cortex" || $0.name.lowercased() == "project-cortex" }
    }

    private var ownscribeService: ServiceStatus? {
        store.snapshot.services.first { $0.name.lowercased() == "ownscribe" }
    }

    private var aiManusService: ServiceStatus? {
        store.snapshot.services.first { $0.name.lowercased() == "ai-manus" }
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

    private var openChronicleModelDetail: String {
        let path = store.openChronicleModelConfig.configPath ?? "~/.openchronicle/config.toml"
        let source = store.openChronicleModelConfig.configExists == true ? "config" : "will create config"
        return "\(path) · \(source)"
    }

    private var vlmacRuntimeDetail: String {
        let env = store.vlmacConfig.envPath ?? "vlmac/.env"
        let restart = store.vlmacConfig.restartRequired == true ? " · restart vlmac to apply" : ""
        return "\(env)\(restart)"
    }

    private var basicMemoryDetail: String {
        let path = store.basicMemoryEmbeddingConfig.configPath ?? "orchestrator/data/basic_memory/config/config.json"
        let project = store.basicMemoryEmbeddingConfig.projectPath ?? "hippo"
        let restart = store.basicMemoryEmbeddingConfig.restartRequired == true ? " · rebuild/restart Basic Memory to apply" : ""
        return "\(path) · \(project)\(restart)"
    }

    private var projectCortexDetail: String {
        let path = store.projectCortexConfig.configPath ?? "orchestrator/data/project_cortex_config.json"
        let mode = store.projectCortexConfig.useReal == true ? "Project_Cortex service" : "direct OpenAI-compatible fallback"
        return "\(path) · \(mode)"
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
        asrKeyDraft = ""
        summaryKeyDraft = ""
        syncProviderDrafts()
    }

    private func syncProviderDrafts() {
        asrBaseURLDraft = store.ownscribeConfig.asrBaseUrl ?? ""
        asrModelDraft = store.ownscribeConfig.asrModel ?? ""
        summaryBaseURLDraft = store.ownscribeConfig.summaryBaseUrl ?? ""
        summaryModelDraft = store.ownscribeConfig.summaryModel ?? ""
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
        aiManusKeyDraft = ""
        syncAiManusDrafts()
    }

    private func saveOpenChronicleConfig() async {
        await store.updateOpenChronicleModelConfig(
            stage: nonEmpty(openChronicleStageDraft),
            model: nonEmpty(openChronicleModelDraft),
            baseUrl: nonEmpty(openChronicleBaseURLDraft),
            apiKeyEnv: nonEmpty(openChronicleKeyEnvDraft),
            apiKey: nonEmpty(openChronicleKeyDraft),
            maxTokens: intValue(openChronicleMaxTokensDraft)
        )
        openChronicleKeyDraft = ""
        syncOpenChronicleDrafts()
    }

    private func syncOpenChronicleDrafts() {
        openChronicleStageDraft = store.openChronicleModelConfig.stage ?? "default"
        openChronicleModelDraft = store.openChronicleModelConfig.model ?? ""
        openChronicleBaseURLDraft = store.openChronicleModelConfig.baseUrl ?? ""
        openChronicleKeyEnvDraft = store.openChronicleModelConfig.apiKeyEnv ?? "OPENAI_API_KEY"
        openChronicleMaxTokensDraft = store.openChronicleModelConfig.maxTokens.map(String.init) ?? ""
    }

    private func saveVlmacConfig() async {
        await store.updateVlmacConfig(
            serviceBaseUrl: nonEmpty(vlmacServiceBaseURLDraft),
            vllmBaseUrl: nonEmpty(vlmacVLLMBaseURLDraft),
            vllmModel: nonEmpty(vlmacModelDraft),
            vllmApiKey: nonEmpty(vlmacKeyDraft),
            temperature: doubleValue(vlmacTemperatureDraft),
            maxTokens: intValue(vlmacMaxTokensDraft),
            timeoutSeconds: doubleValue(vlmacTimeoutDraft)
        )
        vlmacKeyDraft = ""
        syncVlmacDrafts()
    }

    private func syncVlmacDrafts() {
        vlmacServiceBaseURLDraft = store.vlmacConfig.serviceBaseUrl ?? ""
        vlmacVLLMBaseURLDraft = store.vlmacConfig.vllmBaseUrl ?? ""
        vlmacModelDraft = store.vlmacConfig.vllmModel ?? ""
        vlmacTemperatureDraft = store.vlmacConfig.temperature.map { formatNumber($0) } ?? ""
        vlmacMaxTokensDraft = store.vlmacConfig.maxTokens.map(String.init) ?? ""
        vlmacTimeoutDraft = store.vlmacConfig.timeoutSeconds.map { formatNumber($0) } ?? ""
    }

    private func saveBasicMemoryConfig() async {
        await store.updateBasicMemoryEmbeddingConfig(
            semanticSearchEnabled: basicMemorySemanticEnabledDraft,
            semanticEmbeddingProvider: nonEmpty(basicMemoryProviderDraft),
            semanticEmbeddingModel: nonEmpty(basicMemoryModelDraft),
            semanticEmbeddingBaseUrl: nonEmpty(basicMemoryBaseURLDraft),
            semanticEmbeddingApiKey: nonEmpty(basicMemoryKeyDraft),
            semanticEmbeddingApiKeyEnv: nonEmpty(basicMemoryKeyEnvDraft),
            semanticEmbeddingDimensions: intValue(basicMemoryDimensionsDraft),
            semanticEmbeddingBatchSize: intValue(basicMemoryBatchSizeDraft),
            semanticEmbeddingRequestConcurrency: intValue(basicMemoryConcurrencyDraft),
            semanticEmbeddingTimeout: doubleValue(basicMemoryTimeoutDraft)
        )
        basicMemoryKeyDraft = ""
        syncBasicMemoryDrafts()
    }

    private func syncBasicMemoryDrafts() {
        basicMemorySemanticEnabledDraft = store.basicMemoryEmbeddingConfig.semanticSearchEnabled ?? true
        basicMemoryProviderDraft = store.basicMemoryEmbeddingConfig.semanticEmbeddingProvider ?? ""
        basicMemoryModelDraft = store.basicMemoryEmbeddingConfig.semanticEmbeddingModel ?? ""
        basicMemoryBaseURLDraft = store.basicMemoryEmbeddingConfig.semanticEmbeddingBaseUrl ?? ""
        basicMemoryKeyEnvDraft = store.basicMemoryEmbeddingConfig.semanticEmbeddingApiKeyEnv ?? "OPENAI_API_KEY"
        basicMemoryDimensionsDraft = store.basicMemoryEmbeddingConfig.semanticEmbeddingDimensions.map(String.init) ?? ""
        basicMemoryBatchSizeDraft = store.basicMemoryEmbeddingConfig.semanticEmbeddingBatchSize.map(String.init) ?? ""
        basicMemoryConcurrencyDraft = store.basicMemoryEmbeddingConfig.semanticEmbeddingRequestConcurrency.map(String.init) ?? ""
        basicMemoryTimeoutDraft = store.basicMemoryEmbeddingConfig.semanticEmbeddingTimeout.map { formatNumber($0) } ?? ""
    }

    private func saveProjectCortexConfig() async {
        await store.updateProjectCortexConfig(
            useReal: projectCortexUseRealDraft,
            serviceBaseUrl: nonEmpty(projectCortexServiceBaseURLDraft),
            openaiBaseUrl: nonEmpty(projectCortexOpenAIBaseURLDraft),
            openaiModel: nonEmpty(projectCortexModelDraft),
            openaiApiKey: nonEmpty(projectCortexKeyDraft),
            temperature: doubleValue(projectCortexTemperatureDraft),
            maxTokens: intValue(projectCortexMaxTokensDraft),
            timeoutSeconds: doubleValue(projectCortexTimeoutDraft)
        )
        projectCortexKeyDraft = ""
        syncProjectCortexDrafts()
    }

    private func syncProjectCortexDrafts() {
        projectCortexUseRealDraft = store.projectCortexConfig.useReal ?? false
        projectCortexServiceBaseURLDraft = store.projectCortexConfig.serviceBaseUrl ?? ""
        projectCortexOpenAIBaseURLDraft = store.projectCortexConfig.openaiBaseUrl ?? ""
        projectCortexModelDraft = store.projectCortexConfig.openaiModel ?? ""
        projectCortexTemperatureDraft = store.projectCortexConfig.temperature.map { formatNumber($0) } ?? ""
        projectCortexMaxTokensDraft = store.projectCortexConfig.maxTokens.map(String.init) ?? ""
        projectCortexTimeoutDraft = store.projectCortexConfig.timeoutSeconds.map { formatNumber($0) } ?? ""
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
