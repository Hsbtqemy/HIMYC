# SPEC UX P2 — Vue Expert (Auto-refresh + KPI)

Date: 2026-03-17
Perimetre: PLAN_ACTION_P0_P1_P2.md, items P2.1 et P2.2.

## Objectif
Clarifier la lecture des indicateurs Expert et permettre un suivi live sans action manuelle repetitive.

## Changement UX P2.1 — Auto-refresh optionnel
- Nouveau controle: `Auto-refresh (2s)` dans l en-tete de la vue Expert.
- Comportement:
  - active -> timer Qt periodique (2000 ms) qui declenche `refresh()`.
  - desactive -> timer arrete.
- Garantie de robustesse UI:
  - garde anti-reentrance (`_refresh_in_progress`) pour eviter les rafraichissements empiles.

## Changement UX P2.2 — Aide de lecture KPI
- Nouvelle barre KPI au-dessus du snapshot texte:
  - `Project loaded`
  - `Context consistent`
  - `Episode focus`
- Chaque KPI expose une infobulle explicite sur son calcul.
- Legende visible: `Legende KPI: survolez les KPI pour les criteres de calcul.`
- Le snapshot texte inclut aussi une section `KPI legend:` pour export/trace.

## Critere d acceptation
- Toggle auto-refresh activable/desactivable sans freeze.
- KPI visibles et coherents avec le snapshot apres `refresh()`.
- Tooltips disponibles sur les 3 KPI.
