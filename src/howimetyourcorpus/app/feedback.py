"""Helpers UI pour messages de prérequis et erreurs."""

from __future__ import annotations

from typing import Any

from PySide6.QtWidgets import QMessageBox, QWidget


def format_precondition(problem: str, next_step: str | None = None) -> str:
    """Formate un message de prérequis avec une prochaine étape explicite."""
    if next_step:
        return f"{problem}\n\nProchaine étape: {next_step}"
    return problem


def warn_precondition(
    parent: QWidget,
    title: str,
    problem: str,
    *,
    next_step: str | None = None,
) -> None:
    """Affiche un warning homogène pour les prérequis manquants."""
    QMessageBox.warning(parent, title, format_precondition(problem, next_step))


def format_error(exc: Any, *, context: str | None = None, max_len: int = 500) -> str:
    """Convertit une exception en message UI court et stable."""
    try:
        base = str(exc) if exc is not None else "Erreur inconnue"
    except Exception:
        base = "Erreur inconnue"
    if context:
        base = f"{context}: {base}"
    if len(base) > max_len:
        return base[: max_len - 3] + "..."
    return base


def show_error(
    parent: QWidget,
    *,
    title: str = "Erreur",
    exc: Any = None,
    context: str | None = None,
    max_len: int = 500,
) -> None:
    """Affiche une erreur critique avec formatage homogène."""
    QMessageBox.critical(parent, title, format_error(exc, context=context, max_len=max_len))
