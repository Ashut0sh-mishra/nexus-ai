/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx,ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        nexus: {
          bg: "rgb(var(--nx-bg) / <alpha-value>)",
          surface: "rgb(var(--nx-surface) / <alpha-value>)",
          card: "rgb(var(--nx-card) / <alpha-value>)",
          border: "rgb(var(--nx-border) / <alpha-value>)",
          borderHi: "rgb(var(--nx-borderHi) / <alpha-value>)",
          text: "rgb(var(--nx-text) / <alpha-value>)",
          muted: "rgb(var(--nx-muted) / <alpha-value>)",
          dim: "rgb(var(--nx-dim) / <alpha-value>)",
        },
        accent: {
          purple: "#A78BFA",
          blue: "#60A5FA",
          teal: "#34D399",
        },
      },
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "-apple-system",
          "Segoe UI",
          "sans-serif",
        ],
        mono: ["JetBrains Mono", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      backgroundImage: {
        "gradient-nexus":
          "linear-gradient(120deg, #A78BFA 0%, #60A5FA 50%, #34D399 100%)",
        "radial-fade":
          "radial-gradient(ellipse at top, rgba(167,139,250,0.15), transparent 60%)",
      },
      animation: {
        "fade-up": "fadeUp 0.5s ease-out forwards",
        "pulse-soft": "pulseSoft 2s ease-in-out infinite",
        shimmer: "shimmer 2.5s linear infinite",
      },
      keyframes: {
        fadeUp: {
          "0%": { opacity: 0, transform: "translateY(8px)" },
          "100%": { opacity: 1, transform: "translateY(0)" },
        },
        pulseSoft: {
          "0%, 100%": { opacity: 0.6 },
          "50%": { opacity: 1 },
        },
        shimmer: {
          "0%": { backgroundPosition: "-1000px 0" },
          "100%": { backgroundPosition: "1000px 0" },
        },
      },
    },
  },
  plugins: [],
};
