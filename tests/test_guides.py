from __future__ import annotations

import json

from fastapi.testclient import TestClient


def test_guides_match_researched_clients(admin: TestClient):
    body = admin.get("/api/admin/setup").json()
    kinds = {kind["kind"]: kind for kind in body["kinds"]}

    assert "Shortcuts" in kinds["iphone"]["title"]
    assert "OpenWhispr" in kinds["iphone"]["client"]
    iphone_text = json.dumps(kinds["iphone"])
    assert "VivaDicta" in iphone_text
    assert "Record Audio" in iphone_text
    assert "whisper-1" in iphone_text

    assert "OpenWhispr" in kinds["mac"]["title"]
    mac_text = json.dumps(kinds["mac"])
    assert "VoiceInk" in mac_text
    assert "connection test" in mac_text

    for kind in ("windows", "linux"):
        assert "OpenWhispr" in kinds[kind]["title"]
        assert "Whispering" in kinds[kind]["client"]

    android_steps = " ".join(kinds["android"]["steps"])
    assert "Dictate" in kinds["android"]["title"]
    assert "trailing `/v1/`" in android_steps or "trailing /v1/" in android_steps
    assert "auto-detect" in android_steps
    assert "/v1/models" in android_steps

    generic = json.dumps(kinds["other"])
    assert "curl" not in generic.lower()  # the curl block is separate
    assert body["curl"].startswith("curl ")
    assert "OpenAI" in body["sdk_snippet"]
    assert "whisper-1" in body["sdk_snippet"]

    # Do not recommend clients the research could not verify.
    everything = json.dumps(body)
    for unverified in ("Spokenly", "MacWhisper", "Tasker", "AutoVoice"):
        assert unverified not in everything


def test_setup_payload_has_three_copyable_values_and_model():
    from whisper_hub.guides import setup_payload

    payload = setup_payload(
        "http://hub.lan:8765",
        "whk_test",
        "Phone",
        "iphone",
        "large-v3",
        "https://hub.example.com",
    )
    assert payload["api_base"] == "https://hub.example.com/v1/"
    assert payload["endpoint"] == "https://hub.example.com/v1/audio/transcriptions"
    assert payload["lan_url"] == "http://hub.lan:8765"
    assert payload["model"] == "whisper-1"
    assert payload["server_model"] == "large-v3"
    assert [item["value"] for item in payload["values"]] == [
        "https://hub.example.com/v1/",
        "https://hub.example.com/v1/audio/transcriptions",
        "whk_test",
        "whisper-1",
    ]
    assert payload["guide"]["alternatives"]
