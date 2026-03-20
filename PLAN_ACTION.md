# Plan d'action HIMYC — Audit 19 mars 2026

> **Périmètre** : Backend Python (`/HIMYC`) + Frontend Tauri TypeScript (`/himyc-tauri`)
> **Derniers tickets livrés** : MX-034 → MX-046, MX-048, MX-049 + audit général 20 mars 2026
> **Rapport d'audit complet** : `AUDIT_2026-03.md`

---

## État global

| Dimension | État |
|-----------|------|
| Endpoints backend | 30/30 implémentés |
| Modules frontend | 6/6 présents |
| Bugs critiques | 3 fixés (Query import, CharacterAssignment schema, **_get_db undefined**) |
| Couverture fonctionnelle estimée | ~96 % |
| Audit dernière mise à jour | 20 mars 2026 |

---

## Tableau de bord MX

| Ticket | Feature | Backend | Frontend | État |
|--------|---------|:-------:|:--------:|------|
| MX-003 | API Server FastAPI | ✅ | ✅ | Livré |
| MX-005 | Import sources (transcript + SRT) | ✅ | ✅ | Livré |
| MX-006 | Job queue (normalize / segment / align) | ✅ | ✅ | Livré |
| MX-007 | Inspecter — lecture sources | ✅ | ✅ | Livré |
| MX-008 | Guards métier (pré-conditions) | ✅ | ✅ | Livré |
| MX-009 | Handoff Inspecter → Aligner | ✅ | ✅ | Livré |
| MX-020 | Shell navigation (hub + 5 modules) | ✅ | ✅ | Livré |
| MX-021b | Web discovery (TVMaze + Subslikescript) | ✅ | ✅ | Livré |
| MX-021c | Catalogue personnages + assignations | ✅ | ✅ | Livré (B-002 fixé) |
| MX-022 | KWIC query (FTS5) | ✅ | ✅ | Livré |
| MX-025 | Facettes & analytics | ✅ | ✅ | Livré |
| MX-027 | QA report (gate + issues) | ✅ | ✅ | Livré |
| MX-028 | Audit View alignement | ✅ | ✅ | Livré |
| MX-029 | Concordancier parallèle | ✅ | ✅ | Livré |
| MX-030 | Export alignements (CSV/TSV) | ✅ | ✅ | Livré |
| MX-031 | Propagate personnages → SRT | ✅ | ✅ | Livré |
| MX-032 | Auto-assign personnages | ✅ | ✅ | Livré (B-002 fixé) |
| MX-034 | Concordancier — query builder + export | ✅ | ✅ | Livré |
| MX-035 | Quality bar + batch collisions | ✅ | ✅ | Livré |
| MX-036 | Mode Traduction segmentation | ✅ | ✅ | Livré |
| MX-037 | Align config (pivot_lang, min_conf…) | ✅ | ✅ | Livré |
| MX-038 | Export rapport JSON run | ✅ | ✅ | Livré |
| MX-039 | Curation granulaire (ignored + bulk) | ✅ | ✅ | Livré |
| MX-040 | Retarget modal (search + réassignation) | ✅ | ✅ | Livré |
| MX-041 | Édition transcript inline (G-001) | ✅ | ✅ | Livré |
| MX-042 | Suppression source transcript + SRT (G-002) | ✅ | ✅ | Livré |
| MX-043 | Keyboard shortcuts Audit View (G-005) | — | ✅ | Livré |
| MX-044 | Filtre épisode Concordancier (G-006) | — | ✅ | Livré |
| MX-046 | Export rapport HTML (G-009) | — | ✅ | Livré |

---

## Bugs confirmés

### 🐛 B-001 — Import `Query` manquant dans `server.py` · **FIXÉ**

- **Sévérité** : P0 — NameError sur 10+ endpoints à l'exécution
- **Localisation** : `server.py:17`
- **Fix appliqué** : `from fastapi import Depends, FastAPI, HTTPException, Query`
- **Commit** : `4d1b4e0`

---

### 🐛 B-002 — Schema `CharacterAssignment` incohérent · **FIXÉ**

- **Sévérité** : P1 — Auto-assign produit un format que le frontend ne sait pas lire
- **Backend** (`/assignments/auto`) retourne :
  ```json
  { "source_type": "segment", "source_id": "S01E01:42", "character_id": "...", "episode_id": "...", "speaker_label": "..." }
  ```
- **Frontend** (`CharacterAssignment`) attend :
  ```typescript
  { segment_id?: string, cue_id?: string, character_id: string, ... }
  ```
- **Impact** : Les assignations auto-générées sont sauvegardées correctement (backend agnostique) mais le rendu/édition frontend peut lire des champs `undefined`.
- **Fix** : Choisir un schema unique et aligner les deux côtés.
  - Option A (recommandée) : Adopter `source_type / source_id` côté frontend, renommer les champs dans `CharacterAssignment`.
  - Option B : Faire produire au backend `segment_id` / `cue_id` directement.

---

## Gaps fonctionnels ouverts

### P1 — Impact utilisateur direct

#### G-001 · Édition transcript inline · M

- **Contexte** : L'Inspecter permet de voir `raw` vs `clean` mais pas d'éditer le texte.
- **Besoin** : Zone de saisie pour corriger le transcript normalisé manuellement avant segmentation.
- **Backend requis** : `PATCH /episodes/{id}/sources/transcript` (body: `{ clean: string }`).
- **Frontend requis** : Mode édition dans l'Inspecter, bouton "Sauvegarder".
- **Effort estimé** : M (backend 0.5j + frontend 1j)

#### G-002 · Suppression de source · S

- **Contexte** : Il n'existe pas d'endpoint `DELETE /episodes/{id}/sources/{key}`.
- **Besoin** : Permettre de supprimer une piste SRT importée par erreur ou de ré-importer proprement.
- **Backend requis** : `DELETE /episodes/{id}/sources/{key}` — supprime le fichier + réinitialise le statut prep.
- **Frontend requis** : Bouton "Supprimer" sur chaque source dans la table épisodes.
- **Effort estimé** : S (backend 0.5j + frontend 0.5j)

#### G-003 · Normalisation speaker dans segments · M

- **Contexte** : `segments.speaker_explicit` contient des labels bruts (ex: `"MARSHALL"`) qui ne sont pas normalisés vers le catalogue.
- **Besoin** : Après auto-assign, appliquer les noms canoniques dans les segments pour cohérence du concordancier.
- **Backend requis** : Extension de `POST /episodes/{id}/propagate_characters` pour inclure les segments (pas seulement les cues SRT).
- **Effort estimé** : M (backend 1j + test)

---

### P2 — Confort / Complétude

#### G-004 · Minimap Audit View · L

- **Contexte** : Dans l'audit view, pas de vue d'ensemble de la distribution des statuts sur l'axe temporel de l'épisode.
- **Besoin** : Barre latérale proportionnelle (scroll-sync) indiquant la densité de liens acceptés/rejetés/ignorés par position.
- **Backend requis** : Endpoint `GET /episodes/{id}/alignment_runs/{run_id}/links/positions` — retourne uniquement `(segment_n, status)[]` sans texte.
- **Frontend requis** : Canvas/SVG minimap cliquable pour naviguer vers la page correspondante.
- **Effort estimé** : L (backend S + frontend 2j)

#### G-005 · Keyboard shortcuts Audit View · S

- **Contexte** : La curation d'une longue liste de liens est lente sans clavier.
- **Besoin** : `A` = accepter ligne focusée, `R` = rejeter, `I` = ignorer, `↓/↑` = ligne suivante/précédente, `N/P` = page suivante/précédente.
- **Frontend uniquement** — pas de backend requis.
- **Effort estimé** : S (1j frontend)

#### G-006 · Filtre épisode dans Concordancier parallèle · S

- **Contexte** : La vue "parallèle" du concordancier groupe par épisode mais n'est pas filtrable par épisode spécifique.
- **Besoin** : Ajouter un filtre épisode dans le drawer du concordancier (déjà partiellement wired côté filtre FTS).
- **Frontend uniquement** — le backend `POST /query` accepte déjà `episode_ids`.
- **Effort estimé** : S (0.5j frontend)

#### G-007 · Indicateur de progression job align · S

- **Contexte** : Les jobs d'alignement peuvent durer 30–60s. L'UI ne montre qu'un spinner générique.
- **Besoin** : Afficher "En cours…" avec le nb de segments traités si le backend peut l'exposer.
- **Backend requis** : Extension du `JobRecord.result` avec `{ progress_pct, segments_done, segments_total }` lors du running.
- **Effort estimé** : M (backend 1j + frontend 0.5j)

#### G-008 · Note/commentaire sur un lien d'alignement · M

- **Contexte** : Un curateur peut vouloir annoter un lien avec une justification (ex: "ambiguïté sémantique").
- **Besoin** : Champ `note` optionnel sur `align_links.meta_json`.
- **Backend requis** : Extension `PATCH /alignment_links/{id}` pour accepter `note: string | null`.
- **Frontend requis** : Champ texte inline dans la table audit, persisté au blur.
- **Effort estimé** : M (backend 0.5j + frontend 1j)

#### G-009 · Export rapport HTML (en plus du JSON) · S

- **Contexte** : MX-038 produit un JSON. Un rapport HTML lisible serait plus utile pour partager.
- **Besoin** : Alternative HTML générée côté frontend (template string) avec table stats + tableau liens résumé.
- **Frontend uniquement** — deuxième bouton "⬇ HTML" à côté de "⬇ JSON".
- **Effort estimé** : S (1j frontend)

---

### P3 — Post-MVP / Long terme

#### G-010 · Mode hors-ligne partiel · XL

- **Besoin** : Service worker + cache IndexedDB pour les lectures (concordancier, audit) sans backend démarré.
- **Effort estimé** : XL

#### G-011 · Virtual scroll sur la table audit · M

- **Contexte** : Avec `limit: 9999` pour l'export, le DOM peut avoir 5000+ rows.
- **Besoin** : Virtualisation (fenêtre de rendu) pour maintenir 60fps.
- **Effort estimé** : M

#### G-012 · Tests E2E (Playwright + Tauri) · L

- **Contexte** : Aucun test automatisé end-to-end.
- **Effort estimé** : L

---

## Bugs confirmés — [AUDIT-2026-03]

### 🐛 B-003 — `_get_db` indéfinie · **FIXÉ**

- **Sévérité** : P0 — NameError au chargement — serveur ne démarrait pas
- **Présent depuis** : commit `26d1967` (MX-028)
- **Endpoints affectés** : 17 routes (DELETE transcript, audit stats/links/collisions, PATCH link, bulk, subtitle_cues, retarget, segments, QA, auto-assign, propagate, export/alignments…)
- **Fix** : Définition de `_get_db()` strict (lève 503 si corpus.db absent)
- **Commit** : `fix(server): define _get_db`

---

## Issues audit — [AUDIT-2026-03]

### 🔴 CRITIQUE

| ID | Issue | Fichier | Priorité |
|----|-------|---------|----------|
| B-003 | `_get_db` indéfinie — serveur ne démarre pas | server.py | ✅ Fixé |
| AUD-01 | Export alignements cassé si `pivot_lang ≠ en` | db_align.py L554-618 | P1 |

### 🟡 WARN

| ID | Issue | Fichier | Priorité |
|----|-------|---------|----------|
| AUD-02 | Guards `if db is None:` redondants (endpoints _get_db) | server.py ~15 occurrences | P3 |
| AUD-03 | Export `/export/alignments` écrit sur disque inutilement | server.py L1660 | P2 |
| AUD-04 | `personnage` / `speaker` / `speaker_explicit` — 3 noms | db_align.py, export_utils.py, api.ts | P3 |
| AUD-05 | `apiPost()` utilisé pour PATCH — pas de `apiPatch()` | himyc-tauri/src/api.ts | P3 |

### 🔵 NOTE

| ID | Issue | Fichier |
|----|-------|---------|
| AUD-06 | FK manquantes + pas de CASCADE sur tables enfants | schema.sql, migrations |
| AUD-07 | Table `runs` (schema.sql) jamais utilisée | schema.sql L43 |
| AUD-08 | `speaker_explicit` absent de segments_fts | 002_segments.sql |
| AUD-09 | `VERSION = "0.1.0"` hardcodé, non sync pyproject | server.py L27 |

---

## Tickets d'action audit

### AUD-01 · Export alignements multilangue · P1 · Effort M

**Problème** : `get_parallel_concordance()` assume pivot_lang = EN. Les colonnes `text_en/fr/it` sont hardcodées. Si pivot_lang = FR, `text_en` et `text_it` restent vides.

**Backend requis** :
- `db_align.get_parallel_concordance()` : renommer `target_by_cue_en` → `target_by_cue_pivot`
- Rendre l'assignation `text_{lang}` dynamique selon `pivot_lang` et les langues target disponibles dans `align_links`
- `server.py export_alignments()` : déduire les `fieldnames` du run plutôt que les hardcoder

**Frontend** : Mise à jour de l'interface `ExportAlignmentResult` si les colonnes changent

---

### AUD-03 · Export alignements : retour streaming plutôt que disque · P2 · Effort S

**Problème** : Le fichier écrit dans `exports/` n'est jamais lu par le frontend.

**Fix** : Retourner `StreamingResponse` (CSV/TSV inline) au lieu de `FileResponse`. Le frontend reçoit le contenu directement et peut proposer un téléchargement via Blob URL (pattern déjà utilisé pour l'export HTML).

---

### AUD-06 · Migration FK + CASCADE · P3 · Effort S

**Migration 006** à créer :
```sql
-- PRAGMA foreign_keys doit être ON (déjà le cas dans _conn())
-- SQLite ne supporte pas ALTER TABLE ADD CONSTRAINT
-- → recréer les tables avec FK ou documenter l'absence de CASCADE

-- Alternative légère : ajouter des triggers ON DELETE pour simuler CASCADE
CREATE TRIGGER IF NOT EXISTS fk_cascade_segments
BEFORE DELETE ON episodes BEGIN
  DELETE FROM segments WHERE episode_id = OLD.episode_id;
END;
-- idem pour subtitle_tracks, subtitle_cues, align_runs, align_links
```

---

## Prochaines actions recommandées

### Livré — sprint 19-20 mars 2026

| Ticket | Action | État |
|--------|--------|------|
| B-001  | Fix Query import server.py | ✅ Fixé |
| B-002  | Fix CharacterAssignment schema | ✅ Fixé |
| B-003  | Fix `_get_db` undefined | ✅ Fixé |
| MX-041 | G-001 : Édition transcript inline | ✅ Livré |
| MX-042 | G-002 : Suppression transcript + SRT | ✅ Livré |
| MX-043 | G-005 : Keyboard shortcuts Audit View | ✅ Livré |
| MX-044 | G-006 : Filtre épisode Concordancier | ✅ Livré |
| MX-045 | G-003 : Propagate personnages → segments | ✅ Livré |
| MX-046 | G-009 : Export rapport HTML | ✅ Livré |
| MX-048 | G-007 : Progression job align | ✅ Livré |
| MX-049 | G-008 : Note/commentaire lien | ✅ Livré |
| —      | Case-sensitive concordancier (bouton Aa) | ✅ Livré |

### Sprint prochain — priorités audit

| Priorité | Ticket | Action | Effort |
|----------|--------|--------|--------|
| 🔴 P1 | AUD-01 | Export alignements multilangue dynamique | M |
| 🟡 P2 | AUD-03 | Export streaming (supprimer écriture disque) | S |
| 🟡 P2 | G-004  | Minimap Audit View | L |
| 🔵 P3 | AUD-06 | Migration FK + CASCADE triggers | S |
| 🔵 P3 | AUD-02 | Nettoyer guards `if db is None` redondants | S |

---

## Architecture — points de vigilance

### SQLite & performance

- Les requêtes FTS5 (`cues_fts`, `segments_fts`) ont des index corrects (migration 005).
- Le chunking par 500 dans `bulk_set_align_status` est nécessaire pour SQLite (`SQLITE_LIMIT_VARIABLE_NUMBER ≈ 999`).
- Pour des épisodes longs (> 1000 segments), `limit: 9999` dans l'export rapport peut produire de larges payloads JSON. À surveiller.

### Tauri / CSP

- Tous les appels HTTP passent par `sidecar_fetch_loopback` (commande Rust) — jamais de `fetch()` direct vers localhost.
- Les `save` / `writeTextFile` / `readTextFile` nécessitent les permissions Tauri correspondantes dans `tauri.conf.json`.

### Jobs

- Le worker est un thread unique (FIFO). Les jobs `align` longs peuvent bloquer les jobs `normalize` en attente.
- Les jobs `running` au redémarrage sont remis en `pending` (idempotent).
- Il n'y a pas de timeout sur l'exécution d'un job — à surveiller pour les grands corpus.

---

*Généré après audit du 19 mars 2026. Mis à jour le 20 mars 2026 — audit général (branchements, DB, exports) + sprint MX-041→MX-049.*
