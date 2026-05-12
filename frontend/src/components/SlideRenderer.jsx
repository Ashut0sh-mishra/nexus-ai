import { motion } from "framer-motion";
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

import { paletteFor } from "../design/themes.js";
import {
  Eyebrow,
  Header,
  HeroMetric,
  TimelineSpine,
  ComparisonAxis,
  ComparisonSide as ComparisonSidePrim,
  SectionDividerBlock,
  SlideFrame,
} from "./slidePrimitives.jsx";
import CitationMark from "./CitationMark.jsx";

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

// Deterministic variant selector — picks a visual variant based on slide id
// so the same deck always renders consistently but different slides look different.
function variantOf(slideId = "", n = 2) {
  const m = (slideId || "").match(/(\d+)$/);
  return m ? parseInt(m[1], 10) % n : 0;
}

// ── Phase 6AF: claim-level citation markers ───────────────────────────────
// Backend pipeline (`agent/citation_attach.py`) attaches `slide.citations`
// — a list of { path, marker, supported, basis, source_url, source_title }.
// Phase 6AJ: rendering is delegated to ``components/CitationMark.jsx`` which
// upgrades the legacy native ``title=`` tooltip to a documentary-style
// hover popover (source title, domain, basis chip, claim quote, link).
// The thin alias below keeps every existing call site untouched and
// preserves the additive contract (returns null when no marker exists).
const CiteMarker = CitationMark;

function isLight(bg = "") {
  return bg.startsWith("#FFF") || bg.startsWith("#FAF") || bg.startsWith("#F9F")
    || bg.startsWith("#EFF") || bg.startsWith("#F1F") || bg.startsWith("#FEF")
    || bg.includes("EFF6FF") || bg.includes("FAF7F") || bg.includes("F9F5");
}

// ── Hero image helpers ────────────────────────────────────────────────────────

function HeroFull({ src }) {
  if (!src) return null;
  // Phase 6AL-Visuals follow-up: pre-fix HeroFull crushed the image to
  // opacity-40 + 50→72% black overlay — on dark imagery this read as a
  // black rectangle with text floating on it (the "ugliest PPT" cover).
  // We now show the image at full opacity and use a thin bottom-weighted
  // scrim only where the title sits, so the image actually breathes.
  return (
    <div className="pointer-events-none absolute inset-0">
      <img src={src} alt="" loading="lazy" className="h-full w-full object-cover" />
      <div
        className="absolute inset-0"
        style={{
          background:
            "linear-gradient(180deg, rgba(0,0,0,0.05) 0%, rgba(0,0,0,0.25) 45%, rgba(0,0,0,0.78) 100%)",
        }}
      />
    </div>
  );
}

function HeroRight({ src, p }) {
  if (!src) return null;
  return (
    <div className="pointer-events-none absolute inset-y-0 right-0 w-[38%]">
      <img src={src} alt="" loading="lazy" className="h-full w-full object-cover" />
      <div className="absolute inset-0" style={{
        background: `linear-gradient(to right, ${isLight(p.bg) ? "rgba(249,245,240,0.96)" : "rgba(15,15,20,0.88)"} 0%, transparent 65%)`,
      }} />
    </div>
  );
}

// ── Title slide — 2 variants ──────────────────────────────────────────────────

function TitleSlide({ slide, p }) {
  // Phase 6AL-Visuals follow-up: collapsed the two variants into one.
  // The previous variantOf() roll meant ~50% of decks rendered the
  // pre-6AL "centered + HeroFull dark gradient" cover — the single
  // most complained-about visual in the deck. One cover composition,
  // every time, so every deck looks like the new direction intends.
  return <TitleSlideSplit slide={slide} p={p} />;
}

function TitleSlideSplit({ slide, p }) {
  // Phase 6AL-Visuals: full-bleed cinematic cover.
  // Pre-6AL composition was a 58/42 split with a solid accent panel and
  // a sun-glyph disc on the right — the single biggest source of
  // "PowerPoint template" energy in the deck. We now use a full-bleed
  // image with a dark gradient scrim and a bottom-left editorial title
  // block. No disc, no accent panel, no fake brand bar.
  const hasImage = !!slide.image_url;
  return (
    <div className="relative h-full overflow-hidden" style={{ color: p.text, background: p.bg }}>
      {hasImage && (
        <>
          <img
            src={slide.image_url}
            alt=""
            loading="lazy"
            className="absolute inset-0 h-full w-full object-cover"
          />
          <div
            className="absolute inset-0"
            style={{
              background:
                "linear-gradient(180deg, rgba(0,0,0,0.15) 0%, rgba(0,0,0,0.55) 55%, rgba(0,0,0,0.85) 100%)",
            }}
          />
        </>
      )}
      <div className="relative flex h-full flex-col justify-end px-16 pb-14 pt-12">
        {slide.eyebrow && (
          <div
            className="mb-6 text-[0.7rem] font-semibold uppercase tracking-[0.36em]"
            style={{ color: hasImage ? "rgba(255,255,255,0.78)" : p.accent }}
          >
            {slide.eyebrow}
          </div>
        )}
        <h1
          className="max-w-[78%] font-extrabold leading-[0.92]"
          style={{
            color: hasImage ? "#FFFFFF" : p.text,
            fontSize: "clamp(3.5rem, 7.5vw, 6.5rem)",
            letterSpacing: "-0.035em",
          }}
        >
          {slide.title}
        </h1>
        {slide.subtitle && (
          <p
            className="mt-6 max-w-xl text-lg leading-relaxed"
            style={{ color: hasImage ? "rgba(255,255,255,0.75)" : p.muted }}
          >
            {slide.subtitle}
          </p>
        )}
        <div
          className="mt-8 h-px w-20"
          style={{ background: hasImage ? "rgba(255,255,255,0.55)" : p.accent }}
        />
      </div>
    </div>
  );
}

// ── Bullets slide — 3 variants ────────────────────────────────────────────────

function BulletsSlide({ slide, p }) {
  const v = variantOf(slide.id, 3);
  if (v === 1) return <BulletsNumbered slide={slide} p={p} />;
  if (v === 2) return <BulletsBarred slide={slide} p={p} />;
  return <BulletsDefault slide={slide} p={p} />;
}

function BulletsDefault({ slide, p }) {
  // Phase 6AL-Visuals: typography uplift. Title was text-3xl/4xl which
  // reads as utilitarian. We now use a fluid clamp + tighter tracking so
  // hierarchy is dramatic. Body bullets stay at text-lg.
  const hasImg = !!slide.image_url;
  return (
    <div className="relative h-full" style={{ color: p.text }}>
      <HeroRight src={slide.image_url} p={p} />
      <div className={`relative flex h-full flex-col px-14 py-12 ${hasImg ? "pr-[44%]" : ""}`}>
        <h2
          className="mb-10 font-bold leading-[0.95]"
          style={{ fontSize: "clamp(2.25rem, 4vw, 3.5rem)", letterSpacing: "-0.025em" }}
        >
          {slide.title}
        </h2>
        <ul className="space-y-4">
          {(slide.bullets || []).map((b, i) => (
            <li key={i} className="flex items-start gap-3 text-lg">
              <span className="mt-[9px] inline-block h-2 w-2 shrink-0 rounded-full" style={{ background: p.accent }} />
              <span>{b}<CiteMarker slide={slide} path={`bullets[${i}]`} p={p} /></span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function BulletsNumbered({ slide, p }) {
  const hasImg = !!slide.image_url;
  return (
    <div className="relative h-full" style={{ color: p.text }}>
      <HeroRight src={slide.image_url} p={p} />
      <div className={`relative flex h-full flex-col px-14 py-12 ${hasImg ? "pr-[44%]" : ""}`}>
        <h2 className="mb-8 text-3xl font-semibold md:text-4xl">{slide.title}</h2>
        <ul className="space-y-3">
          {(slide.bullets || []).map((b, i) => (
            <li key={i} className="flex items-baseline gap-5">
              <span className="shrink-0 text-4xl font-black tabular-nums leading-none"
                style={{ color: p.accent, opacity: 0.35 + i * 0.15 }}>
                {String(i + 1).padStart(2, "0")}
              </span>
              <span className="text-lg leading-snug">{b}<CiteMarker slide={slide} path={`bullets[${i}]`} p={p} /></span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

function BulletsBarred({ slide, p }) {
  const hasImg = !!slide.image_url;
  return (
    <div className="relative h-full" style={{ color: p.text }}>
      <HeroRight src={slide.image_url} p={p} />
      <div className={`relative flex h-full flex-col px-14 py-12 ${hasImg ? "pr-[44%]" : ""}`}>
        <h2 className="mb-8 text-3xl font-semibold md:text-4xl">{slide.title}</h2>
        <ul className="space-y-1">
          {(slide.bullets || []).map((b, i) => (
            <li key={i} className="flex items-stretch gap-0">
              <div className="mr-5 w-1 shrink-0 rounded-full" style={{ background: p.accent, opacity: 0.5 + i * 0.12 }} />
              <span className="py-2.5 text-lg leading-snug">{b}<CiteMarker slide={slide} path={`bullets[${i}]`} p={p} /></span>
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

// ── Two-col slide — 3 variants ────────────────────────────────────────────────

function TwoColSlide({ slide, p }) {
  const v = variantOf(slide.id, 3);
  if (v === 1) return <TwoColDivider slide={slide} p={p} />;
  if (v === 2) return <TwoColAsymmetric slide={slide} p={p} />;
  return <TwoColCards slide={slide} p={p} />;
}

function TwoColCards({ slide, p }) {
  const cols = slide.columns || [];
  return (
    <div className="relative h-full" style={{ color: p.text }}>
      <HeroRight src={slide.image_url} p={p} />
      <div className={`relative flex h-full flex-col px-14 py-12 ${slide.image_url ? "pr-[44%]" : ""}`}>
        <h2 className="mb-8 text-3xl font-semibold md:text-4xl">{slide.title}</h2>
        <div className="grid flex-1 grid-cols-2 gap-6">
          {cols.slice(0, 2).map((c, i) => (
            <div key={i} className="rounded-xl border p-6" style={{ borderColor: p.accent + "35" }}>
              <h3 className="mb-3 text-lg font-semibold" style={{ color: p.accent }}>{c.heading}</h3>
              <p className="text-base leading-relaxed" style={{ color: p.muted }}>{c.body}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function TwoColDivider({ slide, p }) {
  const cols = slide.columns || [];
  return (
    <div className="relative h-full" style={{ color: p.text }}>
      <div className="relative flex h-full flex-col px-14 py-12">
        <h2 className="mb-10 text-3xl font-semibold md:text-4xl">{slide.title}</h2>
        <div className="flex flex-1 gap-0">
          {cols.slice(0, 2).map((c, i) => (
            <div key={i} className={`flex flex-1 flex-col ${i === 0 ? "pr-10 border-r" : "pl-10"}`}
              style={{ borderColor: p.accent + "30" }}>
              <h3 className="mb-4 text-sm font-semibold uppercase tracking-widest" style={{ color: p.accent }}>{c.heading}</h3>
              <p className="text-base leading-relaxed" style={{ color: p.muted }}>{c.body}</p>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function TwoColAsymmetric({ slide, p }) {
  const cols = slide.columns || [];
  return (
    <div className="relative h-full" style={{ color: p.text }}>
      <div className="relative grid h-full grid-cols-[55%_45%]">
        {/* Left — wider, accent-tinted panel */}
        <div className="flex flex-col justify-center px-14 py-12" style={{ background: p.accent + "12" }}>
          {cols[0] && (
            <>
              <div className="mb-3 text-xs font-semibold uppercase tracking-widest" style={{ color: p.accent }}>
                {cols[0].heading}
              </div>
              <p className="text-lg leading-relaxed">{cols[0].body}</p>
            </>
          )}
        </div>
        {/* Right — plain with title at top */}
        <div className="flex flex-col px-10 py-12">
          <h2 className="mb-8 text-2xl font-semibold">{slide.title}</h2>
          {cols[1] && (
            <>
              <div className="mb-2 text-xs font-semibold uppercase tracking-widest" style={{ color: p.muted }}>
                {cols[1].heading}
              </div>
              <p className="text-base leading-relaxed" style={{ color: p.muted }}>{cols[1].body}</p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ── Quote slide — 2 variants ──────────────────────────────────────────────────

function QuoteSlide({ slide, p }) {
  // Phase 6AK: cinematic promotion — the deck's first attributed quote
  // is marked is_hero by `agent.cinematic_marker`. We render it as a
  // magazine-style asymmetric pull-quote instead of a centered block.
  if (slide.is_hero && slide.attribution) {
    return <QuoteEditorial slide={slide} p={p} />;
  }
  const v = variantOf(slide.id, 2);
  if (v === 1) return <QuoteSide slide={slide} p={p} />;
  return <QuoteCentered slide={slide} p={p} />;
}

// Phase 6AK — editorial / magazine pull-quote.
// Asymmetric composition: oversized ❝ glyph in the top-left, quote text
// justified flush-right, attribution as a bottom-baseline caption bar.
// Negative space dominates the top-right and the left margin under the
// glyph. Single dominant moment per deck.
function QuoteEditorial({ slide, p }) {
  // Phase 6AL-Visuals: full-bleed atmosphere when an image is attached
  // (the hero quote is now in _IMAGE_LAYOUTS). Composition still
  // asymmetric: oversized open-quote glyph top-left, quote text
  // justified flush-right, attribution as a thin baseline rule.
  const hasImg = !!slide.image_url;
  const fgText = hasImg ? "#FFFFFF" : p.text;
  const fgAccent = hasImg ? "rgba(255,255,255,0.85)" : p.accent;
  return (
    <div className="relative h-full overflow-hidden" style={{ color: p.text }}>
      {hasImg && (
        <>
          <img
            src={slide.image_url}
            alt=""
            loading="lazy"
            className="absolute inset-0 h-full w-full object-cover"
          />
          <div
            className="absolute inset-0"
            style={{
              background:
                "linear-gradient(135deg, rgba(0,0,0,0.78) 0%, rgba(0,0,0,0.45) 60%, rgba(0,0,0,0.78) 100%)",
            }}
          />
        </>
      )}
      <span
        aria-hidden
        className="absolute left-6 top-2 select-none font-black leading-none"
        style={{
          color: hasImg ? "rgba(255,255,255,0.22)" : p.accent,
          opacity: hasImg ? 1 : 0.18,
          fontSize: "20rem",
        }}
      >
        “
      </span>
      <div className="relative flex h-full flex-col justify-end px-16 pb-12 pt-24">
        <blockquote
          className="ml-auto max-w-[72%] text-right font-semibold leading-[1.12]"
          style={{
            color: fgText,
            fontSize: "clamp(2rem, 4.2vw, 4rem)",
            letterSpacing: "-0.02em",
          }}
        >
          {slide.quote}
        </blockquote>
        {slide.attribution && (
          <div className="mt-10 flex items-center gap-4">
            <div
              className="h-px flex-1"
              style={{ background: hasImg ? "rgba(255,255,255,0.45)" : p.accent + "55" }}
            />
            <p
              className="shrink-0 text-xs font-semibold uppercase tracking-[0.32em]"
              style={{ color: fgAccent }}
            >
              {slide.attribution}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function QuoteCentered({ slide, p }) {
  return (
    <div className="flex h-full flex-col items-center justify-center px-16 text-center" style={{ color: p.text }}>
      <span className="mb-6 text-8xl leading-none font-black" style={{ color: p.accent, opacity: 0.6 }}>"</span>
      <blockquote className="text-2xl font-medium leading-snug md:text-3xl max-w-3xl">{slide.quote}</blockquote>
      {slide.attribution && (
        <p className="mt-8 text-sm uppercase tracking-widest" style={{ color: p.muted }}>— {slide.attribution}</p>
      )}
    </div>
  );
}

function QuoteSide({ slide, p }) {
  return (
    <div className="flex h-full items-center gap-0" style={{ color: p.text }}>
      <div className="h-full w-2 shrink-0" style={{ background: p.accent }} />
      <div className="flex flex-col justify-center px-14 py-16 max-w-3xl">
        <blockquote className="text-2xl font-medium leading-snug md:text-3xl italic">{slide.quote}</blockquote>
        {slide.attribution && (
          <div className="mt-8 flex items-center gap-3">
            <div className="h-px flex-1" style={{ background: p.accent + "40" }} />
            <p className="text-sm font-medium uppercase tracking-widest shrink-0" style={{ color: p.accent }}>
              {slide.attribution}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Stats slide — 2 variants ──────────────────────────────────────────────────

function StatsSlide({ slide, p }) {
  const v = variantOf(slide.id, 2);
  if (v === 1) return <StatsHero slide={slide} p={p} />;
  return <StatsGrid slide={slide} p={p} />;
}

function StatsGrid({ slide, p }) {
  const stats = (slide.stats || []).slice(0, 3);
  return (
    <div className="flex h-full flex-col px-14 py-12" style={{ color: p.text }}>
      <h2 className="mb-10 text-3xl font-semibold md:text-4xl">{slide.title}</h2>
      <div className="grid flex-1 grid-cols-3 gap-6">
        {stats.map((s, i) => (
          <div key={i} className="flex flex-col items-center justify-center rounded-2xl border p-6 text-center"
            style={{ borderColor: p.accent + "35" }}>
            <div className="text-5xl font-black tabular-nums md:text-6xl" style={{ color: p.accent }}>
              {s.value}<CiteMarker slide={slide} path={`stats[${i}]`} p={p} />
            </div>
            <div className="mt-3 text-sm uppercase tracking-wide" style={{ color: p.muted }}>{s.label}</div>
          </div>
        ))}
      </div>
    </div>
  );
}

function StatsHero({ slide, p }) {
  const stats = (slide.stats || []).slice(0, 3);
  const [hero, ...rest] = stats;
  return (
    <div className="flex h-full flex-col px-14 py-12" style={{ color: p.text }}>
      <h2 className="mb-6 text-3xl font-semibold md:text-4xl">{slide.title}</h2>
      {hero && (
        <div className="flex flex-1 flex-col items-start justify-center">
          <div className="text-[5.5rem] font-black leading-none tabular-nums" style={{ color: p.accent }}>
            {hero.value}<CiteMarker slide={slide} path="stats[0]" p={p} />
          </div>
          <div className="mt-2 text-base uppercase tracking-widest" style={{ color: p.muted }}>{hero.label}</div>
          {rest.length > 0 && (
            <div className="mt-8 flex gap-10">
              {rest.map((s, i) => (
                <div key={i}>
                  <div className="text-3xl font-bold tabular-nums" style={{ color: p.text }}>{s.value}<CiteMarker slide={slide} path={`stats[${i + 1}]`} p={p} /></div>
                  <div className="mt-1 text-xs uppercase tracking-wide" style={{ color: p.muted }}>{s.label}</div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── BigStat slide — single dominant metric (Phase 6AA, refactored 6AE) ──────
// Phase 6AE: composes Eyebrow + HeroMetric inside SlideFrame. Visual
// output is identical to the pre-6AE handcrafted version.
// Phase 6AK: when `slide.is_hero` is set by `agent.cinematic_marker`,
// render the full-bleed cinematic variant instead. Both variants share
// the same `value`/`label`/`subtitle` resolution rules so a slide that
// was being shown by `BigStatSlide` can opt-in without any backend
// content change.

function BigStatSlide({ slide, p }) {
  const value = slide.value || (slide.stats && slide.stats[0] && slide.stats[0].value) || "";
  const label = slide.label || (slide.stats && slide.stats[0] && slide.stats[0].label) || "";
  const subtitle = slide.subtitle || "";
  if (slide.is_hero) {
    return <BigStatCinematic slide={slide} value={value} label={label} subtitle={subtitle} p={p} />;
  }
  return (
    <SlideFrame p={p}>
      {slide.title && <Eyebrow p={p}>{slide.title}</Eyebrow>}
      <div className="flex flex-1 flex-col">
        <HeroMetric value={value} label={label} subtitle={subtitle} p={p} size="lg" />
      </div>
    </SlideFrame>
  );
}

// Phase 6AK — full-bleed cinematic bigstat.
// Layout: a 60/40 split where the *left* 60% is a deeply accent-tinted
// panel carrying just the metric number (oversized, bleeding toward the
// vertical centerline). The right 40% holds eyebrow + label + subtitle
// stacked at the baseline, leaving the top-right deliberately empty.
// This is the deck's single dominant moment and stays asymmetric on
// purpose — no centered axis, no balanced grid.
function BigStatCinematic({ slide, value, label, subtitle, p }) {
  return (
    <div className="relative grid h-full grid-cols-[60%_40%]" style={{ color: p.text }}>
      {/* Left — full-bleed accent panel with oversized number */}
      <div
        className="relative flex h-full items-center justify-end overflow-hidden pr-8"
        style={{ background: `linear-gradient(135deg, ${p.accent}EE 0%, ${p.accent}CC 100%)` }}
      >
        <div
          className="select-none font-black leading-[0.85] tabular-nums"
          style={{
            color: "#FFFFFF",
            fontSize: "clamp(8rem, 18vw, 16rem)",
            letterSpacing: "-0.04em",
            textShadow: "0 8px 40px rgba(0,0,0,0.18)",
          }}
        >
          {value || "—"}
        </div>
      </div>
      {/* Right — quiet text column anchored at the bottom */}
      <div className="relative flex h-full flex-col justify-end px-10 py-12">
        {slide.title && (
          <div
            className="mb-auto pt-2 text-[11px] font-semibold uppercase tracking-[0.32em]"
            style={{ color: p.muted }}
          >
            {slide.title}
          </div>
        )}
        {label && (
          <div
            className="text-xl font-semibold uppercase leading-tight tracking-[0.08em]"
            style={{ color: p.text }}
          >
            {label}
          </div>
        )}
        {subtitle && (
          <p className="mt-4 max-w-xs text-sm leading-relaxed" style={{ color: p.muted }}>
            {subtitle}
          </p>
        )}
        <div className="mt-6 h-px w-12" style={{ background: p.accent }} />
      </div>
    </div>
  );
}

// ── Section Divider — typography pause (Phase 6AA, refactored 6AE) ─────────
// Phase 6AE: thin shell over SectionDividerBlock primitive.
// Phase 6AK: when `is_hero` is set, swap in the asymmetric cinematic
// variant — left-anchored sequence number, oversized left-justified
// title, deliberate negative space on the right.

function SectionDividerSlide({ slide, p }) {
  if (slide.is_hero) {
    return <SectionDividerCinematic slide={slide} p={p} />;
  }
  return (
    <SectionDividerBlock
      eyebrow={slide.eyebrow}
      title={slide.title}
      subtitle={slide.subtitle}
      p={p}
    />
  );
}

// Phase 6AK — editorial chapter break.
// Asymmetric magazine page break: a large sequence number ("01" /
// "PART 02" / first letter of the eyebrow) hugs the upper-left corner
// in muted accent; the title is left-justified, oversized, and runs to
// roughly 70% of the canvas width before yielding to negative space on
// the right. Subtitle floats below as a single short line. No centered
// axis, no rule — the silence on the right *is* the rule.
function SectionDividerCinematic({ slide, p }) {
  // Derive a short sequence marker. Prefer a literal number found in
  // the eyebrow (e.g. "Chapter 2", "Section 03"); fall back to "▍".
  const eyebrowText = (slide.eyebrow || "").trim();
  const numMatch = eyebrowText.match(/\b(\d{1,2})\b/);
  const marker = numMatch ? String(parseInt(numMatch[1], 10)).padStart(2, "0") : "▍";
  const eyebrowLabel =
    eyebrowText && !numMatch ? eyebrowText.toUpperCase() : "CHAPTER";
  return (
    <div className="relative h-full" style={{ color: p.text }}>
      <div className="flex h-full flex-col justify-center px-16 py-16">
        <div className="mb-4 flex items-baseline gap-4">
          <span
            className="select-none font-black leading-none tabular-nums"
            style={{
              color: p.accent,
              opacity: 0.22,
              fontSize: "clamp(5rem, 9vw, 8rem)",
              letterSpacing: "-0.03em",
            }}
          >
            {marker}
          </span>
          <span
            className="text-[11px] font-semibold uppercase tracking-[0.32em]"
            style={{ color: p.accent }}
          >
            {eyebrowLabel}
          </span>
        </div>
        <h1
          className="max-w-[70%] text-left font-extrabold leading-[0.95] tracking-tight"
          style={{
            color: p.text,
            fontSize: "clamp(3rem, 6vw, 5.5rem)",
            letterSpacing: "-0.025em",
          }}
        >
          {slide.title}
        </h1>
        {slide.subtitle && (
          <p
            className="mt-8 max-w-md text-base leading-relaxed"
            style={{ color: p.muted }}
          >
            {slide.subtitle}
          </p>
        )}
      </div>
    </div>
  );
}

// ── Timeline slide — horizontal chronology (Phase 6AC, refactored 6AE) ──────
// Phase 6AE: composes Header (with eyebrow="Timeline") + TimelineSpine.

function TimelineSlide({ slide, p }) {
  return (
    <SlideFrame p={p} padding="md">
      <Header
        eyebrow="Timeline"
        title={slide.title}
        subtitle={slide.subtitle}
        p={p}
        size="md"
      />
      <div className="mt-12 flex-1">
        <TimelineSpine events={slide.events} p={p} />
      </div>
    </SlideFrame>
  );
}

// ── Comparison slide — explicit left/right framing (Phase 6AC, refactored 6AE) ─
// Phase 6AE: composes Header + ComparisonSide × 2 + ComparisonAxis.

function ComparisonSlide({ slide, p }) {
  return (
    <SlideFrame p={p} padding="md">
      <Header title={slide.title} subtitle={slide.subtitle} p={p} size="md" />
      <div className="relative mt-8 grid flex-1 grid-cols-[1fr_auto_1fr] gap-6">
        <ComparisonSidePrim block={slide.left} position="left" p={p} />
        <ComparisonAxis p={p} />
        <ComparisonSidePrim block={slide.right} position="right" p={p} />
      </div>
    </SlideFrame>
  );
}

// ── Chart slide ───────────────────────────────────────────────────────────────

function ChartSlide({ slide, p }) {
  const cd = slide.chart_data || {};
  const labels = Array.isArray(cd.labels) ? cd.labels : [];
  const values = Array.isArray(cd.values) ? cd.values.map((v) => Number(v) || 0) : [];
  const unit = cd.unit || "";
  const source = cd.source || "";
  const chartType = (slide.chart_type || "bar").toLowerCase();
  const light = isLight(p.bg);
  // Phase 6AL-Visuals: editorial chart reduction.
  // Pre-6AL the chart had a visible grid, accent borders, point markers,
  // and an 80%-opacity fill — the "dashboard" look. We now drop the grid,
  // hide point markers on lines, thin the line, and use a soft single
  // fill so the chart reads as an editorial figure, not a Tableau tile.
  const tickColor = p.muted;

  const dataset = {
    labels,
    datasets: [{
      label: unit ? `Value (${unit})` : "Value",
      data: values,
      backgroundColor: chartType === "doughnut"
        ? (p.chartPalette || [p.accent]).slice(0, labels.length || 1)
        : chartType === "line"
          ? (light ? `${p.accent}22` : `${p.accent}33`)
          : p.accent,
      borderColor: p.accent,
      borderWidth: chartType === "line" ? 2 : 0,
      fill: chartType === "line",
      tension: 0.4,
      pointRadius: 0,
      pointHoverRadius: 5,
      pointBackgroundColor: p.accent,
      borderRadius: chartType === "bar" ? 4 : 0,
      maxBarThickness: 56,
    }],
  };

  const axisCommon = {
    grid: { display: false, drawBorder: false },
    border: { display: false },
    ticks: { color: tickColor, font: { size: 12, family: "Inter, system-ui, sans-serif" } },
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: (ctx) => `${ctx.parsed.y ?? ctx.parsed} ${unit}`.trim() } },
    },
    scales: chartType === "doughnut" ? {} : {
      x: axisCommon,
      y: { ...axisCommon, beginAtZero: true },
    },
  };

  const ChartComp = chartType === "line" ? Line : chartType === "doughnut" ? Doughnut : Bar;

  return (
    <div className="flex h-full flex-col px-14 py-10" style={{ color: p.text }}>
      <h2
        className="mb-2 font-bold leading-[0.95]"
        style={{ fontSize: "clamp(2.25rem, 4vw, 3.5rem)", letterSpacing: "-0.025em" }}
      >
        {slide.title}
      </h2>
      {slide.subtitle && <p className="mb-4 text-sm" style={{ color: p.muted }}>{slide.subtitle}</p>}
      <div className="relative flex-1">
        {labels.length && values.length ? (
          <ChartComp data={dataset} options={options} />
        ) : (
          <div className="flex h-full items-center justify-center text-sm" style={{ color: p.muted }}>No chart data</div>
        )}
      </div>
      {(unit || source) && (
        <div className="mt-3 flex items-center justify-between text-xs" style={{ color: p.muted }}>
          <span>{unit ? `Units: ${unit}` : ""}</span>
          {source && <span>Source: {source}</span>}
        </div>
      )}
    </div>
  );
}

// ── Closing slide — 2 variants ────────────────────────────────────────────────

function ClosingSlide({ slide, p }) {
  const v = variantOf(slide.id, 2);
  if (v === 1) return <ClosingMinimal slide={slide} p={p} />;
  return <ClosingCard slide={slide} p={p} />;
}

function ClosingCard({ slide, p }) {
  // Phase 6AL-Visuals follow-up: the rounded "card on tinted background"
  // was the closing-slide equivalent of the bad title cover. We now
  // render full-bleed: image (now actually visible via the fixed
  // HeroFull), title flush bottom-left at editorial scale, CTA as a
  // typographic accent rather than a button-shaped chip.
  const hasImg = !!slide.image_url;
  return (
    <div className="relative h-full overflow-hidden" style={{ color: p.text, background: p.bg }}>
      <HeroFull src={slide.image_url} />
      <div className="relative flex h-full flex-col justify-end px-16 pb-14 pt-12">
        <h2
          className="max-w-[78%] font-extrabold leading-[0.95]"
          style={{
            color: hasImg ? "#FFFFFF" : p.text,
            fontSize: "clamp(2.75rem, 5.5vw, 5rem)",
            letterSpacing: "-0.025em",
          }}
        >
          {slide.title}
        </h2>
        {slide.subtitle && (
          <p
            className="mt-5 max-w-xl text-lg leading-relaxed"
            style={{ color: hasImg ? "rgba(255,255,255,0.78)" : p.muted }}
          >
            {slide.subtitle}
          </p>
        )}
        {slide.cta && (
          <div className="mt-8 flex items-center gap-3">
            <div
              className="h-px w-12"
              style={{ background: hasImg ? "rgba(255,255,255,0.6)" : p.accent }}
            />
            <span
              className="text-sm font-semibold uppercase tracking-[0.28em]"
              style={{ color: hasImg ? "#FFFFFF" : p.accent }}
            >
              {slide.cta}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

function ClosingMinimal({ slide, p }) {
  return (
    <div className="relative flex h-full flex-col justify-between px-14 py-14" style={{ color: p.text }}>
      <div className="h-px w-12" style={{ background: p.accent }} />
      <div>
        <h2 className="text-5xl font-extrabold leading-tight md:text-6xl">{slide.title}</h2>
        {slide.subtitle && (
          <p className="mt-5 max-w-lg text-lg" style={{ color: p.muted }}>{slide.subtitle}</p>
        )}
        {slide.cta && (
          <div className="mt-10 inline-flex items-center gap-2 text-base font-semibold" style={{ color: p.accent }}>
            {slide.cta} →
          </div>
        )}
      </div>
      <div className="h-px" style={{ background: p.accent + "30" }} />
    </div>
  );
}

// ── Layout registry ───────────────────────────────────────────────────────────

const layouts = {
  title: TitleSlide,
  bullets: BulletsSlide,
  "two-col": TwoColSlide,
  quote: QuoteSlide,
  stats: StatsSlide,
  chart: ChartSlide,
  closing: ClosingSlide,
  // Phase 6AA — additive layouts. Renderer dispatch falls back to
  // TitleSlide when a layout key is absent (see SlideRenderer below),
  // so old saved decks render unchanged.
  bigstat: BigStatSlide,
  section_divider: SectionDividerSlide,
  // Phase 6AC — semantic story primitives. Both gracefully degrade in
  // the exporter (timeline → bullets, comparison → two-col) and fall
  // back to TitleSlide in the renderer if the dispatch ever misses.
  timeline: TimelineSlide,
  comparison: ComparisonSlide,
};

export default function SlideRenderer({ slide, theme = "light-pro" }) {
  const p = paletteFor(theme);
  const Comp = layouts[slide?.layout] || TitleSlide;
  return (
    <motion.div
      key={slide?.id || slide?.title}
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
      className="relative aspect-video w-full overflow-hidden rounded-2xl border border-nexus-border shadow-2xl shadow-black/40"
      style={{ background: p.bg }}
    >
      <Comp slide={slide} p={p} />
    </motion.div>
  );
}
