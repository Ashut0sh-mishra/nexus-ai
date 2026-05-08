// design/UnsupportedLayoutSlide.jsx — explicit "this layout was not registered" fallback.
//
// Production rendering still degrades gracefully (you don't want a debug
// banner shown to a customer), but the editor + gallery + dev console get
// a loud, unmissable hint with everything needed to file a fix.
//
// Toggled by `import.meta.env.DEV` OR by passing `forceDebug={true}`.

import { Frame, Section, Card } from "./primitives.jsx";
import { Body, Caption, Mono } from "./typography.jsx";
import { LAYOUT_SCHEMAS, CANONICAL_LAYOUTS } from "./registry.js";

/** Cap the JSON preview so we don't render a 200-line blob in the editor. */
function safePreview(slide, max = 1200) {
  try {
    const txt = JSON.stringify(
      Object.fromEntries(
        Object.entries(slide || {}).filter(([k]) => !k.startsWith("_")),
      ),
      null,
      2,
    );
    return txt.length > max ? txt.slice(0, max) + "\n…" : txt;
  } catch {
    return String(slide);
  }
}

export default function UnsupportedLayoutSlide({ slide, p, requestedLayout }) {
  const requested = requestedLayout || slide?._layout_unsupported || slide?.layout || "(none)";
  const suggestions = closestNames(requested, 3);
  const schema = LAYOUT_SCHEMAS[slide?.layout];
  return (
    <Frame p={p}>
      <Section
        eyebrow="⚠ Unsupported layout"
        title={slide?.title || "Layout not registered"}
        subtitle={`Renderer received layout="${requested}" but no matching component exists in the canonical registry.`}
        p={p}
      />
      <Card variant="outlined" p={p} style={{ marginBottom: "1rem" }}>
        <Body p={p} style={{ fontWeight: 700, marginBottom: "0.5rem" }}>How to fix</Body>
        <ol style={{ paddingLeft: "1.25rem", display: "flex", flexDirection: "column", gap: "0.25rem" }}>
          <li><Caption p={p}>Add it to <code>frontend/src/design/layouts.registry.json</code> (also add a renderer in <code>SlideLayouts.jsx</code>),</Caption></li>
          <li><Caption p={p}>OR add an alias entry mapping <code>{requested}</code> → an existing canonical name.</Caption></li>
          <li><Caption p={p}>Run <code>npm run verify:layouts</code> to confirm backend/frontend parity.</Caption></li>
        </ol>
        {suggestions.length > 0 && (
          <Caption p={p} style={{ display: "block", marginTop: "0.75rem" }}>
            Did you mean: {suggestions.map((s, i) => (
              <span key={s}><code>{s}</code>{i < suggestions.length - 1 ? ", " : ""}</span>
            ))}?
          </Caption>
        )}
      </Card>
      {schema && (
        <Card variant="tinted" p={p} style={{ marginBottom: "1rem" }}>
          <Mono p={p} style={{ display: "block", marginBottom: "0.5rem" }}>Expected schema</Mono>
          <Caption p={p}>{schema.join(" · ")}</Caption>
        </Card>
      )}
      <Card variant="elevated" p={p}>
        <Mono p={p} style={{ display: "block", marginBottom: "0.5rem" }}>Slide payload</Mono>
        <pre
          style={{
            margin: 0,
            fontSize: "0.6875rem",
            lineHeight: 1.45,
            color: p?.muted,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            maxHeight: "12rem",
            overflow: "auto",
            fontFamily: "ui-monospace, SFMono-Regular, monospace",
          }}
        >
{safePreview(slide)}
        </pre>
      </Card>
    </Frame>
  );
}

// ─── Levenshtein-ish suggestion (no deps) ──────────────────────────────────
function closestNames(input, k = 3) {
  const target = String(input || "").toLowerCase();
  if (!target) return [];
  return CANONICAL_LAYOUTS
    .map((n) => ({ name: n, score: similarity(target, n) }))
    .sort((a, b) => b.score - a.score)
    .slice(0, k)
    .filter((x) => x.score > 0.35)
    .map((x) => x.name);
}
function similarity(a, b) {
  // Cheap bigram overlap — good enough for "kpi_grid" → "kpi".
  const A = bigrams(a), B = bigrams(b);
  if (!A.size || !B.size) return 0;
  let hit = 0;
  A.forEach((g) => { if (B.has(g)) hit++; });
  return (2 * hit) / (A.size + B.size);
}
function bigrams(str) {
  const s = " " + str + " ";
  const out = new Set();
  for (let i = 0; i < s.length - 1; i++) out.add(s.slice(i, i + 2));
  return out;
}
