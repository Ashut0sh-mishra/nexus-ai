import { useEffect, useState, useCallback } from "react";

const STORAGE_KEY = "nexus.ui-theme";
const EVENT = "nexus:ui-theme-change";

function applyTheme(mode) {
  const root = document.documentElement;
  if (mode === "light") {
    root.classList.add("light");
    root.classList.remove("dark");
  } else {
    root.classList.add("dark");
    root.classList.remove("light");
  }
}

export function useUITheme() {
  const [mode, setMode] = useState(() => {
    if (typeof window === "undefined") return "dark";
    return window.localStorage.getItem(STORAGE_KEY) || "dark";
  });

  useEffect(() => {
    applyTheme(mode);
    try {
      window.localStorage.setItem(STORAGE_KEY, mode);
      window.dispatchEvent(new CustomEvent(EVENT, { detail: mode }));
    } catch {
      /* ignore */
    }
  }, [mode]);

  // Sync across hook instances and tabs.
  useEffect(() => {
    const onCustom = (e) => {
      if (e?.detail && e.detail !== mode) setMode(e.detail);
    };
    const onStorage = (e) => {
      if (e.key === STORAGE_KEY && e.newValue && e.newValue !== mode) {
        setMode(e.newValue);
      }
    };
    window.addEventListener(EVENT, onCustom);
    window.addEventListener("storage", onStorage);
    return () => {
      window.removeEventListener(EVENT, onCustom);
      window.removeEventListener("storage", onStorage);
    };
  }, [mode]);

  const toggle = useCallback(() => {
    setMode((m) => (m === "dark" ? "light" : "dark"));
  }, []);

  return { mode, setMode, toggle };
}
