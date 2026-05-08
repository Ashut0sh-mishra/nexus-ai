import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "../utils/api.js";
import { normalizeSlides } from "../utils/slideParser.js";
import SlideCarousel from "../components/SlideCarousel.jsx";

export default function SharedSlide() {
  const { token } = useParams();
  const [slides, setSlides] = useState(null);
  const [theme, setTheme] = useState("light-pro");
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api
      .get(`/share/${token}`)
      .then((res) => {
        if (cancelled) return;
        setSlides(normalizeSlides(res.data?.slides || []));
        if (res.data?.theme) setTheme(res.data.theme);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err?.response?.data?.detail || "Link not found or expired.");
      });
    return () => {
      cancelled = true;
    };
  }, [token]);

  return (
    <div className="mx-auto max-w-5xl px-6 py-10">
      <div className="mb-6 flex items-center gap-3 text-xs uppercase tracking-widest text-nexus-muted">
        <span className="rounded-full border border-nexus-border bg-nexus-surface px-2 py-0.5">
          Public preview
        </span>
        <span className="font-mono normal-case tracking-normal">{token}</span>
      </div>

      {error && (
        <div className="card border-red-500/40 bg-red-500/10 p-6 text-sm text-red-300">
          {error}
        </div>
      )}

      {!error && slides === null && (
        <div className="card flex aspect-video items-center justify-center text-nexus-muted">
          Loading shared deck…
        </div>
      )}

      {!error && Array.isArray(slides) && slides.length > 0 && (
        <SlideCarousel slides={slides} initialTheme={theme} />
      )}
    </div>
  );
}
