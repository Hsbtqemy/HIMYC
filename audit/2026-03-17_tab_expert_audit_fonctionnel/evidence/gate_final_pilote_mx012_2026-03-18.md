# Gate final pilote — MX-012

Date : 2026-03-18
Verdict : **GO ✅ — Pilote autorisé**

---

## 1. Récapitulatif des gates

| Gate | Tickets | Verdict | Date |
|---|---|---|---|
| A | MX-013 + MX-001 | ✅ VALIDÉ | sprint initial |
| B | MX-002 + MX-014 + MX-003 + MX-016 + MX-004 + MX-005 + MX-006 | ✅ VALIDÉ | sprint 1-2 |
| C | MX-007 + MX-008 + MX-009 | ✅ VALIDÉ | sprint 3 |
| D | MX-010 + MX-015 + MX-011 + MX-012 | ✅ VALIDÉ | 2026-03-18 |

---

## 2. Checklist parité MVP

| # | Critère | Fichier(s) clé(s) | Statut |
|---|---|---|---|
| 1 | Flux unique `Episode + Source` | `constituerModule.ts`, `inspecterModule.ts` | ✅ |
| 2 | Mapping `doc_id/doc_role` encapsulé | `src/model.ts` | ✅ |
| 3 | Parcours transcript-first (import → norm → segment → align) | `constituerModule`, `inspecterModule`, `alignerModule` | ✅ |
| 4 | Parcours SRT-only (2+ SRT → align direct) | `alignerModule`, `guards.ts` | ✅ |
| 5 | Gardes métier UI + handler level | `src/guards.ts`, `guardedAction()` | ✅ |
| 6 | File de jobs persistante (pending/running/done/error/cancelled) | `api/jobs.py` — `jobs.json` | ✅ |
| 7 | Poll statut jobs (2 s) | `constituerModule`, `alignerModule` | ✅ |
| 8 | Handoff inspecter → aligner | `src/context.ts` — `setHandoff/getHandoff` | ✅ |
| 9 | Messages d'erreur actionnables | `formatJobError()`, `getAlignPreconditions()` | ✅ |
| 10 | Métriques runtime minimales | `src/perf.ts` — `[HIMYC perf]` logs | ✅ |
| 11 | Pagination gros corpus (≥ 50 ep.) | `constituerModule` — `PAGE_SIZE=50` | ✅ |
| 12 | Troncature grands textes (> 50 K chars) | `inspecterModule` — `TEXT_TRUNCATE_CHARS` | ✅ |
| 13 | Bridge API typé TS ↔ Python | `src/api.ts`, `api/server.py` | ✅ |
| 14 | Non-régression Python 431/431 | `python -m pytest` | ✅ |
| 15 | Non-régression TypeScript 98/98 | `npm test` | ✅ |
| 16 | 0 erreur de typage TypeScript | `tsc --noEmit` | ✅ |

---

## 3. Recette transcript-first

Chemin code vérifié par les tests d'intégration :

| Étape | Action | Endpoint / Code | Test de référence |
|---|---|---|---|
| 1 | Import transcript | `POST /episodes/{id}/sources/transcript` → `raw.txt` créé | `test_import_transcript_creates_raw` ✅ |
| 2 | Normaliser | `POST /jobs` `normalize_transcript` → worker `NormalizeEpisodeStep` | `test_jobs_create_normalize_transcript` ✅ |
| 3 | Segmenter | `POST /jobs` `segment_transcript` → worker `SegmentEpisodeStep` | workers tests ✅ |
| 4 | Vérifier état | `GET /episodes` → `state=segmented` | `test_project_store_prep_status` ✅ |
| 5 | Handoff → Aligner | `guardAlignEpisode` allowed, `setHandoff()`, `navigateTo("aligner")` | `guards.test.ts` ✅ |
| 6 | Lancer alignement | `POST /jobs` `align` + `params{pivot_lang, target_langs, segment_kind, run_id}` | `test_jobs_create_align` ✅ |
| 7 | Consulter runs | `GET /episodes/{id}/alignment_runs` → `report.json` | `test_alignment_runs_empty` ✅ |

---

## 4. Recette SRT-only

| Étape | Action | Endpoint / Code | Test de référence |
|---|---|---|---|
| 1 | Import SRT×2 | `POST /episodes/{id}/sources/srt_en` + `srt_fr` | `test_import_srt_creates_file` ✅ |
| 2 | Vérifier garde | `guardAlignEpisode` → allowed (2 SRT disponibles) | `guardAlignEpisode — srt-only` ✅ |
| 3 | Checklist préconditions | `getAlignPreconditions` → `srt_count` met=true | `getAlignPreconditions — srt-only` ✅ |
| 4 | Lancer alignement | `POST /jobs` `align` mode srt-only | `test_jobs_create_align` ✅ |

---

## 5. Mode de lancement pilote

### Architecture retenue (MX-001)

Mode **backend externe** — pas de sidecar intégré dans le bundle Tauri.

| Composant | Rôle | Lancement |
|---|---|---|
| Frontend Tauri | UI TypeScript + Rust shell | `tauri build` → bundle macOS/Windows/Linux |
| Backend Python | FastAPI port 8765 | `uvicorn howimetyourcorpus.api.server:app --port 8765` |
| Bridge Rust | `sidecar_fetch_loopback` | Commande Tauri intégrée au binaire — bypass CSP loopback |

**Justification** : Le projet HIMYC est un outil de corpus — l'utilisateur pilote maîtrise son environnement Python. Un sidecar intégré nécessiterait un bundling PyInstaller hors scope pilote.

### Vérification tauri.conf.json

```json
"productName": "HIMYC",
"version": "0.1.0",
"identifier": "com.himyc.app",
"build": {
  "beforeDevCommand": "npm run dev",
  "beforeBuildCommand": "npm run build"
}
```

- Aucun `externalBin` → backend externe confirmé.
- `sidecar_fetch_loopback` restreint aux adresses loopback (`127.0.0.1`, `localhost`, `::1`) — sécurité CSP correcte.
- Timeout connect 5 s, timeout requête 30 s — robuste pour le pilote.

### Commandes de lancement pilote

```bash
# Terminal 1 — backend Python
cd /path/to/himyc-project
uvicorn howimetyourcorpus.api.server:app --host 127.0.0.1 --port 8765

# Terminal 2 — frontend Tauri (dev)
cd /Users/hsmy/Dev/HIMYC_Tauri   # https://github.com/Hsbtqemy/HIMYC_Tauri.git
npm run tauri dev

# Ou build release
npm run tauri build
```

---

## 6. Bloquants P0/P1

Aucun bloquant identifié.

---

## 7. Métriques finales

| Suite | Tests | Résultat |
|---|---|---|
| Python full | 431/431 | ✅ |
| TypeScript (Vitest) | 98/98 | ✅ |
| TypeScript (tsc) | 0 erreur | ✅ |

---

## 8. Verdict Go/No-Go

> **GO ✅**
>
> Gates A, B, C et D validés.
> Flux transcript-first et SRT-only opérationnels.
> Architecture bridge loopback sécurisée.
> Non-régression 431 Python + 98 TypeScript, 0 erreur de typage.
> Aucun bloquant P0/P1 ouvert.
>
> **Le pilote HIMYC peut démarrer.**
