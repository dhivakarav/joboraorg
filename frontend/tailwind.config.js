/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        // ===== Legacy semantic tokens — REMAPPED to LIGHT values so every
        // screen using them (.bg-surface/.border-line/.text-muted/…) flips to
        // the white SaaS theme automatically. Names kept for compatibility. =====
        bg: "#F8FAFC",            // page background (was near-black)
        surface: "#FFFFFF",       // card surface
        elevated: "#F1F5F9",      // subtle raised / hover fill (slate-100)
        line: "#E2E8F0",          // hairline borders
        hairline: "#E2E8F0",
        input: "#FFFFFF",
        inputline: "#E2E8F0",
        muted: "#64748B",         // secondary text (slate-500)
        danger: "#EF4444",
        success: "#16A34A",       // darker green for legible text on white
        accent: "#2563EB",        // brand blue
        "accent-soft": "rgba(37,126,235,0.12)",
        mint: "#16A34A",
        // ===== LIGHT SaaS theme (white redesign) — additive tokens =====
        canvas: "#F8FAFC",       // primary background
        ink: "#0F172A",          // primary text
        "ink-soft": "#64748B",   // secondary text
        edge: "#E2E8F0",         // borders
        brand: "#2563EB",        // primary blue
        "brand-hover": "#1D4ED8",
        "brand-soft": "#DBEAFE", // light blue
        ok: "#22C55E",
        warn: "#F59E0B",
        err: "#EF4444",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      borderRadius: {
        card: "12px",
        btn: "8px",
        xl2: "18px", // premium card radius range (18–24px)
        xl3: "24px",
      },
      boxShadow: {
        glossy: "inset 0 1px 0 rgba(255,255,255,0.08)",
        glossylg:
          "inset 0 1px 0 rgba(255,255,255,0.08), 0 8px 24px rgba(0,0,0,0.5)",
        // Premium depth + hover lift + soft accent glow
        soft: "0 1px 2px rgba(0,0,0,0.4), inset 0 1px 0 rgba(255,255,255,0.05)",
        lift: "0 24px 60px -20px rgba(0,0,0,0.75), inset 0 1px 0 rgba(255,255,255,0.07)",
        glow: "0 0 0 1px rgba(255,255,255,0.12), 0 18px 50px -16px rgba(0,0,0,0.7)",
        glowaccent:
          "0 0 0 1px rgba(79,126,255,0.45), 0 16px 44px -14px rgba(79,126,255,0.30)",
        // Light-theme depth
        "card-l": "0 1px 3px rgba(15,23,42,0.06), 0 1px 2px rgba(15,23,42,0.04)",
        "lift-l": "0 22px 48px -18px rgba(15,23,42,0.18), 0 2px 6px rgba(15,23,42,0.05)",
        "glow-l": "0 0 0 4px rgba(37,99,235,0.12)",
      },
    },
  },
  plugins: [],
};
