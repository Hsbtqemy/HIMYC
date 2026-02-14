"""Décision de prochaine action workflow pour le Pilotage."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkflowStatusCounts:
    n_total: int
    n_fetched: int
    n_norm: int
    n_segmented: int
    n_indexed: int
    n_error: int
    n_with_srt: int
    n_aligned: int


@dataclass(frozen=True)
class WorkflowAdvice:
    action_id: str
    label: str
    message: str


def build_workflow_advice(counts: WorkflowStatusCounts) -> WorkflowAdvice:
    """Retourne la prochaine action recommandée selon l'état agrégé du corpus."""
    if counts.n_error > 0:
        return WorkflowAdvice(
            action_id="retry_errors",
            label="Relancer toutes les erreurs",
            message=(
                "Prochaine action: relancer les épisodes en erreur avec "
                "« Relancer toutes les erreurs » (ou ciblé via « Relancer épisode »)."
            ),
        )
    if (
        counts.n_with_srt > 0
        and counts.n_fetched == 0
        and counts.n_norm == 0
        and counts.n_segmented == 0
        and counts.n_indexed == 0
    ):
        return WorkflowAdvice(
            action_id="open_concordance_cues",
            label="Ouvrir Concordance (Cues)",
            message=(
                "Mode SRT-first détecté: vous pouvez déjà explorer les sous-titres dans Concordance "
                "(scope « Cues »). Pour l'alignement segment↔cues, ajoutez ensuite les transcripts "
                "(Télécharger → Normaliser → Segmenter)."
            ),
        )
    if counts.n_fetched < counts.n_total:
        return WorkflowAdvice(
            action_id="fetch_all",
            label="Télécharger tout",
            message=(
                "Prochaine action: importer les transcripts manquants avec « Télécharger » "
                "(scope « Tout le corpus »)."
            ),
        )
    if counts.n_norm < counts.n_fetched:
        return WorkflowAdvice(
            action_id="normalize_all",
            label="Normaliser tout",
            message=(
                "Prochaine action: normaliser les épisodes FETCHED avec « Normaliser » "
                "(scope « Tout le corpus »)."
            ),
        )
    if counts.n_segmented < counts.n_norm:
        return WorkflowAdvice(
            action_id="segment_and_index",
            label="Segmenter + Indexer",
            message=(
                "Prochaine action: segmenter et indexer les épisodes NORMALIZED "
                "(boutons Segmenter / Indexer DB)."
            ),
        )
    if counts.n_indexed < counts.n_segmented:
        return WorkflowAdvice(
            action_id="index_all",
            label="Indexer tout",
            message=(
                "Prochaine action: indexer les épisodes déjà segmentés avec « Indexer DB » "
                "(scope « Tout le corpus »)."
            ),
        )
    if counts.n_with_srt == 0:
        return WorkflowAdvice(
            action_id="open_inspector_srt",
            label="Ouvrir Inspecteur (SRT)",
            message=(
                "Prochaine action: importer des sous-titres (SRT/VTT) dans l'Inspecteur "
                "pour préparer l'alignement."
            ),
        )
    if counts.n_aligned < counts.n_with_srt:
        return WorkflowAdvice(
            action_id="open_validation_alignment",
            label="Aller à Validation",
            message=(
                "Prochaine action: lancer l'alignement des épisodes avec SRT dans Validation & "
                "Annotation, puis vérifier les personnages."
            ),
        )
    return WorkflowAdvice(
        action_id="done",
        label="Corpus prêt",
        message="Corpus prêt: passez à Validation & Annotation puis Concordance pour l'analyse.",
    )
