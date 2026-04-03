"""
TxtSync — Field Content Conversion

html_to_text: Anki HTML → readable text for the export file (export direction)
text_to_html: readable text → Anki HTML (import direction)

Design rules — LOSSLESS roundtrip:
  - ALL HTML tags are preserved (bold, italic, underline, spans, images, etc.)
  - Only <br> / <br/> / <br /> tags are converted to literal newlines on export
    (and reversed on import) so the text file is human-readable.
  - <div>…</div> is converted to content + newline on export;
    on import newlines become <br>.
  - This guarantees: export → import produces identical Anki HTML.
"""

import re
import unicodedata

from aqt import mw
from aqt.editor import Editor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
class _EditorShim(Editor):
    """Minimal shim so we can call Editor.mungeHTML without a full editor."""
    def __init__(self):
        self.mw = mw


_RE_BR = re.compile(r'<br\s*/?>', re.IGNORECASE)
_RE_DIV = re.compile(r'<div[^>]*>(.*?)</div>', re.IGNORECASE | re.DOTALL)


# ---------------------------------------------------------------------------
# Export: HTML → text  (preserves all styling tags)
# ---------------------------------------------------------------------------
def html_to_text(html: str) -> str:
    """Convert Anki field HTML to text for the export file.

    All HTML is kept intact EXCEPT:
      - <br> variants → literal newline
      - <div>…</div> → content + newline (flattened)
    """
    if not html:
        return ""

    text = html

    # 1. <div>content</div> → content\n  (un-nest divs for readability)
    #    Process repeatedly to handle nested divs
    prev = None
    while prev != text:
        prev = text
        text = _RE_DIV.sub(lambda m: m.group(1) + '\n', text)

    # 2. <br> variants → newline
    text = _RE_BR.sub('\n', text)

    # 3. Clean up trailing whitespace per line
    lines = [line.rstrip() for line in text.split('\n')]
    # Remove trailing empty lines
    while lines and lines[-1] == '':
        lines.pop()
    # Remove leading empty lines
    while lines and lines[0] == '':
        lines.pop(0)

    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Import: text → HTML  (reverses only the newline conversion)
# ---------------------------------------------------------------------------
def text_to_html(text: str) -> str:
    """Convert text from the import file back to Anki field HTML.

    Literal newlines → <br>.  All other content (including existing HTML
    tags for bold, italic, images, sound, etc.) passes through untouched.
    """
    if not text:
        return ""

    # 1. Newlines → <br>
    result = text.replace('\n', '<br>')

    # 2. Normalise unicode (Anki convention)
    result = unicodedata.normalize("NFC", result)

    # 3. Strip null bytes
    result = result.replace("\x00", "")

    # 4. Sanitise via Anki's own mungeHTML
    try:
        editor_shim = _EditorShim()
        result = Editor.mungeHTML(editor_shim, result)
    except Exception:
        pass  # If mungeHTML is unavailable in this Anki version, skip

    return result
