import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import toast from "react-hot-toast";
import { ArrowRight, Loader2, Globe, Sparkles } from "lucide-react";
import { useGenerate } from "../hooks/useGenerate.js";

// "auto" is a Phase 6M sentinel — the backend infers a topic-fitting theme
// (e.g. "Dossier" for war/conflict prompts, "light-pro" for business pitches)
// when the form submits with this value. Listed first so it is the default
// for new visitors who haven't picked a template yet.
const THEMES = [
  "auto",
  "light-pro",
  "Editorial",
  "Pixel",
  "Vellum",
  "Dossier",
  "Whiteboard",
  "Sketch",
  "Glamour",
  "Amber",
  "Arctic",
  "Cerulean",
  "Cobalt",
  "Emerald",
  "Basalt",
  "Mist",
  "Onyx",
  "Sand",
  "Neon",
  "Linen",
];

const DEFAULT_MODE = {
  id: "slides",
  label: "Slides",
  status: "live",
  cta: "Generate deck",
  placeholder:
    "e.g., Create a 10-slide minimalist product launch deck for an AI note-taking app.",
};

export default function PromptInput({ seed = "", mode = DEFAULT_MODE }) {
  const [topic, setTopic] = useState("");
  const [slideCount, setSlideCount] = useState(8);
  const [theme, setTheme] = useState(() => {
    // Phase 6M-Fix: existing browsers may have ``nexus.preferred-theme``
    // set to ``light-pro`` or ``Editorial`` from the pre-6M era, when
    // those values were the form default rather than a deliberate user
    // choice. Treat both as "no choice yet" and migrate them to the new
    // ``auto`` sentinel so topic-aware inference kicks in. Any other
    // stored value (Pixel, Vellum, Dossier, Whiteboard, …) is a real
    // user preference and is kept as-is.
    const LEGACY_DEFAULTS = ["light-pro", "Editorial"];
    try {
      const stored = window.localStorage.getItem("nexus.preferred-theme");
      if (!stored) return "auto";
      if (LEGACY_DEFAULTS.includes(stored)) {
        try {
          window.localStorage.setItem("nexus.preferred-theme", "auto");
        } catch {
          /* ignore */
        }
        return "auto";
      }
      return stored;
    } catch {
      return "auto";
    }
  });
  const [searchWeb, setSearchWeb] = useState(true);
  const { generate, loading } = useGenerate();
  const navigate = useNavigate();
  const isSlidesMode = mode.id === "slides";
  const isResearchMode = mode.id === "research";

  // When a quick-action chip is clicked, populate the textarea.
  useEffect(() => {
    if (seed) setTopic(seed);
  }, [seed]);

  useEffect(() => {
    const onPick = (e) => {
      const next = e?.detail;
      if (next && THEMES.includes(next)) setTheme(next);
    };
    window.addEventListener("nexus:theme-pick", onPick);
    return () => window.removeEventListener("nexus:theme-pick", onPick);
  }, []);

  // When the user changes the theme via the dropdown inside this form,
  // persist + broadcast so the template gallery card updates too.
  const onThemeChange = (next) => {
    setTheme(next);
    try {
      window.localStorage.setItem("nexus.preferred-theme", next);
    } catch {
      /* ignore */
    }
    window.dispatchEvent(new CustomEvent("nexus:theme-pick", { detail: next }));
  };

  const scrollToTemplates = () => {
    document.querySelector("#templates")?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const queueWaitlist = (modeId, t) => {
    try {
      const key = "nexus.waitlist";
      const list = JSON.parse(window.localStorage.getItem(key) || "[]");
      list.push({ mode: modeId, prompt: t, at: new Date().toISOString() });
      window.localStorage.setItem(key, JSON.stringify(list.slice(-50)));
    } catch {
      /* ignore */
    }
  };

  const onSubmit = async (e) => {
    e.preventDefault();
    const t = topic.trim();
    if (t.length < 4) {
      toast.error("Please describe your task in a bit more detail.");
      return;
    }

    // Slides + Research are wired to the live deck pipeline (Research is
    // simply a slides run with web-search forced on and a citation-heavy
    // theme bias). Other modes capture intent into the early-access queue.
    if (isSlidesMode || isResearchMode) {
      try {
        const { task_id } = await generate({
          topic: t,
          slide_count: slideCount,
          theme,
          search_web: isResearchMode ? true : searchWeb,
        });
        navigate(`/generate/${task_id}`, { state: { topic: t, theme, slideCount, mode: mode.id } });
      } catch (err) {
        toast.error(err?.response?.data?.detail || "Failed to start generation.");
      }
      return;
    }

    // Beta / Coming-soon modes: capture intent locally so the user feels
    // heard, and surface a clear status badge.
    queueWaitlist(mode.id, t);
    const niceLabel = mode.label.toLowerCase();
    toast.success(
      mode.status === "beta"
        ? `Queued for the ${niceLabel} beta \u2014 you\u2019ll be notified when it opens.`
        : `Saved \u2014 we\u2019ll ping you when ${niceLabel} mode ships.`,
    );
    setTopic("");
  };

  return (
    <form onSubmit={onSubmit} className="mx-auto max-w-3xl">
      {/* Active template pill (only meaningful for slides) */}
      {isSlidesMode && (
        <div className="mb-3 flex items-center justify-center">
          <button
            type="button"
            onClick={scrollToTemplates}
            className="group inline-flex items-center gap-2 rounded-full border border-accent-purple/40 bg-accent-purple/10 px-3 py-1 text-xs text-accent-purple transition hover:bg-accent-purple/20"
          >
            <Sparkles className="h-3 w-3" />
            <span>Template:</span>
            <span className="font-semibold">
              {theme === "auto" ? "auto · pick from topic" : theme}
            </span>
            <span className="ml-1 text-[10px] text-accent-purple/70 group-hover:text-accent-purple">
              change ↓
            </span>
          </button>
        </div>
      )}

      <div className="card overflow-hidden p-2 shadow-2xl shadow-black/40">
        <textarea
          value={topic}
          onChange={(e) => setTopic(e.target.value)}
          placeholder={mode.placeholder}
          rows={3}
          className="w-full resize-none bg-transparent px-4 py-3 text-base text-nexus-text placeholder-nexus-dim outline-none"
        />

        <div className="flex flex-wrap items-center gap-2 border-t border-nexus-border/60 px-3 py-3">
          {isSlidesMode && (
            <>
              <select
                value={theme}
                onChange={(e) => onThemeChange(e.target.value)}
                className="rounded-lg border border-nexus-border bg-nexus-card px-3 py-1.5 text-xs text-nexus-muted outline-none hover:text-nexus-text"
              >
                {THEMES.map((t) => (
                  <option key={t} value={t}>
                    {t === "auto" ? "auto · pick from topic" : t}
                  </option>
                ))}
              </select>

              <select
                value={slideCount}
                onChange={(e) => setSlideCount(Number(e.target.value))}
                className="rounded-lg border border-nexus-border bg-nexus-card px-3 py-1.5 text-xs text-nexus-muted outline-none hover:text-nexus-text"
              >
                {[4, 6, 8, 10, 12, 14, 16].map((n) => (
                  <option key={n} value={n}>
                    {n} slides
                  </option>
                ))}
              </select>

              <button
                type="button"
                onClick={() => setSearchWeb((v) => !v)}
                className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs transition ${
                  searchWeb
                    ? "border-accent-purple/60 bg-accent-purple/10 text-accent-purple"
                    : "border-nexus-border bg-nexus-card text-nexus-muted hover:text-nexus-text"
                }`}
              >
                <Globe className="h-3.5 w-3.5" /> Web research
              </button>
            </>
          )}

          {isResearchMode && (
            <span className="inline-flex items-center gap-1.5 rounded-lg border border-accent-purple/60 bg-accent-purple/10 px-3 py-1.5 text-xs text-accent-purple">
              <Globe className="h-3.5 w-3.5" /> Web search on · cited
            </span>
          )}

          {!isSlidesMode && !isResearchMode && (
            <span className="inline-flex items-center gap-1.5 rounded-lg border border-nexus-border bg-nexus-card px-3 py-1.5 text-[11px] text-nexus-muted">
              {mode.status === "beta"
                ? "Beta · join the early-access queue"
                : "Coming soon · reserve your spot"}
            </span>
          )}

          <div className="ml-auto">
            <button
              type="submit"
              disabled={loading}
              className="btn-primary"
              aria-label={mode.cta}
            >
              {loading ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Starting…
                </>
              ) : (
                <>
                  {mode.cta}
                  <ArrowRight className="h-4 w-4" />
                </>
              )}
            </button>
          </div>
        </div>
      </div>

      <p className="mt-3 text-center text-xs text-nexus-dim">
        Tip: be specific about audience, tone, and goal for the best results.
      </p>
    </form>
  );
}
