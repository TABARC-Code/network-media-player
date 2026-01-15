# Author: TABARC-Code
#
# Notes:
# - os.path.commonprefix is string-based and will mislead you if you let it. dont ask how i know this.
# - os.path.commonpath is the correct check for “is this path under my root”.
# - Keep traversal checks dull and strict. its late and i just cannoot be botherd. appreciate how it sounds but its 4am and i am just fallling asleep

import os
import mutagen


class MediaManager:
    def __init__(self, root_path):
        self.root = os.path.abspath(root_path)
        self.valid_extensions = {".mp3", ".flac", ".wav", ".m4a", ".aac", ".ogg"}

    def _is_safe(self, path):
        abs_path = os.path.abspath(os.path.join(self.root, path))
        try:
            return os.path.commonpath([abs_path, self.root]) == self.root
        except Exception:
            return False

    def _get_meta(self, path, filename):
        meta = {"filename": filename, "title": filename, "artist": "Unknown", "album": ""}
        try:
            audio = mutagen.File(path, easy=True)
            if audio:
                meta["title"] = audio.get("title", [filename])[0]
                meta["artist"] = audio.get("artist", ["Unknown"])[0]
                meta["album"] = audio.get("album", [""])[0]
        except Exception:
            pass
        return meta

    def list_dir(self, subpath=""):
        if subpath and not self._is_safe(subpath):
            return [], []

        target = os.path.join(self.root, subpath) if subpath else self.root
        if not os.path.exists(target):
            return [], []

        folders, files = [], []
        for item in sorted(os.listdir(target)):
            full = os.path.join(target, item)
            if os.path.isdir(full):
                folders.append(item)
            elif os.path.isfile(full):
                _, ext = os.path.splitext(item)
                if ext.lower() in self.valid_extensions:
                    files.append(self._get_meta(full, item))

        return folders, files

    def get_path(self, filename):
        if not self._is_safe(filename):
            return None
        return os.path.join(self.root, filename)
