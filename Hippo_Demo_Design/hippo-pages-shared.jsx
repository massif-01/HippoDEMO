/* global React, HippoShared */
const { HippoGlyph, Icon, SF, material, StatusDot, TrafficLights, PushButton, SymbolButton, Hairline } = HippoShared;

// Shared collapsed-sidebar context — PageShell prepends traffic lights + toggle
// when this is true.
const CollapsedContext = React.createContext(false);

// ──────────────────────────────────────────────────────────────────────────
// Shared chrome: page titlebar + toolbar + scrollable content
// ──────────────────────────────────────────────────────────────────────────
function PageShell({ title, subtitle, toolbar, trailing, children }) {
  const collapsed = React.useContext(CollapsedContext);
  return (
    <>
      <div style={{
        height: 32,
        display: "flex", alignItems: "center", padding: "0 14px",
        gap: 10,
      }}>
        {collapsed && <SidebarToggleStrip />}
        <span style={{
          fontSize: 13, fontWeight: 600,
          color: "rgba(0,0,0,0.85)", letterSpacing: "-0.005em",
        }}>{title}</span>
        {subtitle && (
          <span style={{
            fontSize: 12, color: "rgba(0,0,0,0.5)",
            letterSpacing: "-0.005em",
          }}>{subtitle}</span>
        )}
        <div style={{ flex: 1 }} />
        {trailing}
      </div>
      {toolbar && (
        <div style={{
          height: 44, display: "flex", alignItems: "center",
          padding: "0 14px", gap: 8,
          borderBottom: "0.5px solid rgba(0,0,0,0.07)",
        }}>{toolbar}</div>
      )}
      <div style={{
        flex: 1, minHeight: 0, overflow: "auto",
      }}>{children}</div>
    </>
  );
}

// Leading strip rendered inside PageShell title when sidebar is collapsed:
// traffic lights + sidebar toggle (same icon as the expanded state — clicking it re-shows the sidebar).
function SidebarToggleStrip() {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <TrafficLights />
      <div style={{
        width: 0.5, height: 16, background: "rgba(0,0,0,0.10)",
      }} />
      <button style={iconBtnSmall()} title="Show sidebar">
        <SF glyph="􀏟" size={14} weight={500} color="rgba(0,0,0,0.65)" />
      </button>
      <div style={{
        width: 0.5, height: 16, background: "rgba(0,0,0,0.10)",
      }} />
    </div>
  );
}
function iconBtnSmall() {
  return {
    width: 22, height: 22, borderRadius: 5,
    background: "transparent", border: "none",
    display: "inline-flex", alignItems: "center", justifyContent: "center",
    cursor: "pointer",
  };
}

function SearchField({ width = 220, placeholder = "Search", kbd = "⌘F" }) {
  return (
    <div style={{
      width, height: 28, borderRadius: 7,
      background: "rgba(0,0,0,0.05)",
      border: "0.5px solid rgba(0,0,0,0.08)",
      display: "flex", alignItems: "center", gap: 6, padding: "0 10px",
    }}>
      <Icon name="search" size={12} color="rgba(0,0,0,0.5)" />
      <span style={{ fontSize: 12, color: "rgba(0,0,0,0.45)", flex: 1 }}>{placeholder}</span>
      {kbd && <span style={{
        fontSize: 10, fontFamily: '"SF Mono", ui-monospace, monospace',
        color: "rgba(0,0,0,0.4)", padding: "1px 5px", borderRadius: 3,
        background: "rgba(0,0,0,0.06)",
      }}>{kbd}</span>}
    </div>
  );
}

function Seg({ items, active }) {
  return (
    <div style={{
      display: "inline-flex", height: 28,
      padding: 2, borderRadius: 7,
      background: "rgba(0,0,0,0.05)",
      border: "0.5px solid rgba(0,0,0,0.08)",
    }}>
      {items.map((it, i) => (
        <button key={i} style={{
          minWidth: 36, height: 24, padding: "0 10px",
          borderRadius: 5,
          background: i === active ? "rgba(255,255,255,0.95)" : "transparent",
          border: "none",
          boxShadow: i === active ? "0 1px 1px rgba(0,0,0,0.06), 0 0 0 0.5px rgba(0,0,0,0.06)" : "none",
          fontSize: 12, fontWeight: 500,
          color: i === active ? "rgba(0,0,0,0.85)" : "rgba(0,0,0,0.6)",
          cursor: "pointer", fontFamily: 'inherit',
          display: "inline-flex", alignItems: "center", justifyContent: "center", gap: 5,
        }}>
          {it.glyph && <SF glyph={it.glyph} size={12} weight={500} color="inherit" />}
          {it.label}
          {it.badge != null && (
            <span style={{
              fontSize: 10, fontWeight: 600,
              padding: "0 5px", height: 14, lineHeight: "14px",
              borderRadius: 100,
              background: i === active ? "rgb(0,122,255)" : "rgba(0,0,0,0.12)",
              color: i === active ? "white" : "rgba(0,0,0,0.6)",
            }}>{it.badge}</span>
          )}
        </button>
      ))}
    </div>
  );
}

// ─── Section header for forms / tables ───────────────────────────────────
function FormSection({ title, footnote, children }) {
  return (
    <div style={{ marginBottom: 22 }}>
      <div style={{
        fontSize: 11, fontWeight: 600,
        color: "rgba(0,0,0,0.5)", letterSpacing: "0.04em",
        textTransform: "uppercase",
        padding: "0 4px 6px",
      }}>{title}</div>
      <div style={{
        borderRadius: 10,
        background: "rgba(255,255,255,0.7)",
        border: "0.5px solid rgba(0,0,0,0.08)",
        overflow: "hidden",
      }}>{children}</div>
      {footnote && (
        <div style={{
          fontSize: 11, color: "rgba(0,0,0,0.5)",
          padding: "6px 6px 0", lineHeight: "16px",
        }}>{footnote}</div>
      )}
    </div>
  );
}

function FormRow({ label, sub, control, last }) {
  return (
    <div style={{
      display: "flex", alignItems: "center",
      minHeight: 44, padding: "8px 14px",
      borderBottom: last ? "none" : "0.5px solid rgba(0,0,0,0.08)",
      gap: 12,
    }}>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontSize: 13, fontWeight: 500, letterSpacing: "-0.005em" }}>{label}</div>
        {sub && (
          <div style={{
            fontSize: 11, color: "rgba(0,0,0,0.5)",
            marginTop: 2, lineHeight: "15px",
          }}>{sub}</div>
        )}
      </div>
      {control}
    </div>
  );
}

window.HippoDashboardPages = window.HippoDashboardPages || {};
Object.assign(window.HippoDashboardPages, {
  PageShell, SearchField, Seg, FormSection, FormRow, CollapsedContext,
});
