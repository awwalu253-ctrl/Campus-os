/* Campus OS — Admin shell interactions.
 * Vanilla JS. Loaded only on admin pages.
 */
(function () {
  'use strict';

  // ── Mobile sidebar toggle ────────────────────────────
  var shell = document.querySelector('[data-admin-shell]');
  var toggle = document.querySelector('[data-admin-toggle]');
  var backdrop = document.querySelector('[data-admin-backdrop]');

  function closeSidebar() {
    if (!shell) return;
    shell.removeAttribute('data-admin-shell');
    if (toggle) toggle.setAttribute('aria-expanded', 'false');
    if (backdrop) backdrop.hidden = true;
  }

  function openSidebar() {
    if (!shell) return;
    shell.setAttribute('data-admin-shell', 'open');
    if (toggle) toggle.setAttribute('aria-expanded', 'true');
    if (backdrop) backdrop.hidden = false;
  }

  if (toggle) {
    toggle.addEventListener('click', function () {
      if (!shell) return;
      if (shell.getAttribute('data-admin-shell') === 'open') closeSidebar();
      else openSidebar();
    });
  }
  if (backdrop) backdrop.addEventListener('click', closeSidebar);

  // ── Account menu ─────────────────────────────────────
  var menu = document.querySelector('[data-admin-menu]');
  var menuTrigger = document.querySelector('[data-admin-menu-trigger]');
  var menuPanel = document.querySelector('[data-admin-menu-panel]');

  function closeMenu() {
    if (!menuPanel || !menuTrigger) return;
    menuPanel.hidden = true;
    menuTrigger.setAttribute('aria-expanded', 'false');
  }
  function openMenu() {
    if (!menuPanel || !menuTrigger) return;
    menuPanel.hidden = false;
    menuTrigger.setAttribute('aria-expanded', 'true');
  }
  if (menuTrigger && menuPanel) {
    menuTrigger.addEventListener('click', function (ev) {
      ev.stopPropagation();
      if (menuPanel.hidden) openMenu(); else closeMenu();
    });
    document.addEventListener('click', function (ev) {
      if (!menu || menu.contains(ev.target)) return;
      closeMenu();
    });
    document.addEventListener('keydown', function (ev) {
      if (ev.key === 'Escape') closeMenu();
    });
  }

  // ── Confirm destructive actions ──────────────────────
  document.querySelectorAll('[data-confirm]').forEach(function (el) {
    el.addEventListener('submit', function (ev) {
      var msg = el.getAttribute('data-confirm') || 'Are you sure?';
      if (!window.confirm(msg)) ev.preventDefault();
    });
  });
})();