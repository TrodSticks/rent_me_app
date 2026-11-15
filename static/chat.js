/* Keep sends in-place. A retry always reuses the same server-enforced submission ID. */
(() => {
    const form = document.querySelector('#chat-form, [data-new-message]');
    if (!form || !window.fetch || !window.crypto?.randomUUID) return;
    const history = document.querySelector('#chat-history');
    const input = form.querySelector('[name="content"]');
    const token = form.querySelector('[name="client_token"]');
    const send = form.querySelector('[type="submit"]');
    let status = document.querySelector('#chat-status');
    if (!status) {
        status = document.createElement('p');
        status.setAttribute('role', 'status');
        form.append(status);
    }
    let busy = false, pending = null, pendingBubble = null, refreshing = false;
    let cursor = Math.max(0, ...Array.from(history?.querySelectorAll('[data-message-id]') || [], e => Number(e.dataset.messageId)));
    const key = `rentme-pending:${form.dataset.owner}:${form.action}:${form.querySelector('[name="property_id"]')?.value || ''}`;
    const persist = () => { try { if (pending) sessionStorage.setItem(key, JSON.stringify(pending)); else sessionStorage.removeItem(key); } catch (_) {} };
    try {
        const saved = JSON.parse(sessionStorage.getItem(key) || 'null');
        if (saved && typeof saved.content === 'string' && typeof saved.token === 'string') {
            pending = saved;
            input.value = saved.content;
            input.readOnly = true;
            status.textContent = 'The last send was not confirmed. Press Send to safely retry it.';
        }
    } catch (_) {}
    function bubble(message) {
        const el = document.createElement('div');
        el.className = `message-bubble ${message.sent ? 'sent' : 'received'}`;
        if (message.id) el.dataset.messageId = message.id;
        const text = document.createElement('div');
        text.className = 'message-text';
        text.textContent = message.content;
        const meta = document.createElement('div');
        meta.className = 'message-meta';
        meta.textContent = message.id ? `${message.label} · ${message.sent ? (message.read ? 'Read' : 'Sent') : ''}` : 'Sending…';
        el.append(text, meta);
        return el;
    }
    async function jsonRequest(url, options = {}) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 20000);
        try {
            const response = await fetch(url, {...options, headers: {Accept: 'application/json'},
                credentials: 'same-origin', redirect: 'error', cache: 'no-store', signal: controller.signal});
            if (!response.headers.get('content-type')?.includes('application/json')) throw new Error('Reload the page and sign in again if needed. Your draft is kept.');
            const data = await response.json();
            if (!response.ok) throw new Error(data.error || 'The request could not be completed.');
            return data;
        } finally { clearTimeout(timer); }
    }
    form.addEventListener('submit', async event => {
        const prevented = event.defaultPrevented;
        event.preventDefault();
        if (busy || prevented) return;
        if (!input.value.trim() || !form.reportValidity()) return;
        busy = true;
        if (!pending) pending = {content: input.value.trim(), token: token.value || crypto.randomUUID()};
        persist();
        token.value = pending.token;
        input.readOnly = true;
        send.disabled = true;
        form.setAttribute('aria-busy', 'true');
        status.textContent = 'Sending…';
        if (history && !pendingBubble) {
            history.querySelector('.rm-empty')?.remove();
            pendingBubble = bubble({content: pending.content, sent: true});
            history.append(pendingBubble);
        }
        if (pendingBubble) pendingBubble.querySelector('.message-meta').textContent = 'Sending…';
        if (history) history.scrollTop = history.scrollHeight;
        const body = new FormData(form);
        body.set('content', pending.content);
        body.set('client_token', pending.token);
        try {
            const data = await jsonRequest(form.action, {method: 'POST', body});
            if (!data.message?.id) throw new Error('The send was not confirmed. Retry safely using Send.');
            if (history) {
                if (history.querySelector(`[data-message-id="${data.message.id}"]`)) pendingBubble?.remove();
                else pendingBubble.replaceWith(bubble(data.message));
            }
            pending = null;
            pendingBubble = null;
            persist();
            input.value = '';
            input.readOnly = false;
            input.style.height = 'auto';
            token.value = crypto.randomUUID();
            status.textContent = 'Sent';
            if (!history && data.redirect) window.location.assign(data.redirect);
        } catch (error) {
            status.textContent = `${error.message === 'Failed to fetch' || error.name === 'AbortError' ? 'Connection interrupted; sending is not confirmed.' : error.message} Press Send to retry the same message safely.`;
            if (pendingBubble) pendingBubble.querySelector('.message-meta').textContent = 'Not confirmed · press Send to retry';
        } finally {
            busy = false;
            send.disabled = false;
            form.removeAttribute('aria-busy');
        }
    });
    if (!history) return;
    async function refresh() {
        if (refreshing || busy || pending || document.hidden || !navigator.onLine) return;
        refreshing = true;
        try {
            const url = new URL(history.dataset.url, location.origin);
            url.searchParams.set('after', cursor);
            const data = await jsonRequest(url);
            const atBottom = history.scrollHeight - history.scrollTop - history.clientHeight < 100;
            for (const message of data.messages) {
                if (!history.querySelector(`[data-message-id="${message.id}"]`)) history.append(bubble(message));
                cursor = Math.max(cursor, message.id);
            }
            if (atBottom) history.scrollTop = history.scrollHeight;
        } catch (_) { /* Keep the loaded conversation usable during a connection interruption. */ }
        finally { refreshing = false; }
    }
    const timer = setInterval(refresh, 15000);
    window.addEventListener('pagehide', () => clearInterval(timer), {once: true});
    document.addEventListener('visibilitychange', () => { if (!document.hidden) refresh(); });
    const older = document.querySelector('#older-messages');
    older?.addEventListener('click', async () => {
        older.disabled = true;
        try {
            const first = Math.min(...Array.from(history.querySelectorAll('[data-message-id]'), e => Number(e.dataset.messageId)));
            const url = new URL(history.dataset.url, location.origin);
            url.searchParams.set('before', first);
            const data = await jsonRequest(url);
            const height = history.scrollHeight;
            const fragment = document.createDocumentFragment();
            for (const message of data.messages) if (!history.querySelector(`[data-message-id="${message.id}"]`)) fragment.append(bubble(message));
            older.after(fragment);
            history.scrollTop += history.scrollHeight - height;
            if (!data.more) older.remove();
        } catch (_) { status.textContent = 'Older messages could not load. Please try again.'; }
        finally { older.disabled = false; }
    });
})();
