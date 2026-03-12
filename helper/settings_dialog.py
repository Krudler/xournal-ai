#!/usr/bin/env python3
"""
XournalAI Settings Dialog — GTK UI for configuring the plugin.
Run with system python3 + PYTHONPATH=/usr/lib/python3/dist-packages.
"""
import sys
import json
import os

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

HISTORY_FILE = "/tmp/xai_history.json"


def load_settings(config_path):
    try:
        with open(config_path) as f:
            return json.load(f)
    except Exception:
        return {}


def save_settings(config_path, settings):
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w") as f:
        json.dump(settings, f, indent=2)


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(
        "~/.config/xournalpp-ai/settings.json")

    settings = load_settings(config_path)

    dialog = Gtk.Dialog(title="XournalAI Settings")
    dialog.add_buttons("Save", Gtk.ResponseType.OK, "Cancel", Gtk.ResponseType.CANCEL)
    dialog.set_default_size(480, -1)

    box = dialog.get_content_area()
    box.set_spacing(6)
    box.set_margin_start(16)
    box.set_margin_end(16)
    box.set_margin_top(12)
    box.set_margin_bottom(12)

    # API Key
    box.add(Gtk.Label(label="Claude API Key:", xalign=0))
    api_entry = Gtk.Entry(visibility=False, text=settings.get("api_key", ""),
                          placeholder_text="sk-ant-...")
    box.add(api_entry)

    # Python interpreter
    box.add(Gtk.Label(label="Python interpreter:", xalign=0))
    python_entry = Gtk.Entry(text=settings.get("python_path", "python3"),
                             placeholder_text="python3 or /path/to/venv/bin/python3")
    box.add(python_entry)

    # Default prompt
    box.add(Gtk.Label(label="Default prompt:", xalign=0))
    prompt_entry = Gtk.Entry(text=settings.get("default_prompt", "What is shown here?"))
    box.add(prompt_entry)

    # Auto send
    auto_check = Gtk.CheckButton(
        label="Auto send — invoke Ask AI without a confirmation dialog")
    auto_check.set_active(settings.get("auto_send", False))
    box.add(auto_check)

    # Image background
    box.add(Gtk.Label(label="Captured image background:", xalign=0))
    bg_box = Gtk.Box(spacing=12)
    bg_white = Gtk.RadioButton.new_with_label(None, "White")
    bg_black = Gtk.RadioButton.new_with_label_from_widget(bg_white, "Black")
    if settings.get("image_background", "white") == "black":
        bg_black.set_active(True)
    else:
        bg_white.set_active(True)
    bg_box.pack_start(bg_white, False, False, 0)
    bg_box.pack_start(bg_black, False, False, 0)
    box.add(bg_box)

    # Separator + Clear history button
    box.add(Gtk.Separator())
    clear_btn = Gtk.Button(label="Clear conversation history")
    clear_btn.set_halign(Gtk.Align.START)

    def on_clear(_btn):
        try:
            os.remove(HISTORY_FILE)
        except FileNotFoundError:
            pass
        info = Gtk.MessageDialog(
            transient_for=dialog,
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="Conversation history cleared.",
        )
        info.run()
        info.destroy()

    clear_btn.connect("clicked", on_clear)
    box.add(clear_btn)

    dialog.show_all()

    if dialog.run() == Gtk.ResponseType.OK:
        settings["api_key"]        = api_entry.get_text().strip()
        settings["python_path"]    = python_entry.get_text().strip() or "python3"
        settings["default_prompt"] = prompt_entry.get_text().strip() or "What is shown here?"
        settings["auto_send"]         = auto_check.get_active()
        settings["image_background"]  = "black" if bg_black.get_active() else "white"
        save_settings(config_path, settings)

    dialog.destroy()


if __name__ == "__main__":
    main()
