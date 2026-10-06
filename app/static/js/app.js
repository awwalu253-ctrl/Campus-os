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

  // ── Navigation loading bar ──────────────────────────
  // Shows a thin animated bar during any internal navigation. Because
  // each navigation is a full page load, we can't animate across the
  // transition — but starting the bar on click and letting the new page
  // instantly render its own (hidden) bar reads as continuous.

  const bar = document.getElementById('loading-bar');

  function startLoading() {
    if (!bar) return;
    bar.classList.add('is-active');
    bar.style.width = '0';
    // Two rAF frames so the browser sees the initial 0 width before
    // animating, otherwise the transition doesn't fire.
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        bar.style.width = '75%';
      });
    });
  }

  function completeLoading() {
    if (!bar) return;
    bar.style.width = '100%';
    setTimeout(() => {
      bar.classList.remove('is-active');
      bar.style.width = '0';
    }, 180);
  }

  function isInternalLink(anchor) {
    if (!anchor || !anchor.href) return false;
    if (anchor.target && anchor.target !== '_self') return false;
    if (anchor.hasAttribute('download')) return false;
    if (anchor.getAttribute('href')?.startsWith('#')) return false;

    try {
      const url = new URL(anchor.href, window.location.origin);
      return url.origin === window.location.origin;
    } catch {
      return false;
    }
  }

  // Intercept clicks on internal links
  document.addEventListener('click', (e) => {
    // Ignore modified clicks (new tab, etc.)
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
    if (e.defaultPrevented) return;

    const anchor = e.target.closest('a');
    if (!isInternalLink(anchor)) return;
    startLoading();
    // Let the browser continue with the default navigation.
  });

  // Intercept form submissions
  document.addEventListener('submit', (e) => {
    if (e.defaultPrevented) return;
    startLoading();
  });

  // When the new page finishes loading, hide any bar that might be visible.
  window.addEventListener('pageshow', completeLoading);
})();