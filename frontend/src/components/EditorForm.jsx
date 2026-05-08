import { useState } from "react";
import { Loader2, Sparkles, Plus, X } from "lucide-react";

const LAYOUTS = [
  "title",
  "section",
  "bullets",
  "two-col",
  "comparison",
  "kpi",
  "quote",
  "stats",
  "chart",
  "table",
  "timeline",
  "image-focus",
  "closing",
];

/**
 * Right rail: layout-aware editor form. Mutates the local `draft` state
 * via `onChange`; persistence happens in the parent (Editor.jsx).
 */
export default function EditorForm({
  slide,
  onChange,
  onRegenerate,
  regenerating,
}) {
  const [instruction, setInstruction] = useState("");

  if (!slide) {
    return (
      <aside className="card !p-4 text-sm text-nexus-muted">
        Select a slide to edit.
      </aside>
    );
  }

  function patch(updates) {
    onChange?.({ ...slide, ...updates });
  }

  return (
    <aside className="card max-h-[calc(100vh-9rem)] overflow-y-auto !p-4 space-y-4">
      {/* Common fields */}
      <Section title="Layout">
        <select
          value={slide.layout || "title"}
          onChange={(e) => patch({ layout: e.target.value })}
          className="input w-full !py-1.5 !text-sm"
        >
          {LAYOUTS.map((l) => (
            <option key={l} value={l}>
              {l}
            </option>
          ))}
        </select>
      </Section>

      <Section title="Title">
        <Input
          value={slide.title || ""}
          onChange={(v) => patch({ title: v })}
          placeholder="Slide title"
        />
      </Section>

      <Section title="Subtitle">
        <Input
          value={slide.subtitle || ""}
          onChange={(v) => patch({ subtitle: v })}
          placeholder="Optional subtitle"
        />
      </Section>

      <Section title="Eyebrow">
        <Input
          value={slide.eyebrow || ""}
          onChange={(v) => patch({ eyebrow: v })}
          placeholder="Small label above title"
        />
      </Section>

      {/* Layout-specific */}
      <LayoutFields slide={slide} patch={patch} />

      <Section title="Speaker notes">
        <Textarea
          value={slide.speaker_notes || ""}
          onChange={(v) => patch({ speaker_notes: v })}
          rows={3}
          placeholder="Notes shown only to the presenter"
        />
      </Section>

      <Section title="Image URL">
        <Input
          value={slide.image_url || ""}
          onChange={(v) => patch({ image_url: v })}
          placeholder="https://…"
        />
      </Section>

      {/* Regenerate */}
      <div className="border-t border-nexus-border pt-3">
        <div className="mb-2 text-[10px] uppercase tracking-widest text-nexus-dim">
          Regenerate with AI
        </div>
        <Textarea
          value={instruction}
          onChange={setInstruction}
          rows={2}
          placeholder="Optional: tell the model what to change"
        />
        <button
          onClick={() => onRegenerate?.(instruction)}
          disabled={regenerating}
          className="btn-ghost mt-2 inline-flex w-full items-center justify-center gap-1.5 !py-1.5 !text-xs"
        >
          {regenerating ? (
            <Loader2 className="h-3.5 w-3.5 animate-spin" />
          ) : (
            <Sparkles className="h-3.5 w-3.5" />
          )}
          Regenerate slide
        </button>
      </div>
    </aside>
  );
}

function LayoutFields({ slide, patch }) {
  const layout = slide.layout || "title";

  switch (layout) {
    case "title":
    case "section":
      return (
        <Section title="Tagline / Number">
          <Input
            value={slide.tagline || slide.section_number || ""}
            onChange={(v) =>
              patch(
                layout === "section"
                  ? { section_number: v }
                  : { tagline: v }
              )
            }
            placeholder={layout === "section" ? "01" : "Tagline"}
          />
        </Section>
      );

    case "bullets":
      return (
        <ListField
          title="Bullets"
          items={slide.bullets || []}
          max={4}
          onChange={(arr) => patch({ bullets: arr })}
        />
      );

    case "two-col": {
      const cols = slide.columns || [];
      return (
        <Section title="Columns">
          {[0, 1].map((i) => (
            <div key={i} className="mb-2 rounded-md border border-nexus-border p-2">
              <div className="mb-1 text-[10px] uppercase tracking-widest text-nexus-dim">
                Col {i + 1}
              </div>
              <Input
                value={cols[i]?.heading || ""}
                onChange={(v) => {
                  const next = [...cols];
                  next[i] = { ...next[i], heading: v };
                  patch({ columns: next });
                }}
                placeholder="Heading"
              />
              <Textarea
                value={cols[i]?.body || ""}
                onChange={(v) => {
                  const next = [...cols];
                  next[i] = { ...next[i], body: v };
                  patch({ columns: next });
                }}
                rows={3}
                placeholder="Body"
              />
            </div>
          ))}
        </Section>
      );
    }

    case "comparison": {
      const items = slide.items || [];
      return (
        <Section title="Comparison cards">
          {[0, 1].map((i) => (
            <div key={i} className="mb-2 rounded-md border border-nexus-border p-2 space-y-1.5">
              <div className="text-[10px] uppercase tracking-widest text-nexus-dim">
                Card {i + 1}
              </div>
              <Input
                value={items[i]?.heading || ""}
                onChange={(v) => {
                  const next = [...items];
                  next[i] = { ...next[i], heading: v };
                  patch({ items: next });
                }}
                placeholder="Heading"
              />
              <Input
                value={items[i]?.subtitle || ""}
                onChange={(v) => {
                  const next = [...items];
                  next[i] = { ...next[i], subtitle: v };
                  patch({ items: next });
                }}
                placeholder="Subtitle"
              />
              <ListField
                items={items[i]?.points || []}
                max={4}
                onChange={(arr) => {
                  const next = [...items];
                  next[i] = { ...next[i], points: arr };
                  patch({ items: next });
                }}
              />
            </div>
          ))}
        </Section>
      );
    }

    case "kpi": {
      const kpis = slide.kpis || [];
      const update = (i, k, v) => {
        const next = [...kpis];
        next[i] = { ...next[i], [k]: v };
        patch({ kpis: next });
      };
      return (
        <Section title="KPIs (max 4)">
          {kpis.map((k, i) => (
            <div key={i} className="mb-2 rounded-md border border-nexus-border p-2 space-y-1.5">
              <div className="flex items-center justify-between">
                <div className="text-[10px] uppercase tracking-widest text-nexus-dim">
                  KPI {i + 1}
                </div>
                <button
                  onClick={() => patch({ kpis: kpis.filter((_, j) => j !== i) })}
                  aria-label="Remove KPI"
                >
                  <X className="h-3.5 w-3.5 text-nexus-muted hover:text-red-400" />
                </button>
              </div>
              <Input value={k.value} onChange={(v) => update(i, "value", v)} placeholder="42%" />
              <Input value={k.label} onChange={(v) => update(i, "label", v)} placeholder="Label" />
              <Input value={k.sublabel} onChange={(v) => update(i, "sublabel", v)} placeholder="Sublabel" />
              <div className="flex gap-2">
                <Input value={k.delta} onChange={(v) => update(i, "delta", v)} placeholder="Δ +12%" />
                <select
                  value={k.direction || ""}
                  onChange={(e) => update(i, "direction", e.target.value)}
                  className="input !py-1.5 !text-sm"
                >
                  <option value="">—</option>
                  <option value="up">▲ up</option>
                  <option value="down">▼ down</option>
                </select>
              </div>
            </div>
          ))}
          {kpis.length < 4 && (
            <AddButton
              onClick={() =>
                patch({
                  kpis: [
                    ...kpis,
                    { value: "", label: "", sublabel: "", delta: "", direction: "" },
                  ],
                })
              }
              label="Add KPI"
            />
          )}
        </Section>
      );
    }

    case "quote":
      return (
        <>
          <Section title="Quote">
            <Textarea
              value={slide.quote || ""}
              onChange={(v) => patch({ quote: v })}
              rows={3}
              placeholder="The quote text"
            />
          </Section>
          <Section title="Attribution">
            <Input
              value={slide.attribution || ""}
              onChange={(v) => patch({ attribution: v })}
              placeholder="— Author"
            />
          </Section>
        </>
      );

    case "stats": {
      const stats = slide.stats || [];
      const update = (i, k, v) => {
        const next = [...stats];
        next[i] = { ...next[i], [k]: v };
        patch({ stats: next });
      };
      return (
        <Section title="Stats (max 3)">
          {stats.map((s, i) => (
            <div key={i} className="mb-2 rounded-md border border-nexus-border p-2 space-y-1.5">
              <div className="flex items-center justify-between">
                <div className="text-[10px] uppercase tracking-widest text-nexus-dim">
                  Stat {i + 1}
                </div>
                <button
                  onClick={() => patch({ stats: stats.filter((_, j) => j !== i) })}
                  aria-label="Remove stat"
                >
                  <X className="h-3.5 w-3.5 text-nexus-muted hover:text-red-400" />
                </button>
              </div>
              <Input value={s.value} onChange={(v) => update(i, "value", v)} placeholder="Value" />
              <Input value={s.label} onChange={(v) => update(i, "label", v)} placeholder="Label" />
              <Input value={s.trend || ""} onChange={(v) => update(i, "trend", v)} placeholder="Trend (optional)" />
            </div>
          ))}
          {stats.length < 3 && (
            <AddButton
              onClick={() => patch({ stats: [...stats, { value: "", label: "", trend: "" }] })}
              label="Add stat"
            />
          )}
        </Section>
      );
    }

    case "chart": {
      const cd = slide.chart_data || { labels: [], values: [] };
      const labels = cd.labels || [];
      const values = cd.values || [];
      return (
        <>
          <Section title="Chart type">
            <select
              value={slide.chart_type || "bar"}
              onChange={(e) => patch({ chart_type: e.target.value })}
              className="input w-full !py-1.5 !text-sm"
            >
              <option value="bar">bar</option>
              <option value="line">line</option>
              <option value="doughnut">doughnut</option>
            </select>
          </Section>
          <Section title="Labels (one per line)">
            <Textarea
              value={labels.join("\n")}
              onChange={(v) =>
                patch({
                  chart_data: { ...cd, labels: v.split("\n").map((s) => s.trim()).filter(Boolean) },
                })
              }
              rows={3}
            />
          </Section>
          <Section title="Values (one per line)">
            <Textarea
              value={values.join("\n")}
              onChange={(v) =>
                patch({
                  chart_data: {
                    ...cd,
                    values: v
                      .split("\n")
                      .map((s) => Number(String(s).replace(/[^0-9.\-]/g, "")) || 0),
                  },
                })
              }
              rows={3}
            />
          </Section>
          <Section title="Unit / Source">
            <Input
              value={cd.unit || ""}
              onChange={(v) => patch({ chart_data: { ...cd, unit: v } })}
              placeholder="Unit (e.g. %)"
            />
            <Input
              value={cd.source || ""}
              onChange={(v) => patch({ chart_data: { ...cd, source: v } })}
              placeholder="Source"
            />
          </Section>
        </>
      );
    }

    case "table": {
      const headers = slide.headers || [];
      const rows = slide.rows || [];
      return (
        <>
          <Section title="Headers (comma-separated)">
            <Input
              value={headers.join(", ")}
              onChange={(v) =>
                patch({ headers: v.split(",").map((s) => s.trim()).filter(Boolean) })
              }
            />
          </Section>
          <Section title="Rows (one row per line, comma-separated cells)">
            <Textarea
              value={rows.map((r) => r.join(", ")).join("\n")}
              onChange={(v) =>
                patch({
                  rows: v
                    .split("\n")
                    .map((line) => line.split(",").map((c) => c.trim()))
                    .filter((r) => r.length > 0 && r.some((c) => c)),
                })
              }
              rows={5}
            />
          </Section>
        </>
      );
    }

    case "timeline": {
      const events = slide.events || [];
      const update = (i, k, v) => {
        const next = [...events];
        next[i] = { ...next[i], [k]: v };
        patch({ events: next });
      };
      return (
        <Section title="Events (max 5)">
          {events.map((ev, i) => (
            <div key={i} className="mb-2 rounded-md border border-nexus-border p-2 space-y-1.5">
              <div className="flex items-center justify-between">
                <div className="text-[10px] uppercase tracking-widest text-nexus-dim">
                  Event {i + 1}
                </div>
                <button
                  onClick={() => patch({ events: events.filter((_, j) => j !== i) })}
                  aria-label="Remove event"
                >
                  <X className="h-3.5 w-3.5 text-nexus-muted hover:text-red-400" />
                </button>
              </div>
              <Input value={ev.year} onChange={(v) => update(i, "year", v)} placeholder="Year" />
              <Input value={ev.title} onChange={(v) => update(i, "title", v)} placeholder="Title" />
              <Input value={ev.desc} onChange={(v) => update(i, "desc", v)} placeholder="Description" />
            </div>
          ))}
          {events.length < 5 && (
            <AddButton
              onClick={() => patch({ events: [...events, { year: "", title: "", desc: "" }] })}
              label="Add event"
            />
          )}
        </Section>
      );
    }

    case "image-focus":
      return (
        <>
          <Section title="Caption">
            <Textarea
              value={slide.caption || ""}
              onChange={(v) => patch({ caption: v })}
              rows={2}
            />
          </Section>
          <Section title="Image prompt">
            <Textarea
              value={slide.image_prompt || ""}
              onChange={(v) => patch({ image_prompt: v })}
              rows={2}
            />
          </Section>
        </>
      );

    case "closing":
      return (
        <>
          <Section title="Message">
            <Textarea
              value={slide.message || ""}
              onChange={(v) => patch({ message: v })}
              rows={2}
            />
          </Section>
          <Section title="Tagline">
            <Input
              value={slide.tagline || ""}
              onChange={(v) => patch({ tagline: v })}
            />
          </Section>
          <Section title="Call-to-action">
            <Input value={slide.cta || ""} onChange={(v) => patch({ cta: v })} />
          </Section>
        </>
      );

    default:
      return null;
  }
}

/* ---------- tiny presentational helpers ---------- */

function Section({ title, children }) {
  return (
    <div>
      <div className="mb-1 text-[10px] uppercase tracking-widest text-nexus-dim">
        {title}
      </div>
      <div className="space-y-1.5">{children}</div>
    </div>
  );
}

function Input({ value, onChange, placeholder }) {
  return (
    <input
      type="text"
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value)}
      placeholder={placeholder}
      className="input w-full !py-1.5 !text-sm"
    />
  );
}

function Textarea({ value, onChange, rows = 3, placeholder }) {
  return (
    <textarea
      value={value ?? ""}
      onChange={(e) => onChange(e.target.value)}
      rows={rows}
      placeholder={placeholder}
      className="input w-full resize-y !py-1.5 !text-sm"
    />
  );
}

function ListField({ title, items = [], max = 6, onChange }) {
  return (
    <div className="space-y-1.5">
      {title && (
        <div className="text-[10px] uppercase tracking-widest text-nexus-dim">
          {title}
        </div>
      )}
      {items.map((it, i) => (
        <div key={i} className="flex items-center gap-1.5">
          <Input
            value={it}
            onChange={(v) => {
              const next = [...items];
              next[i] = v;
              onChange(next);
            }}
            placeholder={`Item ${i + 1}`}
          />
          <button
            onClick={() => onChange(items.filter((_, j) => j !== i))}
            aria-label="Remove"
          >
            <X className="h-3.5 w-3.5 text-nexus-muted hover:text-red-400" />
          </button>
        </div>
      ))}
      {items.length < max && (
        <AddButton onClick={() => onChange([...items, ""])} label="Add item" />
      )}
    </div>
  );
}

function AddButton({ onClick, label }) {
  return (
    <button
      onClick={onClick}
      className="inline-flex w-full items-center justify-center gap-1 rounded-md border border-dashed border-nexus-border px-2 py-1.5 text-[11px] text-nexus-muted hover:border-nexus-borderHi hover:text-nexus-text"
    >
      <Plus className="h-3 w-3" /> {label}
    </button>
  );
}
