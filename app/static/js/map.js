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

    // UNILORIN Main Campus default center
    const DEFAULT_CENTER = [4.6736, 8.4826];
    const DEFAULT_ZOOM = 15;

    const map = new mapboxgl.Map({
        container: 'map',
        style: 'mapbox://styles/mapbox/streets-v12',
        center: DEFAULT_CENTER,
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
            el.title = loc.name;

            new mapboxgl.Marker(el)
                .setLngLat([loc.lng, loc.lat])
                .addTo(map)
                .getElement().addEventListener('click', () => {
                    const detailUrl = '/map/location/' + loc.id;
                    popup.setLngLat([loc.lng, loc.lat]).setHTML(
                        '<strong>' + escapeHtml(loc.name) + '</strong><br>' +
                        '<small>' + escapeHtml(loc.category) + '</small>' +
                        (loc.description ? '<br>' + escapeHtml(loc.description) : '') +
                        '<br><a href="' + detailUrl + '">Open details</a>'
                    ).addTo(map);
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

    document.getElementById('map-search')?.addEventListener('input', debounce(refresh, 300));
    document.getElementById('map-category')?.addEventListener('change', refresh);
    document.getElementById('toggle-pulse')?.addEventListener('change', refresh);

    function debounce(fn, ms) {
        let t;
        return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
    }
})();