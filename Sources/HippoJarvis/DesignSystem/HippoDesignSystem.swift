import AppKit
import SwiftUI

enum HippoTheme {
    static let preferredBlue = Color(red: 13 / 255, green: 111 / 255, blue: 255 / 255)
    static let sidebarSelected = Color(nsColor: NSColor(name: nil) { appearance in
        appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
            ? NSColor(white: 1, alpha: 0.14)
            : NSColor(white: 0, alpha: 0.11)
    })
    static let subtleFill = Color(nsColor: NSColor(name: nil) { appearance in
        appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
            ? NSColor(white: 1, alpha: 0.08)
            : NSColor(white: 0, alpha: 0.04)
    })
    static let panelFill = Color(nsColor: NSColor(name: nil) { appearance in
        appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
            ? NSColor(white: 1, alpha: 0.10)
            : NSColor(white: 1, alpha: 0.68)
    })
    static let hairline = Color(nsColor: NSColor(name: nil) { appearance in
        appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
            ? NSColor(white: 1, alpha: 0.12)
            : NSColor(white: 0, alpha: 0.08)
    })
    static let segmentedBackground = Color(nsColor: NSColor(name: nil) { appearance in
        appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
            ? NSColor(white: 1, alpha: 0.08)
            : NSColor(white: 0, alpha: 0.05)
    })

    static func stateColor(_ status: String) -> Color {
        switch status {
        case "online", "recording", "ready", "available":
            .green
        case "mock", "warning":
            .orange
        case "error", "unavailable":
            .red
        case "stopped", "idle":
            .secondary
        default:
            status.localizedCaseInsensitiveContains("error") ? .red : .blue
        }
    }
}

struct HippoHairline: View {
    var body: some View {
        Rectangle()
            .fill(Color(nsColor: .separatorColor).opacity(0.6))
            .frame(height: 0.5)
    }
}

struct HippoVHairline: View {
    var body: some View {
        Rectangle()
            .fill(Color(nsColor: .separatorColor).opacity(0.6))
            .frame(width: 0.5)
            .padding(.vertical, 4)
    }
}

struct HippoGlyphView: View {
    var size: CGFloat = 16
    var foreground: Color?

    var body: some View {
        ZStack {
            HippoHeadShape()
                .fill(
                    foreground.map { AnyShapeStyle($0) }
                        ?? AnyShapeStyle(LinearGradient(
                            colors: [.orange, .red],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        ))
                )

            Circle()
                .fill(.white.opacity(0.96))
                .frame(width: size * 0.075, height: size * 0.075)
                .offset(x: -size * 0.10, y: -size * 0.06)

            Circle()
                .fill(.white.opacity(0.96))
                .frame(width: size * 0.075, height: size * 0.075)
                .offset(x: size * 0.14, y: -size * 0.06)
        }
        .frame(width: size, height: size)
        .accessibilityHidden(true)
    }
}

private struct HippoHeadShape: Shape {
    func path(in rect: CGRect) -> Path {
        func p(_ x: CGFloat, _ y: CGFloat) -> CGPoint {
            CGPoint(x: rect.minX + rect.width * x / 24, y: rect.minY + rect.height * y / 24)
        }

        var path = Path()
        path.move(to: p(5, 13))
        path.addCurve(to: p(12, 6.5), control1: p(5, 9.6), control2: p(8.1, 6.5))
        path.addCurve(to: p(19, 13), control1: p(15.9, 6.5), control2: p(19, 9.6))
        path.addLine(to: p(19, 16))
        path.addCurve(to: p(17, 18), control1: p(19, 17.1), control2: p(18.1, 18))
        path.addLine(to: p(14.8, 18))
        path.addCurve(to: p(14, 17.2), control1: p(14.35, 18), control2: p(14, 17.65))
        path.addLine(to: p(14, 16.6))
        path.addCurve(to: p(11, 14), control1: p(14, 15.2), control2: p(12.7, 14))
        path.addCurve(to: p(8, 16.6), control1: p(9.3, 14), control2: p(8, 15.2))
        path.addLine(to: p(8, 17.2))
        path.addCurve(to: p(7.2, 18), control1: p(8, 17.65), control2: p(7.65, 18))
        path.addLine(to: p(4.5, 18))
        path.addCurve(to: p(4, 17.5), control1: p(4.2, 18), control2: p(4, 17.8))
        path.addLine(to: p(4, 17))
        path.addCurve(to: p(5, 13), control1: p(4, 15), control2: p(4.4, 14))
        path.closeSubpath()
        return path
    }
}

struct HippoTile: View {
    var size: CGFloat = 28

    var body: some View {
        RoundedRectangle(cornerRadius: size * 0.25, style: .continuous)
            .fill(LinearGradient(colors: [.orange.opacity(0.90), .red.opacity(0.86)], startPoint: .topLeading, endPoint: .bottomTrailing))
            .overlay {
                HippoGlyphView(size: size * 0.64, foreground: .white)
            }
            .overlay {
                RoundedRectangle(cornerRadius: size * 0.25, style: .continuous)
                    .strokeBorder(.white.opacity(0.35), lineWidth: 0.5)
            }
            .frame(width: size, height: size)
    }
}

struct HippoStatusDot: View {
    var color: Color
    var pulse = false
    var size: CGFloat = 6
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    @State private var active = false

    var body: some View {
        Circle()
            .fill(color)
            .frame(width: size, height: size)
            .scaleEffect(pulse && active && !reduceMotion ? 1.35 : 1)
            .opacity(pulse && active && !reduceMotion ? 0.72 : 1)
            .shadow(color: pulse ? color.opacity(0.55) : .clear, radius: 4)
            .onAppear {
                guard pulse, !reduceMotion else { return }
                withAnimation(.easeInOut(duration: 0.8).repeatForever(autoreverses: true)) {
                    active = true
                }
            }
            .accessibilityHidden(true)
    }
}

struct HippoWaveform: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        TimelineView(.animation) { timeline in
            let t = reduceMotion ? 0 : timeline.date.timeIntervalSinceReferenceDate
            HStack(alignment: .center, spacing: 2.5) {
                ForEach(0..<13, id: \.self) { index in
                    let value = (sin(t * 5 + Double(index) * 0.7) + 1) * 12 + 6
                    Capsule()
                        .fill(LinearGradient(colors: [.red, .orange], startPoint: .top, endPoint: .bottom))
                        .frame(width: 2.5, height: reduceMotion ? 14 : value)
                }
            }
            .frame(width: 62, height: 34)
        }
        .accessibilityLabel("Recording waveform")
    }
}

enum HippoPushVariant {
    case preferred
    case destructive
    case stop
    case neutral
    case glass
    case plain
}

enum HippoPushSize {
    case sm
    case md
    case lg

    var height: CGFloat {
        switch self {
        case .sm: 20
        case .md: 24
        case .lg: 28
        }
    }

    var horizontalPadding: CGFloat {
        switch self {
        case .sm: 10
        case .md: 16
        case .lg: 18
        }
    }

    var fontSize: CGFloat {
        switch self {
        case .sm: 12
        case .md: 13
        case .lg: 14
        }
    }
}

struct HippoPushButtonStyle: ButtonStyle {
    var variant: HippoPushVariant
    var size: HippoPushSize
    var fullWidth: Bool

    init(_ variant: HippoPushVariant = .neutral, size: HippoPushSize = .md, fullWidth: Bool = false) {
        self.variant = variant
        self.size = size
        self.fullWidth = fullWidth
    }

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(.system(size: size.fontSize, weight: .medium))
            .lineLimit(1)
            .padding(.horizontal, size.horizontalPadding)
            .frame(maxWidth: fullWidth ? .infinity : nil)
            .frame(height: size.height)
            .foregroundStyle(foreground)
            .background(background.opacity(configuration.isPressed ? 0.82 : 1), in: RoundedRectangle(cornerRadius: 6, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: 6, style: .continuous)
                    .strokeBorder(border, lineWidth: variant == .plain ? 0 : 0.5)
            }
            .shadow(color: shadow, radius: 1.5, y: 1)
            .opacity(configuration.isPressed ? 0.85 : 1)
            .animation(.easeOut(duration: 0.08), value: configuration.isPressed)
    }

    private var foreground: Color {
        switch variant {
        case .preferred, .stop:
            .white
        case .destructive:
            .red
        case .neutral, .glass, .plain:
            .primary
        }
    }

    private var background: Color {
        switch variant {
        case .preferred:
            HippoTheme.preferredBlue
        case .stop:
            .red
        case .destructive, .neutral:
            Color(nsColor: .controlBackgroundColor).opacity(0.92)
        case .glass:
            .white.opacity(0.48)
        case .plain:
            .clear
        }
    }

    private var border: Color {
        switch variant {
        case .plain:
            .clear
        case .stop, .preferred:
            .black.opacity(0.10)
        default:
            HippoTheme.hairline
        }
    }

    private var shadow: Color {
        switch variant {
        case .preferred, .stop, .destructive, .neutral:
            .black.opacity(0.06)
        case .glass, .plain:
            .clear
        }
    }
}

extension ButtonStyle where Self == HippoPushButtonStyle {
    static var hippoNeutral: HippoPushButtonStyle { HippoPushButtonStyle(.neutral) }
    static var hippoPreferred: HippoPushButtonStyle { HippoPushButtonStyle(.preferred) }
    static var hippoStop: HippoPushButtonStyle { HippoPushButtonStyle(.stop) }
}

struct HippoSymbolButton: View {
    let systemName: String
    var title: String
    var size: CGFloat = 28
    var active = false
    var action: () -> Void

    var body: some View {
        Button(action: action) {
            Image(systemName: systemName)
                .font(.system(size: 13, weight: .medium))
                .frame(width: size, height: size)
        }
        .buttonStyle(.plain)
        .foregroundStyle(active ? Color.accentColor : .secondary)
        .background(active ? HippoTheme.sidebarSelected : .clear, in: RoundedRectangle(cornerRadius: 7, style: .continuous))
        .accessibilityLabel(title)
        .help(title)
    }
}

struct HippoMetadataCell: View {
    let label: String
    let value: String
    var mono = false
    var muted = false

    var body: some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(label.uppercased())
                .font(.system(size: 10, weight: .semibold))
                .tracking(0.4)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.system(size: 14, weight: .semibold, design: mono ? .monospaced : .default))
                .foregroundStyle(muted ? .secondary : .primary)
                .lineLimit(1)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 16)
    }
}

struct HippoCapsuleLabel: View {
    let title: String
    var color: Color = .blue
    var systemImage: String?

    var body: some View {
        Label {
            Text(title)
        } icon: {
            if let systemImage {
                Image(systemName: systemImage)
            }
        }
        .font(.system(size: 11, weight: .semibold))
        .foregroundStyle(color)
        .padding(.horizontal, 8)
        .padding(.vertical, 2)
        .background(color.opacity(0.14), in: Capsule())
    }
}

struct HippoInsetPanel<Content: View>: View {
    var radius: CGFloat = 10
    let content: Content

    init(radius: CGFloat = 10, @ViewBuilder content: () -> Content) {
        self.radius = radius
        self.content = content()
    }

    var body: some View {
        content
            .background(HippoTheme.panelFill, in: RoundedRectangle(cornerRadius: radius, style: .continuous))
            .overlay {
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .strokeBorder(HippoTheme.hairline, lineWidth: 0.5)
            }
    }
}

extension String {
    var hippoTitleCasedEvent: String {
        replacingOccurrences(of: "_", with: " ").capitalized
    }
}

struct HippoFlowLayout: Layout {
    var spacing: CGFloat = 8

    func sizeThatFits(proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) -> CGSize {
        let width = proposal.width ?? 400
        return layout(in: width, subviews: subviews).size
    }

    func placeSubviews(in bounds: CGRect, proposal: ProposedViewSize, subviews: Subviews, cache: inout ()) {
        let rows = layout(in: bounds.width, subviews: subviews).rows
        var y = bounds.minY

        for row in rows {
            var x = bounds.minX + max(0, (bounds.width - row.width) / 2)
            for item in row.items {
                subviews[item.index].place(
                    at: CGPoint(x: x, y: y),
                    proposal: ProposedViewSize(item.size)
                )
                x += item.size.width + spacing
            }
            y += row.height + spacing
        }
    }

    private func layout(in width: CGFloat, subviews: Subviews) -> (rows: [Row], size: CGSize) {
        var rows: [Row] = []
        var current = Row()
        var currentWidth: CGFloat = 0

        for index in subviews.indices {
            let size = subviews[index].sizeThatFits(.unspecified)
            let nextWidth = current.items.isEmpty ? size.width : currentWidth + spacing + size.width
            if nextWidth > width, !current.items.isEmpty {
                current.width = currentWidth
                rows.append(current)
                current = Row()
                currentWidth = 0
            }

            current.items.append(Item(index: index, size: size))
            currentWidth = current.items.count == 1 ? size.width : currentWidth + spacing + size.width
            current.height = max(current.height, size.height)
        }

        if !current.items.isEmpty {
            current.width = currentWidth
            rows.append(current)
        }

        let height = rows.reduce(CGFloat(0)) { $0 + $1.height } + CGFloat(max(rows.count - 1, 0)) * spacing
        return (rows, CGSize(width: width, height: height))
    }

    private struct Row {
        var items: [Item] = []
        var height: CGFloat = 0
        var width: CGFloat = 0
    }

    private struct Item {
        var index: Int
        var size: CGSize
    }
}
