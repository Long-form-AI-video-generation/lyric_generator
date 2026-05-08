import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
    "./lib/**/*.{ts,tsx}",
    "./store/**/*.{ts,tsx}"
  ],
  theme: {
    extend: {
      colors: {
        background: "#0A0A0A",
        surface: "#141414",
        surface2: "#1A1A1A",
        border: "#2A2A2A",
        primary: "#7C3AED",
        success: "#10B981",
        destructive: "#EF4444",
        muted: "#71717A",
        text: "#F5F5F5"
      },
      boxShadow: {
        glow: "0 0 28px rgba(124, 58, 237, 0.20)"
      },
      fontFamily: {
        sans: ["var(--font-inter)", "Inter", "sans-serif"],
        display: ["var(--font-montserrat)", "Montserrat", "sans-serif"]
      }
    }
  },
  plugins: []
};

export default config;

