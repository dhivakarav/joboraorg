import type { Config } from 'tailwindcss';

const config: Config = {
  // Only scan extension source files — never the root Jobora codebase
  content: [
    './src/popup/**/*.{ts,tsx}',
    './src/sidebar/**/*.{ts,tsx}',
    './src/content/**/*.{ts,tsx}',
  ],
  theme: {
    extend: {
      // Mirror the Jobora design tokens exactly (from frontend/tailwind.config.js)
      colors: {
        bg: '#F8FAFC',
        canvas: '#F8FAFC',
        surface: '#FFFFFF',
        elevated: '#F1F5F9',
        line: '#E2E8F0',
        edge: '#E2E8F0',
        muted: '#64748B',
        'ink-soft': '#64748B',
        ink: '#0F172A',
        brand: '#2563EB',
        'brand-hover': '#1D4ED8',
        'brand-soft': '#DBEAFE',
        danger: '#EF4444',
        err: '#EF4444',
        success: '#16A34A',
        ok: '#22C55E',
        warn: '#F59E0B',
        accent: '#2563EB',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      borderRadius: {
        card: '12px',
        btn: '8px',
      },
      boxShadow: {
        'card-l': '0 1px 3px rgba(15,23,42,0.06), 0 1px 2px rgba(15,23,42,0.04)',
        'lift-l': '0 22px 48px -18px rgba(15,23,42,0.18), 0 2px 6px rgba(15,23,42,0.05)',
        'glow-l': '0 0 0 4px rgba(37,99,235,0.12)',
        sidebar: '−4px 0 24px rgba(15,23,42,0.12)',
      },
    },
  },
  plugins: [],
};

export default config;
