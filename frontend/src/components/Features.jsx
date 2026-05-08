import { useEffect, useState } from "react";
import { Wand2, Search, Layers, Download } from "lucide-react";
import { api } from "../utils/api.js";

const baseItems = (modelTitle, modelBody) => [
  {
    icon: Search,
    title: "Live research",
    body: "Web search (Tavily / DuckDuckGo / Wikipedia) pulls fresh facts and citations into every deck.",
  },
  {
    icon: Wand2,
    title: modelTitle,
    body: modelBody,
  },
  {
    icon: Layers,
    title: "Six layouts + critic",
    body: "Title, bullets, two-column, quote, stats, closing — then a critic pass rewrites bland slides with specifics.",
  },
  {
    icon: Download,
    title: "Export anywhere",
    body: "Download .pptx and .pdf, or share a public preview link in one click.",
  },
];

export default function Features() {
  const [items, setItems] = useState(
    baseItems("Multi-provider AI", "Falls back across Groq, Gemini, OpenRouter, and NVIDIA NIM \u2014 fast, sharp, and structured.")
  );
  useEffect(() => {
    api
      .get("/health")
      .then(({ data }) => {
        const provider = data?.provider || "";
        const titles = {
          anthropic: ["Claude Sonnet", "Same model class Manus AI uses in production \u2014 fast, sharp, and structured."],
          groq: ["Llama 3.3 70B \u00b7 Groq", "Open-weight 70B model running at >500 tok/s on Groq LPUs \u2014 the fastest free inference available."],
          gemini: ["Gemini 2.0 Flash", "Google's free-tier flagship \u2014 1500 requests/day, multimodal, low-latency."],
          openrouter: ["Llama 3.3 70B \u00b7 OpenRouter", "Free-tier Llama 3.3 70B Instruct routed through OpenRouter."],
          nvidia_nim: ["Llama 3.3 70B \u00b7 NVIDIA NIM", "Llama 3.3 70B served on NVIDIA's hosted NIM endpoints."],
          openai: ["GPT-4.1", "OpenAI's flagship reasoning model as a paid fallback."],
        };
        const [t, b] = titles[provider] || ["Multi-provider AI", "Falls back across Groq, Gemini, OpenRouter, and NVIDIA NIM."];
        setItems(baseItems(t, b));
      })
      .catch(() => {});
  }, []);
  return (
    <section id="features" className="mx-auto max-w-6xl px-6 py-20">
      <h2 className="mb-12 text-center text-3xl font-semibold tracking-tight md:text-4xl">
        Built for <span className="gradient-text">production</span>.
      </h2>
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-4">
        {items.map(({ icon: Icon, title, body }) => (
          <div
            key={title}
            className="card group p-5 transition hover:border-nexus-borderHi"
          >
            <div className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg bg-nexus-card group-hover:bg-gradient-nexus transition">
              <Icon className="h-5 w-5 text-nexus-text group-hover:text-nexus-bg transition" />
            </div>
            <h3 className="mb-1.5 font-medium">{title}</h3>
            <p className="text-sm leading-relaxed text-nexus-muted">{body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
