import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate, stamp, upgrade
from flask_wtf.csrf import CSRFProtect
from sqlalchemy import inspect
from config import BASE_DIR, Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'main.login'
csrf = CSRFProtect()
migrate = Migrate()

# The migration that matches databases created before migrations were introduced
BASELINE_REVISION = '0001_baseline'


def prepare_database(app):
    """Bring the database up to date with the models.

    - Brand-new database: create every table and mark it as fully migrated.
    - Database from before migrations existed: mark it as the baseline, then upgrade.
    - Anything else: apply any migrations it hasn't had yet.
    """
    uri = app.config['SQLALCHEMY_DATABASE_URI']
    if uri in ('sqlite://', 'sqlite:///:memory:'):
        # In-memory database (tests): nothing to migrate
        db.create_all()
        return

    tables = set(inspect(db.engine).get_table_names())
    if not tables - {'alembic_version'}:
        db.create_all()
        stamp()
    else:
        if 'alembic_version' not in tables:
            stamp(revision=BASELINE_REVISION)
        upgrade()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    # render_as_batch lets SQLite change existing tables
    migrate.init_app(app, db, directory=os.path.join(BASE_DIR, 'migrations'), render_as_batch=True)

    if app.config['TRUSTED_PROXY_COUNT']:
        # Behind a reverse proxy, read the visitor's address and https status from its headers
        from werkzeug.middleware.proxy_fix import ProxyFix
        hops = app.config['TRUSTED_PROXY_COUNT']
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops, x_host=hops)

    from routes import bp
    app.register_blueprint(bp)

    from cli import register_commands
    register_commands(app)

    if app.config['MAIL_BACKEND'] == 'disabled':
        app.logger.warning("Email is not configured: verification and password-reset emails will not be sent. "
                           "Set MAIL_SERVER (see README).")

    # Set AUTO_MIGRATE=0 to manage the database by hand with `flask --app app db ...`
    if os.environ.get('AUTO_MIGRATE', '1') != '0':
        with app.app_context():
            prepare_database(app)

    return app

if __name__ == '__main__':
    # Import via the module name so routes/models share this module's db
    from app import create_app
    app = create_app()
    # Debug mode exposes a code console, so it is opt-in: set FLASK_DEBUG=1 while developing
    debug = os.environ.get('FLASK_DEBUG') == '1'
    app.run(host=os.environ.get('HOST', '0.0.0.0'), port=int(os.environ.get('PORT', 5000)), debug=debug)
