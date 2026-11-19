import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: "class",
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        /**
         * Semantic surface/foreground tokens. These resolve through CSS variables
         * set in globals.css, so a single `.dark` class re-themes every screen.
         * `ink` stays the brand-dark band colour in both themes.
         */
        canvas: "rgb(var(--canvas) / <alpha-value>)",
        surface: {
          DEFAULT: "rgb(var(--surface) / <alpha-value>)",
          2: "rgb(var(--surface-2) / <alpha-value>)",
          3: "rgb(var(--surface-3) / <alpha-value>)",
        },
        line: {
          DEFAULT: "rgb(var(--line) / <alpha-value>)",
          strong: "rgb(var(--line-strong) / <alpha-value>)",
        },
        fg: {
          DEFAULT: "rgb(var(--fg) / <alpha-value>)",
          strong: "rgb(var(--fg-strong) / <alpha-value>)",
          soft: "rgb(var(--fg-soft) / <alpha-value>)",
          muted: "rgb(var(--fg-muted) / <alpha-value>)",
          subtle: "rgb(var(--fg-subtle) / <alpha-value>)",
        },
        ink: {
          DEFAULT: "#0B1F2A",
          900: "#071620",
          700: "#123241",
          600: "#1B4557",
          400: "#4A6B7A",
        },
        sand: {
          DEFAULT: "#F7F4EF",
          50: "#FCFAF7",
          200: "#EDE7DC",
          300: "#DED5C6",
        },
        teal: {
          DEFAULT: "#0F766E",
          bright: "#14B8A6",
          soft: "#CCFBF1",
          deep: "#0B5D57",
        },
        amber: {
          DEFAULT: "#D97706",
          soft: "#FEF3C7",
        },
        crimson: "#B91C1C",
      },
      fontFamily: {
        sans: ["Inter", "Noto Sans Devanagari", "system-ui", "sans-serif"],
      },
      boxShadow: {
        card: "0 1px 2px rgba(11,31,42,0.06), 0 12px 28px -18px rgba(11,31,42,0.35)",
        lift: "0 2px 4px rgba(11,31,42,0.08), 0 24px 48px -24px rgba(11,31,42,0.45)",
      },
      keyframes: {
        "fade-up": {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        "fade-up": "fade-up 400ms cubic-bezier(0.22,1,0.36,1) both",
      },
    },
  },
  plugins: [],
};

export default config;
