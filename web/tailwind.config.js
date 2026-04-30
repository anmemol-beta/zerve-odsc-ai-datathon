/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{ts,tsx}",
    "./components/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#020617",
          900: "#0b1120",
          800: "#0f172a",
          700: "#1e293b",
          600: "#334155",
        },
        accent: {
          pink:   "#ec4899",
          cyan:   "#06b6d4",
          green:  "#10b981",
          violet: "#8b5cf6",
          amber:  "#f59e0b",
        },
      },
      fontFamily: {
        sans: ['"Inter"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      animation: {
        "blob-1": "blob1 18s ease-in-out infinite",
        "blob-2": "blob2 22s ease-in-out infinite",
        "blob-3": "blob3 26s ease-in-out infinite",
      },
      keyframes: {
        blob1: {
          "0%,100%": { transform: "translate(0, 0) scale(1)" },
          "33%":     { transform: "translate(40px, -30px) scale(1.1)" },
          "66%":     { transform: "translate(-20px, 30px) scale(0.95)" },
        },
        blob2: {
          "0%,100%": { transform: "translate(0, 0) scale(1)" },
          "33%":     { transform: "translate(-50px, 20px) scale(0.9)" },
          "66%":     { transform: "translate(30px, -40px) scale(1.15)" },
        },
        blob3: {
          "0%,100%": { transform: "translate(0, 0) scale(1)" },
          "50%":     { transform: "translate(60px, 40px) scale(1.05)" },
        },
      },
    },
  },
  plugins: [],
};
