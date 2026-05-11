import { useMemo, useState } from "react";

/**
 * SlideEditor — per-layout editable form for the deck workspace.
 *
 * Supported edits:
 *   title:    title, subtitle, eyebrow
 *   bullets:  title, bullets[]
 *   two-col:  title, columns[].heading/body (up to 2)
 *   quote:    quote, attribution
 *   stats:    title, stats[].label/value (up to 3)
 *   closing:  title, subtitle, cta
 *   chart:    title, subtitle (chart_data is preview-only)
 *
 * Unknown / unsupported layouts render a read-only notice and never throw.
 *
 * Pure controlled component: parent owns slide state. Calls `onChange(next)`
 * with the new slide object whenever a field is edited; keeps `slide.layout`,
 * `slide.id`, and any other unrelated fields (e.g. `image_url`, `sources`)
 * untouched so this stays compatible with the existing slide renderer.
 */
export default function SlideEditor({ slide, onChange }) {
  if (!slide) {
    return (
      <div className="text-sm text-nexus-muted">No slide selected.</div>
    );
  }

  const setField = (key, value) => onChange({ ...slide, [key]: value });

  const setBullet = (i, value) => {
    const next = [...(slide.bullets || [])];
    next[i] = value;
    onChange({ ...slide, bullets: next });
  };
  const addBullet = () =>
    onChange({ ...slide, bullets: [...(slide.bullets || []), ""] });
  const removeBullet = (i) => {
    const next = [...(slide.bullets || [])];
    next.splice(i, 1);
    onChange({ ...slide, bullets: next });
  };

  const setColumn = (i, key, value) => {
    const cols = [...(slide.columns || [])];
    while (cols.length <= i) cols.push({ heading: "", body: "" });
    cols[i] = { ...cols[i], [key]: value };
    onChange({ ...slide, columns: cols.slice(0, 2) });
  };

  const setStat = (i, key, value) => {
    const stats = [...(slide.stats || [])];
    while (stats.length <= i) stats.push({ value: "", label: "" });
    stats[i] = { ...stats[i], [key]: value };
    onChange({ ...slide, stats: stats.slice(0, 3) });
  };

  switch (slide.layout) {
    case "title":
      return (
        <div className="space-y-4">
          <Field label="Eyebrow">
            <Input
              value={slide.eyebrow || ""}
              onChange={(v) => setField("eyebrow", v)}
              placeholder="Optional kicker (e.g. Q3 Briefing)"
            />
          </Field>
          <Field label="Title">
            <TextArea
              value={slide.title || ""}
              onChange={(v) => setField("title", v)}
              rows={2}
            />
          </Field>
          <Field label="Subtitle">
            <TextArea
              value={slide.subtitle || ""}
              onChange={(v) => setField("subtitle", v)}
              rows={2}
            />
          </Field>
        </div>
      );

    case "bullets":
      return (
        <div className="space-y-4">
          <Field label="Title">
            <Input
              value={slide.title || ""}
              onChange={(v) => setField("title", v)}
            />
          </Field>
          <Field label="Bullets">
            <div className="space-y-2">
              {(slide.bullets || []).map((b, i) => (
                <div key={i} className="flex items-start gap-2">
                  <TextArea
                    value={b}
                    onChange={(v) => setBullet(i, v)}
                    rows={2}
                  />
                  <button
                    onClick={() => removeBullet(i)}
                    aria-label={`Remove bullet ${i + 1}`}
                    className="btn-ghost !px-2 !py-1 text-xs"
                  >
                    ✕
                  </button>
                </div>
              ))}
              <button
                onClick={addBullet}
                className="btn-ghost !px-3 !py-1 text-xs"
              >
                + Add bullet
              </button>
            </div>
          </Field>
        </div>
      );

    case "two-col": {
      const cols = slide.columns || [];
      return (
        <div className="space-y-4">
          <Field label="Title">
            <Input
              value={slide.title || ""}
              onChange={(v) => setField("title", v)}
            />
          </Field>
          {[0, 1].map((i) => (
            <div key={i} className="rounded-lg border border-nexus-border p-3">
              <div className="mb-2 text-[11px] uppercase tracking-widest text-nexus-dim">
                Column {i + 1}
              </div>
              <Field label="Heading">
                <Input
                  value={cols[i]?.heading || ""}
                  onChange={(v) => setColumn(i, "heading", v)}
                />
              </Field>
              <Field label="Body">
                <TextArea
                  value={cols[i]?.body || ""}
                  onChange={(v) => setColumn(i, "body", v)}
                  rows={3}
                />
              </Field>
            </div>
          ))}
        </div>
      );
    }

    case "quote":
      return (
        <div className="space-y-4">
          <Field label="Quote">
            <TextArea
              value={slide.quote || ""}
              onChange={(v) => setField("quote", v)}
              rows={4}
            />
          </Field>
          <Field label="Attribution">
            <Input
              value={slide.attribution || ""}
              onChange={(v) => setField("attribution", v)}
              placeholder="Speaker, source, or omit"
            />
          </Field>
        </div>
      );

    case "stats": {
      const stats = slide.stats || [];
      return (
        <div className="space-y-4">
          <Field label="Title">
            <Input
              value={slide.title || ""}
              onChange={(v) => setField("title", v)}
            />
          </Field>
          {[0, 1, 2].map((i) => (
            <div key={i} className="rounded-lg border border-nexus-border p-3">
              <div className="mb-2 text-[11px] uppercase tracking-widest text-nexus-dim">
                Stat {i + 1}
              </div>
              <Field label="Value">
                <Input
                  value={stats[i]?.value ?? ""}
                  onChange={(v) => setStat(i, "value", v)}
                  placeholder="42%"
                />
              </Field>
              <Field label="Label">
                <Input
                  value={stats[i]?.label || ""}
                  onChange={(v) => setStat(i, "label", v)}
                />
              </Field>
            </div>
          ))}
        </div>
      );
    }

    case "closing":
      return (
        <div className="space-y-4">
          <Field label="Title">
            <Input
              value={slide.title || ""}
              onChange={(v) => setField("title", v)}
            />
          </Field>
          <Field label="Subtitle">
            <TextArea
              value={slide.subtitle || ""}
              onChange={(v) => setField("subtitle", v)}
              rows={2}
            />
          </Field>
          <Field label="Call to action">
            <Input
              value={slide.cta || ""}
              onChange={(v) => setField("cta", v)}
              placeholder="Optional"
            />
          </Field>
        </div>
      );

    case "chart":
      return (
        <div className="space-y-4">
          <Field label="Title">
            <Input
              value={slide.title || ""}
              onChange={(v) => setField("title", v)}
            />
          </Field>
          <Field label="Subtitle">
            <TextArea
              value={slide.subtitle || ""}
              onChange={(v) => setField("subtitle", v)}
              rows={2}
            />
          </Field>
          <p className="text-xs text-nexus-muted">
            Chart data is preview-only in this workspace. Edit titles and
            subtitles here; regenerate the deck to change the chart values.
          </p>
        </div>
      );

    default:
      return (
        <div className="rounded-lg border border-nexus-border p-3 text-sm text-nexus-muted">
          Layout <code>{String(slide.layout)}</code> is preview-only.
        </div>
      );
  }
}

// ── tiny presentational helpers (kept inline to avoid a new component file) ─

function Field({ label, children }) {
  return (
    <label className="block">
      <span className="mb-1 block text-[11px] uppercase tracking-widest text-nexus-dim">
        {label}
      </span>
      {children}
    </label>
  );
}

function Input({ value, onChange, placeholder = "" }) {
  return (
    <input
      type="text"
      value={value}
      placeholder={placeholder}
      onChange={(e) => onChange(e.target.value)}
      className="w-full rounded-md border border-nexus-border bg-nexus-card px-3 py-2 text-sm text-nexus-text placeholder:text-nexus-dim focus:border-accent-purple focus:outline-none"
    />
  );
}

function TextArea({ value, onChange, rows = 2, placeholder = "" }) {
  return (
    <textarea
      value={value}
      placeholder={placeholder}
      rows={rows}
      onChange={(e) => onChange(e.target.value)}
      className="w-full resize-y rounded-md border border-nexus-border bg-nexus-card px-3 py-2 text-sm text-nexus-text placeholder:text-nexus-dim focus:border-accent-purple focus:outline-none"
    />
  );
}
