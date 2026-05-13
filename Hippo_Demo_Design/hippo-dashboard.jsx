/* global React, HippoShared, HippoDashboardPages */
const { AuroraBackdrop, HippoGlyph, Icon, SF, material, StatusDot, TrafficLights, PushButton, SymbolButton, Hairline } = HippoShared;
const CollapsedContext = (window.HippoDashboardPages && window.HippoDashboardPages.CollapsedContext) || React.createContext(false);

// ──────────────────────────────────────────────────────────────────────────
// Dashboard shell — same window chrome for every view; view changes the
// sidebar selection + content pane.
// ──────────────────────────────────────────────────────────────────────────
function DashboardArtboard({ view = "skills", collapsed = false }) {
  return (
    <div style={{
      position: "relative", width: "100%", height: "100%", overflow: "hidden",
      borderRadius: 12, fontFamily: '"SF Pro", -apple-system, BlinkMacSystemFont, sans-serif',
    }}>
      <AuroraBackdrop variant="warm" />
      <div style={{ position: "absolute", inset: 28 }}>
        <Window view={view} collapsed={collapsed} />
      </div>
      <div style={{
        position: "absolute", left: 28, bottom: 22,
        fontSize: 11, color: "rgba(255,255,255,0.65)", letterSpacing: "0.06em",
        textTransform: "uppercase", fontWeight: 600,
      }}>{LABEL[view]}{collapsed ? " · sidebar collapsed" : ""}</div>
    </div>
  );
}

const LABEL = {
  chat: "Dashboard · Chat",
  skills: "Dashboard · Skill Library",
  live: "Dashboard · Live Signal",
  task: "Dashboard · Active Task",
  sessions: "Dashboard · Sessions",
  settings: "Dashboard · Settings",
};

function Window({ view, collapsed }) {
  return (
    <div style={{
      width: "100%", height: "100%",
      borderRadius: 16,
      overflow: "hidden",
      display: "flex",
      color: "rgba(0,0,0,0.85)",
      ...material("light"),
      boxShadow: "0 16px 60px rgba(0,0,0,0.30), 0 0 0 0.5px rgba(0,0,0,0.15)",
    }}>
      <CollapsedContext.Provider value={!!collapsed}>
        {!collapsed && <Sidebar view={view} />}
        <ContentPane view={view} />
      </CollapsedContext.Provider>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Sidebar (240 wide). Same structure across all views; selection changes.
// ──────────────────────────────────────────────────────────────────────────
function Sidebar({ view }) {
  return (
    <div style={{
      width: 240, height: "100%",
      display: "flex", flexDirection: "column",
      padding: "0 8px 8px 8px",
      background: "rgba(255,255,255,0.30)",
      backdropFilter: "saturate(180%) blur(20px)",
      borderRight: "0.5px solid rgba(0,0,0,0.08)",
    }}>
      {/* Titlebar — traffic lights + sidebar toggle (collapse) */}
      <div style={{
        height: 32, display: "flex", alignItems: "center",
        padding: "0 6px", gap: 10,
      }}>
        <TrafficLights />
        <div style={{ width: 0.5, height: 16, background: "rgba(0,0,0,0.10)" }} />
        <button style={iconBtnSm()} title="Collapse sidebar">
          <SF glyph="􀏟" size={14} weight={500} color="rgba(0,0,0,0.65)" />
        </button>
      </div>

      {/* Hippo identity row */}
      <div style={{
        display: "flex", alignItems: "center", gap: 8,
        padding: "8px 8px 14px",
      }}>
        <div style={{
          width: 22, height: 22, borderRadius: 6,
          background: "linear-gradient(135deg, oklch(78% 0.18 40), oklch(58% 0.22 18))",
          display: "flex", alignItems: "center", justifyContent: "center",
          boxShadow: "0 0.5px 0 rgba(255,255,255,0.5) inset",
        }}>
          <HippoGlyph size={14} color="white" />
        </div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 600, lineHeight: "16px", letterSpacing: "-0.005em" }}>Hippo</div>
          <div style={{
            fontSize: 11, color: "rgb(255,56,60)",
            display: "flex", alignItems: "center", gap: 4, lineHeight: "14px",
          }}>
            <StatusDot state="rec" pulse size={5} />
            <span style={{ fontVariantNumeric: "tabular-nums" }}>Recording · 04:12</span>
          </div>
        </div>
      </div>

      {/* Activity section */}
      <SidebarItem glyph="􀒤" label="Chat" pillRight="Beta" active={view === "chat"} />
      <SidebarItem glyph="􀙬" label="Live Signal" badge="12" active={view === "live"} />
      <SidebarItem glyph="􀋂" label="Active Task" badge="1" badgeAccent active={view === "task"} />
      <SidebarItem glyph="􀐱" label="Sessions" active={view === "sessions"} />

      {/* Library section — Skill Library */}
      <SectionHeader label="Library" trailing="+" />
      <SkillRow name="Investor Follow-up" sub="just now" active={view === "skills"} />
      <SkillRow name="Standup Notes Sync" sub="yesterday" />
      <SkillRow name="CRM Recap Drop" sub="Tue" />
      <SkillRow name="Design Review Captures" sub="Mon" />
      <SkillRow name="1:1 Action Items" sub="May 6" dim />
      <SkillRow name="Recruit Loop Notes" sub="May 3" dim />

      <div style={{ flex: 1 }} />

      {/* Footer — Settings + Orchestrator status */}
      <Hairline inset={-8} />
      <div style={{
        padding: "10px 8px 0",
        display: "flex", alignItems: "center", gap: 8,
      }}>
        <button
          onClick={() => {}}
          style={{
            width: 28, height: 28, borderRadius: 7,
            background: view === "settings" ? "rgba(0,0,0,0.11)" : "transparent",
            border: "0.5px solid transparent",
            display: "inline-flex", alignItems: "center", justifyContent: "center",
            cursor: "pointer",
            color: view === "settings" ? "rgb(0,122,255)" : "rgba(0,0,0,0.7)",
          }}>
          <SF glyph="􀍟" size={14} weight={500} />
        </button>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ fontSize: 11, color: "rgba(0,0,0,0.5)", lineHeight: "14px" }}>Orchestrator</div>
          <div style={{
            fontSize: 11,
            fontFamily: '"SF Mono", ui-monospace, monospace',
            color: "rgba(0,0,0,0.75)",
            display: "flex", alignItems: "center", gap: 5,
          }}>
            <StatusDot state="ok" size={5} />
            127.0.0.1:8787
          </div>
        </div>
      </div>
    </div>
  );
}

function iconBtnSm() {
  return {
    width: 22, height: 22, borderRadius: 5,
    background: "transparent", border: "none",
    display: "inline-flex", alignItems: "center", justifyContent: "center",
    cursor: "pointer",
  };
}

function SectionHeader({ label, trailing }) {
  return (
    <div style={{
      padding: "10px 12px 4px",
      display: "flex", alignItems: "center",
      fontSize: 11, fontWeight: 700,
      color: "rgba(0,0,0,0.45)",
      letterSpacing: "-0.005em",
    }}>
      <span style={{ flex: 1 }}>{label}</span>
      {trailing && (
        <button style={{
          width: 16, height: 16, borderRadius: 4,
          background: "transparent", border: "none", cursor: "pointer",
          color: "rgba(0,0,0,0.45)", fontFamily: 'inherit',
          fontSize: 13, lineHeight: 1, padding: 0,
        }}>{trailing}</button>
      )}
    </div>
  );
}

function SidebarItem({ glyph, label, badge, badgeAccent, pillRight, active }) {
  return (
    <div style={{
      height: 28, margin: "0 4px",
      borderRadius: 8,
      background: active ? "rgba(0,0,0,0.11)" : "transparent",
      display: "flex", alignItems: "center",
      padding: "0 8px", gap: 8,
      cursor: "pointer",
    }}>
      <div style={{
        width: 20, height: 16,
        display: "flex", alignItems: "center", justifyContent: "center",
        color: active ? "rgb(0,122,255)" : "rgba(0,0,0,0.65)",
      }}>
        <SF glyph={glyph} size={13} weight={500} />
      </div>
      <span style={{
        fontSize: 13, fontWeight: active ? 600 : 500,
        letterSpacing: "-0.005em",
        color: "rgba(0,0,0,0.85)",
      }}>{label}</span>
      <div style={{ flex: 1 }} />
      {pillRight && (
        <span style={{
          fontSize: 10, fontWeight: 700,
          padding: "1px 6px", borderRadius: 4,
          background: "rgba(0,122,255,0.16)",
          color: "rgb(0,90,200)",
          letterSpacing: "0.02em", textTransform: "uppercase",
        }}>{pillRight}</span>
      )}
      {badge && (
        <span style={{
          fontSize: 11, fontWeight: 600,
          padding: "1px 7px", borderRadius: 100,
          background: badgeAccent ? "rgb(0,122,255)" : "rgba(0,0,0,0.10)",
          color: badgeAccent ? "white" : "rgba(0,0,0,0.6)",
          letterSpacing: "-0.005em", lineHeight: "14px",
        }}>{badge}</span>
      )}
    </div>
  );
}

function SkillRow({ name, sub, active, dim }) {
  return (
    <div style={{
      height: 32, margin: "0 4px",
      borderRadius: 8,
      background: active ? "rgba(0,0,0,0.11)" : "transparent",
      display: "flex", alignItems: "center", gap: 8,
      padding: "0 8px",
      opacity: dim ? 0.6 : 1,
      cursor: "pointer",
    }}>
      <SF glyph="􀋃" size={13} weight={500}
        color={active ? "rgb(0,122,255)" : "rgba(0,0,0,0.6)"} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: 13, fontWeight: active ? 600 : 500,
          letterSpacing: "-0.005em",
          color: "rgba(0,0,0,0.85)",
          whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis",
        }}>{name}</div>
      </div>
      <span style={{
        fontSize: 11, color: "rgba(0,0,0,0.45)",
        letterSpacing: "-0.005em", flexShrink: 0,
      }}>{sub}</span>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// Content pane — delegates to the right page renderer
// ──────────────────────────────────────────────────────────────────────────
function ContentPane({ view }) {
  const pages = window.HippoDashboardPages || {};
  const Page = {
    chat: pages.ChatPage,
    skills: pages.SkillsPage,
    live: pages.LivePage,
    task: pages.TaskPage,
    sessions: pages.SessionsPage,
    settings: pages.SettingsPage,
  }[view];
  return (
    <div style={{
      flex: 1, minWidth: 0,
      display: "flex", flexDirection: "column",
      background: "rgba(255,255,255,0.62)",
    }}>
      {Page ? <Page /> : null}
    </div>
  );
}

window.HippoDashboard = { DashboardArtboard };
