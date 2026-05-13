# HippoDEMO · Design Specification

> Single-source implementation spec for the **macOS 26 (Tahoe / Liquid Glass)** build of HippoDEMO.
> Pair this document with `Hippo Demo.html` — the HTML mocks are the visual ground truth; this
> document tells a coding agent how to translate them into native code **without recreating the
> browser chrome the mock fakes**.

Last updated: 2026-05-13. Target OS: macOS 26 (Tahoe). Language: Swift 6 / SwiftUI 6 + AppKit
where SwiftUI lacks surface area. Product behavior is fixed by `HIPPODEMO_PRD_REALTIME_PATH.md`;
this document only defines the **interface**.

---

## 0. Critical pitfalls — read this first

These are the ten mistakes that produce the bugs / misalignment / aesthetic drift previous attempts
hit. Each is restated in its section but stated together here so the agent has a checklist before
writing code.

| # | Pitfall | Right answer |
| --- | --- | --- |
| 1 | Drawing fake traffic lights inside the sidebar (because the mock does) | Use the system window chrome. macOS draws real traffic lights in the window titlebar. Do **not** reimplement them. |
| 2 | Using `.toolbar { … }` for the 44-pt filter row at the top of each page | The 44-pt filter row is **content**, not chrome. Build it as a manual `HStack(spacing: 8)` inside the detail view. Use `.toolbar { … }` only for window-level items (title, right-side actions). |
| 3 | Using the system's automatic sidebar toggle *and* a custom one | Hide the system one (`.toolbar(removing: .sidebarToggle)`) **and** add your own custom toggle via `ToolbarItem(.navigation)`. Otherwise users see two toggles. |
| 4 | Letting `Toggle().toggleStyle(.switch)` render at its default macOS size (50 × 31 pt) | Wrap with `.controlSize(.mini)` or build a custom 36 × 22 capsule toggle. The mock's switch is 36 × 22. |
| 5 | Slapping `.regularMaterial` on every panel and hoping it matches the mock | macOS 26 Liquid Glass uses `.glassEffect()` and `.containerBackground(.thickMaterial, …)`. See §3.3 — use the table, don't improvise. |
| 6 | Replacing the PUA glyphs in the HTML with whatever SF Symbols name "looks similar" | Use the explicit name table in §11. Every glyph in the mock has a named SF Symbol; do not pattern-match. |
| 7 | Using `Divider()` between cells in a horizontal metadata strip | `Divider()` is horizontal in SwiftUI. For a vertical hairline use `Rectangle().frame(width: 0.5).foregroundStyle(.separator)`. |
| 8 | Stacking `.frame(height: 32)` with `.padding(.vertical, …)` and getting a 40-pt row | Heights in this spec are *outer* heights. Use either `.frame(height: H)` **or** padding, not both. Each row's spec lists which. |
| 9 | Picker with `.pickerStyle(.segmented)` for the in-pane filter row | The mock's segmented control is **not** the system one. It's a capsule pill: `RoundedRectangle(7)` + 2-pt inner padding + per-cell `RoundedRectangle(5)`. Build it custom — see §6.2. |
| 10 | Rendering the Skill markdown with `AttributedString(markdown:)` | `AttributedString(markdown:)` cannot render the amber callout box or the monospace `<pre>` block. Use `swift-markdown-ui` or hand-roll renderer — see §5.7. |

---

## 1. Product surface

HippoDEMO is a status-bar-resident macOS app with two windows + two popover states, all sharing a
single local backend (`http://127.0.0.1:8787` FastAPI Orchestrator):

| Surface | Purpose | Hosting |
| --- | --- | --- |
| **Menu Bar extra** | At-a-glance presence + entry point | `MenuBarExtra` |
| **Status popover** | Live session control, services | `MenuBarExtra(... .window)` body when no task awaits |
| **Review popover** | Awaiting-review task review | Same `MenuBarExtra` body when `task.state == .awaitingReview` |
| **Dashboard window** | Chat, Live Signal, Active Task, Sessions, Skill Library, Settings | `Window` with `NavigationSplitView` |

Behavior is fully specified in the PRD; this file only defines the **interface**.

---

## 2. Project layout

```
HippoJarvis/
├── App/
│   ├── HippoJarvisApp.swift            // @main — MenuBarExtra + Window
│   ├── AppState.swift                  // ObservableObject — /state + SSE bridge
│   └── OrchestratorClient.swift        // URLSession SSE + REST
├── DesignSystem/
│   ├── Tokens.swift                    // Colors, Fonts, Spacing, Radii
│   ├── Materials.swift                 // glass(), surfaceCard()
│   ├── PushButton.swift                // ButtonStyle variants
│   ├── SegmentedPill.swift             // custom segmented (not system)
│   ├── StatusDot.swift                 // solid + pulsing
│   ├── HippoGlyph.swift                // the one custom symbol
│   └── Hairline.swift                  // VHairline + HHairline
├── MenuBar/
│   ├── MenuBarExtraView.swift          // HippoGlyph + recording dot
│   ├── PopoverHost.swift               // routes Status vs Review
│   ├── StatusPopover.swift
│   └── ReviewPopover.swift
├── Dashboard/
│   ├── DashboardWindow.swift           // NavigationSplitView root + custom toolbar
│   ├── Sidebar.swift                   // Hippo identity + Activity + Library + footer
│   ├── PageShell.swift                 // (title row) + (filter row) + content
│   ├── ChatView.swift
│   ├── LiveSignalView.swift
│   ├── ActiveTaskView.swift
│   ├── SessionsView.swift
│   ├── SkillView.swift
│   └── SettingsView.swift
└── Resources/
    └── Assets.xcassets/                // only HippoGlyph.symbolset + accent
```

Only **one `@main`** (`HippoJarvisApp`). It declares both the `MenuBarExtra` and the dashboard
`Window`. The dashboard is a `Window` (singleton), not a `WindowGroup`.

---

## 3. Design tokens

Single source of truth. Wire these into `DesignSystem/Tokens.swift`.

### 3.1 Color

| Token | sRGB (light) | sRGB (dark) | SwiftUI shortcut |
| --- | --- | --- | --- |
| `text.primary` | `rgba(0,0,0,0.85)` | `rgba(255,255,255,0.92)` | `.foregroundStyle(.primary)` |
| `text.secondary` | `rgba(0,0,0,0.5)` | `rgba(255,255,255,0.55)` | `.foregroundStyle(.secondary)` |
| `text.tertiary` | `rgba(0,0,0,0.4)` | `rgba(255,255,255,0.4)` | `.foregroundStyle(.tertiary)` |
| `accent` | system blue | system blue | `Color.accentColor` |
| `accent.preferred-fill` | `rgb(0,122,255)` | `rgb(10,132,255)` | `Color.accentColor` |
| `state.green` | `rgb(48,209,88)` | `rgb(48,209,88)` | `Color.green` |
| `state.amber` | `rgb(255,159,10)` | `rgb(255,159,10)` | `Color.orange` |
| `state.red` | `rgb(255,56,60)` | `rgb(255,69,73)` | `Color.red` |
| `selection.bg` | `rgba(0,0,0,0.11)` | `rgba(255,255,255,0.14)` | `Color.sidebarSelected` (dynamic, §9) |
| `divider` | `rgba(0,0,0,0.10)` | `rgba(255,255,255,0.16)` | `Color.separator` (use the system one) |

Never hard-code black on a possibly-dark surface. The `.primary` / `.secondary` / `.tertiary`
hierarchical foreground styles handle dark mode automatically — use them for **all** text unless
the design calls for a specific tint (e.g. red for "stop").

### 3.2 Type — SF Pro

Every text node uses SF Pro (system default on macOS) except the Chat hero, which uses **New York**
(macOS's bundled serif). Reference both by family name only — the system resolves weights:

```swift
// SF Pro (default)
.font(.system(size: 13, weight: .medium))

// New York (serif) — for the Chat hero ONLY
.font(.system(size: 42, weight: .regular, design: .serif))
```

| Style | Family / weight | Size / leading / tracking | Use site |
| --- | --- | --- | --- |
| `display.xxl` | SF Pro Bold | 32 / 36 / -0.025em | Skill page H1 |
| `display.xl` | SF Pro Bold | 28 / 32 / -0.020em | Active Task hero |
| `serif.hero` | **New York** Regular | 42 / 48 / -0.020em | Chat "What should Hippo do?" *(only)* |
| `title.h1` | SF Pro Semibold | 17 / 22 / -0.020em | Popover hero, sidebar identity |
| `body` | SF Pro Regular | 13 / 18 / -0.008em | Body, sidebar items, table rows |
| `body.emph` | SF Pro Medium | 13 / 16 / -0.005em | Selected sidebar item, button labels |
| `caption` | SF Pro Regular | 11 / 14 / 0 | Subtitles, secondary detail |
| `caption.bold` | SF Pro Semibold | 11 / 14 / 0.005em | Sidebar section header, form section header |
| `mono.body` | SF Mono Regular | 12.5 / 18 / -0.005em | Inline code, file paths, IDs |
| `mono.caption` | SF Mono Regular | 11 / 14 / -0.005em | Timeline timestamps, version strings |

**Never** ship absolute-point text in production paths the user can scale (body and below). Wrap
in `.dynamicTypeSize(...DynamicTypeSize.xxxLarge)` for Dynamic Type clamping if needed.

### 3.3 Materials — Liquid Glass

The mock layers two backgrounds and a 30-px backdrop blur to approximate macOS 26's Liquid Glass.
**SwiftUI on macOS 26 ships the real thing — use it, don't approximate.**

| Surface | macOS 26 SwiftUI | macOS 14–15 fallback |
| --- | --- | --- |
| Window content background | (no explicit fill; the window provides) | (default) |
| Sidebar | `NavigationSplitView` auto-applies vibrant material | `.regularMaterial` |
| Popover body | `.glassEffect()` (macOS 26) | `.regularMaterial` |
| Sidebar/sheet card | `.thickMaterial` | `.thickMaterial` |
| Filter row background under content title | none (transparent over window material) | none |

**Do not** dump `.regularMaterial` on the dashboard's main content area — `NavigationSplitView`
already provides the right material. Doubling it produces grey-on-grey.

### 3.4 Spacing & radii

| Token | Value | Use |
| --- | --- | --- |
| `space.0.5 / 1 / 1.5 / 2 / 3 / 4` | 2 / 4 / 6 / 8 / 12 / 16 | Inter-element padding |
| `radius.row` | 6 | Push buttons, segmented cells |
| `radius.item` | 8 | Sidebar items, form rows, list rows |
| `radius.card` | 10 | Form sections, table containers |
| `radius.composer` | 18 | Chat composer card |
| `radius.popover` | 16 | Popovers |
| `radius.window` | 16 | Window (system-provided; do not draw) |

### 3.5 Animation

| Motion | Curve | Duration |
| --- | --- | --- |
| Popover present | system default | — |
| Recording dot pulse | `.easeInOut`.repeatForever | 1.6 s |
| `Toggle`, segmented selection | `.easeInOut` | 150 ms |
| Sidebar collapse | system default (NavigationSplitView) | — |
| Waveform bars | `TimelineView(.animation)` | per frame |

Wrap pulse / waveform in `if !accessibilityReduceMotion`. See §10.

---

## 4. What the mock fakes vs what SwiftUI provides

This section eliminates the largest class of port bugs. Read carefully.

| Mock element | What the mock does | What SwiftUI does | Action |
| --- | --- | --- | --- |
| Traffic lights at top-left of sidebar / collapsed page | Draws three 12-pt circles | macOS draws real ones in the window titlebar | **Delete from your impl.** Trust the window chrome. |
| 32-pt title slice with "Chat" + "Hippo · local agent" | Manual `HStack` inside content | `.navigationTitle("Chat").navigationSubtitle("Hippo · local agent")` renders in window titlebar | Use `.navigationTitle(...)` + `.navigationSubtitle(...)`. **Do not** render a duplicate 32-pt strip. |
| Sidebar toggle button next to traffic lights | A custom `<button>` | `NavigationSplitView` provides one automatically (or you can place a custom one as `ToolbarItem(.navigation)`) | Use the system one. If you don't like its position, remove with `.toolbar(removing: .sidebarToggle)` and add `ToolbarItem(.navigation) { customToggle }`. Never both. |
| Aurora wallpaper outside the window | Painted by the mock | macOS shows the real desktop | Not your concern. |
| Popover arrow notch | None (correctly) | `MenuBarExtra` window-style has no notch | OK. Don't add one. |

After applying this section, your **PageShell** should be only two pieces:

```
PageShell
├── (the 44-pt filter row — manual HStack)
└── (scrollable content)
```

Title and subtitle live in the window via `.navigationTitle()` / `.navigationSubtitle()`. **There
is no 32-pt title slice in the native implementation.** The mock fakes one because the browser
has no titlebar API.

---

## 5. Window architecture

### 5.1 `@main`

```swift
@main
struct HippoJarvisApp: App {
    @StateObject private var state = AppState()

    var body: some Scene {
        // Menu bar entry
        MenuBarExtra("Hippo", image: "HippoGlyph") {
            PopoverHost()
                .environmentObject(state)
                .frame(width: 320)
        }
        .menuBarExtraStyle(.window)

        // Dashboard window
        Window("Hippo Dashboard", id: "dashboard") {
            DashboardWindow()
                .environmentObject(state)
        }
        .defaultSize(width: 1280, height: 800)
        .windowResizability(.contentMinSize)
        // Default chrome — traffic lights provided by the system
    }
}
```

### 5.2 `DashboardWindow`

```swift
struct DashboardWindow: View {
    @EnvironmentObject var state: AppState
    @SceneStorage("hippo.dashboard.sidebarVisible")
        private var visibility: NavigationSplitViewVisibility = .all
    @SceneStorage("hippo.dashboard.route")
        private var route: DashboardRoute = .liveSignal

    var body: some View {
        NavigationSplitView(columnVisibility: $visibility) {
            Sidebar(route: $route)
                .navigationSplitViewColumnWidth(min: 220, ideal: 240, max: 260)
        } detail: {
            Detail(route: route)
        }
        .navigationSplitViewStyle(.balanced)
        .toolbar(removing: .sidebarToggle)        // hide system toggle
        .toolbar {
            ToolbarItem(placement: .navigation) {
                Button {
                    withAnimation { visibility = (visibility == .all ? .detailOnly : .all) }
                } label: {
                    Image(systemName: "sidebar.left")
                }
                .help(visibility == .all ? "Hide sidebar" : "Show sidebar")
            }
        }
    }
}
```

The window minimum is **1024 × 640**. Below that, the Chat composer's max-width 720 column starts
clipping; below that the Live Signal table starts wrapping. Don't go lower.

### 5.3 `DashboardRoute`

```swift
enum DashboardRoute: Hashable, Codable {
    case chat
    case liveSignal
    case activeTask
    case sessions
    case skill(UUID)
    case settings
}
```

Default route at first launch = `.liveSignal`. If `state.currentTask?.state == .awaitingReview`
at launch, switch to `.activeTask`. Persist in `@SceneStorage`.

### 5.4 `Detail` switch

```swift
struct Detail: View {
    let route: DashboardRoute
    var body: some View {
        switch route {
        case .chat:        ChatView()
        case .liveSignal:  LiveSignalView()
        case .activeTask:  ActiveTaskView()
        case .sessions:    SessionsView()
        case .skill(let id): SkillView(id: id)
        case .settings:    SettingsView()
        }
    }
}
```

Every detail view is wrapped in `PageShell` (defined below).

---

## 6. Reusable components — Swift code

### 6.1 `PageShell`

The detail-view chrome. **Owns only the 44-pt filter row** (no title strip — that's the window
titlebar).

```swift
struct PageShell<Filter: View, Body_: View>: View {
    let title: String
    let subtitle: String?
    @ViewBuilder var filter: () -> Filter
    @ViewBuilder var body_: () -> Body_

    var body: some View {
        VStack(spacing: 0) {
            // 44-pt filter row — NOT the system .toolbar
            HStack(spacing: 8) { filter() }
                .frame(height: 44)
                .padding(.horizontal, 14)
                .overlay(alignment: .bottom) { HHairline() }

            // Content area
            body_()
                .frame(maxWidth: .infinity, maxHeight: .infinity)
        }
        .navigationTitle(title)
        .if(subtitle != nil) { $0.navigationSubtitle(subtitle!) }
    }
}
```

Notes:
- The filter row is **always 44 pt** outer height. Don't add vertical padding to its children;
  vertical-center them inside the row.
- `HHairline` (§6.7) is 0.5 pt.
- The `subtitle` becomes `.navigationSubtitle` — it appears below the title in the window
  titlebar (macOS 15+).

### 6.2 `SegmentedPill` (custom, NOT the system Picker)

The mock's segmented control is a **capsule with inner-padded cells**. It is **not** the SwiftUI
`.pickerStyle(.segmented)`, which is wider, taller, and uses a different selection treatment.

```swift
struct SegmentedPill<Option: Hashable>: View {
    @Binding var selection: Option
    let options: [(value: Option, label: String, glyph: String?, badge: Int?)]

    var body: some View {
        HStack(spacing: 0) {
            ForEach(options, id: \.value) { opt in
                Button {
                    withAnimation(.easeInOut(duration: 0.15)) { selection = opt.value }
                } label: {
                    HStack(spacing: 5) {
                        if let g = opt.glyph { Image(systemName: g) }
                        Text(opt.label)
                        if let b = opt.badge {
                            Text("\(b)").font(.system(size: 10, weight: .semibold))
                                .padding(.horizontal, 5).frame(height: 14)
                                .background(badgeBg(opt.value == selection), in: Capsule())
                                .foregroundStyle(opt.value == selection ? .white : .secondary)
                        }
                    }
                    .font(.system(size: 12, weight: .medium))
                    .padding(.horizontal, 10)
                    .frame(minWidth: 36, idealHeight: 24).frame(height: 24)
                    .background(
                        RoundedRectangle(cornerRadius: 5, style: .continuous)
                            .fill(opt.value == selection ? Color(white: 1).opacity(0.95) : .clear)
                            .shadow(color: opt.value == selection ? .black.opacity(0.06) : .clear,
                                    radius: 0.5, y: 1)
                    )
                }
                .buttonStyle(.plain)
            }
        }
        .padding(2)
        .background(
            RoundedRectangle(cornerRadius: 7, style: .continuous)
                .fill(.black.opacity(0.05))
                .overlay(RoundedRectangle(cornerRadius: 7).stroke(.black.opacity(0.08), lineWidth: 0.5))
        )
    }

    private func badgeBg(_ selected: Bool) -> some ShapeStyle {
        selected ? AnyShapeStyle(Color.accentColor) : AnyShapeStyle(Color.black.opacity(0.12))
    }
}
```

The outer pill is **28 pt** tall. Don't add `.frame(height:)` to the inner cells beyond the
explicit `24` shown. Tracking measurements:

- Outer pill: `RoundedRectangle(7)`, fill `black.opacity(0.05)`, stroke 0.5pt.
- Inner padding: 2 pt all sides.
- Inner cell: `RoundedRectangle(5)`, 24 pt tall, 10 pt horizontal padding, 36 pt min width.
- Selected cell fill: white opacity 0.95, shadow 0.5/0.06 1y.
- Cell label: SF Pro Medium 12 pt.

### 6.3 `PushButton` (as a `ButtonStyle`)

```swift
enum PushButtonVariant { case preferred, neutral, destructive, stop, glass, plain }
enum PushButtonSize    { case sm, md, lg }

struct PushButtonStyle: ButtonStyle {
    var variant: PushButtonVariant = .neutral
    var size: PushButtonSize = .md
    var fullWidth: Bool = false

    func makeBody(configuration: Configuration) -> some View {
        let (h, hp, fs): (CGFloat, CGFloat, CGFloat) = {
            switch size {
            case .sm: return (20, 10, 12)
            case .md: return (24, 16, 13)
            case .lg: return (28, 18, 14)
            }
        }()
        configuration.label
            .font(.system(size: fs, weight: .medium))
            .padding(.horizontal, hp)
            .frame(height: h)
            .frame(maxWidth: fullWidth ? .infinity : nil)
            .foregroundStyle(fg)
            .background(bg(configuration.isPressed), in: RoundedRectangle(cornerRadius: 6, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 6).stroke(stroke, lineWidth: 0.5))
            .shadow(color: shadow, radius: 1.5, y: 1)
            .opacity(configuration.isPressed ? 0.85 : 1)
            .animation(.easeOut(duration: 0.08), value: configuration.isPressed)
    }
    private var fg: Color {
        switch variant {
        case .preferred, .stop: return .white
        case .destructive:      return .red
        case .neutral, .glass:  return .primary
        case .plain:            return .primary
        }
    }
    private func bg(_ pressed: Bool) -> some ShapeStyle {
        switch variant {
        case .preferred:    return AnyShapeStyle(Color.accentColor)
        case .stop:         return AnyShapeStyle(Color.red)
        case .destructive,
             .neutral:      return AnyShapeStyle(Color.white.opacity(0.9))
        case .glass:        return AnyShapeStyle(.thickMaterial)
        case .plain:        return AnyShapeStyle(Color.clear)
        }
    }
    private var stroke: Color {
        variant == .plain ? .clear : .black.opacity(0.10)
    }
    private var shadow: Color {
        switch variant {
        case .preferred, .stop, .destructive, .neutral: return .black.opacity(0.06)
        default: return .clear
        }
    }
}

extension View {
    func pushButtonStyle(_ variant: PushButtonVariant, size: PushButtonSize = .md, fullWidth: Bool = false) -> some View {
        buttonStyle(PushButtonStyle(variant: variant, size: size, fullWidth: fullWidth))
    }
}
```

Usage:
```swift
Button("Insert draft") { … }.pushButtonStyle(.preferred)
Button("Stop Jarvis") { … }.pushButtonStyle(.stop, size: .md, fullWidth: true)
Button("Ignore") { … }.pushButtonStyle(.neutral)
```

### 6.4 `StatusDot`

```swift
struct StatusDot: View {
    enum State { case ok, warn, error, busy, rec, idle }
    let state: State
    var pulse: Bool = false
    var size: CGFloat = 6
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        TimelineView(.animation(minimumInterval: 1/30, paused: !pulse || reduceMotion)) { ctx in
            let t = ctx.date.timeIntervalSinceReferenceDate
            let phase = pulse && !reduceMotion ? (sin(t * 2 * .pi / 1.6) + 1) * 0.5 : 1.0
            ZStack {
                if pulse && !reduceMotion {
                    Circle().fill(color).opacity(0.25 + 0.25 * phase)
                        .frame(width: size + 6 * phase, height: size + 6 * phase)
                }
                Circle().fill(color).frame(width: size, height: size)
                    .overlay(Circle().stroke(.white.opacity(0.4), lineWidth: 0.5))
            }
        }
    }
    private var color: Color {
        switch state {
        case .ok:    return .green
        case .warn:  return .orange
        case .error: return .red
        case .busy:  return .accentColor
        case .rec:   return .red
        case .idle:  return Color(white: 0.7)
        }
    }
}
```

### 6.5 `MetadataCell` and metadata strip

The Active Task metadata strip is **4 cells with vertical hairlines between them**, each cell
two-line (label uppercase 10pt above value 14pt). Total strip height ~52pt with 12pt vertical
padding.

```swift
struct MetadataCell: View {
    let label: String
    let value: String
    var mono: Bool = false
    var muted: Bool = false

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            Text(label.uppercased())
                .font(.system(size: 10, weight: .semibold)).tracking(0.04)
                .foregroundStyle(.secondary)
            Text(value)
                .font(.system(size: 14, weight: .semibold, design: mono ? .monospaced : .default))
                .foregroundStyle(muted ? .secondary : .primary)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 16)
    }
}

struct MetadataStrip: View {
    let cells: [(label: String, value: String, mono: Bool, muted: Bool)]
    var body: some View {
        HStack(spacing: 0) {
            ForEach(Array(cells.enumerated()), id: \.offset) { i, c in
                if i > 0 { VHairline() }
                MetadataCell(label: c.label, value: c.value, mono: c.mono, muted: c.muted)
            }
        }
        .padding(.vertical, 12)
        .background(.white.opacity(0.7), in: RoundedRectangle(cornerRadius: 10))
        .overlay(RoundedRectangle(cornerRadius: 10).stroke(.black.opacity(0.08), lineWidth: 0.5))
    }
}
```

### 6.6 `Toggle` — explicit size

macOS's default `Toggle().toggleStyle(.switch)` is 50 × 31. The mock uses 36 × 22. Use either:

```swift
Toggle("", isOn: $on).labelsHidden().toggleStyle(.switch).controlSize(.mini)
```

…or build a custom one:

```swift
struct PillToggle: View {
    @Binding var isOn: Bool
    var body: some View {
        ZStack(alignment: isOn ? .trailing : .leading) {
            Capsule().fill(isOn ? Color.green : Color.black.opacity(0.18))
                .frame(width: 36, height: 22)
            Circle().fill(.white)
                .frame(width: 20, height: 20).padding(1)
                .shadow(color: .black.opacity(0.18), radius: 2, y: 2)
        }
        .animation(.easeInOut(duration: 0.15), value: isOn)
        .onTapGesture { isOn.toggle() }
    }
}
```

### 6.7 Hairlines

Use `Divider()` for a horizontal hairline below a row — it's 0.5pt on macOS 11+. For a **vertical**
hairline (between metadata cells, between sidebar sections, etc.), `Divider()` doesn't work —
build it explicitly:

```swift
struct HHairline: View { var body: some View {
    Rectangle().fill(Color.separator.opacity(0.6)).frame(height: 0.5)
} }

struct VHairline: View { var body: some View {
    Rectangle().fill(Color.separator.opacity(0.6)).frame(width: 0.5).padding(.vertical, 4)
} }
```

### 6.8 `Waveform`

```swift
struct Waveform: View {
    @Environment(\.accessibilityReduceMotion) private var reduceMotion
    var body: some View {
        TimelineView(.animation(minimumInterval: 1/30, paused: reduceMotion)) { ctx in
            let t = ctx.date.timeIntervalSinceReferenceDate
            HStack(spacing: 2.5) {
                ForEach(0..<13, id: \.self) { i in
                    let phase = reduceMotion ? 1.0 : (sin(t * 5 + Double(i) * 0.7) + 1) * 0.5
                    Capsule()
                        .fill(LinearGradient(colors: [.orange, .red], startPoint: .top, endPoint: .bottom))
                        .frame(width: 2.5, height: 6 + CGFloat(phase) * 18)
                }
            }
            .frame(height: 24)
        }
    }
}
```

### 6.9 `HippoGlyph` — the one custom symbol

Ship as `Assets.xcassets/HippoGlyph.symbolset`. Source SVG path (copy verbatim into the symbol's
"Regular Medium" vector):

```
<svg viewBox="0 0 24 24">
  <path d="M5 13c0-3.5 3.1-6.5 7-6.5s7 3 7 6.5v3a2 2 0 01-2 2h-2.2a.8.8 0 01-.8-.8v-.6
           c0-1.4-1.3-2.6-3-2.6s-3 1.2-3 2.6v.6a.8.8 0 01-.8.8H4.5A.5.5 0 014 18v-1
           c0-2 .4-3 1-4z" fill="currentColor"/>
  <circle cx="15.5" cy="11" r="0.9" fill="white"/>
  <circle cx="9.5"  cy="11" r="0.9" fill="white"/>
</svg>
```

The symbol must be set to **template image** so it inherits tint. Use it at 16 pt (menu bar),
22 pt (sidebar identity row), and 28 pt (popover header tile).

---

## 7. Surface specs

### 7.1 Menu bar extra

```swift
MenuBarExtra { PopoverHost() }
    label: {
        ZStack(alignment: .bottomTrailing) {
            Image("HippoGlyph").renderingMode(.template)
                .resizable().frame(width: 16, height: 16)
            if state.snapshot.services.ownscribe == .recording {
                Circle().fill(.red).frame(width: 5, height: 5)
                    .symbolEffect(.pulse, isActive: !reduceMotion)
            }
        }
    }
    .menuBarExtraStyle(.window)
```

- No "REC" text pill — just the dot.
- The menu-bar icon must be a **template** image (renderingMode `.template`) so macOS tints it for
  selected/menu-bar-color states.

### 7.2 Status popover (idle / recording)

Width **320 pt**. Sections, top to bottom, separated by `Divider()`:

| # | Section | Height | Content |
| --- | --- | --- | --- |
| 1 | Header | 56 pt | 28 × 28 Hippo tile (gradient orange→red), title "Hippo" (semibold 13), subtitle "Investor sync · 04:12" (regular 11 secondary), trailing `ellipsis.circle` |
| 2 | Status | 80 pt | `Waveform` 50×24 — title "Listening" (semibold 13) + subtitle "Audio + window context" (11 secondary) — right-aligned timer (semibold 17 mono digits) |
| 2b | Primary actions | 32 pt | `Stop Jarvis` (`pushButtonStyle(.stop, fullWidth: true)`) + `Capture` (`.neutral`), `HStack(spacing: 8)` |
| 3 | Services | 4 × 32 pt | One row per adapter, see below |
| 4 | Footer toolbar | 36 pt | Left: 3 symbol buttons (`waveform.path.ecg`, `sparkles`, `gearshape`). Right: locale label + `arrow.clockwise` |

Service row layout (32 pt outer height):
```swift
HStack(spacing: 10) {
    SymbolTile(systemName: glyph, size: 20)          // 20×20 grey tile, radius 6
    Text(name).font(.system(size: 13, weight: .medium))
    Spacer()
    Text(detail).font(.system(size: 11)).foregroundStyle(.secondary)
    StatusDot(state: state, pulse: state == .rec, size: 6)
}.padding(.horizontal, 12)
```

Services in order: **OpenChronicle, ownscribe, cua-driver, vlmac**. Do not re-order.

### 7.3 Review popover

Same window as Status. Routing in `PopoverHost`:

```swift
if let task = state.snapshot.currentTask, task.state == .awaitingReview {
    ReviewPopover(task: task).transition(.opacity)
} else {
    StatusPopover().transition(.opacity)
}
```

Layout, top to bottom:

| # | Section | Content |
| --- | --- | --- |
| 1 | Header | Same Hippo tile, title "Ready to act", subtitle "1 task · awaiting review" |
| 2 | Hero | 6-pt-gap VStack: blue "Active Task" capsule (10×3) + 17-pt Bold title + 13-pt secondary body (3-line max) |
| 3 | Metadata strip | `MetadataStrip` 3 cells — `Surface`, `Confidence`, `Mode` |
| 4 | Proposed actions | "PROPOSED" section header (caption.bold), then 2 numbered rows (1 / 2) — each 32-pt with leading number tile, title, trailing tiny grey detail |
| 5 | Actions | `Insert draft` (`.preferred`, fullWidth=true) + `Ignore` (`.neutral`), `HStack(spacing: 8)`, padding `(.top, 10)` |
| 5b | Link | `Open in Activity →` plain button below actions, full width |

Both popovers dismiss on outside-click (system default for `.menuBarExtraStyle(.window)`).

### 7.4 Sidebar

The sidebar's content does **not** include traffic lights or a sidebar toggle — those are in the
window chrome.

```swift
struct Sidebar: View {
    @Binding var route: DashboardRoute
    @EnvironmentObject var state: AppState

    var body: some View {
        List(selection: $route) {
            HippoIdentityRow()                          // hippo tile + name + rec status
                .listRowInsets(.init(top: 8, leading: 8, bottom: 14, trailing: 8))

            Section {
                SidebarRow(.chat,        glyph: "bubble.left.and.bubble.right.fill", label: "Chat",       trailingPill: "BETA")
                SidebarRow(.liveSignal,  glyph: "waveform.path.ecg",                 label: "Live Signal",badge: state.events.count.map(String.init))
                SidebarRow(.activeTask,  glyph: "target",                            label: "Active Task",accentBadge: pendingTaskCount)
                SidebarRow(.sessions,    glyph: "clock.arrow.circlepath",            label: "Sessions")
            }

            Section("Library") {
                ForEach(state.skills) { skill in
                    SkillRow(.skill(skill.id), name: skill.name, sub: skill.relativeDate, dim: skill.older)
                }
            }
        }
        .listStyle(.sidebar)
        .safeAreaInset(edge: .bottom) { SidebarFooter() }
    }
}
```

- `List` with selection of `DashboardRoute` — clicking a row sets the route.
- Sidebar rows are **28 pt** tall. The selected row gets `selection.bg` tint automatically when
  using `.listStyle(.sidebar)` + `selection:` binding — **do not** draw your own selection box.
- `SidebarFooter` is the gear button + Orchestrator status line, pinned at the bottom via
  `.safeAreaInset(.bottom)`.

Selected-row label and symbol use `Color.accentColor` automatically with `.sidebar` style. Do not
hard-code blue.

### 7.5 Chat — `ChatView`

This is the only view that uses a serif font (for the hero).

Layout (when no active thread):

```
PageShell(title: "Chat", subtitle: "Hippo · local agent",
          filter: { SegmentedPill(...) + Spacer() + ModelPicker() + composeButton })
{
  VStack {
    Spacer()
    VStack(spacing: 22) {                     // empty-state stack, max-width 720, centered
      SessionPill()                            // Active session · investor sync [Attach]
      Text("What should Hippo do?")
          .font(.system(size: 42, weight: .regular, design: .serif))
          .multilineTextAlignment(.center)
      Composer()                               // see below — radius 18, padding 16
      ConnectToolsBar()                        // thin pill — wrench + tools row + xmark
      SuggestionChips()                        // wrap-flow, centered
      RecentThreads()                          // 12-radius card, 3 rows
    }
    .frame(maxWidth: 720).padding(.horizontal, 28)
    Spacer()
  }
}
```

#### Composer (the key composer measurements)

```
- Outer card: RoundedRectangle(18), fill rgba(255,255,255,0.92),
              0.5pt stroke rgba(0,0,0,0.10), shadow 0/1 + 0/8(-8) 0.04/0.08
- Inner padding: 16 top + sides, 12 bottom
- TextEditor: min height 56, font system 15, placeholder rgba(0,0,0,0.4) "Assign a task…"
- Bottom row: HStack(spacing: 6) of:
   [+ circle 30, stroke 0.5]
   [ToolChipGroup capsule height 30, 3 colored 22-circle dots overlapped + "+N" text]
   [display circle 30]
   Spacer
   [livephoto circle 30]
   [mic.fill circle 30]
   [SendButton 30 circle, bg black.opacity(0.08), arrow.up.circle.fill]
```

`SendButton` enables only when text is non-empty; while sending, replace symbol with
`ProgressView().controlSize(.small)`.

#### Suggestion chips

`FlowLayout` (or a manual wrap) of 32-pt pill buttons. Each: 14-pt horizontal padding, 7-pt gap,
0.5-pt stroke `rgba(0,0,0,0.10)`, label SF Pro Medium 12.5.

#### Active-thread state

When `thread.messages.isEmpty == false`:
- Replace the empty-state stack with a `ScrollViewReader` of bubble rows.
- Composer becomes `.safeAreaInset(edge: .bottom)` so it pins to the bottom and shrinks the scroll
  region.
- The serif hero collapses to a 13-pt secondary string in the page subtitle ("3 turns · investor
  sync"). The hero font is **not** used outside the empty state.

#### Tool calls in bubbles

Render as a collapsed inline strip inside the agent message:

```
[wrench.and.screwdriver]  toolName  →  resultPreview (truncated 60 chars)
```

Tap expands a sheet showing full args + result.

### 7.6 Live Signal — `LiveSignalView`

`PageShell(title: "Live Signal", subtitle: "Investor sync · 80 events")` with filter row:

```
SegmentedPill(All / Signals / Tasks / Artifacts) — Spacer —
[StatusDot.ok pulsing, "SSE · /events"] — SearchField(180) — refresh
```

Content:
- `ForEach(sessions)` grouped by session.
- Group header: 8-pt row with chevron-down/right, session title, "Active" capsule (if live),
  spacer, duration mono 11 secondary.
- Inside each group: single rounded card (radius 10), rows separated by `Divider()`.
- Event row layout (12-pt outer vertical padding, 16-pt horizontal):
  - 70-pt mono timestamp column
  - 22 × 22 typed glyph in tinted square
  - VStack: title (semibold 13), body (12.5 regular 0.7 opacity), mono meta (11 0.45 opacity)

Event types and accent tints:

| Type | SF Symbol | Tint | Source event |
| --- | --- | --- | --- |
| `task` | `target` | blue | `active_task_generated` |
| `artifact` | `doc.text.fill` | green | `artifact_ready` |
| `asr` | `mic.fill` | green | `transcript_finalized` |
| `sop` | `pin.fill` | orange | `sop_capture_started/closed` |
| `session` | `record.circle` | red | `session_started/stopped` |

### 7.7 Active Task — `ActiveTaskView`

`PageShell(title: "Active Task")` with filter row:

```
SegmentedPill(Awaiting [n] / Completed / Ignored) — Spacer —
[Ignore button .neutral] [Insert draft button .preferred, icon arrow.right.to.line]
```

Content, max-width 820, centered:

1. **Hero**: blue "Awaiting review" capsule (caption.bold, 2/9 padding), then `display.xl` title,
   then 15-pt secondary body (max-width 620).
2. **MetadataStrip**: 4 cells — `Surface · Confidence · Source · Insertion`.
3. **Proposed actions card**: caption.bold "PROPOSED ACTIONS" label, then `RoundedRectangle(10)`
   card with numbered rows. Each row: 22 × 22 grey tile with number, title (semibold 13), detail
   (12 secondary), trailing `Ready` green capsule.
4. **Recent card**: caption.bold "RECENT", then card listing past tasks (target glyph, title, sub,
   trailing state capsule — `Completed` green or `Ignored` grey).

Empty state: when `state.currentTask` is nil, show centered placeholder with `target` symbol +
"No task awaiting review." + secondary "Live signal continues in the background." + link button
"Open Live Signal" → routes to `.liveSignal`.

### 7.8 Sessions — `SessionsView`

`PageShell(title: "Sessions")` with filter row:

```
SegmentedPill(All / Active / Archived) — Spacer —
SearchField(200) — refresh
```

Content: `Table(sessions)` with columns:

| Column | Width | Content |
| --- | --- | --- |
| Session | flex | `clock.arrow.circlepath` glyph + title (semibold 13) + mono id (11 secondary) |
| Started | 110 | "Today 09:42" |
| Duration | 90 right-aligned mono | `04:12` |
| Artifacts | 90 right-aligned mono | `4` |
| State | 110 | Capsule pill — `Active Task` (blue), `Completed` (green), `Ignored` (grey) |
| Disclosure | 28 | `chevron.right` 11 pt tertiary |

Selected row tints `selection.bg`. Clicking navigates to session detail (placeholder — out of
scope for this PR).

### 7.9 Skill Library — `SkillView`

`PageShell(title: skill.name, subtitle: "SKILL.md · 3.2 KB")` with filter row:

```
SegmentedPill(Preview / Source, glyphs: eye / chevron.left.forwardslash.chevron.right)
[secondary label "Preview · Source"] — Spacer — SearchField — Generate — Run skill .preferred
```

Content: centered **720-wide column**, scroll vertical, with:

- Header row: 24×24 tinted blue tile + caption.bold "SKILL · Investor follow-up" + amber "MOCK"
  pill (or green "CORTEX" if non-mock).
- `display.xxl` title (32 / 36 / -0.025em).
- 15-pt secondary subtitle (max-width 580).
- 4-cell inline meta row (Source / Created / Size / Generator) — each cell label-above-value.
- Markdown body — see below.

#### Markdown rendering

`AttributedString(markdown:)` is **insufficient** for this surface. Use **`swift-markdown-ui`**
(Package.swift dependency: `MarkdownUI`) and override these block styles:

```swift
Markdown(markdown)
    .markdownTextStyle { FontFamily(.system); FontSize(14); ForegroundColor(.primary) }
    .markdownBlockStyle(\.heading2) { configuration in
        configuration.label.font(.system(size: 11, weight: .bold)).kerning(0.06 * 11)
            .textCase(.uppercase).foregroundStyle(.secondary)
            .padding(.top, 20).padding(.bottom, 8)
    }
    .markdownBlockStyle(\.codeBlock) { configuration in
        ScrollView(.horizontal) { configuration.label.markdownTextStyle { FontFamilyVariant(.monospaced); FontSize(12.5) } }
            .padding(16).background(.black.opacity(0.04), in: RoundedRectangle(cornerRadius: 10))
    }
    .markdownBlockStyle(\.blockquote) { …amber callout box… }
```

The amber callout is rendered via a custom code-fence directive (e.g. lines starting with
`> [!callout]` or a custom inline component) — **not** native markdown blockquote. The mock uses
a hand-styled `<div>` so a hand-rolled directive is fine.

### 7.10 Settings — `SettingsView`

`PageShell(title: "Settings", subtitle: "Developer console")` with filter row:

```
SegmentedPill(General / Services / Recording / Permissions / About) — Spacer —
refresh
```

Content: centered 760-wide column. Vertical stack of `FormSection`s (16-pt gap):

1. **Orchestrator** — Base URL field, Status row (dot + text), Auto-launch toggle.
2. **Services** — One 52-pt row per adapter: `StatusDot`, mono name, secondary detail, version,
   chevron.
3. **OpenChronicle** — Daemon (Start/Pause/Stop buttons row), Capture (Capture once / Timeline
   tick), Captures index (Rebuild).
4. **Permissions** — Mic / Screen Recording / Accessibility. Each is a 52-pt row with leading
   28-pt tinted icon tile, label, subtitle, trailing `Granted` (green) or `Not granted` (amber)
   capsule, then a "Manage" / "Open Settings" `.neutral` push button.
5. **About** — Build string + Export diagnostics button.

`FormSection` implementation:
```swift
struct FormSection<Content: View>: View {
    let title: String
    let footnote: String?
    @ViewBuilder var content: () -> Content
    var body: some View {
        VStack(alignment: .leading, spacing: 0) {
            Text(title.uppercased()).font(.system(size: 11, weight: .semibold))
                .tracking(0.04 * 11).foregroundStyle(.secondary)
                .padding(.bottom, 6).padding(.horizontal, 4)
            VStack(spacing: 0) { content() }
                .background(.white.opacity(0.7), in: RoundedRectangle(cornerRadius: 10))
                .overlay(RoundedRectangle(cornerRadius: 10).stroke(.black.opacity(0.08), lineWidth: 0.5))
            if let f = footnote {
                Text(f).font(.system(size: 11)).foregroundStyle(.secondary)
                    .padding(.top, 6).padding(.horizontal, 6)
            }
        }.padding(.bottom, 22)
    }
}
```

Each form row is 44 pt min height with `Divider()` between (except last). Always use the
`FormRow` view defined in §6.5-style with `(label, sub?, control)`.

`Open Settings` permission button must call:
```swift
NSWorkspace.shared.open(URL(string: "x-apple.systempreferences:com.apple.preference.security")!)
```

---

## 8. State & data flow

```swift
@MainActor final class AppState: ObservableObject {
    @Published var snapshot: StateSnapshot = .placeholder
    @Published var events:   [SignalEvent] = []
    @Published var skills:   [Skill] = []
    @Published var sessions: [Session] = []
    @Published var connectivity: Connectivity = .connecting

    let orchestrator: OrchestratorClient

    init() {
        self.orchestrator = OrchestratorClient()
        Task { await bootstrap() }
    }

    private func bootstrap() async {
        await orchestrator.healthcheck()
        async let s = orchestrator.get("/state")
        async let e = orchestrator.get("/events/history?limit=80")
        async let sk = orchestrator.get("/skills")
        async let ss = orchestrator.get("/sessions")
        // … assign with `await`
        Task { for try await event in orchestrator.eventStream("/events") {
            await MainActor.run { events.insert(event, at: 0); apply(event) }
        }}
    }
}
```

- Inject via `.environmentObject(state)` at `@main`.
- SSE: `URLSession.bytes(for:)` against `/events`. Parse `event:` / `data:` lines.
- Reconnect with exponential backoff (1s, 2s, 4s, … max 30s) on drop. While reconnecting:
  `connectivity = .reconnecting` — sidebar footer dot flips to amber.

### 8.1 Snapshot shape (mirrors PRD §6 `/state`)

```swift
struct StateSnapshot: Codable {
    var jarvisState: JarvisState           // idle, meetingActive, sopMarking, sopGenerating, activeTaskCandidate, taskReviewing
    var statusMessage: String
    var currentSession: SessionRef?
    var sopCapture: SopCaptureRef?
    var currentTask: ActiveTask?
    var services: ServicesSnapshot         // openchronicle, ownscribe, cuaDriver, vlmac (each: state + detail + version)
}
```

---

## 9. Orchestrator integration

| UI action | HTTP call |
| --- | --- |
| Popover "Jarvis ON" | `POST /session/jarvis-on` |
| Popover "Jarvis OFF" / "Stop Jarvis" | `POST /session/jarvis-off` |
| Popover "Capture" → "Finish Capture" | `POST /sop/capture-start` then `…/capture-finish` |
| Review popover "Insert draft" | `POST /active-task/{id}/confirm` |
| Review popover / Active Task "Ignore" | `POST /active-task/{id}/ignore` |
| Active Task tab "Complete" | `POST /active-task/{id}/complete` |
| Skill `Generate` | `POST /skill/generate` |
| Skill row delete | `DELETE /skill/{id}` |
| Settings · OpenChronicle buttons | `POST /integrations/openchronicle/{verb}` |
| Sessions list (load) | `GET /sessions` |
| Skill list (load) | `GET /skills` |
| Live Signal initial load | `GET /events/history?limit=80` |
| Live Signal stream | `GET /events` (SSE) |

Each call sets the trigger button's `isLoading = true`; on a non-2xx response, surface the
response's `detail` string in `.alert("…", isPresented:)`. Match PRD service-detail semantics.

---

## 10. Light / dark mode & accessibility

- **Color**: Always use `.foregroundStyle(.primary/.secondary/.tertiary)`, `Color.accentColor`,
  `Color.red/.green/.orange`. Where a hand-mixed tint is unavoidable (e.g. `selection.bg`), wrap
  in a dynamic `Color(nsColor: NSColor(name: …) { appearance in … })`.
- **Material**: `NavigationSplitView` swaps materials per appearance. Don't override.
- **Voice Over**: every push button, sidebar row, and table row needs an explicit
  `.accessibilityLabel(...)` and (for status dots / pulsing icons)
  `.accessibilityValue("Recording, four minutes twelve seconds")`.
- **Reduce Motion**: pulse animations on `StatusDot` / `Waveform` / segmented selection must check
  `@Environment(\.accessibilityReduceMotion)` and disable. Sample shown in §6.4 / §6.8.
- **Dynamic Type**: 13 pt body scales — don't lock with `.fixedSize(horizontal: false, vertical: true)`
  unless the layout truly cannot accommodate growth.

---

## 11. Iconography — SF Symbols only

The mock uses SF Symbols' private-use codepoints (e.g. `􀋃`) so the browser can render them
via the system SF Pro font. **Never copy a PUA codepoint into Swift code.** Use the named symbol
in the tables below.

### 11.1 Glyph mapping

#### Menu bar / popovers
| Where | SF Symbols name | Notes |
| --- | --- | --- |
| Menu-bar extra (Hippo) | custom: `HippoGlyph` | + overlaid red `circle.fill` when recording |
| Battery / Wi-Fi / Spotlight / Control Center | system menu extras (don't draw) | macOS handles |
| Status popover header more | `ellipsis.circle` |  |
| Stop Jarvis | `stop.fill` |  |
| Capture | `pin.fill` |  |
| Service: OpenChronicle | `clock.arrow.circlepath` |  |
| Service: ownscribe | `mic.fill` |  |
| Service: cua-driver | `cursorarrow.click.2` |  |
| Service: vlmac | `eye.fill` |  |
| Popover footer · Activity | `waveform.path.ecg` |  |
| Popover footer · Library | `sparkles` |  |
| Popover footer · Settings | `gearshape` |  |
| Popover footer · Refresh | `arrow.clockwise` |  |
| Review · Active Task pill | `target` |  |
| Review · Insert draft button | `arrow.right.to.line` |  |
| Review · Open in Activity link | `arrow.up.right` |  |

#### Sidebar / dashboard
| Item | SF Symbols name |
| --- | --- |
| Chat | `bubble.left.and.bubble.right.fill` |
| Live Signal | `waveform.path.ecg` |
| Active Task | `target` |
| Sessions | `clock.arrow.circlepath` |
| Library section `+` button | `plus` |
| Skill row | `sparkles` |
| Settings footer button | `gearshape` |
| Sidebar toggle (custom) | `sidebar.left` |

#### Toolbar (every page filter row)
| Where | SF Symbols name |
| --- | --- |
| Search field icon | `magnifyingglass` |
| Generic refresh | `arrow.clockwise` |
| Insert (preferred) | `arrow.right.to.line` |
| Play / Run | `play.fill` |
| Generate | `sparkles` |
| Segmented · Preview | `eye` |
| Segmented · Source | `chevron.left.forwardslash.chevron.right` |
| Disclosure right / down | `chevron.right` / `chevron.down` |

#### Chat composer
| Where | SF Symbols name |
| --- | --- |
| Model picker leading | `cpu` |
| Compose new chat | `square.and.pencil` |
| Composer `+` | `plus.circle` |
| Screen-capture | `display` |
| Mic | `mic.fill` |
| Live audio | `livephoto` |
| Send | `arrow.up.circle.fill` |
| Tool dot · Mail | `envelope.fill` |
| Tool dot · Calendar | `calendar` |
| Tool dot · GitHub | `chevron.left.forwardslash.chevron.right` |
| Tool dot · Slack-like | `bubble.left.and.bubble.right.fill` |
| Tool dot · Notion-like | `square.and.pencil` |
| Connect-tools strip icon | `wrench.and.screwdriver.fill` |
| Connect-tools dismiss | `xmark` |
| Suggestion · Generate skill | `sparkles` |
| Suggestion · Draft follow-up | `envelope.fill` |
| Suggestion · Summarize | `clock.arrow.circlepath` |
| Suggestion · Start capture | `mic.fill` |
| Suggestion · More | `ellipsis` |

#### Live Signal · Settings
See §7.6 and §7.10 tables.

### 11.2 Symbol styling

- Sidebar rows: `.font(.system(size: 13, weight: .regular))` — system tints when selected.
- Toolbar filter row: `.font(.system(size: 14, weight: .medium))`.
- Composer tool dots: 22 pt circle bg; 10-pt `bold` white-foreground symbol.
- Recording dot: `.symbolEffect(.pulse, isActive: !reduceMotion)`.

---

## 12. Build / package

- Xcode 17, macOS 26 SDK.
- Bundle id `com.hippo.jarvis`. Entitlements: Hardened Runtime, Microphone, Screen Recording.
- Single dependency: `swift-markdown-ui` (for Skill view). Everything else is system.
- The Swift app launches the FastAPI Orchestrator with `Process` if it isn't reachable — see PRD
  §4.1. Log path: `.runtime/orchestrator-app.log`.
- Ship one `Custom.symbolset` in `Assets.xcassets` for the Hippo head (§6.9). No other asset
  bundles.

---

## 13. Acceptance checklist

A PR delivering this spec passes if all of the following hold:

- [ ] Menu bar shows the Hippo glyph + red pulsing dot when recording; **no rectangle pill**.
- [ ] Status popover dismisses on outside-click, opens instantly, width 320, no arrow notch, sections separated by 0.5-pt `Divider()`s.
- [ ] When `currentTask.state == .awaitingReview`, the popover body swaps to the Review variant on next open with an opacity crossfade.
- [ ] **No fake traffic lights drawn inside the sidebar or detail pane.** macOS's window chrome is the only source.
- [ ] **No `.toolbar { … }` is used for the 44-pt filter row at the top of any page.** Each page builds it as a manual `HStack` inside `PageShell`.
- [ ] Sidebar toggle: the system one is removed via `.toolbar(removing: .sidebarToggle)`; a single custom `sidebar.left` toggle lives in `ToolbarItem(.navigation)`. Never two.
- [ ] Sidebar fully collapses (`NavigationSplitViewVisibility.detailOnly`); the same `sidebar.left` icon flips the visibility either way.
- [ ] All six routes (`chat`, `liveSignal`, `activeTask`, `sessions`, `.skill`, `settings`) render cleanly in both expanded and collapsed states with no per-page collapse code.
- [ ] Page titles appear in the **window titlebar** via `.navigationTitle()` / `.navigationSubtitle()` — not as a duplicated 32-pt strip inside the content.
- [ ] Chat hero "What should Hippo do?" is the **only** New York serif text. Everything else is SF Pro.
- [ ] Skill view renders the amber callout block and the monospace `<pre>` block correctly — not as default `AttributedString` markdown.
- [ ] `Toggle` in Settings is 36 × 22 (custom) or `.controlSize(.mini)` — never the default 50 × 31.
- [ ] In-pane segmented controls use the custom `SegmentedPill` (§6.2) — **not** `.pickerStyle(.segmented)`.
- [ ] Vertical hairlines are `Rectangle().frame(width: 0.5)` — never `Divider()` inside an `HStack`.
- [ ] Dark mode renders without any hand-mixed black-on-grey survivors. Run every artboard in dark mode and screenshot-diff.
- [ ] Every icon is `Image(systemName: …)` or the single `HippoGlyph` custom symbol — no PNG / SVG fallbacks.
- [ ] VoiceOver reads every push button, sidebar row, table row, and status dot.
- [ ] Reduce Motion disables `StatusDot` pulse and `Waveform` animation.

---

## 14. Out of scope (per PRD §10 / §12)

- Independent floating intervention HUD outside the popover.
- Real `cua-driver` insertion into Mail / Messages / browser forms.
- `vlmac` video preview, `basic-memory` persistence, multi-user cloud sync.
- `Project_Cortex` real backend invocation (gated behind env vars).

Placeholder views that surface service status only — they are not visual scope.

---

## 15. Delivered artboards (HTML mock)

The HTML mock in `Hippo Demo.html` is the visual ground truth. Each artboard maps to a SwiftUI
scene/view as below. **Where the mock and this document disagree on a SwiftUI API or measurement,
this document wins** — the mock is a browser approximation.

| Artboard id | Surface | SwiftUI |
| --- | --- | --- |
| `menubar-popover` | Menu bar + idle / recording popover | `MenuBarExtra { StatusPopover() }` |
| `review-popover` | Menu bar + task-review popover | same `MenuBarExtra`, body = `ReviewPopover` |
| `dash-chat` | Dashboard · Chat | `route = .chat` |
| `dash-live` | Dashboard · Live Signal | `route = .liveSignal` |
| `dash-task` | Dashboard · Active Task | `route = .activeTask` |
| `dash-sessions` | Dashboard · Sessions | `route = .sessions` |
| `dash-skills` | Dashboard · Skill Library | `route = .skill(<investor-followup>)` |
| `dash-settings` | Dashboard · Settings | `route = .settings` |
| `dash-chat-col` / `dash-task-col` / `dash-skills-col` / `dash-sessions-col` | Same, sidebar collapsed | `visibility = .detailOnly` |

Collapsed variants for Live Signal and Settings are not shipped as separate artboards — they
are produced automatically by `PageShell` honoring the collapsed environment.
