import { defineConfig, build } from 'vite';
import react from '@vitejs/plugin-react';
import { resolve } from 'path';

// Chrome MV3 extension — three separate Vite builds:
//   1. popup   : standard React SPA (popup/index.html)
//   2. content : IIFE bundle injected into linkedin.com pages
//   3. background : ES module service worker
//
// Run `npm run build` which calls `node build.mjs` to orchestrate all three.
// `npm run dev` watches all three in parallel.

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': resolve(__dirname, 'src') },
  },
  define: {
    // Suppress React dev warnings in extension context
    'process.env.NODE_ENV': '"production"',
  },
  build: {
    target: 'chrome111',
    outDir: 'dist',
    emptyOutDir: false,
    sourcemap: false,
    rollupOptions: {
      input: {
        // Popup is a full HTML page — Vite handles all assets automatically
        'popup/index': resolve(__dirname, 'src/popup/index.html'),
        // Background service worker — ESM (MV3 supports `type: module`)
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

// Content script config (IIFE — no dynamic imports allowed in content scripts)
export const contentConfig = defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': resolve(__dirname, 'src') },
  },
  define: {
    'process.env.NODE_ENV': '"production"',
  },
  build: {
    target: 'chrome111',
    outDir: 'dist',
    emptyOutDir: false,
    sourcemap: false,
    lib: {
      entry: resolve(__dirname, 'src/content/index.tsx'),
      name: 'JoboraContent',
      formats: ['iife'],
      fileName: () => 'index.js',
    },
    rollupOptions: {
      output: {
        dir: 'dist/content',
        entryFileNames: 'index.js',
        // Bundle React + all dependencies — content scripts are isolated
        inlineDynamicImports: true,
      },
    },
  },
});
