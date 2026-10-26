"""Read Windows CF_HTML bytes without a Qt conversion."""
from __future__ import annotations
import re
import sys


def decode_cf_html(data: bytes) -> str:
    offsets = {}
    for key in (b'StartHTML', b'EndHTML'):
        match = re.search(key + rb':\s*(\d+)', data[:4096])
        if match:
            offsets[key] = int(match.group(1))
    start, end = offsets.get(b'StartHTML', -1), offsets.get(b'EndHTML', -1)
    if 0 <= start < end <= len(data):
        data = data[start:end]
    return data.rstrip(b'\0').decode('utf-8-sig', errors='strict')


def read_clipboard_html() -> str:
    if sys.platform != 'win32':
        raise RuntimeError('Import from clipboard requires Windows and pywin32.')
    try:
        import win32clipboard
    except ImportError as exc:
        raise RuntimeError('Install pywin32 in the Python environment used by Anki, then restart Anki.') from exc
    fmt = win32clipboard.RegisterClipboardFormat('HTML Format')
    win32clipboard.OpenClipboard()
    try:
        if not win32clipboard.IsClipboardFormatAvailable(fmt):
            raise ValueError('Clipboard has no HTML Format. Copy the document content from Word or Google Docs.')
        data = win32clipboard.GetClipboardData(fmt)
    finally:
        win32clipboard.CloseClipboard()
    return decode_cf_html(data) if isinstance(data, bytes) else data


def encode_cf_html(fragment: str) -> bytes:
    """CF_HTML offsets count UTF-8 bytes, including the fixed-width header."""
    prefix = b'<html><body><!--StartFragment-->'
    suffix = b'<!--EndFragment--></body></html>'
    content = fragment.encode('utf-8')
    template = ('Version:1.0\r\nStartHTML:{:010d}\r\nEndHTML:{:010d}\r\n'
                'StartFragment:{:010d}\r\nEndFragment:{:010d}\r\n')
    start = len(template.format(0, 0, 0, 0).encode('ascii'))
    start_fragment = start + len(prefix)
    end_fragment = start_fragment + len(content)
    header = template.format(start, end_fragment + len(suffix), start_fragment, end_fragment).encode('ascii')
    return header + prefix + content + suffix + b'\0'


def write_clipboard_html(fragment: str, owner: int) -> None:
    """Publish generated HTML directly via Win32, never Qt's clipboard API."""
    if sys.platform != 'win32':
        raise RuntimeError('Copy to clipboard requires Windows and pywin32.')
    try:
        import win32clipboard
    except ImportError as exc:
        raise RuntimeError('Install pywin32 in the Python environment used by Anki, then restart Anki.') from exc
    from bs4 import BeautifulSoup
    import time
    payload = encode_cf_html(fragment)
    plain = BeautifulSoup(fragment, 'html.parser').get_text(separator='\n')
    fmt = win32clipboard.RegisterClipboardFormat('HTML Format')
    # Another application can briefly hold the clipboard lock.
    for attempt in range(5):
        try:
            win32clipboard.OpenClipboard(owner)
            break
        except Exception:
            if attempt == 4:
                raise
            time.sleep(0.05)
    try:
        win32clipboard.EmptyClipboard()
        win32clipboard.SetClipboardData(fmt, payload)
        win32clipboard.SetClipboardData(13, plain)  # CF_UNICODETEXT
    finally:
        win32clipboard.CloseClipboard()
