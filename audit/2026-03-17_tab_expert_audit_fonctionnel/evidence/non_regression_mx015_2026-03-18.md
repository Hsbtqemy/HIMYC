# Rapport de campagne non-régression — MX-015

Date : 2026-03-18
Gate cible : Gate C (MX-007..MX-009 livrés) → Gate D (MX-010..MX-012)
Verdict : **GO ✅ — 0 bloquant P0/P1**

---

## 1. Périmètre testé

### 1.1 Suite Python complète

| Métrique | Valeur |
|---|---|
| Tests collectés | 431 |
| Passés | 431 |
| Échoués | 0 |
| Erreurs | 0 |
| Durée | ~5 s |
| Commande | `python -m pytest --tb=no -q` |

### 1.2 Subset critique (Gate C/D)

| Fichier test | Domaine | Tests | Résultat |
|---|---|---|---|
| `test_api_bridge.py` | Bridge API / jobs / import sources | 25 | ✅ |
| `test_align.py` | Algorithme alignement core | 12 | ✅ |
| `test_align_integrity.py` | Intégrité BDD après delete/resegment | 4 | ✅ |
| `test_align_run_metadata.py` | Métadonnées run (segment_kind, pivot_lang) | 7 | ✅ |
| `test_preparer_service.py` | Service préparateur (édition cues, rollback) | 2 | ✅ |
| `test_project_store_config_toml.py` | Config projet (TOML, languages, profiles) | 7 | ✅ |
| `test_project_store_prep_status.py` | État sources (raw/normalized/segmented) | 4 | ✅ |
| `test_workers.py` | Workers jobs (normalize, segment) | 4 | ✅ |
| `test_ui_guards.py` | Gardes UI (CTA, états) | 6 | ✅ |
| `test_ui_alignement.py` | UI onglet Aligner (MX-009) | 36 | ✅ |
| `test_ui_inspecteur_source_flow.py` | Flux inspecteur source-centric (MX-007) | 20 | ✅ |
| **Total subset** | | **127** | **✅ 127/127** |

### 1.3 Suite TypeScript / Vitest

| Fichier test | Domaine | Tests | Résultat |
|---|---|---|---|
| `tests/model.test.ts` | Modèle source-centric (MX-004) | 30 | ✅ |
| `tests/guards.test.ts` | Gardes métier (MX-008/MX-010) | 56 | ✅ |
| **Total TS** | | **86** | **✅ 86/86** |

### 1.4 Vérification typage

| Commande | Résultat |
|---|---|
| `npx tsc --noEmit` (HIMYC_Tauri) | 0 erreur ✅ |

---

## 2. Matrice de couverture par gate

### Gate A (MX-013 + MX-001) — baseline + ADR
- Couvert par `test_api_bridge.py::test_health_always_up`
- ADR archivé dans `ADR_ARCHITECTURE_MIX_TAURI_HIMYC.md`
- **Verdict Gate A : ✅ VALIDÉ**

### Gate B (MX-002 + MX-014 + MX-003 + MX-016 + MX-004..MX-006)
Shell Tauri + bridge + constitution multi-source

| Domaine | Test représentatif | Résultat |
|---|---|---|
| Bridge API (MX-003) | `test_error_format_no_project_config` | ✅ |
| Import transcript (MX-005) | `test_import_transcript_creates_raw` | ✅ |
| Import SRT (MX-005) | `test_import_srt_creates_file` | ✅ |
| Jobs create/get/cancel (MX-006) | `test_jobs_create_normalize_transcript`, `test_jobs_get_by_id`, `test_jobs_cancel_pending` | ✅ |
| Jobs persistance (MX-006) | `test_jobs_persistence` | ✅ |
| Modèle source-centric (MX-004/MX-016) | `tests/model.test.ts` (30/30) | ✅ |

- **Verdict Gate B : ✅ VALIDÉ**

### Gate C (MX-007..MX-009) — inspection + handoff alignement
| Domaine | Test représentatif | Résultat |
|---|---|---|
| Flux inspecteur source-centric (MX-007) | `test_ui_inspecteur_source_flow.py` (20/20) | ✅ |
| Gardes métier (MX-008) | `test_ui_guards.py` (6/6) + `guards.test.ts` (56/56) | ✅ |
| Alignement + runs (MX-009) | `test_ui_alignement.py` (36/36) + `test_alignment_runs_empty` | ✅ |
| Métadonnées align (MX-009) | `test_align_run_metadata.py` (7/7) | ✅ |

- **Verdict Gate C : ✅ VALIDÉ**

### Gate D (MX-010 + MX-015 + MX-011 + MX-012) — hardening + pilote
| Domaine | État |
|---|---|
| MX-010 — Parité messages erreurs alignement | ✅ LIVRÉ (86/86 TS, 431/431 Python) |
| MX-015 — Campagne non-régression (ce rapport) | ✅ LIVRÉ |
| MX-011 — Hardening gros corpus | ⏳ À livrer |
| MX-012 — Gate final pilote | ⏳ À livrer |

- **Verdict Gate D courant : PARTIEL — Go pour MX-011**

---

## 3. Bloquants P0/P1

Aucun bloquant identifié.

---

## 4. Observations

- Le subset critique (127 tests Python) couvre l'intégralité du flux MX-003 → MX-009 : bridge, import, jobs, normalisation, segmentation, alignement, métadonnées.
- La suite complète (431 tests) ne présente aucune régression depuis la baseline Gate A.
- Les 86 tests TypeScript (model + guards) couvrent le contrat de typage entre frontend et backend.
- `tsc --noEmit` : 0 erreur confirme la cohérence des interfaces TypeScript avec l'API Python.

---

## 5. Commandes de reproductibilité

```bash
# Python full
cd /Users/hsmy/Dev/HIMYC
python -m pytest --tb=no -q

# Python subset critique Gate C/D
python -m pytest tests/test_api_bridge.py tests/test_align.py tests/test_align_integrity.py \
  tests/test_align_run_metadata.py tests/test_preparer_service.py \
  tests/test_project_store_config_toml.py tests/test_project_store_prep_status.py \
  tests/test_workers.py tests/test_ui_guards.py tests/test_ui_alignement.py \
  tests/test_ui_inspecteur_source_flow.py -q

# TypeScript
cd /Users/hsmy/Dev/HIMYC_Tauri   # https://github.com/Hsbtqemy/HIMYC_Tauri.git
npm test
npx tsc --noEmit
```
