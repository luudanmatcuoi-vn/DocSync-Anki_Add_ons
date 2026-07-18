# DocSync (Notes Import/Export)

## Description

**DocSync (Notes Import/Export)** is an Anki add-on designed to import/export notes to rich text. You can edit those notes using any document editor of your choice (recommend gg docs) and seamlessly import the changes back into Anki, updating existing fields based on their unique note ID (position).

This is especially helpful for bulk editing content, reviewing your cards externally, or leveraging other text-processing tools while preserving the integrity of Anki fields, media elements (only support image), and HTML formatting.

## Installation

You can easily install this add-on directly from AnkiWeb using the shared add-on ID.

1. Open Anki and go to `Tools` -> `Add-ons`.
2. Click **Get Add-ons...**
3. Enter the code `1353411495` and click **OK**.
4. Restart Anki to allow the add-on to load.

More info on the [AnkiWeb Shared Add-on Page](https://ankiweb.net/shared/info/1353411495).

## Usage


### Exporting Notes
1. Open the **Anki Browser** (`Browse` from the main window).
2. Select one or more notes you want to export.
3. Right-click the selected notes.
4. Click on **📄 DocSync: Export Notes to Docs**.

The exported text file will have the following structure:
```text
### START_CONFIG
{"notetype": "", "deck": "", "fields": [""]}
### END_CONFIG
===[anki-id]
(content)
>>>
(content)
===
(content2)
>>>
(content2)
```

### Importing Notes

1. On the main Anki window, click the **Tools** menu.
2. Click on **📄 DocSync: Import Notes from Docs**.
4. Pasted rich-text and press import.

The add-on will intelligently parse the Note IDs and Field Names, only updating the note content where differences are detected. Media tags and HTML structures are handled robustly to prevent breaking your rich formatting!
