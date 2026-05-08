import * as React from "react";
import type { Slide, SlideDeck } from "../types.js";

/**
 * Lightweight, dependency-free slide renderer. Designed to embed cleanly in
 * any React app — no Tailwind, no chart libs. Consumers can override styles
 * via the `className`, `style`, or `slideStyle` props.
 *
 * For a feature-complete renderer (charts, themes, animations) see the full
 * NEXUS frontend. This SDK component covers the most common layouts so a
 * deck embeds usefully out-of-the-box.
 */
export interface NexusSlideProps {
  slide: Slide;
  style?: React.CSSProperties;
  className?: string;
}

const baseStyle: React.CSSProperties = {
  position: "relative",
  width: "100%",
  aspectRatio: "16 / 9",
  background: "#ffffff",
  color: "#111827",
  borderRadius: 12,
  overflow: "hidden",
  boxShadow: "0 1px 2px rgba(0,0,0,0.04), 0 8px 24px rgba(0,0,0,0.06)",
  fontFamily:
    "system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', sans-serif",
};

const padStyle: React.CSSProperties = {
  position: "absolute",
  inset: 0,
  padding: "6% 7%",
  display: "flex",
  flexDirection: "column",
  gap: "1.25rem",
  boxSizing: "border-box",
};

const titleStyle: React.CSSProperties = {
  fontSize: "2.4rem",
  fontWeight: 700,
  lineHeight: 1.1,
  margin: 0,
};
const subtitleStyle: React.CSSProperties = {
  fontSize: "1.05rem",
  color: "#4b5563",
  margin: 0,
};
const eyebrowStyle: React.CSSProperties = {
  fontSize: "0.7rem",
  letterSpacing: "0.18em",
  textTransform: "uppercase",
  color: "#9ca3af",
};

export function NexusSlide({ slide, style, className }: NexusSlideProps) {
  return (
    <div className={className} style={{ ...baseStyle, ...style }}>
      <div style={padStyle}>{renderBody(slide)}</div>
    </div>
  );
}

function renderBody(s: Slide): React.ReactNode {
  const title = s.title ? <h2 style={titleStyle}>{s.title}</h2> : null;
  const subtitle = s.subtitle ? <p style={subtitleStyle}>{s.subtitle}</p> : null;
  const eyebrow = s.eyebrow ? <div style={eyebrowStyle}>{s.eyebrow}</div> : null;

  switch (s.layout) {
    case "title":
      return (
        <div style={{ margin: "auto", textAlign: "center" }}>
          {eyebrow}
          {title}
          {subtitle}
          {s.tagline ? (
            <p style={{ ...subtitleStyle, marginTop: "0.5rem" }}>{s.tagline}</p>
          ) : null}
        </div>
      );

    case "section":
      return (
        <div style={{ margin: "auto" }}>
          {s.section_number ? (
            <div
              style={{
                fontSize: "5rem",
                fontWeight: 700,
                lineHeight: 1,
                color: "#e5e7eb",
              }}
            >
              {s.section_number}
            </div>
          ) : null}
          {eyebrow}
          {title}
          {subtitle}
        </div>
      );

    case "bullets":
      return (
        <>
          {eyebrow}
          {title}
          {subtitle}
          <ul
            style={{
              margin: 0,
              paddingLeft: "1.2rem",
              fontSize: "1.05rem",
              lineHeight: 1.6,
            }}
          >
            {(s.bullets ?? []).map((b, i) => (
              <li key={i}>{b}</li>
            ))}
          </ul>
        </>
      );

    case "two-col":
      return (
        <>
          {eyebrow}
          {title}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "1.5rem", flex: 1 }}>
            {(s.columns ?? []).map((c, i) => (
              <div key={i}>
                {c.heading ? (
                  <h3 style={{ margin: 0, fontSize: "1.15rem", fontWeight: 600 }}>
                    {c.heading}
                  </h3>
                ) : null}
                {c.body ? (
                  <p style={{ marginTop: "0.5rem", color: "#4b5563", lineHeight: 1.55 }}>
                    {c.body}
                  </p>
                ) : null}
              </div>
            ))}
          </div>
        </>
      );

    case "comparison":
      return (
        <>
          {eyebrow}
          {title}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "1fr auto 1fr",
              alignItems: "stretch",
              gap: "1rem",
              flex: 1,
            }}
          >
            {(s.items ?? []).slice(0, 2).map((c, i) => (
              <React.Fragment key={i}>
                <div
                  style={{
                    border: "1px solid #e5e7eb",
                    borderRadius: 10,
                    padding: "1rem",
                  }}
                >
                  <h3 style={{ margin: 0, fontSize: "1.1rem", fontWeight: 600 }}>
                    {c.heading}
                  </h3>
                  {c.subtitle ? (
                    <div style={{ ...eyebrowStyle, marginTop: 4 }}>{c.subtitle}</div>
                  ) : null}
                  {(c.points ?? []).length > 0 ? (
                    <ul style={{ marginTop: "0.5rem", paddingLeft: "1.1rem", lineHeight: 1.55 }}>
                      {c.points!.map((p, j) => (
                        <li key={j}>{p}</li>
                      ))}
                    </ul>
                  ) : c.body ? (
                    <p style={{ marginTop: "0.5rem", color: "#4b5563" }}>{c.body}</p>
                  ) : null}
                </div>
                {i === 0 ? (
                  <div style={{ alignSelf: "center", fontWeight: 700, color: "#9ca3af" }}>
                    {s.title ? "vs" : ""}
                  </div>
                ) : null}
              </React.Fragment>
            ))}
          </div>
        </>
      );

    case "kpi":
      return (
        <>
          {eyebrow}
          {title}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: `repeat(${Math.max(1, Math.min(4, (s.kpis ?? []).length))}, 1fr)`,
              gap: "1rem",
              flex: 1,
            }}
          >
            {(s.kpis ?? []).map((k, i) => (
              <div
                key={i}
                style={{
                  border: "1px solid #e5e7eb",
                  borderRadius: 10,
                  padding: "1rem",
                  display: "flex",
                  flexDirection: "column",
                  justifyContent: "center",
                }}
              >
                <div style={{ fontSize: "2rem", fontWeight: 700 }}>{k.value}</div>
                {k.delta ? (
                  <div
                    style={{
                      color: k.direction === "down" ? "#dc2626" : "#16a34a",
                      fontSize: "0.85rem",
                    }}
                  >
                    {k.direction === "down" ? "▼" : "▲"} {k.delta}
                  </div>
                ) : null}
                {k.label ? (
                  <div style={{ marginTop: "0.4rem", fontWeight: 500 }}>{k.label}</div>
                ) : null}
                {k.sublabel ? (
                  <div style={{ fontSize: "0.8rem", color: "#6b7280" }}>{k.sublabel}</div>
                ) : null}
              </div>
            ))}
          </div>
        </>
      );

    case "quote":
      return (
        <div style={{ margin: "auto", textAlign: "center", maxWidth: "80%" }}>
          <div
            style={{
              fontSize: "1.6rem",
              fontStyle: "italic",
              lineHeight: 1.4,
              color: "#1f2937",
            }}
          >
            “{s.quote ?? s.title}”
          </div>
          {s.attribution ? (
            <div style={{ marginTop: "1rem", color: "#6b7280" }}>— {s.attribution}</div>
          ) : null}
        </div>
      );

    case "stats":
      return (
        <>
          {eyebrow}
          {title}
          <div style={{ display: "grid", gridTemplateColumns: "repeat(3, 1fr)", gap: "1rem", flex: 1 }}>
            {(s.stats ?? []).map((st, i) => (
              <div key={i} style={{ textAlign: "center", margin: "auto" }}>
                <div style={{ fontSize: "2.5rem", fontWeight: 700 }}>{String(st.value)}</div>
                {st.label ? (
                  <div style={{ color: "#6b7280", marginTop: "0.25rem" }}>{st.label}</div>
                ) : null}
              </div>
            ))}
          </div>
        </>
      );

    case "table":
      return (
        <>
          {eyebrow}
          {title}
          <div style={{ flex: 1, overflow: "auto" }}>
            <table style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
              <thead>
                <tr>
                  {(s.headers ?? []).map((h, i) => (
                    <th
                      key={i}
                      style={{
                        textAlign: "left",
                        borderBottom: "2px solid #e5e7eb",
                        padding: "0.5rem",
                        fontWeight: 600,
                      }}
                    >
                      {h}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {(s.rows ?? []).map((r, i) => (
                  <tr key={i}>
                    {r.map((c, j) => (
                      <td
                        key={j}
                        style={{
                          borderBottom: "1px solid #f3f4f6",
                          padding: "0.5rem",
                        }}
                      >
                        {c}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      );

    case "timeline":
      return (
        <>
          {eyebrow}
          {title}
          <ol style={{ listStyle: "none", margin: 0, padding: 0, flex: 1 }}>
            {(s.events ?? []).map((e, i) => (
              <li
                key={i}
                style={{ display: "flex", gap: "1rem", padding: "0.4rem 0" }}
              >
                <div
                  style={{
                    minWidth: 64,
                    fontWeight: 700,
                    color: "#2563eb",
                  }}
                >
                  {e.year}
                </div>
                <div>
                  <div style={{ fontWeight: 600 }}>{e.title}</div>
                  {e.desc ? (
                    <div style={{ color: "#6b7280", fontSize: "0.9rem" }}>{e.desc}</div>
                  ) : null}
                </div>
              </li>
            ))}
          </ol>
        </>
      );

    case "image-focus":
      return (
        <>
          {eyebrow}
          {title}
          {s.image_url ? (
            <img
              src={s.image_url}
              alt={s.image?.alt ?? s.title ?? ""}
              style={{ flex: 1, objectFit: "cover", width: "100%", borderRadius: 8 }}
            />
          ) : null}
          {s.caption ? (
            <p style={{ ...subtitleStyle, marginTop: "0.5rem" }}>{s.caption}</p>
          ) : null}
        </>
      );

    case "chart":
      return (
        <>
          {eyebrow}
          {title}
          {subtitle}
          <div
            style={{
              flex: 1,
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              color: "#9ca3af",
              border: "1px dashed #e5e7eb",
              borderRadius: 8,
            }}
          >
            {(s.chart_data?.labels?.length ?? 0) > 0
              ? `Chart: ${s.chart_type ?? "bar"} · ${s.chart_data?.labels?.length} points`
              : "No chart data"}
          </div>
        </>
      );

    case "closing":
    default:
      return (
        <div style={{ margin: "auto", textAlign: "center" }}>
          {eyebrow}
          {title}
          {s.message ? (
            <p style={{ ...subtitleStyle, marginTop: "0.5rem" }}>{s.message}</p>
          ) : (
            subtitle
          )}
          {s.cta ? (
            <p style={{ marginTop: "1rem", fontWeight: 600 }}>{s.cta}</p>
          ) : null}
        </div>
      );
  }
}

/**
 * Renders an entire deck as a vertical stack of slides. Pass `slides` from
 * `useNexusGenerate()` or `useNexusDeck()`.
 */
export interface NexusDeckProps {
  deck?: SlideDeck | null;
  slides?: Slide[];
  className?: string;
  style?: React.CSSProperties;
  slideStyle?: React.CSSProperties;
  gap?: number | string;
}

export function NexusDeck({ deck, slides, className, style, slideStyle, gap = "2rem" }: NexusDeckProps) {
  const list = slides ?? deck?.slides ?? [];
  return (
    <div
      className={className}
      style={{ display: "flex", flexDirection: "column", gap, ...style }}
    >
      {list.map((s, i) => (
        <NexusSlide key={s.slide_id ?? s.id ?? i} slide={s} style={slideStyle} />
      ))}
    </div>
  );
}
