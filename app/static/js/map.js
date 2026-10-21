/* Campus OS — Mapbox GL map layer.
   Vanilla JS, no framework. */
(function () {
    const cfg = window.CAMPUS_OS;
    const container = document.getElementById('map');
    if (!cfg || !container || !window.mapboxgl) return;
    if (!cfg.mapboxToken) {
        container.innerHTML = '<div style="padding:24px;color:#667085;">Mapbox token not configured. Set MAPBOX_TOKEN in .env and restart Flask.</div>';
        return;
    }

    mapboxgl.accessToken = cfg.mapboxToken;

    // TEMPORARY FALLBACK: UNILORIN Main Campus center.
    //
    // Used only when the selected campus has no lat/lng coordinates yet
    // (Phase 3.3 added nullable coordinate columns; campuses without
    // verified coordinates are NULL). A follow-up phase should provide
    // per-campus defaults or a "no data yet" message instead of silently
    // centering on an unrelated campus.
    //
    // Order is [lng, lat] — Mapbox's center convention.
    const FALLBACK_CENTER = [4.6736, 8.4826];
    const DEFAULT_ZOOM = 15;

    // Prefer the current campus's verified coordinates when present.
    // Any missing/invalid value triggers the fallback.
    function resolveInitialCenter() {
        const lat = cfg.campusLat;
        const lng = cfg.campusLng;
        if (
            typeof lat === 'number' && typeof lng === 'number' &&
            Number.isFinite(lat) && Number.isFinite(lng) &&
            lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180
        ) {
            return [lng, lat];  // Mapbox expects [lng, lat]
        }
        return FALLBACK_CENTER;
    }

    const map = new mapboxgl.Map({
        container: 'map',
        style: 'mapbox://styles/mapbox/streets-v12',
        center: resolveInitialCenter(),
        zoom: DEFAULT_ZOOM,
        attributionControl: true,
    });
    map.addControl(new mapboxgl.NavigationControl(), 'top-right');
    map.addControl(new mapboxgl.GeolocateControl({
        positionOptions: { enableHighAccuracy: true },
        trackUserLocation: false,
    }), 'top-right');

    const popup = new mapboxgl.Popup({ closeButton: true, offset: 12 });

    // ── Locations layer ────────────────────────────────
    async function loadLocations() {
        const cat = document.getElementById('map-category')?.value || '';
        const q = document.getElementById('map-search')?.value || '';
        const url = new URL(cfg.apiLocations, window.location.origin);
        if (cat) url.searchParams.set('category', cat);
        if (q) url.searchParams.set('q', q);

        const res = await fetch(url, { credentials: 'same-origin' });
        const data = await res.json();
        return data.locations || [];
    }

    async function loadPulse() {
        const url = new URL(cfg.apiPulse, window.location.origin);
        const res = await fetch(url, { credentials: 'same-origin' });
        const data = await res.json();
        return data.reports || [];
    }

    function renderMarkers(locations, reports) {
        // Clear previous
        document.querySelectorAll('.cos-marker').forEach(el => el.remove());

        locations.forEach(loc => {
            if (loc.lat == null || loc.lng == null) return;
            const el = document.createElement('div');
            el.className = 'cos-marker';
            el.style.cssText = 'width:14px;height:14px;border-radius:50%;background:#243B6B;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.3);cursor:pointer;';
            // data-name is read by the CSS tooltip. We deliberately avoid
            // `title` so the OS tooltip doesn't compete with our styled one.
            el.dataset.name = loc.name;
            // Focusable so keyboard users can tab to markers.
            el.tabIndex = 0;
            el.setAttribute('role', 'button');
            el.setAttribute('aria-label', loc.name);

            const openPopup = () => {
                const detailUrl = '/map/location/' + loc.id;
                popup.setLngLat([loc.lng, loc.lat]).setHTML(
                    '<strong>' + escapeHtml(loc.name) + '</strong><br>' +
                    '<small>' + escapeHtml(loc.category) + '</small>' +
                    (loc.description ? '<br>' + escapeHtml(loc.description) : '') +
                    '<br><a href="' + detailUrl + '">Open details</a>'
                ).addTo(map);
            };

            new mapboxgl.Marker(el)
                .setLngLat([loc.lng, loc.lat])
                .addTo(map)
                .getElement().addEventListener('click', openPopup);

            // Keyboard equivalent of clicking: Enter or Space opens the popup.
            el.addEventListener('keydown', (ev) => {
                if (ev.key === 'Enter' || ev.key === ' ') {
                    ev.preventDefault();
                    openPopup();
                }
            });
        });

        const showPulse = document.getElementById('toggle-pulse')?.checked;
        if (!showPulse) return;

        reports.forEach(r => {
            if (r.lat == null || r.lng == null) return;
            const el = document.createElement('div');
            el.className = 'cos-marker';
            el.style.cssText = 'width:12px;height:12px;border-radius:50%;background:#19C3E6;border:2px solid #fff;cursor:pointer;';
            el.title = r.category;

            new mapboxgl.Marker(el)
                .setLngLat([r.lng, r.lat])
                .addTo(map)
                .getElement().addEventListener('click', () => {
                    popup.setLngLat([r.lng, r.lat]).setHTML(
                        '<strong>' + escapeHtml(r.category.replace(/_/g, ' ')) + '</strong><br>' +
                        '<small>confidence: ' + escapeHtml(r.confidence) + '</small><br>' +
                        '<a href="' + r.url + '">Open report</a>'
                    ).addTo(map);
                });
        });
    }

    function escapeHtml(s) {
        return String(s || '').replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        })[c]);
    }

    async function refresh() {
        const [locs, reports] = await Promise.all([loadLocations(), loadPulse()]);
        renderMarkers(locs, reports);
    }

    map.on('load', refresh);

    function debounce(fn, ms) {
        let t;
        return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
    }

    // ── Polling / re-entrancy ───────────────────────────
    // The map refreshes:
    //   - once on load (existing),
    //   - on any user interaction with search/category/pulse (existing),
    //   - on a 60s timer while the tab is visible (new),
    //   - immediately when the tab becomes visible again (new).
    //
    // Re-entrancy rules:
    //   - At most one network refresh in flight at a time.
    //   - Automatic refreshes (timer, visibility) are skipped while one
    //     is in flight — the next tick or the next focus will retry.
    //   - User-initiated refreshes (search, category, pulse) are never
    //     lost: if one is in flight, we set a pending flag and re-run
    //     once the in-flight call resolves.
    const POLL_INTERVAL_MS = 60000;
    let refreshInFlight = false;
    let pendingUserRefresh = false;
    let pollTimer = null;

    function schedulePoll() {
        if (pollTimer !== null) return;
        pollTimer = setInterval(() => {
            if (document.visibilityState === 'visible') {
                refresh({ userInitiated: false });
            }
        }, POLL_INTERVAL_MS);
    }

    function stopPoll() {
        if (pollTimer !== null) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
    }

    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') {
            refresh({ userInitiated: false });
            schedulePoll();
        } else {
            stopPoll();
        }
    });

    // Belt-and-braces: clear the timer on navigation away.
    window.addEventListener('pagehide', stopPoll);

    // Start the poll once the map is loaded. The map's own `load`
    // handler already kicks off the first refresh.
    map.on('load', schedulePoll);

    // Expose the guard-aware refresh by wrapping the existing one.
    // The existing `refresh()` becomes `_refreshOnce()` so it can be
    // called internally by the wrapper.
    const _refreshOnce = refresh;

    refresh = function (opts) {
        const userInitiated = !!(opts && opts.userInitiated);

        if (refreshInFlight) {
            if (userInitiated) pendingUserRefresh = true;
            return;
        }

        refreshInFlight = true;
        _refreshOnce()
            .catch((err) => {
                // Swallow network errors — the previous marker set stays
                // visible. The next tick will retry.
                console.warn('map refresh failed', err);
            })
            .finally(() => {
                refreshInFlight = false;
                if (pendingUserRefresh) {
                    pendingUserRefresh = false;
                    refresh({ userInitiated: true });
                }
            });
    };

    // Rewire the three existing interaction handlers to mark their
    // refreshes as user-initiated, so they are never dropped.
    document.getElementById('map-search')?.addEventListener('input', debounce(() => refresh({ userInitiated: true }), 300));
    document.getElementById('map-category')?.addEventListener('change', () => refresh({ userInitiated: true }));
    document.getElementById('toggle-pulse')?.addEventListener('change', () => refresh({ userInitiated: true }));
})();