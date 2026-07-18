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


def _image_to_data_uri(filename: str) -> str | None:
    path = os.path.join(media.media_dir(), filename)
    if not os.path.exists(path):
        return None
    ext = os.path.splitext(filename)[1].lstrip(".").lower() or "png"
    mime = "jpeg" if ext in ("jpg", "jpeg") else ext
    with open(path, "rb") as f:
        data = f.read()
    b64 = base64.b64encode(data).decode("ascii")
    return f"data:image/{mime};base64,{b64}"


def _embed_real_images(field_html: str) -> str:
    def repl(m: re.Match) -> str:
        src = m.group(1)
        if src.startswith("data:"):
            return m.group(0)
        data_uri = _image_to_data_uri(src)
        if not data_uri:
            return m.group(0)
        return f'<img src="{data_uri}"><br>{html_lib.escape(f"({src})")}'
    return _RE_IMG_SRC.sub(repl, field_html)


def encode_config(cfg: dict) -> str:
    return json.dumps(cfg, ensure_ascii=False)
    
def build_config_block(cfg: dict, position: str = "start") -> str:
    if not cfg:
        return ""
    return f"### START_CONFIG\n{encode_config(cfg)}\n### END_CONFIG\n"
    
def build_preview_html(cfg: dict, cards: list[dict]) -> str:
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
            parts.append(_embed_real_images(field_html) + "<br>")
        parts.append("<br>")
        
    if parts[-1] == "<br>":
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
