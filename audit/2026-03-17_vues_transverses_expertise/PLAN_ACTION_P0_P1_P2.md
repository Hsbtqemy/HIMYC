# Plan d'Action - Vues Transverses d'Expertise

## P0 - Corriger

- Aucun P0 identifie sur les flux transverses verifies.

## P1 - Completer

1. Creer une vue transverse unifiee "Expert"
- synthese contexte episode/source courant,
- etat run alignement (segment_kind, pivot/cible, stats),
- etat propagation personnages,
- indicateurs undo/redo et draft dirty.

2. Ajouter un test E2E transverse unique
- scenario continu: Preparer -> Alignement -> Personnages -> retour Preparer,
- verification automatique du contexte conserve et des metadonnees run/segment_kind.

3. Augmenter les tests undo/redo transverses
- couvrir explicitement au moins un cas Preparer + un cas Alignement en plus du cas Sous-titres.

## P2 - Polish

1. Uniformiser les messages de handoff inter-onglets
- termes harmonises pour episode/source/segment_kind.

2. Ajouter un "journal transverse" dans Logs
- traces lisibles des transitions de contexte et refresh multi-tabs.

3. Exposer une mini-checklist expert dans l'UI
- points de controle rapides avant export final.
