# HippoDEMO · Design Specification

> Single-source implementation spec for the macOS 26 (Tahoe / Liquid Glass) build of HippoDEMO.
> Pair this document with `Hippo Demo.html` — the HTML mocks are the visual ground truth; this
> document tells a coding agent how to translate them into native code.

Last updated: 2026-05-13. Target OS: macOS 26 (Tahoe). Language: Swift 6 / SwiftUI 6 + AppKit
where SwiftUI lacks surface area. The product behavior is fixed by `HIPPODEMO_PRD_REALTIME_PATH.md`;
this document only defines the **interface**.

---

## 1. Product surface

HippoDEMO is a status-bar-resident macOS app with four user-facing surfaces, all of which share a
single backend (`http://127.0.0.1:8787` FastAPI Orchestrator):

| Surface | Purpose | Primary control |
| --- | --- | --- |
| **Menu Bar extra** | At-a-glance presence + entry point | `MenuBarExtra` |
| **Status Popover** | Live session control, services, recent task | `MenuBarExtra(... .window)` |
| **Review Popover** | Same window — content changes when an Active Task is awaiting review | same `MenuBarExtra` window |
| **Dashboard window** | Full session, library, sessions, settings | Standard `Window` w/ `NavigationSplitView` |

Behavior is exhaustively specified in the PRD (`HIPPODEMO_PRD_REALTIME_PATH.md`). This file only
defines visual structure, materials, type, and the SwiftUI hierarchy.

---

## 2. Project layout (recommended)

```
HippoJarvis.app/
├── App/
│   ├── HippoJarvisApp.swift            // @main, MenuBarExtra + WindowGroup
│   ├── AppState.swift                  // ObservableObject — /state SSE bridge
│   └── OrchestratorClient.swift        // URLSession SSE + REST
├── DesignSystem/
│   ├── Tokens.swift                    // Colors, Fonts, Materials, Radii
│   ├── Materials.swift                 // .regularMaterial wrappers
│   ├── PushButton.swift                // bordered / preferred / destructive
│   ├── ListRow.swift                   // 24h sidebar item, 44h form row, etc.
│   ├── SegmentedControl.swift          // toolbar segmented
│   └── StatusDot.swift                 // pulsing recording dot
├── MenuBar/
│   ├── MenuBarExtraView.swift          // HippoGlyph + pulsing dot
│   ├── StatusPopover.swift             // Idle / recording popover body
│   └── ReviewPopover.swift             // Task-review popover body
├── Dashboard/
│   ├── DashboardWindow.swift           // NavigationSplitView root
│   ├── Sidebar.swift                   // Hippo identity + Activity + Library
│   ├── ChatView.swift                  // agent conversation surface
│   ├── LiveSignalView.swift
│   ├── ActiveTaskView.swift
│   ├── SessionsView.swift
│   ├── SkillView.swift                 // markdown viewer
│   └── SettingsView.swift
└── Resources/
    └── Assets.xcassets/
```

Only one `@main` (`HippoJarvisApp`); the menu-bar extra and the window-group both live inside it.
The dashboard is a standard window so users can `⌘W` close and re-open from the popover or Dock.

---

## 3. Design tokens

All tokens map 1:1 with the values currently used in `hippo-shared.jsx`. They derive from the
attached macOS 26 Figma kit — keep the exact values.

### 3.1 Color

| Token | sRGB | When | SwiftUI |
| --- | --- | --- | --- |
| `text.primary` | `rgba(0,0,0,0.85)` light · `rgba(255,255,255,0.92)` dark | Body, labels | `.foregroundStyle(.primary)` |
| `text.secondary` | `rgba(0,0,0,0.5)` / `rgba(255,255,255,0.55)` | Subtitles, captions | `.secondary` |
| `text.tertiary` | `rgb(191,191,191)` | Trailing details, hints | `.tertiary` |
| `accent.system` | `rgb(0,122,255)` | Selected sidebar symbol, links, preferred button | `.tint(.accentColor)` / `Color.accentColor` |
| `accent.preferredFill` | `rgb(13,111,255)` | Preferred / default push-button background | `Color(red:13/255,green:111/255,blue:255/255)` |
| `state.green` | `rgb(48,209,88)` | Toggle on, "Granted", "Ready" pill | `Color.green` system |
| `state.amber` | `rgb(255,159,10)` | Mock fallback, warning callout | `Color.orange` system |
| `state.red` | `rgb(255,56,60)` | Recording, destructive, stop | `Color.red` system |
| `sel.bg` | `rgba(0,0,0,0.11)` | Sidebar selection, table row selected | n/a — use `.contentShape(.rect)` + manual |
| `divider` | `rgba(0,0,0,0.08–0.10)` | All hairlines | `Divider()` (override if needed) |

> Always source the system accent via `Color.accentColor` so user preferences are respected; the
> hard hex above is only the design intent.

### 3.2 Type — SF Pro

| Style | Family / weight | Size / leading / tracking |
| --- | --- | --- |
| `display.xxl` | SF Pro Heavy | 32 / 36 / -0.025em |
| `display.xl` | SF Pro Bold | 28 / 32 / -0.020em |
| `display.lg` | SF Pro Bold | 22 / 26 / -0.020em |
| `title.h1` | SF Pro Bold | 17 / 22 / -0.020em |
| `title.h2` | SF Pro Medium | 15 / 22 / -0.008em |
| `body` | SF Pro Regular | 13 / 18 / -0.008em |
| `body.emph` | SF Pro Medium | 13 / 16 / -0.005em |
| `caption` | SF Pro Regular | 11 / 14 / 0 |
| `caption.bold` | SF Pro Bold | 11 / 14 / 0.005em |
| `mono.body` | SF Mono Regular | 12.5 / 18 / -0.005em |
| `mono.caption` | SF Mono Regular | 11 / 14 / -0.005em |

In SwiftUI use `.font(.system(size:13, weight:.medium, design:.default))` or `.font(.body)` family
modifiers. **Never override the user's accessibility text-size preference** — pin only the relative
ratios.

### 3.3 Materials (Liquid Glass)

The mock layers two backgrounds per Apple's Liquid Glass spec. In SwiftUI prefer the system
materials — they map 1:1:

| Mock token | SwiftUI material | Where it is used |
| --- | --- | --- |
| `material.window` | `.regularMaterial` | Dashboard window content |
| `material.sidebar` | `.thinMaterial` | Dashboard sidebar (`NavigationSplitView` does this automatically) |
| `material.popover` | `.regularMaterial` | Status popover, Review popover |
| `material.toolbar` | `.bar` / `.ultraThinMaterial` | Window titlebar / toolbar |
| `material.menubar` | (system; not overridable) | The menu bar itself |

Underlying CSS values for reference:
- Light: fill `rgba(245,245,245,0.67)` over glass tint `rgba(0,0,0,0.2)`, blur 30, saturate 180.
- Dark: fill `rgba(38,38,38,0.67)` over glass tint `rgba(0,0,0,0.2)`, blur 30, saturate 180.

**Shadows.**
- Popover: `0 4px 20px rgba(0,0,0,0.15), 0 0 0 0.5px rgba(0,0,0,0.10)` — SwiftUI: rely on
  `.background(.regularMaterial, in: RoundedRectangle(...))`; system applies the shadow.
- Window: macOS supplies it. Do not draw your own.

### 3.4 Spacing & radii

| Token | Value | Use |
| --- | --- | --- |
| `space.1 / 2 / 3 / 4` | 4 / 8 / 12 / 16 | Inter-element padding |
| `radius.row` | 6 | Push buttons, segmented cells |
| `radius.item` | 8 | Sidebar items |
| `radius.card` | 10 | Form sections, table containers |
| `radius.popover` | 16 | Popovers, dashboards (window radius is system-provided 16) |
| `radius.material` | 34 | Large free-floating glass (rare here) |

### 3.5 Animation

| Motion | Curve | Duration |
| --- | --- | --- |
| Popover present | `.easeOut` | 180 ms (system default) |
| Recording dot pulse | `.easeInOut` repeat-forever | 1.6 s |
| Toggle, segmented selection | `.easeInOut` | 150 ms |
| Waveform bars | independent `repeat-forever` per bar | 1.2 s |

---

## 4. Surface 1 — Menu Bar extra

### 4.1 Structure

```swift
MenuBarExtra("Hippo", systemImage: "h.circle.fill") {
    StatusPopoverRoot()        // ReviewPopover OR StatusPopover, picked by state
        .frame(width: 320)
}
.menuBarExtraStyle(.window)    // window-style, not menu-style
```

### 4.2 Menu bar icon

- Custom `HippoGlyph` (Hippo head, 16 × 16). Provide as PDF + Symbol set so it tints automatically.
- **Show a 5-pt red status dot** next to the glyph when `services.ownscribe.state == .recording`.
  Implement with `Image(systemName: "circle.fill").foregroundStyle(.red)` overlaid bottom-right.
- **No "REC" text pill** — the dot is sufficient. (This is the bug we fixed in mock v3.)
- Selected state is handled by the system when the popover is open.

### 4.3 Idle / Recording popover (artboard 01)

Width 320, light material, **no arrow notch** (macOS 26 menu-bar popovers don't draw one).

Sections separated by `Divider()` (full-width hairlines). Vertical order:

1. **Header** — 28 × 28 Hippo tile (`LinearGradient` orange→red), title `"Hippo"`, subtitle session name + elapsed.
2. **Status row** — waveform on the left, status label + clock on the right. Big primary action below:
   - `Stop Jarvis` (destructive filled red, `PushButton.stop`) — full width
   - `Capture` (neutral bordered) — fixed width, trailing
3. **Services list** — four rows: `OpenChronicle`, `ownscribe`, `cua-driver`, `vlmac`. Each row:
   `Image(systemName:)` 20 × 20 leading, name, trailing detail in secondary text, trailing `StatusDot`.
4. **Footer toolbar** — left: `activity`, `book`, `gear` symbol buttons. Right: locale + refresh.

### 4.4 Review popover (artboard 02)

Same window; SwiftUI switches body when `state.currentTask?.state == .awaitingReview`:

1. **Header** — Hippo tile, title `"Ready to act"`, subtitle `"1 task · awaiting review"`.
2. **Hero** — small blue "Active Task" capsule, 17 pt Bold title, 13 pt secondary body.
3. **Metadata strip** — 3-column inset block: `Surface` · `Confidence` · `Mode`.
4. **Proposed actions** — numbered rows (1, 2…) inside a card.
5. **Actions row** — `Insert draft` preferred + `Ignore` neutral, then `Open in Activity →` link.

Both popovers must dismiss the moment the user clicks outside (`scenePhase` `.background`).

---

## 5. Surface 2 — Dashboard window (1280 × 800 default)

```swift
WindowGroup(id: "dashboard") {
    DashboardWindow()
        .frame(minWidth: 1024, minHeight: 640, idealWidth: 1280, idealHeight: 800)
}
.defaultSize(width: 1280, height: 800)
.windowToolbarStyle(.unified(showsTitle: true))
```

### 5.1 Sidebar (240 wide, collapsible)

`NavigationSplitView` left column. Compose with `List` in `.sidebar` style:

1. **Titlebar row** — 32 pt; left-to-right: traffic lights, `Divider` 0.5 pt vertical, **sidebar toggle** (`sidebar.left`). The same toggle icon is used in both expanded and collapsed states; clicking flips the visibility.
2. **Hippo identity row** — 22 × 22 gradient tile, `Hippo` title, pulsing recording line.
3. **Activity items**:
   - `Chat` (`bubble.left.and.bubble.right.fill`, blue "Beta" pill)
   - `Live Signal` (`waveform.path.ecg`, badge `12`)
   - `Active Task` (`target`, blue badge `1` when a task awaits review)
   - `Sessions` (`clock.arrow.circlepath`)
4. **Library section header** — `"Library"` with `+` action button (creates a new skill from current selection).
5. **Skill rows** — one row per `Skill`, sorted desc by `created_at`. Leading: sparkle symbol. Trailing: relative date.
6. **Footer** — gear button (opens Settings page) + orchestrator status (`StatusDot` + `127.0.0.1:8787`).

#### 5.1.1 Collapsed state

The sidebar collapses **fully** (not to a rail). SwiftUI:

```swift
@State private var sidebarVisible: NavigationSplitViewVisibility = .all

NavigationSplitView(columnVisibility: $sidebarVisible) { Sidebar() }
    detail: { DetailPane() }
```

When `sidebarVisible == .detailOnly`:
- The sidebar pane is hidden completely (no rail).
- The detail pane's titlebar **prepends** the chrome that lived in the sidebar header: traffic lights, a 0.5 pt vertical hairline, and the same `sidebar.left` toggle (which now expands the sidebar back). 22 × 22 hit target, no fill.
- The page title from `PageShell` still appears immediately after, so the user always knows which view they're on.
- The detail pane's 44 pt toolbar row is unchanged.

`PageShell` reads a `@Environment(\.sidebarVisible)` (or equivalent) and conditionally renders the prepended chrome via a `leading:` slot. Page authors don't need to know about collapse state — the shell handles it. **Every view** (`ChatView`, `LiveSignalView`, `ActiveTaskView`, `SessionsView`, `SkillView`, `SettingsView`) inherits this behavior automatically.

The mock ships a collapsed variant of all five primary detail views — see the artboards listed in §15. They are visually identical to their expanded counterparts except for the sidebar being hidden and the toggle / traffic-lights moving into the page title row.

Persist `sidebarVisible` in `@SceneStorage("hippo.dashboard.sidebar")` so it survives launch.

Selection model: `@State selection: DashboardRoute` where `DashboardRoute` is an enum
`{ chat, liveSignal, activeTask, sessions, skill(id), settings }`. Skill rows pass the id.

### 5.2 Detail pane

`NavigationSplitView` right column hosts a `switch selection`:

| Route | View |
| --- | --- |
| `.chat` | `ChatView` |
| `.liveSignal` | `LiveSignalView` |
| `.activeTask` | `ActiveTaskView` |
| `.sessions` | `SessionsView` |
| `.skill(id)` | `SkillView(id:)` |
| `.settings` | `SettingsView` |

Every detail view follows the same chrome: **32 pt titlebar slice** (label only, no extra controls)
then a **44 pt toolbar slice** (segmented control + spacer + actions), then scrollable content.
Implement the chrome as a single `DetailHeader` view to avoid drift.

### 5.3 Chat — `ChatView`

The agentic conversation surface, modelled on Manus's empty state. Lets the user assign one-off
tasks ("draft a follow-up to Hana", "summarize last session", "generate a skill for X") that fall
outside the auto-capture flow. Chats hold a reference to a session and to a model.

- **Toolbar.** Segmented `Chat / Recent / Templates`. Trailing: `ModelPicker` (capsule, e.g. `Hippo Mini · local`) + `square.and.pencil` compose button.
- **Empty state.** Centered max-width 720 column:
  1. **Session pill** — round capsule showing the live session (`StatusDot.rec`, `"Active session · investor sync"`) with an inline `Attach` button that pins the current session as context.
  2. **Hero** — 42 pt serif heading (`New York Regular`, `-0.02em`): "What should Hippo do?". Pin the *serif* font here; **everything else in the dashboard stays SF Pro**.
  3. **Composer** — 18 pt-radius card, white-ish fill, 0.5 pt hairline, padding 16. Two zones:
     - Multi-line `TextEditor` (treat 56 pt as `minHeight`). Placeholder: "Assign a task, ask Hippo to draft something, or describe what to capture next…"
     - Bottom action row: a `+` circle (radius 100, 30 pt), inline tool-chip group (three colored tool dots `+ N`), a `display` circle, spacer, `livephoto`, `mic.fill`, then a 30 pt arrow-up send button.
  4. **Connect-tools hint** — thin 100-radius bar with `wrench.and.screwdriver` + label `"Connect more tools to Hippo"` + a row of 18 pt rounded brand badges + a dismiss `xmark`.
  5. **Suggestion chips** — wrap-flow of 32 pt pill buttons (`Generate a skill`, `Draft follow-up`, `Summarize last session`, `Start capture`, …, `More`).
  6. **Recent threads** — 12 pt-radius rounded card listing past chats. Each row: 28 pt rounded tinted tile + title + secondary `"3 turns · uses Mail · 2 min ago"` + trailing chevron.
- **Active state.** When a thread has messages, swap the empty state for a `ScrollView`-of-bubbles. The composer **stays pinned to the bottom** with the same control row; the session-pill and `New York` hero collapse into a 13 pt header.
- **Streaming.** Use `URLSession.bytes` against `/chat/stream` (forthcoming Orchestrator endpoint). Render incoming tokens into a `Text` buffer. Animate insertion with `.transition(.opacity)`. Cancel on user `⌘⌥⌫`.
- **Tool calls.** When the agent emits a tool call, render it as a collapsed inline strip in the bubble (`wrench.and.screwdriver` + tool name + result preview). Click expands a sheet showing arguments/result.
- **References.** A chat may reference a `Session`, a `Skill`, or an `ActiveTask` (drag-drop or `@` mention). References render as 22 pt rounded tinted chips inline with the user's message.

### 5.4 Live Signal — `LiveSignalView`

- Toolbar: `Picker("Filter", selection:)` rendered `.pickerStyle(.segmented)` with `All / Signals / Tasks / Artifacts`.
- Right side: SSE indicator (`StatusDot(.green, pulse: true)` + `"SSE · /events"`), search field, refresh button.
- Content: `ForEach(sessions)` grouped by session. Group header includes session title, "Active" pill if live, duration. Inside each group: list of `Event` rows in a single rounded container.
- `Event` row layout: 70 pt monospace time column · 22 × 22 typed glyph (color per type) · title + secondary body + optional meta in mono.

Event types and their accent colors (matches `EVENT_TYPE` in the mock):
| Type | Color | Source event |
| --- | --- | --- |
| `task` | blue | `active_task_generated` |
| `artifact` | green | `artifact_ready` |
| `asr` | green | `transcript_finalized` |
| `sop` | amber | `sop_capture_started/closed` |
| `session` | red | `session_started/stopped` |

### 5.5 Active Task — `ActiveTaskView`

- Toolbar: 3-tab segmented `Awaiting (n) / Completed / Ignored`. Trailing: `Ignore` + `Insert draft`.
- Centered max-width 820 column.
- **Hero**: blue "Awaiting review" capsule, 28 pt Bold title, 15 pt secondary body.
- **Metadata strip**: 4 cells with internal `Divider()`s — `Surface · Confidence · Source · Insertion`.
- **Proposed actions** card — numbered rows; trailing `Ready` green capsule per action.
- **Recent** card — past tasks with a `Completed` / `Ignored` capsule.

When `state.currentTask` is nil, show an empty state ("No task awaiting review. Live signal continues in the background.") + a link to `LiveSignal`.

### 5.6 Sessions — `SessionsView`

- Single `Table(sessions)` with columns: `Session` (icon + title + monospaced id), `Started`,
  `Duration` (right-aligned monospace), `Artifacts` (right-aligned monospace), `State` (pill),
  trailing chevron. Selected row tinted `rgba(0,0,0,0.04)`.
- State pill values: `Active Task` (blue), `Completed` (green), `Ignored` (gray).
- Clicking a row navigates to a session-detail view (out of scope for this PR; placeholder ok).

### 5.7 Skill Library — `SkillView`

- Toolbar: 2-icon segmented `Preview / Source`. Right: search field + `Generate` + `Run skill`.
- Body: centered 720-wide column rendering markdown. Use `AttributedString(markdown:)` and
  custom paragraph styles for `H2`, lists, code blocks, callouts.
- **Mock callout** — amber bordered box reminding the user this version writes `inserted_mock`.

### 5.8 Settings — `SettingsView`

Styled as a self-contained preferences pane inside the dashboard (not the system Settings app).

- Toolbar: segmented `General / Services / Recording / Permissions / About`.
- Content: stacked `FormSection`s (centered max-width 760):
  1. **Orchestrator** — Base URL (`TextField`), Status (`StatusDot` + text), Auto-launch (`Toggle`).
  2. **Services** — One row per adapter: `StatusDot`, monospace name, secondary detail, version, chevron.
  3. **OpenChronicle** — Daemon control buttons (Start/Pause/Stop), Capture (Capture once / Timeline tick), Captures index (Rebuild).
  4. **Permissions** — Mic / Screen Recording / Accessibility, each with a `Granted` / `Not granted` pill and a Manage / Open Settings button. Always defer the actual grant to `System Settings.app` via `NSWorkspace.shared.open(URL(string: "x-apple.systempreferences:com.apple.preference.security"))`.
  5. **About** — build string + Export diagnostics.

`FormSection` = a header label above + a rounded white-ish `RoundedRectangle` with internal `Divider()`s between rows. Each row is 44 pt tall, padding 14.

---

## 6. Components inventory

### 6.1 `PushButton`

```swift
enum PushButtonVariant { case preferred, destructive, stop, neutral, glass, plain }
enum PushButtonSize    { case sm, md, lg }     // h 20 / 24 / 28
```

- All variants: `RoundedRectangle(cornerRadius: 6)`, SF Pro Medium 13.
- `.preferred` → fill `rgb(13,111,255)`, white label, inset highlight.
- `.destructive` → white bg + `rgb(255,56,60)` label.
- `.stop` → fill `rgb(255,56,60)`, white label.
- `.neutral` → `rgba(255,255,255,0.9)` bg + `rgba(0,0,0,0.10)` border.
- `.glass` → `rgba(255,255,255,0.5)` + 20 px blur (popover footer).
- `.plain` → no chrome.

Implement once in `DesignSystem/PushButton.swift`. Use `ButtonStyle` so callers stay terse:
`Button("Insert draft") { … }.buttonStyle(.preferred)`.

### 6.2 `SegmentedControl`

`Picker(...) { ForEach(...) }.pickerStyle(.segmented)`. Add a custom modifier that renders the
height-28 capsule style if the default `.segmented` doesn't match the mock; otherwise leave as-is.

### 6.3 `StatusDot`

Two states matter: solid (always-on health), and `pulse` (recording). For pulse:

```swift
@State private var pulse = false
Circle()
    .scaleEffect(pulse ? 1.4 : 1)
    .opacity(pulse ? 0.7 : 1)
    .onAppear { withAnimation(.easeInOut(duration: 0.8).repeatForever(autoreverses: true)) { pulse = true } }
```

### 6.4 `ListRow` / `FormRow`

Two heights:
- 28 pt sidebar item (icon + label + badge), radius 8, selected fill `rgba(0,0,0,0.11)`.
- 44 pt form row (label/subtitle on left, control on right), bottom `Divider()` except last.

### 6.5 `Toggle` (custom)

Apple's default `Toggle().toggleStyle(.switch)` already renders correctly in macOS 26. Use it.

### 6.6 `MetadataCell`

Used in popover hero and task metadata strip. Compact two-line cell:

```swift
VStack(alignment: .leading, spacing: 2) {
    Text(label.uppercased()).font(.caption2).foregroundStyle(.secondary)
    Text(value).font(.system(size: 14, weight: .semibold))
}
```

Wrap in a `HStack` with `Divider()` between cells for the strip layout.

### 6.7 `Waveform`

13 vertical bars, 2.5 wide, gap 2.5, heights driven by an array; each bar animates with its own
phase offset. SwiftUI:

```swift
TimelineView(.animation) { context in
    let t = context.date.timeIntervalSinceReferenceDate
    HStack(spacing: 2.5) {
        ForEach(0..<13) { i in
            let h = (sin(t * 5 + Double(i) * 0.7) + 1) * 12 + 6
            Capsule().fill(.linearGradient(...)).frame(width: 2.5, height: h)
        }
    }
}
```

---

## 7. State & data flow

### 7.1 `AppState`

```swift
@MainActor final class AppState: ObservableObject {
    @Published var snapshot: StateSnapshot           // mirrors GET /state
    @Published var events:   [SignalEvent] = []      // SSE
    @Published var skills:   [Skill] = []
    @Published var sessions: [Session] = []
    var orchestratorClient: OrchestratorClient
}
```

- Inject via `.environmentObject(appState)` at `@main`.
- `OrchestratorClient` owns the SSE connection (`URLSession.bytes(for:)`) and parses
  `event:` / `data:` lines, posting decoded `SignalEvent`s on the main actor.
- Reconnect with exponential backoff if the SSE drops; the UI shows a `StatusDot(.warn)` and
  the sidebar footer flips its dot to amber.

### 7.2 Derived selection

```swift
enum DashboardRoute: Hashable {
    case liveSignal, activeTask, sessions, skill(UUID), settings
}
```

`@State var route: DashboardRoute = .liveSignal` (or `.activeTask` if a task is awaiting review at
launch). Persist last route in `@SceneStorage("hippo.dashboard.route")`.

### 7.3 Menu-bar popover routing

`MenuBarExtraView` decides which popover body to render:

```swift
if let task = appState.snapshot.currentTask, task.state == .awaitingReview {
    ReviewPopover(task: task)
} else {
    StatusPopover()
}
```

This is point 5 of the design brief: when an Active Task is generated, the popover content changes
on its next open. If the popover is already open, the swap animates with `.transition(.opacity)`.

---

## 8. Orchestrator integration

All HTTP/SSE endpoints are documented in the PRD section 6. The UI only needs to:

| UI action | HTTP call |
| --- | --- |
| Header "Jarvis ON" | `POST /session/jarvis-on` |
| Header "Jarvis OFF" / "Stop Jarvis" | `POST /session/jarvis-off` |
| Popover "Capture" → "Finish Capture" | `POST /sop/capture-start` then `…/capture-finish` |
| Review popover "Insert draft" | `POST /active-task/{id}/confirm` |
| Review popover "Ignore" | `POST /active-task/{id}/ignore` |
| Active Task tab "Completed" press | `POST /active-task/{id}/complete` |
| Skill `Generate` | `POST /skill/generate` |
| Skill row delete | `DELETE /skill/{id}` |
| Settings · OpenChronicle buttons | `POST /integrations/openchronicle/{verb}` |

Each call must show an in-flight state on its trigger (button loading) and surface a `detail`
string in an Alert if the response is non-2xx — match the PRD's "service detail" semantics.

---

## 9. Light / dark mode

The Figma kit ships both. SwiftUI handles this automatically as long as you:

- Use `.foregroundStyle(.primary / .secondary / .tertiary)` instead of hardcoded blacks.
- Use system materials (`.regularMaterial`, etc.) — they swap fills.
- Use `Color.accentColor`, `.red`, `.green`, `.orange` semantically.
- For the few hand-mixed tints (e.g. `rgba(0,0,0,0.11)` selection bg), wrap them in a dynamic
  color:

```swift
extension Color {
    static let sidebarSelected = Color(nsColor: NSColor(name: nil) { appearance in
        appearance.bestMatch(from: [.darkAqua, .aqua]) == .darkAqua
            ? NSColor(white: 1, alpha: 0.14)
            : NSColor(white: 0, alpha: 0.11)
    })
}
```

---

## 10. Accessibility

- Every popover row, sidebar item, toolbar button needs an `.accessibilityLabel`.
- Recording status dot: `accessibilityValue("Recording, four minutes twelve seconds")`.
- Dashboard navigation must respect Voice Control selectors — use plain text labels, not symbols
  only.
- Honor `@Environment(\.legibilityWeight)` and `\.sizeCategory`. The 13 pt floor in this spec
  scales — don't pin to absolute points.
- Animations gated on `@Environment(\.accessibilityReduceMotion)` — disable pulse and waveform.

---

## 11. Iconography

Use **SF Symbols 6** as the *only* icon library. It ships with Xcode, scales with Dynamic Type,
inherits the user's accent, animates via `.symbolEffect(...)`, and has matching glyphs for every
icon used in the mock. Render with `Image(systemName: "...")` — never as PNGs or hand-drawn SVGs.

Download the **SF Symbols app** from Apple to browse glyphs and copy names; the public catalogue
also lives at `developer.apple.com/sf-symbols`.

**Only one custom symbol**: the Hippo head (`HippoGlyph`). Ship it as a `Custom.symbolset` inside
`Assets.xcassets` so it tints and scales like a stock symbol. Use it for:
- The menu-bar extra icon (16 pt).
- The 28 pt rounded gradient tile in the Status / Review popovers.
- The 22 pt rounded tile in the dashboard sidebar identity row.

Do **not** reach for third-party icon packs (Lucide, Phosphor, Tabler, etc.). They are great
products but pull a 200–800 KB asset bundle, fight VoiceOver, and don't get free dark-mode /
hierarchical-color treatment. SF Symbols covers every glyph the design uses.

### 11.1 Glyph mapping

The HTML mock uses SF Symbols' PUA codepoints directly. When you port to Swift, replace each
with `Image(systemName: "<name>")`.

#### Menu bar

| Where | SF Symbols name | Notes |
| --- | --- | --- |
| Menu-bar extra (Hippo) | custom: `HippoGlyph` | + overlaid red `circle.fill` when recording |
| Battery | `battery.100` | use percentage variants per state |
| Wi-Fi | `wifi` | use `wifi.slash` if offline |
| Spotlight | `magnifyingglass` |  |
| Control Center | `switch.2` |  |

#### Status popover (idle / recording)

| Where | SF Symbols name |
| --- | --- |
| Header more menu | `ellipsis.circle` |
| Stop Jarvis button | `stop.fill` |
| Capture button | `pin.fill` |
| OpenChronicle row | `clock.arrow.circlepath` |
| ownscribe row | `mic.fill` |
| cua-driver row | `cursorarrow.click.2` |
| vlmac row | `eye.fill` |
| Footer · Activity | `waveform.path.ecg` |
| Footer · Library | `sparkles` |
| Footer · Settings | `gearshape` |
| Footer · Refresh | `arrow.clockwise` |

#### Review popover

| Where | SF Symbols name |
| --- | --- |
| Active Task pill | `target` |
| Insert draft button | `arrow.right.to.line` |
| Ignore | (text only) |
| Open in Activity link | `arrow.up.right` |

#### Dashboard sidebar

| Item | SF Symbols name |
| --- | --- |
| Chat | `bubble.left.and.bubble.right.fill` |
| Live Signal | `waveform.path.ecg` |
| Active Task | `target` |
| Sessions | `clock.arrow.circlepath` |
| Library section `+` | `plus` |
| Skill row | `sparkles` |
| Settings (footer) | `gearshape` |

#### Toolbar (per page)

| Where | SF Symbols name |
| --- | --- |
| Search field icon | `magnifyingglass` |
| Generic refresh | `arrow.clockwise` |
| Insert (preferred button) | `arrow.right.to.line` |
| Play / Run | `play.fill` |
| Generate | `sparkles` |
| Segmented · Preview | `eye` |
| Segmented · Source | `chevron.left.forwardslash.chevron.right` |
| Disclosure right | `chevron.right` |
| Disclosure down | `chevron.down` |

#### Chat page

| Where | SF Symbols name |
| --- | --- |
| Model picker (Hippo Mini) | `cpu` (or `apple.intelligence` if available) |
| Session pill dot | `circle.fill` (red) |
| Compose new chat (toolbar) | `square.and.pencil` |
| Composer `+` (more) | `plus.circle` |
| Composer screen-capture | `display` |
| Composer mic | `mic.fill` |
| Composer live audio | `livephoto` |
| Composer send | `arrow.up.circle.fill` |
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

#### Live Signal events

| Event type | SF Symbols name | Tint |
| --- | --- | --- |
| `task` | `target` | blue |
| `artifact` | `doc.text.fill` | green |
| `asr` | `mic.fill` | green |
| `sop` | `pin.fill` | amber |
| `session` | `record.circle` | red |

#### Settings · Permissions

| Permission | SF Symbols name |
| --- | --- |
| Microphone | `mic.fill` |
| Screen Recording | `eye.fill` |
| Accessibility | `figure.wave` (or `hand.raised.fill`) |

### 11.2 Symbol styling

- Sidebar rows use `.regular` weight at 13 pt. Selected items get `.foregroundStyle(.tint)`.
- Toolbar symbols use `.medium` weight at 14 pt.
- Tool dots (Chat composer) use `.bold` at 10 pt over a colored background — set
  `.foregroundStyle(.white)`.
- For the recording state, attach `.symbolEffect(.pulse)` to the red dot; gate via
  `.symbolEffectsRemoved()` when `\\.accessibilityReduceMotion` is on.

---

## 12. Build / package

- Xcode 17, macOS 26 SDK.
- Bundle id `com.hippo.jarvis`. Entitlements: Hardened Runtime, Microphone, Screen Recording,
  Apple Events (to AppKit; no Mail.app scripting yet).
- The Swift app launches the FastAPI Orchestrator with `Process` if it isn't reachable — see PRD
  section 4.1. Log path: `.runtime/orchestrator-app.log`.
- Ship a single `Custom.symbolset` in `Assets.xcassets` for the Hippo head. Nothing else needs to
  be bundled — every other icon is sourced from SF Symbols at runtime.

---

## 13. Acceptance checklist

A PR delivering this spec passes if all of the following hold:

- [ ] Menu bar shows the Hippo glyph + red pulsing dot when recording; **no rectangle pill**.
- [ ] Status popover dismisses on outside-click, opens instantly, width 320, no arrow notch.
- [ ] When an Active Task moves to `awaiting_review`, the popover body swaps to the Review variant on next open with an opacity crossfade.
- [ ] Dashboard sidebar selection is one of: Chat, Live Signal, Active Task, Sessions, a specific Skill, or Settings — and each detail view loads in <100 ms from in-memory state.
- [ ] Sidebar **fully collapses** (`NavigationSplitViewVisibility.detailOnly`); when collapsed the **same `sidebar.left` toggle** appears in the detail pane's title row to re-expand. No compose / pencil button next to the toggle in either state.
- [ ] Every detail view (Chat, Live Signal, Active Task, Sessions, Skill, Settings) renders cleanly in both expanded and collapsed states without page-level changes — collapse is handled entirely by `PageShell`.
- [ ] The Chat page renders the empty state (serif hero + composer + suggestions + recent threads) when the thread is empty, and switches to a bubble list with a pinned composer when messages exist.
- [ ] The serif `New York` font is used **only** for the Chat hero — every other label, title and body uses SF Pro.
- [ ] All hairlines are 0.5 pt (use `.frame(height: 0.5)` Rectangle, not `Divider()` which is 1 pt on macOS pre-26 — verify on the target OS).
- [ ] Dark mode renders without any hand-mixed gray ever being visible against a dark background.
- [ ] Every icon is an `Image(systemName:)` call (or the single custom Hippo symbol) — no PNG or SVG fallbacks in the binary.
- [ ] VoiceOver reads every row and every push button.
- [ ] Reducing motion disables the recording dot pulse and the waveform animation.

---

## 14. Out of scope (documented in PRD §10/12)

- Independent floating intervention HUD outside the popover.
- Real `cua-driver` insertion into Mail / Messages / browser forms.
- `vlmac` video preview, `basic-memory` persistence, multi-user cloud sync.
- `Project_Cortex` real backend invocation (gated behind env vars).

These should compile to placeholder views that surface their service status only; they are not part of the visual scope of this design.

---

## 15. Delivered artboards (HTML mock)

The HTML mock in `Hippo Demo.html` is the visual ground truth. Each artboard maps to a SwiftUI scene/view:

| Artboard id | Surface | SwiftUI |
| --- | --- | --- |
| `menubar-popover` | Menu bar + idle / recording popover | `MenuBarExtra(...) { StatusPopover() }` |
| `review-popover` | Menu bar + task-review popover | same `MenuBarExtra`, body = `ReviewPopover` |
| `dash-chat` | Dashboard · Chat | `DashboardWindow(route: .chat)` |
| `dash-live` | Dashboard · Live Signal | `.liveSignal` |
| `dash-task` | Dashboard · Active Task | `.activeTask` |
| `dash-sessions` | Dashboard · Sessions | `.sessions` |
| `dash-skills` | Dashboard · Skill Library | `.skill("investor-followup")` |
| `dash-settings` | Dashboard · Settings | `.settings` |
| `dash-chat-col` | Same as `dash-chat`, sidebar collapsed | `NavigationSplitViewVisibility.detailOnly` |
| `dash-task-col` | Same as `dash-task`, sidebar collapsed | ” |
| `dash-skills-col` | Same as `dash-skills`, sidebar collapsed | ” |
| `dash-sessions-col` | Same as `dash-sessions`, sidebar collapsed | ” |

Collapsed variants for Live Signal and Settings are not shipped as separate artboards — they are visually identical to the other collapsed views (sidebar removed, toggle prepended to the page title) and need no extra spec.
