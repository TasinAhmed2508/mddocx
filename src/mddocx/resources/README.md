# Resource pipeline

`resolver.py` safely acquires local, inline, and remote image bytes. `media.py`
identifies raster content from decoded bytes rather than filenames or HTTP headers.
`models.py` defines the typed success/fallback boundary used by renderers.

Persistent cache entries contain validated prepared images and are keyed by URL and
SVG/WebP conversion settings. Unreadable, invalid, or oversized entries are cache
misses. A successful download atomically repairs the matching entry. Older cache
keys are ignored and rebuilt on demand.
