// Campus OS — app bootstrap
(function () {
  // ── Service worker registration ─────────────────────
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker
        .register('/service-worker.js', { scope: '/' })
        .then((reg) => {
          reg.addEventListener('updatefound', () => {
            const worker = reg.installing;
            if (!worker) return;
            worker.addEventListener('statechange', () => {
              if (worker.state === 'installed' && navigator.serviceWorker.controller) {
                showUpdateToast();
              }
            });
          });
        })
        .catch((err) => console.warn('[SW] registration failed', err));
    });
  }

  function showUpdateToast() {
    const el = document.createElement('div');
    el.className = 'flash flash--info';
    el.style.cssText =
      'position:fixed;left:16px;right:16px;bottom:80px;z-index:60;' +
      'display:flex;justify-content:space-between;align-items:center;gap:12px;';
    el.innerHTML = '<span>Update available.</span>';
    const btn = document.createElement('button');
    btn.className = 'btn btn--primary';
    btn.textContent = 'Refresh';
    btn.onclick = () => {
      navigator.serviceWorker.controller?.postMessage('SKIP_WAITING');
      location.reload();
    };
    el.appendChild(btn);
    document.body.appendChild(el);
  }

  // ── Navigation spinner overlay ──────────────────────
  // Shows a centered spinner during internal navigation. Only appears if
  // the wait exceeds SHOW_DELAY_MS (so fast pages don't flash), and once
  // shown it stays for at least MIN_VISIBLE_MS (so it doesn't blink).

  const SHOW_DELAY_MS = 150;
  const MIN_VISIBLE_MS = 350;

  let showTimer = null;
  let spinnerShownAt = 0;

  function getSpinner() {
    return document.getElementById('nav-spinner');
  }

  function showSpinner() {
    const el = getSpinner();
    if (!el) return;
    spinnerShownAt = Date.now();
    el.classList.add('is-active');
  }

  function hideSpinner() {
    const el = getSpinner();
    if (!el) return;
    const elapsed = spinnerShownAt ? Date.now() - spinnerShownAt : 0;
    const remaining = Math.max(0, MIN_VISIBLE_MS - elapsed);
    setTimeout(() => {
      el.classList.remove('is-active');
      spinnerShownAt = 0;
    }, remaining);
  }

  function beginNavigation() {
    // If a previous navigation was mid-flight, cancel its pending show.
    if (showTimer) clearTimeout(showTimer);
    showTimer = setTimeout(showSpinner, SHOW_DELAY_MS);
  }

  function isInternalLink(anchor) {
    if (!anchor || !anchor.href) return false;
    if (anchor.target && anchor.target !== '_self') return false;
    if (anchor.hasAttribute('download')) return false;
    const href = anchor.getAttribute('href');
    if (!href || href.startsWith('#')) return false;
    if (href.startsWith('mailto:') || href.startsWith('tel:')) return false;
    try {
      const url = new URL(anchor.href, window.location.origin);
      return url.origin === window.location.origin;
    } catch {
      return false;
    }
  }

  document.addEventListener('click', (e) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    if (e.defaultPrevented) return;
    const anchor = e.target.closest('a');
    if (!isInternalLink(anchor)) return;
    beginNavigation();
  });

  document.addEventListener('submit', (e) => {
    if (e.defaultPrevented) return;
    beginNavigation();
  });

  // When the new page finishes loading, hide any spinner that managed to
  // appear. Because each page gets a fresh JS context, this runs on the
  // incoming page — the spinner element is present but inactive by default,
  // so nothing flashes.
  window.addEventListener('pageshow', () => {
    if (showTimer) clearTimeout(showTimer);
    hideSpinner();
  });

  window.addEventListener('popstate', () => {
    if (showTimer) clearTimeout(showTimer);
    hideSpinner();
  });
})();