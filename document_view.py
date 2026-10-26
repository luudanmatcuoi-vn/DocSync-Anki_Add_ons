from __future__ import annotations

import base64
import html as html_lib
import os
import re
import json

from aqt.qt import (
    QColor,
    QColorDialog,
    QFont,
    QHBoxLayout,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    qconnect,
)

from . import media

_RE_IMG_SRC = re.compile(r'<img\b[^>]*\bsrc=["\']([^"\']+)["\'][^>]*>', re.IGNORECASE)
FIELD_SEP = ">>>"


def _line(text: str) -> str:
    return html_lib.escape(text) + "<br>"


def _image_to_data_uri(filename: str, directory: str | None = None) -> str | None:
    path = os.path.join(directory or media.media_dir(), filename)
    if not os.path.exists(path):
        return None
    ext = os.path.splitext(filename)[1].lstrip(".").lower() or "png"
    mime = "jpeg" if ext in ("jpg", "jpeg") else ext
    with open(path, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:image/{mime};base64,{b64}"


def _embed_real_images(field_html: str, mode: str = "media", directory: str | None = None, images: dict | None = None) -> str:
    def repl(m: re.Match) -> str:
        src = m.group(1)
        if src.startswith("data:") or src.startswith("file://"):
            return m.group(0)

        if mode == "temp":
            import shutil, tempfile
            from pathlib import Path
            path = os.path.join(directory or media.media_dir(), src)
            if not os.path.exists(path):
                return m.group(0)

            temp_path = os.path.join(tempfile.gettempdir(), src)
            if not os.path.exists(temp_path):
                shutil.copy2(path, temp_path)

            file_uri = Path(temp_path).as_uri()
            return f'<img src="{file_uri}"><br>{html_lib.escape(f"({src})")}'

        if mode == "media":
            from pathlib import Path
            path = os.path.join(directory or media.media_dir(), src)
            if not os.path.exists(path):
                return html_lib.escape(f"({src})")
            file_uri = Path(path).as_uri()
            return f'<img src="{file_uri}"><br>{html_lib.escape(f"({src})")}'

        data_uri = images.get(src) if images is not None else _image_to_data_uri(src, directory)
        if not data_uri:
            return html_lib.escape(f"({src})")
        return f'<img src="{data_uri}"><br>{html_lib.escape(f"({src})")}'
    return _RE_IMG_SRC.sub(repl, field_html)

def encode_config(cfg: dict) -> str:
    return json.dumps(cfg, ensure_ascii=False)
    
def build_config_block(cfg: dict, position: str = "start") -> str:
    if not cfg:
        return ""
    return f"### START_CONFIG\n{encode_config(cfg)}\n### END_CONFIG\n"

def build_preview_html(cfg: dict, cards: list[dict], mode: str = "media", directory: str | None = None) -> str:
    images = None
    if mode == "base64":
        from concurrent.futures import ThreadPoolExecutor
        directory = directory or media.media_dir()
        names = sorted({m.group(1) for card in cards for field in card['fields']
                        for m in _RE_IMG_SRC.finditer(field)
                        if not m.group(1).startswith(('data:', 'file:', 'http:', 'https:'))})
        with ThreadPoolExecutor(max_workers=4) as pool:
            images = dict(zip(names, pool.map(lambda name: _image_to_data_uri(name, directory), names)))
    parts: list[str] = []

    cfg_block = build_config_block(cfg)
    if cfg_block:
        for line in cfg_block.rstrip("\n").split("\n"):
            parts.append(_line(line))

    for card in cards:
        nid = card.get("nid")
        parts.append(_line(f"===[{nid}]" if nid else "==="))
        for i, field_html in enumerate(card["fields"]):
            if i > 0:
                parts.append(_line(FIELD_SEP))
            # Truyền tham số mode vào quá trình render ảnh
            parts.append(_embed_real_images(field_html, mode, directory, images) + "<br>")
        parts.append("<br>")
        
    if parts and parts[-1] == "<br>":
        parts = parts[:-1]

    return "".join(parts)

class DocumentEditor(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.edit = QTextEdit()
        self.edit.setAcceptRichText(True)
        layout.addWidget(self.edit)

    def load_html(self, html: str) -> None:
        self.edit.setHtml(html)

    def copy_rich_to_clipboard(self) -> None:
        cursor = self.edit.textCursor()
        self.edit.selectAll()
        self.edit.copy()
        self.edit.setTextCursor(cursor)
