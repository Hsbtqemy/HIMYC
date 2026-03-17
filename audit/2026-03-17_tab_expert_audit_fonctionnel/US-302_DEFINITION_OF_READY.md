# US-302 — Definition of Ready (Gate US-301)

Date: 2026-03-17
Scope: Epic Inspecteur Cockpit (CTA "Prochaine action recommandée")

## Objectif
Sécuriser le démarrage de `US-302` (implémentation CTA) en évitant tout faux départ si la matrice d'état n'est pas stabilisée.

## Prérequis obligatoires (DoR)
- `US-301` est validée en revue produit/UX.
- La matrice CTA est **gelée** avant le kickoff du Sprint 3 (versionnée).
- La matrice couvre explicitement:
  - `transcript-first`
  - `srt-only`
  - `mode similarity`
  - `alignement déjà existant`
- Les cas `Transcript = N/A` sont présents pour les branches où applicable (`srt-only`, `similarity`).
- Les jeux de tests dérivés de la matrice sont prêts:
  - au moins 1 test par branche principale de décision.

## Règle de démarrage US-302
`US-302` démarre uniquement si tous les prérequis ci-dessus sont satisfaits et approuvés.

## Règle de blocage / changement
- Si la matrice change après kickoff Sprint 3:
  - `US-302` passe en `blocked`,
  - un change request est ouvert,
  - l'impact planning/tests est réestimé avant reprise.

## Critère de gouvernance
La matrice CTA est l'unique source de vérité pour la logique de recommandation.  
Aucune règle ad hoc ne doit être ajoutée directement en implémentation sans mise à jour préalable de la matrice.
