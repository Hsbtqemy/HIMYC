"""Tests des helpers de feedback UI (formatage)."""

from howimetyourcorpus.app.feedback import format_error, format_precondition, show_info


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


def test_show_info_uses_status_callback_without_popup(monkeypatch) -> None:
    popup_calls: list[tuple[object, str, str]] = []
    status_calls: list[tuple[str, int]] = []

    def _fake_popup(parent, title: str, message: str) -> None:
        popup_calls.append((parent, title, message))

    monkeypatch.setattr("howimetyourcorpus.app.feedback.QMessageBox.information", _fake_popup)

    show_info(
        None,
        "Export",
        "Terminé",
        status_callback=lambda msg, timeout: status_calls.append((msg, timeout)),
    )

    assert status_calls == [("Export: Terminé", 4000)]
    assert popup_calls == []


def test_show_info_falls_back_to_popup_when_no_status_available(monkeypatch) -> None:
    popup_calls: list[tuple[object, str, str]] = []

    def _fake_popup(parent, title: str, message: str) -> None:
        popup_calls.append((parent, title, message))

    monkeypatch.setattr("howimetyourcorpus.app.feedback.QMessageBox.information", _fake_popup)

    show_info(None, "Export", "Terminé")

    assert popup_calls == [(None, "Export", "Terminé")]
