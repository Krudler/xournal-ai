#!/usr/bin/env python3
"""
Reads JSON from stdin:
  {
    "api_key": "...",
    "messages": [  # full conversation history as Claude API format
      {"role": "user",      "content": [...]},
      {"role": "assistant", "content": [...]},
      ...
    ],
    "render_prefix": "..."  # unique prefix for LaTeX PNG filenames
  }
Writes JSON to stdout:
  {
    "segments": [{"type": "text"|"image", "content": "..."}],
    "response_text": "..."  # raw text for history storage
  }
"""
import sys
import json
import re

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import anthropic


def render_latex(expr, prefix, index):
    path = f"/tmp/xai_latex_{prefix}_{index}.png"
    fig = plt.figure(figsize=(6, 0.8))
    fig.patch.set_alpha(0)
    try:
        fig.text(0.05, 0.5, f"${expr}$", fontsize=18, va="center")
        plt.savefig(path, bbox_inches="tight", dpi=150, transparent=True)
    except Exception:
        return None
    finally:
        plt.close(fig)
    return path


def parse_response(text, prefix):
    segments = []
    pattern = re.compile(r'\$\$(.+?)\$\$|\$(.+?)\$', re.DOTALL)
    last = 0
    latex_idx = 0
    for m in pattern.finditer(text):
        if m.start() > last:
            segments.append({"type": "text", "content": text[last:m.start()]})
        expr = (m.group(1) or m.group(2)).strip()
        path = render_latex(expr, prefix, latex_idx)
        if path:
            segments.append({"type": "image", "content": path})
            latex_idx += 1
        else:
            segments.append({"type": "text", "content": m.group(0)})
        last = m.end()
    if last < len(text):
        segments.append({"type": "text", "content": text[last:]})
    return segments


def main():
    data = json.load(sys.stdin)
    api_key       = data["api_key"]
    messages      = data["messages"]       # full conversation as Claude API format
    render_prefix = data.get("render_prefix", "0")

    client = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=messages,
    )

    response_text = message.content[0].text
    segments = parse_response(response_text, render_prefix)
    print(json.dumps({"segments": segments, "response_text": response_text}))


if __name__ == "__main__":
    main()
