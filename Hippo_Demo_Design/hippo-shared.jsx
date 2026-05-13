/* global React */
const { useState, useEffect, useMemo, useRef } = React;

// ─── Aurora wallpaper ─────────────────────────────────────────────────────
function AuroraBackdrop({ variant = "warm" }) {
  const styles = {
    warm: {
      background: `
        radial-gradient(ellipse 55% 60% at 12% 18%, oklch(72% 0.20 320 / 0.72), transparent 62%),
        radial-gradient(ellipse 60% 50% at 88% 8%, oklch(74% 0.18 35 / 0.68), transparent 60%),
        radial-gradient(ellipse 70% 60% at 72% 92%, oklch(66% 0.18 250 / 0.70), transparent 65%),
        radial-gradient(ellipse 45% 40% at 28% 82%, oklch(76% 0.16 185 / 0.55), transparent 60%),
        linear-gradient(135deg, oklch(20% 0.06 290), oklch(16% 0.05 260))
      `,
    },
    cool: {
      background: `
        radial-gradient(ellipse 55% 60% at 10% 15%, oklch(70% 0.16 230 / 0.62), transparent 60%),
        radial-gradient(ellipse 60% 50% at 90% 20%, oklch(72% 0.14 200 / 0.55), transparent 60%),
        radial-gradient(ellipse 70% 60% at 75% 90%, oklch(66% 0.16 290 / 0.55), transparent 65%),
        radial-gradient(ellipse 40% 40% at 30% 75%, oklch(72% 0.12 160 / 0.45), transparent 60%),
        linear-gradient(135deg, oklch(18% 0.06 260), oklch(14% 0.04 240))
      `,
    },
  };
  return (
    <div style={{ position: "absolute", inset: 0, overflow: "hidden", ...styles[variant] }}>
      <div style={{
        position: "absolute", inset: 0, opacity: 0.35, mixBlendMode: "overlay",
        backgroundImage: `url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 1 0 0 0 0 1 0 0 0 0 1 0 0 0 0.30 0'/></filter><rect width='100%' height='100%' filter='url(%23n)'/></svg>")`,
      }} />
    </div>
  );
}

// ─── Hippo glyph (the menu-bar icon) ──────────────────────────────────────
function HippoGlyph({ size = 16, color = "currentColor" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none">
      <defs>
        <linearGradient id="hg-grad" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="oklch(75% 0.20 40)" />
          <stop offset="1" stopColor="oklch(58% 0.22 15)" />
        </linearGradient>
      </defs>
      <path
        d="M5 13c0-3.5 3.1-6.5 7-6.5s7 3 7 6.5v3a2 2 0 01-2 2h-2.2a.8.8 0 01-.8-.8v-.6c0-1.4-1.3-2.6-3-2.6s-3 1.2-3 2.6v.6a.8.8 0 01-.8.8H4.5A.5.5 0 014 18v-1c0-2 .4-3 1-4z"
        fill={color === "currentColor" ? "url(#hg-grad)" : color}
      />
      <circle cx="15.5" cy="11" r="0.9" fill="oklch(98% 0 0)" />
      <circle cx="9.5" cy="11" r="0.9" fill="oklch(98% 0 0)" />
    </svg>
  );
}

// ─── SF Symbols (via Unicode) + stroke fallbacks ──────────────────────────
// macOS 26 ships SF Symbols as glyphs in the SF Pro font (PUA range).
// We use the unicode point and rely on font fallback to a stroked SVG.
const SF = ({ glyph, size = 13, weight = 500, color = "currentColor", style }) => (
  <span style={{
    fontFamily: '"SF Pro", -apple-system, BlinkMacSystemFont, sans-serif',
    fontWeight: weight, fontSize: size, color, lineHeight: 1,
    display: "inline-flex", alignItems: "center", justifyContent: "center",
    ...style,
  }}>{glyph}</span>
);

// Stroked icon set as a fallback when SF Symbols aren't available in browser
const Icon = ({ name, size = 13, stroke = 1.5, color = "currentColor" }) => {
  const props = {
    width: size, height: size, viewBox: "0 0 16 16", fill: "none",
    stroke: color, strokeWidth: stroke, strokeLinecap: "round", strokeLinejoin: "round",
  };
  const paths = {
    record: <circle cx="8" cy="8" r="3.5" fill={color} stroke="none" />,
    stop: <rect x="4.5" y="4.5" width="7" height="7" rx="1.5" fill={color} stroke="none" />,
    play: <path d="M5.5 4l6 4-6 4z" fill={color} stroke="none" />,
    mic: <g><rect x="6" y="2" width="4" height="8" rx="2"/><path d="M4 8a4 4 0 008 0M8 12v2M5.5 14h5"/></g>,
    waveform: <path d="M3 8h0.5M5.5 6v4M8 4v8M10.5 6v4M13 8h-0.5" strokeWidth={stroke + 0.5}/>,
    sparkles: <g><path d="M6 2l1 2 2 1-2 1-1 2-1-2-2-1 2-1z"/><path d="M12 8l.7 1.4L14 10l-1.3.6L12 12l-.7-1.4L10 10l1.3-.6z"/></g>,
    pin: <path d="M8 2l1.5 4 4 .5-3 2.8.8 4.2L8 11.5 4.7 13.5l.8-4.2L2.5 6.5l4-.5z" />,
    book: <path d="M3 3h4a2 2 0 012 2v8a2 2 0 00-2-2H3V3zm10 0H9a2 2 0 00-2 2v8a2 2 0 012-2h4V3z"/>,
    activity: <path d="M2 8h2l2-5 4 10 2-5h2"/>,
    gear: <g><circle cx="8" cy="8" r="2"/><path d="M8 1.5v2M8 12.5v2M14.5 8h-2M3.5 8h-2M12.6 3.4l-1.4 1.4M4.8 11.2l-1.4 1.4M12.6 12.6l-1.4-1.4M4.8 4.8L3.4 3.4"/></g>,
    refresh: <path d="M2.5 8a5.5 5.5 0 019.4-3.9L13.5 5.5M13.5 8a5.5 5.5 0 01-9.4 3.9L2.5 10.5M11 2.5v3h3M5 13.5v-3H2"/>,
    chevron: <path d="M5 6l3 3 3-3"/>,
    chevronR: <path d="M6 4l3 4-3 4"/>,
    check: <path d="M3 8.5L6.5 12 13 4.5"/>,
    x: <path d="M4 4l8 8M12 4l-8 8"/>,
    plus: <path d="M8 3v10M3 8h10"/>,
    search: <g><circle cx="7" cy="7" r="4"/><path d="M10 10l3 3"/></g>,
    globe: <g><circle cx="8" cy="8" r="6"/><path d="M2 8h12M8 2c2 1.5 3 4 3 6s-1 4.5-3 6c-2-1.5-3-4-3-6s1-4.5 3-6z"/></g>,
    eye: <g><path d="M1.5 8s2.5-4 6.5-4 6.5 4 6.5 4-2.5 4-6.5 4-6.5-4-6.5-4z"/><circle cx="8" cy="8" r="1.5"/></g>,
    moreDots: <g><circle cx="3" cy="8" r="0.9" fill={color} stroke="none"/><circle cx="8" cy="8" r="0.9" fill={color} stroke="none"/><circle cx="13" cy="8" r="0.9" fill={color} stroke="none"/></g>,
    insert: <g><path d="M3 8h7M7 5l3 3-3 3"/><path d="M13 3v10" strokeWidth={stroke + 0.4} /></g>,
    folder: <path d="M2 5a1 1 0 011-1h3l1 1h6a1 1 0 011 1v6a1 1 0 01-1 1H3a1 1 0 01-1-1V5z"/>,
    file: <path d="M4 2h5l3 3v9H4z M9 2v3h3"/>,
    clock: <g><circle cx="8" cy="8" r="6"/><path d="M8 5v3l2 1.5"/></g>,
    bolt: <path d="M9 2L4 9h3l-1 5 5-7H8z" fill={color} stroke="none" />,
    target: <g><circle cx="8" cy="8" r="6"/><circle cx="8" cy="8" r="3"/><circle cx="8" cy="8" r="0.8" fill={color} stroke="none"/></g>,
    bell: <g><path d="M4 11V8a4 4 0 018 0v3l1 1.5H3z"/><path d="M7 13.5a1.5 1.5 0 003 0"/></g>,
    mail: <g><rect x="2" y="3.5" width="12" height="9" rx="1.5"/><path d="M2.5 4.5L8 9l5.5-4.5"/></g>,
    terminal: <g><path d="M3 5l3 3-3 3M8 11h5"/><rect x="1" y="2.5" width="14" height="11" rx="1.5"/></g>,
  };
  return <svg {...props} style={{ display: "inline-block", verticalAlign: "middle" }}>{paths[name] || paths.sparkles}</svg>;
};

// ─── Materials (per Apple Liquid Glass spec) ──────────────────────────────
// Light medium = rgba(245,245,245,0.67) fill + rgba(0,0,0,0.2) glass tint, radius 34
// We layer them via two stacked backgrounds + backdrop-filter.
const materialBg = (mode = "light") => mode === "dark"
  ? `linear-gradient(rgba(0,0,0,0.2), rgba(0,0,0,0.2)), linear-gradient(rgba(38,38,38,0.67), rgba(38,38,38,0.67))`
  : `linear-gradient(rgba(0,0,0,0.04), rgba(0,0,0,0.04)), linear-gradient(rgba(245,245,245,0.72), rgba(245,245,245,0.72))`;

const material = (mode = "light") => ({
  background: materialBg(mode),
  backdropFilter: "saturate(180%) blur(30px)",
  WebkitBackdropFilter: "saturate(180%) blur(30px)",
});

// ─── Status dot ──────────────────────────────────────────────────────────
function StatusDot({ state = "ok", pulse = false, size = 6 }) {
  const colors = {
    ok: "rgb(48,209,88)",
    warn: "rgb(255,159,10)",
    error: "rgb(255,56,60)",
    busy: "rgb(0,122,255)",
    rec: "rgb(255,56,60)",
    idle: "rgb(174,174,178)",
  };
  return (
    <span style={{
      width: size, height: size, borderRadius: "50%",
      background: colors[state],
      boxShadow: `0 0 0 0.5px rgba(255,255,255,0.4)${pulse ? `, 0 0 6px ${colors[state]}` : ""}`,
      animation: pulse ? "hippo-pulse 1.6s ease-in-out infinite" : "none",
      display: "inline-block", flexShrink: 0,
    }} />
  );
}

// ─── Traffic lights ──────────────────────────────────────────────────────
function TrafficLights({ disabled = false }) {
  const dot = (bg, ring) => ({
    width: 12, height: 12, borderRadius: "50%",
    background: bg,
    boxShadow: `0 0 0 0.5px ${ring} inset, 0 0.5px 0 rgba(255,255,255,0.5) inset`,
  });
  return (
    <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
      <span style={dot(disabled ? "rgba(0,0,0,0.18)" : "#ff5f57", "rgba(0,0,0,0.18)")} />
      <span style={dot(disabled ? "rgba(0,0,0,0.18)" : "#febc2e", "rgba(0,0,0,0.18)")} />
      <span style={dot(disabled ? "rgba(0,0,0,0.18)" : "#28c840", "rgba(0,0,0,0.18)")} />
    </div>
  );
}

// ─── Push button (Apple HIG: radius 6, h24, SF Pro Medium 13) ─────────────
function PushButton({ children, variant = "neutral", icon, full, onClick, style, size = "md" }) {
  const sizes = { sm: { h: 20, px: 10, fs: 12 }, md: { h: 24, px: 16, fs: 13 }, lg: { h: 28, px: 18, fs: 14 } };
  const s = sizes[size];
  const variants = {
    // Default / preferred (filled blue accent)
    preferred: {
      background: "rgb(0,122,255)",
      color: "rgb(255,255,255)",
      border: "0.5px solid rgba(0,0,0,0.10)",
      boxShadow: "0 0.5px 0 rgba(255,255,255,0.4) inset, 0 1px 2px rgba(0,72,179,0.25)",
    },
    // Bordered destructive (red text)
    destructive: {
      background: "rgba(255,255,255,0.9)",
      color: "rgb(255,56,60)",
      border: "0.5px solid rgba(0,0,0,0.10)",
      boxShadow: "0 0.5px 0 rgba(255,255,255,0.6) inset, 0 1px 1.5px rgba(0,0,0,0.06)",
    },
    // Filled red — primary stop
    stop: {
      background: "rgb(255,56,60)",
      color: "rgb(255,255,255)",
      border: "0.5px solid rgba(0,0,0,0.10)",
      boxShadow: "0 0.5px 0 rgba(255,255,255,0.4) inset, 0 1px 2px rgba(179,0,8,0.30)",
    },
    // Bordered neutral (white-ish bg, dark text)
    neutral: {
      background: "rgba(255,255,255,0.9)",
      color: "rgba(0,0,0,0.85)",
      border: "0.5px solid rgba(0,0,0,0.10)",
      boxShadow: "0 0.5px 0 rgba(255,255,255,0.6) inset, 0 1px 1.5px rgba(0,0,0,0.06)",
    },
    // Glass / vibrant (semi-transparent)
    glass: {
      background: "rgba(255,255,255,0.5)",
      color: "rgba(0,0,0,0.85)",
      border: "0.5px solid rgba(0,0,0,0.10)",
      backdropFilter: "blur(20px)",
    },
    plain: {
      background: "transparent",
      color: "rgba(0,0,0,0.85)",
      border: "0.5px solid transparent",
    },
  };
  return (
    <button onClick={onClick} style={{
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      height: s.h, padding: `0 ${s.px}px`,
      gap: 6, fontSize: s.fs, fontWeight: 500, letterSpacing: "-0.005em",
      borderRadius: 6, cursor: "pointer",
      fontFamily: 'inherit',
      width: full ? "100%" : "auto",
      ...variants[variant], ...style,
    }}>
      {icon && <Icon name={icon} size={s.fs - 1} />}
      {children}
    </button>
  );
}

// Capsule variant — sometimes used for primary popover action
function Capsule({ children, variant = "neutral", icon, full, onClick, style }) {
  return (
    <PushButton variant={variant} icon={icon} full={full} onClick={onClick}
      style={{ borderRadius: 999, height: 32, padding: "0 18px", ...style }}>
      {children}
    </PushButton>
  );
}

// Toolbar symbol button — 28×28
function SymbolButton({ glyph, icon, onClick, size = 13, color = "rgba(0,0,0,0.85)", style }) {
  return (
    <button onClick={onClick} style={{
      width: 28, height: 28, borderRadius: 7,
      background: "transparent", border: "0.5px solid transparent",
      display: "inline-flex", alignItems: "center", justifyContent: "center",
      cursor: "pointer", color, ...style,
    }}>
      {glyph ? <SF glyph={glyph} size={size} color={color} /> : <Icon name={icon} size={size} color={color} />}
    </button>
  );
}

// ─── Hairline divider ─────────────────────────────────────────────────────
function Hairline({ inset = 0, vertical = false, color = "rgba(0,0,0,0.10)" }) {
  return (
    <div style={{
      ...(vertical
        ? { width: 0.5, alignSelf: "stretch", marginTop: inset, marginBottom: inset }
        : { height: 0.5, marginLeft: inset, marginRight: inset }),
      background: color,
    }} />
  );
}

window.HippoShared = {
  AuroraBackdrop, HippoGlyph, Icon, SF,
  material, materialBg,
  StatusDot, TrafficLights, PushButton, Capsule, SymbolButton, Hairline,
};
