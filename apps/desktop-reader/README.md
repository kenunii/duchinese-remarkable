# Chinese Book

Offline desktop reader for the prepared Chinese textbook. Scroll normally,
click words for translations, and pinch to zoom just the PDF.

Press **T**, then click the starting point for a textbox. Type with your normal
keyboard or Pinyin input method. Text saves automatically after a short pause;
click elsewhere, press Escape, or Ctrl+Enter to finish. Click existing text to
edit it. Unfocused textboxes are clickable only on their visible text; blank
space passes clicks through to the textbook. **Alt-click** a textbox to delete
it; **Ctrl-drag** to move it within the page. Both changes save automatically
to the PDF. Clearing the text also
removes it from the saved PDF. Empty or whitespace-only textboxes disappear
when they lose focus. No toolbar is added.

The original textbook is preserved. Text is saved as editable PDF FreeText
annotations in `~/Documents/Chinese Book.pdf`. Textbox state and recovery drafts
are also kept locally. The copy is created on the first nonempty textbox save.

```sh
python -m venv apps/desktop-reader/.venv
apps/desktop-reader/.venv/bin/pip install -r apps/desktop-reader/requirements.txt
python scripts/open-desktop-reader.py
```

Requires Chromium and Python with PyMuPDF and Pillow. `CHINESE_BOOK_PYTHON` can
select another interpreter; the laptop's existing PDF environment is also
reused when available. The default collection is
`build/new-textbook-complete-20261008`; its matching source is
`~/Downloads/新当代中文4-课本-compressed.pdf`. Pass a different prepared
collection and `--pdf /path/to/matching.pdf` together when needed.

A local server binds only to `127.0.0.1:8767` for writing PDF annotations. No OCR,
translation API or internet connection is used. Source PDFs are hash checked;
PDF and textbox writes use atomic replacement. Only nearby page rasters and
word overlays are loaded. Reading position and zoom persist per book in browser
storage and an atomic local `reading-position.json` file. Closing the window flushes the latest
position; reopening restores the exact page, offset and zoom. On this
Hyprland laptop, the launcher applies an app-only scroll factor of 0.35.
The installed shortcut is `~/.local/share/applications/chinese-book.desktop`.
