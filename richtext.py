"""Normalize Office/Docs HTML into explicit, inherited Anki formatting."""
from __future__ import annotations
import html
import re
from bs4 import BeautifulSoup, Comment, NavigableString


def normalize_html(source: str) -> str:
    soup = BeautifulSoup(source, 'html.parser')
    for node in soup.find_all(['head', 'script', 'style', 'xml']):
        node.decompose()
    for node in soup.find_all(string=lambda s: isinstance(s, Comment)):
        node.extract()
    def render(node, inherited):
        if isinstance(node, NavigableString):
            # Office wraps source lines; only pre-wrap text retains actual newlines.
            text = str(node).replace('\r\n', '\n')
            if not inherited.get('_pre'):
                text = re.sub(r'\s+', ' ', text)
            return html.escape(text, quote=False)
        tag = node.name.lower()
        if tag == 'img':
            return '<img src="' + html.escape(node.get('src', ''), quote=True) + '">'
        if tag == 'br':
            return '\n'
        style = dict(inherited)
        if tag in ('b', 'strong'): style['font-weight'] = 'bold'
        if tag in ('i', 'em'): style['font-style'] = 'italic'
        if tag == 'u': style['text-decoration'] = 'underline'
        for item in node.get('style', '').split(';'):
            if ':' not in item: continue
            key, value = item.split(':', 1)
            key, value = key.strip().lower(), value.strip()
            if key == 'background': key = 'background-color'
            if key in ('font-weight', 'font-style', 'text-decoration', 'text-decoration-line', 'font-size', 'color', 'background-color'):
                style[key] = value
            if key == 'white-space': style['_pre'] = value.startswith('pre')
        if tag == 'font':
            if node.get('color'): style['color'] = node['color']
        pieces = []
        for child in node.children:
            if isinstance(child, NavigableString) and not isinstance(child, Comment):
                text = render(child, style)
                if not text.strip():
                    pieces.append(text)
                    continue
                css = []
                for key, value in style.items():
                    if key.startswith('_'): continue
                    if key == 'text-decoration-line': key = 'text-decoration'
                    # A small CSS allowlist excludes URLs and markup in values.
                    if re.fullmatch(r'[\w#().,% +\-]+', value):
                        css.append(f'{key}:{value}')
                pieces.append('\n'.join(f'<span style="{html.escape(";".join(css), quote=True)}">{line}</span>' if css and line else line for line in text.split('\n')))
            else:
                pieces.append(render(child, style))
        body = ''.join(pieces)
        return body + ('\n' if tag in ('p', 'div', 'li', 'tr') else '')
    return render(soup.body or soup, {}).strip()
