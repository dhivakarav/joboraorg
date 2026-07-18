/**
 * Extension build orchestrator.
 * Runs two separate Vite passes so each output gets the right format:
 *   Pass 1 — popup + background (ES module)
 *   Pass 2 — content script     (IIFE, no dynamic imports)
 */
import { build } from 'vite';
import { resolve, dirname } from 'path';
import { fileURLToPath } from 'url';
import { copyFileSync, mkdirSync, rmSync } from 'fs';
import react from '@vitejs/plugin-react';

const __dirname = dirname(fileURLToPath(import.meta.url));
const alias = { '@': resolve(__dirname, 'src') };

// API base baked into the bundle. Defaults to production; override for local dev:
//   JOBORA_API_BASE=http://localhost:8000/api npm run build
const API_BASE = process.env.JOBORA_API_BASE || 'https://jobara-api.onrender.com/api';
const define = {
  'process.env.NODE_ENV': '"production"',
  __JOBORA_API_BASE__: JSON.stringify(API_BASE),
};
console.log(`\n🔧  API base baked into build: ${API_BASE}`);

// ── Pass 1: popup + background ────────────────────────────────────────────────
await build({
  plugins: [react()],
  resolve: { alias },
  define,
  build: {
    target: 'chrome111',
    outDir: 'dist',
    emptyOutDir: true,           // clean on first pass only
    sourcemap: false,
    rollupOptions: {
      input: {
        'popup/index': resolve(__dirname, 'src/popup/index.html'),
        'background/index': resolve(__dirname, 'src/background/index.ts'),
      },
      output: {
        entryFileNames: '[name].js',
        chunkFileNames: 'assets/[name]-[hash].js',
        assetFileNames: 'assets/[name]-[hash][extname]',
        format: 'es',
      },
    },
  },
});

// ── Pass 2: content script (IIFE, single-file bundle) ────────────────────────
// Use plain rollupOptions with a single string input — lib mode can't do
// single-file IIFE without triggering the multi-input inlineDynamicImports error.
await build({
  plugins: [react()],
  resolve: { alias },
  define,
  build: {
    target: 'chrome111',
    outDir: 'dist/content',
    emptyOutDir: false,           // keep Pass 1 output
    sourcemap: false,
    rollupOptions: {
      input: resolve(__dirname, 'src/content/index.tsx'),
      output: {
        format: 'iife',
        name: 'JoboraContent',
        entryFileNames: 'index.js',
        inlineDynamicImports: true,  // safe: exactly one input
        // Bundle all assets inline — content script can't import external files
        assetFileNames: 'assets/[name]-[hash][extname]',
      },
    },
  },
});

// ── Post-build: move popup HTML to the path manifest.json expects ─────────────
// Vite mirrors the source path (dist/src/popup/index.html) but the manifest
// declares `popup/index.html`, so we copy + clean up the extra src/ nesting.
const htmlSrc  = resolve(__dirname, 'dist/src/popup/index.html');
const htmlDest = resolve(__dirname, 'dist/popup/index.html');
mkdirSync(resolve(__dirname, 'dist/popup'), { recursive: true });
copyFileSync(htmlSrc, htmlDest);
rmSync(resolve(__dirname, 'dist/src'), { recursive: true, force: true });

// ── Copy manifest.json into dist/ ─────────────────────────────────────────────
copyFileSync(
  resolve(__dirname, 'manifest.json'),
  resolve(__dirname, 'dist/manifest.json'),
);

console.log('\n✅  Extension built to dist/ — load it in chrome://extensions');
