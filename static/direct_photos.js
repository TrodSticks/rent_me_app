// Send photo bytes only to the scoped Supabase URL. The final listing request contains receipts.
(function () {
    const manager = document.getElementById('photo-manager');
    if (!manager || manager.dataset.direct !== 'true') return;
    const form = document.getElementById('listing-form');
    const input = document.getElementById('photos');
    const warning = document.getElementById('photo-warning');
    const progress = document.createElement('p');
    progress.setAttribute('role', 'status');
    progress.setAttribute('aria-live', 'polite');
    manager.append(progress);
    const receipts = new Map(); // File identity survives retries without uploading completed files again.
    let busy = false;

    async function jsonRequest(url, body, isForm = false) {
        const response = await fetch(url, {
            method: 'POST', credentials: 'same-origin',
            headers: {
                'X-CSRFToken': form.elements.csrf_token.value,
                'X-Photo-Upload': 'direct',
                ...(isForm ? {} : {'Content-Type': 'application/json'})
            },
            body: isForm ? body : JSON.stringify(body),
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok || response.redirected || (!data.id && !data.redirect)) {
            throw new Error(data.error || 'Your session may have expired. Keep this page open, sign in in another tab, then retry.');
        }
        return data;
    }

    function upload(url, file, label) {
        return new Promise((resolve, reject) => {
            const xhr = new XMLHttpRequest();
            xhr.open('PUT', url);
            xhr.timeout = 120000;
            xhr.setRequestHeader('Content-Type', file.type || 'application/octet-stream');
            xhr.upload.onprogress = event => {
                if (event.lengthComputable) progress.textContent = `${label}: ${Math.round(event.loaded * 100 / event.total)}%`;
            };
            xhr.onload = () => {
                // A retry after a lost response can find the immutable object already present.
                // Only the authenticated finish endpoint can decide whether it is a valid photo.
                let duplicate = false;
                try {
                    const detail = JSON.parse(xhr.responseText);
                    duplicate = detail.error === 'Duplicate' || /already exists/i.test(detail.message || '');
                } catch (_) { /* Non-JSON errors are reported as upload failures. */ }
                if ((xhr.status >= 200 && xhr.status < 300) || duplicate) resolve();
                else reject(new Error(`Could not upload ${file.name}. Use a JPG, PNG, GIF or WebP up to 5 MB, check your connection, then press Save again.`));
            };
            xhr.onerror = xhr.ontimeout = () => reject(new Error(`Upload interrupted for ${file.name}. Check your connection and press Save again to retry.`));
            xhr.send(file);
        });
    }

    form.addEventListener('submit', async event => {
        event.preventDefault();
        if (busy) return;
        const files = [...input.files];
        const kept = manager.querySelectorAll('#photo-grid .rm-photo-tile:not(.is-removed)').length;
        const max = Number(manager.dataset.max);
        let problem = '';
        if (kept + files.length > max) problem = `A listing can have up to ${max} photos. Remove some and try again.`;
        if (files.some(file => file.size > Number(manager.dataset.maxBytes))) problem = 'Each photo must be 5 MB or smaller.';
        if (problem) {
            warning.textContent = problem;
            warning.hidden = false;
            return;
        }
        // Capture enabled controls and the chosen save action before locking the form.
        const body = new FormData(form);
        body.delete('photos');
        body.delete('image');
        body.set('action', event.submitter ? event.submitter.value : 'draft');
        const controls = [...form.querySelectorAll('input, select, textarea, button')];
        const previous = controls.map(control => control.disabled);
        busy = true;
        controls.forEach(control => { control.disabled = true; });
        warning.hidden = true;
        try {
            for (const [index, file] of files.entries()) {
                const label = `Photo ${index + 1} of ${files.length}`;
                let receipt = receipts.get(file);
                if (!receipt || Date.now() - receipt.started > 105 * 60 * 1000) {
                    progress.textContent = `${label}: preparing upload…`;
                    receipt = await jsonRequest('/api/photo-uploads', {
                        listing_id: manager.dataset.listingId ? Number(manager.dataset.listingId) : null,
                        size: file.size,
                    });
                    receipt.started = Date.now();
                    receipts.set(file, receipt);
                }
                if (!receipt.ready) {
                    if (!receipt.sent) {
                        await upload(receipt.url, file, label);
                        receipt.sent = true;
                    }
                    progress.textContent = `${label}: checking photo…`;
                    await jsonRequest(`/api/photo-uploads/${receipt.id}/finish`, {});
                    receipt.ready = true;
                }
                body.append('photo_upload_ids', receipt.id);
            }
            progress.textContent = 'Photos checked. Saving your listing…';
            const result = await jsonRequest(form.action || window.location.href, body, true);
            window.location.assign(result.redirect);
        } catch (error) {
            warning.textContent = error.message || 'Could not save. Check your connection and try again.';
            warning.hidden = false;
            progress.textContent = 'Your changes have not been confirmed saved. Completed uploads are kept for retry.';
            warning.scrollIntoView({block: 'center', behavior: 'smooth'});
        } finally {
            busy = false;
            controls.forEach((control, index) => { control.disabled = previous[index]; });
        }
    });
    window.addEventListener('beforeunload', event => {
        if (busy) { event.preventDefault(); event.returnValue = ''; }
    });
})();
