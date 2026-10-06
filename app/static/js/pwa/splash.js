// Custom in-app splash — fires once per standalone session.
// On a server-rendered app, every link click is a full page load, so we
// gate the splash behind sessionStorage: it runs on the very first page
// load of a PWA session, and never again until the app is closed and
// reopened.
(function () {
  const standalone =
    window.matchMedia('(display-mode: standalone)').matches ||
    window.navigator.standalone === true;

  // Never show in a browser tab.
  if (!standalone) return;

  // Never show if the user has reduce-motion enabled.
  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  const SPLASH_KEY = 'campusos.splash.shown';
  let alreadyShown = false;
  try {
    alreadyShown = sessionStorage.getItem(SPLASH_KEY) === '1';
  } catch (e) {
    // sessionStorage may be unavailable (private mode, etc.). Fail closed
    // — do not show a splash we can't track.
    return;
  }

  if (alreadyShown) return;

  // Mark it immediately so a fast double-navigation can't show it twice.
  try {
    sessionStorage.setItem(SPLASH_KEY, '1');
  } catch (e) {
    return;
  }

  // Reduce-motion users still get the flag set (so we don't retry) but
  // skip the visual.
  if (reduce) return;

  const splash = document.getElementById('splash');
  if (!splash) return;

  // Show the splash and let CSS do the fade.
  requestAnimationFrame(() => splash.classList.add('is-visible'));

  // Visible for ~1.2s, faded out by ~1.4s, removed at ~1.5s.
  setTimeout(() => splash.classList.remove('is-visible'), 1200);
  setTimeout(() => splash.remove(), 1500);
})();