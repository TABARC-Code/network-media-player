# network-media-player
A small Flask service to browse a local music folder and play tracks to Chromecast, Sonos, or Spotify Connect.

# TABARC-Code Network Media Player

<p align="center">
  <img src=".branding/tabarc-icon.svg" width="180" alt="TABARC-Code Icon">
</p>

A small Flask service to browse a local music folder and play tracks to Chromecast, Sonos, or Spotify Connect.

Includes:
- Local library browsing with metadata (mutagen)
- Spotify OAuth session for cover art lookups
- Lazy cover art loading with a concurrency cap
- Queue with auto-advance
- Paranoid playback monitor to avoid Chromecast race conditions
- I created for a simply run mediaa [player so can run light on a system. appreciate lots of more complex systems but this is a nicee lite low system app. 

Plugin URI: https://github.com/TABARC-Code/

## Quick start

1) Copy `.env.example` to `.env` and set:
- `HOST_IP`
- Spotify credentials.
- `MEDIA_ROOT` if you need it'

2) Update the music volume in `docker-compose.yml`:
- Replace `/path/to/your/music` with a real folder on the host.'

3) Start:

```bash
docker-compose up -d --build

## Open:

http://YOUR_HOST_IP:5000

### Cover art placeholder

The UI expects a placeholder file at:

app/static/default_album.png

A simple 1x1 PNG is provided in this repo. Replace it with any square image you like.

### Notes on monitoring

Chromecast status can be unreliable at start of playback.
We use:

a grace period (PLAYBACK_GRACE_SECONDS)

a STOPPING state (do not advance until the device is actually stopped)

a stop timeout (PLAYBACK_STOP_TIMEOUT_SECONDS) to prevent dead queues

If you want more responsiveness, lower PLAYBACK_POLL_SECONDS, but do not pretend that comes free
