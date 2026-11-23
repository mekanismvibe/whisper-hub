# Architecture

Whisper Hub is a single Python process: FastAPI serves the OpenAI-compatible
audio API, the admin API, the pairing pages and a small vanilla-JS dashboard.
SQLite stores devices, pairing codes, transcripts and settings. Audio bytes are
decoded from memory with PyAV and never written to disk.

## Request flow

```
client (API key) ──► BodyLimitMiddleware ──► /v1/audio/{transcriptions,translations}
                         │                        │
                         │                        ▼
                         │              in-memory multipart parse
                         │                        │
                         │                        ▼
                         │              faster-whisper decode_audio()
                         │                        │
                         │                        ▼
                         │                language detection
                         │                  ├─ English  → transcribe (Whisper or Parakeet)
                         │                  └─ other    → translate with Whisper
                         │                        │
                         ▼                        ▼
                 SQLite (text only) ◄── store transcript + metadata
                                              │
                                              ▼
                       json / text / verbose_json / srt / vtt
```

- `/v1/audio/translations` shares the same policy as `/v1/audio/transcriptions`.
- Every response includes `X-Whub-Detected-Language`, `X-Whub-Task` and, when
  text was stored, `X-Whub-Transcription-Id`.
- Apple Shortcuts user agents default to plain text, because a Shortcut shows
  the raw response body.
- The inference semaphore (`max_concurrency`) bounds concurrent model calls.
  Model loading, idle unload and hot swaps run in separate threads so the event
  loop stays responsive.

## Language policy

1. Whisper detects the spoken language from the first pass.
2. English audio is transcribed as English and is never sent through the
   translate task. A low-confidence non-English result is re-decoded as English
   when English is a plausible alternative (`lang_confidence`).
3. Everything else uses the translation model (`translate_model`, or the main
   model when it is translatable). Only the translation is consumed and stored.
4. If the optional Parakeet engine is enabled, English is transcribed by
   Parakeet after Whisper's language head has detected English. Whisper still
   translates other languages. A Parakeet failure falls back to Whisper for that
   request.
5. Clients may send a `language` hint; it is ignored unless
   `honor_client_language` is enabled.

Distil and Turbo models cannot translate. The catalog marks them and the UI and
settings validation refuse to use them as the translation model.

## Data model

SQLite (`data/whisper.db`, mode 0600) has these tables:

| table | contents |
| --- | --- |
| `devices` | name, kind, status, SHA-256 hash and prefix of the per-device key, timestamps, last-seen IP/user agent |
| `pairing_codes` | hashed one-time pairing codes with a 15-minute expiry |
| `transcriptions` | text, detected language, probability, task, duration, processing time, model, endpoint |
| `transcriptions_fts` | FTS5 index over transcript text (external-content) |
| `settings` | key/value runtime settings, scrypt admin-password hash, setup flag |

Settings resolution is `WHUB_*` environment variable → `settings` table →
built-in default. Host, port and data directory are environment/CLI only.
Changing a model-related setting loads a replacement engine in the background;
the old engine keeps serving until the new one is ready, then the swap is
atomic. A failed load records an error and leaves the old engine untouched.

Passwords are hashed with `hashlib.scrypt` (N=2^14, r=8, p=1). Dashboard
sessions are signed cookies; "sign out all sessions" rotates the signing key.
Device API keys are random `whk_…` tokens; only their SHA-256 hash is stored.

## First-run setup

If no `WHUB_ADMIN_PASSWORD` and no password hash exist, the server enters setup
mode. It writes a one-time token to `data/setup_token` (0600) and logs a
`/setup?token=…` URL. Admin APIs return `409 setup_required` until the wizard
finishes. A legacy `data/admin_password` file is hashed into the database on
startup and left in place so existing installations keep working.

## Privacy

- Audio is read into memory and released after decoding. There is no audio
  file, cache or temp spool. The container mounts `/tmp` as tmpfs as defence in
  depth.
- Transcript text is stored to provide the shared searchable history; the
  dashboard can delete one entry or all history and export it as JSON/CSV.
- Logs never include transcript text or audio. Model failures log the exception
  type/message only.
- The optional Parakeet/Photon runtime is third-party software. When enabled it
  sends usage telemetry (hostname, GPU, request counts; no audio or text) to
  `api.moondream.ai`. Whisper-only setups make no outbound calls except model
  downloads from Hugging Face.
