/**
 * LinkedIn SPA navigation + job-change detector.
 *
 * LinkedIn is a React SPA with two kinds of navigation to handle:
 *
 *   1. Full URL path change
 *      e.g. /jobs/search/ → /jobs/view/123456/
 *      Caught by comparing location.href with the last seen URL.
 *
 *   2. Query-param-only change (same path, different job)
 *      e.g. ?currentJobId=111 → ?currentJobId=222 (search/collections pages)
 *      Caught by comparing the currentJobId query param.
 *
 * Both are detected by a single MutationObserver on document.body childList.
 * LinkedIn's React router updates the URL synchronously before re-rendering,
 * so the URL is always updated by the time our MutationObserver fires.
 */

export type NavigateCallback = (url: string) => void;

/**
 * Watch for LinkedIn SPA navigation (path OR currentJobId changes).
 * Returns a cleanup function to stop watching.
 */
export function watchNavigation(onNavigate: NavigateCallback): () => void {
  let lastHref = window.location.href;
  let lastJobId = extractCurrentJobId(lastHref);

  function checkForChange() {
    const currentHref  = window.location.href;
    const currentJobId = extractCurrentJobId(currentHref);

    const pathChanged  = currentHref !== lastHref;
    const jobIdChanged = currentJobId !== lastJobId && (currentJobId !== '' || lastJobId !== '');

    if (pathChanged || jobIdChanged) {
      lastHref  = currentHref;
      lastJobId = currentJobId;
      onNavigate(currentHref);
    }
  }

  const observer = new MutationObserver(checkForChange);
  observer.observe(document.body, { childList: true, subtree: true });

  // Also listen to popstate for back/forward navigation
  window.addEventListener('popstate', checkForChange);

  return () => {
    observer.disconnect();
    window.removeEventListener('popstate', checkForChange);
  };
}

/**
 * True when this LinkedIn URL has a specific job visible.
 * Covers:
 *   - /jobs/view/ID/                 (direct full-page view)
 *   - /jobs/search/?currentJobId=ID  (search split-pane)
 *   - /jobs/collections/...?currentJobId=ID (collections panel)
 */
export function isLinkedInJobPage(url: string): boolean {
  try {
    const u = new URL(url);
    if (!u.hostname.endsWith('linkedin.com')) return false;
    const path = u.pathname;
    if (/\/jobs\/view\/\d+/.test(path)) return true;
    if ((/\/jobs\/search\//.test(path) || /\/jobs\/collections\//.test(path))
        && u.searchParams.has('currentJobId')) return true;
    return false;
  } catch {
    return false;
  }
}

/** Extract the currentJobId param, or '' if absent. */
export function extractCurrentJobId(url: string): string {
  try {
    const u = new URL(url);
    // Direct view: job ID is in the path
    const viewMatch = u.pathname.match(/\/jobs\/view\/(\d+)/);
    if (viewMatch) return viewMatch[1];
    // Search / collections: currentJobId query param
    return u.searchParams.get('currentJobId') ?? '';
  } catch {
    return '';
  }
}
