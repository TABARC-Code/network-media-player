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

