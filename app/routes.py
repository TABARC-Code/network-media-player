# Author: TABARC-Code
#
# Notes:
# - Folder queue URLs are built as one relative path and then quoted once.
# - Cover art endpoint always returns a placeholder if unauthenticated or missing.
# - Stop is explicit: stop + clear queue, no accidental “advance”.

import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, send_file, jsonify
from urllib.parse import quote

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    path = request.args.get("path", "")
    parent = os.path.dirname(path) if path else None

    try:
        folders, files = current_app.media_manager.list_dir(path)
    except Exception:
        folders, files = [], []

    devices = current_app.device_manager.get_all()
    queue = current_app.queue_manager.get_list()
    logged_in = current_app.spotify_handler.get_client() is not None

    return render_template(
        "index.html",
        devices=devices.keys(),
        spotify_logged_in=logged_in,
        folders=folders,
        files=files,
        queue=queue,
        current_path=path,
        parent_path=parent
    )


@main_bp.route("/login")
def login():
    return redirect(current_app.spotify_handler.get_auth_url())


@main_bp.route("/callback")
def callback():
    code = request.args.get("code")
    current_app.spotify_handler.process_code(code)
    return redirect(url_for("main.index"))


@main_bp.route("/api/get_cover_art")
def get_cover_art():
    artist = (request.args.get("artist") or "").strip()
    album = (request.args.get("album") or "").strip()

    if not artist or artist.lower() in ("unknown", "unknown artist"):
        return jsonify({"url": "/static/default_album.png"})

    if current_app.spotify_handler.get_client() is None:
        return jsonify({"url": "/static/default_album.png"})

    url = current_app.spotify_handler.search_album_art(artist, album)
    return jsonify({"url": url or "/static/default_album.png"})


@main_bp.route("/stream/<path:filename>")
def stream(filename):
    path = current_app.media_manager.get_path(filename)
    if path and os.path.exists(path):
        return send_file(path)
    return "Not found", 404


@main_bp.route("/play", methods=["POST"])
def play():
    device = request.form.get("device_name")
    action = request.form.get("action", "play_now")  # play_now | queue

    item = {
        "device_name": device,
        "track_uri": request.form.get("track_uri"),
        "file_path": None,
        "title": "Manual Input"
    }

    file_rel = request.form.get("file_rel_path")
    if file_rel:
        host = os.getenv("HOST_IP")
        if not host:
            flash("Error: HOST_IP not set in .env", "error")
            return redirect(request.referrer or url_for("main.index"))

        item["file_path"] = f"http://{host}:5000/stream/{quote(file_rel)}"
        item["title"] = os.path.basename(file_rel)

    if request.form.get("file_url"):
        item["file_path"] = request.form.get("file_url")

    if action == "queue":
        current_app.queue_manager.add(item)
        flash("Added to queue", "info")
    else:
        current_app.playback_manager.play_now(device, item)
        flash(f"Playing on {device}", "success")

    return redirect(request.referrer or url_for("main.index"))


@main_bp.route("/queue/add_folder", methods=["POST"])
def queue_folder():
    device = request.form.get("device_name")
    path = request.form.get("folder_path")

    _, files = current_app.media_manager.list_dir(path)
    host = os.getenv("HOST_IP")
    if not host:
        flash("Error: HOST_IP not set in .env", "error")
        return redirect(url_for("main.index", path=path))

    count = 0
    for f in files:
        rel = f"{path}/{f['filename']}" if path else f"{f['filename']}"
        url = f"http://{host}:5000/stream/{quote(rel)}"

        item = {
            "device_name": device,
            "track_uri": None,
            "file_path": url,
            "title": f.get("title") or f["filename"]
        }
        current_app.queue_manager.add(item)
        count += 1

    flash(f"Queued {count} tracks on {device}", "success")
    return redirect(url_for("main.index", path=path))


@main_bp.route("/next", methods=["POST"])
def next_track():
    current_app.playback_manager.next_track()
    return redirect(url_for("main.index"))


@main_bp.route("/stop", methods=["POST"])
def stop():
    current_app.playback_manager.stop_playback(clear_queue=True, advance=False)
    flash("Stopped and queue cleared", "info")
    return redirect(url_for("main.index"))
