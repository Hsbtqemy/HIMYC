"""Tests des profils de normalisation."""

import pytest
from howimetyourcorpus.core.normalize.profiles import (
    NormalizationProfile,
    PROFILES,
    get_profile,
    resolve_lang_hint_from_profile_id,
)


@pytest.fixture
def profile():
    return NormalizationProfile(id="test")


def test_normalize_merge_mid_phrase(profile: NormalizationProfile):
    """Césure au milieu d'une phrase : fusionnée en une ligne."""
    raw = "This is a long line that\nbreaks in the middle."
    clean, stats, debug = profile.apply(raw)
    assert "that" in clean and "breaks" in clean
    # Les deux parties sont sur la même ligne logique (fusion)
    lines = [l for l in clean.splitlines() if l.strip()]
    assert len(lines) == 1
    assert stats.merges >= 1


def test_normalize_double_break_kept(profile: NormalizationProfile):
    """Double saut de ligne conservé."""
    raw = "First paragraph.\n\nSecond paragraph."
    clean, stats, debug = profile.apply(raw)
    assert "First paragraph" in clean
    assert "Second paragraph" in clean
    # Il doit y avoir une ligne vide entre les deux
    parts = clean.split("\n\n")
    assert len(parts) >= 2


def test_normalize_didascalia_kept(profile: NormalizationProfile):
    """Didascalie (parenthèses) conservée comme coupure."""
    raw = "Ted: Hello.\n(smiling)\nMarshall: Hi."
    clean, stats, debug = profile.apply(raw)
    assert "(smiling)" in clean or "smiling" in clean
    assert "Ted:" in clean
    assert "Marshall:" in clean
    # Les répliques ne doivent pas être fusionnées avec la didascalie
    lines = [l.strip() for l in clean.splitlines() if l.strip()]
    assert len(lines) >= 2


def test_normalize_speaker_line_kept(profile: NormalizationProfile):
    """Ligne type TED: conservée (pattern speaker-like)."""
    raw = "TED: I have something to say.\nMARSHALL: What?"
    clean, stats, debug = profile.apply(raw)
    assert "TED:" in clean
    assert "MARSHALL:" in clean
    assert "I have something" in clean
    assert "What?" in clean
    # Deux blocs distincts
    lines = [l for l in clean.splitlines() if l.strip()]
    assert len(lines) >= 2


def test_profile_empty_string(profile: NormalizationProfile):
    raw = ""
    clean, stats, debug = profile.apply(raw)
    assert clean == ""
    assert stats.raw_lines == 0


def test_get_profile():
    assert get_profile("default_en_v1") is not None
    assert get_profile("nonexistent") is None
    assert "default_en_v1" in PROFILES


def test_resolve_lang_hint_from_profile_id_default_profile() -> None:
    assert resolve_lang_hint_from_profile_id("default_fr_v2") == "fr"


def test_resolve_lang_hint_from_profile_id_custom_prefix() -> None:
    assert resolve_lang_hint_from_profile_id("it_dialogue_v1") == "it"


def test_resolve_lang_hint_from_profile_id_falls_back_on_non_lang_prefix() -> None:
    assert resolve_lang_hint_from_profile_id("aggressive_v1", fallback="en") == "en"


def test_resolve_lang_hint_from_profile_id_supports_locale_tokens() -> None:
    assert resolve_lang_hint_from_profile_id("default_en-us_v1", fallback="fr") == "en"
