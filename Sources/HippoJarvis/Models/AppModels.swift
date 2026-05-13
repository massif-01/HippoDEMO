import Foundation

indirect enum JSONValue: Codable, Equatable, Sendable {
    case string(String)
    case number(Double)
    case bool(Bool)
    case object([String: JSONValue])
    case array([JSONValue])
    case null

    init(from decoder: Decoder) throws {
        let container = try decoder.singleValueContainer()
        if container.decodeNil() {
            self = .null
        } else if let value = try? container.decode(Bool.self) {
            self = .bool(value)
        } else if let value = try? container.decode(Double.self) {
            self = .number(value)
        } else if let value = try? container.decode(String.self) {
            self = .string(value)
        } else if let value = try? container.decode([JSONValue].self) {
            self = .array(value)
        } else {
            self = .object(try container.decode([String: JSONValue].self))
        }
    }

    func encode(to encoder: Encoder) throws {
        var container = encoder.singleValueContainer()
        switch self {
        case .string(let value):
            try container.encode(value)
        case .number(let value):
            try container.encode(value)
        case .bool(let value):
            try container.encode(value)
        case .object(let value):
            try container.encode(value)
        case .array(let value):
            try container.encode(value)
        case .null:
            try container.encodeNil()
        }
    }

    var compactDescription: String {
        switch self {
        case .string(let value):
            value
        case .number(let value):
            value.rounded() == value ? String(Int(value)) : String(value)
        case .bool(let value):
            value ? "true" : "false"
        case .object(let value):
            value.keys.sorted().prefix(3).joined(separator: ", ")
        case .array(let value):
            "\(value.count) items"
        case .null:
            "null"
        }
    }
}

enum JarvisState: String, Codable, Sendable {
    case idle
    case meetingActive = "meeting_active"
    case paused
    case sopMarking = "sop_marking"
    case sopGenerating = "sop_generating"
    case thinking
    case activeTaskCandidate = "active_task_candidate"
    case taskSurfaceDetected = "task_surface_detected"
    case taskExecuting = "task_executing"
    case taskReviewing = "task_reviewing"
    case patternDetected = "pattern_detected"
    case error
}

struct AppSnapshot: Codable, Sendable {
    var jarvisState: JarvisState
    var statusMessage: String
    var currentSession: DemoSession?
    var sopCapture: SopCapture?
    var highlightSegment: HighlightSegment?
    var frontmostContext: ForegroundAXSnapshot?
    var followUpPackage: FollowUpPackage?
    var mailDraftInsertResult: MailDraftInsertResult?
    var workerStatuses: [PlanWorkerStatus]?
    var memoryContextChunks: [MemoryContextChunk]?
    var currentTask: ActiveTask?
    var skills: [SkillRecord]
    var services: [ServiceStatus]

    static let empty = AppSnapshot(
        jarvisState: .idle,
        statusMessage: "Waiting for task",
        currentSession: nil,
        sopCapture: nil,
        highlightSegment: nil,
        frontmostContext: nil,
        followUpPackage: nil,
        mailDraftInsertResult: nil,
        workerStatuses: [],
        memoryContextChunks: [],
        currentTask: nil,
        skills: [],
        services: []
    )
}

struct EventRecord: Identifiable, Codable, Equatable, Sendable {
    var id: String
    var type: String
    var timestamp: String
    var sessionId: String?
    var payload: [String: JSONValue]
}

struct DemoSession: Identifiable, Codable, Sendable {
    var id: String
    var title: String
    var startedAt: String
    var endedAt: String?
    var artifacts: [Artifact]
}

struct SopCapture: Codable, Sendable {
    var checkIn: String?
    var checkOut: String?
    var state: JarvisState
}

struct MemoryContextChunk: Identifiable, Codable, Equatable, Sendable {
    var id: String
    var sessionId: String?
    var source: String
    var startAt: String
    var endAt: String
    var content: String
    var metadata: [String: JSONValue]
    var createdAt: String?
}

struct ForegroundAXSnapshot: Codable, Equatable, Sendable {
    var bundleId: String?
    var appName: String?
    var windowTitle: String?
    var focusedElement: String?
    var visibleText: String
    var treeMarkdown: String
    var editableFields: [JSONValue]
    var targetSurface: CuaTargetSurface?
    var capturedAt: String?
    var metadata: [String: JSONValue]

    static let empty = ForegroundAXSnapshot(
        bundleId: nil,
        appName: nil,
        windowTitle: nil,
        focusedElement: nil,
        visibleText: "",
        treeMarkdown: "",
        editableFields: [],
        targetSurface: nil,
        capturedAt: nil,
        metadata: [:]
    )
}

struct HighlightSegment: Identifiable, Codable, Equatable, Sendable {
    var id: String
    var checkIn: String?
    var checkOut: String?
    var status: String
    var sourceSessionId: String?
    var contextPriority: String?
    var generatedSkillId: String?
    var contextChunkIds: [String]
    var error: String?
}

struct FollowUpPackage: Identifiable, Codable, Equatable, Sendable {
    var id: String
    var subject: String
    var body: String
    var minutesPath: String?
    var contextPriority: String
    var sourceSessionId: String?
    var contextChunkIds: [String]
    var createdAt: String?
    var metadata: [String: JSONValue]
}

struct MailDraftInsertResult: Codable, Equatable, Sendable {
    var ok: Bool
    var detail: String
    var targetSurface: CuaTargetSurface?
    var insertedAt: String?
    var metadata: [String: JSONValue]
}

struct PlanWorkerStatus: Identifiable, Codable, Equatable, Sendable {
    var name: String
    var status: String
    var detail: String?
    var startedAt: String?
    var updatedAt: String?
    var metadata: [String: JSONValue]

    var id: String { name }
}

struct PlanStatus: Codable, Equatable, Sendable {
    var highlightSegment: HighlightSegment?
    var frontmostContext: ForegroundAXSnapshot?
    var followUpPackage: FollowUpPackage?
    var mailDraftInsertResult: MailDraftInsertResult?
    var workerStatuses: [PlanWorkerStatus]
    var memoryContextChunks: [MemoryContextChunk]

    static let empty = PlanStatus(
        highlightSegment: nil,
        frontmostContext: nil,
        followUpPackage: nil,
        mailDraftInsertResult: nil,
        workerStatuses: [],
        memoryContextChunks: []
    )
}

struct ActiveTask: Identifiable, Codable, Sendable {
    var id: String
    var title: String
    var intent: String
    var confidence: Double
    var state: JarvisState
    var artifacts: [Artifact]
    var proposedActions: [ProposedAction]
}

struct ProposedAction: Identifiable, Codable, Sendable {
    var id: String
    var type: String
    var label: String
    var requiresConfirmation: Bool
    var status: String?
}

struct CuaTargetSurface: Codable, Equatable, Sendable {
    var safe: Bool
    var status: String
    var mode: String
    var requiresConfirmation: Bool
    var reason: String
    var appName: String?
    var bundleId: String?
    var pid: Int?
    var windowId: Int?
    var windowTitle: String?
    var elementIndex: Int?
    var elementRole: String?
    var detail: String?

    static let empty = CuaTargetSurface(
        safe: false,
        status: "unknown",
        mode: "none",
        requiresConfirmation: true,
        reason: "Target surface has not been checked.",
        appName: nil,
        bundleId: nil,
        pid: nil,
        windowId: nil,
        windowTitle: nil,
        elementIndex: nil,
        elementRole: nil,
        detail: nil
    )

    var displayName: String {
        if let appName, !appName.isEmpty {
            if let windowTitle, !windowTitle.isEmpty {
                return "\(appName) · \(windowTitle)"
            }
            return appName
        }
        return status.replacingOccurrences(of: "_", with: " ").capitalized
    }

    var modeLabel: String {
        switch mode {
        case "textedit":
            return "TextEdit"
        case "low_risk_editor":
            return "Low Risk Editor"
        case "notes_editor":
            return "Notes"
        case "allowlisted_editor":
            return "Allowlisted Editor"
        case "current_focused_text":
            return "Focused Text"
        case "blocked_app":
            return "Blocked App"
        default:
            return mode
                .replacingOccurrences(of: "_", with: " ")
                .capitalized
        }
    }
}

struct Artifact: Identifiable, Codable, Sendable {
    var id: String
    var kind: String
    var title: String
    var path: String?
    var content: String?
    var createdAt: String?
    var metadata: [String: JSONValue]?
}

struct SkillRecord: Identifiable, Codable, Equatable, Sendable {
    var id: String
    var name: String
    var description: String
    var content: String
    var createdAt: String
    var sourceSessionId: String?
    var sourceTaskId: String?
}

struct ServiceStatus: Identifiable, Codable, Sendable {
    var id: String
    var name: String
    var status: String
    var detail: String?
}

enum OwnscribeAudioSource: String, Codable, CaseIterable, Identifiable, Sendable {
    case system
    case mic
    case both

    var id: String { rawValue }
}

struct OwnscribeConfig: Codable, Equatable, Sendable {
    var audioSource: OwnscribeAudioSource
    var micDevice: String?
    var audioDisplay: Bool?
    var asrProvider: String?
    var asrBaseUrl: String?
    var asrModel: String?
    var summaryProvider: String?
    var summaryBaseUrl: String?
    var summaryModel: String?
    var asrApiKeyConfigured: Bool?
    var summaryApiKeyConfigured: Bool?
    var configPath: String?

    static let empty = OwnscribeConfig(
        audioSource: .system,
        micDevice: nil,
        audioDisplay: true,
        asrProvider: nil,
        asrBaseUrl: nil,
        asrModel: nil,
        summaryProvider: nil,
        summaryBaseUrl: nil,
        summaryModel: nil,
        asrApiKeyConfigured: false,
        summaryApiKeyConfigured: false,
        configPath: nil
    )
}

struct OwnscribeConfigRequest: Codable, Sendable {
    var audioSource: OwnscribeAudioSource?
    var micDevice: String?
    var audioDisplay: Bool?
    var asrProvider: String?
    var asrBaseUrl: String?
    var asrModel: String?
    var asrApiKey: String?
    var summaryProvider: String?
    var summaryBaseUrl: String?
    var summaryModel: String?
    var summaryApiKey: String?
    var apiKey: String?
}

struct OwnscribeAudioDevice: Identifiable, Codable, Equatable, Sendable {
    var name: String
    var isDefault: Bool

    var id: String { name }
}

struct OwnscribeAudioDevicesResponse: Codable, Equatable, Sendable {
    var ok: Bool
    var devices: [OwnscribeAudioDevice]
    var raw: String?
    var detail: String?

    static let empty = OwnscribeAudioDevicesResponse(ok: false, devices: [], raw: nil, detail: nil)
}

struct OwnscribePreflight: Codable, Equatable, Sendable {
    var ok: Bool
    var updatedAt: String?
    var config: OwnscribeConfig?
    var checks: [OwnscribePreflightCheck]
    var networkChecked: Bool?
    var latestTimelinePath: String?

    static let empty = OwnscribePreflight(ok: false, updatedAt: nil, config: nil, checks: [], networkChecked: false, latestTimelinePath: nil)
}

struct OwnscribePreflightCheck: Identifiable, Codable, Equatable, Sendable {
    var name: String
    var ok: Bool
    var detail: String

    var id: String { name }
}

struct OpenChronicleModelConfig: Codable, Equatable, Sendable {
    var stage: String?
    var model: String?
    var baseUrl: String?
    var apiKeyEnv: String?
    var apiKeyConfigured: Bool?
    var maxTokens: Int?
    var configPath: String?
    var configExists: Bool?
    var restartRequired: Bool?

    static let empty = OpenChronicleModelConfig(
        stage: "default",
        model: nil,
        baseUrl: nil,
        apiKeyEnv: "OPENAI_API_KEY",
        apiKeyConfigured: false,
        maxTokens: nil,
        configPath: nil,
        configExists: nil,
        restartRequired: nil
    )
}

struct OpenChronicleModelConfigUpdateRequest: Codable, Sendable {
    var stage: String?
    var model: String?
    var baseUrl: String?
    var apiKeyEnv: String?
    var apiKey: String?
    var maxTokens: Int?
}

struct VlmacConfig: Codable, Equatable, Sendable {
    var serviceBaseUrl: String?
    var vllmBaseUrl: String?
    var vllmModel: String?
    var vllmApiKeyConfigured: Bool?
    var temperature: Double?
    var maxTokens: Int?
    var timeoutSeconds: Double?
    var configPath: String?
    var envPath: String?
    var envExists: Bool?
    var restartRequired: Bool?

    static let empty = VlmacConfig(
        serviceBaseUrl: nil,
        vllmBaseUrl: nil,
        vllmModel: nil,
        vllmApiKeyConfigured: false,
        temperature: nil,
        maxTokens: nil,
        timeoutSeconds: nil,
        configPath: nil,
        envPath: nil,
        envExists: nil,
        restartRequired: nil
    )
}

struct VlmacConfigUpdateRequest: Codable, Sendable {
    var serviceBaseUrl: String?
    var vllmBaseUrl: String?
    var vllmModel: String?
    var vllmApiKey: String?
    var temperature: Double?
    var maxTokens: Int?
    var timeoutSeconds: Double?
}

struct BasicMemoryEmbeddingConfig: Codable, Equatable, Sendable {
    var configPath: String?
    var configExists: Bool?
    var projectPath: String?
    var defaultProject: String?
    var semanticSearchEnabled: Bool?
    var semanticEmbeddingProvider: String?
    var semanticEmbeddingModel: String?
    var semanticEmbeddingBaseUrl: String?
    var semanticEmbeddingApiKeyEnv: String?
    var semanticEmbeddingApiKeyConfigured: Bool?
    var semanticEmbeddingDimensions: Int?
    var semanticEmbeddingBatchSize: Int?
    var semanticEmbeddingRequestConcurrency: Int?
    var semanticEmbeddingTimeout: Double?
    var restartRequired: Bool?

    static let empty = BasicMemoryEmbeddingConfig(
        configPath: nil,
        configExists: nil,
        projectPath: nil,
        defaultProject: nil,
        semanticSearchEnabled: nil,
        semanticEmbeddingProvider: nil,
        semanticEmbeddingModel: nil,
        semanticEmbeddingBaseUrl: nil,
        semanticEmbeddingApiKeyEnv: nil,
        semanticEmbeddingApiKeyConfigured: false,
        semanticEmbeddingDimensions: nil,
        semanticEmbeddingBatchSize: nil,
        semanticEmbeddingRequestConcurrency: nil,
        semanticEmbeddingTimeout: nil,
        restartRequired: nil
    )
}

struct BasicMemoryEmbeddingConfigUpdateRequest: Codable, Sendable {
    var semanticSearchEnabled: Bool?
    var semanticEmbeddingProvider: String?
    var semanticEmbeddingModel: String?
    var semanticEmbeddingBaseUrl: String?
    var semanticEmbeddingApiKey: String?
    var semanticEmbeddingApiKeyEnv: String?
    var semanticEmbeddingDimensions: Int?
    var semanticEmbeddingBatchSize: Int?
    var semanticEmbeddingRequestConcurrency: Int?
    var semanticEmbeddingTimeout: Double?
}

struct ProjectCortexConfig: Codable, Equatable, Sendable {
    var useReal: Bool?
    var serviceBaseUrl: String?
    var openaiBaseUrl: String?
    var openaiModel: String?
    var openaiApiKeyConfigured: Bool?
    var temperature: Double?
    var maxTokens: Int?
    var timeoutSeconds: Double?
    var configPath: String?
    var configExists: Bool?

    static let empty = ProjectCortexConfig(
        useReal: false,
        serviceBaseUrl: nil,
        openaiBaseUrl: nil,
        openaiModel: nil,
        openaiApiKeyConfigured: false,
        temperature: nil,
        maxTokens: nil,
        timeoutSeconds: nil,
        configPath: nil,
        configExists: nil
    )
}

struct ProjectCortexConfigUpdateRequest: Codable, Sendable {
    var useReal: Bool?
    var serviceBaseUrl: String?
    var openaiBaseUrl: String?
    var openaiModel: String?
    var openaiApiKey: String?
    var temperature: Double?
    var maxTokens: Int?
    var timeoutSeconds: Double?
}

struct RecordingTimeline: Codable, Equatable, Sendable {
    var schemaVersion: Int?
    var source: String?
    var sessionId: String?
    var audioSource: String?
    var micDevice: String?
    var audioPath: String?
    var status: String?
    var recordingStartedAt: String?
    var recordingStopRequestedAt: String?
    var recordingStoppedAt: String?
    var wallDurationSeconds: Double?
    var monotonicDurationSeconds: Double?
    var audioFile: RecordingAudioFile?
    var alignment: RecordingTimelineAlignment?
}

struct RecordingTimelineAlignment: Codable, Equatable, Sendable {
    var offsetSeconds: Double?
    var wallTimeField: String?
    var formula: String?
}

struct RecordingAudioFile: Codable, Equatable, Sendable {
    var fileSizeBytes: Double?
    var durationSeconds: Double?
    var dataFormat: String?
}

struct AiManusConfig: Codable, Equatable, Sendable {
    var enabled: Bool?
    var status: String?
    var model: String?
    var provider: String?
    var baseUrl: String?
    var frontendUrl: String?
    var apiBaseUrl: String?
    var authProvider: String?
    var apiKeyConfigured: Bool?
    var tokenConfigured: Bool?
    var timeoutSeconds: Double?
    var apiBase: String?
    var modelName: String?
    var temperature: Double?
    var maxTokens: Int?
    var extraHeaders: String?
    var extraHeadersConfigured: Bool?
    var envPath: String?
    var envExists: Bool?
    var envSource: String?
    var restartRequired: Bool?
    var clawEnabled: Bool?
    var detail: String?

    static let empty = AiManusConfig(
        enabled: false,
        status: "unavailable",
        model: nil,
        provider: nil,
        baseUrl: nil,
        frontendUrl: nil,
        apiBaseUrl: nil,
        authProvider: nil,
        apiKeyConfigured: false,
        tokenConfigured: false,
        timeoutSeconds: nil,
        apiBase: nil,
        modelName: nil,
        temperature: nil,
        maxTokens: nil,
        extraHeaders: nil,
        extraHeadersConfigured: nil,
        envPath: nil,
        envExists: nil,
        envSource: nil,
        restartRequired: nil,
        clawEnabled: nil,
        detail: nil
    )
}

struct AiManusConfigUpdateRequest: Codable, Sendable {
    var baseUrl: String?
    var frontendUrl: String?
    var authProvider: String?
    var apiKey: String?
    var timeoutSeconds: Double?
    var apiBase: String?
    var modelName: String?
    var temperature: Double?
    var maxTokens: Int?
    var extraHeaders: String?
}

struct AiManusRuntimeCommandRequest: Codable, Sendable {
    var build: Bool?
}

struct AiManusRuntimeCommandResponse: Codable, Sendable {
    var action: String?
    var status: String?
    var detail: String?
    var pid: Int?
    var command: [String]?
    var cwd: String?
    var logPath: String?
    var service: ServiceStatus?
}

struct AiManusRuntimeLogsResponse: Codable, Equatable, Sendable {
    var logPath: String?
    var lines: [String]
    var detail: String?

    static let empty = AiManusRuntimeLogsResponse(logPath: nil, lines: [], detail: nil)
}

struct AiManusStatus: Codable, Equatable, Sendable {
    var ok: Bool?
    var status: String
    var detail: String?
    var config: AiManusConfig?

    static let empty = AiManusStatus(ok: false, status: "unknown", detail: nil, config: nil)
}

struct ManusThread: Identifiable, Codable, Equatable, Sendable {
    var id: String
    var sessionId: String
    var manusSessionId: String?
    var title: String?
    var status: String
    var latestMessage: String?
    var latestMessageAt: Int?
    var unreadMessageCount: Int?
    var isShared: Bool?
    var createdAt: String?
    var updatedAt: String?

    init(
        id: String? = nil,
        sessionId: String,
        manusSessionId: String? = nil,
        title: String?,
        status: String,
        latestMessage: String?,
        latestMessageAt: Int?,
        unreadMessageCount: Int?,
        isShared: Bool?,
        createdAt: String? = nil,
        updatedAt: String? = nil
    ) {
        self.id = id ?? sessionId
        self.sessionId = sessionId
        self.manusSessionId = manusSessionId
        self.title = title
        self.status = status
        self.latestMessage = latestMessage
        self.latestMessageAt = latestMessageAt
        self.unreadMessageCount = unreadMessageCount
        self.isShared = isShared
        self.createdAt = createdAt
        self.updatedAt = updatedAt
    }

    private enum CodingKeys: String, CodingKey {
        case id
        case sessionId
        case manusSessionId
        case title
        case status
        case latestMessage
        case latestMessageAt
        case unreadMessageCount
        case isShared
        case createdAt
        case updatedAt
    }

    init(from decoder: Decoder) throws {
        let container = try decoder.container(keyedBy: CodingKeys.self)
        let sessionId = try container.decode(String.self, forKey: .sessionId)
        self.init(
            id: try container.decodeIfPresent(String.self, forKey: .id),
            sessionId: sessionId,
            manusSessionId: try container.decodeIfPresent(String.self, forKey: .manusSessionId),
            title: try container.decodeIfPresent(String.self, forKey: .title),
            status: try container.decodeIfPresent(String.self, forKey: .status) ?? "unknown",
            latestMessage: try container.decodeIfPresent(String.self, forKey: .latestMessage),
            latestMessageAt: try container.decodeIfPresent(Int.self, forKey: .latestMessageAt),
            unreadMessageCount: try container.decodeIfPresent(Int.self, forKey: .unreadMessageCount),
            isShared: try container.decodeIfPresent(Bool.self, forKey: .isShared),
            createdAt: try container.decodeIfPresent(String.self, forKey: .createdAt),
            updatedAt: try container.decodeIfPresent(String.self, forKey: .updatedAt)
        )
    }
}

struct ManusThreadsResponse: Codable, Equatable, Sendable {
    var sessions: [ManusThread]

    static let empty = ManusThreadsResponse(sessions: [])
}

struct ManusSessionResponse: Codable, Equatable, Sendable {
    var sessionId: String
    var manusSessionId: String?
}

struct ManusThreadDetail: Codable, Equatable, Sendable {
    var sessionId: String
    var manusSessionId: String?
    var title: String?
    var status: String
    var messages: [ManusMessage]?
    var events: [ManusStreamEvent]
    var isShared: Bool?
    var remote: ManusRemoteSession?
    var remoteStatus: String?
    var remoteDetail: String?
    var metadata: [String: JSONValue]?
}

struct ManusRemoteSession: Codable, Equatable, Sendable {
    var sessionId: String?
    var title: String?
    var status: String?
    var filesCount: Int?
    var files: [ManusRemoteFile]?
}

struct ManusRemoteFile: Codable, Equatable, Sendable {
    var name: String?
    var path: String?
    var size: Double?
}

struct ManusSandboxAccess: Codable, Equatable, Sendable {
    var sessionId: String?
    var frontendUrl: String?
    var backendUrl: String?
    var websocketUrl: String?
    var interactiveUrl: String?
    var takeOverUrl: String?
    var status: String?
    var requiresConfirmation: Bool?
    var expiresAt: String?
    var detail: String?
    var metadata: [String: JSONValue]?

    static let empty = ManusSandboxAccess(
        sessionId: nil,
        frontendUrl: nil,
        backendUrl: nil,
        websocketUrl: nil,
        interactiveUrl: nil,
        takeOverUrl: nil,
        status: nil,
        requiresConfirmation: true,
        expiresAt: nil,
        detail: nil,
        metadata: nil
    )

    var interactiveEntryURL: String? {
        if let takeOverUrl, !takeOverUrl.isEmpty {
            return takeOverUrl
        }
        if let interactiveUrl, !interactiveUrl.isEmpty {
            return interactiveUrl
        }
        return nil
    }
}

struct ManusFileInfo: Identifiable, Codable, Equatable, Sendable {
    var fileId: String?
    var remoteId: String?
    var name: String?
    var filename: String?
    var path: String?
    var filePath: String?
    var size: Double?
    var sizeBytes: Double?
    var mimeType: String?
    var contentType: String?
    var fileType: String?
    var type: String?
    var kind: String?
    var isDirectory: Bool?
    var createdAt: String?
    var updatedAt: String?
    var modifiedAt: String?
    var uploadDate: String?
    var fileUrl: String?
    var metadata: [String: JSONValue]?

    var id: String {
        fileIdentifier.isEmpty ? "unknown-file" : fileIdentifier
    }

    var fileIdentifier: String {
        fileId ?? remoteId ?? path ?? filePath ?? name ?? filename ?? ""
    }

    var displayName: String {
        if let name, !name.isEmpty {
            return name
        }
        if let filename, !filename.isEmpty {
            return filename
        }
        if let path, !path.isEmpty {
            return URL(fileURLWithPath: path).lastPathComponent
        }
        if let filePath, !filePath.isEmpty {
            return URL(fileURLWithPath: filePath).lastPathComponent
        }
        return fileIdentifier.isEmpty ? "Untitled file" : fileIdentifier
    }

    var effectiveSize: Double? {
        sizeBytes ?? size
    }

    var typeLabel: String {
        if isDirectory == true {
            return "Folder"
        }
        if let fileType, !fileType.isEmpty {
            return fileType
        }
        if let type, !type.isEmpty {
            return type
        }
        if let kind, !kind.isEmpty {
            return kind
        }
        if let mimeType, !mimeType.isEmpty {
            return mimeType
        }
        if let contentType, !contentType.isEmpty {
            return contentType
        }
        return "File"
    }

    private enum CodingKeys: String, CodingKey {
        case fileId
        case remoteId = "id"
        case name
        case filename
        case path
        case filePath
        case size
        case sizeBytes
        case mimeType
        case contentType
        case fileType
        case type
        case kind
        case isDirectory
        case createdAt
        case updatedAt
        case modifiedAt
        case uploadDate
        case fileUrl
        case metadata
    }
}

struct ManusFilesResponse: Codable, Equatable, Sendable {
    var sessionId: String?
    var files: [ManusFileInfo]
    var count: Int?
    var status: String?
    var detail: String?

    static let empty = ManusFilesResponse(sessionId: nil, files: [], count: nil, status: nil, detail: nil)
}

struct ManusFilePreview: Codable, Equatable, Sendable {
    var fileId: String?
    var name: String?
    var path: String?
    var mimeType: String?
    var fileType: String?
    var content: JSONValue?
    var text: String?
    var previewUrl: String?
    var signedUrl: String?
    var size: Double?
    var truncated: Bool?
    var detail: String?

    var previewText: String? {
        if let text, !text.isEmpty {
            return text
        }
        if case .string(let value)? = content, !value.isEmpty {
            return value
        }
        return content?.compactDescription
    }

    var displayName: String {
        if let name, !name.isEmpty {
            return name
        }
        if let path, !path.isEmpty {
            return URL(fileURLWithPath: path).lastPathComponent
        }
        return fileId ?? "Preview"
    }
}

struct ManusFileDownloadLink: Codable, Equatable, Sendable {
    var fileId: String?
    var url: String
    var expiresAt: String?
    var method: String?
    var headers: [String: JSONValue]?
    var detail: String?

    var downloadURL: URL? {
        URL(string: url)
    }
}

struct ManusMessage: Identifiable, Codable, Equatable, Sendable {
    var id: String
    var role: String
    var content: String
    var timestamp: Int?
    var eventId: String?
    var attachments: [JSONValue]?
}

struct ManusPlanStep: Identifiable, Codable, Equatable, Sendable {
    var id: String
    var description: String
    var status: String
    var timestamp: Int?
    var eventId: String?
}

struct ManusToolEvent: Identifiable, Codable, Equatable, Sendable {
    var toolCallId: String
    var name: String
    var function: String
    var status: String
    var args: [String: JSONValue]
    var content: JSONValue?
    var timestamp: Int?
    var eventId: String?

    var id: String { toolCallId }
}

struct ManusChatRequest: Codable, Sendable {
    var message: String?
    var timestamp: Int?
    var eventId: String?
    var attachments: [JSONValue]?
}

struct ManusStreamEvent: Codable, Equatable, Sendable {
    var event: String
    var data: JSONValue?
}
