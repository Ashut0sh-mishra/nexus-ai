import { Link, NavLink } from "react-router-dom";
import { Sparkles, Moon, Sun } from "lucide-react";
import { useUITheme } from "../hooks/useUITheme.js";

export default function Navbar() {
  const { mode, toggle } = useUITheme();
  return (
    <header className="sticky top-0 z-40 border-b border-nexus-border/60 bg-nexus-bg/70 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
        <Link to="/" className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-nexus">
            <Sparkles className="h-4 w-4 text-white" />
          </div>
          <span className="text-lg font-semibold tracking-tight">NEXUS</span>
        </Link>

        <nav className="hidden items-center gap-7 text-sm text-nexus-muted md:flex">
          <NavLink to="/" className="hover:text-nexus-text transition">
            Home
          </NavLink>
          <a
            href="https://github.com"
            target="_blank"
            rel="noreferrer"
            className="hover:text-nexus-text transition"
          >
            Docs
          </a>
          <a href="#features" className="hover:text-nexus-text transition">
            Features
          </a>
          <a href="#templates" className="hover:text-nexus-text transition">
            Templates
          </a>
        </nav>

        <div className="flex items-center gap-3">
          <button
            type="button"
            onClick={toggle}
            aria-label={mode === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-nexus-border bg-nexus-surface text-nexus-muted transition hover:text-nexus-text hover:border-nexus-borderHi"
          >
            {mode === "dark" ? (
              <Sun className="h-4 w-4" />
            ) : (
              <Moon className="h-4 w-4" />
            )}
          </button>
          <button className="hidden text-sm text-nexus-muted hover:text-nexus-text md:inline">
            Sign in
          </button>
          <button className="btn-primary !py-2 !px-4 text-sm">Sign up</button>
        </div>
      </div>
    </header>
  );
}
