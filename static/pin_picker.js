// Property form: lets a landlord mark the property's spot on a small map.

(function() {
    const mapEl = document.getElementById('pin-map');
    const latInput = document.getElementById('latitude');
    const lngInput = document.getElementById('longitude');
    const status = document.getElementById('pin-status');
    const clearBtn = document.getElementById('pin-clear');
    const townSelect = document.getElementById('location');

    if (typeof L === 'undefined') {
        // Leaflet didn't load (offline, or the CDN is blocked). The form still works without a pin.
        mapEl.hidden = true;
        status.textContent = "The map couldn't load, so the listing will show its town only";
        return;
    }

    const towns = JSON.parse(document.getElementById('pin-data').textContent);
    const TOWN_ZOOM = 13;
    const map = L.map(mapEl, { minZoom: 5 });
    L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(map);

    const icon = L.divIcon({ className: 'rm-pin-anchor', html: '<span class="rm-drop-pin"></span>', iconSize: [0, 0] });
    let marker = null;

    function setPin(latlng) {
        if (marker) {
            marker.setLatLng(latlng);
        } else {
            marker = L.marker(latlng, { icon, draggable: true, keyboard: true, title: 'Property location' }).addTo(map);
            marker.on('dragend', () => setPin(marker.getLatLng()));
        }
        latInput.value = latlng.lat.toFixed(6);
        lngInput.value = latlng.lng.toFixed(6);
        status.textContent = 'Pin placed';
        status.classList.add('blue');
        clearBtn.hidden = false;
    }

    function clearPin() {
        if (marker) {
            map.removeLayer(marker);
            marker = null;
        }
        latInput.value = '';
        lngInput.value = '';
        status.textContent = 'No pin placed';
        status.classList.remove('blue');
        clearBtn.hidden = true;
    }

    function showTown() {
        const centre = towns[townSelect.value];
        if (centre) {
            map.setView(centre, TOWN_ZOOM);
        } else {
            map.fitBounds([[-26.9, 20.0], [-17.8, 29.4]]);   // all of Botswana
        }
    }

    map.on('click', e => setPin(e.latlng));
    clearBtn.addEventListener('click', clearPin);
    // Changing the town moves the map there, unless a pin has already been placed
    townSelect.addEventListener('change', () => { if (!marker) showTown(); });

    const lat = parseFloat(latInput.value);
    const lng = parseFloat(lngInput.value);
    if (Number.isFinite(lat) && Number.isFinite(lng)) {
        map.setView([lat, lng], 15);
        setPin(L.latLng(lat, lng));
    } else {
        showTown();
    }
})();
