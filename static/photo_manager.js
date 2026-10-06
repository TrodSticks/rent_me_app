// Property form: reorder, pick a cover for, and remove a listing's photos, and preview new ones.
// The order of the tiles is the order that is saved; the first tile is the cover.

(function() {
    const manager = document.getElementById('photo-manager');
    if (!manager) return;

    const grid = document.getElementById('photo-grid');
    const input = document.getElementById('photos');
    const previews = document.getElementById('photo-previews');
    const warning = document.getElementById('photo-warning');
    const maxPhotos = Number(manager.dataset.max);
    const maxBytes = Number(manager.dataset.maxBytes);

    if (grid) {
        grid.addEventListener('click', event => {
            const button = event.target.closest('button');
            if (!button) return;
            const tile = button.closest('.rm-photo-tile');

            if (button.dataset.cover !== undefined) {
                grid.prepend(tile);
            } else if (button.dataset.move === '-1' && tile.previousElementSibling) {
                grid.insertBefore(tile, tile.previousElementSibling);
            } else if (button.dataset.move === '1' && tile.nextElementSibling) {
                grid.insertBefore(tile.nextElementSibling, tile);
            }
            button.focus();
        });

        grid.addEventListener('change', event => {
            if (event.target.name === 'remove_photos') {
                event.target.closest('.rm-photo-tile').classList.toggle('is-removed', event.target.checked);
                check();
            }
        });
    }

    function keptCount() {
        return grid ? grid.querySelectorAll('.rm-photo-tile:not(.is-removed)').length : 0;
    }

    // Tell the landlord about problems before they wait for an upload. The server checks again.
    function check() {
        const files = [...input.files];
        const tooBig = files.filter(file => file.size > maxBytes).map(file => file.name);
        const total = keptCount() + files.length;
        let message = '';
        if (tooBig.length) {
            message = `Larger than 5 MB: ${tooBig.join(', ')}. Choose smaller photos.`;
        } else if (total > maxPhotos) {
            message = `That makes ${total} photos. A listing can have up to ${maxPhotos}; remove ${total - maxPhotos}.`;
        }
        warning.textContent = message;
        warning.hidden = !message;
    }

    input.addEventListener('change', () => {
        previews.replaceChildren(...[...input.files].map((file, index) => {
            const tile = document.createElement('li');
            tile.className = 'rm-photo-tile is-new';
            const image = document.createElement('img');
            image.alt = `New photo ${index + 1}`;
            image.src = URL.createObjectURL(file);
            image.onload = () => URL.revokeObjectURL(image.src);
            const flag = document.createElement('span');
            flag.className = 'rm-new-flag';
            flag.textContent = 'New';
            tile.append(image, flag);
            return tile;
        }));
        check();
    });
})();
