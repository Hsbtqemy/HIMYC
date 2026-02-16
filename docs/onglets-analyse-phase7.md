# 🔍 Analyse des Onglets — Phase 7

**Date** : 2026-02-16  
**Objectif** : Analyser chaque onglet du programme pour identifier les opportunités d'amélioration (UX, performance, maintenabilité)

---

## 📋 Vue d'ensemble

Le programme HIMYC est organisé en **9 onglets** :

1. **Projet** — Configuration projet, langues, source
2. **Corpus** — Import transcripts/sous-titres, découverte épisodes
3. **Sous-titres** — Gestion pistes SRT/VTT multi-langues
4. **Inspecteur** — Visualisation épisode (texte, segments, cues)
5. **Inspecteur Sous-titres** — Comparaison multi-langues
6. **Concordance** — Recherche KWIC (épisodes, segments, cues)
7. **Alignement** — Transcript ↔ EN ↔ FR/IT, liens, validation
8. **Personnages** — Noms canoniques, assignation, propagation
9. **Logs** — Historique des opérations pipeline

---

## 🟢 Onglets Déjà Optimisés (Phases 1-6)

### ✅ **Onglet Corpus** (Phase 5)
- **Refonte Phase 5** : Sources équilibrées (Transcripts + Sous-titres au même niveau)
- **Décorateurs Phase 5** : `@require_project`, `@require_project_and_db`
- **UI claire** : Deux colonnes symétriques, tooltips explicites
- **Statut** : **Optimal**

### ✅ **Onglet Concordance** (Phase 2)
- **Recherche KWIC** : Performante avec FTS5
- **Multi-scope** : Épisodes, Segments, Cues
- **Export multi-format** : CSV, TSV, JSON, JSONL, DOCX
- **Statut** : **Optimal**

### ✅ **Base de Données** (Phase 6)
- **Context manager** : `with db.connection()` (31-76x plus rapide)
- **Index optimisés** : 6 index ciblés (Phase 6)
- **PRAGMA performants** : WAL, cache, mmap
- **Statut** : **Optimal**

---

## 🟡 Onglets à Analyser/Améliorer

### 1. 📁 **Onglet Projet**

**Fonctionnalités** :
- Création/ouverture de projet
- Configuration source (adapter)
- Gestion langues projet
- Affichage métadonnées

**Observations** :
- ✅ Interface claire
- ⚠️ **Validation manquante** : Pas de vérification si URL série valide
- ⚠️ **Feedback insuffisant** : Après création projet, pas de confirmation visuelle
- ⚠️ **Langues fixes** : EN/FR/IT, pas d'ajout custom

**Recommandations** :
1. **Ajouter validation URL** : Détecter adapter avant création
2. **Feedback création** : Notification + ouverture auto du projet
3. **Langues extensibles** : Permettre ajout de langues custom (ISO 639-1)

---

### 2. 🗂️ **Onglet Sous-titres**

**Fonctionnalités** :
- Import SRT/VTT par épisode
- Affichage pistes par langue
- Suppression pistes

**Observations** :
- ✅ Fonctionnel
- ⚠️ **Import un par un** : Pas de batch import (contrairement au Corpus)
- ⚠️ **Pas de validation** : Format SRT vérifié seulement à l'import (erreurs non affichées)
- ⚠️ **Normalisation manquante** : Les cues text_clean ne sont pas normalisées avec les profils
- ⚠️ **Pas de prévisualisation** : Impossible de voir le SRT avant import

**Recommandations** :
1. **Import batch** : Ajouter "Importer SRT pour plusieurs épisodes" (dossier avec S01E01.fr.srt, S01E02.fr.srt, etc.)
2. **Validation stricte** : Afficher erreurs de parsing (timecodes invalides, encodage)
3. **Normalisation des cues** : Appliquer profils de normalisation sur `text_clean` (comme pour transcripts)
4. **Prévisualisation** : Dialogue montrant 10 premières cues avant import

---

### 3. 🔍 **Onglet Inspecteur**

**Fonctionnalités** :
- Visualisation texte brut / normalisé
- Segmentation (phrases, tours de parole)
- Affichage segments avec métadonnées

**Observations** :
- ✅ UI claire
- ⚠️ **Performance lourde** : Affichage texte complet peut être lent (>50KB)
- ⚠️ **Pas de navigation** : Impossible de sauter à un segment spécifique (ex: segment #45)
- ⚠️ **Édition limitée** : On peut modifier speaker_explicit mais pas le texte du segment
- ⚠️ **Validation DB répétée** : Chaque méthode vérifie `db` (candidat pour décorateur)

**Recommandations** :
1. **Lazy loading** : Charger texte par chunks (ou pagination)
2. **Navigation segments** : Barre de recherche "Aller au segment #N"
3. **Édition avancée** : Permettre correction du texte segment (+ historique)
4. **Décorateurs Phase 7** : Appliquer `@require_project_and_db` (éliminer 10+ lignes)

---

### 4. 🌐 **Onglet Inspecteur Sous-titres**

**Fonctionnalités** :
- Comparaison multi-langues (EN / FR / IT)
- Affichage cues alignées temporellement

**Observations** :
- ✅ Concept excellent (comparaison visuelle)
- ⚠️ **Requêtes multiples** : 3 appels DB séparés (1 par langue) pour 1 épisode
- ⚠️ **Pas d'export** : Impossible d'exporter la vue comparative
- ⚠️ **Timecodes fixes** : Pas de lecture vidéo intégrée (hors scope mais utile)
- ⚠️ **Filtre manquant** : Impossible de filtrer par plage de temps (ex: 10:00-15:00)

**Recommandations** :
1. **Optimisation DB** : Méthode `get_cues_multi_lang(episode_id, langs)` (1 requête au lieu de 3)
2. **Export comparative** : CSV avec colonnes EN | FR | IT
3. **Filtre temporal** : Slider "Afficher cues entre MM:SS et MM:SS"
4. **Highlight différences** : Colorier les cues avec texte très différent (pour détecter erreurs de synchro)

---

### 5. 🔗 **Onglet Alignement**

**Fonctionnalités** :
- Lancer alignement épisode (segments ↔ cues EN ↔ cues FR/IT)
- Table des liens (role: pivot/target)
- Accepter/Rejeter/Modifier liens
- Export concordancier parallèle

**Observations** :
- ✅ Fonctionnalité complète
- ✅ Modification manuelle (dialogue cues)
- ⚠️ **Complexité élevée** : Flux non intuitif pour débutants
- ⚠️ **Pas de progression** : Alignement long (1000+ liens) sans barre de progression
- ⚠️ **Validation bulk manquante** : Impossible d'accepter 50 liens d'un coup
- ⚠️ **Statistiques cachées** : Bouton "Stats" ouvre dialogue, devrait être toujours visible

**Recommandations** :
1. **Tutoriel intégré** : Tooltip ou wizard "Nouveau ? Suivez ces 3 étapes"
2. **Barre de progression** : Intégrer dans AlignEpisodeStep (déjà prévu on_progress?)
3. **Actions bulk** : Bouton "Accepter tous les liens > 0.8 confidence"
4. **Stats permanentes** : Panneau latéral avec nb_auto/accepted/rejected en temps réel
5. **Filtres avancés** : Afficher seulement liens "auto" ou "confidence < 0.5"

---

### 6. 👥 **Onglet Personnages**

**Fonctionnalités** :
- Liste personnages (noms canoniques + par langue)
- Import noms depuis segments
- Assignation segment/cue → personnage
- Propagation via liens alignement

**Observations** :
- ✅ Concept avancé (gestion multi-langue)
- ⚠️ **UX complexe** : Assignation manuelle lourde (1 segment à la fois)
- ⚠️ **Import limité** : Depuis segments uniquement (pas depuis cues EN)
- ⚠️ **Propagation opaque** : Pas de feedback détaillé (quels segments/cues modifiés ?)
- ⚠️ **Validation répétée** : 6 méthodes vérifient `store`/`db` (candidat décorateur)

**Recommandations** :
1. **Auto-détection** : Analyser patterns ("Marshall:", "Ted :") pour pré-assigner
2. **Import multi-source** : Importer noms depuis cues EN (speaker metadata SRT)
3. **Propagation détaillée** : Dialogue recap "52 segments Marshall, 38 cues FR Ted modifiés"
4. **Décorateurs Phase 7** : `@require_project_and_db` sur 6 méthodes (éliminer 36 lignes)
5. **Export/Import JSON** : Sauvegarder/charger liste personnages d'un projet à l'autre

---

### 7. 📜 **Onglet Logs**

**Fonctionnalités** :
- Affichage logs pipeline (info, warning, error)
- Scrolling auto
- Filtrage par niveau (à implémenter ?)

**Observations** :
- ✅ Fonctionnel
- ⚠️ **Pas de filtrage** : Impossible de voir seulement les erreurs
- ⚠️ **Pas d'export** : Impossible de sauvegarder logs (debug)
- ⚠️ **Pas de timestamps** : Les logs n'affichent pas l'heure
- ⚠️ **Performance** : TextEdit peut ralentir avec >10000 lignes

**Recommandations** :
1. **Filtrage niveau** : Boutons "Tout | Info | Warning | Error"
2. **Export logs** : Bouton "Sauvegarder logs.txt"
3. **Timestamps** : Préfixer chaque ligne avec `[HH:MM:SS]`
4. **Limite buffer** : Garder seulement les 1000 dernières lignes (éviter lag)
5. **Recherche** : Champ "Filtrer par mot-clé"

---

## 🔴 Problèmes Transversaux

### 1. **Duplication Validation DB/Store**

**Observation** : ~40 méthodes vérifient manuellement :
```python
if not store or not db:
    QMessageBox.warning(self, "X", "Ouvrez un projet d'abord.")
    return
```

**Solution Phase 7** : Étendre les décorateurs `@require_project` et `@require_project_and_db` à **tous les onglets**.

**Gain estimé** : **120+ lignes éliminées**, code plus lisible

---

### 2. **Absence de Undo/Redo**

**Observation** : Actions destructives (supprimer run, supprimer piste SRT) sont irréversibles.

**Solution** :
- Ajouter confirmation "Êtes-vous sûr ?" avant suppression
- (Optionnel long terme) : Implémenter QUndoStack pour opérations critiques

---

### 3. **Pas de Raccourcis Clavier**

**Observation** : Toutes les actions nécessitent la souris.

**Solution** :
- `Ctrl+O` : Ouvrir projet
- `Ctrl+S` : Sauvegarder (profils, personnages, etc.)
- `Ctrl+F` : Recherche (Concordance)
- `Ctrl+E` : Export (onglet actif)
- `F5` : Refresh onglet actif

---

### 4. **Feedback Asynchrone Manquant**

**Observation** : Opérations longues (fetch 50 épisodes, alignement) bloquent l'UI sans feedback.

**Solution** :
- QProgressDialog pour opérations > 2s
- Statut en temps réel ("Fetching S01E05... 12/50")
- Bouton "Annuler" (QThread.requestInterruption())

---

## 📊 Priorisation des Améliorations

### 🔴 **Haute Priorité** (Impact UX majeur)

1. **Décorateurs onglets** (Inspecteur, Personnages, Sous-titres) → -120 lignes
2. **Validation/Feedback actions** (création projet, import SRT, alignement)
3. **Barre progression opérations longues** (fetch, alignement, export)
4. **Stats alignement permanentes** (onglet Alignement)

### 🟡 **Moyenne Priorité** (Améliore productivité)

5. **Import batch SRT** (onglet Sous-titres)
6. **Filtrage logs** (onglet Logs)
7. **Navigation segments** (Inspecteur)
8. **Actions bulk alignement** ("Accepter tous > 0.8")
9. **Export multi-format logs** (TXT)

### 🟢 **Basse Priorité** (Nice-to-have)

10. **Langues custom** (Projet)
11. **Lazy loading texte** (Inspecteur)
12. **Comparaison cues optimisée** (Inspecteur Sous-titres)
13. **Auto-détection personnages** (Personnages)
14. **Undo/Redo** (toute l'app)
15. **Raccourcis clavier** (toute l'app)

---

## 🎯 Plan d'Action Phase 7

### Étape 1 : Décorateurs Onglets (1h)
- Appliquer `@require_project_and_db` à :
  - `tab_inspecteur.py` (10 méthodes)
  - `tab_personnages.py` (6 méthodes)
  - `tab_sous_titres.py` (4 méthodes)
  - `tab_alignement.py` (8 méthodes)
  - `tab_inspecteur_sous_titres.py` (3 méthodes)

**Gain** : **120 lignes éliminées**, cohérence totale

---

### Étape 2 : Validation & Feedback (2h)
- **Création projet** : Valider URL + adapter, feedback visuel
- **Import SRT** : Afficher erreurs parsing, prévisualisation
- **Alignement** : QProgressDialog intégré

---

### Étape 3 : Améliorer Alignement (1h)
- **Stats permanentes** : Panneau latéral
- **Actions bulk** : "Accepter liens > N confidence"
- **Filtres table** : "Montrer seulement auto/rejected"

---

### Étape 4 : Améliorer Logs (30min)
- **Filtrage niveau** : ComboBox "Tout | Info | Warning | Error"
- **Export** : Bouton "Sauvegarder logs.txt"
- **Timestamps** : Préfixer lignes avec `[HH:MM:SS]`

---

### Étape 5 : Import Batch SRT (1h)
- **Nouvelle fonctionnalité** : Importer dossier avec pattern `S01E01.fr.srt`, `S01E01.en.srt`, etc.
- **Détection auto** : Parser noms fichiers pour extraire saison/épisode/langue

---

## ✅ Tests de Validation Phase 7

1. **Décorateurs** : Appeler méthodes sans projet ouvert → Warning cohérent
2. **Import batch SRT** : Importer 10 SRT d'un coup → Tous enregistrés
3. **Stats alignement** : Lancer alignement → Stats visibles en permanence
4. **Filtrage logs** : Générer 100 logs mixtes → Filtrer seulement "Error"
5. **Raccourcis** : Tester Ctrl+O, Ctrl+S, F5 → Fonctionnels

---

## 📚 Documentation à Créer

1. **`docs/onglets-analyse-phase7.md`** : Ce fichier (analyse complète)
2. **`docs/onglets-guide-utilisateur.md`** : Guide UX par onglet
3. **`CHANGELOG_ONGLETS_PHASE7.md`** : Résumé des améliorations implémentées

---

## 🎓 Enseignements

1. **Cohérence UI** : Décorateurs = moins de duplication, UX uniforme
2. **Feedback essentiel** : Opérations asynchrones sans feedback = frustration
3. **Batch > Individuel** : Import/export batch = gain productivité exponentiel
4. **Stats visibles** : Informations critiques (alignement) doivent être toujours affichées
5. **Validation early** : Détecter erreurs avant exécution (URL, format SRT) = moins de bugs

---

**🎯 Objectif Phase 7** : Éliminer duplication code UI, améliorer feedback utilisateur, enrichir fonctionnalités batch.
