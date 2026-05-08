/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: {
          DEFAULT: "#0a0a0b",
          raised: "#111114",
          card: "#141418",
        },
        border: {
          subtle: "#1f1f24",
          strong: "#27272a",
        },
        ink: {
          DEFAULT: "#f5f5f7",
          muted: "#a1a1aa",
          dim: "#71717a",
        },
        accent: {
          DEFAULT: "#a78bfa",
          hover: "#b8a1fb",
          dim: "#6d5cb5",
        },
        good: "#4ade80",
        bad: "#f87171",
      },
      fontFamily: {
        sans: [
          "Inter",
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "sans-serif",
        ],
        mono: ["JetBrains Mono", "ui-monospace", "Menlo", "monospace"],
      },
      boxShadow: {
        glow: "0 0 40px -8px rgba(167, 139, 250, 0.35)",
      },
    },
  },
  plugins: [],
};
