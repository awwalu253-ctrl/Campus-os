// Campus OS — app bootstrap
(function () {
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker.register('/service-worker.js', { scope: '/' })
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
      'position:fixed;left:16px;right:16px;bottom:80px;z-index:60;display:flex;' +
      'justify-content:space-between;align-items:center;gap:12px;';
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
})();