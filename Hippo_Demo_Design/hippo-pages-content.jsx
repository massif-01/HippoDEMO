/* global React, HippoShared, HippoDashboardPages */
const { HippoGlyph, Icon, SF, material, StatusDot, PushButton, SymbolButton, Hairline } = HippoShared;
const { PageShell, SearchField, Seg, FormSection, FormRow } = HippoDashboardPages;

// ──────────────────────────────────────────────────────────────────────────
// SKILLS — markdown viewer for the selected skill (Investor Follow-up)
// ──────────────────────────────────────────────────────────────────────────
function SkillsPage() {
  return (
    <PageShell
      title="Investor Follow-up"
      subtitle="SKILL.md · 3.2 KB"
      toolbar={<>
        <Seg active={0} items={[{ glyph: "􀈎" }, { glyph: "􀙬" }]} />
        <span style={{ fontSize: 12, color: "rgba(0,0,0,0.5)" }}>Preview · Source</span>
        <div style={{ flex: 1 }} />
        <SearchField width={200} placeholder="Search skills" />
        <PushButton variant="neutral" icon="sparkles">Generate</PushButton>
        <PushButton variant="preferred" icon="play">Run skill</PushButton>
      </>}>
      <div style={{ padding: "28px 40px 40px" }}>
        <div style={{ maxWidth: 720, margin: "0 auto" }}>
          <SkillHeader />
          <SkillBody />
        </div>
      </div>
    </PageShell>
  );
}

function SkillHeader() {
  return (
    <>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
        <div style={{
          width: 24, height: 24, borderRadius: 6,
          background: "rgba(0,122,255,0.12)",
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <SF glyph="􀋃" size={13} weight={500} color="rgb(0,122,255)" />
        </div>
        <span style={{ fontSize: 12, fontWeight: 600, color: "rgb(0,122,255)", letterSpacing: "-0.005em" }}>
          SKILL · Investor follow-up
        </span>
        <span style={{
          fontSize: 11, fontWeight: 500,
          padding: "1px 7px", borderRadius: 4,
          background: "rgba(255,159,10,0.16)",
          color: "rgb(178,116,0)",
          letterSpacing: "0.02em", textTransform: "uppercase",
        }}>mock</span>
      </div>

      <h1 style={{
        margin: "0 0 6px",
        fontSize: 32, fontWeight: 800,
        letterSpacing: "-0.025em", lineHeight: "36px",
        color: "rgba(0,0,0,0.92)",
      }}>Investor Follow-up</h1>

      <p style={{
        margin: "0 0 8px",
        fontSize: 15, lineHeight: "22px",
        color: "rgba(0,0,0,0.65)",
        letterSpacing: "-0.008em",
        maxWidth: 580,
      }}>Detect a thank-you commitment with concrete deliverables, draft the reply against the active mail thread, and attach the action items.</p>

      <div style={{
        display: "flex", gap: 16,
        margin: "20px 0 28px",
        fontSize: 12, color: "rgba(0,0,0,0.55)",
        letterSpacing: "-0.005em",
      }}>
        <MetaInline label="Source" value="dem_a91" mono />
        <MetaInline label="Created" value="Today 09:47" />
        <MetaInline label="Size" value="3.2 KB" />
        <MetaInline label="Generator" value="Cortex (mock)" />
      </div>
    </>
  );
}

function MetaInline({ label, value, mono }) {
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>
      <span style={{
        fontSize: 10, fontWeight: 600,
        letterSpacing: "0.04em", textTransform: "uppercase",
        color: "rgba(0,0,0,0.5)",
      }}>{label}</span>
      <span style={{
        fontSize: 13, fontWeight: 500,
        letterSpacing: "-0.005em",
        color: "rgba(0,0,0,0.85)",
        fontFamily: mono ? '"SF Mono", ui-monospace, monospace' : 'inherit',
      }}>{value}</span>
    </div>
  );
}

function SkillBody() {
  return (
    <>
      <H2>Trigger</H2>
      <P>Speaker commits to <Em>"send a follow-up by Friday"</Em> with at least one specific deliverable in a meeting where Mail or a thread surface is active.</P>

      <H2>Steps</H2>
      <ol style={{ margin: "8px 0 16px", paddingLeft: 22 }}>
        <Li><B>Resolve recipient.</B> Map the speaker's spoken name to the active Mail draft's <Code>To:</Code> field.</Li>
        <Li><B>Draft body.</B> Open with thanks, restate the two deliverables verbatim, propose a date by close-of-Friday.</Li>
        <Li><B>Attach action items.</B> Append a compact bullet list under <Code>Action items</Code>.</Li>
        <Li><B>Request review.</B> Surface the draft to the user. <Em>Never send automatically.</Em></Li>
      </ol>

      <div style={{
        margin: "14px 0",
        padding: "12px 16px",
        borderRadius: 12,
        background: "rgba(255,159,10,0.10)",
        border: "0.5px solid rgba(255,159,10,0.3)",
        display: "flex", alignItems: "flex-start", gap: 10,
        fontSize: 14, lineHeight: "20px",
        color: "rgba(0,0,0,0.85)",
        letterSpacing: "-0.008em",
      }}>
        <SF glyph="􀇿" size={14} weight={500} color="rgb(178,116,0)" />
        <span>Insertion is <B>mocked</B>. This skill marks <Code>proposed_action.state = inserted_mock</Code>; cua-driver execution is not on the main path.</span>
      </div>

      <H2>Example draft</H2>
      <pre style={{
        margin: "8px 0 0", padding: "16px 18px",
        background: "rgba(0,0,0,0.04)",
        border: "0.5px solid rgba(0,0,0,0.08)",
        borderRadius: 10,
        fontFamily: '"SF Mono", ui-monospace, monospace',
        fontSize: 12.5, lineHeight: "18px",
        color: "rgba(0,0,0,0.85)",
        letterSpacing: "-0.005em",
        whiteSpace: "pre-wrap",
      }}>{`Subject: Re: Ridgeline — term sheet

Hi Hana,

Thanks for the time today. Confirming the two
adjustments we agreed on:

  • Cap moved to $24M post.
  • Board observer seat reserved for Ridgeline
    until Series A close.

I'll send a redlined term sheet by Friday EOD.

— Massif`}</pre>
    </>
  );
}

const H2 = ({ children }) => (
  <h2 style={{
    margin: "20px 0 8px",
    fontSize: 11, fontWeight: 700,
    letterSpacing: "0.06em", textTransform: "uppercase",
    color: "rgba(0,0,0,0.5)",
  }}>{children}</h2>
);
const P = ({ children }) => (
  <p style={{
    margin: "0 0 8px",
    fontSize: 14, lineHeight: "22px",
    letterSpacing: "-0.008em",
    color: "rgba(0,0,0,0.85)",
  }}>{children}</p>
);
const Em = ({ children }) => <em style={{ color: "rgb(0,122,255)", fontStyle: "normal", fontWeight: 500 }}>{children}</em>;
const B = ({ children }) => <strong style={{ fontWeight: 700 }}>{children}</strong>;
const Code = ({ children }) => (
  <code style={{
    fontFamily: '"SF Mono", ui-monospace, monospace',
    fontSize: 12, padding: "1px 5px", borderRadius: 4,
    background: "rgba(0,0,0,0.05)",
    color: "rgba(0,0,0,0.85)",
    letterSpacing: "-0.005em",
  }}>{children}</code>
);
const Li = ({ children }) => (
  <li style={{
    fontSize: 14, lineHeight: "22px",
    margin: "5px 0",
    letterSpacing: "-0.008em",
    color: "rgba(0,0,0,0.85)",
  }}>{children}</li>
);

// ──────────────────────────────────────────────────────────────────────────
// SETTINGS — Apple System Settings style: grouped inset forms
// ──────────────────────────────────────────────────────────────────────────
function SettingsPage() {
  return (
    <PageShell
      title="Settings"
      subtitle="Developer Console"
      toolbar={<>
        <Seg active={0} items={[
          { label: "General" },
          { label: "Services" },
          { label: "Recording" },
          { label: "Permissions" },
          { label: "About" },
        ]} />
        <div style={{ flex: 1 }} />
        <SymbolButton glyph="􀅈" size={14} />
      </>}>
      <div style={{ padding: "24px 32px 32px", maxWidth: 760, margin: "0 auto" }}>
        <OrchestratorSection />
        <ServicesSection />
        <OpenChronicleSection />
        <PermissionsSection />
        <AboutSection />
      </div>
    </PageShell>
  );
}

// ─── Form controls ─────────────────────────────────────────────────────────
function Toggle({ on }) {
  return (
    <span style={{
      width: 36, height: 22, borderRadius: 100,
      background: on ? "rgb(48,209,88)" : "rgba(0,0,0,0.18)",
      position: "relative",
      transition: "background 0.15s",
      flexShrink: 0,
    }}>
      <span style={{
        position: "absolute", top: 1, left: on ? 15 : 1,
        width: 20, height: 20, borderRadius: "50%",
        background: "white",
        boxShadow: "0 0 0 0.5px rgba(0,0,0,0.06), 0 2px 4px rgba(0,0,0,0.18)",
      }} />
    </span>
  );
}

function PopUpButton({ value }) {
  return (
    <button style={{
      height: 24, padding: "0 8px 0 10px", borderRadius: 6,
      background: "rgba(255,255,255,0.95)",
      border: "0.5px solid rgba(0,0,0,0.10)",
      boxShadow: "0 0.5px 0 rgba(255,255,255,0.6) inset, 0 1px 1.5px rgba(0,0,0,0.06)",
      display: "inline-flex", alignItems: "center", gap: 6,
      fontFamily: 'inherit', fontSize: 13, color: "rgba(0,0,0,0.85)",
      cursor: "pointer", letterSpacing: "-0.005em",
    }}>
      <span>{value}</span>
      <SF glyph="􀆈" size={9} weight={700} color="rgba(0,0,0,0.5)" />
    </button>
  );
}

function TextField({ value, width = 200, mono }) {
  return (
    <div style={{
      height: 24, width, padding: "0 8px",
      borderRadius: 6,
      background: "rgba(255,255,255,0.95)",
      border: "0.5px solid rgba(0,0,0,0.10)",
      boxShadow: "0 0.5px 0 rgba(255,255,255,0.6) inset, 0 1px 1.5px rgba(0,0,0,0.04) inset",
      display: "flex", alignItems: "center",
      fontFamily: mono ? '"SF Mono", ui-monospace, monospace' : 'inherit',
      fontSize: 12.5, color: "rgba(0,0,0,0.85)",
      letterSpacing: "-0.005em",
    }}>{value}</div>
  );
}

// ─── Sections ──────────────────────────────────────────────────────────────
function OrchestratorSection() {
  return (
    <FormSection title="Orchestrator" footnote="Hippo will launch a local Orchestrator if this address is unreachable.">
      <FormRow label="Base URL" sub="FastAPI on 127.0.0.1:8787"
        control={<TextField value="http://127.0.0.1:8787" width={240} mono />} />
      <FormRow label="Status"
        control={
          <span style={{
            display: "inline-flex", alignItems: "center", gap: 6,
            fontSize: 12.5, color: "rgba(0,0,0,0.85)",
          }}>
            <StatusDot state="ok" size={7} /> Connected · 200 events buffered
          </span>
        } />
      <FormRow label="Auto-launch on app start" control={<Toggle on />} last />
    </FormSection>
  );
}

function ServicesSection() {
  return (
    <FormSection title="Services">
      <ServiceFormRow name="OpenChronicle" detail="Capture · timeline · index" state="ok" version="v1.0" />
      <ServiceFormRow name="ownscribe" detail="Recording 04:12 · display-audio helper" state="rec" version="v1.0" pulse />
      <ServiceFormRow name="cua-driver" detail="Mock placeholder · insertion not real" state="idle" version="–" />
      <ServiceFormRow name="vlmac" detail="Video capture not in main path" state="idle" version="–" last />
    </FormSection>
  );
}

function ServiceFormRow({ name, detail, state, version, pulse, last }) {
  return (
    <div style={{
      display: "flex", alignItems: "center",
      minHeight: 52, padding: "10px 14px",
      borderBottom: last ? "none" : "0.5px solid rgba(0,0,0,0.08)",
      gap: 12,
    }}>
      <StatusDot state={state} pulse={pulse} size={8} />
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{
          fontSize: 13, fontWeight: 600, letterSpacing: "-0.005em",
          fontFamily: '"SF Mono", ui-monospace, monospace',
        }}>{name}</div>
        <div style={{
          fontSize: 11, color: "rgba(0,0,0,0.5)",
          marginTop: 2, lineHeight: "15px",
        }}>{detail}</div>
      </div>
      <span style={{
        fontSize: 11, color: "rgba(0,0,0,0.5)",
        fontFamily: '"SF Mono", ui-monospace, monospace',
      }}>{version}</span>
      <SF glyph="􀆊" size={11} weight={700} color="rgba(0,0,0,0.35)" />
    </div>
  );
}

function OpenChronicleSection() {
  return (
    <FormSection title="OpenChronicle" footnote="Daemon commands run synchronously; capture-once and timeline-tick are safe at any time.">
      <FormRow label="Daemon" sub="status, start/stop/pause/resume"
        control={
          <div style={{ display: "flex", gap: 6 }}>
            <PushButton variant="neutral" size="sm">Start</PushButton>
            <PushButton variant="neutral" size="sm">Pause</PushButton>
            <PushButton variant="destructive" size="sm">Stop</PushButton>
          </div>
        } />
      <FormRow label="Capture"
        control={
          <div style={{ display: "flex", gap: 6 }}>
            <PushButton variant="neutral" size="sm">Capture once</PushButton>
            <PushButton variant="neutral" size="sm">Timeline tick</PushButton>
          </div>
        } />
      <FormRow label="Captures index"
        control={<PushButton variant="neutral" size="sm">Rebuild</PushButton>} last />
    </FormSection>
  );
}

function PermissionsSection() {
  return (
    <FormSection title="Permissions" footnote="Hippo cannot grant these for you — open System Settings to authorize.">
      <PermissionRow icon="mic" label="Microphone" sub="Required for ownscribe recording" granted />
      <PermissionRow icon="eye" label="Screen Recording" sub="Required for OpenChronicle window capture" granted />
      <PermissionRow icon="gear" label="Accessibility" sub="Required when cua-driver executes a real insertion" granted={false} last />
    </FormSection>
  );
}

function PermissionRow({ icon, label, sub, granted, last }) {
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 12,
      minHeight: 52, padding: "10px 14px",
      borderBottom: last ? "none" : "0.5px solid rgba(0,0,0,0.08)",
    }}>
      <div style={{
        width: 28, height: 28, borderRadius: 7,
        background: "rgba(0,0,0,0.06)",
        display: "flex", alignItems: "center", justifyContent: "center",
      }}>
        <Icon name={icon} size={14} color="rgba(0,0,0,0.65)" />
      </div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 500, letterSpacing: "-0.005em" }}>{label}</div>
        <div style={{ fontSize: 11, color: "rgba(0,0,0,0.5)", marginTop: 2 }}>{sub}</div>
      </div>
      <span style={{
        display: "inline-flex", alignItems: "center", gap: 5,
        fontSize: 11, fontWeight: 600,
        padding: "2px 8px", borderRadius: 100,
        background: granted ? "rgba(48,209,88,0.16)" : "rgba(255,159,10,0.16)",
        color: granted ? "rgb(30,140,60)" : "rgb(178,116,0)",
      }}>
        <StatusDot state={granted ? "ok" : "warn"} size={5} />
        {granted ? "Granted" : "Not granted"}
      </span>
      <PushButton variant="neutral" size="sm">{granted ? "Manage" : "Open Settings"}</PushButton>
    </div>
  );
}

function AboutSection() {
  return (
    <FormSection title="About">
      <FormRow label="HippoJarvis"
        sub="Build 2026.05.13 · macOS 26 Tahoe"
        control={<span style={{
          fontSize: 12, color: "rgba(0,0,0,0.5)",
          fontFamily: '"SF Mono", ui-monospace, monospace',
        }}>0.4.1-demo</span>} />
      <FormRow label="Diagnostics"
        sub="Export runtime log + state snapshot"
        control={<PushButton variant="neutral" size="sm">Export…</PushButton>} last />
    </FormSection>
  );
}

window.HippoDashboardPages = window.HippoDashboardPages || {};
Object.assign(window.HippoDashboardPages, {
  SkillsPage, SettingsPage,
});
