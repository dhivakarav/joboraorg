/**
 * LinkedIn SPA navigation detector.
 *
 * LinkedIn is a React SPA — page transitions don't trigger full reloads.
 * We watch for URL changes via MutationObserver and fire a custom event
 * so the sidebar can re-extract the job without remounting.
 */
export function watchNavigation(onNavigate: (url: string) => void): () => void {
  let lastUrl = location.href;

  const observer = new MutationObserver(() => {
    const current = location.href;
    if (current !== lastUrl) {
      lastUrl = current;
      onNavigate(current);
    }
  });

  observer.observe(document.body, { childList: true, subtree: true });

  return () => observer.disconnect();
}

export function isLinkedInJobPage(url: string): boolean {
  try {
    const { hostname, pathname } = new URL(url);
    return (
      hostname.includes('linkedin.com') &&
      /^\/jobs\/(view|search|collections)/.test(pathname)
    );
  } catch {
    return false;
  }
}
