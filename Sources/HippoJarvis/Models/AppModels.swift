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
    var currentTask: ActiveTask?
    var skills: [SkillRecord]
    var services: [ServiceStatus]

    static let empty = AppSnapshot(
        jarvisState: .idle,
        statusMessage: "Waiting for task",
        currentSession: nil,
        sopCapture: nil,
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
