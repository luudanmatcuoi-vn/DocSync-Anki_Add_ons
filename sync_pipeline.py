from __future__ import annotations

import html as html_lib
import re
import json

from . import media

# ---------------------------------------------------------------------------
# Cấu hình danh sách Regex tự do xử lý lỗi HTML vặt
# ---------------------------------------------------------------------------
RAW_HTML_REPLACEMENTS: list[tuple[str, str]] = [
    (r'<meta[^>]*>', ''),
    (r'<!--.*?-->', ''),
    (r'<head\b.*?</head>', ''),
    (r'</?html[^>]*>', ''),
    (r'</?body[^>]*>', ''),
]

_RE_GUID_WRAPPER_OPEN = re.compile(
    r'<b\s+style="font-weight:\s*normal;?"[^>]*>', re.IGNORECASE
)

def _strip_guid_wrapper(html_in: str) -> str:
    if not _RE_GUID_WRAPPER_OPEN.search(html_in):
        return html_in
    html_in = _RE_GUID_WRAPPER_OPEN.sub('', html_in, count=1)
    idx = html_in.rfind('</b>')
    if idx != -1:
        html_in = html_in[:idx] + html_in[idx + len('</b>'):]
    return html_in

TEXT_REPLACEMENTS: list[tuple[str, str]] = [
    (r'\u00a0', ' '),
    (r'[\u200b\u200c\u200d]', ''),
    (r'[ \t]+\n', '\n'),
    (r'\n{3,}', '\n\n'),
]

def _apply(text: str, replacements: list[tuple[str, str]]) -> str:
    for pat, repl in replacements:
        text = re.sub(pat, repl, text, flags=re.IGNORECASE | re.DOTALL)
    return text

# ---------------------------------------------------------------------------
# Xử lý ẢNH BASE64 (Dùng Regex bóc tách & check trùng trong Collection)
# ---------------------------------------------------------------------------
_RE_IMG_WITH_HINT = re.compile(
    r'<img\b[^>]*\bsrc="data:(?P<mime>[^;"]+);base64,(?P<data>[^"]+)"[^>]*>'
    r'(?:\s|<br\s*/?>|</?(?:div|p|span)[^>]*>)*'
    r'(?:\(([^()\n]{1,120})\))?',
    re.IGNORECASE | re.DOTALL,
)

def resolve_base64_images(html_in: str) -> str:
    import base64

    def repl(m: re.Match) -> str:
        mime = m.group("mime")
        b64data = m.group("data")
        hint = m.group(3)
        suggested_name = hint.strip() if hint else None
        ext = "." + mime.split("/")[-1] if "/" in mime else ".png"

        # Nếu ảnh (có tên hint) đã tồn tại trong media Anki => lấy luôn ảnh gốc, bỏ qua base64
        if suggested_name and media.file_exists(suggested_name):
            return f'<img src="{suggested_name}">'

        # Nếu chưa có, giải mã base64 và lưu thẳng vào Collection Anki
        data = base64.b64decode(b64data)
        filename = media.store_media(data, suggested_name=suggested_name, ext_hint=ext)
        return f'<img src="{filename}">'

    return _RE_IMG_WITH_HINT.sub(repl, html_in)

# ---------------------------------------------------------------------------
# Xử lý các thẻ RICHTEXT (span style sang html)
# ---------------------------------------------------------------------------
_RE_SPAN_TAG = re.compile(r'<span\b([^>]*)>|</span>', re.IGNORECASE)
_RE_STYLE_ATTR = re.compile(r'style\s*=\s*"([^"]*)"', re.IGNORECASE)

def _style_dict(style_attr: str) -> dict:
    out = {}
    for chunk in style_attr.split(";"):
        if ":" not in chunk:
            continue
        k, v = chunk.split(":", 1)
        out[k.strip().lower()] = v.strip()
    return out

def _tags_for_style(style: dict) -> tuple[list[str], list[str]]:
    open_tags, close_tags = [], []
    weight = style.get("font-weight", "400")
    try:
        is_bold = int(weight) >= 700
    except ValueError:
        is_bold = weight.lower() in ("bold", "bolder")
    if is_bold:
        open_tags.append("<b>")
        close_tags.insert(0, "</b>")

    if style.get("font-style", "").lower() == "italic":
        open_tags.append("<i>")
        close_tags.insert(0, "</i>")

    if "underline" in style.get("text-decoration", "").lower():
        open_tags.append("<u>")
        close_tags.insert(0, "</u>")

    color = style.get("color", "")
    if color and color.lower() not in ("#000000", "black", "inherit"):
        open_tags.append(f'<span style="color:{color}">')
        close_tags.insert(0, "</span>")

    bgcolor = style.get("background-color", "")
    if bgcolor and bgcolor.lower() not in ("transparent", "inherit"):
        open_tags.append(f'<span style="background-color:{bgcolor}">')
        close_tags.insert(0, "</span>")

    return open_tags, close_tags

def clean_richtext_html(html_in: str) -> str:
    stack, out, pos = [], [], 0
    for m in _RE_SPAN_TAG.finditer(html_in):
        out.append(html_in[pos:m.start()])
        pos = m.end()
        if m.group(0).lower() == "</span>":
            close_tags = stack.pop() if stack else []
            out.append("".join(close_tags))
        else:
            attrs = m.group(1) or ""
            style_m = _RE_STYLE_ATTR.search(attrs)
            style = _style_dict(style_m.group(1)) if style_m else {}
            open_tags, close_tags = _tags_for_style(style)
            stack.append(close_tags)
            out.append("".join(open_tags))
    out.append(html_in[pos:])
    return "".join(out)

# ---------------------------------------------------------------------------
# Lột bỏ sạch sẽ các tag (như bọc <div> hoặc <p>) lỡ dính vào mốc === hoặc >>>
# ---------------------------------------------------------------------------
_RE_MARKER_LINE = re.compile(
    r'^[ \t]*(?:<[^>\n]+>[ \t]*)*(===(?:\[\d+\])?|>>>)[ \t]*(?:<[^>\n]+>[ \t]*)*[ \t]*$',
    re.MULTILINE,
)

def html_handle_function(body_html:str):
    # Bước 2: Regex tách và lưu base64, so sánh tên ảnh (không lưu thừa)
    text = resolve_base64_images(body_html)

    # Bước 3: Replace custom regex list 
    text = _apply(text, RAW_HTML_REPLACEMENTS)
    text = _strip_guid_wrapper(text)

    # Bước 4: Xử lý thẻ richtext sang thẻ html thuần
    text = clean_richtext_html(text)

    # Flatten block-level structure về newlines thật
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</(p|div)\s*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<(p|div)\b[^>]*>', '', text, flags=re.IGNORECASE)
    text = text.strip()

    text = html_lib.unescape(text)
    text = _apply(text, TEXT_REPLACEMENTS)

    # Tiêu diệt các tag html lỡ bọc lấy dấu tách blocks
    text = _RE_MARKER_LINE.sub(lambda m: m.group(1), text)
    return text
 
_RE_CONFIG = re.compile(
    r'#{1,}\s*START_CONFIG.*#{1,}\s*END_CONFIG',
    re.DOTALL,
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
    cfg_text = html_handle_function(raw_text)
    m = _RE_CONFIG.search(cfg_text)
    if not m:
        cfg_text = ""
    else:
        cfg_text = m.group(0)
    cfg_text = re.sub(r"<[^>]+>","",cfg_text)
    cfg_text = re.sub(r"#{1,}\s*START_CONFIG","",cfg_text)
    cfg_text = re.sub(r"#{1,}\s*END_CONFIG","",cfg_text)
    cfg = decode_config(cfg_text)
    return cfg

def extract_body(text: str):
    m = _RE_CONFIG.search(text)
    if not m:
        return text
    remaining = text[: m.start()] + text[m.end():]
    return remaining.strip("\n")
    
def parse_pasted_html(raw_html: str) -> tuple[dict, list[dict]]:
    """Pipeline gốc: Đi qua từng bước chuẩn Workflow trực tiếp trên HTML rác."""

    # Bước 1: Tách JSON Config
    cfg = config_extract_handle(raw_html)
    body_html = extract_body(raw_html)
    
    # Bước 2->4: html_handle_function
    text = html_handle_function(body_html)
    
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
        fields = [f.strip("\n") for f in raw_fields]
        
        # Bỏ đi thẻ trống do Regex thừa
        if len(fields) == 1 and fields[0] == "":
            fields = []

        cards.append({"nid": nid, "fields": fields})

    return cfg, cards