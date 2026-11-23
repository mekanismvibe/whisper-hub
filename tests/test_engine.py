from __future__ import annotations

from types import SimpleNamespace

import numpy as np

from whisper_hub.config import Config
from whisper_hub.engine import ParakeetModels, _warmup_parakeet, _warmup_whisper, run_policy


class FakeWhisperModel:
    def __init__(
        self,
        language: str,
        text: str,
        *,
        all_language_probs: list[tuple[str, float]] | None = None,
        english_text: str | None = None,
    ) -> None:
        self.language = language
        self.text = text
        self.all_language_probs = all_language_probs
        self.english_text = english_text
        self.calls: list[dict] = []
        self.detect_calls: list[dict] = []
        self.consumed = 0

    def detect_language(self, audio, **kwargs):
        self.detect_calls.append(kwargs)
        return self.language, 0.91, self.all_language_probs

    def transcribe(self, audio, **kwargs):
        self.calls.append(kwargs)
        info_kwargs = {
            "language": self.language,
            "language_probability": 0.91,
            "duration": 3.25,
        }
        if self.all_language_probs is not None:
            info_kwargs["all_language_probs"] = self.all_language_probs
        info = SimpleNamespace(**info_kwargs)
        text = self.english_text if kwargs.get("language") == "en" and self.english_text else self.text

        def segments():
            self.consumed += 1
            if text:
                yield SimpleNamespace(
                    id=0, start=0.0, end=3.25, text=" " + text, avg_logprob=-0.1
                )

        return segments(), info


class FakeModelSource:
    def __init__(self, primary: FakeWhisperModel, translator: FakeWhisperModel | None = None) -> None:
        self.primary = primary
        self.translator = translator or primary
        self.requests: list[bool] = []
        self.models_loaded = True

    def get_model(self, *, translate: bool):
        self.requests.append(translate)
        model = self.translator if translate else self.primary
        return model, "translate-model" if translate else "primary-model"

    def touch(self) -> None:
        pass


class FakeSpeechModel:
    def __init__(self, text: str = "hello from parakeet", error: BaseException | None = None) -> None:
        self.text = text
        self.error = error
        self.calls: list[dict] = []

    def transcribe(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return {
            "text": self.text,
            "duration_seconds": 3.25,
            "segments": [{"start": 0.0, "end": 3.25, "text": self.text}],
        }


class FakeSpeechSource:
    def __init__(self, model: FakeSpeechModel) -> None:
        self.model = model
        self.requests = 0
        self.models_loaded = True

    def get_model(self):
        self.requests += 1
        return self.model, "parakeet-ultra"

    def touch(self) -> None:
        pass


AUDIO = np.zeros(1600, dtype=np.float32)


def test_english_audio_is_transcribed_and_not_translated():
    primary = FakeWhisperModel("en", "hello there")
    translator = FakeWhisperModel("en", "SHOULD NOT APPEAR")
    source = FakeModelSource(primary, translator)

    result = run_policy(
        source,
        b"audio",
        prompt="Names: Alice",
        language_hint="es",
        beam_size=5,
        honor_client_language=False,
    )

    assert result.text == "hello there"
    assert result.task == "transcribe"
    assert result.model == "primary-model"
    assert result.detected_language == "en"
    assert result.duration_s == 3.25
    assert primary.consumed == 1
    assert source.requests == [False]
    assert translator.calls == []
    call = primary.calls[0]
    assert call["task"] == "transcribe"
    assert call["language"] is None  # client hint ignored by default
    assert call["vad_filter"] is True
    assert call["condition_on_previous_text"] is False
    assert call["initial_prompt"] == "Names: Alice"
    assert call["beam_size"] == 5


def test_non_english_audio_drops_transcription_and_runs_translation():
    primary = FakeWhisperModel("es", "transcripción original")
    translator = FakeWhisperModel("es", "the translated english text")
    source = FakeModelSource(primary, translator)

    result = run_policy(
        source,
        b"audio",
        prompt=None,
        language_hint=None,
        beam_size=3,
        honor_client_language=False,
    )

    assert result.text == "the translated english text"
    assert result.task == "translate"
    assert result.detected_language == "es"
    assert result.model == "translate-model"
    assert source.requests == [False, True]
    assert primary.consumed == 0, "the English-decoding generator must not be consumed"
    assert translator.consumed == 1
    assert translator.calls[0]["task"] == "translate"
    assert translator.calls[0]["language"] == "es"
    assert translator.calls[0]["beam_size"] == 5


def test_language_hint_is_used_only_when_enabled():
    primary = FakeWhisperModel("es", "hola")
    source = FakeModelSource(primary)

    run_policy(
        source,
        b"audio",
        prompt=None,
        language_hint="es",
        beam_size=5,
        honor_client_language=True,
    )
    assert primary.calls[0]["language"] == "es"


def test_empty_segments_produce_empty_text_without_error():
    primary = FakeWhisperModel("en", "")
    source = FakeModelSource(primary)
    result = run_policy(
        source,
        b"audio",
        prompt=None,
        language_hint=None,
        beam_size=5,
        honor_client_language=False,
    )
    assert result.text == ""
    assert result.segments == []
    assert result.task == "transcribe"


def test_low_confidence_non_english_is_transcribed_as_english():
    primary = FakeWhisperModel(
        "es",
        "texto original",
        all_language_probs=[("es", 0.31), ("en", 0.44), ("pt", 0.1)],
        english_text="hello there",
    )
    translator = FakeWhisperModel("es", "SHOULD NOT APPEAR")
    source = FakeModelSource(primary, translator)

    result = run_policy(
        source,
        b"audio",
        prompt=None,
        language_hint=None,
        beam_size=5,
        honor_client_language=False,
        lang_confidence=0.5,
    )

    assert result.task == "transcribe"
    assert result.text == "hello there"
    assert result.detected_language == "es"  # detection is stored even when overridden
    assert translator.calls == []
    assert source.requests == [False]
    assert primary.consumed == 1
    assert len(primary.calls) == 2
    assert primary.calls[0]["language"] is None
    assert primary.calls[1]["language"] == "en"
    assert primary.calls[1]["task"] == "transcribe"


def test_low_confidence_without_english_support_still_translates():
    primary = FakeWhisperModel(
        "es",
        "hola",
        all_language_probs=[("es", 0.32), ("en", 0.08), ("pt", 0.3)],
    )
    translator = FakeWhisperModel("es", "hello")
    source = FakeModelSource(primary, translator)

    result = run_policy(
        source,
        b"audio",
        prompt=None,
        language_hint=None,
        beam_size=5,
        honor_client_language=False,
        lang_confidence=0.5,
    )

    assert result.task == "translate"
    assert translator.consumed == 1


def test_english_audio_uses_parakeet_without_decoding_whisper_text():
    primary = FakeWhisperModel("en", "SHOULD NOT APPEAR")
    source = FakeModelSource(primary)
    speech = FakeSpeechSource(FakeSpeechModel("hello from parakeet"))

    result = run_policy(
        source,
        AUDIO,
        prompt="Names: Alice",
        language_hint=None,
        beam_size=5,
        honor_client_language=False,
        speech=speech,
    )

    assert result.text == "hello from parakeet"
    assert result.task == "transcribe"
    assert result.model == "parakeet-ultra"
    assert result.detected_language == "en"
    assert primary.consumed == 0, "whisper must not decode English text as well"
    assert primary.calls == []
    assert len(primary.detect_calls) == 1
    assert primary.detect_calls[0]["vad_filter"] is True
    assert speech.requests == 1
    assert speech.model.calls[0]["sample_rate"] == 16000
    assert speech.model.calls[0]["timestamps"] == "segment"


def test_non_english_audio_still_translates_with_whisper():
    primary = FakeWhisperModel("es", "transcripción original")
    translator = FakeWhisperModel("es", "the translated english text")
    source = FakeModelSource(primary, translator)
    speech = FakeSpeechSource(FakeSpeechModel("SHOULD NOT APPEAR"))

    result = run_policy(
        source,
        AUDIO,
        prompt=None,
        language_hint=None,
        beam_size=3,
        honor_client_language=False,
        speech=speech,
    )

    assert result.text == "the translated english text"
    assert result.task == "translate"
    assert result.model == "translate-model"
    assert result.detected_language == "es"
    assert speech.requests == 0
    assert primary.consumed == 0
    assert translator.consumed == 1
    assert translator.calls[0]["language"] == "es"


def test_low_confidence_english_uses_parakeet():
    primary = FakeWhisperModel(
        "es",
        "texto original",
        all_language_probs=[("es", 0.31), ("en", 0.44), ("pt", 0.1)],
    )
    source = FakeModelSource(primary)
    speech = FakeSpeechSource(FakeSpeechModel("hello there"))

    result = run_policy(
        source,
        AUDIO,
        prompt=None,
        language_hint=None,
        beam_size=5,
        honor_client_language=False,
        lang_confidence=0.5,
        speech=speech,
    )

    assert result.task == "transcribe"
    assert result.text == "hello there"
    assert result.detected_language == "es"
    assert result.model == "parakeet-ultra"
    assert primary.consumed == 0
    assert speech.requests == 1


def test_parakeet_error_falls_back_to_whisper(caplog):
    primary = FakeWhisperModel("en", "SHOULD NOT APPEAR", english_text="hello fallback")
    source = FakeModelSource(primary)
    speech = FakeSpeechSource(FakeSpeechModel(error=RuntimeError("boom")))

    result = run_policy(
        source,
        AUDIO,
        prompt=None,
        language_hint=None,
        beam_size=5,
        honor_client_language=False,
        speech=speech,
    )

    assert result.text == "hello fallback"
    assert result.task == "transcribe"
    assert result.model == "primary-model"
    assert result.detected_language == "en"
    assert primary.consumed == 1
    assert primary.calls[0]["language"] == "en"
    assert "parakeet failed" in caplog.text
    assert "boom" not in caplog.text, "the warning must not include arbitrary text"


def test_translation_uses_its_own_beam_size():
    primary = FakeWhisperModel("es", "transcripción original")
    translator = FakeWhisperModel("es", "the translated english text")
    source = FakeModelSource(primary, translator)

    result = run_policy(
        source,
        b"audio",
        prompt=None,
        language_hint=None,
        beam_size=5,
        translate_beam_size=2,
        honor_client_language=False,
    )

    assert result.task == "translate"
    assert primary.calls[0]["beam_size"] == 5  # the scan still uses beam_size
    assert translator.calls[0]["beam_size"] == 2


def test_without_timestamps_reaches_whisper_transcribe_and_translate():
    primary = FakeWhisperModel("en", "hello")
    source = FakeModelSource(primary)
    run_policy(
        source,
        b"audio",
        prompt=None,
        language_hint=None,
        beam_size=5,
        honor_client_language=False,
        without_timestamps=True,
    )
    assert source.requests == [False]
    assert primary.calls[0]["without_timestamps"] is True

    translate_primary = FakeWhisperModel("es", "texto original")
    translator = FakeWhisperModel("es", "hello")
    run_policy(
        FakeModelSource(translate_primary, translator),
        b"audio",
        prompt=None,
        language_hint=None,
        beam_size=5,
        honor_client_language=False,
        without_timestamps=True,
    )
    assert translator.calls[0]["without_timestamps"] is True


def test_without_timestamps_does_not_touch_parakeet():
    primary = FakeWhisperModel("en", "SHOULD NOT APPEAR")
    speech = FakeSpeechSource(FakeSpeechModel("hello from parakeet"))

    result = run_policy(
        FakeModelSource(primary),
        AUDIO,
        prompt=None,
        language_hint=None,
        beam_size=5,
        honor_client_language=False,
        speech=speech,
        without_timestamps=True,
    )

    assert result.text == "hello from parakeet"
    assert "without_timestamps" not in speech.model.calls[0]


def test_warmup_whisper_detects_and_decodes_silence():
    model = FakeWhisperModel("en", "")

    _warmup_whisper(model)

    assert model.detect_calls == [{"vad_filter": False}]
    assert len(model.calls) == 1
    assert model.calls[0]["beam_size"] == 1
    assert model.consumed == 1, "the lazy segment generator must be consumed"


def test_warmup_whisper_failure_is_logged_not_raised(caplog):
    class Broken(FakeWhisperModel):
        def detect_language(self, audio, **kwargs):
            raise RuntimeError("boom")

    _warmup_whisper(Broken("en", "text"))

    assert "whisper warm-up failed" in caplog.text
    assert "boom" not in caplog.text


def test_warmup_parakeet_runs_thirty_seconds_of_silence():
    speech = FakeSpeechModel()

    _warmup_parakeet(speech)

    call = speech.calls[0]
    assert call["timestamps"] == "none"
    assert call["sample_rate"] == 16000
    assert len(call["audio"]) == 16000 * 30


def test_parakeet_models_load_lazily_and_unload(monkeypatch):
    config = Config(english_engine="parakeet", device="cpu", model="fake-model")
    provider = ParakeetModels(config)
    assert provider.models_loaded is False
    assert provider.device == "cpu"

    class FakePhoton:
        def __init__(self) -> None:
            self.closed = False

        def close(self) -> None:
            self.closed = True

    photon = FakePhoton()
    monkeypatch.setattr(ParakeetModels, "_load", lambda self: photon)

    model, name = provider.get_model()
    assert model is photon
    assert name == "moondream/parakeet-ultra"
    assert provider.models_loaded is True
    assert provider.get_model()[0] is photon  # cached, one load

    assert provider.unload() is True
    assert photon.closed is True
    assert provider.models_loaded is False
    assert provider.unload() is False


class EnglishOnlyModel(FakeWhisperModel):
    """Mimics a *.en checkpoint: always reports English and cannot detect."""

    model = SimpleNamespace(is_multilingual=False)

    def __init__(self, text: str = "english only output") -> None:
        super().__init__("en", text)

    def detect_language(self, audio, **kwargs):
        raise RuntimeError("detect_language can only be called on multilingual models")


def test_english_only_main_model_still_translates_non_english():
    translator = FakeWhisperModel("es", "translated text")
    source = FakeModelSource(EnglishOnlyModel(), translator)
    result = run_policy(source, np.zeros(16000, dtype=np.float32), prompt=None, language_hint=None,
                        beam_size=5, honor_client_language=False)
    assert result.task == "translate" and result.text == "translated text"
    assert result.detected_language == "es"


def test_english_only_main_model_transcribes_english_itself():
    primary = EnglishOnlyModel()
    source = FakeModelSource(primary, FakeWhisperModel("en", "unused"))
    result = run_policy(source, np.zeros(16000, dtype=np.float32), prompt=None, language_hint=None,
                        beam_size=5, honor_client_language=False)
    assert result.task == "transcribe" and result.text == "english only output"


def test_english_only_main_model_with_parakeet_does_not_crash():
    speech = FakeSpeechSource(FakeSpeechModel())
    source = FakeModelSource(EnglishOnlyModel(), FakeWhisperModel("en", "unused"))
    result = run_policy(source, np.zeros(16000, dtype=np.float32), prompt=None, language_hint=None,
                        beam_size=5, honor_client_language=False, speech=speech)
    assert result.text == "hello from parakeet"


def test_swapped_engine_is_released_after_its_last_request():
    import threading

    from whisper_hub.engine import WhisperEngine

    class Models(FakeModelSource):
        unloaded = 0

        def unload(self):
            Models.unloaded += 1
            return True

    gate = threading.Event()
    inside = threading.Event()

    class SlowModel(FakeWhisperModel):
        def transcribe(self, audio, **kwargs):
            inside.set()
            gate.wait(5)
            return super().transcribe(audio, **kwargs)

    engine = WhisperEngine(Config(model="fake", preload=False), models=Models(SlowModel("en", "hi")))
    import io
    import wave

    buf = io.BytesIO()
    with wave.open(buf, "wb") as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(16000); wav.writeframes(b"\x01\x00" * 16000)
    worker = threading.Thread(target=engine.transcribe_bytes, args=(buf.getvalue(),))
    worker.start()
    assert inside.wait(5) and engine.busy
    engine.retire()
    assert Models.unloaded == 0  # still serving the in-flight request
    gate.set()
    worker.join(5)
    assert Models.unloaded == 1 and not engine.busy
