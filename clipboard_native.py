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
