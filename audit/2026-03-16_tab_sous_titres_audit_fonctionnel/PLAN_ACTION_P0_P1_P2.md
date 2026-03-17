# Plan d'Action - Audit Fonctionnel Sous-titres

## P0 - Corriger

- Aucun P0 identifie sur le branchement fonctionnel des controles.

## P1 - Completer

1. Ajouter des tests UI directs pour les slots critiques de `SubtitleTabWidget`:
- `_import_file`
- `_import_batch`
- `_import_opensubtitles`
- `_normalize_track`
- `_export_srt_final`
- `_save_content`

2. Ajouter un test de non-regression sur le comportement batch en cas de doublons `(episode, langue)` dans `_import_batch`:
- soit dedup explicite,
- soit warning utilisateur + regle "dernier fichier gagne" documentee.

3. Renforcer la preuve d'integration en mode release (`.exe`) avec un smoke semi-automatise:
- ouverture projet,
- import SRT batch,
- verification presence piste.

## P2 - Polish

1. Clarifier la documentation UX:
- "Sous-titres est integre a l'onglet Inspecteur (pas un onglet dedie)."

2. Ameliorer l'ergonomie de retour utilisateur post-job:
- signaler explicitement que le rafraichissement final depend de la fin de job pipeline (eviter l'impression de stale state juste apres clic).

3. Refactoriser `_import_batch` (complexite elevee) vers un helper/service pour faciliter maintenance et testabilite.
