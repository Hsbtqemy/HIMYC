# DOC_REFONTE_PLAN_EXEC.md

## 1) But

Plan d’exécution détaillé de la refonte, sans big-bang, avec migration progressive et contrôle du risque.

Ce plan s’appuie sur `DOC_REFONTE_BACKLOG.md` et donne:

1. l’ordre exact des itérations,
2. les critères d’entrée/sortie,
3. les tests obligatoires,
4. la stratégie de rollback.

## 2) Contraintes de pilotage

1. Priorité absolue à l’intégrité des données (RAW immuable).
2. UI non bloquante, jobs robustes, annulation fiable.
3. Compatibilité Windows conservée.
4. Pas de réécriture complète en une seule étape.
5. Chaque itération doit laisser l’application exploitable.

## 3) Stratégie de migration (Strangler)

### 3.1 Principe

1. Introduire le nouveau socle (`core/workflow`) en parallèle.
2. Rebrancher les onglets progressivement.
3. Retirer l’ancien code seulement après parité fonctionnelle vérifiée.

### 3.2 Bascule progressive

1. Phase A: service disponible mais non exclusif.
2. Phase B: Pilotage branché au service.
3. Phase C: Inspecteur/Validation branchés.
4. Phase D: suppression des anciens chemins.

### 3.3 Option feature flag (si besoin)

1. Flag interne `new_pilotage_ui` pendant la transition.
2. Retrait du flag à la fin de l’itération UI complète.

## 4) Plan par itérations

## Itération 0 — Cadrage et baseline

### Objectif

Sécuriser la base avant refonte.

### Tickets

1. RF-001
2. RF-063 (squelette)

### Livrables

1. scénarios de référence documentés:
- web transcript complet
- SRT-only
- reprise échecs

2. baseline de tests verte.

### Go/No-Go

1. `pytest -q` vert.
2. scénarios manuels reproductibles.

### Risques

1. couverture initiale insuffisante.

### Mitigation

1. ajouter rapidement tests manquants avant itération 1.

---

## Itération 1 — Socle architecture workflow

### Objectif

Créer le cœur central d’exécution (sans changer encore tout l’UI).

### Tickets

1. RF-002
2. RF-003
3. RF-004
4. RF-005
6. RF-006

### Livrables

1. `core/workflow/contracts.py`
2. `core/workflow/service.py`
3. `core/workflow/actions.py`
4. `core/workflow/scope.py`
5. `core/workflow/state.py`

### Intégration

1. `MainWindow` sait appeler `WorkflowService` pour au moins:
- fetch
- normalize
- segment
- index

### Go/No-Go

1. parité fonctionnelle sur ces 4 actions.
2. pas de régression tests existants.

### Risques

1. adaptation progressive des onglets.

### Mitigation

1. conserver temporairement anciens chemins en fallback contrôlé.

---

## Itération 2 — Fiabilité exécution (jobs, force, reprise)

### Objectif

Rendre l’exécution robuste et prévisible pour l’utilisateur.

### Tickets

1. RF-009
2. RF-010
3. RF-011
4. RF-012
5. RF-013
6. RF-060

### Livrables

1. single-flight job.
2. progression globale.
3. options `force` visibles.
4. reprise des échecs.
5. scope strict pour “Tout faire (sélection)”.

### Go/No-Go

1. impossible de lancer 2 jobs simultanés.
2. annulation fiable sur flux long.
3. reprise échecs opérationnelle.

### Risques

1. conflits UX au début (nouveaux contrôles).

### Mitigation

1. messages UI explicites et tooltips ciblés.

---

## Itération 3 — Correctifs P0 data/exports

### Objectif

Fermer les incohérences métier critiques.

### Tickets

1. RF-007
2. RF-008
3. RF-014
4. RF-015
5. RF-016
6. RF-061

### Livrables

1. états épisodes cohérents (dont ERROR).
2. SRT-only cohérent DB.
3. stats alignement justes.
4. exports JSON/JSONL fiables.
5. SRT export standard.
6. horodatage timezone-aware.

### Go/No-Go

1. tests dédiés passent.
2. avertissements datetime supprimés.

### Risques

1. impact sur données historiques.

### Mitigation

1. migration additive et compat backward.

---

## Itération 4 — Refonte UI Pilotage

### Objectif

Fusionner Projet + Corpus dans un onglet unique d’orchestration.

### Tickets

1. RF-040
2. RF-017 (partie sélection/statuts)

### Livrables

1. `tab_pilotage.py`.
2. actions batch centralisées.
3. états + prochaine action visibles en un coup d’œil.

### Go/No-Go

1. parcours principal réalisable sans revenir à anciens onglets.
2. aucune perte fonctionnelle de configuration.

### Risques

1. courbe d’apprentissage utilisateur.

### Mitigation

1. micro-guidage intégré (“étape suivante”).

---

## Itération 5 — Recentrage Inspecteur

### Objectif

Faire de l’Inspecteur un espace QA pur sur épisode courant.

### Tickets

1. RF-041
2. RF-022 (partie badges)

### Livrables

1. actions locales uniquement.
2. badges de profil/normalisation.
3. raccourci vers Pilotage pour passer en batch.

### Go/No-Go

1. aucune action batch restante dans Inspecteur.
2. QA épisode plus lisible qu’avant.

### Risques

1. attentes utilisateurs habitués aux vieux boutons.

### Mitigation

1. mapping de transition documenté dans release notes.

---

## Itération 6 — Validation & Annotation unifiées

### Objectif

Rapprocher alignement et assignation personnages dans un flux continu.

### Tickets

1. RF-042
2. RF-021 (traçabilité utile à annotation)

### Livrables

1. run d’alignement sélectionné explicitement.
2. assignation + propagation dans le même écran.

### Go/No-Go

1. propagation toujours liée au run choisi.
2. workflow review -> annotate -> export réalisable sans changer d’onglet.

### Risques

1. complexité visuelle.

### Mitigation

1. sections repliables + sous-vues internes.

---

## Itération 7 — Politique de profils unifiée

### Objectif

Uniformiser l’application des profils et sa lisibilité.

### Tickets

1. RF-020
2. RF-021 (complément)
3. RF-022 (complément)

### Livrables

1. politique officielle acquisition/normalisation/export.
2. traçabilité profil sur artefacts.
3. affichage UI des profils appliqués.

### Go/No-Go

1. plus de zone grise sur “quel profil s’applique quand”.

### Risques

1. migration de config projet existante.

### Mitigation

1. migration non destructive + fallback legacy.

---

## Itération 8 — Acquisition multi-source (subtitles inclus)

### Objectif

Rendre l’acquisition réellement agile (transcripts + subtitles API + subtitles scraping).

### Tickets

1. RF-030
2. RF-031
3. RF-032
4. RF-033
5. RF-034

### Livrables

1. modèle de capacités d’adapters.
2. OpenSubtitles intégré comme provider standard.
3. squelette subtitles scraping.
4. garde-fous réseau/toS.

### Go/No-Go

1. Pilotage propose des actions selon capacités source.
2. erreurs réseau/toS explicites et exploitables.

### Risques

1. maintenance adapters scraping.

### Mitigation

1. tests fixtures + registre source versionné.

---

## Itération 9 — Nettoyage final perf/observabilité

### Objectif

Finir la refonte avec rationalisation technique et gains de perf.

### Tickets

1. RF-043
2. RF-044
3. RF-050
4. RF-051
5. RF-052
6. RF-053
7. RF-054
8. RF-062

### Livrables

1. logs dans menu + panneau global.
2. exports unifiés.
3. écritures DB batchées.
4. optimisation indexation/align/KWIC.
5. migration SQL perf.

### Go/No-Go

1. UX allégée et stable.
2. gains de perf mesurés.

### Risques

1. régression subtile de perf sur petits corpus.

### Mitigation

1. benchmark comparatif petit/moyen/gros corpus.

## 5) Plan de tests par itération

### 5.1 Tests obligatoires à chaque merge

1. `pytest -q`
2. smoke test manuel minimal:
- ouvrir projet
- lancer 1 action workflow
- annuler
- reprendre
- exporter

### 5.2 Suites dédiées refonte

1. `tests/test_workflow_service.py`
2. `tests/test_scope_resolver.py`
3. `tests/test_episode_state_resolver.py`
4. `tests/test_job_controller.py`
5. `tests/test_refonte_ui_smoke.py` (si harness disponible)

### 5.3 Scénarios fonctionnels de validation

1. Web full pipeline:
- discover -> fetch -> normalize -> segment -> index -> align -> export

2. SRT-only:
- ajout épisodes -> import srt -> normalize piste -> align (si pivot dispo) -> concordance

3. Recoverability:
- injecter échec -> reprendre échecs -> succès final

## 6) Stratégie de données et migrations

### 6.1 Principes

1. migrations SQL additives et idempotentes.
2. compat lecture des anciennes configs.
3. aucun effacement destructif automatique.

### 6.2 Migrations prévues

1. `005_perf_indexes.sql` (RF-054).
2. migration config projet pour profils unifiés (RF-020/RF-031).

### 6.3 Rollback

1. conserver backup DB avant migration majeure.
2. rollback code via tag stable.
3. scripts de downgrade limités aux métadonnées non destructives.

## 7) Gouvernance d’exécution

### 7.1 Rituels

1. revue de conception courte au début de chaque itération.
2. démo de fin d’itération sur scénario réel.
3. mise à jour des docs backlog/plan à chaque clôture.

### 7.2 Critères de sortie globale de refonte

1. architecture centralisée en place (`WorkflowService`).
2. UI cible 4 onglets + logs menu.
3. politiques de profils claires et visibles.
4. acquisition multi-source active (API + scraping subtitles prêt à étendre).
5. frictions P0 toutes résolues.
6. tests et smoke complets verts.

## 8) Ordre recommandé compact

1. I0 baseline
2. I1 socle workflow
3. I2 fiabilité jobs/scope/force/reprise
4. I3 correctifs P0 données/exports
5. I4 Pilotage
6. I5 Inspecteur
7. I6 Validation & Annotation
8. I7 profils unifiés
9. I8 acquisition multi-source
10. I9 nettoyage perf/observabilité

## 9) Checklist de lancement immédiat (prochaine session)

1. Valider ce plan et geler RF-001..RF-016 comme lot “Phase 1 refonte”.
2. Créer l’arborescence `src/howimetyourcorpus/core/workflow/`.
3. Implémenter RF-002 + RF-003 + RF-005 en premier incrément.
4. Brancher une action pilote (`normalize`) via `WorkflowService`.
5. Poser tests de non-régression scope et état.
