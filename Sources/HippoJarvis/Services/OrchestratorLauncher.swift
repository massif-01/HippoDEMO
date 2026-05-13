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

        for _ in 0..<30 {
            if (try? await client.health()) == true {
                return
            }
            try await Task.sleep(nanoseconds: 200_000_000)
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

        let runtime = root.appending(path: ".runtime", directoryHint: .isDirectory)
        try FileManager.default.createDirectory(at: runtime, withIntermediateDirectories: true)

        let logURL = runtime.appending(path: "orchestrator-app.log")
        let pidURL = runtime.appending(path: "orchestrator-app.pid")
        if !FileManager.default.fileExists(atPath: logURL.path) {
            FileManager.default.createFile(atPath: logURL.path, contents: nil)
        }

        let next = Process()
        let python = try pythonURL(root: root)
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
        environment["OWNSCRIBE_PYTHON"] = python.path
        environment["PATH"] = "\(runtimeBin.path):\(environment["PATH"] ?? "/usr/bin:/bin:/usr/sbin:/sbin")"
        next.environment = environment

        let output = try FileHandle(forWritingTo: logURL)
        try output.seekToEnd()
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
        try "\(next.processIdentifier)\n".write(to: pidURL, atomically: true, encoding: .utf8)
        process = next
        log("started uvicorn pid \(next.processIdentifier)")
    }

    private func projectRootURL() -> URL? {
        let bundleRoot = Bundle.main.bundleURL
            .deletingLastPathComponent()
            .deletingLastPathComponent()
        if FileManager.default.fileExists(atPath: bundleRoot.appending(path: "orchestrator/main.py").path) {
            return bundleRoot
        }

        let cwd = URL(fileURLWithPath: FileManager.default.currentDirectoryPath)
        if FileManager.default.fileExists(atPath: cwd.appending(path: "orchestrator/main.py").path) {
            return cwd
        }

        return nil
    }

    private func pythonURL(root: URL) throws -> URL {
        let runtimePython = root.appending(path: ".runtime/python/bin/python")
        if FileManager.default.isExecutableFile(atPath: runtimePython.path) {
            return runtimePython
        }

        log("project runtime missing: \(runtimePython.path)")
        throw OrchestratorError.badStatus(
            -1,
            "Hippo runtime is missing. Run script/build_and_run.sh --bootstrap-runtime before launching the app."
        )
    }

    private func log(_ message: String) {
        let root = projectRootURL()
        let fallback = URL(fileURLWithPath: NSTemporaryDirectory(), isDirectory: true)
        let runtime = (root ?? fallback).appending(path: ".runtime", directoryHint: .isDirectory)
        try? FileManager.default.createDirectory(at: runtime, withIntermediateDirectories: true)
        let line = "[\(Date().formatted(date: .omitted, time: .standard))] \(message)\n"
        let url = runtime.appending(path: "orchestrator-launcher.log")
        if !FileManager.default.fileExists(atPath: url.path) {
            FileManager.default.createFile(atPath: url.path, contents: nil)
        }
        if let handle = try? FileHandle(forWritingTo: url) {
            _ = try? handle.seekToEnd()
            try? handle.write(contentsOf: Data(line.utf8))
            try? handle.close()
        }
    }

}
