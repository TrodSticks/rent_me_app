"""Content-addressed public assets; private pages are never shared-cache entries."""
import hashlib
from pathlib import Path
from time import perf_counter
from flask import abort, g, request, send_from_directory, url_for


def install_assets(app):
    root = Path(app.static_folder)
    versions = {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()[:16]
                for p in root.rglob('*') if p.is_file()
                and 'property_pics' not in p.relative_to(root).parts
                and p.suffix in {'.css', '.js', '.svg', '.png', '.ico', '.webmanifest'}}

    def asset_url(filename):
        if filename not in versions:
            return url_for('static', filename=filename)
        return url_for('versioned_asset', version=versions[filename], filename=filename)

    @app.context_processor
    def asset_helpers():
        return {'asset_url': asset_url}

    @app.get('/assets/<version>/<path:filename>')
    def versioned_asset(version, filename):
        if versions.get(filename) != version:
            abort(404)
        response = send_from_directory(root, filename, max_age=31536000)
        response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
        return response

    @app.before_request
    def start_timer():
        g.request_started = perf_counter()

    @app.after_request
    def response_headers(response):
        if hasattr(g, 'request_started'):
            response.headers['Server-Timing'] = f'app;dur={(perf_counter() - g.request_started) * 1000:.1f}'
        if request.endpoint not in {'versioned_asset', 'static', 'main.thumbnail'}:
            response.headers['Cache-Control'] = 'private, no-store'
        return response
