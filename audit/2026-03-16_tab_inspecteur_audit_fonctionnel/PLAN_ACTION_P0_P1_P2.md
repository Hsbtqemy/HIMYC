# Plan d'Action - Audit Fonctionnel Inspecteur

## P0 - Corriger

- Aucun P0 identifie sur le branchement des controles Inspecteur.

## P1 - Completer

1. Ajouter des tests UI de non-regression pour les slots a impact metier:
- `_run_segment` (garde clean + payload du step)
- `_export_segments` (mapping extension/filter + erreurs I/O)
- `_open_profiles_dialog` (refresh combo + preview apres fermeture)

2. Clarifier le comportement de segmentation dans la doc utilisateur:
- `Segmente l'episode` genere `sentence` et `utterance`.
- `Kind` dans Inspecteur filtre l'affichage, ne change pas le mode d'execution.

3. Ajouter un test d'integration sur conservation episode en mode combine
- changer episode dans le selecteur commun,
- verifier synchro Inspecteur + Sous-titres + refresh.

## P2 - Polish

1. Ameliorer la lisibilite UX du bloc segmentation
- micro-copy explicite sur la generation des deux types de segments.

2. Refactoriser `_export_segments` (complexite elevee) vers helper dedie
- simplifier la logique suffix/filter,
- rendre les erreurs plus testables.

3. Eventuellement separer davantage la logique `_load_episode`
- lecture meta,
- choix profil,
- chargement texte/notes,
pour faciliter maintenance future.
