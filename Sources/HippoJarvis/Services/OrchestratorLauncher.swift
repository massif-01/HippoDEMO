import Foundation
import Darwin

@MainActor
final class OrchestratorLauncher {
    static let shared = OrchestratorLauncher()

    private var process: Process?
    private var outputPipe: Pipe?
    private var inputHandle: FileHandle?

    func ensureRunning(client: OrchestratorClient) async throws {
        let startedAt = AppLog.start()
        log("ensureRunning requested")
        if let root = projectRootURL() {
            AppLog.configure(projectRoot: root)
            AppLog.event(action: "orchestrator.ensure_running", path: root.path, status: "root_located")
        } else {
            AppLog.event(action: "orchestrator.ensure_running", status: "root_missing")
        }

        if (try? await client.health()) == true {
            log("health already ready")
            AppLog.event(action: "orchestrator.ensure_running", status: "already_ready", startedAt: startedAt)
            return
        }

        if let process, process.isRunning {
            let pid = process.processIdentifier
            AppLog.event(action: "orchestrator.start", path: "pid \(pid)", status: "running_unhealthy", startedAt: startedAt)
            for _ in 0..<16 {
                try await Task.sleep(nanoseconds: 500_000_000)
                if (try? await client.health()) == true {
                    AppLog.event(action: "orchestrator.ensure_running", status: "ready_existing", startedAt: startedAt)
                    return
                }
                if !process.isRunning {
                    break
                }
            }
            if process.isRunning {
                process.terminate()
                AppLog.event(action: "orchestrator.start", path: "pid \(pid)", status: "terminated_unhealthy", startedAt: startedAt)
            }
            self.process = nil
        }

        do {
            try start()
        } catch {
            AppLog.event(action: "orchestrator.start", status: "error", startedAt: startedAt, error: error)
            throw error
        }

        for _ in 0..<240 {
            if (try? await client.health()) == true {
                AppLog.event(action: "orchestrator.ensure_running", status: "ready", startedAt: startedAt)
                return
            }
            if let process, !process.isRunning {
                let error = OrchestratorError.badStatus(Int(process.terminationStatus), "Orchestrator exited before health became ready")
                AppLog.event(action: "orchestrator.ensure_running", status: "exited", startedAt: startedAt, error: error)
                throw error
            }
            try await Task.sleep(nanoseconds: 500_000_000)
        }

        log("health did not become ready")
        let error = OrchestratorError.badStatus(-1, "Orchestrator health did not become ready")
        AppLog.event(action: "orchestrator.ensure_running", status: "error", startedAt: startedAt, error: error)
        if let process, process.isRunning {
            let pid = process.processIdentifier
            process.terminate()
            AppLog.event(action: "orchestrator.start", path: "pid \(pid)", status: "terminated_after_timeout")
        }
        throw error
    }

    private func start() throws {
        let startedAt = AppLog.start()
        guard let root = projectRootURL() else {
            log("project root not found")
            throw OrchestratorError.invalidURL("Could not locate HippoDEMO project root")
        }
        AppLog.configure(projectRoot: root)
        AppLog.event(action: "orchestrator.start", path: root.path, status: "preparing", startedAt: startedAt)
        log("project root: \(root.path)")

        if let process {
            if process.isRunning {
                log("uvicorn already running as pid \(process.processIdentifier)")
                AppLog.event(action: "orchestrator.start", path: root.path, status: "already_running", startedAt: startedAt)
                return
            }
            self.process = nil
        }

        let runtime = root.appending(path: ".runtime", directoryHint: .isDirectory)
        try FileManager.default.createDirectory(at: runtime, withIntermediateDirectories: true)

        let pidURL = runtime.appending(path: "orchestrator-app.pid")
        let logURL = runtime.appending(path: "orchestrator-app.log")

        let next = Process()
        let python = pythonURL(root: root)
        if python.path == "/usr/bin/env" {
            next.executableURL = python
            next.arguments = ["python3", "-m", "uvicorn", "orchestrator.main:app", "--host", "127.0.0.1", "--port", "8787"]
        } else {
            next.executableURL = python
            next.arguments = ["-m", "uvicorn", "orchestrator.main:app", "--host", "127.0.0.1", "--port", "8787"]
        }
        next.currentDirectoryURL = root
        let inheritedEnvironment = ProcessInfo.processInfo.environment
        var environment: [String: String] = [:]
        for key in ["HOME", "USER", "LOGNAME", "SHELL", "TMPDIR", "SSH_AUTH_SOCK"] {
            if let value = inheritedEnvironment[key] {
                environment[key] = value
            }
        }
        environment["LANG"] = "en_US.UTF-8"
        environment["LC_CTYPE"] = "UTF-8"
        environment["PYTHONUTF8"] = "1"
        environment["PYTHONNOUSERSITE"] = "1"
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        let runtimeBin = root.appending(path: ".runtime/python/bin", directoryHint: .isDirectory)
        environment["PYTHONPATH"] = pythonPath(root: root, python: python)
        environment["HIPPODEMO_ROOT"] = root.path
        environment["HIPPODEMO_PYTHON"] = python.path
        environment["OWNSCRIBE_PYTHON"] = python.path
        let bundledPathEntries = [
            runtimeBin.path,
            root.appending(path: "orchestrator-runtime/bin").path,
            root.appending(path: "vlmac-runtime/bin").path
        ].filter { pathExists(URL(fileURLWithPath: $0).appending(path: "python").path) }
        let systemPathEntries = [
            "/opt/anaconda3/bin",
            "/opt/homebrew/bin",
            "/opt/homebrew/sbin",
            "/usr/local/bin",
            "/usr/bin",
            "/bin",
            "/usr/sbin",
            "/sbin"
        ]
        let pathEntries = python.path.hasPrefix("/opt/anaconda3/")
            ? (systemPathEntries + bundledPathEntries)
            : (bundledPathEntries + systemPathEntries)
        environment["PATH"] = pathEntries.joined(separator: ":")
        next.environment = environment

        let outputPipe = Pipe()
        outputPipe.fileHandleForReading.readabilityHandler = { handle in
            let data = handle.availableData
            guard !data.isEmpty else { return }
            Self.appendProcessOutput(data, to: logURL)
        }
        let input = FileHandle(forReadingAtPath: "/dev/null")
        next.standardOutput = outputPipe.fileHandleForWriting
        next.standardError = outputPipe.fileHandleForWriting
        if let input {
            next.standardInput = input
        }
        next.terminationHandler = { _ in
            outputPipe.fileHandleForReading.readabilityHandler = nil
        }

        self.outputPipe = outputPipe
        inputHandle = input

        log("starting uvicorn with \(python.path)")
        AppLog.event(action: "orchestrator.start", path: logURL.path, status: "stdio_log", startedAt: startedAt)
        AppLog.event(action: "orchestrator.start", path: root.path, status: "launching", startedAt: startedAt)
        try next.run()
        try? "\(next.processIdentifier)\n".write(to: pidURL, atomically: true, encoding: .utf8)
        process = next
        log("started uvicorn pid \(next.processIdentifier)")
        AppLog.event(action: "orchestrator.start", path: root.path, status: "started", startedAt: startedAt)
    }

    private func projectRootURL() -> URL? {
        let starts = [
            Bundle.main.bundleURL,
            URL(fileURLWithPath: FileManager.default.currentDirectoryPath, isDirectory: true),
        ]
        for start in starts {
            if let root = firstProjectRoot(from: start) {
                return root
            }
        }

        return nil
    }

    private func firstProjectRoot(from url: URL) -> URL? {
        var current = url.hasDirectoryPath ? url : url.deletingLastPathComponent()
        for _ in 0..<8 {
            if FileManager.default.fileExists(atPath: current.appending(path: "orchestrator/main.py").path) {
                return current
            }
            let next = current.deletingLastPathComponent()
            if next.path == current.path {
                break
            }
            current = next
        }
        return nil
    }

    private func pythonURL(root: URL) -> URL {
        let candidates = [
            "/opt/anaconda3/bin/python",
            "/opt/homebrew/opt/python@3.14/bin/python3.14",
            "/opt/homebrew/bin/python3",
            root.appending(path: "orchestrator-runtime/bin/python").path,
            "/usr/bin/python3"
        ]
        for path in candidates where executableExists(path) {
            return URL(fileURLWithPath: path)
        }
        return URL(fileURLWithPath: "/usr/bin/env")
    }

    private func pythonPath(root: URL, python: URL) -> String {
        if python.path.hasPrefix("/opt/anaconda3/") {
            return root.path
        }

        var entries: [String] = []
        for version in ["python3.14", "python3.13", "python3.12"] {
            let sitePackages = root.appending(path: "orchestrator-runtime/lib/\(version)/site-packages", directoryHint: .isDirectory)
            if pathExists(sitePackages.path) {
                entries.append(sitePackages.path)
            }
        }
        entries.append(root.path)
        return entries.joined(separator: ":")
    }

    private func executableExists(_ path: String) -> Bool {
        Darwin.access(path, X_OK) == 0
    }

    private func pathExists(_ path: String) -> Bool {
        Darwin.access(path, F_OK) == 0
    }

    private func log(_ message: String) {
        // Keep launch on the JSON AppLog path; NSLog can block when the macOS log store is unhealthy.
    }

    nonisolated private static func appendProcessOutput(_ data: Data, to url: URL) {
        url.path.withCString { path in
            let fd = Darwin.open(path, O_WRONLY | O_CREAT | O_APPEND, S_IRUSR | S_IWUSR | S_IRGRP | S_IROTH)
            guard fd >= 0 else { return }
            defer { Darwin.close(fd) }

            data.withUnsafeBytes { buffer in
                guard let base = buffer.baseAddress else { return }
                var offset = 0
                var remaining = buffer.count
                while remaining > 0 {
                    let written = Darwin.write(fd, base.advanced(by: offset), remaining)
                    if written <= 0 { break }
                    offset += written
                    remaining -= written
                }
            }
        }
    }

}
