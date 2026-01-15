# Author: TABARC-Code
#
# Application factory.
# Keeps object initialisation in one place so it stays readable once the project grows.

import os
import logging
from flask import Flask
from .services import DeviceManager, PlaybackManager, SpotifyHandler, QueueManager
from .media_manager import MediaManager


def create_app():
    app = Flask(__name__)

    app.secret_key = os.getenv("FLASK_SECRET_KEY", "dev_key")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    with app.app_context():
        app.spotify_handler = SpotifyHandler(
            client_id=os.getenv("SPOTIPY_CLIENT_ID"),
            client_secret=os.getenv("SPOTIPY_CLIENT_SECRET"),
            redirect_uri=os.getenv("SPOTIPY_REDIRECT_URI")
        )

        app.device_manager = DeviceManager(app.spotify_handler)

        app.queue_manager = QueueManager()

        app.playback_manager = PlaybackManager(app.device_manager, app.queue_manager)

        media_root = os.getenv("MEDIA_ROOT", "/app/media")
        app.media_manager = MediaManager(media_root)

    from .routes import main_bp
    app.register_blueprint(main_bp)

    return app
