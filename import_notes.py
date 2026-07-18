from __future__ import annotations

import os
import re
import unicodedata

from aqt import mw
from aqt.qt import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    qconnect,
)
from aqt.editor import Editor
from aqt.qt import (
    QByteArray,
    QColor,
    QFont,
    QTextCharFormat,
    QTextCursor,
    QTextDocument,
    QUrl,
)
from aqt.utils import askUser, showText, tooltip

from .document_view import DocumentEditor
from .note_resolver import ResolutionContext
from .sync_pipeline import parse_pasted_html
from . import media


# ---------------------------------------------------------------------------
# A) Anki HTML  <->  sync-text field content
# ---------------------------------------------------------------------------
_RE_BR = re.compile(r'<br\s*/?>', re.IGNORECASE)
_RE_DIV = re.compile(r'<div[^>]*>(.*?)</div>', re.IGNORECASE | re.DOTALL)

class _EditorShim(Editor):
    def __init__(self):
        self.mw = mw

def sync_text_to_anki_html(text: str) -> str:
    if not text:
        return ""
    result = media.placeholders_to_html_images(text)
    result = result.replace("\n", "<br>")
    result = unicodedata.normalize("NFC", result)
    result = result.replace("\x00", "")
    try:
        result = Editor.mungeHTML(_EditorShim(), result)
    except Exception:
        pass
    return result

# ---------------------------------------------------------------------------
# Import logic
# ---------------------------------------------------------------------------
def do_import(cfg: dict, cards: list[dict]) -> dict:
    updated_nids = []
    added_nids = []
    error_nids = []
    skip_no_change_nids = []
    skip_missing_fields = []
    skip_missing_field_nids = set()
    resolution_errors = []

    # Khởi tạo cơ chế ghi nhớ. Nếu thiếu, tự động fallback lấy từ lần nhập/khối ngay trước đó
    ctx = ResolutionContext(cfg)
    mw.checkpoint("DocSync Import")

    for entry in cards:
        nid = entry["nid"]
        raw_fields = entry["fields"]

        if nid:
            # ---- Update existing note ----
            try:
                note = mw.col.get_note(nid)
            except Exception:
                error_nids.append(nid)
                continue

            field_names = cfg.get("fields") or list(note.keys())
            changed = False
            
            # zip() sẽ linh hoạt ngắt tại vị trí ngắn hơn. Nếu raw_fields có 2 trường (nhưng Note có 5), nó chỉ điền đúng 2 trường đầu.
            for fname, raw in zip(field_names, raw_fields):
                if fname not in note:
                    skip_missing_fields.append(f"[[{nid}]]: [{fname}]")
                    skip_missing_field_nids.add(nid)
                    continue
                new_html = sync_text_to_anki_html(raw)
                if note[fname] != new_html:
                    note[fname] = new_html
                    changed = True

            if changed:
                mw.col.update_note(note)
                updated_nids.append(nid)
            else:
                skip_no_change_nids.append(nid)

        else:
            # ---- Add new note (Ghi nhớ Note Type & Deck logic) ----
            resolved = ctx.resolve_notetype_and_deck()
            if resolved is None:
                resolution_errors.append("Canceled selecting Note Type/Deck — skip new card.")
                continue
            notetype_name, deck_name = resolved

            model = mw.col.models.by_name(notetype_name)
            deck = mw.col.decks.by_name(deck_name)
            if not model or not deck:
                resolution_errors.append(
                    f"Could not find Note Type '{notetype_name}' or Deck '{deck_name}'."
                )
                continue

            field_names = ctx.resolve_field_names(notetype_name, len(raw_fields))

            new_note = mw.col.new_note(model)
            
            # Dùng lại cơ chế zip linh hoạt field
            for fname, raw in zip(field_names, raw_fields):
                if fname in new_note:
                    new_note[fname] = sync_text_to_anki_html(raw)
            mw.col.add_note(new_note, deck["id"])
            added_nids.append(new_note.id)

    mw.reset()
    return {
        "total": len(cards),
        "updated_nids": updated_nids,
        "added_nids": added_nids,
        "error_nids": error_nids,
        "skip_no_change_nids": skip_no_change_nids,
        "skip_missing_fields": skip_missing_fields,
        "skip_missing_field_nids": sorted(skip_missing_field_nids),
        "resolution_errors": resolution_errors,
    }


def _build_result_text(result: dict) -> str:
    sep = "─" * 50
    lines: list[str] = []

    total = result["total"]
    updated = result["updated_nids"]
    added = result["added_nids"]
    errors = result["error_nids"]
    no_change = result["skip_no_change_nids"]
    missing_fields = result["skip_missing_fields"]
    missing_field_nids = result["skip_missing_field_nids"]
    resolution_errors = result["resolution_errors"]

    skip_count = len(no_change) + len(missing_field_nids)

    lines.append("IMPORT RESULT")
    lines.append(sep)
    lines.append(f"Total cards in text:   {total}")
    lines.append(f"Updated (existing):    {len(updated)}")
    lines.append(f"Added (new):           {len(added)}")
    lines.append(f"Errors (not found):    {len(errors)}")
    lines.append(f"Skipped:               {skip_count}")
    lines.append(f"  • No content change: {len(no_change)}")
    lines.append(f"  • Missing fields:    {len(missing_field_nids)} note(s), {len(missing_fields)} field(s)")
    if resolution_errors:
        lines.append(f"  • Resolution errors: {len(resolution_errors)}")
    lines.append("")

    def _section(title, nids):
        if not nids:
            return
        lines.append(sep)
        lines.append(f"{title} ({len(nids)})")
        lines.append(sep)
        for n in nids:
            lines.append(f"  [[{n}]]")
        lines.append("")

    _section("UPDATED", updated)
    _section("ADDED (new note ids)", added)
    _section("ERROR — NOTE NOT FOUND", errors)
    _section("SKIPPED — NO CONTENT CHANGE", no_change)

    if missing_fields:
        lines.append(sep)
        lines.append(f"SKIPPED — MISSING FIELD ({len(missing_fields)} field(s))")
        lines.append(sep)
        for entry in missing_fields:
            lines.append(f"  {entry}")
        lines.append("")

    if resolution_errors:
        lines.append(sep)
        lines.append("RESOLUTION ERRORS")
        lines.append(sep)
        for entry in resolution_errors:
            lines.append(f"  {entry}")
        lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Import Dialog
# ---------------------------------------------------------------------------
class ImportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DocSync — Import")
        self.resize(800, 700)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Paste rich-text content"))

        self.doc_editor = DocumentEditor(self)
        layout.addWidget(self.doc_editor)

        btn_row = QHBoxLayout()
        self.import_btn = QPushButton("⬇️ Import")
        self.close_btn = QPushButton("Close")
        btn_row.addWidget(self.import_btn)
        btn_row.addWidget(self.close_btn)
        layout.addLayout(btn_row)

        qconnect(self.import_btn.clicked, self._import)
        qconnect(self.close_btn.clicked, self.close)

    def _import(self):
        # Lấy trực tiếp HTML thay vì plain text mangled bởi QTextEdit
        raw_html = self.doc_editor.edit.toHtml()
        
        if not raw_html.strip():
            tooltip("Nothing to import.")
            return

        cfg, cards = parse_pasted_html(raw_html)
        if not cards:
            tooltip("No valid card blocks found.")
            return

        ok = askUser(
            f"This action will affect {len(cards)} cards.\nContinue?",
            parent=self, defaultno=False,
        )
        if not ok:
            return

        result = do_import(cfg, cards)
        self.close()
        showText(_build_result_text(result), title="DocSync — Import Result",
                  minWidth=500, minHeight=400)


def import_notes_from_txt() -> None:
    dlg = ImportDialog(mw)
    dlg.exec()