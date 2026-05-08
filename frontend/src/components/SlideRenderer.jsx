import { motion } from "framer-motion";
import { EXTRA_LAYOUTS, LAYOUT_ALIASES } from "./SlideLayouts.jsx";
import {
  paletteFor as designPaletteFor,
  resolveLayoutName,
  normalizeSlideContent,
  UnsupportedLayoutSlide,
} from "../design/index.js";
import {
  Sparkles,
  Target,
  TrendingUp,
  Lightbulb,
  Rocket,
  Shield,
  Zap,
  Globe,
  Users,
  BarChart3,
  Heart,
  Star,
  CheckCircle2,
  Layers,
  Gem,
  Compass,
  Brain,
  Award,
} from "lucide-react";
import {
  Chart as ChartJS,
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  Title as ChartTitle,
  Tooltip,
  Legend,
  Filler,
} from "chart.js";
import { Bar, Line, Doughnut } from "react-chartjs-2";

ChartJS.register(
  CategoryScale,
  LinearScale,
  BarElement,
  LineElement,
  PointElement,
  ArcElement,
  ChartTitle,
  Tooltip,
  Legend,
  Filler,
);

// ─── 40+ slidesalad-inspired themes ─────────────────────────────────────────
// Each palette is a complete look: bg (solid or gradient), accent, text, muted.
// Names roughly map to slidesalad.com's "40+ Beautiful PowerPoint Templates"
// catalog so each new deck feels like a different premium template.
const themePalettes = {
  // — Existing five (kept for backward-compat) —
  "light-pro": { bg: "#FFFFFF", accent: "#F59E0B", text: "#111827", muted: "#6B7280" },
  Editorial:   { bg: "linear-gradient(135deg,#0F0F14 0%,#1A1A22 100%)", accent: "#A78BFA", text: "#F5F5F7", muted: "#9A9AA5" },
  Pixel:       { bg: "linear-gradient(135deg,#101820 0%,#1A2A33 100%)", accent: "#34D399", text: "#F1FAEE", muted: "#94A3B8" },
  Vellum:      { bg: "linear-gradient(135deg,#FAF7F2 0%,#EFE9DD 100%)", accent: "#A0522D", text: "#1F1A14", muted: "#6B5E4A" },
  Dossier:     { bg: "linear-gradient(135deg,#0B1220 0%,#1E293B 100%)", accent: "#60A5FA", text: "#E2E8F0", muted: "#94A3B8" },

  // — Slidesalad-inspired — Light, vivid —
  Complete:    { bg: "linear-gradient(135deg,#FFFFFF 0%,#F1F5F9 100%)", accent: "#2563EB", text: "#0F172A", muted: "#64748B" },
  Golden:      { bg: "linear-gradient(135deg,#FFFBEB 0%,#FEF3C7 100%)", accent: "#D97706", text: "#1C1917", muted: "#78716C" },
  Simplicity:  { bg: "#FFFFFF", accent: "#0EA5E9", text: "#0F172A", muted: "#64748B" },
  Marketing:   { bg: "linear-gradient(135deg,#FEF2F2 0%,#FEE2E2 100%)", accent: "#DC2626", text: "#1A0A0A", muted: "#78716C" },
  Proposal:    { bg: "linear-gradient(135deg,#F5F3FF 0%,#EDE9FE 100%)", accent: "#7C3AED", text: "#1E1B2E", muted: "#6B6B7B" },
  Strategy:    { bg: "linear-gradient(135deg,#ECFEFF 0%,#CFFAFE 100%)", accent: "#0891B2", text: "#083344", muted: "#475569" },
  Launch:      { bg: "linear-gradient(135deg,#FFF7ED 0%,#FFEDD5 100%)", accent: "#EA580C", text: "#1C1917", muted: "#78716C" },
  Growth:      { bg: "linear-gradient(135deg,#F0FDF4 0%,#BBF7D0 100%)", accent: "#16A34A", text: "#0E1F17", muted: "#475569" },
  Plan:        { bg: "linear-gradient(135deg,#EFF6FF 0%,#DBEAFE 100%)", accent: "#2563EB", text: "#0C1E2E", muted: "#64748B" },
  Pitch:       { bg: "linear-gradient(135deg,#FAF5FF 0%,#E9D5FF 100%)", accent: "#9333EA", text: "#1F0A2E", muted: "#6B5B7B" },
  Sales:       { bg: "linear-gradient(135deg,#FEF2F2 0%,#FECACA 100%)", accent: "#E11D48", text: "#1F0A14", muted: "#78716C" },
  Plan2:       { bg: "linear-gradient(135deg,#F0FDFA 0%,#CCFBF1 100%)", accent: "#0D9488", text: "#0E1F1A", muted: "#475569" },
  Multi:       { bg: "linear-gradient(135deg,#FEFCE8 0%,#FEF08A 100%)", accent: "#CA8A04", text: "#1C1917", muted: "#78716C" },
  Stunning:    { bg: "linear-gradient(135deg,#FDF4FF 0%,#FAE8FF 100%)", accent: "#C026D3", text: "#1F0A1F", muted: "#6B5263" },
  Profile:     { bg: "linear-gradient(135deg,#F8FAFC 0%,#E2E8F0 100%)", accent: "#1E40AF", text: "#0F172A", muted: "#475569" },
  Annual:      { bg: "linear-gradient(135deg,#F1F5F9 0%,#CBD5E1 100%)", accent: "#0F766E", text: "#0F172A", muted: "#475569" },
  Review:      { bg: "linear-gradient(135deg,#FEFEFE 0%,#F3F4F6 100%)", accent: "#7C3AED", text: "#111827", muted: "#6B7280" },
  Minimal:     { bg: "#FAFAFA", accent: "#18181B", text: "#09090B", muted: "#71717A" },
  Simple:      { bg: "#FFFFFF", accent: "#10B981", text: "#0F172A", muted: "#64748B" },
  Elegant:     { bg: "linear-gradient(135deg,#FAF7F2 0%,#F3E8DD 100%)", accent: "#92400E", text: "#1F1610", muted: "#78716C" },
  Modern:      { bg: "linear-gradient(135deg,#F0F9FF 0%,#E0F2FE 100%)", accent: "#0369A1", text: "#0C1E2E", muted: "#475569" },
  Creative:    { bg: "linear-gradient(135deg,#FFE4E6 0%,#FECDD3 100%)", accent: "#BE123C", text: "#1F0A14", muted: "#78716C" },
  Clean:       { bg: "#FFFFFF", accent: "#475569", text: "#0F172A", muted: "#94A3B8" },

  // — Slidesalad-inspired — Bold dark —
  Onyx:        { bg: "linear-gradient(135deg,#000000 0%,#1F2937 100%)", accent: "#F59E0B", text: "#FAFAFA", muted: "#9CA3AF" },
  Cobalt:      { bg: "linear-gradient(135deg,#0C1844 0%,#1E3A8A 100%)", accent: "#FBBF24", text: "#F9FAFB", muted: "#94A3B8" },
  Emerald:     { bg: "linear-gradient(135deg,#022C22 0%,#064E3B 100%)", accent: "#34D399", text: "#ECFDF5", muted: "#9CA3AF" },
  Plum:        { bg: "linear-gradient(135deg,#1E0A2E 0%,#3B0764 100%)", accent: "#E879F9", text: "#FAF5FF", muted: "#A78BFA" },
  Crimson:     { bg: "linear-gradient(135deg,#1A0A0A 0%,#7F1D1D 100%)", accent: "#FCA5A5", text: "#FEF2F2", muted: "#FDA4AF" },
  Midnight:    { bg: "linear-gradient(135deg,#020617 0%,#0F172A 100%)", accent: "#38BDF8", text: "#F1F5F9", muted: "#94A3B8" },
  Forest:      { bg: "linear-gradient(135deg,#14532D 0%,#166534 100%)", accent: "#FDE047", text: "#F0FDF4", muted: "#A7F3D0" },
  Rose:        { bg: "linear-gradient(135deg,#4C0519 0%,#881337 100%)", accent: "#FDA4AF", text: "#FFF1F2", muted: "#FECDD3" },
  Carbon:      { bg: "linear-gradient(135deg,#0A0A0A 0%,#262626 100%)", accent: "#84CC16", text: "#FAFAFA", muted: "#A1A1AA" },

  // — Slidesalad-inspired — Vibrant gradient —
  Sunrise:     { bg: "linear-gradient(135deg,#FF6B6B 0%,#FFE66D 100%)", accent: "#1A1A2E", text: "#1A1A2E", muted: "#3F3F46" },
  Aurora:      { bg: "linear-gradient(135deg,#A8EDEA 0%,#FED6E3 100%)", accent: "#7C3AED", text: "#1A0A2E", muted: "#5B5563" },
  Tropical:    { bg: "linear-gradient(135deg,#FCCB90 0%,#D57EEB 100%)", accent: "#0F172A", text: "#0F172A", muted: "#3F3F46" },
  Lagoon:      { bg: "linear-gradient(135deg,#43E97B 0%,#38F9D7 100%)", accent: "#0F172A", text: "#0F172A", muted: "#374151" },
  Coral:       { bg: "linear-gradient(135deg,#FF9A8B 0%,#FF6A88 100%)", accent: "#1A0A14", text: "#1A0A14", muted: "#52525B" },
  Ice:         { bg: "linear-gradient(135deg,#E0EAFC 0%,#CFDEF3 100%)", accent: "#1E40AF", text: "#0F172A", muted: "#64748B" },
  Peach:       { bg: "linear-gradient(135deg,#FFE0C7 0%,#FFB199 100%)", accent: "#9A3412", text: "#1C1917", muted: "#78716C" },

  // — Slidesalad-inspired — Bright single-color —
  Sunset:      { bg: "linear-gradient(135deg,#FFF5F1 0%,#FFE4D6 100%)", accent: "#F97316", text: "#1C1917", muted: "#78716C" },
  Ocean:       { bg: "linear-gradient(135deg,#F0F9FF 0%,#DBEAFE 100%)", accent: "#0284C7", text: "#0C1E2E", muted: "#475569" },
  Mint:        { bg: "linear-gradient(135deg,#F0FDF4 0%,#D1FAE5 100%)", accent: "#059669", text: "#0E1F17", muted: "#475569" },
  Berry:       { bg: "linear-gradient(135deg,#FDF2F8 0%,#FCE7F3 100%)", accent: "#DB2777", text: "#1F0A14", muted: "#6B5263" },
  Slate:       { bg: "linear-gradient(135deg,#F8FAFC 0%,#E2E8F0 100%)", accent: "#0F172A", text: "#0F172A", muted: "#475569" },
  Lemon:       { bg: "linear-gradient(135deg,#FEFCE8 0%,#FEF9C3 100%)", accent: "#65A30D", text: "#1C1917", muted: "#78716C" },
  Lavender:    { bg: "linear-gradient(135deg,#FAF5FF 0%,#F3E8FF 100%)", accent: "#7C3AED", text: "#1E1B2E", muted: "#6B5B7B" },
  Sand:        { bg: "linear-gradient(135deg,#FAF7F2 0%,#EFE9DD 100%)", accent: "#92400E", text: "#1F1A14", muted: "#6B5E4A" },
  Linen:       { bg: "linear-gradient(135deg,#FFFAF0 0%,#FEF3E2 100%)", accent: "#B45309", text: "#1C1917", muted: "#78716C" },
  Mist:        { bg: "linear-gradient(135deg,#F8FAFC 0%,#F1F5F9 100%)", accent: "#475569", text: "#0F172A", muted: "#64748B" },
  Cerulean:    { bg: "linear-gradient(135deg,#ECFEFF 0%,#A5F3FC 100%)", accent: "#0E7490", text: "#083344", muted: "#475569" },
  Whiteboard:  { bg: "#FFFFFF", accent: "#2563EB", text: "#0F172A", muted: "#64748B" },
  Sketch:      { bg: "#FAFAF9", accent: "#525252", text: "#171717", muted: "#737373" },
  Glamour:     { bg: "linear-gradient(135deg,#1A0A1F 0%,#2D0B3D 100%)", accent: "#F0ABFC", text: "#FAF5FF", muted: "#C4B5FD" },
  Amber:       { bg: "linear-gradient(135deg,#FFFBEB 0%,#FDE68A 100%)", accent: "#B45309", text: "#1C1917", muted: "#78716C" },
  Arctic:      { bg: "linear-gradient(135deg,#F0F9FF 0%,#E0F2FE 100%)", accent: "#0369A1", text: "#0C1E2E", muted: "#475569" },
  Neon:        { bg: "linear-gradient(135deg,#0A0A0A 0%,#171717 100%)", accent: "#22D3EE", text: "#FAFAFA", muted: "#A1A1AA" },
  Basalt:      { bg: "linear-gradient(135deg,#1F2937 0%,#374151 100%)", accent: "#F59E0B", text: "#F9FAFB", muted: "#9CA3AF" },
};

function paletteFor(theme) {
  // Delegate to the design system so editor / renderer / future export all
  // resolve themes from one catalog. The local `themePalettes` map above is
  // kept for backward-compat callers that import it via this module's
  // closure (e.g. older tests) — but `paletteFor` is the canonical resolver.
  return designPaletteFor(theme);
}

// Cheap stable string hash so the same deck always renders the same variant,
// but different decks pick different layouts. Used for deterministic variety.
function hashString(s) {
  let h = 2166136261;
  const str = String(s || "");
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = (h * 16777619) >>> 0;
  }
  return h >>> 0;
}

// Pick one of N variants deterministically from a seed.
function pickVariant(seed, n) {
  return hashString(seed) % n;
}

// Compute a safe font-size for a title given how many words/characters it has
// and whether the layout stacks each word on its own line. Uses container-
// relative `cqw` so it scales with the SLIDE box, not the browser viewport.
// Falls back gracefully on browsers without container queries via the rem cap.
//   stacked=true  -> each word becomes a new line, so we shrink hard once the
//                    word count climbs past 2.
//   stacked=false -> the title wraps as a paragraph, so character count
//                    governs the size.
function titleFontSize(text, { stacked = false, max = 6.5, min = 2.4 } = {}) {
  const t = (text || "").trim();
  if (!t) return `${max}rem`;
  if (stacked) {
    const words = t.split(/\s+/).length;
    const rem = words <= 1 ? max : words === 2 ? max * 0.85 : words === 3 ? max * 0.65 : words === 4 ? max * 0.52 : max * 0.42;
    return `${Math.max(min, rem)}rem`;
  }
  const chars = t.length;
  const rem = chars <= 14 ? max : chars <= 24 ? max * 0.78 : chars <= 38 ? max * 0.62 : chars <= 60 ? max * 0.5 : max * 0.4;
  return `${Math.max(min, rem)}rem`;
}

// Round-robin icon set used in card-style bullet slides.
const BULLET_ICONS = [
  Sparkles, Target, TrendingUp, Lightbulb, Rocket, Shield,
  Zap, Globe, Users, BarChart3, Heart, Star, Layers, Gem, Compass, Brain, Award,
  CheckCircle2,
];
function iconFor(seed, idx) {
  const i = (hashString(seed) + idx) % BULLET_ICONS.length;
  return BULLET_ICONS[i];
}

// 6 vivid card backgrounds rotated through grids (warna-style).
const CARD_TINTS = [
  "#3B82F6", "#A855F7", "#10B981", "#F59E0B", "#EF4444", "#06B6D4",
];
function tintFor(seed, idx) {
  return CARD_TINTS[(hashString(seed) + idx) % CARD_TINTS.length];
}

function HeroImage({ src, mode = "full", p }) {
  if (!src) return null;
  // mode: "full" (title/closing) covers entire slide with dark scrim;
  // mode: "right" (bullets/two-col) covers right 38% with vertical fade.
  if (mode === "right") {
    return (
      <div className="pointer-events-none absolute inset-y-0 right-0 w-[38%]">
        <img
          src={src}
          alt=""
          loading="lazy"
          className="h-full w-full object-cover"
        />
        <div
          className="absolute inset-0"
          style={{
            background: `linear-gradient(to right, ${
              p.bg.includes("FAF") ? "rgba(250,247,242,0.95)" : "rgba(15,15,20,0.85)"
            } 0%, transparent 60%)`,
          }}
        />
      </div>
    );
  }
  return (
    <div className="pointer-events-none absolute inset-0">
      <img
        src={src}
        alt=""
        loading="lazy"
        className="h-full w-full object-cover opacity-40"
      />
      <div
        className="absolute inset-0"
        style={{
          background: `linear-gradient(180deg, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0.75) 100%)`,
        }}
      />
    </div>
  );
}

function TitleSlide({ slide, p, deckSeed }) {
  const fullTitle = (slide.title || "").trim();
  const variant = pickVariant(deckSeed || fullTitle, 10);
  // 10 structurally distinct title designs. Each variant has its own
  // skeleton (sidebar / banner / asymmetric / mosaic / hero / etc) so two
  // adjacent decks never feel like the same template just recolored.
  const Variants = [
    TitleMosaic,        // 0: 4 vivid quadrants + frosted card
    TitleSidebar,       // 1: vertical accent bar with rotated label
    TitleBadgeGrid,     // 2: colorful icon-badge infographic
    TitleTopBanner,     // 3: top accent strip + centered editorial body
    TitleGradientMesh,  // 4: gradient mesh + bold gradient-text title
    TitleAsymmetric,    // 5: oversized number letter + side stack
    TitleHeroImage,     // 6: full-bleed hero photo
    TitleMagazine,      // 7: serif magazine cover
    TitleStacked,       // 8: cascading stacked words (auto-sized)
    TitleBand,          // 9: centered + accent band
  ];
  const V = Variants[variant];
  return <V slide={slide} p={p} />;
}

// ── Variant A: split-screen with accent disc (the original) ─────────────────
function TitleSplit({ slide, p }) {
  const fullTitle = (slide.title || "").trim();
  const words = fullTitle.split(/\s+/);
  const splitIdx = words.length > 1 ? Math.ceil(words.length / 2) : 1;
  const titleTop = words.slice(0, splitIdx).join(" ");
  const titleBottom = words.slice(splitIdx).join(" ");

  return (
    <div
      className="relative grid h-full grid-cols-[58%_42%]"
      style={{ color: p.text }}
    >
      {/* LEFT — text column */}
      <div className="relative flex h-full flex-col justify-between px-14 py-12">
        <div
          className="text-xs uppercase tracking-[0.28em]"
          style={{ color: p.muted }}
        >
          {slide.eyebrow || "Presentation"}
        </div>

        <div>
          <h1
            className="text-6xl font-extrabold uppercase leading-[0.95] tracking-tight md:text-7xl"
            style={{ color: p.text }}
          >
            {titleTop}
          </h1>
          {titleBottom && (
            <h1
              className="mt-1 text-6xl font-extrabold uppercase leading-[0.95] tracking-tight md:text-7xl"
              style={{ color: p.accent }}
            >
              {titleBottom}
            </h1>
          )}
          {slide.subtitle && (
            <p
              className="mt-6 max-w-md text-base leading-relaxed"
              style={{ color: p.muted }}
            >
              {slide.subtitle}
            </p>
          )}
        </div>

        <div
          className="text-[10px] uppercase tracking-[0.32em]"
          style={{ color: p.muted }}
        >
          Powered by NEXUS
        </div>
      </div>

      {/* RIGHT — vivid accent panel with stylized circular graphic */}
      <div
        className="relative h-full overflow-hidden"
        style={{ background: p.accent }}
      >
        {slide.image_url ? (
          <img
            src={slide.image_url}
            alt=""
            loading="lazy"
            className="absolute inset-0 h-full w-full object-cover mix-blend-luminosity opacity-90"
          />
        ) : null}
        {/* stylized sun / disc */}
        <div
          className="absolute left-1/2 top-1/2 h-[55%] w-[55%] -translate-x-1/2 -translate-y-1/2 rounded-full"
          style={{
            background: `radial-gradient(circle at 35% 30%, rgba(255,255,255,0.55), rgba(255,255,255,0) 60%), ${p.accent}`,
            boxShadow: `0 0 80px 20px ${p.accent}80`,
            border: `2px solid rgba(255,255,255,0.35)`,
          }}
        />
        {/* center glyph */}
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-5xl font-black text-white/90">
          ✦
        </div>
      </div>
    </div>
  );
}

// ── Variant B: typographic stack — no accent panel, oversized stacked words ─
function TitleStacked({ slide, p }) {
  const fullTitle = (slide.title || "").trim();
  const words = fullTitle.split(/\s+/);
  return (
    <div
      className="relative flex h-full flex-col justify-between px-16 py-14"
      style={{ color: p.text }}
    >
      <div className="flex items-center gap-3 text-xs uppercase tracking-[0.32em]" style={{ color: p.muted }}>
        <span className="inline-block h-px w-10" style={{ background: p.accent }} />
        {slide.eyebrow || "Presentation"}
      </div>
      <div>
        <h1
          className="font-extrabold uppercase leading-[0.9] tracking-tight"
          style={{ fontSize: titleFontSize(fullTitle, { stacked: true, max: 6, min: 2.2 }) }}
        >
          {words.map((w, i) => (
            <span
              key={i}
              className="block"
              style={{
                color: i % 2 === 1 ? p.accent : p.text,
                marginLeft: i === 0 ? 0 : `${(i % 3) * 1.2}rem`,
              }}
            >
              {w}
            </span>
          ))}
        </h1>
        {slide.subtitle && (
          <p className="mt-8 max-w-xl text-base leading-relaxed" style={{ color: p.muted }}>
            {slide.subtitle}
          </p>
        )}
      </div>
      <div className="flex items-center justify-between text-[10px] uppercase tracking-[0.32em]" style={{ color: p.muted }}>
        <span>Powered by NEXUS</span>
        <span>{new Date().getFullYear()}</span>
      </div>
    </div>
  );
}

// ── Variant C: full-bleed hero image with bottom-left title block ───────────
function TitleHeroImage({ slide, p }) {
  return (
    <div className="relative h-full" style={{ color: "#FFF" }}>
      {slide.image_url ? (
        <img src={slide.image_url} alt="" loading="lazy" className="absolute inset-0 h-full w-full object-cover" />
      ) : (
        <div
          className="absolute inset-0"
          style={{
            background: `radial-gradient(ellipse at 30% 20%, ${p.accent}55 0%, transparent 60%), radial-gradient(ellipse at 80% 90%, ${p.accent}33 0%, transparent 55%), ${typeof p.bg === "string" ? p.bg : "#0F0F14"}`,
          }}
        />
      )}
      <div
        className="absolute inset-0"
        style={{ background: "linear-gradient(180deg, rgba(0,0,0,0.15) 0%, rgba(0,0,0,0.85) 100%)" }}
      />
      <div className="relative flex h-full flex-col justify-end px-16 pb-16 pt-12">
        <div className="text-xs uppercase tracking-[0.32em] text-white/70">
          {slide.eyebrow || "Presentation"}
        </div>
        <h1 className="mt-4 max-w-4xl text-6xl font-extrabold leading-[1.02] tracking-tight md:text-7xl">
          {slide.title}
        </h1>
        {slide.subtitle && (
          <p className="mt-5 max-w-2xl text-lg text-white/80">{slide.subtitle}</p>
        )}
        <div
          className="mt-8 inline-block self-start rounded-full px-5 py-2 text-xs uppercase tracking-[0.28em]"
          style={{ background: p.accent, color: "#0A0A0F" }}
        >
          NEXUS
        </div>
      </div>
    </div>
  );
}

// ── Variant D: centered with horizontal accent band ─────────────────────────
function TitleBand({ slide, p }) {
  return (
    <div className="relative flex h-full flex-col items-center justify-center px-16 text-center" style={{ color: p.text }}>
      <div className="absolute inset-x-0 top-1/2 h-24 -translate-y-1/2" style={{ background: p.accent + "1A" }} />
      <div className="absolute inset-x-0 top-1/2 h-px" style={{ background: p.accent }} />
      <div className="relative">
        <div className="text-xs uppercase tracking-[0.4em]" style={{ color: p.accent }}>
          {slide.eyebrow || "NEXUS"}
        </div>
        <h1 className="mt-6 text-5xl font-bold leading-[1.05] tracking-tight md:text-7xl" style={{ color: p.text }}>
          {slide.title}
        </h1>
        {slide.subtitle && (
          <p className="mx-auto mt-6 max-w-2xl text-base md:text-lg" style={{ color: p.muted }}>
            {slide.subtitle}
          </p>
        )}
        <div className="mt-10 flex items-center justify-center gap-2">
          <span className="inline-block h-1 w-12 rounded-full" style={{ background: p.accent }} />
          <span className="inline-block h-1 w-3 rounded-full" style={{ background: p.accent + "80" }} />
          <span className="inline-block h-1 w-1.5 rounded-full" style={{ background: p.accent + "50" }} />
        </div>
      </div>
    </div>
  );
}

// ── Variant E: magazine cover — kicker rules + serif feel + side number ─────
function TitleMagazine({ slide, p }) {
  return (
    <div className="relative grid h-full grid-cols-[1fr_auto] gap-8 px-14 py-12" style={{ color: p.text }}>
      <div className="flex flex-col justify-between">
        <div>
          <div className="flex items-center gap-3 text-[11px] uppercase tracking-[0.4em]" style={{ color: p.accent }}>
            <span className="inline-block h-px w-12" style={{ background: p.accent }} />
            {slide.eyebrow || "ISSUE 01"}
            <span className="inline-block h-px w-12" style={{ background: p.accent }} />
          </div>
          <div className="mt-3 text-xs uppercase tracking-[0.3em]" style={{ color: p.muted }}>
            A NEXUS Presentation
          </div>
        </div>
        <div className="max-w-3xl">
          <h1
            className="font-bold leading-[0.95] tracking-tight"
            style={{ fontSize: titleFontSize(slide.title, { max: 5.5, min: 2.4 }), color: p.text, fontFamily: "Georgia, 'Times New Roman', serif" }}
          >
            {slide.title}
          </h1>
          <div className="mt-6 h-1 w-32 rounded-full" style={{ background: p.accent }} />
          {slide.subtitle && (
            <p className="mt-6 max-w-xl text-base leading-relaxed" style={{ color: p.muted }}>
              {slide.subtitle}
            </p>
          )}
        </div>
        <div className="flex items-center justify-between text-[10px] uppercase tracking-[0.32em]" style={{ color: p.muted }}>
          <span>nexus.ai · {new Date().getFullYear()}</span>
          <span>Vol. {((slide.title || "X").length % 9) + 1}</span>
        </div>
      </div>
      <div className="hidden flex-col items-center justify-center gap-6 border-l pl-8 md:flex" style={{ borderColor: p.accent + "40" }}>
        <div className="text-[10px] uppercase tracking-[0.4em]" style={{ color: p.muted }}>NO.</div>
        <div className="font-extrabold tabular-nums leading-none" style={{ fontSize: "5.5rem", color: p.accent }}>
          01
        </div>
        <div className="text-[10px] uppercase tracking-[0.4em]" style={{ color: p.muted }}>FEATURE</div>
      </div>
    </div>
  );
}

// ── Variant F: decorative icon-badge grid (a la slidesalad infographic) ─────
function TitleBadgeGrid({ slide, p }) {
  const seed = slide.title || "";
  return (
    <div className="grid h-full grid-cols-[55%_45%]" style={{ color: p.text }}>
      <div className="flex flex-col justify-center px-14 py-12">
        <div className="text-xs uppercase tracking-[0.32em]" style={{ color: p.accent }}>
          {slide.eyebrow || "Presentation"}
        </div>
        <h1 className="mt-5 text-5xl font-extrabold leading-[1.05] tracking-tight md:text-6xl" style={{ color: p.text }}>
          {slide.title}
        </h1>
        {slide.subtitle && (
          <p className="mt-5 max-w-md text-base leading-relaxed" style={{ color: p.muted }}>
            {slide.subtitle}
          </p>
        )}
        <div className="mt-8 flex items-center gap-3">
          <div className="h-1 w-12 rounded-full" style={{ background: p.accent }} />
          <span className="text-[10px] uppercase tracking-[0.32em]" style={{ color: p.muted }}>
            Powered by NEXUS
          </span>
        </div>
      </div>
      <div
        className="relative flex items-center justify-center overflow-hidden p-8"
        style={{ background: `linear-gradient(135deg, ${p.accent}10 0%, ${p.accent}25 100%)` }}
      >
        <div className="grid w-full max-w-md grid-cols-3 gap-4">
          {Array.from({ length: 6 }).map((_, i) => {
            const Icon = iconFor(seed, i);
            const tint = tintFor(seed, i);
            const isCenter = i === 4;
            return (
              <div
                key={i}
                className={`flex aspect-square items-center justify-center rounded-2xl ${isCenter ? "scale-110" : ""}`}
                style={{
                  background: tint,
                  color: "#FFF",
                  boxShadow: isCenter ? `0 12px 40px -8px ${tint}AA` : `0 6px 20px -8px ${tint}66`,
                  transform: `rotate(${(i % 3 - 1) * 4}deg) ${isCenter ? "scale(1.1)" : ""}`,
                }}
              >
                <Icon className="h-8 w-8" strokeWidth={2.2} />
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── Variant G: 4-tile color mosaic with title overlay ───────────────────────
function TitleMosaic({ slide, p }) {
  const seed = slide.title || "";
  const tints = [tintFor(seed, 0), tintFor(seed, 1), tintFor(seed, 2), tintFor(seed, 3)];
  return (
    <div className="relative h-full" style={{ color: "#FFF" }}>
      <div className="absolute inset-0 grid grid-cols-2 grid-rows-2">
        {tints.map((t, i) => (
          <div
            key={i}
            style={{
              background: `linear-gradient(${135 + i * 30}deg, ${t} 0%, ${t}AA 100%)`,
            }}
          />
        ))}
      </div>
      {/* center frosted card */}
      <div className="relative flex h-full items-center justify-center px-12">
        <div
          className="max-w-3xl rounded-3xl border border-white/30 bg-white/10 px-12 py-12 text-center backdrop-blur-md"
          style={{ boxShadow: "0 25px 80px -20px rgba(0,0,0,0.5)" }}
        >
          <div className="text-[11px] uppercase tracking-[0.4em] text-white/80">
            {slide.eyebrow || "NEXUS"}
          </div>
          <h1 className="mt-4 text-5xl font-extrabold leading-[1.05] md:text-6xl">
            {slide.title}
          </h1>
          {slide.subtitle && (
            <p className="mx-auto mt-5 max-w-xl text-base text-white/90">
              {slide.subtitle}
            </p>
          )}
          <div className="mt-8 inline-flex items-center gap-2 rounded-full bg-white/20 px-4 py-1.5 text-[10px] uppercase tracking-[0.32em] text-white">
            <Sparkles className="h-3 w-3" /> Powered by NEXUS
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Variant H: gradient mesh + huge typography ──────────────────────────────
function TitleGradientMesh({ slide, p }) {
  const seed = slide.title || "";
  const c1 = tintFor(seed, 0);
  const c2 = tintFor(seed, 2);
  const c3 = tintFor(seed, 4);
  return (
    <div className="relative h-full overflow-hidden" style={{ color: p.text }}>
      <div
        className="absolute inset-0"
        style={{
          background: `
            radial-gradient(ellipse at 20% 20%, ${c1}66 0%, transparent 55%),
            radial-gradient(ellipse at 80% 30%, ${c2}55 0%, transparent 60%),
            radial-gradient(ellipse at 50% 90%, ${c3}55 0%, transparent 60%),
            ${typeof p.bg === "string" ? p.bg : "#0F0F14"}
          `,
        }}
      />
      <div className="relative flex h-full flex-col justify-between px-14 py-12">
        <div className="flex items-center gap-3">
          <div
            className="flex h-10 w-10 items-center justify-center rounded-xl"
            style={{ background: p.accent, color: "#FFF" }}
          >
            <Sparkles className="h-5 w-5" />
          </div>
          <span className="text-xs uppercase tracking-[0.32em]" style={{ color: p.muted }}>
            {slide.eyebrow || "NEXUS · Presentation"}
          </span>
        </div>
        <div>
          <h1
            className="font-extrabold leading-[0.92] tracking-tight"
            style={{
              fontSize: titleFontSize(slide.title, { max: 6.5, min: 2.6 }),
              background: `linear-gradient(135deg, ${p.text} 0%, ${p.accent} 100%)`,
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
              backgroundClip: "text",
            }}
          >
            {slide.title}
          </h1>
          {slide.subtitle && (
            <p className="mt-6 max-w-2xl text-lg leading-relaxed" style={{ color: p.muted }}>
              {slide.subtitle}
            </p>
          )}
        </div>
        <div className="flex items-end justify-between">
          <div className="text-[10px] uppercase tracking-[0.32em]" style={{ color: p.muted }}>
            Powered by NEXUS
          </div>
          <div className="flex gap-1.5">
            {[c1, c2, c3, p.accent].map((c, i) => (
              <span key={i} className="inline-block h-2 w-8 rounded-full" style={{ background: c }} />
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── Variant I: vertical accent sidebar with rotated label ───────────────────
function TitleSidebar({ slide, p }) {
  const seed = slide.title || "";
  const tint = tintFor(seed, 0);
  return (
    <div className="relative grid h-full grid-cols-[14%_1fr]" style={{ color: p.text }}>
      <div className="relative flex items-center justify-center overflow-hidden" style={{ background: tint }}>
        <span
          className="text-[10px] font-bold uppercase tracking-[0.5em] text-white/90"
          style={{ writingMode: "vertical-rl", transform: "rotate(180deg)" }}
        >
          {slide.eyebrow || "PRESENTATION"} · NEXUS
        </span>
        <div className="absolute bottom-6 left-1/2 -translate-x-1/2">
          <Sparkles className="h-5 w-5 text-white/80" />
        </div>
      </div>
      <div className="flex flex-col justify-center px-14 py-12">
        <div className="flex items-center gap-3 text-xs uppercase tracking-[0.32em]" style={{ color: p.muted }}>
          <span className="inline-block h-px w-10" style={{ background: tint }} />
          {new Date().getFullYear()}
        </div>
        <h1
          className="mt-5 font-extrabold leading-[1.02] tracking-tight"
          style={{ fontSize: titleFontSize(slide.title, { max: 5.5, min: 2.4 }), color: p.text }}
        >
          {slide.title}
        </h1>
        <div className="mt-6 h-1.5 w-24 rounded-full" style={{ background: tint }} />
        {slide.subtitle && (
          <p className="mt-6 max-w-xl text-base leading-relaxed" style={{ color: p.muted }}>
            {slide.subtitle}
          </p>
        )}
      </div>
    </div>
  );
}

// ── Variant J: top accent banner + centered editorial body ──────────────────
function TitleTopBanner({ slide, p }) {
  const seed = slide.title || "";
  const t1 = tintFor(seed, 0);
  const t2 = tintFor(seed, 2);
  return (
    <div className="relative flex h-full flex-col" style={{ color: p.text }}>
      {/* top banner */}
      <div className="relative flex h-[22%] items-center px-12" style={{ background: `linear-gradient(90deg, ${t1} 0%, ${t2} 100%)` }}>
        <div className="flex items-center gap-3 text-white">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-white/25 backdrop-blur">
            <Sparkles className="h-4 w-4" />
          </div>
          <span className="text-[11px] font-semibold uppercase tracking-[0.32em]">
            {slide.eyebrow || "NEXUS PRESENTATION"}
          </span>
        </div>
        <div className="ml-auto flex items-center gap-1.5">
          {[0, 1, 2, 3].map((i) => (
            <span key={i} className="inline-block h-1.5 rounded-full bg-white/60" style={{ width: i === 0 ? "2.5rem" : "0.4rem" }} />
          ))}
        </div>
      </div>
      {/* body */}
      <div className="flex flex-1 flex-col items-center justify-center px-14 text-center">
        <h1
          className="font-extrabold leading-[1.02] tracking-tight"
          style={{ fontSize: titleFontSize(slide.title, { max: 5.5, min: 2.6 }), color: p.text }}
        >
          {slide.title}
        </h1>
        {slide.subtitle && (
          <p className="mt-6 max-w-2xl text-base leading-relaxed" style={{ color: p.muted }}>
            {slide.subtitle}
          </p>
        )}
        <div className="mt-8 flex items-center gap-2">
          <span className="inline-block h-1 w-10 rounded-full" style={{ background: t1 }} />
          <span className="inline-block h-1 w-3 rounded-full" style={{ background: t2 }} />
        </div>
      </div>
    </div>
  );
}

// ── Variant K: asymmetric — huge first letter/numeral on left ───────────────
function TitleAsymmetric({ slide, p }) {
  const seed = slide.title || "";
  const tint = tintFor(seed, 0);
  const initial = (slide.title || "?").trim().charAt(0).toUpperCase();
  return (
    <div className="relative grid h-full grid-cols-[42%_58%] overflow-hidden" style={{ color: p.text }}>
      <div className="relative flex items-center justify-center" style={{ background: tint }}>
        <span
          className="font-black leading-none text-white/95"
          style={{ fontSize: "clamp(10rem, 28cqw, 22rem)" }}
        >
          {initial}
        </span>
        <div className="absolute bottom-6 left-6 text-[10px] font-bold uppercase tracking-[0.4em] text-white/70">
          {new Date().getFullYear()} · VOL.01
        </div>
      </div>
      <div className="flex flex-col justify-center px-12 py-12">
        <div className="text-[11px] uppercase tracking-[0.4em]" style={{ color: tint }}>
          {slide.eyebrow || "FEATURE"}
        </div>
        <h1
          className="mt-4 font-extrabold leading-[1.02] tracking-tight"
          style={{ fontSize: titleFontSize(slide.title, { max: 4.8, min: 2.2 }), color: p.text }}
        >
          {slide.title}
        </h1>
        {slide.subtitle && (
          <p className="mt-5 max-w-md text-base leading-relaxed" style={{ color: p.muted }}>
            {slide.subtitle}
          </p>
        )}
        <div className="mt-8 flex items-center gap-3 text-[10px] uppercase tracking-[0.32em]" style={{ color: p.muted }}>
          <Sparkles className="h-3.5 w-3.5" style={{ color: tint }} />
          Powered by NEXUS
        </div>
      </div>
    </div>
  );
}

function BulletsSlide({ slide, p, deckSeed }) {
  const seed = `${deckSeed || ""}::${slide.id || slide.title || ""}`;
  const n = (slide.bullets || []).length;
  // HubAndSpoke needs all 6 spokes filled — otherwise we get a giant empty
  // hole with a floating icon (the "ugly gem in the void" bug).
  const variant = n >= 5
    ? pickVariant(seed, 3)
    : pickVariant(seed, 2);  // pick only between CardGrid and HeroSplit
  const Variants = n >= 5
    ? [BulletsCardGrid, BulletsHubAndSpoke, BulletsHeroSplit]
    : [BulletsCardGrid, BulletsHeroSplit];
  const V = Variants[variant];
  return <V slide={slide} p={p} seed={seed} />;
}

// ── Variant A: 6-card grid with vivid tints + icons (warna-style) ───────────
function BulletsCardGrid({ slide, p, seed }) {
  const items = (slide.bullets || []).slice(0, 6);
  const cols = items.length <= 2 ? 1 : items.length <= 4 ? 2 : 3;
  return (
    <div className="flex h-full flex-col px-12 py-10" style={{ color: p.text }}>
      <div className="mb-2 text-[11px] uppercase tracking-[0.32em]" style={{ color: p.accent }}>
        {slide.eyebrow || "Section"}
      </div>
      <h2 className="mb-8 text-3xl font-bold leading-tight md:text-4xl">{slide.title}</h2>
      <div
        className="grid content-start gap-4"
        style={{
          gridTemplateColumns: `repeat(${cols}, minmax(0, 1fr))`,
          gridAutoRows: "minmax(min-content, max-content)",
        }}
      >
        {items.map((b, i) => {
          const Icon = iconFor(seed, i);
          const tint = tintFor(seed, i);
          return (
            <div
              key={i}
              className="relative flex flex-col gap-3 overflow-hidden rounded-2xl border p-5"
              style={{ borderColor: tint + "40", background: tint + "10", minHeight: "9rem", maxHeight: "15rem" }}
            >
              <div
                className="flex h-10 w-10 items-center justify-center rounded-xl"
                style={{ background: tint, color: "#FFF" }}
              >
                <Icon className="h-5 w-5" strokeWidth={2.4} />
              </div>
              <div className="text-[11px] font-mono uppercase tracking-widest" style={{ color: tint }}>
                {String(i + 1).padStart(2, "0")}
              </div>
              <p className="text-sm leading-relaxed" style={{ color: p.text }}>
                {b}
              </p>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── Variant B: hub-and-spoke — center icon ringed by labeled cards ──────────
function BulletsHubAndSpoke({ slide, p, seed }) {
  const items = (slide.bullets || []).slice(0, 6);
  const HubIcon = iconFor(seed, 99);
  return (
    <div className="flex h-full flex-col px-12 py-10" style={{ color: p.text }}>
      <h2 className="mb-2 text-3xl font-bold md:text-4xl">{slide.title}</h2>
      {slide.subtitle && (
        <p className="mb-6 text-sm" style={{ color: p.muted }}>{slide.subtitle}</p>
      )}
      <div className="relative flex-1">
        {/* central hub */}
        <div className="absolute left-1/2 top-1/2 z-10 -translate-x-1/2 -translate-y-1/2">
          <div
            className="flex h-28 w-28 items-center justify-center rounded-full"
            style={{
              background: `radial-gradient(circle at 35% 30%, ${p.accent}, ${p.accent}AA)`,
              boxShadow: `0 0 0 8px ${p.accent}1A, 0 0 60px ${p.accent}55`,
            }}
          >
            <HubIcon className="h-10 w-10 text-white" strokeWidth={2} />
          </div>
        </div>
        {/* spokes */}
        <div className="grid h-full grid-cols-3 grid-rows-2 gap-4">
          {items.map((b, i) => {
            const Icon = iconFor(seed, i);
            const tint = tintFor(seed, i);
            // hide center cell: positions 0,1,2 / 3,4,5 — middle of row 1 is index 1
            const isHidden = false;
            return (
              <div
                key={i}
                className={`relative flex items-start gap-3 rounded-xl border p-4 ${isHidden ? "invisible" : ""}`}
                style={{ borderColor: tint + "55", background: tint + "0F" }}
              >
                <div
                  className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg"
                  style={{ background: tint, color: "#FFF" }}
                >
                  <Icon className="h-4 w-4" />
                </div>
                <p className="text-sm leading-snug" style={{ color: p.text }}>{b}</p>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// ── Variant C: hero image left + numbered solution list right (Warna-style) ─
function BulletsHeroSplit({ slide, p, seed }) {
  const items = (slide.bullets || []).slice(0, 6);
  const hasImg = !!slide.image_url;
  return (
    <div className="grid h-full grid-cols-[44%_56%]" style={{ color: p.text }}>
      <div
        className="relative overflow-hidden p-10"
        style={{
          background: hasImg
            ? undefined
            : `linear-gradient(135deg, ${p.accent} 0%, ${p.accent}CC 100%)`,
        }}
      >
        {hasImg && (
          <img src={slide.image_url} alt="" loading="lazy" className="absolute inset-0 h-full w-full object-cover" />
        )}
        <div
          className="absolute inset-0"
          style={{
            background: hasImg
              ? "linear-gradient(135deg, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0.25) 100%)"
              : undefined,
          }}
        />
        <div className="relative flex h-full flex-col justify-between text-white">
          <div className="text-xs uppercase tracking-[0.3em] opacity-80">
            {slide.eyebrow || "Recipe for success"}
          </div>
          <div>
            <h2 className="text-4xl font-extrabold leading-[1.05] md:text-5xl">
              {slide.title}
            </h2>
            {slide.subtitle && (
              <p className="mt-4 max-w-sm text-base opacity-85">{slide.subtitle}</p>
            )}
          </div>
          <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.32em] opacity-70">
            <span className="inline-block h-px w-8 bg-white/60" />
            NEXUS
          </div>
        </div>
      </div>
      <div className="px-10 py-10">
        <div className="grid h-full grid-cols-2 gap-5">
          {items.map((b, i) => {
            const tint = tintFor(seed, i);
            return (
              <div key={i} className="flex items-start gap-4">
                <div
                  className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl text-lg font-bold"
                  style={{ background: tint + "1A", color: tint, border: `1.5px solid ${tint}55` }}
                >
                  {i + 1}
                </div>
                <div>
                  <div className="text-xs uppercase tracking-wider" style={{ color: tint }}>
                    Step {i + 1}
                  </div>
                  <p className="mt-1 text-sm leading-relaxed" style={{ color: p.text }}>
                    {b}
                  </p>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function TwoColSlide({ slide, p, deckSeed }) {
  const seed = `${deckSeed || ""}::${slide.id || slide.title || ""}`;
  const cols = slide.columns || [];
  const variant = pickVariant(seed, 2);
  if (variant === 0) {
    // Variant A: 4-card quadrant (uses 2 columns expanded into pros/cons style)
    const cells = cols.flatMap((c, ci) => {
      const items = (c.body || "").split(/(?:•|·|—|\n|\.\s)/).map((s) => s.trim()).filter(Boolean).slice(0, 2);
      // Only the first cell from each column shows the heading; siblings get
      // an empty heading so the same eyebrow doesn't repeat (e.g. "AWARENESS
      // OF DIGITAL MEDIA" twice in a row).
      return items.length
        ? items.map((b, bi) => ({ heading: bi === 0 ? c.heading : "", body: b, ci }))
        : [{ heading: c.heading, body: c.body, ci }];
    }).slice(0, 4);
    return (
      <div className="flex h-full flex-col px-12 py-10" style={{ color: p.text }}>
        <h2 className="mb-2 text-3xl font-bold md:text-4xl">{slide.title}</h2>
        {slide.subtitle && <p className="mb-6 text-sm" style={{ color: p.muted }}>{slide.subtitle}</p>}
        <div
          className="grid content-start gap-4"
          style={{
            gridTemplateColumns: "repeat(2, minmax(0, 1fr))",
            gridAutoRows: "minmax(min-content, max-content)",
          }}
        >
          {cells.map((c, i) => {
            const tint = tintFor(seed, i);
            const Icon = iconFor(seed, i);
            return (
              <div
                key={i}
                className="flex flex-col gap-3 rounded-2xl p-6"
                style={{ background: tint, color: "#FFF", minHeight: "9rem", maxHeight: "14rem" }}
              >
                <Icon className="h-6 w-6" strokeWidth={2.4} />
                <div className="text-base font-bold uppercase tracking-wide">{c.heading}</div>
                <p className="text-sm leading-relaxed opacity-90">{c.body}</p>
              </div>
            );
          })}
        </div>
      </div>
    );
  }
  // Variant B: classic two-card with image side
  return (
    <div className="relative h-full" style={{ color: p.text }}>
      <HeroImage src={slide.image_url} mode="right" p={p} />
      <div className={`relative flex h-full flex-col px-12 py-10 ${slide.image_url ? "pr-[42%]" : ""}`}>
        <h2 className="mb-8 text-3xl font-bold md:text-4xl">{slide.title}</h2>
        <div className="grid flex-1 grid-cols-2 gap-6">
          {cols.slice(0, 2).map((c, i) => {
            const tint = tintFor(seed, i);
            const Icon = iconFor(seed, i);
            return (
              <div
                key={i}
                className="flex flex-col gap-4 rounded-2xl border-2 p-6"
                style={{ borderColor: tint, background: tint + "0F" }}
              >
                <div
                  className="flex h-12 w-12 items-center justify-center rounded-xl"
                  style={{ background: tint, color: "#FFF" }}
                >
                  <Icon className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-bold" style={{ color: tint }}>{c.heading}</h3>
                <p className="text-sm leading-relaxed" style={{ color: p.text }}>{c.body}</p>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

function QuoteSlide({ slide, p }) {
  return (
    <div
      className="flex h-full flex-col items-center justify-center px-16 text-center"
      style={{ color: p.text }}
    >
      <span
        className="mb-6 text-7xl leading-none"
        style={{ color: p.accent }}
      >
        “
      </span>
      <blockquote className="text-2xl font-medium leading-snug md:text-3xl">
        {slide.quote}
      </blockquote>
      {slide.attribution && (
        <p className="mt-8 text-sm uppercase tracking-widest" style={{ color: p.muted }}>
          — {slide.attribution}
        </p>
      )}
    </div>
  );
}

function StatsSlide({ slide, p, deckSeed }) {
  const seed = `${deckSeed || ""}::${slide.id || slide.title || ""}`;
  const stats = (slide.stats || []).slice(0, 6);
  const variant = pickVariant(seed, 2);
  if (variant === 0) {
    // Variant A: big tinted circles in a row, icon above the number
    return (
      <div className="flex h-full flex-col px-12 py-10" style={{ color: p.text }}>
        <div className="mb-2 text-[11px] uppercase tracking-[0.32em]" style={{ color: p.accent }}>
          {slide.eyebrow || "By the numbers"}
        </div>
        <h2 className="mb-10 text-3xl font-bold md:text-4xl">{slide.title}</h2>
        <div className="flex flex-1 items-center justify-center gap-6">
          {stats.slice(0, Math.min(stats.length, 4)).map((s, i) => {
            const tint = tintFor(seed, i);
            const Icon = iconFor(seed, i);
            return (
              <div key={i} className="flex flex-col items-center text-center">
                <div
                  className="mb-4 flex h-28 w-28 items-center justify-center rounded-full"
                  style={{ background: tint, color: "#FFF", boxShadow: `0 10px 40px -10px ${tint}88` }}
                >
                  <Icon className="h-10 w-10" strokeWidth={2} />
                </div>
                <div className="text-3xl font-extrabold tabular-nums md:text-4xl" style={{ color: p.text }}>
                  {s.value}
                </div>
                <div className="mt-1 text-xs uppercase tracking-wider" style={{ color: p.muted }}>
                  {s.label}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    );
  }
  // Variant B: 6-tile grid (warna numbers grid)
  return (
    <div className="flex h-full flex-col px-12 py-10" style={{ color: p.text }}>
      <h2 className="mb-8 text-3xl font-bold md:text-4xl">{slide.title}</h2>
      <div className="grid flex-1 grid-cols-3 grid-rows-2 gap-4">
        {stats.map((s, i) => {
          const tint = tintFor(seed, i);
          const Icon = iconFor(seed, i);
          const isHero = i === 1; // make second cell the highlighted one
          return (
            <div
              key={i}
              className="flex flex-col items-start justify-between rounded-2xl border-2 p-5"
              style={{
                borderColor: isHero ? tint : tint + "40",
                background: isHero ? tint + "1A" : "transparent",
              }}
            >
              <div
                className="flex h-9 w-9 items-center justify-center rounded-lg"
                style={{ background: tint, color: "#FFF" }}
              >
                <Icon className="h-4 w-4" />
              </div>
              <div className="mt-2">
                <div className="text-3xl font-extrabold tabular-nums" style={{ color: isHero ? tint : p.text }}>
                  {s.value}
                </div>
                <div className="mt-1 text-[11px] uppercase tracking-wider" style={{ color: p.muted }}>
                  {s.label}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function ClosingSlide({ slide, p, deckSeed }) {
  const seed = `${deckSeed || ""}::${slide.id || slide.title || ""}`;
  const variant = pickVariant(seed, 2);
  if (variant === 0) {
    // Variant A: oversized "thank you" + cta card on a vivid accent panel
    return (
      <div className="grid h-full grid-cols-[55%_45%]" style={{ color: p.text }}>
        <div className="flex flex-col justify-center px-12 py-12">
          <div className="text-xs uppercase tracking-[0.32em]" style={{ color: p.accent }}>
            {slide.eyebrow || "Thank you"}
          </div>
          <h2 className="mt-4 text-5xl font-extrabold leading-[1.05] md:text-6xl" style={{ color: p.text }}>
            {slide.title}
          </h2>
          {slide.subtitle && (
            <p className="mt-5 max-w-md text-base leading-relaxed" style={{ color: p.muted }}>
              {slide.subtitle}
            </p>
          )}
          {slide.cta && (
            <div
              className="mt-8 inline-flex w-fit items-center gap-2 rounded-xl px-5 py-3 text-sm font-semibold"
              style={{ background: p.accent, color: "#0A0A0F" }}
            >
              <Sparkles className="h-4 w-4" /> {slide.cta}
            </div>
          )}
        </div>
        <div
          className="relative flex flex-col items-center justify-center overflow-hidden p-12"
          style={{ background: p.accent }}
        >
          <div className="text-center text-white">
            <div className="text-xs uppercase tracking-[0.32em] opacity-80">Get in touch</div>
            <div className="mt-3 break-words text-3xl font-extrabold leading-[1.05] md:text-4xl">
              nexus.ai
            </div>
            <div className="mt-6 flex items-center justify-center gap-2 text-xs uppercase tracking-[0.32em] opacity-80">
              <span className="inline-block h-px w-8 bg-white/70" />
              Powered by NEXUS
            </div>
          </div>
        </div>
      </div>
    );
  }
  // Variant B: full-bleed image with frosted card
  return (
    <>
      <HeroImage src={slide.image_url} mode="full" p={p} />
      <div className="relative flex h-full flex-col items-center justify-center px-16 text-center" style={{ color: p.text }}>
        <div
          className="rounded-3xl border bg-black/30 px-12 py-12 backdrop-blur-sm"
          style={{ borderColor: p.accent + "40" }}
        >
          <h2 className="text-4xl font-bold md:text-5xl">{slide.title}</h2>
          {slide.subtitle && (
            <p className="mt-5 max-w-xl text-lg" style={{ color: p.muted }}>
              {slide.subtitle}
            </p>
          )}
          {slide.cta && (
            <div
              className="mt-8 inline-block rounded-xl px-6 py-3 text-base font-semibold"
              style={{ background: p.accent, color: "#0A0A0F" }}
            >
              {slide.cta}
            </div>
          )}
        </div>
      </div>
    </>
  );
}

function ChartSlide({ slide, p }) {
  const cd = slide.chart_data || {};
  const labels = Array.isArray(cd.labels) ? cd.labels : [];
  const values = Array.isArray(cd.values) ? cd.values.map((v) => Number(v) || 0) : [];
  const unit = cd.unit || "";
  const source = cd.source || "";
  const chartType = (slide.chart_type || "bar").toLowerCase();
  const isLight = p.bg.startsWith("#FFF") || p.bg.includes("FAF");
  const gridColor = isLight ? "rgba(0,0,0,0.06)" : "rgba(255,255,255,0.08)";
  const tickColor = p.muted;

  const dataset = {
    labels,
    datasets: [
      {
        label: unit ? `Value (${unit})` : "Value",
        data: values,
        backgroundColor:
          chartType === "doughnut"
            ? [p.accent, "#34D399", "#60A5FA", "#F472B6", "#FBBF24", "#A78BFA"].slice(
                0,
                labels.length,
              )
            : `${p.accent}CC`,
        borderColor: p.accent,
        borderWidth: 2,
        fill: chartType === "line",
        tension: 0.35,
        pointRadius: 4,
        pointBackgroundColor: p.accent,
      },
    ],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          label: (ctx) => `${ctx.parsed.y ?? ctx.parsed} ${unit}`.trim(),
        },
      },
    },
    scales:
      chartType === "doughnut"
        ? {}
        : {
            x: {
              grid: { color: gridColor },
              ticks: { color: tickColor, font: { size: 12 } },
            },
            y: {
              grid: { color: gridColor },
              ticks: { color: tickColor, font: { size: 12 } },
              beginAtZero: true,
            },
          },
  };

  const ChartComp = chartType === "line" ? Line : chartType === "doughnut" ? Doughnut : Bar;

  return (
    <div className="flex h-full flex-col px-14 py-10" style={{ color: p.text }}>
      <h2 className="mb-2 text-3xl font-semibold md:text-4xl">{slide.title}</h2>
      {slide.subtitle && (
        <p className="mb-4 text-sm" style={{ color: p.muted }}>
          {slide.subtitle}
        </p>
      )}
      <div className="relative flex-1">
        {labels.length && values.length ? (
          <ChartComp data={dataset} options={options} />
        ) : (
          <div
            className="flex h-full items-center justify-center text-sm"
            style={{ color: p.muted }}
          >
            No chart data
          </div>
        )}
      </div>
      {(unit || source) && (
        <div
          className="mt-3 flex items-center justify-between text-xs"
          style={{ color: p.muted }}
        >
          <span>{unit ? `Units: ${unit}` : ""}</span>
          {source && <span>Source: {source}</span>}
        </div>
      )}
    </div>
  );
}

function TableSlide({ slide, p }) {
  const headers = Array.isArray(slide.headers) ? slide.headers : [];
  const rows = Array.isArray(slide.rows) ? slide.rows : [];
  return (
    <div className="flex h-full flex-col px-14 py-10" style={{ color: p.text }}>
      <h2 className="mb-6 text-3xl font-semibold md:text-4xl">{slide.title}</h2>
      <div className="flex-1 overflow-hidden rounded-2xl border" style={{ borderColor: p.accent + "40" }}>
        <table className="w-full text-left text-sm md:text-base">
          {headers.length > 0 && (
            <thead>
              <tr style={{ background: p.accent + "1A" }}>
                {headers.map((h, i) => (
                  <th
                    key={i}
                    className="px-5 py-3 font-medium uppercase tracking-wide"
                    style={{ color: p.accent }}
                  >
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
          )}
          <tbody>
            {rows.map((row, ri) => (
              <tr
                key={ri}
                className="border-t"
                style={{ borderColor: p.accent + "20" }}
              >
                {row.map((cell, ci) => (
                  <td
                    key={ci}
                    className="px-5 py-3"
                    style={{ color: ci === 0 ? p.text : p.muted }}
                  >
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function TimelineSlide({ slide, p }) {
  const events = Array.isArray(slide.events) ? slide.events : [];
  return (
    <div className="flex h-full flex-col px-14 py-10" style={{ color: p.text }}>
      <h2 className="mb-8 text-3xl font-semibold md:text-4xl">{slide.title}</h2>
      <div className="relative flex-1 overflow-y-auto pl-8">
        <div
          className="absolute bottom-2 left-3 top-2 w-px"
          style={{ background: p.accent + "60" }}
        />
        <ul className="space-y-5">
          {events.map((e, i) => (
            <li key={i} className="relative">
              <span
                className="absolute -left-[1.45rem] top-1 inline-block h-3 w-3 rounded-full ring-4"
                style={{
                  background: p.accent,
                  boxShadow: `0 0 0 4px ${p.bg.startsWith("#FFF") || p.bg.includes("FAF") ? "rgba(255,255,255,1)" : "rgba(15,15,20,1)"}`,
                }}
              />
              <div className="flex flex-wrap items-baseline gap-3">
                <span
                  className="text-sm font-semibold tabular-nums"
                  style={{ color: p.accent }}
                >
                  {e.year}
                </span>
                <span className="text-lg font-medium">{e.title}</span>
              </div>
              {e.desc && (
                <p className="mt-1 text-sm leading-relaxed" style={{ color: p.muted }}>
                  {e.desc}
                </p>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function ImageFocusSlide({ slide, p }) {
  return (
    <div className="relative h-full" style={{ color: p.text }}>
      {slide.image_url ? (
        <>
          <img
            src={slide.image_url}
            alt={slide.caption || slide.title}
            loading="lazy"
            className="absolute inset-0 h-full w-full object-cover"
          />
          <div
            className="absolute inset-0"
            style={{
              background:
                p.bg.includes("FAF") || p.bg.startsWith("#FFF")
                  ? "linear-gradient(to top, rgba(250,247,242,0.92) 0%, rgba(250,247,242,0.1) 55%)"
                  : "linear-gradient(to top, rgba(10,10,15,0.92) 0%, rgba(10,10,15,0.1) 55%)",
            }}
          />
        </>
      ) : (
        <div
          className="absolute inset-0 flex items-center justify-center"
          style={{ background: p.accent + "15", color: p.muted }}
        >
          <span className="text-sm uppercase tracking-widest">No image</span>
        </div>
      )}
      <div className="relative flex h-full flex-col justify-end px-14 py-12">
        <h2 className="text-3xl font-semibold md:text-4xl">{slide.title}</h2>
        {slide.caption && (
          <p
            className="mt-3 max-w-2xl text-base leading-relaxed"
            style={{ color: p.muted }}
          >
            {slide.caption}
          </p>
        )}
      </div>
    </div>
  );
}

const layouts = {
  title: TitleSlide,
  bullets: BulletsSlide,
  "two-col": TwoColSlide,
  // Backend ships a dedicated comparison renderer in PPTX; on the web we
  // collapse it onto the same two-col surface (registry says it's canonical).
  comparison: TwoColSlide,
  // Backend's `section` is a divider page; visually it's the title surface.
  section: TitleSlide,
  quote: QuoteSlide,
  stats: StatsSlide,
  chart: ChartSlide,
  table: TableSlide,
  timeline: TimelineSlide,
  "image-focus": ImageFocusSlide,
  closing: ClosingSlide,
  ...EXTRA_LAYOUTS,
};

function resolveLayout(name) {
  const meta = resolveLayoutName(name);
  const Comp = layouts[meta.canonical];
  if (Comp) {
    if (meta.aliased && typeof window !== "undefined" && import.meta.env?.DEV) {
      console.info(`[SlideRenderer] layout "${meta.input}" → alias "${meta.canonical}"`);
    }
    return { Comp, meta };
  }
  // Registered as canonical in the registry but no renderer exists — hard
  // bug; surface in dev with the debug card and fall back to bullets in prod.
  if (typeof window !== "undefined" && import.meta.env?.DEV) {
    console.warn(
      `[SlideRenderer] Unsupported layout "${meta.input}". ` +
        `Add a renderer for "${meta.canonical}" or fix the registry.`,
    );
    return { Comp: UnsupportedLayoutSlide, meta };
  }
  return { Comp: BulletsSlide, meta };
}

export default function SlideRenderer({ slide, theme = "light-pro", deckSeed }) {
  const p = paletteFor(theme);
  // Normalize at the boundary so downstream renderers receive the canonical
  // schema (stats[].value, events[].year, headers/rows split, etc).
  const { slide: normalized } = normalizeSlideContent(slide || {});
  // If the original layout name didn't resolve, expose the debug card in
  // dev (prod silently uses the bullet fallback the registry chose).
  const isUnsupported = !!normalized._layout_unsupported;
  const isDev = typeof window !== "undefined" && import.meta.env?.DEV;
  if (isUnsupported && isDev) {
    console.warn(
      `[SlideRenderer] Unsupported layout "${normalized._layout_unsupported}". ` +
        `Add it to design/layouts.registry.json or alias it.`,
    );
  }
  const { Comp } = isUnsupported && isDev
    ? { Comp: UnsupportedLayoutSlide }
    : resolveLayout(normalized.layout);
  const seed = deckSeed || normalized.deck_id || normalized.task_id || normalized.title || "";
  return (
    <motion.div
      key={slide?.id || slide?.title}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="relative aspect-video w-full overflow-hidden rounded-2xl border border-nexus-border shadow-2xl shadow-black/40"
      style={{ background: p.bg }}
    >
      <Comp slide={normalized} p={p} deckSeed={seed} />
    </motion.div>
  );
}
