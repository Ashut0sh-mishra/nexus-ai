import { CheckCircle2, Clock, ArrowRight } from "lucide-react";
import { MODES, STATUS_BADGE } from "../config/modes.js";

const ICONS = {
  live: CheckCircle2,
  beta: Clock,
  soon: Clock,
};

export default function Capabilities() {
  const onPick = (id) => {
    document
      .querySelector("#prompt-anchor")
      ?.scrollIntoView({ behavior: "smooth", block: "start" });
    window.dispatchEvent(new CustomEvent("nexus:mode-pick", { detail: id }));
  };

  return (
    <section
      id="capabilities"
      className="mx-auto max-w-7xl px-6 pt-4 pb-20"
    >
      <div className="mb-10 text-center">
        <h2 className="text-3xl font-semibold tracking-tight md:text-4xl">
          One agent, every <span className="gradient-text">deliverable</span>.
        </h2>
        <p className="mx-auto mt-3 max-w-2xl text-sm text-nexus-muted md:text-base">
          NEXUS isn&rsquo;t just slides. The same research-and-plan engine ships
          decks today, with websites, desktop apps, and full design kits rolling
          out across 2026.
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        {MODES.map((m) => {
          const Icon = m.icon;
          const StatusIcon = ICONS[m.status];
          const badge = STATUS_BADGE[m.status];
          return (
            <button
              key={m.id}
              type="button"
              onClick={() => onPick(m.id)}
              className="card group flex flex-col items-start p-6 text-left transition hover:border-nexus-borderHi hover:shadow-lg hover:shadow-black/20"
            >
              <div className="mb-4 flex w-full items-center justify-between">
                <div className="flex h-11 w-11 items-center justify-center rounded-xl bg-nexus-card group-hover:bg-gradient-nexus transition">
                  <Icon className="h-5 w-5 text-nexus-text group-hover:text-nexus-bg transition" />
                </div>
                <span
                  className={`inline-flex items-center gap-1 rounded-md border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${badge.cls}`}
                >
                  <StatusIcon className="h-3 w-3" />
                  {badge.label}
                </span>
              </div>
              <h3 className="mb-1.5 text-lg font-semibold tracking-tight">
                {m.label}
              </h3>
              <p className="text-sm leading-relaxed text-nexus-muted">
                {m.tagline}
              </p>
              <span className="mt-4 inline-flex items-center gap-1 text-xs text-nexus-muted transition group-hover:text-accent-purple">
                {m.status === "live" ? "Try it now" : "Reserve early access"}
                <ArrowRight className="h-3.5 w-3.5 transition group-hover:translate-x-0.5" />
              </span>
            </button>
          );
        })}
      </div>
    </section>
  );
}
