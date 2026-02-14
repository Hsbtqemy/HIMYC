# Checklist accessibilite UI (desktop Qt)

Date: 2026-02-14
Projet: HowIMetYourCorpus

## Objectif

Fournir un protocole simple, reproductible et testable pour valider l'accessibilite de base des ecrans critiques sans ajouter de dependances externes.

## Perimetre critique

1. Pilotage (Projet + Corpus)
2. Inspecteur
3. Validation / Annotation (Alignement + Personnages)
4. Concordance
5. Logs

## 1) Navigation clavier

- `Tab` et `Shift+Tab` parcourent tous les controles actionnables sans piege focus.
- `Space`/`Enter` activent les boutons principaux.
- Tableau corpus: navigation fleches + selection stable.
- Tableau personnages: edition cellule possible au clavier.
- Table assignations: combo personnage modifiable sans souris.
- `Ctrl/Cmd+F`: focus recherche (Concordance par defaut, Logs si actif).
- `Ctrl/Cmd+L`: ouverture directe du panneau Logs.

Criteres OK:
- Aucun controle principal inaccessible sans souris.
- Pas de saut de focus incoherent entre colonne gauche/droite en Pilotage.

## 2) Focus visuel

- L'element actif est visible (outline/etat focus lisible en theme sombre).
- Le focus ne depend pas uniquement d'un changement de couleur faible contraste.
- Lors d'ouverture de tab via raccourci, le focus est place sur le champ attendu.

Criteres OK:
- Focus visible sur tous les champs texte, combos, tables, boutons CTA.

## 3) Lisibilite et densite

- Taille minimale fenetre testee: 1280x800.
- Aucun chevauchement de labels/boutons.
- Zone corpus reste prioritaire et lisible en split 2 colonnes.
- Pas de scroll interne parasite dans la colonne droite au demarrage.

Criteres OK:
- Information cle visible sans superposition.
- CTA principaux detectables en moins de 2 secondes (scan visuel).

## 4) HDPI (Windows)

Executer les tests a 125%, 150%, 200% (Display Scaling):
- Verifier troncature des libelles boutons.
- Verifier alignements des groupes (Projet/Source/Normalisation/Langues).
- Verifier table corpus: entetes lisibles, colonnes resizeables, pas de clipping severe.
- Verifier barres de progression et badges d'etat.

Criteres OK:
- Aucun texte critique coupe de maniere bloquante.
- Aucun controle hors viewport sans possibilite de resize/split.

## 5) Couleurs et etats

- Etats job `idle/running/cancelling/done/error` lisibles sans ambiguite.
- Messages d'erreur accompagnent une action suivante (retry, logs, inspecteur).
- Ne pas encoder une info uniquement par couleur: ajouter texte explicite.

Criteres OK:
- Un utilisateur peut distinguer les etats meme avec perception couleur limitee.

## 6) Longues operations

- Pendant job: UI non bloquante, boutons critiques desactives correctement.
- Progression visible (barre globale + messages status).
- Annulation disponible et retour etat coherent.

Criteres OK:
- Aucun freeze > 1s lors des interactions de base.
- Etat final coherent apres cancel/erreur/succes.

## 7) Journalisation et recuperation

- Depuis erreur episode, ouverture logs filtree sur episode fonctionne.
- Logs consultables et filtrables au clavier.
- Copie diagnostic accessible sans souris.

Criteres OK:
- Chemin de recovery en <= 3 actions (ouvrir logs -> filtrer -> relancer).

## 8) Rapport de validation (template)

Pour chaque onglet:
- Resultat: OK / KO
- Defaut observe
- Etapes de reproduction
- Capture (si necessaire)
- Priorite: P0/P1/P2
- Correctif propose

## Sequencement recommande

1. Valider navigation clavier + focus visuel.
2. Valider lisibilite macOS (resolutions 13" + ecran large).
3. Valider HDPI Windows (125/150/200%).
4. Ouvrir tickets correctifs P0/P1 avec preuve de repro.
