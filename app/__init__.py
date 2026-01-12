import os
from flask import Flask
from app.config import Config

# Get absolute paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATE_DIR = os.path.join(BASE_DIR, "app", "templates")


def create_app():
    app = Flask(__name__, static_folder=STATIC_DIR, template_folder=TEMPLATE_DIR)
    app.config.from_object(Config)

    # Ensure data directories exist
    data_dir = app.config["DATA_DIR"]
    os.makedirs(os.path.join(data_dir, "audio"), exist_ok=True)
    os.makedirs(os.path.join(data_dir, "sources"), exist_ok=True)

    # Initialize database
    from app.database import init_db
    init_db()

    from app.routes import main_bp
    app.register_blueprint(main_bp)

    return app
