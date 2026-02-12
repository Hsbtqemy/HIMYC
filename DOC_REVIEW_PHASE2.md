# Revue de code — Phase 2 (HowIMetYourCorpus)  
**Segmentation phrases / utterances, exports JSONL/CSV**

*Date : février 2025*

---

## 1. Contexte

La Phase 2 ajoute :
- **Segmentation** : phrases (sentence) et tours de parole (utterance) avec positions `start_char` / `end_char`, stockage en base et fichier `segments.jsonl` par épisode.
- **Exports** : corpus en TXT, CSV, JSON, Word, et **segmenté** en JSONL/CSV (utterances ou phrases) ; export des résultats KWIC en CSV/TSV/JSON/JSONL (avec `segment_id` / `kind` si scope segments).
- **UI** : onglet Inspecteur avec vue « Segments », bouton « Segmente l’épisode », liste de segments et surlignage dans le texte CLEAN ; concordance avec scope « Épisodes » vs « Segments » et kind « Phrases » / « Tours » ; export corpus et export KWIC.

Ce document résume la revue du code Phase 2 et liste les points à traiter ou à garder en tête.

---

## 2. Ce qui va bien

- **Séparation nette** : `core/segment/` (segmenters + legacy pour exports), `core/export_utils.py`, `core/storage/db.py` (segments + FTS), pipeline `SegmentEpisodeStep` / `RebuildSegmentsIndexStep`, UI qui délègue au pipeline et au store.
- **Modèle Segment** : dataclass avec `segment_id` (property), `kind`, `start_char` / `end_char`, `speaker_explicit` (sans inventer de locuteur).
- **Migrations** : `schema_version` + `002_segments.sql` pour tables `segments` et `segments_fts`, appliquées dans `db.init()`.
- **FTS segments** : `query_kwic_segments` utilise `segments_fts MATCH` puis construit le KWIC en Python ; cohérent avec la phase 1.
- **Exports** : JSONL/CSV segmentés (utterances / phrases) et exports KWIC avec `segment_id` / `kind` quand présents.
- **Tests** : `test_segment.py` (segmenters) et `test_db_kwic.py` (upsert_segments, query_kwic_segments, non-régression épisodes).

---

## 3. Actions à traiter

### 3.1 Priorité moyenne

#### A. Langue (lang_hint) en dur dans l’UI

**Fichier :** `src/howimetyourcorpus/app/ui_mainwindow.py`  
**Méthode :** `_run_segment_episode` (ligne ~572)

**Problème :** Le bouton « Segmente l’épisode » appelle `SegmentEpisodeStep(eid, lang_hint="en")`. La langue est donc fixée à `"en"` alors que `RebuildSegmentsIndexStep` la dérive du profil de normalisation (`normalize_profile`).

**À faire :** Utiliser la même logique que `RebuildSegmentsIndexStep` (ex. dériver `lang_hint` depuis `self._config.normalize_profile`) ou exposer un réglage « Langue segmentation » dans l’onglet Projet/Inspecteur.

---

#### B. Dérivation de `lang_hint` dans RebuildSegmentsIndexStep

**Fichier :** `src/howimetyourcorpus/core/pipeline/tasks.py`  
**Ligne :** ~301

**Problème :**  
`lang_hint = getattr(context.get("config"), "normalize_profile", "default_en_v1").split("_")[0].replace("default", "en") or "en"`  
donne par exemple `"en"` pour `default_en_v1` mais `"conservative"` pour `conservative_v1`, qui n’est pas un code de langue standard.

**À faire :** Soit documenter que seuls les profils du type `default_XX_v1` fournissent un vrai code langue, soit stocker un champ `lang_segmentation` (ou code langue) dans la config projet et l’utiliser ici et dans l’UI.

---

#### C. `get_segments_for_episode` : `meta_json` renvoyé en chaîne

**Fichier :** `src/howimetyourcorpus/core/storage/db.py`  
**Méthode :** `get_segments_for_episode`

**Problème :** Les lignes retournées sont des `dict(r)` ; la colonne `meta_json` est donc une chaîne JSON et non un dictionnaire. L’UI n’utilise pas `meta` pour l’instant, mais tout code qui s’attend à `meta` comme `dict` (ex. `didascalia`) devra parser.

**À faire :** Optionnel : parser `meta_json` en dict avant de retourner (et gérer `NULL` / chaîne vide). Sinon documenter que les appelants doivent parser `meta_json` si besoin.

---

### 3.2 Priorité basse

#### D. Duplication segmentation : segmenters vs legacy

**Fichiers :** `core/segment/segmenters.py` (Segment, segmenter_sentences, segmenter_utterances) et `core/segment/legacy.py` (Utterance, Phrase, segment_utterances, segment_phrases, segment_utterances_into_phrases).

**Constat :** Deux modèles (Segment avec positions vs Utterance/Phrase avec index) et des regex partagées (SPEAKER_PREFIX, SENTENCE_BOUNDARY) dupliquées. Les exports JSONL/CSV utilisent le legacy ; le pipeline et la DB utilisent les segmenters.

**À faire :** À long terme, envisager de faire dériver les exports segmentés des Segment (segmenters) pour une seule source de vérité, ou de factoriser les regex/helpers dans un module commun. Pas bloquant pour la Phase 2.

---

#### E. Affichage concordance : segment_id / kind

**Fichier :** `src/howimetyourcorpus/app/models_qt.py` — `KwicTableModel`

**Constat :** Les colonnes affichées sont Épisode, Titre, Contexte gauche, Match, Contexte droit. Les champs `segment_id` et `kind` sont exportés (CSV/TSV/JSON/JSONL) mais pas affichés dans le tableau.

**À faire :** Optionnel : ajouter une ou deux colonnes (Segment ID, Kind) quand les hits proviennent de `query_kwic_segments`, pour faciliter l’audit sans passer par l’export.

---

#### F. Export corpus : ordre des filtres et extension

**Fichier :** `src/howimetyourcorpus/app/ui_mainwindow.py` — `_export_corpus`

**Constat :** La détection du format repose sur `path.suffix` et `selected_filter`. Si l’utilisateur choisit un filtre générique « CSV » puis change l’extension en `.jsonl`, le comportement peut être ambigu.

**À faire :** Optionnel : renforcer la détection (ex. priorité au filtre sélectionné pour JSONL/CSV segmentés) et/ou documenter dans l’UI le lien extension / format.

---

## 4. Synthèse pour le dev

| Priorité | Réf   | Sujet |
|----------|-------|--------|
| Moyenne  | § 3.1 A | Utiliser une langue cohérente pour « Segmente l’épisode » (config ou réglage). |
| Moyenne  | § 3.1 B | Dérivation fiable de `lang_hint` (config ou codes langue explicites). |
| Moyenne  | § 3.1 C | Optionnel : retourner `meta` comme dict dans `get_segments_for_episode`. |
| Basse    | § 3.2 D–F | Consolidation segmenters/legacy, colonnes segment dans la table KWIC, robustesse filtre export. |

---

## 5. Fichiers Phase 2 concernés

| Fichier | Rôle Phase 2 |
|---------|----------------|
| `core/segment/__init__.py` | Export Segment + legacy (utterances/phrases). |
| `core/segment/segmenters.py` | Segment, segmenter_sentences, segmenter_utterances (positions, speaker_explicit). |
| `core/segment/legacy.py` | Utterance, Phrase, segment_utterances, segment_utterances_into_phrases (exports). |
| `core/export_utils.py` | Exports corpus (dont JSONL/CSV segmentés) et KWIC (dont segment_id/kind). |
| `core/storage/db.py` | KwicHit.segment_id/kind, upsert_segments, query_kwic_segments, get_segments_for_episode, migrations. |
| `core/storage/migrations/002_segments.sql` | Tables segments + segments_fts + triggers. |
| `core/pipeline/tasks.py` | SegmentEpisodeStep, RebuildSegmentsIndexStep. |
| `app/ui_mainwindow.py` | Export corpus, Inspecteur (Segments, bouton Segmente, liste + surlignage), Concordance (scope/kind), export KWIC. |
| `app/models_qt.py` | get_all_hits pour export KWIC. |
| `tests/test_segment.py` | Tests segmenters. |
| `tests/test_db_kwic.py` | test_upsert_segments_and_query_kwic_segments, test_kwic_episode_non_regression. |

---

*Document généré à partir de la revue de code Phase 2 du projet HowIMetYourCorpus.*
