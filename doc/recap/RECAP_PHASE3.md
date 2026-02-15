# Récap Phase 3 — Import sous-titres SRT/VTT

**HowIMetYourCorpus** — Phase 3 : import de sous-titres (fichiers locaux .srt / .vtt), stockage par épisode/langue, recherche KWIC sur les cues.

---

## 1. Objectif Phase 3

- **Import** : importer des fichiers SRT ou VTT (fichiers locaux) pour un épisode et une langue donnée.
- **Stockage** : conserver le fichier brut + un audit des cues (timecodes, text_raw, text_clean) ; en base : pistes (tracks) + cues avec FTS pour la recherche.
- **Exploration** : recherche KWIC sur les sous-titres (scope « Cues (sous-titres) » dans la concordance, avec filtre langue).

---

## 2. Ce qui a été mis en place

### 2.1 Parsing SRT / VTT

| Élément | Fichier | Rôle |
|--------|---------|------|
| **Cue** | `core/subtitles/parsers.py` | Dataclass : `episode_id`, `lang`, `n`, `start_ms`, `end_ms`, `text_raw`, `text_clean`, `meta`. `cue_id` = `{episode_id}:{lang}:{n}` (property). |
| **parse_srt** | id. | Parse un contenu SRT (timecodes `HH:MM:SS,MMM --> ...`), retourne `list[Cue]` avec `text_clean` normalisé. |
| **parse_vtt** | id. | Parse WEBVTT (timecodes `HH:MM:SS.MMM` ou `MM:SS.MMM`), supprime tags `<v>`, `<i>`, etc., retourne `list[Cue]`. |
| **parse_subtitle_file** | id. | Détecte SRT/VTT par extension ou en-tête, retourne `(cues, "srt"|"vtt")`. |

Normalisation minimaliste des cues : suppression des tags VTT, espaces/sauts de ligne → `text_clean`.

### 2.2 Stockage fichier + base

| Élément | Fichier | Rôle |
|--------|---------|------|
| **Layout disque** | `core/storage/project_store.py` | `episodes/<episode_id>/subs/<lang>.srt` ou `.vtt` + `<lang>_cues.jsonl` (audit des cues). |
| **save_episode_subtitles** | id. | Sauvegarde le contenu brut + liste d’audit cues (pour traçabilité). |
| **has_episode_subs** | id. | Indique si un fichier subs existe pour (episode_id, lang). |
| **Migration 003** | `core/storage/migrations/003_subtitles.sql` | Tables `subtitle_tracks` (track_id, episode_id, lang, format, source_path, imported_at, meta_json) et `subtitle_cues` (cue_id, track_id, episode_id, lang, n, start_ms, end_ms, text_raw, text_clean, meta_json) + FTS5 `cues_fts` + triggers. |
| **add_track** | `core/storage/db.py` | Enregistre ou met à jour une piste (episode_id, lang, format, etc.). |
| **upsert_cues** | id. | Remplace les cues d’une piste (DELETE + INSERT). |
| **get_tracks_for_episode** | id. | Liste les pistes d’un épisode avec `nb_cues`. |
| **get_cues_for_episode_lang** | id. | Liste les cues d’un épisode pour une langue (pour affichage / audit). |

### 2.3 Pipeline

| Étape | Fichier | Rôle |
|-------|---------|------|
| **ImportSubtitlesStep** | `core/pipeline/tasks.py` | Prend `(episode_id, lang, file_path)`. Parse le fichier, remplit `episode_id`/`lang` sur chaque Cue, sauvegarde via `store.save_episode_subtitles` + `db.add_track` + `db.upsert_cues`. Idempotent si on réimporte : la piste est mise à jour. |

### 2.4 Recherche KWIC sur les cues

| Élément | Fichier | Rôle |
|--------|---------|------|
| **KwicHit** | `core/storage/db.py` | Champs ajoutés Phase 3 : `cue_id`, `lang`. |
| **query_kwic_cues** | id. | Recherche FTS sur `cues_fts` (text_clean), filtres optionnels `lang`, `season`, `episode`. Retourne des `KwicHit` avec `cue_id` et `lang` renseignés. |

### 2.5 UI

| Élément | Fichier | Rôle |
|--------|---------|------|
| **Onglet Sous-titres** | `app/ui_mainwindow.py` | Liste déroulante Épisode + Langue (en/fr/it) + bouton « Importer SRT/VTT... ». Liste « Pistes pour l’épisode » : `lang | format | nb cues`. |
| **Import** | id. | `_subs_import_file` : ouverture d’un fichier .srt/.vtt, puis `ImportSubtitlesStep(eid, lang, path)` en job async ; à la fin, rafraîchit la liste des pistes. |
| **Concordance** | id. | Scope « Cues (sous-titres) » + combo Langue (—/en/fr/it). Si scope = cues, appel à `query_kwic_cues(term, lang=..., season=..., episode=...)`. |
| **Export KWIC** | id. | Les hits issus des cues ont `cue_id` et `lang` ; export CSV/TSV/JSON/JSONL les inclut (comme pour segment_id/kind). |

### 2.6 Tests

| Fichier | Contenu |
|---------|--------|
| **tests/test_subtitles.py** | `parse_srt` (basic, multi-ligne), `parse_vtt` (basic, italics), `parse_subtitle_file` (fixtures sample.srt / sample.vtt). |
| **tests/test_db_kwic.py** | Phase 3 : `add_track`, `upsert_cues` (cues issues de `parse_srt`), `query_kwic_cues` ; vérification de `cue_id` et `lang` sur les hits. |

---

## 3. Structure projet (Phase 3)

```
episodes/<episode_id>/
  ...
  subs/
    <lang>.srt ou <lang>.vtt    # Fichier importé
    <lang>_cues.jsonl          # Audit des cues (traçabilité)

corpus.db (après migration 003)
  subtitle_tracks (track_id, episode_id, lang, format, source_path, imported_at, meta_json)
  subtitle_cues (cue_id, track_id, episode_id, lang, n, start_ms, end_ms, text_raw, text_clean, meta_json)
  cues_fts (FTS5 sur subtitle_cues)
```

---

## 4. Workflow utilisateur (Phase 3)

1. **Ouvrir un projet** et avoir au moins un épisode (découvert).
2. **Onglet Sous-titres** : choisir un épisode et une langue (en/fr/it).
3. **« Importer SRT/VTT... »** : sélectionner un fichier .srt ou .vtt.
4. Le job parse le fichier, enregistre la piste et les cues, sauvegarde le fichier et l’audit dans `episodes/<id>/subs/`.
5. La liste « Pistes pour l’épisode » affiche les pistes (lang | format | nb cues).
6. **Concordance** : scope « Cues (sous-titres) », optionnellement filtre Langue ; recherche KWIC dans les sous-titres ; export des résultats avec `cue_id` et `lang`.

---

## 5. Fichiers concernés (Phase 3)

| Fichier | Rôle |
|---------|------|
| `core/subtitles/__init__.py` | Export Cue, parse_srt, parse_vtt, parse_subtitle_file. |
| `core/subtitles/parsers.py` | Cue, timecodes SRT/VTT, normalisation, parse_srt, parse_vtt, parse_subtitle_file. |
| `core/storage/project_store.py` | _subs_dir, save_episode_subtitles, has_episode_subs. |
| `core/storage/db.py` | add_track, upsert_cues, query_kwic_cues, get_tracks_for_episode, get_cues_for_episode_lang ; KwicHit.cue_id, KwicHit.lang. |
| `core/storage/migrations/003_subtitles.sql` | Tables subtitle_tracks, subtitle_cues, cues_fts, triggers, schema_version = 3. |
| `core/pipeline/tasks.py` | ImportSubtitlesStep. |
| `app/ui_mainwindow.py` | Onglet Sous-titres, _refresh_subs_tracks, _subs_on_episode_changed, _subs_import_file ; Concordance scope cues + combo Langue ; _run_kwic scope cues. |
| `tests/test_subtitles.py` | Tests parsing SRT/VTT. |
| `tests/test_db_kwic.py` | Test add_track, upsert_cues, query_kwic_cues. |
| `tests/fixtures/sample.srt`, `sample.vtt` | Fixtures optionnelles pour parse_subtitle_file. |

---

## 6. Suite prévue (Phase 4)

- **Phase 4** : Alignement transcript ↔ sous-titres officiels, UI de validation (non implémenté dans ce récap).

---

*Récap généré à partir du code et de la doc du projet HowIMetYourCorpus — Phase 3.*
