# Plan Detaille - Refonte Workflow + UI/UX (sans application des correctifs)

Date: 2026-02-14  
Projet: HowIMetYourCorpus (HIMYC)  
Auteur: Audit technique + UX (base sur l'etat reel du code)

## 1) Objectif du document

Ce document sert de plan d'execution **tres detaille** pour clarifier le workflow, reduire les frictions UI/UX, et cadrer un refactor incremental sans casser le pipeline.

Il reprend:
- les constats de `DOC_REVIEW_UI_ERGONOMIE.md`,
- ce qui a deja ete implemente dans le refactor en cours,
- les decisions produit discutees (fusion d'onglets, logs via menu, separation Pilotage vs Inspecteur),
- une feuille de route ordonnee avec criteres de validation.

## 2) Etat actuel consolide (ce qui est deja vrai dans le code)

### 2.1 Changements deja effectifs

1. `Projet` + `Corpus` sont fusionnes dans `Pilotage`.
2. `Inspecteur` + `Sous-titres` sont fusionnes.
3. `Alignement` + `Personnages` sont fusionnes dans `Validation & Annotation`.
4. `Logs` est masque par defaut et accessible via menu `Outils > Journaux`.
5. `Corpus` est deja structure en 3 blocs fonctionnels: `Importer`, `Transformer/Indexer`, `Reprise`.
6. Le statut workflow affiche explicitement `Segmentes`.
7. Le diagnostic runtime acquisition (profil/rate/timeout/retries/backoff) est visible dans:
   - `Projet` (preview),
   - `Pilotage/Corpus`,
   - `Inspecteur`,
   - logs de lancement job.

### 2.2 Limites encore presentes

1. KWIC reste synchrone sur le thread UI (risque de freeze).
2. KWIC reste limite a 200 hits, sans pagination.
3. Double-clic KWIC ouvre l'episode, sans deep-link segment/cue.
4. Filtrage logs sans debounce, refresh total a chaque frappe.
5. Chargement tail logs lit tout le fichier avant de garder la fin.
6. Personnages reste en `QTableWidget` (item-based, peu scalable).
7. Propagation personnages prend implicitement le premier run d'alignement.
8. Certaines barres d'actions restent denses (surtout Alignement).

## 3) Positionnement workflow cible (vision claire)

## 3.1 Flux cible de reference

```text
[Pilotage / Projet]
  -> ouvrir/creer projet
  -> config source, profils, langues

[Pilotage / Corpus]
  Bloc 1 Importer
    -> decouvrir episodes / ajouter episodes / telecharger
  Bloc 2 Transformer + Indexer
    -> normaliser / segmenter / indexer
  Bloc 3 Reprise
    -> relancer erreurs / ouvrir episode en inspection

[Inspecteur]
  -> QA episode (RAW vs CLEAN, segments)
  -> import/edition/normalisation des pistes sous-titres

[Validation & Annotation]
  -> lancer et valider alignement
  -> assigner personnages
  -> propager personnages sur cibles

[Concordance]
  -> recherche corpus (episodes/segments/cues)
  -> export results

[Logs via menu]
  -> diagnostic transversal, copiable, persistant a la demande
```

### 3.2 Regle metier cle (deja discutee)

1. Les operations batch restent dans `Pilotage`.
2. `Inspecteur` sert a la QA locale episode et operations fines.
3. L'assignation personnages et la propagation restent apres l'alignement (dans `Validation & Annotation`).
4. Les profils d'acquisition concernent les etapes reseau.
5. Les profils de normalisation concernent transcript RAW->CLEAN et pistes SRT/VTT (pas les exports).

## 4) Revue UX tab par tab (etat + plan)

## 4.1 Pilotage (Projet + Corpus)

### But utilisateur
Piloter le workflow principal du projet de bout en bout.

### Entrees
- Dossier projet, source, URL, profils, langues.
- Scope action (courant/selection/saison/tout).
- Actions import/transform/index/reprise.

### Sorties
- Fichiers projet + artefacts episode.
- Etats DB (`new/fetched/normalized/segmented/indexed/error`).

### Feedback/controle
- Progression + cancel.
- Action recommandee + prochaine etape.
- Panneau erreurs relancables.

### Frictions restantes
- Densite de controles encore importante.
- Infos d'artefacts parfois textuelles, pas assez "action -> sortie".

### Priorites
- P0: barre de job globale transverse (visible quel que soit l'onglet).
- P1: renforcer panel "sortie attendue" au clic action.
- P2: badges/legende d'etats encore plus visuels.

## 4.2 Inspecteur (Transcript + Sous-titres)

### But utilisateur
Controle qualite local par episode + edition pistes.

### Entrees
- Episode courant unique.
- Actions transcript (normaliser, segmenter, exporter).
- Actions sous-titres (import/edit/save/normaliser piste).

### Sorties
- `clean.txt`, `transform_meta.json`, `segments`, pistes SRT/VTT, cues.

### Feedback/controle
- Tooltips prerequis.
- Etat busy propage depuis job global.

### Frictions restantes
- Lisibilite des actions avancees encore perfectible.
- Pas de panneau "ce bouton va ecrire X/Y".

### Priorites
- P0: bandeau "sorties de l'action" explicite avant execution.
- P1: menu secondaire pour actions avancees.
- P2: options de lecture QA (diff/wrap/mono) plus poussées.

## 4.3 Validation & Annotation (Alignement + Personnages)

### But utilisateur
Valider l'alignement puis annoter/propager les personnages.

### Entrees
- Episode, run, langue cible, decisions manuelles.
- Source assignation (segments/cues lang).

### Sorties
- Runs/liens d'alignement + exports.
- Assignations personnages + propagation.

### Feedback/controle
- Pre-requis alignement deja bien controles.
- Stats et exports disponibles.

### Frictions restantes
- Barre Alignement tres chargee.
- Personnages en table item-based.
- Propagation run implicite (`runs[0]`).

### Priorites
- P0: run actif explicite pour propagation (pas implicite).
- P1: migration Personnages vers model/view.
- P1: regrouper actions Alignement par finalite (Calcul/Validation/Export).

## 4.4 Concordance

### But utilisateur
Explorer vite le corpus et exporter.

### Entrees
- Terme, scope, kind/lang, saison/episode.

### Sorties
- Hits KWIC + exports.

### Feedback/controle
- Etat des boutons coherent avec DB/terme.

### Frictions restantes
- Requete synchrone UI.
- Pas de pagination.
- Navigation episode sans focus exact sur hit.

### Priorites
- P0: KWIC asynchrone (worker + cancel).
- P1: pagination/incremental loading.
- P2: deep-link inspecteur via `segment_id/cue_id`.

## 4.5 Logs

### But utilisateur
Diagnostic rapide et partageable.

### Entrees
- Presets, niveau, recherche.
- Actions copie, ouvrir episode, charger tail.

### Sorties
- Buffer live filtre.
- Rapport diagnostic copiable.

### Feedback/controle
- Compteur visible/total.

### Frictions restantes
- Non-persistant en vue workflow (masquage hors focus).
- Filtrage sans debounce.
- Tail fichier en lecture lineaire complete.

### Priorites
- P0: option "logs dockables/persistants" (ou mode pin).
- P1: debounce + refresh incremental.
- P2: vrai tail depuis fin de fichier.

## 5) Reponses aux questions produit deja tranchees

### 5.1 Projet et Corpus couples ensemble ?
Oui, c'est le bon choix et c'est deja en place (`Pilotage`).

### 5.2 Que peut-on fusionner en plus ?
Deja fusionne au bon niveau:
- `Inspecteur + Sous-titres`,
- `Alignement + Personnages`.

Eviter de tout refusionner dans un mega-onglet: on perdrait la separation mentale des etapes.

### 5.3 Logs en menu plutot qu'onglet fixe ?
Oui, mais avec condition:
- garder acces menu (deja fait),
- ajouter option d'affichage persistant quand debug intensif.

### 5.4 Pourquoi garder le batch hors Inspecteur ?
Parce que le batch est orchestration macro (scope large) et doit rester dans Pilotage.  
Inspecteur doit rester un atelier local episode.

### 5.5 Normalisation profils: a tout appliquer ?
Decision cible:
- Acquisition profile: reseau/scraping/API uniquement.
- Normalize profile: transcript + sous-titres importes (SRT/VTT), selon operation explicite.
- Formats binaires (Word/docx brut) doivent passer par un importeur/adaptateur explicite, pas par une normalisation implicite.

## 6) Backlog determinant (brainstorm transforme en epics)

## Epic A - Contexte de run explicite (P0)

Probleme: propagation personnages non deterministe (run implicite).  
Livrable: `RunContext` explicite visible/selectable + persiste par episode.  
Impact: fiabilite analytique, reproductibilite.

## Epic B - Job feedback global (P0)

Probleme: feedback long job encore concentre dans certaines zones.  
Livrable: barre globale (step en cours, progress, cancel, dernier echec, ouvrir logs).  
Impact: reduction des zones d'incertitude.

## Epic C - Concordance non bloquante (P0/P1)

Probleme: KWIC bloque UI + limite dure.  
Livrable: worker KWIC, cancel, pagination.  
Impact: fluidite, exploration corpus large.

## Epic D - Logs performants et exploitables (P1)

Probleme: refresh couteux + tail lineaire complet.  
Livrable: debounce, refresh incremental, tail reverse seek.  
Impact: confort debug + perf.

## Epic E - Personnages model/view (P1)

Probleme: `QTableWidget` ne scale pas.  
Livrable: `QAbstractTableModel` + delegates.  
Impact: maintenabilite, performance, testabilite.

## Epic F - Decouplage Pilotage (P2)

Probleme: logique de preconditions/scope encore epaisse dans tab UI.  
Livrable: service applicatif dedie (`controller`), UI plus declarative.  
Impact: architecture propre, tests unitaires plus faciles.

## 7) Plan d'execution recommande (ordre strict)

## Lot 0 - Baseline et garde-fous (prealable)

### Scope
- Figurer la baseline UX/perf avant nouveaux changements.

### Actions
1. Capturer temps reponse KWIC (petit vs gros corpus).
2. Mesurer latence filtre logs sur 5k lignes.
3. Lister flux manuels critiques (smoke workflow).

### Risque
Faible.

### Validation
- Baseline documentee et partagee.

## Lot 1 - Fiabilite workflow critique (P0)

### Scope
- Run actif explicite pour propagation + feedback job global.

### Actions
1. Introduire selection run explicite cote Personnages.
2. Refuser propagation sans run selectionne.
3. Ajouter feedback global transverse (si pas deja complet).

### Risque
Moyen (flux utilisateurs frequent).

### Validation
- Aucun cas de propagation sur mauvais run.
- Job visible et annulable depuis tout onglet.

## Lot 2 - Concordance asynchrone (P0/P1)

### Scope
- Worker KWIC + cancel + pagination.

### Actions
1. Worker dedie requete.
2. "Rechercher" -> async + spinner/etat.
3. "Charger plus" (offset/limit).

### Risque
Moyen.

### Validation
- Pas de freeze UI sur gros corpus.
- Resultats identiques au mode precedent a perimetre equivalent.

## Lot 3 - Logs performance (P1)

### Scope
- Debounce, incremental refresh, tail efficace.

### Actions
1. Debounce 150-250ms.
2. Raffraichir seulement differences filtrees.
3. Lire tail depuis fin fichier (seek reverse).

### Risque
Faible.

### Validation
- Filtre fluide sur 10k+ lignes.
- `load_file_tail` rapide sur fichier volumineux.

## Lot 4 - Personnages model/view (P1)

### Scope
- Remplacer tables item-based.

### Actions
1. Creer modeles table personnages + assignations.
2. Delegates pour colonnes editables/combos.
3. Conserver contrat I/O store/db identique.

### Risque
Moyen.

### Validation
- Parite fonctionnelle complete (charger/edit/save/propager).

## Lot 5 - Clarte visuelle et discoverabilite (P1/P2)

### Scope
- Lisibilite actions et sorties.

### Actions
1. Groupes d'actions plus stricts en Alignement.
2. Panneau "ce que l'action produit" dans zones critiques.
3. Acces direct "ouvrir dossier/fichier artefact".

### Risque
Faible a moyen (layout).

### Validation
- Reduction clics et erreurs de manipulation en parcours guide.

## Lot 6 - Decouplage architecture UI/core (P2)

### Scope
- Extraire logique corpus UI dense dans service.

### Actions
1. Introduire controller workflow corpus.
2. Deplacer preconditions/scope composition steps.
3. Garder UI purement presentation.

### Risque
Moyen.

### Validation
- Tests unitaires controller + non regression UI.

## 8) Matrice de tests (a executer a chaque lot)

## 8.1 Tests fonctionnels e2e manuels

1. Ouvrir/creer projet.
2. Decouvrir episodes puis telecharger.
3. Normaliser + segmenter + indexer.
4. Importer pistes EN + cible.
5. Lancer alignement, valider quelques liens.
6. Assigner personnages et propager.
7. Rechercher en Concordance et exporter.
8. Reprendre episodes en erreur.

## 8.2 Tests non-fonctionnels

1. UI reste responsive pendant jobs longs.
2. Cancellation fiable et etat post-annulation coherent.
3. Aucune reecriture involontaire RAW.
4. Pas de reprocessing inutile hors mode force.
5. Compatibilite macOS (vue episodes fallback table), Windows paths UTF-8.

## 8.3 Tests de regression cibles

1. Logs: presets/restauration et copie diagnostic.
2. Workflow advice: action recommandee coherent avec compteurs.
3. Concordance: equivalence des hits avant/apres async.
4. Personnages: identite des payloads sauvegardes.

## 9) KPI de succes (mesurables)

1. Temps de retour UI pendant KWIC > 500ms: passe de blocant a non-bloquant.
2. Latence filtre logs sur 5k lignes: < 200ms perceptif.
3. Taux erreurs user "mauvais run de propagation": vise 0.
4. Temps moyen pour workflow "ouvrir projet -> premier export KWIC": reduction mesurable.
5. Nombre de retours "je ne sais pas quoi faire ensuite": baisse nette (UX qualitative).

## 10) Risques et arbitrages

1. Ajouter trop de guidage peut surcharger visuellement.
   - Mitigation: progressive disclosure (details a la demande).
2. Async KWIC peut complexifier l'etat des controles.
   - Mitigation: machine d'etat simple (idle/running/cancelled/done/error).
3. Refactor Personnages peut introduire regressions d'edition.
   - Mitigation: parite stricte + tests de sauvegarde comparatifs.
4. Barre job globale peut dupliquer le feedback existant.
   - Mitigation: conserver source de verite unique, vues derivees.

## 11) Definition of Done (DoD) de la refonte

1. Workflow comprenable en 1 lecture de chaque onglet.
2. Aucune operation lourde ne fige l'interface.
3. Toutes les operations sensibles sont explicites sur leurs sorties.
4. Les etats workflow et prerequis sont coherents et visibles.
5. Les erreurs sont recuperables avec action suivante claire.
6. Les logs sont exploitables sans casser le flux utilisateur principal.
7. Les changements restent incrementaux, auditables, et sans rewrite complet.

## 12) Recommandation operative immediate

Ordre recommande pour la suite:
1. Lot 1 (Run explicite + feedback global),
2. Lot 2 (KWIC async/pagination),
3. Lot 3 (Logs perf),
4. Lot 4 (Personnages model/view),
5. Lot 5 (clarte visuelle),
6. Lot 6 (decouplage architecture).

Ce sequence maximise le ratio impact/risque et reduit vite les frictions majeures sans destabiliser le coeur pipeline.

