from __future__ import annotations
from aqt import mw
from aqt.qt import QComboBox, QDialog, QDialogButtonBox, QLabel, QVBoxLayout


class NoteTypeDeckPicker(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("DocSync — Select Note Type & Deck")
        layout = QVBoxLayout(self)

        layout.addWidget(QLabel("Note type:"))
        self.notetype_box = QComboBox()
        self.notetype_names = [nt.name for nt in mw.col.models.all_names_and_ids()]
        self.notetype_box.addItems(self.notetype_names)
        layout.addWidget(self.notetype_box)

        layout.addWidget(QLabel("Deck:"))
        self.deck_box = QComboBox()
        self.deck_names = [d.name for d in mw.col.decks.all_names_and_ids()]
        self.deck_box.addItems(self.deck_names)
        layout.addWidget(self.deck_box)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def result_values(self) -> tuple[str, str]:
        return self.notetype_box.currentText(), self.deck_box.currentText()


class ResolutionContext:
    def __init__(self, cfg: dict):
        self.cfg = cfg or {}
        self.last_notetype: str | None = self.cfg.get("notetype")
        self.last_deck: str | None = self.cfg.get("deck")

    def resolve_notetype_and_deck(self, parent=None) -> tuple[str, str] | None:
        notetype = self.cfg.get("notetype") or self.last_notetype
        deck = self.cfg.get("deck") or self.last_deck

        if notetype and deck:
            self.last_notetype, self.last_deck = notetype, deck
            return notetype, deck

        dlg = NoteTypeDeckPicker(parent)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return None
        notetype, deck = dlg.result_values()
        self.last_notetype, self.last_deck = notetype, deck
        return notetype, deck

    def resolve_field_names(self, notetype_name: str, field_count: int) -> list[str]:
        cfg_fields = self.cfg.get("fields")
        if cfg_fields:
            return list(cfg_fields)[:field_count] + [
                f"Field{i+1}" for i in range(len(cfg_fields), field_count)
            ]
        model = mw.col.models.by_name(notetype_name)
        if model:
            model_fields = [f["name"] for f in model["flds"]]
            if len(model_fields) >= field_count:
                return model_fields[:field_count]
        return [f"Field{i+1}" for i in range(field_count)]
