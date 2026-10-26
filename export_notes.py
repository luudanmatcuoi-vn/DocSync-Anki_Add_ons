from __future__ import annotations

import os

from aqt import mw
from aqt.browser import Browser
from aqt.qt import QObject, QThread, pyqtSignal, QApplication, QMimeData, QDialog, QHBoxLayout, QPushButton, QVBoxLayout, QComboBox, QLabel, qconnect
from aqt.utils import tooltip

from . import media
from .document_view import DocumentEditor, build_preview_html


class RenderWorker(QObject):
    finished = pyqtSignal(str, str)

    def __init__(self, cfg, cards, mode, directory):
        super().__init__()
        self.args = cfg, cards, mode, directory

    def run(self):
        try:
            # No Qt widgets or Anki collection access on the worker thread.
            self.finished.emit(build_preview_html(*self.args), "")
        except Exception as exc:
            self.finished.emit("", str(exc))


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
        self.rendered_html = build_preview_html(self.cfg, self.cards, mode="media")
        self.doc_editor.load_html(self.rendered_html)
        outer.addWidget(self.doc_editor)
        
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Copy images mode:"))
        self.mode_box = QComboBox()
        self.mode_box.addItem("Media paths (default)", "media")
        self.mode_box.addItem("Base64 images", "base64")
        mode_row.addWidget(self.mode_box)
        outer.addLayout(mode_row)
        

        btn_row = QHBoxLayout()
        self.copy_btn = copy_btn = QPushButton("📋 Copy rich-text to Clipboard")
        close_btn = QPushButton("Close")
        btn_row.addWidget(copy_btn)
        btn_row.addWidget(close_btn)
        outer.addLayout(btn_row)

        self.thread = None
        qconnect(self.mode_box.currentIndexChanged, self._render)
        qconnect(copy_btn.clicked, self._copy)
        qconnect(close_btn.clicked, self.close)

    def _render(self):
        self.copy_btn.setEnabled(False)
        self.mode_box.setEnabled(False)
        self.thread = QThread(self)
        self.worker = RenderWorker(self.cfg, self.cards, self.mode_box.currentData(), media.media_dir())
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._rendered)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.start()

    def _rendered(self, html, error):
        from aqt.utils import showText
        if error:
            showText(error, title="DocSync — Export failed")
        else:
            self.rendered_html = html
            # Avoid QTextEdit parsing/decoding a huge base64 document on the GUI thread.
            if self.mode_box.currentData() == "media":
                self.doc_editor.load_html(html)
        self.copy_btn.setEnabled(not bool(error))
        self.mode_box.setEnabled(True)

    def reject(self):
        if self.thread is not None and self.thread.isRunning():
            tooltip("Image conversion is running; please wait.")
            return
        super().reject()

    def closeEvent(self, event):
        if self.thread is not None and self.thread.isRunning():
            event.ignore()
            return
        super().closeEvent(event)

    def _copy(self):
        mime = QMimeData()
        mime.setHtml(self.rendered_html)
        mime.setText(self.doc_editor.edit.toPlainText())
        QApplication.clipboard().setMimeData(mime)
        tooltip("Copied")

def export_selected_notes(browser: Browser) -> None:
    note_ids = browser.selectedNotes()
    if not note_ids:
        tooltip("Please select at least one note.")
        return
    dlg = ExportDialog(note_ids, browser)
    dlg.exec()
