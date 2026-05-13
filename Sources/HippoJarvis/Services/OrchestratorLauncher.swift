import Foundation

@MainActor
final class OrchestratorLauncher {
    static let shared = OrchestratorLauncher()

    private var process: Process?
    private var logHandle: FileHandle?
    private var inputHandle: FileHandle?

    func ensureRunning(client: OrchestratorClient) async throws {
        log("ensureRunning requested")
        if (try? await client.health()) == true {
            log("health already ready")
            return
        }

        try start()

        for _ in 0..<240 {
            if (try? await client.health()) == true {
                return
            }
            try await Task.sleep(nanoseconds: 500_000_000)
        }

        log("health did not become ready")
        throw OrchestratorError.badStatus(-1, "Orchestrator health did not become ready")
    }

    private func start() throws {
        guard let root = projectRootURL() else {
            log("project root not found")
            throw OrchestratorError.invalidURL("Could not locate HippoDEMO project root")
        }
        log("project root: \(root.path)")

        if let process, process.isRunning {
            log("uvicorn already running as pid \(process.processIdentifier)")
            return
        }

        let runtime = URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true)
            .appending(path: "HippoDEMO", directoryHint: .isDirectory)
        try FileManager.default.createDirectory(at: runtime, withIntermediateDirectories: true)

        let pidURL = runtime.appending(path: "orchestrator-app.pid")

        let next = Process()
        let python = pythonURL(root: root)
        next.executableURL = python
        if python.path == "/usr/bin/env" {
            next.arguments = ["python3", "-m", "uvicorn", "orchestrator.main:app", "--host", "127.0.0.1", "--port", "8787"]
        } else {
            next.arguments = ["-m", "uvicorn", "orchestrator.main:app", "--host", "127.0.0.1", "--port", "8787"]
        }
        next.currentDirectoryURL = root
        var environment = ProcessInfo.processInfo.environment
        let runtimeBin = root.appending(path: ".runtime/python/bin", directoryHint: .isDirectory)
        environment["PYTHONPATH"] = root.path
        environment["HIPPODEMO_ROOT"] = root.path
        environment["HIPPODEMO_PYTHON"] = python.path
        environment["OWNSCRIBE_PYTHON"] = python.path
        let bundledPathEntries = [
            runtimeBin.path,
            root.appending(path: "orchestrator-runtime/bin").path,
            root.appending(path: "vlmac-runtime/bin").path
        ].filter { FileManager.default.fileExists(atPath: $0) }
        if !bundledPathEntries.isEmpty {
            environment["PATH"] = (bundledPathEntries + [environment["PATH"] ?? ""]).joined(separator: ":")
        }
        next.environment = environment

        let output = FileHandle(forWritingAtPath: "/dev/null")
        let input = FileHandle(forReadingAtPath: "/dev/null")
        next.standardOutput = output
        next.standardError = output
        if let input {
            next.standardInput = input
        }

        logHandle = output
        inputHandle = input

        log("starting uvicorn with \(python.path)")
        try next.run()
        try? "\(next.processIdentifier)\n".write(to: pidURL, atomically: true, encoding: .utf8)
        process = next
        log("started uvicorn pid \(next.processIdentifier)")
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
            root.appending(path: ".runtime/python/bin/python").path,
            root.appending(path: "orchestrator-runtime/bin/python").path,
            root.appending(path: "orchestrator/.venv/bin/python").path,
            "/opt/homebrew/Caskroom/miniconda/base/bin/python",
            "/opt/homebrew/opt/python@3.13/bin/python3.13",
            "/opt/homebrew/bin/python3",
            "/usr/bin/python3",
        ]

        for path in candidates where FileManager.default.isExecutableFile(atPath: path) {
            return URL(fileURLWithPath: path)
        }

        return URL(fileURLWithPath: "/usr/bin/env")
    }

    private func log(_ message: String) {
        NSLog("[HippoJarvis] %@", message)
    }

}
