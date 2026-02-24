# Checklist Workflow E2E

Date de référence: 2026-02-24
Version code vérifiée: HEAD local

## Pré-check

1. Lancer la base automatique:
```bash
pytest -q
```
2. Attendu: `178 passed`.

## Scénario A: Transcript -> Préparer -> Alignement -> Personnages

1. Projet
   - Ouvrir un projet existant ou en créer un.
   - Attendu: onglets sans erreur, épisodes chargés.
2. Corpus
   - Découvrir les épisodes puis télécharger au moins un épisode.
   - Attendu: statut `Téléchargés` augmente.
3. Inspecteur
   - Ouvrir un épisode, normaliser puis segmenter.
   - Vérifier `Phrases` et `Tours`.
   - Attendu: segments visibles, stats remplies.
4. Préparer (source Transcript)
   - Ouvrir le même épisode.
   - Utiliser `Segmenter en tours`, `Ajouter ligne`, `Fusionner`, `Scinder au curseur`, `Regrouper par assignations`.
   - Enregistrer.
   - Attendu: sauvegarde OK; si structure modifiée et run existant, message critique avant invalidation des runs.
5. Alignement
   - Lancer un run en `Phrases`, puis un run en `Tours`.
   - Tester accepter/rejeter un lien.
   - Générer `Groupes` puis exporter.
   - Attendu: runs visibles, exports générés.
6. Personnages
   - Créer/éditer des personnages.
   - Charger assignations (`Segments (tours)` ou `Cues`), enregistrer.
   - Propager avec un run d'alignement.
   - Attendu: message de propagation, cues/segments mis à jour.
7. Concordance / Exports
   - Exporter concordancier parallèle (classique + groupes).
   - Attendu: contenu aligné cohérent entre langues.

## Scénario B: Sous-titres only

1. Corpus
   - Ajouter épisodes manuellement.
2. Inspecteur/Sous-titres
   - Importer piste SRT EN + FR (ou autre langue projet).
3. Préparer (sources SRT)
   - Ouvrir `SRT <lang>`, éditer texte et timecodes.
   - Tester `Validation stricte` activée/désactivée.
   - Attendu: strict bloque chevauchements; non strict autorise.
4. Alignement
   - Lancer alignement (similarité si nécessaire).
   - Attendu: run créé, liens consultables.

## Scénario C: Continuité multi-langues projet

1. Dans Projet, définir langues incluant une langue non par défaut (ex: `es`).
2. Vérifier la langue dans:
   - Sous-titres (combo langue import),
   - Personnages (`Cues ES`),
   - Préparer (source `SRT ES`).
3. Attendu: mêmes langues visibles sur les onglets concernés.

## Vérifs de continuité inter-onglets

1. Préparer dirty -> changement d'onglet:
   - Cliquer `Ignorer`.
   - Attendu: brouillon abandonné et état persistant rechargé (pas seulement dirty=false).
2. Fin de job pipeline:
   - Attendu: rafraîchissement automatique de `Corpus`, `Inspecteur`, `Préparer`, `Sous-titres`, `Alignement`, `Personnages`.
3. Handoff explicite:
   - Depuis Préparer, `Aller à l'alignement`.
   - Attendu: épisode et `segment_kind` correctement transmis.

## Critères de sortie

1. Aucun blocage fonctionnel entre onglets.
2. Aucun écart de langue entre onglets.
3. Aucune perte silencieuse de données sur `Ignorer`.
4. Exports alignement/concordance générés et lisibles.
