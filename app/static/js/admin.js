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
})();