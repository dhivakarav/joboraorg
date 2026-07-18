/// <reference types="vite/client" />
/// <reference types="chrome" />

// Injected at build time by build.mjs (vite `define`). Set the JOBORA_API_BASE
// env var when building to override the default API base, e.g.
//   JOBORA_API_BASE=http://localhost:8000/api npm run build
declare const __JOBORA_API_BASE__: string;

// Allow `import css from './file.css?inline'` — returns the CSS text as a string.
declare module '*.css?inline' {
  const content: string;
  export default content;
}
