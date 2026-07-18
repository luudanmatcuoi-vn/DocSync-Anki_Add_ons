from __future__ import annotations
import hashlib
import os
import re

from aqt import mw

PLACEHOLDER = "<ảnh>"

_RE_IMG = re.compile(r'<img\b[^>]*\bsrc=["\']([^"\']+)["\'][^>]*>', re.IGNORECASE)

_RE_PLACEHOLDER_BLOCK = re.compile(
    r'<ảnh>[ \t]*(?:\n\(([^()\n]+)\))?',
    re.IGNORECASE,
)

RE_NAME_HINT = re.compile(r'^\(([^()\n]{1,120})\)$')


def media_dir() -> str:
    return mw.col.media.dir()


def file_exists(filename: str) -> bool:
    return bool(filename) and os.path.exists(os.path.join(media_dir(), filename))


def _hash_name(data: bytes, ext: str) -> str:
    digest = hashlib.sha1(data).hexdigest()[:12]
    return f"DocSync_{digest}{ext}"


def store_media(data: bytes, suggested_name: str | None, ext_hint: str = ".png") -> str:
    if suggested_name:
        suggested_name = os.path.basename(suggested_name.strip())
        if file_exists(suggested_name):
            return suggested_name
        return mw.col.media.write_data(suggested_name, data)

    if not ext_hint.startswith("."):
        ext_hint = f".{ext_hint}"
    name = _hash_name(data, ext_hint)
    if file_exists(name):
        return name
    return mw.col.media.write_data(name, data)

def placeholders_to_html_images(text: str) -> str:
    def repl(m: re.Match) -> str:
        name = m.group(1)
        return f'<img src="{name}">' if name else ""
    return _RE_PLACEHOLDER_BLOCK.sub(repl, text)
