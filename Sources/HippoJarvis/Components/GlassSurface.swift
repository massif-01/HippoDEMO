import SwiftUI

struct GlassSurface<Content: View>: View {
    var inset: CGFloat
    let content: Content

    init(inset: CGFloat = 12, @ViewBuilder content: () -> Content) {
        self.inset = inset
        self.content = content()
    }

    var body: some View {
        content
            .padding(inset)
            .background(.regularMaterial, in: RoundedRectangle(cornerRadius: 12, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 12, style: .continuous)
                    .strokeBorder(.white.opacity(0.18), lineWidth: 0.7)
            }
            .shadow(color: .black.opacity(0.12), radius: 18, x: 0, y: 10)
    }
}

enum StatusVisuals {
    static func serviceColor(_ status: String) -> Color {
        switch status {
        case "online": .green
        case "available": .blue
        case "mock": .orange
        case "error": .red
        case "stopped", "idle": .secondary
        default:
            status.contains("error") ? .red : .cyan
        }
    }

    static func serviceIcon(_ status: String) -> String {
        switch status {
        case "online": "checkmark.circle.fill"
        case "available": "checkmark.circle"
        case "stopped": "stop.circle"
        case "mock": "wand.and.stars"
        case "error": "exclamationmark.triangle.fill"
        default: "circle.dashed"
        }
    }

    static func jarvisColor(_ state: JarvisState) -> Color {
        switch state {
        case .idle: .secondary
        case .meetingActive: .cyan
        case .sopMarking, .sopGenerating: .orange
        case .activeTaskCandidate, .taskSurfaceDetected, .taskExecuting: .blue
        case .taskReviewing, .patternDetected: .green
        case .paused: .yellow
        case .thinking: .purple
        case .error: .red
        }
    }
}

struct HUDSection<Content: View>: View {
    let title: String?
    var systemImage: String?
    let content: Content

    init(_ title: String? = nil, systemImage: String? = nil, @ViewBuilder content: () -> Content) {
        self.title = title
        self.systemImage = systemImage
        self.content = content()
    }

    var body: some View {
        GlassSurface(inset: 12) {
            VStack(alignment: .leading, spacing: 10) {
                if let title {
                    HStack(spacing: 7) {
                        if let systemImage {
                            Image(systemName: systemImage)
                        }
                        Text(title)
                    }
                    .font(.system(size: 11, weight: .bold, design: .rounded))
                    .foregroundStyle(.secondary)
                    .textCase(.uppercase)
                    .tracking(0.8)
                }
                content
            }
        }
    }
}

struct ServiceLight: View {
    let service: ServiceStatus
    var title: String? = nil
    var detail: String? = nil
    var compact = false

    private var color: Color {
        StatusVisuals.serviceColor(service.status)
    }

    var body: some View {
        HStack(spacing: compact ? 6 : 8) {
            ZStack {
                Circle()
                    .fill(color.opacity(0.13))
                Circle()
                    .fill(color)
                    .frame(width: compact ? 6 : 8, height: compact ? 6 : 8)
            }
            .frame(width: compact ? 18 : 24, height: compact ? 18 : 24)

            VStack(alignment: .leading, spacing: 1) {
                Text(title ?? service.name)
                    .font(.system(size: compact ? 10 : 12, weight: .semibold, design: .rounded))
                    .lineLimit(1)
                if !compact, let detail {
                    Text(detail)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                        .lineLimit(1)
                }
            }
        }
        .foregroundStyle(.primary)
    }
}

struct SignalMetric: View {
    let title: String
    let value: String
    let systemImage: String
    var color: Color = .cyan

    var body: some View {
        VStack(alignment: .leading, spacing: 7) {
            HStack(spacing: 5) {
                Image(systemName: systemImage)
                Text(title)
            }
            .font(.system(size: 10, weight: .medium))
            .foregroundStyle(.secondary)

            Text(value)
                .font(.system(size: 15, weight: .semibold, design: .rounded))
                .foregroundStyle(color)
                .lineLimit(1)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(10)
        .background(.thinMaterial, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .strokeBorder(color.opacity(0.18), lineWidth: 0.7)
        }
    }
}

struct TimelineRow: View {
    let event: EventRecord
    var color: Color = .cyan

    var body: some View {
        HStack(alignment: .top, spacing: 12) {
            VStack(spacing: 0) {
                Circle()
                    .fill(color)
                    .frame(width: 9, height: 9)
                Rectangle()
                    .fill(color.opacity(0.20))
                    .frame(width: 1)
            }
            .frame(width: 16)

            VStack(alignment: .leading, spacing: 4) {
                HStack(spacing: 8) {
                    Text(eventTitle)
                        .font(.system(size: 13, weight: .semibold, design: .rounded))
                        .lineLimit(1)
                    Text(formattedTime)
                        .font(.caption2)
                        .foregroundStyle(.secondary)
                }

                Text(detailText)
                    .font(.caption)
                    .foregroundStyle(.secondary)
                    .lineLimit(2)
            }

            Spacer(minLength: 0)
        }
        .frame(minHeight: 44, alignment: .top)
    }

    private var eventTitle: String {
        event.type.replacingOccurrences(of: "_", with: " ").capitalized
    }

    private var detailText: String {
        if let action = event.payload["action"]?.compactDescription {
            return action
        }
        if let status = event.payload["status"]?.compactDescription {
            return status
        }
        if let service = event.payload["service"] {
            return service.compactDescription
        }
        if let sessionId = event.sessionId {
            return "session \(String(sessionId.prefix(8)))"
        }
        return event.payload.keys.sorted().prefix(3).joined(separator: " / ")
    }

    private var formattedTime: String {
        guard let date = ISO8601DateFormatter().date(from: event.timestamp) else {
            return event.timestamp
        }
        return date.formatted(date: .omitted, time: .shortened)
    }
}

struct ArtifactBadge: View {
    let title: String
    let systemImage: String
    var color: Color = .cyan

    var body: some View {
        Label(title, systemImage: systemImage)
            .font(.caption)
            .foregroundStyle(color)
            .padding(.horizontal, 9)
            .padding(.vertical, 5)
            .background(color.opacity(0.10), in: Capsule())
            .overlay {
                Capsule()
                    .strokeBorder(color.opacity(0.22), lineWidth: 0.7)
            }
    }
}

struct JarvisActionButton: View {
    enum Tone {
        case primary
        case quiet
        case amber
        case destructive
    }

    let title: String
    let systemImage: String
    var tone: Tone = .quiet
    var action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 8) {
                Image(systemName: systemImage)
                    .font(.system(size: 13, weight: .semibold))
                    .frame(width: 16)
                Text(title)
                    .font(.system(size: 13, weight: .semibold))
                    .lineLimit(1)
                Spacer(minLength: 0)
            }
            .frame(maxWidth: .infinity)
            .padding(.horizontal, 12)
            .padding(.vertical, 9)
            .contentShape(RoundedRectangle(cornerRadius: 10, style: .continuous))
        }
        .buttonStyle(.plain)
        .foregroundStyle(foreground)
        .background(background, in: RoundedRectangle(cornerRadius: 10, style: .continuous))
        .overlay {
            RoundedRectangle(cornerRadius: 10, style: .continuous)
                .strokeBorder(border, lineWidth: 0.7)
        }
    }

    private var foreground: Color {
        switch tone {
        case .primary: .white
        case .amber: .white
        case .destructive: .red
        case .quiet: .primary
        }
    }

    private var background: AnyShapeStyle {
        switch tone {
        case .primary:
            AnyShapeStyle(LinearGradient(colors: [.cyan.opacity(0.86), .blue.opacity(0.78)], startPoint: .topLeading, endPoint: .bottomTrailing))
        case .amber:
            AnyShapeStyle(LinearGradient(colors: [.orange.opacity(0.88), .yellow.opacity(0.72)], startPoint: .topLeading, endPoint: .bottomTrailing))
        case .destructive:
            AnyShapeStyle(.red.opacity(0.08))
        case .quiet:
            AnyShapeStyle(.thinMaterial)
        }
    }

    private var border: Color {
        switch tone {
        case .primary: .white.opacity(0.22)
        case .amber: .white.opacity(0.28)
        case .destructive: .red.opacity(0.22)
        case .quiet: .white.opacity(0.18)
        }
    }
}

struct StatusPulse: View {
    let color: Color
    let systemImage: String
    let isActive: Bool

    var body: some View {
        TimelineView(.animation) { timeline in
            let phase = timeline.date.timeIntervalSinceReferenceDate
            let pulse = isActive ? (sin(phase * 2.3) + 1) / 2 : 0

            ZStack {
                Circle()
                    .stroke(color.opacity(0.18 + pulse * 0.22), lineWidth: 1.5)
                    .frame(width: 72 + pulse * 8, height: 72 + pulse * 8)

                Circle()
                    .fill(.thinMaterial)
                    .frame(width: 62, height: 62)
                    .overlay {
                        Circle()
                            .strokeBorder(color.opacity(0.42), lineWidth: 1)
                    }

                Image(systemName: systemImage)
                    .font(.system(size: 26, weight: .semibold))
                    .symbolRenderingMode(.hierarchical)
                    .foregroundStyle(color)
            }
            .frame(width: 84, height: 84)
        }
    }
}
