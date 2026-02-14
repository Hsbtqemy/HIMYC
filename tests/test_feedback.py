"""Tests des helpers de feedback UI (formatage)."""

from howimetyourcorpus.app.feedback import format_error, format_precondition


def test_format_precondition_with_next_step() -> None:
    msg = format_precondition("Précondition manquante.", "Faites l'étape suivante.")
    assert "Précondition manquante." in msg
    assert "Prochaine étape:" in msg
    assert "Faites l'étape suivante." in msg


def test_format_precondition_without_next_step() -> None:
    assert format_precondition("Précondition manquante.") == "Précondition manquante."


def test_format_error_truncates_long_messages() -> None:
    msg = format_error("x" * 600, context="Export", max_len=100)
    assert msg.startswith("Export: ")
    assert len(msg) == 100
    assert msg.endswith("...")


def test_format_error_handles_bad_exception_str() -> None:
    class BrokenExc:
        def __str__(self) -> str:
            raise RuntimeError("boom")

    assert format_error(BrokenExc()) == "Erreur inconnue"
