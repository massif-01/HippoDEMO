import Foundation

final class SkillStore {
    private let fileManager = FileManager.default

    private var supportDirectory: URL {
        let base = fileManager.urls(for: .applicationSupportDirectory, in: .userDomainMask).first!
        return base.appending(path: "HippoDEMO", directoryHint: .isDirectory)
    }

    private var skillsDirectory: URL {
        supportDirectory.appending(path: "Skills", directoryHint: .isDirectory)
    }

    private var indexURL: URL {
        supportDirectory.appending(path: "skills.json")
    }

    func persist(_ skills: [SkillRecord]) {
        let startedAt = AppLog.start()
        do {
            try fileManager.createDirectory(at: skillsDirectory, withIntermediateDirectories: true)
            let encoder = JSONEncoder()
            encoder.outputFormatting = [.prettyPrinted, .sortedKeys]
            try encoder.encode(skills).write(to: indexURL, options: .atomic)

            for skill in skills {
                let filename = "\(slug(skill.name))-\(skill.id).md"
                try skill.content.write(
                    to: skillsDirectory.appending(path: filename),
                    atomically: true,
                    encoding: .utf8
                )
            }
            AppLog.event(
                action: "skill_store.persist",
                path: indexURL.path,
                status: "ok",
                startedAt: startedAt,
                eventCount: skills.count
            )
        } catch {
            NSLog("SkillStore persist failed: \(error.localizedDescription)")
            AppLog.event(
                action: "skill_store.persist",
                path: indexURL.path,
                status: "error",
                startedAt: startedAt,
                error: error,
                eventCount: skills.count
            )
        }
    }

    private func slug(_ value: String) -> String {
        let allowed = CharacterSet.alphanumerics.union(CharacterSet(charactersIn: "-_"))
        let folded = value.lowercased().replacingOccurrences(of: " ", with: "-")
        let scalars = folded.unicodeScalars.map { allowed.contains($0) ? Character($0) : "-" }
        let result = String(scalars).split(separator: "-").joined(separator: "-")
        return result.isEmpty ? "skill" : result
    }
}
