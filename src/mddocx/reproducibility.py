from __future__ import annotations

from io import BytesIO
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from .config import ReproducibilityConfig


def make_reproducible_docx(blob: bytes, config: ReproducibilityConfig) -> bytes:
    if not config.enabled:
        return blob
    source = BytesIO(blob)
    output = BytesIO()
    with ZipFile(source, "r") as zin, ZipFile(output, "w", compression=ZIP_DEFLATED, compresslevel=9) as zout:
        infos = zin.infolist()
        if config.sort_package_parts:
            infos = sorted(infos, key=lambda item: item.filename)
        for old in infos:
            data = zin.read(old.filename)
            info = ZipInfo(old.filename, date_time=config.zip_timestamp)
            info.compress_type = ZIP_DEFLATED
            info.comment = old.comment
            info.extra = b""
            info.internal_attr = old.internal_attr
            info.external_attr = old.external_attr
            info.create_system = old.create_system
            zout.writestr(info, data, compress_type=ZIP_DEFLATED, compresslevel=9)
    return output.getvalue()
