/// <reference types="vite/client" />
/// <reference types="chrome" />

// Allow `import css from './file.css?inline'` — returns the CSS text as a string.
declare module '*.css?inline' {
  const content: string;
  export default content;
}
