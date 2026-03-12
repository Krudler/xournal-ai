# xournal-ai

A [Xournal++](https://xournalpp.github.io/) plugin that sends your handwritten notes to Claude AI and displays the response in a conversation window, with LaTeX equations rendered inline.

## Features

- Capture a selection or full page from Xournal++ and ask Claude about it
- Persistent multi-turn conversation history per session
- LaTeX expressions in responses are rendered as inline images
- Configurable: API key, default prompt, auto-send mode, image background colour

## Requirements

### System

- Linux (X11 — clipboard access via `xclip`)
- [Xournal++](https://xournalpp.github.io/) with Lua plugin support
- Python 3.8+
- `xclip`
- `zenity`
- PyGObject (`python3-gi`, `gir1.2-gtk-3.0`) installed **system-wide**

```sh
sudo apt install xclip zenity python3-gi gir1.2-gtk-3.0
```

### Python (pip)

Install into a virtual environment or system-wide:

```sh
pip install anthropic matplotlib
```

**Optional dependencies** (extend functionality but not required):

| Package | Purpose |
|---------|---------|
| `cairosvg` | Convert SVG clipboard data to PNG (faster than Inkscape) |
| `inkscape` (system) | Fallback SVG→PNG conversion if cairosvg is unavailable |
| `Pillow` | Composite a solid white or black background onto transparent captures |

If neither `cairosvg` nor `inkscape` is available, selections exported as SVG (e.g. from some Xournal++ builds) will be silently skipped and the query sent without an image.

## Installation

1. Locate your Xournal++ plugins directory. Typical paths:
   - `~/.config/xournalpp/plugins/`
   - `/usr/share/xournalpp/plugins/`

2. Copy or symlink this repository into that directory:

   ```sh
   ln -s /path/to/xournal-ai ~/.config/xournalpp/plugins/xournal-ai
   ```

3. Restart Xournal++. The plugin appears under **Plugin → Ask AI** and **Plugin → AI Settings**.

## Configuration

Open **Plugin → AI Settings** and fill in:

| Field | Description |
|-------|-------------|
| Claude API Key | Your `sk-ant-…` key from [console.anthropic.com](https://console.anthropic.com) |
| Python interpreter | Path to the Python 3 binary that has `anthropic` and `matplotlib` installed (e.g. `/home/user/.venv/bin/python3`) |
| Default prompt | Pre-filled question shown in the query dialog |
| Auto send | Skip the question dialog and use the default prompt immediately |
| Image background | White or black — applied to transparent captures before sending |

Settings are stored at `~/.config/xournalpp-ai/settings.json`.

## Usage

1. Select a region in Xournal++ (or leave nothing selected to capture the whole page).
2. Press **Ctrl+Alt+A** or go to **Plugin → Ask AI**.
3. Type your question in the dialog that appears, then press Enter.
4. A conversation window opens with Claude's response. LaTeX is rendered inline.
5. Ask follow-up questions by triggering **Ask AI** again — the full history is sent each time.
6. Click **Clear History** (in the conversation window or settings dialog) to start fresh.

## Caveats and Gotchas

### GTK bindings must be system-wide

`show_response.py` and `settings_dialog.py` use PyGObject (`gi`), which is typically only available in the system Python installation. The plugin hardcodes `/usr/bin/python3` for the response window for this reason. If your system Python differs (e.g. on Arch Linux it may be `/usr/bin/python`), you may need to adjust line 305 in `helper/capture_and_ask.py`.

The **Python interpreter** setting only affects which Python runs `claude_api.py` (the API call and LaTeX rendering); GTK windows always use the system Python.

### Virtual environment for API dependencies

If you install `anthropic` and `matplotlib` into a virtualenv, set the **Python interpreter** in AI Settings to the venv's Python path. The GTK windows will still use the system Python regardless.

### Clipboard timing

The plugin copies the current selection to clipboard and then immediately spawns a background process to read it. There is a 0.4 s sleep to let the clipboard settle. On very slow machines this may need to be increased (`time.sleep(0.4)` in `helper/capture_and_ask.py`).

### Temporary files are not cleaned up automatically

The plugin writes to `/tmp` and does not clean up on exit:

| Path | Contents |
|------|----------|
| `/tmp/xai_captures/` | Captured PNG images (one per query) |
| `/tmp/xai_latex_*.png` | Rendered LaTeX equation images |
| `/tmp/xai_history.json` | Conversation history (cleared by "Clear History") |
| `/tmp/xai_debug.log` | Debug log (appended continuously) |
| `/tmp/xai_error.log` | stderr from the last `claude_api.py` run |

These are wiped on reboot. Clear them manually if disk space matters.

### History is lost on reboot

`/tmp/xai_history.json` lives in `/tmp`, so it does not survive a reboot. If you want to keep conversations, copy it elsewhere before rebooting.

### Wayland is not supported

Clipboard access uses `xclip`, which requires X11. On Wayland sessions Xournal++ must be run under XWayland (`DISPLAY=:0 xournalpp`).
