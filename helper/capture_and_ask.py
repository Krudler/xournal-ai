#!/usr/bin/env python3
"""
Orchestrates the full XournalAI flow AFTER the Lua callback has returned,
so Xournal's main thread is free to serve clipboard requests.

Usage: capture_and_ask.py <config_path> <plugin_dir>
"""
import sys
import json
import os
import signal
import subprocess
import time
import datetime

LOG        = "/tmp/xai_debug.log"
HISTORY    = "/tmp/xai_history.json"
PID_FILE   = "/tmp/xai_response.pid"
CAPTURE_DIR = "/tmp/xai_captures"


def log(msg):
    with open(LOG, "a") as f:
        f.write(datetime.datetime.now().strftime("%H:%M:%S") + " [py] " + msg + "\n")


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def read_settings(config_path):
    try:
        with open(config_path) as f:
            s = json.load(f)
        return (
            s.get("api_key", ""),
            s.get("python_path", "python3"),
            s.get("default_prompt", "What is shown here?"),
            s.get("auto_send", False),
            s.get("image_background", "white"),
        )
    except Exception as e:
        log(f"read_settings error: {e}")
        return "", "python3", "What is shown here?", False, "white"


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

def load_history():
    try:
        with open(HISTORY) as f:
            return json.load(f)
    except Exception:
        return []


def save_history(history):
    with open(HISTORY, "w") as f:
        json.dump(history, f, indent=2)


# ---------------------------------------------------------------------------
# Clipboard image capture
# ---------------------------------------------------------------------------

def get_clipboard_targets():
    try:
        r = subprocess.run(
            ["xclip", "-selection", "clipboard", "-t", "TARGETS", "-o"],
            capture_output=True, text=True, timeout=5,
        )
        return [t.strip() for t in r.stdout.strip().split("\n") if t.strip()]
    except Exception as e:
        log(f"xclip TARGETS error: {e}")
        return []


def get_clipboard_bytes(target):
    try:
        r = subprocess.run(
            ["xclip", "-selection", "clipboard", "-t", target, "-o"],
            capture_output=True, timeout=10,
        )
        return r.stdout if r.returncode == 0 else None
    except Exception as e:
        log(f"xclip {target} error: {e}")
        return None


def svg_to_png(svg_bytes, output_path):
    try:
        import cairosvg
        cairosvg.svg2png(bytestring=svg_bytes, write_to=output_path, dpi=150)
        if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
            log(f"cairosvg OK -> {output_path}")
            return True
    except Exception as e:
        log(f"cairosvg failed: {e}")
    try:
        svg_path = "/tmp/xai_clipboard.svg"
        with open(svg_path, "wb") as f:
            f.write(svg_bytes)
        r = subprocess.run(
            ["inkscape", "--export-type=png", f"--export-filename={output_path}", svg_path],
            capture_output=True, timeout=30,
        )
        if r.returncode == 0 and os.path.exists(output_path):
            log("inkscape OK")
            return True
    except Exception as e:
        log(f"inkscape failed: {e}")
    return False


def apply_background(image_path, bg_color):
    """Composite a PNG (possibly transparent) onto a solid white or black background."""
    try:
        from PIL import Image
        im = Image.open(image_path).convert("RGBA")
        fill = (0, 0, 0, 255) if bg_color == "black" else (255, 255, 255, 255)
        bg = Image.new("RGBA", im.size, fill)
        bg.paste(im, mask=im.split()[3])
        bg.convert("RGB").save(image_path)
        log(f"applied {bg_color} background to {image_path}")
    except Exception as e:
        log(f"apply_background error: {e}")


def get_clipboard_image():
    """Return path to captured PNG or None."""
    time.sleep(0.4)
    os.makedirs(CAPTURE_DIR, exist_ok=True)
    ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    out = os.path.join(CAPTURE_DIR, f"capture_{ts}.png")

    targets = get_clipboard_targets()
    log(f"clipboard targets: {targets}")

    if "image/png" in targets:
        data = get_clipboard_bytes("image/png")
        if data:
            with open(out, "wb") as f:
                f.write(data)
            log(f"image/png captured ({len(data)} bytes)")
            return out

    for t in ["image/svg+xml", "image/x-inkscape-svg"]:
        if t in targets:
            data = get_clipboard_bytes(t)
            if data:
                log(f"{t} captured, converting to PNG")
                if svg_to_png(data, out):
                    return out

    log("no usable clipboard image")
    return None


# ---------------------------------------------------------------------------
# Window management
# ---------------------------------------------------------------------------

def kill_old_response_window():
    if not os.path.exists(PID_FILE):
        return
    try:
        with open(PID_FILE) as f:
            pid = int(f.read().strip())
        os.kill(pid, signal.SIGTERM)
        time.sleep(0.15)
    except Exception:
        pass


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser(
        "~/.config/xournalpp-ai/settings.json")
    plugin_dir = sys.argv[2] if len(sys.argv) > 2 else os.path.dirname(
        os.path.abspath(__file__)) + "/.."

    log("capture_and_ask.py started")

    api_key, python_path, default_prompt, auto_send, image_background = read_settings(config_path)
    if not api_key:
        subprocess.run(["zenity", "--error",
                        "--text=No API key configured.\nUse Plugin > AI Settings."])
        sys.exit(1)

    # Capture clipboard image and apply chosen background
    image_path = get_clipboard_image() or ""
    if image_path:
        apply_background(image_path, image_background)

    # Get question
    if auto_send:
        question = default_prompt
        log(f"auto_send: using default prompt '{question}'")
    else:
        dlg = subprocess.run(
            ["zenity", "--entry", "--title=Ask AI", "--text=Your question:",
             f"--entry-text={default_prompt}"],
            capture_output=True, text=True,
        )
        if dlg.returncode != 0:
            log("question dialog cancelled")
            sys.exit(0)
        question = dlg.stdout.strip()
        if not question:
            sys.exit(0)

    log(f"question: {question!r} | image: {image_path!r}")

    # Load history and append new user message
    history = load_history()
    history.append({
        "role": "user",
        "text": question,
        "image_path": image_path,
    })

    # Build Claude API messages array from full history
    api_messages = []
    for msg in history:
        if msg["role"] == "user":
            content = []
            img = msg.get("image_path", "")
            if img and os.path.exists(img):
                import base64
                with open(img, "rb") as f:
                    b64 = base64.standard_b64encode(f.read()).decode()
                content.append({"type": "image",
                                 "source": {"type": "base64",
                                            "media_type": "image/png",
                                            "data": b64}})
            content.append({"type": "text", "text": msg["text"]})
            api_messages.append({"role": "user", "content": content})
        else:
            api_messages.append({"role": "assistant",
                                  "content": [{"type": "text",
                                               "text": msg.get("text", "")}]})

    # Unique prefix for LaTeX render files for this response
    render_prefix = datetime.datetime.now().strftime("%H%M%S%f")

    api_input = json.dumps({
        "api_key": api_key,
        "messages": api_messages,
        "render_prefix": render_prefix,
    }).encode()

    # Call claude_api.py
    log("calling claude_api.py")
    helper  = os.path.join(plugin_dir, "helper", "claude_api.py")
    viewer  = os.path.join(plugin_dir, "helper", "show_response.py")

    try:
        with open("/tmp/xai_error.log", "w") as err_f:
            proc = subprocess.run(
                [python_path, helper],
                input=api_input,
                stdout=subprocess.PIPE,
                stderr=err_f,
            )
    except Exception as e:
        log(f"subprocess error: {e}")
        subprocess.run(["zenity", "--error", f"--text=Failed to run AI helper:\n{e}"])
        sys.exit(1)

    log(f"claude_api.py exited code={proc.returncode}, "
        f"stdout={len(proc.stdout or b'')} bytes")

    if not proc.stdout:
        log("no output from claude_api.py")
        subprocess.run(["zenity", "--error",
                        "--text=Error calling AI. Check /tmp/xai_error.log"])
        sys.exit(1)

    try:
        result = json.loads(proc.stdout)
    except Exception as e:
        log(f"JSON parse error: {e}")
        subprocess.run(["zenity", "--error", "--text=Invalid response from AI helper."])
        sys.exit(1)

    # Append assistant message to history
    history.append({
        "role": "assistant",
        "text": result.get("response_text", ""),
        "segments": result.get("segments", []),
    })
    save_history(history)

    # Kill old response window and show new one with full history
    kill_old_response_window()

    env = os.environ.copy()
    env["PYTHONPATH"] = "/usr/lib/python3/dist-packages"
    subprocess.run(
        ["/usr/bin/python3", viewer],
        input=json.dumps({"history": history}).encode(),
        env=env,
    )
    log("capture_and_ask.py done")


if __name__ == "__main__":
    main()
