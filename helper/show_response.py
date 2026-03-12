#!/usr/bin/env python3
"""
Reads JSON from stdin:
  {"history": [{"role": "user"|"assistant", "text": "...",
                "image_path": "..." (user only, optional),
                "segments": [...] (assistant only)}]}
Opens a GTK window showing the full conversation.
"""
import sys
import json
import os
import signal

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib, Pango, Gdk, GdkPixbuf

PID_FILE = "/tmp/xai_response.pid"
HISTORY  = "/tmp/xai_history.json"

# Global CSS injected once — sets both color AND background-color so contrast
# is always correct regardless of the system GTK theme.
GLOBAL_CSS = b"""
.xai-user-bubble {
    background-color: #1565C0;
    color: #FFFFFF;
    padding: 8px 12px;
    border-radius: 6px;
}
.xai-user-bubble * {
    color: #FFFFFF;
}
.xai-asst-bubble {
    background-color: #EEEEEE;
    color: #1A1A1A;
    padding: 8px 12px;
    border-radius: 6px;
}
.xai-asst-bubble * {
    color: #1A1A1A;
}
.xai-user-header {
    color: #1565C0;
    font-weight: bold;
    font-size: 0.85em;
}
.xai-asst-header {
    color: #555555;
    font-weight: bold;
    font-size: 0.85em;
}
"""


def install_css():
    provider = Gtk.CssProvider()
    provider.load_from_data(GLOBAL_CSS)
    Gtk.StyleContext.add_provider_for_screen(
        Gdk.Screen.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )


def save_pid():
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))


def remove_pid():
    try:
        os.remove(PID_FILE)
    except FileNotFoundError:
        pass


def make_bubble(text, css_class):
    """Return an EventBox containing a wrapped, selectable label styled with css_class."""
    ev = Gtk.EventBox()
    ev.get_style_context().add_class(css_class)

    lbl = Gtk.Label(label=text)
    lbl.set_line_wrap(True)
    lbl.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
    lbl.set_xalign(0)
    lbl.set_selectable(True)
    lbl.set_margin_start(0)
    ev.add(lbl)
    return ev


def load_pixbuf_scaled(path, max_width=320):
    """Load a pixbuf scaled to max_width, preserving aspect ratio."""
    try:
        pb = GdkPixbuf.Pixbuf.new_from_file(path)
        if pb.get_width() > max_width:
            ratio = max_width / pb.get_width()
            pb = pb.scale_simple(max_width, int(pb.get_height() * ratio),
                                 GdkPixbuf.InterpType.BILINEAR)
        return pb
    except Exception:
        return None


def add_message(vbox, msg):
    role    = msg.get("role", "user")
    is_user = role == "user"
    name    = "You" if is_user else "Claude"
    bubble_cls  = "xai-user-bubble"  if is_user else "xai-asst-bubble"
    header_cls  = "xai-user-header"  if is_user else "xai-asst-header"

    # Header label ("You" / "Claude")
    header = Gtk.Label(label=name, xalign=0)
    header.get_style_context().add_class(header_cls)
    vbox.pack_start(header, False, False, 0)

    if is_user:
        # Optional image thumbnail
        img_path = msg.get("image_path", "")
        if img_path and os.path.exists(img_path):
            pb = load_pixbuf_scaled(img_path)
            if pb:
                img_widget = Gtk.Image.new_from_pixbuf(pb)
                ev = Gtk.EventBox()
                ev.get_style_context().add_class(bubble_cls)
                box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
                box.pack_start(img_widget, False, False, 0)
                text = msg.get("text", "")
                if text:
                    lbl = Gtk.Label(label=text)
                    lbl.set_line_wrap(True)
                    lbl.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
                    lbl.set_xalign(0)
                    lbl.set_selectable(True)
                    box.pack_start(lbl, False, False, 0)
                ev.add(box)
                vbox.pack_start(ev, False, False, 0)
                vbox.pack_start(Gtk.Separator(), False, False, 4)
                return
        # Text-only user message
        bubble = make_bubble(msg.get("text", ""), bubble_cls)
        vbox.pack_start(bubble, False, False, 0)

    else:
        # Assistant: render segments (text + LaTeX images)
        segments = msg.get("segments", [])
        if segments:
            ev = Gtk.EventBox()
            ev.get_style_context().add_class(bubble_cls)
            inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
            inner.set_margin_start(0)
            for seg in segments:
                if seg.get("type") == "text" and seg.get("content", "").strip():
                    lbl = Gtk.Label(label=seg["content"])
                    lbl.set_line_wrap(True)
                    lbl.set_line_wrap_mode(Pango.WrapMode.WORD_CHAR)
                    lbl.set_xalign(0)
                    lbl.set_selectable(True)
                    inner.pack_start(lbl, False, False, 0)
                elif seg.get("type") == "image" and seg.get("content"):
                    pb = load_pixbuf_scaled(seg["content"], max_width=500)
                    if pb:
                        inner.pack_start(Gtk.Image.new_from_pixbuf(pb), False, False, 0)
            ev.add(inner)
            vbox.pack_start(ev, False, False, 0)
        else:
            # Fallback: raw text
            bubble = make_bubble(msg.get("text", ""), bubble_cls)
            vbox.pack_start(bubble, False, False, 0)

    vbox.pack_start(Gtk.Separator(), False, False, 4)


def on_clear(_btn):
    try:
        os.remove(HISTORY)
    except FileNotFoundError:
        pass
    Gtk.main_quit()


def on_destroy(_win):
    remove_pid()
    Gtk.main_quit()


def build_window(history):
    win = Gtk.Window(title="XournalAI — Conversation")
    win.set_default_size(700, 580)
    win.connect("destroy", on_destroy)

    outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

    scroll = Gtk.ScrolledWindow()
    scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)

    vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    vbox.set_margin_start(16)
    vbox.set_margin_end(16)
    vbox.set_margin_top(12)
    vbox.set_margin_bottom(12)

    for msg in history:
        add_message(vbox, msg)

    scroll.add(vbox)
    outer.pack_start(scroll, True, True, 0)

    # Button bar
    bar = Gtk.Box(spacing=8)
    bar.set_margin_start(10)
    bar.set_margin_end(10)
    bar.set_margin_top(6)
    bar.set_margin_bottom(8)

    clear_btn = Gtk.Button(label="Clear History")
    clear_btn.connect("clicked", on_clear)
    bar.pack_start(clear_btn, False, False, 0)

    close_btn = Gtk.Button(label="Close")
    close_btn.connect("clicked", lambda _: Gtk.main_quit())
    bar.pack_end(close_btn, False, False, 0)

    outer.pack_start(bar, False, False, 0)
    win.add(outer)
    win.show_all()

    # Scroll to bottom once layout is settled
    def scroll_bottom(_):
        adj = scroll.get_vadjustment()
        adj.set_value(adj.get_upper())
        return False
    GLib.idle_add(scroll_bottom, None)


def main():
    install_css()

    data    = json.load(sys.stdin)
    history = data.get("history", [])

    save_pid()
    signal.signal(signal.SIGTERM, lambda *_: (remove_pid(), Gtk.main_quit()))

    if not history:
        dlg = Gtk.MessageDialog(
            message_type=Gtk.MessageType.INFO,
            buttons=Gtk.ButtonsType.OK,
            text="No conversation history.",
        )
        dlg.run()
        dlg.destroy()
        return

    build_window(history)
    Gtk.main()


if __name__ == "__main__":
    main()
