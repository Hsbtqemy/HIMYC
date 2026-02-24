# Plan d'implémentation : Onglet « Préparer un fichier » (version exécutable)

**Référence** : [DOC_SCENARIO_PREP_ET_PERSONNAGES.md](DOC_SCENARIO_PREP_ET_PERSONNAGES.md)  
**Date** : 2026-02-23  
**Statut** : implémentation terminée (P0 + Phase 1 + Phase 2 + Phase 3.1/3.3 + refacto P3 du widget)

### État d'avancement (mise à jour 2026-02-24)

- ✅ P0 (APIs DB + navigation onglets + contrat save clean + tests socle)
- ✅ Phase 1 (MVP transcript complet)
- ✅ Phase 2 (mode SRT EN/FR/IT + sauvegarde cues + réécriture piste)
- ✅ Phase 3.1 (statut par fichier `episode_prep_status.json`)
- ✅ Phase 3.3 (édition timecodes + validation stricte optionnelle)
- ✅ Refacto technique P3 (`tab_preparer.py` décomposé en contrôleurs/sous-vues)
- ➖ Phase 3.2 non implémentée (optionnelle, hors périmètre validé: statut par ligne)

---

## Objectif

Créer un onglet « Préparer » entre Inspecteur et Alignement pour travailler sur un seul fichier d'un épisode (transcript ou piste SRT), avec:

- normalisation explicite
- recherche/remplacement
- segmentation en tours et édition personnage/texte
- affichage timecodes côté SRT
- sauvegarde traçable avant alignement

---

## Contraintes techniques observées

1. `ProjectStore.save_episode_clean` exige la signature complète:
   `save_episode_clean(episode_id, clean_text, stats, debug)`.
2. `db_segments` ne fournissait pas initialement `update_segment_text` (désormais ajouté + exposé dans `db.py`).
3. `db_subtitles` ne fournissait pas initialement `update_cue_timecodes` (désormais ajouté + exposé dans `db.py`).
4. Les index d'onglets sont gérés par constantes `TAB_*` dans `ui_mainwindow.py`.  
   Un `insertTab` sans refactor complet crée vite des décalages de navigation.
5. Le pipeline d'alignement accepte déjà `segment_kind` (`sentence`/`utterance`) et peut donc être branché directement.

---

## Principes d'implémentation (à respecter)

1. **Pas de perte silencieuse de données**:
   tout changement non sauvegardé doit déclencher un prompt à la navigation.
2. **Écriture atomique**:
   les mises à jour multi-tables doivent être transactionnelles.
3. **Une seule logique métier**:
   l'UI appelle un service `core/preparer/` plutôt que du SQL dispersé.
4. **Undo/Redo par défaut**:
   toutes les actions éditoriales significatives doivent être annulables.
5. **Handoff explicite vers Alignement**:
   navigation + épisode + `segment_kind` transférés explicitement.

---

## Phase 0 (P0) : prérequis techniques obligatoires

### P0.1 API de persistance minimales

- **Ajouter** dans `core/storage/db_segments.py`:
  `update_segment_text(conn, segment_id, text)`.
- **Exposer** dans `core/storage/db.py`:
  `update_segment_text(segment_id, text)`.
- **Ajouter** dans `core/storage/db_subtitles.py`:
  `update_cue_timecodes(conn, cue_id, start_ms, end_ms)`.
- **Exposer** dans `core/storage/db.py`:
  `update_cue_timecodes(cue_id, start_ms, end_ms)`.
- **Ajouter** dans `core/storage/db.py` un helper transactionnel réutilisable pour le module Préparer
  (ou réutiliser `with db.connection() as conn:` de manière systématique).

### P0.2 Stratégie d'onglets robuste

- **Modifier** `ui_mainwindow.py` en un seul lot:
  recalcul complet des `TAB_*` après insertion de `TAB_PREPARER`.
- **Éviter** les index magiques hors constantes.
- **Ajouter** un helper central:
  `open_preparer_for_episode(episode_id, source=None)` pour navigation croisée.
- **Ajouter** le chemin inverse:
  `open_alignement_for_episode(episode_id, segment_kind="sentence")`.

### P0.3 Contrat de sauvegarde transcript

- **Ajouter** dans `tab_preparer.py` un helper local:
  `save_clean_text_with_meta(episode_id, clean_text)` qui construit `TransformStats` minimal + `debug`.
- **Ne pas** appeler `save_episode_clean` avec une signature incomplète.

### P0.4 Tests socle

- `tests/test_db_segments.py`:
  couverture `update_segment_text`.
- `tests/test_subtitles.py` ou nouveau test dédié:
  couverture `update_cue_timecodes`.
- test UI léger de non-régression navigation onglets (ou test logique sur constantes/helpers).
- **Ajouter tests Qt minimaux**:
  - passage Inspecteur -> Préparer -> Alignement sans décalage d'index;
  - propagation de l'épisode courant;
  - propagation `segment_kind` demandé.

### P0.5 Service métier Préparer (recommandé)

- **Créer** `src/howimetyourcorpus/core/preparer/service.py` avec API:
  - `load_source(episode_id, source_key)`
  - `apply_normalization(episode_id, source_key, options)`
  - `segment_transcript_to_utterances(episode_id)`
  - `save_utterance_edits(episode_id, rows)`
  - `save_cue_edits(episode_id, lang, rows)`
- Le widget UI ne doit orchestrer que l'affichage/interaction.

---

## Phase 1 : MVP transcript (livrable productif)

### 1.1 Créer l'onglet

- **Créer** `src/howimetyourcorpus/app/tabs/tab_preparer.py` avec `PreparerTabWidget`.
- callbacks:
  `get_store`, `get_db`, `show_status`, `on_go_alignement`.
- UI minimale:
  combo épisode, combo fichier (Transcript actif, SRT désactivés), zone texte, boutons:
  `Nettoyer`, `Rechercher/Remplacer`, `Segmenter en tours`, `Enregistrer`, `Aller à l'alignement`.
- **Ajouter** un indicateur `*` de brouillon non sauvegardé.

### 1.2 Brancher dans la fenêtre principale

- **Modifier** `app/tabs/__init__.py` (export `PreparerTabWidget`).
- **Modifier** `app/ui_mainwindow.py`:
  - `_build_tab_preparer()` entre Inspecteur et Alignement
  - mise à jour complète `TAB_*`
  - `_refresh_preparer()`
  - `closeEvent` avec `preparer_tab.save_state()` si état

### 1.3 Chargement transcript

- source par défaut: `clean`, fallback `raw`.
- logique simple:
  - si `segments utterance` existent, proposer vue table
  - sinon vue texte

### 1.4 Normalisation explicite

- **Créer** `NormalizeOptionsDialog` (ou widget local) avec options explicites.
- support preset via profils existants.
- appliquer `NormalizationProfile.apply`.
- persister via `save_clean_text_with_meta`.

### 1.5 Recherche/remplacement

- dialogue dédié avec options case-sensitive + regex.
- modifications en mémoire puis sauvegarde explicite (pas d'auto-save).
- si texte modifié: marquer état `dirty`.

### 1.6 Segmentation + édition tours

- segmentation via `segmenter_utterances`.
- persistance via `db.upsert_segments(episode_id, "utterance", segments)`.
- table editable `[n | personnage | texte]`.
- sauvegarde:
  - `update_segment_speaker`
  - `update_segment_text`
  - synchronisation `character_assignments` (`source_type="segment"`).
- **Comportement re-segmentation à verrouiller**:
  - par défaut: demander confirmation explicite avant écrasement des edits tours existants;
  - option future: fusion assistée (hors MVP).

### 1.7 Undo/Redo et gestion des brouillons

- toutes les actions suivantes doivent être Undoables:
  - remplacement texte;
  - segmentation;
  - édition table tours;
  - sauvegarde des tours.
- au changement d'épisode/source/onglet:
  - prompt `Enregistrer / Ignorer / Annuler` si `dirty`.

### 1.8 Lien Alignement

- bouton `Aller à l'alignement`:
  - ouvre onglet Alignement
  - sélectionne épisode courant
  - présélectionne `segment_kind="utterance"` si disponible.
- contrat de handoff:
  `open_alignement_for_episode(episode_id, segment_kind)` côté `MainWindow`.

---

## Phase 2 : mode SRT (EN/FR/IT) + timecodes lecture

### 2.1 Activer sources SRT

- combo fichier: `Transcript`, `SRT EN`, `SRT FR`, `SRT IT`.
- chargement via `db.get_cues_for_episode_lang`.
- table:
  `[n | debut | fin | personnage | texte]`.

### 2.2 Normalisation/assignation sur cues

- normalisation sur `text_clean` avec `db.update_cue_text_clean`.
- assignation personnage:
  - écriture `character_assignments` (`source_type="cue"`),
  - option de préfixage cohérent avec propagation actuelle.
- réécriture piste disque via `cues_to_srt` + `save_episode_subtitle_content`.
- opérations regroupées dans une transaction logique (DB puis disque avec rollback compensatoire minimal si échec).

### 2.3 Timecodes en lecture seule

- conversion `start_ms/end_ms` en format SRT.
- pas d'édition à cette phase.

---

## Phase 3 : statut et options avancées

### 3.1 Statut par fichier (recommandé)

- persistance simple JSON projet:
  `episode_prep_status.json`.
- clé:
  `(episode_id, source_key)` avec valeurs:
  `raw`, `normalized`, `edited`, `verified`, `to_review`.

### 3.2 Statut par ligne (optionnel)

- uniquement si besoin métier fort.
- implique migration SQL (`segments` + `subtitle_cues`).

### 3.3 Édition timecodes (optionnel)

- éditer `start_ms/end_ms` avec validation stricte:
  `start < end`, valeurs >= 0.
- sauvegarde via `update_cue_timecodes`.
- validation supplémentaire:
  empêcher chevauchement non intentionnel avec la cue suivante/précédente (mode strict configurable).

---

## Ordre d'exécution recommandé

1. P0.1 + P0.3 (APIs et contrat de sauvegarde)
2. P0.2 (refactor index onglets)
3. Phase 1 complète
4. P0.4 + tests Phase 1
5. Phase 2
6. Phase 3 (parties utiles seulement)

---

## Fichiers impactés (révisé)

| Fichier | Action |
|---------|--------|
| `app/tabs/tab_preparer.py` | Créé puis refactoré (orchestration conservée) |
| `app/tabs/preparer_views.py` | Ajouté (sous-vues transcript/cues) |
| `app/tabs/preparer_save.py` | Ajouté (validation + sauvegarde + undo snapshot) |
| `app/tabs/preparer_context.py` | Ajouté (navigation/chargement épisode+source) |
| `app/tabs/preparer_edit.py` | Ajouté (édition locale + recherche/remplacement + segmentation) |
| `app/tabs/preparer_state.py` | Ajouté (état/snapshots statut+assignations+persistence) |
| `app/tabs/__init__.py` | Export `PreparerTabWidget` |
| `app/ui_mainwindow.py` | Insertion onglet + constantes + navigation + refresh |
| `app/dialogs/normalize_options.py` | Ajouté (UI normalisation explicite) |
| `core/storage/db_segments.py` | `update_segment_text` ajouté |
| `core/storage/db_subtitles.py` | `update_cue_timecodes` ajouté |
| `core/storage/db.py` | Wrappers exposés |
| `core/storage/project_store.py` | `episode_prep_status` (load/save/get/set) |
| `core/preparer/` | Service + helpers partagés (`status`, `timecodes`, `snapshots`, `persistence`) |
| `tests/` | Tests API + navigation/UI + undo/preparer consolidés |

---

## Estimation révisée

- **P0** : 0,5 à 1 jour
- **Phase 1** : 2 jours
- **Phase 2** : 1 à 1,5 jour
- **Phase 3** : 0,5 à 1,5 jour selon options retenues

---

## Critères d'acceptation

1. L'onglet Préparer est visible entre Inspecteur et Alignement, sans casser les autres navigations.
2. Un transcript peut être normalisé explicitement, édité, segmenté en tours, sauvegardé et relu.
3. Les tours édités sont bien persistés en base (`speaker` + `text`).
4. Le passage vers Alignement reprend l'épisode courant et permet un run sur `utterance`.
5. Les sources SRT affichent correctement timecodes + texte, avec sauvegarde sans perte.
6. Les brouillons non sauvegardés ne sont jamais perdus silencieusement.
7. Les actions d'édition principales sont Undo/Redo.
8. Suite de tests verte.

---

## Hors périmètre explicite (pour éviter le scope creep)

### Hors périmètre Phase 1

- édition timecodes SRT;
- statut par ligne (`segment`/`cue`);
- fusion intelligente lors d'une re-segmentation.

### Hors périmètre Phase 2

- migration SQL de statuts ligne;
- outillage analytique avancé personnages (global cross-série détaillé).

### Hors périmètre Phase 3

- automatisation complète d'arbitrage de conflits d'édition multi-utilisateur.

---

## Décisions à verrouiller avant dev

1. Vue par défaut si segments existent:
   table tours ou texte brut.
2. Position de l'UI normalisation:
   dialogue modal ou panneau inline.
3. Politique de sauvegarde:
   explicite (bouton) ou auto-save partiel.
4. Portée de Phase 3:
   statut fichier seul ou statut par ligne.
