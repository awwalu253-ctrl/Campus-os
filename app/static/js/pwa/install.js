// Custom "Add to Home Screen" experience.
(function () {
  const DISMISS_KEY = 'campusos.install.dismissedAt';
  const INSTALLED_KEY = 'campusos.install.installed';
  const COOLDOWN_MS = 14 * 24 * 60 * 60 * 1000;

  const card = document.getElementById('install-card');
  if (!card) return;

  const acceptBtn = card.querySelector('[data-install-accept]');
  const dismissBtn = card.querySelector('[data-install-dismiss]');

  const standalone = window.matchMedia('(display-mode: standalone)').matches
    || window.navigator.standalone === true;

  // Already running as an installed PWA: never show the card.
  if (standalone) return;

  // Previously recorded that this device installed the app: never show
  // the card again, even if the browser re-fires beforeinstallprompt.
  // This survives browser restarts until site data is cleared.
  if (localStorage.getItem(INSTALLED_KEY) === 'true') return;

  // The user dismissed the card recently: honour the cooldown.
  const dismissedAt = Number(localStorage.getItem(DISMISS_KEY) || 0);
  if (dismissedAt && Date.now() - dismissedAt < COOLDOWN_MS) return;

  const ua = navigator.userAgent.toLowerCase();
  const isIOS = /iphone|ipad|ipod/.test(ua);
  const isAndroid = /android/.test(ua);

  let deferredPrompt = null;

  // Chrome/Edge/Android fire this when the app is installable.
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    show(isAndroid ? 'android' : 'generic');
  });

  // Fires after a successful install. Record it so we never show the
  // card again.
  window.addEventListener('appinstalled', () => {
    localStorage.setItem(INSTALLED_KEY, 'true');
    hide();
  });

  // iOS Safari: no beforeinstallprompt. Show manual instructions.
  if (isIOS) {
    if (/safari/.test(ua) && !/crios|fxios|edgios/.test(ua)) {
      setTimeout(() => show('ios'), 2500);
    }
  }

  acceptBtn?.addEventListener('click', async () => {
    if (deferredPrompt) {
      deferredPrompt.prompt();
      const { outcome } = await deferredPrompt.userChoice;
      deferredPrompt = null;
      if (outcome === 'accepted') {
        localStorage.setItem(INSTALLED_KEY, 'true');
        hide();
      }
    } else if (isIOS) {
      showIOSInstructions();
    }
  });

  dismissBtn?.addEventListener('click', () => {
    localStorage.setItem(DISMISS_KEY, String(Date.now()));
    hide();
  });

  function show(mode) {
    card.dataset.mode = mode;
    if (mode === 'ios') {
      card.querySelector('p').textContent =
        'Install Campus OS: tap Share, then "Add to Home Screen".';
      acceptBtn.textContent = 'Show me how';
    }
    card.hidden = false;
  }

  function hide() { card.hidden = true; }

  function showIOSInstructions() {
    const overlay = document.createElement('div');
    overlay.className = 'flash flash--info';
    overlay.style.cssText =
      'position:fixed;inset:auto 16px 96px 16px;z-index:60;padding:16px;';
    overlay.innerHTML =
      '<strong>Add Campus OS to your Home Screen</strong>' +
      '<ol style="margin:8px 0 0 18px;padding:0;">' +
      '<li>Tap the Share icon</li>' +
      '<li>Scroll and choose <em>Add to Home Screen</em></li>' +
      '<li>Tap <em>Add</em></li>' +
      '</ol>';
    document.body.appendChild(overlay);
    setTimeout(() => overlay.remove(), 12000);
  }
})();