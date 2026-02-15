# Plan priorise - UI/UX Workflow (elements reviewed + ajouts)

Date: 2026-02-14  
Projet: HowIMetYourCorpus

## 1) But du plan

Consolider en un seul plan:
- ce qui est deja reviewe et valide dans `DOC_REVIEW_UI_ERGONOMIE.md` et `DOC_REFONTE_WORKFLOW_UI_DETAILLE.md`,
- ce qui manque pour une execution fiable (ownership, KPI instrumentes, rollback, accessibilite, CI).

Objectif: execution incrementale, risque maitrise, impact utilisateur rapide.

## 2) Regles de priorisation

- P0: fiabilite workflow et non-blocage UI.
- P1: performance quotidienne et qualite d'execution.
- P2: architecture et ergonomie avancee.

Ordre de passage:
1. impact utilisateur fort,
2. risque de regression faible a moyen,
3. dependances techniques minimales.

## 2.1 Etat implemente (deja livre dans la branche)

Statut confirme au commit `560c3a8` (et commits precedents de la meme serie):

1. Pilotage passe en layout 2 colonnes (Corpus a gauche, configuration a droite).
2. Ligne d'entete unifiee: configuration projet, aide workflow, etapes suivantes.
3. Blocs "Transformer/Indexer" et "Reprise-Erreurs" deplaces en colonne droite.
4. Colonne droite avec largeur de box adaptative lors du resize utilisateur (splitter).
5. Table Corpus agrandie (hauteur mini + expansion verticale prioritaire).
6. Suppression des chevauchements de labels/actions dans les blocs corpus.
7. Box Projet/Source simplifiee: retrait du detail runtime HTTP dans le formulaire.
8. Scrolls verticaux parasites supprimes sur panneau projet/colonne droite.
9. Stabilisation du mode compact projet (resume + onglets details + fix crash init).

Conclusion: la dette ergonomique "mac readability / overlap / pilotage framing" est en grande partie traitee.

## 3) Backlog consolide priorise

## 3.1 P0 (must-have, immediate)

1. Run de propagation explicite en Personnages (plus de `runs[0]` implicite).  
   Source reviewed: oui.  
   Ajout: persistance du dernier run selectionne par episode.

2. Barre de job globale transverse (etat + cancel + dernier echec + ouvrir logs).  
   Source reviewed: oui.  
   Ajout: contrat d'etat unique `idle/running/cancelling/done/error`.

3. Concordance async (worker) + cancel.  
   Source reviewed: oui.  
   Ajout: ordre deterministe des pages avant pagination.

4. Baseline metrique (avant/apres) pour KWIC et Logs.  
   Source reviewed: partiel.  
   Ajout: protocole de mesure outille.

## 3.2 P1 (high-value, short term)

5. Pagination KWIC (incrementale) avec tri stable.  
   Source reviewed: oui.  
   Ajout: specification technique page token/offset stable.

6. Logs: debounce, tail efficace (reverse seek), mode persistant (pin/dock).  
   Source reviewed: oui.  
   Ajout: palier progressif (debounce d'abord, incremental ensuite).

7. Migration Personnages vers model/view (`QAbstractTableModel` + delegates).  
   Source reviewed: oui.  
   Ajout: schema de tests de parite payload I/O.

8. Accessibilite desktop (clavier/focus/HDPI/contraste) avec checklist testable.  
   Source reviewed: non explicite.  
   Ajout: lot dedie.

9. Criteres d'acceptation lot-par-lot + gate CI (smoke UI minimal).  
   Source reviewed: partiel (DoD globale).  
   Ajout: acceptance locale et gating.

## 3.3 P2 (structurant, medium term)

10. Clarte visuelle avancee (actions/artefacts/progressive disclosure).  
    Source reviewed: oui.  
    Ajout: design tokens UI minimaux (spacing/hierarchie/cta).

11. Decouplage `tab_corpus` vers controller applicatif.  
    Source reviewed: oui.  
    Ajout: plan de migration en 2 etapes pour limiter regressions.

12. Gouvernance (ownership, RACI leger, release/rollback playbook).  
    Source reviewed: non.  
    Ajout: roles explicites par lot.

## 4) Plan d'execution (lots ordonnes)

## Lot -1 - Refonte ergonomique Pilotage mac (deja livre)

### Scope
- Recentrage de l'ecran sur le corpus.
- Recomposition visuelle de la colonne droite.
- Suppression des sources de scroll/chevauchement.

### Livre
1. Entete fusionnee (configuration/aide/etapes suivantes).
2. Split 2 colonnes et panneau projet retractable.
3. Deplacement des blocs secondaires a droite.
4. Largeur des box droite adaptative au resize splitter.
5. Table corpus agrandie et plus lisible.
6. Nettoyage Source/Serie (retrait runtime HTTP verbose).

### Resultat
- Lisibilite et densite d'information nettement ameliorees.
- Moins de friction de navigation dans Pilotage.
- Base UI stabilisee pour attaquer les P0 fonctionnels.

## Lot 0 - Cadrage et baseline (P0)

### Scope
- Mesurer l'etat actuel avant changements.
- Fixer ownership + criteres + rollback.

### Elements reviewed
- Baseline KWIC/logs est deja demandee dans le document detaille.

### Ajouts
1. Nommer les responsables par lot:
   - Dev owner
   - Reviewer technique
   - Validateur produit/UX
2. Definir format KPI:
   - metrique
   - methode de collecte
   - seuil cible
3. Definir rollback minimal par lot (flag/revert).

### Deliverables
- `BASELINE_UI_PERF.md`
- `MATRICE_OWNERSHIP_UI.md`
- `PLAYBOOK_ROLLBACK_UI.md`

Etat 2026-02-14:
- `BASELINE_UI_PERF.md` cree (avec mesures initiales + protocole)
- `MATRICE_OWNERSHIP_UI.md` cree
- `PLAYBOOK_ROLLBACK_UI.md` cree

### Acceptance criteria
- Baseline chiffree disponible pour:
  - KWIC petit corpus / gros corpus
  - filtre logs sur 5k lignes
- Chaque lot a owner + fallback de rollback ecrit.

## Lot 1 - Fiabilite critique workflow (P0)

### Scope
- Run explicite propagation.
- Barre de job globale.

### Elements reviewed
- Epic A + Epic B deja identifies.

### Ajouts
1. Etat global machine (`idle/running/cancelling/done/error`) partage par toutes vues.
2. Regle stricte: propagation impossible sans run selectionne.
3. Restauration etat: dernier run choisi par episode.

Etat 2026-02-14:
- Regle stricte run explicite: deja en place (propagation bloquee sans run).
- Restauration dernier run par episode: implementee (QSettings, par projet) dans `tab_personnages.py`.
- Contrat global d'etat machine transversal (`idle/running/cancelling/done/error`): implemente dans `ui_mainwindow.py`.

### Acceptance criteria
- Zero propagation sur mauvais run en test manuel cible.
- Job visible et annulable depuis chaque onglet principal.
- Etat UI coherent apres annulation.

### Rollback
- Feature flag UI `global_job_bar_enabled`.
- En cas d'incident, retour a feedback local actuel.

## Lot 2 - Concordance non bloquante (P0/P1)

### Scope
- Async KWIC + cancel + pagination v1.

### Elements reviewed
- Epic C valide.

### Ajouts
1. Tri stable impose (ex: `episode_id, position, segment_id/cue_id`) pour paging deterministe.
2. Palier:
   - v1: async + cancel + limite configurable
   - v2: "charger plus" stable
3. Telemetrie simple:
   - temps requete
   - nb hits
   - statut cancel/success/error

Etat 2026-02-14:
- Async + cancel: deja en place dans `tab_concordance.py` (worker/thread + annulation).
- Tri/paging deterministe: implemente dans `db_kwic.py` (ORDER BY explicite episodes/segments/cues).
- Tests de non-regression pagination stable: ajoutes dans `tests/test_db_kwic.py`.
- Telemetrie requete: implementee dans `tab_concordance.py` (log status/hits/elapsed + feedback ms).

### Acceptance criteria
- Pas de freeze perceptible pendant recherche longue.
- Equivalence fonctionnelle des hits sur meme perimetre qu'avant.
- Pagination sans doublon/manque entre pages.

### Rollback
- Flag `kwic_async_enabled`.
- Fallback execution synchrone historique.

## Lot 3 - Logs performance et continuite debug (P1)

### Scope
- Debounce + tail efficace + mode persistant.

### Elements reviewed
- Epic D valide.

### Ajouts
1. Ordre de mise en oeuvre pragmatique:
   - etape A: debounce + optimisation refresh global
   - etape B: refresh incremental
2. Mode "pin" logs (ne pas auto-masquer si active).
3. KPI:
   - latence filtre p95
   - temps de chargement tail sur gros fichier.

Etat 2026-02-14:
- Debounce filtre: deja en place.
- Tail reverse seek: deja en place.
- Optimisation refresh global: implementee (`setPlainText` en bloc au lieu d'append ligne par ligne).
- Ingestion incremental load tail (mode non-clear): implementee.
- Mode pin logs: deja en place.
- Baseline Lot 0 enrichie: metrique `logs_render_10k_ms` ajoutee.

### Acceptance criteria
- Filtre fluide sur 10k lignes.
- `load_file_tail` significativement plus rapide sur gros logs.
- Mode pin respecte lors des changements d'onglet.

### Rollback
- Flag `logs_incremental_refresh_enabled`.
- Fallback debounce only.

## Lot 4 - Personnages model/view (P1)

### Scope
- Remplacement QTableWidget par model/view.

### Elements reviewed
- Epic E valide.

### Ajouts
1. Test de parite I/O obligatoire:
   - `character_names.json`
   - `character_assignments.json`
2. Snapshot comparatif avant/apres sur jeu de donnees de reference.
3. Validation propagation inchangee (hors run explicite Lot 1).

Etat 2026-02-14:
- Etape 1 livree: grille Personnages migree vers `QTableView + CharacterNamesTableModel` (edition/add/remove/save).
- Etape 2 livree: table d'assignation migree vers `QTableView + CharacterAssignmentsTableModel + delegate combo`.
- Tests de base model/view ajoutes dans `tests/test_tab_personnages.py`.
- Parite I/O JSON (noms + assignations) verrouillee via `tests/test_project_store_propagation.py`.
- Chargement assignations optimise en remplissage batch (moins de freeze UI sur gros episodes).

### Acceptance criteria
- Parite fonctionnelle charge/edit/save/propager.
- Pas de regression sur payloads sauvegardes.

### Rollback
- Flag `personnages_model_view_enabled`.

## Lot 5 - Accessibilite + clarte visuelle (P1/P2)

### Scope
- Ergonomie de lecture et navigation clavier.

### Elements reviewed
- Clarte visuelle deja ciblee (badges/sorties/action).

### Ajouts
1. Raccourcis:
   - `Ctrl+F` recherche (Concordance/Logs)
   - `Ctrl+L` ouvrir logs
2. Focus order explicite sur ecrans principaux.
3. Validation HDPI Windows (125/150/200%).
4. Checklist contraste/etats des controles.

Etat 2026-02-14:
- Raccourcis globaux implementes:
  - `Ctrl/Cmd+F`: focus recherche (Concordance par defaut, Logs si onglet Logs actif).
  - `Ctrl/Cmd+L`: ouverture directe du panneau Logs.
- Methodes de focus dediees ajoutees dans `tab_concordance.py` et `tab_logs.py`.
- Checklist accessibilite testable ajoutee: `CHECKLIST_ACCESSIBILITE_UI.md`.
- Focus order explicite ajoute sur les vues critiques (Pilotage, Projet, Corpus, Validation/Alignement/Personnages).

### Acceptance criteria
- Parcours complet possible au clavier sur flux critique.
- Aucune zone cassée en HDPI.

### Rollback
- Changements purement UI, rollback commit simple.

## Lot 6 - Decouplage architecture (P2)

### Scope
- Extraire logique `tab_corpus` vers controller.

### Elements reviewed
- Epic F valide.

### Ajouts
1. Migration en 2 temps:
   - phase A: extraire fonctions pures (scope/prerequis/step building)
   - phase B: brancher controller unique
2. Couverture tests unitaires controller avant bascule.

Etat 2026-02-14:
- Phase A demarree: fonctions pures de scope extraites vers `app/corpus_scope.py`.
- `tab_corpus.py` recable sur ces fonctions (URL/source/raw/clean/runnable + cache capabilities).
- Resolution scope mode/ids (`current/selection/season/all`) extraite en fonction pure.
- Resolution profile par episode (priorite episode > source > batch) extraite en fonction pure.
- Couverture dediee ajoutee: `tests/test_corpus_scope.py`.
- Phase B demarree: `CorpusWorkflowController` introduit pour centraliser build/run des actions workflow.
- `tab_corpus.py` delegue build/execution de steps au controller.
- Composition des plans multi-etapes (`Tout faire`, `Segmenter+Indexer`) deplacee dans le controller.
- Couverture dediee ajoutee: `tests/test_corpus_controller.py`.

### Acceptance criteria
- UI conserve le meme comportement observable.
- Complexite reduite dans `tab_corpus.py`.

### Rollback
- Bascule par integration progressive (PRs petits), revert par phase.

## 5) Matrice ownership (template a remplir)

| Lot | Dev owner | Reviewer tech | Validateur UX/Produit | Statut |
|---|---|---|---|---|
| Lot -1 | hsmy + codex | TBD | TBD | Fait |
| Lot 0 | hsmy + codex | TBD | TBD | En cours |
| Lot 1 | TBD | TBD | TBD | A faire |
| Lot 2 | TBD | TBD | TBD | A faire |
| Lot 3 | TBD | TBD | TBD | A faire |
| Lot 4 | TBD | TBD | TBD | En cours |
| Lot 5 | TBD | TBD | TBD | En cours |
| Lot 6 | TBD | TBD | TBD | En cours |

## 6) KPI instrumentes (definitifs)

1. KWIC responsiveness:
   - Mesure: temps entre clic Rechercher et retour controle UI.
   - Cible: pas de blocage perceptible, p95 < 200 ms pour interactions UI.
2. KWIC throughput:
   - Mesure: temps de completion requete petit/gros corpus.
   - Cible: tendance a la baisse vs baseline.
3. Logs filter latency:
   - Mesure: latence p95 filtre texte sur 5k/10k lignes.
   - Cible: p95 < 200 ms perceptif.
4. Propagation safety:
   - Mesure: nb cas "propagation run non voulu".
   - Cible: 0.
5. Workflow efficiency:
   - Mesure: temps median "ouvrir projet -> premier export KWIC".
   - Cible: reduction vs baseline.

## 7) Definition of Done consolidee (plan)

1. Aucun lot P0 ne degrade l'auditabilite RAW/CLEAN/SRT/ALIGN.
2. Les actions longues ne bloquent plus l'interface.
3. Les sorties sensibles sont explicites avant execution.
4. Les prerequis et transitions d'etat sont visibles et coherents.
5. Les erreurs ont une action de recuperation claire.
6. Chaque lot a:
   - acceptance criteria passes,
   - rollback documente,
   - validation owner/reviewer effectuee.

## 8) Recommandation immediate

Execution conseillee:
1. Valider visuellement Lot -1 sur 2 resolutions mac (13" et ecran large),
2. Lot 0 (cadrage+baseline),
3. Lot 1 (fiabilite critique),
4. Lot 2 (KWIC async),
5. Lot 3 (logs perf),
6. Lot 4 (personnages model/view),
7. Lot 5 (accessibilite+clarte),
8. Lot 6 (decouplage).

C'est le meilleur ratio impact/risque pour reduire les frictions majeures sans destabiliser le pipeline coeur.
