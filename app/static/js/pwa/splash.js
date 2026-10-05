// Custom in-app splash — only shown in standalone/installed mode (per spec §8).
(function () {
  const standalone = window.matchMedia('(display-mode: standalone)').matches
    || window.navigator.standalone === true;
  if (!standalone) return;

  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  const splash = document.getElementById('splash');
  if (!splash) return;

  if (reduce) {
    // Skip animation entirely
    return;
  }

  splash.classList.add('is-visible');

  // Fade out at ~1.4s, remove at 1.7s
  setTimeout(() => splash.classList.remove('is-visible'), 1400);
  setTimeout(() => splash.remove(), 1800);
})();