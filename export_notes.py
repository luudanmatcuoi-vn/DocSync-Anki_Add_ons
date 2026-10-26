from __future__ import annotations

from aqt import mw
from aqt.browser import Browser
from aqt.qt import QObject, QThread, pyqtSignal, QCheckBox, QDialogButtonBox, QScrollArea, QWidget, QDialog, QHBoxLayout, QPushButton, QVBoxLayout, QComboBox, QLabel, qconnect
from aqt.utils import tooltip

from .clipboard_native import write_clipboard_html
from . import media
from .document_view import DocumentEditor, build_preview_html


class RenderWorker(QObject):
    finished = pyqtSignal(str)

    def __init__(self, cfg, cards, mode, directory, owner):
        super().__init__()
        self.args = cfg, cards, mode, directory
        self.owner = owner

    def run(self):
        try:
            # Build all selected notes without passing them through a Qt document.
            html = build_preview_html(*self.args)
            write_clipboard_html(html, self.owner)
            self.finished.emit("")
        except Exception as exc:
            self.finished.emit(str(exc))


def preview_cards(cards):
    return cards[:20] if len(cards) > 100 else cards


class FieldSelectionDialog(QDialog):
    def __init__(self, fields, selected, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select fields to export")
        layout = QVBoxLayout(self)
        content = QWidget()
        checks_layout = QVBoxLayout(content)
        self.checks = []
        for name in fields:
            checkbox = QCheckBox(name)
            checkbox.setChecked(name in selected)
            checks_layout.addWidget(checkbox)
            self.checks.append(checkbox)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        layout.addWidget(scroll)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        for checkbox in self.checks:
            checkbox.toggled.connect(self._validate)
        self._validate()

    def _validate(self):
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(bool(self.selected_fields()))

    def selected_fields(self):
        return [checkbox.text() for checkbox in self.checks if checkbox.isChecked()]


def select_card_fields(cards, names, selected):
    indices = [names.index(name) for name in selected]
    return [{"nid": card["nid"], "fields": [card["fields"][i] for i in indices]} for card in cards]


class ExportDialog(QDialog):
    def __init__(self, note_ids: list[int], parent=None):
        super().__init__(parent)
        self.setWindowTitle("DocSync — Export")
        self.resize(800, 700)

        outer = QVBoxLayout(self)

        cards = []
        named_cards = []
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
            named_cards.append((nid, dict(note.items())))

        # A single config field list must map identically for every exported note.
        cfg_fields = [name for name in (cfg_fields or [])
                      if all(name in fields for _, fields in named_cards)]
        if not cfg_fields:
            raise ValueError("Selected notes have no common fields. Select notes with matching fields.")
        cards = [{"nid": nid, "fields": [fields[name] for name in cfg_fields]}
                 for nid, fields in named_cards]
        cfg = {}
        if cfg_notetype:
            cfg["notetype"] = cfg_notetype
            cfg["deck"] = cfg_deck
            cfg["fields"] = cfg_fields
        self.cfg = cfg
        self.all_cards = cards
        self.available_fields = list(cfg_fields)
        self.cards = cards
        self.select_fields_btn = QPushButton("Select fields…")
        outer.addWidget(self.select_fields_btn)
        qconnect(self.select_fields_btn.clicked, self._select_fields)
        self.doc_editor = DocumentEditor(self)
        self.doc_editor.load_html(build_preview_html(self.cfg, preview_cards(self.cards), mode="media"))
        self.doc_editor.edit.setReadOnly(True)
        outer.addWidget(self.doc_editor)
        if len(self.cards) > 100:
            notice = QLabel(f"Preview shows only the first 20 of {len(self.cards)} notes. "
                            "Click Copy to Clipboard to copy all selected notes.")
            notice.setWordWrap(True)
            font = notice.font()
            font.setPointSizeF(max(7, font.pointSizeF() - 1))
            notice.setFont(font)
            outer.addWidget(notice)
        self.status_label = QLabel("")
        outer.addWidget(self.status_label)
        
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Copy images mode:"))
        self.mode_box = QComboBox()
        self.mode_box.addItem("Media paths (default)", "media")
        self.mode_box.addItem("Base64 images", "base64")
        mode_row.addWidget(self.mode_box)
        outer.addLayout(mode_row)
        

        btn_row = QHBoxLayout()
        self.copy_btn = copy_btn = QPushButton("📋 Copy to Clipboard (all notes)")
        close_btn = QPushButton("Close")
        btn_row.addWidget(copy_btn)
        btn_row.addWidget(close_btn)
        outer.addLayout(btn_row)

        self.thread = None
        qconnect(copy_btn.clicked, self._copy)
        qconnect(close_btn.clicked, self.close)

    def _select_fields(self):
        dialog = FieldSelectionDialog(self.available_fields, self.cfg['fields'], self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        selected = dialog.selected_fields()
        self.cards = select_card_fields(self.all_cards, self.available_fields, selected)
        self.cfg = {**self.cfg, "fields": selected}
        self.doc_editor.load_html(build_preview_html(self.cfg, preview_cards(self.cards), mode="media"))
        self.status_label.setText("Fields updated. Copy to Clipboard to export all notes.")

    def _copy(self):
        if self.thread is not None and self.thread.isRunning():
            return
        self.status_label.setText(f"Preparing and copying all {len(self.cards)} notes…")
        self.copy_btn.setEnabled(False)
        self.mode_box.setEnabled(False)
        self.select_fields_btn.setEnabled(False)
        self.thread = QThread(self)
        self.worker = RenderWorker(self.cfg, self.cards, self.mode_box.currentData(), media.media_dir(), int(self.winId()))
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self._rendered)
        self.thread.finished.connect(self._copy_finished)
        self.worker.finished.connect(self.thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.thread.start()

    def _rendered(self, error):
        from aqt.utils import showText
        if error:
            self.status_label.setText("Copy failed. You can retry.")
            showText(error, title="DocSync — Export failed")
        else:
            self.status_label.setText(f"Copied all {len(self.cards)} notes.")
            tooltip("Copied all selected notes")

    def _copy_finished(self):
        self.copy_btn.setEnabled(True)
        self.mode_box.setEnabled(True)
        self.select_fields_btn.setEnabled(True)

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


def export_selected_notes(browser: Browser) -> None:
    note_ids = browser.selectedNotes()
    if not note_ids:
        tooltip("Please select at least one note.")
        return
    try:
        dlg = ExportDialog(note_ids, browser)
    except ValueError as exc:
        from aqt.utils import showText
        showText(str(exc), title="DocSync — Export")
        return
    dlg.exec()
