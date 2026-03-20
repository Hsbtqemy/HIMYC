# Audit — Valeurs hardcodées (20 mars 2026)

> Périmètre : backend Python + frontend TypeScript
> Objectif : identifier toute valeur qui devrait être une constante, une config ou un paramètre

---

## Résumé exécutif

| Catégorie | Instances | Risque max | Action |
|-----------|-----------|-----------|--------|
| Langues (`["en","fr","it"]`) | 6+ | 🔴 Très élevé | Constante `SUPPORTED_LANGUAGES` |
| Noms de fichiers | 20+ | 🔴 Très élevé | Constantes `FILE_*` |
| Limites / pagination | 12+ | 🟡 Élevé | Constantes `LIMIT_*` |
| KWIC context window | 6 | 🟡 Élevé | Constante `KWIC_CONTEXT_WINDOW` |
| Port 8765 | 3 | 🟡 Élevé | Constante ou env var |
| Profil normalisation | 4 | 🟡 Élevé | Constante `DEFAULT_NORMALIZE_PROFILE` |
| Patterns regex validation | 4 | 🟠 Moyen | Constantes `*_PATTERN` |
| Statuts enum | 8 | 🟠 Moyen | Enum / tuple |
| Labels Tauri / API | 3 | 🟠 Moyen | Constantes frontend |
| Version | 2 | 🟠 Moyen | Source unique |
| Autres (KWIC ellipsis, regex speaker) | 6 | 🟢 Faible | Constantes locales |

**Total : ~70 instances sur 13 catégories**

---

## 1. Langues supportées

| Valeur | Fichier | Ligne | Contexte |
|--------|---------|-------|---------|
| `["en", "fr", "it"]` | `server.py` | 825 | boucle langues concordancier |
| `lang_pool = ["en", "fr", "it"]` | `server.py` | 1621 | export alignments |
| `("en", "fr", "it") as const` | `constituerModule.ts` | ~3580 | build langCols |
| `pivot_lang or "en"` | `server.py` | 817 | défaut pivot |
| `pivot_lang or "en"` | `server.py` | 1619 | défaut pivot export |
| `pivot_lang or "en"` | `db_align.py` | 554 | défaut pivot concordance |

**Risque** : Ajouter une 4ème langue nécessite de modifier 6+ endroits.

**Fix proposé** :
```python
# core/constants.py
SUPPORTED_LANGUAGES: list[str] = ["en", "fr", "it"]
DEFAULT_PIVOT_LANG = "en"
```
```typescript
// src/constants.ts
export const SUPPORTED_LANGUAGES = ["en", "fr", "it"] as const;
```

---

## 2. Noms de fichiers

| Valeur | Fichier | Occurrences | Risque |
|--------|---------|-------------|--------|
| `"corpus.db"` | `server.py:82,90`, `project_store.py:372` | 3 | 🔴 Très élevé |
| `"raw.txt"` | `server.py:346`, `project_store_episode_io.py:36,71,84` | 4 | 🔴 Très élevé |
| `"clean.txt"` | `server.py:346,435,437`, `project_store_episode_io.py:53,71,89` | 6 | 🔴 Très élevé |
| `"segments.jsonl"` | `server.py:209,346,437,1326,1388` | 5 | 🔴 Très élevé |
| `"report.json"` | `server.py:543`, `jobs.py:403` | 2 | 🟡 Élevé |
| `"exports"` | `server.py:1289,1614` | 2 | 🟠 Moyen |
| `"episodes"` | `server.py:209,1326,1388` | 3 | 🟠 Moyen |
| `"default.json"` (config) | `project_store.py` | 1 | 🟢 Faible |

**Fix proposé** :
```python
# core/constants.py
CORPUS_DB_FILENAME   = "corpus.db"
RAW_TEXT_FILENAME    = "raw.txt"
CLEAN_TEXT_FILENAME  = "clean.txt"
SEGMENTS_JSONL_FILENAME = "segments.jsonl"
ALIGN_REPORT_FILENAME = "report.json"
EXPORTS_DIR_NAME     = "exports"
EPISODES_DIR_NAME    = "episodes"
```

---

## 3. Limites de pagination et seuils de requête

| Valeur | Contexte | Fichier | Occurrences |
|--------|---------|---------|-------------|
| `50` | limit par défaut audit links | `server.py:599`, `db.py:714` | 2 |
| `200` | max limit audit links + query | `server.py:599,812,839` | 3 |
| `2000` | max hits KWIC | `server.py:1012` | 1 |
| `5000` | limit fetch pour facettes | `server.py:1057` | 1 |
| `100` | max limit subtitle cues search | `server.py:747` | 1 |
| `20` | default limit subtitle cues | `db.py:592`, `db_align.py:179` | 2 |
| `10` | neighbourhood window cues | `db.py:591`, `db_align.py:178`, `server.py:746` | 3 |

**Fix proposé** :
```python
DEFAULT_AUDIT_LIMIT  = 50
MAX_AUDIT_LIMIT      = 200
MAX_KWIC_HITS        = 2000
FACETS_FETCH_LIMIT   = 5000
DEFAULT_CUES_LIMIT   = 20
DEFAULT_CUES_WINDOW  = 10
MAX_CUES_LIMIT       = 100
```

---

## 4. KWIC — Fenêtre de contexte

| Valeur | Fichier | Ligne | Contexte |
|--------|---------|-------|---------|
| `45` | `db_kwic.py` | 39 | `window` param par défaut |
| `45` | `db_kwic.py` | 122 | windowing parallel |
| `45` | `db_kwic.py` | 197 | windowing facets |
| `45` | `db.py` | 247 | wrapper query |
| `45` | `db.py` | 336 | wrapper facets |
| `45` | `db.py` | 441 | wrapper parallel |

6 occurrences identiques — si on change la fenêtre, il faut modifier 6 endroits.

**Fix** :
```python
KWIC_CONTEXT_WINDOW = 45  # Nombre de caractères de chaque côté du match
KWIC_FACETS_WINDOW  = 5   # Fenêtre réduite pour les agrégations
```

---

## 5. Port et URL backend

| Valeur | Fichier | Contexte |
|--------|---------|---------|
| `8765` | `server.py:5,60` | `PORT` + config uvicorn |
| `1421` | `server.py:39` | CORS origin Vite dev |
| `"http://localhost:8765"` | `api.ts:11` | base URL fetch Tauri |
| `"localhost"` | `server.py:39,40,41,60` | CORS + host uvicorn |

**Fix proposé** :
```python
# server.py
PORT = int(os.environ.get("HIMYC_API_PORT", 8765))
ALLOWED_ORIGINS = [
    "tauri://localhost",
    f"http://localhost:{PORT}",
    "http://localhost:1421",  # Vite dev
]
```
```typescript
// api.ts
const API_BASE = import.meta.env.VITE_API_BASE ?? "http://localhost:8765";
```

---

## 6. Profil de normalisation par défaut

| Valeur | Fichier | Occurrences |
|--------|---------|-------------|
| `"default_en_v1"` | `server.py:123,170` | 2 |
| `"default_en_v1"` | `jobs.py:312,353` | 2 |

**Fix** :
```python
DEFAULT_NORMALIZE_PROFILE = "default_en_v1"
```

---

## 7. Patterns regex de validation

| Pattern | Fichier | Ligne | Contexte |
|---------|---------|-------|---------|
| `^(auto\|accepted\|rejected\|ignored)$` | `server.py` | 596, 807 | Validation statut lien |
| `^(sentence\|utterance)$` | `server.py` | 839 | Validation segment kind |
| `^(strict\|lenient)$` | `server.py` | 1350 | Validation policy QA |
| `^(csv\|tsv)$` | `server.py` | 1601 | Validation format export |

**Fix** :
```python
ALIGN_STATUS_VALUES  = ("auto", "accepted", "rejected", "ignored")
SEGMENT_KIND_VALUES  = ("sentence", "utterance")
QA_POLICY_VALUES     = ("strict", "lenient")
EXPORT_FORMAT_VALUES = ("csv", "tsv")
# Patterns générés automatiquement
ALIGN_STATUS_PATTERN = f"^({'|'.join(ALIGN_STATUS_VALUES)})$"
```

---

## 8. Clés sources transcript/SRT

| Valeur | Fichier | Occurrences |
|--------|---------|-------------|
| `"transcript"` | `server.py` | 6+ |
| `"srt_"` (prefix) | `server.py` | 5+ |

```python
SOURCE_KEY_TRANSCRIPT = "transcript"
SOURCE_KEY_SRT_PREFIX  = "srt_"
```

---

## 9. Constantes frontend TypeScript

| Valeur | Fichier | Occurrences | Fix |
|--------|---------|-------------|-----|
| `"sidecar_fetch_loopback"` | `api.ts:36,568` | 2 | `const TAURI_CMD = "sidecar_fetch_loopback"` |
| `"UNKNOWN"` (erreur défaut) | `api.ts:47,62,77,92` | 4 | `const DEFAULT_ERROR_CODE = "UNKNOWN"` |

---

## 10. Version

| Valeur | Fichier | Note |
|--------|---------|------|
| `VERSION = "0.1.0"` | `server.py:27` | Hardcodé |
| `version = "0.6.4"` | `pyproject.toml:7` | Source de vérité |

**Fix** :
```python
from importlib.metadata import version as _pkg_version
VERSION = _pkg_version("howimetyourcorpus")
```

---

## 11. SQLite pragmas

| Valeur | Fichier | Contexte | Note |
|--------|---------|---------|------|
| `-64000` (cache 64 MB) | `db.py:50` | `PRAGMA cache_size` | Acceptable en constante locale |
| `268435456` (256 MB mmap) | `db.py:52` | `PRAGMA mmap_size` | Acceptable en constante locale |
| `500` | `db_align.py:120` | Chunk bulk SQLite | Constante `SQLITE_BULK_CHUNK_SIZE` |

---

## 12. Divers (faible impact)

| Valeur | Fichier | Contexte |
|--------|---------|---------|
| `"..."` | `db_kwic.py:97,99,248,249` | Marqueur ellipsis KWIC |
| `"^([^:]+):\s*"` | `db_kwic.py:238` | Regex extraction speaker SRT |
| `"00:00:00,000 --> 00:00:00,000"` | export segments | Timecode SRT fallback |
| `999999` | `db_align.py:452` | Fallback COALESCE sort |

---

## Plan d'action — Tickets

| ID | Action | Fichiers | Effort | Priorité |
|----|--------|---------|--------|---------|
| **HC-01** | Créer `core/constants.py` (langues, fichiers, limites, patterns) | Nouveau fichier + imports | S | 🟡 P2 |
| **HC-02** | Créer `src/constants.ts` frontend (langues, Tauri cmd) | Nouveau fichier + imports | XS | 🟡 P2 |
| **HC-03** | `KWIC_CONTEXT_WINDOW` — centraliser les 6 occurrences | `db_kwic.py`, `db.py` | XS | 🟡 P2 |
| **HC-04** | Noms fichiers — remplacer les 20+ occurrences | `server.py`, `project_store_*.py` | S | 🟡 P2 |
| **HC-05** | Port 8765 — constante + env var `HIMYC_API_PORT` | `server.py`, `api.ts` | XS | 🟠 P3 |
| **HC-06** | `DEFAULT_NORMALIZE_PROFILE` — centraliser les 4 occurrences | `server.py`, `jobs.py` | XS | 🟠 P3 |
| **HC-07** | `VERSION` — lire depuis `importlib.metadata` | `server.py` | XS | 🟠 P3 |
| **HC-08** | SQLite pragmas — constantes locales dans `db.py` | `db.py` | XS | 🔵 P4 |

---

*Audit réalisé le 20 mars 2026 — ~70 instances identifiées dans 13 catégories*
