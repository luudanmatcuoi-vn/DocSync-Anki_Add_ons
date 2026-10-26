import re
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

# Reuse the test package setup without loading the add-on's menu entry point.
import test_sync
from docsync_test.clipboard_native import encode_cf_html, write_clipboard_html
from docsync_test.export_notes import preview_cards, RenderWorker


class ExportTests(unittest.TestCase):
    def test_preview_threshold(self):
        for count, expected in ((20, 20), (100, 100), (101, 20), (1700, 20)):
            cards = [{'nid': i, 'fields': ['Text']} for i in range(count)]
            self.assertEqual(preview_cards(cards), cards[:expected])
            self.assertEqual(len(cards), count)

    def test_cf_html_unicode_offsets(self):
        fragment = '<b>Tiếng Việt</b><img src="file:///C:/ảnh.png">'
        data = encode_cf_html(fragment)
        offsets = {key: int(re.search(key.encode() + rb':(\d+)', data).group(1))
                   for key in ('StartHTML', 'EndHTML', 'StartFragment', 'EndFragment')}
        self.assertEqual(data[offsets['StartFragment']:offsets['EndFragment']].decode(), fragment)
        self.assertTrue(data[offsets['StartHTML']:offsets['EndHTML']].endswith(b'</html>'))

    def test_native_writer(self):
        clipboard = Mock()
        clipboard.RegisterClipboardFormat.return_value = 123
        with patch('docsync_test.clipboard_native.sys.platform', 'win32'), patch.dict(sys.modules, {'win32clipboard': clipboard}):
            write_clipboard_html('<b>Tiếng Việt</b>', 42)
        clipboard.OpenClipboard.assert_called_once_with(42)
        clipboard.EmptyClipboard.assert_called_once()
        self.assertEqual(clipboard.SetClipboardData.call_args_list[0].args[0], 123)
        self.assertEqual(clipboard.SetClipboardData.call_args_list[1].args, (13, 'Tiếng Việt'))
        clipboard.CloseClipboard.assert_called_once()

    def test_large_copy_uses_all_notes(self):
        cards = [{'nid': i + 1, 'fields': ['Text']} for i in range(1700)]
        errors = []
        worker = RenderWorker({}, cards, 'media', '/tmp', 42)
        worker.finished.connect(errors.append)
        with patch('docsync_test.export_notes.write_clipboard_html') as write:
            worker.run()
        self.assertEqual(errors, [''])
        html, owner = write.call_args.args
        self.assertEqual(html.count('===['), 1700)
        self.assertIn('===[1700]', html)
        self.assertEqual(owner, 42)

    def test_worker_reports_copy_error(self):
        worker = RenderWorker({}, [], 'media', '/tmp', 42)
        errors = []
        worker.finished.connect(errors.append)
        with patch('docsync_test.export_notes.write_clipboard_html', side_effect=RuntimeError('Clipboard busy')):
            worker.run()
        self.assertEqual(errors, ['Clipboard busy'])
