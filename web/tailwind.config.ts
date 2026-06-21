import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}", "./lib/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        app: "var(--bg-app)",
        raised: "var(--bg-raised)",
        card: "var(--surface-card)",
        sunken: "var(--surface-sunken)",
        tint: "var(--surface-tint)",
        strong: "var(--text-strong)",
        body: "var(--text-body)",
        muted: "var(--text-muted)",
        subtle: "var(--text-subtle)",
        brand: "var(--evergreen-700)",
        evergreen: {
          50: "var(--evergreen-50)",
          100: "var(--evergreen-100)",
          200: "var(--evergreen-200)",
          400: "var(--evergreen-400)",
          500: "var(--evergreen-500)",
          600: "var(--evergreen-600)",
          700: "var(--evergreen-700)",
          800: "var(--evergreen-800)",
          900: "var(--evergreen-900)",
        },
      },
      fontFamily: {
        display: ["var(--font-display)"],
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"],
      },
      borderColor: {
        subtle: "var(--border-subtle)",
        DEFAULT: "var(--border-default)",
        strong: "var(--border-strong)",
        brand: "var(--border-brand)",
      },
      boxShadow: {
        xs: "var(--shadow-xs)",
        sm: "var(--shadow-sm)",
        md: "var(--shadow-md)",
        lg: "var(--shadow-lg)",
      },
      borderRadius: {
        md: "var(--radius-md)",
        lg: "var(--radius-lg)",
        xl: "var(--radius-xl)",
      },
    },
  },
  plugins: [],
};

export default config;
