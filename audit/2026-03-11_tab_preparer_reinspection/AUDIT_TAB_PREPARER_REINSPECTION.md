# Audit ciblé onglet Préparer (réinspection)

Date: 2026-03-11
Périmètre: `src/howimetyourcorpus/app/tabs/tab_preparer.py`, `preparer_ui.py`, `preparer_actions.py`, `preparer_edit.py`, `preparer_context.py`, `core/preparer/segmentation.py`
Contrainte respectée: aucune modification applicative.

## Méthode et mesures

1. Capture de branchement UI -> handlers -> logique métier.
2. Exécution de tests ciblés Préparer/segmentation/navigation.
3. Vérification spécifique de la logique `segment_kind` (`sentence` vs `utterance`) et du regroupement par assignations.
4. Vérification ciblée du bouton `Renuméroter` via probe exécutable.

Mesures:
- `python -m pytest -q tests/test_preparer_actions.py tests/test_preparer_segmentation.py tests/test_ui_preparer_navigation.py`
  - Résultat: **71 passed** (`evidence/pytest_preparer_focus.log`)
- `python -m pytest -q -vv tests/test_preparer_actions.py -k "normalize_transcript or search_replace or open_segmentation_options or go_to_alignement_transcript_uses_utterance_or_sentence or infer_segment_kind_non_transcript_reads_db_utterances"`
  - Résultat: **20 passed** (`evidence/pytest_preparer_actions_vv.log`)
- `python -m pytest -q -vv tests/test_ui_preparer_navigation.py -k "go_to_alignement_uses_utterance_when_transcript_rows_present or go_to_alignement_prefers_existing_utterances_from_srt_source or segment_uses_saved_segmentation_options or merge_selected_utterances_with_user_separator or split_selected_utterance_uses_cursor_position or group_utterances_by_assignments_tolerant_mode or group_utterances_uses_segment_assignments_when_labels_do_not_match or save_transcript_structural_edits_replace_segments or reset_utterances_to_text_and_save_clears_segments"`
  - Résultat: **9 passed** (`evidence/pytest_preparer_buttons_vv.log`)
- `python -m pytest -q -vv tests/test_preparer_segmentation.py`
  - Résultat: **5 passed** (`evidence/pytest_preparer_segmentation_vv.log`)

## Cartographie des contrôles et état fonctionnel réel

Source de branchement UI: `evidence/button_wiring_preparer_ui.txt`
Source handlers widget: `evidence/button_handlers_tab_preparer.txt`

### Ligne actions principale

1. `Nettoyer`
- Branché: oui (`preparer_ui.py:58-60`)
- Handler: `_normalize_transcript` -> `PreparerActionsController.normalize_transcript`
- Statut fonctionnel: **OK** (garde épisode/source transcript, appel service, persistance meta)
- Preuves: `evidence/pytest_preparer_actions_vv.log`, tests `test_normalize_transcript_*`

2. `Rechercher / Remplacer`
- Branché: oui (`preparer_ui.py:62-64`)
- Handler: `_search_replace` -> `PreparerActionsController.search_replace`
- Statut fonctionnel: **OK** (branches texte/table utterance/table cue + gestion regex)
- Preuves: `evidence/pytest_preparer_actions_vv.log`, tests `test_search_replace_*`

3. `Segmenter en tours`
- Branché: oui (`preparer_ui.py:66-68`)
- Handler: `_segment_to_utterances` -> `PreparerEditController.segment_to_utterances`
- Statut fonctionnel: **OK** (garde épisode/source transcript, confirmation écrasement, options sauvegardées)
- Preuves: `evidence/preparer_edit_segment_excerpt.txt`, `evidence/pytest_preparer_buttons_vv.log`

4. `Paramètres segmentation`
- Branché: oui (`preparer_ui.py:70-72`)
- Handler: `_open_segmentation_options` -> `PreparerActionsController.open_segmentation_options`
- Statut fonctionnel: **OK** (disponible transcript, options normalisées et persistées)
- Preuves: `evidence/pytest_preparer_actions_vv.log`

5. `Éditer timecodes` (checkbox)
- Branché: oui (`preparer_ui.py:74-80`)
- Activation réelle: uniquement sur source SRT (`preparer_context.py:197-201`)
- Statut fonctionnel: **OK** (active édition Début/Fin, piloté par `_on_edit_timecodes_toggled`)
- Preuves: `evidence/context_enablement_capture.txt`, `evidence/pytest_preparer_focus.log`

6. `Validation stricte` (checkbox)
- Branché: oui (`preparer_ui.py:82-87`)
- Activation réelle: dépend de `Éditer timecodes` (`tab_preparer.py:311-313`)
- Statut fonctionnel: **OK** (rejette chevauchements si strict=true à la sauvegarde)
- Preuves: `evidence/preparer_save_timecode_validation_excerpt.txt`, tests `test_preparer_srt_timecode_strict_rejects_overlap` / `test_preparer_srt_timecode_overlap_allowed_when_strict_disabled` (voir `evidence/tests_preparer_navigation_index.txt`)

7. `Enregistrer`
- Branché: oui (`preparer_ui.py:89-91`)
- Handler: `save_current` -> persistance transcript ou cues selon source
- Statut fonctionnel: **OK**
- Preuves: `evidence/preparer_persistence_save_excerpt.txt`, `evidence/pytest_preparer_focus.log`

8. `Aller à l'alignement`
- Branché: oui (`preparer_ui.py:93-95`)
- Handler: `_go_to_alignement` -> `go_to_alignement` + inférence `segment_kind`
- Statut fonctionnel: **OK**
- Preuves: `evidence/preparer_actions_handoff_excerpt.txt`, `evidence/pytest_preparer_buttons_vv.log`

### Ligne actions tours (utterances)

9. `Ajouter ligne`
- Branché: oui (`preparer_ui.py:102-104`)
- Statut fonctionnel: **OK**
- Preuves: `evidence/button_logic_preparer_edit.txt`, test `test_preparer_save_transcript_structural_edits_replace_segments` (`evidence/tests_traceability_capture.txt`)

10. `Supprimer ligne`
- Branché: oui (`preparer_ui.py:106-108`)
- Statut fonctionnel: **OK**
- Preuves: `evidence/button_logic_preparer_edit.txt`, tests `test_preparer_save_transcript_structural_edits_replace_segments` et `test_preparer_save_transcript_can_persist_zero_utterance_rows`

11. `Fusionner`
- Branché: oui (`preparer_ui.py:110-112`)
- Statut fonctionnel: **OK** (nécessite sélection consécutive, séparateur choisi)
- Preuves: test `test_preparer_merge_selected_utterances_with_user_separator` (`evidence/pytest_preparer_buttons_vv.log`)

12. `Scinder au curseur`
- Branché: oui (`preparer_ui.py:114-116`)
- Statut fonctionnel: **OK** (curseur exigé en cellule texte, scission en 2 lignes)
- Preuves: test `test_preparer_split_selected_utterance_uses_cursor_position` (`evidence/pytest_preparer_buttons_vv.log`)

13. `Regrouper par assignations`
- Branché: oui (`preparer_ui.py:118-120`)
- Statut fonctionnel: **OK** (utilise assignations segment si disponibles, sinon labels speaker; mode tolérant activé)
- Preuves: `evidence/preparer_edit_group_excerpt.txt`, `evidence/segmentation_excerpt.txt`, tests `test_preparer_group_utterances_by_assignments_tolerant_mode` et `test_preparer_group_utterances_uses_segment_assignments_when_labels_do_not_match`

14. `Renuméroter`
- Branché UI: oui (`preparer_ui.py:122-124`)
- Handler appelé: oui (`tab_preparer.py:401-402`)
- Effet réel: **NON CONCLUANT / effet nul détecté**
- Analyse: `_apply_utterance_rows_with_undo` compare `normalized_before` et `normalized_after`; or `_normalize_utterance_rows` réécrit déjà `n=idx` dans les deux cas, ce qui peut annuler toute différence de renumérotation pure.
- Preuves code: `evidence/renumber_noop_code_capture.txt`
- Preuve exécutable: `evidence/renumber_probe.json` (valeurs `n` inchangées après appel)
- Conclusion: **élément présent mais pas réellement opérationnel pour son objectif de renumérotation**.

15. `Revenir au texte`
- Branché: oui (`preparer_ui.py:126-128`)
- Statut fonctionnel: **OK** (supprime tours, bascule éditeur texte, sauvegarde vide possible)
- Preuves: test `test_preparer_reset_utterances_to_text_and_save_clears_segments` (`evidence/pytest_preparer_buttons_vv.log`)

## Logique segmentation: "ligne" vs "utterance"

Constat code:
- L’onglet Préparer segmente vers des **tours** via `segment_text_to_utterance_rows(...)` (`core/preparer/segmentation.py`).
- Au handoff vers Alignement:
  - source transcript + au moins 1 tour en table -> `segment_kind="utterance"`
  - sinon -> `segment_kind="sentence"`
  - source non transcript: fallback DB sur segments `kind="utterance"`, sinon `sentence`
  - preuves: `evidence/preparer_actions_handoff_excerpt.txt`
- Côté Alignement, le sélecteur expose explicitement: `Phrases` (`sentence`) et `Tours` (`utterance`) (`evidence/align_segment_kind_combo_capture.txt`).

Interprétation fonctionnelle:
- Dans ce code, il n’existe pas de type persistant "line" distinct de `utterance` pour l’alignement.
- "Ligne" dans Préparer correspond pratiquement à une ligne de table de tours (`utterance row`), tandis que l’alignement consomme `sentence` ou `utterance`.

## Logique du bouton "Regrouper par assignations"

Algorithme (`core/preparer/segmentation.py`, `evidence/segmentation_excerpt.txt`):
1. Pour chaque ligne consécutive, priorité à l’assignation segment (`assignment_by_segment_id`).
2. Sinon fallback sur `speaker_explicit` via `character_lookup`.
3. Si speaker non mappé mais présent, clé synthétique `speaker:<label>` pour éviter un collapse global.
4. Fusion seulement entre lignes consécutives portant le même identifiant courant.
5. Si `tolerant=True` et ligne non marquée après un personnage actif, fusion dans le bloc courant.
6. Renumérotation finale des lignes groupées (`n`) + reset `segment_id`.

Validation par tests:
- `test_regroup_prefers_assignments_when_present`
- `test_regroup_tolerant_merges_unmarked_rows_after_character`
- `test_preparer_group_utterances_by_assignments_tolerant_mode`
- `test_preparer_group_utterances_uses_segment_assignments_when_labels_do_not_match`

## Synthèse exécutive

- **Globalement**, les contrôles de l’onglet Préparer sont branchés et fonctionnels selon tests ciblés (71/71 sur le lot exécuté).
- **Point d’écart identifié**: `Renuméroter` est visible/branché mais son effet métier est neutralisé dans le flux actuel (présent != réellement opérationnel).

Priorisation:
- **P0 corriger**: aucun blocage critique global détecté sur les parcours testés.
- **P1 compléter/corriger**: corriger `Renuméroter` pour qu’une renumérotation pure produise un changement effectif.
- **P2 polish**: ajouter un test UI dédié `Renuméroter` pour éviter régression silencieuse.
