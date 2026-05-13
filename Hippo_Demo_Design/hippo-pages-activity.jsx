/* global React, HippoShared, HippoDashboardPages */
const { HippoGlyph, Icon, SF, material, StatusDot, PushButton, SymbolButton, Hairline } = HippoShared;
const { PageShell, SearchField, Seg } = HippoDashboardPages;

// ──────────────────────────────────────────────────────────────────────────
// LIVE SIGNAL — event timeline
// ──────────────────────────────────────────────────────────────────────────
function LivePage() {
  return (
    <PageShell
      title="Live Signal"
      subtitle="Investor sync · 80 events"
      toolbar={<>
        <Seg active={0} items={[
          { label: "All" },
          { label: "Signals" },
          { label: "Tasks" },
          { label: "Artifacts" },
        ]} />
        <div style={{ flex: 1 }} />
        <span style={{
          display: "inline-flex", alignItems: "center", gap: 6,
          fontSize: 12, color: "rgba(0,0,0,0.55)",
          padding: "0 6px",
        }}>
          <StatusDot state="ok" pulse size={6} />
          SSE · /events
        </span>
        <SearchField width={180} placeholder="Filter events" kbd={null} />
        <SymbolButton glyph="􀅈" size={14} />
      </>}>
      <div style={{ padding: "16px 24px 24px" }}>
        <TimelineGroup title="Investor sync" status="active" duration="04:12 · live">
          <Event time="09:47:02" type="task" title="Active Task generated" body="Insert investor follow-up draft" meta="task_id: act_7f3 · status: AWAITING_REVIEW" />
          <Event time="09:46:58" type="artifact" title="meeting_minutes generated" body="3 action items · 1 follow-up body · summary 412w" meta="source: ownscribe + Cortex" />
          <Event time="09:46:54" type="asr" title="Transcript finalized" body="04:08 of audio · 1,284 tokens via openai-compatible" meta="model: whisper-large-v3" />
          <Event time="09:46:30" type="sop" title="Skill capture closed" body="Captured 02:18 between check_in / check_out" meta="mode: mock" warn />
          <Event time="09:44:12" type="sop" title="Skill capture started" body="User marked check_in" />
          <Event time="09:42:50" type="session" title="Jarvis ON" body="DemoSession dem_a91 · OpenChronicle started · ownscribe recording" meta="state: meeting_active" />
        </TimelineGroup>

        <TimelineGroup title="Eng standup" status="done" duration="yesterday · 18:32" collapsed />
        <TimelineGroup title="Design review" status="done" duration="Mon 14:00 · 47:18" collapsed />
      </div>
    </PageShell>
  );
}

function TimelineGroup({ title, status, duration, children, collapsed }) {
  return (
    <div style={{ marginBottom: 18 }}>
      <div style={{
        display: "flex", alignItems: "center", gap: 8,
        padding: "8px 4px",
      }}>
        <SF glyph={collapsed ? "􀆊" : "􀆈"} size={11} weight={700} color="rgba(0,0,0,0.4)" />
        <span style={{ fontSize: 13, fontWeight: 600, letterSpacing: "-0.005em" }}>{title}</span>
        {status === "active" && (
          <span style={{
            display: "inline-flex", alignItems: "center", gap: 4,
            padding: "1px 7px", borderRadius: 100,
            background: "rgba(255,56,60,0.12)",
            color: "rgb(255,56,60)",
            fontSize: 10.5, fontWeight: 600,
            letterSpacing: "-0.005em",
          }}>
            <StatusDot state="rec" pulse size={5} /> Active
          </span>
        )}
        <div style={{ flex: 1 }} />
        <span style={{ fontSize: 11, color: "rgba(0,0,0,0.5)", fontVariantNumeric: "tabular-nums" }}>{duration}</span>
      </div>
      {!collapsed && (
        <div style={{
          borderRadius: 10,
          background: "rgba(255,255,255,0.62)",
          border: "0.5px solid rgba(0,0,0,0.08)",
          overflow: "hidden",
        }}>{children}</div>
      )}
    </div>
  );
}

const EVENT_TYPE = {
  task:     { glyph: "􀋂", color: "rgb(0,122,255)" },
  artifact: { glyph: "􀉅", color: "rgb(48,209,88)" },
  asr:      { glyph: "􀊰", color: "rgb(48,209,88)" },
  sop:      { glyph: "􀎫", color: "rgb(255,159,10)" },
  session:  { glyph: "􀐫", color: "rgb(255,56,60)" },
};

function Event({ time, type, title, body, meta, warn }) {
  const t = EVENT_TYPE[type];
  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "70px 24px 1fr",
      gap: 12,
      padding: "12px 16px",
      alignItems: "flex-start",
      borderBottom: "0.5px solid rgba(0,0,0,0.06)",
    }}>
      <span style={{
        fontFamily: '"SF Mono", ui-monospace, monospace',
        fontSize: 11, color: "rgba(0,0,0,0.5)",
        paddingTop: 2, letterSpacing: "-0.005em",
      }}>{time}</span>
      <div style={{
        width: 22, height: 22, borderRadius: 5,
        background: `${t.color}1f`,
        display: "flex", alignItems: "center", justifyContent: "center",
        marginTop: 1,
      }}>
        <SF glyph={t.glyph} size={12} weight={600} color={t.color} />
      </div>
      <div style={{ minWidth: 0 }}>
        <div style={{
          fontSize: 13, fontWeight: 600,
          letterSpacing: "-0.005em",
          color: "rgba(0,0,0,0.9)",
        }}>{title}</div>
        <div style={{
          fontSize: 12.5, color: "rgba(0,0,0,0.7)",
          lineHeight: "18px", marginTop: 1,
          letterSpacing: "-0.005em",
        }}>{body}</div>
        {meta && (
          <div style={{
            fontSize: 11, fontFamily: '"SF Mono", ui-monospace, monospace',
            color: "rgba(0,0,0,0.45)", marginTop: 4,
            letterSpacing: "-0.005em",
          }}>{meta}</div>
        )}
      </div>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// ACTIVE TASK
// ──────────────────────────────────────────────────────────────────────────
function TaskPage() {
  return (
    <PageShell
      title="Active Task"
      toolbar={<>
        <Seg active={0} items={[
          { label: "Awaiting", badge: 1 },
          { label: "Completed" },
          { label: "Ignored" },
        ]} />
        <div style={{ flex: 1 }} />
        <PushButton variant="neutral">Ignore</PushButton>
        <PushButton variant="preferred" icon="insert">Insert draft</PushButton>
      </>}>
      <div style={{ padding: "24px 28px 28px", maxWidth: 820, margin: "0 auto" }}>
        <TaskHero />
        <TaskMeta />
        <TaskActions />
        <RecentTasks />
      </div>
    </PageShell>
  );
}

function TaskHero() {
  return (
    <div style={{ marginBottom: 24 }}>
      <div style={{
        display: "inline-flex", alignItems: "center", gap: 5,
        padding: "2px 9px", borderRadius: 100,
        background: "rgba(0,122,255,0.12)",
        marginBottom: 10,
      }}>
        <SF glyph="􀋂" size={11} weight={600} color="rgb(0,122,255)" />
        <span style={{ fontSize: 11, fontWeight: 600, color: "rgb(0,122,255)", letterSpacing: "-0.005em" }}>
          Awaiting review
        </span>
      </div>
      <h1 style={{
        margin: "0 0 8px",
        fontSize: 28, fontWeight: 700,
        letterSpacing: "-0.02em", lineHeight: "32px",
        color: "rgba(0,0,0,0.92)",
      }}>Insert investor follow-up draft</h1>
      <p style={{
        margin: 0, fontSize: 15, lineHeight: "22px",
        letterSpacing: "-0.008em",
        color: "rgba(0,0,0,0.65)",
        maxWidth: 620,
      }}>
        Reply to <b style={{ color: "rgba(0,0,0,0.85)", fontWeight: 600 }}>Hana · Ridgeline</b> confirming the cap adjustment and observer seat. Term sheet by Friday EOD.
      </p>
    </div>
  );
}

function TaskMeta() {
  return (
    <div style={{
      display: "grid", gridTemplateColumns: "repeat(4, 1fr)",
      gap: 0, marginBottom: 24,
      borderRadius: 10,
      background: "rgba(255,255,255,0.7)",
      border: "0.5px solid rgba(0,0,0,0.08)",
      padding: "12px 0",
    }}>
      <MetaCell label="Surface" value="Mail · draft" />
      <MetaCell label="Confidence" value="82%" />
      <MetaCell label="Source" value="dem_a91" mono />
      <MetaCell label="Insertion" value="Mock" muted />
    </div>
  );
}

function MetaCell({ label, value, mono, muted }) {
  return (
    <div style={{
      padding: "0 16px",
      borderLeft: "0.5px solid rgba(0,0,0,0.08)",
    }}>
      <div style={{
        fontSize: 10, fontWeight: 600,
        letterSpacing: "0.04em", textTransform: "uppercase",
        color: "rgba(0,0,0,0.5)",
        marginBottom: 4,
      }}>{label}</div>
      <div style={{
        fontSize: 14, fontWeight: 600,
        color: muted ? "rgba(0,0,0,0.55)" : "rgba(0,0,0,0.9)",
        letterSpacing: "-0.008em",
        fontFamily: mono ? '"SF Mono", ui-monospace, monospace' : 'inherit',
      }}>{value}</div>
    </div>
  );
}

function TaskActions() {
  return (
    <div style={{ marginBottom: 28 }}>
      <div style={{
        fontSize: 11, fontWeight: 600,
        letterSpacing: "0.04em", textTransform: "uppercase",
        color: "rgba(0,0,0,0.5)",
        padding: "0 4px 6px",
      }}>Proposed actions</div>
      <div style={{
        borderRadius: 10,
        background: "rgba(255,255,255,0.7)",
        border: "0.5px solid rgba(0,0,0,0.08)",
        overflow: "hidden",
      }}>
        <ActionRow num="1" title="Insert follow-up body" detail="Reply to ridgeline thread · 412 chars" />
        <ActionRow num="2" title="Attach action items" detail="Append 3 bullets to message" last />
      </div>
    </div>
  );
}

function ActionRow({ num, title, detail, last }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 14,
      padding: "12px 16px",
      borderBottom: last ? "none" : "0.5px solid rgba(0,0,0,0.08)",
    }}>
      <div style={{
        width: 22, height: 22, borderRadius: 5,
        background: "rgba(0,0,0,0.06)",
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: 11, fontWeight: 700,
        color: "rgba(0,0,0,0.6)",
      }}>{num}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 600, letterSpacing: "-0.005em" }}>{title}</div>
        <div style={{ fontSize: 12, color: "rgba(0,0,0,0.55)", marginTop: 2 }}>{detail}</div>
      </div>
      <span style={{
        fontSize: 11, fontWeight: 600,
        padding: "2px 8px", borderRadius: 100,
        background: "rgba(48,209,88,0.16)",
        color: "rgb(30,140,60)",
      }}>Ready</span>
    </div>
  );
}

function RecentTasks() {
  return (
    <div>
      <div style={{
        fontSize: 11, fontWeight: 600,
        letterSpacing: "0.04em", textTransform: "uppercase",
        color: "rgba(0,0,0,0.5)",
        padding: "0 4px 6px",
      }}>Recent</div>
      <div style={{
        borderRadius: 10,
        background: "rgba(255,255,255,0.7)",
        border: "0.5px solid rgba(0,0,0,0.08)",
        overflow: "hidden",
      }}>
        <RecentRow title="Post standup recap to Linear" sub="Eng standup · yesterday" state="completed" />
        <RecentRow title="Drop design review summary into Figma" sub="Design review · Mon" state="completed" />
        <RecentRow title="Send 1:1 recap to Hana" sub="1:1 — Hana · May 6" state="ignored" last />
      </div>
    </div>
  );
}

function RecentRow({ title, sub, state, last }) {
  const stateMap = {
    completed: { bg: "rgba(48,209,88,0.16)", color: "rgb(30,140,60)", label: "Completed" },
    ignored: { bg: "rgba(0,0,0,0.06)", color: "rgba(0,0,0,0.55)", label: "Ignored" },
  }[state];
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 14,
      padding: "12px 16px",
      borderBottom: last ? "none" : "0.5px solid rgba(0,0,0,0.08)",
    }}>
      <SF glyph="􀋂" size={13} weight={500} color="rgba(0,0,0,0.5)" />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 500, letterSpacing: "-0.005em" }}>{title}</div>
        <div style={{ fontSize: 11, color: "rgba(0,0,0,0.5)", marginTop: 1 }}>{sub}</div>
      </div>
      <span style={{
        fontSize: 11, fontWeight: 600,
        padding: "2px 8px", borderRadius: 100,
        background: stateMap.bg, color: stateMap.color,
      }}>{stateMap.label}</span>
    </div>
  );
}

// ──────────────────────────────────────────────────────────────────────────
// SESSIONS — list of past sessions
// ──────────────────────────────────────────────────────────────────────────
function SessionsPage() {
  return (
    <PageShell
      title="Sessions"
      toolbar={<>
        <Seg active={0} items={[
          { label: "All" }, { label: "Active" }, { label: "Archived" },
        ]} />
        <div style={{ flex: 1 }} />
        <SearchField width={200} placeholder="Search sessions" kbd={null} />
        <SymbolButton glyph="􀅈" size={14} />
      </>}>
      <div style={{ padding: "16px 24px 24px" }}>
        {/* Table header */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "1fr 110px 90px 90px 110px 28px",
          gap: 14, padding: "0 12px 8px",
          fontSize: 10, fontWeight: 700,
          letterSpacing: "0.04em", textTransform: "uppercase",
          color: "rgba(0,0,0,0.45)",
        }}>
          <span>Session</span>
          <span>Started</span>
          <span style={{ textAlign: "right" }}>Duration</span>
          <span style={{ textAlign: "right" }}>Artifacts</span>
          <span>State</span>
          <span />
        </div>

        <div style={{
          borderRadius: 10,
          background: "rgba(255,255,255,0.7)",
          border: "0.5px solid rgba(0,0,0,0.08)",
          overflow: "hidden",
        }}>
          <SessionRow active title="Investor sync" sid="dem_a91" started="09:42 AM" duration="04:12" artifacts={4} state="task" />
          <SessionRow title="Eng standup" sid="dem_9c4" started="Yesterday 10:30" duration="18:32" artifacts={2} state="completed" />
          <SessionRow title="Design review" sid="dem_77b" started="Mon 2:00 PM" duration="47:18" artifacts={6} state="completed" />
          <SessionRow title="1:1 — Hana" sid="dem_4f1" started="May 6" duration="32:04" artifacts={3} state="completed" />
          <SessionRow title="Recruit loop — Eng" sid="dem_22e" started="May 3" duration="58:42" artifacts={5} state="completed" />
          <SessionRow title="Customer call — Acme" sid="dem_0d8" started="Apr 28" duration="24:11" artifacts={3} state="ignored" last />
        </div>
      </div>
    </PageShell>
  );
}

function SessionRow({ title, sid, started, duration, artifacts, state, active, last }) {
  const stateMap = {
    task: { bg: "rgba(0,122,255,0.16)", color: "rgb(0,90,200)", label: "Active Task" },
    completed: { bg: "rgba(48,209,88,0.16)", color: "rgb(30,140,60)", label: "Completed" },
    ignored: { bg: "rgba(0,0,0,0.06)", color: "rgba(0,0,0,0.55)", label: "Ignored" },
  }[state];
  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "1fr 110px 90px 90px 110px 28px",
      gap: 14, padding: "12px 16px",
      alignItems: "center",
      background: active ? "rgba(0,0,0,0.04)" : "transparent",
      borderBottom: last ? "none" : "0.5px solid rgba(0,0,0,0.08)",
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
        <SF glyph="􀐫" size={14} weight={500} color={active ? "rgb(0,122,255)" : "rgba(0,0,0,0.55)"} />
        <div style={{ minWidth: 0 }}>
          <div style={{ fontSize: 13, fontWeight: 600, letterSpacing: "-0.005em", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{title}</div>
          <div style={{
            fontSize: 11, color: "rgba(0,0,0,0.5)",
            fontFamily: '"SF Mono", ui-monospace, monospace',
            marginTop: 1, letterSpacing: "-0.005em",
          }}>{sid}</div>
        </div>
      </div>
      <span style={{ fontSize: 12, color: "rgba(0,0,0,0.7)" }}>{started}</span>
      <span style={{ fontSize: 12, color: "rgba(0,0,0,0.7)", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{duration}</span>
      <span style={{ fontSize: 12, color: "rgba(0,0,0,0.7)", textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{artifacts}</span>
      <span style={{
        fontSize: 11, fontWeight: 600,
        padding: "2px 8px", borderRadius: 100,
        background: stateMap.bg, color: stateMap.color,
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        width: "fit-content",
      }}>{stateMap.label}</span>
      <SF glyph="􀆊" size={11} weight={700} color="rgba(0,0,0,0.35)" />
    </div>
  );
}

window.HippoDashboardPages = window.HippoDashboardPages || {};
Object.assign(window.HippoDashboardPages, {
  LivePage, TaskPage, SessionsPage,
});
