from __future__ import annotations

import os

from aqt import mw
from aqt.browser import Browser
from aqt.qt import QDialog, QHBoxLayout, QPushButton, QVBoxLayout, QComboBox, QLabel, qconnect
from aqt.utils import tooltip

from .document_view import DocumentEditor, build_preview_html


class ExportDialog(QDialog):
    def __init__(self, note_ids: list[int], parent=None):
        super().__init__(parent)
        self.setWindowTitle("DocSync — Export")
        self.resize(800, 700)

        outer = QVBoxLayout(self)

        cards = []
        cfg_notetype = None
        cfg_fields = None
        cfg_deck = None
        for nid in note_ids:
            note = mw.col.get_note(nid)
            field_names = list(note.keys())
            if cfg_notetype is None:
                cfg_notetype = note.note_type()["name"]
                cfg_fields = field_names
                # cards_first_did = mw.col.decks.current()["id"]
                # cfg_deck = mw.col.decks.name(cards_first_did)
                note_cards = note.cards()
                if note_cards:
                    cfg_deck = mw.col.decks.name(note_cards[0].did)
                else:
                    cfg_deck = mw.col.decks.name(mw.col.decks.current()["id"])
            cards.append({"nid": nid, "fields": [note[f] for f in field_names]})

        cfg = {}
        if cfg_notetype:
            cfg["notetype"] = cfg_notetype
            cfg["deck"] = cfg_deck
            cfg["fields"] = cfg_fields
        self.cfg = cfg
        self.cards = cards
        self.doc_editor = DocumentEditor(self)
        self.doc_editor.load_html(build_preview_html(self.cfg, self.cards, mode="base64"))
        outer.addWidget(self.doc_editor)
        
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Copy images mode:"))
        self.mode_box = QComboBox()
        self.mode_box.addItem("Base64 (slower but safter)", "base64")
        self.mode_box.addItem("Media (from anki media - faster)", "media")
        mode_row.addWidget(self.mode_box)
        outer.addLayout(mode_row)
        

        btn_row = QHBoxLayout()
        copy_btn = QPushButton("📋 Copy rich-text to Clipboard")
        close_btn = QPushButton("Close")
        btn_row.addWidget(copy_btn)
        btn_row.addWidget(close_btn)
        outer.addLayout(btn_row)

        qconnect(copy_btn.clicked, self._copy)
        qconnect(close_btn.clicked, self.close)

    def _copy(self):
        mode = self.mode_box.currentData()  # "base64" hoặc "media"

        # 1. Render theo mode đã chọn để copy
        self.doc_editor.load_html(build_preview_html(self.cfg, self.cards, mode=mode))
        self.doc_editor.copy_rich_to_clipboard()

        # 2. Render phục hồi lại dạng Base64 cho UI Preview
        self.doc_editor.load_html(build_preview_html(self.cfg, self.cards, mode="base64"))
        tooltip("Coppied")

def export_selected_notes(browser: Browser) -> None:
    note_ids = browser.selectedNotes()
    if not note_ids:
        tooltip("Please select at least one note.")
        return
    dlg = ExportDialog(note_ids, browser)
    dlg.exec()
