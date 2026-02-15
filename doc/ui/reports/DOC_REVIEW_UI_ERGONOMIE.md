# Revue UI/UX Desktop - HowIMetYourCorpus (PySide6)

Date: 14 fevrier 2026

## 1) Resume executif

- L'architecture globale UI est saine: bootstrap clair, `MainWindow` orchestratrice, workers asynchrones, et usage partiel correct du pattern model/view Qt.
- Le point critique ergonomique est la surcharge des barres d'actions horizontales (Pilotage, Inspecteur, Alignement), qui degrade la lisibilite et la priorisation des actions.
- La priorite metier "clarte des sorties par onglet" est partiellement couverte: les artefacts sont reels et auditables, mais pas toujours explicitement annonces au moment de l'action.
- Les transitions d'etat `new/fetched/normalized/indexed/error` sont visibles dans Pilotage, mais `segmented` et la qualite d'alignement restent peu explicites pour l'utilisateur.
- Le flux "quoi faire ensuite" est bien engage via `WorkflowAdvice`, mais la guidance est surtout textuelle et insuffisamment hierarchisee visuellement.
- Le feedback long job est robuste dans Pilotage (progression/cancel), mais moins uniformement visible lorsque les actions partent d'autres onglets.
- La reprise sur erreur est bonne dans `Corpus` (liste + relance ciblee), plus faible dans les onglets analytiques (Concordance/Validation) ou le retry est peu contextualise.
- Le panneau Logs est riche fonctionnellement, mais son mode "onglet masque par defaut" reduit la continuite de diagnostic pendant les allers-retours de workflow.
- Plusieurs chemins restent synchrones en thread UI (KWIC, filtrage logs, lecture tail fichier, certaines tables item-based), avec risque de latence sur corpus volumineux.
- `tab_corpus.py` concentre trop de responsabilites (UI + orchestration + preconditions + construction de steps), ce qui freine la maintenabilite et les tests unitaires.
- L'accessibilite clavier est insuffisante (peu de raccourcis globaux, ordre de focus non explicite, peu d'indices non visuels).
- Quick wins recommandes: barre de job globale multi-onglets, debounce logs, raccourcis recherche, clarification "entrees/sorties" par zone.

## 2) Perimetre et methodologie d'inspection

### 2.1 Entree application et orchestration

- Bootstrap: `launch_himyc.py`, `src/howimetyourcorpus/app/main.py`
- Fenetre principale, creation onglets, wiring jobs: `src/howimetyourcorpus/app/ui_mainwindow.py`
- Worker pipeline: `src/howimetyourcorpus/app/workers.py`

### 2.2 UI inspectee

- Onglets principaux:
  - `src/howimetyourcorpus/app/tabs/tab_pilotage.py`
  - `src/howimetyourcorpus/app/tabs/tab_projet.py`
  - `src/howimetyourcorpus/app/tabs/tab_corpus.py`
  - `src/howimetyourcorpus/app/tabs/tab_inspecteur_sous_titres.py`
  - `src/howimetyourcorpus/app/tabs/tab_inspecteur.py`
  - `src/howimetyourcorpus/app/tabs/tab_sous_titres.py`
  - `src/howimetyourcorpus/app/tabs/tab_validation_annotation.py`
  - `src/howimetyourcorpus/app/tabs/tab_alignement.py`
  - `src/howimetyourcorpus/app/tabs/tab_personnages.py`
  - `src/howimetyourcorpus/app/tabs/tab_concordance.py`
  - `src/howimetyourcorpus/app/tabs/tab_logs.py`

- Modeles Qt:
  - `src/howimetyourcorpus/app/models_qt.py`

- Dialogues supports:
  - `src/howimetyourcorpus/app/dialogs/profiles.py`
  - `src/howimetyourcorpus/app/dialogs/subtitle_batch_import.py`
  - `src/howimetyourcorpus/app/dialogs/opensubtitles_download.py`

### 2.3 Trace des sorties reelles (fichiers + DB)

- Steps pipeline:
  - `src/howimetyourcorpus/core/pipeline/tasks.py`
  - `src/howimetyourcorpus/core/pipeline/runner.py`
- Persistences projet:
  - `src/howimetyourcorpus/core/storage/project_store.py`
- DB et requetes:
  - `src/howimetyourcorpus/core/storage/db.py`
  - `src/howimetyourcorpus/core/storage/db_kwic.py`
  - `src/howimetyourcorpus/core/storage/db_align.py`
  - `src/howimetyourcorpus/core/storage/migrations/*.sql`
- Regles workflow:
  - `src/howimetyourcorpus/app/workflow_status.py`
  - `src/howimetyourcorpus/app/workflow_advice.py`
  - `src/howimetyourcorpus/core/workflow/*`

## 3) Cartographie UI

### 3.1 Structure des fenetres/onglets/widgets

- `MainWindow`:
  - Onglet 0: `Pilotage` (fusion Projet + Corpus)
  - Onglet 1: `Inspecteur` (fusion Transcript + Sous-titres)
  - Onglet 2: `Validation & Annotation` (fusion Alignement + Personnages)
  - Onglet 3: `Concordance`
  - Onglet 4: `Logs` (masque par defaut, ouvert via menu Outils)

### 3.2 Parcours utilisateur (creation projet -> KWIC)

1. Ouvrir/creer projet dans `Pilotage > Projet` (ecrit `config.toml`).
2. Decouvrir episodes (`series_index.json`, episodes DB en `new`).
3. Telecharger transcripts (`page.html`, `raw.txt`, statut `fetched`).
4. Normaliser (`clean.txt`, `transform_meta.json`, statut `normalized`).
5. Segmenter + indexer (`segments.jsonl`, tables `segments`/FTS, statut `indexed`).
6. Importer/normaliser sous-titres (`episodes/<id>/subs/*`, `subtitle_tracks`, `subtitle_cues`).
7. Aligner (`align_runs`, `align_links`, audit `episodes/<id>/align/*.jsonl` + report JSON).
8. Rechercher en `Concordance` (documents/segments/cues) et exporter.

## 4) Revue onglet par onglet

## 4.1 Pilotage (Projet + Corpus)

### Objectif utilisateur

Configurer le projet et piloter le flux batch RAW -> CLEAN -> SEGMENTS -> INDEX, avec reprise d'erreurs.

### Entrees

- Dossier projet, source, URL serie, profils acquisition/normalisation, langues.
- Filtres saison/statut, scope action, selection/cochage episodes.
- Actions decouvrir/importer/telecharger/normaliser/segmenter/indexer/tout faire/exporter.

### Sorties

- Fichiers: `config.toml`, `series_index.json`, `languages.json`.
- Fichiers episodes: `page.html`, `raw.txt`, `clean.txt`, `transform_meta.json`, `segments.jsonl`.
- DB: `episodes.status`, `documents` + FTS, `segments` + FTS.
- Exports corpus (TXT/CSV/JSON/JSONL/DOCX selon mode).

### Feedback & controle

- Progress bar, status message, "prochaine action", CTA recommande.
- Verrouillage controls pendant job + bouton annuler.
- Panneau erreurs avec relance ciblee/globale + ouverture Inspecteur.

### Problemes ergonomie visuelle

- Densite elevee des actions sur lignes horizontales longues.
- CTA principal pas assez saillant face aux actions secondaires.
- Informations d'etat importantes presentes mais textuelles et dispersees.

### Propositions

- P0: panneau job global visible dans toute l'app.
  - Pourquoi: supprimer les zones d'incertitude hors onglet Pilotage.
  - Impact: meilleur controle des longs traitements, moins de confusion.
- P1: re-decoupage visuel en 3 zones strictes (Importer / Transformer / Reprise).
  - Pourquoi: clarifier le chemin d'action prioritaire.
  - Impact: reduction du temps de decision et du risque de mauvaise action.
- P2: badges d'etat normalises + legende persistante.
  - Pourquoi: rendre les transitions d'etat evidentes.
  - Impact: meilleure lisibilite operationnelle et auditabilite.

## 4.2 Inspecteur (Transcript + Sous-titres)

### Objectif utilisateur

Qualite locale par episode: comparer RAW/CLEAN, lancer normalisation/segmentation locale, gerer pistes SRT/VTT.

### Entrees

- Episode courant (selecteur partage).
- Cote transcript: vue episode/segments, profil, actions normaliser/segmenter/export.
- Cote sous-titres: langue, import unitaire/masse/OpenSubtitles, edition/sauvegarde, normalisation piste.

### Sorties

- Transcript: `clean.txt`, `transform_meta.json`, `notes.txt`, profil prefere par episode.
- Sous-titres: `episodes/<id>/subs/<lang>.srt|vtt`, `<lang>_cues.jsonl`, `<lang>_normalize_meta.json`.
- DB: tracks/cues importees, `text_clean` cues maj, align runs supprimes en cas de suppression piste.
- Exports: segments (TXT/CSV/TSV/DOCX), SRT final.

### Feedback & controle

- Tooltips prerequis dynamiques (RAW/CLEAN/segments).
- Meta de normalisation piste visible.
- Desactivation pendant job global.

### Problemes ergonomie visuelle

- Top bars trop chargees (actions frequentes + avancees melangees).
- Pas de rappel court "ce que l'action va produire" au clic.
- Lecture texte orientee brute, sans options d'aide (monospace/wrap/diff cues).

### Propositions

- P0: bandeau "sorties de l'action" avant execution + bouton ouvrir dossier episode.
  - Pourquoi: lier instantanement action et artefacts.
  - Impact: moins d'ambiguite sur l'effet des actions.
- P1: regrouper actions avancees dans un menu secondaire.
  - Pourquoi: reduire la charge visuelle.
  - Impact: parcours plus rapide pour actions courantes.
- P2: options de lecture QA (wrap, monospace, vue diff RAW/CLEAN).
  - Pourquoi: faciliter la relecture linguistique.
  - Impact: gains de confort et de precision.

## 4.3 Validation & Annotation (Alignement + Personnages)

### Objectif utilisateur

Executer/valider l'alignement puis annoter et propager les personnages.

### Entrees

- Alignement: episode, run, langue cible, mode similarite, filtres de statut.
- Annotation: episode, source (segments/cues langue), assignations source -> personnage.

### Sorties

- DB alignement: `align_runs`, `align_links`, statuts `auto/accepted/rejected`.
- Fichiers audit alignement: `episodes/<id>/align/*.jsonl`, `*_report.json`.
- Exports alignement/parallele/rapport HTML.
- Personnages: `character_names.json`, `character_assignments.json`, propagation vers segments/cues + reecriture SRT.

### Feedback & controle

- Verification prerequis avant "Lancer alignement".
- Menu contextuel validation manuelle des liens.
- Stats et export rapport.

### Problemes ergonomie visuelle

- Barre Alignement tres dense; CTA principal noye.
- Personnages utilise `QTableWidget` avec widgets cellule, peu scalable.
- Propagation choisit implicitement le premier run, sans selection explicite du run source.

### Propositions

- P0: bloc "Run actif" + selection explicite du run pour propagation.
  - Pourquoi: eviter les propagations involontaires sur mauvais run.
  - Impact: fiabilite analytique.
- P1: migration assignations vers model/view (`QAbstractTableModel` + delegate).
  - Pourquoi: performance et maintenabilite.
  - Impact: meilleure tenue sur gros volumes.
- P2: separation visuelle des actions par finalite (Calcul/Validation/Export).
  - Pourquoi: clarifier les intentions utilisateur.
  - Impact: diminution des erreurs de manipulation.

## 4.4 Concordance

### Objectif utilisateur

Explorer rapidement le corpus via KWIC (documents/segments/cues), filtrer et exporter.

### Entrees

- Terme de recherche, scope, filtres kind/langue, saison/episode.

### Sorties

- Table de hits KWIC.
- Exports CSV/TSV/JSON/JSONL/DOCX.
- Navigation vers Inspecteur sur double-clic.

### Feedback & controle

- Etats actifs/inactifs des controles selon DB/terme/resultats.

### Problemes ergonomie visuelle et interaction

- Requete KWIC synchrone en thread UI.
- Limite dure a 200 hits sans pagination.
- Navigation episode sans positionnement precis sur segment/cue hit.

### Propositions

- P0: execution KWIC en worker + indicateur de progression + annulation.
  - Pourquoi: eviter freeze UI.
  - Impact: fluidite sur gros corpus.
- P1: pagination/incremental loading.
  - Pourquoi: mieux gerer forte cardinalite.
  - Impact: exploration plus complete.
- P2: deep-link inspecteur via `segment_id`/`cue_id`.
  - Pourquoi: reduire les clics de diagnostic.
  - Impact: meilleure efficacite QA.

## 4.5 Logs

### Objectif utilisateur

Diagnostiquer les executions, filtrer rapidement, partager un contexte utile.

### Entrees

- Presets, niveau min, requete texte.
- Actions copier ligne/episode/diagnostic, charger tail, ouvrir fichier.

### Sorties

- Tampon live filtre.
- Rapport diagnostic copiable.
- Etats filtres/presets persistants (`QSettings`).

### Feedback & controle

- Compteur visible/total.
- Ouverture episode depuis pattern `SxxExx`.

### Problemes ergonomie visuelle et performance

- Onglet masque automatiquement hors focus, friction pour debug continu.
- Filtrage reconstruit toute la vue sans debounce.
- Chargement tail lit le fichier entier pour obtenir la fin.

### Propositions

- P0: logs dockables/persistants (au lieu d'onglet temporaire uniquement).
  - Pourquoi: conserver le contexte d'erreur pendant navigation.
  - Impact: meilleure recuperation d'incidents.
- P1: debounce filtre + refresh incremental.
  - Pourquoi: lisser l'UI sur buffers volumineux.
  - Impact: reactivite accrue.
- P2: vraie lecture tail depuis fin fichier + export des lignes filtrees.
  - Pourquoi: eviter cout lineaire sur gros logs.
  - Impact: diagnostic plus rapide.

## 5) Checklist UI/UX (evaluation explicite)

- Clear primary action per tab: partiellement atteint, surtout degrade dans Alignement/Inspecteur (densite boutons).
- Visible state & next step: bon dans Pilotage (`WorkflowAdvice`), moins visible ailleurs.
- Empty states helpful: globalement bon (messages precondition + next step).
- Error states actionable: tres bon dans Pilotage, moyen dans Concordance/Validation.
- Long tasks: progression + cancel presents, mais pas uniformement visibles sur tous onglets.
- Terminologie consistente: globalement bonne, quelques melanges FR/EN (`scope`, `kind`, `run`).
- Button placement and spacing: coherence moyenne; surcharge horizontale recurrente.
- Text inspector ergonomics: base fonctionnelle mais manque d'options de lecture QA.
- Concordance speed and density: model/view OK, execution synchrone a ameliorer.
- Logs search/filter/copy/export: riche fonctionnellement, optimisation perf et persistance UX attendues.

## 6) Performance UI (constats et recommandations)

### 6.1 Zones de risque

- KWIC synchrone (thread UI).
- Filtrage logs full refresh a chaque frappe.
- Lecture tail fichier lineaire sur tout le fichier.
- Tables Personnages item-based (QTableWidget + widgets cellule).

### 6.2 Recommandations

- Generaliser model/view:
  - Maintenir `QAbstractTableModel` + `QSortFilterProxyModel` comme standard.
  - Migrer Personnages/assignations vers model + delegate.
- KWIC:
  - Worker dedie + pagination ("charger plus").
  - Affichage incrementiel des hits.
- Logs:
  - Debounce 150-250ms.
  - Tail depuis fin de fichier.
  - Eventuellement virtualisation/recyclage de rendu.
- Refresh post-job:
  - Eviter le "refresh global complet" systematique.
  - Rafraichir uniquement les sous-vues impactees par les steps executes.

## 7) Maintenabilite UI

### 7.1 Frontieres de modules

- `MainWindow` doit rester orchestratrice, pas conteneur de regles metier.
- Extraire la logique de scope/preconditions/steps de `tab_corpus.py` vers un service d'application UI.

### 7.2 Composants reutilisables a creer

- `EpisodeSelectorWidget` (label + combo + preservation selection).
- `JobFeedbackPanel` (progression, annulation, dernier echec, ouvrir logs).
- `WorkflowStatusBadgeRow` (etats corpus normalises).
- `ArtifactActionsWidget` (ouvrir dossier, ouvrir fichier, copier chemin).

### 7.3 Hygiene signals/dependances

- Favoriser signaux explicites plutot que callbacks lambda transverses.
- Eviter les appels implicites du parent depuis dialogues (couplage cache).
- Uniformiser la resolution store/db/config via helpers partages.

### 7.4 Testabilite

- Ajouter tests UI (ex: `pytest-qt`) sur parcours critiques:
  - creation projet
  - enchainement batch
  - reprise erreurs
  - alignement + validation manuelle
  - recherche KWIC + export
  - diagnostic logs.

## 8) Plan de patchs incremental

### Patch 1 - Job feedback global (P0)

- Scope: progression/cancel/etat erreur visibles quel que soit l'onglet.
- Fichiers: `ui_mainwindow.py` + nouveau widget `app/widgets/job_feedback_bar.py`.
- Risque: faible.
- Validation: jobs lances depuis Pilotage/Inspecteur/Validation affichent le meme controle global.

### Patch 2 - Rationalisation visuelle Pilotage (P1)

- Scope: structurer `Corpus` en 3 sections fonctionnelles, CTA principal mis en evidence.
- Fichiers: `tab_corpus.py`.
- Risque: moyen (changement layout).
- Validation: aucun flux cassé, baisse du nombre de clics pour actions frequentes.

### Patch 3 - Etats workflow explicites (P1)

- Scope: badges d'etat standardises et legende persistante.
- Fichiers: `models_qt.py`, `tab_corpus.py`, `workflow_status.py`.
- Risque: faible.
- Validation: coherences etat colonne vs compteurs vs filtres.

### Patch 4 - Concordance asynchrone + pagination (P0/P1)

- Scope: worker KWIC, annulation, "charger plus".
- Fichiers: `tab_concordance.py`, nouveau `workers_kwic.py`, `core/storage/db.py`.
- Risque: moyen.
- Validation: pas de freeze UI sur corpus volumineux.

### Patch 5 - Optimisations Logs (P1)

- Scope: debounce filtres, tail efficace, persistance de visibilite.
- Fichiers: `tab_logs.py`, `ui_mainwindow.py`.
- Risque: faible.
- Validation: fluidite sur 10k+ lignes, comportement stable des presets.

### Patch 6 - Refactor Personnages model/view (P1)

- Scope: remplacer `QTableWidget` par modele + delegate.
- Fichiers: `tab_personnages.py`, nouveau `models_personnages_qt.py`.
- Risque: moyen.
- Validation: chargement/edition/sauvegarde/propagation identiques fonctionnellement.

### Patch 7 - Accessibilite clavier (P1)

- Scope: raccourcis (`Ctrl+F`, `Ctrl+L`, etc.), focus order explicite.
- Fichiers: `ui_mainwindow.py`, `tab_concordance.py`, `tab_logs.py`.
- Risque: faible.
- Validation: parcours clavier complet sans souris sur scenarios principaux.

### Patch 8 - Decouplage logique Corpus (P2)

- Scope: extraire preconditions/scope/actions de `tab_corpus.py` vers service dedie.
- Fichiers: `tab_corpus.py`, nouveau `app/services/corpus_workflow_controller.py`.
- Risque: moyen.
- Validation: tests unitaires du service + non regression UI.

## 9) Notes de compatibilite Windows

- Conserver les garde-fous deja en place sur IDs de fichiers (sanitization episode_id, run_id sans `:` pour audit alignement).
- Garder les boites de dialogue natives et chemins UTF-8.
- Verifier les tailles minimales/focus sur ecrans HDPI (100%-150%-200%).
- Eviter d'ajouter des dependances lourdes non Qt-native pour les ajustements UX.

## 10) Conclusion operative

L'application est deja solide sur les fondamentaux pipeline + persistance + audit, mais la prochaine valeur UX vient de trois chantiers prioritaires:

1. rendre le feedback long job global et omnipresent,
2. reduire la densite visuelle des zones d'action,
3. enlever les points de blocage UI synchrones (KWIC/logs) pour garantir une experience fluide a l'echelle.

Ces evolutions peuvent etre livrees de facon incrementale sans toucher a la logique coeur du pipeline.

