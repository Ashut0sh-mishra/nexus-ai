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

function isLight(bg = "") {
  return bg.startsWith("#FFF") || bg.startsWith("#FAF") || bg.startsWith("#F9F")
    || bg.startsWith("#EFF") || bg.startsWith("#F1F") || bg.startsWith("#FEF")
    || bg.includes("EFF6FF") || bg.includes("FAF7F") || bg.includes("F9F5");
}

// ── Hero image helpers ────────────────────────────────────────────────────────

function HeroFull({ src }) {
  if (!src) return null;
  return (
    <div className="pointer-events-none absolute inset-0">
      <img src={src} alt="" loading="lazy" className="h-full w-full object-cover opacity-40" />
      <div className="absolute inset-0" style={{ background: "linear-gradient(180deg,rgba(0,0,0,0.5) 0%,rgba(0,0,0,0.72) 100%)" }} />
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
  const v = variantOf(slide.id, 2);
  if (v === 1) return <TitleSlideCentered slide={slide} p={p} />;
  return <TitleSlideSplit slide={slide} p={p} />;
}

function TitleSlideSplit({ slide, p }) {
  const words = (slide.title || "").trim().split(/\s+/);
  const splitIdx = words.length > 1 ? Math.ceil(words.length / 2) : 1;
  const top = words.slice(0, splitIdx).join(" ");
  const bottom = words.slice(splitIdx).join(" ");
  return (
    <div className="relative grid h-full grid-cols-[58%_42%]" style={{ color: p.text }}>
      <div className="relative flex h-full flex-col justify-between px-14 py-12">
        <div className="text-xs uppercase tracking-[0.28em]" style={{ color: p.muted }}>
          {slide.eyebrow || ""}
        </div>
        <div>
          <h1 className="text-6xl font-extrabold uppercase leading-[0.95] tracking-tight md:text-7xl" style={{ color: p.text }}>
            {top}
          </h1>
          {bottom && (
            <h1 className="mt-1 text-6xl font-extrabold uppercase leading-[0.95] tracking-tight md:text-7xl" style={{ color: p.accent }}>
              {bottom}
            </h1>
          )}
          {slide.subtitle && (
            <p className="mt-6 max-w-md text-base leading-relaxed" style={{ color: p.muted }}>
              {slide.subtitle}
            </p>
          )}
        </div>
        <div />
      </div>
      <div className="relative h-full overflow-hidden" style={{ background: p.accent }}>
        {slide.image_url && (
          <img src={slide.image_url} alt="" loading="lazy"
            className="absolute inset-0 h-full w-full object-cover mix-blend-luminosity opacity-90" />
        )}
        <div className="absolute left-1/2 top-1/2 h-[55%] w-[55%] -translate-x-1/2 -translate-y-1/2 rounded-full"
          style={{
            background: `radial-gradient(circle at 35% 30%, rgba(255,255,255,0.5), rgba(255,255,255,0) 60%), ${p.accent}`,
            boxShadow: `0 0 80px 20px ${p.accent}70`,
            border: "2px solid rgba(255,255,255,0.3)",
          }} />
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 text-5xl font-black text-white/80">✦</div>
      </div>
    </div>
  );
}

function TitleSlideCentered({ slide, p }) {
  return (
    <div className="relative flex h-full flex-col items-center justify-center px-16 text-center" style={{ color: p.text }}>
      <HeroFull src={slide.image_url} />
      <div className="relative z-10 max-w-3xl">
        {slide.eyebrow && (
          <div className="mb-6 inline-block rounded-full border px-4 py-1.5 text-xs uppercase tracking-[0.22em]"
            style={{ borderColor: p.accent + "60", color: p.accent }}>
            {slide.eyebrow}
          </div>
        )}
        <h1 className="text-6xl font-extrabold leading-[1.0] tracking-tight md:text-7xl" style={{ color: slide.image_url ? "#fff" : p.text }}>
          {slide.title}
        </h1>
        {slide.subtitle && (
          <p className="mt-6 text-lg leading-relaxed" style={{ color: slide.image_url ? "rgba(255,255,255,0.75)" : p.muted }}>
            {slide.subtitle}
          </p>
        )}
        <div className="mt-10 h-px w-16 mx-auto" style={{ background: p.accent }} />
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
  const hasImg = !!slide.image_url;
  return (
    <div className="relative h-full" style={{ color: p.text }}>
      <HeroRight src={slide.image_url} p={p} />
      <div className={`relative flex h-full flex-col px-14 py-12 ${hasImg ? "pr-[44%]" : ""}`}>
        <h2 className="mb-8 text-3xl font-semibold md:text-4xl">{slide.title}</h2>
        <ul className="space-y-4">
          {(slide.bullets || []).map((b, i) => (
            <li key={i} className="flex items-start gap-3 text-lg">
              <span className="mt-[9px] inline-block h-2 w-2 shrink-0 rounded-full" style={{ background: p.accent }} />
              <span>{b}</span>
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
              <span className="text-lg leading-snug">{b}</span>
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
              <span className="py-2.5 text-lg leading-snug">{b}</span>
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
  const v = variantOf(slide.id, 2);
  if (v === 1) return <QuoteSide slide={slide} p={p} />;
  return <QuoteCentered slide={slide} p={p} />;
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
              {s.value}
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
            {hero.value}
          </div>
          <div className="mt-2 text-base uppercase tracking-widest" style={{ color: p.muted }}>{hero.label}</div>
          {rest.length > 0 && (
            <div className="mt-8 flex gap-10">
              {rest.map((s, i) => (
                <div key={i}>
                  <div className="text-3xl font-bold tabular-nums" style={{ color: p.text }}>{s.value}</div>
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

function BigStatSlide({ slide, p }) {
  const value = slide.value || (slide.stats && slide.stats[0] && slide.stats[0].value) || "";
  const label = slide.label || (slide.stats && slide.stats[0] && slide.stats[0].label) || "";
  const subtitle = slide.subtitle || "";
  return (
    <SlideFrame p={p}>
      {slide.title && <Eyebrow p={p}>{slide.title}</Eyebrow>}
      <div className="flex flex-1 flex-col">
        <HeroMetric value={value} label={label} subtitle={subtitle} p={p} size="lg" />
      </div>
    </SlideFrame>
  );
}

// ── Section Divider — typography pause (Phase 6AA, refactored 6AE) ─────────
// Phase 6AE: thin shell over SectionDividerBlock primitive.

function SectionDividerSlide({ slide, p }) {
  return (
    <SectionDividerBlock
      eyebrow={slide.eyebrow}
      title={slide.title}
      subtitle={slide.subtitle}
      p={p}
    />
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
  const gridColor = light ? "rgba(0,0,0,0.06)" : "rgba(255,255,255,0.08)";
  const tickColor = p.muted;

  const dataset = {
    labels,
    datasets: [{
      label: unit ? `Value (${unit})` : "Value",
      data: values,
      backgroundColor: chartType === "doughnut"
        ? (p.chartPalette || [p.accent]).slice(0, labels.length || 1)
        : `${p.accent}CC`,
      borderColor: p.accent,
      borderWidth: 2,
      fill: chartType === "line",
      tension: 0.35,
      pointRadius: 4,
      pointBackgroundColor: p.accent,
    }],
  };

  const options = {
    responsive: true,
    maintainAspectRatio: false,
    plugins: {
      legend: { display: false },
      tooltip: { callbacks: { label: (ctx) => `${ctx.parsed.y ?? ctx.parsed} ${unit}`.trim() } },
    },
    scales: chartType === "doughnut" ? {} : {
      x: { grid: { color: gridColor }, ticks: { color: tickColor, font: { size: 12 } } },
      y: { grid: { color: gridColor }, ticks: { color: tickColor, font: { size: 12 } }, beginAtZero: true },
    },
  };

  const ChartComp = chartType === "line" ? Line : chartType === "doughnut" ? Doughnut : Bar;

  return (
    <div className="flex h-full flex-col px-14 py-10" style={{ color: p.text }}>
      <h2 className="mb-2 text-3xl font-semibold md:text-4xl">{slide.title}</h2>
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
  return (
    <>
      <HeroFull src={slide.image_url} />
      <div className="relative flex h-full flex-col items-center justify-center px-16 text-center" style={{ color: p.text }}>
        <div className="rounded-3xl border bg-black/25 px-12 py-12 backdrop-blur-sm" style={{ borderColor: p.accent + "40" }}>
          <h2 className="text-4xl font-semibold md:text-5xl">{slide.title}</h2>
          {slide.subtitle && <p className="mt-5 max-w-xl text-lg" style={{ color: p.muted }}>{slide.subtitle}</p>}
          {slide.cta && (
            <div className="mt-8 inline-block rounded-xl px-6 py-3 text-base font-semibold"
              style={{ background: p.accent, color: isLight(p.bg) ? "#fff" : "#0A0A0F" }}>
              {slide.cta}
            </div>
          )}
        </div>
      </div>
    </>
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
