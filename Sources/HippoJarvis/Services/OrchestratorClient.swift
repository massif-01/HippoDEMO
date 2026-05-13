import Foundation

enum OrchestratorError: LocalizedError {
    case invalidURL(String)
    case badStatus(Int, String?)
    case emptyResponse(String)

    var errorDescription: String? {
        switch self {
        case .invalidURL(let value):
            "Invalid Orchestrator URL: \(value)"
        case .badStatus(let code, let detail):
            if let detail, !detail.isEmpty {
                "Orchestrator returned HTTP \(code): \(detail)"
            } else {
                "Orchestrator returned HTTP \(code)"
            }
        case .emptyResponse(let path):
            "Orchestrator returned an empty response for \(path)"
        }
    }
}

private struct APIResponseEnvelope<T: Decodable>: Decodable {
    var code: Int?
    var msg: String?
    var data: T?
}

private struct ManusFileViewRequest: Encodable {
    var fileId: String
    var filePath: String?
}

struct OrchestratorClient {
    private var baseURL: URL {
        let stored = UserDefaults.standard.string(forKey: "orchestratorBaseURL")
        let value = stored?.isEmpty == false ? stored! : "http://127.0.0.1:8787"
        return URL(string: value) ?? URL(string: "http://127.0.0.1:8787")!
    }

    private let decoder: JSONDecoder = {
        let decoder = JSONDecoder()
        decoder.keyDecodingStrategy = .convertFromSnakeCase
        return decoder
    }()

    private let encoder: JSONEncoder = {
        let encoder = JSONEncoder()
        encoder.keyEncodingStrategy = .convertToSnakeCase
        return encoder
    }()

    func health() async throws -> Bool {
        let url = baseURL.appending(path: "health")
        let (_, response) = try await URLSession.shared.data(from: url)
        guard let http = response as? HTTPURLResponse else { return false }
        return (200..<300).contains(http.statusCode)
    }

    func state() async throws -> AppSnapshot {
        try await getSnapshot(path: "state")
    }

    func eventHistory(limit: Int = 50) async throws -> [EventRecord] {
        var components = URLComponents(url: baseURL.appending(path: "events/history"), resolvingAgainstBaseURL: false)
        components?.queryItems = [URLQueryItem(name: "limit", value: "\(limit)")]
        guard let url = components?.url else {
            throw OrchestratorError.invalidURL("events/history")
        }
        let (data, response) = try await URLSession.shared.data(from: url)
        try validate(response, data: data)
        return try decoder.decode([EventRecord].self, from: data)
    }

    func jarvisOn() async throws -> AppSnapshot {
        try await postSnapshot(path: "session/jarvis-on")
    }

    func jarvisOff() async throws -> AppSnapshot {
        try await postSnapshot(path: "session/jarvis-off")
    }

    func pause() async throws -> AppSnapshot {
        try await postSnapshot(path: "session/pause")
    }

    func resume() async throws -> AppSnapshot {
        try await postSnapshot(path: "session/resume")
    }

    func captureStart() async throws -> AppSnapshot {
        try await postSnapshot(path: "sop/capture-start")
    }

    func captureFinish() async throws -> AppSnapshot {
        try await postSnapshot(path: "sop/capture-finish")
    }

    func generateActiveTask() async throws -> AppSnapshot {
        try await postSnapshot(path: "active-task/generate")
    }

    func confirm(taskID: String) async throws -> AppSnapshot {
        try await postSnapshot(path: "active-task/\(taskID)/confirm")
    }

    func ignore(taskID: String) async throws -> AppSnapshot {
        try await postSnapshot(path: "active-task/\(taskID)/ignore")
    }

    func complete(taskID: String) async throws -> AppSnapshot {
        try await postSnapshot(path: "active-task/\(taskID)/complete")
    }

    func generateSkill() async throws -> AppSnapshot {
        try await postSnapshot(path: "skill/generate")
    }

    func deleteSkill(skillID: String) async throws -> AppSnapshot {
        try await deleteSnapshot(path: "skill/\(skillID)")
    }

    func openChronicleStart() async throws -> AppSnapshot {
        try await postSnapshot(path: "integrations/openchronicle/start")
    }

    func openChronicleStop() async throws -> AppSnapshot {
        try await postSnapshot(path: "integrations/openchronicle/stop")
    }

    func openChroniclePause() async throws -> AppSnapshot {
        try await postSnapshot(path: "integrations/openchronicle/pause")
    }

    func openChronicleResume() async throws -> AppSnapshot {
        try await postSnapshot(path: "integrations/openchronicle/resume")
    }

    func openChronicleCaptureOnce() async throws -> AppSnapshot {
        try await postSnapshot(path: "integrations/openchronicle/capture-once")
    }

    func openChronicleRebuildCapturesIndex() async throws -> AppSnapshot {
        try await postSnapshot(path: "integrations/openchronicle/rebuild-captures-index")
    }

    func openChronicleTimelineTick() async throws -> AppSnapshot {
        try await postSnapshot(path: "integrations/openchronicle/timeline-tick")
    }

    func ownscribeConfig() async throws -> OwnscribeConfig {
        try await get(path: "integrations/ownscribe/config")
    }

    func updateOwnscribeConfig(_ request: OwnscribeConfigRequest) async throws -> OwnscribeConfig {
        try await post(path: "integrations/ownscribe/config", body: request)
    }

    func ownscribeAudioDevices() async throws -> OwnscribeAudioDevicesResponse {
        try await get(path: "integrations/ownscribe/audio-devices")
    }

    func ownscribePreflight(network: Bool = false) async throws -> OwnscribePreflight {
        var components = URLComponents(url: baseURL.appending(path: "integrations/ownscribe/preflight"), resolvingAgainstBaseURL: false)
        components?.queryItems = [URLQueryItem(name: "network", value: network ? "true" : "false")]
        guard let url = components?.url else {
            throw OrchestratorError.invalidURL("integrations/ownscribe/preflight")
        }
        return try await get(url: url)
    }

    func aiManusConfig() async throws -> AiManusConfig {
        try await getWrapped(path: "integrations/ai-manus/config")
    }

    func updateAiManusConfig(_ request: AiManusConfigUpdateRequest) async throws -> AiManusConfig {
        try await post(path: "integrations/ai-manus/config", body: request)
    }

    func aiManusStatus() async throws -> AiManusStatus {
        try await getWrapped(path: "integrations/ai-manus/status")
    }

    func aiManusRuntimeStart(build: Bool = false) async throws -> AiManusRuntimeCommandResponse {
        try await post(
            path: "integrations/ai-manus/runtime/start",
            body: AiManusRuntimeCommandRequest(build: build)
        )
    }

    func aiManusRuntimeStop() async throws -> AiManusRuntimeCommandResponse {
        try await post(
            path: "integrations/ai-manus/runtime/stop",
            body: AiManusRuntimeCommandRequest(build: nil)
        )
    }

    func aiManusRuntimeRestart(build: Bool = false) async throws -> AiManusRuntimeCommandResponse {
        try await post(
            path: "integrations/ai-manus/runtime/restart",
            body: AiManusRuntimeCommandRequest(build: build)
        )
    }

    func aiManusRuntimeLogs(limit: Int = 80) async throws -> AiManusRuntimeLogsResponse {
        var components = URLComponents(url: baseURL.appending(path: "integrations/ai-manus/runtime/logs"), resolvingAgainstBaseURL: false)
        components?.queryItems = [URLQueryItem(name: "limit", value: "\(limit)")]
        guard let url = components?.url else {
            throw OrchestratorError.invalidURL("integrations/ai-manus/runtime/logs")
        }
        return try await get(url: url)
    }

    func createManusSession() async throws -> ManusSessionResponse {
        try await postWrapped(path: "integrations/ai-manus/session")
    }

    func manusSessions() async throws -> ManusThreadsResponse {
        try await getWrapped(path: "integrations/ai-manus/sessions")
    }

    func manusThreadDetail(sessionID: String) async throws -> ManusThreadDetail {
        try await getWrapped(path: "integrations/ai-manus/session/\(sessionID)/detail")
    }

    func stopManusSession(sessionID: String) async throws {
        try await postNoContent(path: "integrations/ai-manus/session/\(sessionID)/stop")
    }

    func manusSandboxAccess(sessionID: String) async throws -> ManusSandboxAccess {
        try await postWrapped(path: "integrations/ai-manus/session/\(sessionID)/sandbox-access")
    }

    func manusFiles(sessionID: String) async throws -> ManusFilesResponse {
        try await getWrapped(path: "integrations/ai-manus/session/\(sessionID)/files")
    }

    func manusFilePreview(sessionID: String, file: ManusFileInfo) async throws -> ManusFilePreview {
        let request = ManusFileViewRequest(fileId: file.fileIdentifier, filePath: file.path ?? file.filePath)
        return try await postWrapped(path: "integrations/ai-manus/session/\(sessionID)/file-view", body: request)
    }

    func manusFileDownloadLink(fileID: String) async throws -> ManusFileDownloadLink {
        try await postWrapped(path: "integrations/ai-manus/files/\(fileID)/signed-url")
    }

    func streamManusChat(
        sessionID: String,
        message: String,
        attachments: [JSONValue]? = nil,
        eventID: String? = nil,
        onEvent: @escaping @Sendable (ManusStreamEvent) async -> Void
    ) async throws {
        let requestBody = ManusChatRequest(
            message: message,
            timestamp: Int(Date().timeIntervalSince1970),
            eventId: eventID,
            attachments: attachments
        )
        let url = baseURL.appending(path: "integrations/ai-manus/session/\(sessionID)/chat")
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 1_800
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoder.encode(requestBody)

        let (bytes, response) = try await URLSession.shared.bytes(for: request)
        try validate(response)

        var eventName: String?
        for try await line in bytes.lines {
            if line.hasPrefix("event:") {
                eventName = String(line.dropFirst("event:".count)).trimmingCharacters(in: .whitespaces)
                continue
            }
            guard line.hasPrefix("data:") else { continue }

            let payload = String(line.dropFirst("data:".count)).trimmingCharacters(in: .whitespaces)
            guard !payload.isEmpty, payload != "[DONE]" else { continue }

            let data = Data(payload.utf8)
            let decoded = try decoder.decode(JSONValue.self, from: data)
            let nextEvent = ManusStreamEvent(
                event: eventName ?? eventNameFromData(decoded) ?? "message",
                data: dataFromEventEnvelope(decoded)
            )
            await onEvent(nextEvent)
            eventName = nil
        }
    }

    func cuaTargetSurface() async throws -> CuaTargetSurface {
        try await get(path: "integrations/cua/target-surface")
    }

    func cuaDriverStart() async throws -> AppSnapshot {
        try await postSnapshot(path: "integrations/cua/start")
    }

    func cuaDriverStop() async throws -> AppSnapshot {
        try await postSnapshot(path: "integrations/cua/stop")
    }

    func cuaDriverRestart() async throws -> AppSnapshot {
        try await postSnapshot(path: "integrations/cua/restart")
    }

    func detectIntervention() async throws -> AppSnapshot {
        try await postSnapshot(path: "intervention/detect")
    }

    func listenForEvents(onEvent: @escaping @Sendable () async -> Void) async throws {
        let url = baseURL.appending(path: "events")
        let (bytes, response) = try await URLSession.shared.bytes(from: url)
        try validate(response)

        for try await line in bytes.lines {
            if line.hasPrefix("data:") {
                await onEvent()
            }
        }
    }

    private func getSnapshot(path: String) async throws -> AppSnapshot {
        let url = baseURL.appending(path: path)
        let (data, response) = try await URLSession.shared.data(from: url)
        try validate(response, data: data)
        return try decoder.decode(AppSnapshot.self, from: data)
    }

    private func postSnapshot(path: String) async throws -> AppSnapshot {
        let url = baseURL.appending(path: path)
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 1_800
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        let (data, response) = try await URLSession.shared.data(for: request)
        try validate(response, data: data)
        return try decoder.decode(AppSnapshot.self, from: data)
    }

    private func get<T: Decodable>(path: String) async throws -> T {
        try await get(url: baseURL.appending(path: path))
    }

    private func get<T: Decodable>(url: URL) async throws -> T {
        let (data, response) = try await URLSession.shared.data(from: url)
        try validate(response, data: data)
        return try decoder.decode(T.self, from: data)
    }

    private func getWrapped<T: Decodable>(path: String) async throws -> T {
        let url = baseURL.appending(path: path)
        let (data, response) = try await URLSession.shared.data(from: url)
        try validate(response, data: data)
        return try decodeWrapped(T.self, from: data, path: path)
    }

    private func postWrapped<T: Decodable>(path: String) async throws -> T {
        let url = baseURL.appending(path: path)
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 60
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        let (data, response) = try await URLSession.shared.data(for: request)
        try validate(response, data: data)
        return try decodeWrapped(T.self, from: data, path: path)
    }

    private func postWrapped<Body: Encodable, Response: Decodable>(path: String, body: Body) async throws -> Response {
        let url = baseURL.appending(path: path)
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 60
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoder.encode(body)
        let (data, response) = try await URLSession.shared.data(for: request)
        try validate(response, data: data)
        return try decodeWrapped(Response.self, from: data, path: path)
    }

    private func post<Body: Encodable, Response: Decodable>(path: String, body: Body) async throws -> Response {
        let url = baseURL.appending(path: path)
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 60
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.httpBody = try encoder.encode(body)
        let (data, response) = try await URLSession.shared.data(for: request)
        try validate(response, data: data)
        return try decoder.decode(Response.self, from: data)
    }

    private func postNoContent(path: String) async throws {
        let url = baseURL.appending(path: path)
        var request = URLRequest(url: url)
        request.httpMethod = "POST"
        request.timeoutInterval = 60
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        let (data, response) = try await URLSession.shared.data(for: request)
        try validate(response, data: data)
    }

    private func deleteSnapshot(path: String) async throws -> AppSnapshot {
        let url = baseURL.appending(path: path)
        var request = URLRequest(url: url)
        request.httpMethod = "DELETE"
        request.setValue("application/json", forHTTPHeaderField: "Accept")
        let (data, response) = try await URLSession.shared.data(for: request)
        try validate(response, data: data)
        return try decoder.decode(AppSnapshot.self, from: data)
    }

    private func validate(_ response: URLResponse, data: Data? = nil) throws {
        guard let http = response as? HTTPURLResponse else { return }
        guard (200..<300).contains(http.statusCode) else {
            throw OrchestratorError.badStatus(http.statusCode, errorDetail(from: data))
        }
    }

    private func errorDetail(from data: Data?) -> String? {
        guard let data, !data.isEmpty else { return nil }
        if
            let object = try? JSONSerialization.jsonObject(with: data),
            let dictionary = object as? [String: Any],
            let detail = dictionary["detail"]
        {
            return stringValue(detail)
        }
        return String(data: data, encoding: .utf8).map(truncate)
    }

    private func stringValue(_ value: Any) -> String {
        if let string = value as? String {
            return truncate(string)
        }
        if let data = try? JSONSerialization.data(withJSONObject: value),
           let string = String(data: data, encoding: .utf8) {
            return truncate(string)
        }
        return truncate(String(describing: value))
    }

    private func truncate(_ value: String) -> String {
        if value.count <= 500 {
            return value
        }
        return String(value.prefix(497)) + "..."
    }

    private func decodeWrapped<T: Decodable>(_ type: T.Type, from data: Data, path: String) throws -> T {
        if let envelope = try? decoder.decode(APIResponseEnvelope<T>.self, from: data) {
            if let code = envelope.code, code != 0 {
                throw OrchestratorError.badStatus(code, envelope.msg)
            }
            if let value = envelope.data {
                return value
            }
        }
        if data.isEmpty {
            throw OrchestratorError.emptyResponse(path)
        }
        return try decoder.decode(type, from: data)
    }

    private func eventNameFromData(_ value: JSONValue) -> String? {
        guard case .object(let object) = value, case .string(let event)? = object["event"] else {
            return nil
        }
        return event
    }

    private func dataFromEventEnvelope(_ value: JSONValue) -> JSONValue? {
        guard case .object(let object) = value, let data = object["data"] else {
            return value
        }
        return data
    }
}
