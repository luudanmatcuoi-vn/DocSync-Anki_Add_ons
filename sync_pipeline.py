from __future__ import annotations

import html as html_lib
import re
import json
import os

from . import media

_RE_MARKER_LINE = re.compile(
    r'^[ \t]*(?:<[^>\n]+>[ \t]*)*(===(?:\[\d+\])?|>>>)[ \t]*(?:<[^>\n]+>[ \t]*)*[ \t]*$',
    re.MULTILINE,
)

def html_handle_function(body_html: str):
    from .richtext import normalize_html
    text = normalize_html(body_html)
    text = re.sub(r"(?m)^([^\n]*?)&gt;&gt;&gt;([^\n]*)$", lambda m: m.group(0).replace("&gt;&gt;&gt;", ">>>") if not re.sub(r"<[^>]+>", "", m.group(1) + m.group(2)).strip() else m.group(0), text)
    text = _RE_MARKER_LINE.sub(lambda m: m.group(1), text)
    return text

_RE_CONFIG = re.compile(
    r'^[^\n]*#{1,}\s*START_CONFIG.*?#{1,}\s*END_CONFIG[^\n]*',
    re.DOTALL | re.MULTILINE,
)

def decode_config(blob: str) -> dict:
    blob = blob.strip()
    if not blob:
        return {}
    try:
        return json.loads(blob)
    except:
        return {}

def config_extract_handle(raw_text:str):
    from bs4 import BeautifulSoup
    text = html_handle_function(raw_text)
    cfg_text = BeautifulSoup(text, 'html.parser').get_text()
    m = _RE_CONFIG.search(cfg_text)
    if not m:
        return {}
    cfg_text = re.sub(r"#{1,}\s*(?:START_CONFIG|END_CONFIG)", "", m.group(0))
    cfg = decode_config(cfg_text)
    return cfg

def extract_body(text: str):
    m = _RE_CONFIG.search(text)
    if not m:
        return text
    remaining = text[: m.start()] + text[m.end():]
    return remaining.strip("\n")
    
def parse_pasted_html(raw_html: str, resolve_media: bool = True) -> tuple[dict, list[dict]]:
    """Pipeline gốc: Đi qua từng bước chuẩn Workflow trực tiếp trên HTML rác."""

    # Bước 1: Tách JSON Config
    normalized = html_handle_function(raw_html)
    cfg = config_extract_handle(raw_html)
    body_html = extract_body(normalized)
    
    # Bước 2->4: html_handle_function
    text = body_html
    
    # if True:
        # raise ValueError(str(raw_html)+"\n----------\n"+str(cfg)+"\n----------\n"+str(body_html) +"\n----------\n"+str(text)   )

    # Bước 5 & 6: Tách block thông qua Regex '===[nid]' và '>>>'
    _RE_CARD_HEADER = re.compile(r'^===(?:\[(\d+)\])?[ \t]*$', re.MULTILINE)
    _RE_FIELD_SEP = re.compile(r'^[ \t]*>>>[ \t]*$', re.MULTILINE)

    cards = []
    parts = _RE_CARD_HEADER.split(text)

    i = 1
    while i < len(parts) - 1:
        nid_str = parts[i]
        card_body = parts[i + 1]
        i += 2

        nid = int(nid_str) if nid_str else None
        
        # Tách fields
        raw_fields = _RE_FIELD_SEP.split(card_body)
        fields = [resolve_field_images(f.strip("\n")) if resolve_media else f.strip("\n") for f in raw_fields]
        
        # Bỏ đi thẻ trống do Regex thừa
        if len(fields) == 1 and fields[0] == "":
            fields = []

        cards.append({"nid": nid, "fields": fields})

    return cfg, cards

def resolve_field_images(field: str) -> str:
    """Filename hints are authoritative, including when the picture was removed."""
    import base64
    from pathlib import Path
    from urllib.parse import urlparse, unquote
    from urllib.request import url2pathname
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(field, 'html.parser')
    # Work on lines, so ordinary parenthesized prose cannot claim an image.
    lines = str(soup).split('\n')
    name_re = re.compile(r'^\(([^()\r\n]+\.(?:png|jpe?g|gif|webp|bmp|svg|avif))\)$', re.I)
    for i, line in enumerate(lines):
        hint = name_re.fullmatch(BeautifulSoup(line, 'html.parser').get_text().strip())
        if not hint:
            continue
        name = hint.group(1)
        if name != os.path.basename(name) or '/' in name or '\\' in name:
            raise ValueError('Invalid image filename: ' + name)
        previous = i - 1
        while previous >= 0 and not lines[previous].strip(): previous -= 1
        image = None
        image_soup = None
        if previous >= 0:
            image_soup = BeautifulSoup(lines[previous], 'html.parser')
            # Associate an image at the end of the preceding line, within this field.
            if len(image_soup.find_all('img')) == 1 and not ''.join(image_soup.img.find_all_next(string=True)).strip():
                image = image_soup.img
        if media.file_exists(name):
            replacement = f'<img data-docsync-keep="1" src="{html_lib.escape(name, quote=True)}">'
        elif image:
            replacement = save_image(str(image['src']), name).replace("<img ", '<img data-docsync-keep="1" ', 1)
        else:
            # Preserve the reference even when the original media file is absent.
            replacement = f'<img data-docsync-keep="1" src="{html_lib.escape(name, quote=True)}">'
        if image:
            image.replace_with(BeautifulSoup(replacement, 'html.parser'))
            lines[previous] = str(image_soup)
            lines[i] = ''
        else:
            lines[i] = replacement
    soup = BeautifulSoup('\n'.join(lines), 'html.parser')
    for image in soup.find_all('img'):
        src = image.get('src', '')
        if image.has_attr('data-docsync-keep'):
            del image['data-docsync-keep']
            continue
        if media.file_exists(src):
            image['src'] = BeautifulSoup(save_image(os.path.join(media.media_dir(), src), None), 'html.parser').img['src']
            continue
        if not re.match(r'^(?:data:|file:|https?:|/|[A-Za-z]:)', src):
            continue  # missing existing media reference
        image['src'] = BeautifulSoup(save_image(src, None), 'html.parser').img['src']
    return str(soup)


def save_image(src: str, name: str | None) -> str:
    import base64
    from pathlib import Path
    from urllib.parse import urlparse, unquote
    from urllib.request import url2pathname, urlopen
    if src.startswith('data:'):
        header, encoded = src.split(',', 1)
        if ';base64' not in header: raise ValueError('Unsupported image data URI')
        data = base64.b64decode(encoded, validate=True)
        ext = '.' + header.split('/')[1].split(';')[0]
    elif src.startswith('https://'):
        with urlopen(src, timeout=20) as response:
            if not response.headers.get('Content-Type', '').startswith('image/'):
                raise ValueError('Image URL did not return an image')
            data = response.read(32 * 1024 * 1024 + 1)
            ext = '.' + response.headers.get_content_subtype()
        if len(data) > 32 * 1024 * 1024: raise ValueError('Image exceeds 32 MiB')
    elif src.startswith('file:') or os.path.isabs(src):
        path = url2pathname(unquote(urlparse(src).path)) if src.startswith('file:') else src
        data = Path(path).read_bytes()
        ext = Path(path).suffix or '.png'
    else:
        raise ValueError('Cannot read image: ' + src[:160])
    filename = media.store_media(data, name, ext)
    return f'<img src="{html_lib.escape(filename, quote=True)}">'
