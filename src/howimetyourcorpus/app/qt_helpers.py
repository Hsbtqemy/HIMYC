"""Helpers Qt partagés (UI)."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from PySide6.QtWidgets import QComboBox


def refill_combo_preserve_selection(
    combo: QComboBox,
    *,
    items: Sequence[tuple[str, Any]],
    current_data: Any = None,
) -> Any:
    """Recharge un combo en conservant la sélection courante si possible.

    Retourne la donnée actuellement sélectionnée après rechargement.
    """
    target_data = combo.currentData() if current_data is None else current_data
    combo.blockSignals(True)
    combo.clear()
    target_index = -1
    for idx, (label, data) in enumerate(items):
        combo.addItem(label, data)
        if target_data is not None and data == target_data and target_index < 0:
            target_index = idx
    if target_index >= 0:
        combo.setCurrentIndex(target_index)
    combo.blockSignals(False)
    return combo.currentData()
