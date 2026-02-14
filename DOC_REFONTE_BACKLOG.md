# DOC_REFONTE_BACKLOG.md

## 1) Objectif

Ce document définit le backlog complet de la refonte UX + architecture de **HowIMetYourCorpus**, avec un ordre de priorité, des tickets actionnables et des critères d’acceptation vérifiables.

Ce backlog intègre:

1. Les frictions observées lors de l’audit technique et UX.
2. Les décisions du mini-atelier de conception.
3. Les priorités non négociables (intégrité, réactivité UI, maintenabilité, performance, ergonomie, Windows readiness).

## 2) Décisions validées (atelier)

### 2.1 Cible UI

1. Onglets cibles:
- `Pilotage` (fusion Projet + Corpus)
- `Inspecteur`
- `Validation & Annotation` (fusion Alignement + Personnages)
- `Concordance`

2. Les logs quittent les onglets:
- accès via menu `Outils > Journaux`
- panneau repliable pour flux live

### 2.2 Règles de workflow

1. Source de vérité des états épisode: **DB**.
2. Scopes unifiés pour toutes actions: `épisode courant | sélection | saison | tout`.
3. Rejouabilité explicite: option `force` pour les étapes dérivées.
4. Exécution métier centralisée dans un service unique (`WorkflowService`).

### 2.3 Politique de profils (à unifier)

1. Profil d’acquisition:
- web scraping/API uniquement
- adapter, rythme, retries, règles réseau

2. Profil de normalisation:
- transcript + sous-titres
- mode explicite (auto, manuel, hybride)

3. Profil d’export:
- format/présentation, sans altération cachée du contenu

### 2.4 Acquisition étendue

1. L’acquisition doit supporter:
- transcripts web
- sous-titres API (OpenSubtitles)
- sous-titres scraping (nouveaux adapters)

## 3) Frictions importées de l’audit

### 3.1 Frictions P0

1. Rejouabilité incomplète des dérivés (`skip` silencieux si artefact existe).
2. Scope incohérent (`Tout faire (sélection)` indexe plus large que la sélection).
3. États UI incomplets/incohérents (`ERROR` non visible de façon fiable).
4. SRT-only partiellement hors DB (ajout manuel non upsert complet).
5. Statistique `avg_confidence` d’alignement incorrecte.
6. Risque de jobs concurrents.
7. Progression affichée non globale.

### 3.2 Frictions P1/P2

1. Cibles d’alignement trop figées (FR hardcodé au lancement).
2. Ambiguïté export JSON vs JSONL.
3. Numérotation SRT d’export non standard (base 0).
4. Duplications de logique (sélection d’épisodes, statuts, normalisation cues).

## 4) Cible architecture (résumé)

```text
UI Tabs
  -> WorkflowService.execute(action_id, scope, options)
      -> ActionCatalog
      -> ScopeResolver
      -> EpisodeStateResolver
      -> JobController
      -> PipelineRunner
          -> ProjectStore + CorpusDB
```

## 5) Format ticket

Chaque ticket suit ce format:

1. `ID`
2. `Problème utilisateur`
3. `Décision produit`
4. `Changements techniques`
5. `Fichiers impactés`
6. `Critères d’acceptation`
7. `Risques`
8. `Tests`

## 6) Backlog priorisé (vue synthèse)

| ID | Epic | Priorité | Effort | Dépendances |
|---|---|---|---|---|
| RF-001 | Baseline de refonte (tests/scénarios) | P0 | M | - |
| RF-002 | Contrats workflow (types + interfaces) | P0 | M | RF-001 |
| RF-003 | WorkflowService (socle) | P0 | L | RF-002 |
| RF-004 | ActionCatalog déclaratif | P0 | M | RF-003 |
| RF-005 | ScopeResolver unifié | P0 | M | RF-004 |
| RF-006 | EpisodeStateResolver (DB source of truth) | P0 | M | RF-003 |
| RF-007 | UI états épisodes alignée DB | P0 | M | RF-006 |
| RF-008 | SRT-only: upsert DB systématique | P0 | S | RF-006 |
| RF-009 | JobController single-flight | P0 | M | RF-003 |
| RF-010 | Progression globale de job | P0 | M | RF-009 |
| RF-011 | Rejouer avec force (UI + core) | P0 | M | RF-003 |
| RF-012 | Reprendre les échecs | P0 | M | RF-009 |
| RF-013 | Scope strict pour “Tout faire (sélection)” | P0 | S | RF-005 |
| RF-014 | Fix avg_confidence alignement | P0 | S | - |
| RF-015 | Fix export JSON/JSONL Concordance | P0 | S | - |
| RF-016 | SRT export en numérotation standard | P0 | S | - |
| RF-017 | Nettoyage duplications bloquantes | P1 | S | - |
| RF-020 | Politique de profils unifiée (spécification) | P0 | M | RF-002 |
| RF-021 | Traçabilité profil appliqué par artefact | P1 | M | RF-020 |
| RF-022 | Badges UI de normalisation/profil | P1 | M | RF-021 |
| RF-030 | Adapters à capacités (transcript/subtitles) | P1 | M | RF-002 |
| RF-031 | Acquisition multi-source dans config projet | P1 | M | RF-030 |
| RF-032 | Unification OpenSubtitles dans acquisition | P1 | M | RF-030 |
| RF-033 | Adapter subtitles scraping (squelette) | P1 | L | RF-030 |
| RF-034 | Garde-fous réseau/toS/rate-limit par source | P1 | M | RF-033 |
| RF-040 | Nouvel onglet Pilotage (fusion Projet+Corpus) | P1 | L | RF-003, RF-005, RF-006 |
| RF-041 | Inspecteur recentré QA épisode courant | P1 | M | RF-040 |
| RF-042 | Fusion Alignement+Personnages | P1 | L | RF-040 |
| RF-043 | Logs via menu + panneau repliable | P1 | M | RF-009 |
| RF-044 | UX unifiée des exports | P2 | M | RF-040 |
| RF-050 | Batch DB writes (segments/cues/align) | P1 | M | RF-003 |
| RF-051 | Optimisation BuildDbIndexStep | P1 | S | - |
| RF-052 | Optimisation alignement heuristique | P2 | M | RF-030 |
| RF-053 | Rationalisation KWIC post-traitement | P2 | M | - |
| RF-054 | Migration SQL perf/indexes | P2 | M | RF-050 |
| RF-060 | Annulation coopérative réseau | P1 | M | RF-009 |
| RF-061 | Horodatage timezone-aware UTC | P1 | S | - |
| RF-062 | Ouverture logs cross-platform | P2 | S | RF-043 |
| RF-063 | Suite de tests refonte (scope/state/recover) | P0 | M | RF-001 |

## 7) Détail des tickets

### RF-001 — Baseline de refonte (tests/scénarios)

1. Problème utilisateur:
- Risque élevé de régression pendant refonte.

2. Décision produit:
- Geler une baseline fonctionnelle avant tout refactor.

3. Changements techniques:
- Ajouter scénarios de référence: web complet, SRT-only, reprise échecs.

4. Fichiers impactés:
- `tests/`
- `example/`

5. Critères d’acceptation:
- scénarios reproductibles documentés
- baseline testable en local et CI

6. Risques:
- couverture initiale incomplète

7. Tests:
- `pytest -q`
- smoke scénarios manuels scriptés

---

### RF-002 — Contrats workflow (types + interfaces)

1. Problème utilisateur:
- logique dispersée, difficile à maintenir.

2. Décision produit:
- contrat explicite des actions et des états.

3. Changements techniques:
- définir dataclasses/protocoles: `WorkflowAction`, `WorkflowScope`, `EpisodeStateSnapshot`.

4. Fichiers impactés:
- `src/howimetyourcorpus/core/workflow/contracts.py` (nouveau)

5. Critères d’acceptation:
- types utilisés par le service et l’UI
- docs de contrat présentes

6. Risques:
- effort de migration d’appelants

7. Tests:
- tests unitaires contrats + validations

---

### RF-003 — WorkflowService (socle)

1. Problème utilisateur:
- mêmes opérations codées dans plusieurs onglets.

2. Décision produit:
- une porte d’entrée métier unique.

3. Changements techniques:
- créer `WorkflowService.execute(action_id, scope, options)`.

4. Fichiers impactés:
- `src/howimetyourcorpus/core/workflow/service.py` (nouveau)
- `src/howimetyourcorpus/app/ui_mainwindow.py`

5. Critères d’acceptation:
- au moins fetch/normalize/segment/index passent par le service

6. Risques:
- régression de branchements UI

7. Tests:
- intégration workflow via service

---

### RF-004 — ActionCatalog déclaratif

1. Problème utilisateur:
- activation/désactivation des boutons hétérogène.

2. Décision produit:
- catalogue d’actions piloté par métadonnées.

3. Changements techniques:
- action = id, label, prérequis, scopes, artefacts produits.

4. Fichiers impactés:
- `src/howimetyourcorpus/core/workflow/actions.py` (nouveau)

5. Critères d’acceptation:
- prérequis évalués de manière uniforme

6. Risques:
- mapping initial incomplet

7. Tests:
- tests table-driven des prérequis

---

### RF-005 — ScopeResolver unifié

1. Problème utilisateur:
- comportements différents selon onglet.

2. Décision produit:
- résolution unique de scope.

3. Changements techniques:
- centraliser extraction d’`episode_ids` depuis contexte UI.

4. Fichiers impactés:
- `src/howimetyourcorpus/core/workflow/scope.py` (nouveau)
- `src/howimetyourcorpus/app/tabs/tab_corpus.py`

5. Critères d’acceptation:
- même scope = même résultat dans toutes actions

6. Risques:
- impacts sur habitudes utilisateurs

7. Tests:
- tests unitaires scope + tests end-to-end sur sélection/saison/tout

---

### RF-006 — EpisodeStateResolver (DB source of truth)

1. Problème utilisateur:
- états épisodes divergents.

2. Décision produit:
- DB devient source officielle des états.

3. Changements techniques:
- lecture centralisée des statuts + check artefacts diagnostiques.

4. Fichiers impactés:
- `src/howimetyourcorpus/core/workflow/state.py` (nouveau)
- `src/howimetyourcorpus/core/storage/db.py`

5. Critères d’acceptation:
- état `ERROR` visible et stable en UI

6. Risques:
- besoin migration légère d’états historiques

7. Tests:
- tests statuts avec cas d’erreur et cas SRT-only

---

### RF-007 — UI états épisodes alignée DB

1. Problème utilisateur:
- affichage statuts inexact.

2. Décision produit:
- modèles Qt lisent `EpisodeStateResolver`.

3. Changements techniques:
- retirer logique dupliquée dans modèles table/arbre.

4. Fichiers impactés:
- `src/howimetyourcorpus/app/models_qt.py`

5. Critères d’acceptation:
- statuts identiques entre vues

6. Risques:
- tri/filtre à ajuster

7. Tests:
- tests de modèles Qt sur jeux d’états

---

### RF-008 — SRT-only: upsert DB systématique

1. Problème utilisateur:
- épisodes manuels absents en DB.

2. Décision produit:
- toute création épisode écrit aussi DB.

3. Changements techniques:
- compléter `_add_episodes_manually` avec upsert DB.

4. Fichiers impactés:
- `src/howimetyourcorpus/app/tabs/tab_corpus.py`

5. Critères d’acceptation:
- KWIC/jointures valides en SRT-only

6. Risques:
- doublons si normalisation d’id incohérente

7. Tests:
- test d’intégration SRT-only complet

---

### RF-009 — JobController single-flight

1. Problème utilisateur:
- jobs concurrents possibles.

2. Décision produit:
- un seul job actif à la fois (ou queue explicite ultérieure).

3. Changements techniques:
- garde centralisée au lancement de job.

4. Fichiers impactés:
- `src/howimetyourcorpus/app/ui_mainwindow.py`
- `src/howimetyourcorpus/app/workers.py`

5. Critères d’acceptation:
- second lancement refusé proprement avec message clair

6. Risques:
- frustration si pas de queue

7. Tests:
- test double-click/rapid-fire actions

---

### RF-010 — Progression globale de job

1. Problème utilisateur:
- progression locale par step trompeuse.

2. Décision produit:
- progression globale pondérée par nombre d’actions.

3. Changements techniques:
- agréger progression step + index step courant.

4. Fichiers impactés:
- `src/howimetyourcorpus/core/pipeline/runner.py`
- `src/howimetyourcorpus/app/ui_mainwindow.py`

5. Critères d’acceptation:
- barre progresse de 0 à 100 sans retours incohérents

6. Risques:
- pondération imparfaite selon coût réel

7. Tests:
- jobs mixtes multi-steps

---

### RF-011 — Rejouer avec force

1. Problème utilisateur:
- impossible de recalculer facilement un dérivé.

2. Décision produit:
- options `force` visibles en UI.

3. Changements techniques:
- checkbox/bouton force pour normalize/segment/index/subtitles normalize.

4. Fichiers impactés:
- `src/howimetyourcorpus/app/tabs/tab_corpus.py`
- `src/howimetyourcorpus/app/tabs/tab_inspecteur.py`
- `src/howimetyourcorpus/app/ui_mainwindow.py`

5. Critères d’acceptation:
- recalcul effectif même si artefacts existent

6. Risques:
- coûts CPU/I/O augmentés

7. Tests:
- non-régression skip + force

---

### RF-012 — Reprendre les échecs

1. Problème utilisateur:
- reprise batch laborieuse.

2. Décision produit:
- action native “Reprendre les échecs”.

3. Changements techniques:
- mémoriser dernier lot en échec + filtre rapide.

4. Fichiers impactés:
- `src/howimetyourcorpus/app/tabs/tab_corpus.py`
- `src/howimetyourcorpus/app/ui_mainwindow.py`

5. Critères d’acceptation:
- un clic relance seulement les épisodes en échec

6. Risques:
- persistance de contexte de run

7. Tests:
- test avec échecs simulés et reprise

---

### RF-013 — Scope strict “Tout faire (sélection)”

1. Problème utilisateur:
- l’action déborde du scope attendu.

2. Décision produit:
- toutes sous-actions respectent strictement la sélection.

3. Changements techniques:
- `BuildDbIndexStep(episode_ids=...)` dans workflow sélection.

4. Fichiers impactés:
- `src/howimetyourcorpus/app/tabs/tab_corpus.py`
- `src/howimetyourcorpus/core/pipeline/tasks.py`

5. Critères d’acceptation:
- aucune écriture hors sélection

6. Risques:
- dépendances indirectes à documenter

7. Tests:
- test de périmètre DB avant/après

---

### RF-014 — Fix avg_confidence alignement

1. Problème utilisateur:
- stats de confiance fausses.

2. Décision produit:
- agrégation SQL correcte.

3. Changements techniques:
- utiliser `SUM(confidence)` + `COUNT(confidence)` par groupe.

4. Fichiers impactés:
- `src/howimetyourcorpus/core/storage/db_align.py`

5. Critères d’acceptation:
- valeurs concordent avec calcul manuel

6. Risques:
- aucun majeur

7. Tests:
- test unitaire dédié stats align

---

### RF-015 — Fix export JSON/JSONL Concordance

1. Problème utilisateur:
- JSONL peut être exporté en JSON selon filtre.

2. Décision produit:
- priorité claire à l’extension ou filtre exact.

3. Changements techniques:
- ordre des conditions d’export corrigé.

4. Fichiers impactés:
- `src/howimetyourcorpus/app/tabs/tab_concordance.py`

5. Critères d’acceptation:
- `.jsonl` exporte toujours en JSONL

6. Risques:
- aucun majeur

7. Tests:
- test UI/export ciblé

---

### RF-016 — SRT export en numérotation standard

1. Problème utilisateur:
- interop SRT fragile (index base 0).

2. Décision produit:
- export SRT en index 1..N.

3. Changements techniques:
- adapter `cues_to_srt`.

4. Fichiers impactés:
- `src/howimetyourcorpus/core/subtitles/parsers.py`

5. Critères d’acceptation:
- validation sur lecteurs SRT externes

6. Risques:
- aucun majeur

7. Tests:
- test unitaire de sérialisation SRT

---

### RF-017 — Nettoyage duplications bloquantes

1. Problème utilisateur:
- dette qui gêne la refonte.

2. Décision produit:
- supprimer les duplications à fort bruit seulement.

3. Changements techniques:
- méthode dupliquée sous-titres, helper sélection épisodes, normalisation cue partagée.

4. Fichiers impactés:
- `src/howimetyourcorpus/app/tabs/tab_sous_titres.py`
- `src/howimetyourcorpus/app/tabs/tab_corpus.py`
- `src/howimetyourcorpus/core/subtitles/parsers.py`
- `src/howimetyourcorpus/core/storage/db_subtitles.py`

5. Critères d’acceptation:
- code supprimé net, comportement identique

6. Risques:
- régression mineure de branchement

7. Tests:
- tests existants + smoke manual

---

### RF-020 — Politique de profils unifiée (spécification)

1. Problème utilisateur:
- confusion: quels profils s’appliquent à quoi.

2. Décision produit:
- trois familles de profils officielles (acquisition/normalisation/export).

3. Changements techniques:
- documenter contrat + stockage config versionné.

4. Fichiers impactés:
- `DOC_REFONTE_BACKLOG.md`
- `DOC_REFONTE_PLAN_EXEC.md`
- `src/howimetyourcorpus/core/storage/project_store.py`

5. Critères d’acceptation:
- politique visible et compréhensible depuis UI

6. Risques:
- migration config existante

7. Tests:
- tests de lecture/écriture config refondue

---

### RF-021 — Traçabilité profil appliqué

1. Problème utilisateur:
- difficile de savoir quel profil a été appliqué.

2. Décision produit:
- chaque artefact dérivé garde une empreinte profil.

3. Changements techniques:
- métadonnées `applied_profile_id` + `applied_at` sur clean, cues, exports.

4. Fichiers impactés:
- `src/howimetyourcorpus/core/storage/project_store.py`
- `src/howimetyourcorpus/core/storage/db_subtitles.py`

5. Critères d’acceptation:
- inspectable dans UI

6. Risques:
- compat backward des méta JSON

7. Tests:
- tests méta persistées

---

### RF-022 — Badges UI de normalisation/profil

1. Problème utilisateur:
- statut de normalisation peu lisible.

2. Décision produit:
- badges: `Non normalisé`, `Normalisé (profil X)`.

3. Changements techniques:
- enrichir table épisodes + inspecteur + sous-titres.

4. Fichiers impactés:
- `src/howimetyourcorpus/app/models_qt.py`
- `src/howimetyourcorpus/app/tabs/tab_inspecteur.py`
- `src/howimetyourcorpus/app/tabs/tab_sous_titres.py`

5. Critères d’acceptation:
- badge visible et cohérent partout

6. Risques:
- surcharge visuelle

7. Tests:
- tests UI smoke

---

### RF-030 — Adapters à capacités

1. Problème utilisateur:
- acquisition figée par type de source.

2. Décision produit:
- modèle de capacités explicites.

3. Changements techniques:
- enrichir `SourceAdapter` ou ajouter couche `AcquisitionProvider`.

4. Fichiers impactés:
- `src/howimetyourcorpus/core/adapters/base.py`
- `src/howimetyourcorpus/core/adapters/subslikescript.py`

5. Critères d’acceptation:
- UI peut proposer actions selon capacités source

6. Risques:
- compat adapters existants

7. Tests:
- tests registry/capabilities

---

### RF-031 — Acquisition multi-source dans config

1. Problème utilisateur:
- projet limité à une logique source unique implicite.

2. Décision produit:
- config par artefact/source (transcript/subtitles).

3. Changements techniques:
- structure config enrichie (migration douce).

4. Fichiers impactés:
- `src/howimetyourcorpus/core/storage/project_store.py`
- `src/howimetyourcorpus/core/models.py`

5. Critères d’acceptation:
- config ancienne toujours lisible

6. Risques:
- complexité migration

7. Tests:
- test migration config legacy

---

### RF-032 — Unification OpenSubtitles dans acquisition

1. Problème utilisateur:
- logique API sous-titres partiellement séparée.

2. Décision produit:
- OpenSubtitles devient un provider standard d’acquisition.

3. Changements techniques:
- brancher `DownloadOpenSubtitlesStep` au nouveau service/capabilities.

4. Fichiers impactés:
- `src/howimetyourcorpus/core/pipeline/tasks.py`
- `src/howimetyourcorpus/core/opensubtitles/client.py`

5. Critères d’acceptation:
- même UX d’acquisition que les autres sources

6. Risques:
- quotas API / erreurs réseau

7. Tests:
- tests unitaires client + intégration step

---

### RF-033 — Adapter subtitles scraping (squelette)

1. Problème utilisateur:
- pas d’acquisition sous-titres scraping native.

2. Décision produit:
- ajouter un premier adapter scraping de sous-titres.

3. Changements techniques:
- provider `fetch_subtitles` + parsing + import pipeline.

4. Fichiers impactés:
- `src/howimetyourcorpus/core/adapters/` (nouveau module)
- `src/howimetyourcorpus/core/pipeline/tasks.py`

5. Critères d’acceptation:
- POC fonctionnel sur une source testée

6. Risques:
- instabilité HTML, légalité, anti-bot

7. Tests:
- fixtures HTML + non-régression scraping

---

### RF-034 — Garde-fous réseau/toS/rate-limit

1. Problème utilisateur:
- acquisition potentiellement fragile/non conforme.

2. Décision produit:
- règles réseau explicites par source.

3. Changements techniques:
- rate-limit source-aware, retries status-aware, logs de conformité.

4. Fichiers impactés:
- `src/howimetyourcorpus/core/utils/http.py`
- `src/howimetyourcorpus/core/pipeline/tasks.py`

5. Critères d’acceptation:
- 429/403 mieux gérés et expliqués en UI

6. Risques:
- augmentation latence

7. Tests:
- tests mocks HTTP status 403/429/5xx

---

### RF-040 — Nouvel onglet Pilotage

1. Problème utilisateur:
- Projet et Corpus éclatés, actions dupliquées.

2. Décision produit:
- fusionner en un onglet d’orchestration.

3. Changements techniques:
- créer `tab_pilotage.py` et migrer les blocs pertinents.

4. Fichiers impactés:
- `src/howimetyourcorpus/app/tabs/tab_pilotage.py` (nouveau)
- `src/howimetyourcorpus/app/ui_mainwindow.py`

5. Critères d’acceptation:
- plus aucun doublon d’action batch hors Pilotage

6. Risques:
- changement fort d’habitudes UI

7. Tests:
- smoke UX sur parcours complet

---

### RF-041 — Inspecteur recentré QA

1. Problème utilisateur:
- confusion entre QA et orchestration.

2. Décision produit:
- Inspecteur = épisode courant + QA seulement.

3. Changements techniques:
- conserver actions rapides locales, supprimer batch.

4. Fichiers impactés:
- `src/howimetyourcorpus/app/tabs/tab_inspecteur.py`
- `src/howimetyourcorpus/app/tabs/tab_inspecteur_sous_titres.py`

5. Critères d’acceptation:
- scope épisode uniquement

6. Risques:
- besoin de raccourci vers Pilotage

7. Tests:
- tests UI sur actions locales

---

### RF-042 — Fusion Alignement + Personnages

1. Problème utilisateur:
- annotation dépend de l’alignement mais séparée en onglet distant.

2. Décision produit:
- unifier dans `Validation & Annotation`.

3. Changements techniques:
- run sélectionné partagé avec assignation/propagation.

4. Fichiers impactés:
- `src/howimetyourcorpus/app/tabs/tab_alignement.py`
- `src/howimetyourcorpus/app/tabs/tab_personnages.py`

5. Critères d’acceptation:
- propagation explicite sur run choisi

6. Risques:
- écran dense

7. Tests:
- workflow align -> assignation -> propagation

---

### RF-043 — Logs via menu + panneau repliable

1. Problème utilisateur:
- onglet logs surcharge la navigation.

2. Décision produit:
- logs accessibles depuis menu + dock.

3. Changements techniques:
- retirer onglet logs, ajouter actions menu.

4. Fichiers impactés:
- `src/howimetyourcorpus/app/ui_mainwindow.py`
- `src/howimetyourcorpus/app/tabs/tab_logs.py`

5. Critères d’acceptation:
- logs consultables globalement sans onglet dédié

6. Risques:
- découverte de la fonctionnalité

7. Tests:
- smoke ouverture panneau/fichier

---

### RF-044 — UX unifiée des exports

1. Problème utilisateur:
- exports dispersés et parfois incohérents.

2. Décision produit:
- contrat d’export homogène (extension prioritaire, filtres explicites).

3. Changements techniques:
- helper commun de routing export + conventions partagées.

4. Fichiers impactés:
- `src/howimetyourcorpus/core/export_utils.py`
- `src/howimetyourcorpus/app/tabs/` (plusieurs)

5. Critères d’acceptation:
- comportement identique pour tous formats

6. Risques:
- régression ciblée sur un format

7. Tests:
- tests exports tabulaires + docx + jsonl

---

### RF-050 — Batch DB writes

1. Problème utilisateur:
- coûts I/O élevés sur gros corpus.

2. Décision produit:
- batcher les writes DB.

3. Changements techniques:
- `executemany` et transactions groupées.

4. Fichiers impactés:
- `src/howimetyourcorpus/core/storage/db_segments.py`
- `src/howimetyourcorpus/core/storage/db_subtitles.py`
- `src/howimetyourcorpus/core/storage/db_align.py`

5. Critères d’acceptation:
- gain mesurable sur import/alignement batch

6. Risques:
- rollback transaction à soigner

7. Tests:
- tests perf simples + intégrité data

---

### RF-051 — Optimisation BuildDbIndexStep

1. Problème utilisateur:
- requêtes répétées inutiles.

2. Décision produit:
- calcul local des IDs indexés.

3. Changements techniques:
- charger set indexé une seule fois.

4. Fichiers impactés:
- `src/howimetyourcorpus/core/pipeline/tasks.py`

5. Critères d’acceptation:
- baisse du nombre de requêtes SQL

6. Risques:
- faible

7. Tests:
- tests unitaires + profilage simple

---

### RF-052 — Optimisation alignement heuristique

1. Problème utilisateur:
- complexité potentiellement élevée sur gros épisodes.

2. Décision produit:
- heuristiques bornées et fenêtrage.

3. Changements techniques:
- préfiltrage cues candidats, préconcaténations contrôlées.

4. Fichiers impactés:
- `src/howimetyourcorpus/core/align/aligner.py`

5. Critères d’acceptation:
- temps d’alignement réduit sans perte qualité majeure

6. Risques:
- faux négatifs si fenêtrage trop strict

7. Tests:
- bench + qualité sur fixtures

---

### RF-053 — Rationalisation KWIC post-traitement

1. Problème utilisateur:
- duplication logique et ellipses peu utiles.

2. Décision produit:
- helper central KWIC left/match/right.

3. Changements techniques:
- factoriser post-traitement dans `db_kwic.py`.

4. Fichiers impactés:
- `src/howimetyourcorpus/core/storage/db_kwic.py`

5. Critères d’acceptation:
- code réduit, résultats stables

6. Risques:
- impact sur format exact des sorties

7. Tests:
- tests snapshot de résultats KWIC

---

### RF-054 — Migration SQL perf/indexes

1. Problème utilisateur:
- montée en charge DB perfectible.

2. Décision produit:
- migration additive non destructive.

3. Changements techniques:
- `005_perf_indexes.sql` + bump schema_version.

4. Fichiers impactés:
- `src/howimetyourcorpus/core/storage/migrations/005_perf_indexes.sql` (nouveau)
- `src/howimetyourcorpus/core/storage/db.py`

5. Critères d’acceptation:
- migration idempotente et backward-safe

6. Risques:
- temps de création index sur grosses DB

7. Tests:
- tests migration v4 -> v5

---

### RF-060 — Annulation coopérative réseau

1. Problème utilisateur:
- annulation non immédiate sur I/O réseau.

2. Décision produit:
- annulation prise en compte avant/après requêtes.

3. Changements techniques:
- checks `is_cancelled` autour des appels fetch/download.

4. Fichiers impactés:
- `src/howimetyourcorpus/core/pipeline/tasks.py`

5. Critères d’acceptation:
- annulation visible en quelques secondes max

6. Risques:
- implémentation fine selon bibliothèque HTTP

7. Tests:
- tests avec mocks de latence réseau

---

### RF-061 — Horodatage timezone-aware UTC

1. Problème utilisateur:
- warnings runtime et dette future.

2. Décision produit:
- `datetime.now(datetime.UTC)` partout.

3. Changements techniques:
- remplacer `utcnow()`.

4. Fichiers impactés:
- `src/howimetyourcorpus/core/pipeline/tasks.py`
- `src/howimetyourcorpus/core/storage/db.py`
- `src/howimetyourcorpus/core/storage/db_align.py`

5. Critères d’acceptation:
- plus de warning de dépréciation datetime

6. Risques:
- aucun majeur

7. Tests:
- tests existants + vérification warnings

---

### RF-062 — Ouverture logs cross-platform

1. Problème utilisateur:
- `os.startfile` Windows-only.

2. Décision produit:
- fallback cross-platform via Qt.

3. Changements techniques:
- `QDesktopServices.openUrl` fallback.

4. Fichiers impactés:
- `src/howimetyourcorpus/app/ui_mainwindow.py`

5. Critères d’acceptation:
- ouverture log sur Windows et macOS

6. Risques:
- permission OS

7. Tests:
- smoke multi-OS

---

### RF-063 — Suite tests refonte (scope/state/recover)

1. Problème utilisateur:
- régressions probables sans couverture dédiée.

2. Décision produit:
- suite de tests centrée refonte.

3. Changements techniques:
- tests sur états, scopes, reprise échecs, force, jobs.

4. Fichiers impactés:
- `tests/` nouveaux modules

5. Critères d’acceptation:
- couverture des flux critiques refondus

6. Risques:
- coût initial de setup test

7. Tests:
- CI obligatoire avant merge

## 8) Définition de prêt (Definition of Ready)

Un ticket est prêt si:

1. décision produit figée
2. dépendances identifiées
3. critères d’acceptation testables
4. impacts fichiers listés
5. risque qualifié (faible/moyen/élevé)

## 9) Définition de terminé (Definition of Done)

Un ticket est terminé si:

1. code + tests + docs sont alignés
2. non-régression `pytest -q`
3. UX valide sur le parcours concerné
4. logs et erreurs explicites
5. compat Windows préservée

## 10) Questions ouvertes (à trancher tôt)

1. Mode par défaut de normalisation sous-titres à l’import: `auto` ou `manuel`?
2. Support officiel des langues > 3 caractères (codes internes vs ISO)?
3. Queue de jobs (plus tard) ou simple refus du 2e job?
4. Niveau de support légal/ToS pour adapters de scraping sous-titres (liste blanche de sources)?
