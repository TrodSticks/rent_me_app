const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function selection(files, kept = 2) {
    let focused;
    class Element {
        constructor() { this.children = []; this.listeners = {}; this.dataset = {}; }
        addEventListener(name, fn) { this.listeners[name] = fn; }
        setAttribute(name, value) { this[name] = value; }
        append(...children) { this.children.push(...children); }
        replaceChildren(...children) { this.children = children; }
        focus() { focused = this; }
        querySelectorAll(selector) {
            return selector === '.rm-remove-new-photo' ? this.children.map(tile => tile.children[2]) : [];
        }
    }
    const input = new Element(); input.files = files; input.disabled = false;
    const previews = new Element(), warning = new Element(), count = new Element();
    const manager = new Element(); manager.dataset = {max: '10', maxBytes: '5242880'};
    const grid = new Element();
    grid.querySelectorAll = selector => selector.includes(':not') ? Array(kept).fill({}) : [];
    const elements = {'photo-manager': manager, 'photo-grid': grid, photos: input,
        'photo-previews': previews, 'photo-warning': warning, 'photo-count': count};
    class DataTransfer {
        constructor() { this.files = []; this.items = {add: file => this.files.push(file)}; }
    }
    vm.runInNewContext(fs.readFileSync('static/photo_manager.js', 'utf8'), {
        document: {getElementById: id => elements[id], createElement: () => new Element()},
        URL: {createObjectURL: () => 'blob:preview', revokeObjectURL() {}}, DataTransfer,
    });
    input.listeners.change();
    return {input, previews, warning, count, remove: index => previews.children[index].children[2].listeners.click(),
        get focused() { return focused; }};
}

test('remove six of fourteen new photos without restarting or changing saved photos', () => {
    const files = Array.from({length: 14}, (_, i) => ({name: `photo-${i}.jpg`, size: 100}));
    const ui = selection(files);
    assert.match(ui.warning.textContent, /16 photos.*remove 6/);
    for (let i = 0; i < 6; i++) ui.remove(2);
    assert.equal(ui.input.files.length, 8);
    assert.equal(ui.previews.children.length, 8);
    assert.equal(ui.count.textContent, '10 of 10 photos after saving');
    assert.equal(ui.warning.hidden, true);
    assert.deepEqual(Array.from(ui.input.files), [...files.slice(0, 2), ...files.slice(8)]);
});

test('remove an oversized selection and clear its warning', () => {
    const small = {name: 'small.jpg', size: 100};
    const ui = selection([{name: 'large.jpg', size: 6000000}, small]);
    assert.equal(ui.warning.hidden, false);
    ui.remove(0);
    assert.equal(ui.warning.hidden, true);
    assert.equal(ui.input.files[0], small);
});

test('all new photos can be removed; focus returns to picker', () => {
    const ui = selection([{name: 'one.jpg', size: 100}], 0);
    ui.remove(0);
    assert.equal(ui.input.files.length, 0);
    assert.equal(ui.count.textContent, '0 of 10 photos after saving');
    assert.equal(ui.focused, ui.input);
});

test('selection cannot change while an upload is in progress', () => {
    const ui = selection([{name: 'one.jpg', size: 100}]);
    ui.input.disabled = true;
    ui.remove(0);
    assert.equal(ui.input.files.length, 1);
});
