import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from types import ModuleType, SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
pkg = ModuleType('docsync_test')
pkg.__path__ = [str(ROOT)]
sys.modules[pkg.__name__] = pkg
import aqt
from anki.collection import Collection
from docsync_test import media
from docsync_test.sync_pipeline import parse_pasted_html, resolve_field_images
from docsync_test.richtext import normalize_html
from docsync_test.clipboard_native import decode_cf_html

class SyncTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.col = Collection(str(Path(self.tmp.name) / 'collection.anki2'))
        media.mw = SimpleNamespace(col=self.col)
    def tearDown(self):
        self.col.close()
        self.tmp.cleanup()
    def test_styles(self):
        docs = '<span style="font-weight:700;font-style:italic;text-decoration:underline;font-size:16pt;background-color:yellow;color:red">Text</span>'
        word = "<b><i><u><span style='font-size:16pt;background:yellow;color:red'>Text</span></u></i></b>"
        for source in (word, docs):
            result = normalize_html(source)
            for expected in ('font-size:16pt', 'background-color:yellow', 'color:red', 'font-style:italic', 'text-decoration:underline'):
                self.assertIn(expected, result)
    def test_existing_and_removed_image(self):
        self.col.media.write_data('old.png', b'old')
        for source in ('(old.png)', '<img src="data:image/png;base64,bmV3">\n(old.png)'):
            self.assertEqual(resolve_field_images(source).strip(), '<img src="old.png"/>')
        self.assertEqual(Path(self.col.media.dir(), 'old.png').read_bytes(), b'old')
        self.assertIn('missing.png', resolve_field_images('(missing.png)'))
    def test_new_images(self):
        result = resolve_field_images('<img src="data:image/png;base64,bmV3">\n(new.png)')
        self.assertIn('new.png', result)
        self.assertEqual(Path(self.col.media.dir(), 'new.png').read_bytes(), b'new')
        a = resolve_field_images('<img src="data:image/png;base64,bmV3">')
        b = resolve_field_images('<img src="data:image/png;base64,bmV3">')
        self.assertNotEqual(a, b)
    def test_parser(self):
        source = '### START_CONFIG<br>{"fields":["Front","Back"]}<br>### END_CONFIG<br>===[123]<br><b>A</b><br>&gt;&gt;&gt;<br>B'
        cfg, cards = parse_pasted_html(source)
        self.assertEqual(cfg, {'fields':['Front','Back']})
        self.assertEqual(len(cards[0]['fields']), 2)
        self.assertEqual(cards[0]['nid'], 123)
    def test_cf_html_byte_offsets(self):
        payload = '<html>Tiếng Việt</html>'.encode()
        header = b'StartHTML:0000000045\r\nEndHTML:0000000000\r\n'
        # Build header with actual byte offsets, not character offsets.
        header = f'StartHTML:{len(header):010d}\r\nEndHTML:{len(header)+len(payload):010d}\r\n'.encode()
        self.assertEqual(decode_cf_html(header + payload), payload.decode())


class CapturedFormattingTests(unittest.TestCase):
    def test_captured_docs_and_word(self):
        for name in ('docs', 'word'):
            result = normalize_html((ROOT / 'tests' / 'fixtures' / (name + '.html')).read_text())
            for expected in ('font-size:16', 'color:', 'background-color:', 'font-style:italic', 'text-decoration:underline', 'font-weight:'):
                self.assertIn(expected, result, name)

class AnkiIntegrationTests(unittest.TestCase):
    setUp = SyncTests.setUp
    tearDown = SyncTests.tearDown
    def test_update_create_and_parallel_export(self):
        from aqt.qt import QApplication
        app = QApplication.instance() or QApplication([])
        from docsync_test import import_notes, note_resolver
        host = SimpleNamespace(col=self.col, checkpoint=lambda _: None, reset=lambda: None)
        import_notes.mw = note_resolver.mw = host
        cfg = {'notetype':'Basic', 'deck':'Default', 'fields':['Front','Back']}
        result = import_notes.do_import(cfg, [{'nid':None, 'fields':['Question','Answer']}])
        nid = result['added_nids'][0]
        cfg2, cards = parse_pasted_html('### START_CONFIG<br>{"fields":["Front","Back"]}<br>### END_CONFIG<br>===[' + str(nid) + ']<br><b>Question</b><br>&gt;&gt;&gt;<br>Changed')
        result = import_notes.do_import(cfg2, cards)
        self.assertEqual(result['updated_nids'], [nid])
        self.assertEqual(self.col.get_note(nid)['Back'], 'Changed')
        from docsync_test.document_view import build_preview_html
        self.col.media.write_data('picture.png', b'picture')
        data = [{'nid':nid, 'fields':['<img src="picture.png">']}]
        linked = build_preview_html(cfg, data, 'media', self.col.media.dir())
        encoded = build_preview_html(cfg, data, 'base64', self.col.media.dir())
        self.assertIn('file:', linked)
        self.assertIn('data:image/png;base64,', encoded)
        self.assertIn('(picture.png)', encoded)

if __name__ == "__main__": unittest.main()
