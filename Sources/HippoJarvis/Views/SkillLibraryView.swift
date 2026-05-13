import SwiftUI

struct SkillLibraryView: View {
    @EnvironmentObject private var store: AppStateStore
    @State private var selection: SkillRecord.ID?
    @State private var searchText = ""
    @State private var skillPendingDeletion: SkillRecord?

    private var selectedSkill: SkillRecord? {
        filteredSkills.first { $0.id == selection } ?? filteredSkills.first
    }

    private var filteredSkills: [SkillRecord] {
        let query = searchText.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !query.isEmpty else { return store.snapshot.skills }

        return store.snapshot.skills.filter { skill in
            skill.name.localizedCaseInsensitiveContains(query)
                || skill.description.localizedCaseInsensitiveContains(query)
                || skill.content.localizedCaseInsensitiveContains(query)
        }
    }

    var body: some View {
        NavigationSplitView {
            sidebar
        } detail: {
            detail
        }
        .searchable(text: $searchText, placement: .toolbar, prompt: Text(store.text(.searchSkills)))
        .task {
            await store.bootstrap()
        }
        .onChange(of: store.snapshot.skills) { _, skills in
            if let selection, skills.contains(where: { $0.id == selection }) {
                return
            }
            selection = filteredSkills.first?.id
        }
        .alert(store.text(.deleteSkillQuestion), isPresented: deleteDialogPresented) {
            if let skill = skillPendingDeletion {
                Button(store.text(.deleteSkill), role: .destructive) {
                    deleteSkill(skill)
                }
            }
            Button(store.text(.cancel), role: .cancel) {}
        } message: {
            if let skill = skillPendingDeletion {
                Text(deleteMessage(for: skill))
            }
        }
    }

    private var sidebar: some View {
        List(selection: $selection) {
            Section(store.text(.artifactVault)) {
                ForEach(filteredSkills) { skill in
                    SkillSidebarRow(
                        skill: skill,
                        sourceType: sourceTypeLabel(for: skill),
                        created: compactDate(skill.createdAt),
                        shortID: shortID(skill.id)
                    )
                        .tag(skill.id)
                }
            }
        }
        .listStyle(.sidebar)
        .navigationTitle(store.text(.skills))
    }

    @ViewBuilder
    private var detail: some View {
        if let skill = selectedSkill {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    artifactHeader(skill)
                    metadataStrip(skill)
                    markdownPreview(skill)
                }
                .padding(20)
                .frame(maxWidth: 900, alignment: .leading)
                .frame(maxWidth: .infinity, alignment: .leading)
            }
            .navigationTitle(store.text(.artifactVault))
        } else {
            ContentUnavailableView(store.text(.noSkills), systemImage: "book.pages", description: Text(emptyDescription))
        }
    }

    private var emptyDescription: String {
        searchText.isEmpty ? store.text(.noSkillsDescription) : store.text(.noSkillSearch)
    }

    private var deleteDialogPresented: Binding<Bool> {
        Binding {
            skillPendingDeletion != nil
        } set: { isPresented in
            if !isPresented {
                skillPendingDeletion = nil
            }
        }
    }

    private func artifactHeader(_ skill: SkillRecord) -> some View {
        GlassSurface(inset: 16) {
            VStack(alignment: .leading, spacing: 14) {
                HStack(alignment: .top, spacing: 16) {
                    StatusPulse(color: .cyan, systemImage: "shippingbox.fill", isActive: true)

                    VStack(alignment: .leading, spacing: 8) {
                        HStack(spacing: 8) {
                            Text(store.text(.skillArtifact))
                                .font(.system(size: 11, weight: .bold, design: .rounded))
                                .tracking(1.5)
                                .foregroundStyle(.secondary)

                            ArtifactBadge(title: "Markdown", systemImage: "doc.plaintext", color: .cyan)
                        }

                        Text(skill.name)
                            .font(.system(size: 28, weight: .semibold, design: .rounded))
                            .lineLimit(2)

                        Text(skill.description)
                            .foregroundStyle(.secondary)
                            .lineLimit(3)

                        HStack(spacing: 8) {
                            ArtifactBadge(title: sourceLine(for: skill), systemImage: "record.circle", color: .blue)
                            ArtifactBadge(title: formattedDate(skill.createdAt), systemImage: "calendar", color: .secondary)
                        }
                    }

                    Spacer(minLength: 0)

                    Button(role: .destructive) {
                        skillPendingDeletion = skill
                    } label: {
                        Label(store.text(.delete), systemImage: "trash")
                    }
                    .buttonStyle(.bordered)
                    .controlSize(.small)
                    .disabled(store.isBusy)
                }

                Divider()

                LazyVGrid(columns: metadataColumns, alignment: .leading, spacing: 10) {
                    SignalMetric(title: store.text(.source), value: sourceLine(for: skill), systemImage: "tray.full", color: .blue)
                    SignalMetric(title: store.text(.created), value: formattedDate(skill.createdAt), systemImage: "calendar", color: .cyan)
                    SignalMetric(title: store.text(.size), value: sizeLabel(for: skill), systemImage: "number", color: .green)
                    SignalMetric(title: store.text(.generatedBy), value: adapterLabel(for: skill), systemImage: "cpu", color: .orange)
                }
            }
        }
    }

    private func metadataStrip(_ skill: SkillRecord) -> some View {
        HUDSection(nil) {
            HStack(spacing: 8) {
                metadataChip(store.text(.source), value: sourceTypeLabel(for: skill), icon: "tray.full")
                metadataChip(store.text(.format), value: "Markdown", icon: "doc.plaintext")
                metadataChip(store.text(.created), value: compactDate(skill.createdAt), icon: "calendar")
                metadataChip(store.text(.size), value: sizeLabel(for: skill), icon: "number")
                metadataChip(store.text(.generatedBy), value: adapterLabel(for: skill), icon: "cpu")
            }
            .lineLimit(1)
        }
    }

    private func markdownPreview(_ skill: SkillRecord) -> some View {
        HUDSection(store.text(.markdownPreview), systemImage: "doc.text.magnifyingglass") {
            VStack(alignment: .leading, spacing: 12) {
                HStack {
                    Text(store.text(.artifactContent))
                        .font(.system(size: 13, weight: .semibold, design: .rounded))
                    Spacer()
                    Text(store.text(.readOnly))
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Image(systemName: "lock")
                        .font(.caption)
                        .foregroundStyle(.secondary)
                }

                Text(skill.content)
                    .font(.system(.body, design: .monospaced))
                    .textSelection(.enabled)
                    .padding(16)
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .background(.black.opacity(0.08), in: RoundedRectangle(cornerRadius: 10, style: .continuous))
                    .overlay(alignment: .topLeading) {
                        RoundedRectangle(cornerRadius: 10, style: .continuous)
                            .strokeBorder(.white.opacity(0.12), lineWidth: 0.7)
                    }
            }
        }
    }

    private func metadataChip(_ title: String, value: String, icon: String) -> some View {
        Label {
            Text("\(title): \(value)")
        } icon: {
            Image(systemName: icon)
        }
        .font(.caption)
        .foregroundStyle(.secondary)
        .padding(.horizontal, 9)
        .padding(.vertical, 5)
        .background(.thinMaterial, in: Capsule())
    }

    private var metadataColumns: [GridItem] {
        [GridItem(.adaptive(minimum: 160), spacing: 10)]
    }

    private func formattedDate(_ value: String) -> String {
        guard let date = ISO8601DateFormatter().date(from: value) else {
            return value.isEmpty ? localSourceLabel : value
        }

        let locale = Locale(identifier: store.language == .simplifiedChinese ? "zh_Hans" : "en_US")
        return date.formatted(.dateTime.month(.abbreviated).day().hour().minute().locale(locale))
    }

    private func compactDate(_ value: String) -> String {
        guard let date = ISO8601DateFormatter().date(from: value) else {
            return value.isEmpty ? localSourceLabel : value
        }

        let locale = Locale(identifier: store.language == .simplifiedChinese ? "zh_Hans" : "en_US")
        return date.formatted(.dateTime.month(.abbreviated).day().locale(locale))
    }

    private func shortID(_ value: String) -> String {
        String(value.prefix(8))
    }

    private func deleteSkill(_ skill: SkillRecord) {
        Task {
            await store.deleteSkill(id: skill.id)
            skillPendingDeletion = nil
            if selection == skill.id {
                selection = filteredSkills.first?.id
            }
        }
    }

    private var localSourceLabel: String {
        store.language == .simplifiedChinese ? "本地" : "Local"
    }

    private var sessionSourceLabel: String {
        store.language == .simplifiedChinese ? "会话" : "Session"
    }

    private func sourceTypeLabel(for skill: SkillRecord) -> String {
        skill.sourceSessionId == nil && skill.sourceTaskId == nil ? localSourceLabel : sessionSourceLabel
    }

    private func sourceLine(for skill: SkillRecord) -> String {
        if let session = skill.sourceSessionId, let task = skill.sourceTaskId {
            return "\(sessionSourceLabel) \(shortID(session)) / \(store.text(.task)) \(shortID(task))"
        }
        if let session = skill.sourceSessionId {
            return "\(sessionSourceLabel) \(shortID(session))"
        }
        if let task = skill.sourceTaskId {
            return "\(store.text(.task)) \(shortID(task))"
        }
        return localSourceLabel
    }

    private func adapterLabel(for skill: SkillRecord) -> String {
        skill.sourceSessionId == nil && skill.sourceTaskId == nil ? "Local" : "Project_Cortex"
    }

    private func sizeLabel(for skill: SkillRecord) -> String {
        store.language == .simplifiedChinese ? "\(skill.content.count) 字符" : "\(skill.content.count) chars"
    }

    private func deleteMessage(for skill: SkillRecord) -> String {
        if store.language == .simplifiedChinese {
            return "这会从 Skill 库中移除 \(skill.name)，并删除它生成的 Markdown 产物。"
        }
        return "This removes \(skill.name) from the Skill Library and deletes its generated Markdown artifact."
    }
}

private struct SkillSidebarRow: View {
    let skill: SkillRecord
    let sourceType: String
    let created: String
    let shortID: String

    var body: some View {
        HStack(alignment: .top, spacing: 10) {
            Image(systemName: skill.sourceSessionId == nil ? "doc.plaintext" : "record.circle")
                .foregroundStyle(.secondary)
                .frame(width: 16, height: 18)

            VStack(alignment: .leading, spacing: 2) {
                Text(skill.name)
                    .lineLimit(1)
                Text(skill.description)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(1)
                HStack(spacing: 6) {
                    Text(sourceType)
                    Text(created)
                    Text("#\(shortID)")
                }
                .font(.caption2)
                .foregroundStyle(.tertiary)
                .lineLimit(1)
            }
        }
    }
}
