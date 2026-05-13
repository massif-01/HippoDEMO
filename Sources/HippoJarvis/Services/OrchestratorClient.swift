import Foundation

enum OrchestratorError: LocalizedError {
    case invalidURL(String)
    case badStatus(Int, String?)

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
        }
    }
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
}
