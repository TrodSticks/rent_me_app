// Run with node --test tests/test_pin_picker.cjs (no browser dependencies).
const {test} = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');

test('map starts locked, allows deliberate edits, and relocks without losing the pin', () => {
    const elements = {};
    for (const id of ['pin-map', 'latitude', 'longitude', 'pin-status', 'pin-clear', 'location', 'pin-edit', 'pin-instructions', 'pin-data']) {
        elements[id] = {value: '', events: {}, classList: {toggle() {}, add() {}, remove() {}},
            addEventListener(name, fn) {this.events[name] = fn;}, setAttribute() {}, focus() {}};
    }
    elements.latitude.value = '-24.650000';
    elements.longitude.value = '25.910000';
    elements['pin-data'].textContent = '{}';
    const handlers = {};
    const map = {setView() {}, fitBounds() {}, removeLayer() {}, on(name, fn) {handlers[name] = fn;}};
    for (const name of ['dragging', 'touchZoom', 'scrollWheelZoom', 'doubleClickZoom', 'boxZoom', 'keyboard', 'tapHold']) {
        map[name] = {enabled: false, enable() {this.enabled = true;}, disable() {this.enabled = false;}};
    }
    const pageEvents = {};
    const L = {map: () => map, tileLayer: () => ({addTo() {}}), divIcon() {},
        latLng: (lat, lng) => ({lat, lng}), marker: () => ({addTo() {return this;}, on() {},
            setLatLng() {}, dragging: {enable() {}, disable() {}}})};
    vm.runInNewContext(fs.readFileSync('static/pin_picker.js', 'utf8'), {
        L, document: {getElementById: id => elements[id]},
        window: {addEventListener: (name, fn) => {pageEvents[name] = fn;}}
    });
    assert.equal(elements['pin-map'].inert, true);
    assert.equal(map.dragging.enabled, false);
    handlers.click({latlng: {lat: -24, lng: 26}});
    assert.equal(elements.latitude.value, '-24.650000');
    elements['pin-edit'].events.click();
    assert.equal(elements['pin-map'].inert, false);
    assert.equal(map.dragging.enabled, true);
    handlers.click({latlng: {lat: -24, lng: 26}});
    assert.equal(elements.latitude.value, '-24.000000');
    elements['pin-edit'].events.click();
    assert.equal(elements['pin-map'].inert, true);
    assert.equal(map.scrollWheelZoom.enabled, false);
    assert.equal(elements.latitude.value, '-24.000000');
    elements['pin-edit'].events.click();
    pageEvents.pageshow();
    assert.equal(elements['pin-map'].inert, true);
});
