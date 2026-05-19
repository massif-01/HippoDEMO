import Foundation

enum AppLog {
    private static let lock = NSLock()
    nonisolated(unsafe) private static var logURL: URL?
    nonisolated(unsafe) private static var didReportFallback = false
    nonisolated(unsafe) private static var didReportWriteFailure = false
    private static let sensitiveKeys = [
        "api_key", "apikey", "authorization", "bearer", "key", "password", "secret", "signed-url",
        "signed_url", "signature", "token"
    ]

    static func configure(projectRoot: URL) {
        lock.lock()
        defer { lock.unlock() }

        let logsDirectory = projectRoot
            .appending(path: ".runtime", directoryHint: .isDirectory)
            .appending(path: "logs", directoryHint: .isDirectory)
        logURL = logsDirectory.appending(path: "hippo-swift.jsonl")
    }

    static func start() -> Date {
        Date()
    }

    static func event(
        action: String,
        path: String? = nil,
        status: String,
        startedAt: Date? = nil,
        error: Error? = nil,
        eventCount: Int? = nil
    ) {
        var payload: [String: Any] = [
            "ts": isoTimestamp(Date()),
            "action": sanitize(action),
            "status": sanitize(status)
        ]
        if let path {
            payload["path"] = sanitizePath(path)
        }
        if let startedAt {
            payload["duration_ms"] = max(0, Int(Date().timeIntervalSince(startedAt) * 1000))
        }
        if let error {
            payload["error"] = errorSummary(error)
        }
        if let eventCount {
            payload["event_count"] = eventCount
        }

        write(payload)
    }

    static func event(
        action: String,
        path: String? = nil,
        status: String,
        startedAt: Date? = nil,
        errorSummary: String,
        eventCount: Int? = nil
    ) {
        var payload: [String: Any] = [
            "ts": isoTimestamp(Date()),
            "action": sanitize(action),
            "status": sanitize(status),
            "error": truncate(sanitize(errorSummary), limit: 300)
        ]
        if let path {
            payload["path"] = sanitizePath(path)
        }
        if let startedAt {
            payload["duration_ms"] = max(0, Int(Date().timeIntervalSince(startedAt) * 1000))
        }
        if let eventCount {
            payload["event_count"] = eventCount
        }

        write(payload)
    }

    private static func write(_ payload: [String: Any]) {
        lock.lock()
        defer { lock.unlock() }

        guard let logURL else {
            if !didReportFallback {
                didReportFallback = true
                NSLog("[HippoJarvis] AppLog project root not located; using NSLog fallback")
            }
            NSLog("[HippoJarvis] %@", fallbackLine(payload))
            return
        }

        do {
            try FileManager.default.createDirectory(
                at: logURL.deletingLastPathComponent(),
                withIntermediateDirectories: true
            )
            let data = try JSONSerialization.data(withJSONObject: payload, options: [.sortedKeys])
            guard var line = String(data: data, encoding: .utf8) else { return }
            line.append("\n")
            if !FileManager.default.fileExists(atPath: logURL.path) {
                _ = FileManager.default.createFile(atPath: logURL.path, contents: nil)
            }
            let handle = try FileHandle(forWritingTo: logURL)
            defer { try? handle.close() }
            try handle.seekToEnd()
            if let lineData = line.data(using: .utf8) {
                try handle.write(contentsOf: lineData)
            }
        } catch {
            if !didReportWriteFailure {
                didReportWriteFailure = true
                NSLog("[HippoJarvis] AppLog write failed: %@", error.localizedDescription)
            }
        }
    }

    private static func fallbackLine(_ payload: [String: Any]) -> String {
        let action = payload["action"] as? String ?? "unknown"
        let status = payload["status"] as? String ?? "unknown"
        let path = payload["path"].map { " path=\($0)" } ?? ""
        return "action=\(action) status=\(status)\(path)"
    }

    private static func errorSummary(_ error: Error) -> String {
        if let orchestratorError = error as? OrchestratorError {
            switch orchestratorError {
            case .badStatus(let code, _):
                return "Orchestrator returned HTTP \(code)"
            case .invalidURL(let value):
                return truncate("Invalid Orchestrator URL: \(sanitizePath(value))", limit: 300)
            case .emptyResponse(let path):
                return truncate("Orchestrator returned an empty response for \(sanitizePath(path))", limit: 300)
            }
        }
        return truncate(sanitize(error.localizedDescription), limit: 300)
    }

    private static func sanitizePath(_ value: String) -> String {
        guard let components = URLComponents(string: value), components.scheme != nil else {
            return truncate(sanitize(value), limit: 300)
        }
        let host = components.host.map { "://\($0)" } ?? ""
        return truncate("\(components.scheme ?? "url")\(host)\(components.path)", limit: 300)
    }

    private static func sanitize(_ value: String) -> String {
        var result = value
        for key in sensitiveKeys {
            result = result.replacingOccurrences(
                of: "(?i)(\(NSRegularExpression.escapedPattern(for: key))\\s*[=:]\\s*)[^\\s,&]+",
                with: "$1[REDACTED]",
                options: .regularExpression
            )
        }
        result = result.replacingOccurrences(
            of: "(?i)Bearer\\s+[A-Za-z0-9._~+/=-]+",
            with: "Bearer [REDACTED]",
            options: .regularExpression
        )
        result = result.replacingOccurrences(
            of: "\\bsk-[A-Za-z0-9][A-Za-z0-9._-]{8,}\\b",
            with: "[REDACTED]",
            options: .regularExpression
        )
        result = result.replacingOccurrences(
            of: "(?i)((?:https?|wss?)://[^\\s]+/(?:[^\\s/]+/)*[^\\s?]*(?:signed-url|signed_url)[^\\s]*)",
            with: "[REDACTED_URL]",
            options: .regularExpression
        )
        result = result.replacingOccurrences(
            of: "(?i)((?:https?|wss?)://[^\\s]+[?][^\\s]*(?:token|signature|expires|key|secret)=[^\\s]+)",
            with: "[REDACTED_URL]",
            options: .regularExpression
        )
        return result
    }

    private static func truncate(_ value: String, limit: Int) -> String {
        if value.count <= limit {
            return value
        }
        return String(value.prefix(max(0, limit - 3))) + "..."
    }

    private static func isoTimestamp(_ date: Date) -> String {
        ISO8601DateFormatter().string(from: date)
    }
}
