import type { Config } from "tailwindcss";

// DESIGN-SYSTEM.md 토큰. 라이트 테마, slate-900 CTA, 상태색 전용.
const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#F1F5F9",
        surface: "#FFFFFF",
        surface2: "#F8FAFC",
        border2: "#E2E8F0",
        border3: "#CBD5E1",
        ink: "#0F172A",
        muted: "#475569",
        dim: "#64748B",
        cta: "#0F172A",
        ok: "#16A34A",
        warn: "#D97706",
        warnsoft: "#FEF3C7",
        danger: "#DC2626",
        info: "#2563EB",
        epic: "#4F46E5",
      },
      fontFamily: {
        sans: ['"IBM Plex Sans"', "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};

export default config;
