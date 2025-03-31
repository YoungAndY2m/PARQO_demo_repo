from flask import Flask
from .config import Config
from .db import DB

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    app.db = DB(app)

    from .index import bp as index_bp
    app.register_blueprint(index_bp)

    return app
