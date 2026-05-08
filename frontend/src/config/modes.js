// Central registry of NEXUS capability "modes" (Manus-style).
// Slides is fully wired; other modes are roadmap items that capture intent.
import {
  Presentation,
  Globe,
  Monitor,
  Palette,
  Search,
} from "lucide-react";

export const MODES = [
  {
    id: "slides",
    label: "Slides",
    icon: Presentation,
    status: "live",
    tagline: "Research, design, and ship a deck in minutes.",
    placeholder:
      "e.g., Create a 10-slide minimalist product launch deck for an AI note-taking app.",
    cta: "Generate deck",
    chips: [
      { label: "Investor pitch", prompt: "Create a 10-slide investor pitch deck for an early-stage AI startup, with problem, solution, market, traction, team, and ask." },
      { label: "Product launch", prompt: "Create a product-launch deck announcing a new mobile app, with positioning, features, GTM plan, and a 6-month roadmap." },
      { label: "Market analysis", prompt: "Create a 12-slide market analysis on the global electric vehicle industry, with TAM/SAM/SOM, competitor landscape, and outlook." },
      { label: "Education", prompt: "Create a 10-slide undergraduate lesson on the fundamentals of quantum computing, with diagrams and a quiz at the end." },
      { label: "Research summary", prompt: "Create a research summary deck on the latest 2025-2026 breakthroughs in fusion energy, with citations." },
    ],
  },
  {
    id: "website",
    label: "Build website",
    icon: Globe,
    status: "beta",
    tagline: "Generate a multi-page marketing site with copy, layout, and assets.",
    placeholder:
      "e.g., Build a 4-page marketing site for a B2B accounting SaaS, with hero, features, pricing, and contact.",
    cta: "Plan website",
    chips: [
      { label: "SaaS landing", prompt: "Build a single-page SaaS landing site for a project-management tool, with hero, features, testimonials, pricing, and CTA." },
      { label: "Personal portfolio", prompt: "Build a personal portfolio site for a UX designer, with about, work, case studies, and contact." },
      { label: "Restaurant", prompt: "Build a 3-page restaurant site with menu, reservations, and gallery, in a warm minimal style." },
      { label: "Open-source docs", prompt: "Build a documentation site for an open-source library, with install, quickstart, API reference, and examples." },
    ],
  },
  {
    id: "desktop",
    label: "Desktop app",
    icon: Monitor,
    status: "soon",
    tagline: "Scaffold a cross-platform desktop app with a polished UI.",
    placeholder:
      "e.g., Develop a cross-platform desktop note-taking app with markdown, tags, and local search.",
    cta: "Plan desktop app",
    chips: [
      { label: "Note-taking", prompt: "Develop a cross-platform desktop note-taking app with markdown, tags, full-text search, and local-first sync." },
      { label: "Pomodoro timer", prompt: "Develop a minimal desktop pomodoro timer with task list, daily stats, and system-tray controls." },
      { label: "File organizer", prompt: "Develop a desktop file-organizer that watches folders and auto-sorts by rules and content type." },
    ],
  },
  {
    id: "design",
    label: "Design",
    icon: Palette,
    status: "beta",
    tagline: "Generate a brand kit, social assets, or a full design system.",
    placeholder:
      "e.g., Design a brand kit for a sustainable coffee startup, with logo direction, palette, type, and social templates.",
    cta: "Generate design",
    chips: [
      { label: "Brand kit", prompt: "Design a brand kit for a sustainable coffee startup, with logo direction, color palette, typography, and tone-of-voice." },
      { label: "Social pack", prompt: "Design a 10-piece Instagram/LinkedIn social pack announcing a Series A funding round." },
      { label: "Pitch visuals", prompt: "Design a set of pitch-deck cover and section visuals for an AI infrastructure company." },
      { label: "Design system", prompt: "Design a lightweight design system with primitives (colors, type, spacing) and 12 core components for a fintech web app." },
    ],
  },
  {
    id: "research",
    label: "Research",
    icon: Search,
    status: "live",
    tagline: "Live web research with citations, summarized into a structured brief.",
    placeholder:
      "e.g., Research the state of solid-state batteries in 2026, with players, milestones, and remaining challenges.",
    cta: "Run research",
    chips: [
      { label: "Industry scan", prompt: "Research the state of solid-state batteries in 2026, with key players, recent milestones, and remaining technical challenges. Cite sources." },
      { label: "Competitor brief", prompt: "Research and compare the top 5 AI presentation tools (features, pricing, target users, weaknesses). Cite sources." },
      { label: "Topic primer", prompt: "Research a primer on quantum-resistant cryptography for a non-technical exec audience. Cite sources." },
      { label: "Trend report", prompt: "Research the 2026 trends in agentic AI: model capabilities, frameworks, deployment patterns, and adoption signals. Cite sources." },
    ],
  },
];

export const MODE_BY_ID = Object.fromEntries(MODES.map((m) => [m.id, m]));

export const STATUS_BADGE = {
  live: { label: "Live", cls: "bg-accent-teal/15 text-accent-teal border-accent-teal/30" },
  beta: { label: "Beta", cls: "bg-accent-purple/15 text-accent-purple border-accent-purple/30" },
  soon: { label: "Coming soon", cls: "bg-nexus-card text-nexus-muted border-nexus-border" },
};
