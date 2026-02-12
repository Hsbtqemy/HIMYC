"""Alignement transcript ↔ cues (Phase 4)."""

from howimetyourcorpus.core.align.similarity import text_similarity
from howimetyourcorpus.core.align.aligner import (
    AlignLink,
    align_segments_to_cues,
    align_cues_by_time,
)

__all__ = [
    "text_similarity",
    "AlignLink",
    "align_segments_to_cues",
    "align_cues_by_time",
]
