"""HTML pages for pairing and one-time key reveal. No template engine needed."""

from __future__ import annotations

import html
import re
from typing import Any

from .guides import KIND_LABELS

_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")
_CODE_RE = re.compile(r"`([^`]+)`")


def rich_text(value: str) -> str:
    """Escape then apply the two inline marks used in guide steps."""
    escaped = html.escape(value)
    escaped = _CODE_RE.sub(r"<code>\1</code>", escaped)
    escaped = _BOLD_RE.sub(r"<strong>\1</strong>", escaped)
    return escaped


def _layout(title: str, body: str, *, wide: bool = False, centered: bool = False) -> str:
    width = "880px" if wide else "620px"
    shell_class = "shell shell-center" if centered else "shell"
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex, nofollow">
<meta name="referrer" content="no-referrer">
<title>{html.escape(title)} · Whisper Hub</title>
<link rel="icon" href="/static/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="/static/pair.css">
</head>
<body>
<main class="{shell_class}" style="--shell-width:{width}">
  <header class="brand">
    <span class="brand-mark" aria-hidden="true">
      <svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="2"
           stroke-linecap="round"><path d="M3 12h2M7 8v8M11 4v16M15 7v10M19 10v4M21 12h0"/></svg>
    </span>
    <span>Whisper Hub</span>
  </header>
  {body}
  <footer class="foot">One server. Every device. English text everywhere.</footer>
</main>
<script src="/static/pair.js" defer></script>
</body>
</html>
"""


def render_pair_page(device_name: str, kind: str, base_url: str, code: str, expires_at: str) -> str:
    kind_label = KIND_LABELS.get(kind, "device")
    body = f"""
  <section class="card hero">
    <p class="eyebrow">Pairing request</p>
    <h1>Link “{html.escape(device_name)}”</h1>
    <p class="lede">This {html.escape(kind_label)} will appear in your Whisper Hub history
    as its own device. You can revoke it any time from the dashboard.</p>
    <dl class="facts">
      <div><dt>Server</dt><dd>{html.escape(base_url)}</dd></div>
      <div><dt>Link expires</dt><dd>{html.escape(expires_at)}</dd></div>
    </dl>
    <form method="post" action="/pair/{html.escape(code)}">
      <button class="btn btn-primary btn-lg" type="submit">Link this device</button>
    </form>
    <p class="hint">Only tap once, on the device you are pairing. The API key is shown on the next
    screen and never again.</p>
  </section>
"""
    return _layout("Pair device", body, centered=True)


def _steps_html(steps: list[str]) -> str:
    return "<ol class=\"steps\">" + "".join(f"<li>{rich_text(step)}</li>" for step in steps) + "</ol>"


def render_setup_page(payload: dict[str, Any]) -> str:
    values = []
    for item in payload["values"]:
        value = html.escape(item["value"])
        secret = " secret" if item.get("secret") else ""
        values.append(
            f'<div class="copy-row"><label>{html.escape(item["label"])}</label>'
            f'<div class="copy-box{secret}"><code>{value}</code>'
            f'<button class="btn btn-quiet" type="button" data-copy="{html.escape(item["value"], quote=True)}">'
            "Copy</button></div></div>"
        )
    values_block = "".join(values)
    guide = payload["guide"]
    alternatives = "".join(
        f'<details class="details"><summary>{rich_text(item["title"])}</summary>'
        f'{_steps_html(item["steps"])}</details>'
        for item in guide["alternatives"]
    )
    if payload.get("https_url"):
        url_note = (
            f'<p class="note">Recommended URL: <code>{html.escape(payload["base_url"])}</code> '
            f'(HTTPS). The LAN address <code>{html.escape(payload["lan_url"])}</code> also works for '
            "most clients; the browser Record button needs the HTTPS URL.</p>"
        )
    else:
        url_note = (
            '<p class="note">Plain HTTP works for most LAN clients. The browser Record button needs '
            "an HTTPS origin (or localhost); set <code>WHUB_HTTPS_URL</code> to show one here.</p>"
        )
    body = f"""
  <section class="card hero success">
    <p class="eyebrow"><span class="dot"></span> Device linked</p>
    <h1>{html.escape(payload["device_name"])}</h1>
    <p class="lede">Paste these values into your transcription app. The API key is shown
    <strong>only once</strong> — store it in a password manager if you might need it again.</p>
    {values_block}
    {url_note}
  </section>

  <section class="card">
    <p class="eyebrow">Next steps</p>
    <h2>{rich_text(guide["title"])}</h2>
    {_steps_html(guide["steps"])}
    {alternatives}
    <h3 class="subhead">Any OpenAI-compatible client</h3>
    {_steps_html(payload["generic"]["steps"])}
    <p class="label">curl</p>
    <pre class="code"><code>{html.escape(payload["curl"])}</code></pre>
    <p class="label">OpenAI Python SDK</p>
    <pre class="code"><code>{html.escape(payload["sdk_snippet"])}</code></pre>
  </section>

  <p class="center"><a class="link" href="/">Open the dashboard</a></p>
"""
    return _layout("Device linked", body, wide=True)


def render_error_page(title: str, message: str, *, code_hint: str = "") -> str:
    hint = f'<p class="hint">{html.escape(code_hint)}</p>' if code_hint else ""
    body = f"""
  <section class="card hero">
    <p class="eyebrow">Pairing unavailable</p>
    <h1>{html.escape(title)}</h1>
    <p class="lede">{html.escape(message)}</p>
    {hint}
    <p><a class="link" href="/">Go to the dashboard</a></p>
  </section>
"""
    return _layout("Pairing unavailable", body)
