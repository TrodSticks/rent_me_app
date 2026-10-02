import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from config import Config

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = 'main.login'
csrf = CSRFProtect()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)

    from routes import bp
    app.register_blueprint(bp)

    with app.app_context():
        db.create_all()

    return app

if __name__ == '__main__':
    # Import via the module name so routes/models share this module's db
    from app import create_app
    app = create_app()
    # Debug mode exposes a code console, so it is opt-in: set FLASK_DEBUG=1 while developing
    debug = os.environ.get('FLASK_DEBUG') == '1'
    app.run(host=os.environ.get('HOST', '0.0.0.0'), port=int(os.environ.get('PORT', 5000)), debug=debug)
