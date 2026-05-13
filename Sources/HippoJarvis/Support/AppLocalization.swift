import Foundation

enum AppLanguage: String, CaseIterable, Identifiable {
    case english = "en"
    case simplifiedChinese = "zh-Hans"

    var id: String { rawValue }

    var displayName: String {
        switch self {
        case .english:
            "English"
        case .simplifiedChinese:
            "中文"
        }
    }

    static var defaultLanguage: AppLanguage {
        let preferred = Locale.preferredLanguages.first ?? ""
        return preferred.hasPrefix("zh") ? .simplifiedChinese : .english
    }
}

enum AppCopyKey {
    case activity
    case activityCenter
    case activeTaskReadyDescription
    case accessibility
    case artifactContent
    case artifactVault
    case artifacts
    case audioCapture
    case audioDevices
    case audioSource
    case apiKeyConfigured
    case apiKeyMissing
    case asrApiKey
    case asrBaseURL
    case asrModel
    case backendServices
    case baseURL
    case captureSkill
    case captureOnce
    case confidence
    case cuaDriverControls
    case current
    case currentSignal
    case cancel
    case created
    case delete
    case deleteSkill
    case deleteSkillQuestion
    case developerConsole
    case environmentSignals
    case events
    case finishCapture
    case format
    case generateSkill
    case generatedBy
    case health
    case ignore
    case insert
    case insertToCurrentTask
    case integrations
    case jarvisOff
    case jarvisOn
    case jarvisSettings
    case language
    case library
    case markComplete
    case markdownPreview
    case microphone
    case micOnly
    case mode
    case noEvents
    case noActiveTask
    case noActiveTaskDescription
    case noDetailsReported
    case noSkillSearch
    case noSkills
    case noSkillsDescription
    case notReported
    case operations
    case openChronicleControls
    case orchestrator
    case pause
    case permissions
    case preflight
    case primaryAction
    case proposedActions
    case readOnly
    case refresh
    case refreshState
    case rebuildCapturesIndex
    case recordingTimeline
    case resume
    case restart
    case runPreflight
    case runtime
    case runtimeProvider
    case saveProvider
    case screenRecording
    case searchSkills
    case service
    case serviceMatrix
    case serviceSignals
    case services
    case signal
    case size
    case skillArtifact
    case skills
    case source
    case start
    case state
    case stop
    case summaryApiKey
    case summaryBaseURL
    case summaryConfigured
    case summaryMissing
    case summaryModel
    case systemAndMic
    case systemAudio
    case task
    case taskCandidate
    case targetBlocked
    case targetReady
    case targetSurface
    case timeline
    case timelineTick
    case selectedMicrophone
    case wallClockAlignment
    case keyStoredLocally
}

enum AppCopy {
    static func text(_ key: AppCopyKey, language: AppLanguage) -> String {
        switch language {
        case .english:
            english[key] ?? ""
        case .simplifiedChinese:
            chinese[key] ?? english[key] ?? ""
        }
    }

    static func statusTitle(_ state: JarvisState, language: AppLanguage) -> String {
        switch language {
        case .english:
            switch state {
            case .idle: "Waiting for task"
            case .meetingActive: "Jarvis is listening"
            case .paused: "Jarvis paused"
            case .sopMarking: "Capturing skill"
            case .sopGenerating: "Generating Skill..."
            case .thinking: "Thinking"
            case .activeTaskCandidate, .taskSurfaceDetected: "Ready to Act"
            case .taskExecuting: "Acting"
            case .taskReviewing: "Waiting for Review"
            case .patternDetected: "Reusable pattern found"
            case .error: "Needs attention"
            }
        case .simplifiedChinese:
            switch state {
            case .idle: "等待任务"
            case .meetingActive: "Jarvis 正在聆听"
            case .paused: "Jarvis 已暂停"
            case .sopMarking: "正在标记 Skill"
            case .sopGenerating: "正在生成 Skill..."
            case .thinking: "正在思考"
            case .activeTaskCandidate, .taskSurfaceDetected: "可以介入"
            case .taskExecuting: "正在执行"
            case .taskReviewing: "等待你审核"
            case .patternDetected: "发现可复用模式"
            case .error: "需要处理"
            }
        }
    }

    static func shortStateLabel(_ state: JarvisState, language: AppLanguage) -> String {
        switch language {
        case .english:
            switch state {
            case .idle: "STANDBY"
            case .meetingActive: "LIVE"
            case .sopMarking: "CAPTURE"
            case .sopGenerating: "SKILL"
            case .activeTaskCandidate, .taskSurfaceDetected: "READY"
            case .taskExecuting: "ACTING"
            case .taskReviewing: "REVIEW"
            case .patternDetected: "PATTERN"
            case .paused: "PAUSED"
            case .thinking: "THINKING"
            case .error: "CHECK"
            }
        case .simplifiedChinese:
            switch state {
            case .idle: "待命"
            case .meetingActive: "监听中"
            case .sopMarking: "标记中"
            case .sopGenerating: "生成中"
            case .activeTaskCandidate, .taskSurfaceDetected: "可介入"
            case .taskExecuting: "执行中"
            case .taskReviewing: "审核中"
            case .patternDetected: "可沉淀"
            case .paused: "暂停"
            case .thinking: "思考中"
            case .error: "检查"
            }
        }
    }

    static func stateName(_ state: JarvisState, language: AppLanguage) -> String {
        switch language {
        case .english:
            state.rawValue.replacingOccurrences(of: "_", with: " ")
        case .simplifiedChinese:
            switch state {
            case .idle: "待命"
            case .meetingActive: "会议监听"
            case .paused: "暂停"
            case .sopMarking: "Skill 标记"
            case .sopGenerating: "Skill 生成"
            case .thinking: "思考"
            case .activeTaskCandidate: "任务候选"
            case .taskSurfaceDetected: "发现任务界面"
            case .taskExecuting: "执行"
            case .taskReviewing: "审核"
            case .patternDetected: "发现模式"
            case .error: "错误"
            }
        }
    }

    static func statusMessage(_ message: String, state: JarvisState, language: AppLanguage) -> String {
        guard language == .simplifiedChinese else {
            return message
        }

        switch message {
        case "Waiting for task":
            return "等待任务"
        case "Listening to meeting, screen, and context":
            return "正在监听会议、屏幕和上下文"
        case "Jarvis paused":
            return "Jarvis 已暂停"
        case "Capture Skill is active":
            return "正在记录可沉淀的 Skill 片段"
        case "Generating Skill...":
            return "正在生成 Skill..."
        case "Ready to Act":
            return "已准备好介入当前任务"
        case "Inserted content is waiting for your review":
            return "内容已插入，等待你审核"
        case "Reusable pattern detected":
            return "已识别到可复用模式"
        case "Jarvis is ready":
            return "Jarvis 已就绪"
        default:
            return statusTitle(state, language: language)
        }
    }

    static func permissionDetail(_ key: AppCopyKey, language: AppLanguage) -> String {
        switch (key, language) {
        case (.microphone, .english):
            "Used while Jarvis listens for meeting context"
        case (.microphone, .simplifiedChinese):
            "用于 Jarvis 监听会议上下文"
        case (.screenRecording, .english):
            "Allows task-surface detection on screen"
        case (.screenRecording, .simplifiedChinese):
            "用于识别屏幕上的任务界面"
        case (.accessibility, .english):
            "Required for assisted insertion and app control"
        case (.accessibility, .simplifiedChinese):
            "用于辅助插入内容和控制应用"
        default:
            ""
        }
    }

    static func serviceStatus(_ status: String, language: AppLanguage) -> String {
        guard language == .simplifiedChinese else {
            return status.capitalized
        }

        return switch status {
        case "online": "在线"
        case "available": "可用"
        case "stopped": "已停止"
        case "mock": "占位"
        case "error": "错误"
        case "idle": "待命"
        case "unknown": "未知"
        default: status
        }
    }

    static func serviceDetail(_ detail: String?, status: String, language: AppLanguage) -> String {
        let fallback = serviceStatus(status, language: language)
        guard let detail, !detail.isEmpty else {
            return fallback
        }
        guard language == .simplifiedChinese else {
            return detail
        }

        switch detail {
        case "audio recording/transcription placeholder":
            return "录音和转写能力占位"
        case "video capture placeholder":
            return "视频采集能力占位"
        case "context timeline placeholder":
            return "上下文时间线能力占位"
        case "manual-confirmed insertion placeholder":
            return "人工确认插入能力占位"
        case "/api/sop_generator adapter disabled by default":
            return "/api/sop_generator 适配器默认关闭"
        default:
            return detail
        }
    }

    private static let english: [AppCopyKey: String] = [
        .activity: "Activity",
        .activityCenter: "Activity Center",
        .activeTaskReadyDescription: "Prepared content is ready for the current task surface.",
        .accessibility: "Accessibility",
        .artifactContent: "Artifact Content",
        .artifactVault: "Artifact Vault",
        .artifacts: "Artifacts",
        .audioCapture: "Audio Capture",
        .audioDevices: "Audio Devices",
        .audioSource: "Audio Source",
        .apiKeyConfigured: "ASR key set",
        .apiKeyMissing: "ASR key missing",
        .asrApiKey: "ASR API Key",
        .asrBaseURL: "ASR Base URL",
        .asrModel: "ASR Model",
        .backendServices: "Backend Services",
        .baseURL: "Base URL",
        .captureSkill: "Capture Skill",
        .captureOnce: "Capture Once",
        .confidence: "confidence",
        .cuaDriverControls: "cua-driver Controls",
        .current: "Current",
        .currentSignal: "Current Signal",
        .cancel: "Cancel",
        .created: "Created",
        .delete: "Delete",
        .deleteSkill: "Delete Skill",
        .deleteSkillQuestion: "Delete Skill?",
        .developerConsole: "Developer Console",
        .environmentSignals: "Environment Signals",
        .events: "Events",
        .finishCapture: "Finish Capture",
        .format: "Format",
        .generateSkill: "Generate Skill",
        .generatedBy: "Generated by",
        .health: "Health",
        .ignore: "Ignore",
        .insert: "Insert",
        .insertToCurrentTask: "Insert to Current Task",
        .integrations: "Integrations",
        .jarvisOff: "Jarvis OFF",
        .jarvisOn: "Jarvis ON",
        .jarvisSettings: "Jarvis Settings",
        .language: "Language",
        .library: "Library",
        .markComplete: "Mark Complete",
        .markdownPreview: "Markdown Preview",
        .microphone: "Microphone",
        .micOnly: "Mic Only",
        .mode: "Mode",
        .noActiveTask: "No active task",
        .noActiveTaskDescription: "Jarvis will surface task candidates and review actions here when a signal is detected.",
        .noEvents: "No events yet",
        .noDetailsReported: "No details reported",
        .noSkillSearch: "No skill artifact matches the current search.",
        .noSkills: "No Skills",
        .noSkillsDescription: "Captured skill artifacts will appear here.",
        .notReported: "Not reported",
        .operations: "Operations",
        .openChronicleControls: "OpenChronicle Controls",
        .orchestrator: "Orchestrator",
        .pause: "Pause",
        .permissions: "Permissions",
        .preflight: "Preflight",
        .primaryAction: "Primary Action",
        .proposedActions: "Proposed Actions",
        .readOnly: "Read only",
        .refresh: "Refresh",
        .refreshState: "Refresh State",
        .rebuildCapturesIndex: "Rebuild Captures Index",
        .recordingTimeline: "Recording Timeline",
        .resume: "Resume",
        .restart: "Restart",
        .runPreflight: "Run Preflight",
        .runtime: "Runtime",
        .runtimeProvider: "Runtime Provider",
        .saveProvider: "Save Provider",
        .screenRecording: "Screen Recording",
        .searchSkills: "Search skills",
        .service: "Service",
        .serviceMatrix: "Service Matrix",
        .serviceSignals: "Service Signals",
        .services: "Services",
        .signal: "SIGNAL",
        .size: "Size",
        .skillArtifact: "SKILL ARTIFACT",
        .skills: "Skills",
        .source: "Source",
        .start: "Start",
        .state: "State",
        .stop: "Stop",
        .summaryApiKey: "Summary API Key",
        .summaryBaseURL: "Summary Base URL",
        .summaryConfigured: "Summary key set",
        .summaryMissing: "Summary key missing",
        .summaryModel: "Summary Model",
        .systemAndMic: "System + Mic",
        .systemAudio: "System Audio",
        .task: "Task",
        .taskCandidate: "Task Candidate",
        .targetBlocked: "Target blocked",
        .targetReady: "Target ready",
        .targetSurface: "Target Surface",
        .timeline: "Timeline",
        .timelineTick: "Timeline Tick",
        .selectedMicrophone: "Selected Microphone",
        .wallClockAlignment: "Wall-clock Alignment",
        .keyStoredLocally: "Keys are stored in the ignored local .runtime provider file, not Keychain.",
    ]

    private static let chinese: [AppCopyKey: String] = [
        .activity: "活动",
        .activityCenter: "活动中心",
        .activeTaskReadyDescription: "已为当前任务界面准备好内容。",
        .accessibility: "辅助功能",
        .artifactContent: "产物内容",
        .artifactVault: "产物库",
        .artifacts: "产物",
        .audioCapture: "音频采集",
        .audioDevices: "音频设备",
        .audioSource: "音频源",
        .apiKeyConfigured: "ASR key 已配置",
        .apiKeyMissing: "ASR key 未配置",
        .asrApiKey: "ASR API Key",
        .asrBaseURL: "ASR Base URL",
        .asrModel: "ASR 模型",
        .backendServices: "后端服务",
        .baseURL: "服务地址",
        .captureSkill: "标记 Skill",
        .captureOnce: "采集一次",
        .confidence: "置信度",
        .cuaDriverControls: "cua-driver 控制",
        .current: "当前",
        .currentSignal: "当前信号",
        .cancel: "取消",
        .created: "创建于",
        .delete: "删除",
        .deleteSkill: "删除 Skill",
        .deleteSkillQuestion: "删除 Skill？",
        .developerConsole: "开发者控制台",
        .environmentSignals: "环境信号",
        .events: "事件",
        .finishCapture: "完成标记",
        .format: "格式",
        .generateSkill: "生成 Skill",
        .generatedBy: "生成来源",
        .health: "健康状态",
        .ignore: "忽略",
        .insert: "插入",
        .insertToCurrentTask: "插入到当前任务",
        .integrations: "集成",
        .jarvisOff: "Jarvis 关闭",
        .jarvisOn: "Jarvis 启动",
        .jarvisSettings: "Jarvis 设置",
        .language: "语言",
        .library: "库",
        .markComplete: "标记完成",
        .markdownPreview: "Markdown 预览",
        .microphone: "麦克风",
        .micOnly: "仅麦克风",
        .mode: "模式",
        .noActiveTask: "暂无活动任务",
        .noActiveTaskDescription: "当检测到可介入信号时，Jarvis 会在这里展示任务候选和审核动作。",
        .noEvents: "暂无事件",
        .noDetailsReported: "暂无详情",
        .noSkillSearch: "没有匹配当前搜索的 Skill 产物。",
        .noSkills: "暂无 Skill",
        .noSkillsDescription: "沉淀后的 Skill 产物会显示在这里。",
        .notReported: "未上报",
        .operations: "操作",
        .openChronicleControls: "OpenChronicle 控制",
        .orchestrator: "Orchestrator",
        .pause: "暂停",
        .permissions: "权限",
        .preflight: "预检",
        .primaryAction: "主动作",
        .proposedActions: "建议动作",
        .readOnly: "只读",
        .refresh: "刷新",
        .refreshState: "刷新状态",
        .rebuildCapturesIndex: "重建采集索引",
        .recordingTimeline: "录音时间轴",
        .resume: "继续",
        .restart: "重启",
        .runPreflight: "运行预检",
        .runtime: "运行",
        .runtimeProvider: "运行时 Provider",
        .saveProvider: "保存 Provider",
        .screenRecording: "屏幕录制",
        .searchSkills: "搜索 Skill",
        .service: "服务",
        .serviceMatrix: "服务矩阵",
        .serviceSignals: "服务信号",
        .services: "服务",
        .signal: "信号",
        .size: "大小",
        .skillArtifact: "SKILL 产物",
        .skills: "Skills",
        .source: "来源",
        .start: "启动",
        .state: "状态",
        .stop: "停止",
        .summaryApiKey: "总结 API Key",
        .summaryBaseURL: "总结 Base URL",
        .summaryConfigured: "总结 key 已配置",
        .summaryMissing: "总结 key 未配置",
        .summaryModel: "总结模型",
        .systemAndMic: "系统声 + 麦克风",
        .systemAudio: "系统声音",
        .task: "任务",
        .taskCandidate: "任务候选",
        .targetBlocked: "目标已拦截",
        .targetReady: "目标就绪",
        .targetSurface: "目标界面",
        .timeline: "时间线",
        .timelineTick: "推进时间线",
        .selectedMicrophone: "已选麦克风",
        .wallClockAlignment: "真实时间对齐",
        .keyStoredLocally: "Key 存在本地 ignored 的 .runtime provider 文件，不进 Keychain。",
    ]
}
