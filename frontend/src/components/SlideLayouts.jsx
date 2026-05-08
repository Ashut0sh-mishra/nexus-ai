// SlideLayouts.jsx — 11 Manus-grade layouts built on the design system.
//
// All visual constants come from design/. Adding a new layout:
//   1. Compose with <Frame>, <Section>, <Card>, <MetricBlock>, <IconBadge>.
//   2. Never write `px-12`, `text-3xl`, `gap-6` — use tokens / primitives.
//   3. Register in EXTRA_LAYOUTS at the bottom.
//
// Backward-compat re-exports (SPACING, RADII, SlideFrame, SlideEyebrow,
// SlideTitle, SlideSubtitle) are kept so older callers keep working while
// they migrate to the design system.

import { Sparkles, ArrowRight, ChevronRight } from "lucide-react";
import {
  Frame, Section, Card, IconBadge, MetricBlock, ImageFrame,
  BulletList, Stack, Grid,
  Title, Subtitle, Body, Caption, Eyebrow, Mono,
  slideSpacing, slideSpacingClass,
  radius, accentTints, tintFor, hashString, iconFor,
} from "../design/index.js";

// ─── Backward-compat token shims (do not delete; older code imports these) ──
export const SPACING = Object.freeze({
  framePadX: slideSpacingClass.padX,
  framePadY: slideSpacingClass.padY,
  blockGap: slideSpacingClass.blockGap,
  cardPad: slideSpacingClass.cardPad,
  cardGap: slideSpacingClass.cardGap,
  eyebrowMb: slideSpacingClass.eyebrowToTitle,
  titleMb: slideSpacingClass.titleToBody,
});
export const RADII = Object.freeze({ card: "rounded-2xl", chip: "rounded-full", pill: "rounded-xl" });

// Compat primitives so SlideRenderer's older imports (SlideFrame etc.) work.
export function SlideFrame({ p, children, className = "", style = {} }) {
  return <Frame p={p} className={className} style={style}>{children}</Frame>;
}
export function SlideEyebrow({ children, p }) {
  return <Eyebrow p={p}>{children}</Eyebrow>;
}
export function SlideTitle({ children, p, size = "lg" }) {
  // Map old "lg/md/xl" sizes onto the new typography scale.
  const map = { xl: "h1", lg: "h2", md: "h3", sm: "h4" };
  return (
    <Title p={p} size={map[size] || "h2"} style={{ marginBottom: slideSpacing.titleToBody }}>
      {children}
    </Title>
  );
}
export function SlideSubtitle({ children, p }) {
  return <Subtitle p={p} style={{ marginBottom: slideSpacing.subtitleToBody, maxWidth: "48rem" }}>{children}</Subtitle>;
}
export { tintFor, iconFor, hashString };

// ─── Bullet & "head: body" helpers ──────────────────────────────────────────
export function readBullets(slide, max = 6) {
  if (Array.isArray(slide?.bullets) && slide.bullets.length) {
    return slide.bullets.slice(0, max).map((b) => String(b).trim()).filter(Boolean);
  }
  if (Array.isArray(slide?.columns) && slide.columns.length) {
    return slide.columns
      .slice(0, max)
      .map((c) => `${c.heading || ""}${c.heading && c.body ? ": " : ""}${c.body || ""}`.trim())
      .filter(Boolean);
  }
  if (slide?.body) {
    return String(slide.body)
      .split(/\n+|(?:•|·|—)\s*/)
      .map((s) => s.trim())
      .filter(Boolean)
      .slice(0, max);
  }
  return [];
}

export function splitHeadBody(text, fallbackHead = "") {
  const t = String(text || "").trim();
  const m = t.match(/^([^:—–-]{2,40})\s*[:—–-]\s*(.+)$/);
  if (m) return { head: m[1].trim(), body: m[2].trim() };
  const words = t.split(/\s+/);
  if (words.length > 6) return { head: words.slice(0, 4).join(" "), body: t };
  return { head: fallbackHead || t, body: words.length > 4 ? t : "" };
}

// Fallback used by every layout when bullets are empty.
function FallbackBullets({ slide, p }) {
  return (
    <Frame p={p}>
      <Section eyebrow={slide.eyebrow} title={slide.title} subtitle={slide.subtitle || slide.body} p={p} />
    </Frame>
  );
}

// ─── 1. BENTO ───────────────────────────────────────────────────────────────
export function BentoSlide({ slide, p, deckSeed }) {
  const items = readBullets(slide, 5).map((b, i) => ({ ...splitHeadBody(b, `Item ${i + 1}`), i }));
  if (!items.length) return <FallbackBullets slide={slide} p={p} />;
  const [hero, ...rest] = items;
  const heroTint = tintFor(deckSeed, 0);
  const HeroIcon = iconFor(deckSeed, 0);
  return (
    <Frame p={p}>
      <Section eyebrow={slide.eyebrow || "Highlights"} title={slide.title} p={p} />
      <Grid cols={2} style={{ gridTemplateColumns: "1.4fr 1fr" }}>
        <Card variant="filled" tint={heroTint} p={p} minH="16rem" style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", padding: "1.75rem" }}>
          <HeroIcon style={{ width: "1.75rem", height: "1.75rem" }} strokeWidth={2.4} />
          <div>
            <Mono p={p} tint="rgba(255,255,255,0.85)" style={{ display: "block", marginBottom: "0.5rem" }}>01</Mono>
            <Title p={{ ...p, text: "#FFFFFF" }} size="h3">{hero.head}</Title>
            {hero.body && <Body p={{ ...p, text: "rgba(255,255,255,0.9)" }} style={{ marginTop: "0.5rem" }}>{hero.body}</Body>}
          </div>
        </Card>
        <Stack gap="cardGap">
          {rest.slice(0, 3).map((it) => {
            const Icon = iconFor(deckSeed, it.i);
            const tint = tintFor(deckSeed, it.i);
            return (
              <Card key={it.i} variant="tinted" tint={tint} p={p} style={{ display: "flex", alignItems: "flex-start", gap: slideSpacing.cardGap }}>
                <IconBadge icon={Icon} tint={tint} size="md" />
                <div>
                  <Body p={p} style={{ fontWeight: 700 }}>{it.head}</Body>
                  {it.body && <Caption p={p} style={{ display: "block", marginTop: "0.25rem" }}>{it.body}</Caption>}
                </div>
              </Card>
            );
          })}
        </Stack>
      </Grid>
    </Frame>
  );
}

// ─── 2. ROADMAP ─────────────────────────────────────────────────────────────
export function RoadmapSlide({ slide, p, deckSeed }) {
  const steps = readBullets(slide, 5).map((b, i) => ({ ...splitHeadBody(b, `Phase ${i + 1}`), i }));
  if (!steps.length) return <FallbackBullets slide={slide} p={p} />;
  return (
    <Frame p={p}>
      <Section eyebrow={slide.eyebrow || "Roadmap"} title={slide.title} p={p} />
      <div className="relative">
        <div className="absolute left-0 right-0" style={{ top: "1.5rem", height: 1, background: p.border }} />
        <div className="grid gap-4" style={{ gridTemplateColumns: `repeat(${steps.length}, minmax(0, 1fr))` }}>
          {steps.map((s) => {
            const tint = tintFor(deckSeed, s.i);
            return (
              <div key={s.i} className="flex flex-col items-start">
                <div
                  className="relative z-10 flex items-center justify-center"
                  style={{ width: "3rem", height: "3rem", borderRadius: radius.full, background: tint, color: "#FFFFFF", fontWeight: 700 }}
                >
                  {String(s.i + 1).padStart(2, "0")}
                </div>
                <Body p={p} style={{ fontWeight: 700, marginTop: "1rem" }}>{s.head}</Body>
                {s.body && <Caption p={p} style={{ display: "block", marginTop: "0.25rem" }}>{s.body}</Caption>}
              </div>
            );
          })}
        </div>
      </div>
    </Frame>
  );
}

// ─── 3. PROCESS ─────────────────────────────────────────────────────────────
export function ProcessSlide({ slide, p, deckSeed }) {
  const steps = readBullets(slide, 6).map((b, i) => ({ ...splitHeadBody(b, `Step ${i + 1}`), i }));
  if (!steps.length) return <FallbackBullets slide={slide} p={p} />;
  return (
    <Frame p={p}>
      <Section eyebrow={slide.eyebrow || "Process"} title={slide.title} p={p} />
      <div className="flex flex-wrap items-stretch" style={{ gap: slideSpacing.cardGap }}>
        {steps.map((s, idx) => {
          const tint = tintFor(deckSeed, s.i);
          const Icon = iconFor(deckSeed, s.i);
          return (
            <div key={s.i} className="flex items-stretch" style={{ gap: slideSpacing.cardGap }}>
              <Card variant="tinted" tint={tint} p={p} style={{ width: "11rem", display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                <div className="flex items-center" style={{ gap: "0.5rem" }}>
                  <IconBadge icon={Icon} tint={tint} size="sm" />
                  <Mono p={p} tint={tint}>Step {String(s.i + 1).padStart(2, "0")}</Mono>
                </div>
                <Body p={p} style={{ fontWeight: 700 }}>{s.head}</Body>
                {s.body && <Caption p={p}>{s.body}</Caption>}
              </Card>
              {idx < steps.length - 1 && <ChevronRight className="my-auto h-5 w-5 shrink-0" style={{ color: p.muted }} />}
            </div>
          );
        })}
      </div>
    </Frame>
  );
}

// ─── 4. FEATURE-GRID ────────────────────────────────────────────────────────
export function FeatureGridSlide({ slide, p, deckSeed }) {
  const items = readBullets(slide, 6).map((b, i) => ({ ...splitHeadBody(b, `Feature ${i + 1}`), i }));
  if (!items.length) return <FallbackBullets slide={slide} p={p} />;
  const cols = items.length <= 2 ? 2 : items.length <= 4 ? 2 : 3;
  return (
    <Frame p={p}>
      <Section eyebrow={slide.eyebrow || "Features"} title={slide.title} subtitle={slide.subtitle} p={p} />
      <Grid cols={cols}>
        {items.map((it) => {
          const tint = tintFor(deckSeed, it.i);
          const Icon = iconFor(deckSeed, it.i);
          return (
            <Card key={it.i} variant="tinted" tint={tint} p={p} minH="8.5rem" style={{ display: "flex", flexDirection: "column", gap: slideSpacing.cardGap }}>
              <IconBadge icon={Icon} tint={tint} size="md" />
              <Body p={p} style={{ fontWeight: 700 }}>{it.head}</Body>
              {it.body && <Caption p={p}>{it.body}</Caption>}
            </Card>
          );
        })}
      </Grid>
    </Frame>
  );
}

// ─── 5. METRIC-SPOTLIGHT ────────────────────────────────────────────────────
// Backend contract: prefer slide.stats[0] when present (planner sends
// `{ stats: [{value, label}] }` for this layout). Fall back to regex on
// title/body for legacy decks.
export function MetricSpotlightSlide({ slide, p, deckSeed }) {
  const stat = Array.isArray(slide?.stats) && slide.stats[0];
  let value = stat?.value || slide.metric;
  let label = stat?.label || slide.metric_label;
  if (!value) {
    const haystack = [slide.title, slide.subtitle, slide.body, ...(slide.bullets || [])].filter(Boolean).join(" ");
    const m = haystack.match(/(\d+(?:\.\d+)?\s*[%KMBkmb]?|\$\s?\d[\d,]*)/);
    value = m ? m[0].trim() : (slide.bullets?.[0] || "—");
  }
  const supporting = readBullets(slide, 4).filter((b) => !value || !b.includes(String(value))).slice(0, 3);
  const tint = tintFor(deckSeed, 0);
  return (
    <Frame p={p}>
      <Section eyebrow={slide.eyebrow || "Key Metric"} p={p} />
      <div className="grid flex-1" style={{ gridTemplateColumns: "1.1fr 1fr", gap: "2rem", alignItems: "center" }}>
        <MetricBlock value={value} label={label} tint={tint} p={p} size="xl" />
        <Stack gap="cardBlockGap">
          <Title p={p} size="h3">{slide.title}</Title>
          {supporting.length > 0 && <BulletList items={supporting} p={p} tint={tint} />}
        </Stack>
      </div>
    </Frame>
  );
}

// ─── 5b. KPI ────────────────────────────────────────────────────────────────
// Multi-stat dashboard (backend layout `kpi`). Renders 3-4 MetricBlocks in a row.
export function KpiSlide({ slide, p, deckSeed }) {
  let stats = Array.isArray(slide?.stats) ? slide.stats : [];
  // Fallback: parse "<num> <label>" out of bullets.
  if (!stats.length) {
    stats = readBullets(slide, 4)
      .map((b) => {
        const m = b.match(/^([^a-zA-Z]*\d[\d.,KMB%kmb$\s]*)[\s—–-]+(.+)$/);
        return m ? { value: m[1].trim(), label: m[2].trim() } : null;
      })
      .filter(Boolean);
  }
  if (!stats.length) return <FallbackBullets slide={slide} p={p} />;
  const cols = Math.min(stats.length, 4);
  return (
    <Frame p={p}>
      <Section eyebrow={slide.eyebrow || "Key Numbers"} title={slide.title} subtitle={slide.subtitle} p={p} />
      <Grid cols={cols}>
        {stats.slice(0, 4).map((s, i) => {
          const tint = tintFor(deckSeed, i);
          return (
            <Card key={i} variant="elevated" p={p} style={{ display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "flex-start" }}>
              <MetricBlock value={s.value} label={s.label} caption={s.caption} tint={tint} p={p} size="md" />
            </Card>
          );
        })}
      </Grid>
    </Frame>
  );
}

// ─── 6. HERO ────────────────────────────────────────────────────────────────
export function HeroSlide({ slide, p }) {
  const img = slide.image_url || slide.image || slide.hero_image;
  return (
    <div className="relative h-full w-full overflow-hidden" style={{ background: p.bg }}>
      {img ? (
        <ImageFrame src={img} scrim="full" rounded="none" className="absolute inset-0" style={{ aspectRatio: "auto", height: "100%", width: "100%" }} />
      ) : (
        <div className="absolute inset-0" style={{ background: `linear-gradient(135deg, ${p.accent}55 0%, ${p.bg} 100%)` }} />
      )}
      <Frame p={img ? { ...p, text: "#FFFFFF", muted: "#E5E7EB" } : p} className="relative justify-end">
        {slide.eyebrow && (
          <div
            className="mb-3 inline-block self-start"
            style={{ background: p.accent, color: "#FFFFFF", borderRadius: radius.full, padding: "0.25rem 0.75rem", fontSize: "0.6875rem", fontWeight: 600, letterSpacing: "0.32em", textTransform: "uppercase" }}
          >
            {slide.eyebrow}
          </div>
        )}
        <Title p={img ? { ...p, text: "#FFFFFF" } : p} size="h1" style={{ fontSize: "clamp(3rem, 6vw, 5rem)", fontWeight: 900 }}>
          {slide.title}
        </Title>
        {slide.subtitle && (
          <Subtitle p={img ? { ...p, muted: "#E5E7EB" } : p} style={{ marginTop: "1rem", maxWidth: "42rem" }}>
            {slide.subtitle}
          </Subtitle>
        )}
      </Frame>
    </div>
  );
}

// ─── 7. PYRAMID ─────────────────────────────────────────────────────────────
export function PyramidSlide({ slide, p, deckSeed }) {
  const tiers = readBullets(slide, 4).map((b, i) => ({ ...splitHeadBody(b, `Tier ${i + 1}`), i }));
  if (!tiers.length) return <FallbackBullets slide={slide} p={p} />;
  const widths = ["40%", "65%", "90%", "100%"];
  return (
    <Frame p={p}>
      <Section eyebrow={slide.eyebrow || "Hierarchy"} title={slide.title} p={p} />
      <div className="flex flex-col items-center" style={{ gap: "0.5rem" }}>
        {tiers.map((t, idx) => {
          const tint = tintFor(deckSeed, idx);
          return (
            <div
              key={t.i}
              className="flex items-center justify-center text-center"
              style={{ width: widths[idx] || "100%", background: tint, color: "#FFFFFF", borderRadius: radius.lg, padding: "0.75rem 1.5rem", minHeight: "3rem" }}
            >
              <div>
                <Body p={{ ...p, text: "#FFFFFF" }} style={{ fontWeight: 700 }}>{t.head}</Body>
                {t.body && <Caption p={{ ...p, muted: "rgba(255,255,255,0.9)" }}>{t.body}</Caption>}
              </div>
            </div>
          );
        })}
      </div>
    </Frame>
  );
}

// ─── 8. MATRIX-2x2 ──────────────────────────────────────────────────────────
export function Matrix2x2Slide({ slide, p, deckSeed }) {
  const labels = ["High Impact", "Quick Win", "Strategic", "Avoid"];
  const items = readBullets(slide, 4).map((b, i) => ({ ...splitHeadBody(b, labels[i]), i }));
  while (items.length < 4) items.push({ head: "—", body: "", i: items.length });
  const axis = slide.axis || { x: "Impact →", y: "Effort ↑" };
  return (
    <Frame p={p}>
      <Section eyebrow={slide.eyebrow || "Matrix"} title={slide.title} p={p} size="h3" />
      <div className="flex flex-1" style={{ gap: slideSpacing.cardGap }}>
        <div
          className="flex items-center justify-center"
          style={{ color: p.muted, writingMode: "vertical-rl", transform: "rotate(180deg)", fontSize: "0.6875rem", fontWeight: 600, letterSpacing: "0.18em", textTransform: "uppercase" }}
        >
          {axis.y}
        </div>
        <div className="flex flex-1 flex-col" style={{ gap: slideSpacing.cardGap }}>
          <div className="grid flex-1" style={{ gridTemplateColumns: "1fr 1fr", gridTemplateRows: "1fr 1fr", gap: slideSpacing.cardGap }}>
            {items.slice(0, 4).map((it) => {
              const tint = tintFor(deckSeed, it.i);
              return (
                <Card key={it.i} variant="tinted" tint={tint} p={p} minH="5.5rem" style={{ display: "flex", flexDirection: "column", justifyContent: "center" }}>
                  <Body p={p} style={{ fontWeight: 700, color: tint }}>{it.head}</Body>
                  {it.body && <Caption p={p} style={{ display: "block", marginTop: "0.25rem" }}>{it.body}</Caption>}
                </Card>
              );
            })}
          </div>
          <Mono p={p} style={{ textAlign: "center" }}>{axis.x}</Mono>
        </div>
      </div>
    </Frame>
  );
}

// ─── 9. AGENDA ──────────────────────────────────────────────────────────────
export function AgendaSlide({ slide, p, deckSeed }) {
  const items = readBullets(slide, 8).map((b, i) => ({ ...splitHeadBody(b, b), i }));
  if (!items.length) return <FallbackBullets slide={slide} p={p} />;
  return (
    <Frame p={p}>
      <Section eyebrow={slide.eyebrow || "Agenda"} title={slide.title || "Agenda"} p={p} />
      <div className="grid" style={{ gridTemplateColumns: items.length > 4 ? "1fr 1fr" : "1fr", gap: slideSpacing.cardGap }}>
        {items.map((it) => {
          const tint = tintFor(deckSeed, it.i);
          return (
            <div key={it.i} className="flex items-center border-b" style={{ gap: "1rem", padding: "0.75rem 0", borderColor: p.border }}>
              <div
                className="flex items-center justify-center shrink-0"
                style={{ width: "2.5rem", height: "2.5rem", borderRadius: radius.full, background: `${tint}20`, color: tint, fontWeight: 900, fontSize: "0.875rem" }}
              >
                {String(it.i + 1).padStart(2, "0")}
              </div>
              <div className="min-w-0">
                <Body p={p} style={{ fontWeight: 600, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{it.head}</Body>
                {it.body && it.body !== it.head && <Caption p={p} style={{ display: "block", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{it.body}</Caption>}
              </div>
            </div>
          );
        })}
      </div>
    </Frame>
  );
}

// ─── 10. CALLOUT ────────────────────────────────────────────────────────────
export function CalloutSlide({ slide, p, deckSeed }) {
  const bullets = readBullets(slide, 4);
  const lead = slide.callout || slide.subtitle || bullets[0] || slide.title || "";
  const supporting = bullets.slice(slide.callout || slide.subtitle ? 0 : 1, 4);
  const tint = tintFor(deckSeed, 0);
  return (
    <Frame p={p}>
      <Section eyebrow={slide.eyebrow || "Insight"} title={slide.title} p={p} size="h3" />
      <Card variant="filled" tint={tint} p={p} style={{ marginBottom: slideSpacing.blockGap, padding: "1.75rem" }}>
        <Sparkles className="mb-3 h-6 w-6" strokeWidth={2.4} />
        <Title p={{ ...p, text: "#FFFFFF" }} size="h2">{lead}</Title>
      </Card>
      {supporting.length > 0 && (
        <Grid cols={Math.min(supporting.length, 3)}>
          {supporting.map((b, i) => {
            const t = tintFor(deckSeed, i + 1);
            return (
              <Card key={i} variant="tinted" tint={t} p={p} style={{ display: "flex", alignItems: "flex-start", gap: "0.5rem" }}>
                <ArrowRight className="mt-0.5 h-4 w-4 shrink-0" style={{ color: t }} />
                <Caption p={p}>{b}</Caption>
              </Card>
            );
          })}
        </Grid>
      )}
    </Frame>
  );
}

// ─── Registry ───────────────────────────────────────────────────────────────
export const EXTRA_LAYOUTS = {
  bento: BentoSlide,
  roadmap: RoadmapSlide,
  process: ProcessSlide,
  "feature-grid": FeatureGridSlide,
  "metric-spotlight": MetricSpotlightSlide,
  kpi: KpiSlide,
  hero: HeroSlide,
  pyramid: PyramidSlide,
  "matrix-2x2": Matrix2x2Slide,
  agenda: AgendaSlide,
  callout: CalloutSlide,
};

// Names backend may emit that map onto a registered renderer.
// Sourced from the canonical registry — never hand-edited here.
// Edit `frontend/src/design/layouts.registry.json` instead.
export { LAYOUT_ALIASES } from "../design/registry.js";
