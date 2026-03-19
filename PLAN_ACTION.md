# Plan d'action HIMYC — Audit 19 mars 2026

> **Périmètre** : Backend Python (`/HIMYC`) + Frontend Tauri TypeScript (`/himyc-tauri`)
> **Derniers tickets livrés** : MX-034 → MX-040 (concordancier, quality bar, mode traduction, align config, export rapport, curation granulaire, retarget modal)

---

## État global

| Dimension | État |
|-----------|------|
| Endpoints backend | 28/28 implémentés |
| Modules frontend | 6/6 présents |
| Bugs critiques | 1 fixé (Query import), 1 ouvert (CharacterAssignment schema) |
| Couverture fonctionnelle estimée | ~87 % |

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
| MX-021c | Catalogue personnages + assignations | ✅ | ⚠️ | Schema mismatch |
| MX-022 | KWIC query (FTS5) | ✅ | ✅ | Livré |
| MX-025 | Facettes & analytics | ✅ | ✅ | Livré |
| MX-027 | QA report (gate + issues) | ✅ | ✅ | Livré |
| MX-028 | Audit View alignement | ✅ | ✅ | Livré |
| MX-029 | Concordancier parallèle | ✅ | ✅ | Livré |
| MX-030 | Export alignements (CSV/TSV) | ✅ | ✅ | Livré |
| MX-031 | Propagate personnages → SRT | ✅ | ✅ | Livré |
| MX-032 | Auto-assign personnages | ✅ | ⚠️ | Schema mismatch |
| MX-034 | Concordancier — query builder + export | ✅ | ✅ | Livré |
| MX-035 | Quality bar + batch collisions | ✅ | ✅ | Livré |
| MX-036 | Mode Traduction segmentation | ✅ | ✅ | Livré |
| MX-037 | Align config (pivot_lang, min_conf…) | ✅ | ✅ | Livré |
| MX-038 | Export rapport JSON run | ✅ | ✅ | Livré |
| MX-039 | Curation granulaire (ignored + bulk) | ✅ | ✅ | Livré |
| MX-040 | Retarget modal (search + réassignation) | ✅ | ✅ | Livré |

---

## Bugs confirmés

### 🐛 B-001 — Import `Query` manquant dans `server.py` · **FIXÉ**

- **Sévérité** : P0 — NameError sur 10+ endpoints à l'exécution
- **Localisation** : `server.py:17`
- **Fix appliqué** : `from fastapi import Depends, FastAPI, HTTPException, Query`
- **Commit** : `4d1b4e0`

---

### 🐛 B-002 — Schema `CharacterAssignment` incohérent · **OUVERT**

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

## Prochaines actions recommandées

### Semaine courante

| Priorité | Action | Effort | Ticket |
|----------|--------|--------|--------|
| 🔴 P1 | Fixer B-002 (CharacterAssignment schema) | S | — |
| 🟠 P1 | G-001 : Édition transcript inline | M | MX-041 |
| 🟠 P1 | G-002 : Suppression source | S | MX-042 |

### Semaine suivante

| Priorité | Action | Effort | Ticket |
|----------|--------|--------|--------|
| 🟡 P2 | G-005 : Keyboard shortcuts Audit View | S | MX-043 |
| 🟡 P2 | G-006 : Filtre épisode Concordancier parallèle | S | MX-044 |
| 🟡 P2 | G-003 : Propagate personnages → segments | M | MX-045 |
| 🟡 P2 | G-009 : Export rapport HTML | S | MX-046 |

### Sprint suivant

| Priorité | Action | Effort | Ticket |
|----------|--------|--------|--------|
| 🟡 P2 | G-004 : Minimap Audit View | L | MX-047 |
| 🟡 P2 | G-007 : Progression job align | M | MX-048 |
| 🟡 P2 | G-008 : Note/commentaire lien | M | MX-049 |

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

*Généré automatiquement après audit du 19 mars 2026.*
