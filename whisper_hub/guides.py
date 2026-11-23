"""Client setup instructions, kept as data so they are easy to refine.

Placeholders available in steps: ``{base_url}`` (recommended server root),
``{api_base}`` (``.../v1/``), ``{sdk_base}`` (``.../v1``), ``{endpoint}`` (full
transcription URL), ``{api_key}``, ``{model}`` and ``{device_name}``.
"""

from __future__ import annotations

from typing import Any

KIND_LABELS = {
    "iphone": "iPhone",
    "ipad": "iPad",
    "mac": "Mac",
    "windows": "Windows",
    "linux": "Linux",
    "android": "Android",
    "web": "Web browser",
    "other": "Other device",
}

IOS_STEPS = [
    "Open **Shortcuts**, create a shortcut, and name it “Dictate to Whisper Hub”.",
    "Add **Record Audio**. The first run asks for microphone permission.",
    "Add **Get Contents of URL**. URL: `{endpoint}`. Tap **Show More**, set Method to **POST** "
    "and Request Body to **Form**.",
    "Add form fields: `file` = **Recorded Audio** (type File), `model` = `{model}`, "
    "`response_format` = `text`.",
    "Add a Header: `Authorization` = `Bearer {api_key}`.",
    "Add **Get Text from Input**, then **Copy to Clipboard**, then **Show Notification**.",
    "The first run asks permission to connect to the LAN address; allow it. Plain HTTP on the "
    "LAN works.",
    "Trigger it from the Action Button, Back Tap, the Home Screen, a widget, or Siri.",
]

IOS_ALTERNATIVES = [
    {
        "title": "OpenWhispr iOS — BYOK → Custom",
        "steps": [
            "Install **OpenWhispr** and open Settings → Providers → **Bring Your Own Key** → **Custom**.",
            "Server URL: `{api_base}`. Model ID: `{model}`. API key: the key above.",
            "Plain HTTP to a private LAN address is allowed. Dictation inserts text at the cursor "
            "through the OpenWhispr keyboard.",
        ],
    },
    {
        "title": "VivaDicta — custom endpoint",
        "steps": [
            "Install **VivaDicta** and open its transcription settings.",
            "Choose the **custom OpenAI-compatible** service. Endpoint URL: `{endpoint}` "
            "(the full URL). API key: the key above.",
            "VivaDicta allows arbitrary HTTP loads, so the LAN address works. It keeps its own "
            "notes and search on-device.",
        ],
    },
]

MAC_STEPS = [
    "Install **OpenWhispr** and open Settings → Transcription → **Custom provider**.",
    "Server URL: `{api_base}`. Model ID: `{model}`. API key: the key above.",
    "Plain HTTP to a private LAN address is allowed. Pick a global shortcut; OpenWhispr "
    "auto-pastes the result.",
]

MAC_ALTERNATIVES = [
    {
        "title": "VoiceInk — full endpoint",
        "steps": [
            "Install **VoiceInk** and add a custom OpenAI-compatible model.",
            "API Endpoint: `{endpoint}` (the full URL). API Key: the key above. Model Name: `{model}`.",
            "VoiceInk’s connection test rejects plain HTTP on a LAN address. Use the HTTPS URL if "
            "the setup page shows one; otherwise saving still works and transcription can proceed "
            "even though the test reports a scheme error.",
            "VoiceInk’s global shortcut and auto-paste make it the best native macOS option.",
        ],
    },
    {"title": "macOS Shortcuts", "steps": IOS_STEPS},
]

WINDOWS_STEPS = [
    "Install **OpenWhispr** and open Settings → Transcription → **Custom provider**.",
    "Server URL: `{api_base}`. Model ID: `{model}`. API key: the key above.",
    "Plain HTTP on a private LAN is allowed. OpenWhispr auto-pastes on Windows.",
]

WINDOWS_ALTERNATIVES = [
    {
        "title": "Whispering — copy only",
        "steps": [
            "Install **Whispering** and add a custom OpenAI connection.",
            "Base URL: `{api_base}`. API key: the key above. It may call `/v1/models` when adding "
            "the connection.",
            "Whispering has no auto-paste; use its Copy button to move text out.",
        ],
    }
]

LINUX_STEPS = [
    "Install **OpenWhispr** for Linux and open Settings → Transcription → **Custom provider**.",
    "Server URL: `{api_base}`. Model ID: `{model}`. API key: the key above.",
    "Plain HTTP on a private LAN is allowed. Auto-paste works on X11; Wayland falls back to the "
    "clipboard.",
]

LINUX_ALTERNATIVES = WINDOWS_ALTERNATIVES

ANDROID_STEPS = [
    "Install **Dictate** (keyboard) and enable the Dictate keyboard in Android’s language & "
    "input settings.",
    "Open Dictate’s OpenAI-compatible provider settings. Base URL: `{api_base}` — keep the "
    "trailing `/v1/`; Dictate appends `audio/transcriptions` itself.",
    "API key: the key above. Model: `{model}`.",
    "Leave language on **auto-detect**; pinning a language overrides Whisper’s detection.",
    "Dictate calls `GET /v1/models` when it starts recording (“wake up early”). That request is "
    "cheap and never loads the model.",
    "Text is inserted at the cursor by the keyboard. Plain HTTP on the LAN is supported.",
]

WEB_STEPS = [
    "Use the **Record** button in this dashboard’s header.",
    "Browser recording needs a secure origin: `https://` or `http://localhost`. On a plain-HTTP "
    "LAN address the browser blocks the microphone; use the HTTPS URL if your setup has one.",
]

GENERIC_STEPS = [
    "Apps that take a base URL and append `/audio/transcriptions`: use `{api_base}` (the trailing "
    "slash is fine).",
    "Apps that take a complete URL: use `{endpoint}`.",
    "Send the key as `Authorization: Bearer {api_key}` or `X-API-Key`. Model: `{model}` (the server "
    "ignores it and uses its configured model).",
    "Every format is supported: `json` (default), `text`, `verbose_json`, `srt`, `vtt`.",
]

GUIDES: dict[str, dict[str, Any]] = {
    "iphone": {
        "title": "iPhone / iPad — Apple Shortcuts",
        "client": "Shortcuts · OpenWhispr · VivaDicta",
        "steps": IOS_STEPS,
        "alternatives": IOS_ALTERNATIVES,
    },
    "ipad": {
        "title": "iPad — Apple Shortcuts",
        "client": "Shortcuts · OpenWhispr · VivaDicta",
        "steps": IOS_STEPS,
        "alternatives": IOS_ALTERNATIVES,
    },
    "mac": {
        "title": "Mac — OpenWhispr or VoiceInk",
        "client": "OpenWhispr · VoiceInk · Shortcuts",
        "steps": MAC_STEPS,
        "alternatives": MAC_ALTERNATIVES,
    },
    "windows": {
        "title": "Windows — OpenWhispr or Whispering",
        "client": "OpenWhispr · Whispering",
        "steps": WINDOWS_STEPS,
        "alternatives": WINDOWS_ALTERNATIVES,
    },
    "linux": {
        "title": "Linux — OpenWhispr or Whispering",
        "client": "OpenWhispr · Whispering",
        "steps": LINUX_STEPS,
        "alternatives": LINUX_ALTERNATIVES,
    },
    "android": {
        "title": "Android — Dictate keyboard",
        "client": "Dictate",
        "steps": ANDROID_STEPS,
        "alternatives": [],
    },
    "web": {
        "title": "Browser — the Record button",
        "client": "Whisper Hub dashboard",
        "steps": WEB_STEPS,
        "alternatives": [],
    },
    "other": {
        "title": "Any OpenAI-compatible client",
        "client": "Generic",
        "steps": GENERIC_STEPS,
        "alternatives": [],
    },
}

ENDPOINTS = [
    {
        "method": "POST",
        "path": "/v1/audio/transcriptions",
        "description": "Transcribe audio. English stays English; other languages are translated to English.",
    },
    {
        "method": "POST",
        "path": "/v1/audio/translations",
        "description": "Same policy and formats as transcriptions (OpenAI-compatible alias).",
    },
    {"method": "GET", "path": "/v1/models", "description": "Model list for clients that probe it."},
    {"method": "GET", "path": "/api/device/me", "description": "Shows which device the key belongs to."},
    {"method": "GET", "path": "/healthz", "description": "Unauthenticated health and model status."},
]

MODEL_NAME = "whisper-1"


def _join(base: str, suffix: str) -> str:
    return base.rstrip("/") + suffix


def _urls(base_url: str, https_url: str | None) -> dict[str, str]:
    recommended = (https_url or base_url).rstrip("/")
    api_base = _join(recommended, "/v1")
    return {
        "base_url": recommended,
        "lan_url": base_url.rstrip("/"),
        "api_base": api_base + "/",
        "sdk_base": api_base,
        "endpoint": api_base + "/audio/transcriptions",
    }


def _format(value: str, context: dict[str, str]) -> str:
    for key, replacement in context.items():
        value = value.replace("{" + key + "}", replacement)
    return value


def _format_steps(steps: list[str], context: dict[str, str]) -> list[str]:
    return [_format(step, context) for step in steps]


def _guide_payload(guide: dict[str, Any], context: dict[str, str]) -> dict[str, Any]:
    return {
        "title": guide["title"],
        "client": guide["client"],
        "steps": _format_steps(guide["steps"], context),
        "alternatives": [
            {
                "title": alternative["title"],
                "steps": _format_steps(alternative["steps"], context),
            }
            for alternative in guide.get("alternatives", [])
        ],
    }


def _curl(endpoint: str, api_key: str) -> str:
    return (
        f"curl -sS {endpoint} \\\n"
        f'  -H "Authorization: Bearer {api_key}" \\\n'
        "  -F file=@recording.m4a \\\n"
        f"  -F model={MODEL_NAME} \\\n"
        "  -F response_format=text"
    )


def _sdk(api_base: str, api_key: str) -> str:
    return (
        "from openai import OpenAI\n\n"
        "client = OpenAI(\n"
        f'    base_url="{api_base}",\n'
        f'    api_key="{api_key}",\n'
        ")\n"
        'with open("recording.m4a", "rb") as audio:\n'
        "    result = client.audio.transcriptions.create(\n"
        f'        model="{MODEL_NAME}",\n'
        "        file=audio,\n"
        "    )\n"
        "print(result.text)"
    )


def setup_payload(
    base_url: str,
    api_key: str,
    device_name: str,
    kind: str,
    model: str,
    https_url: str | None = None,
) -> dict[str, Any]:
    urls = _urls(base_url, https_url)
    context = {
        **urls,
        "api_key": api_key,
        "model": MODEL_NAME,
        "device_name": device_name,
    }
    guide = GUIDES.get(kind, GUIDES["other"])
    return {
        "device_name": device_name,
        "kind": kind,
        "kind_label": KIND_LABELS.get(kind, "Other device"),
        **urls,
        "https_url": https_url,
        "api_key": api_key,
        "model": MODEL_NAME,
        "server_model": model,
        "values": [
            {
                "label": "Base URL — for apps that append /audio/transcriptions",
                "value": urls["api_base"],
            },
            {
                "label": "Full endpoint — for apps that take a complete URL",
                "value": urls["endpoint"],
            },
            {"label": "API key", "value": api_key, "secret": True},
            {"label": "Model (required by some clients)", "value": MODEL_NAME},
        ],
        "guide": _guide_payload(guide, context),
        "generic": _guide_payload(GUIDES["other"], context),
        "curl": _curl(urls["endpoint"], api_key),
        "sdk_snippet": _sdk(urls["sdk_base"], api_key),
    }


def guides_for_setup(base_url: str, model: str, https_url: str | None = None) -> dict[str, Any]:
    """Guide data for the dashboard Setup page (no real key embedded)."""
    urls = _urls(base_url, https_url)
    context = {
        **urls,
        "api_key": "<your device key>",
        "model": MODEL_NAME,
        "device_name": "this device",
    }
    kinds = []
    for kind, guide in GUIDES.items():
        if kind == "ipad":
            continue
        kinds.append({"kind": kind, "label": KIND_LABELS.get(kind, kind), **_guide_payload(guide, context)})
    return {
        **urls,
        "https_url": https_url,
        "model": MODEL_NAME,
        "server_model": model,
        "endpoints": ENDPOINTS,
        "curl": _curl(urls["endpoint"], "<your device key>"),
        "sdk_snippet": _sdk(urls["sdk_base"], "<your device key>"),
        "kinds": kinds,
    }
