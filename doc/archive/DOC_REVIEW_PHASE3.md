# Revue de code — Phase 3 (HowIMetYourCorpus)  
**Import sous-titres SRT/VTT, pistes, cues, KWIC sur cues**

*Date : février 2025*

---

## 1. Contexte

La Phase 3 ajoute l’import de fichiers SRT/VTT (fichiers locaux) par épisode et par langue, le stockage en piste + cues (avec FTS), et la recherche KWIC sur les sous-titres (scope « Cues (sous-titres) » + filtre langue). Ce document résume la revue du code Phase 3 et liste les corrections ou évolutions à prévoir.

---

## 2. Ce qui va bien

- **Parsing** : `Cue` avec timecodes, `text_raw` / `text_clean`, normalisation minimaliste (tags VTT, espaces). `parse_srt` / `parse_vtt` / `parse_subtitle_content` / `parse_subtitle_file` ; lecture fichier une seule fois dans le step via `parse_subtitle_content`.
- **Stockage** : layout disque `episodes/<id>/subs/<lang>.(srt|vtt)` + `<lang>_cues.jsonl` ; migration 003 (subtitle_tracks, subtitle_cues, cues_fts, triggers) ; `add_track` / `upsert_cues` ; `get_tracks_for_episode` / `get_cues_for_episode_lang` avec `meta` parsé en dict.
- **Pipeline** : `ImportSubtitlesStep` idempotent (réimport = mise à jour piste + remplacement cues), gestion d’erreurs et progression.
- **KWIC cues** : `query_kwic_cues` utilise FTS `cues_fts`, retourne `KwicHit` avec `cue_id` et `lang` ; garde-fou sur terme vide (`if not term or not term.strip(): return []`).
- **UI** : onglet Sous-titres (épisode, langue, import, liste des pistes) ; Concordance scope « Cues (sous-titres) » + combo Langue ; `_on_job_finished` appelle `_refresh_subs_tracks()` pour mettre à jour la liste après import.
- **Exports KWIC** : JSON/JSONL incluent `cue_id` et `lang` quand présents.
- **Tests** : `test_subtitles.py` (parsing SRT/VTT), `test_db_kwic.py` (add_track, upsert_cues, query_kwic_cues).

---

## 3. Actions à traiter

### 3.1 Priorité haute

#### A. Export KWIC CSV/TSV : colonnes cue_id/lang manquantes quand seuls présents

**Fichier :** `src/howimetyourcorpus/core/export_utils.py`  
**Fonctions :** `export_kwic_csv`, `export_kwic_tsv`

**Problème :** L’en-tête est construit selon les attributs présents sur le premier hit (`segment_id`/`kind`, `cue_id`/`lang`). En revanche, les lignes de données sont remplies avec la logique : `if len(row0) > 7` → on ajoute toujours `segment_id`, `kind` ; `if len(row0) > 9` → on ajoute `cue_id`, `lang`. Quand les hits ont **uniquement** `cue_id` et `lang` (pas de segment), `row0` fait 9 colonnes (base 7 + cue_id, lang). On exécute donc la première branche (on écrit segment_id, kind vides) et pas la seconde (9 > 9 est faux), donc **cue_id et lang ne sont jamais écrits** dans les lignes, alors qu’ils figurent dans l’en-tête.

**À faire :** Construire chaque ligne de données en alignement explicite avec l’en-tête (par ex. parcourir les noms de colonnes optionnelles dans `row0[7:]` et ajouter la valeur correspondante pour chaque hit), ou dupliquer la même logique que pour l’en-tête (ajouter segment_id/kind **si** présents, puis cue_id/lang **si** présents) au lieu de s’appuyer sur `len(row0) > 7` / `len(row0) > 9`.

---

### 3.2 Priorité moyenne

#### B. Rafraîchissement liste pistes après import

**Fichier :** `src/howimetyourcorpus/app/ui_mainwindow.py`  
**Méthode :** `_subs_import_file` (ligne ~639)

**Problème :** Juste après `self._run_job([ImportSubtitlesStep(...)])` on appelle `self._refresh_subs_tracks()`. Le job étant asynchrone, ce rafraîchissement s’exécute avant la fin de l’import, donc la nouvelle piste n’apparaît pas à ce moment-là. La liste est déjà mise à jour dans `_on_job_finished`, donc le comportement final est correct, mais l’appel ici est redondant et peut prêter à confusion.

**À faire :** Supprimer l’appel à `_refresh_subs_tracks()` dans `_subs_import_file` et s’appuyer uniquement sur le rafraîchissement dans `_on_job_finished`.

---

#### C. query_kwic_cues et épisodes absents de la table episodes

**Fichier :** `src/howimetyourcorpus/core/storage/db.py`  
**Méthode :** `query_kwic_cues`

**Constat :** La requête fait un `JOIN` avec `episodes` pour récupérer `title`. Si une piste a été enregistrée pour un `episode_id` qui n’existe pas dans `episodes` (cas marginal, ex. import hors workflow normal), les cues de cette piste ne remonteront pas dans les résultats.

**À faire :** Soit documenter que les épisodes doivent exister dans `episodes` (ex. après « Découvrir épisodes ») avant d’importer des sous-titres ; soit utiliser un `LEFT JOIN` sur `episodes` et gérer un `title` nul dans les `KwicHit` / l’affichage.

---

#### D. Langues en dur (UI)

**Fichier :** `src/howimetyourcorpus/app/ui_mainwindow.py`

**Constat :** Les langues proposées sont fixées en dur : `subs_lang_combo.addItems(["en", "fr", "it"])` et `kwic_lang_combo` (en, fr, it). L’ajout d’une langue (ex. "de", "es") impose une modification du code.

**À faire :** Optionnel : définir la liste des langues dans la config projet ou dans un module partagé (constantes / config) et l’utiliser pour les deux combos.

---

### 3.3 Priorité basse

#### E. parse_subtitle_file et type du premier argument

**Fichier :** `src/howimetyourcorpus/core/subtitles/parsers.py`

**Constat :** La signature est `parse_subtitle_file(path: Path, lang_hint: str = "en")`. L’appelant (`ImportSubtitlesStep`) passe bien un `Path`. Si un appelant passait une `str`, `path.read_text(...)` échouerait. Pas de bug actuel, mais pour une API plus robuste on peut accepter `Path | str` et faire `path = Path(path)` en début de fonction.

**À faire :** Optionnel : accepter `Path | str` et normaliser en `Path` au début de `parse_subtitle_file`.

---

#### F. Exposer parse_subtitle_content dans la doc / __all__

**Fichier :** `src/howimetyourcorpus/core/subtitles/__init__.py`

**Constat :** `parse_subtitle_content` est exporté dans `__all__` et utilisé par le pipeline pour éviter de lire le fichier deux fois. C’est cohérent ; rien à changer si ce n’est s’assurer que la doc publique (README, RECAP) mentionne cette API si elle est destinée à des réutilisations externes.

---

## 4. Synthèse pour le dev

| Priorité | Réf   | Sujet |
|----------|-------|--------|
| Haute    | § 3.1 A | Corriger l’export KWIC CSV/TSV : écrire cue_id/lang dans les lignes quand seuls ces champs sont présents. |
| Moyenne  | § 3.2 B | Supprimer l’appel redondant à _refresh_subs_tracks dans _subs_import_file. |
| Moyenne  | § 3.2 C | Documenter ou gérer (LEFT JOIN) les cues dont l’épisode n’est pas dans episodes. |
| Moyenne  | § 3.2 D | Optionnel : rendre la liste des langues configurable. |
| Basse    | § 3.3 E–F | Optionnel : Path | str dans parse_subtitle_file ; visibilité de parse_subtitle_content. |

---

## 5. Fichiers Phase 3 concernés

| Fichier | Rôle Phase 3 |
|---------|----------------|
| `core/subtitles/__init__.py` | Export Cue, parse_srt, parse_vtt, parse_subtitle_content, parse_subtitle_file. |
| `core/subtitles/parsers.py` | Cue, timecodes SRT/VTT, normalisation, parse_*. |
| `core/storage/project_store.py` | _subs_dir, save_episode_subtitles, has_episode_subs. |
| `core/storage/db.py` | add_track, upsert_cues, query_kwic_cues, get_tracks_for_episode, get_cues_for_episode_lang ; KwicHit.cue_id, KwicHit.lang. |
| `core/storage/migrations/003_subtitles.sql` | Tables subtitle_tracks, subtitle_cues, cues_fts, triggers. |
| `core/pipeline/tasks.py` | ImportSubtitlesStep. |
| `core/export_utils.py` | Export KWIC avec cue_id/lang (CSV/TSV/JSON/JSONL) — § 3.1 A. |
| `app/ui_mainwindow.py` | Onglet Sous-titres, _subs_import_file, _refresh_subs_tracks ; Concordance scope cues + Langue ; _on_job_finished → _refresh_subs_tracks. |
| `tests/test_subtitles.py` | Tests parsing SRT/VTT. |
| `tests/test_db_kwic.py` | test_upsert_cues_and_query_kwic_cues. |

---

*Document généré à partir de la revue de code Phase 3 du projet HowIMetYourCorpus.*
