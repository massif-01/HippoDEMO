/* global React, HippoShared, HippoMenuBar */
const { HippoGlyph, Icon, PushButton, SymbolButton, Hairline, AuroraBackdrop } = HippoShared;
const { MenuBar, Popover, Caption, DesktopHint, ListLabel } = HippoMenuBar;

// ──────────────────────────────────────────────────────────────────────────
// Artboard 2: Review Popover — task is ready, user must Insert / Ignore
// ──────────────────────────────────────────────────────────────────────────
function ReviewArtboard() {
  return (
    <div style={{
      position: "relative", width: "100%", height: "100%", overflow: "hidden",
      borderRadius: 12, fontFamily: '"SF Pro", -apple-system, BlinkMacSystemFont, sans-serif',
    }}>
      <AuroraBackdrop variant="warm" />
      <DesktopHint />
      <MenuBar selectedTrailing="hippo" />

      {/* Review popover — anchored under the Hippo menu extra */}
      <div style={{ position: "absolute", top: 40, right: 96, width: 340 }}>
        <Popover anchorRight={48} width={340}>
          <ReviewPopoverBody />
        </Popover>
      </div>

      <Caption>Review Popover · Task awaiting action</Caption>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Review popover body
// ──────────────────────────────────────────────────────────────────────────
function ReviewPopoverBody() {
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
          <div style={{ fontSize: 13, fontWeight: 600, lineHeight: "16px", letterSpacing: "-0.005em" }}>Ready to act</div>
          <div style={{ fontSize: 11, color: "rgba(0,0,0,0.5)", lineHeight: "14px", marginTop: 1 }}>1 task · awaiting review</div>
        </div>
        <SymbolButton glyph="􀍡" />
      </div>

      <Hairline />

      {/* Task body */}
      <div style={{ padding: "14px 14px 4px" }}>
        <div style={{
          display: "inline-flex", alignItems: "center", gap: 5,
          padding: "2px 8px", borderRadius: 100,
          background: "rgba(0,122,255,0.12)",
          marginBottom: 10,
        }}>
          <Icon name="target" size={10} color="rgb(0,122,255)" />
          <span style={{
            fontSize: 11, fontWeight: 600,
            color: "rgb(0,122,255)", letterSpacing: "-0.005em",
          }}>Active Task</span>
        </div>
        <div style={{
          fontSize: 17, fontWeight: 700, lineHeight: "22px",
          letterSpacing: "-0.02em",
          marginBottom: 6,
        }}>Insert investor follow-up draft</div>
        <div style={{
          fontSize: 13, lineHeight: "18px",
          color: "rgba(0,0,0,0.65)",
          letterSpacing: "-0.008em",
        }}>
          Reply to <b style={{ color: "rgba(0,0,0,0.85)", fontWeight: 600 }}>Hana · Ridgeline</b> confirming the cap adjustment and observer seat. Term sheet by Friday EOD.
        </div>
      </div>

      {/* Metadata strip */}
      <div style={{
        margin: "12px 14px 12px",
        padding: "10px 12px",
        borderRadius: 10,
        background: "rgba(0,0,0,0.04)",
        display: "grid", gridTemplateColumns: "1fr 1fr 1fr",
      }}>
        <MetaCell label="Surface" value="Mail" />
        <MetaCell label="Confidence" value="82%" />
        <MetaCell label="Mode" value="Mock" muted />
      </div>

      {/* Proposed actions list */}
      <div style={{ padding: "0 6px 6px" }}>
        <ListLabel>Proposed</ListLabel>
        <ActionRow num="1" name="Insert follow-up body" detail="412 chars" />
        <ActionRow num="2" name="Attach action items" detail="3 bullets" />
      </div>

      <Hairline />

      {/* Actions */}
      <div style={{ padding: "10px 14px 12px" }}>
        <div style={{ display: "flex", gap: 8, marginBottom: 6 }}>
          <PushButton variant="preferred" icon="insert" full>Insert draft</PushButton>
          <PushButton variant="neutral">Ignore</PushButton>
        </div>
        <button style={{
          width: "100%", height: 24, borderRadius: 6,
          background: "transparent", border: "0.5px solid transparent",
          fontFamily: 'inherit',
          fontSize: 12, color: "rgb(0,122,255)", fontWeight: 500,
          cursor: "pointer",
        }}>Open in Activity →</button>
      </div>
    </>
  );
}

function MetaCell({ label, value, muted }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
      <span style={{
        fontSize: 10, fontWeight: 600,
        color: "rgba(0,0,0,0.5)",
        letterSpacing: "0.04em", textTransform: "uppercase",
      }}>{label}</span>
      <span style={{
        fontSize: 12, fontWeight: 600,
        color: muted ? "rgba(0,0,0,0.5)" : "rgba(0,0,0,0.85)",
        letterSpacing: "-0.005em",
      }}>{value}</span>
    </div>
  );
}

function ActionRow({ num, name, detail }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10,
      padding: "5px 10px",
      margin: "0 4px", borderRadius: 7,
    }}>
      <div style={{
        width: 18, height: 18, borderRadius: 4,
        background: "rgba(0,0,0,0.06)",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 10, fontWeight: 700,
        color: "rgba(0,0,0,0.55)",
        fontFamily: '"SF Pro", -apple-system, sans-serif',
      }}>{num}</div>
      <span style={{ fontSize: 13, fontWeight: 500, letterSpacing: "-0.005em" }}>{name}</span>
      <div style={{ flex: 1 }} />
      <span style={{ fontSize: 11, color: "rgba(0,0,0,0.5)" }}>{detail}</span>
    </div>
  );
}

window.HippoReview = { ReviewArtboard };
