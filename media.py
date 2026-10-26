from __future__ import annotations
import uuid
import os
import re

from aqt import mw

def media_dir() -> str:
    return mw.col.media.dir()


def file_exists(filename: str) -> bool:
    return bool(filename) and os.path.exists(os.path.join(media_dir(), filename))


def _random_name(ext: str) -> str:
    digest = uuid.uuid4().hex
    return f"DocSync_{digest}{ext}"


def store_media(data: bytes, suggested_name: str | None, ext_hint: str = ".png") -> str:
    if suggested_name:
        suggested_name = os.path.basename(suggested_name.strip())
        if file_exists(suggested_name):
            return suggested_name
        return mw.col.media.write_data(suggested_name, data)

    if not ext_hint.startswith("."):
        ext_hint = f".{ext_hint}"
    name = _random_name(ext_hint)
    if file_exists(name):
        return name
    return mw.col.media.write_data(name, data)
