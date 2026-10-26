import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch
import test_sync
from docsync_test.clipboard_native import plaintext_to_html, read_clipboard_html
from docsync_test.sync_pipeline import parse_pasted_html
from docsync_test.export_notes import select_card_fields, FieldSelectionDialog
from aqt.qt import QApplication, QDialogButtonBox

class FieldImportTests(unittest.TestCase):
    setUp = test_sync.SyncTests.setUp
    tearDown = test_sync.SyncTests.tearDown

    def test_plaintext_partial_update_preserves_other_field(self):
        from docsync_test import import_notes, note_resolver
        host = SimpleNamespace(col=self.col, checkpoint=lambda _: None, reset=lambda: None)
        import_notes.mw = note_resolver.mw = host
        note = self.col.new_note(self.col.models.by_name('Basic'))
        note['Front'], note['Back'] = 'Keep front', 'Old back'
        self.col.add_note(note, self.col.decks.id('Default'))
        self.col.media.write_data('old.png', b'old')
        text = ('### START_CONFIG\r\n{"fields":["Back"]}\r\n### END_CONFIG\r\n'
                f'===[{note.id}]\r\nLiteral <b>text</b> & more\r\n(old.png)')
        cfg, cards = parse_pasted_html(plaintext_to_html(text))
        result = import_notes.do_import(cfg, cards)
        updated = self.col.get_note(note.id)
        self.assertEqual(result['updated_nids'], [note.id])
        self.assertEqual(updated['Front'], 'Keep front')
        self.assertIn('&lt;b&gt;text&lt;/b&gt;', updated['Back'])
        self.assertIn('src="old.png"', updated['Back'])

    def test_export_reselects_from_original_and_cancel_keeps_selection(self):
        from docsync_test import export_notes
        app = QApplication.instance() or QApplication([])
        note = self.col.new_note(self.col.models.by_name('Basic'))
        note['Front'], note['Back'] = 'Front value', 'Back value'
        self.col.add_note(note, self.col.decks.id('Default'))
        export_notes.mw = SimpleNamespace(col=self.col)
        dialog = export_notes.ExportDialog([note.id])
        with patch.object(export_notes, 'FieldSelectionDialog') as picker:
            picker.return_value.exec.return_value = 1
            picker.return_value.selected_fields.return_value = ['Back']
            dialog._select_fields()
            self.assertEqual(dialog.cfg['fields'], ['Back'])
            self.assertEqual(dialog.cards[0]['fields'], ['Back value'])
            picker.return_value.exec.return_value = 0
            picker.return_value.selected_fields.return_value = ['Front']
            dialog._select_fields()
            self.assertEqual(dialog.cfg['fields'], ['Back'])
            picker.return_value.exec.return_value = 1
            dialog._select_fields()
            self.assertEqual(dialog.cards[0]['fields'], ['Front value'])
        dialog.close()

class SelectionTests(unittest.TestCase):
    def test_selection_values_match_header(self):
        original = [{'nid':1, 'fields':['A','B','C']}]
        selected = select_card_fields(original, ['Front','Back','Extra'], ['Back','Extra'])
        self.assertEqual(selected, [{'nid':1, 'fields':['B','C']}])
        self.assertEqual(original[0]['fields'], ['A','B','C'])
    def test_dialog_state_and_empty_selection(self):
        app = QApplication.instance() or QApplication([])
        dialog = FieldSelectionDialog(['Front','Back'], ['Back'])
        self.assertEqual(dialog.selected_fields(), ['Back'])
        dialog.checks[1].setChecked(False)
        self.assertFalse(dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled())
        dialog.checks[0].setChecked(True)
        self.assertTrue(dialog.buttons.button(QDialogButtonBox.StandardButton.Ok).isEnabled())
        dialog.reject()
        self.assertEqual(dialog.result(), 0)
    def test_native_plaintext_fallback(self):
        clipboard = Mock()
        clipboard.RegisterClipboardFormat.return_value = 123
        clipboard.IsClipboardFormatAvailable.side_effect = lambda fmt: fmt == 13
        clipboard.GetClipboardData.return_value = '===[123]\r\nText'
        with patch('docsync_test.clipboard_native.sys.platform','win32'), patch.dict(sys.modules, {'win32clipboard':clipboard}):
            html = read_clipboard_html()
        self.assertEqual(parse_pasted_html(html)[1], [{'nid':123, 'fields':['Text']}])
        clipboard.CloseClipboard.assert_called_once()
    def test_reject_invalid_plaintext_configuration(self):
        with self.assertRaises(ValueError):
            plaintext_to_html('### START_CONFIG\n{broken}\n### END_CONFIG\n===[123]\nText')

    def test_reject_unstructured_plaintext(self):
        with self.assertRaises(ValueError):
            plaintext_to_html('Ordinary clipboard text without DocSync markers')
