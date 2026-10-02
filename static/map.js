// Map view.
// Zoomed out: one bubble per town. Zoomed in: price pins for the part of the map on screen,
// fetched from the server as the map moves, with overlapping pins grouped into numbered circles.

(function() {
    const mapEl = document.getElementById('map');
    if (typeof L === 'undefined') {
        // Leaflet didn't load (offline, or the CDN is blocked)
        mapEl.hidden = true;
        document.getElementById('town-button').hidden = true;
        document.getElementById('map-fallback').hidden = false;
        return;
    }

    const data = JSON.parse(document.getElementById('map-data').textContent);
    const BOTSWANA = [[-26.9, 20.0], [-17.8, 29.4]];
    const PIN_ZOOM = 11;        // from this zoom level, show individual properties
    const TOWN_ZOOM = 13;       // zoom used when opening a town
    const FOCUS_ZOOM = 16;      // zoom used when opening one property
    const MAX_LIST_ROWS = 60;
    const STORAGE_KEY = 'rentme.mapTown';

    const listEl = document.getElementById('map-list');
    const statusEl = document.getElementById('map-status');
    const chooser = document.getElementById('town-chooser');
    const townButton = document.getElementById('town-button');
    const townButtonLabel = document.getElementById('town-button-label');
    const card = document.getElementById('map-card');
    const cardPhoto = document.getElementById('map-card-photo');

    const formatPrice = price => 'P' + Number(price).toLocaleString('en-US');
    const townCentre = name => data.townCentres.find(t => t.name === name);

    // The visitor's last town. Storage can be unavailable (private windows), so never rely on it.
    function rememberedTown() {
        try { return townCentre(localStorage.getItem(STORAGE_KEY)); } catch (e) { return undefined; }
    }
    function rememberTown(name) {
        try { localStorage.setItem(STORAGE_KEY, name); } catch (e) { /* not saved; the map still works */ }
    }

    // ---------- Map and layers ----------

    const map = L.map(mapEl, { zoomControl: false, minZoom: 5, maxBoundsViscosity: 0.6 });
    map.setMaxBounds([[-30.5, 15.5], [-14.5, 33.5]]);
    L.control.zoom({ position: 'topright' }).addTo(map);
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    // Marker contents are built with DOM methods so listing text is never treated as HTML
    function el(tag, className, text) {
        const node = document.createElement(tag);
        if (className) node.className = className;
        if (text !== undefined) node.textContent = text;
        return node;
    }

    function pinIcon(pin, active) {
        const classes = 'rm-price-pin' + (active ? ' active' : '') + (pin.exact ? '' : ' approx');
        return L.divIcon({ className: 'rm-pin-anchor', html: el('span', classes, formatPrice(pin.price)), iconSize: [0, 0] });
    }

    function bubbleIcon(count, label) {
        const bubble = el('span', 'rm-town-pin');
        bubble.append(el('strong', '', count));
        if (label) bubble.append(el('span', '', label));
        return L.divIcon({ className: 'rm-pin-anchor', html: bubble, iconSize: [0, 0] });
    }

    const townLayer = L.layerGroup();
    // Grouping needs the markercluster plugin; without it the pins still show, just ungrouped
    const pinLayer = L.markerClusterGroup
        ? L.markerClusterGroup({
            showCoverageOnHover: false,
            maxClusterRadius: 48,
            iconCreateFunction: cluster => bubbleIcon(cluster.getChildCount())
        })
        : L.layerGroup();

    data.towns.forEach(town => {
        L.marker([town.lat, town.lng], {
            icon: bubbleIcon(town.count, town.name),
            title: `${town.count} in ${town.name}`,
            keyboard: true
        }).on('click', () => openTown(town.name)).addTo(townLayer);
    });

    let pins = [];              // pins currently loaded for the view
    let markers = {};
    let selectedId = null;
    let pendingSelect = data.focus ? data.focus.id : null;
    let loadedBounds = null;    // area the loaded pins cover
    let loadedComplete = false; // false when the server held some back
    let request = null;

    // ---------- Town chooser ----------

    function openChooser() {
        chooser.hidden = false;
        const first = chooser.querySelector('.rm-town-option') || document.getElementById('town-all');
        first.focus();
    }
    function closeChooser() {
        chooser.hidden = true;
        townButton.focus();
    }
    function openTown(name, animate = true) {
        const town = townCentre(name);
        if (!town) return;
        rememberTown(name);
        townButtonLabel.textContent = name;
        chooser.hidden = true;
        if (animate) {
            map.flyTo([town.lat, town.lng], TOWN_ZOOM, { duration: 0.8 });
        } else {
            map.setView([town.lat, town.lng], TOWN_ZOOM);
        }
    }

    townButton.addEventListener('click', openChooser);
    document.getElementById('town-chooser-close').addEventListener('click', closeChooser);
    chooser.addEventListener('click', e => { if (e.target === chooser) closeChooser(); });
    chooser.addEventListener('keydown', e => { if (e.key === 'Escape') closeChooser(); });
    chooser.querySelectorAll('.rm-town-option').forEach(button => {
        button.addEventListener('click', () => openTown(button.dataset.town));
    });
    document.getElementById('town-all').addEventListener('click', () => {
        chooser.hidden = true;
        townButtonLabel.textContent = 'Choose a town';
        map.flyToBounds(BOTSWANA, { duration: 0.8 });
    });

    // ---------- Loading pins for the visible area ----------

    function showStatus(text) {
        statusEl.textContent = text || '';
        statusEl.hidden = !text;
    }

    function refresh() {
        if (map.getZoom() < PIN_ZOOM) {
            if (request) request.abort();
            map.removeLayer(pinLayer);
            map.addLayer(townLayer);
            loadedBounds = null;
            showStatus('');
            renderTownList();
            return;
        }
        map.removeLayer(townLayer);
        map.addLayer(pinLayer);

        // Moving around inside an area that's already fully loaded needs no new request
        if (loadedBounds && loadedComplete && loadedBounds.contains(map.getBounds())) {
            renderPinList();
            return;
        }
        loadPins();
    }

    function loadPins() {
        if (request) request.abort();
        request = new AbortController();
        const bounds = map.getBounds().pad(0.25);
        const params = new URLSearchParams(window.location.search);
        params.delete('page');
        params.delete('focus');
        params.set('bbox', [bounds.getSouth(), bounds.getWest(), bounds.getNorth(), bounds.getEast()]
            .map(v => v.toFixed(5)).join(','));

        fetch(`${data.pinsUrl}?${params}`, { signal: request.signal })
            .then(response => {
                if (!response.ok) throw new Error('Could not load properties');
                return response.json();
            })
            .then(result => {
                pins = result.pins;
                loadedBounds = bounds;
                loadedComplete = !result.truncated;
                drawPins();
                renderPinList();
                showStatus(result.truncated
                    ? `Showing ${result.pins.length} of ${result.total} here. Zoom in to see the rest.`
                    : '');
                if (pendingSelect !== null) {
                    const id = pendingSelect;
                    pendingSelect = null;
                    select(id);
                }
            })
            .catch(error => {
                if (error.name === 'AbortError') return;
                showStatus("Couldn't load properties. Check your connection and move the map to try again.");
            });
    }

    function drawPins() {
        pinLayer.clearLayers();
        markers = {};
        const layers = pins.map(pin => {
            const marker = L.marker([pin.lat, pin.lng], {
                icon: pinIcon(pin, pin.id === selectedId),
                title: `${pin.title}, ${formatPrice(pin.price)} per month`,
                keyboard: true
            }).on('click', () => select(pin.id));
            markers[pin.id] = marker;
            return marker;
        });
        if (pinLayer.addLayers) {
            pinLayer.addLayers(layers);
        } else {
            layers.forEach(marker => pinLayer.addLayer(marker));
        }
        // The picked property may have moved out of the loaded area
        if (selectedId !== null && !markers[selectedId]) clearSelection();
    }

    // ---------- Side list (wide screens) ----------

    function listMessage(text) {
        listEl.replaceChildren(el('p', 'text-muted p-3 mb-0', text));
    }

    function renderTownList() {
        if (!data.towns.length) {
            listMessage('No properties match. Try removing a filter.');
            return;
        }
        const rows = [...data.towns].sort((a, b) => b.count - a.count).map(town => {
            const row = el('button', 'rm-row rm-map-row');
            row.type = 'button';
            const main = el('span', 'rm-row-main');
            main.append(el('strong', 'd-block', town.name),
                        el('span', 'text-muted small', `${town.count} ${town.count === 1 ? 'property' : 'properties'}`));
            row.append(el('span', 'rm-avatar', town.count), main);
            row.addEventListener('click', () => openTown(town.name));
            return row;
        });
        listEl.replaceChildren(el('p', 'text-muted small px-1 mb-0', 'Choose a town to see its properties.'), ...rows);
    }

    function renderPinList() {
        const view = map.getBounds();
        const visible = pins.filter(pin => view.contains([pin.lat, pin.lng]));
        if (!visible.length) {
            listMessage('No properties in this part of the map. Move the map, zoom out, or choose another town.');
            return;
        }
        const rows = visible.slice(0, MAX_LIST_ROWS).map(pin => {
            const row = el('button', 'rm-row rm-map-row' + (pin.id === selectedId ? ' active' : ''));
            row.type = 'button';
            row.dataset.pinId = pin.id;

            const photo = el('img', 'rm-row-thumb');
            photo.alt = '';
            photo.loading = 'lazy';
            photo.onerror = () => { photo.onerror = null; photo.src = data.defaultPhoto; };
            photo.src = pin.photo;

            const details = el('span', 'property-details');
            const town = el('span', 'property-detail-item');
            town.append(el('i', 'fas fa-map-marker-alt'), pin.town);
            const beds = el('span', 'property-detail-item');
            beds.append(el('i', 'fas fa-bed'), String(pin.bedrooms));
            details.append(town, beds);

            const price = el('span', 'property-price', formatPrice(pin.price) + ' ');
            price.append(el('small', '', '/ month'));

            const main = el('span', 'rm-row-main');
            main.append(el('strong', 'd-block', pin.title), details, price);
            row.append(photo, main);
            row.addEventListener('click', () => select(pin.id));
            return row;
        });
        const heading = el('p', 'text-muted small px-1 mb-0',
            `${visible.length} ${visible.length === 1 ? 'property' : 'properties'} in view`);
        listEl.replaceChildren(heading, ...rows);
        if (visible.length > MAX_LIST_ROWS) {
            listEl.append(el('p', 'text-muted small px-1 mb-0',
                `And ${visible.length - MAX_LIST_ROWS} more. Zoom in to narrow it down.`));
        }
    }

    // ---------- Picking a property ----------

    function select(id) {
        const pin = pins.find(p => p.id === id);
        if (!pin || !markers[id]) return;

        if (selectedId !== null && markers[selectedId]) {
            const previous = pins.find(p => p.id === selectedId);
            markers[selectedId].setIcon(pinIcon(previous, false)).setZIndexOffset(0);
        }
        selectedId = id;
        markers[id].setIcon(pinIcon(pin, true)).setZIndexOffset(1000);

        cardPhoto.onerror = () => { cardPhoto.onerror = null; cardPhoto.src = cardPhoto.dataset.fallback; };
        cardPhoto.src = pin.photo;
        document.getElementById('map-card-type').textContent = pin.type;
        document.getElementById('map-card-approx').hidden = pin.exact;
        document.getElementById('map-card-title').textContent = pin.title;
        document.getElementById('map-card-town').textContent = pin.town;
        document.getElementById('map-card-beds').textContent = pin.bedrooms + (pin.bedrooms === 1 ? ' bed' : ' beds');
        const price = document.getElementById('map-card-price');
        price.replaceChildren(formatPrice(pin.price) + ' ', el('small', '', '/ month'));
        document.getElementById('map-card-link').href = pin.url;
        card.hidden = false;

        listEl.querySelectorAll('.rm-map-row').forEach(row => {
            const isThis = Number(row.dataset.pinId) === id;
            row.classList.toggle('active', isThis);
            if (isThis) row.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        });

        // If the pin is inside a numbered group, open the group first, then keep it clear of the card
        const reveal = () => map.panInside([pin.lat, pin.lng], {
            paddingTopLeft: [50, 60],
            paddingBottomRight: [50, card.offsetHeight + 40]
        });
        if (pinLayer.zoomToShowLayer) {
            pinLayer.zoomToShowLayer(markers[id], reveal);
        } else {
            reveal();
        }
    }

    function clearSelection() {
        if (selectedId !== null && markers[selectedId]) {
            const previous = pins.find(p => p.id === selectedId);
            if (previous) markers[selectedId].setIcon(pinIcon(previous, false)).setZIndexOffset(0);
        }
        selectedId = null;
        card.hidden = true;
        listEl.querySelectorAll('.rm-map-row.active').forEach(row => row.classList.remove('active'));
    }

    document.getElementById('map-card-close').addEventListener('click', clearSelection);
    map.on('click', clearSelection);

    // ---------- Opening view ----------
    // In order: a property asked for by link, the town being filtered on, the visitor's last town.
    // With none of those, show the whole country and ask where they're looking.

    let moveTimer = null;
    map.on('moveend', () => {
        clearTimeout(moveTimer);
        moveTimer = setTimeout(refresh, 200);
    });

    const filterTown = townCentre(data.filterTown);
    const lastTown = rememberedTown();
    if (data.focus) {
        map.setView([data.focus.lat, data.focus.lng], FOCUS_ZOOM);
        townButtonLabel.textContent = data.focus.town;
    } else if (filterTown) {
        map.setView([filterTown.lat, filterTown.lng], TOWN_ZOOM);
        townButtonLabel.textContent = filterTown.name;
    } else if (lastTown) {
        map.setView([lastTown.lat, lastTown.lng], TOWN_ZOOM);
        townButtonLabel.textContent = lastTown.name;
    } else {
        map.fitBounds(BOTSWANA);
        chooser.hidden = false;
    }
    // Setting the view above already queued a refresh; run it now instead of waiting
    clearTimeout(moveTimer);
    refresh();
})();
