/* Campus OS - Notifications frontend.
 *
 * Runs on every authenticated page (via app_shell.html). Two modes:
 *   - "shell": bells + badge + dropdown only (default)
 *   - "page":  shell features + full-page list + pagination + mark-all
 *
 * Config is set by an inline script block in the layout, as
 * window.CAMPUS_OS_NOTIFICATIONS.
 */
(function () {
  'use strict';

  var cfg = window.CAMPUS_OS_NOTIFICATIONS;
  if (!cfg) return;

  var csrfMeta = document.querySelector('meta[name="csrf-token"]');
  var csrfToken = csrfMeta ? csrfMeta.content : '';

  var mode = cfg.mode === 'page' ? 'page' : 'shell';
  function isDesktop() {
    return window.matchMedia('(min-width: 1024px)').matches;
  }

  var POLL_MS = 60000;
  var DROPDOWN_LIMIT = 8;
  var PAGE_LIMIT = 20;

  var bell = document.getElementById('notif-bell');
  var badge = document.getElementById('notif-badge');
  var dropdown = document.getElementById('notif-dropdown');
  var dropdownList = document.getElementById('notif-dropdown-list');
  var dropdownMarkAll = document.getElementById('notif-mark-all');
  var pageList = document.getElementById('notif-page-list');
  var pageMore = document.getElementById('notif-page-more');
  var pageMoreBtn = document.getElementById('notif-page-more-btn');
  var pageMarkAll = document.getElementById('notif-page-mark-all');
  var pageCount = document.getElementById('notif-page-count');
  var pageStatus = document.getElementById('notif-page-status');

  // ---------- Utilities ----------
  function escapeHtml(s) {
    return String(s || '').replace(/[&<>"']/g, function (c) {
      return ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' })[c];
    });
  }

  function timeAgo(iso) {
    if (!iso) return '';
    var then = new Date(iso).getTime();
    if (isNaN(then)) return '';
    var secs = Math.floor((Date.now() - then) / 1000);
    if (secs < 60) return 'just now';
    var mins = Math.floor(secs / 60);
    if (mins < 60) return mins + 'm ago';
    var hrs = Math.floor(mins / 60);
    if (hrs < 24) return hrs + 'h ago';
    var days = Math.floor(hrs / 24);
    if (days < 7) return days + 'd ago';
    var weeks = Math.floor(days / 7);
    if (weeks < 5) return weeks + 'w ago';
    return new Date(iso).toLocaleDateString();
  }

  function clearNode(node) {
    while (node.firstChild) node.removeChild(node.firstChild);
  }

  function apiGet(url) {
    return fetch(url, { credentials: 'same-origin' }).then(function (res) {
      if (!res.ok) throw new Error('GET ' + url + ' -> ' + res.status);
      return res.json();
    });
  }

  function apiPost(url) {
    return fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: { 'X-CSRFToken': csrfToken }
    }).then(function (res) {
      if (!res.ok && res.status !== 204) {
        throw new Error('POST ' + url + ' -> ' + res.status);
      }
      if (res.status === 204) return null;
      return res.json().catch(function () { return null; });
    });
  }

  function readOneUrl(id) {
    return cfg.apiReadOne.replace('__ID__', encodeURIComponent(id));
  }

  // ---------- Badge + polling ----------
  function setBadge(count) {
    if (!badge) return;
    if (count > 0) {
      badge.textContent = count > 99 ? '99+' : String(count);
      badge.hidden = false;
    } else {
      badge.hidden = true;
      badge.textContent = '';
    }
  }

  function refreshUnreadCount() {
    return apiGet(cfg.apiUnreadCount).then(function (data) {
      setBadge(data.count || 0);
    }).catch(function (err) {
      console.warn('[notifications] unread count refresh failed', err);
    });
  }

  // ---------- Rendering ----------
  function renderItem(n, context) {
    var li = document.createElement('li');
    li.className = 'card notification-item' + (n.read_at ? '' : ' notification-item--unread');
    li.dataset.id = n.id;
    if (n.action_url) li.dataset.actionUrl = n.action_url;

    var wrap = document.createElement(n.action_url ? 'a' : 'div');
    wrap.className = 'notification-item__link';
    if (n.action_url) wrap.href = n.action_url;

    var top = document.createElement('div');
    top.className = 'notification-item__top';

    var title = document.createElement('h3');
    title.className = 'notification-item__title';
    title.textContent = n.title || '';
    top.appendChild(title);

    var meta = document.createElement('div');
    meta.className = 'notification-item__meta';
    var time = document.createElement('span');
    time.className = 'notification-item__time';
    time.textContent = timeAgo(n.created_at);
    meta.appendChild(time);

    wrap.appendChild(top);
    if (n.body) {
      var body = document.createElement('p');
      body.className = 'notification-item__body';
      body.textContent = n.body;
      wrap.appendChild(body);
    }
    wrap.appendChild(meta);
    li.appendChild(wrap);

    if (context === 'dropdown' || context === 'page') {
      li.addEventListener('click', function (ev) {
        if (!n.read_at) {
          n.read_at = new Date().toISOString();
          li.classList.remove('notification-item--unread');
          apiPost(readOneUrl(n.id))
            .then(function () { return refreshUnreadCount(); })
            .catch(function (err) { console.warn('[notifications] mark-read failed', err); });
        }
        if (!n.action_url) ev.preventDefault();
        if (context === 'dropdown') closeDropdown();
      });
    }

    return li;
  }

  function renderEmpty(container, message) {
    var wrap = document.createElement('div');
    wrap.className = 'empty notification-empty';
    wrap.innerHTML =
      '<div class="empty__icon">' +
      '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
      'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">' +
      '<path d="M6 8a6 6 0 0 1 12 0c0 7 3 9 3 9H3s3-2 3-9"/>' +
      '<path d="M10.3 21a1.94 1.94 0 0 0 3.4 0"/>' +
      '</svg></div>' +
      '<div class="empty__title">No notifications</div>' +
      '<div class="empty__body">' + escapeHtml(message || '') + '</div>';
    container.appendChild(wrap);
  }

  function renderLoading(container) {
    var wrap = document.createElement('div');
    wrap.className = 'empty';
    wrap.innerHTML =
      '<div class="skeleton skeleton--line" style="width:60%;margin:0 auto 8px;"></div>' +
      '<div class="skeleton skeleton--line" style="width:40%;margin:0 auto;"></div>';
    container.appendChild(wrap);
  }

  function renderError(container, message) {
    var wrap = document.createElement('div');
    wrap.className = 'empty notification-empty';
    wrap.innerHTML =
      '<div class="empty__title">Couldn\u2019t load notifications</div>' +
      '<div class="empty__body">' + escapeHtml(message || 'Try again in a moment.') + '</div>';
    container.appendChild(wrap);
  }

  // ---------- Dropdown ----------
  var dropdownLoaded = false;
  var outsideClickHandler = null;
  var escapeKeyHandler = null;

  function openDropdown() {
    if (!dropdown || !bell) return;
    dropdown.hidden = false;
    bell.setAttribute('aria-expanded', 'true');
    if (!dropdownLoaded) loadDropdown();

    escapeKeyHandler = function (ev) {
      if (ev.key === 'Escape') {
        ev.preventDefault();
        closeDropdown();
      }
    };
    outsideClickHandler = function (ev) {
      if (!dropdown || dropdown.hidden) return;
      if (dropdown.contains(ev.target)) return;
      if (bell && bell.contains(ev.target)) return;
      closeDropdown();
    };

    document.addEventListener('keydown', escapeKeyHandler);
    document.addEventListener('click', outsideClickHandler, true);
  }

  function closeDropdown() {
    if (!dropdown || !bell) return;
    dropdown.hidden = true;
    bell.setAttribute('aria-expanded', 'false');
    if (escapeKeyHandler) {
      document.removeEventListener('keydown', escapeKeyHandler);
      escapeKeyHandler = null;
    }
    if (outsideClickHandler) {
      document.removeEventListener('click', outsideClickHandler, true);
      outsideClickHandler = null;
    }
    bell.focus();
  }

  function loadDropdown() {
    if (!dropdownList) return;
    dropdownLoaded = true;
    clearNode(dropdownList);
    renderLoading(dropdownList);
    apiGet(cfg.apiList + '?limit=' + DROPDOWN_LIMIT).then(function (data) {
      clearNode(dropdownList);
      var items = data.notifications || [];
      if (items.length === 0) {
        renderEmpty(dropdownList, 'You\u2019re all caught up.');
        if (dropdownMarkAll) dropdownMarkAll.hidden = true;
        return;
      }
      items.forEach(function (n) {
        dropdownList.appendChild(renderItem(n, 'dropdown'));
      });
      if (dropdownMarkAll) {
        var hasUnread = items.some(function (n) { return !n.read_at; });
        dropdownMarkAll.hidden = !hasUnread;
      }
    }).catch(function () {
      clearNode(dropdownList);
      renderError(dropdownList, 'Couldn\u2019t load notifications.');
    });
  }

  function wireBell() {
    if (!bell) return;
    bell.addEventListener('click', function (ev) {
      if (!isDesktop()) return;
      if (!dropdown) return;
      ev.preventDefault();
      ev.stopPropagation();
      if (dropdown.hidden) {
        openDropdown();
      } else {
        closeDropdown();
      }
    });
  }

  function wireDropdownMarkAll() {
    if (!dropdownMarkAll) return;
    dropdownMarkAll.addEventListener('click', function (ev) {
      ev.stopPropagation();
      apiPost(cfg.apiReadAll).then(function () {
        if (dropdownList) {
          var unread = dropdownList.querySelectorAll('.notification-item--unread');
          for (var i = 0; i < unread.length; i++) {
            unread[i].classList.remove('notification-item--unread');
          }
        }
        dropdownMarkAll.hidden = true;
        return refreshUnreadCount();
      }).catch(function (err) {
        console.warn('[notifications] mark-all failed', err);
      });
    });
  }

  // ---------- Page mode ----------
  var pageState = {
    loaded: [],
    nextCursor: null,
    loading: false
  };

  function loadPage(reset) {
    if (!pageList || pageState.loading) return;
    pageState.loading = true;

    if (reset) {
      clearNode(pageList);
      pageState.loaded = [];
      pageState.nextCursor = null;
      if (pageStatus) clearNode(pageStatus);
      if (pageStatus) renderLoading(pageStatus);
      if (pageMore) pageMore.hidden = true;
    }

    var params = new URLSearchParams();
    params.set('limit', String(PAGE_LIMIT));
    if (pageState.nextCursor) {
      params.set('before', pageState.nextCursor.before);
      params.set('before_id', pageState.nextCursor.before_id);
    }

    apiGet(cfg.apiList + '?' + params.toString()).then(function (data) {
      if (pageStatus) clearNode(pageStatus);

      var items = data.notifications || [];
      pageState.loaded = pageState.loaded.concat(items);
      pageState.nextCursor = data.next_cursor;

      if (reset && items.length === 0) {
        renderEmpty(pageList, 'You\u2019re all caught up. Nothing new here.');
        if (pageMarkAll) pageMarkAll.hidden = true;
        if (pageCount) pageCount.textContent = '';
      } else {
        var frag = document.createDocumentFragment();
        items.forEach(function (n) { frag.appendChild(renderItem(n, 'page')); });
        pageList.appendChild(frag);

        var unread = pageState.loaded.filter(function (n) { return !n.read_at; }).length;
        if (pageCount) {
          pageCount.textContent = unread > 0 ? (unread + ' unread') : 'All caught up';
        }
        if (pageMarkAll) pageMarkAll.hidden = unread === 0;
      }

      if (pageMore) pageMore.hidden = !pageState.nextCursor;
    }).catch(function () {
      if (pageStatus) clearNode(pageStatus);
      if (reset) {
        clearNode(pageList);
        renderError(pageStatus || pageList, 'Couldn\u2019t load notifications.');
      }
    }).finally(function () {
      pageState.loading = false;
    });
  }

  function wirePage() {
    if (!pageList) return;

    loadPage(true);

    if (pageMoreBtn) {
      pageMoreBtn.addEventListener('click', function () { loadPage(false); });
    }

    if (pageMarkAll) {
      pageMarkAll.addEventListener('click', function () {
        apiPost(cfg.apiReadAll).then(function () {
          var unread = pageList.querySelectorAll('.notification-item--unread');
          for (var i = 0; i < unread.length; i++) {
            unread[i].classList.remove('notification-item--unread');
          }
          pageMarkAll.hidden = true;
          if (pageCount) pageCount.textContent = 'All caught up';
          return refreshUnreadCount();
        }).catch(function (err) {
          console.warn('[notifications] mark-all failed', err);
        });
      });
    }
  }

  // ---------- Boot ----------
  wireBell();
  wireDropdownMarkAll();

  if (badge || dropdown) {
    refreshUnreadCount();
    setInterval(refreshUnreadCount, POLL_MS);
  }

  if (mode === 'page') {
    wirePage();
  }

  // ---------- Push subscription (profile page only) ----------
  wirePushCard();
})();


// ═══════════════════════════════════════════════════════
// Push subscription management.
// Runs only when the profile page is loaded and the push
// card element exists.
// ═══════════════════════════════════════════════════════
function wirePushCard() {
  var card = document.getElementById('push-card');
  if (!card) return;

  var titleEl = document.getElementById('push-card-title');
  var bodyEl = document.getElementById('push-card-body');
  var buttonEl = document.getElementById('push-card-button');
  var statusEl = document.getElementById('push-card-status');

  var vapidEndpoint = card.dataset.vapidEndpoint;
  var subscribeEndpoint = card.dataset.subscribeEndpoint;
  var unsubscribeEndpoint = card.dataset.unsubscribeEndpoint;

  // --- Support detection ---
  var isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
  var standalone = window.matchMedia('(display-mode: standalone)').matches
    || window.navigator.standalone === true;

  var hasPush = 'serviceWorker' in navigator
    && 'PushManager' in window
    && 'Notification' in window;

  if (!hasPush) return;
  // iOS requires the PWA to be installed and opened as standalone.
  if (isIOS && !standalone) return;

  // Reveal the card; JS decides the exact state.
  card.style.display = '';

  var swReg = null;

  function showStatus(message, isError) {
    statusEl.textContent = message;
    statusEl.style.display = '';
    statusEl.style.color = isError ? 'var(--color-danger)' : 'var(--color-text-2)';
  }

  function clearStatus() {
    statusEl.textContent = '';
    statusEl.style.display = 'none';
  }

  function setSubscribed() {
    titleEl.textContent = 'Notifications are on';
    bodyEl.textContent = 'You\u2019ll get alerts about safety reports on your campus.';
    buttonEl.textContent = 'Disable notifications';
    buttonEl.classList.remove('btn--primary');
    buttonEl.classList.add('btn--ghost');
    buttonEl.disabled = false;
  }

  function setUnsubscribed() {
    titleEl.textContent = 'Enable notifications';
    bodyEl.textContent = 'Get alerts about safety reports on your campus, even when Campus OS is closed.';
    buttonEl.textContent = 'Enable notifications';
    buttonEl.classList.remove('btn--ghost');
    buttonEl.classList.add('btn--primary');
    buttonEl.disabled = false;
  }

  function urlBase64ToUint8Array(base64String) {
    var padding = '='.repeat((4 - (base64String.length % 4)) % 4);
    var base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/');
    var rawData = atob(base64);
    var outputArray = new Uint8Array(rawData.length);
    for (var i = 0; i < rawData.length; ++i) {
      outputArray[i] = rawData.charCodeAt(i);
    }
    return outputArray;
  }

  function postJSON(url, body) {
    return fetch(url, {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': csrfToken
      },
      body: JSON.stringify(body)
    }).then(function (res) {
      if (!res.ok) throw new Error(url + ' -> ' + res.status);
      return res.json().catch(function () { return null; });
    });
  }

  function initialise(reg) {
    swReg = reg;
    return reg.pushManager.getSubscription().then(function (existing) {
      if (existing) setSubscribed(); else setUnsubscribed();
    }).catch(function () {
      setUnsubscribed();
    });
  }

  var vapidKeyCache = null;

  function subscribe() {
    if (!swReg || !swReg.pushManager) {
      showStatus('Notifications are not available right now. Try reopening the app.', true);
      return;
    }

    buttonEl.disabled = true;
    clearStatus();

    // Step 1: get the VAPID key BEFORE asking permission, so the
    // subscribe() call can fire synchronously from the tap handler.
    var getKey = Promise.resolve(vapidKeyCache);
    if (!getKey) {
      getKey = fetch(vapidEndpoint, { credentials: 'same-origin' })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (!data || !data.key) throw new Error('VAPID key unavailable');
          vapidKeyCache = data.key;
          return vapidKeyCache;
        });
    }

    getKey.then(function (key) {
      // Step 2: request permission. On iOS this MUST be the first
      // await in the tap handler. The subscribe() call must follow
      // in the same synchronous continuation — no further awaits.
      return Notification.requestPermission().then(function (permission) {
        if (permission !== 'granted') {
          showStatus('Permission was not granted. You can enable it in your browser settings.', true);
          buttonEl.disabled = false;
          return null;
        }

        // Step 3: subscribe. This call must happen immediately after
        // the permission resolves — no awaits in between.
        return swReg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(key)
        }).then(function (subscription) {
          // Step 4: persist the subscription. This CAN be async.
          var json = subscription.toJSON();
          return postJSON(subscribeEndpoint, {
            endpoint: json.endpoint,
            keys: {
              p256dh: json.keys.p256dh,
              auth: json.keys.auth
            }
          }).then(function () {
            setSubscribed();
            showStatus('You\u2019re subscribed on this device.', false);
          });
        });
      });
    }).catch(function (err) {
      console.warn('[push] subscribe failed', err);
      showStatus('Couldn\u2019t enable notifications. Try again in a moment.', true);
      buttonEl.disabled = false;
    });
  }  var vapidKeyCache = null;

  function subscribe() {
    if (!swReg || !swReg.pushManager) {
      showStatus('Notifications are not available right now. Try reopening the app.', true);
      return;
    }

    buttonEl.disabled = true;
    clearStatus();

    // Step 1: get the VAPID key BEFORE asking permission, so the
    // subscribe() call can fire synchronously from the tap handler.
    var getKey = Promise.resolve(vapidKeyCache);
    if (!getKey) {
      getKey = fetch(vapidEndpoint, { credentials: 'same-origin' })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (!data || !data.key) throw new Error('VAPID key unavailable');
          vapidKeyCache = data.key;
          return vapidKeyCache;
        });
    }

    getKey.then(function (key) {
      // Step 2: request permission. On iOS this MUST be the first
      // await in the tap handler. The subscribe() call must follow
      // in the same synchronous continuation — no further awaits.
      return Notification.requestPermission().then(function (permission) {
        if (permission !== 'granted') {
          showStatus('Permission was not granted. You can enable it in your browser settings.', true);
          buttonEl.disabled = false;
          return null;
        }

        // Step 3: subscribe. This call must happen immediately after
        // the permission resolves — no awaits in between.
        return swReg.pushManager.subscribe({
          userVisibleOnly: true,
          applicationServerKey: urlBase64ToUint8Array(key)
        }).then(function (subscription) {
          // Step 4: persist the subscription. This CAN be async.
          var json = subscription.toJSON();
          return postJSON(subscribeEndpoint, {
            endpoint: json.endpoint,
            keys: {
              p256dh: json.keys.p256dh,
              auth: json.keys.auth
            }
          }).then(function () {
            setSubscribed();
            showStatus('You\u2019re subscribed on this device.', false);
          });
        });
      });
    }).catch(function (err) {
      console.warn('[push] subscribe failed', err);
      showStatus('Couldn\u2019t enable notifications. Try again in a moment.', true);
      buttonEl.disabled = false;
    });
  }

  function unsubscribe() {
    buttonEl.disabled = true;
    clearStatus();

    swReg.pushManager.getSubscription().then(function (existing) {
      if (!existing) {
        setUnsubscribed();
        buttonEl.disabled = false;
        return;
      }
      var endpoint = existing.endpoint;
      return existing.unsubscribe().then(function () {
        return postJSON(unsubscribeEndpoint, { endpoint: endpoint });
      }).then(function () {
        setUnsubscribed();
        showStatus('Notifications turned off on this device.', false);
      });
    }).catch(function (err) {
      console.warn('[push] unsubscribe failed', err);
      showStatus('Couldn\u2019t turn off notifications. Try again.', true);
      buttonEl.disabled = false;
    });
  }

  buttonEl.addEventListener('click', function () {
    if (buttonEl.textContent.indexOf('Disable') === 0) unsubscribe();
    else subscribe();
  });

  navigator.serviceWorker.ready.then(initialise).catch(function (err) {
    console.warn('[push] service worker not ready', err);
    showStatus('Notifications are not available right now.', true);
  });
}