/* Campus OS — Admin shell interactions. Loaded only on admin pages. */
(function () {
  'use strict';

  var shell = document.querySelector('[data-admin-shell]');
  var toggle = document.querySelector('[data-admin-toggle]');
  var backdrop = document.querySelector('[data-admin-backdrop]');
  var sidebar = document.querySelector('.admin-sidebar');

  // ── Mobile sidebar ──────────────────────────────────
  function setSidebarOpen(open) {
    if (!shell) return;
    if (open) shell.setAttribute('data-admin-shell', 'open');
    else shell.removeAttribute('data-admin-shell');
    if (toggle) toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (backdrop) backdrop.hidden = !open;
    if (sidebar) sidebar.setAttribute('aria-hidden', open ? 'false' : 'true');
    // Phase 2.1: keep aria-hidden / inert in sync with the drawer state.
    // syncSidebarA11y is defined further down in this IIFE and is hoisted,
    // so it is safe to reference here regardless of declaration order.
    if (typeof syncSidebarA11y === 'function') syncSidebarA11y();
  }

  if (toggle) {
    toggle.addEventListener('click', function () {
      var isOpen = shell && shell.getAttribute('data-admin-shell') === 'open';
      setSidebarOpen(!isOpen);
    });
  }
  if (backdrop) {
    backdrop.addEventListener('click', function () { setSidebarOpen(false); });
  }

  // Close the mobile sidebar before navigating.
  if (sidebar) {
    sidebar.querySelectorAll('a.admin-nav__item').forEach(function (link) {
      link.addEventListener('click', function () {
        if (window.matchMedia('(max-width: 1023px)').matches) {
          setSidebarOpen(false);
        }
      });
    });
  }

  // ── Account menu (disclosure pattern, not a menu) ───
  var menu = document.querySelector('[data-admin-menu]');
  var menuTrigger = document.querySelector('[data-admin-menu-trigger]');
  var menuPanel = document.querySelector('[data-admin-menu-panel]');

  function setMenuOpen(open) {
    if (!menuPanel || !menuTrigger) return;
    menuPanel.hidden = !open;
    menuTrigger.setAttribute('aria-expanded', open ? 'true' : 'false');
    if (open) {
      var firstFocusable = menuPanel.querySelector(
        'a, button, [tabindex]:not([tabindex="-1"])'
      );
      if (firstFocusable) firstFocusable.focus();
    }
  }

  if (menuTrigger && menuPanel) {
    menuTrigger.addEventListener('click', function (ev) {
      ev.stopPropagation();
      setMenuOpen(menuPanel.hidden);
    });

    document.addEventListener('click', function (ev) {
      if (!menu || menu.contains(ev.target)) return;
      if (!menuPanel.hidden) setMenuOpen(false);
    });

    document.addEventListener('keydown', function (ev) {
      if (ev.key !== 'Escape') return;
      if (!menuPanel || menuPanel.hidden) return;
      setMenuOpen(false);
      if (menuTrigger) menuTrigger.focus();
    });

    menuPanel.addEventListener('keydown', function (ev) {
      if (ev.key !== 'Tab') return;
      // Simple focus trap within the panel.
      var focusables = menuPanel.querySelectorAll(
        'a, button, [tabindex]:not([tabindex="-1"])'
      );
      if (!focusables.length) return;
      var first = focusables[0];
      var last = focusables[focusables.length - 1];
      if (ev.shiftKey && document.activeElement === first) {
        ev.preventDefault(); last.focus();
      } else if (!ev.shiftKey && document.activeElement === last) {
        ev.preventDefault(); first.focus();
      }
    });
  }

  // ── Confirm destructive forms ───────────────────────
  document.querySelectorAll('form[data-confirm]').forEach(function (form) {
    form.addEventListener('submit', function (ev) {
      var msg = form.getAttribute('data-confirm') || 'Are you sure?';
      if (!window.confirm(msg)) ev.preventDefault();
    });
  });

  // ── Phase 2.1: mobile sidebar a11y state sync ───────
  // Step 1 made the sidebar start aria-hidden="true" so a closed
  // mobile drawer isn't exposed to assistive tech on first paint.
  // That default is wrong on desktop. This block:
  //   1. Corrects aria-hidden/inert on load and on viewport change.
  //   2. Is called by setSidebarOpen() (see above) so toggles stay in sync.
  //   3. Feature-detects `inert` before assigning it.

  var sidebarEl = document.querySelector('[data-admin-sidebar]');
  var mobileMq = window.matchMedia('(max-width: 1023px)');
  var supportsInert = ('inert' in HTMLElement.prototype);

  function syncSidebarA11y() {
    if (!sidebarEl) return;
    var isMobile = mobileMq.matches;
    var isOpen = shell && shell.getAttribute('data-admin-shell') === 'open';

    if (!isMobile) {
      // Desktop: sidebar is always visible and interactive.
      sidebarEl.setAttribute('aria-hidden', 'false');
      if (supportsInert) sidebarEl.inert = false;
      return;
    }

    // Mobile: reflect the drawer's open/closed state.
    if (isOpen) {
      sidebarEl.setAttribute('aria-hidden', 'false');
      if (supportsInert) sidebarEl.inert = false;
    } else {
      sidebarEl.setAttribute('aria-hidden', 'true');
      if (supportsInert) sidebarEl.inert = true;
    }
  }

  // Initial correction and viewport-change correction.
  syncSidebarA11y();
  if (typeof mobileMq.addEventListener === 'function') {
    mobileMq.addEventListener('change', syncSidebarA11y);
  } else if (typeof mobileMq.addListener === 'function') {
    // Safari < 14 fallback.
    mobileMq.addListener(syncSidebarA11y);
  }
})();