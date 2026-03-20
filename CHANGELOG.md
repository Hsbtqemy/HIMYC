# Changelog — HIMYC

## [0.7.0] — 2026-03-20

### Présentation

Premier release du **frontend Tauri** (`himyc-tauri`). L'interface PyQt reste disponible ; la version Tauri devient la cible principale de développement.

Le backend Python passe de la bibliothèque seule à un **serveur HTTP complet** (FastAPI + 40 routes) qui alimente les deux UIs.

---

### Backend Python — nouveautés

#### Serveur HTTP (MX-003)

- Serveur FastAPI `howimetyourcorpus.api.server` — 40 routes couplées
- CORS configuré pour Tauri WebView + Vite dev (`localhost:1421`)
- `HIMYC_PROJECT_PATH` : chemin projet via env var (pas d'argument CLI)
- `HIMYC_API_PORT` : port configurable (défaut 8765)
- `GET /health` — statut + version
- `GET/PUT /config` — lecture/écriture configuration projet

#### Index série (MX-033)

- `PUT /series_index` — sauvegarde `series_index.json` + crée les répertoires `episodes/{id}/` manquants
- Frontend : bouton "✓ Enregistrer la structure (N épisodes)" dans les panneaux TVMaze et Subslikescript après découverte
- Résout le gap : les épisodes découverts via TVMaze/Subslikescript étaient invisibles dans la table Constituer jusqu'à sauvegarde manuelle de `series_index.json`

#### Import sources (MX-005)

- `POST /episodes/{id}/sources/transcript` — import transcript brut
- `POST /episodes/{id}/sources/srt_{lang}` — import piste SRT/VTT
- `DELETE /episodes/{id}/sources/transcript` — suppression + reset état
- `DELETE /episodes/{id}/sources/srt_{lang}` — suppression piste SRT
- `PATCH /episodes/{id}/sources/transcript` — édition inline du texte normalisé (G-001)
- `GET /episodes/{id}/sources/{key}` — lecture raw + clean

#### Jobs pipeline (MX-006)

- `POST/GET /jobs` — file de jobs (normalize, segment, align)
- `GET /jobs/{id}` — polling statut
- `DELETE /jobs/{id}` — annulation
- Progression temps réel sur jobs d'alignement (G-007)

#### Alignement (MX-028/030/037/039/040)

- `GET /episodes/{id}/alignment_runs` — liste des runs par épisode
- `GET /alignment_runs` — tous les runs du projet
- `GET/PATCH /alignment_links/{id}` — statut + note (G-008)
- `PATCH /alignment_links/{id}/retarget` — réassignation cue cible
- `PATCH /episodes/{id}/alignment_runs/{rid}/links/bulk` — bulk status
- `GET /episodes/{id}/alignment_runs/{rid}/stats` — métriques run
- `GET /episodes/{id}/alignment_runs/{rid}/links` — liste paginée (+ positions minimap)
- `GET /episodes/{id}/alignment_runs/{rid}/collisions` — collisions
- `GET /episodes/{id}/alignment_runs/{rid}/concordance` — concordancier parallèle
- `GET /episodes/{id}/subtitle_cues` — cues voisins (retarget modal)
- Paramètres exposés : `min_confidence`, `use_similarity_for_cues`
- Statut `ignored` + endpoint bulk accept/reject/ignore

#### Personnages (MX-021c/031/032)

- `GET/PUT /characters` — catalogue personnages
- `GET/PUT /assignments` — assignations segment_id/cue_id → character_id
- `POST /assignments/auto` — auto-assignation par correspondance labels
- `POST /episodes/{id}/propagate_characters` — propagation noms canoniques → cues + segments (G-003)

#### Export (MX-027/030)

- `POST /export` — corpus (TXT/CSV/JSON/DOCX) + segments (TXT/CSV/TSV) + jobs (JSONL/JSON)
- `GET /export/qa` — rapport QA (gate lenient/strict)
- `GET /export/alignments` — alignements CSV/TSV avec fieldnames dynamiques selon pivot_lang

#### Concordancier (MX-022/025)

- `POST /query` — KWIC FTS5 avec contexte 45 caractères, sensible à la casse
- `POST /query/facets` — agrégation facettes
- Paramètres : `limit`, `offset`, `has_more`, `episode_ids`

#### Découverte web (MX-021b)

- `POST /web/tvmaze/discover` — découverte séries via TVMaze
- `POST /web/subslikescript/discover` — découverte via Subslikescript
- `POST /web/subslikescript/fetch_transcript` — import transcript web

---

### Backend Python — dettes techniques résolues

| ID | Fix |
|----|-----|
| HC-01..04 | `core/constants.py` — constantes `SUPPORTED_LANGUAGES`, noms fichiers, limites, patterns ; déployées dans ~20 fichiers |
| HC-05 | `API_PORT = int(os.environ.get("HIMYC_API_PORT", 8765))` |
| HC-06 | `DEFAULT_NORMALIZE_PROFILE` centralisé × 13 fichiers |
| AUD-04 | `speaker` unifié (`personnage` supprimé), `speaker_explicit` dans `segments_fts` |
| AUD-05 | `apiPatch<T>()` helper + `cancelJob` simplifié |
| AUD-06 | Migration `006_fk_cascade.sql` — triggers CASCADE DELETE |
| AUD-07 | Migration `007_drop_runs.sql` — DROP TABLE runs orpheline |
| AUD-08 | Migration `008_speaker_explicit_fts.sql` — rebuild FTS avec `speaker_explicit` |
| AUD-09 | `__version__` via `importlib.metadata`, `pyproject.toml` source de vérité |
| B-001 | Import `Query` manquant → NameError sur 10+ endpoints |
| B-002 | `CharacterAssignment` schema aligné backend ↔ frontend |
| B-003 | `_get_db` indéfinie → 17 endpoints inaccessibles depuis MX-028 |

---

### Frontend Tauri (`himyc-tauri`) — première release

#### Architecture

- Shell Vite + TypeScript — pas de framework (DOM vanilla)
- Navigation par modules : Hub · Constituer · Exporter · Concordancier · Aligner (sous-vue) · Inspecter (sous-vue)
- Tous les appels HTTP via `sidecar_fetch_loopback` (contournement CSP Tauri)
- Mode `VITE_E2E=true` pour tests Playwright (bypass Tauri invoke → `fetch()` natif)

#### Modules

| Module | Contenu |
|--------|---------|
| **Hub** | KPIs projet (normalisés, segmentés, runs), gate QA, onboarding |
| **Constituer** | Table épisodes + sources, import transcript/SRT, découverte web, catalogue personnages + auto-assign, virtual scroll audit table (G-011) |
| **Inspecter** | Lecture raw/clean, normalize/segment, édition inline (G-001), suppression source (G-002), handoff → Aligner |
| **Aligner** | Configuration run, lancement alignement, progression temps réel (G-007) |
| **Audit View** | Table liens paginée (virtual scroll 5000+ rows), statuts A/R/I, notes inline (G-008), bulk actions, minimap scroll-sync (G-004), retarget modal, raccourcis clavier (G-005), export rapport JSON/HTML (G-009) |
| **Concordancier** | KWIC FTS5, facettes, filtre épisode (G-006), export TSV/CSV |
| **Exporter** | Export corpus/segments/jobs/alignements, rapport QA, propagation personnages |

#### Frontend — constantes centralisées

- `src/constants.ts` : `SUPPORTED_LANGUAGES`, `API_PORT`, `TAURI_SIDECAR_CMD`, `DEFAULT_ERROR_CODE`
- `src/vite-env.d.ts` : typage `VITE_E2E`

---

### Tests

#### Backend E2E (`tests/test_e2e_pipeline.py`)

9 tests pytest (TestClient) — pipeline normalize → segment → export :
- Import transcript, lecture roundtrip
- Normalize → `clean.txt` + `prep_status=clean`
- Segment → `segments.jsonl` + indexation DB
- Export TXT, CSV, corpus vide (pas de 500)

#### Frontend E2E (`himyc-tauri/tests/e2e/`)

3 tests Playwright (`VITE_E2E=true`) — pipeline UI :
- Bouton Normaliser → feedback "Terminé ✓"
- Bouton Segmenter → feedback "Terminé ✓"
- Export CSV Exporter → résultat "✓"

#### CI

- `HIMYC/.github/workflows/quality-gate.yml` — pytest + coverage + E2E backend (Windows)
- `himyc-tauri/.github/workflows/e2e.yml` — Playwright Chromium (Ubuntu)

---

### Base de données

8 migrations actives :

| # | Fichier | Contenu |
|---|---------|---------|
| 1 | schema.sql | Episodes + Documents + FTS |
| 2 | 002_segments.sql | Segments + FTS |
| 3 | 003_subtitles.sql | Tracks + Cues + FTS |
| 4 | 004_align.sql | align_runs + align_links |
| 5 | 005_optimize_indexes.sql | Index composites |
| 6 | 006_fk_cascade.sql | Triggers CASCADE DELETE |
| 7 | 007_drop_runs.sql | DROP TABLE runs |
| 8 | 008_speaker_explicit_fts.sql | segments_fts + speaker_explicit |

---

## [0.6.10] — 2026-03-16

Dernière version stable du frontend PyQt. Voir historique git (`v0.6.0`→`v0.6.10`) pour le détail des releases précédentes.
