import { useEffect, useState } from "react";
import { Check } from "lucide-react";
import toast from "react-hot-toast";

const TEMPLATES = [
  { name: "Light Pro", theme: "light-pro", bg: "#FFFFFF", accent: "#F59E0B", text: "#111827", muted: "#6B7280" },
  { name: "Editorial", theme: "Editorial", bg: "#0E0E12", accent: "#E8C8A0", text: "#F5F5F7", muted: "#9A9AA5" },
  { name: "Pixel", theme: "Pixel", bg: "#0A0F1F", accent: "#7DD3FC", text: "#E0F2FE", muted: "#94A3B8" },
  { name: "Vellum", theme: "Vellum", bg: "#F8F4EC", accent: "#7C3F00", text: "#1F1B16", muted: "#6B5E4F" },
  { name: "Dossier", theme: "Dossier", bg: "#1B1410", accent: "#D4A45B", text: "#F4EFE7", muted: "#A89685" },
  { name: "Whiteboard", theme: "Whiteboard", bg: "#FAFAFA", accent: "#111111", text: "#0A0A0A", muted: "#666" },
  { name: "Sketch", theme: "Sketch", bg: "#FFFAEC", accent: "#E11D48", text: "#1F1F1F", muted: "#737373" },
  { name: "Glamour", theme: "Glamour", bg: "#0E0608", accent: "#F472B6", text: "#FFE4F1", muted: "#9CA3AF" },
  { name: "Amber", theme: "Amber", bg: "#FFFBEB", accent: "#D97706", text: "#1C1917", muted: "#78716C" },
  { name: "Arctic", theme: "Arctic", bg: "#F0F9FF", accent: "#0284C7", text: "#0C4A6E", muted: "#475569" },
  { name: "Cerulean", theme: "Cerulean", bg: "#082F49", accent: "#38BDF8", text: "#E0F2FE", muted: "#94A3B8" },
  { name: "Cobalt", theme: "Cobalt", bg: "#F8FAFC", accent: "#1E3A8A", text: "#0F172A", muted: "#475569" },
  { name: "Emerald", theme: "Emerald", bg: "#064E3B", accent: "#34D399", text: "#ECFDF5", muted: "#9CA3AF" },
  { name: "Basalt", theme: "Basalt", bg: "#1F2937", accent: "#FBBF24", text: "#F9FAFB", muted: "#9CA3AF" },
  { name: "Mist", theme: "Mist", bg: "#F1F5F9", accent: "#475569", text: "#0F172A", muted: "#64748B" },
  { name: "Onyx", theme: "Onyx", bg: "#0A0A0A", accent: "#F5F5F5", text: "#FAFAFA", muted: "#A3A3A3" },
  { name: "Sand", theme: "Sand", bg: "#F5F0E1", accent: "#B45309", text: "#3F2A14", muted: "#7C6A4F" },
  { name: "Neon", theme: "Neon", bg: "#0A0118", accent: "#22D3EE", text: "#F0ABFC", muted: "#A78BFA" },
  { name: "Linen", theme: "Linen", bg: "#FAF7F2", accent: "#1E3A8A", text: "#1F2937", muted: "#6B7280" },
];

function TemplateCard({ t, active, onPick }) {
  return (
    <button
      type="button"
      onClick={() => onPick(t.theme, t.name)}
      className={`group relative flex flex-col items-stretch overflow-hidden rounded-xl border text-left transition hover:-translate-y-0.5 hover:shadow-lg ${
        active
          ? "border-accent-purple ring-2 ring-accent-purple/60 shadow-lg"
          : "border-nexus-border hover:border-nexus-borderHi bg-nexus-surface"
      }`}
    >
      {active && (
        <div className="absolute right-2 top-2 z-10 flex h-6 w-6 items-center justify-center rounded-full bg-accent-purple text-white shadow-md">
          <Check className="h-3.5 w-3.5" strokeWidth={3} />
        </div>
      )}
      <div
        className="relative h-32 w-full overflow-hidden"
        style={{ background: t.bg, color: t.text }}
      >
        <div className="absolute inset-0 p-3 flex flex-col justify-between">
          <div
            className="text-[8px] uppercase tracking-[0.2em]"
            style={{ color: t.muted }}
          >
            {t.name}
          </div>
          <div>
            <div
              className="font-serif text-[15px] leading-tight font-semibold"
              style={{ color: t.text }}
            >
              The Future of {t.name}
            </div>
            <div
              className="mt-1 h-[2px] w-8 rounded"
              style={{ background: t.accent }}
            />
            <div className="mt-1 text-[7px]" style={{ color: t.muted }}>
              A study by NEXUS · 2026
            </div>
          </div>
          {!active && (
            <div
              className="absolute right-2 top-2 h-2 w-2 rounded-full"
              style={{ background: t.accent }}
            />
          )}
        </div>
      </div>
      <div
        className={`px-3 py-2 text-xs transition ${
          active
            ? "bg-accent-purple/10 text-accent-purple font-medium"
            : "bg-nexus-surface text-nexus-muted group-hover:text-nexus-text"
        }`}
      >
        {active ? `✓ ${t.name} selected` : t.name}
      </div>
    </button>
  );
}

export default function Templates() {
  const [active, setActive] = useState(() => {
    try {
      return window.localStorage.getItem("nexus.preferred-theme") || "light-pro";
    } catch {
      return "light-pro";
    }
  });

  // Listen for theme changes coming from PromptInput dropdown so card stays in sync.
  useEffect(() => {
    const onPick = (e) => {
      if (e?.detail) setActive(e.detail);
    };
    window.addEventListener("nexus:theme-pick", onPick);
    return () => window.removeEventListener("nexus:theme-pick", onPick);
  }, []);

  const onPick = (theme, displayName) => {
    setActive(theme);
    try {
      window.localStorage.setItem("nexus.preferred-theme", theme);
    } catch {
      /* ignore */
    }
    window.dispatchEvent(new CustomEvent("nexus:theme-pick", { detail: theme }));
    toast.success(`Template applied: ${displayName}`, { duration: 1800 });
    document
      .querySelector("#prompt-anchor")
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  return (
    <section id="templates" className="mx-auto max-w-6xl px-6 py-16">
      <div className="mb-8 flex items-end justify-between gap-4">
        <div>
          <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">
            Choose a <span className="gradient-text">template</span>
          </h2>
          <p className="mt-2 text-sm text-nexus-muted">
            Click any template to apply it instantly — then describe your
            topic. Every template renders in both PPTX and PDF exports.
          </p>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
        {TEMPLATES.map((t) => (
          <TemplateCard
            key={t.theme}
            t={t}
            active={active === t.theme}
            onPick={onPick}
          />
        ))}
      </div>
    </section>
  );
}
