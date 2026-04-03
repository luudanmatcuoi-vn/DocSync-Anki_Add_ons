"""
TxtSync — Export Notes to Txt

Hooks into the browser menu. Exports selected notes to the custom text format
and shows the result in a dialog with Copy and Save buttons.
"""

import os

from aqt import mw
from aqt.qt import *
from aqt.browser import Browser
from aqt.utils import tooltip, getSaveFile

from .convert import html_to_text


# ---------------------------------------------------------------------------
# Format builder
# ---------------------------------------------------------------------------
def build_export_text(note_ids: list[int]) -> str:
    """Build the full export string for a list of note IDs."""
    blocks: list[str] = []

    for nid in note_ids:
        note = mw.col.get_note(nid)
        field_names = note.keys()

        lines: list[str] = []
        lines.append(f"[[{nid}]]")

        for fname in field_names:
            raw_html = note[fname]
            converted = html_to_text(raw_html)
            lines.append(f"[{fname}]")
            lines.append(converted)

        blocks.append('\n'.join(lines))

    return '\n\n'.join(blocks) + '\n'


# ---------------------------------------------------------------------------
# Export Dialog
# ---------------------------------------------------------------------------
class ExportDialog(QDialog):
    """Shows the exported text with Copy and Save buttons."""

    def __init__(self, text: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TxtSync — Export")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self.resize(700, 600)

        self._text = text

        layout = QVBoxLayout(self)

        # Text area
        self.text_edit = QPlainTextEdit()
        self.text_edit.setPlainText(text)
        self.text_edit.setReadOnly(True)
        self.text_edit.setFont(QFont("Consolas", 10))
        layout.addWidget(self.text_edit)

        # Buttons
        btn_layout = QHBoxLayout()

        self.copy_btn = QPushButton("📋 Copy to Clipboard")
        self.copy_btn.clicked.connect(self._copy)
        btn_layout.addWidget(self.copy_btn)

        self.save_btn = QPushButton("💾 Save to File")
        self.save_btn.clicked.connect(self._save)
        btn_layout.addWidget(self.save_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)

    def _copy(self):
        QApplication.clipboard().setText(self._text)
        tooltip("Copied to clipboard!")

    def _save(self):
        path = getSaveFile(
            self,
            title="Save Exported Notes",
            dir_description="txtsync_export",
            key="txtSyncExport",
            ext=".txt",
        )
        if not path:
            return
        # Ensure .txt extension
        if not path.endswith(".txt"):
            path += ".txt"
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self._text)
            tooltip(f"Saved to {os.path.basename(path)}")
        except Exception as e:
            tooltip(f"Error saving file: {e}")


# ---------------------------------------------------------------------------
# Entry point (called from browser menu)
# ---------------------------------------------------------------------------
def export_selected_notes(browser: Browser) -> None:
    """Export all selected notes to txt format and show in a dialog."""
    note_ids = browser.selectedNotes()
    if not note_ids:
        tooltip("Please select at least one note.")
        return

    text = build_export_text(note_ids)
    dlg = ExportDialog(text, browser)
    dlg.exec()
