# US-304 — Audit Final de Branchement

Date : 2026-03-17
Périmètre : nouveaux éléments introduits en Sprint 1–3.

---

## Verdict

- Contrôles critiques non branchés : **0**
- Régressions sur suite existante : **0** (365/365 tests verts)

---

## Nouveaux éléments Sprint 1 (US-101/103/104)

| Élément | Rôle | Branchement |
|---------|------|-------------|
| QGroupBox "Consulter" | Conteneur layout — Vue, Kind, Goto | N/A (layout pur) |
| QGroupBox "Produire" | Conteneur layout — Segmenter, Normaliser, Exporter | N/A (layout pur) |
| QGroupBox "Avancé" | Conteneur layout — Profils | N/A (layout pur) |
| `pret_alignement_label` | Statut binaire épisode | BRANCHE_INDIRECT via `_update_action_buttons()` |
| `_update_action_buttons()` | Pilote enabled/tooltip + statut | Appelé dans `_load_episode()` (2 points de sortie) et `__init__` |

Réorganisation US-101 : aucun bouton existant supprimé ni rebranché — attributs inchangés (`inspect_norm_btn`, `inspect_segment_btn`, `inspect_export_segments_btn`, etc.).

## Nouveaux éléments Sprint 2 (US-205/301)

| Élément | Rôle | Branchement |
|---------|------|-------------|
| `cta_recommender.EpisodeState` | Dataclass d'état — pure data | N/A (pas de widget) |
| `cta_recommender.recommend()` | Moteur de décision matrice | Aucun widget — logique pure testée unitairement |

## Nouveaux éléments Sprint 3 (US-302)

| Élément | Rôle | Branchement |
|---------|------|-------------|
| `cta_label` | QLabel CTA lecture seule | BRANCHE_INDIRECT via `_update_action_buttons()` |
| `get_similarity_mode` | Callable optionnel entrant | BRANCHE_INDIRECT — consommé dans `_update_action_buttons()` |
| `db.get_align_runs_for_episode()` | Lecture DB pour `has_alignment_run` | Appelé dans `_update_action_buttons()` avec try/except |

---

## Couverture tests Sprint 1–3

| Fichier | Tests |
|---------|-------|
| `test_ui_inspecteur_sprint1.py` | 14 |
| `test_ui_inspecteur_sprint2.py` | 10 |
| `test_ui_inspecteur_sprint3.py` | 11 |
| `test_cta_recommender.py` | 13 |
| **Total nouveaux** | **48** |
| Suite globale | **365/365** |

---

## Duplication logique transverse Expert

Vérification Scénario B : aucune logique de `tab_expert.py` n'est dupliquée dans `tab_inspecteur.py`.

| Concept | Expert | Inspecteur |
|---------|--------|-----------|
| Cohérence inter-onglets | `context_consistent` (multi-tab) | — |
| Complétude inter-onglets | `context_complete` (multi-tab) | — |
| Prêt alignement épisode | — | `pret_alignement_label` (local épisode) |
| CTA opérationnel | — | `cta_label` (local épisode, matrice US-301) |

Conclusion : **pas de duplication**, frontière claire entre vue transverse (Expert) et vue locale (Inspecteur).

---

## Verdict final

**Sprint 3 clos. DoD satisfait :**
- CTA en production conforme à US-301.
- 0 contrôle critique non branché.
- 0 duplication logique transverse.
- 365/365 tests verts.
