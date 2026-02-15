# Playbook Rollback UI - Workflow

Date: 2026-02-14

## Objectif

Definir un rollback rapide et previsible pour chaque lot UI, sans casser:
- auditabilite RAW/CLEAN/SRT/ALIGN,
- integrite des donnees projet,
- continuites de workflow.

## Regles generales

1. Priorite au rollback non destructif (feature flag / bascule vue).
2. Aucun reset destructif du workspace (`git reset --hard` interdit).
3. Si regression UX severe: retour commit cible + verification smoke minimale.
4. Apres rollback: journaliser cause, impact, correctif prevu.

## Strategie de rollback par lot

| Lot | Mecanisme principal | Fallback |
|---|---|---|
| Lot -1 (fait) | Revert commit UI si blocage majeur layout | revenir au layout precedent par commit |
| Lot 1 | Flag `global_job_bar_enabled` + garde-fous propagation | desactiver barre globale et revenir aux feedbacks locaux |
| Lot 2 | Flag `kwic_async_enabled` | execution synchrone historique |
| Lot 3 | Flag `logs_incremental_refresh_enabled` | debounce seul |
| Lot 4 | Flag `personnages_model_view_enabled` | vue legacy QTableWidget |
| Lot 5 | Rollback commit UI (shortcuts/styles/focus) | desactiver raccourcis nouveaux |
| Lot 6 | Revert serie de commits lot6 (`e60922f^..b2c4a8d`) | revenir a l'ancre pre-lot6 `3216dcc` |
| QA smoke CI | Revert workflow smoke (`2d8e783`) | conserver validation locale manuelle temporaire |

## Procedure de rollback standard

1. Identifier le lot impacte et le dernier commit sain.
2. Appliquer rollback cible (flag ou revert commit).
3. Verifier:
   - ouverture projet,
   - import episode,
   - action normaliser/indexer,
   - recherche KWIC,
   - ouverture logs.
4. Documenter l'incident:
   - symptome,
   - cause probable,
   - impact utilisateur,
   - plan de correction.

## Smoke post-rollback (minimum)

Commande recommandee:

```bash
pytest -q tests/test_workflow_ui.py tests/test_workflow_status.py tests/test_workflow_advice.py tests/test_tab_logs.py
```

Critere: 100% vert avant reprise des developpements.
