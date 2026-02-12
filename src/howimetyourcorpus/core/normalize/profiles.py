"""Profils de normalisation : apply(raw) -> (clean, stats, debug)."""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field

from howimetyourcorpus.core.models import TransformStats
from howimetyourcorpus.core.normalize.rules import MAX_MERGE_EXAMPLES, should_merge


@dataclass
class NormalizationProfile:
    """
    Profil de normalisation = ensemble de règles paramétrables.
    Règles MVP :
    - Fusionner retours à la ligne au milieu d'une phrase (césure sous-titres).
    - Conserver : double saut, didascalies (), [], lignes speaker-like.
    - Ne jamais inventer de locuteur.
    """

    id: str
    merge_subtitle_breaks: bool = True
    max_merge_examples_in_debug: int = MAX_MERGE_EXAMPLES

    def apply(self, raw_text: str) -> tuple[str, TransformStats, dict]:
        """
        Applique la normalisation.
        Returns:
            (clean_text, stats, debug) avec debug contenant merge_examples.
        """
        t0 = time.perf_counter()
        raw_lines = [ln for ln in raw_text.splitlines()]
        stats = TransformStats(raw_lines=len(raw_lines))
        debug: dict = {"merge_examples": []}
        if not raw_lines:
            return "", stats, debug

        output: list[str] = []
        merges = 0
        kept_breaks = 0
        i = 0
        while i < len(raw_lines):
            line = raw_lines[i]
            # Ligne vide : séparation forte
            if not line.strip():
                output.append("")
                kept_breaks += 1
                i += 1
                continue
            # Accumuler les lignes à fusionner (césure)
            acc = [line]
            i += 1
            while i < len(raw_lines) and self.merge_subtitle_breaks and should_merge(
                acc[-1], raw_lines[i]
            ):
                next_ln = raw_lines[i]
                if len(debug["merge_examples"]) < self.max_merge_examples_in_debug:
                    debug["merge_examples"].append(
                        {"before": acc[-1][-40:], "after": next_ln[:40] if len(next_ln) > 40 else next_ln}
                    )
                acc.append(next_ln)
                merges += 1
                i += 1
            merged = " ".join(s.strip() for s in acc if s.strip())
            if merged:
                output.append(merged)
                if len(acc) > 1:
                    kept_breaks += 1  # on compte un bloc logique
        clean_text = "\n".join(output)
        stats.clean_lines = len([x for x in output if x.strip()])
        stats.merges = merges
        stats.kept_breaks = kept_breaks
        stats.duration_ms = int((time.perf_counter() - t0) * 1000)
        return clean_text, stats, debug


# Profils prédéfinis
PROFILES: dict[str, NormalizationProfile] = {
    "default_en_v1": NormalizationProfile(id="default_en_v1"),
    "conservative_v1": NormalizationProfile(
        id="conservative_v1",
        merge_subtitle_breaks=True,
        max_merge_examples_in_debug=10,
    ),
    "aggressive_v1": NormalizationProfile(
        id="aggressive_v1",
        merge_subtitle_breaks=True,
        max_merge_examples_in_debug=30,
    ),
}


def get_profile(profile_id: str) -> NormalizationProfile | None:
    return PROFILES.get(profile_id)
