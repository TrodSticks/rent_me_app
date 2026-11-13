const test = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
const source = fs.readFileSync('static/direct_photos.js', 'utf8');

function browser({failUpload = false, saveError = false} = {}) {
    const listeners = {};
    const files = [{name: 'one.jpg', type: 'image/jpeg', size: 3000000},
                   {name: 'two.jpg', type: 'image/jpeg', size: 3000000}];
    const input = {files, disabled: false};
    const csrf = {value: 'csrf-token', disabled: false};
    const submit = {value: 'draft', disabled: false};
    const controls = [input, csrf, submit];
    const warning = {scrollIntoView() {}};
    const progress = {setAttribute() {}};
    const calls = [], uploads = [], saves = [];
    let redirect;
    const manager = {dataset: {direct: 'true', listingId: '10', max: '10', maxBytes: '5242880'},
                     append() {}, querySelectorAll() { return [{}, {}]; }};
    const form = {elements: {csrf_token: csrf}, action: {namedButtons: true},
        getAttribute(name) { assert.equal(name, 'action'); return '/property/10/update'; },
        addEventListener(name, fn) { listeners[name] = fn; },
        querySelectorAll() { return controls; }};
    const elements = {'photo-manager': manager, 'listing-form': form, photos: input, 'photo-warning': warning};
    class FormData {
        constructor() { this.values = new Map([['photos', files], ['title', ['My property']]]); }
        delete(key) { this.values.delete(key); }
        set(key, value) { this.values.set(key, [value]); }
        append(key, value) { this.values.set(key, [...(this.values.get(key) || []), value]); }
    }
    class XHR {
        constructor() { this.upload = {}; }
        open(method, url) { this.url = url; assert.equal(method, 'PUT'); }
        setRequestHeader(name, value) { assert.equal(name, 'Content-Type'); }
        send(file) {
            uploads.push([this.url, file]);
            if (failUpload && file === files[1]) { failUpload = false; this.onerror(); return; }
            this.status = 200; this.onload();
        }
    }
    const context = {document: {getElementById: id => elements[id], createElement: () => progress},
        window: {addEventListener() {}, location: {assign: url => {redirect = url;}}},
        FormData, XMLHttpRequest: XHR,
        fetch: async (url, options) => {
            calls.push([url, options]);
            assert.equal(options.headers['X-CSRFToken'], 'csrf-token');
            let data, ok = true;
            if (url === '/api/photo-uploads') {
                data = {id: String(calls.length), url: 'https://storage.example/scoped-upload'};
            } else if (url.endsWith('/finish')) {
                data = {id: url.split('/')[3], ready: true};
            } else {
                assert.equal(url, '/property/10/update');
                saves.push(options.body);
                if (saveError) { saveError = false; data = {error: 'Correct the price.'}; ok = false; }
                else data = {redirect: '/dashboard'};
            }
            return {ok, redirected: false, json: async () => data};
        },
    };
    vm.runInNewContext(source, context);
    return {submit: () => listeners.submit({preventDefault() {}, submitter: submit}),
            calls, uploads, saves, controls, warning, progress, get redirect() {return redirect;}};
}

test('6 MB goes directly to storage; save carries only receipts and draft action', async () => {
    const b = browser();
    await b.submit();
    assert.equal(b.uploads.length, 2);
    assert.ok(b.uploads.every(([url]) => url.startsWith('https://storage.example/')));
    assert.equal(b.saves[0].values.has('photos'), false);
    assert.equal(b.saves[0].values.has('image'), false);
    assert.equal(b.saves[0].values.get('photo_upload_ids').length, 2);
    assert.equal(b.saves[0].values.get('action')[0], 'draft');
    assert.equal(b.redirect, '/dashboard');
});

test('interrupted second photo retries without reuploading the first', async () => {
    const b = browser({failUpload: true});
    await b.submit();
    assert.equal(b.saves.length, 0);
    assert.ok(b.controls.every(control => !control.disabled));
    await b.submit();
    assert.equal(b.uploads.length, 3);
    assert.equal(b.calls.filter(([url]) => url === '/api/photo-uploads').length, 2);
    assert.equal(b.redirect, '/dashboard');
});

test('form validation retry reuses completed photos', async () => {
    const b = browser({saveError: true});
    await b.submit();
    assert.equal(b.warning.textContent, 'Correct the price.');
    await b.submit();
    assert.equal(b.uploads.length, 2);
    assert.equal(b.saves.length, 2);
    assert.equal(b.redirect, '/dashboard');
});
