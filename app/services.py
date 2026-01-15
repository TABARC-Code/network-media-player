# Author: TABARC-Code
#
# Notes from the bench:
# - Network playback is a swamp. The status APIs are late, sometimes wrong, and occasionally imaginative.
# - Chromecast will often report IDLE just after you tell it to play. Treat early status as noise.
# - If you clear “current device” too early, the monitor thread will start the next track while the last one
#   is still winding down. That is how you get overlap and “it skips every other track” complaints.
# - We keep a real STOPPING phase: send stop, then wait for the device to actually stop (or time out).
# - Spotify monitoring is not polled here. Polling costs quota. If you want accuracy, you pay for it.

import os
import threading
import time
import logging
import pychromecast
import soco
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from functools import lru_cache
from collections import deque

logger = logging.getLogger(__name__)


class SpotifyHandler:
    def __init__(self, client_id, client_secret, redirect_uri):
        cache_path = os.getenv("SPOTIFY_CACHE_PATH", "/app/.cache_volume/.spotify_cache")

        self.auth_manager = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope="user-library-read user-read-playback-state user-modify-playback-state",
            cache_path=cache_path
        )

    def get_client(self):
        token = self.auth_manager.get_cached_token()
        if not token:
            return None
        return spotipy.Spotify(auth_manager=self.auth_manager)

    def get_auth_url(self):
        return self.auth_manager.get_authorize_url()

    def process_code(self, code):
        self.auth_manager.get_access_token(code)

    def _norm(self, s):
        if not s:
            return ""
        return " ".join(str(s).strip().split())

    @lru_cache(maxsize=256)
    def search_album_art(self, artist, album):
        sp = self.get_client()
        artist = self._norm(artist)
        album = self._norm(album)

        if not sp or not artist:
            return None

        try:
            query = f'artist:"{artist}"'
            if album:
                query += f' album:"{album}"'

            results = sp.search(q=query, type="album", limit=1)
            items = results.get("albums", {}).get("items", [])
            if not items:
                return None

            images = items[0].get("images", [])
            if not images:
                return None

            return images[-1].get("url")
        except Exception as e:
            logger.debug(f"Album art lookup failed artist={artist!r} album={album!r}: {e}")
            return None


class DeviceManager:
    def __init__(self, spotify_handler):
        self.devices = {}
        self.spotify_handler = spotify_handler
        self.lock = threading.Lock()
        self.running = True
        self.scan_thread = threading.Thread(target=self._scan_loop, daemon=True)
        self.scan_thread.start()

    def _scan_loop(self):
        while self.running:
            found = {}

            try:
                chromecasts, _ = pychromecast.get_chromecasts()
                for cc in chromecasts:
                    found[cc.device.friendly_name] = {"type": "chromecast", "obj": cc}
            except Exception:
                pass

            try:
                sonos_list = soco.discover()
                if sonos_list:
                    for dev in sonos_list:
                        found[dev.player_name] = {"type": "sonos", "obj": dev}
            except Exception:
                pass

            sp = self.spotify_handler.get_client()
            if sp:
                try:
                    sp_devs = sp.devices()
                    for d in sp_devs.get("devices", []):
                        name = f"Spotify: {d['name']}"
                        found[name] = {"type": "spotify", "id": d["id"]}
                except Exception:
                    pass

            with self.lock:
                self.devices = found

            time.sleep(30)

    def get_all(self):
        with self.lock:
            return self.devices


class QueueManager:
    def __init__(self):
        self.queue = deque()
        self.lock = threading.Lock()

    def add(self, item):
        with self.lock:
            self.queue.append(item)

    def pop(self):
        with self.lock:
            if self.queue:
                return self.queue.popleft()
            return None

    def get_list(self):
        with self.lock:
            return list(self.queue)

    def clear(self):
        with self.lock:
            self.queue.clear()


class PlaybackManager:
    """
    States:
      IDLE     : current_device is None
      PLAYING  : current_device set, stop_event clear
      STOPPING : current_device set, stop_event set

    Two boring rules that save you days:
      1) Do not clear current_device in stop_playback(). Keep it so the monitor can observe STOPPING.
      2) Treat early Chromecast status as noise. Grace period handles the common IDLE-at-start lie.

    A stop timeout is included so the queue does not hang forever if a device never reports stopped.
    """

    def __init__(self, device_manager, queue_manager):
        self.dm = device_manager
        self.qm = queue_manager

        self.current_device = None
        self.current_type = None
        self.current_started_at = 0.0

        self.stop_event = threading.Event()
        self.stop_requested_at = 0.0

        self.skip_requested = False
        self.advance_on_stop = False

        self.monitor_running = True
        self.monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self.monitor_thread.start()

    def play_now(self, device_name, item):
        self.stop_playback(clear_queue=False, advance=False)
        self._dispatch_play(device_name, item)

    def next_track(self):
        self.skip_requested = True
        self.stop_playback(clear_queue=False, advance=True)

    def stop_playback(self, clear_queue=False, advance=False):
        self.stop_event.set()
        self.stop_requested_at = time.time()
        self.advance_on_stop = bool(advance)

        if clear_queue:
            self.qm.clear()

        if not advance:
            self.skip_requested = False

        if self.current_device:
            try:
                dev = self.current_device
                if dev["type"] == "chromecast":
                    dev["obj"].media_controller.stop()
                elif dev["type"] == "sonos":
                    dev["obj"].stop()
                elif dev["type"] == "spotify":
                    sp = self.dm.spotify_handler.get_client()
                    if sp:
                        sp.pause_playback()
            except Exception as e:
                logger.debug(f"Stop command failed: {e}")

    def _dispatch_play(self, device_name, item):
        devices = self.dm.get_all()
        device = devices.get(device_name)
        if not device:
            logger.error(f"Device {device_name} not found")
            return

        self.current_device = device
        self.current_type = None
        self.current_started_at = time.time()

        self.stop_event.clear()
        self.stop_requested_at = 0.0
        self.skip_requested = False
        self.advance_on_stop = False

        track_uri = item.get("track_uri")
        file_path = item.get("file_path")

        if track_uri:
            self.current_type = "spotify"
            self._play_spotify(device, track_uri)
        elif file_path:
            self.current_type = "file"
            self._play_file(device, file_path)
        else:
            logger.warning(f"Queue item has no playable content: {item}")
            self._reset_to_idle()

    def _play_spotify(self, device, uri):
        sp = self.dm.spotify_handler.get_client()
        if not sp:
            logger.error("Spotify client unavailable (not logged in?)")
            return
        try:
            if device["type"] == "spotify":
                sp.start_playback(device_id=device["id"], context_uri=uri)
            else:
                sp.start_playback(context_uri=uri)
        except Exception as e:
            logger.error(f"Spotify Play Error: {e}")

    def _play_file(self, device, url):
        if device["type"] == "chromecast":
            t = threading.Thread(target=self._cc_play, args=(device["obj"], url), daemon=True)
            t.start()
        elif device["type"] == "sonos":
            t = threading.Thread(target=self._sonos_play, args=(device["obj"], url), daemon=True)
            t.start()
        else:
            logger.warning(f"Device type {device['type']} cannot play file URLs")

    def _cc_play(self, cast, url):
        try:
            cast.wait()
            mc = cast.media_controller
            mc.play_media(url, "audio/mp3")
            mc.block_until_active()
        except Exception as e:
            logger.error(f"Chromecast error: {e}")

    def _sonos_play(self, sonos, url):
        try:
            sonos.play_uri(url)
        except Exception as e:
            logger.error(f"Sonos error: {e}")

    def _is_playing(self, dev):
        grace_seconds = float(os.getenv("PLAYBACK_GRACE_SECONDS", "4.0"))
        if self.current_started_at and (time.time() - self.current_started_at) < grace_seconds:
            return True

        try:
            if dev["type"] == "chromecast":
                state = dev["obj"].media_controller.status.player_state
                return state in ("PLAYING", "BUFFERING")
            if dev["type"] == "sonos":
                info = dev["obj"].get_current_transport_info()
                return info.get("current_transport_state") == "PLAYING"
            if dev["type"] == "spotify":
                return True
        except Exception:
            return False

        return False

    def _reset_to_idle(self):
        self.current_device = None
        self.current_type = None
        self.current_started_at = 0.0
        self.stop_event.clear()
        self.stop_requested_at = 0.0
        self.skip_requested = False
        self.advance_on_stop = False

    def _monitor_loop(self):
        poll_seconds = float(os.getenv("PLAYBACK_POLL_SECONDS", "2.0"))
        stop_timeout = float(os.getenv("PLAYBACK_STOP_TIMEOUT_SECONDS", "8.0"))

        while self.monitor_running:
            time.sleep(poll_seconds)

            if not self.current_device:
                self._play_next_in_queue()
                continue

            dev = self.current_device
            playing = self._is_playing(dev)

            if self.stop_event.is_set():
                timed_out = self.stop_requested_at and (time.time() - self.stop_requested_at) > stop_timeout
                if not playing or timed_out:
                    if timed_out:
                        logger.info("Stop timed out; assuming stopped to keep the queue moving.")
                    should_advance = self.advance_on_stop or self.skip_requested
                    self._reset_to_idle()
                    if should_advance:
                        self._play_next_in_queue()
                continue

            if not playing:
                logger.info("Track finished; advancing.")
                self._reset_to_idle()
                self._play_next_in_queue()

    def _play_next_in_queue(self):
        next_item = self.qm.pop()
        if next_item:
            logger.info(f"Advancing to: {next_item.get('title')}")
            self._dispatch_play(next_item["device_name"], next_item)
