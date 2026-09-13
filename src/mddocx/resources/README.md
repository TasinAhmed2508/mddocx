# Resource pipeline

`resolver.py` safely acquires local, inline, and remote image bytes. `media.py`
identifies raster content from decoded bytes rather than filenames or HTTP headers.
`models.py` defines the typed success/fallback boundary used by renderers.
