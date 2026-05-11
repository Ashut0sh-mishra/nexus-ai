import { Sparkles, Github, Twitter } from "lucide-react";

const COLUMNS = [
  {
    heading: "Product",
    links: [
      { label: "AI slides", href: "#templates" },
      { label: "AI design", href: "#templates" },
      { label: "Live research", href: "#features" },
      { label: "Pricing", href: "#pricing" },
      { label: "Changelog", href: "#features" },
    ],
  },
  {
    heading: "Resources",
    links: [
      { label: "Docs", href: "#features" },
      { label: "Blog", href: "#features" },
      { label: "Help center", href: "#features" },
      { label: "API", href: "#features" },
      { label: "Playbook", href: "#features" },
    ],
  },
  {
    heading: "Compare",
    links: [
      { label: "vs ChatGPT", href: "#features" },
      { label: "vs Manus", href: "#features" },
      { label: "vs Gamma", href: "#features" },
      { label: "vs Beautiful.ai", href: "#features" },
    ],
  },
  {
    heading: "Download",
    links: [
      { label: "Web app", href: "/" },
      { label: "Desktop", href: "#features" },
      { label: "Mobile", href: "#features" },
      { label: "VS Code", href: "#features" },
    ],
  },
  {
    heading: "Company",
    links: [
      { label: "About", href: "#features" },
      { label: "Careers", href: "#features" },
      { label: "Privacy", href: "#features" },
      { label: "Terms", href: "#features" },
      { label: "Contact", href: "mailto:hello@nexus.ai" },
    ],
  },
];

export default function Footer() {
  return (
    <footer className="border-t border-nexus-border/60 bg-nexus-surface/30">
      <div className="mx-auto max-w-7xl px-6 py-14">
        <div className="grid gap-10 md:grid-cols-[1.4fr,repeat(5,1fr)]">
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-gradient-nexus">
                <Sparkles className="h-4 w-4 text-white" />
              </div>
              <span className="text-lg font-semibold tracking-tight">NEXUS</span>
            </div>
            <p className="font-serif italic text-lg text-nexus-text leading-snug">
              Less structure,
              <br />
              more intelligence.
            </p>
            <div className="flex items-center gap-3 pt-2">
              <a
                href="https://github.com"
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-nexus-border bg-nexus-surface text-nexus-muted transition hover:text-nexus-text"
                aria-label="GitHub"
              >
                <Github className="h-4 w-4" />
              </a>
              <a
                href="https://twitter.com"
                target="_blank"
                rel="noreferrer"
                className="inline-flex h-8 w-8 items-center justify-center rounded-lg border border-nexus-border bg-nexus-surface text-nexus-muted transition hover:text-nexus-text"
                aria-label="Twitter"
              >
                <Twitter className="h-4 w-4" />
              </a>
            </div>
          </div>

          {COLUMNS.map((col) => (
            <div key={col.heading}>
              <h4 className="mb-3 text-sm font-semibold text-nexus-text">
                {col.heading}
              </h4>
              <ul className="space-y-2 text-sm text-nexus-muted">
                {col.links.map((l) => (
                  <li key={l.label}>
                    <a
                      href={l.href}
                      className="transition hover:text-nexus-text"
                    >
                      {l.label}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 flex flex-col items-start justify-between gap-3 border-t border-nexus-border/60 pt-6 text-xs text-nexus-dim md:flex-row md:items-center">
          <span>
            © {new Date().getFullYear()} NEXUS · Less structure, more
            intelligence.
          </span>
          <span className="font-mono">v1.0 · prototype</span>
        </div>
      </div>
    </footer>
  );
}
