# Checklist Workflow E2E

---

## ① Checklist automatisée

```bash
# Backend — pytest (unitaires + E2E pipeline)
cd HIMYC
pytest -q                                # unitaires
pytest tests/test_e2e_pipeline.py -v    # E2E pipeline

# Frontend — Playwright (VITE_E2E=true)
cd himyc-tauri
npm run test:e2e
```

Attendu : tous les tests passent sans erreur.

---

## ② Validation manuelle — Frontend Tauri (v0.7.0)

### Pré-requis

```bash
HIMYC_PROJECT_PATH=/path/to/projet \
uvicorn howimetyourcorpus.api.server:app --port 8765
# puis : cd himyc-tauri && npm run tauri dev
```

---

### Scénario T-A : Pipeline transcript → export

| # | Étape | Attendu | ✓ |
|---|-------|---------|---|
| 1 | Hub s'affiche — KPIs à zéro ou cohérents | Pas d'erreur console | ☐ |
| 2 | Constituer → épisode visible dans la table | `sources` affichées correctement | ☐ |
| 3 | Importer un transcript via `→ Inspecter` | Bouton "Normaliser" apparaît, état `raw` | ☐ |
| 4 | Cliquer "Normaliser" | Feedback "Terminé ✓", état passe à `clean` | ☐ |
| 5 | Cliquer "Segmenter" | Feedback "Terminé ✓", état passe à `segmented` | ☐ |
| 6 | Éditer le transcript normalisé (inline) | Zone texte éditable, bouton "Sauvegarder" | ☐ |
| 7 | Exporter → onglet "Segments" → CSV | Résultat "✓ N → /path/to/export.csv" | ☐ |
| 8 | Exporter → onglet "Corpus" → TXT | Résultat "✓" et fichier lisible | ☐ |

---

### Scénario T-B : Alignement + Audit View

| # | Étape | Attendu | ✓ |
|---|-------|---------|---|
| 1 | Importer SRT EN + FR dans Constituer | Sources `srt_en`, `srt_fr` visibles | ☐ |
| 2 | Aligner → configurer run (pivot EN, cible FR) | Run créé, progression affichée | ☐ |
| 3 | Audit View : table liens chargée | Virtual scroll fluide (60fps) | ☐ |
| 4 | Keyboard `A` / `R` sur lien focusé | Statut change, highlight OK | ☐ |
| 5 | Keyboard `N` / `P` | Page suivante/précédente dans le scroll | ☐ |
| 6 | Minimap : clic dans une zone | Table scrolle vers la position correspondante | ☐ |
| 7 | Retarget modal : chercher une cue | Liste filtrée, réassignation OK | ☐ |
| 8 | Note inline sur un lien | Persiste après rechargement de la vue | ☐ |
| 9 | Bulk "Accepter tout auto" | N liens mis à jour, compteur stats mis à jour | ☐ |
| 10 | Export rapport JSON/HTML | Téléchargement déclenché | ☐ |

---

### Scénario T-C : Personnages

| # | Étape | Attendu | ✓ |
|---|-------|---------|---|
| 1 | Constituer → Personnages → Créer un personnage | Apparaît dans la liste | ☐ |
| 2 | Auto-assign (dry run) | Prévisualisation des labels non matchés | ☐ |
| 3 | Auto-assign (live) | Assignations créées | ☐ |
| 4 | Propagate → choisir run | Message `N segments · M cues mis à jour` | ☐ |
| 5 | Concordancier : `speaker` affiché correctement | Nom canonique, pas le label brut | ☐ |

---

### Scénario T-D : Concordancier KWIC

| # | Étape | Attendu | ✓ |
|---|-------|---------|---|
| 1 | Concordancier → taper un mot | Résultats KWIC avec contexte ±45 chars | ☐ |
| 2 | Activer case-sensitive (bouton Aa) | Résultats filtrés strictement | ☐ |
| 3 | Filtre épisode | Seuls les résultats de l'épisode sélectionné | ☐ |
| 4 | Facettes | Agrégations cohérentes avec les résultats | ☐ |
| 5 | Export TSV | Fichier téléchargé, headers corrects | ☐ |

---

### Critères de sortie (Go/No-Go)

| Critère | Seuil |
|---------|-------|
| Scénario T-A complet | 8/8 ☑ |
| Scénario T-B complet | 10/10 ☑ |
| Scénario T-C complet | 5/5 ☑ |
| Scénario T-D complet | 5/5 ☑ |
| 0 erreur 500 dans les logs backend | obligatoire |
| 0 erreur console JS bloquante | obligatoire |
| Tests automatisés : 0 failing | obligatoire |

---

## ③ Checklist historique — Frontend PyQt (≤ v0.6.10)

> Conservé pour référence. Les scénarios A/B/C ci-dessous ciblent l'UI PyQt.

### Scénario A : Transcript → Préparer → Alignement → Personnages

1. Ouvrir un projet existant ou en créer un. Attendu : onglets sans erreur, épisodes chargés.
2. Corpus — découvrir épisodes, télécharger. Attendu : statut `Téléchargés` augmente.
3. Inspecteur — normaliser puis segmenter. Attendu : segments visibles, stats remplies.
4. Préparer — Segmenter en tours, Ajouter ligne, Fusionner, Scinder, Regrouper. Attendu : sauvegarde OK.
5. Alignement — run Phrases puis Tours, accepter/rejeter un lien, exporter. Attendu : exports générés.
6. Personnages — créer, charger assignations, propager. Attendu : cues/segments mis à jour.
7. Exports concordancier parallèle. Attendu : contenu aligné cohérent.

### Scénario B : Sous-titres only

1. Ajouter épisodes manuellement.
2. Importer SRT EN + FR.
3. Préparer SRT — valider strict/non-strict.
4. Lancer alignement similarité. Attendu : run créé.

### Scénario C : Continuité multi-langues

1. Dans Projet, définir langues hors défaut.
2. Vérifier combo langue dans Sous-titres, Personnages, Préparer.
3. Attendu : mêmes langues visibles sur tous les onglets concernés.
