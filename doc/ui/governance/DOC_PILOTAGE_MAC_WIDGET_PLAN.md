# Plan Pilotage macOS - Brainstorming, evaluation, pour/contre, action

## 1) Contexte et cible

Ce document propose une refonte incrementale de l'onglet `Pilotage` sur macOS, sans re-ecriture majeure.
Objectif: rendre le flux "projet -> import -> transformation/index -> reprise erreurs -> passage onglets suivants" plus lisible, plus rapide, et plus robuste.

Base code inspectee:
- `src/howimetyourcorpus/app/tabs/tab_pilotage.py:32`
- `src/howimetyourcorpus/app/tabs/tab_pilotage.py:68`
- `src/howimetyourcorpus/app/tabs/tab_projet.py:75`
- `src/howimetyourcorpus/app/tabs/tab_corpus.py:116`
- `src/howimetyourcorpus/app/tabs/tab_corpus.py:158`
- `src/howimetyourcorpus/app/tabs/tab_corpus.py:194`
- `src/howimetyourcorpus/app/tabs/tab_corpus.py:231`
- `src/howimetyourcorpus/app/tabs/tab_corpus.py:295`
- `src/howimetyourcorpus/app/tabs/tab_corpus.py:333`
- `src/howimetyourcorpus/app/tabs/tab_corpus.py:439`
- `src/howimetyourcorpus/app/ui_mainwindow.py:124`
- `src/howimetyourcorpus/app/ui_mainwindow.py:616`

## 2) Evaluation rapide de l'etat actuel

Points forts:
- Le workflow est complet dans un seul onglet (projet + corpus), ce qui reduit les allers-retours.
- Les etats metier existent et sont visibles (`NEW/FETCHED/NORMALIZED/INDEXED/ERROR`) via la table et le resume workflow.
- Les actions sont bien protegees par preconditions et tooltips explicatifs.
- macOS est traite explicitement via `QTableView` (evite les crashes `QTreeView` observes).
- Un feedback job global existe deja (barre de progression + annulation + logs).

Points faibles (ergonomie mac screenshot + code):
- Trop de texte d'aide permanent en haut + en bas, qui ecrase la zone action utile.
- Hiérarchie visuelle floue: beaucoup de boutons de meme poids, CTA principal peu evident.
- Densite horizontale elevee: risque de wrapping brutal et cibles de clic petites sur petits ecrans.
- Le scope est puissant mais cognitivement lourd (saison/statut/scope/selection/coches) sans "resume action" immediat.
- Les etats vides sont peu pedagogiques dans la table episodes (pas de placeholder "quoi faire maintenant").
- Progression locale + globale coexistantes, mais la relation entre les deux n'est pas explicite.

## 3) Brainstorming d'architectures (pour/contre)

### Option A - "Surgery" minimale (recommandee)
Principe: conserver la structure actuelle, mais clarifier visuellement et reduire la charge cognitive.

Pour:
- Faible risque technique.
- Compatible avec le wiring existant (`MainWindow` + workers).
- Gain UX rapide sans casser les habitudes.

Contre:
- Ne change pas radicalement l'architecture interactionnelle.
- Certaines limitations de densite restent structurelles.

### Option B - Stepper vertical (Import -> Transformer -> Reprise)
Principe: transformer les 3 blocs en etapes verticales explicites avec etat de completion.

Pour:
- Clarte pedagogique forte pour nouveaux utilisateurs.
- Rend explicite "ce qu'il faut faire ensuite".

Contre:
- Refacto moyenne des layouts et des signaux.
- Peut augmenter la hauteur scrollee si mal maitrise.

### Option C - Mode "Assistant" (wizard)
Principe: n'afficher qu'une etape a la fois avec navigation "Suivant".

Pour:
- Tres guidant.
- Limite fortement le bruit visuel.

Contre:
- Mauvais fit pour usage expert/recherche (besoin de sauts rapides).
- Risque de frustration pour les utilisateurs avances.

### Option D - Dashboard cartes KPI + actions contextuelles
Principe: cartes de statut en haut, actions contextuelles en dessous.

Pour:
- Lecture rapide de l'etat corpus.
- Bon pour monitoring.

Contre:
- Effort UI plus eleve.
- Plus de composants custom a maintenir.

Decision proposee: Option A maintenant, avec un "A+" qui introduit des briques de Option B (etat/next-step plus explicites) sans gros chantier.

## 4) Proposition concrete widget par widget (avant/apres)

### 4.1 Entete Pilotage (helper + politique + "Etapes suivantes")
Code actuel:
- `src/howimetyourcorpus/app/tabs/tab_pilotage.py:32`
- `src/howimetyourcorpus/app/tabs/tab_pilotage.py:39`
- `src/howimetyourcorpus/app/tabs/tab_pilotage.py:49`

Avant:
- Deux longs paragraphes toujours visibles.
- Ligne "Etapes suivantes" utile mais visuellement au meme niveau que le reste.

Apres:
- Transformer les 2 paragraphes en panneau repliable "Aide workflow" (ferme par defaut apres premiere utilisation).
- Garder visible une seule ligne courte: "Etat: Projet ouvert ? Episodes decouverts ?".
- Conserver "Etapes suivantes" mais styliser en navigation secondaire discretes.

Pourquoi:
- Ergonomie: reduit le bruit et remonte les controles utiles au-dessus de la ligne de flottaison.
- Efficacite: moins de scroll avant action.
- Maintenabilite: simple (toggle de visibilite, pas de logique metier).

Risque:
- Faible.

### 4.2 Splitter Projet/Corpus
Code actuel:
- `src/howimetyourcorpus/app/tabs/tab_pilotage.py:68`
- `src/howimetyourcorpus/app/tabs/tab_pilotage.py:73`
- `src/howimetyourcorpus/app/tabs/tab_pilotage.py:77`

Avant:
- Split vertical persistant, tailles initiales fixes.
- Possibilite de retrouver une taille peu ergonomique selon historique utilisateur.

Apres:
- Garder le splitter, mais imposer un `minimumHeight` sur la zone Corpus et une borne haute sur Projet.
- Ajouter action "Reinitialiser la mise en page" dans menu Outils (remet tailles par defaut).

Pourquoi:
- Ergonomie: evite un ecran "mange" par Projet.
- Maintenabilite: comportement deterministe, moins de tickets "UI cassée".

Risque:
- Faible.

### 4.3 Section Projet
Code actuel:
- `src/howimetyourcorpus/app/tabs/tab_projet.py:75`
- `src/howimetyourcorpus/app/tabs/tab_projet.py:103`
- `src/howimetyourcorpus/app/tabs/tab_projet.py:148`

Avant:
- Informations completes mais nombreuses (source, profil acquisition, normalisation, langues).
- "Aller a la section Corpus" existe, bien vu, mais peu mis en valeur.

Apres:
- Resumer la section Projet en mode "compact" une fois projet ouvert:
  - chemin projet
  - source
  - profil normalisation
  - bouton "Modifier" pour reouvrir details
- Mettre "Aller a la section Corpus" en bouton principal de cette section quand projet valide.

Pourquoi:
- Efficacite: l'utilisateur recurrent n'a pas besoin de revoir tout le formulaire.
- Ergonomie: reduction densite verticale.

Risque:
- Faible a moyen (ajout etat compact/edite).

### 4.4 Barre filtres/scope du corpus
Code actuel:
- `src/howimetyourcorpus/app/tabs/tab_corpus.py:116`
- `src/howimetyourcorpus/app/tabs/tab_corpus.py:140`
- `src/howimetyourcorpus/app/tabs/tab_corpus.py:683`
- `src/howimetyourcorpus/app/tabs/tab_corpus.py:1014`

Avant:
- Beaucoup de controles sur une seule ligne (saison, statut, cocher saison, scope, preview).

Apres:
- Decouper en 2 lignes:
  - Ligne A: filtres de vue (Saison, Statut).
  - Ligne B: perimetre d'action (Scope + resume "N episodes cibles" + CTA scope).
- Ajouter un resume explicite dynamique: "Action X s'appliquera a N episode(s)".

Pourquoi:
- Ergonomie: separation "filtrer" vs "agir".
- Efficacite: limite erreurs de perimetre.
- Maintenabilite: code plus lisible (2 sous-layouts).

Risque:
- Faible.

### 4.5 Table episodes (macOS)
Code actuel:
- `src/howimetyourcorpus/app/tabs/tab_corpus.py:158`
- `src/howimetyourcorpus/app/models_qt.py:395`

Avant:
- Bon choix technique (`QTableView`) pour macOS.
- Colonnes en `Stretch` partout: lisibilite variable selon largeur.
- Etat vide peu guide.

Apres:
- Conserver `QTableView`, mais:
  - largeur fixe pour colonnes courtes (`ID`, `Saison`, `Episode`, `Statut`, `SRT`, `Aligne`)
  - `Titre` en `Stretch`.
- Ajouter placeholder etat vide dans la table: "Aucun episode. Cliquez sur Decouvrir episodes".
- Ajouter tri explicite sur colonne `Statut` et `ID` avec icone de tri visible.

Pourquoi:
- Ergonomie: meilleure stabilite visuelle des colonnes.
- Performance: reste base model/view natif, aucun cout majeur.
- Efficacite: empty state actionnable.

Risque:
- Faible.

### 4.6 Bloc 1 Import
Code actuel:
- `src/howimetyourcorpus/app/tabs/tab_corpus.py:194`

Avant:
- 6 boutons alignes, de poids quasi identique.

Apres:
- Regrouper actions primaires/secondaires:
  - Primaire: `Decouvrir episodes`, `Telecharger`.
  - Secondaire: `Tout cocher`, `Tout decocher`, `Ajouter episodes`, `Decouvrir (fusionner...)`.
- Ajouter micro-resume de sortie sous le bloc: "Produit: RAW + index episodes".

Pourquoi:
- Clarte outputs: l'utilisateur comprend ce que produit l'etape.
- Ergonomie: hiérarchie d'actions nette.

Risque:
- Faible.

### 4.7 Bloc 2 Transformer/Indexer
Code actuel:
- `src/howimetyourcorpus/app/tabs/tab_corpus.py:231`

Avant:
- `Normaliser`, `Segmenter`, `Tout faire`, `Indexer DB`, `Exporter corpus` au meme plan.

Apres:
- CTA principal visible selon etat:
  - si RAW dispo: `Normaliser`
  - si CLEAN dispo: `Segmenter`
  - si segmentation prete: `Indexer DB`
- `Tout faire` style secondaire (puissant mais risqué)
- `Exporter corpus` decale dans un sous-groupe "Sorties".
- Ajout ligne "Sorties attendues": CLEAN / segments / DB indexes.

Pourquoi:
- Efficacite: action principale immediate.
- Robustesse: limite clics "Tout faire" involontaires.
- Clarte metier: outputs explicites.

Risque:
- Faible a moyen (style + logique d'accentuation CTA).

### 4.8 Bloc 3 Reprise erreurs
Code actuel:
- `src/howimetyourcorpus/app/tabs/tab_corpus.py:295`

Avant:
- Bonne base (liste + relance ciblee/globale + ouvrir inspecteur).
- Peu de contexte sur la nature de l'erreur dans la liste.

Apres:
- Ajouter colonnes virtuelles ou suffixe dans item: `S01E01 - normalize (timeout)`.
- Ajouter CTA "Ouvrir logs filtres sur episode".
- Ajouter bouton "Copier IDs en erreur".

Pourquoi:
- Efficacite diagnostic.
- Recuperation erreur plus rapide.

Risque:
- Moyen (si enrichment via parsing logs), faible si version minimaliste (copie IDs).

### 4.9 Feedback progression et double canal global/local
Code actuel:
- local: `src/howimetyourcorpus/app/tabs/tab_corpus.py:333`
- global: `src/howimetyourcorpus/app/ui_mainwindow.py:124`
- busy wiring: `src/howimetyourcorpus/app/ui_mainwindow.py:616`

Avant:
- Barre globale utile mais pas toujours percue comme "source de verite".
- Barre locale toujours presente, parfois redondante.

Apres:
- Conserver les deux, mais expliciter roles:
  - globale = job en cours (toutes tabs)
  - locale = progression du workflow corpus
- Afficher un libelle synchronise: "Progression job global" / "Progression corpus".

Pourquoi:
- Clarte d'etat.
- Meilleure comprehension multi-onglets.

Risque:
- Faible.

### 4.10 Action recommandee
Code actuel:
- `src/howimetyourcorpus/app/tabs/tab_corpus.py:357`

Avant:
- Bonne idee fonctionnelle, mais style discret et faible saillance.

Apres:
- Transformer en "bandeau de next step" sticky en bas du bloc corpus.
- Ajouter sous-texte court: "Pourquoi cette action" (source: `workflow_advice`).
- Raccourci clavier optionnel: `Cmd+Enter` execute action recommandee.

Pourquoi:
- Efficacite: accelere le flux expert.
- Ergonomie: guidance claire pour novices.

Risque:
- Faible a moyen (raccourci clavier global a tester).

## 5) Plan d'action priorise (ce qui est deja reviewed + ajouts)

## P0 (1 sprint court, faible risque)
1. Reduire le bruit d'entete Pilotage avec panneau aide repliable.
2. Recomposer la barre filtres/scope en 2 lignes (vue vs action).
3. Donner une vraie prominence a `Action recommandee` (bandeau + style CTA).
4. Ajouter etat vide guide dans table episodes.
5. Stabiliser largeur colonnes table macOS (`Titre` extensible, autres fixes).

Impact attendu:
- Clics inutiles reduits.
- Moins d'erreurs de scope.
- Meilleure lisibilite immediate.

## P1 (2e sprint, risque modere)
1. Mode compact de la section Projet apres ouverture.
2. Hierarchie primaire/secondaire dans Bloc 1 et Bloc 2.
3. Clarification explicite des sorties produites par bloc (RAW/CLEAN/DB).
4. CTA diagnostic depuis panneau erreurs vers logs filtres episode.

Impact attendu:
- Parcours expert plus rapide.
- Comprehension de la production par etape.

## P2 (ameliorations avancees)
1. Raccourcis clavier `Cmd+Enter` (action recommandee), `Cmd+L` (logs), `Cmd+Shift+R` (refresh erreurs).
2. Enrichissement semantique de la liste d'erreurs (etape + cause courte).
3. Eventuelle micro-animation d'etat de job (sans surcharge visuelle).

Impact attendu:
- Productivite power users.
- Meilleure recuperation d'erreur a grande echelle.

## 6) Risques et garde-fous

Risques:
- Regression de layout sur petites resolutions.
- Confusion temporaire si style des boutons change trop vite.
- Conflits de raccourcis clavier avec widgets texte.

Garde-fous:
- Tester macOS en largeur 1280 et 1440.
- Garder les labels existants (pas de rupture terminologique).
- Lancer tests UI/logic existants apres chaque lot.
- Mettre les changements UX derrière un flag interne si besoin (`new_pilotage_ui`).

## 7) Validation (Definition of Done)

Checklist:
1. En moins de 10 secondes, un nouvel utilisateur identifie la prochaine action.
2. En moins de 3 clics, un utilisateur expert lance une action batch sur scope voulu.
3. Aucune ambiguite sur "ce que produit" chaque bloc.
4. Aucun freeze pendant job (global bar reactive + annulation disponible).
5. Navigation clavier basique validee sur controles principaux.

KPI simples a suivre:
- Temps median "projet ouvert -> premier telechargement".
- Taux d'erreurs de scope (annulations/reprises immediates).
- Taux d'usage `Action recommandee`.
- Temps median de reprise d'un episode en erreur.

## 8) Proposition de sequence implementation

1. Lot UX rapide (P0) sur `tab_pilotage.py` + `tab_corpus.py` uniquement.
2. Validation manuelle macOS + test non-regression.
3. Lot P1 sur compact mode Projet + hierarchie d'actions.
4. Lot P2 optionnel selon feedback utilisateurs.

