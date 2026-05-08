// design/primitives.js — composable building blocks for slide layouts.
//
// Every layout in SlideLayouts.jsx (and ideally every TitleSlide variant in
// SlideRenderer.jsx) should compose from these. The benefit: when a designer
// says "make every card corner 4px tighter", you change `radius.lg` in
// tokens.js once and the entire deck updates.

import { Sparkles, Target, TrendingUp, Lightbulb, Rocket, Shield, Zap, Globe,
  Users, BarChart3, Heart, Star, Layers, Gem, Compass, Brain, Award,
  CheckCircle2 } from "lucide-react";

import { radius, shadow, accentTints, hashString, iconSize } from "./tokens.js";
import { slideSpacing, slideSpacingClass } from "./spacing.jsx";
import { Eyebrow, Title, Subtitle, Body, Caption } from "./typography.jsx";

// ─── Icon roster ────────────────────────────────────────────────────────────
const ICONS = [
  Sparkles, Target, TrendingUp, Lightbulb, Rocket, Shield, Zap, Globe,
  Users, BarChart3, Heart, Star, Layers, Gem, Compass, Brain, Award, CheckCircle2,
];
export function iconFor(seed, idx = 0) {
  return ICONS[(hashString(seed) + idx) % ICONS.length];
}

// ─── Frame ──────────────────────────────────────────────────────────────────
// The outer slide content wrapper. Every layout starts with <Frame p={p}>.
// Guarantees: consistent slide padding, palette-aware text color,
// flex column so children stack predictably.
export function Frame({ p, children, className = "", style = {}, padded = true }) {
  const padding = padded ? `${slideSpacingClass.padX} ${slideSpacingClass.padY}` : "";
  return (
    <div
      className={`flex h-full flex-col ${padding} ${className}`}
      style={{ color: p?.text, ...style }}
    >
      {children}
    </div>
  );
}

// ─── Section ────────────────────────────────────────────────────────────────
// Eyebrow + Title + (optional) Subtitle composer. Used at the top of nearly
// every layout. Centralises the spacing rhythm between those three lines.
export function Section({
  eyebrow,
  title,
  subtitle,
  p,
  size = "h2",
  align = "left",
  className = "",
}) {
  return (
    <header
      className={`flex flex-col ${className}`}
      style={{ gap: slideSpacing.eyebrowToTitle, alignItems: align === "center" ? "center" : "flex-start", textAlign: align }}
    >
      {eyebrow && <Eyebrow p={p}>{eyebrow}</Eyebrow>}
      {title && (
        <Title p={p} size={size} style={{ marginBottom: subtitle ? slideSpacing.titleToSubtitle : 0 }}>
          {title}
        </Title>
      )}
      {subtitle && <Subtitle p={p} style={{ maxWidth: "48rem" }}>{subtitle}</Subtitle>}
    </header>
  );
}

// ─── Card ───────────────────────────────────────────────────────────────────
// Variants:
//   filled   — solid tinted background, white text (use for hero cells)
//   tinted   — soft accent wash + thin accent border (use for feature grids)
//   outlined — palette border only (use for table-ish lists)
//   elevated — surface bg + drop shadow (use for KPI / floating panels)
export function Card({
  variant = "tinted",
  tint,                                // hex; falls back to palette accent
  p,
  children,
  className = "",
  style = {},
  as: Tag = "div",
  padded = true,
  minH,
}) {
  const accent = tint || p?.accent || accentTints[0];
  const styles = (() => {
    switch (variant) {
      case "filled":
        return { background: accent, color: "#FFFFFF", border: "none" };
      case "outlined":
        return { background: "transparent", borderWidth: 1, borderColor: p?.border || `${accent}40` };
      case "elevated":
        return { background: p?.surface || "#FFFFFF", boxShadow: shadow.card, borderWidth: 1, borderColor: p?.border || "rgba(0,0,0,0.06)" };
      case "tinted":
      default:
        return { background: `${accent}12`, borderWidth: 1, borderColor: `${accent}40` };
    }
  })();
  return (
    <Tag
      className={className}
      style={{
        borderRadius: radius.xl,
        padding: padded ? slideSpacing.cardPad : 0,
        minHeight: minH,
        ...styles,
        ...style,
      }}
    >
      {children}
    </Tag>
  );
}

// ─── IconBadge ──────────────────────────────────────────────────────────────
// Standardised icon "chip" used in cards. Sizes match iconSize scale.
export function IconBadge({ icon: Icon, tint, size = "md", filled = true, style = {} }) {
  const dim = { sm: "1.75rem", md: "2.25rem", lg: "2.75rem", xl: "3.5rem" }[size] || size;
  const iconDim = iconSize[size === "xl" ? "lg" : size === "lg" ? "md" : "sm"];
  return (
    <div
      style={{
        width: dim,
        height: dim,
        borderRadius: radius.lg,
        background: filled ? tint : `${tint}20`,
        color: filled ? "#FFFFFF" : tint,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        flexShrink: 0,
        ...style,
      }}
    >
      <Icon style={{ width: iconDim, height: iconDim }} strokeWidth={2.4} />
    </div>
  );
}

// ─── MetricBlock ────────────────────────────────────────────────────────────
// Big-number + label + optional caption. Reused by stats / metric-spotlight /
// kpi layouts so they all share the same numeric typography.
export function MetricBlock({ value, label, caption, tint, p, size = "lg", align = "left" }) {
  const sizes = {
    sm: "clamp(2rem, 3vw, 2.75rem)",
    md: "clamp(2.5rem, 4vw, 3.75rem)",
    lg: "clamp(3.5rem, 6vw, 5.5rem)",
    xl: "clamp(4.5rem, 8vw, 7rem)",
  };
  return (
    <div style={{ textAlign: align }}>
      <div
        style={{
          fontSize: sizes[size] || sizes.lg,
          fontWeight: 900,
          lineHeight: 1,
          letterSpacing: "-0.02em",
          color: tint || p?.accent,
        }}
      >
        {value}
      </div>
      {label && (
        <div
          style={{
            marginTop: "0.5rem",
            fontSize: "0.75rem",
            fontWeight: 600,
            letterSpacing: "0.18em",
            textTransform: "uppercase",
            color: p?.muted,
          }}
        >
          {label}
        </div>
      )}
      {caption && (
        <Caption p={p} style={{ display: "block", marginTop: "0.5rem" }}>
          {caption}
        </Caption>
      )}
    </div>
  );
}

// ─── ImageFrame ─────────────────────────────────────────────────────────────
// Predictable image container with optional overlay scrim. Use everywhere
// you'd otherwise write `<img class="absolute inset-0 ...">`.
export function ImageFrame({
  src,
  alt = "",
  ratio,                       // e.g. "16/9", "4/3", "1/1"
  scrim = "none",              // "none" | "bottom" | "right" | "full"
  rounded = "xl",              // key from radius scale, or "none"
  className = "",
  style = {},
}) {
  if (!src) return null;
  const scrims = {
    none: null,
    bottom: "linear-gradient(180deg, rgba(0,0,0,0) 40%, rgba(0,0,0,0.65) 100%)",
    right: "linear-gradient(270deg, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0) 60%)",
    full: "linear-gradient(180deg, rgba(0,0,0,0.35) 0%, rgba(0,0,0,0.75) 100%)",
  };
  return (
    <div
      className={`relative overflow-hidden ${className}`}
      style={{
        aspectRatio: ratio,
        borderRadius: rounded === "none" ? 0 : radius[rounded] || radius.xl,
        ...style,
      }}
    >
      <img src={src} alt={alt} loading="lazy" className="h-full w-full object-cover" />
      {scrims[scrim] && (
        <div className="pointer-events-none absolute inset-0" style={{ background: scrims[scrim] }} />
      )}
    </div>
  );
}

// ─── BulletList ─────────────────────────────────────────────────────────────
// Standard bullet rendering — colored dot + body. Use anywhere you'd
// otherwise hand-roll <ul><li>.
export function BulletList({ items, p, tint, className = "", style = {} }) {
  return (
    <ul
      className={`flex flex-col ${className}`}
      style={{ gap: slideSpacing.cardGap, ...style }}
    >
      {items.map((it, i) => (
        <li key={i} className="flex items-start" style={{ gap: slideSpacing.cardGap }}>
          <span
            style={{
              marginTop: "0.55rem",
              width: "0.4rem",
              height: "0.4rem",
              borderRadius: radius.full,
              background: tint || p?.accent,
              flexShrink: 0,
            }}
          />
          <Body p={p} as="span">{it}</Body>
        </li>
      ))}
    </ul>
  );
}
