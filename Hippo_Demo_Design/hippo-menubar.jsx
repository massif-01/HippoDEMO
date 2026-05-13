/* global React, HippoShared */
const { AuroraBackdrop, HippoGlyph, Icon, SF, material, materialBg, StatusDot, PushButton, Capsule, SymbolButton, Hairline } = HippoShared;

// ──────────────────────────────────────────────────────────────────────────
// Artboard 1: Menu Bar + Idle Popover (recording session)
// ──────────────────────────────────────────────────────────────────────────
function MenuBarArtboard() {
  return (
    <div style={{
      position: "relative", width: "100%", height: "100%", overflow: "hidden",
      borderRadius: 12, fontFamily: '"SF Pro", -apple-system, BlinkMacSystemFont, sans-serif',
    }}>
      <AuroraBackdrop variant="warm" />
      <DesktopHint />
      <MenuBar selectedTrailing="hippo" />
      <div style={{ position: "absolute", top: 40, right: 96, width: 320 }}>
        <Popover />
      </div>
      <Caption>Menu bar · Popover · Recording</Caption>
    </div>
  );
}

window.HippoMenuBar = { MenuBarArtboard, MenuBar, Caption, DesktopHint };

// ──────────────────────────────────────────────────────────────────────────
// Faint desktop window peeking behind
// ──────────────────────────────────────────────────────────────────────────
function DesktopHint() {
  return (
    <div style={{ position: "absolute", inset: 0 }}>
      <div style={{
        position: "absolute", left: -60, top: 120, width: 320, height: 360,
        ...material("light"), borderRadius: 16,
        boxShadow: "0 8px 40px rgba(0,0,0,0.12)",
        opacity: 0.7, transform: "rotate(-3deg)",
      }} />
      <div style={{
        position: "absolute", left: 30, top: 480, width: 220, height: 240,
        ...material("light"), borderRadius: 16,
        boxShadow: "0 8px 40px rgba(0,0,0,0.12)",
        opacity: 0.4, transform: "rotate(2deg)",
      }} />
    </div>
  );
}

function Caption({ children }) {
  return (
    <div style={{
      position: "absolute", left: 28, bottom: 22,
      fontFamily: '"SF Pro", -apple-system, sans-serif',
      fontSize: 11, color: "rgba(255,255,255,0.65)", letterSpacing: "0.06em",
      textTransform: "uppercase", fontWeight: 600,
    }}>{children}</div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// macOS menu bar (Figma: height 34, padding 5/10, SF Pro Bold 13 white)
// ──────────────────────────────────────────────────────────────────────────
function MenuBar({ selectedLeading, selectedTrailing }) {
  return (
    <div style={{
      position: "absolute", top: 0, left: 0, right: 0, height: 34,
      display: "flex", alignItems: "center",
      padding: "5px 10px",
      color: "rgba(255,255,255,0.95)",
      fontSize: 13,
      // Translucent over dark wallpaper, no fill — matches Apple menu bar over content
    }}>
      <MenuLeading selected={selectedLeading} />
      <div style={{ flex: 1 }} />
      <MenuTrailing selected={selectedTrailing} />
    </div>
  );
}

function MenuLeading({ selected }) {
  const apps = [
    { id: "apple", label: "", glyph: "", isApple: true, w: 33 },
    { id: "app", label: "Mail", w: 56, bold: true },
    { id: "file", label: "File", w: 44 },
    { id: "edit", label: "Edit", w: 44 },
    { id: "view", label: "View", w: 48 },
    { id: "mbox", label: "Mailbox", w: 70 },
    { id: "msg", label: "Message", w: 75 },
    { id: "fmt", label: "Format", w: 65 },
    { id: "win", label: "Window", w: 75 },
    { id: "help", label: "Help", w: 49 },
  ];
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 0 }}>
      {apps.map(a => a.isApple ? (
        <AppleMark key="apple" />
      ) : (
        <MenuItem key={a.id} label={a.label} width={a.w} bold={a.bold} selected={selected === a.id} />
      ))}
    </div>
  );
}

function AppleMark() {
  return (
    <div style={{
      width: 33, height: 24, padding: "0 11px",
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      {/* Generic mark — not the Apple logo. A subtle white diamond. */}
      <svg width={12} height={14} viewBox="0 0 12 14" fill="rgba(255,255,255,0.95)">
        <path d="M6 0.2L10.5 4.1V9.9L6 13.8L1.5 9.9V4.1L6 0.2Z" />
      </svg>
    </div>
  );
}

function MenuItem({ label, width, bold = false, selected = false }) {
  return (
    <div style={{
      position: "relative",
      width, height: 24,
      display: "flex", alignItems: "center", justifyContent: "center",
      padding: "4px 11px",
    }}>
      {selected && (
        <div style={{
          position: "absolute", inset: "-1px -4px",
          borderRadius: 100,
          background: "rgba(255,255,255,0.10)",
          backdropFilter: "blur(60px)",
          WebkitBackdropFilter: "blur(60px)",
        }} />
      )}
      <span style={{
        position: "relative",
        fontFamily: '"SF Pro", -apple-system, sans-serif',
        fontWeight: bold ? 700 : 500,
        fontSize: 13, lineHeight: "16px",
        color: "rgba(255,255,255,0.95)",
        letterSpacing: "-0.005em",
      }}>{label}</span>
    </div>
  );
}

function MenuTrailing({ selected }) {
  return (
    <div style={{ display: "flex", alignItems: "center" }}>
      <TrailingSymbol glyph="􀙇" w={32} />{/* Battery */}
      <TrailingSymbol glyph="􀙈" w={32} />{/* WiFi */}
      <TrailingSymbol glyph="􀊫" w={32} />{/* Spotlight (search) */}
      <TrailingSymbol glyph="􀜊" w={32} />{/* Control Center */}
      <HippoTrailing selected={selected === "hippo"} />
      <Clock />
    </div>
  );
}

function TrailingSymbol({ glyph, w }) {
  return (
    <div style={{
      width: w, height: 24, padding: "0 8px",
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      <SF glyph={glyph} size={14} weight={500} color="rgba(255,255,255,0.95)" />
    </div>
  );
}

// Hippo menu-extra — selected (popover open) state. NO white pill, just the
// soft capsule selection that wraps the icon, per Apple's menu-bar spec.
function HippoTrailing({ selected }) {
  return (
    <div style={{
      position: "relative",
      width: 32, height: 24, padding: "0 8px",
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      {selected && (
        <div style={{
          position: "absolute", inset: "-1px -2px",
          borderRadius: 100,
          background: "rgba(255,255,255,0.10)",
          backdropFilter: "blur(60px)",
          WebkitBackdropFilter: "blur(60px)",
        }} />
      )}
      <div style={{ position: "relative", display: "flex", alignItems: "center", gap: 3 }}>
        <HippoGlyph size={16} color="rgba(255,255,255,0.96)" />
        <StatusDot state="rec" pulse size={5} />
      </div>
    </div>
  );
}

function Clock() {
  return (
    <div style={{
      height: 24, padding: "0 10px 0 12px",
      display: "flex", alignItems: "center", gap: 6,
    }}>
      <span style={{
        fontFamily: '"SF Pro", -apple-system, sans-serif',
        fontSize: 13, fontWeight: 500,
        color: "rgba(255,255,255,0.95)",
        fontVariantNumeric: "tabular-nums",
        letterSpacing: "-0.005em",
      }}>Wed 9:47 AM</span>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Popover (Apple Liquid Glass — light material, with arrow notch)
// Figma node 121:11340: Fill rgba(255,255,255,0.7) over rgba(250,250,250,0.2)
// Shadow: 0 4px 20px rgba(0,0,0,0.15), 0 0 2.5px rgba(0,0,0,0.5)
// ──────────────────────────────────────────────────────────────────────────
function Popover({ children, anchorRight = 48, width = 320 }) {
  return (
    <div style={{ width, position: "relative" }}>
      <div style={{
        ...material("light"),
        borderRadius: 18,
        boxShadow: "0 4px 20px rgba(0,0,0,0.15), 0 0 0 0.5px rgba(0,0,0,0.10)",
        color: "rgba(0,0,0,0.85)",
        overflow: "hidden",
      }}>
        {children || <DefaultPopoverBody />}
      </div>
    </div>
  );
}
window.HippoMenuBar.Popover = Popover;

function DefaultPopoverBody() {
  return (
    <>
      {/* Header */}
      <div style={{ padding: "12px 14px 10px", display: "flex", alignItems: "center", gap: 10 }}>
        <div style={{
          width: 28, height: 28, borderRadius: 7,
          background: "linear-gradient(135deg, oklch(78% 0.18 40), oklch(58% 0.22 18))",
          display: "flex", alignItems: "center", justifyContent: "center",
          boxShadow: "0 0.5px 0 rgba(255,255,255,0.5) inset, 0 1px 3px rgba(0,0,0,0.1)",
        }}>
          <HippoGlyph size={18} color="white" />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 600, letterSpacing: "-0.005em", lineHeight: "16px" }}>Hippo</div>
          <div style={{ fontSize: 11, color: "rgba(0,0,0,0.5)", lineHeight: "14px", marginTop: 1 }}>Investor sync · 04:12</div>
        </div>
        <SymbolButton glyph="􀍡" />
      </div>

      <Hairline inset={0} />

      {/* Status */}
      <div style={{ padding: "12px 14px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12, marginBottom: 14 }}>
          <Waveform />
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 13, fontWeight: 600, lineHeight: "16px" }}>Listening</div>
            <div style={{ fontSize: 11, color: "rgba(0,0,0,0.5)", lineHeight: "14px", marginTop: 1 }}>Audio + window context</div>
          </div>
          <div style={{
            fontSize: 17, fontWeight: 600,
            fontVariantNumeric: "tabular-nums",
            letterSpacing: "-0.02em",
          }}>04:12</div>
        </div>
        <div style={{ display: "flex", gap: 8 }}>
          <PushButton variant="destructive" icon="stop" full>Stop Jarvis</PushButton>
          <PushButton variant="neutral" icon="pin">Capture</PushButton>
        </div>
      </div>

      <Hairline inset={0} />

      {/* Services */}
      <div style={{ padding: "8px 6px" }}>
        <ListLabel>Services</ListLabel>
        <ListRow glyph="􀐫" name="OpenChronicle" detail="Capture · timeline" state="ok" />
        <ListRow glyph="􀊰" name="ownscribe" detail="Recording · 04:12" state="rec" pulse />
        <ListRow glyph="􀇲" name="cua-driver" detail="Mock" state="idle" />
        <ListRow glyph="􀒮" name="vlmac" detail="Standby" state="idle" />
      </div>

      <Hairline inset={0} />

      {/* Footer */}
      <div style={{
        display: "flex", alignItems: "center", padding: "6px 8px", gap: 2,
      }}>
        <SymbolButton glyph="􀋲" />{/* activity */}
        <SymbolButton glyph="􀉟" />{/* book / library */}
        <SymbolButton glyph="􀍟" />{/* gear */}
        <div style={{ flex: 1 }} />
        <span style={{
          fontSize: 11, color: "rgba(0,0,0,0.45)",
          padding: "0 6px",
        }}>EN</span>
        <SymbolButton glyph="􀅈" />{/* refresh */}
      </div>
    </>
  );
}

function ListLabel({ children }) {
  return (
    <div style={{
      padding: "4px 12px",
      fontSize: 10, fontWeight: 700,
      color: "rgba(0,0,0,0.5)",
      letterSpacing: "0.05em", textTransform: "uppercase",
    }}>{children}</div>
  );
}

function ListRow({ glyph, icon, name, detail, state, pulse }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10,
      padding: "6px 10px",
      margin: "0 4px", borderRadius: 8,
    }}>
      <div style={{
        width: 20, height: 20,
        display: "flex", alignItems: "center", justifyContent: "center",
        color: "rgba(0,0,0,0.65)",
      }}>
        {glyph ? <SF glyph={glyph} size={14} weight={500} /> : <Icon name={icon} size={13} />}
      </div>
      <span style={{ fontSize: 13, fontWeight: 500, letterSpacing: "-0.005em" }}>{name}</span>
      <div style={{ flex: 1 }} />
      <span style={{ fontSize: 11, color: "rgba(0,0,0,0.5)" }}>{detail}</span>
      <StatusDot state={state} pulse={pulse} size={6} />
    </div>
  );
}
window.HippoMenuBar.ListLabel = ListLabel;
window.HippoMenuBar.ListRow = ListRow;

function Waveform() {
  const bars = [3, 7, 5, 9, 11, 8, 13, 10, 6, 12, 9, 5, 11];
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 2.5, height: 28, width: 50 }}>
      {bars.map((h, i) => (
        <div key={i} style={{
          width: 2.5, height: h * 1.8,
          background: "linear-gradient(180deg, rgb(255,90,80), rgb(220,40,30))",
          borderRadius: 1.5,
          animation: `hippo-wave 1.2s ease-in-out ${i * 0.04}s infinite alternate`,
        }} />
      ))}
    </div>
  );
}
window.HippoMenuBar.Waveform = Waveform;
