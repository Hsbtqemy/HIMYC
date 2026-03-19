# Plan Sprints Detaille - Cockpit Inspecteur + Vue Expert

Date de reference: 2026-03-17
Perimetre: simplification Inspecteur (3 blocs) + articulation avec la vue Expert.
Contrainte structurante: Scenario B (Inspecteur = episode courant, Expert = transverse).

## Objectif

Livrer une experience claire pour utilisateur lambda/expert sans dupliquer la logique transverse deja portee par l onglet Expert.

## Cadence

- Sprint 1: structuration UI + branchements explicites.
- Sprint 2: validation UX + cadrage CTA (gate).
- Sprint 3: implementation CTA (si gate validee) + audit final.

## Sprint 1 - Structurer et clarifier

### User Stories

1. US-101 - Reorganiser Inspecteur en 3 blocs (`Consulter`, `Produire`, `Avance`)
- But: reduire la densite cognitive de la barre haute.
- Livrables:
  - regroupement visuel des actions par intention;
  - preservation des comportements existants.
- AC:
  - aucun bouton branche ne devient inactif/invisible par erreur;
  - pas de regression de navigation episode.

2. US-103 - Boutons desactives avec raison explicite
- But: expliquer pourquoi une action est indisponible.
- Livrables:
  - tooltips et/ou message court contextuel;
  - regles de desactivation homogenes.
- AC:
  - chaque bouton critique desactive a une raison lisible.

3. US-104 - Statut `Pret alignement` (Oui/Non + manquants)
- But: donner un verdict operationnel direct.
- Livrables:
  - calcul au chargement d episode;
  - detail des prerequis manquants.
- AC:
  - statut coherent avec transcript/segments/tracks reels.

4. US-105 - Tests non-regression Sprint 1
- But: verrouiller les regressions de cablage.
- Livrables:
  - tests UI/logique sur blocs + disabled reasons + pret alignement.
- AC:
  - suite ciblee verte.

### Definition of Done Sprint 1

- 0 controle present mais non branche.
- RAW/CLEAN et splitter preservent leur comportement.
- Tests Sprint 1 verts.

## Sprint 2 - Valider et figer le cadre CTA

### User Stories

1. US-204 - Revue UX utilisateur lambda + expert
- But: valider lisibilite et parcours reel.
- Livrables:
  - compte-rendu de revue;
  - ajustements mineurs (libelles, ordre, hints).
- AC:
  - confusion transcript/SRT reduite sur parcours nominal.

2. US-205 - Batterie de tests complementaires
- But: couvrir les cas incomplets/heterogenes.
- Livrables:
  - tests sur etats partiels, mismatch de contexte, transitions d onglets.
- AC:
  - aucun crash/etat incoherent sur changement de contexte.

3. US-301 - Matrice d etat CTA (gate)
- But: formaliser les recommandations avant code.
- Livrables:
  - matrice transcript x SRT x alignement x mode de travail;
  - couverture explicite des cas `SRT-only` et `similarite forcee`.
- AC:
  - validation produit/UX signee;
  - matrice gelee avant demarrage Sprint 3.

### Gate de fin Sprint 2 (DoR US-302)

- US-302 demarre uniquement si:
  - US-301 validee et gelee;
  - cas limites couverts;
  - criteres de test CTA definis.
- Reference: `US-302_DEFINITION_OF_READY.md`.

## Sprint 3 - Implementer CTA et cloturer

### User Stories

1. US-302 - Implementer `Prochaine action recommandee`
- But: guider l utilisateur vers l etape suivante pertinente.
- Livrables:
  - moteur de recommandation base sur la matrice gelee;
  - message/CTA contextuel.
- AC:
  - recommandations correctes pour transcript-first, SRT-only, et cas alignes.

2. US-304 - Audit final de branchement
- But: confirmer absence de regressions structurelles.
- Livrables:
  - matrice de branchement mise a jour;
  - evidences runtime + tests.
- AC:
  - aucun controle critique non branche;
  - verdict final documente.

3. US-303 (optionnel) - Mode `Compact/Detail`
- Condition: uniquement si les 3 blocs ne suffisent pas apres revue UX.
- AC:
  - pas de confusion avec la vue Expert transverse.

### Definition of Done Sprint 3

- CTA en production conforme a US-301.
- Audit final vert.
- Aucune duplication de logique transverse avec onglet Expert.

## Dependencies et ordre

1. US-101 -> US-103 -> US-104 -> US-105
2. US-204 + US-205 -> US-301 (gate)
3. US-301 (gelee) -> US-302 -> US-304
4. US-303 seulement si decision explicite post-revue UX.

## Etat actuel (au 2026-03-17)

- Vue Expert P1/P2: terminee (cf. `PLAN_ACTION_P0_P1_P2.md`).
- Sprints Cockpit Inspecteur: planifies ici, a executer selon priorites produit.

## Etat reel apres execution (au 2026-03-18)

Sprint 1, 2, 3 et lot recentrage INS-001 → INS-012 : **LIVRES**.

| Lot | Tickets | Etat | Tests |
|---|---|---|---|
| Sprint 1 (US-101/103/104/105) | INS-001 → INS-004 (P0) | Livre | 125/125 verts |
| Sprint 2 (US-204/205/301) | INS-004 tests | Livre | — |
| Sprint 3 (US-302/304) | INS-003 microcopy | Livre | — |
| Phase 2 recentrage (INS-005/006) | Selecteur Fichier + actions source | Livre | +7 tests |
| Phase 3 recentrage (INS-007/008/009) | Adaptateur + decouplage + integration | Livre | +14 tests |
| Phase 4 (INS-010/011/012) | UX final + docs + gate | Livre | 125/125 verts |

Suite ciblee finale :
`pytest -q tests/test_ui_inspecteur_sprint1.py tests/test_ui_inspecteur_sprint2.py
tests/test_ui_inspecteur_sprint3.py tests/test_cta_recommender.py
tests/test_ui_preparer_navigation.py tests/test_ui_inspecteur_source_flow.py`

**Resultat : 125/125 passes.**

Changements structurels permanents :
- Mode Focus par defaut (INS-001/002).
- Selecteur Fichier source-aware (INS-005/006).
- API de capacite `has_subtitle_panel()` / `set_subtitle_languages()` (INS-007/008).
- Microcopy aligne sur le nouveau flux Focus (INS-003/010).

Reference migration : `MIGRATION_INSPECTEUR_RECENTRAGE.md`.
