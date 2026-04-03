"""
TxtSync — Anki Add-on

Export selected notes to a human-readable text format from the browser,
and import text back into notes from the Tools menu.
"""

from aqt import mw, gui_hooks
from aqt.qt import *
from aqt.browser import Browser
from aqt.utils import qconnect

from .export_notes import export_selected_notes
from .import_notes import import_notes_from_txt


# ---------------------------------------------------------------------------
# Browser menu hook (right-click / menu bar)
# ---------------------------------------------------------------------------
def setup_browser_menu(browser: Browser) -> None:
    """Add 'Export Notes to Txt' to Notes, Cards, and Edit menus."""
    menus = [
        browser.form.menu_Notes,
        browser.form.menu_Cards,
    ]
    for menu in menus:
        menu.addSeparator()
        action = menu.addAction("📄 Export Notes to Txt")
        qconnect(action.triggered, lambda _, b=browser: export_selected_notes(b))


# ---------------------------------------------------------------------------
# Main window Tools menu
# ---------------------------------------------------------------------------
def setup_tools_menu() -> None:
    """Add 'Import Notes from Txt' to the main window Tools menu."""
    action = QAction("📄 Import Notes from Txt", mw)
    action.triggered.connect(lambda: import_notes_from_txt())
    mw.form.menuTools.addAction(action)


# ---------------------------------------------------------------------------
# Register hooks
# ---------------------------------------------------------------------------
gui_hooks.browser_menus_did_init.append(setup_browser_menu)
setup_tools_menu()
