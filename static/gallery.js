// Property page gallery: a swipeable strip of photos with thumbnails, and a full-screen viewer.

(function() {
    const track = document.getElementById('gallery-track');
    const viewer = document.getElementById('viewer');
    if (!track || !viewer) return;

    const slides = [...track.querySelectorAll('.rm-gallery-slide[data-index]')];
    const thumbs = [...document.querySelectorAll('#gallery-thumbs .rm-thumb')];
    const counter = document.getElementById('gallery-count');
    const image = document.getElementById('viewer-image');
    const viewerCount = document.getElementById('viewer-count');
    const closeButton = document.getElementById('viewer-close');
    const total = slides.length;
    if (!total) return;

    let current = 0;        // photo showing in the strip
    let viewing = 0;        // photo showing full screen
    let openedFrom = null;  // what to return focus to when the viewer closes

    // ---------- The strip ----------

    function showInStrip(index, smooth = true) {
        const slide = slides[Math.max(0, Math.min(index, total - 1))];
        track.scrollTo({ left: slide.offsetLeft, behavior: smooth ? 'smooth' : 'auto' });
    }

    function markCurrent(index) {
        current = index;
        if (counter) counter.textContent = `${index + 1} / ${total}`;
        thumbs.forEach((thumb, i) => {
            thumb.classList.toggle('active', i === index);
            if (i === index) thumb.scrollIntoView({ block: 'nearest', inline: 'nearest' });
        });
    }

    // Follow swipes and scrolling to keep the counter and thumbnails in step
    let scrollTimer = null;
    track.addEventListener('scroll', () => {
        clearTimeout(scrollTimer);
        scrollTimer = setTimeout(() => {
            markCurrent(Math.round(track.scrollLeft / track.clientWidth));
        }, 60);
    });

    track.addEventListener('keydown', event => {
        if (event.key === 'ArrowRight') { event.preventDefault(); showInStrip(current + 1); }
        if (event.key === 'ArrowLeft') { event.preventDefault(); showInStrip(current - 1); }
    });

    thumbs.forEach((thumb, index) => thumb.addEventListener('click', () => showInStrip(index)));
    slides.forEach((slide, index) => slide.addEventListener('click', () => openViewer(index, slide)));

    // ---------- Full screen ----------

    function showInViewer(index) {
        viewing = (index + total) % total;
        const source = slides[viewing].querySelector('img');
        image.src = source.currentSrc || source.src;
        image.alt = source.alt;
        viewerCount.textContent = `${viewing + 1} of ${total}`;
    }

    function openViewer(index, from) {
        openedFrom = from;
        showInViewer(index);
        viewer.hidden = false;
        viewer.classList.toggle('single', total === 1);
        document.body.style.overflow = 'hidden';
        closeButton.focus();
    }

    function closeViewer() {
        viewer.hidden = true;
        document.body.style.overflow = '';
        showInStrip(viewing, false);
        if (openedFrom) openedFrom.focus();
    }

    closeButton.addEventListener('click', closeViewer);
    document.getElementById('viewer-prev').addEventListener('click', () => showInViewer(viewing - 1));
    document.getElementById('viewer-next').addEventListener('click', () => showInViewer(viewing + 1));
    viewer.addEventListener('click', event => { if (event.target === viewer) closeViewer(); });

    viewer.addEventListener('keydown', event => {
        if (event.key === 'Escape') closeViewer();
        if (event.key === 'ArrowRight') showInViewer(viewing + 1);
        if (event.key === 'ArrowLeft') showInViewer(viewing - 1);
        if (event.key === 'Tab') {
            // Keep keyboard focus inside the viewer while it is open
            const buttons = [...viewer.querySelectorAll('button')].filter(button => button.offsetParent !== null);
            const first = buttons[0];
            const last = buttons[buttons.length - 1];
            if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
            else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
        }
    });

    // Swipe left and right on a touch screen
    let touchStartX = null;
    viewer.addEventListener('touchstart', event => { touchStartX = event.touches[0].clientX; }, { passive: true });
    viewer.addEventListener('touchend', event => {
        if (touchStartX === null) return;
        const moved = event.changedTouches[0].clientX - touchStartX;
        touchStartX = null;
        if (Math.abs(moved) > 50) showInViewer(viewing + (moved < 0 ? 1 : -1));
    });
})();
