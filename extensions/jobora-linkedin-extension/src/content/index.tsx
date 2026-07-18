/**
 * Content script entry point.
 *
 * Injected into every https://www.linkedin.com/jobs/* page.
 * Mounts the Jobora sidebar inside a Shadow DOM so its styles never conflict
 * with LinkedIn's CSS, and LinkedIn's styles never bleed into the sidebar.
 *
 * Architecture:
 *   This file (IIFE bundle) → Shadow DOM → React root → <Sidebar />
 *   <Sidebar /> ↔ background SW via chrome.runtime.sendMessage
 */
import React from 'react';
import ReactDOM from 'react-dom/client';
import Sidebar from '../sidebar/Sidebar';
import sidebarCss from '../sidebar/sidebar.css?inline';
import { watchNavigation } from './detector';
import { initAutofill } from '../autofill';
import { resumeBulkIfActive } from '../autofill/bulk';

const HOST_ID = 'jobora-ext-host';

function mount(): void {
  if (document.getElementById(HOST_ID)) return;

  // Shadow host — fixed position, full height, on the right edge.
  // Width is controlled by the Sidebar component itself (open = 380px, closed = 48px).
  const host = document.createElement('div');
  host.id = HOST_ID;
  Object.assign(host.style, {
    position: 'fixed',
    top: '0',
    right: '0',
    zIndex: '2147483647',
    height: '100vh',
    width: '0',           // Sidebar component expands/collapses the host width
    pointerEvents: 'none',
  });
  document.body.appendChild(host);

  // Shadow root isolates our CSS from LinkedIn's styles
  const shadow = host.attachShadow({ mode: 'open' });

  // Inject Tailwind CSS (built as inline string by Vite's ?inline import)
  const style = document.createElement('style');
  style.textContent = sidebarCss;
  shadow.appendChild(style);

  const container = document.createElement('div');
  container.id = 'jobora-sidebar-root';
  container.style.height = '100%';
  shadow.appendChild(container);

  // Mount React — pass the host element so the Sidebar can resize it
  ReactDOM.createRoot(container).render(
    <React.StrictMode>
      <Sidebar hostEl={host} />
    </React.StrictMode>,
  );
}

// ── Initial mount ──────────────────────────────────────────────────────────────
// The scoring sidebar mounts on boards with a full adapter (LinkedIn, Internshala).
// Elsewhere (Naukri, Indeed, generic ATS) we run autofill only.
const IS_LINKEDIN = location.hostname.endsWith('linkedin.com');
const SIDEBAR_HOSTS = ['linkedin.com', 'internshala.com'];
const SHOW_SIDEBAR = SIDEBAR_HOSTS.some(h => location.hostname.endsWith(h));
if (SHOW_SIDEBAR) {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', mount);
  } else {
    mount();
  }
}

// ── Autofill ─────────────────────────────────────────────────────────────────
// Runs on every supported board (LinkedIn modal + generic forms on Naukri /
// Indeed / Internshala). Fills only — the user reviews and submits.
initAutofill();

// If a bulk auto-apply run was in progress (e.g. before navigating to the saved
// search), resume it after the page loads.
if (IS_LINKEDIN) void resumeBulkIfActive();

// ── SPA navigation ─────────────────────────────────────────────────────────────
watchNavigation((url) => {
  // Dispatch a custom event into the shadow DOM's container.
  // The Sidebar listens for this to re-extract the current job.
  const container = document
    .getElementById(HOST_ID)
    ?.shadowRoot?.getElementById('jobora-sidebar-root');
  if (container) {
    container.dispatchEvent(
      new CustomEvent('jobora:navigate', { detail: { url }, bubbles: false }),
    );
  }
});
