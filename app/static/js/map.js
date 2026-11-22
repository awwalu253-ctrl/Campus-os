/* Campus OS — Mapbox GL map layer.
   Vanilla JS, no framework.
   Phase 3: Supercluster-based clustering for campus locations.
   Pulse markers remain un-clustered and rendered exactly as before. */
(function () {
    const cfg = window.CAMPUS_OS;
    const container = document.getElementById('map');
    if (!cfg || !container || !window.mapboxgl) return;
    if (!cfg.mapboxToken) {
        container.innerHTML = '<div style="padding:24px;color:#667085;">Mapbox token not configured. Set MAPBOX_TOKEN in .env and restart Flask.</div>';
        return;
    }

    mapboxgl.accessToken = cfg.mapboxToken;

    const FALLBACK_CENTER = [4.6736, 8.4826];
    const DEFAULT_ZOOM = 15;

    function resolveInitialCenter() {
        const lat = cfg.campusLat;
        const lng = cfg.campusLng;
        if (
            typeof lat === 'number' && typeof lng === 'number' &&
            Number.isFinite(lat) && Number.isFinite(lng) &&
            lat >= -90 && lat <= 90 && lng >= -180 && lng <= 180
        ) {
            return [lng, lat];
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

    // ── Search / filter state ──────────────────────────
    function currentSearch() {
        return (document.getElementById('map-search')?.value || '').trim();
    }
    function currentCategory() {
        return (document.getElementById('map-category')?.value || '').trim();
    }
    function filtersActive() {
        return currentSearch().length > 0 || currentCategory().length > 0;
    }

    // ── Data loading (unchanged endpoints) ─────────────
    async function loadLocations() {
        const cat = currentCategory();
        const q = currentSearch();
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

    function escapeHtml(s) {
        return String(s || '').replace(/[&<>"']/g, c => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        })[c]);
    }

    // ── Location rendering via Supercluster ────────────
    // Active markers keyed by unique id, so we can diff on refresh.
    //   individual location -> key: "loc:<location.id>"
    //   cluster            -> key: "cluster:<cluster_id>"
    const activeLocationMarkers = new Map();   // key -> { marker, kind }

    let superclusterIndex = null;
    let lastLocationPayloadSignature = null;

    function buildSuperclusterIndex(locations) {
        const features = locations.map(loc => ({
            type: 'Feature',
            properties: { ...loc },   // all fields preserved for popup
            geometry: { type: 'Point', coordinates: [loc.lng, loc.lat] },
        }));
        const index = new window.Supercluster({
            radius: 60,
            maxZoom: 18,
            minPoints: 2,
        });
        index.load(features);
        return index;
    }

    function locationMarkerElement(loc) {
        const el = document.createElement('div');
        el.className = 'cos-location-marker';
        el.style.cssText = 'width:14px;height:14px;border-radius:50%;background:#243B6B;border:2px solid #fff;box-shadow:0 1px 3px rgba(0,0,0,.3);cursor:pointer;';
        el.dataset.name = loc.name;
        el.tabIndex = 0;
        el.setAttribute('role', 'button');
        el.setAttribute('aria-label', loc.name);
        return el;
    }

    function clusterMarkerElement(feature) {
        const count = feature.properties.point_count;
        const el = document.createElement('div');
        el.className = 'cos-cluster';
        el.style.cssText = 'width:32px;height:32px;border-radius:50%;background:#243B6B;color:#fff;font-size:12px;font-weight:600;display:flex;align-items:center;justify-content:center;border:2px solid #fff;box-shadow:0 1px 4px rgba(0,0,0,.35);cursor:pointer;';
        el.textContent = count;
        el.tabIndex = 0;
        el.setAttribute('role', 'button');
        el.setAttribute('aria-label', `Cluster of ${count} locations`);
        return el;
    }

    function openLocationPopup(loc, lngLat) {
        const detailUrl = '/map/location/' + loc.id;
        popup.setLngLat(lngLat).setHTML(
            '<strong>' + escapeHtml(loc.name) + '</strong><br>' +
            '<small>' + escapeHtml(loc.category) + '</small>' +
            (loc.description ? '<br>' + escapeHtml(loc.description) : '') +
            '<br><a href="' + detailUrl + '">Open details</a>'
        ).addTo(map);
    }

    function wireLocationMarker(markerEl, loc, lngLat) {
        const open = () => openLocationPopup(loc, lngLat);
        markerEl.addEventListener('click', open);
        markerEl.addEventListener('keydown', (ev) => {
            if (ev.key === 'Enter' || ev.key === ' ') {
                ev.preventDefault();
                open();
            }
        });
    }

    function wireClusterMarker(markerEl, feature) {
        const expand = () => {
            const expansionZoom = superclusterIndex.getClusterExpansionZoom(feature.properties.cluster_id);
            const coords = feature.geometry.coordinates;
            map.flyTo({ center: coords, zoom: expansionZoom });
            const statusEl = document.getElementById('map-status');
            if (statusEl) {
                statusEl.textContent = `Expanded cluster of ${feature.properties.point_count} locations.`;
                statusEl.hidden = false;
                // Hide again shortly after; the regular refresh will repopulate.
                setTimeout(() => { statusEl.hidden = true; statusEl.textContent = ''; }, 2500);
            }
        };
        markerEl.addEventListener('click', expand);
        markerEl.addEventListener('keydown', (ev) => {
            if (ev.key === 'Enter' || ev.key === ' ') {
                ev.preventDefault();
                expand();
            }
        });
    }

    function clearLocationMarkers() {
        activeLocationMarkers.forEach(({ marker }) => marker.remove());
        activeLocationMarkers.clear();
    }

    // Compute the new set of markers to show, diff against existing.
    function refreshLocationMarkers() {
        if (!superclusterIndex) {
            clearLocationMarkers();
            return;
        }
        const zoom = Math.floor(map.getZoom());
        const bounds = map.getBounds();
        const bbox = [
            bounds.getWest(), bounds.getSouth(),
            bounds.getEast(), bounds.getNorth(),
        ];
        const clusters = superclusterIndex.getClusters(bbox, zoom);

        const nextKeys = new Set();

        clusters.forEach(feature => {
            const [lng, lat] = feature.geometry.coordinates;
            const isCluster = feature.properties.cluster === true;

            const key = isCluster
                ? `cluster:${feature.properties.cluster_id}`
                : `loc:${feature.properties.id}`;

            nextKeys.add(key);

            if (activeLocationMarkers.has(key)) {
                // Already rendered — do nothing (avoid flicker).
                return;
            }

            if (isCluster) {
                const el = clusterMarkerElement(feature);
                wireClusterMarker(el, feature);
                const m = new mapboxgl.Marker(el).setLngLat([lng, lat]).addTo(map);
                activeLocationMarkers.set(key, { marker: m, kind: 'cluster' });
            } else {
                const loc = feature.properties;
                const el = locationMarkerElement(loc);
                wireLocationMarker(el, loc, [lng, lat]);
                const m = new mapboxgl.Marker(el).setLngLat([lng, lat]).addTo(map);
                activeLocationMarkers.set(key, { marker: m, kind: 'location' });
            }
        });

        // Remove markers that are no longer in the current view.
        activeLocationMarkers.forEach((entry, key) => {
            if (!nextKeys.has(key)) {
                entry.marker.remove();
                activeLocationMarkers.delete(key);
            }
        });
    }

    // Direct (non-clustered) rendering for small filtered results.
    function renderLocationMarkersDirect(locations) {
        clearLocationMarkers();
        locations.forEach(loc => {
            if (loc.lat == null || loc.lng == null) return;
            const el = locationMarkerElement(loc);
            wireLocationMarker(el, loc, [loc.lng, loc.lat]);
            const m = new mapboxgl.Marker(el).setLngLat([loc.lng, loc.lat]).addTo(map);
            activeLocationMarkers.set(`loc:${loc.id}`, { marker: m, kind: 'location' });
        });
    }

    // ── Pulse markers (unchanged behavior) ────────────
    const activePulseMarkers = [];

    function clearPulseMarkers() {
        activePulseMarkers.forEach(m => m.remove());
        activePulseMarkers.length = 0;
    }

    function renderPulseMarkers(reports) {
        clearPulseMarkers();
        const showPulse = document.getElementById('toggle-pulse')?.checked;
        if (!showPulse) return;

        reports.forEach(r => {
            if (r.lat == null || r.lng == null) return;
            const el = document.createElement('div');
            el.className = 'cos-pulse-marker';
            el.style.cssText = 'width:12px;height:12px;border-radius:50%;background:#19C3E6;border:2px solid #fff;cursor:pointer;';
            el.title = r.category;

            const marker = new mapboxgl.Marker(el)
                .setLngLat([r.lng, r.lat])
                .addTo(map);

            marker.getElement().addEventListener('click', () => {
                popup.setLngLat([r.lng, r.lat]).setHTML(
                    '<strong>' + escapeHtml(r.category.replace(/_/g, ' ')) + '</strong><br>' +
                    '<small>confidence: ' + escapeHtml(r.confidence) + '</small><br>' +
                    '<a href="' + r.url + '">Open report</a>'
                ).addTo(map);
            });

            activePulseMarkers.push(marker);
        });
    }

    // ── Status line (unchanged) ───────────────────────
    function updateStatus(count) {
        const el = document.getElementById('map-status');
        if (!el) return;
        const hasFilters = filtersActive();
        let text = '';
        if (count > 0 && hasFilters) {
            text = count === 1
                ? '1 location matches your search.'
                : `${count} locations match your search.`;
        } else if (count === 0 && hasFilters) {
            text = 'No locations match your search. Try a different term.';
        } else if (count === 0 && !hasFilters) {
            text = 'No locations on this campus yet.';
        }
        if (text) {
            el.textContent = text;
            el.hidden = false;
        } else {
            el.textContent = '';
            el.hidden = true;
        }
    }

    function updateStatusError() {
        const el = document.getElementById('map-status');
        if (!el) return;
        el.textContent = "Couldn't load locations. Retrying…";
        el.hidden = false;
    }

    // ── Refresh orchestration ─────────────────────────
    async function loadAndRender() {
        const [locs, reports] = await Promise.all([loadLocations(), loadPulse()]);

        // Locations
        if (filtersActive() && locs.length <= 20) {
            // Bypass clustering for small filtered results.
            superclusterIndex = null;
            lastLocationPayloadSignature = null;
            renderLocationMarkersDirect(locs);
        } else {
            const signature = locs.length + '|' + locs.map(l => l.id).join(',');
            if (signature !== lastLocationPayloadSignature) {
                superclusterIndex = buildSuperclusterIndex(locs);
                lastLocationPayloadSignature = signature;
                clearLocationMarkers();   // payload changed; full reset
            }
            refreshLocationMarkers();
        }

        // Pulse (always fresh render, unchanged behavior)
        renderPulseMarkers(reports);

        updateStatus(locs.length);
    }

    map.on('load', loadAndRender);

    // Re-render clusters on map movement (not on every pan frame).
    map.on('moveend', () => {
        if (superclusterIndex) refreshLocationMarkers();
    });

    function debounce(fn, ms) {
        let t;
        return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
    }

    // ── Polling / re-entrancy (unchanged semantics) ───
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

    window.addEventListener('pagehide', stopPoll);
    map.on('load', schedulePoll);

    const _refreshOnce = loadAndRender;

    function refresh(opts) {
        const userInitiated = !!(opts && opts.userInitiated);
        if (refreshInFlight) {
            if (userInitiated) pendingUserRefresh = true;
            return;
        }
        refreshInFlight = true;

        const statusEl = document.getElementById('map-status');
        if (statusEl) {
            statusEl.hidden = true;
            statusEl.textContent = '';
        }

        _refreshOnce()
            .catch((err) => {
                console.warn('map refresh failed', err);
                updateStatusError();
            })
            .finally(() => {
                refreshInFlight = false;
                if (pendingUserRefresh) {
                    pendingUserRefresh = false;
                    refresh({ userInitiated: true });
                }
            });
    }

    document.getElementById('map-search')?.addEventListener('input', debounce(() => refresh({ userInitiated: true }), 300));
    document.getElementById('map-category')?.addEventListener('change', () => refresh({ userInitiated: true }));
    document.getElementById('toggle-pulse')?.addEventListener('change', () => refresh({ userInitiated: true }));
})();