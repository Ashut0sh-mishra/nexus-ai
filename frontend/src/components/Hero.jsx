import { useEffect, useState } from "react";
import PromptInput from "./PromptInput.jsx";
import { api } from "../utils/api.js";
import { Sparkles } from "lucide-react";
import { MODES, STATUS_BADGE } from "../config/modes.js";

export default function Hero() {
  const [label, setLabel] = useState("Researching active model…");
  const [seed, setSeed] = useState("");
  const [modeId, setModeId] = useState("slides");

  useEffect(() => {
    api
      .get("/health")
      .then(({ data }) => {
        if (data?.label) setLabel(data.label);
      })
      .catch(() => setLabel("Powered by NEXUS"));
  }, []);

  useEffect(() => {
    const onPick = (e) => {
      const id = e?.detail;
      if (id && MODES.some((m) => m.id === id)) {
        setModeId(id);
        setSeed("");
      }
    };
    window.addEventListener("nexus:mode-pick", onPick);
    return () => window.removeEventListener("nexus:mode-pick", onPick);
  }, []);

  const mode = MODES.find((m) => m.id === modeId) || MODES[0];

  const onPickMode = (id) => {
    setModeId(id);
    setSeed("");
  };

  return (
    <section className="relative overflow-hidden">
      <div className="pointer-events-none absolute inset-0 bg-radial-fade" aria-hidden />
      <div className="mx-auto max-w-5xl px-6 pt-24 pb-12 text-center">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-nexus-border bg-nexus-surface/60 px-3 py-1 text-xs text-nexus-muted">
          <span className="h-1.5 w-1.5 rounded-full bg-accent-teal animate-pulse-soft" />
          {label}
        </div>

        <h1 className="text-balance text-5xl font-semibold leading-[1.05] tracking-tight md:text-6xl lg:text-7xl">
          What can I do{" "}
          <span className="gradient-text">for you?</span>
        </h1>

        <p className="mx-auto mt-6 max-w-2xl text-pretty text-base text-nexus-muted md:text-lg">
          {mode.tagline}
        </p>

        {/* Mode tab strip — primary capability switcher */}
        <div className="mx-auto mt-8 inline-flex flex-wrap items-center justify-center gap-1.5 rounded-2xl border border-nexus-border bg-nexus-surface/70 p-1.5 backdrop-blur">
          {MODES.map((m) => {
            const active = m.id === modeId;
            const badge = STATUS_BADGE[m.status];
            const Icon = m.icon;
            return (
              <button
                key={m.id}
                type="button"
                onClick={() => onPickMode(m.id)}
                className={`relative inline-flex items-center gap-1.5 rounded-xl px-3.5 py-2 text-sm transition ${
                  active
                    ? "bg-nexus-card text-nexus-text shadow-sm"
                    : "text-nexus-muted hover:text-nexus-text"
                }`}
              >
                <Icon className="h-4 w-4" />
                {m.label}
                {m.status !== "live" && (
                  <span
                    className={`ml-1 rounded-md border px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wide ${badge.cls}`}
                  >
                    {badge.label}
                  </span>
                )}
              </button>
            );
          })}
        </div>

        <div id="prompt-anchor" className="mt-8 scroll-mt-24">
          <PromptInput seed={seed} mode={mode} />
        </div>

        {/* Per-mode example chips */}
        <div className="mx-auto mt-6 flex max-w-3xl flex-wrap items-center justify-center gap-2">
          {mode.chips.map((c) => (
            <button
              key={c.label}
              type="button"
              onClick={() => setSeed(c.prompt)}
              className="inline-flex items-center gap-1.5 rounded-full border border-nexus-border bg-nexus-surface px-3.5 py-1.5 text-xs text-nexus-muted transition hover:border-nexus-borderHi hover:bg-nexus-card hover:text-nexus-text"
            >
              {c.label}
            </button>
          ))}
          <button
            type="button"
            onClick={() =>
              document
                .querySelector("#capabilities")
                ?.scrollIntoView({ behavior: "smooth", block: "start" })
            }
            className="inline-flex items-center gap-1.5 rounded-full border border-nexus-border bg-nexus-surface px-3.5 py-1.5 text-xs text-nexus-muted transition hover:border-nexus-borderHi hover:bg-nexus-card hover:text-nexus-text"
          >
            <Sparkles className="h-3.5 w-3.5" />
            More
          </button>
        </div>
      </div>
    </section>
  );
}
