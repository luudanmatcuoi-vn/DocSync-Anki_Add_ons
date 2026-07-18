"""
DocSync — Anki Add-on
"""
from aqt import mw, gui_hooks
from aqt.qt import QAction
from aqt.browser import Browser
from aqt.utils import qconnect

from .export_notes import export_selected_notes
from .import_notes import import_notes_from_txt
# from .paste_card import new_card_from_clipboard


# ---------------------------------------------------------------------------
# Browser menu hook
# ---------------------------------------------------------------------------
def setup_browser_menu(browser: Browser) -> None:
    menus = [browser.form.menu_Notes, browser.form.menu_Cards]
    for menu in menus:
        menu.addSeparator()
        action = menu.addAction("📄 DocSync: Export Notes to Docs")
        qconnect(action.triggered, lambda _, b=browser: export_selected_notes(b))


# ---------------------------------------------------------------------------
# Main window Tools menu
# ---------------------------------------------------------------------------
def setup_tools_menu() -> None:
    import_action = QAction("📄 DocSync: Import Notes from Docs", mw)
    import_action.triggered.connect(lambda: import_notes_from_txt())
    mw.form.menuTools.addAction(import_action)

    # paste_action = QAction("🖼️ DocSync: New Card from Clipboard", mw)
    # paste_action.triggered.connect(lambda: new_card_from_clipboard())
    # mw.form.menuTools.addAction(paste_action)


gui_hooks.browser_menus_did_init.append(setup_browser_menu)
setup_tools_menu()
