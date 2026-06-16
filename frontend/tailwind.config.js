/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0a0a0a",
        surface: "#111111",
        elevated: "#1a1a1a",
        line: "#2a2a2a",
        input: "#0f0f0f",
        inputline: "#333333",
        muted: "#888888",
        danger: "#ff4444",
        success: "#00cc66",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      borderRadius: {
        card: "12px",
        btn: "8px",
      },
      boxShadow: {
        glossy: "inset 0 1px 0 rgba(255,255,255,0.08)",
        glossylg:
          "inset 0 1px 0 rgba(255,255,255,0.08), 0 8px 24px rgba(0,0,0,0.5)",
      },
    },
  },
  plugins: [],
};
