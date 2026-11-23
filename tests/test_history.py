from __future__ import annotations

import sqlite3

from fastapi.testclient import TestClient

from .conftest import create_and_pair


def _seed(client: TestClient) -> tuple[dict, dict, list[dict]]:
    first, _, _ = create_and_pair(client, "Workstation", "linux")
    second, _, _ = create_and_pair(client, "Tablet", "ipad")
    db = client.app.state.db
    texts = [
        (first["id"], "Team meeting notes about the quarterly roadmap"),
        (first["id"], "Grocery list: milk, eggs, bread"),
        (second["id"], "Meeting follow-up with the design team"),
        (second["id"], "A note about Spanish class"),
        (first["id"], "meeting"),
        (second["id"], "Unrelated text"),
    ]
    rows = []
    for device_id, text in texts:
        rows.append(
            db.insert_transcription(
                device_id=device_id,
                text=text,
                detected_language="en",
                language_probability=0.99,
                task="transcribe",
                audio_duration_s=2.0,
                processing_ms=10,
                model="fake-model",
                endpoint="transcriptions",
                client_user_agent="pytest",
            )
        )
    return first, second, rows


def test_fts_search_device_filter_and_paging(admin: TestClient):
    first, second, rows = _seed(admin)

    meeting = admin.get("/api/admin/transcriptions", params={"q": "meet"}).json()
    texts = [item["text"] for item in meeting["items"]]
    assert len(texts) == 3
    assert all("meeting" in text.lower() for text in texts)

    upper = admin.get("/api/admin/transcriptions", params={"q": "MEETING"}).json()
    assert {item["id"] for item in upper["items"]} == {item["id"] for item in meeting["items"]}

    only_first = admin.get(
        "/api/admin/transcriptions", params={"device_id": first["id"]}
    ).json()
    assert len(only_first["items"]) == 3
    assert all(item["device_id"] == first["id"] for item in only_first["items"])

    combined = admin.get(
        "/api/admin/transcriptions", params={"q": "meeting", "device_id": second["id"]}
    ).json()
    assert [item["text"] for item in combined["items"]] == ["Meeting follow-up with the design team"]

    # Single-item pages must not skip rows when timestamps tie.
    conn = sqlite3.connect(admin.app.state.config.data_dir / "whisper.db")
    try:
        tied = rows[1]["created_at"]
        conn.execute(
            "UPDATE transcriptions SET created_at = ? WHERE id = ?",
            (tied, rows[2]["id"]),
        )
        conn.commit()
    finally:
        conn.close()

    seen: list[int] = []
    cursor = None
    for _ in range(20):
        params = {"limit": "1"}
        if cursor:
            params["before"] = cursor
        page = admin.get("/api/admin/transcriptions", params=params).json()
        seen.extend(item["id"] for item in page["items"])
        cursor = page["next_cursor"]
        if not cursor:
            break
    assert len(seen) == 6
    assert len(set(seen)) == 6
    assert set(seen) == {row["id"] for row in rows}


def test_fts_input_is_sanitized(admin: TestClient):
    _seed(admin)
    for query in ['" OR *', 'meeting OR "', "!!!", "*", "NEAR(a b)", "meet*"]:
        response = admin.get("/api/admin/transcriptions", params={"q": query})
        assert response.status_code == 200, (query, response.text)


def test_default_limit_and_delete(admin: TestClient):
    _, _, rows = _seed(admin)
    listing = admin.get("/api/admin/transcriptions").json()
    assert len(listing["items"]) == 6
    assert listing["items"][0]["id"] == rows[-1]["id"]

    target = rows[-1]["id"]
    assert admin.delete(f"/api/admin/transcriptions/{target}").status_code == 200
    assert admin.get(f"/api/admin/transcriptions/{target}").status_code == 404

    # FTS index is kept in sync by triggers.
    search = admin.get("/api/admin/transcriptions", params={"q": "unrelated"}).json()
    assert search["items"] == []


def test_stats_include_per_device_counts(admin: TestClient):
    first, second, _ = _seed(admin)
    stats = admin.get("/api/admin/stats").json()
    assert stats["transcriptions_total"] == 6
    assert stats["devices_active"] == 3  # web dashboard + two paired devices
    per_device = {item["id"]: item for item in stats["per_device"]}
    assert per_device[first["id"]]["transcriptions"] == 3
    assert per_device[second["id"]]["transcriptions"] == 3
    assert stats["model"] == "fake-model"
    assert stats["models_loaded"] is True


def test_invalid_cursor_is_rejected(admin: TestClient):
    response = admin.get("/api/admin/transcriptions", params={"before": "not-base64"})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_cursor"


def test_delete_history_via_device_keeps_others(admin: TestClient):
    first, second, _ = _seed(admin)
    assert admin.delete(f"/api/admin/devices/{first['id']}?delete_history=true").status_code == 200
    items = admin.get("/api/admin/transcriptions").json()["items"]
    assert items
    assert all(item["device_id"] == second["id"] for item in items)
