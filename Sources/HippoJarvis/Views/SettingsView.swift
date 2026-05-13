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
            syncProviderDrafts()
        }
        .onChange(of: store.ownscribeConfig) {
            syncProviderDrafts()
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

    private func nonEmpty(_ value: String) -> String? {
        let trimmed = value.trimmingCharacters(in: .whitespacesAndNewlines)
        return trimmed.isEmpty ? nil : trimmed
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
