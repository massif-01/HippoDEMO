/* global React, HippoShared, HippoDashboardPages */
const { HippoGlyph, Icon, SF, material, StatusDot, PushButton, SymbolButton, Hairline } = HippoShared;
const { PageShell, Seg } = HippoDashboardPages;

// ──────────────────────────────────────────────────────────────────────────
// CHAT — agent conversation surface, modelled on Manus's empty-state layout
// ──────────────────────────────────────────────────────────────────────────
function ChatPage() {
  return (
    <PageShell
      title="Chat"
      subtitle="Hippo · local agent"
      toolbar={<>
        <Seg active={0} items={[
          { glyph: "􀒤", label: "Chat" },
          { glyph: "􀐱", label: "Recent" },
          { glyph: "􀋃", label: "Templates" },
        ]} />
        <div style={{ flex: 1 }} />
        <ModelPicker />
        <SymbolButton glyph="􀈎" size={14} />{/* compose new */}
      </>}>
      <div style={{
        height: "100%",
        display: "flex", flexDirection: "column", alignItems: "center",
        justifyContent: "center",
        padding: "32px 28px",
      }}>
        <div style={{ width: "100%", maxWidth: 720 }}>
          <SessionPill />
          <Hero />
          <Composer />
          <ConnectToolsRow />
          <SuggestionRow />
          <RecentThreads />
        </div>
      </div>
    </PageShell>
  );
}

// ─── small components ─────────────────────────────────────────────────────
function ModelPicker() {
  return (
    <button style={{
      height: 28, padding: "0 10px 0 12px", borderRadius: 100,
      background: "rgba(0,0,0,0.05)",
      border: "0.5px solid rgba(0,0,0,0.08)",
      display: "inline-flex", alignItems: "center", gap: 7,
      fontFamily: 'inherit', fontSize: 12, fontWeight: 500,
      color: "rgba(0,0,0,0.8)", cursor: "pointer",
      letterSpacing: "-0.005em",
    }}>
      <SF glyph="􀫊" size={11} weight={600} color="rgb(0,122,255)" />
      <span>Hippo Mini · local</span>
      <SF glyph="􀆈" size={9} weight={700} color="rgba(0,0,0,0.5)" />
    </button>
  );
}

function SessionPill() {
  return (
    <div style={{ textAlign: "center", marginBottom: 22 }}>
      <div style={{
        display: "inline-flex", alignItems: "center", gap: 8,
        padding: "5px 4px 5px 12px", borderRadius: 100,
        background: "rgba(0,0,0,0.04)",
        fontSize: 12, color: "rgba(0,0,0,0.6)",
      }}>
        <StatusDot state="rec" pulse size={6} />
        <span style={{ letterSpacing: "-0.005em" }}>Active session · investor sync</span>
        <button style={{
          padding: "1px 9px", borderRadius: 100,
          background: "rgba(0,122,255,0.16)",
          border: "0.5px solid transparent",
          fontFamily: 'inherit', fontSize: 11, fontWeight: 600,
          color: "rgb(0,90,200)", cursor: "pointer",
        }}>Attach</button>
      </div>
    </div>
  );
}

function Hero() {
  return (
    <h1 style={{
      margin: "0 0 24px",
      textAlign: "center",
      fontFamily: '"New York", ui-serif, Georgia, serif',
      fontSize: 42, fontWeight: 500,
      letterSpacing: "-0.02em",
      lineHeight: "48px",
      color: "rgba(0,0,0,0.9)",
    }}>What should Hippo do?</h1>
  );
}

// ─── Composer ─────────────────────────────────────────────────────────────
function Composer() {
  return (
    <div style={{
      borderRadius: 18,
      background: "rgba(255,255,255,0.92)",
      border: "0.5px solid rgba(0,0,0,0.10)",
      boxShadow: "0 1px 3px rgba(0,0,0,0.04), 0 8px 24px -8px rgba(0,0,0,0.08)",
      padding: "16px 16px 12px",
      marginBottom: 12,
    }}>
      {/* Input area */}
      <div style={{
        minHeight: 56, padding: "0 4px 14px",
        fontSize: 15, lineHeight: "22px",
        color: "rgba(0,0,0,0.4)",
        letterSpacing: "-0.008em",
      }}>Assign a task, ask Hippo to draft something, or describe what to capture next…</div>

      {/* Bottom row */}
      <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
        <ComposerCircle glyph="􀅼" />
        <ToolChipsInline />
        <ComposerCircle glyph="􀟜" />
        <div style={{ flex: 1 }} />
        <ComposerCircle glyph="􀝓" />{/* live / activity */}
        <ComposerCircle glyph="􀊰" />{/* mic */}
        <SendBtn />
      </div>
    </div>
  );
}

function ComposerCircle({ glyph }) {
  return (
    <button style={{
      width: 30, height: 30, borderRadius: 100,
      background: "transparent",
      border: "0.5px solid rgba(0,0,0,0.10)",
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      cursor: "pointer", color: "rgba(0,0,0,0.75)",
    }}>
      <SF glyph={glyph} size={13} weight={500} />
    </button>
  );
}

function SendBtn() {
  return (
    <button style={{
      width: 30, height: 30, borderRadius: 100,
      background: "rgba(0,0,0,0.08)",
      border: "none",
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      cursor: "pointer", color: "rgba(0,0,0,0.55)",
    }}>
      <SF glyph="􀄨" size={14} weight={600} />
    </button>
  );
}

function ToolChipsInline() {
  return (
    <div style={{
      display: "inline-flex", alignItems: "center",
      height: 30, padding: "0 10px 0 4px", borderRadius: 100,
      background: "rgba(0,0,0,0.04)",
      border: "0.5px solid rgba(0,0,0,0.08)",
      gap: 4,
    }}>
      <ToolDot color="rgb(255,90,80)"  glyph="􀉭" />{/* Mail */}
      <ToolDot color="rgb(48,140,255)" glyph="􀉉" />{/* Calendar */}
      <ToolDot color="rgb(30,30,30)"   glyph="􀫊" />{/* GitHub-like */}
      <span style={{
        fontSize: 11, fontWeight: 600,
        color: "rgba(0,0,0,0.6)",
        marginLeft: 4, letterSpacing: "-0.005em",
      }}>+2</span>
    </div>
  );
}

function ToolDot({ color, glyph }) {
  return (
    <div style={{
      width: 22, height: 22, borderRadius: 100,
      background: color,
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      boxShadow: "0 0 0 1.5px rgba(255,255,255,0.9)",
    }}>
      <SF glyph={glyph} size={10} weight={700} color="white" />
    </div>
  );
}

// ─── Connect tools hint ───────────────────────────────────────────────────
function ConnectToolsRow() {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10,
      padding: "8px 14px",
      borderRadius: 100,
      background: "rgba(0,0,0,0.03)",
      border: "0.5px solid rgba(0,0,0,0.06)",
      marginBottom: 20,
    }}>
      <SF glyph="􀫊" size={12} weight={500} color="rgba(0,0,0,0.55)" />
      <span style={{
        fontSize: 12, color: "rgba(0,0,0,0.6)",
        letterSpacing: "-0.005em",
      }}>Connect more tools to Hippo</span>
      <div style={{ flex: 1 }} />
      <div style={{ display: "flex", gap: 6 }}>
        <SmallToolPill color="rgb(255,90,80)"  glyph="􀉭" />
        <SmallToolPill color="rgb(48,140,255)" glyph="􀉉" />
        <SmallToolPill color="rgb(255,159,10)" glyph="􀒤" />
        <SmallToolPill color="rgb(30,30,30)"   glyph="􀫊" />
        <SmallToolPill color="rgb(48,209,88)"  glyph="􀈎" />
      </div>
      <SymbolButton glyph="􀆄" size={12} style={{ width: 20, height: 20 }} />
    </div>
  );
}

function SmallToolPill({ color, glyph }) {
  return (
    <div style={{
      width: 18, height: 18, borderRadius: 5,
      background: color,
      display: "inline-flex", alignItems: "center", justifyContent: "center",
    }}>
      <SF glyph={glyph} size={9} weight={700} color="white" />
    </div>
  );
}

// ─── Suggestion chips ─────────────────────────────────────────────────────
const SUGGESTIONS = [
  { glyph: "􀋃", label: "Generate a skill" },
  { glyph: "􀉭", label: "Draft follow-up" },
  { glyph: "􀐱", label: "Summarize last session" },
  { glyph: "􀊰", label: "Start capture" },
  { glyph: "􀫈", label: "More" },
];

function SuggestionRow() {
  return (
    <div style={{
      display: "flex", flexWrap: "wrap", gap: 8,
      justifyContent: "center",
      marginBottom: 28,
    }}>
      {SUGGESTIONS.map(s => <SuggestionChip key={s.label} {...s} />)}
    </div>
  );
}

function SuggestionChip({ glyph, label }) {
  return (
    <button style={{
      height: 32, padding: "0 14px", borderRadius: 100,
      background: "rgba(255,255,255,0.85)",
      border: "0.5px solid rgba(0,0,0,0.10)",
      display: "inline-flex", alignItems: "center", gap: 7,
      cursor: "pointer", fontFamily: 'inherit',
      fontSize: 12.5, color: "rgba(0,0,0,0.85)",
      letterSpacing: "-0.005em",
      fontWeight: 500,
    }}>
      <SF glyph={glyph} size={12} weight={500} color="rgba(0,0,0,0.6)" />
      {label}
    </button>
  );
}

// ─── Recent threads (compact list) ────────────────────────────────────────
function RecentThreads() {
  return (
    <div>
      <div style={{
        display: "flex", alignItems: "center",
        padding: "0 8px 6px",
      }}>
        <span style={{
          fontSize: 11, fontWeight: 700,
          letterSpacing: "0.04em", textTransform: "uppercase",
          color: "rgba(0,0,0,0.45)",
        }}>Recent threads</span>
        <div style={{ flex: 1 }} />
        <button style={{
          background: "transparent", border: "none",
          color: "rgb(0,122,255)", fontWeight: 500,
          fontSize: 12, cursor: "pointer", fontFamily: 'inherit',
        }}>See all</button>
      </div>
      <div style={{
        borderRadius: 12,
        background: "rgba(255,255,255,0.6)",
        border: "0.5px solid rgba(0,0,0,0.08)",
        overflow: "hidden",
      }}>
        <ThreadRow glyph="􀉭" tint="rgb(255,90,80)"
          title="Draft a reply to Hana from the Ridgeline thread"
          sub="3 turns · uses Mail · 2 min ago" />
        <ThreadRow glyph="􀋃" tint="rgb(255,159,10)"
          title="Generate a skill that posts standup notes to Linear"
          sub="7 turns · references dem_9c4 · yesterday" />
        <ThreadRow glyph="􀐱" tint="rgb(0,122,255)"
          title="Summarize the design review session"
          sub="2 turns · references dem_77b · Mon" last />
      </div>
    </div>
  );
}

function ThreadRow({ glyph, tint, title, sub, last }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 12,
      padding: "12px 14px",
      borderBottom: last ? "none" : "0.5px solid rgba(0,0,0,0.08)",
      cursor: "pointer",
    }}>
      <div style={{
        width: 28, height: 28, borderRadius: 7,
        background: `${tint}26`,
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        <SF glyph={glyph} size={13} weight={500} color={tint} />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: 13, fontWeight: 500,
          letterSpacing: "-0.005em",
          color: "rgba(0,0,0,0.9)",
          whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
        }}>{title}</div>
        <div style={{
          fontSize: 11, color: "rgba(0,0,0,0.5)",
          marginTop: 2,
        }}>{sub}</div>
      </div>
      <SF glyph="􀆊" size={11} weight={700} color="rgba(0,0,0,0.3)" />
    </div>
  );
}

window.HippoDashboardPages = window.HippoDashboardPages || {};
Object.assign(window.HippoDashboardPages, { ChatPage });
