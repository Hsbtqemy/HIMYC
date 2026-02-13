"""Onglets de la fenêtre principale (Logs, Concordance, Sous-titres, Alignement, Inspecteur, Personnages)."""

from howimetyourcorpus.app.tabs.tab_alignement import AlignmentTabWidget
from howimetyourcorpus.app.tabs.tab_concordance import ConcordanceTabWidget
from howimetyourcorpus.app.tabs.tab_corpus import CorpusTabWidget
from howimetyourcorpus.app.tabs.tab_inspecteur import InspectorTabWidget
from howimetyourcorpus.app.tabs.tab_logs import LogsTabWidget
from howimetyourcorpus.app.tabs.tab_personnages import PersonnagesTabWidget
from howimetyourcorpus.app.tabs.tab_projet import ProjectTabWidget
from howimetyourcorpus.app.tabs.tab_sous_titres import SubtitleTabWidget

__all__ = [
    "AlignmentTabWidget",
    "ConcordanceTabWidget",
    "CorpusTabWidget",
    "InspectorTabWidget",
    "LogsTabWidget",
    "PersonnagesTabWidget",
    "ProjectTabWidget",
    "SubtitleTabWidget",
]
