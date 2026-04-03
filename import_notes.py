"""
TxtSync — Import Notes from Txt

Hooks into the main window Tools menu. Parses the custom text format,
updates matching notes in the collection, and shows a result dialog.
"""

import re

from aqt import mw
from aqt.qt import *
from aqt.utils import tooltip, showText, askUser

from .convert import text_to_html


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
_RE_NOTE_HEADER = re.compile(r'^\[\[(\d+)\]\]\s*$', re.MULTILINE)
_RE_FIELD_HEADER = re.compile(r'^\[([^\[\]]+)\]\s*$', re.MULTILINE)


def parse_txt(text: str) -> list[dict]:
    """Parse the custom format into a list of note dicts.

    Returns:
        [{"nid": int, "fields": {"FieldName": "content", ...}}, ...]
    """
    notes: list[dict] = []

    # Split into note blocks by [[nid]]
    note_splits = _RE_NOTE_HEADER.split(text)
    # note_splits: ['preamble', 'nid1', 'body1', 'nid2', 'body2', ...]

    i = 1  # skip preamble
    while i < len(note_splits) - 1:
        nid_str = note_splits[i].strip()
        body = note_splits[i + 1]
        i += 2

        try:
            nid = int(nid_str)
        except ValueError:
            continue

        # Parse fields within the body
        field_splits = _RE_FIELD_HEADER.split(body)
        # field_splits: ['preamble', 'FieldName1', 'content1', 'FieldName2', 'content2', ...]

        fields: dict[str, str] = {}
        j = 1
        while j < len(field_splits) - 1:
            fname = field_splits[j].strip()
            fcontent = field_splits[j + 1].strip()
            fields[fname] = fcontent
            j += 2

        notes.append({"nid": nid, "fields": fields})

    return notes


# ---------------------------------------------------------------------------
# Import logic
# ---------------------------------------------------------------------------
def do_import(parsed_notes: list[dict]) -> dict:
    """Apply parsed notes to the collection.

    Returns a result dict with detailed counts and note ID lists.
    """
    updated_nids: list[int] = []
    error_nids: list[int] = []               # note not found in collection
    skip_no_change_nids: list[int] = []       # note found but no field changed
    skip_missing_fields: list[str] = []       # "[[nid]]: [field]" entries
    skip_missing_field_nids: set[int] = set() # unique nids with missing fields

    mw.checkpoint("TxtSync Import")

    for entry in parsed_notes:
        nid = entry["nid"]

        try:
            note = mw.col.get_note(nid)
        except Exception:
            error_nids.append(nid)
            continue

        note_field_names = note.keys()
        changed = False

        for fname, fvalue in entry["fields"].items():
            if fname in note_field_names:
                new_html = text_to_html(fvalue)
                if note[fname] != new_html:
                    note[fname] = new_html
                    changed = True
            else:
                skip_missing_fields.append(f"[[{nid}]]: [{fname}]")
                skip_missing_field_nids.add(nid)

        if changed:
            mw.col.update_note(note)
            updated_nids.append(nid)
        else:
            skip_no_change_nids.append(nid)

    mw.reset()
    return {
        "total": len(parsed_notes),
        "updated_nids": updated_nids,
        "error_nids": error_nids,
        "skip_no_change_nids": skip_no_change_nids,
        "skip_missing_fields": skip_missing_fields,
        "skip_missing_field_nids": sorted(skip_missing_field_nids),
    }


def _build_result_text(result: dict) -> str:
    """Build the detailed result string for the import result dialog."""
    sep = "─" * 50
    lines: list[str] = []

    total = result["total"]
    updated = result["updated_nids"]
    errors = result["error_nids"]
    no_change = result["skip_no_change_nids"]
    missing_fields = result["skip_missing_fields"]
    missing_field_nids = result["skip_missing_field_nids"]

    skip_count = len(no_change) + len(missing_field_nids)

    # ── Summary ──
    lines.append("IMPORT RESULT")
    lines.append(sep)
    lines.append(f"Total notes in text:   {total}")
    lines.append(f"Updated:               {len(updated)}")
    lines.append(f"Errors (not found):    {len(errors)}")
    lines.append(f"Skipped:               {skip_count}")
    lines.append(f"  • No content change: {len(no_change)}")
    lines.append(f"  • Missing fields:    {len(missing_field_nids)} note(s), {len(missing_fields)} field(s)")
    lines.append("")

    # ── Updated ──
    if updated:
        lines.append(sep)
        lines.append(f"UPDATED ({len(updated)})")
        lines.append(sep)
        for nid in updated:
            lines.append(f"  [[{nid}]]")
        lines.append("")

    # ── Errors ──
    if errors:
        lines.append(sep)
        lines.append(f"ERROR — NOTE NOT FOUND ({len(errors)})")
        lines.append(sep)
        for nid in errors:
            lines.append(f"  [[{nid}]]")
        lines.append("")

    # ── Skipped: no change ──
    if no_change:
        lines.append(sep)
        lines.append(f"SKIPPED — NO CONTENT CHANGE ({len(no_change)})")
        lines.append(sep)
        for nid in no_change:
            lines.append(f"  [[{nid}]]")
        lines.append("")

    # ── Skipped: missing fields ──
    if missing_fields:
        lines.append(sep)
        lines.append(f"SKIPPED — MISSING FIELD ({len(missing_fields)} field(s) across {len(missing_field_nids)} note(s))")
        lines.append(sep)
        for entry in missing_fields:
            lines.append(f"  {entry}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Import Dialog
# ---------------------------------------------------------------------------
class ImportDialog(QDialog):
    """Dialog for pasting text and importing into Anki."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("TxtSync — Import")
        self.setMinimumWidth(600)
        self.setMinimumHeight(500)
        self.resize(700, 600)

        layout = QVBoxLayout(self)

        label = QLabel("Paste the exported text below, then click Import:")
        layout.addWidget(label)

        # Text area
        self.text_edit = QPlainTextEdit()
        self.text_edit.setFont(QFont("Consolas", 10))
        self.text_edit.setPlaceholderText(
            "[[note_id]]\n[FieldName]\nfield content\n..."
        )
        layout.addWidget(self.text_edit)

        # Buttons
        btn_layout = QHBoxLayout()

        self.load_btn = QPushButton("📂 Load from File")
        self.load_btn.clicked.connect(self._load_file)
        btn_layout.addWidget(self.load_btn)

        self.import_btn = QPushButton("⬇️ Import")
        self.import_btn.clicked.connect(self._import)
        btn_layout.addWidget(self.import_btn)

        self.close_btn = QPushButton("Close")
        self.close_btn.clicked.connect(self.close)
        btn_layout.addWidget(self.close_btn)

        layout.addLayout(btn_layout)

    def _load_file(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open Exported Txt",
            "",
            "Text Files (*.txt);;All Files (*)",
        )
        if not path:
            return
        try:
            with open(path, "r", encoding="utf-8") as f:
                self.text_edit.setPlainText(f.read())
            tooltip(f"Loaded {path}")
        except Exception as e:
            tooltip(f"Error loading file: {e}")

    def _import(self):
        text = self.text_edit.toPlainText().strip()
        if not text:
            tooltip("Nothing to import.")
            return

        # Parse first to show confirmation
        parsed = parse_txt(text)
        if not parsed:
            tooltip("No valid note blocks found.")
            return

        # Confirmation
        ok = askUser(
            f"This will modify up to {len(parsed)} note(s).\nProceed?",
            parent=self,
            defaultno=False,
        )
        if not ok:
            return

        # Do the import
        result = do_import(parsed)

        # Show detailed result
        self.close()
        showText(
            _build_result_text(result),
            title="TxtSync — Import Result",
            minWidth=500,
            minHeight=400,
        )


# ---------------------------------------------------------------------------
# Entry point (called from Tools menu)
# ---------------------------------------------------------------------------
def import_notes_from_txt() -> None:
    """Open the import dialog."""
    dlg = ImportDialog(mw)
    dlg.exec()
