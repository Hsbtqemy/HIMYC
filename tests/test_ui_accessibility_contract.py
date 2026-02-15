"""Contrats d'accessibilité UI (navigation clavier/focus/raccourcis)."""

from __future__ import annotations

import inspect
from pathlib import Path

from howimetyourcorpus.app.tabs.tab_alignement import AlignmentTabWidget
from howimetyourcorpus.app.tabs.tab_concordance import ConcordanceTabWidget
from howimetyourcorpus.app.tabs.tab_corpus import CorpusTabWidget
from howimetyourcorpus.app.tabs.tab_logs import LogsTabWidget
from howimetyourcorpus.app.tabs.tab_personnages import PersonnagesTabWidget
from howimetyourcorpus.app.tabs.tab_pilotage import PilotageTabWidget
from howimetyourcorpus.app.tabs.tab_projet import ProjectTabWidget
from howimetyourcorpus.app.tabs.tab_validation_annotation import ValidationAnnotationTabWidget


def test_mainwindow_declares_global_accessibility_shortcuts() -> None:
    source = Path("src/howimetyourcorpus/app/ui_mainwindow.py").read_text(encoding="utf-8")
    assert "Ctrl+L" in source
    assert "Meta+L" in source
    assert "Ctrl+F" in source
    assert "Meta+F" in source
    assert "QKeySequence.StandardKey.Find" in source


def test_focus_contract_methods_exist_on_key_widgets() -> None:
    # Pilotage (Projet + Corpus)
    assert hasattr(ProjectTabWidget, "first_focus_widget")
    assert hasattr(ProjectTabWidget, "last_focus_widget")
    assert hasattr(CorpusTabWidget, "first_focus_widget")
    assert hasattr(CorpusTabWidget, "last_focus_widget")
    assert hasattr(PilotageTabWidget, "focus_corpus")
    # Validation / Annotation
    assert hasattr(AlignmentTabWidget, "first_focus_widget")
    assert hasattr(AlignmentTabWidget, "last_focus_widget")
    assert hasattr(PersonnagesTabWidget, "first_focus_widget")
    assert hasattr(PersonnagesTabWidget, "last_focus_widget")
    assert hasattr(ValidationAnnotationTabWidget, "focus_alignment")
    # Recherche
    assert hasattr(ConcordanceTabWidget, "focus_search")
    assert hasattr(LogsTabWidget, "focus_search")


def test_tab_order_configuration_methods_call_set_tab_order() -> None:
    widgets = [
        ProjectTabWidget,
        CorpusTabWidget,
        PilotageTabWidget,
        AlignmentTabWidget,
        PersonnagesTabWidget,
        ValidationAnnotationTabWidget,
    ]
    for widget_cls in widgets:
        method = getattr(widget_cls, "_configure_tab_order")
        source = inspect.getsource(method)
        assert "setTabOrder" in source
