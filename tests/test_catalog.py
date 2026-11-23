from __future__ import annotations

import pytest

from whisper_hub import catalog


def test_catalog_covers_the_expected_models():
    ids = {model.id for model in catalog.MODELS}
    assert {"tiny", "base", "small", "medium", "large-v3", "large-v3-turbo"} <= ids
    assert any(model.id.startswith("distil") for model in catalog.MODELS)
    for model in catalog.MODELS:
        assert model.download_mb > 0
        assert model.ram_mb > 0
        assert 1 <= model.speed <= 10
        assert 1 <= model.quality <= 5


@pytest.mark.parametrize("name", ["large-v3-turbo", "distil-large-v3", "distil-medium.en"])
def test_translation_incapable_models_are_known(name):
    assert catalog.is_translatable(name) is False


@pytest.mark.parametrize("name", ["tiny", "base", "small", "medium", "large-v3", "custom/model"])
def test_translation_capable_models(name):
    assert catalog.is_translatable(name) is True


def test_translation_model_validation():
    with pytest.raises(ValueError):
        catalog.validate_models("large-v3-turbo", "")
    with pytest.raises(ValueError):
        catalog.validate_models("large-v3-turbo", "large-v3-turbo")
    with pytest.raises(ValueError):
        catalog.validate_models("small", "distil-large-v3")
    catalog.validate_models("large-v3-turbo", "large-v3")
    catalog.validate_models("small", "")
    with pytest.raises(ValueError):
        catalog.validate_models("", "")


def test_recommendation_is_generic_and_hardware_aware():
    assert catalog.recommend(None, 16, 4) == "base"
    assert catalog.recommend(None, 16, 16) == "small"
    assert catalog.recommend(4, 16, 8) == "small"
    assert catalog.recommend(8, 32, 8) == "medium"
    assert catalog.recommend(24, 64, 16) == "medium"
    assert catalog.recommend_translation("small", None) == ""
    assert catalog.recommend_translation("large-v3-turbo", 8) == "medium"
    assert catalog.recommend_translation("large-v3-turbo", 24) == "large-v3"
